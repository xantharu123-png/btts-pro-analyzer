"""Fixed Root transport entry for the reviewed Task61 native prefix tests."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

assert sys.platform == "linux" and os.getresuid() == os.getresgid() == (0,) * 3
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
mode = "PREFIX_MODE"
assert mode in ("prepare", "success", "failure")
pins = {
    "tests/native_context_receipt_diagnostic.py": "249aa84f12de528d0bbb268de794582ff44bcc6eb1330099793aa1de86a1feb5",
    "tests/native_context_receipt_diagnostic_catalogue.py": "c05241df7965b5b185f2df63945806eb89d5b4a37f3fa69c4bd400e17b8249d7",
    "tests/native_context_chain_catalogue.py": "48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935",
    "tests/native_context_diagnostic_admission.py": "f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad",
    "context_preparation_process_guard.py": "62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4",
    "context_preparation_budget.py": "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478",
    "context_preparation_supervisor.py": "c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8",
}
encoded = json.loads(base64.b64decode("BUNDLE_BASE64", validate=True))
assert type(encoded) is dict and set(encoded) == set(pins)
sources = {name: base64.b64decode(value, validate=True) for name, value in encoded.items()}
assert all(0 < len(raw) <= 1024**2 and hashlib.sha256(raw).hexdigest() == pins[name]
           for name, raw in sources.items())
parent = dict(__name__="_task61_native_prefix_entry", __file__="<reviewed-task61-parent>",
              _REVIEWED_BOOTSTRAP=sources)
exec(compile(sources["tests/native_context_receipt_diagnostic.py"], parent["__file__"], "exec"), parent)
base = Path("/var/lib/betboy-receipt-prefix-task61-01")
if mode == "prepare":
    # This branch never launches a child; an alarm cannot abandon custody.
    signal.alarm(30)
    parent["startup"]()
    catalogue = parent["load_catalogue"](sources)
    catalogue["protected"](base.parent, directory=True, searchable=True)
    probe = parent["PROBE_SOURCE"]
    assert len(probe) == 1203 and hashlib.sha256(probe).hexdigest() == "5818c8a838e817651c6bd0e9e76158df4f029eb0bb2bc6d5d74de1d189fa37be"
    os.mkdir(base, 0o755)  # Refuse any pre-existing namespace, never clean/reuse it.
    parent_fd = os.open(base.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    parent["write_new"](catalogue, base / "probe.py", probe, 4096)
    for name in ("success", "failure"):
        path = base / name
        os.mkdir(path, 0o700)
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchown(fd, 65534, 65534)
            os.fsync(fd)
        finally:
            os.close(fd)
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    records = []
    for path in (base, base / "probe.py", base / "success", base / "failure"):
        info = path.lstat()
        records.append(dict(path=str(path), uid=info.st_uid, gid=info.st_gid,
                            mode=stat.S_IMODE(info.st_mode), inode=info.st_ino,
                            size=info.st_size, allocated=info.st_blocks * 512))
    result = dict(prepared=records, probe_sha256=hashlib.sha256(probe).hexdigest())
else:
    # No alarm/timeout that could discard an actual UnreapedChild pidfd.
    result = parent["native_prefix_test"](mode, root=str(base))
output = dict(format="betboy-task61-root-prefix-evidence-v1", mode=mode,
              observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              parent_pid=os.getpid(), cpu_ns=time.process_time_ns(),
              whole_c_pass=False, production_changed=False, result=result)
raw = json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
assert len(raw) <= 65536
print(raw.decode("ascii"), flush=True)
