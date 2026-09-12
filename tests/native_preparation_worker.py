"""Version-1 disposable Python worker for the separately reviewed native probe.

Not a product entrypoint. The root coordinator must load this exact sealed file
through runpy only AFTER identity drop, guard installation and stopped-parent
readback. No network, corpus, existing database, shell or successful exec path.
"""
import ctypes
import errno
import json
import os
from pathlib import Path
import resource
import signal
import sys


FORMAT = "betboy-native-preparation-worker-v1"
MODES = ("positive", "denials", "fsize", "address_space", "cpu", "output")
GIB = 1024**3


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def libc_handle():
    lib = ctypes.CDLL(None, use_errno=True)
    lib.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    lib.prctl.restype = ctypes.c_int
    lib.syscall.restype = ctypes.c_long
    return lib


def state(lib, uid, gid):
    require(os.getresuid() == (uid,) * 3 and os.getresgid() == (gid,) * 3,
            "worker is not the expected fully nonprivileged identity")
    require(uid > 0 and gid > 0 and os.getgroups() == [], "worker retains privileged groups")
    with open("/proc/self/status", "rb") as stream:
        raw = stream.read(65537)
    require(0 < len(raw) <= 65536 and raw.endswith(b"\n"), "unbounded worker status")
    parsed = {}
    for line in raw.decode("ascii").splitlines():
        name, value = line.split(":", 1)
        require(name not in parsed, "duplicate worker status field")
        parsed[name] = value.strip()
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        require(1 <= len(parsed[name]) <= 16 and int(parsed[name], 16) == 0,
                "worker retains capabilities")
    require(parsed["Uid"].split() == [str(uid)] * 4 and
            parsed["Gid"].split() == [str(gid)] * 4, "filesystem identities differ")
    require(parsed["Threads"] == "1" and parsed["TracerPid"] == "0" and
            parsed["NoNewPrivs"] == "1" and parsed["Seccomp"] == "2",
            "worker process guard is not observable")
    with os.scandir("/proc/self/task") as tasks:
        first, second = next(tasks, None), next(tasks, None)
    require(first is not None and first.name == str(os.getpid()) and second is None,
            "worker is not one kernel task")
    dumpable = lib.prctl(3, 0, 0, 0, 0)
    require(dumpable == 0, "worker dumpability is not zero")
    for key, value in ((resource.RLIMIT_AS, 2 * GIB),
                       (resource.RLIMIT_CORE, 0), (resource.RLIMIT_NPROC, 0)):
        require(resource.getrlimit(key) == (value, value), "worker limit differs")
    return {"pid": os.getpid(), "uid": uid, "gid": gid, "threads": 1,
            "dumpable": dumpable, "no_new_privs": 1, "seccomp": 2,
            "seccomp_filters": int(parsed["Seccomp_filters"]),
            "cpu_limit": list(resource.getrlimit(resource.RLIMIT_CPU)),
            "fsize_limit": list(resource.getrlimit(resource.RLIMIT_FSIZE))}


def emit(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii") + b"\n"
    require(len(raw) <= 8192, "worker control record exceeds bound")
    offset = 0
    while offset < len(raw):
        count = os.write(1, raw[offset:])
        require(count > 0, "worker output made no progress")
        offset += count


def positive(dependency_directory):
    # The parent never imports site, numpy or scipy. No .pth processing occurs.
    # This is deliberately after state() confirmed real unprivileged guard state.
    root = Path(dependency_directory)
    require(root.is_absolute() and root == root.resolve(strict=True), "dependency path is not explicit")
    sys.path.append(str(root))
    import numpy as np
    import scipy
    from scipy.linalg import solve
    import sqlite3
    for module in (np, scipy):
        origin = Path(module.__file__).resolve(strict=True)
        require(origin.is_relative_to(root), "numerical import escaped declared dependency directory")
    answer = solve(np.array([[2.0, 0.0], [0.0, 4.0]]), np.array([4.0, 8.0]))
    require(bool(np.allclose(answer, [2.0, 2.0])), "numerical result differs")
    # Reserve this NEW name exclusively; SQLite only edits this own empty file.
    fd = os.open("probe.sqlite3", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    with sqlite3.connect("probe.sqlite3") as connection:
        connection.execute("PRAGMA page_size=4096")
        require(connection.execute("PRAGMA journal_mode=MEMORY").fetchone() == ("memory",),
                "SQLite did not select in-memory journaling")
        connection.execute("PRAGMA temp_store=MEMORY")
        require(connection.execute("PRAGMA max_page_count=64").fetchone() == (64,),
                "SQLite logical page bound differs")
        connection.execute("CREATE TABLE probe(x INTEGER NOT NULL)")
        connection.executemany("INSERT INTO probe VALUES(?)", [(2,), (3,), (5,)])
        require(connection.execute("SELECT count(*), sum(x) FROM probe").fetchone() == (3, 10),
                "SQLite computation differs")
    connection.close()
    return {"solution": [float(value) for value in answer], "sqlite_sum": 10,
            "sqlite_version": sqlite3.sqlite_version,
            "numpy_version": np.__version__, "scipy_version": scipy.__version__,
            "sqlite_bytes": os.stat("probe.sqlite3", follow_symlinks=False).st_size}


def denials(lib):
    observed = {}
    try:
        child = os.fork()
    except OSError as exc:
        observed["fork_errno"] = exc.errno
    else:
        # Unexpected success is a failed probe, never a measurement success.
        # An accidental child exits immediately; this is not a double-fork test.
        if child == 0:
            os._exit(93)
        os.waitpid(child, 0)
        raise RuntimeError("fork unexpectedly succeeded")
    require(observed["fork_errno"] == errno.EPERM, "fork was not denied by EPERM")
    # Invalid exec arguments can never intentionally execute another image even
    # if the filter is faulty. EPERM (not EFAULT/EBADF) demonstrates the denial.
    for label, number in (("execve", 59), ("execveat", 322), ("clone3", 435)):
        ctypes.set_errno(0)
        result = lib.syscall(ctypes.c_long(number), *([ctypes.c_ulong(0)] * 6))
        observed[label + "_errno"] = ctypes.get_errno()
        require(result == -1 and observed[label + "_errno"] == errno.EPERM,
                label + " was not denied by EPERM")
    ctypes.set_errno(0)
    result = lib.prctl(4, 1, 0, 0, 0)
    observed["dumpable_set_errno"] = ctypes.get_errno()
    require(result == -1 and observed["dumpable_set_errno"] == errno.EPERM,
            "Dumpable reset was not denied by EPERM")
    # pthread_create returns its error NUMBER directly; errno is not its API.
    callback_type = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
    callback = callback_type(lambda _arg: None)
    thread = ctypes.c_ulong()
    lib.pthread_create.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
                                  callback_type, ctypes.c_void_p]
    lib.pthread_create.restype = ctypes.c_int
    result = lib.pthread_create(ctypes.byref(thread), None, callback, None)
    observed["pthread_create_error"] = result
    if result == 0:
        lib.pthread_join.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
        lib.pthread_join.restype = ctypes.c_int
        lib.pthread_join(thread, None)
        raise RuntimeError("pthread_create unexpectedly succeeded")
    require(result == errno.EPERM, "pthread_create was not denied by EPERM")
    require(lib.prctl(3, 0, 0, 0, 0) == 0, "Dumpable changed after rejected reset")
    return observed


def fsize():
    require(resource.getrlimit(resource.RLIMIT_FSIZE) == (4096, 4096), "FSIZE probe limit differs")
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    fd = os.open("fsize.bin", os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        require(os.write(fd, b"x" * 4096) == 4096, "bounded first file write differs")
        try:
            os.write(fd, b"x")
        except OSError as exc:
            require(exc.errno == errno.EFBIG, "FSIZE denial was not EFBIG")
            error = exc.errno
        else:
            raise RuntimeError("FSIZE extension unexpectedly succeeded")
        os.fsync(fd)
        size = os.fstat(fd).st_size
        require(size == 4096, "FSIZE file size differs")
        return {"extension_errno": error, "file_bytes": size}
    finally:
        os.close(fd)


def address_space(lib):
    import mmap
    requested = 3 * GIB
    lib.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                         ctypes.c_int, ctypes.c_int, ctypes.c_long]
    lib.mmap.restype = ctypes.c_void_p
    ctypes.set_errno(0)
    address = lib.mmap(None, requested, mmap.PROT_READ | mmap.PROT_WRITE,
                       mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS, -1, 0)
    error = ctypes.get_errno()
    if address != ctypes.c_void_p(-1).value:
        # No read, write, MAP_POPULATE or physical touching, even on failure.
        lib.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        lib.munmap.restype = ctypes.c_int
        lib.munmap(address, requested)
        raise RuntimeError("virtual reservation unexpectedly succeeded")
    require(error == errno.ENOMEM, "virtual reservation was not rejected with ENOMEM")
    return {"requested_virtual_bytes": requested, "touched_bytes": 0, "mmap_errno": error}


def main():
    require(sys.platform == "linux" and len(sys.argv) == 5, "native worker argument/platform mismatch")
    mode, dependency_directory, raw_uid, raw_gid = sys.argv[1:]
    require(mode in MODES and raw_uid.isascii() and raw_uid.isdecimal() and
            raw_gid.isascii() and raw_gid.isdecimal() and
            len(raw_uid) <= 10 and len(raw_gid) <= 10, "unknown bounded worker mode/identity")
    uid, gid = int(raw_uid), int(raw_gid)
    lib = libc_handle()
    before = state(lib, uid, gid)
    os.umask(0o077)
    # The new output ancestor is root0711: searchable, not listable/writable.
    # SQLite's VFS resolves even relative DB names to absolute paths. Journals
    # remain separately root0700; this child's new private cwd is nobody0700.
    os.environ["TMPDIR"] = "."
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "GOTO_NUM_THREADS", "BLIS_NUM_THREADS"):
        os.environ[name] = "1"
    if mode in ("cpu", "output"):
        emit({"format": FORMAT, "mode": mode, "phase": "armed", "state": before})
        if mode == "cpu":
            require(before["cpu_limit"] == [1, 1], "CPU fault probe limit differs")
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
            while True:
                pass
        chunk = b"x" * 65536
        for _ in range(32):
            offset = 0
            while offset < len(chunk):
                count = os.write(1, chunk[offset:])
                require(count > 0, "output fault made no progress")
                offset += count
        raise RuntimeError("output overrun was not stopped before 2 MiB")
    if mode == "positive":
        detail = positive(dependency_directory)
    elif mode == "denials":
        detail = denials(lib)
    elif mode == "fsize":
        detail = fsize()
    else:
        detail = address_space(lib)
    after = state(lib, uid, gid)
    require(before == after, "worker kernel identity/guard changed")
    emit({"format": FORMAT, "mode": mode, "phase": "complete", "state": after, "detail": detail})


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        # Errors are bounded data, not a command, retry request or success proof.
        raw_error = (type(exc).__name__ + ": " + str(exc))[:1024]
        os.write(2, raw_error.encode("utf-8", errors="backslashreplace") + b"\n")
        raise SystemExit(91)
