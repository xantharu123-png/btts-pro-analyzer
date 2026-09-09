"""Immutable JSON model artifacts with atomic manifest publication."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from runtime_paths import prepare_trusted_runtime_database_path


class ManifestConflict(RuntimeError):
    """The active manifest changed after a publisher read it."""


class ArtifactIntegrityError(ValueError):
    """Stored model data no longer matches its immutable identity or schema."""


def canonical_bytes(value: object) -> bytes:
    """Return the deterministic UTF-8 JSON representation of ``value``."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _validate_json_object_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _validate_json_object_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _validate_json_object_keys(nested)


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError) as exc:
        raise ValueError("timestamp must be timezone-aware") from exc
    if offset is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.isoformat()


def _decision_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("decision cutoff must be timezone-aware")
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError) as exc:
        raise ValueError("decision cutoff must be timezone-aware") from exc
    if offset is None:
        raise ValueError("decision cutoff must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_stored_timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ArtifactIntegrityError(f"{label} must be SQLite TEXT")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ArtifactIntegrityError(f"{label} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ArtifactIntegrityError(f"{label} must be timezone-aware")
    return value


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _validate_digest(value: object, *, label: str = "digest") -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactIntegrityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json(value: str):
    raise ArtifactIntegrityError(f"JSON number must be finite: {value}")


def _decode_object(payload: object, *, label: str) -> dict:
    if not isinstance(payload, bytes):
        raise ArtifactIntegrityError(f"{label} must be SQLite BLOB")
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_json,
        )
    except ArtifactIntegrityError:
        raise
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ArtifactIntegrityError(f"{label} must be a JSON object")
    if canonical_bytes(value) != payload:
        raise ArtifactIntegrityError(f"{label} is not canonical JSON")
    return value


def _connect(path: Path) -> sqlite3.Connection:
    path = prepare_trusted_runtime_database_path(Path(path))
    connection = sqlite3.connect(path, timeout=5)
    try:
        prepare_trusted_runtime_database_path(path)
    except BaseException:
        connection.close()
        raise
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts(
                digest TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload BLOB NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS manifests(
                digest TEXT PRIMARY KEY,
                predecessor TEXT,
                payload BLOB NOT NULL,
                published_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS active_manifest(
                id INTEGER PRIMARY KEY CHECK(id=1),
                digest TEXT NOT NULL REFERENCES manifests(digest)
            )
            """
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        connection.close()
        raise
    return connection


def put_artifact(
    path: Path,
    *,
    kind: str,
    payload: dict,
    created_at: datetime,
) -> str:
    """Store an immutable typed payload and return its content identity."""

    if not isinstance(kind, str):
        raise TypeError("kind must be a string")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")
    _validate_json_object_keys(payload)
    created_at_text = _timestamp(created_at)
    payload_bytes = canonical_bytes(payload)
    digest = _digest({"kind": kind, "payload": payload})
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO artifacts(digest, kind, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (digest, kind, payload_bytes, created_at_text),
            )
            row = connection.execute(
                "SELECT kind, payload FROM artifacts WHERE digest=?",
                (digest,),
            ).fetchone()
            if row != (kind, payload_bytes):
                raise ValueError("artifact identity collision")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return digest


def _load_artifact(
    connection: sqlite3.Connection,
    digest: str,
) -> dict:
    _validate_digest(digest, label="artifact digest")
    row = connection.execute(
        "SELECT kind, payload, created_at FROM artifacts WHERE digest=?",
        (digest,),
    ).fetchone()
    if row is None:
        raise KeyError(digest)
    kind, payload_bytes, created_at = row
    if not isinstance(kind, str):
        raise ArtifactIntegrityError("artifact kind must be SQLite TEXT")
    payload = _decode_object(payload_bytes, label="artifact payload")
    _validate_stored_timestamp(created_at, label="artifact created_at")
    if _digest({"kind": kind, "payload": payload}) != digest:
        raise ArtifactIntegrityError("artifact hash mismatch")
    return {"kind": kind, "payload": payload}


def load_artifact(path: Path, digest: str) -> dict:
    """Load one artifact by its immutable content identity."""

    _validate_digest(digest, label="artifact digest")
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN")
            artifact = _load_artifact(connection, digest)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return artifact


def _load_active(
    connection: sqlite3.Connection,
    *,
    decision_cutoff: datetime | None = None,
) -> tuple[str | None, dict[str, str]]:
    active_row = connection.execute(
        "SELECT digest FROM active_manifest WHERE id=1"
    ).fetchone()
    if active_row is None:
        return None, {}
    digest = _validate_digest(active_row[0], label="active manifest digest")
    row = connection.execute(
        """
        SELECT predecessor, payload, published_at
        FROM manifests WHERE digest=?
        """,
        (digest,),
    ).fetchone()
    if row is None:
        raise ArtifactIntegrityError("active row references a missing manifest")
    predecessor, payload_bytes, published_at = row
    if predecessor is not None:
        _validate_digest(predecessor, label="manifest predecessor")
    slots = _decode_object(payload_bytes, label="manifest payload")
    published_at = _validate_stored_timestamp(
        published_at,
        label="manifest published_at",
    )
    for slot, artifact_digest in slots.items():
        if not isinstance(slot, str):
            raise ArtifactIntegrityError("manifest slot must be a string")
        _validate_digest(artifact_digest, label=f"manifest slot {slot!r}")
    if _digest(
        {
            "predecessor": predecessor,
            "slots": slots,
            "published_at": published_at,
        }
    ) != digest:
        raise ArtifactIntegrityError("manifest hash mismatch")
    if decision_cutoff is not None:
        published = datetime.fromisoformat(published_at).astimezone(timezone.utc)
        if published > decision_cutoff:
            raise ValueError("active manifest was published after the decision cutoff")
    return digest, slots


def load_manifest(
    path: Path,
    *,
    decision_cutoff: datetime | None = None,
) -> tuple[str | None, dict[str, str]]:
    """Return the active manifest identity and its artifact slots."""

    decision_cutoff = _decision_time(decision_cutoff)
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN")
            manifest = _load_active(
                connection,
                decision_cutoff=decision_cutoff,
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return manifest


def publish_slots(
    path: Path,
    updates: dict[str, str],
    *,
    expected_manifest: str | None,
    published_at: datetime,
) -> str:
    """Atomically merge slots when the active manifest matches the caller."""

    if not isinstance(updates, dict):
        raise TypeError("updates must be a dictionary")
    if expected_manifest is not None:
        _validate_digest(expected_manifest, label="expected manifest")
    for slot, artifact_digest in updates.items():
        if not isinstance(slot, str):
            raise TypeError("manifest slot must be a string")
        _validate_digest(artifact_digest, label=f"manifest slot {slot!r}")
    published_at_text = _timestamp(published_at)
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            current_digest, current_slots = _load_active(connection)
            if current_digest != expected_manifest:
                connection.rollback()
                raise ManifestConflict("manifest changed")
            next_slots = {**current_slots, **updates}
            for artifact_digest in next_slots.values():
                _load_artifact(connection, artifact_digest)
            digest = _digest(
                {
                    "predecessor": current_digest,
                    "slots": next_slots,
                    "published_at": published_at_text,
                }
            )
            payload_bytes = canonical_bytes(next_slots)
            connection.execute(
                """
                INSERT OR IGNORE INTO manifests(
                    digest, predecessor, payload, published_at
                ) VALUES (?, ?, ?, ?)
                """,
                (digest, current_digest, payload_bytes, published_at_text),
            )
            stored = connection.execute(
                """
                SELECT predecessor, payload, published_at
                FROM manifests WHERE digest=?
                """,
                (digest,),
            ).fetchone()
            if stored != (current_digest, payload_bytes, published_at_text):
                raise ArtifactIntegrityError("manifest identity collision")
            connection.execute(
                """
                INSERT INTO active_manifest(id, digest) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET digest=excluded.digest
                """,
                (digest,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return digest


def rollback_model_slots(
    path: Path, previous_manifest_hash: str, *, expected_manifest: str,
    published_at: datetime,
) -> str:
    """Publish the exact old model-slot set as a new, audited CAS revision.

    Only immutable pointers roll back. Newer artifacts, observations, forecast
    snapshots and every separate finance database remain untouched. This is a
    mechanical operator rollback, never a new empirical model approval.
    """
    # Lazy import keeps A1 canonical storage available to the owning validators.
    from context_runtime import ROLLBACK_REASON, ROLLBACK_SQL, _open_database, _verify_connection

    _validate_digest(previous_manifest_hash, label="rollback target")
    _validate_digest(expected_manifest, label="expected manifest")
    published = _timestamp(published_at)
    with _open_database(path, writable=True) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            # Check CAS before any audit-table creation or publication.
            current, _ = _load_active(connection)
            if current != expected_manifest:
                raise ManifestConflict("manifest changed")
            checked = _verify_connection(connection)
            manifests, chain = checked["manifests"], checked["chain"]
            if previous_manifest_hash not in chain[1:]:
                raise ArtifactIntegrityError("rollback target is not an earlier manifest in this history")
            if datetime.fromisoformat(published) < datetime.fromisoformat(manifests[current]["published_at"]):
                raise ArtifactIntegrityError("rollback publication time precedes the current manifest")
            slots = manifests[previous_manifest_hash]["slots"]
            new = _digest({"predecessor": current, "slots": slots, "published_at": published})
            connection.execute("INSERT INTO manifests(digest,predecessor,payload,published_at) VALUES (?,?,?,?)",
                               (new, current, canonical_bytes(slots), published))
            if "context_model_rollbacks" not in checked["tables"]:
                connection.execute(ROLLBACK_SQL)
            audit = {"schema": 1, "expected_manifest": current, "target_manifest": previous_manifest_hash,
                     "new_manifest": new, "reason": ROLLBACK_REASON, "published_at": published}
            connection.execute("INSERT INTO context_model_rollbacks(digest,payload) VALUES (?,?)",
                               (_digest(audit), canonical_bytes(audit)))
            connection.execute("UPDATE active_manifest SET digest=? WHERE id=1 AND digest=?", (new, current))
            _verify_connection(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return new
