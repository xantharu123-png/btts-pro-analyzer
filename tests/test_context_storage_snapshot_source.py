"""Real raw-row coverage and bounded transport only, never semantic approval."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import gc
import hashlib
import sqlite3
import tracemalloc
from uuid import uuid4

import pytest

from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection
from context_snapshots import compute_once, _payload_digest
from context_storage_v2 import refs, snapshots, snapshot_source as owner
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.inventory import inventory_raw
from context_transport import calculate_context_payload, context_payload_key
from model_artifacts import canonical_bytes
from test_context_transport import inputs


def packet(*, family="tennis:winner", with_effect=False, count=None):
    payload = calculate_context_payload(**inputs(family=family, with_effect=with_effect))
    key = context_payload_key(payload)
    if count is not None:
        # Synthetic exact reference cardinality, not a model-valid enlarged run.
        payload["observation_refs"] = [f"{number:064x}" for number in range(count)]
    return key, payload


@contextmanager
def source(tmp_path, packets=(), *, raw_rows=(), optional=True, encoding="UTF-8", writable=False):
    path = tmp_path / ("source-" + uuid4().hex + ".sqlite")
    writer = sqlite3.connect(path)
    writer.execute(f"PRAGMA encoding='{encoding}'")
    for name, sql in _SCHEMA.items():
        if optional or name in {"artifacts", "manifests", "active_manifest"}:
            writer.execute(sql)
    writer.commit()
    writer.close()
    for key, payload in packets:
        # Exercise the actual unchanged persistence owner, not just manually
        # stamped JSON rows or standalone parts descriptors.
        assert compute_once(path, key, lambda payload=payload: payload) == payload
    writer = sqlite3.connect(path)
    writer.executemany("INSERT INTO context_snapshots VALUES(?,?,?)", raw_rows) if raw_rows else None
    writer.commit()
    writer.close()
    con = sqlite3.connect(path if writable else path.as_uri() + "?mode=ro", uri=not writable,
                          factory=TrackedConnection)
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute("PRAGMA query_only=ON")
    con.execute("BEGIN")
    try:
        yield path, con
    finally:
        con.close()


@contextmanager
def target(tmp_path):
    path = tmp_path / ("parts-" + uuid4().hex + ".sqlite")
    con = sqlite3.connect(path, factory=TrackedConnection)
    con.execute("PRAGMA page_size=4096")
    con.execute("PRAGMA cache_size=-4096")
    con.execute("PRAGMA mmap_size=0")
    con.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096}")
    con.execute("BEGIN")
    refs.create_schema(con)
    snapshots.create_schema(con)
    con.commit()
    con.execute("BEGIN")
    try:
        yield con
    finally:
        con.close()


def contents(con):
    return {name: tuple(con.execute(f'SELECT * FROM "{name}" ORDER BY 1'))
            for (name,) in con.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")}


def adapt(con, output, *, limits=DEFAULT_LIMITS):
    return owner.adapt_source_snapshots(con, output, inventory_raw(con, limits=limits), limits=limits)


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("with_effect", [False, True])
def test_actual_legacy_owner_snapshot_is_byte_identical_and_source_is_untouched(tmp_path, family, with_effect):
    key, payload = packet(family=family, with_effect=with_effect)
    raw = canonical_bytes(payload)
    with source(tmp_path, [(key, payload)]) as (path, con), target(tmp_path) as output:
        before = path.read_bytes(), con.total_changes, con.transaction_generation
        expected = inventory_raw(con)
        descriptor = owner.adapt_source_snapshots(con, output, expected)
        assert descriptor.source_inventory == expected
        assert descriptor.snapshot_count == descriptor.adapted_count == 1
        assert descriptor.unadapted_count == 0
        part = snapshots._read_descriptor(output, key)
        assert b"".join(snapshots.iter_snapshot_bytes(output, part)) == raw
        assert part.payload_digest == _payload_digest(key, payload)
        assert descriptor.snapshot_row_digest == next(table.row_digest for table in expected.tables if table.name == "context_snapshots")
        output.commit()
        output.execute("PRAGMA query_only=ON")
        output.execute("BEGIN")
        changed = output.total_changes
        owner.validate_source_coverage(con, output, descriptor)
        owner.validate_source_coverage(con, output, descriptor)
        assert output.total_changes == changed
        assert (path.read_bytes(), con.total_changes, con.transaction_generation) == before
        assert con.in_transaction and output.in_transaction


@pytest.mark.parametrize("optional", [False, True])
def test_absent_and_present_empty_optional_snapshot_table_are_distinct_complete_coverage(tmp_path, optional):
    with source(tmp_path, optional=optional) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        assert descriptor.snapshot_table_present is optional
        assert descriptor.snapshot_count == descriptor.adapted_count == descriptor.unadapted_count == 0
        assert (descriptor.snapshot_row_digest == "0" * 64) is not optional
        owner.validate_source_coverage(con, output, descriptor)


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_nested_strings_escaped_delimiters_unicode_and_nested_refs_stay_in_the_header(tmp_path, encoding):
    key, payload = packet()
    payload["result"]["nested"] = {"observation_refs": ["not-extracted"], "quoted": '\\"},["observation_refs":[] 🟩 Zürich Ä\0'}
    with source(tmp_path, [(key, payload)], encoding=encoding) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        part = snapshots._read_descriptor(output, key)
        assert part.observation_refs.reference_count == len(payload["observation_refs"])
        assert b"".join(snapshots.iter_snapshot_bytes(output, part, chunk_bytes=17)) == canonical_bytes(payload)
        owner.validate_source_coverage(con, output, descriptor)


@pytest.mark.parametrize("count", [0, 1, 500])
def test_empty_single_and_multiblock_real_arrays_have_complete_membership(tmp_path, count):
    key, payload = packet(count=count)
    limits = replace(DEFAULT_LIMITS, block_bytes=16384)
    with source(tmp_path, [(key, payload)]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output, limits=limits)
        part = snapshots._read_descriptor(output, key)
        assert tuple(refs.iter_refset(output, part.observation_refs, limits=limits)) == tuple(payload["observation_refs"])
        assert part.observation_refs.reference_count == count
        assert descriptor.snapshot_count == 1


def test_unknown_kind_and_oversized_nonref_header_keep_raw_coverage_without_orphan_parts(tmp_path):
    key, known = packet()
    unknown = {"kind": "not-this-adapter", "observation_refs": [{"future-shape": "kept raw"}]}
    large = deepcopy(known)
    large["observation_refs"] = ["f" * 64]
    large["result"]["large-nonref"] = "x" * (snapshots.MAX_HEADER_BYTES + 1)
    packets = [(key, known), ("e" * 64, unknown), ("f" * 64, large)]
    with source(tmp_path, packets) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        assert (descriptor.snapshot_count, descriptor.adapted_count, descriptor.unadapted_count) == (3, 1, 2)
        rows = tuple(output.execute("SELECT raw_payload_sha256,payload_bytes,status,reason,parts_key FROM v2_snap_source_rows"))
        for _key, payload in packets:
            raw = canonical_bytes(payload)
            row = next(row for row in rows if row[0] == hashlib.sha256(raw).hexdigest())
            assert row[1] == len(raw)
        assert {row[3] for row in rows} == {"", "unknown-header", "header-limit"}
        assert all(row[4] == "" for row in rows if row[2] == "unadapted")
        assert output.execute("SELECT count(*) FROM v2_snapshot_parts").fetchone() == (1,)
        assert output.execute("SELECT count(*) FROM v2_ref_staging").fetchone() == (0,)
        assert output.execute("SELECT count(*) FROM v2_ref_sets").fetchone() == (1,)
        snapshots.validate_all(output)
        owner.validate_source_coverage(con, output, descriptor)


@pytest.mark.parametrize("column", ["key", "payload_digest"])
@pytest.mark.parametrize("value", ["a" * 64 + "\0" + "x" * 65536, "A" * 64, "", "x" * 1048577],
                         ids=["nul-tail", "uppercase", "empty", "oversized"])
def test_arbitrary_real_text_identities_are_raw_only_and_never_loaded_as_large_strings(tmp_path, column, value):
    key, payload = packet()
    row = [key, canonical_bytes(payload), _payload_digest(key, payload)]
    row[0 if column == "key" else 2] = value
    limits = replace(DEFAULT_LIMITS, block_bytes=16384)
    with source(tmp_path, raw_rows=[tuple(row)]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output, limits=limits)
        assert descriptor.adapted_count == 0 and descriptor.unadapted_count == 1
        assert output.execute("SELECT reason FROM v2_snap_source_rows").fetchone() == ("invalid-key" if column == "key" else "invalid-payload-digest",)
        for table in ("v2_snapshot_parts", "v2_snapshot_headers", "v2_ref_sets", "v2_ref_blocks", "v2_ref_members", "v2_ref_staging"):
            assert output.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
        owner.validate_source_coverage(con, output, descriptor, limits=limits)


@pytest.mark.parametrize("difference", ["missing", "additional", "same-count-membership", "other-table", "missing-table"])
def test_expected_inventory_is_whole_fresh_and_not_a_count_only_snapshot_subset(tmp_path, difference):
    original = packet(count=3)
    changed = deepcopy(original[1])
    changed["observation_refs"][-1] = "f" * 64
    packets = [] if difference in {"missing", "missing-table"} else [(original[0], changed)] if difference == "same-count-membership" else [original]
    if difference == "additional":
        packets.append(("f" * 64, changed))
    with source(tmp_path, [original]) as (_left, left), source(tmp_path, packets, optional=difference != "missing-table", writable=True) as (_right, right), target(tmp_path) as output:
        if difference == "other-table":
            right.rollback()
            right.execute("PRAGMA query_only=OFF")
            right.execute("INSERT INTO context_contents VALUES(?,?)", ("9" * 64, b"unreferenced future source bytes"))
            right.commit()
            right.execute("PRAGMA query_only=ON")
            right.execute("BEGIN")
        before = contents(output)
        with pytest.raises(StorageIntegrityError, match="expected complete raw inventory"):
            owner.adapt_source_snapshots(right, output, inventory_raw(left))
        assert contents(output) == before


@pytest.mark.parametrize("mutation", ["duplicate", "descending", "uppercase", "whitespace", "escaped-ref", "object-ref", "escaped-key", "duplicate-key", "trailing", "order", "missing-refs", "wrong-schema", "digest"])
def test_malformed_known_snapshots_fail_the_whole_batch_without_partial_success(tmp_path, mutation):
    key, payload = packet(count=3)
    bad = deepcopy(payload)
    if mutation == "duplicate":
        bad["observation_refs"][1] = bad["observation_refs"][0]
    elif mutation == "descending":
        bad["observation_refs"].reverse()
    elif mutation == "uppercase":
        bad["observation_refs"][-1] = "F" * 64
    elif mutation == "object-ref":
        bad["observation_refs"][-1] = {"digest": "f" * 64}
    elif mutation == "missing-refs":
        del bad["observation_refs"]
    elif mutation == "wrong-schema":
        bad["schema"] = 2
    raw = canonical_bytes(bad)
    if mutation == "whitespace":
        raw = raw.replace(b'"observation_refs":[', b'"observation_refs": [')
    elif mutation == "escaped-ref":
        raw = raw.replace(b'"' + b"0" * 64 + b'"', b'"\\u0030' + b"0" * 63 + b'"', 1)
    elif mutation == "escaped-key":
        raw = raw.replace(b'"observation_refs":', b'"observation_\\u0072efs":')
    elif mutation == "duplicate-key":
        raw = raw.replace(b'"observation_refs":', b'"observation_refs":[],"observation_refs":')
    elif mutation == "trailing":
        raw += b" "
    elif mutation == "order":
        raw = raw.replace(b'{"approval":', b'{"zz":0,"approval":', 1)
    digest = "d" * 64 if mutation == "digest" else _payload_digest("f" * 64, bad)
    with source(tmp_path, [("0" * 64, payload)], raw_rows=[("f" * 64, raw, digest)]) as (_path, con), target(tmp_path) as output:
        before = contents(output)
        with pytest.raises(StorageIntegrityError):
            adapt(con, output)
        assert contents(output) == before
        assert output.in_transaction


@pytest.mark.parametrize("change", ["commit", "rollback", "script", "main-ddl", "temp-ddl", "write"])
@pytest.mark.parametrize("phase", ["build", "validate"])
def test_source_reader_end_restart_write_and_ddl_are_not_revived(tmp_path, monkeypatch, change, phase):
    with source(tmp_path, [packet()], writable=True) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output) if phase == "validate" else None
        before = contents(output)
        original, fired = owner._Payload.take, False
        def changed(self, size):
            nonlocal fired
            if not fired:
                fired = True
                if change in {"commit", "rollback"}:
                    getattr(con, change)()
                    con.execute("BEGIN")
                elif change == "script":
                    con.executescript("BEGIN;")
                else:
                    con.execute("PRAGMA query_only=OFF")
                    con.execute({"main-ddl": "CREATE TABLE unrelated(x INTEGER)",
                                 "temp-ddl": "CREATE TEMP TABLE unrelated(x INTEGER)",
                                 "write": "UPDATE context_snapshots SET payload_digest=payload_digest"}[change])
                    con.execute("PRAGMA query_only=ON")
            return original(self, size)
        monkeypatch.setattr(owner._Payload, "take", changed)
        with pytest.raises(StorageIntegrityError):
            if phase == "build":
                adapt(con, output)
            else:
                owner.validate_source_coverage(con, output, descriptor)
        assert fired
        assert contents(output) == before


@pytest.mark.parametrize("mutation", [
    "DELETE FROM v2_snap_source_rows",
    "DELETE FROM v2_snapshot_parts",
    "UPDATE v2_snap_source_rows SET reason='unknown-header',status='unadapted',parts_key=''",
    "UPDATE v2_snap_source_rows SET source_row_digest=printf('%064d',0)",
    "UPDATE v2_snap_source_rows SET raw_payload_sha256=printf('%064d',0)",
    "UPDATE v2_snap_source_rows SET parts_key=parts_key||char(0)||hex(zeroblob(1048576))",
    "UPDATE v2_snap_source_rows SET status=hex(zeroblob(1048576))",
    "UPDATE v2_snap_source_manifest SET adapted_count=0",
    "INSERT INTO v2_snap_source_manifest SELECT 2,format_version,source_inventory_digest,source_schema_digest,snapshot_table_present,snapshot_count,snapshot_value_bytes,snapshot_row_digest,adapted_count,unadapted_count,coverage_digest,descriptor_digest FROM v2_snap_source_manifest",
    "CREATE TABLE v2_snap_source_foreign(x INTEGER)",
    "ALTER TABLE v2_snap_source_rows ADD COLUMN extra TEXT",
    "CREATE TRIGGER v2_snap_source_tr AFTER INSERT ON v2_snap_source_rows BEGIN SELECT 1; END",
])
def test_complete_validation_rejects_missing_additional_foreign_and_unbounded_output(tmp_path, mutation):
    with source(tmp_path, [packet()]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        output.execute(mutation)
        with pytest.raises(StorageIntegrityError):
            owner.validate_source_coverage(con, output, descriptor)


def test_existing_target_is_not_overwritten_or_guessed_as_a_resume(tmp_path):
    with source(tmp_path, [packet()]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        before = contents(output)
        with pytest.raises(StorageIntegrityError, match="fresh unowned"):
            adapt(con, output)
        assert contents(output) == before
        owner.validate_source_coverage(con, output, descriptor)


@pytest.mark.parametrize("replace_old", [False, True])
def test_additional_and_same_count_valid_but_foreign_snapshot_parts_fail_full_keyset_coverage(tmp_path, replace_old):
    key, payload = packet()
    with source(tmp_path, [(key, payload)]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        part = snapshots._read_descriptor(output, key)
        header = deepcopy(payload)
        del header["observation_refs"]
        if replace_old:
            output.execute("DELETE FROM v2_snapshot_parts WHERE key=?", (key,))
        snapshots.put_snapshot_parts(output, key="f" * 64, header_bytes=canonical_bytes(header),
            observation_refs=part.observation_refs, expected_raw_payload_sha256=part.raw_payload_sha256,
            expected_payload_bytes=part.payload_bytes, expected_payload_digest=_payload_digest("f" * 64, payload),
            expected_observation_count=part.observation_refs.reference_count)
        snapshots.validate_all(output)  # Intrinsic validity is insufficient.
        with pytest.raises(StorageIntegrityError):
            owner.validate_source_coverage(con, output, descriptor)


def test_same_count_other_source_cannot_reuse_a_complete_coverage_descriptor(tmp_path):
    key, payload = packet(count=4)
    changed = deepcopy(payload)
    changed["observation_refs"][-1] = "f" * 64
    with source(tmp_path, [(key, payload)]) as (_one, first), source(tmp_path, [(key, changed)]) as (_two, second), target(tmp_path) as output:
        descriptor = adapt(first, output)
        with pytest.raises(StorageIntegrityError, match="complete coverage inventory"):
            owner.validate_source_coverage(second, output, descriptor)


@pytest.mark.parametrize("change", ["commit", "rollback", "script", "main-ddl", "temp-ddl"])
def test_output_transaction_and_schema_cannot_change_during_source_reading(tmp_path, monkeypatch, change):
    with source(tmp_path, [packet()]) as (_path, con), target(tmp_path) as output:
        original, fired = owner._Payload.take, False
        def changed(self, size):
            nonlocal fired
            if not fired:
                fired = True
                if change in {"commit", "rollback"}:
                    getattr(output, change)()
                    output.execute("BEGIN")
                elif change == "script":
                    output.executescript("BEGIN;")
                elif change == "main-ddl":
                    output.execute("CREATE TABLE foreign_owner_table(x INTEGER)")
                else:
                    output.execute("CREATE TEMP TABLE foreign_owner_table(x INTEGER)")
            return original(self, size)
        monkeypatch.setattr(owner._Payload, "take", changed)
        with pytest.raises(StorageIntegrityError):
            adapt(con, output)
        assert fired
        # An interleaved caller commit cannot be undone by this adapter. It must
        # never return a coverage descriptor or a partial-success assertion.
        assert output.execute("SELECT count(*) FROM v2_snapshot_parts").fetchone() == (0,)


@pytest.mark.parametrize("function", ["typeof", "octet_length", "count"])
def test_output_shape_checks_cannot_be_forged_with_overridden_sql_functions(tmp_path, function):
    with source(tmp_path, [packet()]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        output.create_function(function, -1, lambda *_args: 0)
        with pytest.raises(StorageIntegrityError, match="core SQL functions"):
            owner.validate_source_coverage(con, output, descriptor)


def test_source_row_scan_streams_every_real_payload_including_raw_only_rows(tmp_path, monkeypatch):
    key, payload = packet()
    rows = [(key, payload), ("e" * 64, {"kind": "unknown", "unchanged": [1, "a"]})]
    original, opened = owner._Payload.__init__, []
    def track(self, blob, guard, row_hash, size, limits, key):
        assert isinstance(blob, sqlite3.Blob)
        assert len(blob) == size
        opened.append(size)
        return original(self, blob, guard, row_hash, size, limits, key)
    monkeypatch.setattr(owner._Payload, "__init__", track)
    with source(tmp_path, rows, raw_rows=[("bad-key", b"", "bad-digest")]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        assert descriptor.snapshot_count == 3 and descriptor.unadapted_count == 2
        sizes = sorted([len(canonical_bytes(value)) for _key, value in rows] + [0])
        assert sorted(opened) == sorted(sizes * 2)  # Build and complete final rescan.


@pytest.mark.parametrize("field,value", [("format_version", 1), ("snapshot_count", True),
    ("adapted_count", 0), ("snapshot_table_present", 1), ("coverage_digest", "f" * 64),
    ("descriptor_digest", "f" * 64)])
def test_forged_incomplete_or_mixed_version_descriptor_is_rejected(tmp_path, field, value):
    with source(tmp_path, [packet()]) as (_path, con), target(tmp_path) as output:
        descriptor = adapt(con, output)
        with pytest.raises(StorageIntegrityError):
            owner.validate_source_coverage(con, output, replace(descriptor, **{field: value}))


def test_entire_known_ref_array_crosses_chunks_without_full_payload_or_list_allocation(tmp_path, record_property):
    # tracemalloc measures Python allocator growth, NOT native RSS, CPU, or C6.
    limits = replace(DEFAULT_LIMITS, block_bytes=64 * 1024)
    peaks = []
    for count in (1000, 12000):
        key, payload = packet(count=count)
        with source(tmp_path, [(key, payload)]) as (_path, con), target(tmp_path) as output:
            expected = inventory_raw(con, limits=limits)
            del payload
            gc.collect()
            tracemalloc.start()
            try:
                descriptor = owner.adapt_source_snapshots(con, output, expected, limits=limits)
                _current, peak = tracemalloc.get_traced_memory()
                peaks.append(peak)
            finally:
                tracemalloc.stop()
            assert descriptor.adapted_count == 1
            part = snapshots._read_descriptor(output, key)
            assert part.observation_refs.reference_count == count
            assert part.observation_refs.block_count == (count + 2047) // 2048
    record_property("python_allocator_peak_small_bytes", peaks[0])
    record_property("python_allocator_peak_large_bytes", peaks[1])
    assert max(peaks) < 3 * 1024**2
    assert peaks[1] - peaks[0] < 768 * 1024
