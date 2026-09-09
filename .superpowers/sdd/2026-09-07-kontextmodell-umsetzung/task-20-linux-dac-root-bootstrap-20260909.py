"""Fixed in-memory bootstrap for the completely reviewed synthetic DAC QA.

Invoke only with the isolated root interpreter on the existing BetBoy VPS.
No selectable input, production mutation, key read or installation interface.
"""
import hashlib
import os
import stat
from pathlib import Path

path = Path('/tmp/betboy-context-qa.9xr68INa/root-dac-smoke-958836d1.py')
for part in (path, *path.parents):
    assert not stat.S_ISLNK(part.lstat().st_mode)
descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    before = os.fstat(descriptor)
    assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1
    assert (before.st_uid, before.st_gid, stat.S_IMODE(before.st_mode)) == (1000, 1000, 0o600)
    assert before.st_size <= 65536
    with os.fdopen(descriptor, 'rb', closefd=False) as stream:
        raw = stream.read(65537)
    def signature(value):
        return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
                value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    assert signature(before) == signature(os.fstat(descriptor)) == signature(path.lstat())
    assert hashlib.sha256(raw).hexdigest() == '958836d1a74376cf76f35d44b526cfd4b7438deadc61f539a7d86b6e8b0ad756'
finally:
    os.close(descriptor)

exec(compile(raw, 'reviewed-fixed-synthetic-DAC-smoke', 'exec'), {'__name__': '__main__'})
