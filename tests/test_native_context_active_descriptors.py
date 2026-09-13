"""Task63 focused FD contract; native cases are explicit on non-Linux hosts."""
from contextlib import ExitStack
import importlib.util
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).absolute().parents[1]


def catalogue():
    spec=importlib.util.spec_from_file_location('task63_catalogue',ROOT/'tests/native_context_receipt_diagnostic_catalogue.py')
    c=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    c.old()
    return c


def plan(root):
    path=root/'input'
    path.write_bytes(b'actual held input')
    return dict(inputs=[dict(path=str(path),cap=4096)],input_metadata_cap=128*1024**2,
                active_input_cap=4*1024**3,total=1024**3)


def test_descriptor_contract_exact_arithmetic_and_rejection():
    c=catalogue()
    value=c._active_descriptor_reservation((1024,1048576),[0,1,2,3],4546,468)
    assert value==dict(original_soft=1024,desired_soft=5146,hard=1048576,baseline=4,
                      files=4546,directories=468,required=5146,ceiling=32768,reserve=128)
    assert c._active_descriptor_reservation((8192,1048576),[0,7],4546,468)['desired_soft']==8192
    for limits,fds,files,dirs in [((1024,1024),[0,1,2,3],4546,468),
        ((32769,1048576),[0],1,1),((1024,1048576),[128],1,1),
        ((1024,1048576),[0,0],1,1),((1024,1048576),[False],1,1),
        ((1024,1048576),[],1,1),((1024,1048576),[0],30000,1)]:
        with pytest.raises(c.DiagnosticError):
            c._active_descriptor_reservation(limits,fds,files,dirs)


def test_portable_sample_marks_native_descriptor_validation_absent(tmp_path):
    if sys.platform=='linux': pytest.skip('portable route only')
    c=catalogue()
    p=plan(tmp_path)
    with ExitStack() as held:
        binding=c.hold_active_inputs(held,p)
        first=c.sample_active_inputs(binding,p)
        second=c.sample_active_inputs(binding,p,previous=first)
    assert first==second and first['descriptors'] is None
    assert first['files'][0]['sha256']==hashlib.sha256(b'actual held input').hexdigest()


class ResourceModel:
    RLIMIT_NOFILE=7
    def __init__(self,adapter):
        self.limits=(32,1048576)
        self.calls=[]
        self.adapter=adapter
    def getrlimit(self,key):
        assert key==self.RLIMIT_NOFILE
        return self.limits
    def setrlimit(self,key,value):
        assert key==self.RLIMIT_NOFILE and value[1]==1048576
        if self.calls and value[0]==32:
            assert not self.adapter.nodes, 'restoration occurred before complete FD unwind'
        self.calls.append(value)
        self.limits=value


class DescriptorModel:
    """Windows directory-FD model, with actual held file bytes; not native QA."""
    O_RDONLY=os.O_RDONLY
    O_DIRECTORY=0x10000000
    O_NOFOLLOW=0x20000000
    O_CLOEXEC=0x40000000
    O_NONBLOCK=0x08000000
    SEEK_SET=os.SEEK_SET
    getpid=staticmethod(os.getpid)
    lseek=staticmethod(os.lseek)
    read=staticmethod(os.read)
    def __init__(self):
        self.nodes={}
        self.next=-100
        self.opens=[]
    def path(self,name,dir_fd=None):
        return Path(name) if dir_fd is None else self.nodes[dir_fd]/name
    def stat(self,name,*,dir_fd=None,follow_symlinks=False):
        assert not follow_symlinks
        return self.path(name,dir_fd).lstat()
    def open(self,name,flags,*,dir_fd=None):
        path=self.path(name,dir_fd)
        assert flags & self.O_NOFOLLOW and flags & self.O_CLOEXEC
        assert not path.is_symlink()
        self.opens.append((str(name),dir_fd))
        if flags & self.O_DIRECTORY:
            assert path.is_dir()
            self.next-=1
            fd=self.next
        else:
            fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0))
        self.nodes[fd]=path
        return fd
    def fstat(self,fd):
        if fd<0:
            return self.nodes[fd].stat()
        return os.fstat(fd)
    def close(self,fd):
        if fd>=0: os.close(fd)
        del self.nodes[fd]
    def scandir(self,path):
        from contextlib import contextmanager
        assert path=='/proc/self/fd'
        @contextmanager
        def entries(): yield iter(SimpleNamespace(name=str(i)) for i in range(4))
        return entries()


def modeled(c,monkeypatch):
    adapter=DescriptorModel()
    resource=ResourceModel(adapter)
    old=dict(c.old())
    # Explicit model limitation: Windows fstat ctime is not Linux ctime.
    old['identity']=lambda i:(i.st_dev,i.st_ino,i.st_mode,i.st_nlink,i.st_size,i.st_mtime_ns,i.st_mtime_ns)
    monkeypatch.setattr(c,'_OLD_CATALOGUE',old)
    monkeypatch.setattr(c,'os',adapter)
    monkeypatch.setattr(c,'_active_resource',lambda:resource)
    return adapter,resource


def native_paths(p):
    paths=[Path(item['path']) for item in p['inputs']]
    return paths,sorted({q for path in paths for q in path.parents},key=str)


def test_modeled_shared_lifetime_full_hashes_and_restoration_order(tmp_path,monkeypatch):
    c=catalogue()
    p=plan(tmp_path)
    adapter,resource=modeled(c,monkeypatch)
    paths,ancestors=native_paths(p)
    with c._held_active_linux(paths,ancestors) as binding:
        assert len(adapter.nodes)==len(paths)+len(ancestors)
        first=c.sample_active_inputs(binding,p)
        second=c.sample_active_inputs(binding,p,previous=first)
        assert second==first and first['descriptors']['required']==4+len(paths)+len(ancestors)+128
        assert len(adapter.opens)==len(paths)+len(ancestors)
        assert first['files'][0]['sha256']==hashlib.sha256(b'actual held input').hexdigest()
        assert resource.limits[0]==first['descriptors']['desired_soft']
    assert resource.limits==(32,1048576) and not adapter.nodes
    assert len(resource.calls)==2


@pytest.mark.parametrize('fault',['hard','high_baseline','invalid_fd','deny','readback'])
def test_modeled_preflight_refuses_before_bulk_open(tmp_path,monkeypatch,fault):
    from contextlib import contextmanager
    c=catalogue()
    p=plan(tmp_path)
    adapter,resource=modeled(c,monkeypatch)
    if fault=='hard': resource.limits=(32,40)
    elif fault in ('high_baseline','invalid_fd'):
        @contextmanager
        def scan(path): yield iter([SimpleNamespace(name='128' if fault=='high_baseline' else 'bad')])
        monkeypatch.setattr(adapter,'scandir',scan)
    else:
        actual=resource.setrlimit
        def setlimit(key,value):
            if value[0]!=32:
                if fault=='deny': raise PermissionError('denied soft reservation')
                actual(key,(value[0]+1,value[1]))
            else: actual(key,value)
        monkeypatch.setattr(resource,'setrlimit',setlimit)
    with pytest.raises(Exception):
        with c._held_active_linux(*native_paths(p)): pytest.fail('returned a rejected binding')
    assert not adapter.opens and not adapter.nodes


@pytest.mark.parametrize('fault',['open','stat','read','close','preclose','restore','drift','edit','directory','allocation','caller'])
def test_modeled_binding_failures_cleanup_and_never_hide_fault(tmp_path,monkeypatch,fault):
    c=catalogue()
    p=plan(tmp_path)
    adapter,resource=modeled(c,monkeypatch)
    fired=[]
    if fault in ('open','stat'):
        actual=getattr(adapter,fault)
        def fail(*args,**kwargs):
            if args[0]=='input':
                fired.append(fault)
                raise OSError('injected '+fault)
            return actual(*args,**kwargs)
        monkeypatch.setattr(adapter,fault,fail)
    with pytest.raises(Exception):
        with c._held_active_linux(*native_paths(p)) as binding:
            first=c.sample_active_inputs(binding,p)
            if fault in ('open','stat'): pytest.fail('missed injected failure')
            if fault=='caller': raise RuntimeError('caller failed')
            if fault in ('close','preclose'):
                actual=adapter.close
                def close(fd):
                    if fault=='preclose' and not fired:
                        fired.append(fault)
                        raise OSError('one-shot pre-release close fault')
                    actual(fd)
                    if not fired:
                        fired.append(fault)
                        raise OSError('post-release close fault')
                monkeypatch.setattr(adapter,'close',close)
            elif fault=='restore':
                actual=resource.setrlimit
                def setlimit(key,value):
                    if value[0]==32: raise PermissionError('restore denied')
                    actual(key,value)
                monkeypatch.setattr(resource,'setrlimit',setlimit)
            elif fault=='drift': resource.limits=(resource.limits[0]+1,resource.limits[1])
            elif fault=='read': monkeypatch.setattr(adapter,'read',lambda *a:(_ for _ in ()).throw(OSError('read failed')))
            elif fault=='edit': (tmp_path/'input').write_bytes(b'changed held data')
            elif fault=='directory':
                before=tmp_path.stat()
                os.utime(tmp_path,ns=(before.st_atime_ns,before.st_mtime_ns+1000000000))
            elif fault=='allocation': monkeypatch.setattr(c,'_allocation',lambda info:129*1024**2)
            if fault not in ('close','preclose','restore'):
                c.sample_active_inputs(binding,p,previous=first)
    assert not adapter.nodes
    assert resource.limits==(32,1048576) or fault=='restore'


def test_public_path_bounds_fail_before_any_descriptor_reservation(tmp_path,monkeypatch):
    c=catalogue()
    def forbidden(): raise AssertionError('path refusal reached native resource acquisition')
    monkeypatch.setattr(c,'_active_resource',forbidden)
    for entries in ([dict(path=str(tmp_path/'x'),cap=1)]*30001,
                    [dict(path=str(tmp_path.joinpath(*(['x']*33))),cap=1)]):
        with ExitStack() as held, pytest.raises(c.DiagnosticError):
            c.hold_active_inputs(held,dict(inputs=entries))


@pytest.mark.skipif(sys.platform!='linux',reason='actual Linux shared ownership and NOFILE proof required')
def test_native_shared_input_descriptors_and_complete_sampling(tmp_path,monkeypatch):
    import resource
    c=catalogue()
    p=plan(tmp_path)
    (tmp_path/'other').write_bytes(b'other')
    p['inputs'].append(dict(path=str(tmp_path/'other'),cap=4096))
    original_limits=resource.getrlimit(resource.RLIMIT_NOFILE)
    if original_limits[0]>32768:
        pytest.skip('in-process parent has an intentionally rejected soft limit; fresh subprocess below covers native success')
    before=set(os.listdir('/proc/self/fd'))
    opened=[]
    real_open=os.open
    def observed(name,flags,*args,**kwargs):
        opened.append((str(name),kwargs.get('dir_fd')))
        return real_open(name,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',observed)
    with ExitStack() as held:
        binding=c.hold_active_inputs(held,p)
        sample=c.sample_active_inputs(binding,p)
        assert len(opened)==2+len({parent for item in p['inputs'] for parent in Path(item['path']).parents})
        assert sum(name=='/' for name,_ in opened)==1
        assert c.sample_active_inputs(binding,p,previous=sample)==sample
        assert len(opened)==sample['descriptors']['files']+sample['descriptors']['directories']
        assert resource.getrlimit(resource.RLIMIT_NOFILE)==(sample['descriptors']['desired_soft'],original_limits[1])
    assert resource.getrlimit(resource.RLIMIT_NOFILE)==original_limits
    assert set(os.listdir('/proc/self/fd'))==before


NATIVE_SCRIPT=r'''
import errno,hashlib,json,os,resource,runpy,sys
from pathlib import Path
from contextlib import ExitStack
c=runpy.run_path(sys.argv[1])
root=Path(sys.argv[2])
mode=sys.argv[3]
original=resource.getrlimit(resource.RLIMIT_NOFILE)
assert original[1]>=2048
resource.setrlimit(resource.RLIMIT_NOFILE,(1024,original[1]))
p=dict(inputs=[dict(path=str(root/str(n)),cap=4096) for n in range(1100)],
       input_metadata_cap=128*1024**2,active_input_cap=4*1024**3,total=1024**3)
paths=[Path(item['path']) for item in p['inputs']]
ancestors=sorted({q for path in paths for q in path.parents},key=str)
before=set(os.listdir('/proc/self/fd'))
if mode=='prior':
    # Exact prior ownership algorithm, using the actual unchanged pinned
    # opened() contexts, not a mocked FD count or time threshold.
    try:
        with ExitStack() as held:
            for kind,names in (('directories',ancestors),('files',paths)):
                for path in names:
                    held.enter_context(c['old']()['opened'](path,directory=kind=='directories'))
    except OSError as exc:
        assert exc.errno==errno.EMFILE
    else:
        raise AssertionError('prior complete-chain ownership did not exhaust soft1024')
    assert set(os.listdir('/proc/self/fd'))==before
    print('prior_actual_EMFILE_no_leak')
else:
    with ExitStack() as held:
        binding=c['hold_active_inputs'](held,p)
        first=c['sample_active_inputs'](binding,p)
        assert len(binding['files'])==1100
        assert len(binding['directories'])==len(ancestors)
        assert len(set(os.listdir('/proc/self/fd'))-before)==1100+len(ancestors)
        assert first['descriptors']['required']==first['descriptors']['baseline']+1100+len(ancestors)+128
        assert 1024<first['descriptors']['desired_soft']<=32768
        assert resource.getrlimit(resource.RLIMIT_NOFILE)==(first['descriptors']['desired_soft'],original[1])
        # Fresh full hash reads must not reopen any pathname/ancestor chain.
        actual_open=os.open
        os.open=lambda *a,**k:(_ for _ in ()).throw(AssertionError('sample reopened a pathname'))
        try: second=c['sample_active_inputs'](binding,p,previous=first)
        finally: os.open=actual_open
        assert second==first
        assert all(x['sha256']==hashlib.sha256(b'held').hexdigest() for x in second['files'])
        if mode=='closure':
            # Actual unchanged supervisor child closure up to its first chdir.
            # Stop at that explicit boundary: no root UID-drop/guard claim.
            import importlib.util,types
            helper=Path(sys.argv[1]).parents[1]/'context_preparation_supervisor.py'
            raw=helper.read_bytes()
            assert hashlib.sha256(raw).hexdigest()==c['HELPERS']['context_preparation_supervisor.py']
            mod=types.ModuleType('context_preparation_supervisor')
            mod.__file__=str(helper)
            sys.modules[mod.__name__]=mod
            exec(compile(raw,str(helper),'exec'),mod.__dict__)
            out_read,out_write=os.pipe()
            err_read,err_write=os.pipe()
            null=os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC)
            pid=os.fork()
            if pid==0:
                def at_chdir(path):
                    fds=sorted(int(x) for x in os.listdir('/proc/self/fd'))
                    assert fds==[0,1,2,3],fds
                    assert resource.getrlimit(resource.RLIMIT_NOFILE)==(first['descriptors']['desired_soft'],original[1])
                    os.write(1,b'actual_child_closure_inherited_nofile\n')
                    os._exit(0)
                os.chdir=at_chdir
                mod._child_run_python(('unused','receipt-v1'),65534,65534,str(root),out_write,err_write,null,536870912,240,None)
                os._exit(125)
            for fd in (out_write,err_write,null):os.close(fd)
            output=os.read(out_read,4096)
            error=os.read(err_read,4096)
            found,status=os.waitpid(pid,0)
            os.close(out_read);os.close(err_read)
            assert found==pid and os.waitstatus_to_exitcode(status)==0 and error==b''
            assert output==b'actual_child_closure_inherited_nofile\n'
            assert len(binding['files'])==1100 and c['sample_active_inputs'](binding,p,previous=first)==first
    assert set(os.listdir('/proc/self/fd'))==before
    assert resource.getrlimit(resource.RLIMIT_NOFILE)==(1024,original[1])
    print('shared_actual_1100_held_restored_no_leak '+mode)
resource.setrlimit(resource.RLIMIT_NOFILE,original)
'''


@pytest.mark.skipif(sys.platform!='linux',reason='Root runs isolated ordinary-UID native subprocesses separately')
@pytest.mark.parametrize('mode',['prior','shared','closure'])
def test_native_fresh_soft1024_more_than1024_files_and_actual_child_closure(tmp_path,mode):
    for n in range(1100): (tmp_path/str(n)).write_bytes(b'held')
    result=subprocess.run([sys.executable,'-I','-S','-B','-c',NATIVE_SCRIPT,
        str(ROOT/'tests/native_context_receipt_diagnostic_catalogue.py'),str(tmp_path),mode],
        capture_output=True,timeout=30)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert result.stderr==b''
    assert (b'prior_actual_EMFILE_no_leak' if mode=='prior' else b'shared_actual_1100_held_restored_no_leak') in result.stdout


@pytest.mark.skipif(sys.platform!='linux',reason='actual Linux file/ancestor binding and full metadata comparison required')
@pytest.mark.parametrize('fault',['none','alias','symlink','same_size','file_rename','directory_rename','read','stat','open','close','soft_drift','restore'])
def test_native_bindings_and_error_unwind_with_modeled_limit_provider(tmp_path,monkeypatch,fault):
    """Real Linux descriptors/epochs; the limit provider here is explicitly modeled."""
    c=catalogue()
    directory=tmp_path/'inputs'
    directory.mkdir()
    p=plan(directory)
    paths,ancestors=native_paths(p)
    class NativeDescriptors(DescriptorModel):
        O_RDONLY=os.O_RDONLY
        O_DIRECTORY=os.O_DIRECTORY
        O_NOFOLLOW=os.O_NOFOLLOW
        O_CLOEXEC=os.O_CLOEXEC
        O_NONBLOCK=os.O_NONBLOCK
        stat=staticmethod(os.stat)
        fstat=staticmethod(os.fstat)
        scandir=staticmethod(os.scandir)
        def open(self,name,flags,*,dir_fd=None):
            args={} if dir_fd is None else dict(dir_fd=dir_fd)
            fd=os.open(name,flags,**args)
            self.nodes[fd]=self.path(name,dir_fd)
            return fd
        def close(self,fd):
            os.close(fd)
            del self.nodes[fd]
    adapter=NativeDescriptors()
    provider=ResourceModel(adapter)
    monkeypatch.setattr(c,'os',adapter)
    monkeypatch.setattr(c,'_active_resource',lambda:provider)
    before=set(os.listdir('/proc/self/fd'))
    if fault=='alias': os.link(paths[0],directory/'other-alias')
    if fault=='symlink':
        paths[0].rename(directory/'preserved')
        os.symlink('preserved',paths[0])
    if fault=='open':
        actual=adapter.open
        def opened(name,*args,**kwargs):
            if name=='input': raise OSError('injected open error')
            return actual(name,*args,**kwargs)
        monkeypatch.setattr(adapter,'open',opened)
    def run():
        # Previous sampler with actual old held contexts, on the same small
        # unchanged fixture, before exercising the shared ownership route.
        expected=None
        if fault=='none':
            with ExitStack() as stack:
                previous={'files':[],'directories':[]}
                for kind,names in (('directories',ancestors),('files',paths)):
                    for path in names:
                        fd,info=stack.enter_context(c.old()['opened'](path,directory=kind=='directories'))
                        previous[kind].append((path,fd,info))
                expected=c.sample_active_inputs(previous,p)
        with c._held_active_linux(paths,ancestors) as binding:
            first=c.sample_active_inputs(binding,p)
            if expected is not None:
                actual=dict(first,descriptors=None)
                assert c.canonical(actual)==c.canonical(expected)
            if fault=='same_size': paths[0].write_bytes(b'changed held data')
            elif fault=='file_rename':
                paths[0].rename(directory/'preserved')
                paths[0].write_bytes(b'actual held input')
            elif fault=='directory_rename':
                directory.rename(tmp_path/'preserved-inputs')
                directory.mkdir()
            elif fault=='read': monkeypatch.setattr(adapter,'read',lambda *a:(_ for _ in ()).throw(OSError('read failed')))
            elif fault=='stat': monkeypatch.setattr(adapter,'stat',lambda *a,**k:(_ for _ in ()).throw(OSError('stat failed')))
            elif fault=='close':
                actual=adapter.close
                fired=[]
                def closed(fd):
                    actual(fd)
                    if not fired:
                        fired.append(True)
                        raise OSError('post-release close failed')
                monkeypatch.setattr(adapter,'close',closed)
            elif fault=='soft_drift': provider.limits=(provider.limits[0]+1,provider.limits[1])
            elif fault=='restore':
                actual=provider.setrlimit
                def restore(key,value):
                    if value[0]==32: raise OSError('restoration failed')
                    actual(key,value)
                monkeypatch.setattr(provider,'setrlimit',restore)
            c.sample_active_inputs(binding,p,previous=first)
    if fault=='none': run()
    else:
        with pytest.raises(Exception): run()
    assert not adapter.nodes
    assert set(os.listdir('/proc/self/fd'))==before
