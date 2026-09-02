"""Append-only SQLite persistence and atomic publication for RisikoBet."""

from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Mapping, Optional

import runtime_paths
from riskobet_domain import (
    EvidenceStage,
    EventModelSnapshot,
    RiskCandidate,
    RiskRunSnapshot,
    ValidationEvidenceArtifact,
    canonical_json,
)
from riskobet_settlement import SettlementResult, SettlementStatus


DEFAULT_DB_PATH = runtime_paths.RUNTIME_STATE_DIR / "riskobet.db"
DEFAULT_LATEST_PATH = runtime_paths.RUNTIME_STATE_DIR / "riskobet_latest.json"
SCHEMA_VERSION = 3
SETTLEMENT_RESULTS = frozenset({"UNRESOLVED", "WON", "LOST", "VOID"})
_FINAL_SETTLEMENT_RESULTS = frozenset({"WON", "LOST", "VOID"})
_PRICE_WORDS = frozenset(
    {"odd", "odds", "quote", "price", "preis", "bookmaker", "profit", "clv"}
)
_ALLOWED_STAGE_TRANSITIONS = frozenset(
    {
        (EvidenceStage.RESEARCH, EvidenceStage.SHADOW),
        (EvidenceStage.SHADOW, EvidenceStage.VALIDATED),
    }
)


class FrozenRevisionError(ValueError):
    """An existing immutable identity was presented with different content."""


class _AmbiguousSettleableRevisionError(FrozenRevisionError):
    """One candidate has multiple equally current settleable revisions."""

    def __init__(self, message: str, *, starts_at: Iterable[str]) -> None:
        super().__init__(message)
        self.starts_at = tuple(starts_at)


class MissingRevisionError(RuntimeError):
    """A referenced run, snapshot or candidate does not exist."""


@contextmanager
def _publication_lock(latest_path: Path):
    """Serialize latest-pointer replacement across local service processes."""

    lock_path = Path(f"{latest_path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


_SCHEMA_V1 = """

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMPLETE', 'PARTIAL', 'FAILED')),
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    event_key TEXT NOT NULL,
    sport TEXT NOT NULL,
    model_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    modeled_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(event_key, model_version, input_hash)
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    sport TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    initial_stage TEXT NOT NULL
        CHECK (initial_stage IN ('RESEARCH', 'SHADOW', 'VALIDATED')),
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY(candidate_id, snapshot_id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS run_snapshots (
    run_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY(run_id, snapshot_id),
    UNIQUE(run_id, ordinal),
    FOREIGN KEY(run_id) REFERENCES runs(run_id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS run_candidates (
    run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0, 1)),
    PRIMARY KEY(run_id, candidate_id, snapshot_id),
    UNIQUE(run_id, ordinal),
    FOREIGN KEY(run_id) REFERENCES runs(run_id),
    FOREIGN KEY(candidate_id, snapshot_id)
        REFERENCES candidates(candidate_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    settlement_version TEXT NOT NULL,
    result TEXT NOT NULL
        CHECK (result IN ('OPEN', 'UNRESOLVED', 'WON', 'LOST', 'VOID')),
    settled_at TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(candidate_id, snapshot_id, settlement_version),
    FOREIGN KEY(candidate_id, snapshot_id)
        REFERENCES candidates(candidate_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS stage_events (
    stage_event_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    from_stage TEXT NOT NULL
        CHECK (from_stage IN ('RESEARCH', 'SHADOW', 'VALIDATED')),
    to_stage TEXT NOT NULL
        CHECK (to_stage IN ('RESEARCH', 'SHADOW', 'VALIDATED')),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    validation_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(candidate_id, snapshot_id, to_stage, validation_version),
    FOREIGN KEY(candidate_id, snapshot_id)
        REFERENCES candidates(candidate_id, snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_event_revision
ON snapshots(event_key, model_version, input_hash);

CREATE INDEX IF NOT EXISTS idx_candidates_event
ON candidates(event_key, snapshot_id);

CREATE INDEX IF NOT EXISTS idx_stage_events_candidate
ON stage_events(candidate_id, snapshot_id, occurred_at, stage_event_id);

CREATE INDEX IF NOT EXISTS idx_settlements_candidate
ON settlements(candidate_id, snapshot_id, settled_at, settlement_id);
"""


_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMPLETE', 'PARTIAL', 'FAILED')),
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    event_key TEXT NOT NULL,
    sport TEXT NOT NULL,
    model_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    modeled_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(event_key, model_version, input_hash)
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    sport TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    initial_stage TEXT NOT NULL CHECK (initial_stage IN ('RESEARCH', 'SHADOW')),
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY(candidate_id, snapshot_id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS run_snapshots (
    run_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY(run_id, snapshot_id),
    UNIQUE(run_id, ordinal),
    FOREIGN KEY(run_id) REFERENCES runs(run_id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS run_candidates (
    run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0, 1)),
    PRIMARY KEY(run_id, candidate_id, snapshot_id),
    UNIQUE(run_id, ordinal),
    FOREIGN KEY(run_id) REFERENCES runs(run_id),
    FOREIGN KEY(candidate_id, snapshot_id)
        REFERENCES candidates(candidate_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    settlement_version TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('UNRESOLVED', 'WON', 'LOST', 'VOID')),
    settled_at TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(candidate_id, snapshot_id, settlement_version, settled_at),
    FOREIGN KEY(candidate_id, snapshot_id)
        REFERENCES candidates(candidate_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS stage_events (
    stage_event_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    parent_stage_event_id TEXT,
    from_stage TEXT NOT NULL CHECK (from_stage IN ('RESEARCH', 'SHADOW')),
    to_stage TEXT NOT NULL CHECK (to_stage IN ('SHADOW', 'VALIDATED')),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    validation_version TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(candidate_id, snapshot_id, to_stage, validation_version),
    FOREIGN KEY(candidate_id, snapshot_id)
        REFERENCES candidates(candidate_id, snapshot_id),
    FOREIGN KEY(parent_stage_event_id) REFERENCES stage_events(stage_event_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_event_revision
ON snapshots(event_key, model_version, input_hash);

CREATE INDEX IF NOT EXISTS idx_candidates_event
ON candidates(event_key, snapshot_id);

CREATE INDEX IF NOT EXISTS idx_stage_events_candidate
ON stage_events(candidate_id, snapshot_id, occurred_at, stage_event_id);

CREATE INDEX IF NOT EXISTS idx_settlements_candidate
ON settlements(candidate_id, snapshot_id, settled_at, settlement_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_settlements_terminal_candidate
ON settlements(candidate_id) WHERE result IN ('WON', 'LOST', 'VOID');
"""


_SCHEMA_V3 = _SCHEMA_V2 + """

CREATE TABLE IF NOT EXISTS publication_pointer (
    slot TEXT PRIMARY KEY CHECK (slot = 'latest'),
    run_id TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    run_content_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
"""


def _utc_text(value: datetime, field_name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


def _text(value: object, field_name: str, maximum: int = 500) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(
            f"{field_name} must contain between 1 and {maximum} characters"
        )
    if any(ord(character) < 32 for character in normalized):
        raise ValueError(f"{field_name} contains control characters")
    return normalized


def _digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _publication_pointer_payload(
    run_id: str,
    completed_at: str,
    run_content_hash: str,
) -> dict[str, str]:
    return {
        "slot": "latest",
        "run_id": run_id,
        "completed_at": completed_at,
        "run_content_hash": run_content_hash,
    }


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()}"


def _detail_payload(detail: Optional[Mapping[str, object]]) -> str:
    if detail is None:
        return "{}"
    if not isinstance(detail, Mapping):
        raise ValueError("detail must be a mapping")
    _assert_price_neutral(detail, "detail")
    try:
        return canonical_json(dict(detail))
    except (TypeError, ValueError) as exc:
        raise ValueError("detail must be canonical-JSON serializable") from exc


def _assert_price_neutral(value: object, field_name: str) -> None:
    """Reject bookmaker-price information from the evidence database."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be text")
            _assert_price_neutral(key, field_name)
            _assert_price_neutral(item, field_name)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_price_neutral(item, field_name)
        return
    if isinstance(value, str):
        normalized = value.casefold()
        if any(word in normalized for word in _PRICE_WORDS):
            raise ValueError(f"{field_name} must not contain price information")


def _verified_json(
    payload_json: object,
    content_hash: object,
    identity_label: str,
) -> dict[str, object]:
    if not isinstance(payload_json, str) or not isinstance(content_hash, str):
        raise FrozenRevisionError(f"{identity_label} has invalid stored types")
    if _digest(payload_json) != content_hash:
        raise FrozenRevisionError(f"{identity_label} content hash mismatch")
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise FrozenRevisionError(f"{identity_label} payload is invalid JSON") from exc
    if not isinstance(payload, dict) or canonical_json(payload) != payload_json:
        raise FrozenRevisionError(f"{identity_label} payload is not canonical")
    return payload


def _run_identity_from_payload(payload: Mapping[str, object]) -> str:
    try:
        snapshots = tuple(payload["snapshots"])
        candidates = tuple(payload["candidates"])
        errors = tuple(payload["errors"])
        snapshot_ids = sorted(str(item["snapshot_id"]) for item in snapshots)
        candidate_keys = sorted(
            (str(item["snapshot_id"]), str(item["candidate_id"]))
            for item in candidates
        )
        identity_parts = [
            str(payload["started_at"]),
            str(payload["completed_at"]),
            str(payload["status"]),
            *snapshot_ids,
            *(f"{snapshot_id}:{candidate_id}" for snapshot_id, candidate_id in candidate_keys),
            *(f"error:{error}" for error in errors),
        ]
    except (KeyError, TypeError) as exc:
        raise FrozenRevisionError("run payload is incomplete") from exc
    return _stable_id("run", *identity_parts)


def _legacy_run_identity_from_payload(payload: Mapping[str, object]) -> str:
    try:
        snapshots = tuple(payload["snapshots"])
        candidates = tuple(payload["candidates"])
        snapshot_ids = sorted(str(item["snapshot_id"]) for item in snapshots)
        candidate_keys = sorted(
            (str(item["snapshot_id"]), str(item["candidate_id"]))
            for item in candidates
        )
        identity_parts = [
            str(payload["started_at"]),
            str(payload["completed_at"]),
            str(payload["status"]),
            *snapshot_ids,
            *(f"{snapshot_id}:{candidate_id}" for snapshot_id, candidate_id in candidate_keys),
        ]
    except (KeyError, TypeError) as exc:
        raise FrozenRevisionError("legacy run payload is incomplete") from exc
    return _stable_id("run", *identity_parts)


def _artifact_from_payload(payload: object) -> ValidationEvidenceArtifact:
    if not isinstance(payload, Mapping):
        raise FrozenRevisionError("validation evidence is not an object")
    try:
        return ValidationEvidenceArtifact(**dict(payload))
    except (TypeError, ValueError) as exc:
        raise FrozenRevisionError("validation evidence is invalid") from exc


def validate_latest_document(document: Mapping[str, object]) -> dict[str, object]:
    """Verify and unwrap one digest-bound latest publication.

    The digest detects truncated or silently modified consumer files.  It is
    deliberately not presented as protection against an attacker who can
    rewrite both payload and digest; that requires an external secret.
    """

    if not isinstance(document, Mapping):
        raise FrozenRevisionError("riskobet_latest.json must contain an object")
    payload_digest = document.get("payload_digest")
    if (
        not isinstance(payload_digest, str)
        or len(payload_digest) != 64
        or any(character not in "0123456789abcdef" for character in payload_digest)
    ):
        raise FrozenRevisionError("riskobet_latest.json has no valid payload digest")
    payload = dict(document)
    payload.pop("payload_digest", None)
    if _digest(canonical_json(payload)) != payload_digest:
        raise FrozenRevisionError("riskobet_latest.json payload digest mismatch")
    if payload.get("schema_version") != 1:
        raise FrozenRevisionError("riskobet_latest.json has an unknown schema")
    return payload


def _normalized_sql(sql: object) -> str:
    if not isinstance(sql, str):
        return ""
    return re.sub(r"\s+", " ", sql.strip()).casefold()


def _schema_signature(connection: sqlite3.Connection) -> tuple[object, ...]:
    objects = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    object_signature = tuple(
        (row["type"], row["name"], row["tbl_name"], _normalized_sql(row["sql"]))
        for row in objects
    )
    table_names = tuple(
        row["name"] for row in objects if row["type"] == "table"
    )
    table_details: list[tuple[object, ...]] = []
    for table in table_names:
        columns = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA table_xinfo({json.dumps(table)})"
            ).fetchall()
        )
        foreign_keys = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA foreign_key_list({json.dumps(table)})"
            ).fetchall()
        )
        indexes: list[tuple[object, ...]] = []
        for index in connection.execute(
            f"PRAGMA index_list({json.dumps(table)})"
        ).fetchall():
            index_name = index[1]
            index_columns = tuple(
                tuple(row)
                for row in connection.execute(
                    f"PRAGMA index_xinfo({json.dumps(index_name)})"
                ).fetchall()
            )
            indexes.append(
                (
                    index[2],
                    index[3],
                    index[4],
                    _normalized_sql(
                        connection.execute(
                            "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
                            (index_name,),
                        ).fetchone()[0]
                        if not str(index_name).startswith("sqlite_autoindex_")
                        else None
                    ),
                    index_columns,
                )
            )
        table_details.append(
            (table, columns, foreign_keys, tuple(sorted(indexes, key=repr)))
        )
    return object_signature, tuple(table_details)


def _reference_signature(schema: str) -> tuple[object, ...]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema)
        return _schema_signature(connection)
    finally:
        connection.close()


_V1_SIGNATURE: tuple[object, ...] | None = None
_V2_SIGNATURE: tuple[object, ...] | None = None
_V3_SIGNATURE: tuple[object, ...] | None = None


def _expected_signature(version: int) -> tuple[object, ...]:
    global _V1_SIGNATURE, _V2_SIGNATURE, _V3_SIGNATURE
    if version == 1:
        if _V1_SIGNATURE is None:
            _V1_SIGNATURE = _reference_signature(_SCHEMA_V1)
        return _V1_SIGNATURE
    if version == 2:
        if _V2_SIGNATURE is None:
            _V2_SIGNATURE = _reference_signature(_SCHEMA_V2)
        return _V2_SIGNATURE
    if version == SCHEMA_VERSION:
        if _V3_SIGNATURE is None:
            _V3_SIGNATURE = _reference_signature(_SCHEMA_V3)
        return _V3_SIGNATURE
    raise FrozenRevisionError(f"unsupported RisikoBet schema version: {version}")


class RiskBetStore:
    """Revision-safe store for RisikoBet model output.

    Every public append method is idempotent for byte-equivalent content.  An
    attempt to reuse an existing logical identity with different content is
    rejected instead of updating the frozen revision.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        latest_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        if latest_path is None:
            self.latest_path = (
                DEFAULT_LATEST_PATH
                if self.db_path == DEFAULT_DB_PATH
                else self.db_path.with_name("riskobet_latest.json")
            )
        else:
            self.latest_path = Path(latest_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # V2 -> V3 reads the legacy derived pointer while adding the durable
        # selection.  Use the same cross-process lock as publication so an
        # older service cannot replace that file during the migration.
        with _publication_lock(self.latest_path):
            with closing(self._connect()) as connection:
                self._initialize_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @classmethod
    def recover_latest_from_database(
        cls,
        db_path: str | Path = DEFAULT_DB_PATH,
    ) -> Optional[dict[str, object]]:
        """Recover the selected V3 consumer payload without touching the database.

        This path is intended for backup recovery when ``riskobet_latest.json``
        is absent.  It never creates directories/files, changes journal mode or
        runs a migration.  Any non-V3, foreign or corrupt database fails closed.
        """

        path = Path(db_path)
        if not path.is_file():
            return None
        sidecars = tuple(Path(f"{path}{suffix}") for suffix in ("-wal", "-shm", "-journal"))
        if any(sidecar.exists() for sidecar in sidecars):
            raise FrozenRevisionError(
                "RisikoBet recovery requires a checkpointed standalone database"
            )
        try:
            uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
            connection = sqlite3.connect(uri, uri=True, timeout=5)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise FrozenRevisionError(
                "RisikoBet recovery database cannot be opened read-only"
            ) from exc
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version != SCHEMA_VERSION:
                raise FrozenRevisionError(
                    "RisikoBet recovery requires an existing V3 database"
                )
            cls._assert_exact_schema(connection, SCHEMA_VERSION)
            reader = object.__new__(cls)
            selected = reader._verified_publication_run(connection)
            if selected is None:
                return None
            return reader._consumer_payload(connection, str(selected["run_id"]))
        except sqlite3.Error as exc:
            raise FrozenRevisionError(
                "RisikoBet recovery database could not be validated"
            ) from exc
        finally:
            connection.close()

    @staticmethod
    def _assert_exact_schema(connection: sqlite3.Connection, version: int) -> None:
        if _schema_signature(connection) != _expected_signature(version):
            raise FrozenRevisionError(
                f"RisikoBet database schema {version} is partial or foreign"
            )
        integrity = connection.execute("PRAGMA quick_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise FrozenRevisionError("RisikoBet database failed SQLite integrity check")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise FrozenRevisionError("RisikoBet database has broken foreign keys")

    def _verified_publication_run(
        self,
        connection: sqlite3.Connection,
    ) -> dict[str, object] | None:
        rows = connection.execute(
            "SELECT * FROM publication_pointer ORDER BY slot"
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise FrozenRevisionError("publication pointer is not a singleton")
        row = rows[0]
        if any(
            not isinstance(row[field], str)
            for field in (
                "slot",
                "run_id",
                "completed_at",
                "run_content_hash",
                "content_hash",
            )
        ):
            raise FrozenRevisionError("publication pointer has invalid stored types")
        pointer_payload = _publication_pointer_payload(
            row["run_id"],
            row["completed_at"],
            row["run_content_hash"],
        )
        if row["slot"] != "latest" or _digest(
            canonical_json(pointer_payload)
        ) != row["content_hash"]:
            raise FrozenRevisionError("publication pointer content hash mismatch")
        run_row = connection.execute(
            "SELECT completed_at, content_hash FROM runs WHERE run_id=?",
            (row["run_id"],),
        ).fetchone()
        if run_row is None:
            raise FrozenRevisionError("publication pointer references an unknown run")
        if (
            run_row["completed_at"] != row["completed_at"]
            or run_row["content_hash"] != row["run_content_hash"]
        ):
            raise FrozenRevisionError("publication pointer differs from its run")
        run_payload = self._verified_run_payload(connection, row["run_id"])
        self._verified_frozen_memberships(connection, run_payload)
        return run_payload

    def _set_publication_pointer(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> dict[str, object]:
        run_payload = self._verified_run_payload(connection, run_id)
        self._verified_frozen_memberships(connection, run_payload)
        run_row = connection.execute(
            "SELECT completed_at, content_hash FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if run_row is None:
            raise MissingRevisionError(f"unknown run: {run_id}")
        pointer_payload = _publication_pointer_payload(
            run_id,
            str(run_row["completed_at"]),
            str(run_row["content_hash"]),
        )
        connection.execute(
            """
            INSERT INTO publication_pointer (
                slot, run_id, completed_at, run_content_hash, content_hash
            ) VALUES ('latest', ?, ?, ?, ?)
            ON CONFLICT(slot) DO UPDATE SET
                run_id=excluded.run_id,
                completed_at=excluded.completed_at,
                run_content_hash=excluded.run_content_hash,
                content_hash=excluded.content_hash
            """,
            (
                run_id,
                run_row["completed_at"],
                run_row["content_hash"],
                _digest(canonical_json(pointer_payload)),
            ),
        )
        verified = self._verified_publication_run(connection)
        if verified is None or verified["run_id"] != run_id:
            raise FrozenRevisionError("publication pointer update was not durable")
        return verified

    def _legacy_latest_run_id(
        self,
        run_id_map: Mapping[str, str] | None = None,
    ) -> str | None:
        try:
            payload = self.read_latest()
        except OSError as exc:
            raise FrozenRevisionError(
                "legacy latest publication cannot be read"
            ) from exc
        if payload is None:
            return None
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise FrozenRevisionError("legacy latest publication has no run id")
        return dict(run_id_map or {}).get(run_id, run_id)

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        has_objects = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%' LIMIT 1
            """
        ).fetchone() is not None
        if not has_objects:
            if version != 0:
                raise FrozenRevisionError(
                    "RisikoBet database has a version but no complete schema"
                )
            try:
                connection.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + _SCHEMA_V3
                    + f"\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
                )
            except Exception:
                connection.rollback()
                raise
            self._assert_exact_schema(connection, SCHEMA_VERSION)
            self._verified_publication_run(connection)
            return
        run_id_map: Mapping[str, str] | None = None
        if version in {0, 1}:
            self._assert_exact_schema(connection, 1)
            run_id_map = self._migrate_v1_to_v2(connection)
            version = 2
        if version == 2:
            self._assert_exact_schema(connection, 2)
            self._migrate_v2_to_v3(connection, run_id_map=run_id_map)
            self._assert_exact_schema(connection, SCHEMA_VERSION)
            self._verified_publication_run(connection)
            return
        if version != SCHEMA_VERSION:
            raise FrozenRevisionError(
                f"unsupported RisikoBet database schema version: {version}"
            )
        self._assert_exact_schema(connection, SCHEMA_VERSION)
        self._verified_publication_run(connection)

    def _migrate_v1_to_v2(
        self,
        connection: sqlite3.Connection,
    ) -> dict[str, str]:
        """Validate all V1 data first, then replace the schema atomically."""

        run_rows = connection.execute("SELECT * FROM runs ORDER BY run_id").fetchall()
        snapshot_rows = connection.execute(
            "SELECT * FROM snapshots ORDER BY snapshot_id"
        ).fetchall()
        candidate_rows = connection.execute(
            "SELECT * FROM candidates ORDER BY candidate_id, snapshot_id"
        ).fetchall()
        run_snapshot_rows = connection.execute(
            "SELECT * FROM run_snapshots ORDER BY run_id, ordinal"
        ).fetchall()
        run_candidate_rows = connection.execute(
            "SELECT * FROM run_candidates ORDER BY run_id, ordinal"
        ).fetchall()
        settlement_rows = connection.execute(
            "SELECT * FROM settlements ORDER BY candidate_id, settled_at, settlement_id"
        ).fetchall()
        stage_rows = connection.execute(
            "SELECT * FROM stage_events ORDER BY candidate_id, snapshot_id, occurred_at, stage_event_id"
        ).fetchall()

        snapshots: dict[str, dict[str, object]] = {}
        for row in snapshot_rows:
            payload = _verified_json(
                row["payload_json"], row["content_hash"], f"snapshot {row['snapshot_id']}"
            )
            expected_id = _stable_id(
                "snapshot",
                str(payload.get("event_key")),
                str(payload.get("model_version")),
                str(payload.get("input_hash")),
            )
            if (
                payload.get("snapshot_id") != row["snapshot_id"]
                or expected_id != row["snapshot_id"]
                or payload.get("event_key") != row["event_key"]
                or payload.get("sport") != row["sport"]
                or payload.get("model_version") != row["model_version"]
                or payload.get("input_hash") != row["input_hash"]
                or payload.get("modeled_at") != row["modeled_at"]
            ):
                raise FrozenRevisionError("V1 snapshot columns differ from payload")
            snapshots[row["snapshot_id"]] = payload

        candidates: dict[tuple[str, str], dict[str, object]] = {}
        for row in candidate_rows:
            key = (row["candidate_id"], row["snapshot_id"])
            payload = _verified_json(
                row["payload_json"],
                row["content_hash"],
                f"candidate {row['candidate_id']}/{row['snapshot_id']}",
            )
            expected_id = _stable_id(
                "candidate",
                str(payload.get("event_key")),
                str(payload.get("sport")),
                str(payload.get("market_key")),
                str(payload.get("selection_key")),
                str(payload.get("policy_version")),
            )
            if (
                payload.get("candidate_id") != row["candidate_id"]
                or payload.get("snapshot_id") != row["snapshot_id"]
                or expected_id != row["candidate_id"]
                or payload.get("event_key") != row["event_key"]
                or payload.get("sport") != row["sport"]
                or payload.get("policy_version") != row["policy_version"]
                or payload.get("stage") != row["initial_stage"]
            ):
                raise FrozenRevisionError("V1 candidate columns differ from payload")
            if row["initial_stage"] == EvidenceStage.VALIDATED.value:
                raise FrozenRevisionError(
                    "V1 contains an initially VALIDATED candidate without promotion proof"
                )
            if (
                row["initial_stage"] == EvidenceStage.SHADOW.value
                and not payload.get("settlement_contract")
            ):
                raise FrozenRevisionError("V1 SHADOW candidate has no settlement contract")
            snapshot = snapshots.get(row["snapshot_id"])
            if snapshot is None or (
                snapshot.get("event_key") != payload.get("event_key")
                or snapshot.get("sport") != payload.get("sport")
            ):
                raise FrozenRevisionError("V1 candidate differs from its snapshot")
            candidates[key] = payload

        runs: dict[str, dict[str, object]] = {}
        run_id_map: dict[str, str] = {}
        for row in run_rows:
            payload = _verified_json(
                row["payload_json"], row["content_hash"], f"run {row['run_id']}"
            )
            if (
                payload.get("run_id") != row["run_id"]
                or payload.get("started_at") != row["started_at"]
                or payload.get("completed_at") != row["completed_at"]
                or payload.get("status") != row["status"]
                or _legacy_run_identity_from_payload(payload) != row["run_id"]
            ):
                raise FrozenRevisionError("V1 run identity differs from payload")
            new_payload = dict(payload)
            new_id = _run_identity_from_payload(new_payload)
            new_payload["run_id"] = new_id
            if new_id in runs:
                raise FrozenRevisionError("V1 run migration creates an identity collision")
            runs[new_id] = new_payload
            run_id_map[row["run_id"]] = new_id

        snapshots_by_run: dict[str, list[sqlite3.Row]] = {}
        for row in run_snapshot_rows:
            snapshots_by_run.setdefault(row["run_id"], []).append(row)
        candidates_by_run: dict[str, list[sqlite3.Row]] = {}
        for row in run_candidate_rows:
            if row["featured"] != 0:
                raise FrozenRevisionError("V1 sealed run has mutable featured membership")
            candidates_by_run.setdefault(row["run_id"], []).append(row)

        for old_id, new_id in run_id_map.items():
            payload = runs[new_id]
            stored_snapshots = snapshots_by_run.get(old_id, [])
            stored_candidates = candidates_by_run.get(old_id, [])
            if [row["ordinal"] for row in stored_snapshots] != list(
                range(len(stored_snapshots))
            ) or [row["ordinal"] for row in stored_candidates] != list(
                range(len(stored_candidates))
            ):
                raise FrozenRevisionError("V1 run membership ordinals are not contiguous")
            frozen_snapshots = list(payload.get("snapshots", ()))
            frozen_candidates = list(payload.get("candidates", ()))
            if [row["snapshot_id"] for row in stored_snapshots] != [
                item.get("snapshot_id") for item in frozen_snapshots
            ]:
                raise FrozenRevisionError("V1 run snapshot membership was modified")
            if [
                (row["candidate_id"], row["snapshot_id"])
                for row in stored_candidates
            ] != [
                (item.get("candidate_id"), item.get("snapshot_id"))
                for item in frozen_candidates
            ]:
                raise FrozenRevisionError("V1 run candidate membership was modified")
            for item in frozen_snapshots:
                stored = snapshots.get(str(item.get("snapshot_id")))
                if stored is None or canonical_json(item) != canonical_json(stored):
                    raise FrozenRevisionError("V1 frozen run snapshot content differs")
            for item in frozen_candidates:
                key = (str(item.get("candidate_id")), str(item.get("snapshot_id")))
                stored = candidates.get(key)
                if stored is None or canonical_json(item) != canonical_json(stored):
                    raise FrozenRevisionError("V1 frozen run candidate content differs")

        transformed_stages: list[dict[str, object]] = []
        effective_stage = {
            key: EvidenceStage(str(payload["stage"])) for key, payload in candidates.items()
        }
        stages_by_candidate: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in stage_rows:
            stages_by_candidate.setdefault(
                (row["candidate_id"], row["snapshot_id"]), []
            ).append(row)
        for key, rows in stages_by_candidate.items():
            candidate = candidates.get(key)
            if candidate is None:
                raise FrozenRevisionError("V1 stage event references an unknown candidate")
            current = EvidenceStage(str(candidate["stage"]))
            previous_time: str | None = None
            parent_id: str | None = None
            for row in rows:
                old_payload = {
                    "stage_event_id": row["stage_event_id"],
                    "candidate_id": row["candidate_id"],
                    "snapshot_id": row["snapshot_id"],
                    "from_stage": row["from_stage"],
                    "to_stage": row["to_stage"],
                    "occurred_at": row["occurred_at"],
                    "reason": row["reason"],
                    "validation_version": row["validation_version"],
                }
                if _digest(canonical_json(old_payload)) != row["content_hash"]:
                    raise FrozenRevisionError("V1 stage event content hash mismatch")
                from_stage = EvidenceStage(row["from_stage"])
                to_stage = EvidenceStage(row["to_stage"])
                if (from_stage, to_stage) not in _ALLOWED_STAGE_TRANSITIONS:
                    raise FrozenRevisionError("V1 stage transition is illegal")
                if from_stage is not current:
                    raise FrozenRevisionError("V1 stage chain is discontinuous")
                if previous_time is not None and row["occurred_at"] <= previous_time:
                    raise FrozenRevisionError("V1 stage timestamps are not strictly ordered")
                _assert_price_neutral(row["reason"], "reason")
                if to_stage is EvidenceStage.VALIDATED:
                    raise FrozenRevisionError(
                        "V1 VALIDATED transition has no structured validation evidence"
                    )
                if not candidate.get("settlement_contract"):
                    raise FrozenRevisionError(
                        "V1 RESEARCH to SHADOW transition has no settlement contract"
                    )
                if candidate.get("model_probability") is None:
                    raise FrozenRevisionError(
                        "V1 RESEARCH to SHADOW transition has no model probability"
                    )
                if row["occurred_at"] >= str(candidate["starts_at"]):
                    raise FrozenRevisionError("V1 SHADOW transition was not prospective")
                new_id = _stable_id(
                    "stage",
                    key[0],
                    key[1],
                    parent_id or "",
                    from_stage.value,
                    to_stage.value,
                    row["validation_version"],
                    row["occurred_at"],
                )
                new_payload = {
                    "stage_event_id": new_id,
                    "candidate_id": key[0],
                    "snapshot_id": key[1],
                    "parent_stage_event_id": parent_id,
                    "from_stage": from_stage.value,
                    "to_stage": to_stage.value,
                    "occurred_at": row["occurred_at"],
                    "reason": row["reason"],
                    "validation_version": row["validation_version"],
                    "evidence": {},
                }
                transformed_stages.append(new_payload)
                current = to_stage
                effective_stage[key] = current
                previous_time = row["occurred_at"]
                parent_id = new_id

        prospective_revisions: dict[str, list[tuple[str, str, str]]] = {}
        run_completed = {
            old_id: str(runs[new_id]["completed_at"])
            for old_id, new_id in run_id_map.items()
        }
        for row in run_candidate_rows:
            key = (row["candidate_id"], row["snapshot_id"])
            candidate = candidates[key]
            snapshot = snapshots[row["snapshot_id"]]
            if run_completed[row["run_id"]] <= str(candidate["starts_at"]):
                prospective_revisions.setdefault(row["candidate_id"], []).append(
                    (
                        str(snapshot["modeled_at"]),
                        str(snapshot["input_cutoff_at"]),
                        row["snapshot_id"],
                    )
                )
        newest_revision = {
            candidate_id: max(revisions)[2]
            for candidate_id, revisions in prospective_revisions.items()
        }

        transformed_settlements: list[dict[str, object]] = []
        terminal_candidates: set[str] = set()
        for row in settlement_rows:
            old_payload = {
                "settlement_id": row["settlement_id"],
                "candidate_id": row["candidate_id"],
                "snapshot_id": row["snapshot_id"],
                "settlement_version": row["settlement_version"],
                "result": row["result"],
                "settled_at": row["settled_at"],
                "detail": json.loads(row["detail_json"]),
            }
            if _digest(canonical_json(old_payload)) != row["content_hash"]:
                raise FrozenRevisionError("V1 settlement content hash mismatch")
            key = (row["candidate_id"], row["snapshot_id"])
            candidate = candidates.get(key)
            if candidate is None or effective_stage.get(key) not in {
                EvidenceStage.SHADOW,
                EvidenceStage.VALIDATED,
            }:
                raise FrozenRevisionError("V1 settlement is not bound to SHADOW evidence")
            contract = candidate.get("settlement_contract")
            if not contract or row["settlement_version"] != contract:
                raise FrozenRevisionError("V1 settlement contract differs from candidate")
            if row["settled_at"] < str(candidate["starts_at"]):
                raise FrozenRevisionError("V1 settlement predates the event")
            if newest_revision.get(row["candidate_id"]) != row["snapshot_id"]:
                raise FrozenRevisionError("V1 settlement uses a superseded snapshot")
            if row["result"] not in SETTLEMENT_RESULTS:
                raise FrozenRevisionError("V1 settlement result cannot be migrated")
            detail = json.loads(row["detail_json"])
            _assert_price_neutral(detail, "detail")
            if row["result"] in _FINAL_SETTLEMENT_RESULTS:
                if row["candidate_id"] in terminal_candidates:
                    raise FrozenRevisionError("V1 has duplicate terminal settlements")
                terminal_candidates.add(row["candidate_id"])
            new_id = _stable_id(
                "settlement",
                row["candidate_id"],
                row["snapshot_id"],
                row["settlement_version"],
                row["settled_at"],
            )
            transformed_settlements.append(
                {
                    "settlement_id": new_id,
                    "candidate_id": row["candidate_id"],
                    "snapshot_id": row["snapshot_id"],
                    "settlement_version": row["settlement_version"],
                    "result": row["result"],
                    "settled_at": row["settled_at"],
                    "detail": detail,
                }
            )

        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for table in (
                "stage_events",
                "settlements",
                "run_candidates",
                "run_snapshots",
                "candidates",
                "snapshots",
                "runs",
            ):
                connection.execute(f"DROP TABLE {table}")
            for statement in _SCHEMA_V2.split(";"):
                if statement.strip():
                    connection.execute(statement)
            for new_id, payload in runs.items():
                payload_json = canonical_json(payload)
                connection.execute(
                    "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        new_id,
                        payload["started_at"],
                        payload["completed_at"],
                        payload["status"],
                        payload_json,
                        _digest(payload_json),
                    ),
                )
            for row in snapshot_rows:
                connection.execute(
                    "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(row),
                )
            for row in candidate_rows:
                connection.execute(
                    "INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(row),
                )
            for row in run_snapshot_rows:
                connection.execute(
                    "INSERT INTO run_snapshots VALUES (?, ?, ?)",
                    (run_id_map[row["run_id"]], row["snapshot_id"], row["ordinal"]),
                )
            for row in run_candidate_rows:
                connection.execute(
                    "INSERT INTO run_candidates VALUES (?, ?, ?, ?, ?)",
                    (
                        run_id_map[row["run_id"]],
                        row["candidate_id"],
                        row["snapshot_id"],
                        row["ordinal"],
                        row["featured"],
                    ),
                )
            for payload in transformed_settlements:
                detail_json = canonical_json(payload["detail"])
                stored_payload = canonical_json(payload)
                connection.execute(
                    "INSERT INTO settlements VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        payload["settlement_id"],
                        payload["candidate_id"],
                        payload["snapshot_id"],
                        payload["settlement_version"],
                        payload["result"],
                        payload["settled_at"],
                        detail_json,
                        _digest(stored_payload),
                    ),
                )
            for payload in transformed_stages:
                evidence_json = canonical_json(payload["evidence"])
                stored_payload = canonical_json(payload)
                connection.execute(
                    """
                    INSERT INTO stage_events (
                        stage_event_id, candidate_id, snapshot_id,
                        parent_stage_event_id, from_stage, to_stage,
                        occurred_at, reason, validation_version,
                        evidence_json, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["stage_event_id"],
                        payload["candidate_id"],
                        payload["snapshot_id"],
                        payload["parent_stage_event_id"],
                        payload["from_stage"],
                        payload["to_stage"],
                        payload["occurred_at"],
                        payload["reason"],
                        payload["validation_version"],
                        evidence_json,
                        _digest(stored_payload),
                    ),
                )
            connection.execute("PRAGMA user_version = 2")
            violation = connection.execute("PRAGMA foreign_key_check").fetchone()
            if violation is not None:
                raise FrozenRevisionError("V1 migration created a broken foreign key")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
        return run_id_map

    def _migrate_v2_to_v3(
        self,
        connection: sqlite3.Connection,
        *,
        run_id_map: Mapping[str, str] | None = None,
    ) -> None:
        """Add a durable publication selection without guessing from run order."""

        selected_run_id = self._legacy_latest_run_id(run_id_map)
        if selected_run_id is not None:
            run_payload = self._verified_run_payload(connection, selected_run_id)
            self._verified_frozen_memberships(connection, run_payload)

        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_pointer (
                    slot TEXT PRIMARY KEY CHECK (slot = 'latest'),
                    run_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    run_content_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
                """
            )
            if selected_run_id is not None:
                self._set_publication_pointer(connection, selected_run_id)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            violation = connection.execute("PRAGMA foreign_key_check").fetchone()
            if violation is not None:
                raise FrozenRevisionError(
                    "V2 publication migration created a broken foreign key"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @staticmethod
    def _insert_immutable(
        connection: sqlite3.Connection,
        *,
        insert_sql: str,
        values: tuple[object, ...],
        select_sql: str,
        select_values: tuple[object, ...],
        expected_hash: str,
        identity_label: str,
    ) -> bool:
        cursor = connection.execute(insert_sql, values)
        if cursor.rowcount == 1:
            return True
        row = connection.execute(select_sql, select_values).fetchone()
        if row is None:
            raise FrozenRevisionError(
                f"{identity_label} collided with another immutable identity"
            )
        if row["content_hash"] != expected_hash:
            raise FrozenRevisionError(
                f"{identity_label} already exists with different content"
            )
        return False

    @staticmethod
    def _assert_run(connection: sqlite3.Connection, run_id: str) -> None:
        if connection.execute(
            "SELECT 1 FROM runs WHERE run_id=?", (run_id,)
        ).fetchone() is None:
            raise MissingRevisionError(f"unknown run: {run_id}")

    @staticmethod
    def _assert_candidate(
        connection: sqlite3.Connection,
        candidate_id: str,
        snapshot_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT initial_stage, payload_json, content_hash FROM candidates
            WHERE candidate_id=? AND snapshot_id=?
            """,
            (candidate_id, snapshot_id),
        ).fetchone()
        if row is None:
            raise MissingRevisionError(
                f"unknown candidate revision: {candidate_id}/{snapshot_id}"
            )
        payload = _verified_json(
            row["payload_json"],
            row["content_hash"],
            f"candidate {candidate_id}/{snapshot_id}",
        )
        if (
            payload.get("candidate_id") != candidate_id
            or payload.get("snapshot_id") != snapshot_id
            or payload.get("stage") != row["initial_stage"]
        ):
            raise FrozenRevisionError("candidate columns differ from frozen payload")
        return row

    def _append_run_row(
        self,
        connection: sqlite3.Connection,
        run: RiskRunSnapshot,
    ) -> bool:
        payload = canonical_json(run.to_dict())
        content_hash = _digest(payload)
        return self._insert_immutable(
            connection,
            insert_sql="""
                INSERT OR IGNORE INTO runs (
                    run_id, started_at, completed_at, status,
                    payload_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            values=(
                run.run_id,
                _utc_text(run.started_at, "started_at"),
                _utc_text(run.completed_at, "completed_at"),
                run.status.value,
                payload,
                content_hash,
            ),
            select_sql="SELECT content_hash FROM runs WHERE run_id=?",
            select_values=(run.run_id,),
            expected_hash=content_hash,
            identity_label=f"run {run.run_id}",
        )

    def _append_snapshot_row(
        self,
        connection: sqlite3.Connection,
        snapshot: EventModelSnapshot,
    ) -> bool:
        payload = canonical_json(snapshot.to_dict())
        content_hash = _digest(payload)
        return self._insert_immutable(
            connection,
            insert_sql="""
                INSERT OR IGNORE INTO snapshots (
                    snapshot_id, event_key, sport, model_version, input_hash,
                    modeled_at, payload_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values=(
                snapshot.snapshot_id,
                snapshot.event_key,
                snapshot.sport,
                snapshot.model_version,
                snapshot.input_hash,
                _utc_text(snapshot.modeled_at, "modeled_at"),
                payload,
                content_hash,
            ),
            select_sql="""
                SELECT content_hash FROM snapshots
                WHERE event_key=? AND model_version=? AND input_hash=?
            """,
            select_values=(
                snapshot.event_key,
                snapshot.model_version,
                snapshot.input_hash,
            ),
            expected_hash=content_hash,
            identity_label=(
                f"snapshot {snapshot.event_key}/"
                f"{snapshot.model_version}/{snapshot.input_hash}"
            ),
        )

    def _append_candidate_row(
        self,
        connection: sqlite3.Connection,
        candidate: RiskCandidate,
    ) -> bool:
        if candidate.stage is EvidenceStage.VALIDATED:
            raise FrozenRevisionError(
                "VALIDATED candidates must enter through a SHADOW promotion"
            )
        snapshot = connection.execute(
            "SELECT event_key, sport FROM snapshots WHERE snapshot_id=?",
            (candidate.snapshot_id,),
        ).fetchone()
        if snapshot is None:
            raise MissingRevisionError(f"unknown snapshot: {candidate.snapshot_id}")
        if (
            snapshot["event_key"] != candidate.event_key
            or snapshot["sport"] != candidate.sport
        ):
            raise FrozenRevisionError("candidate identity differs from its snapshot")
        payload = canonical_json(candidate.to_dict())
        content_hash = _digest(payload)
        return self._insert_immutable(
            connection,
            insert_sql="""
                INSERT OR IGNORE INTO candidates (
                    candidate_id, snapshot_id, event_key, sport,
                    policy_version, initial_stage, payload_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values=(
                candidate.candidate_id,
                candidate.snapshot_id,
                candidate.event_key,
                candidate.sport,
                candidate.policy_version,
                candidate.stage.value,
                payload,
                content_hash,
            ),
            select_sql="""
                SELECT content_hash FROM candidates
                WHERE candidate_id=? AND snapshot_id=?
            """,
            select_values=(candidate.candidate_id, candidate.snapshot_id),
            expected_hash=content_hash,
            identity_label=(
                f"candidate {candidate.candidate_id}/{candidate.snapshot_id}"
            ),
        )

    @staticmethod
    def _append_membership(
        connection: sqlite3.Connection,
        *,
        table: str,
        columns: tuple[str, ...],
        values: tuple[object, ...],
        identity_columns: tuple[str, ...],
    ) -> bool:
        placeholders = ", ".join("?" for _ in values)
        cursor = connection.execute(
            f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) "
            f"VALUES ({placeholders})",
            values,
        )
        if cursor.rowcount == 1:
            return True
        identity_indexes = [columns.index(column) for column in identity_columns]
        where = " AND ".join(f"{column}=?" for column in identity_columns)
        row = connection.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE {where}",
            tuple(values[index] for index in identity_indexes),
        ).fetchone()
        if row is None or tuple(row[column] for column in columns) != values:
            raise FrozenRevisionError(f"{table} membership is immutable")
        return False

    @staticmethod
    def _verified_run_payload(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> dict[str, object]:
        row = connection.execute(
            "SELECT * FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise MissingRevisionError(f"unknown run: {run_id}")
        payload = _verified_json(row["payload_json"], row["content_hash"], f"run {run_id}")
        if (
            payload.get("run_id") != run_id
            or payload.get("started_at") != row["started_at"]
            or payload.get("completed_at") != row["completed_at"]
            or payload.get("status") != row["status"]
            or _run_identity_from_payload(payload) != run_id
        ):
            raise FrozenRevisionError("run columns or identity differ from payload")
        return payload

    @staticmethod
    def _verified_snapshot_row(row: sqlite3.Row) -> dict[str, object]:
        payload = _verified_json(
            row["payload_json"], row["content_hash"], f"snapshot {row['snapshot_id']}"
        )
        expected_id = _stable_id(
            "snapshot",
            str(payload.get("event_key")),
            str(payload.get("model_version")),
            str(payload.get("input_hash")),
        )
        if (
            payload.get("snapshot_id") != row["snapshot_id"]
            or expected_id != row["snapshot_id"]
            or payload.get("event_key") != row["event_key"]
            or payload.get("sport") != row["sport"]
            or payload.get("model_version") != row["model_version"]
            or payload.get("input_hash") != row["input_hash"]
            or payload.get("modeled_at") != row["modeled_at"]
        ):
            raise FrozenRevisionError("snapshot columns or identity differ from payload")
        return payload

    @staticmethod
    def _verified_candidate_row(row: sqlite3.Row) -> dict[str, object]:
        payload = _verified_json(
            row["payload_json"],
            row["content_hash"],
            f"candidate {row['candidate_id']}/{row['snapshot_id']}",
        )
        expected_id = _stable_id(
            "candidate",
            str(payload.get("event_key")),
            str(payload.get("sport")),
            str(payload.get("market_key")),
            str(payload.get("selection_key")),
            str(payload.get("policy_version")),
        )
        if (
            payload.get("candidate_id") != row["candidate_id"]
            or payload.get("snapshot_id") != row["snapshot_id"]
            or expected_id != row["candidate_id"]
            or payload.get("event_key") != row["event_key"]
            or payload.get("sport") != row["sport"]
            or payload.get("policy_version") != row["policy_version"]
            or payload.get("stage") != row["initial_stage"]
        ):
            raise FrozenRevisionError("candidate columns or identity differ from payload")
        if row["initial_stage"] == EvidenceStage.VALIDATED.value:
            raise FrozenRevisionError("candidate was stored as initially VALIDATED")
        return payload

    def _verified_frozen_memberships(
        self,
        connection: sqlite3.Connection,
        run_payload: Mapping[str, object],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        run_id = str(run_payload["run_id"])
        snapshot_rows = connection.execute(
            """
            SELECT s.*, rs.ordinal
            FROM run_snapshots rs
            JOIN snapshots s ON s.snapshot_id=rs.snapshot_id
            WHERE rs.run_id=? ORDER BY rs.ordinal
            """,
            (run_id,),
        ).fetchall()
        candidate_rows = connection.execute(
            """
            SELECT c.*, rc.ordinal, rc.featured
            FROM run_candidates rc
            JOIN candidates c
              ON c.candidate_id=rc.candidate_id
             AND c.snapshot_id=rc.snapshot_id
            WHERE rc.run_id=? ORDER BY rc.ordinal
            """,
            (run_id,),
        ).fetchall()
        if [row["ordinal"] for row in snapshot_rows] != list(range(len(snapshot_rows))):
            raise FrozenRevisionError("run snapshot ordinals are not contiguous")
        if [row["ordinal"] for row in candidate_rows] != list(range(len(candidate_rows))):
            raise FrozenRevisionError("run candidate ordinals are not contiguous")
        if any(row["featured"] != 0 for row in candidate_rows):
            raise FrozenRevisionError("sealed run membership contains mutable featured state")
        snapshots = [self._verified_snapshot_row(row) for row in snapshot_rows]
        candidates = [self._verified_candidate_row(row) for row in candidate_rows]
        frozen_snapshots = run_payload.get("snapshots")
        frozen_candidates = run_payload.get("candidates")
        if not isinstance(frozen_snapshots, list) or not isinstance(frozen_candidates, list):
            raise FrozenRevisionError("run membership payload is malformed")
        if canonical_json({"items": snapshots}) != canonical_json(
            {"items": frozen_snapshots}
        ):
            raise FrozenRevisionError("run snapshot membership differs from frozen run")
        if canonical_json({"items": candidates}) != canonical_json(
            {"items": frozen_candidates}
        ):
            raise FrozenRevisionError("run candidate membership differs from frozen run")
        return snapshots, candidates

    def append_run(self, run: RiskRunSnapshot) -> bool:
        """Atomically append a run and all of its immutable revisions."""

        if not isinstance(run, RiskRunSnapshot):
            raise TypeError("run must be a RiskRunSnapshot")
        if any(candidate.stage is EvidenceStage.VALIDATED for candidate in run.candidates):
            raise FrozenRevisionError(
                "VALIDATED candidates must enter through a SHADOW promotion"
            )
        if any(
            candidate.stage is EvidenceStage.SHADOW
            and run.completed_at >= candidate.starts_at
            for candidate in run.candidates
        ):
            raise FrozenRevisionError("SHADOW candidates must be stored before event start")
        inserted = False
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                inserted = self._append_run_row(connection, run)
                if not inserted:
                    stored_run = self._verified_run_payload(connection, run.run_id)
                    self._verified_frozen_memberships(connection, stored_run)
                    if canonical_json(stored_run) != canonical_json(run.to_dict()):
                        raise FrozenRevisionError(
                            "run identity already exists with different frozen content"
                        )
                    connection.commit()
                    return False
                for ordinal, snapshot in enumerate(run.snapshots):
                    inserted = self._append_snapshot_row(connection, snapshot) or inserted
                    inserted = self._append_membership(
                        connection,
                        table="run_snapshots",
                        columns=("run_id", "snapshot_id", "ordinal"),
                        values=(run.run_id, snapshot.snapshot_id, ordinal),
                        identity_columns=("run_id", "snapshot_id"),
                    ) or inserted
                for ordinal, candidate in enumerate(run.candidates):
                    inserted = self._append_candidate_row(connection, candidate) or inserted
                    inserted = self._append_membership(
                        connection,
                        table="run_candidates",
                        columns=(
                            "run_id",
                            "candidate_id",
                            "snapshot_id",
                            "ordinal",
                            "featured",
                        ),
                        values=(
                            run.run_id,
                            candidate.candidate_id,
                            candidate.snapshot_id,
                            ordinal,
                            0,
                        ),
                        identity_columns=("run_id", "candidate_id", "snapshot_id"),
                    ) or inserted
                stored_run = self._verified_run_payload(connection, run.run_id)
                self._verified_frozen_memberships(connection, stored_run)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return inserted

    def append_snapshot(
        self,
        snapshot: EventModelSnapshot,
        run_id: str,
        *,
        ordinal: int = 0,
    ) -> bool:
        """Validate an existing frozen snapshot membership idempotently."""

        if not isinstance(snapshot, EventModelSnapshot):
            raise TypeError("snapshot must be an EventModelSnapshot")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise ValueError("ordinal must be a non-negative integer")
        run_id = _text(run_id, "run_id", 100)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run_payload = self._verified_run_payload(connection, run_id)
                self._verified_frozen_memberships(connection, run_payload)
                frozen = run_payload["snapshots"]
                if ordinal >= len(frozen) or canonical_json(frozen[ordinal]) != canonical_json(
                    snapshot.to_dict()
                ):
                    raise FrozenRevisionError(
                        "run is sealed; snapshot membership cannot be changed"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return False

    def append_candidate(
        self,
        candidate: RiskCandidate,
        run_id: str,
        *,
        ordinal: int = 0,
        featured: bool = False,
    ) -> bool:
        """Validate an existing frozen candidate membership idempotently."""

        if not isinstance(candidate, RiskCandidate):
            raise TypeError("candidate must be a RiskCandidate")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise ValueError("ordinal must be a non-negative integer")
        if not isinstance(featured, bool):
            raise ValueError("featured must be a boolean")
        if featured:
            raise FrozenRevisionError("featured state is presentation-only")
        run_id = _text(run_id, "run_id", 100)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run_payload = self._verified_run_payload(connection, run_id)
                self._verified_frozen_memberships(connection, run_payload)
                frozen = run_payload["candidates"]
                if ordinal >= len(frozen) or canonical_json(frozen[ordinal]) != canonical_json(
                    candidate.to_dict()
                ):
                    raise FrozenRevisionError(
                        "run is sealed; candidate membership cannot be changed"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return False

    @staticmethod
    def _validate_promotion_evidence(
        artifact: ValidationEvidenceArtifact,
        *,
        candidate: Mapping[str, object],
        snapshot: Mapping[str, object],
        validation_version: str,
    ) -> None:
        if artifact.validation_version != validation_version:
            raise FrozenRevisionError("validation evidence version mismatch")
        if artifact.policy_version != candidate.get("policy_version"):
            raise FrozenRevisionError("validation evidence policy mismatch")
        if artifact.model_version != snapshot.get("model_version"):
            raise FrozenRevisionError("validation evidence model mismatch")
        if artifact.settlement_contract != candidate.get("settlement_contract"):
            raise FrozenRevisionError("validation evidence settlement mismatch")
        if candidate.get("sport") == "esports" and artifact.esports_patch_periods < 2:
            raise FrozenRevisionError(
                "e-sport validation requires at least two patch periods"
            )

    def _verified_stage_history(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
        snapshot_id: str,
        *,
        candidate: Optional[Mapping[str, object]] = None,
    ) -> tuple[list[dict[str, object]], EvidenceStage, str | None, str | None]:
        if candidate is None:
            candidate_row = self._assert_candidate(connection, candidate_id, snapshot_id)
            candidate = _verified_json(
                candidate_row["payload_json"],
                candidate_row["content_hash"],
                f"candidate {candidate_id}/{snapshot_id}",
            )
        snapshot_row = connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        if snapshot_row is None:
            raise MissingRevisionError(f"unknown snapshot: {snapshot_id}")
        snapshot = self._verified_snapshot_row(snapshot_row)
        rows = connection.execute(
            """
            SELECT * FROM stage_events
            WHERE candidate_id=? AND snapshot_id=?
            ORDER BY occurred_at, stage_event_id
            """,
            (candidate_id, snapshot_id),
        ).fetchall()
        current = EvidenceStage(str(candidate["stage"]))
        if current is EvidenceStage.VALIDATED:
            raise FrozenRevisionError("candidate was stored as initially VALIDATED")
        history: list[dict[str, object]] = []
        parent_id: str | None = None
        previous_time: str | None = None
        for row in rows:
            try:
                evidence = json.loads(row["evidence_json"])
            except json.JSONDecodeError as exc:
                raise FrozenRevisionError("stage evidence is invalid JSON") from exc
            payload = {
                "stage_event_id": row["stage_event_id"],
                "candidate_id": row["candidate_id"],
                "snapshot_id": row["snapshot_id"],
                "parent_stage_event_id": row["parent_stage_event_id"],
                "from_stage": row["from_stage"],
                "to_stage": row["to_stage"],
                "occurred_at": row["occurred_at"],
                "reason": row["reason"],
                "validation_version": row["validation_version"],
                "evidence": evidence,
            }
            if _digest(canonical_json(payload)) != row["content_hash"]:
                raise FrozenRevisionError("stage event content hash mismatch")
            if row["parent_stage_event_id"] != parent_id:
                raise FrozenRevisionError("stage event parent chain is broken")
            if previous_time is not None and row["occurred_at"] <= previous_time:
                raise FrozenRevisionError("stage transition time must be strictly increasing")
            from_stage = EvidenceStage(row["from_stage"])
            to_stage = EvidenceStage(row["to_stage"])
            if (from_stage, to_stage) not in _ALLOWED_STAGE_TRANSITIONS:
                raise FrozenRevisionError("stored stage transition is illegal")
            if from_stage is not current:
                raise FrozenRevisionError("stored stage chain is discontinuous")
            _assert_price_neutral(row["reason"], "reason")
            if to_stage is EvidenceStage.SHADOW:
                if evidence not in ({}, None):
                    raise FrozenRevisionError("SHADOW transition has unexpected evidence")
                if not candidate.get("settlement_contract"):
                    raise FrozenRevisionError("SHADOW transition has no settlement contract")
                if candidate.get("model_probability") is None:
                    raise FrozenRevisionError("SHADOW transition has no model probability")
                if row["occurred_at"] >= str(candidate["starts_at"]):
                    raise FrozenRevisionError("SHADOW transition was not prospective")
            else:
                artifact = _artifact_from_payload(evidence)
                self._validate_promotion_evidence(
                    artifact,
                    candidate=candidate,
                    snapshot=snapshot,
                    validation_version=row["validation_version"],
                )
            history.append(payload)
            current = to_stage
            parent_id = row["stage_event_id"]
            previous_time = row["occurred_at"]
        return history, current, parent_id, previous_time

    def _verified_settlement_rows(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
        *,
        snapshot_id: str | None = None,
    ) -> list[dict[str, object]]:
        parameters: tuple[object, ...]
        if snapshot_id is None:
            where = "candidate_id=?"
            parameters = (candidate_id,)
        else:
            where = "candidate_id=? AND snapshot_id=?"
            parameters = (candidate_id, snapshot_id)
        rows = connection.execute(
            f"SELECT * FROM settlements WHERE {where} "
            "ORDER BY settled_at, settlement_id",
            parameters,
        ).fetchall()
        verified: list[dict[str, object]] = []
        terminal_count = 0
        for row in rows:
            candidate_row = connection.execute(
                "SELECT * FROM candidates WHERE candidate_id=? AND snapshot_id=?",
                (row["candidate_id"], row["snapshot_id"]),
            ).fetchone()
            if candidate_row is None:
                raise FrozenRevisionError("settlement references an unknown candidate")
            candidate = self._verified_candidate_row(candidate_row)
            try:
                detail = json.loads(row["detail_json"])
            except json.JSONDecodeError as exc:
                raise FrozenRevisionError("settlement detail is invalid JSON") from exc
            if not isinstance(detail, Mapping) or canonical_json(detail) != row["detail_json"]:
                raise FrozenRevisionError("settlement detail is not canonical")
            _assert_price_neutral(detail, "detail")
            payload = {
                "settlement_id": row["settlement_id"],
                "candidate_id": row["candidate_id"],
                "snapshot_id": row["snapshot_id"],
                "settlement_version": row["settlement_version"],
                "result": row["result"],
                "settled_at": row["settled_at"],
                "detail": dict(detail),
            }
            if _digest(canonical_json(payload)) != row["content_hash"]:
                raise FrozenRevisionError("settlement content hash mismatch")
            if row["settlement_version"] != candidate.get("settlement_contract"):
                raise FrozenRevisionError("settlement is detached from candidate contract")
            if row["settled_at"] < str(candidate["starts_at"]):
                raise FrozenRevisionError("settlement predates event start")
            if row["result"] in _FINAL_SETTLEMENT_RESULTS:
                terminal_count += 1
            verified.append(payload)
        if terminal_count > 1:
            raise FrozenRevisionError("candidate has duplicate terminal settlements")
        return verified

    def _settleable_revisions(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
    ) -> list[dict[str, object]]:
        revisions: list[dict[str, object]] = []
        rows = connection.execute(
            "SELECT * FROM candidates WHERE candidate_id=? ORDER BY snapshot_id",
            (candidate_id,),
        ).fetchall()
        verified_runs: dict[str, Mapping[str, object]] = {}
        for row in rows:
            candidate = self._verified_candidate_row(row)
            snapshot_row = connection.execute(
                "SELECT * FROM snapshots WHERE snapshot_id=?",
                (candidate["snapshot_id"],),
            ).fetchone()
            if snapshot_row is None:
                raise FrozenRevisionError("candidate snapshot is missing")
            snapshot = self._verified_snapshot_row(snapshot_row)
            if (
                snapshot.get("event_key") != candidate.get("event_key")
                or snapshot.get("sport") != candidate.get("sport")
            ):
                raise FrozenRevisionError("candidate identity differs from its snapshot")
            stage_history, current_stage, _, _ = self._verified_stage_history(
                connection,
                candidate_id,
                str(candidate["snapshot_id"]),
                candidate=candidate,
            )
            if current_stage not in {EvidenceStage.SHADOW, EvidenceStage.VALIDATED}:
                continue
            memberships = connection.execute(
                "SELECT run_id FROM run_candidates "
                "WHERE candidate_id=? AND snapshot_id=? ORDER BY run_id",
                (candidate_id, candidate["snapshot_id"]),
            ).fetchall()
            prospective_run_ids: list[str] = []
            for membership in memberships:
                run_id = str(membership["run_id"])
                run_payload = verified_runs.get(run_id)
                if run_payload is None:
                    run_payload = self._verified_run_payload(connection, run_id)
                    self._verified_frozen_memberships(connection, run_payload)
                    verified_runs[run_id] = run_payload
                if str(run_payload["completed_at"]) < str(candidate["starts_at"]):
                    prospective_run_ids.append(run_id)
            if not prospective_run_ids:
                continue
            revisions.append(
                {
                    "candidate": candidate,
                    "snapshot": snapshot,
                    "stage": current_stage,
                    "stage_history": stage_history,
                    "prospective_run_ids": tuple(prospective_run_ids),
                    "logical_time": (
                        str(snapshot["modeled_at"]),
                        str(snapshot["input_cutoff_at"]),
                    ),
                }
            )
        return revisions

    def _newest_settleable_revision(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
    ) -> dict[str, object] | None:
        revisions = self._settleable_revisions(connection, candidate_id)
        if not revisions:
            return None
        newest_time = max(revision["logical_time"] for revision in revisions)
        newest = [
            revision for revision in revisions if revision["logical_time"] == newest_time
        ]
        snapshot_ids = {
            str(revision["candidate"]["snapshot_id"])  # type: ignore[index]
            for revision in newest
        }
        if len(snapshot_ids) != 1:
            raise _AmbiguousSettleableRevisionError(
                "candidate has ambiguous equal-time settleable revisions",
                starts_at=(
                    str(revision["candidate"]["starts_at"])  # type: ignore[index]
                    for revision in newest
                ),
            )
        return newest[0]

    def load_due_settlement_targets_with_issues(
        self,
        *,
        as_of: datetime,
    ) -> tuple[tuple[dict[str, object], ...], int]:
        """Load settleable revisions and isolate ambiguous candidate histories.

        Results are fully verified through their run memberships, current
        stage chains and global terminal-settlement uniqueness.  A newer
        RESEARCH-only revision never masks an older settleable revision.  An
        equal-time ambiguity stays unselected for that candidate, while every
        other integrity error still aborts the store-wide read.
        """

        as_of_text = _utc_text(as_of, "as_of")
        targets: list[dict[str, object]] = []
        ambiguous_count = 0
        with closing(self._connect()) as connection:
            candidate_ids = [
                str(row["candidate_id"])
                for row in connection.execute(
                    "SELECT DISTINCT candidate_id FROM candidates ORDER BY candidate_id"
                ).fetchall()
            ]
            for candidate_id in candidate_ids:
                settlements = self._verified_settlement_rows(
                    connection,
                    candidate_id,
                )
                if any(
                    settlement["result"] in _FINAL_SETTLEMENT_RESULTS
                    for settlement in settlements
                ):
                    continue
                try:
                    revision = self._newest_settleable_revision(
                        connection,
                        candidate_id,
                    )
                except _AmbiguousSettleableRevisionError as exc:
                    if any(starts_at <= as_of_text for starts_at in exc.starts_at):
                        ambiguous_count += 1
                    continue
                if revision is None:
                    continue
                candidate = dict(revision["candidate"])  # type: ignore[arg-type]
                if str(candidate["starts_at"]) > as_of_text:
                    continue
                candidate["stage"] = revision["stage"].value  # type: ignore[union-attr]
                candidate["stage_history"] = revision["stage_history"]
                candidate["settlements"] = [
                    {
                        "settlement_id": settlement["settlement_id"],
                        "settlement_version": settlement["settlement_version"],
                        "result": settlement["result"],
                        "settled_at": settlement["settled_at"],
                        "detail": settlement["detail"],
                    }
                    for settlement in settlements
                    if settlement["snapshot_id"] == candidate["snapshot_id"]
                ]
                targets.append(
                    {
                        "candidate": candidate,
                        "snapshot": dict(revision["snapshot"]),  # type: ignore[arg-type]
                        "prospective_run_ids": list(
                            revision["prospective_run_ids"]  # type: ignore[arg-type]
                        ),
                    }
                )
        ordered = tuple(
            sorted(
                targets,
                key=lambda target: (
                    str(target["candidate"]["starts_at"]),  # type: ignore[index]
                    str(target["candidate"]["sport"]),  # type: ignore[index]
                    str(target["candidate"]["candidate_id"]),  # type: ignore[index]
                ),
            )
        )
        return ordered, ambiguous_count

    def load_due_settlement_targets(
        self,
        *,
        as_of: datetime,
    ) -> tuple[dict[str, object], ...]:
        """Load unambiguous newest prospective SHADOW/VALIDATED revisions."""

        targets, ambiguous_count = self.load_due_settlement_targets_with_issues(
            as_of=as_of
        )
        if ambiguous_count:
            raise FrozenRevisionError(
                "candidate has ambiguous equal-time settleable revisions"
            )
        return targets

    def append_settlement(
        self,
        *,
        candidate_id: str,
        snapshot_id: str,
        result: SettlementResult,
        settled_at: datetime,
        settlement_version: str | None = None,
        detail: Optional[Mapping[str, object]] = None,
    ) -> bool:
        """Append one causally and contract-bound settlement observation."""

        candidate_id = _text(candidate_id, "candidate_id", 100)
        snapshot_id = _text(snapshot_id, "snapshot_id", 100)
        if not isinstance(result, SettlementResult):
            raise TypeError("result must be a SettlementResult")
        if not isinstance(result.status, SettlementStatus):
            raise ValueError("SettlementResult.status must be SettlementStatus")
        stored_result = {
            SettlementStatus.WIN: "WON",
            SettlementStatus.LOSS: "LOST",
            SettlementStatus.VOID: "VOID",
            SettlementStatus.UNRESOLVED: "UNRESOLVED",
        }[result.status]
        rule_version = _text(result.rule_version, "rule_version", 120)
        settlement_reason = _text(result.reason, "settlement reason", 600)
        _assert_price_neutral(settlement_reason, "settlement reason")
        settled_at_text = _utc_text(settled_at, "settled_at")
        context_json = _detail_payload(detail)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                candidate_row = self._assert_candidate(
                    connection, candidate_id, snapshot_id
                )
                candidate = _verified_json(
                    candidate_row["payload_json"],
                    candidate_row["content_hash"],
                    f"candidate {candidate_id}/{snapshot_id}",
                )
                _, current_stage, _, _ = self._verified_stage_history(
                    connection,
                    candidate_id,
                    snapshot_id,
                    candidate=candidate,
                )
                if current_stage not in {
                    EvidenceStage.SHADOW,
                    EvidenceStage.VALIDATED,
                }:
                    raise FrozenRevisionError(
                        "only SHADOW or VALIDATED candidates may be settled"
                    )
                contract = _text(
                    candidate.get("settlement_contract"),
                    "settlement_contract",
                    240,
                )
                if settlement_version is not None and _text(
                    settlement_version, "settlement_version", 240
                ) != contract:
                    raise FrozenRevisionError(
                        "settlement version differs from the frozen candidate contract"
                    )
                contract_rule_version = contract.split(":", 1)[0]
                if contract_rule_version != rule_version:
                    raise FrozenRevisionError(
                        "settlement rule version differs from the frozen contract"
                    )
                if settled_at_text < str(candidate["starts_at"]):
                    raise FrozenRevisionError("settlement must not predate event start")

                newest_revision = self._newest_settleable_revision(
                    connection,
                    candidate_id,
                )
                if (
                    newest_revision is None
                    or newest_revision["candidate"]["snapshot_id"] != snapshot_id  # type: ignore[index]
                ):
                    raise FrozenRevisionError(
                        "settlement must use the newest prospectively stored snapshot"
                    )

                detail_payload: dict[str, object] = {
                    "settlement_reason": settlement_reason,
                    "rule_version": rule_version,
                }
                context = json.loads(context_json)
                if context:
                    detail_payload["context"] = context
                detail_json = canonical_json(detail_payload)
                settlement_id = _stable_id(
                    "settlement",
                    candidate_id,
                    snapshot_id,
                    contract,
                    settled_at_text,
                )
                settlement_payload = {
                    "settlement_id": settlement_id,
                    "candidate_id": candidate_id,
                    "snapshot_id": snapshot_id,
                    "settlement_version": contract,
                    "result": stored_result,
                    "settled_at": settled_at_text,
                    "detail": detail_payload,
                }
                stored_payload = canonical_json(settlement_payload)
                content_hash = _digest(stored_payload)

                if stored_result in _FINAL_SETTLEMENT_RESULTS:
                    terminal = connection.execute(
                        """
                        SELECT * FROM settlements
                        WHERE candidate_id=? AND result IN ('WON', 'LOST', 'VOID')
                        """,
                        (candidate_id,),
                    ).fetchone()
                    if terminal is not None:
                        terminal_payload = {
                            "settlement_id": terminal["settlement_id"],
                            "candidate_id": terminal["candidate_id"],
                            "snapshot_id": terminal["snapshot_id"],
                            "settlement_version": terminal["settlement_version"],
                            "result": terminal["result"],
                            "settled_at": terminal["settled_at"],
                            "detail": json.loads(terminal["detail_json"]),
                        }
                        if _digest(canonical_json(terminal_payload)) != terminal["content_hash"]:
                            raise FrozenRevisionError(
                                "terminal settlement content hash mismatch"
                            )
                        comparable = dict(terminal_payload)
                        comparable.pop("settlement_id")
                        comparable.pop("settled_at")
                        incoming = dict(settlement_payload)
                        incoming.pop("settlement_id")
                        incoming.pop("settled_at")
                        if comparable == incoming:
                            connection.commit()
                            return False
                        raise FrozenRevisionError(
                            "candidate already has a conflicting terminal settlement"
                        )
                inserted = self._insert_immutable(
                    connection,
                    insert_sql="""
                        INSERT OR IGNORE INTO settlements (
                            settlement_id, candidate_id, snapshot_id,
                            settlement_version, result, settled_at,
                            detail_json, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values=(
                        settlement_id,
                        candidate_id,
                        snapshot_id,
                        contract,
                        stored_result,
                        settled_at_text,
                        detail_json,
                        content_hash,
                    ),
                    select_sql="SELECT content_hash FROM settlements WHERE settlement_id=?",
                    select_values=(
                        settlement_id,
                    ),
                    expected_hash=content_hash,
                    identity_label=(
                        f"settlement {candidate_id}/{snapshot_id}/{contract}"
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise FrozenRevisionError("settlement uniqueness was violated") from exc
            except Exception:
                connection.rollback()
                raise
        return inserted

    def append_terminal_settlement(self, **kwargs: object) -> bool:
        """Append only a final WIN/LOSS/VOID observation."""

        result = kwargs.get("result")
        if not isinstance(result, SettlementResult):
            raise TypeError("result must be a SettlementResult")
        if result.status not in {
            SettlementStatus.WIN,
            SettlementStatus.LOSS,
            SettlementStatus.VOID,
        }:
            raise ValueError("only terminal settlements may be appended")
        return self.append_settlement(**kwargs)  # type: ignore[arg-type]

    def append_stage_event(
        self,
        *,
        candidate_id: str,
        snapshot_id: str,
        from_stage: EvidenceStage | str,
        to_stage: EvidenceStage | str,
        occurred_at: datetime,
        reason: str,
        validation_version: str,
        evidence: ValidationEvidenceArtifact | None = None,
    ) -> bool:
        """Append a legal evidence transition without rewriting the candidate."""

        candidate_id = _text(candidate_id, "candidate_id", 100)
        snapshot_id = _text(snapshot_id, "snapshot_id", 100)
        try:
            from_stage = EvidenceStage(from_stage)
            to_stage = EvidenceStage(to_stage)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid evidence stage") from exc
        if (from_stage, to_stage) not in _ALLOWED_STAGE_TRANSITIONS:
            raise ValueError("illegal evidence-stage transition")
        occurred_at_text = _utc_text(occurred_at, "occurred_at")
        reason = _text(reason, "reason", 600)
        _assert_price_neutral(reason, "reason")
        validation_version = _text(
            validation_version,
            "validation_version",
            120,
        )
        if to_stage is EvidenceStage.SHADOW:
            if evidence is not None:
                raise ValueError("RESEARCH to SHADOW does not accept validation evidence")
            evidence_payload: dict[str, object] = {}
        else:
            if not isinstance(evidence, ValidationEvidenceArtifact):
                raise ValueError(
                    "SHADOW to VALIDATED requires ValidationEvidenceArtifact"
                )
            evidence_payload = evidence.to_dict()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                candidate_row = self._assert_candidate(
                    connection,
                    candidate_id,
                    snapshot_id,
                )
                candidate = _verified_json(
                    candidate_row["payload_json"],
                    candidate_row["content_hash"],
                    f"candidate {candidate_id}/{snapshot_id}",
                )
                _, current_stage, parent_id, previous_time = self._verified_stage_history(
                    connection,
                    candidate_id,
                    snapshot_id,
                    candidate=candidate,
                )
                existing = connection.execute(
                    """
                    SELECT * FROM stage_events
                    WHERE candidate_id=? AND snapshot_id=? AND to_stage=?
                      AND validation_version=?
                    """,
                    (
                        candidate_id,
                        snapshot_id,
                        to_stage.value,
                        validation_version,
                    ),
                ).fetchone()
                if existing is not None:
                    existing_payload = {
                        "stage_event_id": existing["stage_event_id"],
                        "candidate_id": existing["candidate_id"],
                        "snapshot_id": existing["snapshot_id"],
                        "parent_stage_event_id": existing["parent_stage_event_id"],
                        "from_stage": existing["from_stage"],
                        "to_stage": existing["to_stage"],
                        "occurred_at": existing["occurred_at"],
                        "reason": existing["reason"],
                        "validation_version": existing["validation_version"],
                        "evidence": json.loads(existing["evidence_json"]),
                    }
                    if _digest(canonical_json(existing_payload)) != existing["content_hash"]:
                        raise FrozenRevisionError("stage transition content hash mismatch")
                    if (
                        existing["from_stage"] != from_stage.value
                        or existing["occurred_at"] != occurred_at_text
                        or existing["reason"] != reason
                        or existing_payload["evidence"] != evidence_payload
                    ):
                        raise FrozenRevisionError(
                            "stage transition already exists with different content"
                        )
                    connection.commit()
                    return False
                if current_stage is not from_stage:
                    raise FrozenRevisionError(
                        "stage transition does not start at the current stage"
                    )
                if previous_time is not None and occurred_at_text <= previous_time:
                    raise FrozenRevisionError(
                        "stage transition time must be strictly increasing"
                    )
                if to_stage is EvidenceStage.SHADOW:
                    if not candidate.get("settlement_contract"):
                        raise FrozenRevisionError(
                            "RESEARCH to SHADOW requires a frozen settlement contract"
                        )
                    if candidate.get("model_probability") is None:
                        raise FrozenRevisionError(
                            "RESEARCH to SHADOW requires a model probability"
                        )
                    if occurred_at_text >= str(candidate["starts_at"]):
                        raise FrozenRevisionError(
                            "RESEARCH to SHADOW must be recorded before event start"
                        )
                else:
                    snapshot_row = connection.execute(
                        "SELECT * FROM snapshots WHERE snapshot_id=?",
                        (snapshot_id,),
                    ).fetchone()
                    if snapshot_row is None:
                        raise MissingRevisionError(f"unknown snapshot: {snapshot_id}")
                    snapshot = self._verified_snapshot_row(snapshot_row)
                    self._validate_promotion_evidence(
                        evidence,
                        candidate=candidate,
                        snapshot=snapshot,
                        validation_version=validation_version,
                    )
                stage_event_id = _stable_id(
                    "stage",
                    candidate_id,
                    snapshot_id,
                    parent_id or "",
                    from_stage.value,
                    to_stage.value,
                    validation_version,
                    occurred_at_text,
                )
                event_payload = {
                    "stage_event_id": stage_event_id,
                    "candidate_id": candidate_id,
                    "snapshot_id": snapshot_id,
                    "parent_stage_event_id": parent_id,
                    "from_stage": from_stage.value,
                    "to_stage": to_stage.value,
                    "occurred_at": occurred_at_text,
                    "reason": reason,
                    "validation_version": validation_version,
                    "evidence": evidence_payload,
                }
                stored_payload = canonical_json(event_payload)
                content_hash = _digest(stored_payload)
                evidence_json = canonical_json(evidence_payload)
                inserted = self._insert_immutable(
                    connection,
                    insert_sql="""
                        INSERT OR IGNORE INTO stage_events (
                            stage_event_id, candidate_id, snapshot_id,
                            parent_stage_event_id, from_stage, to_stage,
                            occurred_at, reason, validation_version,
                            evidence_json, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values=(
                        stage_event_id,
                        candidate_id,
                        snapshot_id,
                        parent_id,
                        from_stage.value,
                        to_stage.value,
                        occurred_at_text,
                        reason,
                        validation_version,
                        evidence_json,
                        content_hash,
                    ),
                    select_sql="SELECT content_hash FROM stage_events WHERE stage_event_id=?",
                    select_values=(stage_event_id,),
                    expected_hash=content_hash,
                    identity_label=f"stage event {stage_event_id}",
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return inserted

    def _consumer_payload(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> dict[str, object]:
        stored_run = self._verified_run_payload(connection, run_id)
        snapshots, frozen_candidates = self._verified_frozen_memberships(
            connection, stored_run
        )
        candidates: list[dict[str, object]] = []
        for frozen_candidate in frozen_candidates:
            candidate = dict(frozen_candidate)
            candidate["featured"] = False
            stage_history, current_stage, _, _ = self._verified_stage_history(
                connection,
                str(candidate["candidate_id"]),
                str(candidate["snapshot_id"]),
                candidate=candidate,
            )
            candidate["stage_history"] = stage_history
            candidate["stage"] = current_stage.value
            settlement_rows = connection.execute(
                """
                SELECT *
                FROM settlements
                WHERE candidate_id=? AND snapshot_id=?
                ORDER BY settled_at, settlement_id
                """,
                (candidate["candidate_id"], candidate["snapshot_id"]),
            ).fetchall()
            settlements: list[dict[str, object]] = []
            terminal_count = 0
            for settlement in settlement_rows:
                try:
                    detail = json.loads(settlement["detail_json"])
                except json.JSONDecodeError as exc:
                    raise FrozenRevisionError("settlement detail is invalid JSON") from exc
                if canonical_json(detail) != settlement["detail_json"]:
                    raise FrozenRevisionError("settlement detail is not canonical")
                _assert_price_neutral(detail, "detail")
                settlement_payload = {
                    "settlement_id": settlement["settlement_id"],
                    "candidate_id": settlement["candidate_id"],
                    "snapshot_id": settlement["snapshot_id"],
                    "settlement_version": settlement["settlement_version"],
                    "result": settlement["result"],
                    "settled_at": settlement["settled_at"],
                    "detail": detail,
                }
                if _digest(canonical_json(settlement_payload)) != settlement["content_hash"]:
                    raise FrozenRevisionError("settlement content hash mismatch")
                if settlement["settlement_version"] != candidate.get(
                    "settlement_contract"
                ):
                    raise FrozenRevisionError("settlement is detached from candidate contract")
                if settlement["settled_at"] < str(candidate["starts_at"]):
                    raise FrozenRevisionError("settlement predates event start")
                if settlement["result"] in _FINAL_SETTLEMENT_RESULTS:
                    terminal_count += 1
                settlements.append(
                    {
                        "settlement_id": settlement["settlement_id"],
                        "settlement_version": settlement["settlement_version"],
                        "result": settlement["result"],
                        "settled_at": settlement["settled_at"],
                        "detail": detail,
                    }
                )
            if terminal_count > 1:
                raise FrozenRevisionError("candidate has duplicate terminal settlements")
            candidate["settlements"] = settlements
            candidates.append(candidate)
        return {
            "schema_version": 1,
            "run_id": stored_run["run_id"],
            "started_at": stored_run["started_at"],
            "completed_at": stored_run["completed_at"],
            "status": stored_run["status"],
            "snapshots": snapshots,
            "candidates": candidates,
            "errors": stored_run["errors"],
        }

    def load_run(self, run_id: str | None = None) -> Optional[dict[str, object]]:
        """Load a stored run as its read-only consumer payload."""

        with closing(self._connect()) as connection:
            if run_id is None:
                row = connection.execute(
                    """
                    SELECT run_id FROM runs
                    ORDER BY completed_at DESC, run_id DESC LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    return None
                run_id = row["run_id"]
            else:
                run_id = _text(run_id, "run_id", 100)
            return self._consumer_payload(connection, run_id)

    def publish_latest(
        self,
        run: RiskRunSnapshot | str | None = None,
    ) -> Path:
        """Select and atomically publish one persisted run for consumers."""

        if isinstance(run, RiskRunSnapshot):
            self.append_run(run)
            run_id: str | None = run.run_id
        elif run is None:
            run_id = None
        else:
            run_id = _text(run, "run_id", 100)
        with _publication_lock(self.latest_path):
            try:
                current = self.read_latest()
            except FrozenRevisionError:
                # The JSON file is a derived read model.  A verified database
                # payload may repair a torn or otherwise invalid publication.
                current = None
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    selected = self._verified_publication_run(connection)
                    if run_id is None:
                        if selected is not None:
                            requested = selected
                        else:
                            row = connection.execute(
                                """
                                SELECT run_id FROM runs
                                ORDER BY completed_at DESC, run_id DESC LIMIT 1
                                """
                            ).fetchone()
                            if row is None:
                                raise MissingRevisionError(
                                    "no RisikoBet run is available to publish"
                                )
                            requested = self._verified_run_payload(
                                connection,
                                str(row["run_id"]),
                            )
                            self._verified_frozen_memberships(connection, requested)
                    else:
                        requested = self._verified_run_payload(connection, run_id)
                        self._verified_frozen_memberships(connection, requested)

                    requested_order = (
                        str(requested["completed_at"]),
                        str(requested["run_id"]),
                    )
                    selected_order = (
                        None
                        if selected is None
                        else (
                            str(selected["completed_at"]),
                            str(selected["run_id"]),
                        )
                    )
                    effective = requested
                    if selected is not None and requested_order < selected_order:
                        # An old explicit request may heal the derived file, but
                        # it can never move the durable selection backwards.
                        effective = selected
                    effective_order = (
                        str(effective["completed_at"]),
                        str(effective["run_id"]),
                    )
                    if current is not None:
                        current_order = (
                            str(current["completed_at"]),
                            str(current["run_id"]),
                        )
                        if effective_order < current_order:
                            connection.commit()
                            return self.latest_path
                    if (
                        selected is None
                        or effective["run_id"] != selected["run_id"]
                    ):
                        self._set_publication_pointer(
                            connection,
                            str(effective["run_id"]),
                        )
                    payload = self._consumer_payload(
                        connection,
                        str(effective["run_id"]),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            runtime_paths.atomic_write_text(
                self.latest_path,
                canonical_json(
                    {
                        **payload,
                        "payload_digest": _digest(canonical_json(payload)),
                    }
                )
                + "\n",
            )
        return self.latest_path

    def republish_latest_if_current(
        self,
        run_id: str,
        *,
        expected_payload_digest: str,
    ) -> bool:
        """Atomically replace the derived JSON only if its pointer is unchanged."""

        run_id = _text(run_id, "run_id", 100)
        expected = _text(
            expected_payload_digest,
            "expected_payload_digest",
            64,
        ).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("expected_payload_digest must be a SHA-256 digest")
        with _publication_lock(self.latest_path):
            current = self.read_latest()
            if (
                current is None
                or current.get("run_id") != run_id
                or _digest(canonical_json(current)) != expected
            ):
                return False
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    selected = self._verified_publication_run(connection)
                    if selected is None or selected.get("run_id") != run_id:
                        connection.commit()
                        return False
                    payload = self._consumer_payload(connection, run_id)
                    current = self.read_latest()
                    if (
                        current is None
                        or current.get("run_id") != run_id
                        or _digest(canonical_json(current)) != expected
                    ):
                        connection.commit()
                        return False
                    runtime_paths.atomic_write_text(
                        self.latest_path,
                        canonical_json(
                            {
                                **payload,
                                "payload_digest": _digest(canonical_json(payload)),
                            }
                        )
                        + "\n",
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return True

    def read_latest(self) -> Optional[dict[str, object]]:
        """Read the last fully replaced consumer document, if present."""

        try:
            raw = self.latest_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FrozenRevisionError("riskobet_latest.json is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise FrozenRevisionError("riskobet_latest.json must contain an object")
        return validate_latest_document(payload)


__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_LATEST_PATH",
    "FrozenRevisionError",
    "MissingRevisionError",
    "RiskBetStore",
    "SCHEMA_VERSION",
    "SETTLEMENT_RESULTS",
    "validate_latest_document",
]
