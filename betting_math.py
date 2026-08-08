"""Strict betting math built around verified external market prices.

Model probabilities are produced independently. A market edge, expected ROI,
or Kelly stake only exists after a valid quote has been supplied. The wager
gate is based on risk-adjusted expected return, not on a fixed probability-point
edge that would treat favourites and longshots differently.
"""

from dataclasses import dataclass
import math
from typing import Iterable, Optional


MINIMUM_RISK_ADJUSTED_ROI_PERCENT = 3.0
MINIMUM_RECOMMENDED_DECIMAL_ODDS = 1.20
DEFAULT_KELLY_FRACTION = 0.25
DEFAULT_KELLY_CAP = 0.02
BETTING_POLICY_VERSION = "risk-ev-3pct-min-odds-1.20-v2"


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
    fair_odds: Optional[float]
    risk_adjusted_fair_odds: Optional[float]


@dataclass(frozen=True)
class NoVigMarket:
    """Proportional no-vig probabilities for one complete outcome market."""

    odds: tuple[float, ...]
    raw_implied_probabilities: tuple[float, ...]
    no_vig_probabilities: tuple[float, ...]
    overround: float


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


def _validate_nonnegative_percent(value: float, field: str) -> float:
    if isinstance(value, bool):
        raise BettingMathError(f"{field} must be numeric, not boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise BettingMathError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or number < 0.0:
        raise BettingMathError(f"{field} must be finite and non-negative")
    return number


def minimum_acceptable_odds(
    probability: float,
    *,
    probability_haircut: float = 0.0,
    minimum_expected_roi_percent: float = MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
    price_increment: float = 0.01,
) -> Optional[float]:
    """Return the first decimal price meeting the risk-adjusted ROI target.

    A fixed probability-point edge is deliberately not used. For example,
    one percentage point of edge is worth about 2% ROI at odds 2.00, but about
    6% ROI at odds 6.00. Expected return is therefore the coherent common
    comparison across probability levels.
    """

    probability_percent = validate_probability_percent(probability)
    haircut_percent = validate_probability_percent(probability_haircut)
    target_roi = _validate_nonnegative_percent(
        minimum_expected_roi_percent,
        "Minimum expected ROI",
    )
    if (
        isinstance(price_increment, bool)
        or not isinstance(price_increment, (int, float))
        or not math.isfinite(float(price_increment))
        or float(price_increment) <= 0.0
    ):
        raise BettingMathError("Price increment must be finite and positive")

    adjusted_probability = max(0.0, probability_percent - haircut_percent) / 100.0
    if adjusted_probability <= 0.0:
        return None
    exact_price = (1.0 + target_roi / 100.0) / adjusted_probability
    increment = float(price_increment)
    rounded_price = math.ceil((exact_price - 1e-12) / increment) * increment
    return max(1.0 + increment, round(rounded_price, 10))


def minimum_recommendation_odds(
    probability: float,
    *,
    probability_haircut: float = 0.0,
    minimum_expected_roi_percent: float = MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
    minimum_published_odds: float = MINIMUM_RECOMMENDED_DECIMAL_ODDS,
    price_increment: float = 0.01,
) -> Optional[float]:
    """Return the stricter of the mathematical and publication thresholds.

    The publication floor is a product-risk rule, not a claim about fair odds.
    Very short prices remain available to model evaluation but cannot become a
    visible recommendation merely because their estimated ROI clears the gate.
    """

    publication_floor = validate_decimal_odds(minimum_published_odds)
    mathematical_minimum = minimum_acceptable_odds(
        probability,
        probability_haircut=probability_haircut,
        minimum_expected_roi_percent=minimum_expected_roi_percent,
        price_increment=price_increment,
    )
    if mathematical_minimum is None:
        return None
    return max(publication_floor, mathematical_minimum)


def proportional_no_vig_market(odds: Iterable[float]) -> NoVigMarket:
    """Remove bookmaker margin proportionally from a complete market.

    The output is a market benchmark, never a substitute for the model.
    At least two mutually exclusive and exhaustive outcome prices are needed.
    """

    prices = tuple(validate_decimal_odds(price) for price in odds)
    if len(prices) < 2:
        raise BettingMathError("A no-vig market needs at least two prices")
    raw = tuple(1.0 / price for price in prices)
    overround = sum(raw)
    if not math.isfinite(overround) or overround <= 0.0:
        raise BettingMathError("Market overround is invalid")
    normalized = tuple(probability / overround for probability in raw)
    return NoVigMarket(
        odds=prices,
        raw_implied_probabilities=raw,
        no_vig_probabilities=normalized,
        overround=overround,
    )


def evaluate_market_price(
    probability: float,
    odds: float,
    *,
    probability_haircut: float = 0.0,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    kelly_cap: float = DEFAULT_KELLY_CAP,
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
        fair_odds=(1.0 / probability_decimal if probability_decimal > 0.0 else None),
        risk_adjusted_fair_odds=(
            1.0 / risk_adjusted_decimal if risk_adjusted_decimal > 0.0 else None
        ),
    )
