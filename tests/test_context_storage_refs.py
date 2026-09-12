"""Exact-membership and caller-owned lifetime tests for C2, not a VPS proof."""
from dataclasses import replace
import hashlib
import sqlite3
import tracemalloc
from types import SimpleNamespace

import pytest

from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2 import refs
from model_artifacts import canonical_bytes


def reference(number):
    return f"{number:064x}"


@pytest.fixture
def connection(tmp_path):
    connection = sqlite3.connect(tmp_path / "refs.db", factory=TrackedConnection)
    connection.execute("PRAGMA page_size=4096")
    connection.execute("PRAGMA cache_size=-4096")
    connection.execute("PRAGMA mmap_size=0")
    connection.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096}")
    connection.execute("BEGIN")
    refs.create_schema(connection)
    connection.commit()
    connection.execute("BEGIN")
    try:
        yield connection
    finally:
        connection.close()


def contents(connection):
    return {
        table: tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1,2"))
        for table in refs._TABLES
    }


def two_blocks(connection):
    limits = replace(DEFAULT_LIMITS, block_bytes=64)
    return refs.put_refset(connection, (reference(i) for i in (4, 1, 3, 2)), limits=limits), limits


def test_complete_canonical_digest_and_repeatable_sorted_view(connection):
    original = [reference(i) for i in (100, 4, 21, 1)]
    descriptor = refs.put_refset(connection, iter(original))
    expected = sorted(original)
    assert list(refs.iter_refset(connection, descriptor)) == expected
    assert list(refs.iter_refset(connection, descriptor)) == expected
    assert descriptor.reference_count == 4
    assert descriptor.canonical_bytes == len(canonical_bytes(expected))
    assert descriptor.canonical_digest == hashlib.sha256(canonical_bytes(expected)).hexdigest()
    assert descriptor.binary_bytes == 4 * 32
    assert connection.in_transaction
    refs.validate_all(connection)


def test_empty_set_is_complete_and_deduplicated(connection):
    descriptor = refs.put_refset(connection, iter(()))
    assert descriptor == refs.put_refset(connection, ())
    assert descriptor.reference_count == descriptor.binary_bytes == descriptor.block_count == 0
    assert descriptor.canonical_bytes == 2
    assert descriptor.canonical_digest == hashlib.sha256(b"[]").hexdigest()
    assert list(refs.iter_refset(connection, descriptor)) == []
    assert connection.execute("SELECT COUNT(*) FROM v2_ref_blocks").fetchone() == (0,)
    refs.validate_all(connection)


def test_compatible_manifests_share_identical_fixed_width_blocks(connection):
    limits = replace(DEFAULT_LIMITS, block_bytes=64)
    first = refs.put_refset(connection, [reference(i) for i in (1, 2, 3, 4)], limits=limits)
    second = refs.put_refset(connection, [reference(i) for i in (1, 2, 5, 6)], limits=limits)
    assert first.block_count == second.block_count == 2
    assert connection.execute("SELECT COUNT(*) FROM v2_ref_blocks").fetchone() == (3,)
    assert connection.execute("SELECT COUNT(*) FROM v2_ref_members").fetchone() == (4,)
    assert first != second
    refs.validate_all(connection, limits=limits)


def test_manifest_digest_is_complete_canonical_json(connection):
    descriptor, _ = two_blocks(connection)
    manifest = {
        "format": "betboy-reference-set-v2",
        "format_version": 2,
        "canonical_digest": descriptor.canonical_digest,
        "reference_count": descriptor.reference_count,
        "canonical_bytes": descriptor.canonical_bytes,
        "binary_bytes": descriptor.binary_bytes,
        "block_count": descriptor.block_count,
        "blocks": [
            dict(zip(("block_index", "block_digest", "reference_count", "encoded_bytes"), row))
            for row in connection.execute(
                "SELECT block_index,block_digest,reference_count,encoded_bytes FROM v2_ref_members ORDER BY block_index"
            )
        ],
    }
    assert descriptor.set_digest == hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def test_duplicate_input_is_error_and_entire_operation_rolls_back(connection):
    original = refs.put_refset(connection, [reference(9)])
    before = contents(connection)
    with pytest.raises(StorageIntegrityError, match="duplicate"):
        refs.put_refset(connection, [reference(1), reference(2), reference(1)])
    assert contents(connection) == before
    assert list(refs.iter_refset(connection, original)) == [reference(9)]
    assert connection.in_transaction


@pytest.mark.parametrize("bad", [None, True, 123, b"a" * 64, "A" * 64, "g" * 64, "1" * 63, "1" * 65, "1" * 64 + "\n"])
def test_invalid_reference_never_partially_publishes(connection, bad):
    before = contents(connection)
    with pytest.raises(StorageIntegrityError):
        refs.put_refset(connection, iter([reference(1), bad]))
    assert contents(connection) == before


def test_failing_source_generator_preserves_caller_transaction(connection):
    refs.put_refset(connection, [reference(99)])
    before = contents(connection)

    def source():
        yield reference(1)
        raise ValueError("source interrupted")

    with pytest.raises(ValueError, match="source interrupted"):
        refs.put_refset(connection, source())
    assert contents(connection) == before
    assert connection.in_transaction


def test_module_never_commits_successful_changes(connection):
    descriptor = refs.put_refset(connection, [reference(1)])
    connection.rollback()
    connection.execute("BEGIN")
    assert connection.execute("SELECT COUNT(*) FROM v2_ref_sets").fetchone() == (0,)
    with pytest.raises(StorageIntegrityError, match="missing"):
        list(refs.iter_refset(connection, descriptor))


def test_raw_or_memory_connections_are_not_lifetime_safe(tmp_path):
    raw = sqlite3.connect(tmp_path / "raw.db")
    raw.execute("BEGIN")
    with pytest.raises(StorageIntegrityError, match="tracked"):
        refs.create_schema(raw)
    raw.close()
    memory = sqlite3.connect(":memory:", factory=TrackedConnection)
    memory.execute("BEGIN")
    with pytest.raises(StorageIntegrityError, match="on-disk"):
        refs.create_schema(memory)
    memory.close()


@pytest.mark.parametrize("operation", ["schema", "put", "read", "all"])
def test_every_api_requires_explicit_caller_transaction(connection, operation):
    descriptor = refs.put_refset(connection, ())
    connection.commit()
    with pytest.raises(StorageIntegrityError, match="transaction"):
        if operation == "schema":
            refs.create_schema(connection)
        elif operation == "put":
            refs.put_refset(connection, ())
        elif operation == "read":
            list(refs.iter_refset(connection, descriptor))
        else:
            refs.validate_all(connection)


@pytest.mark.parametrize("mutation", [
    "DELETE FROM v2_ref_blocks WHERE digest=(SELECT block_digest FROM v2_ref_members WHERE block_index=1)",
    "DELETE FROM v2_ref_members WHERE block_index=1",
    "UPDATE v2_ref_members SET block_index=3 WHERE block_index=1",
    "UPDATE v2_ref_members SET block_index=block_index+0.5",
    "UPDATE v2_ref_members SET encoded_bytes=encoded_bytes+0.5",
    "UPDATE v2_ref_blocks SET reference_count=reference_count+0.5",
    "UPDATE v2_ref_blocks SET format_version=1",
    "UPDATE v2_ref_blocks SET encoded_bytes=encoded_bytes+32",
    "UPDATE v2_ref_blocks SET content=CAST(content AS TEXT)",
    "UPDATE v2_ref_sets SET reference_count=reference_count+0.5",
    "UPDATE v2_ref_sets SET canonical_bytes=canonical_bytes+0.5",
    "UPDATE v2_ref_sets SET format_version=1",
    "UPDATE v2_ref_sets SET canonical_digest=printf('%064d', 0)",
    "UPDATE v2_ref_sets SET canonical_digest=zeroblob(1048576)",
    "UPDATE v2_ref_members SET block_digest=zeroblob(1048576)",
])
def test_bad_storage_and_manifest_fail_before_first_reference(connection, mutation):
    descriptor, limits = two_blocks(connection)
    connection.execute(mutation)
    with pytest.raises(StorageIntegrityError):
        next(refs.iter_refset(connection, descriptor, limits=limits))
    with pytest.raises(StorageIntegrityError):
        refs.validate_all(connection, limits=limits)


def test_equal_count_other_membership_rehash_does_not_match_old_descriptor(connection):
    descriptor, limits = two_blocks(connection)
    old_digest, = connection.execute("SELECT block_digest FROM v2_ref_members WHERE block_index=1").fetchone()
    altered = bytes.fromhex(reference(3) + reference(5))
    new_digest = refs._block_digest(altered)
    connection.execute("UPDATE v2_ref_blocks SET digest=?, content=? WHERE digest=?", (new_digest, altered, old_digest))
    connection.execute("UPDATE v2_ref_members SET block_digest=? WHERE block_index=1", (new_digest,))
    with pytest.raises(StorageIntegrityError, match="canonical"):
        next(refs.iter_refset(connection, descriptor, limits=limits))


def test_additional_duplicate_block_and_swapped_blocks_are_rejected(connection):
    descriptor, limits = two_blocks(connection)
    before = contents(connection)
    connection.execute("SAVEPOINT mutation")
    connection.execute(
        "INSERT INTO v2_ref_members SELECT set_digest,2,block_digest,reference_count,encoded_bytes "
        "FROM v2_ref_members WHERE block_index=0"
    )
    with pytest.raises(StorageIntegrityError):
        list(refs.iter_refset(connection, descriptor, limits=limits))
    connection.execute("ROLLBACK TO mutation")
    connection.execute("RELEASE mutation")
    assert contents(connection) == before
    connection.execute("UPDATE v2_ref_members SET block_index=block_index+100")
    connection.execute("UPDATE v2_ref_members SET block_index=101-block_index")
    with pytest.raises(StorageIntegrityError, match="unordered"):
        list(refs.iter_refset(connection, descriptor, limits=limits))


def test_duplicated_binary_reference_fails_even_with_recomputed_block_digest(connection):
    descriptor, limits = two_blocks(connection)
    previous, = connection.execute("SELECT block_digest FROM v2_ref_members WHERE block_index=0").fetchone()
    content = bytes.fromhex(reference(1) * 2)
    new_digest = refs._block_digest(content)
    connection.execute("UPDATE v2_ref_blocks SET digest=?,content=? WHERE digest=?", (new_digest, content, previous))
    connection.execute("UPDATE v2_ref_members SET block_digest=? WHERE block_index=0", (new_digest,))
    with pytest.raises(StorageIntegrityError, match="unique"):
        next(refs.iter_refset(connection, descriptor, limits=limits))


@pytest.mark.parametrize("field,value", [
    ("format_version", 1), ("format_version", True), ("reference_count", 4.0),
    ("canonical_bytes", 269.0), ("binary_bytes", 129), ("block_count", 3),
    ("canonical_digest", "f" * 64), ("set_digest", "f" * 64),
])
def test_foreign_or_malformed_descriptors_are_not_accepted(connection, field, value):
    descriptor, limits = two_blocks(connection)
    with pytest.raises(StorageIntegrityError):
        list(refs.iter_refset(connection, replace(descriptor, **{field: value}), limits=limits))


@pytest.mark.parametrize("change", ["commit", "rollback", "sql_commit", "script", "write", "row_factory", "text_factory", "isolation", "main_ddl", "temp_ddl"])
def test_reader_cannot_survive_changed_transaction_or_factories(connection, change):
    descriptor, limits = two_blocks(connection)
    connection.commit()
    connection.execute("BEGIN")
    reader = refs.iter_refset(connection, descriptor, limits=limits)
    assert next(reader) == reference(1)
    if change == "commit":
        connection.commit()
        connection.execute("BEGIN")
    elif change == "rollback":
        connection.rollback()
        connection.execute("BEGIN")
    elif change == "sql_commit":
        connection.execute("COMMIT")
        connection.execute("BEGIN")
    elif change == "script":
        connection.executescript("BEGIN;")
    elif change == "write":
        connection.execute("UPDATE v2_ref_sets SET block_count=block_count")
    elif change == "row_factory":
        connection.row_factory = sqlite3.Row
    elif change == "text_factory":
        connection.text_factory = bytes
    elif change == "main_ddl":
        connection.execute("CREATE TABLE unexpected_during_read (id INTEGER)")
    elif change == "temp_ddl":
        connection.execute("CREATE TEMP TABLE unexpected_during_read (id INTEGER)")
    else:
        connection.isolation_level = None
        connection.execute("BEGIN")
    with pytest.raises(StorageIntegrityError, match="generation"):
        next(reader)


def test_reader_fails_if_connection_closes(connection):
    descriptor = refs.put_refset(connection, [reference(1), reference(2)])
    reader = refs.iter_refset(connection, descriptor)
    assert next(reader) == reference(1)
    connection.close()
    with pytest.raises(StorageIntegrityError, match="generation"):
        next(reader)


@pytest.mark.parametrize("mutation", [
    "INSERT INTO v2_ref_staging VALUES ('01234567890123456789012345678901', zeroblob(32))",
    "UPDATE v2_ref_members SET set_digest=printf('%064d', 0)",
    "INSERT INTO v2_ref_blocks VALUES (printf('%064d',0), 2, 1, 32, zeroblob(32))",
    "ALTER TABLE v2_ref_sets ADD COLUMN unexpected TEXT",
    "CREATE TABLE v2_ref_foreign (id INTEGER)",
    "CREATE TRIGGER v2_ref_test AFTER INSERT ON v2_ref_sets BEGIN SELECT 1; END",
])
def test_full_validation_rejects_incomplete_foreign_and_unreachable_rows(connection, mutation):
    refs.put_refset(connection, [reference(1)])
    connection.execute(mutation)
    with pytest.raises(StorageIntegrityError):
        refs.validate_all(connection)


def test_block_quota_rolls_back_new_rows_without_losing_old_sets(connection):
    original = refs.put_refset(connection, [reference(99)])
    before = contents(connection)
    limits = replace(DEFAULT_LIMITS, block_bytes=32, blocks_per_set=1)
    with pytest.raises(StorageLimitError, match="block-count"):
        refs.put_refset(connection, [reference(1), reference(2)], limits=limits)
    assert contents(connection) == before
    assert list(refs.iter_refset(connection, original)) == [reference(99)]


def test_block_byte_quota_is_checked_before_materialization(connection):
    descriptor, _ = two_blocks(connection)
    with pytest.raises(StorageLimitError, match="block budget"):
        next(refs.iter_refset(connection, descriptor, limits=replace(DEFAULT_LIMITS, block_bytes=32)))


def test_database_quota_accounts_for_unrelated_tables_and_freelist(connection):
    connection.execute("CREATE TABLE unrelated (payload BLOB)")
    connection.execute("INSERT INTO unrelated VALUES (zeroblob(200000))")
    connection.execute("DELETE FROM unrelated")
    limits = replace(DEFAULT_LIMITS, input_bytes=128000)
    with pytest.raises(StorageLimitError, match="complete reference output"):
        refs.put_refset(connection, (), limits=limits)
    assert connection.in_transaction


def test_growth_quota_failure_rolls_back_staged_references(connection):
    before = contents(connection)
    baseline = connection.execute("PRAGMA page_count").fetchone()[0] * connection.execute("PRAGMA page_size").fetchone()[0]
    limits = replace(DEFAULT_LIMITS, input_bytes=baseline + 16384)
    connection.commit()
    connection.execute(f"PRAGMA max_page_count={limits.input_bytes // 4096}")
    connection.execute("BEGIN")
    with pytest.raises(StorageLimitError):
        refs.put_refset(connection, (reference(i) for i in range(5000)), limits=limits)
    if not connection.in_transaction:
        connection.execute("BEGIN")
    assert contents(connection) == before


def test_workspace_and_free_space_fail_closed(connection, monkeypatch):
    with pytest.raises(StorageLimitError, match="workspace"):
        refs.put_refset(connection, (), limits=replace(DEFAULT_LIMITS, workspace_bytes=1))
    monkeypatch.setattr(refs.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(StorageLimitError, match="reserve"):
        refs.put_refset(connection, ())
    assert connection.execute("SELECT COUNT(*) FROM v2_ref_sets").fetchone() == (0,)


def test_large_input_roundtrip_uses_canonical_sorted_order(connection):
    count = 10_000
    descriptor = refs.put_refset(
        connection, (reference(i) for i in reversed(range(count))),
        limits=replace(DEFAULT_LIMITS, block_bytes=4096),
    )
    iterator = refs.iter_refset(connection, descriptor)
    for expected, actual in enumerate(iterator):
        assert actual == reference(expected)
    assert expected == count - 1
    assert descriptor.reference_count == count
    assert connection.execute("SELECT COUNT(*) FROM v2_ref_staging").fetchone() == (0,)
    refs.validate_all(connection)


def test_standard_sqlite_row_factory_is_supported(connection):
    connection.row_factory = sqlite3.Row
    descriptor = refs.put_refset(connection, [reference(1)])
    assert list(refs.iter_refset(connection, descriptor)) == [reference(1)]
    refs.validate_all(connection)


def test_query_only_repeated_reads_need_no_hidden_write(connection):
    descriptor = refs.put_refset(connection, [reference(2), reference(1)])
    connection.commit()
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    before = connection.total_changes
    assert list(refs.iter_refset(connection, descriptor)) == [reference(1), reference(2)]
    assert list(refs.iter_refset(connection, descriptor)) == [reference(1), reference(2)]
    refs.validate_all(connection)
    assert connection.total_changes == before


def test_python_reference_storage_stays_bounded_for_a_large_stream(connection):
    # This is Python-allocation evidence only, not native RSS or VPS acceptance.
    count = 100_000
    limits = replace(DEFAULT_LIMITS, block_bytes=4096)
    tracemalloc.start()
    try:
        descriptor = refs.put_refset(connection, (reference(i) for i in reversed(range(count))), limits=limits)
        for expected, actual in enumerate(refs.iter_refset(connection, descriptor, limits=limits)):
            assert actual == reference(expected)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert expected == count - 1
    assert peak < 8 * 1024**2


@pytest.mark.parametrize("pragma", [
    "PRAGMA max_page_count=2147483646", "PRAGMA cache_size=1000",
    "PRAGMA cache_size=-16384", "PRAGMA mmap_size=1048576",
])
def test_connection_resource_admission_is_explicit_without_silent_reconfiguration(connection, pragma):
    connection.commit()
    connection.execute(pragma)
    connection.execute("BEGIN")
    before = contents(connection)
    with pytest.raises(StorageLimitError):
        refs.put_refset(connection, [reference(1)])
    assert contents(connection) == before


@pytest.mark.parametrize("field", ["input_bytes", "block_bytes", "workspace_bytes", "blocks_per_set", "tour_history_bytes"])
def test_forged_frozen_limits_cannot_widen_the_approved_envelope(connection, field):
    forged = replace(DEFAULT_LIMITS)
    object.__setattr__(forged, field, getattr(forged, field) + 1)
    with pytest.raises(StorageLimitError):
        refs.put_refset(connection, [reference(1)], limits=forged)


def test_forged_free_space_reserve_cannot_be_lowered(connection):
    forged = replace(DEFAULT_LIMITS)
    object.__setattr__(forged, "min_free_bytes", 0)
    with pytest.raises(StorageLimitError):
        refs.put_refset(connection, [reference(1)], limits=forged)


@pytest.mark.parametrize("change", ["cache", "max_pages", "mmap", "forged_block", "forged_reserve"])
def test_resource_contract_is_bound_before_every_next_reference(connection, change):
    limits = replace(DEFAULT_LIMITS)
    descriptor = refs.put_refset(connection, [reference(1), reference(2)], limits=limits)
    reader = refs.iter_refset(connection, descriptor, limits=limits)
    assert next(reader) == reference(1)
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


def test_close_exactly_after_last_reference_of_block_is_a_typed_lifetime_error(connection):
    limits = replace(DEFAULT_LIMITS, block_bytes=32)
    descriptor = refs.put_refset(connection, [reference(1), reference(2)], limits=limits)
    reader = refs.iter_refset(connection, descriptor, limits=limits)
    assert next(reader) == reference(1)
    connection.close()
    with pytest.raises(StorageIntegrityError, match="generation"):
        next(reader)


@pytest.mark.parametrize("phase", ["before_put", "before_read", "after_first_yield"])
def test_shadowed_instance_callback_cannot_bypass_fixed_limits_owner(connection, phase):
    limits = replace(DEFAULT_LIMITS)
    descriptor = refs.put_refset(connection, [reference(1), reference(2)], limits=limits)
    before = contents(connection)
    if phase == "after_first_yield":
        reader = refs.iter_refset(connection, descriptor, limits=limits)
        assert next(reader) == reference(1)
    object.__setattr__(limits, "block_bytes", 2**30)
    object.__setattr__(limits, "__post_init__", lambda: None)
    with pytest.raises(StorageLimitError):
        if phase == "before_put":
            refs.put_refset(connection, [reference(3)], limits=limits)
        elif phase == "before_read":
            next(refs.iter_refset(connection, descriptor, limits=limits))
        else:
            next(reader)
    assert contents(connection) == before


@pytest.mark.parametrize("table,column,size", [
    ("v2_ref_blocks", "digest", 64), ("v2_ref_sets", "set_digest", 64),
    ("v2_ref_sets", "canonical_digest", 64), ("v2_ref_members", "set_digest", 64),
    ("v2_ref_members", "block_digest", 64), ("v2_ref_staging", "stage_id", 32),
])
def test_nul_suffix_is_rejected_before_loading_any_reference_metadata(connection, table, column, size):
    refs.put_refset(connection, [reference(1)])
    if table == "v2_ref_staging":
        connection.execute("INSERT INTO v2_ref_staging VALUES(?,?)", ("1" * 32, b"a" * 32))
    damaged = "f" * size + "\0" + "suffix"
    connection.execute(f"UPDATE {table} SET {column}=?", (damaged,))
    assert connection.execute(f"SELECT length({column}),octet_length({column}) FROM {table}").fetchone() == (size, size + 7)
    with pytest.raises(StorageIntegrityError, match="bounded"):
        refs._check_shapes(connection)


def test_huge_nul_metadata_is_rejected_before_a_large_python_fetch(connection):
    descriptor = refs.put_refset(connection, [reference(1)])
    connection.execute("UPDATE v2_ref_sets SET canonical_digest=?", ("f" * 64 + "\0" + "x" * (20 * 1024**2),))
    tracemalloc.start()
    try:
        with pytest.raises(StorageIntegrityError):
            next(refs.iter_refset(connection, descriptor))
        assert tracemalloc.get_traced_memory()[1] < 1024**2
    finally:
        tracemalloc.stop()


@pytest.mark.parametrize("with_validator", [False, True])
def test_atomic_final_validator_follows_real_footprint_once_without_committing(connection, monkeypatch, with_validator):
    events = []
    actual_usage = refs.shutil.disk_usage
    def measured_usage(path):
        result = actual_usage(path)
        events.append("footprint")
        return result
    def validate_pending_input():
        assert connection.in_transaction
        assert connection.execute("SELECT * FROM pending_publication").fetchall() == [("complete",)]
        events.append("validate")
    monkeypatch.setattr(refs.shutil, "disk_usage", measured_usage)
    options = {"final_validate": validate_pending_input} if with_validator else {}
    with refs._atomic(connection, DEFAULT_LIMITS, **options):
        connection.execute("CREATE TABLE pending_publication(value TEXT)")
        connection.execute("INSERT INTO pending_publication VALUES('complete')")
        events.append("body")
    assert events == ["footprint", "body", "footprint"] + (["validate"] if with_validator else [])
    assert connection.in_transaction
    assert connection.execute("SELECT * FROM pending_publication").fetchall() == [("complete",)]
    connection.rollback()
    connection.execute("BEGIN")
    assert connection.execute("SELECT name FROM sqlite_schema WHERE name='pending_publication'").fetchall() == []


@pytest.mark.parametrize("failure", ["input-lifetime", "ordinary", "actual-sqlite"])
def test_atomic_final_validator_failure_rolls_back_with_existing_error_conversion(connection, failure):
    connection.execute("CREATE TABLE caller_marker(value TEXT)")
    connection.execute("INSERT INTO caller_marker VALUES('keep')")
    calls = []
    def validate_pending_input():
        assert connection.execute("SELECT * FROM pending_publication").fetchall() == [("complete",)]
        calls.append("validate")
        if failure == "input-lifetime":
            raise StorageIntegrityError("actual input lifetime stopped")
        if failure == "ordinary":
            raise ValueError("actual input validator stopped")
        connection.execute("SELECT * FROM absent_validator_input")
    expected = ValueError if failure == "ordinary" else StorageIntegrityError
    with pytest.raises(expected) as error:
        with refs._atomic(connection, DEFAULT_LIMITS, final_validate=validate_pending_input):
            connection.execute("CREATE TABLE pending_publication(value TEXT)")
            connection.execute("INSERT INTO pending_publication VALUES('complete')")
    assert calls == ["validate"]
    assert connection.in_transaction
    assert connection.execute("SELECT * FROM caller_marker").fetchall() == [("keep",)]
    assert connection.execute("SELECT name FROM sqlite_schema WHERE name='pending_publication'").fetchall() == []
    if failure == "actual-sqlite":
        assert isinstance(error.value.__cause__, sqlite3.OperationalError)
        assert error.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_ERROR
    else:
        assert error.value.__cause__ is None


@pytest.mark.parametrize("failure", ["body", "post-yield-footprint"])
def test_atomic_final_validator_is_not_called_after_an_earlier_failure(connection, monkeypatch, failure):
    connection.execute("CREATE TABLE caller_marker(value TEXT)")
    connection.execute("INSERT INTO caller_marker VALUES('keep')")
    usage_calls = 0
    actual_usage = refs.shutil.disk_usage
    def measured_usage(path):
        nonlocal usage_calls
        result = actual_usage(path)
        usage_calls += 1
        if usage_calls == 2 and failure == "post-yield-footprint":
            raise OSError("actual final footprint measurement interrupted")
        return result
    validator_calls = []
    def validate_pending_input():
        validator_calls.append("validate")
    monkeypatch.setattr(refs.shutil, "disk_usage", measured_usage)
    expected = RuntimeError if failure == "body" else StorageIntegrityError
    with pytest.raises(expected):
        with refs._atomic(connection, DEFAULT_LIMITS, final_validate=validate_pending_input):
            connection.execute("CREATE TABLE pending_publication(value TEXT)")
            if failure == "body":
                raise RuntimeError("actual publication interrupted")
    assert validator_calls == []
    assert connection.in_transaction
    assert connection.execute("SELECT * FROM caller_marker").fetchall() == [("keep",)]
    assert connection.execute("SELECT name FROM sqlite_schema WHERE name='pending_publication'").fetchall() == []
