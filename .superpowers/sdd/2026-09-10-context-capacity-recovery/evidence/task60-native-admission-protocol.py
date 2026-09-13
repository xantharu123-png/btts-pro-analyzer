"""Operator-only stdlib counterpart to the two explicit native Task60 tests.

Root substitutes only BUNDLE_BASE64 with the two reviewed source byte strings.
This creates one fixed isolated test namespace, never touches app or old QA,
and returns observations, not permission to run the real receipt diagnostic.
"""
import base64
import hashlib
import json
import os
import resource
import signal
import stat
import sys
import time
import types
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
signal.alarm(30)
assert sys.platform == "linux" and os.getuid() == os.geteuid() == 0
assert os.getgid() == os.getegid() == 0
assert dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
assert sys.flags.isolated and sys.flags.no_site and not sys.flags.optimize
assert sys.dont_write_bytecode

PINS = {
    "context_preparation_budget": "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478",
    "admission": "f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad",
}
bundle = json.loads(base64.b64decode("BUNDLE_BASE64", validate=True))
assert set(bundle) == set(PINS)
sources = {}
for name in sorted(PINS):
    raw = base64.b64decode(bundle[name], validate=True)
    assert len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == PINS[name]
    sources[name] = raw
budget = types.ModuleType("context_preparation_budget")
budget.__file__ = "<held-reviewed-budget>"
assert budget.__name__ not in sys.modules
sys.modules[budget.__name__] = budget
exec(compile(sources[budget.__name__], budget.__file__, "exec"), budget.__dict__)
admission = {"__name__": "held_native_admission_not_registered"}
exec(compile(sources["admission"], "<held-reviewed-admission>", "exec"), admission)
assert admission["__name__"] not in sys.modules

base = Path("/var/lib/betboy-admission-task60-protocol-8574747-01")
for parent in reversed(base.parents):
    info = parent.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022
base.mkdir(mode=0o700)  # Exact fresh test root only; existing path refuses.
checks = []


def reject(call, message=None):
    try:
        call()
    except admission["AdmissionError"] as error:
        if message is not None:
            assert message in str(error), (message, str(error))
        return type(error).__name__
    raise AssertionError("native rejection was required")


def capture(registry):
    result = {}
    for item in sorted(registry.iterdir()):
        info = item.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        assert info.st_uid == 0 and not info.st_mode & 0o077 and info.st_size <= 1024**2
        fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            held = os.fstat(stream.fileno())
            assert (info.st_dev, info.st_ino) == (held.st_dev, held.st_ino)
            raw = stream.read(1024**2 + 1)
            assert len(raw) == info.st_size and len(raw) <= 1024**2
            def stamp(value):
                return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
                        value.st_uid, value.st_gid, value.st_size, value.st_mtime_ns,
                        value.st_ctime_ns, value.st_blocks)
            assert stamp(os.fstat(stream.fileno())) == stamp(held) == stamp(item.lstat())
        result[item.name] = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                             "device": info.st_dev, "inode": info.st_ino,
                             "mode": stat.S_IMODE(info.st_mode)}
    return result


def arguments(job, identity="abcde"):
    return dict(identity=budget.BudgetIdentity(*(c * 64 for c in identity)),
                purpose="context-receipt-corpus-diagnostic-v1", profile_kind="atp-heavy",
                plan_digest="1" * 64, job_directory=job, retained_history_digest="2" * 64)


registry, job = base / "registry", base / "job"
registry.mkdir(mode=0o700)
job.mkdir(mode=0o700)
owner = admission["admit_diagnostic"](registry, **arguments(job))
owner.assert_admitted()
snapshot = owner.snapshot()
assert snapshot["binding"]["ticket"]["cpu_ns"] == 300 * 10**9
assert snapshot["admission"]["process"]["pid"] == os.getpid()
before = capture(registry)
reject(lambda: admission["admit_diagnostic"](registry, **arguments(job, "fbcde")), "lock contention")
assert capture(registry) == before
owner.assert_admitted()
owner.close()
closed = capture(registry)
reject(lambda: admission["admit_diagnostic"](registry, **arguments(job)), "permanently consumed")
assert capture(registry) == closed
checks.extend(["native-private-root-admission", "actual-flock-contention",
               "durable-close-no-refund", "same-family-refused-without-mutation"])

registry, job = base / "loss-registry", base / "loss-job"
registry.mkdir(mode=0o700)
job.mkdir(mode=0o700)
alias = base / "linked-registry"
alias.symlink_to(registry, target_is_directory=True)
reject(lambda: admission["admit_diagnostic"](alias, **arguments(job)))
writable = base / "writable-parent"
writable.mkdir(mode=0o700)
writable.chmod(0o777)  # Deliberate negative fixture, only inside this new test root.
child = writable / "registry"
child.mkdir(mode=0o700)
reject(lambda: admission["admit_diagnostic"](child, **arguments(job)))
assert not list(registry.iterdir()) and not list(child.iterdir())
owner = admission["admit_diagnostic"](registry, **arguments(job))
owner.assert_admitted()
assert owner.snapshot()["binding"]["ticket"]["cpu_ns"] == 300 * 10**9
import fcntl
fcntl.flock(owner._namespace._registry_fd, fcntl.LOCK_UN)  # Exact private loss injection.
reject(owner.assert_admitted, "custody lost")
reject(owner.close)
lost = capture(registry)
reject(lambda: admission["admit_diagnostic"](registry, **arguments(job, "fbcde")))
assert capture(registry) == lost
checks.extend(["symlink-registry-denied", "writable-ancestor-denied",
               "lost-live-flock-poisons-assert-and-close", "poisoned-registry-no-retry"])
result = {"format": "betboy-admission-native-protocol-observation-v1",
          "observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "root": str(base), "pins": PINS, "checks": checks,
          "closed_registry": closed, "lost_registry": lost,
          "retained_reserved_cpu_ns": 600 * 10**9,
          "cpu_seconds": time.process_time(),
          "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "actual_exit_observed_externally": False, "native_driver_pass": False,
          "fixture_identity_is_not_real_baseline_authority": True}
raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
assert len(raw) <= 65536
view = memoryview(raw)
while view:
    count = os.write(1, view)
    assert count > 0
    view = view[count:]
