"""Complete private-copy checks; neither publication nor native capacity proof."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3

import pytest

from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.copying import copy_legacy as _copy_legacy
from context_storage_v2.inventory import inventory_raw


def copy_legacy(source, **options):
    # The separately owning fixture supplies the actual pre-mutation source
    # identity, not a success flag or a patched validator.
    path = Path(source.execute("PRAGMA database_list").fetchone()[2])
    return _copy_legacy(source, expected_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **options)


@contextmanager
def source(tmp_path, *, encoding="UTF-8", large=False, page_size=4096, nul_keys=False):
    path = tmp_path / "original.sqlite"
    writer = sqlite3.connect(path)
    writer.execute(f"PRAGMA page_size={page_size}")
    writer.execute(f"PRAGMA encoding='{encoding}'")
    for sql in _SCHEMA.values():
        writer.execute(sql)
    suffix = "\0Жä-tail" if nul_keys else ""
    writer.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (
        "a" * 64 + suffix, "old-kind-Ä\0tail", b'{ "unchanged": true }' * (10000 if large else 1),
        "2026-09-12T00:00:00+00:00"))
    writer.execute("INSERT INTO context_contents VALUES(?,?)", ("b" * 64 + suffix, b"unreferenced raw bytes\0"))
    writer.execute("INSERT INTO context_snapshots VALUES(?,?,?)", ("c" * 64 + suffix, b"opaque legacy payload", "d" * 64 + suffix))
    writer.commit()
    writer.close()
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, factory=TrackedConnection)
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute("BEGIN")
    try:
        yield path, con
    finally:
        con.close()


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_copy_preserves_every_logical_type_byte_key_and_source_file(tmp_path, encoding):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path, encoding=encoding, large=True) as (path, con):
        before = path.read_bytes()
        expected = inventory_raw(con)
        epoch = con.transaction_generation
        result = copy_legacy(con, directory=work)
        assert result.inventory == expected
        assert result.source_sha256 == hashlib.sha256(before).hexdigest()
        assert result.copy_sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()
        assert result.path.parent.parent == work
        assert result.source_bytes == len(before)
        assert result.copy_bytes == result.path.stat().st_size
        assert con.transaction_generation == epoch and con.in_transaction
        assert path.read_bytes() == before
        assert len(list(work.rglob("*.sqlite"))) == 1
        reader = sqlite3.connect(result.path.as_uri() + "?mode=ro", uri=True, factory=TrackedConnection)
        reader.execute("PRAGMA query_only=ON")
        reader.execute("PRAGMA trusted_schema=OFF")
        reader.execute("BEGIN")
        try:
            assert inventory_raw(reader) == expected
        finally:
            reader.close()


def test_existing_files_in_parent_are_never_overwritten_or_removed(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    old = work / "legacy-copy.sqlite"
    old.write_bytes(b"user-owned existing file")
    with source(tmp_path) as (_path, con):
        first = copy_legacy(con, directory=work)
        second = copy_legacy(con, directory=work)
        assert first.path != second.path
        assert first.inventory == second.inventory
    assert old.read_bytes() == b"user-owned existing file"


def test_source_and_copy_are_both_charged_to_the_passed_input_budget(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path) as (path, con):
        size = path.stat().st_size
        with pytest.raises(StorageLimitError, match="combined"):
            copy_legacy(con, directory=work, limits=replace(DEFAULT_LIMITS, input_bytes=size * 2 - 1))
    assert list(work.iterdir()) == []


def test_existing_entire_work_directory_is_charged_before_allocating(tmp_path):
    work = tmp_path / "work"
    nested = work / "other-build"
    nested.mkdir(parents=True)
    (nested / "prior-result").write_bytes(b"x" * 32768)
    with source(tmp_path) as (path, con):
        with pytest.raises(StorageLimitError, match="workspace"):
            copy_legacy(con, directory=work, limits=replace(
                DEFAULT_LIMITS, workspace_bytes=path.stat().st_size + 32768 - 1))
    assert list(work.iterdir()) == [nested]


def test_insufficient_free_reserve_rejects_before_creating_output(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path) as (path, con):
        usage = shutil.disk_usage(work)
        monkeypatch.setattr(shutil, "disk_usage", lambda _path: type(usage)(usage.total, usage.used,
                            DEFAULT_LIMITS.min_free_bytes + path.stat().st_size - 1))
        with pytest.raises(StorageLimitError, match="reserve"):
            copy_legacy(con, directory=work)
    assert list(work.iterdir()) == []


@pytest.mark.parametrize("ending", ["commit", "rollback"])
def test_unheld_source_is_rejected_without_partial_copy(tmp_path, ending):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path) as (_path, con):
        getattr(con, ending)()
        with pytest.raises(StorageIntegrityError):
            copy_legacy(con, directory=work)
    assert list(work.iterdir()) == []


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_source_with_companion_is_not_a_sealed_copy_input(tmp_path, suffix):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path) as (path, con):
        Path(str(path) + suffix).write_bytes(b"do not open as a standalone image")
        with pytest.raises(StorageIntegrityError, match="companion"):
            copy_legacy(con, directory=work)
    assert list(work.iterdir()) == []


def test_forged_wider_limits_and_callback_shadow_are_rejected(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    limits = replace(DEFAULT_LIMITS)
    object.__setattr__(limits, "input_bytes", 16 * 1024**3)
    object.__setattr__(limits, "__post_init__", lambda: None)
    with source(tmp_path) as (_path, con):
        with pytest.raises(StorageLimitError):
            copy_legacy(con, directory=work, limits=limits)
    assert list(work.iterdir()) == []


def test_wrong_sealed_digest_fails_before_output_allocation(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path) as (_path, con):
        with pytest.raises(StorageIntegrityError, match="sealed source digest"):
            _copy_legacy(con, directory=work, expected_source_sha256="0" * 64)
    assert list(work.iterdir()) == []


def test_checkpointed_wal_header_is_rejected_before_source_side_files_are_created(tmp_path):
    path, work = tmp_path / "wal.sqlite", tmp_path / "work"
    work.mkdir()
    writer = sqlite3.connect(path)
    writer.execute("PRAGMA journal_mode=WAL")
    for sql in _SCHEMA.values():
        writer.execute(sql)
    writer.commit()
    writer.close()
    before = path.read_bytes()
    assert before[18:20] == b"\x02\x02"
    assert not Path(str(path) + "-wal").exists()
    assert not Path(str(path) + "-shm").exists()
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, factory=TrackedConnection)
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute("BEGIN")
    try:
        with pytest.raises(StorageIntegrityError, match="header"):
            _copy_legacy(con, directory=work, expected_source_sha256=hashlib.sha256(before).hexdigest())
        assert path.read_bytes() == before
        assert not Path(str(path) + "-wal").exists()
        assert not Path(str(path) + "-shm").exists()
    finally:
        con.close()
    assert list(work.iterdir()) == []


def test_real_shortwrites_and_binary_control_bytes_preserve_the_complete_copy(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    actual_write = os.write
    requests = []
    def short_write(fd, raw):
        requests.append(len(raw))
        return actual_write(fd, raw[:317])
    monkeypatch.setattr(os, "write", short_write)
    with source(tmp_path, large=True) as (path, con):
        result = copy_legacy(con, directory=work, limits=replace(DEFAULT_LIMITS, block_bytes=4096))
        assert result.path.read_bytes() == path.read_bytes()
    assert len(requests) > 20 and max(requests) <= 4096


def test_zero_write_progress_leaves_no_complete_receipt_or_source_change(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    with source(tmp_path) as (path, con):
        before = path.read_bytes()
        monkeypatch.setattr(os, "write", lambda _fd, _raw: 0)
        with pytest.raises(StorageIntegrityError, match="progress"):
            copy_legacy(con, directory=work)
        assert path.read_bytes() == before
    # Partial output is not silently deleted or made into successful evidence.
    assert len(list(work.rglob("legacy-copy.sqlite"))) == 1


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_owned_copy_slot_is_exact_and_preserves_raw_unknown_nul_bytes(tmp_path, encoding):
    work = tmp_path / "work"
    work.mkdir()
    owned = work / "reserved-copy"
    owned.mkdir()
    with source(tmp_path, encoding=encoding, large=True) as (path, con):
        original = path.read_bytes()
        expected = inventory_raw(con)
        result = copy_legacy(con, directory=work, owned_directory=owned)
        assert result.path == owned / "legacy-copy.sqlite"
        assert result.path.read_bytes() == original
        assert result.inventory == expected
        assert path.read_bytes() == original
        assert list(work.iterdir()) == [owned]
        assert list(owned.iterdir()) == [result.path]
        with pytest.raises(StorageIntegrityError, match="empty"):
            copy_legacy(con, directory=work, owned_directory=owned)
        assert result.path.read_bytes() == original


def test_new_internal_copy_reader_has_memory_first_and_bounded_actual_policy(tmp_path, monkeypatch):
    from context_storage_v2 import copying
    work = tmp_path / "work"
    work.mkdir()
    captured = []
    connect = sqlite3.connect
    compare = copying.compare_raw

    def traced(database, *args, **kwargs):
        reader = connect(database, *args, **kwargs)
        if "legacy-copy.sqlite?mode=ro" in str(database):
            statements = []
            sqlite3.Connection.set_trace_callback(reader, statements.append)
            captured.append((reader, statements))
        return reader

    def bounded_compare(original, reader, *, limits):
        assert type(reader) is TrackedConnection
        assert reader.in_transaction
        assert captured[0][1][0] == "PRAGMA temp_store=MEMORY"
        for name, expected in (
            ("temp_store", 2), ("main.cache_size", -4096), ("main.mmap_size", 0),
            ("threads", 0), ("query_only", 1), ("trusted_schema", 0),
            ("main.max_page_count", original.execute("PRAGMA main.page_count").fetchone()[0]),
        ):
            assert reader.execute("PRAGMA " + name).fetchone() == (expected,)
        assert reader.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED) == 0
        assert reader.getlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS) == 0
        assert reader.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE) is True
        assert reader.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION) is False
        assert reader.getconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA) is False
        return compare(original, reader, limits=limits)

    with source(tmp_path) as (path, con):
        before = path.read_bytes()
        policy_names = ("temp_store", "main.cache_size", "main.mmap_size", "threads",
                        "main.page_size", "encoding", "query_only", "trusted_schema")
        policy = tuple(con.execute("PRAGMA " + name).fetchone() for name in policy_names)
        generation = con.transaction_generation
        monkeypatch.setattr(sqlite3, "connect", traced)
        monkeypatch.setattr(copying, "compare_raw", bounded_compare)
        result = copy_legacy(con, directory=work)
        assert len(captured) == 1
        assert tuple(con.execute("PRAGMA " + name).fetchone() for name in policy_names) == policy
        assert con.transaction_generation == generation and con.in_transaction
        assert path.read_bytes() == result.path.read_bytes() == before
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        captured[0][0].execute("SELECT 1")


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
@pytest.mark.parametrize("page_size", [512, 8192, 65536])
def test_copy_reader_preserves_nondefault_page_dimensions_and_encoding(tmp_path, encoding, page_size):
    work = tmp_path / "work"
    owned = work / "reserved"
    owned.mkdir(parents=True)
    with source(tmp_path, encoding=encoding, page_size=page_size) as (path, con):
        before = path.read_bytes()
        expected = inventory_raw(con)
        result = copy_legacy(con, directory=work, owned_directory=owned)
        assert result.inventory == expected
        assert result.path.read_bytes() == path.read_bytes() == before
        assert con.execute("PRAGMA main.page_size").fetchone() == (page_size,)
        assert con.execute("PRAGMA encoding").fetchone() == (encoding,)


@pytest.mark.parametrize("kind", ["main", "journal", "wal", "shm", "unknown",
                                  "file", "missing", "relative", "nested", "root", "outside", "dotdot"])
def test_owned_copy_directory_never_adopts_other_paths_or_existing_artifacts(tmp_path, kind):
    work = tmp_path / "work"
    work.mkdir()
    owned = work / "owned"
    owned.mkdir()
    sentinel = None
    suffixes = {"main": "", "journal": "-journal", "wal": "-wal", "shm": "-shm"}
    if kind in suffixes or kind == "unknown":
        sentinel = owned / ("legacy-copy.sqlite" + suffixes[kind] if kind != "unknown" else ".unknown")
        sentinel.write_bytes(b"not our bytes\0do not replace")
    elif kind == "file":
        owned = work / "not-a-directory"
        sentinel = owned
        sentinel.write_bytes(b"existing ordinary file")
    elif kind == "missing":
        owned = work / "does-not-exist"
    elif kind == "relative":
        owned = Path("owned")
    elif kind == "nested":
        owned = owned / "nested"
        owned.mkdir()
    elif kind == "root":
        owned = work
    elif kind == "outside":
        owned = tmp_path / "outside"
        owned.mkdir()
    else:
        owned = work / ".."
    before = None if sentinel is None else (sentinel.read_bytes(), sentinel.stat().st_ino,
                                            sentinel.stat().st_mtime_ns)
    with source(tmp_path) as (path, con):
        original = path.read_bytes()
        with pytest.raises((StorageIntegrityError, OSError)):
            copy_legacy(con, directory=work, owned_directory=owned)
        assert path.read_bytes() == original
    if sentinel is not None:
        assert (sentinel.read_bytes(), sentinel.stat().st_ino, sentinel.stat().st_mtime_ns) == before
    assert not list(work.glob("context-copy-*"))


def test_copy_owned_slot_still_charges_only_the_actual_copy_not_a_writer_journal(tmp_path):
    from context_storage_v2 import copying
    work = tmp_path / "work"
    owned = work / "owned"
    owned.mkdir(parents=True)
    with source(tmp_path, large=True) as (path, con):
        size = path.stat().st_size
        actual_envelope = size + copying._workspace_bytes(work) + copying._METADATA_RESERVE
        assert actual_envelope < 2 * size
        result = copy_legacy(con, directory=work, owned_directory=owned,
            limits=replace(DEFAULT_LIMITS, workspace_bytes=actual_envelope))
        assert result.path.read_bytes() == path.read_bytes()
        assert list(owned.iterdir()) == [result.path]


def _capture_copy_fds(monkeypatch):
    actual_open = os.open
    descriptors = []

    def opened(*args, **kwargs):
        descriptor = actual_open(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", opened)
    return descriptors


@pytest.mark.parametrize("mode", ["owned", "convenience"])
@pytest.mark.parametrize("failure", ["write", "open_reader", "memory_denied"])
def test_copy_failure_keeps_artifacts_and_closes_every_owned_fd(tmp_path, monkeypatch, mode, failure):
    work = tmp_path / "work"
    work.mkdir()
    options = {}
    if mode == "owned":
        owned = work / "owned"
        owned.mkdir()
        options["owned_directory"] = owned
    connect = sqlite3.connect
    readers = []

    def opened(database, *args, **kwargs):
        if "legacy-copy.sqlite?mode=ro" in str(database):
            if failure == "open_reader":
                raise sqlite3.OperationalError("deliberate internal reader open failure")
            reader = connect(database, *args, **kwargs)
            readers.append(reader)
            if failure == "memory_denied":
                def authorize(action, name, value, *unused):
                    if action == sqlite3.SQLITE_PRAGMA and name == "temp_store" and value:
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK
                reader.set_authorizer(authorize)
            return reader
        return connect(database, *args, **kwargs)

    with source(tmp_path) as (path, con):
        original = path.read_bytes()
        descriptors = _capture_copy_fds(monkeypatch)
        monkeypatch.setattr(sqlite3, "connect", opened)
        if failure == "write":
            monkeypatch.setattr(os, "write", lambda _fd, _raw: 0)
        with pytest.raises(StorageIntegrityError) as caught:
            copy_legacy(con, directory=work, **options)
        assert path.read_bytes() == original
        files = list(work.rglob("legacy-copy.sqlite"))
        assert len(files) == 1
        assert any(str(files[0].parent) in note for note in caught.value.__notes__)
        assert files[0].read_bytes() == (b"" if failure == "write" else original)
        for descriptor in descriptors:
            with pytest.raises(OSError):
                os.fstat(descriptor)
        assert len(descriptors) == 2
        for reader in readers:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                reader.execute("SELECT 1")


@pytest.mark.parametrize("change", ["cache", "max_pages", "threads", "attach_limit",
                                   "worker_limit", "extensions", "defensive", "trusted_schema"])
def test_copy_private_reader_policy_drift_after_complete_scan_prevents_receipt(tmp_path, monkeypatch, change):
    from context_storage_v2 import copying
    work = tmp_path / "work"
    owned = work / "owned"
    owned.mkdir(parents=True)
    compare = copying.compare_raw
    readers = []

    def drift(original, reader, *, limits):
        result = compare(original, reader, limits=limits)
        readers.append(reader)
        if change == "cache":
            reader.execute("PRAGMA main.cache_size=-17")
        elif change == "max_pages":
            reader.execute("PRAGMA main.max_page_count=1000000")
        elif change == "threads":
            reader.execute("PRAGMA threads=1")
        elif change in {"attach_limit", "worker_limit"}:
            category = sqlite3.SQLITE_LIMIT_ATTACHED if change == "attach_limit" else sqlite3.SQLITE_LIMIT_WORKER_THREADS
            reader.setlimit(category, 1)
        else:
            category, value = {
                "extensions": (sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, True),
                "defensive": (sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False),
                "trusted_schema": (sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, True),
            }[change]
            reader.setconfig(category, value)
        return result

    with source(tmp_path) as (path, con):
        original = path.read_bytes()
        monkeypatch.setattr(copying, "compare_raw", drift)
        with pytest.raises(StorageIntegrityError):
            copy_legacy(con, directory=work, owned_directory=owned)
        assert path.read_bytes() == (owned / "legacy-copy.sqlite").read_bytes() == original
    assert len(readers) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        readers[0].execute("SELECT 1")


@pytest.mark.parametrize("options", [[], [("TEMP_STORE=0",)], [("TEMP_STORE=4",)],
    [("TEMP_STORE=1",), ("TEMP_STORE=2",)], [("TEMP_STORE=2\0suffix",)],
    [("x" * 257,)], [(None,)], [("TEMP_STORE=2", "extra")]])
def test_modeled_bad_compile_catalog_refuses_before_copy_inventory(tmp_path, monkeypatch, options):
    # Modeled metadata readback, NOT a local TEMP_STORE=0 SQLite build or native proof.
    from context_storage_v2 import copying
    work = tmp_path / "work"
    work.mkdir()
    query = copying._copy_reader_query

    def observed(reader, sql, **kwargs):
        actual = query(reader, sql, **kwargs)
        return options if sql == "PRAGMA compile_options" else actual

    def forbidden(*args, **kwargs):
        raise AssertionError("bad compile override reached the comparison workload")

    with source(tmp_path) as (path, con):
        original = path.read_bytes()
        monkeypatch.setattr(copying, "_copy_reader_query", observed)
        monkeypatch.setattr(copying, "compare_raw", forbidden)
        with pytest.raises(StorageIntegrityError, match="MEMORY"):
            copy_legacy(con, directory=work)
        assert list(work.rglob("legacy-copy.sqlite"))[0].read_bytes() == original


def test_modeled_copy_profile_fetch_is_bounded_and_closes_on_overflow():
    from context_storage_v2 import copying
    # Closed protocol probe; these are deliberately not native SQLite objects.
    requested = []
    closed = []

    class Cursor:
        def fetchmany(self, count):
            requested.append(count)
            return [("TEMP_STORE=2",)] * count

        def close(self):
            closed.append(True)

    class Reader:
        def execute(self, sql):
            assert sql == "PRAGMA compile_options"
            return Cursor()

    with pytest.raises(StorageIntegrityError, match="bound"):
        copying._copy_reader_query(Reader(), "PRAGMA compile_options", max_rows=256)
    assert requested == [257]
    assert closed == [True]


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_owned_copy_preserves_unknown_nul_suffixed_keys_without_semantic_reinterpretation(tmp_path, encoding):
    # C1 copies typed legacy bytes; it must not impose the C2 digest key grammar.
    work = tmp_path / "work"
    owned = work / "owned"
    owned.mkdir(parents=True)
    with source(tmp_path, encoding=encoding, nul_keys=True) as (path, con):
        expected = inventory_raw(con)
        before = path.read_bytes()
        result = copy_legacy(con, directory=work, owned_directory=owned)
        assert result.inventory == expected
        assert path.read_bytes() == result.path.read_bytes() == before
        assert con.execute("SELECT digest FROM artifacts").fetchone()[0] == "a" * 64 + "\0Жä-tail"


@pytest.mark.parametrize("observed_rows", [[], [(0,)], [(True,)], [(2.0,)], [("2",)], [(2,), (2,)]])
def test_modeled_memory_readback_must_be_the_exact_native_integer(tmp_path, monkeypatch, observed_rows):
    # Modeled missing/malformed metadata, not a claim about this SQLite build.
    from context_storage_v2 import copying
    work = tmp_path / "work"
    work.mkdir()
    query = copying._copy_reader_query

    def observed(reader, sql, **kwargs):
        actual = query(reader, sql, **kwargs)
        return observed_rows if sql == "PRAGMA temp_store" else actual

    def forbidden(*args, **kwargs):
        raise AssertionError("bad MEMORY readback reached comparison")

    with source(tmp_path) as (_path, con):
        monkeypatch.setattr(copying, "_copy_reader_query", observed)
        monkeypatch.setattr(copying, "compare_raw", forbidden)
        with pytest.raises(StorageIntegrityError, match="MEMORY"):
            copy_legacy(con, directory=work)
    assert len(list(work.rglob("legacy-copy.sqlite"))) == 1


def test_copy_reader_is_actually_readonly_even_without_reversible_query_only(tmp_path, monkeypatch):
    from context_storage_v2 import copying
    work = tmp_path / "work"
    work.mkdir()
    compare = copying.compare_raw
    checked = []

    def readonly(original, reader, *, limits):
        reader.execute("PRAGMA query_only=OFF")
        with pytest.raises(sqlite3.OperationalError) as caught:
            reader.execute("UPDATE artifacts SET kind='would-change-raw-bytes'")
        assert caught.value.sqlite_errorcode == sqlite3.SQLITE_READONLY
        reader.execute("PRAGMA query_only=ON")
        checked.append(True)
        return compare(original, reader, limits=limits)

    with source(tmp_path) as (path, con):
        before = path.read_bytes()
        monkeypatch.setattr(copying, "compare_raw", readonly)
        result = copy_legacy(con, directory=work)
        assert path.read_bytes() == result.path.read_bytes() == before
    assert checked == [True]
