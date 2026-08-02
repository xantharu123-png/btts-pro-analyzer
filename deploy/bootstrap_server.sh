#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${BETBOY_APP_DIR:-/opt/betboy/app}"
VENV_DIR="${BETBOY_VENV_DIR:-/opt/betboy/venv}"
PUBLIC_HOST="${BETBOY_HOST:-vps-a30a123f.vps.ovh.net}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root (sudo)." >&2
    exit 1
fi
if [[ ! -f "${APP_DIR}/app.py" ]]; then
    echo "BetBoy checkout not found at ${APP_DIR}." >&2
    exit 1
fi

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

if ! getent passwd betboy >/dev/null; then
    useradd \
        --system \
        --home-dir /opt/betboy \
        --shell /usr/sbin/nologin \
        --user-group \
        betboy
fi

install -d -m 0750 -o betboy -g betboy /opt/betboy
chown -R betboy:betboy "${APP_DIR}"
install -d -m 0750 -o root -g betboy /etc/betboy
install -d -m 0700 -o betboy -g betboy /var/backups/betboy
touch /etc/betboy/betboy.env
chown root:betboy /etc/betboy/betboy.env
chmod 0640 /etc/betboy/betboy.env

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    runuser -u betboy -- python3 -m venv "${VENV_DIR}"
fi
runuser -u betboy -- "${VENV_DIR}/bin/python" -m pip install --upgrade pip
runuser -u betboy -- env PIP_NO_CACHE_DIR=1 \
    "${VENV_DIR}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"

install -m 0644 "${APP_DIR}"/deploy/systemd/*.service /etc/systemd/system/
install -m 0644 "${APP_DIR}"/deploy/systemd/*.timer /etc/systemd/system/

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
systemctl enable --now fail2ban
systemctl enable --now unattended-upgrades
systemctl enable --now caddy
systemctl reload ssh

systemctl enable --now betboy-app.service
systemctl enable --now \
    betboy-football-shadow.timer \
    betboy-tennis.timer \
    betboy-esports.timer \
    betboy-redcard-settlement.timer \
    betboy-redcard-history.timer \
    betboy-backup.timer

echo "BetBoy bootstrap complete: https://${PUBLIC_HOST}"
