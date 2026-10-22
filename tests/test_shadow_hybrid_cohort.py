"""Second shadow cohort (coherent hybrid) next to the legacy ledger.

Plan: docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md. Both cohorts
see the same fixture and the same quote response; the legacy row is written
first and never depends on the hybrid; the flag ``BETBOY_SHADOW_HYBRID_BASIS=0``
switches the cohort off.
"""
from datetime import date, datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

import challenge_engine as engine
import shadow_clv_automation as shadow
from clv_tracker import CLVTracker

HYBRID = engine.GOAL_MODEL_SHADOW_CANDIDATE


def _candidate(market_key="RESULT_HOME", probability=0.62):
    return SimpleNamespace(base_eligible=True, market_key=market_key, selection="Heim", probability=probability,
                           evidence_score=80.0, blocked_reasons=[], context={"passed": True})


class _Provider:
    def __init__(self):
        self.odds_calls = 0

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
        self.odds_calls += 1
        return [{"bookmakers": []}]


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.db"
    tracker = CLVTracker(db_path=str(db_path))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    kickoff = now + timedelta(minutes=40)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE shadow_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE shadow_fixtures (fixture_id INTEGER PRIMARY KEY, zurich_date TEXT, "
                           "league_id INTEGER, season INTEGER, home_team TEXT, away_team TEXT, kickoff TEXT, "
                           "evaluated INTEGER)")
        connection.execute("INSERT INTO shadow_fixtures VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                           (91, date.today().isoformat(), 39, 2026, "Home FC", "Away FC",
                            shadow._utc_iso(kickoff)))
    monkeypatch.setattr(shadow, "SHADOW_DB", db_path)
    monkeypatch.setattr(shadow, "CACHE_DIR", tmp_path / "cache")
    shadow.errors.clear()
    calls = {"validation": [], "candidates": []}
    monkeypatch.setattr(shadow, "_cached_history", lambda *args, **kwargs: [{"fixture": {"id": 1}}])

    def cached_validation(league_id, season, history, day, goal_model=engine.GOAL_MODEL_LEGACY):
        calls["validation"].append(goal_model)
        return {}

    monkeypatch.setattr(shadow, "_cached_validation", cached_validation)
    monkeypatch.setattr(shadow, "_cached_calibration", lambda *args, **kwargs: {})

    def build(detail, history, validation, calibration, **kwargs):
        calls["candidates"].append(kwargs.get("goal_model", engine.GOAL_MODEL_LEGACY))
        return [_candidate()]

    monkeypatch.setattr(shadow, "build_fixture_candidates", build)
    monkeypatch.setattr(shadow, "apply_candidate_context", lambda candidate, **kwargs: None)
    monkeypatch.setattr(shadow, "candidate_is_forecast_credible", lambda candidate: True)
    monkeypatch.setattr(shadow, "_model_first_observations",
                        lambda credible, odds_response, now: [(credible[0], 1.9, now - timedelta(minutes=1))]
                        if odds_response is not None else [])
    return SimpleNamespace(tracker=tracker, db_path=db_path, now=now, calls=calls)


def _rows(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT fixture_id, model_version, policy_version, odds FROM predictions ORDER BY id").fetchall()


def test_versions_and_cache_names_separate_the_two_bases():
    assert shadow.SHADOW_MODEL_VERSION == engine.CHALLENGE_PREDICTION_VERSION.replace(":", "-")
    assert shadow.SHADOW_HYBRID_MODEL_VERSION == engine.prediction_version_for_goal_model(HYBRID).replace(":", "-")
    assert shadow.SHADOW_HYBRID_MODEL_VERSION != shadow.SHADOW_MODEL_VERSION
    legacy = shadow._cache_path("validation", 39, 2030, "2030-01-01")
    hybrid = shadow._cache_path("validation", 39, 2030, "2030-01-01", shadow._basis_cache_version(HYBRID))
    assert legacy.name != hybrid.name and shadow._basis_cache_version(engine.GOAL_MODEL_LEGACY) is None


def test_hybrid_cohort_logs_a_second_row_from_the_same_quote_response(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    provider = _Provider()
    result = shadow.step_evaluate(ledger.tracker, provider, ledger.now, date.today(), 10)
    rows = _rows(ledger.db_path)
    assert [row[1] for row in rows] == [shadow.SHADOW_MODEL_VERSION, shadow.SHADOW_HYBRID_MODEL_VERSION]
    assert {row[2] for row in rows} == {shadow.SHADOW_POLICY_VERSION}
    assert provider.odds_calls == 1  # one quote response for both cohorts
    assert result["logged"] == 1 and result["hybrid_logged"] == 1 and result["evaluated"] == 1
    assert ledger.calls["candidates"] == [engine.GOAL_MODEL_LEGACY, HYBRID]
    assert ledger.calls["validation"] == [engine.GOAL_MODEL_LEGACY, HYBRID]
    assert shadow.errors == []


def test_flag_zero_switches_the_hybrid_cohort_off(ledger, monkeypatch):
    monkeypatch.setenv(shadow.SHADOW_HYBRID_FLAG, "0")
    assert shadow.hybrid_cohort_enabled() is False
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION]
    assert "hybrid_logged" not in result and ledger.calls["candidates"] == [engine.GOAL_MODEL_LEGACY]


def test_hybrid_failure_never_blocks_the_legacy_ledger(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)

    def failing_validation(league_id, season, history, day, goal_model=engine.GOAL_MODEL_LEGACY):
        if goal_model != engine.GOAL_MODEL_LEGACY:
            raise RuntimeError("Dixon-Coles walk-forward unavailable")
        return {}

    monkeypatch.setattr(shadow, "_cached_validation", failing_validation)
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION]
    assert result["logged"] == 1 and result["evaluated"] == 1
    assert any(message.startswith("Hybrid 91:") for message in shadow.errors)


def test_senior_internationals_have_no_hybrid_cohort(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    with sqlite3.connect(ledger.db_path) as connection:
        connection.execute("UPDATE shadow_fixtures SET league_id = 5")
    shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION]
    assert ledger.calls["candidates"] == [engine.GOAL_MODEL_LEGACY]


def test_hybrid_without_quote_keeps_the_fixture_open_until_the_final_retry(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)

    def build(detail, history, validation, calibration, **kwargs):
        basis = kwargs.get("goal_model", engine.GOAL_MODEL_LEGACY)
        ledger.calls["candidates"].append(basis)
        return [] if basis == engine.GOAL_MODEL_LEGACY else [_candidate()]

    monkeypatch.setattr(shadow, "build_fixture_candidates", build)
    monkeypatch.setattr(shadow, "_model_first_observations", lambda credible, odds_response, now: [])
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert _rows(ledger.db_path) == []
    assert result["evaluated"] == 0 and result.get("deferred") == 1
    assert result["hybrid_quote_missing"] == 1


def test_warm_up_builds_hybrid_artifacts_once_per_league(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    built = []

    def cached_validation(league_id, season, history, day, goal_model=engine.GOAL_MODEL_LEGACY):
        built.append(("validation", league_id, goal_model))
        path = shadow._cache_path("validation", league_id, season, day, shadow._basis_cache_version(goal_model))
        path.write_bytes(b"x")
        return {}

    def cached_calibration(league_id, season, history, day, goal_model=engine.GOAL_MODEL_LEGACY):
        built.append(("calibration", league_id, goal_model))
        path = shadow._cache_path("calibration", league_id, season, day, shadow._basis_cache_version(goal_model))
        path.write_bytes(b"x")
        return {}

    monkeypatch.setattr(shadow, "_cached_validation", cached_validation)
    monkeypatch.setattr(shadow, "_cached_calibration", cached_calibration)
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == 1
    assert built == [("validation", 39, HYBRID), ("calibration", 39, HYBRID)]
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == 0  # cache hit, nothing rebuilt
    monkeypatch.setenv(shadow.SHADOW_HYBRID_FLAG, "0")
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == 0


def test_paired_statistics_compare_only_fixtures_closed_in_both_cohorts(ledger):
    with sqlite3.connect(ledger.db_path) as connection:
        rows = [
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.8, "WIN", "x", shadow.SHADOW_MODEL_VERSION),
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.9, "WIN", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
            (2, "C", "D", "TOTAL_OVER_2_5", "Über", 1.9, 2.0, "LOSS", "x", shadow.SHADOW_MODEL_VERSION),
            (2, "C", "D", "RESULT_AWAY", "Auswärts", 2.2, 2.0, "WIN", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
            (3, "E", "F", "RESULT_HOME", "Heim", 2.0, None, None, "x", shadow.SHADOW_MODEL_VERSION),
            (3, "E", "F", "RESULT_HOME", "Heim", 2.0, 1.9, "WIN", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
        ]
        connection.executemany(
            "INSERT INTO predictions (fixture_id, home_team, away_team, market_type, prediction, odds, "
            "closing_odds, result, created_at, model_version, policy_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(*row, shadow.SHADOW_POLICY_VERSION) for row in rows])
    paired = shadow._paired_cohort_statistics()
    assert paired["pairs"] == 2 and paired["same_selection"] == 1
    assert paired["legacy_avg_clv"] == pytest.approx(round(((2.0 / 1.8 - 1) * 100 + (1.9 / 2.0 - 1) * 100) / 2, 2))
    assert paired["hybrid_avg_clv"] == pytest.approx(round(((2.0 / 1.9 - 1) * 100 + (2.2 / 2.0 - 1) * 100) / 2, 2))
    assert paired["legacy_hit_rate"] == 0.5 and paired["hybrid_hit_rate"] == 1.0
    assert paired["minimum_pairs"] == shadow.SHADOW_REVIEW_MIN_CLV_BETS
