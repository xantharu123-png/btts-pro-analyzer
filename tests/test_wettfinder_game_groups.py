from copy import deepcopy
from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest

import app
from wettfinder_surface import (
    WettfinderCatalog, build_wettfinder_card, compose_wettfinder_catalog,
    group_wettfinder_games, render_compact_row_html, wettfinder_game_label,
)
from test_daily3_selection import NOW, football, tennis
from test_forecast_compact import InitialText
from test_workflow_integrity import _RecordingStreamlit


def card(game=1, market='DC_X2'):
    from test_publication_odds_floor import priced
    signal = priced(football(game, market), (1.8,)*3)
    return build_wettfinder_card(signal, signal.reference_quote, now=NOW)


def test_featured_and_additional_markets_of_same_game_merge_once_without_data_changes():
    cards = [card(1, 'AWAY_OVER_2_5'), card(1, 'AWAY_OVER_1_5'), card(1),
             card(2, 'BTTS_YES'), card(3, 'HOME_OVER_1_5')]
    catalog = compose_wettfinder_catalog(cards)
    before = deepcopy(catalog)
    groups = group_wettfinder_games(catalog)
    visible = catalog.featured + catalog.additional
    assert len(groups) == 3 and len({g.fixture_identity for g in groups}) == 3
    first_game = next(g for g in groups if g.cards[0].fixture_id == 1)
    assert {c.market_key for c in first_game.cards} == {'AWAY_OVER_2_5', 'AWAY_OVER_1_5', 'DC_X2'}
    assert {id(c) for g in groups for c in g.cards} == {id(c) for c in visible}
    assert sum(len(g.cards) for g in groups) == len(visible)
    assert catalog == before
    assert first_game.cards[0].key in {c.key for c in catalog.featured}


def test_grouping_never_reintroduces_conflicting_markets():
    catalog = compose_wettfinder_catalog([card(1, 'AWAY_OVER_2_5'), card(1, 'AWAY_UNDER_1_5')])
    groups = group_wettfinder_games(catalog)
    assert len(groups) == 1 and len(groups[0].cards) == 1


def test_price_changes_do_not_change_game_order_membership_or_expander_key():
    cards = [card(1, 'AWAY_OVER_2_5'), card(1), card(2, 'BTTS_YES')]
    left = group_wettfinder_games(compose_wettfinder_catalog(cards))
    right = group_wettfinder_games(compose_wettfinder_catalog([
        replace(c, observed_odds=99, price_code='PLAYABLE') for c in cards]))
    assert [(g.fixture_identity, [c.key for c in g.cards]) for g in left] == [
        (g.fixture_identity, [c.key for c in g.cards]) for g in right]
    assert [app._wettfinder_game_key(g) for g in left] == [app._wettfinder_game_key(g) for g in right]


@pytest.mark.parametrize('change', [
    {'fixture_id': 2}, {'sport': 'Basketball'}, {'sport': 'Eishockey'},
    {'sport': 'Cricket'}, {'sport': 'Tennis'}, {'sport': 'E-Sport'},
])
def test_same_label_is_not_enough_to_merge_different_event_or_sport(change):
    first = card()
    second = replace(first, key='different', **change)
    groups = group_wettfinder_games(WettfinderCatalog((first,), (second,), ()))
    assert len(groups) == 2
    assert app._wettfinder_game_key(groups[0]) != app._wettfinder_game_key(groups[1])


def test_provider_event_keys_keep_tennis_rematches_and_sources_separate():
    first = build_wettfinder_card(tennis(), now=NOW)
    others = [replace(first, key='other-match', provider_event_id='t2'),
              replace(first, key='other-source', fixture_source='another')]
    assert len(group_wettfinder_games(WettfinderCatalog((first,), tuple(others), ()))) == 3


def test_same_native_event_different_labels_and_schedule_use_stable_group_key():
    first = card()
    before = group_wettfinder_games(WettfinderCatalog((first,), (), ()))[0]
    second = replace(first, event_label='Corrected names', scheduled_start_label='02.01. 18:00')
    after = group_wettfinder_games(WettfinderCatalog((), (second,), ()))[0]
    assert app._wettfinder_game_key(before) == app._wettfinder_game_key(after)


def test_exact_legacy_kickoff_separates_rematches_without_native_ids():
    first = replace(card(), fixture_id=None)
    other = replace(first, key='return-match', scheduled_start='2030-01-02T15:00:00+00:00')
    assert len(group_wettfinder_games(WettfinderCatalog((first,), (other,), ()))) == 2


def test_header_has_game_count_and_escapes_markdown_but_not_identity():
    first = replace(card(), event_label='A [fake](https://invalid) *x* vs B\nsecond line')
    group = group_wettfinder_games(WettfinderCatalog((first,), (replace(first, key='extra'),), ()))[0]
    label = wettfinder_game_label(group)
    assert r'\[fake\]\(https://invalid\)' in label and r'\*x\*' in label
    assert '\n' not in label and label.endswith('2 Auswahlen')
    assert 'Fußball' in label and first.scheduled_start_label in label


# The price status „TOO_LOW“ belongs to the old value-gate contract; under `floor` a 1,80 median is playable.
@pytest.mark.price_policy("gate")
def test_grouped_market_does_not_repeat_game_heading_but_keeps_exact_price_binding():
    c = card()
    assert c.compact_analysis is not None
    internal_note = 'Interner Sicherheitswert: heuristischer Abschlag, keine gesicherte Mindestchance.'
    c = replace(c, compact_analysis=replace(c.compact_analysis,
        explanation=c.compact_analysis.explanation + (internal_note,)))
    before = deepcopy(c)
    markup = render_compact_row_html(c, grouped=True, featured=True)
    visible = InitialText(markup).visible
    assert c.event_label not in visible
    assert c.selection in visible and c.market in visible
    assert 'MODELL-AUSWAHL' in visible and 'Modell 75.0 %' in visible
    # The approved customer projection omits method notes; the original
    # internal facts and numerical model fields must remain unchanged.
    for text in ('Sicherheitswert', 'heuristisch', 'keine gesicherte Mindestchance'):
        assert text not in markup
    assert internal_note in c.compact_analysis.explanation
    assert c == before
    assert f'data-key="{c.key}"' in markup and 'data-price-code="TOO_LOW"' in markup
    assert 'data-grouped="true"' in markup
    assert c.event_label in markup  # aria-label still identifies the complete bet


def _game_container(context):
    return next((label for kind, label in reversed(context)
                 if kind == 'container' and str(label).startswith('wettfinder_game_row_')), None)


def _row_calls(recording):
    return [(text, _game_container(context)) for text, _kwargs, context in recording.markdown_calls
            if 'class="rb-row wf-rb-row"' in text]


def test_each_market_row_stays_inside_its_game_container_without_expanders(monkeypatch):
    # Owner 15.11.2026: every game open as a RisikoBet-style card, no expander, no jersey header.
    cards = [card(1, 'AWAY_OVER_2_5'), card(1), card(2, 'BTTS_YES'), card(3, 'HOME_OVER_1_5')]
    catalog = WettfinderCatalog((cards[0],), tuple(cards[1:]), ())
    rows = {c.key: (None, c) for c in cards}
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(catalog, rows, sport_filter='Alle')
    # The game is never an expander; only the closed RisikoBet drawer „Analyse anzeigen“ may follow its rows.
    assert all(label == 'Analyse anzeigen' and not expanded for label, expanded in recording.expanders)
    assert not any(kind == 'expander' for text, _kwargs, context in recording.markdown_calls
                   if 'class="rb-row wf-rb-row"' in text for kind, _label in context)
    calls = _row_calls(recording)
    assert len(calls) == len(cards)
    assert all(game is not None for _text, game in calls)
    assert calls[0][1] == calls[1][1]
    assert len({game for _text, game in calls}) == 3
    html = '\n'.join(text for text, _kwargs, _context in recording.markdown_calls)
    assert all(f'data-key="{c.key}"' in html for c in cards)
    assert 'class="se-event' not in html and 'class="se-shield' not in html


def test_game_container_key_follows_the_event_not_the_position(monkeypatch):
    first, second = card(1), card(2, 'BTTS_YES')
    keys = []
    for order in ((first, second), (second, first)):
        recording = _RecordingStreamlit()
        monkeypatch.setattr(app, 'st', recording)
        app._render_wettfinder_games(WettfinderCatalog(order, (), ()), {c.key: (None, c) for c in order},
                                     sport_filter='Alle')
        keys.append({text.split('data-key="')[1].split('"')[0]: game for text, game in _row_calls(recording)})
    assert keys[0] == keys[1]
    assert keys[0][first.key] != keys[0][second.key]


def _render_game_blocks_for_test(count, featured_ids):
    """Exercise the production renderer with actual Streamlit widget state."""
    import streamlit as st
    import app
    from test_daily3_selection import NOW, football
    from wettfinder_surface import WettfinderCatalog, build_wettfinder_card

    mode = app.display_order_control(st, key='game_test_order')
    sport = st.selectbox('Sportart', ('Alle', 'Tennis'), key='game_test_sport')
    shifted = st.checkbox('Andere Highlights', key='game_test_highlights')
    if shifted:
        featured_ids = (count - 2, count - 1, count)
    signals = [football(game, 'DC_X2', .5 + game * .01, start_hours=game)
               for game in range(1, count + 1)]
    cards = [build_wettfinder_card(signal, now=NOW) for signal in signals]
    catalog = WettfinderCatalog(
        tuple(card for card in cards if card.fixture_id in featured_ids),
        tuple(card for card in cards if card.fixture_id not in featured_ids), (),
    ) if sport == 'Alle' else WettfinderCatalog((), (), ())
    app._render_wettfinder_games(catalog,
        {card.key: (signal, card) for signal, card in zip(signals, cards)},
        sport_filter=sport, sort_mode=mode)


def _shown_games(ui):
    import re
    return [int(re.search(r'Heimteam (\d+) vs', block.value).group(1))
            for block in ui.markdown if 'class="rb-row wf-rb-row"' in block.value]


@pytest.mark.parametrize('mode,page,count,expected_games', [
    pytest.param('Startzeit', 1, 5, [1, 2, 3, 4, 5], id='Startzeit-1-5'),
    pytest.param('Wahrscheinlichkeit', 1, 5, [1, 2, 3, 4, 5], id='Wahrscheinlichkeit-1-5'),
    pytest.param('Startzeit', 2, 25, [21, 22, 23, 24, 25], id='Startzeit-2-25'),
    pytest.param('Wahrscheinlichkeit', 2, 25, [21, 22, 23, 24, 25], id='Wahrscheinlichkeit-2-25'),
])
def test_real_renderer_shows_every_visible_game_open_in_display_order(mode, page, count, expected_games):
    ui = AppTest.from_function(_render_game_blocks_for_test, args=(count, (4,)))
    ui.session_state['game_test_order'] = mode
    if page == 2:
        ui.session_state['wettfinder_games_page_Alle_2'] = 2
    ui.run(timeout=30)
    assert not ui.exception
    assert {block.label for block in ui.expander} <= {'Analyse anzeigen'}
    assert _shown_games(ui) == expected_games


def test_real_renderer_follows_sport_filter_and_highlight_changes_without_hiding_games():
    ui = AppTest.from_function(_render_game_blocks_for_test, args=(5, (1, 2, 3))).run(timeout=30)
    assert not ui.exception and _shown_games(ui) == [1, 2, 3, 4, 5]
    ui.selectbox(key='game_test_sport').set_value('Tennis').run(timeout=30)
    assert not ui.exception and _shown_games(ui) == []
    ui.selectbox(key='game_test_sport').set_value('Alle').run(timeout=30)
    assert not ui.exception and _shown_games(ui) == [1, 2, 3, 4, 5]
    ui.checkbox(key='game_test_highlights').check().run(timeout=30)
    assert not ui.exception and _shown_games(ui) == [1, 2, 3, 4, 5]
    assert {block.label for block in ui.expander} <= {'Analyse anzeigen'}
