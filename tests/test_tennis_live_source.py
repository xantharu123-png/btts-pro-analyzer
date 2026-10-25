"""Exact source/original parity, finite live ownership and lifetime checks."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

import pytest

from context_models import tennis_live_source as implementation

from context_models.dataset import _reader
from context_models.tennis_training import _TennisBatchBudget, iter_live_tennis_features
from context_models.tennis_v4 import live_tennis_features
from context_models.tennis_live import original_base
from model_artifacts import canonical_bytes, load_artifact
from test_tennis_training_batch import packet, revision, NOW


def origins_at(db, refs):
    return tuple(load_artifact(db, ref)['payload']['origin'] for ref in refs)


def consume(db, origins, budget):
    cases = tuple((origin['event'], origin['cutoff']) for origin in origins)
    result = []
    with implementation.open_live_sources(db, cases, budget) as (_, sources):
        for origin, owner in zip(origins, sources.histories(), strict=True):
            with owner.feature_scope(origin['event']) as rows:
                features = live_tennis_features('tennis-performed-load-v4', origin['event'], rows,
                    original_base(origin), cutoff=datetime.fromisoformat(origin['cutoff']))
                value = (owner.observation_refs, rows, features)
                budget.keep_prepared(value)
                result.append(value)
    return result


def test_actual_physical_history_and_features_equal_existing_indexed_oracle(tmp_path):
    db, refs, _, _, _ = packet(tmp_path)
    origins = origins_at(db, refs[:2])
    with _reader(db) as connection:
        old = [(owner.observation_refs, rows, features) for owner, rows, features in
            iter_live_tennis_features(connection, origins, budget=_TennisBatchBudget())]
    budget = implementation.LiveTennisReadBudget()
    actual = consume(db, origins, budget)
    assert canonical_bytes(actual) == canonical_bytes(old)
    assert budget.completed_cases == 2 and budget.actual_rows == budget.admitted_rows == 14
    assert budget.contract == 'tennis-live-indexed-source-v1'


def test_later_case_limit_rejects_before_any_source_body(tmp_path, monkeypatch):
    db, refs, _, _, _ = packet(tmp_path)
    origins = origins_at(db, refs[:2])
    budget = implementation.LiveTennisReadBudget()
    budget.raw_row_limit = 8
    monkeypatch.setattr(implementation.PreparedTennisHistory, '_from_case_physical_rows',
                        lambda *a, **k: pytest.fail('body before complete metadata admission'))
    with pytest.raises(ValueError, match='cumulative raw admission'):
        consume(db, origins, budget)


def test_index_invalidity_has_no_fallback_or_write(tmp_path):
    db, refs, _, _, _ = packet(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE tennis_player_index_state SET status='invalid'")
    before = db.read_bytes()
    with pytest.raises(ValueError, match='not verified ready'):
        consume(db, origins_at(db, refs[:1]), implementation.LiveTennisReadBudget())
    assert db.read_bytes() == before


@pytest.mark.parametrize('mutation', ['update', 'delete', 'replace'])
def test_actual_source_mutation_invalidates_ready_index_without_fallback(tmp_path, mutation):
    db, refs, _, _, _ = packet(tmp_path)
    origins = origins_at(db, refs[:1])
    with sqlite3.connect(db) as connection:
        ref, = connection.execute('SELECT content_digest FROM context_observations LIMIT 1').fetchone()
        if mutation == 'update':
            connection.execute("UPDATE context_observations SET subject_id='changed' WHERE content_digest=?", (ref,))
        elif mutation == 'delete':
            connection.execute('DELETE FROM context_observations WHERE content_digest=?', (ref,))
        else:
            connection.execute('INSERT OR REPLACE INTO context_contents VALUES (?,?)', (ref, b'{}'))
    before = db.read_bytes()
    with pytest.raises(ValueError, match='not verified ready'):
        consume(db, origins, implementation.LiveTennisReadBudget())
    assert db.read_bytes() == before


def test_all_removed_participant_revisions_and_mixed_clocks_remain(tmp_path):
    db, refs, _, _, _ = packet(tmp_path)
    removed = revision(db, '1000', NOW-timedelta(hours=1), (9001, 9002))
    origins = list(origins_at(db, refs[:2]))
    origins[1] = deepcopy(origins[0])
    origins[1]['cutoff'] = (NOW-timedelta(minutes=90)).isoformat().replace('+00:00', 'Z')
    # Source ownership preserves clocks; pure origin/base validation is tested
    # independently because this deliberately changes the synthetic origin.
    cases = tuple((origin['event'], origin['cutoff']) for origin in origins)
    with implementation.open_live_sources(db, cases, implementation.LiveTennisReadBudget()) as (_, sources):
        refs_at_clocks = [set(owner.observation_refs) for owner in sources.histories()]
    assert set(removed) <= refs_at_clocks[0]
    assert set(removed).isdisjoint(refs_at_clocks[1])


def test_shared_deadline_cannot_restart_with_later_case(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    budget = implementation.LiveTennisReadBudget()
    first = implementation._LiveCaseBudget(budget)
    clock[0] = 1201.
    second = implementation._LiveCaseBudget(budget)
    for owner in (first, second):
        with pytest.raises(TimeoutError):
            owner.check()


def test_early_consumer_exit_is_not_a_complete_batch(tmp_path):
    db, refs, _, _, _ = packet(tmp_path)
    origins = origins_at(db, refs[:2])
    with pytest.raises(ValueError, match='did not complete'):
        with implementation.open_live_sources(db, tuple((o['event'], o['cutoff']) for o in origins),
                                    implementation.LiveTennisReadBudget()) as (_, sources):
            next(sources.histories())


@pytest.mark.parametrize('field', ['seconds', 'cpu_seconds', 'case_limit', 'raw_row_limit', 'raw_byte_limit', 'output_limit'])
def test_live_limits_only_tighten(field):
    budget = implementation.LiveTennisReadBudget()
    setattr(budget, field, getattr(budget, field)+1)
    with pytest.raises(ValueError, match='only tighten'):
        budget.check()


@pytest.mark.parametrize('field', ['chunk_rows', 'chunk_bytes'])
def test_case_chunk_contract_cannot_be_enlarged(field):
    unit = implementation._LiveCaseBudget(implementation.LiveTennisReadBudget())
    setattr(unit, field, getattr(unit, field)+1)
    with pytest.raises(ValueError, match='only tighten'):
        unit.check()


def test_prepared_output_ref_retention_is_separate_and_bounded():
    budget = implementation.LiveTennisReadBudget()
    budget.output_limit = 1024
    with pytest.raises(ValueError, match='output/reference retention'):
        budget.keep_prepared(('x'*2048, {}, 'key'))


@pytest.mark.parametrize('different_clocks', [False, True])
def test_actual_original_both_tours_equal_oracle_and_previous_owner_dies_before_next(tmp_path, monkeypatch, different_clocks):
    from contextlib import contextmanager
    import gc
    import hashlib
    import weakref
    from context_sources.tennis_capture import capture_tennis_worker
    from context_sources.tennis_status import tennis_histories_as_of
    from context_models.tennis_live import CODE_PATHS
    from context_transport import KIND, context_payload_key
    from tennis.live_context import live_worker, _event, _Inventory
    from test_tennis_live_worker import configure
    from scripts import tennis_daily as daily
    from context_tennis_index_build import initialize_index, build_index
    db, predictions, _, calls = configure(monkeypatch, tmp_path, tours=('ATP', 'WTA'), same_id=True)
    with live_worker(path=db) as batch:
        with capture_tennis_worker(path=db) as capture:
            batch.attach_capture(capture)
            fixtures = daily.fetch_fixtures_espn('2026-09-09')
            for tour in ('ATP', 'WTA'):
                decision = NOW+timedelta(minutes=5) if different_clocks and tour == 'WTA' else NOW
                daily.scan_fixtures('2026-09-09', [fx for fx in fixtures if fx['tour'] == tour],
                    decision_at=decision, db_path=predictions, surfaces={}, workload_history=())
        if different_clocks:
            # This genuine native synthetic revision is AFTER ATP's cutoff
            # and BEFORE WTA's actual calculation. A min/max-clock shortcut
            # or cross-tour numeric-ID membership would fail byte parity.
            revision(db, '9000', NOW+timedelta(minutes=2), (1, 99), tour='WTA')
        initialize_index(db)
        assert build_index(db).status == 'ready'
        qualified = [item for item in batch.pending if item['binding'] is not None]
        assert len(qualified) == 2 and {item['fixture']['tour'] for item in qualified} == {'ATP', 'WTA'}
        root = Path(daily.__file__).resolve().parents[1]
        hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in CODE_PATHS}
        state_refs = batch._verify_states(qualified)
        histories = {item['fixture']['tour']: tennis_histories_as_of(db, cutoff=item['decision'],
            tours=(item['fixture']['tour'],))[item['fixture']['tour']] for item in qualified}
        expected, expected_reasons = {}, []
        with _reader(db) as connection:
            inventory = _Inventory(connection)
            for item in qualified:
                with histories[item['fixture']['tour']].feature_scope(_event(item['binding']['row'])) as rows:
                    origin, event, base, features = batch._original(item, state_refs[id(item)], rows, hashes)
                    refs = sorted({row['digest'] for row in rows})
                effect, effect_hash, approval, reason = inventory.select(event, base, features)
                inputs = {'event': event, 'base': base, 'features': features, 'observation_refs': refs,
                    'preprocessing_refs': [], 'effect_artifact': effect, 'effect_hash': effect_hash, 'approval': approval}
                key = context_payload_key({'schema': 1, 'kind': KIND, **inputs,
                    'approval_hash': approval['digest'] if approval is not None else None})
                expected[id(item)] = (origin, inputs, key)
                expected_reasons.append(reason)
        del rows, histories
        physical = implementation.PreparedTennisHistory._from_case_physical_rows
        scope = implementation.PreparedTennisHistory.feature_scope
        refs, decoded_identities = [], {}
        @contextmanager
        def observed_scope(owner, event):
            with scope(owner, event) as actual_rows:
                decoded_identities.update((id(row), row['digest']) for row in actual_rows)
                yield actual_rows
        monkeypatch.setattr(implementation.PreparedTennisHistory, 'feature_scope', observed_scope)
        def assert_decoded_rows_released():
            # Dict/tuple cannot be weak-referenced. Record ONLY identity plus
            # digest of the real native decoded dictionaries, never their
            # objects; the GC inventory detects a leaked caller rows alias.
            remaining = [obj for obj in gc.get_objects() if type(obj) is dict
                and id(obj) in decoded_identities and obj.get('digest') == decoded_identities[id(obj)]]
            assert not remaining, 'previous actual decoded receipts overlap the next owner'
        def owned(*args, **kwargs):
            # Weakrefs point to REAL physically validated history owners.
            assert all(ref() is None for ref in refs), 'previous physical owner overlaps the next one'
            assert_decoded_rows_released()
            result = physical(*args, **kwargs)
            refs.append(weakref.ref(result))
            return result
        monkeypatch.setattr(implementation.PreparedTennisHistory, '_from_case_physical_rows', owned)
        before, provider_calls = db.read_bytes(), len(calls)
        budget = implementation.LiveTennisReadBudget()
        actual, reasons = implementation.prepare_live_v4(batch, qualified, state_refs, hashes, budget)
        assert canonical_bytes(actual) == canonical_bytes(expected)
        assert reasons == expected_reasons
        assert all(ref() is None for ref in refs) and len(refs) == 2
        assert_decoded_rows_released()
        assert len(calls) == provider_calls and db.read_bytes() == before
        assert budget.prepared_bytes > 0 and budget.completed_cases == 2
        if different_clocks:
            assert len({value[0]['cutoff'] for value in actual.values()}) == 2


@pytest.mark.parametrize('retained_alias,expected', [
    ('observations', 'actual decoded receipts overlap'),
    ('owner', 'physical owner overlaps'),
])
def test_actual_lifetime_oracle_detects_either_leaked_alias(tmp_path, monkeypatch, retained_alias, expected):
    import inspect
    source = inspect.getsource(implementation.prepare_live_v4)
    replacement = 'del owner' if retained_alias == 'observations' else 'del observations'
    namespace = dict(vars(implementation))
    exec(compile(source.replace('del observations, owner', replacement), '<deliberate-lifetime-negative>', 'exec'), namespace)
    monkeypatch.setattr(implementation, 'prepare_live_v4', namespace['prepare_live_v4'])
    with pytest.raises(AssertionError, match=expected):
        test_actual_original_both_tours_equal_oracle_and_previous_owner_dies_before_next(
            tmp_path, monkeypatch, different_clocks=True)


def test_per_case_admission_limit_excludes_only_that_case_with_diagnosis(tmp_path, monkeypatch):
    """Owner 25.10.2026 (Gesamtaudit D3): one oversized case is excluded with its numbers; the batch survives."""
    db, refs, _, _, _ = packet(tmp_path)
    origins = origins_at(db, refs[:2])
    first_key = implementation.live_event(origins[0]['event'])['event_key']
    real_selection = implementation._case_selection

    def selection(discovery, event, cutoff):
        if event['event_key'] == first_key:
            raise implementation.LiveCaseAdmissionExceeded(40000, 5, 6, 7)
        return real_selection(discovery, event, cutoff)

    monkeypatch.setattr(implementation, '_case_selection', selection)
    budget = implementation.LiveTennisReadBudget()
    cases = tuple((origin['event'], origin['cutoff']) for origin in origins)
    seen = 0
    with implementation.open_live_sources(db, cases, budget) as (_, sources):
        assert sources.admitted == [1]
        [diagnosis] = sources.excluded
        assert diagnosis['case'] == 0 and diagnosis['event_key'] == first_key
        assert diagnosis['reason'] == 'live_case_raw_admission_exceeded'
        assert (diagnosis['rows'], diagnosis['bytes'], diagnosis['max_chunk_bytes'], diagnosis['missing_payloads']) == (40000, 5, 6, 7)
        for owner in sources.histories():
            with owner.feature_scope(origins[1]['event']) as rows:
                seen += len(rows)
    assert seen > 0 and budget.completed_cases == 1 and budget.admitted_rows == budget.actual_rows
    # The exception keeps the historic message, so the fail-closed callers still match it.
    with pytest.raises(ValueError, match='live tennis per-case raw admission exceeded'):
        implementation._LiveCaseBudget(implementation.LiveTennisReadBudget()).admit_raw(1, 1, 1, missing=1)
