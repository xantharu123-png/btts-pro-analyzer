"""Guarded fixed Task61 receipt owner; no product import at module load."""
from contextlib import contextmanager
import ctypes
import dataclasses
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

FORMAT = 'betboy-native-receipt-diagnostic-result-v1'
MIB = 1024**2


def require(value, message):
    if not value:
        raise RuntimeError(message)


def require_guard():
    require(sys.platform == 'linux' and os.uname().machine == 'x86_64', 'native Linux/x86_64 worker required')
    require((sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0),
            'assertion-enabled -I -S -B required')
    import resource
    require(os.getresuid() == (65534,)*3 and os.getresgid() == (65534,)*3 and os.getgroups() == [], 'worker identity differs')
    with open('/proc/self/status', 'rb') as stream:
        raw = stream.read(65537)
    require(len(raw) <= 65536, 'bounded status required')
    fields = dict(line.split(':', 1) for line in raw.decode('ascii').splitlines())
    for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'):
        require(int(fields[key].strip(), 16) == 0, 'capabilities remain')
    for key, expected in (('Threads', '1'), ('NoNewPrivs', '1'), ('Seccomp', '2'), ('TracerPid', '0')):
        require(fields[key].strip() == expected, 'guard state differs')
    require(ctypes.CDLL(None).prctl(3, 0, 0, 0, 0) == 0, 'worker dumpability differs')
    for key, value in ((resource.RLIMIT_CPU, 240), (resource.RLIMIT_FSIZE, 512*MIB),
                       (resource.RLIMIT_AS, 2*1024**3), (resource.RLIMIT_NPROC, 0), (resource.RLIMIT_CORE, 0)):
        require(resource.getrlimit(key) == (value, value), 'worker resource guard differs')


def held_namespace(path, *, expected=None, supplied=None):
    with Path(path).open('rb') as stream:
        raw = stream.read(MIB + 1)
    require(0 < len(raw) <= MIB and (expected is None or hashlib.sha256(raw).hexdigest() == expected), 'held module pin differs')
    namespace = dict(__name__='_receipt_worker_held', __file__=str(path))
    namespace.update(supplied or {})
    exec(compile(raw, str(path), 'exec'), namespace)
    return namespace


class PhaseRecorder:
    def __init__(self, progress):
        self.progress = progress
        self.stack, self.occurrences, self.summary = [], {}, []
        self.completed = self.new_contents = self.new_receipts = 0
        self.append_cpu = self.append_wall = 0
        self.append_calls = 0

    def emit(self, event, phase, occurrence, started, exc=None):
        now_cpu, now_wall = time.process_time_ns(), time.monotonic_ns()
        self.progress.append(dict(event=event, phase=phase, occurrence=occurrence, depth=len(self.stack),
            completed=self.completed, cpu_ns=now_cpu, wall_ns=now_wall,
            phase_cpu_ns=now_cpu-started[0], phase_wall_ns=now_wall-started[1],
            submitted=self.completed, new_contents=self.new_contents, new_receipts=self.new_receipts,
            exception=None if exc is None else type(exc).__name__[:64]))

    def begin(self, phase):
        occurrence = self.occurrences.get(phase, 0) + 1
        self.occurrences[phase] = occurrence
        started = time.process_time_ns(), time.monotonic_ns()
        self.stack.append((phase, occurrence, started))
        self.emit('begin', phase, occurrence, started)

    def end(self, exc=None):
        phase, occurrence, started = self.stack[-1]
        self.emit('end' if exc is None else 'fail', phase, occurrence, started, exc)
        self.stack.pop()
        require(len(self.summary) < 64, 'phase summary bound')
        self.summary.append(dict(phase=phase, occurrence=occurrence, inclusive_cpu_ns=time.process_time_ns()-started[0],
            inclusive_wall_ns=time.monotonic_ns()-started[1], returned=exc is None,
            call_count=self.append_calls if phase == 'append' else None,
            call_cpu_ns=self.append_cpu if phase == 'append' else None,
            call_wall_ns=self.append_wall if phase == 'append' else None))

    @contextmanager
    def phase(self, phase):
        self.begin(phase)
        try:
            yield
        except BaseException as exc:
            self.end(exc)
            raise
        else:
            self.end()


def measure_corpus(source, profile, source_sha256, work, progress, *, recorder=None):
    """Real unchanged owner and generator, exactly one fixed 1024-row call."""
    from context_storage_v2 import receipt_corpus as owner
    recorder = recorder or PhaseRecorder(progress)
    if not recorder.occurrences:
        # Portable direct-call fixture retains the same complete phase grammar.
        for phase in ('worker_setup', 'profile', 'source_open'):
            with recorder.phase(phase):
                pass
    original, append_active = [], False
    def wrap(target, name, phase):
        actual = getattr(target, name)
        original.append((target, name, actual))
        def call(*args, **kwargs):
            nonlocal append_active
            if phase == 'ledger_finish' and append_active:
                recorder.end()
                append_active = False
            if phase == 'writer_close':
                # Generator/progress failures can reach real owner cleanup
                # without another append call. Do not obstruct its cleanup.
                io_error = None
                if append_active:
                    try:
                        recorder.end(sys.exception() or RuntimeError('append iteration incomplete'))
                    except BaseException as exc:
                        io_error = exc
                    append_active = False
                try:
                    recorder.begin(phase)
                except BaseException as exc:
                    io_error = exc
                if io_error is not None:
                    try:
                        actual(*args, **kwargs)
                    finally:
                        raise io_error
                try:
                    result = actual(*args, **kwargs)
                except BaseException as exc:
                    recorder.end(exc)
                    raise
                recorder.end()
                return result
            with recorder.phase(phase):
                return actual(*args, **kwargs)
        setattr(target, name, call)
    actual_append = owner._Build.append_one
    def append(build, *args, **kwargs):
        nonlocal append_active
        if not append_active:
            recorder.begin('append')
            append_active = True
            phase, occurrence, started = recorder.stack[-1]
            recorder.emit('checkpoint', phase, occurrence, started)
        start_cpu, start_wall = time.process_time_ns(), time.monotonic_ns()
        recorder.append_calls += 1
        try:
            result = actual_append(build, *args, **kwargs)
        except BaseException as exc:
            recorder.append_cpu += time.process_time_ns() - start_cpu
            recorder.append_wall += time.monotonic_ns() - start_wall
            recorder.end(exc)
            append_active = False
            raise
        recorder.append_cpu += time.process_time_ns() - start_cpu
        recorder.append_wall += time.monotonic_ns() - start_wall
        recorder.completed += 1
        recorder.new_contents, recorder.new_receipts = build.new_contents, build.new_receipts
        if recorder.completed % 64 == 0:
            phase, occurrence, started = recorder.stack[-1]
            recorder.emit('checkpoint', phase, occurrence, started)
        return result
    try:
        wrap(owner._Build, 'run', 'corpus_run')
        wrap(owner, 'copy_legacy', 'copy')
        wrap(owner._Build, 'open_copied_writer', 'writer_open')
        wrap(owner._Ledger, 'finish', 'ledger_finish')
        wrap(owner._Build, 'close_writer', 'writer_close')
        wrap(owner._Build, 'verify_complete', 'cold_verify')
        wrap(owner, '_hash_file', 'hash')
        original.append((owner._Build, 'append_one', actual_append))
        owner._Build.append_one = append
        result = owner.build_receipt_corpus(source, profile.iter_receipts(0, 1024),
            expected_source_sha256=source_sha256, workspace=work, owned_directory=work / 'corpus',
            main_cap_bytes=512*MIB, ledger_cap_bytes=MIB)
        require(result.submitted_observations == result.new_contents == result.new_receipts == 1024,
                'actual fixed append counts differ')
        progress.phase_summary = recorder.summary
        return result
    finally:
        for target, name, actual in reversed(original):
            setattr(target, name, actual)


def namespace_admission(source, profile):
    """Bounded scalar projection over every old receipt, never eager 490k IDs."""
    first, last = profile.first_native_id, profile.first_native_id + 490000 - 1
    require(type(first) is int and 0 < first <= last <= 2**63-1, 'complete future ID room')
    last_clock = profile.start_at + timedelta(days=6, microseconds=69999)
    cursor = source.cursor()
    try:
        cursor.execute('SELECT substr(event_key,1,128), substr(observed_at,1,128), '
                       'octet_length(event_key), octet_length(observed_at) FROM context_observations ORDER BY rowid')
        for event_key, observed_at, event_size, clock_size in cursor:
            require(type(event_key) is str and type(observed_at) is str, 'old receipt scalar types differ')
            for prefix in ('espn:tennis:ATP:match:', 'espn:tennis:WTA:match:'):
                if event_key.startswith(prefix):
                    value = event_key[len(prefix):]
                    require(event_size <= 128 and value.isascii() and value.isdigit(), 'old native ID cannot be boundedly classified')
                    require(not first <= int(value) <= last, 'complete future native namespace collision')
            require(clock_size <= 128, 'old clock cannot be boundedly classified')
            try:
                clock = datetime.fromisoformat(observed_at)
            except ValueError:
                raise RuntimeError('old receipt clock is not a canonical aware clock') from None
            require(clock.tzinfo is not None and clock.utcoffset() == timedelta(0), 'old receipt clock timezone differs')
            require(not profile.start_at <= clock <= last_clock, 'complete future receipt clock collision')
    finally:
        cursor.close()


def observe_files(code, seal, work, manifest):
    permitted = {str(code / x['path']) for x in manifest['code']} | {
        str(seal / 'dependencies' / x['path']) for x in manifest['dependencies']} | {
        str(seal / 'runtime-data/zoneinfo' / x['path']) for x in manifest['timezone_data']}
    permitted.add(str(seal / 'baseline/context-current.db'))
    system = tuple(Path(p) for p in manifest['runtime']['stdlib_search_path'] if Path(p).is_absolute())
    caches = {importlib.util.cache_from_source(p) for p in permitted if p.endswith('.py')}
    def audit(event, args):
        if event == 'import' and args:
            name = args[0]
            require(not any(name == p or name.startswith(p + '.') for p in
                    ('pytest', '_pytest', 'tzdata', 'dateutil.zoneinfo', 'tennis.predict', 'context_history')),
                    'unplanned diagnostic import')
        if event not in ('open', 'sqlite3.connect') or not args or not isinstance(args[0], (str, bytes)):
            return
        name = os.fsdecode(args[0])
        if event == 'open' and len(args) > 2 and type(args[2]) is int and args[2] & getattr(os, 'O_DIRECTORY', 0):
            return
        if name in caches:
            raise FileNotFoundError(2, 'bytecode denied; sealed source required', name)
        path = Path(name)
        require(path.suffix.lower() not in ('.pkl', '.pickle', '.csv', '.xlsx', '.xls', '.pyc'), 'unplanned cached/training data')
        absolute = Path(os.path.abspath(name))
        require(not absolute.is_relative_to(seal / 'dependencies/dateutil/zoneinfo') and
                not absolute.is_relative_to('/usr/share/zoneinfo'), 'unplanned timezone fallback')
        if path.is_absolute() and not path.is_relative_to(work):
            require(name in permitted or name in ('/proc/self/status', '/proc/self/maps') or
                    any(path == base or path.is_relative_to(base) for base in system), 'unplanned Python file access')
    sys.addaudithook(audit)


def close_source(recorder, source):
    """Progress refusal cannot strand the actual held source connection."""
    try:
        recorder.begin('source_close')
    except BaseException:
        source.close()
        raise
    try:
        source.close()
    except BaseException as exc:
        recorder.end(exc)
        raise
    recorder.end()


def run(mode):
    require(mode == 'receipt-v1', 'fixed receipt-v1 argv required')
    require_guard()  # Must precede every catalogue/dependency/product import.
    code = Path(__file__).absolute().parents[1]
    seal, work = code.parent, Path.cwd()
    require(work == seal / 'attempt', 'fixed child workspace differs')
    old_path = code / 'tests/native_context_chain_catalogue.py'
    old = held_namespace(old_path, expected='48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935')
    manifest_raw = old['data_bytes'](seal / 'catalogue.json', 8*MIB,
        old['file_record'](seal / 'catalogue.json', 8*MIB)['sha256'])
    manifest = old['decode'](manifest_raw)
    entries = {x['path']: x for x in manifest['code']}
    c = held_namespace(code / 'tests/native_context_receipt_diagnostic_catalogue.py',
        expected=entries['tests/native_context_receipt_diagnostic_catalogue.py']['sha256'], supplied={'_OLD_CATALOGUE': old})
    require(c['canonical'](manifest) == manifest_raw, 'canonical child manifest required')
    c['validate_profile'](manifest['profile'])
    progress = c['Progress'](work / 'progress.jsonl')
    recorder = PhaseRecorder(progress)
    source = None
    try:
        with recorder.phase('worker_setup'):
            observe_files(code, seal, work, manifest)
            # Reuse only the old exact reader binding, not its small worker/run.
            old_worker = held_namespace(code / 'tests/native_context_chain_worker.py',
                expected=c['PINS']['tests/native_context_chain_worker.py'])
            old_worker['bind_timezone_data'](old, seal, manifest)
            sys.path[:0] = [str(code), str(code / 'tests')]
            from context_growth_profile import build_growth_profile
            from context_runtime_transaction import TrackedConnection
            from context_storage_v2.copying import _configure_copy_reader, _no_companions
            import sqlite3
        with recorder.phase('profile'):
            p = manifest['profile']
            profile = build_growth_profile(p['kind'], baseline_sha256=p['baseline_sha256'],
                start_at=datetime.fromisoformat(p['start_at']), first_native_id=p['first_native_id'],
                atp_fixture=p['atp_fixture'], wta_fixture=None)
        source_path = seal / 'baseline/context-current.db'
        with old['opened'](source_path) as (fd, before):
            with recorder.phase('source_open'):
                require(before.st_uid == before.st_gid == 0 and before.st_mode & 0o777 == 0o444,
                        'genuine read-only root baseline seal required')
                _no_companions(source_path)
                header = os.read(fd, 100)
                require(len(header) == 100 and header[:16] == b'SQLite format 3\0' and header[18:20] == b'\1\1',
                        'standalone rollback header required before SQLite schema access')
                require(old['file_record'](source_path, 270233600) == dict(size=270233600, sha256=c['BASELINE_SHA']),
                        'source baseline bytes differ')
                source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True, factory=TrackedConnection,
                    timeout=0, isolation_level=None, autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL, cached_statements=0)
                _configure_copy_reader(source, page_size=4096, page_count=65975)
                source.execute('BEGIN').close()
                for key, expected in (('page_size', 4096), ('page_count', 65975), ('encoding', 'UTF-8'),
                    ('journal_mode', 'delete'), ('auto_vacuum', 0), ('schema_version', 1), ('user_version', 0), ('application_id', 0)):
                    cursor = source.execute('PRAGMA ' + key)
                    try:
                        require(cursor.fetchone() == (expected,) and cursor.fetchone() is None, 'baseline page profile differs')
                    finally:
                        cursor.close()
                cursor = source.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")
                try:
                    require(cursor.fetchmany(8) == [(name,) for name in sorted(c['TABLE_COUNTS'])], 'actual six source tables differ')
                finally:
                    cursor.close()
                for name, expected in c['TABLE_COUNTS'].items():
                    cursor = source.execute('SELECT count(*) FROM "' + name + '"')
                    try:
                        require(cursor.fetchone() == (expected,), 'actual old source counts differ')
                    finally:
                        cursor.close()
                for kind, count in (('tennis-live-winner-original-v1', 31), ('tennis-tour-state', 2)):
                    cursor = source.execute('SELECT count(*) FROM artifacts WHERE kind=?', (kind,))
                    try:
                        require(cursor.fetchone() == (count,), 'actual old Original/tour-state kinds differ')
                    finally:
                        cursor.close()
                namespace_admission(source, profile)
            result = measure_corpus(source, profile, c['BASELINE_SHA'], work, progress, recorder=recorder)
            counts = {table.name: table.row_count for table in result.source_inventory.tables}
            require(counts == c['TABLE_COUNTS'], 'full actual source table inventory differs')
            target = dict(counts, context_contents=101577, context_observations=101577)
            require({table.name: table.row_count for table in result.inventory.tables} == target, 'full actual output counts differ')
            close_source(recorder, source)
            source = None
        with recorder.phase('worker_finish'):
            require_guard()
        parsed = c['parse_progress'](progress.raw)
        corpus = dataclasses.asdict(result)
        corpus['path'], corpus['ledger_path'] = str(result.path), str(result.ledger_path)
        payload = dict(format=FORMAT, plan_digest=manifest['admission']['plan_digest'],
            baseline_sha256=c['BASELINE_SHA'], generator_sha256=c['PINS']['tests/context_growth_profile.py'],
            driver_sha256=entries['tests/native_context_receipt_diagnostic_worker.py']['sha256'], completed=1024,
            corpus=corpus, phases=recorder.summary, progress=dict(head=parsed['head'], count=len(parsed['frames'])),
            cleanup=dict(source_closed=True, worker_finished=True))
        encoded = c['canonical'](payload) + b'\n'
        require(len(encoded) <= 128*1024, 'worker stdout cap exceeded')
        progress.close()
        c['write_all'](1, encoded)
        return payload
    finally:
        try:
            if source is not None:
                close_source(recorder, source)
        finally:
            progress.close()


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 2, 'one fixed worker argument required')
        run(sys.argv[1])
    except BaseException as exc:
        os.write(2, json.dumps({'format': FORMAT, 'exception': type(exc).__name__[:64], 'phase': 'failed'},
                             sort_keys=True, separators=(',', ':')).encode('ascii') + b'\n')
        raise
