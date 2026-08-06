"""Surface-aware Elo ratings for tennis.

FiveThirtyEight-style experience-scaled K factor:

    K(player) = 250 / (matches_played + 5) ** 0.4

Every player carries an overall rating plus one rating per surface.
New players start at 1500; with zero matches their K is highest, so
ratings converge quickly while veterans stay stable.

The tracker is updated strictly chronologically and never sees the
future: a match only enters the state AFTER its prediction was made
(see tennis/backtest.py).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, FrozenSet, Optional, Tuple

INITIAL_RATING = 1500.0
SURFACES = ("Hard", "Clay", "Grass", "Carpet")


def _k_factor(matches_played: int) -> float:
    return 250.0 / ((matches_played + 5) ** 0.4)


def _new_rating_entry() -> list:
    """Module-level factory so the defaultdict remains picklable."""
    return [INITIAL_RATING, 0]


class _RatingTable:
    def __init__(self) -> None:
        # player -> [rating, matches_played]
        self._table: Dict[str, list] = defaultdict(_new_rating_entry)

    def rating(self, player: str) -> float:
        entry = self._table.get(player)
        return entry[0] if entry is not None else INITIAL_RATING

    def matches(self, player: str) -> int:
        entry = self._table.get(player)
        return entry[1] if entry is not None else 0

    def known_players(self) -> FrozenSet[str]:
        """Return players backed by at least one historical match."""
        return frozenset(
            player for player, (_, matches) in self._table.items() if matches > 0
        )

    def update(self, winner: str, loser: str) -> Tuple[float, float]:
        """Register a result; returns the pre-update expected win prob."""
        rw, mw = self._table[winner]
        rl, ml = self._table[loser]
        expected_w = 1.0 / (1.0 + 10.0 ** ((rl - rw) / 400.0))
        self._table[winner] = [rw + _k_factor(mw) * (1.0 - expected_w), mw + 1]
        self._table[loser] = [rl + _k_factor(ml) * (0.0 - (1.0 - expected_w)), ml + 1]
        return expected_w, 1.0 - expected_w


class SurfaceElo:
    """Overall + per-surface Elo with chronological updates."""

    def __init__(self) -> None:
        self.overall = _RatingTable()
        self.by_surface: Dict[str, _RatingTable] = {s: _RatingTable() for s in SURFACES}

    def update(self, winner: str, loser: str, surface: Optional[str]) -> None:
        self.overall.update(winner, loser)
        table = self.by_surface.get(surface or "")
        if table is not None:
            table.update(winner, loser)

    def known_players(self) -> FrozenSet[str]:
        """Player keys with real history, excluding default-rating lookups."""
        return self.overall.known_players()

    def _expected(self, ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    def win_probability(
        self,
        player_a: str,
        player_b: str,
        surface: Optional[str] = None,
        surface_weight: float = 0.65,
        min_surface_matches: int = 8,
    ) -> float:
        """Blend overall and surface Elo into one win probability.

        The surface blend only kicks in once BOTH players have at least
        ``min_surface_matches`` on that surface; below that we fall back
        to the overall rating (small samples lie).
        """
        p_overall = self._expected(
            self.overall.rating(player_a), self.overall.rating(player_b)
        )
        table = self.by_surface.get(surface or "")
        if table is None:
            return p_overall
        if (
            table.matches(player_a) < min_surface_matches
            or table.matches(player_b) < min_surface_matches
        ):
            return p_overall
        p_surface = self._expected(table.rating(player_a), table.rating(player_b))
        return (1.0 - surface_weight) * p_overall + surface_weight * p_surface
