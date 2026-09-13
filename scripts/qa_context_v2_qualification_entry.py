"""One fixed whole V2 qualification, including input setup in the same process.

The sender substitutes only exact committed code and existing audit metadata.
All old namespaces remain intact; production code/services are never modified.
"""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (512*1024**2, 512*1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile

revision = "SOURCE_REVISION"
archive_sha = "ARCHIVE_SHA256"
archive_raw = base64.b64decode("ARCHIVE_BASE64", validate=True)
known_raw = base64.b64decode("KNOWN_JOURNALS_BASE64", validate=True)
prior_raw = base64.b64decode("PRIOR_ROOTS_BASE64", validate=True)
assert len(archive_raw) <= 64*1024**2 and hashlib.sha256(archive_raw).hexdigest() == archive_sha
assert len(known_raw) <= 262144 and hashlib.sha256(known_raw).hexdigest() == "KNOWN_JOURNALS_SHA256"
assert len(prior_raw) <= 262144 and hashlib.sha256(prior_raw).hexdigest() == "PRIOR_ROOTS_SHA256"
assert os.getresuid() == os.getresgid() == (0,)*3
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
os.umask(0o022)

base_names = ('tests/native_context_receipt_diagnostic.py', 'tests/native_context_receipt_diagnostic_catalogue.py',
              'tests/native_context_chain_catalogue.py', 'tests/native_context_diagnostic_admission.py',
              'context_preparation_process_guard.py', 'context_preparation_budget.py', 'context_preparation_supervisor.py')
qa_names = (*base_names, 'tests/native_context_qa_coordinator.py', 'tests/native_context_qa_budget.py')
sources = {}
with tarfile.open(fileobj=io.BytesIO(archive_raw), mode='r:') as archive:
    assert archive.pax_headers.get('comment') == revision
    for index, member in enumerate(archive):
        assert index < 30000
        if member.name in qa_names:
            assert member.isreg() and member.name not in sources and 0 < member.size <= 1024**2
            with archive.extractfile(member) as stream:
                data = stream.read(member.size+1)
            assert len(data) == member.size
            sources[member.name] = data
assert set(sources) == set(qa_names)
parent = dict(__name__='_qualification_setup_parent', __file__='<held-qualification-setup-parent>')
exec(compile(sources[base_names[0]], parent['__file__'], 'exec'), parent)
c = parent['load_catalogue']({name: sources[name] for name in base_names})
coordinator = dict(__name__='_qualification_setup_coordinator', __file__='<held-qualification-setup-coordinator>')
exec(compile(sources['tests/native_context_qa_coordinator.py'], coordinator['__file__'], 'exec'), coordinator)

known = json.loads(known_raw)['journals']
prior = {item['path'] for item in json.loads(prior_raw)['roots']}
assert len(known) == 16 and len(prior) == 85
paths = coordinator['selected_history']()
assert prior <= set(paths) and all(item['root'] in paths for item in known)
fifo_path = Path(c['HISTORICAL_FIFO'])
def metadata(path):
    info = path.lstat()
    return dict(path=str(path), identity=list(c['old']()['identity'](info)), allocated=c['_allocation'](info))
fifo = metadata(fifo_path)
fifo['ancestors'] = [metadata(path) for path in fifo_path.parents if path.is_relative_to(c['HISTORICAL_FIFO_ROOT'])]
c['validate_historical_fifo'](fifo, observe=True)
roots = []
journal_keys = ('path', 'identity', 'journal_head', 'ticket', 'state', 'charged_cpu_ns', 'settled_cpu_ns', 'category')
for path in paths:
    roots.append(dict(path=path, identity=list(c['old']()['identity'](Path(path).lstat())),
        category='backup' if path.startswith(('/var/backups/', '/var/lib/betboy-live-backup-')) else 'historical-qa',
        charged_cpu_ns=None,
        journals=sorted(({key: item[key] for key in journal_keys} for item in known if item['root'] == path), key=lambda item:item['path'])))
prior_qa_path = Path(coordinator['PRIOR_REGISTRY'])/c['QA_JOURNAL']
prior_qa_record = c['old']()['file_record'](prior_qa_path, maximum=1024**2)
prior_qa = c['old']()['data_bytes'](prior_qa_path, 1024**2, prior_qa_record['sha256'])
request = dict(format='betboy-context-qa-request-v2', authorization=coordinator['AUTHORIZATION'],
    commit=revision, archive=dict(path=coordinator['INPUT']+'/code.tar', size=len(archive_raw), sha256=archive_sha),
    roots=roots, historical_fifo=fifo,
    previous_costs=dict(primary_reserved_cpu_ns=1680*10**9, synthetic_reserved_cpu_ns=600*10**9,
                        unjournaled_cpu_ns=None, evidence_sha256=hashlib.sha256(known_raw).hexdigest(),
                        prior_qa_reserved_cpu_ns=900*10**9, prior_qa_journal_sha256=hashlib.sha256(prior_qa).hexdigest()))
coordinator['validate_request'](c, request)
request_raw = c['canonical'](request)
assert len(request_raw) <= 1024**2 and paths == coordinator['selected_history']()
# There is no alternate name or overwrite path if any part of this one-shot
# namespace exists. The same process's original kernel start covers this setup.
destinations = [Path(coordinator[name]) for name in ('INPUT', 'REGISTRY', 'JOB')]
for path in destinations:
    c['protected'](path.parent, directory=True)
    assert path.parent == Path('/var/lib') and not os.path.lexists(path)
for path in destinations:
    path.mkdir(mode=0o700 if str(path) == coordinator['REGISTRY'] else 0o755)
parent['write_new'](c, destinations[0]/'code.tar', archive_raw, 64*1024**2)
parent['write_new'](c, destinations[0]/'request.json', request_raw, 1024**2)
print('QA inputs bound; roots='+str(len(roots))+'; source='+revision, flush=True)
bootstrap = coordinator['bootstrap_source'](sources, c['BOOTSTRAP'])
sys.argv = ['<held-qa-v2>', '--request', str(destinations[0]/'request.json'), '--request-sha256', c['digest'](request_raw)]
exec(compile(bootstrap, '<held-qa-v2-bootstrap>', 'exec'), {'__name__': '__main__', '__file__': '<held-qa-v2-bootstrap>'})
