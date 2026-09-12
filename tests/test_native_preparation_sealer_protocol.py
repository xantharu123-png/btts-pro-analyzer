"""Versioned sealer protocol checks, never a native/root sealing run.

Linux flags and privilege operations are modeled. Pipe/regular-file FD checks
use real tiny portable fixtures, not a Linux FIFO race or filesystem quota.
"""
import ast
import builtins
import ctypes
import io
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_sealer_protocol():
    """Load only definitions, without importing the sealer or exposing main."""
    path = ROOT / "tests/native_preparation_seal.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    constants = {"MIB", "FREE_BYTES", "COPY_SLOT_BYTES", "OUTPUT_SLOT_BYTES",
                 "ARCHIVE_BYTES", "MAX_FILES", "EXPECTED_BYTES", "EXPECTED_COUNT",
                 "DEPENDENCY_SHA256", "DEPENDENCY_SOURCE", "PACKAGES", "HELPERS"}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            assert all(isinstance(target, ast.Name) and target.id in constants
                       for target in node.targets)
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef):
            if node.name == "main":
                node.name = "sealer_flow"
            nodes.append(node)
    module = types.ModuleType("native_sealer_protocol_model")
    module.__file__ = str(path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unmodeled external operation in sealer protocol test")

    def model_import(name, *_args, **_kwargs):
        assert name in {"ctypes", "resource"}, "unexpected sealer model import"
        return getattr(module, name)

    module.__dict__.update(
        __builtins__={**vars(builtins), "__import__": model_import, "open": forbidden, "exec": forbidden},
        hashlib=hashlib, io=io, json=json, Path=PurePosixPath, stat=stat, tarfile=tarfile,
        time=types.SimpleNamespace(monotonic=lambda: 1.0),
        sys=types.SimpleNamespace(platform=sys.platform),
        os=types.SimpleNamespace(
            O_RDONLY=os.O_RDONLY, O_WRONLY=os.O_WRONLY, O_CREAT=os.O_CREAT, O_EXCL=os.O_EXCL,
            O_NOFOLLOW=0x20000, O_CLOEXEC=0x80000, O_NONBLOCK=0x800,
            read=os.read, write=os.write, fstat=os.fstat, close=os.close, fsync=os.fsync),
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), module.__dict__)
    assert not hasattr(module, "main")
    return module


@pytest.fixture
def seal():
    return load_sealer_protocol()


class ObservedPath:
    def __init__(self, observations):
        self.observations = iter(observations)
        self.last = None

    def lstat(self):
        try:
            self.last = next(self.observations)
        except StopIteration:
            pass
        return self.last


def fd_info(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"bounded source bytes")
    fd = os.open(path, os.O_RDONLY)
    return fd, os.fstat(fd)


def test_fifo_replacement_open_is_nonblocking_before_real_pipe_type_binding(seal, tmp_path):
    source_fd, original = fd_info(tmp_path)
    pipe_read, pipe_write = os.pipe()
    opened = []
    real_read = seal.os.read

    def open_replacement(path, flags):
        # With the original flags Linux can block here before fstat forever.
        # This is a protocol assertion, not an actual blocking syscall test.
        assert flags & seal.os.O_NONBLOCK, "regular-to-FIFO replacement may block before fstat"
        assert flags & seal.os.O_NOFOLLOW
        assert flags & seal.os.O_CLOEXEC
        opened.append(pipe_read)
        return pipe_read

    def never_read(fd, count):
        raise AssertionError("different real pipe FD must be rejected before read")

    seal.os.open = open_replacement
    seal.os.read = never_read
    try:
        assert stat.S_ISFIFO(os.fstat(pipe_read).st_mode)
        with pytest.raises(RuntimeError, match="opened source differs"):
            seal.regular(ObservedPath([original]), 1024)
        assert opened == [pipe_read]
        with pytest.raises(OSError):
            os.fstat(pipe_read)
    finally:
        seal.os.read = real_read
        for fd in (source_fd, pipe_read, pipe_write):
            try:
                os.close(fd)
            except OSError:
                pass


def test_real_other_regular_fd_rejected_before_read_and_closed(seal, tmp_path):
    source_fd, original = fd_info(tmp_path)
    other_path = tmp_path / "replacement.bin"
    other_path.write_bytes(b"replacement bytes are never read")
    other_fd = os.open(other_path, os.O_RDONLY)
    seal.os.open = lambda _path, _flags: other_fd
    seal.os.read = lambda *_args: pytest.fail("replacement bytes were read")
    try:
        with pytest.raises(RuntimeError, match="opened source differs"):
            seal.regular(ObservedPath([original]), 1024)
        with pytest.raises(OSError):
            os.fstat(other_fd)
        assert other_path.read_bytes() == b"replacement bytes are never read"
    finally:
        os.close(source_fd)
        try:
            os.close(other_fd)
        except OSError:
            pass


def test_real_fd_short_reads_preserve_every_byte_and_close(seal, tmp_path):
    source_fd, original = fd_info(tmp_path)
    seal.os.open = lambda _path, _flags: source_fd
    native_read = os.read
    calls = []

    def short_read(fd, count):
        calls.append(count)
        return native_read(fd, min(3, count))

    seal.os.read = short_read
    result = seal.regular(ObservedPath([original]), 1024)
    assert result == b"bounded source bytes"
    assert len(calls) > 3 and max(calls) <= 1024 + 1
    with pytest.raises(OSError):
        os.fstat(source_fd)


@pytest.mark.parametrize("field", ["st_dev", "st_ino", "st_mode", "st_uid", "st_gid",
                                    "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"])
def test_terminal_identity_drift_rejected_with_real_fd_closed(seal, tmp_path, field):
    source_fd, original = fd_info(tmp_path)
    changed = types.SimpleNamespace(**{name: getattr(original, name) for name in
        ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size",
         "st_mtime_ns", "st_ctime_ns")})
    setattr(changed, field, getattr(changed, field) + 1)
    seal.os.open = lambda _path, _flags: source_fd
    with pytest.raises(RuntimeError, match="source identity changed"):
        seal.regular(ObservedPath([original, changed]), 1024)
    with pytest.raises(OSError):
        os.fstat(source_fd)


def test_growth_stops_after_at_most_maximum_plus_one_real_bytes(seal, tmp_path):
    source_fd, original = fd_info(tmp_path)
    small = types.SimpleNamespace(**{name: getattr(original, name) for name in
        ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size",
         "st_mtime_ns", "st_ctime_ns")})
    small.st_size = 4
    seal.os.open = lambda _path, _flags: source_fd
    seal.os.fstat = lambda _fd: small
    read_sizes = []

    def measured_read(fd, count):
        piece = os.read(fd, count)
        read_sizes.append(len(piece))
        return piece

    seal.os.read = measured_read
    with pytest.raises(RuntimeError, match="source grew beyond bound"):
        seal.regular(ObservedPath([small]), 4)
    assert sum(read_sizes) == 5
    with pytest.raises(OSError):
        os.fstat(source_fd)


def test_atime_alone_is_deliberately_not_content_identity(seal):
    fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size",
              "st_mtime_ns", "st_ctime_ns")
    first = types.SimpleNamespace(**dict.fromkeys(fields, 7), st_atime_ns=1)
    second = types.SimpleNamespace(**dict.fromkeys(fields, 7), st_atime_ns=99)
    assert seal.identity(first) == seal.identity(second)


@pytest.mark.parametrize("failure", ["zero", "write", "fsync"])
def test_fresh_output_error_always_closes_owned_fd(seal, tmp_path, failure):
    path = tmp_path / "new-copy.bin"
    output_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    seal.os.open = lambda *_args: output_fd
    seal.os.fchmod = lambda *_args: pytest.fail("incomplete file was made public-readable")
    if failure == "zero":
        seal.os.write = lambda *_args: 0
        expected = RuntimeError
    elif failure == "write":
        def broken_write(*_args):
            raise OSError("simulated write failure")
        seal.os.write = broken_write
        expected = OSError
    else:
        def broken_sync(*_args):
            raise OSError("simulated fsync failure")
        seal.os.fsync = broken_sync
        expected = OSError
    with pytest.raises(expected):
        seal.fresh_file(path, b"small approved copy")
    with pytest.raises(OSError):
        os.fstat(output_fd)


def test_no_truncation_of_preexisting_output(seal, tmp_path):
    path = tmp_path / "already-there.bin"
    original = b"do not replace or truncate this file"
    path.write_bytes(original)

    def real_host_open(target, flags, mode):
        assert flags & os.O_CREAT and flags & os.O_EXCL and not flags & os.O_TRUNC
        return os.open(target, flags & ~seal.os.O_NOFOLLOW, mode)

    seal.os.open = real_host_open
    with pytest.raises(FileExistsError):
        seal.fresh_file(path, b"replacement")
    assert path.read_bytes() == original


@pytest.mark.parametrize("returns,accepted", [([0, 0], True), ([-1], False), ([0, 1], False)])
def test_sealer_dumpability_protocol_fails_before_any_input_io(seal, returns, accepted):
    seal.sys = types.SimpleNamespace(**vars(sys))
    seal.sys.platform = "linux"
    seal.sys.flags = types.SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1)
    seal.os.getresuid = lambda: (0, 0, 0)
    seal.os.environ = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    seal.Path = PurePosixPath
    seal.DEPENDENCY_SOURCE = PurePosixPath("/modeled-qa/venv/lib/python3.12/site-packages")
    values, calls = iter(returns), []
    class Prctl:
        def __call__(self, *args):
            calls.append(args)
            return next(values)
    lib = types.SimpleNamespace(prctl=Prctl())
    fake_ctypes = types.SimpleNamespace(CDLL=lambda name, use_errno: lib,
                                        c_int=ctypes.c_int, c_ulong=ctypes.c_ulong)
    limit_calls = []
    resource = types.SimpleNamespace(RLIMIT_CPU=1, RLIMIT_AS=2, RLIMIT_FSIZE=3, RLIMIT_CORE=4,
        setrlimit=lambda *args: limit_calls.append(args))
    seal.ctypes = fake_ctypes
    seal.resource = resource
    class ReachedInput(BaseException):
        pass
    def first_input(*_args):
        assert calls == [(4, 0, 0, 0, 0), (3, 0, 0, 0, 0)]
        raise ReachedInput()
    seal.regular = first_input
    args = [str(seal.DEPENDENCY_SOURCE.parents[3] / "probe.tar"), "0" * 64, "1" * 64, "2" * 64]
    if accepted:
        with pytest.raises(ReachedInput):
            seal.sealer_flow(args)
        assert limit_calls == [(1, (30, 30)), (2, (512 * 1024**2,) * 2),
                               (3, (128 * 1024**2,) * 2), (4, (0, 0))]
    else:
        with pytest.raises(RuntimeError, match="nondumpable state unavailable"):
            seal.sealer_flow(args)
        assert limit_calls == []


def test_final_dumpable_and_layout_readback_is_before_seal_publication(seal):
    tree = ast.parse(Path(seal.__file__).read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = [node for node in ast.walk(main) if isinstance(node, ast.Call)]
    final_get = max(node.lineno for node in calls if ast.unparse(node.func) == "libc.prctl"
                    and ast.literal_eval(node.args[0]) == 3)
    publication = next(node for node in calls if ast.unparse(node.func) == "os.chmod"
                       and ast.unparse(node.args[0]) == "root")
    assert final_get < publication.lineno
    output_binding = next(node for node in ast.walk(main) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "output" for target in node.targets))
    assert ast.unparse(output_binding.value) == "root / 'output'"
    output_modes = [node for node in calls if ast.unparse(node.func) == "os.chmod"
                    and ast.unparse(node.args[0]) == "output"]
    assert len(output_modes) == 1 and ast.literal_eval(output_modes[0].args[1]) == 0o711
    assert output_modes[0].lineno < publication.lineno
    assert not any(ast.unparse(node.func) in {"os.execve", "os.setresuid", "os.setresgid"} for node in calls)


@pytest.fixture
def actual_source_archive(seal):
    sources = {name + ".py": (ROOT / (name + ".py")).read_bytes() for name in seal.HELPERS}
    sources.update({name: (ROOT / name).read_bytes() for name in
                    ("tests/native_preparation_probe.py", "tests/native_preparation_worker.py")})
    return sources


def make_archive(sources, damage=None):
    members = [(name, body, tarfile.REGTYPE) for name, body in sources.items()]
    if damage == "missing":
        members.pop()
    elif damage == "extra":
        members.append(("unexpected.py", b"unexpected", tarfile.REGTYPE))
    elif damage == "duplicate":
        members.append(members[0])
    elif damage == "traversal":
        name, body, kind = members[0]
        members[0] = ("../" + name, body, kind)
    elif damage in {"symlink", "hardlink", "fifo"}:
        kind = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE, "fifo": tarfile.FIFOTYPE}[damage]
        members[0] = (members[0][0], b"", kind)
    elif damage == "changed":
        name, body, kind = members[0]
        members[0] = (name, body + b"\n# changed\n", kind)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, body, kind in members:
            info = tarfile.TarInfo(name)
            info.type, info.size = kind, len(body)
            if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                info.linkname = "/must-not-read"
            archive.addfile(info, io.BytesIO(body))
    return output.getvalue()


def decode_actual(seal, raw, sources):
    return seal.decode_archive(
        raw, hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(sources["tests/native_preparation_probe.py"]).hexdigest(),
        hashlib.sha256(sources["tests/native_preparation_worker.py"]).hexdigest())


def test_complete_actual_five_pinned_sources_decode_without_extraction_or_import(seal, actual_source_archive):
    raw = make_archive(actual_source_archive)
    assert len(raw) <= seal.ARCHIVE_BYTES
    assert decode_actual(seal, raw, actual_source_archive) == actual_source_archive


@pytest.mark.parametrize("damage", ["missing", "extra", "duplicate", "traversal",
                                    "symlink", "hardlink", "fifo", "changed"])
def test_actual_archive_rejects_every_nonclosed_or_changed_member(seal, actual_source_archive, damage):
    raw = make_archive(actual_source_archive, damage)
    with pytest.raises(RuntimeError):
        decode_actual(seal, raw, actual_source_archive)


def test_definition_loader_has_no_native_sealer_import_or_entrypoint():
    before = sys.modules.get("native_preparation_seal")
    model = load_sealer_protocol()
    assert not hasattr(model, "main") and not hasattr(model.os, "open")
    assert sys.modules.get("native_preparation_seal") is before
