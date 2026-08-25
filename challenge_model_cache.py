"""Persistent cache for expensive challenge walk-forward model artifacts."""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Optional

from challenge_engine import MarketCalibration, ValidationMetrics


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent
    / "runtime_state"
    / "challenge_model_cache.db"
)
MODEL_ARTIFACT_SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS challenge_model_artifacts (
    cache_key TEXT PRIMARY KEY,
    model_signature TEXT NOT NULL,
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    history_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_challenge_model_scope
ON challenge_model_artifacts(model_signature, league_id, season);
"""

_LOCK = threading.Lock()


def _history_hash(history: list[dict[str, Any]]) -> str:
    document = json.dumps(
        history,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def _identity(
    model_signature: str,
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
) -> tuple[str, str]:
    history_hash = _history_hash(history)
    material = f"{model_signature}:{league_id}:{season}:{history_hash}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest(), history_hash


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    connection.execute("PRAGMA busy_timeout = 30000")
    journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
    if journal_mode != ("delete",):
        connection.close()
        raise sqlite3.OperationalError(
            "Challenge model cache requires DELETE journal mode"
        )
    connection.executescript(_SCHEMA)
    return connection


def load_model_artifact(
    model_signature: str,
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> Optional[
    tuple[
        dict[str, ValidationMetrics],
        dict[str, MarketCalibration],
    ]
]:
    cache_key, _history_digest = _identity(
        model_signature,
        league_id,
        season,
        history,
    )
    try:
        with _LOCK, closing(_connect(Path(db_path))) as connection:
            row = connection.execute(
                "SELECT payload FROM challenge_model_artifacts WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
    except (OSError, sqlite3.Error):
        return None
    if row is None:
        return None
    try:
        payload = json.loads(row[0])
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != MODEL_ARTIFACT_SCHEMA_VERSION
        ):
            return None
        raw_validation = payload["validation"]
        raw_calibration = payload["calibration"]
        if not isinstance(raw_validation, dict) or not isinstance(raw_calibration, dict):
            return None
        validation = {
            str(key): ValidationMetrics(**values)
            for key, values in raw_validation.items()
            if isinstance(values, dict)
        }
        calibration = {
            str(key): MarketCalibration(
                points=tuple(
                    (float(point[0]), float(point[1]))
                    for point in values["points"]
                ),
                samples=int(values["samples"]),
            )
            for key, values in raw_calibration.items()
            if isinstance(values, dict)
            and isinstance(values.get("points"), list)
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return validation, calibration


def save_model_artifact(
    model_signature: str,
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
    validation: dict[str, ValidationMetrics],
    calibration: dict[str, MarketCalibration],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    cache_key, history_hash = _identity(
        model_signature,
        league_id,
        season,
        history,
    )
    payload = json.dumps(
        {
            "schema_version": MODEL_ARTIFACT_SCHEMA_VERSION,
            "validation": {
                key: asdict(metric)
                for key, metric in validation.items()
                if isinstance(metric, ValidationMetrics)
            },
            "calibration": {
                key: {
                    "points": [list(point) for point in curve.points],
                    "samples": curve.samples,
                }
                for key, curve in calibration.items()
                if isinstance(curve, MarketCalibration)
            },
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    try:
        with _LOCK, closing(_connect(Path(db_path))) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO challenge_model_artifacts (
                    cache_key, model_signature, league_id, season,
                    history_hash, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    model_signature,
                    league_id,
                    season,
                    history_hash,
                    datetime.now(timezone.utc).isoformat(),
                    payload,
                ),
            )
            connection.execute(
                """
                DELETE FROM challenge_model_artifacts
                WHERE model_signature = ?
                  AND league_id = ?
                  AND season = ?
                  AND cache_key <> ?
                """,
                (model_signature, league_id, season, cache_key),
            )
            connection.commit()
    except (OSError, sqlite3.Error):
        return


__all__ = [
    "DEFAULT_DB_PATH",
    "MODEL_ARTIFACT_SCHEMA_VERSION",
    "load_model_artifact",
    "save_model_artifact",
]
