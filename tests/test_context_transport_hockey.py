"""D3 transport of the actual C3 law; synthetic inputs, no real D2 approval."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, digest
from context_transport import (calculate_context_payload, context_payload_key,
    context_consumer_reference, project_context_market, replay_context_payload)
from model_artifacts import canonical_bytes
from test_ice_hockey_context import event
from test_ice_hockey_effects import inputs, approval


def packet(*, with_effect=True, with_approval=False, confirmed=True):
    original, fv, fitted = inputs(role="goalie", confirmed=confirmed)
    wrapped = {"kind": "context-effect-v1", "payload": fitted} if with_effect else None
    return dict(event=event(), base=original, features=fv,
        observation_refs=sorted({ref for refs in fv["refs"].values() for ref in refs}),
        preprocessing_refs=[], effect_artifact=wrapped,
        effect_hash=digest(wrapped) if wrapped else None,
        approval=approval(fitted) if with_approval else None)


@pytest.mark.parametrize("with_effect,with_approval,confirmed,role", [
    (False, False, True, "not_applied"), (True, False, True, "experimental"),
    (True, True, True, "applied"), (True, True, False, "experimental"),
])
def test_owning_hockey_role_and_ot_survive_transport(with_effect, with_approval, confirmed, role):
    args = packet(with_effect=with_effect, with_approval=with_approval, confirmed=confirmed)
    before = canonical_bytes(args)
    payload = calculate_context_payload(**args)
    result = payload["result"]
    assert result["role"] == role
    assert result["used_params"]["overtime_home_probability"] == args["base"]["params"]["overtime_home_probability"]
    if role != "applied":
        assert canonical_bytes(result["used_params"]) == canonical_bytes(args["base"]["params"])
        assert canonical_bytes(result["used_markets"]) == canonical_bytes(args["base"]["markets"])
    key = context_payload_key(payload)
    assert replay_context_payload(payload, key=key, effect_artifact=args["effect_artifact"], approval=args["approval"]) == payload
    assert canonical_bytes(args) == before


def test_hockey_market_reader_never_replays_original_poisson_fit(monkeypatch):
    args = packet()
    payload = calculate_context_payload(**args)
    reference = context_consumer_reference(context_payload_key(payload), payload)
    def forbidden(*args, **kwargs):
        pytest.fail("reading a stored hockey market must not refit the original model")
    monkeypatch.setattr("context_models.ice_hockey._original_parts", forbidden)
    for market in args["base"]["markets"]:
        projected = project_context_market(payload, reference, market)
        assert projected["used_probability"] == args["base"]["markets"][market]
        assert projected["context_ref"] == reference


@pytest.mark.parametrize("change", ["schedule", "participants", "preprocessing"])
def test_hockey_unapplied_reference_still_binds_whole_inputs(change):
    args = packet(with_effect=False)
    if change == "schedule":
        args["event"]["schedule_revision"] = "different-v2"
    elif change == "participants":
        args["event"]["home_id"] = "nhl:ice_hockey:team:99"
    else:
        args["preprocessing_refs"] = ["e"*64]
    with pytest.raises((ContextIntegrityError, ContextContractError)):
        calculate_context_payload(**args)


def test_owning_replay_rejects_promoted_conditional_hockey_comparison():
    args = packet(with_approval=True, confirmed=False)
    payload = calculate_context_payload(**args)
    assert payload["result"]["role"] == "experimental"
    altered = deepcopy(payload)
    result = altered["result"]
    result.update(role="applied", used_params=result["comparison_params"],
        used_markets=result["comparison_markets"], approval_hash=altered["approval_hash"],
        certified_markets=args["approval"]["payload"]["target_markets"])
    result["factor_roles"] = {name: "applied" if role == "experimental" else role
        for name, role in result["factor_roles"].items()}
    result["delta_pp"] = {name: 100*(value-result["base_markets"][name]) for name, value in result["used_markets"].items()}
    with pytest.raises(ContextIntegrityError):
        replay_context_payload(altered, key=context_payload_key(altered),
            effect_artifact=args["effect_artifact"], approval=args["approval"])


def test_native_hockey_export_preserves_optimizer_and_canonical_bytes():
    from dataclasses import asdict
    from datetime import datetime
    from context_models.ice_hockey import _original_parts
    from context_snapshots import _finite_json
    from test_ice_hockey_context import NOW, base, inputs as original_inputs
    target, history = original_inputs()
    fitted = _original_parts(target, tuple(history), NOW)[2]
    # Exact former export projection, not a replacement model/optimizer.
    former = {name: value.isoformat() if isinstance(value, datetime) else
              list(value) if isinstance(value, tuple) else value
              for name, value in asdict(fitted).items()}
    original = base()
    current = original["reference_weights"]["fit"]
    assert all(type(value) is float for value in current["coefficients"])
    assert [value.hex() for value in current["coefficients"]] == [float(value).hex() for value in former["coefficients"]]
    assert canonical_bytes(current) == canonical_bytes(former)
    _finite_json(original)


def test_complete_hockey_payload_is_stored_once_and_read_by_two_consumers(tmp_path):
    from context_snapshots import compute_once
    args = packet()
    prepared = calculate_context_payload(**args)
    key = context_payload_key(prepared)
    calls = []
    def calculate():
        calls.append("cpu-comparison")
        return calculate_context_payload(**args)
    path = tmp_path/"hockey.db"
    first = compute_once(path, key, calculate)
    second = compute_once(path, key, calculate)
    assert calls == ["cpu-comparison"]
    assert canonical_bytes(first) == canonical_bytes(second)
    reference = context_consumer_reference(key, first)
    assert project_context_market(first, reference, "home_reg")["context_ref"] == reference
    assert project_context_market(second, reference, "away_inclusive")["context_ref"] == reference
