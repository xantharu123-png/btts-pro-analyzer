from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from clv_tracker import (
    CLVEvidenceIntegrityError,
    CLVTracker,
    DuplicatePredictionError,
    SettlementConflictError,
)


def _make_recorded_fixture_settleable(db: Path, prediction_id: int) -> None:
    """Move a fully captured unit-test fixture onto a causal past timeline."""

    now = datetime.now(timezone.utc)
    with closing(sqlite3.connect(db)) as connection:
        connection.execute(
            '''
            UPDATE predictions
            SET quoted_at = ?, created_at = ?, closing_quoted_at = ?,
                fixture_kickoff = ?
            WHERE id = ?
            ''',
            (
                (now - timedelta(minutes=30)).isoformat(),
                (now - timedelta(minutes=29)).isoformat(),
                (now - timedelta(minutes=11)).isoformat(),
                (now - timedelta(minutes=10)).isoformat(),
                prediction_id,
            ),
        )
        connection.commit()


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
            prediction="Ja",
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
                prediction="Ja",
                odds=2.0,
                model_probability=55.0,
                bookmaker="Book",
                quote_source="API",
                fixture_kickoff=now + timedelta(minutes=10),
                quoted_at=now,
                model_version=model_version,
                policy_version=policy_version,
            )
            tracker.update_closing_odds(
                prediction_id,
                1.9,
                bookmaker="Book",
                quote_source="API",
                quoted_at=now,
            )
            _make_recorded_fixture_settleable(db, prediction_id)
            scores = (1, 1) if result == "Won" else (1, 0)
            tracker.settle_prediction(prediction_id, result, *scores)

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


def test_versioned_prediction_is_unique_per_fixture_and_generation() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)

        def record(model: str, policy: str) -> int:
            return tracker.record_prediction(
                fixture_id=42,
                home_team="Home",
                away_team="Away",
                market_type="BTTS_YES",
                prediction="Ja",
                odds=2.0,
                model_probability=55.0,
                bookmaker="Book",
                quote_source="API",
                fixture_kickoff=now + timedelta(hours=1),
                quoted_at=now,
                model_version=model,
                policy_version=policy,
            )

        record("model-v1", "policy-v1")
        with pytest.raises(DuplicatePredictionError):
            record("model-v1", "policy-v1")

        record("model-v2", "policy-v1")
        record("model-v1", "policy-v2")
        with closing(sqlite3.connect(db)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        assert count == 3


def test_new_predictions_require_both_non_empty_versions() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        common = dict(
            fixture_id=42,
            home_team="Home",
            away_team="Away",
            market_type="BTTS_YES",
            prediction="Ja",
            odds=2.0,
            model_probability=55.0,
            bookmaker="Book",
            quote_source="API",
            fixture_kickoff=now + timedelta(hours=1),
            quoted_at=now,
        )

        for versions in (
            {},
            {"model_version": "model-v1", "policy_version": ""},
            {"model_version": " ", "policy_version": "policy-v1"},
        ):
            with pytest.raises(ValueError, match="required"):
                tracker.record_prediction(**common, **versions)

        with closing(sqlite3.connect(db)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        assert count == 0


def test_statistics_fail_closed_if_duplicate_fixture_rows_bypass_the_index() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        prediction_id = tracker.record_prediction(
            fixture_id=42,
            home_team="Home",
            away_team="Away",
            market_type="BTTS_YES",
            prediction="Ja",
            odds=2.0,
            model_probability=55.0,
            bookmaker="Book",
            quote_source="API",
            fixture_kickoff=now + timedelta(minutes=10),
            quoted_at=now,
            model_version="model-v1",
            policy_version="policy-v1",
        )
        tracker.update_closing_odds(
            prediction_id,
            1.9,
            bookmaker="Book",
            quote_source="API",
            quoted_at=now + timedelta(seconds=1),
        )
        _make_recorded_fixture_settleable(db, prediction_id)
        tracker.settle_prediction(prediction_id, "Won", 2, 1)

        with closing(sqlite3.connect(db)) as connection:
            connection.execute("DROP INDEX uq_prediction_fixture_model_policy")
            columns = [
                row[1]
                for row in connection.execute("PRAGMA table_info(predictions)")
                if row[1] != "id"
            ]
            column_sql = ", ".join(columns)
            duplicate_cursor = connection.execute(
                f"INSERT INTO predictions ({column_sql}) "
                f"SELECT {column_sql} FROM predictions WHERE id = ?",
                (prediction_id,),
            )
            connection.execute(
                "UPDATE predictions SET result = NULL, profit = NULL, settled_at = NULL "
                "WHERE id = ?",
                (duplicate_cursor.lastrowid,),
            )
            connection.commit()

        stats = tracker.get_clv_statistics(
            days=30,
            model_version="model-v1",
            policy_version="policy-v1",
        )

        assert stats["evidence_valid"] is False
        assert stats["duplicate_fixture_groups"] == 1
        assert stats["independent_clv_fixtures"] == 0
        assert stats["clv_bets"] == 0
        assert stats["avg_clv"] is None


def test_existing_versioned_duplicates_lock_initialization_without_deleting_rows() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("DROP INDEX uq_prediction_fixture_model_policy")
            columns = [
                row[1]
                for row in connection.execute("PRAGMA table_info(predictions)")
                if row[1] != "id"
            ]
            values = {column: None for column in columns}
            values.update({
                "fixture_id": 42,
                "home_team": "Home",
                "away_team": "Away",
                "market_type": "BTTS_YES",
                "prediction": "Yes",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "model-v1",
                "policy_version": "policy-v1",
            })
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(columns)
            row_values = [values[column] for column in columns]
            connection.execute(
                f"INSERT INTO predictions ({column_sql}) VALUES ({placeholders})",
                row_values,
            )
            connection.execute(
                f"INSERT INTO predictions ({column_sql}) VALUES ({placeholders})",
                row_values,
            )
            connection.commit()

        with pytest.raises(CLVEvidenceIntegrityError):
            CLVTracker(str(db))

        with closing(sqlite3.connect(db)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        assert count == 2


def test_legacy_null_versions_survive_migration_but_new_rows_are_versioned() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("DROP INDEX uq_prediction_fixture_model_policy")
            for _ in range(2):
                connection.execute('''
                    INSERT INTO predictions (
                        fixture_id, home_team, away_team, market_type,
                        prediction, created_at, model_version, policy_version
                    ) VALUES (42, 'Home', 'Away', 'BTTS_YES', 'Yes', ?, NULL, NULL)
                ''', (datetime.now(timezone.utc).isoformat(),))
            connection.commit()

        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        tracker.record_prediction(
            fixture_id=42,
            home_team="Home",
            away_team="Away",
            market_type="BTTS_YES",
            prediction="Ja",
            odds=2.0,
            model_probability=55.0,
            bookmaker="Book",
            quote_source="API",
            fixture_kickoff=now + timedelta(hours=1),
            quoted_at=now,
            model_version="model-v1",
            policy_version="policy-v1",
        )

        with closing(sqlite3.connect(db)) as connection:
            rows = connection.execute('''
                SELECT model_version, policy_version
                FROM predictions ORDER BY id
            ''').fetchall()
        assert rows == [(None, None), (None, None), ("model-v1", "policy-v1")]


def test_concurrent_versioned_inserts_allow_exactly_one_prediction() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        barrier = threading.Barrier(2)

        def insert_once() -> str:
            barrier.wait(timeout=5)
            try:
                tracker.record_prediction(
                    fixture_id=42,
                    home_team="Home",
                    away_team="Away",
                    market_type="BTTS_YES",
                    prediction="Ja",
                    odds=2.0,
                    model_probability=55.0,
                    bookmaker="Book",
                    quote_source="API",
                    fixture_kickoff=now + timedelta(hours=1),
                    quoted_at=now,
                    model_version="model-v1",
                    policy_version="policy-v1",
                )
            except DuplicatePredictionError:
                return "duplicate"
            return "inserted"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(lambda _index: insert_once(), range(2)))

        assert outcomes == ["duplicate", "inserted"]
        with closing(sqlite3.connect(db)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        assert count == 1


def _record_complete_evidence(
    tracker: CLVTracker,
    *,
    fixture_id: int,
    result: str = "Won",
) -> int:
    now = datetime.now(timezone.utc)
    prediction_id = tracker.record_prediction(
        fixture_id=fixture_id,
        home_team=f"Home {fixture_id}",
        away_team=f"Away {fixture_id}",
        market_type="BTTS_YES",
        prediction="Ja",
        odds=2.0,
        model_probability=55.0,
        bookmaker="Book",
        quote_source="API",
        fixture_kickoff=now + timedelta(minutes=10),
        quoted_at=now - timedelta(minutes=1),
        model_version="model-v1",
        policy_version="policy-v1",
    )
    tracker.update_closing_odds(
        prediction_id,
        1.9,
        bookmaker="Book",
        quote_source="API",
        quoted_at=now,
    )
    _make_recorded_fixture_settleable(Path(tracker.db_path), prediction_id)
    scores = (2, 1) if result == "Won" else (2, 0)
    tracker.settle_prediction(prediction_id, result, *scores)
    return prediction_id


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    (
        ("profit = NULL", "malformed_settlement"),
        ("result = NULL", "malformed_settlement"),
        ("prediction = 'Nein'", "malformed_settlement"),
        (
            "market_type = 'HOME_OVER_0_5', prediction = 'Über 0.5'",
            "malformed_settlement",
        ),
        ("closing_source = 'OTHER'", "invalid_quote_provenance"),
        (
            "closing_odds = NULL, closing_bookmaker = NULL, "
            "closing_source = NULL, closing_quoted_at = NULL",
            "malformed_settlement",
        ),
    ),
)
def test_statistics_fail_closed_for_any_malformed_or_unproven_settled_row(
    mutation: str,
    expected_issue: str,
) -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        _record_complete_evidence(tracker, fixture_id=41)
        damaged_id = _record_complete_evidence(
            tracker,
            fixture_id=42,
            result="Lost",
        )
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                f"UPDATE predictions SET {mutation} WHERE id = ?",
                (damaged_id,),
            )
            connection.commit()

        stats = tracker.get_clv_statistics(
            days=30,
            model_version="model-v1",
            policy_version="policy-v1",
        )

        assert stats["evidence_valid"] is False
        assert stats["invalid_evidence_rows"] == 1
        assert expected_issue in stats["integrity_issues"]
        assert stats["total_bets"] == 0
        assert stats["independent_clv_fixtures"] == 0
        assert stats["win_rate"] is None
        assert stats["roi"] is None


def test_malformed_settled_row_outside_metric_window_still_locks_version() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        damaged_id = _record_complete_evidence(tracker, fixture_id=42)
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                "UPDATE predictions SET created_at = ?, profit = NULL WHERE id = ?",
                (
                    (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
                    damaged_id,
                ),
            )
            connection.commit()

        stats = tracker.get_clv_statistics(
            days=30,
            model_version="model-v1",
            policy_version="policy-v1",
        )

        assert stats["evidence_valid"] is False
        assert stats["invalid_evidence_rows"] == 1


def test_statistics_reject_result_that_does_not_match_market_and_score() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        prediction_id = _record_complete_evidence(tracker, fixture_id=42)
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                "UPDATE predictions SET home_score = 2, away_score = 0 "
                "WHERE id = ?",
                (prediction_id,),
            )
            connection.commit()

        stats = tracker.get_clv_statistics(
            days=30,
            model_version="model-v1",
            policy_version="policy-v1",
        )

        assert stats["evidence_valid"] is False
        assert stats["invalid_evidence_rows"] == 1
        assert "malformed_settlement" in stats["integrity_issues"]


def test_settlement_rejects_pre_kickoff_and_score_mismatch() -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CLVTracker(str(db))
        now = datetime.now(timezone.utc)
        prediction_id = tracker.record_prediction(
            fixture_id=42,
            home_team="Home",
            away_team="Away",
            market_type="BTTS_YES",
            prediction="Ja",
            odds=2.0,
            model_probability=55.0,
            bookmaker="Book",
            quote_source="API",
            fixture_kickoff=now + timedelta(minutes=10),
            quoted_at=now,
            model_version="model-v1",
            policy_version="policy-v1",
        )

        with pytest.raises(ValueError, match="before fixture kickoff"):
            tracker.settle_prediction(prediction_id, "Won", 2, 1)

        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                "UPDATE predictions SET fixture_kickoff = ? WHERE id = ?",
                (
                    (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                    prediction_id,
                ),
            )
            connection.commit()

        with pytest.raises(ValueError, match="does not match"):
            tracker.settle_prediction(prediction_id, "Won", 2, 0)

        with closing(sqlite3.connect(db)) as connection:
            assert connection.execute(
                "SELECT result, profit, settled_at FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone() == (None, None, None)


def test_concurrent_settlement_is_atomic_and_exactly_one_writer_wins() -> None:
    barrier = threading.Barrier(2)

    class CursorProxy:
        def __init__(self, cursor):
            self._cursor = cursor

        def fetchone(self):
            row = self._cursor.fetchone()
            barrier.wait(timeout=5)
            return row

    class ConnectionProxy:
        def __init__(self, connection):
            self._connection = connection

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("UPDATE predictions") and params[0] == "Won":
                time.sleep(0.1)
            cursor = self._connection.execute(sql, params)
            if normalized.startswith("SELECT odds, result FROM predictions"):
                return CursorProxy(cursor)
            return cursor

    class CoordinatedTracker(CLVTracker):
        @contextmanager
        def _connect(self):
            connection = sqlite3.connect(self.db_path, timeout=5)
            try:
                yield ConnectionProxy(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    with tempfile.TemporaryDirectory(dir=".") as tmp:
        db = Path(tmp) / "clv.db"
        tracker = CoordinatedTracker(str(db))
        now = datetime.now(timezone.utc)
        prediction_id = tracker.record_prediction(
            fixture_id=42,
            home_team="Home",
            away_team="Away",
            market_type="BTTS_YES",
            prediction="Ja",
            odds=2.0,
            model_probability=55.0,
            bookmaker="Book",
            quote_source="API",
            fixture_kickoff=now + timedelta(hours=1),
            quoted_at=now,
            model_version="model-v1",
            policy_version="policy-v1",
        )
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                "UPDATE predictions SET fixture_kickoff = ? WHERE id = ?",
                (
                    (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                    prediction_id,
                ),
            )
            connection.commit()

        def settle_once(result: str) -> str:
            try:
                scores = (2, 1) if result == "Won" else (2, 0)
                tracker.settle_prediction(prediction_id, result, *scores)
            except SettlementConflictError:
                return "conflict"
            return "settled"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(settle_once, ("Won", "Lost")))

        assert outcomes == ["conflict", "settled"]
        with closing(sqlite3.connect(db)) as connection:
            stored = connection.execute(
                "SELECT result, profit FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()
        assert stored == ("Lost", -1.0)
