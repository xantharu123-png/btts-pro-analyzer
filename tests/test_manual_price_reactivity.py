"""Real Streamlit reruns: edits invalidate, explicit checks alone have effects."""
from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest

import bet_finder_ui as ui


def _manual_price_app():
    import streamlit as st
    from dataclasses import replace
    from bet_finder_ui import _render_manual_check
    from multi_sport_recommendations import RecommendationCandidate, EVIDENCE_RELEASED

    candidate = RecommendationCandidate(
        event_key="manual-reactive", sport="Fußball", event_label="Alpha vs Beta",
        market="Endergebnis", selection="Heimsieg", line=None,
        model_probability=40.0, risk_adjusted_probability=31.0,
        probability_haircut=9.0, fair_odds=2.5, minimum_odds=3.38,
        model_name="immutable-test-model", expected_total=3.0, evidence=(),
        evidence_stage=EVIDENCE_RELEASED,
        release_pending=st.session_state.get("pending", True),
    )
    keys = ("card-a", "card-b") if st.session_state.get("two_cards") else ("card-a",)
    for key in keys:
        revision = st.session_state.get("revision_" + key, 0)
        current = replace(
            candidate, event_key=key + ":" + str(revision),
            model_name="immutable-test-model-" + str(revision),
        )
        result = _render_manual_check(
            current, key=key, bankroll_key="manual_balance", price_source="Dezimalquote",
            save_source="Isolated explicit test check",
            manual_surface=st.session_state.get("surface", "popover"),
        )
        st.session_state["returned_" + key] = result


@pytest.fixture
def side_effects(monkeypatch):
    calculations, saves = [], []
    real_evaluate = ui.evaluate_candidate_price

    def evaluate(candidate, odds, *, bankroll, quote_confirmed):
        calculations.append((candidate, odds, bankroll, quote_confirmed))
        return real_evaluate(candidate, odds, bankroll=bankroll, quote_confirmed=quote_confirmed)

    monkeypatch.setattr(ui, "evaluate_candidate_price", evaluate)
    monkeypatch.setattr(ui, "_save_tip", lambda decision, *, source: saves.append((decision, source)))
    return calculations, saves


def start(*, two=False, pending=True, surface="popover"):
    app = AppTest.from_function(_manual_price_app)
    app.session_state["two_cards"] = two
    app.session_state["pending"] = pending
    app.session_state["surface"] = surface
    app.run(timeout=30)
    assert not app.exception
    return app


def submit(app, *, key="card-a", odds="1,12", bankroll=100.0, confirmed=True):
    app.text_input(key="bet_odds_" + key).input(odds)
    app.number_input(key="manual_balance_" + key).set_value(bankroll)
    app.checkbox(key="bet_confirmed_" + key).set_value(confirmed)
    index = 0 if key == "card-a" else 1
    app.button[index].click().run(timeout=30)
    assert not app.exception
    return app.session_state["returned_" + key]


def messages(app):
    return [item.value for group in (app.info, app.success, app.warning) for item in group]


def assert_invalidated(app, key="card-a"):
    assert not app.exception
    assert app.session_state["returned_" + key] is None
    with pytest.raises(KeyError):
        app.session_state["bet_decision_" + key]
    assert any("Eingabe geändert" in value and "neu prüfen" in value for value in messages(app))


@pytest.mark.parametrize("surface", ["popover", "expander"])
def test_real_manual_widgets_are_reactive_not_deferred_form_controls(side_effects, surface):
    app = start(surface=surface)
    assert not app.text_input[0].proto.form_id
    assert not app.number_input[0].proto.form_id
    assert not app.checkbox[0].proto.form_id
    assert not app.button[0].proto.form_id
    assert app.session_state["returned_card-a"] is None
    assert side_effects == ([], [])


@pytest.mark.parametrize("surface", ["popover", "expander"])
def test_original_low_quote_to_four_requires_a_new_explicit_check(side_effects, surface):
    calculations, saves = side_effects
    app = start(surface=surface)
    decision = submit(app)
    assert decision.status == "NO_BET" and decision.quoted_odds == 1.12
    assert len(calculations) == len(saves) == 1
    app.text_input[0].input("4,00").run(timeout=30)
    assert_invalidated(app)
    assert not any("erreicht die Value-Grenze" in value for value in messages(app))
    assert len(calculations) == len(saves) == 1
    app.run(timeout=30)  # No implicit re-evaluation on an unrelated rerun/tab return.
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1
    app.button[0].click().run(timeout=30)
    fresh = app.session_state["returned_card-a"]
    assert fresh.status == "SHADOW" and fresh.quoted_odds == 4.0
    assert len(calculations) == len(saves) == 2
    assert not any("Eingabe geändert" in value for value in messages(app))


@pytest.mark.parametrize("change", ["bankroll", "confirmation", "clear-bankroll"])
def test_bankroll_or_confirmation_edits_remove_stake_and_do_not_save(side_effects, change):
    calculations, saves = side_effects
    app = start(pending=False)
    before = submit(app, odds="4.00")
    assert before.status == "BET" and before.stake_amount > 0
    assert any("Einsatzvorschlag" in item.value for item in app.caption)
    if change == "bankroll":
        app.number_input[0].set_value(200.0).run(timeout=30)
    elif change == "clear-bankroll":
        app.number_input[0].set_value(None).run(timeout=30)
    else:
        app.checkbox[0].uncheck().run(timeout=30)
    assert_invalidated(app)
    assert not app.success
    assert not any("Einsatzvorschlag" in item.value for item in app.caption)
    assert len(calculations) == len(saves) == 1
    if change == "bankroll":
        app.button[0].click().run(timeout=30)
        after = app.session_state["returned_card-a"]
        assert after.stake_amount == before.stake_amount * 2
        assert len(calculations) == len(saves) == 2


@pytest.mark.parametrize("raw", ["", "   ", "not-a-price", "nan", "inf", "0", "1", "-4", "1e9999"])
def test_invalid_new_or_cleared_quote_never_keeps_a_previous_pass(side_effects, raw):
    calculations, saves = side_effects
    app = start(pending=False)
    assert submit(app, odds="4").status == "BET"
    app.text_input[0].input(raw).run(timeout=30)
    assert_invalidated(app)
    assert not app.success
    assert len(calculations) == len(saves) == 1
    app.button[0].click().run(timeout=30)
    assert not app.exception
    decision = app.session_state["returned_card-a"]
    assert not decision.price_passed and decision.quoted_odds is None
    assert not any("erreicht die Value-Grenze" in value for value in messages(app))
    assert len(calculations) == 2


def test_changing_back_to_old_quote_does_not_resurrect_its_previous_decision(side_effects):
    calculations, saves = side_effects
    app = start()
    submit(app)
    app.text_input[0].input("4").run(timeout=30)
    assert_invalidated(app)
    app.text_input[0].input("1,12").run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1


def test_same_widget_keys_and_input_values_do_not_reuse_a_new_candidate_revision(side_effects):
    calculations, saves = side_effects
    app = start()
    old = submit(app)
    app.session_state["revision_card-a"] = 1
    app.run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1
    app.button[0].click().run(timeout=30)
    new = app.session_state["returned_card-a"]
    assert new.candidate != old.candidate
    assert new.quoted_odds == old.quoted_odds
    assert len(calculations) == len(saves) == 2


@pytest.mark.parametrize("change", ["odds", "bankroll", "confirmation", "candidate"])
def test_two_manual_cards_have_independent_inputs_decisions_and_edit_effects(side_effects, change):
    calculations, saves = side_effects
    app = start(two=True)
    submit(app, key="card-a", odds="1.12")
    second = submit(app, key="card-b", odds="4")
    stored_second = app.session_state["bet_decision_card-b"]
    assert app.session_state["returned_card-a"].quoted_odds == 1.12
    if change == "odds":
        app.text_input(key="bet_odds_card-a").input("4").run(timeout=30)
    elif change == "bankroll":
        app.number_input(key="manual_balance_card-a").set_value(200.0).run(timeout=30)
    elif change == "confirmation":
        app.checkbox(key="bet_confirmed_card-a").uncheck().run(timeout=30)
    else:
        app.session_state["revision_card-a"] = 2
        app.run(timeout=30)
    assert_invalidated(app)
    assert app.session_state["returned_card-b"] == second
    # Existing pending-release rendering appends another reason to its return;
    # preserve each original object against its own exact pre-edit value.
    assert app.session_state["bet_decision_card-b"] == stored_second
    assert len(calculations) == len(saves) == 2


def test_first_edits_and_unchecked_explicit_submit_keep_existing_persistence_rules(side_effects):
    calculations, saves = side_effects
    app = start()
    app.text_input[0].input("4").run(timeout=30)
    app.number_input[0].set_value(200.0).run(timeout=30)
    assert not app.exception and app.session_state["returned_card-a"] is None
    assert calculations == [] and saves == []
    app.button[0].click().run(timeout=30)
    assert app.session_state["returned_card-a"].status == "PRICE_REQUIRED"
    assert len(calculations) == 1 and saves == []
    app.checkbox[0].check().run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == 1 and saves == []
    app.button[0].click().run(timeout=30)
    assert app.session_state["returned_card-a"].status == "SHADOW"
    assert len(calculations) == 2 and len(saves) == 1


def test_unchanged_reruns_preserve_exact_decision_without_extra_calculation_or_save(side_effects):
    calculations, saves = side_effects
    app = start()
    decision = submit(app)
    app.run(timeout=30)
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state["returned_card-a"] == decision
    assert len(calculations) == len(saves) == 1
    rendered = messages(app) + [item.value for item in app.caption]
    assert any("1.12" in value or "1,12" in value for value in rendered)


def test_a_legacy_cached_decision_without_exact_input_snapshot_is_not_certified(side_effects):
    calculations, saves = side_effects
    app = start()
    submit(app, odds="4")
    for key in list(app.session_state.filtered_state):
        if key.startswith("bet_checked_inputs_"):
            del app.session_state[key]
    app.run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1


@pytest.mark.parametrize("input_name", ["quote", "bankroll", "confirmation"])
def test_an_edit_and_revert_still_needs_an_explicit_new_check(side_effects, input_name):
    calculations, saves = side_effects
    app = start(pending=False)
    assert submit(app, odds="4").status == "BET"
    if input_name == "quote":
        app.text_input[0].input("4.00").run(timeout=30)
        assert_invalidated(app)
        app.text_input[0].input("4").run(timeout=30)
    elif input_name == "bankroll":
        app.number_input[0].set_value(200.0).run(timeout=30)
        assert_invalidated(app)
        app.number_input[0].set_value(100.0).run(timeout=30)
    else:
        app.checkbox[0].uncheck().run(timeout=30)
        assert_invalidated(app)
        app.checkbox[0].check().run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1


def test_cleared_bankroll_is_not_refilled_and_explicit_check_cannot_reuse_old_stake(side_effects):
    calculations, saves = side_effects
    app = start(pending=False)
    assert app.number_input[0].value == 100.0
    before = submit(app, odds="4")
    app.number_input[0].set_value(None).run(timeout=30)
    assert_invalidated(app)
    assert app.number_input[0].value is None
    assert len(calculations) == len(saves) == 1
    app.run(timeout=30)
    assert app.number_input[0].value is None
    assert_invalidated(app)
    app.button[0].click().run(timeout=30)
    assert not app.exception
    after = app.session_state["returned_card-a"]
    assert after.status == "NO_BET" and after.quoted_odds is None
    assert after.stake_amount == 0 < before.stake_amount
    assert calculations[-1][2] is None and len(calculations) == 2
    assert not any("erreicht die Value-Grenze" in value for value in messages(app))
    assert not any("Einsatzvorschlag" in item.value for item in app.caption)


def test_input_binding_rejects_programmatic_non_widget_state_replacement(side_effects):
    calculations, saves = side_effects
    app = start()
    submit(app)
    # This path has no input widget callback: the full stored input snapshot
    # must independently catch a changed state on the next ordinary rerun.
    app.session_state["bet_odds_card-a"] = "4"
    app.run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1
