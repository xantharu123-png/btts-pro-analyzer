"""A changed reported match clock must not erase a genuinely prior forecast."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import canonical_timestamp
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND
from context_observations import append_observation
from context_sources import tennis_capture as capture
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import put_artifact
from test_context_tennis_outcome_capture import (
    NOW, RECEIVED, completed, original_store, outcomes, record, stored,
)
from test_tennis_live_worker import competition


def test_changed_final_clock_preserves_original_and_actual_reported_clock(monkeypatch, tmp_path):
    db, shadow, _, origin = original_store(monkeypatch, tmp_path)
    old_rows = {row["digest"]: row for row in stored(db)}
    shadow_bytes = shadow.read_bytes()
    raw = completed()
    raw["date"] = canonical_timestamp(NOW + timedelta(hours=5, minutes=15))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    result, = outcomes(db)
    assert result["payload"]["schema"] == 2
    assert result["payload"]["scheduled_start"] == origin["event"]["scheduled_start"]
    assert result["payload"]["reported_scheduled_start"] == raw["date"]
    assert result["schedule_revision"] == origin["event"]["schedule_revision"]
    assert result["source_schema"] == "espn-tennis-winner-outcome-v2"
    assert result["observed_at"] == canonical_timestamp(RECEIVED)
    assert result["published_at"] is None
    assert shadow.read_bytes() == shadow_bytes
    after = {row["digest"]: row for row in stored(db)}
    assert all(after[ref] == row for ref, row in old_rows.items())
    assert not observer.report()["issues"]


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_original_must_precede_reported_start_as_well_as_planned_start(monkeypatch, tmp_path, offset):
    db, _, ref, _ = original_store(monkeypatch, tmp_path)
    with sqlite3.connect(db) as connection:
        published = connection.execute("SELECT created_at FROM artifacts WHERE digest=?", (ref,)).fetchone()[0]
    from datetime import datetime
    reported = datetime.fromisoformat(published) + timedelta(seconds=offset)
    raw = completed()
    raw["date"] = canonical_timestamp(reported)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    assert len(outcomes(db)) == (1 if offset > 0 else 0)


def test_distinct_scheduled_revisions_keep_separate_original_bindings(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    revised = competition(date=canonical_timestamp(NOW + timedelta(hours=6)))
    clock = NOW + timedelta(minutes=1)
    status, = normalize_tennis_status("ATP", "189-2026", revised,
        grouping_slug="mens-singles", observed_at=clock)
    receipt = append_observation(db, status, observed_at=clock)
    second = deepcopy(origin)
    second.update(cutoff=canonical_timestamp(clock + timedelta(seconds=1)),
        native_receipt=receipt, native_observed_at=canonical_timestamp(clock),
        competition_revision=status["payload"]["competition_revision"])
    second["event"].update(scheduled_start=status["payload"]["scheduled_start"],
        schedule_revision=status["schedule_revision"])
    put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND, payload={"schema": 1, "origin": second},
        created_at=clock + timedelta(seconds=2))
    raw = completed()
    raw["date"] = canonical_timestamp(NOW + timedelta(hours=6, minutes=15))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    results = outcomes(db)
    assert len(results) == 2
    assert {row["schedule_revision"] for row in results} == {
        origin["event"]["schedule_revision"], second["event"]["schedule_revision"]}
    assert {row["payload"]["scheduled_start"] for row in results} == {
        origin["event"]["scheduled_start"], second["event"]["scheduled_start"]}
    assert {row["payload"]["reported_scheduled_start"] for row in results} == {raw["date"]}
    assert not observer.report()["issues"]


def test_changed_schedule_outcome_passes_transport_without_empirical_approval(monkeypatch, tmp_path):
    from context_runtime import verify_context_database
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    raw = completed()
    raw["date"] = canonical_timestamp(NOW + timedelta(hours=5, minutes=15))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    assert len(outcomes(db)) == 1
    report = verify_context_database(db)
    assert report["empirical_approval_verified"] is False
    assert report["verification_level"] == "transport_only"


@pytest.mark.parametrize("late_publication", [False, True])
def test_revised_outcome_reaches_real_case_builder_with_physical_publication_check(tmp_path, late_publication):
    from context_models.contracts import ContextIntegrityError
    from context_models.tennis_training import build_live_training_case
    from context_sources.outcomes import normalize_tennis_revised_outcome
    from model_artifacts import load_artifact
    from test_tennis_live_training import packet, live_config
    db, originals, _, identity, built = packet(tmp_path)
    origin = load_artifact(db, originals[0])["payload"]["origin"]
    event = origin["event"]
    raw = completed(event_id=event["event_key"].rsplit(":", 1)[-1])
    raw["date"] = canonical_timestamp(NOW + timedelta(hours=4))
    for side, key in enumerate(("home_id", "away_id")):
        raw["competitors"][side]["id"] = event[key].rsplit(":", 1)[-1]
    source = {"source_schema": "espn-scoreboard-v1", "tour": "ATP",
        "tournament_id": "189-2026", "competition": raw}
    result = normalize_tennis_revised_outcome(event, source, observed_at=RECEIVED,
        original_published_at=canonical_timestamp(NOW+timedelta(seconds=1)))
    outcome = append_observation(db, result, observed_at=RECEIVED)
    if late_publication:
        # Still before the original scheduled time, but after the real reported
        # start. A public payload hash must not promote this to prospective data.
        with sqlite3.connect(db) as connection:
            connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
                (canonical_timestamp(NOW+timedelta(hours=4, minutes=1)), originals[0]))
        with pytest.raises(ContextIntegrityError, match="reported native start"):
            build_live_training_case(db, original_ref=originals[0], outcome_ref=outcome,
                identity_ref=identity, config=live_config(), as_of=built)
    else:
        case = build_live_training_case(db, original_ref=originals[0], outcome_ref=outcome,
            identity_ref=identity, config=live_config(), as_of=built)
        assert case["case"]["payload"]["outcome_ref"] == outcome
        assert case["case"]["payload"]["event"] == event


def test_revised_source_correction_cannot_hide_from_legacy_outcome_audit(monkeypatch, tmp_path):
    from context_models.dataset import _reader, outcome_revisions
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
        observer.persist(db)
        frozen, = outcomes(db)
        corrected = completed(winner=1)
        corrected["date"] = canonical_timestamp(NOW + timedelta(hours=5, minutes=15))
        later = RECEIVED + timedelta(minutes=1)
        record(observer, corrected, clock=later)
    frozen.update(evidence_class="prospective", effective_at=frozen["observed_at"], publication_resolution=None)
    with _reader(db) as connection:
        refs, conflicting = outcome_revisions(connection, frozen,
            event=origin["event"], through=canonical_timestamp(later))
    assert len(refs) == 2 and conflicting is True


def test_unbound_legacy_adapter_still_rejects_another_schedule(monkeypatch, tmp_path):
    from context_models.contracts import ContextContractError
    from context_sources.outcomes import normalize_tennis_outcome
    _, _, _, origin = original_store(monkeypatch, tmp_path)
    raw = completed()
    raw["date"] = canonical_timestamp(NOW+timedelta(hours=5, minutes=15))
    with pytest.raises(ContextContractError, match="differs from original"):
        normalize_tennis_outcome(origin["event"], {"source_schema": "espn-scoreboard-v1",
            "tour": "ATP", "tournament_id": "189-2026", "competition": raw}, observed_at=RECEIVED)
