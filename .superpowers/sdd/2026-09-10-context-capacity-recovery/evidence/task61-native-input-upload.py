"""One fixed code-archive upload; no imported application or worker launch."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

signal.alarm(30)
assert os.getresuid() == os.getresgid() == (0,) * 3
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
os.umask(0o022)
root = Path("/var/lib/betboy-receipt-input-task61-01")
registry = Path("/var/lib/betboy-receipt-registry-task61-01")
job = Path("/var/lib/betboy-receipt-task61-01")
for path in (Path("/"), Path("/var"), Path("/var/lib")):
    info = path.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022
for path in (root, registry, job):
    assert not os.path.lexists(path), "new namespace already exists; preserve it"
space = os.statvfs(root.parent)
assert space.f_bavail * space.f_frsize >= 8 * 1024**3 + 16 * 1024**2 + 1024**2
parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    for path, mode in ((root, 0o755), (registry, 0o700), (job, 0o755)):
        os.mkdir(path, mode)
        os.fsync(parent_fd)
finally:
    os.close(parent_fd)
archive = root / "task61-1632072-01.tar"
fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
hasher, count = hashlib.sha256(), 0
try:
    while block := os.read(0, min(1024**2, 9533441 - count)):
        count += len(block)
        assert count <= 9533440, "archive stream exceeds exact size"
        hasher.update(block)
        pending = memoryview(block)
        while pending:
            written = os.write(fd, pending)
            assert written > 0
            pending = pending[written:]
    assert count == 9533440 and hasher.hexdigest() == "daf6ac61183bb3a42f8401f7568b2020a0f4bdef07d07a72d295e61363bc4d4c"
    os.fsync(fd)
    os.fchmod(fd, 0o444)
    os.fsync(fd)
finally:
    os.close(fd)
root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    os.fsync(root_fd)
finally:
    os.close(root_fd)
print(json.dumps(dict(format="betboy-task61-fixed-upload-v1", path=str(archive),
    bytes=count, sha256=hasher.hexdigest(), allocated=archive.stat().st_blocks * 512,
    created=[str(root), str(registry), str(job)], cpu_ns=time.process_time_ns(),
    observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    application_changed=False, archive_executed=False), sort_keys=True, separators=(",", ":")))
