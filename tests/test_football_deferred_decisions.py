"""Offline deferred storage boundaries; synthetic games are not qualification."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

import football_context_decisions as decisions
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_models.football_original_publication import FootballOriginalBudget, FootballOriginalPublication
from context_training_helpers import NOW
from model_artifacts import canonical_bytes
from test_football_joint_worker import original_case, isolated, capture_report


def rows(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT digest,kind,payload,created_at FROM artifacts ORDER BY digest").fetchall()


def enqueue(budget, packet, *, later=2):
    path, case, _ = packet
    budget.defer_context_decisions(path, capture_report([case["case"]["payload"]["replay_ref"]]),
                                   decision_at=NOW+timedelta(minutes=later))


def budget(maximum=32768):
    return FootballOriginalBudget(max_worker_payload_bytes=maximum, max_source_payload_bytes=0)


def test_defer_freezes_first_real_clock_without_writes_or_original_byte_debit(isolated, monkeypatch):
    owner = budget()
    before = rows(isolated[0])
    enqueue(owner, isolated)
    enqueue(owner, isolated, later=12)
    assert owner.remaining_payload_bytes == 32768 and rows(isolated[0]) == before
    assert len(owner._decisions) == 1 and owner._decision_bytes <= 32768
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(minutes=13))
    report = owner.finish_optional_comparisons()
    assert report["events"][0]["status"] == "captured"
    from context_models.dataset import _reader
    with _reader(isolated[0]) as connection:
        value = decisions.resolve_decision(connection, report["events"][0]["decision_ref"],
                                            latest=decisions.canonical_timestamp(NOW+timedelta(minutes=14)))
    assert value["payload"]["decision_at"] == decisions.canonical_timestamp(NOW+timedelta(minutes=2))
    saved = rows(isolated[0])
    assert owner.finish_optional_comparisons() == report and rows(isolated[0]) == saved
    report["events"].clear()
    assert owner.finish_optional_comparisons()["events"]  # detached return
    with pytest.raises(ContextContractError, match="finished"):
        enqueue(owner, isolated)


def test_two_actual_original_batches_keep_exact_priority_at_tight_worker_budget(tmp_path, monkeypatch):
    from test_football_opponent_publication import two_event_worker, objects
    original_kwargs = FootballOriginalPublication.model_kwargs
    defer = False

    def kwargs(self, **options):
        result = original_kwargs(self, **options)
        capture = result["original_capture"]
        def completed(original):
            capture(original)
            if defer:
                available = self.remaining_payload_bytes
                self._budget.defer_context_decisions(self.path, self.report(),
                                                     decision_at=NOW+timedelta(minutes=1))
                assert self.remaining_payload_bytes == available
        return {**result, "original_capture": completed}

    monkeypatch.setattr(FootballOriginalPublication, "model_kwargs", kwargs)
    measure = tmp_path/"measure"
    measure.mkdir()
    path, _, _, _, _ = two_event_worker(measure, monkeypatch, separate_batches=True, finalize=False)
    original_bytes = sum(len(value["bytes"]) for value in objects(path).values())
    defer = True
    tight = tmp_path/"tight"
    tight.mkdir()
    path, shared, owners, _, _ = two_event_worker(tight, monkeypatch, payload_limit=original_bytes,
                                                separate_batches=True, finalize=False)
    assert [owner.report()["published_count"] for owner in owners] == [1, 1]
    assert shared.remaining_payload_bytes == 0
    originals = rows(path)
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(minutes=2))
    report = shared.finish_optional_comparisons()
    assert [row["status"] for row in report["events"]] == ["budget-exhausted", "budget-exhausted"]
    assert report["inserted_payload_bytes"] == 0 and rows(path) == originals
    assert shared.report()["inserted_payload_bytes"] == original_bytes


def test_deferred_actual_creation_after_start_declines_without_backdating(isolated, monkeypatch):
    owner = budget()
    enqueue(owner, isolated)
    before = rows(isolated[0])
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(hours=3))
    report = owner.finish_optional_comparisons()
    assert report["events"][0]["status"] == "unavailable"
    assert report["events"][0]["reason"] == "decision_publication_missed_prematch"
    assert owner.remaining_payload_bytes == 32768 and rows(isolated[0]) == before


def test_deferred_proof_rechecks_original_and_source_inside_transaction(isolated, monkeypatch):
    owner = budget()
    enqueue(owner, isolated)
    pending = next(iter(owner._decisions.values()))
    pending["payload"]["observation_refs_hash"] = "a"*64
    before = rows(isolated[0])
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(minutes=3))
    with pytest.raises(ContextIntegrityError, match="source revision"):
        owner.finish_optional_comparisons()
    assert rows(isolated[0]) == before and owner.remaining_payload_bytes == 32768
    assert owner._sealed


def test_deferred_native_kickoff_cannot_be_replaced_by_queue_metadata(isolated, monkeypatch):
    owner = budget()
    enqueue(owner, isolated)
    pending = next(iter(owner._decisions.values()))
    pending["scheduled_start"] = decisions.canonical_timestamp(NOW+timedelta(days=3))
    before = rows(isolated[0])
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(minutes=3))
    with pytest.raises(ContextIntegrityError, match="kickoff"):
        owner.finish_optional_comparisons()
    assert rows(isolated[0]) == before and owner.remaining_payload_bytes == 32768


def test_pending_inventory_is_bounded_without_retaining_owners_or_receipts(isolated, monkeypatch):
    owner = budget(1)  # queue cap does not increase this existing write envelope
    prototype = decisions.prepare_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]),
        decision_at=NOW+timedelta(minutes=2))["events"][0]
    def prepared(_path, _report, **_kwargs):
        return {"events": [deepcopy(prototype)], "unprocessed_events": 0}
    monkeypatch.setattr(decisions, "prepare_capture_decisions", prepared)
    for index in range(40):
        prototype["binding_ref"] = f"{index:064x}"
        prototype["payload"]["binding_ref"] = prototype["binding_ref"]
        owner.defer_context_decisions(isolated[0], {}, decision_at=NOW)
    assert len(owner._decisions) == 32 and owner._decision_unprocessed == 8
    assert owner._decision_bytes == sum(len(canonical_bytes(value)) for value in owner._decisions.values()) <= 32768
    assert owner.remaining_payload_bytes == 1
    assert all(set(value) == {"binding_ref", "payload", "scheduled_start"} for value in owner._decisions.values())


def test_already_stored_decision_is_reused_with_no_leftover_bytes(isolated, monkeypatch):
    clock = NOW+timedelta(minutes=2)
    monkeypatch.setattr(decisions, "_now", lambda: clock+timedelta(seconds=1))
    stored = decisions.publish_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]), decision_at=clock)
    owner = budget(0)
    enqueue(owner, isolated, later=4)
    before = rows(isolated[0])
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(minutes=5))
    report = owner.finish_optional_comparisons()
    assert report["events"][0] == {**stored["events"][0], "status": "reused"}
    assert report["inserted_payload_bytes"] == 0 and rows(isolated[0]) == before


@pytest.mark.parametrize("complete_first", [False, True])
def test_partial_original_reports_do_not_use_complete_decision_slots(isolated, complete_first):
    binding = isolated[1]["case"]["payload"]["replay_ref"]
    report = capture_report([*(f"{index:064x}" for index in range(33)), binding])
    for row in report["events"][:-1]:
        row.update(status="partial", source_state="partial")
    if complete_first:
        report["events"].reverse()
    prepared = decisions.prepare_capture_decisions(isolated[0], report,
        decision_at=NOW+timedelta(minutes=2), max_events=1)
    assert prepared["unprocessed_events"] == 0 and len(prepared["events"]) == 1
    assert prepared["events"][0]["binding_ref"] == binding and prepared["events"][0]["payload"] is not None


@pytest.mark.parametrize("complete_first", [False, True])
def test_complete_proof_replaces_unavailable_slot_but_not_reverse(isolated, monkeypatch, complete_first):
    actual = decisions.prepare_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]),
        decision_at=NOW+timedelta(minutes=2))["events"][0]
    owner = budget(1)
    current = [actual]
    monkeypatch.setattr(decisions, "prepare_capture_decisions",
        lambda *_a, **_k: {"events": deepcopy(current), "unprocessed_events": 0})
    unavailable = [{"binding_ref": f"{index:064x}", "payload": None,
                    "scheduled_start": None, "reason": "original_native_xg_receipt_unavailable"} for index in range(40)]
    sequence = [actual, *unavailable] if complete_first else [*unavailable, actual]
    for row in sequence:
        current[:] = [row]
        owner.defer_context_decisions(isolated[0], {}, decision_at=NOW)
    assert len(owner._decisions) == 32 and owner._decision_bytes <= 32768
    assert owner._decisions[actual["binding_ref"]] == actual
    assert owner._decision_unprocessed == 9 and owner.remaining_payload_bytes == 1


def test_replacing_unavailable_cannot_enlarge_queue_byte_cap(isolated, monkeypatch):
    actual = decisions.prepare_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]),
        decision_at=NOW+timedelta(minutes=2))["events"][0]
    owner = budget(1)
    current = [{"binding_ref": "a"*64, "payload": None, "scheduled_start": None, "reason": "absent"}]
    monkeypatch.setattr(decisions, "MAX_DECISION_BYTES", 5)
    monkeypatch.setattr(decisions, "prepare_capture_decisions",
        lambda *_a, **_k: {"events": deepcopy(current), "unprocessed_events": 0})
    owner.defer_context_decisions(isolated[0], {}, decision_at=NOW)
    before = deepcopy(owner._decisions)
    current[:] = [actual]
    owner.defer_context_decisions(isolated[0], {}, decision_at=NOW)
    assert owner._decisions == before and owner._decision_unprocessed == 1
    assert owner._decision_bytes <= 5*32 and owner.remaining_payload_bytes == 1


def test_later_unavailable_attempt_cannot_erase_same_binding_genuine_proof(isolated, monkeypatch):
    actual = decisions.prepare_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]),
        decision_at=NOW+timedelta(minutes=2))["events"][0]
    owner = budget()
    current = [actual]
    monkeypatch.setattr(decisions, "prepare_capture_decisions",
        lambda *_a, **_k: {"events": deepcopy(current), "unprocessed_events": 0})
    owner.defer_context_decisions(isolated[0], {}, decision_at=NOW)
    before = owner._decision_bytes
    current[:] = [{"binding_ref": actual["binding_ref"], "payload": None,
                   "scheduled_start": None, "reason": "source_bound_exceeded"}]
    owner.defer_context_decisions(isolated[0], {}, decision_at=NOW+timedelta(minutes=4))
    assert owner._decisions == {actual["binding_ref"]: actual} and owner._decision_bytes == before
    assert owner.remaining_payload_bytes == 32768
    monkeypatch.setattr(decisions, "_now", lambda: NOW+timedelta(minutes=5))
    report = owner.finish_optional_comparisons()
    assert report["events"][0]["status"] == "captured"


@pytest.mark.parametrize("cross_start", [False, True])
def test_delayed_original_read_uses_actual_new_writer_clock(isolated, monkeypatch, cross_start):
    owner = budget()
    enqueue(owner, isolated)
    actual = decisions._load_publication
    writer_clock = [NOW+timedelta(minutes=3)]
    def delayed(*args, **kwargs):
        result = actual(*args, **kwargs)
        writer_clock[0] = NOW+(timedelta(hours=3) if cross_start else timedelta(minutes=4))
        return result
    monkeypatch.setattr(decisions, "_load_publication", delayed)
    monkeypatch.setattr(decisions, "_now", lambda: writer_clock[0])
    before = rows(isolated[0])
    report = owner.finish_optional_comparisons()
    if cross_start:
        assert report["events"][0]["status"] == "unavailable" and rows(isolated[0]) == before
        assert owner.remaining_payload_bytes == 32768
    else:
        assert report["events"][0]["status"] == "captured"
        stored = next(row for row in rows(isolated[0]) if row[0] == report["events"][0]["decision_ref"])
        assert stored[3] == decisions.canonical_timestamp(NOW+timedelta(minutes=4))


def test_delayed_postinsert_readback_crossing_start_rolls_back_without_debit(isolated, monkeypatch):
    owner = budget()
    enqueue(owner, isolated)
    actual = decisions.resolve_decision
    writer_clock = [NOW+timedelta(minutes=3)]
    def delayed(*args, **kwargs):
        result = actual(*args, **kwargs)
        writer_clock[0] = NOW+timedelta(hours=3)
        return result
    monkeypatch.setattr(decisions, "resolve_decision", delayed)
    monkeypatch.setattr(decisions, "_now", lambda: writer_clock[0])
    before = rows(isolated[0])
    report = owner.finish_optional_comparisons()
    assert report["events"][0]["status"] == "unavailable"
    assert report["events"][0]["reason"] == "decision_readback_missed_prematch"
    assert owner.remaining_payload_bytes == 32768 and rows(isolated[0]) == before
