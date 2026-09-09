"""Closed D3 CPU transport; input identity is not source or empirical proof.

The worker resolves real A1/B1 inputs and D2 approval before calling this module.
Embedded effect/approval envelopes permit pure read-time validation, not an
alternative to those resolvers. D4 additionally replays owning source/features.
Consumer projection does no source lookup, fitting or model recalculation.
"""
from copy import deepcopy
from datetime import datetime

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, digest, event_in_population,
    canonical_timestamp, require_digest, require_list, require_object, require_text,
    validate_base_distribution, validate_context_result, validate_event,
    validate_feature_vector, validate_history_refs, validate_markets, validate_parameters,
)
from context_models.offset import ContextModelError
from context_snapshots import (
    _finite_json, _payload_digest, _verified_payload, select_context_result, snapshot_key,
)
from model_artifacts import canonical_bytes


KIND = "context-worker-snapshot-v1"
_INPUTS = {"schema", "kind", "event", "base", "features", "observation_refs",
    "preprocessing_refs", "effect_artifact", "effect_hash", "approval", "approval_hash"}
_REF_KEYS = {"schema", "kind", "key", "payload_digest"}
_BASE_KEYS = {"version", "model_hash", "event_key", "cutoff", "family", "params",
    "markets", "history_refs", "reference_weights"}


def _refs(value, label):
    require_list(value, label)
    for ref in value:
        require_digest(ref, label)
    if value != sorted(set(value)):
        raise ContextContractError(f"{label} must be sorted and unique")


def _feature_binding(ev, original, feats, preprocessing_refs):
    """Bind even an unapplied feature vector to its owning full Event/Base."""
    pair = original["family"], feats["version"]
    if pair == ("football:goals:90min", "football-roster-components-v2"):
        expected = digest({"version": "football-context-reference-v2", "base_hash": digest(original),
            "event_hash": digest(ev), "preprocessing": preprocessing_refs})
    elif pair in {(family, "tennis-performed-load-v2") for family in ("tennis:winner", "tennis:serve")}:
        expected = digest({"version": "tennis-context-reference-v2", "base_hash": digest(original),
            "event_hash": digest(ev)})
    elif pair in {(family, "tennis-performed-load-v3") for family in ("tennis:winner", "tennis:serve")}:
        if preprocessing_refs:
            raise ContextContractError("tennis status v3 has no named preprocessing contract")
        expected = digest({"version": "tennis-context-reference-v3", "base_hash": digest(original),
            "event_hash": digest(ev)})
    elif pair == ("basketball:margin:including_ot", "basketball-rotation-observed-load-v1"):
        if preprocessing_refs:
            raise ContextContractError("basketball v1 has no named preprocessing contract")
        expected = digest({"version": "basketball-context-reference-v1", "base_hash": digest(original),
            "event_hash": digest(ev), "preprocessing_artifacts": {}})
    elif pair == ("ice_hockey:regulation_goals", "hockey-observed-exposure-load-v1"):
        if preprocessing_refs:
            raise ContextContractError("hockey v1 has no named preprocessing contract")
        expected = digest({"version": "hockey-context-reference-v1", "base_hash": digest(original),
            "event_hash": digest(ev), "preprocessing_artifacts": {}})
    elif pair == ("esports:series:winner", "esports-native-participation-load-v1"):
        if preprocessing_refs:
            raise ContextContractError("esports v1 has no named preprocessing contract")
        expected = digest({"version": "esports-context-reference-v1", "base_hash": digest(original),
            "event_hash": digest(ev), "preprocessing": []})
    else:
        raise ContextContractError("owning worker feature reference is not yet connected")
    if feats["reference_hash"] != expected:
        raise ContextIntegrityError("worker features belong to a different original Event/Base reference")


def _base_read_shape(value):
    """Read scalars/closed transport only; owning reference replay is not a render.

    The worker's full validation remains mandatory. This reader can check the
    already published payload's identity without solving the C2 Ridge recipe.
    It does not certify source/recipe truth or create a new forecast.
    """
    require_object(value, _BASE_KEYS, label="stored original base")
    require_text(value["version"], "original base version", code=True)
    require_digest(value["model_hash"], "original model identity")
    if type(value["reference_weights"]) is not dict or canonical_timestamp(value["cutoff"]) != value["cutoff"]:
        raise ContextContractError("stored base reference/clock shape is invalid")
    validate_parameters(value["params"], value["family"])
    validate_markets(value["markets"], family=value["family"])
    validate_history_refs(value["history_refs"])
    return value


def _inputs(payload, *, replay_base=True):
    require_object(payload, _INPUTS, optional={"result"}, label="context worker payload")
    _finite_json(payload)
    if type(payload["schema"]) is not int or payload["schema"] != 1 or payload["kind"] != KIND:
        raise ContextContractError("unknown worker context transport version")
    ev = validate_event(payload["event"])
    original = validate_base_distribution(payload["base"]) if replay_base else _base_read_shape(payload["base"])
    feats = validate_feature_vector(payload["features"])
    for key, checked in (("event", ev), ("base", original), ("features", feats)):
        if canonical_bytes(payload[key]) != canonical_bytes(checked):
            raise ContextIntegrityError("worker inputs must retain canonical original bytes")
    if (ev["event_key"] != original["event_key"] or feats["event_key"] != ev["event_key"]
            or feats["cutoff"] != original["cutoff"] or original["family"].split(":")[0] != ev["sport"]):
        raise ContextIntegrityError("worker event/base/features do not share a revision")
    for key in ("observation_refs", "preprocessing_refs"):
        _refs(payload[key], key)
    if any(not set(refs) <= set(payload["observation_refs"]) for refs in feats["refs"].values()):
        raise ContextIntegrityError("worker omitted an actual feature observation reference")
    _feature_binding(ev, original, feats, payload["preprocessing_refs"])
    artifact = None
    if payload["effect_artifact"] is not None:
        _, artifact = _verified_payload(payload["effect_artifact"], kind="context-effect-v1",
            expected_hash=payload["effect_hash"])
    elif payload["effect_hash"] is not None:
        raise ContextIntegrityError("effect identity is missing its immutable envelope")
    approval = None
    if payload["approval"] is not None:
        approval_hash, approval = _verified_payload(payload["approval"], kind="context-approval-v1")
        if approval_hash != payload["approval_hash"] or artifact is None:
            raise ContextIntegrityError("approval identity is missing its bound effect")
    elif payload["approval_hash"] is not None:
        raise ContextIntegrityError("approval identity is missing its immutable envelope")
    return ev, original, feats, artifact, approval


def context_payload_key(payload: dict) -> str:
    ev, original, feats, _, _ = _inputs(payload)
    return _input_key(payload, ev, original, feats)


def _input_key(payload, ev, original, feats):
    # This is an input-descriptor digest, explicitly NOT an observation receipt.
    # It separates reference roles and new transport from old bare B3 callbacks.
    descriptor = digest({"kind": KIND, "observation_refs": payload["observation_refs"],
        "preprocessing_refs": payload["preprocessing_refs"]})
    return snapshot_key(ev, base_hash=digest(original),
        context_refs=tuple(sorted(set(payload["observation_refs"] + payload["preprocessing_refs"] + [descriptor]))),
        feature_version=feats["version"], feature_hash=digest(feats),
        effect_hash=payload["effect_hash"], approval_hash=payload["approval_hash"],
        decision_at=datetime.fromisoformat(original["cutoff"]))


def _eligible(ev, original, feats, artifact):
    return artifact is not None and (
        ev["status"] == "scheduled" and original["cutoff"] < ev["scheduled_start"]
        and artifact["family"] == original["family"] and event_in_population(ev, artifact["population"])
        and artifact["feature_version"] == feats["version"] and artifact["coverage"] == feats["coverage"]
        and artifact["training_end"] <= original["cutoff"]
        and all(name in feats["values"] and feats["states"][name] == "available" for name in artifact["feature_names"]))


def _approved(ev, original, feats, artifact, approval, effect_hash):
    fields = ("sport", "family", "feature_version", "population", "coverage", "model_variant")
    return approval is not None and _eligible(ev, original, feats, artifact) and (
        approval["effect_hash"] == effect_hash and all(approval[name] == artifact[name] for name in fields)
        and original["version"] in approval["base_versions"]
        and artifact["training_end"] <= approval["evaluated_at"] <= original["cutoff"]
        and set(approval["target_markets"]) <= set(original["markets"]))


def _comparison(ev, original, feats, artifact):
    family = original["family"]
    if family == "football:goals:90min":
        from context_models.football_effect import apply_football_effect
        return apply_football_effect(original, feats, artifact, event=ev)
    if family in {"tennis:winner", "tennis:serve"}:
        from context_models.tennis_effect import apply_tennis_effect
        return apply_tennis_effect(original, feats, artifact, event=ev)
    if family == "basketball:margin:including_ot":
        from context_models.team_sports import apply_team_sport_effect
        return apply_team_sport_effect("basketball", original, feats, artifact, event=ev)
    if family == "ice_hockey:regulation_goals":
        from context_models.ice_hockey import apply_hockey_effect
        return apply_hockey_effect(original, feats, artifact, event=ev)
    if family == "esports:series:winner":
        from context_models.esports import apply_esports_effect
        return apply_esports_effect(original, feats, artifact, event=ev)
    raise ContextContractError("owning worker comparison family is not yet connected")


def calculate_context_payload(*, event: dict, base: dict, features: dict,
        observation_refs: list, preprocessing_refs: list, effect_artifact: dict | None,
        effect_hash: str | None, approval: dict | None) -> dict:
    """CPU-only original-parameter comparison; no free comparison/callback input.

    Actual source and empirical verification belong to the caller's owning
    worker. A canonical envelope alone is expressly not a trusted approval.
    """
    if approval is not None:
        require_object(approval, {"digest", "kind", "payload"}, label="resolved worker approval envelope")
    payload = deepcopy({"schema": 1, "kind": KIND, "event": validate_event(event),
        "base": validate_base_distribution(base), "features": validate_feature_vector(features),
        "observation_refs": observation_refs, "preprocessing_refs": preprocessing_refs,
        "effect_artifact": effect_artifact, "effect_hash": effect_hash,
        "approval": approval, "approval_hash": None if approval is None else approval.get("digest")})
    ev, original, feats, artifact, _ = _inputs(payload)
    comparison, limitations = None, []
    if artifact is None:
        limitations.append("context-effect-unavailable")
    elif _eligible(ev, original, feats, artifact):
        try:
            comparison = _comparison(ev, original, feats, artifact)
        except ContextModelError:
            limitations.append("context-numerical-comparison-unavailable")
    payload["result"] = select_context_result(original, comparison, event=ev, features=feats,
        effect_artifact=payload["effect_artifact"], effect_hash=effect_hash, approval=payload["approval"],
        factor_roles={name: "applied" if artifact is not None and name in artifact["feature_names"] else "not_applied"
            for name in feats["values"]}, factor_states=feats["states"], limitations=limitations)
    return validate_context_payload(payload, key=context_payload_key(payload),
        effect_artifact=effect_artifact, approval=approval)


def validate_context_payload(payload: dict, *, key: str, effect_artifact: dict | None,
        approval: dict | None) -> dict:
    """Validate exact transport bindings, without rerunning an owning model.

    External resolvers supply matching A1 envelopes. Pure UI projection can
    check the embedded envelopes, which proves identity but not empirical truth.
    Use replay_context_payload for the additional owning numerical audit.
    """
    return _validate_payload(payload, key=key, effect_artifact=effect_artifact, approval=approval)


def _validate_payload(payload, *, key, effect_artifact, approval, replay_base=True):
    require_object(payload, _INPUTS | {"result"}, label="complete worker context payload")
    ev, original, feats, artifact, approved = _inputs(payload, replay_base=replay_base)
    require_digest(key, "worker snapshot key")
    if _input_key(payload, ev, original, feats) != key:
        raise ContextIntegrityError("worker snapshot key does not bind its complete inputs")
    if (canonical_bytes(effect_artifact) != canonical_bytes(payload["effect_artifact"])
            or canonical_bytes(approval) != canonical_bytes(payload["approval"])):
        raise ContextIntegrityError("worker artifact differs from the resolved immutable envelope")
    consumed = artifact if artifact is not None and artifact["family"] == original["family"] else None
    result = validate_context_result(payload["result"], family=original["family"], effect_artifact=consumed)
    expected = {"event_key": ev["event_key"], "base_hash": digest(original), "effect_hash": payload["effect_hash"],
        "base_params": original["params"], "base_markets": original["markets"],
        "factor_states": feats["states"], "feature_refs": feats["refs"]}
    if (canonical_bytes(result) != canonical_bytes(payload["result"])
            or any(canonical_bytes(result[name]) != canonical_bytes(value) for name, value in expected.items())):
        raise ContextIntegrityError("worker result differs from its original inputs")
    prefix = "comparison" if result["role"] == "applied" else "base"
    if any(canonical_bytes(result["used_" + part]) != canonical_bytes(result[prefix + "_" + part])
           for part in ("params", "markets")):
        raise ContextIntegrityError("worker used distribution must preserve the exact role-selected bytes")
    expected_roles = {name: result["role"] if artifact is not None and name in artifact["feature_names"] else "not_applied"
        for name in feats["values"]}
    if result["factor_roles"] != expected_roles:
        raise ContextIntegrityError("worker factor roles differ from actual consumed features")
    expected_delta = {name: 100*(probability-original["markets"][name])
                      for name, probability in result["used_markets"].items()}
    if canonical_bytes(result["delta_pp"]) != canonical_bytes(expected_delta):
        raise ContextIntegrityError("worker result delta is not the exact used difference")
    if result["role"] != "not_applied" and not _eligible(ev, original, feats, artifact):
        raise ContextIntegrityError("ineligible worker input cannot claim a comparison")
    if result["role"] == "applied":
        if (not _approved(ev, original, feats, artifact, approved, payload["effect_hash"])
                or result.get("approval_hash") != payload["approval_hash"]
                or result.get("certified_markets") != approved["target_markets"]):
            raise ContextIntegrityError("worker application does not match its scoped approval")
    elif result.get("approval_hash") is not None or result.get("certified_markets"):
        raise ContextIntegrityError("unapplied worker result cannot inherit certification")
    return deepcopy(payload)


def replay_context_payload(payload: dict, *, key: str, effect_artifact: dict | None,
        approval: dict | None) -> dict:
    """Audit the owning numerical law plus B3 selection, not source/fit truth."""
    checked = validate_context_payload(payload, key=key, effect_artifact=effect_artifact, approval=approval)
    calculated = calculate_context_payload(**{name: checked[name] for name in (
        "event", "base", "features", "observation_refs", "preprocessing_refs", "effect_artifact", "effect_hash", "approval")})
    if canonical_bytes(calculated) != canonical_bytes(checked):
        raise ContextIntegrityError("worker snapshot does not replay its owning comparison and selection")
    return checked


def context_consumer_reference(key: str, payload: dict) -> dict:
    require_object(payload, _INPUTS | {"result"}, label="complete worker context payload")
    validate_context_payload(payload, key=key, effect_artifact=payload.get("effect_artifact"), approval=payload.get("approval"))
    return {"schema": 1, "kind": "context-consumer-reference-v1", "key": key,
        "payload_digest": _payload_digest(key, payload)}


def project_context_market(payload: dict, reference: dict, selected_market: str) -> dict:
    """Read one exact market, detached; never run a model or read a provider."""
    require_object(payload, _INPUTS | {"result"}, label="complete worker context payload")
    require_object(reference, _REF_KEYS, label="context consumer reference")
    if type(reference["schema"]) is not int or reference["schema"] != 1 or reference["kind"] != "context-consumer-reference-v1":
        raise ContextContractError("unknown context consumer reference version")
    require_digest(reference["payload_digest"], "consumer payload identity")
    _validate_payload(payload, key=reference["key"], effect_artifact=payload.get("effect_artifact"),
        approval=payload.get("approval"), replay_base=False)
    if reference["payload_digest"] != _payload_digest(reference["key"], payload):
        raise ContextIntegrityError("consumer reference does not bind this context payload")
    require_text(selected_market, "selected canonical market", code=True)
    result = payload["result"]
    if selected_market not in result["used_markets"]:
        raise ContextContractError("consumer market is outside the bound original distribution")
    return deepcopy({"context_ref": reference, "family": payload["base"]["family"],
        "selected_market": selected_market, "used_params": result["used_params"],
        "base_probability": result["base_markets"][selected_market],
        "used_probability": result["used_markets"][selected_market],
        "delta_pp": result["delta_pp"][selected_market]})
