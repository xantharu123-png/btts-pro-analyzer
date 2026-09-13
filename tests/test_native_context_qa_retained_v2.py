"""V2 special-node boundary; native FIFO assertions are never faked on Windows."""
import importlib.util
import os
from pathlib import Path, PurePosixPath
import stat
import sys

import pytest


def catalogue():
    spec = importlib.util.spec_from_file_location('retained_v2', Path(__file__).with_name('native_context_receipt_diagnostic_catalogue.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declared(c):
    current = PurePosixPath(c.HISTORICAL_FIFO).parent
    ancestors = []
    while str(current).startswith(c.HISTORICAL_FIFO_ROOT):
        ancestors.append(dict(path=str(current), identity=[1, 2, stat.S_IFDIR|0o700, 1, 0, 1, 1], allocated=0))
        current = current.parent
    return dict(path=c.HISTORICAL_FIFO, identity=[1, 3, stat.S_IFIFO|0o600, 1, 0, 1, 1], allocated=0, ancestors=ancestors)


def test_v2_shape_is_closed_and_v1_will_not_accept_it():
    c = catalogue()
    fifo = declared(c)
    assert c.validate_historical_fifo(fifo) == fifo
    raw = c.canonical(dict(format='betboy-receipt-diagnostic-retained-v2', roots=[],
                           backup_rollback_reserve=4*c.GIB, historical_fifo=fifo))
    with pytest.raises(Exception):
        c.validate_retained(raw)


@pytest.mark.parametrize('mutation', ['path', 'type', 'bool', 'ancestor', 'extra', 'root', 'missing'])
def test_metadata_exception_cannot_be_broadened(mutation):
    c = catalogue()
    value = declared(c)
    if mutation == 'path': value['path'] += '2'
    if mutation == 'type': value['identity'][2] = stat.S_IFREG|0o600
    if mutation == 'bool': value['identity'][0] = True
    if mutation == 'ancestor': value['ancestors'][0]['path'] += '2'
    if mutation == 'extra': value['trusted'] = True
    if mutation == 'root': value['ancestors'][-1]['identity'][2] = stat.S_IFLNK|0o777
    if mutation == 'missing': value['ancestors'].pop()
    with pytest.raises(Exception):
        c.validate_historical_fifo(value)


@pytest.fixture
def native_tree(tmp_path, monkeypatch):
    if sys.platform != 'linux':
        pytest.skip('actual Linux FIFO/no-follow required')
    c = catalogue()
    root = tmp_path/'retained'
    fifo = root/'green'/'fixtures'/'known'/'fifo'
    fifo.parent.mkdir(parents=True)
    (root/'body').write_bytes(b'complete regular contents')
    os.mkfifo(fifo, 0o600)
    monkeypatch.setattr(c, 'HISTORICAL_FIFO_ROOT', str(root))
    monkeypatch.setattr(c, 'HISTORICAL_FIFO', str(fifo))
    def meta(path):
        info = path.lstat()
        return dict(path=str(path), identity=list(c.old()['identity'](info)), allocated=c._allocation(info))
    try:
        value = meta(fifo)
        value['ancestors'] = [meta(p) for p in fifo.parents if p.is_relative_to(root)]
        yield c, root, fifo, value
    finally:
        # These three nodes are created only by this fresh fixture. Do not leave
        # additional live FIFOs in the retained audit tree; no old evidence is
        # touched, and the result/assertions remain in the test report.
        for node in (fifo, fifo.with_name('old'), root/'extra'):
            assert node.parent.is_relative_to(root)
            node.unlink(missing_ok=True)


def test_native_fifo_is_never_opened_and_all_regular_bytes_are_hashed(native_tree, monkeypatch):
    c, root, fifo, value = native_tree
    original = os.open
    def guarded(name, flags, *args, **kwargs):
        assert os.fsdecode(name) not in ('fifo', str(fifo)), 'FIFO must never be opened'
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', guarded)
    before = c.retained_root_v2(root, historical_fifo=value)
    assert before['fifos'] == 1 and before['files'] == 1
    (root/'body').write_bytes(b'different regular bytes!')
    after = c.retained_root_v2(root, historical_fifo=value)
    assert after['membership_sha256'] != before['membership_sha256']


def test_native_v1_still_rejects_the_same_fifo(native_tree):
    c, root, _, _ = native_tree
    with pytest.raises(Exception):
        c.retained_root(root)


@pytest.mark.parametrize('mutation', ['replace_fifo', 'second_fifo', 'missing_fifo', 'ancestor_epoch', 'symlink'])
def test_native_changed_or_additional_special_node_is_rejected(native_tree, mutation):
    c, root, fifo, value = native_tree
    if mutation == 'replace_fifo':
        fifo.rename(fifo.with_name('old'))
        os.mkfifo(fifo)
    if mutation == 'second_fifo': os.mkfifo(root/'extra')
    if mutation == 'missing_fifo': fifo.unlink()
    if mutation == 'ancestor_epoch': os.utime(fifo.parent, ns=(1, 1))
    if mutation == 'symlink':
        fifo.rename(fifo.with_name('old'))
        fifo.symlink_to('old')
    with pytest.raises(Exception):
        c.retained_root_v2(root, historical_fifo=value)
