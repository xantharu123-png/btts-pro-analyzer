"""Read-only import diagnosis against the retained FIX5 seal; not native QA."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time

resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
signal.alarm(25)
started = time.process_time_ns()
seal = Path("/var/lib/betboy-context-chain-task57-bc6305c-05")
code = seal / "code"


def pinned(path, checksum, cap):
    def epoch(value):
        return (value.st_dev, value.st_ino, value.st_nlink, value.st_mode,
                value.st_uid, value.st_gid, value.st_size,
                value.st_mtime_ns, value.st_ctime_ns)
    before = path.lstat()
    assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1
    assert before.st_uid == 0 and stat.S_IMODE(before.st_mode) == 0o444
    assert before.st_size <= cap
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as source:
        raw = source.read(cap + 1)
        assert epoch(os.fstat(source.fileno())) == epoch(before) == epoch(path.lstat())
    assert len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == checksum
    return raw


manifest = json.loads(pinned(seal / "catalogue.json", "0a7002d1362dd989dbc7743f49844c4a6a57e141cfd56ac818bb74bc09e6f6e6", 8 * 1024**2))
modules = {}
for name, checksum in (
    ("native_context_chain_catalogue.py", "48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935"),
    ("native_context_chain_worker.py", "afaa8e2cfa01bb6f3d99db2b51f975569ddf84a911d0d3f3f67b840a2fa1d711"),
):
    path = code / "tests" / name
    ns = {"__name__": "_readonly_timezone_diagnosis", "__file__": str(path)}
    exec(compile(pinned(path, checksum, 1024**2), str(path), "exec"), ns)
    modules[name] = ns


def readonly_audit(event, args):
    if event in ("os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "subprocess.Popen", "socket.__new__", "socket.connect", "sqlite3.connect", "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.chown", "os.truncate"):
        raise RuntimeError("read-only diagnostic denied " + event)
    if event == "open" and len(args) > 2 and isinstance(args[2], int):
        assert not args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)


sys.addaudithook(readonly_audit)
worker = modules["native_context_chain_worker.py"]
catalogue = modules["native_context_chain_catalogue.py"]
worker["observe_python_files"](code, seal, seal / "attempts/ATP/positive", manifest)
worker["bind_timezone_data"](catalogue, seal, manifest)
sys.path.insert(0, str(seal / "dependencies"))
try:
    import pandas
except BaseException as exc:
    frames = []
    trace = exc.__traceback__
    while trace is not None and len(frames) < 80:
        frames.append({"file": trace.tb_frame.f_code.co_filename, "line": trace.tb_lineno, "function": trace.tb_frame.f_code.co_name})
        trace = trace.tb_next
    result = {"status": "import-denied", "exception": type(exc).__name__, "message": str(exc)[:512], "file_context": getattr(exc, "file_context", None), "frames": frames, "frames_truncated": trace is not None}
else:
    result = {"status": "import-complete", "pandas": pandas.__version__}
result.update({"scope": "ordinary-user-readonly-import-diagnosis-not-guarded-acceptance", "uid": os.getuid(), "cpu_ns": time.process_time_ns() - started, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
raw = json.dumps(result, sort_keys=True).encode("ascii") + b"\n"
assert len(raw) <= 65536
view = memoryview(raw)
while view:
    count = os.write(1, view)
    assert count > 0
    view = view[count:]
