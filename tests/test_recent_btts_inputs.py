"""Old stored results remain auditable but cannot enter current BTTS inputs."""

import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from advanced_analyzer import AdvancedBTTSAnalyzer
from data_engine import DataEngine, recent_match_cutoff


def test_legacy_btts_stats_and_ml_exclude_2022_without_deleting_history(tmp_path):
    db_path = tmp_path / "matches.db"
    engine = DataEngine(api_key="test", db_path=str(db_path))
    today = datetime.now(timezone.utc).date()
    with sqlite3.connect(db_path) as connection:
        rows = [
            (
                1, "PL", 39, today.isoformat(), "Home", "Away",
                1, 2, 1, 1, 1, 2, "now",
            ),
            (
                2, "PL", 39, "2022-09-24", "Home", "Away",
                1, 2, 6, 0, 0, 6, "now",
            ),
        ]
        rows.extend(
            (
                100 + index, "ALT", 39,
                (today - timedelta(days=index + 1)).isoformat(),
                "Other Home", "Other Away",
                1000 + index, 2000 + index, 1, 0, 0, 1, "now",
            )
            for index in range(59)
        )
        connection.executemany(
            """
            INSERT INTO matches (
                id, league_code, league_id, date, home_team, away_team,
                home_team_id, away_team_id, home_goals, away_goals,
                btts, total_goals, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    assert recent_match_cutoff() > "2022-12-31"
    assert engine.get_match_count("PL") == 1
    assert engine.get_team_stats(1, "PL", "home")["avg_scored"] == 1.0
    assert engine.get_recent_form(1, "PL", "home")["avg_scored"] == 1.0
    assert engine.get_league_stats("PL")["avg_total_goals"] == 2.0
    assert engine.calculate_head_to_head(1, 2)["avg_goals"] == 2.0
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 61

    def inspect_training(frame, *, return_dates):
        assert return_dates is True
        assert len(frame) == 60
        assert frame["date"].min() >= recent_match_cutoff()
        return np.zeros((60, 6)), np.zeros(60), np.array([today] * 60)

    with patch(
        "advanced_analyzer.build_prematch_training_rows",
        side_effect=inspect_training,
    ):
        AdvancedBTTSAnalyzer.prepare_training_data(
            SimpleNamespace(db_path=str(db_path)),
        )
