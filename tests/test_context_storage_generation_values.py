"""Fixed-size guard snapshots retain every valid limit's lifetime binding."""
from dataclasses import fields, replace
import sqlite3

import pytest

from context_runtime_transaction import TrackedConnection
from context_storage_v2 import refs
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimits
from context_storage_v2.ref_chunks import iter_canonical_ref_chunks


@pytest.fixture
def connection(tmp_path):
    con = sqlite3.connect(tmp_path / "refs.sqlite", factory=TrackedConnection)
    con.execute("PRAGMA page_size=4096")
    con.execute("PRAGMA cache_size=-4096")
    con.execute("PRAGMA mmap_size=0")
    # Leave admission headroom for legitimate one-byte tighter limits.
    con.execute("PRAGMA max_page_count=524288")
    con.execute("BEGIN")
    refs.create_schema(con)
    try:
        yield con
    finally:
        con.close()


def test_generation_snapshot_uses_only_the_six_bound_values(connection):
    # Pair/reflection snapshots recreate resized tuple pools at each boundary.
    limits = replace(DEFAULT_LIMITS)
    generation = refs._generation(connection, limits)
    assert len(generation) == 12
    assert generation[10] is limits
    assert generation[11] == (
        4294967296, 1073741824, 16777216, 8589934592, 4294967296, 4096,
    )


def test_limit_declarations_remain_complete_for_the_fixed_value_snapshot():
    # Any added/reordered declaration requires explicit snapshot/test review.
    assert tuple(field.name for field in fields(StorageLimits)) == (
        "input_bytes", "tour_history_bytes", "block_bytes", "workspace_bytes",
        "min_free_bytes", "blocks_per_set",
    )


@pytest.mark.parametrize("kind", ["scalar", "chunks"])
@pytest.mark.parametrize("field,value", [
    ("input_bytes", 4294967295),
    ("tour_history_bytes", 1073741823),
    ("block_bytes", 16777215),
    ("workspace_bytes", 8589934591),
    ("min_free_bytes", 4294967297),
    ("blocks_per_set", 4095),
])
def test_each_valid_tightened_limit_rejects_before_the_next_value(connection, kind, field, value):
    # Omitting/caching any snapshot member would let its valid change escape.
    limits = replace(DEFAULT_LIMITS)
    descriptor = refs.put_refset(connection, ("0" * 64, "1" * 64), limits=limits)
    if kind == "scalar":
        stream = refs.iter_refset(connection, descriptor, limits=limits)
        assert next(stream) == "0" * 64
    else:
        stream = iter_canonical_ref_chunks(connection, descriptor, limits=limits, chunk_bytes=1)
        assert next(stream) == b"["
    object.__setattr__(limits, field, value)
    StorageLimits.__post_init__(limits)  # Still valid: rejection must bind lifetime.
    with pytest.raises(StorageIntegrityError, match="generation"):
        next(stream)
    with pytest.raises(StopIteration):
        next(stream)
