"""Admission protocol I/O tests; simulated custody is NOT native Linux proof."""
from dataclasses import replace
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

import context_preparation_budget as budget


SOURCE = Path(__file__).with_name('native_context_diagnostic_admission.py')
NS = 10**9
BOOT = '11111111-2222-3333-4444-555555555555'


def test_admission_implementation_exists():
    assert SOURCE.is_file(), 'missing protected one-shot admission implementation'


@pytest.fixture
def module():
    assert SOURCE.is_file(), 'missing protected one-shot admission implementation'
    spec = importlib.util.spec_from_file_location('admission_test_subject', SOURCE)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class PortableNamespace:
    """Real files and helper _attach; no Linux/DAC/flock/directory-fsync claim."""
    held = set()

    def __init__(self, module, registry, job, clock):
        self.module, self.registry_path, self.job_path = module, registry, job
        self.clock = clock
        self.closed = False
        self.registry_identity = self.ident(registry)
        self.job_identity = self.ident(job)
        self.process = dict(pid=os.getpid(), start_ticks=10, ticks_per_second=1,
                            start_boot_ns=10*NS, boot_id=BOOT,
                            deadline_boot_ns=3610*NS)
        self.key = str(registry)
        if self.key in self.held:
            raise RuntimeError('lock contention')
        self.held.add(self.key)
        self.store = None

    @staticmethod
    def ident(path):
        info = path.stat()
        return dict(path=str(path), device=info.st_dev, inode=info.st_ino)

    def check(self):
        assert not self.closed and self.key in self.held, 'lost lock custody'
        assert self.ident(self.registry_path) == self.registry_identity, 'registry replaced'
        assert self.ident(self.job_path) == self.job_identity, 'job replaced'

    def names(self):
        self.check()
        return set(p.name for p in self.registry_path.iterdir())

    def open_registry(self, create):
        flags = os.O_RDWR | getattr(os, 'O_BINARY', 0)
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        path = self.registry_path / self.module.REGISTRY_NAME
        self.store = budget._FileJournal(os.open(path, flags, 0o600))
        return self.store

    def directory_sync(self):
        self.check()  # Explicit portable seam, not OS directory durability.

    def create_budget(self, identity):
        path = self.registry_path / (budget._hash(budget._identity(identity)) + '.jsonl')
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
        return budget.PreparationBudget._attach(budget._FileJournal(fd), identity, create=True)

    def journal(self, name):
        self.check()
        path = self.registry_path / name
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_nlink != 1:
            raise RuntimeError('linked journal')
        with path.open('rb') as stream:
            data = stream.read(1024*1024+1)
        return data, info.st_dev, info.st_ino

    def process_identity(self):
        return dict(self.process)

    def sync_journal(self, name, raw, device, inode):
        assert self.journal(name) == (raw, device, inode)
        with (self.registry_path/name).open('r+b') as stream:
            os.fsync(stream.fileno())
        self.directory_sync()
        assert self.journal(name) == (raw, device, inode)

    def close(self):
        if not self.closed:
            self.closed = True
            self.held.remove(self.key)


@pytest.fixture
def setup(module, tmp_path, monkeypatch):
    registry, job = tmp_path/'registry', tmp_path/'job'
    registry.mkdir()
    job.mkdir()
    clock = dict(now=100*NS, boot=BOOT, offset=1700000000*NS)
    monkeypatch.setattr(budget, '_system_clock', lambda: budget.ClockSample(
        clock['boot'], clock['now'], clock['now']+clock['offset'], clock['now']))
    identity = budget.BudgetIdentity(*(c*64 for c in 'abcde'))
    def admit(**changes):
        args = dict(identity=identity, purpose='context-receipt-corpus-diagnostic-v1',
                    profile_kind='atp-heavy', plan_digest='1'*64, retained_history_digest='2'*64)
        target = changes.pop('job', job)
        args.update(changes)
        ns = PortableNamespace(module, registry, target, clock)
        return module._admit_protocol(ns, **args)
    yield module, registry, job, clock, identity, admit
    # Only descriptor custody cleanup for failing tests; no file repair/reset.


def records(registry, module):
    return [json.loads(line) for line in (registry/module.REGISTRY_NAME).read_bytes().splitlines()]


def test_first_requires_real_reserved_budget_and_terminal_retains_charge(setup):
    m, r, j, clock, identity, admit = setup
    owner = admit()
    owner.assert_admitted()
    state = owner.snapshot()
    assert state['binding']['ticket']['cpu_ns'] == 300*NS
    assert state['binding']['deadline_boot_ns'] == 3610*NS
    assert [x['record']['event'] for x in records(r,m)] == ['admitting','admitted']
    journal = r/state['binding']['journal']
    actual = budget._replay(journal.read_bytes(), identity).snapshot()
    assert actual.status == 'pending' and actual.charged_cpu_ns == 300*NS
    owner.close()
    stopped = budget._replay(journal.read_bytes(), identity).snapshot()
    assert stopped.status == 'stopped' and stopped.charged_cpu_ns == 300*NS
    assert stopped.settled_cpu_ns == 0 and stopped.pending == actual.pending
    assert records(r,m)[-1]['record']['body']['journal_head'] == stopped.journal_digest
    with pytest.raises(Exception):
        owner.assert_admitted()


@pytest.mark.parametrize('change', ['none','job','profile','plan','clock','history'])
def test_family_cannot_renew_by_nuisance_identity_changes(setup, change):
    m,r,j,clock,identity,admit = setup
    admit().close()
    before = {p.name:p.read_bytes() for p in r.iterdir()}
    args = {}
    if change == 'job':
        other=j.with_name('other'); other.mkdir(); args['job']=other
    if change == 'profile': args['identity']=replace(identity,profile_digest='f'*64)
    if change == 'plan': args['plan_digest']='f'*64
    if change == 'history': args['retained_history_digest']='f'*64
    if change == 'clock': clock['now']+=NS
    with pytest.raises(Exception): admit(**args)
    assert {p.name:p.read_bytes() for p in r.iterdir()} == before


def test_new_reviewed_family_preserves_expired_historical_charge(setup):
    m,r,j,clock,identity,admit = setup
    with admit() as first: name=first.snapshot()['binding']['journal']
    before=(r/name).read_bytes()
    # Historical replay has no current-deadline renewal or permission.
    clock['now']=3700*NS
    original=PortableNamespace.process_identity
    # The portable parent is a distinct simulated process with original newer start.
    def later(self):
        value=original(self); value.update(start_ticks=200,start_boot_ns=200*NS,deadline_boot_ns=3800*NS)
        return value
    # New process support is supplied via test adapter only.
    from unittest.mock import patch
    with patch.object(PortableNamespace,'process_identity',later):
        with admit(identity=replace(identity,input_digest='f'*64)) as second:
            assert second.snapshot()['binding']['ticket']['cpu_ns']==300*NS
    assert (r/name).read_bytes()==before


def test_snapshot_and_supplied_identity_mutations_do_not_change_owner(setup):
    m,r,j,clock,identity,admit=setup
    owner=admit()
    snapshot=owner.snapshot()
    with pytest.raises(TypeError): snapshot['binding']['ticket']['cpu_ns']=1
    object.__setattr__(identity,'input_digest','f'*64)
    owner.assert_admitted()
    assert owner.snapshot()['admission']['identity']['input_digest']=='a'*64
    owner.close()


@pytest.mark.parametrize('change',['boot','rollback','wall','deadline','process','lock','job'])
def test_changed_live_custody_or_time_permanently_poison_owner(setup,change):
    m,r,j,clock,identity,admit=setup
    owner=admit()
    if change=='boot': clock['boot']='66666666-2222-3333-4444-555555555555'
    elif change=='rollback': clock['now']-=1
    elif change=='wall': clock['offset']+=1
    elif change=='deadline': clock['now']=3610*NS
    elif change=='process': owner._namespace.process['pid']+=1
    elif change=='lock': PortableNamespace.held.remove(str(r))
    else: j.rename(j.with_name('old-job')); j.mkdir()
    with pytest.raises(Exception): owner.assert_admitted()
    clock.update(now=100*NS,boot=BOOT,offset=1700000000*NS)
    if change=='lock': PortableNamespace.held.add(str(r))
    with pytest.raises(Exception): owner.assert_admitted()
    with pytest.raises(Exception): owner.close()


@pytest.mark.parametrize('mutation',['missing','replaced','registry_replaced','different','unknown','hardlink','truncated','reordered','duplicate','noncanonical','bool','float','oversized','too_many','total_bytes','same_count'])
def test_complete_membership_and_closed_registry_parser_reject_corruption(setup, mutation):
    m,r,j,clock,identity,admit=setup
    with admit() as owner: name=owner.snapshot()['binding']['journal']
    path=r/m.REGISTRY_NAME; data=path.read_bytes(); journal=r/name
    if mutation=='missing': journal.rename(r/'renamed.jsonl')
    elif mutation=='replaced':
        journal.rename(r/'old'); journal.write_bytes((r/'old').read_bytes()); (r/'old').unlink()
    elif mutation=='registry_replaced':
        path.rename(j/'old-registry'); path.write_bytes(data)
    elif mutation=='different': journal.write_bytes(b'{}\n')
    elif mutation=='unknown': (r/'unknown').write_bytes(b'x')
    elif mutation=='hardlink':
        os.link(journal,j.with_name('alias'))
    elif mutation=='truncated': path.write_bytes(data[:-1])
    elif mutation=='reordered': path.write_bytes(b''.join(reversed(data.splitlines(keepends=True))))
    elif mutation=='duplicate': path.write_bytes(data.replace(b'"version":1',b'"version":1,"version":1',1))
    elif mutation=='noncanonical': path.write_bytes(b' '+data)
    elif mutation in ('bool','float'):
        lines=records(r,m); lines[0]['record']['version']=True if mutation=='bool' else 1.0
        lines[0]['digest']=budget._hash(lines[0]['record'])
        path.write_bytes(b''.join(budget._canonical(x)+b'\n' for x in lines))
    elif mutation=='oversized': path.write_bytes(b'x'*4097+b'\n')
    elif mutation=='total_bytes': path.write_bytes(b'x'*(1024*1024)+b'\n')
    elif mutation=='same_count': journal.rename(r/('f'*64+'.jsonl'))
    else: path.write_bytes(b'{}\n'*257)
    damaged={p.name:p.read_bytes() for p in r.iterdir()}
    with pytest.raises(Exception): admit(identity=replace(identity,input_digest='f'*64))
    assert {p.name:p.read_bytes() for p in r.iterdir()}==damaged


@pytest.mark.parametrize('boundary',['admitting-write','admitting-fsync','admitting-dir','create','reserve','admitted-write','admitted-fsync','admitted-dir','stop','closed-write','closed-fsync','closed-dir'])
def test_boundary_failures_never_return_owner_or_readmit(setup,monkeypatch,boundary):
    m,r,j,clock,identity,admit=setup
    original_append=budget._FileJournal.append
    original_create=PortableNamespace.create_budget
    original_reserve=budget.PreparationBudget.reserve
    original_stop=budget.PreparationBudget.stop_unmeasured
    original_sync=PortableNamespace.directory_sync
    phase={'event':None}
    def append(store,line):
        event=json.loads(line)['record']['event']
        if event in ('admitting','admitted','closed'):
            phase['event']=event
            if boundary==event+'-write':
                os.lseek(store.fd,0,os.SEEK_END); os.write(store.fd,line[:17])
                raise OSError('injected partial registry write')
            if boundary==event+'-fsync':
                os.lseek(store.fd,0,os.SEEK_END); os.write(store.fd,line)
                raise OSError('injected complete write, uncertain file fsync')
        return original_append(store,line)
    def sync(self):
        if boundary==phase['event']+'-dir': raise OSError('injected directory fsync')
        return original_sync(self)
    def create(self,value):
        if boundary=='create': raise OSError('injected create')
        return original_create(self,value)
    def reserve(self,*args):
        if boundary=='reserve': raise OSError('injected reserve')
        return original_reserve(self,*args)
    def stop(self):
        if boundary=='stop': raise OSError('injected stop')
        return original_stop(self)
    with monkeypatch.context() as patch:
        patch.setattr(budget._FileJournal,'append',append)
        patch.setattr(PortableNamespace,'directory_sync',sync)
        patch.setattr(PortableNamespace,'create_budget',create)
        patch.setattr(budget.PreparationBudget,'reserve',reserve)
        patch.setattr(budget.PreparationBudget,'stop_unmeasured',stop)
        if boundary.startswith('closed') or boundary=='stop':
            owner=admit()
            with pytest.raises(Exception): owner.close()
            with pytest.raises(Exception): owner.assert_admitted()
        else:
            with pytest.raises(Exception): admit()
    damaged={p.name:p.read_bytes() for p in r.iterdir()}
    assert damaged
    if boundary.endswith('-write'):
        raw=damaged[m.REGISTRY_NAME]
        assert not raw.endswith(b'\n') and len(raw.splitlines()[-1])==17
    with pytest.raises(Exception): admit(identity=replace(identity,input_digest='f'*64))
    assert {p.name:p.read_bytes() for p in r.iterdir()}==damaged


def test_lock_contention_fails_before_competing_write(setup):
    m,r,j,clock,identity,admit=setup
    with admit():
        before={p.name:p.read_bytes() for p in r.iterdir()}
        with pytest.raises(Exception): admit(identity=replace(identity,input_digest='f'*64))
        assert {p.name:p.read_bytes() for p in r.iterdir()}==before


@pytest.mark.parametrize('field,value', [('purpose','other'),('profile_kind','other'),
    ('plan_digest','A'*64),('plan_digest',True),('retained_history_digest',None),
    ('identity',{}),('plan_digest','1'*65)])
def test_invalid_public_arguments_never_create_registry(setup,field,value):
    m,r,j,clock,identity,admit=setup
    with pytest.raises(Exception): admit(**{field:value})
    assert list(r.iterdir())==[]


def test_missing_registry_in_nonempty_directory_is_not_recreated(setup):
    m,r,j,clock,identity,admit=setup
    (r/'retained.jsonl').write_bytes(b'old')
    with pytest.raises(Exception): admit()
    assert {p.name:p.read_bytes() for p in r.iterdir()}=={'retained.jsonl':b'old'}


@pytest.mark.parametrize('field,value',[('sequence',True),('pid',True),('start_ticks',1.0),
    ('journal_inode',False),('ticket_cpu',True),('deadline_boot_ns',True),('identity',None),
    ('extra',True),('job_path','relative-job')])
def test_registry_nested_scalar_and_schema_corruption_is_explicitly_rejected(setup,field,value):
    m,r,j,clock,identity,admit=setup
    admit().close()
    envelopes=records(r,m)
    if field=='sequence': envelopes[0]['record']['sequence']=value
    elif field in ('pid','start_ticks'): envelopes[0]['record']['body']['process'][field]=value
    elif field=='identity': envelopes[0]['record']['body']['identity']=value
    elif field=='job_path': envelopes[0]['record']['body']['job']['path']=value
    elif field=='ticket_cpu': envelopes[1]['record']['body']['ticket']['cpu_ns']=value
    elif field=='extra': envelopes[1]['record']['body']['native_success']=value
    else: envelopes[1]['record']['body'][field]=value
    previous='0'*64
    for envelope in envelopes:
        envelope['record']['previous']=previous
        envelope['digest']=budget._hash(envelope['record'])
        previous=envelope['digest']
    path=r/m.REGISTRY_NAME
    changed=b''.join(budget._canonical(e)+b'\n' for e in envelopes)
    path.write_bytes(changed)
    with pytest.raises(Exception): admit(identity=replace(identity,input_digest='f'*64))
    assert path.read_bytes()==changed


def test_admission_startup_cannot_restart_original_parent_deadline(setup,monkeypatch):
    m,r,j,clock,identity,admit=setup
    clock['now']=3610*NS
    with pytest.raises(m.AdmissionError,match='deadline'): admit()
    assert list(r.iterdir())==[]
    clock['now']=100*NS
    original=PortableNamespace.directory_sync
    def delayed(self):
        original(self)
        if records(r,m)[-1]['record']['event']=='admitted': clock['now']=3610*NS
    with monkeypatch.context() as patch:
        patch.setattr(PortableNamespace,'directory_sync',delayed)
        with pytest.raises(m.AdmissionError,match='deadline'): admit()
    binding=records(r,m)[-1]['record']['body']
    state=budget._replay((r/binding['journal']).read_bytes(),identity).snapshot()
    assert state.charged_cpu_ns==300*NS and state.settled_cpu_ns==0
    assert binding['deadline_boot_ns']==3610*NS
    with pytest.raises(Exception): admit()


@pytest.mark.parametrize('event',['init','reserve','stop'])
@pytest.mark.parametrize('failure',['partial','fsync'])
def test_real_budget_io_failure_cannot_escape_admission(setup,monkeypatch,event,failure):
    m,r,j,clock,identity,admit=setup
    owner=admit() if event=='stop' else None
    original=budget._FileJournal.append
    def failing(store,line):
        if json.loads(line)['record']['event']==event:
            os.lseek(store.fd,0,os.SEEK_END)
            os.write(store.fd,line[:17] if failure=='partial' else line)
            raise OSError('injected real budget boundary')
        return original(store,line)
    with monkeypatch.context() as patch:
        patch.setattr(budget._FileJournal,'append',failing)
        with pytest.raises(Exception): owner.close() if owner else admit()
    name=budget._hash(budget._identity(identity))+'.jsonl'
    raw=(r/name).read_bytes()
    if failure=='partial': assert not raw.endswith(b'\n') and len(raw.splitlines()[-1])==17
    else: assert json.loads(raw.splitlines()[-1])['record']['event']==event
    before={p.name:p.read_bytes() for p in r.iterdir()}
    result=_fresh_process(r,j,'fbcde')
    assert result.returncode==7 and 'nonterminal' in result.stdout, result.stdout+result.stderr
    assert {p.name:p.read_bytes() for p in r.iterdir()}==before


@pytest.mark.parametrize('target',['registry','journal'])
def test_live_replacement_or_foreign_bytes_poison_owner(setup,target):
    m,r,j,clock,identity,admit=setup
    owner=admit()
    name=m.REGISTRY_NAME if target=='registry' else owner.snapshot()['binding']['journal']
    with (r/name).open('ab') as stream: stream.write(b'\n')
    with pytest.raises(Exception): owner.assert_admitted()
    with pytest.raises(Exception): owner.close()
    with pytest.raises(Exception): admit(identity=replace(identity,input_digest='f'*64))


@pytest.mark.parametrize('event',['admitting','admitted','closed'])
def test_actual_fsync_failure_preserves_complete_bytes_without_success(setup,monkeypatch,event):
    m,r,j,clock,identity,admit=setup
    original=os.fsync
    owner=admit() if event=='closed' else None
    def failure(fd):
        path=r/m.REGISTRY_NAME
        if path.exists():
            raw=path.read_bytes()
            if raw and json.loads(raw.splitlines()[-1])['record']['event']==event:
                raise OSError('actual os.fsync injection')
        return original(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os,'fsync',failure)
        with pytest.raises(Exception): owner.close() if owner else admit()
    raw=(r/m.REGISTRY_NAME).read_bytes()
    assert json.loads(raw.splitlines()[-1])['record']['event']==event
    with pytest.raises(Exception): admit(identity=replace(identity,input_digest='f'*64))
    assert (r/m.REGISTRY_NAME).read_bytes()==raw


def _fresh_process(registry,job,identity,fail_sync=False):
    """Fresh portable protocol process, not a native root/DAC bypass."""
    code = '''import importlib.util,sys,os
from pathlib import Path
import context_preparation_budget as b
spec=importlib.util.spec_from_file_location('portable_fixture',sys.argv[1]); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
namespace={'__name__':'fresh_held'}; exec(compile(t.SOURCE.read_bytes(),'<held>','exec'),namespace)
class Module: pass
m=Module(); m.REGISTRY_NAME=namespace['REGISTRY_NAME']
clock={'now':100*10**9,'boot':t.BOOT,'offset':1700000000*10**9}
b._system_clock=lambda:b.ClockSample(t.BOOT,clock['now'],clock['now']+clock['offset'],clock['now'])
ns=t.PortableNamespace(m,Path(sys.argv[2]),Path(sys.argv[3]),clock)
if sys.argv[5]=='fail':
 def failed(*args): raise OSError('fresh-history-sync-failed')
 ns.sync_journal=failed
identity=b.BudgetIdentity(*[c*64 for c in sys.argv[4]])
try:
 with namespace['_admit_protocol'](ns,identity=identity,purpose='context-receipt-corpus-diagnostic-v1',profile_kind='atp-heavy',plan_digest='1'*64,retained_history_digest='2'*64) as owner:
  print('CHARGE',owner.snapshot()['binding']['ticket']['cpu_ns'])
except Exception as exc:
 print(type(exc).__name__,str(exc)); sys.exit(7)
'''
    env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'
    return subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__).resolve()),str(registry),str(job),identity,
                           'fail' if fail_sync else 'sync'],capture_output=True,text=True,timeout=15,env=env)


@pytest.mark.parametrize('event',['admitting','admitted','closed'])
def test_fresh_process_only_accepts_fully_cross_bound_stopped_history(setup,monkeypatch,event):
    m,r,j,clock,identity,admit=setup
    owner=admit() if event=='closed' else None
    original=os.fsync
    def failure(fd):
        path=r/m.REGISTRY_NAME
        if path.exists() and path.read_bytes():
            if records(r,m)[-1]['record']['event']==event: raise OSError('uncertain sync')
        return original(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os,'fsync',failure)
        with pytest.raises(Exception): owner.close() if owner else admit()
    before={p.name:p.read_bytes() for p in r.iterdir()}
    same=_fresh_process(r,j,'abcde')
    assert same.returncode==7 and 'permanently consumed' in same.stdout, same.stderr
    if event=='closed':
        failed=_fresh_process(r,j,'fbcde',True)
        assert failed.returncode==7 and 'fresh-history-sync-failed' in failed.stdout, failed.stderr
        assert {p.name:p.read_bytes() for p in r.iterdir()}==before
        result=_fresh_process(r,j,'fbcde')
        assert result.returncode==0 and 'CHARGE 300000000000' in result.stdout, result.stderr+result.stdout
        for name,raw in before.items():
            if name!=m.REGISTRY_NAME: assert (r/name).read_bytes()==raw
    else:
        result=_fresh_process(r,j,'fbcde')
        assert result.returncode==7 and 'nonterminal' in result.stdout, result.stderr+result.stdout
        assert {p.name:p.read_bytes() for p in r.iterdir()}==before


def test_public_entry_has_no_bypass_and_rejects_unsupported_host(module,tmp_path):
    signature=inspect.signature(module.admit_diagnostic)
    assert all(p.default is inspect.Parameter.empty for p in signature.parameters.values())
    assert set(signature.parameters)=={'registry_directory','identity','purpose','profile_kind','plan_digest','job_directory','retained_history_digest'}
    if sys.platform!='linux' or os.geteuid()!=0:
        with pytest.raises(module.NativeAdmissionUnavailable):
            module.admit_diagnostic(tmp_path,identity=budget.BudgetIdentity(*('a'*64,)*5),
                purpose='context-receipt-corpus-diagnostic-v1',profile_kind='atp-heavy',
                plan_digest='1'*64,job_directory=tmp_path,retained_history_digest='2'*64)


def test_held_compiled_namespace_needs_no_new_registered_helper(setup):
    m,r,j,clock,identity,admit=setup
    namespace={'__name__':'held_diagnostic_not_registered'}
    exec(compile(SOURCE.read_bytes(),'<held-diagnostic>','exec'),namespace)
    assert 'held_diagnostic_not_registered' not in sys.modules
    adapter=PortableNamespace(m,r,j,clock)
    with namespace['_admit_protocol'](adapter,identity=identity,purpose='context-receipt-corpus-diagnostic-v1',
            profile_kind='atp-heavy',plan_digest='1'*64,retained_history_digest='2'*64) as owner:
        owner.assert_admitted()


def test_snapshot_keeps_operation_custody_through_returned_data_construction(setup,monkeypatch):
    m,r,j,clock,identity,admit=setup
    owner=admit()
    entered,release=threading.Event(),threading.Event()
    original=m._readonly
    results=[]
    def delayed(value):
        entered.set()
        assert release.wait(5)
        return original(value)
    monkeypatch.setattr(m,'_readonly',delayed)
    worker=threading.Thread(target=lambda:results.append(owner.snapshot()))
    worker.start()
    try:
        assert entered.wait(5)
        before=(r/m.REGISTRY_NAME).read_bytes()
        with pytest.raises(m.AdmissionError,match='concurrent'): owner.close()
        assert (r/m.REGISTRY_NAME).read_bytes()==before
    finally:
        release.set(); worker.join(5)
    assert not worker.is_alive() and results[0]['binding']['ticket']['cpu_ns']==300*NS
    owner.close()


@pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:-1)()!=0,
                    reason='requires real Linux root/DAC/flock; portable tests are not native proof')
def test_native_root_branch_requires_prepared_protected_namespace(module):
    root=os.environ.get('BETBOY_ADMISSION_NATIVE_TEST_ROOT')
    if not root:
        pytest.skip('operator must supply existing protected empty registry and job under non-writable ancestors')
    base=Path(root)
    with module.admit_diagnostic(base/'registry',identity=budget.BudgetIdentity(*(c*64 for c in 'abcde')),
            purpose='context-receipt-corpus-diagnostic-v1',profile_kind='atp-heavy',plan_digest='1'*64,
            job_directory=base/'job',retained_history_digest='2'*64) as owner:
        owner.assert_admitted()
        before=(base/'registry'/module.REGISTRY_NAME).read_bytes()
        with pytest.raises(module.AdmissionError,match='lock contention'):
            module.admit_diagnostic(base/'registry',identity=budget.BudgetIdentity(*(c*64 for c in 'fbcde')),
                purpose='context-receipt-corpus-diagnostic-v1',profile_kind='atp-heavy',plan_digest='1'*64,
                job_directory=base/'job',retained_history_digest='2'*64)
        assert (base/'registry'/module.REGISTRY_NAME).read_bytes()==before


@pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:-1)()!=0,
                    reason='requires real Linux root and explicit disposable protected test root')
def test_native_dac_nofollow_and_lost_flock_are_fail_closed(module,tmp_path):
    root=os.environ.get('BETBOY_ADMISSION_NATIVE_TEST_ROOT')
    if not root: pytest.skip('operator-prepared protected root required')
    base=Path(root)
    registry,job=base/'loss-registry',base/'loss-job'
    registry.mkdir(mode=0o700); job.mkdir(mode=0o700)
    arguments=dict(identity=budget.BudgetIdentity(*(c*64 for c in 'abcde')),
        purpose='context-receipt-corpus-diagnostic-v1',profile_kind='atp-heavy',plan_digest='1'*64,
        job_directory=job,retained_history_digest='2'*64)
    alias=base/'linked-registry'; alias.symlink_to(registry,target_is_directory=True)
    with pytest.raises(module.AdmissionError): module.admit_diagnostic(alias,**arguments)
    writable=base/'writable-parent'; writable.mkdir(mode=0o777); writable.chmod(0o777)
    child=writable/'registry'; child.mkdir(mode=0o700)
    with pytest.raises(module.AdmissionError): module.admit_diagnostic(child,**arguments)
    assert list(registry.iterdir())==[] and list(child.iterdir())==[]
    owner=module.admit_diagnostic(registry,**arguments)
    import fcntl
    fcntl.flock(owner._namespace._registry_fd,fcntl.LOCK_UN)
    with pytest.raises(module.AdmissionError,match='custody lost'): owner.assert_admitted()
    with pytest.raises(module.AdmissionError): owner.close()
