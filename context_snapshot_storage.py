"""Lossless physical sharing of large snapshot reference lists.

This changes storage only. Snapshot keys, canonical logical payloads and their
existing digests remain identical. Legacy JSON blobs remain readable. Shared
lists contain ordered binary SHA256 values, never model/source approvals.
"""
import hashlib
import sqlite3
import re

from context_models.contracts import ContextIntegrityError, require_digest, require_object
from model_artifacts import _decode_object, canonical_bytes


MAGIC = b"BETBOY-SNAPSHOT-REFS-1\n"
REFERENCE_SQL = """CREATE TABLE context_snapshot_references (
    digest TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL)"""
BLOCK_SQL = """CREATE TABLE context_snapshot_reference_blocks (
    digest TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL)"""
BLOCK_MAGIC = b"BETBOY-REFERENCE-BLOCKS-1\n"
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def create_schema(connection):
    connection.execute(REFERENCE_SQL.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))
    connection.execute(BLOCK_SQL.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))


def pack_payload(payload):
    """Return physical bytes plus an optional shared list, without any IO."""
    refs = payload.get("observation_refs")
    if (type(refs) is not list or len(refs) < 128
            or any(type(ref) is not str or _HASH.fullmatch(ref) is None for ref in refs)):
        return canonical_bytes(payload), None
    # A whole-history count limit must never select the larger inline format.
    # Individual stored blocks remain bounded; later analyses share them even
    # after the history grows beyond the former 500,000-reference threshold.
    binary = b"".join(bytes.fromhex(ref) for ref in refs)
    ref_hash = hashlib.sha256(binary).hexdigest()
    header = {name: value for name, value in payload.items() if name != "observation_refs"}
    return MAGIC + canonical_bytes({"header": header, "refs_digest": ref_hash}), (ref_hash, binary)


def store_references(connection, reference):
    if reference is None:
        return
    ref_hash, binary = reference
    sorted_refs = all(binary[i-32:i] <= binary[i:i+32] for i in range(32, len(binary), 32))
    # Stable hash-prefix buckets: a new receipt changes only its bucket,
    # not every later fixed-offset chunk in the sorted tour history.
    # Arbitrarily ordered generic lists keep their exact order in bounded blocks.
    chunks, start = [], 0
    for offset in range(32, len(binary)+32, 32):
        if offset == len(binary) or offset-start >= 64*1024 or (sorted_refs and binary[offset] != binary[start]):
            chunk = binary[start:offset]
            chunk_hash = hashlib.sha256(chunk).hexdigest()
            _put_exact(connection, "context_snapshot_reference_blocks", chunk_hash, chunk)
            chunks.append(bytes.fromhex(chunk_hash))
            start = offset
    physical = BLOCK_MAGIC + len(binary).to_bytes(8, "big") + b"".join(chunks)
    _put_exact(connection, "context_snapshot_references", ref_hash, physical)
    if _reference_bytes(connection, ref_hash) != binary:
        raise ContextIntegrityError("shared snapshot reference identity collision")


def _put_exact(connection, table, key, payload):
    connection.execute(f"INSERT OR IGNORE INTO {table} VALUES (?,?)", (key, payload))
    if _read_blob(connection, table, key) != payload:
        raise ContextIntegrityError("shared snapshot storage identity collision")


def _read_blob(connection, table, key):
    try:
        shape = connection.execute(f"SELECT typeof(payload),length(CAST(payload AS BLOB)) FROM {table} WHERE digest=?", (key,)).fetchone()
        if shape is None or shape[0] != "blob" or not 0 < shape[1] <= 500_000*32:
            raise ContextIntegrityError("shared snapshot references missing or malformed")
        stored = connection.execute(f"SELECT payload FROM {table} WHERE digest=?", (key,)).fetchone()
    except sqlite3.Error as exc:
        raise ContextIntegrityError("shared snapshot reference storage is invalid") from exc
    return stored[0]


def _reference_bytes(connection, ref_hash):
    binary = _read_blob(connection, "context_snapshot_references", ref_hash)
    if binary.startswith(BLOCK_MAGIC):
        expected = int.from_bytes(binary[len(BLOCK_MAGIC):len(BLOCK_MAGIC)+8], "big")
        refs = binary[len(BLOCK_MAGIC)+8:]
        # Bound the declared output by the actual, bounded block descriptor,
        # not a historical total-list cutoff. Each listed block must contribute
        # between one SHA256 and 64 KiB, verified again while reading below.
        block_count = len(refs) // 32
        if (expected < 128*32 or expected % 32 or not refs or len(refs) % 32
                or not block_count*32 <= expected <= block_count*64*1024):
            raise ContextIntegrityError("invalid shared reference block descriptor")
        result = bytearray()
        for i in range(0, len(refs), 32):
            key = refs[i:i+32].hex()
            chunk = _read_blob(connection, "context_snapshot_reference_blocks", key)
            if len(chunk) > 64*1024 or len(chunk) % 32 or hashlib.sha256(chunk).hexdigest() != key:
                raise ContextIntegrityError("shared reference block is corrupt")
            result.extend(chunk)
            if len(result) > expected:
                raise ContextIntegrityError("shared reference blocks exceed declared length")
        if len(result) != expected:
            raise ContextIntegrityError("shared reference blocks are truncated")
        binary = bytes(result)
    if len(binary) < 128*32 or len(binary) % 32 or hashlib.sha256(binary).hexdigest() != ref_hash:
        raise ContextIntegrityError("shared snapshot references missing or corrupt")
    return binary


def freeze_reference_bytes(payload, connection):
    """Copy just physical reference bytes while the caller holds its image."""
    if type(payload) is not bytes or not payload.startswith(MAGIC):
        return None
    envelope = _decode_object(payload[len(MAGIC):], label="shared snapshot header")
    require_object(envelope, {"header", "refs_digest"}, label="shared snapshot header")
    return _reference_bytes(connection, require_digest(envelope["refs_digest"]))


def unpack_payload(payload, connection, reference_data=None):
    if type(payload) is not bytes or not payload.startswith(MAGIC):
        return _decode_object(payload, label="context snapshot")
    if connection is None and reference_data is None:
        raise ContextIntegrityError("shared snapshot requires its owning database transaction")
    envelope = _decode_object(payload[len(MAGIC):], label="shared snapshot header")
    require_object(envelope, {"header", "refs_digest"}, label="shared snapshot header")
    header, ref_hash = envelope["header"], require_digest(envelope["refs_digest"])
    if type(header) is not dict or "observation_refs" in header:
        raise ContextIntegrityError("invalid shared snapshot header fields")
    binary = _reference_bytes(connection, ref_hash) if reference_data is None else reference_data
    if (type(binary) is not bytes or len(binary) < 128*32
            or len(binary) % 32 or hashlib.sha256(binary).hexdigest() != ref_hash):
        raise ContextIntegrityError("frozen snapshot reference identity differs")
    return {**header, "observation_refs": [binary[index:index+32].hex() for index in range(0, len(binary), 32)]}


def verify_reference_storage(connection, tables):
    """Bounded structural/link checks, not historical model recalculation."""
    refs = set()
    if "context_snapshot_references" in tables:
        for (ref,) in connection.execute("SELECT digest FROM context_snapshot_references"):
            require_digest(ref)
            _reference_bytes(connection, ref)
            refs.add(ref)
    if "context_snapshot_reference_blocks" in tables:
        for (ref,) in connection.execute("SELECT digest FROM context_snapshot_reference_blocks"):
            require_digest(ref)
            chunk = _read_blob(connection, "context_snapshot_reference_blocks", ref)
            if len(chunk) > 64*1024 or len(chunk) % 32 or hashlib.sha256(chunk).hexdigest() != ref:
                raise ContextIntegrityError("invalid stored reference block")
    if "context_snapshots" in tables:
        for (raw,) in connection.execute("SELECT payload FROM context_snapshots WHERE substr(payload,1,?)=?", (len(MAGIC), MAGIC)):
            envelope = _decode_object(raw[len(MAGIC):], label="shared snapshot header")
            require_object(envelope, {"header", "refs_digest"}, label="shared snapshot header")
            if type(envelope["header"]) is not dict or "observation_refs" in envelope["header"] or envelope["refs_digest"] not in refs:
                raise ContextIntegrityError("shared snapshot has an invalid reference link")


def compact_snapshots(path, *, vacuum=False, inline_only=False):
    """Atomic lossless repacking; caller stops writers and owns recovery policy.

    Validate each selected old and reconstructed logical payload. Any broken
    selected row rolls back the complete transaction. VACUUM only reclaims
    unused SQLite pages. inline_only leaves existing shared snapshots untouched
    instead of decoding their histories again; logical bytes cover selected rows.
    """
    from contextlib import closing
    from context_snapshots import _compute_lock, _connect, _decode_snapshot
    from context_json import canonical_context_bytes
    from pathlib import Path

    before = Path(path).stat().st_size
    converted = logical_bytes = 0
    with _compute_lock(path) as (path, check_lock), closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            query = "SELECT key,payload,payload_digest FROM context_snapshots"
            parameters = ()
            if inline_only:
                query += " WHERE substr(payload,1,?) != ?"
                parameters = (len(MAGIC), MAGIC)
            for key, raw, payload_hash in connection.execute(query, parameters):
                logical = _decode_snapshot(key, raw, payload_hash, connection=connection)
                logical_bytes += len(canonical_context_bytes(logical))
                packed, reference = pack_payload(logical)
                if reference is None or packed == raw:
                    continue
                store_references(connection, reference)
                if canonical_context_bytes(_decode_snapshot(key, packed, payload_hash, connection=connection)) != canonical_context_bytes(logical):
                    raise ContextIntegrityError("snapshot compaction changed logical bytes")
                connection.execute("UPDATE context_snapshots SET payload=? WHERE key=?", (packed, key))
                converted += 1
            check_lock()
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ContextIntegrityError("SQLite integrity check before compaction commit failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ContextIntegrityError("SQLite reference check before compaction commit failed")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        if vacuum:
            connection.execute("VACUUM")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ContextIntegrityError("SQLite integrity check after compaction failed")
        count, stored_bytes = connection.execute("SELECT count(*),coalesce(sum(length(payload)),0) FROM context_snapshot_references").fetchone()
        block_count, block_bytes = connection.execute("SELECT count(*),coalesce(sum(length(payload)),0) FROM context_snapshot_reference_blocks").fetchone()
        snapshot_bytes = connection.execute("SELECT coalesce(sum(length(payload)),0) FROM context_snapshots").fetchone()[0]
    return {"converted_snapshots": converted, "logical_snapshot_bytes": logical_bytes,
            "shared_reference_sets": count, "shared_reference_bytes": stored_bytes,
            "shared_reference_blocks": block_count, "shared_reference_block_bytes": block_bytes,
            "stored_snapshot_bytes": snapshot_bytes, "database_bytes_before": before,
            "database_bytes_after": Path(path).stat().st_size}
