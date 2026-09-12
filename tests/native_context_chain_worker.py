"""Actual Task54 driver. No product import is reachable before guard readback.

Only the fixed parent may run this script after the unchanged supervisor's
identity drop, irreversible guard, SIGSTOP and actual kernel readback.
"""
import ctypes
import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


FORMAT = "betboy-native-context-chain-worker-v1"
MIB = 1024**2


class ChainError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ChainError(message)


def parse_arguments(args):
    require(len(args) == 1 and args[0] in ("ATP", "WTA"), "only fixed ATP/WTA child argv")
    return args[0]


def require_guard():
    require(sys.flags.optimize == 0, "Task54 requires active Python assertions")
    require(sys.platform == "linux" and os.uname().machine == "x86_64", "Linux/x86_64 child required")
    import resource
    require((sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode) == (1, 1, 1), "-I -S -B child required")
    require(os.getresuid() == (65534,) * 3 and os.getresgid() == (65534,) * 3
            and os.getgroups() == [], "identity drop missing")
    raw = Path("/proc/self/status").read_bytes()
    require(0 < len(raw) <= 65536, "unbounded kernel status")
    fields = dict(line.split(":", 1) for line in raw.decode("ascii").splitlines())
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        require(int(fields[name].strip(), 16) == 0, "capabilities remain")
    for name, value in (("Threads", "1"), ("NoNewPrivs", "1"), ("Seccomp", "2"), ("TracerPid", "0")):
        require(fields[name].strip() == value, "guard/task state differs")
    lib = ctypes.CDLL(None, use_errno=True)
    require(lib.prctl(3, 0, 0, 0, 0) == 0, "child remains dumpable")
    for key, value in ((resource.RLIMIT_AS, 2 * 1024**3), (resource.RLIMIT_CPU, 90),
                       (resource.RLIMIT_FSIZE, 4 * MIB), (resource.RLIMIT_NPROC, 0), (resource.RLIMIT_CORE, 0)):
        require(resource.getrlimit(key) == (value, value), "child limit differs")
    return {"pid": os.getpid(), "uid": os.getuid(), "gid": os.getgid(), "assertions": True}


def load_catalogue(path):
    # Root owns this exact read-only seal. Execute held bytes, not a second
    # runpy path open; parent already binds this file to reviewed manifest.
    namespace = {"__name__": "_chain_observation", "__file__": str(path)}
    exec(compile(path.read_bytes(), str(path), "exec"), namespace)
    return namespace


def invoke_cases(tour, work, sample):
    """Actual callable adapter, also exercised by portable QA (not native proof)."""
    require(sys.flags.optimize == 0 and tour in ("ATP", "WTA"), "active assertions/fixed tour required")
    import pytest
    import test_context_storage_corpus_consumer as acceptance
    from context_storage_v2.workspace_budget import WorkspaceBudget
    actual_check = WorkspaceBudget.check_quiescent

    def observed_check(owner):
        value = actual_check(owner)
        sample(str(owner.directory.relative_to(work)))
        return value

    properties = {}
    def record(key, value):
        require(key not in properties, "duplicate Task54 evidence field")
        properties[key] = value

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(WorkspaceBudget, "check_quiescent", observed_check)
        positive = work / "positive"
        require(positive.is_dir() and not any(positive.iterdir()), "positive directory is not fresh")
        result = acceptance.run_small_corpus_consumer_acceptance(positive, monkeypatch, tour, record_property=record)
        sample("positive-reopened")
    rollback = None
    if tour == "ATP":
        failed = work / "late-cleanup"
        require(failed.is_dir() and not any(failed.iterdir()), "retained-failure directory is not fresh")
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(WorkspaceBudget, "check_quiescent", observed_check)
            acceptance.test_real_late_prepared_cleanup_failure_rolls_back_consumer_before_commit(failed, monkeypatch)
        sample("late-cleanup-cold-reopened-no-tables")
        rollback = {"accepted": False, "directory": "late-cleanup", "cold_reopen": "no-consumer-tables"}
    sample("terminal-quiescent")
    return {"properties": properties, "published": dataclasses.asdict(result["published"]), "late_cleanup": rollback}


def observe_python_files(code, seal, work, manifest):
    """Bounded Python audit observations, NOT a native whole-host sandbox.

Native ELF opens are separately visible in proc maps. Descriptor-relative
stdlib copier opens have no dir_fd in Python's audit event and are labelled
as such; their actual no-follow custody belongs to the catalogue reader.
"""
    permitted = {str(code / x["path"]) for x in manifest["code"]}
    permitted |= {str(seal / "dependencies" / x["path"]) for x in manifest["dependencies"]}
    # -B prevents cache writes, not reads. Deny the exact interpreter cache
    # probe for each admitted source BEFORE opening it, including if a cache
    # exists. FileNotFoundError lets CPython read the admitted source instead;
    # this is not permission to read bytecode or an additional directory root.
    denied_caches = {str(Path(importlib.util.cache_from_source(name)))
                     for name in permitted if name.endswith(".py")}
    system = tuple(Path(p) for p in manifest["runtime"]["stdlib_search_path"] if Path(p).is_absolute())
    observed = {}
    def record(key):
        require(key in observed or len(observed) < 3000, "Python file observation bound exceeded")
        observed[key] = observed.get(key, 0) + 1
    def audit(event, args):
        if event not in ("open", "sqlite3.connect") or not args or not isinstance(args[0], (str, bytes)):
            return
        name = os.fsdecode(args[0])
        # Directory traversal is protected by no-follow directory descriptors,
        # not a language-level audit-path reconstruction.
        if event == "open" and len(args) > 2 and type(args[2]) is int and args[2] & os.O_DIRECTORY:
            return
        p = Path(name)
        require(p.suffix.lower() not in (".pkl", ".pickle", ".csv", ".xlsx", ".xls"), "unplanned training/fallback data access")
        if event == "open" and str(p) in denied_caches:
            require(len(args) > 2 and type(args[2]) is int and
                    not args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND),
                    "unplanned bytecode write")
            record("denied-bytecode-probe:" + name)
            raise FileNotFoundError(2, "bytecode denied; admitted source required", name)
        if p.is_absolute() and not p.is_relative_to(work):
            require(str(p) in permitted or str(p) in ("/proc/self/maps", "/proc/self/status")
                    or any(p == base or p.is_relative_to(base) for base in system), "unplanned Python file read")
        record(event + ":" + name)
    sys.addaudithook(audit)
    return observed


def run(tour):
    state = require_guard()
    code = Path(__file__).absolute().parents[1]
    seal = code.parent
    work = Path.cwd()
    require(work.name == tour and work.parent.name == "attempts", "fixed child workspace differs")
    c = load_catalogue(code / "tests/native_context_chain_catalogue.py")
    manifest = c["decode"]((seal / "catalogue.json").read_bytes())
    slots = {key.split("/", 1)[1]: cap for key, cap in c["attempt_slots"]().items()
             if key.startswith(tour + "/")}
    samples = []
    file_observations = observe_python_files(code, seal, work, manifest)
    # Only now can actual pytest and product modules enter this interpreter.
    sys.path[:0] = [str(code), str(code / "tests"), str(seal / "dependencies")]
    def sample(label):
        require(len(samples) < 40, "quiescent observation count exceeded")
        observed = c["workspace_sample"](work, slots, 4 * MIB)
        logical, allocated = observed["logical"], observed["allocated"]
        usage = os.statvfs(work)
        free = usage.f_bavail * usage.f_frsize
        # Conservative: no credit for writes by a prior child, or metadata.
        # This includes all three attempts, all copies, controls and slack.
        unspent = manifest["plan"]["total"] - logical
        require(free >= 4 * 1024**3 + unspent, "union free reserve lost")
        require(logical <= sum(slots.values()) and allocated <= sum(slots.values()), "child aggregate exceeded")
        samples.append({"boundary": label, "files": observed["files"], "directories": observed["directories"], "logical": logical,
                        "allocated": allocated, "free": free, "unspent_conservative": unspent})

    result = invoke_cases(tour, work, sample)
    require_guard()  # imports/computation must not have changed kernel guard
    with open("/proc/self/maps", "r", encoding="ascii") as stream:
        mappings = stream.read(MIB + 1)
    require(len(mappings) <= MIB, "native mapped-library observation exceeded")
    # Full comparisons and reopen happen in the pinned callable, not in this
    # JSON parser. Dataclasses are evidence only, never Source/commit authority.
    payload = {"format": FORMAT, "tour": tour, "phase": "complete", "state": state,
               **result, "samples": samples,
               "acceptance_callable": c["TASK54_SHA"],
               "task54_m1": "new-original-created-at-direct-assertion-deferred",
               "native_libraries_observation": mappings,
               "python_file_observations": file_observations}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii") + b"\n"
    require(len(encoded) <= MIB, "complete child evidence exceeds output bound")
    view = memoryview(encoded)
    while view:
        count = os.write(1, view)
        require(count > 0, "child output stalled")
        view = view[count:]


if __name__ == "__main__":
    try:
        run(parse_arguments(sys.argv[1:]))
    except BaseException as exc:
        # The unchanged supervisor suppresses arbitrary tracebacks. Preserve a
        # bounded diagnostic reason in its charged stderr before propagating.
        error = json.dumps({"format": FORMAT, "phase": "failed", "exception": type(exc).__name__,
                            "message": str(exc)[:512]}, ensure_ascii=True).encode("ascii") + b"\n"
        os.write(2, error)
        raise
