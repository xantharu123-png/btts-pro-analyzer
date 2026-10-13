"""Real isolated storage mechanics; synthetic cases are not betting evidence."""
from datetime import timedelta
import sqlite3

import pytest

import football_context_decisions as decisions
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader
from context_training_helpers import NOW
from test_football_joint_worker import original_case, isolated, capture_report


def publish(isolated, monkeypatch, *, later=2):
    path, case, _ = isolated
    clock = NOW+timedelta(minutes=later)
    monkeypatch.setattr(decisions, "_now", lambda: clock+timedelta(seconds=1))
    return decisions.publish_capture_decisions(path,
        capture_report([case["case"]["payload"]["replay_ref"]]), decision_at=clock)


def test_no_fit_still_captures_the_actual_later_decision(isolated, monkeypatch):
    report = publish(isolated, monkeypatch)
    assert report["events"][0]["status"] == "captured"
    with _reader(isolated[0]) as connection:
        saved = decisions.resolve_decision(connection, report["events"][0]["decision_ref"],
            latest=canonical_timestamp(NOW+timedelta(minutes=3)))
        assert saved["payload"]["decision_at"] == canonical_timestamp(NOW+timedelta(minutes=2))
        assert saved["payload"]["observation_count"] > 0
        assert len(__import__("model_artifacts").canonical_bytes(saved["payload"])) <= 1024
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-effect-v1'").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM manifests").fetchone() == (0,)


def test_unchanged_sources_reuse_first_real_clock_without_writes(isolated, monkeypatch):
    first = publish(isolated, monkeypatch)
    before = isolated[0].read_bytes()
    second = publish(isolated, monkeypatch, later=12)
    assert second["events"][0] == {**first["events"][0], "status": "reused"}
    assert isolated[0].read_bytes() == before


def test_later_weather_creates_a_real_new_decision_not_a_backdated_source(isolated, monkeypatch):
    from context_observations import append_observation
    from context_sources.openweather import forecast_payload, normalize_forecast
    from datetime import datetime
    first = publish(isolated, monkeypatch)
    event = isolated[1]["case"]["payload"]["event"]
    received = NOW+timedelta(minutes=3)
    point = forecast_payload(event, city="Example", country="GB", latitude=50., longitude=0.,
        point={"dt": datetime.fromisoformat(event["scheduled_start"]).timestamp(),
            "main": {"temp": 18.}, "wind": {"speed": 4.}})
    append_observation(isolated[0], normalize_forecast(point, observed_at=received), observed_at=received)
    second = publish(isolated, monkeypatch, later=4)
    assert second["events"][0]["decision_ref"] != first["events"][0]["decision_ref"]
    with _reader(isolated[0]) as connection:
        saved = decisions.resolve_decision(connection, second["events"][0]["decision_ref"],
            latest=canonical_timestamp(NOW+timedelta(minutes=5)))
    assert saved["payload"]["decision_at"] == canonical_timestamp(NOW+timedelta(minutes=4))


def test_started_event_has_no_new_decision_or_record(isolated, monkeypatch):
    before = isolated[0].read_bytes()
    report = publish(isolated, monkeypatch, later=121)
    assert report["events"][0]["status"] == "unavailable"
    assert report["events"][0]["decision_ref"] is None
    assert isolated[0].read_bytes() == before


def test_zero_byte_admission_creates_no_record_but_can_reuse_existing(isolated, monkeypatch):
    clock = NOW+timedelta(minutes=2)
    monkeypatch.setattr(decisions, "_now", lambda: clock+timedelta(seconds=1))
    before = isolated[0].read_bytes()
    report = decisions.publish_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]), decision_at=clock, max_run_bytes=0)
    assert report["events"][0]["status"] == "budget-exhausted"
    assert report["inserted_payload_bytes"] == 0 and isolated[0].read_bytes() == before
    first = publish(isolated, monkeypatch)
    second = decisions.publish_capture_decisions(isolated[0],
        capture_report([isolated[1]["case"]["payload"]["replay_ref"]]),
        decision_at=clock+timedelta(minutes=1), max_run_bytes=0)
    assert second["events"][0] == {**first["events"][0], "status": "reused"}
    assert second["inserted_payload_bytes"] == 0


@pytest.mark.parametrize("field,value", [("schema", True), ("inserted_payload_bytes", True),
    ("inserted_payload_bytes", 32769), ("unprocessed_events", -1), ("events", [{}])])
def test_admin_report_is_bounded_closed_metadata(field, value):
    report = {"schema": 1, "scope": "football-post-capture-decisions", "events": [],
        "unprocessed_events": 0, "inserted_payload_bytes": 0}
    report[field] = value
    with pytest.raises(ContextContractError):
        decisions.decision_report_fields({"football_context_decisions": report})


def test_corrupt_existing_decision_cannot_be_hidden_as_missing(isolated, monkeypatch):
    report = publish(isolated, monkeypatch)
    with sqlite3.connect(isolated[0]) as connection:
        connection.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b"{}", report["events"][0]["decision_ref"]))
    with pytest.raises(ContextIntegrityError):
        with _reader(isolated[0]) as connection:
            decisions.resolve_decision(connection, report["events"][0]["decision_ref"],
                latest=canonical_timestamp(NOW+timedelta(minutes=4)))


@pytest.mark.parametrize("field,value", [("schema", True), ("observation_count", True),
    ("observation_count", 4097), ("binding_ref", "not-a-hash"), ("event_key", "api-football:football:01")])
def test_closed_decision_contract_rejects_malformed_metadata(field, value):
    payload = {"schema": 1, "binding_ref": "a"*64, "event_key": "api-football:football:1",
        "decision_at": canonical_timestamp(NOW), "observation_refs_hash": "b"*64, "observation_count": 1}
    payload[field] = value
    with pytest.raises(ContextContractError):
        decisions.validate_decision(payload)
