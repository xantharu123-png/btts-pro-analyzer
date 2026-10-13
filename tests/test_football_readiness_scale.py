"""Real SQLite scale mechanics with synthetic sources, never quality proof."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import sqlite3
import time

import pytest

import context_models.football_readiness as readiness
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, OBSERVATION_FIELDS
from context_observations import append_observation
from context_training_helpers import NOW
from test_football_joint_training import native_case

BLOCKS = tuple((NOW+timedelta(days=day), NOW+timedelta(days=day+2)) for day in (4, 6, 8))


def physical_total(path, refs):
    """Independent SQL oracle for the requested ORIGINAL/source closure."""
    artifacts, contents = set(), set()
    with sqlite3.connect(path) as con:
        for ref in refs:
            artifacts.add(ref)
            binding = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (ref,)).fetchone()[0])
            artifacts.add(binding['code_digest'])
            manifest_ref = binding['original_manifest_digest']
            artifacts.add(manifest_ref)
            manifest = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (manifest_ref,)).fetchone()[0])
            body_ref = manifest['body']['digest']
            artifacts.add(body_ref)
            body = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (body_ref,)).fetchone()[0])
            def chunks(value):
                if isinstance(value, dict):
                    if value.get('kind') == 'football-original-json-chunk-v1':
                        artifacts.add(value['digest'])
                    else:
                        for child in value.values(): chunks(child)
                elif isinstance(value, list):
                    for child in value: chunks(child)
            chunks(body)
            history = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (body['league_history']['digest'],)).fetchone()[0])['values']
            ids = [body['fixture']['fixture']['id']] + [raw['fixture']['id'] for raw in history]
            for native_id in ids:
                contents.update(row[0] for row in con.execute("SELECT content_digest FROM context_observations WHERE event_key=? AND observed_at<=? AND kind!='match_outcome'",
                    ('api-football:football:'+str(native_id), binding['decision_at'])))
            contents.update(row[0] for row in con.execute("SELECT content_digest FROM context_observations WHERE event_key=? AND kind='match_outcome'",
                (binding['native_event']['event_key'],)))
        return sum(con.execute('SELECT length(payload) FROM artifacts WHERE digest=?', (ref,)).fetchone()[0] for ref in artifacts) + sum(
            con.execute('SELECT length(payload) FROM context_contents WHERE content_digest=?', (ref,)).fetchone()[0] for ref in contents)


def expanded_occurrence_total(path, refs, original_lengths):
    """Independent former input-accounting oracle, not a physical-byte claim."""
    from model_artifacts import canonical_bytes
    total, payload_sizes = 0, {}
    with sqlite3.connect(path) as con:
        for ref, original_length in zip(refs, original_lengths):
            blob = con.execute('SELECT payload FROM artifacts WHERE digest=?', (ref,)).fetchone()[0]
            binding = json.loads(blob)
            total += len(blob)+original_length
            record_keys = set(binding['inspected_receipts'])
            declared = {item for record in record_keys for item in binding['inspected_receipts'][record]}
            event_keys = {con.execute('SELECT event_key FROM context_observations WHERE digest=?', (item,)).fetchone()[0]
                          for item in declared}
            source_refs = {row[0] for key in event_keys for row in con.execute(
                "SELECT digest FROM context_observations WHERE event_key=? AND observed_at<=? AND kind!='match_outcome'",
                (key, binding['decision_at']))}
            source_refs.update(row[0] for row in con.execute("SELECT digest FROM context_observations WHERE event_key=? AND kind='match_outcome'",
                (binding['native_event']['event_key'],)))
            for receipt in source_refs:
                content_ref, body = con.execute('SELECT r.content_digest,c.payload FROM context_observations r JOIN context_contents c ON c.content_digest=r.content_digest WHERE r.digest=?', (receipt,)).fetchone()
                # The old source sum used payload-only canonical bytes; result
                # admission used the full physical content BLOB.
                if content_ref not in payload_sizes:
                    decoded = json.loads(body)
                    payload_sizes[content_ref] = len(body) if decoded['kind'] == 'match_outcome' else len(canonical_bytes(decoded['payload']))
                total += payload_sizes[content_ref]
    return total


def test_readiness_counts_physical_closure_not_expanded_occurrences(native_case):
    path, case, config = deepcopy(native_case)
    ref = case['case']['payload']['replay_ref']
    report = readiness.inspect_football_readiness(path, ({'binding_ref': ref},), config,
        test_blocks=BLOCKS, as_of=NOW+timedelta(days=10))
    assert report['input_payload_bytes'] == physical_total(path, [ref])
    assert report['input_byte_accounting'] == 'unique-physical-payload-v1'


def test_evaluation_admission_includes_orphan_physical_contents(native_case, tmp_path):
    import shutil
    path = tmp_path/'orphan.db'
    shutil.copyfile(native_case[0], path)  # Synthetic fixture only.
    with sqlite3.connect(path) as con:
        con.execute('INSERT INTO context_contents VALUES (?, zeroblob(?))', ('f'*64, 128*1024*1024))
    with pytest.raises(ContextContractError, match='bounded physical'):
        readiness._evaluation_admission(path)


def test_evaluation_counts_same_content_once_but_keeps_distinct_receipt_clocks(tmp_path):
    from context_sources.outcomes import normalize_football_base_input
    from context_observations import append_observation_batch, _SELECT, _decode_receipt
    from context_training_helpers import detail
    path = tmp_path/'same-content.db'
    raw = detail(1000, NOW-timedelta(days=1))
    raw['fixture']['referee'] = 'synthetic-size-'+'r'*270000
    record = normalize_football_base_input(raw, observed_at=NOW)
    refs = append_observation_batch(path, tuple((record, NOW+timedelta(seconds=i)) for i in range(512)))
    with sqlite3.connect(path) as con:
        assert con.execute('SELECT sum(length(c.payload)) FROM context_observations r JOIN context_contents c ON c.content_digest=r.content_digest').fetchone()[0] > 128*1024*1024
        assert con.execute('SELECT count(*) FROM context_contents').fetchone() == (1,)
        first = _decode_receipt(con.execute(_SELECT+' WHERE r.digest=?', (refs[0],)).fetchone())
        last = _decode_receipt(con.execute(_SELECT+' WHERE r.digest=?', (refs[-1],)).fetchone())
        assert first['content_digest'] == last['content_digest'] and first['observed_at'] != last['observed_at']
    readiness._evaluation_admission(path)


@pytest.mark.parametrize('fault', ['missing', 'corrupt', 'type'])
def test_selected_shared_physical_content_fails_closed_before_writes(native_case, tmp_path, fault):
    import shutil
    path = tmp_path/(fault+'.db')
    shutil.copyfile(native_case[0], path)
    case, config = native_case[1:]
    content = next(row['content_digest'] for row in case['observations'] if row['kind'] == 'base_fixture')
    with sqlite3.connect(path) as con:
        if fault == 'missing': con.execute('DELETE FROM context_contents WHERE content_digest=?', (content,))
        else: con.execute('UPDATE context_contents SET payload=? WHERE content_digest=?', ('{}' if fault == 'type' else b'{}', content))
    before = path.read_bytes()
    with pytest.raises(ContextContractError):
        readiness.prepare_football_context(path, ({'binding_ref': case['case']['payload']['replay_ref']},), config,
            test_blocks=BLOCKS, code_revision='a'*40, created_at=NOW+timedelta(days=10), evaluate=True)
    assert path.read_bytes() == before


def test_unique_physical_payload_excess_is_rejected_before_body_read(tmp_path):
    from context_models.dataset import _reader
    from model_artifacts import _connect
    path = tmp_path/'unique.db'
    con = _connect(path)
    con.executemany('INSERT INTO artifacts VALUES (?, ?, zeroblob(?), ?)',
        [(f'{i:064x}', 'synthetic-physical-admission', 4*1024*1024, canonical_timestamp(NOW)) for i in range(17)])
    con.commit()
    con.close()
    with _reader(path) as con:
        ledger = readiness._PhysicalInputs(con)
        for i in range(16): ledger.admit('artifacts', f'{i:064x}')
        with pytest.raises(ContextContractError, match='preparation_total_byte_bound_exceeded'):
            ledger.admit('artifacts', f'{16:064x}')
        assert ledger.size == 64*1024*1024


def test_shared_chunks_do_not_waive_individual_expanded_original_cap(native_case, tmp_path):
    import shutil
    from model_artifacts import put_artifact
    path = tmp_path/'expanded-bomb.db'
    shutil.copyfile(native_case[0], path)
    ref = native_case[1]['case']['payload']['replay_ref']
    with sqlite3.connect(path) as con:
        binding = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (ref,)).fetchone()[0])
        manifest = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (binding['original_manifest_digest'],)).fetchone()[0])
        body = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (manifest['body']['digest'],)).fetchone()[0])
    clock = NOW+timedelta(seconds=1, microseconds=1)
    chunk = put_artifact(path, kind='football-original-json-chunk-v1', payload={'schema': 1, 'values': ['r'*600000]}, created_at=clock)
    for head in body['goal_provenance']['reference_weights']['heads'].values():
        for component in head['components'].values():
            for term in (component['goals'], component['xg']):
                if term is not None: term['prior_refs']['digest'] = chunk
    manifest['body']['digest'] = put_artifact(path, kind='football-original-body-v1', payload=body, created_at=clock)
    binding['original_manifest_digest'] = put_artifact(path, kind='football-original-storage-manifest-v1', payload=manifest, created_at=clock)
    forged = put_artifact(path, kind='football-original-b1-binding-v1', payload=binding, created_at=clock)
    # This adversarial A1 graph must pass the ORIGINAL storage clock contract
    # so rejection tests occurrence expansion, not generic A1 clock spelling.
    with sqlite3.connect(path) as con:
        con.executemany('UPDATE artifacts SET created_at=? WHERE digest=?', [(canonical_timestamp(clock), digest) for digest in
            (chunk, manifest['body']['digest'], binding['original_manifest_digest'], forged)])
    before = path.read_bytes()
    with pytest.raises(ValueError) as caught:
        readiness.inspect_football_readiness(path, ({'binding_ref': forged},), native_case[2], test_blocks=BLOCKS,
            as_of=NOW+timedelta(days=10))
    causes, error = [], caught.value
    while error is not None:
        causes.append(str(error))
        error = error.__cause__ or error.__context__
    assert any('expanded ORIGINAL exceeds' in cause for cause in causes)
    assert path.read_bytes() == before


@pytest.fixture(scope='module')
def scale_store(tmp_path_factory, native_case):
    """One direct synthetic store with 128 distinct historical native fixtures.

    Every historical fixture appears exactly once in the model input array.
    Their native receipts/chunks remain genuinely shared across 203 targets.
    The 200 final targets have identical kickoff/teams/model inputs; only native
    target ID and capture/decision clocks differ. The owning capture API copies
    that already executed calculation; every subsequent case/evaluator still
    independently reconstructs it through the unmodified mathematical owner.
    """
    import challenge_engine as engine
    import football_original
    from context_models.football_original_publication import FootballOriginalPublication
    from context_sources.football_capture import _Capture
    from context_sources.football import _detail_event, normalize_football_context
    from context_sources.outcomes import normalize_football_base_input, normalize_football_outcome
    from context_training_helpers import detail
    root = tmp_path_factory.mktemp('readiness-scale')
    path = root/'synthetic-scale.db'
    historical = []
    observer = _Capture(path, baseline_enabled=True)
    for index in range(128):
        raw = detail(1000+index, NOW-timedelta(days=128-index), goals=(1+index%3, 1+index%2))
        # Honest partial source: only the two first players have observed match
        # statistics. Other player effects are not selected or imputed. Full
        # native lineups and all distinct fixture/result identities are kept.
        for team in raw['players']:
            team['players'] = team['players'][:1]
        received = NOW-timedelta(days=128-index)+timedelta(hours=3)
        event = _detail_event(raw)
        for record in (normalize_football_base_input(raw, observed_at=received),)+normalize_football_context(
                event, injuries=[], lineups=[], appearances=[raw], observed_at=received):
            append_observation(path, record, observed_at=received)
        observer.record('fixtures', {'id': raw['fixture']['id']},
            {'response': [raw], 'errors': [], 'results': 1, 'paging': {'current': 1, 'total': 1}},
            observed_at=received, status=200)
        historical.append(raw)
    past = historical
    blocks = tuple((NOW+timedelta(days=4, hours=h), NOW+timedelta(days=4, hours=h+2)) for h in (0, 2, 4))
    clocks = [NOW, NOW+timedelta(days=1), NOW+timedelta(days=3)] + [
        blocks[block][0]+timedelta(seconds=i) for block, count in enumerate((67, 67, 66)) for i in range(count)]
    built = NOW+timedelta(days=5)
    refs, captured_lengths, cached = [], [], None
    started = time.monotonic()
    with pytest.MonkeyPatch.context() as patch:
        for index, decision in enumerate(clocks):
            kickoff = decision+timedelta(hours=2) if index < 3 else NOW+timedelta(days=4, hours=8)
            target = detail(9000+index, kickoff, terminal='NS')
            event = _detail_event(target)
            received = decision-timedelta(minutes=30)
            for record in (normalize_football_base_input(target, observed_at=received),)+normalize_football_context(
                    event, injuries=[], lineups=[target], appearances=[], observed_at=received):
                append_observation(path, record, observed_at=received)
            observer.record('fixtures', {'id': 9000+index},
                {'response': [target], 'errors': [], 'results': 1, 'paging': {'current': 1, 'total': 1}},
                observed_at=received, status=200)
            class Clock:
                @staticmethod
                def now(tz=None): return decision+timedelta(seconds=1)
            patch.setattr('context_models.football_original_publication.datetime', Clock)
            patch.setattr(football_original, '_capture_now', lambda: decision)
            publication = FootballOriginalPublication(path, observer, max_publication_payload_bytes=2_000_000,
                max_worker_payload_bytes=2_000_000, max_source_payload_bytes=2_000_000)
            publication.freeze(tuple(past+[target]))
            kwargs = publication.model_kwargs(decision_at=decision)
            if cached is None or index < 4:
                originals = []
                capture = kwargs['original_capture']
                def collect(original):
                    originals.append(original)
                    capture(original)
                model = engine.fixture_market_probabilities(target, past, native_resolver=kwargs['native_resolver'], original_capture=collect)
                original = originals[0]
                if index == 3: cached = (model, original.to_dict())
            else:
                model, template = cached
                kwargs['native_resolver'](tuple(past+[target]))
                original = football_original.capture_football_original(
                    inputs=football_original.football_original_inputs(target, past, None, logical_history_cutoff=kickoff),
                    model=model, raw_probabilities=template['raw_probabilities'], calibration_recipes=template['calibration_recipes'],
                    provenance=template['goal_provenance'], market_specs=engine.MARKET_SPECS,
                    prediction_version=template['prediction_version'], model_contract_signature=template['model_contract_signature'])
                kwargs['original_capture'](original)
            assert publication.report()['events'][0]['source_state'] == 'captured'
            refs.append(publication.report()['events'][0]['binding_ref'])
            captured_lengths.append(len(original._bytes))
            result = normalize_football_outcome(event, detail(9000+index, kickoff), observed_at=kickoff+timedelta(hours=4))
            append_observation(path, result, observed_at=kickoff+timedelta(hours=4))
    config = deepcopy(native_case[2])
    # The partial appearance statistics cannot support full reference-roster
    # features. Select only actual native schedule evidence for this generic
    # streaming/fitting stress; no absent player value becomes numeric zero.
    config.update(feature_names=['schedule.gap_hours_home'], groups={'schedule': ['schedule.gap_hours_home']})
    print({'scale_publication_seconds': round(time.monotonic()-started, 3), 'original_bytes': (min(captured_lengths), max(captured_lengths)),
        'original_expanded_sum': sum(captured_lengths), 'unique_physical_bytes': physical_total(path, refs)})
    return path, tuple({'binding_ref': ref} for ref in refs), config, blocks, built, captured_lengths


def test_203_actual_cases_share_physical_sources_without_raising_caps(scale_store):
    from context_models.dataset import _reader
    from context_models.evaluator import verify_evaluation
    from context_models.training import fit_family
    from context_models.training_cases import assemble_training_cases
    from context_models.football_training import build_joint_training_case
    path, requests, config, blocks, built, lengths = scale_store
    unique = physical_total(path, [item['binding_ref'] for item in requests])
    former = expanded_occurrence_total(path, [item['binding_ref'] for item in requests], lengths)
    assert former > 64*1024*1024 and unique < 64*1024*1024
    report = readiness.inspect_football_readiness(path, requests, config, test_blocks=blocks, as_of=built)
    assert report['inspected_events'] == report['source_complete_events'] == 203
    assert report['test_events'] == 200 and report['input_payload_bytes'] == unique
    assert report['retained_training_payload_bytes'] <= 64*1024*1024
    started = time.monotonic()
    result = readiness.prepare_football_context(path, requests, config, test_blocks=blocks,
        code_revision='a'*40, created_at=built, evaluate=True)
    assert result['status'] == 'evaluated_not_activated' and result['fit_status'] == 'fitted'
    assert len(result['case_refs']) == 203 and result['activated'] is False
    with _reader(path) as con:
        fit = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (result['fit_ref'],)).fetchone()[0])
        dataset = json.loads(con.execute('SELECT payload FROM artifacts WHERE digest=?', (result['dataset_ref'],)).fetchone()[0])
        assert (fit['training_events'], fit['tuning_events']) == (2, 1)
        assert len(dataset['groups'][0]['final_cases']) == 200
        verified = verify_evaluation(con, result['evaluation_ref'])
        assert all(len(rows) == 200 for rows in verified['payload']['distribution_losses'].values())
        assert con.execute('SELECT count(*) FROM active_manifest').fetchone() == (0,)
    training = tuple(build_joint_training_case(path, binding_ref=item['binding_ref'], outcome_ref=next(
        event['outcome_ref'] for event in report['events'] if event['binding_ref'] == item['binding_ref']),
        identity_ref=result['identity_ref'], config=config, as_of=built) for item in requests[:3])
    legacy = fit_family(assemble_training_cases(training, config)['rows'], config, cases=training)
    assert fit == legacy
    print({'scale_prepare_and_verify_seconds': round(time.monotonic()-started, 3), 'unique_physical_bytes': unique,
        'expanded_original_bytes': sum(lengths), 'former_expanded_input_bytes': former,
        'retained_training_payload_bytes': report['retained_training_payload_bytes']})


def test_declared_train_cohort_that_exceeds_retained_cap_is_not_shrunk(scale_store):
    path, requests, config, _, _, _ = scale_store
    config = deepcopy(config)
    config.update(train_end=canonical_timestamp(NOW+timedelta(days=6)), tune_end=canonical_timestamp(NOW+timedelta(days=7)))
    blocks = tuple((NOW+timedelta(days=d), NOW+timedelta(days=d+1)) for d in (7, 8, 9))
    before = path.read_bytes()
    result = readiness.prepare_football_context(path, requests, config, test_blocks=blocks,
        code_revision='a'*40, created_at=NOW+timedelta(days=10))
    assert result['status'] == 'not_ready' and not result['case_refs'] and result['fit_ref'] is None
    assert result['readiness']['retained_training_payload_bytes'] > 64*1024*1024
    assert any(item['reason'] == 'training_retained_byte_bound_exceeded' for item in result['readiness']['events'])
    assert path.read_bytes() == before
