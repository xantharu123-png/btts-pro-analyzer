"""A confirmed final-pair mismatch is unscorable, never a fabricated winner."""
from datetime import timedelta

import pytest

from context_sources import tennis_capture as capture
from context_sources.tennis_outcome_capture import collect_outcomes
from scripts import tennis_daily as daily
from test_context_tennis_outcome_capture import RECEIVED, completed, original_store, outcomes, record
from test_tennis_forecast_retirements import originals
from test_tennis_live_worker import response
from test_tennis_native_outcome_replacement import _final, _scheduled_replacement


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_final_native_participant_change_is_reported_unscorable_without_rewriting(monkeypatch, tmp_path, tour):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour=tour)
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    before_originals, before_predictions = originals(db), predictions.read_bytes()
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour=tour)
    report = observer.report()
    assert report["status"] == "partial"
    assert report["issues"] == ["native-outcome-identity-conflict"]
    assert report["identity_conflict_outcome_events"] == [origin["event"]["event_key"]]
    assert report["unresolved_outcome_events"] == []
    assert report["native_unavailable_outcome_events"] == []
    assert outcomes(db) == ()
    assert originals(db) == before_originals and predictions.read_bytes() == before_predictions


def test_identity_conflict_does_not_require_or_invent_timely_replacement_forecast(monkeypatch, tmp_path):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id, received=RECEIVED - timedelta(hours=1))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA")
    assert observer.report()["identity_conflict_outcome_events"] == [origin["event"]["event_key"]]
    assert outcomes(db) == ()


def test_same_clock_conflicting_native_revisions_are_still_an_error(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    _scheduled_replacement(db, event_id, player="3")
    _scheduled_replacement(db, event_id, player="4")
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA")
    assert observer.report()["identity_conflict_outcome_events"] == []
    assert observer.report()["issues"] == ["native-outcome-unavailable"]
    assert outcomes(db) == ()


@pytest.mark.parametrize("bad", ["missing_flags", "wrong_competition", "invalid_player"])
def test_missing_or_foreign_native_identity_is_not_blessed_as_pair_change(monkeypatch, tmp_path, bad):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    raw = _final(event_id)
    if bad == "missing_flags": raw["competitors"][0].pop("winner")
    elif bad == "invalid_player": raw["competitors"][0]["id"] = "bad"
    payload = response(raw, "WTA")
    if bad == "wrong_competition": payload["events"][0]["id"] = "999-2026"
    with capture.capture_tennis_worker(path=db) as observer:
        observer.record("wta", payload, observed_at=RECEIVED)
    assert observer.report()["identity_conflict_outcome_events"] == []
    assert observer.report()["issues"]
    assert outcomes(db) == ()


def test_direct_collector_still_reports_identity_conflict_without_reporter(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    observer = capture._Capture()
    record(observer, _final(event_id), tour="WTA")
    additions, issues = collect_outcomes(db, observer.pending, observer._outcome_sources)
    assert additions == {} and issues == {"native-outcome-unavailable"}


def test_daily_cli_reports_identity_conflict_as_unscorable_not_failed_scan(monkeypatch, tmp_path, capsys):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    before = predictions.read_bytes()
    monkeypatch.setattr(capture, "_receipt_now", lambda: RECEIVED)
    monkeypatch.setattr(daily, "_run_daily",
        lambda args: capture.observe_espn_response("wta", response(_final(event_id), "WTA")) or 0)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    assert daily.main() == 0
    printed = capsys.readouterr().out
    assert "Kontext-Capture: partial" in printed
    assert '"native-outcome-identity-conflict"' in printed
    assert '"identity_conflict_outcome_events": ["' + origin["event"]["event_key"] + '"]' in printed
    assert outcomes(db) == () and predictions.read_bytes() == before


def test_clean_original_result_still_scores_and_conflict_cannot_replace_it(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path, tour="WTA")
    event_id = origin["event"]["event_key"].rsplit(":", 1)[-1]
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(event_id=event_id), tour="WTA")
    before = outcomes(db)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, _final(event_id), tour="WTA", clock=RECEIVED + timedelta(minutes=1))
    assert observer.report()["identity_conflict_outcome_events"] == [origin["event"]["event_key"]]
    assert outcomes(db) == before
