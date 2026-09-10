"""Updater-only repair RED contract: real local bytes, no VPS or app deployment.

The implementation does not exist yet.  The requested internal seams are
``repair_main`` (Bash orchestration) and ``repair_data`` (stdlib-only Python,
import-safe except for its __main__ dispatch).  No test override is added to
the production CLI.  Unix owner/mode and directory-fsync emulation below is
explicitly NOT native Linux DAC/crash-durability evidence.
"""
import hashlib
import ast
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shlex
import shutil
import stat
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/repair_context_updater.sh"
TARGET = "1234567890abcdef1234567890abcdef12345678"
OLD = b"#!/bin/sh\nprintf 'original-updater\\n'\n"
NEW = b"#!/bin/sh\nprintf 'reviewed-updater\\n'\n"
THIRD = b"#!/bin/sh\nprintf 'external-updater\\n'\n"
NEW_SHA = hashlib.sha256(NEW).hexdigest()
PRODUCTION_OLD_SHA = "74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f"
PRODUCTION_HEAD = "2dd1116b68f3d94e9c24338c6c9dff9b01799221"
REMOTE = "https://github.com/xantharu123-png/btts-pro-analyzer.git"


def source_function(name, path=INSTALLER):
    assert path.is_file(), "missing Task3 updater-only repair installer"
    source = path.read_text(encoding="utf-8")
    start = source.find(name + "() {")
    assert start >= 0, f"missing actual repair function: {name}"
    lines, delimiter = [], None
    for line in source[start:].splitlines(keepends=True):
        lines.append(line)
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        match = re.search(r"<<'([^']+)'", line)
        if match:
            delimiter = match[1]
        elif line == "}\n":
            return "".join(lines)
    raise AssertionError(f"unterminated repair function: {name}")


def repair_namespace():
    source = source_function("repair_data")
    start = source.index("<<'PY'\n") + len("<<'PY'\n")
    code = source[start:source.index("\nPY", start)]
    namespace = {"__name__": "isolated_repair_contract"}
    exec(compile(code, str(INSTALLER) + "::repair_data", "exec"), namespace)
    return namespace


def bash():
    candidate = Path("C:/Program Files/Git/bin/bash.exe")
    executable = str(candidate) if candidate.is_file() else shutil.which("bash")
    assert executable, "real Bash required for repair ordering tests"
    return executable


def run_ordering(tmp_path, *, fail=None):
    """Only external privileged/preflight boundaries are doubles; main is real."""
    log = tmp_path / "order.txt"
    functions = source_function("repair_main")
    boundaries = (
        "verify_repair_invocation", "acquire_deploy_lock", "prepare_repair_source",
        "verify_repair_backup", "verify_repair_context", "install_repair_updater",
    )
    script = "set -Eeuo pipefail\n"
    script += f"EVENTS={shlex.quote(log.as_posix())}\n"
    script += 'die() { printf "failure:%s\\n" "$*" >&2; exit 1; }\n'
    for name in boundaries:
        status = "return 41" if name == fail else ":"
        script += f'{name}() {{ printf "%s\\n" {name} >>"$EVENTS"; {status}; }}\n'
    # Any accidental deployment action is observable and fatal, never a no-op.
    script += 'systemctl() { printf "FORBIDDEN systemctl\\n" >>"$EVENTS"; return 99; }\n'
    script += 'apply_trusted_payload() { printf "FORBIDDEN payload\\n" >>"$EVENTS"; return 99; }\n'
    script += 'prepare_challenge_migration_boundary() { printf "FORBIDDEN marker\\n" >>"$EVENTS"; return 99; }\n'
    script += functions
    script += f"\nrepair_main {TARGET} {NEW_SHA}\n"
    result = subprocess.run([bash()], input=script, text=True, capture_output=True, timeout=15)
    events = log.read_text().splitlines() if log.exists() else []
    assert "command not found" not in result.stderr, result.stderr
    return result, events


class Interrupted(BaseException):
    """A crash is not a catchable operational failure; recovery is a later run."""


def transaction_fixture(tmp_path, *, failure=None, crash=False):
    namespace = repair_namespace()
    target = tmp_path / "sbin" / "betboy-update"
    candidate = tmp_path / "source" / "update_server.sh"
    state = tmp_path / "private-state"
    target.parent.mkdir()
    candidate.parent.mkdir()
    target.write_bytes(OLD)
    candidate.write_bytes(NEW)
    evidence = tmp_path / "accepted-evidence.json"
    evidence.write_text(json.dumps({"schema": 1, "commit": TARGET, "updater_sha256": NEW_SHA,
        "status": "accepted", "records": {name: {"path": "/var/private/" + name,
            "sha256": "a" * 64, "size": 1} for name in ("archive", "stage", "report", "production", "restore", "inline", "measurement")}}))
    target.chmod(0o755)
    candidate.chmod(0o644)
    namespace.update(INSTALLED_UPDATER=target, NEW_UPDATER=candidate,
        REPAIR_STATE_DIR=state, PREFLIGHT_EVIDENCE=evidence, EXPECTED_OLD_SHA256=hashlib.sha256(OLD).hexdigest())
    operations = []
    injected = False
    fd_paths = {}
    unix_modes = {target: 0o755, candidate: 0o644}
    real_os = namespace["os"]
    fixture_os = SimpleNamespace(**{name: getattr(real_os, name) for name in dir(real_os)})

    def metadata(info, path):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        path = Path(path)
        # Emulate only Unix DAC, not identity, digest, size, links or file I/O.
        mode = 0o700 if stat.S_ISDIR(info.st_mode) else unix_modes.get(path, 0o600)
        values.update(st_uid=0, st_gid=0, st_mode=stat.S_IFMT(info.st_mode) | mode)
        if os.name == "nt":
            # Windows fd ctime is not Unix inode-change time (native QA is separate).
            values["st_ctime_ns"] = values["st_mtime_ns"]
        return SimpleNamespace(**values)

    class FixturePath(type(Path())):
        def lstat(self):
            return metadata(super().lstat(), self)
        def stat(self, *, follow_symlinks=True):
            return metadata(super().stat(follow_symlinks=follow_symlinks), self)

    def checked_path(path):
        value = Path(path).absolute()
        assert value == tmp_path or tmp_path in value.parents, f"escaped fixture: {value}"
        return value

    def open_file(path, flags, *args, **kwargs):
        value = checked_path(path)
        if flags & os.O_CREAT and args:
            unix_modes[value] = args[0]
        if os.name == "nt" and value.is_dir():
            # Windows cannot os.open/fsync a directory. Keep the request visible.
            descriptor = -(len(fd_paths) + 100)
        else:
            descriptor = os.open(path, flags | getattr(os, "O_BINARY", 0), *args, **kwargs)
        fd_paths[descriptor] = value
        return descriptor

    def trip(name):
        nonlocal injected
        operations.append(name)
        selected = failure == name or failure == (name, operations.count(name))
        if selected and not injected:
            injected = True
            raise Interrupted(name) if crash else OSError(name)

    def sync_file(descriptor):
        path = fd_paths[descriptor]
        operations.append(("fsync_path", str(path)))
        trip("parent_fsync" if path == target.parent else "fsync")
        if descriptor >= 0:
            os.fsync(descriptor)

    def replace_file(source, destination, **kwargs):
        checked_path(source)
        checked_path(destination)
        is_install = Path(destination) == target and Path(source).read_bytes() == NEW
        if is_install:
            trip("before_replace")
        os.replace(source, destination, **kwargs)
        unix_modes[Path(destination)] = unix_modes.pop(Path(source), 0o600)
        if is_install:
            trip("after_replace")

    fixture_os.open = open_file
    fixture_os.fstat = lambda fd: metadata(os.stat(fd_paths[fd]), fd_paths[fd]) if fd < 0 else metadata(os.fstat(fd), fd_paths[fd])
    fixture_os.stat = lambda path, **kwargs: metadata(os.stat(path, **kwargs), path)
    fixture_os.lstat = lambda path, **kwargs: metadata(os.lstat(path, **kwargs), path)
    fixture_os.close = lambda fd: None if fd < 0 else os.close(fd)
    fixture_os.fsync = sync_file
    fixture_os.replace = replace_file
    fixture_os.geteuid = lambda: 0
    fixture_os.getuid = fixture_os.getgid = lambda: 0
    fixture_os.chown = fixture_os.fchown = lambda *args: None
    fixture_os.fchmod = lambda fd, mode: unix_modes.__setitem__(fd_paths[fd], mode)
    if os.name == "nt":
        fixture_os.O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
        fixture_os.O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
        fixture_os.O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
    namespace.update(os=fixture_os, Path=FixturePath)
    for name in ("INSTALLED_UPDATER", "NEW_UPDATER", "REPAIR_STATE_DIR", "PREFLIGHT_EVIDENCE"):
        namespace[name] = FixturePath(namespace[name])
    return namespace, target, candidate, state, operations


def restart_transaction(data):
    """Discard all production globals: only on-disk recovery evidence survives."""
    restarted = repair_namespace()
    for name in ("os", "Path", "INSTALLED_UPDATER", "NEW_UPDATER", "REPAIR_STATE_DIR", "PREFLIGHT_EVIDENCE", "EXPECTED_OLD_SHA256"):
        restarted[name] = data[name]
    return restarted


def guard_functions():
    source = source_function("repair_guard")
    code = source.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    tree = ast.parse(code)
    namespace = {"os": os, "stat": stat, "Path": Path}
    exec(compile(ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)],
                            type_ignores=[]), "guard-functions", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("unsafe", [None, "foreign", "foreign_gid", "group_write", "app_write", "symlink", "root_ancestor", "replaced"])
def test_live_app_parent_principal_is_narrow_and_identity_bound(unsafe):
    facts = {"/": (0, 0, 0o755), "/opt": (0, 0, 0o755),
             "/opt/betboy": (997, 987, 0o750), "/opt/betboy/app": (997, 987, 0o750)}
    if unsafe == "foreign": facts["/opt/betboy"] = (998, 987, 0o750)
    if unsafe == "foreign_gid": facts["/opt/betboy"] = (997, 988, 0o750)
    if unsafe == "group_write": facts["/opt/betboy"] = (997, 987, 0o775)
    if unsafe == "app_write": facts["/opt/betboy/app"] = (997, 987, 0o775)
    if unsafe == "root_ancestor": facts["/opt"] = (997, 987, 0o755)
    calls = {}
    class LivePath(PurePosixPath):
        def lstat(self):
            uid, gid, mode = facts[str(self)]
            calls[str(self)] = calls.get(str(self), 0) + 1
            kind = stat.S_IFLNK if unsafe == "symlink" and str(self) == "/opt/betboy" else stat.S_IFDIR
            inode = 20 + list(facts).index(str(self))
            if unsafe == "replaced" and str(self) == "/opt/betboy" and calls[str(self)] > 1: inode += 10
            return SimpleNamespace(st_dev=1, st_ino=inode, st_mode=kind | mode, st_uid=uid,
                st_gid=gid, st_nlink=2, st_size=0, st_mtime_ns=1, st_ctime_ns=1)
    data = guard_functions()
    data.update(Path=LivePath, pwd=SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=997, pw_gid=987)))
    if unsafe:
        with pytest.raises(SystemExit): data["live_application_identity"]()
    else:
        identity = data["live_application_identity"]()
        assert set(identity) == {"app", "parent"}
        # This must NOT admit the app principal into any root-private domain.
        with pytest.raises(SystemExit): data["ancestors"](LivePath("/opt/betboy"))


def test_recovery_rejects_original_inode_reuse_with_changed_timestamps(tmp_path):
    data, target, _, state, _ = transaction_fixture(tmp_path, failure="before_replace", crash=True)
    with pytest.raises(Interrupted): data["install_updater"](TARGET, NEW_SHA)
    before = target.stat()
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 1000000000))
    journal = (state / "transaction.json").read_bytes()
    with pytest.raises((SystemExit, ValueError, RuntimeError)):
        restart_transaction(data)["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == OLD
    assert (state / "transaction.json").read_bytes() == journal


@pytest.mark.parametrize("barrier_fails", [False, True])
@pytest.mark.parametrize("interruption", ["after_rename", "after_fsync"])
def test_restart_after_rollback_rename_requires_parent_barrier(tmp_path, barrier_fails, interruption):
    data, target, _, state, operations = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted): data["install_updater"](TARGET, NEW_SHA)
    restarted = restart_transaction(data)
    replace = restarted["os"].replace
    def crash_after_rollback(source, destination):
        replace(source, destination)
        if interruption == "after_rename" and Path(destination) == target and target.read_bytes() == OLD:
            raise Interrupted("rollback rename")
    restarted["os"].replace = crash_after_rollback
    original_sync = restarted["sync_directory"]
    def crash_after_barrier(path):
        original_sync(path)
        if interruption == "after_fsync" and path == restarted["INSTALLED_UPDATER"].parent and target.read_bytes() == OLD:
            raise Interrupted("rollback parent fsync")
    restarted["sync_directory"] = crash_after_barrier
    with pytest.raises(Interrupted): restarted["recover_updater"](TARGET, NEW_SHA)
    operations.clear()
    fresh = restart_transaction(restarted)
    sync = fresh["sync_directory"]
    def barrier(path):
        if barrier_fails and path == fresh["INSTALLED_UPDATER"].parent: raise OSError("parent barrier")
        return sync(path)
    fresh["sync_directory"] = barrier
    if barrier_fails:
        with pytest.raises(OSError): fresh["recover_updater"](TARGET, NEW_SHA)
        assert json.loads((state / "transaction.json").read_text())["phase"] == "replacing"
    else:
        assert fresh["recover_updater"](TARGET, NEW_SHA) == "old"
        assert ("fsync_path", str(target.parent)) in operations
        assert json.loads((state / "transaction.json").read_text())["phase"] == "rolled_back"
    assert target.read_bytes() == OLD


@pytest.mark.parametrize("unsafe", [None, "walk", "hardlink", "directory_link"])
def test_capacity_inventory_includes_companions_unicode_and_fails_closed(tmp_path, capsys, unsafe):
    source = source_function("enumerate_backup_sources")
    code = source.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    files = {"main.db": 4096, "main.db-wal": 200000, "main.db-shm": 32768,
             "main.db-journal": 8192, "unicode.ſQLITE-WAL": 3333, ".git/retained.db": 2222}
    for name, size in files.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"x" * size)
    real_walk = os.walk
    def walk(*args, **kwargs):
        if unsafe == "walk": kwargs["onerror"](PermissionError("denied child"))
        yield from real_walk(*args, **kwargs)
    class InventoryPath(type(Path())):
        def lstat(self):
            info = super().lstat()
            values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
            if unsafe == "hardlink" and self.name == "main.db-wal": values["st_nlink"] = 2
            if unsafe == "directory_link" and self.name == ".git": values["st_mode"] = stat.S_IFLNK | 0o755
            return SimpleNamespace(**values)
    tree = ast.parse(code)
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    data = {"os": SimpleNamespace(**{**vars(os), "walk": walk}), "Path": InventoryPath,
            "stat": stat, "sys": SimpleNamespace(argv=["-", str(tmp_path), "bytes"])}
    if unsafe:
        with pytest.raises(SystemExit): exec(compile(tree, "inventory", "exec"), data)
    else:
        exec(compile(tree, "inventory", "exec"), data)
        assert int(capsys.readouterr().out) == (sum(files.values()) + 1023) // 1024


@pytest.mark.parametrize("inventory_fails", [False, True])
def test_actual_preparation_requires_complete_inventory_before_capacity_or_fetch(tmp_path, inventory_fails):
    script = "set -Eeuo pipefail\n"
    script += f"REQUESTED_HEAD={TARGET}\nEXPECTED_NEW_SHA256={NEW_SHA}\nREPAIR_STATE_DIR=/var/private\n"
    script += 'repair_data() { printf "old\\n"; }\nid() { printf "987\\n"; }\n'
    script += 'context_hook_data() { printf "/var/stage\\n"; }\nverify_repair_production() { :; }\n'
    script += 'repair_guard() { if [[ "$1" == backup-dir ]]; then return; fi; '
    script += '[[ "$*" == "capacity /var/stage /var/private/backups 123" ]] || return 97; printf "capacity-called\\n" >&2; printf "999\\n"; }\n'
    script += 'enumerate_backup_sources() { [[ "$*" == bytes ]] || return 98; '
    script += ('printf "partial\\n"; return 42; ' if inventory_fails else 'printf "123\\n"; ') + '}\n'
    script += 'fetch_repair_source() { printf "fetch-called\\n"; exit 0; }\n'
    script += source_function("prepare_repair_source") + '\nprepare_repair_source\n'
    result = subprocess.run([bash()], input=script, text=True, capture_output=True, timeout=15)
    assert "command not found" not in result.stderr
    assert (result.returncode == 0) is (not inventory_fails), result.stderr
    assert ("capacity-called" in result.stderr) is (not inventory_fails)
    assert ("fetch-called" in result.stdout) is (not inventory_fails)


@pytest.mark.parametrize("insufficient", [False, True])
def test_real_sqlite_wal_snapshot_is_covered_by_actual_capacity_reservation(tmp_path, capsys, insufficient):
    import sqlite3
    database = tmp_path / "context_models.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("CREATE TABLE items (payload BLOB)")
        connection.executemany("INSERT INTO items VALUES (zeroblob(1048576))", [()] * 8)
        connection.commit()
        with sqlite3.connect(tmp_path / "snapshot") as destination:
            connection.backup(destination)
        source = source_function("enumerate_backup_sources")
        code = source.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
        tree = ast.parse(code)
        tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        exec(compile(tree, "real-wal-inventory", "exec"), {"os": os, "Path": Path, "stat": stat,
             "sys": SimpleNamespace(argv=["-", str(tmp_path), "bytes"])})
        kib = int(capsys.readouterr().out)
        total = sum(path.stat().st_size for path in tmp_path.glob("context_models.db*"))
        assert kib == (total + 1023) // 1024
        guard = source_function("repair_guard").split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
        branches = [node for node in ast.walk(ast.parse(guard)) if isinstance(node, ast.If)
                    and isinstance(node.test, ast.BoolOp)
                    and 'action == \'capacity\'' in ast.unparse(node.test)]
        assert len(branches) == 1
        class DestinationPath(PurePosixPath):
            def lstat(self): return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0, st_dev=1)
        def need(condition, message):
            if not condition: raise SystemExit(message)
        data = {"args": ["/var/stage", "/var/recovery", str(kib)], "Path": DestinationPath,
                "need": need, "re": re, "stat": stat, "os": SimpleNamespace(statvfs=lambda _: SimpleNamespace(
                    f_bavail=1 if insufficient else 2**40, f_frsize=1))}
        body = ast.Module(body=branches[0].body, type_ignores=[])
        if insufficient:
            with pytest.raises(SystemExit, match="insufficient combined"): exec(compile(body, "capacity", "exec"), data)
        else:
            exec(compile(body, "capacity", "exec"), data)
            maximum = int(capsys.readouterr().out)
            assert maximum == kib * 2048 + 67108864
            assert maximum > (tmp_path / "snapshot").stat().st_size
    finally:
        connection.close()


def test_exact_two_argument_request_has_no_caller_remote_or_target_path():
    data = repair_namespace()
    assert data["parse_request"]([TARGET, NEW_SHA]) == (TARGET, NEW_SHA)


@pytest.mark.parametrize("arguments", [[], [TARGET], [TARGET, NEW_SHA, REMOTE],
    [TARGET[:39], NEW_SHA], [TARGET + "0", NEW_SHA], ["g" * 40, NEW_SHA],
    [TARGET, "f" * 63], [TARGET, "g" * 64], [TARGET, NEW_SHA + "\n"],
    [TARGET + "\n", NEW_SHA], ["--help", NEW_SHA], [TARGET, "/tmp/updater"]])
def test_malformed_or_extra_request_is_rejected(arguments):
    data = repair_namespace()
    with pytest.raises((ValueError, SystemExit)):
        data["parse_request"](arguments)


def test_all_preflight_gates_precede_the_single_installer_action(tmp_path):
    result, events = run_ordering(tmp_path)
    assert result.returncode == 0, result.stderr
    assert events == ["verify_repair_invocation", "acquire_deploy_lock", "prepare_repair_source",
        "verify_repair_backup", "verify_repair_context", "install_repair_updater"]


@pytest.mark.parametrize("gate", ["verify_repair_invocation", "acquire_deploy_lock",
    "prepare_repair_source", "verify_repair_backup", "verify_repair_context"])
def test_failed_invocation_lock_fetch_backup_restore_or_d4_never_replaces(tmp_path, gate):
    result, events = run_ordering(tmp_path, fail=gate)
    assert result.returncode != 0
    assert events[-1] == gate
    assert "install_repair_updater" not in events
    assert not any(event.startswith("FORBIDDEN") for event in events)


def test_exact_new_bytes_are_installed_and_old_copy_is_independent(tmp_path):
    data, target, candidate, state, operations = transaction_fixture(tmp_path)
    data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == NEW
    assert target.stat().st_nlink == 1
    assert candidate.read_bytes() == NEW
    old_copies = [path for path in state.rglob("*") if path.is_file() and path.read_bytes() == OLD]
    assert len(old_copies) == 1
    assert old_copies[0].stat().st_nlink == 1
    assert old_copies[0].stat().st_ino != target.stat().st_ino
    assert "fsync" in operations and "parent_fsync" in operations


@pytest.mark.parametrize("current", [THIRD, NEW])
def test_unknown_or_unjournaled_new_installed_bytes_are_preserved(tmp_path, current):
    data, target, _, _, _ = transaction_fixture(tmp_path)
    target.write_bytes(current)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == current


def test_fetched_candidate_digest_must_equal_reviewed_new_sha(tmp_path):
    data, target, candidate, _, _ = transaction_fixture(tmp_path)
    candidate.write_bytes(THIRD)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == OLD


@pytest.mark.parametrize("failure", ["fsync", "before_replace", "after_replace", "parent_fsync"])
def test_operational_failure_preserves_or_restores_exact_old_bytes(tmp_path, failure):
    data, target, _, _, operations = transaction_fixture(tmp_path, failure=failure)
    with pytest.raises((OSError, ValueError, RuntimeError, SystemExit)):
        data["install_updater"](TARGET, NEW_SHA)
    assert failure in operations
    assert target.read_bytes() == OLD
    assert target.stat().st_nlink == 1


def test_crash_after_replace_has_durable_recoverable_old_copy(tmp_path):
    data, target, _, _, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == NEW
    data = restart_transaction(data)
    data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == OLD
    data = restart_transaction(data)
    data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == OLD
    assert target.stat().st_nlink == 1


def test_recovery_never_overwrites_external_third_hash(tmp_path):
    data, target, _, _, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    target.write_bytes(THIRD)
    data = restart_transaction(data)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == THIRD


def test_completed_same_request_is_idempotent_without_another_exchange(tmp_path):
    data, target, _, _, operations = transaction_fixture(tmp_path)
    data["install_updater"](TARGET, NEW_SHA)
    exchanges = operations.count("after_replace")
    data = restart_transaction(data)
    data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == NEW
    assert operations.count("after_replace") == exchanges == 1


def test_recovery_cannot_rebind_the_journal_to_another_release(tmp_path):
    data, target, _, _, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    data = restart_transaction(data)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["recover_updater"]("f" * 40, NEW_SHA)
    assert target.read_bytes() == NEW


def test_hardlinked_installed_updater_is_rejected_without_changing_either_name(tmp_path):
    data, target, _, _, _ = transaction_fixture(tmp_path)
    alias = target.parent / "external-link"
    os.link(target, alias)
    assert target.stat().st_nlink == 2
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == alias.read_bytes() == OLD


def test_missing_installed_updater_is_not_treated_as_a_first_install(tmp_path):
    data, target, _, _, _ = transaction_fixture(tmp_path)
    target.unlink()
    with pytest.raises((OSError, ValueError, RuntimeError, SystemExit)):
        data["install_updater"](TARGET, NEW_SHA)
    assert not target.exists()


def test_corrupted_old_copy_cannot_be_used_as_rollback_authority(tmp_path):
    data, target, _, state, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    old_copies = [path for path in state.rglob("*") if path.is_file() and path.read_bytes() == OLD]
    assert len(old_copies) == 1
    old_copies[0].write_bytes(THIRD)
    data = restart_transaction(data)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == NEW


def test_corrupted_durable_journal_cannot_be_recreated_as_success(tmp_path):
    data, target, _, state, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    journals = list(state.glob("*.json"))
    assert journals, "an on-disk journal must precede the first replacement"
    for journal in journals:
        journal.write_bytes(b"{invalid-journal")
    data = restart_transaction(data)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == NEW


@pytest.mark.parametrize("payload", [OLD, NEW])
def test_recovery_rejects_external_same_hash_different_inode(tmp_path, payload):
    data, target, _, _, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    external = target.parent / "external"
    external.write_bytes(payload)
    os.replace(external, target)
    data = restart_transaction(data)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == payload


def test_unknown_journal_phase_is_preserved_and_never_authorizes_exchange(tmp_path):
    data, target, _, state, _ = transaction_fixture(tmp_path, failure="after_replace", crash=True)
    with pytest.raises(Interrupted):
        data["install_updater"](TARGET, NEW_SHA)
    journal = state / "transaction.json"
    value = json.loads(journal.read_text())
    value["phase"] = "operator-approved-whatever"
    journal.write_text(json.dumps(value))
    data = restart_transaction(data)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["recover_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == NEW
    assert json.loads(journal.read_text())["phase"] == "operator-approved-whatever"


def test_every_fsync_failure_including_completion_publication_rolls_back(tmp_path):
    control = tmp_path / "control"
    control.mkdir()
    data, _, _, _, operations = transaction_fixture(control)
    data["install_updater"](TARGET, NEW_SHA)
    for index in range(1, operations.count("fsync") + 1):
        case = tmp_path / f"fsync-{index}"
        case.mkdir()
        data, target, _, _, _ = transaction_fixture(case, failure=("fsync", index))
        with pytest.raises((OSError, ValueError, RuntimeError, SystemExit)):
            data["install_updater"](TARGET, NEW_SHA)
        assert target.read_bytes() == OLD, f"fsync #{index} left replacement installed"
        assert target.stat().st_nlink == 1


def test_existing_private_state_entry_parent_is_fsynced_before_first_exchange(tmp_path):
    data, target, _, state, operations = transaction_fixture(tmp_path)
    state.mkdir()
    data["install_updater"](TARGET, NEW_SHA)
    before_exchange = operations[:operations.index("before_replace")]
    assert ("fsync_path", str(state.parent)) in before_exchange
    assert ("fsync_path", str(state)) in before_exchange
    assert target.read_bytes() == NEW


SHARED_FUNCTIONS = (
    "acquire_deploy_lock", "as_betboy", "root_git", "git_betboy", "trusted_file",
    "target_payload_file", "verify_root_owned_file", "parse_marker_state",
    "create_trusted_manifests", "context_hook_data", "context_hook_command",
    "verification_launcher_source", "configure_context_phase", "prepare_verification_launcher",
    "verify_backup_archive", "capture_root_verifier",
    "produce_update_backup", "enumerate_backup_sources",
)


def test_frozen_reviewed_preflight_algorithms_are_copied_without_drift():
    # Deliberate supply-chain parity gate, not a substitute for behavior tests.
    updater = ROOT / "deploy/update_server.sh"
    assert hashlib.sha256(updater.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == \
        "4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19"
    for name in SHARED_FUNCTIONS:
        assert source_function(name) == source_function(name, updater), name


def test_all_embedded_python_programs_compile_without_running_root_code():
    for name in (*SHARED_FUNCTIONS, "repair_data", "repair_guard", "measure_repair_d4"):
        source = source_function(name)
        if "<<'PY'\n" in source:
            start = source.index("<<'PY'\n") + len("<<'PY'\n")
            compile(source[start:source.index("\nPY", start)], name, "exec")


@pytest.mark.parametrize("failure", [None, "download", "commit", "blob"])
def test_real_fetch_gate_requires_exact_remote_tip_and_blob(tmp_path, failure):
    source = tmp_path / "source"
    source.mkdir()
    raw = tmp_path / "remote-blob"
    raw.write_bytes(THIRD if failure == "blob" else NEW)
    fetched = "f" * 40 if failure == "commit" else TARGET
    harness = "set -Eeuo pipefail\nPATH=/usr/bin:/bin\n"
    for name, value in {"STAGE_DIR": tmp_path.as_posix(), "TRUSTED_TREE": source.as_posix(),
        "REPOSITORY_URL": REMOTE, "REQUESTED_HEAD": TARGET, "EXPECTED_NEW_SHA256": NEW_SHA,
        "FETCHED": fetched, "BLOB": raw.as_posix()}.items():
        harness += f"{name}={shlex.quote(value)}\n"
    harness += 'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
    harness += 'root_git() {\n'
    harness += 'if [[ "$1" == init ]]; then [[ "$*" == "init --quiet $TRUSTED_TREE" ]]; return; fi\n'
    harness += '[[ "$1" == -C && "$2" == "$TRUSTED_TREE" ]] || return 90\nshift 2\n'
    harness += f'if [[ "$1" == fetch ]]; then [[ "$*" == "fetch --quiet --no-tags {REMOTE} refs/heads/main" ]] || return 91; '
    harness += ('return 42; ' if failure == "download" else 'return 0; ') + 'fi\n'
    harness += 'case "$*" in "rev-parse FETCH_HEAD") printf "%s\\n" "$FETCHED";; '
    harness += '"cat-file blob $REQUESTED_HEAD:deploy/update_server.sh") command cat "$BLOB";; *) return 92;; esac\n}\n'
    harness += source_function("fetch_repair_source")
    harness += '\nfetch_repair_source\nprintf "accepted-fetch\\n"\n'
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=15)
    assert "command not found" not in result.stderr, result.stderr
    assert (result.returncode == 0) is (failure is None), result.stderr
    assert ("accepted-fetch" in result.stdout) is (failure is None)


@pytest.mark.skipif(os.name == "nt", reason="real flock needs Linux; Windows gate-order coverage is separate")
def test_real_deploy_flock_rejects_contention_then_releases(tmp_path):
    import fcntl
    lock = tmp_path / "deploy.lock"
    lock.touch()
    script = "set -Eeuo pipefail\nDEPLOY_LOCK=" + shlex.quote(str(lock)) + "\n"
    # Root pathname/principal validation is separately native-reviewed. Here
    # only that boundary is bypassed; the actual Bash FD and flock remain real.
    script += '/usr/bin/python3() { :; }\ndie() { printf "%s\\n" "$*" >&2; exit 1; }\n'
    script += source_function("acquire_deploy_lock") + '\nacquire_deploy_lock\nprintf "lock-acquired\\n"\n'
    with lock.open("rb") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run([bash()], input=script, text=True, capture_output=True, timeout=15)
        assert result.returncode != 0
        assert "already holds the deploy lock" in result.stderr
        assert "lock-acquired" not in result.stdout
    result = subprocess.run([bash()], input=script, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "lock-acquired" in result.stdout


def measurement_namespace():
    source = source_function("measure_repair_d4")
    start = source.index("<<'PY'\n") + len("<<'PY'\n")
    namespace = {"__name__": "measurement_contract"}
    exec(compile(source[start:source.index("\nPY", start)], "repair-measurement", "exec"), namespace)
    return namespace


def valid_measurement():
    return {"schema": 1, "target_commit": TARGET, "updater_sha256": NEW_SHA,
        "database_sha256": "b" * 64, "report_sha256": "c" * 64, "exit_code": 2,
        "wall_seconds": 120.5, "cpu_seconds": 119.0, "peak_rss_bytes": 350 * 1024**2}


def test_measured_exact_input_within_profile_is_accepted():
    data = measurement_namespace()
    data["accept_measurement"](valid_measurement(), TARGET, NEW_SHA, "b" * 64, "c" * 64)


@pytest.mark.parametrize("field,value", [("peak_rss_bytes", 1024**3), ("wall_seconds", 300.0),
    ("cpu_seconds", 300.0), ("exit_code", -9), ("peak_rss_bytes", True),
    ("wall_seconds", float("nan")), ("wall_seconds", -1), ("target_commit", "f" * 40),
    ("updater_sha256", "f" * 64), ("database_sha256", "f" * 64),
    ("report_sha256", "f" * 64), ("schema", True)])
def test_missing_foreign_or_overbudget_measurement_never_authorizes_install(field, value):
    data = measurement_namespace()
    evidence = valid_measurement()
    evidence[field] = value
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["accept_measurement"](evidence, TARGET, NEW_SHA, "b" * 64, "c" * 64)


def test_incomplete_measurement_is_not_an_accepted_report():
    data = measurement_namespace()
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        data["accept_measurement"]({}, TARGET, NEW_SHA, "b" * 64, "c" * 64)


@pytest.mark.parametrize("defect", ["missing", "wrong-target", "wrong-digest", "missing-measurement"])
def test_no_exchange_without_matching_complete_preflight_evidence(tmp_path, defect):
    data, target, _, _, operations = transaction_fixture(tmp_path)
    evidence = Path(data["PREFLIGHT_EVIDENCE"])
    value = json.loads(evidence.read_text())
    if defect == "missing":
        evidence.unlink()
    else:
        if defect == "wrong-target": value["commit"] = "f" * 40
        elif defect == "wrong-digest": value["updater_sha256"] = "f" * 64
        else: del value["records"]["measurement"]
        evidence.write_text(json.dumps(value))
    with pytest.raises((OSError, ValueError, RuntimeError, SystemExit)):
        data["install_updater"](TARGET, NEW_SHA)
    assert target.read_bytes() == OLD
    assert "after_replace" not in operations


def test_repair_backup_wrapper_uses_fresh_online_full_restore_route(tmp_path):
    events = tmp_path / "backup-events"
    harness = "set -Eeuo pipefail\n"
    for name, value in {"RECOVERY_BACKUP_DIR": "/private/backups", "STAGE_DIR": "/var/lib/betboy-context-update.fixture1",
        "REQUESTED_HEAD": TARGET, "EXPECTED_PRODUCTION_HEAD": PRODUCTION_HEAD,
        "EVENTS": events.as_posix()}.items():
        harness += f"{name}={shlex.quote(value)}\n"
    harness += 'produce_update_backup() { printf "%s\\n" "$@" >"$EVENTS"; }\n'
    harness += source_function("verify_repair_backup") + "\nverify_repair_backup\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert events.read_text().splitlines() == ["online",
        "/var/lib/betboy-context-update.fixture1/backup-online-work",
        f"/private/backups/repair-{TARGET}-betboy-context-update.fixture1.zip", PRODUCTION_HEAD]


@pytest.mark.parametrize("failure", [None, "stage", "measure", "finish"])
def test_measured_d4_and_closed_report_both_precede_final_production_recheck(tmp_path, failure):
    events = tmp_path / "d4-events"
    harness = "set -Eeuo pipefail\nCONTEXT_STAGE_DIR=/private/context\nPREFLIGHT_BACKUP=/private/fresh.zip\n"
    harness += f"EVENTS={shlex.quote(events.as_posix())}\n"
    harness += 'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
    harness += 'context_hook_data() { printf "%s\\n" "$1" >>"$EVENTS"; '
    harness += (f'[[ "$1" != {failure} ]] || return 41; ' if failure in {"stage", "finish"} else '')
    harness += 'if [[ "$1" == stage ]]; then printf "present\\n"; fi; }\n'
    harness += 'measure_repair_d4() { printf "measure\\n" >>"$EVENTS"; '
    harness += ('return 42; ' if failure == "measure" else 'printf "2\\n"; ') + '}\n'
    harness += 'verify_repair_production() { printf "production\\n" >>"$EVENTS"; }\n'
    harness += source_function("verify_repair_context") + "\nverify_repair_context\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=15)
    observed = events.read_text().splitlines()
    assert (result.returncode == 0) is (failure is None), result.stderr
    if failure is None:
        assert observed == ["stage", "measure", "finish", "production"]
    else:
        assert "production" not in observed
