"""A revised native pair may be unavailable, never another pair's winner."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_observations import append_observation
from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND
from context_sources import tennis_capture as capture
from context_sources.tennis_outcome_capture import collect_outcomes
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import put_artifact
from scripts import tennis_daily as daily
from test_context_tennis_outcome_capture import (
    completed, original_store, outcomes, record,
)
from test_tennis_forecast_retirements import originals
from test_tennis_live_worker import NOW, competition, response


def _scheduled_replacement(db, event_id, *, player="3", received=NOW + timedelta(minutes=45)):
    revised = competition(id=event_id, date="2026-09-09T13:00Z")
    revised["competitors"][0]["id"] = player
    status, = normalize_tennis_status("WTA", "189-2026", revised,
        grouping_slug="womens-singles", observed_at=received)
    return status, append_observation(db, status, observed_at=received)


def _final(event_id, *, player="3"):
    raw = completed(event_id=event_id)
    raw["competitors"][0]["id"] = player
    raw["date"] = "2026-09-09T13:15Z"
    return raw


def test_verified_new_native_pair_is_data_unavailable_without_old_result(monkeypatch, tmp_path):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id)
    before_originals, before_predictions = originals(db), predictions.read_bytes()
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA")
    assert observer.report()["issues"] == []
    assert observer.report()["status"] == "partial"
    assert observer.report()["native_unavailable_outcome_events"] == [origin["event"]["event_key"]]
    assert observer.report()["retired_outcome_events"] == []
    assert outcomes(db) == ()
    assert originals(db) == before_originals and predictions.read_bytes() == before_predictions


@pytest.mark.parametrize("revision", ["missing", "late", "different_pair"])
def test_replacement_without_timely_exact_native_revision_still_fails(
        monkeypatch, tmp_path, revision):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    if revision == "late":
        _scheduled_replacement(db, event_id, received=NOW + timedelta(hours=1, minutes=5))
    elif revision == "different_pair":
        _scheduled_replacement(db, event_id, player="4")
    before_predictions = predictions.read_bytes()
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA")
    assert observer.report()["issues"] == ["native-outcome-unavailable"]
    assert observer.report()["native_unavailable_outcome_events"] == []
    assert outcomes(db) == () and predictions.read_bytes() == before_predictions


def test_old_pair_result_still_binds_after_an_unrelated_revision(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(event_id=event_id), tour="WTA")
    assert observer.report()["native_unavailable_outcome_events"] == []
    assert len(outcomes(db)) == 1
    assert outcomes(db)[0]["payload"]["home_id"] == origin["event"]["home_id"]


def test_new_pair_publication_after_its_start_cannot_claim_final(monkeypatch, tmp_path):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    revision_at = NOW + timedelta(minutes=45)
    status, receipt = _scheduled_replacement(db, event_id, received=revision_at)
    late = deepcopy(origin)
    late.update(cutoff=canonical_timestamp(revision_at + timedelta(seconds=1)),
        native_receipt=receipt, native_observed_at=canonical_timestamp(revision_at),
        competition_revision=status["payload"]["competition_revision"])
    late["event"].update(home_id="espn:tennis:WTA:player:3",
        scheduled_start=status["payload"]["scheduled_start"],
        schedule_revision=status["schedule_revision"])
    put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND, payload={"schema": 1, "origin": late},
        created_at=NOW + timedelta(hours=1, minutes=5))
    before_predictions = predictions.read_bytes()
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA")
    assert observer.report()["issues"] == []
    assert observer.report()["native_unavailable_outcome_events"] == [origin["event"]["event_key"]]
    assert outcomes(db) == () and predictions.read_bytes() == before_predictions


def test_conflicting_same_clock_native_revisions_are_not_suppressed(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id, player="3")
    _scheduled_replacement(db, event_id, player="4")
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA")
    assert observer.report()["issues"] == ["native-outcome-unavailable"]
    assert observer.report()["native_unavailable_outcome_events"] == []
    assert outcomes(db) == ()


def test_missing_winner_flag_is_not_hidden_by_a_valid_replacement(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id)
    raw = _final(event_id)
    raw["competitors"][0].pop("winner")
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw, tour="WTA")
    assert observer.report()["issues"] == ["native-outcome-unavailable"]
    assert observer.report()["native_unavailable_outcome_events"] == []
    assert outcomes(db) == ()


def test_direct_collector_without_reporter_cannot_silently_drop_issue(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id)
    observer = capture._Capture()
    record(observer, _final(event_id), tour="WTA")
    additions, issues = collect_outcomes(db, observer.pending, observer._outcome_sources)
    assert additions == {}
    assert issues == {"native-outcome-unavailable"}


def test_daily_cli_exits_zero_but_reports_partial_native_gap(monkeypatch, tmp_path, capsys):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id)
    from test_context_tennis_outcome_capture import RECEIVED
    monkeypatch.setattr(capture, "_receipt_now", lambda: RECEIVED)
    monkeypatch.setattr(daily, "_run_daily",
        lambda args: capture.observe_espn_response("wta", response(_final(event_id), "WTA")) or 0)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    assert daily.main() == 0
    printed = capsys.readouterr().out
    assert "Kontext-Capture: partial" in printed
    assert '"issues": []' in printed
    assert '"native_unavailable_outcome_events": ["' + origin["event"]["event_key"] + '"]' in printed
    assert outcomes(db) == ()


def test_corrupt_replacement_receipt_is_integrity_error_not_data_gap(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _, ref = _scheduled_replacement(db, event_id)
    with sqlite3.connect(db) as connection:
        digest, = connection.execute(
            "SELECT content_digest FROM context_observations WHERE digest=?", (ref,)).fetchone()
        connection.execute("UPDATE context_contents SET payload=? WHERE content_digest=?", (b"{}", digest))
    with pytest.raises(ContextIntegrityError):
        with capture.capture_tennis_worker(path=db) as observer:
            record(observer, _final(event_id), tour="WTA")
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM context_observations WHERE kind='match_outcome'").fetchone()[0] == 0
