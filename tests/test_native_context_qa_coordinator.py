"""V2 sequence and real child boundary tests, separate from the full corpus."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_has_closed_membership_and_uses_held_bytes():
    m = load('native_context_qa_coordinator')
    sources = {'base.py': b'# exact base\n', m.COORDINATOR: b'# exact coordinator\n', m.BUDGET: b'# exact budget\n'}
    raw = m.bootstrap_source(sources, ('base.py',))
    assert b'exact coordinator' in raw and b'exact base' in raw
    with pytest.raises(Exception):
        m.bootstrap_source(dict(sources, unknown=b'code'), ('base.py',))
    with pytest.raises(Exception):
        m.bootstrap_source(dict(sources, **{m.BUDGET: b''}), ('base.py',))


def test_each_scanner_step_calls_its_actual_full_observer_once(monkeypatch):
    m = load('native_context_qa_coordinator')
    c = load('native_context_receipt_diagnostic_catalogue')
    seen = []
    request = dict(roots=[], archive=dict(path='unused'), commit='a'*40)
    monkeypatch.setattr(m, 'selected_history', lambda: [])
    funcs = dict(c.__dict__)
    funcs['validate_retained_v2'] = lambda raw, **kwargs: seen.append(('observe', raw, kwargs))
    funcs['inventory_v2'] = lambda *args, **kwargs: (seen.append(('inventory', args, kwargs)) or b'{}')
    for step in ('A2', 'A3', 'C'):
        before = len(seen)
        raw = m._scanner_action(step, funcs, request, b'{}')
        assert len(seen) == before+1 and raw
        if step != 'A2':
            assert seen[-1] == ('observe', b'{}', {'observe': True})


def test_selector_drift_stops_before_any_scan(monkeypatch):
    m = load('native_context_qa_coordinator')
    monkeypatch.setattr(m, 'selected_history', lambda: ['/unexpected'])
    with pytest.raises(Exception, match='membership'):
        m._scanner_action('A3', {}, dict(roots=[]), b'{}')


def v2_manifest(*, inventory_bytes=None):
    from test_native_context_receipt_diagnostic import manifest_fixture
    from test_native_context_qa_retained_v2 import declared
    c = load('native_context_receipt_diagnostic_catalogue')
    value, raw, runtime, installation = manifest_fixture(c, inventory_bytes=inventory_bytes)
    value['format'] = c.FORMAT_V2
    for name in ('tests/native_context_qa_coordinator.py', 'tests/native_context_qa_budget.py'):
        value['code'].append(dict(path=name, size=1, sha256='1'*64))
    value['code'].sort(key=lambda x: x['path'])
    retained = c.decode(raw)
    retained['format'] = 'betboy-receipt-diagnostic-retained-v2'
    retained['historical_fifo'] = declared(c)
    for item in retained['roots']:
        item['fifos'] = 0
    extra = copy.deepcopy(retained['roots'][0])
    extra.update(path=c.HISTORICAL_FIFO_ROOT, fifos=1, journals=[])
    retained['roots'].append(extra)
    retained['roots'].sort(key=lambda x: x['path'])
    raw = c.canonical(retained)
    value['retained'].update(size=len(raw), sha256=c.digest(raw))
    value['admission'].update(purpose='context-receipt-corpus-diagnostic-v2', retained_history_digest=c.digest(raw),
                              identity=c.budget_identity(value, runtime, installation))
    value['allocation'] = c.allocation_plan(dict(value, _retained_data=retained),
        archive_path='/var/lib/task61-inputs/code.tar', manifest_path='/var/lib/task61-inputs/manifest.json',
        retained_path=value['retained']['path'])
    value['admission']['plan_digest'] = c.digest(c.canonical({k: v for k, v in value.items() if k != 'admission'}))
    return c, value, raw, runtime, installation


def test_v2_manifest_accounts_external_controls_and_v1_refuses_it():
    c, value, raw, runtime, installation = v2_manifest()
    c.validate_manifest_v2(value, 'd'*40, retained_raw=raw, runtime=runtime, installation=installation)
    assert value['allocation']['registry_slots'] == {c.QA_JOURNAL: c.MIB}
    assert 'coordination-failure.json' in value['allocation']['coordination_slots']
    assert any(x['path'].endswith('/request.json') for x in value['allocation']['inputs'])
    with pytest.raises(Exception):
        c.validate_manifest(value, 'd'*40, retained_raw=raw, runtime=runtime, installation=installation)


@pytest.mark.parametrize('variant', ['current', 'tampered', 'crlf'])
def test_v2_manifest_rejects_nonhistorical_inventory_even_when_rehashed(variant):
    from native_context_chain_fixtures import ROOT, historical_source
    name = 'context_storage_v2/inventory.py'
    historical = historical_source(name)
    candidate = {'current': (ROOT/name).read_bytes(), 'tampered': historical + b'\n',
                 'crlf': historical.replace(b'\n', b'\r\n')}[variant]
    c, value, raw, runtime, installation = v2_manifest(inventory_bytes=candidate)
    with pytest.raises(c.DiagnosticError, match='unchanged owner pin differs'):
        c.validate_manifest_v2(value, 'd'*40, retained_raw=raw, runtime=runtime, installation=installation)


@pytest.mark.parametrize('missing', ['tests/native_context_qa_coordinator.py', 'tests/native_context_qa_budget.py'])
def test_rehashed_v2_manifest_cannot_omit_its_executing_owner(missing):
    c, value, raw, runtime, installation = v2_manifest()
    value['code'] = [item for item in value['code'] if item['path'] != missing]
    value['admission']['identity'] = c.budget_identity(value, runtime, installation)
    value['admission']['plan_digest'] = c.digest(c.canonical({k: v for k, v in value.items() if k != 'admission'}))
    with pytest.raises(Exception):
        c.validate_manifest_v2(value, 'd'*40, retained_raw=raw, runtime=runtime, installation=installation)


def test_cpu_conversion_is_conservative():
    m = load('native_context_qa_coordinator')
    assert m._cpu_ns(SimpleNamespace(ru_utime=1.0000000001, ru_stime=0)) == 1000000001
    for number in (float('nan'), float('inf'), -1):
        with pytest.raises(Exception):
            m._cpu_ns(SimpleNamespace(ru_utime=number, ru_stime=0))


@pytest.mark.parametrize('fault', ['none', 'file-writable', 'directory-writable', 'foreign-owner', 'other-group-ancestor', 'hardlink'])
def test_frozen_baseline_readonly_group_is_not_write_authority(monkeypatch, fault):
    import stat
    c = load('native_context_receipt_diagnostic_catalogue')
    baseline = Path(c.BASELINE_PATH)
    def info(path):
        leaf = path == baseline
        group = 1001 if path in (baseline, baseline.parent) else 0
        mode = stat.S_IFREG|0o440 if leaf else stat.S_IFDIR|0o750
        owner, links = 0, 1
        if fault == 'file-writable' and leaf: mode |= 0o020
        if fault == 'directory-writable' and path == baseline.parent: mode |= 0o002
        if fault == 'foreign-owner' and leaf: owner = 1001
        if fault == 'other-group-ancestor' and path == baseline.parent.parent: group = 1001
        if fault == 'hardlink' and leaf: links = 2
        return SimpleNamespace(st_uid=owner, st_gid=group, st_mode=mode, st_nlink=links)
    monkeypatch.setattr(Path, 'lstat', info)
    monkeypatch.setattr(Path, 'is_symlink', lambda p: False)
    if fault == 'none':
        assert c.protected(baseline).st_gid == 1001
        with pytest.raises(Exception):
            c.protected(baseline.parent, directory=True)
    else:
        with pytest.raises(Exception):
            c.protected(baseline)


def test_failed_scanner_retains_structural_diagnosis_without_values_or_locals():
    import json
    m = load('native_context_qa_coordinator')
    private_value = 'must-not-be-logged'
    try:
        raise ValueError(private_value)
    except ValueError as exc:
        raw = m.scanner_failure_bytes('A2', exc)
    result = json.loads(raw)
    assert len(raw) < 8192 and private_value.encode() not in raw
    assert result['exception'] == 'ValueError' and result['step'] == 'A2'
    assert result['trace'][-1]['function'] == 'test_failed_scanner_retains_structural_diagnosis_without_values_or_locals'


def previous_package_fixture():
    import hashlib
    m = load('native_context_qa_coordinator')
    owner = m.Coordinator.__new__(m.Coordinator)
    owner._previous_qa_bytes = None
    raw = b'exact previously accepted journal bytes\n'
    reads, replays = [], []
    state = dict(charged_cpu_ns=900*m.NS, binding=dict(authorization='old-fixed-authorization'),
                 completed_steps=['A1'], pending=dict(step='A2'))
    source = dict(raw=raw)
    expected_sha = hashlib.sha256(raw).hexdigest()
    def read(path, maximum, expected):
        assert path.as_posix() == m.PRIOR_REGISTRY+'/qa-coordination-v2.jsonl'
        assert maximum == m.MIB and expected == expected_sha
        reads.append(source['raw'])
        if hashlib.sha256(source['raw']).hexdigest() != expected:
            raise ValueError('held bytes differ')
        return source['raw']
    def replay(data):
        replays.append(data)
        return SimpleNamespace(snapshot=lambda: copy.deepcopy(state))
    owner.c = dict(old=lambda:dict(data_bytes=read), QA_JOURNAL='qa-coordination-v2.jsonl')
    owner.qa = dict(replay=replay, AUTHORIZATION='old-fixed-authorization')
    owner.request = dict(previous_costs=dict(prior_qa_journal_sha256=expected_sha))
    return owner, source, reads, replays, state


def test_previous_package_is_fully_read_each_time_but_identical_state_is_parsed_once():
    owner, source, reads, replays, _ = previous_package_fixture()
    for _ in range(20):
        owner.check_previous_package()
    assert reads == [source['raw']]*20 and replays == [source['raw']]
    source['raw'] = source['raw'].replace(b'accepted', b'rejected')
    with pytest.raises(ValueError, match='bytes'):
        owner.check_previous_package()
    assert len(reads) == 21 and len(replays) == 1


@pytest.mark.parametrize('mutation', ['charge', 'authorization', 'completed', 'pending'])
def test_previous_package_cache_never_accepts_invalid_old_reservation(mutation):
    owner, _, _, _, state = previous_package_fixture()
    if mutation == 'charge': state['charged_cpu_ns'] = 0
    if mutation == 'authorization': state['binding']['authorization'] = 'other'
    if mutation == 'completed': state['completed_steps'] = ['A1', 'A2']
    if mutation == 'pending': state['pending']['step'] = 'B'
    with pytest.raises(Exception, match='qualification state changed'):
        owner.check_previous_package()
    assert owner._previous_qa_bytes is None


@pytest.mark.skipif(sys.platform != 'linux', reason='actual Linux root fork/pidfd/wait4 required')
@pytest.mark.parametrize('fault', ['none', 'exception', 'empty', 'oversize', 'wall', 'cpu'])
def test_native_scanner_is_reaped_on_success_and_every_failure(monkeypatch, fault):
    if os.geteuid() != 0:
        pytest.skip('actual root scanner identity required')
    import context_preparation_supervisor as supervisor
    m = load('native_context_qa_coordinator')
    c = load('native_context_receipt_diagnostic_catalogue')
    marker_read, marker_write = os.pipe()
    original_parent = os.getpid()
    def action(*args):
        # The scanner must not inherit the owner's unrelated open descriptors.
        with pytest.raises(OSError):
            os.fstat(marker_write)
        if fault == 'exception': raise RuntimeError('fixed injected scanner error')
        if fault == 'empty': return b''
        if fault == 'oversize': return b'x'*(8*1024**2+1)
        if fault == 'wall': time.sleep(10)
        if fault == 'cpu':
            while True:
                pass
        return b'{"actual":true}'
    monkeypatch.setattr(m, '_scanner_action', action)
    try:
        deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME)+(1 if fault == 'wall' else 8)*10**9
        if fault == 'none':
            raw, result = m.run_scanner('A1', c.__dict__, {}, None, allowance=2, deadline=deadline, supervisor=supervisor)
            assert raw == b'{"actual":true}' and result['child_exit_code'] == 0
            assert result['child_cpu_ns'] > 0 and result['child_peak_rss_bytes'] > 0
        else:
            with pytest.raises(m.ScannerStopped) as stopped:
                m.run_scanner('A1', c.__dict__, {}, None, allowance=1, deadline=deadline, supervisor=supervisor)
            assert stopped.value.measurement['child_exit_code'] is not None
            assert stopped.value.measurement['child_cpu_ns'] is not None
            if fault == 'exception':
                assert b'betboy-scanner-error-v1' in stopped.value.prefix
        assert os.getpid() == original_parent
        with pytest.raises(ChildProcessError):
            os.waitpid(-1, os.WNOHANG)
    finally:
        os.close(marker_read); os.close(marker_write)
