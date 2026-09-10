#!/usr/bin/env bash
# One-time reviewed updater replacement. Never deploys application payloads.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /

readonly TRUSTED_UPDATER=/usr/local/sbin/betboy-update
readonly REPOSITORY_URL=https://github.com/xantharu123-png/btts-pro-analyzer.git
readonly APP_DIR=/opt/betboy/app
readonly VENV_DIR=/opt/betboy/venv
readonly DEPLOY_LOCK=/run/betboy-deploy/deploy.lock
readonly REPAIR_STATE_DIR=/var/lib/betboy-updater-repair
readonly LEDGER_HMAC_KEY=/etc/betboy/challenge-ledger-hmac.key
readonly LEDGER_MIGRATION_MARKER=/etc/betboy/challenge-ledger-v2-migrated.json
readonly EXPECTED_PRODUCTION_HEAD=2dd1116b68f3d94e9c24338c6c9dff9b01799221
readonly EXPECTED_OLD_SHA256=74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f
REQUESTED_HEAD="${1:-}"
EXPECTED_NEW_SHA256="${2:-}"
DEPLOY_LOCK_FD=""
MIGRATION_RESUME_TARGET=0
PREVIOUS_HEAD="${EXPECTED_PRODUCTION_HEAD}"

log() {
    printf '[betboy-updater-repair] %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

repair_data() {
    /usr/bin/python3 -I -B - "$@" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

INSTALLED_UPDATER = Path("/usr/local/sbin/betboy-update")
REPAIR_STATE_DIR = Path("/var/lib/betboy-updater-repair")
NEW_UPDATER = REPAIR_STATE_DIR / "candidate"
PREFLIGHT_EVIDENCE = REPAIR_STATE_DIR / "accepted-evidence.json"
EXPECTED_OLD_SHA256 = "74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f"
MAX_EXECUTABLE = 2 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def parse_request(arguments):
    need(len(arguments) == 2, "exact target commit and updater SHA256 required")
    commit, checksum = arguments
    need(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "invalid target commit")
    need(re.fullmatch(r"[0-9a-f]{64}", checksum) is not None, "invalid updater SHA256")
    return commit, checksum


def signature(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def directory(path):
    path = Path(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and info.st_gid == 0
         and not info.st_mode & 0o022, "unsafe root directory")
    if path.parent != path:
        directory(path.parent)
    return info


def sync_directory(path):
    before = signature(directory(path))[:5]
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        need(signature(os.fstat(fd))[:5] == before, "directory replaced before fsync")
        os.fsync(fd)
        need(signature(directory(path))[:5] == before, "directory replaced during fsync")
    finally:
        os.close(fd)


def read_exact(path, *, mode=None, maximum=MAX_EXECUTABLE):
    path = Path(path)
    directory(path.parent)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
         and before.st_nlink == 1 and not before.st_mode & 0o022,
         "not a single root-owned protected regular file")
    need(mode is None or stat.S_IMODE(before.st_mode) == mode, "unexpected file mode")
    need(0 < before.st_size <= maximum, "file outside bounded size")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(signature(os.fstat(fd)) == signature(before), "file replaced before open")
        chunks, total = [], 0
        while chunk := os.read(fd, min(65536, maximum + 1 - total)):
            total += len(chunk)
            need(total <= maximum, "file grew beyond bound")
            chunks.append(chunk)
        need(signature(os.fstat(fd)) == signature(before)
             and signature(path.lstat()) == signature(before), "file changed during read")
        return b"".join(chunks), signature(before)
    finally:
        os.close(fd)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def create_exact(path, raw, mode):
    directory(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, mode)
        remaining = memoryview(raw)
        while remaining:
            count = os.write(fd, remaining)
            need(count > 0, "short write")
            remaining = remaining[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    need(read_exact(path, mode=mode)[0] == raw, "written bytes differ")


def state_directory():
    directory(REPAIR_STATE_DIR.parent)
    try:
        os.mkdir(REPAIR_STATE_DIR, 0o700)
    except FileExistsError:
        pass
    info = directory(REPAIR_STATE_DIR)
    need(stat.S_IMODE(info.st_mode) == 0o700, "repair state must be root-private")
    # An operator-created or crash-surviving directory may not yet have a
    # durable parent entry. Flush it even when mkdir reported EEXIST.
    sync_directory(REPAIR_STATE_DIR.parent)


def journal_path():
    return REPAIR_STATE_DIR / "transaction.json"


def write_journal(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    temporary = REPAIR_STATE_DIR / "transaction.next"
    # A previous incomplete publication is evidence, not silently reusable data.
    if os.path.lexists(temporary):
        previous_raw, _ = read_exact(temporary, mode=0o600, maximum=65536)
        previous = json.loads(previous_raw)
        need(type(previous) is dict and previous.get("commit") == value["commit"]
             and previous.get("old") == value["old"] and previous.get("new") == value["new"]
             and previous.get("phase") in {"prepared", "replacing", "complete", "rolled_back"},
             "unknown interrupted journal candidate preserved")
        os.unlink(temporary)
        sync_directory(REPAIR_STATE_DIR)
    create_exact(temporary, raw, 0o600)
    os.replace(temporary, journal_path())
    sync_directory(REPAIR_STATE_DIR)


def load_journal(commit, checksum):
    def pairs(values):
        result = {}
        for key, value in values:
            need(key not in result, "duplicate journal key")
            result[key] = value
        return result
    raw, _ = read_exact(journal_path(), mode=0o600, maximum=65536)
    value = json.loads(raw, object_pairs_hook=pairs)
    need(type(value) is dict and set(value) == {"schema", "commit", "old", "new", "phase", "original", "parent", "replacement", "rollback", "evidence"}, "invalid journal schema")
    need(type(value["schema"]) is int and value["schema"] == 1
         and value["commit"] == commit and value["new"] == checksum
         and value["old"] == EXPECTED_OLD_SHA256
         and value["phase"] in {"prepared", "replacing", "complete", "rolled_back"}, "journal request/state differs")
    need(type(value["original"]) is list and len(value["original"]) == 9
         and all(type(item) is int for item in value["original"]), "invalid original identity")
    need(type(value["parent"]) is list and len(value["parent"]) == 5
         and all(type(item) is int for item in value["parent"]), "invalid parent identity")
    for name in ("replacement", "rollback"):
        need(value[name] is None or (type(value[name]) is list and len(value[name]) == 6
             and all(type(item) is int for item in value[name])), "invalid exchange inode")
    need(signature(directory(INSTALLED_UPDATER.parent))[:5] == value["parent"], "installed parent changed")
    validate_evidence(value["evidence"], commit, checksum)
    old, _ = read_exact(REPAIR_STATE_DIR / "old-updater", mode=0o600)
    need(digest(old) == value["old"], "old recovery copy differs")
    return value, old


def candidate_path():
    return INSTALLED_UPDATER.parent / ".betboy-update.repair-candidate"


def validate_evidence(value, commit, checksum):
    need(type(value) is dict and set(value) == {"schema", "commit", "updater_sha256", "status", "records"}
         and type(value["schema"]) is int and value["schema"] == 1
         and value["commit"] == commit and value["updater_sha256"] == checksum
         and value["status"] == "accepted", "missing accepted preflight evidence")
    need(type(value["records"]) is dict and set(value["records"]) == {"archive", "stage", "report", "production", "restore", "inline", "measurement"}, "incomplete preflight evidence")
    for record in value["records"].values():
        need(type(record) is dict and set(record) == {"path", "sha256", "size"}
             and type(record["path"]) is str and record["path"].startswith("/var/")
             and re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])) is not None
             and type(record["size"]) is int and record["size"] >= 0, "invalid preflight record")
    return value


def recover_updater(commit, checksum):
    parse_request([commit, checksum])
    state_directory()
    if not os.path.lexists(journal_path()):
        current, _ = read_exact(INSTALLED_UPDATER, mode=0o755)
        need(digest(current) == EXPECTED_OLD_SHA256, "unjournaled installed updater differs")
        return "old"
    value, old = load_journal(commit, checksum)
    current, current_identity = read_exact(INSTALLED_UPDATER, mode=0o755)
    current_hash = digest(current)
    need(current_hash in {value["old"], checksum}, "unknown installed updater preserved")
    if current_hash == checksum:
        need(current_identity[:6] == value["replacement"], "new updater inode was externally replaced")
    else:
        need(current_identity == value["original"] or current_identity[:6] == value["rollback"],
             "old updater inode was externally replaced")
    if value["phase"] == "complete":
        need(current_hash == checksum, "completed updater was externally changed")
        return "complete"
    if current_hash == checksum:
        need(value["phase"] == "replacing", "new updater outside exchange intent")
        temporary = INSTALLED_UPDATER.parent / ".betboy-update.repair-rollback"
        if os.path.lexists(temporary):
            need(read_exact(temporary, mode=0o755)[0] == old, "unknown rollback candidate")
        else:
            create_exact(temporary, old, 0o755)
        sync_directory(INSTALLED_UPDATER.parent)
        value["rollback"] = read_exact(temporary, mode=0o755)[1][:6]
        write_journal(value)
        need(read_exact(INSTALLED_UPDATER, mode=0o755)[1] == current_identity, "updater changed before rollback")
        os.replace(temporary, INSTALLED_UPDATER)
        sync_directory(INSTALLED_UPDATER.parent)
        need(read_exact(INSTALLED_UPDATER, mode=0o755)[0] == old, "rollback bytes differ")
    # Recovery may have stopped immediately after the rollback rename. Even an
    # already-old recognized inode needs this durable directory-entry barrier.
    sync_directory(INSTALLED_UPDATER.parent)
    need(read_exact(INSTALLED_UPDATER, mode=0o755)[0] == old, "rollback bytes differ")
    value["phase"] = "rolled_back"
    write_journal(value)
    return "old"


def install_updater(commit, checksum):
    parse_request([commit, checksum])
    state_directory()
    if os.path.lexists(journal_path()):
        if recover_updater(commit, checksum) == "complete":
            return
        # A repeat must have new full preflight evidence in the shell caller.
        previous, _ = load_journal(commit, checksum)
        need(previous["phase"] == "rolled_back", "unfinished repair")
    current, original = read_exact(INSTALLED_UPDATER, mode=0o755)
    need(digest(current) == EXPECTED_OLD_SHA256, "unexpected installed updater")
    new, _ = read_exact(NEW_UPDATER)
    need(digest(new) == checksum and checksum != EXPECTED_OLD_SHA256, "fetched updater digest differs")
    evidence_raw, _ = read_exact(PREFLIGHT_EVIDENCE, mode=0o600, maximum=65536)
    evidence = validate_evidence(json.loads(evidence_raw), commit, checksum)
    old_path = REPAIR_STATE_DIR / "old-updater"
    if os.path.lexists(old_path):
        need(read_exact(old_path, mode=0o600)[0] == current, "existing recovery copy differs")
    else:
        create_exact(old_path, current, 0o600)
        sync_directory(REPAIR_STATE_DIR)
    value = {"schema": 1, "commit": commit, "old": EXPECTED_OLD_SHA256, "new": checksum,
        "phase": "prepared", "original": original,
        "parent": signature(directory(INSTALLED_UPDATER.parent))[:5],
        "replacement": None, "rollback": None, "evidence": evidence}
    try:
        write_journal(value)
        temporary = candidate_path()
        if os.path.lexists(temporary):
            need(read_exact(temporary, mode=0o755)[0] == new, "unknown existing candidate")
        else:
            create_exact(temporary, new, 0o755)
        sync_directory(INSTALLED_UPDATER.parent)
        need(read_exact(INSTALLED_UPDATER, mode=0o755)[1] == original, "installed updater identity changed")
        value["replacement"] = read_exact(temporary, mode=0o755)[1][:6]
        value["phase"] = "replacing"
        write_journal(value)
        need(read_exact(INSTALLED_UPDATER, mode=0o755)[1] == original, "updater changed immediately before replace")
        os.replace(temporary, INSTALLED_UPDATER)
        sync_directory(INSTALLED_UPDATER.parent)
        need(read_exact(INSTALLED_UPDATER, mode=0o755)[0] == new, "installed replacement differs")
        value["phase"] = "complete"
        write_journal(value)
    except Exception:
        # Recovery refuses unknown hashes or corrupt evidence; do not mask that
        # failure by blindly copying an old pathname over the installed target.
        if value["phase"] == "complete":
            value["phase"] = "replacing"
            write_journal(value)
        recover_updater(commit, checksum)
        raise


if __name__ == "__main__":
    need(os.geteuid() == 0, "repair byte operations require root")
    action, *arguments = sys.argv[1:]
    commit, checksum = parse_request(arguments)
    if action == "parse":
        print(commit, checksum)
    elif action == "recover":
        print(recover_updater(commit, checksum))
    elif action == "install":
        install_updater(commit, checksum)
    else:
        raise SystemExit("unknown repair operation")
PY
}

# BEGIN unchanged Task2 6ba2c68 preflight functions (no updater main).
acquire_deploy_lock() {
    /usr/bin/python3 -I - "${DEPLOY_LOCK}" <<'PY'
import os
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
parent = path.parent
base = parent.parent
base_info = os.lstat(base)
if (
    not stat.S_ISDIR(base_info.st_mode)
    or stat.S_ISLNK(base_info.st_mode)
    or base_info.st_uid != 0
    or base_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
):
    raise SystemExit("deploy lock base directory is unsafe")
try:
    os.mkdir(parent, 0o700)
except FileExistsError:
    pass
parent_info = os.lstat(parent)
if (
    not stat.S_ISDIR(parent_info.st_mode)
    or stat.S_ISLNK(parent_info.st_mode)
    or parent_info.st_uid != 0
    or stat.S_IMODE(parent_info.st_mode) != 0o700
):
    raise SystemExit("deploy lock directory is unsafe")
flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
try:
    descriptor = os.open(path, flags, 0o600)
except FileExistsError:
    descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
try:
    info = os.fstat(descriptor)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != 0
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise SystemExit("deploy lock file is unsafe")
finally:
    os.close(descriptor)
PY
    exec {DEPLOY_LOCK_FD}<>"${DEPLOY_LOCK}"
    flock -n "${DEPLOY_LOCK_FD}" \
        || die "Another BetBoy bootstrap/update process already holds the deploy lock."
}

as_betboy() {
    runuser -u betboy -- "$@"
}

root_git() {
    env -i \
        HOME=/root \
        PATH=/usr/bin:/bin \
        GIT_CONFIG_NOSYSTEM=1 \
        GIT_CONFIG_GLOBAL=/dev/null \
        GIT_NO_REPLACE_OBJECTS=1 \
        GIT_TERMINAL_PROMPT=0 \
        git \
        -c core.hooksPath=/dev/null \
        -c core.fsmonitor=false \
        -c credential.helper= \
        -c http.version=HTTP/1.1 \
        -c protocol.file.allow=never \
        "$@"
}

git_betboy() {
    as_betboy env -i \
        HOME=/opt/betboy \
        PATH=/usr/bin:/bin \
        GIT_CONFIG_NOSYSTEM=1 \
        GIT_CONFIG_GLOBAL=/dev/null \
        GIT_NO_REPLACE_OBJECTS=1 \
        GIT_TERMINAL_PROMPT=0 \
        git \
        -c core.hooksPath=/dev/null \
        -c core.fsmonitor=false \
        -c credential.helper= \
        -c http.version=HTTP/1.1 \
        -c protocol.file.allow=never \
        -C "${APP_DIR}" "$@"
}

trusted_file() {
    local relative="$1"
    local path="${TRUSTED_TREE}/${relative}"
    [[ -f "${path}" && ! -L "${path}" ]] \
        || die "Trusted commit lacks regular file ${relative}."
    printf '%s\n' "${path}"
}

target_payload_file() {
    local relative="$1"
    local path="${TARGET_PAYLOAD}/${relative}"
    local metadata
    [[ -n "${TARGET_PAYLOAD}" && -f "${path}" && ! -L "${path}" ]] \
        || die "Target payload lacks regular file ${relative}."
    metadata=$(stat -c '%U:%G:%a:%h' "${path}")
    [[ "${metadata}" == root:betboy:640:1 ]] \
        || die "Target payload file is not immutable and group-readable: ${relative}."
    printf '%s\n' "${path}"
}

verify_root_owned_file() {
    local path="$1"
    local owner
    local mode
    [[ -f "${path}" && ! -L "${path}" ]] || die "Missing trusted root file: ${path}"
    owner=$(stat -c '%U:%G' "${path}")
    mode=$(stat -c '%a' "${path}")
    [[ "${owner}" == root:root ]] || die "Not root-owned: ${path}"
    (( (8#${mode} & 022) == 0 )) || die "Root file is group/other writable: ${path}"
}

parse_marker_state() {
    /usr/bin/python3 -I - "$1" <<'PY'
import json
import re
import sys

try:
    payload = json.loads(sys.argv[1])
except (TypeError, ValueError) as exc:
    raise SystemExit("migration marker status output is invalid") from exc
if (
    not isinstance(payload, dict)
    or set(payload) != {"previous_head", "status", "target_head"}
    or payload["status"] not in {"in_progress", "complete"}
    or not re.fullmatch(r"[0-9a-f]{40}", str(payload["previous_head"]))
    or not re.fullmatch(r"[0-9a-f]{40}", str(payload["target_head"]))
):
    raise SystemExit("migration marker status output is inconsistent")
print(payload["previous_head"], payload["status"], payload["target_head"])
PY
}

create_trusted_manifests() {
    local manifest_previous="${PREVIOUS_HEAD}"
    if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
        manifest_previous="${MIGRATION_MARKER_PREVIOUS_HEAD}"
    fi
    TARGET_MANIFEST="${STAGE_DIR}/target-manifest.json"
    PREVIOUS_MANIFEST="${STAGE_DIR}/previous-manifest.json"
    TARGET_PAYLOAD="${STAGE_DIR}/target-payload"
    PREVIOUS_PAYLOAD="${STAGE_DIR}/previous-payload"

    /usr/bin/python3 -I - \
        "${TRUSTED_TREE}" "${manifest_previous}" "${TARGET_HEAD}" \
        "${PREVIOUS_MANIFEST}" "${TARGET_MANIFEST}" \
        "${PREVIOUS_PAYLOAD}" "${TARGET_PAYLOAD}" <<'PY'
import hashlib
import json
import os
import re
import subprocess
import sys

repo, previous, target, previous_out, target_out, previous_payload, target_payload = sys.argv[1:]


def git(*args: str) -> bytes:
    env = {
        "HOME": "/root",
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.run(
        [
            "/usr/bin/git",
            "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false",
            "-c", "credential.helper=",
            "-C", repo,
            *args,
        ],
        check=True,
        stdout=subprocess.PIPE,
        env=env,
    ).stdout


def load_tree(revision: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for record in git("ls-tree", "-rz", revision).split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split()
        path = raw_path.decode("utf-8", "strict")
        if (
            mode not in {"100644", "100755"}
            or kind != "blob"
            or path.startswith("/")
            or ".." in path.split("/")
            or any(ord(char) < 32 for char in path)
        ):
            raise SystemExit(f"unsupported tracked entry: {mode} {kind} {path!r}")
        blob = git("cat-file", "blob", oid)
        result[path] = {
            "mode": mode,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "oid": oid,
        }
    return result


def protected(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return bool(
        path == "config.ini"
        or path == ".streamlit/secrets.toml"
        or path.startswith(("runtime_state/", "runtime_reports/", "backups_runtime/"))
        or path == "tennis/data/calibration_watch_latest.json"
        or re.fullmatch(r"logs/pipeline_.*\.log", path)
        or re.search(r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$", name)
        or name == ".env"
    )


old_tree = load_tree(previous)
new_tree = load_tree(target)
for path, entry in new_tree.items():
    if protected(path) and old_tree.get(path) != entry:
        raise SystemExit(
            f"target adds or modifies protected runtime path: {path}"
        )


def write_manifest(path: str, revision: str, tree: dict, other: dict) -> None:
    # A file removed by this revision must not survive as an importable stale file.
    absent = [
        old_path
        for old_path in other
        if old_path not in tree
        and not any(new_path.startswith(old_path + "/") for new_path in tree)
    ]
    payload = {
        "revision": revision,
        "files": {
            name: {"mode": entry["mode"], "sha256": entry["sha256"]}
            for name, entry in tree.items()
        },
        "must_be_absent": sorted(absent),
    }
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
        handle.write("\n")


def write_payload(output: str, tree: dict) -> None:
    os.makedirs(output, mode=0o750)
    for relative, entry in tree.items():
        destination = os.path.join(output, *relative.split("/"))
        os.makedirs(os.path.dirname(destination), mode=0o750, exist_ok=True)
        with open(destination, "xb") as handle:
            handle.write(git("cat-file", "blob", entry["oid"]))
        os.chmod(destination, 0o640)
    for directory, _dirnames, _filenames in os.walk(output):
        os.chmod(directory, 0o750)


write_manifest(previous_out, previous, old_tree, new_tree)
write_manifest(target_out, target, new_tree, old_tree)
write_payload(previous_payload, old_tree)
write_payload(target_payload, new_tree)
PY
    chown root:betboy "${PREVIOUS_MANIFEST}" "${TARGET_MANIFEST}"
    chmod 0640 "${PREVIOUS_MANIFEST}" "${TARGET_MANIFEST}"
    chown -R root:betboy "${PREVIOUS_PAYLOAD}" "${TARGET_PAYLOAD}"
}

context_hook_data() {
    # Privileged boundary: only this installed, stdlib-only inline program.
    # Never import the app, its venv, NumPy or the backup's secret contents here.
    /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
        /usr/bin/timeout --signal=TERM --kill-after=10s 600s \
        /usr/bin/python3 -I -B - "$@" <<'PY'
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import sys
import shutil
import tempfile
import time
import zipfile

MAX_IMAGE = 1024 * 1024 * 1024
MAX_REPORT = 1024 * 1024
PATH_CONTRACT = "710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c"
EXCLUDED = {".codex_test_venv", ".git", ".pytest_cache", ".pytest_tmp", ".venv", "__pycache__", "backups_runtime"}
ALLOWED_LIMITS = {
    "d2-final-source-replay-not-opened", "d1-participation-training-receipts-unresolved",
    "d1-final-source-replay-unavailable", "d1-fit-owning-replay-unavailable",
    "d2-dataset-owning-experiment-unavailable", "d1-case-owning-replay-unavailable",
    "d1-original-replay-context-unavailable", "d2-evaluation-opening-unavailable",
    "d2-approval-evidence-resolution-unavailable", "d3-owning-family-replay-unavailable",
    "d3-owning-source-feature-replay-unavailable", "d3-snapshot-input-binding-unavailable",
}
PERSISTENCE_FILES = {"model_artifacts.py", "context_observations.py", "context_snapshots.py",
                     "context_runtime.py", "context_runtime_semantics.py"}
RESULT_KEYS = {"status", "schema", "verification_level", "empirical_approval_verified",
    "limitations", "d2_verified", "counts", "active_manifest", "active_slots_hash",
    "active_slot_count", "tour_states"}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


class ContextResourceError(ValueError):
    """Closed transport admission/deadline failure; never a D4 limitation."""


def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def decode(raw):
    def bad_constant(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=bad_constant)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "invalid hash")
    return value


def integer(value):
    need(type(value) is int and value >= 0, "expected actual nonnegative integer")
    return value


def hash_list(values):
    need(type(values) is list and values == sorted(set(digest(v) for v in values)), "noncanonical hash list")


def validate_report(value, code):
    need(type(value) is dict and set(value) == RESULT_KEYS, "unknown context report shape")
    need(type(value["schema"]) is int and value["schema"] == 1, "unknown report schema")
    need(value["empirical_approval_verified"] is False, "continuity is not effect certification")
    limits = value["limitations"]
    need(type(limits) is list and all(type(v) is str for v in limits)
         and limits == sorted(set(limits)), "noncanonical limitation list")
    if code == 0:
        need(value["status"] == "verified" and value["verification_level"] == "structural"
             and not limits, "success code contradicts the actual report")
    elif code == 2:
        need(value["status"] == "incomplete" and value["verification_level"] == "transport_only"
             and limits and set(limits) <= ALLOWED_LIMITS, "unreviewed context continuity limitation")
    else:
        raise ValueError("context verifier failed or exceeded its execution boundary")
    need(type(value["counts"]) is dict and set(value["counts"]) ==
         {"artifacts", "manifests", "contents", "observations", "snapshots", "rollbacks"}, "unknown counts")
    for count in value["counts"].values():
        integer(count)
    need(type(value["d2_verified"]) is dict and set(value["d2_verified"]) ==
         {"experiments", "datasets", "fits", "cases", "evaluations", "approvals"}, "unknown D2 report lists")
    for refs in value["d2_verified"].values():
        hash_list(refs)
    if value["active_manifest"] is not None:
        digest(value["active_manifest"])
    digest(value["active_slots_hash"])
    integer(value["active_slot_count"])
    need(type(value["tour_states"]) is dict and set(value["tour_states"]) <= {"ATP", "WTA"}, "unknown tour")
    for ref in value["tour_states"].values():
        digest(ref)
    # A1 legitimately allows multiple slot aliases for one immutable artifact.
    need(len(value["tour_states"]) <= value["active_slot_count"], "impossible tour slot count")
    need((value["active_manifest"] is not None) == (value["counts"]["manifests"] > 0), "missing manifest identity")
    need(value["active_manifest"] is not None or value["active_slot_count"] == 0, "slots without a manifest")
    return value


def configuration_lines(raw):
    # Shared closed record grammar for EnvironmentFile and unit records. Only
    # ASCII LF/CRLF/CR delimit records; Unicode never creates another setting.
    text = raw.decode("utf-8", "strict")
    need(not text.startswith("\ufeff") and all((ord(c) >= 32 or c in "\r\n\t")
         and c not in "\x85\u2028\u2029" for c in text), "unsupported configuration encoding")
    return [line.strip(" \t") for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def runtime_override(raw):
    # Deliberately closed EnvironmentFile subset, not an incomplete imitation
    # of systemd's multiline/escape language. Ambiguity stops before downtime.
    seen, result = set(), None
    for line in configuration_lines(raw):
        if not line or line.startswith(("#", ";")):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z_0-9]*)=(.*)", line)
        need(match is not None and "\\" not in line, "unsupported environment record")
        name, value = match.groups()
        need(name not in seen, "duplicate environment assignment")
        seen.add(name)
        value = value.strip(" \t")
        if value.startswith(("'", '"')):
            need(len(value) >= 2 and value[-1] == value[0] and value[0] not in value[1:-1], "unsupported quoted environment record")
            value = value[1:-1]
        else:
            need("'" not in value and '"' not in value, "ambiguous environment quotes")
        if name == "BETBOY_RUNTIME_STATE_DIR":
            result = value.strip(" \t") or None
            # The known app resolver strips Unicode whitespace too. Do not
            # silently turn that different path spelling into an exact route.
            need(result is None or not (result[0].isspace() or result[-1].isspace()), "unsupported runtime path whitespace")
    return result


def relative_name(value):
    need(type(value) is str and value and "\\" not in value
         and all(ord(c) >= 32 for c in value), "unsafe relative path")
    parsed = PurePosixPath(value)
    need(not parsed.is_absolute() and parsed.as_posix() == value and ".." not in parsed.parts
         and ":" not in value and not any(p in EXCLUDED for p in parsed.parts), "unsupported path scope")
    return value


def runtime_relative(app, override):
    root = PurePosixPath(app)
    selected = override or (root / "runtime_state").as_posix()
    pure = PurePosixPath(selected)
    need(root.is_absolute() and root.as_posix() == app and ".." not in root.parts
         and pure.is_absolute() and pure.as_posix() == selected and ".." not in pure.parts
         and "\\" not in selected and ":" not in selected and not selected.startswith("//"), "runtime path must be exact absolute POSIX")
    try:
        relative = (pure / "context_models.db").relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("context path is outside existing backup scope") from exc
    return relative_name(relative)


def signature(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def directory(path, *, owners, direct=True):
    path = Path(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid in owners
         and (not info.st_mode & 0o022 or (not direct and info.st_mode & stat.S_ISVTX)), "unsafe directory boundary")
    if path.parent != path:
        directory(path.parent, owners=owners, direct=False)
    return info


def sealed_directory(path):
    path = Path(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
         "sealed directory must have root-owned nonwritable ancestors")
    if path.parent != path:
        sealed_directory(path.parent)
    return info


def identity(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink]


def authentication_state(key, marker, app_gid):
    result = {}
    for name, path, maximum in (("key", Path(key), 65), ("marker", Path(marker), 65536)):
        if not os.path.lexists(path):
            result[name] = None
            continue
        raw = read_file(path, maximum=maximum, mode=0o640, gid=app_gid)
        if name == "key":
            need(re.fullmatch(rb"[0-9a-f]{64}\n", raw) is not None, "invalid existing authentication key")
        else:
            value = decode(raw)
            need(type(value) is dict and value.get("contract_version") == 1
                 and value.get("status") in {"in_progress", "complete"}, "invalid existing migration marker")
        result[name] = {"path": str(path), "hash": sha(raw), "signature": signature(file_info(path, owners={0}, mode=0o640, gid=app_gid))}
    return result


def copy_completed_archive(source, destination, receipt, maximum, app_uid, app_gid):
    source, destination = Path(source), Path(destination)
    expected = decode(read_file(receipt, mode=0o600))
    need(type(expected) is dict and set(expected) == {"schema", "path", "size", "sha256", "signature"}
         and type(expected["schema"]) is int and expected["schema"] == 1
         and expected["path"] == str(source), "invalid completed archive receipt")
    size = integer(expected["size"])
    if not 0 < size <= maximum:
        raise ContextResourceError("completed archive exceeds admitted byte budget")
    expected_hash = digest(expected["sha256"])
    need(type(expected["signature"]) is list and all(type(value) is int for value in expected["signature"]), "invalid archive signature")
    initial = file_info(source, owners={0, app_uid}, mode=0o600, gid=app_gid)
    need(initial.st_uid == app_uid and signature(initial) == expected["signature"] and initial.st_size == size,
         "archive changed after producer completion")
    directory(destination.parent, owners={0})
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_BINARY", 0)
    input_fd = os.open(source, flags)
    try:
        need(signature(os.fstat(input_fd)) == expected["signature"], "archive replaced before private copy")
        output_fd = os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_BINARY", 0), 0o600)
        try:
            os.fchown(output_fd, 0, 0)
            os.fchmod(output_fd, 0o600)
            created = identity(os.fstat(output_fd))
            remaining, checksum, deadline = size, hashlib.sha256(), time.monotonic() + 600
            with os.fdopen(output_fd, "wb", closefd=False) as output:
                while remaining:
                    if time.monotonic() >= deadline:
                        raise ContextResourceError("private archive copy deadline exceeded")
                    chunk = os.read(input_fd, min(1024 * 1024, remaining))
                    need(bool(chunk), "archive truncated during private copy")
                    remaining -= len(chunk)
                    checksum.update(chunk)
                    output.write(chunk)
                output.flush()
            need(not os.read(input_fd, 1), "archive grew during private copy")
            need(signature(os.fstat(input_fd)) == expected["signature"]
                 and signature(file_info(source, owners={0, app_uid}, mode=0o600, gid=app_gid)) == expected["signature"]
                 and checksum.hexdigest() == expected_hash, "archive changed during private copy")
            os.fsync(output_fd)
            need(identity(os.fstat(output_fd)) == created
                 and identity(file_info(destination, owners={0}, mode=0o600, gid=0)) == created
                 and os.fstat(output_fd).st_size == size, "private archive destination changed")
        finally:
            os.close(output_fd)
    finally:
        os.close(input_fd)


def file_info(path, *, owners, mode=None, gid=None):
    path = Path(path)
    directory(path.parent, owners=owners)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid in owners
         and not info.st_mode & 0o022, "unsafe file boundary")
    need(mode is None or stat.S_IMODE(info.st_mode) == mode, "unexpected file mode")
    need(gid is None or info.st_gid == gid, "unexpected file group")
    return info


def read_file(path, *, owners=frozenset({0}), maximum=MAX_REPORT, mode=None, gid=None):
    path = Path(path)
    initial = file_info(path, owners=owners, mode=mode, gid=gid)
    need(initial.st_size <= maximum, "bounded file input exceeded")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    try:
        need(signature(os.fstat(fd)) == signature(initial), "file changed before read")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(maximum + 1)
        need(len(raw) <= maximum and signature(os.fstat(fd)) == signature(initial)
             and signature(file_info(path, owners=owners, mode=mode, gid=gid)) == signature(initial), "file changed during read")
        return raw
    finally:
        os.close(fd)


def file_hash(path, *, owners=frozenset({0})):
    path = Path(path)
    before = file_info(path, owners=owners)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    try:
        need(signature(os.fstat(fd)) == signature(before), "hash source replaced")
        result = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as handle:
            while block := handle.read(1024 * 1024):
                result.update(block)
        need(signature(os.fstat(fd)) == signature(before) and
             signature(file_info(path, owners=owners)) == signature(before), "hash source changed")
        return result.hexdigest()
    finally:
        os.close(fd)


def write_new(path, raw, *, gid=0, mode=0o600):
    path = Path(path)
    directory(path.parent, owners={0})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), mode)
    try:
        os.fchown(fd, 0, gid)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
        os.fsync(fd)
    finally:
        os.close(fd)


def write_record(path, value):
    write_new(path, json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode())


def verify_payload(root, manifest_path, revision, app_gid):
    root = Path(root)
    directory(root, owners={0})
    manifest = decode(read_file(manifest_path, maximum=16 * 1024 * 1024, mode=0o640, gid=app_gid))
    need(type(manifest) is dict and set(manifest) == {"revision", "files", "must_be_absent"}
         and manifest["revision"] == revision and type(manifest["files"]) is dict
         and type(manifest["must_be_absent"]) is list, "invalid trusted payload manifest")
    files = manifest["files"]
    for name, entry in files.items():
        # Tracked seed/input paths are allowed here, but never executed as root.
        need(type(name) is str and not name.startswith("/") and ".." not in PurePosixPath(name).parts
             and "\\" not in name and PurePosixPath(name).as_posix() == name
             and all(ord(c) >= 32 for c in name), "unsafe tracked name")
        need(type(entry) is dict and set(entry) == {"mode", "sha256"}
             and entry["mode"] in {"100644", "100755"}, "invalid tracked manifest entry")
        file_info(root / name, owners={0}, mode=0o640, gid=app_gid)
        need(file_hash(root / name) == digest(entry["sha256"]), "trusted payload hash differs")
    actual = set()
    def fail_walk(error):
        raise ValueError("Cannot traverse trusted payload inventory") from error
    for parent, dirs, names in os.walk(root, followlinks=False, onerror=fail_walk):
        for name in dirs:
            directory(Path(parent) / name, owners={0})
        actual.update((Path(parent) / name).relative_to(root).as_posix() for name in names)
    need(actual == set(files), "unmanifested payload import or missing file")
    return files


def configuration(app, env_path, target, previous, app_uid, app_gid, target_manifest, previous_manifest, previous_head, target_head, backup_head):
    app = Path(app)
    directory(app, owners={0, app_uid})
    targets = verify_payload(target, target_manifest, target_head, app_gid)
    predecessors = verify_payload(previous, previous_manifest, previous_head, app_gid)
    need("runtime_paths.py" in targets and "scripts/verify_context_runtime.py" in targets, "target lacks the reviewed context entry")
    path_module = read_file(Path(target) / "runtime_paths.py", mode=0o640, gid=app_gid)
    need(sha(path_module.replace(b"\r\n", b"\n")) == PATH_CONTRACT, "unsupported runtime path contract")
    old_paths = (read_file(Path(previous) / "runtime_paths.py", mode=0o640, gid=app_gid)
                 if "runtime_paths.py" in predecessors else b"")
    legacy = b"CONTEXT_MODEL_DB_PATH" not in old_paths
    if legacy:
        partial_context = PERSISTENCE_FILES.intersection(predecessors) or any(
            name.startswith(("context_models/", "context_sources/"))
            or (name.startswith("context_") and name.endswith(".py"))
            or name in {"tennis/tour_state.py", "scripts/verify_context_runtime.py"}
            for name in predecessors)
        need(not partial_context, "partial legacy context persistence is ambiguous")
    else:
        need("model_artifacts.py" in predecessors and sha(old_paths.replace(b"\r\n", b"\n")) == PATH_CONTRACT,
             "previous runtime path contract is unsupported")
    # Existing unit hashes are checked by the installed updater. Additionally
    # bind their actual shared path records, never parse shell or source env.
    for tree, files in ((Path(target), targets), (Path(previous), predecessors)):
        units = [n for n in files if n.startswith("deploy/systemd/betboy-") and n.endswith(".service") and not n.endswith("betboy-backup.service")]
        need(len(units) == 7, "unexpected runtime service inventory")
        for unit in units:
            lines = configuration_lines(read_file(tree / unit, mode=0o640, gid=app_gid))
            need(not any(line.endswith("\\") for line in lines), "unreviewed multiline unit record")
            records = [(key.strip(" \t"), value.strip(" \t")) for line in lines if line and not line.startswith(("#", ";"))
                       for key, separator, value in [line.partition("=")] if separator]
            need([value for key, value in records if key == "EnvironmentFile"] == ["-/etc/betboy/betboy.env"],
                 "unreviewed environment-file route")
            need(not any(key == "Environment" and ("BETBOY_RUNTIME_STATE_DIR" in value or "\\" in value) for key, value in records)
                 and not any(key in {"PassEnvironment", "UnsetEnvironment"} for key, _ in records), "ambiguous runtime environment override")
    env = Path(env_path)
    directory(env.parent, owners={0})
    raw_env = read_file(env, maximum=65536, mode=0o640, gid=app_gid) if os.path.lexists(env) else None
    override = runtime_override(raw_env) if raw_env is not None else None
    relative = runtime_relative(app.as_posix(), override)
    path = app / relative
    current = path.parent
    while not os.path.lexists(current):
        current = current.parent
    directory(current, owners={0, app_uid})
    presence = live_signature(path, app_uid)
    need(presence or legacy, "context-capable predecessor has a missing database")
    return {"app": str(app), "env": str(env), "env_hash": None if raw_env is None else sha(raw_env),
        "target": str(target), "previous": str(previous), "target_manifest": str(target_manifest),
        "previous_manifest": str(previous_manifest), "previous_head": previous_head, "target_head": target_head, "backup_head": backup_head,
        "app_uid": app_uid, "app_gid": app_gid, "relative": relative, "legacy": legacy, "present": bool(presence)}


def live_signature(path, app_uid):
    found = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        name = Path(str(path) + suffix)
        if os.path.lexists(name):
            found[suffix] = signature(file_info(name, owners={0, app_uid}))
    need(not found or "" in found, "context sidecars without their database")
    return found


def load_config(hook):
    value = decode(read_file(Path(hook) / "config.json", mode=0o600))
    keys = {"app", "env", "target", "previous", "app_uid", "app_gid", "target_manifest", "previous_manifest", "previous_head", "target_head", "backup_head"}
    need(type(value) is dict and set(value) == keys | {"env_hash", "relative", "legacy", "present"}, "invalid configuration receipt")
    arguments = {key: value[key] for key in keys}
    arguments["env_path"] = arguments.pop("env")
    current = configuration(**arguments)
    need(current == value, "context configuration/presence changed across downtime")
    return value


def extract_and_seal(archive_path, relative, destination, *, source_head, app_gid):
    archive_path, destination = Path(archive_path), Path(destination)
    sealed_directory(destination.parent)
    before = file_info(archive_path, owners={0}, mode=0o600, gid=0)
    archive_hash = file_hash(archive_path)
    fd = os.open(archive_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    member_hash = None
    try:
        need(signature(os.fstat(fd)) == signature(before), "archive replaced before single-member read")
        with os.fdopen(fd, "rb", closefd=False) as source, zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            need(len(names) == len(set(names)), "duplicate archive members")
            for info in infos:
                relative_name(info.filename)
                need(not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) in {0, stat.S_IFREG}, "nonregular archive member")
            manifest_info = archive.getinfo("MANIFEST.json")
            need(manifest_info.file_size <= MAX_REPORT, "oversized backup manifest")
            manifest = decode(archive.read(manifest_info))
            required = {"created_at", "source_head", "database_count", "databases", "integrity_key"}
            need(type(manifest) is dict and set(manifest) in (required, required | {"migration_marker"})
                 and manifest["source_head"] == source_head, "backup source identity differs")
            entries = manifest["databases"]
            need(type(entries) is list and integer(manifest["database_count"]) == len(entries) and entries, "invalid database inventory")
            paths = []
            for entry in entries:
                need(type(entry) is dict and set(entry) == {"path", "source_size", "backup_size", "sha256"}, "invalid database member record")
                paths.append(relative_name(entry["path"]))
                need(Path(entry["path"]).suffix.casefold() in {".db", ".sqlite", ".sqlite3"}, "non-database inventory entry")
                digest(entry["sha256"])
                integer(entry["source_size"])
                need(integer(entry["backup_size"]) == archive.getinfo(entry["path"]).file_size, "database inventory size differs")
            need(paths == sorted(set(paths)), "noncanonical database inventory")
            allowed = {"MANIFEST.json", *paths}
            for key, expected in (("integrity_key", "integrity/challenge-ledger-hmac.key"),
                                  ("migration_marker", "integrity/challenge-ledger-v2-migrated.json")):
                if key not in manifest:
                    continue
                item = manifest[key]
                need(type(item) is dict and set(item) == {"path", "sha256"} and item["path"] == expected, "invalid integrity inventory identity")
                digest(item["sha256"])
                allowed.add(expected)  # Do NOT read these secret members.
            need(set(names) == allowed, "archive and verified inventory differ")
            if relative in paths:
                member = archive.getinfo(relative)
                need(100 <= member.file_size <= MAX_IMAGE, "context image outside bounded SQLite size")
                member_hash = digest(entries[paths.index(relative)]["sha256"])
                output_fd = os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    os.fchown(output_fd, 0, 0)
                    os.fchmod(output_fd, 0o600)
                    created = identity(os.fstat(output_fd))
                    total, header, checksum = 0, b"", hashlib.sha256()
                    with archive.open(member) as handle, os.fdopen(output_fd, "wb", closefd=False) as output:
                        while chunk := handle.read(1024 * 1024):
                            total += len(chunk)
                            need(total <= member.file_size and total <= MAX_IMAGE, "context member exceeds sealed budget")
                            if len(header) < 100:
                                header += chunk[:100 - len(header)]
                            checksum.update(chunk)
                            output.write(chunk)
                        output.flush()
                    os.fsync(output_fd)
                    need(total == member.file_size and checksum.hexdigest() == member_hash, "context archive member integrity differs")
                    need(header[:16] == b"SQLite format 3\x00" and header[18:20] in {b"\x01\x01", b"\x02\x02"}, "not a complete SQLite backup image")
                    need(identity(os.fstat(output_fd)) == created and identity(file_info(destination, owners={0}, mode=0o600)) == created,
                         "context extraction destination changed")
                finally:
                    os.close(output_fd)
        need(signature(os.fstat(fd)) == signature(before)
             and signature(file_info(archive_path, owners={0}, mode=0o600, gid=0)) == signature(before)
             and file_hash(archive_path) == archive_hash, "archive changed during extraction")
    finally:
        os.close(fd)
    if member_hash is not None:
        # Only the newly created private copy receives a SQLite filename.
        # Actual SQLite sealing, never raw-header repair or immutable WAL.
        need(not any(os.path.lexists(str(destination) + s) for s in ("-wal", "-shm", "-journal")), "unsealed copy has companions")
        seal_fd = os.open(destination, os.O_RDWR | os.O_NOFOLLOW)
        try:
            # `created` is the original extraction inode, not a new baseline.
            need(identity(os.fstat(seal_fd)) == created
                 and identity(file_info(destination, owners={0}, mode=0o600)) == created,
                 "extracted snapshot identity changed before sealing")
            need(file_hash(destination) == member_hash, "extracted snapshot digest changed before sealing")
            connection = sqlite3.connect(destination.as_uri() + "?mode=rw", uri=True, timeout=30)
            try:
                connection.execute("PRAGMA trusted_schema=OFF")
                need(connection.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",), "snapshot could not be sealed")
                need(connection.execute("PRAGMA quick_check").fetchall() == [("ok",)], "sealed snapshot SQLite check failed")
            finally:
                connection.close()
            need(identity(os.fstat(seal_fd)) == created and identity(file_info(destination, owners={0}, mode=0o600)) == created,
                 "snapshot sealing identity changed")
            need(not any(os.path.lexists(str(destination) + s) for s in ("-wal", "-shm", "-journal")), "snapshot sealing left companions")
            need(os.read(seal_fd, 100)[18:20] == b"\x01\x01", "snapshot is not DELETE mode")
            os.fchown(seal_fd, 0, app_gid)
            os.fchmod(seal_fd, 0o440)
            os.fsync(seal_fd)
        finally:
            os.close(seal_fd)
    return {"archive_hash": archive_hash, "archive_signature": signature(before), "member_hash": member_hash}


def main(args):
    need(getattr(os, "geteuid", lambda: -1)() == 0, "installed updater data boundary requires root")
    command, *args = args
    if command == "create-private":
        need(len(args) == 1 and args[0].isdigit() and int(args[0]) > 0, "invalid private-stage group")
        sealed_directory("/var/lib")
        path = Path(tempfile.mkdtemp(prefix="betboy-context-update.", dir="/var/lib"))
        os.chown(path, 0, int(args[0]))
        os.chmod(path, 0o750)
        write_record(path / "identity.json", identity(sealed_directory(path))[:5])
        print(path)
    elif command == "remove-private":
        need(len(args) == 1 and re.fullmatch(r"/var/lib/betboy-context-update\.[a-z0-9_]{8}", args[0]), "not our private stage")
        path = Path(args[0])
        # Directory link counts change when our phase subdirectories are added.
        need(identity(sealed_directory(path))[:5] == decode(read_file(path / "identity.json", mode=0o600)), "private stage replaced")
        need(shutil.rmtree.avoids_symlink_attacks, "safe private cleanup unavailable")
        shutil.rmtree(path)
    elif command == "seal-launcher":
        need(len(args) == 2 and args[1].isdigit() and int(args[1]) > 0, "invalid launcher principal")
        path = Path(args[0])
        need(path.name == "launcher.py", "unknown launcher path")
        sealed_directory(path.parent)
        initial = file_info(path, owners={0}, mode=0o600, gid=0)
        need(0 < initial.st_size < 16384, "invalid launcher size")
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
        try:
            need(signature(os.fstat(fd)) == signature(initial), "launcher file replaced")
            os.fchown(fd, 0, int(args[1]))
            os.fchmod(fd, 0o440)
            os.fsync(fd)
        finally:
            os.close(fd)
    elif command == "copy-archive":
        need(len(args) == 6 and all(value.isdigit() and int(value) > 0 for value in args[3:]), "invalid private archive copy arguments")
        copy_completed_archive(args[0], args[1], args[2], int(args[3]), int(args[4]), int(args[5]))
    elif command == "configure":
        app, env, target, previous, target_manifest, previous_manifest, old, new, backup_head, hook, uid, gid = args
        need(uid.isdigit() and gid.isdigit() and int(uid) > 0 and int(gid) > 0, "invalid app principal")
        need(all(re.fullmatch(r"[0-9a-f]{40}", revision) for revision in (old, new, backup_head)), "invalid release identity")
        need(env == "/etc/betboy/betboy.env", "unreviewed production config source")
        value = configuration(app, env, target, previous, int(uid), int(gid), target_manifest, previous_manifest, old, new, backup_head)
        hook = Path(hook)
        if hook.name == "quiesced":
            # Keep the online environment/payload/path receipt across downtime.
            # Authentication is deliberately not copied: marker preparation is
            # an authorized post-quiesce operation with its own recovery proof.
            need(load_config(hook.parent / "online") == value, "cross-phase configuration changed")
        sealed_directory(hook.parent)
        os.mkdir(hook, 0o750)
        os.chown(hook, 0, int(gid))
        os.chmod(hook, 0o750)
        write_record(hook / "config.json", value)
    elif command == "online-auth":
        need(len(args) == 3 and args[1:] == ["/etc/betboy/challenge-ledger-hmac.key", "/etc/betboy/challenge-ledger-v2-migrated.json"], "unknown authentication paths")
        hook = Path(args[0])
        config = load_config(hook)
        auth = authentication_state(args[1], args[2], config["app_gid"])
        if auth["key"] is None:
            need(config["legacy"] and not config["present"] and auth["marker"] is None,
                 "missing authentication is not a keyless contextless legacy installation")
            print("not_present_legacy")
        else:
            write_record(hook / "authentication.json", auth)
            print("authenticated")
    elif command == "stage":
        if len(args) == 2:
            args.append("quiesced")  # Preserve only the old strictly quiesced internal call.
        need(len(args) == 3 and args[2] in {"online", "quiesced"}, "unknown context phase")
        hook, archive = Path(args[0]), Path(args[1])
        phase = args[2]
        config = load_config(hook)
        path = Path(config["app"]) / config["relative"]
        live = live_signature(path, config["app_uid"])
        destination = hook / "context_models.db"
        proof = extract_and_seal(archive, config["relative"], destination, source_head=config["backup_head"], app_gid=config["app_gid"])
        need(bool(live) == (proof["member_hash"] is not None), "live/backup context presence differs")
        need(live or config["legacy"], "missing database is not a proved legacy installation")
        proof.update({"archive": str(archive), "live": live, "phase": phase,
                      "sealed_hash": file_hash(destination) if live else None,
                      "sealed_signature": signature(file_info(destination, owners={0}, mode=0o440, gid=config["app_gid"])) if live else None})
        write_record(hook / "stage.json", proof)
        print("present" if live else "not_present_legacy")
    elif command == "finish":
        if len(args) == 2:
            args.append("quiesced")
        need(len(args) == 3 and args[2] in {"online", "quiesced"}, "unknown context phase")
        hook, code = Path(args[0]), int(args[1])
        config, proof = load_config(hook), decode(read_file(hook / "stage.json", mode=0o600))
        need(set(proof) == {"archive", "archive_hash", "archive_signature", "member_hash", "live", "phase", "sealed_hash", "sealed_signature"}
             and proof["phase"] == args[2], "unknown stage receipt or phase mismatch")
        need(signature(file_info(proof["archive"], owners={0}, mode=0o600, gid=0)) == proof["archive_signature"]
             and file_hash(proof["archive"]) == proof["archive_hash"], "backup changed after verification")
        current_live = live_signature(Path(config["app"]) / config["relative"], config["app_uid"])
        if proof["phase"] == "quiesced":
            need(current_live == proof["live"], "live source changed during verifier")
        else:
            need(current_live.get("", [])[:6] == proof["live"].get("", [])[:6], "live source identity changed during verifier")
            auth = decode(read_file(hook / "authentication.json", mode=0o600))
            need(authentication_state("/etc/betboy/challenge-ledger-hmac.key", "/etc/betboy/challenge-ledger-v2-migrated.json", config["app_gid"]) == auth,
                 "authentication changed during online verification")
        if proof["member_hash"] is None:
            need(config["legacy"] and not config["present"] and code == 0
                 and not os.path.lexists(hook / "context_models.db"), "invalid legacy absence claim")
            print("Context continuity: not_present_legacy; no model/effect certification.")
        else:
            destination = hook / "context_models.db"
            need(not any(os.path.lexists(str(destination) + s) for s in ("-wal", "-shm", "-journal")), "verifier created companions")
            need(signature(file_info(destination, owners={0}, mode=0o440, gid=config["app_gid"])) == proof["sealed_signature"]
                 and file_hash(destination) == proof["sealed_hash"], "sealed source changed during verifier")
            value = validate_report(decode(read_file(hook / "report.json", maximum=MAX_REPORT, mode=0o600)), code)
            print("Context continuity: " + value["verification_level"] + "; no model/effect certification.")
    elif command == "dependencies":
        need(len(args) == 2 and args[1] == "0" and read_file(args[0], maximum=1024, mode=0o600) == b"context-dependencies-v2:ok\n", "context dependency preflight failed")
    else:
        raise ValueError("unknown context hook action")


if __name__ == "__main__":
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
        main(sys.argv[1:])
    except (MemoryError, ContextResourceError):
        print("ContextResourceError", file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        # Never print provider/env/archive data or arbitrary exception strings.
        print("Context continuity check failed (configuration, integrity, or capability).", file=sys.stderr)
        raise SystemExit(1)
PY
}

context_hook_command() {
    local output="$1"
    local output_size line
    shift
    local -a codes
    [[ ! -e "${output}" && ! -L "${output}" ]] || die "Context output already exists."
    if as_betboy /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
        OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
        NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
        /usr/bin/timeout --signal=TERM --kill-after=10s 600s \
        "$@" 2>&1 | /usr/bin/timeout --signal=TERM --kill-after=10s 610s \
        /usr/bin/head -c 1048577 >"${output}"; then
        codes=("${PIPESTATUS[@]}")
    else
        codes=("${PIPESTATUS[@]}")
    fi
    [[ "${#codes[@]}" == 2 && "${codes[1]}" == 0 ]] \
        || die "Context verifier output could not be captured."
    output_size=$(stat -c '%s' "${output}") || die "Verification output size unavailable."
    [[ "${output_size}" =~ ^[0-9]+$ && "${output_size}" -le 1048576 ]] \
        || die "VerificationResourceError: aggregate output budget exceeded."
    case "${codes[0]}" in
        124|137|152|153) die "VerificationResourceError: child time, memory or file-size limit." ;;
    esac
    while IFS= read -r line || [[ -n "${line}" ]]; do
        line=${line%$'\r'}
        case "${line}" in MemoryError|MemoryError:*|ContextResourceError|ContextResourceError:*)
            die "VerificationResourceError: child memory or capacity limit." ;; esac
    done <"${output}"
    CONTEXT_COMMAND_STATUS="${codes[0]}"
}

verification_launcher_source() {
    # Only installed-updater literals are emitted. No application import or
    # caller-supplied executable/code/environment is accepted by this launcher.
    cat <<'PY'
import hashlib
import os
from pathlib import Path
import pwd
import resource
import stat
import sys

resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": "/var/tmp",
    "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
kind, *args = sys.argv[1:]
if ((kind == "backup" and len(args) == 2 and os.geteuid() == 0)
        or (kind == "backup-service" and len(args) == 1
            and os.geteuid() == pwd.getpwnam("betboy-backup").pw_uid != 0)):
    helper, archive = (map(Path, args) if kind == "backup" else
        (Path("/usr/local/libexec/betboy-backup-runtime.py"), Path(args[0])))
    info = helper.lstat()
    if (helper.name != ("backup_runtime_databases.py" if kind == "backup" else "betboy-backup-runtime.py") or not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022):
        raise SystemExit("invalid trusted backup child")
    with helper.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    if checksum != "b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604":
        raise SystemExit("backup child pin differs")
    executable = "/usr/bin/python3"
    command = [executable, "-I", "-B", str(helper), "--verify-only", str(archive)]
    if kind == "backup":
        command.append("--recovery-mode")
elif kind == "d4" and len(args) == 2 and os.geteuid() != 0:
    target, database = map(Path, args)
    executable = "/opt/betboy/venv/bin/python"
    command = [executable, "-I", "-B", str(target / "scripts/verify_context_runtime.py"),
        "--sealed-file", "--database", str(database)]
elif kind == "dependencies" and len(args) == 1 and os.geteuid() != 0:
    executable = "/opt/betboy/venv/bin/python"
    program = '''import importlib, sqlite3, sys
sys.path.insert(0, sys.argv[1])
for name in ("numpy", "scipy", "pandas", "sklearn", "context_runtime", "context_runtime_input",
             "context_runtime_semantics", "context_models.evaluator", "context_models.activation",
             "tennis.tour_state", "context_transport"):
    importlib.import_module(name)
assert sys.platform == "linux"
from context_runtime_input import open_sealed_connection
assert callable(open_sealed_connection)
connection = sqlite3.connect(":memory:")
try:
    connection.execute("PRAGMA query_only=ON")
    assert connection.execute("PRAGMA query_only").fetchone() == (1,)
finally:
    connection.close()
print("context-dependencies-v2:ok")
'''
    command = [executable, "-I", "-B", "-c", program, args[0]]
else:
    raise SystemExit("invalid verification child selection")
os.execve(executable, command, environment)
PY
}

configure_context_phase() {
    local hook="$1"
    local manifest_previous="${PREVIOUS_HEAD}"
    if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
        manifest_previous="${MIGRATION_MARKER_PREVIOUS_HEAD}"
    fi
    target_payload_file scripts/verify_context_runtime.py >/dev/null
    context_hook_data configure "${APP_DIR}" /etc/betboy/betboy.env \
        "${TARGET_PAYLOAD}" "${PREVIOUS_PAYLOAD}" \
        "${TARGET_MANIFEST}" "${PREVIOUS_MANIFEST}" "${manifest_previous}" "${TARGET_HEAD}" "${PREVIOUS_HEAD}" \
        "${hook}" "$(id -u betboy)" "$(id -g betboy)"
}

prepare_verification_launcher() {
    local launcher="${CONTEXT_STAGE_DIR}/launcher.py"
    [[ ! -e "${launcher}" && ! -L "${launcher}" ]] || die "Launcher already exists."
    # Check the producer status in this shell. An unchecked process-substitution
    # could feed empty/truncated Python to a verifier and lose its failure code.
    ( set -o noclobber; verification_launcher_source >"${launcher}" ) \
        || die "Verification launcher could not be written completely."
    context_hook_data seal-launcher "${launcher}" "$(id -g betboy)"
}

verify_backup_archive() {
    local archive="$1"
    capture_root_verifier "${archive}.inline.log" /usr/bin/python3 -I -B - "${archive}" <<'PY'
import resource
resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

archive_path = Path(sys.argv[1])
with zipfile.ZipFile(archive_path) as archive:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise SystemExit("backup ZIP contains duplicate members")
    for name in names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            raise SystemExit(f"unsafe backup member: {name}")
    bad = archive.testzip()
    if bad is not None:
        raise SystemExit(f"bad ZIP CRC: {bad}")
    try:
        manifest = json.loads(archive.read("MANIFEST.json"))
    except (KeyError, ValueError) as exc:
        raise SystemExit("backup manifest missing or invalid") from exc
    databases = manifest.get("databases")
    if not isinstance(databases, list) or not databases:
        raise SystemExit("backup manifest has no databases")
    integrity_key = manifest.get("integrity_key")
    if (
        not isinstance(integrity_key, dict)
        or integrity_key.get("path") != "integrity/challenge-ledger-hmac.key"
        or not isinstance(integrity_key.get("sha256"), str)
        or len(integrity_key["sha256"]) != 64
    ):
        raise SystemExit("backup manifest has no valid ledger integrity key")
    migration_marker = manifest.get("migration_marker")
    if migration_marker is not None and (
        not isinstance(migration_marker, dict)
        or migration_marker.get("path")
        != "integrity/challenge-ledger-v2-migrated.json"
        or not isinstance(migration_marker.get("sha256"), str)
        or len(migration_marker["sha256"]) != 64
    ):
        raise SystemExit("backup manifest has an invalid migration marker")
    expected = {entry["path"] for entry in databases} | {integrity_key["path"]}
    if migration_marker is not None:
        expected.add(migration_marker["path"])
    actual = set(names) - {"MANIFEST.json"}
    if expected != actual or manifest.get("database_count") != len(databases):
        raise SystemExit("backup inventory does not match ZIP members")
    key_payload = archive.read(integrity_key["path"])
    if (
        len(key_payload) != 65
        or not key_payload.endswith(b"\n")
        or any(byte not in b"0123456789abcdef" for byte in key_payload[:-1])
        or hashlib.sha256(key_payload).hexdigest() != integrity_key["sha256"]
    ):
        raise SystemExit("backup ledger integrity key is invalid")
    if migration_marker is not None:
        marker_payload = archive.read(migration_marker["path"])
        try:
            marker = json.loads(marker_payload)
        except ValueError as exc:
            raise SystemExit("backup migration marker is invalid JSON") from exc
        if (
            marker.get("contract_version") != 1
            or marker.get("status") not in {"in_progress", "complete"}
            or hashlib.sha256(marker_payload).hexdigest()
            != migration_marker["sha256"]
        ):
            raise SystemExit("backup migration marker is incomplete")

    with tempfile.TemporaryDirectory(prefix="betboy-update-verify-") as temp:
        current_challenge_present = False
        for index, entry in enumerate(databases):
            destination = Path(temp) / f"database-{index}.db"
            digest = hashlib.sha256()
            with archive.open(entry["path"]) as source, destination.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != entry["sha256"]:
                raise SystemExit(f"backup digest mismatch: {entry['path']}")
            uri = destination.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=30) as connection:
                result = connection.execute("PRAGMA quick_check").fetchall()
                if connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type='table'
                      AND name='challenge_integrity_checkpoint'
                    """
                ).fetchone() is not None:
                    current_challenge_present = True
            if result != [("ok",)]:
                raise SystemExit(f"SQLite quick_check failed: {entry['path']}")
        if current_challenge_present and migration_marker is None:
            raise SystemExit("current challenge backup has no migration marker")
PY
    [[ "${CONTEXT_COMMAND_STATUS}" == 0 ]] || die "Full backup verification failed."
}

capture_root_verifier() {
    local output="$1"
    local output_size line
    shift
    local -a codes
    [[ ! -e "${output}" && ! -L "${output}" ]] || die "Root verification output already exists."
    if /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=/var/tmp \
        OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
        NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
        /usr/bin/timeout --signal=TERM --kill-after=10s 600s "$@" 2>&1 \
        | /usr/bin/timeout --signal=TERM --kill-after=10s 610s /usr/bin/head -c 1048577 >"${output}"; then
        codes=("${PIPESTATUS[@]}")
    else
        codes=("${PIPESTATUS[@]}")
    fi
    [[ "${#codes[@]}" == 2 && "${codes[1]}" == 0 ]] || die "Full backup output capture failed."
    output_size=$(stat -c '%s' "${output}") || die "Full backup output size unavailable."
    [[ "${output_size}" =~ ^[0-9]+$ && "${output_size}" -le 1048576 ]] || die "VerificationResourceError: full backup output budget."
    case "${codes[0]}" in
        124|137|152|153) die "VerificationResourceError: full backup child limit." ;;
    esac
    while IFS= read -r line || [[ -n "${line}" ]]; do
        line=${line%$'\r'}
        case "${line}" in MemoryError|MemoryError:*|ContextResourceError|ContextResourceError:*)
            die "VerificationResourceError: full backup memory or capacity limit." ;; esac
    done <"${output}"
    CONTEXT_COMMAND_STATUS="${codes[0]}"
}

produce_update_backup() {
    local phase="$1" backup_work="$2" destination_archive="$3" source_head="$4"
    local work_archive
    local partial_archive
    [[ "${phase}" == online || "${phase}" == quiesced ]] || die "Unknown backup phase."
    [[ "${backup_work}" == "${STAGE_DIR}/backup-${phase}-work" ]] || die "Unknown backup work path."

    [[ ! -L /var/backups ]] || die "/var/backups must not be a symlink."
    [[ ! -L "${RECOVERY_BACKUP_DIR}" ]] \
        || die "Recovery backup directory must not be a symlink."
    install -d -m 0700 -o root -g root "${RECOVERY_BACKUP_DIR}"
    verify_root_owned_file "${TRUSTED_UPDATER}"
    [[ "$(stat -c '%U:%G' "${RECOVERY_BACKUP_DIR}")" == root:root ]] \
        || die "Recovery backup directory is not root-owned."
    (( (8#$(stat -c '%a' "${RECOVERY_BACKUP_DIR}") & 077) == 0 )) \
        || die "Recovery backup directory is accessible outside root."

    [[ ! -e "${backup_work}" && ! -L "${backup_work}" ]] || die "Backup work already exists."
    install -d -m 0700 -o betboy -g betboy "${backup_work}"
    work_archive="${backup_work}/capture.zip"
    partial_archive="${destination_archive}.partial.$$"
    [[ ! -e "${work_archive}" && ! -e "${destination_archive}" \
        && ! -e "${partial_archive}" ]] \
        || die "Refusing to overwrite an existing recovery backup."

    log "Creating fresh ${phase} backup (online capture consists of per-database snapshots)."
    context_hook_command "${STAGE_DIR}/backup-${phase}-production.log" /usr/bin/python3 -I -B - \
        "${APP_DIR}" "${work_archive}" "${source_head}" \
        "${LEDGER_HMAC_KEY}" "${LEDGER_MIGRATION_MARKER}" "${ARCHIVE_MAX_BYTES}" <<'PY'
import resource
resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

maximum_archive = int(sys.argv[6])
if maximum_archive <= 0:
    raise SystemExit("invalid archive admission budget")
resource.setrlimit(resource.RLIMIT_FSIZE, (maximum_archive, maximum_archive))
os.umask(0o077)
root_argument = Path(sys.argv[1])
if root_argument.is_symlink():
    raise SystemExit("application backup root must not be a symlink")
root = root_argument.absolute()
resolved_root = root.resolve(strict=True)
if resolved_root != root:
    raise SystemExit("application backup root must not traverse a symlink")
root = resolved_root
archive_path = Path(sys.argv[2])
source_head = sys.argv[3]
integrity_key_path = Path(sys.argv[4])
integrity_member = Path("integrity/challenge-ledger-hmac.key")
migration_marker_path = Path(sys.argv[5])
migration_marker_member = Path("integrity/challenge-ledger-v2-migrated.json")
excluded = {
    ".codex_test_venv", ".git", ".pytest_cache", ".pytest_tmp",
    ".venv", "__pycache__", "backups_runtime",
}


def stable_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)


def capture_inventory():
    found, parents = {}, {}
    def fail_walk(error):
        raise SystemExit("Cannot traverse complete database inventory") from error
    for directory, dirnames, filenames in os.walk(root, followlinks=False, onerror=fail_walk):
        current = Path(directory)
        info = current.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0, os.getuid()}
                or info.st_mode & 0o022):
            raise SystemExit("unsafe database directory principal")
        parents[current.relative_to(root).as_posix()] = stable_identity(info)
        kept = []
        for name in dirnames:
            child = current / name
            if name in excluded:
                continue
            child_info = child.lstat()
            if child.is_symlink() or not stat.S_ISDIR(child_info.st_mode):
                raise SystemExit("database path traverses an unsafe directory")
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            if Path(name).suffix.casefold() not in {".db", ".sqlite", ".sqlite3"}:
                continue
            source = current / name
            info = source.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022):
                raise SystemExit("database is not one safely owned regular file")
            if source.resolve(strict=True) != source:
                raise SystemExit("database path identity is ambiguous")
            found[source.relative_to(root).as_posix()] = stable_identity(info)
    return found, parents


initial_inventory = capture_inventory()
sources = [root / relative for relative in sorted(initial_inventory[0])]
if not sources:
    raise SystemExit("no runtime databases found")

inventory = []


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


with tempfile.TemporaryDirectory(prefix="database-stage-", dir=archive_path.parent) as temp:
    stage = Path(temp)
    snapshot_total = 0
    for source in sources:
        relative = source.relative_to(root)
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            expected = initial_inventory[0][relative.as_posix()]
            if stable_identity(os.fstat(descriptor)) != expected or stable_identity(source.lstat()) != expected:
                raise SystemExit("database replaced before online backup")
            uri = source.as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=30)) as source_connection:
                page_size = source_connection.execute("PRAGMA page_size").fetchone()[0]
                def snapshot_progress(status, remaining, total):
                    # Compressed ZIP size cannot bound SQLite restore growth.
                    # A callback follows at most 256 pages (16 MiB at SQLite's
                    # largest page size), covered by the disk safety margin.
                    if snapshot_total + total * page_size > maximum_archive:
                        raise SystemExit("ContextResourceError: total snapshot byte budget exceeded")
                with closing(sqlite3.connect(destination)) as destination_connection:
                    source_connection.backup(destination_connection, pages=256, sleep=0.1, progress=snapshot_progress)
            if stable_identity(os.fstat(descriptor)) != expected or stable_identity(source.lstat()) != expected:
                raise SystemExit("database replaced during online backup")
        finally:
            os.close(descriptor)
        with closing(sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchall()
        if result != [("ok",)]:
            raise SystemExit(f"SQLite quick_check failed: {relative.as_posix()}")
        snapshot_total += destination.stat().st_size
        if snapshot_total > maximum_archive:
            raise SystemExit("ContextResourceError: total snapshot byte budget exceeded")
        inventory.append({
            "path": relative.as_posix(),
            "source_size": source.stat().st_size,
            "backup_size": destination.stat().st_size,
            "sha256": sha256_file(destination),
        })

    key_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    key_descriptor = os.open(integrity_key_path, key_flags)
    try:
        key_info = os.fstat(key_descriptor)
        key_payload = os.read(key_descriptor, 1024)
        key_extra = os.read(key_descriptor, 1)
    finally:
        os.close(key_descriptor)
    if (
        not stat.S_ISREG(key_info.st_mode)
        or key_info.st_nlink != 1
        or key_info.st_uid != 0
        or key_info.st_gid != os.getgid()
        or stat.S_IMODE(key_info.st_mode) != 0o640
        or key_extra
        or len(key_payload) != 65
        or not key_payload.endswith(b"\n")
        or any(byte not in b"0123456789abcdef" for byte in key_payload[:-1])
    ):
        raise SystemExit("ledger HMAC key metadata or format is invalid")
    staged_key = stage / integrity_member
    staged_key.parent.mkdir(parents=True, exist_ok=True)
    staged_key.write_bytes(key_payload)
    staged_key.chmod(0o600)

    marker_record = None
    if os.path.lexists(migration_marker_path):
        marker_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        marker_descriptor = os.open(migration_marker_path, marker_flags)
        try:
            marker_info = os.fstat(marker_descriptor)
            marker_payload = os.read(marker_descriptor, 65537)
            marker_extra = os.read(marker_descriptor, 1)
        finally:
            os.close(marker_descriptor)
        try:
            marker_json = json.loads(marker_payload)
        except ValueError as exc:
            raise SystemExit("ledger migration marker is invalid JSON") from exc
        if (
            not stat.S_ISREG(marker_info.st_mode)
            or marker_info.st_nlink != 1
            or marker_info.st_uid != 0
            or marker_info.st_gid != os.getgid()
            or stat.S_IMODE(marker_info.st_mode) != 0o640
            or marker_extra
            or len(marker_payload) > 65536
            or marker_json.get("contract_version") != 1
            or marker_json.get("status") not in {"in_progress", "complete"}
        ):
            raise SystemExit("ledger migration marker metadata is invalid")
        staged_marker = stage / migration_marker_member
        staged_marker.parent.mkdir(parents=True, exist_ok=True)
        staged_marker.write_bytes(marker_payload)
        staged_marker.chmod(0o600)
        marker_record = {
            "path": migration_marker_member.as_posix(),
            "sha256": hashlib.sha256(marker_payload).hexdigest(),
        }

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_head": source_head,
        "database_count": len(inventory),
        "databases": inventory,
        "integrity_key": {
            "path": integrity_member.as_posix(),
            "sha256": hashlib.sha256(key_payload).hexdigest(),
        },
    }
    if marker_record is not None:
        manifest["migration_marker"] = marker_record
    manifest_path = stage / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(
        archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.write(manifest_path, "MANIFEST.json")
        archive.write(staged_key, integrity_member.as_posix())
        if marker_record is not None:
            archive.write(staged_marker, migration_marker_member.as_posix())
        for entry in inventory:
            archive.write(stage / entry["path"], entry["path"])
    if capture_inventory() != initial_inventory:
        raise SystemExit("database inventory or principal changed during online capture")
    # Existing authentication bytes must bind the capture; never create or
    # complete a migration marker here. Ordinary DB size/time changes are OK.
    for path, payload in ((integrity_key_path, key_payload), (migration_marker_path, marker_payload if marker_record else None)):
        if payload is None:
            if os.path.lexists(path):
                raise SystemExit("authentication appeared during capture")
        else:
            flags = os.O_RDONLY | os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            try:
                info = os.fstat(descriptor)
                original = key_info if path == integrity_key_path else marker_info
                if (stable_identity(info) != stable_identity(original)
                        or stable_identity(path.lstat()) != stable_identity(original)
                        or os.read(descriptor, len(payload) + 1) != payload):
                    raise SystemExit("authentication changed during capture")
            finally:
                os.close(descriptor)
    descriptor = os.open(archive_path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        captured = os.fstat(descriptor)
        def archive_signature(info):
            return [*stable_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        if not 0 < captured.st_size <= maximum_archive:
            raise SystemExit("ContextResourceError: archive exceeds admitted byte budget")
        checksum = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            checksum.update(chunk)
        if archive_signature(os.fstat(descriptor)) != archive_signature(captured) or archive_signature(archive_path.lstat()) != archive_signature(captured):
            raise SystemExit("produced archive changed before completion")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(json.dumps({"schema": 1, "path": str(archive_path), "size": captured.st_size,
        "sha256": checksum.hexdigest(), "signature": archive_signature(captured)}, sort_keys=True))
PY
    [[ "${CONTEXT_COMMAND_STATUS}" == 0 ]] || die "Fresh backup capture failed before acceptance."
    # The staging parent cannot be renamed by betboy. Revoke its only access
    # before any root pathname operation on the newly-created archive.
    chown root:root "${backup_work}"
    chmod 0700 "${backup_work}"
    [[ -f "${work_archive}" && ! -L "${work_archive}" \
        && "$(stat -c '%U:%G' "${work_archive}")" == betboy:betboy \
        && "$(stat -c '%h' "${work_archive}")" == 1 ]] \
        || die "Backup helper did not produce one regular betboy-owned archive."
    # Copy to a new root-owned inode: revoking the producer directory alone
    # cannot revoke an already-open application file descriptor.
    context_hook_data copy-archive "${work_archive}" "${partial_archive}" "${STAGE_DIR}/backup-${phase}-production.log" \
        "${ARCHIVE_MAX_BYTES}" "$(id -u betboy)" "$(id -g betboy)"
    verify_backup_archive "${partial_archive}"
    capture_root_verifier "${partial_archive}.helper.log" /usr/bin/python3 -I -B "${CONTEXT_STAGE_DIR}/launcher.py" backup \
        "$(trusted_file scripts/backup_runtime_databases.py)" "${partial_archive}"
    [[ "${CONTEXT_COMMAND_STATUS}" == 0 ]] || die "Full backup restore/authentication verification failed."
    /usr/bin/python3 -I - "${partial_archive}" "${destination_archive}" <<'PY'
import os
import stat
import sys
from pathlib import Path

partial = Path(sys.argv[1])
target = Path(sys.argv[2])
if partial.parent != target.parent or os.path.lexists(target):
    raise SystemExit("recovery backup publication target is unsafe")
flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
descriptor = os.open(partial, flags)
try:
    info = os.fstat(descriptor)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != 0
        or info.st_gid != 0
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise SystemExit("recovery backup partial metadata is unsafe")
    os.fsync(descriptor)
finally:
    os.close(descriptor)
os.rename(partial, target)
directory = os.open(
    target.parent,
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
)
try:
    os.fsync(directory)
finally:
    os.close(directory)
PY
    log "Fresh root-protected ${phase} backup verified: ${destination_archive}"
}

enumerate_backup_sources() {
    # One locale-independent discovery contract for byte admission and DAC.
    # Do not substitute find -iname for Python's Unicode suffix.casefold().
    /usr/bin/python3 -I -B - "${APP_DIR}" "$1" <<'PY'
import os
from pathlib import Path
import stat
import sys

root, mode = Path(sys.argv[1]), sys.argv[2]
if mode not in {"bytes", "paths"}:
    raise SystemExit("Unknown backup source enumeration mode")
if root.is_symlink() or root.absolute() != root.resolve(strict=True):
    raise SystemExit("Unsafe backup source root")
excluded = {".codex_test_venv", ".git", ".pytest_cache", ".pytest_tmp"} if mode == "paths" else set()

def fail_walk(error):
    raise SystemExit("Cannot traverse complete backup source inventory") from error

def database_or_companion(name):
    folded = name.casefold()
    for companion in ("-wal", "-shm", "-journal"):
        if folded.endswith(companion):
            folded = folded[:-len(companion)]
            break
    return Path(folded).suffix in {".db", ".sqlite", ".sqlite3"}

total = 0
for parent, directories, names in os.walk(root, topdown=True, followlinks=False, onerror=fail_walk):
    current = Path(parent)
    kept = []
    for name in directories:
        if name in excluded:
            continue
        if not stat.S_ISDIR((current / name).lstat().st_mode):
            raise SystemExit("Unsafe backup source directory")
        kept.append(name)
    directories[:] = kept
    for name in names:
        if not database_or_companion(name):
            continue
        path = current / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit("Unsafe backup source file")
        total += info.st_size
        if mode == "paths":
            sys.stdout.buffer.write(os.fsencode(path.as_posix()) + b"\0")
if mode == "bytes":
    print((total + 1023) // 1024)
PY
}

# END unchanged Task2 preflight functions.

repair_guard() {
    /usr/bin/python3 -I -B - "$@" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys


def need(condition, message):
    if not condition:
        raise SystemExit(message)


def ancestors(path):
    path = Path(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
         "unsafe root-private ancestor")
    if path.parent != path:
        ancestors(path.parent)


def live_application_identity():
    # Only these two fixed live directories may belong to the app principal.
    # Root-private archive/auth/seal paths continue to use ancestors() unchanged.
    account = pwd.getpwnam("betboy")
    parent, app = Path("/opt/betboy"), Path("/opt/betboy/app")
    ancestors(parent.parent)
    records = {}
    for name, path in (("parent", parent), ("app", app)):
        info = path.lstat()
        allowed = {(account.pw_uid, account.pw_gid)}
        if name == "parent":
            allowed.add((0, 0))
        need(stat.S_ISDIR(info.st_mode) and (info.st_uid, info.st_gid) in allowed
             and not info.st_mode & 0o022, "unsafe live application principal")
        records[name] = signature(info)[:6]
    need(signature(parent.lstat())[:6] == records["parent"]
         and signature(app.lstat())[:6] == records["app"], "live application path replaced")
    return records


def signature(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def read(path, maximum):
    path = Path(path)
    ancestors(path.parent)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
         and not before.st_mode & 0o022 and 0 < before.st_size <= maximum,
         "unsafe trusted file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(signature(os.fstat(fd)) == signature(before), "trusted file replaced")
        raw = b""
        while chunk := os.read(fd, min(65536, maximum + 1 - len(raw))):
            raw += chunk
            need(len(raw) <= maximum, "trusted file grew")
        need(signature(os.fstat(fd)) == signature(before)
             and signature(path.lstat()) == signature(before), "trusted file changed")
        return raw, signature(before)
    finally:
        os.close(fd)


def write(path, raw):
    path = Path(path)
    ancestors(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            need(count > 0, "short private write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


need(os.geteuid() == 0, "repair guard requires root")
action, *args = sys.argv[1:]
if action == "self" and len(args) == 1:
    own = Path(os.path.abspath(args[0]))
    need(own.resolve(strict=True) == own, "installer must not traverse symlinks")
    read(own, 2 * 1024 * 1024)
elif action == "continuity" and len(args) == 2:
    head, proof = args
    need(head == "2dd1116b68f3d94e9c24338c6c9dff9b01799221", "production HEAD changed")
    app = Path("/opt/betboy/app")
    live_identity = live_application_identity()
    records = {"head": head, **live_identity}
    updater_raw, updater_identity = read("/usr/local/sbin/betboy-update", 2 * 1024 * 1024)
    need(hashlib.sha256(updater_raw).hexdigest() == "74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f"
         and stat.S_IMODE(updater_identity[2]) == 0o755 and updater_identity[4] == 0,
         "old installed updater identity differs")
    records["updater"] = {"sha256": hashlib.sha256(updater_raw).hexdigest(), "identity": updater_identity}
    for name, path, limit in (
        ("key", "/etc/betboy/challenge-ledger-hmac.key", 65),
        ("marker", "/etc/betboy/challenge-ledger-v2-migrated.json", 65536),
        ("environment", "/etc/betboy/betboy.env", 1048576),
    ):
        raw, identity = read(path, limit)
        records[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "identity": identity}
        if name == "marker":
            marker = json.loads(raw)
            need(marker.get("status") == "complete" and marker.get("target_head") == head
                 and marker.get("application_root") == str(app), "incomplete or mismatched production marker")
    need(live_application_identity() == live_identity, "live application path changed during continuity check")
    encoded = (json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if os.path.lexists(proof):
        need(read(proof, 65536)[0] == encoded, "production authentication/configuration identity changed")
    else:
        write(proof, encoded)
elif action == "candidate" and len(args) == 2:
    raw, _ = read(args[0], 2 * 1024 * 1024)
    need(0 < len(raw) <= 2 * 1024 * 1024
         and hashlib.sha256(raw).hexdigest() == args[1], "fetched updater blob differs")
    candidate = Path("/var/lib/betboy-updater-repair/candidate")
    if os.path.lexists(candidate):
        need(read(candidate, 2 * 1024 * 1024)[0] == raw, "existing candidate differs")
    else:
        write(candidate, raw)
elif action == "backup-dir" and not args:
    destination = Path("/var/lib/betboy-updater-repair/backups")
    ancestors(destination.parent)
    try:
        os.mkdir(destination, 0o700)
    except FileExistsError:
        pass
    ancestors(destination)
    info = destination.lstat()
    need(info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o700,
         "existing repair backup destination is not root-private")
elif action == "capacity" and len(args) == 3:
    stage, recovery = map(Path, args[:2])
    # KiB rounded upward by the exact reviewed Task2 enumerator, whose failed
    # walk aborts the caller before this reservation can be evaluated.
    need(re.fullmatch(r"[1-9][0-9]*", args[2]) is not None, "no database capacity inventory")
    maximum = int(args[2]) * 1024 * 2 + 67108864
    # Add reservations on the actual mounts: retained producer+sealed context,
    # root archive copy, independent helper restore. Never reuse shared free space.
    reservations = ((stage, maximum * 4 + 1073741824),
                    (recovery, maximum * 2 + 67108864),
                    (Path("/var/tmp"), maximum + 67108864))
    devices = {}
    for path, required in reservations:
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0, "unsafe capacity destination")
        free = os.statvfs(path).f_bavail * os.statvfs(path).f_frsize
        previous, available = devices.get(info.st_dev, (0, free))
        devices[info.st_dev] = (previous + required, min(available, free))
    need(all(required <= free for required, free in devices.values()),
         "VerificationResourceError: insufficient combined repair backup/restore capacity")
    print(maximum)
elif action == "evidence" and len(args) == 6:
    stage, archive, commit, updater_hash, process, maximum = args
    stage, archive = Path(stage), Path(archive)
    need(str(stage).startswith("/var/lib/betboy-context-update.")
         and archive.parent == Path("/var/lib/betboy-updater-repair/backups")
         and process.isdigit() and maximum.isdigit(), "unknown evidence scope")
    selected = {"archive": archive, "stage": stage / "online/stage.json",
        "report": stage / "online/report.json", "production": stage / "production-identity.json",
        "restore": Path(str(archive) + ".partial." + process + ".helper.log"),
        "inline": Path(str(archive) + ".partial." + process + ".inline.log"),
        "measurement": stage / "online/measurement.json"}
    records = {}
    for name, path in selected.items():
        ancestors(path.parent)
        before = path.lstat()
        bound = int(maximum) if name == "archive" else 1048576
        need(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
             and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
             and 0 <= before.st_size <= bound, "unsafe preflight evidence file")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            need(signature(os.fstat(descriptor)) == signature(before), "evidence replaced")
            checksum, total = hashlib.sha256(), 0
            while chunk := os.read(descriptor, 1048576):
                total += len(chunk)
                need(total <= bound, "evidence grew beyond bound")
                checksum.update(chunk)
            need(signature(os.fstat(descriptor)) == signature(before)
                 and signature(path.lstat()) == signature(before), "evidence changed")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        records[name] = {"path": str(path), "size": total, "sha256": checksum.hexdigest()}
    proof = json.loads(read(selected["stage"], 1048576)[0])
    measurement = json.loads(read(selected["measurement"], 1048576)[0])
    need(proof["archive_hash"] == records["archive"]["sha256"]
         and measurement["target_commit"] == commit and measurement["updater_sha256"] == updater_hash
         and measurement["database_sha256"] == proof["sealed_hash"]
         and measurement["report_sha256"] == records["report"]["sha256"], "fresh measurement/evidence binding differs")
    value = {"schema": 1, "commit": commit, "updater_sha256": updater_hash,
             "status": "accepted", "records": records}
    destination = Path("/var/lib/betboy-updater-repair/accepted-evidence.json")
    if os.path.lexists(destination):
        previous = json.loads(read(destination, 65536)[0])
        need(previous.get("commit") == commit and previous.get("updater_sha256") == updater_hash
             and previous.get("status") == "accepted", "unknown existing evidence preserved")
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix="accepted-", dir=destination.parent)
    try:
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        # Keep the exact private failed candidate as recovery evidence.
        raise
else:
    raise SystemExit("unknown repair guard operation")
PY
}

verify_repair_invocation() {
    [[ "${EUID}" == 0 ]] || die "Run the reviewed root-owned installer as root."
    repair_data parse "$@" >/dev/null
    repair_guard self "$0"
    local command
    for command in git runuser install stat sha256sum flock mktemp id chown chmod timeout head bash; do
        command -v "${command}" >/dev/null || die "Missing command: ${command}"
    done
}

verify_repair_production() {
    local marker_state marker_previous marker_status marker_target actual
    local helper=/usr/local/libexec/betboy-challenge-migration-marker.py
    verify_root_owned_file "${helper}"
    [[ "$(sha256sum "${helper}" | awk '{print $1}')" == f22065efc2f321e4eaff20d9d8d006332ffe3a99c26931fc329dab7b8d62458b ]] \
        || die "Installed marker helper pin differs."
    actual=$(git_betboy rev-parse HEAD)
    [[ "${actual}" == "${EXPECTED_PRODUCTION_HEAD}" ]] || die "Unexpected production source HEAD."
    marker_state=$(/usr/bin/python3 -I -B "${helper}" --marker "${LEDGER_MIGRATION_MARKER}" --application-root "${APP_DIR}" status)
    read -r marker_previous marker_status marker_target < <(parse_marker_state "${marker_state}")
    [[ "${marker_status}" == complete && "${marker_target}" == "${actual}" ]] \
        || die "Repair requires the existing complete production marker."
    repair_guard continuity "${actual}" "${STAGE_DIR}/production-identity.json"
}

fetch_repair_source() {
    local fetched
    root_git init --quiet "${TRUSTED_TREE}"
    root_git -C "${TRUSTED_TREE}" fetch --quiet --no-tags "${REPOSITORY_URL}" refs/heads/main
    fetched=$(root_git -C "${TRUSTED_TREE}" rev-parse FETCH_HEAD)
    [[ "${fetched}" == "${REQUESTED_HEAD}" ]] || die "Reviewed target is not the fetched origin/main tip."
    TARGET_HEAD="${fetched}"
    root_git -C "${TRUSTED_TREE}" cat-file blob "${TARGET_HEAD}:deploy/update_server.sh" >"${STAGE_DIR}/fetched-updater"
    [[ "$(sha256sum "${STAGE_DIR}/fetched-updater" | awk '{print $1}')" == "${EXPECTED_NEW_SHA256}" ]] \
        || die "Fetched Git blob differs from the reviewed updater digest."
    bash -n "${STAGE_DIR}/fetched-updater"
}

prepare_repair_source() {
    local recovered
    recovered=$(repair_data recover "${REQUESTED_HEAD}" "${EXPECTED_NEW_SHA256}")
    if [[ "${recovered}" == complete ]]; then
        REPAIR_ALREADY_COMPLETE=1
        return
    fi
    [[ "${recovered}" == old ]] || die "Unknown recovery state."
    STAGE_DIR=$(context_hook_data create-private "$(id -g betboy)")
    CONTEXT_STAGE_DIR="${STAGE_DIR}"
    TRUSTED_TREE="${STAGE_DIR}/source"
    RECOVERY_BACKUP_DIR="${REPAIR_STATE_DIR}/backups"
    repair_guard backup-dir
    verify_repair_production
    local source_kib
    source_kib=$(enumerate_backup_sources bytes)
    ARCHIVE_MAX_BYTES=$(repair_guard capacity "${STAGE_DIR}" "${RECOVERY_BACKUP_DIR}" "${source_kib}")
    fetch_repair_source
    create_trusted_manifests
    # The copied backup producer only needs the checked target helper filepath.
    TRUSTED_TREE="${TARGET_PAYLOAD}"
    configure_context_phase "${CONTEXT_STAGE_DIR}/online"
    prepare_verification_launcher
    context_hook_command "${CONTEXT_STAGE_DIR}/online/dependencies.txt" /usr/bin/python3 -I -B \
        "${CONTEXT_STAGE_DIR}/launcher.py" dependencies "${TARGET_PAYLOAD}"
    context_hook_data dependencies "${CONTEXT_STAGE_DIR}/online/dependencies.txt" "${CONTEXT_COMMAND_STATUS}"
    [[ "$(context_hook_data online-auth "${CONTEXT_STAGE_DIR}/online" "${LEDGER_HMAC_KEY}" "${LEDGER_MIGRATION_MARKER}")" == authenticated ]] \
        || die "This repair has no keyless/legacy bypass."
}

verify_repair_backup() {
    PREFLIGHT_BACKUP="${RECOVERY_BACKUP_DIR}/repair-${REQUESTED_HEAD}-${STAGE_DIR##*/}.zip"
    produce_update_backup online "${STAGE_DIR}/backup-online-work" "${PREFLIGHT_BACKUP}" "${EXPECTED_PRODUCTION_HEAD}"
}

measure_repair_d4() {
    /usr/bin/python3 -I -B - "${STAGE_DIR}" "${REQUESTED_HEAD}" "${EXPECTED_NEW_SHA256}" <<'PY'
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time


def need(condition, message):
    if not condition:
        raise ValueError(message)


def accept_measurement(value, commit, updater_hash, database_hash, report_hash):
    expected = {"schema", "target_commit", "updater_sha256", "database_sha256", "report_sha256",
                "exit_code", "wall_seconds", "cpu_seconds", "peak_rss_bytes"}
    need(type(value) is dict and set(value) == expected, "missing complete D4 measurement")
    need(type(value["schema"]) is int and value["schema"] == 1
         and value["target_commit"] == commit and value["updater_sha256"] == updater_hash
         and value["database_sha256"] == database_hash and value["report_sha256"] == report_hash,
         "measurement is not bound to this target/input/report")
    need(type(value["exit_code"]) is int, "invalid measured child status")
    if value["exit_code"] in {-9, 124, 137, 152, 153}:
        raise ValueError("VerificationResourceError: D4 child terminated at a hard resource boundary")
    need(value["exit_code"] in {0, 2}, "D4 child did not complete")
    need(type(value["peak_rss_bytes"]) is int and 0 < value["peak_rss_bytes"] < 1073741824,
         "VerificationResourceError: fresh D4 peak RSS not below 1 GiB")
    for name in ("wall_seconds", "cpu_seconds"):
        number = value[name]
        need(type(number) in {int, float} and math.isfinite(number) and 0 <= number < 300,
             "VerificationResourceError: fresh D4 measured time not below 300 seconds")


def safe_directory(path):
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
         "unsafe measurement ancestor")
    if path.parent != path:
        safe_directory(path.parent)


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def fingerprint(path, maximum):
    safe_directory(path.parent)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
         and not before.st_mode & 0o022 and 0 < before.st_size <= maximum, "unsafe measured input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(file_identity(os.fstat(fd)) == file_identity(before), "measured input replaced")
        checksum, size = hashlib.sha256(), 0
        while chunk := os.read(fd, 1048576):
            size += len(chunk)
            need(size <= maximum, "measured input grew beyond bound")
            checksum.update(chunk)
        need(file_identity(os.fstat(fd)) == file_identity(before)
             and file_identity(path.lstat()) == file_identity(before), "measured input changed")
        return checksum.hexdigest(), file_identity(before)
    finally:
        os.close(fd)


def publish(path, raw):
    safe_directory(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            need(count > 0, "short measurement write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def measure(stage, commit, updater_hash):
    need(os.geteuid() == 0 and sys.platform == "linux", "native root stdlib supervisor required")
    need(re.fullmatch(r"/var/lib/betboy-context-update\.[a-z0-9_]{8}", str(stage)), "unknown measurement stage")
    safe_directory(stage)
    database = stage / "online/context_models.db"
    report = stage / "online/report.json"
    output = stage / "online/measurement.json"
    need(not any(os.path.lexists(path) for path in (report, output)), "measurement outputs already exist")
    before = fingerprint(database, 1073741824)
    need(stat.S_IMODE(before[1][2]) == 0o440, "D4 input is not sealed")
    launcher = stage / "launcher.py"
    launcher_before = fingerprint(launcher, 16384)
    manifest_path = stage / "target-manifest.json"
    manifest_before = fingerprint(manifest_path, 1048576)
    need(json.loads(manifest_path.read_text())["revision"] == commit, "measured source commit differs")
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": "/var/tmp",
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
    command = ["/usr/sbin/runuser", "-u", "betboy", "--", "/usr/bin/timeout",
        "--foreground", "--signal=TERM", "--kill-after=10s", "600s", "/usr/bin/python3", "-I", "-B",
        str(launcher), "d4", str(stage / "target-payload"), str(database)]
    started = time.monotonic()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, env=environment, start_new_session=True)
    chunks, size, completed, usage, violation = [], 0, None, None, None
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    os.set_blocking(child.stdout.fileno(), False)
    try:
        while completed is None or selector.get_map():
            if time.monotonic() - started >= 610 and violation is None:
                violation = "VerificationResourceError: D4 hard wall boundary"
                os.killpg(child.pid, signal.SIGKILL)
            for key, _ in selector.select(0.05):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    size += len(chunk)
                    if size > 1048576:
                        if violation is None:
                            violation = "VerificationResourceError: D4 aggregate output boundary"
                            os.killpg(child.pid, signal.SIGKILL)
                    elif violation is None:
                        chunks.append(chunk)
            if completed is None:
                pid, status, measured = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    completed = os.waitstatus_to_exitcode(status)
                    usage = measured
                    child.returncode = completed
        wall = time.monotonic() - started
    finally:
        selector.close()
        child.stdout.close()
        if completed is None:
            os.killpg(child.pid, signal.SIGKILL)
            _, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
    raw = b"".join(chunks)
    publish(report, raw)
    result = {"schema": 1, "target_commit": commit, "updater_sha256": updater_hash,
        "database_sha256": before[0], "report_sha256": hashlib.sha256(raw).hexdigest(),
        "exit_code": completed, "wall_seconds": wall, "cpu_seconds": usage.ru_utime + usage.ru_stime,
        "peak_rss_bytes": usage.ru_maxrss * 1024}
    publish(output, (json.dumps(result, sort_keys=True) + "\n").encode())
    need(violation is None, violation)
    need(not any(line.startswith((b"MemoryError", b"ContextResourceError")) for line in raw.splitlines()),
         "VerificationResourceError: D4 child memory or capacity failure")
    need(fingerprint(database, 1073741824) == before
         and fingerprint(launcher, 16384) == launcher_before
         and fingerprint(manifest_path, 1048576) == manifest_before, "measured source/input changed")
    accept_measurement(result, commit, updater_hash, before[0], hashlib.sha256(raw).hexdigest())
    print(completed)


if __name__ == "__main__":
    need(len(sys.argv) == 4, "fixed measurement arguments required")
    measure(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
PY
}

verify_repair_context() {
    [[ "$(context_hook_data stage "${CONTEXT_STAGE_DIR}/online" "${PREFLIGHT_BACKUP}" online)" == present ]] \
        || die "Repair requires the present context database."
    REPAIR_D4_STATUS=$(measure_repair_d4) || die "Fresh measured D4 was not accepted."
    [[ "${REPAIR_D4_STATUS}" == 0 || "${REPAIR_D4_STATUS}" == 2 ]] || die "Invalid measured child status."
    context_hook_data finish "${CONTEXT_STAGE_DIR}/online" "${REPAIR_D4_STATUS}" online
    verify_repair_production
}

install_repair_updater() {
    verify_repair_production
    context_hook_data finish "${CONTEXT_STAGE_DIR}/online" "${REPAIR_D4_STATUS}" online
    repair_guard evidence "${STAGE_DIR}" "${PREFLIGHT_BACKUP}" "${REQUESTED_HEAD}" "${EXPECTED_NEW_SHA256}" "$$" "${ARCHIVE_MAX_BYTES}"
    repair_guard candidate "${STAGE_DIR}/fetched-updater" "${EXPECTED_NEW_SHA256}"
    repair_data install "${REQUESTED_HEAD}" "${EXPECTED_NEW_SHA256}"
    log "Installed exact updater ${EXPECTED_NEW_SHA256}; application deployment was NOT run."
    log "Preserved backup ${PREFLIGHT_BACKUP}, journal ${REPAIR_STATE_DIR}, verification ${STAGE_DIR}."
}

repair_main() {
    verify_repair_invocation "$@"
    acquire_deploy_lock
    prepare_repair_source
    if [[ "${REPAIR_ALREADY_COMPLETE:-0}" == 1 ]]; then
        log "Exact updater repair already completed; no application deployment was run."
        return
    fi
    verify_repair_backup
    verify_repair_context
    install_repair_updater
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    repair_main "$@"
fi
