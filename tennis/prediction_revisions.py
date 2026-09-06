"""Append-only current model observations alongside frozen entry predictions.

The parent prediction remains the identity used by results and price ledgers.
These observations never rewrite its original model or adopt its entry price.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path


REVISION_SCHEMA = """
CREATE TABLE IF NOT EXISTS prediction_revisions (
    revision_id TEXT PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    modeled_utc REAL NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tennis_revision_latest
    ON prediction_revisions(prediction_id, modeled_utc DESC);
CREATE TRIGGER IF NOT EXISTS tennis_model_revision_no_update
BEFORE UPDATE ON prediction_revisions
BEGIN SELECT RAISE(ABORT, 'tennis model revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS tennis_model_revision_no_delete
BEFORE DELETE ON prediction_revisions
BEGIN SELECT RAISE(ABORT, 'tennis model revisions are immutable'); END;
"""


def utc_epoch(value: datetime | str | float) -> float:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("model time must be timezone-aware")
        value = value.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("model time must be a finite UTC timestamp")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("model time must be a finite UTC timestamp")
    return value


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def append_revision(conn: sqlite3.Connection, prediction_id: int, payload: dict) -> str:
    """Append one causal observation, rejecting ambiguous equal-time states."""
    modeled = utc_epoch(payload["created_utc"])
    parent = conn.execute("SELECT created_utc FROM predictions WHERE id=?", (prediction_id,)).fetchone()
    if parent is None or modeled < utc_epoch(parent[0]):
        raise ValueError("tennis model revision precedes its original prediction")
    if payload.get("scheduled_start_utc"):
        if modeled >= utc_epoch(payload["scheduled_start_utc"]):
            raise ValueError("tennis model revision must precede match start")
    for key in ("p_raw", "p_cal"):
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"invalid tennis {key}")
    serialized = _canonical(payload)
    revision_id = hashlib.sha256(f"{prediction_id}\n{serialized}".encode("utf-8")).hexdigest()
    equal_time = conn.execute(
        "SELECT revision_id FROM prediction_revisions WHERE prediction_id=? AND modeled_utc=?",
        (prediction_id, modeled),
    ).fetchall()
    if any(row[0] != revision_id for row in equal_time):
        raise ValueError("ambiguous equal-time tennis model revisions")
    conn.execute(
        "INSERT OR IGNORE INTO prediction_revisions VALUES (?,?,?,?)",
        (revision_id, prediction_id, modeled, serialized),
    )
    return revision_id


def freeze_legacy_baseline(conn: sqlite3.Connection, prediction_id: int) -> str | None:
    """Freeze a valid original row before its first mutable fixture refresh.

    This imports existing facts at their stored original clock; it is not a new
    model calculation. Missing native IDs, kickoff or context remain unknown.
    Rows with any existing revision are never retroactively reconstructed from
    potentially refreshed parent metadata.
    """
    if conn.execute("SELECT 1 FROM prediction_revisions WHERE prediction_id=? LIMIT 1", (prediction_id,)).fetchone():
        return None
    cursor = conn.execute("SELECT * FROM predictions WHERE id=?", (prediction_id,))
    stored = cursor.fetchone()
    if stored is None:
        raise ValueError("unknown original tennis prediction")
    original = dict(zip((column[0] for column in cursor.description), stored))
    fields = (
        "created_utc", "match_date", "provider_event_id", "scheduled_start_utc", "fixture_source",
        "tour", "tournament", "surface", "best_of", "player_a", "player_b", "p_raw", "p_cal",
        "markets_json", "gates_json", "context_json", "verdict", "recommended_side", "recommended_edge",
        "model_version", "policy_version",
    )
    payload = {field: original.get(field) for field in fields}
    for field in ("match_date", "player_a", "player_b", "model_version", "policy_version"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"invalid original tennis {field}")
    date.fromisoformat(payload["match_date"])
    if payload["player_a"] == payload["player_b"]:
        raise ValueError("invalid original tennis player identity")
    for field in ("provider_event_id", "fixture_source"):
        value = payload[field]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"invalid original tennis {field}")
    for field in ("markets_json", "gates_json", "context_json"):
        value = payload[field]
        if value is not None and (not isinstance(value, str) or not isinstance(json.loads(value), dict)):
            raise ValueError(f"invalid original tennis {field}")
    # append_revision applies the same strict finite probability and pre-match
    # clock checks to this imported original as to a fresh model observation.
    payload["revision_origin"] = "legacy_imported_baseline"
    return append_revision(conn, prediction_id, payload)


def read_latest_predictions(
    db_path: str | Path, *, pending_only: bool = True,
    as_of: datetime | str | float | None = None,
) -> list[dict]:
    """Read latest causal observations without creating/migrating any database.

    ``id`` keeps the original settlement identity. ``initial_created_utc`` and
    ``model_revision_id`` expose that the visible model may be a later version.
    A later model cannot silently reuse the original entry/closing prices.
    """
    path = Path(db_path)
    if not path.is_file():
        return []
    cutoff = utc_epoch(as_of if as_of is not None else datetime.now(timezone.utc))
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "predictions" not in tables:
            return []
        columns = {row[1] for row in conn.execute("PRAGMA table_info(predictions)")}
        if not {"id", "created_utc", "settled"}.issubset(columns):
            return []
        sql = "SELECT * FROM predictions" + (" WHERE settled=0" if pending_only else "")
        originals = [dict(row) for row in conn.execute(sql)]
        results = []
        for original in originals:
            if utc_epoch(original["created_utc"]) > cutoff:
                continue
            row = dict(original)
            row["initial_created_utc"] = original["created_utc"]
            row["model_revision_id"] = None
            revisions = []
            if "prediction_revisions" in tables:
                revisions = conn.execute(
                    "SELECT * FROM prediction_revisions WHERE prediction_id=? AND modeled_utc<=? ORDER BY modeled_utc DESC, revision_id",
                    (original["id"], cutoff),
                ).fetchall()
                if not revisions and conn.execute(
                    "SELECT 1 FROM prediction_revisions WHERE prediction_id=? LIMIT 1", (original["id"],)
                ).fetchone():
                    # A previously migrated row may have only later revisions.
                    # Its current parent schedule cannot reconstruct a missing
                    # historical baseline without leaking subsequently known facts.
                    continue
            if revisions:
                latest = revisions[0]
                payload = json.loads(latest["payload_json"])
                expected = hashlib.sha256(f"{original['id']}\n{_canonical(payload)}".encode("utf-8")).hexdigest()
                if expected != latest["revision_id"] or utc_epoch(payload["created_utc"]) != latest["modeled_utc"]:
                    raise ValueError("tennis model revision content mismatch")
                if len(revisions) > 1 and revisions[1]["modeled_utc"] == latest["modeled_utc"]:
                    raise ValueError("ambiguous equal-time tennis model revisions")
                for field in ("player_a", "player_b", "model_version", "policy_version"):
                    if payload.get(field) != original.get(field):
                        raise ValueError("tennis model revision identity mismatch")
                if payload.get("scheduled_start_utc") and latest["modeled_utc"] >= utc_epoch(payload["scheduled_start_utc"]):
                    raise ValueError("tennis model revision follows match start")
                row.update(payload)
                row["model_revision_id"] = latest["revision_id"]
                if latest["modeled_utc"] != original["created_utc"]:
                    for field in ("odds_a", "odds_b", "price_checked_utc", "entry_quote_id_a", "entry_quote_id_b", "closing_odds_a", "closing_odds_b", "closing_checked_utc", "closing_quote_id_a", "closing_quote_id_b"):
                        row[field] = None
            # Explicit historical reads must not expose a subsequently added
            # entry/closing price as if it had been known at the cutoff.
            for time_field, price_fields in (
                ("price_checked_utc", ("odds_a", "odds_b", "price_checked_utc", "entry_quote_id_a", "entry_quote_id_b")),
                ("closing_checked_utc", ("closing_odds_a", "closing_odds_b", "closing_checked_utc", "closing_quote_id_a", "closing_quote_id_b")),
            ):
                if row.get(time_field) is not None and utc_epoch(row[time_field]) > cutoff:
                    for field in price_fields:
                        row[field] = None
            results.append(row)
    return sorted(results, key=lambda row: (str(row.get("scheduled_start_utc") or row.get("match_date") or ""), row["id"]))
