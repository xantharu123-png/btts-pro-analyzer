"""Explicit optional migration and bounded, resumable derived membership build.

No source inventories, copies, pruning or implicit runtime activation. Readiness
is published only by an empty range seek while holding the SQLite writer lock.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import time

import context_tennis_index as index
from context_tennis_index import IndexBudgetExceeded
from context_observations import _SELECT, _decode_receipt
from context_runtime import _trusted_existing_file, verify_context_schema_objects
from model_artifacts import ArtifactIntegrityError, canonical_bytes


MAX_LOGICAL_BYTES = 64 * 1024**2
MAX_CHUNK_BYTES = 2 * 1024**2
MAX_CHUNK_ROWS = 512
MAX_CALL_SECONDS = 45.0
MAX_TRANSACTION_SECONDS = 2.0


@dataclass(frozen=True)
class IndexBuildResult:
    status: str
    covered_rowid: int | None
    source_tail_rowid: int | None
    scanned_rows: int
    logical_bytes: int
    elapsed_seconds: float
    stop_reason: str | None


def _check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise IndexBudgetExceeded("deadline")


def _check_owner(path, identity):
    if _trusted_existing_file(path)[1] != identity:
        raise ArtifactIntegrityError("tennis database file identity changed")
    if hashlib.sha256(Path(index.__file__).read_bytes()).hexdigest() != index.PROJECTOR_SHA256:
        raise ArtifactIntegrityError("tennis projector changed during process lifetime")


@contextmanager
def _connection(path, *, writable, deadline):
    _check_deadline(deadline)
    path, identity = _trusted_existing_file(Path(path))
    for suffix in ("-wal", "-shm", "-journal"):
        companion = path.with_name(path.name + suffix)
        if os.path.lexists(companion):
            _trusted_existing_file(companion)
    _check_deadline(deadline)
    connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if writable else "?mode=ro"),
                                 uri=True, timeout=0, isolation_level=None)
    try:
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        if not writable:
            connection.execute("PRAGMA query_only=ON")
        _check_owner(path, identity)
        _check_deadline(deadline)
        yield connection, path, identity
        _check_owner(path, identity)
    except sqlite3.OperationalError as exc:
        code = getattr(exc, "sqlite_errorcode", None)
        if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} or (
                code == sqlite3.SQLITE_INTERRUPT and time.monotonic() >= deadline):
            raise IndexBudgetExceeded("deadline") from exc
        raise
    finally:
        connection.set_progress_handler(None, 0)
        connection.close()


@contextmanager
def _transaction(connection, deadline):
    # Start the transaction clock BEFORE attempting the lock, not after it.
    transaction_deadline = min(deadline, time.monotonic() + MAX_TRANSACTION_SECONDS)
    _check_deadline(transaction_deadline)
    connection.set_progress_handler(lambda: int(time.monotonic() >= transaction_deadline), 100)
    try:
        remaining_ms = max(0, int((transaction_deadline - time.monotonic()) * 1000))
        connection.execute(f"PRAGMA busy_timeout={remaining_ms}")
        connection.execute("BEGIN IMMEDIATE")
        _check_deadline(transaction_deadline)
        yield transaction_deadline
        _check_deadline(transaction_deadline)
        connection.commit()
    except sqlite3.OperationalError as exc:
        # Only expected SQLite lock/interrupt codes are budgets; malformed SQL
        # and genuine source/integrity errors must never become incomplete OK.
        code = getattr(exc, "sqlite_errorcode", None)
        if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_INTERRUPT}:
            raise IndexBudgetExceeded("deadline") from exc
        raise
    finally:
        connection.set_progress_handler(None, 0)
        if connection.in_transaction:
            connection.rollback()
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)


def _validate_state(state, identity):
    if state.schema_version != index.INDEX_SCHEMA_VERSION:
        raise ArtifactIntegrityError("unsupported tennis index schema version")
    if state.db_identity != identity:
        raise ArtifactIntegrityError("tennis index belongs to a different database file")
    if state.logical_bytes < 4096 or state.logical_bytes > MAX_LOGICAL_BYTES:
        raise ArtifactIntegrityError("tennis stored accounting is outside the possible logical range")


def initialize_index(path: Path) -> None:
    """Atomically install the exact optional family in an existing trusted DB."""
    deadline = time.monotonic() + MAX_CALL_SECONDS
    with _connection(path, writable=True, deadline=deadline) as (connection, actual, identity):
        with _transaction(connection, deadline) as transaction_deadline:
            verify_context_schema_objects(connection)
            if index.check_index_schema(connection):
                _validate_state(index.read_index_state(connection), identity)
                return
            sources = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('context_contents','context_observations')")}
            if sources != {"context_contents", "context_observations"}:
                raise ArtifactIntegrityError("tennis build requires the existing observation schema")
            for sql in index.INDEX_SCHEMA.values():
                _check_deadline(transaction_deadline)
                connection.execute(sql)
            connection.execute("""INSERT INTO tennis_player_index_state VALUES
                (1,?,?,?,0,0,0,0,0,0,4096,NULL,'building')""",
                (index.INDEX_SCHEMA_VERSION, index.PROJECTOR_SHA256, canonical_bytes(identity).decode("utf-8")))
            _check_owner(actual, identity)


def _upsert_membership(connection, member, logical_bytes):
    old = connection.execute("SELECT * FROM tennis_player_events WHERE tour=? AND player_id=? AND event_key=?", member[:3]).fetchone()
    if old is not None and old[3:] <= member[3:]:
        return logical_bytes
    updated = logical_bytes + len(canonical_bytes(member)) - (len(canonical_bytes(old)) if old else 0)
    if updated > MAX_LOGICAL_BYTES:
        raise IndexBudgetExceeded("logical_bytes")
    connection.execute("""INSERT INTO tennis_player_events VALUES (?,?,?,?,?)
        ON CONFLICT(tour,player_id,event_key) DO UPDATE SET
        first_observed_at=excluded.first_observed_at,
        first_receipt_digest=excluded.first_receipt_digest""", member)
    return updated


def _build_chunk(connection, path, identity, deadline):
    with _transaction(connection, deadline) as chunk_deadline:
        state = index.read_index_state(connection)
        _validate_state(state, identity)
        _check_owner(path, identity)
        tail = _tail(connection)
        if (state.projector_sha256 != index.PROJECTOR_SHA256
                or state.rewrite_generation != state.verified_rewrite_generation
                or state.index_generation != state.verified_index_generation):
            # Clear derived rows in bounded commits. A full DELETE can exceed
            # 2 seconds forever near the cap. Keep dirty verified generations
            # until empty; invalid counters are not a proof of membership size.
            keys = connection.execute("SELECT tour,player_id,event_key FROM tennis_player_events ORDER BY tour,player_id,event_key LIMIT ?", (MAX_CHUNK_ROWS,)).fetchall()
            for key in keys:
                _check_deadline(chunk_deadline)
                connection.execute("DELETE FROM tennis_player_events WHERE tour=? AND player_id=? AND event_key=?", key)
            if connection.execute("SELECT 1 FROM tennis_player_events LIMIT 1").fetchone():
                connection.execute("UPDATE tennis_player_index_state SET status='invalid' WHERE id=1")
                _check_owner(path, identity)
                committed = index.read_index_state(connection)
                # Context manager commits the partial reset. No source cursor
                # or verified generation can publish success between deletions.
                return 0, committed, False, tail
            connection.execute("""UPDATE tennis_player_index_state SET covered_rowid=NULL,
                logical_bytes=4096,projector_sha256=?,status='building',
                verified_rewrite_generation=rewrite_generation,
                verified_index_generation=index_generation WHERE id=1""", (index.PROJECTOR_SHA256,))
            state = index.read_index_state(connection)
        cursor = state.covered_rowid
        # Distinct SQL is essential: nullable OR predicates can rescan millions
        # of old rows. Both forms visit signed rowids in complete rowid order.
        where, args = ("", ()) if cursor is None else (" WHERE r.rowid>?", (cursor,))
        rows = connection.execute("""SELECT r.rowid,
            CASE WHEN r.source='espn' AND r.kind IN ('event_status','workload')
            THEN 1 ELSE 0 END,
            CASE WHEN r.source='espn' AND r.kind IN ('event_status','workload')
            THEN length(c.payload) ELSE NULL END
            FROM context_observations AS r LEFT JOIN context_contents AS c
            ON c.content_digest=r.content_digest""" + where + " ORDER BY r.rowid LIMIT ?", (*args, MAX_CHUNK_ROWS)).fetchall()
        scanned = size = 0
        logical = state.logical_bytes
        for rowid, candidate, length in rows:
            _check_deadline(chunk_deadline)
            if candidate:
                if type(length) is not int or length < 0:
                    raise ArtifactIntegrityError("missing physical tennis candidate content")
                if length > MAX_CHUNK_BYTES:
                    raise IndexBudgetExceeded("chunk_bytes")
                if size + length > MAX_CHUNK_BYTES:
                    break
                stored = connection.execute(_SELECT + " WHERE r.rowid=?", (rowid,)).fetchone()
                if type(stored[-1]) is not bytes or len(stored[-1]) != length:
                    raise ArtifactIntegrityError("tennis content changed type or length")
                size += length
                for member in index.project_memberships(_decode_receipt(stored)):
                    _check_deadline(chunk_deadline)
                    logical = _upsert_membership(connection, member, logical)
            scanned += 1
            cursor = rowid
        _check_owner(path, identity)
        _check_deadline(chunk_deadline)
        ready = not rows  # not MAX(rowid): actual empty delta under writer
        connection.execute("""UPDATE tennis_player_index_state SET covered_rowid=?,logical_bytes=?,
            status=?,verified_source_generation=source_generation,
            verified_index_generation=index_generation,
            verified_rewrite_generation=rewrite_generation WHERE id=1""",
            (cursor, logical, "ready" if ready else "building"))
        committed = index.read_index_state(connection)
    return scanned, committed, ready, tail


def _tail(connection):
    row = connection.execute("SELECT rowid FROM context_observations ORDER BY rowid DESC LIMIT 1").fetchone()
    return row[0] if row else None


def build_index(path: Path, *, seconds: float = 45) -> IndexBuildResult:
    """Perform one bounded invocation. Resume by explicitly invoking again."""
    started = time.monotonic()
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be finite and nonnegative")
    # A zero-budget request still checks the existing path but never claims
    # ready or changes state. No SQLite open, DDL or inventory is performed.
    if seconds == 0:
        _trusted_existing_file(Path(path))
        return IndexBuildResult("building", None, None, 0, 4096, time.monotonic()-started, "deadline")
    deadline = started + min(seconds, MAX_CALL_SECONDS)
    scanned = 0
    stop = None
    state = None
    tail = None
    try:
        with _connection(path, writable=True, deadline=deadline) as (connection, actual, identity):
            verify_context_schema_objects(connection)
            state = index.read_index_state(connection)
            _validate_state(state, identity)
            tail = _tail(connection)
            while True:
                _check_deadline(deadline)
                count, state, ready, tail = _build_chunk(connection, actual, identity, deadline)
                scanned += count
                if ready:
                    break
    except IndexBudgetExceeded as exc:
        stop = str(exc)
    # Use the last committed state; rollback never advances its cursor.
    # No post-budget SQL scan is needed to construct the bounded result.
    return IndexBuildResult(state.status if stop is None else "building",
        state.covered_rowid if state else None,
        tail, scanned,
        state.logical_bytes if state else 4096, time.monotonic()-started, stop)


def index_status(path: Path):
    """Read stored state without DDL, a build, or a readiness promotion."""
    deadline = time.monotonic() + MAX_TRANSACTION_SECONDS
    with _connection(path, writable=False, deadline=deadline) as (connection, actual, identity):
        verify_context_schema_objects(connection)
        if not index.check_index_schema(connection):
            return None
        state = index.read_index_state(connection)
        _validate_state(state, identity)
        if state.status == "ready" and (
                state.projector_sha256 != index.PROJECTOR_SHA256
                or state.source_generation != state.verified_source_generation
                or state.index_generation != state.verified_index_generation
                or state.rewrite_generation != state.verified_rewrite_generation):
            raise ArtifactIntegrityError("tennis ready state has stale projector or generations")
        return state


def disable_index(path: Path) -> None:
    """Explicitly invalidate; absent optional family is a byte-preserving no-op."""
    deadline = time.monotonic() + MAX_CALL_SECONDS
    with _connection(path, writable=True, deadline=deadline) as (connection, actual, identity):
        verify_context_schema_objects(connection)
        if not index.check_index_schema(connection):
            return
        with _transaction(connection, deadline):
            _validate_state(index.read_index_state(connection), identity)
            connection.execute("UPDATE tennis_player_index_state SET status='invalid',rewrite_generation=rewrite_generation+1 WHERE id=1")
            _check_owner(actual, identity)
