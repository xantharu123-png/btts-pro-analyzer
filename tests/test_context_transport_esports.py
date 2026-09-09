"""C4-to-D3 exact transport; native-shaped synthetic data, no real approval."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_transport import (calculate_context_payload, context_payload_key,
    context_consumer_reference, project_context_market, replay_context_payload)
from model_artifacts import canonical_bytes
from test_context_snapshots import approval_payload, envelope
from test_esports_context import NOW, case, effect


def packet(case, *, with_effect=True, approved=False, coefficient=.7):
    fitted = effect(case, coefficient=coefficient)
    wrapped = {"kind": "context-effect-v1", "payload": fitted} if with_effect else None
    approval = None
    if approved:
        payload = approval_payload(digest(wrapped))
        payload.update({name: deepcopy(fitted[name]) for name in
            ("sport", "family", "feature_version", "population", "coverage", "model_variant")})
        payload.update(base_versions=[case["base"]["version"]],
            target_markets=sorted(case["base"]["markets"]),
            outcome_contract="synthetic-esports-test-only-v1",
            evaluated_at=canonical_timestamp(NOW-timedelta(hours=12)))
        approval = envelope(payload, "context-approval-v1")
    fv = case["features"]
    return dict(event=case["event"], base=case["base"], features=fv,
        observation_refs=sorted({ref for refs in fv["refs"].values() for ref in refs}),
        preprocessing_refs=[], effect_artifact=wrapped,
        effect_hash=digest(wrapped) if wrapped is not None else None, approval=approval)


@pytest.mark.parametrize("with_effect,approved,coefficient,role", [
    (False, False, .7, "not_applied"), (True, False, .7, "experimental"),
    (True, True, .7, "applied"), (True, True, 0., "applied"),
])
def test_original_series_law_and_selection_replay_exactly(case, with_effect, approved, coefficient, role):
    args = packet(case, with_effect=with_effect, approved=approved, coefficient=coefficient)
    before = canonical_bytes(args)
    payload = calculate_context_payload(**args)
    result = payload["result"]
    assert result["role"] == role
    assert result["used_markets"]["series_winner_a"] + result["used_markets"]["series_winner_b"] == 1.
    if role != "applied" or coefficient == 0:
        for part in ("params", "markets"):
            assert canonical_bytes(result["used_"+part]) == canonical_bytes(args["base"][part])
    else:
        assert result["used_markets"]["series_winner_a"] < args["base"]["markets"]["series_winner_a"]
    key = context_payload_key(payload)
    assert replay_context_payload(payload, key=key, effect_artifact=args["effect_artifact"], approval=args["approval"]) == payload
    assert canonical_bytes(args) == before


@pytest.mark.parametrize("change", ["schedule", "participant", "preprocessing", "feature-version", "missing-ref"])
def test_unapplied_esports_still_binds_complete_original_inputs(case, change):
    args = deepcopy(packet(case, with_effect=False))
    if change == "schedule":
        args["event"]["schedule_revision"] = "native-schedule-2"
    elif change == "participant":
        args["event"]["home_id"] = "pandascore:esports:team:99"
    elif change == "preprocessing":
        args["preprocessing_refs"] = ["e"*64]
    elif change == "feature-version":
        args["features"]["version"] = "esports-unreviewed-v2"
    else:
        args["observation_refs"] = []
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        calculate_context_payload(**args)


def test_esports_card_projection_cannot_fit_or_recalculate_or_access_io(case, monkeypatch):
    args = packet(case, approved=True)
    payload = calculate_context_payload(**args)
    reference = context_consumer_reference(context_payload_key(payload), payload)
    def forbidden(*args, **kwargs):
        pytest.fail("stored market projection must not calculate or access sources")
    monkeypatch.setattr("context_models.esports._replay", forbidden)
    monkeypatch.setattr("context_models.esports.apply_esports_effect", forbidden)
    monkeypatch.setattr("context_models.esports.series_probability", forbidden)
    monkeypatch.setattr("sqlite3.connect", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    for market in args["base"]["markets"]:
        result = project_context_market(payload, reference, market)
        assert result["used_probability"] == payload["result"]["used_markets"][market]
        assert result["context_ref"] == reference


def test_esports_full_replay_rejects_rehashed_comparison_rewrite(case):
    args = packet(case)
    payload = calculate_context_payload(**args)
    changed = deepcopy(payload)
    result = changed["result"]
    probability = result["comparison_params"]["p_a"] + .001
    result["comparison_params"] = {"p_a": probability}
    result["comparison_markets"] = {"series_winner_a": probability, "series_winner_b": 1.-probability}
    # The input key intentionally does not certify an arbitrary output.
    with pytest.raises(ContextIntegrityError):
        replay_context_payload(changed, key=context_payload_key(changed),
            effect_artifact=args["effect_artifact"], approval=args["approval"])


def test_actual_esports_law_runs_once_for_two_shared_b3_consumers(case, tmp_path, monkeypatch):
    from context_models import esports
    from context_snapshots import compute_once
    args = packet(case)
    # Construct only the input identity, not a throwaway context calculation.
    key = context_payload_key({"schema": 1, "kind": "context-worker-snapshot-v1",
        **args, "approval_hash": None})
    calls, original = [], esports.apply_esports_effect
    def calculate(*a, **kw):
        calls.append("actual-owning-comparison")
        return original(*a, **kw)
    monkeypatch.setattr(esports, "apply_esports_effect", calculate)
    path = tmp_path/"context.sqlite"
    def consumer(_):
        return compute_once(path, key, lambda: calculate_context_payload(**args))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consumer, range(2)))
    assert calls == ["actual-owning-comparison"]
    assert canonical_bytes(results[0]) == canonical_bytes(results[1])
    reference = context_consumer_reference(key, results[0])
    assert {project_context_market(item, reference, "series_winner_a")["context_ref"]["key"] for item in results} == {key}
