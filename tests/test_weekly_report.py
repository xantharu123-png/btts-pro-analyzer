from __future__ import annotations

import sqlite3
from datetime import date
from html import unescape

import pytest

from scripts import weekly_report
from tennis.predict import SIDE_MARKET_PROBABILITY_HAIRCUT
from tennis.shadow import TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION


def test_minimum_odds_uses_haircut_and_risk_adjusted_roi() -> None:
    probability = 0.70
    # (1 + 3% target ROI) / (70% - 10pp haircut), rounded up to cents.
    assert weekly_report._minimum_odds(probability) == pytest.approx(1.72)


def test_minimum_odds_requires_probability_above_haircut() -> None:
    assert weekly_report._minimum_odds(SIDE_MARKET_PROBABILITY_HAIRCUT) is None
    assert weekly_report._minimum_odds(None) is None


def test_weekly_report_reads_only_current_model_and_policy(tmp_path, monkeypatch):
    db = tmp_path / "tennis.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY,
                match_date TEXT,
                tournament TEXT,
                player_a TEXT,
                model_version TEXT,
                policy_version TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?)",
            (
                (1, "2030-01-01", "Current", "A", TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION),
                (2, "2030-01-01", "Old model", "B", "legacy", TENNIS_POLICY_VERSION),
                (3, "2030-01-01", "Old policy", "C", TENNIS_MODEL_VERSION, "legacy"),
            ),
        )
    monkeypatch.setattr(weekly_report, "DB", db)

    cards = weekly_report.load_cards(date(2030, 1, 1), 1)

    assert [card["id"] for card in cards] == [1]


@pytest.mark.parametrize("status", ["unavailable", "insufficient", "unknown"])
def test_unmeasured_watch_status_never_claims_detected_drift(status):
    # Mutation caught: mapping every non-ok state to a measured drift alarm.
    result = {"status": status, "run_date": "2030-01-01", "n_scored": 0,
              "markets": {}, "limits": {"rms": .07, "mid_bias": .05}}
    html = unescape(weekly_report.render([], [], result, "", date(2030, 1, 1), 1))
    assert "WÄCHTER-ALARM" not in html
    assert "Satz-Märkte driften" not in html
    assert "Modell stabil" not in html
    assert "<div class='box warn'><b>Kalibrierungs-Wächter" in html


def test_unavailable_watch_explains_missing_data_or_contract_not_model_drift():
    result = {"status": "unavailable", "run_date": "2030-01-01",
              "n_scored": 0, "markets": {},
              "unavailable_reason": "actual_joint_original_unavailable"}
    html = unescape(weekly_report.render([], [], result, "", date(2030, 1, 1), 1))
    assert "Daten- oder Vertragsgrundlage fehlt" in html
    assert "Drift nicht gemessen" in html


def test_measured_drift_still_renders_the_drift_alarm():
    result = {"status": "drift", "run_date": "2030-01-01", "n_scored": 1000,
              "markets": {"over_2_5_sets": {
                  "n": 1000, "rms": .12, "max_mid_bias": .12, "drift": True}}}
    html = unescape(weekly_report.render([], [], result, "", date(2030, 1, 1), 1))
    assert "WÄCHTER-ALARM: Satz-Märkte driften" in html
    assert "<div class='box drift'><b>Kalibrierungs-Wächter" in html
    assert "<span class='drift'>DRIFT</span>" in html


@pytest.mark.parametrize("certified", [False, True])
def test_ok_legacy_diagnostic_never_certifies_the_production_model(certified):
    result = {"status": "ok", "run_date": "2030-01-01", "n_scored": 1000,
              "markets": {}, "model_version": "hold-proxy-v1",
              "production_model_certified": certified}
    html = unescape(weekly_report.render([], [], result, "", date(2030, 1, 1), 1))
    assert "Modell stabil" not in html
    assert "Legacy-Diagnose" in html
    assert "hold-proxy-v1" in html
    assert "kein Produktionsnachweis" in html


def test_ok_without_production_contract_does_not_claim_production_stability():
    result = {"status": "ok", "run_date": "2030-01-01", "n_scored": 1000, "markets": {}}
    html = unescape(weekly_report.render([], [], result, "", date(2030, 1, 1), 1))
    assert "Modell stabil" not in html
    assert "kein Produktionsnachweis" in html


def test_only_explicitly_certified_ok_watch_can_report_production_stability():
    result = {"status": "ok", "run_date": "2030-01-01", "n_scored": 1000,
              "markets": {}, "model_version": "serve-points-joint-v2",
              "production_model_certified": True}
    html = unescape(weekly_report.render([], [], result, "", date(2030, 1, 1), 1))
    assert "Modell stabil" in html
    assert "<div class='box ok'><b>Kalibrierungs-Wächter" in html
