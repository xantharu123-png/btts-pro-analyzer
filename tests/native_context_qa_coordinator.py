"""Fixed one-shot root QA coordinator. No production writes or generic runner.

Only held reviewed source runs. Historical contents are read as data, never
imported. The separate data worker retains its existing UID65534/seccomp guard.
Every scanner is an actual direct child, fully reaped before the next phase.
"""
from contextlib import ExitStack
import ctypes
import errno
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import selectors
import signal
import stat
import sys
import tarfile
import time

MIB, GIB, NS = 1024**2, 1024**3, 10**9
COORDINATOR = 'tests/native_context_qa_coordinator.py'
BUDGET = 'tests/native_context_qa_budget.py'
INPUT = '/var/lib/betboy-context-qa-v2-inputs-02'
REGISTRY = '/var/lib/betboy-context-qa-v2-registry-02'
JOB = '/var/lib/betboy-context-qa-v2-job-02'
AUTHORIZATION = '2026-09-13-coordination-qualification-02'
PRIOR_REGISTRY = '/var/lib/betboy-context-qa-v2-registry-01'
SELECTORS = (('/var/lib', 'betboy-', ('betboy-backup',)),
             ('/var/tmp', 'betboy-update.', ()),
             ('/tmp', 'betboy-context-', ()), ('/tmp', 'betboy-tour-', ()),
             ('/var/backups', 'betboy', ('betboy-ssh',)))


class CoordinationError(RuntimeError):
    pass


class ScannerStopped(CoordinationError):
    def __init__(self, cause, measurement, prefix):
        super().__init__('scanner stopped: '+type(cause).__name__)
        self.measurement, self.prefix = measurement, prefix


def need(value, message):
    if not value:
        raise CoordinationError(message)


def selected_history():
    result = set()
    for directory, prefix, omitted in SELECTORS:
        count = 0
        with os.scandir(directory) as entries:
            for item in entries:
                count += 1
                need(count <= 50000, 'bounded historical selector exceeded')
                if item.name.startswith(prefix) and item.name not in omitted and item.path not in (INPUT, REGISTRY, JOB):
                    result.add(item.path)
    need(0 < len(result) <= 256, 'bounded complete history required')
    return sorted(result)


def bootstrap_source(sources, base_names):
    need(type(sources) is dict and set(sources) == set(base_names)|{COORDINATOR, BUDGET}, 'exact V2 bootstrap membership required')
    need(all(type(raw) is bytes and 0 < len(raw) <= MIB for raw in sources.values()), 'bounded held V2 source required')
    literal = repr(dict(sorted(sources.items()))).encode('ascii')
    raw = (b'# Reviewed bounded QA V2 held-source entry\n_REVIEWED_QA_BOOTSTRAP = ' + literal +
           b'\nexec(compile(_REVIEWED_QA_BOOTSTRAP["tests/native_context_qa_coordinator.py"], '
           b'"<held-qa-v2-coordinator>", "exec"), globals())\n')
    need(len(raw) <= 2*MIB, 'V2 bootstrap allowance exceeded')
    return raw


def validate_request(c, value):
    c['shape'](value, 'format authorization commit archive roots historical_fifo previous_costs')
    need(value['format'] == 'betboy-context-qa-request-v2' and
         value['authorization'] == AUTHORIZATION, 'fixed explicit QA request required')
    need(type(value['commit']) is str and len(value['commit']) == 40 and
         all(x in '0123456789abcdef' for x in value['commit']), 'fixed full source revision required')
    c['shape'](value['archive'], 'path size sha256')
    need(value['archive']['path'] == INPUT+'/code.tar', 'fixed archive slot required')
    c['integer'](value['archive']['size'], 64*MIB); c['sha'](value['archive']['sha256'])
    need(type(value['roots']) is list and 0 < len(value['roots']) <= 256, 'all historical roots required')
    names = []
    for record in value['roots']:
        c['shape'](record, 'path identity category charged_cpu_ns journals')
        names.append(c['absolute'](record['path']))
        need(type(record['identity']) is list and len(record['identity']) == 7, 'declared historical root identity required')
        for number in record['identity']:
            c['integer'](number, 2**128-1)
        need(record['category'] in ('historical-qa', 'backup', 'rollback', 'reused-input'), 'root category differs')
        if record['charged_cpu_ns'] is not None:
            c['integer'](record['charged_cpu_ns'])
        c['validate_journals'](Path(record['path']), record['journals'])
    need(names == sorted(set(names)), 'historical declarations must be sorted and unique')
    need(all(not PurePosixPath(a).is_relative_to(b) for a in names for b in names if a != b), 'historical roots overlap')
    c['validate_historical_fifo'](value['historical_fifo'])
    costs = value['previous_costs']
    c['shape'](costs, 'primary_reserved_cpu_ns synthetic_reserved_cpu_ns unjournaled_cpu_ns evidence_sha256 prior_qa_reserved_cpu_ns prior_qa_journal_sha256')
    need(type(costs['primary_reserved_cpu_ns']) is int and costs['primary_reserved_cpu_ns'] == 1680*NS and
         type(costs['synthetic_reserved_cpu_ns']) is int and costs['synthetic_reserved_cpu_ns'] == 600*NS and
         costs['unjournaled_cpu_ns'] is None, 'old known charges and unknown costs must remain explicit')
    need(type(costs['prior_qa_reserved_cpu_ns']) is int and costs['prior_qa_reserved_cpu_ns'] == 900*NS,
         'previous failed qualification charge must not be refunded')
    c['sha'](costs['prior_qa_journal_sha256'])
    need(PRIOR_REGISTRY in names, 'previous QA journal must remain in the fully observed history')
    c['sha'](costs['evidence_sha256'])
    return value


def verify_held_archive(c, request, sources):
    raw = c['old']()['data_bytes'](Path(request['archive']['path']), 64*MIB, request['archive']['sha256'])
    need(len(raw) == request['archive']['size'], 'declared archive length differs')
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for index, member in enumerate(archive):
            need(index < 30000, 'archive member count exceeded')
            if member.isdir():
                continue
            c['old']()['relative'](member.name)
            need(member.isreg() and member.name not in seen and 0 <= member.size <= 128*MIB,
                 'invalid or duplicate archive member')
            seen.add(member.name)
            if member.name in sources:
                need(member.size == len(sources[member.name]), 'held bootstrap member size differs')
                with archive.extractfile(member) as stream:
                    need(stream.read(member.size+1) == sources[member.name], 'executing bootstrap differs from declared archive')
    need(set(sources) <= seen, 'executing source missing from archive')


def _scanner_action(step, c, request, retained_raw):
    """The only privileged child workload; no arbitrary callable/command input."""
    need(step in ('A1', 'A2', 'A3', 'C'), 'fixed scanner step required')
    expected = [x['path'] for x in request['roots']]
    need(selected_history() == expected, 'historical selector membership changed')
    for item in request['roots']:
        need(list(c['old']()['identity'](Path(item['path']).lstat())) == item['identity'], 'declared historical root changed')
    if step == 'A1':
        records = []
        for declaration in request['roots']:
            record = c['retained_root_v2'](declaration['path'], historical_fifo=request['historical_fifo'])
            record.update({key: declaration[key] for key in ('category', 'charged_cpu_ns', 'journals')})
            c['validate_journals'](Path(declaration['path']), declaration['journals'], observe=True)
            records.append(record)
        raw = c['canonical'](dict(format='betboy-receipt-diagnostic-retained-v2', roots=records,
            backup_rollback_reserve=4*GIB, historical_fifo=request['historical_fifo']))
        c['validate_retained_v2'](raw)
    elif step == 'A2':
        raw = c['inventory_v2'](request['archive']['path'], request['commit'],
            manifest_path=INPUT+'/catalogue.json', retained_path=INPUT+'/retained.json',
            retained_sha256=c['digest'](retained_raw), registry_directory=REGISTRY, job_directory=JOB)
    else:
        c['validate_retained_v2'](retained_raw, observe=True)
        raw = c['canonical'](dict(step=step, retained_sha256=c['digest'](retained_raw)))
    need(selected_history() == expected and type(raw) is bytes and 0 < len(raw) <= 8*MIB,
         'complete bounded scanner result required')
    return raw


def _cpu_ns(usage):
    seconds = usage.ru_utime + usage.ru_stime
    need(math.isfinite(seconds) and seconds >= 0, 'actual child CPU usage unavailable')
    return math.ceil(seconds*NS)


def scanner_failure_bytes(step, exc):
    """Bounded structural diagnosis, never exception values or frame locals."""
    trace, current, examined = [], exc.__traceback__, 0
    while current is not None and examined < 64:
        code = current.tb_frame.f_code
        trace.append(dict(file=os.path.basename(code.co_filename)[-160:],
                          function=code.co_name[:80], line=current.tb_lineno))
        current, examined = current.tb_next, examined+1
    return json.dumps(dict(format='betboy-scanner-error-v1', step=step,
        exception=type(exc).__name__[:80], trace=trace[-8:], trace_truncated=current is not None),
        sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _scanner_child(step, c, request, retained_raw, write_fd, read_fd, allowance, parent_pid):
    # Child must never unwind inherited Python owners, even on setup failure.
    try:
        import resource
        need(ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) == 0, 'scanner parent-death signal unavailable')
        need(os.getppid() == parent_pid and os.getresuid() == os.getresgid() == (0,)*3,
             'fixed direct root scanner required')
        resource.setrlimit(resource.RLIMIT_CPU, (allowance, allowance))
        resource.setrlimit(resource.RLIMIT_AS, (2*GIB, 2*GIB))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Close inherited journal, active-input and namespace handles. The child
        # reads its own no-follow inputs and only writes the result pipe.
        descriptors = [int(name) for name in os.listdir('/proc/self/fd')]
        for fd in descriptors:
            if fd > 2 and fd != write_fd:
                try:
                    os.close(fd)
                except OSError as exc:
                    if exc.errno != errno.EBADF:
                        raise
                    # The directory-list descriptor has already closed.
        signal.setitimer(signal.ITIMER_REAL, 0)
        raw = _scanner_action(step, c, request, retained_raw)
        c['write_all'](write_fd, raw)
        os.close(write_fd)
        os._exit(0)
    except BaseException as exc:
        try:
            c['write_all'](write_fd, scanner_failure_bytes(step, exc))
        except BaseException:
            pass  # Exit remains failure even if its diagnostic pipe is broken.
        os._exit(125)


def run_scanner(step, c, request, retained_raw, *, allowance, deadline, supervisor):
    """Measure one fixed scanner with wait4; CPU is never child self-report."""
    need(sys.platform == 'linux' and type(allowance) is int and 1 <= allowance <= 400, 'bounded native scanner required')
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    pid = pidfd = terminal = usage = None
    result, peak_combined = bytearray(), 0
    parent_pid = os.getpid()
    started = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    cleanup_attempted = False
    try:
        pid = os.fork()
        if pid == 0:
            _scanner_child(step, c, request, retained_raw, write_fd, read_fd, allowance, parent_pid)
            os._exit(125)
        pidfd = os.pidfd_open(pid)
        os.close(write_fd); write_fd = None
        os.set_blocking(read_fd, False)
        with selectors.DefaultSelector() as poll:
            poll.register(read_fd, selectors.EVENT_READ)
            while terminal is None or poll.get_map():
                need(time.clock_gettime_ns(time.CLOCK_BOOTTIME) < deadline, 'original global QA wall deadline expired')
                if terminal is None:
                    found, status, measured = os.wait4(pid, os.WNOHANG)
                    if found:
                        need(found == pid, 'reaped a different process')
                        terminal, usage = os.waitstatus_to_exitcode(status), measured
                    else:
                        info = supervisor._status(supervisor._read_small('/proc/'+str(pid)+'/status'))
                        if 'VmHWM' in info:
                            peak = supervisor._rss(info)
                            need(peak < GIB and info.get('Threads') == '1', 'scanner RSS/task envelope exceeded')
                            parent = supervisor._status(supervisor._read_small('/proc/self/status'))
                            peak_combined = max(peak_combined, peak+supervisor._rss(parent))
                for event, _ in poll.select(0.05):
                    raw = os.read(event.fd, min(65536, 8*MIB+1-len(result)))
                    if not raw:
                        poll.unregister(event.fd)
                    else:
                        result.extend(raw)
                        need(len(result) <= 8*MIB, 'scanner control pipe exceeded its separate cap')
        cpu = _cpu_ns(usage)
        need(terminal == 0 and cpu <= allowance*NS and usage.ru_maxrss*1024 < GIB,
             'scanner terminal result exceeded its admitted envelope')
        need(result, 'empty scanner result')
        return bytes(result), dict(child_cpu_ns=cpu, child_peak_rss_bytes=usage.ru_maxrss*1024,
            child_exit_code=terminal, combined_observed_peak_rss_bytes=peak_combined,
            elapsed_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)-started)
    except supervisor.UnreapedChild:
        cleanup_attempted = True
        pidfd = None
        raise
    except BaseException as exc:
        if pid and terminal is None:
            try:
                cleanup_attempted = True
                status, usage = supervisor._cleanup(pid, pidfd)
                terminal = os.waitstatus_to_exitcode(status)
            except supervisor.UnreapedChild:
                pidfd = None
                raise
        measured = dict(step=step, child_exit_code=terminal,
                        child_cpu_ns=None if usage is None else _cpu_ns(usage),
                        child_peak_rss_bytes=None if usage is None else usage.ru_maxrss*1024,
                        observed_control_bytes=len(result), control_sha256=hashlib.sha256(result).hexdigest(),
                        elapsed_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)-started)
        raise ScannerStopped(exc, measured, bytes(result[:65536])) from exc
    finally:
        try:
            if pid and terminal is None and not cleanup_attempted:
                supervisor._cleanup(pid, pidfd)
        except supervisor.UnreapedChild:
            pidfd = None  # Exception retains the exact descriptor custody.
            raise
        finally:
            for fd in (read_fd, write_fd, pidfd):
                if fd is not None:
                    os.close(fd)


class Coordinator:
    def __init__(self, parent, c, helpers, qa, sources, request, request_raw, start):
        self.parent, self.c, self.helpers, self.qa = parent, c, helpers, qa
        self.sources, self.request, self.request_raw = sources, request, request_raw
        self.start, self.deadline = start, start+900*NS
        self.bound = None
        self.plan = None
        self.scans = []
        self.worker_result = None
        self.held = ExitStack()
        self.namespace = helpers['admission']['_NativeNamespace'](REGISTRY, JOB)
        self.store = self.account = None
        self._previous_qa_bytes = None
        try:
            need(not self.namespace.names(), 'one-shot V2 registry already used')
            fd = os.open(c['QA_JOURNAL'], os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_APPEND|os.O_NOFOLLOW|os.O_CLOEXEC,
                         0o600, dir_fd=self.namespace._registry_fd)
            self.store = helpers['context_preparation_budget']._FileJournal(fd, os.dup(self.namespace._registry_fd), c['QA_JOURNAL'])
            runtime = c['runtime_observation']()
            installation = c['installation_observation'](runtime)
            identity = helpers['context_preparation_budget'].BudgetIdentity(
                input_digest=c['BASELINE_SHA'], execution_digest=request['archive']['sha256'],
                runtime_digest=c['digest'](c['canonical'](runtime)),
                installation_digest=c['digest'](c['canonical'](installation)),
                profile_digest=c['digest'](c['canonical'](c['fixed_profile']())))
            self.account = qa['QaBudget'](self.store, identity=identity,
                history_digest=c['digest'](request_raw), process_start_boot_ns=start,
                clock=helpers['context_preparation_budget']._system_clock, parent_cpu=time.process_time_ns,
                authorization=AUTHORIZATION)
            self.held.enter_context(c['old']()['opened'](Path(INPUT)/'request.json'))
            self.held.enter_context(c['old']()['opened'](Path(INPUT)/'code.tar'))
            need(c['old']()['data_bytes'](Path(INPUT)/'request.json', MIB, c['digest'](request_raw)) == request_raw,
                 'held initial request bytes changed')
            need(c['old']()['file_record'](Path(INPUT)/'code.tar', maximum=64*MIB) ==
                 {k: request['archive'][k] for k in ('size', 'sha256')}, 'held initial code archive changed')
            verify_held_archive(c, request, sources)
            self.assert_admitted()
        except BaseException:
            self.close()
            raise

    def check_previous_package(self):
        previous = self.c['old']()['data_bytes'](Path(PRIOR_REGISTRY)/self.c['QA_JOURNAL'], MIB,
            self.request['previous_costs']['prior_qa_journal_sha256'])
        if self._previous_qa_bytes is None:
            old_state = self.qa['replay'](previous).snapshot()
            need(old_state['charged_cpu_ns'] == 900*NS and
                 old_state['binding']['authorization'] == self.qa['AUTHORIZATION'] and
                 old_state['completed_steps'] == ['A1'] and old_state['pending']['step'] == 'A2',
                 'previous failed qualification state changed; no fresh-budget reset')
            self._previous_qa_bytes = previous
        # The complete previous file is freshly read and hash-checked above,
        # not merely trusted via cached metadata. Identical accepted bytes need
        # no second semantic replay; a changed file cannot acquire old authority.
        need(previous == self._previous_qa_bytes, 'previous qualification bytes changed')

    def assert_admitted(self):
        self.namespace.check()
        self.store.check()
        self.check_previous_package()
        info = os.fstat(self.store.fd)
        need(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o600,
             'private native V2 accounting seal changed')
        need(self.namespace.names() == {self.c['QA_JOURNAL']}, 'V2 registry membership changed')
        self.account.assert_running()

    def check_controls(self):
        self.assert_admitted()
        need(self.plan is not None, 'complete allocation plan not bound')
        return self.c['sample_exact_slots'](Path(INPUT), self.plan['coordination_slots'], MIB)

    def snapshot(self):
        self.assert_admitted()
        return dict(binding=dict(deadline_boot_ns=self.deadline))

    def assert_bootstrap(self, digest):
        need(self.c['digest'](bootstrap_source(self.sources, self.c['BOOTSTRAP'])) == digest,
             'actual V2 held bootstrap differs')

    def bind_prepared(self, manifest, retained_raw):
        need(self.account.snapshot()['completed_steps'] == ['A1', 'A2'] and self.bound is None,
             'preparation was not completed exactly once')
        need(manifest['archive'] == {k: self.request['archive'][k] for k in ('size', 'sha256')} and
             manifest['commit'] == self.request['commit'] and manifest['retained']['sha256'] == self.c['digest'](retained_raw),
             'prepared inputs differ from originally declared request')
        self.bound = self.c['digest'](self.c['canonical'](manifest))
        self.plan = manifest['allocation']

    def scan(self, step, retained_raw=None):
        self.assert_admitted()
        allowance = self.account.begin(step)
        print('QA '+step+' started', flush=True)
        raw, actual = run_scanner(step, self.c, self.request, retained_raw, allowance=allowance,
                                 deadline=self.deadline, supervisor=self.helpers['context_preparation_supervisor'])
        evidence = self.c['digest'](raw)
        measurement = {k: actual[k] for k in ('child_cpu_ns', 'child_peak_rss_bytes', 'child_exit_code')}
        self.account.finish(step, **measurement, evidence_digest=evidence)
        self.scans.append(dict(step=step, evidence_sha256=evidence, **actual))
        print('QA '+step+' completed; CPU '+str(actual['child_cpu_ns']//1_000_000)+' ms', flush=True)
        self.assert_admitted()
        return raw

    def observe_retained(self, step, retained_raw):
        need(step in ('A3', 'C') and self.bound is not None, 'prepared binding missing')
        raw = self.scan(step, retained_raw)
        need(raw == self.c['canonical'](dict(step=step, retained_sha256=self.c['digest'](retained_raw))),
             'complete retained observation differs')

    def run_worker(self, helpers, worker, attempt, fd):
        self.assert_admitted()
        need(self.bound is not None and self.worker_result is None and helpers is self.helpers, 'fixed worker already used or substituted')
        need(self.account.begin('B') == 240, 'unchanged data worker budget required')
        print('QA B data check started', flush=True)
        result = self.parent['launch_once'](helpers, worker, attempt, fd)
        # Full terminal measurements are persisted by the shared parent before
        # semantic parsing. A failed worker keeps its pending full reservation.
        self.worker_result = result
        print('QA B ended; exit '+str(result.exit_code), flush=True)
        if result.exit_code == 0 and result.stop_reason is None:
            self.account.finish('B', child_cpu_ns=result.child_cpu_ns, child_peak_rss_bytes=result.peak_rss_bytes,
                child_exit_code=result.exit_code, evidence_digest=self.c['digest'](self.c['canonical'](self.parent['native_data'](result))))
        return result

    def close(self):
        try:
            self.held.close()
        finally:
            try:
                if self.account is not None:
                    self.account.close()
                elif self.store is not None:
                    self.store.close()
            finally:
                self.namespace.close()


def main(argv):
    sources = globals().get('_REVIEWED_QA_BOOTSTRAP')
    need(type(sources) is dict and COORDINATOR in sources and BUDGET in sources, 'held V2 bootstrap required')
    parent = dict(__name__='_held_qa_v2_parent', __file__='<held-qa-v2-parent>')
    exec(compile(sources['tests/native_context_receipt_diagnostic.py'], parent['__file__'], 'exec'), parent)
    start, _ = parent['startup']()
    need(type(argv) is list and len(argv) == 4 and argv[::2] == ['--request', '--request-sha256'] and
         argv[1] == INPUT+'/request.json', 'fixed V2 invocation required')
    base = {name: raw for name, raw in sources.items() if name not in (COORDINATOR, BUDGET)}
    c = parent['load_catalogue'](base)
    need(set(base) == set(c['BOOTSTRAP']), 'V2 base source closure differs')
    helpers = parent['load_helpers'](c, base)
    helpers['context_preparation_supervisor']._require_native_owner()
    qa = dict(__name__='_held_qa_v2_budget', __file__='<held-qa-v2-budget>')
    exec(compile(sources[BUDGET], qa['__file__'], 'exec'), qa)
    request_raw = c['old']()['data_bytes'](Path(argv[1]), MIB, argv[3])
    request = validate_request(c, c['decode'](request_raw))
    need(c['canonical'](request) == request_raw, 'canonical V2 request required')
    for path in (INPUT, REGISTRY, JOB):
        c['protected'](Path(path), directory=True, searchable=path != REGISTRY)
    c['protected'](Path(argv[1]))
    need(sorted(p.name for p in Path(INPUT).iterdir()) == ['code.tar', 'request.json'], 'fixed new input namespace differs')
    owner = Coordinator(parent, c, helpers, qa, sources, request, request_raw, start)
    def alarm(_signum, _frame):
        raise CoordinationError('original global QA wall deadline')
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, (owner.deadline-time.clock_gettime_ns(time.CLOCK_BOOTTIME))/NS))
    try:
        retained_raw = owner.scan('A1')
        parent['write_new'](c, Path(INPUT)/'retained.json', retained_raw, 8*MIB)
        manifest_raw = owner.scan('A2', retained_raw)
        parent['write_new'](c, Path(INPUT)/'catalogue.json', manifest_raw, 8*MIB)
        bootstrap = bootstrap_source(sources, c['BOOTSTRAP'])
        args = {'--manifest': INPUT+'/catalogue.json', '--manifest-sha256': c['digest'](manifest_raw),
                '--archive': INPUT+'/code.tar', '--directory': JOB, '--registry': REGISTRY,
                '--commit': request['commit'], '--launcher-sha256': c['digest'](bootstrap)}
        result = parent['_run_prepared'](args, c, sources, helpers, start, owner.deadline, coordination=owner)
        need(result == 0, 'shared execution did not complete')
        report_path = Path(JOB)/'report.json'
        record = c['old']()['file_record'](report_path, maximum=MIB)
        owner.account.complete(record['sha256'])
        final = dict(format='betboy-context-qa-coordination-v2', previous_costs=request['previous_costs'],
                     account=owner.account.snapshot(), scans=owner.scans, source_commit=request['commit'],
                     report_sha256=record['sha256'], native_pass=False, external_terminal_observation_required=True)
        parent['write_new'](c, Path(INPUT)/'coordination-result.json', c['canonical'](final), MIB)
        print(c['canonical'](dict(status='complete-external-terminal-required', source_commit=request['commit'],
                                 charged_cpu_ns=900*NS, scans=len(owner.scans), native_pass=False)).decode('ascii'), flush=True)
        return 0
    except helpers['context_preparation_supervisor'].UnreapedChild as exc:
        parent['custody_stop'](exc, lambda value: os.write(2, c['canonical'](value)+b'\n'), retained_cpu_ns=900*NS)
        raise
    except BaseException as exc:
        failure = dict(status='STOP', exception=type(exc).__name__, charged_cpu_ns=900*NS,
                       previous_costs=request['previous_costs'], native_pass=False)
        if isinstance(exc, ScannerStopped):
            failure.update(scanner=exc.measurement, control_prefix_hex=exc.prefix.hex(),
                           control_prefix_complete=exc.measurement['observed_control_bytes'] == len(exc.prefix))
        parent['write_new'](c, Path(INPUT)/'coordination-failure.json', c['canonical'](failure), MIB)
        print('QA stopped; retained evidence; '+type(exc).__name__, flush=True)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        owner.close()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
