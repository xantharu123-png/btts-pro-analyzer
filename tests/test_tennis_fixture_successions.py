"""Native replacements keep prices/results and as-of forecast history apart."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError
from scripts import tennis_daily as daily
from tennis import live_context, shadow
from test_tennis_live_worker import NOW, competition, configure, response, run_batch


def next_pair(monkeypatch, db, predictions, *, seconds=10, player_id="3", name="Gamma C", tour="ATP"):
    from context_sources import tennis_capture
    decision = NOW+timedelta(seconds=seconds)
    raw = competition()
    raw["competitors"][1] = {"id": player_id, "athlete": {"displayName": name}}
    class Reply:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return deepcopy(self.body)
    monkeypatch.setattr(daily.requests, "get", lambda url, **kw:
        Reply(response(raw, tour) if f"/{tour.lower()}/" in url else {"events": []}))
    monkeypatch.setattr(tennis_capture, "_receipt_now", lambda: decision-timedelta(seconds=1))
    monkeypatch.setattr(live_context, "_now", lambda: decision+timedelta(seconds=1))
    appended = decision+timedelta(seconds=2)
    monkeypatch.setattr(shadow, "_prediction_append_time", lambda value: (appended.timestamp(), appended.isoformat()))
    result, _ = run_batch(db, predictions, decision=decision)
    return result, shadow.latest_predictions(predictions, as_of=appended+timedelta(seconds=1))


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_successor_has_no_inherited_price_and_does_not_resurrect_after_settlement(monkeypatch, tmp_path, tour):
    db, predictions, _, _ = configure(monkeypatch, tmp_path, tours=(tour,), same_id=True)
    _, rows = run_batch(db, predictions)
    original_id = rows[0]["id"]
    with sqlite3.connect(predictions) as conn:
        conn.execute("UPDATE predictions SET odds_a=1.91,odds_b=2.07 WHERE id=?", (original_id,))
        old = conn.execute("SELECT * FROM predictions WHERE id=?", (original_id,)).fetchone()
    _, current = next_pair(monkeypatch, db, predictions, tour=tour)
    assert len(current) == 1 and current[0]["id"] != original_id
    assert current[0]["odds_a"] is None and current[0]["odds_b"] is None
    assert [r["id"] for r in shadow.pending_predictions()] == [current[0]["id"]]
    with sqlite3.connect(predictions) as conn:
        assert conn.execute("SELECT * FROM predictions WHERE id=?", (original_id,)).fetchone() == old
        conn.execute("UPDATE predictions SET settled=1 WHERE id=?", (current[0]["id"],))
    assert shadow.latest_predictions(predictions, as_of=NOW+timedelta(minutes=1)) == []
    assert shadow.pending_predictions() == []
    assert len(shadow.latest_predictions(predictions, pending_only=False, as_of=NOW+timedelta(minutes=1))) == 2


def test_a_b_a_and_later_refresh_never_reactivate_original_a(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, original = run_batch(db, predictions)
    _, second = next_pair(monkeypatch, db, predictions)
    _, third = next_pair(monkeypatch, db, predictions, seconds=20, player_id="2", name="Beta B")
    assert original[0]["id"] < second[0]["id"] < third[0]["id"]
    assert len(third) == 1 and third[0]["player_b"] == "Beta B"
    result, refreshed = next_pair(monkeypatch, db, predictions, seconds=30, player_id="2", name="Beta B")
    assert result["stored"] == 0 and refreshed[0]["id"] == third[0]["id"]
    assert len(shadow.latest_predictions(predictions, pending_only=False, as_of=NOW+timedelta(minutes=1))) == 3
    assert shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))[0]["id"] == original[0]["id"]
    assert shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=13))[0]["id"] == second[0]["id"]
    # The new model cannot suppress or expose another pair before its receipt.
    before_append = shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=21))
    assert [r["id"] for r in before_append] == [second[0]["id"]]


def test_display_name_change_without_native_player_change_does_not_authorize_successor(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    result, current = next_pair(monkeypatch, db, predictions, player_id="2")
    assert result["errors"][0]["reason"] == "fixture_identity_conflict"
    assert len(current) == 1 and current[0]["player_b"] == "Beta B"


def test_new_native_ids_with_unchanged_display_name_still_require_new_parent(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, original = run_batch(db, predictions)
    result, current = next_pair(monkeypatch, db, predictions, name="Beta B")
    assert not result["errors"] and current[0]["id"] != original[0]["id"]


def test_stale_decision_cannot_replace_a_later_published_parent(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    with pytest.raises(ContextIntegrityError, match="later observed opponent"):
        next_pair(monkeypatch, db, predictions, seconds=2)
    assert len(shadow.latest_predictions(predictions, pending_only=False, as_of=NOW+timedelta(minutes=1))) == 1


def test_settled_original_cannot_be_silently_superseded(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    with sqlite3.connect(predictions) as conn:
        conn.execute("UPDATE predictions SET settled=1")
    with pytest.raises(ContextIntegrityError, match="settled native prediction"):
        next_pair(monkeypatch, db, predictions)


def test_corrupt_first_revision_cannot_hide_the_original(monkeypatch, tmp_path):
    import json
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    _, current = next_pair(monkeypatch, db, predictions)
    with sqlite3.connect(predictions) as conn:
        conn.execute("DROP TRIGGER tennis_model_revision_no_update")
        ref, serialized = conn.execute("SELECT revision_id,payload_json FROM prediction_revisions WHERE prediction_id=?",
            (current[0]["id"],)).fetchone()
        payload = json.loads(serialized)
        payload["fixture_successor"]["prediction_id"] = 99999
        conn.execute("UPDATE prediction_revisions SET payload_json=? WHERE revision_id=?",
            (json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")), ref))
    with pytest.raises(ContextIntegrityError, match="integrity mismatch"):
        shadow.latest_predictions(predictions, as_of=NOW+timedelta(minutes=1))


def test_legacy_tennis_view_excludes_superseded_pair_but_preserves_audit(monkeypatch, tmp_path):
    import tennis_tab
    from datetime import datetime
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (NOW+timedelta(minutes=1)).astimezone(tz)
    monkeypatch.setattr(tennis_tab, "datetime", Clock)
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    monkeypatch.setattr(tennis_tab, "DB_PATH", predictions)
    run_batch(db, predictions)
    _, current = next_pair(monkeypatch, db, predictions)
    assert [row["id"] for row in tennis_tab._load_predictions(unsettled_only=True, native_current_only=True)] == [current[0]["id"]]
    assert len(tennis_tab._load_predictions(current_only=False)) == 2
