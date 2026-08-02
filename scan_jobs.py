"""Session-safe background scan jobs with atomic JSON persistence.

Workers never call Streamlit APIs. UI code starts a worker, polls this
registry, and transfers the result into its own session state.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

JOBS_DIR = Path(__file__).resolve().parent / "scan_jobs"

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def session_scope(session_state: Any) -> str:
    """Return a stable random namespace for one Streamlit session."""
    key = "_betboy_session_scope"
    try:
        scope = session_state.get(key)
    except AttributeError:
        scope = None
    if not isinstance(scope, str) or not scope:
        scope = uuid.uuid4().hex
        session_state[key] = scope
    return scope


def scoped_key(name: str, scope: Optional[str] = None) -> str:
    """Namespace a key while keeping legacy single-user callers compatible."""
    return f"{scope}:{name}" if scope else name


def _expire_locked(key: str) -> None:
    job = _JOBS.get(key)
    if not job or job.get("state") != "running":
        return
    deadline = job.get("_deadline_monotonic")
    if isinstance(deadline, (int, float)) and time.monotonic() > deadline:
        _JOBS[key] = {
            "state": "error",
            "started_at": job.get("started_at"),
            "finished_at": _now(),
            "error": "TimeoutError: Der Scan hat sein Zeitlimit ueberschritten.",
            "generation": job.get("generation"),
        }


def get_job(key: str) -> Dict[str, Any]:
    """Return the current job state, or ``idle`` for an unknown key."""
    with _LOCK:
        _expire_locked(key)
        job = _JOBS.get(key)
        if job is None:
            return {"state": "idle"}
        return {
            field: value
            for field, value in job.items()
            if not field.startswith("_")
        }


def start_job(
    key: str,
    fn: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    *,
    persist_name: Optional[str] = None,
    persist_fn: Optional[Callable[[Any], Optional[dict]]] = None,
    persist_scope: Optional[str] = None,
    timeout_seconds: float = 900.0,
) -> bool:
    """Start ``fn`` in a daemon thread.

    ``fn`` receives ``progress_cb(fraction, text)``. A generation token keeps
    an expired or cleared worker from overwriting a later run with the same key.
    """
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("timeout_seconds must be a positive finite number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive finite number")

    generation = uuid.uuid4().hex
    with _LOCK:
        _expire_locked(key)
        if _JOBS.get(key, {}).get("state") == "running":
            return False
        _JOBS[key] = {
            "state": "running",
            "started_at": _now(),
            "generation": generation,
            "_deadline_monotonic": time.monotonic() + timeout,
            "progress": 0.0,
            "progress_text": "Starte...",
        }

    call_kwargs = dict(kwargs or {})

    def _is_current_running(job: Optional[dict]) -> bool:
        return bool(
            job
            and job.get("state") == "running"
            and job.get("generation") == generation
        )

    def _progress_cb(fraction: float, message: Optional[str] = None) -> None:
        with _LOCK:
            job = _JOBS.get(key)
            if not _is_current_running(job):
                return
            try:
                job["progress"] = min(max(float(fraction), 0.0), 1.0)
            except (TypeError, ValueError, OverflowError):
                pass
            if message:
                job["progress_text"] = str(message)

    def _run() -> None:
        try:
            result = fn(*args, progress_cb=_progress_cb, **call_kwargs)
        except Exception as exc:
            with _LOCK:
                current = _JOBS.get(key)
                if not _is_current_running(current):
                    return
                _JOBS[key] = {
                    "state": "error",
                    "started_at": current.get("started_at"),
                    "finished_at": _now(),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                    "generation": generation,
                }
            return

        with _LOCK:
            current = _JOBS.get(key)
            if not _is_current_running(current):
                return
            _JOBS[key] = {
                "state": "done",
                "started_at": current.get("started_at"),
                "finished_at": _now(),
                "progress": 1.0,
                "result": result,
                "generation": generation,
            }

        if persist_name and persist_fn is not None:
            try:
                payload = persist_fn(result)
            except Exception:
                payload = None
            if payload is not None:
                _persist(persist_name, payload, scope=persist_scope)

    threading.Thread(
        target=_run,
        daemon=True,
        name=f"scan-job-{key}",
    ).start()
    return True


def clear_job(key: str) -> None:
    with _LOCK:
        _JOBS.pop(key, None)


def running_pages(
    page_jobs: Dict[str, Any],
    scope: Optional[str] = None,
) -> set:
    """Return pages with at least one active job in the requested session."""
    return {
        page
        for page, keys in page_jobs.items()
        if any(
            get_job(scoped_key(key, scope)).get("state") == "running"
            for key in keys
        )
    }


def _safe_file_part(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    if not clean:
        raise ValueError("Persistence name must contain a safe character")
    return clean


def _persist(name: str, payload: dict, *, scope: Optional[str] = None) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    document = {"finished_at": _now(), **payload}
    file_name = _safe_file_part(name)
    if scope:
        file_name = f"{_safe_file_part(scope)}__{file_name}"
    target = JOBS_DIR / f"{file_name}.json"
    temporary = JOBS_DIR / f".{file_name}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    temporary.replace(target)


def load_persisted(
    name: str,
    jobs_dir: Optional[Path] = None,
    *,
    scope: Optional[str] = None,
) -> Optional[dict]:
    """Load the latest persisted result, or ``None`` when unavailable."""
    file_name = _safe_file_part(name)
    if scope:
        file_name = f"{_safe_file_part(scope)}__{file_name}"
    target = Path(jobs_dir or JOBS_DIR) / f"{file_name}.json"
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None
