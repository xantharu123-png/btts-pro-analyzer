"""Delegating allocation probes and exact checking-boundary regressions."""
from contextlib import closing
from copy import deepcopy
import gc
import inspect
import sqlite3
import sys
import weakref

import pytest

import context_runtime_history_cache as hc
from context_runtime_inventory import VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection, TrackedCursor
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_capacity import encoded_history_fixture
from test_context_runtime_receipt_witness import prepared


MAIN = "PRAGMA main.schema_version"
TEMP = "PRAGMA temp.schema_version"


def test_plain_guard_eliminates_recursive_generator_dispatch(encoded_history_fixture):
    _, _, _, rows, _ = prepared(encoded_history_fixture)
    generators = []
    previous = sys.getprofile()
    def observe(frame, event, arg):
        if (event == "call" and frame.f_globals is hc.__dict__
                and frame.f_code.co_flags & inspect.CO_GENERATOR):
            generators.append(frame.f_code.co_name)
    try:
        sys.setprofile(observe)
        accepted = [hc._plain_json(row) for row in rows]
    finally:
        sys.setprofile(previous)
    assert accepted == [True] * len(rows)
    assert generators == []  # Performance-contract RED, not a semantic bug.


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
def test_exact_schema_boundary_allocates_one_real_tracked_cursor(boundary):
    with closing(sqlite3.connect(":memory:", factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        cache = hc.EncodedHistoryCache(receipts)
        calls, statements = [], []
        conn.set_trace_callback(statements.append)
        previous = sys.getprofile()
        def observe(frame, event, arg):
            if event == "call" and frame.f_code is TrackedConnection.cursor.__code__:
                calls.append(1)
        try:
            sys.setprofile(observe)
            actual = receipts._inventory_stamp() if boundary == "inventory" else cache._schema_versions()
        finally:
            sys.setprofile(previous)
            conn.set_trace_callback(None)
        assert actual == ((conn.transaction_generation, conn.total_changes, 0, 0)
                          if boundary == "inventory" else (0, 0))
        assert statements == [MAIN, TEMP]
        assert calls == [1]  # Real SQLite work still executes twice.


class DictAlias(dict): pass
class ListAlias(list): pass
class StrAlias(str): pass
class IntAlias(int): pass
class FloatAlias(float): pass


@pytest.mark.parametrize("value,expected", [
    (None, True), (True, True), (False, True), (0, True), (1, True),
    (0.0, True), (-0.0, True), (float("nan"), True), (float("inf"), True),
    (float("-inf"), True), ("", True), ("unicode \u2603", True), ({}, True), ([], True),
    ({"a": [{"b": [None, False, 1, 1.5, "x"]}]}, True),
    ({1: "a"}, False), ({True: "a"}, False), ({None: "a"}, False),
    ({StrAlias("a"): 1}, False), (DictAlias(a=1), False), (ListAlias([1]), False),
    (StrAlias("x"), False), (IntAlias(1), False), (FloatAlias(1), False),
    ((), False), (b"x", False), ({"a": [DictAlias()]}, False), (object(), False),
])
def test_guard_exact_kind_matrix(value, expected):
    assert hc._plain_json(value) is expected


@pytest.mark.parametrize("container", [dict, list])
def test_guard_keeps_recursive_failure_and_first_false_order(container):
    cycle = container()
    if container is dict:
        cycle["self"] = cycle
    else:
        cycle.append(cycle)
    with pytest.raises(RecursionError): hc._plain_json(cycle)
    assert hc._plain_json([object(), cycle]) is False
    assert hc._plain_json({"first": object(), "later": cycle}) is False
    assert hc._plain_json({1: cycle}) is False  # Key rejected before its value.
    with pytest.raises(RecursionError): hc._plain_json([cycle, object()])


@pytest.mark.parametrize("value", [True, 1, 1.0, 0.0, -0.0])
def test_guard_does_not_replace_canonical_scalar_distinctions(value):
    assert hc._plain_json(value)
    expected = {bool: b"true", int: b"1"}.get(type(value))
    if expected is None:
        expected = b"1.0" if value == 1.0 else (b"-0.0" if str(value).startswith("-") else b"0.0")
    assert canonical_bytes(value) == expected


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
@pytest.mark.parametrize("failure", [None, "main", "temp", "fetch", "interrupt"])
def test_local_cursor_closed_after_success_or_failure(monkeypatch, boundary, failure):
    with closing(sqlite3.connect(":memory:", factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        cache = hc.EncodedHistoryCache(receipts)
        execute, fetch = TrackedCursor.execute, TrackedCursor.fetchone
        cursors, statements = [], []
        def tracked(cursor, sql, *args, **kwargs):
            if sql in (MAIN, TEMP):
                if not cursors: cursors.append(cursor)
                statements.append(sql)
            result = execute(cursor, sql, *args, **kwargs)
            if ((failure == "main" and sql == MAIN) or (failure == "temp" and sql == TEMP)):
                raise sqlite3.OperationalError("injected after actual pragma")
            if failure == "interrupt" and sql == TEMP:
                raise KeyboardInterrupt("between cookies")
            return result
        def fetched(cursor):
            result = fetch(cursor)
            if failure == "fetch": raise LookupError("after actual fetch")
            return result
        monkeypatch.setattr(TrackedCursor, "execute", tracked)
        monkeypatch.setattr(TrackedCursor, "fetchone", fetched)
        action = receipts._inventory_stamp if boundary == "inventory" else cache._schema_versions
        if failure:
            with pytest.raises((sqlite3.OperationalError, KeyboardInterrupt, LookupError)): action()
        else:
            assert action()[-2:] == (0, 0)
        assert statements == ([MAIN] if failure in {"main", "fetch"} else [MAIN, TEMP])
        assert len(cursors) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed cursor"):
            fetch(cursors[0])


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
@pytest.mark.parametrize("override", ["connection-subclass", "mapping-subclass", "cache-subclass",
    "class-execute", "instance-execute", "class-cursor", "instance-cursor", "row-factory"])
def test_custom_dispatch_keeps_original_two_cursor_route(monkeypatch, boundary, override):
    calls, cursors, factories = [], [], []
    execute, make_cursor = TrackedConnection.execute, TrackedConnection.cursor
    class ConnectionAlias(TrackedConnection):
        def execute(self, sql, *args, **kwargs):
            calls.append(sql)
            return super().execute(sql, *args, **kwargs)
    class ReceiptAlias(VerifiedReceiptMapping): pass
    class CacheAlias(hc.EncodedHistoryCache): pass
    with closing(sqlite3.connect(":memory:", factory=ConnectionAlias
            if override == "connection-subclass" else TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = (ReceiptAlias if override == "mapping-subclass" else VerifiedReceiptMapping)(conn)
        cache = (CacheAlias if override == "cache-subclass" else hc.EncodedHistoryCache)(receipts)
        if override == "cache-subclass" and boundary == "inventory":
            # The inventory remains exact; exercise the cache-owned route only.
            boundary = "cache"
        def dispatched(connection, sql, *args, **kwargs):
            calls.append(sql)
            return execute(connection, sql, *args, **kwargs)
        def constructed(connection, *args, **kwargs):
            result = make_cursor(connection, *args, **kwargs)
            cursors.append(result)
            return result
        def factory(cursor, row):
            factories.append(cursor)
            return row
        if override == "class-execute": monkeypatch.setattr(TrackedConnection, "execute", dispatched)
        elif override == "instance-execute": monkeypatch.setattr(conn, "execute", lambda *a, **kw: dispatched(conn, *a, **kw))
        elif override == "class-cursor": monkeypatch.setattr(TrackedConnection, "cursor", constructed)
        elif override == "instance-cursor": monkeypatch.setattr(conn, "cursor", lambda *a, **kw: constructed(conn, *a, **kw))
        elif override == "row-factory": conn.row_factory = factory
        calls.clear()
        previous, allocations = sys.getprofile(), []
        def observe(frame, event, arg):
            if event == "call" and frame.f_code is make_cursor.__code__: allocations.append(1)
        try:
            sys.setprofile(observe)
            result = receipts._inventory_stamp() if boundary == "inventory" else cache._schema_versions()
        finally:
            sys.setprofile(previous)
        assert result[-2:] == (0, 0)
        assert allocations == [1, 1]
        if "execute" in override or override == "connection-subclass": assert calls == [MAIN, TEMP]
        if "cursor" in override: assert len(cursors) == 2 and cursors[0] is not cursors[1]
        if override == "row-factory": assert len(factories) == 2 and factories[0] is not factories[1]


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
@pytest.mark.parametrize("override", ["class-execute", "instance-execute", "class-cursor",
    "instance-cursor", "row-factory", "recursive-boundary"])
def test_reentrant_changes_between_cookies_keep_original_dispatch(monkeypatch, boundary, override):
    with closing(sqlite3.connect(":memory:", factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        cache = hc.EncodedHistoryCache(receipts)
        action = receipts._inventory_stamp if boundary == "inventory" else cache._schema_versions
        execute, make_cursor, fetch = TrackedConnection.execute, TrackedConnection.cursor, TrackedCursor.fetchone
        calls, first, recursed = [], [], []
        def dispatched(connection, sql, *args, **kwargs):
            calls.append(sql)
            return execute(connection, sql, *args, **kwargs)
        def constructed(connection, *args, **kwargs):
            cursor = make_cursor(connection, *args, **kwargs)
            calls.append(cursor)
            return cursor
        def factory(cursor, row):
            calls.append(cursor)
            return row
        def fetched(cursor):
            result = fetch(cursor)
            if not first:
                first.append(cursor)
                if override == "class-execute": monkeypatch.setattr(TrackedConnection, "execute", dispatched)
                elif override == "instance-execute": monkeypatch.setattr(conn, "execute", lambda *a, **kw: dispatched(conn, *a, **kw))
                elif override == "class-cursor": monkeypatch.setattr(TrackedConnection, "cursor", constructed)
                elif override == "instance-cursor": monkeypatch.setattr(conn, "cursor", lambda *a, **kw: constructed(conn, *a, **kw))
                elif override == "row-factory": conn.row_factory = factory
                else: recursed.append(action())
            return result
        monkeypatch.setattr(TrackedCursor, "fetchone", fetched)
        assert action()[-2:] == (0, 0)
        with pytest.raises(sqlite3.ProgrammingError, match="closed cursor"): fetch(first[0])
        if "execute" in override: assert calls == [TEMP]
        elif override == "recursive-boundary": assert len(recursed) == 1 and recursed[0][-2:] == (0, 0)
        else: assert len(calls) == 1 and calls[0] is not first[0]


@pytest.mark.parametrize("schema", ["main", "temp"])
@pytest.mark.parametrize("mutation", ["write", "main-ddl", "temp-shadow", "commit", "rollback", "close"])
@pytest.mark.parametrize("boundary", ["before-row", "after-row"])
def test_real_cursor_cookie_races_revoke_witness_permanently(encoded_history_fixture, monkeypatch, schema, mutation, boundary):
    import context_sources.tennis_status as status
    conn, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    execute, events = TrackedCursor.execute, []
    def changed(cursor, sql, *args, **kwargs):
        result = execute(cursor, sql, *args, **kwargs)
        if cursor.connection is conn and sql == "PRAGMA " + schema + ".schema_version":
            events.append(1)
            if len(events) == (1 if boundary == "before-row" else 2):
                if mutation == "write": conn.execute("UPDATE context_observations SET source=source")
                elif mutation == "main-ddl": conn.execute("CREATE TABLE dispatch_ddl (id INTEGER)")
                elif mutation == "temp-shadow": conn.execute("CREATE TEMP TABLE context_observations (digest TEXT)")
                elif mutation == "close": conn.close()
                else:
                    getattr(conn, mutation)()
                    conn.execute("BEGIN")
        return result
    with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
        with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
            monkeypatch.setattr(TrackedCursor, "execute", changed)
            status.validate_selected_tennis_receipt(rows[0])
    assert events and cache._invalid and hc._selected_receipt_witness.get() is None
    assert cache.stats["entries"] == cache.stats["bytes"] == cache.stats["pending_bytes"] == 0
    with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
        cache._check_selected_proof(receipts)


@pytest.mark.parametrize("kind", ["nan", "inf", "cycle", "deep"])
def test_comparison_errors_defer_to_actual_cold_owner(encoded_history_fixture, monkeypatch, kind):
    import context_sources.tennis_status as status
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    candidate = deepcopy(rows[0])
    if kind in {"nan", "inf"}:
        candidate["payload"]["tournament_id"] = float(kind)
    elif kind == "cycle":
        candidate["payload"]["cycle"] = candidate
    else:
        tree = []
        for _ in range(sys.getrecursionlimit() + 5): tree = [tree]
        candidate["payload"]["deep"] = tree
    cold, calls = status._validate_selected_tennis_receipt_cold, []
    with pytest.raises((ValueError, RecursionError)) as expected: cold(candidate)
    def counted(row):
        calls.append(1)
        return cold(row)
    monkeypatch.setattr(status, "_validate_selected_tennis_receipt_cold", counted)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        with pytest.raises(type(expected.value)): status.validate_selected_tennis_receipt(candidate)
    assert calls == [1] and hc._selected_receipt_witness.get() is None


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
@pytest.mark.parametrize("error_type", [KeyboardInterrupt, MemoryError, sqlite3.OperationalError])
def test_cleanup_after_connection_close_preserves_primary_error(monkeypatch, boundary, error_type):
    conn = sqlite3.connect(":memory:", factory=TrackedConnection)
    conn.execute("BEGIN")
    receipts = VerifiedReceiptMapping(conn)
    cache = hc.EncodedHistoryCache(receipts)
    execute = TrackedCursor.execute
    primary = error_type("primary after actual pragma and connection close")
    def interrupted(cursor, sql, *args, **kwargs):
        result = execute(cursor, sql, *args, **kwargs)
        if sql == MAIN:
            conn.close()
            raise primary
        return result
    monkeypatch.setattr(TrackedCursor, "execute", interrupted)
    try:
        with pytest.raises(error_type) as failure:
            (receipts._inventory_stamp if boundary == "inventory" else cache._schema_versions)()
        assert failure.value is primary
        assert isinstance(failure.value.__cause__, sqlite3.ProgrammingError)
    finally:
        conn.close()


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
def test_normal_cleanup_failure_propagates_revokes_and_releases_cursor(encoded_history_fixture, monkeypatch, boundary):
    _, receipts, _, _, cache = prepared(encoded_history_fixture)
    close, refs = TrackedCursor.close, []
    def failed(cursor):
        refs.append(weakref.ref(cursor))
        close(cursor)
        raise sqlite3.OperationalError("normal cleanup failed")
    with monkeypatch.context() as local:
        local.setattr(TrackedCursor, "close", failed)
        action = receipts._check_validation if boundary == "inventory" else lambda: cache._check_selected_proof(receipts)
        with pytest.raises(sqlite3.OperationalError, match="normal cleanup failed"):
            action()
    gc.collect()
    assert refs and all(ref() is None for ref in refs)
    assert receipts._validation_failed and receipts._validation_stamp is None
    with pytest.raises(RuntimeArtifactTrustError): receipts.validate_all()
    if boundary == "cache":
        assert cache._invalid and not cache._seals
        assert cache.stats["entries"] == cache.stats["bytes"] == cache.stats["pending_bytes"] == 0


def test_double_failure_retains_no_cursor_after_exception_unwinds(monkeypatch):
    refs = []
    execute = TrackedCursor.execute
    def run():
        with closing(sqlite3.connect(":memory:", factory=TrackedConnection)) as conn:
            conn.execute("BEGIN")
            receipts = VerifiedReceiptMapping(conn)
            def interrupted(cursor, sql, *args, **kwargs):
                result = execute(cursor, sql, *args, **kwargs)
                if sql == MAIN:
                    refs.append(weakref.ref(cursor))
                    conn.close()
                    raise KeyboardInterrupt("primary")
                return result
            with monkeypatch.context() as local:
                local.setattr(TrackedCursor, "execute", interrupted)
                with pytest.raises(KeyboardInterrupt): receipts._inventory_stamp()
    run()
    gc.collect()
    assert len(refs) == 1 and refs[0]() is None


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
def test_both_actual_cookie_values_and_pragma_shadowing(boundary):
    with closing(sqlite3.connect(":memory:", factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        cache = hc.EncodedHistoryCache(receipts)
        conn.execute("CREATE TABLE first_table (id INTEGER)")
        conn.execute("CREATE TABLE second_table (id INTEGER)")
        conn.execute("CREATE TEMP TABLE pragma_schema_version (schema_version INTEGER)")
        statements = []
        conn.set_trace_callback(statements.append)
        try:
            result = receipts._inventory_stamp() if boundary == "inventory" else cache._schema_versions()
        finally:
            conn.set_trace_callback(None)
        assert result[-2:] == (2, 1)  # Independent actual main/temp DDL counts.
        assert statements == [MAIN, TEMP]


@pytest.mark.parametrize("boundary", ["inventory", "cache"])
def test_actual_sqlite_interrupt_on_second_cookie_closes_cursor(encoded_history_fixture, monkeypatch, boundary):
    conn, receipts, _, _, cache = prepared(encoded_history_fixture)
    execute, fetch, cursors = TrackedCursor.execute, TrackedCursor.fetchone, []
    def interrupted(cursor, sql, *args, **kwargs):
        result = execute(cursor, sql, *args, **kwargs)
        if sql == MAIN:
            cursors.append(cursor)
            conn.set_progress_handler(lambda: 1, 1)
        return result
    with monkeypatch.context() as local:
        local.setattr(TrackedCursor, "execute", interrupted)
        try:
            with pytest.raises(sqlite3.OperationalError, match="interrupted"):
                (receipts._check_validation if boundary == "inventory"
                 else lambda: cache._check_selected_proof(receipts))()
        finally:
            conn.set_progress_handler(None, 0)
    assert len(cursors) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed cursor"): fetch(cursors[0])
    assert receipts._validation_failed and receipts._validation_stamp is None
    if boundary == "cache": assert cache._invalid and not cache._entries
