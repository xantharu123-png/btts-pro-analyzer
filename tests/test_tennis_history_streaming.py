"""Whole-inventory identity checks with bounded decoded-object lifetime."""
from datetime import timedelta
import sqlite3
import weakref

import pytest

from context_models.contracts import ContextIntegrityError
from context_sources import tennis_status
from context_observations import _SELECT, _decode_receipt
from tennis.history_projection import PreparedTennisHistory
from test_context_tennis_capture import NOW, competition, persist, records


def seed(path):
    for tour, slug in (("ATP", "mens-singles"), ("WTA", "womens-singles")):
        for index in range(6):
            clock = NOW-timedelta(hours=index+1)
            persist(path, records(competition(id=str(300+index)), clock=clock, tour=tour, slug=slug), clock=clock)


def test_streamed_projection_matches_full_legacy_selection(tmp_path):
    path = tmp_path/"db"
    seed(path)
    with sqlite3.connect(path) as con:
        all_rows = tuple(_decode_receipt(raw) for raw in con.execute(_SELECT))
    for tour in ("ATP", "WTA"):
        legacy = tennis_status.select_tennis_observations(all_rows, cutoff=NOW, tour=tour)
        assert tennis_status.tennis_observations_as_of(path, cutoff=NOW, tour=tour) == legacy
        prepared = tennis_status.tennis_observations_as_of(path, cutoff=NOW, tour=tour, prepared=True)
        expected = PreparedTennisHistory(legacy)
        assert prepared.observation_refs == expected.observation_refs
        for row in legacy:
            event = {"event_key": row["event_key"], "home_id": "unknown", "away_id": "unknown"}
            assert prepared.for_event(event) == expected.for_event(event)


def test_full_decoded_inventory_is_never_retained_and_sql_is_closed(tmp_path, monkeypatch):
    import context_observations
    path = tmp_path/"db"
    seed(path)
    living, peak = [], []
    class Receipt(dict): pass
    def decode(raw):
        living[:] = [ref for ref in living if ref() is not None]
        row = Receipt(_decode_receipt(raw))
        living.append(weakref.ref(row))
        peak.append(len(living))
        # A CPU-stage write must not wait for this reader's image transaction.
        with sqlite3.connect(path, timeout=.05) as con:
            con.execute("BEGIN EXCLUSIVE")
            con.rollback()
        return row
    monkeypatch.setattr(context_observations, "_decode_receipt", decode)
    owner = tennis_status.tennis_observations_as_of(path, cutoff=NOW, tour="ATP", prepared=True)
    assert owner.observation_refs and max(peak) <= 2


@pytest.mark.parametrize("tour,clock", [("WTA", NOW-timedelta(hours=1)), ("ATP", NOW+timedelta(hours=1))])
def test_other_tour_and_future_corruption_still_fail(tmp_path, tour, clock):
    path = tmp_path/"db"
    persist(path, records(competition(), clock=clock, tour=tour,
                         slug="mens-singles" if tour == "ATP" else "womens-singles"), clock=clock)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE context_observations SET event_key='hidden:corruption'")
    with pytest.raises(ContextIntegrityError):
        tennis_status.tennis_observations_as_of(path, cutoff=NOW, tour="ATP", prepared=True)
