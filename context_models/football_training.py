"""Native ORIGINAL-v2 adapter for the existing D1/D2 pipeline.

Read-only reconstruction of actual publications, not synthetic raw-Poisson
baselines or a second database. Hashes check bytes; physical clocks are checked
by the database owner before detached validation and chronological fitting.
"""
from copy import deepcopy
from datetime import datetime
import hashlib

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest, require_object, validate_base_distribution
from context_models.football_joint_context import BASE_VERSION, joint_params, joint_features
from context_models.football_original_publication import BINDING_KIND, CODE_KIND
from context_models.football_original_storage import ORIGINAL_KIND, MAX_MANIFEST_BYTES, MAX_ORIGINAL_BYTES, _ALL_PATHS, _raw, _hint, _expand
from context_models.replay import ReplayUnavailable
from context_models.training_contracts import validate_artifact_envelope, resolve_identity_map
from context_observations import _SELECT, _decode_receipt, _check_selected_row
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import validate_football_base_input, validate_outcome_record
from football_original import FootballOriginal
from model_artifacts import canonical_bytes


def _same(actual, expected, reason):
    if canonical_bytes(actual) != canonical_bytes(expected):
        raise ContextIntegrityError(reason)


def _original_envelope(original):
    value = {'kind': ORIGINAL_KIND, 'payload': original.to_dict()}
    return {'digest': digest(value), **value}


def _check_goal_source(record, detail):
    native = engine.football_base_history_record(detail)
    if any(native[key] != value for key, value in record.items()
           if key not in {'source_marker', 'xg_home', 'xg_away'}):
        raise ContextIntegrityError('binding receipt differs from the original goal inputs')
    if record['xg_home'] is None and record['xg_away'] is None:
        return  # The baseline did not consume xG for this fixture.
    from xg_backfill import _extract_fixture_stats
    statistics = detail.get('statistics')
    if type(statistics) is not list:
        raise ReplayUnavailable('original_native_xg_receipt_unavailable')
    ids = []
    for block in statistics:
        if (type(block) is not dict or type(block.get('team')) is not dict
                or type(block['team'].get('id')) is not int or block['team']['id'] <= 0):
            raise ContextIntegrityError('binding xG receipt has invalid team blocks')
        ids.append(block['team']['id'])
    if len(ids) != len(set(ids)):
        raise ContextIntegrityError('binding xG receipt has conflicting team blocks')
    values = _extract_fixture_stats(statistics, record['home_id'], record['away_id'])
    if values is None or values['xg'] is None:
        raise ReplayUnavailable('original_native_xg_receipt_unavailable')
    if values['xg'] != (record['xg_home'], record['xg_away']):
        raise ContextIntegrityError('binding receipt differs from the original xG inputs')


def joint_base(original, binding, *, decision_at=None):
    packet = original.to_dict()
    event = binding['native_event']
    if event is None:
        raise ReplayUnavailable('original_native_event_unresolved')
    decision = binding['decision_at'] if decision_at is None else canonical_timestamp(decision_at)
    if decision < binding['decision_at'] or decision >= event['scheduled_start']:
        raise ContextContractError('context decision must follow its original and precede kickoff')
    return validate_base_distribution(dict(version=BASE_VERSION, model_hash=_original_envelope(original)['digest'],
        event_key=event['event_key'], cutoff=decision, family='football:goals:90min',
        params=joint_params(packet['distribution_capture']['families']['goals']['active']['effective_cells']),
        markets={spec.key: packet['probabilities'][spec.key][0] for spec in engine.GOAL_MARKET_SPECS},
        history_refs=packet['goal_provenance']['history_refs'], reference_weights=packet['goal_provenance']['reference_weights']))


def _load_publication(connection, binding_ref, *, latest):
    from context_models.dataset import _artifact
    from context_models.experiments import _artifact_created_at
    envelope = _artifact(connection, binding_ref, BINDING_KIND, latest=latest)
    binding = envelope['payload']
    require_object(binding, {'schema', 'source_state', 'code_state', 'empirical_state', 'native_event',
        'decision_at', 'captured_at', 'original_manifest_digest', 'original_logical_digest', 'code_digest',
        'prediction_version', 'model_contract_signature', 'target_record', 'consumed_receipts', 'inspected_receipts',
        'unresolved'}, label='football original source binding')
    if binding['source_state'] != 'captured' or binding['unresolved']:
        raise ReplayUnavailable('original_native_sources_incomplete')
    manifest = binding['original_manifest_digest']
    rows = {manifest: _raw(connection, manifest, MAX_MANIFEST_BYTES)}
    body = _hint(connection, manifest, ('body',))
    if body is None:
        raise ContextIntegrityError('original manifest has no body')
    rows[body] = _raw(connection, body, MAX_ORIGINAL_BYTES)
    for keys in _ALL_PATHS:
        ref = _hint(connection, body, keys)
        if ref is not None and ref not in rows:
            remaining = MAX_ORIGINAL_BYTES + 32*1024 - sum(len(row[1]) for row in rows.values())
            rows[ref] = _raw(connection, ref, min(MAX_ORIGINAL_BYTES, remaining))
    original = _expand(rows, manifest)[0]
    packet = original.to_dict()
    if packet['schema'] != 2:
        raise ReplayUnavailable('original_has_no_captured_joint_distribution')
    created = _artifact_created_at(connection, binding_ref)
    if (binding['native_event'] is None or binding['decision_at'] > packet['captured_at']
            or packet['captured_at'] > created or created >= binding['native_event']['scheduled_start']
            or any(row[2] > created for row in rows.values())):
        raise ContextIntegrityError('original was not physically published before kickoff')
    _same(binding['captured_at'], packet['captured_at'], 'capture clock differs from binding')
    _same(binding['original_logical_digest'], hashlib.sha256(original._bytes).hexdigest(), 'original logical bytes differ')
    code = _artifact(connection, binding['code_digest'], CODE_KIND, latest=created)
    for key in ('prediction_version', 'model_contract_signature'):
        _same(binding[key], packet[key], 'binding model identity differs')
        _same(code['payload'][key], packet[key], 'executed model identity differs')
    return envelope, original, code


def relevant_receipts(connection, packet, *, cutoff):
    """Complete predecision revision pool for the original's native events.

    Never read outcome labels here. Broader events are not silently added to
    the old model; this is the exact declared native input/context pool.
    """
    ids = {engine.football_base_history_record(raw)['fixture_id'] for raw in
           [packet['fixture'], *packet['league_history'], *(packet['team_history'] or [])]}
    result = []
    for native_id in sorted(ids):
        key = 'api-football:football:' + str(native_id)
        for raw in connection.execute(_SELECT + " WHERE r.event_key=? AND r.observed_at<=? AND r.kind!='match_outcome' ORDER BY r.observed_at,r.digest",
                                      (key, cutoff)):
            row = _decode_receipt(raw)
            row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
            result.append(row)
    return tuple(sorted(result, key=lambda row: (row['observed_at'], row['digest'])))


def joint_case_artifacts(connection, payload, *, latest):
    from context_models.dataset import _artifact
    binding, original, code = _load_publication(connection, payload['replay_ref'], latest=latest)
    decision = payload['base']['cutoff']
    if decision != binding['payload']['decision_at']:
        from context_models.experiments import _artifact_created_at
        if _artifact_created_at(connection, payload['replay_ref']) > decision:
            raise ContextIntegrityError('later context decision precedes physical original publication')
    _same(joint_base(original, binding['payload'], decision_at=decision), payload['base'], 'case changed captured joint baseline')
    _same(binding['payload']['native_event'], payload['event'], 'case changed native event')
    identity = _artifact(connection, payload['event_identity_hash'], 'context-native-identity-map-v1', latest=latest)
    # Expanded original is a detached derived view of the existing chunks;
    # do NOT store another full original in the database.
    derived = _original_envelope(original)
    return {item['digest']: item for item in (binding, derived, code, identity)}


def validate_joint_training_case(resolved, *, config, payload):
    event, base, features = (payload[key] for key in ('event', 'base', 'features'))
    decision, artifacts = base['cutoff'], resolved['artifacts']
    binding = validate_artifact_envelope(artifacts.get(payload['replay_ref']), kind=BINDING_KIND)['payload']
    original_artifact = validate_artifact_envelope(artifacts.get(base['model_hash']), kind=ORIGINAL_KIND)
    original = FootballOriginal(canonical_bytes(original_artifact['payload']))
    if set(artifacts) != {payload['replay_ref'], base['model_hash'], payload['event_identity_hash'], binding['code_digest']}:
        raise ContextIntegrityError('joint case lacks exact original, binding, code or identity bytes')
    for ref, value in artifacts.items():
        if value.get('digest') != ref:
            raise ContextIntegrityError('miskeyed joint artifact')
    code = validate_artifact_envelope(artifacts[binding['code_digest']], kind=CODE_KIND)
    packet = original.to_dict()
    if (type(binding['schema']) is not int or binding['schema'] != 1 or binding['source_state'] != 'captured'
            or binding['unresolved'] or binding['code_state'] != 'execution-fingerprint-only'
            or binding['empirical_state'] != 'not-evaluated'):
        raise ReplayUnavailable('original_native_sources_incomplete')
    _same(binding['original_logical_digest'], hashlib.sha256(original._bytes).hexdigest(), 'original logical digest differs')
    for key in ('prediction_version', 'model_contract_signature'):
        _same(code['payload'][key], packet[key], 'captured code/model identity differs')
        _same(binding[key], packet[key], 'binding/model identity differs')
    _same(binding['captured_at'], packet['captured_at'], 'binding capture clock differs')
    _same(binding['native_event'], event, 'native event differs from original')
    _same(joint_base(original, binding, decision_at=decision), base, 'base differs from actual joint original')
    original_decision = binding['decision_at']
    if original_decision > packet['captured_at'] or packet['captured_at'] >= event['scheduled_start']:
        raise ContextIntegrityError('original calculation was not before kickoff')
    if type(resolved['observations']) is not tuple:
        raise ContextContractError('joint case requires a frozen source pool')
    by_ref, source, outcomes = {}, [], []
    for row in resolved['observations']:
        _check_selected_row(row)
        if row['digest'] in by_ref:
            raise ContextIntegrityError('duplicate source receipt')
        by_ref[row['digest']] = row
        if row['kind'] == 'match_outcome':
            outcomes.append(row)
        else:
            if row['observed_at'] > decision or row['effective_at'] > decision or row['evidence_class'] != 'prospective':
                raise ReplayUnavailable('late_feature_receipt_is_not_predecision_evidence')
            source.append(row)
    if len(outcomes) != 1 or outcomes[0]['digest'] != payload['outcome_ref']:
        raise ContextIntegrityError('joint case must resolve exactly its own result')
    outcome = validate_outcome_record(outcomes[0], event=event)
    if outcome['observed_at'] <= decision or outcome['payload']['outcome_contract'] != config['outcome_contract']:
        raise ContextIntegrityError('outcome is not a later native regulation result')
    identity = resolve_identity_map(artifacts[payload['event_identity_hash']], observations=tuple(source), event_keys=(event['event_key'],))
    native_identity = next(row for row in identity['payload']['bindings'] if row['event_key'] == event['event_key'])
    if any(native_identity[key] != event[key] for key in ('home_id', 'away_id')):
        raise ContextIntegrityError('original participants differ from native identity')
    declared = set(binding['consumed_receipts'])
    expected = {row['ref'] for row in packet['goal_provenance']['history_refs']} | {binding['target_record']}
    if declared != expected or set(binding['inspected_receipts']) != expected:
        raise ContextIntegrityError('binding does not cover the original input union')
    for refs in (*binding['consumed_receipts'].values(), *binding['inspected_receipts'].values()):
        if type(refs) is not list or not refs or refs != sorted(set(refs)):
            raise ContextIntegrityError('original source references are not complete and canonical')
        for ref in refs:
            if ref not in by_ref or by_ref[ref]['kind'] != 'base_fixture':
                raise ContextIntegrityError('original source dependency is missing')
    native_rows = [row for row in source if row['kind'] == 'base_fixture']
    for row in native_rows:
        validate_football_base_input(row)
    # Recompute with latest native revisions over the complete declared pool.
    # Reusing just the old matching receipt would hide an earlier correction.
    from context_sources.football_native import football_native_provenance
    raw_receipts = tuple({'detail': row['payload']['detail'], 'observed_at': row['observed_at']}
                         for row in native_rows if row['observed_at'] <= original_decision)
    selected = []
    captures = []
    native_evidence = {}
    def resolve(fixtures):
        selected.extend(fixtures)
        provenance = football_native_provenance(fixtures, raw_receipts, decision_at=datetime.fromisoformat(original_decision))
        native_evidence.update(provenance['records'])
        return provenance
    from context_models.football_joint_effect import _curve
    engine.fixture_market_probabilities(packet['fixture'], packet['league_history'],
        {key: _curve(value) for key, value in packet['calibration_recipes'].items()},
        team_history=packet['team_history'], native_resolver=resolve, original_capture=captures.append)
    if len(captures) != 1:
        raise ContextIntegrityError('native joint reconstruction produced no original')
    _same(sorted({digest(engine.football_base_history_record(raw)) for raw in selected}), sorted(expected), 'selected original input union differs')
    rebuilt = captures[0].to_dict()
    for key in ('goal_provenance', 'goal_model', 'count_models', 'raw_probabilities', 'probabilities', 'distribution_capture'):
        _same(rebuilt[key], packet[key], 'captured joint or native source provenance differs: '+key)
    for fixture in selected:
        record = engine.football_base_history_record(fixture)
        ref = digest(record)
        inspected = [by_ref[key] for key in binding['inspected_receipts'][ref]]
        if any(row['event_key'] != 'api-football:football:'+str(record['fixture_id'])
               or row['observed_at'] > original_decision for row in inspected):
            raise ContextIntegrityError('binding inspected receipt belongs to another event or time')
        evidence = native_evidence.get(ref)
        if evidence is None:
            raise ContextIntegrityError('binding has no matching native receipt')
        consumed = sorted(row['digest'] for row in inspected
                          if row['observed_at'] == evidence['payload']['observed_at'])
        if not consumed or consumed != binding['consumed_receipts'][ref]:
            raise ContextIntegrityError('binding consumed receipt differs from the original native revision')
        for receipt in consumed:
            _check_goal_source(record, by_ref[receipt]['payload']['detail'])
    # A native detail with players/lineups must have its matching projections,
    # not an older separately normalized roster revision.
    content = {row['content_digest'] for row in source}
    latest_native = {}
    for row in native_rows:
        latest_native[row['event_key']] = max(latest_native.get(row['event_key'], ''), row['observed_at'])
    current = [row for row in native_rows if row['event_key'] == event['event_key']
               and row['observed_at'] == latest_native.get(event['event_key'])]
    if not current or any(_detail_event(row['payload']['detail']) != event for row in current):
        raise ReplayUnavailable('target_changed_before_context_decision')
    for row in native_rows:
        if row['observed_at'] != latest_native[row['event_key']]:
            continue
        raw = row['payload']['detail']
        ev = _detail_event(raw)
        projections = normalize_football_context(ev, injuries=[],
            lineups=[raw] if ev['event_key'] == event['event_key'] and 'lineups' in raw else [],
            appearances=[raw] if ev['status'] == 'completed' and 'players' in raw else [],
            observed_at=datetime.fromisoformat(row['observed_at']))
        if any(digest(part) not in content for part in projections if part['kind'] in {'appearance', 'confirmed_lineup'}):
            raise ReplayUnavailable('native_context_projection_missing_or_superseded')
    _same(joint_features(event, tuple(source), base, cutoff=datetime.fromisoformat(decision)), features,
          'joint context features differ from original source receipts')
    if features['coverage'] != config['coverage']:
        raise ReplayUnavailable('feature_coverage_outside_frozen_cohort')
    for name in config['feature_names']:
        if features['states'].get(name) != 'available' or not features['refs'].get(name):
            raise ReplayUnavailable('consumed_feature_unavailable')
        if any(ref not in by_ref or by_ref[ref]['kind'] == 'match_outcome' for ref in features['refs'][name]):
            raise ContextIntegrityError('joint feature references an absent or result receipt')
    return deepcopy(resolved)


def build_joint_training_case(path, *, binding_ref, outcome_ref, identity_ref, config, as_of, decision_at=None):
    """Build a detached case from actual stored originals; no copies or writes."""
    from context_models.dataset import _reader, _receipt
    from context_models.training_contracts import validate_family_config, validate_resolved_case
    config = validate_family_config(config)
    clock = canonical_timestamp(as_of)
    with _reader(path) as connection:
        binding, original, _ = _load_publication(connection, binding_ref, latest=clock)
        base, event = joint_base(original, binding['payload'], decision_at=decision_at), binding['payload']['native_event']
        if base['cutoff'] > clock:
            raise ContextIntegrityError('context decision is after reconstruction time')
        history = relevant_receipts(connection, original.to_dict(), cutoff=base['cutoff'])
        features = joint_features(event, history, base, cutoff=datetime.fromisoformat(base['cutoff']))
        payload = dict(schema=1, event=event, base=base, features=features, replay_ref=binding_ref,
            outcome_ref=outcome_ref, event_identity_hash=identity_ref, family_config_hash=digest(config), preprocessing_refs=[])
        artifacts = joint_case_artifacts(connection, payload, latest=clock)
        result = _receipt(connection, outcome_ref)
        if result['observed_at'] > clock:
            raise ContextIntegrityError('result was received after case construction')
        result.update(evidence_class='prospective', effective_at=result['observed_at'], publication_resolution=None)
        case = {'kind': 'context-training-case-v1', 'payload': payload}
        resolved = dict(case={'digest': digest(case), **case}, artifacts=artifacts, observations=history+(result,))
    try:
        return validate_resolved_case(resolved, config=config)
    except ReplayUnavailable:
        # D1 records the exclusion; D2 cannot turn missing ready cases into a
        # favorable smaller evaluation. Integrity errors still propagate.
        return resolved
