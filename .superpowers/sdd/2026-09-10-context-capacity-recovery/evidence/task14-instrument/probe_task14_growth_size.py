"""B0 exact byte sizing only; no D4, model replay, database growth, or proof.

Linux execution, through a separately bounded/root-reviewed supervisor::

    python -I -B - baseline
    python -I -B - generated DAY BASE_ROWS BASE_BYTES PRIOR_ROWS PRIOR_BYTES EVIDENCE_SHA

The script is provided on stdin. Each generated command measures at most one
70,000-receipt day. BASE/PRIOR counts and EVIDENCE_SHA are externally verified
diagnostic lineage, NOT trusted production proof. The supervisor must retain
and check all preceding completed outputs and charge the entire B0 job against
1800 CPU / 3600 wall seconds. No input/limit increases or partial D4 successes.

The only native input is the exact fresh root-sealed file below. Generated
receipts are synthetic scheduled ATP events, never fetched provider facts.
An exact canonical-history byte overflow is a necessary-condition StorageSTOP;
otherwise this helper does NOT establish the feasibility of complete snapshots,
SQLite growth, features/models, persistent proofs, or seven days of operation.
"""

from bisect import bisect_left
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import stat
import sys
import time


SOURCE = Path('/var/lib/betboy-capacity-code-5es6n672/source')
REVISION = '72421d3bdbec4ab15a3d2953cb153e867e7e340a'
INPUT = Path('/var/lib/betboy-live-backup-ssfvf5xs/context-current.db')
INPUT_SHA = '73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa'
INPUT_BYTES = 270_233_600
HISTORY_CAP = 256 * 1024**2
DAILY_RECEIPTS = 70_000
EVENT_PREFIX = '97014'
ALLOWED_KINDS = {'tennis-tour-state', 'tennis-live-winner-original-v1'}
SOURCE_PINS = {
    'context_sources/tennis_status.py': '8c2a8093aa2113564c34088227e5fb0a8c70faf9d52428e74c4995c505a57581',
    'context_observations.py': '9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226',
    'context_sources/tennis.py': '80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739',
    'context_models/contracts.py': '7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8',
    'context_models/tennis_live.py': '5498d79266bf5b5a9e9ddc97610a2318f6abe292c164e8a0bf57b0adfcf09ed0',
    'model_artifacts.py': '6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16',
    'context_snapshots.py': 'de9d8146917f568e1567cd8a92b92b64af1b33157f2afadf3c91c27a153de1da',
    'context_runtime_tennis.py': '1bf3ebaf37b13cd0173ac795a2ddc5ea01918dafe6730881625322c6bf205bed',
    'context_runtime_history_cache.py': '2f13f3064222a5ee9e7fa5a432ff47b36e611322ccede3e31217c2400e8178cc',
    'context_runtime.py': '2425264c6f32cd6bb9b304fa1d1e3389b948f7476eb153ac09fd03b6458d9d21',
    'context_runtime_semantics.py': '0e93f4d40ac22f0d80fde6ae3dec7df57a24806951f332a72872fcd7040cf3cd',
    'runtime_paths.py': '710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c',
}
TABLES = {
    'artifacts', 'manifests', 'active_manifest', 'context_contents',
    'context_observations', 'context_snapshots', 'context_model_rollbacks',
}


class DiagnosticStop(BaseException):
    pass


def require(condition, reason):
    if not condition:
        raise DiagnosticStop(reason)


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def no_companions(path):
    return not any(os.path.lexists(str(path) + suffix)
                   for suffix in ('-wal', '-shm', '-journal'))


def root_directory(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
            and not info.st_mode & 0o022 and path.resolve(strict=True) == path,
            'unsafe root-sealed directory')
    return (str(path), info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)


def validate_native_input():
    require(__debug__ and os.geteuid() == 997, 'native diagnostic requires UID997')
    directory_seals, source_seals = [], []
    for parent in (INPUT.parent, *INPUT.parent.parents, SOURCE, *SOURCE.parents):
        directory_seals.append(root_directory(parent))
    for relative, expected in SOURCE_PINS.items():
        path = SOURCE / relative
        directory_seals.append(root_directory(path.parent))
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and not info.st_mode & 0o022 and path.resolve(strict=True) == path
                and file_sha(path) == expected, 'source pin/seal mismatch')
        source_seals.append((relative, identity(info)))
    before = INPUT.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o440 and before.st_size == INPUT_BYTES
            and INPUT.resolve(strict=True) == INPUT and no_companions(INPUT)
            and file_sha(INPUT) == INPUT_SHA, 'input pin/seal mismatch')
    return identity(before), tuple(directory_seals), tuple(source_seals)


def bind_owners(source):
    """Local tests use the same owners; main admits only exact sealed SOURCE."""
    sys.path.insert(0, str(source))
    names = ('model_artifacts', 'context_observations', 'context_sources.tennis_status',
             'context_snapshots', 'context_models.tennis_live')
    owners = tuple(importlib.import_module(name) for name in names)
    for module in owners:
        require(Path(module.__file__).resolve().is_relative_to(source.resolve()),
                'owning import is outside exact source')
    return owners


class ByteCounter:
    """Exactly sum the per-selected-row encoding counted by _cold_replay_history."""
    def __init__(self):
        self.rows = self.bytes = 0
        self.minimum = None
        self.maximum = 0
        self.sha = hashlib.sha256()

    def add(self, row, canonical_bytes):
        raw = canonical_bytes(row)
        size = len(raw)
        self.rows += 1
        self.bytes += size
        self.minimum = size if self.minimum is None else min(self.minimum, size)
        self.maximum = max(self.maximum, size)
        self.sha.update(size.to_bytes(8, 'big'))
        self.sha.update(raw)
        return size

    def report(self):
        return {'rows': self.rows, 'canonical_bytes': self.bytes,
                'min_row_bytes': self.minimum, 'max_row_bytes': self.maximum,
                'length_framed_stream_sha256': self.sha.hexdigest()}


def selected_single(row, cutoff, status_owner):
    # The same unmodified owning selector validates source fields before scope
    # pruning. Dispatching a valid tour avoids validating every WTA row twice;
    # an invalid/missing tour still enters the owner and must fail, never vanish.
    tour = row['payload'].get('tour')
    selected = status_owner.select_tennis_observations(
        (row,), cutoff=cutoff, tour=tour if tour in ('ATP', 'WTA') else 'ATP')
    require(len(selected) <= 1, 'single receipt produced multiple selected rows')
    return selected


def open_readonly(path):
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=2)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 64 * 1024**2)
    connection.execute('PRAGMA query_only=ON')
    connection.execute('PRAGMA temp_store=MEMORY')
    connection.execute('PRAGMA cache_size=-4096')
    connection.execute('BEGIN')
    return connection


def preflight(connection, owners):
    artifacts, _, _, _, live = owners
    actual = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    require(actual <= TABLES and {'artifacts', 'context_contents', 'context_observations',
                                 'context_snapshots'} <= actual, 'unsupported sizing schema')
    require(connection.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('view','trigger')").fetchone()[0] == 0,
            'unsupported view/trigger schema')
    require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'SQLite quick_check failed')
    headers = connection.execute('SELECT digest,kind,created_at FROM artifacts ORDER BY digest').fetchall()
    require(1 <= len(headers) <= 512, 'artifact sizing bound')
    # CRITICAL: all artifact kinds are inspected BEFORE any artifact/content
    # body. These two kinds cannot create unopened D2 test-inventory protection.
    # This matches the no-known-D2/no-approval early return in the unchanged
    # verify_d2_artifacts owner. Existing unrelated match_outcome rows remain.
    require(all(type(kind) is str and kind in ALLOWED_KINDS for _, kind, _ in headers),
            'D2/approval/unknown artifacts require another opaque sizing contract')
    cutoffs = {'ATP': set(), 'WTA': set()}
    clocks, artifact_bytes, artifact_counts = [], {}, {}
    for key, kind, created_at in headers:
        envelope = artifacts._load_artifact(connection, key)
        require(envelope['kind'] == kind, 'artifact header differs')
        clocks.append(datetime.fromisoformat(created_at))
        artifact_counts[kind] = artifact_counts.get(kind, 0) + 1
        artifact_bytes[kind] = artifact_bytes.get(kind, 0) + connection.execute(
            'SELECT length(payload) FROM artifacts WHERE digest=?', (key,)).fetchone()[0]
        if kind == live.ORIGINAL_ARTIFACT_KIND:
            payload = live.validate_original_publication(envelope['payload'], created_at=created_at)
            origin = payload['origin']
            tour, cutoff = origin['event']['tour'], origin['cutoff']
            require(tour in cutoffs, 'unknown original tour')
            cutoffs[tour].add(cutoff)
            clocks.append(datetime.fromisoformat(cutoff))
    minimum, maximum, count = connection.execute(
        'SELECT min(observed_at),max(observed_at),count(*) FROM context_observations').fetchone()
    require(1 <= count <= 2_000_000 and type(maximum) is str, 'receipt sizing bound')
    clocks.append(datetime.fromisoformat(maximum))
    start = (max(clocks).astimezone(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    require(connection.execute(
        'SELECT count(*) FROM context_observations WHERE event_key LIKE ?',
        (f'espn:tennis:ATP:match:{EVENT_PREFIX}%',)).fetchone()[0] == 0,
        'synthetic event namespace already present')
    require(sum(len(values) for values in cutoffs.values()) <= 512, 'cutoff sizing bound')
    return {'cutoffs': {tour: sorted(values) for tour, values in cutoffs.items()},
            'start': start, 'receipt_count': count, 'receipt_clock_min': minimum,
            'receipt_clock_max': maximum, 'artifact_counts': artifact_counts,
            'artifact_payload_bytes': artifact_bytes, 'tables': actual}


def baseline(connection, owners, metadata, emit):
    artifacts, observations, status, snapshots, _ = owners
    cutoff = metadata['start'] + timedelta(days=7)
    counters = {tour: ByteCounter() for tour in ('ATP', 'WTA')}
    bins = {tour: [[0, 0] for _ in metadata['cutoffs'][tour]] for tour in counters}
    raw_count, content_bytes = 0, 0
    kinds = {}
    for stored in connection.execute(observations._SELECT + ' ORDER BY r.observed_at,r.digest'):
        row = observations._decode_receipt(stored)  # No source/scope pruning before physical owner.
        raw_count += 1
        content_bytes += len(stored[8])
        kinds[row['kind']] = kinds.get(row['kind'], 0) + 1
        for candidate in selected_single(row, cutoff, status):
            tour = candidate['payload']['tour']
            size = counters[tour].add(candidate, artifacts.canonical_bytes)
            slot = bisect_left(metadata['cutoffs'][tour], candidate['observed_at'])
            if slot < len(bins[tour]):
                bins[tour][slot][0] += 1
                bins[tour][slot][1] += size
    require(raw_count == metadata['receipt_count'], 'physical scan count differs')
    prefixes = {}
    for tour, entries in bins.items():
        rows = size = 0
        for key, (increment_rows, increment_size) in zip(metadata['cutoffs'][tour], entries):
            rows += increment_rows
            size += increment_size
            prefixes[(tour, key)] = (rows, size)
    snapshot_count = connection.execute('SELECT count(*) FROM context_snapshots').fetchone()[0]
    require(0 <= snapshot_count <= 512, 'snapshot sizing bound')
    snapshot_bytes = refs_bytes = refs_count = 0
    for key, raw, payload_sha in connection.execute(
            'SELECT key,payload,payload_digest FROM context_snapshots ORDER BY key'):
        payload = snapshots._decode_snapshot(key, raw, payload_sha)
        require(payload.get('kind') == 'context-worker-snapshot-v1'
                and payload['event']['sport'] == 'tennis', 'unsupported snapshot sizing kind')
        tour, clock = payload['event']['tour'], payload['base']['cutoff']
        refs = payload['observation_refs']
        require(type(refs) is list and all(type(ref) is str and re.fullmatch('[0-9a-f]{64}', ref) for ref in refs),
                'invalid reference-array sizing input')
        require(refs == sorted(set(refs)), 'reference array is not distinct/sorted')
        array_bytes = len(artifacts.canonical_bytes(refs))
        snapshot_bytes += len(raw)
        refs_bytes += array_bytes
        refs_count += len(refs)
        selected = prefixes.get((tour, clock))
        emit({'phase': 'actual_snapshot_size', 'tour': tour, 'cutoff': clock,
              'payload_bytes': len(raw), 'observation_refs_count': len(refs),
              'observation_refs_canonical_bytes': array_bytes,
              'selected_history_rows': None if selected is None else selected[0],
              'selected_history_bytes': None if selected is None else selected[1],
              'reference_count_matches_current_selection': selected is not None and selected[0] == len(refs)})
    page_count = connection.execute('PRAGMA page_count').fetchone()[0]
    page_size = connection.execute('PRAGMA page_size').fetchone()[0]
    free_pages = connection.execute('PRAGMA freelist_count').fetchone()[0]
    dbstat = None
    try:
        dbstat = [dict(zip(('name', 'pages', 'page_bytes', 'payload_bytes', 'unused_bytes'), row))
                  for row in connection.execute(
                      'SELECT name,count(*),sum(pgsize),sum(payload),sum(unused) FROM dbstat GROUP BY name ORDER BY name')]
        require(len(dbstat) <= 64, 'dbstat sizing bound')
    except sqlite3.OperationalError as exc:
        if str(exc) != 'no such table: dbstat':
            raise
    total_contents, unique_content_bytes = connection.execute(
        'SELECT count(*),coalesce(sum(length(payload)),0) FROM context_contents').fetchone()
    result = {'phase': 'baseline_size', 'measured_receipts': raw_count, 'receipt_kinds': kinds,
              'content_rows': total_contents, 'content_payload_bytes': unique_content_bytes,
              'receipt_referenced_content_bytes': content_bytes,
              'artifact_counts': metadata['artifact_counts'],
              'artifact_payload_bytes': metadata['artifact_payload_bytes'],
              'snapshot_count': snapshot_count, 'snapshot_payload_bytes': snapshot_bytes,
              'snapshot_observation_refs_count': refs_count,
              'snapshot_observation_refs_canonical_bytes': refs_bytes,
              'max_causal_history': {tour: counter.report() for tour, counter in counters.items()},
              'history_cutoff': cutoff.isoformat(), 'synthetic_day1_start': metadata['start'].isoformat(),
              'page_count': page_count, 'page_size': page_size, 'freelist_count': free_pages,
              'logical_file_bytes': page_count * page_size, 'dbstat': dbstat,
              'protected_receipts': 0, 'protected_final_body_guard': 'known_tennis_artifact_kinds_only',
              'measurements_complete': True, 'complete_verification_claimed': False}
    emit(result)
    return result


def generated_physical(global_index, observed, owners, *, tour='ATP'):
    artifacts, observations, status, _, _ = owners
    require(type(global_index) is int and 1 <= global_index <= 7 * DAILY_RECEIPTS,
            'synthetic index bound')
    native_id = EVENT_PREFIX + f'{global_index:014d}'
    competition = {'id': native_id, 'date': (observed + timedelta(days=2)).isoformat(),
                   'competitors': [{'id': '9701490000000000001'}, {'id': '9701490000000000002'}],
                   'status': {'type': {'state': 'pre', 'name': 'STATUS_SCHEDULED', 'completed': False}}}
    records = status.normalize_tennis_status(tour, '97014', competition,
        grouping_slug='mens-singles' if tour == 'ATP' else 'womens-singles', observed_at=observed)
    require(len(records) == 1, 'synthetic scheduled status must be one receipt')
    content = records[0]
    clock = observations.canonical_timestamp(observed)
    raw = artifacts.canonical_bytes(content)
    content_sha = observations.digest(content)
    receipt_sha = observations.digest({'content_digest': content_sha, 'observed_at': clock})
    stored = (receipt_sha, content_sha, content['event_key'], clock, content['schedule_revision'],
              content['source'], content['subject_id'], content['kind'], raw)
    return records[0], stored, observations._decode_receipt(stored)


def generated(connection, owners, metadata, args, emit):
    require(len(args) == 6, 'generated requires six bounded lineage arguments')
    require(all(re.fullmatch('[0-9]{1,12}', value) for value in args[:5]), 'invalid numeric lineage')
    day, base_rows, base_bytes, prior_rows, prior_bytes = map(int, args[:5])
    evidence_sha = args[5]
    require(re.fullmatch('[0-9a-f]{64}', evidence_sha) is not None, 'missing external evidence digest')
    require(1 <= day <= 7 and 0 <= base_rows <= metadata['receipt_count']
            and 0 <= base_bytes <= HISTORY_CAP and prior_rows == (day - 1) * DAILY_RECEIPTS
            and 0 <= prior_bytes <= HISTORY_CAP and base_bytes + prior_bytes <= HISTORY_CAP,
            'invalid/outside-cap prior measured lineage')
    require((prior_rows == 0) == (prior_bytes == 0), 'prior rows/bytes inconsistent')
    artifacts, _, status, _, _ = owners
    clock = metadata['start'] + timedelta(days=day - 1)
    cutoff = metadata['start'] + timedelta(days=day)
    counter = ByteCounter()
    raw_content_bytes = 0
    storage_stop = False
    for offset in range(DAILY_RECEIPTS):
        global_index = prior_rows + offset + 1
        observed = clock + timedelta(seconds=offset, microseconds=1)
        _, physical, row = generated_physical(global_index, observed, owners)
        chosen = status.select_tennis_observations((row,), cutoff=cutoff, tour='ATP')
        require(len(chosen) == 1, 'new ATP row was not selected by owning source')
        counter.add(chosen[0], artifacts.canonical_bytes)
        raw_content_bytes += len(physical[8])
        if base_bytes + prior_bytes + counter.bytes > HISTORY_CAP:
            storage_stop = True
            break
    result = {'phase': 'generated_size', 'synthetic_only': True, 'day': day,
              'synthetic_day1_start': metadata['start'].isoformat(), 'causal_cutoff': cutoff.isoformat(),
              'receipt_generator': 'fully_new_unique_scheduled_ATP_status',
              'externally_measured_baseline_rows': base_rows,
              'externally_measured_baseline_bytes': base_bytes,
              'externally_measured_prior_rows': prior_rows,
              'externally_measured_prior_bytes': prior_bytes,
              'upstream_evidence_sha256': evidence_sha, 'new_receipts': counter.report(),
              'new_content_payload_bytes': raw_content_bytes,
              'combined_selected_rows': base_rows + prior_rows + counter.rows,
              'combined_selected_canonical_bytes': base_bytes + prior_bytes + counter.bytes,
              'history_cap_bytes': HISTORY_CAP, 'storage_stop': storage_stop,
              'necessary_condition_only': True, 'day_completed': counter.rows == DAILY_RECEIPTS,
              'snapshots_generated': 0, 'growth_database_written': False,
              'complete_verification_claimed': False}
    emit(result)
    return result


def main(argv):
    import resource
    require(os.name == 'posix', 'native diagnostic is Linux-only')
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
    started = time.monotonic()
    output_bytes = records = 0
    before = None
    result = None
    error = None
    runtime_identity = None

    def stop(signum, frame):
        raise DiagnosticStop('bounded diagnostic deadline')

    def emit(value):
        nonlocal output_bytes, records
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'))
        output_bytes += len(encoded.encode('utf-8')) + 1
        records += 1
        require(output_bytes <= 1024**2 and records <= 520, 'output bound')
        print(encoded, flush=True)

    for sig in (signal.SIGPROF, signal.SIGALRM, signal.SIGTERM):
        signal.signal(sig, stop)
    signal.setitimer(signal.ITIMER_PROF, 280)
    signal.setitimer(signal.ITIMER_REAL, 285)
    try:
        require(argv and argv[0] in ('baseline', 'generated'), 'unknown sizing mode')
        before = validate_native_input()
        interpreter = Path(sys.executable).resolve(strict=True)
        runtime_identity = {'python_version': sys.version, 'sqlite_version': sqlite3.sqlite_version,
                            'interpreter_realpath': str(interpreter),
                            'interpreter_sha256': file_sha(interpreter),
                            'full_stage_b_runtime_closure_claimed': False}
        owners = bind_owners(SOURCE)
        with closing(open_readonly(INPUT)) as connection:
            try:
                metadata = preflight(connection, owners)
                if argv[0] == 'baseline':
                    require(len(argv) == 1, 'unexpected baseline arguments')
                    result = baseline(connection, owners, metadata, emit)
                else:
                    result = generated(connection, owners, metadata, argv[1:], emit)
            finally:
                connection.rollback()
    except BaseException as exc:
        # Never print a persisted payload, native identifier, or arbitrary
        # exception message. The fixed class identifies bounded failure only.
        error = type(exc).__name__
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.setitimer(signal.ITIMER_REAL, 0)
    try:
        unchanged = before is not None and validate_native_input() == before
        require(runtime_identity is None or file_sha(Path(runtime_identity['interpreter_realpath']))
                == runtime_identity['interpreter_sha256'], 'interpreter changed during diagnostic')
    except BaseException as exc:
        unchanged = False
        error = error or type(exc).__name__
    usage = resource.getrusage(resource.RUSAGE_SELF)
    resources_ok = (usage.ru_utime + usage.ru_stime < 300 and time.monotonic() - started < 300
                    and usage.ru_maxrss < 1024**2)
    complete = result is not None and error is None and unchanged and resources_ok
    emit({'phase': 'diagnostic_summary', 'diagnostic_only': True,
          'source_revision': REVISION, 'input_sha256': INPUT_SHA, 'input_bytes': INPUT_BYTES,
          'mode': argv[0] if argv else None, 'input_unchanged': unchanged,
          'source_and_ancestor_seals_unchanged': unchanged, 'runtime_identity': runtime_identity,
          'measurement_completed': complete, 'error_class': error,
          'cpu_seconds': round(usage.ru_utime + usage.ru_stime, 6),
          'wall_seconds': round(time.monotonic() - started, 6), 'peak_rss_kib': usage.ru_maxrss,
          'resources_ok': resources_ok, 'complete_verification_claimed': False,
          'external_cumulative_budget_required': True})
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
