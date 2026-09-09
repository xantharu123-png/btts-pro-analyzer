"""Exact JSON copy bindings, not a tolerance for fitting arithmetic.

Synthetic approvals only exercise pure transport roles. These cases neither
resolve real sources nor establish empirical effect approval.
"""
import pytest

from context_models.contracts import ContextContractError, digest
from context_snapshots import _payload_digest
from context_transport import (
    calculate_context_payload, context_payload_key, validate_context_payload,
    context_consumer_reference, project_context_market, replay_context_payload,
)
from model_artifacts import canonical_bytes
from test_context_transport import inputs, synthetic_approval


def football(role):
    from test_football_context_model import inputs as source, event
    base, features, fitted = source(home_coef=(0., 0., 0.), away_coef=(0., 0., 0.))
    effect = None if role == "not_applied" else {"kind": "context-effect-v1", "payload": fitted}
    args = {"event": event(), "base": base, "features": features,
            "observation_refs": sorted({ref for refs in features["refs"].values() for ref in refs}),
            "preprocessing_refs": [], "effect_artifact": effect,
            "effect_hash": None if effect is None else digest(effect), "approval": None}
    if role == "applied":
        args["approval"] = synthetic_approval(args)
    payload = calculate_context_payload(**args)
    assert payload["result"]["role"] == role
    return payload


def reject_both_paths(payload):
    key = context_payload_key(payload)
    with pytest.raises(ContextContractError):
        validate_context_payload(payload, key=key,
            effect_artifact=payload["effect_artifact"], approval=payload["approval"])
    reference = {"schema": 1, "kind": "context-consumer-reference-v1", "key": key,
                 "payload_digest": _payload_digest(key, payload)}
    with pytest.raises(ContextContractError):
        project_context_market(payload, reference, next(iter(payload["result"]["used_markets"])))


@pytest.mark.parametrize("role", ["not_applied", "experimental", "applied"])
@pytest.mark.parametrize("part", ["base_params", "used_params"])
def test_same_number_different_type_is_not_an_original_parameter_copy(role, part):
    payload = football(role)
    assert canonical_bytes(payload["result"][part]["home_lambda"]) == b"2.0"
    payload["result"][part]["home_lambda"] = 2
    reject_both_paths(payload)


def test_applied_used_parameters_must_match_comparison_bytes_too():
    payload = football("applied")
    payload["result"]["comparison_params"]["home_lambda"] = 2
    reject_both_paths(payload)


@pytest.mark.parametrize("role", ["not_applied", "experimental", "applied"])
@pytest.mark.parametrize("zero", [0, -0.0])
def test_every_role_binds_exact_computed_delta_bytes(role, zero):
    payload = football(role)
    market = next(iter(payload["result"]["delta_pp"]))
    assert canonical_bytes(payload["result"]["delta_pp"][market]) == b"0.0"
    payload["result"]["delta_pp"][market] = zero
    reject_both_paths(payload)


@pytest.mark.parametrize("part", ["base_markets", "used_markets"])
@pytest.mark.parametrize("number", [0, -0.0])
def test_exact_endpoint_market_copies_cannot_be_retyped_or_resigned(part, number):
    payload = calculate_context_payload(**inputs(p=0.0))
    payload["result"][part]["winner_a"] = number
    reject_both_paths(payload)


@pytest.mark.parametrize("role", ["not_applied", "experimental", "applied"])
def test_genuine_zero_effect_copies_remain_identical_and_detached(role):
    payload = football(role)
    original = canonical_bytes(payload)
    key = context_payload_key(payload)
    result = replay_context_payload(payload, key=key,
        effect_artifact=payload["effect_artifact"], approval=payload["approval"])
    reference = context_consumer_reference(key, result)
    card = project_context_market(result, reference, "HOME_OVER_0_5")
    assert canonical_bytes(card["used_params"]) == canonical_bytes(payload["base"]["params"])
    card["used_params"].clear()
    assert canonical_bytes(payload) == original
