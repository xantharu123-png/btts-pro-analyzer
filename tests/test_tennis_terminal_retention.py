"""One feed's identical terminal echoes are not fresh sporting evidence."""
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import canonical_timestamp
from context_sources.tennis_capture import _Capture
from test_context_tennis_capture import NOW, competition, response


def capture_repeat(*, second=None):
    owner = _Capture()
    owner.record('atp', response(), observed_at=NOW)
    owner.record('atp', response(second), observed_at=NOW+timedelta(hours=1))
    return owner


def test_identical_terminal_echo_keeps_first_real_clock_and_bytes(tmp_path):
    owner = capture_repeat()
    assert len(owner.pending) == 1
    assert owner.unchanged_terminal_receptions == 1
    db = tmp_path/'context.db'
    owner.persist(db)
    with sqlite3.connect(db) as connection:
        assert connection.execute('SELECT COUNT(*) FROM context_observations').fetchone()[0] == 3
        assert connection.execute('SELECT DISTINCT observed_at FROM context_observations').fetchall() == [
            (canonical_timestamp(NOW),)]


@pytest.mark.parametrize('change', ['score', 'player', 'schedule', 'winner', 'missing_score', 'tournament'])
def test_real_terminal_changes_are_retained(change):
    raw = competition()
    if change == 'score':
        raw['competitors'][1]['linescores'][1]['value'] = 5
    elif change == 'player':
        raw['competitors'][1]['id'] = '3'
    elif change == 'schedule':
        raw['date'] = '2026-09-08T19:00Z'
    elif change == 'winner':
        raw['competitors'][0]['winner'] = True
    elif change == 'missing_score':
        raw['competitors'][0].pop('linescores')
    owner = _Capture()
    owner.record('atp', response(), observed_at=NOW)
    changed = response(raw)
    if change == 'tournament':
        changed['events'][0]['id'] = '190-2026'
    owner.record('atp', changed, observed_at=NOW+timedelta(hours=1))
    assert len(owner.pending) == 2
    assert owner.unchanged_terminal_receptions == 0


def test_retraction_then_same_result_never_reuses_old_terminal():
    owner = _Capture()
    owner.record('atp', response(), observed_at=NOW)
    scheduled = competition(status={'type': {'state': 'pre', 'completed': False, 'name': 'STATUS_SCHEDULED'}})
    owner.record('atp', response(scheduled), observed_at=NOW+timedelta(hours=1))
    owner.record('atp', response(), observed_at=NOW+timedelta(hours=2))
    assert len(owner.pending) == 3


@pytest.mark.parametrize('state,name', [('pre', 'STATUS_SCHEDULED'), ('in', 'STATUS_IN_PROGRESS')])
def test_identical_live_receipts_remain_separate_timing_evidence(state, name):
    owner = _Capture()
    raw = response(competition(status={'type': {'state': state, 'completed': False, 'name': name}}))
    owner.record('atp', raw, observed_at=NOW)
    owner.record('atp', raw, observed_at=NOW+timedelta(hours=1))
    assert len(owner.pending) == 2


def test_new_worker_still_records_real_new_receipt_not_cross_run_cache():
    first, second = _Capture(), _Capture()
    first.record('atp', response(), observed_at=NOW)
    second.record('atp', response(), observed_at=NOW+timedelta(days=1))
    assert len(first.pending) == len(second.pending) == 1
    assert first.pending[0][1] != second.pending[0][1]


def test_backward_reception_clock_is_not_deduplicated():
    owner = _Capture()
    owner.record('atp', response(), observed_at=NOW)
    owner.record('atp', response(), observed_at=NOW-timedelta(hours=1))
    assert len(owner.pending) == 2


def test_same_clock_different_native_winner_flags_are_not_deduplicated():
    owner = _Capture()
    owner.record('atp', response(), observed_at=NOW)
    changed = competition()
    changed['competitors'][0]['winner'] = True
    owner.record('atp', response(changed), observed_at=NOW)
    assert len(owner.pending) == 2


def test_same_terminal_after_successful_drain_is_new_receipt(tmp_path):
    owner = _Capture()
    owner.record('atp', response(), observed_at=NOW)
    owner.persist(tmp_path/'context.db')
    owner.record('atp', response(), observed_at=NOW+timedelta(hours=1))
    assert len(owner.pending) == 2


def test_provider_price_and_display_name_do_not_change_sporting_revision():
    raw = competition(odds={'decimal': 1.2}, displayName='A vs B')
    raw['competitors'][0]['athlete'] = {'displayName': 'Player A'}
    owner = capture_repeat(second=raw)
    assert len(owner.pending) == 1
    assert owner.unchanged_terminal_receptions == 1


@pytest.mark.parametrize('flag', [float('inf'), float('-inf'), float('nan'),
    0, 1, 'true', [], {}, object()])
def test_malformed_native_winner_keeps_ambiguous_receipt_without_echo_failure(flag):
    raw = competition()
    raw['competitors'][0]['winner'] = flag
    owner = _Capture()
    owner.record('atp', response(raw), observed_at=NOW)
    owner.record('atp', response(raw), observed_at=NOW+timedelta(hours=1))
    assert len(owner.pending) == 2
    assert owner.unchanged_terminal_receptions == 0
    assert list(owner._outcome_sources.values()) == [None, None]
