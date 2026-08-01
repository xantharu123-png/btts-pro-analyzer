"""Hintergrund-Scans: Thread-Registry + JSON-Persistenz.

Streamlit-kompatibles Muster: Scan-Funktionen laufen in Daemon-Threads
und rufen NIEMALS st.* auf (kein Session-Kontext im Thread).  Die Seite
startet den Job, zeigt den Fortschritt per Fragment-Polling und übernimmt
das Ergebnis beim nächsten Rerun in den session_state — dadurch laufen
mehrere Scans parallel, ohne sich gegenseitig abzubrechen, und ein
Seitenwechsel unterbricht nichts.

Persistenz: optional schreibt der Worker das Ergebnis (über eine
persist_fn in JSON-bare Form gebracht) nach scan_jobs/<name>.json, damit
andere Seiten (z. B. der Wett-Check) den letzten Scan auch nach einem
Neustart lesen können.

Thread-Sicherheit: Die Registry ist gelockt.  Die Scan-Funktionen teilen
sich ggf. denselben Analyzer — lesende Modellnutzung und API-Calls sind
dank GIL und eigener Requests-Sessions unkritisch; im Zweifel entstehen
doppelte Cache-Berechnungen, keine korrupten Zustände.
"""

from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

JOBS_DIR = Path(__file__).resolve().parent / "scan_jobs"

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def get_job(key: str) -> Dict[str, Any]:
    """Aktueller Job-Zustand (idle, wenn unbekannt). Enthält kein Ergebnis-
    Objekt im Fehlerfall; 'result' nur bei state == 'done'."""
    with _LOCK:
        job = _JOBS.get(key)
        if job is None:
            return {"state": "idle"}
        return dict(job)


def start_job(
    key: str,
    fn: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    *,
    persist_name: Optional[str] = None,
    persist_fn: Optional[Callable[[Any], Optional[dict]]] = None,
) -> bool:
    """Startet fn im Hintergrund-Thread.

    fn bekommt ein Keyword-Argument ``progress_cb`` injiziert
    (progress_cb(anteil_0_bis_1, text)); Scan-Funktionen müssen es als
    optionalen Parameter akzeptieren.  Rückgabe False, wenn der Job
    bereits läuft.  persist_fn(result) -> dict wird bei Erfolg als JSON
    unter scan_jobs/<persist_name>.json abgelegt.
    """
    with _LOCK:
        if _JOBS.get(key, {}).get("state") == "running":
            return False
        _JOBS[key] = {
            "state": "running",
            "started_at": _now(),
            "progress": 0.0,
            "progress_text": "Starte...",
        }

    call_kwargs = dict(kwargs or {})

    def _progress_cb(fraction: float, text: Optional[str] = None) -> None:
        with _LOCK:
            job = _JOBS.get(key)
            if job is None or job.get("state") != "running":
                return
            try:
                job["progress"] = min(max(float(fraction), 0.0), 1.0)
            except (TypeError, ValueError):
                pass
            if text:
                job["progress_text"] = str(text)

    def _run() -> None:
        try:
            result = fn(*args, progress_cb=_progress_cb, **call_kwargs)
        except Exception as exc:  # Fehler gehören zum Job, nicht zum Thread
            with _LOCK:
                _JOBS[key] = {
                    "state": "error",
                    "started_at": _JOBS.get(key, {}).get("started_at"),
                    "finished_at": _now(),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            return
        with _LOCK:
            _JOBS[key] = {
                "state": "done",
                "started_at": _JOBS.get(key, {}).get("started_at"),
                "finished_at": _now(),
                "progress": 1.0,
                "result": result,
            }
        if persist_name and persist_fn is not None:
            try:
                payload = persist_fn(result)
            except Exception:
                payload = None
            if payload is not None:
                _persist(persist_name, payload)

    threading.Thread(target=_run, daemon=True, name=f"scan-job-{key}").start()
    return True


def clear_job(key: str) -> None:
    with _LOCK:
        _JOBS.pop(key, None)


def _persist(name: str, payload: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    document = {"finished_at": _now(), **payload}
    target = JOBS_DIR / f"{name}.json"
    target.write_text(
        json.dumps(document, ensure_ascii=False, default=str), encoding="utf-8"
    )


def load_persisted(name: str, jobs_dir: Optional[Path] = None) -> Optional[dict]:
    """Letztes persistiertes Ergebnis (None bei fehlend/ungültig)."""
    target = Path(jobs_dir or JOBS_DIR) / f"{name}.json"
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None
