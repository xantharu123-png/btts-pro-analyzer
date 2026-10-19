import math

import pytest

from betting_math import (
    BettingMathError, no_vig_market, power_no_vig_market, proportional_no_vig_market, shin_no_vig_market,
)


def _fair(market, index):
    return 1.0 / market.no_vig_probabilities[index]


@pytest.mark.parametrize("method", ["proportional", "shin", "power"])
def test_every_method_returns_a_unit_law_and_keeps_raw_inputs(method):
    market = no_vig_market((1.30, 5.50, 10.0), method)
    assert market.method == method
    assert market.odds == (1.30, 5.50, 10.0)
    assert math.isclose(sum(market.no_vig_probabilities), 1.0, abs_tol=1e-9)
    assert math.isclose(market.overround, 1 / 1.30 + 1 / 5.50 + 1 / 10.0)
    assert all(0.0 < p < 1.0 for p in market.no_vig_probabilities)


def test_shin_and_power_give_outsiders_longer_fair_odds_than_proportional():
    odds = (1.30, 5.50, 10.0)
    proportional, shin, power = (no_vig_market(odds, m) for m in ("proportional", "shin", "power"))
    # Hand values from the 2026-09-02 audit appendix A4: 5.78 / 6.00 / 6.22.
    assert math.isclose(_fair(proportional, 1), 5.78, abs_tol=0.02)
    assert 5.9 <= _fair(shin, 1) <= 6.1
    assert 6.1 <= _fair(power, 1) <= 6.35
    assert _fair(proportional, 1) < _fair(shin, 1) < _fair(power, 1)
    # The favourite is correspondingly more likely than proportional removal says.
    assert shin.no_vig_probabilities[0] > proportional.no_vig_probabilities[0]
    assert power.no_vig_probabilities[0] > proportional.no_vig_probabilities[0]


def test_two_way_symmetric_market_is_a_coin_flip_under_every_method():
    for method in ("proportional", "shin", "power"):
        market = no_vig_market((1.90, 1.90), method)
        assert all(math.isclose(p, 0.5, abs_tol=1e-9) for p in market.no_vig_probabilities)


def test_margin_free_market_is_returned_unchanged():
    for market in (shin_no_vig_market((2.0, 2.0)), power_no_vig_market((4.0, 4.0, 4.0, 4.0))):
        assert math.isclose(market.overround, 1.0)
        assert all(math.isclose(p, q) for p, q in zip(market.no_vig_probabilities, market.raw_implied_probabilities))


def test_heavy_favourite_three_way_shin_versus_proportional():
    proportional = proportional_no_vig_market((1.05, 12.0, 26.0))
    shin = shin_no_vig_market((1.05, 12.0, 26.0))
    assert math.isclose(_fair(proportional, 1), 12.89, abs_tol=0.05)  # Audit appendix A4.
    assert _fair(shin, 1) > 14.5  # Shin removes most of the margin from the longshots.


def test_invalid_inputs_are_rejected():
    for method in ("proportional", "shin", "power"):
        with pytest.raises(BettingMathError):
            no_vig_market((1.5,), method)
        with pytest.raises(BettingMathError):
            no_vig_market((1.0, 2.0), method)
    with pytest.raises(BettingMathError):
        no_vig_market((1.5, 2.5), "magic")
