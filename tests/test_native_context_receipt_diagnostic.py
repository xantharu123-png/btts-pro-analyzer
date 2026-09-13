"""Focused Task61 QA. Portable behavior is not privileged/native acceptance."""
from pathlib import Path
import importlib.util
import json
import os
import stat
import subprocess
import sys

import pytest

ROOT = Path(__file__).absolute().parents[1]


def load(name):
    path = ROOT / 'tests' / (name + '.py')
    assert path.is_file(), 'Task61 missing implementation path: ' + name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(event='begin', phase='worker_setup', occurrence=1, depth=1, completed=0):
    return dict(event=event, phase=phase, occurrence=occurrence, depth=depth,
                completed=completed, cpu_ns=1, wall_ns=1, phase_cpu_ns=0,
                phase_wall_ns=0, submitted=completed, new_contents=completed,
                new_receipts=completed, exception=None)


def test_closed_profile_rejects_substitutions_and_bool():
    c = load('native_context_receipt_diagnostic_catalogue')
    profile = c.fixed_profile()
    assert c.validate_profile(profile) == profile
    for key, value in [('stop', 64), ('start', False), ('first_native_id', 2**63-4),
                       ('wta_fixture', {}), ('kind', 'mixed')]:
        altered = dict(profile, **{key: value})
        with pytest.raises(Exception):
            c.validate_profile(altered)


def test_progress_has_durable_hash_linked_prefix_and_rejects_complete_corruption(tmp_path):
    c = load('native_context_receipt_diagnostic_catalogue')
    path = tmp_path / 'progress.jsonl'
    p = c.Progress(path)
    first = p.append(body())
    p.append(body('end'))
    p.close()
    raw = path.read_bytes()
    parsed = c.parse_progress(raw + b'{"incomplete')
    assert parsed['complete_bytes'] == len(raw)
    assert parsed['incomplete_tail_bytes'] == 12
    assert parsed['stack'] == []
    assert parsed['head'] != '0' * 64
    assert first['previous'] == '0' * 64
    with pytest.raises(Exception):
        c.parse_progress(raw.replace(b'worker_setup', b'worker_other'))
    with pytest.raises(Exception):
        c.parse_progress(raw + b'{}\n')
    with pytest.raises(Exception):
        c.Progress(path)


def test_progress_rejects_illegal_stack_checkpoint_and_repeated_phase(tmp_path):
    c = load('native_context_receipt_diagnostic_catalogue')
    for invalid in [body('end'), body(phase='copy'), body('checkpoint'),
                    body(occurrence=2), body(depth=2), body(completed=1)]:
        p = c.Progress(tmp_path / ('p' + str(len(list(tmp_path.iterdir())))))
        with pytest.raises(Exception):
            p.append(invalid)
        p.close()


def test_progress_partial_write_and_fsync_failure_are_not_swallowed(tmp_path, monkeypatch):
    c = load('native_context_receipt_diagnostic_catalogue')
    p = c.Progress(tmp_path / 'partial')
    actual_write = os.write
    monkeypatch.setattr(os, 'write', lambda fd, raw: actual_write(fd, raw[:7]))
    p.append(body())
    p.close()
    assert c.parse_progress((tmp_path / 'partial').read_bytes())['last_phase'] == 'worker_setup'
    p = c.Progress(tmp_path / 'fsync')
    monkeypatch.setattr(os, 'fsync', lambda fd: (_ for _ in ()).throw(OSError('fsync')))
    with pytest.raises(OSError):
        p.append(body())
    p.close()


def test_exact_slots_stream_larger_than_old_member_cap_and_reject_unknown(tmp_path):
    c = load('native_context_receipt_diagnostic_catalogue')
    path = tmp_path / 'baseline'
    size = 128 * 1024**2 + 1
    with path.open('wb') as f:
        block = b'x' * 1024**2
        for _ in range(128):
            f.write(block)
        f.write(b'x')
    sample = c.sample_exact_slots(tmp_path, {'baseline': size}, 1024**2)
    assert sample['files'][0]['size'] == size
    assert sample['logical'] >= size
    with pytest.raises(Exception):
        c.sample_exact_slots(tmp_path, {'baseline': 128*1024**2}, 1024**2)
    (tmp_path / 'unknown').write_bytes(b'no')
    with pytest.raises(Exception):
        c.sample_exact_slots(tmp_path, {'baseline': size}, 1024**2)


def test_rejected_admission_never_copies_or_forks(tmp_path, monkeypatch):
    d, c, argv, events, job, baseline = actual_main_fixture(tmp_path, monkeypatch)
    with pytest.raises(RejectedAdmission):
        d.main(argv)
    assert events == ['admission']
    assert list(job.iterdir()) == []


def test_guard_before_import_rejects_portable_worker():
    w = load('native_context_receipt_diagnostic_worker')
    before = set(sys.modules)
    with pytest.raises(Exception):
        w.run('receipt-v1')
    assert not any(n.startswith(('context_storage_v2', 'context_growth_profile'))
                   for n in set(sys.modules) - before)


def test_real_sample_calls_actual_corpus_once(tmp_path, monkeypatch):
    w = load('native_context_receipt_diagnostic_worker')
    c = load('native_context_receipt_diagnostic_catalogue')
    from test_context_storage_receipt_corpus import source, reader
    from context_storage_v2 import receipt_corpus
    from context_growth_profile import build_growth_profile
    from datetime import datetime
    p = c.fixed_profile()
    import sqlite3
    from contextlib import closing
    from context_storage_v2.inventory import inventory_raw
    with source(tmp_path, large=True, all_rows=True) as (path, sealed, held):
        pass
    with closing(sqlite3.connect(path)) as writer:
        writer.execute('UPDATE artifacts SET payload=zeroblob(?)', (17*1024**2,))
        writer.commit()
    sealed = c.old()['file_record'](path)['sha256']
    with reader(path) as held:
        old_inventory = inventory_raw(held)
        profile = build_growth_profile(p['kind'], baseline_sha256=sealed,
            start_at=datetime.fromisoformat(p['start_at']), first_native_id=p['first_native_id'],
            atp_fixture=p['atp_fixture'], wta_fixture=None)
        actual = receipt_corpus.build_receipt_corpus
        calls = []
        def observed(*args, **kwargs):
            calls.append(1)
            return actual(*args, **kwargs)
        monkeypatch.setattr(receipt_corpus, 'build_receipt_corpus', observed)
        work = tmp_path / 'work'
        (work / 'corpus').mkdir(parents=True)
        progress = c.Progress(work / 'progress.jsonl')
        import types
        manifest, _, _, _ = manifest_fixture(c)
        monkeypatch.setattr(os, 'statvfs', lambda path:types.SimpleNamespace(f_bavail=40*1024**3, f_frsize=1), raising=False)
        checker = w.WorkerAllocation(c.__dict__, manifest['allocation'], work)
        recorder = w.PhaseRecorder(progress, allocation_check=checker)
        result = w.measure_corpus(held, profile, sealed, work, progress, recorder=recorder)
        progress.close()
        assert calls == [1]
        assert result.submitted_observations == result.new_contents == result.new_receipts == 1024
        assert result.source_sha256 == sealed
        assert result.output_sha256 != sealed
        assert result.source_inventory == old_inventory
        untouched = {table.name: table for table in old_inventory.tables
                     if table.name not in ('context_contents', 'context_observations')}
        assert {table.name: table for table in result.inventory.tables if table.name in untouched} == untouched
        parsed = c.parse_progress((work / 'progress.jsonl').read_bytes())
        assert parsed['completed'] == 1024
        assert checker.calls == 2*len(recorder.summary) < 128
        for phase in recorder.summary:
            for boundary in ('allocation_before','allocation_after'):
                observation = phase[boundary]
                assert observation['required_free'] > 8*1024**3
                assert observation['free'] == 40*1024**3
                assert 0 <= observation['checker_cpu_ns'] <= phase['inclusive_cpu_ns']
                assert 0 <= observation['checker_wall_ns'] <= phase['inclusive_wall_ns']
        for clock in ('cpu','wall'):
            assert sum(phase[b]['checker_'+clock+'_ns'] for phase in recorder.summary
                       for b in ('allocation_before','allocation_after')) > 0


@pytest.mark.skipif(sys.platform != 'linux' or os.environ.get('BETBOY_TASK61_NATIVE') != 'prepared',
                    reason='Root must explicitly prepare a fresh secret-free stdlib native coordinator')
def test_native_prefix_failure_never_unwinds_parent_owner():
    result = native_prefix_subprocess('failure')
    assert result['exit_code'] == 125 and result['owner_cleanup_pids'] == [result['parent_pid']]


@pytest.mark.skipif(sys.platform != 'linux' or os.environ.get('BETBOY_TASK61_NATIVE') != 'prepared',
                    reason='Root must explicitly prepare a fresh secret-free stdlib native coordinator')
def test_native_prefix_success_preserves_parent60_and_actual_stopped_child240():
    result = native_prefix_subprocess('success')
    assert result['exit_code'] == 0 and result['parent_cpu'] == [60, 60]
    assert result['kernel_readback']['cpu_seconds'] == 240


def native_prefix_subprocess(mode):
    c = load('native_context_receipt_diagnostic_catalogue')
    sources = {name: (ROOT/name).read_bytes() for name in c.BOOTSTRAP}
    script = ('__name__="_native_prefix_coordinator"\n_REVIEWED_BOOTSTRAP=' + repr(sources) +
        '\nexec(compile(_REVIEWED_BOOTSTRAP["tests/native_context_receipt_diagnostic.py"],"<reviewed-task61-parent>","exec"))\n'
        'print(json.dumps(native_prefix_test(' + repr(mode) + ',root="/var/lib/betboy-receipt-prefix-task61-01"),sort_keys=True,separators=(",",":")))\n')
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-'], input=script.encode('ascii'),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, timeout=280)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stderr == b''
    return json.loads(result.stdout)


def test_killed_worker_retains_only_verified_progress_prefix(tmp_path):
    c = load('native_context_receipt_diagnostic_catalogue')
    path = tmp_path / 'progress.jsonl'
    script = ('import runpy,sys,time\n'
              'c=runpy.run_path(sys.argv[1])\n'
              'p=c["Progress"](__import__("pathlib").Path(sys.argv[2]))\n'
              'p.append(' + repr(body()) + ')\n'
              'print("durable",flush=True)\n'
              'time.sleep(30)\n')
    process = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', script,
        str(ROOT / 'tests/native_context_receipt_diagnostic_catalogue.py'), str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert process.stdout.readline().rstrip(b'\r\n') == b'durable'
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode != 0
        assert stderr == b''
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    parsed = c.parse_progress(path.read_bytes())
    assert parsed['completed'] == 0 and parsed['terminal'] is False
    assert parsed['last_phase'] == 'worker_setup'
    assert parsed['stack'] == [['worker_setup', 1]]


def test_declared_journals_replay_two_distinct_pending_and_stopped_tickets(tmp_path):
    c = load('native_context_receipt_diagnostic_catalogue')
    import context_preparation_budget as budget
    import dataclasses
    declarations = []
    for index, stopped in enumerate((False, True)):
        identity = budget.BudgetIdentity(*(str(index+1)*64 for _ in range(5)))
        state = budget._State(identity)
        clock = budget.ClockSample('11111111-2222-3333-4444-555555555555', 10**9, 1700000000*10**9, 10**9)
        raw = b''
        for event, value in [('init', dict(identity=dataclasses.asdict(identity), clock=dataclasses.asdict(clock),
            total_cpu_ns=budget.TOTAL_CPU_NS, portion_cpu_ns=budget.PORTION_CPU_NS, elapsed_ns=budget.TOTAL_ELAPSED_NS)),
            ('reserve', dict(clock=dataclasses.asdict(clock), portion_digest='a'*64, cpu_ns=300*10**9))] + (
                [('stop', dict(reason='unmeasured'))] if stopped else []):
            line = budget._encode_record(state, event, value)
            raw += line
            state = budget._replay(raw, identity)
        path = tmp_path / (str(index) + '.jsonl')
        path.write_bytes(raw)
        snapshot = state.snapshot()
        declarations.append(dict(path=path.name, identity=dataclasses.asdict(identity), journal_head=snapshot.journal_digest,
            ticket=dataclasses.asdict(snapshot.pending), state=snapshot.status, charged_cpu_ns=300*10**9,
            settled_cpu_ns=0, category='synthetic-protocol'))
    assert c.validate_journals(tmp_path, declarations, observe=True) == declarations
    altered = [dict(x) for x in declarations]
    altered[0]['state'] = 'stopped'
    with pytest.raises(Exception):
        c.validate_journals(tmp_path, altered, observe=True)


def test_historical_hardlink_occupancy_is_inert_but_active_slots_reject_it(tmp_path):
    c = load('native_context_receipt_diagnostic_catalogue')
    (tmp_path / 'data').write_bytes(b'known retained bytes')
    os.link(tmp_path / 'data', tmp_path / 'hardlink')
    record = c.retained_root(tmp_path)
    assert record['files'] == 2 and record['symlinks'] == 0
    assert record['logical'] >= 40
    with pytest.raises(Exception):
        c.sample_exact_slots(tmp_path, {'data': 32, 'hardlink': 32}, 1024**2)


def test_append_failure_restores_all_actual_wrappers_and_retains_prefix(tmp_path, monkeypatch):
    w = load('native_context_receipt_diagnostic_worker')
    c = load('native_context_receipt_diagnostic_catalogue')
    from test_context_storage_receipt_corpus import source
    from context_storage_v2 import receipt_corpus as owner
    from context_growth_profile import build_growth_profile
    from datetime import datetime
    p = c.fixed_profile()
    actual = owner._Build.append_one
    def fail(build, *args, **kwargs):
        if build.submitted == 2:
            raise ValueError('fixed injected boundary')
        return actual(build, *args, **kwargs)
    monkeypatch.setattr(owner._Build, 'append_one', fail)
    callables = (owner.copy_legacy, owner._Build.run, owner._Build.close_writer, owner._hash_file)
    with source(tmp_path) as (path, sealed, held):
        profile = build_growth_profile('atp-heavy', baseline_sha256=sealed, start_at=datetime.fromisoformat(p['start_at']),
            first_native_id=p['first_native_id'], atp_fixture=p['atp_fixture'])
        work = tmp_path / 'work'
        (work / 'corpus').mkdir(parents=True)
        progress = c.Progress(work / 'progress.jsonl')
        try:
            with pytest.raises(ValueError):
                w.measure_corpus(held, profile, sealed, work, progress)
        finally:
            progress.close()
    assert callables == (owner.copy_legacy, owner._Build.run, owner._Build.close_writer, owner._hash_file)
    assert owner._Build.append_one is fail
    prefix = c.parse_progress((work / 'progress.jsonl').read_bytes())
    assert prefix['completed'] == 2 and not prefix['terminal']
    assert (work / 'corpus/legacy-copy.sqlite').is_file()


def test_nonterminal_native_result_never_enters_success_parser(tmp_path):
    d = load('native_context_receipt_diagnostic')
    from types import SimpleNamespace
    for exit_code, stop_reason, readback in [(-9, 'wall', None), (1, None, object()), (0, 'rss', object()), (0, None, None)]:
        result = SimpleNamespace(exit_code=exit_code, stop_reason=stop_reason, kernel_readback=readback)
        with pytest.raises(Exception):
            d.accept_result({}, result, {}, b'', tmp_path)


def manifest_fixture(c):
    import copy
    code = []
    for name in sorted(set(c.PINS | c.HELPERS) | {c.PARENT_NAME, c.CATALOGUE_NAME, c.WORKER_NAME}):
        raw = (ROOT/name).read_bytes()
        code.append(dict(path=name, size=len(raw), sha256=c.digest(raw)))
    dependencies = [dict(path=name + ('/fixture.py' if '.' not in name else ''), size=1, sha256='f'*64)
                    for name in c.old()['PACKAGES']]
    dependencies.sort(key=lambda x: x['path'])
    runtime = dict(executable='/usr/bin/python3.12', executable_sha256='a'*64, python='fixture',
        kernel=['Linux', 'fixture', 'fixture', 'fixture', 'x86_64'], stdlib_search_path=['/usr/lib/python3.12'],
        closure_status='observed-system-runtime-not-transitive-B-closure')
    installation = dict(machine_id_sha256='b'*64, executable=runtime['executable'], executable_sha256='a'*64)
    retained = dict(format='betboy-receipt-diagnostic-retained-v1', backup_rollback_reserve=4*1024**3,
        roots=[dict(path='/var/lib/old-qa', identity=[1, 2, 16832, 2, 4096, 1, 1], membership_sha256='c'*64,
            files=1, directories=1, symlinks=0, logical=4097, allocated=8192, category='historical-qa', charged_cpu_ns=None, journals=[])])
    raw = c.canonical(retained)
    value = dict(format=c.FORMAT, commit='d'*40, archive=dict(size=1024, sha256='e'*64), code=code,
        dependencies=dependencies, dependency_root=c.old()['DEPENDENCY_SOURCE'].as_posix(), packages=list(c.old()['PACKAGES']),
        timezone_data=c.old()['timezone_manifest'](), runtime=runtime, baseline=c.baseline(), profile=c.fixed_profile(),
        retained=dict(path='/var/lib/task61-inputs/retained.json', size=len(raw), sha256=c.digest(raw)))
    value['admission'] = dict(registry_directory='/var/lib/task61-registry', job_directory='/var/lib/task61-job',
        purpose='context-receipt-corpus-diagnostic-v1', profile_kind='atp-heavy', identity=c.budget_identity(value, runtime, installation),
        retained_history_digest=c.digest(raw))
    value['allocation'] = c.allocation_plan(dict(value, _retained_data=retained), archive_path='/var/lib/task61-inputs/code.tar',
        manifest_path='/var/lib/task61-inputs/manifest.json', retained_path=value['retained']['path'])
    value['admission']['plan_digest'] = c.digest(c.canonical({k:v for k,v in value.items() if k != 'admission'}))
    return value, raw, runtime, installation


def test_closed_manifest_recomputes_complete_acyclic_identity_and_slot_plan():
    import copy
    c = load('native_context_receipt_diagnostic_catalogue')
    value, retained, runtime, installation = manifest_fixture(c)
    assert c.validate_manifest(value, 'd'*40, retained_raw=retained, runtime=runtime, installation=installation) == value
    for mutate in [lambda x: x.update(extra=True), lambda x: x['admission']['identity'].update(input_digest='0'*64),
                   lambda x: x['allocation']['slots'].update({'unplanned': 1}),
                   lambda x: x['profile'].update(stop=1), lambda x: x['baseline'].update(size=1),
                   lambda x: x['code'][0].update(sha256='0'*64)]:
        changed = copy.deepcopy(value)
        mutate(changed)
        changed['admission']['plan_digest'] = c.digest(c.canonical({k:v for k,v in changed.items() if k != 'admission'}))
        with pytest.raises(Exception):
            c.validate_manifest(changed, 'd'*40, retained_raw=retained, runtime=runtime, installation=installation)


def test_space_counts_occupied_history_once_and_all_future_reserve():
    d = load('native_context_receipt_diagnostic')
    # 20GiB old occupancy is already absent from f_bavail, never future growth.
    assert d.check_space(free=12*1024**3, total=2*1024**3, occupied=1024**3,
        backup_rollback_reserve=4*1024**3) == 9*1024**3
    with pytest.raises(Exception):
        d.check_space(free=9*1024**3-1, total=2*1024**3, occupied=1024**3,
            backup_rollback_reserve=4*1024**3)


@pytest.mark.parametrize('fault', ['pid', 'ppid', 'uid', 'gid', 'argv', 'cap', 'cpu', 'fsize', 'guard', 'original', 'raise', 'return'])
def test_portable_exact_prefix_failures_exit_without_owner_unwind(tmp_path, monkeypatch, fault):
    d = load('native_context_receipt_diagnostic')
    import types
    import io
    import builtins
    class Exited(BaseException):
        pass
    resource = types.SimpleNamespace(RLIMIT_CPU=0, RLIMIT_FSIZE=1)
    limits = {0: (60,60), 1: (512*1024**2,512*1024**2)}
    resource.getrlimit = lambda key: limits[key]
    def setlimit(key, value):
        if fault == 'raise':
            raise PermissionError('test capability refusal')
        limits[key] = value
    resource.setrlimit = setlimit
    monkeypatch.setitem(sys.modules, 'resource', resource)
    supervisor = types.ModuleType('context_preparation_supervisor')
    exec('_called=[]\ndef _child_run_python(*args):\n _called.append(True)\n return None\n', supervisor.__dict__)
    original = supervisor._child_run_python
    guard = object()
    prefix = d.child_prefix(supervisor, original, parent_pid=100, worker='/sealed/worker.py', cwd='/work', guard=guard)
    supervisor._child_run_python = prefix
    monkeypatch.setattr(os, 'getpid', lambda: 100 if fault == 'pid' else 101)
    monkeypatch.setattr(os, 'getppid', lambda: 99 if fault == 'ppid' else 100)
    monkeypatch.setattr(os, 'getresuid', lambda: (1,1,1) if fault == 'uid' else (0,0,0), raising=False)
    monkeypatch.setattr(os, 'getresgid', lambda: (1,1,1) if fault == 'gid' else (0,0,0), raising=False)
    monkeypatch.setattr(os, 'fstat', lambda fd: types.SimpleNamespace(st_mode=(stat.S_IFCHR if fd == 5 else stat.S_IFIFO)))
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: io.BytesIO(b'CapEff:\t0000000000000000\n' if fault == 'cap' else b'CapEff:\t0000000001000000\n'))
    monkeypatch.setattr(os, '_exit', lambda code: (_ for _ in ()).throw(Exited(code)))
    if fault == 'cpu':
        limits[0] = (59,59)
    if fault == 'original':
        original.__code__ = (lambda *args: None).__code__
    with pytest.raises(Exited) as exit_info:
        prefix(('/sealed/worker.py', 'wrong' if fault == 'argv' else 'receipt-v1'), 65534, 65534, '/work', 3, 4, 5,
               1 if fault == 'fsize' else 512*1024**2, 240, object() if fault == 'guard' else guard)
    assert exit_info.value.args == (125,)
    assert supervisor._called == ([True] if fault == 'return' else [])


def test_launch_uses_unchanged_supervisor_exact_request_contract(tmp_path, monkeypatch):
    d = load('native_context_receipt_diagnostic')
    import context_preparation_supervisor as supervisor
    import types
    monkeypatch.setitem(sys.modules, 'resource', types.SimpleNamespace(RLIMIT_CPU=0, getrlimit=lambda key: (60,60)))
    original = supervisor._child_run_python
    observed = []
    def validate(argv, **kwargs):
        supervisor._validate_request(argv, **kwargs)
        observed.append((argv, kwargs))
        return 'validated-no-native-fork'
    monkeypatch.setattr(supervisor, 'run_single_process', validate)
    helpers = dict(context_preparation_supervisor=supervisor, child_original=original, context_preparation_process_guard=object())
    result = d.launch_once(helpers, tmp_path/'worker.py', tmp_path, 7)
    assert result == 'validated-no-native-fork' and len(observed) == 1
    assert supervisor._child_run_python is original


@pytest.mark.parametrize('mutation', ['table', 'source', 'ledger'])
def test_real_owner_rejects_physical_corruption_and_retains_failed_outputs(tmp_path, monkeypatch, mutation):
    w = load('native_context_receipt_diagnostic_worker')
    c = load('native_context_receipt_diagnostic_catalogue')
    from test_context_storage_receipt_corpus import source
    from context_storage_v2 import receipt_corpus as owner
    from context_growth_profile import build_growth_profile
    from datetime import datetime
    from contextlib import closing
    import sqlite3
    p = c.fixed_profile()
    if mutation in ('table', 'source'):
        actual = owner.copy_legacy
        def corrupt(*args, **kwargs):
            copied = actual(*args, **kwargs)
            if mutation == 'table':
                with closing(sqlite3.connect(copied.path)) as connection:
                    connection.execute("UPDATE artifacts SET payload=x'61'")
                    connection.commit()
            else:
                target = tmp_path/'source.sqlite'
                info = target.stat()
                os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns+10000000))
            return copied
        monkeypatch.setattr(owner, 'copy_legacy', corrupt)
    else:
        actual = owner._Ledger.append
        def corrupt(ledger, *args, **kwargs):
            result = actual(ledger, *args, **kwargs)
            if ledger.count == 1:
                # Actual first ledger write then physical truncation; next
                # original check/read must reject rather than publish success.
                os.ftruncate(ledger.fd, 2*1024**2)
            return result
        monkeypatch.setattr(owner._Ledger, 'append', corrupt)
    with source(tmp_path) as (path, sealed, held):
        profile = build_growth_profile('atp-heavy', baseline_sha256=sealed, start_at=datetime.fromisoformat(p['start_at']),
            first_native_id=p['first_native_id'], atp_fixture=p['atp_fixture'])
        work = tmp_path/'work'
        (work/'corpus').mkdir(parents=True)
        progress = c.Progress(work/'progress.jsonl')
        try:
            with pytest.raises(Exception):
                w.measure_corpus(held, profile, sealed, work, progress)
        finally:
            progress.close()
    prefix = c.parse_progress((work/'progress.jsonl').read_bytes())
    assert not prefix['terminal'] and prefix['completed'] == 0
    assert (work/'corpus/legacy-copy.sqlite').is_file()


def test_native_terminal_retention_bounds_failed_pipe_prefixes_without_claiming_full_output():
    import context_preparation_supervisor as supervisor
    d = load('native_context_receipt_diagnostic')
    result = supervisor.NativeRunResult(-9, 'output_limit', None, 1, 1, 1, 1, 1024**2,
        'a'*64, b'x'*(1024**2-10), b'e'*10, 4*1024**3, 1)
    value = d.native_data(result)
    assert len(bytes.fromhex(value['stdout_prefix'])) == 128*1024
    assert value['stdout_prefix_retained_size'] == 1024**2-10
    assert value['stdout_prefix_truncated'] is True
    assert len(json.dumps(value)) < 1024**2


@pytest.mark.parametrize('raw', [b'{"n":1,"n":2}', b'{"n":1.5}', b'{"n":NaN}', b'{"n":Infinity}'])
def test_closed_json_rejects_duplicate_float_and_nonfinite(raw):
    c = load('native_context_receipt_diagnostic_catalogue')
    with pytest.raises(Exception):
        c.decode(raw)


def test_progress_bounds_unknown_fields_and_poisoned_partial_write(tmp_path, monkeypatch):
    c = load('native_context_receipt_diagnostic_catalogue')
    with pytest.raises(Exception):
        c.parse_progress(b'x'*262145)
    with pytest.raises(Exception):
        c.parse_progress(b'x'*2048)
    p = c.Progress(tmp_path/'progress.jsonl')
    with pytest.raises(Exception):
        p.append(dict(body(), payload='forbidden'))
    actual = os.write
    def partial(fd, raw):
        actual(fd, raw[:7])
        raise OSError('partial actual write')
    monkeypatch.setattr(os, 'write', partial)
    with pytest.raises(OSError):
        p.append(body())
    with pytest.raises(Exception):
        p.append(body())
    p.close()
    parsed = c.parse_progress((tmp_path/'progress.jsonl').read_bytes())
    assert parsed['frames'] == [] and parsed['incomplete_tail_bytes'] == 7


def test_namespace_checks_every_existing_scalar_against_full_future_range(tmp_path):
    w = load('native_context_receipt_diagnostic_worker')
    from types import SimpleNamespace
    from datetime import datetime, timezone
    import sqlite3
    from contextlib import closing
    profile = SimpleNamespace(first_native_id=8000000000000000000,
        start_at=datetime(2026,9,12,tzinfo=timezone.utc))
    with closing(sqlite3.connect(':memory:')) as con:
        con.execute('CREATE TABLE context_observations(event_key TEXT,observed_at TEXT)')
        con.execute('INSERT INTO context_observations VALUES(?,?)', ('espn:tennis:ATP:match:1','2026-09-11T00:00:00+00:00'))
        w.namespace_admission(con, profile)
        con.execute('INSERT INTO context_observations VALUES(?,?)',
            ('espn:tennis:ATP:match:8000000000000489999', '2026-09-11T00:00:00+00:00'))
        with pytest.raises(Exception):
            w.namespace_admission(con, profile)
        con.execute('DELETE FROM context_observations WHERE rowid=2')
        con.execute('INSERT INTO context_observations VALUES(?,?)', ('other', '2026-09-18T00:00:00.069999+00:00'))
        with pytest.raises(Exception):
            w.namespace_admission(con, profile)


def test_source_close_still_closes_actual_connection_if_progress_io_fails(tmp_path):
    w = load('native_context_receipt_diagnostic_worker')
    c = load('native_context_receipt_diagnostic_catalogue')
    import sqlite3
    connection = sqlite3.connect(':memory:')
    progress = c.Progress(tmp_path/'progress.jsonl')
    recorder = w.PhaseRecorder(progress)
    try:
        with pytest.raises(Exception):
            w.close_source(recorder, connection)
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')
    finally:
        progress.close()


class RejectedAdmission(RuntimeError):
    pass


def actual_main_fixture(tmp_path, monkeypatch):
    """Real main/I/O; substitute only native/read-only catalogue preflight.

    The sealed baseline's fixed 270MB fingerprint check is an explicit fixture,
    not a claim about local synthetic bytes. Active-file FDs/stats and directory
    sampling remain actual. No write/launch seam is stubbed into success.
    """
    import types
    import signal
    import time
    import context_preparation_budget as budget
    d = load('native_context_receipt_diagnostic')
    c = load('native_context_receipt_diagnostic_catalogue')
    job, registry, controls = tmp_path/'job', tmp_path/'registry', tmp_path/'controls'
    job.mkdir(); registry.mkdir(); controls.mkdir()
    archive, manifest_path, retained_path, baseline = [controls/n for n in ('code.tar','manifest.json','retained.json','baseline.db')]
    archive.write_bytes(b'reviewed archive fixture')
    retained_path.write_bytes(b'{}')
    baseline.write_bytes(b'actual eight byte fixture')
    events = []
    def forbidden(name):
        def call(*a, **k):
            events.append(name)
            raise AssertionError('actual main reached ' + name + ' before admission')
        return call
    for name in ('write_new', 'copy_exact', 'launch_once'):
        monkeypatch.setattr(d, name, forbidden(name))
    def reject(*a, **k):
        events.append('admission')
        raise RejectedAdmission('actual Task60 call site rejected')
    runtime, installation = {'fixture':'runtime'}, {'fixture':'installation'}
    sources = {'tests/fixture.py': b'pass\n'}
    manifest = dict(archive=dict(size=archive.stat().st_size,sha256=c.digest(archive.read_bytes())),
        code=[], dependencies=[], packages=[], dependency_root=str(controls),
        admission=dict(job_directory=str(job),registry_directory=str(registry), purpose='context-receipt-corpus-diagnostic-v1',
            plan_digest='a'*64,identity=dict(zip(('input_digest','execution_digest','runtime_digest','installation_digest','profile_digest'),
                (x*64 for x in 'abcde')))),
        retained=dict(path=str(retained_path), sha256=c.digest(retained_path.read_bytes())))
    manifest['allocation'] = dict(inputs=[dict(path=str(p),cap=8*1024**2 if p == manifest_path else p.stat().st_size)
        for p in (archive,retained_path,baseline)] + [dict(path=str(manifest_path),cap=8*1024**2)],
        input_metadata_cap=128*1024**2, active_input_cap=4*1024**3,total=2*1024**3,backup_rollback_reserve=4*1024**3)
    manifest['allocation']['inputs'].sort(key=lambda x:x['path'])
    manifest_path.write_bytes(c.canonical(manifest))
    actual_old = c.old()
    old = dict(actual_old)
    actual_file_record = old['file_record']
    def file_record(path, maximum=c.MEMBER_CAP):
        if Path(path) == baseline and maximum == 270233600:
            return dict(size=270233600,sha256='f'*64)
        return actual_file_record(path, maximum)
    old.update(file_record=file_record, archive_members=lambda raw,code:sources, walk=lambda *a:[])
    monkeypatch.setattr(c, '_OLD_CATALOGUE', old)
    monkeypatch.setattr(c, 'validate_manifest', lambda value,*a,**k:value)
    monkeypatch.setattr(c, 'validate_retained', lambda *a,**k:{})
    monkeypatch.setattr(c, 'runtime_observation', lambda:runtime)
    monkeypatch.setattr(c, 'installation_observation', lambda runtime:installation)
    monkeypatch.setattr(c, 'bootstrap_source', lambda sources:b'held bootstrap fixture')
    monkeypatch.setattr(c, 'protected', lambda path,**k:Path(path).lstat())
    monkeypatch.setattr(c, 'BASELINE_PATH', str(baseline))
    monkeypatch.setattr(c, 'BASELINE_SHA', 'f'*64)
    monkeypatch.setattr(d, '_REVIEWED_BOOTSTRAP', sources, raising=False)
    monkeypatch.setattr(d, 'startup', lambda:(10**9,3601*10**9))
    monkeypatch.setattr(d, 'load_catalogue', lambda sources:c.__dict__)
    monkeypatch.setattr(d, 'load_helpers', lambda *a:dict(
        context_preparation_supervisor=types.SimpleNamespace(_require_native_owner=lambda:None),
        context_preparation_budget=budget, admission={'admit_diagnostic':reject}))
    monkeypatch.setattr(signal, 'SIGALRM', 999, raising=False)
    monkeypatch.setattr(signal, 'ITIMER_REAL', 0, raising=False)
    monkeypatch.setattr(signal, 'signal', lambda *a:None)
    monkeypatch.setattr(signal, 'setitimer', lambda *a:None, raising=False)
    monkeypatch.setattr(time, 'CLOCK_BOOTTIME', 7, raising=False)
    monkeypatch.setattr(time, 'clock_gettime_ns', lambda key:2*10**9, raising=False)
    monkeypatch.setattr(os, 'statvfs', lambda path:types.SimpleNamespace(f_bavail=40*1024**3,f_frsize=1),raising=False)
    values = [str(manifest_path),c.digest(manifest_path.read_bytes()),str(archive),str(job),str(registry),'d'*40,
              c.digest(b'held bootstrap fixture')]
    argv = [part for pair in zip(d.FLAGS,values) for part in pair]
    return d,c,argv,events,job,baseline


@pytest.mark.parametrize('overrun', ['file', 'metadata'])
def test_actual_main_rejects_active_physical_or_metadata_overrun_before_admission(tmp_path,monkeypatch,overrun):
    d,c,argv,events,job,baseline = actual_main_fixture(tmp_path,monkeypatch)
    actual = c._allocation
    target = baseline.stat().st_ino
    def allocated(info):
        if overrun == 'file' and info.st_ino == target:
            return 4097  # input logical length <one block, physical slot one block.
        if overrun == 'metadata' and stat.S_ISDIR(info.st_mode):
            return 129*1024**2
        return actual(info)
    monkeypatch.setattr(c,'_allocation',allocated)
    with pytest.raises(c.DiagnosticError):
        d.main(argv)
    assert events == [] and list(job.iterdir()) == []


def test_fully_rehashed_manifest_cannot_change_exact_four_gib_backup_reserve():
    import copy
    c=load('native_context_receipt_diagnostic_catalogue')
    for reserve in (0,4*1024**3-1,4*1024**3+1):
        value,raw,runtime,installation=manifest_fixture(c)
        retained=c.decode(raw)
        retained['backup_rollback_reserve']=reserve
        raw=c.canonical(retained)
        value['retained'].update(size=len(raw),sha256=c.digest(raw))
        value['admission']['retained_history_digest']=c.digest(raw)
        value['allocation']=c.allocation_plan(dict(value,_retained_data=retained),archive_path='/var/lib/task61-inputs/code.tar',
            manifest_path='/var/lib/task61-inputs/manifest.json',retained_path=value['retained']['path'])
        value['admission']['plan_digest']=c.digest(c.canonical({k:v for k,v in value.items() if k!='admission'}))
        with pytest.raises(Exception):
            c.validate_manifest(value,'d'*40,retained_raw=raw,runtime=runtime,installation=installation)


@pytest.mark.parametrize('fault',['reserve','unexpected','overallocated'])
def test_actual_copy_phase_checks_whole_reserve_and_exact_worker_slots(tmp_path,monkeypatch,fault):
    w=load('native_context_receipt_diagnostic_worker')
    c=load('native_context_receipt_diagnostic_catalogue')
    from test_context_storage_receipt_corpus import source
    from context_storage_v2 import receipt_corpus as owner
    from context_growth_profile import build_growth_profile
    from datetime import datetime
    import types
    manifest,_,_,_=manifest_fixture(c)
    work=tmp_path/'work'
    (work/'corpus').mkdir(parents=True)
    p=c.Progress(work/'progress.jsonl')
    checker=w.WorkerAllocation(c.__dict__,manifest['allocation'],work)
    recorder=w.PhaseRecorder(p,allocation_check=checker)
    actual_copy=owner.copy_legacy
    free={'bytes':40*1024**3}
    monkeypatch.setattr(os,'statvfs',lambda path:types.SimpleNamespace(f_bavail=free['bytes'],f_frsize=1),raising=False)
    actual_allocation=c._allocation
    corrupt_inode={'value':None}
    def allocated(info):
        if info.st_ino==corrupt_inode['value']:
            return 512*1024**2+4096
        return actual_allocation(info)
    monkeypatch.setattr(c,'_allocation',allocated)
    def copy(*args,**kwargs):
        result=actual_copy(*args,**kwargs)
        if fault=='reserve':
            free['bytes']=8*1024**3  # above old4GiB threshold, below complete reserve.
        elif fault=='unexpected':
            (work/'unknown').write_bytes(b'unplanned')
        else:
            corrupt_inode['value']=result.path.stat().st_ino
        return result
    monkeypatch.setattr(owner,'copy_legacy',copy)
    with source(tmp_path) as (path,sealed,held):
        profile=build_growth_profile('atp-heavy',baseline_sha256=sealed,
            start_at=datetime.fromisoformat(c.fixed_profile()['start_at']),first_native_id=8000000000000000000,
            atp_fixture=c.fixed_profile()['atp_fixture'])
        try:
            with pytest.raises(Exception):
                w.measure_corpus(held,profile,sealed,work,p,recorder=recorder)
        finally:
            p.close()
    prefix=c.parse_progress((work/'progress.jsonl').read_bytes())
    assert prefix['completed']==0 and not prefix['terminal']
    assert (work/'corpus/legacy-copy.sqlite').is_file()


@pytest.mark.parametrize('drift', ['physical', 'file_epoch', 'directory_epoch', 'aggregate'])
def test_active_input_binding_rejects_later_drift_and_measures_union(tmp_path, monkeypatch, drift):
    from contextlib import ExitStack
    c=load('native_context_receipt_diagnostic_catalogue')
    path=tmp_path/'input'
    path.write_bytes(b'actual input')
    plan=dict(inputs=[dict(path=str(path),cap=8192)],input_metadata_cap=128*1024**2,
              active_input_cap=4*1024**3,total=1024**3)
    actual=c._allocation
    physical={'extra':0}
    monkeypatch.setattr(c,'_allocation',lambda info:actual(info)+(physical['extra'] if info.st_ino==path.stat().st_ino else 0))
    with ExitStack() as held:
        binding=c.hold_active_inputs(held,plan)
        initial=c.sample_active_inputs(binding,plan)
        assert initial['files'][0]['allocated']==4096
        assert {r['path'] for r in initial['directories']} == {str(p) for p in path.parents}
        assert initial['allocated']==4096+initial['metadata_allocated']
        if drift=='physical':
            physical['extra']=4096  # still within slot, but no longer the bound observation.
        elif drift=='aggregate':
            plan['total']=4*1024**3
        elif drift=='file_epoch':
            before=path.stat()
            os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+1000000000))
        else:
            before=tmp_path.stat()
            os.utime(tmp_path,ns=(before.st_atime_ns,before.st_mtime_ns+1000000000))
        with pytest.raises(c.DiagnosticError):
            c.sample_active_inputs(binding,plan,previous=initial)
        # Real held contexts intentionally reject epoch mutations when closed.
        if drift in ('file_epoch','directory_epoch'):
            with pytest.raises(Exception):
                held.close()


def test_transport_uses_held_template_after_path_changes(tmp_path):
    import shutil
    shell=shutil.which('pwsh')
    if shell is None:
        pytest.skip('PowerShell7 required for local transport fixture')
    transport=ROOT/'.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task61-native-prefix-run.ps1'
    template=transport.with_name('task61-native-prefix-entry.py')
    fixture=tmp_path/'template.py'
    fixture.write_bytes(template.read_bytes())
    # Evaluate actual parsed acquisition/replacement statements only. No bundle
    # collection, SSH branch, production template edit, or changed literal pin.
    script=r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:TASK61_TRANSPORT_FIXTURE_SCRIPT,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'transport syntax error'}
$prefixTemplatePath=$env:TASK61_TRANSPORT_FIXTURE_TEMPLATE
$prefixBundleBytes=[byte[]]@(1,2,3); $Mode='prepare'
$items=@($ast.EndBlock.Statements)
$first=3
$pins=0
while($items[$pins].Extent.Text -notmatch '^\$prefixPins\s*='){$pins++}
for($i=$first;$i -lt $pins;$i++){. ([scriptblock]::Create($items[$i].Extent.Text))}
[IO.File]::WriteAllText($prefixTemplatePath,'unreviewed replacement')
$after=0
while($items[$after].Extent.Text -notmatch '^\$prefixBundleBytes\s*='){$after++}
for($i=$after+1;$i -lt $items.Count;$i++){
  if($items[$i].Extent.Text -match '^if \(\$DryRun\)'){break}
  . ([scriptblock]::Create($items[$i].Extent.Text))
}
if($prefixProgram.Contains('unreviewed replacement')){throw 'reopened template'}
if(-not $prefixProgram.Contains('AQID')){throw 'held replacement not used'}
'held_template_ok syntax_ok'
'''
    completed=subprocess.run([shell,'-NoProfile','-NonInteractive','-Command',script],
        env=dict(os.environ,TASK61_TRANSPORT_FIXTURE_SCRIPT=str(transport),TASK61_TRANSPORT_FIXTURE_TEMPLATE=str(fixture)),
        capture_output=True,timeout=30)
    assert completed.returncode==0, (completed.stdout,completed.stderr)
    assert b'held_template_ok syntax_ok' in completed.stdout
