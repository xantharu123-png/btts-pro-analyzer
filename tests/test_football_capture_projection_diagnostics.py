"""Bounded internal failure breadcrumbs preserve the existing strict capture."""
from copy import deepcopy
import hashlib
import json
import logging

import pytest

from context_sources import football_capture as capture
from test_context_football_capture import detail


def broken_capture(monkeypatch, count=12, *, failure=ValueError("contract detail")):
    owner = capture._Capture()
    rows = []
    for index in range(count):
        row = detail()
        row["fixture"]["id"] = 100 + index
        rows.append(row)
        owner.wanted.add(100 + index)
    owner.receipts.append({"endpoint": "fixtures", "rows": rows,
                           "observed_at": "2030-01-01T00:00:00Z",
                           "watched_results_only": False})
    def reject(*args, **kwargs):
        raise failure
    monkeypatch.setattr(capture, "normalize_football_context", reject)
    monkeypatch.setattr(capture, "append_observation_batch",
                        lambda *args, **kwargs: pytest.fail("Rejected fixture persisted"))
    return owner, rows


def test_projection_diagnostics_are_bounded_and_do_not_expose_source_text(monkeypatch, tmp_path, caplog):
    secret = "private API credential and provider detail NEVER PRINT"
    owner, rows = broken_capture(monkeypatch, failure=ValueError(secret))
    before = deepcopy(rows)
    with caplog.at_level(logging.WARNING, logger=capture.__name__):
        owner.persist(tmp_path / "not-created.db")
        owner.persist(tmp_path / "not-created.db")
    records = [record for record in caplog.records if record.name == capture.__name__]
    assert len(records) == 5
    for index, record in enumerate(records):
        message = record.getMessage()
        assert secret not in message
        payload = json.loads(message.split(": ", 1)[1])
        assert payload == {"endpoint": "fixtures", "fixture_id": 100 + index,
                           "exception_type": "ValueError",
                           "reason_sha256": hashlib.sha256(secret.encode()).hexdigest()}
    assert owner.report() == {"schema": 1, "scope": "existing-football-context-requests",
                              "status": "partial", "receipt_refs": [],
                              "issues": ["Kontext-Capture: native-projection-unavailable"]}
    assert rows == before and not (tmp_path / "not-created.db").exists()


@pytest.mark.parametrize("bad_id", [True, "100", 100.0, None, -1])
def test_invalid_native_ids_never_enter_structured_logs(monkeypatch, tmp_path, caplog, bad_id):
    owner, rows = broken_capture(monkeypatch, count=1)
    rows[0]["fixture"]["id"] = bad_id
    owner.wanted = {bad_id}
    with caplog.at_level(logging.WARNING, logger=capture.__name__):
        owner.persist(tmp_path / "not-created.db")
    assert caplog.records == []
    assert owner.report()["issues"] == ["Kontext-Capture: native-projection-unavailable"]


def test_contract_rejection_type_keeps_strictness(monkeypatch, tmp_path, caplog):
    from context_models.contracts import ContextContractError
    owner, _ = broken_capture(monkeypatch, count=1,
                              failure=ContextContractError("appearance and lineup disagree on actual start"))
    with caplog.at_level(logging.WARNING, logger=capture.__name__):
        owner.persist(tmp_path / "not-created.db")
    assert json.loads(caplog.records[0].getMessage().split(": ", 1)[1])["exception_type"] == "ContextContractError"
    assert owner.report()["status"] == "partial"


def test_unrelated_runtime_failures_still_escape(monkeypatch, tmp_path, caplog):
    owner, _ = broken_capture(monkeypatch, count=1, failure=RuntimeError("unexpected runtime failure"))
    with pytest.raises(RuntimeError):
        owner.persist(tmp_path / "not-created.db")
    assert caplog.records == []
