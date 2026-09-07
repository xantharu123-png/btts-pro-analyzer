from datetime import datetime, timedelta, timezone
from dataclasses import replace
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from copy import deepcopy
import sqlite3

import pandas as pd
import pytest

from model_artifacts import load_artifact, load_manifest, ManifestConflict
from tennis import tour_state, backtest
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel
from tennis.model_state import ModelState
from tennis.tour_state import training_years


def test_atp_publishes_even_when_wta_fails(tmp_path):
    from tennis.tour_state import refresh_tours, load_tour_state
    now = datetime(2027, 1, 2, tzinfo=timezone.utc)
    def builder(tour):
        if tour == "WTA":
            raise OSError("source unavailable")
        elo = SurfaceElo()
        elo.update("a", "b", "Hard")
        return ModelState(elo, ServeReturnModel(), 1., 0., 2000,
                          now.timestamp(), "2026-12-28", .3, tour_scope="ATP")
    result = refresh_tours(path=tmp_path / "models.db", as_of=now, builder=builder,
                           publication_clock=lambda: now)
    assert result["status"] == "partial"
    assert load_tour_state("ATP", path=tmp_path / "models.db").tour_scope == "ATP"
    assert training_years(now)[-1] == 2027


@pytest.mark.parametrize("cutoff,last", [
    (datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc), 2026),
    (datetime(2027, 1, 1, tzinfo=timezone.utc), 2027),
])
def test_training_years_cover_current_utc_season(cutoff, last):
    years = training_years(cutoff)
    assert years[0] == 2010
    assert years[-1] == last
    assert len(years) == last - 2009


def test_training_years_reject_naive_cutoff():
    with pytest.raises(ValueError):
        training_years(datetime(2027, 1, 1))


NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)


def state(tour, *, through="2026-12-28", built_at=NOW.timestamp()):
    elo = SurfaceElo()
    elo.update("alpha a", "beta b", "Hard")
    return ModelState(elo, ServeReturnModel(), 1., 0., 1, built_at, through,
                      .3 if tour == "ATP" else 0., tour_scope=tour,
                      stats_through_kind="tournament_start_proxy" if tour == "ATP" else "result_date")


def refresh(path, builder=state, **options):
    return tour_state.refresh_tours(path=path, as_of=NOW, builder=builder,
                                   publication_clock=lambda: NOW, **options)


@pytest.mark.parametrize("broken", ["ATP", "WTA", "both"])
def test_failures_preserve_each_existing_artifact_and_sanitize_errors(tmp_path, broken):
    path = tmp_path / "models.db"
    assert refresh(path)["status"] == "complete"
    old = load_manifest(path)[1]
    def builder(tour):
        if broken in (tour, "both"):
            raise OSError("secret=do-not-persist")
        return state(tour, through="2027-01-01")
    result = refresh(path, builder)
    assert result["status"] == ("failed" if broken == "both" else "partial")
    assert "secret" not in str(result)
    slots = load_manifest(path)[1]
    for tour in ("ATP", "WTA"):
        record = result["tours"][tour]
        if broken in (tour, "both"):
            assert slots[f"tennis:{tour}"] == old[f"tennis:{tour}"]
            assert record["artifact_hash"] == old[f"tennis:{tour}"]
            assert record["stats_through"] == "2026-12-28"
            assert record["error_type"] == "OSError"
        else:
            assert slots[f"tennis:{tour}"] != old[f"tennis:{tour}"]
            assert record["status"] == "published"


def test_missing_tour_never_silently_uses_other_tour(tmp_path):
    path = tmp_path / "models.db"
    def builder(tour):
        if tour == "ATP":
            raise OSError("down")
        return state(tour)
    assert refresh(path, builder)["status"] == "partial"
    with pytest.raises(tour_state.TourUnavailable):
        tour_state.load_tour_state("ATP", path=path)
    assert tour_state.load_tour_state("WTA", path=path).tour_scope == "WTA"
    with pytest.raises(ValueError):
        tour_state.load_tour_state("atp", path=path)


def test_all_fresh_skip_and_partial_stale_failure(tmp_path):
    path = tmp_path / "models.db"
    refresh(path, lambda tour: state(tour, through="2027-01-01"))
    before = load_manifest(path)
    def unavailable(tour):
        raise OSError("down")
    result = refresh(path, unavailable, if_stale_days=7)
    assert result["status"] == "complete"
    assert {r["status"] for r in result["tours"].values()} == {"retained_fresh"}
    assert load_manifest(path) == before


def test_coverage_regression_never_replaces_newer_coverage(tmp_path):
    path = tmp_path / "models.db"
    refresh(path, lambda tour: state(tour, through="2027-01-01"))
    before = load_manifest(path)
    result = refresh(path)
    assert result["status"] == "failed"
    assert load_manifest(path) == before


@pytest.mark.parametrize("mutation", [
    lambda s: replace(s, built_at=NOW.timestamp() + 1),
    lambda s: replace(s, built_at=NOW.timestamp() - 1),
    lambda s: replace(s, stats_through="2027-01-03"),
    lambda s: replace(s, cal_a=float("nan")),
    lambda s: replace(s, tour_scope="WTA" if s.tour_scope == "ATP" else "ATP"),
])
def test_invalid_states_do_not_create_artifacts(tmp_path, mutation):
    path = tmp_path / "models.db"
    result = refresh(path, lambda tour: mutation(state(tour)))
    assert result["status"] == "failed"
    assert load_manifest(path)[1] == {}
    with sqlite3.connect(path) as conn:
        assert conn.execute("select count(*) from artifacts").fetchone()[0] == 0


def test_real_elapsed_build_time_is_not_backdated(tmp_path):
    path = tmp_path / "models.db"
    completed = NOW + timedelta(minutes=3)
    result = tour_state.refresh_tours(
        path=path, as_of=NOW,
        builder=lambda tour: state(tour, built_at=completed.timestamp()),
        publication_clock=lambda: completed + timedelta(seconds=1))
    assert result["status"] == "complete"
    loaded = tour_state.load_tour_state("ATP", path=path)
    assert loaded.built_at == completed.timestamp()
    assert loaded.training_cutoff == NOW.isoformat()
    artifact = load_artifact(path, loaded.artifact_hash)
    assert artifact["kind"] == "tennis-tour-state"
    assert set(artifact["payload"]) == {"schema", "training_cutoff", "state"}
    assert artifact["payload"]["training_cutoff"] == NOW.isoformat()
    with sqlite3.connect(path) as conn:
        receipts = conn.execute("select created_at from artifacts").fetchall()
        assert all(datetime.fromisoformat(row[0]) > completed for row in receipts)


def test_clock_reversal_between_validation_and_cas_is_rejected(tmp_path):
    ticks = iter([NOW, NOW, NOW - timedelta(seconds=1), NOW, NOW, NOW - timedelta(seconds=1)])
    result = tour_state.refresh_tours(path=tmp_path / "models.db", as_of=NOW,
        builder=state, publication_clock=lambda: next(ticks))
    assert result["status"] == "failed"
    assert load_manifest(tmp_path / "models.db")[1] == {}


def test_cas_conflict_reloads_unrelated_slot_and_retries(tmp_path, monkeypatch):
    path = tmp_path / "models.db"
    publish = tour_state.publish_slots
    calls = []
    def conflicting(path, updates, **kwargs):
        calls.append(updates)
        if len(calls) == 1:
            raise ManifestConflict("other writer")
        return publish(path, updates, **kwargs)
    monkeypatch.setattr(tour_state, "publish_slots", conflicting)
    assert refresh(path)["status"] == "complete"
    assert len(calls) == 3
    assert set(load_manifest(path)[1]) == {"tennis:ATP", "tennis:WTA"}


def test_persistent_cas_conflict_is_bounded(tmp_path, monkeypatch):
    attempts = []
    def conflict(*args, **kwargs):
        attempts.append(1)
        raise ManifestConflict("changed")
    monkeypatch.setattr(tour_state, "publish_slots", conflict)
    assert refresh(tmp_path / "models.db")["status"] == "failed"
    assert len(attempts) == 8  # initial attempt plus at most three retries per tour


def market_frame(tour="wta"):
    return pd.DataFrame([
        {"Date": "2024-01-01", "Winner": "Alpha A", "Loser": "Beta B", "Surface": "Hard", "Tournament": "Test", "Best of": 3, "PSW": 2., "PSL": 2., "tour": tour.upper()},
        {"Date": "2024-06-01", "Winner": "Beta B", "Loser": "Alpha A", "Surface": "Hard", "Tournament": "Test", "Best of": 3, "PSW": 2., "PSL": 2., "tour": tour.upper()},
        {"Date": "2024-06-02", "Winner": "Future F", "Loser": "Beta B", "Surface": "Hard", "Tournament": "Test", "Best of": 3, "PSW": 2., "PSL": 2., "tour": tour.upper()},
    ])


def test_wta_calibration_cutoff_and_price_independence(monkeypatch):
    frame = market_frame()
    monkeypatch.setattr(backtest, "load_market_odds", lambda *a, **k: frame.copy())
    monkeypatch.setattr(backtest, "load_wta_ta_stats", lambda: pytest.fail("unused WTA serve source"))
    monkeypatch.setattr(backtest, "load_atp_stats", lambda *a, **k: pytest.fail("other tour"))
    cutoff = datetime(2024, 6, 1, tzinfo=timezone.utc)
    def run():
        return backtest.run_backtest((2024,), tours=("wta",), serve_weight=0.,
            recalibrate=False, end_cutoff=cutoff, calibration_only=True).rows
    original = run()
    assert len(original) == 2
    # First update: K=250/5**0.4, rating gap=K, logistic rounds to .6805.
    assert [r.p_alpha_raw for r in original] == [.5, .6805]
    assert [r.y_alpha for r in original] == [1, 0]
    for prices in (None, [float("nan"), -1., float("inf")], [1.01, 200., 5.]):
        if prices is None:
            frame = frame.drop(columns=["PSW", "PSL"])
        else:
            frame["PSW"] = prices
            frame["PSL"] = prices[::-1]
        assert run() == original


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_separate_builds_exclude_other_tour_future_and_retired_rows(monkeypatch, tour):
    monkeypatch.setattr(tour_state.time, "time", lambda: NOW.timestamp())
    frame = market_frame(tour.lower())
    frame.loc[2, "Date"] = "2027-01-03"
    frame.loc[1, "Comment"] = "Retired"
    def market(years, *, tour, **kwargs):
        assert tour == "wta"
        assert tuple(years)[-1] == 2027
        assert kwargs["current_year"] == 2027
        return frame
    def atp(years, **kwargs):
        assert tuple(years)[-1] == 2027
        assert kwargs["current_year"] == 2027
        return frame.rename(columns={"Date": "tourney_date", "Winner": "winner_name", "Loser": "loser_name", "Surface": "surface", "Comment": "match_ret"})
    monkeypatch.setattr(tour_state, "load_atp_stats", atp if tour == "ATP" else lambda *a, **k: pytest.fail("ATP contamination"))
    monkeypatch.setattr(tour_state, "load_market_odds", market if tour == "WTA" else lambda *a, **k: pytest.fail("WTA contamination"))
    def calibration(**kwargs):
        assert kwargs["tours"] == (tour.lower(),)
        assert kwargs["odds_years"] == (2022, 2023, 2024)
        assert kwargs["end_cutoff"] == NOW
        assert kwargs["calibration_only"] is True
        return SimpleNamespace(rows=[])
    monkeypatch.setattr(tour_state, "run_backtest", calibration)
    built = tour_state.build_tour_state(tour, as_of=NOW)
    assert built.tour_scope == tour
    assert built.elo.known_players() == {"alpha a", "beta b"}
    assert built.stats_through == "2024-01-01"
    assert built.training_cutoff == NOW.isoformat()
    if tour == "WTA":
        assert built.serve_weight == 0.
        assert built.serve.to_payload()["hold_avg"] == .706
        assert built.serve.to_payload()["rows"] == []


def test_future_training_cutoff_rejected_before_source_io(monkeypatch):
    monkeypatch.setattr(tour_state.time, "time", lambda: NOW.timestamp())
    monkeypatch.setattr(tour_state, "load_atp_stats", lambda *a, **k: pytest.fail("future source I/O"))
    with pytest.raises(ValueError):
        tour_state.build_tour_state("ATP", as_of=NOW + timedelta(seconds=1))


def test_clock_reversal_during_cas_retry_is_rejected(tmp_path, monkeypatch):
    ticks = iter([NOW, NOW, NOW + timedelta(seconds=3), NOW + timedelta(seconds=2), NOW])
    actual = tour_state.publish_slots
    attempts = []
    def conflict_once(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise ManifestConflict("changed")
        return actual(*args, **kwargs)
    def builder(tour):
        if tour == "WTA":
            raise OSError("down")
        return state(tour)
    monkeypatch.setattr(tour_state, "publish_slots", conflict_once)
    path = tmp_path / "models.db"
    result = tour_state.refresh_tours(path=path, as_of=NOW, builder=builder,
                                     publication_clock=lambda: next(ticks))
    assert result["status"] == "failed"
    assert load_manifest(path)[1] == {}
    assert len(attempts) == 1


def test_simultaneous_tour_writers_preserve_both_slots(tmp_path, monkeypatch):
    path = tmp_path / "models.db"
    load_manifest(path)
    barrier, thread = Barrier(2), local()
    actual = tour_state.publish_slots
    def overlapping(*args, **kwargs):
        if not getattr(thread, "waited", False):
            thread.waited = True
            barrier.wait(timeout=10)
        return actual(*args, **kwargs)
    monkeypatch.setattr(tour_state, "publish_slots", overlapping)
    def worker(healthy):
        def builder(tour):
            if tour != healthy:
                raise OSError("other source unavailable")
            return state(tour)
        return refresh(path, builder)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, ("ATP", "WTA")))
    assert [r["status"] for r in results] == ["partial", "partial"]
    assert set(load_manifest(path)[1]) == {"tennis:ATP", "tennis:WTA"}
    assert tour_state.load_tour_state("ATP", path=path).tour_scope == "ATP"
    assert tour_state.load_tour_state("WTA", path=path).tour_scope == "WTA"


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(schema=True),
    lambda p: p.update(extra="unexpected"),
    lambda p: p.update(training_cutoff="2027-01-02T13:00:00+01:00"),
    lambda p: p.update(training_cutoff="2027-01-03T12:00:00+00:00"),
    lambda p: p["state"].update(tour="WTA"),
])
def test_loading_validates_wrapper_even_when_registry_hash_is_valid(tmp_path, mutation):
    path = tmp_path / "models.db"
    refresh(path)
    manifest, slots = load_manifest(path)
    payload = deepcopy(load_artifact(path, slots["tennis:ATP"])["payload"])
    mutation(payload)
    digest = tour_state.put_artifact(path, kind="tennis-tour-state", payload=payload, created_at=NOW)
    tour_state.publish_slots(path, {"tennis:ATP": digest}, expected_manifest=manifest, published_at=NOW)
    with pytest.raises(ValueError):
        tour_state.load_tour_state("ATP", path=path)


@pytest.mark.parametrize("matches", [0, 1])
def test_finite_but_overflowing_predictions_cannot_publish(tmp_path, matches):
    def builder(tour):
        result = state(tour)
        payload = result.elo.to_payload()
        payload["overall"]["alpha a"][0] = -1.e300
        payload["overall"]["beta b"][0] = 1.e300
        payload["overall"]["alpha a"][1] = matches
        payload["overall"]["beta b"][1] = matches
        result.elo = SurfaceElo.from_payload(payload)
        return result
    assert refresh(tmp_path / "models.db", builder)["status"] == "failed"
    assert load_manifest(tmp_path / "models.db")[1] == {}


def test_backtest_default_preserves_price_eligibility_and_raw_rounding(monkeypatch):
    frame = market_frame().iloc[:2].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    monkeypatch.setattr(backtest, "load_market_odds", lambda *a, **k: frame.copy())
    monkeypatch.setattr(backtest, "load_wta_ta_stats", lambda: pytest.fail("unused serve dependency"))
    report = backtest.run_backtest((2024,), tours=("wta",), serve_weight=0., recalibrate=False)
    assert isinstance(report, backtest.BacktestReport)
    assert [r.p_alpha_raw for r in report.rows] == [.5, .6805]
    assert [r.odds_w for r in report.rows] == [2., 2.]
    frame.loc[0, "PSW"] = 1.
    report = backtest.run_backtest((2024,), tours=("wta",), serve_weight=0., recalibrate=False)
    assert len(report.rows) == 1
    assert report.rows[0].p_alpha_raw == .6805


def atp_boxscore(winner="Alpha A", *, day="2026-12-28", category="atp250"):
    return {"tourney_date": day, "tour": "ATP", "winner_name": winner,
            "loser_name": "Beta B", "surface": "Hard", "indoor_outdoor": "Indoor",
            "series_category_id": category, "win_service_games_played": 12.,
            "win_return_games_played": 10., "win_break_points_converted": 2.,
            "los_break_points_converted": 1., "los_service_games_played": 10.,
            "los_return_games_played": 12.}


def test_atp_retains_serve_tour_restriction_indoor_split_and_real_completion(monkeypatch):
    ticks = iter([NOW.timestamp(), NOW.timestamp() + 120])
    monkeypatch.setattr(tour_state.time, "time", lambda: next(ticks))
    frame = pd.DataFrame([atp_boxscore(), atp_boxscore("Challenger C", category="challenger")])
    monkeypatch.setattr(tour_state, "load_atp_stats", lambda *a, **k: frame)
    monkeypatch.setattr(tour_state, "run_backtest", lambda **k: SimpleNamespace(rows=[]))
    built = tour_state.build_tour_state("ATP", as_of=NOW)
    assert built.built_at == NOW.timestamp() + 120
    assert "challenger c" in built.elo.known_players()
    assert built.serve.service_games("challenger c") == 0.
    assert built.serve.service_games("alpha a") == 12.
    assert {r["bucket"] for r in built.serve.to_payload()["rows"]} == {"__overall__", "Hard@Indoor"}


def test_future_serve_observation_cannot_hide_under_old_coverage(tmp_path):
    def builder(tour):
        result = state(tour)
        if tour == "ATP":
            result.serve.update_from_match_row(atp_boxscore(day="2027-01-03"))
        else:
            raise OSError("down")
        return result
    assert refresh(tmp_path / "models.db", builder)["status"] == "failed"


@pytest.mark.parametrize("row", [
    SimpleNamespace(date="2027-01-03", tour="ATP", p_alpha_raw=.5, y_alpha=1),
    SimpleNamespace(date="2026-12-28", tour="WTA", p_alpha_raw=.5, y_alpha=1),
    SimpleNamespace(date="2026-12-28", tour="ATP", p_alpha_raw=float("nan"), y_alpha=1),
])
def test_invalid_calibration_inputs_reject_entire_build(monkeypatch, row):
    monkeypatch.setattr(tour_state.time, "time", lambda: NOW.timestamp())
    monkeypatch.setattr(tour_state, "load_atp_stats", lambda *a, **k: pd.DataFrame([atp_boxscore()]))
    monkeypatch.setattr(tour_state, "run_backtest", lambda **k: SimpleNamespace(rows=[row]))
    with pytest.raises(ValueError):
        tour_state.build_tour_state("ATP", as_of=NOW)


def test_publication_clock_is_checked_after_artifact_storage(tmp_path, monkeypatch):
    moment = NOW
    actual = tour_state.put_artifact
    def reversing_storage(*args, **kwargs):
        nonlocal moment
        digest = actual(*args, **kwargs)
        moment = NOW - timedelta(seconds=1)
        return digest
    monkeypatch.setattr(tour_state, "put_artifact", reversing_storage)
    path = tmp_path / "models.db"
    result = tour_state.refresh_tours(path=path, as_of=NOW, builder=state,
                                     publication_clock=lambda: moment)
    assert result["status"] == "failed"
    assert load_manifest(path)[1] == {}


def test_fresh_skip_rejects_state_with_nonfinite_prediction(tmp_path):
    path = tmp_path / "models.db"
    refresh(path, lambda tour: state(tour, through="2027-01-01"))
    manifest, slots = load_manifest(path)
    payload = deepcopy(load_artifact(path, slots["tennis:ATP"])["payload"])
    payload["state"]["elo"]["overall"]["alpha a"][0] = -1.e300
    payload["state"]["elo"]["overall"]["beta b"][0] = 1.e300
    digest = tour_state.put_artifact(path, kind="tennis-tour-state", payload=payload, created_at=NOW)
    tour_state.publish_slots(path, {"tennis:ATP": digest}, expected_manifest=manifest, published_at=NOW)
    result = refresh(path, lambda tour: pytest.fail("freshness must validate prediction"), if_stale_days=7)
    assert result["status"] == "partial"
    assert result["tours"]["ATP"]["status"] == "failed"
    assert result["tours"]["WTA"]["status"] == "retained_fresh"


def test_atp_calibration_bounds_stats_and_results_without_other_tour(monkeypatch):
    frame = market_frame("atp").iloc[1:].copy()
    stats = pd.DataFrame([atp_boxscore(day="2024-01-01"), atp_boxscore("Future F", day="2024-06-02")])
    monkeypatch.setattr(backtest, "load_atp_stats", lambda *a, **k: stats)
    monkeypatch.setattr(backtest, "load_market_odds", lambda *a, **k: frame)
    monkeypatch.setattr(backtest, "load_wta_ta_stats", lambda: pytest.fail("other tour"))
    report = backtest.run_backtest((2024,), tours=("atp",), serve_weight=0.,
        recalibrate=False, end_cutoff=datetime(2024, 6, 1, tzinfo=timezone.utc), calibration_only=True)
    assert len(report.rows) == 1
    assert report.rows[0].p_alpha_raw == .6805
    assert report.rows[0].y_alpha == 0


def test_nonfinite_serve_prediction_cannot_publish(tmp_path, monkeypatch):
    def builder(tour):
        if tour == "WTA":
            raise OSError("down")
        result = state(tour)
        result.serve.update_from_match_row(atp_boxscore())
        return result
    monkeypatch.setattr(ServeReturnModel, "expected_hold_probabilities", lambda *a, **k: (float("nan"), .7))
    result = refresh(tmp_path / "models.db", builder)
    assert result["status"] == "failed"
    assert load_manifest(tmp_path / "models.db")[1] == {}


def test_price_only_changes_cannot_change_separate_model_artifact_hash(tmp_path, monkeypatch):
    frame = market_frame()
    monkeypatch.setattr(tour_state.time, "time", lambda: NOW.timestamp())
    monkeypatch.setattr(tour_state, "load_market_odds", lambda *a, **k: frame.copy())
    monkeypatch.setattr(backtest, "load_market_odds", lambda *a, **k: frame.copy())
    monkeypatch.setattr(backtest, "load_atp_stats", lambda *a, **k: pytest.fail("ATP contamination"))
    monkeypatch.setattr(backtest, "load_wta_ta_stats", lambda *a, **k: pytest.fail("unused WTA serve"))
    def builder(tour):
        if tour == "ATP":
            raise OSError("down")
        return tour_state.build_tour_state(tour, as_of=NOW)
    path = tmp_path / "models.db"
    first = refresh(path, builder)["tours"]["WTA"]["artifact_hash"]
    assert first is not None
    frame = frame.drop(columns=["PSW", "PSL"])
    second = refresh(path, builder)["tours"]["WTA"]["artifact_hash"]
    assert second == first
    frame["PSW"] = [float("nan"), -1., 100.]
    frame["PSL"] = [1., float("inf"), 1.01]
    assert refresh(path, builder)["tours"]["WTA"]["artifact_hash"] == first


@pytest.mark.parametrize("surface", ["Hard", "Clay", "Grass", "Carpet"])
@pytest.mark.parametrize("surface_matches", [8, 10])
def test_inexperienced_surface_extrema_cannot_hide_overflow_before_storage(
        tmp_path, monkeypatch, surface, surface_matches):
    def builder(tour):
        result = state(tour)
        payload = result.elo.to_payload()
        payload["overall"] = {player: [1500., 20] for player in "abcd"}
        payload["by_surface"] = {name: {} for name in payload["by_surface"]}
        payload["by_surface"][surface] = {
            "a": [-1.e300, 0], "b": [1.e300, 0],
            "c": [-1.e200, surface_matches], "d": [1.e200, surface_matches],
        }
        result.elo = SurfaceElo.from_payload(payload)
        # The outer pair falls back safely; the eligible inner pair overflows.
        assert result.elo.win_probability("a", "b", surface) == .5
        with pytest.raises(OverflowError):
            result.elo.win_probability("c", "d", surface)
        return result

    monkeypatch.setattr(tour_state, "put_artifact",
                        lambda *a, **k: pytest.fail("invalid surface model reached artifact storage"))
    path = tmp_path / "models.db"
    result = refresh(path, builder)
    assert result["status"] == "failed"
    assert all(record["error_type"] == "OverflowError" for record in result["tours"].values())
    assert load_manifest(path)[1] == {}


def test_retry_does_not_overwrite_concurrently_improved_same_tour(tmp_path, monkeypatch):
    path = tmp_path / "models.db"
    actual = tour_state.publish_slots
    calls = []
    def improve_once(path, updates, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            newer = state("ATP", through="2027-01-01")
            payload = {"schema": 1, "training_cutoff": NOW.isoformat(),
                       "state": tour_state.encode_state(newer, tour="ATP")}
            digest = tour_state.put_artifact(path, kind="tennis-tour-state", payload=payload, created_at=NOW)
            actual(path, {"tennis:ATP": digest}, **kwargs)
            raise ManifestConflict("concurrent improvement")
        return actual(path, updates, **kwargs)
    def builder(tour):
        if tour == "WTA":
            raise OSError("down")
        return state(tour)
    monkeypatch.setattr(tour_state, "publish_slots", improve_once)
    result = refresh(path, builder)
    assert result["status"] == "failed"
    assert len(calls) == 1
    assert result["tours"]["ATP"]["stats_through"] == "2027-01-01"
    assert tour_state.load_tour_state("ATP", path=path).stats_through == "2027-01-01"
