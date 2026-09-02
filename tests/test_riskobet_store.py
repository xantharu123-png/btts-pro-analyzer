from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from riskobet_domain import (
    ContextState,
    EvidenceStage,
    EventModelSnapshot,
    RiskCandidate,
    RiskRunSnapshot,
    RunStatus,
    ValidationEvidenceArtifact,
    canonical_json,
    canonical_input_hash,
    stable_event_key,
)
from riskobet_settlement import SettlementResult, SettlementStatus
from riskobet_store import (
    SCHEMA_VERSION,
    FrozenRevisionError,
    RiskBetStore,
    _SCHEMA_V1,
    _SCHEMA_V2,
)


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def _snapshot(revision=1, *, event_label="Alpha vs Beta"):
    return EventModelSnapshot(
        event_key=stable_event_key("football", "provider", "fixture-17"),
        sport="football",
        competition="Testliga",
        event_label=event_label,
        starts_at=NOW + timedelta(hours=8),
        modeled_at=NOW,
        input_cutoff_at=NOW - timedelta(minutes=1),
        model_version="football-risk-v1",
        input_hash=canonical_input_hash({"revision": revision}),
    )


def _candidate(snapshot, *, stage=EvidenceStage.RESEARCH, settlement_contract=None):
    return RiskCandidate(
        snapshot_id=snapshot.snapshot_id,
        event_key=snapshot.event_key,
        sport=snapshot.sport,
        competition=snapshot.competition,
        event_label=snapshot.event_label,
        starts_at=snapshot.starts_at,
        market_key="underdog_win",
        market_label="Außenseitersieg",
        selection_key="away",
        selection_label="Beta gewinnt",
        model_probability=0.31,
        cautious_probability=None,
        stage=stage,
        context_state=ContextState.FRESH,
        policy_version="risk-policy-v1",
        pros=("Gute aktuelle Form",),
        cons=("Schwächere Langzeitbasis",),
        settlement_contract=(
            settlement_contract
            if settlement_contract is not None
            else (None if stage is EvidenceStage.RESEARCH else CONTRACT)
        ),
    )


CONTRACT = "riskobet-settlement-v1:football:result_90_minutes:away"


def _validation_artifact(snapshot, candidate, **changes):
    values = dict(
        validation_version="validation-v1",
        policy_version=candidate.policy_version,
        model_version=snapshot.model_version,
        settlement_contract=candidate.settlement_contract,
        walk_forward_sample_size=500,
        predeclared_minimum_sample_size=400,
        hac_brier_advantage_lower_bound=0.01,
        bh_fdr_q=0.04,
        tail_calibration_error=0.03,
        maximum_tail_calibration_error=0.05,
        active_drift=False,
        settlement_rate=0.98,
        minimum_settlement_rate=0.95,
        evaluation_blocks=2,
    )
    values.update(changes)
    return ValidationEvidenceArtifact(**values)


def _run(snapshot, candidate=None, *, minute=1):
    return RiskRunSnapshot(
        started_at=NOW + timedelta(minutes=minute),
        completed_at=NOW + timedelta(minutes=minute, seconds=30),
        status=RunStatus.COMPLETE,
        snapshots=(snapshot,),
        candidates=(() if candidate is None else (candidate,)),
    )


def _write_v1_run(path, run):
    with sqlite3.connect(path) as connection:
        connection.executescript(_SCHEMA_V1)
        run_json = canonical_json(run.to_dict())
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.started_at.isoformat(),
                run.completed_at.isoformat(),
                run.status.value,
                run_json,
                hashlib.sha256(run_json.encode()).hexdigest(),
            ),
        )
        for ordinal, snapshot in enumerate(run.snapshots):
            payload = canonical_json(snapshot.to_dict())
            connection.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.event_key,
                    snapshot.sport,
                    snapshot.model_version,
                    snapshot.input_hash,
                    snapshot.modeled_at.isoformat(),
                    payload,
                    hashlib.sha256(payload.encode()).hexdigest(),
                ),
            )
            connection.execute(
                "INSERT INTO run_snapshots VALUES (?, ?, ?)",
                (run.run_id, snapshot.snapshot_id, ordinal),
            )
        for ordinal, candidate in enumerate(run.candidates):
            payload = canonical_json(candidate.to_dict())
            connection.execute(
                "INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    candidate.candidate_id,
                    candidate.snapshot_id,
                    candidate.event_key,
                    candidate.sport,
                    candidate.policy_version,
                    candidate.stage.value,
                    payload,
                    hashlib.sha256(payload.encode()).hexdigest(),
                ),
            )
            connection.execute(
                "INSERT INTO run_candidates VALUES (?, ?, ?, ?, 0)",
                (run.run_id, candidate.candidate_id, candidate.snapshot_id, ordinal),
            )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()


def test_schema_and_whole_run_append_are_idempotent(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = _run(snapshot, candidate)

    assert store.append_run(run) is True
    assert store.append_run(run) is False

    with sqlite3.connect(store.db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "runs",
            "snapshots",
            "candidates",
            "settlements",
            "stage_events",
            "publication_pointer",
        } <= tables
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1


def test_new_input_hash_appends_revision_without_overwriting_old_snapshot(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    first = _snapshot(1)
    second = _snapshot(2)
    store.append_run(_run(first, _candidate(first), minute=1))
    store.append_run(_run(second, _candidate(second), minute=2))

    with sqlite3.connect(store.db_path) as connection:
        rows = connection.execute(
            "SELECT snapshot_id, input_hash FROM snapshots ORDER BY modeled_at, snapshot_id"
        ).fetchall()
    assert len(rows) == 2
    assert {row[0] for row in rows} == {first.snapshot_id, second.snapshot_id}


def test_same_snapshot_identity_with_changed_content_is_rejected(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    first = _snapshot(event_label="Alpha vs Beta")
    changed = _snapshot(event_label="Altered label")
    run = _run(first)
    store.append_run(run)

    assert first.snapshot_id == changed.snapshot_id
    with pytest.raises(FrozenRevisionError, match="sealed"):
        store.append_snapshot(changed, run.run_id)


def test_candidate_json_and_schema_are_price_neutral(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    store.append_run(_run(snapshot, candidate))

    with sqlite3.connect(store.db_path) as connection:
        payload = connection.execute("SELECT payload_json FROM candidates").fetchone()[0]
        columns = {
            row[1].casefold()
            for row in connection.execute("PRAGMA table_info(candidates)")
        }
    forbidden = ("odds", "quote", "price", "bookmaker", "minimum")
    assert not any(token in payload.casefold() for token in forbidden)
    assert not any(token in column for column in columns for token in forbidden)


def test_settlement_revisions_are_append_only_and_idempotent(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot, stage=EvidenceStage.SHADOW)
    store.append_run(_run(snapshot, candidate))
    kwargs = dict(
        candidate_id=candidate.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        result=SettlementResult(SettlementStatus.UNRESOLVED, "provider_gap"),
        settled_at=NOW + timedelta(days=1),
        detail={"reason": "provider gap"},
    )

    assert store.append_settlement(**kwargs) is True
    assert store.append_settlement(**kwargs) is False
    with pytest.raises(FrozenRevisionError, match="different content"):
        store.append_settlement(
            **{
                **kwargs,
                "result": SettlementResult(SettlementStatus.WIN, "final_score"),
            }
        )

    assert store.append_settlement(
        **{
            **kwargs,
            "result": SettlementResult(SettlementStatus.WIN, "final_score"),
            "settled_at": NOW + timedelta(days=1, minutes=1),
        }
    ) is True
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 2


def test_terminal_append_rejects_unresolved_poll_rows(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot, stage=EvidenceStage.SHADOW)
    store.append_run(_run(snapshot, candidate))

    with pytest.raises(ValueError, match="only terminal"):
        store.append_terminal_settlement(
            candidate_id=candidate.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            result=SettlementResult(SettlementStatus.UNRESOLVED, "provider_gap"),
            settled_at=NOW + timedelta(days=1),
        )


def test_newer_research_revision_does_not_mask_settleable_shadow(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    shadow_snapshot = _snapshot(1)
    research_snapshot = _snapshot(2)
    shadow = _candidate(shadow_snapshot, stage=EvidenceStage.SHADOW)
    research = _candidate(research_snapshot, stage=EvidenceStage.RESEARCH)
    assert shadow.candidate_id == research.candidate_id
    store.append_run(_run(shadow_snapshot, shadow, minute=1))
    store.append_run(_run(research_snapshot, research, minute=2))

    targets = store.load_due_settlement_targets(as_of=NOW + timedelta(days=1))

    assert len(targets) == 1
    assert targets[0]["candidate"]["snapshot_id"] == shadow_snapshot.snapshot_id
    assert store.append_terminal_settlement(
        candidate_id=shadow.candidate_id,
        snapshot_id=shadow_snapshot.snapshot_id,
        result=SettlementResult(SettlementStatus.WIN, "final_score"),
        settled_at=NOW + timedelta(days=1),
    ) is True


def test_equal_time_settleable_revisions_fail_closed(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    first = _snapshot(1)
    second = _snapshot(2)
    first_candidate = _candidate(first, stage=EvidenceStage.SHADOW)
    second_candidate = _candidate(second, stage=EvidenceStage.SHADOW)
    assert first.modeled_at == second.modeled_at
    assert first.input_cutoff_at == second.input_cutoff_at
    assert first_candidate.candidate_id == second_candidate.candidate_id
    store.append_run(_run(first, first_candidate, minute=1))
    store.append_run(_run(second, second_candidate, minute=2))

    future_targets, future_issue_count = store.load_due_settlement_targets_with_issues(
        as_of=NOW + timedelta(hours=1)
    )
    assert future_targets == ()
    assert future_issue_count == 0

    targets, issue_count = store.load_due_settlement_targets_with_issues(
        as_of=NOW + timedelta(days=1)
    )
    assert targets == ()
    assert issue_count == 1
    with pytest.raises(FrozenRevisionError, match="ambiguous equal-time"):
        store.load_due_settlement_targets(as_of=NOW + timedelta(days=1))
    with pytest.raises(FrozenRevisionError, match="ambiguous equal-time"):
        store.append_terminal_settlement(
            candidate_id=first_candidate.candidate_id,
            snapshot_id=first.snapshot_id,
            result=SettlementResult(SettlementStatus.WIN, "final_score"),
            settled_at=NOW + timedelta(days=1),
        )


def test_ambiguous_schedule_revision_does_not_block_unrelated_settlement(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    original_start = NOW + timedelta(hours=6)
    original = EventModelSnapshot(
        event_key=stable_event_key("football", "provider", "fixture-17"),
        sport="football",
        competition="Testliga",
        event_label="Alpha vs Beta",
        starts_at=original_start,
        modeled_at=NOW,
        input_cutoff_at=NOW - timedelta(minutes=1),
        model_version="football-risk-v1",
        input_hash=canonical_input_hash({"revision": 1, "schedule": "original"}),
    )
    postponed_start = original.starts_at + timedelta(hours=2)
    postponed = EventModelSnapshot(
        event_key=original.event_key,
        sport=original.sport,
        competition=original.competition,
        event_label=original.event_label,
        starts_at=postponed_start,
        modeled_at=original.modeled_at,
        input_cutoff_at=original.input_cutoff_at,
        model_version=original.model_version,
        input_hash=canonical_input_hash({"revision": 2, "schedule": "postponed"}),
    )
    original_candidate = _candidate(original, stage=EvidenceStage.SHADOW)
    postponed_candidate = _candidate(postponed, stage=EvidenceStage.SHADOW)
    assert original_candidate.candidate_id == postponed_candidate.candidate_id
    store.append_run(_run(original, original_candidate, minute=1))
    store.append_run(_run(postponed, postponed_candidate, minute=2))

    healthy = EventModelSnapshot(
        event_key=stable_event_key("football", "provider", "fixture-18"),
        sport="football",
        competition="Testliga",
        event_label="Gamma vs Delta",
        starts_at=NOW + timedelta(hours=7),
        modeled_at=NOW + timedelta(minutes=1),
        input_cutoff_at=NOW,
        model_version="football-risk-v1",
        input_hash=canonical_input_hash({"revision": 1, "fixture": 18}),
    )
    healthy_candidate = _candidate(healthy, stage=EvidenceStage.SHADOW)
    store.append_run(_run(healthy, healthy_candidate, minute=3))

    targets, issue_count = store.load_due_settlement_targets_with_issues(
        as_of=NOW + timedelta(days=1)
    )
    assert len(targets) == 1
    assert targets[0]["snapshot"]["snapshot_id"] == healthy.snapshot_id
    assert issue_count == 1
    with pytest.raises(FrozenRevisionError, match="ambiguous equal-time"):
        store.load_due_settlement_targets(as_of=NOW + timedelta(days=1))


def test_evidence_transitions_cannot_skip_shadow_or_rewrite_history(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot, settlement_contract=CONTRACT)
    store.append_run(_run(snapshot, candidate))

    with pytest.raises(ValueError, match="illegal"):
        store.append_stage_event(
            candidate_id=candidate.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            from_stage="RESEARCH",
            to_stage="VALIDATED",
            occurred_at=NOW + timedelta(days=1),
            reason="must not skip shadow",
            validation_version="validation-v1",
        )

    transition = dict(
        candidate_id=candidate.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        from_stage="RESEARCH",
        to_stage="SHADOW",
        occurred_at=NOW + timedelta(hours=1),
        reason="settlement contract frozen",
        validation_version="validation-v1",
    )
    assert store.append_stage_event(**transition) is True
    assert store.append_stage_event(**transition) is False
    with pytest.raises(FrozenRevisionError, match="different content"):
        store.append_stage_event(
            **{**transition, "reason": "rewritten explanation"}
        )


def test_latest_consumer_json_is_atomic_read_model_with_current_stage(tmp_path, monkeypatch):
    latest_path = tmp_path / "consumer" / "riskobet_latest.json"
    store = RiskBetStore(tmp_path / "riskobet.db", latest_path=latest_path)
    snapshot = _snapshot()
    candidate = _candidate(snapshot, settlement_contract=CONTRACT)
    run = _run(snapshot, candidate)
    store.append_run(run)
    store.append_stage_event(
        candidate_id=candidate.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        from_stage="RESEARCH",
        to_stage="SHADOW",
        occurred_at=NOW + timedelta(hours=1),
        reason="settlement contract frozen",
        validation_version="validation-v1",
    )
    calls = []
    real_atomic_write = __import__("runtime_paths").atomic_write_text

    def recording_atomic_write(path, text, *, encoding="utf-8"):
        calls.append((path, text))
        return real_atomic_write(path, text, encoding=encoding)

    monkeypatch.setattr("runtime_paths.atomic_write_text", recording_atomic_write)
    assert store.publish_latest(run.run_id) == latest_path
    payload = store.read_latest()

    assert len(calls) == 1
    assert payload["run_id"] == run.run_id
    assert payload["candidates"][0]["stage"] == "SHADOW"
    assert "observed_odds" not in json.dumps(payload).casefold()
    raw = json.loads(latest_path.read_text(encoding="utf-8"))
    assert raw["payload_digest"]
    assert {key: value for key, value in raw.items() if key != "payload_digest"} == payload
    read_only = object.__new__(RiskBetStore)
    read_only.latest_path = latest_path
    assert read_only.read_latest() == payload


def test_republish_cas_never_rolls_back_a_newer_latest_pointer(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db", tmp_path / "latest.json")
    first_snapshot = _snapshot(1)
    first = _run(first_snapshot, _candidate(first_snapshot), minute=1)
    store.append_run(first)
    store.publish_latest(first.run_id)
    first_digest = json.loads(
        store.latest_path.read_text(encoding="utf-8")
    )["payload_digest"]

    second_snapshot = _snapshot(2)
    second = _run(second_snapshot, _candidate(second_snapshot), minute=2)
    store.append_run(second)
    store.publish_latest(second.run_id)

    assert store.republish_latest_if_current(
        first.run_id,
        expected_payload_digest=first_digest,
    ) is False
    assert store.read_latest()["run_id"] == second.run_id


def test_publish_latest_never_rolls_back_a_newer_latest_pointer(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db", tmp_path / "latest.json")
    older_snapshot = _snapshot(1)
    older = _run(older_snapshot, _candidate(older_snapshot), minute=1)
    newer_snapshot = _snapshot(2)
    newer = _run(newer_snapshot, _candidate(newer_snapshot), minute=2)
    store.append_run(older)
    store.append_run(newer)
    store.publish_latest(newer.run_id)

    assert store.publish_latest(older.run_id) == store.latest_path
    assert store.read_latest()["run_id"] == newer.run_id


def test_invalid_latest_is_repaired_from_durable_selection_not_old_request(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db", tmp_path / "latest.json")
    older_snapshot = _snapshot(1)
    older = _run(older_snapshot, _candidate(older_snapshot), minute=1)
    newer_snapshot = _snapshot(2)
    newer = _run(newer_snapshot, _candidate(newer_snapshot), minute=2)
    store.append_run(older)
    store.append_run(newer)
    store.publish_latest(newer.run_id)
    store.latest_path.write_text("{torn", encoding="utf-8")

    assert store.publish_latest(older.run_id) == store.latest_path
    assert store.read_latest()["run_id"] == newer.run_id


@pytest.mark.parametrize("damage", ("missing", "torn"))
def test_unpublished_newer_failed_run_never_masks_selected_complete_recovery(
    tmp_path,
    damage,
):
    store = RiskBetStore(tmp_path / "riskobet.db", tmp_path / "latest.json")
    snapshot = _snapshot(1)
    complete = _run(snapshot, _candidate(snapshot), minute=1)
    failed = RiskRunSnapshot(
        started_at=NOW + timedelta(minutes=2),
        completed_at=NOW + timedelta(minutes=2, seconds=30),
        status=RunStatus.FAILED,
        errors=("football: source_unavailable",),
    )
    store.append_run(complete)
    store.publish_latest(complete.run_id)
    store.append_run(failed)

    if damage == "missing":
        store.latest_path.unlink()
    else:
        store.latest_path.write_text("{torn", encoding="utf-8")

    recovered = RiskBetStore.recover_latest_from_database(store.db_path)
    assert recovered is not None
    assert recovered["run_id"] == complete.run_id
    assert recovered["status"] == "COMPLETE"

    # No explicit run means repair the durable selection, not the DB-newest
    # run that was intentionally stored without publication.
    store.publish_latest()
    assert store.read_latest()["run_id"] == complete.run_id

    # A FAILED run remains legitimately publishable when explicitly selected.
    store.publish_latest(failed.run_id)
    assert store.read_latest()["run_id"] == failed.run_id
    assert store.read_latest()["status"] == "FAILED"
    assert RiskBetStore.recover_latest_from_database(store.db_path)["run_id"] == failed.run_id


def test_recovery_rejects_tampered_publication_pointer(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db", tmp_path / "latest.json")
    snapshot = _snapshot()
    run = _run(snapshot, _candidate(snapshot))
    store.append_run(run)
    store.publish_latest(run.run_id)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute(
            "UPDATE publication_pointer SET content_hash=?",
            ("0" * 64,),
        )
        connection.commit()

    with pytest.raises(FrozenRevisionError, match="publication pointer content hash"):
        RiskBetStore.recover_latest_from_database(store.db_path)


def test_failed_multirow_append_rolls_back_the_entire_run(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    original = _candidate(snapshot)
    store.append_run(_run(snapshot, original, minute=1))

    changed_candidate = replace(original, model_probability=0.41)
    changed_run = _run(snapshot, changed_candidate, minute=2)
    with pytest.raises(FrozenRevisionError, match="different content"):
        store.append_run(changed_run)

    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        stored_probability = json.loads(
            connection.execute("SELECT payload_json FROM candidates").fetchone()[0]
        )["model_probability"]
    assert stored_probability == 0.31


def test_initial_validated_candidate_is_rejected_by_store_but_read_model_type_remains_valid(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot, stage=EvidenceStage.VALIDATED)

    assert candidate.stage is EvidenceStage.VALIDATED
    with pytest.raises(FrozenRevisionError, match="through a SHADOW promotion"):
        store.append_run(_run(snapshot, candidate))


def test_public_member_apis_cannot_extend_a_sealed_run(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    first = _snapshot(1)
    run = _run(first)
    store.append_run(run)
    second = _snapshot(2)

    with pytest.raises(FrozenRevisionError, match="sealed"):
        store.append_snapshot(second, run.run_id, ordinal=1)
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 1


def test_load_run_detects_row_hash_and_membership_tampering(tmp_path):
    snapshot = _snapshot()
    candidate = _candidate(snapshot)

    hash_store = RiskBetStore(tmp_path / "hash.db")
    hash_run = _run(snapshot, candidate)
    hash_store.append_run(hash_run)
    with sqlite3.connect(hash_store.db_path) as connection:
        payload = json.loads(
            connection.execute("SELECT payload_json FROM candidates").fetchone()[0]
        )
        payload["model_probability"] = 0.99
        connection.execute(
            "UPDATE candidates SET payload_json=?",
            (canonical_json(payload),),
        )
        connection.commit()
    with pytest.raises(FrozenRevisionError, match="content hash mismatch"):
        hash_store.load_run(hash_run.run_id)

    member_store = RiskBetStore(tmp_path / "membership.db")
    member_run = _run(snapshot, candidate)
    member_store.append_run(member_run)
    with sqlite3.connect(member_store.db_path) as connection:
        connection.execute("DELETE FROM run_candidates")
        connection.commit()
    with pytest.raises(FrozenRevisionError, match="membership"):
        member_store.load_run(member_run.run_id)


def test_latest_digest_rejects_silent_payload_changes(tmp_path):
    latest = tmp_path / "latest.json"
    store = RiskBetStore(tmp_path / "riskobet.db", latest_path=latest)
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = _run(snapshot, candidate)
    store.append_run(run)
    store.publish_latest(run.run_id)
    store.publish_latest(run.run_id)

    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload["candidates"][0]["model_probability"] = 0.99
    latest.write_text(canonical_json(payload), encoding="utf-8")

    with pytest.raises(FrozenRevisionError, match="digest mismatch"):
        store.read_latest()


def test_validated_promotion_requires_bound_evidence_and_strict_parent_time(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot, settlement_contract=CONTRACT)
    store.append_run(_run(snapshot, candidate))
    shadow_time = NOW + timedelta(hours=1)
    store.append_stage_event(
        candidate_id=candidate.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        from_stage="RESEARCH",
        to_stage="SHADOW",
        occurred_at=shadow_time,
        reason="prospective settlement contract frozen",
        validation_version="shadow-v1",
    )

    with pytest.raises(ValueError, match="ValidationEvidenceArtifact"):
        store.append_stage_event(
            candidate_id=candidate.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            from_stage="SHADOW",
            to_stage="VALIDATED",
            occurred_at=shadow_time + timedelta(hours=1),
            reason="validation passed",
            validation_version="validation-v1",
        )

    artifact = _validation_artifact(snapshot, candidate)
    mismatched = _validation_artifact(
        snapshot,
        candidate,
        model_version="different-model-v1",
    )
    with pytest.raises(FrozenRevisionError, match="model mismatch"):
        store.append_stage_event(
            candidate_id=candidate.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            from_stage="SHADOW",
            to_stage="VALIDATED",
            occurred_at=shadow_time + timedelta(hours=1),
            reason="validation passed",
            validation_version="validation-v1",
            evidence=mismatched,
        )
    with pytest.raises(FrozenRevisionError, match="strictly increasing"):
        store.append_stage_event(
            candidate_id=candidate.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            from_stage="SHADOW",
            to_stage="VALIDATED",
            occurred_at=shadow_time,
            reason="validation passed",
            validation_version="validation-v1",
            evidence=artifact,
        )

    assert store.append_stage_event(
        candidate_id=candidate.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        from_stage="SHADOW",
        to_stage="VALIDATED",
        occurred_at=shadow_time + timedelta(hours=1),
        reason="validation passed",
        validation_version="validation-v1",
        evidence=artifact,
    ) is True
    payload = store.load_run()
    assert payload["candidates"][0]["stage"] == "VALIDATED"
    assert payload["candidates"][0]["stage_history"][1][
        "parent_stage_event_id"
    ] == payload["candidates"][0]["stage_history"][0]["stage_event_id"]


def test_promotion_and_settlement_reject_price_information(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    snapshot = _snapshot()
    candidate = _candidate(snapshot, stage=EvidenceStage.SHADOW)
    store.append_run(_run(snapshot, candidate))

    with pytest.raises(ValueError, match="price information"):
        store.append_settlement(
            candidate_id=candidate.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            result=SettlementResult(SettlementStatus.WIN, "final_score"),
            settled_at=NOW + timedelta(days=1),
            detail={"bookmaker": "Example"},
        )

    research_store = RiskBetStore(tmp_path / "research.db")
    research = _candidate(snapshot, settlement_contract=CONTRACT)
    research_store.append_run(_run(snapshot, research))
    with pytest.raises(ValueError, match="price information"):
        research_store.append_stage_event(
            candidate_id=research.candidate_id,
            snapshot_id=snapshot.snapshot_id,
            from_stage="RESEARCH",
            to_stage="SHADOW",
            occurred_at=NOW + timedelta(hours=1),
            reason="good odds confirmed",
            validation_version="shadow-v1",
        )


def test_settlement_requires_stage_contract_time_and_newest_prospective_revision(tmp_path):
    result = SettlementResult(SettlementStatus.WIN, "final_score")

    research_store = RiskBetStore(tmp_path / "research.db")
    research_snapshot = _snapshot(10)
    research = _candidate(research_snapshot, settlement_contract=CONTRACT)
    research_store.append_run(_run(research_snapshot, research))
    with pytest.raises(FrozenRevisionError, match="SHADOW or VALIDATED"):
        research_store.append_settlement(
            candidate_id=research.candidate_id,
            snapshot_id=research.snapshot_id,
            result=result,
            settled_at=NOW + timedelta(days=1),
        )

    store = RiskBetStore(tmp_path / "revisions.db")
    first_snapshot = _snapshot(20)
    second_snapshot = replace(
        _snapshot(21),
        modeled_at=NOW + timedelta(minutes=1),
        input_cutoff_at=NOW,
    )
    first = _candidate(first_snapshot, stage=EvidenceStage.SHADOW)
    second = _candidate(second_snapshot, stage=EvidenceStage.SHADOW)
    store.append_run(_run(first_snapshot, first, minute=1))
    store.append_run(_run(second_snapshot, second, minute=2))

    with pytest.raises(FrozenRevisionError, match="newest prospectively"):
        store.append_settlement(
            candidate_id=first.candidate_id,
            snapshot_id=first.snapshot_id,
            result=result,
            settled_at=NOW + timedelta(days=1),
        )
    with pytest.raises(FrozenRevisionError, match="version differs"):
        store.append_settlement(
            candidate_id=second.candidate_id,
            snapshot_id=second.snapshot_id,
            result=result,
            settled_at=NOW + timedelta(days=1),
            settlement_version="riskobet-settlement-v0",
        )
    with pytest.raises(FrozenRevisionError, match="predate"):
        store.append_settlement(
            candidate_id=second.candidate_id,
            snapshot_id=second.snapshot_id,
            result=result,
            settled_at=NOW,
        )
    assert store.append_settlement(
        candidate_id=second.candidate_id,
        snapshot_id=second.snapshot_id,
        result=result,
        settled_at=NOW + timedelta(days=1),
    ) is True


def test_exact_v1_schema_migrates_atomically_to_current_schema_with_data(tmp_path):
    db_path = tmp_path / "riskobet.db"
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = _run(snapshot, candidate)
    _write_v1_run(db_path, run)

    store = RiskBetStore(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert store.load_run(run.run_id)["candidates"][0]["candidate_id"] == candidate.candidate_id


def test_v2_migration_preserves_published_selection_over_newer_failed_run(tmp_path):
    db_path = tmp_path / "riskobet.db"
    latest_path = tmp_path / "latest.json"
    complete = RiskRunSnapshot(
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=30),
        status=RunStatus.COMPLETE,
    )
    failed = RiskRunSnapshot(
        started_at=NOW + timedelta(minutes=1),
        completed_at=NOW + timedelta(minutes=1, seconds=30),
        status=RunStatus.FAILED,
        errors=("football: source_unavailable",),
    )
    with sqlite3.connect(db_path) as connection:
        connection.executescript(_SCHEMA_V2)
        for run in (complete, failed):
            payload_json = canonical_json(run.to_dict())
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run.run_id,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat(),
                    run.status.value,
                    payload_json,
                    hashlib.sha256(payload_json.encode()).hexdigest(),
                ),
            )
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    complete_payload = complete.to_dict()
    latest_path.write_text(
        canonical_json(
            {
                **complete_payload,
                "payload_digest": hashlib.sha256(
                    canonical_json(complete_payload).encode()
                ).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    store = RiskBetStore(db_path, latest_path)
    recovered = RiskBetStore.recover_latest_from_database(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute(
            "SELECT run_id FROM publication_pointer WHERE slot='latest'"
        ).fetchone()[0] == complete.run_id
    assert recovered["run_id"] == complete.run_id
    store.publish_latest()
    assert store.read_latest()["run_id"] == complete.run_id
    store.publish_latest(failed.run_id)
    assert store.read_latest()["run_id"] == failed.run_id


def test_partial_or_tampered_v1_schema_fails_closed_without_migration(tmp_path):
    partial_path = tmp_path / "partial.db"
    with sqlite3.connect(partial_path) as connection:
        connection.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY)")
        connection.commit()
    with pytest.raises(FrozenRevisionError, match="partial or foreign"):
        RiskBetStore(partial_path)

    tampered_path = tmp_path / "tampered.db"
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = _run(snapshot, candidate)
    _write_v1_run(tampered_path, run)
    with sqlite3.connect(tampered_path) as connection:
        connection.execute("UPDATE candidates SET content_hash=?", ("0" * 64,))
        connection.commit()
    with pytest.raises(FrozenRevisionError, match="content hash mismatch"):
        RiskBetStore(tampered_path)
    with sqlite3.connect(tampered_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1


def test_read_only_database_recovery_returns_none_without_creating_anything(tmp_path):
    missing = tmp_path / "not-created" / "riskobet.db"

    assert RiskBetStore.recover_latest_from_database(missing) is None
    assert not missing.parent.exists()


def test_read_only_database_recovery_validates_and_has_no_filesystem_side_effects(tmp_path):
    db_path = tmp_path / "riskobet.db"
    store = RiskBetStore(db_path)
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = _run(snapshot, candidate)
    store.append_run(run)
    store.publish_latest(run.run_id)
    before = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in tmp_path.iterdir()
    }

    recovered = RiskBetStore.recover_latest_from_database(db_path)

    after = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in tmp_path.iterdir()
    }
    assert recovered is not None
    assert recovered["run_id"] == run.run_id
    assert recovered["candidates"][0]["candidate_id"] == candidate.candidate_id
    assert after == before
    assert not list(tmp_path.glob("riskobet.db-*"))


def test_read_only_database_recovery_rejects_v1_foreign_and_corrupt_data(tmp_path):
    v1_path = tmp_path / "v1.db"
    with sqlite3.connect(v1_path) as connection:
        connection.executescript(_SCHEMA_V1)
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    with pytest.raises(FrozenRevisionError, match="requires an existing V3"):
        RiskBetStore.recover_latest_from_database(v1_path)

    foreign_path = tmp_path / "foreign.db"
    with sqlite3.connect(foreign_path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    with pytest.raises(FrozenRevisionError, match="partial or foreign"):
        RiskBetStore.recover_latest_from_database(foreign_path)

    corrupt_path = tmp_path / "corrupt.db"
    store = RiskBetStore(corrupt_path)
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = _run(snapshot, candidate)
    store.append_run(run)
    store.publish_latest(run.run_id)
    connection = sqlite3.connect(corrupt_path)
    try:
        connection.execute("UPDATE candidates SET content_hash=?", ("0" * 64,))
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(FrozenRevisionError, match="content hash mismatch"):
        RiskBetStore.recover_latest_from_database(corrupt_path)

    Path(f"{corrupt_path}-wal").write_bytes(b"pending")
    with pytest.raises(FrozenRevisionError, match="checkpointed standalone"):
        RiskBetStore.recover_latest_from_database(corrupt_path)
