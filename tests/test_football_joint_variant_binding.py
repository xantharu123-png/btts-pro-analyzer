"""Offline law identities only; no predictive approval or active-slot mutation."""
from copy import deepcopy
from datetime import datetime, timezone

import numpy as np
import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, canonical_timestamp, digest, validate_effect_artifact
from context_models.football_joint_context import apply_joint_effect, fit_heads
from context_models.football_joint_effect import fit_joint_offset, joint_offset_delta
from context_models.football_training import joint_base
from context_models.training_contracts import validate_family_config
from football_original import FootballOriginal
from model_artifacts import canonical_bytes
from test_football_base_provenance import target, history
from test_football_original_capture import calibration

OLD_BASE = 'football-goals-captured-joint-v1'
NEW_BASE = 'football-goals-captured-joint-v2'
OLD_EFFECT = 'football-joint-log-tilt-v1'
NEW_EFFECT = 'football-joint-log-tilt-v2'
OLD_LAW = 'football-joint-settlement-projection-v1'
NEW_LAW = 'football-joint-settlement-projection-v2'
AT = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)
NAME = 'schedule.gap_hours_home'


def _config(variant):
    return dict(schema=1, sport='football', family='football:goals:90min',
        feature_version='football-native-context-v1', feature_names=[NAME],
        population=dict(sport='football', competitions=['39'], formats=['90min'], tours=[None], surfaces=[None], indoor=[None]),
        coverage=dict(version='football-native-context-v1.coverage', case='source-bound'),
        model_variant=variant, base_versions=[OLD_BASE if variant == OLD_EFFECT else NEW_BASE],
        head_links={'home': 'log_joint_tilt', 'away': 'log_joint_tilt'}, reference_version='football-context-reference-v2',
        preprocessing_artifacts={}, groups={'schedule': [NAME]}, joint_calibration={'kind': 'identity'},
        target_markets=['RESULT_AWAY', 'RESULT_DRAW', 'RESULT_HOME'], outcome_contract='football-regulation-ft-v1',
        train_end='2026-08-01T00:00:00.000000Z', tune_end='2026-08-02T00:00:00.000000Z',
        alpha_grid=[.01, .1, 1., 10., 100.])


def _capture(monkeypatch, law):
    monkeypatch.setattr('football_original._capture_now', lambda: AT)
    originals = []
    engine.fixture_market_probabilities(target(), history(), calibration(),
        original_capture=originals.append, _joint_law_version=law)
    original = originals[0]
    event = dict(event_key='api-football:football:10001', sport='football', competition='39', format='90min',
                 home_id='api-football:team:1', away_id='api-football:team:2',
                 scheduled_start=canonical_timestamp(datetime(2026, 8, 6, 12, tzinfo=timezone.utc)),
                 schedule_revision='captured-native', status='scheduled')
    binding = dict(native_event=event, decision_at=canonical_timestamp(AT))
    return original, binding


def _inputs(monkeypatch, law, variant):
    original, binding = _capture(monkeypatch, law)
    base = joint_base(original, binding)
    config = _config(variant)
    features = dict(version=config['feature_version'], event_key=base['event_key'], cutoff=base['cutoff'],
        values={NAME: 1.}, states={NAME: 'available'}, refs={NAME: ['a'*64]}, coverage=config['coverage'],
        reference_hash=digest(dict(version='football-context-reference-v2', base_hash=digest(base),
                                   event_hash=digest(binding['native_event']), preprocessing=[])))
    head = dict(link='log_joint_tilt', scale=[1.], coef=[0.], alpha=1., n_rows=3)
    effect = dict(schema=1, heads={'home': deepcopy(head), 'away': deepcopy(head)},
        training_end=config['train_end'], training_refs_hash='b'*64,
        **{key: config[key] for key in ('sport', 'family', 'feature_version', 'feature_names',
            'preprocessing_artifacts', 'joint_calibration', 'population', 'coverage', 'model_variant')})
    return original, base, features, effect, binding['native_event']


@pytest.mark.parametrize('law,variant,want_base,want_comparison', [
    (OLD_LAW, OLD_EFFECT, OLD_BASE, 'football-goals-context-joint-v1'),
    (NEW_LAW, NEW_EFFECT, NEW_BASE, 'football-goals-context-joint-v2'),
])
def test_known_capture_law_owns_exact_base_effect_and_comparison_versions(monkeypatch, law, variant, want_base, want_comparison):
    original, base, features, effect, event = _inputs(monkeypatch, law, variant)
    before = original._bytes
    assert base['version'] == want_base
    comparison = apply_joint_effect(base, features, effect, event=event)
    assert comparison['version'] == want_comparison
    assert comparison['params'] == base['params'] and comparison['markets'] == base['markets']
    assert original._bytes == before


def test_old_effect_cannot_consume_new_capture_before_any_delta(monkeypatch):
    _original, base, features, effect, event = _inputs(monkeypatch, NEW_LAW, OLD_EFFECT)
    before = canonical_bytes(base)
    with pytest.raises(ContextContractError, match='law|variant|version'):
        apply_joint_effect(base, features, effect, event=event)
    assert canonical_bytes(base) == before


@pytest.mark.parametrize('change', ['prediction', 'recipe', 'unknown-law'])
def test_joint_base_cannot_relabel_a_forged_known_capture(monkeypatch, change):
    original, binding = _capture(monkeypatch, OLD_LAW)
    packet = original.to_dict()
    if change == 'prediction':
        packet['prediction_version'] = 'challenge-engine:coherent-joint-calibration-v15'
    elif change == 'recipe':
        packet['distribution_capture']['recipe']['prior_anchor'] = 99
    else:
        packet['distribution_capture']['law_version'] = 'unknown-law'
    with pytest.raises(ContextContractError):
        joint_base(FootballOriginal(canonical_bytes(packet)), binding)


@pytest.mark.parametrize('variant', [OLD_EFFECT, NEW_EFFECT])
def test_config_accepts_only_its_single_matching_base_variant(variant):
    config = _config(variant)
    assert validate_family_config(config) == config
    for bases in ([NEW_BASE if variant == OLD_EFFECT else OLD_BASE], [OLD_BASE, NEW_BASE]):
        with pytest.raises(ContextContractError):
            validate_family_config(dict(config, base_versions=bases))


def _fit_case(base_version, feature, goals):
    return dict(case={'payload': dict(base=dict(version=base_version,
        params={'joint_cells': [[0, 0, .45], [0, 1, .05], [1, 0, .05], [1, 1, .45]]}),
        features={'values': {NAME: feature}}, outcome_ref='outcome')},
        observations=({'digest': 'outcome', 'payload': {'result': {'goals_home': goals, 'goals_away': goals}}},))


def test_fitter_cannot_pool_legacy_and_candidate_laws_even_if_shapes_match():
    cases = [_fit_case(OLD_BASE, -1., 0), _fit_case(NEW_BASE, 1., 1)]
    with pytest.raises(ContextContractError, match='base|variant|law'):
        fit_heads(cases, _config(OLD_EFFECT), 1.)


@pytest.mark.parametrize('variant,base', [(OLD_EFFECT, OLD_BASE), (NEW_EFFECT, NEW_BASE)])
def test_fitter_and_application_primitive_bind_explicit_matching_variant(variant, base):
    matrices = tuple({(0,0): .45, (0,1): .05, (1,0): .05, (1,1): .45} for _ in range(8))
    x, targets = np.array([[-1.]]*4+[[1.]]*4), np.array([[0,0]]*4+[[1,1]]*4)
    fit = fit_joint_offset(matrices, x, targets, alpha=1., variant=variant)
    assert fit['version'] == variant
    assert np.array_equal(joint_offset_delta(fit, np.zeros((1,1)), variant=variant), np.zeros((1,2)))
    with pytest.raises(ContextContractError):
        joint_offset_delta(fit, np.ones((1,1)), variant=NEW_EFFECT if variant == OLD_EFFECT else OLD_EFFECT)
    heads = fit_heads([_fit_case(base, -1., 0), _fit_case(base, 1., 1)], _config(variant), 1.)
    assert set(heads) == {'home', 'away'} and heads['home']['link'] == 'log_joint_tilt'


def test_archived_v1_fitter_output_is_byte_faithful_not_relabelled():
    matrices = tuple({(0,0): .45, (0,1): .05, (1,0): .05, (1,1): .45} for _ in range(8))
    fit = fit_joint_offset(matrices, np.array([[-1.]]*4+[[1.]]*4), np.array([[0,0]]*4+[[1,1]]*4), alpha=1.)
    assert canonical_bytes(fit) == b'{"alpha":1.0,"coef":[[0.34839748002518484,0.34839748002518484]],"n_rows":8,"scale":[1.0],"version":"football-joint-log-tilt-v1"}'


def test_explicit_candidate_numerical_comparison_cannot_claim_legacy_effect_law(monkeypatch):
    from context_models.football_joint_effect import compare_joint_effect
    original, _binding = _capture(monkeypatch, NEW_LAW)
    result = compare_joint_effect(original, home_delta=0., away_delta=0.)
    assert result['version'] == NEW_EFFECT
    assert result['probabilities'] == original.to_dict()['probabilities']


def test_candidate_native_case_uses_owning_d1_resolver_not_raw_poisson(tmp_path, monkeypatch):
    from test_football_joint_training import source_case
    from context_models.training_cases import assemble_training_cases
    with monkeypatch.context() as patch:
        # An explicitly selected OFFLINE candidate execution fingerprint, not
        # an activation or change to the production/default engine version.
        patch.setattr(engine, 'CHALLENGE_PREDICTION_VERSION', 'challenge-engine:coherent-joint-calibration-v15')
        path, case, config = source_case(tmp_path, patch, law_version=NEW_LAW)
        before = path.read_bytes()
        result = assemble_training_cases((case,), config)
        assert result['canonical_events'] == 1 and not result['excluded']
        assert len(result['rows']) == 2
        assert case['case']['payload']['base']['version'] == NEW_BASE
        assert path.read_bytes() == before
        # D2 resolves the physically stored case through the same native law,
        # rather than requiring a raw-Poisson replay artifact for v2.
        from context_models.dataset import _reader, resolve_case
        from context_models.training_contracts import validate_resolved_case
        from context_training_helpers import NOW
        from datetime import timedelta
        from model_artifacts import put_artifact
        built = canonical_timestamp(NOW+timedelta(hours=6))
        case_ref = put_artifact(path, kind=case['case']['kind'], payload=case['case']['payload'], created_at=NOW+timedelta(hours=6))
        item = dict(case_ref=case_ref, observation_refs=sorted(row['digest'] for row in case['observations']))
        before_d2 = path.read_bytes()
        with _reader(path) as connection:
            resolved = resolve_case(connection, item, config=config, plan={'created_at': built, 'code_revision': 'a'*40}, latest=built)
        checked = validate_resolved_case(resolved, config=config)
        assert checked['case']['payload']['base'] == case['case']['payload']['base']
        assert path.read_bytes() == before_d2


def test_active_v1_worker_cannot_apply_old_fit_to_explicit_candidate_original(tmp_path, monkeypatch):
    from test_football_joint_training import source_case
    from test_football_joint_worker import fitted, compare, snapshots
    with monkeypatch.context() as patch:
        patch.setattr(engine, 'CHALLENGE_PREDICTION_VERSION', 'challenge-engine:coherent-joint-calibration-v15')
        isolated = source_case(tmp_path, patch, law_version=NEW_LAW)
        path, case, config = isolated
        fitted((path, case, dict(config, model_variant=OLD_EFFECT)))
        before = path.read_bytes()
        result = compare(isolated)
        assert result['status'] == 'effect-unavailable' and result['role'] == 'not_applied'
        assert snapshots(path) == [] and path.read_bytes() == before
