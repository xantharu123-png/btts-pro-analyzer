#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /

readonly TRUSTED_UPDATER=/usr/local/sbin/betboy-update
readonly TRUSTED_BOOTSTRAP=/usr/local/sbin/betboy-bootstrap
readonly REPOSITORY_URL=https://github.com/xantharu123-png/btts-pro-analyzer.git
readonly APP_DIR=/opt/betboy/app
readonly VENV_DIR=/opt/betboy/venv
readonly HEALTH_URL=http://127.0.0.1:8501/_stcore/health
readonly RECOVERY_BACKUP_DIR=/var/backups/betboy-update
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
declare -A TIMER_WAS_ACTIVE=()
declare -A TIMER_WAS_ENABLED=()

log() {
    printf '[betboy-update] %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

as_betboy() {
    runuser -u betboy -- "$@"
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

expected_unit_sha256() {
    case "$1" in
        deploy/systemd/betboy-app.service) printf '%s\n' 1baa87c8ba83c74927ab348e18a583a57314e36c89d073030c1b90f88de38194 ;;
        deploy/systemd/betboy-backup.service) printf '%s\n' 4b8cfe04226976b2371ab832f9bd1f711c3ef031a8fcfffbabbb4779efd6bda1 ;;
        deploy/systemd/betboy-backup.timer) printf '%s\n' 918fd587a63dd57eb538c0e49d3f1dc13ffe1db9c99e46eeb2e4144605596aaa ;;
        deploy/systemd/betboy-esports.service) printf '%s\n' 06e6d6e01ae2647890ed893b0cbb7fb55ed1d7c425e6549f654c258a7735b253 ;;
        deploy/systemd/betboy-esports.timer) printf '%s\n' 97fd05b6df1df5afdb2b109f75ea1ad6354da3801300056e478b9a53ea320a6c ;;
        deploy/systemd/betboy-football-shadow.service) printf '%s\n' c34cc3a0d67f4ed2d96ad0849c56ab7bdf800749bca5997db83c4951665a32a4 ;;
        deploy/systemd/betboy-football-shadow.timer) printf '%s\n' a311d307bc5a604cba565b97212d815c8c9e5a085844dfa302ea4a1fb62d67bf ;;
        deploy/systemd/betboy-redcard-history.service) printf '%s\n' 315b8ffa8452192dfb8bc24b9313a72e9a84798582bef99c38fc9c7ce8a346ef ;;
        deploy/systemd/betboy-redcard-history.timer) printf '%s\n' cea8127dd10cfe3e911cd0d2f516576964109339e2303792f3c4282a260e26fb ;;
        deploy/systemd/betboy-redcard-settlement.service) printf '%s\n' 6347188ba24e7a5adcca8fe502a19bbc338d17071de9b2bd8e53d0e68642ab04 ;;
        deploy/systemd/betboy-redcard-settlement.timer) printf '%s\n' 86b28ef068b75854e2ce1536b11ac9982c9410a9f1716dfeaa7d6045918bba16 ;;
        deploy/systemd/betboy-tennis.service) printf '%s\n' d7a5dff63ae96b79c70aa0875cf5f9587728e76ea1a4b81da34ae8579266cc25 ;;
        deploy/systemd/betboy-tennis.timer) printf '%s\n' d1c58a3a36736f557d17d68cec6ef64d52e60e7c539d9af463341bb7df27b118 ;;
        deploy/systemd/betboy-wettfinder.service) printf '%s\n' 683fb4a2f6482871f3d69d19c4e35dcd61a0e7fc1bef1a5b7fd70a52484b55ce ;;
        deploy/systemd/betboy-wettfinder.timer) printf '%s\n' 7e26d233ba13afade225ff4b97f00b23a0954b798f7948a927a492563e335db4 ;;
        *) die "Unit is not byte-allowlisted: $1" ;;
    esac
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
    local path="/etc/systemd/system/${name}"
    local expected
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
    expected=$(expected_unit_sha256 "deploy/systemd/${name}")
    actual=$(sha256sum -- "${path}" | awk '{print $1}') || return 1
    [[ "${actual}" == "${expected}" ]] || return 1
    fragment=$(systemctl show "${name}" -p FragmentPath --value) || return 1
    dropins=$(systemctl show "${name}" -p DropInPaths --value) || return 1
    [[ "${fragment}" == "${path}" && -z "${dropins}" ]]
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
    local pids
    pids=$(pgrep -u betboy || true)
    [[ -z "${pids}" ]]
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

prepare_trusted_tree() {
    local fetched_head
    STAGE_DIR=$(mktemp -d /var/tmp/betboy-update.XXXXXXXX)
    chown root:betboy "${STAGE_DIR}"
    chmod 0750 "${STAGE_DIR}"
    TRUSTED_TREE="${STAGE_DIR}/source"

    root_git init --quiet "${TRUSTED_TREE}"
    root_git -C "${TRUSTED_TREE}" fetch --quiet --no-tags \
        "${REPOSITORY_URL}" refs/heads/main
    fetched_head=$(root_git -C "${TRUSTED_TREE}" rev-parse FETCH_HEAD)
    [[ "${fetched_head}" == "${REQUESTED_HEAD}" ]] \
        || die "Requested commit is not the current origin/main tip (${fetched_head})."
    root_git -C "${TRUSTED_TREE}" checkout --quiet --detach "${REQUESTED_HEAD}"
    TARGET_HEAD=$(root_git -C "${TRUSTED_TREE}" rev-parse HEAD)

    trusted_file requirements.txt >/dev/null
    trusted_file deploy/update_server.sh >/dev/null
    trusted_file deploy/bootstrap_server.sh >/dev/null
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
    TARGET_MANIFEST="${STAGE_DIR}/target-manifest.json"
    PREVIOUS_MANIFEST="${STAGE_DIR}/previous-manifest.json"
    TARGET_PAYLOAD="${STAGE_DIR}/target-payload"
    PREVIOUS_PAYLOAD="${STAGE_DIR}/previous-payload"

    /usr/bin/python3 -I - \
        "${TRUSTED_TREE}" "${PREVIOUS_HEAD}" "${TARGET_HEAD}" \
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
    if ! git_betboy diff --cached --quiet --no-ext-diff --no-textconv --ignore-submodules --; then
        die "Staged changes exist; preserve or resolve them first."
    fi
    branch=$(git_betboy symbolic-ref --quiet --short HEAD) \
        || die "Detached app HEAD is not deployable."
    [[ "${branch}" == main ]] || die "Expected app branch main, found ${branch}."

    # The network target is fixed here; no configured origin URL is used.
    git_betboy fetch --no-tags "${REPOSITORY_URL}" refs/heads/main
    fetched_head=$(git_betboy rev-parse FETCH_HEAD)
    [[ "${fetched_head}" == "${TARGET_HEAD}" ]] \
        || die "App checkout fetched a different main commit."
    git_betboy cat-file -e "${TARGET_HEAD}^{commit}"
    PREVIOUS_HEAD=$(git_betboy rev-parse HEAD)
    [[ "${PREVIOUS_HEAD}" =~ ^[0-9a-f]{40}$ ]] \
        || die "App checkout returned an invalid HEAD."
    root_git -C "${TRUSTED_TREE}" cat-file -e "${PREVIOUS_HEAD}^{commit}" \
        || die "Deployed HEAD is not in the trusted origin/main history."
    root_git -C "${TRUSTED_TREE}" merge-base --is-ancestor \
        "${PREVIOUS_HEAD}" "${TARGET_HEAD}" \
        || die "Deployed HEAD is not an ancestor of trusted origin/main."
    read -r ahead behind < <(
        root_git -C "${TRUSTED_TREE}" rev-list --left-right --count \
            "${PREVIOUS_HEAD}...${TARGET_HEAD}"
    )
    [[ "${ahead}" == 0 ]] || die "Deployed app branch is ahead of authorized main."
    log "Authorized target ${TARGET_HEAD:0:12}; commits to apply: ${behind}."

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

    create_trusted_manifests
    verify_app_bytes "${PREVIOUS_MANIFEST}"
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
    expected = {entry["path"] for entry in databases}
    actual = set(names) - {"MANIFEST.json"}
    if expected != actual or manifest.get("database_count") != len(databases):
        raise SystemExit("backup inventory does not match ZIP members")

    with tempfile.TemporaryDirectory(prefix="betboy-update-verify-") as temp:
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
            if result != [("ok",)]:
                raise SystemExit(f"SQLite quick_check failed: {entry['path']}")
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
        "${APP_DIR}" "${work_archive}" "${PREVIOUS_HEAD}" <<'PY'
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

root = Path(sys.argv[1])
archive_path = Path(sys.argv[2])
source_head = sys.argv[3]
excluded = {
    ".codex_test_venv", ".git", ".pytest_cache", ".pytest_tmp",
    ".venv", "__pycache__", "backups_runtime",
}
sources = []
for directory, dirnames, filenames in os.walk(root, followlinks=False):
    current = Path(directory)
    dirnames[:] = [
        name for name in dirnames
        if name not in excluded and not (current / name).is_symlink()
    ]
    for name in filenames:
        if not name.endswith((".db", ".sqlite", ".sqlite3")):
            continue
        source = current / name
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise SystemExit(f"database is not a regular file: {source}")
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

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_head": source_head,
        "database_count": len(inventory),
        "databases": inventory,
    }
    manifest_path = stage / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(
        archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.write(manifest_path, "MANIFEST.json")
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
    install -o root -g root -m 0600 "${work_archive}" "${partial_archive}"
    verify_backup_archive "${partial_archive}"
    mv -- "${partial_archive}" "${FRESH_BACKUP}"
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
    git_betboy ls-files -z --others --exclude-standard >"${inventory}"
    git_betboy ls-files -z --others --ignored --exclude-standard >>"${inventory}"
    chown root:betboy "${inventory}"
    chmod 0640 "${inventory}"

    as_betboy env PYTHONNOUSERSITE=1 PYTHONPATH= \
        /usr/bin/python3 -I - "${APP_DIR}" "${inventory}" <<'PY'
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1])
resolved_root = root.resolve(strict=True)
raw_paths = Path(sys.argv[2]).read_bytes().split(b"\0")
paths = sorted({raw.decode("utf-8", "strict") for raw in raw_paths if raw})
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

remember_unit_state() {
    local timer
    if systemctl is-active --quiet betboy-app.service; then
        APP_WAS_ACTIVE=1
    fi
    for timer in "${BETBOY_TIMERS[@]}"; do
        TIMER_WAS_ACTIVE["${timer}"]=0
        TIMER_WAS_ENABLED["${timer}"]=0
        if systemctl is-active --quiet "${timer}"; then
            TIMER_WAS_ACTIVE["${timer}"]=1
        fi
        if systemctl is-enabled --quiet "${timer}"; then
            TIMER_WAS_ENABLED["${timer}"]=1
        fi
    done
}

snapshot_root_files() {
    local timer
    ROLLBACK_ROOT="${STAGE_DIR}/root-rollback"
    install -d -m 0700 -o root -g root "${ROLLBACK_ROOT}/systemd"
    verify_root_owned_file "${TRUSTED_UPDATER}"
    verify_root_owned_file "${TRUSTED_BOOTSTRAP}"
    cp -a "${TRUSTED_UPDATER}" "${ROLLBACK_ROOT}/betboy-update"
    cp -a "${TRUSTED_BOOTSTRAP}" "${ROLLBACK_ROOT}/betboy-bootstrap"
    verify_installed_unit betboy-app.service
    cp -a /etc/systemd/system/betboy-app.service "${ROLLBACK_ROOT}/systemd/"
    for timer in "${BETBOY_TIMERS[@]}"; do
        verify_installed_unit "${timer}"
        verify_installed_unit "${timer%.timer}.service"
        cp -a "/etc/systemd/system/${timer}" "${ROLLBACK_ROOT}/systemd/"
        cp -a "/etc/systemd/system/${timer%.timer}.service" \
            "${ROLLBACK_ROOT}/systemd/"
    done
}

install_trusted_root_files() {
    local timer
    install -o root -g root -m 0755 \
        "$(trusted_file deploy/update_server.sh)" "${TRUSTED_UPDATER}"
    install -o root -g root -m 0755 \
        "$(trusted_file deploy/bootstrap_server.sh)" "${TRUSTED_BOOTSTRAP}"
    install -o root -g root -m 0644 \
        "$(trusted_file deploy/systemd/betboy-app.service)" \
        /etc/systemd/system/betboy-app.service
    for timer in "${BETBOY_TIMERS[@]}"; do
        install -o root -g root -m 0644 \
            "$(trusted_file deploy/systemd/${timer})" \
            "/etc/systemd/system/${timer}"
        install -o root -g root -m 0644 \
            "$(trusted_file deploy/systemd/${timer%.timer}.service)" \
            "/etc/systemd/system/${timer%.timer}.service"
    done
    systemctl daemon-reload
    verify_installed_unit betboy-app.service
    for timer in "${BETBOY_TIMERS[@]}"; do
        verify_installed_unit "${timer}"
        verify_installed_unit "${timer%.timer}.service"
    done
}

restore_root_files() {
    install -o root -g root -m 0755 \
        "${ROLLBACK_ROOT}/betboy-update" "${TRUSTED_UPDATER}" || return 1
    install -o root -g root -m 0755 \
        "${ROLLBACK_ROOT}/betboy-bootstrap" "${TRUSTED_BOOTSTRAP}" || return 1
    install -o root -g root -m 0644 \
        "${ROLLBACK_ROOT}"/systemd/* /etc/systemd/system/ || return 1
    systemctl daemon-reload || return 1
}

verify_restored_root_files() {
    local timer
    cmp -s "${ROLLBACK_ROOT}/betboy-update" "${TRUSTED_UPDATER}" || return 1
    cmp -s "${ROLLBACK_ROOT}/betboy-bootstrap" "${TRUSTED_BOOTSTRAP}" || return 1
    cmp -s "${ROLLBACK_ROOT}/systemd/betboy-app.service" \
        /etc/systemd/system/betboy-app.service || return 1
    check_installed_unit betboy-app.service || return 1
    for timer in "${BETBOY_TIMERS[@]}"; do
        cmp -s "${ROLLBACK_ROOT}/systemd/${timer}" \
            "/etc/systemd/system/${timer}" || return 1
        cmp -s "${ROLLBACK_ROOT}/systemd/${timer%.timer}.service" \
            "/etc/systemd/system/${timer%.timer}.service" || return 1
        check_installed_unit "${timer}" || return 1
        check_installed_unit "${timer%.timer}.service" || return 1
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
    local timer
    local failed=0

    # Configure enablement while everything is still stopped.
    for timer in "${BETBOY_TIMERS[@]}"; do
        if [[ "${TIMER_WAS_ENABLED[${timer}]:-0}" == 1 ]]; then
            systemctl enable "${timer}" >/dev/null 2>&1 || failed=1
        else
            systemctl disable "${timer}" >/dev/null 2>&1 || failed=1
        fi
        systemctl stop "${timer}" || failed=1
    done
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
    for timer in "${BETBOY_TIMERS[@]}"; do
        if [[ "${TIMER_WAS_ACTIVE[${timer}]:-0}" == 1 ]]; then
            systemctl start "${timer}" || return 1
        else
            systemctl stop "${timer}" || return 1
        fi
    done
    if [[ "${APP_WAS_ACTIVE}" == 1 ]]; then
        systemctl is-active --quiet betboy-app.service || return 1
    elif systemctl is-active --quiet betboy-app.service; then
        return 1
    fi
    for timer in "${BETBOY_TIMERS[@]}"; do
        if [[ "${TIMER_WAS_ENABLED[${timer}]:-0}" == 1 ]]; then
            systemctl is-enabled --quiet "${timer}" || return 1
        elif systemctl is-enabled --quiet "${timer}"; then
            return 1
        fi
        if [[ "${TIMER_WAS_ACTIVE[${timer}]:-0}" == 1 ]]; then
            systemctl is-active --quiet "${timer}" || return 1
        elif systemctl is-active --quiet "${timer}"; then
            return 1
        fi
    done
}

recover_update() {
    local status="$1"
    local current_head=""
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
    log "Update failed; forcing every app, timer and worker unit down."
    stop_all_runtime_units || recovery_ok=0
    if [[ "${NEW_APP_STARTED}" == 1 ]]; then
        log "FAIL-CLOSED: new app code may have touched databases."
        if [[ "${recovery_ok}" == 1 ]]; then
            log "All runtime units are stopped."
        else
            log "At least one runtime unit could not be confirmed stopped."
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

verify_runtime() {
    local timer
    systemctl is-active --quiet betboy-app.service
    for timer in "${BETBOY_TIMERS[@]}"; do
        systemctl is-active --quiet "${timer}"
        systemctl is-enabled --quiet "${timer}"
    done
    curl --fail --silent --show-error \
        --retry 12 --retry-all-errors --retry-delay 2 \
        --connect-timeout 3 --max-time 5 \
        "${HEALTH_URL}" | grep -qx 'ok'
}

preflight() {
    local required_command
    local worker
    local available_kib

    verify_invocation "$@"
    for required_command in \
        git runuser systemctl systemd-analyze install curl awk sort comm \
        bash df grep sleep readlink stat date mktemp cp mv rm cmp chown chmod \
        sha256sum find pgrep; do
        command -v "${required_command}" >/dev/null \
            || die "Missing command: ${required_command}"
    done
    [[ -x /usr/bin/python3 ]] || die "Missing trusted /usr/bin/python3."
    [[ ! -L /opt/betboy && ! -L "${APP_DIR}" ]] \
        || die "Application path must not traverse a symlink."
    verify_no_unit_dropin_paths
    prepare_trusted_tree
    prepare_app_checkout
    available_kib=$(df -Pk "${APP_DIR}" | awk 'NR == 2 {print $4}')
    [[ "${available_kib}" =~ ^[0-9]+$ ]] || die "Cannot determine free disk space."
    (( available_kib >= 2097152 )) || die "Less than 2 GiB free for safe staging."
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

log "Stopping all seven BetBoy timers."
systemctl stop "${BETBOY_TIMERS[@]}"
wait_for_workers || die "Timed out waiting for a raced BetBoy worker."

APP_STOPPED=1
systemctl stop betboy-app.service
wait_for_workers || die "A worker remained active after application shutdown."
verify_no_betboy_processes
purge_python_caches
verify_untracked_policy
verify_clean_worktree "${PREVIOUS_HEAD}" \
    || die "Tracked files or index changed after quiescing runtime writers."
verify_app_bytes "${PREVIOUS_MANIFEST}"
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
verify_no_betboy_processes
verify_untracked_policy
verify_clean_worktree "${TARGET_HEAD}" \
    || die "Git index changed after target installation."
verify_app_bytes "${TARGET_MANIFEST}"

NEW_APP_STARTED=1
systemctl restart betboy-app.service
curl --fail --silent --show-error \
    --retry 12 --retry-all-errors --retry-delay 2 \
    --connect-timeout 3 --max-time 5 \
    "${HEALTH_URL}" | grep -qx 'ok'

systemctl enable --now "${BETBOY_TIMERS[@]}"
systemctl restart "${BETBOY_TIMERS[@]}"
verify_runtime

UPDATE_COMPLETE=1
log "BetBoy updated to ${TARGET_HEAD}; all seven timers are active and enabled."
