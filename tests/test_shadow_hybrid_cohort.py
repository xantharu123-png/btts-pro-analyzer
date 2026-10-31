"""Second shadow cohort (coherent hybrid) next to the legacy ledger.

Plan: docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md. Both cohorts
see the same fixture and the same quote response; the legacy row is written
first and never depends on the hybrid; the flag ``BETBOY_SHADOW_HYBRID_BASIS=0``
switches the cohort off.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

import challenge_engine as engine
import shadow_clv_automation as shadow
from clv_tracker import CLVTracker

HYBRID = engine.GOAL_MODEL_SHADOW_CANDIDATE
_REAL_LOAD_HYBRID_ARTIFACTS = shadow._load_hybrid_artifacts


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
    calls = {"validation": [], "candidates": [], "hybrid_loads": 0}
    monkeypatch.setattr(shadow, "_cached_history", lambda *args, **kwargs: [{"fixture": {"id": 1}}])

    def cached_validation(league_id, season, history, day, goal_model=engine.GOAL_MODEL_LEGACY):
        calls["validation"].append(goal_model)
        return {}

    monkeypatch.setattr(shadow, "_cached_validation", cached_validation)
    monkeypatch.setattr(shadow, "_cached_calibration", lambda *args, **kwargs: {})

    def load_hybrid(league_id, season, day):
        calls["hybrid_loads"] += 1
        return {}, {}

    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", load_hybrid)

    def build(detail, history, validation, calibration, **kwargs):
        calls["candidates"].append(kwargs.get("goal_model", engine.GOAL_MODEL_LEGACY))
        return [_candidate()]

    monkeypatch.setattr(shadow, "build_fixture_candidates", build)
    monkeypatch.setattr(shadow, "apply_candidate_context", lambda candidate, **kwargs: None)
    monkeypatch.setattr(shadow, "candidate_is_forecast_credible", lambda candidate: True)
    monkeypatch.setattr(shadow, "candidate_selection_rank", lambda candidate: (candidate.probability,))
    monkeypatch.setattr(shadow, "_model_first_observations",
                        lambda credible, odds_response, now: [(credible[0], 1.9, now - timedelta(minutes=1))]
                        if odds_response is not None else [])
    return SimpleNamespace(tracker=tracker, db_path=db_path, now=now, calls=calls)


def _rows(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT fixture_id, model_version, policy_version, odds FROM predictions ORDER BY id").fetchall()


def _unpriced(db_path):
    with shadow._connect() as connection:
        return connection.execute(
            "SELECT fixture_id, model_version, policy_version, market_key, reason FROM shadow_unpriced "
            "ORDER BY id").fetchall()


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
    assert ledger.calls["validation"] == [engine.GOAL_MODEL_LEGACY] and ledger.calls["hybrid_loads"] == 1
    assert shadow.errors == []


def test_flag_zero_switches_the_hybrid_cohort_off(ledger, monkeypatch):
    monkeypatch.setenv(shadow.SHADOW_HYBRID_FLAG, "0")
    assert shadow.hybrid_cohort_enabled() is False
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION]
    assert "hybrid_logged" not in result and ledger.calls["candidates"] == [engine.GOAL_MODEL_LEGACY]


def test_hybrid_failure_never_blocks_the_legacy_ledger(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)

    def failing_load(league_id, season, day):
        raise RuntimeError("hybrid artifact unreadable")

    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", failing_load)
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
    assert ledger.calls["candidates"] == [engine.GOAL_MODEL_LEGACY] and ledger.calls["hybrid_loads"] == 0


def test_hybrid_without_artifacts_defers_the_fixture_until_the_league_is_built(ledger, monkeypatch):
    """Massnahme 2 (25.10.2026): the legacy row is logged at once, the fixture stays open for the hybrid."""
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", lambda league_id, season, day: None)
    provider = _Provider()
    result = shadow.step_evaluate(ledger.tracker, provider, ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION]
    assert result["logged"] == 1 and result["evaluated"] == 0 and result.get("deferred") == 1
    assert result["hybrid_not_ready"] == 1 and "hybrid_logged" not in result
    assert ledger.calls["candidates"] == [engine.GOAL_MODEL_LEGACY] and shadow.errors == []
    # The next run finds the artifacts: the hybrid row is logged from a fresh quote, the legacy
    # row is never duplicated and the fixture closes.
    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", lambda league_id, season, day: ({}, {}))
    result = shadow.step_evaluate(ledger.tracker, provider, ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION,
                                                         shadow.SHADOW_HYBRID_MODEL_VERSION]
    assert result["logged"] == 0 and result["hybrid_logged"] == 1 and result["evaluated"] == 1
    assert provider.odds_calls == 2 and shadow.errors == []


def test_failed_hybrid_build_never_keeps_a_fixture_open(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", lambda league_id, season, day: None)
    with shadow._connect() as connection:
        shadow._meta_set(connection, shadow._hybrid_build_marker(date.today().isoformat(), 39, 2026), "t")
        connection.commit()
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION]
    assert result["evaluated"] == 1 and result["hybrid_not_ready"] == 1 and "deferred" not in result


def test_hybrid_without_quote_above_the_model_guard_keeps_the_fixture_open(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)

    def build(detail, history, validation, calibration, **kwargs):
        basis = kwargs.get("goal_model", engine.GOAL_MODEL_LEGACY)
        ledger.calls["candidates"].append(basis)
        return [] if basis == engine.GOAL_MODEL_LEGACY else [_candidate(probability=0.70)]

    monkeypatch.setattr(shadow, "build_fixture_candidates", build)
    monkeypatch.setattr(shadow, "_model_first_observations", lambda credible, odds_response, now: [])
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert _rows(ledger.db_path) == [] and _unpriced(ledger.db_path) == []
    assert result["evaluated"] == 0 and result.get("deferred") == 1
    assert result["hybrid_quote_missing"] == 1


def test_warm_up_builds_both_hybrid_artifacts_in_one_pass_within_the_budget(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", _REAL_LOAD_HYBRID_ARTIFACTS)
    passes = []

    def one_pass(history, goal_model=engine.GOAL_MODEL_LEGACY):
        passes.append(goal_model)
        return {"RESULT_HOME": "validation"}, {"RESULT_HOME": "calibration"}

    monkeypatch.setattr(shadow, "build_market_model_artifact", one_pass)
    idle = {"warmed": 0, "cached": 0, "failed": 0, "pending": 0}
    assert shadow.step_warm_hybrid(_Provider(), date.today(), budget_seconds=0.0) == {**idle, "pending": 1}
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == {**idle, "warmed": 1}
    assert passes == [HYBRID]  # validation and calibration from one walk-forward
    assert shadow._load_hybrid_artifacts(39, 2026, date.today().isoformat()) == (
        {"RESULT_HOME": "validation"}, {"RESULT_HOME": "calibration"})
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == {**idle, "cached": 1} and passes == [HYBRID]
    monkeypatch.setenv(shadow.SHADOW_HYBRID_FLAG, "0")
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == idle


def test_failed_warm_up_marks_the_league_for_the_day_and_is_not_retried(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "_load_hybrid_artifacts", _REAL_LOAD_HYBRID_ARTIFACTS)
    attempts = []

    def failing(history, goal_model=engine.GOAL_MODEL_LEGACY):
        attempts.append(goal_model)
        raise RuntimeError("walk-forward failed")

    monkeypatch.setattr(shadow, "build_market_model_artifact", failing)
    day = date.today().isoformat()
    failed = {"warmed": 0, "cached": 0, "failed": 1, "pending": 0}
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == failed
    assert shadow._hybrid_build_failed(day, 39, 2026) is True
    assert any(message.startswith("Hybrid-Vorbereitung Liga 39:") for message in shadow.errors)
    assert shadow.step_warm_hybrid(_Provider(), date.today()) == failed and attempts == [HYBRID]


def test_warm_up_builds_the_league_with_the_earliest_kick_off_first(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    with sqlite3.connect(ledger.db_path) as connection:
        connection.execute("INSERT INTO shadow_fixtures VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                           (92, date.today().isoformat(), 140, 2026, "C", "D",
                            shadow._utc_iso(ledger.now + timedelta(minutes=10))))
    built = []
    monkeypatch.setattr(shadow, "_build_hybrid_artifacts",
                        lambda league_id, season, history, day: built.append(league_id))
    assert shadow.step_warm_hybrid(_Provider(), date.today())["warmed"] == 2
    assert built == [140, 39]


def test_paired_statistics_compare_only_fixtures_closed_in_both_cohorts(ledger):
    with sqlite3.connect(ledger.db_path) as connection:
        rows = [
            # Results exactly as CLVTracker.settle_prediction stores them ('Won'/'Lost'/'Push').
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.8, "Won", "x", shadow.SHADOW_MODEL_VERSION),
            (1, "A", "B", "RESULT_HOME", "Heim", 2.0, 1.9, "Won", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
            (2, "C", "D", "TOTAL_OVER_2_5", "Über", 1.9, 2.0, "Lost", "x", shadow.SHADOW_MODEL_VERSION),
            (2, "C", "D", "RESULT_AWAY", "Auswärts", 2.2, 2.0, "Won", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
            (3, "E", "F", "RESULT_HOME", "Heim", 2.0, None, None, "x", shadow.SHADOW_MODEL_VERSION),
            (3, "E", "F", "RESULT_HOME", "Heim", 2.0, 1.9, "Won", "x", shadow.SHADOW_HYBRID_MODEL_VERSION),
        ]
        # Closing stamps are a later market state than the opening (contract of 28.10.2026).
        connection.executemany(
            "INSERT INTO predictions (fixture_id, home_team, away_team, market_type, prediction, odds, "
            "closing_odds, result, created_at, model_version, policy_version, quoted_at, closing_quoted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(*row, shadow.SHADOW_POLICY_VERSION, "2030-01-01T10:00:00+00:00",
              "2030-01-01T12:00:00+00:00" if row[6] is not None else None) for row in rows])
    paired = shadow._paired_cohort_statistics()
    assert paired["pairs"] == 2 and paired["same_selection"] == 1
    assert paired["legacy_avg_clv"] == pytest.approx(round(((2.0 / 1.8 - 1) * 100 + (1.9 / 2.0 - 1) * 100) / 2, 2))
    assert paired["hybrid_avg_clv"] == pytest.approx(round(((2.0 / 1.9 - 1) * 100 + (2.2 / 2.0 - 1) * 100) / 2, 2))
    assert paired["legacy_hit_rate"] == 0.5 and paired["hybrid_hit_rate"] == 1.0
    assert paired["minimum_pairs"] == shadow.SHADOW_REVIEW_MIN_CLV_BETS
    # Pre-registered criterion: HAC interval of the paired difference (hybrid minus legacy), chronological.
    difference = paired["difference"]
    assert difference["n"] == 2 and difference["mean"] == paired["avg_difference"]
    assert difference["hac_standard_error"] > 0 and difference["lower_bound"] < difference["mean"]
    assert 0.0 <= difference["p_value"] <= 1.0


def test_a_tip_needs_an_opening_quote_of_at_least_1_30():
    # Owner decision 30.10.2026 (docs/audits/2026-10-30-shadow-mindestquote.md): the minimum
    # filters, the model-first order of the remaining candidates stays.
    assert shadow.SHADOW_MIN_ODDS == 1.30  # since policy v9, unchanged under v10 and v11
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    first, second, third = _candidate("TOTAL_OVER_1_5"), _candidate("RESULT_HOME"), _candidate("BTTS_YES")
    observed = [(first, 1.17, now), (second, 1.3, now), (third, 1.85, now)]
    assert shadow._at_minimum_odds(observed) == [(second, 1.3, now), (third, 1.85, now)]
    source = Path(shadow.__file__).read_text(encoding="utf-8")
    assert '"minimum_odds": SHADOW_MIN_ODDS' in source and source.count('"fixtures_below_minimum_odds"') == 2


def test_both_cohorts_take_the_best_ranked_candidate_at_the_minimum(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "build_fixture_candidates",
                        lambda *args, **kwargs: [_candidate("TOTAL_OVER_1_5"), _candidate("BTTS_YES")])
    monkeypatch.setattr(shadow, "_model_first_observations", lambda credible, odds_response, now: [
        (credible[0], 1.17, now - timedelta(minutes=1)), (credible[1], 1.85, now - timedelta(minutes=1))])
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    with sqlite3.connect(ledger.db_path) as connection:
        rows = connection.execute("SELECT model_version, market_type, odds FROM predictions ORDER BY id").fetchall()
    assert rows == [(shadow.SHADOW_MODEL_VERSION, "BTTS_YES", 1.85),
                    (shadow.SHADOW_HYBRID_MODEL_VERSION, "BTTS_YES", 1.85)]
    assert result["logged"] == 1 and result["hybrid_logged"] == 1 and result["evaluated"] == 1
    assert "below_minimum_odds" not in result and shadow.errors == []


def test_quotes_all_below_the_minimum_log_no_tip_and_keep_the_fixture_open(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "_model_first_observations",
                        lambda credible, odds_response, now: [(credible[0], 1.25, now - timedelta(minutes=1))])
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert _rows(ledger.db_path) == []
    assert result["below_minimum_odds"] == 1 and result["hybrid_below_minimum_odds"] == 1
    assert "quote_missing" not in result and "hybrid_quote_missing" not in result
    # No data problem, so no error; the fixture is retried like any fixture without a tip.
    assert shadow.errors == [] and result["evaluated"] == 0 and result.get("deferred") == 1


# Policy v11 (31.10.2026, owner decision, docs/audits/2026-10-31-shadow-tipps-ohne-quote.md):
# a fixture without a priced pick still gets a tip under the app's model guard.

def test_model_guard_is_the_apps_and_all_goal_markets_are_candidates():
    import market_consensus

    assert shadow.SHADOW_UNPRICED_MAX_PROBABILITY == market_consensus.FLOOR_UNPRICED_MAX_PROBABILITY
    goal = {key for key, spec in engine.MARKET_BY_KEY.items() if spec.kind not in engine.COUNT_MARKET_KINDS}
    assert {key for key in engine.MARKET_BY_KEY if shadow._shadow_market(key)} == goal
    assert len(goal) == 46 and set(shadow._QUOTE_BETS) < goal
    assert not shadow._shadow_market("HOME_CORNERS_OVER_4_5") and not shadow._shadow_market(None)
    for key in goal:  # every candidate market settles from the full-time score
        assert isinstance(engine.market_outcome(engine.MARKET_BY_KEY[key], 2, 1), bool)
        assert isinstance(engine.market_outcome(engine.MARKET_BY_KEY[key], 0, 0), bool)


def test_unpriced_candidates_skip_quoted_ones_and_the_model_guard(monkeypatch):
    monkeypatch.setattr(shadow, "candidate_selection_rank", lambda candidate: (candidate.probability,))
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    quoted_low = _candidate("RESULT_HOME", 0.60)
    stale = _candidate("BTTS_YES", 0.55)
    team_total = _candidate("HOME_OVER_1_5", 0.58)
    sure = _candidate("TOTAL_OVER_0_5", 0.90)
    observed = [(quoted_low, 1.20, now)]  # a fresh quote under the minimum keeps the candidate out
    assert shadow._unpriced_candidates([quoted_low, stale, team_total, sure], observed) == [
        (team_total, "no_bet365_market"), (stale, "no_fresh_bet365_quote")]
    assert shadow._unpriced_candidates([_candidate(probability=0.65)], []) == []


def test_both_cohorts_log_an_unpriced_tip_without_a_bet365_quote(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "_model_first_observations", lambda credible, odds_response, now: [])
    provider = _Provider()
    result = shadow.step_evaluate(ledger.tracker, provider, ledger.now, date.today(), 10)
    assert _rows(ledger.db_path) == []
    assert _unpriced(ledger.db_path) == [
        (91, shadow.SHADOW_MODEL_VERSION, shadow.SHADOW_POLICY_VERSION, "RESULT_HOME", "no_fresh_bet365_quote"),
        (91, shadow.SHADOW_HYBRID_MODEL_VERSION, shadow.SHADOW_POLICY_VERSION, "RESULT_HOME", "no_fresh_bet365_quote")]
    assert result["unpriced_logged"] == 1 and result["hybrid_unpriced_logged"] == 1
    assert result["evaluated"] == 1 and "deferred" not in result and "quote_missing" not in result
    assert provider.odds_calls == 1 and shadow.errors == []
    # One tip per fixture and cohort: a later quote never adds a priced row.
    with sqlite3.connect(ledger.db_path) as connection:
        connection.execute("UPDATE shadow_fixtures SET evaluated = 0")
    monkeypatch.setattr(shadow, "_model_first_observations",
                        lambda credible, odds_response, now: [(credible[0], 1.9, now - timedelta(minutes=1))])
    result = shadow.step_evaluate(ledger.tracker, provider, ledger.now, date.today(), 10)
    assert _rows(ledger.db_path) == [] and len(_unpriced(ledger.db_path)) == 2
    assert result["logged"] == 0 and "unpriced_logged" not in result and result["evaluated"] == 1


def test_markets_without_a_bet365_mapping_need_no_quote_request(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "build_fixture_candidates",
                        lambda *args, **kwargs: [_candidate("HOME_OVER_1_5", 0.58)])
    provider = _Provider()
    result = shadow.step_evaluate(ledger.tracker, provider, ledger.now, date.today(), 10)
    assert provider.odds_calls == 0
    assert [row[3:] for row in _unpriced(ledger.db_path)] == [("HOME_OVER_1_5", "no_bet365_market")] * 2
    assert result["unpriced_logged"] == 1 and result["hybrid_unpriced_logged"] == 1


def test_a_priced_pick_comes_before_an_unpriced_one(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "build_fixture_candidates",
                        lambda *args, **kwargs: [_candidate("HOME_OVER_1_5", 0.58), _candidate("RESULT_HOME")])
    monkeypatch.setattr(shadow, "_model_first_observations", lambda credible, odds_response, now: [
        (credible[1], 1.9, now - timedelta(minutes=1))])
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert [row[1] for row in _rows(ledger.db_path)] == [shadow.SHADOW_MODEL_VERSION,
                                                         shadow.SHADOW_HYBRID_MODEL_VERSION]
    assert _unpriced(ledger.db_path) == [] and "unpriced_logged" not in result


def test_a_quote_below_the_minimum_leaves_room_for_an_unpriced_candidate(ledger, monkeypatch):
    monkeypatch.delenv(shadow.SHADOW_HYBRID_FLAG, raising=False)
    monkeypatch.setattr(shadow, "build_fixture_candidates",
                        lambda *args, **kwargs: [_candidate("RESULT_HOME"), _candidate("TOTAL_RANGE_2_3", 0.48)])
    monkeypatch.setattr(shadow, "_model_first_observations", lambda credible, odds_response, now: [
        (credible[0], 1.15, now - timedelta(minutes=1))])
    result = shadow.step_evaluate(ledger.tracker, _Provider(), ledger.now, date.today(), 10)
    assert _rows(ledger.db_path) == []
    assert [row[3:] for row in _unpriced(ledger.db_path)] == [("TOTAL_RANGE_2_3", "no_bet365_market")] * 2
    assert "below_minimum_odds" not in result and result["evaluated"] == 1


class _SettlingProvider:
    def __init__(self, score):
        self.score = score

    def fixtures_by_ids(self, ids):
        return [{"fixture": {"id": fixture_id, "status": {"short": "FT"}},
                 "goals": {"home": self.score[0], "away": self.score[1]}} for fixture_id in ids]


def test_unpriced_tips_settle_from_the_score_and_count_won_lost_only(ledger):
    pick = _candidate("HOME_OVER_1_5", 0.58)
    kickoff = shadow._utc_iso(ledger.now - timedelta(hours=3))
    assert shadow._record_unpriced(91, "Home FC", "Away FC", kickoff, pick, "no_bet365_market",
                                   shadow.SHADOW_MODEL_VERSION, ledger.now) is True
    assert shadow._record_unpriced(91, "Home FC", "Away FC", kickoff, pick, "no_bet365_market",
                                   shadow.SHADOW_MODEL_VERSION, ledger.now) is False
    assert shadow._record_unpriced(92, "C", "D", kickoff, _candidate("RESULT_HOME", 0.60), "no_fresh_bet365_quote",
                                   shadow.SHADOW_MODEL_VERSION, ledger.now) is True
    assert shadow.step_settle_unpriced(_SettlingProvider((2, 0)), ledger.now) == 2
    stats = shadow._unpriced_statistics(shadow.SHADOW_MODEL_VERSION)
    assert stats["tips"] == 2 and stats["settled"] == 2 and stats["won"] == 2 and stats["lost"] == 0
    assert stats["hit_rate"] == 1.0 and stats["expected_hit_rate"] == pytest.approx(0.59)
    assert stats["by_reason"] == {"no_bet365_market": 1, "no_fresh_bet365_quote": 1}
    assert stats["invalid_rows"] == 0 and stats["max_model_probability"] == 0.65
    with shadow._connect() as connection:
        connection.execute("UPDATE shadow_unpriced SET result = 'Lost' WHERE fixture_id = 92")
    assert shadow._unpriced_statistics(shadow.SHADOW_MODEL_VERSION)["invalid_rows"] == 1
    assert shadow._unpriced_statistics(shadow.SHADOW_HYBRID_MODEL_VERSION)["tips"] == 0
    source = Path(shadow.__file__).read_text(encoding="utf-8")
    assert source.count('"unpriced_results": _unpriced_statistics(') == 2
    assert "settled_unpriced = step_settle_unpriced(provider, now)" in source
