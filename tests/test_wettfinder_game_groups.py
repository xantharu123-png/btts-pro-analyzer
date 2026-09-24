from copy import deepcopy
from dataclasses import replace

import pytest

import app
from wettfinder_surface import (
    WettfinderCatalog, build_wettfinder_card, compose_wettfinder_catalog,
    group_wettfinder_games, render_compact_row_html, wettfinder_game_label,
)
from test_daily3_selection import NOW, football, tennis
from test_forecast_compact import InitialText
from test_workflow_integrity import _RecordingStreamlit


def card(game=1, market='DC_X2'):
    return build_wettfinder_card(football(game, market), now=NOW)


def test_featured_and_additional_markets_of_same_game_merge_once_without_data_changes():
    cards = [card(1, 'AWAY_OVER_2_5'), card(1, 'AWAY_RANGE_2_4'), card(1),
             card(2, 'BTTS_YES'), card(3, 'HOME_OVER_1_5')]
    catalog = compose_wettfinder_catalog(cards)
    before = deepcopy(catalog)
    groups = group_wettfinder_games(catalog)
    visible = catalog.featured + catalog.additional
    assert len(groups) == 3 and len({g.fixture_identity for g in groups}) == 3
    first_game = next(g for g in groups if g.cards[0].fixture_id == 1)
    assert {c.market_key for c in first_game.cards} == {'AWAY_OVER_2_5', 'AWAY_RANGE_2_4', 'DC_X2'}
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


def test_grouped_market_does_not_repeat_game_heading_but_keeps_exact_price_binding():
    c = card()
    markup = render_compact_row_html(c, grouped=True, featured=True)
    visible = InitialText(markup).visible
    assert c.event_label not in visible
    assert c.selection in visible and c.market in visible
    assert 'MODELL-AUSWAHL' in visible and 'keine gesicherte Mindestchance' in visible
    assert f'data-key="{c.key}"' in markup and 'data-price-code="UNAVAILABLE"' in markup
    assert 'data-grouped="true"' in markup
    assert c.event_label in markup  # aria-label still identifies the complete bet


def test_each_market_action_stays_inside_its_game_once_and_highlight_games_open(monkeypatch):
    cards = [card(1, 'AWAY_OVER_2_5'), card(1), card(2, 'BTTS_YES'), card(3, 'HOME_OVER_1_5')]
    catalog = WettfinderCatalog((cards[0],), tuple(cards[1:]), ())
    rows = {c.key: (None, c) for c in cards}
    recording = _RecordingStreamlit()
    actions = []
    monkeypatch.setattr(app, 'st', recording)
    original_render = app.render_compact_row_html
    def record_render(c, **kwargs):
        actions.append((c.key, recording.current_expander))
        return original_render(c, **kwargs)
    monkeypatch.setattr(app, 'render_compact_row_html', record_render)
    app._render_wettfinder_games(catalog, rows, sport_filter='Alle')
    assert len(recording.expanders) == 3
    assert [opened for _label, opened in recording.expanders] == [True, False, False]
    assert len(actions) == len(cards)
    assert actions[0][1] == actions[1][1]
    assert len({label for _key, label in actions}) == 3
    assert all(label.endswith('2 Auswahlen') for _key, label in actions[:2])
    assert all(len([ctx for ctx in context if ctx[0] == 'expander']) == 1
               for _text, _kwargs, context in recording.markdown_calls if any(c[0] == 'expander' for c in context))


def test_closed_game_preference_survives_widget_cleanup_filter_and_highlight_changes(monkeypatch):
    first = card()
    catalog = WettfinderCatalog((first,), (), ())
    group = group_wettfinder_games(catalog)[0]
    key = app._wettfinder_game_key(group)
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    recording.session_state[key] = False  # Actual callback value after closing.
    app._remember_wettfinder_game_state(key)
    del recording.session_state[key]  # Streamlit cleanup after filtering away.
    app._render_wettfinder_game(group, {first.key: (None, first)}, {first.key})
    assert recording.session_state[key] is False
    recording.session_state[key] = True
    app._remember_wettfinder_game_state(key)
    del recording.session_state[key]
    app._render_wettfinder_game(group, {first.key: (None, first)}, set())
    assert recording.session_state[key] is True


def test_game_open_preferences_do_not_cross_event_keys(monkeypatch):
    left = group_wettfinder_games(WettfinderCatalog((card(1),), (), ()))[0]
    right = group_wettfinder_games(WettfinderCatalog((card(2),), (), ()))[0]
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    left_key, right_key = app._wettfinder_game_key(left), app._wettfinder_game_key(right)
    recording.session_state[left_key] = False
    app._remember_wettfinder_game_state(left_key)
    assert right_key not in recording.session_state['_wettfinder_game_open']
