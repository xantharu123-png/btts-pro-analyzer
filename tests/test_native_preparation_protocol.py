"""Versioned independent native-diagnostic protocol regressions; NO native start.

Every privilege, limit, process, /proc, pidfd and filesystem seal here is a
deterministic model. We execute the real coordinator flow/decoders against
those models, not the Linux worker, numerical imports, root or real signals.
"""
import ast
import builtins
import ctypes
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
NANO = 10**9


def load_parent_protocol():
    """Compile definitions only; never import the native module or its CLI.

    The coordinator body is renamed and can only see model dependencies.
    Undeclared imports, file opens and dynamic exec fail in this test namespace.
    This is a regression-test harness, not a production Python sandbox.
    """
    path = ROOT / "tests/native_preparation_probe.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    constants = {
        "FORMAT", "WORKER_FORMAT", "HELPERS", "WORKER_SHA256", "MIB", "NANO",
        "MANIFEST_BYTES", "SOURCE_BYTES", "REPORT_BYTES", "ARTIFACT_BYTES",
        "RESERVED_CPU_NS", "PARENT_CPU_SECONDS", "WALL_SECONDS", "CASES",
        "PLANNED_HARD_CPU_SECONDS", "PLANNED_ARTIFACT_BYTES", "CAP_FIELDS",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            assert all(isinstance(target, ast.Name) and target.id in constants
                       for target in node.targets)
            nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name == "main":
                node.name = "coordinator_flow"
            nodes.append(node)
    module = types.ModuleType("native_parent_protocol_model")
    module.__file__ = str(path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unmodeled external operation in native protocol test")

    def model_import(name, *_args, **_kwargs):
        assert name == "resource", "unexpected import in native protocol model"
        return module.resource

    namespace = module.__dict__
    namespace.update(
        __builtins__={**vars(builtins), "__import__": model_import, "open": forbidden, "exec": forbidden},
        dataclasses=dataclasses, hashlib=hashlib, json=json, math=math,
        Path=PurePosixPath, stat=stat, types=types,
        os=types.SimpleNamespace(),
        signal=types.SimpleNamespace(SIGSTOP=19, SIGKILL=9),
        time=types.SimpleNamespace(CLOCK_BOOTTIME=7),
        sys=types.SimpleNamespace(platform=sys.platform, byteorder=sys.byteorder,
            stdlib_module_names=sys.stdlib_module_names, modules=dict(sys.modules),
            version=sys.version, path=list(sys.path),
            implementation=types.SimpleNamespace(name=sys.implementation.name)),
        ctypes=types.SimpleNamespace(c_int=ctypes.c_int, c_long=ctypes.c_long,
            c_ulong=ctypes.c_ulong, c_void_p=ctypes.c_void_p, sizeof=ctypes.sizeof),
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    assert not hasattr(module, "main")
    return module


@pytest.fixture
def probe():
    return load_parent_protocol()


@dataclasses.dataclass(frozen=True)
class Readback:
    pid: int = 1234
    uid: int = 65534
    gid: int = 65534
    cpu_seconds: int = 15
    file_size_bytes: int = 512 * 1024
    seccomp_filters: int = 2
    initial_rss_bytes: int = 8 * 1024**2


@dataclasses.dataclass(frozen=True)
class NativeResult:
    exit_code: int
    stop_reason: str | None
    kernel_readback: Readback | None
    child_cpu_ns: int
    parent_cpu_ns: int
    elapsed_ns: int
    peak_rss_bytes: int
    observed_output_bytes: int
    output_digest: str
    stdout_prefix: bytes
    stderr_prefix: bytes
    minimum_free_bytes: int
    maximum_sample_gap_ns: int


def result_for(probe, mode, cpu, fsize):
    readback = Readback(cpu_seconds=cpu, file_size_bytes=fsize)
    state = dict(pid=readback.pid, uid=65534, gid=65534, threads=1, dumpable=0,
                 cpu_limit=[cpu, cpu], fsize_limit=[fsize, fsize], no_new_privs=1,
                 seccomp=2, seccomp_filters=2)
    payload = dict(format=probe.WORKER_FORMAT, mode=mode,
                   phase="armed" if mode in {"cpu", "output"} else "complete", state=state)
    if mode == "positive":
        payload["detail"] = {"solution": [2.0, 2.0], "sqlite_sum": 10}
    raw = probe.canonical(payload) + b"\n"
    if mode == "output":
        raw += b"x" * 300
    code = -9 if mode in {"cpu", "output"} else 0
    reason = "signal_exit" if mode == "cpu" else "output_limit" if mode == "output" else None
    return NativeResult(code, reason, readback, 1_100_000_000 if mode == "cpu" else 100_000_000,
                        10_000_000, NANO, 8 * 1024**2,
                        1024**2 + 1 if mode == "output" else len(raw),
                        hashlib.sha256(raw).hexdigest(), raw, b"", 5 * 1024**3, 100_000_000)


@dataclasses.dataclass(frozen=True)
class Ticket:
    reservation_id: str = "a" * 64
    reserved_cpu_ns: int = 60 * NANO


@dataclasses.dataclass(frozen=True)
class AccountState:
    status: str
    pending: Ticket | None
    charged_cpu_ns: int


class Unreaped(Exception):
    def __init__(self, pid=1234, pidfd=99):
        self.pid, self.pidfd = pid, pidfd
        super().__init__("modeled unknown reap")


class Model:
    def __init__(self, probe):
        self.probe = probe
        self.boot, self.cpu = 11 * NANO, 2 * NANO
        self.output_mode = 0o711
        self.events, self.calls, self.reports = [], [], []
        self.directories = {}
        self.root_names_before_admission = []
        self.report_latency = self.stdout_latency = self.directory_close_latency = self.seal_close_latency = 0
        self.close_failure = self.stop_failure = self.reserve_failure = None
        self.dumpable = 0
        self.run_hook = None
        self.closed, self.charge, self.status, self.pending = False, 0, "accounting-open", None
        self.ticket = Ticket()
        probe.os.getpid = lambda: 42
        probe.os.sysconf = lambda _name: 100
        probe.os.uname = lambda: ("Linux", "modeled", "6.8", "test", "x86_64")
        probe.os.fstat = lambda _fd: types.SimpleNamespace(st_mode=stat.S_IFDIR | self.output_mode)
        probe.os.close = self.close_fd
        probe.os.write = self.write_stdout
        probe.time.clock_gettime_ns = lambda _clock: self.boot
        probe.time.process_time_ns = lambda: self.cpu
        # Field 22 is tail[19]; start tick 1000 / HZ100 = boot second 10.
        probe.small_kernel = lambda *_args: b"42 (python) " + b" ".join([b"R"] + [b"0"] * 18 + [b"1000"]) + b"\n"
        def valid_parent_gate():
            self.events.append("modeled-native-platform-gate")
            return types.SimpleNamespace(prctl=lambda *_args: self.dumpable)
        probe.platform_and_parent_limits = valid_parent_gate
        model = self

        class ModeledSeals:
            def __init__(self, window):
                self.window = window
            def directory(self, path, *, child_search=False):
                assert path == PurePosixPath("/private/output") and child_search is True
                return 10
            def check(self):
                self.window.check(10)
            def close(self):
                model.events.append("seal-close")
                model.boot += model.seal_close_latency

        probe.Seals = ModeledSeals
        probe.parent_credentials = lambda: {"uid": 0, "capabilities": "fixed-model"}
        self.manifest = {"worker_path": "/sealed/native_preparation_worker.py", "dependency_directory": "/sealed/deps",
                         "worker_uid": 65534, "worker_gid": 65534, "probe_sha256": "0" * 64,
                         "python_sha256": "1" * 64}
        probe.manifest_and_helpers = lambda *_args: self.manifest
        probe.identity_for = lambda *_args: "modeled-bound-identity"
        probe.accounting_fixtures = lambda *_args: {"scope": "MODELED ONLY in this portable test"}
        probe.new_directory = self.new_directory
        probe.bounded_names = self.names
        probe.inventory = lambda _dirs: {"scope": "MODELED ONLY", "physical_quota_claim": False}
        probe.write_new_report = self.write_report
        probe.sys.modules["context_preparation_budget"] = types.SimpleNamespace(
            PreparationBudget=types.SimpleNamespace(create=lambda *_args: self))
        probe.sys.modules["context_preparation_supervisor"] = types.SimpleNamespace(
            run_single_process=self.run, UnreapedChild=Unreaped)

    def new_directory(self, parent, name, uid=0, gid=0):
        assert parent == 10 and name not in self.directories
        fd = 200 + len(self.directories)
        self.directories[name] = (fd, uid, gid)
        return fd

    def names(self, fd, maximum):
        assert fd == 10
        return list(self.directories) if self.directories else self.root_names_before_admission

    def reserve(self, identity, amount):
        self.events.append("durable-reserve-MODELED")
        assert self.pending is None and amount == 60 * NANO
        self.charge, self.pending = amount, self.ticket
        if self.reserve_failure:
            raise self.reserve_failure
        return self.ticket

    def snapshot(self):
        return AccountState(self.status, self.pending, self.charge)

    def stop_unmeasured(self):
        self.events.append("full-charge-stop")
        if self.stop_failure:
            raise self.stop_failure
        self.status = "stopped"
        return self.snapshot()

    def close(self):
        self.closed = True
        if self.close_failure:
            raise self.close_failure

    def run(self, argv, **limits):
        assert "durable-reserve-MODELED" in self.events and self.charge == 60 * NANO
        mode = argv[1]
        expected = next(case for case in self.probe.CASES if case[0] == mode)
        assert argv == ("/sealed/native_preparation_worker.py", mode, "/sealed/deps", "65534", "65534")
        assert limits == dict(uid=65534, gid=65534, cwd=PurePosixPath("/private/output") / mode,
                              workspace_fd=self.directories[mode][0], file_size_bytes=expected[3],
                              cpu_seconds=expected[1], wall_seconds=expected[2])
        self.calls.append(mode)
        self.boot += NANO
        result = result_for(self.probe, mode, expected[1], expected[3])
        return self.run_hook(mode, result) if self.run_hook else result

    def write_report(self, root_fd, name, report):
        assert root_fd == 10
        raw = self.probe.canonical(report)
        assert len(raw) <= self.probe.REPORT_BYTES
        self.reports.append(json.loads(raw))
        self.boot += self.report_latency
        return dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def write_stdout(self, fd, raw):
        assert fd in (1, 2) and len(raw) < 8192
        self.boot += self.stdout_latency
        return len(raw)

    def close_fd(self, fd):
        assert fd in [entry[0] for entry in self.directories.values()]
        self.events.append("directory-close")
        self.boot += self.directory_close_latency

    def run_protocol(self):
        return self.probe.coordinator_flow(["--manifest", "/sealed/manifest.json", "--manifest-sha256", "0" * 64,
                                "--directory", "/private/output"])


def test_complete_six_calls_share_original_window_and_one_permanent_charge(probe):
    model = Model(probe)
    assert model.run_protocol() == 0
    assert model.calls == [case[0] for case in probe.CASES]
    assert model.events.count("durable-reserve-MODELED") == 1
    assert model.events.count("full-charge-stop") == 1
    assert model.closed and model.status == "stopped" and model.charge == 60 * NANO
    assert model.pending == model.ticket
    report = model.reports[-1]
    assert report["parent_start_boot_ns"] == 10 * NANO and report["deadline_boot_ns"] == 130 * NANO
    assert report["returned_children_terminal_cpu_ns"] == 1_600_000_000
    assert report["native_call_without_returned_terminal_cost"] is None
    assert report["report_phase"].startswith("pre-exit observation; NEVER accept")
    assert report["no_corpus_or_B_authority"] is True
    assert "NOT Task27" in report["sqlite_scope"]


@pytest.mark.parametrize("latency_field", ["report_latency", "stdout_latency", "directory_close_latency", "seal_close_latency"])
def test_late_final_io_can_never_return_success(probe, latency_field):
    model = Model(probe)
    setattr(model, latency_field, 121 * NANO)
    assert model.run_protocol() == 1
    assert len(model.calls) == 6
    # Earlier observations cannot be accepted without terminal exit+wall.
    assert model.reports[-1]["status"] == "six-native-probes-passed-diagnostic-only"
    assert model.charge == 60 * NANO and model.closed


def test_all_six_wall_windows_are_not_independently_reset(probe):
    model = Model(probe)
    def slow(mode, result):
        model.boot += 20 * NANO
        return result
    model.run_hook = slow
    assert model.run_protocol() == 1
    assert model.calls == ["positive", "denials", "fsize", "address_space", "cpu"]
    assert model.reports[-1]["error"]["type"] == "ProbeError"
    assert model.charge == 60 * NANO


def test_cumulative_returned_child_cpu_is_not_reset(probe):
    model = Model(probe)
    model.run_hook = lambda _mode, result: dataclasses.replace(result, child_cpu_ns=28 * NANO)
    assert model.run_protocol() == 1
    assert model.calls == ["positive", "denials"]
    assert model.reports[-1]["returned_children_terminal_cpu_ns"] == 56 * NANO
    assert model.charge == 60 * NANO


def test_parent_cpu_includes_preexisting_and_between_call_work(probe):
    model = Model(probe)
    model.cpu = 14 * NANO
    def parent_work(mode, result):
        model.cpu += 500_000_000
        return result
    model.run_hook = parent_work
    assert model.run_protocol() == 1 and model.calls == ["positive", "denials"]
    assert model.reports[-1]["parent_cpu_observed_through_pre_report_ns"] == 15 * NANO


def test_final_parent_dumpability_change_never_returns_success(probe):
    model = Model(probe)
    model.dumpable = 1
    assert model.run_protocol() == 1 and len(model.calls) == 6
    assert model.charge == 60 * NANO


@pytest.mark.parametrize("failure", ["native", "reserve", "stop", "close"])
def test_unknown_or_finalization_error_keeps_full_charge_and_never_succeeds(probe, failure):
    model = Model(probe)
    if failure == "native":
        def broken_run(_mode, _result):
            raise OSError("modeled terminal cost unavailable")
        model.run_hook = broken_run
    else:
        setattr(model, failure + "_failure", OSError("modeled accounting failure"))
    assert model.run_protocol() == 1
    assert model.charge == 60 * NANO and model.pending == model.ticket and model.closed
    if failure == "native":
        report = model.reports[-1]
        assert report["returned_children_terminal_cpu_ns"] == 0
        assert report["native_call_without_returned_terminal_cost"] == "positive"
    if failure == "reserve":
        assert model.calls == []


def test_existing_output_directory_is_not_written(probe):
    model = Model(probe)
    model.root_names_before_admission = ["existing-must-remain"]
    assert model.run_protocol() == 1
    assert not model.reports and not model.calls and not model.directories
    assert model.root_names_before_admission == ["existing-must-remain"]


@pytest.mark.parametrize("mode", [0o700, 0o710, 0o755, 0o777])
def test_wrong_output_mode_fails_before_report_or_launch(probe, mode):
    model = Model(probe)
    model.output_mode = mode
    assert model.run_protocol() == 1
    assert not model.reports and not model.calls and not model.directories


@pytest.mark.parametrize("now", [10 * NANO - 1, 130 * NANO, 131 * NANO])
def test_original_kernel_start_and_deadline_fail_closed(probe, now):
    model = Model(probe)
    model.boot = now
    assert model.run_protocol() == 1
    assert model.calls == [] and not model.reports


@pytest.mark.parametrize("mode", ["positive", "denials", "fsize", "address_space", "cpu", "output"])
def test_real_result_decoder_accepts_only_modeled_valid_corresponding_case(probe, mode):
    case = next(case for case in probe.CASES if case[0] == mode)
    result = result_for(probe, mode, case[1], case[3])
    payload = probe.check_result(result, mode, case[1], case[3], 65534, 65534)
    assert payload["mode"] == mode
    if mode == "positive":
        assert payload["detail"]["solution"] == [2.0, 2.0]


@pytest.mark.parametrize("field,value", [
    ("kernel_readback", None), ("child_cpu_ns", True), ("child_cpu_ns", -1),
    ("peak_rss_bytes", 0), ("peak_rss_bytes", 1024**3),
    ("minimum_free_bytes", 4 * 1024**3 - 1), ("stderr_prefix", b"error"),
    ("exit_code", -9), ("stop_reason", "sample_gap"),
    ("stdout_prefix", b"{}"), ("stdout_prefix", b"{}\n{}\n"),
    ("stdout_prefix", b"x" * 8193 + b"\n"),
])
def test_result_decoder_rejects_missing_overrun_or_error_measurement(probe, field, value):
    result = dataclasses.replace(result_for(probe, "positive", 15, 512 * 1024), **{field: value})
    with pytest.raises(probe.ProbeError):
        probe.check_result(result, "positive", 15, 512 * 1024, 65534, 65534)


@pytest.mark.parametrize("error_kind", ["signal", "wait", "echld", "wrongpid", "notterminal"])
def test_uncertain_reap_remains_in_custody_and_closes_no_pidfd(probe, error_kind):
    stops, closes, calls = [], [], []
    report = {}
    class StopObservation(BaseException):
        pass
    def kill(pid, sig):
        assert pid == 42 and sig == probe.signal.SIGSTOP
        stops.append((pid, sig))
        if len(stops) == 2:
            raise StopObservation()
    def pidfd_signal(fd, sig):
        assert fd == 99 and sig == 9
        calls.append("signal")
        if error_kind == "signal":
            raise PermissionError("modeled unknown signal")
    def wait4(pid, options):
        calls.append("wait")
        if error_kind == "wait":
            raise OSError("modeled wait error")
        if error_kind == "echld":
            raise ChildProcessError("modeled ECHILD")
        return (9999 if error_kind == "wrongpid" else pid, 0, types.SimpleNamespace())
    probe.os.getpid = lambda: 42
    probe.os.kill, probe.os.wait4 = kill, wait4
    probe.os.WNOHANG = 1
    probe.os.WIFEXITED = lambda _status: error_kind != "notterminal"
    probe.os.WIFSIGNALED = lambda _status: False
    probe.os.close = closes.append
    probe.os.write = lambda _fd, raw: len(raw)
    probe.signal.pidfd_send_signal = pidfd_signal
    probe.write_new_report = lambda *_args: None
    with pytest.raises(StopObservation):
        probe.custody_stop(Unreaped(), 10, report)
    assert len(stops) == 2 and closes == []
    assert report["status"] == "operator-custody-required-NOT-complete"
    if error_kind in {"signal", "wait", "echld"}:
        assert "custody_reap_error" in report


def test_terminal_exact_child_reap_closes_transferred_pidfd_once(probe):
    closes, stops = [], []
    probe.os.getpid = lambda: 42
    probe.os.kill = lambda pid, sig: stops.append((pid, sig))
    probe.os.WNOHANG = 1
    probe.os.wait4 = lambda *_args: (1234, 0, types.SimpleNamespace(ru_utime=0.1, ru_stime=0.2, ru_maxrss=8192))
    probe.os.WIFEXITED = lambda _status: True
    probe.os.WIFSIGNALED = lambda _status: False
    probe.os.waitstatus_to_exitcode = lambda _status: 0
    probe.os.close = closes.append
    probe.os.write = lambda _fd, raw: len(raw)
    probe.signal.pidfd_send_signal = lambda *_args: None
    probe.write_new_report = lambda *_args: None
    report = {}
    probe.custody_stop(Unreaped(), 10, report)
    assert closes == [99] and stops == [(42, 19)]
    assert report["custody_terminal_after_operator_resume"]["child_cpu_ns"] == 300_000_000
    assert report["status"] == "operator-custody-required-NOT-complete"


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}', b'{"x":Infinity}', b""])
def test_manifest_parser_never_normalizes_duplicate_float_or_nonfinite(raw, probe):
    with pytest.raises(probe.ProbeError):
        probe.bounded_json(raw, 100)


def test_all_pinned_helper_and_worker_hashes_match_actual_source(probe):
    for name, expected in probe.HELPERS.items():
        assert hashlib.sha256((ROOT / (name + ".py")).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((ROOT / "tests/native_preparation_worker.py").read_bytes()).hexdigest() == probe.WORKER_SHA256
    assert probe.PLANNED_HARD_CPU_SECONDS == 43 and probe.RESERVED_CPU_NS == 60 * NANO
    assert probe.PLANNED_ARTIFACT_BYTES < probe.ARTIFACT_BYTES == 64 * 1024**2


class KernelCall:
    def __init__(self, returns):
        self.returns = iter(returns)
        self.calls = []
    def __call__(self, *args):
        self.calls.append(args)
        return next(self.returns)


@pytest.mark.parametrize("returns,accepted", [([1, 0, 0], True), ([0, 0, 0], True),
                                              ([-1], False), ([3], False),
                                              ([1, -1], False), ([1, 0, 1], False)])
def test_parent_dumpable_set_get_protocol_precedes_all_limit_and_probe_io(probe, returns, accepted):
    probe.sys.platform = "linux"
    probe.sys.flags = types.SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1)
    probe.sys.modules = {"__main__": types.SimpleNamespace()}
    probe.os.uname = lambda: types.SimpleNamespace(machine="x86_64")
    probe.os.getresuid = probe.os.getresgid = lambda: (0, 0, 0)
    probe.os.environ = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    current = object()
    probe.threading = types.SimpleNamespace(active_count=lambda: 1,
        current_thread=lambda: current, main_thread=lambda: current)
    kernel = KernelCall(returns)
    libc = types.SimpleNamespace(prctl=kernel)
    probe.ctypes = types.SimpleNamespace(**vars(probe.ctypes))
    probe.ctypes.sizeof = lambda _type: 8  # Explicit Linux LP64 model, not Windows ABI evidence.
    probe.ctypes.CDLL = lambda name, use_errno: libc
    limit_calls = []
    limits = {}
    def setlimit(key, pair):
        assert kernel.calls[:3] == [(3, 0, 0, 0, 0), (4, 0, 0, 0, 0), (3, 0, 0, 0, 0)]
        limit_calls.append((key, pair))
        limits[key] = pair
    resource = types.SimpleNamespace(RLIMIT_CPU=1, RLIMIT_CORE=2, RLIMIT_AS=3, RLIMIT_FSIZE=4,
        RLIM_INFINITY=-1, getrlimit=lambda key: limits.get(key, (-1, -1)), setrlimit=setlimit)
    probe.resource = resource
    if accepted:
        assert probe.platform_and_parent_limits() is libc
        assert limit_calls == [(1, (15, 15)), (2, (0, 0)), (3, (2 * 1024**3,) * 2),
                               (4, (1024**2,) * 2)]
    else:
        with pytest.raises(probe.ProbeError):
            probe.platform_and_parent_limits()
        assert limit_calls == []


def test_definition_loader_has_no_native_import_or_cli_entrypoint():
    names = ("native_preparation_probe", "native_preparation_worker",
             "native_preparation_seal", "context_preparation_supervisor")
    before = {name: sys.modules.get(name) for name in names}
    model = load_parent_protocol()
    assert not hasattr(model, "main")
    assert not hasattr(model.os, "fork") and not hasattr(model.os, "open")
    assert {name: sys.modules.get(name) for name in names} == before
