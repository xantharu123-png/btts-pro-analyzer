#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${BETBOY_APP_DIR:-/opt/betboy/app}"
VENV_DIR="${BETBOY_VENV_DIR:-/opt/betboy/venv}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root (sudo)." >&2
    exit 1
fi

systemctl stop betboy-app.service
runuser -u betboy -- git -C "${APP_DIR}" pull --ff-only
runuser -u betboy -- env PIP_NO_CACHE_DIR=1 \
    "${VENV_DIR}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"

install -m 0644 "${APP_DIR}"/deploy/systemd/*.service /etc/systemd/system/
install -m 0644 "${APP_DIR}"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now betboy-wettfinder.timer betboy-esports.timer
systemctl restart betboy-wettfinder.timer betboy-esports.timer
systemctl restart betboy-app.service

echo "BetBoy updated to $(runuser -u betboy -- git -C "${APP_DIR}" rev-parse --short HEAD)"
