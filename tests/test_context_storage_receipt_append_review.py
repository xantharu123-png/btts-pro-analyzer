"""Independent Task49 small receipt SQL/semantic/lifetime probes.

No product or corpus-owner mutation; malformed persisted rows and fault hooks
are disposable test fixtures, not admitted source truth or a writer catalogue.
UTF-16 fixtures exercise SQL transport only, not a copied-main writer profile.
"""
from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3

import pytest

import context_observations as legacy
from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection, TrackedCursor
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_storage_v2 import receipt_append as module
from context_storage_v2.contracts import StorageIntegrityError, StorageLimitError
from context_storage_v2.sqlite_profile import SQLiteWriterPlan, open_fresh_writer


NOW = datetime(2026, 9, 12, 15, 0, 1, 765432, tzinfo=timezone.utc)
SCHEMA = ("context_contents", "context_observations", "context_event_receipts")
FIELDS = ("content_digest", "event_key", "observed_at", "schedule_revision",
          "source", "subject_id", "kind")


def _record():
    return dict(event_key="provider:tennis:native-11", sport="tennis", competition="ATP",
        format="best-of-3", subject_id="player:native-7", kind="workload", source="provider",
        source_schema="match-row-v1", source_revision="rev:11", schedule_revision="schedule-3",
        published_at="2026-09-12T13:30:00+02:00", publication_proof={"untrusted_ref": "local:7"},
        valid_from="2026-09-12T11:00:00-04:00", valid_until=None, complete=True,
        payload={"duration_minutes": 71, "sets": [6, 4], "label": "東京\0🎾"})


def _with(**changes):
    result = _record()
    result.update(changes)
    return result


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _oracle(record, clock=NOW):
    # Independent expected values for these deliberately ordinary aware dates;
    # this is not a replacement validator or a hash-shell acceptance path.
    content = deepcopy(record)
    for field in ("published_at", "valid_from", "valid_until"):
        if content[field] is not None:
            content[field] = datetime.fromisoformat(content[field]).astimezone(timezone.utc).isoformat(
                timespec="microseconds").replace("+00:00", "Z")
    observed = clock.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    payload = _json(content)
    content_id = _sha(payload)
    receipt_id = _sha(_json({"content_digest": content_id, "observed_at": observed}))
    row = (receipt_id, content_id, content["event_key"], observed, content["schedule_revision"],
           content["source"], content["subject_id"], content["kind"])
    return row, payload


def _physical(connection, schema="main"):
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = None
        observations = cursor.execute(f"SELECT * FROM {schema}.context_observations ORDER BY digest").fetchall()
        contents = cursor.execute(f"SELECT * FROM {schema}.context_contents ORDER BY content_digest").fetchall()
    return observations, contents


@contextmanager
def _writer(tmp_path, *, encoding="UTF-8", cap=2 * 1024**2):
    output = tmp_path / "append-main.sqlite"
    if encoding == "UTF-8":
        writer = open_fresh_writer(output, plan=SQLiteWriterPlan(cap))
        con = writer.connection
    else:
        writer = None
        con = sqlite3.connect(output, factory=TrackedConnection, isolation_level=None,
                             autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)
        con.execute("PRAGMA temp_store=MEMORY").close()
        con.execute(f"PRAGMA encoding='{encoding}'").close()
        con.execute("BEGIN IMMEDIATE").close()
    try:
        for name in SCHEMA:
            con.execute(_SCHEMA[name]).close()
        yield con, writer, output
    finally:
        if writer is not None:
            writer.close()
        else:
            con.close()


@pytest.mark.parametrize("sport", ["football", "tennis", "basketball", "ice_hockey", "esports"])
@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_real_owner_and_independent_canonical_identity_match_for_all_sports(tmp_path, sport, encoding):
    value = _with(sport=sport, event_key=f"provider:{sport}:native-11")
    original = deepcopy(value)
    expected_row, expected_payload = _oracle(value)
    old = tmp_path / "legacy-reference.sqlite"
    expected_id = legacy.append_observation(old, value, observed_at=NOW)
    with _writer(tmp_path, encoding=encoding) as (con, writer, output):
        before = con.transaction_generation
        assert module.append_observation_in_connection(con, value, observed_at=NOW) == expected_id == expected_row[0]
        assert _physical(con) == ([expected_row], [(expected_row[1], expected_payload)])
        with closing(sqlite3.connect(old)) as ref:
            assert _physical(con) == _physical(ref)
        assert con.execute("PRAGMA main.encoding").fetchone() == (encoding,)
        assert con.transaction_generation == before and con.in_transaction
        assert value == original
        # No append-owned commit: the explicit fixture owner commits once.
        if writer is None:
            con.commit()
        else:
            writer.commit_build()
        with closing(sqlite3.connect(output.as_uri() + "?mode=ro", uri=True)) as cold:
            assert _physical(cold) == ([expected_row], [(expected_row[1], expected_payload)])


def test_distinct_types_negative_zero_and_receipt_clock_alias_preserve_full_bytes(tmp_path):
    variants = [None, False, 0, 0.0, -0.0, 2**90, "\0", {"b": 1, "a": [True, 2.5]}]
    old = tmp_path / "legacy-reference.sqlite"
    identifiers = []
    with _writer(tmp_path) as (con, writer, _output):
        for value in variants:
            record = _with(payload={"measurement": value})
            expected, raw = _oracle(record)
            actual = module.append_observation_in_connection(con, record, observed_at=NOW)
            assert actual == expected[0] == legacy.append_observation(old, record, observed_at=NOW)
            identifiers.append(actual)
        assert len(set(identifiers)) == len(variants)
        alias = NOW.astimezone(timezone(timedelta(hours=-9, minutes=-30)))
        record = _with(payload={"measurement": variants[-1]})
        assert module.append_observation_in_connection(con, record, observed_at=alias) == identifiers[-1]
        new = module.append_observation_in_connection(con, record, observed_at=NOW + timedelta(microseconds=1))
        assert new != identifiers[-1]
        legacy.append_observation(old, record, observed_at=NOW + timedelta(microseconds=1))
        with closing(sqlite3.connect(old)) as ref:
            assert _physical(con) == _physical(ref)
        assert len(writer._handles) == 0
        writer.check_profile()


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_every_stored_index_nul_tail_is_bounded_before_python_readback(tmp_path, monkeypatch, field, encoding):
    record = _record()
    expected, payload = _oracle(record)
    with _writer(tmp_path, encoding=encoding) as (con, _writer_owner, _output):
        module.append_observation_in_connection(con, record, observed_at=NOW)
        con.execute(f'UPDATE context_observations SET "{field}"=?', ("x\0" + "z" * 32768,)).close()
        before = _physical(con)
        actual_fetch = TrackedCursor.fetchone
        fetched = []

        def measured(cursor):
            row = actual_fetch(cursor)
            fetched.append(row)
            if row is not None:
                assert all(not isinstance(item, (str, bytes)) or len(item) <= len(payload) for item in row)
            return row

        with monkeypatch.context() as patch:
            patch.setattr(TrackedCursor, "fetchone", measured)
            with pytest.raises(ContextIntegrityError):
                module.append_observation_in_connection(con, record, observed_at=NOW)
        assert fetched and fetched[-1] is None
        assert _physical(con) == before
        assert con.in_transaction


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("kind", ["same-size-text", "blob"])
def test_all_index_type_or_equal_length_semantic_collisions_refuse_without_repair(tmp_path, field, kind):
    record = _record()
    expected, _payload = _oracle(record)
    with _writer(tmp_path) as (con, _owner, _output):
        module.append_observation_in_connection(con, record, observed_at=NOW)
        column_index = 1 + FIELDS.index(field)
        old = expected[column_index]
        changed = "x" * len(old) if kind == "same-size-text" else old.encode("ascii")
        con.execute(f'UPDATE context_observations SET "{field}"=?', (changed,)).close()
        before = _physical(con)
        with pytest.raises(ContextIntegrityError):
            module.append_observation_in_connection(con, record, observed_at=NOW)
        assert _physical(con) == before


@pytest.mark.parametrize("kind", ["same-size-blob", "smaller-blob", "larger-blob", "text"])
def test_content_collision_is_not_repaired_and_prior_pending_work_survives(tmp_path, kind):
    value = _record()
    expected, payload = _oracle(value)
    incoming = _with(source_revision="revision-12")
    incoming_row, incoming_payload = _oracle(incoming)
    with _writer(tmp_path) as (con, _owner, _output):
        module.append_observation_in_connection(con, value, observed_at=NOW)
        wrong = {"same-size-blob": b"x" * len(incoming_payload), "smaller-blob": b"",
                 "larger-blob": b"x" * 65536, "text": incoming_payload.decode("utf-8")}[kind]
        con.execute("INSERT INTO context_contents VALUES (?,?)", (incoming_row[1], wrong)).close()
        before = _physical(con)
        with pytest.raises(ContextIntegrityError):
            module.append_observation_in_connection(con, incoming, observed_at=NOW)
        assert _physical(con) == before
        assert before[0] == [expected] and (expected[1], payload) in before[1]


@pytest.mark.parametrize("stage", ["context_contents", "context_observations"])
@pytest.mark.parametrize("action", ["IGNORE", "FAIL", "ABORT", "ROLLBACK"])
def test_actual_trigger_statement_outcome_has_no_partial_success(tmp_path, stage, action):
    # Isolated SQLite fault fixture, explicitly not a permitted C schema.
    with _writer(tmp_path) as (con, _owner, _output):
        module.append_observation_in_connection(con, _record(), observed_at=NOW)
        before = _physical(con)
        generation = con.transaction_generation
        con.execute("CREATE TABLE fault_audit(value TEXT)").close()
        raise_sql = "RAISE(IGNORE)" if action == "IGNORE" else f"RAISE({action},'injected SQL outcome')"
        con.execute(f"CREATE TRIGGER fault BEFORE INSERT ON {stage} BEGIN "
                    f"INSERT INTO fault_audit VALUES ('partial'); SELECT {raise_sql}; END").close()
        with pytest.raises((ContextIntegrityError, StorageIntegrityError)):
            module.append_observation_in_connection(con, _with(source_revision="new-r"), observed_at=NOW)
        if action == "ROLLBACK":
            assert not con.in_transaction and con.transaction_generation != generation
            assert con.execute("SELECT name FROM sqlite_schema").fetchall() == []
        else:
            assert con.in_transaction and con.transaction_generation == generation
            assert _physical(con) == before
            assert con.execute("SELECT * FROM fault_audit").fetchall() == []


@pytest.mark.parametrize("stage", ["context_contents", "context_observations"])
def test_actual_sqlite_interrupt_does_not_forge_rollback_or_return_identity(tmp_path, stage):
    with _writer(tmp_path) as (con, _owner, _output):
        module.append_observation_in_connection(con, _record(), observed_at=NOW)
        generation = con.transaction_generation
        armed, interrupted = [], []

        def trace(statement):
            if statement.startswith("INSERT OR IGNORE INTO main." + stage):
                armed.append(True)

        def progress():
            if armed and not interrupted:
                interrupted.append(True)
                return 1
            return 0

        con.set_trace_callback(trace)
        con.set_progress_handler(progress, 1)
        try:
            with pytest.raises(StorageIntegrityError) as caught:
                module.append_observation_in_connection(con, _with(source_revision="next-r"), observed_at=NOW)
        finally:
            con.set_trace_callback(None)
            con.set_progress_handler(None, 0)
        assert armed and interrupted == [True]
        assert isinstance(caught.value.__cause__, sqlite3.DatabaseError)
        assert caught.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_INTERRUPT
        assert not con.in_transaction and con.transaction_generation != generation
        assert con.execute("SELECT name FROM sqlite_schema").fetchall() == []


@pytest.mark.parametrize("phase", ["release", "close"])
@pytest.mark.parametrize("action", ["commit-restart", "rollback-restart", "autocommit-restart"])
def test_actual_final_boundary_generation_change_never_rolls_back_new_transaction(
        tmp_path, monkeypatch, phase, action):
    with _writer(tmp_path) as (con, _owner, _output):
        execute, close = TrackedCursor.execute, TrackedCursor.close
        performed = []

        def change():
            if performed:
                return
            performed.append(True)
            if action == "commit-restart":
                con.commit()
            elif action == "rollback-restart":
                con.rollback()
            else:
                con.autocommit = True
                con.autocommit = sqlite3.LEGACY_TRANSACTION_CONTROL
            con.execute("BEGIN").close()
            con.execute("CREATE TABLE unrelated_new_generation(value TEXT)").close()
            con.execute("INSERT INTO unrelated_new_generation VALUES ('retain')").close()

        def executed(cursor, sql, *args, **kwargs):
            result = execute(cursor, sql, *args, **kwargs)
            if phase == "release" and sql.startswith("RELEASE v2_receipt_append_"):
                change()
            return result

        def closed(cursor):
            result = close(cursor)
            if phase == "close":
                change()
            return result

        with monkeypatch.context() as patch:
            patch.setattr(TrackedCursor, "execute", executed)
            patch.setattr(TrackedCursor, "close", closed)
            with pytest.raises(StorageIntegrityError):
                module.append_observation_in_connection(con, _record(), observed_at=NOW)
        assert performed == [True]
        assert con.in_transaction
        assert con.execute("SELECT * FROM unrelated_new_generation").fetchall() == [("retain",)]


def test_main_qualification_does_not_append_into_shadow_temp_tables(tmp_path):
    # TEMP shadow fixture is outside the native closed schema; this tests the
    # SQL namespace itself, not permission to install such tables in a build.
    with _writer(tmp_path) as (con, _owner, _output):
        for table in SCHEMA[:2]:
            con.execute(f"CREATE TEMP TABLE {table} AS SELECT * FROM main.{table}").close()
        identity = module.append_observation_in_connection(con, _record(), observed_at=NOW)
        expected, raw = _oracle(_record())
        assert identity == expected[0]
        assert _physical(con) == ([expected], [(expected[1], raw)])
        assert _physical(con, "temp") == ([], [])


def test_existing_unrelated_nul_key_is_not_a_prefix_collision_or_global_validation(tmp_path):
    expected, payload = _oracle(_record())
    with _writer(tmp_path) as (con, _owner, _output):
        unrelated_content = expected[1] + "\0unrelated"
        unrelated_row = (expected[0] + "\0unrelated", unrelated_content, *expected[2:])
        con.execute("INSERT INTO context_contents VALUES (?,?)", (unrelated_content, b"unvalidated")).close()
        con.execute("INSERT INTO context_observations VALUES (?,?,?,?,?,?,?,?)", unrelated_row).close()
        identity = module.append_observation_in_connection(con, _record(), observed_at=NOW)
        receipts, contents = _physical(con)
        assert identity == expected[0]
        assert set(receipts) == {expected, unrelated_row}
        assert set(contents) == {(expected[1], payload), (unrelated_content, b"unvalidated")}
        # Success is only the actual incoming receipt; no unrelated row was
        # verified, cleaned or silently promoted into a VerifiedReceiptMapping.


def test_actual_full_and_toobig_keep_distinct_transaction_outcomes(tmp_path):
    with _writer(tmp_path, cap=32768) as (con, _owner, _output):
        before = con.transaction_generation
        with pytest.raises(StorageLimitError) as caught:
            module.append_observation_in_connection(con, _with(payload={"label": "x" * 98304}), observed_at=NOW)
        assert caught.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_FULL
        assert not con.in_transaction and con.transaction_generation != before
    second = tmp_path / "length-case"
    second.mkdir()
    with _writer(second) as (con, _owner, _output):
        module.append_observation_in_connection(con, _record(), observed_at=NOW)
        expected = _physical(con)
        before = con.transaction_generation
        prior_limit = con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024)
        try:
            with pytest.raises(StorageLimitError) as caught:
                module.append_observation_in_connection(con, _with(payload={"label": "x" * 4096}), observed_at=NOW)
            assert caught.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_TOOBIG
        finally:
            con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, prior_limit)
        assert con.in_transaction and con.transaction_generation == before
        assert _physical(con) == expected


@pytest.mark.parametrize("changes", [
    {"source": "unicode-Ω"}, {"event_key": "provider:tennis:1\0hidden"},
    {"payload": {"details": [{"fairPrice": 1.2}]}}, {"publication_proof": {"ROI": 2}},
    {"published_at": "2026-09-12T15:00:01.765433Z"},
    {"valid_until": "2026-09-12T15:00:00Z"}, {"payload": {"number": float("inf")}},
])
def test_additional_semantic_rejections_match_legacy_and_run_no_sql(tmp_path, changes):
    old = tmp_path / "legacy-reference.sqlite"
    value = _with(**changes)
    with _writer(tmp_path) as (con, _owner, _output):
        statements = []
        con.set_trace_callback(statements.append)
        try:
            with pytest.raises(ContextContractError) as reference:
                legacy.append_observation(old, value, observed_at=NOW)
            with pytest.raises(type(reference.value)):
                module.append_observation_in_connection(con, value, observed_at=NOW)
        finally:
            con.set_trace_callback(None)
        assert statements == []
        assert _physical(con) == ([], [])
