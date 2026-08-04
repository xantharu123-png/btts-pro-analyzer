from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from clv_tracker import CLVTracker


def test_clv_prediction_records_model_and_policy_versions() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        tracker.record_prediction(
            fixture_id=42,
            home_team="Home",
            away_team="Away",
            market_type="BTTS_YES",
            prediction="Yes",
            odds=2.0,
            model_probability=55.0,
            bookmaker="Book",
            quote_source="API",
            fixture_kickoff=now + timedelta(hours=1),
            quoted_at=now,
            model_version="model-v1",
            policy_version="policy-v2",
        )
        with closing(sqlite3.connect(db)) as connection:
            row = connection.execute(
                "SELECT model_version, policy_version FROM predictions"
            ).fetchone()
        assert row == ("model-v1", "policy-v2")


def test_clv_statistics_and_recent_rows_can_be_isolated_by_policy_version() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        for fixture_id, model_version, policy_version, result in (
            (41, "model-v1", "policy-v1", "Won"),
            (42, "model-v2", "policy-v2", "Lost"),
        ):
            prediction_id = tracker.record_prediction(
                fixture_id=fixture_id,
                home_team=f"Home {fixture_id}",
                away_team=f"Away {fixture_id}",
                market_type="BTTS_YES",
                prediction="Yes",
                odds=2.0,
                model_probability=55.0,
                bookmaker="Book",
                quote_source="API",
                fixture_kickoff=now + timedelta(hours=1),
                quoted_at=now,
                model_version=model_version,
                policy_version=policy_version,
            )
            tracker.settle_prediction(prediction_id, result, 1, 1)

        current = tracker.get_clv_statistics(
            days=30,
            model_version="model-v2",
            policy_version="policy-v2",
        )
        recent = tracker.get_recent_predictions(
            10,
            model_version="model-v2",
            policy_version="policy-v2",
        )

        assert current["total_bets"] == 1
        assert current["profit"] == -1.0
        assert [row["fixture_id"] for row in recent] == [42]
