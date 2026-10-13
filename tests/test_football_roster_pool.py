"""Pooling mechanics only: no empirical injury-effect qualification."""
from copy import deepcopy

import pytest

from context_models.football_joint_context import feature_group
from context_models.football_roster_pool import pooled_roster_features
from context_models.contracts import ContextContractError


def roster(ids=(1, 2), values=(-.6, .6)):
    keys = [f'home.venue_attack.goals.api-football:player:{player}' for player in ids]
    return dict(version='football-roster-components-v2', event_key='api-football:fixture:1',
        cutoff='2026-09-01T00:00:00.000000Z', values=dict(zip(keys, values)),
        states={key: 'available' for key in keys}, refs={key: [str(i+1)*64] for i, key in enumerate(keys)},
        coverage=dict(version='football-roster-v1', case='reported_players'), reference_hash='a'*64)


def test_disjoint_team_rosters_have_same_features_and_replacement_does_not_cancel():
    first, second = roster(), roster((111, 222))
    original = deepcopy(first)
    a, b = pooled_roster_features(first), pooled_roster_features(second)
    assert first == original
    assert a == b
    assert len(a['values']) == 32
    prefix = 'roster.home.venue_attack.goals.'
    assert a['values'][prefix+'loss_exposure_v1'] == .6
    assert a['values'][prefix+'gain_exposure_v1'] == .6
    assert a['refs'][prefix+'loss_exposure_v1'] == ['1'*64, '2'*64]
    assert a['values']['roster.away.venue_attack.goals.loss_exposure_v1'] is None


@pytest.mark.parametrize('state', ['missing', 'stale', 'conflicting', 'not_applicable'])
def test_one_unknown_player_cannot_be_dropped_or_imputed_as_healthy(state):
    block = roster()
    key = next(iter(block['values']))
    block['states'][key], block['values'][key], block['refs'][key] = state, None, []
    result = pooled_roster_features(block)
    for suffix in ('loss_exposure_v1', 'gain_exposure_v1'):
        name = 'roster.home.venue_attack.goals.'+suffix
        assert result['states'][name] == 'missing'
        assert result['values'][name] is None and not result['refs'][name]


def test_numeric_value_without_source_is_not_complete_and_real_zero_is_available():
    block = roster(values=(0., 0.))
    result = pooled_roster_features(block)
    name = 'roster.home.venue_attack.goals.loss_exposure_v1'
    assert result['values'][name] == 0. and result['states'][name] == 'available'
    block['refs'][next(iter(block['values']))] = []
    assert pooled_roster_features(block)['values'][name] is None


def test_pooling_does_not_convert_diagnostics_into_players_or_couple_metrics():
    block = roster()
    for field, value in (('values', None), ('states', 'missing'), ('refs', [])):
        block[field]['home.venue_defense.goals.reference'] = value
        block[field]['roster_reference'] = value
    result = pooled_roster_features(block)
    assert result['values']['roster.home.venue_attack.xg.loss_exposure_v1'] is None
    assert result['values']['roster.home.venue_defense.goals.loss_exposure_v1'] is None
    assert result['values']['roster.home.venue_attack.goals.loss_exposure_v1'] == .6


def test_only_closed_new_exposure_names_are_admitted():
    assert feature_group('roster.home.venue_attack.goals.loss_exposure_v1') == 'roster'
    assert feature_group('roster.away.form_defense.xg.gain_exposure_v1') == 'roster'
    with pytest.raises(ContextContractError):
        feature_group('roster.home.venue_attack.goals.injury_effect')


def test_real_native_joint_case_contains_the_exact_source_complete_pool(native_case):
    path, case, config = native_case
    from context_models.football import football_features
    from datetime import datetime
    payload = case['case']['payload']
    # Keep the existing v1 vector byte-compatible; v2 is an explicit new case,
    # not an in-place rewrite of any original, forecast or old training record.
    from context_models.football_joint_context import POOLED_FEATURE_VERSION, feature_coverage
    from context_models.football_training import build_joint_training_case
    name = 'roster.home.venue_attack.goals.loss_exposure_v1'
    assert name not in payload['features']['values']
    config = {**deepcopy(config), 'feature_version': POOLED_FEATURE_VERSION,
        'coverage': feature_coverage(POOLED_FEATURE_VERSION), 'feature_names': [name],
        'groups': {'roster': [name]}}
    as_of = datetime.fromisoformat(payload['base']['cutoff'])
    from datetime import timedelta
    before = path.read_bytes()
    new_case = build_joint_training_case(path, binding_ref=payload['replay_ref'],
        outcome_ref=payload['outcome_ref'], identity_ref=payload['event_identity_hash'],
        config=config, as_of=as_of+timedelta(hours=6))
    assert path.read_bytes() == before
    payload = new_case['case']['payload']
    raw = football_features(payload['event'], case['observations'], payload['base'],
        cutoff=datetime.fromisoformat(payload['base']['cutoff']))
    pool = pooled_roster_features(raw)
    for field in pool:
        for coordinate, value in pool[field].items():
            assert payload['features'][field][coordinate] == value
    assert payload['features']['states'][name] == 'available'
    assert payload['features']['refs'][name]
    from context_models.football_joint_context import apply_joint_effect, COVERAGE, FEATURE_VERSION
    head = dict(link='log_joint_tilt', scale=[1.], coef=[0.], alpha=1., n_rows=3)
    effect = dict(schema=1, heads={'home': head, 'away': head},
        training_end='2026-08-01T00:00:00.000000Z', training_refs_hash='b'*64,
        **{key: config[key] for key in ('sport', 'family', 'feature_version', 'feature_names',
            'preprocessing_artifacts', 'joint_calibration', 'population', 'coverage', 'model_variant')})
    unchanged = apply_joint_effect(payload['base'], payload['features'], effect, event=payload['event'])
    assert unchanged['markets'] == payload['base']['markets']
    wrong = {**deepcopy(payload['features']), 'version': FEATURE_VERSION, 'coverage': dict(COVERAGE)}
    with pytest.raises(ContextContractError):
        apply_joint_effect(payload['base'], wrong, effect, event=payload['event'])


def test_v1_contract_cannot_claim_new_pooled_values(native_case):
    from context_models.training_contracts import validate_family_config
    _, _, config = native_case
    name = 'roster.home.venue_attack.goals.loss_exposure_v1'
    config = {**deepcopy(config), 'feature_names': [name], 'groups': {'roster': [name]}}
    with pytest.raises(ContextContractError, match='separate v2'):
        validate_family_config(config)


# Reuse the existing actual B1 -> A1 -> frozen-original owning fixture.
from test_football_joint_training import native_case
