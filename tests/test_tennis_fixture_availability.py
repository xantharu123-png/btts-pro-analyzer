"""Already received participant/status corrections invalidate active cards only."""
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError
from context_observations import append_observation
from context_sources.tennis_status import normalize_tennis_status
from tennis.fixture_availability import current_native_forecasts
from tennis import shadow
from test_tennis_live_worker import NOW, competition, configure, run_batch


def correction(db, kind, *, clock):
    raw = competition()
    if kind == "missing_player": raw["competitors"][0]["id"] = None
    elif kind == "replacement": raw["competitors"][0]["id"] = "7"
    elif kind == "started": raw["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
    elif kind == "cancelled": raw["status"]["type"].update(state="post", name="STATUS_CANCELED", completed=True)
    elif kind == "schedule": raw["date"] = "2026-09-09T18:00Z"
    for observation in normalize_tennis_status("ATP", "189-2026", raw,
            grouping_slug="mens-singles", observed_at=clock):
        append_observation(db, observation, observed_at=clock)


@pytest.mark.parametrize("kind", ["missing_player", "replacement", "started", "cancelled", "schedule"])
def test_known_native_change_removes_current_card_not_history(monkeypatch, tmp_path, kind):
    import ev_signal_sources as normal
    import riskobet_candidates as risk
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    before_clock = NOW+timedelta(seconds=3)
    assert current_native_forecasts(rows, as_of=before_clock, path=db) == rows
    assert normal._latest_tennis_rows(predictions, "2026-09-09", before_clock)
    assert risk.adapt_tennis_shadow(predictions, as_of=before_clock)
    frozen = predictions.read_bytes()
    clock = NOW+timedelta(seconds=10)
    correction(db, kind, clock=clock)
    context_bytes = db.read_bytes()
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("reader fetched"))
    assert current_native_forecasts(rows, as_of=clock, path=db) == []
    assert normal._latest_tennis_rows(predictions, "2026-09-09", clock) == []
    assert risk.adapt_tennis_shadow(predictions, as_of=clock) == ()
    assert current_native_forecasts(rows, as_of=before_clock, path=db) == rows
    assert len(shadow.latest_predictions(predictions, pending_only=False, as_of=clock)) == 1
    assert predictions.read_bytes() == frozen and db.read_bytes() == context_bytes


def test_legacy_rows_do_not_acquire_a_fictitious_native_source_requirement(tmp_path):
    rows = [{"id": 1, "context_json": None}, {"id": 2, "context_json": "{}"}]
    assert current_native_forecasts(rows, as_of=NOW, path=tmp_path/"absent.db") == rows
    assert not (tmp_path/"absent.db").exists()


def test_simultaneous_known_sources_are_not_resolved_by_choosing_one(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    clock = NOW+timedelta(seconds=10)
    correction(db, "unchanged", clock=clock)
    correction(db, "replacement", clock=clock)
    assert current_native_forecasts(rows, as_of=clock, path=db) == []


def test_source_corruption_is_not_turned_into_an_ordinary_absence(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE context_observations SET subject_id='corrupt'")
    with pytest.raises(ContextIntegrityError):
        current_native_forecasts(rows, as_of=NOW+timedelta(seconds=3), path=db)


def test_active_view_filters_started_match_without_hiding_pending_settlement(monkeypatch, tmp_path):
    import tennis_tab
    from datetime import datetime
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (NOW+timedelta(seconds=11)).astimezone(tz)
    monkeypatch.setattr(tennis_tab, "datetime", Clock)
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    monkeypatch.setattr(tennis_tab, "DB_PATH", predictions)
    run_batch(db, predictions)
    correction(db, "started", clock=NOW+timedelta(seconds=10))
    assert tennis_tab._load_predictions(unsettled_only=True, native_current_only=True) == []
    assert len(tennis_tab._load_predictions(unsettled_only=True)) == 1
