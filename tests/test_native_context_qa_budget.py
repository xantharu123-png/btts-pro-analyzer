"""Closed aggregate accounting tests; portable tests are not native custody QA."""
import importlib.util
import json
import os
from pathlib import Path

import pytest
import context_preparation_budget as legacy

SPEC = importlib.util.spec_from_file_location('qa_budget_v2', Path(__file__).with_name('native_context_qa_budget.py'))
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)
NS = 10**9
BOOT = '11111111-1111-1111-1111-111111111111'


@pytest.fixture
def package(tmp_path):
    path = tmp_path/'qa.jsonl'
    fd = os.open(path, os.O_RDWR|os.O_CREAT|os.O_EXCL|getattr(os, 'O_BINARY', 0), 0o600)
    meter = dict(now=100*NS, cpu=NS, offset=1700000000*NS, boot=BOOT)
    owner = qa.QaBudget(legacy._FileJournal(fd),
        identity=legacy.BudgetIdentity(*(x*64 for x in 'abcde')), history_digest='f'*64,
        process_start_boot_ns=99*NS,
        clock=lambda: legacy.ClockSample(meter['boot'], meter['now'], meter['now']+meter['offset'], meter['now']),
        parent_cpu=lambda: meter['cpu'])
    yield owner, path, meter
    owner.close()


def test_second_explicit_package_has_new_split_without_reinterpreting_old_records(tmp_path):
    path = tmp_path/'second-qa.jsonl'
    store = legacy._FileJournal(os.open(path, os.O_RDWR|os.O_CREAT|os.O_EXCL|getattr(os, 'O_BINARY', 0), 0o600))
    owner = qa.QaBudget(store, identity=legacy.BudgetIdentity(*(x*64 for x in 'abcde')),
        history_digest='f'*64, process_start_boot_ns=99*NS,
        clock=lambda: legacy.ClockSample(BOOT, 100*NS, 1700000100*NS, 100*NS),
        parent_cpu=lambda: NS, authorization=qa.AUTHORIZATION_02)
    try:
        assert owner.snapshot()['binding']['limits'] == {'A': 400*NS, 'B': 300*NS, 'C': 200*NS}
        assert owner.begin('A1') == 400
        finish(owner, 'A1', 108*NS)
        assert owner.begin('A2') == 292
        finish(owner, 'A2', 109*NS)
        assert owner.begin('A3') == 183
        finish(owner, 'A3', 108*NS)
        assert owner.begin('B') == 240
        finish(owner, 'B', 239*NS)
        assert owner.begin('C') == 200
        finish(owner, 'C', 108*NS)
        owner.complete('2'*64)
        assert qa.replay(path.read_bytes()).snapshot()['charged_cpu_ns'] == 900*NS
        # A public rehash cannot relabel the changed 400/300/200 split as the
        # old authorization; old package expectations remain unchanged.
        record = json.loads(path.read_bytes().splitlines()[0])
        record['body']['authorization'] = qa.AUTHORIZATION
        with pytest.raises(Exception, match='reservation|counter'):
            qa.replay(legacy._canonical(record)+b'\n')
    finally:
        owner.close()


def finish(owner, step, cpu=NS, **overrides):
    args = dict(child_cpu_ns=cpu, child_peak_rss_bytes=1024, child_exit_code=0, evidence_digest='1'*64)
    args.update(overrides)
    owner.finish(step, **args)


def test_atomic_full_reservation_precedes_work_and_never_refunds(package):
    owner, path, meter = package
    first = json.loads(path.read_bytes().splitlines()[0])
    assert first['body']['limits'] == qa.LIMITS
    assert first['body']['charge_cpu_ns'] == 900*NS
    assert first['body']['deadline_boot_ns'] == 999*NS
    for step in qa.STEPS:
        assert owner.begin(step) > 0
        finish(owner, step)
    owner.complete('2'*64)
    state = qa.replay(path.read_bytes()).snapshot()
    assert state['status'] == 'complete'
    assert state['charged_cpu_ns'] == 900*NS
    assert state['measured_child_cpu_ns'] == {'A': 3*NS, 'B': NS, 'C': NS}
    assert state['native_pass'] is False
    assert state['external_terminal_observation_required'] is True


def test_cumulative_scans_do_not_get_fresh_300_seconds(package):
    owner, _, _ = package
    assert owner.begin('A1') == 300
    finish(owner, 'A1', 120*NS+1)
    assert owner.begin('A2') == 179
    finish(owner, 'A2', 100*NS)
    assert owner.begin('A3') == 79


@pytest.mark.parametrize('step', ['A2', 'A3', 'B', 'C', '', None, True])
def test_missing_first_scan_never_admits_later_step(package, step):
    with pytest.raises(Exception):
        package[0].begin(step)


def test_second_child_and_repeated_scan_refused(package):
    owner, path, _ = package
    owner.begin('A1')
    before = path.read_bytes()
    with pytest.raises(Exception):
        owner.begin('A1')
    assert path.read_bytes() == before
    assert qa.replay(before).snapshot()['charged_cpu_ns'] == 900*NS


@pytest.mark.parametrize('change', [dict(child_cpu_ns=300*NS+1), dict(child_cpu_ns=True),
    dict(child_peak_rss_bytes=1024**3), dict(child_exit_code=-9), dict(child_exit_code=True),
    dict(evidence_digest=''), dict(child_cpu_ns=-1)])
def test_bad_actual_child_end_never_completes_or_refunds(package, change):
    owner, path, _ = package
    owner.begin('A1')
    with pytest.raises(Exception):
        finish(owner, 'A1', **change)
    state = qa.replay(path.read_bytes()).snapshot()
    assert state['pending']['step'] == 'A1'
    assert state['charged_cpu_ns'] == 900*NS


@pytest.mark.parametrize('change', [dict(cpu=60*NS+1), dict(cpu=0), dict(now=999*NS),
    dict(now=98*NS), dict(boot='22222222-2222-2222-2222-222222222222'), dict(offset=0)])
def test_whole_parent_cpu_original_deadline_and_clock_are_preserved(package, change):
    owner, path, meter = package
    meter.update(change)
    with pytest.raises(Exception):
        owner.begin('A1')
    assert qa.replay(path.read_bytes()).snapshot()['charged_cpu_ns'] == 900*NS


def test_postscan_time_is_reserved_before_worker(package):
    owner, path, meter = package
    for step in qa.STEPS[:3]:
        owner.begin(step); finish(owner, step)
    meter['now'] = 460*NS
    with pytest.raises(Exception, match='postscan'):
        owner.begin('B')
    assert qa.replay(path.read_bytes()).snapshot()['completed_steps'] == ['A1', 'A2', 'A3']


def test_cannot_finish_without_postscan(package):
    owner, _, _ = package
    for step in qa.STEPS[:4]:
        owner.begin(step); finish(owner, step)
    with pytest.raises(Exception, match='incomplete'):
        owner.complete('2'*64)


def test_stop_after_expiry_retains_pending_and_whole_charge(package):
    owner, path, meter = package
    owner.begin('A1')
    meter['now'] = 1000*NS
    owner.stop('wall deadline')
    state = qa.replay(path.read_bytes()).snapshot()
    assert state['status'] == 'stopped' and state['pending']['step'] == 'A1'
    assert state['charged_cpu_ns'] == 900*NS


@pytest.mark.parametrize('mutation', ['truncate', 'append', 'rewrite'])
def test_held_journal_mutation_refuses_all_further_work(package, mutation):
    owner, path, _ = package
    raw = path.read_bytes()
    altered = raw[:-1] if mutation == 'truncate' else raw+b'{}\n' if mutation == 'append' else raw.replace(b'900000000000', b'800000000000')
    path.write_bytes(altered)
    with pytest.raises(Exception):
        owner.begin('A1')


def test_fsync_failure_returns_no_allowance_and_poisoned_owner(package, monkeypatch):
    owner, path, _ = package
    def failed(_fd):
        raise OSError('injected fsync failure')
    monkeypatch.setattr(os, 'fsync', failed)
    with pytest.raises(OSError):
        owner.begin('A1')
    with pytest.raises(Exception):
        owner.begin('A1')
    assert qa.replay(path.read_bytes()).snapshot()['charged_cpu_ns'] == 900*NS


def test_existing_package_cannot_be_reopened_with_new_identity(package):
    owner, path, meter = package
    owner.close()
    store = legacy._FileJournal(os.open(path, os.O_RDWR|getattr(os, 'O_BINARY', 0)))
    try:
        with pytest.raises(Exception, match='restarted'):
            qa.QaBudget(store, identity=legacy.BudgetIdentity(*('9'*64 for _ in range(5))),
                history_digest='8'*64, process_start_boot_ns=meter['now'],
                clock=lambda: legacy.ClockSample(BOOT, meter['now'], meter['now'], meter['now']), parent_cpu=lambda: 0)
    finally:
        store.close()


def test_unchanged_owner_checks_read_all_bytes_without_replaying_history(package, monkeypatch):
    owner, path, _ = package
    for step in ('A1', 'A2'):
        owner.begin(step)
        finish(owner, step)
    expected = qa.replay(path.read_bytes()).snapshot()
    reads = []
    read = owner.store.read
    def observed_read():
        raw = read()
        reads.append(raw)
        return raw
    def redundant_replay(_raw):
        raise AssertionError('unchanged accepted journal was replayed again')
    monkeypatch.setattr(owner.store, 'read', observed_read)
    monkeypatch.setattr(qa, 'replay', redundant_replay)
    for _ in range(20):
        owner.assert_running()
        assert owner.snapshot() == expected
    assert len(reads) == 40 and all(raw == path.read_bytes() for raw in reads)


@pytest.mark.parametrize('mutation', ['truncate', 'append', 'same-length'])
def test_fast_owner_checks_reject_changed_bytes_even_with_restored_mtime(package, mutation):
    owner, path, _ = package
    owner.assert_running()
    original = path.stat()
    raw = path.read_bytes()
    changed = (raw[:-1] if mutation == 'truncate' else raw+b'{}\n'
               if mutation == 'append' else raw.replace(b'900000000000', b'800000000000'))
    assert changed != raw
    path.write_bytes(changed)
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    with pytest.raises(Exception):
        owner.assert_running()


@pytest.mark.parametrize('change', [dict(cpu=60*NS+1), dict(cpu=0), dict(now=999*NS),
    dict(now=98*NS), dict(boot='22222222-2222-2222-2222-222222222222'), dict(offset=0)])
def test_fast_owner_check_preserves_every_live_resource_and_clock_guard(package, change):
    owner, path, meter = package
    before = path.read_bytes()
    meter.update(change)
    with pytest.raises(Exception):
        owner.assert_running()
    assert path.read_bytes() == before


def test_fast_owner_checks_do_not_skip_durable_replay_after_append(package, monkeypatch):
    owner, path, _ = package
    real_replay, observed = qa.replay, []
    def replay(raw):
        observed.append(raw)
        return real_replay(raw)
    monkeypatch.setattr(qa, 'replay', replay)
    owner.begin('A1')
    assert observed[-1] == path.read_bytes()
    assert real_replay(observed[-1]).snapshot() == owner.snapshot()
    count = len(observed)
    owner.assert_running()
    assert len(observed) == count


def test_fast_owner_check_never_reopens_stopped_or_closed_owner(package):
    owner, _, _ = package
    owner.stop('bounded test stop')
    with pytest.raises(Exception, match='active'):
        owner.assert_running()
    owner.close()
    with pytest.raises(Exception):
        owner.assert_running()


def test_fast_owner_check_rejects_inherited_owner(package, monkeypatch):
    owner, _, _ = package
    monkeypatch.setattr(qa.os, 'getpid', lambda: owner.pid+1)
    with pytest.raises(Exception, match='owner'):
        owner.assert_running()


def test_fast_owner_check_preserves_in_memory_state_integrity(package):
    owner, path, _ = package
    before = path.read_bytes()
    owner.state.binding['limits']['A'] += NS
    with pytest.raises(Exception, match='state changed'):
        owner.assert_running()
    assert path.read_bytes() == before


def test_returned_snapshot_cannot_change_the_accepted_owner_state(package):
    owner, _, _ = package
    snapshot = owner.snapshot()
    snapshot['binding']['limits']['A'] += NS
    owner.assert_running()
    assert owner.snapshot()['binding']['limits'] == qa.LIMITS
