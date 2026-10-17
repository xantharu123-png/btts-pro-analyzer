"""Explicit streaming transport, not a relabelled old 512-receipt gate."""
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader
from model_artifacts import canonical_bytes, load_artifact
from test_tennis_training_batch import packet


def api():
    from context_models.tennis_stream import TennisSourceStreamBudget, iter_streamed_tennis_features
    return TennisSourceStreamBudget, iter_streamed_tennis_features


def test_new_stream_matches_every_original_receipt_feature_and_order(tmp_path):
    from context_models.tennis_training import _TennisBatchBudget, iter_live_tennis_features
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origins = tuple(load_artifact(db, ref)['payload']['origin'] for ref in originals[:2])
    with _reader(db) as connection:
        old = [(owner.observation_refs, history, features) for owner, history, features in
            iter_live_tennis_features(connection, origins, budget=_TennisBatchBudget(45))]
    budget = budget_type()
    with _reader(db) as connection:
        new = [(owner.observation_refs, history, features) for owner, history, features in
            streamed(connection, origins, budget=budget)]
    assert canonical_bytes(old) == canonical_bytes(new)
    assert budget.contract == 'tennis-source-stream-v1'
    assert budget.raw_receipts_total == 14
    assert budget.raw_payload_bytes_total > 0
    assert budget.max_chunk_rows <= 512 and budget.max_chunk_payload_bytes <= 2*1024**2


@pytest.mark.parametrize('field', ['raw_case_rows', 'raw_case_bytes', 'raw_total_rows', 'raw_total_bytes'])
def test_raw_admission_rejects_before_any_selected_source_body(tmp_path, monkeypatch, field):
    import tennis.history_projection as projection
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origins = (load_artifact(db, originals[0])['payload']['origin'],)
    budget = budget_type()
    setattr(budget, field, 1)
    monkeypatch.setattr(projection.PreparedTennisHistory, '_from_case_physical_rows',
        lambda *a, **k: pytest.fail('source decoded before raw admission'))
    with _reader(db) as connection, pytest.raises(ValueError, match='raw admission'):
        list(streamed(connection, origins, budget=budget))


def test_invalid_index_is_not_rebuilt_or_used_by_new_transport(tmp_path):
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE tennis_player_index_state SET status='invalid'")
    before = db.read_bytes()
    with _reader(db) as connection, pytest.raises(ValueError, match='not verified ready'):
        list(streamed(connection, (origin,), budget=budget_type()))
    assert db.read_bytes() == before


def test_physical_case_owner_validates_native_source_once_without_selected_redecode(tmp_path, monkeypatch):
    import context_sources.tennis_status as status
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    calls = []
    actual = status._validate_tennis_source_tail
    def checked(row, raw):
        calls.append(row['digest'])
        return actual(row, raw)
    monkeypatch.setattr(status, '_validate_tennis_source_tail', checked)
    with _reader(db) as connection:
        items = list(streamed(connection, (origin,), budget=budget_type()))
    assert len(items) == 1
    assert len(calls) == len(set(calls)) == len(items[0][1])


def test_explicit_training_transport_preserves_the_complete_case_bytes(tmp_path):
    from context_models.tennis_training import build_live_training_cases
    from test_tennis_training_batch import requests_for
    from test_tennis_live_training import live_config
    db, originals, outcomes, identity, at = packet(tmp_path)
    requests = requests_for(originals[:2], outcomes[:2], identity)
    expected = build_live_training_cases(db, requests, config=live_config(), as_of=at)
    actual = build_live_training_cases(db, requests, config=live_config(), as_of=at,
                                      source_transport='tennis-source-stream-v1')
    assert canonical_bytes(expected) == canonical_bytes(actual)


@pytest.mark.parametrize('membership_mode', ['indexed', 'legacy'])
def test_stream_retains_conflicting_and_removed_participant_revisions(tmp_path, membership_mode):
    from context_models.tennis_training import _TennisBatchBudget, iter_live_tennis_features
    from test_tennis_training_batch import revision, NOW
    db, originals, _, _, _ = packet(tmp_path)
    removed = revision(db, '1000', NOW-timedelta(hours=1), (9001, 9002))
    conflict = revision(db, '1000', NOW-timedelta(hours=1), (9003, 9004))
    unrelated = revision(db, '9000', NOW-timedelta(hours=2), (7001, 7002))
    later = revision(db, '9000', NOW+timedelta(hours=2), (100, 7002))
    origin = load_artifact(db, originals[0])['payload']['origin']
    budget_type, streamed = api()
    with _reader(db) as connection:
        old = list(iter_live_tennis_features(connection, (origin,), budget=_TennisBatchBudget(45),
                                            membership_mode=membership_mode))
        new = list(streamed(connection, (origin,), budget=budget_type(), membership_mode=membership_mode))
    assert canonical_bytes(old[0][1:]) == canonical_bytes(new[0][1:])
    refs = set(new[0][0].observation_refs)
    assert refs.issuperset(removed+conflict)
    assert refs.isdisjoint(unrelated+later)


@pytest.mark.parametrize('corruption', ['content_hash', 'outer_identity', 'source_clock', 'membership'])
def test_stream_rejects_real_physical_source_and_membership_corruption(tmp_path, corruption):
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    with sqlite3.connect(db) as connection:
        if corruption == 'membership':
            # Model a malicious metadata row without using the source writer.
            for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'tennis_%'").fetchall():
                connection.execute('DROP TRIGGER '+name)
            connection.execute("UPDATE tennis_player_events SET first_receipt_digest=? WHERE player_id='100'",
                               ('f'*64,))
        elif corruption == 'outer_identity':
            connection.execute("UPDATE context_observations SET subject_id='wrong:identity' WHERE event_key='espn:tennis:ATP:match:1000'")
        elif corruption == 'content_hash':
            connection.execute("UPDATE context_contents SET payload=? WHERE content_digest IN (SELECT content_digest FROM context_observations WHERE event_key='espn:tennis:ATP:match:1000')", (b'{}',))
        else:
            connection.execute("UPDATE context_observations SET observed_at='2026-09-09T10:00:00Z' WHERE event_key='espn:tennis:ATP:match:1000'")
    with _reader(db) as connection, pytest.raises((ValueError, ContextIntegrityError)):
        list(streamed(connection, (origin,), budget=budget_type(),
                      membership_mode='indexed' if corruption == 'membership' else 'legacy'))


def test_legacy_discovery_hash_binds_an_association_that_a_corruption_removed(tmp_path):
    import json
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    with sqlite3.connect(db) as connection:
        for ref, body in connection.execute("SELECT content_digest,payload FROM context_contents WHERE content_digest IN (SELECT content_digest FROM context_observations WHERE event_key='espn:tennis:ATP:match:1000')").fetchall():
            row = json.loads(body)
            if row['kind'] == 'event_status':
                row['payload']['participant_ids'] = ['9001', '9002']
            else:
                row['payload']['player_id'], row['payload']['opponent_id'] = '9001', '9002'
            connection.execute('UPDATE context_contents SET payload=? WHERE content_digest=?',
                               (canonical_bytes(row), ref))
    with _reader(db) as connection, pytest.raises(ContextIntegrityError):
        list(streamed(connection, (origin,), budget=budget_type(), membership_mode='legacy'))


def test_global_negative_proof_checks_a_rehashed_removed_membership_receipt(tmp_path):
    import hashlib
    import json
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    with sqlite3.connect(db) as connection:
        ref, body = connection.execute("SELECT content_digest,payload FROM context_contents WHERE content_digest IN (SELECT content_digest FROM context_observations WHERE event_key='espn:tennis:ATP:match:1000') LIMIT 1").fetchone()
        row = json.loads(body)
        if row['kind'] == 'event_status':
            row['payload']['participant_ids'] = ['espn:tennis:ATP:player:9001', 'espn:tennis:ATP:player:9002']
        else:
            row['payload']['player_id'], row['payload']['opponent_id'] = 'espn:tennis:ATP:player:9001', 'espn:tennis:ATP:player:9002'
        changed = canonical_bytes(row)
        changed_ref = hashlib.sha256(changed).hexdigest()
        connection.execute('INSERT INTO context_contents VALUES (?,?)', (changed_ref, changed))
        # Content's own SHA is now consistent; its old actual receipt and
        # native source fields are not. A metadata-only guard would miss it.
        connection.execute('UPDATE context_observations SET content_digest=? WHERE content_digest=?',
                           (changed_ref, ref))
    with _reader(db) as connection, pytest.raises(ContextIntegrityError):
        list(streamed(connection, (origin,), budget=budget_type(), membership_mode='legacy'))


@pytest.mark.parametrize('corruption', ['missing_content', 'nul_prefixed_text'])
def test_global_physical_admission_rejects_missing_or_text_body_before_selecting_it(tmp_path, monkeypatch, corruption):
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    with sqlite3.connect(db) as connection:
        ref, = connection.execute("SELECT content_digest FROM context_observations WHERE event_key='espn:tennis:ATP:match:1000' LIMIT 1").fetchone()
        if corruption == 'missing_content':
            connection.execute('DELETE FROM context_contents WHERE content_digest=?', (ref,))
        else:
            connection.execute('UPDATE context_contents SET payload=? WHERE content_digest=?',
                               ('\x00'+'x'*(2*1024**2+1), ref))
    queries = []
    monkeypatch.setattr('tennis.history_projection.PreparedTennisHistory._from_physical_case_batch',
                        lambda *a, **k: pytest.fail('physical body selected before raw storage admission'))
    with _reader(db) as connection, pytest.raises(ValueError, match='work row exceeds chunk admission'):
        connection.set_trace_callback(queries.append)
        list(streamed(connection, (origin,), budget=budget_type(), membership_mode='legacy'))
    assert not any('SELECT r.digest' in query for query in queries)


def test_same_native_numeric_ids_on_other_tour_do_not_create_membership(tmp_path):
    from test_tennis_training_batch import revision, NOW
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    foreign = revision(db, '1000', NOW-timedelta(hours=1), (100, 101), tour='WTA')
    origin = load_artifact(db, originals[0])['payload']['origin']
    with _reader(db) as connection:
        actual, = list(streamed(connection, (origin,), budget=budget_type(), membership_mode='legacy'))
    assert set(actual[0].observation_refs).isdisjoint(foreign)


@pytest.mark.parametrize('field', ['raw_case_rows', 'raw_case_bytes', 'raw_total_rows', 'raw_total_bytes',
                                  'chunk_rows', 'chunk_bytes', 'limit'])
def test_diagnostic_limits_cannot_enlarge_the_new_contract(field):
    budget_type, _ = api()
    budget = budget_type()
    setattr(budget, field, getattr(budget, field)+1)
    with pytest.raises(ValueError, match='only tighten'):
        budget.check()


def test_stream_deadline_and_retention_are_enforced_before_body_decode(tmp_path, monkeypatch):
    import context_models.tennis_stream as implementation
    budget_type, streamed = api()
    db, originals, _, _, _ = packet(tmp_path)
    origin = load_artifact(db, originals[0])['payload']['origin']
    monkeypatch.setattr('tennis.history_projection.PreparedTennisHistory._from_case_physical_rows',
                        lambda *a, **k: pytest.fail('body opened after failed retention admission'))
    budget = budget_type()
    budget.limit = 1024
    with _reader(db) as connection, pytest.raises(ValueError, match='retained byte'):
        list(streamed(connection, (origin,), budget=budget))
    clock = [0.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    budget = budget_type(seconds=1)
    clock[0] = 2.
    with pytest.raises(TimeoutError):
        budget.check()
