"""One-shot diagnostic accounting prerequisite, never launch or C/B authority.

Only stdlib and the reviewed preparation helper are imported. This source also
executes in a held compiled namespace without registering an imported helper.
Root/host compromise, foreign privileged edits and VM rollback are excluded.
"""
import json
import os
import stat
import sys
import threading
from types import MappingProxyType

import context_preparation_budget as budget


REGISTRY_NAME = 'diagnostic-admissions.jsonl'
_FORMAT = 'betboy-native-diagnostic-admission-v1'
_PURPOSE = 'context-receipt-corpus-diagnostic-v1'
_PROFILE = 'atp-heavy'
_ZERO = '0' * 64
_POISONED = set()
_MAX_FILE_ID = 2**128 - 1  # POSIX uint64 and portable Windows file identifiers.


class AdmissionError(RuntimeError):
    """No diagnostic owner is available; existing evidence must be retained."""


class NativeAdmissionUnavailable(AdmissionError):
    pass


def _require(condition, message):
    if not condition:
        raise AdmissionError(message)


def _copy(value):
    return json.loads(budget._canonical(value))


def _readonly(value):
    if type(value) is dict:
        return MappingProxyType({k: _readonly(v) for k, v in value.items()})
    return value


def _family(identity, purpose, profile_kind):
    return budget._hash(dict(purpose=purpose, profile_kind=profile_kind,
                            **{k: v for k, v in identity.items() if k != 'profile_digest'}))


def _location(value):
    budget._closed(value, {'path', 'device', 'inode'}, 'protected location')
    _require(type(value['path']) is str and 0 < len(value['path']) <= 1024
             and '\x00' not in value['path'] and os.path.isabs(value['path'])
             and os.path.normpath(value['path']) == value['path'],
             'invalid bounded protected path')
    for key in ('device', 'inode'):
        budget._integer(value[key], key, maximum=_MAX_FILE_ID)


def _json_integer(value):
    _require(len(value) <= 39, 'registry integer encoding exceeds bound')
    return int(value)


def _process(value):
    budget._closed(value, {'pid', 'start_ticks', 'ticks_per_second', 'start_boot_ns',
                          'boot_id', 'deadline_boot_ns'}, 'original process')
    for key in ('pid', 'start_ticks', 'ticks_per_second', 'start_boot_ns', 'deadline_boot_ns'):
        budget._integer(value[key], key, minimum=1 if key in ('pid', 'ticks_per_second') else 0)
    _require(type(value['boot_id']) is str and budget._BOOT.fullmatch(value['boot_id']),
             'invalid original boot')
    _require(value['start_boot_ns'] == value['start_ticks'] * 10**9 // value['ticks_per_second'],
             'original process clock conversion changed')
    _require(value['deadline_boot_ns'] == value['start_boot_ns'] + budget.TOTAL_ELAPSED_NS,
             'original process deadline changed')


def _first(body):
    budget._closed(body, {'family', 'identity', 'purpose', 'profile_kind', 'plan_digest',
                          'retained_history_digest', 'job', 'registry', 'registry_file', 'process'}, 'admitting body')
    identity = budget.BudgetIdentity(**body['identity'])
    actual = budget._identity(identity)
    _require(body['purpose'] == _PURPOSE and body['profile_kind'] == _PROFILE,
             'foreign diagnostic purpose or profile')
    for key in ('family', 'plan_digest', 'retained_history_digest'):
        budget._digest(body[key], key)
    _require(body['family'] == _family(actual, body['purpose'], body['profile_kind']),
             'stable diagnostic family changed')
    _location(body['job']); _location(body['registry']); _process(body['process'])
    budget._closed(body['registry_file'], {'device', 'inode'}, 'registry file identity')
    for key in ('device', 'inode'):
        budget._integer(body['registry_file'][key], key, maximum=_MAX_FILE_ID)


def _binding(body, first):
    budget._closed(body, {'family', 'journal', 'journal_device', 'journal_inode',
                          'journal_head', 'ticket', 'deadline_boot_ns'}, 'admitted body')
    _require(body['family'] == first['family'], 'admitted family changed')
    identity_digest = budget._hash(first['identity'])
    _require(body['journal'] == identity_digest + '.jsonl', 'journal name changed')
    for key in ('journal_device', 'journal_inode'):
        budget._integer(body[key], key, maximum=_MAX_FILE_ID)
    budget._integer(body['deadline_boot_ns'], 'effective deadline')
    budget._digest(body['journal_head'], 'admitted journal head')
    ticket = budget.Reservation(**body['ticket'])
    budget._reservation(ticket)
    _require(ticket.identity_digest == identity_digest and ticket.sequence == 1
             and ticket.portion_digest == first['plan_digest']
             and ticket.cpu_ns == budget.PORTION_CPU_NS
             and ticket.reservation_digest == body['journal_head'], 'ticket binding changed')
    _require(body['deadline_boot_ns'] == min(first['process']['deadline_boot_ns'],
                                           ticket.deadline_boot_ns), 'effective deadline changed')


def _parse(data):
    _require(type(data) is bytes and 0 < len(data) <= budget.MAX_JOURNAL_BYTES
             and data.endswith(b'\n'), 'empty, partial or oversized registry')
    lines = data.splitlines(keepends=True)
    _require(len(lines) <= 256, 'registry record bound exhausted')
    head, entries, current = _ZERO, [], None
    families = set()
    for index, line in enumerate(lines):
        _require(len(line) <= 4096 and line.endswith(b'\n'), 'oversized registry record')
        env = json.loads(line, object_pairs_hook=budget._pairs, parse_int=_json_integer,
                         parse_float=budget._forbidden_number, parse_constant=budget._forbidden_number)
        budget._closed(env, {'record', 'digest'}, 'registry envelope')
        _require(budget._canonical(env) + b'\n' == line, 'noncanonical registry')
        record = env['record']
        budget._closed(record, {'format', 'version', 'sequence', 'previous', 'event', 'body'},
                       'registry record')
        budget._integer(record['version'], 'registry version', minimum=1, maximum=1)
        budget._integer(record['sequence'], 'registry sequence', maximum=255)
        _require(record['format'] == _FORMAT and record['sequence'] == index
                 and record['previous'] == head and env['digest'] == budget._hash(record),
                 'registry schema/order/head changed')
        body, event = record['body'], record['event']
        if event == 'admitting':
            _require(current is None or 'closed' in current, 'prior admission nonterminal')
            _first(body)
            _require(body['family'] not in families, 'family already consumed')
            families.add(body['family'])
            current = {'admission': body}
            entries.append(current)
        elif event == 'admitted':
            _require(current is not None and set(current) == {'admission'}, 'unexpected admitted record')
            _binding(body, current['admission'])
            current['binding'] = body
        elif event == 'closed':
            _require(current is not None and set(current) == {'admission', 'binding'},
                     'unexpected terminal record')
            budget._closed(body, {'family', 'journal_head'}, 'terminal body')
            _require(body['family'] == current['admission']['family'], 'terminal family changed')
            budget._digest(body['journal_head'], 'stopped journal head')
            current['closed'] = body
        else:
            raise AdmissionError('unknown registry event')
        head = env['digest']
    return entries, head, len(lines)


def _line(data, event, body):
    if data:
        _, head, count = _parse(data)
    else:
        head, count = _ZERO, 0
    record = dict(format=_FORMAT, version=1, sequence=count, previous=head, event=event, body=body)
    line = budget._canonical(dict(record=record, digest=budget._hash(record))) + b'\n'
    _require(len(line) <= 4096 and len(data) + len(line) <= budget.MAX_JOURNAL_BYTES,
             'registry byte capacity exhausted')
    _parse(data + line)
    return line


def _historical(namespace, entries, registry_inode, *, sync):
    expected = {REGISTRY_NAME}
    for entry in entries:
        first = entry['admission']
        _require(first['registry'] == namespace.registry_identity, 'historical registry path changed')
        _require((first['registry_file']['device'], first['registry_file']['inode']) == registry_inode,
                 'historical registry file replaced')
        _require('closed' in entry, 'prior nonterminal admission blocks registry')
        binding = entry['binding']
        name = binding['journal']
        _require(name not in expected, 'reused journal membership')
        expected.add(name)
        raw, device, inode = namespace.journal(name)
        _require((device, inode) == (binding['journal_device'], binding['journal_inode']),
                 'historical journal replaced')
        state = budget._replay(raw, budget.BudgetIdentity(**first['identity'])).snapshot()
        _require(state.status == 'stopped' and state.record_count == 3
                 and state.settled_cpu_ns == 0 and state.charged_cpu_ns == budget.PORTION_CPU_NS
                 and state.journal_digest == entry['closed']['journal_head']
                 and state.pending == budget.Reservation(**binding['ticket']),
                 'historical stopped budget cross-binding changed')
        if sync:
            namespace.sync_journal(name, raw, device, inode)
    _require(namespace.names() == expected, 'missing or unexpected registry membership')


def _append(owner, event, body):
    owner._namespace.check()
    data = owner._store.read()
    line = _line(data, event, body)
    owner._store.append(line)
    owner._namespace.check()
    owner._namespace.directory_sync()
    owner._namespace.check()
    _require(owner._store.read() == data + line, 'registry append changed')


class DiagnosticAdmission:
    """Live one-shot custody owner. Data is not native-success/launch authority."""
    __slots__ = ('_namespace', '_store', '_budget', '_first', '_bound', '_monitor',
                 '_failed', '_closed', '_operation', '_expected_registry')

    def __init__(self):
        raise TypeError('use admit_diagnostic')

    def _poison(self):
        self._failed = True
        _POISONED.add(self._namespace.registry_identity['path'])

    def _check_time(self):
        _require(self._namespace.process_identity() == self._first['process'],
                 'original parent process/boot identity changed')
        sample = budget._system_clock()
        self._monitor.observe(sample)
        deadline = self._first['process']['deadline_boot_ns']
        if self._bound is not None:
            deadline = self._bound['deadline_boot_ns']
        _require(sample.boot_id == self._first['process']['boot_id']
                 and sample.boot_after_ns < deadline
                 and sample.boot_before_ns >= self._first['process']['start_boot_ns'],
                 'original process deadline expired or boot changed')

    def _check(self):
        _require(not self._closed and not self._failed, 'admission is closed or permanently poisoned')
        self._namespace.check()
        self._check_time()
        raw = self._store.read()
        _require(raw == self._expected_registry, 'live registry head changed')
        entries, _, _ = _parse(raw)
        _require(entries[-1] == {'admission': self._first, 'binding': self._bound},
                 'live admission binding changed')
        current_name = self._bound['journal']
        known = {REGISTRY_NAME, current_name} | {e['binding']['journal'] for e in entries[:-1]}
        _require(self._namespace.names() == known, 'live membership changed')
        # Historical cross-binding checks are read-only, with no time renewal.
        for entry in entries[:-1]:
            binding = entry['binding']
            raw_history, dev, ino = self._namespace.journal(binding['journal'])
            state = budget._replay(raw_history, budget.BudgetIdentity(**entry['admission']['identity'])).snapshot()
            _require((dev, ino) == (binding['journal_device'], binding['journal_inode'])
                     and state.status == 'stopped' and state.journal_digest == entry['closed']['journal_head']
                     and state.pending == budget.Reservation(**binding['ticket'])
                     and state.charged_cpu_ns == budget.PORTION_CPU_NS and state.settled_cpu_ns == 0,
                     'retained historical budget changed')
        self._budget._check_time()
        state = self._budget.snapshot()
        raw_budget, dev, ino = self._namespace.journal(current_name)
        actual = budget._replay(raw_budget, budget.BudgetIdentity(**self._first['identity'])).snapshot()
        _require((dev, ino) == (self._bound['journal_device'], self._bound['journal_inode'])
                 and actual == state and state.status == 'pending' and state.record_count == 2
                 and state.identity_digest == budget._hash(self._first['identity'])
                 and state.journal_digest == self._bound['journal_head']
                 and state.pending == budget.Reservation(**self._bound['ticket'])
                 and state.charged_cpu_ns == budget.PORTION_CPU_NS and state.settled_cpu_ns == 0,
                 'live budget/ticket/head changed')
        self._namespace.check()
        self._check_time()

    def assert_admitted(self):
        _require(self._operation.acquire(blocking=False), 'concurrent admission operation')
        try:
            self._check()
        except BaseException:
            self._poison()
            raise
        finally:
            self._operation.release()

    def snapshot(self):
        _require(self._operation.acquire(blocking=False), 'concurrent admission operation')
        try:
            self._check()
            return _readonly(_copy(dict(admission=self._first, binding=self._bound)))
        except BaseException:
            self._poison()
            raise
        finally:
            self._operation.release()

    def close(self):
        _require(self._operation.acquire(blocking=False), 'concurrent admission operation')
        try:
            if self._closed:
                _require(not self._failed, 'prior close failed; no cleanup success')
                return
            self._check()
            result = self._budget.stop_unmeasured()
            _require(result.status == 'stopped' and result.charged_cpu_ns == budget.PORTION_CPU_NS
                     and result.pending == budget.Reservation(**self._bound['ticket']),
                     'stopped budget lost its retained charge')
            self._namespace.check()
            self._check_time()
            _append(self, 'closed', dict(family=self._first['family'], journal_head=result.journal_digest))
            self._check_time()
        except BaseException:
            self._poison()
            raise
        finally:
            try:
                if not self._closed:
                    self._release()
            except BaseException:
                self._poison()
                raise
            finally:
                self._operation.release()

    def _release(self):
        self._closed = True
        try:
            if self._budget is not None:
                self._budget.close()
        finally:
            try:
                if self._store is not None:
                    self._store.close()
            finally:
                self._namespace.close()

    def __enter__(self):
        self.assert_admitted()
        return self

    def __exit__(self, *_args):
        self.close()


def _admit_protocol(namespace, *, identity, purpose, profile_kind, plan_digest, retained_history_digest):
    """Private protocol seam; a portable adapter is never native assurance."""
    owner = object.__new__(DiagnosticAdmission)
    owner._namespace, owner._store, owner._budget = namespace, None, None
    owner._failed, owner._closed, owner._bound = False, False, None
    owner._operation = threading.Lock()
    touched = False
    try:
        values = budget._identity(identity)
        identity = budget.BudgetIdentity(**values)
        _require(purpose == _PURPOSE and profile_kind == _PROFILE, 'fixed purpose/profile required')
        budget._digest(plan_digest, 'fixed entire plan')
        budget._digest(retained_history_digest, 'retained inventory')
        namespace.check()
        _require(namespace.registry_identity['path'] not in _POISONED,
                 'this process has an uncertain prior registry operation')
        process = namespace.process_identity()
        _process(process)
        owner._first = dict(family=_family(values, purpose, profile_kind), identity=values,
                            purpose=purpose, profile_kind=profile_kind, plan_digest=plan_digest,
                            retained_history_digest=retained_history_digest,
                            job=_copy(namespace.job_identity), registry=_copy(namespace.registry_identity),
                            process=process)
        owner._monitor = budget._State(identity)
        owner._check_time()
        names = namespace.names()
        if REGISTRY_NAME not in names:
            _require(not names, 'missing registry cannot be recreated in nonempty directory')
            touched = True
            owner._store = namespace.open_registry(True)
            data = b''
        else:
            owner._store = namespace.open_registry(False)
            data = owner._store.read()
            entries, _, count = _parse(data)
            _require(all(e['admission']['family'] != owner._first['family'] for e in entries),
                     'diagnostic family is permanently consumed')
            _require(count + 3 <= 256, 'no full admission/close registry capacity')
            _historical(namespace, entries, owner._store.inode, sync=True)
            os.fsync(owner._store.fd)
            namespace.directory_sync()
            namespace.check()
            _require(owner._store.read() == data, 'history changed during fresh sync')
        owner._check_time()
        owner._first['registry_file'] = dict(zip(('device', 'inode'), owner._store.inode))
        _first(owner._first)
        touched = True
        _append(owner, 'admitting', owner._first)
        owner._check_time()
        namespace.check()
        owner._budget = namespace.create_budget(identity)
        namespace.check()
        owner._check_time()
        ticket = owner._budget.reserve(plan_digest, budget.PORTION_CPU_NS)
        state = owner._budget.snapshot()
        name = budget._hash(values) + '.jsonl'
        raw, device, inode = namespace.journal(name)
        _require(budget._replay(raw, identity).snapshot() == state, 'reserved journal changed')
        ticket_data = {field.name: getattr(ticket, field.name) for field in budget.fields(budget.Reservation)}
        owner._bound = dict(family=owner._first['family'], journal=name, journal_device=device,
                            journal_inode=inode, journal_head=state.journal_digest, ticket=ticket_data,
                            deadline_boot_ns=min(process['deadline_boot_ns'], state.deadline_boot_ns))
        _binding(owner._bound, owner._first)
        _append(owner, 'admitted', owner._bound)
        owner._expected_registry = owner._store.read()
        owner.assert_admitted()
        return owner
    except BaseException:
        if touched:
            owner._poison()
        owner._release()
        raise


def _path(value):
    value = os.fspath(value)
    _require(type(value) is str and 0 < len(value) <= 1024 and '\x00' not in value
             and os.path.isabs(value) and os.path.normpath(value) == value
             and os.path.realpath(value) == value, 'canonical absolute no-symlink path required')
    return value


def _stat_directory(info):
    _require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
             'every ancestor must be root-owned and not group/world writable')


def _stat_file(info):
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == 0
             and not info.st_mode & 0o077 and info.st_size <= budget.MAX_JOURNAL_BYTES,
             'private bounded root-owned single-link regular file required')


def _original_process():
    with open('/proc/self/stat', 'rb') as stream:
        raw = stream.read(8193)
    _require(len(raw) <= 8192 and b') ' in raw, 'bounded kernel process identity required')
    suffix = raw.rsplit(b') ', 1)[1].split()
    pid, start = int(raw.split(b' ', 1)[0]), int(suffix[19])
    _require(pid == os.getpid(), 'kernel process PID mismatch')
    ticks = os.sysconf('SC_CLK_TCK')
    start_ns = start * 10**9 // ticks
    sample = budget._system_clock()
    result = dict(pid=pid, start_ticks=start, ticks_per_second=ticks, start_boot_ns=start_ns,
                  boot_id=sample.boot_id, deadline_boot_ns=start_ns + budget.TOTAL_ELAPSED_NS)
    _process(result)
    return result


class _NativeNamespace:
    def __init__(self, registry, job):
        import fcntl
        self._fcntl = fcntl
        self._chains, self._closed, self._locked = [], False, False
        self._registry_file = None
        self._pid = os.getpid()
        try:
            registry, job = _path(registry), _path(job)
            _require(registry != job and not registry.startswith(job + '/')
                     and not job.startswith(registry + '/'), 'registry and job must be separate owned slots')
            self._registry_fd = self._chain(registry)
            self._job_fd = self._chain(job)
            for fd in (self._registry_fd, self._job_fd):
                os.set_inheritable(fd, False)
            self.registry_identity = self._identity(registry, self._registry_fd)
            self.job_identity = self._identity(job, self._job_fd)
            try:
                fcntl.flock(self._registry_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AdmissionError('registry OS lock contention') from exc
            self._locked = True
            self.check()
            _require(not self._names(self._job_fd), 'job slot must already be empty')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _identity(path, fd):
        info = os.fstat(fd)
        return dict(path=path, device=info.st_dev, inode=info.st_ino)

    def _chain(self, path):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open('/', flags)
        self._chains.append(('/', fd, os.fstat(fd)))
        _stat_directory(os.fstat(fd))
        prefix = ''
        for part in path.split('/')[1:]:
            if not part:
                continue
            fd = os.open(part, flags, dir_fd=fd)
            prefix += '/' + part
            info = os.fstat(fd)
            self._chains.append((prefix, fd, info))
            _stat_directory(info)
        return fd

    def check(self):
        _require(not self._closed and self._pid == os.getpid() and os.geteuid() == 0,
                 'lost original root namespace owner')
        for path, fd, original in self._chains:
            held, named = os.fstat(fd), os.stat(path, follow_symlinks=False)
            _stat_directory(held); _stat_directory(named)
            _require((held.st_dev, held.st_ino) == (named.st_dev, named.st_ino)
                     == (original.st_dev, original.st_ino), 'ancestor FD/path identity changed')
        _require(self._locked, 'registry lock not acquired')
        # fdinfo reports locks associated with this open file description. No
        # LOCK_EX reacquisition: reacquisition would hide a lost prior lock.
        with open('/proc/self/fdinfo/' + str(self._registry_fd), 'r', encoding='ascii') as stream:
            text = stream.read(8193)
        info = os.fstat(self._registry_fd)
        identity = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        found = False
        _require(len(text) <= 8192, 'unbounded lock custody observation')
        for line in text.splitlines():
            fields = line.split()
            if len(fields) == 9 and fields[0] == 'lock:' and fields[2:5] == ['FLOCK', 'ADVISORY', 'WRITE']:
                major, minor, inode = fields[6].split(':')
                found |= (int(fields[5]) == self._pid and (int(major,16),int(minor,16),int(inode)) == identity
                          and fields[7:] == ['0', 'EOF'])
        _require(found, 'held open-description flock custody lost')
        if self._registry_file is not None:
            fd, device, inode = self._registry_file
            held = os.fstat(fd)
            named = os.stat(REGISTRY_NAME, dir_fd=self._registry_fd, follow_symlinks=False)
            _stat_file(held); _stat_file(named)
            _require((held.st_dev, held.st_ino) == (named.st_dev, named.st_ino) == (device, inode),
                     'registry file ownership or path changed')

    @staticmethod
    def _names(fd):
        result = set()
        with os.scandir(fd) as entries:
            for entry in entries:
                result.add(entry.name)
                _require(len(result) <= 257, 'registry membership bound exhausted')
        return result

    def names(self):
        self.check()
        return self._names(self._registry_fd)

    def open_registry(self, create):
        self.check()
        flags = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        fd = os.open(REGISTRY_NAME, flags, 0o600, dir_fd=self._registry_fd)
        directory = None
        try:
            _stat_file(os.fstat(fd))
            directory = os.dup(self._registry_fd)
            result = budget._FileJournal(fd, directory, REGISTRY_NAME)
            self._registry_file = (fd, *result.inode)
            return result
        except BaseException:
            os.close(fd)
            if directory is not None:
                os.close(directory)
            raise

    def directory_sync(self):
        self.check()
        os.fsync(self._registry_fd)
        self.check()

    def create_budget(self, identity):
        self.check()
        return budget.PreparationBudget.create(self._registry_fd, identity)

    def journal(self, name):
        self.check()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=self._registry_fd)
        try:
            before = os.fstat(fd)
            _stat_file(before)
            data = bytearray()
            while len(data) <= budget.MAX_JOURNAL_BYTES:
                piece = os.read(fd, min(65536, budget.MAX_JOURNAL_BYTES + 1 - len(data)))
                if not piece:
                    break
                data.extend(piece)
            after = os.fstat(fd)
            named = os.stat(name, dir_fd=self._registry_fd, follow_symlinks=False)
            _stat_file(after); _stat_file(named)
            signature = lambda i: (i.st_dev, i.st_ino, i.st_size, i.st_mtime_ns, i.st_ctime_ns)
            _require(signature(before) == signature(after) == signature(named)
                     and len(data) == after.st_size, 'journal FD/path changed during bounded read')
            self.check()
            return bytes(data), after.st_dev, after.st_ino
        finally:
            os.close(fd)

    def sync_journal(self, name, raw, device, inode):
        self.check()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=self._registry_fd)
        try:
            info = os.fstat(fd)
            _stat_file(info)
            _require((info.st_dev, info.st_ino) == (device, inode), 'history changed before sync')
            os.fsync(fd)
            self.directory_sync()
            _require(self.journal(name) == (raw, device, inode), 'history changed after sync')
        finally:
            os.close(fd)

    @staticmethod
    def process_identity():
        return _original_process()

    def close(self):
        if not self._closed:
            self._closed = True
            errors = []
            for _path_name, fd, _info in reversed(self._chains):
                try:
                    os.close(fd)
                except OSError as exc:
                    errors.append(exc)
            if errors:
                raise AdmissionError('namespace descriptor cleanup uncertain') from errors[0]


def admit_diagnostic(registry_directory, *, identity, purpose, profile_kind, plan_digest,
                     job_directory, retained_history_digest):
    """Acquire the fixed diagnostic prerequisite; never launches or refunds."""
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise NativeAdmissionUnavailable('real Linux effective UID 0 is required')
    return _admit_protocol(_NativeNamespace(registry_directory, job_directory), identity=identity,
                           purpose=purpose, profile_kind=profile_kind, plan_digest=plan_digest,
                           retained_history_digest=retained_history_digest)
