"""Native SQLite physical-clock regressions; synthetic data is not qualification."""
from datetime import timedelta
import sqlite3

import pytest

import football_context_decisions as decisions
from context_models.contracts import ContextIntegrityError, canonical_timestamp, digest
from context_models.dataset import _artifact, _reader
from context_models.experiments import _artifact_created_at
from context_training_helpers import NOW
from model_artifacts import canonical_bytes, put_artifact
from test_football_joint_worker import original_case, isolated, capture_report


def clock_payload(isolated, *, decision_seconds):
    """Keep real native ownership; delay only this synthetic binding's insert."""
    path, case, _ = isolated
    binding_ref = case["case"]["payload"]["replay_ref"]
    physical_original = canonical_timestamp(NOW + timedelta(seconds=60))
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
                           (physical_original, binding_ref))
    cutoff = canonical_timestamp(NOW + timedelta(seconds=decision_seconds))
    latest = canonical_timestamp(NOW + timedelta(minutes=3))
    with _reader(path) as connection:
        binding, original, _ = decisions._load_publication(connection, binding_ref, latest=latest)
        assert binding["payload"]["decision_at"] == canonical_timestamp(NOW)
        assert _artifact_created_at(connection, binding_ref) == physical_original
        event = binding["payload"]["native_event"]
        rows = decisions._bounded_receipts(connection, original.to_dict(), cutoff=cutoff)
        decisions._native_binding(binding["payload"], original, rows)
    refs = sorted(row["digest"] for row in rows)
    payload = decisions.validate_decision({"schema": 1, "binding_ref": binding_ref,
        "event_key": event["event_key"], "decision_at": cutoff,
        "observation_refs_hash": digest(refs), "observation_count": len(refs)})
    assert cutoff < event["scheduled_start"]
    return path, payload, event


def stored_proof(path, payload):
    ref = put_artifact(path, kind=decisions.DECISION_KIND, payload=payload,
                       created_at=NOW + timedelta(minutes=2))
    # Verify the public hash and stored payload independently of the clock guard.
    with _reader(path) as connection:
        envelope = _artifact(connection, ref, decisions.DECISION_KIND,
                             latest=canonical_timestamp(NOW + timedelta(minutes=3)))
    assert envelope["digest"] == ref
    assert envelope["payload"] == payload
    return ref


def test_correctly_hashed_decision_before_physical_original_is_rejected(isolated):
    path, payload, _ = clock_payload(isolated, decision_seconds=30)
    ref = stored_proof(path, payload)
    before = path.read_bytes()
    with _reader(path) as connection:
        with pytest.raises(ContextIntegrityError, match="physical original publication"):
            decisions.resolve_decision(connection, ref,
                latest=canonical_timestamp(NOW + timedelta(minutes=3)))
    assert path.read_bytes() == before


def test_existing_impossible_decision_cannot_be_reported_reused_or_write(isolated, monkeypatch):
    path, payload, event = clock_payload(isolated, decision_seconds=30)
    ref = stored_proof(path, payload)
    monkeypatch.setattr(decisions, "_now", lambda: NOW + timedelta(minutes=3))
    before = path.read_bytes()
    with pytest.raises(ContextIntegrityError, match="physical original publication"):
        decisions._publish(path, payload, event, remaining=0)
    assert path.read_bytes() == before
    with _reader(path) as connection:
        assert connection.execute("SELECT digest FROM artifacts WHERE kind=?",
                                  (decisions.DECISION_KIND,)).fetchall() == [(ref,)]


def test_new_impossible_decision_readback_rolls_back_without_writes(isolated, monkeypatch):
    path, payload, event = clock_payload(isolated, decision_seconds=30)
    monkeypatch.setattr(decisions, "_now", lambda: NOW + timedelta(minutes=3))
    before = path.read_bytes()
    with pytest.raises(ContextIntegrityError, match="physical original publication"):
        decisions._publish(path, payload, event, remaining=decisions.MAX_DECISION_BYTES)
    assert path.read_bytes() == before
    with _reader(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind=?",
                                  (decisions.DECISION_KIND,)).fetchone() == (0,)


@pytest.mark.parametrize("decision_seconds", [60, 90, 120])
def test_physical_original_boundary_and_later_cuts_keep_readback_reuse(
        isolated, monkeypatch, decision_seconds):
    path, payload, event = clock_payload(isolated, decision_seconds=decision_seconds)
    monkeypatch.setattr(decisions, "_now", lambda: NOW + timedelta(minutes=3))
    ref, status, inserted = decisions._publish(path, payload, event,
                                             remaining=decisions.MAX_DECISION_BYTES)
    assert status == "captured" and inserted == len(canonical_bytes(payload))
    with _reader(path) as connection:
        saved = decisions.resolve_decision(connection, ref,
            latest=canonical_timestamp(NOW + timedelta(minutes=3)))
    assert saved["payload"]["decision_at"] == canonical_timestamp(
        NOW + timedelta(seconds=decision_seconds))
    before = path.read_bytes()
    monkeypatch.setattr(decisions, "_now", lambda: NOW + timedelta(minutes=4))
    report = decisions.publish_capture_decisions(path, capture_report([payload["binding_ref"]]),
        decision_at=NOW + timedelta(minutes=4), max_run_bytes=0)
    assert report["events"] == [{"binding_ref": payload["binding_ref"],
                                "status": "reused", "decision_ref": ref}]
    assert report["inserted_payload_bytes"] == 0 and path.read_bytes() == before
