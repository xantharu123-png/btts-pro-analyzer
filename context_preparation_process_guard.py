"""A narrow Linux/x86_64 LP64 guard, installed in a fresh QA-worker child.

Import this module in the single-threaded trusted launcher BEFORE os.fork().
Only its direct child may use the two public functions. The privileged child
first drops its capability bounding set; the launcher then drops supplementary
groups and all real/effective/saved GIDs and UIDs. The now-unprivileged child
installs the filter before product imports, in the same Python process; exec
is then forbidden. Any exception requires the
launcher to discard that child: changes are irreversible and are not undone.

This is NOT a filesystem sandbox, physical/global quota, CPU/RSS/output meter,
deadline supervisor, authenticated report, budget settlement, or B/C approval.
Fresh-fork provenance, trusted native/ELF closure, namespaces and parent-side
pidfd/readback/wait4 custody remain external requirements. Returned values are
observations, not launch authority. Single-thread numerical-library settings
must be supplied before numerical imports; no model rules are changed here.
"""
from dataclasses import dataclass
import ctypes
import errno
import hashlib
import os
import re
import signal
import struct
import sys


MAX_CPU_SECONDS = 300
ADDRESS_SPACE_BYTES = 2 * 1024**3
MAX_FILE_SIZE_BYTES = 8 * 1024**3
MAX_STATUS_BYTES = 65536
MAX_CAPABILITY = 63
_IMPORT_PID = os.getpid()
_PROC_SUPER_MAGIC = 0x9FA0
_AUDIT_ARCH_X86_64 = 0xC000003E
_X32_SYSCALL_BIT = 0x40000000
_SECCOMP_RET_KILL_PROCESS = 0x80000000
_SECCOMP_RET_ALLOW = 0x7FFF0000
_SECCOMP_RET_ERRNO = 0x00050000 | errno.EPERM
_LD, _JEQ, _JGE, _RET = 0x20, 0x15, 0x35, 0x06
_PR_GET_SECCOMP, _PR_CAPBSET_READ, _PR_CAPBSET_DROP = 21, 23, 24
_PR_GET_DUMPABLE, _PR_SET_DUMPABLE = 3, 4
_PR_SET_NO_NEW_PRIVS, _PR_GET_NO_NEW_PRIVS, _PR_CAP_AMBIENT = 38, 39, 47
_SYS_SECCOMP, _SECCOMP_SET_MODE_FILTER, _SECCOMP_FILTER_FLAG_TSYNC = 317, 1, 1
_CAP_VERSION_3, _CAP_SETPCAP = 0x20080522, 8
_DECIMAL = re.compile(rb"(?:0|[1-9][0-9]{0,19})\Z")
_CAP_HEX = re.compile(rb"[0-9a-f]{16}\Z")

# Fixed, reviewed x86_64 numbers, NOT a range or a host-discovered allowlist.
# Source: Linux v6.12 arch/x86/entry/syscalls/syscall_64.tbl (syscall ABI facts).
# Unknown/new calls fail closed. fork/clone/vfork/clone3, namespaces, ptrace,
# io_uring/AIO, userfaultfd, bpf and privilege/limit setters are absent.
# prctl and prlimit64 have separate restricted read-only argument rules below.
_ALLOWED_SYSCALLS = (
    ("read", 0), ("write", 1), ("open", 2), ("close", 3),
    ("stat", 4), ("fstat", 5), ("lstat", 6), ("poll", 7),
    ("lseek", 8), ("mmap", 9), ("mprotect", 10), ("munmap", 11),
    ("brk", 12), ("rt_sigaction", 13), ("rt_sigprocmask", 14),
    ("rt_sigreturn", 15), ("ioctl", 16), ("pread64", 17),
    ("pwrite64", 18), ("readv", 19), ("writev", 20), ("access", 21),
    ("pipe", 22), ("select", 23), ("sched_yield", 24), ("mremap", 25),
    ("msync", 26), ("mincore", 27), ("madvise", 28), ("dup", 32),
    ("dup2", 33), ("pause", 34), ("nanosleep", 35), ("getitimer", 36),
    ("alarm", 37), ("setitimer", 38), ("getpid", 39), ("sendfile", 40),
    ("exit", 60), ("wait4", 61), ("kill", 62),
    ("uname", 63), ("fcntl", 72), ("flock", 73), ("fsync", 74),
    ("fdatasync", 75), ("truncate", 76), ("ftruncate", 77),
    ("getdents", 78), ("getcwd", 79), ("chdir", 80), ("fchdir", 81),
    ("rename", 82), ("mkdir", 83), ("rmdir", 84), ("creat", 85),
    ("link", 86), ("unlink", 87), ("symlink", 88), ("readlink", 89),
    ("chmod", 90), ("fchmod", 91), ("umask", 95), ("gettimeofday", 96),
    ("getrlimit", 97), ("getrusage", 98), ("sysinfo", 99), ("times", 100),
    ("getuid", 102), ("getgid", 104), ("geteuid", 107), ("getegid", 108),
    ("getppid", 110), ("getpgrp", 111), ("getgroups", 115),
    ("getresuid", 118), ("getresgid", 120), ("getpgid", 121),
    ("getsid", 124), ("capget", 125), ("rt_sigpending", 127),
    ("rt_sigtimedwait", 128), ("rt_sigsuspend", 130), ("sigaltstack", 131),
    ("utime", 132), ("statfs", 137), ("fstatfs", 138),
    ("getpriority", 140), ("sched_getparam", 143), ("sched_getscheduler", 145),
    ("sched_get_priority_max", 146), ("sched_get_priority_min", 147),
    ("sched_rr_get_interval", 148), ("arch_prctl", 158), ("gettid", 186),
    ("readahead", 187), ("getxattr", 191), ("lgetxattr", 192),
    ("fgetxattr", 193), ("listxattr", 194), ("llistxattr", 195),
    ("flistxattr", 196), ("tkill", 200), ("time", 201), ("futex", 202),
    ("sched_getaffinity", 204), ("epoll_create", 213), ("getdents64", 217),
    ("set_tid_address", 218), ("restart_syscall", 219), ("fadvise64", 221),
    ("clock_gettime", 228), ("clock_getres", 229), ("clock_nanosleep", 230),
    ("exit_group", 231), ("epoll_wait", 232), ("epoll_ctl", 233),
    ("tgkill", 234), ("utimes", 235), ("get_mempolicy", 239),
    ("waitid", 247), ("openat", 257), ("mkdirat", 258),
    ("futimesat", 261), ("newfstatat", 262), ("unlinkat", 263),
    ("renameat", 264), ("linkat", 265), ("symlinkat", 266),
    ("readlinkat", 267), ("fchmodat", 268), ("faccessat", 269),
    ("pselect6", 270), ("ppoll", 271), ("set_robust_list", 273),
    ("get_robust_list", 274), ("utimensat", 280), ("epoll_pwait", 281),
    ("signalfd", 282), ("timerfd_create", 283), ("eventfd", 284),
    ("timerfd_settime", 286), ("timerfd_gettime", 287), ("signalfd4", 289),
    ("eventfd2", 290), ("epoll_create1", 291), ("dup3", 292), ("pipe2", 293),
    ("preadv", 295), ("pwritev", 296), ("getcpu", 309),
    ("sched_getattr", 315), ("renameat2", 316), ("getrandom", 318),
    ("membarrier", 324), ("copy_file_range", 326),
    ("preadv2", 327), ("pwritev2", 328), ("statx", 332), ("rseq", 334),
    ("close_range", 436), ("openat2", 437), ("faccessat2", 439),
    ("epoll_pwait2", 441), ("futex_waitv", 449), ("fchmodat2", 452),
)


class GuardError(RuntimeError):
    """Do not execute worker code; discard this possibly partially changed child."""


class GuardUnavailable(GuardError):
    pass


@dataclass(frozen=True)
class BoundingSetReadback:
    pid: int
    cap_last_cap: int
    bounding_mask: int


@dataclass(frozen=True)
class GuardReadback:
    pid: int
    ppid: int
    uid: int
    gid: int
    cap_last_cap: int
    cpu_seconds: int
    address_space_bytes: int
    core_bytes: int
    file_size_bytes: int
    nproc: int
    dumpable: int
    no_new_privs: int
    seccomp_mode: int
    seccomp_filters: int
    threads: int
    policy_sha256: str


def _integer(value, label, maximum, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise GuardError("invalid exact integer " + label)
    return value


def _expect_result(value, expected, label):
    if type(value) is not int or value != expected:
        raise GuardError("native result was not confirmed: " + label)


def _read_limit(native, name):
    result = native.get_limit(name)
    if (type(result) is not tuple or len(result) != 2
            or any(type(value) is not int or value < -1 for value in result)
            or (result[1] != -1 and (result[0] == -1 or result[0] > result[1]))):
        raise GuardError("native limit pair is not exact: " + name)
    return result


def _decimal(value, label, maximum=2**32 - 1):
    if type(value) is not bytes or _DECIMAL.fullmatch(value) is None:
        raise GuardError("invalid bounded decimal " + label)
    return _integer(int(value), label, maximum)


def _parse_cap_last_cap(data):
    if type(data) is not bytes or not 2 <= len(data) <= 3 or data[-1:] != b"\n":
        raise GuardError("missing or unbounded cap_last_cap")
    return _decimal(data[:-1], "cap_last_cap", MAX_CAPABILITY)


def _parse_status(data):
    if type(data) is not bytes or not 0 < len(data) <= MAX_STATUS_BYTES or not data.endswith(b"\n"):
        raise GuardError("missing, oversized or partial /proc status")
    result = {}
    required = {"Pid", "Tgid", "PPid", "TracerPid", "Threads", "Uid", "Gid",
                "Groups", "CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb",
                "NoNewPrivs", "Seccomp", "Seccomp_filters"}
    seen = set()
    for line in data.splitlines():
        key, separator, value = line.partition(b":")
        if not separator or key in seen or not re.fullmatch(rb"[A-Za-z_][A-Za-z_0-9]*", key):
            raise GuardError("malformed or duplicate /proc status field")
        seen.add(key)
        name = key.decode("ascii")
        if name not in required:
            continue
        value = value.strip(b" \t")
        if name.startswith("Cap"):
            if _CAP_HEX.fullmatch(value) is None:
                raise GuardError("malformed capability mask")
            result[name] = int(value, 16)
        elif name in {"Uid", "Gid"}:
            pieces = value.split()
            if len(pieces) != 4:
                raise GuardError("missing real/effective/saved/filesystem IDs")
            result[name] = tuple(_decimal(piece, name) for piece in pieces)
        elif name == "Groups":
            pieces = value.split()
            if len(pieces) > 64:
                raise GuardError("supplementary group observation is not bounded")
            result[name] = tuple(_decimal(piece, "supplementary group") for piece in pieces)
        else:
            result[name] = _decimal(value, name)
    if set(result) != required:
        raise GuardError("incomplete measurable kernel status")
    if result["NoNewPrivs"] not in (0, 1) or result["Seccomp"] not in (0, 2):
        raise GuardError("unsupported privilege or seccomp status")
    if result["Seccomp_filters"] > 256:
        raise GuardError("unbounded preexisting filter count")
    if (result["Seccomp"] == 0) != (result["Seccomp_filters"] == 0):
        raise GuardError("inconsistent seccomp readback")
    return result


def _require_abi(platform, machine, pointer_bytes, long_bytes, byteorder, header):
    if (platform != "linux" or machine != "x86_64" or pointer_bytes != 8
            or long_bytes != 8 or byteorder != "little"):
        raise GuardUnavailable("requires native Linux x86_64 LP64 little-endian ABI")
    if (type(header) is not bytes or len(header) != 64 or header[:7] != b"\x7fELF\x02\x01\x01"
            or header[7] not in (0, 3) or header[18:20] != b"\x3e\x00"):
        raise GuardUnavailable("current executable is not a bounded ELF64 x86_64 image")


def _policy():
    program = [(_LD, 0, 0, 4), (_JEQ, 1, 0, _AUDIT_ARCH_X86_64),
               (_RET, 0, 0, _SECCOMP_RET_KILL_PROCESS), (_LD, 0, 0, 0),
               (_JGE, 0, 1, _X32_SYSCALL_BIT), (_RET, 0, 0, _SECCOMP_RET_KILL_PROCESS),
               (_JGE, 0, 2, 512), (_JGE, 1, 0, 548),
               (_RET, 0, 0, _SECCOMP_RET_KILL_PROCESS)]
    # prlimit64: pid==0 and new_limit==NULL, checking both halves of each u64.
    block = []
    for offset in (16, 20, 32, 36):
        block.extend([(_LD, 0, 0, offset), (_JEQ, 1, 0, 0), (_RET, 0, 0, _SECCOMP_RET_ERRNO)])
    block.append((_RET, 0, 0, _SECCOMP_RET_ALLOW))
    program.extend([(_JEQ, 0, len(block), 302), *block])
    # prctl: only GET_DUMPABLE/SECCOMP/NO_NEW_PRIVS, CAPBSET_READ, AMBIENT_IS_SET.
    block = [(_LD, 0, 0, 20), (_JEQ, 1, 0, 0), (_RET, 0, 0, _SECCOMP_RET_ERRNO),
             (_LD, 0, 0, 16)]
    for option in (_PR_GET_DUMPABLE, _PR_GET_SECCOMP, _PR_GET_NO_NEW_PRIVS, _PR_CAPBSET_READ):
        block.extend([(_JEQ, 0, 1, option), (_RET, 0, 0, _SECCOMP_RET_ALLOW)])
    block.extend([(_JEQ, 1, 0, _PR_CAP_AMBIENT), (_RET, 0, 0, _SECCOMP_RET_ERRNO),
                  (_LD, 0, 0, 24), (_JEQ, 1, 0, 1), (_RET, 0, 0, _SECCOMP_RET_ERRNO),
                  (_LD, 0, 0, 28), (_JEQ, 1, 0, 0), (_RET, 0, 0, _SECCOMP_RET_ERRNO),
                  (_RET, 0, 0, _SECCOMP_RET_ALLOW)])
    program.extend([(_JEQ, 0, len(block), 157), *block])
    numbers = [number for _name, number in _ALLOWED_SYSCALLS]
    if len(numbers) != len(set(numbers)) or numbers != sorted(numbers):
        raise GuardError("fixed syscall policy is not unique and ordered")
    for number in numbers:
        program.extend([(_JEQ, 0, 1, number), (_RET, 0, 0, _SECCOMP_RET_ALLOW)])
    program.append((_RET, 0, 0, _SECCOMP_RET_ERRNO))
    if len(program) > 512:
        raise GuardError("fixed BPF program exceeded its instruction bound")
    return tuple(program)


def _policy_digest(program):
    return hashlib.sha256(b"".join(struct.pack("<HBBI", *instruction) for instruction in program)).hexdigest()


class _SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]


class _SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(_SockFilter))]


class _CapHeader(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint), ("pid", ctypes.c_int)]


class _CapData(ctypes.Structure):
    _fields_ = [("effective", ctypes.c_uint), ("permitted", ctypes.c_uint), ("inheritable", ctypes.c_uint)]


class _StatFs(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_long), ("block_size", ctypes.c_long),
                ("blocks", ctypes.c_ulong), ("blocks_free", ctypes.c_ulong),
                ("blocks_available", ctypes.c_ulong), ("files", ctypes.c_ulong),
                ("files_free", ctypes.c_ulong), ("fsid", ctypes.c_int * 2),
                ("name_length", ctypes.c_long), ("fragment_size", ctypes.c_long),
                ("flags", ctypes.c_long), ("spare", ctypes.c_long * 4)]


class _Native:
    """Native-only observation/transition boundary; no public injected backend."""
    def __init__(self):
        if sys.platform != "linux":
            raise GuardUnavailable("native process guard is Linux-only")
        self.pid, self.ppid = os.getpid(), os.getppid()
        if self.pid == _IMPORT_PID or self.ppid != _IMPORT_PID:
            raise GuardError("guard must run in the direct fork child of its importing launcher")
        executable = os.open("/proc/self/exe", os.O_RDONLY | os.O_CLOEXEC)
        try:
            header = os.read(executable, 64)
        finally:
            os.close(executable)
        _require_abi(sys.platform, os.uname().machine, ctypes.sizeof(ctypes.c_void_p),
                     ctypes.sizeof(ctypes.c_long), sys.byteorder, header)
        if ctypes.sizeof(_SockFilter) != 8 or ctypes.sizeof(_SockFprog) != 16 or ctypes.sizeof(_StatFs) != 120:
            raise GuardUnavailable("unexpected native structure ABI")
        import resource
        self.resource = resource
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
        self.libc.prctl.restype = ctypes.c_int
        self.libc.capget.argtypes = [ctypes.POINTER(_CapHeader), ctypes.POINTER(_CapData)]
        self.libc.capget.restype = ctypes.c_int
        self.libc.fstatfs.argtypes = [ctypes.c_int, ctypes.POINTER(_StatFs)]
        self.libc.fstatfs.restype = ctypes.c_int
        self.libc.syscall.restype = ctypes.c_long
        self.proc = os.open("/proc", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            self._require_procfs(self.proc)
        except BaseException:
            os.close(self.proc)
            raise

    def _require_procfs(self, fd):
        info = _StatFs()
        if self.libc.fstatfs(fd, ctypes.byref(info)) != 0 or info.kind != _PROC_SUPER_MAGIC:
            raise GuardError("kernel observation is not on procfs")

    def read_proc(self, path, maximum):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=self.proc)
        try:
            self._require_procfs(fd)
            result = bytearray()
            while len(result) <= maximum:
                part = os.read(fd, min(4096, maximum + 1 - len(result)))
                if not part:
                    break
                result.extend(part)
            if len(result) > maximum:
                raise GuardError("kernel observation exceeds its byte bound")
            return bytes(result)
        finally:
            os.close(fd)

    def status(self):
        return _parse_status(self.read_proc(f"{self.pid}/status", MAX_STATUS_BYTES))

    def task_ids(self):
        fd = os.open(f"{self.pid}/task", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.proc)
        try:
            self._require_procfs(fd)
            result = []
            with os.scandir(fd) as entries:
                for entry in entries:
                    result.append(_decimal(os.fsencode(entry.name), "task ID"))
                    if len(result) > 1:
                        break
            return tuple(result)
        finally:
            os.close(fd)

    def no_children(self):
        # WNOWAIT avoids reaping. __WALL also covers clone children with unusual
        # exit signals; None means living children, NOT a successful empty set.
        try:
            os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT | 0x40000000)
        except ChildProcessError as exc:
            if exc.errno == errno.ECHILD:
                return
            raise
        raise GuardError("preexisting child or indeterminate child state")

    def ids(self):
        return os.getresuid(), os.getresgid(), tuple(os.getgroups())

    def prctl(self, option, arg=0, third=0):
        ctypes.set_errno(0)
        result = self.libc.prctl(option, arg, third, 0, 0)
        if result < 0:
            raise OSError(ctypes.get_errno(), "native prctl failed")
        return result

    def capabilities(self):
        header, values = _CapHeader(_CAP_VERSION_3, 0), (_CapData * 2)()
        if self.libc.capget(ctypes.byref(header), values) != 0 or header.version != _CAP_VERSION_3:
            raise GuardError("capget v3 could not be verified")
        return {name: getattr(values[0], field) | (getattr(values[1], field) << 32)
                for name, field in (("CapEff", "effective"), ("CapPrm", "permitted"), ("CapInh", "inheritable"))}

    def cap_last_cap(self):
        return _parse_cap_last_cap(self.read_proc("sys/kernel/cap_last_cap", 3))

    def get_limit(self, name):
        return self.resource.getrlimit(getattr(self.resource, "RLIMIT_" + name))

    def set_limit(self, name, value):
        self.resource.setrlimit(getattr(self.resource, "RLIMIT_" + name), (value, value))

    def set_filter(self, program):
        array = (_SockFilter * len(program))(*(_SockFilter(*entry) for entry in program))
        native = _SockFprog(len(program), array)
        ctypes.set_errno(0)
        result = self.libc.syscall(ctypes.c_long(_SYS_SECCOMP), ctypes.c_uint(_SECCOMP_SET_MODE_FILTER),
                                   ctypes.c_uint(_SECCOMP_FILTER_FLAG_TSYNC), ctypes.byref(native))
        # TSYNC can return a positive unsynchronized TID; only exact zero works.
        if type(result) is not int or result != 0:
            raise GuardError("seccomp TSYNC did not confirm filter installation")

    def block_signals(self):
        return signal.pthread_sigmask(signal.SIG_BLOCK, signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP})

    def restore_signals(self, previous):
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)

    def close(self):
        os.close(self.proc)


def _observe(native, *, privileged):
    status = native.status()
    if (status["Pid"] != native.pid or status["Tgid"] != native.pid
            or status["PPid"] != native.ppid or status["Threads"] != 1
            or status["TracerPid"] != 0 or native.task_ids() != (native.pid,)):
        raise GuardError("not an untraced single-main-thread kernel task")
    native.no_children()
    uids, gids, groups = native.ids()
    if (type(uids) is not tuple or type(gids) is not tuple or len(uids) != 3 or len(gids) != 3
            or any(type(item) is not int for item in uids + gids)
            or type(groups) is not tuple or any(type(item) is not int for item in groups)
            or groups != status["Groups"]
            or status["Uid"] != (*uids, uids[1]) or status["Gid"] != (*gids, gids[1])):
        raise GuardError("real/effective/saved/filesystem credentials disagree")
    if privileged:
        if uids != (0, 0, 0):
            raise GuardError("bounding-set drop requires the privileged fresh child")
    elif (groups or len(set(uids)) != 1 or len(set(gids)) != 1 or uids[0] <= 0 or gids[0] <= 0):
        raise GuardError("worker must have equal nonzero real/effective/saved IDs")
    caps = native.capabilities()
    if any(status[key] != value for key, value in caps.items()):
        raise GuardError("direct capget and proc capability readback disagree")
    last = _integer(native.cap_last_cap(), "cap_last_cap", MAX_CAPABILITY)
    bound, ambient = 0, 0
    for capability in range(last + 1):
        bnd = native.prctl(_PR_CAPBSET_READ, capability)
        amb = native.prctl(_PR_CAP_AMBIENT, 1, capability)
        if type(bnd) is not int or type(amb) is not int or bnd not in (0, 1) or amb not in (0, 1):
            raise GuardError("capability bit cannot be read back exactly")
        bound |= bnd << capability
        ambient |= amb << capability
    try:
        native.prctl(_PR_CAPBSET_READ, last + 1)
    except OSError as exc:
        if exc.errno != errno.EINVAL:
            raise GuardError("capability upper bound could not be confirmed") from exc
    else:
        raise GuardError("kernel capability range exceeds the observed bound")
    if bound != status["CapBnd"] or ambient != status["CapAmb"]:
        raise GuardError("direct and proc bounding/ambient masks disagree")
    if not privileged and any(status[key] for key in ("CapEff", "CapPrm", "CapInh", "CapBnd", "CapAmb")):
        raise GuardError("all five worker capability sets must already be zero")
    _expect_result(native.prctl(_PR_GET_NO_NEW_PRIVS), status["NoNewPrivs"], "no_new_privs")
    _expect_result(native.prctl(_PR_GET_SECCOMP), status["Seccomp"], "seccomp mode")
    return status, last


def _drop_bounding(native):
    status, last = _observe(native, privileged=True)
    if not (status["CapEff"] & (1 << _CAP_SETPCAP)):
        raise GuardError("actual CAP_SETPCAP is required before the UID drop")
    for capability in range(last + 1):
        _expect_result(native.prctl(_PR_CAPBSET_DROP, capability), 0, "bounding capability drop")
        _expect_result(native.prctl(_PR_CAPBSET_READ, capability), 0, "zero bounding capability")
    after, last_after = _observe(native, privileged=True)
    if last_after != last or after["CapBnd"] != 0:
        raise GuardError("complete zero bounding set was not confirmed")
    return BoundingSetReadback(native.pid, last, 0)


def _install(native, file_size_bytes, cpu_seconds):
    _integer(file_size_bytes, "file size", MAX_FILE_SIZE_BYTES)
    _integer(cpu_seconds, "CPU seconds", MAX_CPU_SECONDS, minimum=1)
    before, last = _observe(native, privileged=False)
    _integer(native.prctl(_PR_GET_DUMPABLE), "observed dumpable state", 2)
    desired = (("NPROC", 0), ("FSIZE", file_size_bytes), ("CORE", 0),
               ("AS", ADDRESS_SPACE_BYTES), ("CPU", cpu_seconds))
    for name, target in desired:
        _soft, hard = _read_limit(native, name)
        if hard != -1 and hard < target:
            raise GuardError("inherited limit cannot establish the fixed " + name + " bound")
    # UID/GID drop happened first. No later exec or credential/dumpable setter
    # is allowed by the filter, so it cannot reset this to host suid_dumpable.
    _expect_result(native.prctl(_PR_SET_DUMPABLE, 0), 0, "set dumpable zero")
    _expect_result(native.prctl(_PR_GET_DUMPABLE), 0, "dumpable zero before filter")
    for name, target in desired:
        native.set_limit(name, target)
        if _read_limit(native, name) != (target, target):
            raise GuardError("native limit did not read back exactly: " + name)
    _expect_result(native.prctl(_PR_SET_NO_NEW_PRIVS, 1), 0, "set no_new_privs")
    _expect_result(native.prctl(_PR_GET_NO_NEW_PRIVS), 1, "no_new_privs one")
    program = _policy()
    native.set_filter(program)
    after, last_after = _observe(native, privileged=False)
    _expect_result(native.prctl(_PR_GET_DUMPABLE), 0, "dumpable zero after filter")
    if (last_after != last or after["NoNewPrivs"] != 1 or after["Seccomp"] != 2
            or after["Seccomp_filters"] != before["Seccomp_filters"] + 1
            or after["Uid"] != before["Uid"] or after["Gid"] != before["Gid"]):
        raise GuardError("installed kernel guard state was not confirmed")
    for name, target in desired:
        if _read_limit(native, name) != (target, target):
            raise GuardError("final native limit readback changed: " + name)
    return GuardReadback(native.pid, native.ppid, after["Uid"][0], after["Gid"][0], last,
                         cpu_seconds, ADDRESS_SPACE_BYTES, 0, file_size_bytes, 0, 0, 1, 2,
                         after["Seccomp_filters"], 1, _policy_digest(program))


def _run(operation, *args):
    native = _Native()
    previous = None
    try:
        previous = native.block_signals()
        return operation(native, *args)
    except (OSError, ValueError, AttributeError) as exc:
        raise GuardError("native guard transition failed; discard this child") from exc
    finally:
        try:
            if previous is not None:
                native.restore_signals(previous)
        finally:
            native.close()


def drop_worker_capability_bounding_set():
    """Privileged fresh child only; drop all bounding bits, not UIDs/GIDs.

The launcher must subsequently setgroups([]), setresgid(gid,gid,gid), and
setresuid(uid,uid,uid). This function changes only its calling child, never the
parent/host. It does not claim the remaining capability sets are already zero.
"""
    return _run(_drop_bounding)


def install_single_process_guard(*, file_size_bytes: int, cpu_seconds: int = 300):
    """Irreversibly restrict the unprivileged child before same-process Python work.

FSIZE is a logical per-file extension bound, NOT a physical/global disk quota.
The fixed AS/CORE/NPROC limits and CPU range cannot be caller-expanded. Returned
readbacks require independent parent-side custody and are not measurement proof.
Dumpable is set/read as zero; execve/execveat and dumpable setters are forbidden.
"""
    _integer(file_size_bytes, "file size", MAX_FILE_SIZE_BYTES)
    _integer(cpu_seconds, "CPU seconds", MAX_CPU_SECONDS, minimum=1)
    return _run(_install, file_size_bytes, cpu_seconds)
