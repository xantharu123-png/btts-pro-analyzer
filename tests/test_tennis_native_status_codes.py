"""Cancellation is an actual native status code, not a note-text keyword."""
import pytest
from copy import deepcopy
from datetime import timedelta

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from test_context_tennis_capture import NOW, competition, records


@pytest.mark.parametrize("note", ["not canceled", "not cancelled"])
def test_incidental_note_cannot_override_native_final_status(note):
    answer = records(competition(notes=[{"text": note}]))
    assert answer[0]["payload"]["native_status"]["name"] == "STATUS_FINAL"
    assert answer[0]["payload"]["native_status"]["cancelled"] is False
    assert answer[0]["payload"]["status"] == "completed"
    assert len(answer) == 3


@pytest.mark.parametrize("name", ["STATUS_CANCELED", "STATUS_CANCELLED"])
def test_actual_native_cancellation_is_retained(name):
    answer = records(competition(status={"type": {"state": "pre", "name": name, "completed": False}}))
    assert answer[0]["payload"]["native_status"]["cancelled"] is True
    assert answer[0]["payload"]["status"] == "cancelled"
    assert len(answer) == 1


def test_rehashed_cancellation_flag_still_needs_its_actual_native_code():
    from context_sources.tennis_status import validate_tennis_status_record
    row = deepcopy(records()[0])
    payload = row["payload"]
    payload["native_status"]["cancelled"] = True
    payload.update(status="cancelled", workload_receipts=[])
    clock = canonical_timestamp(NOW-timedelta(hours=1))
    payload["competition_revision"] = digest({"version": "espn-tennis-competition-reception-v1",
        "event_key": row["event_key"], "observed_at": clock,
        "projection": {key: value for key, value in payload.items() if key != "competition_revision"}})
    row.update(source_revision=digest(payload), observed_at=clock)
    with pytest.raises(ContextContractError):
        validate_tennis_status_record(row)
