#!/usr/bin/python3 -I
"""OnFailure alert for BetBoy systemd units (Gesamtaudit 25.10.2026, D5).

Installed root-owned as ``/usr/local/libexec/betboy-alert.py`` and started by
the template ``betboy-alert@.service`` (user ``betboy`` with journal read
access) with the failed unit as its instance (``OnFailure=betboy-alert@%n.service``).
Standard library only, never raises: an alert must not fail the host. It
records the failure as one JSON line in ``runtime_state/ops_alerts.jsonl``,
keeps the last 50 alerts in ``runtime_state/ops_alerts.json`` for the app and,
when ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are present in the unit
environment (``/etc/betboy/betboy.env``), sends a short Telegram message.
Journal excerpts are redacted and shortened; the Telegram URL (it contains
the token) is never printed or logged.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.parse
import urllib.request

LOG_PATH = Path("/opt/betboy/app/runtime_state/ops_alerts.jsonl")
RUNTIME_COPY_PATH = Path("/opt/betboy/app/runtime_state/ops_alerts.json")
RUNTIME_COPY_LIMIT = 50
JOURNAL_LINES = 6
MESSAGE_LIMIT = 700
_UNIT_NAME = re.compile(r"[A-Za-z0-9@._:\\-]{1,160}")
_SECRET = re.compile(r"(?i)([A-Za-z0-9_-]*(?:api[_-]?key|key|token|secret|password|authorization|appid))(\s*[=:]\s*)(\S+)")
_NOISE = ("ScriptRunContext", "MemoryCacheStorageManager")


def redact(text: str) -> str:
    """Hide anything that looks like a credential value."""
    return _SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)


def _run(command: list[str], *, run=subprocess.run) -> str:
    try:
        completed = run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (completed.stdout or "").strip()


def unit_facts(unit: str, *, run=subprocess.run) -> dict:
    facts = {}
    for prop in ("Result", "ExecMainStatus", "ExecMainExitTimestamp", "InvocationID"):
        facts[prop.lower()] = _run(["systemctl", "show", unit, "-p", prop, "--value"], run=run) or None
    tail = _run(["journalctl", "-u", unit, "-n", "40", "--no-pager", "-o", "cat"], run=run)
    lines = [redact(line.strip())[:240] for line in tail.splitlines()
             if line.strip() and not any(noise in line for noise in _NOISE)]
    facts["journal_tail"] = lines[-JOURNAL_LINES:]
    return facts


def _append_log(record: dict, path: Path) -> str | None:
    try:
        path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        os.chmod(path, 0o640)
    except OSError as exc:
        return type(exc).__name__
    return None


def _write_runtime_copy(record: dict, path: Path, *, owner: str | None = "betboy") -> str | None:
    try:
        previous = []
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                previous = [item for item in loaded if isinstance(item, dict)]
        alerts = (previous + [record])[-RUNTIME_COPY_LIMIT:]
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(alerts, ensure_ascii=True, indent=1), encoding="utf-8")
        os.chmod(temporary, 0o640)
        if owner:
            try:
                shutil.chown(temporary, owner, owner)
            except (LookupError, OSError, PermissionError):
                pass
        os.replace(temporary, path)
    except (OSError, ValueError) as exc:
        return type(exc).__name__
    return None


def telegram_text(record: dict) -> str:
    head = (f"BetBoy: {record['unit']} fehlgeschlagen "
            f"({record.get('result') or 'unbekannt'}, Exit {record.get('execmainstatus') or '?'}) "
            f"um {record.get('execmainexittimestamp') or record['at']}")
    tail = "\n".join(record.get("journal_tail") or [])[-(MESSAGE_LIMIT - len(head) - 1):]
    return (head + ("\n" + tail if tail else ""))[:MESSAGE_LIMIT]


def send_telegram(record: dict, token: str, chat_id: str, *, urlopen=urllib.request.urlopen) -> str:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": telegram_text(record),
                                   "disable_web_page_preview": "true"}).encode("utf-8")
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
        return "sent" if status == 200 else f"failed:HTTP_{status}"
    except Exception as exc:  # the URL would leak the token; keep only the type
        return f"failed:{type(exc).__name__}"


def main(argv: list[str], *, env: dict | None = None, run=subprocess.run, urlopen=urllib.request.urlopen,
         log_path: Path = LOG_PATH, runtime_copy_path: Path = RUNTIME_COPY_PATH, now: datetime | None = None,
         owner: str | None = None) -> int:
    env = os.environ if env is None else env
    raw = argv[1] if len(argv) > 1 else ""
    unit = raw if _UNIT_NAME.fullmatch(raw) else "invalid-unit-name"
    record = {"at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), "unit": unit}
    record.update(unit_facts(unit, run=run) if unit != "invalid-unit-name" else {"journal_tail": []})
    record["telegram"] = "skipped"
    token, chat_id = (env.get("TELEGRAM_BOT_TOKEN") or "").strip(), (env.get("TELEGRAM_CHAT_ID") or "").strip()
    if token and chat_id:
        record["telegram"] = send_telegram(record, token, chat_id, urlopen=urlopen)
    log_error = _append_log(record, log_path)
    copy_error = _write_runtime_copy(record, runtime_copy_path, owner=owner)
    summary = {key: value for key, value in record.items() if key != "journal_tail"}
    if log_error:
        summary["log_error"] = log_error
    if copy_error:
        summary["runtime_copy_error"] = copy_error
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # pragma: no cover - last line of defence, never fail the host
        print(json.dumps({"unit": sys.argv[1] if len(sys.argv) > 1 else None, "alert_error": type(exc).__name__}))
        sys.exit(0)
