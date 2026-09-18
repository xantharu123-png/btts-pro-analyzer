from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from challenge_engine import MARKET_BY_KEY
from daily3_identity import event_guard
from daily3_selection import daily3_choices
from ev_signal_sources import ModelSignal, _automated_analysis_fields
from forecast_analysis import project_football_analysis

NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def football(fixture=1, key='RESULT_HOME', probability=.65, *, now=NOW):
    spec = MARKET_BY_KEY[key]
    row = dict(candidate_id=f'{fixture}:{key}', fixture_id=fixture,
        home_id=fixture*2, away_id=fixture*2+1, home_team=f'Heimteam {fixture}', away_team=f'Auswärtsteam {fixture}',
        market_key=key, probability=probability, model_scope='same_competition',
        scheduled_start=(now+timedelta(hours=3)).isoformat(), modeled_at=now.isoformat(),
        input_cutoff_at=(now-timedelta(minutes=1)).isoformat(), context={})
    evidence = project_football_analysis(row, model_basis={**row,
        'expected_home_goals': 1.8, 'expected_away_goals': .9, 'venue_samples': [12, 12], 'form_samples': [6, 6]})
    return ModelSignal(key=row['candidate_id'], label=f'Heimteam {fixture} vs Auswärtsteam {fixture}',
        probability=probability, probability_haircut=.08, evidence_stage='SHADOW', policy_version='test-v1',
        detail='Interne Angaben nicht veröffentlichen', sport='Fußball', event_label=f'Heimteam {fixture} vs Auswärtsteam {fixture}',
        market=spec.market, selection=spec.selection, market_key=key, candidate_id=row['candidate_id'],
        fixture_id=fixture, home_team=row['home_team'], away_team=row['away_team'], home_team_id=row['home_id'],
        away_team_id=row['away_id'], scheduled_start=row['scheduled_start'], modeled_at=row['modeled_at'],
        input_cutoff_at=row['input_cutoff_at'], model_scope=row['model_scope'], analysis_evidence=evidence)


def tennis(*, now=NOW, coverage=True):
    return ModelSignal(key='tennis1', label='Spieler A vs Spieler B', probability=.66, probability_haircut=.08,
        evidence_stage='SHADOW', policy_version='test-v1', detail='unused', scheduled_start=(now+timedelta(hours=2)).isoformat(),
        source='tennis_model', sport='Tennis', event_label='Spieler A vs Spieler B', market='Match Winner',
        selection='Sieg Spieler A', market_key='H2H', competitor_a='Spieler A', competitor_b='Spieler B', selected_competitor='Spieler A',
        fixture_source='api-tennis', provider_event_id='t1', competitor_a_id='a1', competitor_b_id='b1',
        modeled_at=now.isoformat(), input_cutoff_at=now.isoformat(), context_evidence={
            'observed_at': now.isoformat(), 'players': {'a': {'player': 'Spieler A'}, 'b': {'player': 'Spieler B'}},
            'model_inputs': {'surface': 'Clay', 'surface_in_model': True, 'serve_in_model': True,
                **({'stats_through': now.date().isoformat(), 'stats_through_kind': 'result_date',
                    'model_built_at': now.isoformat(), 'training_cutoff': now.isoformat()} if coverage else {})}})


def test_no_opposing_selections_and_full_pool_diversity_before_cut():
    pool = [football(i, 'HOME_OVER_0_5', .85) for i in range(1, 41)]
    pool += [football(41, 'BTTS_YES', .61), football(42, 'TOTAL_OVER_2_5', .6), football(41, 'BTTS_NO', .39)]
    choices = daily3_choices(pool, now=NOW)
    assert len(choices) == 3 and len({c.event_id for c in choices}) == 3
    assert len({c.family for c in choices}) == 3
    assert sum(c.signal.market_key == 'HOME_OVER_0_5' for c in choices) == 1


def test_prices_release_flags_and_pool_iteration_cannot_reorder_forecasts():
    pool = [football(1), football(2, 'BTTS_YES'), football(3, 'HOME_UNDER_1_5'), tennis()]
    changed = [replace(s, minimum_odds=999, evidence_stage='RELEASED', statistical_release_passed=True) for s in reversed(pool)]
    before = daily3_choices(pool, now=NOW)
    after = daily3_choices(changed, now=NOW)
    assert [c.signal.key for c in before] == [c.signal.key for c in after]
    assert [c.signal.probability for c in before] == [c.signal.probability for c in after]
    assert any(c.sport == 'tennis' for c in before)


@pytest.mark.parametrize('key', ['HOME_OVER_0_5', 'AWAY_OVER_0_5', 'HOME_UNDER_1_5', 'AWAY_UNDER_1_5'])
def test_no_categorical_simple_market_ban(key):
    assert daily3_choices([football(key=key)], now=NOW)[0].signal.market_key == key


def test_occupied_games_and_slots_are_never_offered_again():
    first = daily3_choices([football(1)], now=NOW)[0]
    choices = daily3_choices([football(1), football(1, 'RESULT_AWAY'), football(2), football(3)], now=NOW,
                            occupied_events=[first.event_id], used_slots=2)
    assert len(choices) == 1 and choices[0].event_id != first.event_id
    assert daily3_choices([football(2)], now=NOW, used_slots=3) == ()


def test_missing_stale_or_misbound_facts_are_not_relabelled_as_good_tips():
    base = football()
    old = football(now=NOW-timedelta(hours=3))
    changed = replace(base, probability=.9)
    for row in (replace(base, analysis_evidence=None), old, changed, replace(base, sport='Cricket')):
        assert daily3_choices([row], now=NOW) == ()


def test_tennis_facts_require_both_players_and_same_model_time():
    s = tennis()
    assert 'Sand' in daily3_choices([s], now=NOW)[0].basis
    assert daily3_choices([replace(s, competitor_a='Fremder Spieler')], now=NOW) == ()
    assert daily3_choices([replace(s, modeled_at=(NOW-timedelta(minutes=1)).isoformat())], now=NOW) == ()


def test_optional_persisted_model_fields_survive_shared_loader_projection():
    s = tennis()
    projected = _automated_analysis_fields(vars(s), now=NOW)
    for field in ('fixture_source', 'provider_event_id', 'competitor_a_id', 'competitor_b_id', 'context_evidence', 'model_version'):
        assert projected[field] == getattr(s, field)


def test_bare_high_probability_does_not_create_an_explanation_or_force_three():
    s = football(probability=.99)
    assert daily3_choices([replace(s, analysis_evidence=None)], now=NOW) == ()
    assert len(daily3_choices([s], now=NOW)) == 1


def test_same_model_result_does_not_pick_weaker_away_direction_by_alphabet():
    choices = daily3_choices([football(1, 'RESULT_AWAY', .21), football(1, 'RESULT_HOME', .46),
                             football(1, 'RESULT_DRAW', .33)], now=NOW)
    assert len(choices) == 1 and choices[0].signal.market_key == 'RESULT_HOME'


def test_persisted_weak_identity_cannot_reappear_after_native_id_upgrade():
    native = tennis()
    weak = replace(native, fixture_source=None, provider_event_id=None, competitor_a_id=None, competitor_b_id=None)
    first = daily3_choices([weak], now=NOW)[0]
    assert first.event_id != daily3_choices([native], now=NOW)[0].event_id
    assert daily3_choices([native], now=NOW, occupied_guards=[first.snapshot()['event_guard']], used_slots=1) == ()


def test_distinct_source_ids_with_exact_same_event_alias_use_only_one_slot():
    base = tennis()
    second = replace(base, key='tennis-second-source', fixture_source='different-fixture-source', provider_event_id='t2')
    assert len(daily3_choices([base, second], now=NOW)) == 1
    # This is not a fuzzy same-opponent ban: a different complete kickoff is a
    # separate event when it also has a distinct native event ID.
    later = replace(second, scheduled_start=(NOW+timedelta(hours=5)).isoformat())
    assert len(daily3_choices([base, later], now=NOW)) == 2
    assert event_guard(base)['identity'] != event_guard(second)['identity']
