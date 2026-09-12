"""Small real legacy/C append differentials, not native or source approval.

The caller fixtures create their own schemas and fixed-profile writers. The
append operation must never acquire either responsibility for itself.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import context_observations as legacy
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    normalize_observation,
)
from context_runtime_transaction import TrackedConnection, TrackedCursor
from context_storage_v2 import receipt_append as append_module
from context_storage_v2.contracts import StorageIntegrityError, StorageLimitError
from context_storage_v2.sqlite_profile import SQLiteWriterPlan, open_fresh_writer
from model_artifacts import canonical_bytes


NOW = datetime(2026, 9, 12, 12, 34, 56, 123456, tzinfo=timezone.utc)
append = append_module.append_observation_in_connection


def record(**changes):
    return {
        "event_key": "fixture:football:1", "sport": "football",
        "competition": "39", "format": "90min", "subject_id": "player:7",
        "kind": "availability", "source": "fixture", "source_schema": "status-v1",
        "source_revision": "r1", "schedule_revision": "s1",
        "published_at": None, "publication_proof": None,
        "valid_from": NOW.isoformat(), "valid_until": None,
        "complete": False, "payload": {"status": "out"}, **changes,
    }


def rows(connection):
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = None
        return cursor.execute(legacy._SELECT + " ORDER BY r.digest").fetchall()


def contents(connection):
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = None
        return cursor.execute(
            "SELECT content_digest,payload FROM main.context_contents ORDER BY content_digest"
        ).fetchall()


def legacy_rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return rows(connection), contents(connection)


def make_pair(tmp_path, *, cap=2 * 1024**2):
    path = tmp_path / "legacy.sqlite"
    with closing(legacy._connect(path)) as reference:
        schema = reference.execute(
            "SELECT sql FROM sqlite_schema WHERE name IN "
            "('context_contents','context_observations','context_event_receipts') "
            "ORDER BY type DESC,name"
        ).fetchall()
    writer = open_fresh_writer(tmp_path / "new.sqlite", plan=SQLiteWriterPlan(cap))
    try:
        for (sql,) in schema:
            writer.connection.execute(sql).close()
        return path, writer
    except BaseException:
        writer.close()
        raise


@pytest.fixture
def pair(tmp_path):
    path, writer = make_pair(tmp_path)
    try:
        yield path, writer
    finally:
        writer.close()


@pytest.mark.parametrize("value", [
    record(),
    record(payload={"nested": [None, True, False, 0, -2, 0.0, -0.0, 0.125,
                                2**80, "München/東京/🎾\x00tail"]}),
    record(published_at=(NOW - timedelta(hours=1)).isoformat(),
           publication_proof={"untrusted_ref": "fixture:17"}, complete=True),
    record(kind="weather", valid_from=(NOW + timedelta(hours=2)).isoformat(),
           valid_until=(NOW + timedelta(hours=3)).isoformat(), payload={"temperature_c": 22}),
], ids=["ordinary", "json-types-unicode-nul", "publication", "future-validity"])
def test_actual_full_nine_field_rows_and_canonical_bytes_match_legacy(pair, value):
    path, writer = pair
    connection = writer.connection
    generation = connection.transaction_generation
    expected = legacy.append_observation(path, value, observed_at=NOW)
    actual = append(connection, value, observed_at=NOW)
    assert actual == expected
    assert (rows(connection), contents(connection)) == legacy_rows(path)
    stored = rows(connection)[0]
    assert len(stored) == 9 and all(type(item) is str for item in stored[:8])
    assert type(stored[8]) is bytes
    normalized = normalize_observation(value, observed_at=NOW)
    assert stored[8] == canonical_bytes(normalized)
    assert legacy._decode_receipt(stored) == {
        **normalized, "digest": actual, "content_digest": digest(normalized),
        "observed_at": canonical_timestamp(NOW),
    }
    assert connection.in_transaction and connection.transaction_generation == generation
    writer.check_profile()


def test_exact_reingestion_and_timezone_alias_are_idempotent_genuine_recheck_is_new(pair):
    path, writer = pair
    equivalent = NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))
    clocks = [NOW, NOW, equivalent, NOW + timedelta(microseconds=1)]
    actual = [append(writer.connection, record(), observed_at=clock) for clock in clocks]
    expected = [legacy.append_observation(path, record(), observed_at=clock) for clock in clocks]
    assert actual == expected
    assert actual[0] == actual[1] == actual[2] != actual[3]
    assert len(rows(writer.connection)) == 2 and len(contents(writer.connection)) == 1
    assert (rows(writer.connection), contents(writer.connection)) == legacy_rows(path)


@pytest.mark.parametrize("changes", [
    {"complete": 1}, {"observed_at": NOW.isoformat()}, {"subject_id": "Same Name"},
    {"payload": {"nested": {"bookmaker": "X"}}}, {"payload": {"bestOdds": 1.2}},
    {"payload": {"duration_minutes": float("nan")}}, {"payload": {"native_id": object()}},
    {"payload": {1: "bad-key"}}, {"payload": [{"status": "out"}]},
    {"payload": {"sets": (1, 2)}}, {"sport": "tennis"},
    {"valid_until": NOW.isoformat()}, {"valid_from": "2026-09-12T12:34:56"},
    {"published_at": (NOW + timedelta(microseconds=1)).isoformat()},
], ids=["bool", "extra-clock", "subject", "bookmaker", "odds", "nan", "object",
        "key", "payload-list", "tuple", "sport", "interval", "naive-content", "future-publication"])
def test_existing_semantic_rejections_are_preserved_before_any_sql(pair, changes):
    path, writer = pair
    before = writer.connection.total_changes
    statements = []
    writer.connection.set_trace_callback(statements.append)
    try:
        with pytest.raises(ContextContractError) as old:
            legacy.append_observation(path, record(**changes), observed_at=NOW)
        with pytest.raises(type(old.value)):
            append(writer.connection, record(**changes), observed_at=NOW)
        assert statements == []
        assert writer.connection.total_changes == before
    finally:
        writer.connection.set_trace_callback(None)


@pytest.mark.parametrize("clock", [NOW.replace(tzinfo=None), NOW.isoformat(), None],
                         ids=["naive", "not-datetime", "none"])
def test_invalid_receipt_clock_has_same_rejection(pair, clock):
    path, writer = pair
    with pytest.raises(ContextContractError):
        legacy.append_observation(path, record(), observed_at=clock)
    with pytest.raises(ContextContractError):
        append(writer.connection, record(), observed_at=clock)
    assert rows(writer.connection) == contents(writer.connection) == []


@pytest.mark.parametrize("sql,args", [
    ("UPDATE context_contents SET payload=?", (b'{"unexpected":true}',)),
    ("UPDATE context_contents SET payload=?", ("not-a-blob",)),
    ("UPDATE context_observations SET observed_at=?", (NOW.isoformat(),)),
    ("UPDATE context_observations SET source=?", ("rewritten",)),
    ("UPDATE context_observations SET content_digest=?", ("f" * 64,)),
], ids=["content-bytes", "content-type", "clock", "index", "foreign-content"])
def test_real_persisted_collisions_are_rejected_without_repair(pair, sql, args):
    path, writer = pair
    legacy.append_observation(path, record(), observed_at=NOW)
    append(writer.connection, record(), observed_at=NOW)
    with closing(sqlite3.connect(path)) as reference:
        reference.execute(sql, args)
        reference.commit()
    writer.connection.execute(sql, args).close()
    before = rows(writer.connection), contents(writer.connection)
    with pytest.raises(ContextIntegrityError):
        legacy.append_observation(path, record(), observed_at=NOW)
    with pytest.raises(ContextIntegrityError):
        append(writer.connection, record(), observed_at=NOW)
    assert (rows(writer.connection), contents(writer.connection)) == before == legacy_rows(path)


def test_receipt_collision_rolls_back_its_new_content_and_preserves_prior_pending_row(pair):
    path, writer = pair
    original, incoming = record(), record(source_revision="r2", payload={"status": "available"})
    legacy.append_observation(path, original, observed_at=NOW)
    append(writer.connection, original, observed_at=NOW)
    content_hash = digest(normalize_observation(incoming, observed_at=NOW))
    collision = digest({"content_digest": content_hash, "observed_at": canonical_timestamp(NOW)})
    with closing(sqlite3.connect(path)) as reference:
        reference.execute("UPDATE context_observations SET digest=?", (collision,))
        reference.commit()
    writer.connection.execute("UPDATE context_observations SET digest=?", (collision,)).close()
    before = rows(writer.connection), contents(writer.connection)
    generation = writer.connection.transaction_generation
    with pytest.raises(ContextIntegrityError):
        legacy.append_observation(path, incoming, observed_at=NOW)
    with pytest.raises(ContextIntegrityError):
        append(writer.connection, incoming, observed_at=NOW)
    assert (rows(writer.connection), contents(writer.connection)) == before == legacy_rows(path)
    assert writer.connection.in_transaction
    assert writer.connection.transaction_generation == generation
    assert content_hash not in dict(contents(writer.connection))


def test_append_never_opens_creates_schema_or_commits_and_caller_rollback_owns_result(pair, monkeypatch):
    _, writer = pair
    connection = writer.connection
    statements = []
    connection.set_trace_callback(statements.append)

    def forbidden(*args, **kwargs):
        pytest.fail("append acquired a caller-owned lifecycle operation")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(legacy, "_connect", forbidden)
    monkeypatch.setattr(connection, "commit", forbidden)
    try:
        append(connection, record(), observed_at=NOW)
    finally:
        connection.set_trace_callback(None)
    assert statements and all(sql.lstrip().split()[0].upper() in
                              {"SAVEPOINT", "INSERT", "SELECT", "RELEASE"} for sql in statements)
    assert not writer.committed and connection.in_transaction
    connection.rollback()
    assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []


@pytest.mark.parametrize("kind", ["plain", "subclass", "inactive", "closed", "text", "row"],
                         ids=["plain", "subclass", "inactive", "closed", "text", "row"])
def test_requires_exact_held_connection_and_plain_factories(tmp_path, kind):
    class Derived(TrackedConnection):
        pass

    factory = sqlite3.Connection if kind == "plain" else Derived if kind == "subclass" else TrackedConnection
    connection = sqlite3.connect(tmp_path / "bad.sqlite", factory=factory, isolation_level=None)
    try:
        if kind != "inactive":
            connection.execute("BEGIN").close()
        if kind == "closed":
            connection.close()
        elif kind == "text":
            connection.text_factory = bytes
        elif kind == "row":
            connection.row_factory = sqlite3.Row
        with pytest.raises(StorageIntegrityError):
            append(connection, record(), observed_at=NOW)
    finally:
        connection.close()


@pytest.mark.parametrize("action", ["rollback", "commit", "restart", "close", "text", "row"],
                         ids=["rollback", "commit", "restart", "close", "text", "row"])
def test_actual_transaction_or_factory_drift_after_physical_decode_never_returns_a_digest(pair, monkeypatch, action):
    _, writer = pair
    connection = writer.connection
    decode = append_module._decode_receipt

    def changed(stored):
        decoded = decode(stored)
        if action in {"commit", "restart"}:
            connection.commit()
            if action == "restart":
                connection.execute("BEGIN").close()
                connection.execute("CREATE TABLE unrelated_pending(value INTEGER)").close()
        elif action == "rollback":
            connection.rollback()
        elif action == "close":
            connection.close()
        elif action == "text":
            connection.text_factory = bytes
        else:
            connection.row_factory = sqlite3.Row
        return decoded

    monkeypatch.setattr(append_module, "_decode_receipt", changed)
    with pytest.raises(StorageIntegrityError):
        append(connection, record(), observed_at=NOW)
    if action == "restart":
        assert connection.in_transaction
        assert connection.execute("SELECT name FROM sqlite_schema WHERE name='unrelated_pending'").fetchone()
    if action in {"text", "row"}:
        connection.text_factory, connection.row_factory = str, None
        assert rows(connection) == contents(connection) == []
    if action == "close":
        # The writer owner must also report this deliberate foreign close;
        # observe that error here instead of hiding it in fixture teardown.
        with pytest.raises(StorageIntegrityError, match="close/rollback"):
            writer.close()


def test_generation_change_during_normalization_precedes_all_append_sql(pair, monkeypatch):
    _, writer = pair
    connection = writer.connection
    normalize = append_module.normalize_observation

    def changed(value, *, observed_at):
        normalized = normalize(value, observed_at=observed_at)
        connection.commit()
        connection.execute("BEGIN").close()
        connection.execute("CREATE TABLE unrelated_pending(value INTEGER)").close()
        return normalized

    monkeypatch.setattr(append_module, "normalize_observation", changed)
    with pytest.raises(StorageIntegrityError):
        append(connection, record(), observed_at=NOW)
    assert rows(connection) == contents(connection) == []
    assert connection.in_transaction
    assert connection.execute("SELECT name FROM sqlite_schema WHERE name='unrelated_pending'").fetchone()


def test_sql_failure_and_keyboard_interrupt_roll_back_only_this_append(pair, monkeypatch):
    _, writer = pair
    connection = writer.connection
    append(connection, record(), observed_at=NOW)
    before = rows(connection), contents(connection)

    def interrupted(stored):
        raise KeyboardInterrupt("bounded test cancellation")

    monkeypatch.setattr(append_module, "_decode_receipt", interrupted)
    with pytest.raises(KeyboardInterrupt):
        append(connection, record(source_revision="r2"), observed_at=NOW)
    assert (rows(connection), contents(connection)) == before
    monkeypatch.undo()
    connection.execute("CREATE TABLE audit(value TEXT)").close()
    connection.execute(
        "CREATE TRIGGER rejected_receipt AFTER INSERT ON context_observations BEGIN "
        "INSERT INTO audit VALUES ('attempted'); SELECT RAISE(FAIL,'receipt rejected'); END"
    ).close()
    with pytest.raises(StorageIntegrityError):
        append(connection, record(source_revision="r2"), observed_at=NOW)
    assert (rows(connection), contents(connection)) == before
    assert connection.execute("SELECT * FROM audit").fetchall() == []
    assert connection.in_transaction


def test_real_sqlite_full_ends_build_instead_of_becoming_partial_success(tmp_path):
    _, writer = make_pair(tmp_path, cap=32768)
    connection = writer.connection
    generation = connection.transaction_generation
    try:
        with pytest.raises(StorageLimitError) as caught:
            append(connection, record(payload={"status": "x" * 131072}), observed_at=NOW)
        assert isinstance(caught.value.__cause__, sqlite3.DatabaseError)
        assert caught.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_FULL
        assert not connection.in_transaction
        assert connection.transaction_generation != generation
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
    finally:
        writer.close()


def test_failed_savepoint_rollback_is_an_explicit_abandon_build_error(pair, monkeypatch):
    _, writer = pair
    connection = writer.connection

    def reject_decode(stored):
        raise ContextIntegrityError("forced physical decoder rejection")

    def authorizer(code, action, name, database, source):
        if code == sqlite3.SQLITE_SAVEPOINT and action == "ROLLBACK":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    monkeypatch.setattr(append_module, "_decode_receipt", reject_decode)
    connection.set_authorizer(authorizer)
    try:
        with pytest.raises(StorageIntegrityError, match="abandon"):
            append(connection, record(), observed_at=NOW)
    finally:
        connection.set_authorizer(None)
    # Deliberately denied cleanup is not claimed to have undone anything. The
    # explicit error requires the owner to abandon, never to publish this build.
    assert connection.in_transaction
    connection.rollback()
    assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []


def test_only_caller_commit_persists_exact_legacy_rows_for_an_independent_reopen(pair):
    path, writer = pair
    for value, clock in [(record(), NOW), (record(source_revision="r2"), NOW + timedelta(seconds=1))]:
        assert append(writer.connection, value, observed_at=clock) == legacy.append_observation(
            path, value, observed_at=clock)
    assert len(writer._handles) == 0  # No retained native cursor/close_v2 zombie.
    output = writer.path
    writer.commit_build()
    assert writer.closed and writer.committed
    with closing(sqlite3.connect(output.as_uri() + "?mode=ro", uri=True)) as reopened:
        assert (rows(reopened), contents(reopened)) == legacy_rows(path)


def test_does_not_create_missing_caller_schema(tmp_path):
    with open_fresh_writer(tmp_path / "empty.sqlite", plan=SQLiteWriterPlan(32768)) as writer:
        connection = writer.connection
        generation = connection.transaction_generation
        with pytest.raises(StorageIntegrityError):
            append(connection, record(), observed_at=NOW)
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
        assert connection.transaction_generation == generation and connection.in_transaction
        writer.check_profile()


def test_nested_caller_savepoint_remains_owned_by_caller(pair):
    _, writer = pair
    connection = writer.connection
    connection.execute("SAVEPOINT caller_batch").close()
    generation = connection.transaction_generation
    append(connection, record(), observed_at=NOW)
    connection.execute("ROLLBACK TO caller_batch").close()
    connection.execute("RELEASE caller_batch").close()
    assert rows(connection) == contents(connection) == []
    assert connection.transaction_generation == generation and connection.in_transaction


@pytest.mark.parametrize("action", ["BEGIN", "RELEASE"], ids=["savepoint-begin", "savepoint-release"])
def test_real_savepoint_statement_failure_is_not_success_and_retains_prior_work(pair, action):
    _, writer = pair
    connection = writer.connection
    append(connection, record(), observed_at=NOW)
    before = rows(connection), contents(connection)
    denied = []

    def authorizer(code, operation, name, database, source):
        if code == sqlite3.SQLITE_SAVEPOINT and operation == action and not denied:
            denied.append(name)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorizer)
    try:
        with pytest.raises(StorageIntegrityError):
            append(connection, record(source_revision="r2"), observed_at=NOW)
    finally:
        connection.set_authorizer(None)
    assert len(denied) == 1
    assert (rows(connection), contents(connection)) == before
    assert connection.in_transaction


def test_actual_sqlite_length_limit_preserves_the_held_build(pair):
    _, writer = pair
    connection = writer.connection
    append(connection, record(), observed_at=NOW)
    before = rows(connection), contents(connection)
    generation = connection.transaction_generation
    old_limit = connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2048)
    try:
        with pytest.raises(StorageLimitError) as caught:
            append(connection, record(payload={"status": "x" * 4096}), observed_at=NOW)
        assert caught.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_TOOBIG
    finally:
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_limit)
    assert (rows(connection), contents(connection)) == before
    assert connection.transaction_generation == generation and connection.in_transaction


@pytest.mark.parametrize("column", ["payload", "source"], ids=["large-blob", "large-text-after-nul"])
def test_collision_size_guards_precede_python_value_materialization(pair, monkeypatch, column):
    path, writer = pair
    connection = writer.connection
    value = record()
    legacy.append_observation(path, value, observed_at=NOW)
    append(connection, value, observed_at=NOW)
    payload_size = len(canonical_bytes(normalize_observation(value, observed_at=NOW)))
    table = "context_contents" if column == "payload" else "context_observations"
    large = b"x" * 131072 if column == "payload" else "fixture\x00" + "x" * 131072
    with closing(sqlite3.connect(path)) as reference:
        reference.execute(f"UPDATE {table} SET {column}=?", (large,))
        reference.commit()
    connection.execute(f"UPDATE {table} SET {column}=?", (large,)).close()
    original_fetchone = TrackedCursor.fetchone
    fetched = []

    def measured(cursor):
        result = original_fetchone(cursor)
        fetched.append(result)
        if result is not None:
            assert all(not isinstance(item, (bytes, str)) or len(item) <= payload_size for item in result)
        return result

    monkeypatch.setattr(TrackedCursor, "fetchone", measured)
    with pytest.raises(ContextIntegrityError):
        append(connection, value, observed_at=NOW)
    assert fetched and fetched[-1] is None
    with pytest.raises(ContextIntegrityError):
        legacy.append_observation(path, value, observed_at=NOW)


@pytest.mark.parametrize("encoding", ["UTF-16le", "UTF-16be"], ids=["utf16le", "utf16be"])
def test_real_utf16_main_receipt_transport_matches_legacy_without_reencoding(tmp_path, encoding):
    # SQL transport fixture only: no claim that this is the missing copied-main
    # writer owner. The fresh writer profile intentionally creates UTF-8 only.
    path, output = tmp_path / "legacy.sqlite", tmp_path / "utf16.sqlite"
    with closing(sqlite3.connect(path)) as reference:
        reference.execute(f"PRAGMA encoding='{encoding}'")
        reference.execute("CREATE TABLE encoding_fixture(value INTEGER)")
        reference.commit()
    with closing(legacy._connect(path)) as reference:
        schema = reference.execute(
            "SELECT sql FROM sqlite_schema WHERE name IN "
            "('context_contents','context_observations','context_event_receipts') "
            "ORDER BY type DESC,name"
        ).fetchall()
    with closing(sqlite3.connect(output, factory=TrackedConnection, isolation_level=None)) as connection:
        connection.execute("PRAGMA temp_store=MEMORY").close()
        connection.execute(f"PRAGMA encoding='{encoding}'").close()
        connection.execute("BEGIN IMMEDIATE").close()
        for (sql,) in schema:
            connection.execute(sql).close()
        value = record(payload={"status": "unknown", "label": "東京\x00🎾"})
        assert append(connection, value, observed_at=NOW) == legacy.append_observation(path, value, observed_at=NOW)
        assert (rows(connection), contents(connection)) == legacy_rows(path)
        assert connection.execute("PRAGMA encoding").fetchone() == (encoding,)
        connection.rollback()
