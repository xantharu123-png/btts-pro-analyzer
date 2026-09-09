"""Frozen pre-extraction engine statistics at 3e9ce2c; policy parity only."""
import math
from typing import Optional

PAIRED_LOSS_CONFIDENCE_Z = 1.6448536269514722


def _mean(values):
    return sum(values) / len(values)


def _paired_loss_statistics(
    probabilities: list[float],
    baselines: list[float],
    outcomes: list[int],
) -> tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """Return paired Brier advantage, HAC-SE, lower bound and one-sided p.

    Every row compares model and baseline on the *same* already generated
    walk-forward prediction.  Positive loss differences therefore mean the
    model beat its contemporaneous baseline without adding any future data.
    A Bartlett/Newey-West long-run variance protects the uncertainty estimate
    against short serial runs in chronological match order.
    """

    if not probabilities or not (
        len(probabilities) == len(baselines) == len(outcomes)
    ):
        return None, None, None, None
    try:
        paired_advantages = [
            (float(baseline) - int(outcome)) ** 2
            - (float(probability) - int(outcome)) ** 2
            for probability, baseline, outcome in zip(
                probabilities,
                baselines,
                outcomes,
            )
        ]
    except (TypeError, ValueError, OverflowError):
        return None, None, None, None
    if any(not math.isfinite(value) for value in paired_advantages):
        return None, None, None, None

    observations = len(paired_advantages)
    mean_advantage = _mean(paired_advantages)
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


def _benjamini_hochberg_q_values(
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
