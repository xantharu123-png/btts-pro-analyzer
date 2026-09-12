"""Reviewed-version native DIAGNOSTIC, not a corpus runner or B-proof owner.

Do not invoke until independent review and outer root closure/custody admission.
Required fresh invocation (the parent must NEVER have held secrets/proof keys):
  env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B \
    /sealed/native_preparation_probe.py --manifest /sealed/manifest.json \
    --manifest-sha256 LOWERCASE_SHA256 --directory /private/NEW_EMPTY_DIRECTORY

Only the exact three pinned stdlib helpers enter this parent. Dependencies enter
only its guarded nobody child. This code neither authenticates a dependency
closure nor proves that a previously populated environment/heap was empty.
No retries, deletion, truncation, repair, arbitrary job, network or live data.

The diagnostic reserves 60 CPU seconds permanently. Even success stops with the
full charge: this live parent cannot terminally measure its own reporting/exit.
Separate journal fixtures test claims, not measurement authenticity or powerloss.
An unkillable/unreaped child is an operator-custody STOP, not a 120-second success.
"""
import ctypes
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import stat
import sys
import threading
import time
import types


FORMAT = "betboy-native-preparation-probe-v1"
WORKER_FORMAT = "betboy-native-preparation-worker-v1"
HELPERS = {
    "context_preparation_process_guard": "62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4",
    "context_preparation_budget": "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478",
    "context_preparation_supervisor": "21c63e0cdf47000c2d3c66e24851635b844a1feb30091d55521ed6dd311f31de",
}
WORKER_SHA256 = "22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e"
MIB = 1024**2
NANO = 10**9
MANIFEST_BYTES = 16384
SOURCE_BYTES = 128 * 1024
REPORT_BYTES = 65536
ARTIFACT_BYTES = 64 * MIB
RESERVED_CPU_NS = 60 * NANO
PARENT_CPU_SECONDS = 15
WALL_SECONDS = 120
# mode, child CPU hard seconds, wall seconds, per-file logical byte limit.
CASES = (("positive", 15, 25, 512 * 1024), ("denials", 3, 10, 4096),
         ("fsize", 3, 10, 4096), ("address_space", 3, 10, 4096),
         ("cpu", 1, 8, 4096), ("output", 3, 8, 4096))
PLANNED_HARD_CPU_SECONDS = PARENT_CPU_SECONDS + sum(case[1] for case in CASES)
# Three bounded journals, two bounded control reports (normal + custody), the
# only two child files, plus a deliberately conservative directory allowance.
PLANNED_ARTIFACT_BYTES = 3 * MIB + 2 * REPORT_BYTES + 256 * 1024 + 4096 + 16 * MIB
CAP_FIELDS = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")


class ProbeError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ProbeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def hash_value(value):
    return digest(canonical(value))


def sha(value):
    require(type(value) is str and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value), "invalid lowercase SHA256")
    return value


def exact_int(value, low, high):
    require(type(value) is int and low <= value <= high, "invalid exact bounded integer")
    return value


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys), "unknown/incomplete manifest or record shape")


def pairs(items):
    result = {}
    for name, value in items:
        require(name not in result, "duplicate JSON key")
        result[name] = value
    return result


def forbidden_number(_value):
    raise ProbeError("non-integer JSON number")


def bounded_json(raw, maximum):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "JSON exceeds fixed bound")
    return json.loads(raw, object_pairs_hook=pairs, parse_float=forbidden_number,
                      parse_constant=forbidden_number)


def absolute(value):
    require(type(value) is str and 1 <= len(value.encode("utf-8")) <= 4096 and "\0" not in value,
            "invalid bounded path")
    path = Path(value)
    require(path.is_absolute() and path.anchor == "/" and str(path) == value and
            1 < len(path.parts) <= 32 and ".." not in path.parts,
            "absolute canonical nonsymlink path required")
    return path


def small_kernel(path, maximum=65536):
    with open(path, "rb") as stream:
        raw = stream.read(maximum + 1)
    require(0 < len(raw) <= maximum and raw.endswith(b"\n"), "invalid bounded kernel record")
    return raw


class Window:
    def __init__(self):
        # Include interpreter/import startup conservatively, rounded DOWN from
        # the kernel start tick. CLOCK_BOOTTIME includes suspended elapsed time.
        raw = small_kernel("/proc/self/stat", 8192)
        require(raw.startswith((str(os.getpid()) + " (").encode("ascii")), "process start PID differs")
        tail = raw.rsplit(b") ", 1)[1].split()
        require(len(tail) >= 20 and tail[19].isdigit(), "process start tick is not measurable")
        hz = exact_int(os.sysconf("SC_CLK_TCK"), 1, 10**9)
        self.start = int(tail[19]) * NANO // hz
        self.previous = self.start
        self.deadline = self.start + WALL_SECONDS * NANO
        self.check()

    def check(self, reserve_seconds=0):
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        require(type(now) is int and self.previous <= now < self.deadline - reserve_seconds * NANO,
                "diagnostic boot-inclusive deadline/clock failed")
        self.previous = now
        require(time.process_time_ns() < PARENT_CPU_SECONDS * NANO, "parent CPU diagnostic cap reached")
        return now


class Seals:
    """Held local root-owned path observations, NOT an authenticated registry."""
    def __init__(self, window):
        self.window, self.fds, self.bindings, self.directories = window, [], [], {}

    def directory(self, path, *, child_search=False):
        path = absolute(str(path)) if str(path) != "/" else Path("/")
        key = str(path)
        if key not in self.directories:
            if path == Path("/"):
                fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
                parent, name = None, None
            else:
                parent = self.directory(path.parent, child_search=child_search)
                name = path.name
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                             dir_fd=parent)
            self.fds.append(fd)
            info = os.fstat(fd)
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                    "path ancestor is not root-protected")
            self.bindings.append((fd, parent, name, info, False))
            self.directories[key] = fd
        fd = self.directories[key]
        if child_search:
            # nobody uses other-mode bits, and has no supplementary groups.
            require(os.fstat(fd).st_mode & 0o001, "worker path ancestor is not searchable by nobody")
            if path != Path("/"):
                self.directory(path.parent, child_search=True)
        return fd

    def file(self, path, expected, maximum, *, child_read=False):
        path = absolute(str(path))
        parent = self.directory(path.parent, child_search=child_read)
        fd = os.open(path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=parent)
        self.fds.append(fd)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
                not info.st_mode & 0o022 and 0 < info.st_size <= maximum,
                "input is not a bounded root-protected single-link file")
        if child_read:
            require(info.st_mode & 0o004, "worker file is not readable by nobody")
        self.bindings.append((fd, parent, path.name, info, True))
        data = bytearray()
        while len(data) <= maximum:
            self.window.check(10)
            piece = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not piece:
                break
            data.extend(piece)
        require(len(data) == info.st_size and digest(data) == sha(expected), "held file hash/length differs")
        self.check()
        return bytes(data)

    def check(self):
        self.window.check(10)
        for fd, parent, name, original, is_file in self.bindings:
            current = os.fstat(fd)
            # New output subdirectories legitimately change their parent's
            # directory link count. File links, unlike directory metadata,
            # remain part of the immutable input observation.
            fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid")
            if is_file:
                fields += ("st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
            require(all(getattr(current, field) == getattr(original, field) for field in fields),
                    "held input/path metadata changed")
            if parent is not None:
                entry = os.stat(name, dir_fd=parent, follow_symlinks=False)
                require((entry.st_dev, entry.st_ino) == (current.st_dev, current.st_ino),
                        "held input/path entry was replaced")

    def close(self):
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds.clear()


def platform_and_parent_limits():
    require(sys.platform == "linux" and hasattr(time, "CLOCK_BOOTTIME") and
            os.uname().machine == "x86_64" and sys.byteorder == "little" and
            ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_long) == 8,
            "native Linux x86_64 LP64 only")
    require(os.getresuid() == (0, 0, 0) and os.getresgid() == (0, 0, 0), "fresh root parent required")
    require((sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode) == (1, 1, 1),
            "fresh -I -S -B interpreter required")
    require(dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            "parent environment was not launched empty; do not sanitize and retry")
    require(threading.active_count() == 1 and threading.current_thread() is threading.main_thread(),
            "single-threaded parent required")
    require(not any(name.split(".", 1)[0] not in sys.stdlib_module_names | {"__main__"}
                    for name in sys.modules), "parent contains non-stdlib code")
    require(PLANNED_HARD_CPU_SECONDS == 43 and PLANNED_ARTIFACT_BYTES < ARTIFACT_BYTES,
            "fixed diagnostic admission plan differs")
    # CORE0 does not suppress a piped core handler. This fresh stdlib parent
    # has no subsequent exec or credential transition; narrow its own actual
    # dumpability before probe input/output I/O, without touching host policy.
    lib = ctypes.CDLL(None, use_errno=True)
    lib.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    lib.prctl.restype = ctypes.c_int
    require(lib.prctl(3, 0, 0, 0, 0) in (0, 1, 2), "parent dumpability is not observable")
    require(lib.prctl(4, 0, 0, 0, 0) == 0 and lib.prctl(3, 0, 0, 0, 0) == 0,
            "parent did not enter nondumpable state")
    import resource
    limits = ((resource.RLIMIT_CPU, PARENT_CPU_SECONDS), (resource.RLIMIT_CORE, 0),
              (resource.RLIMIT_AS, 2 * 1024**3), (resource.RLIMIT_FSIZE, MIB))
    for key, limit in limits:
        _soft, hard = resource.getrlimit(key)
        require(hard == resource.RLIM_INFINITY or hard >= limit, "inherited hard limit is too low")
        resource.setrlimit(key, (limit, limit))
        require(resource.getrlimit(key) == (limit, limit), "parent hard limit did not read back")
    return lib


def parent_credentials():
    parsed = {}
    for line in small_kernel("/proc/self/status").decode("ascii").splitlines():
        name, value = line.split(":", 1)
        require(name not in parsed, "duplicate parent status field")
        parsed[name] = value.strip()
    require(parsed["Threads"] == "1" and parsed["TracerPid"] == "0", "parent task/tracer differs")
    return {name: parsed[name] for name in CAP_FIELDS + ("Uid", "Gid", "Groups")}


def manifest_and_helpers(seals, manifest_path, manifest_sha, probe_directory):
    raw = seals.file(manifest_path, manifest_sha, MANIFEST_BYTES)
    manifest = bounded_json(raw, MANIFEST_BYTES)
    closed(manifest, {"format", "version", "helper_directory", "helper_sha256", "probe_path",
                      "probe_sha256", "worker_path", "worker_sha256", "dependency_directory",
                      "dependency_closure_sha256", "python_executable", "python_sha256", "worker_uid", "worker_gid"})
    require(manifest["format"] == FORMAT and type(manifest["format"]) is str and
            type(manifest["version"]) is int and manifest["version"] == 1, "foreign probe manifest")
    closed(manifest["helper_sha256"], HELPERS)
    require(manifest["helper_sha256"] == HELPERS and manifest["worker_sha256"] == WORKER_SHA256,
            "manifest differs from independently reviewed pinned code")
    require(type(manifest["worker_uid"]) is int and type(manifest["worker_gid"]) is int and
            manifest["worker_uid"] == manifest["worker_gid"] == 65534,
            "this diagnostic is fixed to the admitted nobody UID/GID 65534")
    for name in ("probe_sha256", "worker_sha256", "dependency_closure_sha256", "python_sha256"):
        sha(manifest[name])
    paths = {name: absolute(manifest[name]) for name in
             ("helper_directory", "probe_path", "worker_path", "dependency_directory", "python_executable")}
    require(all(not path.is_relative_to(probe_directory) for path in paths.values()) and
            not absolute(str(manifest_path)).is_relative_to(probe_directory), "inputs must be outside new output directory")
    require(not any(probe_directory.is_relative_to(paths[name]) for name in
                    ("helper_directory", "dependency_directory")), "outputs cannot mutate the sealed helper/dependency tree")
    require(paths["probe_path"] == absolute(__file__) and paths["worker_path"].suffix == ".py",
            "executed probe/worker path differs")
    require(paths["python_executable"] == Path(os.readlink("/proc/self/exe")), "running Python executable differs")
    seals.file(paths["probe_path"], manifest["probe_sha256"], SOURCE_BYTES)
    seals.file(paths["worker_path"], WORKER_SHA256, SOURCE_BYTES, child_read=True)
    seals.file(paths["python_executable"], manifest["python_sha256"], 64 * MIB)
    seals.directory(paths["dependency_directory"], child_search=True)
    require(paths["dependency_directory"] != paths["helper_directory"], "separate helper/dependency directories required")
    helper_names = set(HELPERS)
    for name, expected in HELPERS.items():
        require(name not in sys.modules, "helper was imported before hash admission")
        path = paths["helper_directory"] / (name + ".py")
        code = seals.file(path, expected, SOURCE_BYTES)
        module = types.ModuleType(name)
        module.__file__, module.__package__ = str(path), ""
        sys.modules[name] = module
        exec(compile(code, str(path), "exec", dont_inherit=True), module.__dict__)
    require(not any(name.split(".", 1)[0] not in sys.stdlib_module_names | helper_names | {"__main__"}
                    for name in sys.modules), "helper imported an undeclared parent module")
    return manifest


def new_directory(parent, name, uid=0, gid=0):
    os.mkdir(name, 0o700, dir_fd=parent)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    try:
        os.fchown(fd, uid, gid)
        info = os.fstat(fd)
        require((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, 0o700),
                "new directory identity/mode differs")
        os.fsync(parent)
        return fd
    except BaseException:
        os.close(fd)
        raise


def bounded_names(fd, maximum):
    result = []
    with os.scandir(fd) as entries:
        for entry in entries:
            result.append(entry.name)
            require(len(result) <= maximum, "unexpected artifact count")
    return result


def write_new_report(fd, name, report):
    raw = canonical(report) + b"\n"
    require(len(raw) <= REPORT_BYTES, "control report exceeds fixed bound")
    output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=fd)
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(output, raw[offset:])
            require(count > 0, "control report write made no progress")
            offset += count
        os.fsync(output)
        os.fsync(fd)
    finally:
        os.close(output)
    return {"name": name, "bytes": len(raw), "sha256": digest(raw)}


def identity_for(budget, manifest, label):
    return budget.BudgetIdentity(
        input_digest=hash_value({"synthetic_probe": FORMAT, "label": label, "no_corpus": True}),
        execution_digest=hash_value({"helpers": HELPERS, "probe": manifest["probe_sha256"], "worker": WORKER_SHA256}),
        runtime_digest=hash_value({"python": sys.version, "implementation": sys.implementation.name,
                                   "executable_sha256": manifest["python_sha256"], "stdlib_search_path": sys.path,
                                   "kernel": list(os.uname())}),
        installation_digest=hash_value(manifest),
        profile_digest=hash_value({"format": FORMAT, "cases": CASES, "cpu_reservation_ns": RESERVED_CPU_NS,
                                   "parent_cpu_hard": PARENT_CPU_SECONDS, "wall_seconds": WALL_SECONDS,
                                   "artifact_admission_bytes": PLANNED_ARTIFACT_BYTES}))


def accounting_fixtures(budget, roundtrip_fd, recovery_fd, manifest):
    result = {"scope": "real Linux fd/flock/fsync I/O with SYNTHETIC accounting claims; not measurement/authentication/powerloss"}
    identity = identity_for(budget, manifest, "accounting-roundtrip-fixture")
    with budget.PreparationBudget.create(roundtrip_fd, identity) as handle:
        before = handle.snapshot()
        ticket = handle.reserve(hash_value({"fixture": "once-only"}), NANO)
        measurement = hash_value({"SYNTHETIC_CLAIM": "one accounting nanosecond"})
        settled = handle.settle_claim(ticket, cumulative_cpu_ns=1, measurement_digest=measurement)
        require(settled.charged_cpu_ns == 1 and settled.pending is None, "fixture settlement differs")
        try:
            handle.settle_claim(ticket, cumulative_cpu_ns=1, measurement_digest=measurement)
        except budget.BudgetIntegrityError:
            pass
        else:
            raise ProbeError("double settlement was accepted")
    with budget.PreparationBudget.open_existing(roundtrip_fd, identity) as handle:
        reopened = handle.snapshot()
        require(reopened.status == "accounting-open" and reopened.pending is None and
                reopened.charged_cpu_ns == 1 and reopened.deadline_boot_ns == before.deadline_boot_ns,
                "fresh reopen reset fixture accounting/deadline")
        result["roundtrip"] = dataclasses.asdict(reopened)
    identity = identity_for(budget, manifest, "recovered-pending-fixture")
    with budget.PreparationBudget.create(recovery_fd, identity) as handle:
        ticket = handle.reserve(hash_value({"fixture": "deliberately unresolved"}), NANO)
        original = handle.snapshot()
    for attempt in range(2):
        with budget.PreparationBudget.open_existing(recovery_fd, identity) as handle:
            recovered = handle.snapshot()
            require(recovered.status == "stopped" and recovered.pending == ticket and
                    recovered.charged_cpu_ns == NANO and
                    recovered.deadline_boot_ns == original.deadline_boot_ns,
                    "recovered unknown reservation lost full charge/deadline")
            for action in (lambda: handle.reserve(hash_value({"forbidden": "restart"}), 1),
                           lambda: handle.settle_claim(ticket, cumulative_cpu_ns=0,
                                                       measurement_digest=hash_value({"forbidden": "refund"}))):
                try:
                    action()
                except budget.BudgetStopped:
                    pass
                else:
                    raise ProbeError("recovered reservation accepted start/refund")
            result["recovered_open_" + str(attempt + 1)] = dataclasses.asdict(recovered)
    return result


def result_record(result):
    record = {field.name: getattr(result, field.name) for field in dataclasses.fields(result)
              if field.name not in {"stdout_prefix", "stderr_prefix", "kernel_readback"}}
    record["kernel_readback"] = None if result.kernel_readback is None else dataclasses.asdict(result.kernel_readback)
    record["output_digest_semantics"] = "supervisor observed channel-framed read-order prefix; NOT a complete/deterministic application log"
    for label, raw in (("stdout", result.stdout_prefix), ("stderr", result.stderr_prefix)):
        record[label + "_retained"] = {"bytes": len(raw), "sha256": digest(raw), "first_128_bytes_hex": raw[:128].hex()}
    record["rss_semantics"] = "maximum sampled VmHWM AND terminal wait4 ru_maxrss, enforced by the pinned supervisor"
    return record


def check_result(result, mode, cpu, fsize_limit, uid, gid):
    readback = result.kernel_readback
    require(readback is not None and readback.uid == uid and readback.gid == gid and
            readback.cpu_seconds == cpu and readback.file_size_bytes == fsize_limit,
            "actual stopped-parent readback missing/different")
    require(type(result.child_cpu_ns) is int and result.child_cpu_ns >= 0 and
            0 < result.peak_rss_bytes < 1024**3 and result.minimum_free_bytes >= 4 * 1024**3,
            "actual native measurement is outside the diagnostic profile")
    require(result.stderr_prefix == b"", "worker emitted an error prefix")
    if mode == "output":
        require(result.stop_reason == "output_limit" and result.observed_output_bytes == MIB + 1,
                "actual output overrun was not detected")
        line = result.stdout_prefix.split(b"\n", 1)[0] + b"\n"
    elif mode == "cpu":
        require(result.exit_code == -signal.SIGKILL and result.stop_reason in {"signal_exit", "cpu_limit"} and
                100_000_000 <= result.child_cpu_ns <= 2 * NANO, "actual CPU1 SIGKILL differs")
        line = result.stdout_prefix
    else:
        require(result.exit_code == 0 and result.stop_reason is None, "positive/denial worker did not complete")
        line = result.stdout_prefix
    # The positive numerical solution legitimately contains JSON floats. This
    # output is bounded observational data, never budget/manifest integer input.
    require(0 < len(line) <= 8192 and line.endswith(b"\n") and line.count(b"\n") == 1,
            "worker control output is not a single bounded record")
    payload = json.loads(line, object_pairs_hook=pairs, parse_constant=forbidden_number)
    require(type(payload) is dict and payload.get("format") == WORKER_FORMAT and payload.get("mode") == mode and
            payload.get("phase") == ("armed" if mode in {"cpu", "output"} else "complete"),
            "worker control record differs")
    state = payload["state"]
    require(state["pid"] == readback.pid and state["uid"] == uid and state["gid"] == gid and
            state["dumpable"] == 0 and state["threads"] == 1 and
            state["cpu_limit"] == [cpu, cpu] and state["fsize_limit"] == [fsize_limit, fsize_limit],
            "worker observation differs from actual parent identity/limits")
    return payload


def inventory(directory_fds):
    result, logical, blocks = {}, 0, 0
    for name, (fd, uid) in directory_fds.items():
        expected = {"probe.sqlite3": 256 * 1024} if name == "positive" else {"fsize.bin": 4096} if name == "fsize" else {}
        names = bounded_names(fd, 1)
        if name.startswith("journal-"):
            require(len(names) == 1 and names[0].endswith(".jsonl"), "journal artifact differs")
            sha(names[0][:-6])
            expected = {names[0]: MIB}
        require(set(names) == set(expected), "missing/unexpected worker artifact name")
        files = []
        for child in names:
            info = os.stat(child, dir_fd=fd, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == uid and
                    0 <= info.st_size <= expected[child], "artifact type/ownership/logical bound differs")
            logical += info.st_size
            blocks += exact_int(info.st_blocks, 0, 2**31) * 512
            files.append({"name": child, "logical_bytes": info.st_size, "allocated_bytes": info.st_blocks * 512})
        result[name] = files
    require(logical + 2 * REPORT_BYTES < ARTIFACT_BYTES and blocks + 2 * REPORT_BYTES < ARTIFACT_BYTES,
            "observed artifact envelope exceeded")
    return {"directories": result, "logical_file_bytes_before_reports": logical,
            "allocated_file_bytes_before_reports": blocks,
            "physical_quota_claim": False, "admitted_ceiling_bytes": ARTIFACT_BYTES}


def custody_stop(exc, root_fd, report):
    """Preserve real pidfd custody while STOPPED for the external root operator.

    There is intentionally no timed exit that abandons an unreaped child. This
    exceptional path is NOT a claimed 120-second completed diagnostic. A resume
    is an operator action, never an automatic worker retry. No descriptor closes
    until this exact direct child is terminally reaped by this same parent.
    """
    report["status"] = "operator-custody-required-NOT-complete"
    report["custody"] = {"parent_pid": os.getpid(), "child_pid": exc.pid, "owned_pidfd": exc.pidfd,
                         "instruction": "parent stops holding custody; operator must resolve before any retry"}
    try:
        if root_fd is not None:
            write_new_report(root_fd, "custody-required.json", report)
    except BaseException:
        pass
    try:
        os.write(2, canonical({"format": FORMAT, "status": report["status"], "custody": report["custody"]}) + b"\n")
    finally:
        while True:
            os.kill(os.getpid(), signal.SIGSTOP)
            # Only reached after the external operator explicitly resumes us.
            try:
                try:
                    if exc.pidfd is None:
                        os.kill(exc.pid, signal.SIGKILL)
                    else:
                        signal.pidfd_send_signal(exc.pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                found, status, usage = os.wait4(exc.pid, os.WNOHANG)
            except BaseException as error:
                report["custody_reap_error"] = type(error).__name__
                continue  # STOP again; never lose custody on uncertain wait.
            if found == exc.pid and (os.WIFEXITED(status) or os.WIFSIGNALED(status)):
                report["custody_terminal_after_operator_resume"] = {
                    "exit_code": os.waitstatus_to_exitcode(status),
                    "child_cpu_ns": sum(math.ceil(value * NANO) for value in (usage.ru_utime, usage.ru_stime)),
                    "terminal_rss_bytes": usage.ru_maxrss * 1024}
                if exc.pidfd is not None:
                    os.close(exc.pidfd)
                return


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    report = {"format": FORMAT, "version": 1, "status": "failed", "cases": [],
              "no_corpus_or_B_authority": True, "native_dependency_closure_verified_here": False,
              "sqlite_scope": "minimal MEMORY-journal import/computation only; NOT Task27 DELETE/FULL writer profile"}
    seals = account = supervisor = window = parent_libc = None
    root_fd = None
    directory_fds = {}
    try:
        require(type(arguments) is list and len(arguments) == 6 and arguments[::2] ==
                ["--manifest", "--manifest-sha256", "--directory"], "exact diagnostic CLI required")
        parent_libc = platform_and_parent_limits()
        window = Window()
        seals = Seals(window)
        probe_directory = absolute(arguments[5])
        # SQLite's Unix VFS resolves even relative database names absolutely.
        # A root0700 ancestor after chdir would block that required traversal.
        # The fresh root0711 output reveals no listing/write permission; its
        # journal directories are root0700 and each child directory nobody0700.
        candidate_fd = seals.directory(probe_directory, child_search=True)
        require(stat.S_IMODE(os.fstat(candidate_fd).st_mode) == 0o711 and bounded_names(candidate_fd, 1) == [],
                "caller must supply a new empty root0711 search-only output directory; no reuse")
        root_fd = candidate_fd  # Only this successfully admitted directory may receive a report.
        manifest = manifest_and_helpers(seals, absolute(arguments[1]), sha(arguments[3]), probe_directory)
        report.update({"manifest_sha256": arguments[3], "bound_manifest": manifest,
                       "kernel": list(os.uname()), "python": sys.version,
                       "parent_start_boot_ns": window.start, "deadline_boot_ns": window.deadline,
                       "parent_dumpable_post_set_readback": 0,
                       "planned_hard_cpu_seconds_sum": PLANNED_HARD_CPU_SECONDS,
                       "reserved_cpu_ns": RESERVED_CPU_NS, "planned_artifact_bytes": PLANNED_ARTIFACT_BYTES})
        credentials = parent_credentials()
        budget = sys.modules["context_preparation_budget"]
        supervisor = sys.modules["context_preparation_supervisor"]
        for name in ("journal-diagnostic", "journal-roundtrip", "journal-recovery"):
            directory_fds[name] = (new_directory(root_fd, name), 0)
        identity = identity_for(budget, manifest, "ACTUAL-full-diagnostic-no-refund")
        account = budget.PreparationBudget.create(directory_fds["journal-diagnostic"][0], identity)
        ticket = account.reserve(hash_value({"fixed_six_case_diagnostic": CASES}), RESERVED_CPU_NS)
        report["durable_reservation_before_any_child"] = dataclasses.asdict(ticket)
        report["accounting_fixtures"] = accounting_fixtures(budget, directory_fds["journal-roundtrip"][0],
                                                           directory_fds["journal-recovery"][0], manifest)
        child_cpu = 0
        for mode, cpu, wall, fsize_limit in CASES:
            # Leave ten seconds for bounded cleanup and new report/accounting.
            now = window.check(wall + 10)
            require(child_cpu + time.process_time_ns() + cpu * NANO < RESERVED_CPU_NS,
                    "diagnostic cumulative CPU admission exhausted")
            seals.check()
            require(account.snapshot().pending == ticket, "full durable charge disappeared before child")
            fd = new_directory(root_fd, mode, manifest["worker_uid"], manifest["worker_gid"])
            directory_fds[mode] = (fd, manifest["worker_uid"])
            report["active_native_call"] = mode
            result = supervisor.run_single_process(
                (manifest["worker_path"], mode, manifest["dependency_directory"],
                 str(manifest["worker_uid"]), str(manifest["worker_gid"])),
                uid=manifest["worker_uid"], gid=manifest["worker_gid"], cwd=probe_directory / mode,
                workspace_fd=fd, file_size_bytes=fsize_limit, cpu_seconds=cpu, wall_seconds=wall)
            report.pop("active_native_call")
            item = {"mode": mode, "started_boot_ns": now, "native": result_record(result), "accepted": False}
            report["cases"].append(item)  # Preserve actual evidence even if the next check fails.
            child_cpu += result.child_cpu_ns
            item["worker_observation"] = check_result(result, mode, cpu, fsize_limit,
                                                       manifest["worker_uid"], manifest["worker_gid"])
            item["accepted"] = True
            report["artifact_observation"] = inventory(directory_fds)
            window.check(10)
            require(child_cpu + time.process_time_ns() < RESERVED_CPU_NS, "actual observed diagnostic CPU exceeded")
        require(parent_credentials() == credentials, "parent capabilities/identities changed")
        seals.check()
        report["status"] = "six-native-probes-passed-diagnostic-only"
    except BaseException as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1024]}
        if supervisor is not None and isinstance(exc, supervisor.UnreapedChild):
            if account is not None:
                try:
                    report["diagnostic_accounting"] = dataclasses.asdict(account.stop_unmeasured())
                except BaseException as accounting_error:
                    report["accounting_stop_error"] = type(accounting_error).__name__
            custody_stop(exc, root_fd, report)
    finally:
        if account is not None:
            try:
                current = account.snapshot()
                if current.status != "stopped":
                    current = account.stop_unmeasured()
                require(current.status == "stopped" and current.pending is not None and
                        current.charged_cpu_ns == RESERVED_CPU_NS, "diagnostic full charge not retained")
                report["diagnostic_accounting"] = dataclasses.asdict(current)
                report["diagnostic_refund"] = "NONE: final parent/report/exit CPU has no terminal self-measurement"
            except BaseException as exc:
                report["status"] = "failed"
                report["accounting_stop_error"] = {"type": type(exc).__name__, "message": str(exc)[:1024]}
            finally:
                try:
                    account.close()
                except BaseException as exc:
                    report["status"] = "failed"
                    report["accounting_close_error"] = type(exc).__name__
        if directory_fds:
            try:
                report["artifact_observation"] = inventory(directory_fds)
                require(set(bounded_names(root_fd, 10)) == set(directory_fds) |
                        ({"custody-required.json"} if "custody" in report else set()),
                        "unexpected root output entry")
            except BaseException as exc:
                report["status"] = "failed"
                report["artifact_error"] = {"type": type(exc).__name__, "message": str(exc)[:1024]}
        report["parent_cpu_observed_through_pre_report_ns"] = time.process_time_ns()
        report["returned_children_terminal_cpu_ns"] = sum(item["native"]["child_cpu_ns"] for item in report["cases"])
        report["native_call_without_returned_terminal_cost"] = report.get("active_native_call")
        report["report_phase"] = "pre-exit observation; NEVER accept without exit zero AND outer terminal wall observation"
        if "parent_start_boot_ns" in report:
            report["elapsed_through_pre_report_ns"] = time.clock_gettime_ns(time.CLOCK_BOOTTIME) - report["parent_start_boot_ns"]
            if (report["elapsed_through_pre_report_ns"] >= WALL_SECONDS * NANO or
                    report["parent_cpu_observed_through_pre_report_ns"] + report["returned_children_terminal_cpu_ns"] >= RESERVED_CPU_NS):
                report["status"] = "failed-diagnostic-envelope"
        try:
            if root_fd is not None:
                artifact = write_new_report(root_fd, "report.json", report)
                os.write(1, canonical({"format": FORMAT, "status": report["status"], "report": artifact}) + b"\n")
            else:
                os.write(2, canonical({"format": FORMAT, "status": "preflight-failed", "error": report.get("error")}) + b"\n")
        finally:
            for fd, _uid in directory_fds.values():
                os.close(fd)
            if seals is not None:
                seals.close()
    # Final I/O may have returned late. It is not permitted to turn earlier good
    # observations into an exit-zero success after the original global deadline.
    # This last sample deliberately performs no subsequent reporting/file I/O.
    # The immutable report is labelled pre-exit, and the external root caller
    # must additionally retain the real terminal status/elapsed observation.
    if window is not None:
        try:
            window.check()
            require(parent_libc is not None and parent_libc.prctl(3, 0, 0, 0, 0) == 0,
                    "parent lost nondumpable state")
            require(time.process_time_ns() + report["returned_children_terminal_cpu_ns"] < RESERVED_CPU_NS,
                    "final observed total CPU reached the diagnostic reservation")
        except BaseException:
            return 1
    return 0 if report["status"] == "six-native-probes-passed-diagnostic-only" else 1


if __name__ == "__main__":
    # Avoid unmeasured interpreter/atexit cleanup after the final deadline check.
    os._exit(main())
