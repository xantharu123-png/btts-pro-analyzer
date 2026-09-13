"""Fixed receipt diagnostic controls. Stdlib only; never Source or admission.

Native held bootstrap injects the old catalogue namespace. Read-only inventory
and portable QA may load its exact pinned bytes once, never hash then reopen.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile
import types
import dataclasses

FORMAT = 'betboy-native-receipt-diagnostic-catalogue-v1'
PROGRESS_FORMAT = 'betboy-receipt-diagnostic-progress-v1'
PREFIX = 'betboy-receipt-diagnostic-child-cpu-handoff-v1'
MIB, GIB = 1024**2, 1024**3
MANIFEST_CAP, ARCHIVE_CAP, MEMBER_CAP = 8*MIB, 64*MIB, 128*MIB
PROGRESS_CAP = 262144
OLD_NAME = 'tests/native_context_chain_catalogue.py'
PARENT_NAME = 'tests/native_context_receipt_diagnostic.py'
CATALOGUE_NAME = 'tests/native_context_receipt_diagnostic_catalogue.py'
WORKER_NAME = 'tests/native_context_receipt_diagnostic_worker.py'
ADMISSION_NAME = 'tests/native_context_diagnostic_admission.py'
OLD_SHA = '48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935'
PINS = {
    OLD_NAME: OLD_SHA,
    ADMISSION_NAME: 'f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad',
    'tests/context_growth_profile.py': '584bd2c9c14aee3abe5b5dc2f537ebc25914cd7d63b7dabf6d0abb306798e2c9',
    'context_storage_v2/receipt_corpus.py': 'fdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6',
    'context_storage_v2/copying.py': '15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23',
    'context_storage_v2/inventory.py': '7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b',
    'context_storage_v2/receipt_append.py': 'e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9',
    'context_storage_v2/sqlite_profile.py': '05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc',
    'tests/native_context_chain.py': '73befce90e1087c27350258387c1454527838b7242b767227bafd69cb4f3fff7',
    'tests/native_context_chain_worker.py': '210226b3fd40a9c9bbe8090c9c52a0a56840827e8e75bcd610e4544826d5b209',
}
HELPERS = {
    'context_preparation_process_guard.py': '62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4',
    'context_preparation_budget.py': 'fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478',
    'context_preparation_supervisor.py': 'c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8',
}
BOOTSTRAP = (PARENT_NAME, CATALOGUE_NAME, OLD_NAME, ADMISSION_NAME, *HELPERS)
BASELINE_PATH = '/var/lib/betboy-live-backup-ssfvf5xs/context-current.db'
BASELINE_SHA = '73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa'
TABLE_COUNTS = dict(active_manifest=1, artifacts=33, context_contents=100553,
                    context_observations=100553, context_snapshots=31, manifests=2)


class DiagnosticError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise DiagnosticError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MANIFEST_CAP, 'bounded JSON required')
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise DiagnosticError('noninteger JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=invalid, parse_constant=invalid)


def integer(value, cap=2**63-1):
    require(type(value) is int and 0 <= value <= cap, 'bounded exact integer required')
    return value


def sha(value):
    require(type(value) is str and len(value) == 64 and all(x in '0123456789abcdef' for x in value), 'invalid SHA256')
    return value


def shape(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), 'closed object shape differs')


def old():
    namespace = globals().get('_OLD_CATALOGUE')
    if namespace is None:
        path = Path(__file__).with_name('native_context_chain_catalogue.py')
        with path.open('rb') as stream:
            raw = stream.read(MIB + 1)
        require(len(raw) <= MIB and digest(raw) == OLD_SHA, 'old held catalogue pin differs')
        namespace = {'__name__': '_receipt_old_catalogue', '__file__': str(path)}
        exec(compile(raw, str(path), 'exec'), namespace)
        globals()['_OLD_CATALOGUE'] = namespace
    return namespace


def absolute(value):
    require(type(value) is str and 0 < len(value) <= 1024 and '\\' not in value and '\0' not in value,
            'absolute POSIX path required')
    path = PurePosixPath(value)
    require(path.is_absolute() and path.as_posix() == value and '..' not in path.parts and value != '/',
            'canonical nonroot absolute path required')
    return value


def fixed_profile():
    return dict(kind='atp-heavy', baseline_sha256=BASELINE_SHA, start_at='2026-09-12T00:00:00+00:00',
        first_native_id=8000000000000000000, start=0, stop=1024, wta_fixture=None,
        atp_fixture={
            'competition': {'id': '8000000000000000000', 'date': '2026-09-12T18:00:00Z', 'surface': 'Hard',
                'status': {'type': {'state': 'pre', 'name': 'STATUS_SCHEDULED', 'completed': False}},
                'competitors': [
                    {'id': '1000000001', 'athlete': {'displayName': 'aaron t'}},
                    {'id': '1000000002', 'athlete': {'displayName': 'aarts p'}}]},
            'tournament_id': '189-2026', 'surface': 'Hard', 'best_of': 3, 'indoor': None})


def validate_profile(value):
    require(type(value) is dict and canonical(value) == canonical(fixed_profile()), 'fixed synthetic profile differs')
    require(len(canonical(value['atp_fixture'])) <= 65536, 'seed exceeds closed control cap')
    integer(value['start'], 0)
    integer(value['stop'], 1024)
    integer(value['first_native_id'], 2**63 - 490000)
    return value


def baseline():
    return dict(path=BASELINE_PATH, size=270233600, sha256=BASELINE_SHA,
                page_size=4096, page_count=65975, encoding='UTF-8', journal_mode='delete',
                present_tables=sorted(TABLE_COUNTS), expected_counts=dict(TABLE_COUNTS))


def _allocation(info):
    if sys.platform == 'linux':
        return integer(info.st_blocks * 512, 64*GIB)
    return old()['allocated_slot'](info.st_size)


def _directory_record(path, name):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not path.is_symlink(), 'non-directory/linked namespace')
    return dict(path=name, identity=list(old()['identity'](info)), size=info.st_size, allocated=_allocation(info))


def child_names(path, maximum):
    names = []
    with os.scandir(path) as entries:
        for entry in entries:
            require(len(names) < maximum, 'directory entry bound exceeded')
            names.append(entry.name)
    return sorted(names)


def sample_exact_slots(root, slots, metadata_cap, *, previous=None):
    """No unknown-file allowance; large caps belong to exact declared slots."""
    root = Path(root).absolute()
    integer(metadata_cap, 128*MIB)
    require(type(slots) is dict and len(slots) <= 30000, 'slot count')
    for name, cap in slots.items():
        old()['relative'](name)
        integer(cap, 8*GIB)
    permitted_dirs = {'.'} | {str(p) for name in slots for p in PurePosixPath(name).parents}
    files, directories = [], []
    def visit(path, name):
        require(name in permitted_dirs, 'unplanned directory')
        before = _directory_record(path, name)
        directories.append(before)
        names = child_names(path, 30000)
        require(len(names) + len(files) + len(directories) <= 30000, 'namespace count exceeded')
        for child in names:
            item = path / child
            rel = child if name == '.' else name + '/' + child
            info = item.lstat()
            require(not item.is_symlink(), 'linked namespace member')
            if stat.S_ISDIR(info.st_mode):
                visit(item, rel)
            else:
                require(rel in slots, 'unplanned file')
                record = old()['file_record'](item, maximum=slots[rel])
                require(old()['identity'](info) == old()['identity'](item.lstat()), 'sample file epoch changed')
                allocated = _allocation(info)
                require(max(record['size'], allocated) <= old()['allocated_slot'](slots[rel]), 'file allocation exceeds slot')
                files.append(dict(path=rel, identity=list(old()['identity'](info)), allocated=allocated, **record))
        require(before == _directory_record(path, name), 'sample directory changed')
    visit(root, '.')
    metadata_logical = sum(x['size'] for x in directories)
    metadata_allocated = sum(x['allocated'] for x in directories)
    require(max(metadata_logical, metadata_allocated) <= metadata_cap, 'metadata reservation exceeded')
    result = dict(files=sorted(files, key=lambda x: x['path']), directories=sorted(directories, key=lambda x: x['path']),
        logical=sum(x['size'] for x in files) + metadata_logical,
        allocated=sum(x['allocated'] for x in files) + metadata_allocated,
        metadata_logical=metadata_logical, metadata_allocated=metadata_allocated)
    require(previous is None or result == previous, 'quiescent inventory changed')
    return result


def retained_root(path):
    """Stream complete bounded membership; return only digest/counts/totals."""
    path = Path(path)
    checksum = hashlib.sha256()
    counts = dict(files=0, directories=0, symlinks=0, logical=0, allocated=0)
    def emit(record):
        counts[{'directory': 'directories', 'regular': 'files', 'symlink': 'symlinks'}[record['kind']]] += 1
        counts['logical'] += record['size']
        counts['allocated'] += record['allocated']
        require(counts['files'] + counts['directories'] + counts['symlinks'] <= 200000 and
                max(counts['logical'], counts['allocated']) <= 64*GIB, 'retained namespace bound exceeded')
        checksum.update(canonical(record) + b'\n')
    def visit(current, rel):
        require(len(PurePosixPath(rel).parts) <= 32 and len(os.fsencode(current)) <= 2048, 'retained path/depth bound')
        record = _directory_record(current, rel)
        record.update(kind='directory', sha256=None)
        emit(record)
        names = child_names(current, 50000)
        require(len(names) <= 50000, 'retained directory count exceeded')
        for name in names:
            item = current / name
            key = name if rel == '.' else rel + '/' + name
            info = item.lstat()
            require(len(os.fsencode(item)) <= 2048, 'retained path bound')
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(os.fsencode(item))
                require(type(target) is bytes and len(target) <= 4096, 'retained inert link target bound')
                data = dict(size=info.st_size, sha256=digest(target))
                kind = 'symlink'
            elif stat.S_ISDIR(info.st_mode):
                visit(item, key)
                continue
            else:
                require(stat.S_ISREG(info.st_mode), 'retained special file rejected')
                with old()['opened'](item) as (fd, before):
                    require(old()['identity'](info) == old()['identity'](before) and 0 <= before.st_size <= 8*GIB,
                            'retained regular bound/epoch')
                    hasher, length = hashlib.sha256(), 0
                    while block := os.read(fd, MIB):
                        length += len(block)
                        require(length <= before.st_size, 'retained regular grew')
                        hasher.update(block)
                    require(length == before.st_size, 'retained regular shrank')
                    data = dict(size=length, sha256=hasher.hexdigest())
                kind = 'regular'
            require(old()['identity'](info) == old()['identity'](item.lstat()), 'retained epoch drift')
            emit(dict(path=key, kind=kind, identity=list(old()['identity'](info)), allocated=_allocation(info), **data))
        after = _directory_record(current, rel)
        after.update(kind='directory', sha256=None)
        require(record == after, 'retained namespace changed')
    first = _directory_record(path, '.')
    with old()['opened'](path, directory=True):
        visit(path, '.')
    return dict(path=str(path), identity=first['identity'], membership_sha256=checksum.hexdigest(), **counts)


def validate_retained(raw, *, observe=False):
    value = decode(raw)
    require(canonical(value) == raw, 'retained control must be canonical exact bytes')
    shape(value, 'format roots backup_rollback_reserve')
    require(value['format'] == 'betboy-receipt-diagnostic-retained-v1', 'retained format')
    integer(value['backup_rollback_reserve'], 64*GIB)
    require(type(value['roots']) is list and 0 < len(value['roots']) <= 256, 'complete retained roots required')
    seen = []
    for item in value['roots']:
        shape(item, 'path identity membership_sha256 files directories symlinks logical allocated category charged_cpu_ns journals')
        name = absolute(item['path'])
        require(not any(PurePosixPath(name).is_relative_to(p) or PurePosixPath(p).is_relative_to(name) for p in seen),
                'overlapping retained roots')
        seen.append(name)
        sha(item['membership_sha256'])
        require(type(item['identity']) is list and len(item['identity']) == 7, 'retained identity shape')
        for n in item['identity']:
            integer(n, 2**128-1)
        for key in ('files', 'directories', 'symlinks'):
            integer(item[key], 200000)
        require(sum(item[k] for k in ('files', 'directories', 'symlinks')) <= 200000, 'retained root entry bound')
        for key in ('logical', 'allocated'):
            integer(item[key], 64*GIB)
        require(item['category'] in ('historical-qa', 'backup', 'rollback', 'reused-input'), 'retained category')
        if item['charged_cpu_ns'] is not None:
            integer(item['charged_cpu_ns'])
        validate_journals(Path(name), item['journals'], observe=observe)
        if observe:
            observed = retained_root(name)
            require(all(item[k] == v for k, v in observed.items()), 'retained complete inventory changed')
    require(seen == sorted(seen), 'retained roots not sorted')
    require(sum(x[k] for x in value['roots'] for k in ('files', 'directories', 'symlinks')) <= 500000,
            'retained aggregate entry bound')
    require(max(sum(x[k] for x in value['roots']) for k in ('logical', 'allocated')) <= 64*GIB,
            'retained aggregate byte bound')
    return value


def budget_reader():
    name = 'context_preparation_budget'
    if name in sys.modules:
        return sys.modules[name]
    # Read-only preparation also uses held reviewed bytes; never runpy/reopen.
    path = Path(__file__).absolute().parents[1] / (name + '.py')
    with path.open('rb') as stream:
        raw = stream.read(MIB + 1)
    require(len(raw) <= MIB and digest(raw) == HELPERS[name + '.py'], 'held budget reader pin differs')
    module = types.ModuleType(name)
    module.__file__ = '<reviewed-context_preparation_budget.py>'
    sys.modules[name] = module
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def validate_journals(root, declarations, *, observe=False):
    require(type(declarations) is list and len(declarations) <= 256, 'bounded declared journal list required')
    names = []
    for item in declarations:
        shape(item, 'path identity journal_head ticket state charged_cpu_ns settled_cpu_ns category')
        old()['relative'](item['path'])
        names.append(item['path'])
        sha(item['journal_head'])
        shape(item['identity'], 'input_digest execution_digest runtime_digest installation_digest profile_digest')
        for value in item['identity'].values():
            sha(value)
        require(item['state'] in ('stopped', 'pending', 'accounting-open') and
                item['category'] in ('historical-measurement', 'synthetic-protocol', 'unknown'), 'journal state/category differs')
        integer(item['charged_cpu_ns']); integer(item['settled_cpu_ns'])
        if item['ticket'] is not None:
            shape(item['ticket'], 'identity_digest reservation_digest sequence portion_digest cpu_ns deadline_boot_ns')
            for key in ('identity_digest', 'reservation_digest', 'portion_digest'):
                sha(item['ticket'][key])
            for key in ('sequence', 'cpu_ns', 'deadline_boot_ns'):
                integer(item['ticket'][key])
        if observe:
            path = Path(root) / item['path']
            record = old()['file_record'](path, maximum=MIB)
            raw = old()['data_bytes'](path, MIB, record['sha256'])
            budget = budget_reader()
            actual = budget._replay(raw, budget.BudgetIdentity(**item['identity'])).snapshot()
            require(item['journal_head'] == actual.journal_digest and item['state'] == actual.status and
                    item['charged_cpu_ns'] == actual.charged_cpu_ns and item['settled_cpu_ns'] == actual.settled_cpu_ns and
                    item['ticket'] == (None if actual.pending is None else dataclasses.asdict(actual.pending)),
                    'declared actual budget journal replay differs')
    require(names == sorted(set(names)), 'journals must be sorted and unique')
    return declarations


PHASES = ('worker_setup', 'profile', 'source_open', 'corpus_run', 'copy', 'writer_open',
          'append', 'ledger_finish', 'writer_close', 'cold_verify', 'hash', 'source_close', 'worker_finish')
BODY_KEYS = 'event phase occurrence depth completed cpu_ns wall_ns phase_cpu_ns phase_wall_ns submitted new_contents new_receipts exception'
ROOT_PHASES = ('worker_setup', 'profile', 'source_open', 'corpus_run', 'source_close', 'worker_finish')


class _ProgressState:
    def __init__(self):
        self.stack, self.occurrences = [], {}
        self.completed, self.root_index = 0, -1
        self.cpu_ns = self.wall_ns = 0
        self.terminal = self.failed = False
        self.checkpoint = -64
        self.last_phase = None
        self.corpus_stage = 'copy'

    def consume(self, b):
        shape(b, BODY_KEYS)
        require(b['event'] in ('begin', 'end', 'fail', 'checkpoint') and b['phase'] in PHASES,
                'illegal progress event/phase')
        for key in ('occurrence', 'depth', 'completed', 'cpu_ns', 'wall_ns', 'phase_cpu_ns',
                    'phase_wall_ns', 'submitted', 'new_contents', 'new_receipts'):
            integer(b[key])
        require(not self.terminal and 1 <= b['occurrence'] <= 16 and 1 <= b['depth'] <= 8,
                'terminal/occurrence/depth violation')
        require(self.completed <= b['completed'] <= 1024 and
                b['submitted'] == b['completed'] and 0 <= b['new_contents'] <= b['completed'] and
                0 <= b['new_receipts'] <= b['completed'], 'invalid completed counters')
        require(b['cpu_ns'] >= self.cpu_ns and b['wall_ns'] >= self.wall_ns and
                b['phase_cpu_ns'] <= b['cpu_ns'] and b['phase_wall_ns'] <= b['wall_ns'], 'nonmonotonic progress times')
        exception = b['exception']
        require(exception is None or (type(exception) is str and 0 < len(exception) <= 64 and
                exception.isascii() and exception.isidentifier()), 'exception class only')
        require((b['event'] == 'fail') == (exception is not None), 'failure exception differs')
        phase, occurrence, event = b['phase'], b['occurrence'], b['event']
        if event == 'begin':
            require(occurrence == self.occurrences.get(phase, 0) + 1 and b['depth'] == len(self.stack) + 1,
                    'phase occurrence/stack differs')
            if not self.stack:
                require(phase in ROOT_PHASES, 'nonroot phase without parent')
                index = ROOT_PHASES.index(phase)
                constructor_failed = phase == 'source_close' and self.root_index == 2
                require(index == self.root_index + 1 or (self.failed and phase == 'source_close') or constructor_failed,
                        'root phase order')
                self.failed |= constructor_failed
                self.root_index = index
            else:
                parent = self.stack[-1][0]
                require((parent == 'corpus_run' and phase in ('copy', 'writer_open', 'append', 'ledger_finish',
                        'writer_close', 'cold_verify', 'hash')) or (parent in ('copy', 'writer_open') and phase == 'hash'),
                        'impossible nested phase')
                if parent == 'corpus_run':
                    if self.failed:
                        require(phase == 'writer_close', 'only actual cleanup after failure')
                    elif phase == 'hash':
                        require(self.corpus_stage in ('output_hash', 'source_hash'), 'hash before cold verify')
                    elif phase == 'writer_close':
                        require(self.corpus_stage in ('writer_close', 'cleanup_writer'), 'writer cleanup out of order')
                    else:
                        require(phase == self.corpus_stage, 'corpus phase order differs')
                    if phase not in ('writer_close', 'hash'):
                        require(occurrence == 1, 'repeated noncleanup corpus phase')
            require(b['completed'] == self.completed, 'begin cannot complete append calls')
            self.occurrences[phase] = occurrence
            self.stack.append([phase, occurrence])
        else:
            require(self.stack and self.stack[-1] == [phase, occurrence] and b['depth'] == len(self.stack),
                    'phase close/checkpoint stack differs')
            if event == 'checkpoint':
                require(phase == 'append' and b['completed'] == self.checkpoint + 64,
                        'only fixed append checkpoints')
                self.checkpoint = b['completed']
            else:
                if phase == 'append' and event == 'end':
                    require(b['completed'] == 1024 and self.checkpoint == 1024, 'incomplete append end')
                self.stack.pop()
                if event == 'fail':
                    self.failed = True
                elif phase == 'corpus_run':
                    require(self.corpus_stage == 'complete' and not self.failed, 'incomplete successful corpus')
                elif self.stack and self.stack[-1][0] == 'corpus_run' and not self.failed:
                    transitions = {'copy': 'writer_open', 'writer_open': 'append', 'append': 'ledger_finish',
                        'ledger_finish': 'writer_close', 'writer_close': 'cold_verify', 'cold_verify': 'output_hash',
                        'output_hash': 'source_hash', 'source_hash': 'cleanup_writer', 'cleanup_writer': 'complete'}
                    require(self.corpus_stage in transitions, 'illegal corpus phase return')
                    self.corpus_stage = transitions[self.corpus_stage]
                if phase == 'worker_finish' and event == 'end':
                    require(not self.failed and b['completed'] == 1024, 'false terminal progress')
                    self.terminal = True
        if b['completed'] != self.completed:
            require(phase == 'append' and event in ('checkpoint', 'fail'), 'unrecorded append completion')
        self.completed = b['completed']
        self.cpu_ns, self.wall_ns, self.last_phase = b['cpu_ns'], b['wall_ns'], phase


def parse_progress(raw):
    require(type(raw) is bytes and len(raw) <= PROGRESS_CAP, 'progress file bound')
    split = raw.rfind(b'\n') + 1
    complete, tail = raw[:split], raw[split:]
    require(len(tail) < 2048, 'incomplete frame bound')
    state, frames, head = _ProgressState(), [], '0'*64
    for line in complete.splitlines(keepends=True):
        require(len(frames) < 128 and len(line) <= 2048 and line.endswith(b'\n'), 'frame count/length bound')
        frame = decode(line[:-1])
        shape(frame, 'format sequence previous body sha256')
        require(canonical(frame) + b'\n' == line and frame['format'] == PROGRESS_FORMAT and
                type(frame['sequence']) is int and frame['sequence'] == len(frames) and frame['previous'] == head,
                'noncanonical/discontinuous progress')
        check = {k: v for k, v in frame.items() if k != 'sha256'}
        require(sha(frame['sha256']) == digest(canonical(check)), 'progress hash differs')
        state.consume(frame['body'])
        frames.append(frame)
        head = frame['sha256']
    return dict(frames=frames, head=head, complete_bytes=len(complete), incomplete_tail_bytes=len(tail),
                completed=state.completed, last_phase=state.last_phase, stack=state.stack, terminal=state.terminal)


def write_all(fd, raw):
    view = memoryview(raw)
    while view:
        count = os.write(fd, view)
        require(type(count) is int and 0 < count <= len(view), 'write stalled')
        view = view[count:]


class Progress:
    def __init__(self, path):
        self.path, self.raw, self.failed = Path(path), b'', False
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                          getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0), 0o600)
        self.identity = old()['identity'](os.fstat(self.fd))[:4]
        try:
            os.fsync(self.fd)
            if sys.platform == 'linux':
                directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def append(self, body):
        require(self.fd is not None and not self.failed, 'progress writer closed/poisoned')
        prefix = parse_progress(self.raw)
        frame = dict(format=PROGRESS_FORMAT, sequence=len(prefix['frames']), previous=prefix['head'], body=body)
        frame['sha256'] = digest(canonical(frame))
        encoded = canonical(frame) + b'\n'
        require(len(encoded) <= 2048, 'progress frame bound')
        parse_progress(self.raw + encoded)
        try:
            require(self.identity == old()['identity'](os.fstat(self.fd))[:4] ==
                    old()['identity'](self.path.lstat())[:4] and os.fstat(self.fd).st_size == len(self.raw),
                    'progress held identity/size changed')
            write_all(self.fd, encoded)
            os.fsync(self.fd)
            self.raw += encoded
        except BaseException:
            self.failed = True
            raise
        return frame

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)


def bootstrap_source(sources):
    require(type(sources) is dict and set(sources) == set(BOOTSTRAP), 'fixed held bootstrap only')
    for name, raw in sources.items():
        require(type(raw) is bytes and 0 < len(raw) <= MIB, 'bootstrap source bound')
        expected = (PINS | HELPERS).get(name)
        require(expected is None or digest(raw) == expected, 'held helper pin differs')
    literal = repr({name: sources[name] for name in BOOTSTRAP}).encode('ascii')
    result = (b'# Reviewed Task61 stdlib-only held stdin bootstrap\n_REVIEWED_BOOTSTRAP = ' + literal +
              b'\nexec(compile(_REVIEWED_BOOTSTRAP["tests/native_context_receipt_diagnostic.py"], '
              b'"<reviewed-task61-parent>", "exec"), globals())\n')
    require(len(result) <= 2*MIB, 'bootstrap allowance exceeded')
    return result


def runtime_observation():
    require(sys.platform == 'linux' and os.uname().machine == 'x86_64', 'Linux/x86_64 observation required')
    executable = Path('/proc/self/exe').resolve()
    return dict(executable=str(executable), executable_sha256=old()['file_record'](executable)['sha256'],
                python=sys.version, kernel=list(os.uname()), stdlib_search_path=list(sys.path),
                closure_status='observed-system-runtime-not-transitive-B-closure')


def installation_observation(runtime):
    path = Path('/etc/machine-id')
    protected(path)
    record = old()['file_record'](path, maximum=4096)
    require(record['size'] > 0, 'empty machine identity')
    return dict(machine_id_sha256=record['sha256'], executable=runtime['executable'],
                executable_sha256=runtime['executable_sha256'])


def protected(path, directory=False, *, searchable=False):
    path = Path(path)
    chain = (path, *path.parents)
    for index, item in enumerate(chain):
        info = item.lstat()
        require(info.st_uid == info.st_gid == 0 and not info.st_mode & 0o022 and not item.is_symlink(),
                'root-owned nonwritable protected ancestor required')
        require(stat.S_ISDIR(info.st_mode) if index or directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                'protected input type differs')
        if searchable and (index or directory):
            require(info.st_mode & 0o001, 'child-unsearchable protected ancestor')
    return path.lstat()


def budget_identity(value, runtime, installation):
    return dict(input_digest=value['baseline']['sha256'],
        execution_digest=digest(canonical(dict(code=value['code'], dependencies=value['dependencies'],
            prefix=dict(version=PREFIX, parent_sha256=next(x['sha256'] for x in value['code'] if x['path'] == PARENT_NAME))))),
        runtime_digest=digest(canonical(dict(runtime=runtime, timezone_data=value['timezone_data']))),
        installation_digest=digest(canonical(installation)), profile_digest=digest(canonical(value['profile'])))


def allocation_plan(value, *, archive_path, manifest_path, retained_path, registry_names=()):
    slots = {'archive.tar': value['archive']['size'], 'catalogue.json': MANIFEST_CAP,
        'plan.json': MANIFEST_CAP, 'report.json': MIB, 'failure.json': MIB, 'custody.json': MIB,
        'native-result.json': MIB, 'stdout.bin': 128*1024, 'stderr.bin': 8192,
        'baseline/context-current.db': value['baseline']['size'],
        'attempt/progress.jsonl': PROGRESS_CAP,
        'attempt/corpus/legacy-copy.sqlite': 512*MIB,
        'attempt/corpus/legacy-copy.sqlite-journal': 512*MIB,
        'attempt/corpus/receipt-additions.bin': MIB}
    for prefix, entries in (('code', value['code']), ('dependencies', value['dependencies']),
                            ('runtime-data/zoneinfo', value['timezone_data'])):
        slots.update({prefix + '/' + item['path']: item['size'] for item in entries})
    inputs = [dict(path=absolute(str(archive_path)), cap=value['archive']['size']),
              dict(path=absolute(str(manifest_path)), cap=MANIFEST_CAP),
              dict(path=absolute(str(retained_path)), cap=MANIFEST_CAP),
              dict(path=value['baseline']['path'], cap=value['baseline']['size'])]
    inputs += [dict(path=value['dependency_root'] + '/' + x['path'], cap=x['size']) for x in value['dependencies']]
    inputs += [dict(path=x['source'], cap=x['size']) for x in value['timezone_data']]
    require(len({x['path'] for x in inputs}) == len(inputs), 'aliased original inputs')
    registry_slots = {name: MIB for name in registry_names}
    registry_slots.update({'diagnostic-admissions.jsonl': MIB, digest(canonical(value['admission']['identity'])) + '.jsonl': MIB})
    total = sum(old()['allocated_slot'](n) for n in (*slots.values(), *registry_slots.values())) + 129*MIB
    return dict(slots=dict(sorted(slots.items())), metadata_cap=128*MIB,
        registry_slots=dict(sorted(registry_slots.items())), registry_metadata_cap=MIB,
        inputs=sorted(inputs, key=lambda x: x['path']), input_metadata_cap=128*MIB,
        new_job_cap=8*GIB, active_input_cap=4*GIB, free_reserve=4*GIB,
        backup_rollback_reserve=value['_retained_data']['backup_rollback_reserve'], total=total)


def validate_manifest(value, commit, *, retained_raw, runtime, installation):
    shape(value, 'format commit archive code dependencies dependency_root packages timezone_data runtime baseline profile retained allocation admission')
    require(value['format'] == FORMAT and value['commit'] == commit and type(commit) is str and
            len(commit) == 40 and all(x in '0123456789abcdef' for x in commit), 'reviewed commit/format differs')
    code = old()['records'](value['code'], ARCHIVE_CAP)
    require(set(PINS | HELPERS) | {PARENT_NAME, CATALOGUE_NAME, WORKER_NAME} <= set(code), 'required execution member missing')
    require(all(n.endswith('.py') and not n.startswith('.') for n in code), 'Python source-only archive')
    for name, expected in (PINS | HELPERS).items():
        require(code[name]['sha256'] == expected, 'unchanged owner pin differs')
    deps = old()['records'](value['dependencies'], GIB)
    require(value['dependency_root'] == old()['DEPENDENCY_SOURCE'].as_posix() and value['packages'] == list(old()['PACKAGES']),
            'fixed native dependency source differs')
    require({name.split('/')[0] for name in deps} == set(value['packages']), 'dependency roots incomplete')
    old()['timezone_entries'](value['timezone_data'])
    shape(value['archive'], 'size sha256')
    integer(value['archive']['size'], ARCHIVE_CAP)
    sha(value['archive']['sha256'])
    require(canonical(value['baseline']) == canonical(baseline()), 'exact baseline metadata differs')
    validate_profile(value['profile'])
    require(value['runtime'] == runtime, 'actual runtime differs')
    shape(runtime, 'executable executable_sha256 python kernel stdlib_search_path closure_status')
    require(runtime['closure_status'] == 'observed-system-runtime-not-transitive-B-closure', 'false runtime closure')
    shape(installation, 'machine_id_sha256 executable executable_sha256')
    sha(installation['machine_id_sha256'])
    require(installation['executable'] == runtime['executable'] and
            installation['executable_sha256'] == runtime['executable_sha256'], 'installation executable differs')
    retained = validate_retained(retained_raw)
    shape(value['retained'], 'path size sha256')
    absolute(value['retained']['path'])
    require(value['retained']['size'] == len(retained_raw) and value['retained']['sha256'] == digest(retained_raw),
            'complete retained control differs')
    admission = value['admission']
    shape(admission, 'registry_directory job_directory purpose profile_kind identity plan_digest retained_history_digest')
    registry, job = absolute(admission['registry_directory']), absolute(admission['job_directory'])
    require(not PurePosixPath(registry).is_relative_to(job) and not PurePosixPath(job).is_relative_to(registry), 'registry/job overlap')
    require(admission['purpose'] == 'context-receipt-corpus-diagnostic-v1' and admission['profile_kind'] == 'atp-heavy', 'purpose/profile differs')
    require(admission['identity'] == budget_identity(value, runtime, installation), 'recomputed complete identity differs')
    require(admission['retained_history_digest'] == digest(retained_raw) and
            admission['plan_digest'] == digest(canonical({k: v for k, v in value.items() if k != 'admission'})),
            'acyclic full plan/history differs')
    a = value['allocation']
    shape(a, 'slots metadata_cap registry_slots registry_metadata_cap inputs input_metadata_cap new_job_cap active_input_cap free_reserve backup_rollback_reserve total')
    require(type(a['inputs']) is list and len(a['inputs']) >= 4, 'explicit original input plan required')
    for item in a['inputs']:
        shape(item, 'path cap')
        absolute(item['path']); integer(item['cap'], GIB)
    source_names = {value['baseline']['path'], value['retained']['path']} | {
        value['dependency_root'] + '/' + x['path'] for x in value['dependencies']} | {x['source'] for x in value['timezone_data']}
    controls = [x for x in a['inputs'] if x['path'] not in source_names]
    require(len(controls) == 2, 'exact archive/manifest slots required')
    # Exact archive and manifest paths are further disambiguated by launcher CLI.
    candidates = []
    for first, second in (controls, controls[::-1]):
        temp = dict(value, _retained_data=retained)
        candidate = allocation_plan(temp, archive_path=first['path'], manifest_path=second['path'],
            retained_path=value['retained']['path'])
        if candidate == a:
            candidates.append(candidate)
    require(candidates, 'exact allocation plan differs')
    for root in retained['roots']:
        for path in (registry, job, value['retained']['path'], *(x['path'] for x in controls)):
            require(not PurePosixPath(path).is_relative_to(root['path']) and
                    not PurePosixPath(root['path']).is_relative_to(path), 'new control/namespace overlaps retained inventory')
    require(a['total'] <= 8*GIB, 'whole new job exceeds 8GiB')
    input_total = sum(old()['allocated_slot'](x['cap']) for x in a['inputs']) + a['input_metadata_cap']
    # Conservatively include every new slot as active, even output and slack.
    require(input_total + a['total'] <= 4*GIB, 'simultaneous active input exceeds 4GiB')
    return value


def launcher(archive_path, archive_sha256, manifest_path, manifest_sha256):
    raw = old()['data_bytes'](Path(manifest_path), MANIFEST_CAP, manifest_sha256)
    value = decode(raw)
    require(canonical(value) == raw, 'canonical manifest bytes required')
    retained = old()['data_bytes'](Path(value['retained']['path']), MANIFEST_CAP, value['retained']['sha256'])
    runtime = runtime_observation()
    validate_manifest(value, value['commit'], retained_raw=retained, runtime=runtime,
                      installation=installation_observation(runtime))
    require(value['archive']['sha256'] == archive_sha256, 'archive pin differs')
    archive = old()['data_bytes'](Path(archive_path), ARCHIVE_CAP, archive_sha256)
    members = old()['archive_members'](archive, value['code'])
    return bootstrap_source({name: members[name] for name in BOOTSTRAP})


def inventory(archive_path, commit, *, manifest_path, retained_path, retained_sha256,
              registry_directory, job_directory):
    runtime = runtime_observation()
    installation = installation_observation(runtime)
    for path in (registry_directory, job_directory):
        protected(Path(path), directory=True)
        require(not list(Path(path).iterdir()), 'fixed first diagnostic requires existing empty registry/job')
    retained_raw = old()['data_bytes'](Path(retained_path), MANIFEST_CAP, retained_sha256)
    retained = validate_retained(retained_raw, observe=True)
    ar = old()['file_record'](Path(archive_path), maximum=ARCHIVE_CAP)
    raw = old()['data_bytes'](Path(archive_path), ARCHIVE_CAP, ar['sha256'])
    code = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
        for index, item in enumerate(tar):
            require(index < 30000, 'archive member bound')
            if item.isdir():
                continue
            require(item.isreg() and 0 <= item.size <= MEMBER_CAP, 'archive type/size')
            with tar.extractfile(item) as stream:
                data = stream.read(item.size + 1)
            require(len(data) == item.size, 'archive member length')
            code.append(dict(path=item.name, size=len(data), sha256=digest(data)))
    code.sort(key=lambda x: x['path'])
    old()['archive_members'](raw, code)
    dependencies = old()['walk'](old()['DEPENDENCY_SOURCE'], old()['PACKAGES'])
    value = dict(format=FORMAT, commit=commit, archive=ar, code=code, dependencies=dependencies,
        dependency_root=old()['DEPENDENCY_SOURCE'].as_posix(), packages=list(old()['PACKAGES']),
        timezone_data=old()['timezone_manifest'](), runtime=runtime, baseline=baseline(), profile=fixed_profile(),
        retained=dict(path=absolute(str(retained_path)), size=len(retained_raw), sha256=digest(retained_raw)))
    protected(Path(BASELINE_PATH))
    require(old()['file_record'](Path(BASELINE_PATH), maximum=270233600) ==
            dict(size=270233600, sha256=BASELINE_SHA), 'fresh baseline bytes differ')
    value['admission'] = dict(registry_directory=absolute(str(registry_directory)), job_directory=absolute(str(job_directory)),
        purpose='context-receipt-corpus-diagnostic-v1', profile_kind='atp-heavy',
        identity=budget_identity(value, runtime, installation), retained_history_digest=digest(retained_raw))
    value['allocation'] = allocation_plan(dict(value, _retained_data=retained), archive_path=archive_path,
        manifest_path=manifest_path, retained_path=retained_path)
    value['admission']['plan_digest'] = digest(canonical({k: v for k, v in value.items() if k != 'admission'}))
    validate_manifest(value, commit, retained_raw=retained_raw, runtime=runtime, installation=installation)
    require(len(canonical(value)) <= MANIFEST_CAP, 'manifest cap')
    return canonical(value)
