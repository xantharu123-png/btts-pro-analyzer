"""Opponent-strength-adjusted ELO ratings for e-sports series.

The raw win-rate model treated a 80 % record against weak opposition the
same as 80 % against top teams. This module fixes that with the data we
already fetch: the union of both teams' bounded PandaScore histories
forms a match subgraph; ELO ratings are iterated chronologically over
that subgraph (two passes from a flat 1500 prior, zero-sum updates).

Design notes (kept deliberately conservative):
- Bo1 results carry a reduced K-factor (single-map variance).
- Two passes let the small subgraph settle; the residual estimation
  error of this bounded sample is priced downstream via
  ``ELO_UNCERTAINTY_MARGIN`` in the conservative candidate line.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

ELO_BASE = 1500.0
ELO_SCALE = 400.0
ELO_K_FACTOR = 40.0
ELO_BO1_K_MULTIPLIER = 0.75
ELO_ITERATIONS = 2
ELO_UNCERTAINTY_MARGIN = 150.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """P(A wins) for an ELO rating pair."""
    return 1.0 / (1.0 + 10.0 ** (-(float(rating_a) - float(rating_b)) / ELO_SCALE))


def _subgraph_matches(
    history1: List[Dict[str, Any]],
    history2: List[Dict[str, Any]],
    team1_id: int,
    team2_id: int,
) -> List[Dict[str, Any]]:
    """Merge both histories into one deduplicated chronological list.

    Direct encounters appear in both teams' histories; ``match_id``
    dedupes them so they are rated exactly once.
    """
    seen: set[int] = set()
    merged: List[Dict[str, Any]] = []
    for team_id, history in ((team1_id, history1), (team2_id, history2)):
        if not isinstance(history, list):
            continue
        for item in history:
            if not isinstance(item, dict):
                continue
            match_id = item.get("match_id")
            opponent_id = item.get("opponent_id")
            won = item.get("won")
            if (
                not isinstance(match_id, int)
                or isinstance(match_id, bool)
                or match_id <= 0
                or not isinstance(opponent_id, int)
                or isinstance(opponent_id, bool)
                or opponent_id <= 0
                or opponent_id == team_id
                or not isinstance(won, bool)
                or match_id in seen
            ):
                continue
            seen.add(match_id)
            merged.append(
                {
                    "match_id": match_id,
                    "begin_at": str(item.get("begin_at") or ""),
                    "team_id": team_id,
                    "opponent_id": opponent_id,
                    "won": won,
                    "bo1": item.get("number_of_games") == 1,
                }
            )
    merged.sort(key=lambda entry: (entry["begin_at"], entry["match_id"]))
    return merged


def subgraph_ratings(
    history1: List[Dict[str, Any]],
    history2: List[Dict[str, Any]],
    team1_id: int,
    team2_id: int,
    *,
    k_factor: float = ELO_K_FACTOR,
    iterations: int = ELO_ITERATIONS,
) -> Tuple[float, float, int]:
    """ELO ratings for both teams from their shared match subgraph.

    Returns ``(rating_team1, rating_team2, subgraph_match_count)``.
    Unknown teams start at ``ELO_BASE``; updates are zero-sum, so the
    subgraph's total rating mass stays constant.
    """
    matches = _subgraph_matches(history1, history2, team1_id, team2_id)
    ratings: Dict[int, float] = {}
    passes = max(1, int(iterations))
    for _ in range(passes):
        for match in matches:
            team_a = match["team_id"]
            team_b = match["opponent_id"]
            rating_a = ratings.get(team_a, ELO_BASE)
            rating_b = ratings.get(team_b, ELO_BASE)
            expected_a = expected_score(rating_a, rating_b)
            effective_k = k_factor * (ELO_BO1_K_MULTIPLIER if match["bo1"] else 1.0)
            score_a = 1.0 if match["won"] else 0.0
            delta = effective_k * (score_a - expected_a)
            ratings[team_a] = rating_a + delta
            ratings[team_b] = rating_b - delta
    return (
        ratings.get(team1_id, ELO_BASE),
        ratings.get(team2_id, ELO_BASE),
        len(matches),
    )
