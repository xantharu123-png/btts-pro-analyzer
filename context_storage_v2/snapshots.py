"""Known snapshot byte transport using C2 reference sets, never model approval.

The original source remains elsewhere, unchanged.  This *new*, narrow adapter
stores only a bounded canonical header without its top-level observation_refs
and a complete RefSetDescriptor.  Every reconstruction must match both the
source's entire raw-payload digest and its existing {key,payload} digest.

Unknown or oversized non-reference structures are not adapted by this module;
the caller retains them in its lossless transport-only inventory.  The 1-MiB
header and explicit 64-MiB materialization helper bounds are new adapter bounds,
not claims that legacy snapshots had these per-value limits.  Legacy's separate
64-MiB total in-memory input/history-cache contracts are unchanged.

Only the caller's exact private TrackedConnection is used.  No source opening,
commits, publication, HMAC creation, D2 resolution or model replay occurs here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib

from context_snapshots import _decode_snapshot, _finite_json
from context_transport import KIND, _INPUTS
from model_artifacts import _decode_object, canonical_bytes

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from . import refs
from .ref_chunks import iter_canonical_ref_chunks


FORMAT_VERSION = 2
MAX_HEADER_BYTES = 1024**2
MAX_MATERIALIZE_BYTES = 64 * 1024**2
_FORMAT = "betboy-context-snapshot-parts-v2"
_HEADER_KEYS = (_INPUTS | {"result"}) - {"observation_refs"}
_PART_COLUMNS = (
    "key", "format_version", "header_digest", "header_bytes", "refs_set_digest",
    "refs_format_version", "refs_canonical_digest", "observation_count",
    "refs_canonical_bytes", "refs_binary_bytes", "refs_block_count",
    "raw_payload_sha256", "payload_bytes", "payload_digest", "descriptor_digest",
)
_INTEGER_COLUMNS = {
    "format_version", "header_bytes", "refs_format_version", "observation_count",
    "refs_canonical_bytes", "refs_binary_bytes", "refs_block_count", "payload_bytes",
}
_TABLES = {
    "v2_snapshot_headers": (
        ("header_digest", "TEXT", 1), ("format_version", "INTEGER", 0),
        ("header_bytes", "INTEGER", 0), ("content", "BLOB", 0),
    ),
    "v2_snapshot_parts": tuple(
        (name, "INTEGER" if name in _INTEGER_COLUMNS else "TEXT", int(name == "key"))
        for name in _PART_COLUMNS
    ),
}


class SnapshotAdapterUnavailable(StorageIntegrityError):
    """No known-header adapter: retain the source, without a semantic claim."""


@dataclass(frozen=True)
class SnapshotPartsDescriptor:
    format_version: int
    key: str
    header_digest: str
    header_bytes: int
    observation_refs: refs.RefSetDescriptor
    raw_payload_sha256: str
    payload_bytes: int
    payload_digest: str
    descriptor_digest: str


def _check_schema(connection):
    names = {
        row[0] for row in refs._query(
            connection,
            "SELECT name FROM sqlite_schema WHERE type='table' AND name GLOB 'v2_snapshot_*' LIMIT 3",
        )
    }
    if names != set(_TABLES):
        raise StorageIntegrityError("incomplete or foreign snapshot-parts schema")
    for table, expected in _TABLES.items():
        actual = tuple(refs._query(connection, f"PRAGMA main.table_xinfo({table})"))
        if len(actual) != len(expected):
            raise StorageIntegrityError("snapshot-parts table has unexpected columns")
        for index, (row, column) in enumerate(zip(actual, expected)):
            name, declared_type, primary_key = column
            if row != (index, name, declared_type, 1, None, primary_key, 0):
                raise StorageIntegrityError("snapshot-parts column identity changed")
    if refs._query(
        connection,
        "SELECT 1 FROM sqlite_schema WHERE type='trigger' AND tbl_name GLOB 'v2_snapshot_*' LIMIT 1",
    ).fetchone():
        raise StorageIntegrityError("snapshot-parts storage cannot contain triggers")


def _check_shapes(connection):
    width = refs._text_width(connection)
    for table, columns in _TABLES.items():
        predicates = []
        for name, declared_type, _pk in columns:
            kind = {"TEXT": "text", "INTEGER": "integer", "BLOB": "blob"}[declared_type]
            predicates.append(f"typeof({name})!='{kind}'")
            if kind == "text":
                # length(TEXT) stops at NUL; octet_length bounds the complete
                # stored bytes before any Python TEXT fetch, including UTF-16.
                predicates.append(f"length({name})!=64 OR octet_length({name})!={64 * width}")
        if refs._query(connection, f"SELECT 1 FROM {table} WHERE " + " OR ".join(predicates) + " LIMIT 1").fetchone():
            raise StorageIntegrityError("invalid snapshot-parts SQL storage type or bounded key length")


def _admit(connection, limits):
    refs._require_connection(connection, limits)
    refs._check_footprint(connection, limits)
    refs._check_schema(connection)
    refs._check_shapes(connection)
    _check_schema(connection)
    _check_shapes(connection)


def create_schema(connection) -> None:
    """Create only new snapshot tables; the caller has already created C2 refs."""
    refs._require_connection(connection, DEFAULT_LIMITS)
    refs._check_schema(connection)
    with refs._atomic(connection, DEFAULT_LIMITS):
        connection.execute(
            "CREATE TABLE IF NOT EXISTS v2_snapshot_headers ("
            "header_digest TEXT NOT NULL PRIMARY KEY, format_version INTEGER NOT NULL, "
            "header_bytes INTEGER NOT NULL, content BLOB NOT NULL) WITHOUT ROWID"
        )
        columns = ",".join(
            name + (" INTEGER" if name in _INTEGER_COLUMNS else " TEXT")
            + " NOT NULL" + (" PRIMARY KEY" if name == "key" else "")
            for name in _PART_COLUMNS
        )
        connection.execute(f"CREATE TABLE IF NOT EXISTS v2_snapshot_parts ({columns}) WITHOUT ROWID")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS v2_snapshot_parts_by_header ON v2_snapshot_parts(header_digest,key)"
        )
        _check_schema(connection)


def _decode_header(header_bytes, limits):
    if type(header_bytes) is not bytes:
        raise StorageIntegrityError("snapshot header must be canonical SQLite BLOB bytes")
    if not 0 < len(header_bytes) <= min(MAX_HEADER_BYTES, limits.block_bytes):
        raise StorageLimitError("snapshot header needs a separately reviewed large-header adapter")
    try:
        header = _decode_object(header_bytes, label="snapshot-parts header")
        _finite_json(header)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise StorageIntegrityError("snapshot header is not canonical finite JSON") from exc
    if header.get("kind") != KIND:
        raise SnapshotAdapterUnavailable("unknown snapshot header remains outside this transport-only adapter")
    if type(header.get("schema")) is not int or header["schema"] != 1 or set(header) != _HEADER_KEYS:
        raise StorageIntegrityError("known snapshot header has missing or additional top-level fields")
    return header


def _descriptor_digest(descriptor):
    manifest = asdict(descriptor)
    del manifest["descriptor_digest"]
    manifest["format"] = _FORMAT
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def _validate_descriptor(descriptor, limits):
    if type(descriptor) is not SnapshotPartsDescriptor:
        raise StorageIntegrityError("invalid snapshot-parts descriptor type")
    refs._integer(descriptor.format_version, "snapshot-parts format", minimum=FORMAT_VERSION, maximum=FORMAT_VERSION)
    for label in ("key", "header_digest", "raw_payload_sha256", "payload_digest", "descriptor_digest"):
        refs._digest(getattr(descriptor, label), "snapshot " + label)
    refs._integer(descriptor.header_bytes, "snapshot header bytes", minimum=1)
    refs._integer(descriptor.payload_bytes, "snapshot payload bytes", minimum=1)
    refs._validate_descriptor(descriptor.observation_refs, limits)
    if descriptor.header_bytes > min(MAX_HEADER_BYTES, limits.block_bytes):
        raise StorageLimitError("snapshot header exceeds the narrow adapter envelope")
    if descriptor.payload_bytes > limits.input_bytes:
        raise StorageLimitError("complete snapshot payload exceeds the C input envelope")
    expected_size = descriptor.header_bytes + len(b',"observation_refs":') + descriptor.observation_refs.canonical_bytes
    if descriptor.payload_bytes != expected_size:
        raise StorageIntegrityError("snapshot complete byte count disagrees with header and references")
    if _descriptor_digest(descriptor) != descriptor.descriptor_digest:
        raise StorageIntegrityError("snapshot-parts complete descriptor digest mismatch")


def _to_row(descriptor):
    reference = descriptor.observation_refs
    return (
        descriptor.key, descriptor.format_version, descriptor.header_digest, descriptor.header_bytes,
        reference.set_digest, reference.format_version, reference.canonical_digest,
        reference.reference_count, reference.canonical_bytes, reference.binary_bytes, reference.block_count,
        descriptor.raw_payload_sha256, descriptor.payload_bytes, descriptor.payload_digest,
        descriptor.descriptor_digest,
    )


def _from_row(row):
    if row is None or len(row) != len(_PART_COLUMNS):
        raise StorageIntegrityError("missing complete snapshot-parts descriptor")
    reference = refs.RefSetDescriptor(row[5], row[4], row[6], row[7], row[8], row[9], row[10])
    return SnapshotPartsDescriptor(row[1], row[0], row[2], row[3], reference, row[11], row[12], row[13], row[14])


def _read_descriptor(connection, key):
    return _from_row(refs._query(
        connection, "SELECT " + ",".join(_PART_COLUMNS) + " FROM v2_snapshot_parts WHERE key=?", (key,),
    ).fetchone())


def _read_header(connection, descriptor, limits):
    row = refs._query(
        connection,
        "SELECT format_version,header_bytes,typeof(content),length(content) FROM v2_snapshot_headers WHERE header_digest=?",
        (descriptor.header_digest,),
    ).fetchone()
    if row is None:
        raise StorageIntegrityError("missing snapshot header")
    version, size, storage_type, physical_size = row
    refs._integer(version, "stored snapshot header version", minimum=FORMAT_VERSION, maximum=FORMAT_VERSION)
    refs._integer(size, "stored snapshot header bytes", minimum=1)
    refs._integer(physical_size, "physical snapshot header bytes", minimum=1)
    if storage_type != "blob" or size != physical_size or size != descriptor.header_bytes:
        raise StorageIntegrityError("snapshot header storage differs from complete descriptor")
    if size > min(MAX_HEADER_BYTES, limits.block_bytes):
        raise StorageLimitError("stored snapshot header exceeds the narrow adapter envelope")
    raw_row = refs._query(connection, "SELECT content FROM v2_snapshot_headers WHERE header_digest=?", (descriptor.header_digest,)).fetchone()
    if raw_row is None or type(raw_row[0]) is not bytes or len(raw_row[0]) != size:
        raise StorageIntegrityError("snapshot header changed during bounded read")
    header_bytes = raw_row[0]
    if hashlib.sha256(header_bytes).hexdigest() != descriptor.header_digest:
        raise StorageIntegrityError("snapshot header digest mismatch")
    return _decode_header(header_bytes, limits)


def _payload_pieces(connection, descriptor, header, limits):
    """The same canonical JSON order as the unchanged canonical_bytes owner."""
    yield b"{"
    for index, key in enumerate(sorted((*header, "observation_refs"))):
        if index:
            yield b","
        yield canonical_bytes(key)
        yield b":"
        if key != "observation_refs":
            yield canonical_bytes(header[key])
            continue
        # This byte-oriented adapter now uses the separately reviewed byte
        # reader. The public scalar reference API retains its per-value checks;
        # no check or reference is silently removed from that old interface.
        yield from iter_canonical_ref_chunks(connection, descriptor.observation_refs,
            limits=limits, chunk_bytes=min(65536, limits.block_bytes))
    yield b"}"


def _check_reconstruction(connection, descriptor, header, limits):
    raw_hash = hashlib.sha256()
    old_hash = hashlib.sha256(b'{"key":' + canonical_bytes(descriptor.key) + b',"payload":')
    size = 0
    for piece in _payload_pieces(connection, descriptor, header, limits):
        size += len(piece)
        if size > descriptor.payload_bytes or size > limits.input_bytes:
            raise StorageIntegrityError("snapshot reconstruction contains additional bytes")
        raw_hash.update(piece)
        old_hash.update(piece)
    old_hash.update(b"}")
    if size != descriptor.payload_bytes or raw_hash.hexdigest() != descriptor.raw_payload_sha256:
        raise StorageIntegrityError("complete snapshot raw payload identity mismatch")
    if old_hash.hexdigest() != descriptor.payload_digest:
        raise StorageIntegrityError("snapshot legacy key/payload identity mismatch")


def _verify_snapshot(connection, descriptor, limits):
    _validate_descriptor(descriptor, limits)
    stored = _read_descriptor(connection, descriptor.key)
    _validate_descriptor(stored, limits)
    if stored != descriptor:
        raise StorageIntegrityError("snapshot descriptor belongs to a different immutable generation")
    header = _read_header(connection, descriptor, limits)
    _check_reconstruction(connection, descriptor, header, limits)
    return header


def put_snapshot_parts(
    connection, *, key, header_bytes, observation_refs,
    expected_raw_payload_sha256, expected_payload_bytes, expected_payload_digest,
    expected_observation_count, limits=DEFAULT_LIMITS,
) -> SnapshotPartsDescriptor:
    """Store one byte-identical known transport, without committing or approval.

    Expected identities/counts come from the separately bound complete source
    inventory.  Passing public hashes alone is not proof of source authority.
    """
    _admit(connection, limits)
    refs._digest(key, "snapshot key")
    refs._digest(expected_raw_payload_sha256, "snapshot raw payload")
    refs._digest(expected_payload_digest, "snapshot legacy payload")
    refs._integer(expected_payload_bytes, "expected snapshot bytes", minimum=1)
    refs._integer(expected_observation_count, "expected snapshot reference count")
    refs._validate_descriptor(observation_refs, limits)
    if expected_observation_count != observation_refs.reference_count:
        raise StorageIntegrityError("snapshot expected complete reference count differs")
    header = _decode_header(header_bytes, limits)
    provisional = SnapshotPartsDescriptor(
        FORMAT_VERSION, key, hashlib.sha256(header_bytes).hexdigest(), len(header_bytes),
        observation_refs, expected_raw_payload_sha256, expected_payload_bytes, expected_payload_digest, "0" * 64,
    )
    descriptor = SnapshotPartsDescriptor(
        provisional.format_version, provisional.key, provisional.header_digest, provisional.header_bytes,
        provisional.observation_refs, provisional.raw_payload_sha256, provisional.payload_bytes,
        provisional.payload_digest, _descriptor_digest(provisional),
    )
    _validate_descriptor(descriptor, limits)
    with refs._atomic(connection, limits):
        generation = refs._generation(connection, limits)
        _check_reconstruction(connection, descriptor, header, limits)
        refs._assert_reader(connection, generation)
        old = refs._query(connection, "SELECT 1 FROM v2_snapshot_parts WHERE key=?", (key,)).fetchone()
        if old:
            if _read_descriptor(connection, key) != descriptor:
                raise StorageIntegrityError("immutable snapshot key cannot be overwritten")
            _verify_snapshot(connection, descriptor, limits)
            return descriptor
        old_header = refs._query(connection, "SELECT 1 FROM v2_snapshot_headers WHERE header_digest=?", (descriptor.header_digest,)).fetchone()
        if old_header:
            _read_header(connection, descriptor, limits)
        else:
            connection.execute("INSERT INTO v2_snapshot_headers VALUES (?,?,?,?)", (
                descriptor.header_digest, FORMAT_VERSION, len(header_bytes), header_bytes,
            ))
        placeholders = ",".join("?" for _column in _PART_COLUMNS)
        connection.execute("INSERT INTO v2_snapshot_parts VALUES (" + placeholders + ")", _to_row(descriptor))
        _verify_snapshot(connection, descriptor, limits)
        return descriptor


def _rechunk(pieces, maximum):
    buffer = bytearray()
    for piece in pieces:
        offset = 0
        while offset < len(piece):
            length = min(maximum - len(buffer), len(piece) - offset)
            buffer.extend(piece[offset:offset + length])
            offset += length
            if len(buffer) == maximum:
                yield bytes(buffer)
                buffer.clear()
    if buffer:
        yield bytes(buffer)


def iter_snapshot_bytes(connection, descriptor, *, limits=DEFAULT_LIMITS, chunk_bytes=None):
    """Fresh bounded stream after complete byte/hash validation, never a dict."""
    _admit(connection, limits)
    if chunk_bytes is None:
        chunk_bytes = min(64 * 1024, limits.block_bytes)
    if type(chunk_bytes) is not int or not 0 < chunk_bytes <= limits.block_bytes:
        raise StorageLimitError("snapshot stream chunk must fit the C block budget")
    generation = refs._generation(connection, limits)
    header = _verify_snapshot(connection, descriptor, limits)
    refs._assert_reader(connection, generation)
    chunks = iter(_rechunk(_payload_pieces(connection, descriptor, header, limits), chunk_bytes))
    while True:
        # Check before resuming the inner iterator as well as before exposing its
        # output; close/commit may otherwise raise from a resumed SQLite cursor.
        refs._assert_reader(connection, generation)
        try:
            chunk = next(chunks)
        except StopIteration:
            break
        refs._assert_reader(connection, generation)
        yield chunk
    refs._assert_reader(connection, generation)


def materialize_snapshot(connection, descriptor, *, max_bytes, limits=DEFAULT_LIMITS):
    """Explicit small-fixture/adapter helper; no default legacy materialization.

    64 MiB is this helper's new byte maximum, not a historical per-snapshot
    contract and not a substitute for separately enforced native memory limits.
    """
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_MATERIALIZE_BYTES:
        raise StorageLimitError("snapshot materialization requires an explicit bounded byte limit")
    refs._require_connection(connection, limits)
    _validate_descriptor(descriptor, limits)
    if descriptor.payload_bytes > max_bytes:
        raise StorageLimitError("snapshot exceeds the explicit materialization byte limit")
    result = bytearray()
    for chunk in iter_snapshot_bytes(connection, descriptor, limits=limits):
        if len(result) + len(chunk) > max_bytes:
            raise StorageLimitError("snapshot reconstruction exceeded materialization byte limit")
        result.extend(chunk)
    return _decode_snapshot(descriptor.key, bytes(result), descriptor.payload_digest)


def validate_all(connection, *, limits=DEFAULT_LIMITS) -> None:
    """Check intrinsic new transport integrity, not source coverage or approval.

    The separate inventory owner must additionally compare the *entire* expected
    snapshot-key set; an intrinsically empty store is not proof of a migration.
    """
    _admit(connection, limits)
    generation = refs._generation(connection, limits)
    refs.validate_all(connection, limits=limits)
    if refs._query(
        connection,
        "SELECT 1 FROM v2_snapshot_headers h WHERE NOT EXISTS "
        "(SELECT 1 FROM v2_snapshot_parts p WHERE p.header_digest=h.header_digest) LIMIT 1",
    ).fetchone():
        raise StorageIntegrityError("snapshot storage contains an unreachable additional header")
    for row in refs._query(connection, "SELECT " + ",".join(_PART_COLUMNS) + " FROM v2_snapshot_parts ORDER BY key"):
        _verify_snapshot(connection, _from_row(row), limits)
    refs._assert_reader(connection, generation)
    refs._check_footprint(connection, limits)
