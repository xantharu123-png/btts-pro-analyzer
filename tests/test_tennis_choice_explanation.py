from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

from forecast_analysis import build_forecast_analysis
from forecast_compact import build_compact_analysis, render_compact_analysis_html
from tennis.customer_facts import build_match_statistics
from test_daily3_selection import NOW, tennis


def matchup_signal():
    base = tennis()
    context = deepcopy(base.context_evidence)
    context['surface_evidence'] = {
        'surface': 'Clay', 'surface_elo_applied': True,
        'players': {'a': {'matches': 154, 'elo': 1871.6},
                    'b': {'matches': 93, 'elo': 1830.5}},
        'stats_through': NOW.date().isoformat(),
    }
    rows = [dict(settled=1, player_a='Spieler A', player_b='Gegner A', tour='ATP',
                 surface='Clay', fixture_source='test', provider_event_id='a'+str(i),
                 termination='normal', best_of=3, player_a_sets=2 if i != 2 else 0,
                 player_b_sets=0 if i != 2 else 2,
                 scheduled_start_utc=(NOW-timedelta(days=i)).isoformat(),
                 result_observed_at=(NOW-timedelta(days=i, hours=-2)).isoformat())
            for i in (1, 2, 3)]
    rows += [{**row, 'player_a': 'Spieler B', 'player_b': 'Gegner B',
              'provider_event_id': 'b'+str(i), 'player_a_sets': 2, 'player_b_sets': 0}
             for i, row in enumerate(rows)]
    context['match_statistics'] = build_match_statistics('Spieler A', 'Spieler B', rows,
        surface='Clay', tour='ATP', as_of=NOW)
    return replace(base, probability=.5931, context_evidence=context)


def test_better_opponent_recent_record_does_not_replace_the_actual_choice_reason():
    signal = matchup_signal()
    unchanged = deepcopy(vars(signal))
    analysis = build_forecast_analysis(signal, now=NOW)
    card = build_compact_analysis(signal, analysis, now=NOW)
    assert 'Spieler A' in card.summary
    assert 'längerfristig' in card.summary.casefold()
    assert 'Spieler B' in analysis.caution and '3/3' in analysis.caution
    assert vars(signal) == unchanged
    assert signal.probability == .5931


def test_weaker_long_term_side_is_not_given_an_invented_surface_advantage():
    signal = matchup_signal()
    weaker = replace(signal, selected_competitor='Spieler B', selection='Sieg Spieler B',
                     probability=.4069)
    analysis = build_forecast_analysis(weaker, now=NOW)
    assert 'Außenseiter' in analysis.basis
    assert 'längerfristig' in analysis.caution.casefold()
    assert 'Spieler A' in analysis.caution


def test_other_player_identity_cannot_borrow_matchup_ratings():
    signal = replace(matchup_signal(), competitor_a='Fremder Spieler',
                     selected_competitor='Fremder Spieler')
    analysis = build_forecast_analysis(signal, now=NOW)
    assert 'Vorteil' not in analysis.basis


def test_actual_same_call_surface_facts_keep_the_used_serve_comparison():
    from tennis.predict import predict_match
    from tennis.surface_evidence import build_surface_evidence
    from test_tennis_predict import _synthetic_state
    state = _synthetic_state()
    original = predict_match(state, 'Hero H.', 'Grinder G.', 'Hard', as_of=NOW)
    before = original.market_summary()
    evidence = build_surface_evidence(state, original)
    comparison = evidence.get('matchup')
    assert comparison is not None
    assert comparison['p_elo_a'] > .5
    assert comparison['p_serve_a'] > .5
    assert comparison['hold_a'] > comparison['hold_b']
    assert comparison['p_a_cal'] == original.p_a_cal
    assert original.market_summary() == before


def test_no_internal_ratings_are_exposed_in_customer_markup():
    signal = matchup_signal()
    card = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)
    markup = render_compact_analysis_html(card)
    assert '1871' not in markup and 'Elo' not in markup
    assert '2/3' in markup and '3/3' in markup


def test_better_last_five_is_a_counterargument_even_if_last_ten_are_worse():
    signal = matchup_signal()
    context = deepcopy(signal.context_evidence)
    entries = {}
    for side, name, outcomes in (('a', 'Spieler A', [True]+[False]*4+[True]*5),
                                  ('b', 'Spieler B', [True]*4+[False]*6)):
        rows = [dict(date=(NOW-timedelta(days=i+1)).date().isoformat(), won=won,
                     opponent='Gegner', score='2:0' if won else '0:2', opponent_rank=None,
                     date_kind='result_date') for i, won in enumerate(outcomes)]
        entries[side] = dict(player=name, surface_results=rows,
            surface=dict(matches=10, wins=sum(outcomes), **{'from': rows[-1]['date'], 'through': rows[0]['date']}))
    context['match_statistics'] = dict(schema='tennis-customer-results-v2', observed_at=NOW.isoformat(),
        surface='Clay', tour='ATP', players=entries)
    analysis = build_forecast_analysis(replace(signal, context_evidence=context), now=NOW)
    assert 'Spieler B' in analysis.caution and '4/5' in analysis.caution


def test_legacy_unvalidated_result_list_cannot_crash_recent_comparison():
    signal = matchup_signal()
    context = deepcopy(signal.context_evidence)
    for entry in context['match_statistics']['players'].values():
        entry['surface_results'] = [{}]*5
    analysis = build_forecast_analysis(replace(signal, context_evidence=context), now=NOW)
    assert '3/3' in analysis.caution


def test_rounding_band_does_not_reverse_nearly_even_serve_comparison():
    signal = matchup_signal()
    context = deepcopy(signal.context_evidence)
    context['surface_evidence']['matchup'] = dict(p_a_cal=.5931, p_elo_a=.60003,
        p_serve_a=.49993, p_serve_rounding_error=.00005/.3)
    analysis = build_forecast_analysis(replace(signal, context_evidence=context), now=NOW)
    assert 'Aufschlag' not in analysis.caution
