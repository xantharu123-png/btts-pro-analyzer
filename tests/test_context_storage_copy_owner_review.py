"""Task 45 independent small C1 copy probes, not native quota/B evidence.

The raw-row oracle below does not invoke inventory_raw or its framing helpers.
All mutation and I/O fault hooks operate on disposable test-owned files; they
model observed boundary failures, not a hostile-Python or race-free guarantee.
"""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
from types import SimpleNamespace

import pytest

from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection
from context_storage_v2 import copying
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"), sort_keys=True).encode("utf-8")


def _database(path, *, encoding="UTF-8", page_size=4096, layout="full"):
    # No semantic validation is asserted for these intentionally opaque rows.
    suffix = "\0Ω𐐷-tail"
    long_key = "z" + "p" * (page_size + 19) + suffix
    rows = {
        "active_manifest": [(1, "m0" + suffix)],
        "artifacts": [
            ("a0" + suffix, "future-kind\0tail", b' {"x":1,"x":2} \xff\0', "future\0time"),
            ("a1" + suffix, "opaque", b"", "old"),
            (long_key, "unadapted", b"\0\x1a\r\n\xff" * 7101, "beyond-cutoff"),
        ],
        "context_contents": [("c0" + suffix, b"\xff\0unreferenced"),
                             ("c1" + suffix, b"\0referenced")],
        "context_model_rollbacks": [("r0" + suffix, b"uninterpreted\0rollback")],
        "context_observations": [("o0" + suffix, "c1" + suffix, "other-tour\0event",
            "future", "revision\0opaque", "owner", "subject\0id", "future-kind")],
        "context_snapshots": [("s0" + suffix, b'{ "observation_refs": ["not-a-ref"] }', "not-a-digest"),
                              ("s1" + suffix, b"\xff\0not JSON", long_key)],
        "manifests": [("m0" + suffix, None, b"null-predecessor\0", "first"),
                      ("m1" + suffix, "m0" + suffix, b"", "second")],
    }
    con = sqlite3.connect(path)
    try:
        con.execute(f"PRAGMA page_size={page_size}")
        con.execute(f"PRAGMA encoding='{encoding}'")
        for name, sql in _SCHEMA.items():
            if layout != "core-empty" or name in {"artifacts", "manifests", "active_manifest"}:
                con.execute(sql)
        if layout == "full":
            for table, values in rows.items():
                con.executemany('INSERT INTO "' + table + '" VALUES (' +
                                ",".join("?" for _ in values[0]) + ")", values)
        else:
            rows = {name: [] for name in rows if layout != "core-empty" or
                    name in {"artifacts", "manifests", "active_manifest"}}
        con.commit()
        schema_rows = con.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").fetchall()
    finally:
        con.close()
    return rows, schema_rows


@contextmanager
def _held(path):
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
        factory=TrackedConnection, isolation_level=None, cached_statements=0,
        autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)
    # Deliberately distinct source policy. copy_legacy must not retune it.
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-73")
    con.execute("PRAGMA mmap_size=0")
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute("BEGIN")
    try:
        yield con
    finally:
        con.close()


def _setup(tmp_path, **options):
    path = tmp_path / "sealed-original.sqlite"
    rows, schema = _database(path, **options)
    work = tmp_path / "job"
    slot = work / "input-copy"
    slot.mkdir(parents=True)
    return path, work, slot, rows, schema


def _copy(con, path, work, slot, **options):
    return copying.copy_legacy(con, directory=work, owned_directory=slot,
        expected_source_sha256=_sha(path.read_bytes()), **options)


def _oracle(rows, schema, encoding):
    tables = []
    total = 0
    codec = {"UTF-8": "utf-8", "UTF-16le": "utf-16-le", "UTF-16be": "utf-16-be"}[encoding]
    for name, values in sorted(rows.items()):
        table_hash = hashlib.sha256(b"betboy-context-v2-table\0" + name.encode("ascii"))
        value_bytes = 0
        # The independent fixture uses distinct ASCII prefixes, so this order
        # agrees with BINARY in all three encodings including its NUL suffixes.
        for row in sorted(values, key=lambda value: value[0]):
            row_hash = hashlib.sha256(b"betboy-context-v2-row\0")
            for field in row:
                if field is None:
                    row_hash.update(b"N")
                elif type(field) is int:
                    row_hash.update(b"I" + struct.pack(">q", field))
                    value_bytes += 8
                else:
                    raw = field.encode(codec) if type(field) is str else field
                    tag = b"T" if type(field) is str else b"B"
                    row_hash.update(tag + struct.pack(">Q", len(raw)) + raw)
                    value_bytes += len(raw)
            table_hash.update(row_hash.digest())
        table_hash.update(struct.pack(">Q", len(values)))
        tables.append(dict(name=name, row_count=len(values), value_bytes=value_bytes,
                           row_digest=table_hash.hexdigest()))
        total += value_bytes
    schema_digest = _sha(_canonical(dict(format_version=1, encoding=encoding,
        schema=schema, user_version=0, application_id=0)))
    logical = _sha(_canonical(dict(format_version=1, schema_digest=schema_digest,
                                  tables=tables, value_bytes=total)))
    return tables, total, schema_digest, logical


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
@pytest.mark.parametrize("page_size", [512, 4096, 65536])
def test_independent_typed_row_table_and_full_logical_oracle(tmp_path, encoding, page_size):
    path, work, slot, rows, schema = _setup(tmp_path, encoding=encoding, page_size=page_size)
    original = path.read_bytes()
    expected = _oracle(rows, schema, encoding)
    with _held(path) as con:
        generation = con.transaction_generation
        receipt = _copy(con, path, work, slot,
                        limits=replace(DEFAULT_LIMITS, block_bytes=max(4096, page_size)))
        observed = receipt.inventory
        assert [vars(table) for table in observed.tables] == expected[0]
        assert observed.value_bytes == expected[1]
        assert observed.schema_digest == expected[2]
        assert observed.logical_digest == expected[3]
        assert receipt.source_sha256 == receipt.copy_sha256 == _sha(original)
        assert receipt.source_bytes == receipt.copy_bytes == len(original)
        assert receipt.path == slot / "legacy-copy.sqlite"
        assert receipt.path.read_bytes() == path.read_bytes() == original
        assert con.in_transaction and con.transaction_generation == generation
        assert list(slot.iterdir()) == [receipt.path]


@pytest.mark.parametrize("layout", ["core-empty", "full-empty"])
def test_missing_optional_and_present_empty_tables_are_distinct_complete_identities(tmp_path, layout):
    path, work, slot, rows, schema = _setup(tmp_path, layout=layout)
    expected = _oracle(rows, schema, "UTF-8")
    with _held(path) as con:
        receipt = _copy(con, path, work, slot)
    assert [vars(table) for table in receipt.inventory.tables] == expected[0]
    assert receipt.inventory.logical_digest == expected[3]
    assert len(receipt.inventory.tables) == (3 if layout == "core-empty" else 7)
    assert receipt.inventory.value_bytes == 0


def test_first_actual_sql_memory_exact_ro_reader_and_unchanged_source_policy(tmp_path, monkeypatch):
    path, work, slot, _rows, _schema = _setup(tmp_path, encoding="UTF-16be", page_size=8192)
    connect = sqlite3.connect
    readers, statements = [], []

    def opened(*args, **kwargs):
        assert kwargs == dict(uri=True, factory=TrackedConnection, timeout=0,
            isolation_level=None, autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,
            cached_statements=0)
        assert args == ((slot / "legacy-copy.sqlite").as_uri() + "?mode=ro",)
        reader = connect(*args, **kwargs)
        readers.append(reader)
        reader.set_trace_callback(statements.append)
        return reader

    profile = ["temp_store", "cache_size", "mmap_size", "query_only", "trusted_schema",
               "page_size", "page_count", "max_page_count", "encoding", "journal_mode"]
    original = path.read_bytes()
    with _held(path) as con:
        source_before = [con.execute("PRAGMA " + name).fetchall() for name in profile]
        generation = con.transaction_generation
        monkeypatch.setattr(sqlite3, "connect", opened)
        result = _copy(con, path, work, slot)
        assert [con.execute("PRAGMA " + name).fetchall() for name in profile] == source_before
        assert con.transaction_generation == generation
    assert len(readers) == 1 and type(readers[0]) is TrackedConnection
    assert statements[0] == "PRAGMA temp_store=MEMORY"
    assert statements.count("BEGIN") == 1
    assert not any(sql.upper().startswith(("COMMIT", "CREATE", "VACUUM", "ATTACH", "INSERT", "UPDATE"))
                   for sql in statements)
    assert result.path.read_bytes() == path.read_bytes() == original
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        readers[0].execute("SELECT 1")


@pytest.mark.parametrize("change", ["same-count-key", "same-size-value", "missing", "extra", "wrong-type"])
def test_real_output_sql_changes_never_get_a_receipt(tmp_path, monkeypatch, change):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    original = path.read_bytes()
    fsync = os.fsync
    compare = copying.compare_raw
    visits = []

    def mutate(descriptor):
        fsync(descriptor)
        out = sqlite3.connect(slot / "legacy-copy.sqlite")
        try:
            if change == "same-count-key":
                out.execute("UPDATE artifacts SET digest='q' || substr(digest,2) WHERE rowid=1")
            elif change == "same-size-value":
                out.execute("UPDATE artifacts SET payload=? WHERE rowid=1",
                            (b"x" * len(_rows["artifacts"][0][2]),))
            elif change == "missing":
                out.execute("DELETE FROM context_contents WHERE rowid=1")
            elif change == "extra":
                out.execute("INSERT INTO artifacts VALUES ('extra','unknown',X'00','future')")
            else:
                out.execute("UPDATE artifacts SET payload='text-not-blob' WHERE rowid=1")
            out.commit()
        finally:
            out.close()

    def compared(*args, **kwargs):
        visits.append(True)
        return compare(*args, **kwargs)

    with _held(path) as con:
        monkeypatch.setattr(os, "fsync", mutate)
        monkeypatch.setattr(copying, "compare_raw", compared)
        with pytest.raises(StorageIntegrityError) as caught:
            _copy(con, path, work, slot)
    assert path.read_bytes() == original
    assert visits == [True]
    assert (slot / "legacy-copy.sqlite").is_file()
    assert any(str(slot) in note for note in caught.value.__notes__)


@pytest.mark.parametrize("column,value", [
    ("artifacts.payload", "text"), ("artifacts.kind", b"blob"),
    ("context_contents.content_digest", b"blob-key"),
    ("context_snapshots.payload_digest", b"blob-digest"),
])
def test_typed_invalid_sources_fail_before_output_allocation(tmp_path, column, value):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    table, field = column.split(".")
    writer = sqlite3.connect(path)
    writer.execute(f'UPDATE "{table}" SET "{field}"=? WHERE rowid=1', (value,))
    writer.commit()
    writer.close()
    original = path.read_bytes()
    with _held(path) as con, pytest.raises(StorageIntegrityError):
        _copy(con, path, work, slot)
    assert path.read_bytes() == original and list(slot.iterdir()) == []


def _change_transaction(con, change):
    if change == "commit":
        con.commit()
        con.execute("BEGIN")
    elif change == "rollback":
        con.rollback()
        con.execute("BEGIN")
    elif change == "script":
        con.executescript("BEGIN;")
    elif change == "autocommit":
        con.autocommit = True
        con.autocommit = sqlite3.LEGACY_TRANSACTION_CONTROL
        con.execute("BEGIN")
    else:
        con.execute("PRAGMA query_only=OFF")
        con.execute("CREATE TEMP TABLE lifecycle_probe(x)")
        con.execute("PRAGMA query_only=ON")


@pytest.mark.parametrize("change", ["commit", "rollback", "script", "autocommit", "temp-ddl"])
@pytest.mark.parametrize("target", ["source", "copy"])
def test_actual_same_connection_lifecycle_change_after_inventory_fails(tmp_path, monkeypatch, change, target):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    original = path.read_bytes()
    compare = copying.compare_raw
    readers = []

    def changed(source, reader, **kwargs):
        result = compare(source, reader, **kwargs)
        readers.append(reader)
        _change_transaction(source if target == "source" else reader, change)
        return result

    with _held(path) as con:
        monkeypatch.setattr(copying, "compare_raw", changed)
        with pytest.raises(StorageIntegrityError):
            _copy(con, path, work, slot)
    assert path.read_bytes() == (slot / "legacy-copy.sqlite").read_bytes() == original
    assert len(readers) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        readers[0].execute("SELECT 1")


@pytest.mark.parametrize("change", ["row-factory", "text-factory", "instance-shadow", "query-only"])
def test_private_reader_post_scan_shape_changes_fail(tmp_path, monkeypatch, change):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    compare = copying.compare_raw

    def changed(source, reader, **kwargs):
        result = compare(source, reader, **kwargs)
        if change == "row-factory":
            reader.row_factory = sqlite3.Row
        elif change == "text-factory":
            reader.text_factory = bytes
        elif change == "instance-shadow":
            reader.unapproved_flag = True
        else:
            reader.execute("PRAGMA query_only=OFF")
        return result

    with _held(path) as con:
        monkeypatch.setattr(copying, "compare_raw", changed)
        with pytest.raises(StorageIntegrityError):
            _copy(con, path, work, slot)
    assert (slot / "legacy-copy.sqlite").is_file()


@pytest.mark.parametrize("name", ["legacy-copy.sqlite", "legacy-copy.sqlite-journal",
                                  "legacy-copy.sqlite-wal", "legacy-copy.sqlite-shm", ".failed", "foreign-dir"])
def test_every_existing_owned_entry_refuses_without_replacement(tmp_path, name):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    sentinel = slot / name
    if name == "foreign-dir":
        sentinel.mkdir()
    else:
        sentinel.write_bytes(b"preserved-owner-data\0")
    identity = sentinel.stat()
    original = path.read_bytes()
    with _held(path) as con, pytest.raises(StorageIntegrityError, match="empty"):
        _copy(con, path, work, slot)
    after = sentinel.stat()
    assert (identity.st_dev, identity.st_ino, identity.st_size, identity.st_mtime_ns) == (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    assert path.read_bytes() == original
    assert list(slot.iterdir()) == [sentinel]


@pytest.mark.parametrize("kind", ["source", "workspace-entry"])
def test_actual_hardlink_alias_is_not_accepted(tmp_path, kind):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    if kind == "source":
        alias = tmp_path / "source-alias.sqlite"
        os.link(path, alias)
    else:
        sentinel = tmp_path / "foreign"
        sentinel.write_bytes(b"not-budget-owned")
        alias = work / "prior-hardlink"
        os.link(sentinel, alias)
    original = path.read_bytes()
    with _held(path) as con, pytest.raises(StorageIntegrityError):
        _copy(con, path, work, slot)
    assert alias.exists() and list(slot.iterdir()) == []
    assert path.read_bytes() == original


@pytest.mark.parametrize("kind", ["different-device", "reparse-point"])
def test_modeled_owned_leaf_stat_policy_rejects_before_creation(tmp_path, monkeypatch, kind):
    # Explicit injected stat model, not an actual Windows mount/junction probe.
    path, work, slot, _rows, _schema = _setup(tmp_path)
    lstat = Path.lstat

    def observed(candidate):
        actual = lstat(candidate)
        if candidate != slot:
            return actual
        values = {name: getattr(actual, name) for name in dir(actual) if name.startswith("st_")}
        if kind == "different-device":
            values["st_dev"] += 1
        else:
            values["st_file_attributes"] = values.get("st_file_attributes", 0) | 0x400
        return SimpleNamespace(**values)

    with _held(path) as con:
        monkeypatch.setattr(Path, "lstat", observed)
        with pytest.raises(StorageIntegrityError):
            _copy(con, path, work, slot)
    assert list(slot.iterdir()) == []


def test_observed_output_directory_exchange_after_fd_open_fails(tmp_path, monkeypatch, record_property):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    old_slot = work / "retained-old-slot"
    real_open = os.open
    moved = []

    def opened(name, flags, *args, **kwargs):
        if Path(name) == path and not moved:
            # All moved files are newly test-owned artifacts. On this Windows
            # host the held child FD prevents the parent-directory rename;
            # report that platform limitation rather than inventing a swap.
            try:
                slot.rename(old_slot)
            except PermissionError:
                assert (slot / "legacy-copy.sqlite").read_bytes() == b""
                assert not old_slot.exists()
                record_property("directory_exchange", "OS denied held-FD parent rename")
                pytest.skip("OS prevents this actual held-FD directory exchange; no Linux proof")
            slot.mkdir()
            moved.append(True)
        return real_open(name, flags, *args, **kwargs)

    with _held(path) as con:
        monkeypatch.setattr(os, "open", opened)
        with pytest.raises(StorageIntegrityError, match="allocation directory changed"):
            _copy(con, path, work, slot)
    assert moved == [True]
    assert (old_slot / "legacy-copy.sqlite").read_bytes() == b""
    assert list(slot.iterdir()) == []


def test_modeled_observed_inode_change_after_allocation_fails_before_first_write(tmp_path, monkeypatch):
    # A separate explicit stat model exercises the fail-closed branch even
    # where the actual directory-replacement probe above is unavailable.
    path, work, slot, _rows, _schema = _setup(tmp_path)
    opened, lstat = os.open, Path.lstat
    armed = []

    def captured(name, *args, **kwargs):
        descriptor = opened(name, *args, **kwargs)
        if Path(name) == path:
            armed.append(True)
        return descriptor

    def observed(candidate):
        actual = lstat(candidate)
        if candidate != slot or not armed:
            return actual
        values = {name: getattr(actual, name) for name in dir(actual) if name.startswith("st_")}
        values["st_ino"] += 1
        return SimpleNamespace(**values)

    with _held(path) as con:
        monkeypatch.setattr(os, "open", captured)
        monkeypatch.setattr(Path, "lstat", observed)
        with pytest.raises(StorageIntegrityError, match="allocation directory changed"):
            _copy(con, path, work, slot)
    assert armed == [True]
    assert (slot / "legacy-copy.sqlite").read_bytes() == b""


@pytest.mark.parametrize("boundary", ["read-zero", "write-exception", "fsync-exception", "reader-close-exception"])
def test_observed_io_abort_keeps_exact_slot_and_closes_all_handles(tmp_path, monkeypatch, boundary):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    original = path.read_bytes()
    opened = os.open
    close = TrackedConnection.close
    descriptors = []

    def captured(*args, **kwargs):
        descriptor = opened(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor

    def failed(*_args, **_kwargs):
        raise OSError("injected I/O exception")

    with _held(path) as con:
        monkeypatch.setattr(os, "open", captured)
        if boundary == "read-zero":
            monkeypatch.setattr(os, "read", lambda *_args: b"")
        elif boundary == "write-exception":
            monkeypatch.setattr(os, "write", failed)
        elif boundary == "fsync-exception":
            monkeypatch.setattr(os, "fsync", failed)
        else:
            def reader_close(reader):
                close(reader)
                if reader is not con:
                    raise OSError("injected post-close exception")
            monkeypatch.setattr(TrackedConnection, "close", reader_close)
        with pytest.raises((OSError, StorageIntegrityError)):
            _copy(con, path, work, slot)
        assert len(descriptors) == 2
        for descriptor in descriptors:
            with pytest.raises(OSError):
                os.fstat(descriptor)
        assert con.in_transaction
    assert path.read_bytes() == original
    assert list(slot.iterdir()) == [slot / "legacy-copy.sqlite"]
    expected = b"" if boundary in {"read-zero", "write-exception"} else original
    assert (slot / "legacy-copy.sqlite").read_bytes() == expected


@pytest.mark.parametrize("change", ["limits", "free-space", "workspace-growth"])
def test_observed_budget_drift_before_return_is_not_success(tmp_path, monkeypatch, change):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    compare = copying.compare_raw
    limits = replace(DEFAULT_LIMITS, workspace_bytes=2 * path.stat().st_size + 256 * 1024)
    usage = shutil.disk_usage(work)

    def changed(source, reader, **options):
        result = compare(source, reader, **options)
        if change == "limits":
            object.__setattr__(limits, "block_bytes", limits.block_bytes // 2)
        elif change == "free-space":
            monkeypatch.setattr(shutil, "disk_usage", lambda _path: type(usage)(usage.total, usage.used, 0))
        else:
            (work / "unrelated-failed-attempt").write_bytes(b"x" * limits.workspace_bytes)
        return result

    with _held(path) as con:
        monkeypatch.setattr(copying, "compare_raw", changed)
        with pytest.raises(StorageLimitError):
            _copy(con, path, work, slot, limits=limits)
    assert (slot / "legacy-copy.sqlite").read_bytes() == path.read_bytes()


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_late_output_companion_refuses_retaining_both_files(tmp_path, monkeypatch, suffix):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    fsync = os.fsync
    companion = slot / ("legacy-copy.sqlite" + suffix)

    def changed(descriptor):
        fsync(descriptor)
        companion.write_bytes(b"unexpected\0side-file")

    with _held(path) as con:
        monkeypatch.setattr(os, "fsync", changed)
        with pytest.raises(StorageIntegrityError, match="companion"):
            _copy(con, path, work, slot)
    assert companion.read_bytes() == b"unexpected\0side-file"
    assert (slot / "legacy-copy.sqlite").read_bytes() == path.read_bytes()


def test_completed_receipt_is_not_reuse_or_live_validation_authority(tmp_path):
    path, work, slot, _rows, _schema = _setup(tmp_path)
    with _held(path) as con:
        receipt = _copy(con, path, work, slot)
        with pytest.raises(StorageIntegrityError, match="empty"):
            _copy(con, path, work, slot)
    historical_digest = receipt.copy_sha256
    receipt.path.write_bytes(b"deliberately altered private test artifact")
    assert receipt.copy_sha256 == historical_digest
    assert _sha(receipt.path.read_bytes()) != historical_digest
    assert _sha(path.read_bytes()) == historical_digest
