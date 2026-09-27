"""Synthetic source-bound training mechanics, not predictive-quality evidence."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError, digest
from context_training_helpers import NOW, envelope, football_inventory


def source_case(tmp_path, monkeypatch, *, event_id=9000, shift=0):
    from context_models.football_training import build_joint_training_case
    from context_models.football_original_publication import FootballOriginalPublication
    from context_sources.football_capture import _Capture
    from context_sources.outcomes import normalize_football_outcome
    from context_observations import append_observation
    from model_artifacts import put_artifact
    import football_original
    import challenge_engine as engine
    from context_training_helpers import detail, canonical_timestamp
    decision = NOW + timedelta(days=shift)
    with monkeypatch.context() as scoped:
        import context_training_helpers as helpers
        original_detail = helpers.detail
        scoped.setattr(helpers, 'detail', lambda native_id, *a, **kw:
            original_detail(native_id + event_id*100 if native_id < 9000 else native_id, *a, **kw))
        event, history, observations, identity = football_inventory(tmp_path, decision=decision, event_id=event_id)
    path = tmp_path / f"synthetic-football-{event_id}.db"
    observer = _Capture(path, baseline_enabled=True)
    originals = []
    for row in history:
        raw = row['payload']['detail']
        observer.record('fixtures', {'id': raw['fixture']['id']},
            {'response': [raw], 'errors': [], 'results': 1, 'paging': {'current': 1, 'total': 1}},
            observed_at=row['observed_at'], status=200)
        originals.append(raw)
    target = next(raw for raw in originals if raw['fixture']['id'] == event_id)
    past = [raw for raw in originals if raw is not target]
    # Freeze an actual pre-match publication, including real isolated B1 rows.
    class Clock:
        @staticmethod
        def now(tz=None): return decision + timedelta(seconds=1)
    monkeypatch.setattr('context_models.football_original_publication.datetime', Clock)
    monkeypatch.setattr(football_original, '_capture_now', lambda: decision)
    publication = FootballOriginalPublication(path, observer, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=2_000_000)
    publication.freeze(tuple(originals))
    engine.fixture_market_probabilities(target, past, **publication.model_kwargs(decision_at=decision))
    assert publication.report()['events'][0]['source_state'] == 'captured'
    binding_ref = publication.report()['events'][0]['binding_ref']
    identity_ref = put_artifact(path, kind=identity['kind'], payload=identity['payload'], created_at=decision+timedelta(hours=5))
    result = normalize_football_outcome(event, detail(event_id, decision+timedelta(hours=2)), observed_at=decision+timedelta(hours=4))
    outcome_ref = append_observation(path, result, observed_at=decision+timedelta(hours=4))
    config = dict(schema=1, sport='football', family='football:goals:90min',
        feature_version='football-native-context-v1', feature_names=['roster.home.venue_attack.goals.api-football:player:1'],
        population=dict(sport='football', competitions=['39'], formats=['90min'], tours=[None], surfaces=[None], indoor=[None]),
        coverage=dict(version='football-native-context-v1.coverage', case='source-bound'),
        model_variant='football-joint-log-tilt-v1', base_versions=['football-goals-captured-joint-v1'],
        head_links={'home': 'log_joint_tilt', 'away': 'log_joint_tilt'}, reference_version='football-context-reference-v2',
        preprocessing_artifacts={}, groups={'roster': ['roster.home.venue_attack.goals.api-football:player:1']},
        joint_calibration={'kind': 'identity'}, target_markets=['RESULT_AWAY', 'RESULT_DRAW', 'RESULT_HOME'],
        outcome_contract='football-regulation-ft-v1', train_end=canonical_timestamp(NOW+timedelta(days=2)),
        tune_end=canonical_timestamp(NOW+timedelta(days=4)), alpha_grid=[.01, .1, 1., 10., 100.])
    case = build_joint_training_case(path, binding_ref=binding_ref, outcome_ref=outcome_ref,
        identity_ref=identity_ref, config=config, as_of=decision+timedelta(hours=6))
    return path, case, config


@pytest.fixture(scope='module')
def native_case(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        return source_case(tmp_path_factory.mktemp('joint-native'), patch)


def test_actual_publication_builds_a_causal_joint_case(native_case):
    from context_models.training_cases import assemble_training_cases
    path, case, config = deepcopy(native_case)
    before = path.read_bytes()
    result = assemble_training_cases((case,), config)
    assert result['canonical_events'] == 1 and not result['excluded']
    assert len(result['rows']) == 2
    assert path.read_bytes() == before
    assert 'joint_cells' in case['case']['payload']['base']['params']


@pytest.mark.parametrize('change', ['feature', 'joint', 'source', 'late', 'identity'])
def test_fabricated_case_cannot_pass_with_fresh_public_hashes(native_case, change):
    from context_models.training_contracts import validate_resolved_case
    _, case, config = deepcopy(native_case)
    payload = case['case']['payload']
    if change == 'feature':
        payload['features']['values'][config['feature_names'][0]] += 1
    elif change == 'joint':
        payload['base']['params']['joint_cells'][0][2] += .01
    elif change == 'source':
        case['observations'] = tuple(r for r in case['observations'] if r['kind'] != 'base_fixture')
    elif change == 'late':
        payload['base']['cutoff'] = payload['event']['scheduled_start']
    else:
        payload['event_identity_hash'] = 'f'*64
    case['case'] = envelope('context-training-case-v1', payload)
    with pytest.raises(ContextContractError):
        validate_resolved_case(case, config=config)


def test_original_binding_cannot_swap_receipts_between_matches(native_case):
    from context_models.training_contracts import validate_resolved_case
    _, case, config = deepcopy(native_case)
    payload = case['case']['payload']
    binding = case['artifacts'].pop(payload['replay_ref'])
    refs = binding['payload']['consumed_receipts']
    first, second = list(refs)[:2]
    refs[first], refs[second] = refs[second], refs[first]
    changed = envelope(binding['kind'], binding['payload'])
    case['artifacts'][changed['digest']] = changed
    payload['replay_ref'] = changed['digest']
    case['case'] = envelope('context-training-case-v1', payload)
    with pytest.raises(ContextContractError, match='binding.*receipt'):
        validate_resolved_case(case, config=config)


def test_consumed_xg_needs_the_actual_matching_statistics_receipt():
    from context_training_helpers import detail
    from context_models.football_training import _check_goal_source
    from context_models.replay import ReplayUnavailable
    import challenge_engine as engine
    raw = detail(1000, NOW-timedelta(days=1))
    record = engine.football_base_history_record(raw)
    _check_goal_source(record, raw)
    record.update(xg_home=1.2, xg_away=.8)
    with pytest.raises(ReplayUnavailable, match='xg_receipt_unavailable'):
        _check_goal_source(record, raw)
    raw['statistics'] = [{'team': {'id': team}, 'statistics': [{'type': 'expected_goals', 'value': value}]}
                         for team, value in ((1, '1.2'), (2, '0.8'))]
    _check_goal_source(record, raw)
    record['xg_home'] = 1.3
    with pytest.raises(ContextContractError, match='original xG inputs'):
        _check_goal_source(record, raw)
    raw['statistics'].append(deepcopy(raw['statistics'][0]))
    with pytest.raises(ContextContractError, match='conflicting team blocks'):
        _check_goal_source(record, raw)
    raw['statistics'] = [{'team': None}]
    with pytest.raises(ContextContractError, match='invalid team blocks'):
        _check_goal_source(record, raw)


def test_joint_effect_and_distribution_loss_use_same_law(native_case):
    from context_models.football_joint_effect import fit_joint_offset
    from context_models.football_joint_context import effect_heads
    from context_models.football_effect import apply_football_effect
    from context_models.distribution_losses import paired_distribution_losses
    import numpy as np
    _, case, config = deepcopy(native_case)
    payload = case['case']['payload']
    base = payload['base']
    matrix = {(h, a): p for h, a, p in base['params']['joint_cells']}
    fit = fit_joint_offset((matrix, matrix), np.array([[1.], [2.]]), np.array([[2., 1.], [3., 1.]]), alpha=1.)
    artifact = dict(schema=1, heads=effect_heads(fit), training_end=config['train_end'], training_refs_hash='b'*64,
        **{key: config[key] for key in ('sport', 'family', 'feature_version', 'feature_names',
            'preprocessing_artifacts', 'joint_calibration', 'population', 'coverage', 'model_variant')})
    # Apply a previously trained synthetic model, not a model trained in the future.
    artifact['training_end'] = '2026-08-01T00:00:00.000000Z'
    changed = apply_football_effect(base, payload['features'], artifact, event=payload['event'])
    assert changed['markets'] != base['markets']
    outcome = next(r for r in case['observations'] if r['digest'] == payload['outcome_ref'])
    losses = paired_distribution_losses(base, changed, outcome, event=payload['event'], block='test:0')
    assert losses['tail_policy'] == 'calibrated-joint-goal-buckets-25plus-log-v1'


def test_joint_zero_effect_is_exact_original(native_case):
    from context_models.football_joint_context import apply_joint_effect
    from context_models.contracts import validate_effect_artifact
    _, case, config = deepcopy(native_case)

    payload = case['case']['payload']
    head = dict(link='log_joint_tilt', scale=[1.], coef=[0.], alpha=1., n_rows=3)
    effect = validate_effect_artifact(dict(schema=1, heads={'home': head, 'away': head},
        training_end='2026-08-01T00:00:00.000000Z', training_refs_hash='b'*64,
        **{key: config[key] for key in ('sport', 'family', 'feature_version', 'feature_names',
            'preprocessing_artifacts', 'joint_calibration', 'population', 'coverage', 'model_variant')}))
    changed = apply_joint_effect(payload['base'], payload['features'], effect, event=payload['event'])
    assert changed['params'] == payload['base']['params']
    assert changed['markets'] == payload['base']['markets']


def test_existing_worker_keeps_unapproved_joint_effect_out_of_selected_probability(native_case):
    from context_transport import calculate_context_payload
    _, case, config = deepcopy(native_case)
    payload = case['case']['payload']
    head = dict(link='log_joint_tilt', scale=[1.], coef=[.01], alpha=1., n_rows=3)
    effect = envelope('context-effect-v1', dict(schema=1, heads={'home': head, 'away': head},
        training_end='2026-08-01T00:00:00.000000Z', training_refs_hash='b'*64,
        **{key: config[key] for key in ('sport', 'family', 'feature_version', 'feature_names',
            'preprocessing_artifacts', 'joint_calibration', 'population', 'coverage', 'model_variant')}))
    result = calculate_context_payload(event=payload['event'], base=payload['base'], features=payload['features'],
        observation_refs=sorted(r['digest'] for r in case['observations'] if r['kind'] != 'match_outcome'),
        preprocessing_refs=[], effect_artifact={key: effect[key] for key in ('kind', 'payload')},
        effect_hash=effect['digest'], approval=None)
    assert result['result']['role'] == 'experimental'
    assert result['result']['used_params'] == payload['base']['params']
    assert result['result']['comparison_params'] != payload['base']['params']


def test_later_weather_uses_real_later_decision_not_backdating(native_case, tmp_path):
    import shutil
    from context_models.football_training import build_joint_training_case
    from context_sources.openweather import forecast_payload, normalize_forecast
    from context_observations import append_observation
    from datetime import datetime
    path, case, config = deepcopy(native_case)
    path = shutil.copyfile(path, tmp_path / 'synthetic-later-context.db')
    payload = case['case']['payload']
    clock = NOW+timedelta(minutes=2)
    forecast = forecast_payload(payload['event'], city='Example', country='GB', latitude=50., longitude=0.,
        point={'dt': datetime.fromisoformat(payload['event']['scheduled_start']).timestamp(),
               'main': {'temp': 18.}, 'wind': {'speed': 4.}})
    append_observation(path, normalize_forecast(forecast, observed_at=clock), observed_at=clock)
    def build(decision):
        return build_joint_training_case(path, binding_ref=payload['replay_ref'], outcome_ref=payload['outcome_ref'],
            identity_ref=payload['event_identity_hash'], config=config, as_of=NOW+timedelta(hours=6), decision_at=decision)
    assert build(NOW)['case']['payload']['features']['values']['weather.temperature_c'] is None
    later = build(clock)['case']['payload']
    assert later['features']['values']['weather.temperature_c'] == 18.
    assert later['base']['params'] == payload['base']['params']
    assert later['base']['cutoff'] != payload['base']['cutoff']
    assert later['base']['model_hash'] == payload['base']['model_hash']
    with pytest.raises(ContextContractError):
        build(NOW-timedelta(minutes=1))


@pytest.fixture(scope='module')
def joint_cohort(tmp_path_factory):
    import sqlite3
    from context_models.dataset import _reader
    from context_models.football_training import build_joint_training_case
    from model_artifacts import put_artifact, _connect
    root = tmp_path_factory.mktemp('joint-cohort')
    items = []
    with pytest.MonkeyPatch.context() as patch:
        for index, day in enumerate((0, 1, 3, 4, 6, 8)):
            items.append(source_case(root, patch, event_id=9000+index, shift=day))
    db = root / 'combined.db'
    built = NOW+timedelta(days=10)
    conn = _connect(db)
    conn.close()
    from context_observations import append_observation_batch
    from context_models.contracts import OBSERVATION_FIELDS
    from datetime import datetime
    for path, case, _ in items:
        # Only synthetic isolated test stores are combined. Production uses
        # its existing canonical DB directly and makes no additional copy.
        rows = tuple(({key: row[key] for key in OBSERVATION_FIELDS}, datetime.fromisoformat(row['observed_at']))
                     for row in case['observations'])
        for start in range(0, len(rows), 512):
            append_observation_batch(db, rows[start:start+512])
        with sqlite3.connect(path) as source, sqlite3.connect(db) as dest:
            dest.executemany('INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?)', source.execute('SELECT * FROM artifacts'))
    bindings = [case['artifacts'][case['case']['payload']['event_identity_hash']]['payload']['bindings'][0]
                for _, case, _ in items]
    identity = put_artifact(db, kind='context-native-identity-map-v1',
        payload=dict(schema=1, policy='native-source-only-v1', bindings=sorted(bindings, key=lambda b: b['event_key'])), created_at=built)
    config = items[0][2]
    cases = []
    for _, case, _ in items:
        payload = case['case']['payload']
        cases.append(build_joint_training_case(db, binding_ref=payload['replay_ref'], outcome_ref=payload['outcome_ref'],
            identity_ref=identity, config=config, as_of=built))
    return db, cases, config, built


def test_joint_public_fitter_keeps_final_games_outside_training(joint_cohort):
    from context_models.training_cases import assemble_training_cases
    from context_models.training import fit_family
    _, cases, config, _ = deepcopy(joint_cohort)
    selected = tuple(cases[:3])
    assembly = assemble_training_cases(selected, config)
    result = fit_family(assembly['rows'], config, cases=selected)
    assert result['status'] == 'fitted'
    assert (result['training_events'], result['tuning_events']) == (2, 1)
    assert len(result['alpha_scores']) == 5
    assert {head['link'] for head in result['artifact']['heads'].values()} == {'log_joint_tilt'}
    with pytest.raises(ContextContractError, match='final-test'):
        fit_family((), config, cases=(cases[-1],))


def test_schedule_proxy_uses_coupled_fit_but_missing_weather_is_not_zero(joint_cohort):
    from context_models.training_cases import assemble_training_cases
    from context_models.training import fit_family
    _, cases, config, _ = deepcopy(joint_cohort)
    config.update(feature_names=['schedule.gap_hours_home'], groups={'schedule': ['schedule.gap_hours_home']})
    selected = tuple(cases[:3])
    def bind():
        for case in selected:
            payload = case['case']['payload']
            payload['family_config_hash'] = digest(config)
            case['case'] = envelope('context-training-case-v1', payload)
    bind()
    result = fit_family(assemble_training_cases(selected, config)['rows'], config, cases=selected)
    assert result['status'] == 'fitted'
    config.update(feature_names=['weather.temperature_c'], groups={'weather': ['weather.temperature_c']})
    bind()
    absent = assemble_training_cases(selected, config)
    assert not absent['rows'] and len(absent['excluded']) == 3
    assert all(row['reason'] == 'consumed_feature_unavailable' for row in absent['excluded'])


def test_joint_case_reaches_existing_evaluator_without_a_small_sample_approval(joint_cohort):
    from context_models.training_cases import assemble_training_cases
    from context_models.training import fit_family
    from context_models.experiments import freeze_experiment
    from context_models.evaluator import evaluate_experiment, verify_evaluation
    from context_models.dataset import _reader
    from context_training_helpers import canonical_timestamp
    from model_artifacts import put_artifact
    db, cases, config, built = deepcopy(joint_cohort)
    def store(kind, payload): return put_artifact(db, kind=kind, payload=payload, created_at=built)
    for case in cases:
        assert store(case['case']['kind'], case['case']['payload']) == case['case']['digest']
    training = tuple(cases[:3])
    fit = fit_family(assemble_training_cases(training, config)['rows'], config, cases=training)
    assert fit['status'] == 'fitted'
    for ref, value in fit['candidate_artifacts'].items():
        assert store('context-effect-v1', value) == ref
    fit_ref = store('context-fit-v1', fit)
    member = lambda case: dict(case_ref=case['case']['digest'], observation_refs=sorted(r['digest'] for r in case['observations']))
    identity = cases[0]['case']['payload']['event_identity_hash']
    dataset = dict(schema=1, event_identity_hash=identity, groups=[dict(family_config_hash=digest(config),
        training_cases=[member(c) for c in training], final_cases=[member(c) for c in cases[3:]], unavailable_final=[], fit_ref=fit_ref)])
    definition = dict(family_config_hash=digest(config), ablation='full', target_markets=config['target_markets'],
                      outcome_contract=config['outcome_contract'])
    hypothesis = dict(**definition, hypothesis_id=digest(definition), candidate_artifact=fit['effect_hash'], pretest_status='ready')
    frozen = built+timedelta(minutes=1)
    plan = dict(schema=1, dataset_hash=store('context-dataset-v1', dataset), event_identity_hash=identity,
        code_revision='a'*40, base_versions=config['base_versions'], family_configs=[config],
        train_end=config['train_end'], tune_end=config['tune_end'],
        test_blocks=[[canonical_timestamp(NOW+timedelta(days=d)), canonical_timestamp(NOW+timedelta(days=d+2))] for d in (4, 6, 8)],
        target_markets=config['target_markets'], outcome_contracts=[config['outcome_contract']], candidate_artifacts=[fit['effect_hash']],
        policy_version='context-paired-hac-bh-v1', availability_classes=['prospective'], created_at=canonical_timestamp(frozen),
        hypotheses=[hypothesis], test_inventory=[dict(event=c['case']['payload']['event'],
            decision_at=c['case']['payload']['base']['cutoff'], block=f'test:{i}') for i, c in enumerate(cases[3:])])
    ref = freeze_experiment(db, plan, created_at=frozen)
    result = evaluate_experiment(db, ref, evaluated_at=built+timedelta(hours=1))
    hid = hypothesis['hypothesis_id']
    assert len(result['payload']['results'][hid]) == 9
    assert len(result['payload']['distribution_losses'][hid]) == 3
    assert result['payload']['ready_failures'][hid] == [] and result['approvals'] == []
    with _reader(db) as connection:
        assert verify_evaluation(connection, result['digest'])['payload'] == result['payload']
