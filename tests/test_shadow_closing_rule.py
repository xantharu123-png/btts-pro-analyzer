"""Shadow closing-quote rule (owner decision 28.10.2026).

API-Football refreshes pre-match odds about every three hours, so a closing
stamp inside the final 15 minutes almost never exists (0 closings in 119 shadow
runs). The closing is now the last market state before kick-off: captured in
the final 15 minutes, provider stamp at most three hours old at capture, capture
clock and age stored. A closing that repeats the opening market state is valid
but no CLV evidence. Rows captured under the old rule keep their checks.
Owner decision 29.10.2026 (policy v8): the stamp may be up to twelve hours old,
because API-Football stamps per fixture in batch runs two to four hours apart.
"""
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

import shadow_clv_automation as shadow
from clv_tracker import CLVTracker
from tests.test_shadow_markets import _odds_response

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _tracker(tmp_path):
    return CLVTracker(db_path=str(tmp_path / "clv.db"))


def _record(tracker, *, kickoff, opening_age, fixture_id=42, created=None):
    return tracker.record_prediction(
        fixture_id=fixture_id, home_team="Home", away_team="Away", market_type="BTTS_YES", prediction="Ja",
        odds=1.75, model_probability=55.0, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
        fixture_kickoff=kickoff, quoted_at=NOW - opening_age,
        model_version=shadow.SHADOW_MODEL_VERSION, policy_version=shadow.SHADOW_POLICY_VERSION)


def _row(db_path, prediction_id):
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT closing_odds, quoted_at, closing_quoted_at, closing_captured_at, closing_quote_age_seconds "
            "FROM predictions WHERE id = ?", (prediction_id,)).fetchone()


def test_contract_constants():
    assert CLVTracker.CLOSING_WINDOW == timedelta(minutes=15)
    assert CLVTracker.CLOSING_QUOTE_MAX_AGE == timedelta(hours=12)
    assert shadow.SHADOW_POLICY_VERSION == "shadow-model-first-v9"


def test_tracker_stores_the_last_market_state_with_capture_clock_and_age(tmp_path):
    tracker = _tracker(tmp_path)
    kickoff = NOW + timedelta(minutes=10)
    prediction_id = _record(tracker, kickoff=kickoff, opening_age=timedelta(minutes=150))
    stamp = NOW - timedelta(minutes=95)  # a later market state than the opening, older than 15 minutes
    tracker.update_closing_odds(prediction_id, 1.70, bookmaker=shadow.BOOKMAKER_NAME,
                                quote_source=shadow.QUOTE_SOURCE, quoted_at=stamp, captured_at=NOW)
    closing, _, closing_stamp, captured, age = _row(tmp_path / "clv.db", prediction_id)
    assert closing == 1.70 and closing_stamp == stamp.isoformat() and captured == NOW.isoformat()
    assert age == 95 * 60


def test_tracker_refuses_stale_states_and_captures_outside_the_window(tmp_path):
    tracker = _tracker(tmp_path)
    kickoff = NOW + timedelta(minutes=10)
    first = _record(tracker, kickoff=kickoff, opening_age=timedelta(minutes=170), fixture_id=1)
    with sqlite3.connect(tmp_path / "clv.db") as connection:  # an opening logged long ago (real clocks cannot)
        connection.execute("UPDATE predictions SET quoted_at = ? WHERE id = ?",
                           ((NOW - timedelta(minutes=760)).isoformat(), first))
    with pytest.raises(ValueError, match="older than twelve hours"):
        tracker.update_closing_odds(first, 1.70, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
                                    quoted_at=NOW - timedelta(minutes=725), captured_at=NOW)
    with pytest.raises(ValueError, match="before kickoff|in the future"):
        tracker.update_closing_odds(first, 1.70, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
                                    quoted_at=NOW - timedelta(minutes=30), captured_at=kickoff)
    early = _record(tracker, kickoff=NOW + timedelta(minutes=40), opening_age=timedelta(minutes=60), fixture_id=2)
    with pytest.raises(ValueError, match="15-minute closing window"):
        tracker.update_closing_odds(early, 1.70, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
                                    quoted_at=NOW - timedelta(minutes=30), captured_at=NOW)
    # Without a capture clock the old rule stays: the stamp itself must be inside the final 15 minutes.
    legacy = _record(tracker, kickoff=kickoff, opening_age=timedelta(minutes=60), fixture_id=3)
    with pytest.raises(ValueError, match="15-minute closing window"):
        tracker.update_closing_odds(legacy, 1.70, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
                                    quoted_at=NOW - timedelta(minutes=30))
    tracker.update_closing_odds(legacy, 1.70, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
                                quoted_at=NOW)
    assert _row(tmp_path / "clv.db", legacy)[3:] == (None, None)


def _settled(db_path, prediction_id, *, opening, closing, captured, kickoff, created, age=None):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE predictions SET quoted_at = ?, created_at = ?, opening_quote_age_seconds = ?, closing_odds = 1.6, "
            "closing_bookmaker = ?, closing_source = ?, closing_quoted_at = ?, closing_captured_at = ?, "
            "closing_quote_age_seconds = ?, fixture_kickoff = ?, result = 'Won', profit = 0.75, home_score = 1, "
            "away_score = 1, settled_at = ? WHERE id = ?",
            (opening.isoformat(), created.isoformat(), int((created - opening).total_seconds()), shadow.BOOKMAKER_NAME,
             shadow.QUOTE_SOURCE, closing.isoformat(), captured.isoformat() if captured else None,
             (int((captured - closing).total_seconds()) if age is None else age) if captured else None,
             kickoff.isoformat(), (kickoff + timedelta(hours=2)).isoformat(), prediction_id))


def test_statistics_use_new_market_states_and_count_repeated_ones_apart(tmp_path):
    db_path = tmp_path / "clv.db"
    tracker = _tracker(tmp_path)
    kickoff = NOW - timedelta(hours=4)
    created = kickoff - timedelta(minutes=65)
    opening = created - timedelta(minutes=120)
    capture = kickoff - timedelta(minutes=8)
    later = _record(tracker, kickoff=NOW + timedelta(hours=4), opening_age=timedelta(minutes=5), fixture_id=11)
    _settled(db_path, later, opening=opening, closing=kickoff - timedelta(minutes=50), captured=capture,
             kickoff=kickoff, created=created)
    repeated = _record(tracker, kickoff=NOW + timedelta(hours=4), opening_age=timedelta(minutes=5), fixture_id=12)
    _settled(db_path, repeated, opening=opening, closing=opening, captured=capture, kickoff=kickoff, created=created)
    legacy = _record(tracker, kickoff=NOW + timedelta(hours=4), opening_age=timedelta(minutes=5), fixture_id=13)
    _settled(db_path, legacy, opening=opening, closing=kickoff - timedelta(minutes=5), captured=None,
             kickoff=kickoff, created=created)
    stats = tracker.get_clv_statistics(days=30, model_version=shadow.SHADOW_MODEL_VERSION,
                                       policy_version=shadow.SHADOW_POLICY_VERSION)
    assert stats["evidence_valid"] is True
    assert stats["total_bets"] == 3 and stats["clv_bets"] == 2 and stats["independent_clv_fixtures"] == 2
    assert stats["closing_without_new_market_state"] == 1
    assert stats["avg_clv"] == pytest.approx(round((1.75 / 1.6 - 1) * 100, 2))
    recent = {row["fixture_id"]: row for row in tracker.get_recent_predictions(
        5, model_version=shadow.SHADOW_MODEL_VERSION, policy_version=shadow.SHADOW_POLICY_VERSION)}
    assert recent[11]["closing_new_market_state"] is True and recent[11]["clv"] is not None
    assert recent[12]["closing_new_market_state"] is False and recent[12]["clv"] is None
    assert recent[13]["clv"] is not None  # old rule, stamp inside the final 15 minutes
    # A stored closing age that contradicts the clocks invalidates the evidence.
    broken = _record(tracker, kickoff=NOW + timedelta(hours=4), opening_age=timedelta(minutes=5), fixture_id=14)
    _settled(db_path, broken, opening=opening, closing=kickoff - timedelta(minutes=50), captured=capture,
             kickoff=kickoff, created=created, age=10)
    stats = tracker.get_clv_statistics(days=30, model_version=shadow.SHADOW_MODEL_VERSION,
                                       policy_version=shadow.SHADOW_POLICY_VERSION)
    assert stats["evidence_valid"] is False and "invalid_quote_provenance" in stats["integrity_issues"]


@pytest.fixture
def shadow_db(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.db"
    monkeypatch.setattr(shadow, "SHADOW_DB", db_path)
    shadow.errors.clear()
    return SimpleNamespace(tracker=CLVTracker(db_path=str(db_path)), db_path=db_path)


def test_shadow_captures_the_last_state_even_when_older_than_fifteen_minutes(shadow_db):
    kickoff = NOW + timedelta(minutes=10)
    prediction_id = _record(shadow_db.tracker, kickoff=kickoff, opening_age=timedelta(minutes=150))
    stamp = NOW - timedelta(minutes=95)
    provider = SimpleNamespace(odds=lambda *a, **k: _odds_response(updated_at=stamp.isoformat()))
    assert shadow.step_closing(shadow_db.tracker, provider, NOW) == 1
    closing, _, closing_stamp, captured, age = _row(shadow_db.db_path, prediction_id)
    assert closing == 1.75 and closing_stamp == stamp.isoformat() and captured == NOW.isoformat() and age == 95 * 60
    assert shadow.errors == []


def test_shadow_marks_a_repeated_state_and_skips_a_stale_one_as_data_status(shadow_db):
    kickoff = NOW + timedelta(minutes=10)
    repeated = _record(shadow_db.tracker, kickoff=kickoff, opening_age=timedelta(minutes=100), fixture_id=21)
    opening_stamp = _row(shadow_db.db_path, repeated)[1]
    provider = SimpleNamespace(odds=lambda *a, **k: _odds_response(updated_at=opening_stamp))
    assert shadow.step_closing(shadow_db.tracker, provider, NOW) == 1
    assert _row(shadow_db.db_path, repeated)[2] == opening_stamp  # stored, CLV evidence excludes it
    stale_db = shadow_db.db_path.with_name("stale.db")
    tracker = CLVTracker(db_path=str(stale_db))
    shadow.SHADOW_DB = stale_db
    stale = tracker.record_prediction(
        fixture_id=22, home_team="Home", away_team="Away", market_type="BTTS_YES", prediction="Ja", odds=1.75,
        model_probability=55.0, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
        fixture_kickoff=kickoff, quoted_at=NOW - timedelta(minutes=719),
        model_version=shadow.SHADOW_MODEL_VERSION, policy_version=shadow.SHADOW_POLICY_VERSION)
    with sqlite3.connect(stale_db) as connection:  # an opening logged long ago (real clocks cannot)
        connection.execute("UPDATE predictions SET quoted_at = ? WHERE id = ?",
                           ((NOW - timedelta(minutes=730)).isoformat(), stale))
    provider = SimpleNamespace(odds=lambda *a, **k: _odds_response(
        updated_at=(NOW - timedelta(minutes=725)).isoformat()))
    shadow.errors.clear()
    assert shadow.step_closing(tracker, provider, NOW) == 0
    assert _row(stale_db, stale)[0] is None
    assert shadow.errors and all(shadow.is_data_status(message) for message in shadow.errors)


def test_v8_keeps_the_28_october_closing_older_than_three_hours(shadow_db):
    # Fixture 1638113 on 28.10.2026: stamp 12:04 UTC, logged 14:52, kick-off 16:00, closing call 15:52.
    kickoff = NOW + timedelta(minutes=8)
    prediction_id = _record(shadow_db.tracker, kickoff=kickoff, opening_age=timedelta(minutes=168))
    with sqlite3.connect(shadow_db.db_path) as connection:  # the opening was logged an hour before the call
        connection.execute("UPDATE predictions SET quoted_at = ?, created_at = ? WHERE id = ?",
                           ((NOW - timedelta(minutes=228)).isoformat(), (NOW - timedelta(minutes=60)).isoformat(),
                            prediction_id))
    opening_stamp = _row(shadow_db.db_path, prediction_id)[1]
    provider = SimpleNamespace(odds=lambda *a, **k: _odds_response(updated_at=opening_stamp))
    assert shadow.step_closing(shadow_db.tracker, provider, NOW) == 1
    closing, _, closing_stamp, captured, age = _row(shadow_db.db_path, prediction_id)
    assert closing == 1.75 and closing_stamp == opening_stamp and captured == NOW.isoformat()
    assert age == 228 * 60 and shadow.errors == []


def test_edge_cap_and_paired_statistics_leave_repeated_states_out(shadow_db):
    shadow._connect().close()
    with sqlite3.connect(shadow_db.db_path) as connection:
        rows = [
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.8, "Won", "x", shadow.SHADOW_MODEL_VERSION,
             "2030-01-01T10:00:00+00:00", "2030-01-01T12:00:00+00:00"),
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.9, "Won", "x", shadow.SHADOW_HYBRID_MODEL_VERSION,
             "2030-01-01T10:00:00+00:00", "2030-01-01T12:00:00+00:00"),
            (2, "C", "D", "RESULT_HOME", "Heim", 2.0, 2.0, "Lost", "x", shadow.SHADOW_MODEL_VERSION,
             "2030-01-01T10:00:00+00:00", "2030-01-01T10:00:00+00:00"),
            (2, "C", "D", "RESULT_AWAY", "Auswärts", 3.0, 3.0, "Won", "x", shadow.SHADOW_HYBRID_MODEL_VERSION,
             "2030-01-01T10:00:00+00:00", "2030-01-01T10:00:00+00:00"),
        ]
        connection.executemany(
            "INSERT INTO predictions (fixture_id, home_team, away_team, market_type, prediction, odds, closing_odds, "
            "result, created_at, model_version, quoted_at, closing_quoted_at, policy_version) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [(*row, shadow.SHADOW_POLICY_VERSION) for row in rows])
        ids = [row[0] for row in connection.execute("SELECT id FROM predictions ORDER BY id")]
        connection.executemany(
            "INSERT INTO shadow_edge_cap VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(ids[0], shadow.SHADOW_MODEL_VERSION, 0.55, 0.5, 5.0, 8.0, 1, "t"),
             (ids[2], shadow.SHADOW_MODEL_VERSION, 0.55, 0.5, 5.0, 8.0, 1, "t")])
    legacy = shadow._edge_cap_statistics()["cohorts"][shadow.SHADOW_MODEL_VERSION]
    assert legacy["closed_passed"] == 1 and legacy["closed_without_new_market_state"] == 1
    paired = shadow._paired_cohort_statistics()
    assert paired["pairs"] == 1 and paired["pairs_without_new_market_state"] == 1
