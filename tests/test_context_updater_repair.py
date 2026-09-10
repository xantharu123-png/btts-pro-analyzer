"""Updater-only repair RED contract: real local bytes, no VPS or app deployment.

The implementation does not exist yet.  The requested internal seams are
``repair_main`` (Bash orchestration) and ``repair_data`` (stdlib-only Python,
import-safe except for its __main__ dispatch).  No test override is added to
the production CLI.  Unix owner/mode and directory-fsync emulation below is
explicitly NOT native Linux DAC/crash-durability evidence.
"""
import hashlib
import os
from pathlib import Path
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


def source_function(name):
    assert INSTALLER.is_file(), "missing Task3 updater-only repair installer"
    source = INSTALLER.read_text(encoding="utf-8")
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
    target.chmod(0o755)
    candidate.chmod(0o644)
    namespace.update(INSTALLED_UPDATER=target, NEW_UPDATER=candidate,
        REPAIR_STATE_DIR=state, EXPECTED_OLD_SHA256=hashlib.sha256(OLD).hexdigest())
    operations = []
    injected = False
    fd_paths = {}
    real_os = namespace["os"]
    fixture_os = SimpleNamespace(**{name: getattr(real_os, name) for name in dir(real_os)})

    def metadata(info, path):
        if os.name != "nt":
            return info
        values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        path = Path(path)
        # Emulate only Unix DAC, not identity, digest, size, links or file I/O.
        mode = 0o700 if stat.S_ISDIR(info.st_mode) else (0o755 if path == target else 0o600)
        values.update(st_uid=0, st_gid=0, st_mode=stat.S_IFMT(info.st_mode) | mode)
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
        if failure == name and not injected:
            injected = True
            raise Interrupted(name) if crash else OSError(name)

    def sync_file(descriptor):
        path = fd_paths[descriptor]
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
        if is_install:
            trip("after_replace")

    fixture_os.open = open_file
    fixture_os.fstat = lambda fd: metadata(os.stat(fd_paths[fd]), fd_paths[fd]) if fd < 0 else metadata(os.fstat(fd), fd_paths[fd])
    fixture_os.stat = lambda path, **kwargs: metadata(os.stat(path, **kwargs), path)
    fixture_os.lstat = lambda path, **kwargs: metadata(os.lstat(path, **kwargs), path)
    fixture_os.close = lambda fd: None if fd < 0 else os.close(fd)
    fixture_os.fsync = sync_file
    fixture_os.replace = replace_file
    if os.name == "nt":
        fixture_os.geteuid = lambda: 0
        fixture_os.getuid = fixture_os.getgid = lambda: 0
        fixture_os.chown = fixture_os.fchown = lambda *args: None
        fixture_os.fchmod = lambda *args: None
        fixture_os.O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
        fixture_os.O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
    namespace.update(os=fixture_os, Path=FixturePath)
    for name in ("INSTALLED_UPDATER", "NEW_UPDATER", "REPAIR_STATE_DIR"):
        namespace[name] = FixturePath(namespace[name])
    return namespace, target, candidate, state, operations


def restart_transaction(data):
    """Discard all production globals: only on-disk recovery evidence survives."""
    restarted = repair_namespace()
    for name in ("os", "Path", "INSTALLED_UPDATER", "NEW_UPDATER", "REPAIR_STATE_DIR", "EXPECTED_OLD_SHA256"):
        restarted[name] = data[name]
    return restarted


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
