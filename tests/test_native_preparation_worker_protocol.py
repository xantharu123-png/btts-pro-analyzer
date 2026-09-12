"""Versioned worker protocol models; never load main or call real libc/Linux/root."""
import ast
import builtins
import ctypes
import errno
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_worker_protocol():
    """Compile only the bounded functions under test, with isolated imports."""
    path = ROOT / "tests/native_preparation_worker.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    constants = {"FORMAT", "MODES", "GIB"}
    functions = {"require", "emit", "denials", "fsize", "address_space"}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            assert all(isinstance(target, ast.Name) and target.id in constants
                       for target in node.targets)
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            nodes.append(node)
    module = types.ModuleType("native_worker_protocol_model")
    module.__file__ = str(path)

    def model_import(name, *_args, **_kwargs):
        assert name == "mmap", "unexpected import in worker protocol model"
        return module.mmap

    module.__dict__.update(
        __builtins__={**vars(builtins), "__import__": model_import},
        ctypes=types.SimpleNamespace(**{name: getattr(ctypes, name) for name in
            ("CFUNCTYPE", "POINTER", "byref", "c_int", "c_long", "c_ulong",
             "c_void_p", "c_size_t", "set_errno", "get_errno")}),
        errno=errno, json=json,
        os=types.SimpleNamespace(
            O_WRONLY=os.O_WRONLY, O_CREAT=os.O_CREAT, O_EXCL=os.O_EXCL, O_NOFOLLOW=0x20000,
            write=os.write, fsync=os.fsync, fstat=os.fstat, close=os.close),
        resource=types.SimpleNamespace(RLIMIT_FSIZE=1, RLIMIT_CPU=2, RLIMIT_CORE=3,
            RLIMIT_AS=4, RLIMIT_NPROC=5, getrlimit=lambda _key: (4096, 4096)),
        signal=types.SimpleNamespace(SIGXFSZ=25, SIG_IGN=signal.SIG_IGN, signal=lambda *_args: None),
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), module.__dict__)
    assert not any(hasattr(module, name) for name in ("main", "positive", "libc_handle"))
    return module


@pytest.fixture
def worker():
    return load_worker_protocol()


class Function:
    def __init__(self, body):
        self.body, self.calls = body, []
    def __call__(self, *args):
        self.calls.append(args)
        return self.body(*args)


def test_denials_attempt_only_pinned_calls_and_expect_eperm_without_real_kernel(worker):
    def denied_fork():
        raise PermissionError(errno.EPERM, "modeled deny")
    worker.os.fork = denied_fork
    def denied_syscall(*args):
        ctypes.set_errno(errno.EPERM)
        return -1
    def prctl(operation, *args):
        if operation == 4:
            assert args == (1, 0, 0, 0)
            ctypes.set_errno(errno.EPERM)
            return -1
        assert operation == 3
        return 0
    lib = types.SimpleNamespace(syscall=Function(denied_syscall), prctl=Function(prctl),
                                pthread_create=Function(lambda *_args: errno.EPERM))
    observed = worker.denials(lib)
    assert set(observed) == {"fork_errno", "execve_errno", "execveat_errno", "clone3_errno",
                             "dumpable_set_errno", "pthread_create_error"}
    assert set(observed.values()) == {errno.EPERM}
    assert [args[0].value for args in lib.syscall.calls] == [59, 322, 435]
    assert all(len(args) == 7 and [arg.value for arg in args[1:]] == [0] * 6 for args in lib.syscall.calls)
    assert len(lib.pthread_create.calls) == 1


@pytest.mark.parametrize("error", [errno.EAGAIN, errno.ENOSYS, errno.EFAULT])
def test_fault_or_other_denial_is_not_accepted_as_seccomp_eperm(worker, error):
    def wrong_fork():
        raise OSError(error, "modeled other refusal")
    worker.os.fork = wrong_fork
    with pytest.raises(RuntimeError, match="fork was not denied by EPERM"):
        worker.denials(types.SimpleNamespace())


@pytest.mark.parametrize("address,error,accepted", [(ctypes.c_void_p(-1).value, errno.ENOMEM, True),
                                                   (ctypes.c_void_p(-1).value, errno.EINVAL, False),
                                                   (4096, 0, False)])
def test_address_space_requests_virtual_only_and_unmaps_unexpected_success(worker, address, error, accepted):
    worker.mmap = types.SimpleNamespace(PROT_READ=1, PROT_WRITE=2, MAP_PRIVATE=2, MAP_ANONYMOUS=32)
    def mmap(*_args):
        ctypes.set_errno(error)
        return address
    lib = types.SimpleNamespace(mmap=Function(mmap), munmap=Function(lambda *_args: 0))
    if accepted:
        result = worker.address_space(lib)
        assert result == {"requested_virtual_bytes": 3 * 1024**3, "touched_bytes": 0, "mmap_errno": errno.ENOMEM}
    else:
        with pytest.raises(RuntimeError):
            worker.address_space(lib)
    assert lib.mmap.calls == [(None, 3 * 1024**3, 3, 34, -1, 0)]
    assert lib.munmap.calls == ([] if address == ctypes.c_void_p(-1).value else [(4096, 3 * 1024**3)])


def test_fsize_protocol_real_host_file_with_modeled_limit_denial(worker, tmp_path):
    # Real bounded 4096-byte host artifact, but EFBIG is injected: no Linux limit claim.
    path = tmp_path / "fsize.bin"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    native_write = os.write
    signals = []
    worker.os.open = lambda *_args: fd
    def bounded_write(target, raw):
        if len(raw) == 1:
            raise OSError(errno.EFBIG, "modeled RLIMIT_FSIZE denial")
        return native_write(target, raw)
    worker.os.write = bounded_write
    worker.signal.signal = lambda *args: signals.append(args)
    result = worker.fsize()
    assert result == {"extension_errno": errno.EFBIG, "file_bytes": 4096}
    assert path.read_bytes() == b"x" * 4096
    assert signals == [(25, worker.signal.SIG_IGN)]
    with pytest.raises(OSError):
        os.fstat(fd)


@pytest.mark.parametrize("failure", ["short", "wrong_errno", "unexpected_extension"])
def test_fsize_failure_cannot_emit_success_and_closes_fd(worker, tmp_path, failure):
    path = tmp_path / "failed-fsize.bin"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    worker.os.open = lambda *_args: fd
    def write(target, raw):
        if failure == "short" and len(raw) == 4096:
            return os.write(target, raw[:10])
        if failure == "wrong_errno" and len(raw) == 1:
            raise OSError(errno.ENOSPC, "modeled unrelated failure")
        return os.write(target, raw)
    worker.os.write = write
    with pytest.raises(RuntimeError):
        worker.fsize()
    with pytest.raises(OSError):
        os.fstat(fd)
    assert path.stat().st_size <= 4097


def test_control_record_short_writes_exactly_preserve_json(worker):
    pieces = []
    def write(fd, raw):
        assert fd == 1
        count = min(7, len(raw))
        pieces.append(raw[:count])
        return count
    worker.os.write = write
    value = {"format": worker.FORMAT, "solution": [2.0, 2.0], "unicode": "\u00fc"}
    worker.emit(value)
    raw = b"".join(pieces)
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1 and len(raw) < 8192
    assert json.loads(raw) == value


def test_control_record_overflow_never_reaches_write(worker):
    worker.os.write = lambda *_args: pytest.fail("oversized control record was written")
    with pytest.raises(RuntimeError, match="control record exceeds bound"):
        worker.emit({"value": "x" * 8192})


def test_control_record_zero_progress_stops(worker):
    worker.os.write = lambda *_args: 0
    with pytest.raises(RuntimeError, match="output made no progress"):
        worker.emit({"value": "small"})


def test_real_host_sqlite_relative_name_is_canonicalized_to_absolute_file(tmp_path, monkeypatch):
    # This is a real host SQLite observation, not a Linux path-permission
    # probe. Unix traversal behavior is reviewed from SQLite/Linux sources.
    monkeypatch.chdir(tmp_path)
    fd = os.open("probe.sqlite3", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    connection = sqlite3.connect("probe.sqlite3")
    try:
        connection.execute("PRAGMA page_size=4096")
        assert connection.execute("PRAGMA journal_mode=MEMORY").fetchone() == ("memory",)
        connection.execute("PRAGMA temp_store=MEMORY")
        assert connection.execute("PRAGMA max_page_count=64").fetchone() == (64,)
        connection.execute("CREATE TABLE probe(x INTEGER NOT NULL)")
        connection.executemany("INSERT INTO probe VALUES(?)", [(2,), (3,), (5,)])
        connection.commit()
        filename = connection.execute("PRAGMA database_list").fetchone()[2]
        assert Path(filename).is_absolute()
        assert Path(filename).resolve() == (tmp_path / "probe.sqlite3").resolve()
    finally:
        connection.close()
    assert 0 < (tmp_path / "probe.sqlite3").stat().st_size <= 256 * 1024
    reopened = sqlite3.connect((tmp_path / "probe.sqlite3").as_uri() + "?mode=ro", uri=True)
    try:
        assert reopened.execute("SELECT count(*), sum(x) FROM probe").fetchone() == (3, 10)
    finally:
        reopened.close()


def test_definition_loader_does_not_import_worker_or_expose_launch_path():
    before = sys.modules.get("native_preparation_worker")
    model = load_worker_protocol()
    assert not any(hasattr(model, name) for name in ("main", "positive", "libc_handle"))
    assert not hasattr(model.os, "fork") and not hasattr(model.os, "open")
    assert sys.modules.get("native_preparation_worker") is before
