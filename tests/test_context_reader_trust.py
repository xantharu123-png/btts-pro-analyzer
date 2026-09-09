"""Physical live-reader trust, with real SQLite/WAL and isolated files only."""
from pathlib import Path
import os
import sqlite3
import stat
from types import SimpleNamespace

import pytest

import context_models.dataset as dataset
import runtime_paths
from context_models.contracts import ContextIntegrityError
from context_snapshots import compute_once
from context_transport import calculate_context_payload, context_consumer_reference, context_payload_key
from runtime_paths import RuntimeArtifactTrustError
from test_context_consumers import saved, read
from test_context_transport import inputs


SUFFIXES = ("", "-wal", "-shm", "-journal")


def member(path, suffix):
    return path.with_name(path.name + suffix)


def forbidden_connect(*args, **kwargs):
    pytest.fail("invalid existing physical path reached sqlite3.connect")


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_main_and_every_existing_companion_must_be_singly_linked_before_open(tmp_path, monkeypatch, suffix):
    path, reference, payload = saved(tmp_path)
    target = member(path, suffix)
    if suffix:
        target.write_bytes(b"existing companion")
    sentinel = tmp_path / "other-file.bin"
    os.link(target, sentinel)
    before = sentinel.read_bytes()
    assert os.stat(target).st_nlink == 2
    monkeypatch.setattr(dataset.sqlite3, "connect", forbidden_connect)
    with pytest.raises(RuntimeArtifactTrustError, match="singly linked"):
        read(path, reference, payload)
    assert sentinel.read_bytes() == before


def test_actual_wal_shm_hardlink_never_overwrites_unrelated_file(tmp_path):
    path, reference, payload = saved(tmp_path)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    connection.close()
    sentinel = tmp_path / "unrelated-not-database.bin"
    before = b"OTHER FILE, NOT A SQLITE SHARED MEMORY FILE.\n" * 2048
    sentinel.write_bytes(before)
    os.link(sentinel, member(path, "-shm"))
    with pytest.raises(RuntimeArtifactTrustError, match="singly linked"):
        read(path, reference, payload)
    assert sentinel.read_bytes() == before


@pytest.mark.parametrize("suffix", SUFFIXES[1:])
def test_companion_directory_is_not_a_regular_database_file(tmp_path, monkeypatch, suffix):
    path, reference, payload = saved(tmp_path)
    member(path, suffix).mkdir()
    monkeypatch.setattr(dataset.sqlite3, "connect", forbidden_connect)
    with pytest.raises(RuntimeArtifactTrustError, match="regular file"):
        read(path, reference, payload)


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_every_member_reuses_existing_no_symlink_guard(tmp_path, monkeypatch, suffix):
    path, reference, payload = saved(tmp_path)
    target = member(path, suffix)
    if suffix:
        target.write_bytes(b"companion")
    original_lstat = os.lstat
    def fake_lstat(candidate, *args, **kwargs):
        current = original_lstat(candidate, *args, **kwargs)
        if Path(candidate) == target:
            data = {name: getattr(current, name) for name in dir(current) if name.startswith("st_")}
            data["st_mode"] = stat.S_IFLNK | stat.S_IRUSR
            return SimpleNamespace(**data)
        return current
    monkeypatch.setattr(dataset.os, "lstat", fake_lstat)
    monkeypatch.setattr(dataset.sqlite3, "connect", forbidden_connect)
    with pytest.raises(RuntimeArtifactTrustError, match="symlink"):
        read(path, reference, payload)


@pytest.mark.parametrize("suffix", SUFFIXES)
@pytest.mark.parametrize("invalid", ["owner", "writable"])
def test_every_member_reuses_actual_posix_owner_permission_policy(tmp_path, monkeypatch, suffix, invalid):
    path, reference, payload = saved(tmp_path)
    target = member(path, suffix)
    if suffix:
        target.write_bytes(b"companion")
    original_lstat = os.lstat
    trusted_uid = original_lstat(path).st_uid
    def fake_lstat(candidate, *args, **kwargs):
        current = original_lstat(candidate, *args, **kwargs)
        data = {name: getattr(current, name) for name in dir(current) if name.startswith("st_")}
        # Exercise the unchanged POSIX primitive on Windows too. The physical
        # ancestor checks have independent tests; do not fake Windows ACL proof.
        data["st_mode"] &= ~(stat.S_IWGRP | stat.S_IWOTH)
        if Path(candidate) == target:
            if invalid == "owner":
                data["st_uid"] = trusted_uid + 100001
            else:
                data["st_mode"] |= stat.S_IWOTH
        return SimpleNamespace(**data)
    monkeypatch.setattr(dataset.os, "lstat", fake_lstat)
    monkeypatch.setattr(runtime_paths, "_trusted_owner_ids", lambda: {trusted_uid})
    monkeypatch.setattr(dataset, "_validate_trusted_runtime_ancestor_chain", lambda parent: None)
    monkeypatch.setattr(dataset.sqlite3, "connect", forbidden_connect)
    with pytest.raises(RuntimeArtifactTrustError, match="untrusted owner|group/world writable"):
        read(path, reference, payload)


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_invalid_member_introduced_during_connect_is_rejected_and_connection_closed(tmp_path, monkeypatch, suffix):
    path, reference, payload = saved(tmp_path)
    original_connect = sqlite3.connect
    opened = []
    sentinel = tmp_path / "new-alias.bin"
    before = b"must remain untouched"
    if suffix:
        sentinel.write_bytes(before)
    def connect(database, *args, **kwargs):
        connection = original_connect(database, *args, **kwargs)
        opened.append(connection)
        if suffix:
            os.link(sentinel, member(path, suffix))
        else:
            os.link(path, sentinel)
        return connection
    monkeypatch.setattr(dataset.sqlite3, "connect", connect)
    with pytest.raises(RuntimeArtifactTrustError, match="singly linked"):
        read(path, reference, payload)
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
    if suffix:
        assert sentinel.read_bytes() == before


@pytest.mark.parametrize("suffix", SUFFIXES[1:])
def test_existing_companion_replacement_during_open_is_not_the_original_identity(tmp_path, monkeypatch, suffix):
    path, reference, payload = saved(tmp_path)
    target = member(path, suffix)
    target.write_bytes(b"")
    replacement = tmp_path / "replacement.bin"
    replacement.write_bytes(b"")
    original_connect = sqlite3.connect
    opened = []
    def connect(database, *args, **kwargs):
        connection = original_connect(database, *args, **kwargs)
        opened.append(connection)
        os.replace(replacement, target)
        return connection
    monkeypatch.setattr(dataset.sqlite3, "connect", connect)
    with pytest.raises(ContextIntegrityError, match="identity changed"):
        read(path, reference, payload)
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")


def test_successful_read_rechecks_new_companion_trust_before_return(tmp_path):
    path, _, _ = saved(tmp_path)
    sentinel = tmp_path / "new-after-open.bin"
    before = b"not shared memory"
    sentinel.write_bytes(before)
    with pytest.raises(RuntimeArtifactTrustError, match="singly linked"):
        with dataset._reader(path) as connection:
            assert connection.execute("SELECT count(*) FROM context_snapshots").fetchone() == (1,)
            os.link(sentinel, member(path, "-shm"))
    assert sentinel.read_bytes() == before


def test_real_symlink_companion_is_rejected_if_host_supports_symlinks(tmp_path):
    path, reference, payload = saved(tmp_path)
    sentinel = tmp_path / "symlink-target.bin"
    before = b"not a journal"
    sentinel.write_bytes(before)
    try:
        member(path, "-journal").symlink_to(sentinel)
    except OSError as exc:
        pytest.skip("real symlink capability unavailable on this host: " + str(getattr(exc, "winerror", None)))
    with pytest.raises(RuntimeArtifactTrustError, match="symlink"):
        read(path, reference, payload)
    assert sentinel.read_bytes() == before


def test_default_existing_delete_database_remains_byte_identical(tmp_path):
    path, reference, payload = saved(tmp_path)
    before = path.read_bytes()
    assert read(path, reference, payload)["projection"]["used_probability"] == .6
    assert path.read_bytes() == before
    assert set(item.name for item in tmp_path.iterdir()) == {path.name}


def test_normal_wal_synchronization_files_are_allowed_not_model_writes(tmp_path):
    path, reference, payload = saved(tmp_path)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    connection.close()
    before = path.read_bytes()
    assert read(path, reference, payload)["projection"]["used_probability"] == .6
    assert path.read_bytes() == before
    for suffix in SUFFIXES[1:]:
        companion = member(path, suffix)
        if companion.exists():
            assert companion.is_file() and os.stat(companion).st_nlink == 1


def test_latest_committed_uncheckpointed_wal_revision_is_visible(tmp_path):
    path, old_ref, old = saved(tmp_path)
    keeper = sqlite3.connect(path)
    try:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("BEGIN")
        assert keeper.execute("SELECT count(*) FROM context_snapshots").fetchone() == (1,)
        before = path.read_bytes()
        new = calculate_context_payload(**inputs(p=.71))
        key = context_payload_key(new)
        compute_once(path, key, lambda: new)
        reference = context_consumer_reference(key, new)
        assert member(path, "-wal").stat().st_size > 0
        assert path.read_bytes() == before
        assert read(path, reference, new)["projection"]["used_probability"] == .71
        assert read(path, old_ref, old)["projection"]["used_probability"] == .6
        assert keeper.execute("SELECT count(*) FROM context_snapshots").fetchone() == (1,)
    finally:
        keeper.rollback()
        keeper.close()


def test_one_reader_transaction_does_not_mix_live_schema_and_payload_revisions(tmp_path, monkeypatch):
    path, reference, payload = saved(tmp_path)
    writer = sqlite3.connect(path)
    writer.execute("PRAGMA journal_mode=WAL")
    original_connect = sqlite3.connect
    commits = []
    class InterleavedReader(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql.startswith("SELECT key,payload,payload_digest") and not commits:
                writer.execute("UPDATE context_snapshots SET payload=? WHERE key=?", (b"not-json", reference["key"]))
                writer.commit()
                commits.append("new committed revision")
            return super().execute(sql, parameters)
    def connect(database, *args, **kwargs):
        return original_connect(database, *args, factory=InterleavedReader, **kwargs)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(dataset.sqlite3, "connect", connect)
            assert read(path, reference, payload)["projection"]["used_probability"] == .6
        assert commits == ["new committed revision"]
        with pytest.raises(ContextIntegrityError):
            read(path, reference, payload)
    finally:
        writer.close()
