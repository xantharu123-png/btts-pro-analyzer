"""Separate bounded C2 chunk contract; no scalar API change or native proof."""
from contextlib import contextmanager
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
import tracemalloc

import pytest

from context_runtime_transaction import TrackedConnection
from context_storage_v2 import refs
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.ref_chunks import iter_canonical_ref_chunks
from model_artifacts import canonical_bytes


@contextmanager
def reader(path, *, count=19, encoding="UTF-8", limits=DEFAULT_LIMITS):
    con = sqlite3.connect(path, factory=TrackedConnection)
    con.execute(f"PRAGMA encoding='{encoding}'")
    con.execute("PRAGMA page_size=4096")
    con.execute("PRAGMA cache_size=-4096")
    con.execute("PRAGMA mmap_size=0")
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA temp_store=FILE")
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096}")
    con.execute("BEGIN")
    refs.create_schema(con)
    expected = [f"{value:064x}" for value in range(count)]
    descriptor = refs.put_refset(con, reversed(expected), limits=limits)
    con.commit()
    con.execute("BEGIN")
    try:
        yield con, descriptor, expected
    finally:
        con.close()


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
@pytest.mark.parametrize("count,chunk_bytes", [(0, 1), (1, 2), (11, 7), (37, 64)])
def test_complete_canonical_bytes_match_old_scalar_in_tiny_multiblock_cases(
        tmp_path, encoding, count, chunk_bytes):
    limits = replace(DEFAULT_LIMITS, block_bytes=96)
    with reader(tmp_path / "refs.sqlite", count=count, encoding=encoding, limits=limits) as (con, descriptor, expected):
        old = canonical_bytes(list(refs.iter_refset(con, descriptor, limits=limits)))
        stamp = con.total_changes, con.transaction_generation
        for _repeat in range(2):
            pieces = list(iter_canonical_ref_chunks(con, descriptor, limits=limits, chunk_bytes=chunk_bytes))
            assert all(type(piece) is bytes and 0 < len(piece) <= chunk_bytes for piece in pieces)
            actual = b"".join(pieces)
            assert actual == old == canonical_bytes(expected)
            assert len(actual) == descriptor.canonical_bytes
            assert hashlib.sha256(actual).hexdigest() == descriptor.canonical_digest
        assert (con.total_changes, con.transaction_generation) == stamp
        assert con.in_transaction
        assert descriptor.block_count == (count + 2) // 3


def test_new_reader_does_not_call_or_weaken_scalar_iterator(tmp_path, monkeypatch):
    with reader(tmp_path / "refs.sqlite") as (con, descriptor, expected):
        con.execute("PRAGMA query_only=ON")
        monkeypatch.setattr(refs, "iter_refset", lambda *_args, **_kwargs: pytest.fail("scalar path must remain separate"))
        assert b"".join(iter_canonical_ref_chunks(con, descriptor)) == canonical_bytes(expected)


@pytest.mark.parametrize("chunk_bytes", [0, -1, True, 1.5, None, "64", DEFAULT_LIMITS.block_bytes + 1])
def test_invalid_chunk_budget_never_yields(tmp_path, chunk_bytes):
    with reader(tmp_path / "refs.sqlite") as (con, descriptor, _expected):
        with pytest.raises(StorageLimitError):
            next(iter_canonical_ref_chunks(con, descriptor, chunk_bytes=chunk_bytes))


@pytest.mark.parametrize("damage", ["missing", "reorder", "extra", "version", "same_count_other_members"])
def test_complete_set_validation_precedes_even_first_single_byte(tmp_path, damage):
    limits = replace(DEFAULT_LIMITS, block_bytes=96)
    with reader(tmp_path / "refs.sqlite", count=9, limits=limits) as (con, descriptor, _expected):
        rows = list(con.execute("SELECT block_index,block_digest FROM v2_ref_members ORDER BY block_index"))
        if damage == "missing":
            con.execute("DELETE FROM v2_ref_blocks WHERE digest=?", (rows[-1][1],))
        elif damage == "reorder":
            con.execute("UPDATE v2_ref_members SET block_digest=CASE block_index WHEN 0 THEN ? WHEN 1 THEN ? ELSE block_digest END",
                        (rows[1][1], rows[0][1]))
        elif damage == "extra":
            con.execute("INSERT INTO v2_ref_members VALUES(?,?,?,?,?)", (descriptor.set_digest, 3, rows[0][1], 3, 96))
        elif damage == "version":
            con.execute("UPDATE v2_ref_blocks SET format_version=3 WHERE digest=?", (rows[-1][1],))
        else:
            other = refs.put_refset(con, (f"{value:064x}" for value in range(100, 109)), limits=limits)
            other_block = con.execute("SELECT block_digest FROM v2_ref_members WHERE set_digest=? AND block_index=2", (other.set_digest,)).fetchone()[0]
            con.execute("UPDATE v2_ref_members SET block_digest=? WHERE set_digest=? AND block_index=2", (other_block, descriptor.set_digest))
        with pytest.raises(StorageIntegrityError):
            next(iter_canonical_ref_chunks(con, descriptor, limits=limits, chunk_bytes=1))


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_nul_suffix_metadata_is_rejected_before_python_materialization(tmp_path, encoding):
    with reader(tmp_path / "refs.sqlite", encoding=encoding) as (con, descriptor, _expected):
        con.execute("UPDATE v2_ref_sets SET canonical_digest=?", ("a" * 64 + "\0" + "x" * (2 * 1024**2),))
        tracemalloc.start()
        try:
            with pytest.raises(StorageIntegrityError):
                next(iter_canonical_ref_chunks(con, descriptor, chunk_bytes=1))
            assert tracemalloc.get_traced_memory()[1] < 512 * 1024
        finally:
            tracemalloc.stop()


def change_reader(con, descriptor, limits, change, monkeypatch):
    if change in {"commit", "rollback"}:
        getattr(con, change)()
        con.execute("BEGIN")
    elif change == "script":
        con.executescript("BEGIN;")
    elif change == "close":
        con.close()
    elif change == "write":
        con.execute("UPDATE v2_ref_sets SET reference_count=reference_count")
    elif change == "main_ddl":
        con.execute("CREATE TABLE changed(x)")
    elif change == "temp_ddl":
        con.execute("CREATE TEMP TABLE changed(x)")
    elif change == "attached":
        con.execute("ATTACH DATABASE ':memory:' AS changed")
    elif change == "cache":
        con.execute("PRAGMA cache_size=-2048")
    elif change == "mmap":
        con.execute("PRAGMA mmap_size=4096")
    elif change == "max_pages":
        con.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096 - 1}")
    elif change == "row_factory":
        con.row_factory = sqlite3.Row
    elif change == "text_factory":
        con.text_factory = bytes
    elif change == "limits":
        object.__setattr__(limits, "block_bytes", limits.block_bytes // 2)
    elif change == "widened_limits":
        object.__setattr__(limits, "workspace_bytes", DEFAULT_LIMITS.workspace_bytes + 1)
    elif change == "descriptor":
        object.__setattr__(descriptor, "canonical_digest", "0" * 64)
    elif change == "free_reserve":
        usage = shutil.disk_usage(Path(con.execute("PRAGMA database_list").fetchone()[2]).parent)
        monkeypatch.setattr(refs.shutil, "disk_usage", lambda _path: type(usage)(usage.total, usage.used, limits.min_free_bytes - 1))
    else:
        raise AssertionError(change)


@pytest.mark.parametrize("when", ["middle", "terminal"])
@pytest.mark.parametrize("change", [
    "commit", "rollback", "script", "close", "write", "main_ddl", "temp_ddl",
    "attached", "cache", "mmap", "max_pages", "row_factory", "text_factory",
    "limits", "widened_limits", "descriptor", "free_reserve",
])
def test_real_lifetime_and_resource_changes_fail_before_next_public_chunk_or_terminal(
        tmp_path, monkeypatch, when, change):
    limits = replace(DEFAULT_LIMITS)
    with reader(tmp_path / "refs.sqlite", limits=limits) as (con, descriptor, expected):
        stream = iter_canonical_ref_chunks(con, descriptor, limits=limits, chunk_bytes=64)
        if when == "middle":
            assert len(next(stream)) == 64
        else:
            chunk_count = (descriptor.canonical_bytes + 63) // 64
            assert b"".join(next(stream) for _ in range(chunk_count)) == canonical_bytes(expected)
        change_reader(con, descriptor, limits, change, monkeypatch)
        with pytest.raises((StorageIntegrityError, StorageLimitError)):
            next(stream)
        with pytest.raises(StopIteration):
            next(stream)


def test_empty_set_terminal_is_still_lifetime_bound(tmp_path):
    with reader(tmp_path / "refs.sqlite", count=0) as (con, descriptor, _expected):
        stream = iter_canonical_ref_chunks(con, descriptor, chunk_bytes=1)
        assert next(stream) == b"[" and next(stream) == b"]"
        con.commit()
        with pytest.raises(StorageIntegrityError):
            next(stream)


def test_mutation_during_real_full_block_verification_yields_no_prefix(tmp_path, monkeypatch):
    with reader(tmp_path / "refs.sqlite") as (con, descriptor, _expected):
        real_read_block = refs._read_block
        fired = []
        def read_block(*args):
            value = real_read_block(*args)
            if not fired:
                fired.append(True)
                con.execute("UPDATE v2_ref_sets SET reference_count=reference_count")
            return value
        monkeypatch.setattr(refs, "_read_block", read_block)
        with pytest.raises(StorageIntegrityError):
            next(iter_canonical_ref_chunks(con, descriptor, chunk_bytes=1))
        assert fired


@pytest.mark.parametrize("change", ["commit", "rollback", "script", "close"])
def test_lifecycle_end_during_whole_validation_is_a_typed_failure_before_output(tmp_path, monkeypatch, change):
    with reader(tmp_path / "refs.sqlite") as (con, descriptor, _expected):
        real_read_block = refs._read_block
        fired = []
        def read_block(*args):
            content = real_read_block(*args)
            if not fired:
                fired.append(True)
                change_reader(con, descriptor, DEFAULT_LIMITS, change, monkeypatch)
            return content
        monkeypatch.setattr(refs, "_read_block", read_block)
        with pytest.raises(StorageIntegrityError):
            next(iter_canonical_ref_chunks(con, descriptor, chunk_bytes=1))
        assert fired


def test_already_closed_connection_is_a_typed_admission_failure(tmp_path):
    with reader(tmp_path / "refs.sqlite") as (con, descriptor, _expected):
        con.close()
        with pytest.raises(StorageIntegrityError):
            next(iter_canonical_ref_chunks(con, descriptor))


def test_mutation_inside_emitter_block_read_cannot_escape_in_next_chunk(tmp_path, monkeypatch):
    with reader(tmp_path / "refs.sqlite") as (con, descriptor, _expected):
        real_read_block = refs._read_block
        calls = []
        def read_block(*args):
            content = real_read_block(*args)
            calls.append(True)
            if len(calls) == 2:  # Once for complete validation, then emission.
                con.execute("UPDATE v2_ref_sets SET reference_count=reference_count")
            return content
        monkeypatch.setattr(refs, "_read_block", read_block)
        stream = iter_canonical_ref_chunks(con, descriptor, chunk_bytes=1)
        assert next(stream) == b"["
        with pytest.raises(StorageIntegrityError):
            next(stream)
        assert len(calls) == 2


def test_full_stream_uses_bounded_python_buffers_separately_from_timing(tmp_path):
    limits = replace(DEFAULT_LIMITS, block_bytes=4096)
    with reader(tmp_path / "refs.sqlite", count=12000, limits=limits) as (con, descriptor, expected):
        expected_bytes = canonical_bytes(expected)
        expected_hash = hashlib.sha256(expected_bytes).hexdigest()
        del expected_bytes
        tracemalloc.start()
        try:
            digest, total, count = hashlib.sha256(), 0, 0
            for chunk in iter_canonical_ref_chunks(con, descriptor, limits=limits, chunk_bytes=1024):
                assert 0 < len(chunk) <= 1024
                digest.update(chunk)
                total += len(chunk)
                count += 1
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert total == descriptor.canonical_bytes and digest.hexdigest() == expected_hash
        assert count > 100 and descriptor.block_count > 10
        assert peak < 512 * 1024


def run_performance(workspace):
    """Opt-in finite local measurement, never collected as a pytest benchmark."""
    root = Path(__file__).resolve().parents[1]
    workspace = Path(workspace).resolve()
    assert workspace.is_relative_to((root / ".pytest_tmp").resolve())
    assert not tracemalloc.is_tracing()
    workspace.mkdir(exist_ok=False)
    names = ("context_storage_v2/refs.py", "context_storage_v2/ref_chunks.py", "context_storage_v2/snapshots.py")
    before = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    result = {"kind": "task21-synthetic-local-ref-chunks", "tracemalloc": False,
              "native_acceptance": False, "parallel_root_suite": True,
              "python_sqlite_version": sqlite3.sqlite_version, "limits": asdict(DEFAULT_LIMITS),
              "chunk_bytes": 65536, "timing_rounds_per_case": 5,
              "source_hashes_before": before, "cases": []}
    def timed(function):
        assert not tracemalloc.is_tracing()
        wall, cpu = time.perf_counter(), time.process_time()
        value = function()
        return value, {"cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - wall}
    for count in (5000, 50000):
        path = workspace / f"refs-{count}.sqlite"
        with reader(path, count=count) as (con, descriptor, expected):
            con.execute("PRAGMA query_only=ON")
            raw = canonical_bytes(expected)
            old, scalar_time = timed(lambda: list(refs.iter_refset(con, descriptor)))
            actual, chunk_time = timed(lambda: list(iter_canonical_ref_chunks(con, descriptor)))
            assert canonical_bytes(old) == b"".join(actual) == raw
            assert hashlib.sha256(raw).hexdigest() == descriptor.canonical_digest
            scalar_times, chunk_times = [scalar_time], [chunk_time]
            for round_index in range(1, 5):
                # Alternate order, but retain the same transaction/settings and
                # run complete validation plus complete emission on every call.
                if round_index % 2:
                    actual, chunk_time = timed(lambda: list(iter_canonical_ref_chunks(con, descriptor)))
                    old, scalar_time = timed(lambda: list(refs.iter_refset(con, descriptor)))
                else:
                    old, scalar_time = timed(lambda: list(refs.iter_refset(con, descriptor)))
                    actual, chunk_time = timed(lambda: list(iter_canonical_ref_chunks(con, descriptor)))
                assert canonical_bytes(old) == b"".join(actual) == raw
                scalar_times.append(scalar_time)
                chunk_times.append(chunk_time)
            observed_sql = {}
            for name, function in (
                ("scalar", lambda: canonical_bytes(list(refs.iter_refset(con, descriptor)))),
                ("chunks", lambda: b"".join(iter_canonical_ref_chunks(con, descriptor))),
            ):
                counts = Counter()
                def trace(statement):
                    normalized = " ".join(statement.strip().split())
                    counts[normalized if normalized.startswith("PRAGMA ") else normalized.split(" ", 1)[0]] += 1
                con.set_trace_callback(trace)
                try:
                    assert function() == raw
                finally:
                    con.set_trace_callback(None)
                observed_sql[name] = {"total": sum(counts.values()), "counts": dict(counts)}
            with (workspace / f"source-{count}.json").open("xb") as stream:
                stream.write(raw)
            with (workspace / f"output-{count}.json").open("xb") as stream:
                stream.write(b"".join(actual))
            case = {"count": count, "scalar": scalar_time, "chunks": chunk_time,
                    "scalar_timing_rounds": scalar_times, "chunk_timing_rounds": chunk_times,
                    "scalar_timing_sum": {unit: sum(row[unit] for row in scalar_times) for unit in scalar_time},
                    "chunk_timing_sum": {unit: sum(row[unit] for row in chunk_times) for unit in chunk_time},
                    "untimed_trace_observer": observed_sql,
                    "settings": {name: con.execute(f"PRAGMA {name}").fetchone()[0] for name in (
                        "encoding", "page_size", "cache_size", "mmap_size", "max_page_count",
                        "temp_store", "journal_mode", "synchronous", "trusted_schema", "query_only")},
                    "source_and_output_bytes": len(raw), "sha256": descriptor.canonical_digest,
                    "output_chunks": len(actual), "reference_blocks": descriptor.block_count,
                    "database_bytes": path.stat().st_size}
            result["cases"].append(case)
            print(json.dumps(case, sort_keys=True), flush=True)
    result["source_hashes_after"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    assert result["source_hashes_after"] == before
    with (workspace / "result.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--perf-workspace", required=True)
    run_performance(parser.parse_args().perf_workspace)
