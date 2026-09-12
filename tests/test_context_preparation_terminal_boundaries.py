"""Portable independent terminal-boundary traces; no native Linux/fork/guard execution."""
from dataclasses import dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "terminal_boundaries_review_owner", ROOT / "context_preparation_supervisor.py")
subject = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = subject
SPEC.loader.exec_module(subject)

PID = 52007
STOP = (19 << 8) | 0x7f
LIVE = (0, 0, None)
MISSING = b"Name:\tfixture\nState:\tR (running)\nThreads:\t1\n"
HEALTHY = MISSING + b"VmHWM:\t8192 kB\n"


def usage(*, user=0.125, system=0.0625, rss=2048):
    return SimpleNamespace(ru_utime=user, ru_stime=system, ru_maxrss=rss)


@dataclass
class WaitEvent:
    pid: int = PID
    status: int = 0
    resource: object = None


class Trace:
    """All privileged/process/pipe/clock boundaries are expressly modeled.

    This model has its own Unix-shaped wait-status encoding and time advancing
    only at declared select/sleep boundaries; it does not import owner tests.
    Existing directory lstat is the only filesystem operation in the run.
    """
    def __init__(self, directory, *, events=None, records=None, delays=None,
                 terminal=None, initial_rss=1024 * 1024):
        self.directory = directory
        self.terminal = usage() if terminal is None else terminal
        self.events = list(events if events is not None else
                           [WaitEvent(status=STOP), WaitEvent(resource=self.terminal)])
        self.records = list(records if records is not None else [MISSING])
        self.delays = list(delays if delays is not None else [10_000_000])
        self.now = self.cpu = self.fd_number = 0
        self.live_fds, self.closed_fds, self.actions = {}, [], []
        self.wait_calls = self.proc_reads = self.select_calls = self.readbacks = 0
        self.wait_advances = {}
        self.poll_timeouts = []
        self.started = False
        self.killed = False
        self.cleanup_mode = None
        self.cleanup_exit = 9
        self.initial_rss = initial_rss
        self.initial_error = None
        self.output = b"bounded complete fixture\n"
        self.error_output = b""
        self.free_values = []
        self.pipe_count = 0
        self.pidfd = None

    def allocate(self, role):
        self.fd_number += 1
        fd = 70 + self.fd_number
        self.live_fds[fd] = role
        self.actions.append(("allocate", role, fd))
        return fd

    def close(self, fd):
        assert fd in self.live_fds, ("unexpected double close", fd)
        self.actions.append(("close", self.live_fds[fd], fd))
        self.closed_fds.append(fd)
        del self.live_fds[fd]

    def pipe(self, _flags):
        self.pipe_count += 1
        role = "stdout" if self.pipe_count == 1 else "stderr"
        return self.allocate(role), self.allocate(role + "-writer")

    def get_pidfd(self, pid, flags):
        assert (pid, flags) == (PID, 0)
        self.pidfd = self.allocate("pidfd")
        return self.pidfd

    def wait(self, pid, flags):
        assert pid == PID
        self.wait_calls += 1
        assert self.wait_calls < 200, "independent trace safety bound reached"
        self.actions.append(("wait", pid, flags, self.now))
        self.now += self.wait_advances.get(self.wait_calls, 0)
        if self.killed:
            # Output overflow signals immediately; the next ordinary loop may
            # reap before entering cleanup. Both calls are nonblocking waits.
            assert flags in (1, 3)
            if self.cleanup_mode == "exception":
                raise ChildProcessError("modeled terminal wait unavailable")
            if self.cleanup_mode == "foreign":
                return PID + 1, 0, self.terminal
            if self.cleanup_mode == "never":
                return LIVE
            return PID, self.cleanup_exit, self.terminal
        if not self.events:
            return LIVE
        event = self.events.pop(0)
        if event is None:
            return LIVE
        if isinstance(event, BaseException):
            raise event
        return event.pid, event.status, event.resource

    def signal(self, fd, value):
        assert fd == self.pidfd
        self.actions.append(("signal", fd, value, self.now))
        if value == 9:
            self.killed = True

    def status(self, path):
        assert path == f"/proc/{PID}/status"
        assert self.readbacks == 1, "no proc-running sample before stopped readback"
        self.proc_reads += 1
        self.actions.append(("proc", self.now))
        if not self.records:
            raise AssertionError("a later status must not clear pending RSS")
        record = self.records.pop(0)
        if isinstance(record, BaseException):
            raise record
        return record

    def readback(self, pid, uid, gid, cpu_seconds, file_size_bytes):
        assert (pid, uid, gid, cpu_seconds, file_size_bytes) == (PID, 711, 712, 300, 4096)
        self.readbacks += 1
        self.actions.append(("stopped-readback", self.now))
        if self.initial_error:
            raise self.initial_error
        return subject.KernelReadback(pid, uid, gid, cpu_seconds, file_size_bytes, 1, self.initial_rss)

    def clock(self, kind):
        assert kind == 77
        return self.now

    def parent_cpu(self):
        self.cpu += 123
        return self.cpu

    def pause(self, seconds):
        self.now += math.ceil(seconds * 10**9)

    def free(self, fd):
        assert self.live_fds[fd] == "directory"
        return self.free_values.pop(0) if self.free_values else subject.FREE_BYTES + 512 * 1024**2

    def read(self, fd, maximum):
        role = self.live_fds[fd]
        assert role in {"stdout", "stderr"}
        source = self.output if role == "stdout" else self.error_output
        result = source[:maximum]
        if role == "stdout":
            self.output = source[len(result):]
        else:
            self.error_output = source[len(result):]
        self.actions.append(("read", role, len(result), maximum))
        return result

    def make_selector(self):
        trace = self

        class Selector:
            def __init__(self):
                self.keys = {}
            def register(self, fd, _event, channel):
                self.keys[fd] = SimpleNamespace(fd=fd, data=channel)
            def unregister(self, fd):
                self.keys.pop(fd)
            def get_map(self):
                return self.keys
            def select(self, timeout):
                trace.select_calls += 1
                trace.poll_timeouts.append(timeout)
                trace.now += trace.delays.pop(0) if trace.delays else 10_000_000
                trace.actions.append(("select", timeout, trace.now))
                return [(key, 1) for key in tuple(self.keys.values())]
            def close(self):
                self.keys.clear()

        return Selector()

    def install(self, monkeypatch):
        def exitcode(status):
            if status & 0x7f == 0:
                return status >> 8
            if 0 < status & 0x7f < 0x7f:
                return -(status & 0x7f)
            raise ValueError("modeled nonterminal wait status")

        monkeypatch.setattr(subject, "os", SimpleNamespace(
            dup=lambda _fd: self.allocate("directory"), close=self.close,
            fstat=lambda _fd: self.directory.lstat(), pipe2=self.pipe,
            open=lambda *_args: self.allocate("null"), fork=lambda: PID,
            pidfd_open=self.get_pidfd, wait4=self.wait, read=self.read,
            set_blocking=lambda *_args: None, O_CLOEXEC=0, O_RDONLY=0,
            WNOHANG=1, WUNTRACED=2,
            WIFSTOPPED=lambda status: status & 0xff == 0x7f,
            WSTOPSIG=lambda status: status >> 8,
            WIFEXITED=lambda status: status & 0x7f == 0,
            WIFSIGNALED=lambda status: 0 < status & 0x7f < 0x7f,
            waitstatus_to_exitcode=exitcode,
        ))
        monkeypatch.setattr(subject, "signal", SimpleNamespace(
            SIGSTOP=19, SIGCONT=18, SIGKILL=9, pidfd_send_signal=self.signal))
        monkeypatch.setattr(subject, "time", SimpleNamespace(
            CLOCK_BOOTTIME=77, clock_gettime_ns=self.clock, process_time_ns=self.parent_cpu,
            monotonic=lambda: self.now / 10**9, sleep=self.pause))
        monkeypatch.setattr(subject, "selectors", SimpleNamespace(
            DefaultSelector=self.make_selector, EVENT_READ=1))
        monkeypatch.setattr(subject, "_require_native_owner", lambda: None)
        monkeypatch.setattr(subject, "_kernel_readback", self.readback)
        monkeypatch.setattr(subject, "_free", self.free)
        monkeypatch.setattr(subject, "_read_small", self.status)
        monkeypatch.setitem(sys.modules, "context_preparation_process_guard", SimpleNamespace())

    def run(self, wall=300):
        return subject.run_single_process((str(self.directory / "sealed.py"), "fixture"),
            uid=711, gid=712, cwd=self.directory, workspace_fd=17,
            file_size_bytes=4096, cpu_seconds=300, wall_seconds=wall)


@pytest.mark.parametrize("state", [b"R (running)", b"S (sleeping)", b"D (disk sleep)", b"I (idle)"])
def test_missing_rss_known_single_task_then_same_child_terminal(trace_factory, state):
    trace = trace_factory(records=[b"State:\t" + state + b"\nThreads:\t1\n"])
    result = trace.run()
    assert result.stop_reason is None and result.exit_code == 0
    assert result.child_cpu_ns == 187_500_000
    assert result.parent_cpu_ns == 123
    assert result.peak_rss_bytes == 2048 * 1024
    assert result.elapsed_ns == 20_000_000
    assert result.maximum_sample_gap_ns == 10_000_000
    assert result.kernel_readback.pid == PID
    assert result.kernel_readback.uid == 711 and result.kernel_readback.gid == 712
    assert result.minimum_free_bytes == subject.FREE_BYTES + 512 * 1024**2
    assert result.stdout_prefix == b"bounded complete fixture\n"
    assert result.observed_output_bytes == len(result.stdout_prefix)
    expected_hash = hashlib.sha256(b"O" + len(result.stdout_prefix).to_bytes(4, "big") + result.stdout_prefix)
    assert result.output_digest == expected_hash.hexdigest()
    assert trace.poll_timeouts == [0.05, 0.05]
    assert trace.proc_reads == 1 and not trace.killed and not trace.live_fds


@pytest.fixture
def trace_factory(tmp_path, monkeypatch):
    def build(**kwargs):
        trace = Trace(tmp_path, **kwargs)
        trace.install(monkeypatch)
        return trace
    return build


def test_original_high_water_and_pending_cannot_be_cleared_by_healthy_proc(trace_factory):
    trace = trace_factory(events=[WaitEvent(status=STOP), None, None, WaitEvent(resource=usage())],
        records=[HEALTHY, MISSING, HEALTHY], delays=[10_000_000, 10_000_000, 10_000_000])
    result = trace.run()
    assert result.stop_reason is None and result.peak_rss_bytes == 8192 * 1024
    assert trace.proc_reads == 2 and trace.records == [HEALTHY]
    assert not trace.live_fds


@pytest.mark.parametrize("elapsed", [0, 49_999_999])
def test_terminal_at_no_more_than_declared_poll_boundary(trace_factory, elapsed):
    trace = trace_factory(delays=[elapsed])
    result = trace.run()
    assert result.stop_reason is None and not trace.live_fds


@pytest.mark.parametrize("elapsed", [50_000_000, 50_000_001, 100_000_000, 999_999_999])
def test_terminal_after_declared_pending_bound_must_not_be_success(trace_factory, elapsed):
    trace = trace_factory(delays=[elapsed])
    result = trace.run()
    assert result.stop_reason == "rss_observation_lost", (elapsed, result)
    assert not trace.live_fds


@pytest.mark.parametrize("threads", [b"2", b"999"])
def test_absent_rss_does_not_erase_observed_thread_guard_violation(trace_factory, threads):
    trace = trace_factory(records=[b"State:\tR (running)\nThreads:\t" + threads + b"\n"])
    result = trace.run()
    assert result.stop_reason == "kernel_task_count"
    assert not trace.live_fds


def test_known_thread_violation_with_rss_still_stops(trace_factory):
    trace = trace_factory(records=[b"State:\tR\nThreads:\t2\nVmHWM:\t1024 kB\n"])
    assert trace.run().stop_reason == "kernel_task_count"
    assert trace.killed and not trace.live_fds


@pytest.mark.parametrize("cleanup_exit", [0, 9, 23 << 8])
def test_persistent_missing_sample_stops_even_if_cleanup_returns_normal_exit(trace_factory, cleanup_exit):
    trace = trace_factory(events=[WaitEvent(status=STOP), None], delays=[50_000_000])
    trace.cleanup_exit = cleanup_exit
    result = trace.run()
    assert result.stop_reason == "rss_observation_lost"
    assert result.child_cpu_ns == 187_500_000 and trace.killed
    assert trace.proc_reads == 1 and not trace.live_fds


@pytest.mark.parametrize("rss", [1024**2 - 1, 1024**2, 1024**2 + 1])
def test_terminal_rss_boundary_is_not_relaxed_by_exit_race(trace_factory, rss):
    trace = trace_factory(terminal=usage(rss=rss))
    result = trace.run()
    assert result.peak_rss_bytes == rss * 1024
    assert result.stop_reason == (None if rss < 1024**2 else "rss_limit")
    assert not trace.live_fds


@pytest.mark.parametrize("resource", [usage(rss=0), usage(rss=False), usage(rss="2048"),
    usage(rss=1.0), usage(user=float("nan")), usage(user=True), usage(system=-1)])
def test_malformed_terminal_usage_is_error_after_reap_not_a_guess(trace_factory, resource):
    trace = trace_factory(terminal=resource)
    with pytest.raises(subject.NativeSupervisorError):
        trace.run()
    assert not trace.killed and not trace.live_fds
    assert trace.wait_calls == 2


@pytest.mark.parametrize("rss", [b"x kB", b"0 kB", b"-1 kB", b"1 MB", b"1 KB", b"1.5 kB"])
def test_present_bad_rss_still_fails_without_pending(trace_factory, rss):
    trace = trace_factory(records=[MISSING + b"VmHWM:\t" + rss + b"\n"])
    with pytest.raises(subject.NativeSupervisorError):
        trace.run()
    assert trace.killed and not trace.live_fds
    assert trace.select_calls == 0


@pytest.mark.parametrize("resource_error", [FileNotFoundError("fixture disappearing proc"),
    PermissionError("fixture denied proc"), OSError("fixture I/O error")])
def test_unreadable_status_is_not_the_narrow_absent_field_case(trace_factory, resource_error):
    trace = trace_factory(records=[resource_error])
    with pytest.raises(type(resource_error)):
        trace.run()
    assert trace.killed and not trace.live_fds


def test_no_stopped_readback_is_not_repaired_by_terminal_rusage(trace_factory):
    trace = trace_factory(events=[WaitEvent(resource=usage())], records=[])
    result = trace.run()
    assert result.stop_reason == "launch_unverified"
    assert result.kernel_readback is None and trace.proc_reads == 0
    assert not trace.live_fds


def test_initial_readback_error_must_not_enter_pending(trace_factory):
    trace = trace_factory()
    trace.initial_error = subject.NativeSupervisorError("missing initial stopped RSS")
    with pytest.raises(subject.NativeSupervisorError, match="initial"):
        trace.run()
    assert trace.proc_reads == 0 and trace.killed and not trace.live_fds


def test_foreign_terminal_pid_never_resolves_owned_pending_observation(trace_factory):
    trace = trace_factory(events=[WaitEvent(status=STOP), WaitEvent(pid=PID + 1, resource=usage())])
    with pytest.raises(subject.NativeSupervisorError, match="owned child"):
        trace.run()
    assert trace.killed and not trace.live_fds


@pytest.mark.parametrize("cleanup", ["exception", "foreign", "never"])
def test_uncertain_cleanup_transfers_same_original_pidfd_and_no_success(trace_factory, cleanup):
    trace = trace_factory(events=[WaitEvent(status=STOP), None], delays=[50_000_000])
    trace.cleanup_mode = cleanup
    with pytest.raises(subject.UnreapedChild) as caught:
        trace.run()
    assert caught.value.pid == PID and caught.value.pidfd == trace.pidfd
    assert trace.live_fds == {trace.pidfd: "pidfd"}
    assert trace.pidfd not in trace.closed_fds


@pytest.mark.parametrize("status,reason", [(8 << 8, "nonzero_exit"), (9, "signal_exit")])
def test_terminal_outcome_preserved_during_rss_recovery(trace_factory, status, reason):
    trace = trace_factory(events=[WaitEvent(status=STOP), WaitEvent(status=status, resource=usage())])
    assert trace.run().stop_reason == reason
    assert not trace.live_fds


def test_original_wall_deadline_not_restarted_by_pending(trace_factory):
    trace = trace_factory(delays=[1_000_000_000])
    result = trace.run(wall=1)
    assert result.stop_reason == "wall_limit"
    assert result.elapsed_ns >= 10**9 and not trace.live_fds


def test_gap_limit_not_repaired_by_terminal_measurement(trace_factory):
    trace = trace_factory(delays=[1_000_000_001])
    result = trace.run()
    assert result.stop_reason == "measurement_gap"
    assert result.maximum_sample_gap_ns == 1_000_000_001 and not trace.live_fds


def test_clock_rollback_during_pending_never_succeeds(trace_factory):
    trace = trace_factory(delays=[-1])
    assert trace.run().stop_reason == "measurement_gap"
    assert not trace.live_fds


def test_free_reserve_loss_remains_a_stop_during_terminal_recovery(trace_factory):
    trace = trace_factory()
    trace.free_values = [subject.FREE_BYTES, subject.FREE_BYTES, subject.FREE_BYTES - 1]
    result = trace.run()
    assert result.stop_reason == "free_space"
    assert result.minimum_free_bytes == subject.FREE_BYTES - 1
    assert not trace.live_fds


def test_pending_rss_does_not_disable_bounded_output_accounting(trace_factory):
    trace = trace_factory(events=[WaitEvent(status=STOP)], delays=[1] * 100)
    trace.output = b"x" * (subject.OUTPUT_BYTES + 100)
    result = trace.run()
    assert result.stop_reason == "output_limit"
    assert result.observed_output_bytes == subject.OUTPUT_BYTES + 1
    assert len(result.stdout_prefix) == subject.OUTPUT_BYTES and not trace.live_fds


def test_more_cpu_than_worker_limit_during_exit_still_stops(trace_factory):
    trace = trace_factory(terminal=usage(user=300, system=0.000000001))
    result = trace.run()
    assert result.stop_reason == "cpu_limit" and result.child_cpu_ns == 300_000_000_001
    assert not trace.live_fds


@pytest.mark.parametrize("inside_wait_ns", [40_000_000, 40_000_001, 200_000_000])
def test_terminal_wait_latency_counts_in_same_pending_boundary(trace_factory, inside_wait_ns):
    trace = trace_factory(delays=[10_000_000])
    trace.wait_advances[2] = inside_wait_ns
    result = trace.run()
    assert result.stop_reason == "rss_observation_lost"
    assert result.elapsed_ns == 10_000_000 + inside_wait_ns
    assert not trace.killed and not trace.live_fds


def test_terminal_clock_rollback_after_wait_does_not_resolve_pending(trace_factory):
    trace = trace_factory(delays=[10_000_000])
    trace.wait_advances[2] = -10_000_001
    result = trace.run()
    assert result.stop_reason == "rss_observation_lost"
    assert not trace.killed and not trace.live_fds


@pytest.mark.parametrize("threads", [b"0", b"1 2", b"unknown", None])
def test_missing_rss_keeps_all_other_exact_thread_checks(trace_factory, threads):
    raw = b"State:\tR\n" + (b"" if threads is None else b"Threads:\t" + threads + b"\n")
    trace = trace_factory(records=[raw])
    assert trace.run().stop_reason == "kernel_task_count"
    assert trace.killed and not trace.live_fds


def test_later_healthy_sample_cannot_repair_nonterminal_pending(trace_factory):
    trace = trace_factory(events=[WaitEvent(status=STOP), None, None],
        records=[MISSING, HEALTHY], delays=[20_000_000, 30_000_000])
    assert trace.run().stop_reason == "rss_observation_lost"
    assert trace.records == [HEALTHY] and trace.proc_reads == 1
    assert trace.killed and not trace.live_fds


def test_second_stop_does_not_become_terminal_recovery(trace_factory):
    trace = trace_factory(events=[WaitEvent(status=STOP), WaitEvent(status=STOP)])
    assert trace.run().stop_reason == "unexpected_stop"
    assert trace.readbacks == 1 and trace.killed and not trace.live_fds
