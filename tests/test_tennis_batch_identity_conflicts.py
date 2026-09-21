"""One replaced opponent must not abort unrelated native predictions."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from scripts import tennis_daily as daily
from tennis import shadow
from test_tennis_live_worker import NOW, competition, configure, response, run_batch


def changed_response(monkeypatch, *, clock=NOW+timedelta(seconds=9)):
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
    monkeypatch.setattr(tennis_capture, "_receipt_now", lambda: clock)


def later_clocks(monkeypatch):
    from tennis import live_context
    decision = NOW+timedelta(seconds=10)
    moment = decision+timedelta(seconds=2)
    monkeypatch.setattr(daily, "_refresh_now", lambda: decision)
    monkeypatch.setattr(live_context, "_now", lambda: decision+timedelta(seconds=1))
    monkeypatch.setattr(shadow, "_prediction_append_time", lambda value: (moment.timestamp(), moment.isoformat()))
    return decision, moment


def test_verified_changed_pair_gets_own_lineage_without_mutating_history(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, original = run_batch(db, predictions)
    with sqlite3.connect(predictions) as conn:
        before = conn.execute("SELECT * FROM prediction_revisions WHERE prediction_id=?", (original[0]["id"],)).fetchall()
    changed_response(monkeypatch)
    decision, moment = later_clocks(monkeypatch)

    result, _ = run_batch(db, predictions, decision=decision)
    rows = shadow.latest_predictions(predictions, as_of=moment+timedelta(seconds=1))

    assert result["status"] != "partial"
    assert result["stored"] == 2 and result["skipped"] == 0 and not result["errors"]
    assert {r["provider_event_id"] for r in rows} == {"201", "203"}
    current = next(r for r in rows if r["provider_event_id"] == "201")
    assert current["player_b"] == "Gamma C" and current["id"] != original[0]["id"]
    assert current["odds_a"] is None and current["odds_b"] is None
    assert len(shadow.latest_predictions(predictions, pending_only=False, as_of=moment+timedelta(seconds=1))) == 3
    assert shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))[0]["player_b"] == "Beta B"
    with sqlite3.connect(predictions) as conn:
        assert conn.execute("SELECT * FROM prediction_revisions WHERE prediction_id=?", (original[0]["id"],)).fetchall() == before


def test_daily_main_completes_verified_successor_and_independent_fixture(monkeypatch, tmp_path, capsys):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    changed_response(monkeypatch)
    monkeypatch.setattr(daily, "auto_settle_completed", lambda: 0)
    monkeypatch.setattr(daily, "tournament_surface_map", lambda *a: {})
    monkeypatch.setattr(daily, "fetch_fixtures", daily.fetch_fixtures_espn)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    _, moment = later_clocks(monkeypatch)

    assert daily.main() == 0
    output = capsys.readouterr().out
    import json
    progress = [json.loads(line.split(": ", 1)[1]) for line in output.splitlines()
                if line.startswith("Tennis-Abschluss: ")]
    assert [row["phase"] for row in progress] == [
        "history", "history_ready", "prepare", "prepare_progress", "prepare_progress",
        "prepared", "published", "published", "complete"]
    assert all(row["elapsed_seconds"] >= 0 for row in progress)
    assert [row["processed"] for row in progress if row["phase"] == "prepare_progress"] == [1, 2]
    assert progress[0]["total"] == progress[-1]["total"] == 2
    assert progress[-2]["processed"] == 2
    assert "Nach Datenempfang gespeichert: 2" in output
    assert "fixture_identity_conflict" not in output
    assert len(shadow.latest_predictions(predictions, as_of=moment+timedelta(seconds=1))) == 2


def test_unrelated_store_integrity_failure_is_not_hidden(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    def broken(*args, **kwargs):
        raise ValueError("different integrity failure")
    monkeypatch.setattr(shadow, "store_prediction", broken)
    with pytest.raises(ValueError, match="different integrity failure"):
        run_batch(db, predictions)
