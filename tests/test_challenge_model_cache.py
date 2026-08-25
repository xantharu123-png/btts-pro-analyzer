import json
import sqlite3
from datetime import datetime, timezone

from challenge_engine import MarketCalibration, ValidationMetrics
from challenge_model_cache import load_model_artifact, save_model_artifact


def test_model_artifact_round_trip_and_history_invalidation(tmp_path):
    db_path = tmp_path / "model-cache.db"
    history = [
        {
            "fixture": {
                "id": 1,
                "date": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            },
            "goals": {"home": 2, "away": 1},
        }
    ]
    validation = {
        "BTTS_YES": ValidationMetrics(
            observations=300,
            brier_score=0.15,
            baseline_brier_score=0.20,
            relative_improvement=0.25,
            expected_calibration_error=0.04,
            passed=True,
            calibration_bins=4,
            min_bin_size=30,
            max_calibration_error=0.06,
            max_error_bin_size=30,
            max_error_bin_mean_probability=0.6,
            raw_brier_score=0.16,
        )
    }
    calibration = {
        "BTTS_YES": MarketCalibration(
            points=((0.0, 0.1), (1.0, 0.9)),
            samples=300,
        )
    }

    save_model_artifact(
        "model-v1",
        39,
        2026,
        history,
        validation,
        calibration,
        db_path=db_path,
    )
    loaded = load_model_artifact(
        "model-v1",
        39,
        2026,
        history,
        db_path=db_path,
    )

    assert loaded == (validation, calibration)
    changed_history = [{**history[0], "goals": {"home": 3, "away": 1}}]
    assert (
        load_model_artifact(
            "model-v1",
            39,
            2026,
            changed_history,
            db_path=db_path,
        )
        is None
    )

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    assert (
        load_model_artifact(
            "model-v2",
            39,
            2026,
            history,
            db_path=db_path,
        )
        is None
    )


def test_model_artifact_without_current_schema_is_recomputed(tmp_path):
    db_path = tmp_path / "model-cache.db"
    history = [
        {
            "fixture": {
                "id": 1,
                "date": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            },
            "goals": {"home": 2, "away": 1},
        }
    ]
    validation = {
        "BTTS_YES": ValidationMetrics(
            observations=300,
            brier_score=0.15,
            baseline_brier_score=0.20,
            relative_improvement=0.25,
            expected_calibration_error=0.04,
            passed=True,
        )
    }
    save_model_artifact(
        "model-v1",
        39,
        2026,
        history,
        validation,
        {},
        db_path=db_path,
    )

    with sqlite3.connect(db_path) as connection:
        raw_payload = connection.execute(
            "SELECT payload FROM challenge_model_artifacts"
        ).fetchone()[0]
        payload = json.loads(raw_payload)
        payload.pop("schema_version")
        connection.execute(
            "UPDATE challenge_model_artifacts SET payload = ?",
            (json.dumps(payload),),
        )
        connection.commit()

    assert (
        load_model_artifact(
            "model-v1",
            39,
            2026,
            history,
            db_path=db_path,
        )
        is None
    )
