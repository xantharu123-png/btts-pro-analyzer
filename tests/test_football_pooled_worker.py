"""Native B1 -> frozen ORIGINAL -> fitted synthetic comparison, never approval.

These tests catch selecting v1 for a v2 fit, accepting another version's
coverage, expanding v3 sources for v2, and losing exact replay/base identity.
No successful worker is mocked; all databases are newly built, never copied.
"""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

import football_joint_worker as worker
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_models.dataset import _reader
from context_models.football_joint_context import joint_features, fit_heads
from context_models.football_training import build_joint_training_case
from context_snapshots import _decode_snapshot
from context_transport import calculate_context_payload, replay_context_payload, project_context_market
from context_training_helpers import NOW
from model_artifacts import canonical_bytes, put_artifact, publish_slots
from test_football_joint_training import source_case
from test_football_player_load_integration import national


V1 = 'football-native-context-v1'
V2 = 'football-native-context-exposure-v2'
V3 = 'football-native-player-load-v3'
CONTRACTS = [
    (V1, {'version': 'football-native-context-v1.coverage', 'case': 'source-bound'},
     'roster.home.venue_attack.goals.api-football:player:1'),
    (V2, {'version': 'football-native-context-exposure-v2.coverage', 'case': 'source-bound'},
     'roster.home.venue_attack.goals.loss_exposure_v1'),
    (V3, {'version': 'football-native-player-load-v3.coverage', 'case': 'source-bound'},
     'schedule.gap_hours_home'),
]


def native(tmp_path, *, event_id=9000, shift=0):
    import test_football_joint_training as support
    import context_training_helpers as helpers
    from context_observations import append_observation, observations_as_of
    from context_sources.football import normalize_football_context
    inventory = support.football_inventory
    detail = helpers.detail
    # Small explicitly reported historical cohorts. Current source says both
    # reported players are out; no confirmed target lineup is fabricated.
    def reported(*a, **kw):
        raw = detail(*a, **kw)
        for block in raw['players']:
            block['players'] = block['players'][:1]
        if raw['fixture']['status']['short'] == 'NS':
            raw['lineups'] = []
        return raw
    def with_absences(*a, **kw):
        event, history, observations, identity = inventory(*a, **kw)
        decision = kw['decision']
        received = decision-timedelta(minutes=10)
        injuries = [{'fixture': {'id': event_id, 'date': event['scheduled_start']},
                     'league': {'id': 39}, 'team': {'id': team},
                     'player': {'id': player, 'type': 'Missing Fixture', 'reason': 'Injury'}}
                    for team, player in ((1, 1), (2, 12))]
        path = a[0]/f'synthetic-football-{event_id}.db'
        for row in normalize_football_context(event, injuries=injuries, lineups=[], appearances=[], observed_at=received):
            append_observation(path, row, observed_at=received)
        target = observations_as_of(path, event['event_key'], cutoff=decision,
                                    schedule_revision=event['schedule_revision'])
        observations = tuple(r for r in observations if r['event_key'] != event['event_key']) + tuple(target)
        return event, history, observations, identity
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(helpers, 'detail', reported)
        patch.setattr(support, 'football_inventory', with_absences)
        return source_case(tmp_path, patch, event_id=event_id, shift=shift)


@pytest.fixture
def original(tmp_path):
    return native(tmp_path)


def config_for(config, version, coverage, name):
    config = deepcopy(config)
    config.update(feature_version=version, coverage=deepcopy(coverage),
                  feature_names=sorted(set([name, 'schedule.gap_hours_home'])))
    config['groups'] = {'schedule': ['schedule.gap_hours_home']}
    if version != V3:
        config['groups']['roster'] = [name]
    return config


@pytest.fixture(scope='module')
def effects(tmp_path_factory):
    # Real fitting over two distinct earlier native synthetic publications.
    # Their actual outcomes are available before the live worker's decision.
    historical = [native(tmp_path_factory.mktemp('pool-train'), event_id=9100+i, shift=-12+i)
                  for i in range(2)]
    result = {}
    for version, coverage, name in CONTRACTS:
        config = config_for(historical[0][2], version, coverage, name)
        cases = []
        for path, case, _ in historical:
            payload = case['case']['payload']
            cutoff = datetime.fromisoformat(payload['base']['cutoff'])
            built = build_joint_training_case(path, binding_ref=payload['replay_ref'],
                outcome_ref=payload['outcome_ref'], identity_ref=payload['event_identity_hash'],
                config=config, as_of=cutoff+timedelta(hours=6))
            assert all(built['case']['payload']['features']['states'][n] == 'available'
                       for n in config['feature_names'])
            cases.append(built)
        result[version] = dict(schema=1, heads=fit_heads(tuple(cases), config, 1.),
            training_end='2026-08-29T18:00:00.000000Z',
            training_refs_hash=digest(sorted(case['case']['digest'] for case in cases)),
            **{key: config[key] for key in ('sport', 'family', 'feature_version', 'feature_names',
                'preprocessing_artifacts', 'joint_calibration', 'population', 'coverage', 'model_variant')})
    return result


def activate(path, effects):
    created = NOW + timedelta(seconds=2)
    slots = {f'context-effect:football:test:{i}': put_artifact(path,
        kind='context-effect-v1', payload=effect, created_at=created)
        for i, effect in enumerate(effects)}
    publish_slots(path, slots, expected_manifest=None, published_at=created)


def compare(original, *, minutes=2):
    path, case, _ = original
    return worker.publish_joint_comparison(path, case['case']['payload']['replay_ref'],
        decision_at=NOW+timedelta(minutes=minutes))


def stored(path, report):
    with _reader(path) as connection:
        raw = connection.execute('SELECT payload,payload_digest FROM context_snapshots WHERE key=?',
                                 (report['reference']['key'],)).fetchone()
        return _decode_snapshot(report['reference']['key'], *raw, connection=connection)


@pytest.mark.parametrize('version,coverage,name', CONTRACTS)
def test_native_fit_uses_exact_contract_and_replays_without_changing_public_p(original, effects, version, coverage, name):
    path, case, _ = original
    national_refs = national(path)
    activate(path, [effects[version]])
    before_original = canonical_bytes(case['case']['payload']['base'])
    report = compare(original)
    assert report['status'] == 'comparison-stored', report
    assert report['role'] == 'experimental' and report['publication_reused'] is False
    payload = stored(path, report)
    features, result = payload['features'], payload['result']
    assert features['version'] == version and features['coverage'] == coverage
    assert features['states'][name] == 'available' and features['refs'][name]
    assert result['used_markets'] == result['base_markets'] == case['case']['payload']['base']['markets']
    assert result['used_params'] == result['base_params'] == case['case']['payload']['base']['params']
    assert result['comparison_markets'] != result['base_markets']
    assert result['approval_hash'] is None and result['certified_markets'] == []
    assert payload['approval'] is None and payload['approval_hash'] is None
    if version == V3:
        assert set(national_refs) <= set(payload['observation_refs'])
        assert not any(n.startswith('roster.') for n in features['values'])
        assert not any(n.endswith('loss_exposure_v1') for n in features['values'])
        assert features['states']['load.home.reported_minutes_schedule_7d'] == 'missing'
        assert features['values']['load.home.reported_minutes_schedule_7d'] is None
    else:
        assert not set(national_refs) & set(payload['observation_refs'])
        assert not any(n.startswith('load.') for n in features['values'])
        assert (name.endswith('loss_exposure_v1')) == (version == V2)
    replayed = replay_context_payload(payload, key=report['reference']['key'],
        effect_artifact=payload['effect_artifact'], approval=None)
    assert canonical_bytes(replayed) == canonical_bytes(payload)
    projected = project_context_market(payload, report['reference'], 'RESULT_HOME')
    assert projected['used_probability'] == projected['base_probability']
    assert projected['delta_pp'] == 0.
    before_db = path.read_bytes()
    later = compare(original, minutes=12)
    assert later == {**report, 'publication_reused': True}
    assert path.read_bytes() == before_db
    assert canonical_bytes(case['case']['payload']['base']) == before_original


def test_v2_transport_accepts_native_source_bound_vector_without_activating(original, effects):
    _, case, _ = original
    old = case['case']['payload']
    features = joint_features(old['event'], case['observations'], old['base'], cutoff=NOW, version=V2)
    effect = effects[V2]
    ref = digest({'kind': 'context-effect-v1', 'payload': effect})
    payload = calculate_context_payload(event=old['event'], base=old['base'], features=features,
        observation_refs=sorted(r['digest'] for r in case['observations']), preprocessing_refs=[],
        effect_artifact={'kind': 'context-effect-v1', 'payload': effect}, effect_hash=ref, approval=None)
    assert payload['features']['coverage'] == {'version': 'football-native-context-exposure-v2.coverage', 'case': 'source-bound'}
    assert payload['result']['role'] == 'experimental'
    assert payload['result']['used_markets'] == old['base']['markets']


@pytest.mark.parametrize('version,coverage,name', CONTRACTS)
@pytest.mark.parametrize('bad', ['other-version-coverage', 'other-case', 'unknown-version'])
def test_active_fit_rejects_wrong_exact_coverage_or_unknown_version_without_writes(tmp_path, effects, version, coverage, name, bad):
    path = tmp_path/'rejected-fit.db'
    effect = deepcopy(effects[version])
    if bad == 'other-version-coverage':
        effect['coverage'] = {'version': 'football-native-context-exposure-v2.coverage' if version != V2
                              else 'football-native-context-v1.coverage', 'case': 'source-bound'}
    elif bad == 'other-case':
        effect['coverage']['case'] = 'reported_players'
    else:
        effect['feature_version'] = 'football-native-context-unknown-v9'
        effect['coverage'] = {'version': 'football-native-context-unknown-v9.coverage', 'case': 'source-bound'}
    activate(path, [effect])
    before = path.read_bytes()
    report = worker.publish_joint_comparison(path, 'a'*64, decision_at=NOW+timedelta(minutes=2))
    assert report['status'] == 'effect-unavailable' and report['reference'] is None
    assert report['role'] == 'not_applied' and path.read_bytes() == before


def test_v2_selected_only_after_nonapplicable_v1_population_is_removed(original, effects):
    path, _, _ = original
    v1 = deepcopy(effects[V1])
    v1['population']['competitions'] = ['40']
    activate(path, [v1, effects[V2]])
    report = compare(original)
    assert report['status'] == 'comparison-stored', report
    assert stored(path, report)['features']['version'] == V2


def test_applicable_v1_and_v2_are_ambiguous_not_automatically_selected(original, effects):
    path, _, _ = original
    activate(path, [effects[V1], effects[V2]])
    before = path.read_bytes()
    report = compare(original)
    assert report['status'] == 'effect-ambiguous' and report['reference'] is None
    assert report['role'] == 'not_applied' and path.read_bytes() == before


def test_v2_changed_native_target_source_is_rejected_without_writes(original, effects):
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    from context_training_helpers import detail
    path, _, _ = original
    activate(path, [effects[V2]])
    raw = detail(9000, NOW+timedelta(hours=4), terminal='NS')
    observed = NOW+timedelta(minutes=1)
    append_observation(path, normalize_football_base_input(raw, observed_at=observed), observed_at=observed)
    before = path.read_bytes()
    report = compare(original)
    assert report['status'] == 'source-unavailable'
    assert report['reason'] == 'target_changed_before_context_decision'
    assert report['reference'] is None and path.read_bytes() == before


def test_stored_v2_input_binding_rejects_altered_version_coverage_or_source(original, effects):
    path, _, _ = original
    activate(path, [effects[V2]])
    report = compare(original)
    assert report['status'] == 'comparison-stored', report
    original_payload = stored(path, report)
    for field, value in [('version', V1), ('version', 'unknown-v9'),
        ('coverage', {'version': 'football-native-context-v1.coverage', 'case': 'source-bound'}),
        ('reference_hash', 'f'*64), ('refs', {})]:
        payload = deepcopy(original_payload)
        payload['features'][field] = value
        with pytest.raises((ContextContractError, ContextIntegrityError)):
            replay_context_payload(payload, key=report['reference']['key'],
                effect_artifact=payload['effect_artifact'], approval=None)


def test_default_v1_native_feature_bytes_remain_explicitly_identical(original):
    _, case, _ = original
    payload = case['case']['payload']
    default = joint_features(payload['event'], case['observations'], payload['base'], cutoff=NOW)
    assert canonical_bytes(default) == canonical_bytes(payload['features'])
    assert default['version'] == V1
    assert default['coverage'] == {'version': 'football-native-context-v1.coverage', 'case': 'source-bound'}
    assert not any(n.endswith('loss_exposure_v1') or n.startswith('load.') for n in default['values'])


def test_unapplied_native_transport_rejects_another_versions_coverage(original):
    _, case, _ = original
    old = case['case']['payload']
    for version, coverage, _ in CONTRACTS:
        features = joint_features(old['event'], case['observations'], old['base'], cutoff=NOW, version=version)
        features['coverage'] = {'version': 'football-native-context-v1.coverage' if version != V1
                               else 'football-native-player-load-v3.coverage', 'case': 'source-bound'}
        with pytest.raises(ContextContractError, match='coverage'):
            calculate_context_payload(event=old['event'], base=old['base'], features=features,
                observation_refs=sorted(r['digest'] for r in case['observations']), preprocessing_refs=[],
                effect_artifact=None, effect_hash=None, approval=None)
