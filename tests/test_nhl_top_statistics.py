from datetime import datetime, timedelta, timezone

import pytest


def _games(count=200, high=50, days=30, high_days=15):
    first = datetime(2027, 1, 12, 23, tzinfo=timezone.utc)
    return [
        {
            "event_id": f"game-{idx:03d}",
            "start": first + timedelta(days=idx % (high_days if idx < high else days),
                                       seconds=idx),
            "p_model": .6996 if idx < high else .60,
            "p_market": .50,
        }
        for idx in range(count)
    ]


def _unopened(_game):
    pytest.fail("coverage must not load even one outcome")


@pytest.mark.parametrize("count,high,days,high_days", [
    (199, 50, 30, 15),
    (200, 49, 30, 15),
    (200, 50, 29, 15),
    (200, 50, 30, 14),
])
def test_each_of_four_coverage_deficits_keeps_results_closed(count, high, days, high_days):
    from nhl_top_statistics import evaluate_nhl_top

    result = evaluate_nhl_top(_games(count, high, days, high_days), _unopened)

    assert result == {
        "status": "insufficient_coverage",
        "coverage": {
            "tier_60": {"games": count, "zurich_days": days},
            "tier_70": {"games": high, "zurich_days": high_days},
        },
        "settled": None,
        "scores": None,
    }


def test_coverage_uses_zurich_date_and_display_rounding_but_not_results():
    from nhl_top_statistics import nhl_top_coverage

    games = _games(3, 2, 2, 2)
    games[0]["start"] = datetime(2026, 11, 24, 22, 59, 59, tzinfo=timezone.utc)
    games[1]["start"] = games[0]["start"] + timedelta(seconds=1)  # Different Zurich day.
    games[2]["start"] = games[1]["start"] + timedelta(minutes=1)
    games[2]["p_model"] = .6994  # Displayed as 69.9, not 70.0.

    assert nhl_top_coverage(iter(games)) == {
        "tier_60": {"games": 3, "zurich_days": 2},
        "tier_70": {"games": 2, "zurich_days": 2},
    }


def test_unresolved_result_deficit_emits_only_counts_after_reading():
    from nhl_top_statistics import evaluate_nhl_top

    games = _games()
    result = evaluate_nhl_top(games, lambda game: None if game is games[0] else 1)
    assert result["status"] == "insufficient_settled"
    assert result["settled"] == {
        "tier_60": {"games": 199, "zurich_days": 30},
        "tier_70": {"games": 49, "zurich_days": 15},
    }
    assert result["scores"] is None


def test_sufficient_decisions_but_too_few_settled_70er_dates_does_not_score():
    from nhl_top_statistics import evaluate_nhl_top

    games = _games(count=205, high=60)
    missing_ids = {"game-000", "game-015", "game-030", "game-045"}
    result = evaluate_nhl_top(games, lambda game: None if game["event_id"] in missing_ids else 0)

    assert result["status"] == "insufficient_settled"
    assert result["settled"]["tier_60"] == {"games": 201, "zurich_days": 30}
    assert result["settled"]["tier_70"] == {"games": 56, "zurich_days": 14}
    assert result["scores"] is None


def test_paired_brier_uses_raw_model_probability_and_accepts_both_positive_bounds():
    from nhl_top_statistics import evaluate_nhl_top

    result = evaluate_nhl_top(reversed(_games()), lambda game: 1)

    assert result["status"] == "passed"
    high = result["scores"]["tier_70"]
    # 50 identical games: y=1, p=.6996, market=.50. Zero HAC standard error.
    assert high["model_brier"] == pytest.approx(.09024016)
    assert high["market_brier"] == pytest.approx(.25)
    assert high["brier_advantage"] == pytest.approx(.15975984)
    assert high["paired_one_sided_95pct_lower_bound"] == pytest.approx(.15975984)
    assert result["scores"]["tier_60"]["model_brier"] == pytest.approx(.14256004)
    assert result["scores"]["tier_60"]["paired_one_sided_95pct_lower_bound"] > 0


@pytest.mark.parametrize("failed_tier,other_tier", [("tier_70", "tier_60"), ("tier_60", "tier_70")])
def test_each_nonpositive_bound_prevents_a_pass_even_when_other_tier_is_positive(failed_tier, other_tier):
    from nhl_top_statistics import evaluate_nhl_top

    games = _games()
    for game in games:
        if failed_tier == "tier_70" and game["p_model"] > .6:
            game["p_market"] = .78
        elif failed_tier == "tier_60" and game["p_model"] == .6:
            game["p_market"] = .78
    result = evaluate_nhl_top(games, lambda game: 1)

    assert result["status"] == "not_passed"
    assert result["scores"][failed_tier]["paired_one_sided_95pct_lower_bound"] < 0
    assert result["scores"][other_tier]["paired_one_sided_95pct_lower_bound"] > 0


def test_equal_model_and_market_cannot_pass():
    from nhl_top_statistics import evaluate_nhl_top

    games = _games()
    for game in games:
        game["p_market"] = game["p_model"]
    result = evaluate_nhl_top(games, lambda game: 1)
    assert result["status"] == "not_passed"
    assert result["scores"]["tier_70"]["paired_one_sided_95pct_lower_bound"] == 0


def test_hac_is_invariant_to_input_order_and_uses_chronological_games():
    from nhl_top_statistics import evaluate_nhl_top

    games = _games()

    def outcome(game):
        return int(game["start"].day % 2 == 0)

    ordered = evaluate_nhl_top(sorted(games, key=lambda game: game["start"]), outcome)
    unordered = evaluate_nhl_top(reversed(games), outcome)

    assert unordered == ordered
    # Independently summed centered lag covariances through lag four, with
    # Bartlett weights 1, .8, .6, .4, .2.
    assert ordered["scores"]["tier_60"]["paired_hac_standard_error"] == pytest.approx(
        .0153713642012521, abs=1e-12
    )


@pytest.mark.parametrize("field,value", [
    ("event_id", "game-001"),
    ("start", datetime(2027, 1, 12)),
    ("p_model", float("nan")),
    ("p_model", .599),
    ("p_market", True),
    ("p_market", 0.0),
])
def test_malformed_game_inputs_never_reach_outcome_loader(field, value):
    from nhl_top_statistics import evaluate_nhl_top

    games = _games()
    games[0][field] = value
    with pytest.raises(ValueError):
        evaluate_nhl_top(games, _unopened)


def test_outcome_loader_cannot_silently_turn_other_values_into_decisions():
    from nhl_top_statistics import evaluate_nhl_top

    with pytest.raises(ValueError):
        evaluate_nhl_top(_games(), lambda game: False)
