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
        cache = EncodedHistoryCache(receipts, max_bytes=1024**2)
        assert _replay_history(receipts, cutoff=EVALUATED, tour="ATP", max_bytes=None, cache=cache) == ()
        assert _replay_history(receipts, cutoff=EVALUATED, tour="ATP", max_bytes=None, cache=cache) == ()
        assert cache.stats["hits"] == 1
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


@pytest.mark.parametrize("damage", ["future_unrelated", "other_tour_typed"])
def test_encoded_history_cold_path_keeps_full_validation(encoded_history_fixture, damage):
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
    with pytest.raises(ContextIntegrityError):
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
    assert caches[0].stats["misses"] == 2 and caches[0].stats["hits"] == 2


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
