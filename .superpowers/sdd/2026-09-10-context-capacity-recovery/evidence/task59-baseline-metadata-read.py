"""Read-only metadata for a pinned synthetic-capacity baseline, not admission.

No product import, database copy, whole receipt payload export or write. Candidate
state names are QA metadata only, never native-player identity resolution.
"""
import resource
import signal

resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
signal.alarm(30)

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

START = time.monotonic()
PATH = Path('/var/lib/betboy-live-backup-ssfvf5xs/context-current.db')
SHA = '73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa'
SIZE = 270233600
FIRST = 8000000000000000000
LAST = FIRST + 490000 - 1


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def hashed(descriptor):
    os.lseek(descriptor, 0, os.SEEK_SET)
    value = hashlib.sha256()
    while chunk := os.read(descriptor, 1024 * 1024):
        value.update(chunk)
    return value.hexdigest()


info = PATH.lstat()
assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o440
assert info.st_uid == 0 and info.st_nlink == 1 and info.st_size == SIZE
initial = identity(info)
for suffix in ('-wal', '-shm', '-journal'):
    assert not Path(str(PATH) + suffix).exists()
fd = os.open(PATH, os.O_RDONLY | os.O_NOFOLLOW)
try:
    assert identity(os.fstat(fd)) == initial and hashed(fd) == SHA
    connection = sqlite3.connect(PATH.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        connection.execute('PRAGMA temp_store=MEMORY')
        connection.execute('PRAGMA cache_size=-8192')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")]
        expected = ['active_manifest', 'artifacts', 'context_contents',
                    'context_observations', 'context_snapshots', 'manifests']
        assert tables == expected
        counts = {name: connection.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0]
                  for name in expected}
        namespaces = {'ATP': {'rows': 0, 'maximum_id': 0, 'candidate_collisions': 0},
                      'WTA': {'rows': 0, 'maximum_id': 0, 'candidate_collisions': 0}}
        minimum_clock = maximum_clock = None
        receipt_count = 0
        for key, clock in connection.execute(
                'SELECT event_key,observed_at FROM context_observations ORDER BY rowid'):
            assert isinstance(key, str) and isinstance(clock, str)
            parsed = datetime.datetime.fromisoformat(clock)
            assert parsed.tzinfo is not None and parsed.utcoffset() == datetime.timedelta()
            minimum_clock = parsed if minimum_clock is None else min(minimum_clock, parsed)
            maximum_clock = parsed if maximum_clock is None else max(maximum_clock, parsed)
            receipt_count += 1
            match = re.fullmatch(r'espn:tennis:(ATP|WTA):match:([1-9][0-9]*)', key)
            if match:
                tour, native = match.group(1), int(match.group(2))
                row = namespaces[tour]
                row['rows'] += 1
                row['maximum_id'] = max(row['maximum_id'], native)
                row['candidate_collisions'] += FIRST <= native <= LAST
        assert receipt_count == counts['context_observations'] == 100553
        states = []
        for artifact, created, raw in connection.execute(
                "SELECT digest,created_at,payload FROM artifacts WHERE kind='tennis-tour-state' ORDER BY digest"):
            # State-only metadata. This does not call or replace the actual codec.
            assert len(raw) <= 16 * 1024**2
            payload = json.loads(raw)
            state = payload['state']
            ratings = state['elo']['overall']
            sample = []
            for name, rating in ratings.items():
                if len(sample) < 2:
                    sample.append({'name': name, 'rating_shape': type(rating).__name__})
            states.append({'artifact': artifact, 'created_at': created,
                           'tour': state['tour'], 'training_cutoff': payload['training_cutoff'],
                           'player_count': len(ratings), 'candidate_names': sample})
        assert len(states) == 2 and {item['tour'] for item in states} == {'ATP', 'WTA'}
        connection.rollback()
    finally:
        connection.close()
    assert identity(os.fstat(fd)) == initial and identity(PATH.lstat()) == initial
    assert hashed(fd) == SHA
    for suffix in ('-wal', '-shm', '-journal'):
        assert not Path(str(PATH) + suffix).exists()
    print(json.dumps({'kind': 'read-only-baseline-metadata-not-source-admission',
        'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'baseline_sha256': SHA, 'baseline_bytes': SIZE, 'counts': counts,
        'receipt_clock_min': minimum_clock.isoformat(),
        'receipt_clock_max': maximum_clock.isoformat(),
        'namespace_candidate': [FIRST, LAST], 'namespaces': namespaces, 'states': states,
        'cpu_s': time.process_time(), 'wall_s': time.monotonic() - START,
        'maxrss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        sort_keys=True, separators=(',', ':')))
finally:
    os.close(fd)
