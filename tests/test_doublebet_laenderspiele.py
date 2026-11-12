"""Doublebet: A-Länderspiele ohne Verletzungsdaten (Owner 12.11.2026, „Ja, zulassen“, Policy v16).

The provider does not cover injuries for senior national teams. Only the Doublebet accepts
that explicit "not covered" fact for the pooled national model; club games, a failed
injury fetch and every other context veto keep excluding the row, and every other
surface keeps the full context requirement.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from challenge_engine import MARKET_BY_KEY
from daily3_selection import POLICY_VERSION, daily3_choices
from ev_signal_sources import ModelSignal
from forecast_analysis import (football_context_highlight_reason, forecast_highlight_reason,
                               project_football_analysis, read_football_analysis)
from highlight_fixtures import football_checks
from test_daily3_selection import NOW, _admitted

NOT_COVERED = {'status': 'unavailable', 'availability': 'not_covered', 'coverage_available': False,
               'reason': 'Verletzungsdaten werden für diese Liga nicht abgedeckt'}
PROVIDER_DOWN = {'status': 'unavailable', 'availability': 'provider_unavailable', 'coverage_available': True,
                 'reason': 'Verletzungsdaten konnten nicht verifiziert werden'}


def _signal(*, scope='senior_national_pooled', injuries=NOT_COVERED, fixture=7, start_hours=3,
            source='automated_wettfinder_forecast', context_change=None):
    key = 'RESULT_HOME'
    spec = MARKET_BY_KEY[key]
    context = football_checks(NOW)
    if injuries is None:
        context.pop('injuries')
    else:
        context['injuries'] = dict(injuries)
    if context_change:
        context_change(context)
    row = dict(candidate_id=f'{fixture}:{key}', fixture_id=fixture, home_id=fixture*2, away_id=fixture*2+1,
               home_team=f'Land {fixture}', away_team=f'Gegner {fixture}', market_key=key, probability=.55,
               model_scope=scope, scheduled_start=(NOW+timedelta(hours=start_hours)).isoformat(),
               modeled_at=NOW.isoformat(), input_cutoff_at=(NOW-timedelta(minutes=1)).isoformat(), context=context)
    basis = {**row, 'expected_home_goals': 1.6, 'expected_away_goals': 1.0, 'form_samples': [6, 6]}
    basis.update({'national_samples': [12, 12]} if scope == 'senior_national_pooled' else {'venue_samples': [12, 12]})
    evidence = project_football_analysis(row, model_basis=basis)
    signal = ModelSignal(key=row['candidate_id'], label=f'Land {fixture} vs Gegner {fixture}', probability=.55,
        probability_haircut=.08, evidence_stage='SHADOW', policy_version='test-v1', detail='intern', sport='Fußball',
        event_label=f'Land {fixture} vs Gegner {fixture}', market=spec.market, selection=spec.selection,
        market_key=key, candidate_id=row['candidate_id'], fixture_id=fixture, home_team=row['home_team'],
        away_team=row['away_team'], home_team_id=row['home_id'], away_team_id=row['away_id'],
        scheduled_start=row['scheduled_start'], modeled_at=row['modeled_at'], input_cutoff_at=row['input_cutoff_at'],
        model_scope=scope, analysis_evidence=evidence, model_version='test-model-v1',
        price_checked_at=NOW.isoformat(), source=source)
    return _admitted(signal)


def test_national_match_without_injury_coverage_enters_doublebet():
    signal = _signal()
    choice, = daily3_choices([signal], now=NOW)
    assert choice.signal.key == signal.key and choice.sport == 'football'
    # The card says honestly that injuries were not available for this match.
    assert 'Verletzungsdaten für dieses Spiel nicht abgedeckt' in choice.caution
    assert choice.snapshot()['policy_version'] == POLICY_VERSION == 'doublebet-odds-around-2-most-probable-v16'


def test_club_match_without_injury_coverage_stays_out():
    club = _signal(scope='same_competition')
    assert daily3_choices([club], now=NOW) == ()
    # The scope is bound to the evidence identity; relabelling a club row does not admit it.
    assert daily3_choices([replace(club, model_scope='senior_national_pooled')], now=NOW) == ()


@pytest.mark.parametrize('injuries', [PROVIDER_DOWN, None])
def test_failed_or_missing_injury_check_still_excludes_a_national_match(injuries):
    assert daily3_choices([_signal(injuries=injuries)], now=NOW) == ()


@pytest.mark.parametrize('change', [
    lambda c: c['weather'].update(status='blocked'),
    lambda c: c['h2h'].update(status='blocked'),
    lambda c: c.update(lineups={'status': 'blocked', 'checked_at': NOW.isoformat()}),
    lambda c: c['weather'].update(checked_at=(NOW-timedelta(hours=25)).isoformat()),
    lambda c: c.pop('h2h'),
])
def test_other_context_vetoes_still_exclude_a_national_match(change):
    assert daily3_choices([_signal(context_change=change)], now=NOW) == ()


def test_conflicting_context_still_excludes_a_national_match():
    signal = _signal()
    evidence = deepcopy(signal.analysis_evidence)
    evidence['context']['conflicting'] = True
    assert daily3_choices([replace(signal, analysis_evidence=evidence)], now=NOW) == ()


def test_other_surfaces_keep_the_full_context_requirement():
    signal = _signal()
    context = read_football_analysis(vars(signal), now=NOW)['context']
    assert football_context_highlight_reason(context, now=NOW) == 'Spielinformationen nicht aktuell belegt'
    assert forecast_highlight_reason(signal, now=NOW) == 'Spielinformationen nicht aktuell belegt'


def test_national_match_with_observed_injuries_is_unchanged():
    signal = _signal(injuries=football_checks(NOW)['injuries'])
    choice, = daily3_choices([signal], now=NOW)
    assert '0/0 Ausfälle gemeldet' in choice.caution
