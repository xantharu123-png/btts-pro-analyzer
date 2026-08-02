"""Standalone Tages-Pipeline fuer Windows-Aufgabenplanung und Linux-systemd.

Ablauf (taeglich 07:17 lokal):
  1) Model-State neu bauen, wenn aelter als 7 Tage (rebuild_state.py --if-stale-days 7)
  2) Tages-Scan (tennis_daily.py) - idempotent, Doppel-Scan am selben Tag ist harmlos
  3) Montags: Kalibrierungs-Waechter (calibration_watch_runner.py)
     -> Ergebnis nach tennis/data/calibration_watch_latest.json
  4) Montags: Wochenreport (weekly_report.py) -> HTML + Browser oeffnet sich

Logs: logs/pipeline_<datum>.log

Flags fuer Tests: --skip-rebuild --skip-scan --skip-watch --skip-report
--force-monday (Waechter/Report auch an anderen Wochentagen) --no-open
Exit-Code 1, wenn ein angeforderter Pipeline-Schritt fehlschlaegt.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))

WINDOWS_VENV_PY = ROOT / ".codex_test_venv" / "Scripts" / "python.exe"
LOG_DIR = ROOT / "logs"
WATCH_JSON = ROOT / "tennis" / "data" / "calibration_watch_latest.json"

MAX_STATE_AGE_DAYS = 7
WATCH_WEEKDAY = 0  # Montag: nach den Wochenend-Matches

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def python_executable() -> Path:
    """Use the local Windows venv when present, otherwise this interpreter."""
    if WINDOWS_VENV_PY.is_file():
        return WINDOWS_VENV_PY
    return Path(sys.executable)


def run_step(log: logging.Logger, name: str, script: str,
             args: list[str], timeout: int) -> str | None:
    """Run a project script with the venv python. Return combined output or None."""
    log.info("=== %s gestartet (Timeout %ds) ===", name, timeout)
    t0 = time.time()
    try:
        # PYTHONUTF8: Kind-Prozesse laufen ohne Konsole (Aufgabenplanung);
        # sonst faellt stdout auf cp1252 zurueck und Umlaute/Sonderzeichen
        # (z. B. "−0,7 %") lassen den Scan mit UnicodeEncodeError crashen.
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [str(python_executable()), str(ROOT / "scripts" / script), *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(ROOT), creationflags=CREATE_NO_WINDOW, env=env,
        )
    except subprocess.TimeoutExpired:
        log.error("%s: TIMEOUT nach %ds", name, timeout)
        return None
    except OSError as exc:
        log.error("%s: Start fehlgeschlagen: %s", name, exc)
        return None
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    log.info("%s beendet rc=%s in %.0fs\n%s", name, proc.returncode,
             time.time() - t0, out[-2500:])
    if proc.returncode != 0:
        log.error("%s FEHLGESCHLAGEN (rc=%s)", name, proc.returncode)
        return None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-rebuild", action="store_true")
    ap.add_argument("--skip-scan", action="store_true")
    ap.add_argument("--skip-watch", action="store_true")
    ap.add_argument("--skip-report", action="store_true")
    ap.add_argument("--force-monday", action="store_true",
                    help="Waechter + Report auch an anderen Wochentagen laufen lassen")
    ap.add_argument("--no-open", action="store_true", help="Report nicht im Browser oeffnen")
    args = ap.parse_args()

    LOG_DIR.mkdir(exist_ok=True)
    log = logging.getLogger("pipeline")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / f"pipeline_{date.today().isoformat()}.log",
                             encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if sys.stderr is not None:  # pythonw (Aufgabenplanung) hat keine Konsole
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        log.addHandler(ch)

    log.info("Pipeline-Start (Wochentag %s)", date.today().strftime("%A"))
    pipeline_ok = True

    # 1) State-Rebuild (no-op wenn frisch)
    if not args.skip_rebuild:
        out = run_step(log, "State-Rebuild", "rebuild_state.py",
                       ["--if-stale-days", str(MAX_STATE_AGE_DAYS)], timeout=900)
        if out is None:
            log.warning("Rebuild fehlgeschlagen - Scan nutzt bisherigen State.")
            pipeline_ok = False

    # 2) Tages-Scan
    scan_ok = True
    if not args.skip_scan:
        scan_ok = run_step(log, "Tages-Scan", "tennis_daily.py", [], timeout=900) is not None
        pipeline_ok = pipeline_ok and scan_ok

    monday = date.today().weekday() == WATCH_WEEKDAY or args.force_monday

    # 3) Kalibrierungs-Waechter (montags)
    if monday and not args.skip_watch:
        out = run_step(log, "Kalibrierungs-Waechter", "calibration_watch_runner.py",
                       [], timeout=7200)
        payload = None
        if out:
            for line in out.splitlines():
                if line.startswith("CALIBRATION_WATCH_JSON="):
                    try:
                        payload = json.loads(line.split("=", 1)[1])
                    except ValueError:
                        payload = None
        if payload is not None:
            payload["run_date"] = date.today().isoformat()
            WATCH_JSON.write_text(json.dumps(payload), encoding="utf-8")
            log.info("Waechter-Ergebnis gespeichert: status=%s n=%s",
                     payload.get("status"), payload.get("n_scored"))
            if payload.get("status") == "drift":
                log.warning("WAECHTER-ALARM: Satz-Maerkte driften!")
        else:
            log.error("Waechter lieferte kein JSON - Report zeigt letzten Stand.")
            pipeline_ok = False

    # 4) Wochenreport (montags)
    if monday and not args.skip_report:
        rargs = ["--days", "2"]
        if not args.no_open:
            rargs.append("--open")
        report_ok = (
            run_step(log, "Wochenreport", "weekly_report.py", rargs, timeout=300)
            is not None
        )
        pipeline_ok = pipeline_ok and report_ok

    log.info(
        "Pipeline-Ende (Scan %s, Gesamt %s)",
        "OK" if scan_ok else "FEHLGESCHLAGEN",
        "OK" if pipeline_ok else "FEHLGESCHLAGEN",
    )
    for handler in list(log.handlers):
        handler.flush()
        handler.close()
        log.removeHandler(handler)
    return 0 if pipeline_ok else 1


if __name__ == "__main__":
    sys.exit(main())
