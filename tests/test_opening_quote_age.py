"""Opening-quote freshness contract (owner decision 23.10.2026).

The opening price may carry a provider stamp up to three hours old; the ledger
stores the age of every new row, the statistics re-check the stored age against
the row's own clocks, and the shadow cohorts moved to policy v6.
"""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import shadow_clv_automation as shadow
from clv_tracker import CLVTracker


def _record(tracker, now, *, age, fixture_id=42, odds=2.0):
    return tracker.record_prediction(
        fixture_id=fixture_id, home_team="Home", away_team="Away", market_type="BTTS_YES", prediction="Ja",
        odds=odds, model_probability=55.0, bookmaker="Bet365", quote_source="API-Football",
        fixture_kickoff=now + timedelta(hours=4), quoted_at=now - age,
        model_version=shadow.SHADOW_MODEL_VERSION, policy_version=shadow.SHADOW_POLICY_VERSION,
    )


def test_contract_constants_and_policy_version():
    assert CLVTracker.OPENING_QUOTE_MAX_AGE == timedelta(hours=3)
    assert CLVTracker.OPENING_QUOTE_MAX_AGE_V1 == timedelta(minutes=10)
    assert CLVTracker.CLOSING_WINDOW == timedelta(minutes=15)
    # v7 since 28.10.2026: closing = last market state before kick-off (tests/test_shadow_closing_rule.py).
    assert shadow.SHADOW_POLICY_VERSION == "shadow-model-first-v7"


def test_opening_quote_up_to_three_hours_is_recorded_with_its_age(tmp_path):
    tracker = CLVTracker(db_path=str(tmp_path / "clv.db"))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    prediction_id = _record(tracker, now, age=timedelta(hours=2, minutes=30))
    with sqlite3.connect(tmp_path / "clv.db") as connection:
        age, quoted_at, created_at = connection.execute(
            "SELECT opening_quote_age_seconds, quoted_at, created_at FROM predictions WHERE id = ?",
            (prediction_id,)).fetchone()
    assert age == pytest.approx(2.5 * 3600, abs=2)
    assert abs((datetime.fromisoformat(created_at) - datetime.fromisoformat(quoted_at)).total_seconds() - age) <= 1
    recent = tracker.get_recent_predictions(5, model_version=shadow.SHADOW_MODEL_VERSION,
                                            policy_version=shadow.SHADOW_POLICY_VERSION)
    assert recent[0]["opening_quote_age_seconds"] == age
    with pytest.raises(ValueError, match="stale"):
        _record(tracker, now, age=timedelta(hours=3, minutes=1), fixture_id=43)


def _settle(db_path, prediction_id, *, age_seconds, stored_age="same"):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    kickoff = now - timedelta(hours=3)
    created = kickoff - timedelta(hours=1)
    opening = created - timedelta(seconds=age_seconds)
    closing = kickoff - timedelta(minutes=5)
    stored = age_seconds if stored_age == "same" else stored_age
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE predictions SET quoted_at = ?, created_at = ?, closing_odds = 1.9, closing_bookmaker = 'Bet365', "
            "closing_source = 'API-Football', closing_quoted_at = ?, fixture_kickoff = ?, result = 'Won', profit = 1.0, "
            "home_score = 1, away_score = 1, settled_at = ?, opening_quote_age_seconds = ? WHERE id = ?",
            (opening.isoformat(), created.isoformat(), closing.isoformat(), kickoff.isoformat(),
             (kickoff + timedelta(hours=2)).isoformat(), stored, prediction_id))


def test_statistics_accept_aged_openings_and_reject_an_inconsistent_stored_age(tmp_path):
    db_path = tmp_path / "clv.db"
    tracker = CLVTracker(db_path=str(db_path))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first = _record(tracker, now, age=timedelta(minutes=5), fixture_id=1)
    _settle(db_path, first, age_seconds=2 * 3600)  # two hours old: valid under the new contract
    stats = tracker.get_clv_statistics(days=30, model_version=shadow.SHADOW_MODEL_VERSION,
                                       policy_version=shadow.SHADOW_POLICY_VERSION)
    assert stats["evidence_valid"] is True and stats["clv_bets"] == 1
    second = _record(tracker, now, age=timedelta(minutes=5), fixture_id=2)
    _settle(db_path, second, age_seconds=600, stored_age=5000)  # stored age contradicts the clocks
    stats = tracker.get_clv_statistics(days=30, model_version=shadow.SHADOW_MODEL_VERSION,
                                       policy_version=shadow.SHADOW_POLICY_VERSION)
    assert stats["evidence_valid"] is False and "invalid_quote_provenance" in stats["integrity_issues"]


def test_legacy_rows_without_stored_age_stay_valid_evidence(tmp_path):
    db_path = tmp_path / "clv.db"
    tracker = CLVTracker(db_path=str(db_path))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    row = _record(tracker, now, age=timedelta(minutes=5), fixture_id=7)
    _settle(db_path, row, age_seconds=300, stored_age=None)  # a v5 row: ten-minute rule, no age column
    stats = tracker.get_clv_statistics(days=30, model_version=shadow.SHADOW_MODEL_VERSION,
                                       policy_version=shadow.SHADOW_POLICY_VERSION)
    assert stats["evidence_valid"] is True and stats["clv_bets"] == 1


def test_run_artifact_names_the_opening_quote_limit():
    assert int(CLVTracker.OPENING_QUOTE_MAX_AGE.total_seconds()) == 10800
    source = open(shadow.__file__, encoding="utf-8").read()
    assert '"opening_quote_max_age_seconds"' in source
