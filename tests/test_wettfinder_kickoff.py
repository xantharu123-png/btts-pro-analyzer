"""Clock-driven pre-match projection. The synthetic publication deliberately stays unchanged."""
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import app
from test_daily3_selection import NOW, _admitted, _admitted_football, tennis
from test_workflow_integrity import _RecordingStreamlit, _automatic_status


def _page(monkeypatch, forecasts, *, slips=()):
    clock = [NOW]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]
    timers, reads, receipts = [], [], []
    def fragment(*, run_every):
        def register(callback):
            timers.append((run_every, callback))
            return callback
        return register
    def read(*, now):
        reads.append(now)
        return SimpleNamespace(status=_automatic_status(NOW), forecasts=forecasts)
    class Rerun(Exception):
        pass
    class UI(_RecordingStreamlit):
        def rerun(self):
            raise Rerun()
        def progress(self, *a, **k):
            pass
        def text(self, value):
            self.messages.append(('text', value))
    ui = UI(widget_values={'wettfinder_min_chance': 0})
    monkeypatch.setattr(app, 'st', ui)
    monkeypatch.setattr('streamlit.fragment', fragment)
    monkeypatch.setattr(app, 'datetime', Clock)
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot', read)
    monkeypatch.setattr(app, '_daily3_rail_allowed', lambda: True)
    monkeypatch.setattr('daily_accumulator_receipts.load_daily_picks', lambda *a, **k: slips)
    monkeypatch.setattr('tip_publication.record_signal_catalog',
                        lambda surface, signals, **kw: receipts.append((surface, tuple(s.key for s in signals))))
    return ui, clock, timers, reads, receipts, Rerun


def test_open_page_expires_cards_and_both_rails_at_kickoff_without_republishing(monkeypatch):
    soon = _admitted(tennis())  # Tennis box, Doublebet and main list
    later = _admitted_football(2, start_hours=8)
    ui, clock, timers, reads, receipts, rerun = _page(monkeypatch, [later, soon])
    app._render_automated_daily_selection()
    html = [s for s, _, _ in ui.markdown_calls]
    assert ['Spieler A' in el for el in html if 'wf-rb-row"' in el] == [True, False]
    assert any('se-tennis-copy' in el and 'Spieler A' in el for el in html)
    assert any('se-rail-choice' in el and 'Spieler A' in el for el in html)
    assert {surface for surface, _ in receipts} == {'wettfinder_automatic', 'daily3_rail'}
    first_receipts = list(receipts)
    assert len(timers) == 1
    delay, tick = timers[0]
    assert delay == timedelta(hours=2)
    clock[0] += delay - timedelta(microseconds=1)
    tick()
    assert reads == [NOW] and receipts == first_receipts
    clock[0] += timedelta(microseconds=1)
    with pytest.raises(rerun):
        tick()
    ui.markdown_calls.clear()
    app._render_automated_daily_selection()
    html = [s for s, _, _ in ui.markdown_calls]
    assert not any('Spieler A' in el for el in html)
    assert any('Heimteam 2' in el and 'wf-rb-row"' in el for el in html)
    assert timers[-1][0] == timedelta(hours=6)
    assert receipts == first_receipts


@pytest.mark.parametrize('sport', ['Fußball', 'Tennis', 'Eishockey', 'Basketball', 'E-Sport', 'Cricket'])
def test_stale_rows_and_unproven_clocks_do_not_reach_any_prematch_card(monkeypatch, sport):
    fixture = _admitted_football(3)
    # Non-ISO and timezone-naive strings are already rejected by ModelSignal itself.
    starts = [None, '2030-01-01T07:59:59+01:00',
              '2030-01-01T08:00:00+01:00', '2030-01-01T08:00:00.000001+01:00']
    rows = [replace(fixture, key=str(i), sport=sport, scheduled_start=t) for i, t in enumerate(starts)]
    _page(monkeypatch, rows)
    built = []
    build = app.build_wettfinder_card
    def capture(signal, **kwargs):
        built.append(signal.key)
        return build(signal, **kwargs)
    monkeypatch.setattr(app, 'build_wettfinder_card', capture)
    app._render_automated_daily_selection()
    assert built == ['3']


def test_open_original_combination_supplies_its_own_earliest_deadline(monkeypatch):
    from test_daily_accumulator_surface import example
    slip = dict(example(), arm='daily-picks', captured_at=NOW.isoformat(), day=NOW.date().isoformat())
    slip['legs'] = [dict(leg, starts_at=(NOW + timedelta(minutes=i)).isoformat())
                    for i, leg in enumerate(slip['legs'], 1)]
    ui, clock, timers, _, receipts, rerun = _page(monkeypatch, [], slips=[slip])
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot',
                        lambda **kw: SimpleNamespace(status=None, forecasts=()))
    app._render_automated_daily_selection()
    assert not ui.expanders
    assert len(timers) == 1 and timers[0][0] == timedelta(minutes=1)
    before = list(receipts)
    clock[0] += timedelta(minutes=1)
    with pytest.raises(rerun):
        timers[0][1]()
    app._render_automated_daily_selection()
    assert ui.expanders == [('Bereits begonnen (1)', False)]
    assert receipts == before
    assert timers[-1][0] == timedelta(hours=15, minutes=59)  # Zurich midnight removes yesterday's original.


def test_empty_unpublished_page_has_no_kickoff_timer(monkeypatch):
    _, _, timers, _, _, _ = _page(monkeypatch, [])
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot',
                        lambda **kw: SimpleNamespace(status=None, forecasts=()))
    app._render_automated_daily_selection()
    assert timers == []


def test_newly_published_run_at_kickoff_gets_its_normal_visible_receipts(monkeypatch):
    old = _admitted_football(1, start_hours=1)
    new = _admitted_football(2, start_hours=4)
    ui, clock, timers, _, receipts, rerun = _page(monkeypatch, [old])
    app._render_automated_daily_selection()
    initial = list(receipts)
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot', lambda **kw: SimpleNamespace(
        status=_automatic_status(NOW + timedelta(minutes=30)), forecasts=[new]))
    clock[0] += timedelta(hours=1)
    with pytest.raises(rerun):
        timers[0][1]()
    ui.markdown_calls.clear()
    app._render_automated_daily_selection()
    assert any('Heimteam 2' in html for html, _, _ in ui.markdown_calls)
    assert receipts[len(initial):] == [('wettfinder_automatic', (new.key,)), ('daily3_rail', (new.key,))]


def test_browser_wire_delay_never_rounds_below_kickoff(monkeypatch):
    from streamlit.proto.AutoRerun_pb2 import AutoRerun
    # Streamlit transmits seconds in a float32, and browsers use integer milliseconds.
    wait = timedelta(hours=2, microseconds=150)
    item = _admitted_football(7, start_hours=wait.total_seconds() / 3600)
    _, _, timers, _, _, _ = _page(monkeypatch, [item])
    app._render_automated_daily_selection()
    wire = AutoRerun(interval=timers[0][0].total_seconds())
    browser_delay = timedelta(milliseconds=int(wire.interval * 1000))
    assert wait <= browser_delay <= wait + timedelta(milliseconds=125)
