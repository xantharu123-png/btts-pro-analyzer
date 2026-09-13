"""Fixed isolated native QA transport template; not imported by the app.

The local sender substitutes the held Git archive, revision, digest and mode.
Neither mode reads production databases/secrets or creates real QA admission.
"""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (64*1024**2, 64*1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import subprocess
import sys
import tarfile
import time

revision = "SOURCE_REVISION"
expected_sha = "ARCHIVE_SHA256"
mode = "NATIVE_MODE"
raw = base64.b64decode("ARCHIVE_BASE64", validate=True)
assert mode in ('portable-native', 'root-process')
assert len(revision) == 40 and len(raw) <= 2*1024**2 and hashlib.sha256(raw).hexdigest() == expected_sha
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
expected_uid = 1000 if mode == 'portable-native' else 0
assert os.getresuid() == os.getresgid() == (expected_uid,)*3
members = {}
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
    assert archive.pax_headers.get('comment') == revision
    for index, member in enumerate(archive):
        assert index < 64
        if member.isdir():
            continue
        name = PurePosixPath(member.name)
        assert member.isreg() and str(name) == member.name and not name.is_absolute() and '..' not in name.parts
        assert member.name not in members and member.name.endswith('.py') and 0 < member.size <= 1024**2
        with archive.extractfile(member) as stream:
            data = stream.read(member.size+1)
        assert len(data) == member.size
        members[member.name] = data

# Validate the immutable helper pins before even creating a test directory.
# A transport line-ending conversion must fail here, not inside a FIFO fixture.
parent = dict(__name__='_root_unit_parent', __file__='<held-root-unit-parent>')
exec(compile(members['tests/native_context_receipt_diagnostic.py'], parent['__file__'], 'exec'), parent)
base_names = ('tests/native_context_receipt_diagnostic.py', 'tests/native_context_receipt_diagnostic_catalogue.py',
              'tests/native_context_chain_catalogue.py', 'tests/native_context_diagnostic_admission.py',
              'context_preparation_process_guard.py', 'context_preparation_budget.py', 'context_preparation_supervisor.py')
c = parent['load_catalogue']({name: members[name] for name in base_names})

root = Path('/tmp' if expected_uid else '/var/lib') / ('betboy-context-qav2-unit-'+revision[:7]+'-'+mode+'-01')
assert root.parent.resolve() == root.parent and not os.path.lexists(root)
os.umask(0o077)
root.mkdir(mode=0o700)


def write(path, data):
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            assert count > 0
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


write(root/'source.tar', raw)
started = time.monotonic_ns()
if mode == 'portable-native':
    for name, data in members.items():
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, data)
    code = ('import sys; sys.path.insert(0,'+repr(str(root))+'); '
            'sys.path.insert(0,'+repr(str(root/'tests'))+'); import pytest; '
            'raise SystemExit(pytest.main('+repr([
                '--noconftest', '-q', '-p', 'no:cacheprovider', '--tb=short', '--maxfail=2',
                '--basetemp='+str(root/'fixtures'), '--junitxml='+str(root/'result.xml'),
                'tests/test_native_context_qa_budget.py', 'tests/test_native_context_qa_retained_v2.py',
                'tests/test_native_context_qa_coordinator.py'])+'))')
    result = subprocess.run(['/tmp/betboy-context-qa.9xr68INa/venv/bin/python', '-I', '-B', '-c', code],
        cwd=root, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'},
        capture_output=True, timeout=100)
    assert len(result.stdout)+len(result.stderr) <= 1024**2
    write(root/'stdout.log', result.stdout); write(root/'stderr.log', result.stderr)
    output = dict(mode=mode, source_revision=revision, exit_code=result.returncode,
                  stdout=result.stdout.decode('utf-8', errors='replace'), stderr=result.stderr.decode('utf-8', errors='replace'))
else:
    helpers = parent['load_helpers'](c, {name: members[name] for name in base_names})
    module = dict(__name__='_root_unit_coordinator', __file__='<held-root-unit-coordinator>')
    exec(compile(members['tests/native_context_qa_coordinator.py'], module['__file__'], 'exec'), module)
    results = []
    for fault in ('none', 'exception', 'empty', 'oversize', 'wall', 'cpu'):
        read_fd, write_fd = os.pipe()
        def action(*_args):
            try:
                os.fstat(write_fd)
            except OSError:
                pass
            else:
                raise AssertionError('owner descriptor inherited')
            if fault == 'exception': raise ValueError('injected unit fault')
            if fault == 'empty': return b''
            if fault == 'oversize': return b'x'*(8*1024**2+1)
            if fault == 'wall': time.sleep(10)
            if fault == 'cpu':
                while True:
                    pass
            return b'{"actual":true}'
        module['_scanner_action'] = action
        try:
            deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME)+(1 if fault == 'wall' else 8)*10**9
            try:
                data, result = module['run_scanner']('A1', c, {}, None, allowance=1,
                    deadline=deadline, supervisor=helpers['context_preparation_supervisor'])
            except module['ScannerStopped'] as exc:
                assert fault != 'none' and exc.measurement['child_exit_code'] is not None
                assert exc.measurement['child_cpu_ns'] is not None
                result = dict(status='expected-stop', measurement=exc.measurement)
            else:
                assert fault == 'none' and data == b'{"actual":true}' and result['child_exit_code'] == 0
            try:
                os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                pass
            else:
                raise AssertionError('child custody remains')
            results.append(dict(case=fault, result=result))
        finally:
            os.close(read_fd); os.close(write_fd)
    output = dict(mode=mode, source_revision=revision, exit_code=0, cases=results)
output.update(qa_directory=str(root), total_wall_ns=time.monotonic_ns()-started,
              parent_cpu_ns=time.process_time_ns(), child_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+
              resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
              application_changed=False, real_diagnostic_admitted=False)
encoded = json.dumps(output, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
write(root/'result.json', encoded)
print(encoded.decode('ascii'), flush=True)
raise SystemExit(output['exit_code'])
