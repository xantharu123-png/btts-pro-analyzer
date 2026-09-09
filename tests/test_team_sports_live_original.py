"""Actual same-call captures; synthetic source inputs, not source certification."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import sys

import pytest

import sports_prematch as old
from context_models.contracts import ContextContractError, canonical_timestamp, digest, validate_base_distribution
from model_artifacts import canonical_bytes
from test_sports_prematch import NOW, event as old_event, history as old_history

SPORTS = ("basketball", "ice_hockey")


def api():
    from context_models import team_sports_live
    return team_sports_live


def raw_inputs(sport):
    target = old_event(sport, provider_event_id="401999999" if sport == "basketball" else "2025020999")
    rows = old_history(sport)
    for i, row in enumerate(rows):
        row["provider_event_id"] = str((401800000 if sport == "basketball" else 2025020000) + i)
    if sport == "basketball":
        scope = dict(season="2026", context_rules=dict(regulation_minutes=48, regulation_periods=4, overtime_period_minutes=5))
    else:
        scope = dict(season=20252026, context_rule_version="nhl-2025-26-rule84")
    target.update(scope)
    for row in rows:
        row.update(deepcopy(scope))
    return target, rows


def native_event(sport):
    source = "espn" if sport == "basketball" else "nhl"
    return dict(event_key=f"{source}:{sport}:" + ("401999999" if sport == "basketball" else "2025020999"),
        sport=sport, competition="nba" if sport == "basketball" else "nhl",
        format="nba_reg48_including_ot" if sport == "basketball" else "nhl_reg60_regular_ot_so",
        home_id=f"{source}:{sport}:team:1", away_id=f"{source}:{sport}:team:8",
        scheduled_start=canonical_timestamp(NOW + timedelta(hours=6)),
        schedule_revision=digest({"source_test_revision": 1}), status="scheduled")


def capture(sport, *, target=None, rows=None):
    defaults = raw_inputs(sport)
    target = defaults[0] if target is None else target
    rows = defaults[1] if rows is None else rows
    originals = []
    prediction = old.predict_prematch(sport, target, rows, NOW, original_capture=originals.append)
    return originals[0], prediction


def build(sport, original=None, **kwargs):
    original = capture(sport)[0] if original is None else original
    return getattr(api(), f"build_{'basketball' if sport == 'basketball' else 'hockey'}_live_original")(
        original, event=kwargs.pop("event", native_event(sport)), **kwargs)


@pytest.mark.parametrize("sport", SPORTS)
def test_builder_uses_captured_fit_and_exact_original_law_without_target_replay(sport, monkeypatch):
    original, prediction = capture(sport)
    frozen = canonical_bytes(prediction.to_dict())
    for name in ("_fit", "_predict", "predict_prematch", "minimize"):
        monkeypatch.setattr(old, name, lambda *a, **k: pytest.fail("second target fit/predict"))
    value = build(sport, original)
    assert value.base is not None
    assert value.context_unavailable_reason == "native-receipts-unresolved"
    assert value.base["history_refs"] == []
    assert canonical_bytes(api().validate_team_sport_live_origin(value.base, native_event(sport))) == canonical_bytes(value.base)
    assert canonical_bytes(validate_base_distribution(value.base)) == canonical_bytes(value.base)
    assert canonical_bytes(prediction.to_dict()) == frozen
    winner = "home_win" if sport == "basketball" else "home_inclusive"
    other = "away_win" if sport == "basketball" else "away_inclusive"
    assert value.base["markets"][winner].hex() == prediction.p_home.hex()
    assert value.base["markets"][other].hex() == prediction.p_away.hex()
    if sport == "basketball":
        assert canonical_bytes(value.base["params"]) == canonical_bytes(dict(original.values))
        assert min(value.original["auxiliary_reference"]["influences"]) < 0
    else:
        assert value.base["params"]["home_lambda"].hex() == original.values["expected_home_goals"].hex()
        assert value.base["params"]["away_lambda"].hex() == original.values["expected_away_goals"].hex()
        assert value.base["markets"]["home_reg"].hex() == prediction.p_home_regulation.hex()
        assert value.base["params"]["overtime_home_probability"] == original.fitted.overtime_home_rate


@pytest.mark.parametrize("sport", SPORTS)
def test_actual_cold_target_fit_once_then_build_inside_callback(sport, monkeypatch):
    target, rows = raw_inputs(sport)
    old._fit.cache_clear()
    old._evaluate.cache_clear()
    real_fit, real_predict, calls, target_calls = old._fit, old._predict, [], []
    def fit(which, matches):
        calls.append((which, matches))
        return real_fit(which, matches)
    def predict(*args):
        target_calls.append(args)
        return real_predict(*args)
    monkeypatch.setattr(old, "_fit", fit)
    monkeypatch.setattr(old, "_predict", predict)
    captures = []
    def collect(original):
        prior = len(calls), len(target_calls)
        captures.append(build(sport, original))
        assert prior == (len(calls), len(target_calls))
    result = old.predict_prematch(sport, target, rows, NOW, original_capture=collect)
    assert result.p_home is not None and len(captures) == 1
    assert sum(len(matches) == 84 for _, matches in calls) == 1
    assert any(len(matches) < 84 for _, matches in calls)  # legitimate past folds retained


@pytest.mark.parametrize("sport", SPORTS)
def test_explicit_offline_replay_is_separate_and_fresh(sport, monkeypatch):
    value = build(sport)
    original_fit, calls = old._fit.__wrapped__, []
    def replay(which, matches):
        calls.append((which, len(matches)))
        return original_fit(which, matches)
    monkeypatch.setattr(old, "_fit", replay)
    actual = api().replay_team_sport_live_origin(value.base)
    assert canonical_bytes(actual) == canonical_bytes(value.base)
    assert calls == [(sport, 84)]


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("field", ["event_key", "home_id", "away_id", "scheduled_start", "schedule_revision", "format", "status"])
def test_complete_expected_event_binding(sport, field):
    value = build(sport)
    event = native_event(sport)
    event[field] = {"scheduled_start": canonical_timestamp(NOW + timedelta(hours=7)), "status": "cancelled"}.get(field, event[field] + "-different")
    with pytest.raises(ContextContractError):
        api().validate_team_sport_live_origin(value.base, event)


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("field", ["model_hash", "cutoff", "params", "markets", "native_event", "input_hash", "fit", "raw_history"])
def test_original_byte_mutations_are_not_accepted(sport, field):
    base = deepcopy(build(sport).base)
    origin = base["reference_weights"]["original"]
    if field == "model_hash": base[field] = "a" * 64
    elif field == "cutoff": base[field] = canonical_timestamp(NOW - timedelta(microseconds=1))
    elif field in {"params", "markets"}:
        key = next(iter(base[field]))
        base[field][key] = math.nextafter(base[field][key], math.inf)
    elif field == "native_event": origin["event"]["schedule_revision"] = "a" * 64
    elif field == "input_hash": origin["model"]["input_hash"] = "a" * 64
    elif field == "fit": origin["model"]["fit"]["coefficients"][0] += .25
    else: origin["inputs"]["history"][0]["home_score"] += 1
    with pytest.raises(ContextContractError):
        validate_base_distribution(base)


@pytest.mark.parametrize("sport", SPORTS)
def test_missing_native_metadata_does_not_destroy_original(sport):
    original, prediction = capture(sport)
    value = build(sport, original, event=None)
    assert value.base is None
    assert value.context_unavailable_reason == "native-event-unavailable"
    assert value.original["outputs"]["p_home"].hex() == prediction.p_home.hex()
    target, rows = raw_inputs(sport)
    target.pop("neutral_site")
    partial = build(sport, capture(sport, target=target, rows=rows)[0])
    assert partial.base is not None and partial.original["native_scope"] is None
    assert partial.context_unavailable_reason == "native-neutral-site-unavailable"
    assert "neutral_site" not in partial.original["inputs"]["event"]
    assert partial.original["model"]["identity"]["neutral"] is False  # inherited model default, not native fact


@pytest.mark.parametrize("sport", SPORTS)
def test_unavailable_model_stays_missing_not_fifty_percent(sport):
    original, prediction = capture(sport, rows=[])
    value = build(sport, original)
    assert value.base is None and prediction.p_home is None
    assert value.original["outputs"]["p_home"] is None
    assert value.context_unavailable_reason == "original-model-unavailable"


def test_new_hockey_season_is_not_an_old_rule_approval():
    target, rows = raw_inputs("ice_hockey")
    target.update(season=20262027, context_rule_version="nhl-2026-27-rule84")
    value = build("ice_hockey", capture("ice_hockey", target=target, rows=rows)[0])
    assert value.base is not None
    assert value.original["native_scope"] is None
    assert value.context_unavailable_reason == "native-scope-unreviewed-or-missing"


@pytest.mark.parametrize("sport", SPORTS)
def test_prices_are_outside_both_new_original_and_model_identity(sport):
    target, rows = raw_inputs(sport)
    before = build(sport, capture(sport, target=target, rows=rows)[0])
    target.update(odds=3.5, bookmaker="any", minimum_odds=1.01, price_status="UNAVAILABLE")
    for row in rows: row.update(odds=900, bookmaker="other")
    after = build(sport, capture(sport, target=target, rows=rows)[0])
    assert canonical_bytes(before.original) == canonical_bytes(after.original)
    assert canonical_bytes(before.base) == canonical_bytes(after.base)


@pytest.mark.parametrize("sport", SPORTS)
def test_reference_links_never_self_certify_source_resolution(sport):
    refs = dict(schema=1, kind="team-sports-live-receipt-refs-v1", event_receipt="a" * 64,
        history_receipts=[dict(input_index=0, receipt="b" * 64)], artifact_refs=["c" * 64])
    value = build(sport, receipt_binding=refs)
    assert value.context_unavailable_reason == "native-receipts-unresolved"
    assert value.base["history_refs"] == []
    refs["verified"] = True
    with pytest.raises(ContextContractError): build(sport, receipt_binding=refs)


@pytest.mark.parametrize("defect", ["bool_index", "negative_index", "out_of_range", "duplicate_index", "bad_ref", "missing_member"])
def test_binding_schema_is_closed_and_indexes_are_real(defect):
    refs = dict(schema=1, kind="team-sports-live-receipt-refs-v1", event_receipt=None,
        history_receipts=[dict(input_index=0, receipt="b" * 64)], artifact_refs=[])
    if defect == "bool_index": refs["history_receipts"][0]["input_index"] = True
    if defect == "negative_index": refs["history_receipts"][0]["input_index"] = -1
    if defect == "out_of_range": refs["history_receipts"][0]["input_index"] = 84
    if defect == "duplicate_index": refs["history_receipts"] *= 2
    if defect == "bad_ref": refs["event_receipt"] = "not-a-digest"
    if defect == "missing_member": refs.pop("artifact_refs")
    with pytest.raises(ContextContractError): build("basketball", receipt_binding=refs)


def test_frozen_default_cricket_and_existing_risk_outputs_remain_exact(monkeypatch):
    from riskobet_candidates import adapt_research_matchwinner
    raw = Path(__file__).parent / "fixtures/context/basketball/sports_prematch_legacy_0d000f6.py"
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == "b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677"
    spec = importlib.util.spec_from_file_location("p4a_legacy_model", raw)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    for form in ("t20", "odi", "test"):
        target = old_event("cricket", format=form, source_observed_at=NOW.isoformat())
        rows = [{**r, "format": form} for r in old_history("cricket")]
        assert canonical_bytes(old.predict_prematch("cricket", target, rows, NOW).to_dict()) == canonical_bytes(legacy.predict_prematch("cricket", target, rows, NOW).to_dict())
        before = adapt_research_matchwinner("cricket", target, rows, modeled_at=NOW)
        with monkeypatch.context() as local:
            local.setattr(old, "predict_prematch", legacy.predict_prematch)
            after = adapt_research_matchwinner("cricket", target, rows, modeled_at=NOW)
        assert canonical_bytes(before.snapshot.to_dict()) == canonical_bytes(after.snapshot.to_dict())
        assert canonical_bytes([r.to_dict() for r in before.candidates]) == canonical_bytes([r.to_dict() for r in after.candidates])


@pytest.mark.parametrize("sport", SPORTS)
def test_noncanonical_top_level_clock_is_not_normalized_away(sport):
    base = deepcopy(build(sport).base)
    base["cutoff"] = NOW.isoformat()
    with pytest.raises(ContextContractError): validate_base_distribution(base)
    event = native_event(sport)
    event["scheduled_start"] = (NOW + timedelta(hours=6)).isoformat()
    with pytest.raises(ContextContractError): build(sport, event=event)


@pytest.mark.parametrize("sport", SPORTS)
def test_missing_native_target_id_does_not_erase_pure_capture(sport):
    target, rows = raw_inputs(sport)
    target["provider_event_id"] = "legacy-nonnative-match"
    original, prediction = capture(sport, target=target, rows=rows)
    value = build(sport, original)
    assert value.base is None
    assert value.context_unavailable_reason == "native-target-event-identity-unavailable"
    assert value.original["outputs"]["p_home"] == prediction.p_home


@pytest.mark.parametrize("sport", SPORTS)
def test_missing_native_teams_do_not_turn_names_into_ids(sport):
    target, rows = raw_inputs(sport)
    for row in [target, *rows]:
        row.pop("home_team_id")
        row.pop("away_team_id")
    original, prediction = capture(sport, target=target, rows=rows)
    assert prediction.p_home is not None
    value = build(sport, original)
    assert value.base is None
    assert value.context_unavailable_reason == "native-target-team-identity-unavailable"
    assert value.original["outputs"]["p_home"] == prediction.p_home


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("field", ["sport", "kind", "schema"])
def test_malformed_origin_tag_is_a_typed_contract_error(sport, field):
    value = deepcopy(build(sport).original)
    value[field] = []
    with pytest.raises(ContextContractError): api().validate_captured_team_sport_original(value)


@pytest.mark.parametrize("sport", SPORTS)
def test_return_payloads_are_detached_from_each_other_and_input(sport):
    original, prediction = capture(sport)
    expected = canonical_bytes(prediction.to_dict())
    value = build(sport, original)
    frozen_base = canonical_bytes(value.base)
    value.original["inputs"]["event"]["home_team_id"] = "777"
    assert canonical_bytes(value.base) == frozen_base
    assert original.raw_event["home_team_id"] == "1"
    assert canonical_bytes(prediction.to_dict()) == expected
    with pytest.raises(FrozenInstanceError): value.base = {}


@pytest.mark.parametrize("sport", SPORTS)
def test_receipt_links_change_capture_not_the_original_model_hash(sport):
    before = build(sport)
    refs = dict(schema=1, kind="team-sports-live-receipt-refs-v1", event_receipt="a"*64,
        history_receipts=[], artifact_refs=[])
    after = build(sport, receipt_binding=refs)
    assert before.base["model_hash"] == after.base["model_hash"]
    assert canonical_bytes(before.base["params"]) == canonical_bytes(after.base["params"])
    assert canonical_bytes(before.base["markets"]) == canonical_bytes(after.base["markets"])
    assert digest(before.original) != digest(after.original)


@pytest.mark.parametrize("sport", SPORTS)
def test_native_alias_known_contradictions_are_not_soft_unavailable(sport):
    original, _ = capture(sport)
    target = native_event(sport)
    target["home_id"], target["away_id"] = target["away_id"], target["home_id"]
    with pytest.raises(ContextContractError): build(sport, original, event=target)
    mutated = replace(original, raw_event={**original.raw_event, "home_team_id": "8", "away_team_id": "1"})
    with pytest.raises(ContextContractError): build(sport, mutated)


def test_hockey_preseason_and_missing_ot_or_neutral_original_are_not_repurposed():
    target, rows = raw_inputs("ice_hockey")
    target["game_type"] = 1
    for row in rows: row["game_type"] = 1
    original, prediction = capture("ice_hockey", target=target, rows=rows)
    assert prediction.p_home is not None
    value = build("ice_hockey", original)
    assert value.base is None and value.context_unavailable_reason == "native-format-unsupported"
    target, rows = raw_inputs("ice_hockey")
    target["neutral_site"] = True
    original, prediction = capture("ice_hockey", target=target, rows=rows)
    value = build("ice_hockey", original)
    assert value.base is None and prediction.p_home is None
    assert value.original["outputs"]["values"] == {}
    target, rows = raw_inputs("ice_hockey")
    for row in rows:
        row.update(home_score=3, away_score=1, winner_side="home", last_period_type="REG")
    original, prediction = capture("ice_hockey", target=target, rows=rows)
    assert original.fitted is not None and original.fitted.overtime_home_rate is None
    value = build("ice_hockey", original)
    assert value.base is None and value.original["outputs"]["p_home"] is None


@pytest.mark.parametrize("sport", SPORTS)
def test_no_free_reference_kind_or_original_version_can_bypass_family(sport):
    base = deepcopy(build(sport).base)
    base["version"] = "another-live-version"
    with pytest.raises(ContextContractError): validate_base_distribution(base)
    base = deepcopy(build(sport).base)
    base["reference_weights"]["kind"] = "hockey-live-poisson-origin-v1" if sport == "basketball" else "basketball-live-margin-origin-v1"
    with pytest.raises(ContextContractError): validate_base_distribution(base)
    base = deepcopy(build(sport).base)
    base["reference_weights"]["original"]["source_resolution"] = "verified"
    with pytest.raises(ContextContractError): validate_base_distribution(base)


def test_basketball_auxiliary_does_not_solve_coefficients_or_residual_scale(monkeypatch):
    import numpy as np
    original, _ = capture("basketball")
    actual_solve, shapes = np.linalg.solve, []
    width, sample = len(original.fitted.teams) + 1, len(original.matches)
    def solve(a, b):
        shapes.append(b.shape)
        assert b.shape == (width, sample)  # only the signed-influence RHS, never X'y or Gram
        return actual_solve(a, b)
    monkeypatch.setattr(np.linalg, "solve", solve)
    value = build("basketball", original)
    validate_base_distribution(value.base)
    assert shapes and set(shapes) == {(width, sample)}


@pytest.mark.parametrize("sport", SPORTS)
def test_explicit_offline_replay_is_needed_to_prove_fitted_origin_not_just_a_rehash(sport):
    base = deepcopy(build(sport).base)
    origin = base["reference_weights"]["original"]
    # Non-target coefficient: internally coherent forward output is unchanged.
    # A new public hash is not evidence that the actual model fitted it.
    origin["model"]["fit"]["coefficients"][3] += .125
    base["model_hash"] = digest(dict(kind=api().MODEL_RECIPE, sport=sport, model=origin["model"]))
    assert api().validate_team_sport_live_origin(base)["reference_weights"]["original"]["source_resolution"] == "unresolved"
    with pytest.raises(ContextContractError, match="offline original fitted"):
        api().replay_team_sport_live_origin(base)


def test_actual_euroleague_scope_and_raw_case_sensitive_ids_are_not_nba_defaults():
    target, rows = raw_inputs("basketball")
    clubs = {str(i): f"Club_{i}" for i in range(1, 9)}
    for i, row in enumerate([target, *rows]):
        row.update(provider="EuroLeague", competition="EuroLeague", provider_event_id=f"E2026_{i}",
            season="E2026", context_rules=dict(regulation_minutes=40, regulation_periods=4, overtime_period_minutes=5))
        row["home_team_id"] = clubs[row["home_team_id"]]
        row["away_team_id"] = clubs[row["away_team_id"]]
    current = native_event("basketball")
    current.update(event_key="euroleague:basketball:E2026_0", competition="euroleague",
        format="euroleague_reg40_including_ot", home_id="euroleague:basketball:team:Club_1",
        away_id="euroleague:basketball:team:Club_8")
    original, prediction = capture("basketball", target=target, rows=rows)
    value = build("basketball", original, event=current)
    assert value.base["markets"]["home_win"].hex() == prediction.p_home.hex()
    assert value.original["native_scope"]["rules"]["regulation_minutes"] == 40
    assert value.original["model"]["identity"]["home"] == "id:club_1"
    assert value.original["inputs"]["event"]["home_team_id"] == "Club_1"
    changed = deepcopy(current)
    changed["home_id"] = changed["home_id"].lower()
    with pytest.raises(ContextContractError): build("basketball", original, event=changed)


def test_nested_unrelated_rule_prices_are_not_captured():
    target, rows = raw_inputs("basketball")
    before = build("basketball", capture("basketball", target=target, rows=rows)[0])
    for row in [target, *rows]:
        row["context_rules"].update(odds=4.5, bookmaker=dict(secret="not-model-data"))
    after = build("basketball", capture("basketball", target=target, rows=rows)[0])
    assert canonical_bytes(before.base) == canonical_bytes(after.base)
    assert canonical_bytes(before.original) == canonical_bytes(after.original)


@pytest.mark.parametrize("sport", SPORTS)
def test_full_actual_revision_inventory_not_a_selected_rows_receipt_zip(sport):
    target, rows = raw_inputs(sport)
    # The first old result is explicitly retracted before cutoff. Original
    # same-call selected design excludes it, while raw index 84 records why.
    correction = {**rows[0], "status": "started", "result_observed_at": (NOW-timedelta(minutes=1)).isoformat()}
    rows.append(correction)
    original, prediction = capture(sport, target=target, rows=rows)
    assert len(original.matches) == 83
    binding = dict(schema=1, kind="team-sports-live-receipt-refs-v1", event_receipt=None,
        history_receipts=[dict(input_index=84, receipt="d"*64)], artifact_refs=[])
    result = build(sport, original, receipt_binding=binding)
    assert len(result.original["inputs"]["history"]) == 85
    assert result.original["inputs"]["history"][84]["status"] == "started"
    assert result.base["history_refs"] == []
    assert result.original["outputs"]["p_home"] == prediction.p_home
    assert canonical_bytes(api().replay_team_sport_live_origin(result.base)) == canonical_bytes(result.base)


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("value", [True, "0.5", float("nan"), float("inf")])
def test_bad_captured_numerics_are_not_clipped_or_cast(sport, value):
    base = deepcopy(build(sport).base)
    base["reference_weights"]["original"]["model"]["fit"]["coefficients"][0] = value
    with pytest.raises(ContextContractError): api().validate_team_sport_live_origin(base)


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("field,value", [("cutoff", None), ("cutoff", "bad-time"), ("p_home", float("nan")),
    ("p_away", float("inf")), ("p_home", {}), ("p_away", True)])
def test_malformed_output_or_clock_remains_typed(sport, field, value):
    origin = deepcopy(build(sport).original)
    if field == "cutoff": origin[field] = value
    else: origin["outputs"][field] = value
    with pytest.raises(ContextContractError): api().validate_captured_team_sport_original(origin)


@pytest.mark.parametrize("sport", SPORTS)
def test_mutated_capture_dataclass_is_not_an_original_proof(sport):
    original, _ = capture(sport)
    with pytest.raises(ContextContractError): build(sport, replace(original, fitted={}))
    with pytest.raises(ContextContractError): build(sport, replace(original, prediction={}))


def test_hockey_inline_sample_indices_are_not_measured_exposure_records():
    result = build("ice_hockey")
    ref = result.original["auxiliary_reference"]
    assert ref["kind"] == "hockey-inline-contributing-sample-indices-v1"
    assert ref["role"] == "model-design-rows-not-native-receipts"
    assert set(ref) == {"kind", "role", "regulation_outcomes", "sample_indices_home", "sample_indices_away"}


@pytest.mark.parametrize("sport", SPORTS)
def test_capture_and_pure_validator_do_not_access_database_files_or_sources(sport, monkeypatch):
    import builtins
    import requests
    import model_artifacts
    import context_observations
    original, _ = capture(sport)
    implementation = api()
    def forbidden(*args, **kwargs): pytest.fail("pure original performed runtime IO")
    monkeypatch.setattr(model_artifacts, "_connect", forbidden)
    monkeypatch.setattr(context_observations, "_connect", forbidden)
    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    result = build(sport, original)
    assert implementation.validate_team_sport_live_origin(result.base) == result.base
    assert validate_base_distribution(result.base) == result.base
