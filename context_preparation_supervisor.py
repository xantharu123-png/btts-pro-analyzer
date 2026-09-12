"""Native measurement for one actually constrained preparation child.

This is not a B publisher, a protected job registry, a source seal or a disk
quota. The caller must admit the complete workspace and durably reserve costs
BEFORE calling, and charge its own whole-job CPU outside this measured window.
Only a fresh, single-threaded, secret-free root Linux coordinator may launch.
The caller must start that interpreter with an empty inherited environment,
adding only PATH=/usr/bin:/bin and LANG=C.UTF-8, before any Python execution.
Fork copies Python and native memory: clearing os.environ in the child does
NOT erase previously loaded secrets. Never call this from a key-holding B
publisher, app process or reused interpreter. Current environment/module
checks catch common misuse, but cannot prove the parent's entire past.
Its freshly forked child drops all identities/capabilities and installs the
separate native single-process guard before any worker code, without a
subsequent exec. A stopped child is checked through actual
kernel state, not a JSON assertion emitted by the application. pidfd + wait4
then bind signalling, terminal usage and reaping to that same child.

The measured parent window is included separately. RLIMIT_AS is an allocation
limit; RSS is observed and the terminal kernel high-water mark is mandatory.
Free space is sampled, not promised against unobserved third-party allocation.
The caller must keep an unknown/failed run charged and unpublished. An unreaped
child is an explicit STOP carrying an owned pidfd, never a successful result.
No existing updater, model, live data or production entrypoint calls this file.
"""
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import runpy
import selectors
import signal
import stat
import sys
import threading
import time


AS_BYTES = 2 * 1024**3
RSS_BYTES = 1024**3
OUTPUT_BYTES = 1024**2
FREE_BYTES = 4 * 1024**3
MAX_CPU_SECONDS = 300
MAX_WALL_SECONDS = 3600
MAX_FILE_BYTES = 4 * 1024**3
POLL_SECONDS = 0.05
MAX_SAMPLE_GAP_NS = 10**9
PROC_BYTES = 32768
_CAP_FIELDS = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
_PARENT_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}


class NativeSupervisorError(RuntimeError):
    pass


class NativeSupervisorUnavailable(NativeSupervisorError):
    pass


class UnreapedChild(NativeSupervisorError):
    """Caller inherits pidfd custody (if acquired); retain charge and reap."""

    def __init__(self, pid, pidfd):
        super().__init__("native child has not been reaped; preparation STOP")
        self.pid = pid
        self.pidfd = pidfd


@dataclass(frozen=True)
class KernelReadback:
    pid: int
    uid: int
    gid: int
    cpu_seconds: int
    file_size_bytes: int
    seccomp_filters: int
    initial_rss_bytes: int


@dataclass(frozen=True)
class NativeRunResult:
    exit_code: int
    stop_reason: str | None
    kernel_readback: KernelReadback | None
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


def _int(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise NativeSupervisorError("invalid exact integer " + name)
    return value


def _read_small(path):
    with open(path, "rb", buffering=0) as stream:
        raw = stream.read(PROC_BYTES + 1)
    if not raw or len(raw) > PROC_BYTES or not raw.endswith(b"\n"):
        raise NativeSupervisorError("unbounded or incomplete kernel observation")
    return raw


def _status(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= PROC_BYTES or not raw.endswith(b"\n"):
        raise NativeSupervisorError("invalid kernel status bytes")
    try:
        parsed = {}
        for line in raw.decode("ascii").splitlines():
            name, value = line.split(":", 1)
            if not name or name in parsed:
                raise ValueError("duplicate status field")
            parsed[name] = value.strip()
        return parsed
    except (ValueError, UnicodeError) as exc:
        raise NativeSupervisorError("invalid kernel status record") from exc


def _unsigned(raw, *, base=10):
    alphabet = "0123456789" if base == 10 else "0123456789abcdefABCDEF"
    if type(raw) is not str or not 1 <= len(raw) <= 20 or any(c not in alphabet for c in raw):
        raise NativeSupervisorError("invalid unsigned kernel counter")
    value = int(raw, base)
    return _int(value, "kernel counter", 0, 2**64 - 1)


def _rss(status):
    try:
        parts = status["VmHWM"].split()
    except KeyError as exc:
        raise NativeSupervisorError("missing kernel RSS high-water mark") from exc
    if len(parts) != 2 or parts[1] != "kB":
        raise NativeSupervisorError("invalid kernel RSS unit")
    return _int(_unsigned(parts[0]) * 1024, "RSS", 1, 2**63 - 1)


def _ids(status, name, expected):
    parts = status.get(name, "").split()
    if len(parts) != 4 or any(_unsigned(part) != expected for part in parts):
        raise NativeSupervisorError("child kernel identities differ")


def _one_task(pid):
    with os.scandir(f"/proc/{pid}/task") as items:
        first = next(items, None)
        second = next(items, None)
    if first is None or first.name != str(pid) or second is not None:
        raise NativeSupervisorError("exactly one kernel task is required")


def _kernel_readback(pid, uid, gid, cpu_seconds, file_size_bytes):
    import resource
    state = _status(_read_small(f"/proc/{pid}/status"))
    for name, expected in (("Pid", pid), ("Tgid", pid), ("PPid", os.getpid()), ("TracerPid", 0)):
        if _unsigned(state.get(name, "")) != expected:
            raise NativeSupervisorError("child kernel process identity differs")
    if state.get("State", "").split()[:1] != ["T"]:
        raise NativeSupervisorError("child was not stopped before worker entry")
    _ids(state, "Uid", uid)
    _ids(state, "Gid", gid)
    if state.get("Groups", "").split():
        raise NativeSupervisorError("child retains supplementary groups")
    for key in _CAP_FIELDS:
        if key not in state or _unsigned(state[key], base=16) != 0:
            raise NativeSupervisorError("child retains Linux capabilities")
    if state.get("NoNewPrivs") != "1" or state.get("Seccomp") != "2":
        raise NativeSupervisorError("child lacks native irreversible process guard")
    filters = _unsigned(state.get("Seccomp_filters", ""))
    if not 1 <= filters <= 256 or state.get("Threads") != "1":
        raise NativeSupervisorError("invalid child filter/task count")
    _one_task(pid)
    for key, expected in ((resource.RLIMIT_CPU, cpu_seconds),
                          (resource.RLIMIT_AS, AS_BYTES),
                          (resource.RLIMIT_FSIZE, file_size_bytes),
                          (resource.RLIMIT_NPROC, 0), (resource.RLIMIT_CORE, 0)):
        value = resource.prlimit(pid, key)
        if type(value) is not tuple or len(value) != 2 or any(type(item) is not int for item in value) or value != (expected, expected):
            raise NativeSupervisorError("native child resource readback differs")
    return KernelReadback(pid, uid, gid, cpu_seconds, file_size_bytes, filters, _rss(state))


def _free(fd):
    usage = os.fstatvfs(fd)
    block = _int(usage.f_frsize, "filesystem fragment", 1, 2**30)
    count = _int(usage.f_bavail, "available filesystem blocks", 0, 2**63 - 1)
    _int(usage.f_favail, "available filesystem inodes", 1, 2**63 - 1)
    return _int(block * count, "available filesystem bytes", 0, 2**63 - 1)


def _usage_cpu_ns(usage):
    total = 0
    for value in (usage.ru_utime, usage.ru_stime):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= MAX_WALL_SECONDS:
            raise NativeSupervisorError("invalid terminal kernel CPU measurement")
        # Kernel rusage arrives as float seconds; round each term upwards.
        total += math.ceil(value * 10**9)
    return total


def _validate_request(argv, uid, gid, cwd, workspace_fd, file_size_bytes, cpu_seconds, wall_seconds):
    _int(uid, "worker uid", 1, 2**31 - 1)
    _int(gid, "worker gid", 1, 2**31 - 1)
    _int(workspace_fd, "workspace descriptor", 0, 2**31 - 1)
    _int(file_size_bytes, "file size", 4096, MAX_FILE_BYTES)
    _int(cpu_seconds, "worker CPU", 1, MAX_CPU_SECONDS)
    _int(wall_seconds, "worker wall", 1, MAX_WALL_SECONDS)
    if (type(argv) is not tuple or not 1 <= len(argv) <= 32 or
            any(type(item) is not str or not item or "\0" in item for item in argv)):
        raise NativeSupervisorError("bounded exact command tuple required")
    try:
        size = sum(len(item.encode("utf-8")) + 1 for item in argv)
    except UnicodeError as exc:
        raise NativeSupervisorError("command is not UTF-8 encodable") from exc
    if size > 65536 or not Path(argv[0]).is_absolute() or Path(argv[0]).suffix != ".py":
        raise NativeSupervisorError("bounded absolute Python worker script required")
    if not isinstance(cwd, Path) or not cwd.is_absolute():
        raise NativeSupervisorError("absolute pre-admitted workspace required")


def _require_native_owner():
    if (sys.platform != "linux" or not all(hasattr(os, item) for item in
            ("fork", "wait4", "pidfd_open", "getresuid", "setresuid", "fstatvfs")) or
            not hasattr(signal, "pidfd_send_signal") or not hasattr(time, "CLOCK_BOOTTIME")):
        raise NativeSupervisorUnavailable("native Linux pidfd/wait4/boot-clock owner required")
    if os.getresuid() != (0, 0, 0):
        raise NativeSupervisorUnavailable("root coordinator required for child identity drop")
    if (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode) != (1, 1, 1):
        raise NativeSupervisorUnavailable("isolated no-site no-bytecode coordinator required")
    _require_clean_environment()
    allowed = sys.stdlib_module_names | {"__main__", "context_preparation_supervisor",
              "context_preparation_process_guard", "context_preparation_budget"}
    if any(name.split(".", 1)[0] not in allowed for name in sys.modules):
        raise NativeSupervisorUnavailable("coordinator already imported non-stdlib worker dependencies")
    if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
        raise NativeSupervisorUnavailable("fresh single-threaded coordinator required")
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise NativeSupervisorUnavailable("default SIGCHLD disposition is required")
    _one_task(os.getpid())


def _require_clean_environment():
    # A current readback, not proof that deleted environment/heap secrets never
    # existed. The fresh env-i launcher remains an explicit outer prerequisite.
    if dict(os.environ) != _PARENT_ENVIRONMENT:
        raise NativeSupervisorUnavailable("fresh explicitly empty-environment coordinator required")


def _child_run_python(argv, uid, gid, cwd, stdout_fd, stderr_fd, null_fd, file_size_bytes, cpu_seconds, guard):
    # Only trusted stdlib + guard code runs before identity drop and SIGSTOP.
    # No exec may reset the installed nondumpable state on a piped-core host.
    try:
        os.dup2(null_fd, 0, inheritable=True)
        os.dup2(stdout_fd, 1, inheritable=True)
        os.dup2(stderr_fd, 2, inheritable=True)
        with os.scandir("/proc/self/fd") as items:
            descriptors = [int(entry.name) for entry in items]
        os.closerange(3, max(descriptors, default=2) + 1)
        os.chdir(cwd)
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": str(cwd),
                       "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                       "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
        os.environ.clear()
        os.environ.update(environment)
        sys.stdout.reconfigure(line_buffering=True, write_through=True)
        sys.stderr.reconfigure(line_buffering=True, write_through=True)
        guard.drop_worker_capability_bounding_set()
        os.setgroups([])
        os.setresgid(gid, gid, gid)
        os.setresuid(uid, uid, uid)
        guard.install_single_process_guard(file_size_bytes=file_size_bytes, cpu_seconds=cpu_seconds)
        os.kill(os.getpid(), signal.SIGSTOP)
        sys.argv = list(argv)
        exit_code = 0
        try:
            runpy.run_path(argv[0], run_name="__main__")
        except SystemExit as exc:
            exit_code = 0 if exc.code is None else exc.code
            if type(exit_code) is not int or not 0 <= exit_code <= 255:
                exit_code = 125
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    except BaseException:
        try:
            os.write(2, b"betboy-native-launch-failed\n")
        finally:
            os._exit(125)


def _signal_owned(pid, pidfd, value):
    try:
        if pidfd is None:
            # Only before pidfd_open, while this direct child is unreaped.
            os.kill(pid, value)
        else:
            signal.pidfd_send_signal(pidfd, value)
    except ProcessLookupError:
        pass


def _cleanup(pid, pidfd):
    try:
        _signal_owned(pid, pidfd, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while True:
            found, status, usage = os.wait4(pid, os.WNOHANG)
            if found:
                if found != pid or not (os.WIFEXITED(status) or os.WIFSIGNALED(status)):
                    raise NativeSupervisorError("cleanup did not return the owned terminal child")
                return status, usage
            if time.monotonic() >= deadline:
                # Transfer existing custody; cleanup must not need a spare FD.
                raise UnreapedChild(pid, pidfd)
            time.sleep(0.02)
    except UnreapedChild:
        raise
    except BaseException as exc:
        raise UnreapedChild(pid, pidfd) from exc


def run_single_process(argv, *, uid, gid, cwd, workspace_fd, file_size_bytes,
                       cpu_seconds=MAX_CPU_SECONDS, wall_seconds=MAX_CPU_SECONDS):
    """Measure an already reserved run; return evidence, never permission.

    `cwd` must be the directory held by `workspace_fd`. The surrounding trusted
    owner must separately verify the Python script/runtime closure, all input
    seals, namespace and physical writer envelope. argv is script+arguments,
    not an executable command. Worker dependencies are loaded only after UID
    drop from the script's separately declared closure. No shell/exec is used.
    All errors after fork kill/reap this child; unknown reaping is explicit STOP.
    """
    _validate_request(argv, uid, gid, cwd, workspace_fd, file_size_bytes, cpu_seconds, wall_seconds)
    _require_native_owner()
    import context_preparation_process_guard as guard
    parent_started = time.process_time_ns()
    started = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    held = os.dup(workspace_fd)
    fds = {held}
    pid = pidfd = completed = usage = None
    selector = None
    cleanup_attempted = False
    stdout = bytearray()
    stderr = bytearray()
    checksum = hashlib.sha256()
    observed = retained = 0
    reason = readback = None
    minimum_free = peak_rss = 0
    previous_sample = started
    maximum_gap = 0
    try:
        selector = selectors.DefaultSelector()
        info = os.fstat(held)
        path_info = cwd.lstat()
        if not stat.S_ISDIR(info.st_mode) or not stat.S_ISDIR(path_info.st_mode) or (
                info.st_dev, info.st_ino) != (path_info.st_dev, path_info.st_ino):
            raise NativeSupervisorError("workspace FD and directory differ")
        minimum_free = _free(held)
        if minimum_free < FREE_BYTES:
            raise NativeSupervisorError("native free-space reserve is unavailable")
        out_read, out_write = os.pipe2(os.O_CLOEXEC)
        fds.update((out_read, out_write))
        err_read, err_write = os.pipe2(os.O_CLOEXEC)
        fds.update((err_read, err_write))
        null_fd = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        fds.add(null_fd)
        # Do not copy buffered coordinator output into the child's log pipes.
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            _child_run_python(argv, uid, gid, cwd, out_write, err_write, null_fd,
                              file_size_bytes, cpu_seconds, guard)
            os._exit(125)
        pidfd = os.pidfd_open(pid, 0)
        fds.add(pidfd)
        for fd in (out_write, err_write, null_fd):
            os.close(fd)
            fds.remove(fd)
        for fd, name in ((out_read, b"O"), (err_read, b"E")):
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, name)

        while completed is None or selector.get_map():
            now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            gap = now - previous_sample
            previous_sample = now
            maximum_gap = max(maximum_gap, gap)
            if gap < 0 or gap > MAX_SAMPLE_GAP_NS:
                reason = reason or "measurement_gap"
            if now - started >= wall_seconds * 10**9:
                reason = reason or "wall_limit"
            free = _free(held)
            minimum_free = min(minimum_free, free)
            if free < FREE_BYTES:
                reason = reason or "free_space"

            if completed is None:
                found, status, measured = os.wait4(pid, os.WNOHANG | os.WUNTRACED)
                if found:
                    if found != pid:
                        raise NativeSupervisorError("wait4 did not return the owned child")
                    if os.WIFSTOPPED(status):
                        if readback is not None or os.WSTOPSIG(status) != signal.SIGSTOP or reason is not None:
                            reason = reason or "unexpected_stop"
                        else:
                            readback = _kernel_readback(pid, uid, gid, cpu_seconds, file_size_bytes)
                            peak_rss = readback.initial_rss_bytes
                            if peak_rss >= RSS_BYTES:
                                reason = "rss_limit"
                            else:
                                _signal_owned(pid, pidfd, signal.SIGCONT)
                    else:
                        completed = os.waitstatus_to_exitcode(status)
                        usage = measured
                if completed is None and readback is not None:
                    state = _status(_read_small(f"/proc/{pid}/status"))
                    if state.get("State", "").split()[:1] != ["Z"]:
                        peak_rss = max(peak_rss, _rss(state))
                        if peak_rss >= RSS_BYTES:
                            reason = reason or "rss_limit"
                        if state.get("Threads") != "1":
                            reason = reason or "kernel_task_count"

            if reason is not None:
                if completed is None:
                    cleanup_attempted = True
                    status, usage = _cleanup(pid, pidfd)
                    completed = os.waitstatus_to_exitcode(status)
                # Reaped failed output need not be completely drained. Already
                # retained bytes are a bounded prefix, not an invented full log.
                for key in tuple(selector.get_map().values()):
                    selector.unregister(key.fd)
                continue

            for key, _ in selector.select(POLL_SECONDS):
                chunk = os.read(key.fd, min(65536, OUTPUT_BYTES - observed + 1))
                if not chunk:
                    selector.unregister(key.fd)
                    continue
                observed += len(chunk)
                # Channel framing and read order are part of this evidence hash,
                # not a deterministic application-output or source identity.
                checksum.update(key.data + len(chunk).to_bytes(4, "big") + chunk)
                kept = chunk[:max(0, OUTPUT_BYTES - retained)]
                (stdout if key.data == b"O" else stderr).extend(kept)
                retained += len(kept)
                if observed > OUTPUT_BYTES:
                    reason = reason or "output_limit"
                    if completed is None:
                        _signal_owned(pid, pidfd, signal.SIGKILL)
                    break

        finished = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        elapsed = finished - started
        final_gap = finished - previous_sample
        maximum_gap = max(maximum_gap, final_gap)
        if final_gap < 0 or final_gap > MAX_SAMPLE_GAP_NS:
            reason = reason or "measurement_gap"
        if elapsed >= wall_seconds * 10**9:
            reason = reason or "wall_limit"
        child_cpu = _usage_cpu_ns(usage)
        peak_rss = max(peak_rss, _int(usage.ru_maxrss, "terminal RSS KiB", 1, 2**53) * 1024)
        if peak_rss >= RSS_BYTES:
            reason = reason or "rss_limit"
        if child_cpu > cpu_seconds * 10**9:
            reason = reason or "cpu_limit"
        if readback is None:
            reason = reason or "launch_unverified"
        if completed != 0:
            reason = reason or ("signal_exit" if completed < 0 else "nonzero_exit")
        parent_cpu = time.process_time_ns() - parent_started
        return NativeRunResult(completed, reason, readback, child_cpu, parent_cpu, elapsed,
                               peak_rss, observed, checksum.hexdigest(), bytes(stdout), bytes(stderr),
                               minimum_free, maximum_gap)
    except UnreapedChild as exc:
        fds.discard(exc.pidfd)
        raise
    finally:
        try:
            if pid is not None and pid > 0 and completed is None and not cleanup_attempted:
                try:
                    cleanup_attempted = True
                    _cleanup(pid, pidfd)
                except UnreapedChild as exc:
                    fds.discard(exc.pidfd)
                    raise
        finally:
            if selector is not None:
                selector.close()
            for fd in fds:
                os.close(fd)
