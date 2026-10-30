"""Shadow judged by won/lost at the fetched quote (owner decision 30.10.2026).

Report: docs/audits/2026-10-30-shadow-bewertung-ergebnis.md. A settled tip counts
without a closing quote; the CLV statistics stay a background record.
"""
from pathlib import Path
import sqlite3

import pytest

import shadow_clv_automation as shadow
from clv_tracker import CLVTracker

_COLUMNS = ("fixture_id, home_team, away_team, market_type, prediction, odds, result, profit, "
            "home_score, away_score, created_at, model_version, policy_version")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "shadow.db"
    CLVTracker(db_path=str(path))
    monkeypatch.setattr(shadow, "SHADOW_DB", path)
    shadow._connect().close()  # creates the shadow tables (edge cap)
    return path


def _insert(path, rows, market=None):
    with sqlite3.connect(path) as connection:
        ids = []
        for row in rows:
            cursor = connection.execute(
                f"INSERT INTO predictions ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            ids.append(cursor.lastrowid)
        for index, probability in (market or {}).items():
            connection.execute(
                "INSERT INTO shadow_edge_cap VALUES (?,?,?,?,?,?,?,?)",
                (ids[index], rows[index][11], 0.6, probability, 0.0, 8.0, 1, "2030-01-01T10:00:00+00:00"))
    return ids


def _row(fixture_id, market_type, selection, odds, result, profit, score, created,
         model_version=shadow.SHADOW_MODEL_VERSION, policy_version=shadow.SHADOW_POLICY_VERSION):
    return (fixture_id, "Home FC", "Away FC", market_type, selection, odds, result, profit,
            score[0], score[1], created, model_version, policy_version)


def test_settled_tips_count_without_a_closing_quote(db_path):
    _insert(db_path, [
        _row(1, "RESULT_HOME", "Heimsieg", 2.0, "Won", 1.0, (2, 1), "2030-01-01T10:00:00+00:00"),
        _row(2, "TOTAL_UNDER_3_5", "Unter 3.5", 1.5, "Lost", -1.0, (3, 1), "2030-01-02T10:00:00+00:00"),
        _row(3, "BTTS_YES", "Ja", 1.8, "Won", 0.8, (1, 1), "2030-01-03T10:00:00+00:00"),
        _row(4, "RESULT_HOME", "Heimsieg", 1.9, None, None, (None, None), "2030-01-04T10:00:00+00:00"),
        _row(5, "RESULT_HOME", "Heimsieg", 2.0, "Won", 1.0, (1, 0), "2030-01-05T10:00:00+00:00",
             policy_version="shadow-model-first-v8"),
    ], market={0: 0.5, 1: 0.6})
    results = shadow._result_statistics(shadow.SHADOW_MODEL_VERSION)
    assert (results["settled"], results["won"], results["lost"], results["push"]) == (3, 2, 1, 0)
    assert results["invalid_rows"] == 0 and results["hit_rate"] == pytest.approx(0.6667)
    assert results["avg_odds"] == pytest.approx(1.767) and results["profit_units"] == pytest.approx(0.8)
    assert results["roi"]["n"] == 3 and results["roi"]["mean"] == pytest.approx(26.67)
    assert results["market"] == {"n": 2, "hit_rate": 0.5, "market_hit_rate": 0.55}
    assert results["minimum_settled"] == shadow.SHADOW_REVIEW_MIN_SETTLED == 1000
    assert shadow._result_statistics(shadow.SHADOW_HYBRID_MODEL_VERSION)["settled"] == 0


def test_a_row_that_contradicts_its_score_blocks_the_verdict(db_path):
    _insert(db_path, [
        _row(1, "RESULT_HOME", "Heimsieg", 2.0, "Won", 1.0, (0, 1), "2030-01-01T10:00:00+00:00"),
        _row(2, "RESULT_HOME", "Heimsieg", 2.0, "Won", 0.5, (2, 0), "2030-01-02T10:00:00+00:00"),
    ])
    results = shadow._result_statistics(shadow.SHADOW_MODEL_VERSION)
    assert results["settled"] == 0 and results["invalid_rows"] == 2
    assert shadow._result_verdict(results).startswith("Shadow-Evidenz gesperrt: 2 ")


def test_verdict_needs_1000_settled_tips_and_names_the_lower_bound():
    building = shadow._result_verdict({"settled": 999, "invalid_rows": 0})
    assert building.startswith("Shadow-Evidenzaufbau: 999/1000 abgerechnete Tipps")
    reached = shadow._result_verdict(
        {"settled": 1000, "invalid_rows": 0, "roi": {"mean": 1.2, "lower_bound": -0.8}})
    assert reached.startswith("Shadow-Prüfstufe erreicht: 1000/1000")
    assert "+1.20 % je Tipp, untere Grenze -0.80 %" in reached and "Erst eine untere Grenze über 0" in reached


def test_paired_results_compare_the_two_cohorts_on_the_same_fixture(db_path):
    _insert(db_path, [
        _row(1, "RESULT_HOME", "Heimsieg", 2.0, "Won", 1.0, (2, 1), "2030-01-01T10:00:00+00:00"),
        _row(1, "BTTS_YES", "Ja", 1.8, "Lost", -1.0, (2, 0), "2030-01-01T10:00:00+00:00",
             model_version=shadow.SHADOW_HYBRID_MODEL_VERSION),
        _row(2, "RESULT_HOME", "Heimsieg", 2.0, "Won", 1.0, (1, 0), "2030-01-02T10:00:00+00:00"),
    ])
    paired = shadow._paired_result_statistics()
    assert paired["pairs"] == 1 and paired["minimum_pairs"] == 1000
    assert paired["difference"]["n"] == 1 and paired["difference"]["mean"] == pytest.approx(-200.0)


def test_run_artifact_is_judged_by_results_and_keeps_clv_in_the_background():
    source = Path(shadow.__file__).read_text(encoding="utf-8")
    assert '"evaluation": "won_lost_at_opening_quote"' in source
    assert '"verdict": _result_verdict(results)' in source and '"clv_verdict": _verdict(stats_all)' in source
    assert '"results": _result_statistics(SHADOW_HYBRID_MODEL_VERSION)' in source
    assert '"paired_results": _paired_result_statistics()' in source


def test_results_are_split_by_the_age_of_the_opening_stamp(db_path):
    # Policy v10 (30.10.2026) admits stamps up to 24 hours old; the split shows whether older ones do worse.
    ids = _insert(db_path, [
        _row(1, "RESULT_HOME", "Heimsieg", 2.0, "Won", 1.0, (2, 1), "2030-01-01T10:00:00+00:00"),
        _row(2, "RESULT_HOME", "Heimsieg", 1.5, "Lost", -1.0, (0, 0), "2030-01-02T10:00:00+00:00"),
        _row(3, "BTTS_YES", "Ja", 1.8, "Won", 0.8, (1, 1), "2030-01-03T10:00:00+00:00"),
    ])
    with sqlite3.connect(db_path) as connection:
        connection.executemany("UPDATE predictions SET opening_quote_age_seconds = ? WHERE id = ?",
                               [(12 * 3600, ids[0]), (18 * 3600, ids[1])])
    split = shadow._result_statistics(shadow.SHADOW_MODEL_VERSION)["by_opening_age"]
    assert split["up_to_12h"] == {"settled": 1, "hit_rate": 1.0, "roi_mean": 100.0}
    assert split["over_12h"] == {"settled": 1, "hit_rate": 0.0, "roi_mean": -100.0}
    assert split["unknown"] == {"settled": 1, "hit_rate": 1.0, "roi_mean": 80.0}
