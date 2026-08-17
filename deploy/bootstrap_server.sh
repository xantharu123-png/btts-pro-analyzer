#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /

readonly TRUSTED_BOOTSTRAP=/usr/local/sbin/betboy-bootstrap
readonly TRUSTED_UPDATER=/usr/local/sbin/betboy-update
readonly REPOSITORY_URL=https://github.com/xantharu123-png/btts-pro-analyzer.git
readonly APP_DIR=/opt/betboy/app
readonly VENV_DIR=/opt/betboy/venv
readonly PUBLIC_HOST=vps-a30a123f.vps.ovh.net

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

log() {
    printf '[betboy-bootstrap] %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
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

verify_no_betboy_processes() {
    local pids
    pids=$(pgrep -u betboy || true)
    [[ -z "${pids}" ]] \
        || die "Unexpected betboy process exists on this fresh host: ${pids//$'\n'/, }"
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
}

verify_invocation "$@"
command -v git >/dev/null || die "Install Git before the trusted bootstrap."
for required_command in \
    git runuser systemctl systemd-analyze install awk grep bash readlink \
    stat find chown chmod sha256sum pgrep; do
    command -v "${required_command}" >/dev/null \
        || die "Missing prerequisite command: ${required_command}"
done
[[ -x /usr/bin/python3 ]] || die "Missing trusted /usr/bin/python3."
getent passwd betboy >/dev/null \
    || die "Create the betboy service account before bootstrap (see deploy/README.md)."
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
install -d -m 0700 -o betboy -g betboy /var/backups/betboy
touch /etc/betboy/betboy.env
chown root:betboy /etc/betboy/betboy.env
chmod 0640 /etc/betboy/betboy.env

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

cat > /etc/caddy/Caddyfile <<EOF
${PUBLIC_HOST} {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
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

systemctl daemon-reload
verify_no_unit_dropin_paths
verify_installed_unit betboy-app.service
for timer in "${BETBOY_TIMERS[@]}"; do
    verify_installed_unit "${timer}"
    verify_installed_unit "${timer%.timer}.service"
done
systemctl enable --now fail2ban
systemctl enable --now unattended-upgrades
systemctl enable --now caddy
systemctl reload ssh

verify_no_betboy_processes
systemctl enable --now betboy-app.service
curl --fail --silent --show-error \
    --retry 12 --retry-all-errors --retry-delay 2 \
    --connect-timeout 3 --max-time 5 \
    http://127.0.0.1:8501/_stcore/health | grep -qx 'ok'
systemctl enable --now "${BETBOY_TIMERS[@]}"

log "Bootstrap complete at ${REQUESTED_HEAD}: https://${PUBLIC_HOST}"
log "Future updates: sudo ${TRUSTED_UPDATER} <40-hex-origin-main-commit>"
