"""C2b byte-identity differentials, not model/source/approval certification."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import sqlite3
import tracemalloc

import pytest

from context_runtime_transaction import TrackedConnection
from context_snapshots import _decode_snapshot, _payload_digest
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2 import refs, snapshots
from context_transport import calculate_context_payload, context_payload_key
from model_artifacts import canonical_bytes
from test_context_transport import inputs


@pytest.fixture
def connection(tmp_path):
    connection = sqlite3.connect(tmp_path / "snapshot-parts.db", factory=TrackedConnection)
    connection.execute("PRAGMA page_size=4096")
    connection.execute("PRAGMA cache_size=-4096")
    connection.execute("PRAGMA mmap_size=0")
    connection.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096}")
    connection.execute("BEGIN")
    refs.create_schema(connection)
    snapshots.create_schema(connection)
    connection.commit()
    connection.execute("BEGIN")
    try:
        yield connection
    finally:
        connection.close()


def packet(*, family="tennis:winner", with_effect=False):
    payload = calculate_context_payload(**inputs(family=family, with_effect=with_effect))
    key = context_payload_key(payload)
    raw = canonical_bytes(payload)
    return key, payload, raw, _payload_digest(key, payload)


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("with_effect", [False, True])
def test_snapshot_build_and_reconstruction_use_complete_byte_reader_not_scalar(
        connection, monkeypatch, family, with_effect):
    key, payload, raw, original_digest = packet(family=family, with_effect=with_effect)
    expected_arguments = arguments(connection, payload=payload, key=key)
    def no_scalar(*_args, **_kwargs):
        pytest.fail("byte-oriented snapshots must not invoke the unchanged scalar reader")
    monkeypatch.setattr(refs, "iter_refset", no_scalar)
    descriptor = snapshots.put_snapshot_parts(connection, **expected_arguments)
    for chunk_size in (3, 67, 4096):
        assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor,
            chunk_bytes=chunk_size)) == raw
    snapshots.validate_all(connection)
    assert descriptor.payload_digest == original_digest


def test_snapshot_chunk_reconstruction_retains_all_many_reference_bytes(connection):
    key, payload, _raw, _original_digest = packet()
    # Explicit synthetic transport cardinality, never a source/model-valid
    # replacement for an owner-generated large sports profile.
    payload["observation_refs"] = sorted(hashlib.sha256(str(n).encode()).hexdigest()
                                          for n in range(5000))
    raw = canonical_bytes(payload)
    descriptor = snapshots.put_snapshot_parts(connection,
        **arguments(connection, payload=payload, key=key))
    hasher, total = hashlib.sha256(), 0
    for piece in snapshots.iter_snapshot_bytes(connection, descriptor, chunk_bytes=997):
        assert piece == raw[total:total+len(piece)]
        hasher.update(piece)
        total += len(piece)
    assert total == len(raw) == descriptor.payload_bytes
    assert hasher.hexdigest() == hashlib.sha256(raw).hexdigest() == descriptor.raw_payload_sha256
    assert descriptor.payload_digest == _payload_digest(key, payload)


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_full_snapshot_transport_and_nul_admission_respect_sql_text_encoding(tmp_path, encoding):
    connection = sqlite3.connect(tmp_path / "encoding.sqlite", factory=TrackedConnection)
    connection.execute(f"PRAGMA encoding='{encoding}'")
    connection.execute("PRAGMA cache_size=-4096")
    connection.execute("PRAGMA mmap_size=0")
    connection.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096}")
    connection.execute("BEGIN")
    try:
        refs.create_schema(connection)
        snapshots.create_schema(connection)
        key, payload, raw, _digest = packet(family="tennis:serve", with_effect=True)
        descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=key))
        assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor)) == raw
        connection.execute("UPDATE v2_snapshot_parts SET raw_payload_sha256=?", ("a" * 64 + "\0suffix",))
        with pytest.raises(StorageIntegrityError, match="bounded"):
            snapshots._check_shapes(connection)
        connection.execute("UPDATE v2_ref_sets SET canonical_digest=?", ("b" * 64 + "\0suffix",))
        with pytest.raises(StorageIntegrityError, match="bounded"):
            refs._check_shapes(connection)
    finally:
        connection.close()


@pytest.mark.parametrize("column", ["key", "header_digest", "raw_payload_sha256", "payload_digest", "descriptor_digest"])
def test_snapshot_nul_metadata_never_passes_its_complete_byte_bound(connection, column):
    snapshots.put_snapshot_parts(connection, **arguments(connection))
    connection.execute(f"UPDATE v2_snapshot_parts SET {column}=?", ("a" * 64 + "\0suffix",))
    with pytest.raises(StorageIntegrityError, match="bounded"):
        snapshots._check_shapes(connection)


def test_snapshot_large_nul_suffix_is_rejected_before_python_materialization(connection):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    connection.execute("UPDATE v2_snapshot_parts SET raw_payload_sha256=?", ("a" * 64 + "\0" + "x" * (20 * 1024**2),))
    tracemalloc.start()
    try:
        with pytest.raises(StorageIntegrityError):
            next(snapshots.iter_snapshot_bytes(connection, descriptor))
        assert tracemalloc.get_traced_memory()[1] < 1024**2
    finally:
        tracemalloc.stop()


def arguments(connection, *, payload=None, key=None):
    if payload is None:
        key, payload, raw, payload_digest = packet()
    else:
        assert key is not None
        raw, payload_digest = canonical_bytes(payload), _payload_digest(key, payload)
    header = deepcopy(payload)
    observations = header.pop("observation_refs")
    descriptor = refs.put_refset(connection, observations)
    return dict(
        key=key,
        header_bytes=canonical_bytes(header),
        observation_refs=descriptor,
        expected_raw_payload_sha256=hashlib.sha256(raw).hexdigest(),
        expected_payload_bytes=len(raw),
        expected_payload_digest=payload_digest,
        expected_observation_count=len(observations),
    )


def contents(connection):
    return {
        table: tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1"))
        for table in ("v2_snapshot_headers", "v2_snapshot_parts")
    }


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("with_effect", [False, True])
def test_real_old_worker_payload_and_snapshot_decoder_are_byte_exact(connection, family, with_effect):
    key, payload, raw, digest = packet(family=family, with_effect=with_effect)
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=key))
    assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor)) == raw
    assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor)) == raw
    assert descriptor.key == key
    assert descriptor.payload_digest == digest
    assert descriptor.raw_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert descriptor.payload_bytes == len(raw)
    assert snapshots.materialize_snapshot(connection, descriptor, max_bytes=len(raw)) == _decode_snapshot(key, raw, digest)
    assert contents(connection)["v2_snapshot_parts"]
    snapshots.validate_all(connection)


def test_unicode_and_nested_observation_refs_are_preserved_not_accidentally_extracted(connection):
    key, payload, _raw, _digest = packet()
    payload["result"]["limitations"].append('Änderung "observation_refs":[] — Zürich 🟩')
    payload["result"]["nested_for_transport_test"] = {"observation_refs": ["not-the-top-level-set"]}
    # This is a finite legacy snapshot byte-transport fixture, not a model-valid result.
    raw = canonical_bytes(payload)
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=key))
    assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor)) == raw
    assert snapshots.materialize_snapshot(connection, descriptor, max_bytes=len(raw)) == _decode_snapshot(key, raw, _payload_digest(key, payload))


@pytest.mark.parametrize("count", [0, 1, 400])
def test_complete_reference_array_preserves_empty_single_and_many_byte_forms(connection, count):
    key, payload, _raw, _digest = packet()
    payload["observation_refs"] = [f"{number:064x}" for number in range(count)]
    # Again only the unchanged legacy finite-JSON/hash contract is asserted.
    raw = canonical_bytes(payload)
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=key))
    chunks = list(snapshots.iter_snapshot_bytes(connection, descriptor, chunk_bytes=127))
    assert all(0 < len(chunk) <= 127 for chunk in chunks)
    assert b"".join(chunks) == raw
    snapshots.validate_all(connection)


def test_identical_small_headers_are_shared_across_different_complete_refsets(connection):
    key, payload, _raw, _digest = packet()
    one = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=key))
    payload["observation_refs"].append("f" * 64)
    other_key = context_payload_key(payload)
    two = snapshots.put_snapshot_parts(connection, **arguments(connection, payload=payload, key=other_key))
    assert one.header_digest == two.header_digest
    assert one.observation_refs != two.observation_refs
    assert connection.execute("SELECT COUNT(*) FROM v2_snapshot_headers").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM v2_snapshot_parts").fetchone() == (2,)
    snapshots.validate_all(connection)


@pytest.mark.parametrize("field,value", [
    ("key", "f" * 64), ("key", "invalid"),
    ("expected_raw_payload_sha256", "f" * 64), ("expected_payload_digest", "f" * 64),
    ("expected_payload_bytes", 10), ("expected_payload_bytes", 10.0),
    ("expected_payload_bytes", True), ("expected_observation_count", 0),
    ("expected_observation_count", 1.0),
])
def test_expected_old_identities_and_counts_are_all_independently_bound(connection, field, value):
    args = arguments(connection)
    args[field] = value
    before = contents(connection)
    with pytest.raises(StorageIntegrityError):
        snapshots.put_snapshot_parts(connection, **args)
    assert contents(connection) == before
    assert connection.in_transaction


@pytest.mark.parametrize("header", [
    b"{}", b"[]", b'{"kind":"unknown","schema":1}',
    b'{"kind":"context-worker-snapshot-v1","kind":"context-worker-snapshot-v1"}',
    b'{"schema":NaN}', b'{"schema":1e999}',
])
def test_unknown_nonfinite_noncanonical_or_incomplete_header_never_becomes_a_validated_snapshot(connection, header):
    args = arguments(connection)
    args["header_bytes"] = header
    before = contents(connection)
    with pytest.raises(StorageIntegrityError):
        snapshots.put_snapshot_parts(connection, **args)
    assert contents(connection) == before


@pytest.mark.parametrize("mutation", ["extra", "missing", "observation_refs", "schema_bool", "noncanonical"])
def test_known_header_is_closed_and_cannot_hide_a_second_top_level_reference_array(connection, mutation):
    args = arguments(connection)
    import json
    header = json.loads(args["header_bytes"])
    if mutation == "extra":
        header["verified"] = True
    elif mutation == "missing":
        del header["result"]
    elif mutation == "observation_refs":
        header["observation_refs"] = []
    elif mutation == "schema_bool":
        header["schema"] = True
    args["header_bytes"] = canonical_bytes(header)
    if mutation == "noncanonical":
        args["header_bytes"] = b" " + args["header_bytes"]
    with pytest.raises(StorageIntegrityError):
        snapshots.put_snapshot_parts(connection, **args)


def test_large_unadapted_header_is_rejected_without_touching_source_or_output(connection):
    args = arguments(connection)
    oversized = b" " * (snapshots.MAX_HEADER_BYTES + 1)
    args["header_bytes"] = oversized
    before = contents(connection)
    with pytest.raises(StorageLimitError, match="header"):
        snapshots.put_snapshot_parts(connection, **args)
    assert args["header_bytes"] is oversized
    assert contents(connection) == before


def test_different_same_count_references_cannot_replace_an_old_snapshot(connection):
    args = arguments(connection)
    args["observation_refs"] = refs.put_refset(connection, ["f" * 64])
    with pytest.raises(StorageIntegrityError):
        snapshots.put_snapshot_parts(connection, **args)
    assert connection.execute("SELECT COUNT(*) FROM v2_snapshot_parts").fetchone() == (0,)


def test_changed_same_key_snapshot_is_not_overwritten(connection):
    args = arguments(connection)
    original = snapshots.put_snapshot_parts(connection, **args)
    before = contents(connection)
    key, payload, _raw, _digest = packet()
    payload["result"]["limitations"].append("different transport bytes")
    changed = arguments(connection, payload=payload, key=key)
    with pytest.raises(StorageIntegrityError, match="immutable"):
        snapshots.put_snapshot_parts(connection, **changed)
    assert contents(connection) == before
    assert b"".join(snapshots.iter_snapshot_bytes(connection, original))


def test_success_does_not_commit_and_complete_repeat_deduplicates(connection):
    args = arguments(connection)
    descriptor = snapshots.put_snapshot_parts(connection, **args)
    assert snapshots.put_snapshot_parts(connection, **args) == descriptor
    connection.rollback()
    connection.execute("BEGIN")
    assert connection.execute("SELECT COUNT(*) FROM v2_snapshot_parts").fetchone() == (0,)


@pytest.mark.parametrize("mutation", [
    "DELETE FROM v2_snapshot_headers",
    "DELETE FROM v2_snapshot_parts",
    "UPDATE v2_snapshot_headers SET content=zeroblob(header_bytes)",
    "UPDATE v2_snapshot_headers SET content=CAST(content AS TEXT)",
    "UPDATE v2_snapshot_headers SET format_version=1",
    "UPDATE v2_snapshot_parts SET format_version=1",
    "UPDATE v2_snapshot_parts SET payload_bytes=payload_bytes+0.5",
    "UPDATE v2_snapshot_parts SET observation_count=observation_count+0.5",
    "UPDATE v2_snapshot_parts SET raw_payload_sha256=printf('%064d',0)",
    "UPDATE v2_snapshot_parts SET payload_digest=printf('%064d',0)",
    "UPDATE v2_snapshot_parts SET refs_set_digest=printf('%064d',0)",
    "UPDATE v2_snapshot_parts SET header_digest=zeroblob(1048576)",
])
def test_stored_corruption_is_rejected_before_any_payload_chunk(connection, mutation):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    connection.execute(mutation)
    with pytest.raises(StorageIntegrityError):
        next(snapshots.iter_snapshot_bytes(connection, descriptor))


@pytest.mark.parametrize("change", ["commit", "rollback", "script", "write", "main_ddl", "temp_ddl", "factory"])
def test_snapshot_reader_binds_transaction_and_both_schemas_between_chunks(connection, change):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    connection.commit()
    connection.execute("BEGIN")
    reader = snapshots.iter_snapshot_bytes(connection, descriptor, chunk_bytes=13)
    assert len(next(reader)) == 13
    if change == "commit":
        connection.commit()
        connection.execute("BEGIN")
    elif change == "rollback":
        connection.rollback()
        connection.execute("BEGIN")
    elif change == "script":
        connection.executescript("BEGIN;")
    elif change == "write":
        connection.execute("UPDATE v2_snapshot_parts SET payload_bytes=payload_bytes")
    elif change == "main_ddl":
        connection.execute("CREATE TABLE another_table(id INTEGER)")
    elif change == "temp_ddl":
        connection.execute("CREATE TEMP TABLE another_table(id INTEGER)")
    else:
        connection.row_factory = sqlite3.Row
    with pytest.raises(StorageIntegrityError, match="generation"):
        next(reader)


@pytest.mark.parametrize("mutation", [
    "UPDATE v2_snapshot_parts SET key=printf('%064d', 0)",
    "INSERT INTO v2_snapshot_headers VALUES (printf('%064d',0), 2, 2, x'7b7d')",
    "ALTER TABLE v2_snapshot_parts ADD COLUMN extra TEXT",
    "CREATE TABLE v2_snapshot_unknown(id INTEGER)",
    "CREATE TRIGGER v2_snapshot_extra AFTER INSERT ON v2_snapshot_parts BEGIN SELECT 1; END",
])
def test_full_validation_rejects_foreign_keys_additional_headers_and_schema(connection, mutation):
    snapshots.put_snapshot_parts(connection, **arguments(connection))
    connection.execute(mutation)
    with pytest.raises(StorageIntegrityError):
        snapshots.validate_all(connection)


def test_legacy_materialization_is_explicit_and_bounded_and_not_used_by_streaming(connection, monkeypatch):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    with pytest.raises(TypeError):
        snapshots.materialize_snapshot(connection, descriptor)
    with pytest.raises(StorageLimitError):
        snapshots.materialize_snapshot(connection, descriptor, max_bytes=descriptor.payload_bytes - 1)
    with pytest.raises(StorageLimitError):
        snapshots.materialize_snapshot(connection, descriptor, max_bytes=snapshots.MAX_MATERIALIZE_BYTES + 1)

    def forbidden(*args, **kwargs):
        pytest.fail("normal streaming must not invoke legacy whole-payload materialization")

    monkeypatch.setattr(snapshots, "_decode_snapshot", forbidden)
    assert sum(map(len, snapshots.iter_snapshot_bytes(connection, descriptor))) == descriptor.payload_bytes
    snapshots.validate_all(connection)


def test_query_only_snapshot_read_is_repeatable_and_nonmutating(connection):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    connection.commit()
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    before = connection.total_changes
    assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor))
    assert b"".join(snapshots.iter_snapshot_bytes(connection, descriptor))
    snapshots.validate_all(connection)
    assert connection.total_changes == before


def test_snapshot_write_rejects_forged_limits_and_preserves_existing_generation(connection):
    args = arguments(connection)
    original = snapshots.put_snapshot_parts(connection, **args)
    before = contents(connection)
    limits = replace(DEFAULT_LIMITS)
    object.__setattr__(limits, "block_bytes", limits.block_bytes + 1)
    with pytest.raises(StorageLimitError):
        snapshots.put_snapshot_parts(connection, **args, limits=limits)
    assert contents(connection) == before
    assert b"".join(snapshots.iter_snapshot_bytes(connection, original))


@pytest.mark.parametrize("field,value", [
    ("format_version", 1), ("format_version", True), ("key", "f" * 64),
    ("header_bytes", 1.5), ("payload_bytes", 1.0),
    ("descriptor_digest", "f" * 64), ("payload_digest", "f" * 64),
])
def test_foreign_or_malformed_snapshot_descriptor_never_emits_bytes(connection, field, value):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    with pytest.raises(StorageIntegrityError):
        next(snapshots.iter_snapshot_bytes(connection, replace(descriptor, **{field: value})))


def test_closed_connection_is_detected_before_resuming_underlying_stream(connection):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    reader = snapshots.iter_snapshot_bytes(connection, descriptor, chunk_bytes=13)
    assert next(reader)
    connection.close()
    with pytest.raises(StorageIntegrityError, match="generation"):
        next(reader)


@pytest.mark.parametrize("size", [0, -1, True, 1.5, DEFAULT_LIMITS.block_bytes + 1])
def test_streaming_chunk_boundary_is_never_silently_widened(connection, size):
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection))
    with pytest.raises(StorageLimitError):
        next(snapshots.iter_snapshot_bytes(connection, descriptor, chunk_bytes=size))


def test_actual_sqlite_hard_quota_keeps_the_previously_committed_snapshot(connection):
    args = arguments(connection)
    original = snapshots.put_snapshot_parts(connection, **args)
    _key, changed, _raw, _digest = packet()
    changed["result"]["transport_only_large_field"] = "x" * 20_000
    new_args = arguments(connection, payload=changed, key="f" * 64)
    connection.commit()
    baseline_bytes = connection.execute("PRAGMA page_count").fetchone()[0] * 4096
    limits = replace(DEFAULT_LIMITS, input_bytes=baseline_bytes + 8192)
    assert new_args["expected_payload_bytes"] < limits.input_bytes
    connection.execute(f"PRAGMA max_page_count={limits.input_bytes // 4096}")
    connection.execute("BEGIN")
    before = contents(connection)
    with pytest.raises(StorageLimitError, match="hard allocation"):
        snapshots.put_snapshot_parts(connection, **new_args, limits=limits)
    if not connection.in_transaction:
        connection.execute("BEGIN")
    assert contents(connection) == before
    assert b"".join(snapshots.iter_snapshot_bytes(connection, original))


@pytest.mark.parametrize("change", ["cache", "max_pages", "mmap", "forged_block", "forged_reserve"])
def test_snapshot_reader_uses_same_resource_guard_before_next_chunk(connection, change):
    limits = replace(DEFAULT_LIMITS)
    descriptor = snapshots.put_snapshot_parts(connection, **arguments(connection), limits=limits)
    reader = snapshots.iter_snapshot_bytes(connection, descriptor, limits=limits, chunk_bytes=13)
    assert next(reader)
    if change == "cache":
        connection.execute("PRAGMA cache_size=-4194304")
    elif change == "max_pages":
        connection.execute("PRAGMA max_page_count=2147483646")
    elif change == "mmap":
        connection.execute("PRAGMA mmap_size=1073741824")
    elif change == "forged_block":
        object.__setattr__(limits, "block_bytes", 2**30)
    else:
        object.__setattr__(limits, "min_free_bytes", 0)
    with pytest.raises((StorageIntegrityError, StorageLimitError)):
        next(reader)


@pytest.mark.parametrize("phase", ["before_put", "before_read", "after_first_yield"])
def test_snapshot_boundaries_use_fixed_limits_owner_not_shadowed_instance_callback(connection, phase):
    limits = replace(DEFAULT_LIMITS)
    args = arguments(connection)
    descriptor = snapshots.put_snapshot_parts(connection, **args, limits=limits)
    before = contents(connection)
    if phase == "after_first_yield":
        reader = snapshots.iter_snapshot_bytes(connection, descriptor, limits=limits, chunk_bytes=13)
        assert next(reader)
    object.__setattr__(limits, "block_bytes", 2**30)
    object.__setattr__(limits, "__post_init__", lambda: None)
    with pytest.raises(StorageLimitError):
        if phase == "before_put":
            snapshots.put_snapshot_parts(connection, **args, limits=limits)
        elif phase == "before_read":
            next(snapshots.iter_snapshot_bytes(connection, descriptor, limits=limits))
        else:
            next(reader)
    assert contents(connection) == before
