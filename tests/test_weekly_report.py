from __future__ import annotations

import sqlite3
from datetime import date

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
