"""One replaced opponent must not abort unrelated native predictions."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from scripts import tennis_daily as daily
from tennis import shadow
from test_tennis_live_worker import NOW, competition, configure, response, run_batch


def changed_response(monkeypatch):
    replaced = competition()
    replaced["competitors"][1] = {"id": "3", "athlete": {"displayName": "Gamma C"}}
    independent = competition(id="203")
    independent["competitors"] = [
        {"id": "4", "athlete": {"displayName": "Delta D"}},
        {"id": "5", "athlete": {"displayName": "Epsilon E"}},
    ]
    document = response(replaced)
    document["events"][0]["groupings"][0]["competitions"].append(independent)

    class Reply:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return deepcopy(self.payload)

    monkeypatch.setattr(daily.requests, "get", lambda url, **kwargs:
        Reply(document if "/atp/" in url else {"events": []}))
    from context_sources import tennis_capture
    monkeypatch.setattr(tennis_capture, "_receipt_now", lambda: NOW-timedelta(seconds=5))


def test_changed_pair_is_reported_without_mutating_history_or_aborting_next_fixture(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, original = run_batch(db, predictions)
    with sqlite3.connect(predictions) as conn:
        before = conn.execute("SELECT * FROM prediction_revisions WHERE prediction_id=?", (original[0]["id"],)).fetchall()
    changed_response(monkeypatch)

    result, rows = run_batch(db, predictions)

    assert result["status"] == "partial"
    assert result["stored"] == 1 and result["skipped"] == 1
    assert result["errors"] == [{"tour": "ATP", "provider_event_id": "201",
        "reason": "fixture_identity_conflict", "error_type": "FixtureIdentityConflict"}]
    assert {r["provider_event_id"] for r in rows} == {"201", "203"}
    assert next(r for r in rows if r["provider_event_id"] == "201")["player_b"] == "Beta B"
    with sqlite3.connect(predictions) as conn:
        assert conn.execute("SELECT * FROM prediction_revisions WHERE prediction_id=?", (original[0]["id"],)).fetchall() == before


def test_daily_main_keeps_nonzero_partial_result_after_finishing_other_predictions(monkeypatch, tmp_path, capsys):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    changed_response(monkeypatch)
    monkeypatch.setattr(daily, "auto_settle_completed", lambda: 0)
    monkeypatch.setattr(daily, "tournament_surface_map", lambda *a: {})
    monkeypatch.setattr(daily, "fetch_fixtures", daily.fetch_fixtures_espn)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    moment = NOW+timedelta(seconds=2)
    monkeypatch.setattr(shadow, "_prediction_append_time", lambda value: (moment.timestamp(), moment.isoformat()))

    assert daily.main() == 1
    output = capsys.readouterr().out
    assert "Nach Datenempfang gespeichert: 1" in output
    assert "fixture_identity_conflict" in output
    assert len(shadow.latest_predictions(predictions, as_of=moment+timedelta(seconds=1))) == 2


def test_unrelated_store_integrity_failure_is_not_hidden(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    def broken(*args, **kwargs):
        raise ValueError("different integrity failure")
    monkeypatch.setattr(shadow, "store_prediction", broken)
    with pytest.raises(ValueError, match="different integrity failure"):
        run_batch(db, predictions)
