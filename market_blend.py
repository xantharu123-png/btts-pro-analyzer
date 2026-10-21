"""Decision probability as a log-odds blend of model and market, with policy replays.

Audit 2026-10-16 K3: a fixed percentage-point haircut selects the fixtures
where the model deviates most from the market (winner's curse). The remedy is
a decision probability that shrinks the model towards the no-vig market with a
weight estimated out of sample, plus a cap on the admissible model-market edge.
This module estimates that weight on benchmark rows (chronological split) and
replays the price-gate policy with blend and cap. Analysis only; the model
probability stored by the product is never changed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Optional

from betting_math import BettingMathError, blended_decision_probability, minimum_recommendation_odds
from market_benchmark import GENERIC_HAIRCUT_PP, _bootstrap_interval

WEIGHT_GRID = tuple(round(0.05 * step, 2) for step in range(21))


def _clip(p: float) -> float:
    return min(1.0 - 1e-6, max(1e-6, float(p)))


def log_loss(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    total, count = 0.0, 0
    for p, y in zip(probabilities, outcomes):
        q = _clip(p)
        total -= math.log(q) if y else math.log(1.0 - q)
        count += 1
    return total / count if count else float("nan")


def brier(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    pairs = list(zip(probabilities, outcomes))
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else float("nan")


def blended(rows: list[dict[str, Any]], weight: float) -> list[float]:
    return [blended_decision_probability(_clip(r["model_p"]), _clip(r["market_p"]), weight) for r in rows]


def split_by_date(rows: list[dict[str, Any]], train_share: float = 0.7) -> tuple[list[dict], list[dict]]:
    ordered = sorted(rows, key=lambda r: (r.get("date") or "", r["fixture_id"], r["market_key"]))
    cut = int(len(ordered) * train_share)
    return ordered[:cut], ordered[cut:]


@dataclass(frozen=True)
class WeightFit:
    label: str
    train_rows: int
    test_rows: int
    weight: float
    train_losses: dict[float, float]
    test_logloss_model: float
    test_logloss_market: float
    test_logloss_blend: float
    test_brier_model: float
    test_brier_market: float
    test_brier_blend: float


def fit_blend_weight(rows: list[dict[str, Any]], *, label: str, grid: tuple[float, ...] = WEIGHT_GRID,
                     train_share: float = 0.7) -> WeightFit:
    """Grid-search the model weight on the earlier rows, score on the later rows."""
    train, test = split_by_date(rows, train_share)
    if len(train) < 50 or len(test) < 50:
        raise ValueError("blend fit needs at least 50 training and 50 test rows")
    y_train = [r["y"] for r in train]
    losses = {w: log_loss(blended(train, w), y_train) for w in grid}
    best = min(grid, key=lambda w: (losses[w], abs(w - 0.5)))
    y_test = [r["y"] for r in test]
    return WeightFit(
        label=label, train_rows=len(train), test_rows=len(test), weight=best, train_losses=losses,
        test_logloss_model=log_loss(blended(test, 1.0), y_test), test_logloss_market=log_loss(blended(test, 0.0), y_test),
        test_logloss_blend=log_loss(blended(test, best), y_test),
        test_brier_model=brier(blended(test, 1.0), y_test), test_brier_market=brier(blended(test, 0.0), y_test),
        test_brier_blend=brier(blended(test, best), y_test),
    )


@dataclass(frozen=True)
class ReplayResult:
    label: str
    bets: int
    hit_rate: Optional[float]
    roi: Optional[float]
    roi_interval: Optional[tuple[float, float]]
    clv: Optional[float]
    clv_interval: Optional[tuple[float, float]]
    mean_edge_pp: Optional[float]


def replay_policy(rows: list[dict[str, Any]], *, label: str, haircut_pp: float = GENERIC_HAIRCUT_PP,
                  edge_cap_pp: Optional[float] = None, weights: Optional[dict[str, float]] = None,
                  default_weight: float = 1.0) -> ReplayResult:
    """Bet when the best closing offer meets the minimum odds of the decision probability.

    ``weights`` maps market keys to the model share of the blend (1.0 = pure
    model, today's policy). ``edge_cap_pp`` refuses bets whose model-minus-market
    gap exceeds the cap (audit recommendation: 8 pp).
    """
    rois, clvs, edges, wins = [], [], [], 0
    for row in rows:
        offer = row.get("offer_odds")
        if offer is None:
            continue
        model_p, market_p = _clip(row["model_p"]), _clip(row["market_p"])
        edge_pp = 100.0 * (model_p - market_p)
        if edge_cap_pp is not None and edge_pp > edge_cap_pp:
            continue
        weight = (weights or {}).get(row["market_key"], default_weight)
        decision = blended_decision_probability(model_p, market_p, weight)
        try:
            minimum = minimum_recommendation_odds(decision * 100.0, probability_haircut=haircut_pp)
        except BettingMathError:
            continue
        if minimum is None or offer < minimum:
            continue
        won = int(row["y"])
        rois.append(offer - 1.0 if won else -1.0)
        clvs.append(market_p * offer - 1.0)
        edges.append(edge_pp)
        wins += won
    if not rois:
        return ReplayResult(label, 0, None, None, None, None, None, None)
    return ReplayResult(
        label=label, bets=len(rois), hit_rate=wins / len(rois), roi=sum(rois) / len(rois),
        roi_interval=_bootstrap_interval(rois), clv=sum(clvs) / len(clvs), clv_interval=_bootstrap_interval(clvs),
        mean_edge_pp=sum(edges) / len(edges),
    )


__all__ = ["ReplayResult", "WEIGHT_GRID", "WeightFit", "blended", "brier", "fit_blend_weight", "log_loss",
           "replay_policy", "split_by_date"]
