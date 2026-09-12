"""Lossless, disk-staged reference sets for the explicit C storage format.

This module only operates on the caller's private output connection.  It never
opens a legacy database, commits a transaction, or grants a verification proof.
The caller must hold a transaction and retain ownership of that connection for
the full lifetime of a read.  Public hashes establish equality, not authority.
Before BEGIN, the caller configures max_page_count within its input/workspace
limits, a negative cache_size of at most 8192 KiB, and mmap_size=0.  These local
settings are admission conditions, not a replacement for native RSS/CPU checks.

Input references are unique lowercase SHA-256 strings, in any order.  Sorting is
performed by an ordinary, on-disk staging table, not by a Python set or SQLite's
potentially in-memory TEMP store.  The caller owns the global multi-file budget;
each operation additionally checks this complete output database, its journal
files, and current free-space reserve against the passed (only tighter) limits.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields
import hashlib
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Iterable, Iterator
from uuid import uuid4

from model_artifacts import canonical_bytes
from context_runtime_transaction import TrackedConnection

from .contracts import (
    DEFAULT_LIMITS,
    StorageIntegrityError,
    StorageLimitError,
    StorageLimits,
)


FORMAT_VERSION = 2
_FORMAT = "betboy-reference-set-v2"
_BLOCK_DOMAIN = b"betboy-reference-block-v2\x00"
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_TABLES = {
    "v2_ref_blocks": (
        ("digest", "TEXT", 1),
        ("format_version", "INTEGER", 0),
        ("reference_count", "INTEGER", 0),
        ("encoded_bytes", "INTEGER", 0),
        ("content", "BLOB", 0),
    ),
    "v2_ref_sets": (
        ("set_digest", "TEXT", 1),
        ("format_version", "INTEGER", 0),
        ("canonical_digest", "TEXT", 0),
        ("reference_count", "INTEGER", 0),
        ("canonical_bytes", "INTEGER", 0),
        ("binary_bytes", "INTEGER", 0),
        ("block_count", "INTEGER", 0),
    ),
    "v2_ref_members": (
        ("set_digest", "TEXT", 1),
        ("block_index", "INTEGER", 2),
        ("block_digest", "TEXT", 0),
        ("reference_count", "INTEGER", 0),
        ("encoded_bytes", "INTEGER", 0),
    ),
    "v2_ref_staging": (
        ("stage_id", "TEXT", 1),
        ("digest", "BLOB", 2),
    ),
}
_SET_COLUMNS = (
    "format_version", "set_digest", "canonical_digest", "reference_count",
    "canonical_bytes", "binary_bytes", "block_count",
)


@dataclass(frozen=True)
class RefSetDescriptor:
    """A bounded descriptor; its complete ordered manifest remains on disk."""

    format_version: int
    set_digest: str
    canonical_digest: str
    reference_count: int
    canonical_bytes: int
    binary_bytes: int
    block_count: int


def _query(connection, sql, parameters=()):
    try:
        cursor = connection.cursor()
        cursor.row_factory = None
        return cursor.execute(sql, parameters)
    except sqlite3.DatabaseError as exc:
        raise StorageIntegrityError("reference storage query failed") from exc


def _require_connection(connection, limits):
    if type(connection) is not TrackedConnection:
        raise StorageIntegrityError("reference storage requires an exact tracked SQLite connection")
    if type(limits) is not StorageLimits:
        raise StorageLimitError("reference storage requires validated C limits")
    # Frozen dataclasses can still be forged through object.__setattr__/pickle;
    # every owning boundary revalidates the explicit envelope, not just __init__.
    StorageLimits.__post_init__(limits)
    if not connection.in_transaction:
        raise StorageIntegrityError("reference storage requires a caller-owned transaction")
    if connection.text_factory is not str:
        raise StorageIntegrityError("reference storage requires unchanged SQLite text decoding")
    if connection.row_factory not in (None, sqlite3.Row):
        raise StorageIntegrityError("reference storage requires an unchanged standard row factory")
    databases = tuple(_query(connection, "PRAGMA database_list"))
    if (
        not databases or len(databases) > 2 or databases[0][1] != "main" or not databases[0][2]
        or (len(databases) == 2 and (databases[1][1] != "temp" or databases[1][2]))
        or _query(connection, "SELECT 1 FROM temp.sqlite_schema LIMIT 1").fetchone()
    ):
        raise StorageIntegrityError("reference storage requires one private on-disk database")
    return Path(databases[0][2])


def _check_footprint(connection, limits):
    path = _require_connection(connection, limits)
    page_count = _query(connection, "PRAGMA main.page_count").fetchone()[0]
    page_size = _query(connection, "PRAGMA main.page_size").fetchone()[0]
    if type(page_count) is not int or type(page_size) is not int:
        raise StorageIntegrityError("invalid reference database page metadata")
    if page_count < 0 or page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
        raise StorageIntegrityError("invalid reference database page accounting")
    try:
        physical = path.stat().st_size
        companions = sum(
            candidate.stat().st_size
            for suffix in ("-wal", "-shm", "-journal")
            if (candidate := Path(str(path) + suffix)).exists()
        )
        free = shutil.disk_usage(path.parent).free
    except OSError as exc:
        raise StorageIntegrityError("reference output footprint could not be measured") from exc
    # page_count includes staging tables, indexes and free pages, not just blocks.
    logical = page_count * page_size
    if max(logical, physical) > limits.input_bytes:
        raise StorageLimitError("complete reference output exceeds the C input budget")
    if max(logical, physical) + companions > limits.workspace_bytes:
        raise StorageLimitError("reference output and journals exceed the C workspace budget")
    if free < limits.min_free_bytes:
        raise StorageLimitError("reference output violates the C free-space reserve")
    max_pages = _query(connection, "PRAGMA main.max_page_count").fetchone()[0]
    cache_size = _query(connection, "PRAGMA main.cache_size").fetchone()[0]
    mmap_size = _query(connection, "PRAGMA main.mmap_size").fetchone()[0]
    if type(max_pages) is not int or max_pages < page_count or max_pages * page_size > min(limits.input_bytes, limits.workspace_bytes):
        raise StorageLimitError("private reference connection needs a bounded max_page_count before BEGIN")
    if type(cache_size) is not int or not -8192 <= cache_size < 0:
        raise StorageLimitError("private reference connection needs an explicit bounded cache before BEGIN")
    if type(mmap_size) is not int or mmap_size != 0:
        raise StorageLimitError("private reference connection requires mmap_size=0 before BEGIN")


@contextmanager
def _atomic(connection, limits):
    _check_footprint(connection, limits)
    name = "v2_refs_" + uuid4().hex
    connection.execute(f"SAVEPOINT {name}")
    try:
        yield
        _check_footprint(connection, limits)
    except BaseException as exc:
        # SQLite can itself roll back the *whole* caller transaction on FULL or
        # I/O failure.  Do not hide that failure behind a missing-savepoint error;
        # the caller must abandon that unpublished build. Committed data remains.
        if connection.in_transaction:
            connection.execute(f"ROLLBACK TO {name}")
            connection.execute(f"RELEASE {name}")
        if isinstance(exc, sqlite3.DatabaseError):
            if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_FULL, sqlite3.SQLITE_TOOBIG):
                raise StorageLimitError("private reference output hit SQLite's hard allocation limit") from exc
            raise StorageIntegrityError("private reference output transaction failed") from exc
        raise
    else:
        connection.execute(f"RELEASE {name}")


def _check_schema(connection):
    names = {
        row[0] for row in _query(
            connection,
            "SELECT name FROM sqlite_schema WHERE name GLOB 'v2_ref_*' AND type='table' LIMIT 5",
        )
    }
    if names != set(_TABLES):
        raise StorageIntegrityError("incomplete or foreign reference storage schema")
    for table, expected in _TABLES.items():
        actual = tuple(_query(connection, f"PRAGMA main.table_xinfo({table})"))
        if len(actual) != len(expected):
            raise StorageIntegrityError("reference table has unexpected columns")
        for position, (row, column) in enumerate(zip(actual, expected)):
            name, declared_type, primary_key = column
            if row != (position, name, declared_type, 1, None, primary_key, 0):
                raise StorageIntegrityError("reference table column identity changed")
    if _query(
        connection,
        "SELECT 1 FROM sqlite_schema WHERE type='trigger' AND tbl_name GLOB 'v2_ref_*' LIMIT 1",
    ).fetchone():
        raise StorageIntegrityError("reference storage cannot contain triggers")


def _text_width(connection):
    encoding = _query(connection, "PRAGMA main.encoding").fetchone()
    widths = {"UTF-8": 1, "UTF-16le": 2, "UTF-16be": 2}
    if encoding is None or encoding[0] not in widths:
        raise StorageIntegrityError("reference storage has an unsupported text encoding")
    return widths[encoding[0]]


def _check_shapes(connection):
    width = _text_width(connection)
    # Inspect SQL types/lengths *before* materializing attacker-sized TEXT values.
    # This is deliberately separate from B's later whole-input authentication.
    predicates = {
        "v2_ref_blocks": (
            f"typeof(digest)!='text' OR length(digest)!=64 OR octet_length(digest)!={64 * width} OR "
            "typeof(format_version)!='integer' OR typeof(reference_count)!='integer' OR "
            "typeof(encoded_bytes)!='integer' OR typeof(content)!='blob'"
        ),
        "v2_ref_sets": (
            f"typeof(set_digest)!='text' OR length(set_digest)!=64 OR octet_length(set_digest)!={64 * width} OR "
            f"typeof(canonical_digest)!='text' OR length(canonical_digest)!=64 OR octet_length(canonical_digest)!={64 * width} OR "
            "typeof(format_version)!='integer' OR typeof(reference_count)!='integer' OR "
            "typeof(canonical_bytes)!='integer' OR typeof(binary_bytes)!='integer' OR "
            "typeof(block_count)!='integer'"
        ),
        "v2_ref_members": (
            f"typeof(set_digest)!='text' OR length(set_digest)!=64 OR octet_length(set_digest)!={64 * width} OR "
            f"typeof(block_digest)!='text' OR length(block_digest)!=64 OR octet_length(block_digest)!={64 * width} OR "
            "typeof(block_index)!='integer' OR typeof(reference_count)!='integer' OR "
            "typeof(encoded_bytes)!='integer'"
        ),
        "v2_ref_staging": (
            f"typeof(stage_id)!='text' OR length(stage_id)!=32 OR octet_length(stage_id)!={32 * width} OR "
            "typeof(digest)!='blob' OR length(digest)!=32"
        ),
    }
    for table, predicate in predicates.items():
        if _query(connection, f"SELECT 1 FROM {table} WHERE {predicate} LIMIT 1").fetchone():
            raise StorageIntegrityError("invalid reference SQL storage types or bounded key lengths")


def create_schema(connection) -> None:
    """Create only private v2 tables, atomically inside the caller transaction."""
    with _atomic(connection, DEFAULT_LIMITS):
        connection.execute(
            "CREATE TABLE IF NOT EXISTS v2_ref_blocks ("
            "digest TEXT NOT NULL PRIMARY KEY, format_version INTEGER NOT NULL, "
            "reference_count INTEGER NOT NULL, encoded_bytes INTEGER NOT NULL, "
            "content BLOB NOT NULL) WITHOUT ROWID"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS v2_ref_sets ("
            "set_digest TEXT NOT NULL PRIMARY KEY, format_version INTEGER NOT NULL, "
            "canonical_digest TEXT NOT NULL, reference_count INTEGER NOT NULL, "
            "canonical_bytes INTEGER NOT NULL, binary_bytes INTEGER NOT NULL, "
            "block_count INTEGER NOT NULL) WITHOUT ROWID"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS v2_ref_members ("
            "set_digest TEXT NOT NULL, block_index INTEGER NOT NULL, "
            "block_digest TEXT NOT NULL, reference_count INTEGER NOT NULL, "
            "encoded_bytes INTEGER NOT NULL, PRIMARY KEY(set_digest, block_index)) WITHOUT ROWID"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS v2_ref_staging ("
            "stage_id TEXT NOT NULL, digest BLOB NOT NULL, "
            "PRIMARY KEY(stage_id, digest)) WITHOUT ROWID"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS v2_ref_members_by_block "
            "ON v2_ref_members(block_digest, set_digest)"
        )
        _check_schema(connection)


def _digest(value, label):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise StorageIntegrityError(f"invalid {label} SHA-256 identity")
    return value


def _integer(value, label, *, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise StorageIntegrityError(f"invalid {label} integer storage type or range")
    return value


def _array_bytes(count):
    return 67 * count + 1 if count else 2


def _validate_descriptor(descriptor, limits):
    if type(descriptor) is not RefSetDescriptor:
        raise StorageIntegrityError("invalid reference set descriptor type")
    _integer(descriptor.format_version, "reference format", minimum=FORMAT_VERSION, maximum=FORMAT_VERSION)
    _digest(descriptor.set_digest, "reference set")
    _digest(descriptor.canonical_digest, "canonical reference array")
    count = _integer(descriptor.reference_count, "reference count")
    size = _integer(descriptor.canonical_bytes, "canonical reference byte count")
    binary = _integer(descriptor.binary_bytes, "binary reference byte count")
    blocks = _integer(descriptor.block_count, "reference block count")
    if size != _array_bytes(count) or binary != 32 * count or bool(count) != bool(blocks):
        raise StorageIntegrityError("inconsistent complete reference set descriptor")
    if blocks > count:
        raise StorageIntegrityError("empty reference block in set descriptor")
    if size > limits.input_bytes or binary > limits.input_bytes or blocks > limits.blocks_per_set:
        raise StorageLimitError("complete reference set descriptor exceeds C limits")


def _descriptor_from_row(row):
    if row is None or len(row) != len(_SET_COLUMNS):
        raise StorageIntegrityError("missing complete reference set descriptor")
    return RefSetDescriptor(*row)


def _block_digest(content):
    hasher = hashlib.sha256(_BLOCK_DOMAIN)
    hasher.update(content)
    return hasher.hexdigest()


def _read_block(connection, digest, limits):
    _digest(digest, "reference block")
    # Check SQL length and all metadata before asking sqlite3 to materialize BLOB.
    header = _query(
        connection,
        "SELECT digest, format_version, reference_count, encoded_bytes, typeof(content), length(content) "
        "FROM v2_ref_blocks WHERE digest=?", (digest,),
    ).fetchone()
    if header is None:
        raise StorageIntegrityError("missing reference block")
    key, version, count, encoded, storage_type, physical_size = header
    _digest(key, "stored reference block")
    _integer(version, "block format", minimum=FORMAT_VERSION, maximum=FORMAT_VERSION)
    _integer(count, "block reference count", minimum=1)
    _integer(encoded, "block encoded byte count", minimum=32)
    _integer(physical_size, "physical block byte count", minimum=32)
    if storage_type != "blob" or encoded != physical_size or encoded != count * 32:
        raise StorageIntegrityError("invalid reference block encoding metadata")
    if encoded > limits.block_bytes:
        raise StorageLimitError("reference block exceeds the C block budget")
    row = _query(connection, "SELECT content FROM v2_ref_blocks WHERE digest=?", (digest,)).fetchone()
    if row is None or type(row[0]) is not bytes or len(row[0]) != encoded:
        raise StorageIntegrityError("reference block changed while reading")
    content = row[0]
    if _block_digest(content) != digest:
        raise StorageIntegrityError("reference block content digest mismatch")
    previous = None
    for offset in range(0, len(content), 32):
        current = content[offset:offset + 32]
        if previous is not None and current <= previous:
            raise StorageIntegrityError("reference block is not strictly ordered and unique")
        previous = current
    return content


def _put_block(connection, content, limits):
    digest = _block_digest(content)
    stored = _query(connection, "SELECT 1 FROM v2_ref_blocks WHERE digest=?", (digest,)).fetchone()
    if stored is None:
        connection.execute(
            "INSERT INTO v2_ref_blocks VALUES (?, ?, ?, ?, ?)",
            (digest, FORMAT_VERSION, len(content) // 32, len(content), content),
        )
    elif _read_block(connection, digest, limits) != content:
        raise StorageIntegrityError("reference block identity collision")
    return digest, len(content) // 32, len(content)


def _manifest_digest(descriptor, members):
    """Hash the complete canonical manifest without constructing its array."""
    metadata = {
        field.name: getattr(descriptor, field.name)
        for field in fields(RefSetDescriptor) if field.name != "set_digest"
    }
    metadata["format"] = _FORMAT
    hasher = hashlib.sha256()
    hasher.update(b"{")
    for key_index, key in enumerate(sorted((*metadata, "blocks"))):
        if key_index:
            hasher.update(b",")
        hasher.update(canonical_bytes(key))
        hasher.update(b":")
        if key == "blocks":
            hasher.update(b"[")
            for member_index, member in enumerate(members):
                if member_index:
                    hasher.update(b",")
                block_index, digest, count, encoded = member
                hasher.update(canonical_bytes({
                    "block_index": block_index,
                    "block_digest": digest,
                    "reference_count": count,
                    "encoded_bytes": encoded,
                }))
            hasher.update(b"]")
        else:
            hasher.update(canonical_bytes(metadata[key]))
    hasher.update(b"}")
    return hasher.hexdigest()


def _members(connection, set_digest):
    return _query(
        connection,
        "SELECT block_index, block_digest, reference_count, encoded_bytes "
        "FROM v2_ref_members WHERE set_digest=? ORDER BY block_index", (set_digest,),
    )


def _read_descriptor(connection, set_digest):
    row = _query(
        connection,
        "SELECT " + ",".join(_SET_COLUMNS) + " FROM v2_ref_sets WHERE set_digest=?",
        (set_digest,),
    ).fetchone()
    return _descriptor_from_row(row)


def put_refset(connection, refs_iterable: Iterable[str], *, limits=DEFAULT_LIMITS) -> RefSetDescriptor:
    """Sort and seal one exact set; duplicate input is an error, not a union.

    Changes made by this call are rolled back on *any* failure.  Successful
    changes remain uncommitted in the caller's already active transaction.
    """
    _require_connection(connection, limits)
    _check_schema(connection)
    _check_shapes(connection)
    with _atomic(connection, limits):
        if _query(connection, "SELECT 1 FROM v2_ref_staging LIMIT 1").fetchone():
            raise StorageIntegrityError("reference storage contains an incomplete build")
        stage_id = uuid4().hex
        count = 0
        block_capacity = limits.block_bytes // 32
        for reference in refs_iterable:
            _digest(reference, "input reference")
            count += 1
            if not block_capacity or (count + block_capacity - 1) // block_capacity > limits.blocks_per_set:
                raise StorageLimitError("reference set exceeds the C block-count budget")
            if _array_bytes(count) > limits.input_bytes:
                raise StorageLimitError("canonical reference array exceeds the C input budget")
            try:
                connection.execute("INSERT INTO v2_ref_staging VALUES (?, ?)", (stage_id, bytes.fromhex(reference)))
            except sqlite3.IntegrityError as exc:
                raise StorageIntegrityError("duplicate reference in exact input set") from exc
            if count % 1024 == 0:
                _check_footprint(connection, limits)
        _check_footprint(connection, limits)
        hasher = hashlib.sha256(b"[")
        block = bytearray()
        # Only this explicitly bounded manifest is retained; references stay on disk.
        members = []
        cursor = _query(connection, "SELECT digest FROM v2_ref_staging WHERE stage_id=? ORDER BY digest", (stage_id,))
        for position, (digest,) in enumerate(cursor):
            if type(digest) is not bytes or len(digest) != 32:
                raise StorageIntegrityError("invalid staged reference storage type")
            if position:
                hasher.update(b",")
            hasher.update(b'"' + digest.hex().encode("ascii") + b'"')
            block.extend(digest)
            if len(block) == block_capacity * 32:
                members.append((len(members), *_put_block(connection, bytes(block), limits)))
                block.clear()
                _check_footprint(connection, limits)
        if block:
            members.append((len(members), *_put_block(connection, bytes(block), limits)))
            block.clear()
        hasher.update(b"]")
        provisional = RefSetDescriptor(
            FORMAT_VERSION, "0" * 64, hasher.hexdigest(), count,
            _array_bytes(count), count * 32, len(members),
        )
        descriptor = RefSetDescriptor(
            FORMAT_VERSION, _manifest_digest(provisional, iter(members)),
            provisional.canonical_digest, count, provisional.canonical_bytes,
            provisional.binary_bytes, provisional.block_count,
        )
        _validate_descriptor(descriptor, limits)
        existing = _query(connection, "SELECT 1 FROM v2_ref_sets WHERE set_digest=?", (descriptor.set_digest,)).fetchone()
        if existing:
            if _read_descriptor(connection, descriptor.set_digest) != descriptor:
                raise StorageIntegrityError("reference set identity collision")
        else:
            connection.execute(
                "INSERT INTO v2_ref_sets (" + ",".join(_SET_COLUMNS) + ") VALUES (?,?,?,?,?,?,?)",
                tuple(getattr(descriptor, column) for column in _SET_COLUMNS),
            )
            connection.executemany(
                "INSERT INTO v2_ref_members VALUES (?,?,?,?,?)",
                ((descriptor.set_digest, *member) for member in members),
            )
        connection.execute("DELETE FROM v2_ref_staging WHERE stage_id=?", (stage_id,))
        _verify_set(connection, descriptor, limits)
        return descriptor


def _verify_set(connection, descriptor, limits):
    _validate_descriptor(descriptor, limits)
    stored = _read_descriptor(connection, descriptor.set_digest)
    _validate_descriptor(stored, limits)
    if stored != descriptor:
        raise StorageIntegrityError("reference set descriptor does not match its generation")
    count = 0
    block_count = 0
    previous = None
    hasher = hashlib.sha256(b"[")
    for block_index, digest, expected_count, expected_bytes in _members(connection, descriptor.set_digest):
        _integer(block_index, "manifest block index")
        _integer(expected_count, "manifest reference count", minimum=1)
        _integer(expected_bytes, "manifest encoded bytes", minimum=32)
        if block_index != block_count or block_count >= limits.blocks_per_set:
            raise StorageIntegrityError("reference manifest has missing or additional block positions")
        block_count += 1
        content = _read_block(connection, digest, limits)
        if len(content) != expected_bytes or len(content) != expected_count * 32:
            raise StorageIntegrityError("reference manifest and block disagree")
        for offset in range(0, len(content), 32):
            current = content[offset:offset + 32]
            if previous is not None and current <= previous:
                raise StorageIntegrityError("reference set has duplicated or unordered membership")
            if count:
                hasher.update(b",")
            hasher.update(b'"' + current.hex().encode("ascii") + b'"')
            previous = current
            count += 1
        if count > descriptor.reference_count:
            raise StorageIntegrityError("reference manifest contains additional references")
    hasher.update(b"]")
    if count != descriptor.reference_count or block_count != descriptor.block_count:
        raise StorageIntegrityError("incomplete reference manifest membership")
    if hasher.hexdigest() != descriptor.canonical_digest:
        raise StorageIntegrityError("complete canonical reference array digest mismatch")
    if _manifest_digest(descriptor, _members(connection, descriptor.set_digest)) != descriptor.set_digest:
        raise StorageIntegrityError("complete reference manifest digest mismatch")


def _generation(connection, limits=DEFAULT_LIMITS):
    if type(limits) is not StorageLimits:
        raise StorageLimitError("reference generation requires exact C limits")
    StorageLimits.__post_init__(limits)
    return (
        connection.transaction_generation,
        connection.total_changes,
        connection.row_factory,
        connection.text_factory,
        _query(connection, "PRAGMA main.data_version").fetchone()[0],
        _query(connection, "PRAGMA main.schema_version").fetchone()[0],
        _query(connection, "PRAGMA temp.schema_version").fetchone()[0],
        _query(connection, "PRAGMA main.max_page_count").fetchone()[0],
        _query(connection, "PRAGMA main.cache_size").fetchone()[0],
        _query(connection, "PRAGMA main.mmap_size").fetchone()[0],
        limits,
        tuple((field.name, getattr(limits, field.name)) for field in fields(StorageLimits)),
    )


def _assert_reader(connection, generation):
    if connection.transaction_generation != generation[0]:
        raise StorageIntegrityError("reference reader lost its tracked transaction generation")
    if (
        not connection.in_transaction
        or connection.total_changes != generation[1]
        or connection.row_factory is not generation[2]
        or connection.text_factory is not generation[3]
    ):
        raise StorageIntegrityError("reference reader lost its caller-owned generation")
    # DDL does not increment total_changes or end a transaction.  Check both
    # schemas before *each* yield, never only at the end of a large block.
    if _generation(connection, generation[10]) != generation:
        raise StorageIntegrityError("reference reader schema or snapshot generation changed")


def iter_refset(connection, descriptor: RefSetDescriptor, *, limits=DEFAULT_LIMITS) -> Iterator[str]:
    """Return a fresh iterator; validate the *whole* set before the first value.

    Iteration requires an unchanged caller-owned transaction.  An application
    must create another iterator to read again; it must not share this connection
    with mutation or close/commit its transaction while an iterator is in use.
    """
    _require_connection(connection, limits)
    _check_schema(connection)
    _check_footprint(connection, limits)
    _check_shapes(connection)
    generation = _generation(connection, limits)
    _verify_set(connection, descriptor, limits)
    if _generation(connection, limits) != generation:
        raise StorageIntegrityError("reference generation changed during complete verification")
    for _index, digest, _count, _bytes in _members(connection, descriptor.set_digest):
        content = _read_block(connection, digest, limits)
        for offset in range(0, len(content), 32):
            _assert_reader(connection, generation)
            yield content[offset:offset + 32].hex()
        _assert_reader(connection, generation)
        if _generation(connection, limits) != generation:
            raise StorageIntegrityError("reference generation changed during iteration")
    _assert_reader(connection, generation)
    if _generation(connection, limits) != generation:
        raise StorageIntegrityError("reference generation changed before iteration completed")


def validate_all(connection, *, limits=DEFAULT_LIMITS) -> None:
    """Check every set and block, all keys, and absence of incomplete/orphan rows."""
    _require_connection(connection, limits)
    _check_schema(connection)
    _check_footprint(connection, limits)
    _check_shapes(connection)
    generation = _generation(connection, limits)
    if _query(connection, "SELECT 1 FROM v2_ref_staging LIMIT 1").fetchone():
        raise StorageIntegrityError("reference store contains an incomplete generation")
    if _query(
        connection,
        "SELECT 1 FROM v2_ref_members m LEFT JOIN v2_ref_sets s ON s.set_digest=m.set_digest "
        "WHERE s.set_digest IS NULL LIMIT 1",
    ).fetchone():
        raise StorageIntegrityError("reference store contains foreign manifest membership")
    if _query(
        connection,
        "SELECT 1 FROM v2_ref_blocks b WHERE NOT EXISTS "
        "(SELECT 1 FROM v2_ref_members m WHERE m.block_digest=b.digest) LIMIT 1",
    ).fetchone():
        raise StorageIntegrityError("reference store contains an unreachable additional block")
    for (digest,) in _query(connection, "SELECT digest FROM v2_ref_blocks ORDER BY digest"):
        _read_block(connection, digest, limits)
    for row in _query(connection, "SELECT " + ",".join(_SET_COLUMNS) + " FROM v2_ref_sets ORDER BY set_digest"):
        _verify_set(connection, _descriptor_from_row(row), limits)
    _assert_reader(connection, generation)
    if _generation(connection, limits) != generation:
        raise StorageIntegrityError("reference store changed during full validation")
    _check_footprint(connection, limits)
