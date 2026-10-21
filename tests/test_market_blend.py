import math
import random

import pytest

from betting_math import BettingMathError, blended_decision_probability
from market_blend import fit_blend_weight, log_loss, replay_policy, split_by_date


def test_blend_endpoints_and_validation():
    assert blended_decision_probability(0.7, 0.4, 1.0) == pytest.approx(0.7)
    assert blended_decision_probability(0.7, 0.4, 0.0) == pytest.approx(0.4)
    mid = blended_decision_probability(0.7, 0.4, 0.5)
    assert 0.4 < mid < 0.7
    # Log-odds mixing: equal weights give the geometric mean of the odds.
    odds = math.sqrt((0.7 / 0.3) * (0.4 / 0.6))
    assert mid == pytest.approx(odds / (1 + odds))
    for bad in ((0.0, 0.4, 0.5), (0.7, 1.0, 0.5), (0.7, 0.4, 1.5)):
        with pytest.raises(BettingMathError):
            blended_decision_probability(*bad)


def _rows(seed=1, n=2000, true_weight=0.2):
    generator = random.Random(seed)
    rows = []
    for index in range(n):
        market = generator.uniform(0.2, 0.8)
        noise = generator.gauss(0.0, 0.6)
        model = 1 / (1 + math.exp(-(math.log(market / (1 - market)) + noise)))
        truth = blended_decision_probability(model, market, true_weight)
        rows.append({"date": f"2024-{1 + index % 12:02d}-{1 + index % 28:02d}", "fixture_id": index,
                     "market_key": "RESULT_HOME", "model_p": model, "market_p": market,
                     "y": int(generator.random() < truth), "offer_odds": round(1.03 / market, 2)})
    return rows


def test_weight_fit_recovers_a_small_model_share_and_scores_out_of_sample():
    rows = _rows()
    fit = fit_blend_weight(rows, label="test")
    assert fit.train_rows + fit.test_rows == len(rows)
    assert 0.05 <= fit.weight <= 0.4  # Generated with 0.2.
    assert fit.test_logloss_blend <= fit.test_logloss_model
    assert fit.test_logloss_blend <= fit.test_logloss_market + 1e-3
    train, test = split_by_date(rows)
    assert all(a.get("date") <= b.get("date") for a, b in zip(train, train[1:]))
    with pytest.raises(ValueError):
        fit_blend_weight(rows[:60], label="tiny")


def test_edge_cap_and_blend_reduce_the_bet_count_and_remove_extreme_edges():
    rows = _rows(seed=3)
    baseline = replay_policy(rows, label="base")
    capped = replay_policy(rows, label="cap", edge_cap_pp=8.0)
    blended = replay_policy(rows, label="blend", weights={"RESULT_HOME": 0.2})
    assert baseline.bets > capped.bets > 0
    assert capped.mean_edge_pp <= 8.0
    assert blended.bets < baseline.bets
    assert baseline.roi_interval is not None and baseline.clv is not None
    assert log_loss([0.5, 0.5], [1, 0]) == pytest.approx(math.log(2))
