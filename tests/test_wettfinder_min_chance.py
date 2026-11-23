"""Viewer-chosen minimum model chance on the Wettfinder page (owner 05.11.2026)."""
import math
from dataclasses import replace
from datetime import datetime

import pytest

import app
from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog, meets_min_probability


def _signal(game, probability, market='HOME_OVER_1_5'):
    return priced(football(game, market, probability), (1.8,) * 3)


def _card(game, probability, market='HOME_OVER_1_5'):
    signal = _signal(game, probability, market)
    return build_wettfinder_card(signal, signal.reference_quote, now=NOW)


def _shown(catalog):
    return {card.key: card.model_probability for card in (*catalog.featured, *catalog.additional)}


def test_minimum_keeps_the_shown_percentage_and_drops_lower_chances():
    cards = [_card(1, .292), _card(2, .50), _card(3, .4996), _card(4, .766)]
    assert len(_shown(compose_wettfinder_catalog(cards))) == 4
    shown = _shown(compose_wettfinder_catalog(cards, min_probability=.5))
    # 49.96 % is shown as 50.0 % and therefore passes a 50 % minimum.
    assert sorted(shown.values()) == [.4996, .50, .766]
    assert sorted(_shown(compose_wettfinder_catalog(cards, min_probability=.8)).values()) == []


def test_minimum_never_changes_cards_or_featured_order_of_kept_cards():
    cards = [_card(game, .55 + game / 100) for game in range(1, 7)]
    full = compose_wettfinder_catalog(cards)
    narrowed = compose_wettfinder_catalog(cards, min_probability=.5)
    assert full == narrowed


@pytest.mark.parametrize('value', [True, -.01, 1.01, math.nan, '0.5', None])
def test_invalid_minimum_is_rejected(value):
    with pytest.raises(ValueError):
        compose_wettfinder_catalog([_card(1, .7)], min_probability=value)


@pytest.mark.parametrize('value', [None, True, math.nan, -.1, 1.2, '0.9'])
def test_unknown_chance_never_passes_a_minimum(value):
    assert meets_min_probability(replace(_card(1, .7), model_probability=value), .0) is False


def _render(monkeypatch, forecasts, widget_values=None):
    from test_workflow_integrity import _RecordingStreamlit, _automatic_status, _patch_automatic_snapshot
    import tip_publication

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    recorder, catalogs, recorded = _RecordingStreamlit(widget_values=widget_values or {}), [], []
    monkeypatch.setattr(app, 'st', recorder)
    monkeypatch.setattr(app, 'datetime', Clock)
    _patch_automatic_snapshot(monkeypatch, status=_automatic_status(NOW), forecasts=forecasts)
    monkeypatch.setattr(app, '_render_wettfinder_games', lambda result, *a, **kw: catalogs.append(result))
    def capture_catalog(surface, signals, **kwargs):
        if surface == "wettfinder_automatic":
            recorded.append([s.key for s in signals])

    monkeypatch.setattr(tip_publication, 'record_signal_catalog', capture_catalog)
    app._render_automated_daily_selection()
    return recorder, catalogs, recorded


def test_page_defaults_to_fifty_percent_and_records_the_unfiltered_catalog(monkeypatch):
    low, high = _signal(1, .292), _signal(2, .766)
    recorder, catalogs, recorded = _render(monkeypatch, [low, high])
    assert 'wettfinder_v2_min_chance' in recorder.containers
    assert set(_shown(catalogs[0])) == {high.key}
    assert set(recorded[0]) == {low.key, high.key}


def test_slider_value_narrows_and_widens_the_page(monkeypatch):
    low, high = _signal(1, .292), _signal(2, .766)
    _recorder, catalogs, _recorded = _render(monkeypatch, [low, high], {'wettfinder_min_chance': 0})
    assert set(_shown(catalogs[0])) == {low.key, high.key}
    _recorder, catalogs, _recorded = _render(monkeypatch, [low, high], {'wettfinder_min_chance': 80})
    assert catalogs == []


def test_empty_view_tells_the_viewer_to_move_the_slider(monkeypatch):
    recorder, catalogs, recorded = _render(monkeypatch, [_signal(1, .55)], {'wettfinder_min_chance': 60})
    assert catalogs == [] and recorded and recorded[0]
    infos = [value for kind, value in recorder.messages if kind == 'info']
    assert any('Keine Auswahl ab 60 % Modellchance' in str(value) for value in infos)


def test_market_view_lists_a_lower_probability_result_without_changing_the_standard(monkeypatch):
    high = _signal(1, .79)
    winner = _signal(2, .57, "RESULT_HOME")
    corner = _signal(3, .61, "AWAY_CORNERS_OVER_3_5")
    _recorder, catalogs, recorded = _render(monkeypatch, [high, winner, corner],
        {"wettfinder_market_view": "Bester je Wettart", "wettfinder_market_family": "Sieger & Ergebnis"})
    assert set(_shown(catalogs[0])) == {winner.key}
    assert recorded == []
    _recorder, catalogs, recorded = _render(monkeypatch, [high, winner, corner])
    assert set(_shown(catalogs[0])) == {high.key}
    assert set(recorded[0]) == {high.key, winner.key, corner.key}


def test_actual_ui_page_receipt_uses_filter_page_and_never_archives_tomorrow(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import consumer_tip_history as history
    import tip_publication
    from test_workflow_integrity import _RecordingStreamlit, _automatic_status
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    signals = [priced(football(i, probability=.65, start_hours=1+i/100), (1.8,)*3)
               for i in range(1, 22)]
    signals.append(priced(football(22, probability=.90, start_hours=27), (1.8,)*3))
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot', lambda **kw:
                        SimpleNamespace(status=_automatic_status(NOW), forecasts=signals))
    monkeypatch.setattr(app, 'datetime', Clock)
    monkeypatch.setattr(history, '_now', lambda: NOW)
    monkeypatch.setattr(tip_publication, 'DEFAULT_HISTORY_DB', tmp_path/'tips.db')
    monkeypatch.setattr(tip_publication, 'DEFAULT_FORECAST_DB', tmp_path/'missing.db')
    monkeypatch.setattr(app, '_daily3_rail_allowed', lambda: False)
    monkeypatch.setattr(app, '_render_editorial_rail', lambda *a, **k: None)
    ui = _RecordingStreamlit(widget_values={"wettfinder_market_view": "Bester je Wettart"})
    monkeypatch.setattr(app, 'st', ui)
    app._render_automated_daily_selection()
    assert not history.read_tip_publications(tmp_path/'tips.db', surface='wettfinder_automatic_event_leads')
    # The opt-in view cannot replace the first record of actually shown standard leads.
    ui = _RecordingStreamlit(widget_values={'wettfinder_min_chance': 60, 'wettfinder_games_page_Alle_2': 2})
    monkeypatch.setattr(app, 'st', ui)
    app._render_automated_daily_selection()
    rows = history.read_tip_publications(tmp_path/'tips.db', surface='wettfinder_automatic_event_leads')
    assert len(rows) == 1
    assert [t['fixture_id'] for t in rows[0]['tips']] == [21]
    inventory, = history.read_tip_publications(tmp_path/'tips.db', surface='wettfinder_automatic')
    # Existing unfiltered inventory (including next-day previews) remains unchanged.
    assert {t['fixture_id'] for t in inventory['tips']} == set(range(1, 23))


def _render_page_for_test(many_games=False):
    """Run the real page renderer with Streamlit's own slider widget."""
    from datetime import datetime as real_datetime
    from types import SimpleNamespace
    import app
    import tip_publication
    from test_daily3_selection import NOW
    from test_workflow_integrity import _automatic_status
    from test_wettfinder_min_chance import _signal

    class Clock(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    saved = (app.automated_wettfinder_snapshot, app.datetime, tip_publication.record_signal_catalog)
    forecasts = (tuple(_signal(i, .766) for i in range(1, 23)) if many_games else
                 (_signal(1, .292), _signal(2, .766)))
    app.automated_wettfinder_snapshot = lambda **_: SimpleNamespace(status=_automatic_status(NOW), forecasts=forecasts)
    app.datetime = Clock
    tip_publication.record_signal_catalog = lambda *a, **kw: None
    try:
        app._render_automated_daily_selection()
    finally:
        app.automated_wettfinder_snapshot, app.datetime, tip_publication.record_signal_catalog = saved


def test_real_streamlit_slider_starts_at_seventy_and_moves_the_page():
    from streamlit.testing.v1 import AppTest
    ui = AppTest.from_function(_render_page_for_test).run(timeout=60)
    assert not ui.exception
    slider, = [item for item in ui.slider if item.key == 'wettfinder_min_chance']
    # Owner 10.11.2026 „Liste ab 70 %“: the page starts with the 70 % list, the viewer can slide lower.
    assert slider.value == 70 and slider.label == 'Mindest-Modellchance (%)'
    assert _shown_games(ui) == ['Heimteam 2']
    slider.set_value(25).run(timeout=60)
    assert not ui.exception
    assert sorted(_shown_games(ui)) == ['Heimteam 1', 'Heimteam 2']


def test_real_streamlit_switch_preserves_independent_minimums():
    from streamlit.testing.v1 import AppTest

    ui = AppTest.from_function(_render_page_for_test).run(timeout=60)
    assert not ui.exception
    ui.slider(key="wettfinder_min_chance").set_value(80).run(timeout=60)
    ui.radio(key="wettfinder_market_view").set_value("Bester je Wettart").run(timeout=60)
    assert not ui.exception
    assert ui.slider(key="wettfinder_market_min_chance").value == 0
    assert sorted(_shown_games(ui)) == ["Heimteam 1", "Heimteam 2"]
    ui.slider(key="wettfinder_market_min_chance").set_value(50).run(timeout=60)
    assert _shown_games(ui) == ["Heimteam 2"]
    ui.radio(key="wettfinder_market_view").set_value("Übersicht").run(timeout=60)
    assert not ui.exception
    assert ui.slider(key="wettfinder_min_chance").value == 80
    assert _shown_games(ui) == []
    ui.radio(key="wettfinder_market_view").set_value("Bester je Wettart").run(timeout=60)
    assert ui.slider(key="wettfinder_market_min_chance").value == 50


def test_real_streamlit_switch_remembers_category_and_pages_separately():
    from streamlit.testing.v1 import AppTest

    ui = AppTest.from_function(_render_page_for_test, args=(True,)).run(timeout=60)
    ui.selectbox(key="wettfinder_games_page_Alle_2").select(2).run(timeout=60)
    ui.radio(key="wettfinder_market_view").set_value("Bester je Wettart").run(timeout=60)
    ui.selectbox(key="wettfinder_market_family").select("Tore Über/Unter").run(timeout=60)
    alt_page_key = "wettfinder_games_page_Alle_Tore Über/Unter_2"
    assert ui.selectbox(key=alt_page_key).value == 1
    ui.selectbox(key=alt_page_key).select(2).run(timeout=60)
    ui.radio(key="wettfinder_market_view").set_value("Übersicht").run(timeout=60)
    assert not ui.exception
    assert ui.selectbox(key="wettfinder_games_page_Alle_2").value == 2
    ui.radio(key="wettfinder_market_view").set_value("Bester je Wettart").run(timeout=60)
    assert ui.selectbox(key="wettfinder_market_family").value == "Tore Über/Unter"
    assert ui.selectbox(key=alt_page_key).value == 2


def _shown_games(ui):
    # Owner 15.11.2026: games are open RisikoBet-style rows, never an expander. Owner 17.11.2026: the only
    # drawer is the closed „Analyse anzeigen“ under a game, as on the RisikoBet page.
    assert {block.label for block in ui.expander} <= {'Analyse anzeigen'}
    return [block.value.split('<strong>')[1].split(' vs ')[0] for block in ui.markdown
            if 'class="rb-row wf-rb-row"' in block.value]
