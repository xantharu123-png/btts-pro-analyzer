"""Optional bounded POINT reads must not abort an otherwise valid daily batch."""
from datetime import timedelta
import json
import sqlite3

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError
from context_models import tennis_point_original as point
from context_sources.tennis_capture import _Capture, capture_tennis_worker
from model_artifacts import put_artifact
from tennis import shadow
from tennis.live_context import LiveWorker, live_worker
from test_context_tennis_outcome_capture import completed
from test_tennis_live_worker import NOW, competition, configure, daily, response
from test_tennis_point_original import originals, setup_point
from test_tennis_live_worker import run_batch


DECLINE = {"reason": "event_scope_limit_exceeded", "event_count": 501, "limit": 500}


def capture_events(count):
    capture = _Capture()
    raw = response()
    raw["events"][0]["groupings"][0]["competitions"] = [
        competition(id=str(n)) for n in range(1, count+1)]
    capture.record("atp", raw, observed_at=NOW-timedelta(seconds=10))
    assert len(capture.pending) == count
    return capture


@pytest.mark.parametrize("count", [500, 501])
def test_real_finish_keeps_optional_event_limit_nonfatal_without_a_database(monkeypatch, tmp_path, count):
    progress = []
    path = tmp_path / "absent.db"
    batch = LiveWorker(path, progress=progress.append)
    batch.attach_capture(capture_events(count))
    actual = point.point_scores_as_of
    calls = []
    def collect(*args, **kwargs):
        calls.append(kwargs["event_keys"])
        return actual(*args, **kwargs)
    monkeypatch.setattr(point, "point_scores_as_of", collect)
    monkeypatch.setattr(point, "_reader", lambda *a, **kw: pytest.fail("optional read opened a database"))
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("finish fetched"))

    batch.finish()

    assert batch.finished is True
    assert batch.point_outcomes == ()
    assert progress[-1]["phase"] == "complete"
    assert progress[-1]["total"] == 0
    assert not path.exists()
    if count == 501:
        assert calls == []  # No truncation, batching or optional helper call.
        assert batch.point_scores_decline == DECLINE
        declines = [item for item in progress if item["phase"] == "point_scores_declined"]
        assert len(declines) == 1
        assert {key: declines[0][key] for key in DECLINE} == DECLINE
        assert not any(item["phase"] == "point_scores" for item in progress)
    else:
        assert len(calls) == 1 and len(calls[0]) == 500
        assert batch.point_scores_decline is None
        assert not any(item["phase"] == "point_scores_declined" for item in progress)
    with pytest.raises(ContextContractError, match="twice"):
        batch.finish()


def test_direct_helper_still_rejects_501_valid_native_keys(tmp_path):
    keys = {f"espn:tennis:ATP:match:{n}" for n in range(1, 502)}
    with pytest.raises(ContextContractError, match="native event scopes"):
        point.point_scores_as_of(tmp_path / "absent.db", as_of=NOW, event_keys=keys)


def forecast_batch(monkeypatch, directory, *, native, backlog):
    directory.mkdir()
    db, predictions, _, _ = configure(monkeypatch, directory)
    progress = []
    with live_worker(path=db, progress=progress.append) as batch:
        with capture_tennis_worker(path=db) as capture:
            batch.attach_capture(capture)
            fixtures = daily.fetch_fixtures_espn("2026-09-09")
            if not native:
                batch.bindings.clear()  # Valid ordinary, unlinked forecast owner.
            result = daily.scan_fixtures("2026-09-09", fixtures, decision_at=NOW,
                db_path=predictions, surfaces={}, workload_history=(),
                append_observed_at=NOW+timedelta(seconds=2))
            assert result["prepared"] == 1 and result["stored"] == 0
            assert len(batch.pending) == 1
            assert (batch.pending[0]["binding"] is not None) is native
            for index in range(backlog):
                raw = completed(event_id=str(1000+index))
                raw["date"] = "2026-09-08T17:00Z"
                for side, player in enumerate(raw["competitors"]):
                    player["id"] = str(10000+2*index+side)
                capture.record("atp", response(raw), observed_at=NOW-timedelta(seconds=10))
        assert len(capture.pending) == backlog+1
        # Real capture persistence is complete before the optional finish read.
        with sqlite3.connect(db) as connection:
            assert connection.execute("SELECT count(DISTINCT event_key) FROM context_observations").fetchone()[0] == backlog+1
        actual = point.point_scores_as_of
        calls = []
        def collect(*args, **kwargs):
            calls.append(kwargs["event_keys"])
            return actual(*args, **kwargs)
        with monkeypatch.context() as finishing:
            finishing.setattr(point, "point_scores_as_of", collect)
            finishing.setattr("requests.get", lambda *a, **kw: pytest.fail("finish fetched"))
            batch.finish()
        assert batch.finished is True and batch.point_outcomes == ()
        assert progress[-1]["phase"] == "complete" and progress[-1]["total"] == 1
        assert result["stored"] == 1 and result["errors"] == []
        if backlog:
            assert calls == []
            assert batch.point_scores_decline == DECLINE
            declines = [item for item in progress if item["phase"] == "point_scores_declined"]
            assert len(declines) == 1
            assert {key: declines[0][key] for key in DECLINE} == DECLINE
        rows = shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))
        assert len(rows) == 1
        context = json.loads(rows[0]["context_json"])
        assert ("context_model" in context) is native
        assert "point_scores_decline" not in context
        assert "event_scope_limit_exceeded" not in rows[0]["context_json"]
        return rows[0]


@pytest.mark.parametrize("native", [False, True], ids=["legacy", "linked-public"])
def test_oversized_captured_backlog_finishes_queued_forecast_exactly(monkeypatch, tmp_path, native):
    baseline = forecast_batch(monkeypatch, tmp_path / "baseline", native=native, backlog=0)
    oversized = forecast_batch(monkeypatch, tmp_path / "oversized", native=native, backlog=500)
    # All customer-visible values/market/gate bytes stay exact; only the linked
    # internal context reference may depend on the complete receipt inventory.
    public = ("created_utc", "match_date", "provider_event_id", "scheduled_start_utc",
        "fixture_source", "tour", "tournament", "surface", "best_of", "player_a",
        "player_b", "p_raw", "p_cal", "markets_json", "gates_json", "verdict",
        "recommended_side", "recommended_edge", "model_version", "policy_version")
    assert {key: oversized[key] for key in public} == {key: baseline[key] for key in public}
    baseline_context = json.loads(baseline["context_json"])
    oversized_context = json.loads(oversized["context_json"])
    baseline_context.pop("context_model", None)
    oversized_context.pop("context_model", None)
    assert oversized_context == baseline_context


def test_in_range_finish_propagates_real_corrupt_point_admission(monkeypatch, tmp_path):
    db = tmp_path / "corrupt.db"
    ref = put_artifact(db, kind=point.POINT_ORIGINAL_KIND,
        payload={"event_key": "espn:tennis:ATP:match:1"}, created_at=NOW)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE artifacts SET payload=? WHERE digest=?",
            (b" "*(point.MAX_PUBLICATION_BYTES+1), ref))
    before = db.read_bytes()
    progress = []
    batch = LiveWorker(db, progress=progress.append)
    batch.attach_capture(capture_events(1))
    monkeypatch.setattr(point, "_native_score", lambda *a, **kw: pytest.fail("corrupt body decoded"))
    with pytest.raises(ContextIntegrityError, match="admission header"):
        batch.finish()
    assert batch.finished is False and batch.point_outcomes == ()
    assert not any(item["phase"] == "complete" for item in progress)
    assert db.read_bytes() == before


def test_in_range_finish_does_not_swallow_unexpected_helper_errors(monkeypatch, tmp_path):
    batch = LiveWorker(tmp_path / "absent.db")
    batch.attach_capture(capture_events(1))
    def broken(*args, **kwargs):
        raise RuntimeError("unexpected POINT read failure")
    monkeypatch.setattr(point, "point_scores_as_of", broken)
    with pytest.raises(RuntimeError, match="unexpected POINT read failure"):
        batch.finish()
    assert batch.finished is False


@pytest.mark.parametrize("budget", ["count", "bytes"])
def test_optional_finish_declines_only_explicit_finite_admission_exhaustion(monkeypatch, tmp_path, budget):
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref, _ = originals(db)[0]
    # This is an actual valid immutable POINT original, not a fake error stub.
    assert point.read_point_score(db, ref, as_of=NOW+timedelta(seconds=3)) is None
    with sqlite3.connect(db) as connection:
        size = connection.execute("SELECT length(payload) FROM artifacts WHERE digest=?", (ref,)).fetchone()[0]
    capture = _Capture()
    capture.record("atp", response(), observed_at=NOW-timedelta(seconds=10))
    progress = []
    batch = LiveWorker(db, progress=progress.append)
    batch.attach_capture(capture)
    if budget == "count":
        monkeypatch.setattr(point, "MAX_ADMITTED_ORIGINALS", 0)
        wanted = {"reason": "original_count_limit_exceeded", "original_count_at_least": 1, "limit": 0}
    else:
        monkeypatch.setattr(point, "MAX_ADMITTED_BYTES", 1)
        wanted = {"reason": "original_bytes_limit_exceeded", "original_bytes": size, "limit": 1}
    monkeypatch.setattr(point, "_native_score", lambda *a, **kw: pytest.fail("unadmitted original expanded"))
    before = db.read_bytes()
    batch.finish()
    assert batch.finished is True and batch.point_outcomes == ()
    assert batch.point_scores_decline == wanted
    assert progress[-1]["phase"] == "complete"
    declines = [item for item in progress if item["phase"] == "point_scores_declined"]
    assert len(declines) == 1
    assert {key: declines[0][key] for key in wanted} == wanted
    # Only the optional owner declines. Direct helper callers retain rejection.
    with pytest.raises(ContextContractError, match="admission"):
        point.point_scores_as_of(db, as_of=NOW+timedelta(seconds=3), event_keys={"espn:tennis:ATP:match:201"})
    assert db.read_bytes() == before
