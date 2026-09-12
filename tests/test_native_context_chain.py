"""Task57 protocol tests. Portable fixtures are not native kernel evidence."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


HERE = Path(__file__).parent


def module(name):
    path = HERE / (name + ".py")
    assert path.is_file(), "Task57 implementation is missing"
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as target:
        for name, data, kind in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = len(data)
            target.addfile(item, io.BytesIO(data))
    return stream.getvalue()


def entry(name, raw):
    return {"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def test_plan_predeclares_three_attempts_without_reset_allowance():
    c = module("native_context_chain_catalogue")
    plan = c.attempt_slots()
    assert len(plan) == 57
    assert sum(plan.values()) == 229638144
    assert plan["ATP/positive/whole-job/corpus/receipt-additions.bin"] == 1048576
    assert plan["ATP/late-cleanup/legacy-setup/context.db-journal"] == 4194304
    assert plan["WTA/positive/whole-job/new-consumers/consumers.sqlite-journal"] == 4194304
    assert c.resource_plan(10000, 20000, 30000)["attempt_reservation"] == 235929600
    with pytest.raises(c.ChainError):
        c.resource_plan(10000, 4 * 1024**3, 30000)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "link", "changed", "oversized"])
def test_archive_rejects_incomplete_or_nonexact_member(mutation):
    c = module("native_context_chain_catalogue")
    entries = [("a.py", b"x=1\n", tarfile.REGTYPE)]
    expected = [entry("a.py", b"x=1\n")]
    if mutation == "missing":
        entries = []
    elif mutation == "extra":
        entries.append(("b.py", b"", tarfile.REGTYPE))
    elif mutation == "duplicate":
        entries *= 2
    elif mutation == "link":
        entries[0] = ("a.py", b"x=1\n", tarfile.SYMTYPE)
    elif mutation == "changed":
        entries[0] = ("a.py", b"x=2\n", tarfile.REGTYPE)
    else:
        expected[0]["size"] = 1
    with pytest.raises(c.ChainError):
        c.archive_members(archive(entries), expected)


def test_archive_complete_roundtrip_and_path_escape_rejection():
    c = module("native_context_chain_catalogue")
    raw = archive([("a.py", b"x=1\n", tarfile.REGTYPE)])
    assert c.archive_members(raw, [entry("a.py", b"x=1\n")]) == {"a.py": b"x=1\n"}
    for value in ("../a.py", "/a.py", "a//b.py", "a/./b.py", "a\\b.py"):
        with pytest.raises(c.ChainError):
            c.relative(value)


def test_copy_retains_failed_candidate_and_rejects_changed_input(tmp_path):
    c = module("native_context_chain_catalogue")
    source = tmp_path / "source"
    source.write_bytes(b"abcd")
    target = tmp_path / "target"
    with pytest.raises(c.ChainError):
        c.copy_file(source, target, entry("source", b"abce"))
    assert target.read_bytes() == b"abcd"
    with pytest.raises(FileExistsError):
        c.copy_file(source, target, entry("source", b"abcd"))


def test_copy_rejects_oversize_before_destination_write(tmp_path):
    c = module("native_context_chain_catalogue")
    source = tmp_path / "source"
    source.write_bytes(b"abcde")
    with pytest.raises(c.ChainError):
        c.copy_file(source, tmp_path / "target", entry("source", b"abcd"))
    assert not (tmp_path / "target").exists()


def test_duplicate_json_and_closed_cli_are_rejected():
    c = module("native_context_chain_catalogue")
    with pytest.raises(c.ChainError):
        c.decode(b'{"x":1,"x":2}')
    p = module("native_context_chain")
    for args in ([], ["--worker", "/arbitrary.py"], ["--tour", "WTA"], ["--retry"]):
        with pytest.raises(p.ChainError):
            p.arguments(args)


def test_parent_never_accepts_stopped_unknown_or_over_budget_result():
    p = module("native_context_chain")
    from types import SimpleNamespace
    good = dict(exit_code=0, stop_reason=None, child_cpu_ns=1, elapsed_ns=1,
                peak_rss_bytes=1, observed_output_bytes=0, stdout_prefix=b"", stderr_prefix=b"",
                minimum_free_bytes=4 * 1024**3, kernel_readback=None)
    for change in ({}, {"stop_reason": "unknown"}, {"child_cpu_ns": 90000000001},
                   {"peak_rss_bytes": 1024**3}, {"observed_output_bytes": 1048577}):
        with pytest.raises(p.ChainError):
            p.accept_result(SimpleNamespace(**(good | change)), "ATP")


def test_worker_refuses_unprotected_or_optimized_entry_before_import(tmp_path):
    w = module("native_context_chain_worker")
    with pytest.raises(w.ChainError):
        w.require_guard()
    with pytest.raises(w.ChainError):
        w.parse_arguments(["ATP", str(tmp_path), "unexpected"])


def test_unknown_empty_directory_and_linked_source_are_rejected(tmp_path):
    c = module("native_context_chain_catalogue")
    assert hasattr(c, "workspace_sample"), "whole namespace observation is missing"
    (tmp_path / "unplanned").mkdir()
    with pytest.raises(c.ChainError):
        c.workspace_sample(tmp_path, {"allowed/file": 100}, 1048576)


def test_actual_fixed_driver_runs_task54_and_retains_real_rollback(tmp_path):
    w = module("native_context_chain_worker")
    assert hasattr(w, "invoke_cases"), "direct actual Task54 invocation interface is missing"
    for tour in ("ATP", "WTA"):
        root = tmp_path / tour
        root.mkdir()
        (root / "positive").mkdir()
        if tour == "ATP":
            (root / "late-cleanup").mkdir()
        observed = []
        result = w.invoke_cases(tour, root, lambda label: observed.append(label))
        assert len(json.dumps(result, allow_nan=False)) < 1048576
        assert result["properties"]["tour"] == tour
        assert result["properties"]["union_reserved_bytes"] == 78643200
        assert len(result["properties"]["snapshot_key"]) == 64
        assert "positive-reopened" in observed
        assert result["late_cleanup"] == ({"accepted": False, "directory": "late-cleanup",
                 "cold_reopen": "no-consumer-tables"} if tour == "ATP" else None)
        assert (root / "positive/whole-job/new-consumers/consumers.sqlite").is_file()
        # Parser-only fixture wraps REAL callable output; the native counters
        # below are synthetic, explicitly not a guard/kernel observation.
        p = module("native_context_chain")
        from types import SimpleNamespace
        payload = {"format": "betboy-native-context-chain-worker-v1", "tour": tour, "phase": "complete",
            "state": {"pid": 321, "uid": 65534, "gid": 65534, "assertions": True}, **result,
            "samples": [{"boundary": label, "files": [], "directories": [], "logical": 0,
                         "allocated": 0, "free": 4294967296, "unspent_conservative": 0} for label in observed],
            "acceptance_callable": "5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649",
            "task54_m1": "new-original-created-at-direct-assertion-deferred",
            "native_libraries_observation": "SYNTHETIC parser fixture", "python_file_observations": {"fixture": 1}}
        raw = json.dumps(payload, allow_nan=False).encode() + b"\n"
        native = dict(exit_code=0, stop_reason=None, child_cpu_ns=1, elapsed_ns=1, peak_rss_bytes=1,
            observed_output_bytes=len(raw), stdout_prefix=raw, stderr_prefix=b"", minimum_free_bytes=4294967296,
            kernel_readback=SimpleNamespace(pid=321, uid=65534, gid=65534, cpu_seconds=90, file_size_bytes=4194304))
        assert p.accept_result(SimpleNamespace(**native), tour)["properties"]["snapshot_key"] == result["properties"]["snapshot_key"]
        for change in ({"stop_reason": "unknown"}, {"child_cpu_ns": 90000000001},
                       {"peak_rss_bytes": 1073741824}, {"observed_output_bytes": 1048577},
                       {"kernel_readback": None}, {"exit_code": 125}):
            with pytest.raises(p.ChainError):
                p.accept_result(SimpleNamespace(**(native | change)), tour)
        if tour == "ATP":
            import sqlite3
            with sqlite3.connect(root / "late-cleanup/whole-job/new-consumers/consumers.sqlite") as db:
                assert db.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []


def test_kernel_start_parser_uses_start_tick_not_import_stopwatch():
    p = module("native_context_chain")
    # The 20th field after the closing comm is kernel field 22/starttime.
    raw = b"123 (name with ) parens) " + b" ".join([b"S"] + [b"0"] * 18 + [b"250"]) + b"\n"
    assert p.boot_start(raw, 100, 123) == 2500000000
    with pytest.raises(p.ChainError):
        p.boot_start(raw, 100, 124)


def test_manifest_requires_exact_owner_pins_roots_and_plan():
    c = module("native_context_chain_catalogue")
    code = sorted([entry(n, (HERE.parent / n).read_bytes()) for n in c.REQUIRED], key=lambda x: x["path"])
    deps = sorted([entry(n if n.endswith(".py") else n + "/member", b"") for n in c.PACKAGES], key=lambda x: x["path"])
    manifest = {"format": c.FORMAT, "commit": "a" * 40, "archive": {"size": 0, "sha256": "b" * 64},
        "code": code, "dependencies": deps, "dependency_source": str(c.DEPENDENCY_SOURCE),
        "packages": list(c.PACKAGES), "runtime": {"executable": "/usr/bin/python3.12", "executable_sha256": "c" * 64,
            "python": "observed", "kernel": [], "stdlib_search_path": [],
            "closure_status": "observed-system-runtime-not-transitive-B-closure"},
        "plan": c.resource_plan(0, sum(x["size"] for x in code), 0)}
    assert c.validate_manifest(manifest, "a" * 40) is manifest
    import copy
    for mutate in (lambda m: m["dependencies"].pop(),
                   lambda m: m["code"].append(dict(m["code"][0])),
                   lambda m: m["plan"].update(retained_cpu_ns=270000000000),
                   lambda m: m.update(worker="unreviewed.py"),
                   lambda m: next(x for x in m["code"] if x["path"] == c.TASK54).update(sha256="f" * 64)):
        changed = copy.deepcopy(manifest)
        mutate(changed)
        with pytest.raises(c.ChainError):
            c.validate_manifest(changed, "a" * 40)


def test_broken_child_evidence_never_substitutes_for_real_reopen():
    p = module("native_context_chain")
    from types import SimpleNamespace
    body = {"format": "betboy-native-context-chain-worker-v1", "tour": "WTA", "phase": "complete",
            "state": {"pid": 321, "uid": 65534, "gid": 65534, "assertions": True},
            "late_cleanup": None, "samples": [{}] * 7 + [{"boundary": "terminal-quiescent"}]}
    raw = json.dumps(body).encode() + b"\n"
    rb = SimpleNamespace(pid=321, uid=65534, gid=65534, cpu_seconds=90, file_size_bytes=4194304)
    result = SimpleNamespace(exit_code=0, stop_reason=None, child_cpu_ns=1, elapsed_ns=1,
        peak_rss_bytes=1, observed_output_bytes=len(raw), stdout_prefix=raw, stderr_prefix=b"",
        minimum_free_bytes=4 * 1024**3, kernel_readback=rb)
    with pytest.raises(p.ChainError):
        p.accept_result(result, "WTA")


def test_orchestration_unknown_child_stops_without_launching_second_case(tmp_path):
    p = module("native_context_chain")
    assert hasattr(p, "run_cases"), "portable fixed orchestration boundary is missing"
    events = []
    class UnknownChild(RuntimeError):
        pass
    def launch(tour):
        events.append(tour)
        raise UnknownChild("retained custody")
    with pytest.raises(UnknownChild):
        p.run_cases(launch, lambda: events.append("recheck"))
    assert events == ["recheck", "ATP"]


def test_custody_report_failure_keeps_same_pidfd_until_operator_resume(monkeypatch):
    p = module("native_context_chain")
    from types import SimpleNamespace
    events = []
    native_signal = p.signal
    fake_os = SimpleNamespace(getpid=lambda: 456, WNOHANG=1,
        kill=lambda pid, sig: events.append(("stop", pid, sig)),
        wait4=lambda pid, flag: (events.append(("wait4", pid, flag)) or (pid, 0, None)),
        WIFEXITED=lambda status: True, WIFSIGNALED=lambda status: False,
        close=lambda fd: events.append(("close", fd)))
    monkeypatch.setattr(p, "os", fake_os)
    monkeypatch.setattr(p, "signal", SimpleNamespace(SIGSTOP=native_signal.SIGSTOP if hasattr(native_signal, "SIGSTOP") else 19,
        SIGKILL=9, pidfd_send_signal=lambda fd, sig: events.append(("pidfd-kill", fd, sig))))
    def failed_report(_record):
        events.append(("report-failed",))
        raise OSError("retained journal is still charged")
    p.custody_stop(SimpleNamespace(pid=123, pidfd=77), failed_report)
    assert events == [("report-failed",), ("stop", 456, p.signal.SIGSTOP),
                      ("pidfd-kill", 77, 9), ("wait4", 123, 1), ("close", 77)]


def test_linked_input_is_rejected_without_creating_copy(tmp_path):
    c = module("native_context_chain_catalogue")
    import os
    source = tmp_path / "source"
    source.write_bytes(b"abcd")
    os.link(source, tmp_path / "second-name")
    with pytest.raises(c.ChainError):
        c.copy_file(source, tmp_path / "copy", entry("source", b"abcd"))
    assert not (tmp_path / "copy").exists()


def test_real_entry_rejects_optimization_without_importing_product():
    import subprocess
    import sys
    script = ("import runpy,sys; w=runpy.run_path(sys.argv[1]); "
              "w['require_guard']()")
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-O", "-c", script,
                             str(HERE / "native_context_chain_worker.py")], capture_output=True, timeout=10)
    assert result.returncode != 0
    assert b"Task54 requires active Python assertions" in result.stderr
    assert b"ModuleNotFoundError" not in result.stderr


def test_stdin_bootstrap_has_only_fixed_members_and_rejects_byte_substitution():
    c = module("native_context_chain_catalogue")
    assert hasattr(c, "bootstrap_source"), "fixed stdin bootstrap is missing"
    names = ("tests/native_context_chain.py", "tests/native_context_chain_catalogue.py", *c.HELPERS)
    sources = {name: (HERE.parent / name).read_bytes() for name in names}
    script = c.bootstrap_source(sources)
    assert script.startswith(b"# Reviewed Task57 stdlib-only stdin bootstrap")
    # Execute only the generated stub with compile/exec intercepted in the test
    # namespace: verify it selects the fixed parent bytes, not any caller module.
    captured = []
    namespace = {"__name__": "test", "exec": lambda code, scope: captured.append(code),
                 "compile": lambda raw, name, mode: (raw, name, mode)}
    exec(script, namespace)
    assert captured == [(sources["tests/native_context_chain.py"], "<reviewed-task57-parent>", "exec")]
    with pytest.raises(c.ChainError):
        c.bootstrap_source(sources | {"arbitrary.py": b"pass"})
    changed = dict(sources)
    changed["context_preparation_supervisor.py"] += b"\n"
    with pytest.raises(c.ChainError):
        c.bootstrap_source(changed)


def test_data_read_holds_fd_and_rejects_namespace_replacement(tmp_path, monkeypatch):
    c = module("native_context_chain_catalogue")
    assert hasattr(c, "data_bytes"), "FD-bound mutable input reader missing"
    source = tmp_path / "input"
    source.write_bytes(b"abcd")
    assert c.data_bytes(source, 4, hashlib.sha256(b"abcd").hexdigest()) == b"abcd"
    with pytest.raises(c.ChainError):
        c.data_bytes(source, 4, hashlib.sha256(b"abce").hexdigest())
    # Portable path-entry replacement protocol: Windows cannot unlink this
    # open CRT descriptor. Supply a real other inode's stat only at final path
    # readback; this is explicitly not a Linux rename/race observation.
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"abcd")
    replacement_stat = replacement.lstat()
    real_lstat = Path.lstat
    seen = 0
    def changed_entry(path, *args, **kwargs):
        nonlocal seen
        if path == source:
            seen += 1
            if seen >= 2:
                return replacement_stat
        return real_lstat(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", changed_entry)
    with pytest.raises(c.ChainError):
        c.data_bytes(source, 4, hashlib.sha256(b"abcd").hexdigest())


def test_missing_reservation_prevents_first_copy_and_file_writer(tmp_path):
    p = module("native_context_chain")
    from types import SimpleNamespace
    actions = p.ReservedActions(SimpleNamespace(snapshot=lambda: SimpleNamespace(
        status="accounting-open", pending=None, charged_cpu_ns=0)), "not-durable")
    with pytest.raises(p.ChainError):
        actions.write(tmp_path / "must-not-exist", b"x")
    assert not (tmp_path / "must-not-exist").exists()
    def forbidden_copy(*_args):
        pytest.fail("copy entered without the durable reservation")
    with pytest.raises(p.ChainError):
        actions.copy(forbidden_copy, None, None, None)


def test_actual_bootstrap_catalogue_pin_rejects_modified_in_memory_bytes(monkeypatch):
    p = module("native_context_chain")
    raw = (HERE / "native_context_chain_catalogue.py").read_bytes()
    monkeypatch.setattr(p, "_REVIEWED_BOOTSTRAP", {"tests/native_context_chain_catalogue.py": raw + b"\n"}, raising=False)
    with pytest.raises(p.ChainError):
        p.load_catalogue()
    monkeypatch.setattr(p, "_REVIEWED_BOOTSTRAP", {"tests/native_context_chain_catalogue.py": raw})
    assert p.load_catalogue()["TASK54_SHA"] == "5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649"
