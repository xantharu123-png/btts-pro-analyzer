"""Synthetic unresolved inventory mechanics; no betting-quality claim."""
from datetime import datetime, timedelta
from copy import deepcopy
import importlib
import sqlite3
from time import monotonic

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader
from context_models.football_joint_context import FEATURE_VERSION
from context_training_helpers import NOW
from test_football_joint_worker import original_case, isolated
from test_football_joint_worker import capture_report
from test_football_joint_training import joint_cohort

import football_context_inventory as inventory


@pytest.fixture
def stream_owner():
    return importlib.import_module('context_models.football_source_stream')


@pytest.fixture
def publication_owner():
    return importlib.import_module('context_models.football_original_publication')


@pytest.fixture
def pipeline_owner(stream_owner):
    return {name: importlib.import_module('context_models.'+name)
            for name in ('football_training', 'dataset', 'football_readiness')}


def budget():
    # Explicit SYNTHETIC QA allowances, not proposed production defaults.
    return inventory.HeaderBudget(max_headers=1000000, max_bytes=256*1024**2, seconds=120, phase_seconds=2)


def prepared(isolated, *, later=2, ledger=None):
    return inventory.prepare_inventory(isolated[0], isolated[1]['case']['payload']['replay_ref'],
        decision_at=NOW+timedelta(minutes=later), budget=ledger or budget())


def publish(isolated, payload, monkeypatch, *, ledger=None):
    monkeypatch.setattr(inventory, '_now', lambda: NOW+timedelta(minutes=15))
    return inventory.publish_inventory(isolated[0], payload, remaining=1024, budget=ledger or budget())


def test_separate_unresolved_kind_without_effect_or_body_audit(isolated, monkeypatch, stream_owner):
    monkeypatch.setattr(stream_owner, '_stream_joint_sources_at_cutoff',
        lambda *_a, **_k: pytest.fail('capture must not perform physical source-body audit'))
    payload = prepared(isolated)
    ref, status, size = publish(isolated, payload, monkeypatch)
    assert status == 'captured-unresolved' and 0 < size <= 1024
    with sqlite3.connect(isolated[0]) as connection:
        assert connection.execute('SELECT kind FROM artifacts WHERE digest=?', (ref,)).fetchone() == (inventory.KIND,)
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-effect-v1'").fetchone() == (0,)
        assert connection.execute('SELECT COUNT(*) FROM manifests').fetchone() == (0,)
    assert payload['state'] == 'frozen-unresolved'


def test_complete_physical_resolver_not_hash_only(isolated, monkeypatch, stream_owner):
    payload = prepared(isolated)
    ref, _, _ = publish(isolated, payload, monkeypatch)
    with _reader(isolated[0]) as connection:
        stored, sources = inventory.resolve_inventory_sources(connection, ref,
            latest=NOW+timedelta(minutes=16), feature_version=FEATURE_VERSION, retain_full=True)
    assert stored['payload'] == payload
    assert len(sources['observations']) == payload['observation_count']
    with sqlite3.connect(isolated[0]) as connection:
        # Preserve ALL header columns and hashes but corrupt an actual body.
        connection.execute('UPDATE context_contents SET payload=? WHERE content_digest IN '
            '(SELECT content_digest FROM context_observations LIMIT 1)', (b'{}',))
    with _reader(isolated[0]) as connection, pytest.raises(ContextIntegrityError):
        inventory.resolve_inventory_sources(connection, ref, latest=NOW+timedelta(minutes=16),
            feature_version=FEATURE_VERSION)


def test_actual_new_kind_readiness_case_and_d2_reopen_all_physical_sources(isolated, monkeypatch, pipeline_owner):
    from context_models.training_contracts import validate_resolved_case
    from model_artifacts import put_artifact
    path, prior, config = isolated
    # This synthetic small-roster fixture does not satisfy a player injury
    # feature. Test the transport using its real available schedule feature;
    # never bypass the missing-feature gate or claim a fitted context effect.
    config = deepcopy(config)
    config.update(feature_names=['schedule.gap_hours_home'], groups={'schedule': ['schedule.gap_hours_home']})
    payload = prior['case']['payload']
    freeze = prepared(isolated)
    inventory_ref, _, _ = publish(isolated, freeze, monkeypatch)
    training = pipeline_owner['football_training']
    built = training.build_joint_training_case(path, binding_ref=payload['replay_ref'],
        outcome_ref=payload['outcome_ref'], identity_ref=payload['event_identity_hash'],
        config=config, as_of=NOW+timedelta(hours=6), decision_at=NOW+timedelta(minutes=2),
        source_transport=inventory.SOURCE_TRANSPORT)
    validate_resolved_case(built, config=config)
    assert inventory_ref in built['artifacts']
    assert built['case']['payload']['base']['markets'] == payload['base']['markets']
    blocks = tuple((NOW+timedelta(days=d), NOW+timedelta(days=d+2)) for d in (4, 6, 8))
    report = pipeline_owner['football_readiness'].inspect_football_readiness(path,
        ({'binding_ref': payload['replay_ref'], 'decision_ref': inventory_ref},), config,
        test_blocks=blocks, as_of=NOW+timedelta(days=11), source_transport=inventory.SOURCE_TRANSPORT)
    assert report['source_complete_events'] == 1
    assert report['minimum_test_events'] == 200 and report['empirical_qualification'] == 'not_evaluated'
    created = NOW+timedelta(hours=6, seconds=1)
    case_ref = put_artifact(path, kind=built['case']['kind'], payload=built['case']['payload'], created_at=created)
    item = {'case_ref': case_ref, 'observation_refs': sorted(row['digest'] for row in built['observations'])}
    plan = {'created_at': canonical_timestamp(created+timedelta(seconds=1))}
    with _reader(path) as connection:
        actual = pipeline_owner['dataset'].resolve_case(connection, item, config=config, plan=plan,
            latest=canonical_timestamp(created+timedelta(seconds=1)))
        validate_resolved_case(actual, config=config)
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE context_contents SET payload=? WHERE content_digest IN '
            '(SELECT content_digest FROM context_observations LIMIT 1)', (b'{}',))
    # Case, frozen header hash and all receipt IDs are unchanged. D2 must still
    # open and reject the corrupted real body, not trust its unchanged headers.
    with _reader(path) as connection, pytest.raises(ContextIntegrityError):
        pipeline_owner['dataset'].resolve_case(connection, item, config=config, plan=plan,
            latest=canonical_timestamp(created+timedelta(seconds=1)))


def test_existing_v1_later_decision_remains_legacy(isolated, monkeypatch, pipeline_owner):
    import football_context_decisions as legacy
    from context_models.training_contracts import validate_resolved_case
    path, prior, config = isolated
    config = deepcopy(config)
    config.update(feature_names=['schedule.gap_hours_home'], groups={'schedule': ['schedule.gap_hours_home']})
    payload = prior['case']['payload']
    monkeypatch.setattr(legacy, '_now', lambda: NOW+timedelta(minutes=15))
    report = legacy.publish_capture_decisions(path, capture_report([payload['replay_ref']]),
        decision_at=NOW+timedelta(minutes=2))
    assert report['schema'] == 1 and report['events'][0]['status'] == 'captured'
    built = pipeline_owner['football_training'].build_joint_training_case(path,
        binding_ref=payload['replay_ref'], outcome_ref=payload['outcome_ref'],
        identity_ref=payload['event_identity_hash'], config=config, as_of=NOW+timedelta(hours=6),
        decision_at=NOW+timedelta(minutes=2))
    assert built['case']['payload']['schema'] == 1
    validate_resolved_case(built, config=config)


def test_new_inventory_kind_reaches_public_fit_evaluator_and_physical_d2(joint_cohort, monkeypatch):
    """Existing small synthetic cohort exercises plumbing, never qualification."""
    from context_models.contracts import digest
    from context_models.dataset import resolve_case
    from context_models.evaluator import evaluate_experiment, verify_evaluation
    from context_models.experiments import freeze_experiment
    from context_models.football_training import build_joint_training_case
    from context_models.training import fit_family
    from context_models.training_cases import assemble_training_cases
    from context_models.training_contracts import validate_resolved_case
    from model_artifacts import put_artifact
    db, prior_cases, config, built = deepcopy(joint_cohort)
    config.update(feature_names=['schedule.gap_hours_home'], groups={'schedule': ['schedule.gap_hours_home']})
    cases = []
    for prior in prior_cases:
        original = prior['case']['payload']
        cutoff = datetime.fromisoformat(original['base']['cutoff'])+timedelta(minutes=2)
        frozen = inventory.prepare_inventory(db, original['replay_ref'], decision_at=cutoff, budget=budget())
        monkeypatch.setattr(inventory, '_now', lambda at=cutoff: at+timedelta(minutes=1))
        ref, status, _ = inventory.publish_inventory(db, frozen, remaining=1024, budget=budget())
        assert status == 'captured-unresolved'
        case = build_joint_training_case(db, binding_ref=original['replay_ref'],
            outcome_ref=original['outcome_ref'], identity_ref=original['event_identity_hash'],
            config=config, as_of=built, decision_at=cutoff, source_transport=inventory.SOURCE_TRANSPORT)
        assert case['case']['payload']['schema'] == 2 and ref in case['artifacts']
        assert case['case']['payload']['base']['markets'] == original['base']['markets']
        cases.append(case)
    def store(kind, payload):
        return put_artifact(db, kind=kind, payload=payload, created_at=built)
    def member(case):
        return {'case_ref': case['case']['digest'], 'observation_refs': sorted(row['digest'] for row in case['observations'])}
    for case in cases:
        assert store(case['case']['kind'], case['case']['payload']) == case['case']['digest']
    training = tuple(cases[:3])
    fitted = fit_family(assemble_training_cases(training, config)['rows'], config, cases=training)
    assert fitted['status'] == 'fitted'
    for ref, value in fitted['candidate_artifacts'].items():
        assert store('context-effect-v1', value) == ref
    identity = cases[0]['case']['payload']['event_identity_hash']
    dataset = {'schema': 1, 'event_identity_hash': identity, 'groups': [{
        'family_config_hash': digest(config), 'training_cases': [member(c) for c in training],
        'final_cases': [member(c) for c in cases[3:]], 'unavailable_final': [],
        'fit_ref': store('context-fit-v1', fitted)}]}
    definition = {'family_config_hash': digest(config), 'ablation': 'full',
        'target_markets': config['target_markets'], 'outcome_contract': config['outcome_contract']}
    hypothesis = dict(**definition, hypothesis_id=digest(definition),
        candidate_artifact=fitted['effect_hash'], pretest_status='ready')
    frozen_at = built+timedelta(minutes=1)
    plan = {'schema': 1, 'dataset_hash': store('context-dataset-v1', dataset), 'event_identity_hash': identity,
        'code_revision': 'a'*40, 'base_versions': config['base_versions'], 'family_configs': [config],
        'train_end': config['train_end'], 'tune_end': config['tune_end'],
        'test_blocks': [[canonical_timestamp(NOW+timedelta(days=d)), canonical_timestamp(NOW+timedelta(days=d+2))]
                        for d in (4, 6, 8)], 'target_markets': config['target_markets'],
        'outcome_contracts': [config['outcome_contract']], 'candidate_artifacts': [fitted['effect_hash']],
        'policy_version': 'context-paired-hac-bh-v1', 'availability_classes': ['prospective'],
        'created_at': canonical_timestamp(frozen_at), 'hypotheses': [hypothesis],
        'test_inventory': [{'event': c['case']['payload']['event'], 'decision_at': c['case']['payload']['base']['cutoff'],
                            'block': f'test:{i}'} for i, c in enumerate(cases[3:])]}
    plan_ref = freeze_experiment(db, plan, created_at=frozen_at)
    result = evaluate_experiment(db, plan_ref, evaluated_at=built+timedelta(hours=1))
    hid = hypothesis['hypothesis_id']
    assert len(result['payload']['results'][hid]) == 9
    assert len(result['payload']['distribution_losses'][hid]) == 3
    assert result['payload']['ready_failures'][hid] == [] and result['approvals'] == []
    with _reader(db) as connection:
        validate_resolved_case(resolve_case(connection, member(cases[3]), config=config,
            plan=plan, latest=canonical_timestamp(frozen_at)), config=config)
        assert verify_evaluation(connection, result['digest'])['payload'] == result['payload']
    with sqlite3.connect(db) as connection:
        connection.execute('UPDATE context_contents SET payload=? WHERE content_digest IN '
            '(SELECT content_digest FROM context_observations LIMIT 1)', (b'{}',))
    with _reader(db) as connection, pytest.raises(ContextIntegrityError):
        verify_evaluation(connection, result['digest'])


def test_intervening_predecision_revision_aborts_without_artifact(isolated, monkeypatch):
    payload = prepared(isolated)
    with sqlite3.connect(isolated[0]) as connection:
        connection.execute("UPDATE context_observations SET subject_id='changed' WHERE rowid IN "
                           '(SELECT rowid FROM context_observations LIMIT 1)')
    with pytest.raises(ContextIntegrityError):
        publish(isolated, payload, monkeypatch)
    with sqlite3.connect(isolated[0]) as connection:
        assert connection.execute('SELECT COUNT(*) FROM artifacts WHERE kind=?', (inventory.KIND,)).fetchone() == (0,)


def test_insertion_trigger_header_change_rolls_back(isolated, monkeypatch):
    payload = prepared(isolated)
    with sqlite3.connect(isolated[0]) as connection:
        before = connection.execute('SELECT subject_id FROM context_observations ORDER BY rowid').fetchall()
        connection.execute("CREATE TRIGGER corrupt_header AFTER INSERT ON artifacts WHEN NEW.kind='"+inventory.KIND+
            "' BEGIN UPDATE context_observations SET subject_id='changed' WHERE rowid IN "
            '(SELECT rowid FROM context_observations LIMIT 1); END')
    with pytest.raises(ContextIntegrityError):
        publish(isolated, payload, monkeypatch)
    with sqlite3.connect(isolated[0]) as connection:
        assert connection.execute('SELECT subject_id FROM context_observations ORDER BY rowid').fetchall() == before
        assert connection.execute('SELECT COUNT(*) FROM artifacts WHERE kind=?', (inventory.KIND,)).fetchone() == (0,)


@pytest.mark.parametrize('created', [canonical_timestamp(NOW), canonical_timestamp(NOW+timedelta(days=1))])
def test_trigger_cannot_rewrite_actual_inventory_insert_clock(isolated, monkeypatch, created):
    payload = prepared(isolated)
    with sqlite3.connect(isolated[0]) as connection:
        connection.execute("CREATE TRIGGER corrupt_inventory_clock AFTER INSERT ON artifacts WHEN NEW.kind='"+inventory.KIND+
            "' BEGIN UPDATE artifacts SET created_at='"+created+"' WHERE digest=NEW.digest; END")
    with pytest.raises(ContextIntegrityError):
        publish(isolated, payload, monkeypatch)
    with sqlite3.connect(isolated[0]) as connection:
        assert connection.execute('SELECT COUNT(*) FROM artifacts WHERE kind=?', (inventory.KIND,)).fetchone() == (0,)


def test_locked_existing_database_fails_bounded_without_autoinit(isolated, monkeypatch):
    payload = prepared(isolated)
    with sqlite3.connect(isolated[0], timeout=0) as blocker:
        blocker.execute('BEGIN IMMEDIATE')
        started = monotonic()
        with pytest.raises(inventory.ReplayUnavailable, match='writer_busy'):
            publish(isolated, payload, monkeypatch)
        assert monotonic()-started < 1
        blocker.rollback()


def test_missing_database_is_not_created(isolated, tmp_path):
    payload = prepared(isolated)
    missing = tmp_path/'not-created.db'
    with pytest.raises(ContextIntegrityError):
        inventory.publish_inventory(missing, payload, remaining=1024, budget=budget())
    assert not missing.exists()


def test_first_real_clock_and_zero_byte_reuse(isolated, monkeypatch):
    first = prepared(isolated)
    ref, _, size = publish(isolated, first, monkeypatch)
    later = prepared(isolated, later=4)
    reused, status, spent = inventory.publish_inventory(isolated[0], later, remaining=0, budget=budget())
    assert reused == ref and status == 'reused-unresolved' and spent == 0 and size > 0
    with _reader(isolated[0]) as connection:
        from context_models.dataset import _artifact
        saved = _artifact(connection, ref, inventory.KIND, latest=canonical_timestamp(NOW+timedelta(minutes=16)))
    assert saved['payload']['decision_at'] == canonical_timestamp(NOW+timedelta(minutes=2))


def test_legacy_decision_cap_is_not_changed(isolated):
    from football_context_decisions import validate_decision
    value = prepared(isolated)
    old = {name: value[name] for name in ('binding_ref', 'event_key', 'decision_at',
        'observation_refs_hash', 'observation_count')}
    old.update(schema=1, observation_count=4097)
    with pytest.raises(ContextContractError):
        validate_decision(old)


def test_shared_header_budget_cannot_reset_between_phases():
    ledger = inventory.HeaderBudget(max_headers=2, max_bytes=100, seconds=2, phase_seconds=2)
    with ledger.phase() as check:
        check(2, 70)
    with ledger.phase() as check, pytest.raises(inventory.ReplayUnavailable):
        check(1, 1)


def test_explicit_worker_has_no_source_io_under_shared_mutex(isolated, monkeypatch, publication_owner, record_property):
    owner = publication_owner.FootballOriginalBudget(max_worker_payload_bytes=32768,
        max_source_payload_bytes=0, context_inventory_contract=inventory.KIND)
    real_prepare, real_publish = inventory.prepare_capture_inventories, inventory.publish_deferred_inventories
    def prepare(*args, **kwargs):
        assert not owner.lock.locked()
        return real_prepare(*args, **kwargs)
    def publish(*args, **kwargs):
        assert not owner.lock.locked()
        return real_publish(*args, **kwargs)
    monkeypatch.setattr(inventory, 'prepare_capture_inventories', prepare)
    monkeypatch.setattr(inventory, 'publish_deferred_inventories', publish)
    monkeypatch.setattr(inventory, '_now', lambda: NOW+timedelta(minutes=15))
    owner.defer_context_decisions(isolated[0], capture_report([isolated[1]['case']['payload']['replay_ref']]),
                                 decision_at=NOW+timedelta(minutes=2))
    report = owner.finish_optional_comparisons()
    assert report['events'][0]['status'] == 'captured-unresolved'
    assert inventory.inventory_report_fields({'football_context_decisions': report})
    assert owner.finish_optional_comparisons() == report
    assert owner.remaining_payload_bytes == 32768-report['inserted_payload_bytes']
    record_property('synthetic_max_writer_seconds', report['max_writer_seconds'])


def test_seal_cannot_drop_an_inflight_preparation(isolated, monkeypatch, publication_owner):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    entered, release = Event(), Event()
    owner = publication_owner.FootballOriginalBudget(max_worker_payload_bytes=32768,
        max_source_payload_bytes=0, context_inventory_contract=inventory.KIND)
    real_prepare = inventory.prepare_capture_inventories
    def prepare(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return real_prepare(*args, **kwargs)
    monkeypatch.setattr(inventory, 'prepare_capture_inventories', prepare)
    monkeypatch.setattr(inventory, '_now', lambda: NOW+timedelta(minutes=15))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner.defer_context_decisions, isolated[0],
            capture_report([isolated[1]['case']['payload']['replay_ref']]), decision_at=NOW+timedelta(minutes=2))
        assert entered.wait(10)
        with pytest.raises(ContextContractError, match='join inventory'):
            owner.finish_optional_comparisons()
        assert not owner._sealed
        release.set()
        future.result(timeout=20)
    assert owner.finish_optional_comparisons()['events'][0]['status'] == 'captured-unresolved'


def test_same_revision_out_of_order_preparations_keep_first_actual_clock(isolated, monkeypatch, publication_owner):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    entered, release = Event(), Event()
    owner = publication_owner.FootballOriginalBudget(max_worker_payload_bytes=32768,
        max_source_payload_bytes=0, context_inventory_contract=inventory.KIND)
    real = inventory.prepare_capture_inventories
    def prepare(*args, **kwargs):
        result = real(*args, **kwargs)
        if kwargs['decision_at'] == NOW+timedelta(minutes=2):
            entered.set()
            assert release.wait(10)
        return result
    monkeypatch.setattr(inventory, 'prepare_capture_inventories', prepare)
    report = capture_report([isolated[1]['case']['payload']['replay_ref']])
    with ThreadPoolExecutor(max_workers=1) as pool:
        early = pool.submit(owner.defer_context_decisions, isolated[0], report, decision_at=NOW+timedelta(minutes=2))
        assert entered.wait(10)
        owner.defer_context_decisions(isolated[0], report, decision_at=NOW+timedelta(minutes=4))
        release.set()
        early.result(timeout=20)
    payload = next(iter(owner._decisions.values()))['payload']
    assert payload['decision_at'] == canonical_timestamp(NOW+timedelta(minutes=2))


def test_slower_older_preparation_cannot_replace_newer_weather_revision(isolated, monkeypatch, publication_owner):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    from context_observations import append_observation
    from context_sources.openweather import forecast_payload, normalize_forecast
    entered, release = Event(), Event()
    owner = publication_owner.FootballOriginalBudget(max_worker_payload_bytes=32768,
        max_source_payload_bytes=0, context_inventory_contract=inventory.KIND)
    real = inventory.prepare_capture_inventories
    def prepare(*args, **kwargs):
        result = real(*args, **kwargs)
        if kwargs['decision_at'] == NOW+timedelta(minutes=2):
            entered.set()
            assert release.wait(10)
        return result
    monkeypatch.setattr(inventory, 'prepare_capture_inventories', prepare)
    report = capture_report([isolated[1]['case']['payload']['replay_ref']])
    with ThreadPoolExecutor(max_workers=1) as pool:
        early = pool.submit(owner.defer_context_decisions, isolated[0], report, decision_at=NOW+timedelta(minutes=2))
        assert entered.wait(10)
        event = isolated[1]['case']['payload']['event']
        point = forecast_payload(event, city='Example', country='GB', latitude=50., longitude=0.,
            point={'dt': datetime.fromisoformat(event['scheduled_start']).timestamp(),
                   'main': {'temp': 18.}, 'wind': {'speed': 4.}})
        received = NOW+timedelta(minutes=3)
        append_observation(isolated[0], normalize_forecast(point, observed_at=received), observed_at=received)
        owner.defer_context_decisions(isolated[0], report, decision_at=NOW+timedelta(minutes=4))
        release.set()
        early.result(timeout=20)
    payload = next(iter(owner._decisions.values()))['payload']
    assert payload['decision_at'] == canonical_timestamp(NOW+timedelta(minutes=4))


def test_commit_overrun_keeps_real_bytes_and_debits_before_later_failure(isolated, monkeypatch):
    from contextlib import contextmanager
    real_writer, real_clock = inventory._existing_writer, inventory.monotonic
    delta = [0.0]
    class CommitLatency:
        def __init__(self, connection): self.connection = connection
        def __getattr__(self, name): return getattr(self.connection, name)
        def commit(self):
            self.connection.commit()
            delta[0] += 3.0
    @contextmanager
    def writer(path):
        with real_writer(path) as (connection, check_file):
            yield CommitLatency(connection), check_file
    payload = prepared(isolated)
    monkeypatch.setattr(inventory, '_existing_writer', writer)
    monkeypatch.setattr(inventory, 'monotonic', lambda: real_clock()+delta[0])
    monkeypatch.setattr(inventory, '_now', lambda: NOW+timedelta(minutes=15))
    ledger = budget()
    ref, status, size = inventory.publish_inventory(isolated[0], payload, remaining=1024, budget=ledger)
    assert status == 'captured-unresolved-time-overrun' and size > 0
    assert ledger.max_writer_seconds > 2
    # A fresh phase in this synthetic DB must also debit its committed proof
    # before a later batch-validation error. No production data are involved.
    with sqlite3.connect(isolated[0]) as connection:
        connection.execute('DELETE FROM artifacts WHERE digest=?', (ref,))
    debits = []
    row = {'binding_ref': payload['binding_ref'], 'payload': payload, 'scheduled_start': payload['scheduled_start']}
    with pytest.raises(ContextContractError, match='duplicate deferred'):
        inventory.publish_deferred_inventories(isolated[0], {'events': [row, row], 'unprocessed_events': 0},
            max_run_bytes=2048, budget=budget(), on_commit=debits.append)
    assert debits == [size]
    with sqlite3.connect(isolated[0]) as connection:
        assert connection.execute('SELECT COUNT(*) FROM artifacts WHERE kind=?', (inventory.KIND,)).fetchone() == (1,)


@pytest.mark.parametrize('changes', [dict(schema=True), dict(state='approved'),
    dict(observation_count=True), dict(observation_count=100001), dict(header_bytes=33554433)])
def test_unresolved_closed_contract_rejects_bypass_metadata(isolated, changes):
    payload = prepared(isolated)
    with pytest.raises(ContextContractError):
        inventory.validate_inventory({**payload, **changes})
