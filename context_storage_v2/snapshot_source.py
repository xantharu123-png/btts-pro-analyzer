"""Bounded adaptation of every real legacy snapshot in one held raw source.

The source is never opened, changed, committed, or replaced here. A fresh whole
raw inventory precedes any output, and the snapshot scan repeats that owner's
typed row/table framing. Unadapted rows retain full raw identities and require
the original source; neither this ledger nor C2b is a B/HMAC/D2/model approval.

Only the canonical top-level observation_refs array is streamed into C2. The
small remaining header is parsed by the existing snapshot owner. The scanner
below only locates lexical boundaries; it is not a general JSON decoder.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass
from functools import wraps
import hashlib
from pathlib import Path
import sqlite3
import struct
from uuid import uuid4

from model_artifacts import canonical_bytes

from . import inventory, refs, snapshots
from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from .inventory import RawInventory, TableInventory


FORMAT_VERSION = 2
_FORMAT = "betboy-snapshot-source-coverage-v2"
_TABLE = "context_snapshots"
_ZERO = "0" * 64
_CHUNK_BYTES = 64 * 1024
_REASONS = frozenset({"unknown-header", "header-limit", "invalid-key", "invalid-payload-digest"})
_ROW_COLUMNS = (
    "key_field_digest", "key_bytes", "payload_digest_field_digest", "payload_digest_bytes",
    "source_row_digest", "raw_payload_sha256", "payload_bytes", "status", "reason",
    "parts_key", "parts_descriptor_digest",
)
_MANIFEST_COLUMNS = (
    "id", "format_version", "source_inventory_digest", "source_schema_digest",
    "snapshot_table_present", "snapshot_count", "snapshot_value_bytes", "snapshot_row_digest",
    "adapted_count", "unadapted_count", "coverage_digest", "descriptor_digest",
)
_INTEGER_COLUMNS = frozenset({
    "id", "format_version", "key_bytes", "payload_digest_bytes", "payload_bytes",
    "snapshot_table_present", "snapshot_count", "snapshot_value_bytes", "adapted_count",
    "unadapted_count",
})
_TABLES = {
    "v2_snap_source_rows": tuple((name, "INTEGER" if name in _INTEGER_COLUMNS else "TEXT",
                                   int(name == "key_field_digest")) for name in _ROW_COLUMNS),
    "v2_snap_source_manifest": tuple((name, "INTEGER" if name in _INTEGER_COLUMNS else "TEXT",
                                       int(name == "id")) for name in _MANIFEST_COLUMNS),
}


@dataclass(frozen=True)
class CoverageDescriptor:
    format_version: int
    source_inventory: RawInventory
    snapshot_table_present: bool
    snapshot_count: int
    snapshot_value_bytes: int
    snapshot_row_digest: str
    adapted_count: int
    unadapted_count: int
    coverage_digest: str
    descriptor_digest: str


class _Unadapted(Exception):
    def __init__(self, reason):
        self.reason = reason


def _table_inventory(raw):
    return next((table for table in raw.tables if table.name == _TABLE), None)


def _validate_inventory(raw):
    if type(raw) is not RawInventory or type(raw.tables) is not tuple or len(raw.tables) > len(inventory._TABLES):
        raise StorageIntegrityError("snapshot source requires a complete exact raw inventory")
    refs._integer(raw.format_version, "source inventory version", minimum=1, maximum=1)
    refs._digest(raw.schema_digest, "source schema")
    refs._digest(raw.logical_digest, "source inventory")
    refs._integer(raw.value_bytes, "source inventory bytes")
    previous, total = "", 0
    for table in raw.tables:
        if type(table) is not TableInventory or type(table.name) is not str or table.name not in inventory._TABLES or table.name <= previous:
            raise StorageIntegrityError("snapshot source inventory has foreign or unordered tables")
        refs._integer(table.row_count, "source table count")
        refs._integer(table.value_bytes, "source table bytes")
        refs._digest(table.row_digest, "source table")
        previous, total = table.name, total + table.value_bytes
    manifest = {"format_version": 1, "schema_digest": raw.schema_digest,
                "tables": [vars(table) for table in raw.tables], "value_bytes": total}
    if raw.value_bytes != total or hashlib.sha256(canonical_bytes(manifest)).hexdigest() != raw.logical_digest:
        raise StorageIntegrityError("snapshot source inventory descriptor is inconsistent")


def _descriptor_digest(descriptor):
    values = asdict(descriptor)
    del values["descriptor_digest"]
    values["format"] = _FORMAT
    return hashlib.sha256(canonical_bytes(values)).hexdigest()


def _validate_descriptor(descriptor):
    if type(descriptor) is not CoverageDescriptor:
        raise StorageIntegrityError("invalid snapshot source coverage descriptor")
    refs._integer(descriptor.format_version, "source coverage version", minimum=FORMAT_VERSION, maximum=FORMAT_VERSION)
    _validate_inventory(descriptor.source_inventory)
    if type(descriptor.snapshot_table_present) is not bool:
        raise StorageIntegrityError("snapshot source table presence must be explicit")
    for name in ("snapshot_count", "snapshot_value_bytes", "adapted_count", "unadapted_count"):
        refs._integer(getattr(descriptor, name), "coverage " + name)
    for name in ("snapshot_row_digest", "coverage_digest", "descriptor_digest"):
        refs._digest(getattr(descriptor, name), "coverage " + name)
    table = _table_inventory(descriptor.source_inventory)
    if (descriptor.snapshot_table_present != (table is not None)
            or descriptor.snapshot_count != (0 if table is None else table.row_count)
            or descriptor.snapshot_value_bytes != (0 if table is None else table.value_bytes)
            or descriptor.snapshot_row_digest != (_ZERO if table is None else table.row_digest)
            or descriptor.adapted_count + descriptor.unadapted_count != descriptor.snapshot_count
            or _descriptor_digest(descriptor) != descriptor.descriptor_digest):
        raise StorageIntegrityError("snapshot source complete coverage descriptor disagrees")


def _manifest_row(descriptor):
    return (
        1, descriptor.format_version, descriptor.source_inventory.logical_digest,
        descriptor.source_inventory.schema_digest, int(descriptor.snapshot_table_present),
        descriptor.snapshot_count, descriptor.snapshot_value_bytes, descriptor.snapshot_row_digest,
        descriptor.adapted_count, descriptor.unadapted_count, descriptor.coverage_digest,
        descriptor.descriptor_digest,
    )


def _check_schema(output):
    names = {row[0] for row in refs._query(output,
        "SELECT name FROM main.sqlite_schema WHERE type='table' AND name GLOB 'v2_snap_source_*' LIMIT 3")}
    if names != set(_TABLES):
        raise StorageIntegrityError("incomplete or foreign snapshot source coverage schema")
    for name, columns in _TABLES.items():
        actual = tuple(refs._query(output, f"PRAGMA main.table_xinfo({name})"))
        expected = tuple((index, key, kind, 1, None, pk, 0)
                         for index, (key, kind, pk) in enumerate(columns))
        if actual != expected:
            raise StorageIntegrityError("snapshot source coverage column identity changed")
    if refs._query(output, "SELECT 1 FROM main.sqlite_schema WHERE type='trigger' "
                   "AND tbl_name GLOB 'v2_snap_source_*' LIMIT 1").fetchone():
        raise StorageIntegrityError("snapshot source coverage cannot contain triggers")


def _check_shapes(output):
    # octet_length, never length(TEXT): embedded NUL must not hide a huge suffix.
    # All output metadata is ASCII; UTF-8 is required for this own new ledger.
    if refs._query(output, "PRAGMA main.encoding").fetchone() != ("UTF-8",):
        raise StorageIntegrityError("snapshot source output requires UTF-8 metadata")
    for table, columns in _TABLES.items():
        checks = []
        for name, kind, _pk in columns:
            checks.append(f"typeof({name})!='{kind.lower()}'")
            if kind == "TEXT":
                size = "<=24" if name in {"status", "reason"} else "<=64" if name == "parts_key" else "=64"
                checks.append(f"NOT(octet_length({name}){size})")
        if refs._query(output, f"SELECT 1 FROM {table} WHERE " + " OR ".join(checks) + " LIMIT 1").fetchone():
            raise StorageIntegrityError("snapshot source coverage has unbounded or mistyped metadata")


def _create_schema(output):
    for table, columns in _TABLES.items():
        declaration = ",".join(name + " " + kind + " NOT NULL" + (" PRIMARY KEY" if pk else "")
                               for name, kind, pk in columns)
        output.execute(f"CREATE TABLE {table} ({declaration}) WITHOUT ROWID")
    output.execute("CREATE INDEX v2_snap_source_rows_by_parts ON v2_snap_source_rows(parts_key)")
    _check_schema(output)
    _check_shapes(output)


def _admit_pair(source, output, limits):
    guard = inventory._HeldRead(source)
    output_path = refs._require_connection(output, limits)
    source_path = source.execute("PRAGMA database_list").fetchone()[2]
    if source is output or (source_path and Path(source_path).samefile(output_path)):
        raise StorageIntegrityError("snapshot source and private output must be different databases")
    functions = refs._query(output, "PRAGMA function_list").fetchmany(1025)
    if len(functions) > 1024 or any(row[1] != 1 and row[0].casefold() in
            {"typeof", "octet_length", "count"} for row in functions):
        raise StorageIntegrityError("snapshot source output requires unchanged core SQL functions")
    snapshots._admit(output, limits)
    guard.check()
    return guard


@contextmanager
def _atomic(output, limits):
    """Own savepoint, with no attempt to revive a caller-ended transaction."""
    refs._check_footprint(output, limits)
    name = "v2_snap_source_" + uuid4().hex
    output.execute(f"SAVEPOINT {name}")
    epoch = output.transaction_generation
    try:
        yield
        if not output.in_transaction or output.transaction_generation != epoch:
            raise StorageIntegrityError("snapshot source output transaction ended during build")
        refs._check_footprint(output, limits)
    except BaseException as exc:
        if output.in_transaction and output.transaction_generation == epoch:
            output.execute(f"ROLLBACK TO {name}")
            output.execute(f"RELEASE {name}")
        if isinstance(exc, sqlite3.DatabaseError):
            if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_FULL, sqlite3.SQLITE_TOOBIG):
                raise StorageLimitError("snapshot source output hit its hard allocation limit") from exc
            raise StorageIntegrityError("snapshot source build transaction failed") from exc
        raise
    else:
        output.execute(f"RELEASE {name}")


class _OutputEpoch:
    def __init__(self, output, limits):
        self.output, self.limits = output, limits
        self.stamp = self._current()

    def _current(self):
        current = refs._generation(self.output, self.limits)
        # Own normal writes are permitted, never transaction/DDL/settings changes.
        return current[:1] + current[2:]

    def check(self):
        if not self.output.in_transaction or self._current() != self.stamp:
            raise StorageIntegrityError("snapshot source output generation changed")


class _TextHash:
    """Tee the exact inventory field framing; retain at most one tiny identity."""
    def __init__(self, row_hash, size):
        self.row_hash, self.hasher = row_hash, hashlib.sha256()
        self.small = bytearray() if size <= 128 else None
        self.first = True

    def update(self, value):
        self.row_hash.update(value)
        self.hasher.update(value)
        if self.first:
            self.first = False  # The existing inventory's T + uint64 size frame.
        elif self.small is not None:
            self.small.extend(value)


def _text_field(source, guard, rowid, name, size, row_hash, limits, encoding):
    hasher = _TextHash(row_hash, size)
    inventory._field_hash(source, guard, _TABLE, rowid, name, "text", size, None, hasher, limits)
    value = None
    if hasher.small is not None:
        try:
            candidate = bytes(hasher.small).decode(encoding)
        except UnicodeError:
            pass
        else:
            if len(candidate) == 64 and all(char in "0123456789abcdef" for char in candidate):
                value = candidate
    return hasher.hasher.hexdigest(), value


class _Payload:
    def __init__(self, blob, guard, row_hash, size, limits, key):
        self.blob, self.guard, self.row_hash = blob, guard, row_hash
        self.size, self.chunk = size, min(_CHUNK_BYTES, limits.block_bytes)
        self.buffer, self.position, self.read_bytes = b"", 0, 0
        self.hasher = hashlib.sha256()
        self.legacy = None if key is None else hashlib.sha256(b'{"key":' + canonical_bytes(key) + b',"payload":')
        if len(blob) != size:
            raise StorageIntegrityError("source snapshot payload length changed")
        row_hash.update(b"B" + struct.pack(">Q", size))

    def _fill(self):
        if self.position < len(self.buffer):
            return True
        self.guard.check()
        self.buffer = self.blob.read(min(self.chunk, self.size - self.read_bytes))
        self.position = 0
        if not self.buffer:
            if self.read_bytes != self.size or self.blob.read(1):
                raise StorageIntegrityError("source snapshot payload changed during streaming")
            return False
        self.read_bytes += len(self.buffer)
        self.hasher.update(self.buffer)
        self.row_hash.update(self.buffer)
        if self.legacy is not None:
            self.legacy.update(self.buffer)
        return True

    def peek(self):
        return self.buffer[self.position] if self._fill() else None

    def take(self, size):
        result = bytearray()
        while len(result) < size:
            if not self._fill():
                raise StorageIntegrityError("truncated source snapshot envelope")
            length = min(size - len(result), len(self.buffer) - self.position)
            result.extend(self.buffer[self.position:self.position + length])
            self.position += length
        return bytes(result)

    def expect(self, value):
        if self.take(len(value)) != value:
            raise StorageIntegrityError("source snapshot envelope is not canonical")

    def drain(self):
        while self._fill():
            self.position = len(self.buffer)
        self.guard.check()


class _Scanner:
    def __init__(self, payload, limits):
        self.payload, self.limits = payload, limits
        self.maximum = min(snapshots.MAX_HEADER_BYTES, limits.block_bytes)
        self.header = bytearray()
        self.header_bytes = None
        self.count = 0

    def _append(self, value):
        if len(self.header) + len(value) > self.maximum:
            raise _Unadapted("header-limit")
        self.header.extend(value)

    def _key(self):
        self.payload.expect(b'"')
        value, escaped = bytearray(b'"'), False
        while True:
            char = self.payload.take(1)
            value.extend(char)
            if len(self.header) + len(value) > self.maximum:
                raise _Unadapted("header-limit")
            if escaped:
                escaped = False
            elif char == b"\\":
                escaped = True
            elif char == b'"':
                return bytes(value)

    def _value(self):
        # Copy bounded non-ref bytes only. JSON semantics/canonical form belong
        # to snapshots._decode_header, not this lexical nesting/string locator.
        nesting, quoted, escaped, any_bytes = bytearray(), False, False, False
        while True:
            current = self.payload.peek()
            if current is None:
                raise StorageIntegrityError("truncated source snapshot header")
            if not quoted and not nesting and current in (ord(","), ord("}")):
                if not any_bytes:
                    raise StorageIntegrityError("empty source snapshot header value")
                return
            char = self.payload.take(1)
            self._append(char)
            any_bytes = True
            if quoted:
                if escaped:
                    escaped = False
                elif char == b"\\":
                    escaped = True
                elif char == b'"':
                    quoted = False
            elif char == b'"':
                quoted = True
            elif char in (b"{", b"["):
                nesting.extend(char)
            elif char in (b"}", b"]"):
                if not nesting or (nesting.pop(), char) not in ((ord("{"), b"}"), (ord("["), b"]")):
                    raise StorageIntegrityError("unbalanced source snapshot header")

    def __iter__(self):
        payload = self.payload
        payload.expect(b"{")
        self._append(b"{")
        previous_key, fields, found_refs = None, 0, False
        if payload.peek() != ord("}"):
            while True:
                key = self._key()
                if previous_key is not None and key <= previous_key:
                    raise StorageIntegrityError("source snapshot top-level keys are not canonical and unique")
                previous_key = key
                payload.expect(b":")
                if key == b'"observation_refs"':
                    if found_refs:
                        raise StorageIntegrityError("duplicate source snapshot reference array")
                    found_refs = True
                    payload.expect(b"[")
                    previous_ref = None
                    if payload.peek() != ord("]"):
                        while True:
                            payload.expect(b'"')
                            reference = payload.take(64)
                            payload.expect(b'"')
                            if any(char not in b"0123456789abcdef" for char in reference):
                                raise StorageIntegrityError("source snapshot reference is not a lowercase SHA-256")
                            if previous_ref is not None and reference <= previous_ref:
                                raise StorageIntegrityError("source snapshot references are not strictly increasing")
                            previous_ref = reference
                            self.count += 1
                            yield reference.decode("ascii")
                            if payload.peek() == ord("]"):
                                break
                            payload.expect(b",")
                    payload.expect(b"]")
                else:
                    self._append((b"," if fields else b"") + key + b":")
                    start = len(self.header)
                    self._value()
                    fields += 1
                    if key == b'"kind"':
                        try:
                            kind = snapshots._decode_object(b'{"kind":' + bytes(self.header[start:]) + b"}", label="source snapshot kind")
                            snapshots._finite_json(kind)
                        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
                            raise StorageIntegrityError("source snapshot kind is not canonical finite JSON") from exc
                        if kind["kind"] != snapshots.KIND:
                            raise _Unadapted("unknown-header")
                if payload.peek() == ord("}"):
                    break
                payload.expect(b",")
        payload.expect(b"}")
        self._append(b"}")
        if payload.peek() is not None:
            raise StorageIntegrityError("source snapshot contains noncanonical trailing bytes")
        self.header_bytes = bytes(self.header)
        try:
            snapshots._decode_header(self.header_bytes, self.limits)
        except snapshots.SnapshotAdapterUnavailable as exc:
            raise _Unadapted("unknown-header") from exc
        if not found_refs:
            raise StorageIntegrityError("known source snapshot lacks its complete reference array")


def _read_row(source, guard, raw, limits, encoding, *, output=None):
    rowid = raw[0]
    refs._integer(rowid, "source snapshot rowid", minimum=-(2**63))
    sizes = []
    for index, (_name, expected, _nullable) in enumerate(inventory._TABLES[_TABLE]):
        kind, size, _value = raw[1 + 3 * index:4 + 3 * index]
        if kind != expected:
            raise StorageIntegrityError("source snapshot changed physical storage type")
        refs._integer(size, "source snapshot field size")
        if size > limits.input_bytes:
            raise StorageLimitError("source snapshot field exceeds C input admission")
        sizes.append(size)
    row_hash = hashlib.sha256(b"betboy-context-v2-row\0")
    key_digest, key = _text_field(source, guard, rowid, "key", sizes[0], row_hash, limits, encoding)
    digest_info, part, reason = None, None, ""
    guard.check()
    # Even tiny and zero-length real payloads use the physical readonly BLOB API.
    with source.blobopen(_TABLE, "payload", rowid, readonly=True) as blob:
        payload = _Payload(blob, guard, row_hash, sizes[1], limits, key)
        try:
            with nullcontext() if output is None else _atomic(output, limits):
                if key is None:
                    raise _Unadapted("invalid-key")
                scanner = _Scanner(payload, limits)
                if output is None:
                    for _reference in scanner:
                        pass
                    reference_set = None
                else:
                    reference_set = refs.put_refset(output, scanner, limits=limits)
                payload.drain()
                digest_info = _text_field(source, guard, rowid, "payload_digest", sizes[2], row_hash, limits, encoding)
                if digest_info[1] is None:
                    raise _Unadapted("invalid-payload-digest")
                payload.legacy.update(b"}")
                if payload.legacy.hexdigest() != digest_info[1]:
                    raise StorageIntegrityError("source snapshot legacy payload digest mismatch")
                if output is not None:
                    part = snapshots.put_snapshot_parts(
                        output, key=key, header_bytes=scanner.header_bytes,
                        observation_refs=reference_set,
                        expected_raw_payload_sha256=payload.hasher.hexdigest(),
                        expected_payload_bytes=sizes[1], expected_payload_digest=digest_info[1],
                        expected_observation_count=scanner.count, limits=limits,
                    )
        except _Unadapted as exc:
            reason = exc.reason
            payload.drain()
            if digest_info is None:
                digest_info = _text_field(source, guard, rowid, "payload_digest", sizes[2], row_hash, limits, encoding)
    guard.check()
    row = (key_digest, sizes[0], digest_info[0], sizes[2], row_hash.hexdigest(),
           payload.hasher.hexdigest(), sizes[1], "unadapted" if reason else "adapted", reason,
           "" if reason else key, _ZERO if part is None else part.descriptor_digest)
    return row, sum(sizes), digest_info[1]


def _source_rows(source):
    # Zero inline budget: never SELECT the payload, including on the small path.
    return inventory._raw_rows(source, _TABLE, inventory._TABLES[_TABLE], 0)


def _coverage_hash():
    return hashlib.sha256(b"betboy-snapshot-source-coverage-v2\0")


def _check_table(table, row_hash, count, size):
    row_hash.update(struct.pack(">Q", count))
    if table is not None and (table.row_count != count or table.value_bytes != size or table.row_digest != row_hash.hexdigest()):
        raise StorageIntegrityError("complete source snapshot table differs from its raw inventory")


def _translate_sql_errors(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except sqlite3.Error as exc:
            raise StorageIntegrityError("snapshot source SQL identity or reader could not be established") from exc
    return checked


@_translate_sql_errors
def adapt_source_snapshots(source, output, expected_inventory: RawInventory, *, limits=DEFAULT_LIMITS) -> CoverageDescriptor:
    """Build complete source coverage in a fresh C2 target, without committing.

Caller creates refs/snapshot schemas first and retains both connections. This
function deliberately does not guess ownership of pre-existing snapshot parts
or resume a partially authored coverage ledger. On failure, all its changes are
rolled back; pre-existing caller data remains. Raw-only rows are not validated
snapshots and the exact original raw source must remain available.
"""
    _validate_inventory(expected_inventory)
    guard = _admit_pair(source, output, limits)
    fresh = inventory.inventory_raw(source, limits=limits)
    guard.check()
    if fresh != expected_inventory:
        raise StorageIntegrityError("snapshot source differs from the expected complete raw inventory")
    if refs._query(output, "SELECT 1 FROM v2_snapshot_parts LIMIT 1").fetchone() or refs._query(
            output, "SELECT 1 FROM v2_snapshot_headers LIMIT 1").fetchone() or refs._query(
            output, "SELECT 1 FROM main.sqlite_schema WHERE name GLOB 'v2_snap_source_*' LIMIT 1").fetchone():
        raise StorageIntegrityError("snapshot source adapter requires a fresh unowned snapshot target")
    table = _table_inventory(fresh)
    encoding = {"UTF-8": "utf-8", "UTF-16le": "utf-16-le", "UTF-16be": "utf-16-be"}[source.execute("PRAGMA encoding").fetchone()[0]]
    count = size = adapted = unadapted = 0
    table_hash = hashlib.sha256(b"betboy-context-v2-table\0" + _TABLE.encode("ascii"))
    coverage_hash = _coverage_hash()
    with _atomic(output, limits):
        _create_schema(output)
        epoch = _OutputEpoch(output, limits)
        if table is not None:
            cursor = _source_rows(source)
            try:
                for raw in cursor:
                    epoch.check()
                    row, value_bytes, _digest = _read_row(source, guard, raw, limits, encoding, output=output)
                    epoch.check()
                    output.execute("INSERT INTO v2_snap_source_rows VALUES (" + ",".join("?" for _ in row) + ")", row)
                    table_hash.update(bytes.fromhex(row[4]))
                    coverage_hash.update(canonical_bytes(row))
                    count, size = count + 1, size + value_bytes
                    adapted += row[7] == "adapted"
                    unadapted += row[7] == "unadapted"
            finally:
                cursor.close()
        _check_table(table, table_hash, count, size)
        coverage_hash.update(struct.pack(">Q", count))
        provisional = CoverageDescriptor(FORMAT_VERSION, fresh, table is not None, count, size,
            _ZERO if table is None else table.row_digest, adapted, unadapted, coverage_hash.hexdigest(), _ZERO)
        descriptor = CoverageDescriptor(**{**vars(provisional), "descriptor_digest": _descriptor_digest(provisional)})
        _validate_descriptor(descriptor)
        output.execute("INSERT INTO v2_snap_source_manifest VALUES (" + ",".join("?" for _ in _MANIFEST_COLUMNS) + ")", _manifest_row(descriptor))
        epoch.check()
        # This re-reads the entire source and every output key before success.
        validate_source_coverage(source, output, descriptor, limits=limits)
        guard.check()
        epoch.check()
        return descriptor


@_translate_sql_errors
def validate_source_coverage(source, output, descriptor: CoverageDescriptor, *, limits=DEFAULT_LIMITS) -> None:
    """Fresh full-source and exact-output validation, never standalone approval."""
    _validate_descriptor(descriptor)
    guard = _admit_pair(source, output, limits)
    generation = refs._generation(output, limits)
    _check_schema(output)
    _check_shapes(output)
    stored = refs._query(output, "SELECT " + ",".join(_MANIFEST_COLUMNS) + " FROM v2_snap_source_manifest LIMIT 2").fetchall()
    if stored != [_manifest_row(descriptor)]:
        raise StorageIntegrityError("snapshot source coverage belongs to a different complete generation")
    fresh = inventory.inventory_raw(source, limits=limits)
    guard.check()
    refs._assert_reader(output, generation)
    if fresh != descriptor.source_inventory:
        raise StorageIntegrityError("snapshot source differs from its complete coverage inventory")
    snapshots.validate_all(output, limits=limits)
    table, count, size, adapted, unadapted = _table_inventory(fresh), 0, 0, 0, 0
    table_hash = hashlib.sha256(b"betboy-context-v2-table\0" + _TABLE.encode("ascii"))
    coverage_hash = _coverage_hash()
    encoding = {"UTF-8": "utf-8", "UTF-16le": "utf-16-le", "UTF-16be": "utf-16-be"}[source.execute("PRAGMA encoding").fetchone()[0]]
    if table is not None:
        cursor = _source_rows(source)
        try:
            for raw in cursor:
                row, value_bytes, payload_digest = _read_row(source, guard, raw, limits, encoding)
                stored = refs._query(output, "SELECT " + ",".join(_ROW_COLUMNS) +
                    " FROM v2_snap_source_rows WHERE key_field_digest=?", (row[0],)).fetchone()
                if stored is None or stored[:-1] != row[:-1]:
                    raise StorageIntegrityError("snapshot source row coverage is missing, foreign, or changed")
                refs._digest(stored[-1], "source coverage parts")
                if row[7] == "adapted":
                    part = snapshots._read_descriptor(output, row[9])
                    if (part.descriptor_digest != stored[-1] or part.raw_payload_sha256 != row[5]
                            or part.payload_bytes != row[6] or part.payload_digest != payload_digest):
                        raise StorageIntegrityError("snapshot source coverage differs from its actual parts")
                    adapted += 1
                else:
                    if row[8] not in _REASONS or stored[-1] != _ZERO:
                        raise StorageIntegrityError("raw-only snapshot source has a false adapter claim")
                    unadapted += 1
                count, size = count + 1, size + value_bytes
                table_hash.update(bytes.fromhex(row[4]))
                coverage_hash.update(canonical_bytes(stored))
                refs._assert_reader(output, generation)
        finally:
            cursor.close()
    _check_table(table, table_hash, count, size)
    coverage_hash.update(struct.pack(">Q", count))
    if (count != descriptor.snapshot_count or size != descriptor.snapshot_value_bytes
            or adapted != descriptor.adapted_count or unadapted != descriptor.unadapted_count
            or coverage_hash.hexdigest() != descriptor.coverage_digest
            or refs._query(output, "SELECT count(*) FROM v2_snap_source_rows").fetchone() != (count,)
            or refs._query(output, "SELECT count(*) FROM v2_snapshot_parts").fetchone() != (adapted,)
            or refs._query(output, "SELECT 1 FROM v2_snapshot_parts p WHERE NOT EXISTS "
                "(SELECT 1 FROM v2_snap_source_rows r WHERE r.status='adapted' AND r.parts_key=p.key) LIMIT 1").fetchone()):
        raise StorageIntegrityError("snapshot source complete output keyset coverage differs")
    guard.check()
    refs._assert_reader(output, generation)
    refs._check_footprint(output, limits)
