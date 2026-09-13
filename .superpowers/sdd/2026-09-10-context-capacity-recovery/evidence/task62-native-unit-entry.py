"""Fixed ordinary-user synthetic RED/GREEN; no retained/live data access."""
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
root = Path("/tmp/betboy-context-retained-task62-6eb267a-01")
python = Path("/tmp/betboy-context-qa.9xr68INa/venv/bin/python")
assert root.parent.resolve() == root.parent and not os.path.lexists(root)
assert python.is_file()

new_raw = base64.b64decode("NEW_ARCHIVE_BASE64", validate=True)
old_raw = base64.b64decode("OLD_ARCHIVE_BASE64", validate=True)
assert len(new_raw) == 112640 and hashlib.sha256(new_raw).hexdigest() == "817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d"
assert len(old_raw) == 51200 and hashlib.sha256(old_raw).hexdigest() == "69ee6d43caa2f1d95ed5af5ced9d3f4aeda79023c74bf27447f8baca75a6d1a0"
test_name = "tests/test_native_context_receipt_retained_walk.py"
cat_name = "tests/native_context_receipt_diagnostic_catalogue.py"
helper_name = "tests/native_context_chain_catalogue.py"
pins = {test_name: "d71f669ded5272ef18e3907f7f1d5b628a72e1a35c4aa604d55cfe9a9438a68e",
        cat_name: "a17c62e6fec58735974f74be59e16dfd2d7ac9061da58239eac35a4f3a202185",
        helper_name: "48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935"}

def members(raw, expected, commit):
    result = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as bundle:
        assert bundle.pax_headers.get("comment") == commit
        for index, member in enumerate(bundle):
            assert index < 8
            if member.isdir():
                assert member.name.rstrip("/") == "tests"
                continue
            assert member.isreg() and member.name in expected and member.name not in result
            assert 0 < member.size <= 1024**2
            with bundle.extractfile(member) as source:
                value = source.read(member.size + 1)
            assert len(value) == member.size and hashlib.sha256(value).hexdigest() == expected[member.name]
            result[member.name] = value
    assert set(result) == set(expected)
    return result

new = members(new_raw, pins, "6eb267a294244bcb6375c5045cc5231c1109d611")
old_pin = "8ebd29f82bd8c92a8601adf8a339f9eb27ddbdf7dcb02bcc0f61d56ea03012e8"
old = members(old_raw, {cat_name: old_pin}, "68c1ff89042d26a9c9454a308e3fe65defa8947a")
# All archive members and bytes are validated before this first output mkdir.
root.mkdir(mode=0o700)
info = root.lstat()
assert stat.S_ISDIR(info.st_mode) and info.st_uid == 1000 and stat.S_IMODE(info.st_mode) == 0o700

def write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            assert n > 0
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)

write(root / "new-source.tar", new_raw)
write(root / "previous-source.tar", old_raw)
environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
results = []
started = time.monotonic()
for phase in ("red", "green"):
    stage = root / phase
    stage.mkdir(mode=0o700)
    (stage / "tests").mkdir(mode=0o700)
    supplied = dict(new)
    if phase == "red":
        supplied[cat_name] = old[cat_name]
    for name, raw in supplied.items():
        write(stage / name, raw)
    selected = test_name + ("::test_native_ancestor_open_scaling_and_complete_equivalence" if phase == "red" else "")
    report = stage / "result.xml"
    assert not os.path.lexists(stage / "fixtures") and not os.path.lexists(report)
    command = [str(python), "-I", "-B", "-m", "pytest", "--noconftest", "-q", "-p", "no:cacheprovider", selected,
               "--basetemp=" + str(stage / "fixtures"), "--junitxml=" + str(report), "--tb=short"]
    phase_start = time.monotonic()
    result = subprocess.run(command, cwd=stage, env=environment, capture_output=True, timeout=90)
    write(stage / "stdout.log", result.stdout)
    write(stage / "stderr.log", result.stderr)
    assert len(result.stdout) + len(result.stderr) <= 1024**2
    xml_raw = report.read_bytes()
    assert len(xml_raw) <= 262144
    suite = ET.fromstring(xml_raw).find("testsuite")
    assert suite is not None
    counts = {name: int(suite.attrib[name]) for name in ("tests", "failures", "errors", "skipped")}
    item = dict(phase=phase, child_exit=result.returncode, counts=counts, wall_seconds=time.monotonic() - phase_start,
                xml_bytes=len(xml_raw), xml_sha256=hashlib.sha256(xml_raw).hexdigest(),
                stdout_bytes=len(result.stdout), stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                stderr_bytes=len(result.stderr), stderr_sha256=hashlib.sha256(result.stderr).hexdigest(),
                stdout=result.stdout[:16000].decode("utf-8", errors="replace"), stderr=result.stderr[:4000].decode("utf-8", errors="replace"))
    print(json.dumps(item, sort_keys=True, separators=(",", ":")), flush=True)
    results.append(item)
    if phase == "red":
        assert result.returncode == 1 and counts == dict(tests=1, failures=1, errors=0, skipped=0)
        failure = suite.find("testcase/failure")
        assert failure is not None and "sum(name" in (failure.text or "")
    else:
        assert result.returncode == 0 and counts == dict(tests=43, failures=0, errors=0, skipped=0)

output = dict(format="betboy-task62-native-unit-v1", qa_directory=str(root), uid=os.geteuid(),
    observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    source_revision="6eb267a294244bcb6375c5045cc5231c1109d611", previous_revision="68c1ff89042d26a9c9454a308e3fe65defa8947a",
    parent_cpu_seconds=time.process_time(), children_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
    total_wall_seconds=time.monotonic() - started, phases=results,
    retained_inventory_measured=False, admission_created=False, application_changed=False)
raw = json.dumps(output, sort_keys=True, separators=(",", ":")).encode("ascii")
write(root / "result.json", raw)
print(raw.decode("ascii"), flush=True)
