"""Typed whole-corpus copy identity is not source, model or HMAC approval."""
from contextlib import contextmanager
from dataclasses import replace
import sqlite3

import pytest

from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.inventory import compare_raw, inventory_raw
from context_storage_v2 import inventory as owner


@contextmanager
def reader(*, encoding="UTF-8", payload=b'{"unchanged": true}', all_tables=True):
    con = sqlite3.connect(":memory:", factory=TrackedConnection)
    con.execute(f"PRAGMA encoding='{encoding}'")
    for name, sql in _SCHEMA.items():
        if all_tables or name in {"artifacts", "manifests", "active_manifest"}:
            con.execute(sql)
    con.execute("INSERT INTO artifacts VALUES(?,?,?,?)",
                ("a" * 64, "synthetic-Hä\x00after", payload, "2026-09-12T00:00:00+00:00"))
    con.execute("INSERT INTO manifests VALUES(?,?,?,?)",
                ("b" * 64, None, b"{}", "2026-09-12T00:00:00+00:00"))
    con.execute("INSERT INTO active_manifest VALUES(1,?)", ("b" * 64,))
    con.commit()
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA query_only=ON")
    con.execute("BEGIN")
    try:
        yield con
    finally:
        con.close()


def mutate(con, sql, params=()):
    con.rollback()
    con.execute("PRAGMA query_only=OFF")
    con.execute(sql, params)
    con.commit()
    con.execute("PRAGMA query_only=ON")
    con.execute("BEGIN")


def test_closed_schema_empty_optional_tables_are_inventoried():
    with reader() as con:
        before = con.total_changes, con.transaction_generation
        one, two = inventory_raw(con), inventory_raw(con)
        assert one == two
        assert len(one.tables) == 7
        assert sum(t.row_count for t in one.tables) == 3
        assert (con.total_changes, con.transaction_generation) == before
        assert con.in_transaction


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_incremental_and_inline_paths_are_byte_identical(encoding):
    with reader(encoding=encoding, payload=b"old uncanonical bytes\0" * 100) as con:
        whole = inventory_raw(con)
        blocks = inventory_raw(con, limits=replace(DEFAULT_LIMITS, block_bytes=17))
        assert blocks == whole


def test_backup_copy_preserves_raw_noncanonical_json_and_embedded_nul():
    with reader() as source, reader() as target:
        # The test owns this isolated target; the production inventory API never
        # creates, copies, commits or edits a source/target database.
        target.rollback()
        target.execute("PRAGMA query_only=OFF")
        source.backup(target)
        target.execute("PRAGMA query_only=ON")
        target.execute("BEGIN")
        assert compare_raw(source, target) == inventory_raw(source)


@pytest.mark.parametrize("sql,params", [
    ("UPDATE artifacts SET payload=?", (b'{"unchanged":true}',)),
    ("UPDATE artifacts SET digest=?", ("c" * 64,)),
    ("UPDATE artifacts SET kind=?", ("synthetic-Hä\x00changed",)),
    ("INSERT INTO context_contents VALUES(?,?)", ("d" * 64, b'{"future":true}')),
    ("DELETE FROM active_manifest", ()),
])
def test_same_counts_changed_bytes_extra_unreferenced_or_deleted_rows_fail(sql, params):
    with reader() as source, reader() as target:
        mutate(target, sql, params)
        with pytest.raises(StorageIntegrityError, match="differs"):
            compare_raw(source, target)


@pytest.mark.parametrize("column,value", [("payload", "{}"), ("kind", b"same-text"),
                                          ("digest", None), ("created_at", b"date")])
def test_wrong_sql_storage_type_is_not_coerced(column, value):
    with reader() as con:
        mutate(con, f'UPDATE artifacts SET "{column}"=?', (value,))
        with pytest.raises(StorageIntegrityError, match="coercion"):
            inventory_raw(con)


def test_unknown_schema_is_not_silently_ignored():
    with reader() as con:
        mutate(con, "CREATE TABLE unexpected(x TEXT)")
        with pytest.raises(ValueError, match="schema"):
            inventory_raw(con)


def test_absent_optional_schema_is_distinct_from_present_empty_tables():
    with reader() as complete, reader(all_tables=False) as core:
        with pytest.raises(StorageIntegrityError, match="differs"):
            compare_raw(complete, core)


@pytest.mark.parametrize("factory", [bytes, lambda value: value.decode()])
def test_nonstandard_text_factory_is_rejected(factory):
    with reader() as con:
        con.text_factory = factory
        with pytest.raises(StorageIntegrityError, match="held reader"):
            inventory_raw(con)


def test_readonly_and_live_transaction_are_mandatory():
    with reader() as con:
        con.execute("PRAGMA query_only=OFF")
        with pytest.raises(StorageIntegrityError, match="read-only"):
            inventory_raw(con)
        con.execute("PRAGMA query_only=ON")
        con.commit()
        with pytest.raises(StorageIntegrityError, match="held reader"):
            inventory_raw(con)


def test_mutation_during_complete_scan_never_returns_partial_identity():
    with reader() as con:
        fired = False
        def progress():
            nonlocal fired
            if not fired:
                fired = True
                con.execute("PRAGMA query_only=OFF")
                con.execute("UPDATE artifacts SET kind='modified'")
                con.execute("PRAGMA query_only=ON")
            return 0
        # Do not use the callback to forge proof state. It only models an actual
        # interleaved connection write that the inventory must detect.
        con.set_progress_handler(progress, 200)
        with pytest.raises(StorageIntegrityError):
            inventory_raw(con)
        assert fired


def test_input_limit_counts_complete_allocated_image():
    with reader() as con:
        with pytest.raises(StorageLimitError, match="image"):
            inventory_raw(con, limits=replace(DEFAULT_LIMITS, input_bytes=4096))


@pytest.mark.parametrize("function", ["octet_length", "typeof", "count", "sum", "coalesce"])
def test_core_sql_function_override_cannot_forge_metadata(function):
    with reader() as con:
        con.create_function(function, -1, lambda *args: 0)
        with pytest.raises(StorageIntegrityError, match="core SQL functions"):
            inventory_raw(con)


@pytest.mark.parametrize("transition", ["commit", "rollback", "script"])
def test_end_and_restart_of_transaction_during_scan_is_not_revived(monkeypatch, transition):
    with reader() as con:
        original = owner._raw_rows
        def ended(*args):
            if transition == "script":
                con.executescript("BEGIN;")
            else:
                getattr(con, transition)()
                con.execute("BEGIN")
            return original(*args)
        monkeypatch.setattr(owner, "_raw_rows", ended)
        with pytest.raises(StorageIntegrityError, match="reader changed"):
            inventory_raw(con)


def test_compare_keeps_source_bound_while_copy_is_scanned(monkeypatch):
    with reader() as source, reader() as copied:
        original = owner.inventory_raw
        def scan(con, **kwargs):
            if con is copied:
                source.commit()
                source.execute("BEGIN")
            return original(con, **kwargs)
        monkeypatch.setattr(owner, "inventory_raw", scan)
        with pytest.raises(StorageIntegrityError, match="reader changed"):
            compare_raw(source, copied)


def test_physical_rowid_and_insertion_order_are_not_logical_keys():
    with reader() as source, reader() as copied:
        mutate(source, "INSERT INTO context_contents VALUES(?,?)", ("d" * 64, b"first"))
        mutate(source, "INSERT INTO context_contents VALUES(?,?)", ("c" * 64, b"second"))
        mutate(copied, "INSERT INTO context_contents VALUES(?,?)", ("c" * 64, b"second"))
        mutate(copied, "INSERT INTO context_contents VALUES(?,?)", ("d" * 64, b"first"))
        assert compare_raw(source, copied) == inventory_raw(source)


def test_null_predecessor_is_not_empty_text():
    with reader() as source, reader() as copied:
        mutate(copied, "UPDATE manifests SET predecessor='' ")
        with pytest.raises(StorageIntegrityError, match="differs"):
            compare_raw(source, copied)


def test_noncontract_limit_object_is_rejected():
    with reader() as con:
        with pytest.raises(StorageLimitError, match="exact resource envelope"):
            inventory_raw(con, limits=object())


def test_instance_callback_cannot_override_the_fixed_limit_validator():
    limits = replace(DEFAULT_LIMITS)
    object.__setattr__(limits, "block_bytes", 1024**3)
    object.__setattr__(limits, "__post_init__", lambda: None)
    with reader() as con:
        with pytest.raises(StorageLimitError, match="widened"):
            inventory_raw(con, limits=limits)


def test_many_broken_foreign_keys_fail_before_legacy_collects_all_errors(monkeypatch):
    with reader() as con:
        con.rollback()
        con.execute("PRAGMA query_only=OFF")
        con.execute("PRAGMA foreign_keys=OFF")
        con.executemany("INSERT INTO context_observations VALUES(?,?,?,?,?,?,?,?)",
                        ((f"{i:064x}", "e" * 64, "espn:tennis:future", "2099-01-01",
                          "future", "espn", "unknown", "workload") for i in range(10000)))
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        monkeypatch.setattr(owner, "_verify_schema", lambda *_: pytest.fail(
            "the legacy all-errors collector must not see the corrupt input"))
        with pytest.raises(StorageIntegrityError, match="foreign-key"):
            inventory_raw(con)


@pytest.mark.parametrize("field,value", [
    ("input_bytes", True), ("block_bytes", 0), ("tour_history_bytes", 1024**3 + 1),
    ("workspace_bytes", 8 * 1024**3 + 1), ("min_free_bytes", 4 * 1024**3 - 1),
    ("blocks_per_set", 4097), ("input_bytes", 4.0),
])
def test_resource_envelope_cannot_be_widened_or_type_coerced(field, value):
    with pytest.raises(StorageLimitError):
        replace(DEFAULT_LIMITS, **{field: value})
