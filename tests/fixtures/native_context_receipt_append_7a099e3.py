"""One real observation append inside a caller-owned private C build.

The caller supplies the exact, already profiled TrackedConnection, its existing
legacy receipt schema, and its held build transaction. This module never opens
a connection, creates schema, commits, closes the connection or deletes a file.
It returns the ordinary content-derived receipt identity, NOT a verified source
mapping, copied-main writer capability, coverage, publication or B permission.

The complete fixed writer profile, protected namespace, input/record bounds,
global reservations and native CPU/memory/file limits belong to that caller.
In particular this is not a Python sandbox: callbacks, concurrent use, raw base
class calls, illicit commits and replacement/ABA are excluded by the outer
closed writer catalogue. Observed lifetime/factory drift is a failure, not a
way to undo a commit that an unsupported caller has already performed.

Each normal failed append rolls back its own savepoint, preserving earlier
pending caller work. If SQLite ends the transaction, or savepoint cleanup is
unavailable, the caller must abandon the entire unpublished build. No digest
is returned for such an outcome, and a different transaction is never rolled
back as if it were the original one. Materialization is one normalized input
record; stored collision values are size/type bounded before Python readback.
"""
from __future__ import annotations

from datetime import datetime
import sqlite3
from uuid import uuid4

from context_models.contracts import (
    ContextIntegrityError, canonical_timestamp, digest, normalize_observation,
)
from context_observations import _decode_receipt
from context_runtime_transaction import TrackedConnection, TrackedCursor
from model_artifacts import canonical_bytes

from .contracts import StorageIntegrityError, StorageLimitError


_FIELDS = ("digest", "content_digest", "event_key", "observed_at",
           "schedule_revision", "source", "subject_id", "kind")
_SELECT = """SELECT r.digest,r.content_digest,r.event_key,r.observed_at,
                   r.schedule_revision,r.source,r.subject_id,r.kind,c.payload
            FROM main.context_observations AS r
            LEFT JOIN main.context_contents AS c ON c.content_digest=r.content_digest
            WHERE r.digest=?"""
# The normalized index fields are ASCII codes, clocks and hex identities.
# Two bytes per character also admits their physical UTF-16 representation.
# CAST(... AS BLOB) counts bytes beyond embedded NUL, unlike SQL length(TEXT).
_BOUNDED_SELECT = _SELECT + "".join(
    f" AND typeof(r.{name})='text' AND length(CAST(r.{name} AS BLOB))<=?"
    for name in _FIELDS
) + " AND typeof(c.payload)='blob' AND length(c.payload)=?"


def _held(connection, generation=None):
    if type(connection) is not TrackedConnection:
        raise StorageIntegrityError("receipt append requires the exact tracked connection")
    try:
        current = connection.transaction_generation
        if (not connection.in_transaction or type(current) is not int or current < 0
                or (generation is not None and current != generation)):
            raise StorageIntegrityError("receipt append build transaction ended or changed")
        if (connection.row_factory is not None or connection.text_factory is not str
                or connection.isolation_level is not None
                or connection.autocommit != sqlite3.LEGACY_TRANSACTION_CONTROL):
            raise StorageIntegrityError("receipt append connection policy changed")
        return current
    except sqlite3.Error as exc:
        raise StorageIntegrityError("receipt append connection is no longer usable") from exc


def _same_transaction(connection, generation):
    # Cleanup deliberately does not require unchanged factories: the held
    # cursor can still roll back this savepoint after observed factory drift.
    try:
        return (type(connection) is TrackedConnection and connection.in_transaction
                and type(connection.transaction_generation) is int
                and connection.transaction_generation == generation)
    except sqlite3.Error:
        return False


def _run(cursor, connection, generation, sql, parameters=(), *, read=False):
    _held(connection, generation)
    cursor.execute(sql, parameters)
    _held(connection, generation)
    result = cursor.fetchone() if read else None
    _held(connection, generation)
    return result


def append_observation_in_connection(
    connection: TrackedConnection, record: dict, *, observed_at: datetime,
) -> str:
    """Append with unchanged legacy normalization/identity/collision semantics.

    Only the caller can finish this build. This call neither begins an outer
    transaction nor validates the complete corpus or source truth. Semantic
    rejection retains the existing ContextContractError/ContextIntegrityError;
    SQL allocation failure is StorageLimitError, and connection/cleanup failure
    is StorageIntegrityError. A failed cleanup requires whole-build abandonment.
    """
    generation = _held(connection)
    try:
        content = normalize_observation(record, observed_at=observed_at)
        observed = canonical_timestamp(observed_at)
        content_hash = digest(content)
        receipt_hash = digest({"content_digest": content_hash, "observed_at": observed})
        payload = canonical_bytes(content)
    finally:
        _held(connection, generation)
    expected = (receipt_hash, content_hash, content["event_key"], observed,
                content["schedule_revision"], content["source"], content["subject_id"],
                content["kind"])
    name = "v2_receipt_append_" + uuid4().hex
    cursor, saved = None, False
    try:
        cursor = connection.cursor()
        if type(cursor) is not TrackedCursor or cursor.connection is not connection:
            raise StorageIntegrityError("receipt append requires its normal tracked cursor")
        cursor.row_factory = None
        _held(connection, generation)
        cursor.execute(f"SAVEPOINT {name}")
        saved = True
        _held(connection, generation)
        _run(cursor, connection, generation,
             "INSERT OR IGNORE INTO main.context_contents VALUES (?, ?)",
             (content_hash, payload))
        existing = _run(cursor, connection, generation,
            "SELECT payload FROM main.context_contents WHERE content_digest=? "
            "AND typeof(payload)='blob' AND length(payload)=?",
            (content_hash, len(payload)), read=True)
        if existing != (payload,):
            raise ContextIntegrityError("context content identity collision")
        _run(cursor, connection, generation,
            "INSERT OR IGNORE INTO main.context_observations "
            "(digest,content_digest,event_key,observed_at,schedule_revision,source,subject_id,kind) "
            "VALUES (?,?,?,?,?,?,?,?)", expected)
        stored = _run(cursor, connection, generation, _BOUNDED_SELECT,
                      (receipt_hash, *(2 * len(value) for value in expected), len(payload)), read=True)
        if stored is None or _decode_receipt(stored) != {
            **content, "digest": receipt_hash, "content_digest": content_hash,
            "observed_at": observed,
        }:
            raise ContextIntegrityError("context receipt identity collision")
        _held(connection, generation)
        cursor.execute(f"RELEASE {name}")
        saved = False
        _held(connection, generation)
        cursor.close()
        cursor = None
        _held(connection, generation)
    except BaseException as exc:
        cleanup_error = None
        if saved and _same_transaction(connection, generation):
            try:
                cursor.execute(f"ROLLBACK TO {name}")
                if not _same_transaction(connection, generation):
                    raise StorageIntegrityError("receipt append cleanup changed its transaction")
                cursor.execute(f"RELEASE {name}")
                if not _same_transaction(connection, generation):
                    raise StorageIntegrityError("receipt append cleanup changed its transaction")
            except BaseException as rollback_error:
                cleanup_error = rollback_error
        if cursor is not None:
            try:
                cursor.close()
            except BaseException as close_error:
                cleanup_error = cleanup_error or close_error
        if cleanup_error is not None:
            failure = StorageIntegrityError("receipt append cleanup failed; abandon the entire build")
            failure.add_note("Original append failure: " + type(exc).__name__)
            raise failure from cleanup_error
        if isinstance(exc, sqlite3.DatabaseError):
            if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_FULL, sqlite3.SQLITE_TOOBIG):
                raise StorageLimitError("receipt append hit SQLite's hard allocation limit") from exc
            raise StorageIntegrityError("receipt append SQL transaction failed") from exc
        raise
    return receipt_hash
