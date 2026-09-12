"""Decoder/policy/mock transitions are NOT native guard evidence.

Native tests are separately marked and run only in disposable fork children
of a separate Linux/root test process. They never guard the pytest process.
"""
from copy import deepcopy
import ctypes
import errno
import hashlib
import inspect
import importlib.util
import json
import os
from pathlib import Path
import signal
import site
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

import context_preparation_process_guard as guard


def status_bytes(**changes):
    data = {
        "Name": "qa-worker", "Tgid": "1234", "Pid": "1234", "PPid": "1200",
        "TracerPid": "0", "Uid": "1000\t1000\t1000\t1000",
        "Gid": "1000\t1000\t1000\t1000", "Groups": "", "Threads": "1",
        "CapInh": "0000000000000000", "CapPrm": "0000000000000000",
        "CapEff": "0000000000000000", "CapBnd": "0000000000000000",
        "CapAmb": "0000000000000000", "NoNewPrivs": "0", "Seccomp": "0",
        "Seccomp_filters": "0",
    }
    data.update(changes)
    return "".join(f"{key}:\t{value}\n" for key, value in data.items()).encode("ascii")


class SimulatedKernel:
    """Protocol model only. No real UID/limit/capability/seccomp claim."""
    def __init__(self, *, privileged=False):
        self.pid, self.ppid, self.last = 1234, 1200, 40
        self.dumpable = 2  # Simulated host suid_dumpable after UID drop.
        self.data = guard._parse_status(status_bytes())
        if privileged:
            self.data["Uid"] = self.data["Gid"] = (0, 0, 0, 0)
            self.data["Groups"] = (0,)
            self.data["CapEff"] = self.data["CapPrm"] = (1 << 41) - 1
            self.data["CapBnd"] = (1 << 41) - 1
        self.tasks, self.children = (self.pid,), False
        self.events, self.policy, self.hook = [], None, None
        self.limits = {name: (-1, -1) for name in ("NPROC", "FSIZE", "CORE", "AS", "CPU")}

    def status(self):
        return deepcopy(self.data)

    def task_ids(self):
        return self.tasks

    def no_children(self):
        if self.children:
            raise guard.GuardError("simulated preexisting child")

    def ids(self):
        return self.data["Uid"][:3], self.data["Gid"][:3], self.data["Groups"]

    def capabilities(self):
        return {key: self.data[key] for key in ("CapEff", "CapPrm", "CapInh")}

    def cap_last_cap(self):
        return self.last

    def prctl(self, option, arg=0, third=0):
        self.events.append(("prctl", option, arg, third))
        if option == guard._PR_GET_DUMPABLE:
            return self.dumpable
        if option == guard._PR_SET_DUMPABLE:
            assert arg == 0
            self.dumpable = 0
            return 0
        if option == guard._PR_CAPBSET_READ:
            if arg > self.last:
                raise OSError(errno.EINVAL, "simulated unsupported capability")
            return (self.data["CapBnd"] >> arg) & 1
        if option == guard._PR_CAPBSET_DROP:
            self.data["CapBnd"] &= ~(1 << arg)
            return 0
        if option == guard._PR_CAP_AMBIENT:
            assert arg == 1
            return (self.data["CapAmb"] >> third) & 1
        if option == guard._PR_GET_NO_NEW_PRIVS:
            return self.data["NoNewPrivs"]
        if option == guard._PR_SET_NO_NEW_PRIVS:
            assert arg == 1
            self.data["NoNewPrivs"] = 1
            return 0
        if option == guard._PR_GET_SECCOMP:
            return self.data["Seccomp"]
        raise AssertionError("unexpected simulated prctl")

    def get_limit(self, name):
        return self.limits[name]

    def set_limit(self, name, value):
        self.events.append(("limit", name, value))
        self.limits[name] = (value, value)

    def set_filter(self, policy):
        self.events.append(("filter",))
        self.policy = policy
        self.data["Seccomp"] = 2
        self.data["Seccomp_filters"] += 1
        if self.hook is not None:
            self.hook(self)


def evaluate_bpf(nr, *, arch=guard._AUDIT_ARCH_X86_64, args=(0, 0, 0, 0, 0, 0)):
    """Independent small interpreter of emitted classic-BPF, not a kernel."""
    data = struct.pack("<IIQ6Q", nr & 0xFFFFFFFF, arch, 0, *args)
    program = guard._policy()
    accumulator, pc = 0, 0
    for _ in range(len(program)):
        code, yes, no, immediate = program[pc]
        if code == 0x20:
            accumulator = struct.unpack_from("<I", data, immediate)[0]
        elif code in (0x15, 0x35):
            condition = accumulator == immediate if code == 0x15 else accumulator >= immediate
            pc += yes if condition else no
        elif code == 0x06:
            return immediate
        else:
            raise AssertionError("unexpected emitted instruction")
        pc += 1
        assert 0 <= pc < len(program)
    raise AssertionError("filter did not terminate within its bound")


def test_decoder_reads_all_four_ids_and_five_capability_sets_without_native_claim():
    result = guard._parse_status(status_bytes(Groups="0 12"))
    assert result["Uid"] == (1000, 1000, 1000, 1000)
    assert result["Groups"] == (0, 12)
    assert [result[key] for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")] == [0] * 5


@pytest.mark.parametrize("data", [b"", b"x" * (guard.MAX_STATUS_BYTES + 1),
    status_bytes()[:-1], status_bytes() + b"Threads:\t1\n", status_bytes() + b"garbage\n",
    status_bytes().replace(b"CapAmb:", b"Other:"), status_bytes(Threads="true"),
    status_bytes(Threads="1.0"), status_bytes(Pid="001234"),
    status_bytes(Uid="1000 1000 1000"), status_bytes(CapEff="0"),
    status_bytes(CapEff="000000000000000A"), status_bytes(CapBnd="0000000000000000\x00"),
    status_bytes(NoNewPrivs="2"), status_bytes(Seccomp="1"),
    status_bytes(Seccomp="2", Seccomp_filters="0"),
    status_bytes(Seccomp="0", Seccomp_filters="1"),
    status_bytes(Seccomp="2", Seccomp_filters="257"),
    status_bytes(Groups=" ".join(["1"] * 65)),
], ids=lambda value: "bytes-" + hashlib.sha256(value).hexdigest()[:12])
def test_bounded_status_decoder_rejects_malformed_or_unmeasurable(data):
    with pytest.raises(guard.GuardError):
        guard._parse_status(data)


@pytest.mark.parametrize("data", [b"", b"40", b"040\n", b"64\n", b"-1\n", b"true\n", b"4.0\n", b"40\x00\n", b"40\n0"])
def test_capability_upper_bound_is_closed_and_exact(data):
    with pytest.raises(guard.GuardError):
        guard._parse_cap_last_cap(data)


def test_capability_upper_bound_accepts_only_bounded_supported_encoding():
    assert guard._parse_cap_last_cap(b"0\n") == 0
    assert guard._parse_cap_last_cap(b"40\n") == 40
    assert guard._parse_cap_last_cap(b"63\n") == 63


def test_allowlist_exact_native_numbers_and_unknown_calls_have_no_range_holes():
    allowed = {number for _name, number in guard._ALLOWED_SYSCALLS}
    for number in range(4096):
        actual = evaluate_bpf(number)
        if 512 <= number < 548:
            expected = guard._SECCOMP_RET_KILL_PROCESS
        elif number in allowed or number == 302:  # zero args are read-only self prlimit.
            expected = guard._SECCOMP_RET_ALLOW
        else:
            expected = guard._SECCOMP_RET_ERRNO
        assert actual == expected, number
    assert evaluate_bpf(0x3FFFFFFF) == guard._SECCOMP_RET_ERRNO


@pytest.mark.parametrize("number", [56, 57, 58, 59, 322, 435, 101, 126, 160, 272, 308, 317, 321, 323, 206, 209, 425, 426, 427, 9999])
def test_creation_privilege_async_and_unknown_syscalls_are_denied(number):
    assert evaluate_bpf(number) == guard._SECCOMP_RET_ERRNO


@pytest.mark.parametrize("arch,number", [
    (0x40000003, 2), (0xC00000B7, 56), (0, 0),
    (guard._AUDIT_ARCH_X86_64, 0x40000000),
    (guard._AUDIT_ARCH_X86_64, 57 | 0x40000000),
    (guard._AUDIT_ARCH_X86_64, -1), (guard._AUDIT_ARCH_X86_64, 512),
    (guard._AUDIT_ARCH_X86_64, 547),
])
def test_architecture_x32_and_historic_abi_aliases_kill_before_any_allowlist(arch, number):
    assert evaluate_bpf(number, arch=arch) == guard._SECCOMP_RET_KILL_PROCESS


@pytest.mark.parametrize("args,allowed", [
    ((0, 0, 0, 123, 0, 0), True), ((1234, 0, 0, 123, 0, 0), False),
    ((1 << 32, 0, 0, 0, 0, 0), False), ((0, 0, 123, 0, 0, 0), False),
    ((0, 0, 1 << 32, 0, 0, 0), False),
])
def test_prlimit_only_reads_self_with_null_new_limit_checking_all_pointer_bits(args, allowed):
    assert evaluate_bpf(302, args=args) == (guard._SECCOMP_RET_ALLOW if allowed else guard._SECCOMP_RET_ERRNO)


@pytest.mark.parametrize("args,allowed", [
    ((3, 0, 0, 0, 0, 0), True), ((4, 0, 0, 0, 0, 0), False),
    ((4, 1, 0, 0, 0, 0), False),
    ((21, 0, 0, 0, 0, 0), True), ((23, 40, 0, 0, 0, 0), True),
    ((39, 0, 0, 0, 0, 0), True), ((47, 1, 40, 0, 0, 0), True),
    ((38, 1, 0, 0, 0, 0), False), ((24, 0, 0, 0, 0, 0), False),
    ((22, 2, 0, 0, 0, 0), False), ((47, 2, 0, 0, 0, 0), False),
    ((39 | (1 << 32), 0, 0, 0, 0, 0), False),
    ((47, 1 | (1 << 32), 0, 0, 0, 0), False),
])
def test_prctl_after_install_is_read_only_and_checks_full_option_words(args, allowed):
    assert evaluate_bpf(157, args=args) == (guard._SECCOMP_RET_ALLOW if allowed else guard._SECCOMP_RET_ERRNO)


def test_policy_native_byte_layout_and_digest_are_deterministic_and_bounded():
    program = guard._policy()
    assert len(program) <= 512
    assert ctypes.sizeof(guard._SockFilter) == 8
    native = (guard._SockFilter * len(program))(*(guard._SockFilter(*entry) for entry in program))
    assert bytes(native) == b"".join(struct.pack("<HBBI", *entry) for entry in program)
    assert len(guard._policy_digest(program)) == 64
    assert guard._policy_digest(program) == guard._policy_digest(guard._policy())


@pytest.mark.parametrize("outcome", [-1, 12, True, False, None])
def test_mocked_seccomp_syscall_requires_exact_zero_not_positive_tsync_tid(outcome):
    native = object.__new__(guard._Native)
    native.libc = SimpleNamespace(syscall=lambda *_args: outcome)
    with pytest.raises(guard.GuardError, match="TSYNC"):
        native.set_filter(guard._policy())


def test_protocol_install_sets_and_reads_all_limits_before_filter():
    native = SimulatedKernel()
    result = guard._install(native, 123456, 3)
    assert result.cpu_seconds == 3 and result.file_size_bytes == 123456
    assert result.address_space_bytes == 2 * 1024**3
    assert result.nproc == result.core_bytes == 0
    assert result.dumpable == native.dumpable == 0
    assert result.no_new_privs == result.threads == 1
    assert result.seccomp_mode == 2 and result.seccomp_filters == 1
    position = native.events.index(("filter",))
    assert [event for event in native.events[:position] if event[0] == "limit"] == [
        ("limit", "NPROC", 0), ("limit", "FSIZE", 123456), ("limit", "CORE", 0),
        ("limit", "AS", 2 * 1024**3), ("limit", "CPU", 3),
    ]
    assert ("prctl", guard._PR_SET_NO_NEW_PRIVS, 1, 0) in native.events[:position]
    assert native.events.count(("prctl", guard._PR_SET_DUMPABLE, 0, 0)) == 1
    drop_index = native.events.index(("prctl", guard._PR_SET_DUMPABLE, 0, 0))
    assert ("prctl", guard._PR_GET_DUMPABLE, 0, 0) in native.events[drop_index + 1:position]
    assert ("prctl", guard._PR_GET_DUMPABLE, 0, 0) in native.events[position + 1:]


@pytest.mark.parametrize("initial", [0, 1, 2])
def test_each_measured_initial_dumpability_is_irreversibly_set_to_zero(initial):
    native = SimulatedKernel()
    native.dumpable = initial
    assert guard._install(native, 4096, 300).dumpable == native.dumpable == 0


@pytest.mark.parametrize("initial", [True, False, None, -1, 3, 0.0, "0"])
def test_unmeasurable_initial_dumpability_refuses_before_any_change(initial):
    native = SimulatedKernel()
    native.dumpable = initial
    with pytest.raises(guard.GuardError, match="dumpable"):
        guard._install(native, 4096, 300)
    assert native.policy is None
    assert not any(event[0] == "limit" or event[:2] == ("prctl", guard._PR_SET_DUMPABLE) for event in native.events)


def test_false_dumpable_set_success_is_rejected_by_pre_filter_readback():
    native = SimulatedKernel()
    original = native.prctl
    native.prctl = lambda option, arg=0, third=0: 0 if option == guard._PR_SET_DUMPABLE else original(option, arg, third)
    with pytest.raises(guard.GuardError, match="dumpable zero before"):
        guard._install(native, 4096, 300)
    assert native.policy is None and native.dumpable == 2


@pytest.mark.parametrize("cpu", [True, False, 0, -1, 301, 1.0, "1", None])
def test_invalid_cpu_input_never_reaches_native_changes(cpu):
    native = SimulatedKernel()
    with pytest.raises(guard.GuardError):
        guard._install(native, 1024, cpu)
    assert native.events == []


@pytest.mark.parametrize("size", [True, False, -1, 8 * 1024**3 + 1, 1.0, "1", None])
def test_invalid_file_size_input_never_reaches_native_changes(size):
    native = SimulatedKernel()
    with pytest.raises(guard.GuardError):
        guard._install(native, size, 300)
    assert native.events == []


@pytest.mark.parametrize("field,value", [
    ("Uid", (0, 0, 0, 0)), ("Uid", (1000, 1000, 0, 1000)),
    ("Uid", (1000, 1000, 1000, 0)), ("Gid", (0, 0, 0, 0)),
    ("Groups", (0,)), ("Threads", 2), ("TracerPid", 12),
    ("Pid", 999), ("Tgid", 999), ("PPid", 999),
    ("CapEff", 1), ("CapPrm", 1), ("CapInh", 1), ("CapBnd", 1), ("CapAmb", 1),
])
def test_unsafe_identity_privilege_or_thread_state_refuses_before_mutation(field, value):
    native = SimulatedKernel()
    native.data[field] = value
    with pytest.raises(guard.GuardError):
        guard._install(native, 4096, 300)
    assert not any(event[0] in ("filter", "limit") for event in native.events)


@pytest.mark.parametrize("fault", ["threads", "child", "caps_mismatch", "extra_cap", "last_cap", "limit_low", "limit_bool", "limit_unread"])
def test_missing_or_contradictory_native_observations_do_not_install(fault):
    native = SimulatedKernel()
    if fault == "threads":
        native.tasks = (native.pid, native.pid + 1)
    elif fault == "child":
        native.children = True
    elif fault == "caps_mismatch":
        native.capabilities = lambda: {"CapEff": 1, "CapPrm": 0, "CapInh": 0}
    elif fault == "extra_cap":
        original = native.prctl
        native.prctl = lambda option, arg=0, third=0: 0 if option == guard._PR_CAPBSET_READ and arg == 41 else original(option, arg, third)
    elif fault == "last_cap":
        native.last = 64
    elif fault == "limit_low":
        native.limits["CPU"] = (1, 1)
    elif fault == "limit_bool":
        native.limits["NPROC"] = (False, False)
    else:
        native.get_limit = lambda _name: None
    with pytest.raises(guard.GuardError):
        guard._install(native, 4096, 300)
    assert native.policy is None


@pytest.mark.parametrize("fault", ["threads", "uid", "caps", "nnp", "filters", "mode", "limit", "children", "dumpable"])
def test_readback_failure_after_irreversible_filter_never_returns_success(fault):
    native = SimulatedKernel()
    def damage(value):
        if fault == "threads":
            value.tasks = (value.pid, value.pid + 1)
        elif fault == "uid":
            value.data["Uid"] = (1001,) * 4
        elif fault == "caps":
            value.data["CapBnd"] = 1
        elif fault == "nnp":
            value.data["NoNewPrivs"] = 0
        elif fault == "filters":
            value.data["Seccomp_filters"] += 1
        elif fault == "mode":
            value.data["Seccomp"] = 0
        elif fault == "limit":
            value.limits["CPU"] = (300, 300)
        elif fault == "dumpable":
            value.dumpable = 1
        else:
            value.children = True
    native.hook = damage
    with pytest.raises(guard.GuardError):
        guard._install(native, 4096, 2)
    assert native.policy is not None
    assert len([event for event in native.events if event[0] == "filter"]) == 1


def test_mocked_zero_bounding_transition_checks_every_capability_and_does_not_drop_uids():
    native = SimulatedKernel(privileged=True)
    result = guard._drop_bounding(native)
    assert result.bounding_mask == 0 and result.cap_last_cap == 40
    drops = [event[2] for event in native.events if event[:2] == ("prctl", guard._PR_CAPBSET_DROP)]
    assert drops == list(range(41))
    assert native.data["Uid"] == (0, 0, 0, 0)
    assert native.data["CapEff"] != 0  # Helper does not falsely certify all-zero caps.


def test_bounding_helper_requires_real_privilege_and_drop_readback():
    with pytest.raises(guard.GuardError):
        guard._drop_bounding(SimulatedKernel())
    native = SimulatedKernel(privileged=True)
    original = native.prctl
    def no_drop(option, arg=0, third=0):
        if option == guard._PR_CAPBSET_DROP:
            return 0
        return original(option, arg, third)
    native.prctl = no_drop
    with pytest.raises(guard.GuardError, match="zero bounding"):
        guard._drop_bounding(native)


def test_elf_and_platform_checks_are_closed_to_linux_lp64_x86_64():
    elf = bytearray(64)
    elf[:7], elf[18:20] = b"\x7fELF\x02\x01\x01", b"\x3e\x00"
    good = ("linux", "x86_64", 8, 8, "little", bytes(elf))
    guard._require_abi(*good)
    for field, value in ((0, "win32"), (1, "aarch64"), (2, 4), (3, 4), (4, "big"), (5, bytes(elf[:63]))):
        changed = list(good)
        changed[field] = value
        with pytest.raises(guard.GuardUnavailable):
            guard._require_abi(*changed)
    elf[4] = 1  # x32 ELF class is not LP64.
    with pytest.raises(guard.GuardUnavailable):
        guard._require_abi(*good[:5], bytes(elf))


def test_public_apis_do_not_accept_caller_assurance_booleans():
    assert list(inspect.signature(guard.drop_worker_capability_bounding_set).parameters) == []
    assert list(inspect.signature(guard.install_single_process_guard).parameters) == ["file_size_bytes", "cpu_seconds"]


@pytest.mark.skipif(sys.platform == "linux", reason="Windows/non-Linux public entry fail-closed check")
def test_nonlinux_never_falls_back_to_simulated_enforcement():
    with pytest.raises(guard.GuardUnavailable):
        guard.install_single_process_guard(file_size_bytes=4096)
    with pytest.raises(guard.GuardUnavailable):
        guard.drop_worker_capability_bounding_set()


@pytest.mark.skipif(sys.platform != "linux", reason="native Linux direct-child requirement")
def test_native_public_api_refuses_importing_parent_without_changes():
    with pytest.raises(guard.GuardError, match="direct fork child"):
        guard.drop_worker_capability_bounding_set()


_NATIVE_SCRIPT = r'''
import ctypes, errno, importlib.util, json, os, pwd, signal, sys
spec = importlib.util.spec_from_file_location("context_preparation_process_guard", sys.argv[3])
g = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = g
spec.loader.exec_module(g)
mode = sys.argv[1]
identity = pwd.getpwnam("nobody")
if identity.pw_uid == 0 or identity.pw_gid == 0:
    raise RuntimeError("native test requires an existing nonprivileged nobody identity")
parent_before = open("/proc/self/status", "rb").read(65537)
scratch = os.open(sys.argv[2], os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600) if mode == "denials" else None
pid = os.fork()
if pid == 0:
    try:
        g.drop_worker_capability_bounding_set()
        os.setgroups([])
        os.setresgid(identity.pw_gid, identity.pw_gid, identity.pw_gid)
        os.setresuid(identity.pw_uid, identity.pw_uid, identity.pw_uid)
        readback = g.install_single_process_guard(file_size_bytes=4096, cpu_seconds=1 if mode == "cpu" else 10)
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong]*4
        libc.prctl.restype = ctypes.c_int
        libc.syscall.restype = ctypes.c_long
        assert readback.dumpable == libc.prctl(3, 0, 0, 0, 0) == 0
        if mode == "cpu":
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
            while True:
                pass
        if mode in ("python", "numeric"):
            original_pid = os.getpid()
            if mode == "numeric":
                # Explicit test dependencies enter only this now-unprivileged,
                # guarded interpreter, never the isolated -I -S -B parent.
                sys.path.extend(json.loads(sys.argv[4]))
                import numpy as n
                from scipy.linalg import solve
                assert n.allclose(solve(n.array([[2.,0.],[0.,4.]]), n.array([4.,8.])), [2.,2.])
            import sqlite3
            c = sqlite3.connect(":memory:")
            c.execute("create table t(x)")
            c.execute("insert into t values(7)")
            assert c.execute("select x from t").fetchone() == (7,)
            status = g._parse_status(open("/proc/self/status", "rb").read(65537))
            assert status["Threads"] == status["NoNewPrivs"] == 1
            assert os.getpid() == original_pid == readback.pid
            assert libc.prctl(3, 0, 0, 0, 0) == 0
            print("PYTHON_SQLITE_SINGLE_THREAD_OK", flush=True)
            os._exit(0)
        denied = []
        for number in (56, 57, 58, 59, 322, 435, 425, 426, 427, 9999):
            ctypes.set_errno(0)
            outcome = libc.syscall(ctypes.c_long(number), ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0))
            if outcome == 0 and number in (56, 57, 58):
                os._exit(90)
            assert outcome == -1 and ctypes.get_errno() == errno.EPERM, (number, outcome, ctypes.get_errno())
            denied.append(number)
        ctypes.set_errno(0)
        assert libc.prctl(4, 1, 0, 0, 0) == -1 and ctypes.get_errno() == errno.EPERM
        assert libc.prctl(3, 0, 0, 0, 0) == 0
        import threading
        try:
            threading.Thread(target=lambda: None).start()
        except RuntimeError:
            pass
        else:
            raise AssertionError("a native thread escaped")
        import mmap, resource
        assert resource.getrlimit(resource.RLIMIT_NPROC) == (0, 0)
        assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
        assert resource.getrlimit(resource.RLIMIT_AS) == (2*1024**3, 2*1024**3)
        assert resource.getrlimit(resource.RLIMIT_FSIZE) == (4096, 4096)
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        assert os.write(scratch, b"x"*4096) == 4096
        try:
            os.write(scratch, b"x")
        except OSError as exc:
            assert exc.errno == errno.EFBIG
        else:
            raise AssertionError("logical FSIZE extension escaped")
        assert os.fstat(scratch).st_size == 4096
        try:
            mmap.mmap(-1, 3*1024**3)
        except (OSError, MemoryError):
            pass
        else:
            raise AssertionError("native AS limit did not reject allocation")
        print(json.dumps({"denied":denied,"pid":os.getpid(),"filter":readback.policy_sha256}), flush=True)
        os._exit(0)
    except BaseException as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr, flush=True)
        os._exit(91)
_, status, usage = os.wait4(pid, 0)
if scratch is not None:
    os.close(scratch)
parent_after = open("/proc/self/status", "rb").read(65537)
def caps(data):
    return [line for line in data.splitlines() if line.startswith(b"Cap")]
assert caps(parent_before) == caps(parent_after), "parent capability sets changed"
if mode == "cpu":
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL, status
    print("NATIVE_CPU_KILL_OK", flush=True)
else:
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, status
'''


@pytest.mark.skipif(sys.platform != "linux", reason="requires actual Linux x86_64 seccomp, capabilities, RLIMIT and isolated root fork children")
@pytest.mark.parametrize("mode", ["denials", "python", "numeric", "cpu"])
def test_native_linux_child_enforcement_and_parent_unchanged(mode, tmp_path):
    if os.geteuid() != 0:
        pytest.skip("native bounding-drop probe requires root only for its disposable child")
    if mode == "numeric" and any(importlib.util.find_spec(module) is None for module in ("numpy", "scipy")):
        pytest.skip("native numerical-profile dependencies unavailable; no numerical acceptance")
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", _NATIVE_SCRIPT, mode,
                             str(tmp_path / "guard-fsize.bin"), str(Path(guard.__file__).resolve()), json.dumps(site.getsitepackages())],
                            cwd=Path(guard.__file__).parent, capture_output=True, timeout=15,
                            env={**os.environ, **{name: "1" for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "GOTO_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}})
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert len(result.stdout) < 4096 and len(result.stderr) < 4096
    if mode == "denials":
        assert json.loads(result.stdout)["denied"] == [56, 57, 58, 59, 322, 435, 425, 426, 427, 9999]
    elif mode in ("python", "numeric"):
        assert b"PYTHON_SQLITE_SINGLE_THREAD_OK" in result.stdout
    else:
        assert b"NATIVE_CPU_KILL_OK" in result.stdout
