"""Byte-verified owning modules before the authorized joint-law transition.

Copied without modification from 94671485b9659aa3f047491cb7c34f4ddfb03229.
Only historical mathematical evidence uses these modules, never production.
"""
import hashlib
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).parent / 'fixtures' / 'football_pre_joint'
HASHES = {'challenge_engine': '9e3b35cc9c0aba5f611d334336beaccfd4e885b280d9173dd98dcd7c6740922e',
          'football_original': '138fbe5a6570995e7274741dde84e2d4ea1a9cedb7efbaecb2856d91be88af1d',
          'challenge_15k': 'ec42f57e54becc2a08fe6d416468cd7ac49173a46c0e10751a01d22edeb5c04e',
          'parent_engine': '915a49325754ace657227c8195c914a18cd2d5fba83482c8f526d7fb03f75fa5',
          'parent_challenge': '7d7e217282c6e0a9d12aeb38f03340311aaa2895037a79c12226566769535433'}


def source(name):
    data=(ROOT/(name+'.py.txt')).read_bytes()
    assert hashlib.sha256(data).hexdigest()==HASHES[name]
    return data


def load(name):
    key='_pre_joint_'+name
    if key not in sys.modules:
        module=ModuleType(key)
        sys.modules[key]=module
        exec(compile(source(name),str(ROOT/(name+'.py.txt')),'exec'),module.__dict__)
    return sys.modules[key]


def activate(monkeypatch, namespace):
    legacy=load('challenge_engine')
    monkeypatch.setitem(sys.modules,'challenge_engine',legacy)
    monkeypatch.setitem(sys.modules,'football_original',load('football_original'))
    for key,value in list(namespace.items()):
        if key in ('engine','challenge_engine'):
            monkeypatch.setitem(namespace,key,legacy)
        elif getattr(value,'__module__',None)=='challenge_engine' and hasattr(legacy,key):
            monkeypatch.setitem(namespace,key,getattr(legacy,key))
    return legacy
