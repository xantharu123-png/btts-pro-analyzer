"""Old admissible objects remain old objects, not new processing blocks."""
from datetime import datetime, timedelta, timezone
import hashlib
import gc
import sqlite3
import sys
import pytest
from types import SimpleNamespace

from context_models.contracts import canonical_timestamp
from context_models.tennis_v3 import tennis_features_v3
from context_observations import append_observation
from context_runtime_tennis import _cold_replay_history
from context_sources.tennis import normalize_tennis_workload
from context_sources.tennis_status import normalize_tennis_status
from context_storage_v2.contracts import StorageIntegrityError, StorageLimitError, StorageLimits
from context_storage_v2.history import build_history
from context_storage_v2.tennis import tennis_features_streaming
from model_artifacts import canonical_bytes
from test_context_storage_history import source
from test_context_tennis_capture import NOW, persist, records
from test_tennis_context_features import base, event, native_row
from runtime_paths import RuntimeArtifactTrustError


MAIN_CAP = 64 * 1024**2


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024**2):
            digest.update(chunk)
    return digest.hexdigest()


def assert_history(view, expected):
    expected_bytes = canonical_bytes(expected)
    assert canonical_bytes(tuple(view.iter_rows())) == expected_bytes
    assert canonical_bytes(tuple(view.iter_rows())) == expected_bytes
    digest = hashlib.sha256()
    for row in expected:
        payload = canonical_bytes(row)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    assert view.row_count == len(expected)
    assert view.canonical_bytes == sum(len(canonical_bytes(row)) for row in expected)
    assert view.binding.selected_digest == digest.hexdigest()
    for group in view.iter_events():
        rows = tuple(row for row in expected if row["event_key"] == group.event_key)
        assert canonical_bytes(tuple(group.iter_rows())) == canonical_bytes(rows)
        latest = max(row["observed_at"] for row in rows)
        wanted = canonical_bytes(tuple(row for row in rows if row["observed_at"] == latest))
        assert canonical_bytes(tuple(group.iter_latest_rows())) == wanted
        assert canonical_bytes(tuple(view.event(group.event_key).iter_latest_rows())) == wanted


def test_real_default_block_status_keeps_old_history_and_tennis_bytes(tmp_path):
    # Regression: removing old-value admission at the default 16 MiB block.
    clock = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
    competition = {"id": "101", "date": "2026-09-12T16:00:00Z",
        "status": {"type": {"state": "pre", "name": "S" * 16777217, "completed": False}},
        "competitors": [{"id": "1"}, {"id": "2"}]}
    generated = normalize_tennis_status("ATP", "189-2026", competition,
        grouping_slug="mens-singles", observed_at=clock)
    assert generated[0]["payload"]["status"] == "scheduled"
    assert generated[0]["payload"]["issues"] == []
    db = tmp_path / "source.sqlite"
    append_observation(db, generated[0], observed_at=clock)
    before = file_hash(db)
    ev = event(event_key="espn:tennis:ATP:match:101", scheduled_start="2026-09-12T16:00:00Z")
    basis = base(ev, cutoff=clock)
    with source(db) as (connection, receipts):
        generation = connection.transaction_generation
        value_limit = connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
        expected = _cold_replay_history(receipts, cutoff=clock, tour="ATP", max_bytes=None)
        assert len(canonical_bytes(expected[0])) == 16778570
        assert db.stat().st_size < 64 * 1024**2
        old_features = canonical_bytes(tennis_features_v3(ev, expected, basis, cutoff=clock))
        with build_history(receipts, directory=tmp_path, cutoff=clock, tour="ATP",
                input_identity=before, main_cap_bytes=MAIN_CAP) as view:
            assert_history(view, expected)
            with view.as_of(clock) as prefix:
                assert_history(prefix, expected)
            with view.as_of(clock-timedelta(microseconds=1)) as prefix:
                assert_history(prefix, ())
            row = next(view.iter_rows())
            row["payload"].clear()
            assert canonical_bytes(next(view.iter_rows())) == canonical_bytes(expected[0])
            with tennis_features_streaming(ev, view, basis, cutoff=clock,
                    work_directory=tmp_path, main_cap_bytes=MAIN_CAP) as features:
                assert canonical_bytes(features.materialize()) == old_features
                assert b"".join(features.iter_canonical_chunks()) == old_features
        assert connection.in_transaction and connection.transaction_generation == generation
        assert connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH) == value_limit
        assert file_hash(db) == before


def test_chosen_large_workload_and_large_index_keep_old_features(tmp_path):
    # Regression: old usable workload is copied to an oversized staging BLOB.
    limits = StorageLimits(block_bytes=2048)
    db = tmp_path / "source.sqlite"
    clock = NOW-timedelta(hours=1)
    generated = normalize_tennis_workload((native_row("7" * 3000),), observed_at=clock)
    persist(db, generated, clock=clock)
    persist(db, records(clock=clock-timedelta(hours=1)), clock=clock-timedelta(hours=1))
    before = file_hash(db)
    ev, basis = event(), base()
    with source(db) as (connection, receipts):
        value_limit = connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
        expected = _cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        assert any(len(row["event_key"].encode()) > limits.block_bytes for row in expected)
        old_features = tennis_features_v3(ev, expected, basis, cutoff=NOW)
        assert old_features["values"]["observed_minutes_1d_a"] == 120
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=before, main_cap_bytes=MAIN_CAP, limits=limits) as view:
            assert_history(view, expected)
            modes = dict(connection_row for connection_row in sqlite3.Connection.execute(
                view._state.connection, "SELECT mode,count(*) FROM main.history GROUP BY mode"))
            assert modes["inline"] > 0 and modes["source"] > 0
            with tennis_features_streaming(ev, view, basis, cutoff=NOW,
                    work_directory=tmp_path, main_cap_bytes=MAIN_CAP, limits=limits) as features:
                assert canonical_bytes(features.materialize()) == canonical_bytes(old_features)
                staged = features._connection.execute(
                    "SELECT receipt,association,mode,row FROM tennis_chosen ORDER BY sequence").fetchall()
                assert staged and all(len(ref) == 64 and len(association) <= limits.block_bytes
                                      for ref, association, _, _ in staged)
                assert {mode for _, _, mode, _ in staged} == {"inline", "source"}
                assert all((mode == "inline" and type(raw) is bytes and len(raw) <= limits.block_bytes)
                           or (mode == "source" and raw is None) for _, _, mode, raw in staged)
                assert features._connection.execute(
                    "SELECT count(*) FROM tennis_chosen WHERE receipt IN (?,?)",
                    tuple(row["digest"] for row in expected if len(row["event_key"]) > 2048)
                ).fetchone() == (1,)
        assert connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH) == value_limit
        assert file_hash(db) == before


def large_source(tmp_path):
    db = tmp_path / "source.sqlite"
    clock = NOW-timedelta(hours=1)
    generated = normalize_tennis_workload((native_row("7" * 3000),), observed_at=clock)
    persist(db, generated, clock=clock)
    return db


def test_closing_nonowning_parent_poison_nested_large_prefix_between_yields(tmp_path):
    # Regression: a prefix must not outlive even a nonowning immediate parent.
    db = large_source(tmp_path)
    with source(db) as (_, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048)) as view:
            parent = view.as_of(NOW)
            child = parent.as_of(NOW)
            try:
                iterator = child.iter_rows()
                next(iterator)
                parent.close()
                with pytest.raises(StorageIntegrityError):
                    next(iterator)
                with pytest.raises(StorageIntegrityError):
                    child.assert_intact()
                view.assert_intact()
            finally:
                iterator.close()
                parent.close()
                child.close()


@pytest.mark.parametrize("operation", ["source-close", "source-restart", "view-close", "reader-restart"])
def test_large_resolution_does_not_survive_lifetime_drift_between_yields(tmp_path, operation):
    db = large_source(tmp_path)
    with source(db) as (connection, receipts):
        view = build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
            input_identity=file_hash(db), main_cap_bytes=MAIN_CAP, limits=StorageLimits(block_bytes=2048))
        prefix = view.as_of(NOW)
        try:
            iterator = prefix.iter_rows()
            next(iterator)
            if operation == "source-close":
                connection.close()
            elif operation == "source-restart":
                connection.commit()
                connection.execute("BEGIN")
            elif operation == "view-close":
                view.close()
            else:
                view._state.connection.commit()
                view._state.connection.execute("BEGIN")
            with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError, sqlite3.Error)):
                next(iterator)
            with pytest.raises(StorageIntegrityError):
                prefix.assert_intact()
        finally:
            prefix.close()
            view.close()


@pytest.mark.parametrize("field,value", [
    (0, "0" * 64), (1, canonical_timestamp(NOW-timedelta(hours=2))),
    (2, "espn:tennis:ATP:match:999"), (3, "0" * 64), (4, "unknown"),
    (5, 2049), (6, "0" * 64), (7, b"{}"),
])
def test_invalid_locator_or_resolved_identity_poison_public_reader(tmp_path, monkeypatch, field, value):
    # Inject corruption at the private record boundary, keeping the real source
    # owner, its actual SQL, decoder, selector and original resolver intact.
    import context_storage_v2.history as implementation
    db = large_source(tmp_path)
    with source(db) as (_, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048)) as view:
            original = implementation._resolve_row
            def damaged(source_owner, stored, **kwargs):
                changed = list(stored)
                changed[field] = value
                return original(source_owner, tuple(changed), **kwargs)
            with monkeypatch.context() as patch:
                patch.setattr(implementation, "_resolve_row", damaged)
                with pytest.raises(StorageIntegrityError):
                    next(view.iter_rows())
            with pytest.raises(StorageIntegrityError):
                view.assert_intact()


def test_large_canonical_bytes_not_locator_size_charge_full_tour_budget(tmp_path):
    db = large_source(tmp_path)
    with source(db) as (_, receipts):
        expected = _cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        size = sum(len(canonical_bytes(row)) for row in expected)
        with pytest.raises(StorageLimitError):
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048, tour_history_bytes=size-1))
        assert list(tmp_path.glob("context-history-*/history.sqlite"))
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048, tour_history_bytes=size)) as view:
            assert_history(view, expected)


def test_even_framing_hash_updates_obey_tightened_processing_blocks(tmp_path, monkeypatch):
    import context_storage_v2.history as implementation
    db = large_source(tmp_path)
    largest_update = 0
    class MeasuredHash:
        def __init__(self):
            self.actual = hashlib.sha256()
        def update(self, data):
            nonlocal largest_update
            largest_update = max(largest_update, len(data))
            self.actual.update(data)
        def hexdigest(self):
            return self.actual.hexdigest()
    # Measure actual calls while retaining the real SHA implementation/results.
    monkeypatch.setattr(implementation, "hashlib", SimpleNamespace(sha256=MeasuredHash))
    with source(db) as (_, receipts):
        expected = _cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=4)) as view:
            assert_history(view, expected)
            with view.as_of(NOW) as prefix:
                assert_history(prefix, expected)
    assert largest_update <= 4


@pytest.mark.parametrize("phase", ["before", "after"])
def test_source_restart_during_resolver_cannot_yield_partial_success(tmp_path, monkeypatch, phase):
    import context_storage_v2.history as implementation
    db = large_source(tmp_path)
    with source(db) as (connection, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048)) as view:
            original = implementation._resolve_row
            def interrupted(*args, **kwargs):
                if phase == "before":
                    connection.commit()
                    connection.execute("BEGIN")
                result = original(*args, **kwargs)
                if phase == "after":
                    connection.commit()
                    connection.execute("BEGIN")
                return result
            monkeypatch.setattr(implementation, "_resolve_row", interrupted)
            with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError)):
                next(view.iter_rows())
            with pytest.raises(StorageIntegrityError):
                view.assert_intact()


def test_build_end_resolves_and_rejects_invalid_large_identity_before_publication(tmp_path, monkeypatch):
    import context_storage_v2.history as implementation
    db = large_source(tmp_path)
    original = implementation._resolve_row
    def damaged(owner, stored, **kwargs):
        changed = list(stored)
        changed[6] = "0" * 64
        return original(owner, tuple(changed), **kwargs)
    monkeypatch.setattr(implementation, "_resolve_row", damaged)
    with source(db) as (_, receipts):
        with pytest.raises(StorageIntegrityError):
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048))
    retained = list(tmp_path.glob("context-history-*/history.sqlite"))
    assert len(retained) == 1
    with sqlite3.connect(retained[0].as_uri() + "?mode=ro", uri=True) as check:
        assert check.execute("SELECT count(*) FROM sqlite_schema").fetchone() == (0,)


def test_reference_budget_failure_closes_live_ref_cursor_before_writer(tmp_path, monkeypatch):
    # Removing the old row cap exposes a real downstream ref-budget failure;
    # its suspended reference cursor must not outlive the rolled-back writer.
    db = large_source(tmp_path)
    unraisable = []
    with source(db) as (_, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                input_identity=file_hash(db), main_cap_bytes=MAIN_CAP,
                limits=StorageLimits(block_bytes=2048)) as view:
            monkeypatch.setattr(sys, "unraisablehook", unraisable.append)
            try:
                tennis_features_streaming(event(), view, base(), cutoff=NOW,
                    work_directory=tmp_path, main_cap_bytes=MAIN_CAP,
                    limits=StorageLimits(block_bytes=1))
            except StorageLimitError:
                pass
            else:
                pytest.fail("reference-budget failure returned a partial feature result")
            gc.collect()
            assert not unraisable
            view.assert_intact()
