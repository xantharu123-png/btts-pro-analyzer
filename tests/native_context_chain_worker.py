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
    file_context = None


def require(value, message):
    if not value:
        raise ChainError(message)


def failure_bytes(exc):
    """One bounded failure record; never reopen a rejected path for diagnosis."""
    payload = {"format": FORMAT, "phase": "failed", "exception": type(exc).__name__[:64],
               "message": str(exc)[:512]}
    if isinstance(exc, ChainError) and exc.file_context is not None:
        payload["file_context"] = exc.file_context
    encoded = json.dumps(payload, ensure_ascii=True).encode("ascii") + b"\n"
    require(len(encoded) <= 8192, "failure diagnostic exceeds bound")
    return encoded


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
    timezone_root = seal / "runtime-data/zoneinfo"
    timezone_system = Path("/usr/share/zoneinfo").absolute()
    timezone_files = {str(timezone_root / x["path"]) for x in manifest.get("timezone_data", [])}
    permitted |= timezone_files
    # -B prevents cache writes, not reads. Deny the exact interpreter cache
    # probe for each admitted source BEFORE opening it, including if a cache
    # exists. FileNotFoundError lets CPython read the admitted source instead;
    # this is not permission to read bytecode or an additional directory root.
    denied_caches = {str(Path(importlib.util.cache_from_source(name)))
                     for name in permitted if name.endswith(".py")}
    # NumPy probes this optional installation-origin file through the stdlib's
    # PathDistribution.read_text. Derive only the exact sibling of an already
    # admitted NumPy METADATA file. Missing/unadmitted bytes remain unreadable;
    # an actually catalogued origin file retains its normal exact admission.
    denied_optional_metadata = {
        str(p.with_name("direct_url.json")) for p in map(Path, permitted)
        if p.name == "METADATA" and p.parent.name.startswith("numpy-")
        and p.parent.name.endswith(".dist-info")
    } - permitted
    system = tuple(Path(p) for p in manifest["runtime"]["stdlib_search_path"] if Path(p).is_absolute())
    observed = {}
    def record(key):
        require(key in observed or len(observed) < 3000, "Python file observation bound exceeded")
        observed[key] = observed.get(key, 0) + 1
    def audit(event, args):
        if event == "import" and args and isinstance(args[0], str):
            require(args[0] != "tzdata" and not args[0].startswith("tzdata."), "unplanned tzdata fallback import")
        if event not in ("open", "sqlite3.connect") or not args or not isinstance(args[0], (str, bytes)):
            return
        name = os.fsdecode(args[0])
        def reject(message):
            flags = args[2] if event == "open" and len(args) > 2 else None
            error = ChainError(message)
            error.file_context = {
                "event": event, "path": name[:512], "path_truncated": len(name) > 512,
                "path_sha256": hashlib.sha256(os.fsencode(name)).hexdigest(),
                "flags": flags if type(flags) is int and -(2**63) <= flags < 2**63 else None,
            }
            raise error
        # Directory traversal is protected by no-follow directory descriptors,
        # not a language-level audit-path reconstruction.
        if event == "open" and len(args) > 2 and type(args[2]) is int and args[2] & os.O_DIRECTORY:
            return
        p = Path(name)
        # No filesystem lookup: normalize only to recognize relative traversal
        # into the protected data tree. Descriptor-relative bare-name opens
        # retain the existing catalogue no-follow-FD custody contract.
        data_path = Path(os.path.abspath(name))
        if str(p) in timezone_files:
            if (event != "open" or len(args) <= 2 or type(args[2]) is not int or
                    args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                reject("unplanned timezone data write")
        elif data_path.is_relative_to(timezone_root) or data_path.is_relative_to(timezone_system):
            reject("unplanned timezone data read")
        if p.suffix.lower() in (".pkl", ".pickle", ".csv", ".xlsx", ".xls"):
            reject("unplanned training/fallback data access")
        if event == "open" and str(p) in denied_caches:
            require(len(args) > 2 and type(args[2]) is int and
                    not args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND),
                    "unplanned bytecode write")
            record("denied-bytecode-probe:" + name)
            raise FileNotFoundError(2, "bytecode denied; admitted source required", name)
        if event == "open" and str(p) in denied_optional_metadata:
            if (len(args) <= 2 or type(args[2]) is not int or
                    args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                reject("unplanned optional metadata write")
            record("denied-optional-metadata-probe:" + name)
            raise FileNotFoundError(2, "uncatalogued optional NumPy metadata denied", name)
        if p.is_absolute() and not p.is_relative_to(work):
            if not (str(p) in permitted or str(p) in ("/proc/self/maps", "/proc/self/status")
                    or any(p == base or p.is_relative_to(base) for base in system)):
                reject("unplanned Python file read")
        record(event + ":" + name)
    sys.addaudithook(audit)
    return observed


def bind_timezone_data(c, seal, manifest):
    """After guard/audit, point the actual stdlib reader only at the data seal.

    No reader/import shim: unknown fallback package bytes still fail the
    exact-member file audit, including resources/importlib-driven imports.
    """
    require(not any(n == "tzdata" or n.startswith("tzdata.") for n in sys.modules),
            "preloaded tzdata fallback is not permitted")
    root = seal / "runtime-data/zoneinfo"
    c["timezone_copy_identities"](root, manifest["timezone_data"])
    import zoneinfo
    zoneinfo.reset_tzpath((str(root),))
    zoneinfo.ZoneInfo.clear_cache()
    require(zoneinfo.TZPATH == (str(root),), "sealed timezone search path differs")


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
    bind_timezone_data(c, seal, manifest)
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
        os.write(2, failure_bytes(exc))
        raise
