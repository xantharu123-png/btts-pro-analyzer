"""Real footprint owner retains admission/error guards without hot path parsing."""
from dataclasses import replace
import errno
import os
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

import pytest

from context_runtime_transaction import TrackedConnection
from context_storage_v2 import refs
from context_storage_v2.contracts import (
    DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError,
)


@pytest.fixture
def connection(tmp_path):
    con = sqlite3.connect(tmp_path / "native.sqlite", factory=TrackedConnection)
    con.execute("PRAGMA page_size=4096")
    con.execute("PRAGMA cache_size=-4096")
    con.execute("PRAGMA mmap_size=0")
    con.execute("PRAGMA max_page_count=32")
    con.execute("CREATE TABLE held(x)")
    con.commit()
    con.execute("BEGIN")
    con.execute("SELECT * FROM held").fetchall()
    try:
        yield con
    finally:
        con.close()


def database_path(con):
    return con.execute("PRAGMA database_list").fetchone()[2]


def test_hot_footprint_does_not_construct_or_parse_path(connection, monkeypatch):
    # A repeated Path constructor can rebuild the process-wide intern table
    # during a bounded stream; native resource checks must not cause that work.
    def no_path(*_args, **_kwargs):
        pytest.fail("hot native footprint must not construct Path")
    monkeypatch.setattr(refs, "Path", no_path)
    assert refs._check_footprint(connection, DEFAULT_LIMITS) is None


def test_cold_admission_keeps_path_api_for_samefile_consumers(connection):
    # Returning a string from the old wrapper breaks actual samefile callers.
    path = refs._require_connection(connection, DEFAULT_LIMITS)
    assert isinstance(path, Path)
    assert path.samefile(database_path(connection))


def test_relative_native_filename_measures_current_directory(connection, monkeypatch):
    # SQLite ordinarily reports an absolute name, but admission never required
    # it. Path('native.sqlite').parent is '.', not an empty disk-usage path.
    path = database_path(connection)
    monkeypatch.chdir(os.path.dirname(path))
    real_query, real_usage = refs._query, shutil.disk_usage
    def query(con, sql, parameters=()):
        if sql == "PRAGMA database_list":
            return real_query(con, "SELECT seq,name,CASE WHEN name='main' THEN ? ELSE file END "
                              "FROM pragma_database_list", (os.path.basename(path),))
        return real_query(con, sql, parameters)
    def usage(directory):
        assert os.fspath(directory) == "."
        return real_usage(directory)
    monkeypatch.setattr(refs, "_query", query)
    monkeypatch.setattr(refs.shutil, "disk_usage", usage)
    assert refs._check_footprint(connection, DEFAULT_LIMITS) is None


def test_native_physical_measurement_follows_real_database_symlink(connection, tmp_path):
    # lstat/no-follow would account for the link rather than an oversized file.
    target, link = database_path(connection), tmp_path / "linked.sqlite"
    try:
        os.symlink(target, link)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink creation privilege unavailable")
        raise
    con = sqlite3.connect(link, factory=TrackedConnection)
    try:
        con.execute("PRAGMA cache_size=-4096")
        con.execute("PRAGMA mmap_size=0")
        con.execute("PRAGMA max_page_count=32")
        con.execute("BEGIN")
        con.execute("SELECT * FROM held").fetchall()
        limits = replace(DEFAULT_LIMITS, input_bytes=131072, workspace_bytes=131072)
        refs._check_footprint(con, limits)
        with open(target, "ab") as stream:
            stream.write(b"\0" * 131072)
        with pytest.raises(StorageLimitError, match="input budget"):
            refs._check_footprint(con, limits)
    finally:
        con.close()


@pytest.mark.parametrize("boundary", ["cold", "hot"])
@pytest.mark.parametrize("damage", [
    "plain", "subclass", "no_transaction", "text", "row", "attached",
    "temp", "memory", "limits_type", "limits_forged",
])
def test_both_admissions_reject_actual_invalid_connection_state(
        connection, tmp_path, boundary, damage):
    # Extracting the path must not bypass any real tracked/SQLite admission.
    con, limits, extra = connection, DEFAULT_LIMITS, None
    if damage in {"plain", "subclass", "memory"}:
        if damage == "subclass":
            class OtherConnection(TrackedConnection):
                pass
            extra = sqlite3.connect(tmp_path / "other.sqlite", factory=OtherConnection)
        elif damage == "memory":
            extra = sqlite3.connect(":memory:", factory=TrackedConnection)
        else:
            extra = sqlite3.connect(tmp_path / "plain.sqlite")
        extra.execute("BEGIN")
        con = extra
    elif damage == "no_transaction":
        con.commit()
    elif damage == "text":
        con.text_factory = bytes
    elif damage == "row":
        con.row_factory = lambda _cursor, row: row
    elif damage == "attached":
        con.execute("ATTACH DATABASE ':memory:' AS other")
    elif damage == "temp":
        con.execute("CREATE TEMP TABLE extra(x)")
    elif damage == "limits_type":
        limits = SimpleNamespace(**DEFAULT_LIMITS.__dict__)
    else:
        limits = replace(DEFAULT_LIMITS)
        object.__setattr__(limits, "input_bytes", DEFAULT_LIMITS.input_bytes + 1)
    try:
        action = refs._require_connection if boundary == "cold" else refs._check_footprint
        with pytest.raises((StorageIntegrityError, StorageLimitError)):
            action(con, limits)
    finally:
        if extra is not None:
            extra.close()


def stat_fault(monkeypatch, target, fault):
    # Fault only the native filesystem dependency; all SQL ownership stays real.
    real_stat = os.stat
    def stat(path, *args, **kwargs):
        if os.fspath(path) == target:
            raise fault
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", stat)


@pytest.mark.parametrize("number", [errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP])
def test_companion_exists_ignores_only_old_missing_errnos(connection, monkeypatch, number):
    # Treating a missing companion as a fatal footprint failure changes policy.
    stat_fault(monkeypatch, database_path(connection) + "-wal", OSError(number, "native fault"))
    assert refs._check_footprint(connection, DEFAULT_LIMITS) is None


@pytest.mark.parametrize("number", [21, 123, 1921])
def test_companion_exists_keeps_exact_ignored_windows_codes(connection, monkeypatch, number):
    error = OSError(errno.EACCES, "native fault")
    error.winerror = number
    stat_fault(monkeypatch, database_path(connection) + "-shm", error)
    assert refs._check_footprint(connection, DEFAULT_LIMITS) is None


def test_companion_exists_keeps_non_encodable_valueerror_policy(connection, monkeypatch):
    stat_fault(monkeypatch, database_path(connection) + "-journal", ValueError("non-encodable path"))
    assert refs._check_footprint(connection, DEFAULT_LIMITS) is None


@pytest.mark.parametrize("number", [errno.EACCES, errno.EPERM, errno.EIO, errno.ENOSPC])
def test_companion_measurement_does_not_hide_other_os_errors(connection, monkeypatch, number):
    # os.path.exists would silently turn PermissionError into missing, bypassing
    # the current fail-closed measurement owner.
    fault = OSError(number, "native fault")
    stat_fault(monkeypatch, database_path(connection) + "-wal", fault)
    with pytest.raises(StorageIntegrityError, match="footprint") as caught:
        refs._check_footprint(connection, DEFAULT_LIMITS)
    assert caught.value.__cause__ is fault


@pytest.mark.parametrize("number", [5, 22, 124, 1922])
def test_companion_measurement_does_not_hide_other_windows_codes(connection, monkeypatch, number):
    fault = OSError(errno.EIO, "native fault")
    fault.winerror = number
    stat_fault(monkeypatch, database_path(connection) + "-wal", fault)
    with pytest.raises(StorageIntegrityError, match="footprint") as caught:
        refs._check_footprint(connection, DEFAULT_LIMITS)
    assert caught.value.__cause__ is fault


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
@pytest.mark.parametrize("fault_kind", ["disappear", "permission", "value"])
def test_companion_positive_exists_still_requires_second_stat(
        connection, monkeypatch, suffix, fault_kind):
    # Reusing the existence stat would incorrectly grant a stale byte count.
    target = database_path(connection) + suffix
    real_stat, calls = os.stat, []
    fault = {
        "disappear": FileNotFoundError(errno.ENOENT, "removed after existence"),
        "permission": PermissionError(errno.EACCES, "denied after existence"),
        "value": ValueError("invalid after existence"),
    }[fault_kind]
    def stat(path, *args, **kwargs):
        if os.fspath(path) == target:
            calls.append(path)
            if len(calls) == 1:
                return SimpleNamespace(st_size=7)
            raise fault
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", stat)
    exception = ValueError if fault_kind == "value" else StorageIntegrityError
    with pytest.raises(exception):
        refs._check_footprint(connection, DEFAULT_LIMITS)
    assert len(calls) == 2


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_each_companion_actual_second_size_counts_toward_workspace(
        connection, monkeypatch, suffix):
    # Omitting any of the three companions or using its existence size permits
    # a workspace overflow. Limits and page cap are independently hand-set.
    target = database_path(connection) + suffix
    real_stat, calls = os.stat, []
    limits = replace(DEFAULT_LIMITS, input_bytes=131072, workspace_bytes=131072)
    def stat(path, *args, **kwargs):
        if os.fspath(path) == target:
            calls.append(path)
            return SimpleNamespace(st_size=1 if len(calls) == 1 else 131072)
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", stat)
    with pytest.raises(StorageLimitError, match="journals"):
        refs._check_footprint(connection, limits)
    assert len(calls) == 2


def test_hot_native_arguments_are_strings_in_existing_measurement_order(connection, monkeypatch):
    # Reconstructing companion paths/parents reintroduces the interning work.
    path = database_path(connection)
    real_stat, real_usage, events = os.stat, shutil.disk_usage, []
    def stat(value, *args, **kwargs):
        if os.fspath(value) in (path, path + "-wal", path + "-shm", path + "-journal"):
            assert type(value) is str
            events.append(("stat", value))
        return real_stat(value, *args, **kwargs)
    def usage(value):
        assert type(value) is str
        events.append(("free", value))
        return real_usage(value)
    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(refs.shutil, "disk_usage", usage)
    refs._check_footprint(connection, DEFAULT_LIMITS)
    assert events == [
        ("stat", path), ("stat", path + "-wal"), ("stat", path + "-shm"),
        ("stat", path + "-journal"), ("free", os.path.dirname(path)),
    ]


@pytest.mark.parametrize("kind", ["physical", "free"])
def test_each_boundary_remeasures_live_resources_without_cache(connection, monkeypatch, kind):
    # A previous successful measurement is never authority for later bytes/free.
    path = database_path(connection)
    refs._check_footprint(connection, DEFAULT_LIMITS)
    if kind == "physical":
        real_stat = os.stat
        def stat(value, *args, **kwargs):
            if os.fspath(value) == path:
                return SimpleNamespace(st_size=DEFAULT_LIMITS.input_bytes + 1)
            return real_stat(value, *args, **kwargs)
        monkeypatch.setattr(os, "stat", stat)
    else:
        usage = shutil.disk_usage(os.path.dirname(path))
        monkeypatch.setattr(refs.shutil, "disk_usage", lambda _path:
            type(usage)(usage.total, usage.used, DEFAULT_LIMITS.min_free_bytes - 1))
    with pytest.raises(StorageLimitError):
        refs._check_footprint(connection, DEFAULT_LIMITS)
