"""Bounded D4 transport/inventory, not Linux deployment or empirical proof."""
from contextlib import closing
from datetime import datetime, timedelta
import os
import sqlite3
import sys
from pathlib import Path

import pytest

import context_runtime as runtime
from context_runtime_transaction import TrackedConnection
from model_artifacts import ArtifactIntegrityError, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_backup import seeded, add_receipt, cli


def test_explicit_memory_mode_preserves_report_and_rejects_unknown_mode(tmp_path):
    path = tmp_path / "context.db"
    seeded(path)
    expected = runtime.verify_context_database(path)
    assert runtime.verify_context_database(path, input_mode="memory") == expected
    with pytest.raises(RuntimeArtifactTrustError, match="unsupported"):
        runtime.verify_context_database(path, input_mode="auto")


def test_large_input_does_not_implicitly_switch_to_file_mode(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    seeded(path)
    monkeypatch.setattr(runtime, "MAX_CONTEXT_IMAGE_BYTES", path.stat().st_size - 1)
    with pytest.raises(RuntimeArtifactTrustError, match="size"):
        runtime.verify_context_database(path)


def test_no_originals_do_not_require_original_replay_code(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    seeded(path)
    def unavailable():
        pytest.fail("unrelated original replay code was requested")
    monkeypatch.setattr("context_runtime_tennis._code_variants", unavailable)
    assert runtime.verify_context_database(path)["counts"]["artifacts"] == 2


def test_sealed_cli_is_explicit_and_fails_closed_on_windows(tmp_path):
    path = tmp_path / "context.db"
    seeded(path)
    result = cli(path, "--sealed-file")
    # A normal writable fixture is never sealed, on any OS.
    assert result.returncode == 1
    assert '"error_type": "RuntimeArtifactTrustError"' in result.stdout


def test_lazy_inventory_complete_independent_values_and_closed_connection(tmp_path):
    from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
    path = tmp_path / "context.db"
    _, atp, wta = seeded(path)
    refs = [add_receipt(path, revision=f"r{i}") for i in range(5)]
    with closing(sqlite3.connect(path, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        artifacts = VerifiedArtifactMapping(conn)
        receipts = VerifiedReceiptMapping(conn)
        assert set(artifacts) == {atp, wta}
        assert set(receipts) == set(refs)
        assert len(receipts) == 5
        receipts[refs[0]]["payload"]["sets"] = -999
        artifacts[atp]["payload"]["state"].clear()
        assert receipts[refs[0]]["payload"]["sets"] == 3
        assert artifacts[atp]["payload"]["state"]
        assert refs[0] in receipts and "0" * 64 not in receipts
        with pytest.raises(KeyError):
            receipts["0" * 64]
        with pytest.raises(TypeError):
            receipts[refs[0]] = {}
    for operation in (lambda: receipts[refs[0]], lambda: len(artifacts),
                      lambda: refs[0] in receipts, lambda: list(artifacts)):
        with pytest.raises((sqlite3.ProgrammingError, RuntimeArtifactTrustError)):
            operation()


@pytest.mark.parametrize("boundary", ["commit", "rollback", "sql_commit", "sql_rollback",
    "cursor_commit", "cursor_rollback", "returned_cursor", "script", "cursor_script",
    "context_commit", "context_rollback", "executemany_rollback", "cursor_executemany_rollback",
    "isolation_commit", "savepoint_release", "ended", "closed"])
def test_inventory_transaction_generation_never_revives(tmp_path, monkeypatch, boundary):
    from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping, ArtifactSubsetMapping
    import context_observations
    path = tmp_path / "context.db"
    _, atp, wta = seeded(path)
    first, second = add_receipt(path, revision="first"), add_receipt(path, revision="second")
    original_decoder = context_observations._decode_receipt
    def guarded(row):
        if row[0] == first:
            pytest.fail("protected receipt body decoded")
        return original_decoder(row)
    monkeypatch.setattr(context_observations, "_decode_receipt", guarded)
    with runtime._open_database(path, writable=True) as conn:
        conn.execute("CREATE TABLE boundary_test (id INTEGER PRIMARY KEY)")
        for _ in range(2):  # The second pass uses cached transaction SQL.
            conn.execute("SAVEPOINT held" if boundary == "savepoint_release" else "BEGIN")
            artifacts = VerifiedArtifactMapping(conn)
            ordinary = VerifiedReceiptMapping(conn)
            protected = VerifiedReceiptMapping(conn, protected_receipts={first})
            subset = ArtifactSubsetMapping(artifacts, [atp, wta])
            views = [(artifacts, atp), (ordinary, second), (protected, first), (subset, atp)]
            live_iterators = []
            for view, key in views:
                assert key in view
                assert len(view) == 2
                assert view[key]
                iterator = iter(view)
                next(iterator)
                live_iterators.append(iterator)
            if boundary in {"commit", "rollback"}:
                getattr(conn, boundary)()
            elif boundary in {"sql_commit", "sql_rollback"}:
                conn.execute("/* cached boundary */ " + boundary.removeprefix("sql_").upper())
            elif boundary in {"cursor_commit", "cursor_rollback"}:
                conn.cursor().execute(boundary.removeprefix("cursor_").upper())
            elif boundary == "returned_cursor":
                conn.execute("SELECT 1").execute("COMMIT")
            elif boundary in {"script", "cursor_script"}:
                target = conn if boundary == "script" else conn.cursor()
                target.executescript("BEGIN; SELECT 1;")  # implicit end + new BEGIN inside one call
            elif boundary in {"context_commit", "context_rollback"}:
                try:
                    with conn:
                        if boundary == "context_rollback": raise RuntimeError("test rollback")
                except RuntimeError:
                    pass
            elif boundary in {"executemany_rollback", "cursor_executemany_rollback"}:
                target = conn if boundary == "executemany_rollback" else conn.cursor()
                with pytest.raises(sqlite3.IntegrityError):
                    target.executemany("INSERT OR ROLLBACK INTO boundary_test VALUES (?)", [(1,), (1,)])
            elif boundary == "isolation_commit":
                conn.isolation_level = None  # SQLite's property setter commits.
            elif boundary == "savepoint_release":
                conn.execute("RELEASE held")
            elif boundary == "ended":
                conn.commit()
            else:
                conn.close()
            if boundary not in {"closed", "ended"} and not conn.in_transaction:
                conn.execute("BEGIN")
            for view, key in views:
                for operation in (lambda: view[key], lambda: len(view), lambda: key in view,
                                  lambda: list(view), lambda: view.get("0" * 64)):
                    with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
                        operation()
            for iterator in live_iterators:
                with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
                    next(iterator)
            if boundary == "closed": break
            conn.rollback()


def test_verified_inventory_rejects_untracked_connections(tmp_path):
    from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
    path = tmp_path / "context.db"
    seeded(path)
    add_receipt(path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("BEGIN")
        for factory in (VerifiedArtifactMapping, VerifiedReceiptMapping):
            with pytest.raises(RuntimeArtifactTrustError, match="tracked"):
                factory(conn)


@pytest.mark.parametrize("boundary", ["commit", "rollback", "context_exit", "autocommit_setters"])
def test_pep249_end_and_automatic_restart_invalidates_views(tmp_path, boundary):
    from context_runtime_inventory import VerifiedArtifactMapping, ArtifactSubsetMapping
    if not hasattr(sqlite3.Connection, "autocommit"):
        pytest.skip("PEP249 autocommit setting requires Python 3.12")
    path = tmp_path / "context.db"
    _, atp, _ = seeded(path)
    with closing(sqlite3.connect(path, factory=TrackedConnection, autocommit=False)) as conn:
        artifacts = VerifiedArtifactMapping(conn)
        subset = ArtifactSubsetMapping(artifacts, [atp])
        assert conn.in_transaction
        if boundary == "context_exit":
            with conn:
                pass
        elif boundary == "autocommit_setters":
            conn.autocommit = True
            assert not conn.in_transaction
            conn.autocommit = False
        else:
            getattr(conn, boundary)()
        assert conn.in_transaction  # Boolean alone cannot detect this boundary.
        for view in (artifacts, subset):
            with pytest.raises(RuntimeArtifactTrustError):
                len(view)
        assert len(VerifiedArtifactMapping(conn)) == 2


@pytest.mark.parametrize("damage", ["orphan", "unreferenced_receipt"])
def test_complete_inventory_rejects_unreferenced_corruption(tmp_path, damage):
    path = tmp_path / "context.db"
    seeded(path)
    add_receipt(path)
    with closing(sqlite3.connect(path)) as conn, conn:
        if damage == "orphan":
            from context_models.contracts import digest
            content = {"orphan": True}
            conn.execute("INSERT INTO context_contents VALUES (?,?)", (digest(content), canonical_bytes(content)))
        else:
            conn.execute("UPDATE context_observations SET source='wrong-source'")
    with pytest.raises(ArtifactIntegrityError):
        runtime.verify_context_database(path)


def test_lazy_membership_does_not_decode_unopened_final(tmp_path, monkeypatch):
    from context_dataset_helpers import stored_packet
    from context_runtime_inventory import VerifiedReceiptMapping
    import context_observations
    packet = stored_packet(tmp_path)
    finals = {item["event"]["event_key"] for item in packet["plan"]["test_inventory"]}
    original = context_observations._decode_receipt
    def guarded(row):
        if row[2] in finals and row[7] == "match_outcome":
            pytest.fail("protected final decoded")
        return original(row)
    monkeypatch.setattr(context_observations, "_decode_receipt", guarded)
    monkeypatch.setattr(runtime, "_decode_receipt", guarded)
    with closing(sqlite3.connect(packet["path"], factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        refs = {r for r, event, kind in conn.execute(
            "SELECT digest,event_key,kind FROM context_observations") if event in finals and kind == "match_outcome"}
        assert refs
        receipts = VerifiedReceiptMapping(conn, protected_receipts=refs)
        assert refs <= set(receipts)
        for ref in refs:
            assert ref in receipts
            assert "source_schema" not in receipts[ref]
        from context_runtime_history_cache import EncodedHistoryCache
        from context_runtime_tennis import _replay_history
        from context_dataset_helpers import EVALUATED
        receipts.validate_all()
        early = tuple(receipts.values_at_or_before(EVALUATED-timedelta(days=3650)))
        assert {row["digest"] for row in early} == refs
        assert all("source_schema" not in row for row in early)
        cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
        assert cache._plan_bases(receipts, {"ATP": EVALUATED})
        assert _replay_history(receipts, cutoff=EVALUATED, tour="ATP", max_bytes=None, cache=cache) == ()
        assert _replay_history(receipts, cutoff=EVALUATED, tour="ATP", max_bytes=None, cache=cache) == ()
        assert cache.stats["hits"] == 1
        assert _replay_history(receipts, cutoff=EVALUATED-timedelta(days=3650), tour="ATP", max_bytes=0, cache=cache) == ()
        assert cache.stats["covering_hits"] == 1
    report = runtime.verify_context_database(packet["path"])
    assert "d2-final-source-replay-not-opened" in report["limitations"]
    with closing(sqlite3.connect(packet["path"])) as conn, conn:
        ordinary = conn.execute("SELECT digest FROM context_observations WHERE kind!='match_outcome' LIMIT 1").fetchone()[0]
        conn.execute("UPDATE context_observations SET source='corrupted-ordinary' WHERE digest=?", (ordinary,))
    with pytest.raises(ArtifactIntegrityError):
        runtime.verify_context_database(packet["path"])


def test_original_descriptors_release_histories_between_cutoffs(tmp_path, monkeypatch):
    from test_tennis_live_worker import configure, run_batch, NOW
    from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
    from context_runtime_tennis import verify_live_originals, LiveReplayDescriptor
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions, decision=NOW-timedelta(seconds=1))
    run_batch(db, predictions)
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        artifacts, receipts = VerifiedArtifactMapping(conn), VerifiedReceiptMapping(conn)
        clocks = {ref: datetime.fromisoformat(clock) for ref, clock in conn.execute("SELECT digest,created_at FROM artifacts")}
        descriptors = verify_live_originals(artifacts, clocks, receipts, set())
        assert len(descriptors) == 2
        assert all(isinstance(value, LiveReplayDescriptor) for value in descriptors.values())
        assert all(not hasattr(value, "history") and not hasattr(value, "base") for value in descriptors.values())
    assert runtime.verify_context_database(db)["counts"]["snapshots"] == 2


def test_history_budget_rejects_complete_replay_without_truncation(tmp_path, monkeypatch):
    from test_context_runtime_tennis_live import _stored
    from context_runtime_inventory import VerifiedReceiptMapping
    from context_runtime_tennis import _replay_history
    from test_tennis_live_worker import NOW
    db, _ = _stored(monkeypatch, tmp_path)
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        complete = _replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        assert type(complete) is tuple and len(complete) == 1
        with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
            _replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=1)
        assert _replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None) == complete


@pytest.fixture
def encoded_history_fixture(tmp_path, monkeypatch):
    from test_context_runtime_tennis_live import _stored
    from test_tennis_live_worker import NOW, competition
    from context_runtime_inventory import VerifiedReceiptMapping
    from context_sources.tennis_status import normalize_tennis_status
    from context_observations import append_observation
    db, _ = _stored(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    for row in normalize_tennis_status("ATP", "189-2026", competition(),
            grouping_slug="mens-singles", observed_at=NOW+timedelta(seconds=1)):
        append_observation(db, row, observed_at=NOW+timedelta(seconds=1))
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        yield conn, VerifiedReceiptMapping(conn), NOW


def test_encoded_history_eight_consumers_two_cold_passes(encoded_history_fixture, monkeypatch):
    from context_runtime_history_cache import EncodedHistoryCache
    import context_runtime_tennis as tennis_runtime
    from context_sources.tennis_status import select_tennis_observations
    conn, receipts, now = encoded_history_fixture
    cutoffs = (now, now+timedelta(seconds=2))
    expected = [select_tennis_observations(tuple(receipts.values()), cutoff=cutoff, tour="ATP") for cutoff in cutoffs]
    assert [len(rows) for rows in expected] == [1, 2]
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    cold, calls = tennis_runtime._cold_replay_history, []
    def counted(*args, **kwargs):
        calls.append(kwargs["cutoff"])
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", counted)
    for index in (0, 1, 0, 1, 1, 0, 1, 0):
        result = tennis_runtime._replay_history(receipts, cutoff=cutoffs[index], tour="ATP", max_bytes=None, cache=cache)
        assert type(result) is tuple and canonical_bytes(result) == canonical_bytes(expected[index])
    assert calls == list(cutoffs)
    assert cache.stats["hits"] == 6 and cache.stats["misses"] == 2
    assert cache.stats["entries"] == 2
    assert cache.stats["bytes"] == sum(len(canonical_bytes(row)) for rows in expected for row in rows)


def test_covering_history_later_first_exact_owning_parity(encoded_history_fixture, monkeypatch):
    from datetime import timezone
    import context_runtime_tennis as tennis_runtime
    from context_runtime_history_cache import EncodedHistoryCache
    from context_sources.tennis_status import select_tennis_observations
    _, receipts, now = encoded_history_fixture
    baseline = tuple(receipts.values())
    receipts.validate_all()
    cache = EncodedHistoryCache(receipts)
    cold, calls = tennis_runtime._cold_replay_history, []
    def counted(*args, **kwargs):
        calls.append(kwargs["cutoff"])
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", counted)
    later = now+timedelta(seconds=2)
    for cutoff in (later, now, later, now, now-timedelta(microseconds=1),
                   now.astimezone(timezone(timedelta(hours=-5))), now+timedelta(seconds=1)):
        expected = select_tennis_observations(baseline, cutoff=cutoff, tour="ATP")
        actual = tennis_runtime._replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None, cache=cache)
        assert type(actual) is tuple and canonical_bytes(actual) == canonical_bytes(expected)
        if actual:
            actual[0]["payload"].clear()  # Neither parent nor independently stored child may be poisoned.
    assert calls == [later]
    assert cache.stats["covering_hits"] == 3


def test_covering_history_admits_only_retained_subset_bytes(encoded_history_fixture, monkeypatch):
    import context_runtime_tennis as tennis_runtime
    from context_runtime_history_cache import EncodedHistoryCache
    _, receipts, now = encoded_history_fixture
    receipts.validate_all()
    cache = EncodedHistoryCache(receipts)
    later = tennis_runtime._replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None, cache=cache)
    assert len(later) == 2
    size = len(canonical_bytes(later[0]))
    assert sum(len(canonical_bytes(row)) for row in later) > size
    def no_cold(*args, **kwargs):
        pytest.fail("covering result fell back to full cold reconstruction")
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", no_cold)
    with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
        tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=size-1, cache=cache)
    assert cache.stats["entries"] == 1  # Failed subset never published.
    assert tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=size, cache=cache) == (later[0],)
    assert tennis_runtime._replay_history(receipts, cutoff=now-timedelta(days=1), tour="ATP", max_bytes=0, cache=cache) == ()


@pytest.mark.parametrize("fallback", ["never_validated", "different_tour", "forward", "missing"])
def test_covering_history_cold_fallback_requires_proof_and_cover(encoded_history_fixture, monkeypatch, fallback):
    import context_runtime_tennis as tennis_runtime
    from context_runtime_history_cache import EncodedHistoryCache
    _, receipts, now = encoded_history_fixture
    if fallback != "never_validated":
        receipts.validate_all()
    cache = EncodedHistoryCache(receipts, max_bytes=0 if fallback == "missing" else 1024**2)
    cold, calls = tennis_runtime._cold_replay_history, []
    def counted(*args, **kwargs):
        calls.append(kwargs["cutoff"])
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", counted)
    initial = now if fallback == "forward" else now+timedelta(seconds=2)
    tennis_runtime._replay_history(receipts, cutoff=initial, tour="ATP", max_bytes=None, cache=cache)
    requested = now+timedelta(seconds=2) if fallback == "forward" else now
    tour = "WTA" if fallback == "different_tour" else "ATP"
    assert tennis_runtime._replay_history(receipts, cutoff=requested, tour=tour, max_bytes=None, cache=cache)
    assert calls == [initial, requested]


@pytest.mark.parametrize("mutation", ["write", "ddl", "temp", "commit", "rollback", "close"])
@pytest.mark.parametrize("empty", [False, True])
def test_covering_history_revokes_during_fresh_decode(encoded_history_fixture, monkeypatch, mutation, empty):
    from types import SimpleNamespace
    import context_runtime_tennis as tennis_runtime
    import context_runtime_history_cache as history_cache
    conn, receipts, now = encoded_history_fixture
    receipts.validate_all()
    cache = history_cache.EncodedHistoryCache(receipts)
    tennis_runtime._replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None, cache=cache)
    owner = history_cache.json.loads
    def changed(raw):
        row = owner(raw)
        if mutation == "write": conn.execute("UPDATE context_observations SET source=source")
        elif mutation == "ddl": conn.execute("CREATE TABLE covering_mutation (id INTEGER)")
        elif mutation == "temp": conn.execute("CREATE TEMP TABLE context_observations (digest TEXT)")
        elif mutation == "close": conn.close()
        else:
            getattr(conn, mutation)()
            conn.execute("BEGIN")
        return row
    monkeypatch.setattr(history_cache, "json", SimpleNamespace(loads=changed))
    cutoff = now-timedelta(days=1) if empty else now
    for _ in range(2):
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
            tennis_runtime._replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["entries"] == 0


@pytest.mark.parametrize("phase", ["decode", "encode"])
def test_covering_history_interrupted_build_never_publishes(encoded_history_fixture, monkeypatch, phase):
    from types import SimpleNamespace
    import context_runtime_tennis as tennis_runtime
    import context_runtime_history_cache as history_cache
    _, receipts, now = encoded_history_fixture
    receipts.validate_all()
    cache = history_cache.EncodedHistoryCache(receipts)
    parent = tennis_runtime._replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None, cache=cache)
    def no_cold(*args, **kwargs):
        pytest.fail("covering result unexpectedly rebuilt cold")
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", no_cold)
    monkeypatch.setattr(history_cache, "json", SimpleNamespace(loads=history_cache.json.loads))
    target, name = (history_cache.json, "loads") if phase == "decode" else (history_cache, "canonical_bytes")
    owner = getattr(target, name)
    def interrupted(*args, **kwargs):
        raise MemoryError("interrupted covering history build")
    monkeypatch.setattr(target, name, interrupted)
    with pytest.raises(MemoryError):
        tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["entries"] == 1 and cache.stats["pending_bytes"] == 0
    monkeypatch.setattr(target, name, owner)
    assert tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache) == (parent[0],)


def test_covering_history_child_survives_parent_eviction(encoded_history_fixture, monkeypatch):
    import context_runtime_tennis as tennis_runtime
    from context_runtime_history_cache import EncodedHistoryCache
    _, receipts, now = encoded_history_fixture
    receipts.validate_all()
    later = now+timedelta(seconds=2)
    expected = tennis_runtime._replay_history(receipts, cutoff=later, tour="ATP", max_bytes=None)
    cache = EncodedHistoryCache(receipts, max_bytes=sum(len(canonical_bytes(row)) for row in expected))
    cold, calls = tennis_runtime._cold_replay_history, []
    def counted(*args, **kwargs):
        calls.append(kwargs["cutoff"])
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", counted)
    tennis_runtime._replay_history(receipts, cutoff=later, tour="ATP", max_bytes=None, cache=cache)
    child = tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    assert child == (expected[0],) and cache.stats["evictions"] == 1
    child[0]["payload"].clear()
    assert tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache) == (expected[0],)
    assert tennis_runtime._replay_history(receipts, cutoff=later, tour="ATP", max_bytes=None, cache=cache) == expected
    assert calls == [later, later]
    assert cache.stats["peak_bytes"] <= cache.stats["max_bytes"]


def test_encoded_history_cache_returns_fresh_nested_objects(encoded_history_fixture):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    def replay():
        return _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    first = replay()
    expected = canonical_bytes(first)
    first[0]["payload"]["participant_ids"].append("poison")
    second = replay()
    assert canonical_bytes(second) == expected
    second[0]["payload"].clear()
    assert canonical_bytes(replay()) == expected


def test_encoded_history_warm_hit_rejects_string_cutoff(encoded_history_fixture):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    from context_models.contracts import ContextContractError, canonical_timestamp
    _, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    assert _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    with pytest.raises(ContextContractError):
        _replay_history(receipts, cutoff=canonical_timestamp(now), tour="ATP", max_bytes=None, cache=cache)


@pytest.mark.parametrize("mode", ["evict", "bypass"])
def test_encoded_history_pressure_never_truncates_or_rejects(encoded_history_fixture, mode):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    later = now+timedelta(seconds=2)
    expected = [_replay_history(receipts, cutoff=c, tour="ATP", max_bytes=None) for c in (now, later)]
    budget = max(sum(len(canonical_bytes(row)) for row in rows) for rows in expected) if mode == "evict" else 1
    cache = EncodedHistoryCache(receipts, max_bytes=budget)
    for index in (0, 1, 0):
        result = _replay_history(receipts, cutoff=(now, later)[index], tour="ATP", max_bytes=None, cache=cache)
        assert canonical_bytes(result) == canonical_bytes(expected[index])
        assert cache.stats["bytes"] + cache.stats["pending_bytes"] <= budget
        assert cache.stats["peak_bytes"] <= budget
    assert cache.stats["misses"] == 3
    assert cache.stats["evictions" if mode == "evict" else "bypasses"] >= 2


@pytest.mark.parametrize("mutation", ["commit", "rollback", "same_transaction_write", "close", "other_inventory"])
def test_encoded_history_cannot_outlive_exact_inventory(encoded_history_fixture, mutation):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_inventory import VerifiedReceiptMapping
    from context_runtime_tennis import _replay_history
    conn, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    if mutation in {"commit", "rollback"}:
        getattr(conn, mutation)()
        conn.execute("BEGIN")
    elif mutation == "same_transaction_write":
        conn.execute("UPDATE context_observations SET source=source")
    elif mutation == "close":
        conn.close()
    else:
        receipts = VerifiedReceiptMapping(conn)
    for _ in range(2):
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
            _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)


def test_encoded_history_budget_failure_does_not_publish_partial_entry(encoded_history_fixture):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    expected = _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None)
    size = sum(len(canonical_bytes(row)) for row in expected)
    with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
        _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=size-1, cache=cache)
    assert cache.stats["entries"] == 0 and cache.stats["pending_bytes"] == 0
    assert _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=size, cache=cache) == expected
    with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
        _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=size-1, cache=cache)
    assert cache.stats["hits"] == 1


@pytest.mark.parametrize("validated", [False, True])
@pytest.mark.parametrize("damage", ["future_unrelated", "other_tour_typed"])
def test_encoded_history_cold_path_keeps_full_validation(encoded_history_fixture, damage, validated):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_inventory import VerifiedReceiptMapping
    from context_runtime_tennis import _replay_history
    from context_models.contracts import digest, canonical_timestamp, ContextIntegrityError
    import json
    conn, _, now = encoded_history_fixture
    rows = conn.execute("SELECT content_digest,payload FROM context_contents").fetchall()
    for ref, raw in rows:
        content = json.loads(raw)
        if content["payload"]["tour"] == "WTA":
            if damage == "future_unrelated":
                conn.execute("UPDATE context_observations SET observed_at=? WHERE content_digest=?", (canonical_timestamp(now+timedelta(days=10)), ref))
            else:
                content["payload"]["competition_revision"] = "0"*64
                new_content = digest(content)
                clock = conn.execute("SELECT observed_at FROM context_observations WHERE content_digest=?", (ref,)).fetchone()[0]
                conn.execute("UPDATE context_contents SET content_digest=?,payload=? WHERE content_digest=?", (new_content, canonical_bytes(content), ref))
                conn.execute("UPDATE context_observations SET content_digest=?,digest=? WHERE content_digest=?",
                    (new_content, digest({"content_digest": new_content, "observed_at": clock}), ref))
            break
    else:
        pytest.fail("missing other-tour fixture")
    receipts = VerifiedReceiptMapping(conn)
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    if validated and damage == "other_tour_typed":
        receipts.validate_all()  # B1-valid damage must still reach eligible opposite-tour owning validation.
    with pytest.raises(ContextIntegrityError):
        if validated and damage == "future_unrelated":
            receipts.validate_all()
        _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["entries"] == 0


def test_encoded_history_failed_encoding_discards_pending(encoded_history_fixture, monkeypatch):
    import context_runtime_history_cache as history_cache
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    cache = history_cache.EncodedHistoryCache(receipts, max_bytes=1024**2)
    encode, calls = history_cache.canonical_bytes, 0
    def interrupted(row):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise MemoryError("test interrupted row encoding")
        return encode(row)
    monkeypatch.setattr(history_cache, "canonical_bytes", interrupted)
    with pytest.raises(MemoryError):
        _replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["entries"] == 0
    assert cache.stats["pending_bytes"] == cache.stats["bytes"] == 0
    monkeypatch.setattr(history_cache, "canonical_bytes", encode)
    assert len(_replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None, cache=cache)) == 2
    assert cache.stats["misses"] == 2


@pytest.mark.parametrize("statement", [
    "DROP TABLE context_observations",
    "CREATE TABLE cache_schema_change (id INTEGER)",
    "ALTER TABLE context_observations ADD COLUMN cache_schema_change INTEGER",
    "CREATE TEMP TABLE context_observations (digest TEXT)",
])
@pytest.mark.parametrize("cursor_sql", [False, True])
@pytest.mark.parametrize("warm", [False, True])
def test_encoded_history_schema_change_invalidates_original_inventory(
        encoded_history_fixture, statement, cursor_sql, warm):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    conn, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts)
    cutoff = now-timedelta(days=1)
    if warm:
        assert _replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None, cache=cache) == ()
    generation, changes = conn.transaction_generation, conn.total_changes
    executor = conn.cursor() if cursor_sql else conn
    executor.execute(statement)
    assert conn.in_transaction
    assert (conn.transaction_generation, conn.total_changes) == (generation, changes)
    if statement.startswith("DROP"):
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            _replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None)
    for _ in range(2):
        with pytest.raises(RuntimeArtifactTrustError, match="inventory changed"):
            _replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["entries"] == cache.stats["bytes"] == cache.stats["pending_bytes"] == 0


def test_validated_cutoff_filters_only_after_complete_pass(encoded_history_fixture, monkeypatch):
    import context_observations
    from context_runtime_tennis import _replay_history
    from context_models.contracts import canonical_timestamp
    conn, receipts, now = encoded_history_fixture
    all_refs = set(receipts)
    eligible = {ref for ref, clock in conn.execute("SELECT digest,observed_at FROM context_observations")
                if clock <= canonical_timestamp(now)}
    assert len(all_refs) == 3 and len(eligible) == 2
    decoded, owner = [], context_observations._decode_receipt
    def counted(raw):
        decoded.append(raw[0])
        return owner(raw)
    monkeypatch.setattr(context_observations, "_decode_receipt", counted)
    assert {row["digest"] for row in receipts.values_at_or_before(now)} == all_refs
    assert set(decoded) == all_refs
    decoded.clear()
    assert receipts.validate_all() == 3
    assert set(decoded) == all_refs
    decoded.clear()
    assert {row["digest"] for row in receipts.values_at_or_before(now)} == eligible
    assert set(decoded) == eligible
    from context_runtime_inventory import VerifiedReceiptMapping
    assert {row["digest"] for row in VerifiedReceiptMapping(conn).values_at_or_before(now)} == all_refs
    decoded.clear()
    result = _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None)
    assert len(result) == 1 and result[0]["payload"]["tour"] == "ATP"
    assert set(decoded) == eligible  # Actual cold replay uses the completed capability.
    result[0]["payload"].clear()
    assert _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None)[0]["payload"]["tour"] == "ATP"


def test_streamed_receipts_one_join_preserves_full_owner_counts_and_phases(encoded_history_fixture, monkeypatch):
    import context_runtime_inventory as inventory
    import context_observations
    conn, receipts, _ = encoded_history_fixture
    events, joins = [], []
    execute, decode, content = TrackedConnection.execute, context_observations._decode_receipt, inventory._decode_object
    def observed_execute(self, sql, *args, **kwargs):
        if self is conn:
            if "LEFT JOIN context_contents AS c" in sql: joins.append(sql)
            if "WHERE r.digest IS NULL" in sql: events.append("orphan")
        return execute(self, sql, *args, **kwargs)
    def observed_content(*args, **kwargs):
        events.append("content")
        return content(*args, **kwargs)
    def observed_receipt(raw):
        events.append("receipt")
        return decode(raw)
    monkeypatch.setattr(TrackedConnection, "execute", observed_execute)
    monkeypatch.setattr(inventory, "_decode_object", observed_content)
    monkeypatch.setattr(context_observations, "_decode_receipt", observed_receipt)
    assert receipts.validate_all() == 3
    assert events == ["content"]*3 + ["receipt"]*3 + ["orphan"]
    assert len(joins) == 1


@pytest.mark.parametrize("future_count", [0, 40])
def test_streamed_cutoff_future_growth_has_constant_python_checks(encoded_history_fixture, monkeypatch, future_count):
    from context_models.contracts import canonical_timestamp, digest
    from context_sources.tennis_status import normalize_tennis_status
    from test_tennis_live_worker import competition
    conn, receipts, now = encoded_history_fixture
    for index in range(future_count):
        clock = now+timedelta(days=index+1)
        for row in normalize_tennis_status("ATP", "189-2026", competition(), grouping_slug="mens-singles", observed_at=clock):
            content = digest(row)
            observed = canonical_timestamp(clock)
            ref = digest({"content_digest": content, "observed_at": observed})
            conn.execute("INSERT INTO context_contents VALUES (?,?)", (content, canonical_bytes(row)))
            conn.execute("INSERT INTO context_observations VALUES (?,?,?,?,?,?,?,?)",
                (ref, content, row["event_key"], observed, row["schedule_revision"], row["source"], row["subject_id"], row["kind"]))
    assert receipts.validate_all() == future_count+3
    joins, checks = [], []
    execute, check = TrackedConnection.execute, receipts._check_validation
    def observed_execute(self, sql, *args, **kwargs):
        if self is conn and "LEFT JOIN context_contents AS c" in sql: joins.append(sql)
        return execute(self, sql, *args, **kwargs)
    def observed_check():
        checks.append(1)
        return check()
    monkeypatch.setattr(TrackedConnection, "execute", observed_execute)
    monkeypatch.setattr(receipts, "_check_validation", observed_check)
    assert len(tuple(receipts.values_at_or_before(now))) == 2
    assert len(checks) <= 10
    assert len(joins) == 1 and "WHERE r.observed_at<=?" in joins[0]


@pytest.mark.parametrize("bad_identity", [None, "not-a-digest", b"bad-digest"])
@pytest.mark.parametrize("protected", [False, True])
def test_streamed_receipts_reject_null_and_invalid_identity(encoded_history_fixture, bad_identity, protected):
    from context_runtime_inventory import VerifiedReceiptMapping
    from context_models.contracts import ContextContractError
    conn, _, _ = encoded_history_fixture
    ref = conn.execute("SELECT digest FROM context_observations LIMIT 1").fetchone()[0]
    conn.execute("UPDATE context_observations SET digest=? WHERE digest=?", (bad_identity, ref))
    receipts = VerifiedReceiptMapping(conn, protected_receipts={bad_identity} if protected else ())
    with pytest.raises((ContextContractError, ArtifactIntegrityError, KeyError)):
        receipts.validate_all()
    with pytest.raises(RuntimeArtifactTrustError):
        receipts.validate_all()


@pytest.mark.parametrize("clock", ["2000-01-01T00:00:00.000000Z", "2099-01-01T00:00:00.000000Z", "!unknown", "unknown", b"opaque-clock"])
def test_streamed_cutoff_preserves_all_opaque_refs_and_skips_absent(encoded_history_fixture, monkeypatch, clock):
    import context_observations
    from context_runtime_inventory import VerifiedReceiptMapping
    conn, _, now = encoded_history_fixture
    all_refs = {row[0] for row in conn.execute("SELECT digest FROM context_observations")}
    protected = set(sorted(all_refs)[:2])
    for ref in protected:
        conn.execute("UPDATE context_observations SET observed_at=? WHERE digest=?", (clock, ref))
    receipts = VerifiedReceiptMapping(conn, protected_receipts=protected | {"0"*64})
    decode = context_observations._decode_receipt
    def guarded(raw):
        if raw[0] in protected: pytest.fail("opaque protected receipt body decoded")
        return decode(raw)
    monkeypatch.setattr(context_observations, "_decode_receipt", guarded)
    receipts.validate_all()
    rows = tuple(receipts.values_at_or_before(now+timedelta(seconds=2)))
    assert len(rows) == 3 and {row["digest"] for row in rows} == all_refs
    assert all("source_schema" not in row for row in rows if row["digest"] in protected)


def test_streamed_cutoff_missing_protected_lookup_cannot_hide_mutation(encoded_history_fixture, monkeypatch):
    from context_runtime_inventory import VerifiedReceiptMapping
    conn, _, now = encoded_history_fixture
    missing = "0"*64
    receipts = VerifiedReceiptMapping(conn, protected_receipts={missing})
    receipts.validate_all()
    execute = TrackedConnection.execute
    changed = []
    def mutate_on_absence(self, sql, *args, **kwargs):
        if self is conn and "WHERE r.digest=?" in sql and args == ((missing,),):
            execute(self, "UPDATE context_observations SET source=source")
            changed.append(1)
        return execute(self, sql, *args, **kwargs)
    monkeypatch.setattr(TrackedConnection, "execute", mutate_on_absence)
    with pytest.raises(RuntimeArtifactTrustError):
        tuple(receipts.values_at_or_before(now))
    assert changed == [1]
    with pytest.raises(RuntimeArtifactTrustError):
        receipts.validate_all()


@pytest.mark.parametrize("phase", ["physical", "cutoff"])
@pytest.mark.parametrize("mutation", ["write", "ddl", "commit", "rollback", "close", "interrupt"])
def test_streamed_receipts_last_decode_failure_never_completes(encoded_history_fixture, monkeypatch, phase, mutation):
    import context_observations
    conn, receipts, now = encoded_history_fixture
    if phase == "cutoff": receipts.validate_all()
    owner, calls = context_observations._decode_receipt, []
    def fail_last(raw):
        row = owner(raw)
        calls.append(raw[0])
        if len(calls) == 3:
            if mutation == "write": conn.execute("UPDATE context_observations SET source=source")
            elif mutation == "ddl": conn.execute("CREATE TABLE stream_mutation (id INTEGER)")
            elif mutation == "close": conn.close()
            elif mutation == "interrupt": raise KeyboardInterrupt("last receipt interrupted")
            else:
                getattr(conn, mutation)()
                conn.execute("BEGIN")
        return row
    monkeypatch.setattr(context_observations, "_decode_receipt", fail_last)
    with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError, KeyboardInterrupt)):
        if phase == "physical": receipts.validate_all()
        else: tuple(receipts.values_at_or_before(now+timedelta(seconds=2)))
    assert len(calls) == 3
    if phase == "physical":
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
            receipts.validate_all()


def test_streamed_receipts_left_join_rejects_missing_content(encoded_history_fixture):
    from context_models.contracts import ContextIntegrityError
    conn, receipts, _ = encoded_history_fixture
    ref = conn.execute("SELECT content_digest FROM context_observations LIMIT 1").fetchone()[0]
    conn.execute("DELETE FROM context_contents WHERE content_digest=?", (ref,))
    with pytest.raises(ContextIntegrityError):
        receipts.validate_all()
    with pytest.raises(RuntimeArtifactTrustError):
        receipts.validate_all()


def test_streamed_cutoff_empty_query_still_checks_mutation(encoded_history_fixture, monkeypatch):
    conn, receipts, now = encoded_history_fixture
    receipts.validate_all()
    execute = TrackedConnection.execute
    changed = []
    def mutate_after_query(self, sql, *args, **kwargs):
        cursor = execute(self, sql, *args, **kwargs)
        if self is conn and "WHERE r.observed_at<=?" in sql:
            execute(self, "UPDATE context_observations SET source=source")
            changed.append(1)
        return cursor
    monkeypatch.setattr(TrackedConnection, "execute", mutate_after_query)
    with pytest.raises(RuntimeArtifactTrustError):
        tuple(receipts.values_at_or_before(now-timedelta(days=1)))
    assert changed == [1]


def test_streamed_cutoff_rejects_mutation_after_last_yield(encoded_history_fixture):
    conn, receipts, now = encoded_history_fixture
    receipts.validate_all()
    iterator = receipts.values_at_or_before(now)
    assert next(iterator) and next(iterator)
    conn.execute("UPDATE context_observations SET source=source")
    with pytest.raises(RuntimeArtifactTrustError):
        next(iterator)


def test_validated_cutoff_exact_boundary_and_timezone_parity(encoded_history_fixture):
    from datetime import timezone
    from context_sources.tennis_status import select_tennis_observations
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    baseline = tuple(receipts.values())
    receipts.validate_all()
    for cutoff in (now-timedelta(microseconds=1), now, now+timedelta(seconds=1),
                   now.astimezone(timezone(timedelta(hours=5, minutes=30)))):
        for tour in ("ATP", "WTA"):
            expected = select_tennis_observations(baseline, cutoff=cutoff, tour=tour)
            actual = _replay_history(receipts, cutoff=cutoff, tour=tour, max_bytes=None)
            assert type(actual) is tuple and canonical_bytes(actual) == canonical_bytes(expected)


@pytest.mark.parametrize("failure", ["interrupt", "mutation", "orphan", "future_index", "content"])
def test_validated_cutoff_failed_pass_never_reseals(encoded_history_fixture, monkeypatch, failure):
    import context_observations
    from context_models.contracts import ContextIntegrityError, canonical_timestamp
    conn, receipts, now = encoded_history_fixture
    owner = context_observations._decode_receipt
    if failure in {"interrupt", "mutation"}:
        def interrupted(raw):
            if failure == "interrupt":
                raise KeyboardInterrupt("interrupted full receipt validation")
            conn.execute("UPDATE context_observations SET source=source")
            return owner(raw)
        monkeypatch.setattr(context_observations, "_decode_receipt", interrupted)
    elif failure == "orphan":
        conn.execute("DELETE FROM context_observations WHERE digest=(SELECT digest FROM context_observations LIMIT 1)")
    elif failure == "future_index":
        conn.execute("UPDATE context_observations SET observed_at=?", (canonical_timestamp(now+timedelta(days=10)),))
    else:
        conn.execute("UPDATE context_contents SET payload=?", (b'{}',))
    with pytest.raises((KeyboardInterrupt, RuntimeArtifactTrustError, ArtifactIntegrityError, ContextIntegrityError)):
        receipts.validate_all()
    monkeypatch.setattr(context_observations, "_decode_receipt", owner)
    for _ in range(2):
        with pytest.raises(RuntimeArtifactTrustError):
            tuple(receipts.values_at_or_before(now))
        with pytest.raises(RuntimeArtifactTrustError):
            receipts.validate_all()


@pytest.mark.parametrize("mutation", ["write", "drop", "create", "alter", "temp", "commit", "rollback", "close"])
def test_validated_cutoff_rejects_mutation_and_started_iterators(encoded_history_fixture, mutation):
    conn, receipts, now = encoded_history_fixture
    receipts.validate_all()
    iterator = receipts.values_at_or_before(now+timedelta(seconds=5))
    if mutation != "drop":  # SQLite prohibits DROP while any read cursor is active.
        assert next(iterator)
    sql = {"write": "UPDATE context_observations SET source=source",
           "drop": "DROP TABLE context_observations",
           "create": "CREATE TABLE validation_mutation (id INTEGER)",
           "alter": "ALTER TABLE context_snapshots ADD COLUMN validation_mutation INTEGER",
           "temp": "CREATE TEMP TABLE context_observations (digest TEXT)"}
    if mutation in sql:
        conn.cursor().execute(sql[mutation])
    elif mutation in {"commit", "rollback"}:
        getattr(conn, mutation)()
        conn.execute("BEGIN")
    else:
        conn.close()
    for operation in (lambda: next(iterator), lambda: tuple(receipts.values_at_or_before(now)), receipts.validate_all):
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
            operation()


def test_validated_cutoff_failure_revokes_existing_warm_cache(encoded_history_fixture, monkeypatch):
    import context_observations
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts)
    expected = _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    assert expected
    def interrupted(raw):
        raise KeyboardInterrupt("failed full validation after baseline cache fill")
    monkeypatch.setattr(context_observations, "_decode_receipt", interrupted)
    with pytest.raises(KeyboardInterrupt):
        receipts.validate_all()
    with pytest.raises(RuntimeArtifactTrustError):
        _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["entries"] == 0


def test_encoded_history_empty_entries_and_tour_keys_are_bounded(encoded_history_fixture):
    from context_runtime_history_cache import EncodedHistoryCache
    from context_runtime_tennis import _replay_history
    _, receipts, now = encoded_history_fixture
    cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
    atp = _replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)
    wta = _replay_history(receipts, cutoff=now, tour="WTA", max_bytes=None, cache=cache)
    assert atp[0]["payload"]["tour"] == "ATP" and wta[0]["payload"]["tour"] == "WTA"
    assert cache.stats["misses"] == 2
    for day in range(1, 101):
        assert _replay_history(receipts, cutoff=now-timedelta(days=day), tour="ATP", max_bytes=None, cache=cache) == ()
    assert cache.stats["entries"] <= 32
    assert cache.stats["bytes"] == 0 and cache.stats["evictions"] > 0


def test_encoded_history_real_d4_shares_original_snapshot_cache(encoded_history_fixture, monkeypatch):
    import context_runtime_history_cache as history_cache
    conn, _, _ = encoded_history_fixture
    caches = []
    original = history_cache.EncodedHistoryCache
    class ObservedCache(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            caches.append(self)
    monkeypatch.setattr(history_cache, "EncodedHistoryCache", ObservedCache)
    path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    report = runtime.verify_context_database(path)
    assert report["counts"]["snapshots"] == 2
    assert len(caches) == 1
    assert caches[0].stats["stores"] == 2 and caches[0].stats["hits"] == 4
    assert caches[0].stats["misses"] == 0  # Completed per-tour bases precede replay.


def test_strict_reader_never_accepts_unprovable_platform(tmp_path):
    from context_runtime_input import open_sealed_connection
    if sys.platform == "linux":
        pytest.skip("non-Linux platform fail-closed check")
    path = tmp_path / "context.db"
    seeded(path)
    with pytest.raises(RuntimeArtifactTrustError, match="Linux"):
        with open_sealed_connection(path, max_bytes=1024**3):
            pytest.fail("unprovable sealed reader yielded")


@pytest.fixture
def linux_seal():
    if sys.platform != "linux":
        pytest.skip("real Linux DAC fixtures unavailable on Windows")
    if os.geteuid() == 0:
        pytest.fail("run app/model tests as the application user, never root")
    directory = os.environ.get("CONTEXT_CAPACITY_TEST_ROOT")
    if not directory:
        pytest.skip("controller must provide root-staged CONTEXT_CAPACITY_TEST_ROOT fixtures")
    return Path(directory) / "valid" / "context.db"


def test_linux_real_dac_and_sqlite_readonly(linux_seal):
    from context_runtime_input import open_sealed_connection
    for operation in (lambda: os.open(linux_seal, os.O_WRONLY),
                      lambda: linux_seal.rename(linux_seal.with_suffix(".moved"))):
        with pytest.raises(PermissionError):
            operation()
    with open_sealed_connection(linux_seal, max_bytes=1024**3) as conn:
        assert conn.in_transaction
        assert conn.execute("SELECT count(*) FROM artifacts").fetchone() == (2,)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM artifacts")
    assert runtime.verify_context_database(linux_seal, input_mode="sealed_file") == runtime.verify_context_database(linux_seal)


@pytest.mark.parametrize("damage", ["hardlink", "symlink", "owner", "mode", "ancestor_mode", "sidecar", "wal", "budget"])
def test_linux_sealed_reader_rejects_unsealed_inputs(linux_seal, damage):
    from context_runtime_input import open_sealed_connection
    path = linux_seal if damage == "budget" else linux_seal.parent.parent / damage / "context.db"
    # A missing fixture must never count as a successful trust rejection.
    assert path.exists(), f"controller fixture missing: {damage}"
    with pytest.raises(RuntimeArtifactTrustError):
        with open_sealed_connection(path, max_bytes=1 if damage == "budget" else 1024**3):
            pytest.fail("unsealed input yielded")
