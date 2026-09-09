"""Existing event-loss statistics, extracted without a new release policy.

Callers own canonical events, chronology, common cohorts and input validation.
These formulas alone do not prove source quality or authorize a context effect.
Legacy wrapper input behavior and the original HAC/BH arithmetic are preserved.
"""
from __future__ import annotations

import math

PAIRED_LOSS_CONFIDENCE_Z = 1.6448536269514722


def paired_advantage_statistics(paired_advantages: list[float]) -> tuple[
    float | None, float | None, float | None, float | None,
]:
    """Return mean, HAC standard error, lower bound and one-sided p, in order.

    Do not sort by advantage or turn one event into multiple market samples.
    D2 supplies bounded, finite per-event Brier advantages in chronological order.
    """
    if not paired_advantages:
        return None, None, None, None
    try:
        if any(not math.isfinite(value) for value in paired_advantages):
            return None, None, None, None
    except (TypeError, ValueError, OverflowError):
        return None, None, None, None
    observations = len(paired_advantages)
    mean_advantage = sum(paired_advantages) / observations
    if observations < 2:
        return mean_advantage, None, None, None

    centered = [value - mean_advantage for value in paired_advantages]
    gamma_zero = sum(value * value for value in centered) / observations
    # Standard automatic Newey-West bandwidth for a low-order HAC estimate.
    max_lag = min(
        observations - 1,
        max(1, int(4.0 * (observations / 100.0) ** (2.0 / 9.0))),
    )
    long_run_variance = gamma_zero
    for lag in range(1, max_lag + 1):
        covariance = sum(
            centered[index] * centered[index - lag]
            for index in range(lag, observations)
        ) / observations
        bartlett_weight = 1.0 - lag / (max_lag + 1.0)
        long_run_variance += 2.0 * bartlett_weight * covariance
    standard_error = math.sqrt(max(0.0, long_run_variance) / observations)
    lower_bound = mean_advantage - PAIRED_LOSS_CONFIDENCE_Z * standard_error
    if standard_error <= 1e-15:
        p_value = 0.0 if mean_advantage > 0.0 else 1.0
    else:
        z_score = mean_advantage / standard_error
        p_value = 0.5 * math.erfc(z_score / math.sqrt(2.0))
    return (
        mean_advantage,
        standard_error,
        lower_bound,
        min(1.0, max(0.0, p_value)),
    )


def benjamini_hochberg_q_values(
    p_values: dict[str, float],
) -> dict[str, float]:
    """Deterministically adjust one-sided p-values with BH-FDR.

    Callers pass one hypothesis for every configured market, using p=1 for a
    market without a valid test.  This prevents sparse data from silently
    shrinking the 90-market testing family.
    """

    if not p_values:
        return {}
    cleaned: list[tuple[str, float]] = []
    for key, value in p_values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise ValueError("BH p-values must be finite numbers in [0, 1]")
        cleaned.append((str(key), float(value)))
    ordered = sorted(cleaned, key=lambda item: (item[1], item[0]))
    hypothesis_count = len(ordered)
    adjusted: dict[str, float] = {}
    running_minimum = 1.0
    for rank_index in range(hypothesis_count - 1, -1, -1):
        key, p_value = ordered[rank_index]
        rank = rank_index + 1
        running_minimum = min(
            running_minimum,
            p_value * hypothesis_count / rank,
        )
        adjusted[key] = min(1.0, max(0.0, running_minimum))
    return adjusted
