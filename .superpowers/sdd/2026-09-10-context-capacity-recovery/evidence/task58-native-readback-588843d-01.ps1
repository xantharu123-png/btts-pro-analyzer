$task57ReadbackScript = @'
import os, stat, json, hashlib, time, resource, signal
resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
signal.alarm(90)
from pathlib import Path
root = Path("/var/lib/betboy-context-chain-task58-588843d-01")
def identity(s):
    return [s.st_dev, s.st_ino, s.st_nlink, s.st_mode, s.st_uid, s.st_gid, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_blocks]
def read(path, cap):
    before = path.lstat()
    assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= cap
        raw = f.read(cap + 1)
        assert len(raw) == s.st_size
        after_fd = os.fstat(f.fileno())
        after_path = path.lstat()
        assert identity(before) == identity(s) == identity(after_fd) == identity(after_path)
        return raw, {"bytes": len(raw), "allocated": s.st_blocks * 512, "sha256": hashlib.sha256(raw).hexdigest(), "uid": s.st_uid, "gid": s.st_gid, "mode": oct(stat.S_IMODE(s.st_mode)), "device": s.st_dev, "inode": s.st_ino, "nlink": s.st_nlink, "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns, "identity_stable_during_read": True}
names = ["plan.json", "8cf04c77ca7a47063617cb1489471160c8329ce1420298b112e04c547c2a720f.jsonl"]
for name in ("ATP-output.json", "WTA-output.json", "failure.json", "report.json", "custody.json"):
    if (root / name).exists():
        names.append(name)
files = {}
for name in names:
    raw, meta = read(root / name, 8 * 1024**2)
    meta["text"] = raw.decode("utf-8")
    files[name] = meta
raw, cat_meta = read(root / "catalogue.json", 8 * 1024**2)
manifest = json.loads(raw)

expected_timezones = [
    {"path": "Europe/Zurich", "source": "/usr/share/zoneinfo/Europe/Zurich", "size": 1909, "sha256": "2b9418ed48e3d9551c84a4786e185bd2181d009866c040fbd729170d038629ef"},
    {"path": "UTC", "source": "/usr/share/zoneinfo/Etc/UTC", "size": 114, "sha256": "8b85846791ab2c8a5463c83a5be3c043e2570d7448434d41398969ed47e3e6f2"}
]
assert manifest["format"] == "betboy-native-context-chain-catalogue-v2"
assert manifest["timezone_data"] == expected_timezones
timezone_data = {"sources": [], "copies": [], "directories": [], "source_directories": []}
for item in expected_timezones:
    for label, path, mode in (("sources", Path(item["source"]), "0o644"), ("copies", root / "runtime-data" / "zoneinfo" / item["path"], "0o444")):
        _, meta = read(path, 65536)
        assert meta["bytes"] == item["size"] and meta["sha256"] == item["sha256"]
        assert meta["uid"] == 0 and meta["gid"] == 0 and meta["mode"] == mode
        meta["path"] = str(path)
        meta["key"] = item["path"]
        timezone_data[label].append(meta)
expected_dirs = {root / "runtime-data", root / "runtime-data/zoneinfo", root / "runtime-data/zoneinfo/Europe"}
expected_leaves = {root / "runtime-data/zoneinfo" / item["path"] for item in expected_timezones}
seen_dirs, seen_leaves = set(), set()
for parent, dirs, leaves in os.walk(root / "runtime-data", followlinks=False):
    p = Path(parent)
    assert p in expected_dirs
    s = p.lstat()
    assert stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and s.st_gid == 0 and stat.S_IMODE(s.st_mode) == 0o555
    seen_dirs.add(p)
    timezone_data["directories"].append({"path": str(p), "identity": identity(s), "logical": s.st_size, "allocated": s.st_blocks * 512})
    for name in dirs:
        assert p / name in expected_dirs and not (p / name).is_symlink()
    for name in leaves:
        assert p / name in expected_leaves
        seen_leaves.add(p / name)
assert seen_dirs == expected_dirs and seen_leaves == expected_leaves
source_dirs = {ancestor for item in expected_timezones for ancestor in Path(item["source"]).parents}
for p in sorted(source_dirs):
    s = p.lstat()
    assert stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and s.st_gid == 0 and not stat.S_IMODE(s.st_mode) & 0o022
    timezone_data["source_directories"].append({"path": str(p), "identity": identity(s), "logical": s.st_size, "allocated": s.st_blocks * 512})
alias = Path("/usr/share/zoneinfo/UTC")
alias_stat = alias.lstat()
assert stat.S_ISLNK(alias_stat.st_mode)
timezone_data["unadmitted_alias"] = {"path": str(alias), "target": os.readlink(alias), "identity": identity(alias_stat), "admitted": False}
timezone_data["all_originals_and_copies_match"] = True

copies = {}
for label, base, entries in (("code", root / "code", manifest["code"]), ("dependencies", root / "dependencies", manifest["dependencies"])):
    total = allocated = 0
    for item in entries:
        data, meta = read(base / item["path"], 128 * 1024**2)
        assert meta["bytes"] == item["size"] and meta["sha256"] == item["sha256"]
        assert meta["uid"] == 0 and meta["gid"] == 0 and meta["mode"] == "0o444"
        total += meta["bytes"]
        allocated += meta["allocated"]
    copies[label] = {"files": len(entries), "logical": total, "allocated": allocated, "all_members_match": True}
_, copied_archive = read(root / "archive.tar", 64 * 1024**2)
_, original_archive = read(Path("/tmp/betboy-context-qa.9xr68INa/task58-588843d-01.tar"), 64 * 1024**2)
_, original_catalogue = read(Path("/tmp/betboy-context-qa.9xr68INa/task58-588843d-01-catalogue.json"), 8 * 1024**2)
assert copied_archive["sha256"] == original_archive["sha256"]
assert cat_meta["sha256"] == original_catalogue["sha256"]
logical = allocated = file_count = directory_count = 0
attempt_files = []
for parent, dirs, leaves in os.walk(root, followlinks=False):
    for path in [Path(parent)] + [Path(parent) / name for name in leaves]:
        s = path.lstat()
        assert not stat.S_ISLNK(s.st_mode)
        if stat.S_ISDIR(s.st_mode):
            directory_count += 1
        else:
            assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1
            file_count += 1
        assert file_count + directory_count <= 20000
        logical += s.st_size
        allocated += s.st_blocks * 512
        if path.is_relative_to(root / "attempts"):
            attempt_files.append({"path": str(path.relative_to(root)), "bytes": s.st_size, "allocated": s.st_blocks * 512, "mode": oct(stat.S_IMODE(s.st_mode)), "uid": s.st_uid, "gid": s.st_gid})
    for name in dirs:
        assert not (Path(parent) / name).is_symlink()
processes = []
for name in os.listdir("/proc"):
    if not name.isdigit():
        continue
    try:
        status = Path("/proc", name, "status").read_text()
    except (FileNotFoundError, ProcessLookupError):
        continue
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if int(fields["Uid"].split()[0]) == 65534:
        processes.append({k: fields[k].strip() for k in ("Name", "State", "Pid", "PPid", "Uid", "Gid")})
v = os.statvfs(root)
result = {"format": "task57-native-terminal-readback-v2", "observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "job": str(root), "files": files, "copied_catalogue": cat_meta, "copied_archive": copied_archive, "original_archive": original_archive, "original_catalogue": original_catalogue, "copied_members": copies, "timezone_data": timezone_data, "job_physical": {"files": file_count, "directories": directory_count, "logical": logical, "allocated": allocated, "free": v.f_bavail * v.f_frsize}, "attempt_paths": attempt_files, "uid65534_processes": processes}
encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
assert len(encoded) <= 12 * 1024**2
view = memoryview(encoded)
while view:
    n = os.write(1, view)
    assert n > 0
    view = view[n:]
'@
$task57ReadbackCommand = "sudo -n /usr/bin/python3 -I -S -B -c '" + $task57ReadbackScript + "'"
$task57ReadbackOut = [IO.File]::Open((Join-Path (Get-Location) '.pytest_tmp/task58-native-run-588843d-01-readback.json'), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
$task57ReadbackErr = [IO.File]::Open((Join-Path (Get-Location) '.pytest_tmp/task58-native-run-588843d-01-readback.stderr'), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
$task57ReadbackStart = [Diagnostics.ProcessStartInfo]::new('ssh')
$task57ReadbackStart.UseShellExecute = $false
$task57ReadbackStart.CreateNoWindow = $true
$task57ReadbackStart.RedirectStandardOutput = $true
$task57ReadbackStart.RedirectStandardError = $true
foreach ($task57ReadbackArg in @('-o','BatchMode=yes','-o','ConnectTimeout=10','betboy-vps',$task57ReadbackCommand)) { $task57ReadbackStart.ArgumentList.Add($task57ReadbackArg) }
$task57ReadbackProcess = [Diagnostics.Process]::Start($task57ReadbackStart)
$task57ReadbackOutTask = $task57ReadbackProcess.StandardOutput.BaseStream.CopyToAsync($task57ReadbackOut)
$task57ReadbackErrTask = $task57ReadbackProcess.StandardError.BaseStream.CopyToAsync($task57ReadbackErr)
$task57ReadbackStopwatch = [Diagnostics.Stopwatch]::StartNew()
while (-not $task57ReadbackProcess.WaitForExit(1000)) { if ($task57ReadbackStopwatch.Elapsed.TotalSeconds -gt 120) { throw "Readback transport is nonterminal; inspect before any retry" } }
[void]$task57ReadbackOutTask.GetAwaiter().GetResult()
[void]$task57ReadbackErrTask.GetAwaiter().GetResult()
$task57ReadbackOut.Flush($true)
$task57ReadbackErr.Flush($true)
$task57ReadbackOut.Dispose()
$task57ReadbackErr.Dispose()
"readback_exit=$($task57ReadbackProcess.ExitCode)"
Get-Item -LiteralPath .pytest_tmp/task58-native-run-588843d-01-readback.json, .pytest_tmp/task58-native-run-588843d-01-readback.stderr | Select-Object Name,Length | ConvertTo-Json
Get-FileHash -LiteralPath .pytest_tmp/task58-native-run-588843d-01-readback.json -Algorithm SHA256 | ConvertTo-Json
Get-Content -LiteralPath .pytest_tmp/task58-native-run-588843d-01-readback.stderr
