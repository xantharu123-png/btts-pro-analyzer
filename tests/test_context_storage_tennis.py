"""Exact differential checks against real unchanged source/B6 owners, offline."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextContractError
from context_models.tennis_v3 import tennis_features_v3
from context_observations import _connect, append_observation
from context_runtime_tennis import _cold_replay_history
from context_storage_v2.contracts import StorageIntegrityError, StorageLimitError, StorageLimits
from context_storage_v2.history import build_history
from context_storage_v2.tennis import (
    MAX_MATERIALIZATION_BYTES, StreamingTennisFeatures, tennis_features_streaming,
)
from context_sources.tennis import normalize_tennis_workload
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_storage_history import source
from test_context_tennis_capture import NOW, competition, persist, records
from test_tennis_context_features import base, event, native_row


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty(db):
    connection = _connect(db)
    connection.close()


def _legacy(db, rows=None, *, clock=NOW-timedelta(hours=1)):
    normalized = normalize_tennis_workload(tuple(rows or [native_row("101")]), observed_at=clock)
    persist(db, normalized, clock=clock)


@contextmanager
def _opened(db, directory, *, ev=None, cutoff=NOW, basis=None, limits=None):
    ev = event() if ev is None else ev
    basis = base(ev, cutoff=cutoff) if basis is None else basis
    with source(db) as (connection, receipts):
        expected_history = _cold_replay_history(receipts, cutoff=cutoff, tour=ev["tour"], max_bytes=None)
        expected = tennis_features_v3(ev, expected_history, basis, cutoff=cutoff)
        with build_history(receipts, directory=directory, cutoff=cutoff, tour=ev["tour"], input_identity=_sha(db)) as view:
            with tennis_features_streaming(ev, view, basis, cutoff=cutoff, work_directory=directory,
                    **({"limits": limits} if limits is not None else {})) as actual:
                yield actual, expected, view, connection


def _same(db, directory, **kwargs):
    with _opened(db, directory, **kwargs) as (actual, expected, _, _):
        assert type(actual) is StreamingTennisFeatures and not isinstance(actual, dict)
        assert canonical_bytes(actual.materialize()) == canonical_bytes(expected)
        assert dict(actual.values) == expected["values"]
        assert dict(actual.states) == expected["states"]
        assert dict(actual.coverage) == expected["coverage"]
        assert actual.canonical_size == len(canonical_bytes(expected))
        assert actual.canonical_digest() == hashlib.sha256(canonical_bytes(expected)).hexdigest()
        assert b"".join(actual.iter_canonical_chunks()) == canonical_bytes(expected)
        for name, refs in expected["refs"].items():
            assert list(actual.iter_refs(name)) == refs
        return expected


@pytest.mark.parametrize("kind", ["empty", "legacy", "paired", "mixed", "unrelated", "wta", "walkover", "retired"])
def test_full_legacy_vector_and_streamed_canonical_digest_are_exact(tmp_path, kind):
    db = tmp_path / "source.db"
    _empty(db)
    ev = event()
    if kind in {"legacy", "mixed"}:
        _legacy(db, [native_row("101", sets=(3, 2), duration=300), native_row("102", "2", sets=(2, 0), duration=90)])
    if kind in {"paired", "mixed", "unrelated", "wta", "walkover", "retired"}:
        comp = competition(id="103", notes=[{"text": kind}] if kind in {"walkover", "retired"} else [])
        if kind == "unrelated":
            comp["competitors"][0]["id"], comp["competitors"][1]["id"] = "77", "88"
        if kind == "wta":
            ev = event(event_key="espn:tennis:WTA:match:999", tour="WTA",
                competition="espn:WTA:tournament:189-2026",
                home_id="espn:tennis:WTA:player:1", away_id="espn:tennis:WTA:player:2")
        at = NOW-timedelta(hours=1)
        persist(db, records(comp, clock=at, tour=ev["tour"], slug="womens-singles" if kind == "wta" else "mens-singles"), clock=at)
    _same(db, tmp_path, ev=ev)


@pytest.mark.parametrize("change", [
    {"status": {"type": {"state": "in", "completed": False, "name": "STATUS_IN_PROGRESS"}}},
    {"status": {"type": {"state": "post", "completed": True, "name": "STATUS_CANCELED"}}},
    {"status": {"type": {"state": "post", "completed": True, "name": "STATUS_ABANDONED"}}},
    {"competitors": []}, {"competitors": [{"id": None}, {"id": "9"}]},
    {"date": None}, {"date": "bad-time"}, {"status": None},
])
def test_every_new_defective_or_nonterminal_revision_retracts_exactly(tmp_path, change):
    db = tmp_path / "source.db"
    _legacy(db, clock=NOW-timedelta(hours=2))
    at = NOW-timedelta(hours=1)
    persist(db, records(competition(**change), clock=at), clock=at)
    actual = _same(db, tmp_path)
    assert actual["states"]["observed_sets_1d_a"] == "missing"


@pytest.mark.parametrize("kind", ["missing-pair", "crossed-pair", "extra-pair", "two-heads", "headless", "participant-change", "schedule-change"])
def test_revision_pair_selection_and_old_participant_coverage_match(tmp_path, kind):
    db = tmp_path / "source.db"
    _legacy(db, clock=NOW-timedelta(hours=2))
    at = NOW-timedelta(hours=1)
    comp = competition()
    if kind == "participant-change":
        comp["competitors"][0]["id"], comp["competitors"][1]["id"] = "3", "9"
    if kind == "schedule-change":
        comp["date"] = "2026-09-08T20:00Z"
    first = records(comp, clock=at)
    other_comp = competition()
    other_comp["competitors"][0]["linescores"][0]["value"] = 7
    second = records(other_comp, clock=at)
    rows = (first[:2] if kind == "missing-pair" else first[:2]+second[2:] if kind == "crossed-pair" else
            first+second[1:] if kind == "extra-pair" else first+second if kind == "two-heads" else
            first[1:] if kind == "headless" else first)
    persist(db, rows, clock=at)
    _same(db, tmp_path)


@pytest.mark.parametrize("kind", ["started", "cancelled", "participant-change", "schedule-change", "defective", "scheduled", "two-heads", "missing-head"])
def test_target_native_status_refs_and_override_match(tmp_path, kind):
    db = tmp_path / "source.db"
    _legacy(db)
    comp = competition(id="999", date=event()["scheduled_start"],
        status={"type": {"state": "pre", "completed": False, "name": "STATUS_SCHEDULED"}})
    if kind == "started":
        comp["status"] = {"type": {"state": "in", "completed": False, "name": "STATUS_IN_PROGRESS"}}
    elif kind == "cancelled":
        comp["status"] = {"type": {"state": "pre", "completed": False, "name": "STATUS_CANCELLED"}}
    elif kind == "participant-change":
        comp["competitors"][0]["id"] = "3"
    elif kind == "schedule-change":
        comp["date"] = "2026-09-09T19:00Z"
    elif kind == "defective":
        comp["competitors"] = []
    at = NOW-timedelta(minutes=30)
    persist(db, records(comp, clock=at), clock=at)
    if kind == "two-heads":
        comp["competitors"] = []
        persist(db, records(comp, clock=at), clock=at)
    if kind == "missing-head":
        _legacy(db, [native_row("999")], clock=NOW-timedelta(minutes=10))
    _same(db, tmp_path)


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_unknown_end_window_boundary_and_latest_recovery_are_exact(tmp_path, days, microseconds):
    db = tmp_path / "source.db"
    upper = NOW-timedelta(days=days)+timedelta(microseconds=microseconds)
    _legacy(db, [native_row("77", hours=300, actual_start_utc=None, actual_end_utc=None,
        match_duration_minutes=None, result_observed_at=upper.isoformat())], clock=upper)
    _legacy(db, [native_row("101", sets=(3, 2)), native_row("102", "2", sets=(2, 0))])
    _same(db, tmp_path)


@pytest.mark.parametrize("kind", ["partial", "conflicting-pair", "removed-old-player", "both-replaced"])
def test_legacy_latest_group_resolver_uses_whole_event_before_subject(tmp_path, kind):
    db = tmp_path / "source.db"
    _legacy(db, [native_row("101")], clock=NOW-timedelta(hours=2))
    at = NOW-timedelta(hours=1)
    rows = normalize_tennis_workload((native_row("101", sets=(3, 2)),), observed_at=at)
    if kind == "partial":
        rows = rows[:1]
    elif kind == "conflicting-pair":
        other = normalize_tennis_workload((native_row("101", sets=(2, 0)),), observed_at=at)
        rows = rows[:1]+other[1:]
    else:
        rows = normalize_tennis_workload((native_row("101", "3", "8" if kind == "both-replaced" else "9"),), observed_at=at)
    persist(db, rows, clock=at)
    _same(db, tmp_path)


@pytest.mark.parametrize("status", ["cancelled", "started", "completed"])
def test_inapplicable_event_remains_inapplicable_with_unknown_history(tmp_path, status):
    db = tmp_path / "source.db"
    _legacy(db)
    at = NOW-timedelta(minutes=10)
    persist(db, records(competition(competitors=[]), clock=at), clock=at)
    _same(db, tmp_path, ev=event(status=status))


def test_foreign_tour_future_backdated_and_same_time_rows_do_not_change_selected_order(tmp_path):
    db = tmp_path / "source.db"
    for ident, clock in (("302", NOW-timedelta(hours=1)), ("101", NOW-timedelta(hours=3)),
                         ("302", NOW), ("204", NOW+timedelta(microseconds=1))):
        persist(db, records(competition(id=ident), clock=clock), clock=clock)
    at = NOW-timedelta(hours=1)
    persist(db, records(competition(id="302", competitors=[]), clock=at, tour="WTA", slug="womens-singles"), clock=at)
    for cutoff in (NOW-timedelta(hours=2), NOW-timedelta(microseconds=1), NOW):
        _same(db, tmp_path, cutoff=cutoff)


def test_floating_sums_follow_original_python_sum_in_complete_event_order(tmp_path):
    db = tmp_path / "source.db"
    # All numbers are normalized, positive measured minutes. The exact order is
    # set by receipt clock, not native event key or insertion order. Python's
    # compensated sum can differ from repeated += on these inputs.
    for index, minutes in enumerate([1.] + [1e-16]*75 + [0.2, 0.1]):
        at = NOW-timedelta(minutes=100-index)
        raw = native_row(str(1000+index), actual_start_utc=(NOW-timedelta(days=2)).isoformat(),
                         match_duration_minutes=minutes)
        _legacy(db, [raw], clock=at)
    answer = _same(db, tmp_path)
    assert answer["values"]["observed_minutes_1d_a"] == sum([1.] + [1e-16]*75 + [0.2, 0.1])


def test_large_equal_time_conflict_group_never_enters_legacy_tuple_owner_unbounded(tmp_path, monkeypatch):
    import context_storage_v2.tennis as implementation
    db = tmp_path / "source.db"
    for index in range(125):
        _legacy(db, [native_row("101", match_duration_minutes=60.+index/100)], clock=NOW-timedelta(hours=1))
    original = implementation._usable_history
    sizes = []
    def bounded(rows, **kwargs):
        sizes.append(len(rows))
        assert type(rows) is tuple and len(rows) <= 2
        return original(rows, **kwargs)
    monkeypatch.setattr(implementation, "_usable_history", bounded)
    answer = _same(db, tmp_path)
    assert answer["states"]["observed_sets_1d_a"] == "conflicting"
    assert not sizes  # No arbitrary subset was accepted as a complete group.


@pytest.mark.parametrize("operation", ["commit", "rollback", "restart", "script", "close", "rowfactory", "textfactory", "callback", "override"])
def test_output_lifecycle_changes_permanently_invalidate_even_existing_ref_iterators(tmp_path, operation):
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, _, _, _):
        iterator = result.iter_refs("observed_recovery_minimum_hours_a")
        next(iterator)
        connection = result._connection
        if operation == "restart":
            connection.commit()
            connection.execute("BEGIN")
        elif operation == "script":
            connection.executescript("BEGIN;")  # SQLite first ends the old transaction.
        elif operation == "rowfactory":
            connection.row_factory = sqlite3.Row
        elif operation == "textfactory":
            connection.text_factory = bytes
        elif operation == "callback":
            with pytest.raises(StorageIntegrityError):
                connection.set_trace_callback(lambda *args: None)
        elif operation == "override":
            connection.execute = lambda *args, **kwargs: None
        else:
            getattr(connection, operation)()
        with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError, sqlite3.Error)):
            next(iterator)
        with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError, sqlite3.Error)):
            result.materialize()


@pytest.mark.parametrize("which", ["history", "source", "source-restart", "result"])
def test_result_never_outlives_owning_source_or_history(tmp_path, which):
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, _, history, connection):
        if which == "source-restart":
            connection.commit()
            connection.execute("BEGIN")
        else:
            {"history": history, "source": connection, "result": result}[which].close()
        with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError, sqlite3.Error)):
            result.canonical_digest()


def test_public_views_and_materialized_objects_cannot_mutate_result(tmp_path):
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, expected, _, _):
        with pytest.raises(TypeError):
            result.values["observed_sets_1d_a"] = -1
        with pytest.raises(StorageIntegrityError):
            result._header = b"{}"
        with pytest.raises(TypeError):
            result._refs["observed_sets_1d_a"] = None
        mutated = result.materialize()
        mutated["refs"]["observed_sets_1d_a"].clear()
        mutated["values"].clear()
        assert result.materialize() == expected
        assert not result._connection.execute("SELECT 1 FROM tennis_chosen WHERE 0").fetchall()
        with pytest.raises(sqlite3.OperationalError):
            result._connection.execute("DELETE FROM tennis_chosen")


def test_no_caller_constructed_result_or_partial_canonical_stream_survives_epoch_change(tmp_path):
    with pytest.raises(StorageIntegrityError):
        StreamingTennisFeatures()
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, _, _, _):
        chunks = result.iter_canonical_chunks()
        assert next(chunks) == b"{"
        result._connection.commit()
        result._connection.execute("BEGIN")
        with pytest.raises(StorageIntegrityError):
            next(chunks)


def test_published_output_is_really_readonly_even_after_pragma_guard_is_disabled(tmp_path):
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, _, _, _):
        connection = result._connection
        connection.execute("PRAGMA query_only=OFF")
        connection.execute("PRAGMA journal_mode=OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("CREATE TABLE unexpected(x TEXT)")
        connection.execute("PRAGMA query_only=ON")
        with pytest.raises(StorageIntegrityError):
            result.assert_intact()  # Changed journal policy is independently bound.


def test_temp_ddl_cannot_hide_between_queries_with_unchanged_total_changes(tmp_path):
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, _, _, _):
        connection = result._connection
        before = connection.total_changes
        connection.execute("PRAGMA query_only=OFF")
        connection.execute("CREATE TEMP TABLE unexpected(x TEXT)")
        connection.execute("PRAGMA query_only=ON")
        assert connection.total_changes == before
        with pytest.raises(StorageIntegrityError):
            result.assert_intact()


@pytest.mark.parametrize("change", ["attachment", "temp_journal", "cache", "max_pages", "mmap", "limits"])
def test_whole_published_storage_and_resource_binding_is_immutable(tmp_path, change):
    from context_storage_v2.contracts import DEFAULT_LIMITS
    db = tmp_path / "source.db"
    _legacy(db)
    limits = replace(DEFAULT_LIMITS)
    with _opened(db, tmp_path, limits=limits) as (result, _, _, _):
        connection = result._connection
        if change == "attachment":
            connection.execute("ATTACH ':memory:' AS unexpected")
        elif change == "temp_journal":
            connection.execute("PRAGMA temp.journal_mode=OFF")
        elif change == "cache":
            connection.execute("PRAGMA cache_size=-4194304")
        elif change == "max_pages":
            connection.execute("PRAGMA max_page_count=2147483646")
        elif change == "mmap":
            connection.execute("PRAGMA mmap_size=1073741824")
        else:
            # Even a formally valid new limit cannot replace the bound limit
            # under which this already published result was constructed.
            object.__setattr__(limits, "block_bytes", limits.block_bytes//2)
        with pytest.raises((StorageIntegrityError, StorageLimitError)):
            result.assert_intact()


def test_builder_failure_does_not_publish_or_leave_partial_output(tmp_path, monkeypatch):
    import context_storage_v2.tennis as implementation
    db = tmp_path / "source.db"
    _legacy(db)
    original = implementation._compute_header
    def broken(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("controlled interrupted feature build")
    with source(db) as (_, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(db)) as view:
            with monkeypatch.context() as scoped:
                scoped.setattr(implementation, "_compute_header", broken)
                with pytest.raises(RuntimeError, match="controlled interrupted"):
                    tennis_features_streaming(event(), view, base(), cutoff=NOW, work_directory=tmp_path)
            assert not list(tmp_path.glob("tennis-features-*"))
            with tennis_features_streaming(event(), view, base(), cutoff=NOW, work_directory=tmp_path) as result:
                assert result.values["observed_sets_1d_a"] == 3


def test_materialization_limit_rejects_whole_result_before_any_partial_refs(tmp_path, monkeypatch):
    db = tmp_path / "source.db"
    _legacy(db)
    with _opened(db, tmp_path) as (result, expected, _, _):
        size = len(canonical_bytes(expected))
        assert result.materialize(max_bytes=size) == expected
        with pytest.raises(StorageLimitError):
            result.materialize(max_bytes=size-1)
        assert result.materialize(max_bytes=size) == expected  # A tighter request isn't corruption.
        for invalid in (0, -1, True, 1.5, MAX_MATERIALIZATION_BYTES+1):
            with pytest.raises(StorageLimitError):
                result.materialize(max_bytes=invalid)


@pytest.mark.parametrize("which", ["tour", "block", "input", "workspace", "free"])
def test_component_caps_fail_without_returning_partial_feature_result(tmp_path, which):
    db = tmp_path / "source.db"
    _legacy(db)
    kwargs = {"tour_history_bytes": 1} if which == "tour" else {"block_bytes": 1} if which == "block" else (
        {"input_bytes": 1} if which == "input" else {"workspace_bytes": 1} if which == "workspace" else {"min_free_bytes": 2**63})
    with pytest.raises(StorageLimitError):
        with _opened(db, tmp_path, limits=StorageLimits(**kwargs)):
            pytest.fail("an over-budget result was published")


def test_wrong_cutoff_tour_raw_tuple_and_output_file_changes_are_rejected(tmp_path):
    db = tmp_path / "source.db"
    _legacy(db)
    with source(db) as (_, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(db)) as view:
            with pytest.raises(StorageIntegrityError):
                tennis_features_streaming(event(), tuple(view.iter_rows()), base(), cutoff=NOW, work_directory=tmp_path)
            earlier = NOW-timedelta(minutes=1)
            with pytest.raises(StorageIntegrityError):
                tennis_features_streaming(event(), view, base(cutoff=earlier), cutoff=earlier, work_directory=tmp_path)
            changed = event(tour="WTA")
            with pytest.raises(StorageIntegrityError):
                tennis_features_streaming(changed, view, base(changed), cutoff=NOW, work_directory=tmp_path)
    with _opened(db, tmp_path) as (result, _, _, _):
        with result._path.open("ab") as stream:
            stream.write(b"invalid trailing bytes")
        with pytest.raises(StorageIntegrityError):
            result.materialize()


def test_forged_limits_cannot_supply_their_own_validation_callback(tmp_path):
    from context_storage_v2.contracts import DEFAULT_LIMITS
    db = tmp_path / "source.db"
    _legacy(db)
    forged, called = replace(DEFAULT_LIMITS), []
    object.__setattr__(forged, "block_bytes", 2**30)
    object.__setattr__(forged, "__post_init__", lambda: called.append(True))
    with pytest.raises(StorageLimitError):
        with _opened(db, tmp_path, limits=forged):
            pytest.fail("untrusted validator widened the approved block budget")
    assert called == []


def test_dated_real_fixture_uses_measured_scores_without_invented_duration(tmp_path):
    db = tmp_path / "source.db"
    sample = json.loads((Path(__file__).parent/"fixtures/tennis_context_espn_20260907.json").read_text(encoding="utf-8"))
    from datetime import datetime
    at = datetime.fromisoformat(sample["received_at"])
    for comp in sample["examples"]:
        persist(db, records(comp, clock=at, tournament=comp["event_id"]), clock=at)
    _same(db, tmp_path)
