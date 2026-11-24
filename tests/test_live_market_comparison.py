"""A pre-kickoff-only reference and the current model must predict the very same outcome."""

import math

import pytest


def observed(*, home=1, away=0, xg=(1.8, 0.3), priors=(1.5, 0.9), minute=60, red=False):
    from live_football_source import analyze_detail
    from tests.test_live_football_source import native

    match = native()
    match["goals"] = {"home": home, "away": away}
    match["score"]["halftime"] = dict(match["goals"]) if minute >= 45 else {"home": None, "away": None}
    match["fixture"]["status"].update(elapsed=minute, short="1H" if minute < 45 else "2H")
    match["events"] = [
        {"type": "Goal", "detail": "Normal Goal", "team": {"id": idx}, "time": {"elapsed": min(10 + j, minute)}}
        for idx, n in [(1, home), (2, away)]
        for j in range(n)
    ] + (match["events"][1:] if red else [])
    for row in match["statistics"]:
        idx = row["team"]["id"]
        row["statistics"][0]["value"] = xg[idx - 1]
        row["statistics"][1]["value"] = int(red and idx == 2)
    return analyze_detail(match, prior_reader=lambda _: priors)[0]


def module():
    import live_market_comparison

    return live_market_comparison


def test_both_teams_scored_does_not_settle_the_rest_of_the_game():
    row = observed(home=1, away=1)
    assert row["breakdown"]["remaining_home_mean"] == pytest.approx(2.3 / 3)
    assert row["breakdown"]["remaining_away_mean"] == pytest.approx(0.2)
    choices = module().compare_live_markets(row)
    over = next(p for p in choices if (p.market, p.side) == ("ft_total", "over_2_5"))
    assert over.probability == pytest.approx(1 - math.exp(-2.9 / 3))
    assert all(p.market not in {"btts", "ft_btts"} for p in choices)


def test_same_score_and_minute_remove_mechanical_progress_and_rank_information_first():
    rules = module()
    choices = rules.compare_live_markets(observed())
    out = {(p.market, p.side): p for p in choices}
    # From independent unrounded Poisson grids: rest rates (.7666667,.2) versus (.5,.3), both at 1:0.
    expected = {
        ("ft_result", "home"): (0.909389877616761, 0.831320516990897),
        ("ft_dc", "1x"): (0.991442602646926, 0.976485038619278),
        ("ft_handicap", "home_minus_0_5"): (0.909389877616761, 0.831320516990897),
        ("ft_total", "under_3_5"): None,  # less likely despite a high absolute probability
        ("ft_multigoal", "total_1_3"): None,
        ("ft_btts", "no"): (0.818730753077982, 0.740818220681718),
        ("next_goal", "any"): (1 - math.exp(-2.9 / 3), 1 - math.exp(-0.8)),
        ("team_scores", "home"): None,  # lift is positive, but below 55 %
        ("next_scorer", "home"): None,
    }
    for key, pair in expected.items():
        if pair is None:
            assert key not in out
        else:
            assert (out[key].probability, out[key].reference) == pytest.approx(pair)
    assert all(p.probability >= 0.55 and p.probability > p.reference for p in choices)
    assert choices[0].probability < max(p.probability for p in choices)
    assert choices == sorted(
        choices, key=lambda p: (p.reference - p.probability, -p.probability, p.market, p.side)
    )
    assert len({(p.market, p.side) for p in choices}) == len(choices)
    for p in choices:
        assert rules.selection_labels(p.market, p.side, "1", "2") == (rules.display_market(p.market), p.label)


def test_no_information_means_no_pick_even_for_nearly_certain_outcomes():
    assert module().compare_live_markets(observed(xg=(1.0, 0.6))) == []


def test_neutral_native_minute_one_cannot_manufacture_a_handicap_lift():
    priors = (5.279, 7.569)
    row = observed(home=0, away=1, minute=1, priors=priors, xg=tuple(rate / 90 for rate in priors))
    assert module().compare_live_markets(row) == []


@pytest.mark.parametrize("minute", [49, 50])
def test_btts_no_and_still_scoreless_team_under_half_do_not_swap_due_to_roundoff(minute):
    row = observed(home=1, away=0, xg=(1.04, 0.22), priors=(1.6, 2.0), minute=minute)
    picks = module().compare_live_markets(row)
    by_key = {(p.market, p.side): (p.probability, p.reference) for p in picks}
    assert by_key["ft_btts", "no"] == by_key["ft_team_total", "away_under_0_5"]
    assert (picks[0].market, picks[0].side) == ("ft_btts", "no")


def test_next_scorer_with_zero_opposing_rate_agrees_exactly_with_another_goal():
    row = observed(home=0, away=0, xg=(4.6, 0.0), priors=(1.5, 0.0), minute=60)
    picks = {(p.market, p.side): (p.probability, p.reference) for p in module().compare_live_markets(row)}
    assert picks["next_scorer", "home"] == picks["next_goal", "any"] == picks["team_scores", "home"]


def test_an_ordinary_next_scorer_accounts_for_no_goal_and_a_card_once():
    row = observed(xg=(2.8, 0.6), red=True)
    picks = {(p.market, p.side): p for p in module().compare_live_markets(row)}
    red = row["red_cards"]
    lh, la = 1.1 * red["home_factor"], 0.3 * red["away_factor"]
    pick = picks["next_scorer", "home"]
    assert pick.probability == pytest.approx(-math.expm1(-lh - la) * lh / (lh + la))
    assert pick.reference == pytest.approx(0.5 / 0.8 * -math.expm1(-0.8))
    assert pick.probability < lh / (lh + la)


@pytest.mark.parametrize(
    "field,damage",
    [
        ("prematch_prior_source", None),
        ("live_data_quality", "LOW"),
        ("red_cards", {"supported": False}),
        ("phase_data", {"status": "ET", "remaining_minutes": 5}),
        ("xg_data", {"home_prior": 1.0, "away_prior": 1.0}),
        ("minute", 90),
        ("breakdown", {"remaining_home_mean": float("nan"), "remaining_away_mean": 0.4}),
    ],
)
def test_missing_or_unusable_comparison_never_leaks_old_candidate(field, damage):
    row = observed()
    row[field] = damage
    assert module().compare_live_markets(row) is None


@pytest.mark.parametrize(
    "market,side,score,open_,verdict",
    [
        ("ft_result", "draw", (2, 2), True, True),
        ("ft_dc", "12", (2, 2), True, False),
        ("ft_handicap", "home_minus_1_5", (2, 1), True, False),
        ("ft_handicap", "away_plus_1_5", (2, 1), True, True),
        ("ft_total", "over_2_5", (2, 1), False, True),
        ("ft_total", "under_2_5", (2, 1), False, False),
        ("ft_team_total", "home_under_1_5", (2, 0), False, False),
        ("ft_team_total", "away_under_1_5", (2, 0), True, True),
        ("ft_multigoal", "total_1_3", (2, 1), True, True),
        ("ft_multigoal", "total_1_3", (2, 2), False, False),
        ("ft_multigoal", "home_1_4", (5, 0), False, False),
        ("ft_multigoal", "away_1_4", (5, 0), True, False),
        ("ft_btts", "no", (1, 1), False, False),
        ("btts", "yes", (1, 1), False, True),
        ("next_scorer", "home", (1, 1), True, None),
        ("next_goal", "any", (0, 0), True, None),
        ("team_scores", "away", (1, 0), True, None),
        ("ft_total", "over_2_0", (2, 1), False, None),
    ],
)
def test_regulation_settlement_and_structural_openness(market, side, score, open_, verdict):
    rules = module()
    assert rules.market_open(market, side, *score) is open_
    assert rules.final_verdict(market, side, *score) is verdict


def test_next_scorer_none_uses_no_event_mass_and_zero_live_xg_is_not_missing():
    row = observed(xg=(0.0, 0.0), minute=80)
    out = {(p.market, p.side): p for p in module().compare_live_markets(row)}
    pick = out["next_scorer", "none"]
    assert pick.probability == pytest.approx(math.exp(-2.4 / 90 * 30 / 110 * 10))
    assert pick.reference == pytest.approx(math.exp(-2.4 * 10 / 90))


def test_obsolete_complete_btts_rates_are_not_trusted_even_with_a_valid_prematch_prior():
    from live_football_priors import PRIOR_REVISION

    row = observed(home=1, away=1)
    row["model_version"] = "live-restspiel-poisson-regulation-clock-v2" + PRIOR_REVISION
    row["breakdown"].update(remaining_home_mean=0.0, remaining_away_mean=0.0)
    assert module().compare_live_markets(row) is None


def test_contradictory_dismissal_state_does_not_masquerade_as_verified_no_card():
    row = observed(red=True)
    row["red_cards"]["status"] = "VERIFIED_NONE"
    assert module().compare_live_markets(row) is None


def test_numerically_certain_market_cannot_hide_another_eligible_forecast():
    # Large but accepted xG produces some probabilities equal to 1.0 in binary64.
    row = observed(home=0, away=0, xg=(20.0, 0.1), priors=(0.4, 0.3), minute=1)
    choices = module().compare_live_markets(row)
    assert choices
    assert all(0.55 <= c.probability < 1.0 for c in choices)
    assert any(c.market == "next_scorer" and c.side == "home" for c in choices)
