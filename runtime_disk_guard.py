"""Disk headroom of the runtime volume (Audit 25.10.2026 D6, Massnahme 9).

On 28.10.2026 the runtime databases took 8.7 GB of a 38 GB volume with 20 GB free;
``context_models.db`` alone was 7.8 GiB and grows by tens of megabytes a day. A full
volume would stop every SQLite writer at once. The guard measures the volume and the
runtime databases, keeps one sample per UTC day and reports ``low`` below a fixed
headroom. It never deletes data: retention of the append-only context receipts is an
owner decision (docs/audits/2026-10-28-massnahme-9-plattenwaechter.md).
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from runtime_paths import RUNTIME_STATE_DIR, atomic_write_text

STATUS_FILE = "disk_status.json"
MIN_FREE_BYTES = 5 * 1024 ** 3
MIN_FREE_RATIO = 0.10
MAX_DAILY_SAMPLES = 120
GIB = 1024 ** 3


def _utc(now: Optional[datetime]) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(timezone.utc)


def _database_sizes(directory: Path) -> dict[str, int]:
    sizes = {}
    for path in sorted(directory.glob("*.db")):
        try:
            sizes[path.name] = path.stat().st_size
        except OSError:
            continue
    return sizes


def _previous_samples(path: Path) -> list[dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    samples = document.get("daily_samples") if isinstance(document, dict) else None
    return [sample for sample in samples if isinstance(sample, dict)] if isinstance(samples, list) else []


def _growth_per_day(samples: list[dict[str, Any]]) -> Optional[int]:
    """Average growth of the runtime databases between the first and the last day."""
    if len(samples) < 2:
        return None
    try:
        first, last = samples[0], samples[-1]
        days = (datetime.fromisoformat(last["day"]) - datetime.fromisoformat(first["day"])).days
        if days <= 0:
            return None
        return int((int(last["database_bytes"]) - int(first["database_bytes"])) / days)
    except (KeyError, TypeError, ValueError):
        return None


def check_runtime_disk(
    directory: Path = RUNTIME_STATE_DIR,
    *,
    now: Optional[datetime] = None,
    usage: Callable[[Path], Any] = shutil.disk_usage,
) -> dict[str, Any]:
    """Measure, persist ``disk_status.json`` and return the status record."""
    current = _utc(now)
    directory = Path(directory)
    total, _used, free = usage(directory)
    sizes = _database_sizes(directory)
    database_bytes = sum(sizes.values())
    status_path = directory / STATUS_FILE
    day = current.date().isoformat()
    samples = [sample for sample in _previous_samples(status_path) if sample.get("day") != day]
    samples.append({"day": day, "free_bytes": int(free), "database_bytes": int(database_bytes)})
    samples = samples[-MAX_DAILY_SAMPLES:]
    low = free < MIN_FREE_BYTES or (total > 0 and free / total < MIN_FREE_RATIO)
    growth = _growth_per_day(samples)
    record = {
        "status": "low" if low else "ok",
        "checked_at": current.isoformat(),
        "total_bytes": int(total),
        "free_bytes": int(free),
        "free_ratio": round(free / total, 4) if total > 0 else None,
        "min_free_bytes": MIN_FREE_BYTES,
        "min_free_ratio": MIN_FREE_RATIO,
        "database_bytes": int(database_bytes),
        "largest_databases": dict(sorted(sizes.items(), key=lambda item: -item[1])[:5]),
        "database_growth_bytes_per_day": growth,
        "days_until_min_free": (
            int((free - MIN_FREE_BYTES) / growth) if growth and growth > 0 and free > MIN_FREE_BYTES else None
        ),
        "daily_samples": samples,
    }
    atomic_write_text(status_path, json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def disk_problem(record: dict[str, Any]) -> Optional[str]:
    """One journal line for the OnFailure alert, or ``None`` when the headroom is fine."""
    if record.get("status") != "low":
        return None
    ratio = record.get("free_ratio")
    percent = f"{ratio * 100:.0f} %" if isinstance(ratio, (int, float)) else "?"
    return (
        f"Speicherplatz knapp: {record['free_bytes'] / GIB:.1f} GB frei ({percent}); "
        f"Laufzeitdatenbanken {record['database_bytes'] / GIB:.1f} GB. Nichts wird gelöscht; "
        "Aufbewahrung entscheidet der Owner."
    )


def guard_runtime_disk(**kwargs: Any) -> Optional[str]:
    """Run the check for a scheduled job; a failing measurement never fails the job."""
    try:
        record = check_runtime_disk(**kwargs)
    except (OSError, ValueError) as exc:
        print(json.dumps({"disk_guard": "unavailable", "error_type": type(exc).__name__}))
        return None
    return disk_problem(record)
