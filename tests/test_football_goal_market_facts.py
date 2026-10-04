"""Real market-specific form, never odds, fitted chance or invented matches."""
from copy import deepcopy
from datetime import timedelta

import pytest

from challenge_engine import MARKET_BY_KEY
from football_customer_facts import recent_football_goal_market_facts, football_customer_analysis
from forecast_analysis import build_forecast_analysis, project_football_analysis
from forecast_compact import build_compact_analysis, render_compact_analysis_html
from test_football_recent_results import NOW, builder, game
from test_forecast_analysis import _row, _basis, _signal


def histories():
    # Away-team scored figures are the actual Germany-like last ten. A 7:1
    # sixth game must stay visible in the ten-game count, not vanish behind 5/5.
    scored = [2, 0, 1, 1, 2, 7, 2, 4, 2, 4]
    conceded = [2, 0, 1, 1, 2, 0, 1, 0, 2, 3]
    return ([game(100+i, home=40, away=12, score=(1, n), age=i+1)
             for i, n in enumerate(scored)]
            + [game(200+i, home=11, away=40, score=(1, n), age=i+1)
               for i, n in enumerate(conceded)])


def facts(key, history=None):
    recent = builder(histories() if history is None else history)
    return recent_football_goal_market_facts(recent, MARKET_BY_KEY[key], home='Alpha', away='Beta')


def test_under_market_uses_scored_for_selected_side_and_conceded_for_opponent():
    result, details = facts('AWAY_UNDER_2_5')
    assert dict(result) == {'Beta · höchstens 2 Tore': '5/5 zuletzt · 7/10',
                            'Alpha · Gegentore: höchstens 2 Tore': '5/5 zuletzt · 9/10'}
    assert '7:1' in ' '.join(dict(details)['Beta · höchstens 2 Tore'])
    assert '1:7' not in ' '.join(dict(details)['Beta · höchstens 2 Tore'])
    assert 'Beobachtete Ergebnisse' in ' '.join(dict(details)['Beta · höchstens 2 Tore'])


def test_home_market_reverses_team_roles_not_scores():
    result, _ = facts('HOME_UNDER_2_5')
    assert dict(result) == {'Alpha · höchstens 2 Tore': '5/5 zuletzt · 10/10',
                            'Beta · Gegentore: höchstens 2 Tore': '5/5 zuletzt · 10/10'}


@pytest.mark.parametrize('key,expected', [
    ('AWAY_OVER_2_5', '0/5 zuletzt · 3/10'),
    ('AWAY_RANGE_1_3', '4/5 zuletzt · 6/10'),
    ('AWAY_RANGE_2_4', '2/5 zuletzt · 6/10'),
])
def test_opposing_and_range_markets_count_the_exact_condition(key, expected):
    result, _ = facts(key)
    assert result[0][1] == expected


def test_total_market_uses_each_teams_actual_match_total_not_both_teams_own_goals():
    result, _ = facts('TOTAL_OVER_2_5')
    assert result[0][1] == '2/5 zuletzt · 4/10'
    assert result[1][1] == '2/5 zuletzt · 7/10'


@pytest.mark.parametrize('key,expected', [('BTTS_YES', '4/5 zuletzt · 7/10'),
                                         ('BTTS_NO', '1/5 zuletzt · 3/10')])
def test_btts_counts_both_goals_from_the_same_result(key, expected):
    result, _ = facts(key)
    assert result[0][1] == expected


def test_short_sample_not_called_five_or_ten_and_missing_side_not_zero():
    result, _ = facts('HOME_OVER_0_5', [game(1), game(2), game(3, score=(0, 1))])
    assert len(result) == 1
    assert result[0][1] == '2/3 erfasst'
    assert '5' not in result[0][1] and '10' not in result[0][1]


@pytest.mark.parametrize('key', ['RESULT_HOME', 'DC_X2', 'CORNERS_OVER_8_5', 'HOME_CORNERS_OVER_4_5'])
def test_scores_never_become_unsupported_or_corner_market_facts(key):
    spec = MARKET_BY_KEY[key]
    assert recent_football_goal_market_facts(builder(histories()), spec, home='Alpha', away='Beta') == ((), ())


def test_exact_bound_card_keeps_model_probability_and_adds_short_observed_facts():
    row = _row('AWAY_UNDER_2_5', .72)
    recent = builder(histories(), row)
    row['analysis_evidence'] = project_football_analysis(row, model_basis={
        **_basis(row), 'customer_recent_results': recent})
    signal = _signal(row)
    before = deepcopy(vars(signal))
    now = NOW+timedelta(hours=3)
    customer = football_customer_analysis(signal, now=now)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=now), now=now)
    assert dict(customer.facts)['Beta · höchstens 2 Tore'] == '5/5 zuletzt · 7/10'
    assert compact.summary == 'Beta · höchstens 2 Tore: 5/5 zuletzt · 7/10'
    assert not any(f.label == 'Beta · höchstens 2 Tore' for f in compact.facts)
    assert next(f for f in compact.facts if f.label == 'Torprognose').value == 'Beta: 1,13 erwartete Tore'
    assert signal.probability == .72
    assert vars(signal) == before


@pytest.mark.parametrize('mutate', ['future', 'wrong_side'])
def test_unbound_or_future_recent_results_do_not_add_goal_claims(mutate):
    row = _row('AWAY_UNDER_2_5', .72)
    recent = builder(histories(), row)
    if mutate == 'future':
        recent['as_of'] = '2030-01-02T00:00:00+00:00'
    else:
        recent['away_id'] = 99
    row['analysis_evidence'] = project_football_analysis(row, model_basis={
        **_basis(row), 'customer_recent_results': recent})
    result = football_customer_analysis(_signal(row), now=NOW+timedelta(hours=3))
    assert not any('höchstens' in label for label, _ in result.facts)


def test_national_basis_is_not_mislabeled_as_venue_only_games():
    row = _row('AWAY_UNDER_2_5', .72)
    row['model_scope'] = 'senior_national_pooled'
    row['analysis_evidence'] = project_football_analysis(row, model_basis={
        **_basis(row), 'national_samples': [12, 12], 'venue_samples': [6, 6]})
    signal = _signal(row)
    now = NOW+timedelta(hours=3)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=now), now=now)
    assert next(f for f in compact.facts if f.label == 'Basis').value == '12 / 12 A-Länderspiele'
    assert '12 Heim' not in render_compact_analysis_html(compact)
