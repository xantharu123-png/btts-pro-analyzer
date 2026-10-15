"""Actual indexed readers: causal equivalence, fail-closed state and release order."""
from contextlib import contextmanager
from datetime import timedelta
import importlib
from pathlib import Path
import sqlite3

import pytest

from context_models import dataset, readiness, tennis_training as training
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_tennis_index import IndexBudgetExceeded, TennisIndexUnavailable
import context_tennis_index_build as builder
from model_artifacts import canonical_bytes, load_artifact
from test_tennis_live_training import packet, live_config
from test_tennis_live_worker import NOW
from test_tennis_training_batch import requests_for, revision


def indexed(path):
    builder.initialize_index(path)
    assert builder.build_index(path).status == 'ready'


def origins(path, originals):
    return tuple(load_artifact(path, ref)['payload']['origin'] for ref in originals)


def test_indexed_batch_matches_single_case_bytes_and_digests(tmp_path):
    db, originals, outcomes, identity, at = packet(tmp_path)
    revision(db, '1000', NOW-timedelta(hours=1), (9001, 9002))
    revision(db, '1000', NOW-timedelta(hours=1), (9003, 9004))
    indexed(db)
    requests = requests_for(originals, outcomes, identity)
    single = tuple(training.build_live_training_case(db, **r, config=live_config(), as_of=at) for r in requests)
    before = db.read_bytes()
    actual = training.build_live_training_cases(db, requests, config=live_config(), as_of=at,
                                               membership_mode='indexed')
    assert canonical_bytes(actual) == canonical_bytes(single)
    assert [c['case']['digest'] for c in actual] == [c['case']['digest'] for c in single]
    assert db.read_bytes() == before


def test_two_cutoffs_admit_exactly_7_and_13_receipts(tmp_path, monkeypatch):
    db, originals, outcomes, identity, at = packet(tmp_path)
    old = revision(db, '9000', NOW-timedelta(hours=2), (7001, 7002))
    associated = revision(db, '9000', NOW+timedelta(hours=2), (100, 110))
    indexed(db)
    counts = []
    admit = training._TennisBatchBudget.admit_selected
    def counted(self, count, size):
        counts.append(count)
        return admit(self, count, size)
    monkeypatch.setattr(training._TennisBatchBudget, 'admit_selected', counted)
    cases = training.build_live_training_cases(db, requests_for(originals[:2], outcomes[:2], identity),
                                               config=live_config(), as_of=at)
    assert counts == [7, 13]
    refs = [{r['digest'] for r in c['observations']} for c in cases]
    assert refs[0].isdisjoint(old+associated)
    assert refs[1].issuperset(old+associated)


def strict_reader(path, *, queries):
    @contextmanager
    def held(path):
        with dataset._reader(path) as connection:
            allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                       sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_RECURSIVE}
            connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
            connection.set_trace_callback(queries.append)
            yield connection
            assert connection.in_transaction
            assert connection.total_changes == 0
    return held(path)


def test_readiness_uses_index_in_its_held_snapshot(tmp_path, monkeypatch):
    db, originals, _, _, at = packet(tmp_path)
    indexed(db)
    queries = []
    monkeypatch.setattr(readiness, '_reader', lambda path: strict_reader(path, queries=queries))
    report = readiness.audit_tennis_readiness(db, as_of=at, all_features=True, event_count=2)
    assert [r['original_ref'] for r in report['sample']] == originals[:2]
    assert [r['references'] for r in report['sample']] == [7, 7]
    assert any('FROM main.tennis_player_events' in q for q in queries)
    assert not any('json_extract' in q or 'receipt_candidates' in q for q in queries)


def test_actual_feature_reader_under_strict_authorizer_never_discovers_json_or_labels(tmp_path):
    db, originals, _, _, _ = packet(tmp_path)
    indexed(db)
    frozen = origins(db, originals[:2])
    queries = []
    with strict_reader(db, queries=queries) as connection:
        rows = list(training.iter_live_tennis_features(connection, frozen, budget=training._TennisBatchBudget(45)))
    assert [len(history) for _, history, _ in rows] == [7, 7]
    assert any('FROM main.tennis_player_events' in q for q in queries)
    assert not any('json_' in q or 'PRAGMA' in q or "kind='match_outcome'" in q for q in queries)
    assert all(r['kind'] != 'match_outcome' for _, history, _ in rows for r in history)


@pytest.mark.parametrize('limit', ['count', 'bytes'])
def test_real_membership_proof_decoder_waits_for_complete_case_admission(tmp_path, monkeypatch, limit):
    """Proofs, not merely the history decoder alias, must wait for admission."""
    import context_observations
    db, originals, _, _, _ = packet(tmp_path)
    indexed(db)
    frozen = origins(db, originals[:1])
    def forbidden(raw):
        raise AssertionError('membership proof body decoded before complete case admission')
    monkeypatch.setattr(context_observations, '_decode_receipt', forbidden)
    budget = training._TennisBatchBudget(45, **({'selected_count': 6} if limit == 'count'
                                               else {'selected_bytes_per_case': 1}))
    with dataset._reader(db) as connection, pytest.raises(ValueError, match='budget'):
        list(training.iter_live_tennis_features(connection, frozen, budget=budget))


@pytest.mark.parametrize('damage', ['missing', 'dirty', 'replaced', 'generation', 'projector', 'schema', 'version', 'receipt'])
def test_missing_dirty_or_replaced_index_never_returns_empty_success(tmp_path, damage):
    db, originals, outcomes, identity, at = packet(tmp_path)
    if damage != 'missing':
        indexed(db)
        with sqlite3.connect(db) as connection:
            if damage == 'dirty':
                connection.execute("UPDATE tennis_player_index_state SET status='invalid'")
            elif damage == 'generation':
                connection.execute('UPDATE tennis_player_index_state SET source_generation=source_generation+1')
            elif damage == 'projector':
                connection.execute("UPDATE tennis_player_index_state SET projector_sha256=?", ('0'*64,))
            elif damage == 'version':
                connection.execute('UPDATE tennis_player_index_state SET schema_version=2')
            elif damage == 'schema':
                connection.execute('DROP TRIGGER tennis_player_index_observations_insert')
            elif damage == 'receipt':
                connection.execute("UPDATE tennis_player_events SET first_receipt_digest=?", ('0'*64,))
                connection.execute("UPDATE tennis_player_index_state SET status='ready',verified_index_generation=index_generation")
        if damage == 'replaced':
            copy = db.with_name('replacement.db')
            copy.write_bytes(db.read_bytes())
            db = copy
    with pytest.raises((TennisIndexUnavailable, ContextIntegrityError)):
        training.build_live_training_cases(db, requests_for(originals[:1], outcomes[:1], identity),
                                           config=live_config(), as_of=at)


def test_fresh_reader_refuses_legacy_write(tmp_path):
    db, originals, outcomes, identity, at = packet(tmp_path)
    indexed(db)
    revision(db, '9000', NOW-timedelta(hours=2), (100, 7002))
    # Simulate a legacy SQL writer, which cannot publish a verified generation.
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE context_observations SET subject_id=subject_id WHERE rowid=(SELECT MIN(rowid) FROM context_observations)")
    with pytest.raises(TennisIndexUnavailable):
        training.build_live_training_cases(db, requests_for(originals[:1], outcomes[:1], identity),
                                           config=live_config(), as_of=at)


def test_inventory_only_never_needs_index(tmp_path):
    db, _, _, _, at = packet(tmp_path)
    assert readiness.audit_tennis_readiness(db, as_of=at, inventory_only=True)['sample'] == []


@pytest.mark.parametrize('mode', ['auto', '', None, 1])
def test_membership_mode_is_explicit_before_open(tmp_path, mode):
    with pytest.raises(ValueError, match='membership_mode'):
        readiness.audit_tennis_readiness(tmp_path/'missing', as_of=NOW, membership_mode=mode)
    with pytest.raises(ValueError, match='membership_mode'):
        training.build_live_training_cases(tmp_path/'missing', (), config=live_config(), as_of=NOW, membership_mode=mode)
    with pytest.raises(ValueError, match='membership_mode'):
        list(training.iter_live_tennis_features(None, (), budget=training._TennisBatchBudget(45), membership_mode=mode))


@pytest.fixture(scope='module')
def evaluation_proof(tmp_path_factory):
    from context_models.evaluator import evaluate_experiment
    from context_dataset_helpers import stored_packet, EVALUATED
    fixture = stored_packet(tmp_path_factory.mktemp('indexed-evaluation-proof'))
    report = evaluate_experiment(fixture['path'], fixture['experiment_ref'], evaluated_at=EVALUATED)
    return fixture, report


@pytest.mark.parametrize('owner', ['context_tennis_index.py', 'context_tennis_index_build.py', 'context_observations.py', 'context_runtime.py'])
def test_index_owner_hash_is_bound_to_real_evaluation(evaluation_proof, monkeypatch, owner):
    from context_models.evaluator import verify_evaluation
    fixture, report = evaluation_proof
    read = Path.read_bytes
    def changed(path):
        raw = read(path)
        return raw+b'\n# changed owner\n' if path.name == owner else raw
    monkeypatch.setattr(Path, 'read_bytes', changed)
    with dataset._reader(fixture['path']) as connection, pytest.raises(ContextIntegrityError, match='exact original source proof'):
        verify_evaluation(connection, report['digest'])


def test_non_index_reader_keeps_original_read_only_contract(tmp_path):
    db, _, _, _, _ = packet(tmp_path)
    queries = []
    with strict_reader(db, queries=queries) as connection:
        assert connection.execute('SELECT COUNT(*) FROM context_observations').fetchone()[0] > 0


def test_release_order_and_disable_keep_originals_usable(tmp_path, monkeypatch):
    db, originals, outcomes, identity, at = packet(tmp_path)
    def source_rows():
        with sqlite3.connect(db) as connection:
            return tuple(connection.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall()
                         for table in ('context_contents', 'context_observations', 'artifacts'))
    before = source_rows()
    for name in ('context_tennis_index', 'context_tennis_index_build', 'context_models.tennis_training'):
        importlib.import_module(name)
    with sqlite3.connect(db) as connection:
        assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name='tennis_player_events'").fetchall()
    request = requests_for(originals[:1], outcomes[:1], identity)
    legacy = training.build_live_training_cases(db, request, config=live_config(), as_of=at, membership_mode='legacy')
    builder.initialize_index(db)
    upsert = builder._upsert_membership
    def interrupted(*args):
        upsert(*args)
        raise IndexBudgetExceeded('bounded interruption')
    monkeypatch.setattr(builder, '_upsert_membership', interrupted)
    assert builder.build_index(db).status != 'ready'
    with pytest.raises(TennisIndexUnavailable):
        training.build_live_training_cases(db, request, config=live_config(), as_of=at)
    monkeypatch.setattr(builder, '_upsert_membership', upsert)
    assert builder.build_index(db).status == 'ready'
    actual = training.build_live_training_cases(db, request, config=live_config(), as_of=at)
    assert canonical_bytes(actual) == canonical_bytes(legacy)
    with strict_reader(db, queries=[]) as connection:
        assert len(list(training.iter_live_tennis_features(connection, origins(db, originals[:1]),
                   budget=training._TennisBatchBudget(45)))) == 1
    builder.disable_index(db)
    with sqlite3.connect(db) as connection:
        assert connection.execute('SELECT status FROM tennis_player_index_state').fetchone() == ('invalid',)
    with pytest.raises(TennisIndexUnavailable):
        training.build_live_training_cases(db, request, config=live_config(), as_of=at)
    assert canonical_bytes(training.build_live_training_cases(db, request, config=live_config(), as_of=at,
                           membership_mode='legacy')) == canonical_bytes(legacy)
    assert source_rows() == before
