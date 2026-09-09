"""No active/caller/hash-only approval can replace an owning D2 report."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_dataset_helpers import BUILT, EVALUATED, copy_packet
from context_models.contracts import ContextIntegrityError
from model_artifacts import put_artifact, publish_slots
from test_context_dataset import prepared


def test_missing_active_approval_returns_none_without_creating_a_database(prepared, tmp_path):
    from context_models.activation import approved_effect
    case = prepared["cases"][-1]["case"]["payload"]
    missing = tmp_path/"missing.db"
    assert approved_effect(missing, effect_hash=prepared["fit"]["effect_hash"],
                           event=case["event"], base=case["base"], features=case["features"]) is None
    assert not missing.exists()


def test_small_actual_replayed_report_cannot_be_promoted_by_a_passed_flag(prepared, tmp_path):
    from context_models.activation import verify_approval
    from context_models.evaluator import evaluate_experiment
    from context_models.dataset import _reader
    packet = copy_packet(prepared, tmp_path)
    result = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    fake = {"schema": 1, "decision": "approved", "hypothesis_id": packet["hypothesis_id"],
        "experiment_hash": packet["experiment_ref"], "report_hash": result["digest"], "effect_hash": packet["fit"]["effect_hash"],
        "dataset_hash": packet["plan"]["dataset_hash"], "event_identity_hash": packet["plan"]["event_identity_hash"],
        "code_revision": packet["plan"]["code_revision"], "policy_version": packet["plan"]["policy_version"],
        **{key: packet["plan"]["family_configs"][0][key] for key in ("base_versions", "sport", "family", "feature_version",
            "population", "coverage", "model_variant", "target_markets", "outcome_contract")},
        "test_events_hash": "0"*64, "evaluated_at": result["payload"]["evaluated_at"]}
    ref = put_artifact(packet["path"], kind="context-approval-v1", payload=fake, created_at=EVALUATED)
    with _reader(packet["path"]) as connection, pytest.raises(ContextIntegrityError):
        verify_approval(connection, ref)


def test_active_unknown_artifact_kind_is_an_integrity_error(prepared, tmp_path):
    from context_models.activation import approved_effect
    packet = copy_packet(prepared, tmp_path)
    ref = put_artifact(packet["path"], kind="free-statistical-row-claim", payload={"passed": True}, created_at=BUILT)
    effect = packet["fit"]["effect_hash"]
    publish_slots(packet["path"], {"effect": effect, "context-approval:"+effect: ref}, expected_manifest=None, published_at=BUILT)
    case = deepcopy(packet["cases"][-1]["case"]["payload"])
    with pytest.raises(ContextIntegrityError):
        approved_effect(packet["path"], effect_hash=effect, event=case["event"], base=case["base"], features=case["features"])


@pytest.mark.parametrize("variant", ["exact", "population", "coverage", "evaluated-after-decision",
                                    "published-after-decision", "uncoupled", "stale-event-reference"])
def test_scoped_lookup_contract_with_explicit_standin_verifier(prepared, tmp_path, monkeypatch, variant):
    """Scope-only unit test: a verifier stand-in is NOT empirical evidence."""
    import context_models.activation as activation
    from context_models.contracts import canonical_timestamp, digest
    packet = copy_packet(prepared, tmp_path)
    effect_ref = packet["fit"]["effect_hash"]
    config = packet["plan"]["family_configs"][0]
    claim = {"schema": 1, "decision": "approved", "hypothesis_id": packet["hypothesis_id"],
        "experiment_hash": packet["experiment_ref"], "report_hash": "0"*64, "effect_hash": effect_ref,
        "dataset_hash": packet["plan"]["dataset_hash"], "event_identity_hash": packet["plan"]["event_identity_hash"],
        "code_revision": packet["plan"]["code_revision"], "policy_version": packet["plan"]["policy_version"],
        **{key: config[key] for key in ("base_versions", "sport", "family", "feature_version", "population",
            "coverage", "model_variant", "target_markets", "outcome_contract")},
        "test_events_hash": "1"*64, "evaluated_at": canonical_timestamp(EVALUATED)}
    # Rebind a structural future request, not a source-replayed case. The true
    # historical verifier remains covered by the rejection test above.
    decision = EVALUATED+timedelta(days=10)
    case = deepcopy(packet["cases"][-1]["case"]["payload"])
    case["base"]["cutoff"] = case["features"]["cutoff"] = canonical_timestamp(decision)
    case["event"]["scheduled_start"] = canonical_timestamp(decision+timedelta(hours=2))
    if variant == "population":
        case["event"]["competition"] = "140"
    if variant == "coverage":
        case["features"]["coverage"]["case"] = "different_scope"
    case["features"]["reference_hash"] = digest({"version": "football-context-reference-v2",
        "base_hash": digest(case["base"]), "event_hash": digest(case["event"]), "preprocessing": []})
    if variant == "stale-event-reference":
        case["event"]["scheduled_start"] = canonical_timestamp(decision+timedelta(hours=3))
    if variant == "evaluated-after-decision":
        claim["evaluated_at"] = canonical_timestamp(decision+timedelta(seconds=1))
    ref = put_artifact(packet["path"], kind="context-approval-v1", payload=claim, created_at=EVALUATED)
    slots = {"context-approval:"+effect_ref: ref}
    if variant != "uncoupled":
        slots["effect"] = effect_ref
    published = decision+timedelta(seconds=1) if variant == "published-after-decision" else EVALUATED
    publish_slots(packet["path"], slots, expected_manifest=None, published_at=published)
    envelope = {"digest": ref, "kind": "context-approval-v1", "payload": claim}
    calls = []
    def standin(connection, expected):
        assert expected == ref and connection.execute("PRAGMA query_only").fetchone() == (1,)
        calls.append(expected)
        return envelope
    monkeypatch.setattr(activation, "verify_approval", standin)
    kwargs = {key: case[key] for key in ("event", "features", "base")}
    if variant in {"uncoupled", "stale-event-reference"}:
        with pytest.raises(ContextIntegrityError):
            activation.approved_effect(packet["path"], effect_hash=effect_ref, **kwargs)
    else:
        actual = activation.approved_effect(packet["path"], effect_hash=effect_ref, **kwargs)
        assert actual == (envelope if variant == "exact" else None)
    assert calls == [ref]
