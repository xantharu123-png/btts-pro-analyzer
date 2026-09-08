from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
import sys

import pytest

from model_artifacts import put_artifact, publish_slots
from scripts import tennis_daily as daily
from tennis import shadow
from tennis.elo import SurfaceElo
from tennis.model_state import ModelState, load_state, save_state
from tennis.predict import predict_match
from tennis.serve_model import ServeReturnModel
from tennis.state_codec import encode_state
from tennis.tour_state import load_tour_state


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def _state(tour="ATP", *, built_at=None, artifact_hash=None):
    return ModelState(
        SurfaceElo(),
        ServeReturnModel(),
        1.0,
        0.0,
        0,
        (built_at or NOW).timestamp(),
        "2026-09-06",
        0.3 if tour == "ATP" else 0.0,
        tour_scope=tour,
        stats_through_kind=(
            "tournament_start_proxy" if tour == "ATP" else "result_date"
        ),
        artifact_hash=artifact_hash,
        training_cutoff=(NOW - timedelta(days=1)).isoformat(),
    )


def _publish(path, *, tour="ATP", built_at=None, published_at=None):
    state = _state(tour, built_at=built_at)
    payload = {
        "schema": 1,
        "training_cutoff": state.training_cutoff,
        "state": encode_state(state, tour=tour),
    }
    digest = put_artifact(
        path,
        kind="tennis-tour-state",
        payload=payload,
        created_at=built_at or NOW,
    )
    publish_slots(
        path,
        {f"tennis:{tour}": digest},
        expected_manifest=None,
        published_at=published_at or NOW,
    )
    return digest


def test_prediction_rejects_cross_tour_state():
    state = ModelState(
        SurfaceElo(),
        ServeReturnModel(),
        1.0,
        0.0,
        0,
        1.0,
        "1970-01-01",
        0.3,
        tour_scope="ATP",
    )

    with pytest.raises(ValueError, match="tour"):
        predict_match(
            state,
            "a",
            "b",
            "Hard",
            tour="WTA",
            as_of=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )


def test_tour_reader_rejects_manifest_published_after_decision(tmp_path):
    path = tmp_path / "models.db"
    _publish(
        path,
        built_at=NOW - timedelta(hours=2),
        published_at=NOW + timedelta(minutes=1),
    )

    with pytest.raises(ValueError, match="published"):
        load_tour_state("ATP", path=path, decision_cutoff=NOW)


def test_tour_reader_rejects_naive_cutoff_and_accepts_current_manifest(tmp_path):
    path = tmp_path / "models.db"
    digest = _publish(
        path,
        built_at=NOW - timedelta(hours=2),
        published_at=NOW - timedelta(hours=1),
    )

    with pytest.raises(ValueError, match="aware"):
        load_tour_state("ATP", path=path, decision_cutoff=NOW.replace(tzinfo=None))

    loaded = load_tour_state("ATP", path=path, decision_cutoff=NOW)
    assert loaded.artifact_hash == digest
    assert loaded.training_cutoff == (NOW - timedelta(days=1)).isoformat()


def test_tour_reader_rejects_state_built_after_decision(tmp_path):
    path = tmp_path / "models.db"
    _publish(
        path,
        built_at=NOW + timedelta(seconds=1),
        published_at=NOW - timedelta(hours=1),
    )

    with pytest.raises(ValueError, match="built_at"):
        load_tour_state("ATP", path=path, decision_cutoff=NOW)


def test_legacy_loader_hashes_exact_trusted_pickle_bytes(tmp_path):
    path = tmp_path / "legacy.pkl"
    save_state(_state("legacy-combined"), path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()

    loaded = load_state(path)

    assert loaded.tour_scope == "legacy-combined"
    assert loaded.artifact_hash == expected


def test_prediction_exposes_model_identity_without_prices():
    state = _state("ATP", artifact_hash="a" * 64)

    prediction = predict_match(
        state,
        "a",
        "b",
        "Hard",
        tour="ATP",
        as_of=NOW,
    )

    assert prediction.context_evidence["model_inputs"] == {
        "surface": "Hard",
        "indoor": None,
        "surface_in_model": True,
        "serve_in_model": False,
        "model_artifact_hash": "a" * 64,
        "model_built_at": NOW.isoformat(),
        "model_tour_scope": "ATP",
        "stats_through": "2026-09-06",
        "stats_through_kind": "tournament_start_proxy",
        "training_cutoff": (NOW - timedelta(days=1)).isoformat(),
    }


def test_prediction_rejects_explicit_state_with_training_after_build():
    state = _state("ATP", built_at=NOW - timedelta(hours=1))
    state.training_cutoff = NOW.isoformat()

    with pytest.raises(ValueError, match="training cutoff"):
        predict_match(state, "a", "b", "Hard", tour="ATP", as_of=NOW)


def _rated_state(tour, *, winner, artifact_hash, through):
    state = _state(
        tour,
        built_at=NOW - timedelta(hours=1),
        artifact_hash=artifact_hash,
    )
    state.stats_through = through
    for _ in range(25):
        state.elo.update(winner, "same b" if winner == "same a" else "same a", "Hard")
    return state


def _fixture(tour, event_id):
    return {
        "tour": tour,
        "tournament": "Test Open",
        "player_a": "Same A",
        "player_b": "Same B",
        "match_date": "2026-09-08",
        "provider_event_id": event_id,
        "scheduled_start_utc": (NOW + timedelta(hours=4)).isoformat(),
        "fixture_source": "test-provider",
        "surface": "Hard",
        "indoor": False,
    }


def test_initial_scan_selects_independent_tour_states_with_same_player_names(
    tmp_path, monkeypatch
):
    states = {
        "ATP": _rated_state(
            "ATP", winner="same a", artifact_hash="a" * 64,
            through="2026-09-06",
        ),
        "WTA": _rated_state(
            "WTA", winner="same b", artifact_hash="b" * 64,
            through="2026-08-30",
        ),
    }
    loads = []

    def load(tour, **kwargs):
        loads.append((tour, kwargs))
        return states[tour]

    monkeypatch.setattr(daily, "load_tour_state", load)
    db = tmp_path / "scan.db"

    result = daily.scan_fixtures(
        "2026-09-08",
        [_fixture("ATP", "atp-1"), _fixture("WTA", "wta-1")],
        decision_at=NOW,
        db_path=db,
        surfaces={},
        workload_history=[],
        append_observed_at=NOW,
    )

    assert [item[0] for item in loads] == ["ATP", "WTA"]
    assert all(item[1]["decision_cutoff"] == NOW for item in loads)
    assert all(item[1]["allow_legacy"] is False for item in loads)
    assert result["status"] == "complete"
    rows = {row["tour"]: row for row in shadow.latest_predictions(db, as_of=NOW)}
    assert rows["ATP"]["p_cal"] > .5
    assert rows["WTA"]["p_cal"] < .5
    assert rows["ATP"]["context_json"].count("a" * 64) == 1
    assert rows["WTA"]["context_json"].count("b" * 64) == 1
    assert result["models"]["ATP"]["stats_through"] == "2026-09-06"
    assert result["models"]["WTA"]["stats_through"] == "2026-08-30"


def test_initial_scan_keeps_healthy_tour_and_never_builds_missing_state(
    tmp_path, monkeypatch
):
    atp = _rated_state(
        "ATP", winner="same a", artifact_hash="a" * 64,
        through="2026-09-06",
    )

    def load(tour, **kwargs):
        if tour == "WTA":
            raise FileNotFoundError("missing WTA artifact")
        return atp

    monkeypatch.setattr(daily, "load_tour_state", load)
    import tennis.model_state
    monkeypatch.setattr(
        tennis.model_state, "build_state",
        lambda *a, **k: pytest.fail("reader must not build a model"),
    )
    db = tmp_path / "scan.db"

    result = daily.scan_fixtures(
        "2026-09-08",
        [_fixture("ATP", "atp-1"), _fixture("WTA", "wta-1")],
        decision_at=NOW,
        db_path=db,
        surfaces={},
        workload_history=[],
        append_observed_at=NOW,
    )

    assert result["status"] == "partial"
    assert result["stored"] == 1
    assert result["errors"] == [{
        "tour": "WTA", "reason": "cached_tour_state_unavailable",
        "error_type": "FileNotFoundError",
    }]
    assert [row["tour"] for row in shadow.latest_predictions(db, as_of=NOW)] == ["ATP"]


def test_initial_main_rejects_default_append_when_computation_crosses_start(
    tmp_path, monkeypatch,
):
    db = tmp_path / "initial.db"
    clock = [NOW.timestamp()]
    start = NOW + timedelta(seconds=30)
    fixture = _fixture("ATP", "atp-1")
    fixture["match_date"] = start.date().isoformat()
    fixture["scheduled_start_utc"] = start.isoformat()

    def slow_prediction(*args, **kwargs):
        clock[0] = (start + timedelta(seconds=1)).timestamp()
        return predict_match(
            _state("ATP", built_at=NOW - timedelta(hours=1)),
            "Same A", "Same B", "Hard", tour="ATP", as_of=NOW,
        )

    monkeypatch.setattr(shadow, "DB_PATH", db)
    monkeypatch.setattr(daily, "auto_settle_completed", lambda: 0)
    monkeypatch.setattr(daily, "tournament_surface_map", lambda year: {})
    monkeypatch.setattr(daily, "fetch_fixtures", lambda *args, **kwargs: [fixture])
    monkeypatch.setattr(daily, "load_tour_state", lambda *args, **kwargs: _state("ATP"))
    monkeypatch.setattr(daily, "predict_match", slow_prediction)
    monkeypatch.setattr(daily.time, "time", lambda: clock[0])
    monkeypatch.setattr(sys, "argv", ["tennis_daily.py", start.date().isoformat()])

    assert daily.main() == 0
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM prediction_revisions"
        ).fetchone()[0] == 0
