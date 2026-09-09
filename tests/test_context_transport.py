"""D3 transport mechanics on synthetic B7 inputs, not source/empirical proof."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, digest
from model_artifacts import canonical_bytes
from test_tennis_context_model import artifact, base, event, features, REF
from context_transport import (
    calculate_context_payload, validate_context_payload, replay_context_payload,
    context_payload_key, context_consumer_reference, project_context_market,
)


def inputs(*, with_effect=False, **base_args):
    original = base(**base_args)
    ev = event(best_of=original["params"].get("best_of", 3))
    feats = features(original, ev=ev)
    effect = {"kind": "context-effect-v1", "payload": artifact(original, feats, ev)} if with_effect else None
    return {"event": ev, "base": original, "features": feats,
        "observation_refs": [REF], "preprocessing_refs": [], "effect_artifact": effect,
        "effect_hash": digest(effect) if effect else None, "approval": None}


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("with_effect", [False, True])
def test_real_owning_comparison_preserves_base_without_empirical_approval(family, with_effect):
    args = inputs(with_effect=with_effect, family=family)
    before = deepcopy(args)
    payload = calculate_context_payload(**args)
    assert args == before
    assert payload["kind"] == "context-worker-snapshot-v1"
    assert payload["result"]["role"] == ("experimental" if with_effect else "not_applied")
    assert payload["result"]["used_params"] == args["base"]["params"]
    assert payload["result"]["used_markets"] == args["base"]["markets"]
    key = context_payload_key(payload)
    assert replay_context_payload(payload, key=key, effect_artifact=args["effect_artifact"], approval=None) == payload
    reference = context_consumer_reference(key, payload)
    first = project_context_market(payload, reference, "winner_a")
    second = project_context_market(payload, reference, "winner_b")
    assert first["context_ref"] == second["context_ref"] == reference
    assert first["used_params"] == second["used_params"] == args["base"]["params"]
    assert first["used_probability"] == args["base"]["markets"]["winner_a"]
    assert second["used_probability"] == args["base"]["markets"]["winner_b"]
    first["used_params"].clear()
    reference["key"] = "e" * 64
    assert payload["result"]["used_params"] == before["base"]["params"]
    assert second["context_ref"]["key"] == key


@pytest.mark.parametrize("path,value", [
    (("schema",), True), (("kind",), "other"), (("event", "schedule_revision"), "s2"),
    (("base", "cutoff"), "2026-09-09T13:00:00.000000Z"),
    (("features", "event_key"), "espn:tennis:ATP:match:998"),
    (("observation_refs",), []), (("observation_refs",), [REF, REF]),
    (("preprocessing_refs",), ["z" * 64]),
    (("result", "used_params", "p_a"), .8),
    (("result", "delta_pp", "winner_a"), 1e-11),
    (("result", "factor_states", "availability_delta"), "available"),
])
def test_snapshot_input_and_exact_result_tampering_is_rejected(path, value):
    args = inputs()
    payload = calculate_context_payload(**args)
    key = context_payload_key(payload)
    target = payload
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = value
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        validate_context_payload(payload, key=key, effect_artifact=None, approval=None)


@pytest.mark.parametrize("extra", ["price", "odds", "bookmaker", "selected_market", "verified", "callback"])
def test_closed_payload_cannot_add_price_or_source_authority(extra):
    payload = calculate_context_payload(**inputs())
    key = context_payload_key(payload)
    payload[extra] = "claimed"
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        validate_context_payload(payload, key=key, effect_artifact=None, approval=None)


@pytest.mark.parametrize("field", ["key", "payload_digest"])
def test_consumer_reference_binds_input_and_payload_identity(field):
    payload = calculate_context_payload(**inputs())
    reference = context_consumer_reference(context_payload_key(payload), payload)
    reference[field] = "e" * 64
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        project_context_market(payload, reference, "winner_a")


@pytest.mark.parametrize("market", ["home", "winner", "total_sets_over_2.5", "<script>", None])
def test_projection_cannot_invent_market_or_orientation(market):
    payload = calculate_context_payload(**inputs())
    reference = context_consumer_reference(context_payload_key(payload), payload)
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        project_context_market(payload, reference, market)


def test_read_projection_performs_no_owning_model_calculation(monkeypatch):
    args = inputs(with_effect=True)
    payload = calculate_context_payload(**args)
    reference = context_consumer_reference(context_payload_key(payload), payload)
    def forbidden(*args, **kwargs):
        pytest.fail("a consumer read must not recalculate the context model")
    monkeypatch.setattr("context_models.tennis_effect.apply_tennis_effect", forbidden)
    before = canonical_bytes(payload)
    for _ in range(3):
        assert project_context_market(payload, reference, "winner_a")["used_probability"] == .6
    assert canonical_bytes(payload) == before


def test_replay_rejects_rehashed_comparison_forgery():
    args = inputs(with_effect=True)
    payload = calculate_context_payload(**args)
    payload["result"]["comparison_params"]["p_a"] = .51
    payload["result"]["comparison_markets"] = {"winner_a": .51, "winner_b": .49}
    key = context_payload_key(payload)
    with pytest.raises(ContextIntegrityError):
        replay_context_payload(payload, key=key, effect_artifact=args["effect_artifact"], approval=None)


def test_all_inspected_input_refs_change_key_not_only_used_feature_refs():
    args = inputs()
    first = calculate_context_payload(**args)
    args["observation_refs"] = [REF, "f" * 64]
    second = calculate_context_payload(**args)
    assert first["result"] == second["result"]
    assert context_payload_key(first) != context_payload_key(second)


def test_reference_roles_and_transport_version_are_bound_in_key():
    from datetime import datetime
    from context_snapshots import snapshot_key
    args = inputs()
    args["observation_refs"] = [REF, "f" * 64]
    observed = calculate_context_payload(**args)
    args["observation_refs"] = [REF]
    args["preprocessing_refs"] = ["f" * 64]
    preprocessed = calculate_context_payload(**args)
    assert observed["result"] == preprocessed["result"]
    assert context_payload_key(observed) != context_payload_key(preprocessed)
    old_key = snapshot_key(preprocessed["event"], base_hash=digest(preprocessed["base"]),
        context_refs=(REF, "f" * 64), feature_version=preprocessed["features"]["version"],
        feature_hash=digest(preprocessed["features"]), effect_hash=None, approval_hash=None,
        decision_at=datetime.fromisoformat(preprocessed["base"]["cutoff"]))
    assert old_key != context_payload_key(preprocessed)


def test_wrong_effect_transport_is_not_disguised_as_missing_context():
    args = inputs(with_effect=True)
    args["effect_artifact"]["payload"]["heads"]["winner"]["coef"][0] += .1
    with pytest.raises(ContextIntegrityError):
        calculate_context_payload(**args)


@pytest.mark.parametrize("family", ["football", "basketball"])
@pytest.mark.parametrize("with_effect", [False, True])
def test_other_reviewed_owning_laws_replay_in_same_transport(family, with_effect):
    if family == "football":
        from test_football_context_model import inputs as other_inputs, event as other_event
        original, feats, fitted = other_inputs()
    else:
        from test_basketball_context import packet, feature_packet, artifact as other_artifact, event as other_event
        original, _, rows = packet()
        feats = feature_packet(original, rows)
        fitted = other_artifact(original, feats)
    effect = {"kind": "context-effect-v1", "payload": fitted} if with_effect else None
    payload = calculate_context_payload(event=other_event(), base=original, features=feats,
        observation_refs=sorted({ref for refs in feats["refs"].values() for ref in refs}),
        preprocessing_refs=[], effect_artifact=effect, effect_hash=digest(effect) if effect else None, approval=None)
    assert payload["result"]["used_params"] == original["params"]
    assert payload["result"]["used_markets"] == original["markets"]
    assert payload["result"]["role"] == ("experimental" if with_effect else "not_applied")
    assert replay_context_payload(payload, key=context_payload_key(payload), effect_artifact=effect, approval=None) == payload


@pytest.mark.parametrize("field,value", [("home_id", "espn:tennis:ATP:player:99"),
    ("schedule_revision", "s2"), ("scheduled_start", "2026-09-09T19:00:00.000000Z")])
def test_even_missing_effect_requires_features_bound_to_whole_original_event(field, value):
    args = inputs()
    args["event"][field] = value
    with pytest.raises(ContextIntegrityError):
        calculate_context_payload(**args)


@pytest.mark.parametrize("approval", [[], "approved", True, 1])
def test_invalid_approval_types_are_typed_not_attribute_errors(approval):
    args = inputs()
    args["approval"] = approval
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        calculate_context_payload(**args)


def synthetic_approval(args):
    # Deliberately synthetic TRANSPORT input, never supplied to a real worker.
    from test_context_snapshots import approval_payload
    fitted = args["effect_artifact"]["payload"]
    body = approval_payload(args["effect_hash"])
    body.update({key: deepcopy(fitted[key]) for key in (
        "sport", "family", "feature_version", "population", "coverage", "model_variant")})
    body.update(base_versions=[args["base"]["version"]], target_markets=sorted(args["base"]["markets"]),
        evaluated_at="2026-09-08T12:00:00.000000Z")
    envelope = {"kind": "context-approval-v1", "payload": body}
    return {"digest": digest(envelope), **envelope}


@pytest.mark.parametrize("condition", ["scoped", "other-version", "future", "wrong-population", "zero"])
def test_transport_role_tracks_exact_synthetic_approval_scope_not_price(condition):
    args = inputs(with_effect=True)
    if condition == "zero":
        args["effect_artifact"]["payload"]["heads"]["winner"]["coef"] = [0.]
        args["effect_hash"] = digest(args["effect_artifact"])
    approval = synthetic_approval(args)
    if condition == "other-version":
        approval["payload"]["base_versions"] = ["unrelated-v1"]
    elif condition == "future":
        approval["payload"]["evaluated_at"] = "2026-09-09T12:00:00.000001Z"
    elif condition == "wrong-population":
        approval["payload"]["population"]["tours"] = ["WTA"]
    approval["digest"] = digest({key: approval[key] for key in ("kind", "payload")})
    args["approval"] = approval
    payload = calculate_context_payload(**args)
    result = payload["result"]
    applied = condition in {"scoped", "zero"}
    assert result["role"] == ("applied" if applied else "experimental")
    assert result["approval_hash"] == (approval["digest"] if applied else None)
    assert result["used_params"] == result["comparison_params" if applied else "base_params"]
    if condition == "zero":
        assert canonical_bytes(result["used_markets"]) == canonical_bytes(args["base"]["markets"])
        assert set(result["delta_pp"].values()) == {0.}
    assert replay_context_payload(payload, key=context_payload_key(payload),
        effect_artifact=args["effect_artifact"], approval=approval) == payload


def test_basketball_consumer_does_not_refit_ridge_inside_validation(monkeypatch):
    from test_basketball_context import packet, feature_packet, event as other_event
    original, _, rows = packet()
    feats = feature_packet(original, rows)
    payload = calculate_context_payload(event=other_event(), base=original, features=feats,
        observation_refs=sorted({ref for refs in feats["refs"].values() for ref in refs}),
        preprocessing_refs=[], effect_artifact=None, effect_hash=None, approval=None)
    reference = context_consumer_reference(context_payload_key(payload), payload)
    def forbidden(*args, **kwargs):
        pytest.fail("a card reader must not refit Ridge inside a base validator")
    monkeypatch.setattr("context_models.team_sports._recipe_arrays", forbidden)
    assert project_context_market(payload, reference, "home_win")["used_params"] == original["params"]


@pytest.mark.parametrize("payload", [None, [], "snapshot", True, 1])
@pytest.mark.parametrize("reader", ["reference", "market"])
def test_read_boundaries_reject_non_object_payload_without_attribute_error(payload, reader):
    original = calculate_context_payload(**inputs())
    key = context_payload_key(original)
    reference = context_consumer_reference(key, original)
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        if reader == "reference":
            context_consumer_reference(key, payload)
        else:
            project_context_market(payload, reference, "winner_a")


def test_real_b3_store_reuses_one_packet_for_two_read_consumers(tmp_path):
    from context_snapshots import compute_once
    path = tmp_path / "worker.db"
    args = inputs(with_effect=True)
    # Preparation here is synthetic and deliberately not an upstream once-only
    # claim. This test covers the real B3 stored transport and its CPU callback.
    prepared = calculate_context_payload(**args)
    key = context_payload_key(prepared)
    calls = []
    def calculate():
        calls.append("comparison")
        return calculate_context_payload(**args)
    first = compute_once(path, key, calculate)
    reference = context_consumer_reference(key, first)
    second = compute_once(path, key, calculate)
    assert calls == ["comparison"]
    assert canonical_bytes(first) == canonical_bytes(second)
    assert project_context_market(first, reference, "winner_a")["context_ref"] == reference
    assert project_context_market(second, reference, "winner_b")["context_ref"] == reference
    second["result"]["used_params"].clear()
    assert compute_once(path, key, calculate) == first
    assert calls == ["comparison"]
