"""Strict betting math built around verified external market prices.

Model probabilities are produced independently.  A market edge, expected ROI,
or Kelly stake only exists after a valid quote has been supplied.
"""

from dataclasses import dataclass
import math


class BettingMathError(ValueError):
    """Raised when probability or market-price inputs are invalid."""


@dataclass(frozen=True)
class ValueMetrics:
    model_probability: float
    risk_adjusted_probability: float
    probability_haircut: float
    market_odds: float
    implied_probability: float
    edge: float
    expected_roi: float
    risk_adjusted_edge: float
    risk_adjusted_expected_roi: float
    kelly_fraction: float


def validate_probability_percent(probability: float) -> float:
    """Return a finite probability expressed explicitly in percent."""
    if isinstance(probability, bool):
        raise BettingMathError("Probability must be numeric, not boolean")
    try:
        value = float(probability)
    except (TypeError, ValueError) as exc:
        raise BettingMathError("Probability must be numeric") from exc

    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        raise BettingMathError("Probability must be between 0 and 100")
    return value


def validate_decimal_odds(odds: float) -> float:
    """Return finite decimal odds; prices at or below 1.0 are invalid."""
    if isinstance(odds, bool):
        raise BettingMathError("Decimal odds must be numeric, not boolean")
    try:
        value = float(odds)
    except (TypeError, ValueError) as exc:
        raise BettingMathError("Decimal odds must be numeric") from exc

    if not math.isfinite(value) or value <= 1.0:
        raise BettingMathError("Decimal odds must be greater than 1.0")
    return value


def evaluate_market_price(
    probability: float,
    odds: float,
    *,
    probability_haircut: float = 0.0,
    kelly_fraction: float = 0.25,
    kelly_cap: float = 0.02,
) -> ValueMetrics:
    """Calculate price-dependent metrics from a model probability and quote.

    ``probability_haircut`` is an explicit percentage-point deduction applied
    for staking and the actionable edge/EV gate. It is a robustness adjustment,
    not a statistical confidence bound. ``kelly_fraction`` is the fraction of
    full Kelly to use. ``kelly_cap`` is the maximum bankroll fraction, so the
    default caps stakes at 2%.
    """
    probability_percent = validate_probability_percent(probability)
    haircut_percent = validate_probability_percent(probability_haircut)
    decimal_odds = validate_decimal_odds(odds)

    if (
        isinstance(kelly_fraction, bool)
        or not isinstance(kelly_fraction, (int, float))
        or not math.isfinite(float(kelly_fraction))
        or not 0.0 <= float(kelly_fraction) <= 1.0
    ):
        raise BettingMathError("Kelly fraction must be between 0 and 1")
    if (
        isinstance(kelly_cap, bool)
        or not isinstance(kelly_cap, (int, float))
        or not math.isfinite(float(kelly_cap))
        or not 0.0 <= float(kelly_cap) <= 1.0
    ):
        raise BettingMathError("Kelly cap must be between 0 and 1")

    probability_decimal = probability_percent / 100.0
    risk_adjusted_probability = max(0.0, probability_percent - haircut_percent)
    risk_adjusted_decimal = risk_adjusted_probability / 100.0
    implied_probability = 100.0 / decimal_odds
    edge = probability_percent - implied_probability
    expected_roi = (probability_decimal * decimal_odds - 1.0) * 100.0
    risk_adjusted_edge = risk_adjusted_probability - implied_probability
    risk_adjusted_expected_roi = (
        risk_adjusted_decimal * decimal_odds - 1.0
    ) * 100.0

    net_odds = decimal_odds - 1.0
    full_kelly = (
        (net_odds * risk_adjusted_decimal - (1.0 - risk_adjusted_decimal))
        / net_odds
    )
    applied_kelly = min(max(0.0, full_kelly) * kelly_fraction, kelly_cap)

    return ValueMetrics(
        model_probability=probability_percent,
        risk_adjusted_probability=risk_adjusted_probability,
        probability_haircut=haircut_percent,
        market_odds=decimal_odds,
        implied_probability=implied_probability,
        edge=edge,
        expected_roi=expected_roi,
        risk_adjusted_edge=risk_adjusted_edge,
        risk_adjusted_expected_roi=risk_adjusted_expected_roi,
        kelly_fraction=applied_kelly,
    )
