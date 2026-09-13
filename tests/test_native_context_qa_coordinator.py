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


def v2_manifest():
    from test_native_context_receipt_diagnostic import manifest_fixture
    from test_native_context_qa_retained_v2 import declared
    c = load('native_context_receipt_diagnostic_catalogue')
    value, raw, runtime, installation = manifest_fixture(c)
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
        assert os.getpid() == original_parent
        with pytest.raises(ChildProcessError):
            os.waitpid(-1, os.WNOHANG)
    finally:
        os.close(marker_read); os.close(marker_write)
