"""Bounded read-only shape preflight; no retained-content/admission authority."""
import hashlib
import json
import os
import resource
import signal
import stat
import time

resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
signal.alarm(45)

SELECTORS = (
    ("/var/lib", "betboy-", ("betboy-backup",)),
    ("/var/tmp", "betboy-update.", ()),
    ("/tmp", "betboy-context-", ()),
    ("/tmp", "betboy-tour-", ()),
    ("/var/backups", "betboy", ("betboy-ssh",)),
)


def ident(value):
    return [value.st_dev, value.st_ino, value.st_mode, value.st_uid,
            value.st_gid, value.st_nlink, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_blocks]


def selection():
    result = set()
    for parent, prefix, omitted in SELECTORS:
        with os.scandir(parent) as items:
            for item in items:
                if item.name.startswith(prefix) and item.name not in omitted:
                    result.add(item.path)
    assert 0 < len(result) <= 256
    return sorted(result)


def shape(root):
    before = os.lstat(root)
    assert stat.S_ISDIR(before.st_mode)
    kinds = {"regular": 0, "directory": 0, "symlink": 0, "other": 0}
    logical = allocated = max_file = linked = writable = 0
    examples = []
    hasher = hashlib.sha256()
    pending = [(root, 0)]
    while pending:
        path, depth = pending.pop()
        assert depth <= 32
        info = os.lstat(path)
        relative = os.path.relpath(path, root)
        assert len(relative.encode("utf-8")) <= 2048
        if stat.S_ISDIR(info.st_mode):
            kind = "directory"
            with os.scandir(path) as items:
                names = sorted(item.name for item in items)
            assert len(names) <= 50000
            pending.extend((os.path.join(path, name), depth + 1)
                           for name in reversed(names))
            assert ident(info) == ident(os.lstat(path))
        elif stat.S_ISREG(info.st_mode):
            kind = "regular"
            max_file = max(max_file, info.st_size)
            linked += int(info.st_nlink != 1)
        elif stat.S_ISLNK(info.st_mode):
            kind = "symlink"
        else:
            kind = "other"
        kinds[kind] += 1
        assert sum(kinds.values()) <= 200000
        logical += info.st_size
        allocated += info.st_blocks * 512
        writable += int(bool(info.st_mode & 0o022))
        if kind in ("symlink", "other") and len(examples) < 8:
            examples.append({"path": relative, "kind": kind})
        record = {"path": relative, "kind": kind, "identity": ident(info)}
        hasher.update(json.dumps(record, sort_keys=True,
                                 separators=(",", ":")).encode("ascii") + b"\n")
    assert ident(before) == ident(os.lstat(root))
    return {"path": root, "identity": ident(before), "counts": kinds,
            "logical": logical, "allocated": allocated,
            "max_file": max_file, "hardlinked_regular_files": linked,
            "group_or_other_writable_entries": writable,
            "nonregular_examples": examples,
            "metadata_membership_sha256": hasher.hexdigest()}


roots = selection()
results = [shape(root) for root in roots]
assert roots == selection()
filesystem = os.statvfs("/var/lib")
result = {
    "format": "betboy-retained-metadata-preflight-v1",
    "observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "selectors": SELECTORS, "roots": results,
    "logical": sum(item["logical"] for item in results),
    "allocated": sum(item["allocated"] for item in results),
    "free": filesystem.f_bavail * filesystem.f_frsize,
    "cpu_seconds": time.process_time(),
    "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    "contents_hashed": False, "admission_authority": False,
    "durable_cpu_ticket": None,
}
raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
assert len(raw) <= 262144
remaining = memoryview(raw)
while remaining:
    written = os.write(1, remaining)
    assert written > 0
    remaining = remaining[written:]
