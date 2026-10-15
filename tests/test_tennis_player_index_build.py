"""Real SQLite receipts, rollback, signed cursors and operator boundaries."""
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

from context_runtime import _SCHEMA
from context_models.contracts import digest, normalize_observation
from context_sources.tennis_status import normalize_tennis_status
from context_tennis_index import IndexBudgetExceeded, read_index_state
from model_artifacts import canonical_bytes, ArtifactIntegrityError


def builder():
    assert importlib.util.find_spec("context_tennis_index_build") is not None, "bounded builder is missing"
    return importlib.import_module("context_tennis_index_build")


def database(tmp_path):
    path = tmp_path / "context.sqlite"
    with sqlite3.connect(path) as connection:
        for sql in _SCHEMA.values():
            connection.execute(sql)
    return path


def insert(path, event=101, *, rowid=None, hour=10, players=("1", "9")):
    clock = datetime(2026, 10, 15, hour, tzinfo=timezone.utc)
    native = {"id": str(event), "date": "2026-10-16T12:00:00Z",
        "competitors": [{"id": player} for player in players],
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}}}
    content, = normalize_tennis_status("ATP", "189-2026", native,
        grouping_slug="mens-singles", observed_at=clock)
    content = normalize_observation(content, observed_at=clock)
    observed = f"2026-10-15T{hour:02d}:00:00.000000Z"
    content_hash = digest(content)
    receipt_hash = digest({"content_digest": content_hash, "observed_at": observed})
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT OR IGNORE INTO context_contents VALUES (?,?)", (content_hash, canonical_bytes(content)))
        fields = (receipt_hash, content_hash, content["event_key"], observed,
                  content["schedule_revision"], "espn", content["subject_id"], "event_status")
        if rowid is None:
            connection.execute("INSERT INTO context_observations VALUES (?,?,?,?,?,?,?,?)", fields)
        else:
            connection.execute("INSERT INTO context_observations(rowid,digest,content_digest,event_key,observed_at,schedule_revision,source,subject_id,kind) VALUES (?,?,?,?,?,?,?,?,?)", (rowid, *fields))
    return receipt_hash


def state(path):
    with sqlite3.connect(path) as connection:
        return read_index_state(connection)


def memberships(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT * FROM tennis_player_events ORDER BY tour,player_id,event_key").fetchall()


def test_missing_database_is_not_created(tmp_path):
    api = builder()
    missing = tmp_path / "absent.sqlite"
    for operation in (api.initialize_index, api.build_index, api.disable_index, api.index_status):
        with pytest.raises(FileNotFoundError):
            operation(missing)
        assert not missing.exists()


def test_chunk_rollback_does_not_advance_cursor(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    assert state(path).covered_rowid is None
    original = api._upsert_membership
    def interrupt(connection, member, logical_bytes):
        original(connection, member, logical_bytes)
        raise IndexBudgetExceeded("simulated interruption after real membership write")
    monkeypatch.setattr(api, "_upsert_membership", interrupt)
    result = api.build_index(path)
    assert result.status != "ready"
    assert result.covered_rowid is None
    assert memberships(path) == []
    assert state(path).logical_bytes == 4096
    monkeypatch.setattr(api, "_upsert_membership", original)
    assert api.build_index(path).status == "ready"


def test_resume_drains_concurrent_insert_without_gap(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    original = api._build_chunk
    inserted = False
    def interleave(*args, **kwargs):
        nonlocal inserted
        value = original(*args, **kwargs)
        if not inserted:
            inserted = True
            insert(path, 102)  # independent real writer after a chunk commit
        return value
    monkeypatch.setattr(api, "_build_chunk", interleave)
    result = api.build_index(path)
    assert result.status == "ready"
    assert result.covered_rowid == 2
    assert len(memberships(path)) == 4
    assert state(path).source_generation == state(path).verified_source_generation


def test_negative_rowid_and_legacy_insert_before_cursor(tmp_path):
    api = builder()
    path = database(tmp_path)
    insert(path, rowid=-8)
    api.initialize_index(path)
    assert api.build_index(path).covered_rowid == -8
    insert(path, 102, rowid=-10)
    assert state(path).status == "invalid"
    result = api.build_index(path)
    assert result.status == "ready"
    assert result.scanned_rows == 2  # rebuild, not just MAX(rowid) equality
    assert result.covered_rowid == -8
    assert len(memberships(path)) == 4


def test_late_receipt_moves_minimum_and_tie_is_digest_ordered(tmp_path):
    api = builder()
    path = database(tmp_path)
    insert(path, hour=11)
    api.initialize_index(path)
    assert api.build_index(path).status == "ready"
    early = insert(path, hour=9)
    tied = insert(path, hour=9, players=("1", "8"))
    result = api.build_index(path)
    assert result.status == "ready"
    one = next(row for row in memberships(path) if row[1].endswith(":1"))
    assert one[3:] == ("2026-10-15T09:00:00.000000Z", min(early, tied))
    assert result.logical_bytes == 4096 + sum(len(canonical_bytes(row)) for row in memberships(path))
    assert result.logical_bytes <= 64 * 1024**2


def test_size_and_lock_deadlines_abort_before_ready(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    monkeypatch.setattr(api, "MAX_LOGICAL_BYTES", 4096)
    assert api.build_index(path).status != "ready"
    assert state(path).covered_rowid is None
    lock = sqlite3.connect(path)
    try:
        lock.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        result = api.build_index(path, seconds=0.15)
        assert time.monotonic() - started < 0.8
        assert result.status != "ready"
        assert result.stop_reason == "deadline"
    finally:
        lock.rollback()
        lock.close()


def test_disable_without_index_is_no_ddl_and_status_is_read_only(tmp_path):
    api = builder()
    path = database(tmp_path)
    before = path.read_bytes()
    api.disable_index(path)
    assert path.read_bytes() == before
    assert api.index_status(path) is None
    assert path.read_bytes() == before
    api.initialize_index(path)
    assert api.build_index(path).status == "ready"
    before = path.read_bytes()
    assert api.index_status(path).status == "ready"
    assert path.read_bytes() == before
    api.disable_index(path)
    assert state(path).status == "invalid"


def test_corrupt_receipt_rolls_back_not_budget_or_ready(tmp_path):
    api = builder()
    path = database(tmp_path)
    insert(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE context_contents SET payload=?", (b"{}",))
    api.initialize_index(path)
    with pytest.raises(ValueError):
        api.build_index(path)
    assert state(path).covered_rowid is None
    assert memberships(path) == []


def test_cli_exit_codes_and_missing_file(tmp_path):
    builder()
    script = Path(__file__).resolve().parents[1] / "scripts" / "tennis_player_index.py"
    path = database(tmp_path)
    def run(command, *extra):
        return subprocess.run([sys.executable, "-B", str(script), command, str(path), *extra], capture_output=True, text=True)
    assert run("status").returncode == 3
    assert run("build").returncode == 2
    assert run("initialize").returncode == 0
    assert run("build", "--seconds", "0").returncode == 3
    completed = run("build")
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "ready"
    assert run("disable").returncode == 0


def test_cli_operator_db_flag_and_argument_order(tmp_path):
    builder()
    script = Path(__file__).resolve().parents[1] / "scripts" / "tennis_player_index.py"
    path = database(tmp_path)
    for command in (["init", "--db", str(path)],
                    ["build", "--seconds", "45", "--db", str(path)],
                    ["status", "--db", str(path)], ["disable", "--db", str(path)]):
        result = subprocess.run([sys.executable, "-B", str(script), *command], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    missing = subprocess.run([sys.executable, "-B", str(script), "init", "--db", str(path.parent / "missing.sqlite")], capture_output=True, text=True)
    assert missing.returncode == 2
    assert not (path.parent / "missing.sqlite").exists()


def test_chunk_rows_range_seek_and_prior_committed_cursor_survive_interrupt(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    # Noncandidate rows need not have JSON bodies decoded at all.
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO context_contents VALUES (?,?)", ("0" * 64, b"not json"))
        connection.executemany("INSERT INTO context_observations VALUES (?,?,?,?,?,?,?,?)",
            [(str(i), "0" * 64, "other", "clock", "revision", "other", "subject", "other") for i in range(513)])
    insert(path, 101)
    api.initialize_index(path)
    original = api._build_chunk
    chunks = []
    def interrupt_after_first(*args, **kwargs):
        if chunks:
            raise IndexBudgetExceeded("interrupted between commits")
        result = original(*args, **kwargs)
        chunks.append(result[0])
        return result
    monkeypatch.setattr(api, "_build_chunk", interrupt_after_first)
    stopped = api.build_index(path)
    assert chunks == [512]
    assert stopped.scanned_rows == 512
    assert stopped.covered_rowid == 512
    assert stopped.status != "ready"
    monkeypatch.setattr(api, "_build_chunk", original)
    resumed = api.build_index(path)
    assert resumed.status == "ready"
    assert resumed.scanned_rows == 2
    assert len(memberships(path)) == 2


def test_oversized_candidate_checked_before_body_or_ready(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE context_contents SET payload=zeroblob(?)", (2 * 1024**2 + 1,))
    api.initialize_index(path)
    def forbidden_decode(*args):
        pytest.fail("oversized content body must not be decoded")
    monkeypatch.setattr(api, "_decode_receipt", forbidden_decode)
    result = api.build_index(path)
    assert result.status != "ready"
    assert result.stop_reason == "chunk_bytes"
    assert result.covered_rowid is None


def test_rewrite_and_external_membership_change_force_rebuild(tmp_path):
    api = builder()
    path = database(tmp_path)
    insert(path, 101)
    insert(path, 102)
    api.initialize_index(path)
    assert api.build_index(path).status == "ready"
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM context_observations WHERE rowid=1")
        connection.execute("UPDATE tennis_player_events SET first_receipt_digest=?", ("f" * 64,))
    rebuilt = api.build_index(path)
    assert rebuilt.status == "ready"
    assert rebuilt.scanned_rows == 1
    assert {row[2] for row in memberships(path)} == {"espn:tennis:ATP:match:102"}
    assert not any(row[4] == "f" * 64 for row in memberships(path))


def test_real_slow_projection_aborts_chunk_within_shared_deadline(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    original = api.index.project_memberships
    def slow(receipt):
        time.sleep(0.12)
        return original(receipt)
    monkeypatch.setattr(api.index, "project_memberships", slow)
    result = api.build_index(path, seconds=0.08)
    assert result.status != "ready"
    assert result.stop_reason == "deadline"
    assert result.covered_rowid is None
    assert memberships(path) == []


def test_status_rejects_stale_ready_projector_without_writing(tmp_path):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    api.build_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE tennis_player_index_state SET projector_sha256=?", ("0" * 64,))
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        api.index_status(path)
    assert path.read_bytes() == before
    rebuilt = api.build_index(path)
    assert rebuilt.status == "ready"
    assert rebuilt.scanned_rows == 1


def test_large_invalid_index_cleanup_is_resumable_not_one_delete(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    old = [("ATP", f"player:{i}", "old:event", "2026-10-15T09:00:00.000000Z", "0" * 64) for i in range(600)]
    with sqlite3.connect(path) as connection:
        connection.executemany("INSERT INTO tennis_player_events VALUES (?,?,?,?,?)", old)
        connection.execute("UPDATE tennis_player_index_state SET projector_sha256=?,logical_bytes=?",
            ("0" * 64, 4096 + sum(len(canonical_bytes(row)) for row in old)))
        originals = connection.execute("SELECT * FROM context_observations").fetchall(), connection.execute("SELECT * FROM context_contents").fetchall()
    original = api._build_chunk
    committed = []
    def stop_after_one(*args, **kwargs):
        if committed:
            raise IndexBudgetExceeded("interrupted reset")
        result = original(*args, **kwargs)
        committed.append(result)
        return result
    monkeypatch.setattr(api, "_build_chunk", stop_after_one)
    partial = api.build_index(path)
    assert partial.status != "ready"
    assert len(memberships(path)) == 88  # at most 512 derived removals/commit
    assert state(path).status == "invalid"
    assert state(path).covered_rowid is None
    assert state(path).index_generation != state(path).verified_index_generation
    monkeypatch.setattr(api, "_build_chunk", original)
    assert api.build_index(path).status == "ready"
    assert len(memberships(path)) == 2
    with sqlite3.connect(path) as connection:
        assert (connection.execute("SELECT * FROM context_observations").fetchall(), connection.execute("SELECT * FROM context_contents").fetchall()) == originals


def test_real_sqlite_progress_interrupt_rolls_back_nested_savepoint(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    original = api._upsert_membership
    def long_sql(connection, member, logical_bytes):
        connection.execute("SAVEPOINT partial_membership")
        original(connection, member, logical_bytes)
        connection.execute("""WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL
            SELECT x+1 FROM n WHERE x<100000000) SELECT sum(x) FROM n""").fetchone()
        connection.execute("RELEASE partial_membership")
        pytest.fail("real SQLite progress handler should interrupt recursive SQL")
    monkeypatch.setattr(api, "_upsert_membership", long_sql)
    started = time.monotonic()
    result = api.build_index(path, seconds=0.12)
    assert time.monotonic() - started < 0.8
    assert result.status != "ready"
    assert result.stop_reason == "deadline"
    assert result.covered_rowid is None
    assert memberships(path) == []


def test_exclusive_schema_lock_is_budget_not_integrity_error(tmp_path):
    api = builder()
    path = database(tmp_path)
    api.initialize_index(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        result = api.build_index(path, seconds=0.1)
        assert result.status != "ready"
        assert result.stop_reason == "deadline"
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.parametrize("column,value", [("schema_version", 2), ("db_identity", "[0,0]"),
    ("logical_bytes", 4095), ("logical_bytes", 64 * 1024**2 + 1)])
def test_unknown_version_identity_and_impossible_accounting_fail_closed(tmp_path, column, value):
    api = builder()
    path = database(tmp_path)
    api.initialize_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE tennis_player_index_state SET {column}=?", (value,))
    before = path.read_bytes()
    for operation in (api.initialize_index, api.build_index, api.index_status):
        with pytest.raises(ArtifactIntegrityError):
            operation(path)
    assert path.read_bytes() == before


def test_readiness_tail_reflects_concurrent_append_before_bounded_stop(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    insert(path)
    api.initialize_index(path)
    original = api._build_chunk
    calls = []
    def append_then_stop(*args, **kwargs):
        if len(calls) == 2:
            raise IndexBudgetExceeded("bounded stop")
        value = original(*args, **kwargs)
        calls.append(value)
        if len(calls) == 1:
            insert(path, 102)
        return value
    monkeypatch.setattr(api, "_build_chunk", append_then_stop)
    result = api.build_index(path)
    assert result.status != "ready"
    assert result.covered_rowid == 2
    assert result.source_tail_rowid == 2


def test_content_sum_splits_chunks_before_next_body(tmp_path, monkeypatch):
    api = builder()
    path = database(tmp_path)
    for event in (101, 102, 103):
        insert(path, event)
    api.initialize_index(path)
    with sqlite3.connect(path) as connection:
        length = connection.execute("SELECT max(length(payload)) FROM context_contents").fetchone()[0]
    monkeypatch.setattr(api, "MAX_CHUNK_BYTES", length + length // 2)
    original = api._build_chunk
    chunks = []
    def record(*args, **kwargs):
        result = original(*args, **kwargs)
        chunks.append(result[0])
        return result
    monkeypatch.setattr(api, "_build_chunk", record)
    result = api.build_index(path)
    assert result.status == "ready"
    assert chunks == [1, 1, 1, 0]
    assert result.scanned_rows == 3
    assert len(memberships(path)) == 6


def test_default_call_still_caps_real_writer_wait_at_two_seconds(tmp_path):
    api = builder()
    path = database(tmp_path)
    api.initialize_index(path)
    lock = sqlite3.connect(path)
    try:
        lock.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        result = api.build_index(path)  # default 45s must not become lock wait
        elapsed = time.monotonic() - started
        assert 1.5 < elapsed < 2.5
        assert result.status != "ready"
        assert result.stop_reason == "deadline"
        assert state(path).status == "building"
    finally:
        lock.rollback()
        lock.close()
