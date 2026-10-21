"""Benjamini-Hochberg over the whole selection family: leagues x markets.

Audit 2026-10-16, finding M5. ``challenge_engine._validation_metrics_from_records``
adjusts the one-sided paired-loss p-values only within one league (family =
``MARKET_SPECS``), yet 15K/Wettfinder candidates are selected across every
scanned league.  This module re-adjusts the already computed p-values once
over the complete family of one scan run and rewrites exactly the fields the
release gate (``challenge_engine._credible_statistical_release_validation``)
reads: ``fdr_q_value``, ``tested_hypotheses`` and ``statistical_release_passed``.

Rules
-----
* Pure function: inputs are never mutated; new ``ValidationMetrics`` objects
  are produced with ``dataclasses.replace``.
* A market without a valid test (metric missing or ``paired_loss_p_value`` is
  ``None``) enters the family with p = 1, so sparse leagues cannot shrink the
  family (same convention as the per-league procedure).
* No release threshold is tuned here: alpha stays ``VALIDATION_FDR_ALPHA`` and
  the lower-confidence-bound rule stays exactly as in the engine.
* The adjusted metrics are valid only for the league set of one run.  They
  must never be written back into the per-league model cache
  (``challenge_model_cache``), because that cache is keyed per league.
"""
from __future__ import annotations

from dataclasses import replace
import math
from typing import Any, Hashable, Iterable, Mapping, Optional, TypeVar

from challenge_engine import MARKET_SPECS, VALIDATION_FDR_ALPHA, ValidationMetrics
from model_loss_statistics import benjamini_hochberg_q_values

LeagueKey = TypeVar("LeagueKey", bound=Hashable)

# Rounding used by ``challenge_engine._validation_metrics_from_records``.
_Q_VALUE_DECIMALS = 10


def _family_market_keys(
    metrics_by_league: Mapping[Any, Mapping[str, Any]],
    market_keys: Optional[Iterable[str]],
) -> tuple[str, ...]:
    """Every configured market plus any extra key a league reports, in order."""
    ordered: dict[str, None] = {}
    base = (
        tuple(market_keys)
        if market_keys is not None
        else tuple(spec.key for spec in MARKET_SPECS)
    )
    for key in base:
        ordered[str(key)] = None
    for metrics in metrics_by_league.values():
        for key in metrics:
            ordered[str(key)] = None
    return tuple(ordered)


def _family_p_value(metric: Any) -> float:
    """p for the family; 1.0 for a missing or untested market (fail-closed)."""
    if not isinstance(metric, ValidationMetrics):
        return 1.0
    p_value = metric.paired_loss_p_value
    if (
        p_value is None
        or isinstance(p_value, bool)
        or not isinstance(p_value, (int, float))
        or not math.isfinite(float(p_value))
    ):
        return 1.0
    return min(1.0, max(0.0, float(p_value)))


def apply_cross_league_fdr(
    metrics_by_league: Mapping[LeagueKey, Mapping[str, ValidationMetrics]],
    alpha: float = VALIDATION_FDR_ALPHA,
    *,
    market_keys: Optional[Iterable[str]] = None,
) -> dict[LeagueKey, dict[str, ValidationMetrics]]:
    """Re-run BH once over all (league, market) hypotheses of one run.

    ``metrics_by_league`` maps a league key (an ``int`` league id or the
    ``(league_id, season)`` tuple used by ``challenge_15k``) to the per-league
    validation map.  The family is ``len(metrics_by_league) x len(markets)``
    where ``markets`` is every configured ``MARKET_SPECS`` key (or
    ``market_keys``) plus any extra key present in a league map.

    For every ``ValidationMetrics`` the function returns a copy with

    * ``fdr_q_value``: family-wide BH q (``None`` when the market has no p),
    * ``tested_hypotheses``: the family size,
    * ``statistical_release_passed``: ``passed`` and lower confidence bound
      > 0 and family q <= ``alpha`` (the engine's own rule, re-evaluated).

    Values that are not ``ValidationMetrics`` are returned unchanged but still
    occupy a p = 1 slot in the family.  Inputs are not mutated.
    """
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not math.isfinite(float(alpha))
        or not 0.0 < float(alpha) <= 1.0
    ):
        raise ValueError("alpha must be a finite number in (0, 1]")
    alpha = float(alpha)
    if not metrics_by_league:
        return {}

    league_keys = list(metrics_by_league)
    family_markets = _family_market_keys(metrics_by_league, market_keys)
    hypothesis_count = len(league_keys) * len(family_markets)

    family_p_values: dict[str, float] = {}
    slot_by_pair: dict[tuple[int, str], str] = {}
    for league_index, league_key in enumerate(league_keys):
        league_metrics = metrics_by_league[league_key]
        for market_key in family_markets:
            slot = f"{league_index}|{market_key}"
            slot_by_pair[(league_index, market_key)] = slot
            family_p_values[slot] = _family_p_value(league_metrics.get(market_key))
    family_q_values = benjamini_hochberg_q_values(family_p_values)
    assert len(family_q_values) == hypothesis_count

    adjusted: dict[LeagueKey, dict[str, ValidationMetrics]] = {}
    for league_index, league_key in enumerate(league_keys):
        league_metrics = metrics_by_league[league_key]
        new_league_metrics: dict[str, ValidationMetrics] = {}
        for market_key, metric in league_metrics.items():
            if not isinstance(metric, ValidationMetrics):
                new_league_metrics[market_key] = metric
                continue
            slot = slot_by_pair[(league_index, str(market_key))]
            has_test = metric.paired_loss_p_value is not None
            q_value = (
                round(family_q_values[slot], _Q_VALUE_DECIMALS)
                if has_test
                else None
            )
            lower_bound = metric.paired_loss_lower_confidence_bound
            statistical_evidence_passed = bool(
                has_test
                and q_value is not None
                and lower_bound is not None
                and not isinstance(lower_bound, bool)
                and isinstance(lower_bound, (int, float))
                and math.isfinite(float(lower_bound))
                and float(lower_bound) > 0.0
                and q_value <= alpha
            )
            new_league_metrics[market_key] = replace(
                metric,
                fdr_q_value=q_value,
                tested_hypotheses=hypothesis_count,
                statistical_release_passed=bool(
                    metric.passed is True and statistical_evidence_passed
                ),
            )
        adjusted[league_key] = new_league_metrics
    return adjusted


def cross_league_fdr_summary(
    before: Mapping[Any, Mapping[str, Any]],
    after: Mapping[Any, Mapping[str, Any]],
) -> dict[str, int]:
    """Count how many (league, market) releases the wider family changed."""
    released_before = 0
    released_after = 0
    lost = 0
    gained = 0
    for league_key, league_metrics in before.items():
        after_metrics = after.get(league_key, {})
        for market_key, metric in league_metrics.items():
            if not isinstance(metric, ValidationMetrics):
                continue
            old = metric.statistical_release_passed is True
            new_metric = after_metrics.get(market_key)
            new = (
                isinstance(new_metric, ValidationMetrics)
                and new_metric.statistical_release_passed is True
            )
            released_before += int(old)
            released_after += int(new)
            lost += int(old and not new)
            gained += int(new and not old)
    return {
        "leagues": len(before),
        "released_before": released_before,
        "released_after": released_after,
        "lost": lost,
        "gained": gained,
    }


__all__ = [
    "apply_cross_league_fdr",
    "cross_league_fdr_summary",
]
