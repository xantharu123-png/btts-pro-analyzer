"""Actual live writes: derived failure must not discard valid source receipts."""
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

import context_observations as observations
import context_tennis_index as index
from context_models.contracts import ContextIntegrityError
from context_runtime import _SCHEMA
from context_sources.tennis_status import normalize_tennis_status
from context_tennis_index_build import initialize_index, build_index
from model_artifacts import canonical_bytes


CLOCK = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)


def record(event=101, *, clock=CLOCK):
    native = {"id": str(event), "date": "2026-10-16T12:00:00Z",
        "competitors": [{"id": "1"}, {"id": "9"}],
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}}}
    value, = normalize_tennis_status("ATP", "189-2026", native,
        grouping_slug="mens-singles", observed_at=clock)
    return value


def football():
    return dict(event_key="api-football:football:1", sport="football", competition="39",
        format="90min", subject_id="player:7", kind="availability", source="api-football",
        source_schema="injuries-v3", source_revision="r1", schedule_revision="s1",
        published_at=None, publication_proof=None, valid_from=CLOCK.isoformat(),
        valid_until=None, complete=False, payload={"status": "out"})


def database(tmp_path, *, ready=True):
    path = tmp_path / "context.sqlite"
    with sqlite3.connect(path) as connection:
        for sql in _SCHEMA.values():
            connection.execute(sql)
    initialize_index(path)
    if ready:
        assert build_index(path).status == "ready"
    return path


def snapshot(path):
    with sqlite3.connect(path) as connection:
        return (index.read_index_state(connection),
            connection.execute("SELECT * FROM tennis_player_events ORDER BY tour,player_id,event_key").fetchall(),
            connection.execute("SELECT * FROM context_observations ORDER BY digest").fetchall(),
            connection.execute("SELECT * FROM context_contents ORDER BY content_digest").fetchall())


def test_receipt_and_membership_commit_or_rollback_together(tmp_path, monkeypatch):
    path = database(tmp_path)
    receipt = observations.append_observation(path, record(), observed_at=CLOCK)
    state, members, receipts, contents = snapshot(path)
    assert state.status == "ready"
    assert len(members) == 2
    assert {row[4] for row in members} == {receipt}
    assert state.source_generation == state.verified_source_generation == 1
    assert state.index_generation == state.verified_index_generation == 2
    assert state.covered_rowid == 1
    assert state.logical_bytes == 4096 + sum(len(canonical_bytes(row)) for row in members)
    original = index.finish_index_append
    def fail(connection, *, context):
        original(connection, context=context)
        raise sqlite3.OperationalError("commit boundary fixture")
    monkeypatch.setattr(index, "finish_index_append", fail)
    with pytest.raises(sqlite3.OperationalError, match="commit boundary"):
        observations.append_observation(path, record(102), observed_at=CLOCK)
    assert snapshot(path) == (state, members, receipts, contents)


def test_duplicate_new_clock_and_older_clock(tmp_path):
    path = database(tmp_path)
    value = record()
    first = observations.append_observation(path, value, observed_at=CLOCK)
    before = snapshot(path)
    assert observations.append_observation_batch(path, ((value, CLOCK), (value, CLOCK))) == (first, first)
    assert snapshot(path) == before
    later = CLOCK + timedelta(hours=1)
    observations.append_observation_batch(path, ((record(clock=later), later),) * 2)
    assert len(snapshot(path)[1]) == 2
    assert {row[4] for row in snapshot(path)[1]} == {first}
    # The source valid_from must not postdate an earlier physical receipt.
    earlier = CLOCK - timedelta(hours=1)
    old = observations.append_observation(path, record(clock=earlier), observed_at=earlier)
    state, members, receipts, contents = snapshot(path)
    assert state.status == "ready"
    assert state.source_generation == state.verified_source_generation == 3
    assert state.index_generation == state.verified_index_generation == 4
    assert {row[3:] for row in members} == {("2026-10-15T09:00:00.000000Z", old)}
    assert all(row in receipts for row in before[2])
    assert all(row in contents for row in before[3])


def test_budget_invalidates_index_but_keeps_valid_sports_receipt(tmp_path, monkeypatch):
    path = database(tmp_path)
    observations.append_observation(path, record(), observed_at=CLOCK)
    before = snapshot(path)
    assert hasattr(index, "MAX_APPEND_LOGICAL_BYTES"), "derived append budget is missing"
    monkeypatch.setattr(index, "MAX_APPEND_LOGICAL_BYTES", before[0].logical_bytes)
    refs = observations.append_observation_batch(path, ((record(102), CLOCK), (football(), CLOCK)))
    state, members, receipts, contents = snapshot(path)
    assert state.status == "invalid"
    assert members == before[1]
    assert {row[0] for row in receipts}.issuperset(refs)
    assert all(row in receipts for row in before[2])
    assert all(row in contents for row in before[3])


@pytest.mark.parametrize("error", [sqlite3.OperationalError("real SQL failure"), ContextIntegrityError("source damage")])
def test_sql_and_source_errors_still_rollback_batch(tmp_path, monkeypatch, error):
    path = database(tmp_path)
    before = snapshot(path)
    assert hasattr(index, "observe_index_append"), "atomic append hook is missing"
    original = index.project_memberships
    def fail(receipt):
        original(receipt)
        raise error
    monkeypatch.setattr(index, "project_memberships", fail)
    with pytest.raises(type(error), match=str(error)):
        observations.append_observation_batch(path, ((football(), CLOCK), (record(), CLOCK)))
    assert snapshot(path) == before


@pytest.mark.parametrize("dirty", ["building", "invalid", "source", "index", "version", "projector", "cursor"])
def test_append_never_certifies_an_unprocessed_gap(tmp_path, dirty):
    path = database(tmp_path)
    with sqlite3.connect(path) as connection:
        if dirty in {"building", "invalid"}:
            connection.execute("UPDATE tennis_player_index_state SET status=?", (dirty,))
        else:
            assignment = {"source": "source_generation=source_generation+1",
                "index": "index_generation=index_generation+1", "version": "schema_version=2",
                "projector": "projector_sha256='" + "a" * 64 + "'", "cursor": "covered_rowid=99"}[dirty]
            connection.execute("UPDATE tennis_player_index_state SET " + assignment)
    before = snapshot(path)
    ref = observations.append_observation(path, record(), observed_at=CLOCK)
    state, members, receipts, contents = snapshot(path)
    assert state.status != "ready"
    assert members == before[1]
    assert state.verified_source_generation == before[0].verified_source_generation
    assert state.verified_index_generation == before[0].verified_index_generation
    assert ref in {row[0] for row in receipts}


def test_absent_index_keeps_legacy_no_ddl(tmp_path):
    path = tmp_path / "legacy.sqlite"
    ref = observations.append_observation(path, record(), observed_at=CLOCK)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT digest FROM context_observations").fetchone() == (ref,)
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'tennis_%'").fetchall()
        connection.execute("BEGIN IMMEDIATE")
        assert hasattr(index, "begin_index_append"), "held-connection append API is missing"
        assert index.begin_index_append(connection) is None
        assert connection.in_transaction


def test_unknown_projection_invalidates_but_known_schema_damage_rolls_back(tmp_path):
    path = database(tmp_path)
    ref = observations.append_observation(path, {**record(), "source_schema": "future-tennis-v99"}, observed_at=CLOCK)
    state, members, receipts, _ = snapshot(path)
    assert state.status == "invalid"
    assert members == []
    assert ref in {row[0] for row in receipts}
    # A known schema must still validate its native participant namespace.
    other = tmp_path / "known"
    other.mkdir()
    path = database(other)
    before = snapshot(path)
    value = record()
    value = {**value, "payload": {**value["payload"], "tour": "WTA"}}
    with pytest.raises(ValueError):
        observations.append_observation(path, value, observed_at=CLOCK)
    assert snapshot(path) == before


def test_additional_time_budget_rolls_back_derived_savepoint(tmp_path, monkeypatch):
    path = database(tmp_path)
    before = snapshot(path)
    assert hasattr(index, "_upsert_append_membership"), "derived savepoint is missing"
    original = index._upsert_append_membership
    def exhausted(*args):
        original(*args)
        raise index.IndexBudgetExceeded("elapsed fixture after real derived insert")
    monkeypatch.setattr(index, "_upsert_append_membership", exhausted)
    ref = observations.append_observation(path, record(), observed_at=CLOCK)
    after = snapshot(path)
    assert after[0].status == "invalid"
    assert after[0].logical_bytes == before[0].logical_bytes
    assert after[0].index_generation == before[0].index_generation
    assert after[1] == before[1]
    assert ref in {row[0] for row in after[2]}


def test_additional_time_budget_is_cumulative_across_receipts(tmp_path, monkeypatch):
    path = database(tmp_path)
    assert hasattr(index, "_upsert_append_membership"), "cumulative index clock is missing"
    clock = [0.0]
    monkeypatch.setattr(index, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    original = index._upsert_append_membership
    def costly(*args):
        result = original(*args)
        clock[0] += 0.8  # First receipt costs 1.6s; next crosses the 2s total.
        return result
    monkeypatch.setattr(index, "_upsert_append_membership", costly)
    refs = observations.append_observation_batch(path, ((record(), CLOCK), (record(102), CLOCK)))
    state, members, receipts, _ = snapshot(path)
    assert state.status == "invalid"
    assert len(members) == 2
    assert {row[4] for row in members} == {refs[0]}
    assert state.logical_bytes == 4096 + sum(len(canonical_bytes(row)) for row in members)
    assert set(refs) <= {row[0] for row in receipts}


def test_original_retention_budget_still_rolls_back_everything(tmp_path):
    from context_models.football_original_storage import StorageBudgetExceeded
    path = database(tmp_path)
    before = snapshot(path)
    with pytest.raises(StorageBudgetExceeded):
        observations.append_bounded_observation_batch(path, ((record(), CLOCK),), max_new_payload_bytes=0)
    assert snapshot(path) == before


def test_physical_receipt_not_caller_flag_is_admitted(tmp_path):
    path = database(tmp_path)
    assert hasattr(index, "begin_index_append"), "physical admission guard is missing"
    before = snapshot(path)
    with sqlite3.connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        context = index.begin_index_append(connection)
        with pytest.raises(ContextIntegrityError):
            index.observe_index_append(connection, {"digest": "a" * 64, "verified": True}, context=context)
        assert connection.in_transaction
        connection.rollback()
    assert snapshot(path) == before
