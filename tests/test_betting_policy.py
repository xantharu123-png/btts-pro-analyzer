"""Cross-sport contracts for the shared price and market mathematics."""

from __future__ import annotations

import pytest

from betting_math import (
    BettingMathError,
    evaluate_market_price,
    minimum_acceptable_odds,
    proportional_no_vig_market,
)


def test_minimum_price_targets_same_roi_without_fixed_edge_bias() -> None:
    favourite_odds = minimum_acceptable_odds(70.0)
    longshot_odds = minimum_acceptable_odds(20.0)

    favourite = evaluate_market_price(70.0, favourite_odds)
    longshot = evaluate_market_price(20.0, longshot_odds)

    assert favourite.risk_adjusted_expected_roi >= 3.0
    assert longshot.risk_adjusted_expected_roi >= 3.0
    # The monetary hurdle is the same even though percentage-point edge is not.
    assert favourite.risk_adjusted_edge > longshot.risk_adjusted_edge
    assert longshot.risk_adjusted_edge < 1.0


def test_minimum_price_applies_uncertainty_before_roi() -> None:
    price = minimum_acceptable_odds(
        70.0,
        probability_haircut=10.0,
        minimum_expected_roi_percent=3.0,
    )

    assert price == pytest.approx(1.72)
    metrics = evaluate_market_price(70.0, price, probability_haircut=10.0)
    assert metrics.risk_adjusted_expected_roi >= 3.0


def test_no_vig_probabilities_are_normalized_complete_market_benchmark() -> None:
    market = proportional_no_vig_market((1.91, 1.91))

    assert market.overround > 1.0
    assert sum(market.no_vig_probabilities) == pytest.approx(1.0)
    assert market.no_vig_probabilities == pytest.approx((0.5, 0.5))


def test_no_vig_rejects_incomplete_market() -> None:
    with pytest.raises(BettingMathError):
        proportional_no_vig_market((1.90,))
