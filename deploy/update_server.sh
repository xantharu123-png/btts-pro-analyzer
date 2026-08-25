#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /

readonly TRUSTED_UPDATER=/usr/local/sbin/betboy-update
readonly TRUSTED_BOOTSTRAP=/usr/local/sbin/betboy-bootstrap
readonly TRUSTED_BACKUP_HELPER=/usr/local/libexec/betboy-backup-runtime.py
readonly TRUSTED_BACKUP_STAGE_HELPER=/usr/local/libexec/betboy-backup-stage-runtime.py
readonly TRUSTED_MIGRATION_MARKER_HELPER=/usr/local/libexec/betboy-challenge-migration-marker.py
readonly LEDGER_HMAC_KEY=/etc/betboy/challenge-ledger-hmac.key
readonly LEDGER_MIGRATION_MARKER=/etc/betboy/challenge-ledger-v2-migrated.json
readonly REPOSITORY_URL=https://github.com/xantharu123-png/btts-pro-analyzer.git
readonly APP_DIR=/opt/betboy/app
readonly VENV_DIR=/opt/betboy/venv
readonly HEALTH_URL=http://127.0.0.1:8501/_stcore/health
readonly PUBLIC_HOST=vps-a30a123f.vps.ovh.net
readonly RECOVERY_BACKUP_DIR=/var/backups/betboy-update
readonly DEPLOY_LOCK=/run/betboy-deploy/deploy.lock
readonly WORKER_WAIT_SECONDS=600

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
UPDATE_STARTED=0
UPDATE_COMPLETE=0
APP_STOPPED=0
DATABASE_MIGRATION_STARTED=0
NEW_APP_STARTED=0
PREVIOUS_HEAD=""
TARGET_HEAD=""
FRESH_BACKUP=""
STAGE_DIR=""
TRUSTED_TREE=""
ROLLBACK_ROOT=""
TARGET_MANIFEST=""
PREVIOUS_MANIFEST=""
TARGET_PAYLOAD=""
PREVIOUS_PAYLOAD=""
APP_WAS_ACTIVE=0
APP_WAS_ENABLED=0
BACKUP_HELPER_WAS_PRESENT=0
BACKUP_STAGE_HELPER_WAS_PRESENT=0
MIGRATION_MARKER_HELPER_WAS_PRESENT=0
BACKUP_USER_WAS_PRESENT=0
BACKUP_GROUP_WAS_PRESENT=0
BACKUP_HOME_WAS_PRESENT=0
BACKUP_DIR_WAS_PRESENT=0
BACKUP_DIR_UID=""
BACKUP_DIR_GID=""
BACKUP_DIR_MODE=""
CADDY_UID=""
CADDY_GID=""
CADDY_MODE=""
SOURCE_METADATA_MANIFEST=""
BACKUP_ARCHIVE_INVENTORY=""
BACKUP_PROBE_ARCHIVE=""
PREVIOUS_CHALLENGE_WRITER_BLOB=""
DEPLOY_LOCK_FD=""
AUTHORIZED_MAIN_HEAD=""
MIGRATION_RESUME_TARGET=0
MIGRATION_MARKER_PREVIOUS_HEAD=""
MIGRATION_MARKER_STATUS=""
declare -A TIMER_WAS_ACTIVE=()
declare -A TIMER_WAS_ENABLED=()

log() {
    printf '[betboy-update] %s\n' "$*"
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
        --production
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

safe_remove_stage() {
    if [[ -n "${STAGE_DIR}" && -d "${STAGE_DIR}" \
        && "${STAGE_DIR}" == /var/tmp/betboy-update.* ]]; then
        rm -rf --one-file-system -- "${STAGE_DIR}" \
            || log "WARN: could not remove staging ${STAGE_DIR}"
    fi
    return 0
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
        deploy/systemd/betboy-backup.service) printf '%s\n' 922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8 ;;
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
    printf '%s\n' b11704036e7a6f2302970a12395cd120b4ec26c76eb60f63618896f5bef85e6d
}

reviewed_backup_stage_target_sha256() {
    printf '%s\n' 1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026
}

target_backup_stage_helper_sha256() {
    local path
    local actual
    local reviewed
    path=$(trusted_file scripts/stage_runtime_databases.py)
    actual=$(sha256sum -- "${path}" | awk '{print $1}')
    reviewed=$(expected_backup_stage_helper_sha256)
    if [[ "${actual}" == "${reviewed}" \
        || "${actual}" == "$(reviewed_backup_stage_target_sha256)" ]]; then
        printf '%s\n' "${actual}"
        return
    fi
    die "Privileged backup stage helper differs from both reviewed transition hashes."
}

validate_trusted_backup_stage_helper() {
    local path
    local actual
    path=$(trusted_file scripts/stage_runtime_databases.py)
    actual=$(sha256sum -- "${path}" | awk '{print $1}')
    [[ "${actual}" == "$(target_backup_stage_helper_sha256)" ]] \
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

check_installed_unit() {
    local name="$1"
    local expected_override="${2:-}"
    local path="/etc/systemd/system/${name}"
    local actual
    local fragment
    local dropins
    local owner
    local mode
    [[ -f "${path}" && ! -L "${path}" ]] || return 1
    owner=$(stat -c '%U:%G' "${path}") || return 1
    mode=$(stat -c '%a' "${path}") || return 1
    [[ "${owner}" == root:root ]] || return 1
    (( (8#${mode} & 022) == 0 )) || return 1
    actual=$(sha256sum -- "${path}" | awk '{print $1}') || return 1
    if [[ -n "${expected_override}" ]]; then
        [[ "${actual}" == "${expected_override}" ]] || return 1
    else
        [[ "${actual}" == "$(expected_unit_sha256 "deploy/systemd/${name}")" ]] \
            || return 1
    fi
    fragment=$(systemctl show "${name}" -p FragmentPath --value) || return 1
    dropins=$(systemctl show "${name}" -p DropInPaths --value) || return 1
    [[ "${fragment}" == "${path}" && -z "${dropins}" ]]
}

verify_installed_previous_unit() {
    local name="$1"
    local reference="${PREVIOUS_PAYLOAD}/deploy/systemd/${name}"
    local target_reference="${TARGET_PAYLOAD}/deploy/systemd/${name}"
    local expected
    local target_expected
    [[ -f "${reference}" && ! -L "${reference}" ]] \
        || die "Previous trusted payload lacks ${name}."
    expected=$(sha256sum -- "${reference}" | awk '{print $1}')
    if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
        [[ -f "${target_reference}" && ! -L "${target_reference}" ]] \
            || die "Target trusted payload lacks ${name}."
        target_expected=$(sha256sum -- "${target_reference}" | awk '{print $1}')
        check_installed_unit "${name}" "${expected}" \
            || check_installed_unit "${name}" "${target_expected}" \
            || die "Installed ${name} is neither migration predecessor nor target."
    else
        check_installed_unit "${name}" "${expected}" \
            || die "Installed ${name} does not match the previous trusted commit."
    fi
}

verify_installed_unit() {
    local name="$1"
    check_installed_unit "${name}" \
        || die "Installed ${name} failed byte, owner, fragment or drop-in policy."
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
        || die "Unexpected betboy process remains after service shutdown."
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

verify_invocation() {
    local invoked_as
    [[ "${EUID}" -eq 0 ]] || die "Run the root-owned updater as root."
    [[ "$#" -eq 1 ]] || die "Usage: ${TRUSTED_UPDATER} <40-hex-origin-main-commit>"
    [[ "${REQUESTED_HEAD}" =~ ^[0-9A-Fa-f]{40}$ ]] \
        || die "Target must be an explicit 40-hex commit."
    REQUESTED_HEAD="${REQUESTED_HEAD,,}"
    invoked_as=$(readlink -f "$0")
    [[ "${invoked_as}" == "${TRUSTED_UPDATER}" ]] \
        || die "Refusing sudo execution from a writable checkout; use ${TRUSTED_UPDATER}."
    verify_root_owned_file "${TRUSTED_UPDATER}"
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

prepare_trusted_tree() {
    local fetched_head
    local marker_state
    local marker_target=""
    STAGE_DIR=$(mktemp -d /var/tmp/betboy-update.XXXXXXXX)
    chown root:betboy "${STAGE_DIR}"
    chmod 0750 "${STAGE_DIR}"
    TRUSTED_TREE="${STAGE_DIR}/source"

    root_git init --quiet "${TRUSTED_TREE}"
    root_git -C "${TRUSTED_TREE}" fetch --quiet --no-tags \
        "${REPOSITORY_URL}" refs/heads/main
    fetched_head=$(root_git -C "${TRUSTED_TREE}" rev-parse FETCH_HEAD)
    AUTHORIZED_MAIN_HEAD="${fetched_head}"
    if [[ -e "${LEDGER_MIGRATION_MARKER}" \
        || -L "${LEDGER_MIGRATION_MARKER}" ]]; then
        [[ -x "${TRUSTED_MIGRATION_MARKER_HELPER}" ]] \
            || die "Migration marker exists without its trusted status helper."
        verify_root_owned_file "${TRUSTED_MIGRATION_MARKER_HELPER}"
        marker_state=$(
            /usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}" \
                --marker "${LEDGER_MIGRATION_MARKER}" \
                --application-root "${APP_DIR}" status
        ) || die "Migration marker cannot be validated before target selection."
        read -r MIGRATION_MARKER_PREVIOUS_HEAD MIGRATION_MARKER_STATUS \
            marker_target < <(parse_marker_state "${marker_state}") \
            || die "Migration marker status cannot be parsed safely."
    fi
    if [[ "${MIGRATION_MARKER_STATUS}" == in_progress ]]; then
        [[ "${REQUESTED_HEAD}" == "${marker_target}" ]] \
            || die "Migration is incomplete; explicitly resume ${marker_target}."
        root_git -C "${TRUSTED_TREE}" cat-file -e \
            "${REQUESTED_HEAD}^{commit}" \
            || die "Migration resume target is absent from origin/main history."
        root_git -C "${TRUSTED_TREE}" merge-base --is-ancestor \
            "${REQUESTED_HEAD}" "${fetched_head}" \
            || die "Migration resume target is not an ancestor of origin/main."
        MIGRATION_RESUME_TARGET=1
        log "Authorized exact resume for migration target ${REQUESTED_HEAD:0:12}."
    else
        [[ "${fetched_head}" == "${REQUESTED_HEAD}" ]] \
            || die "Requested commit is not the current origin/main tip (${fetched_head})."
    fi
    root_git -C "${TRUSTED_TREE}" checkout --quiet --detach "${REQUESTED_HEAD}"
    TARGET_HEAD=$(root_git -C "${TRUSTED_TREE}" rev-parse HEAD)

    trusted_file requirements.txt >/dev/null
    trusted_file deploy/update_server.sh >/dev/null
    trusted_file deploy/bootstrap_server.sh >/dev/null
    trusted_file scripts/backup_runtime_databases.py >/dev/null
    validate_trusted_backup_stage_helper
    trusted_file scripts/manage_challenge_integrity_key.py >/dev/null
    trusted_file scripts/manage_challenge_migration_marker.py >/dev/null
    trusted_file scripts/migrate_challenge_ledgers.py >/dev/null
    trusted_file deploy/systemd/betboy-app.service >/dev/null
    validate_trusted_unit deploy/systemd/betboy-app.service
    local timer
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

verify_app_bytes() {
    local manifest="$1"
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${APP_DIR}" "${manifest}" <<'PY'
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

root_argument = Path(sys.argv[1])
if root_argument.is_symlink():
    raise SystemExit("application root must not be a symlink")
root = root_argument.absolute()
resolved_root = root.resolve(strict=True)
if resolved_root != root:
    raise SystemExit("application root must not traverse a symlink")
root = resolved_root
with open(sys.argv[2], encoding="utf-8") as handle:
    manifest = json.load(handle)

for relative, expected in manifest["files"].items():
    path = root.joinpath(*relative.split("/"))
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"tracked path is not a regular file: {relative}")
    resolved_path = path.resolve(strict=True)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SystemExit(f"tracked path escapes application root: {relative}") from exc
    if resolved_path != path.absolute():
        raise SystemExit(f"tracked path traverses a symlink: {relative}")
    actual_mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
    if actual_mode != expected["mode"]:
        raise SystemExit(f"tracked mode mismatch: {relative}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected["sha256"]:
        raise SystemExit(f"tracked byte mismatch: {relative}")

for relative in manifest["must_be_absent"]:
    path = root.joinpath(*relative.split("/"))
    if os.path.lexists(path):
        raise SystemExit(f"removed tracked path survived update: {relative}")
PY
}

verify_resume_app_bytes() {
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - \
        "${APP_DIR}" "${PREVIOUS_MANIFEST}" "${TARGET_MANIFEST}" <<'PY'
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

root_argument = Path(sys.argv[1])
if root_argument.is_symlink():
    raise SystemExit("application root must not be a symlink")
root = root_argument.absolute()
resolved_root = root.resolve(strict=True)
if resolved_root != root:
    raise SystemExit("application root must not traverse a symlink")
root = resolved_root
with open(sys.argv[2], encoding="utf-8") as handle:
    previous = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    target = json.load(handle)
paths = set(previous["files"]) | set(target["files"])
previous_absent = set(previous["must_be_absent"])
target_absent = set(target["must_be_absent"])
for relative in sorted(paths | previous_absent | target_absent):
    path = root.joinpath(*relative.split("/"))
    variants = [
        manifest["files"][relative]
        for manifest in (previous, target)
        if relative in manifest["files"]
    ]
    if not os.path.lexists(path):
        if relative not in previous_absent | target_absent:
            raise SystemExit(f"resume path is unexpectedly absent: {relative}")
        continue
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"resume path is not a regular file: {relative}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"resume path escapes application root: {relative}") from exc
    if resolved != path.absolute():
        raise SystemExit(f"resume path traverses a symlink: {relative}")
    actual = {
        "mode": "100755" if info.st_mode & stat.S_IXUSR else "100644",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if actual not in variants:
        raise SystemExit(f"resume path is neither predecessor nor target: {relative}")
PY
}

apply_trusted_payload() {
    local manifest="$1"
    local payload="$2"
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${APP_DIR}" "${manifest}" "${payload}" <<'PY'
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
payload_root = Path(sys.argv[3]).resolve(strict=True)
resolved_root = root.resolve(strict=True)
with manifest_path.open(encoding="utf-8") as handle:
    manifest = json.load(handle)


def ensure_parent(relative: str) -> Path:
    current = root
    parts = relative.split("/")
    for part in parts[:-1]:
        current = current / part
        if os.path.lexists(current):
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or current.is_symlink():
                raise SystemExit(f"tracked parent is not a real directory: {relative}")
        else:
            current.mkdir(mode=0o750)
    resolved = current.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SystemExit(f"tracked parent escapes app root: {relative}") from exc
    if resolved != current.absolute():
        raise SystemExit(f"tracked parent traverses a symlink: {relative}")
    return current


for relative in manifest.get("must_be_absent", []):
    destination = root.joinpath(*relative.split("/"))
    if os.path.lexists(destination):
        info = destination.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise SystemExit(f"refusing to remove non-file tracked path: {relative}")
        destination.unlink()

for relative, expected in manifest["files"].items():
    parent = ensure_parent(relative)
    source = payload_root.joinpath(*relative.split("/"))
    source_info = source.lstat()
    if not stat.S_ISREG(source_info.st_mode):
        raise SystemExit(f"trusted payload is not regular: {relative}")
    resolved_source = source.resolve(strict=True)
    try:
        resolved_source.relative_to(payload_root)
    except ValueError as exc:
        raise SystemExit(f"trusted payload escapes staging: {relative}") from exc
    destination = root.joinpath(*relative.split("/"))
    if os.path.lexists(destination) and not stat.S_ISREG(destination.lstat().st_mode):
        raise SystemExit(f"refusing to replace non-file tracked path: {relative}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, delete=False) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, handle, length=1024 * 1024)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o755 if expected["mode"] == "100755" else 0o644)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
PY
}

prepare_app_checkout() {
    local branch
    local fetched_head
    local ahead
    local behind
    local untracked_conflicts

    [[ -d "${APP_DIR}/.git" ]] || die "Not a Git checkout: ${APP_DIR}"
    [[ -x "${VENV_DIR}/bin/python" ]] || die "Missing venv Python: ${VENV_DIR}/bin/python"
    if [[ "${MIGRATION_RESUME_TARGET}" != 1 ]] \
        && ! git_betboy diff --cached --quiet --no-ext-diff --no-textconv \
            --ignore-submodules --; then
        die "Staged changes exist; preserve or resolve them first."
    fi
    branch=$(git_betboy symbolic-ref --quiet --short HEAD) \
        || die "Detached app HEAD is not deployable."
    [[ "${branch}" == main ]] || die "Expected app branch main, found ${branch}."

    # The network target is fixed here; no configured origin URL is used.
    git_betboy fetch --no-tags "${REPOSITORY_URL}" refs/heads/main
    fetched_head=$(git_betboy rev-parse FETCH_HEAD)
    [[ "${fetched_head}" == "${AUTHORIZED_MAIN_HEAD}" ]] \
        || die "Origin/main changed during deployment preflight."
    git_betboy cat-file -e "${TARGET_HEAD}^{commit}"
    PREVIOUS_HEAD=$(git_betboy rev-parse HEAD)
    [[ "${PREVIOUS_HEAD}" =~ ^[0-9a-f]{40}$ ]] \
        || die "App checkout returned an invalid HEAD."
    root_git -C "${TRUSTED_TREE}" cat-file -e "${PREVIOUS_HEAD}^{commit}" \
        || die "Deployed HEAD is not in the trusted origin/main history."
    if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
        [[ "${PREVIOUS_HEAD}" == "${TARGET_HEAD}" \
            || "${PREVIOUS_HEAD}" == "${MIGRATION_MARKER_PREVIOUS_HEAD}" ]] \
            || die "Migration resume checkout is neither predecessor nor target."
        root_git -C "${TRUSTED_TREE}" merge-base --is-ancestor \
            "${PREVIOUS_HEAD}" "${TARGET_HEAD}" \
            || die "Migration resume checkout is not in the authorized target history."
    else
        [[ "${fetched_head}" == "${TARGET_HEAD}" ]] \
            || die "App checkout fetched a different main commit."
        root_git -C "${TRUSTED_TREE}" merge-base --is-ancestor \
            "${PREVIOUS_HEAD}" "${TARGET_HEAD}" \
            || die "Deployed HEAD is not an ancestor of trusted origin/main."
    fi
    read -r ahead behind < <(
        root_git -C "${TRUSTED_TREE}" rev-list --left-right --count \
            "${PREVIOUS_HEAD}...${TARGET_HEAD}"
    )
    [[ "${ahead}" == 0 ]] || die "Deployed app branch is ahead of authorized main."
    PREVIOUS_CHALLENGE_WRITER_BLOB=$(root_git -C "${TRUSTED_TREE}" \
        rev-parse "${PREVIOUS_HEAD}:challenge_store.py")
    [[ "${PREVIOUS_CHALLENGE_WRITER_BLOB}" =~ ^[0-9a-f]{40}$ ]] \
        || die "Deployed challenge writer has an invalid Git blob."
    log "Authorized target ${TARGET_HEAD:0:12}; commits to apply: ${behind}."

    if [[ "${MIGRATION_RESUME_TARGET}" != 1 ]]; then
        untracked_conflicts=$(
            comm -12 \
                <(
                    {
                        git_betboy ls-files --others --exclude-standard
                        git_betboy ls-files --others --ignored --exclude-standard
                    } | sort -u
                ) \
                <(
                    root_git -C "${TRUSTED_TREE}" diff \
                        --name-only --diff-filter=ACMRT \
                        "${PREVIOUS_HEAD}" "${TARGET_HEAD}" | sort -u
                )
        )
        [[ -z "${untracked_conflicts}" ]] \
            || die "Untracked or ignored files would be overwritten:${untracked_conflicts//$'\n'/, }"
    fi

    create_trusted_manifests
    if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
        verify_resume_app_bytes
    else
        verify_app_bytes "${PREVIOUS_MANIFEST}"
    fi
}

prepare_dependencies() {
    local previous_blob
    local target_blob

    previous_blob=$(root_git -C "${TRUSTED_TREE}" \
        rev-parse "${PREVIOUS_HEAD}:requirements.txt")
    target_blob=$(root_git -C "${TRUSTED_TREE}" rev-parse "${TARGET_HEAD}:requirements.txt")
    if [[ "${previous_blob}" == "${target_blob}" ]]; then
        log "requirements.txt unchanged; skipping pip completely."
        return
    fi

    die "requirements.txt changed; use the separately reviewed venv-migration runbook."
}

verify_backup_archive() {
    local archive="$1"
    env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${archive}" <<'PY'
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
}

create_fresh_backup() {
    local backup_work
    local work_archive
    local partial_archive
    local stamp

    [[ ! -L /var/backups ]] || die "/var/backups must not be a symlink."
    [[ ! -L "${RECOVERY_BACKUP_DIR}" ]] \
        || die "Recovery backup directory must not be a symlink."
    install -d -m 0700 -o root -g root "${RECOVERY_BACKUP_DIR}"
    verify_root_owned_file "${TRUSTED_UPDATER}"
    [[ "$(stat -c '%U:%G' "${RECOVERY_BACKUP_DIR}")" == root:root ]] \
        || die "Recovery backup directory is not root-owned."
    (( (8#$(stat -c '%a' "${RECOVERY_BACKUP_DIR}") & 077) == 0 )) \
        || die "Recovery backup directory is accessible outside root."

    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    backup_work="${STAGE_DIR}/backup-work"
    install -d -m 0700 -o betboy -g betboy "${backup_work}"
    work_archive="${backup_work}/betboy-preupdate-${stamp}-${PREVIOUS_HEAD:0:12}.zip"
    FRESH_BACKUP="${RECOVERY_BACKUP_DIR}/${work_archive##*/}"
    partial_archive="${FRESH_BACKUP}.partial.$$"
    [[ ! -e "${work_archive}" && ! -e "${FRESH_BACKUP}" \
        && ! -e "${partial_archive}" ]] \
        || die "Refusing to overwrite an existing recovery backup."

    log "Creating a trusted backup after all database writers stopped."
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - \
        "${APP_DIR}" "${work_archive}" "${PREVIOUS_HEAD}" \
        "${LEDGER_HMAC_KEY}" "${LEDGER_MIGRATION_MARKER}" <<'PY'
import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

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
sources = []
for directory, dirnames, filenames in os.walk(root, followlinks=False):
    current = Path(directory)
    kept = []
    for name in dirnames:
        child = current / name
        if name in excluded:
            continue
        child_info = child.lstat()
        if child.is_symlink() or not stat.S_ISDIR(child_info.st_mode):
            raise SystemExit(f"database path traverses an unsafe directory: {child}")
        kept.append(name)
    dirnames[:] = kept
    for name in filenames:
        if not name.endswith((".db", ".sqlite", ".sqlite3")):
            continue
        source = current / name
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"database is not one regular file: {source}")
        try:
            source.resolve(strict=True).relative_to(root)
        except ValueError as exc:
            raise SystemExit(f"database escapes application root: {source}") from exc
        sources.append(source)
sources.sort(key=lambda path: path.relative_to(root).as_posix())
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
    for source in sources:
        relative = source.relative_to(root)
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        uri = source.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=30) as source_connection:
            with sqlite3.connect(destination) as destination_connection:
                source_connection.backup(destination_connection)
        with sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            result = connection.execute("PRAGMA quick_check").fetchall()
        if result != [("ok",)]:
            raise SystemExit(f"SQLite quick_check failed: {relative.as_posix()}")
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
PY
    # The staging parent cannot be renamed by betboy. Revoke its only access
    # before any root pathname operation on the newly-created archive.
    chown root:root "${backup_work}"
    chmod 0700 "${backup_work}"
    [[ -f "${work_archive}" && ! -L "${work_archive}" \
        && "$(stat -c '%U:%G' "${work_archive}")" == betboy:betboy \
        && "$(stat -c '%h' "${work_archive}")" == 1 ]] \
        || die "Backup helper did not produce one regular betboy-owned archive."
    chown -h root:root "${work_archive}"
    chmod 0600 -- "${work_archive}"
    verify_backup_archive "${work_archive}"
    env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I \
        "$(trusted_file scripts/backup_runtime_databases.py)" \
        --verify-only "${work_archive}" --recovery-mode
    install -o root -g root -m 0600 "${work_archive}" "${partial_archive}"
    verify_backup_archive "${partial_archive}"
    /usr/bin/python3 -I - "${partial_archive}" "${FRESH_BACKUP}" <<'PY'
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
    log "Fresh root-protected backup verified: ${FRESH_BACKUP}"
}

verify_clean_worktree() {
    local revision="$1"
    git_betboy diff --cached --quiet --no-ext-diff --no-textconv \
        --ignore-submodules "${revision}" -- \
        || return 1
}

purge_python_caches() {
    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${APP_DIR}" <<'PY'
import os
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
for directory, dirnames, _filenames in os.walk(root, topdown=True, followlinks=False):
    current = Path(directory)
    kept = []
    for name in dirnames:
        candidate = current / name
        if candidate.is_symlink():
            kept.append(name)
        elif name == "__pycache__":
            shutil.rmtree(candidate)
        else:
            kept.append(name)
    dirnames[:] = kept
PY
}

verify_untracked_policy() {
    local inventory="${STAGE_DIR}/untracked-paths.bin"
    local resume_tracked="${STAGE_DIR}/resume-tracked-paths.bin"
    git_betboy ls-files -z --others --exclude-standard >"${inventory}"
    git_betboy ls-files -z --others --ignored --exclude-standard >>"${inventory}"
    : >"${resume_tracked}"
    if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
        root_git -C "${TRUSTED_TREE}" ls-tree -rz --name-only \
            "${MIGRATION_MARKER_PREVIOUS_HEAD}" >>"${resume_tracked}"
        root_git -C "${TRUSTED_TREE}" ls-tree -rz --name-only \
            "${TARGET_HEAD}" >>"${resume_tracked}"
    fi
    chown root:betboy "${inventory}" "${resume_tracked}"
    chmod 0640 "${inventory}" "${resume_tracked}"

    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - \
        "${APP_DIR}" "${inventory}" "${resume_tracked}" <<'PY'
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1])
resolved_root = root.resolve(strict=True)
raw_paths = Path(sys.argv[2]).read_bytes().split(b"\0")
trusted_paths = {
    raw.decode("utf-8", "strict")
    for raw in Path(sys.argv[3]).read_bytes().split(b"\0")
    if raw
}
paths = sorted(
    {
        raw.decode("utf-8", "strict")
        for raw in raw_paths
        if raw and raw.decode("utf-8", "strict") not in trusted_paths
    }
)
dangerous_suffixes = (
    ".py", ".pyc", ".pyo", ".so", ".pth", ".egg-link", ".sh",
)


def is_allowed_data(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return bool(
        path in {"config.ini", ".env", ".streamlit/secrets.toml"}
        or path.startswith(("runtime_state/", "runtime_reports/"))
        or re.fullmatch(r"\.shadow_cache/[^/]+\.pkl", path)
        or re.fullmatch(r"scan_jobs/(?:.*/)?[^/]+\.json", path)
        or re.search(r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$", name)
        or re.fullmatch(r"logs/pipeline_[^/]+\.log", path)
        or re.fullmatch(r"reports/weekly_[^/]+\.html", path)
        or path == "tennis/data/calibration_watch_latest.json"
    )


for relative in paths:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or any(ord(c) < 32 for c in relative):
        raise SystemExit(f"unsafe untracked path: {relative!r}")
    if relative.lower().endswith(dangerous_suffixes):
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
    if not is_allowed_data(relative):
        raise SystemExit(f"untracked path is outside the runtime allowlist: {relative}")
PY
}

read_unit_enablement_state() {
    local state
    state=$(systemctl is-enabled "$1" 2>/dev/null || true)
    [[ "${state}" == enabled || "${state}" == disabled ]] \
        || die "Cannot classify unit enablement safely (${state:-error}): $1"
    printf '%s\n' "${state}"
}

read_unit_activity_state() {
    local state
    state=$(systemctl is-active "$1" 2>/dev/null || true)
    [[ "${state}" == active || "${state}" == inactive ]] \
        || die "Cannot classify unit activity safely (${state:-error}): $1"
    printf '%s\n' "${state}"
}

remember_unit_state() {
    local state
    local timer
    state=$(read_unit_activity_state betboy-app.service)
    if [[ "${state}" == active ]]; then
        APP_WAS_ACTIVE=1
    fi
    state=$(read_unit_enablement_state betboy-app.service)
    if [[ "${state}" == enabled ]]; then
        APP_WAS_ENABLED=1
    fi
    for timer in "${BETBOY_TIMERS[@]}"; do
        TIMER_WAS_ACTIVE["${timer}"]=0
        TIMER_WAS_ENABLED["${timer}"]=0
        state=$(read_unit_activity_state "${timer}")
        if [[ "${state}" == active ]]; then
            TIMER_WAS_ACTIVE["${timer}"]=1
        fi
        state=$(read_unit_enablement_state "${timer}")
        if [[ "${state}" == enabled ]]; then
            TIMER_WAS_ENABLED["${timer}"]=1
        fi
    done
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

    # Some worker services are intentionally static.  Ignore disable's aggregate
    # status and verify the fail-closed outcome for every unit below.
    systemctl disable betboy-app.service \
        "${BETBOY_TIMERS[@]}" "${BETBOY_WORKERS[@]}" >/dev/null 2>&1 || true
    durable_os_sync || failed=1
    for unit in betboy-app.service "${BETBOY_TIMERS[@]}"; do
        state=$(systemctl is-enabled "${unit}" 2>/dev/null || true)
        if [[ "${state}" != disabled ]]; then
            failed=1
            log "Runtime unit is not exactly disabled (${state:-error}): ${unit}"
        fi
    done
    for worker in "${BETBOY_WORKERS[@]}"; do
        state=$(systemctl is-enabled "${worker}" 2>/dev/null || true)
        if [[ "${state}" != static ]]; then
            failed=1
            log "Worker unit is not exactly static (${state:-error}): ${worker}"
        fi
    done
    return "${failed}"
}

disable_runtime_autostart() {
    persist_runtime_autostart_disabled \
        || die "Runtime autostart could not be disabled durably."
    log "Runtime autostart disabled durably until ledger migration completes."
}

snapshot_backup_principal_state() {
    local group_exists=0
    local user_exists=0

    getent group betboy-backup >/dev/null && group_exists=1
    getent passwd betboy-backup >/dev/null && user_exists=1
    [[ "${group_exists}" == "${user_exists}" ]] \
        || die "Only one of backup user/group exists before migration."
    BACKUP_GROUP_WAS_PRESENT="${group_exists}"
    BACKUP_USER_WAS_PRESENT="${user_exists}"
    if [[ "${user_exists}" == 1 ]]; then
        verify_backup_principal
    fi
    if [[ -e /var/lib/betboy-backup || -L /var/lib/betboy-backup ]]; then
        [[ "${user_exists}" == 1 ]] \
            || die "Backup home exists without its dedicated principal."
        verify_backup_home
        BACKUP_HOME_WAS_PRESENT=1
    fi
}

restore_backup_principal_state() {
    if [[ "${BACKUP_HOME_WAS_PRESENT}" == 0 \
        && ( -e /var/lib/betboy-backup || -L /var/lib/betboy-backup ) ]]; then
        [[ -d /var/lib/betboy-backup && ! -L /var/lib/betboy-backup ]] \
            || return 1
        rmdir -- /var/lib/betboy-backup || return 1
    fi
    if [[ "${BACKUP_USER_WAS_PRESENT}" == 0 ]] \
        && getent passwd betboy-backup >/dev/null; then
        userdel betboy-backup || return 1
    fi
    if [[ "${BACKUP_GROUP_WAS_PRESENT}" == 0 ]] \
        && getent group betboy-backup >/dev/null; then
        groupdel betboy-backup || return 1
    fi
}

verify_restored_backup_principal_state() {
    if [[ "${BACKUP_USER_WAS_PRESENT}" == 1 ]]; then
        ( verify_backup_principal ) || return 1
    elif getent passwd betboy-backup >/dev/null; then
        return 1
    fi
    if [[ "${BACKUP_GROUP_WAS_PRESENT}" == 1 ]]; then
        getent group betboy-backup >/dev/null || return 1
    elif getent group betboy-backup >/dev/null; then
        return 1
    fi
    if [[ "${BACKUP_HOME_WAS_PRESENT}" == 1 ]]; then
        ( verify_backup_home ) || return 1
    elif [[ -e /var/lib/betboy-backup || -L /var/lib/betboy-backup ]]; then
        return 1
    fi
}

snapshot_backup_source_metadata() {
    SOURCE_METADATA_MANIFEST="${ROLLBACK_ROOT}/backup-source-metadata.json"
    /usr/bin/python3 -I - \
        "${APP_DIR}" "${SOURCE_METADATA_MANIFEST}" <<'PY'
import json
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
manifest = Path(sys.argv[2])
excluded = {".codex_test_venv", ".git", ".pytest_cache", ".pytest_tmp"}
suffixes = (
    ".db", ".sqlite", ".sqlite3",
    ".db-wal", ".db-shm", ".db-journal",
    ".sqlite-wal", ".sqlite-shm", ".sqlite-journal",
    ".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal",
)
selected: set[Path] = set()

for current, directories, files in os.walk(root, topdown=True, followlinks=False):
    current_path = Path(current)
    kept = []
    for name in directories:
        child = current_path / name
        if name in excluded or name.startswith(".pytest_tmp"):
            continue
        child_info = child.lstat()
        if child.is_symlink() or not stat.S_ISDIR(child_info.st_mode):
            raise SystemExit(f"metadata path traverses an unsafe directory: {child}")
        kept.append(name)
    directories[:] = kept
    for name in files:
        if not name.casefold().endswith(suffixes):
            continue
        path = current_path / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"runtime database path is not one regular file: {path}")
        selected.add(path)
        parent = path.parent
        while parent == root or root in parent.parents:
            selected.add(parent)
            if parent == root:
                break
            parent = parent.parent

records = []
for path in sorted(selected, key=lambda item: (len(item.parts), str(item))):
    info = path.lstat()
    kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
    if kind == "file" and not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"metadata source changed type: {path}")
    records.append({
        "path": str(path),
        "kind": kind,
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": stat.S_IMODE(info.st_mode),
    })

temporary = manifest.with_suffix(".partial")
with temporary.open("w", encoding="utf-8") as handle:
    json.dump(records, handle, ensure_ascii=True, sort_keys=True)
    handle.flush()
    os.fsync(handle.fileno())
os.replace(temporary, manifest)
directory_fd = os.open(manifest.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY
}

apply_backup_source_metadata() {
    local mode="$1"
    [[ -n "${SOURCE_METADATA_MANIFEST}" \
        && -f "${SOURCE_METADATA_MANIFEST}" \
        && ! -L "${SOURCE_METADATA_MANIFEST}" ]] || return 0
    /usr/bin/python3 -I - \
        "${APP_DIR}" "${SOURCE_METADATA_MANIFEST}" "${mode}" <<'PY'
import json
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
manifest = Path(sys.argv[2])
mode = sys.argv[3]
records = json.loads(manifest.read_text(encoding="utf-8"))
if not isinstance(records, list):
    raise SystemExit("invalid source metadata manifest")

for record in sorted(records, key=lambda item: len(Path(item["path"]).parts), reverse=True):
    path = Path(record["path"])
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"metadata path escapes app root: {path}") from exc
    info = path.lstat()
    expected_kind = record["kind"]
    actual_kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
    if actual_kind != expected_kind or (
        actual_kind == "file" and not stat.S_ISREG(info.st_mode)
    ):
        raise SystemExit(f"metadata path changed type: {path}")
    if mode == "restore":
        os.chown(path, int(record["uid"]), int(record["gid"]), follow_symlinks=False)
        os.chmod(path, int(record["mode"]))
        info = path.lstat()
    if (
        info.st_uid != int(record["uid"])
        or info.st_gid != int(record["gid"])
        or stat.S_IMODE(info.st_mode) != int(record["mode"])
    ):
        raise SystemExit(f"metadata mismatch after {mode}: {path}")
PY
}

snapshot_backup_archives() {
    local candidate="${ROLLBACK_ROOT}/backup-archive-snapshot"
    [[ -z "${BACKUP_ARCHIVE_INVENTORY}" ]] \
        || die "Backup rollback snapshot was already published."
    /usr/bin/python3 -I \
        "$(trusted_file scripts/backup_runtime_databases.py)" \
        --snapshot-backup-tree /var/backups/betboy "${candidate}"
    [[ -d "${candidate}" && ! -L "${candidate}" \
        && -f "${candidate}/manifest.json" \
        && ! -L "${candidate}/manifest.json" ]] \
        || die "Backup rollback snapshot was not published safely."
    BACKUP_ARCHIVE_INVENTORY="${candidate}"
}

restore_backup_archives() {
    local helper="${TRUSTED_TREE}/scripts/backup_runtime_databases.py"
    [[ -z "${BACKUP_ARCHIVE_INVENTORY}" ]] && return 0
    [[ -d "${BACKUP_ARCHIVE_INVENTORY}" \
        && ! -L "${BACKUP_ARCHIVE_INVENTORY}" \
        && -f "${BACKUP_ARCHIVE_INVENTORY}/manifest.json" \
        && ! -L "${BACKUP_ARCHIVE_INVENTORY}/manifest.json" ]] \
        || return 1
    [[ -f "${helper}" && ! -L "${helper}" ]] || return 1
    /usr/bin/python3 -I \
        "${helper}" \
        --restore-backup-tree \
        "${BACKUP_ARCHIVE_INVENTORY}" /var/backups/betboy
}

verify_backup_service_migration() {
    local archive
    local exec_status
    local result

    verify_backup_principal
    verify_backup_home
    systemctl start betboy-backup.service
    result=$(systemctl show betboy-backup.service -p Result --value)
    exec_status=$(systemctl show betboy-backup.service -p ExecMainStatus --value)
    [[ "${result}" == success && "${exec_status}" == 0 ]] \
        || die "Hardened backup service did not complete successfully."
    [[ "$(systemctl is-active betboy-backup.service || true)" == inactive ]] \
        || die "Backup oneshot did not return to inactive state."

    archive=$(
        /usr/bin/python3 -I \
            "$(trusted_file scripts/backup_runtime_databases.py)" \
            --verify-backup-tree-update \
            "${BACKUP_ARCHIVE_INVENTORY}" /var/backups/betboy
    )
    BACKUP_PROBE_ARCHIVE="${archive}"
    [[ -f "${archive}" && ! -L "${archive}" \
        && "$(stat -c '%U:%G' "${archive}")" \
            == betboy-backup:betboy-backup \
        && "$(stat -c '%a' "${archive}")" == 600 \
        && "$(stat -c '%h' "${archive}")" == 1 ]] \
        || die "Backup service archive failed owner, mode or link policy."
    runuser -u betboy-backup -- \
        /usr/bin/python3 -I "${TRUSTED_BACKUP_HELPER}" \
        --verify-only "${archive}"
    runuser -u betboy -- /usr/bin/test ! -r "${archive}" \
        || die "Application account can read the protected backup archive."
    runuser -u betboy -- /usr/bin/test ! -w "${archive}" \
        || die "Application account can write the protected backup archive."
    runuser -u betboy -- /usr/bin/test ! -w /var/backups/betboy \
        || die "Application account can write the protected backup directory."
    runuser -u betboy-backup -- \
        /usr/bin/test ! -r /etc/betboy/betboy.env \
        || die "Backup account can read the runtime environment secrets."
}

prepare_backup_storage_and_sources() {
    local database
    local owner
    local parent
    local unsafe_path

    [[ -d /var/backups && ! -L /var/backups ]] \
        || die "/var/backups must be a real directory."
    [[ ! -L /var/backups/betboy ]] \
        || die "Backup destination must not be a symlink."
    install -d -m 0700 -o betboy-backup -g betboy-backup \
        /var/backups/betboy

    unsafe_path=$(find -P "${APP_DIR}" -xdev \
        \( -path "${APP_DIR}/.git" \
           -o -path "${APP_DIR}/.codex_test_venv" \
           -o -path "${APP_DIR}/.pytest_cache" \
           -o -path "${APP_DIR}/.pytest_tmp" \) -prune -o \
        -type l -print -quit)
    [[ -z "${unsafe_path}" ]] \
        || die "Backup source path must not contain a symlink: ${unsafe_path}"

    while IFS= read -r -d '' database; do
        [[ "$(stat -c '%h' "${database}")" == 1 ]] \
            || die "Runtime database has multiple hard links: ${database}"
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

verify_backup_source_dac() {
    local database
    local parent
    local -a backup_identity=(
        runuser -u betboy-backup -g betboy-backup -G betboy --
    )

    while IFS= read -r -d '' database; do
        "${backup_identity[@]}" /usr/bin/test ! -w "${database}" \
            || die "Backup service identity can write live SQLite state: ${database}"
        parent=$(dirname "${database}")
        while [[ "${parent}" == "${APP_DIR}" \
            || "${parent}" == "${APP_DIR}/"* ]]; do
            "${backup_identity[@]}" /usr/bin/test ! -w "${parent}" \
                || die "Backup service identity can write a live parent: ${parent}"
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
    "${backup_identity[@]}" /usr/bin/test ! -w "${LEDGER_HMAC_KEY}" \
        || die "Backup service identity can write the ledger integrity key."
    if [[ -e "${LEDGER_MIGRATION_MARKER}" ]]; then
        "${backup_identity[@]}" /usr/bin/test \
            ! -w "${LEDGER_MIGRATION_MARKER}" \
            || die "Backup service identity can write the migration marker."
    fi
    "${backup_identity[@]}" /usr/bin/test ! -w /etc/betboy/betboy.env \
        || die "Backup service identity can write runtime environment secrets."
    "${backup_identity[@]}" /usr/bin/test -w /var/backups/betboy \
        || die "Backup service identity cannot write the backup destination."
}

write_trusted_caddy_config() {
    local destination="$1"
    cat >"${destination}" <<EOF
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
}

verify_public_proxy() {
    local body="${STAGE_DIR}/public-health-body"
    local headers="${STAGE_DIR}/public-health-headers"

    curl --fail --silent --show-error \
        --retry 12 --retry-all-errors --retry-delay 2 \
        --connect-timeout 3 --max-time 8 \
        --resolve "${PUBLIC_HOST}:443:127.0.0.1" \
        --dump-header "${headers}" --output "${body}" \
        "https://${PUBLIC_HOST}/_stcore/health"
    grep -qx 'ok' "${body}" \
        || die "Public TLS health response is not exact."
    grep -Eiq \
        "^content-security-policy:[[:space:]]*frame-ancestors 'self'[[:space:]]*$" \
        "${headers}" \
        || die "Public TLS response lacks the exact frame-ancestors policy."
    grep -Eiq \
        '^x-frame-options:[[:space:]]*SAMEORIGIN[[:space:]]*$' \
        "${headers}" \
        || die "Public TLS response lacks SAMEORIGIN frame protection."
}

snapshot_root_files() {
    local backup_parent_mode
    local timer
    ROLLBACK_ROOT="${STAGE_DIR}/root-rollback"
    install -d -m 0700 -o root -g root "${ROLLBACK_ROOT}"
    install -d -m 0700 -o root -g root "${ROLLBACK_ROOT}/systemd"
    verify_root_owned_file "${TRUSTED_UPDATER}"
    verify_root_owned_file "${TRUSTED_BOOTSTRAP}"
    cp -a "${TRUSTED_UPDATER}" "${ROLLBACK_ROOT}/betboy-update"
    cp -a "${TRUSTED_BOOTSTRAP}" "${ROLLBACK_ROOT}/betboy-bootstrap"
    if [[ -e "${TRUSTED_BACKUP_HELPER}" ]]; then
        verify_root_owned_file "${TRUSTED_BACKUP_HELPER}"
        cp -a "${TRUSTED_BACKUP_HELPER}" "${ROLLBACK_ROOT}/backup-helper"
        BACKUP_HELPER_WAS_PRESENT=1
    fi
    if [[ -e "${TRUSTED_BACKUP_STAGE_HELPER}" ]]; then
        verify_root_owned_file "${TRUSTED_BACKUP_STAGE_HELPER}"
        cp -a "${TRUSTED_BACKUP_STAGE_HELPER}" \
            "${ROLLBACK_ROOT}/backup-stage-helper"
        BACKUP_STAGE_HELPER_WAS_PRESENT=1
    fi
    if [[ -e "${TRUSTED_MIGRATION_MARKER_HELPER}" ]]; then
        verify_root_owned_file "${TRUSTED_MIGRATION_MARKER_HELPER}"
        cp -a "${TRUSTED_MIGRATION_MARKER_HELPER}" \
            "${ROLLBACK_ROOT}/migration-marker-helper"
        MIGRATION_MARKER_HELPER_WAS_PRESENT=1
    fi
    verify_root_owned_file /etc/caddy/Caddyfile
    systemctl is-active --quiet caddy \
        || die "Caddy must be active before an in-place update."
    caddy validate --config /etc/caddy/Caddyfile
    cp -a /etc/caddy/Caddyfile "${ROLLBACK_ROOT}/Caddyfile"
    CADDY_UID=$(stat -c '%u' /etc/caddy/Caddyfile)
    CADDY_GID=$(stat -c '%g' /etc/caddy/Caddyfile)
    CADDY_MODE=$(stat -c '%a' /etc/caddy/Caddyfile)
    [[ -d /var/backups && ! -L /var/backups \
        && "$(stat -c '%u' /var/backups)" == 0 ]] \
        || die "Backup parent must be a real root-owned directory."
    backup_parent_mode=$(stat -c '%a' /var/backups)
    (( (8#${backup_parent_mode} & 022) == 0 )) \
        || die "Backup parent is writable by a non-root account."
    [[ -d /var/backups/betboy && ! -L /var/backups/betboy ]] \
        || die "Existing backup destination is not a real directory."
    [[ "$(stat -c '%d' /var/backups/betboy)" \
        == "$(stat -c '%d' /var/backups)" ]] \
        || die "Backup destination must share its parent filesystem."
    ! mountpoint -q /var/backups/betboy \
        || die "Backup destination must not be a separate mountpoint."
    BACKUP_DIR_WAS_PRESENT=1
    BACKUP_DIR_UID=$(stat -c '%u' /var/backups/betboy)
    BACKUP_DIR_GID=$(stat -c '%g' /var/backups/betboy)
    BACKUP_DIR_MODE=$(stat -c '%a' /var/backups/betboy)
    snapshot_backup_principal_state
    verify_installed_previous_unit betboy-app.service
    cp -a /etc/systemd/system/betboy-app.service "${ROLLBACK_ROOT}/systemd/"
    for timer in "${BETBOY_TIMERS[@]}"; do
        verify_installed_previous_unit "${timer}"
        verify_installed_previous_unit "${timer%.timer}.service"
        cp -a "/etc/systemd/system/${timer}" "${ROLLBACK_ROOT}/systemd/"
        cp -a "/etc/systemd/system/${timer%.timer}.service" \
            "${ROLLBACK_ROOT}/systemd/"
    done
}

install_trusted_root_files() {
    local timer
    local caddy_candidate="${STAGE_DIR}/Caddyfile"
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
    write_trusted_caddy_config "${caddy_candidate}"
    chown root:root "${caddy_candidate}"
    chmod 0600 "${caddy_candidate}"
    caddy validate --config "${caddy_candidate}"
    install_root_file_atomic \
        "${caddy_candidate}" /etc/caddy/Caddyfile 0644 root root
    caddy reload --config /etc/caddy/Caddyfile
    systemctl daemon-reload
    verify_installed_unit betboy-app.service
    for timer in "${BETBOY_TIMERS[@]}"; do
        verify_installed_unit "${timer}"
        verify_installed_unit "${timer%.timer}.service"
    done
}

restore_root_files() {
    local unit
    install_root_file_atomic \
        "${ROLLBACK_ROOT}/betboy-update" "${TRUSTED_UPDATER}" \
        0755 root root || return 1
    install_root_file_atomic \
        "${ROLLBACK_ROOT}/betboy-bootstrap" "${TRUSTED_BOOTSTRAP}" \
        0755 root root || return 1
    for unit in "${ROLLBACK_ROOT}"/systemd/*; do
        install_root_file_atomic \
            "${unit}" "/etc/systemd/system/${unit##*/}" \
            0644 root root || return 1
    done
    if [[ "${BACKUP_HELPER_WAS_PRESENT}" == 1 ]]; then
        install_root_file_atomic \
            "${ROLLBACK_ROOT}/backup-helper" "${TRUSTED_BACKUP_HELPER}" \
            0755 root root || return 1
    else
        rm -f -- "${TRUSTED_BACKUP_HELPER}" || return 1
    fi
    if [[ "${BACKUP_STAGE_HELPER_WAS_PRESENT}" == 1 ]]; then
        install_root_file_atomic \
            "${ROLLBACK_ROOT}/backup-stage-helper" \
            "${TRUSTED_BACKUP_STAGE_HELPER}" 0755 root root || return 1
    else
        rm -f -- "${TRUSTED_BACKUP_STAGE_HELPER}" || return 1
    fi
    if [[ "${MIGRATION_MARKER_HELPER_WAS_PRESENT}" == 1 ]]; then
        install_root_file_atomic \
            "${ROLLBACK_ROOT}/migration-marker-helper" \
            "${TRUSTED_MIGRATION_MARKER_HELPER}" 0755 root root || return 1
    else
        rm -f -- "${TRUSTED_MIGRATION_MARKER_HELPER}" || return 1
    fi
    install_root_file_atomic \
        "${ROLLBACK_ROOT}/Caddyfile" /etc/caddy/Caddyfile \
        "${CADDY_MODE}" root root || return 1
    caddy validate --config /etc/caddy/Caddyfile || return 1
    caddy reload --config /etc/caddy/Caddyfile || return 1
    restore_backup_archives || return 1
    apply_backup_source_metadata restore || return 1
    if [[ "${BACKUP_DIR_WAS_PRESENT}" == 1 ]]; then
        chown "${BACKUP_DIR_UID}:${BACKUP_DIR_GID}" /var/backups/betboy \
            || return 1
        chmod "${BACKUP_DIR_MODE}" /var/backups/betboy || return 1
    fi
    restore_backup_principal_state || return 1
    systemctl daemon-reload || return 1
}

verify_restored_root_files() {
    local timer
    local expected
    cmp -s "${ROLLBACK_ROOT}/betboy-update" "${TRUSTED_UPDATER}" || return 1
    cmp -s "${ROLLBACK_ROOT}/betboy-bootstrap" "${TRUSTED_BOOTSTRAP}" || return 1
    cmp -s "${ROLLBACK_ROOT}/systemd/betboy-app.service" \
        /etc/systemd/system/betboy-app.service || return 1
    expected=$(sha256sum -- "${ROLLBACK_ROOT}/systemd/betboy-app.service" \
        | awk '{print $1}') || return 1
    check_installed_unit betboy-app.service "${expected}" || return 1
    if [[ "${BACKUP_HELPER_WAS_PRESENT}" == 1 ]]; then
        cmp -s "${ROLLBACK_ROOT}/backup-helper" "${TRUSTED_BACKUP_HELPER}" \
            || return 1
    elif [[ -e "${TRUSTED_BACKUP_HELPER}" ]]; then
        return 1
    fi
    if [[ "${BACKUP_STAGE_HELPER_WAS_PRESENT}" == 1 ]]; then
        cmp -s "${ROLLBACK_ROOT}/backup-stage-helper" \
            "${TRUSTED_BACKUP_STAGE_HELPER}" || return 1
    elif [[ -e "${TRUSTED_BACKUP_STAGE_HELPER}" ]]; then
        return 1
    fi
    if [[ "${MIGRATION_MARKER_HELPER_WAS_PRESENT}" == 1 ]]; then
        cmp -s "${ROLLBACK_ROOT}/migration-marker-helper" \
            "${TRUSTED_MIGRATION_MARKER_HELPER}" || return 1
    elif [[ -e "${TRUSTED_MIGRATION_MARKER_HELPER}" ]]; then
        return 1
    fi
    cmp -s "${ROLLBACK_ROOT}/Caddyfile" /etc/caddy/Caddyfile || return 1
    [[ "$(stat -c '%u' /etc/caddy/Caddyfile)" == "${CADDY_UID}" \
        && "$(stat -c '%g' /etc/caddy/Caddyfile)" == "${CADDY_GID}" \
        && "$(stat -c '%a' /etc/caddy/Caddyfile)" == "${CADDY_MODE}" ]] \
        || return 1
    [[ "$(stat -c '%u' /var/backups/betboy)" == "${BACKUP_DIR_UID}" \
        && "$(stat -c '%g' /var/backups/betboy)" == "${BACKUP_DIR_GID}" \
        && "$(stat -c '%a' /var/backups/betboy)" == "${BACKUP_DIR_MODE}" ]] \
        || return 1
    apply_backup_source_metadata verify || return 1
    verify_restored_backup_principal_state || return 1
    if [[ -n "${BACKUP_PROBE_ARCHIVE}" \
        && ( -e "${BACKUP_PROBE_ARCHIVE}" \
             || -L "${BACKUP_PROBE_ARCHIVE}" ) ]]; then
        return 1
    fi
    for timer in "${BETBOY_TIMERS[@]}"; do
        cmp -s "${ROLLBACK_ROOT}/systemd/${timer}" \
            "/etc/systemd/system/${timer}" || return 1
        cmp -s "${ROLLBACK_ROOT}/systemd/${timer%.timer}.service" \
            "/etc/systemd/system/${timer%.timer}.service" || return 1
        expected=$(sha256sum -- "${ROLLBACK_ROOT}/systemd/${timer}" \
            | awk '{print $1}') || return 1
        check_installed_unit "${timer}" "${expected}" || return 1
        expected=$(sha256sum -- \
            "${ROLLBACK_ROOT}/systemd/${timer%.timer}.service" \
            | awk '{print $1}') || return 1
        check_installed_unit "${timer%.timer}.service" "${expected}" \
            || return 1
    done
}

stop_all_runtime_units() {
    local failed=0
    local unit
    systemctl stop "${BETBOY_TIMERS[@]}" || failed=1
    systemctl stop "${BETBOY_WORKERS[@]}" || failed=1
    systemctl stop betboy-app.service || failed=1
    for unit in betboy-app.service "${BETBOY_TIMERS[@]}" "${BETBOY_WORKERS[@]}"; do
        if systemctl is-active --quiet "${unit}"; then
            failed=1
            log "Recovery could not stop ${unit}."
        fi
    done
    if ! check_no_betboy_processes; then
        failed=1
        log "Unexpected betboy-owned process remains outside stopped units."
    fi
    return "${failed}"
}

restore_unit_state() {
    local expected
    local state
    local timer
    local failed=0

    # Configure enablement while everything is still stopped.
    if [[ "${APP_WAS_ENABLED}" == 1 ]]; then
        systemctl enable betboy-app.service >/dev/null 2>&1 || failed=1
    else
        systemctl disable betboy-app.service >/dev/null 2>&1 || failed=1
    fi
    systemctl stop betboy-app.service || failed=1
    for timer in "${BETBOY_TIMERS[@]}"; do
        if [[ "${TIMER_WAS_ENABLED[${timer}]:-0}" == 1 ]]; then
            systemctl enable "${timer}" >/dev/null 2>&1 || failed=1
        else
            systemctl disable "${timer}" >/dev/null 2>&1 || failed=1
        fi
        systemctl stop "${timer}" || failed=1
    done
    /usr/bin/python3 -I - <<'PY'
import os

os.sync()
PY
    [[ "${failed}" == 0 ]] || return 1

    if [[ "${APP_WAS_ACTIVE}" == 1 ]]; then
        systemctl start betboy-app.service || return 1
        curl --fail --silent --show-error \
            --retry 12 --retry-all-errors --retry-delay 2 \
            --connect-timeout 3 --max-time 5 \
            "${HEALTH_URL}" | grep -qx 'ok' || return 1
    else
        systemctl stop betboy-app.service || return 1
    fi
    state=$(systemctl is-enabled betboy-app.service 2>/dev/null || true)
    expected=disabled
    [[ "${APP_WAS_ENABLED}" == 1 ]] && expected=enabled
    [[ "${state}" == "${expected}" ]] || return 1
    for timer in "${BETBOY_TIMERS[@]}"; do
        if [[ "${TIMER_WAS_ACTIVE[${timer}]:-0}" == 1 ]]; then
            systemctl start "${timer}" || return 1
        else
            systemctl stop "${timer}" || return 1
        fi
    done
    state=$(systemctl is-active betboy-app.service 2>/dev/null || true)
    expected=inactive
    [[ "${APP_WAS_ACTIVE}" == 1 ]] && expected=active
    [[ "${state}" == "${expected}" ]] || return 1
    for timer in "${BETBOY_TIMERS[@]}"; do
        state=$(systemctl is-enabled "${timer}" 2>/dev/null || true)
        expected=disabled
        [[ "${TIMER_WAS_ENABLED[${timer}]:-0}" == 1 ]] && expected=enabled
        [[ "${state}" == "${expected}" ]] || return 1
        state=$(systemctl is-active "${timer}" 2>/dev/null || true)
        expected=inactive
        [[ "${TIMER_WAS_ACTIVE[${timer}]:-0}" == 1 ]] && expected=active
        [[ "${state}" == "${expected}" ]] || return 1
    done
}

durable_migration_requires_fail_closed() {
    local helper_info
    local marker_state

    [[ -e "${LEDGER_MIGRATION_MARKER}" \
        || -L "${LEDGER_MIGRATION_MARKER}" ]] || return 1
    [[ -f "${TRUSTED_MIGRATION_MARKER_HELPER}" \
        && ! -L "${TRUSTED_MIGRATION_MARKER_HELPER}" ]] || return 0
    helper_info=$(stat -c '%U:%a' "${TRUSTED_MIGRATION_MARKER_HELPER}" 2>/dev/null) \
        || return 0
    [[ "${helper_info%%:*}" == root \
        && $((8#${helper_info#*:} & 022)) == 0 ]] || return 0
    marker_state=$(
        /usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}" \
            --marker "${LEDGER_MIGRATION_MARKER}" \
            --application-root "${APP_DIR}" status 2>/dev/null
    ) || return 0
    [[ "${marker_state}" == *'"status":"in_progress"'* ]] && return 0
    [[ "${marker_state}" == *'"status":"complete"'* ]] && return 1
    return 0
}

recover_update() {
    local status="$1"
    local current_head=""
    local fail_closed_required=0
    local recovery_ok=1

    if [[ "${status}" == 0 && "${UPDATE_COMPLETE}" == 1 ]]; then
        safe_remove_stage
        return
    fi
    if [[ "${UPDATE_STARTED}" != 1 ]]; then
        safe_remove_stage
        log "Preflight failed; app and timers were not stopped."
        return
    fi

    trap - EXIT
    set +e
    [[ "${status}" != 0 ]] || status=1
    if [[ "${DATABASE_MIGRATION_STARTED}" == 1 \
        || "${NEW_APP_STARTED}" == 1 ]] \
        || durable_migration_requires_fail_closed; then
        fail_closed_required=1
    fi
    log "Update failed; forcing every app, timer and worker unit down."
    stop_all_runtime_units || recovery_ok=0
    if [[ "${fail_closed_required}" == 1 ]]; then
        persist_runtime_autostart_disabled || recovery_ok=0
        log "FAIL-CLOSED: the target migration/app may have touched databases."
        if [[ "${recovery_ok}" == 1 ]]; then
            log "All runtime units are stopped and durably disabled."
        else
            log "At least one runtime unit could not be confirmed stopped and disabled."
        fi
        log "Inspect/restore ${FRESH_BACKUP:-no-backup-created} before recovery."
        log "Preserved recovery staging: ${STAGE_DIR}"
    else
        current_head=$(git_betboy rev-parse HEAD 2>/dev/null) || recovery_ok=0
        if [[ "${recovery_ok}" == 1 ]]; then
            apply_trusted_payload "${PREVIOUS_MANIFEST}" "${PREVIOUS_PAYLOAD}" \
                || recovery_ok=0
        fi
        if [[ "${recovery_ok}" == 1 && "${current_head}" == "${TARGET_HEAD}" ]]; then
            git_betboy update-ref refs/heads/main \
                "${PREVIOUS_HEAD}" "${TARGET_HEAD}" || recovery_ok=0
        elif [[ "${recovery_ok}" == 1 && "${current_head}" != "${PREVIOUS_HEAD}" ]]; then
            recovery_ok=0
        fi
        if [[ "${recovery_ok}" == 1 ]]; then
            git_betboy read-tree "${PREVIOUS_HEAD}" || recovery_ok=0
        fi
        if [[ "${recovery_ok}" == 1 ]]; then
            [[ "$(git_betboy rev-parse HEAD 2>/dev/null)" == "${PREVIOUS_HEAD}" ]] \
                || recovery_ok=0
            verify_clean_worktree "${PREVIOUS_HEAD}" || recovery_ok=0
            verify_app_bytes "${PREVIOUS_MANIFEST}" || recovery_ok=0
        fi
        if [[ "${recovery_ok}" == 1 && -n "${ROLLBACK_ROOT}" \
            && -d "${ROLLBACK_ROOT}" ]]; then
            restore_root_files || recovery_ok=0
            verify_restored_root_files || recovery_ok=0
        else
            recovery_ok=0
        fi
        if [[ "${recovery_ok}" == 1 ]]; then
            restore_unit_state || recovery_ok=0
        fi
        if [[ "${recovery_ok}" == 1 ]]; then
            log "Previous code, root files and remembered unit state restored."
            safe_remove_stage
        else
            stop_all_runtime_units
            persist_runtime_autostart_disabled
            log "FAIL-CLOSED: rollback verification failed; all runtime units remain stopped."
            log "Preserved recovery staging: ${STAGE_DIR}"
            log "Recovery backup: ${FRESH_BACKUP:-not-created}"
        fi
    fi
    exit "${status}"
}

trap 'recover_update "$?"' EXIT

wait_for_workers() {
    local deadline=$((SECONDS + WORKER_WAIT_SECONDS))
    local worker
    local running

    while true; do
        running=0
        for worker in "${BETBOY_WORKERS[@]}"; do
            if systemctl is-active --quiet "${worker}"; then
                running=1
                log "A worker won the preflight race; waiting for ${worker}."
            fi
        done
        [[ "${running}" == 0 ]] && return 0
        (( SECONDS < deadline )) || return 1
        sleep 2
    done
}

prepare_challenge_migration_boundary() {
    local marker_previous
    local marker_state
    local marker_status
    local marker_target

    install -d -m 0755 -o root -g root /usr/local/libexec
    install_root_file_atomic \
        "$(trusted_file scripts/manage_challenge_migration_marker.py)" \
        "${TRUSTED_MIGRATION_MARKER_HELPER}" 0755 root root
    verify_root_owned_file "${TRUSTED_MIGRATION_MARKER_HELPER}"
    marker_state=$(
        /usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}" \
            --marker "${LEDGER_MIGRATION_MARKER}" \
            --application-root "${APP_DIR}" \
            --group betboy \
            prepare \
            --previous-head "${PREVIOUS_HEAD}" \
            --previous-writer-blob "${PREVIOUS_CHALLENGE_WRITER_BLOB}" \
            --target-head "${TARGET_HEAD}"
    )
    read -r marker_previous marker_status marker_target \
        < <(parse_marker_state "${marker_state}") \
        || die "Prepared migration marker status cannot be parsed safely."
    if [[ "${marker_status}" == in_progress ]]; then
        [[ "${marker_target}" == "${TARGET_HEAD}" ]] \
            || die "Prepared migration marker targets another rollout."
        [[ "${PREVIOUS_HEAD}" == "${marker_previous}" \
            || "${PREVIOUS_HEAD}" == "${marker_target}" ]] \
            || die "Prepared migration marker does not match the deployed checkout."
        MIGRATION_MARKER_PREVIOUS_HEAD="${marker_previous}"
        MIGRATION_MARKER_STATUS="${marker_status}"
        DATABASE_MIGRATION_STARTED=1
        log "Durable fail-closed migration boundary published for ${marker_target:0:12}."
    elif [[ "${marker_status}" == complete ]]; then
        MIGRATION_MARKER_PREVIOUS_HEAD="${marker_previous}"
        MIGRATION_MARKER_STATUS="${marker_status}"
        log "Existing completed migration boundary verified."
    else
        die "Prepared migration marker returned an unexpected state."
    fi
}

migrate_challenge_integrity_offline() {
    local helper
    local marker_state
    local _marker_previous
    local _marker_status
    local _marker_target
    local receipt="${STAGE_DIR}/challenge-ledger-migration-receipt.json"

    # ChallengeLedger construction and verify-only reconciliation are allowed to
    # persist authenticated state. From this point an automatic code rollback is
    # therefore never safe, even when the durable marker was already complete.
    DATABASE_MIGRATION_STARTED=1
    [[ -x "${VENV_DIR}/bin/python" ]] \
        || die "Application Python is unavailable for offline ledger migration."
    helper=$(target_payload_file scripts/migrate_challenge_ledgers.py)
    verify_root_owned_file "${TRUSTED_MIGRATION_MARKER_HELPER}"
    [[ ! -e "${receipt}" && ! -L "${receipt}" ]] \
        || die "Challenge migration receipt path already exists."

    if [[ "${MIGRATION_MARKER_STATUS}" == in_progress ]]; then
        log "Migrating legacy v0 challenge ledgers under the root policy marker."
        as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
            "${VENV_DIR}/bin/python" -I "${helper}" \
            --root "${APP_DIR}" \
            --integrity-key "${LEDGER_HMAC_KEY}" \
            --offline-confirmed \
            --migration-policy-file "${LEDGER_MIGRATION_MARKER}" \
            >"${receipt}"
        /usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}" \
            --marker "${LEDGER_MIGRATION_MARKER}" \
            --application-root "${APP_DIR}" \
            --group betboy \
            complete \
            --target-head "${TARGET_HEAD}" \
            --receipt "${receipt}" >/dev/null
    elif [[ "${MIGRATION_MARKER_STATUS}" == complete ]]; then
        log "Migration marker is complete; verifying current HMAC ledgers only."
        as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
            "${VENV_DIR}/bin/python" -I "${helper}" \
            --root "${APP_DIR}" \
            --integrity-key "${LEDGER_HMAC_KEY}" \
            --offline-confirmed \
            --verify-only >"${receipt}"
    else
        die "Challenge migration marker returned an unexpected state."
    fi
    marker_state=$(
        /usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}" \
            --marker "${LEDGER_MIGRATION_MARKER}" \
            --application-root "${APP_DIR}" status
    )
    read -r _marker_previous _marker_status _marker_target \
        < <(parse_marker_state "${marker_state}") \
        || die "Completed migration marker status cannot be parsed safely."
    [[ "${_marker_status}" == complete ]] \
        || die "Challenge migration marker was not completed."
    MIGRATION_MARKER_STATUS=complete
}

verify_runtime() {
    local state
    local timer
    local worker
    systemctl is-active --quiet betboy-app.service
    state=$(systemctl is-enabled betboy-app.service 2>/dev/null || true)
    [[ "${state}" == enabled ]]
    for timer in "${BETBOY_TIMERS[@]}"; do
        systemctl is-active --quiet "${timer}"
        state=$(systemctl is-enabled "${timer}" 2>/dev/null || true)
        [[ "${state}" == enabled ]]
    done
    for worker in "${BETBOY_WORKERS[@]}"; do
        state=$(systemctl is-enabled "${worker}" 2>/dev/null || true)
        [[ "${state}" == static ]]
    done
    curl --fail --silent --show-error \
        --retry 12 --retry-all-errors --retry-delay 2 \
        --connect-timeout 3 --max-time 5 \
        "${HEALTH_URL}" | grep -qx 'ok'
    verify_public_proxy
}

preflight() {
    local required_command
    local worker
    local available_kib
    local backup_apparent_kib
    local backup_available_kib
    local backup_required_kib
    local database_apparent_kib
    local rollback_available_kib
    local rollback_required_kib
    local shared_required_kib

    verify_invocation "$@"
    for required_command in \
        git runuser systemctl systemd-analyze install curl awk sort comm \
        bash df du grep sleep readlink stat date mktemp cp mv rm cmp chown chmod \
        chgrp sha256sum find pgrep getent groupadd groupdel useradd userdel \
        passwd id dirname rmdir caddy flock mountpoint; do
        command -v "${required_command}" >/dev/null \
            || die "Missing command: ${required_command}"
    done
    [[ -x /usr/bin/python3 ]] || die "Missing trusted /usr/bin/python3."
    acquire_deploy_lock
    [[ ! -L /opt/betboy && ! -L "${APP_DIR}" ]] \
        || die "Application path must not traverse a symlink."
    getent passwd betboy >/dev/null \
        || die "The betboy service account is missing."
    verify_no_unit_dropin_paths
    prepare_trusted_tree
    prepare_app_checkout
    available_kib=$(df -Pk "${APP_DIR}" | awk 'NR == 2 {print $4}')
    [[ "${available_kib}" =~ ^[0-9]+$ ]] || die "Cannot determine free disk space."
    (( available_kib >= 2097152 )) || die "Less than 2 GiB free for safe staging."
    backup_apparent_kib=$(du -skx --apparent-size /var/backups/betboy \
        | awk 'NR == 1 {print $1}')
    database_apparent_kib=$(
        find -P "${APP_DIR}" -xdev -type f \
            \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \
               -o -name '*.db-wal' -o -name '*.db-shm' \
               -o -name '*.sqlite-wal' -o -name '*.sqlite-shm' \
               -o -name '*.sqlite3-wal' -o -name '*.sqlite3-shm' \
               -o -name '*.db-journal' -o -name '*.sqlite-journal' \
               -o -name '*.sqlite3-journal' \) \
            -printf '%s\n' \
            | awk '{total += $1} END {print int((total + 1023) / 1024)}'
    )
    rollback_available_kib=$(df -Pk /var/tmp | awk 'NR == 2 {print $4}')
    backup_available_kib=$(df -Pk /var/backups \
        | awk 'NR == 2 {print $4}')
    [[ "${backup_apparent_kib}" =~ ^[0-9]+$ \
        && "${database_apparent_kib}" =~ ^[0-9]+$ \
        && "${rollback_available_kib}" =~ ^[0-9]+$ \
        && "${backup_available_kib}" =~ ^[0-9]+$ ]] \
        || die "Cannot determine rollback snapshot capacity."
    rollback_required_kib=$((
        backup_apparent_kib + database_apparent_kib * 3 + 524288
    ))
    backup_required_kib=$((
        backup_apparent_kib + database_apparent_kib * 2 + 524288
    ))
    if [[ "$(stat -c '%d' /var/tmp)" \
        == "$(stat -c '%d' /var/backups/betboy)" ]]; then
        shared_required_kib=$((
            backup_apparent_kib * 2 + database_apparent_kib * 5 + 524288
        ))
        (( rollback_available_kib >= shared_required_kib )) \
            || die "Insufficient shared space for an independent backup snapshot and restore."
    else
        (( rollback_available_kib >= rollback_required_kib \
            && backup_available_kib >= backup_required_kib )) \
            || die "Insufficient space for an independent backup snapshot and restore."
    fi
    for worker in "${BETBOY_WORKERS[@]}"; do
        if systemctl is-active --quiet "${worker}"; then
            die "Worker ${worker} is active; retry after it finishes."
        fi
    done
    prepare_dependencies
}

preflight "$@"
remember_unit_state
snapshot_root_files
UPDATE_STARTED=1
ensure_backup_principal

log "Stopping all seven BetBoy timers."
systemctl stop "${BETBOY_TIMERS[@]}"
wait_for_workers || die "Timed out waiting for a raced BetBoy worker."

APP_STOPPED=1
systemctl stop betboy-app.service
wait_for_workers || die "A worker remained active after application shutdown."
verify_no_betboy_processes
disable_runtime_autostart
ensure_ledger_hmac_key
purge_python_caches
verify_untracked_policy
if [[ "${MIGRATION_RESUME_TARGET}" == 1 ]]; then
    verify_resume_app_bytes
else
    verify_clean_worktree "${PREVIOUS_HEAD}" \
        || die "Tracked files or index changed after quiescing runtime writers."
    verify_app_bytes "${PREVIOUS_MANIFEST}"
fi
snapshot_backup_source_metadata
snapshot_backup_archives
prepare_challenge_migration_boundary
create_fresh_backup

# Materialize only root-verified Git blobs as the unprivileged service user.
# update-ref/read-tree move repository metadata without checkout filters/hooks.
apply_trusted_payload "${TARGET_MANIFEST}" "${TARGET_PAYLOAD}"
git_betboy update-ref refs/heads/main "${TARGET_HEAD}" "${PREVIOUS_HEAD}"
git_betboy read-tree "${TARGET_HEAD}"
[[ "$(git_betboy rev-parse HEAD)" == "${TARGET_HEAD}" ]] \
    || die "App checkout did not reach the authorized target."
verify_clean_worktree "${TARGET_HEAD}" \
    || die "Tracked files or index differ from the authorized target."
verify_app_bytes "${TARGET_MANIFEST}"

install_trusted_root_files
prepare_backup_storage_and_sources
verify_backup_source_dac
verify_no_betboy_processes
verify_untracked_policy
verify_clean_worktree "${TARGET_HEAD}" \
    || die "Git index changed after target installation."
verify_app_bytes "${TARGET_MANIFEST}"

migrate_challenge_integrity_offline
verify_no_betboy_processes
verify_backup_service_migration

NEW_APP_STARTED=1
systemctl start betboy-app.service
curl --fail --silent --show-error \
    --retry 12 --retry-all-errors --retry-delay 2 \
    --connect-timeout 3 --max-time 5 \
    "${HEALTH_URL}" | grep -qx 'ok'

systemctl start "${BETBOY_TIMERS[@]}"
systemctl is-active --quiet betboy-app.service
for timer in "${BETBOY_TIMERS[@]}"; do
    systemctl is-active --quiet "${timer}"
done
verify_public_proxy

# Enablement is the final mutation.  Until the app and all timers have started
# and passed their health checks, a reboot therefore remains fail-closed.
systemctl enable betboy-app.service "${BETBOY_TIMERS[@]}"
durable_os_sync
verify_runtime

UPDATE_COMPLETE=1
log "BetBoy updated to ${TARGET_HEAD}; all seven timers are active and enabled."
