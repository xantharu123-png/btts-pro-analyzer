"""Same-call internal originals, not an empirical context approval."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import timedelta
import json

import pytest

import sports_prematch as model
from test_sports_prematch import NOW, event, history


SPORTS = ("basketball", "ice_hockey")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@pytest.mark.parametrize("sport", SPORTS)
def test_capture_uses_actual_single_target_computation_and_preserves_output(sport, monkeypatch):
    target, rows = event(sport), history(sport)
    expected = model.predict_prematch(sport, target, rows, NOW)
    fits, predictions, originals = [], [], []
    real_fit, real_predict = model._fit, model._predict

    def fitted(which, matches):
        fits.append((which, matches))
        return real_fit(which, matches)

    def predicted(fit, home, away, neutral):
        output = real_predict(fit, home, away, neutral)
        predictions.append((fit, output))
        return output

    monkeypatch.setattr(model, "_fit", fitted)
    monkeypatch.setattr(model, "_predict", predicted)
    result = model.predict_prematch(sport, target, iter(rows), NOW, original_capture=originals.append)
    assert encoded(result.to_dict()) == encoded(expected.to_dict())
    assert len(originals) == 1
    original = originals[0]
    assert original.prediction is result
    assert original.as_of == NOW
    assert original.sport == sport
    assert original.input_hash == result.input_hash
    assert original.raw_event == target
    assert original.raw_history == tuple(rows)
    assert len(original.matches) == result.training_games == 84
    assert sum(which == sport and matches == original.matches for which, matches in fits) == 1
    target_predictions = [item for fit, item in predictions if fit is original.fitted]
    assert len(target_predictions) == 1
    direct_p, direct_values = target_predictions[0]
    assert original.probability.hex() == direct_p.hex() == result.p_home.hex()
    assert original.values.keys() == direct_values.keys()
    for key, value in direct_values.items():
        assert float(original.values[key]).hex() == float(value).hex()
    if sport == "basketball":
        assert original.values["expected_margin"] != round(original.values["expected_margin"], 2)
    else:
        assert original.values["p_home_regulation"].hex() == result.p_home_regulation.hex()
        assert original.values["p_draw_regulation"].hex() == result.p_draw_regulation.hex()


@pytest.mark.parametrize("sport", SPORTS)
def test_original_is_detached_and_core_parts_cannot_be_reassigned(sport):
    target, rows = event(sport), history(sport)
    before_target, before_rows = deepcopy(target), deepcopy(rows)
    captured = []
    result = model.predict_prematch(sport, target, rows, NOW, original_capture=captured.append)
    original = captured[0]
    before_prediction = encoded(result.to_dict())
    target["home_team_id"] = "999"
    rows[0]["home_score"] = 999
    assert original.raw_event == before_target
    assert original.raw_history == tuple(before_rows)
    original.raw_event["home_team_id"] = "777"
    original.raw_history[0]["home_score"] = 777
    assert target["home_team_id"] == "999" and rows[0]["home_score"] == 999
    assert encoded(result.to_dict()) == before_prediction
    with pytest.raises(FrozenInstanceError):
        original.input_hash = "0" * 64
    with pytest.raises(TypeError):
        original.values["expected_margin"] = 3.0
    with pytest.raises(FrozenInstanceError):
        original.identity.home = "id:777"


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("defect", ["missing_history", "started", "no_identity", "disconnected"])
def test_missing_original_remains_absent_and_records_actual_missing_state(sport, defect):
    target, rows = event(sport), history(sport)
    if defect == "missing_history":
        rows = rows[:3]
    elif defect == "started":
        target["starts_at"] = (NOW - timedelta(seconds=1)).isoformat()
    elif defect == "no_identity":
        target["provider"] = ""
    else:
        target["home_team_id"] = "999"
    expected = model.predict_prematch(sport, target, rows, NOW)
    originals = []
    result = model.predict_prematch(sport, target, rows, NOW, original_capture=originals.append)
    assert result.p_home is None
    assert encoded(result.to_dict()) == encoded(expected.to_dict())
    assert len(originals) == 1 and originals[0].probability is None
    assert originals[0].prediction is result and originals[0].prediction.missing


def test_hockey_without_native_ot_basis_does_not_export_an_invented_distribution():
    originals = []
    result = model.predict_prematch("ice_hockey", event("ice_hockey", neutral_site=True),
                                    history("ice_hockey"), NOW, original_capture=originals.append)
    assert result.p_home is None
    assert originals[0].fitted is not None
    assert originals[0].probability is None and dict(originals[0].values) == {}


@pytest.mark.parametrize("sport", SPORTS)
def test_actual_risk_adapter_passes_through_same_original_without_second_target_call(sport, monkeypatch):
    from riskobet_candidates import adapt_research_matchwinner
    target = event(sport, source_observed_at=NOW.isoformat())
    rows = history(sport)
    expected = adapt_research_matchwinner(sport, target, rows, modeled_at=NOW)
    original_predict, calls = model.predict_prematch, []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original_predict(*args, **kwargs)

    monkeypatch.setattr(model, "predict_prematch", spy)
    captured = []
    result = adapt_research_matchwinner(sport, target, rows, modeled_at=NOW,
                                       original_capture=captured.append)
    assert len(calls) == len(captured) == 1
    assert result.snapshot.to_dict() == expected.snapshot.to_dict()
    assert [c.to_dict() for c in result.candidates] == [c.to_dict() for c in expected.candidates]
    assert captured[0].input_hash == captured[0].prediction.input_hash


def test_callback_error_is_not_swallowed_as_a_missing_model():
    def broken(_):
        raise RuntimeError("internal collector failed")

    with pytest.raises(RuntimeError, match="internal collector failed"):
        model.predict_prematch("basketball", event(), history(), NOW, original_capture=broken)


def test_collector_is_explicitly_outside_cricket_scope():
    with pytest.raises(ValueError, match="basketball.*ice_hockey"):
        model.predict_prematch("cricket", event("cricket"), history("cricket"), NOW,
                               original_capture=lambda _: pytest.fail("Cricket collector invoked"))


@pytest.mark.parametrize("sport", SPORTS)
def test_invalid_collector_rejected_before_any_model_fit(sport, monkeypatch):
    monkeypatch.setattr(model, "_fit", lambda *_: pytest.fail("invalid collector fitted a model"))
    with pytest.raises(ValueError, match="callable"):
        model.predict_prematch(sport, event(sport), history(sport), NOW, original_capture={})


@pytest.mark.parametrize("sport", SPORTS)
def test_prices_never_change_actual_model_identity_or_numbers(sport):
    target, rows = event(sport), history(sport)
    original, repriced = [], []
    model.predict_prematch(sport, target, rows, NOW, original_capture=original.append)
    target.update(odds=900., bookmaker="different", minimum_odds=0.01)
    for row in rows:
        row["odds"] = 0.0
    model.predict_prematch(sport, target, rows, NOW, original_capture=repriced.append)
    a, b = original[0], repriced[0]
    assert a.input_hash == b.input_hash
    assert a.identity == b.identity and a.matches == b.matches and a.fitted == b.fitted
    assert a.probability.hex() == b.probability.hex()
    assert dict(a.values) == dict(b.values)
    assert encoded(a.prediction.to_dict()) == encoded(b.prediction.to_dict())
