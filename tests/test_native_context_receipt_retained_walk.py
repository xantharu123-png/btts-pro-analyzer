"""Task62 focused walker QA; modeled FD calls are NOT native openat proof."""
from contextlib import contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).absolute().parents[1]


def catalogue():
    name = 'task62_catalogue'
    spec = importlib.util.spec_from_file_location(name, ROOT/'tests/native_context_receipt_diagnostic_catalogue.py')
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    c.old()
    return c


def reference(c, root):
    """Independent path-based typed inventory oracle, no optimized walker call."""
    records = []
    def visit(path, name):
        info = path.lstat()
        kind = 'directory' if stat.S_ISDIR(info.st_mode) else 'symlink' if stat.S_ISLNK(info.st_mode) else 'regular'
        if kind == 'directory':
            checksum = None
        elif kind == 'symlink':
            checksum = hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
        else:
            assert stat.S_ISREG(info.st_mode)
            h = hashlib.sha256()
            with path.open('rb') as stream:
                while block := stream.read(1024**2):
                    h.update(block)
            checksum = h.hexdigest()
        records.append(dict(path=name,kind=kind,identity=list(c.old()['identity'](info)),
                            allocated=c._allocation(info),size=info.st_size,sha256=checksum))
        if kind == 'directory':
            for child in sorted(path.iterdir(),key=lambda p:p.name):
                visit(child,child.name if name=='.' else name+'/'+child.name)
    visit(root,'.')
    return dict(path=str(root),identity=records[0]['identity'],
        membership_sha256=hashlib.sha256(b''.join(c.canonical(r)+b'\n' for r in records)).hexdigest(),
        files=sum(r['kind']=='regular' for r in records),directories=sum(r['kind']=='directory' for r in records),
        symlinks=sum(r['kind']=='symlink' for r in records),logical=sum(r['size'] for r in records),
        allocated=sum(r['allocated'] for r in records))


def tree(root, *, links=False):
    (root/'a'/'deep'/'lower').mkdir(parents=True)
    (root/'Z').mkdir()
    (root/'empty').write_bytes(b'')
    (root/'a'/'one').write_bytes(b'one')
    (root/'a'/'deep'/'lower'/'large').write_bytes(b'large'*300000)
    (root/'Z'/' mixed name ').write_bytes(b'mixed')
    if links:
        os.link(root/'a'/'one',root/'hardlink')
        os.symlink('../outside-not-read',root/'a'/'inert')
        os.symlink('a',root/'directory-link')


class ModeledFD:
    """Real file bytes/stats, modeled directory FDs; never labeled Linux QA."""
    O_RDONLY=os.O_RDONLY
    O_NOFOLLOW=0x20000000
    O_DIRECTORY=0x10000000
    O_NONBLOCK=0x08000000
    O_CLOEXEC=0x04000000
    fsencode=staticmethod(os.fsencode)
    def __init__(self):
        self.directories={}
        self.files=set()
        self.opens=[]
        self.next_fd=-100
    def path(self,name,dir_fd=None):
        return Path(name) if dir_fd is None else self.directories[dir_fd]/os.fsdecode(name)
    def open(self,name,flags,*,dir_fd=None):
        path=self.path(name,dir_fd)
        self.opens.append((str(name),dir_fd,flags))
        if path.is_symlink():
            raise OSError('modeled O_NOFOLLOW')
        if flags & self.O_DIRECTORY:
            assert path.is_dir()
            self.next_fd-=1
            self.directories[self.next_fd]=path
            return self.next_fd
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0))
        self.files.add(fd)
        return fd
    def close(self,fd):
        if fd in self.directories:
            del self.directories[fd]
        else:
            os.close(fd)
            self.files.remove(fd)
    def fstat(self,fd):
        return self.directories[fd].stat() if fd in self.directories else os.fstat(fd)
    def stat(self,name,*,dir_fd=None,follow_symlinks=False):
        assert follow_symlinks is False
        return self.path(name,dir_fd).lstat()
    def scandir(self,fd):
        assert fd in self.directories
        return os.scandir(self.directories[fd])
    def readlink(self,name,*,dir_fd=None):
        return os.fsencode(os.readlink(self.path(name,dir_fd)))
    def read(self,fd,count):
        return os.read(fd,count)


def modeled(c, monkeypatch):
    adapter=ModeledFD()
    old=dict(c.old())
    calls=[]
    @contextmanager
    def opened(path,directory=False):
        assert directory is True
        calls.append(str(path))
        fd=adapter.open(path,adapter.O_RDONLY|adapter.O_DIRECTORY|adapter.O_NOFOLLOW)
        try:
            yield fd,adapter.fstat(fd)
        finally:
            adapter.close(fd)
    old['opened']=opened
    # Windows fstat has different ctime precision. This model substitutes the
    # mtime field for ctime; native tests retain the actual seven-field identity.
    old['identity']=lambda info:(info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_mtime_ns)
    monkeypatch.setattr(c,'_OLD_CATALOGUE',old)
    monkeypatch.setattr(c,'os',adapter)
    return adapter,calls


def test_modeled_fd_walk_uses_one_root_entry_and_relative_descendants(tmp_path,monkeypatch):
    c=catalogue()
    tree(tmp_path)
    adapter,calls=modeled(c,monkeypatch)
    expected=reference(c,tmp_path)
    actual=c._retained_root_linux(tmp_path)
    assert c.canonical(actual)==c.canonical(expected)
    assert calls==[str(tmp_path)]
    assert len(adapter.opens)==actual['files']+actual['directories']
    assert all(parent is not None and '/' not in name and '\\' not in name for name,parent,_ in adapter.opens[1:])
    assert all(flags & adapter.O_NOFOLLOW and flags & adapter.O_CLOEXEC for _,_,flags in adapter.opens[1:])
    assert not adapter.files and not adapter.directories


def test_portable_unchanged_inventory_matches_independent_oracle(tmp_path):
    c=catalogue()
    tree(tmp_path)
    assert c.canonical(c.retained_root(tmp_path))==c.canonical(reference(c,tmp_path))


@pytest.mark.skipif(sys.platform!='linux',reason='actual Linux dir_fd/openat/no-follow evidence required')
def test_native_ancestor_open_scaling_and_complete_equivalence(tmp_path,monkeypatch):
    c=catalogue()
    tree(tmp_path,links=True)
    before=reference(c,tmp_path)
    legacy=getattr(c,'_retained_root_portable',c.retained_root)
    assert c.canonical(legacy(tmp_path))==c.canonical(before)
    actual_open=os.open
    calls=[]
    def tracked(name,flags,*args,**kwargs):
        calls.append((str(name),kwargs.get('dir_fd')))
        return actual_open(name,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',tracked)
    result=c.retained_root(tmp_path)
    assert c.canonical(result)==c.canonical(before)
    assert sum(name=='/' for name,_ in calls)==1
    assert len(calls)==len(tmp_path.parts)-1+result['files']+result['directories']
    assert all(name=='/' or parent is not None for name,parent in calls)


def changed(info, **values):
    fields={name:getattr(info,name) for name in dir(info) if name.startswith('st_')}
    return SimpleNamespace(**dict(fields,**values))


FAULTS=('read','stat','scandir','close','file_epoch','named_epoch','directory_epoch',
        'directory_replacement','file_replacement','grow','shrink','membership','unsupported','allocation')


def faulty_walk(c, adapter, root, monkeypatch, fault):
    """Faults reach real walker call boundaries; all must refuse a result."""
    original={name:getattr(adapter,name) for name in ('read','stat','scandir','close','fstat','open')}
    fired=[]
    if fault in ('read','grow','shrink'):
        def read(fd,count):
            raw=original['read'](fd,count)
            if not fired and raw:
                fired.append(fault)
                if fault=='read': raise OSError('injected read error')
                if fault=='grow': return raw+b'longer'
                return b''
            return raw
        monkeypatch.setattr(adapter,'read',read)
    elif fault=='scandir':
        def scandir(fd):
            fired.append(fault)
            raise OSError('injected scandir error')
        monkeypatch.setattr(adapter,'scandir',scandir)
    elif fault=='close':
        def close(fd):
            original['close'](fd)
            if not fired:
                fired.append(fault)
                raise OSError('injected post-release close error')
        monkeypatch.setattr(adapter,'close',close)
    elif fault in ('file_epoch','directory_epoch','directory_replacement','allocation'):
        seen={}
        def fstat(fd):
            info=original['fstat'](fd)
            seen[fd]=seen.get(fd,0)+1
            wantdir=fault in ('directory_epoch','directory_replacement')
            if not fired and stat.S_ISDIR(info.st_mode)==wantdir and (not wantdir or seen[fd]>=2):
                fired.append(fault)
                if fault=='directory_replacement': return changed(info,st_ino=info.st_ino+1)
                if fault=='allocation': return changed(info,st_size=8*1024**3+1)
                return changed(info,st_mtime_ns=info.st_mtime_ns+1)
            return info
        monkeypatch.setattr(adapter,'fstat',fstat)
    elif fault=='membership':
        calls={}
        def scandir(fd):
            calls[fd]=calls.get(fd,0)+1
            if not fired and calls[fd]==2:
                fired.append(fault)
                @contextmanager
                def empty(): yield iter(())
                return empty()
            return original['scandir'](fd)
        monkeypatch.setattr(adapter,'scandir',scandir)
    else:
        seen={}
        def named(name,**kwargs):
            info=original['stat'](name,**kwargs)
            key=(kwargs.get('dir_fd'),str(name))
            seen[key]=seen.get(key,0)+1
            if not fired and stat.S_ISREG(info.st_mode) and (fault not in ('named_epoch','file_replacement') or seen[key]>=2):
                fired.append(fault)
                if fault=='stat': raise OSError('injected stat error')
                if fault=='unsupported': return changed(info,st_mode=stat.S_IFIFO|0o600)
                if fault=='file_replacement': return changed(info,st_ino=info.st_ino+1)
                return changed(info,st_mtime_ns=info.st_mtime_ns+1)
            return info
        monkeypatch.setattr(adapter,'stat',named)
    with pytest.raises(Exception):
        c._retained_root_linux(root)
    assert fired==[fault]


@pytest.mark.parametrize('fault',FAULTS)
def test_modeled_error_paths_refuse_and_close_all_owned_descriptors(tmp_path,monkeypatch,fault):
    c=catalogue()
    tree(tmp_path)
    adapter,_=modeled(c,monkeypatch)
    faulty_walk(c,adapter,tmp_path,monkeypatch,fault)
    assert not adapter.files and not adapter.directories


def native_facade(c,monkeypatch):
    adapter=SimpleNamespace(**{name:getattr(os,name) for name in (
        'O_RDONLY','O_DIRECTORY','O_NOFOLLOW','O_NONBLOCK','O_CLOEXEC','open','close','fstat','stat','scandir','readlink','read','fsencode')})
    monkeypatch.setattr(c,'os',adapter)
    return adapter


@pytest.mark.skipif(sys.platform!='linux',reason='actual Linux error/unwind descriptor proof required')
@pytest.mark.parametrize('fault',FAULTS)
def test_native_error_paths_refuse_and_close_all_owned_descriptors(tmp_path,monkeypatch,fault):
    c=catalogue()
    tree(tmp_path,links=True)
    adapter=native_facade(c,monkeypatch)
    before=set(os.listdir('/proc/self/fd'))
    faulty_walk(c,adapter,tmp_path,monkeypatch,fault)
    assert set(os.listdir('/proc/self/fd'))==before


@pytest.mark.skipif(sys.platform!='linux',reason='actual no-follow named replacement and symlink proof required')
@pytest.mark.parametrize('target',['file','directory','symlink','root'])
def test_native_real_replacements_are_rejected_without_fd_leaks(tmp_path,monkeypatch,target):
    c=catalogue()
    root=tmp_path/'tree'
    root.mkdir()
    (root/'file').write_bytes(b'original content')
    (root/'directory').mkdir()
    os.symlink('missing-one',root/'symlink')
    adapter=native_facade(c,monkeypatch)
    actual_open,actual_readlink=adapter.open,adapter.readlink
    fired=[]
    def opened(name,flags,**kwargs):
        if not fired and target in ('file','directory') and name==target:
            fired.append(target)
            (root/target).rename(root/(target+'-preserved'))
            os.symlink('missing-target',root/target)
        elif not fired and target=='root':
            fired.append(target)
            root.rename(tmp_path/'preserved-root')
            root.mkdir()
        return actual_open(name,flags,**kwargs)
    def readlink(name,**kwargs):
        result=actual_readlink(name,**kwargs)
        if target=='symlink' and not fired:
            fired.append(target)
            (root/'symlink').unlink()
            os.symlink('missing-two',root/'symlink')
        return result
    monkeypatch.setattr(adapter,'open',opened)
    monkeypatch.setattr(adapter,'readlink',readlink)
    before=set(os.listdir('/proc/self/fd'))
    with pytest.raises(Exception): c.retained_root(root)
    assert fired==[target]
    assert set(os.listdir('/proc/self/fd'))==before


@pytest.mark.skipif(sys.platform!='linux',reason='actual per-alias native content reads required')
def test_native_hardlinks_and_fresh_calls_never_skip_content_reads(tmp_path,monkeypatch):
    c=catalogue()
    (tmp_path/'original').write_bytes(b'content'*200000)
    os.link(tmp_path/'original',tmp_path/'alias')
    adapter=native_facade(c,monkeypatch)
    actual=adapter.read
    lengths=[]
    def read(fd,size):
        raw=actual(fd,size)
        lengths.append(len(raw))
        return raw
    monkeypatch.setattr(adapter,'read',read)
    first=c.retained_root(tmp_path)
    second=c.retained_root(tmp_path)
    assert first==second
    assert sum(lengths)==4*1400000
    assert first['files']==2


@pytest.mark.parametrize('bound',['depth','path','file_size','directory_count','entry_count','allocation'])
def test_modeled_bounds_refuse_without_leaks(tmp_path,monkeypatch,bound):
    c=catalogue()
    tree(tmp_path)
    adapter,_=modeled(c,monkeypatch)
    if bound=='path':
        monkeypatch.setattr(adapter,'fsencode',lambda name:b'x'*2049)
    elif bound=='depth':
        # Exercise the actual recursion/depth condition using a deterministic
        # component-count proxy, not a relaxed production depth constant.
        actual=c.PurePosixPath
        monkeypatch.setattr(c,'PurePosixPath',lambda name:SimpleNamespace(parts=('x',)*33) if name!='.' else actual(name))
    elif bound in ('directory_count','entry_count'):
        actual=adapter.scandir
        limit=50001 if bound=='directory_count' else 49999
        original_stat=adapter.stat
        target=(tmp_path/'a'/'one').lstat()
        @contextmanager
        def scandir(fd):
            if bound=='directory_count' or adapter.directories[fd].name in ('Z','deep','lower','a'):
                yield (SimpleNamespace(name=str(n)) for n in range(limit))
            else:
                with actual(fd) as items: yield items
        if bound=='entry_count':
            def stat_name(name,**kwargs):
                if str(name).isdigit(): return changed(target,st_mode=stat.S_IFLNK|0o777,st_size=1)
                return original_stat(name,**kwargs)
            monkeypatch.setattr(adapter,'stat',stat_name)
            monkeypatch.setattr(adapter,'readlink',lambda *args,**kwargs:b'x')
            # Four synthetic wide directories plus root metadata exceed200000.
            for name in ('deep','lower'): (tmp_path/name).mkdir()
        monkeypatch.setattr(adapter,'scandir',scandir)
    elif bound=='allocation':
        monkeypatch.setattr(c,'_allocation',lambda info:65*1024**3)
    else:
        actual=adapter.stat
        def observed(name,**kwargs):
            info=actual(name,**kwargs)
            if stat.S_ISREG(info.st_mode):
                return changed(info,st_size=8*1024**3+1)
            return info
        monkeypatch.setattr(adapter,'stat',observed)
    with pytest.raises(Exception): c._retained_root_linux(tmp_path)
    assert not adapter.files and not adapter.directories


@pytest.mark.skipif(sys.platform!='linux',reason='actual Linux FIFO refusal must not block or leak')
def test_native_fifo_refused_without_open_or_fd_leak(tmp_path,monkeypatch):
    c=catalogue()
    os.mkfifo(tmp_path/'fifo')
    adapter=native_facade(c,monkeypatch)
    def forbidden(*args,**kwargs): raise AssertionError('unsupported FIFO reached open')
    monkeypatch.setattr(adapter,'open',forbidden)
    before=set(os.listdir('/proc/self/fd'))
    with pytest.raises(c.DiagnosticError): c.retained_root(tmp_path)
    assert set(os.listdir('/proc/self/fd'))==before
