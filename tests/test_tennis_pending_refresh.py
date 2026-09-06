from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import tennis_daily as daily
from tennis import shadow


NOW = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)
START = NOW+timedelta(hours=6)


def prediction(p=.62):
    return SimpleNamespace(
        player_a="Alpha", player_b="Beta", surface="Hard", best_of=5,
        p_a_raw=p, p_a_cal=p, gates=[], verdict="KEINE WETTE",
        recommended_side=None, recommended_edge=0.,
        market_summary=lambda: {"p_a_cal":p, "p_b_cal":1-p},
        context_evidence={"model_inputs":{"indoor":True}},
    )


def store(path, when=NOW-timedelta(hours=3)):
    return shadow.store_prediction(
        "2030-01-02", "ATP", "Test Open", prediction(), odds_a=1.8, odds_b=2.1,
        provider_event_id="123", fixture_source="ESPN", scheduled_start_utc=START.isoformat(),
        modeled_at=when, db_path=path,
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path/"refresh.db"
    monkeypatch.setattr(shadow,"DB_PATH",tmp_path/"unrelated-global.db")
    monkeypatch.setattr(daily,"load_state",lambda: SimpleNamespace(stats_through="2029-12-30"))
    monkeypatch.setattr(daily.requests,"get",lambda *a,**k: pytest.fail("refresh must not request providers"))
    return path


def test_refresh_appends_one_shared_revision_preserving_first_prediction_and_prices(db, monkeypatch):
    initial_id = store(db)
    seen = []
    def predict(state,a,b,surface,best_of,**kwargs):
        seen.append((a,b,surface,best_of,kwargs))
        return prediction(.57)
    monkeypatch.setattr(daily,"predict_match",predict)
    result = daily.refresh_pending_predictions(db_path=db,as_of=NOW)
    assert result["status"] == "complete"
    assert result["refreshed"] == 1
    assert result["provider_checked"] is False
    assert result["model_stats_through"] == "2029-12-30"
    assert seen[0][:4] == ("Alpha","Beta","Hard",5)
    assert seen[0][4]["indoor"] is True
    assert seen[0][4]["as_of"] == NOW
    assert seen[0][4]["workload_history"] == []
    latest = shadow.latest_predictions(db,as_of=NOW)[0]
    assert latest["id"] == initial_id
    assert latest["p_cal"] == .57
    assert latest["odds_a"] is None
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("SELECT p_cal,odds_a FROM predictions").fetchone() == (.62,1.8)
        assert conn.execute("SELECT COUNT(*) FROM prediction_revisions").fetchone()[0] == 2
    assert not shadow.DB_PATH.exists()
    assert daily.refresh_pending_predictions(db_path=db,as_of=NOW+timedelta(minutes=30))["refreshed"] == 0


def test_recent_or_missing_fixture_does_not_load_state_or_create_db(db, monkeypatch):
    monkeypatch.setattr(daily,"load_state",lambda: pytest.fail("no due fixture, no state load"))
    assert daily.refresh_pending_predictions(db_path=db,as_of=NOW)["checked"] == 0
    assert not db.exists()
    store(db,NOW-timedelta(minutes=5))
    assert daily.refresh_pending_predictions(db_path=db,as_of=NOW)["due"] == 0


def test_state_failure_preserves_previous_revision_and_never_rebuilds(db, monkeypatch):
    store(db)
    def missing():
        raise FileNotFoundError("missing cached state")
    monkeypatch.setattr(daily,"load_state",missing)
    import tennis.model_state
    monkeypatch.setattr(tennis.model_state,"build_state",lambda: pytest.fail("lightweight refresh must not build"))
    result = daily.refresh_pending_predictions(db_path=db,as_of=NOW)
    assert result["status"] == "unavailable"
    assert result["errors"][0]["error_type"] == "FileNotFoundError"
    assert shadow.latest_predictions(db,as_of=NOW)[0]["p_cal"] == .62


def test_runtime_model_clock_is_captured_after_reads_and_does_not_refresh_started_match(db, monkeypatch):
    store(db)
    calls = []
    clocks = iter((NOW,NOW+timedelta(seconds=10),NOW+timedelta(seconds=11),NOW+timedelta(seconds=12)))
    monkeypatch.setattr(daily,"_refresh_now",lambda: next(clocks))
    def predict(*args,**kwargs):
        calls.append(kwargs["as_of"])
        return prediction(.57)
    monkeypatch.setattr(daily,"predict_match",predict)
    assert daily.refresh_pending_predictions(db_path=db)["refreshed"] == 1
    assert calls == [NOW+timedelta(seconds=10)]
    monkeypatch.setattr(daily,"predict_match",lambda *a,**k: pytest.fail("event already started"))
    assert daily.refresh_pending_predictions(db_path=db,as_of=START)["refreshed"] == 0


def test_match_start_during_model_computation_prevents_late_append(db, monkeypatch):
    store(db)
    clocks = iter((NOW,START-timedelta(seconds=1),START,START+timedelta(seconds=1)))
    monkeypatch.setattr(daily,"_refresh_now",lambda: next(clocks))
    monkeypatch.setattr(daily,"predict_match",lambda *a,**k: prediction(.57))
    result = daily.refresh_pending_predictions(db_path=db)
    assert result["refreshed"] == 0
    assert result["skipped"] == 1
    assert shadow.latest_predictions(db,as_of=START)[0]["p_cal"] == .62


def test_invalid_metadata_is_reported_without_guessing_or_loading_state(db, monkeypatch):
    store(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TABLE prediction_revisions")
        conn.execute("UPDATE predictions SET provider_event_id=NULL")
    monkeypatch.setattr(daily,"load_state",lambda: pytest.fail("invalid identity"))
    result = daily.refresh_pending_predictions(db_path=db,as_of=NOW)
    assert result["due"] == 0
    assert result["errors"] == [{"prediction_id":1,"reason":"invalid_fixture_metadata"}]


def test_bad_cutoff_and_interval_are_not_silently_normalized(db):
    with pytest.raises(ValueError,match="timezone-aware"):
        daily.refresh_pending_predictions(db_path=db,as_of=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError,match="non-negative"):
        daily.refresh_pending_predictions(db_path=db,as_of=NOW,minimum_interval=timedelta(seconds=-1))
