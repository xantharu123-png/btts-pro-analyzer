"""Display ordering never changes model selection or breaks event groups."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import math
import pytest

from tip_display_order import START_TIME, PROBABILITY, ordered_event_rows, display_order_control, recommendation_probability


@dataclass(frozen=True)
class Row:
    event: str
    start: object
    chance: object
    selection: str
    quote: object = None


def ordered(rows, mode=START_TIME):
    return ordered_event_rows(rows, mode=mode, event_key=lambda r: r.event,
                              starts_at=lambda r: r.start, probability=lambda r: r.chance)


def test_default_is_ascending_actual_start_not_probability_or_feature_role():
    rows = [Row('late', '2026-10-11T21:00:00+02:00', .99, 'late'),
            Row('early', '2026-10-11T14:00:00+02:00', .40, 'early')]
    assert [r.event for r in ordered(rows)] == ['early', 'late']


def test_probability_order_keeps_whole_events_together_and_uses_best_visible_market():
    rows = [Row('a', '2026-10-11T14:00:00Z', .40, 'a1'),
            Row('b', '2026-10-11T15:00:00Z', .70, 'b1'),
            Row('a', '2026-10-11T14:00:00Z', .80, 'a2')]
    assert [r.selection for r in ordered(rows, PROBABILITY)] == ['a2', 'a1', 'b1']
    assert [r.selection for r in ordered(rows)] == ['a1', 'a2', 'b1']
    assert ordered(rows, PROBABILITY)[0] is rows[2]


def test_utc_offset_and_dst_repeated_hour_compare_actual_instants():
    rows = [Row('second', '2026-10-25T02:30:00+01:00', .8, 'second'),
            Row('first', '2026-10-25T02:30:00+02:00', .7, 'first')]
    assert [r.event for r in ordered(rows)] == ['first', 'second']


def test_missing_naive_and_invalid_clocks_are_last_never_guessed_from_display():
    valid = Row('valid', datetime(2026, 10, 11, tzinfo=timezone.utc), .5, 'valid')
    rows = [Row('unknown', None, .9, 'unknown'), Row('naive', '2026-10-11T08:00:00', .8, 'naive'),
            Row('display', '11.10. 08:00', .7, 'display'), valid]
    assert ordered(rows)[0] is valid
    assert len(ordered(rows)) == 4


def test_unknown_event_identities_do_not_merge_unrelated_games():
    rows = [Row(None, '2026-10-11T20:00:00Z', .4, 'late'),
            Row(None, '2026-10-11T12:00:00Z', .9, 'early')]
    assert [r.selection for r in ordered(rows)] == ['early', 'late']
    assert [r.selection for r in ordered(rows, PROBABILITY)] == ['early', 'late']


def test_recommendation_percent_probabilities_are_normalized_for_display_only():
    from types import SimpleNamespace
    candidates = [SimpleNamespace(event_key='early', model_probability=70., starts_at='2026-10-11T12:00:00Z'),
                  SimpleNamespace(event_key='late', model_probability=90., starts_at='2026-10-11T20:00:00Z')]
    result = ordered_event_rows(candidates, mode=PROBABILITY, event_key=lambda c: c.event_key,
        starts_at=lambda c: c.starts_at, probability=recommendation_probability)
    assert result == (candidates[1], candidates[0])
    assert [c.model_probability for c in candidates] == [70., 90.]
    assert recommendation_probability(SimpleNamespace(model_probability=None)) is None


@pytest.mark.parametrize('bad', [None, True, float('nan'), math.inf, -.1, 1.1])
def test_invalid_probability_never_becomes_best_group(bad):
    rows = [Row('invalid', None, bad, 'bad'), Row('good', None, .01, 'good')]
    assert ordered(rows, PROBABILITY)[0] is rows[1]


def test_prices_names_and_input_mutation_do_not_affect_order_or_values():
    rows = [Row('b', '2026-10-11T20:00:00Z', .8, 'b', 1.01),
            Row('a', '2026-10-11T19:00:00Z', .6, 'a', 50.)]
    assert [r.event for r in ordered(rows)] == [r.event for r in ordered([replace(r, quote=2.) for r in rows])]
    assert [r.event for r in rows] == ['b', 'a']
    assert {id(r) for r in ordered(rows)} == {id(r) for r in rows}


def test_control_defaults_to_starttime_and_explicit_choice_is_only_display_state():
    class UI:
        def selectbox(self, label, options, **kwargs):
            assert label == 'Reihenfolge' and options == (START_TIME, PROBABILITY)
            assert kwargs['key'] == 'view-order' and kwargs['index'] == 0
            return PROBABILITY
    assert display_order_control(UI(), key='view-order') == PROBABILITY


def test_unmodelled_schedule_control_does_not_offer_probability_ranking():
    class UI:
        def selectbox(self, label, options, **kwargs):
            assert label == 'Reihenfolge' and options == (START_TIME,)
            return START_TIME
    assert display_order_control(UI(), key='schedule-order', probability_available=False) == START_TIME


def test_unknown_order_is_rejected_instead_of_silent_probability_ranking():
    with pytest.raises(ValueError):
        ordered([], 'Value')


@pytest.mark.parametrize('mode,expected', [(START_TIME, ['early', 'late']), (PROBABILITY, ['late', 'early'])])
def test_automatic_renderer_does_not_force_later_featured_games_before_earlier_games(monkeypatch, mode, expected):
    import app
    import wettfinder_surface as surface
    from test_wettfinder_surface import _card, _signal
    from test_workflow_integrity import _RecordingStreamlit
    early = replace(_card(_signal('early', event='Early vs Opponent')),
                    scheduled_start='2026-10-11T12:00:00Z', model_probability=.4)
    late = replace(_card(_signal('late', event='Late vs Opponent')),
                   scheduled_start='2026-10-11T20:00:00Z', model_probability=.9)
    catalog = surface.WettfinderCatalog((late,), (early,), ())
    seen = []
    monkeypatch.setattr(app, 'st', _RecordingStreamlit())
    monkeypatch.setattr(app, '_render_wettfinder_game', lambda group, *_args: seen.append(group.cards[0].key))
    app._render_wettfinder_games(catalog, {}, sport_filter='Alle', sort_mode=mode)
    assert seen == expected


def test_riskobet_orders_the_combined_catalog_not_each_section_separately():
    import riskobet_ui
    from test_riskobet_surface import _candidate, _card
    from riskobet_surface import RiskBetCatalog
    late = _candidate('late-sort', event_key='event-late', model_probability=.8)
    early = replace(_candidate('early-sort', event_key='event-early', model_probability=.4),
                    starts_at=late.starts_at.replace(hour=14))
    late_card, early_card = _card(late), _card(early)
    catalog = RiskBetCatalog((late_card,), (early_card,))
    result = riskobet_ui._ordered_riskobet_cards(catalog,
        {late_card.candidate_id: late, early_card.candidate_id: early}, START_TIME)
    assert result == (early_card, late_card)


@pytest.mark.parametrize('mode,first,table_order', [
    (START_TIME, 'early', ['excluded', 'early', 'middle', 'late']),
    (PROBABILITY, 'late', ['late', 'middle', 'early', 'excluded'])])
def test_prematch_real_renderer_sorts_percent_candidates_and_table_after_selection(monkeypatch, mode, first, table_order):
    import app
    import pandas as pd
    from types import SimpleNamespace
    from test_workflow_integrity import _RecordingStreamlit
    ui = _RecordingStreamlit(widget_values={'prematch_display_order': mode})
    ui.success = lambda _message: None
    tables, rendered, rendered_sources = [], [], []
    ui.dataframe = lambda frame, **_kwargs: tables.append(frame)
    monkeypatch.setattr(app, 'st', ui)
    monkeypatch.setattr(app, '_freemode_enabled', lambda: False)
    monkeypatch.setattr(app, 'prematch_btts_candidate', lambda row, **_kwargs: SimpleNamespace(
        model_ready=True, event_key=row['event'], event_label=row['event'], selection='Ja', market='BTTS',
        risk_adjusted_probability=row['BTTS_num'], model_probability=row['BTTS_num']))
    def record_selection(candidate, *, save_source):
        rendered.append(candidate.event_key)
        rendered_sources.append(save_source)
    monkeypatch.setattr(app, 'render_model_selection', record_selection)
    rows = pd.DataFrame([dict(event=event, BTTS_num=p, Quality_num=90,
        _fixture_date=f'2026-10-11T{hour:02d}:00:00Z') for event, p, hour in
        [('late', 90., 20), ('early', 70., 12), ('middle', 80., 15), ('excluded', 60., 10)]])
    before = rows.copy(deep=True)
    app._render_prematch_results(rows, 58, 70, scanned_at=None, validated_model_available=True)
    # The earliest low-ranked game is visible in the all-games table, but the
    # presentation control does not promote it into the original three picks.
    assert rendered == [first]
    assert rendered_sources == ['Fußball Prematch']
    assert tables[0]['Spiel'].tolist() == table_order
    pd.testing.assert_frame_equal(rows, before)


def test_manual_esports_sort_uses_percent_and_keeps_selected_original_event(monkeypatch):
    import app
    from types import SimpleNamespace
    from manual_search_filters import SearchFilters
    from multi_sport_recommendations import RecommendationCandidate
    from test_workflow_integrity import _RecordingStreamlit
    now = datetime.now(timezone.utc)
    items = [dict(id=90, source='pandascore', status='upcoming', begin_at='2026-10-11T20:00:00Z'),
             dict(id=70, source='pandascore', status='upcoming', begin_at='2026-10-11T12:00:00Z')]
    def candidate(item):
        return RecommendationCandidate(str(item['id']), 'E-Sport', str(item['id']), 'Sieger', 'Team',
            None, float(item['id']), float(item['id']), None, None, None, 'existing', None, ())
    results = [SimpleNamespace(item=item, candidate=candidate(item), quote=None) for item in items]
    scope = app._multi_sport_scope_key('E-Sport', 'Alle Spiele', now.date(), now.date())
    ui = _RecordingStreamlit({'multi_sport_snapshots': {scope: {'items': items,
        'scanned_at': now.isoformat(), 'credentials_available': True}}},
        widget_values={f'multi_sport_event_{scope}': 0})
    rendered = []
    monkeypatch.setattr(app, 'st', ui)
    monkeypatch.setattr(app, '_job_key', lambda _name: 'offline')
    monkeypatch.setattr(app.scan_jobs, 'get_job', lambda _key: {'state': 'idle'})
    monkeypatch.setattr(app.scan_jobs, 'start_job', lambda *_args, **_kwargs: pytest.fail('display cannot scan'))
    monkeypatch.setattr(app, 'esports_search_results', lambda *_args: results)
    monkeypatch.setattr(app, '_multi_sport_release_blockers', lambda *_args: ())
    monkeypatch.setattr(app, 'render_model_selection', lambda c: rendered.append(c.event_key))
    for mode, expected in [(START_TIME, (1, 0)), (PROBABILITY, (0, 1))]:
        ui.widget_values['manual_esport_order'] = mode
        app.render_multi_sport('E-Sport', now.date(), now.date(), SearchFilters())
        assert ui.selectboxes[-1][1] == expected
        assert rendered[-1] == '90'  # Current selection remains original event 0.
    assert [item['id'] for item in items] == [90, 70]


def test_manual_hockey_schedule_default_is_chronological_without_fake_chance_choice(monkeypatch):
    import app
    from types import SimpleNamespace
    from test_workflow_integrity import _RecordingStreamlit
    now = datetime.now(timezone.utc)
    items = [dict(id=90, source='nhl', status='upcoming', start_time='2026-10-11T20:00:00Z'),
             dict(id=70, source='nhl', status='upcoming', start_time='2026-10-11T12:00:00Z')]
    scope = app._multi_sport_scope_key('Eishockey', None, now.date(), now.date())
    ui = _RecordingStreamlit({'multi_sport_snapshots': {scope: {'items': items, 'scanned_at': now.isoformat()}}})
    rendered = []
    monkeypatch.setattr(app, 'st', ui)
    monkeypatch.setattr(app, '_job_key', lambda _name: 'offline')
    monkeypatch.setattr(app.scan_jobs, 'get_job', lambda _key: {'state': 'idle'})
    monkeypatch.setattr(app.scan_jobs, 'start_job', lambda *_args, **_kwargs: pytest.fail('display cannot scan'))
    monkeypatch.setattr(app, 'build_candidate', lambda sport, item, **_kwargs: SimpleNamespace(
        event_key=str(item['id']), expected_total=None))
    monkeypatch.setattr(app, '_multi_sport_release_blockers', lambda *_args: ())
    monkeypatch.setattr(app, 'render_model_selection', lambda c: rendered.append(c.event_key))
    app.render_multi_sport('Eishockey', now.date(), now.date())
    assert ui.selectboxes[0][1] == (START_TIME,)
    assert ui.selectboxes[1][1] == (1, 0)
    assert rendered == ['70']
    assert [item['id'] for item in items] == [90, 70]


@pytest.mark.parametrize('mode,expected', [(START_TIME, ['2:BTTS', '1:BTTS']),
                                         (PROBABILITY, ['1:BTTS', '2:BTTS'])])
def test_15k_actual_card_and_ticket_options_share_display_order_without_ledger_write(monkeypatch, mode, expected):
    import challenge_15k
    from unittest.mock import Mock, MagicMock
    from test_challenge_15k import stress_safe_ticket_candidates
    first, second = stress_safe_ticket_candidates()
    first.kickoff = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)).isoformat()
    second.kickoff = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)).isoformat()
    ui, ledger = MagicMock(), Mock()
    ui.selectbox.return_value = mode
    ui.multiselect.return_value = []
    monkeypatch.setattr(challenge_15k, 'st', ui)
    challenge_15k._render_model_challenge({'challenge_model_candidates': [first, second]}, ledger, {})
    assert ui.multiselect.call_args.kwargs['options'] == expected
    assert [call.args[0].split(' · ')[0] for call in ui.expander.call_args_list] == [
        f'Home {key[0]} vs Away {key[0]}' for key in expected]
    assert not ledger.method_calls
