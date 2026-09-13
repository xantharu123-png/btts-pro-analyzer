"""Fixed ordinary-user Task63 tests; no retained/live database or admission."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import time
import xml.etree.ElementTree as ET

assert os.getresuid() == os.getresgid() == (1000,) * 3
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
os.umask(0o077)
root = Path("/tmp/betboy-context-descriptors-task63-bb54ec5-01")
python = Path("/tmp/betboy-context-qa.9xr68INa/venv/bin/python")
assert root.parent.resolve() == root.parent and not os.path.lexists(root)
assert python.is_file()
initial_nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
assert initial_nofile == (1024, 1048576), initial_nofile

source_raw = base64.b64decode("NEW_ARCHIVE_BASE64", validate=True)
assert len(source_raw) == 143360 and hashlib.sha256(source_raw).hexdigest() == "6d93ed7db2d1fb29167deceda86e4910f0fe99f951a2dfc3cf0f421f89d4ea10"
test_name = "tests/test_native_context_active_descriptors.py"
pins = {
    test_name: "aeb378e3bf9bb79fdb8793ba382780724a7cc116c9eb682bb67c67c2cac6e69c",
    "tests/native_context_receipt_diagnostic_catalogue.py": "69a7300536b81d78c38fd6a7d4701f451b1d1468f546ba892908896311dc7f7b",
    "tests/native_context_chain_catalogue.py": "48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935",
    "context_preparation_supervisor.py": "c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8",
}
members = {}
with tarfile.open(fileobj=io.BytesIO(source_raw), mode="r:") as bundle:
    assert bundle.pax_headers.get("comment") == "bb54ec58eadcab0e9c0ae065aa258cb7a8f337d6"
    for index, member in enumerate(bundle):
        assert index < 8
        if member.isdir():
            assert member.name.rstrip("/") == "tests"
            continue
        assert member.isreg() and member.name in pins and member.name not in members
        assert 0 < member.size <= 1024**2
        with bundle.extractfile(member) as source:
            raw = source.read(member.size + 1)
        assert len(raw) == member.size and hashlib.sha256(raw).hexdigest() == pins[member.name]
        members[member.name] = raw
assert set(members) == set(pins)
# Complete held archive validation precedes the first output creation.
root.mkdir(mode=0o700)
info = root.lstat()
assert stat.S_ISDIR(info.st_mode) and info.st_uid == 1000 and stat.S_IMODE(info.st_mode) == 0o700
(root / "tests").mkdir(mode=0o700)

def write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            assert count > 0
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)

write(root / "source.tar", source_raw)
for name, raw in members.items():
    write(root / name, raw)
environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
report = root / "result.xml"
command = [str(python), "-I", "-B", "-m", "pytest", "--noconftest", "-q", "-p", "no:cacheprovider", test_name,
           "--basetemp=" + str(root / "fixtures"), "--junitxml=" + str(report), "--tb=short"]
started = time.monotonic()
result = subprocess.run(command, cwd=root, env=environment, capture_output=True, timeout=75)
assert len(result.stdout) + len(result.stderr) <= 1024**2
write(root / "stdout.log", result.stdout)
write(root / "stderr.log", result.stderr)
with report.open("rb") as source:
    xml_raw = source.read(262145)
assert len(xml_raw) <= 262144
suite = ET.fromstring(xml_raw).find("testsuite")
assert suite is not None
counts = {name: int(suite.attrib[name]) for name in ("tests", "failures", "errors", "skipped")}
output = dict(format="betboy-task63-native-unit-v1", qa_directory=str(root), uid=os.geteuid(),
    observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    source_revision="bb54ec58eadcab0e9c0ae065aa258cb7a8f337d6", child_exit=result.returncode,
    counts=counts, initial_nofile=initial_nofile, final_nofile=resource.getrlimit(resource.RLIMIT_NOFILE),
    parent_cpu_seconds=time.process_time(), children_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
    total_wall_seconds=time.monotonic() - started, xml_bytes=len(xml_raw), xml_sha256=hashlib.sha256(xml_raw).hexdigest(),
    stdout_bytes=len(result.stdout), stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
    stderr_bytes=len(result.stderr), stderr_sha256=hashlib.sha256(result.stderr).hexdigest(),
    stdout=result.stdout[:16000].decode("utf-8", errors="replace"), stderr=result.stderr[:4000].decode("utf-8", errors="replace"),
    retained_inventory_measured=False, admission_created=False, application_changed=False)
raw = json.dumps(output, sort_keys=True, separators=(",", ":")).encode("ascii")
write(root / "result.json", raw)
print(raw.decode("ascii"), flush=True)
assert result.returncode == 0 and counts == dict(tests=36, failures=0, errors=0, skipped=1)
skipped = [node for node in suite.findall("testcase") if node.find("skipped") is not None]
assert len(skipped) == 1 and skipped[0].attrib["name"] == "test_portable_sample_marks_native_descriptor_validation_absent"
assert resource.getrlimit(resource.RLIMIT_NOFILE) == initial_nofile and result.stderr == b""
