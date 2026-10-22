"""Edge-cap research record in the shadow path (never a filter).

Plan: docs/superpowers/plans/2026-10-21-edge-cap.md, step 1 of the check
plan: per logged tip the shadow records the no-vig market probability from
the same Bet365 partition, the model/market distance and whether the
pre-registered 8 pp cap would have passed. ``BETBOY_EDGE_CAP_PP`` stays unset.
"""
from datetime import date, datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

import challenge_engine as engine
import shadow_clv_automation as shadow
from betting_math import power_no_vig_market, shin_no_vig_market
from clv_tracker import CLVTracker
from tests.test_shadow_markets import _odds_response


def test_no_vig_probability_uses_the_complete_partition_of_the_tipped_side():
    response = _odds_response()
    shin = shin_no_vig_market([1.85, 3.60, 4.20]).no_vig_probabilities
    assert shadow._no_vig_market_probability(response, "RESULT_HOME") == pytest.approx(shin[0])
    assert shadow._no_vig_market_probability(response, "RESULT_AWAY") == pytest.approx(shin[2])
    assert shadow._no_vig_market_probability(response, "DC_1X") == pytest.approx(shin[0] + shin[1])
    power = power_no_vig_market([1.90, 1.91]).no_vig_probabilities
    assert shadow._no_vig_market_probability(response, "TOTAL_OVER_2_5") == pytest.approx(power[0])
    assert shadow._no_vig_market_probability(response, "TOTAL_UNDER_2_5") == pytest.approx(power[1])
    btts = power_no_vig_market([1.75, 2.05]).no_vig_probabilities
    assert shadow._no_vig_market_probability(response, "BTTS_NO") == pytest.approx(btts[1])
    # One-sided quotes are not a market: Under 0.5 is missing, so no probability.
    assert shadow._no_vig_market_probability(response, "TOTAL_OVER_0_5") is None
    assert shadow._no_vig_market_probability(_odds_response(bookmaker_name="Other"), "RESULT_HOME") is None
    assert shadow._no_vig_market_probability(None, "RESULT_HOME") is None
    assert shadow._no_vig_market_probability(response, "CORNERS_OVER_9_5") is None


def _candidate(probability, market_key="RESULT_HOME"):
    return SimpleNamespace(base_eligible=True, market_key=market_key, selection="Heim", probability=probability,
                           evidence_score=80.0, blocked_reasons=[], context={"passed": True})


class _Provider:
    def __init__(self, response):
        self.response = response

    def fixture_details(self, fixture_id):
        return {"fixture": {"id": fixture_id}, "teams": {"home": {"id": 1}, "away": {"id": 2}}}

    def coverage(self, league_id, season):
        return {"injuries": False, "lineups": False}

    def h2h(self, home_id, away_id):
        return []

    def injuries(self, fixture_id):
        return []

    def weather(self, detail):
        return None

    def odds(self, fixture_id, **_):
        return self.response


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.db"
    tracker = CLVTracker(db_path=str(db_path))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE shadow_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE shadow_fixtures (fixture_id INTEGER PRIMARY KEY, zurich_date TEXT, "
                           "league_id INTEGER, season INTEGER, home_team TEXT, away_team TEXT, kickoff TEXT, "
                           "evaluated INTEGER)")
        connection.execute("INSERT INTO shadow_fixtures VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                           (91, date.today().isoformat(), 39, 2026, "Home FC", "Away FC",
                            shadow._utc_iso(now + timedelta(minutes=40))))
    monkeypatch.setattr(shadow, "SHADOW_DB", db_path)
    shadow._connect().close()  # creates the shadow_edge_cap table like the runner does
    monkeypatch.setattr(shadow, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    shadow.errors.clear()
    monkeypatch.setattr(shadow, "_cached_history", lambda *args, **kwargs: [{"fixture": {"id": 1}}])
    monkeypatch.setattr(shadow, "_cached_validation", lambda *args, **kwargs: {})
    monkeypatch.setattr(shadow, "_cached_calibration", lambda *args, **kwargs: {})
    monkeypatch.setattr(shadow, "apply_candidate_context", lambda candidate, **kwargs: None)
    monkeypatch.setattr(shadow, "candidate_is_forecast_credible", lambda candidate: True)
    monkeypatch.setattr(shadow, "candidate_selection_rank", lambda candidate: 0.0)
    return SimpleNamespace(tracker=tracker, db_path=db_path, now=now)


def _edge_rows(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT e.model_version, e.model_probability, e.market_probability, e.edge_pp, e.cap_pp, e.passed "
            "FROM shadow_edge_cap e JOIN predictions p ON p.id = e.prediction_id ORDER BY e.prediction_id").fetchall()


def test_every_logged_tip_records_its_cap_verdict_without_filtering(ledger, monkeypatch):
    def build(detail, history, validation, calibration, **kwargs):
        basis = kwargs.get("goal_model", engine.GOAL_MODEL_LEGACY)
        # Legacy tip far above the market (fails the cap), hybrid tip close to it (passes).
        return [_candidate(0.68 if basis == engine.GOAL_MODEL_LEGACY else 0.55)]

    monkeypatch.setattr(shadow, "build_fixture_candidates", build)
    quoted_at = ledger.now - timedelta(minutes=1)
    response = _odds_response(updated_at=quoted_at.isoformat())
    result = shadow.step_evaluate(ledger.tracker, _Provider(response), ledger.now, date.today(), 10)
    assert result["logged"] == 1 and result["hybrid_logged"] == 1 and shadow.errors == []
    rows = _edge_rows(ledger.db_path)
    market = shin_no_vig_market([1.85, 3.60, 4.20]).no_vig_probabilities[0]
    assert [row[0] for row in rows] == [shadow.SHADOW_MODEL_VERSION, shadow.SHADOW_HYBRID_MODEL_VERSION]
    assert rows[0][1] == 0.68 and rows[0][2] == pytest.approx(market)
    assert rows[0][3] == pytest.approx(100.0 * (0.68 - market)) and rows[0][4] == 8.0 and rows[0][5] == 0
    assert rows[1][3] == pytest.approx(100.0 * (0.55 - market)) and rows[1][5] == 1
    # Both ledger rows exist regardless of the verdict: the cap is recorded, never applied.
    with sqlite3.connect(ledger.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 2


def test_missing_partition_is_recorded_as_unknown_and_never_blocks_the_ledger(ledger, monkeypatch):
    monkeypatch.setenv(shadow.SHADOW_HYBRID_FLAG, "0")
    monkeypatch.setattr(shadow, "build_fixture_candidates",
                        lambda *args, **kwargs: [_candidate(0.9, "TOTAL_OVER_0_5")])
    quoted_at = ledger.now - timedelta(minutes=1)
    response = _odds_response(updated_at=quoted_at.isoformat())
    result = shadow.step_evaluate(ledger.tracker, _Provider(response), ledger.now, date.today(), 10)
    assert result["logged"] == 1 and shadow.errors == []
    rows = _edge_rows(ledger.db_path)
    assert len(rows) == 1 and rows[0][2] is None and rows[0][3] is None and rows[0][5] is None


def test_edge_cap_statistics_separate_cohorts_and_cap_groups(ledger):
    with sqlite3.connect(ledger.db_path) as connection:
        predictions = [
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.8, "WIN", "x", shadow.SHADOW_MODEL_VERSION),
            (2, "C", "D", "RESULT_HOME", "Heim", 2.0, 2.2, "LOSS", "x", shadow.SHADOW_MODEL_VERSION),
            (3, "E", "F", "RESULT_HOME", "Heim", 2.0, None, None, "x", shadow.SHADOW_MODEL_VERSION),
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.9, "WIN", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
        ]
        connection.executemany(
            "INSERT INTO predictions (fixture_id, home_team, away_team, market_type, prediction, odds, "
            "closing_odds, result, created_at, model_version, policy_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(*row, shadow.SHADOW_POLICY_VERSION) for row in predictions])
        ids = [row[0] for row in connection.execute("SELECT id FROM predictions ORDER BY id")]
        connection.executemany(
            "INSERT INTO shadow_edge_cap VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(ids[0], shadow.SHADOW_MODEL_VERSION, 0.55, 0.50, 5.0, 8.0, 1, "t"),
             (ids[1], shadow.SHADOW_MODEL_VERSION, 0.70, 0.50, 20.0, 8.0, 0, "t"),
             (ids[2], shadow.SHADOW_MODEL_VERSION, 0.60, None, None, 8.0, None, "t"),
             (ids[3], shadow.SHADOW_HYBRID_MODEL_VERSION, 0.56, 0.50, 6.0, 8.0, 1, "t")])
    stats = shadow._edge_cap_statistics()
    assert stats["cap_pp"] == 8.0 and stats["applied"] is False
    legacy = stats["cohorts"][shadow.SHADOW_MODEL_VERSION]
    assert (legacy["recorded"], legacy["passed"], legacy["failed"], legacy["unknown"]) == (3, 1, 1, 1)
    assert legacy["closed_passed"] == 1 and legacy["closed_failed"] == 1
    assert legacy["passed_avg_clv"] == pytest.approx(round((2.0 / 1.8 - 1) * 100, 2))
    assert legacy["failed_avg_clv"] == pytest.approx(round((2.0 / 2.2 - 1) * 100, 2))
    assert legacy["passed_hit_rate"] == 1.0 and legacy["failed_hit_rate"] == 0.0
    hybrid = stats["cohorts"][shadow.SHADOW_HYBRID_MODEL_VERSION]
    assert hybrid["recorded"] == 1 and hybrid["passed"] == 1 and hybrid["closed_passed"] == 1
    assert stats["minimum_closed_per_group"] == shadow.SHADOW_REVIEW_MIN_CLV_BETS


def test_production_edge_cap_flag_stays_unset_by_the_shadow(monkeypatch):
    from market_consensus import EDGE_CAP_FLAG, edge_cap_pp
    monkeypatch.delenv(EDGE_CAP_FLAG, raising=False)
    assert edge_cap_pp() is None
    assert shadow.SHADOW_EDGE_CAP_PP == 8.0
