"""Portable deterministic exit-mm/wait4 races; these are not Linux evidence."""
from types import SimpleNamespace
import sys

import pytest

import context_preparation_supervisor as owner


class ExitModel:
    def __init__(self, directory, *, terminal_at=3, rss=4096, raw=None):
        self.directory = directory
        self.terminal_at, self.rss = terminal_at, rss
        self.raw = b"State:\tR (running)\nThreads:\t1\n" if raw is None else raw
        self.fd = 40
        self.live, self.closed, self.signals = {}, [], []
        self.waits = self.clock = self.samples = 0
        self.killed = False
        self.output = b"complete\n"
        self.usage = SimpleNamespace(ru_utime=0.2, ru_stime=0.1, ru_maxrss=rss)

    def new_fd(self, kind):
        self.fd += 1
        self.live[self.fd] = kind
        return self.fd

    def close(self, fd):
        assert fd in self.live
        self.closed.append(fd)
        del self.live[fd]

    def pipe(self, _flags):
        name = "stdout" if "stdout" not in self.live.values() else "stderr"
        return self.new_fd(name), self.new_fd("write")

    def wait(self, pid, _flags):
        assert pid == 900
        self.waits += 1
        assert self.waits < 100, "test observation bound, not a supervisor timeout"
        if self.killed:
            return pid, -9, self.usage
        if self.waits == 1:
            return pid, 19, self.usage  # Actual SIGSTOP is only modeled here.
        if self.waits >= self.terminal_at:
            return pid, 0, self.usage
        return 0, 0, None

    def signal(self, _fd, value):
        self.signals.append(value)
        self.killed |= value == 9

    def now(self, _clock):
        self.clock += 5_000_000
        return self.clock

    def read(self, fd, maximum):
        if self.live[fd] == "stdout":
            value, self.output = self.output[:maximum], self.output[maximum:]
            return value
        return b""

    def status(self, _path):
        self.samples += 1
        if self.samples == 1:
            return b"State:\tR (running)\nThreads:\t1\nVmHWM:\t1024 kB\n"
        return self.raw

    def install(self, monkeypatch):
        model = self

        class Selector:
            def __init__(self):
                self.keys = {}
            def register(self, fd, _events, data):
                self.keys[fd] = SimpleNamespace(fd=fd, data=data)
            def unregister(self, fd):
                del self.keys[fd]
            def get_map(self):
                return self.keys
            def select(self, _timeout):
                return [(key, 1) for key in tuple(self.keys.values())]
            def close(self):
                self.keys.clear()

        monkeypatch.setattr(owner, "os", SimpleNamespace(
            dup=lambda _fd: self.new_fd("workspace"), close=self.close,
            fstat=lambda _fd: self.directory.lstat(), pipe2=self.pipe,
            open=lambda *_args: self.new_fd("null"), fork=lambda: 900,
            pidfd_open=lambda *_args: self.new_fd("pidfd"),
            set_blocking=lambda *_args: None, read=self.read, wait4=self.wait,
            WIFSTOPPED=lambda status: status == 19, WSTOPSIG=lambda status: status,
            WIFEXITED=lambda status: status == 0, WIFSIGNALED=lambda status: status < 0,
            waitstatus_to_exitcode=lambda status: status,
            WNOHANG=1, WUNTRACED=2, O_CLOEXEC=0, O_RDONLY=0,
        ))
        monkeypatch.setattr(owner, "time", SimpleNamespace(
            CLOCK_BOOTTIME=7, clock_gettime_ns=self.now,
            process_time_ns=lambda: model.clock // 10,
            monotonic=lambda: model.clock / 10**9, sleep=lambda _delay: None,
        ))
        monkeypatch.setattr(owner, "signal", SimpleNamespace(
            SIGKILL=9, SIGSTOP=19, SIGCONT=18, pidfd_send_signal=self.signal,
        ))
        monkeypatch.setattr(owner, "selectors", SimpleNamespace(DefaultSelector=Selector, EVENT_READ=1))
        monkeypatch.setattr(owner, "_require_native_owner", lambda: None)
        monkeypatch.setattr(owner, "_free", lambda _fd: owner.FREE_BYTES + 1024**3)
        monkeypatch.setattr(owner, "_kernel_readback", lambda *args:
                            owner.KernelReadback(*args, 1, 1024**2))
        monkeypatch.setattr(owner, "_read_small", self.status)
        monkeypatch.setitem(sys.modules, "context_preparation_process_guard", SimpleNamespace())

    def run(self):
        return owner.run_single_process((str(self.directory / "worker.py"),),
                                       uid=701, gid=702, cwd=self.directory, workspace_fd=7,
                                       file_size_bytes=4096, cpu_seconds=300, wall_seconds=300)


def test_exit_mm_without_z_state_recovers_only_after_actual_terminal_wait(tmp_path, monkeypatch):
    model = ExitModel(tmp_path)
    model.install(monkeypatch)
    result = model.run()
    assert result.exit_code == 0 and result.stop_reason is None
    assert result.peak_rss_bytes == 4096 * 1024
    assert result.child_cpu_ns == 300_000_000
    assert result.stdout_prefix == b"complete\n"
    assert model.waits == 3 and model.samples == 2
    assert model.signals == [18] and not model.live


@pytest.mark.parametrize("terminal_at", [4, 5, 6])
def test_short_exit_transition_keeps_original_limits_and_terminal_usage(tmp_path, monkeypatch, terminal_at):
    model = ExitModel(tmp_path, terminal_at=terminal_at)
    model.install(monkeypatch)
    result = model.run()
    assert result.stop_reason is None and result.peak_rss_bytes == 4096 * 1024
    assert model.waits == terminal_at and not model.live
    assert result.elapsed_ns < 200_000_000


def test_missing_rss_cannot_turn_a_still_running_child_into_success(tmp_path, monkeypatch):
    model = ExitModel(tmp_path, terminal_at=90)
    model.install(monkeypatch)
    result = model.run()
    assert result.stop_reason == "rss_observation_lost"
    assert result.exit_code == -9 and result.child_cpu_ns == 300_000_000
    assert result.elapsed_ns < 200_000_000 and not model.live
    assert model.signals == [18, 9]


@pytest.mark.parametrize("rss", [1024**2, 1024**2 + 1])
def test_exit_race_does_not_hide_excessive_terminal_rss(tmp_path, monkeypatch, rss):
    model = ExitModel(tmp_path, rss=rss)
    model.install(monkeypatch)
    assert model.run().stop_reason == "rss_limit"
    assert not model.live


@pytest.mark.parametrize("rss", [0, -1, True, 1.5, None])
def test_exit_race_still_requires_strict_terminal_rusage(tmp_path, monkeypatch, rss):
    model = ExitModel(tmp_path, rss=rss)
    model.install(monkeypatch)
    with pytest.raises(owner.NativeSupervisorError, match="terminal RSS"):
        model.run()
    assert not model.live


@pytest.mark.parametrize("value", ["0 kB", "1 MB", "-1 kB", "broken"])
def test_present_malformed_rss_is_not_an_exit_transition(tmp_path, monkeypatch, value):
    model = ExitModel(tmp_path, raw=("State:\tR\nThreads:\t1\nVmHWM:\t" + value + "\n").encode())
    model.install(monkeypatch)
    with pytest.raises(owner.NativeSupervisorError):
        model.run()
    assert not model.live
