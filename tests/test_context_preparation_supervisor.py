"""Portable decoder/protocol tests only; simulated readbacks are NOT Linux QA."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import math
import os
import sys

import pytest

import context_preparation_supervisor as owner


def status_bytes(**changes):
    values = {"Name": "worker", "Pid": "900", "Tgid": "900", "PPid": str(os.getpid()), "TracerPid": "0",
              "State": "T (stopped)", "Uid": "701\t701\t701\t701",
              "Gid": "702\t702\t702\t702", "Groups": "", "Threads": "1", "VmHWM": "1234 kB",
              "NoNewPrivs": "1", "Seccomp": "2", "Seccomp_filters": "1"}
    values.update({name: "0000000000000000" for name in owner._CAP_FIELDS})
    values.update(changes)
    return "".join(f"{key}:\t{value}\n" for key, value in values.items()).encode("ascii")


@pytest.fixture
def launch_request(tmp_path):
    return {"argv": (str((tmp_path / "sealed-worker.py").absolute()), "fixture"),
            "uid": 701, "gid": 702, "cwd": tmp_path.absolute(), "workspace_fd": 7,
            "file_size_bytes": 4096, "cpu_seconds": 300, "wall_seconds": 300}


def test_valid_bounded_request_does_not_itself_grant_native_access(launch_request):
    assert owner._validate_request(**launch_request) is None


@pytest.mark.parametrize("key,value", [
    ("uid", 0), ("uid", True), ("uid", -1), ("uid", 2**31), ("gid", 0), ("gid", 1.0),
    ("workspace_fd", True), ("workspace_fd", -1), ("workspace_fd", "7"),
    ("file_size_bytes", 4095), ("file_size_bytes", True), ("file_size_bytes", 4 * 1024**3 + 1),
    ("cpu_seconds", 0), ("cpu_seconds", 301), ("cpu_seconds", 299.0), ("cpu_seconds", True),
    ("wall_seconds", 0), ("wall_seconds", 3601), ("wall_seconds", 300.0), ("wall_seconds", False),
    ("argv", []), ("argv", ()), ("argv", ("python",)), ("argv", ("",)),
    ("argv", ("/bin/worker.py", None)), ("argv", ("/bin/worker.py", "\0")),
    ("argv", ("/bin/worker.py", "\ud800")), ("argv", ("/bin/worker.py", "x" * 65536)),
    ("argv", ("/bin/worker.py",) * 33), ("cwd", "C:/existing"), ("cwd", Path("relative")),
], ids=lambda value: type(value).__name__)
def test_invalid_request_rejected_before_fork(launch_request, key, value):
    launch_request[key] = value
    with pytest.raises(owner.NativeSupervisorError):
        owner._validate_request(**launch_request)


@pytest.mark.parametrize("cpu,wall,size", [(1, 1, 4096), (300, 3600, 4 * 1024**3)])
def test_limits_can_be_tighter_but_not_wider(launch_request, cpu, wall, size):
    launch_request.update(cpu_seconds=cpu, wall_seconds=wall, file_size_bytes=size)
    owner._validate_request(**launch_request)


def test_status_has_exact_duplicate_and_bounded_byte_detection():
    parsed = owner._status(status_bytes())
    assert owner._rss(parsed) == 1234 * 1024
    assert parsed["Groups"] == ""
    assert parsed["State"] == "T (stopped)"


@pytest.mark.parametrize("raw", [b"", "Name: x\n", b"Name: x", b"a\n", b": x\n",
                                b"Name: x\nName: y\n", b"Name: \xff\n",
                                b"Name: " + b"x" * owner.PROC_BYTES + b"\n"],
                         ids=["empty", "text", "unterminated", "no-colon", "no-name",
                              "duplicate", "non-ascii", "oversized"])
def test_invalid_status_bytes(raw):
    with pytest.raises(owner.NativeSupervisorError):
        owner._status(raw)


@pytest.mark.parametrize("value", ["", "-1", "+1", "1.0", "1 2", " 1", "1\n", "1\0", "a", "9" * 21,
                                  str(2**64), None, True, 1])
def test_unsigned_counter_no_coercion(value):
    with pytest.raises(owner.NativeSupervisorError):
        owner._unsigned(value)


def test_hex_and_decimal_kernel_counter_boundaries():
    assert owner._unsigned("000") == 0
    assert owner._unsigned(str(2**64 - 1)) == 2**64 - 1
    assert owner._unsigned("ffffffffFFFFFFFF", base=16) == 2**64 - 1


@pytest.mark.parametrize("raw", ["0 kB", "-1 kB", "1 KB", "1 KiB", "1", "1.5 kB", "1 kB extra", "" ])
def test_rss_missing_zero_or_untyped_is_not_zero_memory(raw):
    with pytest.raises(owner.NativeSupervisorError):
        owner._rss({"VmHWM": raw})
    with pytest.raises(owner.NativeSupervisorError):
        owner._rss({})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -0.1, True, "0.1", 3601])
def test_terminal_cpu_invalid_data_is_not_success(value):
    with pytest.raises(owner.NativeSupervisorError):
        owner._usage_cpu_ns(SimpleNamespace(ru_utime=value, ru_stime=0))


def test_terminal_cpu_charges_both_terms_rounding_up():
    value = SimpleNamespace(ru_utime=0.1234567891, ru_stime=0.0000000001)
    assert owner._usage_cpu_ns(value) == 123456791
    assert owner._usage_cpu_ns(SimpleNamespace(ru_utime=0, ru_stime=0)) == 0


@pytest.fixture
def simulated_kernel(monkeypatch):
    # A simulation of kernel readback rejection, deliberately not native proof.
    fields = {"RLIMIT_CPU": 0, "RLIMIT_AS": 1, "RLIMIT_FSIZE": 2, "RLIMIT_NPROC": 3, "RLIMIT_CORE": 4}
    values = {0: (300, 300), 1: (owner.AS_BYTES, owner.AS_BYTES), 2: (4096, 4096), 3: (0, 0), 4: (0, 0)}
    calls = []

    def prlimit(pid, key):
        calls.append((pid, key))
        return values[key]

    monkeypatch.setitem(sys.modules, "resource", SimpleNamespace(**fields, prlimit=prlimit))
    state = {"raw": status_bytes()}
    monkeypatch.setattr(owner, "_read_small", lambda _: state["raw"])
    monkeypatch.setattr(owner, "_one_task", lambda pid: calls.append((pid, "tasks")))
    return state, values, calls


def test_simulated_matching_readback_checks_all_actual_limit_fields(simulated_kernel):
    state, values, calls = simulated_kernel
    result = owner._kernel_readback(900, 701, 702, 300, 4096)
    assert result == owner.KernelReadback(900, 701, 702, 300, 4096, 1, 1234 * 1024)
    assert calls == [(900, "tasks")] + [(900, key) for key in range(5)]


@pytest.mark.parametrize("key,value", [
    ("State", "R (running)"), ("State", "t (tracing stop)"), ("Uid", "701 701 701 0"),
    ("Uid", "701 701 701"), ("Gid", "702 702 702 703"), ("Groups", "702"),
    ("NoNewPrivs", "0"), ("Seccomp", "0"), ("Seccomp", "1"), ("Seccomp_filters", "0"),
    ("Seccomp_filters", "1.0"), ("Threads", "2"), ("VmHWM", "0 kB"),
    ("Seccomp_filters", "257"), ("Pid", "901"), ("Tgid", "901"), ("PPid", "0"), ("TracerPid", "1"),
] + [(name, "0000000000000001") for name in owner._CAP_FIELDS])
def test_simulated_kernel_disagreement_refuses_resume(simulated_kernel, key, value):
    state, _, _ = simulated_kernel
    state["raw"] = status_bytes(**{key: value})
    with pytest.raises(owner.NativeSupervisorError):
        owner._kernel_readback(900, 701, 702, 300, 4096)


@pytest.mark.parametrize("key", range(5))
def test_simulated_raised_soft_or_hard_resource_never_accepted(simulated_kernel, key):
    _, values, _ = simulated_kernel
    old = values[key][0]
    values[key] = (old, old + 1)
    with pytest.raises(owner.NativeSupervisorError):
        owner._kernel_readback(900, 701, 702, 300, 4096)


def test_windows_entrypoint_fails_before_importing_guard_or_launching(launch_request, monkeypatch):
    monkeypatch.setattr(owner.sys, "platform", "win32")
    with pytest.raises(owner.NativeSupervisorUnavailable, match="Linux"):
        owner.run_single_process(**launch_request)


def test_portable_readback_does_not_itself_become_run_or_authority():
    value = owner.KernelReadback(900, 701, 702, 300, 4096, 1, 1024)
    assert replace(value, uid=0).uid == 0
    assert not hasattr(value, "publish")
    assert not hasattr(value, "settle")
    assert not hasattr(value, "approved")


def test_unreaped_child_error_carries_owned_handle_without_success():
    error = owner.UnreapedChild(900, 15)
    assert error.pid == 900 and error.pidfd == 15
    assert "STOP" in str(error)
    assert not hasattr(error, "exit_code")


@pytest.mark.parametrize("source", ["signal", "wait", "deadline"])
def test_cleanup_unknown_custody_preserves_original_fd_without_allocating(monkeypatch, source):
    monkeypatch.setattr(owner.signal, "SIGKILL", 9, raising=False)
    calls = []
    def fail(*_):
        raise OSError("injected unavailable measurement")
    monkeypatch.setattr(owner, "_signal_owned", fail if source == "signal" else lambda *args: calls.append(args))
    monkeypatch.setattr(owner.os, "wait4", fail if source == "wait" else lambda *_: (0, 0, None), raising=False)
    monkeypatch.setattr(owner.os, "WNOHANG", 1, raising=False)
    counter = iter((0.0, 6.0))
    monkeypatch.setattr(owner.time, "monotonic", lambda: next(counter))
    # No os.dup or pidfd_open may be needed during an allocation-failure STOP.
    monkeypatch.setattr(owner.os, "dup", fail)
    monkeypatch.setattr(owner.os, "pidfd_open", fail, raising=False)
    with pytest.raises(owner.UnreapedChild) as captured:
        owner._cleanup(900, 23)
    assert captured.value.pid == 900
    assert captured.value.pidfd == 23
    if source != "signal":
        assert len(calls) == 1


def test_cleanup_terminal_child_returns_real_usage_object_once(monkeypatch):
    monkeypatch.setattr(owner.signal, "SIGKILL", 9, raising=False)
    usage = SimpleNamespace(ru_utime=0.1, ru_stime=0.2, ru_maxrss=1024)
    calls = []
    monkeypatch.setattr(owner, "_signal_owned", lambda *args: calls.append(args))
    monkeypatch.setattr(owner.os, "wait4", lambda *_: (900, 0, usage), raising=False)
    monkeypatch.setattr(owner.os, "WNOHANG", 1, raising=False)
    monkeypatch.setattr(owner.os, "WIFEXITED", lambda status: status == 0, raising=False)
    monkeypatch.setattr(owner.os, "WIFSIGNALED", lambda _: False, raising=False)
    assert owner._cleanup(900, 23) == (0, usage)
    assert len(calls) == 1


def test_native_module_has_only_stdlib_or_exact_guard_imports():
    import ast
    tree = ast.parse(Path(owner.__file__).read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert imports <= sys.stdlib_module_names | {"context_preparation_process_guard"}


def test_current_exact_environment_readback_is_required(monkeypatch):
    monkeypatch.setattr(owner.os, "environ", {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    assert owner._require_clean_environment() is None


@pytest.mark.parametrize("environment", [
    {}, {"PATH": "/usr/bin:/bin"}, {"LANG": "C.UTF-8"},
    {"PATH": "/usr/bin:/bin", "LANG": "C"},
    {"PATH": "/tmp:/usr/bin:/bin", "LANG": "C.UTF-8"},
    {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONPATH": "/tmp"},
    {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LD_PRELOAD": ""},
    {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "APP_SECRET": "fixture-not-a-secret"},
], ids=["empty", "missing-lang", "missing-path", "locale", "path", "pythonpath", "preload", "secret"])
def test_unexpected_parent_environment_is_not_silently_scrubbed(monkeypatch, environment):
    before = dict(environment)
    monkeypatch.setattr(owner.os, "environ", environment)
    with pytest.raises(owner.NativeSupervisorUnavailable, match="environment"):
        owner._require_clean_environment()
    assert environment == before
