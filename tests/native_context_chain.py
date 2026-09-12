"""Task57 fresh secret-free stdlib parent; no native-pass/self-exit claim.

Root reviews the archive, inventory and this bootstrap before launching with
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B.
No retry, reset, arbitrary worker, installation, deployment or B authority.
"""
from contextlib import ExitStack
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types


MIB = 1024**2
CATALOGUE_SHA256 = "93d38e46c17b9796088cfad66ea1667413b702b93f8310ac43b6e6ee7ac648f9"
WORKER_FORMAT = "betboy-native-context-chain-worker-v1"
TASK54_SHA256 = "5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649"
PROPERTY_KEYS = frozenset("tour source_sha256 corpus_sha256 ledger_sha256 parts_sha256 history_sha256 features_sha256 consumer_sha256 receipt_inventory_digest old_coverage_digest feature_canonical_sha256 snapshot_key snapshot_raw_sha256 snapshot_payload_digest original_hash protected_receipt_count semantic_limitations budget_plan budget_reserved setup_budget_plan setup_budget_reserved setup_workspace_bytes union_reserved_bytes union_observed_bytes after_corpus_bytes after_parts_bytes after_history_bytes after_feature_bytes final_workspace_bytes final_free_bytes".split())
FLAGS = ("--manifest", "--manifest-sha256", "--archive", "--directory", "--commit", "--launcher-sha256")


class ChainError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ChainError(message)


def arguments(args):
    require(len(args) == 12 and tuple(args[::2]) == FLAGS, "fixed manifest/hash/archive/directory/commit/launcher CLI only")
    values = dict(zip(FLAGS, args[1::2]))
    for key in ("--manifest", "--archive", "--directory"):
        path = Path(values[key])
        require(path.is_absolute() and str(path) == values[key] and ".." not in path.parts, "canonical absolute path required")
    for key in ("--manifest-sha256", "--launcher-sha256"):
        value = values[key]
        require(len(value) == 64 and all(c in "0123456789abcdef" for c in value), "reviewed digest required")
    return values


def boot_start(raw, hz, pid):
    require(type(raw) is bytes and 0 < len(raw) <= 8192 and raw.startswith((str(pid) + " (").encode()), "kernel process record differs")
    tail = raw.rsplit(b") ", 1)[-1].split()
    require(len(tail) >= 20 and tail[19].isdigit() and type(hz) is int and hz > 0, "kernel start tick unavailable")
    return int(tail[19]) * 10**9 // hz


class Window:
    def __init__(self):
        with open("/proc/self/stat", "rb") as stream:
            raw = stream.read(8193)
        self.start = boot_start(raw, os.sysconf("SC_CLK_TCK"), os.getpid())
        self.deadline = self.start + 600 * 10**9
        self.previous = self.start
        self.check()

    def check(self, reserve=0):
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        require(self.previous <= now < self.deadline - reserve * 10**9, "whole diagnostic wall deadline")
        require(time.process_time_ns() < 90 * 10**9, "parent whole-life CPU exceeded")
        self.previous = now
        return now


def protected(path, directory=False):
    """No existing permissions change; all bootstrap/namespace ancestors protected."""
    require(path.is_absolute(), "absolute protected path required")
    for candidate in [path, *path.parents]:
        value = candidate.lstat()
        require(value.st_uid == 0 and not value.st_mode & 0o022, "unprotected root namespace")
        if candidate != path or directory:
            require(stat.S_ISDIR(value.st_mode), "linked protected directory")
        else:
            require(stat.S_ISREG(value.st_mode) and value.st_nlink == 1, "linked protected file")
    return path.stat()


def load_catalogue():
    sources = globals().get("_REVIEWED_BOOTSTRAP")
    require(type(sources) is dict, "reviewed stdin bootstrap required; no installed-path fallback")
    raw = sources.get("tests/native_context_chain_catalogue.py")
    require(type(raw) is bytes and len(raw) <= MIB and hashlib.sha256(raw).hexdigest() == CATALOGUE_SHA256,
            "actual in-memory catalogue pin differs")
    namespace = {"__name__": "_task57_catalogue", "__file__": "<reviewed-task57-catalogue>"}
    exec(compile(raw, "<reviewed-task57-catalogue>", "exec"), namespace)
    return namespace


def load_helpers(c, sources):
    result = {}
    for filename, expected in c["HELPERS"].items():
        raw = sources[filename]
        require(type(raw) is bytes and 0 < len(raw) <= MIB and hashlib.sha256(raw).hexdigest() == expected, "in-memory helper pin differs")
        name = filename[:-3]
        require(name not in sys.modules, "helper interpreter is reused")
        module = types.ModuleType(name)
        module.__file__ = "<reviewed-" + filename + ">"
        sys.modules[name] = module
        exec(compile(raw, module.__file__, "exec"), module.__dict__)
        result[name] = module
    return result


def write_new(path, raw, mode=0o444):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            require(n > 0, "parent write stalled")
            view = view[n:]
        os.fsync(fd)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


class ReservedActions:
    """No new copy or child can enter without the actual durable ticket."""
    def __init__(self, handle, ticket):
        self.handle, self.ticket = handle, ticket

    def check(self):
        value = self.handle.snapshot()
        require(value.status == "pending" and value.pending == self.ticket
                and value.charged_cpu_ns == 300 * 10**9, "complete durable charge missing")

    def write(self, path, raw):
        self.check()
        write_new(path, raw)

    def copy(self, copy, source, target, item):
        self.check()
        copy(source, target, item)


def accept_result(result, tour):
    require(result.exit_code == 0 and result.stop_reason is None, "stopped/failed child cannot be accepted")
    require(type(result.child_cpu_ns) is int and 0 <= result.child_cpu_ns <= 90 * 10**9
            and 0 <= result.elapsed_ns <= 90 * 10**9 and 0 < result.peak_rss_bytes < 1024**3,
            "native child over budget")
    require(result.observed_output_bytes <= MIB and result.stderr_prefix == b""
            and result.minimum_free_bytes >= 4 * 1024**3, "output/free native bounds failed")
    rb = result.kernel_readback
    require(rb is not None and rb.uid == rb.gid == 65534 and rb.cpu_seconds == 90
            and rb.file_size_bytes == 4 * MIB, "missing/different actual stopped kernel readback")
    raw = result.stdout_prefix
    require(0 < len(raw) <= MIB and raw.endswith(b"\n") and raw.count(b"\n") == 1
            and len(raw) == result.observed_output_bytes, "incomplete child output")
    def pairs(values):
        d = {}
        for k, v in values:
            require(k not in d, "duplicate child JSON key")
            d[k] = v
        return d
    def invalid(_value):
        raise ChainError("nonfinite child JSON number")
    data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    require(type(data) is dict and data.get("format") == WORKER_FORMAT and data.get("tour") == tour
            and data.get("phase") == "complete", "foreign/incomplete child output")
    require(data.get("state") == {"pid": rb.pid, "uid": 65534, "gid": 65534, "assertions": True}, "child identity output differs")
    require(data.get("late_cleanup") == ({"accepted": False, "directory": "late-cleanup",
            "cold_reopen": "no-consumer-tables"} if tour == "ATP" else None), "missing late-close no-acceptance")
    require(type(data.get("samples")) is list and 8 <= len(data["samples"]) <= 40
            and data["samples"][-1].get("boundary") == "terminal-quiescent", "missing whole child observations")
    require(set(data) == {"format", "tour", "phase", "state", "properties", "published", "samples",
            "late_cleanup", "acceptance_callable", "task54_m1", "native_libraries_observation", "python_file_observations"},
            "incomplete/unknown child evidence")
    require(data["acceptance_callable"] == TASK54_SHA256
            and data["task54_m1"] == "new-original-created-at-direct-assertion-deferred", "acceptance owner differs")
    properties = data["properties"]
    require(type(properties) is dict and set(properties) == PROPERTY_KEYS and properties["tour"] == tour
            and properties["union_reserved_bytes"] == 78643200
            and properties["setup_budget_reserved"] == 34603008
            and properties["budget_reserved"] == 44040192, "Task54 evidence/reservation incomplete")
    require(type(data["published"]) is dict and data["published"].get("original_hash") == properties["original_hash"], "published evidence differs")
    for sample in data["samples"]:
        require(type(sample) is dict and set(sample) == {"boundary", "files", "directories", "logical", "allocated", "free", "unspent_conservative"}
                and type(sample["files"]) is list and type(sample["directories"]) is list
                and sample["free"] >= 4 * 1024**3 + sample["unspent_conservative"], "incomplete/over-budget phase observation")
    return data


def run_cases(launch, recheck):
    results = []
    for tour in ("ATP", "WTA"):
        recheck()
        result = launch(tour)
        recheck()
        payload = accept_result(result, tour)
        results.append({"tour": tour, "output_file": tour + "-output.json",
                        "properties": payload["properties"], "late_cleanup": payload["late_cleanup"]})
    return results


def orchestrate(supervisor, *, worker, attempt_root, window, recheck, retain, custody, admit):
    def launch(tour):
        admit()
        window.check(95)
        directory = attempt_root / tour
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                result = supervisor.run_single_process((str(worker), tour), uid=65534, gid=65534,
                    cwd=directory, workspace_fd=fd, file_size_bytes=4 * MIB, cpu_seconds=90, wall_seconds=90)
            except supervisor.UnreapedChild as exc:
                # FIRST transition: disable the wall alarm before any fallible
                # report/journal operation can abandon actual pidfd custody.
                signal.setitimer(signal.ITIMER_REAL, 0)
                custody(exc)
                raise
        finally:
            os.close(fd)
        retain(tour, result)  # retain even invalid/failed output before parsing
        return result
    return run_cases(launch, recheck)


def custody_stop(exc, report):
    """Never abandon the same unreaped child; NOT a completed600s diagnostic."""
    try:
        report({"status": "operator-custody-required-NOT-complete", "parent_pid": os.getpid(),
                "child_pid": exc.pid, "owned_pidfd": exc.pidfd, "retained_cpu_ns": 300 * 10**9})
    except BaseException:
        pass  # no report failure may discard the still-owned pidfd
    while True:
        os.kill(os.getpid(), signal.SIGSTOP)
        # Reached only after an external operator's explicit SIGCONT.
        try:
            try:
                if exc.pidfd is None:
                    os.kill(exc.pid, signal.SIGKILL)
                else:
                    signal.pidfd_send_signal(exc.pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            found, status, _usage = os.wait4(exc.pid, os.WNOHANG)
        except BaseException:
            continue
        if found == exc.pid and (os.WIFEXITED(status) or os.WIFSIGNALED(status)):
            if exc.pidfd is not None:
                os.close(exc.pidfd)
            return


def main(argv):
    args = arguments(argv)
    require(sys.platform == "linux" and os.uname().machine == "x86_64" and os.getresuid() == (0, 0, 0), "fresh root Linux/x86_64 parent required")
    require((sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0), "fresh -I -S -B without optimization required")
    require(dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, "empty env-i parent required")
    window = Window()
    import resource
    import ctypes
    for key, value in ((resource.RLIMIT_CPU, 90), (resource.RLIMIT_AS, 2 * 1024**3),
                       (resource.RLIMIT_FSIZE, 128 * MIB), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (value, value))
    lib = ctypes.CDLL(None, use_errno=True)
    require(lib.prctl(4, 0, 0, 0, 0) == 0 and lib.prctl(3, 0, 0, 0, 0) == 0, "parent dumpability")
    def expired(_signum, _frame):
        raise ChainError("parent diagnostic deadline expired; no acceptance")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, (window.deadline - window.check()) / 10**9)
    c = load_catalogue()
    manifest_raw = c["data_bytes"](Path(args["--manifest"]), c["MANIFEST_CAP"], args["--manifest-sha256"])
    manifest = c["validate_manifest"](c["decode"](manifest_raw), args["--commit"])
    # Bind the actual executing bootstrap, not just an unused archive copy.
    code_entries = {x["path"]: x for x in manifest["code"]}
    sources = globals()["_REVIEWED_BOOTSTRAP"]
    reconstructed_stdin = c["bootstrap_source"](sources)
    require(c["digest"](reconstructed_stdin) == args["--launcher-sha256"], "Root-reviewed stdin digest differs")
    for name, raw in sources.items():
        require(code_entries[name]["sha256"] == c["digest"](raw) and code_entries[name]["size"] == len(raw), "executed in-memory bootstrap differs from archive")
    require(code_entries["tests/native_context_chain_catalogue.py"]["sha256"] == CATALOGUE_SHA256, "catalogue self pin differs")
    runtime = manifest["runtime"]
    require(runtime["python"] == sys.version and runtime["kernel"] == list(os.uname())
            and runtime["stdlib_search_path"] == list(sys.path)
            and runtime["executable"] == str(Path("/proc/self/exe").resolve())
            and c["file_record"](Path(runtime["executable"]))["sha256"] == runtime["executable_sha256"], "observed runtime changed")
    helpers = load_helpers(c, sources)
    supervisor = helpers["context_preparation_supervisor"]
    supervisor._require_native_owner()
    job = Path(args["--directory"])
    protected(job.parent, directory=True)
    require(all(p.stat().st_mode & 0o001 for p in [job.parent, *job.parent.parents]), "existing job parent is not child-searchable")
    require(not os.path.lexists(job), "no directory reuse/retry")
    plan = manifest["plan"]
    archive, manifest_path = Path(args["--archive"]), Path(args["--manifest"])
    originals_plan = c["original_input_plan"](archive, manifest_path, c["DEPENDENCY_SOURCE"],
                                               manifest["archive"]["size"], manifest["dependencies"])
    require(sum(x["logical"] for x in originals_plan["files"]) == plan["original_logical_reservation"]
            and sum(x["allocated"] for x in originals_plan["files"]) == plan["original_allocated_reservation"]
            and originals_plan["metadata_cap"] == plan["original_metadata_reservation"], "original plan differs")
    require(os.statvfs(job.parent).f_bavail * os.statvfs(job.parent).f_frsize >= 4 * 1024**3 + plan["total"], "initial complete free reserve")
    # This new directory's creation is inside the same kernel-start window and
    # predeclared metadata allowance; journal inode identity follows creation.
    job.mkdir(mode=0o755)
    job_info = protected(job, directory=True)
    budget_module = helpers["context_preparation_budget"]
    hash_value = lambda value: c["digest"](c["canonical"](value))
    identity = budget_module.BudgetIdentity(
        input_digest=manifest["archive"]["sha256"], execution_digest=hash_value(manifest["code"]),
        runtime_digest=hash_value(runtime), installation_digest=hash_value({"manifest": args["--manifest-sha256"],
            "job": str(job), "dev": job_info.st_dev, "ino": job_info.st_ino,
            "originals": originals_plan}), profile_digest=hash_value(plan))
    journal_name = hash_value(dataclasses.asdict(identity)) + ".jsonl"
    # Complete fixed slots exist in memory BEFORE the first journal writer.
    fixed = {"archive.tar": (manifest["archive"]["size"] + 4095) // 4096 * 4096,
             "catalogue.json": c["MANIFEST_CAP"], "plan.json": c["MANIFEST_CAP"],
             "report.json": MIB, "failure.json": MIB, "custody.json": MIB, journal_name: MIB,
             "ATP-output.json": 3 * MIB, "WTA-output.json": 3 * MIB}
    # Rounded copy allocation slack is charged inside the predeclared 128MiB
    # metadata/allocation reserve, not mistaken for exact logical content size.
    fixed.update({"code/" + x["path"]: (x["size"] + 4095) // 4096 * 4096 for x in manifest["code"]})
    fixed.update({"dependencies/" + x["path"]: (x["size"] + 4095) // 4096 * 4096 for x in manifest["dependencies"]})
    fixed.update({"attempts/" + name: cap for name, cap in c["attempt_slots"]().items()})
    job_fd = os.open(job, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    handle = budget_module.PreparationBudget.create(job_fd, identity)
    inputs = ExitStack()
    retained = None
    try:
        ticket = handle.reserve(hash_value({"diagnostic": "task57-atp-wta-once", "plan": plan}), 300 * 10**9)
        actions = ReservedActions(handle, ticket)
        archive_fd, archive_stat = inputs.enter_context(c["opened"](archive))
        dependency_fd, dependency_stat = inputs.enter_context(c["opened"](c["DEPENDENCY_SOURCE"], directory=True))
        manifest_fd, manifest_stat = inputs.enter_context(c["opened"](manifest_path))
        raw = c["data_bytes"](archive, c["ARCHIVE_CAP"], manifest["archive"]["sha256"])
        require(len(raw) == manifest["archive"]["size"], "archive length differs")
        archive_info = c["identity"](archive.lstat())
        members = c["archive_members"](raw, manifest["code"])
        require(c["walk"](c["DEPENDENCY_SOURCE"], c["PACKAGES"]) == manifest["dependencies"], "dependency admission incomplete")
        dependency_identities = [(x["path"], c["identity"]((c["DEPENDENCY_SOURCE"] / x["path"]).lstat()))
                                 for x in manifest["dependencies"]]
        original_baseline = c["sample_original_inputs"](originals_plan)
        baseline_files = {x["path"]: x["identity"] for x in original_baseline["files"]}
        for path, expected in [(str(archive), c["identity"](archive_stat)),
                               (str(manifest_path), c["identity"](manifest_stat))] + [
                (str(c["DEPENDENCY_SOURCE"] / name), expected) for name, expected in dependency_identities]:
            require(baseline_files[path] == expected, "original observation differs from admitted identity")
        baseline_directories = {x["path"]: x["identity"] for x in original_baseline["directories"]}
        require(baseline_directories[str(c["DEPENDENCY_SOURCE"])] ==
                (dependency_stat.st_dev, dependency_stat.st_ino, dependency_stat.st_mode), "original root identity differs")
        c["check_active_inputs"](original_baseline, {"logical": 0, "allocated": 0}, plan)
        encoded_plan = c["canonical"]({"slots": fixed, "plan": plan, "originals_plan": originals_plan,
                                        "originals_observed": original_baseline})
        require(len(encoded_plan) <= c["MANIFEST_CAP"], "complete original plan evidence exceeded")
        actions.write(job / "plan.json", encoded_plan)
        actions.write(job / "catalogue.json", manifest_raw)
        actions.write(job / "archive.tar", raw)
        for prefix, entries in (("code", manifest["code"]), ("dependencies", manifest["dependencies"])):
            (job / prefix).mkdir(mode=0o755)
            for item in entries:
                window.check(190)
                destination = job / prefix / item["path"]
                destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                if prefix == "code":
                    actions.write(destination, members[item["path"]])
                else:
                    actions.copy(c["copy_file"], c["DEPENDENCY_SOURCE"] / item["path"], destination, item)
        (job / "attempts").mkdir(mode=0o755)
        for tour in ("ATP", "WTA"):
            directory = job / "attempts" / tour
            directory.mkdir(mode=0o755)
            for attempt in ("positive", "late-cleanup") if tour == "ATP" else ("positive",):
                (directory / attempt).mkdir(mode=0o700)
                os.chown(directory / attempt, 65534, 65534)
            # Only the fresh private attempt directories need child write rights.
        boundaries = []
        completed_views = {}
        def recheck():
            window.check()
            require((job.lstat().st_dev, job.lstat().st_ino) == (job_info.st_dev, job_info.st_ino), "job directory replaced")
            for fd, initial, path in ((archive_fd, archive_stat, archive), (dependency_fd, dependency_stat, c["DEPENDENCY_SOURCE"]),
                                       (manifest_fd, manifest_stat, manifest_path)):
                require(c["identity"](os.fstat(fd)) == c["identity"](initial) == c["identity"](path.lstat()), "held initial input changed")
            require(c["data_bytes"](manifest_path, c["MANIFEST_CAP"], args["--manifest-sha256"]) == manifest_raw, "initial manifest changed")
            require(c["identity"](archive.lstat()) == archive_info, "initial archive replaced")
            require(c["file_record"](archive, c["ARCHIVE_CAP"])["sha256"] == manifest["archive"]["sha256"], "initial archive changed")
            require(c["walk"](c["DEPENDENCY_SOURCE"], c["PACKAGES"]) == manifest["dependencies"], "dependency inputs changed")
            for name, expected in dependency_identities:
                require(c["identity"]((c["DEPENDENCY_SOURCE"] / name).lstat()) == expected, "dependency input identity changed")
            require(c["walk"](job / "code") == manifest["code"], "sealed code changed")
            require(c["walk"](job / "dependencies") == manifest["dependencies"], "sealed dependencies changed")
            for tour, view in completed_views.items():
                require(c["walk"](job / "attempts" / tour) == view, "previous child private outputs changed")
            observed = c["workspace_sample"](job, fixed, plan["metadata_reservation"])
            originals = c["sample_original_inputs"](originals_plan, previous=original_baseline)
            active = c["check_active_inputs"](originals, observed, plan)
            values = observed["files"]
            logical, allocated = observed["logical"], observed["allocated"]
            free = os.fstatvfs(job_fd).f_bavail * os.fstatvfs(job_fd).f_frsize
            require(max(logical, allocated) <= plan["total"] and free >= 4 * 1024**3 + plan["total"] - logical, "complete union physical/free observation failed")
            require(len(boundaries) < 8, "parent boundary count exceeded")
            boundaries.append({"logical": logical, "allocated": allocated, "free": free,
                               "originals": {key: originals[key] for key in
                                   ("logical", "allocated", "metadata_logical", "metadata_allocated")},
                               "originals_sha256": hash_value(originals), "simultaneous_active": active,
                               "inventory_sha256": hash_value(values), "boot_ns": window.check()})
        def retain(tour, result):
            native = dataclasses.asdict(result)
            native["stdout_prefix"] = result.stdout_prefix.hex()
            native["stderr_prefix"] = result.stderr_prefix.hex()
            native["output_encoding"] = "hex-exact-retained-bytes"
            encoded = c["canonical"](native)
            require(len(encoded) <= 3 * MIB, "retained native output bound exceeded")
            actions.write(job / (tour + "-output.json"), encoded)
            completed_views[tour] = c["walk"](job / "attempts" / tour)
        def custody(exc):
            nonlocal retained
            try:
                retained = handle.stop_unmeasured()
            except BaseException:
                pass
            custody_stop(exc, lambda report: write_new(job / "custody.json", c["canonical"](report)))
        results = orchestrate(supervisor, worker=job / "code/tests/native_context_chain_worker.py",
            attempt_root=job / "attempts", window=window, recheck=recheck, retain=retain, custody=custody, admit=actions.check)
        retained = handle.stop_unmeasured()
        require(retained.status == "stopped" and retained.charged_cpu_ns == 300 * 10**9, "full diagnostic charge not retained")
        report = {"status": "children-complete-external-terminal-observation-required", "native_pass": False,
            "scope": "small ATP/WTA only; no native quota/global-C/B/runtime-closure certificate",
            "identity": dataclasses.asdict(identity), "reservation": dataclasses.asdict(ticket),
            "reviewed_stdin_sha256": args["--launcher-sha256"],
            "accounting": dataclasses.asdict(retained), "parent_boot_start_ns": window.start,
            "parent_boot_observed_ns": window.check(), "parent_cpu_observed_ns": time.process_time_ns(),
            "boundaries": boundaries, "children": results}
        encoded = c["canonical"](report)
        require(len(encoded) <= MIB, "parent report bound exceeded")
        write_new(job / "report.json", encoded)
        os.fsync(job_fd)
        window.check()
    except BaseException as exc:
        if retained is None:
            try:
                retained = handle.stop_unmeasured()
            except BaseException:
                pass  # outstanding durable ticket remains fully charged
        failure = {"status": "STOP", "exception": type(exc).__name__, "native_pass": False,
                   "retained_cpu_ns": 300 * 10**9, "cleanup": "retain-all-no-retry"}
        if isinstance(exc, supervisor.UnreapedChild):
            failure.update({"pid": exc.pid, "pidfd": exc.pidfd, "custody": "UNREAPED-OPERATOR-REQUIRED"})
        try:
            write_new(job / "failure.json", c["canonical"](failure))
            os.fsync(job_fd)
        finally:
            raise
    finally:
        try:
            inputs.close()
        finally:
            try:
                handle.close()
            finally:
                os.close(job_fd)


if __name__ == "__main__":
    main(sys.argv[1:])
