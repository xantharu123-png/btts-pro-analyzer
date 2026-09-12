"""Root-only bounded sealer for one small native diagnostic, never a deploy.

Run this reviewed/versioned stdlib script through a fresh env-i Python stdin,
not by importing or executing an app/user-writable source path as root.
Only a known five-file Git archive and four existing numerical packages are
copied. All failures leave their new root-private directory charged/intact.
No existing directory, database, service, permission or key is modified.
This is diagnostic installation, NOT a B runtime-closure attestation/quota.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import time


MIB = 1024**2
FREE_BYTES = 4 * 1024**3
COPY_SLOT_BYTES = 512 * MIB
OUTPUT_SLOT_BYTES = 64 * MIB
ARCHIVE_BYTES = MIB
MAX_FILES = 20000
EXPECTED_BYTES = 207288087
EXPECTED_COUNT = 3729
DEPENDENCY_SHA256 = "eb6679f2264b26bf998b7efdae0f3ad57c0a18dd1597a8201ed6054cbebfd55c"
DEPENDENCY_SOURCE = Path("/tmp/betboy-context-qa.9xr68INa/venv/lib/python3.12/site-packages")
PACKAGES = ("numpy", "numpy.libs", "scipy", "scipy.libs")
HELPERS = {
    "context_preparation_process_guard": "62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4",
    "context_preparation_budget": "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478",
    "context_preparation_supervisor": "ae9fec1f9a7798455f21f5ac4588f714bc31803602ed51128686e3f9c17ea16d",
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest_text(raw):
    require(type(raw) is str and len(raw) == 64 and
            all(c in "0123456789abcdef" for c in raw), "invalid exact digest")
    return raw


def identity(info):
    # Reading may change atime. Content/namespace mutation must not be hidden.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def regular(path, maximum):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            0 <= before.st_size <= maximum, "not a bounded single-link regular file")
    # Binding the returned FD must not first block on a regular -> FIFO swap.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        require(identity(os.fstat(fd)) == identity(before), "opened source differs")
        raw = bytearray()
        while part := os.read(fd, min(MIB, maximum + 1 - len(raw))):
            raw.extend(part)
            require(len(raw) <= maximum, "source grew beyond bound")
        require(identity(os.fstat(fd)) == identity(before) == identity(path.lstat()),
                "source identity changed")
        return bytes(raw)
    finally:
        os.close(fd)


def fresh_file(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            require(count > 0, "copy made no progress")
            view = view[count:]
        os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)


def decode_archive(raw, archive_sha, probe_sha, worker_sha):
    require(len(raw) <= ARCHIVE_BYTES and hashlib.sha256(raw).hexdigest() == digest_text(archive_sha),
            "archive identity differs")
    expected = {name + ".py": value for name, value in HELPERS.items()}
    expected.update({"tests/native_preparation_probe.py": digest_text(probe_sha),
                     "tests/native_preparation_worker.py": digest_text(worker_sha)})
    result = {}
    entries = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for entry in archive:
            entries += 1
            require(entries <= 6, "too many archive members")
            if entry.isdir():
                require(entry.name == "tests" and entry.size == 0, "unexpected archive directory")
                continue
            require(entry.name in expected and entry.name not in result and
                    entry.isreg() and 0 < entry.size <= 128 * 1024,
                    "unknown, duplicate, linked or oversized archive source")
            stream = archive.extractfile(entry)
            require(stream is not None, "missing source bytes")
            with stream:
                body = stream.read(128 * 1024 + 1)
            require(len(body) == entry.size and hashlib.sha256(body).hexdigest() == expected[entry.name],
                    "source code identity differs")
            result[entry.name] = body
    require(result.keys() == expected.keys(), "incomplete code archive")
    return result


def walk_packages(root):
    directory_count = 0
    for name in PACKAGES:
        base = root / name
        require(stat.S_ISDIR(base.lstat().st_mode), "package root is not a real directory")
        for directory, dirs, files in os.walk(base, followlinks=False):
            directory_count += 1
            require(directory_count <= MAX_FILES and len(dirs) + len(files) <= MAX_FILES,
                    "dependency namespace exceeded")
            current = Path(directory)
            require(len(current.parts) - len(base.parts) <= 32, "dependency depth exceeded")
            for child in dirs:
                require(stat.S_ISDIR((current / child).lstat().st_mode), "dependency directory is linked")
            for child in sorted(files):
                yield current / child
            dirs.sort()


def tree_digest(root, inventory=None):
    total = count = 0
    digest = hashlib.sha256()
    for path in walk_packages(root):
        info = path.lstat()
        total += info.st_size
        count += 1
        require(count <= MAX_FILES and total <= COPY_SLOT_BYTES, "dependency inventory exceeded")
        raw = regular(path, 128 * MIB)
        require(identity(path.lstat()) == identity(info), "inventory source changed")
        if inventory is not None:
            inventory.append((path.relative_to(root), identity(info), hashlib.sha256(raw).hexdigest()))
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0" +
                      str(len(raw)).encode("ascii") + b"\0" + hashlib.sha256(raw).digest())
    return count, total, digest.hexdigest()


def free_space(directory):
    info = os.statvfs(directory)
    require(info.f_favail > 0 and info.f_frsize > 0, "filesystem observation unavailable")
    return info.f_bavail * info.f_frsize


def main(arguments):
    started = time.monotonic()
    require(sys.platform == "linux" and os.getresuid() == (0, 0, 0), "fresh root Linux CLI required")
    import resource
    require((sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode) == (1, 1, 1),
            "-I -S -B required")
    require(dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, "clean env-i required")
    require(len(arguments) == 4, "archive/path and three exact hashes required")
    # The VPS uses a piped coredump handler: CORE=0 alone is insufficient.
    # This dedicated stdlib process neither execs nor changes credentials later.
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    require(libc.prctl(4, 0, 0, 0, 0) == 0 and libc.prctl(3, 0, 0, 0, 0) == 0,
            "sealer nondumpable state unavailable")
    archive_path, archive_sha, probe_sha, worker_sha = arguments
    for raw in (archive_sha, probe_sha, worker_sha):
        digest_text(raw)
    archive_path = Path(archive_path)
    require(archive_path.is_absolute() and archive_path.parent == DEPENDENCY_SOURCE.parents[3],
            "archive outside already authorized QA upload directory")
    for key, value in ((resource.RLIMIT_CPU, 30), (resource.RLIMIT_AS, 512 * MIB),
                       (resource.RLIMIT_FSIZE, 128 * MIB), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (value, value))
    raw = regular(archive_path, ARCHIVE_BYTES)
    sources = decode_archive(raw, archive_sha, probe_sha, worker_sha)
    inventory = []
    require(tree_digest(DEPENDENCY_SOURCE, inventory) == (EXPECTED_COUNT, EXPECTED_BYTES, DEPENDENCY_SHA256),
            "complete predeclared dependency inventory differs")
    reserve = COPY_SLOT_BYTES + OUTPUT_SLOT_BYTES + ARCHIVE_BYTES + 2 * MIB
    require(free_space(Path("/var/lib")) >= FREE_BYTES + reserve, "whole diagnostic reservation unavailable")
    root = Path(tempfile.mkdtemp(prefix="betboy-native-probe-", dir="/var/lib"))
    print(json.dumps({"stage": "private_seal_created", "root": str(root), "probe_executed": False}), flush=True)
    # Private until ALL byte/identity/resource checks completed. Failures keep it
    # private and charged; even source namespace races never publish other bytes.
    helper_dir, dependency_dir = root / "helpers", root / "deps"
    helper_dir.mkdir(mode=0o755)
    dependency_dir.mkdir(mode=0o755)
    for name, body in sources.items():
        target = helper_dir / name if "/" not in name else root / Path(name).name
        fresh_file(target, body)
    total = count = 0
    # Copy the exact predeclared inventory, never a newly enumerated path set.
    # Names and contents were included in the approved complete source hash.
    for relative, before, expected_digest in inventory:
        require(time.monotonic() - started < 60, "diagnostic sealing deadline exceeded")
        require(free_space(root) >= FREE_BYTES + OUTPUT_SLOT_BYTES, "free-space reserve lost")
        path = DEPENDENCY_SOURCE / relative
        require(identity(path.lstat()) == before, "dependency changed after admission")
        body = regular(path, 128 * MIB)
        require(identity(path.lstat()) == before and hashlib.sha256(body).hexdigest() == expected_digest,
                "dependency changed during copy")
        total += len(body)
        count += 1
        require(total <= COPY_SLOT_BYTES and count <= MAX_FILES, "dependency copy reservation exceeded")
        target = dependency_dir / relative
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        fresh_file(target, body)
    require(tree_digest(dependency_dir) == (EXPECTED_COUNT, EXPECTED_BYTES, DEPENDENCY_SHA256),
            "complete sealed dependency copy differs")
    # Final physical readback includes every new file and directory, not merely
    # source lengths. This does not claim a filesystem quota during copy.
    allocated = root.stat().st_blocks * 512
    for directory, dirs, files in os.walk(root):
        for name in dirs:
            os.chmod(Path(directory) / name, 0o755)
        for name in dirs + files:
            info = (Path(directory) / name).lstat()
            require(info.st_uid == 0 and not info.st_mode & 0o022, "seal not root-protected")
            allocated += max(info.st_size, info.st_blocks * 512)
    require(allocated <= COPY_SLOT_BYTES and free_space(root) >= FREE_BYTES + OUTPUT_SLOT_BYTES,
            "final diagnostic allocation/reserve differs")
    executable = Path("/proc/self/exe").resolve(strict=True)
    manifest = {"format": "betboy-native-preparation-probe-v1", "version": 1,
                "helper_directory": str(helper_dir), "helper_sha256": HELPERS,
                "probe_path": str(root / "native_preparation_probe.py"), "probe_sha256": probe_sha,
                "worker_path": str(root / "native_preparation_worker.py"), "worker_sha256": worker_sha,
                "dependency_directory": str(dependency_dir), "dependency_closure_sha256": DEPENDENCY_SHA256,
                "python_executable": str(executable),
                "python_sha256": hashlib.sha256(regular(executable, 64 * MIB)).hexdigest(),
                "worker_uid": 65534, "worker_gid": 65534}
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    fresh_file(root / "manifest.json", manifest_bytes)
    # SQLite canonicalizes its file name and traverses absolute ancestors even
    # after chdir. Traversal only, no listing/write; journal and child dirs are
    # separately 0700 and report files 0600. Only this NEW directory is changed.
    output = root / "output"
    output.mkdir(mode=0o700)
    os.chmod(output, 0o711)
    require(time.monotonic() - started < 60 and libc.prctl(3, 0, 0, 0, 0) == 0,
            "diagnostic sealing deadline/nondumpable state changed")
    # Publish read-only code/deps only; output is not listable/writable. No probe is
    # started by this helper and no key/app configuration was read or copied.
    os.chmod(root, 0o755)
    print(json.dumps({"format": "betboy-native-probe-seal-v1", "root": str(root),
                      "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                      "dependency_sha256": DEPENDENCY_SHA256, "dependency_bytes": total,
                      "dependency_files": count, "observed_allocation_bytes_before_manifest": allocated,
                      "reserved_copy_bytes": COPY_SLOT_BYTES, "reserved_output_bytes": OUTPUT_SLOT_BYTES,
                      "elapsed_seconds": time.monotonic() - started,
                      "sealer_cpu_seconds": time.process_time(), "probe_executed": False}, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
