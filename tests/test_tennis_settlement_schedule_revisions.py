"""A moved tennis start does not change the frozen native sporting event."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3

import pytest

from riskobet_domain import (
    ContextState, EvidenceStage, EventModelSnapshot, FactorEvidence, FactorRole,
    RiskCandidate, RiskRunSnapshot, RunStatus, canonical_input_hash, stable_event_key,
)
import riskobet_settlement_automation as automation
from riskobet_store import RiskBetStore


MODELED = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
OLD_START = MODELED + timedelta(hours=8)
NEW_START = OLD_START + timedelta(hours=1)
NOW = NEW_START + timedelta(hours=2)


def append_run(store, *, policy="riskobet-selection-v1", start=OLD_START,
               modeled=MODELED, prediction_ids=(1269,), label="A vs B",
               provider="ESPN", event_id="182682", tag="initial",
               markets=(("match_winner", "home"),)):
    event_key = stable_event_key("tennis", provider, event_id)
    snapshot = EventModelSnapshot(
        event_key=event_key, sport="tennis", competition="Test", event_label=label,
        starts_at=start, modeled_at=modeled, input_cutoff_at=modeled,
        model_version="tennis-test-v1",
        input_hash=canonical_input_hash({"start": start.isoformat(), "tag": tag}),
        factors=tuple(FactorEvidence(
            factor_key=f"tennis_prediction_id:{prediction_id}",
            summary="Frozen source identity", source="tennis_shadow.predictions",
            observed_at=modeled, imported_at=modeled, fresh_until=start,
            role=FactorRole.DISPLAY_ONLY,
        ) for prediction_id in prediction_ids),
    )
    candidates = tuple(RiskCandidate(
        snapshot_id=snapshot.snapshot_id, event_key=event_key, sport="tennis",
        competition="Test", event_label=label, starts_at=start,
        market_key=market, market_label=market, selection_key=selection,
        selection_label=selection, model_probability=.30, cautious_probability=.25,
        stage=EvidenceStage.SHADOW, context_state=ContextState.PARTIAL,
        policy_version=policy, pros=("Recorded model",), cons=("Uncertain outcome",),
        settlement_contract=f"riskobet-settlement-v1:tennis:{market}:{selection}",
    ) for market, selection in markets)
    run = RiskRunSnapshot(
        started_at=modeled, completed_at=modeled + timedelta(minutes=1),
        status=RunStatus.COMPLETE, snapshots=(snapshot,), candidates=candidates,
    )
    store.append_run(run)
    store.publish_latest(run.run_id)
    return run


def moved_runs(store, **new_changes):
    old = append_run(store)
    changes = dict(policy="riskobet-evidence-order-v2", start=NEW_START,
                   modeled=MODELED + timedelta(hours=1), tag="moved")
    changes.update(new_changes)
    return old, append_run(store, **changes)


def result_database(tmp_path, *, observed=NOW - timedelta(minutes=10), unique_id=True, **changes):
    path = tmp_path / "tennis.db"
    row = dict(id=1269, settled=1, player_a="A", player_b="B",
               provider_event_id="182682", fixture_source="ESPN", actual_winner="B",
               ret_flag=0, termination="normal", result_observed_at=observed.isoformat(),
               player_a_sets=1, player_b_sets=2)
    row.update(changes)
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"CREATE TABLE predictions (id INTEGER {'PRIMARY KEY' if unique_id else ''}, settled INTEGER, "
            "player_a TEXT, player_b TEXT, provider_event_id TEXT, fixture_source TEXT, "
            "actual_winner TEXT, ret_flag INTEGER, termination TEXT, "
            "result_observed_at TEXT, player_a_sets INTEGER, player_b_sets INTEGER)"
        )
        connection.execute("INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           tuple(row.values()))
    return path


def frozen_rows(store):
    with sqlite3.connect(store.db_path) as connection:
        return {table: tuple(sorted(connection.execute(f"SELECT * FROM {table}").fetchall()))
                for table in ("runs", "snapshots", "candidates", "run_candidates",
                              "run_snapshots", "stage_events")}


def terminal_rows(store):
    with sqlite3.connect(store.db_path) as connection:
        return connection.execute(
            "SELECT candidate_id,snapshot_id,result,settled_at,detail_json "
            "FROM settlements ORDER BY candidate_id"
        ).fetchall()


def run_with_source(store, source, *, loader_calls=None, now=NOW):
    load = automation.tennis_result_loader(source)
    def counted(requests, observed_at):
        if loader_calls is not None:
            loader_calls.append(requests)
        return load(requests, observed_at)
    return automation.run_riskobet_settlements(
        store=store, now=now, result_loaders={"tennis": counted},
    )


@pytest.mark.parametrize("different_contract", [False, True])
def test_moved_native_event_loads_once_and_preserves_each_frozen_contract(tmp_path, different_contract):
    store = RiskBetStore(tmp_path / "riskobet.db")
    markets = (("over_2_5_sets", "over"),) if different_contract else (("match_winner", "home"),)
    old, new = moved_runs(store, markets=markets)
    source = result_database(tmp_path)
    before = frozen_rows(store)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    calls = []
    summary = run_with_source(store, source, loader_calls=calls)
    assert summary.errors == ()
    assert (summary.due_events, summary.terminal_settlements, summary.unresolved_candidates) == (1, 2, 0)
    assert len(calls) == 1 and len(calls[0]) == 1
    assert set(calls[0][0].candidate_ids) == {old.candidates[0].candidate_id, new.candidates[0].candidate_id}
    settled = {row[0]: row for row in terminal_rows(store)}
    assert settled[old.candidates[0].candidate_id][1:3] == (old.snapshots[0].snapshot_id, "LOST")
    assert settled[new.candidates[0].candidate_id][1:3] == (
        new.snapshots[0].snapshot_id, "WON" if different_contract else "LOST")
    assert all(json.loads(row[4])["context"]["source_result_id"] == "tennis-shadow:prediction:1269"
               for row in settled.values())
    assert frozen_rows(store) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    terminal_before = terminal_rows(store)
    repeat_calls = []
    repeated = run_with_source(store, source, loader_calls=repeat_calls, now=NOW + timedelta(minutes=30))
    assert repeated.terminal_settlements == 0 and repeated.errors == ()
    assert repeat_calls == [] and terminal_rows(store) == terminal_before
    assert frozen_rows(store) == before


@pytest.mark.parametrize("observed,expected", [
    (OLD_START - timedelta(seconds=1), 0),
    (OLD_START, 1),
    (NEW_START - timedelta(microseconds=1), 1),
    (NEW_START, 2),
    (NOW + timedelta(microseconds=1), 0),
])
def test_result_time_is_checked_before_each_individual_candidate_write(tmp_path, monkeypatch, observed, expected):
    store = RiskBetStore(tmp_path / "riskobet.db")
    old, new = moved_runs(store)
    source = result_database(tmp_path, observed=observed)
    before = frozen_rows(store)
    append = store.append_terminal_settlement
    attempted = []
    def tracked_append(**kwargs):
        attempted.append(kwargs["candidate_id"])
        return append(**kwargs)
    monkeypatch.setattr(store, "append_terminal_settlement", tracked_append)
    summary = run_with_source(store, source)
    assert summary.terminal_settlements == expected
    assert summary.unresolved_candidates == 2 - expected
    assert len(attempted) == expected
    if expected == 1:
        assert attempted == [old.candidates[0].candidate_id]
        assert new.candidates[0].candidate_id not in attempted
    assert summary.errors == (() if expected == 2 else ("tennis:result_identity_or_time_invalid",))
    assert frozen_rows(store) == before


@pytest.mark.parametrize("changes", [
    {"prediction_ids": (1270,)}, {"prediction_ids": ()},
    {"prediction_ids": (1269, 1270)}, {"label": "B vs A"}, {"label": "A vs C"},
])
def test_schedule_exception_never_combines_conflicting_frozen_source_identity(tmp_path, changes):
    store = RiskBetStore(tmp_path / "riskobet.db")
    moved_runs(store, **changes)
    before = frozen_rows(store)
    def forbidden(*_args):
        pytest.fail("incompatible frozen identities must not reach a result source")
    summary = automation.run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"tennis": forbidden})
    assert summary.errors == ("tennis:event_snapshot_ambiguous",)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert terminal_rows(store) == [] and frozen_rows(store) == before


@pytest.mark.parametrize("changes", [
    {"id": 1270}, {"provider_event_id": "different-event"},
    {"fixture_source": "different-provider"}, {"player_a": "B", "player_b": "A"},
    {"player_b": "C"}, {"settled": 0},
])
def test_moved_event_still_requires_exact_source_row_event_and_orientation(tmp_path, changes):
    store = RiskBetStore(tmp_path / "riskobet.db")
    moved_runs(store)
    source = result_database(tmp_path, **changes)
    before = frozen_rows(store)
    calls = []
    summary = run_with_source(store, source, loader_calls=calls)
    assert len(calls) == 1 and len(calls[0]) == 1
    assert summary.errors == ("tennis:matching_settled_result_missing",)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert terminal_rows(store) == [] and frozen_rows(store) == before


def test_legacy_fallback_row_cannot_certify_a_changed_native_schedule(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    append_run(store, provider="tennis-shadow", event_id="shadow-1269")
    append_run(store, policy="riskobet-evidence-order-v2", start=NEW_START,
               modeled=MODELED + timedelta(hours=1), tag="moved",
               provider="tennis-shadow", event_id="shadow-1269")
    source = result_database(tmp_path, provider_event_id=None, fixture_source=None)
    summary = run_with_source(store, source)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert summary.errors == ("tennis:source_identity_unproven",)
    assert terminal_rows(store) == []


@pytest.mark.parametrize("provider,event_id", [
    ("tennis-shadow", "shadow-1269"),
    ("tennis-shadow", "182682"),
    ("ESPN", "shadow-1269"),
    (" TENNIS-SHADOW ", " SHADOW-1269 "),
])
def test_explicit_fallback_identity_is_not_native_for_a_moved_schedule(tmp_path, provider, event_id):
    store = RiskBetStore(tmp_path / "riskobet.db")
    append_run(store, provider=provider, event_id=event_id)
    append_run(store, provider=provider, event_id=event_id,
               policy="riskobet-evidence-order-v2", start=NEW_START,
               modeled=MODELED + timedelta(hours=1), tag="moved")
    source = result_database(tmp_path, fixture_source=provider, provider_event_id=event_id)
    before = frozen_rows(store)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    summary = run_with_source(store, source)
    assert summary.errors == ("tennis:source_identity_unproven",)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert terminal_rows(store) == [] and frozen_rows(store) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


def test_duplicate_source_results_remain_unresolved_for_all_schedule_revisions(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    moved_runs(store)
    source = result_database(tmp_path)
    load = automation.tennis_result_loader(source)
    calls = []
    def ambiguous(requests, now):
        calls.append(requests)
        batch = load(requests, now)
        assert len(batch.results) == 1
        return automation.ResultLoadBatch(results=batch.results * 2)
    summary = automation.run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"tennis": ambiguous})
    assert len(calls) == 1
    assert summary.errors == ("tennis:duplicate_event_result",)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert terminal_rows(store) == []


@pytest.mark.parametrize("contradictory", [False, True])
def test_duplicate_physical_source_rows_cannot_certify_schedule_identity(tmp_path, contradictory):
    store = RiskBetStore(tmp_path / "riskobet.db")
    moved_runs(store)
    source = result_database(tmp_path, unique_id=False)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO predictions SELECT * FROM predictions")
        if contradictory:
            connection.execute("UPDATE predictions SET actual_winner='A', player_a_sets=2, "
                               "player_b_sets=0 WHERE rowid=2")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    summary = run_with_source(store, source)
    assert summary.errors == ("tennis:duplicate_event_result",)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert terminal_rows(store) == []
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


@pytest.mark.parametrize("different_identity", [False, True])
@pytest.mark.parametrize("pending_row", [1, 2])
def test_pending_duplicate_source_row_cannot_be_filtered_out_of_identity_check(tmp_path, different_identity, pending_row):
    store = RiskBetStore(tmp_path / "riskobet.db")
    moved_runs(store)
    source = result_database(tmp_path, unique_id=False)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO predictions SELECT * FROM predictions")
        connection.execute("UPDATE predictions SET settled=0 WHERE rowid=?", (pending_row,))
        if different_identity:
            connection.execute("UPDATE predictions SET provider_event_id='other-native-event', "
                               "player_b='C' WHERE rowid=?", (pending_row,))
    before = frozen_rows(store)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    summary = run_with_source(store, source)
    assert summary.errors == ("tennis:duplicate_event_result",)
    assert summary.terminal_settlements == 0 and summary.unresolved_candidates == 2
    assert terminal_rows(store) == [] and frozen_rows(store) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


def test_equal_time_candidate_revision_ambiguity_is_not_repaired_by_schedule_handling(tmp_path):
    store = RiskBetStore(tmp_path / "riskobet.db")
    old = append_run(store)
    append_run(store, tag="ambiguous-equal-time")
    new = append_run(store, policy="riskobet-evidence-order-v2", start=NEW_START,
                     modeled=MODELED + timedelta(hours=1), tag="moved")
    source = result_database(tmp_path)
    before = frozen_rows(store)
    summary = run_with_source(store, source)
    assert summary.errors == ("automation:ambiguous_settlement_revisions",)
    assert summary.operational_error_count == 0
    assert summary.due_candidates == 2 and summary.unresolved_candidates == 1
    assert summary.terminal_settlements == 1
    assert {row[0] for row in terminal_rows(store)} == {new.candidates[0].candidate_id}
    assert old.candidates[0].candidate_id != new.candidates[0].candidate_id
    assert frozen_rows(store) == before
