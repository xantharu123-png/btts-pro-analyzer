"""No-vig CLV in the shadow (Audit 25.10.2026 S5, second part).

The raw CLV (opening / closing − 1) still contains the bookmaker margin of both
prices. With the closing quote the shadow stores the fair (no-vig) closing
probability of the tip's side from the complete Bet365 partition; the no-vig
CLV is the expected value of the opening price at that fair probability:
opening odds × p_close − 1. Research record only; it never changes the ledger.
"""
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

import shadow_clv_automation as shadow
from betting_math import no_vig_market
from clv_tracker import CLVTracker
from tests.test_shadow_markets import _odds_response

NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def shadow_db(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.db"
    monkeypatch.setattr(shadow, "SHADOW_DB", db_path)
    shadow.errors.clear()
    return SimpleNamespace(tracker=CLVTracker(db_path=str(db_path)), db_path=db_path)


def _record(tracker, *, fixture_id=42, model_version=shadow.SHADOW_MODEL_VERSION, market="BTTS_YES",
            selection="Ja", odds=1.80):
    return tracker.record_prediction(
        fixture_id=fixture_id, home_team="Home", away_team="Away", market_type=market, prediction=selection,
        odds=odds, model_probability=55.0, bookmaker=shadow.BOOKMAKER_NAME, quote_source=shadow.QUOTE_SOURCE,
        fixture_kickoff=NOW + timedelta(minutes=10), quoted_at=NOW - timedelta(minutes=150),
        model_version=model_version, policy_version=shadow.SHADOW_POLICY_VERSION)


def _closing_market(db_path):
    with sqlite3.connect(db_path) as connection:
        return dict(connection.execute("SELECT prediction_id, market_probability FROM shadow_closing_market"))


def test_closing_stores_the_fair_probability_of_the_complete_partition(shadow_db):
    prediction_id = _record(shadow_db.tracker)
    provider = SimpleNamespace(odds=lambda *a, **k: _odds_response(
        updated_at=(NOW - timedelta(minutes=95)).isoformat()))

    assert shadow.step_closing(shadow_db.tracker, provider, NOW) == 1

    fair_yes = no_vig_market([1.75, 2.05], "power").no_vig_probabilities[0]
    assert _closing_market(shadow_db.db_path) == {prediction_id: pytest.approx(fair_yes)}
    assert shadow.errors == []


def test_incomplete_partition_is_recorded_without_probability(shadow_db):
    prediction_id = _record(shadow_db.tracker)
    bets = [{"name": "Both Teams Score", "values": [{"value": "Yes", "odd": "1.75"}]}]
    provider = SimpleNamespace(odds=lambda *a, **k: _odds_response(
        bets=bets, updated_at=(NOW - timedelta(minutes=95)).isoformat()))

    assert shadow.step_closing(shadow_db.tracker, provider, NOW) == 1
    assert _closing_market(shadow_db.db_path) == {prediction_id: None}


def _closed(db_path, prediction_id, *, probability, closing_stamp="2030-01-01T12:00:00+00:00"):
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE predictions SET closing_odds = 1.70, quoted_at = ?, closing_quoted_at = ? "
                           "WHERE id = ?", ("2030-01-01T10:00:00+00:00", closing_stamp, prediction_id))
        connection.execute("INSERT INTO shadow_closing_market VALUES (?, ?, ?)", (prediction_id, probability, "t"))


def test_statistics_per_cohort_and_paired_difference(shadow_db):
    shadow._connect().close()
    legacy = _record(shadow_db.tracker, fixture_id=1, odds=2.00)
    hybrid = _record(shadow_db.tracker, fixture_id=1, odds=2.10, model_version=shadow.SHADOW_HYBRID_MODEL_VERSION)
    repeated = _record(shadow_db.tracker, fixture_id=2, odds=2.00)
    unpriced = _record(shadow_db.tracker, fixture_id=3, odds=2.00)
    _closed(shadow_db.db_path, legacy, probability=0.52)
    _closed(shadow_db.db_path, hybrid, probability=0.52)
    _closed(shadow_db.db_path, repeated, probability=0.52, closing_stamp="2030-01-01T10:00:00+00:00")
    _closed(shadow_db.db_path, unpriced, probability=None)

    stats = shadow._no_vig_clv_statistics()

    cohort = stats["cohorts"][shadow.SHADOW_MODEL_VERSION]
    assert cohort["clv"]["n"] == 1 and cohort["clv"]["mean"] == pytest.approx(4.0)
    assert cohort["without_market"] == 1 and cohort["without_new_market_state"] == 1
    assert stats["cohorts"][shadow.SHADOW_HYBRID_MODEL_VERSION]["clv"]["mean"] == pytest.approx(9.2)
    assert stats["paired_difference"]["n"] == 1 and stats["paired_difference"]["mean"] == pytest.approx(5.2)
