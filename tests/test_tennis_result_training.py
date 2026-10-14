"""Confirmed native results bridge, using real temporary receipt stores."""
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
import sqlite3

import pandas as pd
import pytest

from context_sources import tennis_capture as capture
from tennis import tour_state
from test_context_tennis_outcome_capture import original_store, completed, record, RECEIVED


def training_frame(tour):
    if tour == "ATP":
        return pd.DataFrame([{"tourney_date": "2026-08-01", "winner_name": "Alpha A",
            "loser_name": "Beta B", "surface": "Hard", "match_ret": None, "tour": tour}])
    return pd.DataFrame([{"Date": "2026-08-01", "Winner": "Alpha A", "Loser": "Beta B",
        "Surface": "Hard", "Comment": "Completed", "tour": tour}])


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_confirmed_missing_result_changes_elo_without_fabricating_serve_or_rewriting_history(
        monkeypatch, tmp_path, tour):
    # Break caught: builder ignores a winner already confirmed in its own cache.
    db, shadow, _, origin = original_store(monkeypatch, tmp_path, tour=tour)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(event_id=origin["event"]["event_key"].rsplit(":", 1)[-1], winner=1), tour=tour)
    db_before, shadow_before = db.read_bytes(), shadow.read_bytes()
    cutoff = RECEIVED + timedelta(hours=1)
    monkeypatch.setattr(tour_state, "CONTEXT_MODEL_DB_PATH", db)
    monkeypatch.setattr(tour_state.time, "time", lambda: cutoff.timestamp())
    monkeypatch.setattr(tour_state, "load_atp_stats", lambda *a, **k: training_frame("ATP"))
    monkeypatch.setattr(tour_state, "load_market_odds", lambda *a, **k: training_frame("WTA"))
    monkeypatch.setattr(tour_state, "run_backtest", lambda **k: SimpleNamespace(rows=[]))
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("extra provider query"))
    diagnostics = {}
    state = tour_state.build_tour_state(tour, as_of=cutoff, refresh_training_data=False,
        diagnostics=diagnostics)
    assert state.elo.overall.matches("alpha a") == 2
    assert state.elo.overall.matches("beta b") == 2
    assert state.elo.overall.rating("beta b") > state.elo.overall.rating("alpha a")
    assert state.serve.to_payload()["rows"] == []
    assert state.stats_through == "2026-08-01"  # no invented complete-history coverage
    assert diagnostics["cached_results"]["added"] == 1
    assert db.read_bytes() == db_before and shadow.read_bytes() == shadow_before


def cached(db, *, cutoff=RECEIVED + timedelta(hours=1), tour="ATP"):
    from tennis.result_training import cached_elo_results
    return cached_elo_results(db, tour=tour, cutoff=cutoff,
        known_keys={"alpha a", "beta b"}, diagnostics={})


@pytest.mark.parametrize("change", ["missing-winner", "retired", "cancelled", "replacement", "doubles"])
def test_new_unusable_whole_reception_cannot_revive_an_earlier_winner(monkeypatch, tmp_path, change):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    later = RECEIVED + timedelta(minutes=1)
    raw = completed(winner=1)
    if change == "missing-winner":
        for player in raw["competitors"]: player.pop("winner")
    elif change == "retired": raw["notes"] = [{"text": "retired"}]
    elif change == "cancelled": raw["status"]["type"].update(state="post", name="STATUS_CANCELED")
    elif change == "replacement": raw["competitors"][1]["id"] = "3"
    from test_tennis_live_worker import response
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(winner=1))
        payload = response(raw)
        if change == "doubles": payload["events"][0]["groupings"][0]["grouping"]["slug"] = "mens-doubles"
        observer.record("atp", payload, observed_at=later)
    assert len(cached(db, cutoff=RECEIVED)) == 1
    assert cached(db, cutoff=later) == []


def test_repeat_receptions_count_once_but_true_correction_keeps_its_new_clock(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    later = RECEIVED + timedelta(minutes=1)
    for moment in (RECEIVED, later):
        with capture.capture_tennis_worker(path=db) as observer:
            record(observer, completed(winner=1), clock=moment)
    rows = cached(db)
    assert len(rows) == 1 and rows[0]["winner_key"] == "beta b"
    assert datetime.fromisoformat(rows[0]["result_observed_at"]) == RECEIVED
    correction = later + timedelta(minutes=1)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(winner=0), clock=correction)
    assert cached(db, cutoff=later)[0]["winner_key"] == "beta b"
    row, = cached(db, cutoff=correction)
    assert row["winner_key"] == "alpha a" and datetime.fromisoformat(row["result_observed_at"]) == correction


def test_conflicting_equal_clock_results_have_no_digest_tiebreak(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(winner=0))
        record(observer, completed(winner=1))
    assert cached(db) == []


@pytest.mark.parametrize("tour,date,want", [
    ("ATP", "2026-09-01", 0), ("ATP", "2026-08-01", 1),
    ("WTA", "2026-09-08", 0), ("WTA", "2026-08-01", 1),
])
def test_possible_csv_overlap_never_counts_a_second_result(tour, date, want):
    from tennis.result_training import missing_results
    # Reversed winner, different surface: pair/date overlap still excludes it.
    frame = pd.DataFrame([{"winner_key": "alpha a", "loser_key": "beta b",
        "date": pd.Timestamp(date, tz="UTC"), "surface": "Clay"}])
    result = {"event_key": "espn:tennis:ATP:match:201", "winner_key": "beta b",
        "loser_key": "alpha a", "scheduled_start": "2026-09-09T17:00:00+00:00"}
    assert len(missing_results(frame, [result], column="date", tour=tour, diagnostics={})) == want


def test_missing_result_store_remains_absent(tmp_path):
    db = tmp_path / "absent.db"
    assert cached(db) == [] and not db.exists()


def test_old_model_only_database_needs_no_receipt_migration(tmp_path):
    from test_tennis_live_worker import publish_state
    db = tmp_path / "old.db"
    publish_state(db)
    before = db.read_bytes()
    assert cached(db) == [] and db.read_bytes() == before


def test_original_database_with_missing_receipt_tables_is_not_silently_empty(monkeypatch, tmp_path):
    from context_models.contracts import ContextIntegrityError
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute("DROP TABLE context_observations")
    with pytest.raises(ContextIntegrityError):
        cached(db)


@pytest.mark.parametrize("change", ["unknown-key", "no-surface", "different-surface"])
def test_disagreeing_original_mappings_are_not_pruned_before_conflict_detection(monkeypatch, tmp_path, change):
    from model_artifacts import put_artifact
    from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND
    from test_tennis_live_worker import NOW
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    altered = deepcopy(origin)
    if change == "unknown-key": altered["inputs"]["state_key_a"] = "someone x"
    elif change == "no-surface": altered["inputs"]["surface"] = None
    else: altered["inputs"]["surface"] = "Clay"
    put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND, payload={"schema": 1, "origin": altered},
        created_at=NOW + timedelta(seconds=2))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    assert cached(db) == []


def test_orphan_state_reference_cannot_supply_player_mapping(monkeypatch, tmp_path):
    from context_models.contracts import ContextIntegrityError
    from model_artifacts import put_artifact
    from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND
    from test_tennis_live_worker import NOW
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    broken = deepcopy(origin)
    broken["state_hash"] = "9" * 64
    put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND, payload={"schema": 1, "origin": broken},
        created_at=NOW + timedelta(seconds=2))
    with pytest.raises(ContextIntegrityError):
        cached(db)


@pytest.mark.parametrize("broken", [None, "ATP", "WTA"])
def test_daily_pipeline_rebuilds_fresh_tours_from_cache_without_extra_downloads(
        monkeypatch, tmp_path, broken):
    import sys
    from scripts import rebuild_state
    from model_artifacts import load_manifest
    from test_tennis_training_refresh import _cli_scoped_state, NOW
    from datetime import timezone
    db = tmp_path / "models.db"
    previous = datetime.fromtimestamp(NOW, timezone.utc)
    assert tour_state.refresh_tours(path=db, as_of=previous,
        builder=lambda tour: _cli_scoped_state(tour, rebuild_state.POINT_MODEL_VERSION),
        publication_clock=lambda: previous)["status"] == "complete"
    before = load_manifest(db)[1]
    later = previous + timedelta(days=1)
    def build(tour, *, as_of, refresh_training_data, diagnostics):
        if refresh_training_data:
            pytest.fail("Fresh daily Elo update requested additional source downloads")
        if tour == broken:
            raise OSError("cache unavailable")
        result = _cli_scoped_state(tour, rebuild_state.POINT_MODEL_VERSION)
        result.built_at = later.timestamp()
        result.elo.update("alpha a", "beta b", "Hard")
        diagnostics["cached_results"] = {"added": 1}
        return result
    monkeypatch.setattr(rebuild_state, "build_tour_state", build)
    monkeypatch.setattr(rebuild_state, "CONTEXT_MODEL_DB_PATH", db)
    monkeypatch.setattr(rebuild_state.time, "time", lambda: later.timestamp())
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--if-stale-days", "7"])
    assert rebuild_state.main() == (1 if broken else 0)
    after = load_manifest(db)[1]
    for tour in ("ATP", "WTA"):
        if tour == broken:
            assert after["tennis:" + tour] == before["tennis:" + tour]
        else:
            assert after["tennis:" + tour] != before["tennis:" + tour]
            assert tour_state.load_tour_state(tour, path=db).elo.overall.matches("alpha a") == 1
    # Same UTC day must not repeatedly rebuild the unchanged cached models.
    if broken is None:
        assert rebuild_state.main() == 0
        assert load_manifest(db)[1] == after


def test_daily_cache_miss_cannot_fetch_or_create_a_cache_directory(monkeypatch, tmp_path):
    import sys
    from datetime import timezone
    from scripts import rebuild_state
    from model_artifacts import load_manifest
    from tennis import data_loader
    from test_tennis_training_refresh import _cli_scoped_state, NOW
    db = tmp_path / "models.db"
    previous = datetime.fromtimestamp(NOW, timezone.utc)
    tour_state.refresh_tours(path=db, as_of=previous,
        builder=lambda tour: _cli_scoped_state(tour, rebuild_state.POINT_MODEL_VERSION),
        publication_clock=lambda: previous)
    before = load_manifest(db)
    directory = tmp_path / "no-cache"
    def build(tour, **kwargs):
        data_loader._download("https://example.invalid/results.csv", directory / (tour + ".csv"))
        pytest.fail("missing cache was treated as a model")
    network = []
    def get(*args, **kwargs):
        network.append(args)
        raise RuntimeError("unexpected source fetch")
    monkeypatch.setattr(data_loader.requests, "get", get)
    monkeypatch.setattr(rebuild_state, "build_tour_state", build)
    monkeypatch.setattr(rebuild_state, "CONTEXT_MODEL_DB_PATH", db)
    monkeypatch.setattr(rebuild_state.time, "time", lambda: NOW + 86400)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--if-stale-days", "7"])
    assert rebuild_state.main() == 1
    assert not network and not directory.exists()
    assert load_manifest(db) == before


def test_cached_build_cannot_replace_a_newer_cutoff_with_equal_csv_coverage(tmp_path):
    from datetime import timezone
    from test_tennis_training_refresh import _cli_scoped_state, NOW
    from tennis.simulator import POINT_MODEL_VERSION
    start = datetime.fromtimestamp(NOW, timezone.utc)
    later, publication = start + timedelta(hours=2), start + timedelta(days=1)
    db = tmp_path / "models.db"
    def state(tour, built):
        result = _cli_scoped_state(tour, POINT_MODEL_VERSION)
        result.built_at = built.timestamp()
        return result
    tour_state.refresh_tours(path=db, as_of=start, builder=lambda tour: state(tour, start),
        publication_clock=lambda: start)
    def racing_builder(tour):
        if tour == "ATP":
            tour_state.refresh_tours(path=db, as_of=later, builder=lambda name: state(name, later),
                publication_clock=lambda: later)
        return state(tour, publication)
    result = tour_state.refresh_tours(path=db, as_of=start + timedelta(hours=1),
        builder=racing_builder, publication_clock=lambda: publication)
    assert result["status"] == "failed"
    for tour in ("ATP", "WTA"):
        assert tour_state.load_tour_state(tour, path=db).training_cutoff == later.isoformat()
