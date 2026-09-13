"""Bounded read-only baseline page/kind metadata; no model or source authority."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import stat
import time

resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
signal.alarm(30)
started = time.monotonic_ns()
source = Path('/var/lib/betboy-live-backup-ssfvf5xs/context-current.db')
expected = '73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa'


def identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_uid, value.st_gid, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_blocks)


def check():
    if identity(os.fstat(fd)) != initial or identity(source.lstat()) != initial:
        raise RuntimeError('baseline identity changed')
    if any(os.path.lexists(str(source) + suffix) for suffix in ('-wal', '-shm', '-journal')):
        raise RuntimeError('baseline companion exists')


def checksum():
    check()
    value = hashlib.sha256()
    offset = 0
    while offset < initial[6]:
        block = os.pread(fd, min(1024**2, initial[6] - offset), offset)
        if not block:
            raise RuntimeError('short baseline read')
        offset += len(block)
        value.update(block)
    check()
    if value.hexdigest() != expected:
        raise RuntimeError('baseline byte hash changed')


for parent in source.parents:
    metadata = parent.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise RuntimeError('baseline ancestor is not protected')
fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
try:
    metadata = os.fstat(fd)
    initial = identity(metadata)
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or metadata.st_uid != 0 or metadata.st_mode & 0o222 or metadata.st_size != 270233600):
        raise RuntimeError('baseline file admission differs')
    checksum()
    header = os.pread(fd, 100, 0)
    if header[:16] != b'SQLite format 3\0' or header[18:20] != b'\x01\x01':
        raise RuntimeError('baseline is not standalone rollback format')
    connection = sqlite3.connect(source.as_uri() + '?mode=ro&immutable=1', uri=True,
                                 timeout=0, isolation_level=None, cached_statements=0)
    try:
        connection.execute('PRAGMA query_only=ON').close()
        connection.execute('PRAGMA trusted_schema=OFF').close()
        connection.execute('PRAGMA temp_store=MEMORY').close()
        connection.execute('PRAGMA cache_size=-8192').close()
        connection.execute('BEGIN').close()
        names = ('page_size', 'page_count', 'encoding', 'journal_mode', 'auto_vacuum',
                 'schema_version', 'user_version', 'application_id', 'query_only', 'trusted_schema')
        profile = {name: connection.execute('PRAGMA ' + name).fetchone()[0] for name in names}
        kinds = connection.execute(
            'SELECT kind,count(*),min(created_at),max(created_at) FROM artifacts GROUP BY kind ORDER BY kind'
        ).fetchmany(17)
        if len(kinds) > 16:
            raise RuntimeError('artifact kind metadata exceeded bound')
        table_names = connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        ).fetchmany(17)
        if len(table_names) > 16:
            raise RuntimeError('table metadata exceeded bound')
        check()
    finally:
        connection.close()
    checksum()
    result = {'format': 'task61-baseline-profile-observation-v1', 'source': str(source),
              'source_sha256': expected, 'bytes': metadata.st_size,
              'header_page_size': int.from_bytes(header[16:18], 'big'),
              'header_encoding': int.from_bytes(header[56:60], 'big'),
              'profile': profile, 'artifact_kind_counts_clocks': kinds,
              'present_tables': [row[0] for row in table_names],
              'sqlite_runtime': sqlite3.sqlite_version, 'source_identity_unchanged': True,
              'observed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'cpu_ns_before_output': time.process_time_ns(),
              'wall_ns_after_import_before_output': time.monotonic_ns() - started,
              'rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
finally:
    os.close(fd)
encoded = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii') + b'\n'
if len(encoded) > 8192:
    raise RuntimeError('bounded metadata output exceeded')
view = memoryview(encoded)
while view:
    written = os.write(1, view)
    if written <= 0:
        raise RuntimeError('metadata output stalled')
    view = view[written:]
