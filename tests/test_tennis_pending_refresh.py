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


def prediction(p=.62, artifact_hash="new-hash"):
    return SimpleNamespace(
        player_a="Alpha", player_b="Beta", surface="Hard", best_of=5,
        p_a_raw=p, p_a_cal=p, gates=[], verdict="KEINE WETTE",
        recommended_side=None, recommended_edge=0.,
        market_summary=lambda: {"p_a_cal":p, "p_b_cal":1-p},
        context_evidence={"model_inputs":{
            "indoor":True, "model_artifact_hash":artifact_hash,
        }},
    )


def store(
    path, when=NOW-timedelta(hours=3), *, tour="ATP", event_id="123",
    artifact_hash="old-hash",
):
    return shadow.store_prediction(
        "2030-01-02", tour, "Test Open", prediction(artifact_hash=artifact_hash),
        odds_a=1.8, odds_b=2.1,
        provider_event_id=event_id, fixture_source="ESPN", scheduled_start_utc=START.isoformat(),
        modeled_at=when, append_observed_at=when, db_path=path,
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path/"refresh.db"
    monkeypatch.setattr(shadow,"DB_PATH",tmp_path/"unrelated-global.db")
    monkeypatch.setattr(
        daily,
        "load_tour_state",
        lambda tour, **kwargs: SimpleNamespace(
            stats_through="2029-12-30" if tour == "ATP" else "2029-11-30",
            stats_through_kind=("tournament_start_proxy" if tour == "ATP" else "result_date"),
            built_at=(NOW - timedelta(days=1)).timestamp(),
            training_cutoff=(NOW - timedelta(days=2)).isoformat(),
            artifact_hash="new-hash",
            tour_scope=tour,
        ),
    )
    monkeypatch.setattr(daily.requests,"get",lambda *a,**k: pytest.fail("refresh must not request providers"))
    return path


def test_refresh_appends_one_shared_revision_preserving_first_prediction_and_prices(db, monkeypatch):
    initial_id = store(db)
    seen = []
    def predict(state,a,b,surface,best_of,**kwargs):
        seen.append((a,b,surface,best_of,kwargs))
        return prediction(.57)
    monkeypatch.setattr(daily,"predict_match",predict)
    result = daily.refresh_pending_predictions(
        db_path=db, as_of=NOW, append_observed_at=NOW,
    )
    assert result["status"] == "complete"
    assert result["refreshed"] == 1
    assert result["provider_checked"] is False
    assert result["models"]["ATP"]["stats_through"] == "2029-12-30"
    assert result["models"]["ATP"]["artifact_hash"] == "new-hash"
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


def test_missing_fixture_does_not_load_state_or_create_db(db, monkeypatch):
    monkeypatch.setattr(daily,"load_tour_state",lambda *a,**k: pytest.fail("no due fixture, no state load"))
    assert daily.refresh_pending_predictions(db_path=db,as_of=NOW)["checked"] == 0
    assert not db.exists()


def test_recent_fixture_with_same_artifact_is_not_due(db):
    store(db, NOW-timedelta(minutes=5), artifact_hash="new-hash")
    assert daily.refresh_pending_predictions(db_path=db,as_of=NOW)["due"] == 0


def test_artifact_change_refreshes_recent_fixture_without_price_revision(db, monkeypatch):
    initial_id = store(db, NOW - timedelta(minutes=5))
    monkeypatch.setattr(
        daily,
        "predict_match",
        lambda state, *args, **kwargs: prediction(.57, state.artifact_hash),
    )

    result = daily.refresh_pending_predictions(
        db_path=db, as_of=NOW, append_observed_at=NOW,
    )

    assert result["due"] == result["refreshed"] == 1
    latest = shadow.latest_predictions(db, as_of=NOW)[0]
    assert latest["id"] == initial_id
    assert latest["p_cal"] == .57
    assert latest["odds_a"] is None
    assert latest["created_utc"] == NOW.timestamp()
    assert latest["append_observed_at"] == NOW.isoformat()
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute(
            "SELECT odds_a,odds_b FROM predictions WHERE id=?", (initial_id,)
        ).fetchone() == (1.8, 2.1)
        assert conn.execute(
            "SELECT COUNT(*) FROM prediction_revisions"
        ).fetchone()[0] == 2


def test_missing_wta_state_keeps_atp_refresh_and_per_tour_diagnostics(db, monkeypatch):
    store(db, event_id="atp-event")
    store(db, tour="WTA", event_id="wta-event")
    loaded = []

    def load(tour, **kwargs):
        loaded.append((tour, kwargs))
        if tour == "WTA":
            raise FileNotFoundError("no WTA model")
        return SimpleNamespace(
            stats_through="2029-12-30",
            stats_through_kind="tournament_start_proxy",
            built_at=(NOW - timedelta(days=1)).timestamp(),
            training_cutoff=(NOW - timedelta(days=2)).isoformat(),
            artifact_hash="atp-new",
            tour_scope="ATP",
        )

    monkeypatch.setattr(daily, "load_tour_state", load)
    monkeypatch.setattr(
        daily,
        "predict_match",
        lambda state, *args, **kwargs: prediction(.57, state.artifact_hash),
    )

    result = daily.refresh_pending_predictions(
        db_path=db, as_of=NOW, append_observed_at=NOW,
    )

    assert [item[0] for item in loaded] == ["ATP", "WTA"]
    assert all(item[1]["decision_cutoff"] == NOW for item in loaded)
    assert all(item[1]["allow_legacy"] is False for item in loaded)
    assert result["status"] == "partial"
    assert result["refreshed"] == 1
    assert result["models"]["ATP"] == {
        "status": "available",
        "artifact_hash": "atp-new",
        "built_at": (NOW - timedelta(days=1)).isoformat(),
        "training_cutoff": (NOW - timedelta(days=2)).isoformat(),
        "stats_through": "2029-12-30",
        "stats_through_kind": "tournament_start_proxy",
        "tour_scope": "ATP",
    }
    assert result["models"]["WTA"] == {
        "status": "unavailable", "error_type": "FileNotFoundError",
    }
    assert result["errors"] == [{
        "tour": "WTA", "reason": "cached_tour_state_unavailable",
        "error_type": "FileNotFoundError",
    }]
    current = {row["tour"]: row for row in shadow.latest_predictions(db, as_of=NOW)}
    assert current["ATP"]["p_cal"] == .57
    assert current["WTA"]["p_cal"] == .62


def test_explicit_legacy_fallback_remains_labelled(db, monkeypatch):
    store(db)
    legacy = SimpleNamespace(
        stats_through="2029-10-01",
        stats_through_kind="tournament_start_proxy",
        built_at=(NOW - timedelta(days=10)).timestamp(),
        training_cutoff=None,
        artifact_hash="legacy-bytes",
        tour_scope="legacy-combined",
    )
    calls = []
    monkeypatch.setattr(
        daily,
        "load_tour_state",
        lambda tour, **kwargs: calls.append((tour, kwargs)) or legacy,
    )
    monkeypatch.setattr(
        daily, "predict_match",
        lambda state, *args, **kwargs: prediction(.57, state.artifact_hash),
    )

    result = daily.refresh_pending_predictions(
        db_path=db, as_of=NOW, allow_legacy_model=True,
        append_observed_at=NOW,
    )

    assert result["models"]["ATP"]["status"] == "legacy"
    assert result["models"]["ATP"]["tour_scope"] == "legacy-combined"
    assert result["models"]["ATP"]["artifact_hash"] == "legacy-bytes"
    assert calls == [("ATP", {
        "allow_legacy": True,
        "decision_cutoff": NOW,
    })]


def test_state_failure_preserves_previous_revision_and_never_rebuilds(db, monkeypatch):
    store(db)
    def missing(*args, **kwargs):
        raise FileNotFoundError("missing cached state")
    monkeypatch.setattr(daily,"load_tour_state",missing)
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


def test_pending_default_append_rechecks_start_inside_write(db, monkeypatch):
    store(db)
    clock = [NOW.timestamp()]
    original_store = shadow.store_prediction

    def begin_write_after_start(*args, **kwargs):
        clock[0] = (START + timedelta(seconds=1)).timestamp()
        return original_store(*args, **kwargs)

    monkeypatch.setattr(daily.time, "time", lambda: clock[0])
    monkeypatch.setattr(daily, "predict_match", lambda *args, **kwargs: prediction(.57))
    monkeypatch.setattr(shadow, "store_prediction", begin_write_after_start)

    result = daily.refresh_pending_predictions(db_path=db)

    assert result["refreshed"] == 0
    assert result["skipped"] == 1
    assert result["errors"] == []
    assert shadow.latest_predictions(db, as_of=START)[0]["p_cal"] == .62


def test_pending_stale_snapshot_cannot_rewind_concurrent_reschedule(
    db, monkeypatch,
):
    old_start = START
    new_start = START + timedelta(days=1)
    store(db)
    clock = [NOW.timestamp()]

    def concurrent_reschedule(*args, **kwargs):
        changed_at = NOW + timedelta(seconds=1)
        clock[0] = changed_at.timestamp()
        shadow.store_prediction(
            new_start.date().isoformat(), "ATP", "Test Open",
            prediction(.66), provider_event_id="123", fixture_source="ESPN",
            scheduled_start_utc=new_start.isoformat(), modeled_at=changed_at,
            append_observed_at=changed_at, db_path=db,
        )
        clock[0] = (NOW + timedelta(seconds=2)).timestamp()
        return prediction(.57)

    monkeypatch.setattr(daily.time, "time", lambda: clock[0])
    monkeypatch.setattr(daily, "predict_match", concurrent_reschedule)

    result = daily.refresh_pending_predictions(db_path=db)

    assert result["refreshed"] == 0
    assert result["skipped"] == 1
    assert result["errors"] == []
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute(
            "SELECT match_date,scheduled_start_utc FROM predictions"
        ).fetchone() == (new_start.date().isoformat(), new_start.isoformat())
        assert connection.execute(
            "SELECT COUNT(*) FROM prediction_revisions"
        ).fetchone()[0] == 2
    latest = shadow.latest_predictions(
        db, as_of=NOW + timedelta(seconds=2)
    )[0]
    assert latest["scheduled_start_utc"] == new_start.isoformat()
    assert latest["p_cal"] == .66


def test_observed_cancellation_during_model_computation_prevents_append(db, monkeypatch):
    store(db)

    def cancel_before_append(*args, **kwargs):
        shadow.record_fixture_status(
            fixture_source="ESPN",
            provider_event_id="123",
            status="cancelled",
            observed_at=NOW + timedelta(seconds=1),
            db_path=db,
        )
        return prediction(.57)

    monkeypatch.setattr(daily, "predict_match", cancel_before_append)
    result = daily.refresh_pending_predictions(db_path=db, as_of=NOW)

    assert result["refreshed"] == 0
    assert result["skipped"] == 1
    assert result["errors"] == []
    assert shadow.latest_predictions(db, as_of=NOW)[0]["p_cal"] == .62
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM prediction_revisions"
        ).fetchone()[0] == 1


def test_fixture_status_is_monotonic_and_unknown_is_not_invented(db):
    assert shadow.latest_fixture_status(
        fixture_source="ESPN", provider_event_id="unknown", db_path=db
    ) is None

    shadow.record_fixture_status(
        fixture_source="ESPN", provider_event_id="123", status="scheduled",
        observed_at=NOW, db_path=db,
    )
    shadow.record_fixture_status(
        fixture_source="ESPN", provider_event_id="123", status="cancelled",
        observed_at=NOW + timedelta(seconds=2), db_path=db,
    )
    shadow.record_fixture_status(
        fixture_source="ESPN", provider_event_id="123", status="scheduled",
        observed_at=NOW + timedelta(seconds=1), db_path=db,
    )

    assert shadow.latest_fixture_status(
        fixture_source="ESPN", provider_event_id="123", db_path=db
    ) == {
        "status": "cancelled",
        "observed_at": (NOW + timedelta(seconds=2)).isoformat(),
    }


def test_fixture_status_rows_are_append_only(db):
    shadow.record_fixture_status(
        fixture_source="ESPN", provider_event_id="123", status="scheduled",
        observed_at=NOW, db_path=db,
    )

    with closing(sqlite3.connect(db)) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE fixture_status_observations SET status='cancelled'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM fixture_status_observations")


def test_invalid_metadata_is_reported_without_guessing_or_loading_state(db, monkeypatch):
    store(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TABLE prediction_revisions")
        conn.execute("UPDATE predictions SET provider_event_id=NULL")
    monkeypatch.setattr(daily,"load_tour_state",lambda *a,**k: pytest.fail("invalid identity"))
    result = daily.refresh_pending_predictions(db_path=db,as_of=NOW)
    assert result["due"] == 0
    assert result["errors"] == [{"prediction_id":1,"reason":"invalid_fixture_metadata"}]


@pytest.mark.parametrize("start,match_date,checked_at", [
    ((NOW-timedelta(seconds=1)).isoformat(), "2030-01-02", NOW),
    (NOW.isoformat(), "2030-01-02", NOW),
    (None, "2029-12-01", NOW),
    ("invalid", "2029-12-01", NOW),
    ("2030-01-01T18:00:00", "2030-01-01", NOW),
    (None, "2030-01-02", NOW.replace(hour=23, minute=30)),
])
def test_past_legacy_rows_are_preserved_without_operational_errors(
    db, monkeypatch, start, match_date, checked_at,
):
    store(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TABLE prediction_revisions")
        conn.execute(
            "UPDATE predictions SET provider_event_id=NULL, fixture_source=NULL, "
            "scheduled_start_utc=?, match_date=?", (start, match_date),
        )
    before = db.read_bytes()
    monkeypatch.setattr(daily,"load_tour_state",lambda *a,**k: pytest.fail("past legacy row is not refreshable"))
    result = daily.refresh_pending_predictions(db_path=db,as_of=checked_at)
    assert result["checked"] == result["skipped"] == 1
    assert result["due"] == result["refreshed"] == 0
    assert result["errors"] == []
    assert result["status"] == "unchanged"
    assert db.read_bytes() == before


@pytest.mark.parametrize("start,match_date", [
    (None, "2030-01-02"),
    (None, "2030-01-03"),
    (None, "malformed-date"),
    (None, "2030-02-30"),
    ("invalid", "2030-01-02"),
    (START.isoformat(), "2029-12-01"),
])
def test_unresolved_current_or_future_metadata_remains_an_error(db, monkeypatch, start, match_date):
    store(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TABLE prediction_revisions")
        conn.execute(
            "UPDATE predictions SET provider_event_id=NULL, fixture_source=NULL, "
            "scheduled_start_utc=?, match_date=?", (start, match_date),
        )
    before = db.read_bytes()
    monkeypatch.setattr(daily,"load_tour_state",lambda *a,**k: pytest.fail("invalid metadata cannot be refreshed"))
    result = daily.refresh_pending_predictions(db_path=db,as_of=NOW)
    assert result["checked"] == result["skipped"] == 1
    assert result["due"] == result["refreshed"] == 0
    assert result["errors"] == [{"prediction_id":1,"reason":"invalid_fixture_metadata"}]
    assert db.read_bytes() == before


def test_explicit_future_start_is_refreshable_despite_old_calendar_date(db, monkeypatch):
    store(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TABLE prediction_revisions")
        conn.execute("UPDATE predictions SET match_date='2029-12-01'")
    monkeypatch.setattr(daily,"predict_match",lambda *a,**k: prediction(.57))
    result = daily.refresh_pending_predictions(
        db_path=db, as_of=NOW, append_observed_at=NOW,
    )
    assert result["due"] == result["refreshed"] == 1
    assert result["errors"] == []
    latest = shadow.latest_predictions(db,as_of=NOW)[0]
    assert latest["scheduled_start_utc"] == START.isoformat()
    assert latest["match_date"] == "2029-12-01"
    assert latest["p_cal"] == .57


def test_bad_cutoff_and_interval_are_not_silently_normalized(db):
    with pytest.raises(ValueError,match="timezone-aware"):
        daily.refresh_pending_predictions(db_path=db,as_of=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError,match="non-negative"):
        daily.refresh_pending_predictions(db_path=db,as_of=NOW,minimum_interval=timedelta(seconds=-1))
