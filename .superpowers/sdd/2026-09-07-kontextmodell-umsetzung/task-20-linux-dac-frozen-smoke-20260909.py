"""REVIEWED-DRAFT ONLY: fixed synthetic Linux DAC smoke, never an updater.

No caller-selected paths, installation, service control, real keys or cleanup.
The controller must read/hash this script before any privileged execution.
Root imports stdlib only; archived application/fixture code runs as betboy only.
"""
import ast
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import signal
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

QA = Path('/tmp/betboy-context-qa.9xr68INa')
SOURCE = QA / 'context-hook-linux-a224d13.tar'
IMAGE = QA / ('hook-fixtures-2346846-20260909/.pytest_tmp/'
    'hook-linux-unprivileged-fixtures-02/test_wal_online_backup_then_re0/private/image.db')
ARCHIVE_SIZE = 101335040
ARCHIVE_HASH = 'e76488f9a34ca8544667411151bac6e69ab275ccad4d6079c47a2051cf83492f'
IMAGE_HASH = '66ee78e58b4b70fb33b0f70f8b7995ac220025ef2c5bc8f34c273dfa5cfe6c09'
HOOK_HASH = '74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f'
HELPERS_HASH = '71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62'
REVISION = 'a224d136d232ecc16e7f4b0a3341518efb54906a'
VENV = '/opt/betboy/venv/bin/python'
UID, GID = 997, 987
MAX_IMAGE, MAX_OUTPUT = 64 * 1024 * 1024, 1024 * 1024
HELPERS = {'model_event', 'effect_payload', 'add_receipt', 'add_context_snapshot'}
STDLIB = {'hashlib', 'json', 'os', 'pathlib', 're', 'sqlite3', 'stat', 'sys',
           'zipfile', 'shutil', 'tempfile'}


def need(ok, label):
    if not ok:
        raise RuntimeError(label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(st):
    # Deliberately exclude atime; reads themselves may update it.
    return [st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid, st.st_nlink,
            st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def no_links(path):
    for part in [path, *path.parents]:
        need(not stat.S_ISLNK(part.lstat().st_mode), 'symlink in fixed input path')


def read_stable(path, limit, *, owner, expected=None, size=None):
    no_links(path)
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_uid == owner and st.st_nlink == 1,
         'input owner/type/link mismatch')
    need(st.st_size <= limit and (size is None or st.st_size == size), 'input size mismatch')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(identity(os.fstat(fd)) == identity(st), 'input replaced before read')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        need(len(raw) <= limit and identity(os.fstat(fd)) == identity(st)
             and identity(path.lstat()) == identity(st), 'input changed during read')
        need(expected is None or digest(raw) == expected, 'input hash mismatch')
        return raw, identity(st)
    finally:
        os.close(fd)


def create(path, raw, *, uid=0, gid=0, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchown(fd, uid, gid)
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdir(path, *, uid=0, gid=0, mode=0o700):
    path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def inventory(archive):
    """Validate every TAR header before creating any source member."""
    members, names, total = [], set(), 0
    for item in archive.getmembers():
        name = item.name[:-1] if item.isdir() and item.name.endswith('/') else item.name
        pure = PurePosixPath(name)
        need(name and pure.parts and pure.as_posix() == name and not pure.is_absolute()
             and '..' not in pure.parts and '.' not in pure.parts
             and '\\' not in name and ':' not in name
             and all(ord(c) >= 32 for c in name), 'unsafe TAR name')
        need(name not in names and (item.isdir() or item.isreg())
             and not item.linkname and not item.issparse(), 'duplicate/link/special TAR member')
        need(not item.mode & 0o7000 and 0 <= item.size <= ARCHIVE_SIZE, 'unsupported TAR mode/size')
        names.add(name)
        members.append((name, item))
        total += item.size
        need(total <= ARCHIVE_SIZE and len(members) <= 20000, 'TAR inventory limit')
    files = {name for name, item in members if item.isreg()}
    need(not any(parent.as_posix() in files for name in names
                 for parent in PurePosixPath(name).parents if parent.as_posix() != '.'),
         'TAR file/directory collision')
    return members


def stage(archive_path, target):
    manifest = {'revision': REVISION, 'must_be_absent': [], 'files': {}}
    with tarfile.open(archive_path, 'r:') as archive:
        entries = inventory(archive)
        dirs = {p.as_posix() for name, _ in entries for p in PurePosixPath(name).parents
                if p.as_posix() != '.'} | {n for n, m in entries if m.isdir()}
        for name in sorted(dirs, key=lambda n: (len(PurePosixPath(n).parts), n)):
            mkdir(target / name, gid=GID, mode=0o750)
        for name, item in entries:
            if item.isdir():
                continue
            with archive.extractfile(item) as stream:
                raw = stream.read(item.size + 1)
            need(len(raw) == item.size, 'short TAR source member')
            create(target / name, raw, gid=GID, mode=0o640)
            manifest['files'][name] = {'mode': '100755' if item.mode & 0o111 else '100644',
                                       'sha256': digest(raw)}
    return manifest


def shell_function(text, name):
    marker = name + '() {\n'
    need(text.count(marker) == 1, 'missing/ambiguous pinned function')
    selected, heredoc = [], None
    for line in text[text.index(marker):].splitlines(keepends=True):
        selected.append(line)
        if heredoc is not None:
            if line == heredoc + '\n':
                heredoc = None
            continue
        match = re.search(r"<<'([^']+)'", line)
        if match:
            heredoc = match[1]
        elif line == '}\n':
            return ''.join(selected)
    raise RuntimeError('unterminated pinned function')


def inline(function):
    need(function.count("<<'PY'\n") == 1, 'ambiguous pinned inline body')
    body = function.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    for node in ast.walk(ast.parse(body)):
        modules = ([a.name.split('.')[0] for a in node.names] if isinstance(node, ast.Import)
                   else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) else [])
        need(set(modules) <= STDLIB, 'privileged non-stdlib import')
    return body


def fixture_builder(source):
    """Extract only four unchanged pinned helpers; never execute them as root."""
    need(digest(source) == HELPERS_HASH, 'fixture helper source drift')
    lines = source.decode().splitlines(keepends=True)
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in HELPERS]
    need({n.name for n in nodes} == HELPERS, 'fixture helper inventory differs')
    return BUILDER_IMPORTS + '\n'.join(''.join(lines[n.lineno - 1:n.end_lineno]) for n in nodes) + BUILDER_MAIN


BUILDER_IMPORTS = '''import os, sys, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing
assert os.geteuid() == 997 and os.getegid() == 987 and os.getgroups() == [987]
source, sealed, scratch = map(Path, sys.argv[1:4])
os.environ["HOME"] = str(scratch)
os.environ["TMPDIR"] = str(scratch)
sys.path.insert(0, str(source))
from context_observations import append_observation
from context_snapshots import compute_once, select_context_result, snapshot_key
from context_models.contracts import digest
from model_artifacts import put_artifact, load_manifest
NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
'''
BUILDER_MAIN = '''
for variant in ("transport", "broken"):
    path = scratch / (variant + ".db")
    with path.open("xb") as stream:
        stream.write(sealed.read_bytes())
    path.chmod(0o600)
    if variant == "transport":
        effect = effect_payload()
        ref = put_artifact(path, kind="context-effect-v1", payload=effect, created_at=NOW)
        add_context_snapshot(path, ref, effect)
    else:
        _, slots = load_manifest(path)
        with closing(sqlite3.connect(path)) as connection, connection:
            cursor = connection.execute("DELETE FROM artifacts WHERE digest=?", (slots["tennis:ATP"],))
            assert cursor.rowcount == 1
    assert not any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
print("fixture-builder-v1:ok")
'''

DAC_PROBE = '''import errno, json, os, sys
from pathlib import Path
image, scratch, *private = map(Path, sys.argv[1:])
assert os.geteuid() == 997 and os.getegid() == 987 and os.getgroups() == [987]
assert image.read_bytes()[:16] == b"SQLite format 3\\0"
control = scratch / "positive-write-control"
with control.open("xb") as stream: stream.write(b"fixture-only")
control.chmod(0o600)
assert control.read_bytes() == b"fixture-only"
control.unlink()
replacement = scratch / "replacement-control"
with replacement.open("xb") as stream: stream.write(b"fixture-only")
def append():
    with image.open("ab") as stream: stream.write(b"forbidden")
def sidecar(suffix):
    with Path(str(image)+suffix).open("xb") as stream: stream.write(b"forbidden")
actions = [("write", append), ("chmod", lambda: image.chmod(0o660)),
    ("unlink", image.unlink), ("replace", lambda: os.replace(replacement, image)),
    ("hardlink", lambda: os.link(image, scratch/"forbidden-hardlink"))]
actions += [("sidecar"+suffix, lambda suffix=suffix: sidecar(suffix)) for suffix in ("-wal", "-shm", "-journal")]
actions += [("private-read-"+str(i), path.read_bytes) for i, path in enumerate(private)]
denied = []
for label, action in actions:
    try: action()
    except OSError as exc:
        assert exc.errno in (errno.EACCES, errno.EPERM), (label, exc.errno)
        denied.append(label)
    else: raise AssertionError("DAC unexpectedly allowed "+label)
assert replacement.read_bytes() == b"fixture-only"
replacement.unlink()
print(json.dumps({"uid":os.geteuid(),"gid":os.getegid(),"groups":os.getgroups(),
    "read":True,"scratch_write":True,"denied":denied},sort_keys=True))
'''


def captured(command_function, as_function, output, argv, *, stdin=None):
    """Actual unchanged Bash functions, real runuser/env/timeout/head pipeline."""
    body = ('set -euo pipefail\numask 077\n'
            'die() { printf "%s\\n" "isolated DAC hook command failed" >&2; exit 91; }\n'
            + as_function + command_function + '\ncontext_hook_command '
            + ' '.join(shlex.quote(str(v)) for v in [output, *argv])
            + '\nprintf "%s\\n" "$CONTEXT_COMMAND_STATUS"\n')
    process = subprocess.Popen(['/usr/bin/env', '-i', 'PATH=/usr/sbin:/usr/bin:/sbin:/bin',
        'LANG=C.UTF-8', '/bin/bash', '--noprofile', '--norc', '-c', body],
        cwd='/', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True)
    try:
        out, err = process.communicate(stdin, timeout=630)
    except subprocess.TimeoutExpired:
        # Only this newly started process group; never look up production jobs.
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=10)
        raise RuntimeError('isolated harness outer timeout')
    need(process.returncode == 0 and not err and len(out) <= 16
         and re.fullmatch(rb'[0-9]{1,3}\n', out), 'invalid hook capture protocol')
    return int(out), process.pid


def no_fixture_children(sessions):
    # Popen created these exact new sessions. GNU timeout may create a nested
    # process group, so inspect session IDs, without reading any cmdlines.
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            fields = (entry/'stat').read_text().rsplit(')',1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        need(int(fields[3]) not in sessions, 'a fixture child survived its completed command')


def make_backup(path, raw, key):
    manifest = {'created_at':'2026-09-09T12:00:00+00:00','source_head':REVISION,'database_count':1,
        'databases':[{'path':'runtime_state/context_models.db','source_size':len(raw),
                      'backup_size':len(raw),'sha256':digest(raw)}],
        'integrity_key':{'path':'integrity/challenge-ledger-hmac.key','sha256':digest(key)}}
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name, data in [('MANIFEST.json',json.dumps(manifest).encode()),
            ('runtime_state/context_models.db',raw),('integrity/challenge-ledger-hmac.key',key)]:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, data)
    os.chown(path,0,0)
    os.chmod(path,0o600)


def full_verify(program, archive, private_tmp):
    previous_argv, previous_temp = sys.argv, tempfile.tempdir
    try:
        sys.argv = ['pinned-inline-backup-verifier', str(archive)]
        tempfile.tempdir = str(private_tmp)
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            exec(compile(program, 'pinned-verify-backup-inline', 'exec'), {'__name__':'fixed_backup_smoke'})
        need(not out.getvalue() and not err.getvalue(), 'unexpected backup verifier output')
    finally:
        sys.argv, tempfile.tempdir = previous_argv, previous_temp


def main():
    need(sys.platform == 'linux' and os.geteuid() == 0, 'Linux root execution required after review')
    import pwd
    need(len(sys.argv) == 1, 'fixed smoke takes no configurable arguments')
    os.umask(0o077)
    account = pwd.getpwnam('betboy')
    need((account.pw_uid,account.pw_gid) == (UID,GID)
         and sorted(set(os.getgrouplist('betboy',GID))) == [GID], 'app principal differs')
    need(Path('/proc/sys/fs/protected_hardlinks').read_text().strip() == '1', 'hardlink protection differs')
    no_links(QA)
    info = QA.lstat()
    need(info.st_uid == 1000 and info.st_gid == 1000 and stat.S_IMODE(info.st_mode) == 0o700,
         'original private QA directory differs')
    archive_raw, archive_id = read_stable(SOURCE, ARCHIVE_SIZE, owner=1000, expected=ARCHIVE_HASH, size=ARCHIVE_SIZE)
    image_raw, image_id = read_stable(IMAGE, MAX_IMAGE, owner=1000, expected=IMAGE_HASH, size=45056)
    need(image_raw[:16] == b'SQLite format 3\0' and image_raw[18:20] == b'\x02\x02', 'not the pinned real WAL backup')
    root = Path(tempfile.mkdtemp(prefix='betboy-context-dac-',dir='/tmp'))
    # A 0700 common ancestor would make the positive app read impossible.
    # This common ancestor is traverse-only; private root children stay 0700.
    os.chown(root,0,GID)
    os.chmod(root,0o710)
    private,target,scratch = root/'private',root/'source',root/'app-scratch'
    mkdir(private)
    mkdir(private/'verify-tmp')
    mkdir(target,gid=GID,mode=0o750)
    mkdir(scratch,uid=UID,gid=GID,mode=0o700)
    print(json.dumps({'phase':'created-synthetic-fixture','path':str(root)}),flush=True)
    source_copy=private/'source.tar'
    create(source_copy,archive_raw)
    source_copy_id=identity(source_copy.lstat())
    source_manifest=stage(source_copy,target)
    source_identities={name:identity((target/name).lstat()) for name in source_manifest['files']}
    del archive_raw
    manifest_path=private/'source-manifest.json'
    create(manifest_path,json.dumps(source_manifest,sort_keys=True).encode(),gid=GID,mode=0o640)
    hook=(target/'deploy/update_server.sh').read_bytes()
    need(digest(hook)==HOOK_HASH,'pinned updater source differs')
    hook=hook.decode()
    functions={n:shell_function(hook,n) for n in ('context_hook_data','verify_backup_archive','context_hook_command','as_betboy')}
    data={'__name__':'isolated_pinned_hook_data'}
    exec(compile(inline(functions['context_hook_data']),'pinned-hook-data','exec'),data)
    data['verify_payload'](target,manifest_path,REVISION,GID)
    backup_program=inline(functions['verify_backup_archive'])
    key=b'a1'*32+b'\n'  # Public synthetic test key; never read any installed key.
    key_path=private/'synthetic-ledger.key'
    create(key_path,key)
    cli=target/'scripts/verify_context_runtime.py'
    proofs={}
    sessions=set()
    def run(name,argv,stdin=None):
        output=private/(name+'.out')
        code,session=captured(functions['context_hook_command'],functions['as_betboy'],output,argv,stdin=stdin)
        sessions.add(session)
        no_fixture_children(sessions)
        return code,output
    def stage_variant(name,raw):
        archive=private/(name+'.zip')
        make_backup(archive,raw,key)
        archive_hash=data['file_hash'](archive)
        archive_sig=data['signature'](archive.lstat())
        full_verify(backup_program,archive,private/'verify-tmp')
        folder=root/('sealed-'+name)
        mkdir(folder,gid=GID,mode=0o750)
        sealed=folder/'context_models.db'
        proof=data['extract_and_seal'](archive,'runtime_state/context_models.db',sealed,
            source_head=REVISION,app_gid=GID)
        need(proof['member_hash']==digest(raw) and proof['archive_hash']==archive_hash
             and proof['archive_signature']==archive_sig,'sealed transport proof differs')
        proof.update(archive=str(archive),sealed=str(sealed),sealed_hash=data['file_hash'](sealed),
            sealed_signature=data['signature'](data['file_info'](sealed,owners={0},mode=0o440,gid=GID)))
        create(private/(name+'-receipt.json'),json.dumps(proof,sort_keys=True).encode())
        proofs[name]=proof
        return sealed
    def verify(name,sealed,expected):
        code,output=run(name,[VENV,'-I','-B',cli,'--database',sealed])
        need(code==expected,'unexpected actual CLI exit')
        value=data['decode'](data['read_file'](output,mode=0o600,maximum=MAX_OUTPUT))
        if expected in (0,2):
            data['validate_report'](value,code)
            need(value['empirical_approval_verified'] is False,'unexpected empirical certification')
        else:
            need(set(value)=={'status','error_type'} and value['status']=='failed'
                 and value['error_type']=='ArtifactIntegrityError','invalid missing-reference CLI result')
            try: data['validate_report'](value,code)
            except ValueError: pass
            else: raise RuntimeError('CLI1 was accepted as continuity')
        return value
    good=stage_variant('structural',image_raw)
    positive=verify('structural',good,0)
    need(set(positive['tour_states'])=={'ATP','WTA'} and positive['counts']['manifests']==1
         and positive['counts']['observations']==1,'real WAL fixture content did not survive')
    builder=fixture_builder((target/'tests/test_context_runtime_backup.py').read_bytes())
    create(private/'app-builder.py',builder.encode())
    code,output=run('fixture-builder',[VENV,'-I','-B','-',target,good,scratch],builder.encode())
    need(code==0 and data['read_file'](output,mode=0o600)==b'fixture-builder-v1:ok\n','app fixture builder failed')
    reports={'structural':positive}
    for name,expected in [('transport',2),('broken',1)]:
        raw,stamp=read_stable(scratch/(name+'.db'),MAX_IMAGE,owner=UID)
        sealed=stage_variant(name,raw)
        reports[name]=verify(name,sealed,expected)
        need(read_stable(scratch/(name+'.db'),MAX_IMAGE,owner=UID)[1]==stamp,'app fixture input changed')
    create(private/'dac-probe.py',DAC_PROBE.encode())
    code,output=run('dac-probe',[VENV,'-I','-B','-',good,scratch,source_copy,key_path,
        private/'structural.zip',private/'structural-receipt.json'],DAC_PROBE.encode())
    dac=data['decode'](data['read_file'](output,mode=0o600))
    need(code==0 and dac['uid']==UID and dac['gid']==GID and dac['groups']==[GID]
         and dac['read'] is True and dac['scratch_write'] is True and len(dac['denied'])==12,'DAC controls incomplete')
    # Real short GNU timeout inside the unchanged outer 600s/610s hook guards.
    code,output=run('tool-timeout',['/usr/bin/timeout','--signal=TERM','--kill-after=1s','1s',
        VENV,'-I','-B','-c','import time; time.sleep(30)'])
    need(code==124 and output.stat().st_size==0,'actual tool timeout not observed')
    try: data['validate_report'](positive,code)
    except ValueError: pass
    else: raise RuntimeError('timeout was accepted')
    code,output=run('tool-output',[VENV,'-I','-B','-c','import os; os.write(1,b"x"*(8*1024*1024))'])
    need(output.stat().st_size==MAX_OUTPUT+1,'actual head output boundary differs')
    try: data['read_file'](output,mode=0o600,maximum=MAX_OUTPUT)
    except ValueError: pass
    else: raise RuntimeError('oversized output was accepted')
    for proof in proofs.values():
        archive,sealed=Path(proof['archive']),Path(proof['sealed'])
        need(data['file_hash'](archive)==proof['archive_hash']
             and data['signature'](archive.lstat())==proof['archive_signature'],'private ZIP changed')
        need(data['file_hash'](sealed)==proof['sealed_hash']
             and data['signature'](data['file_info'](sealed,owners={0},mode=0o440,gid=GID))==proof['sealed_signature'],
             'sealed image identity/bytes changed')
        need(not any(Path(str(sealed)+s).exists() for s in ('-wal','-shm','-journal')),'sealed companions appeared')
    data['verify_payload'](target,manifest_path,REVISION,GID)
    need({name:identity((target/name).lstat()) for name in source_manifest['files']}==source_identities,
         'staged source file identities changed')
    need(data['file_hash'](source_copy)==ARCHIVE_HASH and identity(source_copy.lstat())==source_copy_id,
         'private source archive changed')
    need(read_stable(SOURCE,ARCHIVE_SIZE,owner=1000,expected=ARCHIVE_HASH,size=ARCHIVE_SIZE)[1]==archive_id,
         'original archive identity changed')
    need(read_stable(IMAGE,MAX_IMAGE,owner=1000,expected=IMAGE_HASH,size=45056)[1]==image_id,
         'original real WAL image identity changed')
    no_fixture_children(sessions)
    result={'status':'passed','scope':'synthetic Linux root/betboy DAC only; not installed A-to-B',
        'root':str(root),'uid':UID,'gid':GID,'hook_sha256':HOOK_HASH,'archive_sha256':ARCHIVE_HASH,
        'image_sha256':IMAGE_HASH,'reports':reports,'dac':dac,'timeout_exit':124,'bounded_output_bytes':MAX_OUTPUT+1,
        'function_sha256':{name:digest(body.encode()) for name,body in functions.items()},
        'source_manifest_sha256':data['file_hash'](manifest_path),
        'original_archive_identity':archive_id,'original_image_identity':image_id,
        'private_archive_identity':source_copy_id,
        'source_helper_sha256':HELPERS_HASH,'builder_sha256':digest(builder.encode()),'proofs':proofs}
    create(private/'RESULT.json',json.dumps(result,sort_keys=True).encode())
    print(json.dumps({'status':'passed','path':str(root),'result_sha256':data['file_hash'](private/'RESULT.json'),
        'scope':result['scope']},sort_keys=True))


if __name__=='__main__':
    try:
        main()
    except BaseException as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,
            'scope':'isolated synthetic smoke only; retain new fixture for inspection'},sort_keys=True))
        raise SystemExit(1)
