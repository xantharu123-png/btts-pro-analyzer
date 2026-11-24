"""The public choice is about evidence from this game, not the broadest event."""
from copy import deepcopy

import pytest

import app
import live_football_board as board
from live_football_source import analyze_detail
from test_live_football_source import native


def observed(home_xg, away_xg, *, red=False, clock=45, priors=(2., 1.), score=(1, 0)):
    game = native()
    game["fixture"]["status"] = {"elapsed": clock, "short": "HT" if clock == 45 else "1H", "extra": None}
    game["events"][1]["time"]["elapsed"] = 19
    for group in game["statistics"]:
        for stat in group["statistics"]:
            if stat["type"] == "expected_goals":
                stat["value"] = home_xg if group["team"]["id"] == 1 else away_xg
            if stat["type"] == "Red Cards" and not red:
                stat["value"] = 0
    if not red:
        game["events"].pop()
    game["goals"] = dict(zip(("home", "away"), score, strict=True))
    if score == (0, 0):
        game["events"].pop(0)
    game["score"]["halftime"] = dict(game["goals"]) if clock == 45 else {"home": None, "away": None}
    ordinary, specialist = analyze_detail(game, prior_reader=lambda _: priors)
    return game, ordinary, specialist


def assess(game, ordinary, red=None, age=1):
    return app._assess_live_fixture(game, ordinary, red, age=age, freemode=False)


def test_full_next_scorer_label_is_not_prefixed_twice():
    from types import SimpleNamespace
    for selection in ("Nächstes Tor: PAOK", "PAOK"):
        assert board._pick_label(SimpleNamespace(market="Nächstes Tor", selection=selection)) == "Nächstes Tor: PAOK"


def test_open_tip_does_not_round_up_to_a_certain_outcome():
    from types import SimpleNamespace
    assert board._percent(SimpleNamespace(model_probability=99.996)) == ">99,9 %"


def test_neutral_tempo_at_halftime_does_not_produce_a_generic_goal_pick():
    game, ordinary, specialist = observed(1., .5)
    assert ordinary["remaining_goals"]["over_0_5_probability"] > 55
    best, status = assess(game, ordinary, specialist)
    assert best is None and status == "Geprüft – kein Tipp"


def test_cardiff_two_scoreless_minutes_cannot_turn_a_high_prior_into_a_live_tip():
    game, ordinary, specialist = observed(0., 0., clock=2, priors=(2.091, 1.109), score=(0, 0))
    assert ordinary["remaining_goals"]["over_0_5_probability"] == pytest.approx(94.7, abs=.05)
    assert assess(game, ordinary, specialist)[0] is None


def test_small_real_tempo_difference_is_not_an_actionable_signal():
    game, ordinary, specialist = observed(0.95, 0.49)
    assert assess(game, ordinary, specialist)[0] is None


@pytest.mark.parametrize("minute, visible", [(14, False), (15, True)])
def test_minimum_verified_playing_time_also_applies_to_large_early_xg_differences(minute, visible):
    game, ordinary, specialist = observed(0., 2.9, clock=minute, score=(0, 0))
    best, _ = assess(game, ordinary, specialist)
    assert (best is not None) is visible
    if best:
        assert best[1]["live_comparison"]["market"] != "next_goal"


def test_withdrawn_dismissal_cannot_promote_a_stale_advantage_at_the_same_minute():
    game, ordinary, specialist = observed(.05, .02, red=True)
    assert assess(game, ordinary, specialist)[0] is not None
    game["events"].pop()
    for group in game["statistics"]:
        for stat in group["statistics"]:
            if stat["type"] == "Red Cards":
                stat["value"] = 0
    assert assess(game, ordinary, specialist)[0] is None


def test_lift_winner_is_same_selection_as_receipt_and_shortcheck():
    from live_tip_surface import live_snapshot_fields
    game, ordinary, specialist = observed(0.05, 0.02, red=True)
    best, _ = assess(game, ordinary, specialist)
    assert best is not None
    candidate, row, red = best
    assert "live_comparison" in row
    choice = row["live_comparison"]
    fields = live_snapshot_fields(candidate, row, red=red)
    assert fields and (fields["market"], fields["side"]) == (choice["market"], choice["side"])
    assert choice["label"] == candidate.selection
    assert choice["market"] not in {"next_goal", "next_scorer"}
    assert "1:0" in choice["reason"] and "19" in choice["reason"]
    assert "live_comparison" not in ordinary  # input is never rewritten


def test_first_half_added_time_encoding_cannot_change_a_red_card_selection():
    game, _, _ = observed(.25, .90, red=True)
    game["score"]["halftime"] = {"home": None, "away": None}
    game["events"][1]["time"]["elapsed"] = 39
    probabilities = []
    for elapsed, extra in [(45, 5), (50, None)]:
        game["fixture"]["status"] = {"elapsed": elapsed, "short": "1H", "extra": extra}
        ordinary, _ = analyze_detail(game, prior_reader=lambda _: (1.2, 2.0))
        best, _ = assess(game, ordinary)
        assert best is not None
        probabilities.append((best[0].selection, best[0].model_probability))
    assert probabilities[0] == probabilities[1]


@pytest.mark.parametrize("damage", ["away_id", "minute", "phase", "stale", "future", "no-comparison"])
def test_invalid_snapshot_cannot_fall_back_to_the_old_most_probable_goal(damage):
    game, source, specialist = observed(.05, .02, red=True)
    row = deepcopy(source)
    if damage == "away_id":
        row["away_team_id"] += 1
    if damage == "minute":
        row["minute"] += 1
    if damage == "phase":
        row["phase_data"]["status"] = "1H"
    if damage == "no-comparison":
        row.pop("xg_data")
    assert assess(game, row, specialist, age={"stale": 121, "future": -1}.get(damage, 1))[0] is None
