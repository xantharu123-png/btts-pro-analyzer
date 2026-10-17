"""Repeated final draws must not inflate causal workload history across jobs."""
from datetime import timedelta

import pytest

from context_models.contracts import canonical_timestamp
from context_sources import tennis_capture as capture
from test_context_tennis_outcome_capture import (
    RECEIVED, completed, original_store, record, stored,
)


def test_unchanged_final_across_workers_reuses_exact_original_receipts(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as first:
        record(first)
    before = stored(db)
    with capture.capture_tennis_worker(path=db) as second:
        record(second, clock=RECEIVED + timedelta(days=1))
    assert stored(db) == before
    assert second.report()['receipt_refs'] == first.report()['receipt_refs']
    assert second.report()['unchanged_terminal_receptions'] == 1


@pytest.mark.parametrize('barrier', ['started', 'scheduled', 'cancelled', 'score', 'players', 'winner'])
def test_changed_terminal_or_intervening_status_is_never_suppressed(monkeypatch, tmp_path, barrier):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as first:
        record(first)
    before = stored(db)
    changed = completed()
    if barrier in {'started', 'scheduled', 'cancelled'}:
        state, name = {'started': ('in', 'STATUS_IN_PROGRESS'),
                       'scheduled': ('pre', 'STATUS_SCHEDULED'),
                       'cancelled': ('post', 'STATUS_CANCELED')}[barrier]
        changed['status']['type'].update(state=state, name=name, completed=False)
    elif barrier == 'score':
        changed['competitors'][1]['linescores'][0]['value'] = 3
    elif barrier == 'players':
        changed['competitors'][1]['id'] = '999'
    else:
        changed = completed(winner=1)
    with capture.capture_tennis_worker(path=db) as second:
        record(second, changed, clock=RECEIVED + timedelta(minutes=1))
        record(second, clock=RECEIVED + timedelta(minutes=2))
    after = stored(db)
    assert all(row in after for row in before)
    clocks = {row['observed_at'] for row in after if row['kind'] == 'event_status'}
    assert canonical_timestamp(RECEIVED + timedelta(minutes=1)) in clocks
    assert canonical_timestamp(RECEIVED + timedelta(minutes=2)) in clocks


def test_unknown_winner_flags_keep_new_receipt_and_do_not_refresh_old_outcome(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as first:
        record(first)
    raw = completed()
    for player in raw['competitors']:
        player.pop('winner')
    with capture.capture_tennis_worker(path=db) as second:
        record(second, raw, clock=RECEIVED + timedelta(days=1))
    clocks = {r['observed_at'] for r in stored(db) if r['kind'] == 'event_status'}
    assert canonical_timestamp(RECEIVED + timedelta(days=1)) in clocks
    assert len([r for r in stored(db) if r['kind'] == 'match_outcome']) == 1


def test_non_capture_append_still_retains_each_actual_reception(monkeypatch, tmp_path):
    from context_observations import append_observation_batch
    from test_context_tennis_capture import records
    db = tmp_path/'unchanged-default.db'
    for clock in (RECEIVED, RECEIVED + timedelta(days=1)):
        append_observation_batch(db, tuple((row, clock) for row in records(clock=clock)))
    assert len(stored(db)) == 6


def test_terminal_comparison_runs_inside_the_actual_writer_transaction(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as first:
        record(first)
    actual = capture._persisted_terminal_reuse
    transactions = []
    def checked(connection, prepared):
        transactions.append(connection.in_transaction)
        return actual(connection, prepared)
    monkeypatch.setattr(capture, '_persisted_terminal_reuse', checked)
    with capture.capture_tennis_worker(path=db) as second:
        record(second, clock=RECEIVED + timedelta(days=1))
    assert transactions and all(transactions)
    assert second.report()['unchanged_terminal_receptions'] == 1


@pytest.mark.parametrize('option', [None, 0, 1, 'yes'])
def test_deduplication_requires_an_explicit_boolean_before_database_access(tmp_path, option):
    from context_observations import append_observation_batch
    path = tmp_path/'absent.db'
    with pytest.raises(ValueError, match='explicit boolean'):
        append_observation_batch(path, (), deduplicate_tennis_terminals=option)
    assert not path.exists()
