"""The scoreboard displays native card events, not an 11-v-10 model verdict."""
import pytest

import live_football_source as source


def card(team_id, player, minute, detail="Red Card", **extra):
    return {"type": "Card", "detail": detail, "team": {"id": team_id}, "player": {"id": player},
            "time": {"elapsed": minute}, **extra}


def match(*events):
    return {"fixture": {"id": 81, "status": {"short": "2H", "elapsed": 64}},
            "teams": {"home": {"id": 11, "name": "Heim"}, "away": {"id": 22, "name": "Gast"}},
            "events": list(events)}


def counts(team, count):
    return {"team": {"id": team}, "statistics": [{"type": "Red Cards", "value": count}]}


def test_confirmed_cards_for_both_teams_are_chronological_without_xg_or_model():
    row = match(card(22, 200, 62, comments="Substitute"),
                card(11, 101, 45, time={"elapsed": 45, "extra": 3}),
                card(11, 100, 25, "Second Yellow card"),
                card(11, 100, 25), card(11, 999, 18, "Yellow Card"))
    row["statistics"] = [counts(22, 1), counts(11, 2)]
    assert source.analyze_detail(row) == (None, None)
    assert source.confirmed_live_dismissals(row) == (("home", 25, 0, False), ("home", 45, 3, False),
                                                    ("away", 62, 0, True))


@pytest.mark.parametrize("event", [
    card(22, 8, 65), card(77, 8, 21), card(22, True, 21), card(22, 8, 21, fixture_id=82),
    card(22, 8, 21, team={"id": 22, "name": "Heim"}), card(22, 8, False),
    card(22, 8, 45, time={"elapsed": 45, "extra": False}),
    card(22, 8, 21, comments="Red Card overturned"),
    card(22, 8, 21, "Yellow Card"),
])
def test_misattributed_future_and_non_final_cards_are_not_facts(event):
    assert source.confirmed_live_dismissals(match(event)) == ()


def test_native_counts_if_present_must_agree_for_the_affected_side():
    row = match(card(11, 9, 20), card(22, 8, 45))
    assert source.confirmed_live_dismissals(row) == (("home", 20, 0, False), ("away", 45, 0, False))
    row["statistics"] = [counts(11, None), counts(22, 1)]
    assert source.confirmed_live_dismissals(row) == (("away", 45, 0, False),)


def test_cancelled_red_card_is_not_shown_but_another_teams_card_survives():
    row = match(card(22, 8, 31), card(11, 9, 40),
                card(22, 8, 34, "Red card cancelled", type="Var"),
                card(11, 9, 42, "Red card confirmed", type="Var"))
    assert source.confirmed_live_dismissals(row) == (("home", 40, 0, False),)


@pytest.mark.parametrize("change", [
    lambda row: row["fixture"].update(id=False), lambda row: row["fixture"]["status"].update(short="FT"),
    lambda row: row["teams"]["home"].update(id=22),
    lambda row: row.update(statistics=[counts(22, True)]),
    lambda row: row.update(statistics=[counts(22, 1), counts(22, 1)]),
    lambda row: row.update(statistics=[dict(counts(22, 1), fixture={"id": 99})]),
])
def test_unproved_native_identity_clock_or_card_count_is_not_a_fact(change):
    row = match(card(22, 8, 45))
    change(row)
    assert source.confirmed_live_dismissals(row) == ()


@pytest.mark.parametrize(("phase", "minute", "extra", "expected"), [
    ("BT", 90, None, (("home", 90, 4),)),
    ("ET", 99, None, (("home", 90, 4), ("away", 97, 0))),
    ("BT", 105, None, (("home", 90, 4), ("away", 97, 0), ("away", 105, 2))),
    ("ET", 106, None, (("home", 90, 4), ("away", 97, 0), ("away", 105, 2))),
    ("ET", 120, 2, (("home", 90, 4), ("away", 97, 0), ("away", 105, 2))),
    ("P", 120, None, (("home", 90, 4), ("away", 97, 0), ("away", 105, 2), ("home", 120, 3))),
    ("P", 90, None, (("home", 90, 4),)),
])
def test_extra_time_breaks_and_shootout_keep_only_completed_card_events(phase, minute, extra, expected):
    row = match(card(11, 1, 90, time={"elapsed": 90, "extra": 4}),
                card(22, 2, 97), card(22, 3, 105, time={"elapsed": 105, "extra": 2, "period": "ET1"}),
                card(11, 4, 120, time={"elapsed": 120, "extra": 3}),
                card(11, 5, 112, time={"elapsed": 112, "period": "ET1"}))
    row["fixture"]["status"] = {"short": phase, "elapsed": minute, "extra": extra}
    assert source.confirmed_live_dismissals(row) == tuple((*event, False) for event in expected)


def test_native_card_upgrade_does_not_invent_a_red_or_erase_a_corroborated_card_for_the_same_player():
    row = match(card(11, 1, 25, "Second Yellow Card"),
                card(11, 1, 26, "Card upgrade", type="Var"),
                card(22, 2, 31, "Card upgrade", type="Var"))
    row["statistics"] = [counts(11, 1), counts(22, 0)]
    assert source.confirmed_live_dismissals(row) == (("home", 25, 0, False),)


def test_explicit_denial_or_unattributed_staff_note_is_not_a_player_dismissal():
    row = match(card(11, 1, 25, comments="No red card"),
                card(22, None, 31, comments="Coach"))
    assert source.confirmed_live_dismissals(row) == ()


@pytest.mark.parametrize("kind", ["VAR", "card"])
def test_explicit_card_reversal_survives_event_type_casing(kind):
    row = match(card(11, 1, 25), card(11, 1, 27, "Red card cancelled", type=kind))
    assert source.confirmed_live_dismissals(row) == ()


def test_an_undatable_card_review_during_extra_time_does_not_confirm_the_original_card():
    row = match(card(11, 1, 25), card(11, 1, False, "Red card cancelled", type="Var"))
    row["fixture"]["status"] = {"short": "ET", "elapsed": 100}
    assert source.confirmed_live_dismissals(row) == ()


def test_later_var_confirmation_restores_only_its_reviewed_card_and_still_needs_matching_counts():
    row = match(card(11, 1, 31), card(22, 2, 39), card(11, 1, 32, "Red card under review", type="Var"),
                card(22, 2, 40, "Red card under review", type="Var"),
                card(11, 1, 34, "Red card confirmed", type="Var"))
    assert source.confirmed_live_dismissals(row) == (("home", 31, 0, False),)
    row["statistics"] = [counts(11, 0)]
    assert source.confirmed_live_dismissals(row) == ()


@pytest.mark.parametrize(("review", "who", "when"), [
    ("Red card cancelled", 1, 34), ("Red card under review", 2, 34),
    ("Red card under review", None, 34), ("Red card under review", 1, 32),
])
def test_confirmation_does_not_undo_a_cancellation_or_an_unresolved_review(review, who, when):
    row = match(card(11, 1, 31), card(11, 1, 32, review, type="Var"),
                card(11, who, when, "Red card confirmed", type="Var"))
    assert source.confirmed_live_dismissals(row) == ()


def test_matching_duplicates_preserve_off_field_evidence_but_conflicting_minutes_are_not_guessed():
    row = match(card(22, 2, 39), card(22, 2, 39, "Second Yellow Card", comments="Substitute"),
                card(11, 1, 31), card(11, 1, 48))
    assert source.confirmed_live_dismissals(row) == (("away", 39, 0, True),)
