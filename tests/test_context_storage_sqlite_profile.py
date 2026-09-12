"""Small real SQLite lifecycle differentials; NO native quota/RSS/VPS proof."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
from types import SimpleNamespace

import pytest

from context_runtime_transaction import TrackedConnection, TrackedCursor
from context_storage_v2 import refs, snapshots, sqlite_profile as profile
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from test_context_storage_snapshots import arguments, packet


MIB = 1024**2


def plan(**kwargs):
    return profile.SQLiteWriterPlan(kwargs.pop("main_cap_bytes", 8 * MIB), **kwargs)


def open_writer(tmp_path, **kwargs):
    return profile.open_fresh_writer(tmp_path / "new.db", plan=plan(**kwargs))


def table_names(path):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        return tuple(connection.execute("SELECT name FROM sqlite_schema ORDER BY name"))
    finally:
        connection.close()


def assert_closed(connection):
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


@pytest.mark.parametrize("page_size", [512, 1024, 4096, 65536])
@pytest.mark.parametrize("cache_kib", [1, 4096, 8192])
def test_exact_profile_and_one_commit_close(tmp_path, page_size, cache_kib):
    writer = open_writer(tmp_path, page_size=page_size, cache_kib=cache_kib)
    connection = writer.connection
    held_fd = writer._fd
    assert type(connection) is TrackedConnection
    assert writer.plan.max_page_count == 8 * MIB // page_size
    assert writer.plan.journal_cap_bytes == 8 * MIB
    assert writer.plan.logical_reserved_bytes == 16 * MIB
    reading = writer.check_profile()
    assert reading.profile_id == "fresh-single-main-v1"
    assert reading.compile_temp_store in (1, 2, 3)
    assert reading.sqlite_version == sqlite3.sqlite_version
    assert connection.in_transaction
    assert connection.execute("PRAGMA temp_store").fetchone() == (2,)
    assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    assert connection.execute("PRAGMA synchronous").fetchone() == (2,)
    assert connection.execute("PRAGMA mmap_size").fetchone() == (0,)
    assert connection.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED) == 0
    assert connection.getlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS) == 0
    assert not connection.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION)
    connection.execute("CREATE TABLE example(k PRIMARY KEY, value)")
    connection.execute("INSERT INTO example VALUES (1, 'complete')")
    writer.commit_build()
    assert writer.closed and writer.committed and writer.connection is None
    assert_closed(connection)
    with pytest.raises(OSError):
        os.fstat(held_fd)
    with pytest.raises(StorageIntegrityError, match="closed"):
        writer.commit_build()
    with pytest.raises(StorageIntegrityError, match="closed"):
        writer.check_profile()
    writer.close()  # idempotent close is not an idempotent build/commit API
    assert table_names(writer.path) == (("example",), ("sqlite_autoindex_example_1",))


def test_first_sql_memory_and_begin_before_any_ddl(tmp_path, monkeypatch):
    original = sqlite3.connect
    statements, connections = [], []

    def connect(*args, **kwargs):
        result = original(*args, **kwargs)
        result.set_trace_callback(statements.append)
        connections.append(result)
        assert kwargs["factory"] is TrackedConnection
        assert kwargs["cached_statements"] == 0
        assert kwargs["isolation_level"] is None
        return result

    monkeypatch.setattr(profile.sqlite3, "connect", connect)
    with open_writer(tmp_path) as writer:
        writer.connection.execute("CREATE TABLE after_begin(x)")
        writer.commit_build()
    assert len(connections) == 1
    assert statements[0] == "PRAGMA temp_store=MEMORY"
    assert statements.index("PRAGMA compile_options") < statements.index("SELECT 1 FROM temp.sqlite_schema LIMIT 1")
    assert statements.count("BEGIN IMMEDIATE") == statements.count("COMMIT") == 1
    assert statements.index("BEGIN IMMEDIATE") < statements.index("CREATE TABLE after_begin(x)")
    assert not any(sql.startswith("CREATE") for sql in statements[:statements.index("BEGIN IMMEDIATE")])


@pytest.mark.parametrize("exception", [False, True])
def test_context_exit_never_implicitly_commits_and_keeps_failed_main(tmp_path, exception):
    writer = open_writer(tmp_path)
    connection = writer.connection
    try:
        with writer:
            connection.execute("CREATE TABLE uncommitted(x)")
            connection.execute("INSERT INTO uncommitted VALUES (7)")
            if exception:
                raise ValueError("controlled failure")
    except ValueError:
        assert exception
    assert writer.closed and not writer.committed
    assert_closed(connection)
    assert writer.path.exists() and table_names(writer.path) == ()
    with pytest.raises(StorageIntegrityError, match="exists"):
        profile.open_fresh_writer(writer.path, plan=plan())


@pytest.mark.parametrize("invalid", [
    {"main_cap_bytes": True}, {"main_cap_bytes": 0}, {"main_cap_bytes": -4096},
    {"main_cap_bytes": 4097}, {"main_cap_bytes": 4 * 1024**3 + 4096},
    {"page_size": True}, {"page_size": 256}, {"page_size": 513}, {"page_size": 131072},
    {"cache_kib": True}, {"cache_kib": 0}, {"cache_kib": 8193},
])
def test_fixed_plan_rejects_invalid_or_widened_values(invalid):
    with pytest.raises(StorageLimitError):
        plan(**invalid)


@pytest.mark.parametrize("change", [
    {"input_bytes": MIB}, {"workspace_bytes": 8 * MIB},
])
def test_tighter_c_limits_apply_before_file_creation(tmp_path, change):
    with pytest.raises(StorageLimitError):
        profile.open_fresh_writer(tmp_path / "new.db", plan=plan(), limits=replace(DEFAULT_LIMITS, **change))
    assert not tuple(tmp_path.iterdir())


def test_forged_plan_and_limits_revalidated_with_fixed_validator(tmp_path):
    candidate = plan()
    object.__setattr__(candidate, "cache_kib", 9000)
    with pytest.raises(StorageLimitError):
        profile.open_fresh_writer(tmp_path / "new.db", plan=candidate)
    limits = replace(DEFAULT_LIMITS)
    object.__setattr__(limits, "input_bytes", 100 * 1024**3)
    object.__setattr__(limits, "__post_init__", lambda: None)
    with pytest.raises(StorageLimitError):
        profile.open_fresh_writer(tmp_path / "new.db", plan=plan(), limits=limits)
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_existing_files_are_never_opened_overwritten_or_deleted(tmp_path, suffix, monkeypatch):
    path = tmp_path / ("new.db" + suffix)
    path.write_bytes(b"PREEXISTING bytes\x00 are not ours")
    before = path.read_bytes(), path.stat().st_ino
    monkeypatch.setattr(profile.sqlite3, "connect", lambda *a, **k: pytest.fail("existing target opened"))
    with pytest.raises(StorageIntegrityError, match="exists"):
        open_writer(tmp_path)
    assert (path.read_bytes(), path.stat().st_ino) == before
    assert tuple(tmp_path.iterdir()) == (path,)


@pytest.mark.parametrize("name", ["NUL.db", "con", "a:stream.db", "space name.db", "trailing."])
def test_ambiguous_filename_is_rejected_before_creation(tmp_path, name):
    with pytest.raises(StorageIntegrityError):
        profile.open_fresh_writer(tmp_path / name, plan=plan())
    assert not tuple(tmp_path.iterdir())


def test_absolute_existing_parent_is_required(tmp_path):
    with pytest.raises(StorageIntegrityError):
        profile.open_fresh_writer(Path("relative.db"), plan=plan())
    with pytest.raises(StorageIntegrityError):
        profile.open_fresh_writer(tmp_path / "absent" / "new.db", plan=plan())
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("mutation", [
    lambda c: c.execute("PRAGMA cache_size=-99"),
    lambda c: c.execute("PRAGMA cache_spill=OFF"),
    lambda c: c.execute("PRAGMA journal_size_limit=123"),
    lambda c: c.execute("PRAGMA threads=1"),
    lambda c: c.execute("PRAGMA query_only=ON"),
    lambda c: c.execute("PRAGMA busy_timeout=1"),
    lambda c: c.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 1),
    lambda c: c.setlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS, 1),
    lambda c: c.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False),
    lambda c: c.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, True),
    lambda c: setattr(c, "row_factory", sqlite3.Row),
    lambda c: setattr(c, "text_factory", bytes),
    lambda c: setattr(c, "isolation_level", "DEFERRED"),
    lambda c: setattr(c, "autocommit", True),
    lambda c: c.execute("CREATE TEMP TABLE forbidden(x)"),
])
def test_observed_profile_drift_aborts_and_closes(tmp_path, mutation):
    writer = open_writer(tmp_path)
    connection = writer.connection
    connection.execute("CREATE TABLE must_not_be_approved(x)")
    mutation(connection)
    with pytest.raises(StorageIntegrityError):
        writer.check_profile()
    assert writer.closed and not writer.committed
    assert_closed(connection)
    assert writer.path.exists()


@pytest.mark.parametrize("mutator", [
    lambda c: c.commit(), lambda c: c.rollback(),
    lambda c: c.executescript("COMMIT; BEGIN"),
    lambda c: c.executescript("BEGIN"),
])
def test_normal_tracked_transaction_end_or_script_restart_invalidates(tmp_path, mutator):
    writer = open_writer(tmp_path)
    connection = writer.connection
    connection.execute("CREATE TABLE changed_epoch(x)")
    try:
        mutator(connection)
    except sqlite3.Error:
        pass
    with pytest.raises(StorageIntegrityError, match="transaction"):
        writer.commit_build()
    assert writer.closed and not writer.committed
    assert_closed(connection)
    # Illicit caller commits may already have persisted! The invalid handle
    # cannot undo those bytes; it never grants success or deletes the file.
    assert writer.path.exists()


def test_mutated_plan_during_lifetime_is_rejected(tmp_path):
    writer = open_writer(tmp_path)
    connection = writer.connection
    object.__setattr__(writer.plan, "main_cap_bytes", 16 * MIB)
    with pytest.raises(StorageIntegrityError, match="plan"):
        writer.check_profile()
    assert_closed(connection)


def test_savepoints_and_statement_abort_preserve_outer_build_exactly(tmp_path):
    with open_writer(tmp_path, cache_kib=1) as writer:
        connection = writer.connection
        generation = connection.transaction_generation
        connection.execute("CREATE TABLE records(k INTEGER PRIMARY KEY, value BLOB UNIQUE)")
        connection.executemany("INSERT INTO records VALUES (?,?)", ((n, str(n).encode() * 400) for n in range(300)))
        original = tuple(connection.execute("SELECT k,value FROM records ORDER BY k"))
        connection.execute("SAVEPOINT outer_part")
        connection.execute("UPDATE records SET value = value || x'ff'")
        connection.execute("SAVEPOINT inner_part")
        connection.execute("DELETE FROM records WHERE k % 2 = 0")
        connection.execute("ROLLBACK TO inner_part")
        connection.execute("RELEASE inner_part")
        connection.execute("ROLLBACK TO outer_part")
        connection.execute("RELEASE outer_part")
        assert tuple(connection.execute("SELECT k,value FROM records ORDER BY k")) == original
        # A multi-row failing UNIQUE statement must undo that whole statement,
        # not merely the last row, without ending the caller transaction.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE records SET value = x'00'")
        assert tuple(connection.execute("SELECT k,value FROM records ORDER BY k")) == original
        assert connection.transaction_generation == generation
        writer.check_profile()
        writer.commit_build()


def test_real_full_auto_rollback_never_becomes_partial_commit(tmp_path):
    writer = open_writer(tmp_path, main_cap_bytes=8 * 4096, cache_kib=1)
    connection = writer.connection
    connection.execute("CREATE TABLE fill(k INTEGER PRIMARY KEY, payload BLOB)")
    connection.execute("SAVEPOINT subpart")
    with pytest.raises(sqlite3.OperationalError) as failure:
        for n in range(100):
            connection.execute("INSERT INTO fill VALUES (?,zeroblob(5000))", (n,))
    assert failure.value.sqlite_errorcode == sqlite3.SQLITE_FULL
    assert not connection.in_transaction
    with pytest.raises(StorageIntegrityError, match="transaction"):
        writer.commit_build()
    assert writer.closed and not writer.committed
    assert_closed(connection)
    assert table_names(writer.path) == ()
    assert writer.path.stat().st_size <= writer.plan.main_cap_bytes


def test_refs_and_owner_snapshot_transport_in_the_single_build(tmp_path):
    with open_writer(tmp_path) as writer:
        connection = writer.connection
        generation = connection.transaction_generation
        refs.create_schema(connection)
        snapshots.create_schema(connection)
        key, payload, raw, digest = packet(family="tennis:serve", with_effect=True)
        descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=key))
        assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor)) == raw
        assert descriptor.payload_digest == digest
        refs.validate_all(connection)
        snapshots.validate_all(connection)
        assert connection.transaction_generation == generation
        writer.check_profile()
        writer.commit_build()


def test_memory_sort_matches_file_temp_reference_without_changing_old_paths(tmp_path):
    writer = open_writer(tmp_path, cache_kib=4)
    reference = sqlite3.connect(tmp_path / "reference.db", isolation_level=None)
    try:
        reference.execute("PRAGMA temp_store=FILE")
        reference.execute("BEGIN")
        rows = lambda: ((n, f"value-{n % 113:04d}-" + "x" * 96) for n in range(6000))
        query = "SELECT k,value FROM sortdata ORDER BY (k*7919)%8191,value,k"
        hashes = []
        for connection in (writer.connection, reference):
            connection.execute("CREATE TABLE sortdata(k INTEGER PRIMARY KEY, value TEXT)")
            connection.executemany("INSERT INTO sortdata VALUES (?,?)", rows())
            explanation = tuple(connection.execute("EXPLAIN QUERY PLAN " + query))
            assert any("TEMP B-TREE" in row[3] for row in explanation)
            digest = hashlib.sha256()
            for key, value in connection.execute(query):
                digest.update(key.to_bytes(8, "big"))
                digest.update(value.encode())
            hashes.append(digest.digest())
        assert hashes[0] == hashes[1]
        reading = writer.check_profile()
        assert reading.page_count > 100
        assert reading.journal_file_bytes > 0
        # Named entries only: NOT proof about unlinked files or native RSS.
        assert {p.name for p in tmp_path.iterdir()} <= {"new.db", "new.db-journal", "reference.db", "reference.db-journal"}
        writer.commit_build()
    finally:
        writer.close()
        reference.close()


@pytest.mark.parametrize("sql", [
    "ATTACH ':memory:' AS extra", "VACUUM", "VACUUM INTO",
])
def test_sqlite_rejects_incompatible_operations_in_held_build(tmp_path, sql):
    target = tmp_path / "forbidden-copy.db"
    if sql == "VACUUM INTO":
        sql += " '" + str(target).replace("'", "''") + "'"
    with open_writer(tmp_path) as writer:
        writer.connection.execute("CREATE TABLE active(x)")
        with pytest.raises(sqlite3.DatabaseError):
            writer.connection.execute(sql)
        writer.check_profile()
        assert not target.exists()


def test_wal_attempt_during_build_readbacks_unchanged_delete(tmp_path):
    with open_writer(tmp_path) as writer:
        writer.connection.execute("CREATE TABLE active(x)")
        # SQLite 3.53.1 returns the unchanged mode here rather than raising.
        assert writer.connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("delete",)
        writer.check_profile()


def test_sqlite_open_error_retains_new_file_and_releases_exclusive_fd(tmp_path, monkeypatch):
    descriptor = []
    original = os.open

    def opened(*args, **kwargs):
        result = original(*args, **kwargs)
        descriptor.append(result)
        return result

    monkeypatch.setattr(profile.os, "open", opened)
    monkeypatch.setattr(profile.sqlite3, "connect", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("injected open failure")))
    with pytest.raises(StorageIntegrityError):
        open_writer(tmp_path)
    assert (tmp_path / "new.db").read_bytes() == b""
    with pytest.raises(OSError):
        os.fstat(descriptor[0])


def test_factory_type_mismatch_is_closed_without_first_sql(tmp_path, monkeypatch):
    original, opened, statements = sqlite3.connect, [], []

    def wrong_factory(*args, **kwargs):
        kwargs["factory"] = sqlite3.Connection
        result = original(*args, **kwargs)
        result.set_trace_callback(statements.append)
        opened.append(result)
        return result

    monkeypatch.setattr(profile.sqlite3, "connect", wrong_factory)
    with pytest.raises(StorageIntegrityError, match="exact tracked"):
        open_writer(tmp_path)
    assert statements == []
    assert_closed(opened[0])
    assert (tmp_path / "new.db").read_bytes() == b""


def test_replacement_before_first_sql_keeps_foreign_bytes_untouched(tmp_path, monkeypatch):
    original_open, original_connect = os.open, sqlite3.connect
    held, statements, opened = [], [], []
    foreign = tmp_path / "foreign.db"
    foreign.write_bytes(b"FOREIGN not-a-database\x00 must not be touched")
    before = foreign.read_bytes()

    def capture_fd(*args, **kwargs):
        result = original_open(*args, **kwargs)
        held.append(result)
        return result

    def swapped_open(*args, **kwargs):
        # Windows does not share DELETE on os.open descriptors. This explicit
        # fault closes the held fd before real replacement; Linux also has a
        # separate live-fd inode mismatch fixture below. Neither is an ABA proof.
        os.close(held[0])
        os.replace(foreign, tmp_path / "new.db")
        result = original_connect(*args, **kwargs)
        opened.append(result)
        result.set_trace_callback(statements.append)
        return result

    monkeypatch.setattr(profile.os, "open", capture_fd)
    monkeypatch.setattr(profile.sqlite3, "connect", swapped_open)
    with pytest.raises(StorageIntegrityError):
        open_writer(tmp_path)
    assert statements == []
    assert (tmp_path / "new.db").read_bytes() == before
    assert_closed(opened[0])


@pytest.mark.parametrize("field", ["st_ino", "st_dev", "st_nlink", "st_file_attributes"])
def test_live_fd_namespace_mismatch_before_first_sql_is_fail_closed(tmp_path, monkeypatch, field):
    original_connect, original_lstat = sqlite3.connect, Path.lstat
    connected, statements, opened = [], [], []

    def connect(*args, **kwargs):
        result = original_connect(*args, **kwargs)
        result.set_trace_callback(statements.append)
        connected.append(True)
        opened.append(result)
        return result

    def changed(path, *args, **kwargs):
        result = original_lstat(path, *args, **kwargs)
        if connected and path == tmp_path / "new.db":
            data = {name: getattr(result, name) for name in dir(result) if name.startswith("st_")}
            data[field] = 2 if field == "st_nlink" else (getattr(result, field, 0) + 1)
            if field == "st_file_attributes":
                data[field] = getattr(result, field, 0) | 0x400
            return SimpleNamespace(**data)
        return result

    monkeypatch.setattr(profile.sqlite3, "connect", connect)
    monkeypatch.setattr(Path, "lstat", changed)
    with pytest.raises(StorageIntegrityError, match="identity"):
        open_writer(tmp_path)
    assert statements == []
    assert_closed(opened[0])
    assert (tmp_path / "new.db").read_bytes() == b""


def test_initial_readback_mismatch_closes_and_retains_file(tmp_path, monkeypatch):
    original, connections = profile.FreshSQLiteWriter._value, []

    def mismatch(self, name):
        connections.append(self.connection)
        return 1 if name == "temp_store" else original(self, name)

    monkeypatch.setattr(profile.FreshSQLiteWriter, "_value", mismatch)
    with pytest.raises(StorageIntegrityError, match="MEMORY"):
        open_writer(tmp_path)
    assert_closed(connections[0])
    assert (tmp_path / "new.db").read_bytes() == b""


def test_commit_busy_aborts_closes_and_leaves_unpublished_file(tmp_path):
    writer = open_writer(tmp_path, cache_kib=1)
    writer.connection.execute("CREATE TABLE test(x)")
    reader = sqlite3.connect(writer.path.as_uri() + "?mode=ro", uri=True, timeout=0)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT name FROM sqlite_schema").fetchall()
        connection = writer.connection
        with pytest.raises(StorageIntegrityError, match="commit"):
            writer.commit_build()
        assert writer.closed and not writer.committed
        assert_closed(connection)
    finally:
        reader.close()
    assert writer.path.exists() and table_names(writer.path) == ()


def test_native_limits_are_not_claimed_or_installed(tmp_path):
    with open_writer(tmp_path) as writer:
        assert writer.plan.journal_cap_bytes == writer.plan.main_cap_bytes
        # A second Python connection is possible. Ownership/exclusivity is an
        # outer precondition, not a claim of this configuration/lifecycle API.
        other = sqlite3.connect(writer.path)
        try:
            assert other.execute("SELECT 1").fetchone() == (1,)
        finally:
            other.close()


@pytest.mark.parametrize("commit", [False, True])
def test_live_cursor_and_blob_are_closed_before_connection_releases_native_file(tmp_path, commit):
    writer = open_writer(tmp_path)
    connection = writer.connection
    connection.execute("CREATE TABLE data(x BLOB)")
    connection.executemany("INSERT INTO data VALUES (?)", [(b"123",), (b"456",)])
    cursor = connection.execute("SELECT x FROM data")
    assert cursor.fetchone() == (b"123",)
    blob = connection.blobopen("data", "x", 1)
    assert blob.read(1) == b"1"
    if commit:
        writer.commit_build()
    else:
        writer.close()
    assert_closed(connection)
    with pytest.raises(sqlite3.ProgrammingError):
        cursor.fetchone()
    with pytest.raises(sqlite3.ProgrammingError):
        blob.read(1)
    # Actual Windows rename fails with WinError 32 if close_v2 still retains a
    # file through an unfinalized cursor. Only move this test's unique own file.
    renamed = tmp_path / "closed-retained.db"
    writer.path.rename(renamed)
    assert renamed.exists()


def test_registry_is_bounded_and_closes_retained_cursors(tmp_path):
    writer = open_writer(tmp_path)
    connection = writer.connection
    cursors = [connection.execute("SELECT 1") for _ in range(profile.MAX_REGISTERED_HANDLES)]
    with pytest.raises(StorageLimitError, match="handles"):
        connection.execute("SELECT 1")
    writer.close()
    assert_closed(connection)
    assert len(cursors) == 256
    for cursor in cursors:
        with pytest.raises(sqlite3.ProgrammingError):
            cursor.fetchone()


def test_replaced_normal_handle_registry_method_invalidates(tmp_path):
    writer = open_writer(tmp_path)
    connection = writer.connection
    connection.cursor = lambda: TrackedConnection.cursor(connection)
    with pytest.raises(StorageIntegrityError, match="policy"):
        writer.check_profile()
    assert_closed(connection)


@pytest.mark.parametrize("options", [[], ["TEMP_STORE=0"], ["TEMP_STORE=4"], ["TEMP_STORE=1", "TEMP_STORE=1"]])
def test_unsupported_or_ambiguous_compile_temp_store_is_rejected(tmp_path, monkeypatch, options):
    original = TrackedConnection.execute
    opened = []

    def fake_options(connection, sql, *args):
        if sql == "PRAGMA compile_options":
            opened.append(connection)
            # Declared compile-capability injection; real SQLite query/cursor.
            if not options:
                return original(connection, "SELECT '' WHERE 0")
            return original(connection, " UNION ALL ".join("SELECT '" + item + "'" for item in options))
        return original(connection, sql, *args)

    monkeypatch.setattr(TrackedConnection, "execute", fake_options)
    with pytest.raises(StorageIntegrityError, match="effective MEMORY"):
        open_writer(tmp_path)
    assert_closed(opened[0])
    assert (tmp_path / "new.db").read_bytes() == b""


def test_file_arriving_after_absence_check_is_not_overwritten(tmp_path, monkeypatch):
    original = os.open
    marker = b"Arrived before O_EXCL; owned by somebody else"

    def arriving(path, flags, mode):
        Path(path).write_bytes(marker)
        return original(path, flags, mode)

    monkeypatch.setattr(profile.os, "open", arriving)
    monkeypatch.setattr(profile.sqlite3, "connect", lambda *a, **k: pytest.fail("foreign file opened"))
    with pytest.raises(StorageIntegrityError):
        open_writer(tmp_path)
    assert (tmp_path / "new.db").read_bytes() == marker


def test_different_sqlite_main_binding_never_changes_foreign_database(tmp_path, monkeypatch):
    foreign = tmp_path / "foreign.db"
    original = sqlite3.connect
    connection = original(foreign)
    connection.execute("CREATE TABLE precious(x)")
    connection.execute("INSERT INTO precious VALUES ('unchanged')")
    connection.commit()
    connection.close()
    before = foreign.read_bytes()
    opened = []

    def wrong_main(*args, **kwargs):
        result = original(foreign.as_uri() + "?mode=rw", **kwargs)
        opened.append(result)
        return result

    monkeypatch.setattr(profile.sqlite3, "connect", wrong_main)
    with pytest.raises(StorageIntegrityError, match="pathname"):
        open_writer(tmp_path)
    assert foreign.read_bytes() == before
    assert_closed(opened[0])
    assert (tmp_path / "new.db").read_bytes() == b""


def test_real_hardlink_added_during_build_invalidates(tmp_path):
    writer = open_writer(tmp_path)
    connection = writer.connection
    alias = tmp_path / "alias.db"
    try:
        os.link(writer.path, alias)
    except OSError as exc:
        writer.close()
        pytest.skip(f"native hardlink unavailable: {exc}")
    with pytest.raises(StorageIntegrityError, match="identity"):
        writer.check_profile()
    assert_closed(connection)
    assert writer.path.exists() and alias.exists()


def test_zero_filesystem_identity_is_not_a_binding(tmp_path, monkeypatch):
    original = Path.lstat

    def no_identity(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == tmp_path:
            data = {name: getattr(result, name) for name in dir(result) if name.startswith("st_")}
            data["st_ino"] = 0
            return SimpleNamespace(**data)
        return result

    monkeypatch.setattr(Path, "lstat", no_identity)
    with pytest.raises(StorageIntegrityError, match="identity is unavailable"):
        open_writer(tmp_path)
    assert not tuple(tmp_path.iterdir())


def test_registered_custom_tracked_cursor_finalizes_via_sqlite_not_override(tmp_path):
    class CustomTrackedCursor(TrackedCursor):
        def close(self):
            raise AssertionError("profile must close the real SQLite handle")

    writer = open_writer(tmp_path)
    writer.connection.execute("CREATE TABLE data(x)")
    writer.connection.executemany("INSERT INTO data VALUES (?)", [(1,), (2,)])
    cursor = writer.connection.cursor(factory=CustomTrackedCursor)
    cursor.execute("SELECT * FROM data")
    cursor.fetchone()
    writer.commit_build()
    writer.path.rename(tmp_path / "closed-custom.db")
    with pytest.raises(sqlite3.ProgrammingError):
        cursor.fetchone()


def test_error_after_commit_is_not_reported_as_success(tmp_path, monkeypatch):
    writer = open_writer(tmp_path)
    connection = writer.connection
    connection.execute("CREATE TABLE completed_but_unapproved(x)")
    original = profile.FreshSQLiteWriter._read_profile

    def late_error(self, *, active):
        if not active:
            raise OSError("injected post-commit namespace failure")
        return original(self, active=active)

    monkeypatch.setattr(profile.FreshSQLiteWriter, "_read_profile", late_error)
    with pytest.raises(StorageIntegrityError, match="commit"):
        writer.commit_build()
    assert writer.closed and not writer.committed
    assert_closed(connection)
    # Commit cannot be undone after the fact. Retain, but never approve/resume.
    assert table_names(writer.path) == (("completed_but_unapproved",),)


def test_main_descriptor_is_non_inheritable_and_retained_until_close(tmp_path):
    writer = open_writer(tmp_path)
    descriptor = writer._fd
    assert not os.get_inheritable(descriptor)
    assert os.fstat(descriptor).st_ino == writer.path.stat().st_ino
    writer.close()
    with pytest.raises(OSError):
        os.fstat(descriptor)
