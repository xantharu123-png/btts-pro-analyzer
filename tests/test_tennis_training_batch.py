"""Real SQLite batch contracts; legacy single selection remains the oracle."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader
from context_models import tennis_training as impl
from context_observations import append_observation
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import canonical_bytes, load_artifact
from test_tennis_live_training import packet, live_config
from test_tennis_live_worker import NOW
from test_context_tennis_outcome_capture import completed


def batch_api():
    function = getattr(impl, 'build_live_training_cases', None)
    assert callable(function), 'missing same-transaction live training batch'
    return function


def requests_for(originals, outcomes, identity):
    return tuple(dict(original_ref=a, outcome_ref=b, identity_ref=identity)
                 for a, b in zip(originals, outcomes))


def revision(db, event_id, at, players, *, tour='ATP'):
    raw = completed(event_id=event_id)
    raw['date'] = canonical_timestamp(NOW-timedelta(hours=52))
    for side, player in enumerate(raw['competitors']):
        player['id'] = str(players[side])
    refs = []
    for row in normalize_tennis_status(tour, '189-2026', raw,
            grouping_slug='mens-singles' if tour == 'ATP' else 'womens-singles', observed_at=at):
        refs.append(append_observation(db, row, observed_at=at))
    return refs


def test_batch_preserves_case_bytes_and_digests_from_single_reader_path(tmp_path):
    build = batch_api()
    db, originals, outcomes, identity, at = packet(tmp_path)
    requests = requests_for(originals, outcomes, identity)
    expected = tuple(impl.build_live_training_case(db, **request, config=live_config(), as_of=at)
                     for request in requests)
    before = db.read_bytes()
    actual = build(db, requests, config=live_config(), as_of=at)
    assert type(actual) is tuple
    assert canonical_bytes(actual) == canonical_bytes(expected)
    assert [r['case']['digest'] for r in actual] == [r['case']['digest'] for r in expected]
    assert len(actual[0]['observations']) == 8  # seven native receipts + its outcome
    assert db.read_bytes() == before


def test_discovery_keeps_all_admitted_revisions_without_future_association(tmp_path):
    build = batch_api()
    db, originals, outcomes, identity, at = packet(tmp_path)
    # Key 9000 only joins player 100 after case zero, despite older unrelated rows.
    old = revision(db, '9000', NOW-timedelta(hours=2), (7001, 7002))
    future = revision(db, '9000', NOW+timedelta(hours=2), (100, 7002))
    # Event 1000 already belonged to player 100: later removal must be retained.
    removed = revision(db, '1000', NOW-timedelta(hours=1), (9001, 9002))
    conflict = revision(db, '1000', NOW-timedelta(hours=1), (9003, 9004))
    revision(db, '1000', NOW-timedelta(hours=1), (100, 101), tour='WTA')
    request = requests_for(originals[:1], outcomes[:1], identity)
    actual, = build(db, request, config=live_config(), as_of=at)
    expected = impl.build_live_training_case(db, **request[0], config=live_config(), as_of=at)
    refs = {r['digest'] for r in actual['observations']}
    assert refs.issuperset(removed+conflict)
    assert refs.isdisjoint(old+future)
    assert canonical_bytes(actual) == canonical_bytes(expected)


def test_two_cutoff_batch_discovers_between_case_association_but_keeps_earlier_pool_causal(tmp_path, monkeypatch):
    """Removing only per-case first_seen filtering must break the early pool."""
    build = batch_api()
    db, originals, outcomes, identity, at = packet(tmp_path)
    old = revision(db, '9000', NOW-timedelta(hours=2), (7001, 7002))
    associated = revision(db, '9000', NOW+timedelta(hours=2), (100, 110))
    requests = requests_for(originals[:2], outcomes[:2], identity)
    expected = tuple(impl.build_live_training_case(db, **request, config=live_config(), as_of=at)
                     for request in requests)
    admitted_counts = []
    original_admit = impl._TennisBatchBudget.admit_selected
    def admitted(budget, count, payload_bytes):
        admitted_counts.append(count)
        return original_admit(budget, count, payload_bytes)
    monkeypatch.setattr(impl._TennisBatchBudget, 'admit_selected', admitted)
    actual = build(db, requests, config=live_config(), as_of=at)
    assert [case['case']['payload']['base']['cutoff'] for case in actual] == [
        '2026-09-09T12:00:00.000000Z', '2026-09-10T12:00:00.000000Z']
    early_refs, later_refs = ({r['digest'] for r in case['observations']} for case in actual)
    assert early_refs.isdisjoint(old+associated)
    assert later_refs.issuperset(old+associated)
    assert [len(case['observations']) for case in actual] == [8, 14]
    assert admitted_counts == [7, 13]  # no unrelated bodies admitted for the early decision
    assert canonical_bytes(actual) == canonical_bytes(expected)
    assert [case['case']['digest'] for case in actual] == [case['case']['digest'] for case in expected]


def test_actual_batch_discovery_extracts_one_small_projection_after_native_prefilter(tmp_path):
    db, originals, _, _, _ = packet(tmp_path)
    origins = tuple(load_artifact(db, ref)['payload']['origin'] for ref in originals[:2])
    sql = []
    with _reader(db) as conn:
        conn.set_trace_callback(sql.append)
        rows = list(impl.iter_live_tennis_features(conn, origins, budget=impl._TennisBatchBudget(45)))
    assert [len(history) for _, history, _ in rows] == [7, 7]
    discovery, = [query for query in sql if 'WITH receipt_candidates' in query]
    assert discovery.count('json_extract(') == 1
    assert discovery.index("source='espn'") < discovery.index('json_extract(')
    assert discovery.index("kind IN ('event_status','workload')") < discovery.index('json_extract(')


@pytest.mark.parametrize('requests', [(), [], iter(()), [None], [{}], [{}]*101])
def test_batch_rejects_invalid_explicit_inventory_before_database_access(tmp_path, requests):
    with pytest.raises((ValueError, TypeError)):
        batch_api()(tmp_path/'missing', requests, config=live_config(), as_of=NOW)
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('seconds', [True, 0, 601, float('nan'), float('inf')])
def test_batch_rejects_nonfinite_or_unbounded_budget_before_database_access(tmp_path, seconds):
    with pytest.raises(ValueError):
        batch_api()(tmp_path/'missing', ({'original_ref':'a'*64, 'outcome_ref':'b'*64,
                    'identity_ref':'c'*64},), config=live_config(), as_of=NOW, seconds=seconds)


@pytest.mark.parametrize('corruption', ['missing_content', 'outer_identity'])
def test_batch_checks_all_selected_physical_revisions(tmp_path, corruption):
    build = batch_api()
    db, originals, outcomes, identity, at = packet(tmp_path)
    with sqlite3.connect(db) as conn:
        if corruption == 'missing_content':
            conn.execute("DELETE FROM context_contents WHERE content_digest IN (SELECT content_digest FROM context_observations WHERE event_key='espn:tennis:ATP:match:200')")
        else:
            conn.execute("UPDATE context_observations SET subject_id='wrong:identity' WHERE event_key='espn:tennis:ATP:match:1000'")
    with pytest.raises(ContextIntegrityError):
        build(db, requests_for(originals[:1], outcomes[:1], identity), config=live_config(), as_of=at)


def test_feature_batch_discovers_once_in_same_transaction_and_never_opens_outcomes(tmp_path):
    function = getattr(impl, 'iter_live_tennis_features', None)
    assert callable(function), 'missing actual shared readiness feature consumer'
    db, originals, _, _, _ = packet(tmp_path)
    origins = tuple(load_artifact(db, ref)['payload']['origin'] for ref in originals[:2])
    sql = []
    with _reader(db) as conn:
        conn.set_trace_callback(sql.append)
        actual = list(function(conn, origins, budget=impl._TennisBatchBudget(45),
                               feature_version='tennis-performed-load-v3'))
        assert conn.in_transaction
    assert len(actual) == 2
    assert [len(history) for _, history, _ in actual] == [7, 7]
    assert all(r['kind'] != 'match_outcome' for _, history, _ in actual for r in history)
    assert len([q for q in sql if 'WITH receipt_candidates' in q]) == 1
    assert not any("r.kind='match_outcome'" in q for q in sql)


def test_batch_combines_lookup_and_selected_history_admission_and_recovers_after_abort(tmp_path, monkeypatch):
    build = batch_api()
    import context_runtime
    db, originals, outcomes, identity, at = packet(tmp_path)
    requests = requests_for(originals[:2], outcomes[:2], identity)
    original_limit = context_runtime.MAX_TENNIS_HISTORY_BYTES
    monkeypatch.setattr(context_runtime, 'MAX_TENNIS_HISTORY_BYTES', 1024)
    with pytest.raises((ValueError, ContextIntegrityError), match='byte|retention|budget'):
        build(db, requests, config=live_config(), as_of=at)
    monkeypatch.setattr(context_runtime, 'MAX_TENNIS_HISTORY_BYTES', original_limit)
    assert len(build(db, requests, config=live_config(), as_of=at)) == 2


def test_batch_deadline_includes_original_preparation_and_returns_no_partial_pool(tmp_path, monkeypatch):
    build = batch_api()
    db, originals, outcomes, identity, at = packet(tmp_path)
    import context_models.dataset as dataset
    time = [0.]
    original = dataset._artifact
    def slow(*args, **kwargs):
        value = original(*args, **kwargs)
        time[0] = 2.
        return value
    monkeypatch.setattr(impl, 'monotonic', lambda: time[0])
    monkeypatch.setattr(dataset, '_artifact', slow)
    with pytest.raises(TimeoutError):
        build(db, requests_for(originals[:2], outcomes[:2], identity),
              config=live_config(), as_of=at, seconds=1)


def test_exact_evaluation_source_proof_detects_prepared_history_owner_change(tmp_path, monkeypatch):
    """A real persisted report must stop verifying after this owner changes."""
    from pathlib import Path
    from context_models.evaluator import evaluate_experiment, verify_evaluation
    from context_dataset_helpers import stored_packet, EVALUATED
    fixture = stored_packet(tmp_path)
    report = evaluate_experiment(fixture['path'], fixture['experiment_ref'], evaluated_at=EVALUATED)
    actual_read = Path.read_bytes
    def changed_owner(path):
        raw = actual_read(path)
        if path.as_posix().endswith('/tennis/history_projection.py'):
            return raw+b'\n# independently changed source owner\n'
        return raw
    monkeypatch.setattr(Path, 'read_bytes', changed_owner)
    with _reader(fixture['path']) as connection, pytest.raises(ContextIntegrityError, match='exact original source proof'):
        verify_evaluation(connection, report['digest'])


@pytest.mark.parametrize('limit', ['count', 'bytes'])
def test_lower_diagnostic_admission_rejects_before_any_selected_body_decode(tmp_path, monkeypatch, limit):
    function = getattr(impl, 'iter_live_tennis_features', None)
    assert callable(function), 'missing actual feature batch'
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    def forbidden(*args):
        raise AssertionError('selected body decoded before finite admission')
    monkeypatch.setattr(impl, '_decode_receipt', forbidden)
    budget = impl._TennisBatchBudget(45, **({'selected_count': 6} if limit == 'count'
                                           else {'selected_bytes_per_case': 1}))
    with _reader(db) as conn, pytest.raises(ValueError, match='budget'):
        list(function(conn, (origin,), budget=budget))


def test_shared_payload_limit_is_not_renewed_for_later_cases(tmp_path, monkeypatch):
    function = getattr(impl, 'iter_live_tennis_features', None)
    assert callable(function), 'missing actual feature batch'
    db, originals, _, _, _ = packet(tmp_path)
    origins = tuple(load_artifact(db, ref)['payload']['origin'] for ref in originals[:2])
    # First consume one actual case to obtain its physical payload accounting.
    first_budget = impl._TennisBatchBudget(45)
    with _reader(db) as conn:
        list(function(conn, origins[:1], budget=first_budget))
    calls = []
    actual = impl._decode_receipt
    def counted(raw):
        calls.append(raw[0])
        return actual(raw)
    monkeypatch.setattr(impl, '_decode_receipt', counted)
    budget = impl._TennisBatchBudget(45, selected_bytes_total=first_budget.selected_payload_bytes)
    with _reader(db) as conn, pytest.raises(ValueError, match='budget'):
        list(function(conn, origins, budget=budget))
    assert len(calls) == 7  # case two is rejected before any body decoding
