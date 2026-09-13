"""One full read of the fixed dominant old QA root; no control/admission write."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tarfile
import time

signal.alarm(300)  # No child is ever created by this read-only instrument.
assert os.getresuid() == os.getresgid() == (0,) * 3
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
raw = base64.b64decode("NEW_ARCHIVE_BASE64", validate=True)
assert len(raw) == 112640 and hashlib.sha256(raw).hexdigest() == "817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d"
pins = {"tests/test_native_context_receipt_retained_walk.py": "d71f669ded5272ef18e3907f7f1d5b628a72e1a35c4aa604d55cfe9a9438a68e",
        "tests/native_context_receipt_diagnostic_catalogue.py": "a17c62e6fec58735974f74be59e16dfd2d7ac9061da58239eac35a4f3a202185",
        "tests/native_context_chain_catalogue.py": "48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935"}
members = {}
with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as bundle:
    assert bundle.pax_headers.get("comment") == "6eb267a294244bcb6375c5045cc5231c1109d611"
    for index, member in enumerate(bundle):
        assert index < 8
        if member.isdir():
            assert member.name.rstrip("/") == "tests"
            continue
        assert member.isreg() and member.name in pins and member.name not in members and 0 < member.size <= 1024**2
        with bundle.extractfile(member) as source:
            value = source.read(member.size + 1)
        assert len(value) == member.size and hashlib.sha256(value).hexdigest() == pins[member.name]
        members[member.name] = value
assert set(members) == set(pins)
old = dict(__name__="_held_task62_old_catalogue", __file__="<held-old-catalogue>")
exec(compile(members["tests/native_context_chain_catalogue.py"], old["__file__"], "exec"), old)
catalogue = dict(__name__="_held_task62_measure_catalogue", __file__="<held-new-catalogue>", _OLD_CATALOGUE=old)
exec(compile(members["tests/native_context_receipt_diagnostic_catalogue.py"], catalogue["__file__"], "exec"), catalogue)
assert not any(name.startswith(("pytest", "numpy", "scipy", "pandas", "context_storage_v2")) for name in sys.modules)
root = Path("/tmp/betboy-context-qa.9xr68INa")
started_cpu, started_wall = time.process_time_ns(), time.monotonic_ns()
print(json.dumps(dict(format="betboy-task62-fixed-root-measure-v1", event="begin", path=str(root),
    pid=os.getpid(), cpu_ns=started_cpu, observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    scope="one-complete-root-not-whole-retained-union", admission_created=False, application_changed=False),
    sort_keys=True, separators=(",", ":")), flush=True)
result = catalogue["retained_root"](root)
print(json.dumps(dict(format="betboy-task62-fixed-root-measure-v1", event="end", record=result,
    pid=os.getpid(), scan_cpu_ns=time.process_time_ns()-started_cpu, scan_wall_ns=time.monotonic_ns()-started_wall,
    parent_whole_cpu_ns=time.process_time_ns(), observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    scope="one-complete-root-not-whole-retained-union", admission_created=False, application_changed=False),
    sort_keys=True, separators=(",", ":")), flush=True)
