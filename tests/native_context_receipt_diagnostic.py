"""Fresh stdlib-only Task61 parent. No retry, release, Source or C/B pass."""
from contextlib import ExitStack
import ctypes
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types

MIB, GIB = 1024**2, 1024**3
FLAGS = ('--manifest', '--manifest-sha256', '--archive', '--directory', '--registry', '--commit', '--launcher-sha256')
CATALOGUE = 'tests/native_context_receipt_diagnostic_catalogue.py'
OLD = 'tests/native_context_chain_catalogue.py'
ADMISSION = 'tests/native_context_diagnostic_admission.py'
PREFIX_ROOT = '/var/lib/betboy-receipt-prefix-task61-01'
PROBE_SOURCE = b'''"""Fixed Task61 stdlib-only guard probe; never a receipt diagnostic."""
import ctypes, json, os, resource, sys
assert sys.argv[1:] == ["receipt-v1"]
assert os.getresuid() == os.getresgid() == (65534,)*3
assert os.getgroups() == []
assert (sys.flags.isolated,sys.flags.no_site,sys.flags.dont_write_bytecode,sys.flags.optimize)==(1,1,1,0)
assert resource.getrlimit(resource.RLIMIT_CPU)==(240,240)
assert resource.getrlimit(resource.RLIMIT_FSIZE)==(536870912,536870912)
assert resource.getrlimit(resource.RLIMIT_AS)==(2147483648,2147483648)
assert resource.getrlimit(resource.RLIMIT_NPROC)==(0,0)
assert resource.getrlimit(resource.RLIMIT_CORE)==(0,0)
assert ctypes.CDLL(None).prctl(3,0,0,0,0)==0
with open("/proc/self/status","r",encoding="ascii") as f: raw=f.read(65537)
assert len(raw)<=65536
fields=dict(line.split(":",1) for line in raw.splitlines())
assert all(int(fields[k].strip(),16)==0 for k in ("CapInh","CapPrm","CapEff","CapBnd","CapAmb"))
assert all(fields[k].strip()==v for k,v in (("Threads","1"),("NoNewPrivs","1"),("Seccomp","2"),("TracerPid","0")))
print(json.dumps({"format":"betboy-task61-prefix-probe-v1","guard":True,"cpu":[240,240]},sort_keys=True,separators=(",",":")),flush=True)
'''


class DiagnosticError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise DiagnosticError(message)


def arguments(argv):
    require(type(argv) is list and len(argv) == 14 and tuple(argv[::2]) == FLAGS, 'exact seven ordered CLI pairs required')
    require(all(type(v) is str and v for v in argv[1::2]), 'nonempty CLI values required')
    return dict(zip(FLAGS, argv[1::2]))


def load_catalogue(sources):
    require(type(sources) is dict and OLD in sources and CATALOGUE in sources, 'held bootstrap only; no root path fallback')
    raw = sources[OLD]
    require(type(raw) is bytes and len(raw) <= MIB and hashlib.sha256(raw).hexdigest() ==
            '48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935', 'old held catalogue pin differs')
    old = dict(__name__='_task61_old_catalogue', __file__='<held-old-catalogue>')
    exec(compile(raw, old['__file__'], 'exec'), old)
    raw = sources[CATALOGUE]
    require(type(raw) is bytes and 0 < len(raw) <= MIB, 'held new catalogue bound')
    c = dict(__name__='_task61_catalogue', __file__='<held-task61-catalogue>', _OLD_CATALOGUE=old)
    exec(compile(raw, c['__file__'], 'exec'), c)
    c['bootstrap_source'](sources)
    return c


def load_helpers(c, sources):
    result = {}
    for filename, expected in c['HELPERS'].items():
        raw = sources[filename]
        require(c['digest'](raw) == expected, 'held helper pin differs')
        name = filename[:-3]
        require(name not in sys.modules, 'fresh helper interpreter required')
        module = types.ModuleType(name)
        module.__file__ = '<reviewed-' + filename + '>'
        sys.modules[name] = module
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        result[name] = module
    raw = sources[ADMISSION]
    require(c['digest'](raw) == c['PINS'][ADMISSION], 'Task60 held source pin differs')
    admission = dict(__name__='_task61_admission', __file__='<held-task60>')
    exec(compile(raw, admission['__file__'], 'exec'), admission)
    result['admission'] = admission
    supervisor = result['context_preparation_supervisor']
    result['child_original'] = supervisor._child_run_python
    return result


def startup():
    require(sys.platform == 'linux' and os.uname().machine == 'x86_64' and os.getresuid() == (0,)*3,
            'fresh native root coordinator required')
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    os.umask(0o022)
    for key, cap in ((resource.RLIMIT_AS, 2*GIB), (resource.RLIMIT_FSIZE, 512*MIB), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (cap, cap))
    require((sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0),
            'fresh assertion-enabled -I -S -B required')
    require(dict(os.environ) == {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, 'fresh env-i coordinator required')
    lib = ctypes.CDLL(None)
    require(lib.prctl(4, 0, 0, 0, 0) == 0 and lib.prctl(3, 0, 0, 0, 0) == 0, 'parent nondumpable required')
    with open('/proc/self/stat', 'rb') as stream:
        raw = stream.read(8193)
    require(len(raw) <= 8192 and raw.startswith(str(os.getpid()).encode() + b' ('), 'kernel original start required')
    ticks = int(raw[raw.rfind(b')')+2:].split()[19])
    start = ticks * 10**9 // os.sysconf('SC_CLK_TCK')
    return start, start + 3600*10**9


def child_prefix(supervisor, original, *, parent_pid, worker, cwd, guard):
    """The only child CPU handoff; every failure exits without Python unwind."""
    import resource
    require(supervisor._child_run_python is original and original.__module__ == 'context_preparation_supervisor'
            and original.__name__ == '_child_run_python', 'exact original child callable required')
    original_code = original.__code__
    expected_argv, expected_cwd = (str(worker), 'receipt-v1'), str(cwd)
    def prefix(argv, uid, gid, actual_cwd, stdout_fd, stderr_fd, null_fd, file_size_bytes, cpu_seconds, actual_guard):
        try:
            require(supervisor._child_run_python is prefix and original.__code__ is original_code and
                    original.__globals__ is supervisor.__dict__, 'held child callable changed')
            require(os.getpid() != parent_pid and os.getppid() == parent_pid, 'not the exact direct child')
            require(os.getresuid() == (0,)*3 and os.getresgid() == (0,)*3, 'child pre-drop root IDs differ')
            require(type(argv) is tuple and argv == expected_argv and str(actual_cwd) == expected_cwd and
                    type(uid) is int and type(gid) is int and uid == gid == 65534 and
                    type(file_size_bytes) is int and file_size_bytes == 512*MIB and
                    type(cpu_seconds) is int and cpu_seconds == 240 and actual_guard is guard,
                    'fixed child arguments/guard differ')
            require(all(type(fd) is int and fd >= 3 for fd in (stdout_fd, stderr_fd, null_fd)) and
                    len({stdout_fd, stderr_fd, null_fd}) == 3, 'child pipe/null descriptors differ')
            require(stat.S_ISFIFO(os.fstat(stdout_fd).st_mode) and stat.S_ISFIFO(os.fstat(stderr_fd).st_mode) and
                    stat.S_ISCHR(os.fstat(null_fd).st_mode), 'child descriptors are not actual pipes/null')
            require(resource.getrlimit(resource.RLIMIT_CPU) == (60, 60) and
                    resource.getrlimit(resource.RLIMIT_FSIZE) == (512*MIB, 512*MIB), 'inherited fixed limits differ')
            with open('/proc/self/status', 'rb') as stream:
                raw = stream.read(65537)
            require(len(raw) <= 65536, 'capability status bound')
            fields = dict(line.split(b':', 1) for line in raw.splitlines())
            require(int(fields[b'CapEff'].strip(), 16) & (1 << 24), 'CAP_SYS_RESOURCE is absent')
            resource.setrlimit(resource.RLIMIT_CPU, (240, 240))
            require(resource.getrlimit(resource.RLIMIT_CPU) == (240, 240), 'child hard-limit handoff failed')
            original(argv, uid, gid, actual_cwd, stdout_fd, stderr_fd, null_fd, file_size_bytes, cpu_seconds, actual_guard)
        except BaseException:
            os._exit(125)
        os._exit(125)  # Unexpected original return must never unwind parent owners.
    return prefix


def launch_once(helpers, worker, attempt, fd, *, parent_pid=None):
    import resource
    supervisor = helpers['context_preparation_supervisor']
    original = helpers['child_original']
    prefix = child_prefix(supervisor, original, parent_pid=os.getpid() if parent_pid is None else parent_pid,
        worker=worker, cwd=attempt, guard=helpers['context_preparation_process_guard'])
    supervisor._child_run_python = prefix
    try:
        return supervisor.run_single_process((str(worker), 'receipt-v1'), uid=65534, gid=65534,
            cwd=Path(attempt), workspace_fd=fd, file_size_bytes=512*MIB, cpu_seconds=240, wall_seconds=240)
    finally:
        supervisor._child_run_python = original
        require(resource.getrlimit(resource.RLIMIT_CPU) == (60, 60), 'parent hardCPU60 changed')


def admitted_run(admit, prepare, launch):
    owner = admit()  # Never enters either action on rejection.
    try:
        owner.assert_admitted()
        prepare(owner)
        owner.assert_admitted()
        result = launch(owner)
        owner.assert_admitted()
        return result
    finally:
        owner.close()  # Unchanged Task60; failed close is not success/recovery.


def write_new(c, path, raw, cap, mode=0o444):
    require(type(raw) is bytes and len(raw) <= cap, 'exact output/control cap')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        c['write_all'](fd, raw)
        os.fsync(fd)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def copy_exact(c, source, target, entry):
    with c['old']()['opened'](source) as (src, before):
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == entry['size'], 'streaming source type/size')
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            checksum, total = hashlib.sha256(), 0
            while block := os.read(src, min(MIB, entry['size'] + 1 - total)):
                total += len(block)
                require(total <= entry['size'], 'streaming source grew')
                checksum.update(block)
                c['write_all'](fd, block)
            require(total == entry['size'] and checksum.hexdigest() == entry['sha256'], 'streaming copy hash differs')
            os.fsync(fd)
            os.fchmod(fd, 0o444)
        finally:
            os.close(fd)
        directory = os.open(Path(target).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def native_data(result):
    value = dataclasses.asdict(result)
    for key, cap in (('stdout_prefix', 128*1024), ('stderr_prefix', 8192)):
        raw = getattr(result, key)
        value[key] = raw[:cap].hex()
        value[key + '_retained_size'] = len(raw)
        value[key + '_retained_sha256'] = hashlib.sha256(raw).hexdigest()
        value[key + '_truncated'] = len(raw) > cap
    return value


def check_space(*, free, total, occupied, backup_rollback_reserve):
    require(all(type(x) is int and x >= 0 for x in (free, total, occupied, backup_rollback_reserve)),
            'exact physical allocation counters required')
    require(total <= 8*GIB and occupied <= total, 'whole new job allocation exceeded')
    required = 4*GIB + total - occupied + backup_rollback_reserve
    require(free >= required, 'free plus outstanding and backup/rollback reserve unavailable')
    return required


def accept_result(c, result, manifest, progress, job):
    require(result.exit_code == 0 and result.stop_reason is None and result.kernel_readback is not None,
            'actual exit0/no-stop/guard readback required')
    require(result.peak_rss_bytes < GIB and result.child_cpu_ns <= 240*10**9 and
            result.elapsed_ns <= 240*10**9 and result.observed_output_bytes + len(progress) <= MIB,
            'native resource/output envelope differs')
    require(len(result.stdout_prefix) <= 128*1024 and len(result.stderr_prefix) <= 8192 and not result.stderr_prefix,
            'bounded complete successful pipes required')
    raw = result.stdout_prefix
    payload = c['decode'](raw)
    require(c['canonical'](payload) + b'\n' == raw, 'one complete canonical worker result required')
    c['shape'](payload, 'format plan_digest baseline_sha256 generator_sha256 driver_sha256 completed corpus phases progress cleanup')
    entries = {x['path']: x for x in manifest['code']}
    require(payload['format'] == 'betboy-native-receipt-diagnostic-result-v1' and
            payload['plan_digest'] == manifest['admission']['plan_digest'] and payload['baseline_sha256'] == c['BASELINE_SHA'] and
            payload['generator_sha256'] == c['PINS']['tests/context_growth_profile.py'] and
            payload['driver_sha256'] == entries[c['WORKER_NAME']]['sha256'] and type(payload['completed']) is int and
            payload['completed'] == 1024 and payload['cleanup'] == dict(source_closed=True, worker_finished=True), 'worker identities/cleanup differ')
    prefix = c['parse_progress'](progress)
    require(prefix['terminal'] and not prefix['incomplete_tail_bytes'] and not prefix['stack'] and
            payload['progress'] == dict(head=prefix['head'], count=len(prefix['frames'])), 'terminal durable progress differs')
    corpus = payload['corpus']
    c['shape'](corpus, 'path ledger_path source_sha256 output_sha256 ledger_sha256 source_inventory inventory submitted_observations new_contents new_receipts main_bytes ledger_bytes page_size encoding')
    require(all(type(corpus[k]) is int and corpus[k] == 1024 for k in ('submitted_observations', 'new_contents', 'new_receipts')),
            'actual corpus count differs')
    require(corpus['source_sha256'] == c['BASELINE_SHA'] and corpus['page_size'] == 4096 and corpus['encoding'] == 'UTF-8',
            'corpus source/profile differs')
    for key, slot, cap, sizekey, hashkey in (
        ('path', 'attempt/corpus/legacy-copy.sqlite', 512*MIB, 'main_bytes', 'output_sha256'),
        ('ledger_path', 'attempt/corpus/receipt-additions.bin', MIB, 'ledger_bytes', 'ledger_sha256')):
        require(corpus[key] == str(job / slot), 'physical result path differs')
        require(c['old']()['file_record'](job / slot, maximum=cap) ==
                dict(size=corpus[sizekey], sha256=corpus[hashkey]), 'physical terminal bytes differ')
    require(not os.path.lexists(job / 'attempt/corpus/legacy-copy.sqlite-journal'), 'terminal cleanup journal remains')
    for label, expected in (('source_inventory', c['TABLE_COUNTS']),
        ('inventory', dict(c['TABLE_COUNTS'], context_contents=101577, context_observations=101577))):
        inventory = corpus[label]
        c['shape'](inventory, 'format_version schema_digest tables value_bytes logical_digest')
        require(type(inventory['format_version']) is int and inventory['format_version'] == 1 and
                type(inventory['tables']) is list and len(inventory['tables']) == 6, 'inventory format/count shape')
        c['integer'](inventory['value_bytes'], 4*GIB)
        c['sha'](inventory['schema_digest']); c['sha'](inventory['logical_digest'])
        for table in inventory['tables']:
            c['shape'](table, 'name row_count value_bytes row_digest')
            c['integer'](table['row_count']); c['integer'](table['value_bytes'], 4*GIB); c['sha'](table['row_digest'])
        require([x['name'] for x in inventory['tables']] == sorted(expected), 'inventory ordering/unique membership differs')
        require({x['name']: x['row_count'] for x in inventory['tables']} == expected, 'complete inventory counts differ')
    old_tables = {x['name']: x for x in corpus['source_inventory']['tables']}
    require(corpus['source_inventory']['schema_digest'] == corpus['inventory']['schema_digest'], 'complete schema differs')
    for table in corpus['inventory']['tables']:
        if table['name'] not in ('context_contents', 'context_observations'):
            require(table == old_tables[table['name']], 'unchanged old physical inventory differs')
    require(type(payload['phases']) is list and len(payload['phases']) <= 64, 'bounded phase summary required')
    actual_returns = [x['body'] for x in prefix['frames'] if x['body']['event'] in ('end', 'fail')]
    require(len(payload['phases']) == len(actual_returns), 'phase summary membership differs')
    for summary, event in zip(payload['phases'], actual_returns):
        c['shape'](summary, 'phase occurrence inclusive_cpu_ns inclusive_wall_ns returned call_count call_cpu_ns call_wall_ns')
        require(summary['phase'] == event['phase'] and type(summary['occurrence']) is int and
                summary['occurrence'] == event['occurrence'] and type(summary['returned']) is bool and
                summary['returned'] == (event['event'] == 'end'), 'phase scalar identity differs')
        for key in ('inclusive_cpu_ns', 'inclusive_wall_ns'):
            c['integer'](summary[key])
        if summary['phase'] == 'append':
            require(type(summary['call_count']) is int and summary['call_count'] == 1024, 'actual append call count differs')
            c['integer'](summary['call_cpu_ns'], summary['inclusive_cpu_ns'])
            c['integer'](summary['call_wall_ns'], summary['inclusive_wall_ns'])
        else:
            require(summary['call_count'] is summary['call_cpu_ns'] is summary['call_wall_ns'] is None,
                    'only append has separate call accumulators')
    return payload


def custody_stop(exc, report):
    signal.setitimer(signal.ITIMER_REAL, 0)
    try:
        report(dict(status='operator-custody-required-NOT-complete', parent_pid=os.getpid(), child_pid=exc.pid,
                    owned_pidfd=exc.pidfd, retained_cpu_ns=300*10**9, native_pass=False))
    except BaseException:
        pass  # Report failure never discards the same unreaped PID/pidfd.
    while True:
        os.kill(os.getpid(), signal.SIGSTOP)
        try:
            try:
                if exc.pidfd is None:
                    os.kill(exc.pid, signal.SIGKILL)
                else:
                    signal.pidfd_send_signal(exc.pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            found, status, _usage = os.wait4(exc.pid, os.WNOHANG)
            if found == exc.pid and (os.WIFEXITED(status) or os.WIFSIGNALED(status)):
                if exc.pidfd is not None:
                    os.close(exc.pidfd)
                return
        except BaseException:
            continue


def main(argv):
    start, deadline = startup()
    args = arguments(argv)
    c = load_catalogue(globals().get('_REVIEWED_BOOTSTRAP'))
    old, sources = c['old'](), globals()['_REVIEWED_BOOTSTRAP']
    helpers = load_helpers(c, sources)
    supervisor = helpers['context_preparation_supervisor']
    supervisor._require_native_owner()
    def check_time(reserve=0):
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        require(start <= now < deadline - reserve*10**9, 'original parent deadline exhausted')
        return now
    def alarm(_signum, _frame):
        raise DiagnosticError('original parent wall deadline')
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, (deadline-check_time())/10**9)
    manifest_path, archive_path = Path(args['--manifest']), Path(args['--archive'])
    job, registry = Path(args['--directory']), Path(args['--registry'])
    manifest_raw = old['data_bytes'](manifest_path, 8*MIB, args['--manifest-sha256'])
    manifest = c['decode'](manifest_raw)
    require(c['canonical'](manifest) == manifest_raw, 'manifest bytes must be canonical')
    retained_path = Path(manifest['retained']['path'])
    retained_raw = old['data_bytes'](retained_path, 8*MIB, manifest['retained']['sha256'])
    runtime = c['runtime_observation']()
    installation = c['installation_observation'](runtime)
    c['validate_manifest'](manifest, args['--commit'], retained_raw=retained_raw, runtime=runtime, installation=installation)
    require(manifest['admission']['job_directory'] == str(job) and manifest['admission']['registry_directory'] == str(registry), 'CLI namespace differs')
    inputs = {x['path']: x['cap'] for x in manifest['allocation']['inputs']}
    require(inputs.get(str(manifest_path)) == 8*MIB and inputs.get(str(archive_path)) == manifest['archive']['size'], 'CLI controls differ')
    require(c['digest'](c['bootstrap_source'](sources)) == args['--launcher-sha256'], 'Root-pinned executing stdin differs')
    archive_raw = old['data_bytes'](archive_path, 64*MIB, manifest['archive']['sha256'])
    members = old['archive_members'](archive_raw, manifest['code'])
    require(all(members[name] == raw for name, raw in sources.items()), 'executed held sources differ from actual archive')
    c['protected'](job, directory=True, searchable=True)
    c['protected'](registry, directory=True)
    require(not list(job.iterdir()) and not list(registry.iterdir()), 'fixed first diagnostic empty registry/job required')
    c['validate_retained'](retained_raw, observe=True)
    plan = manifest['allocation']
    root_info = job.lstat()
    held = ExitStack()
    owner = None
    parsed = None
    try:
        admitted_inputs = []
        for item in plan['inputs']:
            path = Path(item['path'])
            fd, info = held.enter_context(old['opened'](path))
            record = old['file_record'](path, maximum=item['cap'])
            admitted_inputs.append((path, fd, info, record))
        require(old['walk'](Path(manifest['dependency_root']), tuple(manifest['packages'])) == manifest['dependencies'], 'complete dependencies differ')
        c['protected'](Path(c['BASELINE_PATH']))
        require(old['file_record'](Path(c['BASELINE_PATH']), maximum=270233600) ==
                dict(size=270233600, sha256=c['BASELINE_SHA']), 'actual baseline bytes differ')
        usage = os.statvfs(job)
        check_space(free=usage.f_bavail*usage.f_frsize, total=plan['total'], occupied=0,
                    backup_rollback_reserve=plan['backup_rollback_reserve'])
        identity = helpers['context_preparation_budget'].BudgetIdentity(**manifest['admission']['identity'])
        owner = helpers['admission']['admit_diagnostic'](str(registry), identity=identity,
            purpose=manifest['admission']['purpose'], profile_kind='atp-heavy',
            plan_digest=manifest['admission']['plan_digest'], job_directory=str(job), retained_history_digest=c['digest'](retained_raw))
        owner.assert_admitted()
        snapshot = owner.snapshot()
        deadline = min(deadline, snapshot['binding']['deadline_boot_ns'])
        def write(name, raw):
            owner.assert_admitted(); check_time()
            write_new(c, job / name, raw, plan['slots'][name])
            owner.assert_admitted()
        def recheck():
            owner.assert_admitted(); check_time()
            require(c['runtime_observation']() == runtime and c['installation_observation'](runtime) == installation,
                    'runtime/installation identity drift')
            require((job.lstat().st_dev, job.lstat().st_ino) == (root_info.st_dev, root_info.st_ino), 'held job changed')
            for path, fd, info, record in admitted_inputs:
                require(old['identity'](info) == old['identity'](os.fstat(fd)) == old['identity'](path.lstat()), 'held active input epoch changed')
                require(old['file_record'](path, maximum=inputs[str(path)]) == record, 'held active input bytes changed')
            observed = c['sample_exact_slots'](job, plan['slots'], plan['metadata_cap'])
            observed_files = {x['path']: x for x in observed['files']}
            for prefix, entries in (('code', manifest['code']), ('dependencies', manifest['dependencies']),
                                    ('runtime-data/zoneinfo', manifest['timezone_data'])):
                for item in entries:
                    key = prefix + '/' + item['path']
                    require(key in observed_files and all(observed_files[key][k] == item[k] for k in ('size', 'sha256')),
                            'sealed execution copy differs')
                    info = (job / key).lstat()
                    require(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o444, 'execution copy root seal differs')
            reg = c['sample_exact_slots'](registry, plan['registry_slots'], plan['registry_metadata_cap'])
            occupied = observed['allocated'] + reg['allocated']
            require(max(observed['logical'] + reg['logical'], occupied) <= plan['total'], 'whole new job allocation exceeded')
            usage = os.statvfs(job)
            check_space(free=usage.f_bavail*usage.f_frsize, total=plan['total'], occupied=occupied,
                        backup_rollback_reserve=plan['backup_rollback_reserve'])
            owner.assert_admitted()
            return observed
        # Every allocation/copy follows actual durable Task60 admission.
        write('catalogue.json', manifest_raw)
        write('archive.tar', archive_raw)
        write('plan.json', c['canonical'](plan))
        for prefix, entries in (('code', manifest['code']), ('dependencies', manifest['dependencies']),
                                ('runtime-data/zoneinfo', manifest['timezone_data'])):
            for item in entries:
                owner.assert_admitted(); check_time(255)
                target = job / prefix / item['path']
                target.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
                if prefix == 'code':
                    write_new(c, target, members[item['path']], item['size'])
                else:
                    source = Path(manifest['dependency_root']) / item['path'] if prefix == 'dependencies' else Path(item['source'])
                    copy_exact(c, source, target, item)
                owner.assert_admitted()
        (job / 'baseline').mkdir(mode=0o755)
        copy_exact(c, Path(c['BASELINE_PATH']), job / 'baseline/context-current.db', manifest['baseline'])
        owner.assert_admitted()
        attempt = job / 'attempt'
        attempt.mkdir(mode=0o700)
        (attempt / 'corpus').mkdir(mode=0o700)
        os.chown(attempt / 'corpus', 65534, 65534)
        os.chown(attempt, 65534, 65534)
        recheck(); check_time(255)
        fd = os.open(attempt, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                result = launch_once(helpers, job / 'code/tests/native_context_receipt_diagnostic_worker.py', attempt, fd)
            except supervisor.UnreapedChild as exc:
                custody_stop(exc, lambda data: write_new(c, job / 'custody.json', c['canonical'](data), MIB))
                raise
        finally:
            os.close(fd)
        # Retain actual terminal result before progress/success parsing.
        write_new(c, job / 'native-result.json', c['canonical'](native_data(result)), MIB)
        write_new(c, job / 'stdout.bin', result.stdout_prefix[:128*1024], 128*1024)
        write_new(c, job / 'stderr.bin', result.stderr_prefix[:8192], 8192)
        progress_path = attempt / 'progress.jsonl'
        progress = b''
        if os.path.lexists(progress_path):
            record = old['file_record'](progress_path, maximum=262144)
            progress = old['data_bytes'](progress_path, 262144, record['sha256'])
        parsed = c['parse_progress'](progress)
        c['validate_retained'](retained_raw, observe=True)
        observed = recheck()
        payload = accept_result(c, result, manifest, progress, job)
        owner.assert_admitted()
        owner.close()
        owner = None
        report = dict(status='complete-external-terminal-observation-required', native_pass=False,
            retained_cpu_ns=300*10**9, parent_start_boot_ns=start, parent_end_boot_ns=check_time(),
            parent_whole_cpu_ns=time.process_time_ns(), progress=parsed, worker=payload,
            inventory_sha256=c['digest'](c['canonical'](observed)))
        write_new(c, job / 'report.json', c['canonical'](report), MIB)
        return 0
    except BaseException as exc:
        if owner is not None:
            try:
                write_new(c, job / 'failure.json', c['canonical'](dict(status='STOP', native_pass=False,
                    exception=type(exc).__name__, retained_cpu_ns=300*10**9, cleanup='retain-all-no-retry',
                    progress=None if parsed is None else {k:v for k,v in parsed.items() if k != 'frames'})), MIB)
            except BaseException:
                pass  # Charge remains in unchanged durable owner even if report I/O fails.
        raise
    finally:
        try:
            if owner is not None:
                owner.close()
        finally:
            held.close()


def native_prefix_test(mode, *, root=PREFIX_ROOT):
    """Root-provisioned test-only entry. Never called by diagnostic main."""
    startup()
    require(mode in ('success', 'failure') and root == PREFIX_ROOT, 'fixed native prefix QA namespace required')
    c = load_catalogue(globals().get('_REVIEWED_BOOTSTRAP'))
    helpers = load_helpers(c, globals()['_REVIEWED_BOOTSTRAP'])
    helpers['context_preparation_supervisor']._require_native_owner()
    directory = Path(root)
    c['protected'](directory, directory=True, searchable=True)
    worker, work = directory / 'probe.py', directory / mode
    c['protected'](worker, searchable=True)
    require(c['old']()['file_record'](worker) == dict(size=len(PROBE_SOURCE), sha256=c['digest'](PROBE_SOURCE)), 'fixed probe seal bytes differ')
    info = work.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 65534 and
            stat.S_IMODE(info.st_mode) == 0o700 and not list(work.iterdir()), 'fresh native private probe directory required')
    fd = os.open(work, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    cleanup_read, cleanup_write = os.pipe()
    parent_pid = os.getpid()
    try:
        try:
            try:
                result = launch_once(helpers, worker, work, fd, parent_pid=parent_pid + (1 if mode == 'failure' else 0))
            except helpers['context_preparation_supervisor'].UnreapedChild as exc:
                custody_stop(exc, lambda data: os.write(2, c['canonical'](data) + b'\n'))
                raise
        finally:
            # A child unwinding into this inherited owner would write its PID.
            os.write(cleanup_write, (str(os.getpid()) + '\n').encode('ascii'))
    finally:
        os.close(fd)
        os.close(cleanup_write)
    try:
        cleanup_raw = os.read(cleanup_read, 128)
    finally:
        os.close(cleanup_read)
    cleanup_pids = [int(line) for line in cleanup_raw.splitlines()]
    require(cleanup_pids == [parent_pid], 'native child unwound inherited owner cleanup')
    import resource
    output = native_data(result)
    output.update(parent_cpu=list(resource.getrlimit(resource.RLIMIT_CPU)), native_pass=False,
                  external_terminal_observation_required=True, owner_cleanup_pids=cleanup_pids, parent_pid=parent_pid)
    require(result.exit_code == (0 if mode == 'success' else 125), 'native prefix terminal exit differs')
    if mode == 'success':
        require(result.stop_reason is None and result.kernel_readback is not None and
                result.kernel_readback.cpu_seconds == 240, 'actual stopped child guard readback required')
    return output


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
