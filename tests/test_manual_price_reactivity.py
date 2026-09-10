"""Real Streamlit reruns: edits invalidate, explicit checks alone have effects."""
from dataclasses import replace
from copy import deepcopy

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


def start(*, two=False, pending=True, surface="popover", initial_values=None):
    app = AppTest.from_function(_manual_price_app)
    app.session_state["two_cards"] = two
    app.session_state["pending"] = pending
    app.session_state["surface"] = surface
    for key, value in (initial_values or {}).items():
        app.session_state[key] = value
    app.run(timeout=30)
    assert not app.exception
    return app


def submit(app, *, key="card-a", odds="1,12", bankroll=100.0, confirmed=True):
    # None requires a preserved nullable initial state. Actual user clearing is
    # a present empty string, not an absent WidgetState with the old default.
    app.text_input(key="bet_odds_" + key).input(odds)
    app.text_input(key="manual_balance_" + key).input(
        None if bankroll is None else str(bankroll)
    )
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
    assert not app.text_input(key="manual_balance_card-a").proto.form_id
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
        app.text_input(key="manual_balance_card-a").input("200.0").run(timeout=30)
    elif change == "clear-bankroll":
        app.text_input(key="manual_balance_card-a").input("").run(timeout=30)
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
        app.text_input(key="manual_balance_card-a").input("200.0").run(timeout=30)
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
    app.text_input(key="manual_balance_card-a").input("200.0").run(timeout=30)
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
    rendered = messages(app) + [item.value for item in app.caption] + checked_text(app)
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
        app.text_input(key="manual_balance_card-a").input("200.0").run(timeout=30)
        assert_invalidated(app)
        app.text_input(key="manual_balance_card-a").input("100.0").run(timeout=30)
    else:
        app.checkbox[0].uncheck().run(timeout=30)
        assert_invalidated(app)
        app.checkbox[0].check().run(timeout=30)
    assert_invalidated(app)
    assert len(calculations) == len(saves) == 1


def test_cleared_bankroll_is_not_refilled_and_explicit_check_cannot_reuse_old_stake(side_effects):
    calculations, saves = side_effects
    app = start(pending=False)
    assert app.text_input(key="manual_balance_card-a").proto.default == "100.00"
    before = submit(app, odds="4")
    app.text_input(key="manual_balance_card-a").input("").run(timeout=30)
    assert_invalidated(app)
    assert app.text_input(key="manual_balance_card-a").value == ""
    assert len(calculations) == len(saves) == 1
    app.run(timeout=30)
    assert app.text_input(key="manual_balance_card-a").value == ""
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


@pytest.fixture
def rendered_elements(monkeypatch):
    """Observe the actual NewElement boundary, not AppTest's server-side value."""
    import streamlit.delta_generator as delta_generator

    elements = []
    enqueue = delta_generator._enqueue_message

    def record(message):
        if message.HasField("delta") and message.delta.HasField("new_element"):
            elements.append(deepcopy(message.delta.new_element))
        return enqueue(message)

    monkeypatch.setattr(delta_generator, "_enqueue_message", record)
    return elements


def checked_text(app):
    return [item.value for item in app.text if item.value.startswith("Letzte Prüfung:")]


@pytest.mark.parametrize("surface", ["popover", "expander"])
def test_initial_bankroll_is_a_durable_visible_protocol_default_not_a_one_shot_seed(
    side_effects, rendered_elements, surface,
):
    app = start(two=True, surface=surface)
    for _ in range(2):
        balances = []
        for element in rendered_elements:
            kind = element.WhichOneof("type")
            if kind in {"number_input", "text_input"}:
                widget = getattr(element, kind)
                if widget.label == "Aktuelles Wettguthaben":
                    balances.append((element, widget))
        assert len(balances) == 2
        for element, widget in balances:
            assert widget.HasField("default"), "A Python-only seed is not a visible default"
            assert widget.default == "100.00"
            assert not widget.set_value
            assert not element.has_one_shot_effect
            assert not widget.form_id
        rendered_elements.clear()
        app.run(timeout=30)
        assert not app.exception
    assert side_effects == ([], [])


@pytest.mark.parametrize(
    "odds,bankroll,confirmed,expected",
    [
        ("1,12", 100.0, True, 'Quote "1,12" · Wettguthaben "100.0" € · Auswahl bestätigt: ja.'),
        ("  1.1200  ", 100.0, True, 'Quote "  1.1200  " · Wettguthaben "100.0" € · Auswahl bestätigt: ja.'),
        ("bad-price", 100.0, True, 'Quote "bad-price" · Wettguthaben "100.0" € · Auswahl bestätigt: ja.'),
        ("", 100.0, True, 'Quote "" · Wettguthaben "100.0" € · Auswahl bestätigt: ja.'),
        (None, 100.0, True, 'Quote leer (kein Wert) · Wettguthaben "100.0" € · Auswahl bestätigt: ja.'),
        ("1.12", None, True, 'Quote "1.12" · Wettguthaben leer (kein Wert) € · Auswahl bestätigt: ja.'),
        ("4", 100.0, False, 'Quote "4" · Wettguthaben "100.0" € · Auswahl bestätigt: nein.'),
    ],
)
def test_every_explicit_result_identifies_its_raw_snapshot_even_when_invalid(
    side_effects, odds, bankroll, confirmed, expected,
):
    initial_values = {}
    if odds is None:
        initial_values["bet_odds_card-a"] = None
    if bankroll is None:
        initial_values["manual_balance_card-a"] = None
    app = start(initial_values=initial_values)
    decision = submit(app, odds=odds, bankroll=bankroll, confirmed=confirmed)
    assert decision is not None
    assert checked_text(app) == ["Letzte Prüfung: " + expected]
    app.run(timeout=30)
    assert checked_text(app) == ["Letzte Prüfung: " + expected]
    assert len(side_effects[0]) == 1


def test_literal_bankroll_clear_is_an_empty_wire_string_not_an_absent_number(side_effects):
    from streamlit.elements.widgets.text_widgets import TextInputSerde

    calculations, saves = side_effects
    app = start(two=True, pending=False)
    balance = next(item for item in app.text_input if item.label == "Aktuelles Wettguthaben")
    assert balance.proto.default == "100.00"
    submit(app, odds="4")
    second = submit(app, key="card-b", odds="4")
    stored_second = app.session_state["bet_decision_card-b"]
    balance = app.text_input(key="manual_balance_card-a").input("")
    wire = balance._widget_state
    assert wire.WhichOneof("value") == "string_value"
    assert wire.string_value == ""
    # The actual owning serde does not replace a present empty string by 100.
    assert TextInputSerde("100.00").deserialize(wire.string_value) == ""
    balance.run(timeout=30)
    assert_invalidated(app)
    assert app.text_input(key="manual_balance_card-a").value == ""
    assert app.session_state["returned_card-b"] == second
    assert app.session_state["bet_decision_card-b"] == stored_second
    assert len(calculations) == len(saves) == 2
    app.run(timeout=30)
    assert app.text_input(key="manual_balance_card-a").value == ""
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert calculations[-1][2] is None
    assert app.session_state["returned_card-a"].stake_amount == 0
    assert 'Wettguthaben "" €' in checked_text(app)[0]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", None), ("  ", None), ("bad-balance", None), ("0", None),
        ("0.999", None), ("-1", None), ("nan", None), ("inf", None),
        ("1e9999", None), ("1_000", None), ("1 000", None),
        ("1", 1.0), ("1,5", 1.5), (" 100.00 ", 100.0),
        ("+100", 100.0), ("1e2", 100.0),
    ],
)
def test_raw_bankroll_is_preserved_but_only_finite_values_at_least_one_are_evaluated(
    side_effects, raw, expected,
):
    app = start(pending=False)
    # This must be a real text widget: numerical AppTest assignment would not
    # exercise the browser's empty-string delivery or malformed spelling.
    balance = next(item for item in app.text_input if item.label == "Aktuelles Wettguthaben")
    balance.input(raw)
    app.text_input(key="bet_odds_card-a").input("4")
    app.checkbox[0].check()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert side_effects[0][-1][2] == expected
    snapshot = app.session_state["bet_checked_inputs_card-a"]
    assert snapshot.raw_bankroll == raw and snapshot.bankroll == expected
    assert len(checked_text(app)) == 1
    assert f'Wettguthaben "{raw}" €' in checked_text(app)[0]
    if expected is None:
        assert app.session_state["returned_card-a"].stake_amount == 0
        assert not app.success


def test_bankroll_spelling_edit_and_revert_cannot_resurrect_a_checked_snapshot(side_effects):
    app = start(pending=False)
    submit(app, odds="4")
    balance = next(item for item in app.text_input if item.label == "Aktuelles Wettguthaben")
    balance.input("100,00").run(timeout=30)
    assert_invalidated(app)
    assert not checked_text(app)
    app.text_input(key="manual_balance_card-a").input("100.0").run(timeout=30)
    assert_invalidated(app)
    assert not checked_text(app)
    assert len(side_effects[0]) == len(side_effects[1]) == 1


@pytest.mark.parametrize("field", ["quote", "bankroll"])
def test_checked_raw_input_is_plain_text_not_html_or_markdown(side_effects, rendered_elements, field):
    app = start()
    raw = '[not a link](https://example.invalid) <b>not bold</b>\n\t'
    if field == "quote":
        submit(app, odds=raw)
        expected = (
            'Letzte Prüfung: Quote "[not a link](https://example.invalid) '
            '<b>not bold</b>\\n\\t" · Wettguthaben "100.0" € · Auswahl bestätigt: ja.'
        )
    else:
        submit(app, odds="4", bankroll=raw)
        expected = (
            'Letzte Prüfung: Quote "4" · Wettguthaben "[not a link](https://example.invalid) '
            '<b>not bold</b>\\n\\t" € · Auswahl bestätigt: ja.'
        )
    assert checked_text(app) == [expected]
    assert any(element.HasField("text") and element.text.body == expected for element in rendered_elements)
    assert not any(element.HasField("markdown") and raw in element.markdown.body for element in rendered_elements)


def test_untouched_visible_default_is_the_actual_explicitly_checked_bankroll(side_effects):
    app = start()
    app.text_input(key="bet_odds_card-a").input("1.12")
    app.checkbox[0].check()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert side_effects[0][-1][2] == 100.0
    snapshot = app.session_state["bet_checked_inputs_card-a"]
    assert snapshot.raw_bankroll == "100.00" and snapshot.bankroll == 100.0
    assert 'Wettguthaben "100.00" €' in checked_text(app)[0]


def test_raw_bankroll_spelling_replacement_without_callback_still_invalidates(side_effects):
    app = start()
    submit(app)
    app.session_state["manual_balance_card-a"] = "100.00"
    app.run(timeout=30)
    assert_invalidated(app)
    assert not checked_text(app)
    assert len(side_effects[0]) == len(side_effects[1]) == 1


@pytest.mark.parametrize(
    "previous,raw,parsed",
    [(42.25, "42.25", 42.25), (0.0, "0.0", None), (-4.0, "-4.0", None),
     (float("inf"), "inf", None), (None, None, None)],
)
def test_legacy_numeric_or_missing_bankroll_is_not_fabricated_as_one_hundred(
    side_effects, previous, raw, parsed,
):
    app = start(initial_values={"manual_balance_card-a": previous})
    assert app.text_input(key="manual_balance_card-a").value == raw
    app.text_input(key="bet_odds_card-a").input("4")
    app.checkbox[0].check()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert side_effects[0][-1][2] == parsed
    snapshot = app.session_state["bet_checked_inputs_card-a"]
    assert snapshot.raw_bankroll == raw and snapshot.bankroll == parsed
