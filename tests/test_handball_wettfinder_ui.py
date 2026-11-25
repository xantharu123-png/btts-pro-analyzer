"""Handball projection stays in the display catalog, outside tip machinery."""
from datetime import datetime, timedelta
import sys
from types import SimpleNamespace

import app
from test_daily3_selection import NOW, _admitted, tennis
from test_workflow_integrity import _RecordingStreamlit, _automatic_status


def _selection(game_id='DE:39:2030:101', *, home='Nordstadt', league='Bundesliga',
               side='home', probability=.64, start_minutes=40, expires_minutes=20):
    return SimpleNamespace(
        event_id=game_id, league=league, home=home, away='Südstadt',
        starts_at=NOW + timedelta(minutes=start_minutes), side=side,
        probability=probability, expires_at=NOW + timedelta(minutes=expires_minutes),
    )


def _render(monkeypatch, selections, *, filters=None, normal=(), instant=NOW, status=True):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant

    class UI(_RecordingStreamlit):
        def slider(self, label, low, high, value, *, key=None, **kwargs):
            sliders[key] = value
            return super().slider(label, low, high, value, key=key, **kwargs)

    def editorial(choices, tennis_cards, **kwargs):
        rails.append((tuple(choice.signal.key for choice in choices), tuple(card.key for card in tennis_cards)))

    def receipt(surface, signals, *, event_lead_keys, **kwargs):
        receipts.append((surface, tuple(signal.key for signal in signals), tuple(event_lead_keys)))

    def read(*, now):
        return selections

    sliders, timers, receipts, bookmarks, rails = {}, [], [], [], []
    ui = UI(widget_values=filters)
    monkeypatch.setattr(app, 'st', ui)
    monkeypatch.setattr(app, 'datetime', Clock)
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot',
                        lambda *, now: SimpleNamespace(status=_automatic_status(NOW) if status else None,
                                                       forecasts=normal))
    monkeypatch.setitem(sys.modules, 'handball_publication', SimpleNamespace(read_handball_selections=read))
    monkeypatch.setattr(app, '_render_editorial_rail', editorial)
    monkeypatch.setattr(app, '_daily3_rail_allowed', lambda: True)
    monkeypatch.setattr(app, 'render_tip_bookmark', lambda candidate, **kwargs: bookmarks.append(kwargs['key']))
    monkeypatch.setattr('tip_publication.record_signal_catalog', receipt)
    monkeypatch.setattr(app, '_schedule_wettfinder_cutoff', lambda deadline, source: timers.append(deadline))
    app._render_automated_daily_selection()
    return SimpleNamespace(ui=ui, sliders=sliders, bookmarks=bookmarks, receipts=receipts, rails=rails,
                           timers=timers, html='\n'.join(s for s, _, _ in ui.markdown_calls))


def test_dedicated_handball_uses_own_zero_slider_without_touching_tips_or_manual_search(monkeypatch):
    player = _admitted(tennis())
    page = _render(monkeypatch, [_selection()], normal=(player,), filters={
        'wettfinder_automatic_sport_v2': 'Handball', 'wettfinder_min_chance': 95,
    })
    assert 'Handball' in page.ui.segmented_controls[0][1]
    assert 'Handball' not in app._finder_sports_for_selection('Alle')
    assert page.sliders['wettfinder_handball_min_chance'] == 0
    assert 'Handball · Bundesliga' in page.html
    assert 'Nordstadt' in page.html and '64' in page.html and '1X2' in page.html
    assert 'data-featured=' not in page.html
    assert 'Spieler A' not in page.html
    assert not page.bookmarks and not page.receipts
    assert page.rails == [((player.key,), (player.key,))]


def test_mixed_default_respects_70_percent_without_archiving_or_bookmarking_handball(monkeypatch):
    player = _admitted(tennis())
    page = _render(monkeypatch, [_selection(),
                               _selection('ES:58:2030:101', home='Barcelona', league='Liga ASOBAL',
                                          probability=.81, start_minutes=30)], normal=(player,))
    assert page.sliders['wettfinder_min_chance'] == 70
    assert 'Barcelona' in page.html and 'Nordstadt' not in page.html
    assert page.bookmarks == [f'wettfinder_v2_{player.key}']
    assert page.receipts == [('wettfinder_automatic', (player.key,), ())]
    assert page.rails == [((player.key,), (player.key,))]


def test_market_view_keeps_1x2_in_results_and_sorts_namespaced_games_by_kickoff(monkeypatch):
    page = _render(monkeypatch, [_selection(),
                               _selection('ES:58:2030:101', home='Barcelona', league='Liga ASOBAL',
                                          side='draw', start_minutes=25)], filters={
        'wettfinder_automatic_sport_v2': 'Handball',
        'wettfinder_market_view': 'Bester je Wettart',
        'wettfinder_market_family': 'Sieger & Ergebnis',
    })
    assert page.html.index('Barcelona') < page.html.index('Nordstadt')
    assert 'Unentschieden' in page.html
    assert not page.bookmarks and not page.receipts
    corner_view = _render(monkeypatch, [_selection()], filters={
        'wettfinder_automatic_sport_v2': 'Handball',
        'wettfinder_market_view': 'Bester je Wettart',
        'wettfinder_market_family': 'Ecken',
    })
    assert 'Nordstadt' not in corner_view.html


def test_handball_alone_expires_on_open_page_at_quote_deadline_or_kickoff(monkeypatch):
    filters = {'wettfinder_automatic_sport_v2': 'Handball'}
    game = _selection()
    earlier_kickoff = _selection(start_minutes=10)
    assert _render(monkeypatch, [earlier_kickoff], filters=filters, status=False).timers == [earlier_kickoff.starts_at]
    page = _render(monkeypatch, [game], filters=filters, status=False)
    assert page.timers == [game.expires_at] and 'Nordstadt' in page.html
    expired = _render(monkeypatch, [game], filters=filters, instant=game.expires_at, status=False)
    assert 'Nordstadt' not in expired.html and expired.timers == []
