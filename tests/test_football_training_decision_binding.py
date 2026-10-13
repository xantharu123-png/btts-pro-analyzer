"""Offline source-clock proof mechanics, not predictive-quality evidence."""
from copy import deepcopy
from datetime import timedelta
import shutil
import sqlite3
from pathlib import Path

import pytest

import football_context_decisions as decisions
from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.football_training import build_joint_training_case
from context_models.replay import ReplayUnavailable
from context_models.training_contracts import validate_resolved_case
from context_training_helpers import NOW, envelope
from test_football_joint_training import source_case
from test_football_joint_worker import capture_report


@pytest.fixture(scope="module")
def original(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        return source_case(tmp_path_factory.mktemp("decision-training"), patch)


@pytest.fixture
def isolated(original, tmp_path):
    path, case, config = deepcopy(original)
    return shutil.copyfile(path, tmp_path / "decision.db"), case, config


def build(isolated, decision):
    path, case, config = isolated
    payload = case["case"]["payload"]
    return build_joint_training_case(path, binding_ref=payload["replay_ref"],
        outcome_ref=payload["outcome_ref"], identity_ref=payload["event_identity_hash"],
        config=config, as_of=NOW+timedelta(hours=6), decision_at=decision)


def publish(isolated, monkeypatch):
    clock = NOW+timedelta(minutes=2)
    monkeypatch.setattr(decisions, "_now", lambda: clock+timedelta(seconds=1))
    return decisions.publish_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]), decision_at=clock)


def test_old_original_cutoff_keeps_exact_four_artifact_case(isolated):
    before = Path(isolated[0]).read_bytes()
    actual = build(isolated, NOW)
    assert actual == isolated[1] and len(actual["artifacts"]) == 4
    assert Path(isolated[0]).read_bytes() == before


def test_later_cutoff_without_actual_decision_is_not_trainable(isolated):
    with pytest.raises(ReplayUnavailable, match="later_context_decision_unpublished"):
        build(isolated, NOW+timedelta(minutes=2))


def test_genuine_later_decision_is_fifth_exact_source_artifact(isolated, monkeypatch):
    report = publish(isolated, monkeypatch)
    ref = report["events"][0]["decision_ref"]
    actual = build(isolated, NOW+timedelta(minutes=2))
    assert len(actual["artifacts"]) == 5 and ref in actual["artifacts"]
    proof = actual["artifacts"][ref]
    assert proof["kind"] == decisions.DECISION_KIND
    assert proof["payload"]["decision_at"] == actual["case"]["payload"]["base"]["cutoff"]
    assert validate_resolved_case(actual, config=isolated[2]) == actual
    with pytest.raises(ReplayUnavailable, match="later_context_decision_unpublished"):
        build(isolated, NOW+timedelta(minutes=3))


@pytest.mark.parametrize("change", ["missing", "clock", "sources", "binding"])
def test_detached_later_decision_cannot_be_rehashed_or_dropped(isolated, monkeypatch, change):
    ref = publish(isolated, monkeypatch)["events"][0]["decision_ref"]
    actual = build(isolated, NOW+timedelta(minutes=2))
    proof = actual["artifacts"].pop(ref)
    if change != "missing":
        if change == "clock": proof["payload"]["decision_at"] = canonical_timestamp(NOW+timedelta(minutes=1))
        elif change == "sources": proof["payload"]["observation_refs_hash"] = "f"*64
        else: proof["payload"]["binding_ref"] = "f"*64
        proof = envelope(proof["kind"], proof["payload"])
        actual["artifacts"][proof["digest"]] = proof
    with pytest.raises(ContextIntegrityError, match="decision"):
        validate_resolved_case(actual, config=isolated[2])


def test_corrupt_physical_later_decision_is_not_laundered_as_missing(isolated, monkeypatch):
    ref = publish(isolated, monkeypatch)["events"][0]["decision_ref"]
    with sqlite3.connect(isolated[0]) as connection:
        raw = connection.execute("SELECT payload FROM artifacts WHERE digest=?", (ref,)).fetchone()[0]
        connection.execute("UPDATE artifacts SET payload=? WHERE digest=?", (raw.replace(b'"schema":1', b'"schema":2'), ref))
    with pytest.raises(ContextIntegrityError):
        build(isolated, NOW+timedelta(minutes=2))


def test_duplicate_same_clock_proof_cannot_choose_a_convenient_hash(isolated, monkeypatch):
    import json
    from model_artifacts import put_artifact
    ref = publish(isolated, monkeypatch)["events"][0]["decision_ref"]
    with sqlite3.connect(isolated[0]) as connection:
        payload = json.loads(connection.execute("SELECT payload FROM artifacts WHERE digest=?", (ref,)).fetchone()[0])
    payload["observation_refs_hash"] = "f"*64
    put_artifact(isolated[0], kind=decisions.DECISION_KIND, payload=payload,
        created_at=NOW+timedelta(minutes=2, seconds=1))
    with pytest.raises(ContextIntegrityError, match="duplicate physical context decision"):
        build(isolated, NOW+timedelta(minutes=2))


def test_later_proof_physically_after_case_is_not_causal(isolated, monkeypatch):
    ref = publish(isolated, monkeypatch)["events"][0]["decision_ref"]
    with sqlite3.connect(isolated[0]) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
            (canonical_timestamp(NOW+timedelta(hours=7)), ref))
    with pytest.raises(ContextIntegrityError):
        build(isolated, NOW+timedelta(minutes=2))
