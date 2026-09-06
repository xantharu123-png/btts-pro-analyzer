from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace

import pytest

from tennis import shadow
from tennis.workload import observed_workload_context


NOW = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)
START = NOW + timedelta(hours=6)


def prediction(p=0.65):
    return SimpleNamespace(
        player_a="Alpha", player_b="Beta", surface="Hard", best_of=3,
        p_a_raw=p, p_a_cal=p, gates=[], verdict="KEINE WETTE",
        recommended_side=None, recommended_edge=0.0,
        market_summary=lambda: {"p_a_cal": p, "p_b_cal": 1-p},
        context_evidence={"probability_adjustment_applied": False},
    )


def store(pred, when, **kwargs):
    return shadow.store_prediction(
        "2030-01-02", "ATP", "Test Open", pred,
        provider_event_id="123", fixture_source="ESPN",
        scheduled_start_utc=START.isoformat(), modeled_at=when, **kwargs,
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "tennis.db"
    monkeypatch.setattr(shadow, "DB_PATH", path)
    return path


def test_new_scan_exposes_latest_model_without_rewriting_initial_or_prices(db):
    original = store(prediction(.65), NOW, odds_a=1.9, odds_b=2.0)
    assert store(prediction(.56), NOW + timedelta(hours=1)) == -1
    initial = shadow.pending_predictions()[0]
    latest = shadow.latest_predictions(as_of=NOW + timedelta(hours=2))[0]
    assert initial["id"] == latest["id"] == original
    assert initial["p_cal"] == .65
    assert initial["odds_a"] == 1.9
    assert latest["p_cal"] == .56
    assert latest["odds_a"] is None
    assert latest["initial_created_utc"] == NOW.timestamp()
    assert latest["created_utc"] == (NOW + timedelta(hours=1)).timestamp()
    assert len(latest["model_revision_id"]) == 64
    assert json.loads(latest["context_json"])["probability_adjustment_applied"] is False
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM prediction_revisions").fetchone()[0] == 2


def test_asof_read_does_not_leak_later_revision(db):
    store(prediction(.65), NOW)
    store(prediction(.56), NOW + timedelta(hours=1))
    assert shadow.latest_predictions(as_of=NOW - timedelta(seconds=1)) == []
    assert shadow.latest_predictions(as_of=NOW + timedelta(minutes=30))[0]["p_cal"] == .65


@pytest.mark.parametrize("first_id,first_source,next_id,next_source", [
    ("123", "ESPN", "456", "ESPN"),
    ("123", "ESPN", "123", "Sofascore"),
    ("123", None, "456", "ESPN"),
    (None, "Sofascore", "123", "ESPN"),
    ("123", "ESPN", None, None),
])
def test_same_pair_day_cannot_merge_conflicting_native_events(
    db, first_id, first_source, next_id, next_source,
):
    original = shadow.store_prediction(
        "2030-01-02", "ATP", "Test Open", prediction(.65),
        provider_event_id=first_id, fixture_source=first_source,
        scheduled_start_utc=START.isoformat(), modeled_at=NOW,
    )
    other_start = START + timedelta(hours=1)
    other = shadow.store_prediction(
        "2030-01-02", "ATP", "Test Open", prediction(.42),
        provider_event_id=next_id, fixture_source=next_source,
        scheduled_start_utc=other_start.isoformat(),
        modeled_at=NOW + timedelta(minutes=1),
    )
    assert other > original
    rows = {row["id"]: row for row in shadow.latest_predictions(as_of=NOW + timedelta(hours=2))}
    assert len(rows) == 2
    for key, event_id, source, start, p in [
        (original, first_id, first_source, START, .65),
        (other, next_id, next_source, other_start, .42),
    ]:
        assert rows[key]["provider_event_id"] == event_id
        assert rows[key]["fixture_source"] == source
        assert rows[key]["scheduled_start_utc"] == start.isoformat()
        assert rows[key]["p_cal"] == p
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT scheduled_start_utc FROM predictions WHERE id=?", (original,)).fetchone()[0] == START.isoformat()


@pytest.mark.parametrize("legacy_id,legacy_source", [(None, None), ("123", None), (None, "ESPN")])
def test_compatible_legacy_identity_can_gain_native_metadata(db, legacy_id, legacy_source):
    original = shadow.store_prediction(
        "2030-01-02", "ATP", "Test Open", prediction(.65),
        provider_event_id=legacy_id, fixture_source=legacy_source,
        scheduled_start_utc=START.isoformat(), modeled_at=NOW,
    )
    assert store(prediction(.42), NOW + timedelta(hours=1)) == -1
    rows = shadow.latest_predictions(as_of=NOW + timedelta(hours=2))
    assert len(rows) == 1
    assert rows[0]["id"] == original
    assert rows[0]["provider_event_id"] == "123"
    assert rows[0]["fixture_source"] == "ESPN"
    assert rows[0]["p_cal"] == .42
    historical = shadow.latest_predictions(as_of=NOW + timedelta(minutes=30))[0]
    assert historical["provider_event_id"] == legacy_id
    assert historical["fixture_source"] == legacy_source
    assert historical["p_cal"] == .65


def test_asof_read_cannot_reuse_prices_observed_after_cutoff(db):
    store(prediction(.65), NOW)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE predictions SET odds_a=2.1, odds_b=1.8, price_checked_utc=?", ((NOW+timedelta(hours=1)).timestamp(),))
    before = shadow.latest_predictions(as_of=NOW+timedelta(minutes=30))[0]
    after = shadow.latest_predictions(as_of=NOW+timedelta(hours=2))[0]
    assert before["odds_a"] is None
    assert before["price_checked_utc"] is None
    assert after["odds_a"] == 2.1


def test_legacy_reader_is_read_only_and_new_scan_preserves_original(db):
    store(prediction(.65), NOW)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE prediction_revisions")
        before = conn.execute("SELECT * FROM predictions").fetchall()
    assert shadow.latest_predictions(as_of=NOW+timedelta(minutes=30))[0]["model_revision_id"] is None
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='prediction_revisions'").fetchone() is None
    store(prediction(.52), NOW+timedelta(hours=1))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT * FROM predictions").fetchall() == before
    assert shadow.latest_predictions(as_of=NOW+timedelta(hours=2))[0]["p_cal"] == .52


def test_legacy_reschedule_freezes_original_fixture_before_parent_refresh(db):
    original = store(prediction(.65), NOW, odds_a=1.9, odds_b=2.0)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE prediction_revisions")
    moved = START + timedelta(days=1)
    shadow.store_prediction("2030-01-03", "ATP", "Test Open", prediction(.56),
        provider_event_id="123", fixture_source="ESPN", scheduled_start_utc=moved.isoformat(),
        modeled_at=NOW+timedelta(hours=1))
    historical = shadow.latest_predictions(as_of=NOW+timedelta(minutes=30))[0]
    assert historical["id"] == original
    assert historical["p_cal"] == .65
    assert historical["match_date"] == "2030-01-02"
    assert historical["scheduled_start_utc"] == START.isoformat()
    assert historical["created_utc"] == NOW.timestamp()
    assert historical["revision_origin"] == "legacy_imported_baseline"
    assert historical["odds_a"] == 1.9
    latest = shadow.latest_predictions(as_of=NOW+timedelta(hours=2))[0]
    assert latest["p_cal"] == .56
    assert latest["scheduled_start_utc"] == moved.isoformat()
    assert latest["odds_a"] is None
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT p_cal,odds_a,match_date FROM predictions").fetchone() == (.65, 1.9, "2030-01-03")
        baselines = [json.loads(row[0]) for row in conn.execute(
            "SELECT payload_json FROM prediction_revisions WHERE modeled_utc=?", (NOW.timestamp(),))]
    assert len(baselines) == 1
    assert not {"odds_a", "odds_b", "actual_winner", "pnl", "settled"} & set(baselines[0])


def test_legacy_baseline_preserves_unknown_native_metadata_without_borrowing_new_values(db):
    shadow.store_prediction("2030-01-02", "ATP", "Test Open", prediction(), modeled_at=NOW)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE prediction_revisions")
    store(prediction(.56), NOW+timedelta(hours=1))
    original = shadow.latest_predictions(as_of=NOW+timedelta(minutes=30))[0]
    assert original["scheduled_start_utc"] is None
    assert original["provider_event_id"] is None
    assert original["fixture_source"] is None
    assert original["context_json"] is None
    assert original["created_utc"] == NOW.timestamp()


@pytest.mark.parametrize("field,value", [
    ("p_raw", None), ("p_cal", 1.5), ("p_raw", float("inf")),
    ("created_utc", "missing"), ("created_utc", -1),
    ("scheduled_start_utc", "2030-01-02T18:00:00"),
    ("scheduled_start_utc", (NOW-timedelta(hours=1)).isoformat()),
    ("markets_json", "not-json"),
])
def test_invalid_legacy_baseline_aborts_refresh_atomically(db, field, value):
    store(prediction(), NOW)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE prediction_revisions")
        conn.execute(f"UPDATE predictions SET {field}=?", (value,))
        original = conn.execute("SELECT * FROM predictions").fetchall()
    with pytest.raises((ValueError, TypeError)):
        shadow.store_prediction("2030-01-03", "ATP", "Test Open", prediction(.56),
            provider_event_id="123", fixture_source="ESPN", scheduled_start_utc=(START+timedelta(days=1)).isoformat(),
            modeled_at=NOW+timedelta(hours=1))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT * FROM predictions").fetchall() == original
        assert conn.execute("SELECT COUNT(*) FROM prediction_revisions").fetchone()[0] == 0


def test_already_mutated_legacy_row_cannot_supply_historical_fixture_without_baseline(db):
    from tennis.prediction_revisions import REVISION_SCHEMA, append_revision
    store(prediction(), NOW)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("DROP TABLE prediction_revisions")
        conn.executescript(REVISION_SCHEMA)
        conn.execute("UPDATE predictions SET scheduled_start_utc=?,match_date='2030-01-03'",
                     ((START+timedelta(days=1)).isoformat(),))
        later = dict(conn.execute("SELECT * FROM predictions").fetchone())
        later.update(created_utc=(NOW+timedelta(hours=1)).timestamp(), p_raw=.56, p_cal=.56)
        append_revision(conn, later["id"], later)
    assert shadow.latest_predictions(as_of=NOW+timedelta(minutes=30)) == []
    assert shadow.latest_predictions(as_of=NOW+timedelta(hours=2))[0]["p_cal"] == .56


def test_append_cannot_backdate_before_original_observation(db):
    store(prediction(.65), NOW)
    with pytest.raises(ValueError, match="precedes"):
        store(prediction(.56), NOW-timedelta(seconds=1))


def test_revision_mutations_are_rejected_and_equal_time_is_unambiguous(db):
    store(prediction(.65), NOW)
    assert store(prediction(.65), NOW) == -1
    with pytest.raises(ValueError, match="equal-time"):
        store(prediction(.56), NOW)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM prediction_revisions").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("UPDATE prediction_revisions SET modeled_utc=0")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("DELETE FROM prediction_revisions")


def test_revision_after_start_or_swapped_players_cannot_mutate_identity(db):
    store(prediction(.65), NOW)
    with pytest.raises(ValueError, match="precede"):
        store(prediction(.56), START)
    swapped = prediction(.56)
    swapped.player_a, swapped.player_b = "Beta", "Alpha"
    with pytest.raises(ValueError, match="identity"):
        store(swapped, NOW + timedelta(hours=1))
    assert shadow.latest_predictions(as_of=NOW + timedelta(hours=2))[0]["p_cal"] == .65


def test_settlement_remains_on_original_row_and_stops_new_revisions(db):
    original = store(prediction(.65), NOW)
    store(prediction(.56), NOW + timedelta(hours=1))
    shadow.settle(original, "Alpha", termination="normal", result_observed_at=START+timedelta(hours=2), player_a_sets=2, player_b_sets=0)
    assert shadow.latest_predictions(as_of=START+timedelta(hours=3)) == []
    with pytest.raises(ValueError, match="settlement"):
        store(prediction(.60), NOW + timedelta(hours=2))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT p_cal, actual_winner FROM predictions").fetchone() == (.65, "Alpha")


def test_latest_reader_never_creates_missing_database(tmp_path):
    path = tmp_path / "missing.db"
    assert shadow.latest_predictions(path) == []
    assert not path.exists()


def test_incomplete_legacy_database_is_not_given_a_fabricated_clock(tmp_path):
    path = tmp_path / "legacy-incomplete.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE predictions(id INTEGER PRIMARY KEY, settled INTEGER)")
        conn.execute("INSERT INTO predictions VALUES(1,0)")
    conn.close()
    assert shadow.latest_predictions(path) == []
    # This also checks that a short-circuit reader releases the Windows handle.
    path.unlink()


def workload_row(**overrides):
    return {
        "settled": 1, "player_a": "Alpha", "player_b": "Gamma",
        "fixture_source": "ESPN", "provider_event_id": "previous",
        "scheduled_start_utc": (NOW-timedelta(hours=22)).isoformat(),
        "result_observed_at": (NOW-timedelta(hours=18)).isoformat(),
        "termination": "normal", "player_a_sets": 3, "player_b_sets": 2,
        "match_duration_minutes": 230, **overrides,
    }


def test_workload_records_five_sets_and_only_a_bound_for_recovery():
    context = observed_workload_context("Alpha", "Beta", [workload_row()], as_of=NOW)
    alpha = context["players"]["a"]
    assert alpha["previous_five_sets"] is True
    assert alpha["minimum_recovery_hours"] == 18
    assert alpha["observed_minutes_7d"] == 230
    assert alpha["observed_sets_7d"] == 5
    assert context["probability_adjustment_applied"] is False
    assert context["adjustment_pp"] == 0
    assert context["coverage"] == "observed_matches_only"
    assert context["players"]["b"]["previous_match"] is None
    assert context["players"]["b"]["observed_minutes_7d"] is None


def test_workload_ignores_future_observation_unplayed_and_undated_matches():
    rows = [
        workload_row(result_observed_at=(NOW+timedelta(seconds=1)).isoformat()),
        workload_row(termination="walkover"),
        workload_row(scheduled_start_utc=None),
        workload_row(settled=0),
        workload_row(player_a="Alphard"),
    ]
    evidence = observed_workload_context("Alpha", "Beta", rows, as_of=NOW)["players"]["a"]
    assert evidence["previous_match"] is None
    assert evidence["previous_five_sets"] is None


def test_workload_counts_event_once_across_model_versions():
    row = workload_row()
    evidence = observed_workload_context("Alpha", "Beta", [row, dict(row)], as_of=NOW)["players"]["a"]
    assert evidence["observed_matches_7d"] == 1
    assert evidence["observed_sets_7d"] == 5


def test_known_result_duration_is_persisted_without_price_or_model_leak(db):
    pred = prediction()
    pred.best_of = 5
    original = store(pred, NOW)
    shadow.settle(original, "Alpha", termination="normal", result_observed_at=START+timedelta(hours=4), player_a_sets=3, player_b_sets=2, match_duration_minutes=230)
    records = shadow.workload_history()
    assert records[0]["match_duration_minutes"] == 230
    assert "p_cal" not in records[0]
    assert "odds_a" not in records[0]


def test_predict_keeps_numerical_model_independent_of_unvalidated_workload():
    from test_tennis_predict import _synthetic_state
    from tennis.predict import predict_match
    state = _synthetic_state()
    observed = workload_row(player_a="Hero H.")
    plain = predict_match(state, "Hero H.", "Grinder G.", "Hard", as_of=NOW)
    contextual = predict_match(state, "Hero H.", "Grinder G.", "Hard", as_of=NOW, workload_history=[observed])
    assert plain.p_a_cal == contextual.p_a_cal
    assert plain.market_summary() == contextual.market_summary()
    assert contextual.context_evidence["players"]["a"]["previous_five_sets"] is True
    assert contextual.modeled_at == NOW
