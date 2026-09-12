"""Independent timeout-faithful supervisor traces, NOT native Linux evidence.

No real fork, pidfd, signals, limits, process measurement, or worker code runs.
Unlike an always-ready selector or a clock advanced once per call, this model
charges the requested timeout when no descriptor is ready (also with zero FDs).
Terminal availability is scheduled by model time, not by a wait-call ordinal.
"""
import hashlib
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import context_preparation_supervisor as owner


PID = 47003
STOP = (19 << 8) | 0x7f
PENDING_BOUND_NS = 50_000_000  # Contract boundary, never derived from new short waits.


class TimedSelectorTrace:
    def __init__(self, directory, *, pipes="empty_before_pending", terminal_delay_ns=1_000_000,
                 oversleep_ns=0, wait_latency_ns=0, missing=True):
        self.directory, self.pipes = directory, pipes
        self.terminal_delay_ns = terminal_delay_ns
        self.oversleep_ns, self.wait_latency_ns = oversleep_ns, wait_latency_ns
        self.missing = missing
        self.now = self.cpu = 0
        self.pending_since = None
        self.fd = 70
        self.live = {}
        self.closed = []
        self.actions = []
        self.waits = self.proc_reads = self.selects = self.pipe_count = 0
        self.readbacks = 0
        self.killed = False
        self.reaped_at = None
        self.cleanup_unknown = False
        self.threads = "1"
        self.status_override = None
        self.exit_status = 0
        self.terminal_usage = SimpleNamespace(ru_utime=0.125, ru_stime=0.0625, ru_maxrss=8192)
        self.free_bytes = owner.FREE_BYTES + 1024**3
        self.pidfd = None

    def allocate(self, role):
        self.fd += 1
        self.live[self.fd] = role
        return self.fd

    def close(self, fd):
        assert fd in self.live, ("double/unowned close", fd)
        self.closed.append(fd)
        del self.live[fd]

    def pipe(self, flags):
        self.pipe_count += 1
        channel = "stdout" if self.pipe_count == 1 else "stderr"
        return self.allocate(channel), self.allocate(channel + "-writer")

    def open_pidfd(self, pid, flags):
        assert (pid, flags) == (PID, 0)
        self.pidfd = self.allocate("pidfd")
        return self.pidfd

    def terminal_time(self):
        if not self.missing:
            return self.terminal_delay_ns
        if self.pending_since is None:
            return None
        return self.pending_since + self.terminal_delay_ns

    def wait(self, pid, flags):
        assert pid == PID and flags in (1, 3)
        self.waits += 1
        assert self.waits < 512, "model safety bound, not a changed product deadline"
        self.actions.append(("wait", self.now, flags))
        if self.waits == 1:
            return PID, STOP, None
        if self.killed:
            if self.cleanup_unknown:
                raise ChildProcessError("modeled unknown reap")
            self.reaped_at = self.now
            return PID, 9, self.terminal_usage
        available = self.terminal_time()
        if available is not None and self.now >= available:
            self.now += self.wait_latency_ns
            self.reaped_at = self.now
            return PID, self.exit_status, self.terminal_usage
        return 0, 0, None

    def signal(self, fd, value):
        assert fd == self.pidfd
        self.actions.append(("signal", self.now, value))
        if value == 9:
            self.killed = True

    def status(self, path):
        assert path == f"/proc/{PID}/status"
        self.proc_reads += 1
        if self.proc_reads == 1 or not self.missing:
            return b"State:\tR (running)\nThreads:\t1\nVmHWM:\t4096 kB\n"
        assert self.proc_reads == 2, "later apparently healthy proc must not clear pending"
        self.pending_since = self.now
        if self.status_override is not None:
            return self.status_override
        return ("State:\tR (running)\nThreads:\t" + self.threads + "\n").encode("ascii")

    def readback(self, pid, uid, gid, cpu, file_size):
        assert (pid, uid, gid, cpu, file_size) == (PID, 701, 702, 300, 4096)
        self.readbacks += 1
        return owner.KernelReadback(pid, uid, gid, cpu, file_size, 1, 1024**2)

    def read(self, fd, maximum):
        assert self.live[fd] in {"stdout", "stderr"}
        assert 0 < maximum <= 65536
        return b""  # Real meaning modeled here: EOF, not an idle non-ready pipe.

    def selector(self):
        trace = self

        class Selector:
            def __init__(self):
                self.keys = {}

            def register(self, fd, event, data):
                self.keys[fd] = SimpleNamespace(fd=fd, data=data)

            def unregister(self, fd):
                del self.keys[fd]

            def get_map(self):
                return self.keys

            def select(self, timeout):
                trace.selects += 1
                assert trace.selects < 100, "modeled loop failed to finish"
                assert 0 < timeout <= 0.05
                before = trace.now
                count = len(self.keys)
                if self.keys and (
                    trace.pipes == "empty_before_pending" or
                    trace.pipes == "eof_after_pending" and trace.pending_since is not None
                ):
                    elapsed = 0  # EOF is ready: actual select need not use its timeout.
                elif self.keys and trace.pipes == "open_until_terminal" and trace.terminal_time() is not None:
                    elapsed = min(math.ceil(timeout * 10**9), max(0, trace.terminal_time() - trace.now))
                else:
                    # Empty selector still sleeps. Scheduling oversleep counts too.
                    elapsed = math.ceil(timeout * 10**9)
                trace.now += elapsed + (trace.oversleep_ns if elapsed else 0)
                trace.actions.append(("select", before, trace.now, timeout, count))
                ready = (trace.pipes != "eof_after_pending" or trace.pending_since is not None)
                if trace.pipes == "open_until_terminal":
                    ready = trace.terminal_time() is not None and trace.now >= trace.terminal_time()
                return [(key, 1) for key in tuple(self.keys.values())] if ready else []

            def close(self):
                self.keys.clear()

        return Selector()

    def install(self, monkeypatch):
        def exitcode(status):
            return status >> 8 if status & 0x7f == 0 else -(status & 0x7f)

        monkeypatch.setattr(owner, "os", SimpleNamespace(
            dup=lambda _: self.allocate("workspace"), close=self.close,
            fstat=lambda _: self.directory.lstat(), pipe2=self.pipe,
            open=lambda *_: self.allocate("null"), fork=lambda: PID,
            pidfd_open=self.open_pidfd, wait4=self.wait, read=self.read,
            set_blocking=lambda *_: None, O_CLOEXEC=0, O_RDONLY=0,
            WNOHANG=1, WUNTRACED=2,
            WIFSTOPPED=lambda value: value & 0xff == 0x7f,
            WSTOPSIG=lambda value: value >> 8,
            WIFEXITED=lambda value: value & 0x7f == 0,
            WIFSIGNALED=lambda value: 0 < value & 0x7f < 0x7f,
            waitstatus_to_exitcode=exitcode,
        ))
        monkeypatch.setattr(owner, "signal", SimpleNamespace(
            SIGSTOP=19, SIGCONT=18, SIGKILL=9, pidfd_send_signal=self.signal))
        monkeypatch.setattr(owner, "time", SimpleNamespace(
            CLOCK_BOOTTIME=77, clock_gettime_ns=lambda _: self.now,
            process_time_ns=lambda: self.now // 100,
            monotonic=lambda: self.now / 10**9,
            sleep=lambda seconds: setattr(self, "now", self.now + math.ceil(seconds * 10**9)),
        ))
        monkeypatch.setattr(owner, "selectors", SimpleNamespace(DefaultSelector=self.selector, EVENT_READ=1))
        monkeypatch.setattr(owner, "_require_native_owner", lambda: None)
        monkeypatch.setattr(owner, "_kernel_readback", self.readback)
        monkeypatch.setattr(owner, "_free", lambda _: self.free_bytes)
        monkeypatch.setattr(owner, "_read_small", self.status)
        monkeypatch.setitem(sys.modules, "context_preparation_process_guard", SimpleNamespace())

    def run(self, *, wall=300):
        return owner.run_single_process((str(self.directory / "modeled-worker.py"),),
            uid=701, gid=702, cwd=self.directory, workspace_fd=7,
            file_size_bytes=4096, cpu_seconds=300, wall_seconds=wall)


@pytest.mark.parametrize("pipes", ["empty_before_pending", "eof_after_pending"])
@pytest.mark.parametrize("oversleep_ns", [0, 2_799_507])
def test_early_terminal_child_after_pipe_eof_is_not_delayed_to_pending_deadline(
        tmp_path, monkeypatch, pipes, oversleep_ns, record_property):
    model = TimedSelectorTrace(tmp_path, pipes=pipes, oversleep_ns=oversleep_ns)
    model.install(monkeypatch)
    result = model.run()
    record_property("supervisor_sha256", hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest())
    record_property("selector_trace", repr(model.actions))
    assert result.exit_code == 0
    assert model.pending_since is not None
    assert any(action[0] == "select" and action[4] == 0 for action in model.actions)
    assert model.reaped_at - model.pending_since < PENDING_BOUND_NS
    assert result.stop_reason is None
    assert not model.killed and not model.live


@pytest.mark.parametrize("terminal_delay_ns", [1, 5_000_000, 5_000_001, 19_000_000, 44_000_000, 45_000_000])
def test_repeated_short_polls_keep_the_first_pending_deadline(tmp_path, monkeypatch, terminal_delay_ns):
    model = TimedSelectorTrace(tmp_path, terminal_delay_ns=terminal_delay_ns)
    model.install(monkeypatch)
    result = model.run()
    polls = [action[3] for action in model.actions if action[0] == "select"]
    assert polls[0] == 0.05  # The healthy observation still uses the ordinary poll.
    assert all(timeout == 0.005 for timeout in polls[1:])
    assert model.reaped_at == math.ceil(terminal_delay_ns / 5_000_000) * 5_000_000
    assert model.pending_since == 0 and model.proc_reads == 2
    assert result.stop_reason is None and not model.killed and not model.live
    assert result.child_cpu_ns == 187_500_000
    assert result.peak_rss_bytes == 8192 * 1024


def test_healthy_child_keeps_normal_poll_even_with_empty_selector(tmp_path, monkeypatch):
    model = TimedSelectorTrace(tmp_path, missing=False, terminal_delay_ns=10_000_000)
    model.install(monkeypatch)
    result = model.run()
    polls = [action for action in model.actions if action[0] == "select"]
    assert any(action[4] == 0 and action[2] - action[1] == PENDING_BOUND_NS for action in polls)
    assert all(action[3] == 0.05 for action in polls)
    assert model.pending_since is None and result.stop_reason is None
    assert model.readbacks == 1 and not model.killed and not model.live


@pytest.mark.parametrize("terminal_delay_ns", [0, 1, 1_000_000, 4_999_999])
def test_realistic_pipe_eof_wakes_select_before_its_requested_timeout(tmp_path, monkeypatch, terminal_delay_ns):
    model = TimedSelectorTrace(tmp_path, pipes="open_until_terminal", terminal_delay_ns=terminal_delay_ns)
    model.install(monkeypatch)
    result = model.run()
    assert model.pending_since == 50_000_000
    assert model.reaped_at - model.pending_since == terminal_delay_ns
    assert result.stop_reason is None and not model.live


@pytest.mark.parametrize("terminal_delay_ns", [45_000_001, 49_999_999, 50_000_000, 50_000_001, 60_000_000, 10**12])
def test_terminal_observed_at_or_after_fifty_ms_remains_stop(tmp_path, monkeypatch, terminal_delay_ns):
    model = TimedSelectorTrace(tmp_path, terminal_delay_ns=terminal_delay_ns)
    model.install(monkeypatch)
    result = model.run()
    # A child available just below 50 ms may first be observed at 50 ms. It must
    # still STOP: the fix does not invent an earlier terminal observation.
    assert model.reaped_at - model.pending_since == PENDING_BOUND_NS
    assert result.stop_reason == "rss_observation_lost"
    assert model.killed == (terminal_delay_ns > PENDING_BOUND_NS)
    assert model.proc_reads == 2 and model.pending_since == 0 and not model.live


@pytest.mark.parametrize("oversleep_ns,reason", [
    (44_999_999, None),
    (45_000_000, "rss_observation_lost"),
    (45_000_001, "rss_observation_lost"),
    (1_000_000_000, "measurement_gap"),
])
def test_scheduler_oversleep_is_not_subtracted_from_real_observation_gap(
        tmp_path, monkeypatch, oversleep_ns, reason):
    model = TimedSelectorTrace(tmp_path, oversleep_ns=oversleep_ns)
    model.install(monkeypatch)
    result = model.run()
    assert model.reaped_at - model.pending_since == 5_000_000 + oversleep_ns
    assert result.stop_reason == reason and not model.live


@pytest.mark.parametrize("wait_latency_ns,reason", [
    (44_999_999, None),
    (45_000_000, "rss_observation_lost"),
    (45_000_001, "rss_observation_lost"),
])
def test_actual_wait4_return_time_still_binds_pending_not_pre_wait_timestamp(
        tmp_path, monkeypatch, wait_latency_ns, reason):
    model = TimedSelectorTrace(tmp_path, wait_latency_ns=wait_latency_ns)
    model.install(monkeypatch)
    result = model.run()
    assert model.reaped_at - model.pending_since == 5_000_000 + wait_latency_ns
    assert result.stop_reason == reason and not model.live


def test_pending_does_not_restart_original_wall_deadline(tmp_path, monkeypatch):
    model = TimedSelectorTrace(tmp_path, pipes="eof_after_pending", oversleep_ns=940_000_000)
    model.install(monkeypatch)
    result = model.run(wall=1)
    assert model.pending_since == 990_000_000
    assert result.elapsed_ns == 1_935_000_000
    assert result.maximum_sample_gap_ns == 990_000_000
    assert result.stop_reason == "wall_limit" and not model.live


@pytest.mark.parametrize("threads", ["0", "2", "unknown"])
def test_missing_rss_and_thread_violation_still_stops_immediately(tmp_path, monkeypatch, threads):
    model = TimedSelectorTrace(tmp_path)
    model.threads = threads
    model.install(monkeypatch)
    result = model.run()
    assert result.stop_reason == "kernel_task_count" and model.killed
    assert not any(action[0] == "select" and action[3] == 0.005 for action in model.actions)
    assert model.proc_reads == 2 and not model.live


@pytest.mark.parametrize("rss_kib,reason", [
    (1024**2 - 1, None), (1024**2, "rss_limit"), (1024**2 + 1, "rss_limit"),
])
def test_early_terminal_still_requires_original_terminal_rss_bound(tmp_path, monkeypatch, rss_kib, reason):
    model = TimedSelectorTrace(tmp_path)
    model.terminal_usage.ru_maxrss = rss_kib
    model.install(monkeypatch)
    result = model.run()
    assert result.peak_rss_bytes == rss_kib * 1024
    assert result.stop_reason == reason and not model.live


@pytest.mark.parametrize("rss_kib", [0, -1, True, 1.0, "8192", None])
def test_bad_terminal_rss_still_errors_after_reap_without_fake_measurement(tmp_path, monkeypatch, rss_kib):
    model = TimedSelectorTrace(tmp_path)
    model.terminal_usage.ru_maxrss = rss_kib
    model.install(monkeypatch)
    with pytest.raises(owner.NativeSupervisorError, match="terminal RSS KiB"):
        model.run()
    assert model.reaped_at == 5_000_000 and not model.killed and not model.live


@pytest.mark.parametrize("cpu_seconds,reason", [(300.0, None), (300.000000001, "cpu_limit")])
def test_pending_does_not_relax_terminal_cpu_bound(tmp_path, monkeypatch, cpu_seconds, reason):
    model = TimedSelectorTrace(tmp_path)
    model.terminal_usage.ru_utime, model.terminal_usage.ru_stime = cpu_seconds, 0.0
    model.install(monkeypatch)
    result = model.run()
    assert result.child_cpu_ns == math.ceil(cpu_seconds * 10**9)
    assert result.stop_reason == reason and not model.live


def test_unknown_cleanup_retains_original_pidfd_custody_without_success(tmp_path, monkeypatch):
    model = TimedSelectorTrace(tmp_path, terminal_delay_ns=10**12)
    model.cleanup_unknown = True
    model.install(monkeypatch)
    with pytest.raises(owner.UnreapedChild) as caught:
        model.run()
    assert caught.value.pid == PID and caught.value.pidfd == model.pidfd
    assert model.killed and model.reaped_at is None
    assert model.now == PENDING_BOUND_NS and model.pending_since == 0
    assert model.live == {model.pidfd: "pidfd"}
    assert model.proc_reads == 2
