"""Small display projection of already-loaded football results, never a model."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest

from test_forecast_analysis import _row, _basis, _signal
from forecast_analysis import project_football_analysis

NOW = datetime(2030, 1, 1, 9, tzinfo=timezone.utc)


def game(number, home=11, away=40, score=(2, 1), *, age=1):
    return {'fixture': {'id': number, 'date': (NOW-timedelta(days=age)).isoformat(),
                        'status': {'short': 'FT'}},
            'teams': {'home': {'id': home, 'name': 'Alpha' if home == 11 else 'Opponent'},
                      'away': {'id': away, 'name': 'Beta' if away == 12 else 'Opponent'}},
            'goals': {'home': score[0], 'away': score[1]},
            'league': {'id': 9, 'name': 'League'}, 'bookmaker_odds': 99}


def builder(history, row=None):
    module = import_module('football_customer_facts')
    row = row or _row()
    fixture = {'fixture': {'id': row['fixture_id'], 'date': row['scheduled_start']},
               'teams': {'home': {'id': row['home_id'], 'name': row['home_team']},
                         'away': {'id': row['away_id'], 'name': row['away_team']}}}
    return module.build_football_recent_results(fixture, history, as_of=NOW,
                                               model_scope=row['model_scope'])


def customer(history, *, key='RESULT_HOME'):
    row = _row(key)
    basis = _basis(row)
    basis['customer_recent_results'] = builder(history, row)
    row['analysis_evidence'] = project_football_analysis(row, model_basis=basis)
    return import_module('football_customer_facts').football_customer_analysis(
        _signal(row), now=NOW+timedelta(hours=3))


def test_real_last_five_and_ten_include_away_orientation_and_opponents():
    history = [game(i+1, score=(2, 1), age=i+1) for i in range(11)]
    history += [game(100+i, home=40, away=12, score=(0, 2), age=i+1) for i in range(10)]
    original = deepcopy(history)
    result = customer(history)
    facts = dict(result.facts)
    assert facts['Form Alpha'] == '5S · 0U · 0N (5) / 10S · 0U · 0N (10)'
    assert facts['Form Beta'] == '5S · 0U · 0N (5) / 10S · 0U · 0N (10)'
    assert any('Opponent' in detail and '2:0' in detail for detail in result.details)
    assert 'nicht hinterlegt' not in ' '.join(result.details)
    assert history == original
    assert 'bookmaker_odds' not in repr(builder(history))


def test_only_real_sample_never_claims_ten_from_three_and_no_future_results():
    history = [game(i+1, age=i+1) for i in range(3)]
    history += [game(70, age=-1), game(71, age=400)]
    result = customer(history)
    assert dict(result.facts)['Form Alpha'] == '3S · 0U · 0N (3 erfasst)'
    assert 'Form Beta' not in dict(result.facts)
    assert '(10)' not in ' '.join(v for _, v in result.facts)


def test_conflicting_results_and_unfinished_games_are_not_presented_as_wins():
    one = game(1)
    conflicting = game(1, score=(0, 5))
    pending = game(2)
    pending['fixture']['status']['short'] = 'NS'
    history = [one, deepcopy(one), conflicting, pending, game(3, score=(1, 1))]
    result = customer(history)
    assert dict(result.facts)['Form Alpha'] == '0S · 1U · 0N (1 erfasst)'


@pytest.mark.parametrize('mutation', ['team', 'clock', 'score', 'source'])
def test_malformed_or_misbound_recent_projection_cannot_add_form_claims(mutation):
    row = _row()
    raw = builder([game(1)])
    if mutation == 'team':
        raw['home_id'] = 99
    elif mutation == 'clock':
        raw['as_of'] = '2030-01-01T10:01:00+00:00'
    elif mutation == 'score':
        raw['home'][0]['scored'] = True
    else:
        raw['home'][0]['opponent_rank'] = 1
    row['analysis_evidence'] = project_football_analysis(row, model_basis={**_basis(row), 'customer_recent_results': raw})
    result = import_module('football_customer_facts').football_customer_analysis(_signal(row), now=NOW+timedelta(hours=3))
    assert 'Form Alpha' not in dict(result.facts)


def test_opponents_better_recent_results_are_counterargument_not_claimed_weaker():
    history = [game(i+1, score=(2, 1), age=i+1) for i in range(5)]
    history += [game(100+i, home=40, away=12, score=(2, 1), age=i+1) for i in range(5)]
    result = customer(history, key='RESULT_AWAY')
    assert 'Alpha gewann 5 der letzten 5' in result.counterargument
    assert 'Beta gewann 0' in result.counterargument
    assert 'stärkere Gegner' not in result.summary


def test_worker_persists_recent_results_once_projected_without_touching_the_candidate():
    from test_wettfinder_automation import _football_snapshot
    from wettfinder_automation import _football_state_from_snapshot
    now = NOW+timedelta(hours=1)
    snapshot = _football_snapshot(now)
    candidate = snapshot['shortlist'][0]
    row = {'fixture_id': candidate.fixture_id, 'home_id': candidate.home_team_id,
           'away_id': candidate.away_team_id, 'home_team': candidate.home_team,
           'away_team': candidate.away_team, 'scheduled_start': candidate.kickoff,
           'model_scope': candidate.model_scope}
    history = [game(i+20, home=10, away=40, age=i+1) for i in range(10)]
    snapshot['football_recent_results'] = {str(candidate.fixture_id): builder(history, row)}
    before = deepcopy(vars(candidate))
    state = _football_state_from_snapshot(snapshot, attempted_at=now, search_date=now.date())
    recent = state['candidates'][0]['analysis_evidence']['basis']['customer_recent_results']
    assert len(recent['home']) == 10
    assert recent['home'][0]['opponent'] == 'Opponent'
    assert vars(candidate) == before


def test_context_only_refresh_keeps_old_results_and_cannot_backfill_a_new_result():
    from test_wettfinder_automation import _football_snapshot
    from wettfinder_automation import _football_state_from_snapshot, _merge_context_refresh
    now = NOW+timedelta(hours=1)
    snapshot = _football_snapshot(now)
    candidate = snapshot['shortlist'][0]
    row = {'fixture_id': candidate.fixture_id, 'home_id': candidate.home_team_id,
           'away_id': candidate.away_team_id, 'home_team': candidate.home_team,
           'away_team': candidate.away_team, 'scheduled_start': candidate.kickoff,
           'model_scope': candidate.model_scope}
    old_recent = builder([game(20, home=10, away=40)], row)
    snapshot['football_recent_results'] = {'1': old_recent}
    state = _football_state_from_snapshot(snapshot, attempted_at=now, search_date=now.date())
    old = deepcopy(state)
    refreshed = _merge_context_refresh(state, {'candidates': [candidate], 'errors': [],
        'football_recent_results': {'1': builder([game(21, home=10, away=40, score=(9, 0))], row)}},
        fixture_ids=[1], checked_at=now+timedelta(minutes=30))
    assert refreshed['candidates'][0]['analysis_evidence']['basis']['customer_recent_results'] == old_recent
    assert state == old


def test_nested_missing_provider_fields_do_not_break_a_completed_model():
    history = [None, {'fixture': None}, {'fixture': {'id': 20}, 'teams': None},
               {'fixture': {'id': 21}, 'goals': None}, game(22, score=(1, 1))]
    recent = builder(history)
    assert len(recent['home']) == 1


def test_a_reopened_or_conflicting_native_match_is_not_still_reported_as_completed():
    played = game(20)
    reopened = deepcopy(played)
    reopened['fixture']['status']['short'] = 'NS'
    recent = builder([played, reopened, game(21, score=(1, 1))])
    assert [r['fixture_id'] for r in recent['home']] == [21]


def test_a_loaded_future_reschedule_invalidates_the_old_completed_result():
    played = game(20)
    rescheduled = deepcopy(played)
    rescheduled['fixture']['date'] = (NOW+timedelta(days=1)).isoformat()
    rescheduled['fixture']['status']['short'] = 'NS'
    for history in ([played, rescheduled], [rescheduled, played]):
        assert builder(history)['home'] == []


@pytest.mark.parametrize('field, value', [('scored', 2), ('opponent_id', 99),
                                        ('venue', 'home'), ('competition', 'Wrong League')])
def test_shared_result_must_be_the_same_match_from_opposite_team_perspectives(field, value):
    from football_customer_facts import validated_football_recent_results
    raw = builder([game(20, home=11, away=12)])
    raw['away'][0][field] = value
    assert validated_football_recent_results(raw, identity={
        **_row(), 'input_cutoff_at': NOW.isoformat()}) is None


def test_consistent_shared_result_is_accepted_without_mutating_the_source():
    from football_customer_facts import validated_football_recent_results
    raw = builder([game(20, home=11, away=12)])
    before = deepcopy(raw)
    checked = validated_football_recent_results(raw, identity={
        **_row(), 'input_cutoff_at': NOW.isoformat()})
    assert checked == before
    assert checked is not raw


def test_each_team_form_click_shows_only_its_own_actual_opponents():
    from forecast_analysis import build_forecast_analysis
    from forecast_compact import build_compact_analysis
    row = _row()
    recent = builder([game(20), game(30, home=50, away=12, score=(3, 0))])
    row['analysis_evidence'] = project_football_analysis(row, model_basis={
        **_basis(row), 'customer_recent_results': recent})
    signal = _signal(row)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW+timedelta(hours=3)),
                                     now=NOW+timedelta(hours=3))
    details = {f.label: f.details for f in compact.facts}
    assert any('Alpha ·' in line for line in details['Form Alpha'])
    assert not any('Beta ·' in line for line in details['Form Alpha'])
    assert any('Beta ·' in line for line in details['Form Beta'])
    assert not any('Alpha ·' in line for line in details['Form Beta'])


def test_identically_named_native_teams_keep_distinct_form_details():
    from forecast_analysis import build_forecast_analysis
    from forecast_compact import build_compact_analysis
    row = _row()
    row.update(home_team='United', away_team='United')
    recent = builder([game(20), game(30, home=50, away=12, score=(3, 0))], row)
    row['analysis_evidence'] = project_football_analysis(row, model_basis={
        **_basis(row), 'customer_recent_results': recent})
    signal = _signal(row)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW+timedelta(hours=3)),
                                     now=NOW+timedelta(hours=3))
    facts = {f.label: f for f in compact.facts}
    assert facts['Form United (Heim)'].value == '1S · 0U · 0N (1 erfasst)'
    assert '2:1' in ' '.join(facts['Form United (Heim)'].details)
    assert '0:3' not in ' '.join(facts['Form United (Heim)'].details)
    assert facts['Form United (Gast)'].value == '0S · 0U · 1N (1 erfasst)'
    assert '0:3' in ' '.join(facts['Form United (Gast)'].details)


def test_manual_card_uses_same_bound_stats_and_counterargument_as_automatic_card():
    from test_wettfinder_automation import _challenge_candidate
    candidate = _challenge_candidate(NOW+timedelta(hours=6))
    candidate.context = {'passed': True, 'forecast_passed': True}
    native = {'fixture_id': 1, 'home_id': 10, 'away_id': 11, 'home_team': 'FC Alpha',
              'away_team': 'FC Beta', 'scheduled_start': candidate.kickoff, 'model_scope': candidate.model_scope}
    recent = builder([game(i+20, home=10, away=40, age=i+1) for i in range(10)], native)
    result = import_module('football_customer_facts').manual_football_customer_analysis(
        candidate, recent_results=recent, model_clock=NOW+timedelta(minutes=1), now=NOW+timedelta(hours=1))
    assert dict(result.facts)['Form FC Alpha'] == '5S · 0U · 0N (5) / 10S · 0U · 0N (10)'
    assert 'beide Teams' in result.summary


@pytest.mark.parametrize('missing', ['home_team_id', 'away_team_id', 'kickoff'])
def test_manual_optional_analysis_preserves_legacy_cards_without_identity(missing):
    from types import SimpleNamespace
    from test_wettfinder_automation import _challenge_candidate
    raw = deepcopy(vars(_challenge_candidate(NOW+timedelta(hours=6))))
    raw.pop(missing)
    candidate = SimpleNamespace(**raw)
    before = deepcopy(vars(candidate))
    assert import_module('football_customer_facts').manual_football_customer_analysis(
        candidate, recent_results=None, model_clock=NOW, now=NOW+timedelta(hours=1)) is None
    assert vars(candidate) == before
