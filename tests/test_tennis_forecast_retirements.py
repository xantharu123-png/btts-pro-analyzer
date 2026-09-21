"""Exact logical removals: no broad event ban, history rewrite or fake result."""
from copy import deepcopy
from datetime import timedelta
import re
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND
from context_observations import append_observation
from context_sources import tennis_capture as capture
from context_sources.tennis_outcome_capture import collect_outcomes
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import put_artifact
from scripts import tennis_daily as daily
from tennis import forecast_retirements as retirements, shadow
from test_context_tennis_outcome_capture import (
    RECEIVED, completed, original_store, outcomes, record,
)
from test_tennis_live_worker import NOW, competition


def retire(monkeypatch, predictions, ref, origin):
    row, = shadow.latest_predictions(predictions, pending_only=False, as_of=RECEIVED)
    marker = retirements.ForecastRetirement(origin["event"]["event_key"], row["id"],
        row["initial_created_utc"], frozenset({ref}))
    monkeypatch.setattr(retirements, "RETIREMENTS", (marker,))
    monkeypatch.setattr(retirements, "APPROVED_AT", (NOW+timedelta(minutes=2)).timestamp())
    return row, marker


def originals(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT digest,kind,payload,created_at FROM artifacts WHERE kind=? ORDER BY digest",
            (ORIGINAL_ARTIFACT_KIND,)).fetchall()


def test_approved_catalog_contains_only_the_four_reviewed_lineages():
    assert {item.event_key for item in retirements.RETIREMENTS} == {
        "espn:tennis:WTA:match:"+value for value in ("183710", "183831", "183844", "183854")}
    refs = [ref for item in retirements.RETIREMENTS for ref in item.original_hashes]
    assert len(refs) == len(set(refs)) == 30
    assert all(re.fullmatch(r"[a-f0-9]{64}", ref) for ref in refs)
    assert {item.prediction_id for item in retirements.RETIREMENTS} == {1441, 1419, 1414, 1409}


@pytest.mark.parametrize("changed", ["id", "created_utc", "fixture_source", "tour", "provider_event_id"])
def test_prediction_identity_must_match_in_full(changed):
    item = retirements.RETIREMENTS[0]
    row = {"id": item.prediction_id, "created_utc": item.initial_created_utc,
        "fixture_source": "ESPN", "tour": "WTA", "provider_event_id": "183710"}
    assert retirements.prediction_is_retired(row)
    assert not retirements.prediction_is_retired(row, as_of=retirements.APPROVED_AT-1)
    assert retirements.prediction_is_retired(row, as_of=retirements.APPROVED_AT)
    revision = {**row, "created_utc": item.initial_created_utc+100,
        "initial_created_utc": item.initial_created_utc}
    assert retirements.prediction_is_retired(revision)
    row[changed] = {"id": item.prediction_id+1, "created_utc": item.initial_created_utc+1,
        "fixture_source": "SofaScore", "tour": "ATP", "provider_event_id": "183711"}[changed]
    assert not retirements.prediction_is_retired(row)


def test_original_removal_is_hash_and_event_scoped():
    item = retirements.RETIREMENTS[0]
    ref = next(iter(item.original_hashes))
    assert retirements.original_is_retired(ref, item.event_key)
    assert not retirements.original_is_retired("0"*64, item.event_key)
    assert not retirements.original_is_retired(ref, item.event_key.replace("WTA", "ATP"))


def test_unrelated_forecast_remains_in_both_active_queues(monkeypatch, tmp_path):
    from test_tennis_pending_refresh import prediction
    db, predictions, ref, origin = original_store(monkeypatch, tmp_path)
    retire(monkeypatch, predictions, ref, origin)
    other_id = shadow.store_prediction("2026-09-09", "ATP", "Other Open", prediction(),
        provider_event_id="999", fixture_source="ESPN", scheduled_start_utc="2026-09-09T22:00:00Z",
        modeled_at=NOW+timedelta(seconds=5), append_observed_at=NOW+timedelta(seconds=6), db_path=predictions)
    before = predictions.read_bytes()
    assert [row["id"] for row in shadow.latest_predictions(predictions, as_of=RECEIVED)] == [other_id]
    assert [row["id"] for row in shadow.pending_predictions()] == [other_id]
    assert len(shadow.latest_predictions(predictions, pending_only=False, as_of=RECEIVED)) == 2
    assert predictions.read_bytes() == before


def test_active_reads_and_auto_settlement_omit_only_retired_rows_without_writes(monkeypatch, tmp_path):
    db, predictions, ref, origin = original_store(monkeypatch, tmp_path)
    row, _ = retire(monkeypatch, predictions, ref, origin)
    context_before, shadow_before = db.read_bytes(), predictions.read_bytes()
    assert shadow.latest_predictions(predictions, as_of=RECEIVED) == []
    assert shadow.pending_predictions() == []
    assert shadow.latest_predictions(predictions, pending_only=False, as_of=RECEIVED) == [row]
    assert shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3)) == [row]
    monkeypatch.setattr(daily, "fetch_results_espn", lambda *a, **kw: pytest.fail("retired forecast was polled"))
    monkeypatch.setattr(shadow, "settle", lambda *a, **kw: pytest.fail("retired forecast was settled"))
    assert daily.auto_settle_completed(today="2026-09-11") == 0
    assert db.read_bytes() == context_before and predictions.read_bytes() == shadow_before
    monkeypatch.setattr(retirements, "RETIREMENTS", ())
    assert shadow.latest_predictions(predictions, as_of=RECEIVED) == [row]
    assert len(shadow.pending_predictions()) == 1


def test_removed_participant_change_no_longer_errors_but_preserves_originals(monkeypatch, tmp_path):
    db, predictions, ref, origin = original_store(monkeypatch, tmp_path)
    before = originals(db)
    shadow_before = predictions.read_bytes()
    raw = completed()
    raw["competitors"][1]["id"] = "3"
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    assert observer.report()["issues"] == ["native-outcome-unavailable"]
    retire(monkeypatch, predictions, ref, origin)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw, clock=RECEIVED+timedelta(minutes=1))
    report = observer.report()
    assert report["status"] == "captured" and report["issues"] == []
    assert report["retired_outcome_events"] == [origin["event"]["event_key"]]
    assert outcomes(db) == ()  # Removal is neither a winner nor a void result.
    assert originals(db) == before and predictions.read_bytes() == shadow_before


@pytest.mark.parametrize("corruption", ["payload", "clock", "native_receipt", "state"])
def test_logical_removal_never_hides_damaged_evidence(monkeypatch, tmp_path, corruption):
    db, predictions, ref, origin = original_store(monkeypatch, tmp_path)
    retire(monkeypatch, predictions, ref, origin)
    with sqlite3.connect(db) as connection:
        if corruption == "payload":
            connection.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b"{}", ref))
        elif corruption == "clock":
            connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
                (canonical_timestamp(NOW-timedelta(minutes=1)), ref))
        elif corruption == "native_receipt":
            connection.execute("DELETE FROM context_observations WHERE digest=?", (origin["native_receipt"],))
        else:
            connection.execute("DELETE FROM artifacts WHERE digest=?", (origin["state_hash"],))
    with pytest.raises(ContextIntegrityError):
        with capture.capture_tennis_worker(path=db) as observer:
            record(observer)


def test_retired_prediction_does_not_hide_a_corrupt_revision(monkeypatch, tmp_path):
    _, predictions, ref, origin = original_store(monkeypatch, tmp_path)
    retire(monkeypatch, predictions, ref, origin)
    with sqlite3.connect(predictions) as connection:
        connection.execute("DROP TRIGGER tennis_model_revision_no_update")
        connection.execute("UPDATE prediction_revisions SET payload_json='{}'")
    with pytest.raises(ValueError, match="revision"):
        shadow.latest_predictions(predictions, as_of=RECEIVED)


def test_unlisted_new_original_of_same_event_is_not_suppressed(monkeypatch, tmp_path):
    db, predictions, ref, origin = original_store(monkeypatch, tmp_path)
    retire(monkeypatch, predictions, ref, origin)
    revised = competition()
    revised["competitors"][1]["id"] = "3"
    clock = NOW+timedelta(minutes=1)
    status, = normalize_tennis_status("ATP", "189-2026", revised,
        grouping_slug="mens-singles", observed_at=clock)
    receipt = append_observation(db, status, observed_at=clock)
    new_origin = deepcopy(origin)
    new_origin.update(cutoff=canonical_timestamp(clock+timedelta(seconds=1)),
        native_receipt=receipt, native_observed_at=canonical_timestamp(clock),
        competition_revision=status["payload"]["competition_revision"])
    new_origin["event"]["away_id"] = "espn:tennis:ATP:player:3"
    new_ref = put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND,
        payload={"schema": 1, "origin": new_origin}, created_at=clock+timedelta(seconds=2))
    assert not retirements.original_is_retired(new_ref, origin["event"]["event_key"])
    raw = completed()
    raw["competitors"][1]["id"] = "3"
    observer = capture._Capture()
    record(observer, raw)
    retired = set()
    additions, issues = collect_outcomes(db, observer.pending, observer._outcome_sources, retired_events=retired)
    assert not issues and len(additions[0]) == 1
    assert additions[0][0]["payload"]["away_id"] == "espn:tennis:ATP:player:3"
    assert retired == {origin["event"]["event_key"]}
    monkeypatch.setattr(retirements, "RETIREMENTS", ())
    additions, issues = collect_outcomes(db, observer.pending, observer._outcome_sources)
    assert additions == {} and issues == {"native-outcome-conflicting"}
