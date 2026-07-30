"""Rolling serve/return strength tracker built from match box scores.

For every player we keep cumulative sums (overall and per surface) of:

- service games played / held      -> hold percentage
- return games played / breaks     -> break percentage
- opponent quality faced           -> schedule adjustment

OPPONENT ADJUSTMENT (the part that separates a model from a toy):
a challenger regular can post a 0.84 grass hold% against weak
returners while a top-10 player posts 0.86 against elite ones.  Raw
percentages without schedule context are garbage.  For every service
game we therefore also accumulate the opponent's *current* shrunk
break%, and for every return game the opponent's *current* shrunk
hold%.  Raw rates are then deflated/inflated in odds form:

    adj_hold_odds = raw_hold_odds · (avg_opp_break_faced / TOUR_BREAK_AVG)
    adj_break_odds = raw_break_odds · (avg_opp_hold_faced / TOUR_HOLD_AVG)

Facing weak returners (avg_opp_break < tour avg) deflates an inflated
hold%, facing weak servers deflates an inflated break%.  The factor is
capped to [0.7, 1.4] so tiny samples cannot explode.

Matchup prediction for "A holds serve against B" combines the adjusted
abilities via a league-adjusted odds-ratio (log5 family):

    P(A holds) = hA·(1-bB)·(1-L) / (hA·(1-bB)·(1-L) + (1-hA)·bB·L)

with L = tour hold average.  It reduces EXACTLY to hA when B is a
league-average returner and moves in the right direction for
strong/weak returners.

Small samples are shrunk toward the tour average with a prior of
``PRIOR_GAMES`` games.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Optional, Tuple

from .data_loader import normalize_player_name

SURFACES = ("Hard", "Clay", "Grass", "Carpet")
OVERALL_KEY = "__overall__"

# ATP tour averages (long-run): servers hold ~77%, returners break ~23%.
# WTA is a different universe (~70.6% hold, measured on Tennis Abstract
# top-100 box scores 2024-2026, n=56.6k service games): passing WTA rows
# through ATP constants would inflate every hold rating, so the averages
# are constructor parameters, not module constants.
TOUR_HOLD_AVG = 0.770
TOUR_BREAK_AVG = 0.230
WTA_TOUR_HOLD_AVG = 0.706
WTA_TOUR_BREAK_AVG = 1.0 - WTA_TOUR_HOLD_AVG
PRIOR_GAMES = 60.0
MIN_SURFACE_GAMES = 30.0
# opponent-adjustment factor is capped to this range
ADJUST_MIN, ADJUST_MAX = 0.70, 1.40

# Only tour-level events feed serve/return ratings.  Challenger box
# scores measure players against *challenger* opposition; mixing them
# in inflates journeymen (their "break%" comes against weak servers,
# so one opponent-adjustment pass cannot rescue them — circular
# reference).  Elo still consumes challengers (Elo is opponent-adjusted
# by construction); serve ratings must be level-pure.
TOUR_LEVEL_CATEGORIES = frozenset(
    {"gs", "1000", "atp500", "atp250", "og", "atpCup", "atpFinal", "wta_tour"}
)


def is_tour_level(row) -> bool:
    return row.get("series_category_id") in TOUR_LEVEL_CATEGORIES


class _Accum:
    __slots__ = ("sv_gms", "sv_held", "ret_gms", "ret_breaks",
                 "sv_opp_break_sum", "ret_opp_hold_sum")

    def __init__(self) -> None:
        self.sv_gms = 0.0
        self.sv_held = 0.0
        self.ret_gms = 0.0
        self.ret_breaks = 0.0
        self.sv_opp_break_sum = 0.0   # sum(sv_gms * opponent break% at the time)
        self.ret_opp_hold_sum = 0.0   # sum(ret_gms * opponent hold% at the time)


def _odds(p: float) -> float:
    p = min(max(p, 1e-4), 1.0 - 1e-4)
    return p / (1.0 - p)


def _from_odds(o: float) -> float:
    return o / (1.0 + o)


class ServeReturnModel:
    """Chronological tracker; state only moves when ``update`` is called."""

    def __init__(self, hold_avg: float = TOUR_HOLD_AVG,
                 break_avg: float = TOUR_BREAK_AVG) -> None:
        self._table: Dict[Tuple[str, str], _Accum] = defaultdict(_Accum)
        self._hold_avg = hold_avg
        self._break_avg = break_avg

    # ------------------------------------------------------------------ update

    def update_from_match_row(self, row) -> None:
        """Consume one ManTennisData stats row (winner/loser box score)."""
        surface = row.get("surface")
        keys = [OVERALL_KEY] + ([surface] if surface in SURFACES else [])
        self._add_player(row, "win", "los", keys)
        self._add_player(row, "los", "win", keys)

    _NAME_COLUMN = {"win": "winner_key", "los": "loser_key"}

    def _add_player(self, row, me: str, opp: str, keys) -> None:
        # rows must already carry normalized keys (add_normalized_names);
        # fall back to normalizing the raw name so callers can't mismatch
        name = row.get(self._NAME_COLUMN[me])
        opp_name = row.get(self._NAME_COLUMN[opp])
        if not name:
            raw = row.get("winner_name" if me == "win" else "loser_name")
            name = normalize_player_name(raw)
        if not opp_name:
            raw_opp = row.get("loser_name" if me == "win" else "winner_name")
            opp_name = normalize_player_name(raw_opp)
        if not isinstance(name, str) or not name:
            return
        sv_gms = _num(row.get(f"{me}_service_games_played"))
        ret_gms = _num(row.get(f"{me}_return_games_played"))
        # breaks I conceded = opponent's converted break points
        breaks_conceded = _num(row.get(f"{opp}_break_points_converted"))
        breaks_made = _num(row.get(f"{me}_break_points_converted"))
        if sv_gms is None or ret_gms is None or breaks_conceded is None or breaks_made is None:
            return  # no usable box score for this match

        # opponent's CURRENT overall rates (before this match) for the
        # schedule adjustment; tour average when the opponent is unknown
        opp_hold, opp_break = self.hold_and_break(
            opp_name if isinstance(opp_name, str) else "", None
        )

        for key in keys:
            acc = self._table[(name, key)]
            acc.sv_gms += sv_gms
            acc.sv_held += max(sv_gms - breaks_conceded, 0.0)
            acc.ret_gms += ret_gms
            acc.ret_breaks += breaks_made
            acc.sv_opp_break_sum += sv_gms * opp_break
            acc.ret_opp_hold_sum += ret_gms * opp_hold

    # -------------------------------------------------------------- prediction

    def _rates(self, player: str, key: str) -> Tuple[Optional[float], Optional[float]]:
        acc = self._table.get((player, key))
        if acc is None or acc.sv_gms <= 0 or acc.ret_gms <= 0:
            return None, None
        raw_hold = acc.sv_held / acc.sv_gms
        raw_break = acc.ret_breaks / acc.ret_gms

        # schedule adjustment in odds form (capped)
        avg_opp_break = acc.sv_opp_break_sum / acc.sv_gms
        avg_opp_hold = acc.ret_opp_hold_sum / acc.ret_gms
        hold_factor = min(max(avg_opp_break / self._break_avg, ADJUST_MIN), ADJUST_MAX)
        break_factor = min(max(avg_opp_hold / self._hold_avg, ADJUST_MIN), ADJUST_MAX)
        adj_hold = _from_odds(_odds(raw_hold) * hold_factor)
        adj_break = _from_odds(_odds(raw_break) * break_factor)

        # shrinkage toward tour average after adjustment
        hold = (adj_hold * acc.sv_gms + PRIOR_GAMES * self._hold_avg) / (
            acc.sv_gms + PRIOR_GAMES
        )
        brk = (adj_break * acc.ret_gms + PRIOR_GAMES * self._break_avg) / (
            acc.ret_gms + PRIOR_GAMES
        )
        return hold, brk

    def hold_and_break(
        self, player: str, surface: Optional[str]
    ) -> Tuple[float, float]:
        """Adjusted + shrunk (hold%, break%), surface-aware with fallback."""
        hold_s, brk_s = (None, None)
        if surface in SURFACES:
            acc = self._table.get((player, surface))
            if acc is not None and acc.sv_gms >= MIN_SURFACE_GAMES:
                hold_s, brk_s = self._rates(player, surface)
        hold_o, brk_o = self._rates(player, OVERALL_KEY)
        hold = hold_s if hold_s is not None else (hold_o if hold_o is not None else self._hold_avg)
        brk = brk_s if brk_s is not None else (brk_o if brk_o is not None else self._break_avg)
        return hold, brk

    def expected_hold_probabilities(
        self, player_a: str, player_b: str, surface: Optional[str]
    ) -> Tuple[float, float]:
        """P(A holds serve vs B) and P(B holds serve vs A) via log5."""
        hold_a, break_a = self.hold_and_break(player_a, surface)
        hold_b, break_b = self.hold_and_break(player_b, surface)
        p_a = _log5(hold_a, break_b, self._hold_avg)
        p_b = _log5(hold_b, break_a, self._hold_avg)
        return p_a, p_b


def _log5(rate: float, opp_counter_rate: float, league_hold: float = TOUR_HOLD_AVG) -> float:
    """League-adjusted odds-ratio combination on the hold% scale.

    rate             = A's hold% (vs average returners)
    opp_counter_rate = B's break% (vs average servers)

    Odds form, normalised by the tour hold average L:

        P = hA·(1-bB)·(1-L) / (hA·(1-bB)·(1-L) + (1-hA)·bB·L)

    Properties: B league-average (bB = 1-L) -> P = hA exactly;
    strong returner (bB > 1-L) pushes P below hA, weak above.
    """
    numerator = rate * (1.0 - opp_counter_rate) * (1.0 - league_hold)
    denominator = numerator + (1.0 - rate) * opp_counter_rate * league_hold
    if denominator <= 0:
        return rate
    return numerator / denominator


def _num(value) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and value != value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
