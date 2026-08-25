#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /

readonly TRUSTED_BOOTSTRAP=/usr/local/sbin/betboy-bootstrap
readonly TRUSTED_UPDATER=/usr/local/sbin/betboy-update
readonly TRUSTED_BACKUP_HELPER=/usr/local/libexec/betboy-backup-runtime.py
readonly TRUSTED_BACKUP_STAGE_HELPER=/usr/local/libexec/betboy-backup-stage-runtime.py
readonly TRUSTED_MIGRATION_MARKER_HELPER=/usr/local/libexec/betboy-challenge-migration-marker.py
readonly LEDGER_HMAC_KEY=/etc/betboy/challenge-ledger-hmac.key
readonly LEDGER_MIGRATION_MARKER=/etc/betboy/challenge-ledger-v2-migrated.json
readonly REPOSITORY_URL=https://github.com/xantharu123-png/btts-pro-analyzer.git
readonly APP_DIR=/opt/betboy/app
readonly VENV_DIR=/opt/betboy/venv
readonly PUBLIC_HOST=vps-a30a123f.vps.ovh.net
readonly DEPLOY_LOCK=/run/betboy-deploy/deploy.lock

readonly -a BETBOY_TIMERS=(
    betboy-wettfinder.timer
    betboy-football-shadow.timer
    betboy-tennis.timer
    betboy-esports.timer
    betboy-redcard-settlement.timer
    betboy-redcard-history.timer
    betboy-backup.timer
)
readonly -a BETBOY_WORKERS=(
    betboy-wettfinder.service
    betboy-football-shadow.service
    betboy-tennis.service
    betboy-esports.service
    betboy-redcard-settlement.service
    betboy-redcard-history.service
    betboy-backup.service
)

REQUESTED_HEAD="${1:-}"
STAGE_DIR=""
TRUSTED_TREE=""
TRUSTED_REQUIREMENTS=""
TARGET_MANIFEST=""
DEPLOY_LOCK_FD=""
BOOTSTRAP_COMPLETE=0

log() {
    printf '[betboy-bootstrap] %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

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

safe_remove_stage() {
    if [[ -n "${STAGE_DIR}" && -d "${STAGE_DIR}" \
        && "${STAGE_DIR}" == /var/tmp/betboy-bootstrap.* ]]; then
        rm -rf --one-file-system -- "${STAGE_DIR}" \
            || log "WARN: could not remove staging ${STAGE_DIR}"
    fi
    return 0
}

trap safe_remove_stage EXIT

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

verify_invocation() {
    local invoked_as
    [[ "${EUID}" -eq 0 ]] || die "Run the root-owned bootstrap as root."
    [[ "$#" -eq 1 ]] || die "Usage: ${TRUSTED_BOOTSTRAP} <40-hex-origin-main-commit>"
    [[ "${REQUESTED_HEAD}" =~ ^[0-9A-Fa-f]{40}$ ]] \
        || die "Target must be an explicit 40-hex commit."
    REQUESTED_HEAD="${REQUESTED_HEAD,,}"
    invoked_as=$(readlink -f "$0")
    [[ "${invoked_as}" == "${TRUSTED_BOOTSTRAP}" ]] \
        || die "Refusing sudo execution from a writable checkout; use ${TRUSTED_BOOTSTRAP}."
    verify_root_owned_file "${TRUSTED_BOOTSTRAP}"
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
        -c protocol.file.allow=never \
        "$@"
}

as_betboy() {
    runuser -u betboy -- "$@"
}

ensure_ledger_hmac_key() {
    /usr/bin/python3 -I \
        "$(trusted_file scripts/manage_challenge_integrity_key.py)" \
        --key "${LEDGER_HMAC_KEY}" \
        --application-root "${APP_DIR}" \
        --marker "${LEDGER_MIGRATION_MARKER}" \
        --group betboy \
        --production \
        --fresh-install
}

ensure_backup_principal() {
    local group_exists=0
    local user_exists=0

    getent group betboy-backup >/dev/null && group_exists=1
    getent passwd betboy-backup >/dev/null && user_exists=1
    [[ "${group_exists}" == "${user_exists}" ]] \
        || die "Only one of backup user/group exists; refusing to adopt it."
    if [[ "${group_exists}" == 0 ]]; then
        groupadd --system betboy-backup
        useradd --system --gid betboy-backup \
            --home-dir /var/lib/betboy-backup --no-create-home \
            --shell /usr/sbin/nologin betboy-backup
    fi
    verify_backup_principal
    if [[ -e /var/lib/betboy-backup || -L /var/lib/betboy-backup ]]; then
        verify_backup_home
    else
        install -d -m 0700 -o betboy-backup -g betboy-backup \
            /var/lib/betboy-backup
    fi
    verify_backup_home
}

verify_backup_principal() {
    local group_entry
    local group_gid
    local group_name
    local password_status
    local user_entry
    local user_gid
    local user_home
    local user_name
    local user_shell
    local user_uid

    group_entry=$(getent group betboy-backup) \
        || die "Backup group is missing."
    user_entry=$(getent passwd betboy-backup) \
        || die "Backup account is missing."
    IFS=: read -r group_name _ group_gid _ <<<"${group_entry}"
    IFS=: read -r user_name _ user_uid user_gid _ user_home user_shell \
        <<<"${user_entry}"
    [[ "${group_name}" == betboy-backup && "${user_name}" == betboy-backup ]] \
        || die "Backup principal names are inconsistent."
    [[ "${user_gid}" == "${group_gid}" ]] \
        || die "Backup account has an unexpected primary group."
    [[ "${user_uid}" =~ ^[0-9]+$ && "${group_gid}" =~ ^[0-9]+$ \
        && "${user_uid}" -gt 0 && "${user_uid}" -lt 1000 \
        && "${group_gid}" -gt 0 && "${group_gid}" -lt 1000 ]] \
        || die "Backup principal is not a non-root system principal."
    [[ "${user_home}" == /var/lib/betboy-backup \
        && "${user_shell}" == /usr/sbin/nologin ]] \
        || die "Backup account has unexpected home or shell."
    [[ "$(id -nG betboy-backup)" == betboy-backup ]] \
        || die "Backup account must not have persistent supplementary groups."
    read -r _ password_status _ < <(passwd -S betboy-backup)
    [[ "${password_status}" == L ]] \
        || die "Backup account password is not locked."
}

verify_backup_home() {
    [[ -d /var/lib/betboy-backup && ! -L /var/lib/betboy-backup ]] \
        || die "Backup home is not a real directory."
    [[ "$(stat -c '%U:%G' /var/lib/betboy-backup)" \
        == betboy-backup:betboy-backup \
        && "$(stat -c '%a' /var/lib/betboy-backup)" == 700 ]] \
        || die "Backup home has unexpected owner or mode."
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

install_root_file_atomic() {
    local source="$1"
    local destination="$2"
    local mode="$3"
    local owner="$4"
    local group="$5"
    /usr/bin/python3 -I - \
        "${source}" "${destination}" "${mode}" "${owner}" "${group}" <<'PY'
import grp
import os
from pathlib import Path
import pwd
import secrets
import stat
import sys

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
mode = int(sys.argv[3], 8)
uid = pwd.getpwnam(sys.argv[4]).pw_uid
gid = grp.getgrnam(sys.argv[5]).gr_gid
source_info = source.lstat()
parent_info = destination.parent.lstat()
if (
    not stat.S_ISREG(source_info.st_mode)
    or source.is_symlink()
    or source_info.st_nlink != 1
):
    raise SystemExit("atomic install source is unsafe")
if (
    not stat.S_ISDIR(parent_info.st_mode)
    or destination.parent.is_symlink()
    or parent_info.st_uid != 0
    or parent_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
):
    raise SystemExit("atomic install parent is unsafe")
if os.path.lexists(destination):
    destination_info = destination.lstat()
    if not stat.S_ISREG(destination_info.st_mode) or destination.is_symlink():
        raise SystemExit("atomic install destination is unsafe")
temporary = destination.parent / (
    f".{destination.name}.{os.getpid()}.{secrets.token_hex(8)}.partial"
)
read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
try:
    source_fd = os.open(source, read_flags)
    try:
        temporary_fd = os.open(temporary, write_flags, 0o600)
        try:
            while True:
                chunk = os.read(source_fd, 1024 * 1024)
                if not chunk:
                    break
                written = 0
                while written < len(chunk):
                    count = os.write(temporary_fd, chunk[written:])
                    if count <= 0:
                        raise OSError("short atomic root-file write")
                    written += count
            os.fchown(temporary_fd, uid, gid)
            os.fchmod(temporary_fd, mode)
            os.fsync(temporary_fd)
        finally:
            os.close(temporary_fd)
    finally:
        os.close(source_fd)
    os.replace(temporary, destination)
    directory_fd = os.open(
        destination.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
finally:
    try:
        temporary.unlink()
    except FileNotFoundError:
        pass
PY
}

expected_unit_sha256() {
    case "$1" in
        deploy/systemd/betboy-app.service) printf '%s\n' 90d5047df1ef96e6a4bc9d2a3e888ca6c14d64d62c3526470a64d088788145b8 ;;
        deploy/systemd/betboy-backup.service) printf '%s\n' c5d5248eb672f3f242ecfed74634d9abf0af003fe0bc7bb68f51f8279f45cdc1 ;;
        deploy/systemd/betboy-backup.timer) printf '%s\n' 918fd587a63dd57eb538c0e49d3f1dc13ffe1db9c99e46eeb2e4144605596aaa ;;
        deploy/systemd/betboy-esports.service) printf '%s\n' 1df7e7c001c093c211ce03ae3c0ac57ce8030f9c3da008e1ee04e431ca9cfd8b ;;
        deploy/systemd/betboy-esports.timer) printf '%s\n' 97fd05b6df1df5afdb2b109f75ea1ad6354da3801300056e478b9a53ea320a6c ;;
        deploy/systemd/betboy-football-shadow.service) printf '%s\n' 0e9bf4d73bc8db2b2dee201b116d63f86c0dcd953a5458e0f6c8ea00df33a149 ;;
        deploy/systemd/betboy-football-shadow.timer) printf '%s\n' a311d307bc5a604cba565b97212d815c8c9e5a085844dfa302ea4a1fb62d67bf ;;
        deploy/systemd/betboy-redcard-history.service) printf '%s\n' a063bd88657bfbcffe804732c48c5302b98c3fd869864383a62f6b2f1daa8795 ;;
        deploy/systemd/betboy-redcard-history.timer) printf '%s\n' cea8127dd10cfe3e911cd0d2f516576964109339e2303792f3c4282a260e26fb ;;
        deploy/systemd/betboy-redcard-settlement.service) printf '%s\n' f2bdb5ed768012258ecec20f3ba91c0f8290853218f26842524a210aa1ba767a ;;
        deploy/systemd/betboy-redcard-settlement.timer) printf '%s\n' 86b28ef068b75854e2ce1536b11ac9982c9410a9f1716dfeaa7d6045918bba16 ;;
        deploy/systemd/betboy-tennis.service) printf '%s\n' 8f0239135e214f1ffe2cdf1adeda62d2852b5a9ff36ebdf5a1d347850cbef146 ;;
        deploy/systemd/betboy-tennis.timer) printf '%s\n' d1c58a3a36736f557d17d68cec6ef64d52e60e7c539d9af463341bb7df27b118 ;;
        deploy/systemd/betboy-wettfinder.service) printf '%s\n' 698cbda1b157603f735e079c9f30b25bdfb1d78b74d693b8a05036b811d36d1b ;;
        deploy/systemd/betboy-wettfinder.timer) printf '%s\n' 7e26d233ba13afade225ff4b97f00b23a0954b798f7948a927a492563e335db4 ;;
        *) die "Unit is not byte-allowlisted: $1" ;;
    esac
}

expected_backup_stage_helper_sha256() {
    printf '%s\n' 50a1dfefcca43f07a397654d09954dce9aafbceb4b2f677bfa3c46ac41abd865
}

validate_trusted_backup_stage_helper() {
    local path
    local actual
    path=$(trusted_file scripts/stage_runtime_databases.py)
    actual=$(sha256sum -- "${path}" | awk '{print $1}')
    [[ "${actual}" == "$(expected_backup_stage_helper_sha256)" ]] \
        || die "Privileged backup stage helper differs from reviewed bytes."
}

validate_trusted_unit() {
    local relative="$1"
    local path
    local expected
    local actual
    path=$(trusted_file "${relative}")
    expected=$(expected_unit_sha256 "${relative}")
    actual=$(sha256sum -- "${path}" | awk '{print $1}')
    [[ "${actual}" == "${expected}" ]] \
        || die "${relative} differs from its reviewed byte allowlist."
}

verify_installed_unit() {
    local name="$1"
    local path="/etc/systemd/system/${name}"
    local expected
    local actual
    local fragment
    local dropins
    verify_root_owned_file "${path}"
    expected=$(expected_unit_sha256 "deploy/systemd/${name}")
    actual=$(sha256sum -- "${path}" | awk '{print $1}')
    fragment=$(systemctl show "${name}" -p FragmentPath --value)
    dropins=$(systemctl show "${name}" -p DropInPaths --value)
    [[ "${actual}" == "${expected}" && "${fragment}" == "${path}" \
        && -z "${dropins}" ]] \
        || die "Installed ${name} failed byte, fragment or drop-in policy."
}

verify_no_unit_dropin_paths() {
    local search_root
    local found
    for search_root in \
        /etc/systemd/system /etc/systemd/system.control \
        /run/systemd/system /run/systemd/system.control \
        /run/systemd/generator.early /run/systemd/generator \
        /run/systemd/generator.late \
        /usr/local/lib/systemd/system /usr/lib/systemd/system \
        /lib/systemd/system; do
        [[ -d "${search_root}" ]] || continue
        found=$(find "${search_root}" -mindepth 1 -maxdepth 1 \
            \( -name 'betboy-*.service.d' -o -name 'betboy-*.timer.d' \
               -o -name 'service.d' -o -name 'timer.d' \) \
            -print -quit)
        [[ -z "${found}" ]] \
            || die "Forbidden systemd drop-in path exists: ${found}"
    done
}

check_no_betboy_processes() {
    local account
    local pids
    for account in betboy betboy-backup; do
        getent passwd "${account}" >/dev/null || continue
        pids=$(pgrep -u "${account}" || true)
        [[ -z "${pids}" ]] || return 1
    done
    return 0
}

verify_no_betboy_processes() {
    check_no_betboy_processes \
        || die "Unexpected betboy/betboy-backup process exists on this fresh host."
}

durable_os_sync() {
    /usr/bin/python3 -I - <<'PY'
import os

os.sync()
PY
}

persist_runtime_autostart_disabled() {
    local failed=0
    local state
    local unit
    local worker

    # Static workers can make disable return non-zero.  The authoritative
    # outcome is checked unit-by-unit after the durable sync.
    systemctl disable betboy-app.service \
        "${BETBOY_TIMERS[@]}" "${BETBOY_WORKERS[@]}" >/dev/null 2>&1 || true
    durable_os_sync || failed=1
    for unit in betboy-app.service "${BETBOY_TIMERS[@]}"; do
        state=$(systemctl is-enabled "${unit}" 2>/dev/null || true)
        if [[ "${state}" != disabled && "${state}" != not-found ]]; then
            failed=1
            log "Runtime unit is not disabled/absent (${state:-error}): ${unit}"
        fi
    done
    for worker in "${BETBOY_WORKERS[@]}"; do
        state=$(systemctl is-enabled "${worker}" 2>/dev/null || true)
        if [[ "${state}" != static && "${state}" != disabled \
            && "${state}" != not-found ]]; then
            failed=1
            log "Worker unit is not static/disabled/absent (${state:-error}): ${worker}"
        fi
    done
    return "${failed}"
}

force_runtime_fail_closed() {
    local failed=0
    local unit

    # Disable first so an inactive legacy timer/linked worker cannot win the
    # stop race while the gated replacement units are being installed.
    persist_runtime_autostart_disabled || failed=1
    systemctl stop "${BETBOY_TIMERS[@]}" >/dev/null 2>&1 || true
    systemctl stop "${BETBOY_WORKERS[@]}" >/dev/null 2>&1 || true
    systemctl stop betboy-app.service >/dev/null 2>&1 || true
    for unit in betboy-app.service \
        "${BETBOY_TIMERS[@]}" "${BETBOY_WORKERS[@]}"; do
        if systemctl is-active --quiet "${unit}"; then
            failed=1
            log "Runtime unit remained active across the bootstrap boundary: ${unit}"
        fi
    done
    if ! check_no_betboy_processes; then
        failed=1
        log "A betboy/betboy-backup process remains outside the stopped units."
    fi
    return "${failed}"
}

recover_bootstrap() {
    local status="$1"

    trap - EXIT
    set +e
    if [[ "${status}" == 0 && "${BOOTSTRAP_COMPLETE}" == 1 ]]; then
        safe_remove_stage
        return
    fi
    [[ "${status}" != 0 ]] || status=1
    log "Bootstrap failed; forcing every BetBoy runtime unit down and disabled."
    if force_runtime_fail_closed; then
        log "All BetBoy runtime units are stopped and durably disabled."
    else
        log "FAIL-CLOSED verification failed; inspect unit state before recovery."
    fi
    safe_remove_stage
    exit "${status}"
}

create_target_manifest() {
    TARGET_MANIFEST="${STAGE_DIR}/target-manifest.json"
    /usr/bin/python3 -I - \
        "${TRUSTED_TREE}" "${REQUESTED_HEAD}" "${TARGET_MANIFEST}" <<'PY'
import hashlib
import json
import re
import subprocess
import sys

repo, target, output = sys.argv[1:]
env = {
    "HOME": "/root",
    "PATH": "/usr/bin:/bin",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def git(*args: str) -> bytes:
    return subprocess.run(
        [
            "/usr/bin/git", "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false", "-c", "credential.helper=",
            "-C", repo, *args,
        ],
        check=True,
        stdout=subprocess.PIPE,
        env=env,
    ).stdout


files = {}
for record in git("ls-tree", "-rz", target).split(b"\0"):
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
    name = path.rsplit("/", 1)[-1]
    protected = bool(
        path == "config.ini"
        or path == ".streamlit/secrets.toml"
        or path.startswith(("runtime_state/", "runtime_reports/", "backups_runtime/"))
        or re.search(r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$", name)
        or name == ".env"
    )
    if protected:
        raise SystemExit(f"target tracks protected runtime path: {path}")
    blob = git("cat-file", "blob", oid)
    files[path] = {
        "mode": mode,
        "sha256": hashlib.sha256(blob).hexdigest(),
    }

with open(output, "w", encoding="utf-8", newline="\n") as handle:
    json.dump({"revision": target, "files": files}, handle, sort_keys=True)
    handle.write("\n")
PY
    chown root:betboy "${TARGET_MANIFEST}"
    chmod 0640 "${TARGET_MANIFEST}"
}

verify_app_bytes() {
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${APP_DIR}" "${TARGET_MANIFEST}" <<'PY'
import hashlib
import json
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
resolved_root = root.resolve(strict=True)
if resolved_root != root.absolute():
    raise SystemExit("application root must not traverse a symlink")
with open(sys.argv[2], encoding="utf-8") as handle:
    manifest = json.load(handle)
for relative, expected in manifest["files"].items():
    path = root.joinpath(*relative.split("/"))
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"tracked path is not a regular file: {relative}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SystemExit(f"tracked path escapes app root: {relative}") from exc
    if resolved != path.absolute():
        raise SystemExit(f"tracked path traverses a symlink: {relative}")
    actual_mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_mode != expected["mode"] or digest != expected["sha256"]:
        raise SystemExit(f"tracked target mismatch: {relative}")
PY
}

verify_untracked_policy() {
    local inventory="${STAGE_DIR}/untracked-paths.bin"
    git_betboy ls-files -z --others --exclude-standard >"${inventory}"
    git_betboy ls-files -z --others --ignored --exclude-standard >>"${inventory}"
    chown root:betboy "${inventory}"
    chmod 0640 "${inventory}"
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${APP_DIR}" "${inventory}" <<'PY'
import re
import stat
import sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1])
resolved_root = root.resolve(strict=True)
paths = sorted({
    raw.decode("utf-8", "strict")
    for raw in Path(sys.argv[2]).read_bytes().split(b"\0") if raw
})
dangerous = (".py", ".pyc", ".pyo", ".so", ".pth", ".egg-link", ".sh")
for relative in paths:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or any(ord(c) < 32 for c in relative):
        raise SystemExit(f"unsafe untracked path: {relative!r}")
    if relative.lower().endswith(dangerous):
        raise SystemExit(f"untracked executable/code file is forbidden: {relative}")
    path = root.joinpath(*pure.parts)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o111:
        raise SystemExit(f"untracked non-data entry is forbidden: {relative}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SystemExit(f"untracked path escapes app root: {relative}") from exc
    if resolved != path.absolute():
        raise SystemExit(f"untracked path traverses a symlink: {relative}")
    name = relative.rsplit("/", 1)[-1]
    allowed = bool(
        relative in {"config.ini", ".env", ".streamlit/secrets.toml"}
        or relative.startswith(("runtime_state/", "runtime_reports/"))
        or re.fullmatch(r"\.shadow_cache/[^/]+\.pkl", relative)
        or re.fullmatch(r"scan_jobs/(?:.*/)?[^/]+\.json", relative)
        or re.search(r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$", name)
        or re.fullmatch(r"logs/pipeline_[^/]+\.log", relative)
        or re.fullmatch(r"reports/weekly_[^/]+\.html", relative)
        or relative == "tennis/data/calibration_watch_latest.json"
    )
    if not allowed:
        raise SystemExit(f"untracked path is outside the runtime allowlist: {relative}")
PY
}

prepare_trusted_tree() {
    local fetched_head
    local timer

    STAGE_DIR=$(mktemp -d /var/tmp/betboy-bootstrap.XXXXXXXX)
    chown root:betboy "${STAGE_DIR}"
    chmod 0750 "${STAGE_DIR}"
    TRUSTED_TREE="${STAGE_DIR}/source"
    root_git init --quiet "${TRUSTED_TREE}"
    root_git -C "${TRUSTED_TREE}" fetch --quiet --no-tags --depth=1 \
        "${REPOSITORY_URL}" refs/heads/main
    fetched_head=$(root_git -C "${TRUSTED_TREE}" rev-parse FETCH_HEAD)
    [[ "${fetched_head}" == "${REQUESTED_HEAD}" ]] \
        || die "Requested commit is not the current origin/main tip (${fetched_head})."
    root_git -C "${TRUSTED_TREE}" checkout --quiet --detach "${REQUESTED_HEAD}"
    create_target_manifest

    trusted_file requirements.txt >/dev/null
    TRUSTED_REQUIREMENTS="${STAGE_DIR}/requirements.txt"
    install -o root -g betboy -m 0640 \
        "$(trusted_file requirements.txt)" "${TRUSTED_REQUIREMENTS}"
    trusted_file deploy/update_server.sh >/dev/null
    trusted_file deploy/bootstrap_server.sh >/dev/null
    trusted_file scripts/backup_runtime_databases.py >/dev/null
    validate_trusted_backup_stage_helper
    trusted_file scripts/manage_challenge_integrity_key.py >/dev/null
    trusted_file scripts/manage_challenge_migration_marker.py >/dev/null
    trusted_file scripts/migrate_challenge_ledgers.py >/dev/null
    trusted_file deploy/systemd/betboy-app.service >/dev/null
    validate_trusted_unit deploy/systemd/betboy-app.service
    for timer in "${BETBOY_TIMERS[@]}"; do
        trusted_file "deploy/systemd/${timer}" >/dev/null
        trusted_file "deploy/systemd/${timer%.timer}.service" >/dev/null
        validate_trusted_unit "deploy/systemd/${timer}"
        validate_trusted_unit "deploy/systemd/${timer%.timer}.service"
    done
    bash -n "$(trusted_file deploy/update_server.sh)"
    bash -n "$(trusted_file deploy/bootstrap_server.sh)"
    systemd-analyze verify \
        "$(trusted_file deploy/systemd/betboy-app.service)" \
        "${BETBOY_TIMERS[@]/#/${TRUSTED_TREE}\/deploy\/systemd\/}" \
        "${BETBOY_WORKERS[@]/#/${TRUSTED_TREE}\/deploy\/systemd\/}"
}

prepare_app_checkout() {
    local branch
    local current_head
    local wrong_owner

    [[ ! -L /opt/betboy ]] || die "/opt/betboy must not be a symlink."
    [[ ! -L "${APP_DIR}" ]] || die "${APP_DIR} must not be a symlink."
    [[ -d "${APP_DIR}/.git" ]] \
        || die "Clone the app to ${APP_DIR} before bootstrap."
    wrong_owner=$(find -P "${APP_DIR}" -xdev \
        \( ! -user betboy -o ! -group betboy \) -print -quit)
    [[ -z "${wrong_owner}" ]] \
        || die "App checkout is not wholly betboy-owned: ${wrong_owner}"
    if ! git_betboy diff --cached --quiet --no-ext-diff --no-textconv \
        --ignore-submodules --; then
        die "Staged app changes exist; preserve or resolve them first."
    fi
    branch=$(git_betboy symbolic-ref --quiet --short HEAD) \
        || die "Detached app HEAD is not bootstrap-safe."
    [[ "${branch}" == main ]] || die "Expected app branch main, found ${branch}."
    current_head=$(git_betboy rev-parse HEAD)
    [[ "${current_head}" == "${REQUESTED_HEAD}" ]] \
        || die "Initial checkout must already equal the authorized target."
    verify_untracked_policy
    verify_app_bytes
}

install_trusted_units_and_tools() {
    local timer
    install -d -m 0755 -o root -g root /usr/local/libexec
    install_root_file_atomic \
        "$(trusted_file deploy/update_server.sh)" "${TRUSTED_UPDATER}" \
        0755 root root
    install_root_file_atomic \
        "$(trusted_file deploy/bootstrap_server.sh)" "${TRUSTED_BOOTSTRAP}" \
        0755 root root
    install_root_file_atomic \
        "$(trusted_file scripts/backup_runtime_databases.py)" \
        "${TRUSTED_BACKUP_HELPER}" 0755 root root
    install_root_file_atomic \
        "$(trusted_file scripts/stage_runtime_databases.py)" \
        "${TRUSTED_BACKUP_STAGE_HELPER}" 0755 root root
    install_root_file_atomic \
        "$(trusted_file scripts/manage_challenge_migration_marker.py)" \
        "${TRUSTED_MIGRATION_MARKER_HELPER}" 0755 root root
    install_root_file_atomic \
        "$(trusted_file deploy/systemd/betboy-app.service)" \
        /etc/systemd/system/betboy-app.service 0644 root root
    for timer in "${BETBOY_TIMERS[@]}"; do
        install_root_file_atomic \
            "$(trusted_file deploy/systemd/${timer})" \
            "/etc/systemd/system/${timer}" 0644 root root
        install_root_file_atomic \
            "$(trusted_file deploy/systemd/${timer%.timer}.service)" \
            "/etc/systemd/system/${timer%.timer}.service" 0644 root root
    done
}

prepare_backup_storage_and_sources() {
    local database
    local owner
    local parent

    [[ -d /var/backups && ! -L /var/backups ]] \
        || die "/var/backups must be a real directory."
    [[ ! -L /var/backups/betboy ]] \
        || die "Backup destination must not be a symlink."
    install -d -m 0700 -o betboy-backup -g betboy-backup \
        /var/backups/betboy

    while IFS= read -r -d '' database; do
        owner=$(stat -c '%U' "${database}")
        [[ "${owner}" == betboy ]] \
            || die "Runtime database is not owned by betboy: ${database}"
        chgrp betboy "${database}"
        chmod u=rw,g=r,o= "${database}"
        parent=$(dirname "${database}")
        while [[ "${parent}" == "${APP_DIR}" \
            || "${parent}" == "${APP_DIR}/"* ]]; do
            chgrp betboy "${parent}"
            chmod u=rwx,g=rx,o= "${parent}"
            [[ "${parent}" == "${APP_DIR}" ]] && break
            parent=$(dirname "${parent}")
        done
    done < <(
        find -P "${APP_DIR}" -xdev \
            \( -path "${APP_DIR}/.git" \
               -o -path "${APP_DIR}/.codex_test_venv" \
               -o -path "${APP_DIR}/.pytest_cache" \
               -o -path "${APP_DIR}/.pytest_tmp" \) -prune -o \
            -type f \
            \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \
               -o -name '*.db-wal' -o -name '*.db-shm' \
               -o -name '*.sqlite-wal' -o -name '*.sqlite-shm' \
               -o -name '*.sqlite3-wal' -o -name '*.sqlite3-shm' \
               -o -name '*.db-journal' -o -name '*.sqlite-journal' \
               -o -name '*.sqlite3-journal' \) \
            -print0
    )
}

prepare_readonly_backup_sources() {
    verify_no_betboy_processes
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I "${TRUSTED_BACKUP_HELPER}" \
        --root "${APP_DIR}" \
        --prepare-readonly-sources \
        --offline-confirmed
}

verify_invocation "$@"
command -v git >/dev/null || die "Install Git before the trusted bootstrap."
for required_command in \
    git runuser systemctl systemd-analyze install awk grep bash readlink \
    stat find chown chgrp chmod sha256sum pgrep getent groupadd useradd \
    passwd id dirname flock; do
    command -v "${required_command}" >/dev/null \
        || die "Missing prerequisite command: ${required_command}"
done
[[ -x /usr/bin/python3 ]] || die "Missing trusted /usr/bin/python3."
acquire_deploy_lock
trap 'recover_bootstrap "$?"' EXIT
force_runtime_fail_closed \
    || die "Existing BetBoy runtime could not be made durably fail-closed."
getent passwd betboy >/dev/null \
    || die "Create the betboy service account before bootstrap (see deploy/README.md)."
ensure_backup_principal
verify_no_unit_dropin_paths
verify_no_betboy_processes
for unit in betboy-app.service "${BETBOY_TIMERS[@]}" "${BETBOY_WORKERS[@]}"; do
    if systemctl is-active --quiet "${unit}"; then
        die "Existing BetBoy runtime is active; use ${TRUSTED_UPDATER}, not bootstrap."
    fi
done
[[ ! -e "${VENV_DIR}" && ! -L "${VENV_DIR}" ]] \
    || die "Existing venv found; bootstrap is only for a fresh installation."
REMOTE_MAIN=$(
    root_git ls-remote "${REPOSITORY_URL}" refs/heads/main | awk '{print $1}'
)
[[ "${REMOTE_MAIN}" == "${REQUESTED_HEAD}" ]] \
    || die "Requested commit is not the current origin/main tip (${REMOTE_MAIN})."
prepare_trusted_tree
prepare_app_checkout

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    caddy \
    fail2ban \
    git \
    python3-pip \
    python3-venv \
    sqlite3 \
    ufw \
    unattended-upgrades

timedatectl set-timezone Europe/Zurich

if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile
fi
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
    swapon /swapfile
fi
if ! grep -q '^/swapfile ' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
cat > /etc/sysctl.d/99-betboy-memory.conf <<'EOF'
vm.swappiness=10
EOF
sysctl --system >/dev/null

[[ ! -L /opt/betboy ]] || die "/opt/betboy must not be a symlink."
[[ ! -L "${APP_DIR}" ]] || die "${APP_DIR} must not be a symlink."
install -d -m 0750 -o betboy -g betboy /opt/betboy
install -d -m 0750 -o root -g betboy /etc/betboy
install -d -m 0700 -o betboy-backup -g betboy-backup /var/backups/betboy
touch /etc/betboy/betboy.env
chown root:betboy /etc/betboy/betboy.env
chmod 0640 /etc/betboy/betboy.env
ensure_ledger_hmac_key

as_betboy python3 -m venv "${VENV_DIR}"
as_betboy "${VENV_DIR}/bin/python" -m pip install --upgrade pip
as_betboy env PIP_NO_CACHE_DIR=1 \
    "${VENV_DIR}/bin/python" -m pip install \
    -r "${TRUSTED_REQUIREMENTS}"
as_betboy "${VENV_DIR}/bin/python" -m pip check
verify_untracked_policy
verify_app_bytes
verify_no_betboy_processes

install_trusted_units_and_tools
systemctl daemon-reload
verify_no_unit_dropin_paths
verify_installed_unit betboy-app.service
for timer in "${BETBOY_TIMERS[@]}"; do
    verify_installed_unit "${timer}"
    verify_installed_unit "${timer%.timer}.service"
done
prepare_backup_storage_and_sources
prepare_readonly_backup_sources
/usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}" \
    --marker "${LEDGER_MIGRATION_MARKER}" \
    --application-root "${APP_DIR}" \
    --group betboy \
    fresh --target-head "${REQUESTED_HEAD}" >/dev/null

cat > /etc/caddy/Caddyfile <<EOF
${PUBLIC_HOST} {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        Content-Security-Policy "frame-ancestors 'self'"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    reverse_proxy 127.0.0.1:8501
}
EOF
caddy validate --config /etc/caddy/Caddyfile

rm -f /etc/ssh/sshd_config.d/99-betboy.conf
cat > /etc/ssh/sshd_config.d/00-betboy.conf <<'EOF'
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
AllowUsers ubuntu
EOF
sshd -t

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl enable --now fail2ban
systemctl enable --now unattended-upgrades
systemctl enable --now caddy
systemctl reload ssh

verify_no_betboy_processes
systemctl start betboy-app.service
curl --fail --silent --show-error \
    --retry 12 --retry-all-errors --retry-delay 2 \
    --connect-timeout 3 --max-time 5 \
    http://127.0.0.1:8501/_stcore/health | grep -qx 'ok'
systemctl start "${BETBOY_TIMERS[@]}"
systemctl is-active --quiet betboy-app.service
for timer in "${BETBOY_TIMERS[@]}"; do
    systemctl is-active --quiet "${timer}"
done
for worker in "${BETBOY_WORKERS[@]}"; do
    [[ "$(systemctl is-enabled "${worker}" 2>/dev/null || true)" == static ]] \
        || die "Worker service must remain exactly static: ${worker}"
done

# Make runtime persistence the final mutation, after the live health gate.
systemctl enable betboy-app.service "${BETBOY_TIMERS[@]}"
durable_os_sync
[[ "$(systemctl is-enabled betboy-app.service 2>/dev/null || true)" == enabled ]]
for timer in "${BETBOY_TIMERS[@]}"; do
    [[ "$(systemctl is-enabled "${timer}" 2>/dev/null || true)" == enabled ]]
done

BOOTSTRAP_COMPLETE=1
log "Bootstrap complete at ${REQUESTED_HEAD}: https://${PUBLIC_HOST}"
log "Future updates: sudo ${TRUSTED_UPDATER} <40-hex-origin-main-commit>"
