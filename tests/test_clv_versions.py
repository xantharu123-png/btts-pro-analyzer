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
