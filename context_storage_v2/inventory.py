"""Complete typed, uncached raw inventory for the explicit v2 copy boundary.

This establishes logical byte identity, NOT source truth, D2 authority, semantic
replay, a validation checkpoint, or a filesystem seal. Callers own the sealed
input and complete resource accounting across all input/output databases.
Every physical table is scanned, including unreferenced/future/other-tour rows.
Large TEXT/BLOB fields are read incrementally; old JSON bytes are never rewritten.
"""
from dataclasses import dataclass
import hashlib
import sqlite3
import struct

from context_runtime import _verify_schema
from context_runtime_transaction import TrackedConnection
from model_artifacts import canonical_bytes

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits


# This is the old, closed owning schema, not a caller-controlled SQL identifier.
_TABLES = {
    "active_manifest": (("id", "integer", False), ("digest", "text", False)),
    "artifacts": (("digest", "text", False), ("kind", "text", False),
                  ("payload", "blob", False), ("created_at", "text", False)),
    "context_contents": (("content_digest", "text", False), ("payload", "blob", False)),
    "context_model_rollbacks": (("digest", "text", False), ("payload", "blob", False)),
    "context_observations": tuple((name, "text", False) for name in (
        "digest", "content_digest", "event_key", "observed_at", "schedule_revision",
        "source", "subject_id", "kind")),
    "context_snapshots": (("key", "text", False), ("payload", "blob", False),
                          ("payload_digest", "text", False)),
    "manifests": (("digest", "text", False), ("predecessor", "text", True),
                  ("payload", "blob", False), ("published_at", "text", False)),
}
_EXECUTE = TrackedConnection.execute
_CURSOR = TrackedConnection.cursor
_BLOBOPEN = TrackedConnection.blobopen
_TAGS = {"null": b"N", "integer": b"I", "text": b"T", "blob": b"B"}
_SCHEMA_BYTES = 64 * 1024


@dataclass(frozen=True)
class TableInventory:
    name: str
    row_count: int
    value_bytes: int
    row_digest: str


@dataclass(frozen=True)
class RawInventory:
    format_version: int
    schema_digest: str
    tables: tuple[TableInventory, ...]
    value_bytes: int
    logical_digest: str


class _HeldRead:
    def __init__(self, connection):
        self.connection = connection
        self.failed = False
        self.stamp = self._current()

    def _current(self):
        con = self.connection
        if (type(con) is not TrackedConnection or not con.in_transaction
                or con.row_factory is not None or con.text_factory is not str
                or TrackedConnection.execute is not _EXECUTE
                or TrackedConnection.cursor is not _CURSOR
                or TrackedConnection.blobopen is not _BLOBOPEN
                or any(name in con.__dict__ for name in ("execute", "cursor", "blobopen"))):
            raise StorageIntegrityError("raw inventory requires its unmodified held reader")
        generation, changes = con.transaction_generation, con.total_changes
        if con.execute("PRAGMA query_only").fetchone() != (1,):
            raise StorageIntegrityError("raw inventory requires read-only admission")
        if con.execute("PRAGMA trusted_schema").fetchone() != (0,):
            raise StorageIntegrityError("raw inventory requires untrusted schema execution")
        databases = con.execute("PRAGMA database_list").fetchall()
        if any(row[1] not in {"main", "temp"} for row in databases):
            raise StorageIntegrityError("raw inventory rejects attached databases")
        functions = con.execute("PRAGMA function_list").fetchmany(1025)
        if len(functions) > 1024 or any(
                row[1] != 1 and row[0].casefold() in
                {"octet_length", "typeof", "coalesce", "sum", "count"}
                for row in functions):
            raise StorageIntegrityError("raw inventory requires unchanged core SQL functions")
        main = con.execute("PRAGMA main.schema_version").fetchone()[0]
        temp = con.execute("PRAGMA temp.schema_version").fetchone()[0]
        if ((con.transaction_generation, con.total_changes) != (generation, changes)
                or not con.in_transaction or con.row_factory is not None
                or con.text_factory is not str):
            raise StorageIntegrityError("raw inventory reader changed during admission")
        return generation, changes, main, temp

    def check(self):
        try:
            if self.failed or self._current() != self.stamp:
                raise StorageIntegrityError("raw inventory reader changed")
        except (sqlite3.Error, StorageIntegrityError):
            self.failed = True
            raise


def _size(connection, limits):
    page_count = connection.execute("PRAGMA main.page_count").fetchone()[0]
    page_size = connection.execute("PRAGMA main.page_size").fetchone()[0]
    if (type(page_count) is not int or type(page_size) is not int
            or page_count < 1 or page_size < 512):
        raise StorageIntegrityError("raw inventory has invalid image dimensions")
    if page_count * page_size > limits.input_bytes:
        raise StorageLimitError("raw input image exceeds v2 input admission")


def _schema(connection, guard):
    # Bound metadata BEFORE the old owning schema parser loads it. The limit is
    # on the closed schema alone, not on a historically unrestricted SQL value.
    meta_size, count = connection.execute(
        "SELECT coalesce(sum(octet_length(sql)),0), count(*) FROM main.sqlite_schema"
    ).fetchone()
    if type(meta_size) is not int or meta_size > _SCHEMA_BYTES or count > 32:
        raise StorageIntegrityError("raw inventory schema metadata is not bounded")
    # The unchanged legacy owner collects FK errors. Refuse on its first
    # physical violation before calling it, so a corrupt multi-GiB input cannot
    # allocate a list containing every bad row merely to report failure.
    cursor = connection.execute("PRAGMA foreign_key_check")
    try:
        if cursor.fetchone() is not None:
            raise StorageIntegrityError("raw inventory has a foreign-key violation")
    finally:
        cursor.close()
    seen = _verify_schema(connection)
    rows = connection.execute(
        "SELECT type,name,tbl_name,sql FROM main.sqlite_schema ORDER BY type,name"
    ).fetchall()
    encoding = connection.execute("PRAGMA encoding").fetchone()[0]
    if encoding not in {"UTF-8", "UTF-16le", "UTF-16be"}:
        raise StorageIntegrityError("raw inventory has unsupported text encoding")
    guard.check()
    schema = {"format_version": 1, "encoding": encoding, "schema": rows,
              "user_version": 0, "application_id": 0}
    return seen, hashlib.sha256(canonical_bytes(schema)).hexdigest()


def _raw_rows(connection, table, columns, limit):
    # octet_length(column) obtains stored byte lengths without loading the whole
    # large value. SQLite >=3.43 is an explicit capability of this NEW mode.
    # Both deployed 3.45.1 and the local runtime expose it. No legacy fallback.
    sizes = [f'coalesce(octet_length("{name}"),0)' for name, _, _ in columns]
    small = " + ".join(sizes) + " <= ?"
    expressions = ["rowid"]
    for name, kind, _ in columns:
        value = f'"{name}"' if kind == "integer" else f'CAST("{name}" AS BLOB)'
        expressions += [f'typeof("{name}")', f'octet_length("{name}")',
                        f'CASE WHEN {small} THEN {value} ELSE NULL END']
    query = (f'SELECT {", ".join(expressions)} FROM main."{table}" '
             f'ORDER BY "{columns[0][0]}" COLLATE BINARY')
    return connection.execute(query, (limit,) * len(columns))


def _field_hash(connection, guard, table, rowid, name, kind, size, value,
                row_hash, limits):
    if kind == "null":
        if size is not None or value is not None:
            raise StorageIntegrityError("raw inventory NULL changed storage type")
        row_hash.update(b"N")
        return 0
    if type(size) is not int or size < 0 or size > limits.input_bytes:
        raise StorageLimitError("raw inventory field length exceeds admission")
    if kind == "integer":
        if value is None:
            value = connection.execute(
                f'SELECT "{name}" FROM main."{table}" WHERE rowid=?', (rowid,)
            ).fetchone()[0]
        if type(value) is not int:
            raise StorageIntegrityError("raw inventory integer must not be coerced")
        row_hash.update(b"I" + struct.pack(">q", value))
        return 8
    row_hash.update(_TAGS[kind] + struct.pack(">Q", size))
    if value is not None:
        if type(value) is not bytes or len(value) != size or size > limits.block_bytes:
            raise StorageIntegrityError("raw inventory inline bytes changed")
        row_hash.update(value)
    elif size:
        guard.check()
        with connection.blobopen(table, name, rowid, readonly=True) as blob:
            if len(blob) != size:
                raise StorageIntegrityError("raw inventory incremental value changed")
            remaining = size
            while remaining:
                guard.check()
                part = blob.read(min(remaining, limits.block_bytes))
                if not part or len(part) > limits.block_bytes:
                    raise StorageIntegrityError("raw inventory value was truncated")
                remaining -= len(part)
                row_hash.update(part)
            if blob.read(1):
                raise StorageIntegrityError("raw inventory value grew")
        guard.check()
    return size


def inventory_raw(connection, *, limits=DEFAULT_LIMITS):
    """Return a complete fresh identity, never a semantic/provenance approval.

The caller must hold an unchanged read-only TrackedConnection transaction from
the sealed input owner. No source connection commits, writes, pragmas or cache
entries are introduced. Metadata and value chunks, not the corpus, occupy RAM.
The returned immutable digest is historical evidence; it is NOT a reusable view
or permission to reuse a proof after the held transaction ends.
"""
    if type(limits) is not StorageLimits:
        raise StorageLimitError("raw inventory requires the approved exact resource envelope")
    StorageLimits.__post_init__(limits)
    guard = _HeldRead(connection)
    try:
        _size(connection, limits)
        seen, schema_digest = _schema(connection, guard)
        tables, total = [], 0
        for table, columns in sorted(_TABLES.items()):
            if table not in seen:
                continue
            table_hash = hashlib.sha256(b"betboy-context-v2-table\0" + table.encode("ascii"))
            row_count, value_bytes = 0, 0
            cursor = _raw_rows(connection, table, columns, limits.block_bytes)
            try:
                for raw in cursor:
                    if row_count % 256 == 0:
                        guard.check()
                    rowid = raw[0]
                    if type(rowid) is not int:
                        raise StorageIntegrityError("raw inventory row identity is not integer")
                    row_hash = hashlib.sha256(b"betboy-context-v2-row\0")
                    for index, (name, expected, nullable) in enumerate(columns):
                        kind, size, value = raw[1 + index * 3:4 + index * 3]
                        if kind != expected and not (nullable and kind == "null"):
                            raise StorageIntegrityError("raw inventory rejects SQLite storage coercion")
                        value_bytes += _field_hash(connection, guard, table, rowid, name,
                                                   kind, size, value, row_hash, limits)
                    row_count += 1
                    table_hash.update(row_hash.digest())
                    if total + value_bytes > limits.input_bytes:
                        raise StorageLimitError("raw inventory cumulative values exceed admission")
            finally:
                cursor.close()
            table_hash.update(struct.pack(">Q", row_count))
            total += value_bytes
            tables.append(TableInventory(table, row_count, value_bytes, table_hash.hexdigest()))
            guard.check()
        guard.check()
        _size(connection, limits)
        manifest = {"format_version": 1, "schema_digest": schema_digest,
                    "tables": [vars(table) for table in tables], "value_bytes": total}
        result = RawInventory(1, schema_digest, tuple(tables), total,
                              hashlib.sha256(canonical_bytes(manifest)).hexdigest())
        guard.check()
        return result
    except sqlite3.Error as exc:
        raise StorageIntegrityError("complete raw inventory could not be established") from exc


def compare_raw(source, copied, *, limits=DEFAULT_LIMITS):
    """Independently rescan both complete held inputs and require byte identity."""
    source_guard, copy_guard = _HeldRead(source), _HeldRead(copied)
    left = inventory_raw(source, limits=limits)
    right = inventory_raw(copied, limits=limits)
    source_guard.check()
    copy_guard.check()
    if left != right:
        raise StorageIntegrityError("complete typed raw copy differs from its source")
    return left
