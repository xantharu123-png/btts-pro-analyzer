"""Optional release condition: the model must have beaten the no-vig closing market.

Audit 2026-10-16 K2: the walk-forward release gate compares the model with a
Laplace base rate, which proves no market skill. This module reads the per-cell
verdicts written by ``scripts/market_benchmark_report.py --gate-json`` and lets
``challenge_engine.build_fixture_candidates`` add a block reason when the
league/market cell has not beaten the market.

Off by default: ``BETBOY_RELEASE_MARKET_BENCHMARK=1`` enables it. The owner's
recorded product rule of 2026-10-17 rejects a hard market gate, and the first
benchmark (2026-10-19) shows 0 of 112 cells beating the market, so enabling it
empties every real-money path until a model actually beats the market. That is
the honest state of the evidence, not a defect of the gate.

Fail-closed: when enabled, a missing, malformed or stale gate document and an
unknown cell all count as "not passed".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any, Optional

from runtime_paths import RUNTIME_STATE_DIR

FLAG = "BETBOY_RELEASE_MARKET_BENCHMARK"
PATH_FLAG = "BETBOY_MARKET_GATE_PATH"
DEFAULT_PATH = RUNTIME_STATE_DIR / "market_benchmark" / "market_gate.json"
MAX_AGE = timedelta(days=120)
MAX_BYTES = 8 * 1024 * 1024
BLOCK_REASON = "Marktbenchmark gegen No-Vig-Closing nicht bestanden"


def market_benchmark_required() -> bool:
    return os.environ.get(FLAG, "0").strip() == "1"


def gate_path(path: Optional[Path | str] = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.environ.get(PATH_FLAG, "").strip()
    return Path(configured) if configured else DEFAULT_PATH


@lru_cache(maxsize=8)
def _load(path_text: str, mtime_ns: int, size: int) -> Optional[dict[str, Any]]:
    try:
        if size > MAX_BYTES:
            return None
        document = json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(document, dict) or not isinstance(document.get("cells"), dict):
        return None
    if not isinstance(document.get("version"), str) or not isinstance(document.get("generated_at"), str):
        return None
    return document


def load_gate_document(path: Optional[Path | str] = None) -> Optional[dict[str, Any]]:
    target = gate_path(path)
    try:
        stat = target.stat()
    except OSError:
        return None
    return _load(str(target), stat.st_mtime_ns, stat.st_size)


def _generated_at(document: dict[str, Any]) -> Optional[datetime]:
    try:
        stamp = datetime.fromisoformat(document["generated_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def market_benchmark_verdict(league_id: int, market_key: str, *, path: Optional[Path | str] = None,
                             now: Optional[datetime] = None) -> Optional[bool]:
    """True/False for a benchmarked cell; None when no current verdict exists."""
    document = load_gate_document(path)
    if document is None:
        return None
    generated = _generated_at(document)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if generated is None or not timedelta(0) <= current - generated <= MAX_AGE:
        return None
    cell = document["cells"].get(f"{int(league_id)}:{market_key}")
    if not isinstance(cell, dict) or not isinstance(cell.get("market_beaten"), bool):
        return None
    return bool(cell["market_beaten"])


def market_benchmark_passed(league_id: int, market_key: str, *, path: Optional[Path | str] = None,
                            now: Optional[datetime] = None) -> bool:
    """Fail-closed: only an explicit, current positive verdict passes."""
    return market_benchmark_verdict(league_id, market_key, path=path, now=now) is True


__all__ = [
    "BLOCK_REASON", "DEFAULT_PATH", "FLAG", "MAX_AGE", "PATH_FLAG", "gate_path", "load_gate_document",
    "market_benchmark_passed", "market_benchmark_required", "market_benchmark_verdict",
]
