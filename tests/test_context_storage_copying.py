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
def source(tmp_path, *, encoding="UTF-8", large=False):
    path = tmp_path / "original.sqlite"
    writer = sqlite3.connect(path)
    writer.execute(f"PRAGMA encoding='{encoding}'")
    for sql in _SCHEMA.values():
        writer.execute(sql)
    writer.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (
        "a" * 64, "old-kind-Ä\0tail", b'{ "unchanged": true }' * (10000 if large else 1),
        "2026-09-12T00:00:00+00:00"))
    writer.execute("INSERT INTO context_contents VALUES(?,?)", ("b" * 64, b"unreferenced raw bytes\0"))
    writer.execute("INSERT INTO context_snapshots VALUES(?,?,?)", ("c" * 64, b"opaque legacy payload", "d" * 64))
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
