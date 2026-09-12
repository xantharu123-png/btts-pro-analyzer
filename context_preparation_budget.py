"""Conservative preparation accounting only; never execution or proof authority.

The fixed C/B preparation envelope is 1800 CPU seconds, 3600 elapsed seconds,
and at most 300 CPU seconds reserved per portion. A ticket is returned only
after its append has been synced. An outstanding ticket recovered by another
handle is permanently blocked in V1 and retains its entire charge.

Settlement is explicitly a *claim* supplied by the future trusted complete-job
process-tree meter, not evidence that such measurement happened. This module
does not spawn, supervise, authorize a refund, verify a root namespace, create
B proofs, authenticate measurements, or enforce native CPU/RSS/disk limits.
It cannot prevent a privileged journal/whole-VM rollback or deletion followed
by create: a protected durable registry and native owner remain mandatory.

Public durable opening is Linux-only (flock, held directory/file descriptors,
O_NOFOLLOW, file and directory fsync). Portable tests may exercise the pure
protocol and real local descriptor I/O without claiming those Linux guarantees.
There is deliberately no repair, truncation, implicit creation, or retry API.
"""
from dataclasses import dataclass, fields, replace
from functools import wraps
import hashlib
import json
import os
import re
import stat
import sys
import threading
import time


TOTAL_CPU_NS = 1800 * 10**9
PORTION_CPU_NS = 300 * 10**9
TOTAL_ELAPSED_NS = 3600 * 10**9
MAX_RECORD_BYTES = 4096
MAX_RECORDS = 256
MAX_JOURNAL_BYTES = MAX_RECORD_BYTES * MAX_RECORDS
MAX_CLOCK_SAMPLE_NS = 50_000_000
MAX_INTEGER = 2**63 - 1
_VERSION = 1
_FORMAT = "betboy-preparation-accounting-v1"
_ZERO = "0" * 64
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_BOOT = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z", re.ASCII)
_OWNERS = set()
_OWNERS_LOCK = threading.Lock()


class BudgetError(RuntimeError):
    """No preparation authorization may be inferred from an accounting error."""


class BudgetIntegrityError(BudgetError):
    pass


class BudgetExceeded(BudgetError):
    pass


class BudgetStopped(BudgetError):
    pass


class BudgetBusy(BudgetError):
    pass


class BudgetIOError(BudgetError):
    pass


class NativeBudgetUnavailable(BudgetError):
    pass


def _exclusive(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        if not self._operation_lock.acquire(blocking=False):
            raise BudgetBusy("another operation owns this accounting handle")
        try:
            return method(self, *args, **kwargs)
        finally:
            self._operation_lock.release()
    return guarded


def _integer(value, label, *, minimum=0, maximum=MAX_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        raise BudgetIntegrityError("invalid exact integer " + label)
    return value


def _digest(value, label):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise BudgetIntegrityError("invalid lowercase SHA256 " + label)
    return value


def _closed(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise BudgetIntegrityError("unknown or incomplete " + label)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise BudgetIntegrityError("invalid canonical accounting data") from exc


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class BudgetIdentity:
    input_digest: str
    execution_digest: str
    runtime_digest: str
    installation_digest: str
    profile_digest: str


def _identity(value):
    if type(value) is not BudgetIdentity:
        raise BudgetIntegrityError("exact budget identity required")
    result = {field.name: _digest(getattr(value, field.name), field.name)
              for field in fields(BudgetIdentity)}
    return result


@dataclass(frozen=True)
class ClockSample:
    boot_id: str
    boot_before_ns: int
    realtime_ns: int
    boot_after_ns: int


def _clock(value):
    if type(value) is not ClockSample or type(value.boot_id) is not str or _BOOT.fullmatch(value.boot_id) is None:
        raise BudgetIntegrityError("invalid boot clock identity")
    for name in ("boot_before_ns", "realtime_ns", "boot_after_ns"):
        _integer(getattr(value, name), name)
    if not 0 <= value.boot_after_ns - value.boot_before_ns <= MAX_CLOCK_SAMPLE_NS:
        raise BudgetIntegrityError("clock observation is inverted or unmeasurably wide")
    return {field.name: getattr(value, field.name) for field in fields(ClockSample)}


def _clock_from_dict(value):
    _closed(value, (field.name for field in fields(ClockSample)), "clock sample")
    result = ClockSample(**value)
    _clock(result)
    return result


def _system_clock():
    if sys.platform != "linux" or not hasattr(time, "CLOCK_BOOTTIME"):
        raise NativeBudgetUnavailable("native Linux boot-inclusive clock is required")
    try:
        with open("/proc/sys/kernel/random/boot_id", "rb") as stream:
            raw = stream.read(129)
        if len(raw) != 37 or raw[-1:] != b"\n":
            raise BudgetIntegrityError("kernel boot identity is not bounded")
        boot_id = raw[:-1].decode("ascii")
        before = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        wall = time.time_ns()
        after = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    except (OSError, UnicodeError) as exc:
        raise BudgetIOError("native clock could not be observed") from exc
    result = ClockSample(boot_id, before, wall, after)
    _clock(result)
    return result


@dataclass(frozen=True)
class Reservation:
    identity_digest: str
    reservation_digest: str
    sequence: int
    portion_digest: str
    cpu_ns: int
    deadline_boot_ns: int


def _reservation(value):
    if type(value) is not Reservation:
        raise BudgetIntegrityError("exact accounting reservation required")
    for name in ("identity_digest", "reservation_digest", "portion_digest"):
        _digest(getattr(value, name), name)
    _integer(value.sequence, "reservation sequence", minimum=1, maximum=MAX_RECORDS - 1)
    _integer(value.cpu_ns, "portion CPU", minimum=1, maximum=PORTION_CPU_NS)
    _integer(value.deadline_boot_ns, "fixed deadline")


@dataclass(frozen=True)
class AccountingSnapshot:
    identity_digest: str
    journal_digest: str
    record_count: int
    settled_cpu_ns: int
    charged_cpu_ns: int
    remaining_cpu_ns: int
    deadline_boot_ns: int
    pending: Reservation | None
    status: str


class _State:
    def __init__(self, identity):
        self.identity = _identity(identity)
        self.identity_digest = _hash(self.identity)
        self.count, self.head, self.used = 0, _ZERO, 0
        self.pending, self.first_clock, self.last_clock = None, None, None
        self.offset_low, self.offset_high, self.deadline = None, None, None
        self.measurements = set()
        self.stopped = False

    def observe(self, sample):
        _clock(sample)
        low = sample.realtime_ns - sample.boot_after_ns
        high = sample.realtime_ns - sample.boot_before_ns
        if self.first_clock is None:
            _integer(sample.boot_before_ns + TOTAL_ELAPSED_NS, "fixed deadline")
            self.first_clock = replace(sample)
            self.deadline = sample.boot_before_ns + TOTAL_ELAPSED_NS
            self.offset_low, self.offset_high = low, high
        else:
            if (sample.boot_id != self.first_clock.boot_id
                    or sample.boot_before_ns < self.last_clock.boot_after_ns
                    or sample.realtime_ns < self.last_clock.realtime_ns):
                raise BudgetStopped("boot or clock rollback invalidates preparation")
            self.offset_low = max(self.offset_low, low)
            self.offset_high = min(self.offset_high, high)
            if self.offset_low > self.offset_high:
                raise BudgetStopped("realtime/boot clock discontinuity invalidates preparation")
        self.last_clock = replace(sample)
        if sample.boot_after_ns >= self.deadline:
            raise BudgetExceeded("the original preparation deadline has expired")

    def apply(self, record, digest):
        _closed(record, {"format", "version", "sequence", "previous", "event", "body"}, "journal record")
        if record["format"] != _FORMAT or type(record["format"]) is not str:
            raise BudgetIntegrityError("foreign preparation journal format")
        _integer(record["version"], "journal version", minimum=_VERSION, maximum=_VERSION)
        _integer(record["sequence"], "record sequence", maximum=MAX_RECORDS - 1)
        _digest(record["previous"], "previous record")
        if record["sequence"] != self.count or record["previous"] != self.head or self.stopped:
            raise BudgetIntegrityError("stale, reordered, or post-stop journal record")
        event, body = record["event"], record["body"]
        if type(event) is not str:
            raise BudgetIntegrityError("journal event must be text")
        if event == "init":
            _closed(body, {"identity", "clock", "total_cpu_ns", "portion_cpu_ns", "elapsed_ns"}, "initial record")
            _closed(body["identity"], self.identity, "bound identity")
            if self.count or body["identity"] != self.identity:
                raise BudgetIntegrityError("preparation identity mismatch or repeated initialization")
            for name, expected in (("total_cpu_ns", TOTAL_CPU_NS), ("portion_cpu_ns", PORTION_CPU_NS), ("elapsed_ns", TOTAL_ELAPSED_NS)):
                _integer(body[name], name, minimum=expected, maximum=expected)
            self.observe(_clock_from_dict(body["clock"]))
        elif not self.count:
            raise BudgetIntegrityError("journal has no initialization")
        elif event == "reserve":
            _closed(body, {"clock", "portion_digest", "cpu_ns"}, "reservation record")
            _digest(body["portion_digest"], "portion")
            _integer(body["cpu_ns"], "reserved CPU", minimum=1, maximum=PORTION_CPU_NS)
            if self.pending is not None:
                raise BudgetIntegrityError("an unresolved reservation already exists")
            self.observe(_clock_from_dict(body["clock"]))
            if self.used + body["cpu_ns"] > TOTAL_CPU_NS:
                raise BudgetExceeded("preparation cumulative CPU budget is exhausted")
            self.pending = Reservation(self.identity_digest, digest, self.count, body["portion_digest"], body["cpu_ns"], self.deadline)
        elif event == "settle-claim":
            _closed(body, {"clock", "reservation_digest", "cumulative_cpu_ns", "measurement_digest"}, "settlement claim")
            _digest(body["reservation_digest"], "settled reservation")
            _digest(body["measurement_digest"], "measurement claim")
            _integer(body["cumulative_cpu_ns"], "claimed cumulative CPU", maximum=TOTAL_CPU_NS)
            if self.pending is None or body["reservation_digest"] != self.pending.reservation_digest:
                raise BudgetIntegrityError("missing, stale, or already settled reservation")
            if body["measurement_digest"] in self.measurements:
                raise BudgetIntegrityError("measurement claim was already consumed")
            if not self.used <= body["cumulative_cpu_ns"] <= self.used + self.pending.cpu_ns:
                raise BudgetExceeded("CPU claim rolled back or exceeded its complete reservation")
            self.observe(_clock_from_dict(body["clock"]))
            self.used = body["cumulative_cpu_ns"]
            self.measurements.add(body["measurement_digest"])
            self.pending = None
        elif event == "stop":
            _closed(body, {"reason"}, "stop record")
            if type(body["reason"]) is not str or body["reason"] not in {"unmeasured", "budget-violation", "operator-stop", "clock-invalid"}:
                raise BudgetIntegrityError("unknown preparation stop reason")
            self.stopped = True
        else:
            raise BudgetIntegrityError("unknown preparation event")
        self.head, self.count = digest, self.count + 1

    def snapshot(self, recovered=False):
        pending = None if self.pending is None else replace(self.pending)
        charged = self.used + (0 if pending is None else pending.cpu_ns)
        status = "stopped" if self.stopped or recovered else "pending" if pending else "accounting-open"
        return AccountingSnapshot(self.identity_digest, self.head, self.count, self.used,
                                  charged, TOTAL_CPU_NS - charged, self.deadline, pending, status)


def _encode_record(state, event, body):
    record = {"format": _FORMAT, "version": _VERSION, "sequence": state.count,
              "previous": state.head, "event": event, "body": body}
    digest = _hash(record)
    line = _canonical({"record": record, "digest": digest}) + b"\n"
    if len(line) > MAX_RECORD_BYTES or state.count >= MAX_RECORDS:
        raise BudgetExceeded("bounded preparation journal is exhausted")
    return line


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BudgetIntegrityError("duplicate journal JSON key")
        result[key] = value
    return result


def _json_integer(value):
    if len(value) > 19:
        raise BudgetIntegrityError("journal integer encoding is not bounded")
    return int(value)


def _forbidden_number(_value):
    raise BudgetIntegrityError("journal numbers must be actual integer nanoseconds")


def _replay(data, identity):
    if type(data) is not bytes or not 0 < len(data) <= MAX_JOURNAL_BYTES or not data.endswith(b"\n"):
        raise BudgetIntegrityError("missing, empty, oversized, or partial existing journal")
    lines = data.splitlines(keepends=True)
    if len(lines) > MAX_RECORDS:
        raise BudgetIntegrityError("journal record count exceeds its bound")
    state = _State(identity)
    for line in lines:
        if len(line) > MAX_RECORD_BYTES or not line.endswith(b"\n"):
            raise BudgetIntegrityError("partial or oversized journal record")
        try:
            envelope = json.loads(line, object_pairs_hook=_pairs, parse_int=_json_integer,
                                  parse_float=_forbidden_number, parse_constant=_forbidden_number)
            _closed(envelope, {"record", "digest"}, "record envelope")
            if _canonical(envelope) + b"\n" != line:
                raise BudgetIntegrityError("journal encoding is not canonical")
            _digest(envelope["digest"], "record")
            if _hash(envelope["record"]) != envelope["digest"]:
                raise BudgetIntegrityError("journal record digest mismatch")
            state.apply(envelope["record"], envelope["digest"])
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise BudgetIntegrityError("malformed bounded preparation journal") from exc
    return state


class _FileJournal:
    """Real bounded descriptor I/O; native lock/namespace acquisition is separate."""
    def __init__(self, fd, directory_fd=None, name=None):
        self.fd, self.directory_fd, self.name = fd, directory_fd, name
        self.pid, self.closed, self.failed = os.getpid(), False, False
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_JOURNAL_BYTES:
            raise BudgetIntegrityError("journal must be a bounded regular single-link file")
        self.inode = info.st_dev, info.st_ino
        with _OWNERS_LOCK:
            if self.inode in _OWNERS:
                raise BudgetBusy("another in-process accounting owner holds this journal")
            _OWNERS.add(self.inode)
        self.expected = None

    def check(self):
        if self.closed or self.failed or self.pid != os.getpid():
            raise BudgetStopped("journal handle is closed, failed, or inherited by another process")
        info = os.fstat(self.fd)
        if (info.st_dev, info.st_ino) != self.inode or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise BudgetIntegrityError("held journal identity changed")
        if self.directory_fd is not None:
            link = os.stat(self.name, dir_fd=self.directory_fd, follow_symlinks=False)
            if not stat.S_ISREG(link.st_mode) or (link.st_dev, link.st_ino) != self.inode:
                raise BudgetIntegrityError("journal directory entry was replaced")
        if info.st_size > MAX_JOURNAL_BYTES:
            raise BudgetIntegrityError("journal file grew beyond its bound")
        return info

    def read(self):
        before = self.check()
        os.lseek(self.fd, 0, os.SEEK_SET)
        result = bytearray()
        while len(result) <= MAX_JOURNAL_BYTES:
            piece = os.read(self.fd, min(65536, MAX_JOURNAL_BYTES + 1 - len(result)))
            if not piece:
                break
            result.extend(piece)
        after = self.check()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(result) != after.st_size:
            raise BudgetIntegrityError("journal changed during bounded read")
        data = bytes(result)
        identity = len(data), hashlib.sha256(data).digest()
        if self.expected is not None and identity != self.expected:
            raise BudgetIntegrityError("held journal bytes changed outside this owner")
        self.expected = identity
        return data

    def append(self, line):
        if type(line) is not bytes or not 0 < len(line) <= MAX_RECORD_BYTES or not line.endswith(b"\n"):
            raise BudgetIntegrityError("invalid bounded journal append")
        before = self.read()
        if len(before) + len(line) > MAX_JOURNAL_BYTES:
            raise BudgetExceeded("complete preparation journal is full")
        try:
            os.lseek(self.fd, 0, os.SEEK_END)
            written = 0
            while written < len(line):
                count = os.write(self.fd, line[written:])
                if type(count) is not int or count <= 0:
                    raise OSError("journal write made no progress")
                written += count
            os.fsync(self.fd)
            if self.directory_fd is not None:
                os.fsync(self.directory_fd)
            self.expected = len(before) + len(line), hashlib.sha256(before + line).digest()
            self.read()
        except BaseException:
            self.failed = True
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                os.close(self.fd)
            finally:
                if self.directory_fd is not None:
                    os.close(self.directory_fd)
                with _OWNERS_LOCK:
                    _OWNERS.discard(self.inode)


def _native_file(directory_fd, identity, *, create):
    if sys.platform != "linux" or not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")):
        raise NativeBudgetUnavailable("durable native journal acquisition is Linux-only")
    import fcntl
    _integer(directory_fd, "directory descriptor")
    name = _hash(_identity(identity)) + ".jsonl"
    directory = os.dup(directory_fd)
    fd = None
    try:
        parent = os.fstat(directory)
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
            raise BudgetIntegrityError("held journal directory must be caller-owned and not group/world writable")
        flags = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        fd = os.open(name, flags, 0o600, dir_fd=directory)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BudgetBusy("another native accounting owner holds the journal") from exc
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise BudgetIntegrityError("journal is not private to its actual caller UID")
        return _FileJournal(fd, directory, name)
    except BaseException:
        if fd is not None:
            os.close(fd)
        os.close(directory)
        raise


class PreparationBudget:
    """Accounting handle, not a native launch/refund authorization capability."""
    def __init__(self):
        raise TypeError("use explicit create or open_existing")

    @classmethod
    def create(cls, directory_fd, identity):
        """Explicit new journal only; external registry must authorize first use."""
        return cls._attach(_native_file(directory_fd, identity, create=True), identity, create=True)

    @classmethod
    def open_existing(cls, directory_fd, identity):
        """Never create, reset, repair, or resume a recovered pending ticket."""
        return cls._attach(_native_file(directory_fd, identity, create=False), identity, create=False)

    @classmethod
    def _attach(cls, store, identity, *, create):
        # Shared protocol/I/O construction, not a public assurance toggle.
        handle = object.__new__(cls)
        handle._store = store
        handle._operation_lock = threading.Lock()
        handle._observed_clock = None
        handle._observed_offsets = None
        handle._recovered = False
        handle._clock_failed = False
        try:
            handle._identity = BudgetIdentity(**_identity(identity))
            data = store.read()
            if create:
                if data:
                    raise BudgetIntegrityError("new initialization cannot replace existing journal bytes")
                state = _State(handle._identity)
                body = {"identity": state.identity, "clock": _clock(_system_clock()),
                        "total_cpu_ns": TOTAL_CPU_NS, "portion_cpu_ns": PORTION_CPU_NS,
                        "elapsed_ns": TOTAL_ELAPSED_NS}
                line = _encode_record(state, "init", body)
                _replay(line, handle._identity)
                store.append(line)
            handle._state = _replay(store.read(), handle._identity)
            handle._recovered = not create and handle._state.pending is not None
            handle._check_time()
            return handle
        except BaseException:
            store.close()
            raise

    def _check_time(self):
        state = _replay(self._store.read(), self._identity)
        try:
            if self._observed_clock is not None:
                if self._observed_clock != state.last_clock:
                    state.observe(self._observed_clock)
                state.offset_low = max(state.offset_low, self._observed_offsets[0])
                state.offset_high = min(state.offset_high, self._observed_offsets[1])
                if state.offset_low > state.offset_high:
                    raise BudgetStopped("observed clock continuity was lost")
            state.observe(_system_clock())
            self._observed_clock = replace(state.last_clock)
            self._observed_offsets = state.offset_low, state.offset_high
        except BudgetError:
            self._clock_failed = True
            if not state.stopped and state.count < MAX_RECORDS:
                data = self._store.read()
                line = _encode_record(state, "stop", {"reason": "clock-invalid"})
                self._store.append(line)
                self._state = _replay(data + line, self._identity)
            raise
        return state.last_clock

    def _ready(self):
        self._store.check()
        self._state = _replay(self._store.read(), self._identity)
        if self._recovered or self._clock_failed or self._state.stopped:
            raise BudgetStopped("preparation is stopped; recovered reservations cannot be reused or refunded")
        return self._check_time()

    def _append(self, event, body):
        data = self._store.read()
        line = _encode_record(self._state, event, body)
        proposed = _replay(data + line, self._identity)
        try:
            self._store.append(line)
        except OSError as exc:
            raise BudgetIOError("journal append did not establish durability; no ticket is authorized") from exc
        self._state = proposed
        self._check_time()

    def _snapshot(self):
        self._store.check()
        self._state = _replay(self._store.read(), self._identity)
        return self._state.snapshot(self._recovered)

    @_exclusive
    def snapshot(self):
        """Historical accounting data, never a current permission to execute."""
        return self._snapshot()

    @_exclusive
    def reserve(self, portion_digest, cpu_ns):
        """Durably charge a whole possible portion before returning its ticket."""
        sample = self._ready()
        _digest(portion_digest, "portion")
        _integer(cpu_ns, "reserved CPU", minimum=1, maximum=PORTION_CPU_NS)
        if self._state.pending is not None:
            raise BudgetStopped("unresolved reservation prevents another portion")
        if self._state.count + 3 > MAX_RECORDS:
            raise BudgetExceeded("journal has no reserved settlement/stop capacity")
        self._append("reserve", {"clock": _clock(sample), "portion_digest": portion_digest, "cpu_ns": cpu_ns})
        return replace(self._state.pending)

    @_exclusive
    def settle_claim(self, reservation, *, cumulative_cpu_ns, measurement_digest):
        """Book a once-only cumulative complete-job CPU claim, NOT measurement proof.

The future trusted native owner must first establish a stopped/quiescent whole
process tree and authentic cumulative cost, including all retries and overhead.
No integer, digest, dataclass or successful return here establishes that fact.
The delta must fit this ticket; an unmeasurable/overrun job must stay stopped.
"""
        sample = self._ready()
        _reservation(reservation)
        if self._state.pending != reservation:
            raise BudgetIntegrityError("foreign, stale, changed, or already settled ticket")
        try:
            _integer(cumulative_cpu_ns, "claimed cumulative CPU", maximum=TOTAL_CPU_NS)
            _digest(measurement_digest, "measurement claim")
            if not self._state.used <= cumulative_cpu_ns <= self._state.used + reservation.cpu_ns:
                raise BudgetExceeded("claimed CPU rolled back or exceeded the reserved portion")
        except BudgetError:
            self._append("stop", {"reason": "budget-violation"})
            raise
        self._append("settle-claim", {"clock": _clock(sample),
                     "reservation_digest": reservation.reservation_digest,
                     "cumulative_cpu_ns": cumulative_cpu_ns, "measurement_digest": measurement_digest})
        return self._snapshot()

    @_exclusive
    def stop_unmeasured(self):
        """Stop without releasing any unknown reservation or inventing cost."""
        self._ready()
        self._append("stop", {"reason": "unmeasured"})
        return self._snapshot()

    @_exclusive
    def close(self):
        self._store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
