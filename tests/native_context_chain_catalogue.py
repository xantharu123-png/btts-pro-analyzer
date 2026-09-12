"""Closed Task57 small-chain admission. Stdlib only; not a quota/B closure.

Inventory mode is read-only preparation, NOT the measured execution/sealer.
The root owner must review and pin its output before the separate fresh parent
starts. Source archive must be exported by Root from the reviewed Git commit.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile


FORMAT = "betboy-native-context-chain-catalogue-v1"
MIB = 1024**2
GIB = 1024**3
ARCHIVE_CAP = 64 * MIB
MANIFEST_CAP = 8 * MIB
MEMBER_CAP = 128 * MIB
DEPENDENCY_CAP = GIB
MAX_FILES = 30000
ATTEMPTS = ("ATP/positive", "ATP/late-cleanup", "WTA/positive")
DEPENDENCY_SOURCE = Path("/tmp/betboy-context-qa.9xr68INa/venv/lib/python3.12/site-packages")
# Closed observed installation selection, including lazy numerical and pytest
# support and metadata. Unrelated installers and training packages are excluded.
PACKAGES = (
    "_pytest", "certifi", "certifi-2026.7.22.dist-info", "charset_normalizer",
    "charset_normalizer-3.5.1.dist-info", "dateutil", "idna", "idna-3.19.dist-info",
    "iniconfig", "iniconfig-2.3.0.dist-info", "numpy", "numpy-2.5.1.dist-info",
    "numpy.libs", "packaging", "packaging-26.3.dist-info", "pandas",
    "pandas-3.0.5.dist-info", "pluggy", "pluggy-1.6.0.dist-info", "py.py",
    "pygments", "pygments-2.21.0.dist-info", "pytest", "pytest-9.1.1.dist-info",
    "python_dateutil-2.9.0.post0.dist-info", "requests", "requests-2.34.2.dist-info",
    "scipy", "scipy-1.18.0.dist-info", "scipy.libs", "six-1.17.0.dist-info",
    "six.py", "urllib3", "urllib3-2.7.0.dist-info",
)
HELPERS = {
    "context_preparation_process_guard.py": "62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4",
    "context_preparation_budget.py": "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478",
    "context_preparation_supervisor.py": "c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8",
}
TASK54 = "tests/test_context_storage_corpus_consumer.py"
TASK54_SHA = "5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649"
REQUIRED = tuple(HELPERS) + (TASK54, "tests/test_tennis_live_worker.py",
    "tests/native_context_chain.py", "tests/native_context_chain_catalogue.py",
    "tests/native_context_chain_worker.py", "tennis/predict.py", "tennis/model_state.py",
    "tennis/elo.py", "tennis/serve_model.py", "tennis/simulator.py", "tennis/data_loader.py")


class ChainError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ChainError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(values):
    result = {}
    for key, value in values:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MANIFEST_CAP, "bounded JSON required")
    def invalid(_value):
        raise ChainError("nonfinite/noninteger catalogue number")
    return json.loads(raw, object_pairs_hook=pairs, parse_float=invalid, parse_constant=invalid)


def sha(value):
    require(type(value) is str and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "invalid SHA256")
    return value


def integer(value, maximum):
    require(type(value) is int and 0 <= value <= maximum, "invalid bounded exact integer")
    return value


def relative(value):
    require(type(value) is str and 0 < len(value) <= 512 and "\\" not in value
            and "\0" not in value, "invalid member path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and len(p.parts) <= 20
            and ".." not in p.parts and "." not in p.parts, "noncanonical member path")
    return value


def records(values, maximum):
    require(type(values) is list and 0 < len(values) <= MAX_FILES, "invalid catalogue count")
    found, total = {}, 0
    for item in values:
        require(type(item) is dict and set(item) == {"path", "size", "sha256"}, "entry shape")
        name = relative(item["path"])
        require(name not in found, "duplicate catalogue member")
        total += integer(item["size"], MEMBER_CAP)
        sha(item["sha256"])
        found[name] = item
    require(total <= maximum, "aggregate catalogue exceeded")
    require(list(found) == sorted(found), "catalogue is not sorted")
    return found


def archive_members(raw, entries):
    require(type(raw) is bytes and len(raw) <= ARCHIVE_CAP, "archive exceeded")
    expected = records(entries, ARCHIVE_CAP)
    directories = {str(p) for n in expected for p in PurePosixPath(n).parents if str(p) != "."}
    seen_dirs, found = set(), {}
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            for index, member in enumerate(archive):
                require(index < MAX_FILES, "archive member count exceeded")
                name = relative(member.name)
                if member.isdir():
                    require(name in directories and name not in seen_dirs and member.size == 0,
                            "unknown/duplicate archive directory")
                    seen_dirs.add(name)
                    continue
                require(member.isreg() and name in expected and name not in found,
                        "unknown/duplicate/linked archive member")
                item = expected[name]
                require(member.size == item["size"] and member.size <= MEMBER_CAP, "member size differs")
                stream = archive.extractfile(member)
                require(stream is not None, "missing member bytes")
                with stream:
                    body = stream.read(item["size"] + 1)
                require(len(body) == item["size"] and digest(body) == item["sha256"], "member hash differs")
                found[name] = body
    except (tarfile.TarError, OSError) as exc:
        raise ChainError("invalid uncompressed archive") from exc
    require(found.keys() == expected.keys(), "incomplete archive")
    return found


def attempt_slots():
    result = {}
    names = ["legacy-setup/" + n for n in
             ("context.db", "shadow.db", "legacy-oracle.sqlite", "oracle-shadow.sqlite")]
    names += ["whole-job/" + n for n in ("corpus/legacy-copy.sqlite",
              "old-parts/snapshot-parts.sqlite", "history/history.sqlite",
              "feature/features.sqlite", "new-consumers/consumers.sqlite")]
    for attempt in ATTEMPTS:
        for name in names:
            result[attempt + "/" + name] = 4 * MIB
            result[attempt + "/" + name + "-journal"] = 4 * MIB
        result[attempt + "/whole-job/corpus/receipt-additions.bin"] = MIB
    return result


def resource_plan(archive_bytes, code_bytes, dependency_bytes):
    integer(archive_bytes, ARCHIVE_CAP)
    integer(code_bytes, ARCHIVE_CAP)
    integer(dependency_bytes, DEPENDENCY_CAP)
    # All code/dependency files remain active inputs, not just corpus DBs.
    attempts = sum(attempt_slots().values()) + 6 * MIB
    controls = 2 * MANIFEST_CAP + 12 * MIB  # includes 2MiB reviewed stdin/launcher allowance
    metadata = 128 * MIB  # includes copied directory and per-file allocation slack
    total = archive_bytes + code_bytes + dependency_bytes + attempts + controls + metadata
    # Original archive/dependency inputs remain admitted while their full
    # copies are rechecked; neither side is silently excluded from active input.
    active = 2 * archive_bytes + code_bytes + 2 * dependency_bytes + attempts + controls + metadata
    require(total <= 8 * GIB and active <= 4 * GIB, "complete diagnostic plan exceeded")
    return {"archive": archive_bytes, "code": code_bytes, "dependencies": dependency_bytes,
            "attempt_reservation": attempts, "control_reservation": controls,
            "metadata_reservation": metadata, "total": total, "active_input_ceiling": active,
            "parent_cpu_seconds": 90, "child_cpu_seconds": [90, 90], "hard_cpu_sum": 270,
            "retained_cpu_ns": 300000000000, "wall_seconds": 600, "child_wall_seconds": 90,
            "child_fsize": 4 * MIB, "parent_fsize": max(archive_bytes, MEMBER_CAP),
            "as_bytes": 2 * GIB, "rss_exclusive": GIB, "output_limit": MIB}


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def opened(path, directory=False):
    """Hold no-follow directory chain and input FD; never resolve through links.

The portable branch exists only for local protocol QA; native execution always
uses the Linux dir_fd branch and observes st_blocks separately.
"""
    path = path.absolute()
    if sys.platform != "linux":
        before = path.lstat()
        if directory:
            require(stat.S_ISDIR(before.st_mode), "linked/replaced directory")
            yield None, before
            require(identity(before) == identity(path.lstat()), "directory changed")
            return
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        try:
            require(not path.is_symlink() and identity(before)[:-1] == identity(os.fstat(fd))[:-1], "linked/replaced input")
            yield fd, before
            require(identity(before)[:-1] == identity(os.fstat(fd))[:-1]
                    and identity(before) == identity(path.lstat()), "held input changed")
        finally:
            os.close(fd)
        return
    fds, bindings = [], []
    try:
        parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        fds.append(parent)
        for component in path.parts[1:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            before = os.fstat(child)
            bindings.append((parent, component, child, before))
            fds.append(child)
            parent = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        if directory:
            flags |= os.O_DIRECTORY
        fd = os.open(path.name, flags, dir_fd=parent)
        fds.append(fd)
        before = os.fstat(fd)
        bindings.append((parent, path.name, fd, before))
        yield fd, before
        for ancestor, name, held, expected in bindings:
            current = os.stat(name, dir_fd=ancestor, follow_symlinks=False)
            # Ancestor directory content may legitimately grow elsewhere; bind
            # its identity/mode, while the selected held input has a full epoch.
            if held == fd:
                require(identity(expected) == identity(os.fstat(held)) == identity(current), "held input changed")
            else:
                require((expected.st_dev, expected.st_ino, expected.st_mode) ==
                        (current.st_dev, current.st_ino, current.st_mode), "input ancestor replaced")
    finally:
        for fd in reversed(fds):
            os.close(fd)


def file_record(path, maximum=MEMBER_CAP):
    with opened(path) as (fd, before):
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 <= before.st_size <= maximum, "not a bounded single-link regular input")
        checksum, count = hashlib.sha256(), 0
        while block := os.read(fd, min(MIB, maximum + 1 - count)):
            count += len(block)
            require(count <= maximum, "input grew beyond bound")
            checksum.update(block)
        return {"size": count, "sha256": checksum.hexdigest()}


def data_bytes(path, maximum, expected):
    """Ordinary-user-owned pinned DATA, never an executable import path."""
    sha(expected)
    with opened(path) as (fd, before):
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 <= before.st_size <= maximum, "invalid bounded input data")
        raw = bytearray()
        while piece := os.read(fd, min(MIB, maximum + 1 - len(raw))):
            raw.extend(piece)
            require(len(raw) <= maximum, "input data exceeded")
        require(len(raw) == before.st_size and digest(raw) == expected, "input data hash differs")
        return bytes(raw)


def bootstrap_source(sources):
    names = ("tests/native_context_chain.py", "tests/native_context_chain_catalogue.py", *HELPERS)
    require(type(sources) is dict and set(sources) == set(names), "nonfixed bootstrap members")
    for name, raw in sources.items():
        require(type(raw) is bytes and 0 < len(raw) <= MIB, "bootstrap member bound")
        if name in HELPERS:
            require(digest(raw) == HELPERS[name], "bootstrap helper pin differs")
    # Insertion order is fixed so Root can reproduce and pin the exact stdin.
    literal = repr({name: sources[name] for name in names}).encode("ascii")
    result = (b"# Reviewed Task57 stdlib-only stdin bootstrap\n_REVIEWED_BOOTSTRAP = " + literal +
              b"\nexec(compile(_REVIEWED_BOOTSTRAP['tests/native_context_chain.py'], "
              b"'<reviewed-task57-parent>', 'exec'), globals())\n")
    require(len(result) <= 2 * MIB, "stdin bootstrap allowance exceeded")
    return result


def launcher(archive_path, archive_sha, manifest_path, manifest_sha):
    raw_manifest = data_bytes(manifest_path, MANIFEST_CAP, manifest_sha)
    manifest = decode(raw_manifest)
    validate_manifest(manifest, manifest["commit"])
    require(manifest["archive"]["sha256"] == archive_sha, "launcher archive pin differs")
    raw = data_bytes(archive_path, ARCHIVE_CAP, archive_sha)
    members = archive_members(raw, manifest["code"])
    names = ("tests/native_context_chain.py", "tests/native_context_chain_catalogue.py", *HELPERS)
    return bootstrap_source({name: members[name] for name in names})


def copy_file(source, target, entry):
    with opened(source) as (src, before):
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == entry["size"] <= MEMBER_CAP, "copy input size/type differs")
        flags = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        dst = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | flags, 0o600)
        try:
            total, checksum = 0, hashlib.sha256()
            while piece := os.read(src, min(MIB, entry["size"] + 1 - total)):
                total += len(piece)
                require(total <= entry["size"], "copy source grew")
                checksum.update(piece)
                view = memoryview(piece)
                while view:
                    n = os.write(dst, view)
                    require(n > 0, "copy write stalled")
                    view = view[n:]
            os.fsync(dst)
            require(total == entry["size"] and checksum.hexdigest() == entry["sha256"], "copy hash differs")
            if hasattr(os, "fchmod"):
                os.fchmod(dst, 0o444)
        finally:
            os.close(dst)


def walk(root, selected=None):
    """Bounded, no-linked members; rechecks every directory epoch after traversal."""
    entries, epochs = [], []
    def visit(path, depth):
        require(depth <= 20 and len(entries) + len(epochs) < MAX_FILES, "tree bound exceeded")
        before = path.lstat()
        require(stat.S_ISDIR(before.st_mode), "linked/non-directory namespace")
        epochs.append((path, identity(before)))
        with opened(path, directory=True) as (fd, _held):
            with os.scandir(fd if sys.platform == "linux" else path) as scan:
                children = []
                for child in scan:
                    require(len(children) < MAX_FILES, "directory count exceeded")
                    children.append(child.name)
        for name in sorted(children):
            child = path / name
            info = child.lstat()
            if stat.S_ISDIR(info.st_mode):
                # Bytecode is not needed under -B and is explicitly excluded.
                if selected is None or name != "__pycache__":
                    visit(child, depth + 1)
            else:
                require(not name.endswith((".pyc", ".pyo")), "unexpected loose bytecode")
                value = file_record(child)
                entries.append({"path": child.relative_to(root).as_posix(), **value})
                require(len(entries) < MAX_FILES, "file count exceeded")
    if selected is None:
        visit(root, 0)
    else:
        before = identity(root.lstat())
        for name in selected:
            path = root / name
            if stat.S_ISDIR(path.lstat().st_mode):
                visit(path, 0)
            else:
                entries.append({"path": name, **file_record(path)})
        require(identity(root.lstat()) == before, "selected root changed")
    for path, before in epochs:
        require(identity(path.lstat()) == before, "directory changed during scan")
    return sorted(entries, key=lambda item: item["path"])


def workspace_sample(root, slots, metadata_cap):
    """Exact file AND directory names, logical AND allocated quiescent sizes."""
    allowed_dirs = {str(p) for name in slots for p in PurePosixPath(name).parents}
    found_dirs, epochs = [], []
    metadata_logical = metadata_allocated = 0
    def directories(path, depth):
        nonlocal metadata_logical, metadata_allocated
        require(depth <= 20 and len(found_dirs) < MAX_FILES, "workspace directory bound")
        before = path.lstat()
        require(stat.S_ISDIR(before.st_mode), "linked workspace directory")
        name = path.relative_to(root).as_posix()
        require(name in allowed_dirs, "unknown workspace directory")
        epochs.append((path, identity(before)))
        metadata_logical += before.st_size
        metadata_allocated += getattr(before, "st_blocks", 0) * 512
        found_dirs.append({"path": name, "logical": before.st_size, "allocated": getattr(before, "st_blocks", 0) * 512})
        with opened(path, directory=True) as (fd, _held):
            with os.scandir(fd if sys.platform == "linux" else path) as scan:
                names = []
                for child in scan:
                    require(len(names) < MAX_FILES, "workspace directory entries exceeded")
                    if child.is_dir(follow_symlinks=False):
                        names.append(child.name)
        for name in sorted(names):
            directories(path / name, depth + 1)
    directories(root, 0)
    files = walk(root)
    logical = allocated = 0
    for item in files:
        require(item["path"] in slots and item["size"] <= slots[item["path"]], "unplanned/oversized workspace file")
        info = (root / item["path"]).lstat()
        blocks = getattr(info, "st_blocks", 0) * 512
        require(max(item["size"], blocks) <= slots[item["path"]], "file allocation exceeded slot")
        item["allocated"] = blocks
        logical += item["size"]
        allocated += blocks
    require(max(metadata_logical, metadata_allocated) <= metadata_cap, "metadata reservation exceeded")
    for path, epoch in epochs:
        require(identity(path.lstat()) == epoch, "workspace was not quiescent")
    return {"files": files, "directories": found_dirs, "logical": logical + metadata_logical,
            "allocated": allocated + metadata_allocated, "metadata_logical": metadata_logical,
            "metadata_allocated": metadata_allocated}


def validate_manifest(value, commit):
    require(type(value) is dict and set(value) == {"format", "commit", "archive", "code", "dependencies",
            "dependency_source", "packages", "runtime", "plan"}, "catalogue shape")
    require(value["format"] == FORMAT and value["commit"] == commit and type(commit) is str
            and len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "reviewed commit differs")
    require(value["dependency_source"] == str(DEPENDENCY_SOURCE) and value["packages"] == list(PACKAGES),
            "nonfixed dependency installation")
    code = records(value["code"], ARCHIVE_CAP)
    require(set(REQUIRED) <= code.keys() and all(n.endswith(".py") and not n.startswith(".") for n in code),
            "missing route code or non-Python archive")
    for name, expected in (HELPERS | {TASK54: TASK54_SHA}).items():
        require(code[name]["sha256"] == expected, "independently reviewed owner pin differs")
    deps = records(value["dependencies"], DEPENDENCY_CAP)
    require({n.split("/", 1)[0] for n in deps} == set(PACKAGES), "incomplete/foreign dependency roots")
    destinations = ["code/" + n for n in code] + ["dependencies/" + n for n in deps] + list(attempt_slots())
    directories = {str(p) for n in destinations for p in PurePosixPath(n).parents}
    require(len(destinations) + len(directories) + 32 < MAX_FILES, "aggregate namespace exceeds bound")
    ar = value["archive"]
    require(type(ar) is dict and set(ar) == {"size", "sha256"}, "archive shape")
    sha(ar["sha256"])
    integer(ar["size"], ARCHIVE_CAP)
    runtime = value["runtime"]
    require(type(runtime) is dict and set(runtime) == {"executable", "executable_sha256", "python", "kernel",
            "stdlib_search_path", "closure_status"}, "runtime observation shape")
    sha(runtime["executable_sha256"])
    require(runtime["closure_status"] == "observed-system-runtime-not-transitive-B-closure", "false runtime closure")
    expected = resource_plan(ar["size"], sum(x["size"] for x in code.values()), sum(x["size"] for x in deps.values()))
    require(value["plan"] == expected, "resource plan differs")
    return value


def inventory(archive_path, commit):
    require(sys.platform == "linux" and os.uname().machine == "x86_64", "native inventory host required")
    ar = file_record(archive_path, ARCHIVE_CAP)
    raw = data_bytes(archive_path, ARCHIVE_CAP, ar["sha256"])
    code = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
        for i, member in enumerate(tar):
            require(i < MAX_FILES, "archive count exceeded")
            if member.isdir():
                continue
            require(member.isreg() and member.size <= MEMBER_CAP, "archive link/size")
            stream = tar.extractfile(member)
            with stream:
                body = stream.read(MEMBER_CAP + 1)
            code.append({"path": member.name, "size": len(body), "sha256": digest(body)})
    code.sort(key=lambda x: x["path"])
    archive_members(raw, code)
    dependencies = walk(DEPENDENCY_SOURCE, PACKAGES)
    executable = Path("/proc/self/exe").resolve()
    result = {"format": FORMAT, "commit": commit, "archive": ar, "code": code,
              "dependencies": dependencies, "dependency_source": str(DEPENDENCY_SOURCE),
              "packages": list(PACKAGES), "runtime": {
                  "executable": str(executable), "executable_sha256": file_record(executable)["sha256"],
                  "python": sys.version, "kernel": list(os.uname()), "stdlib_search_path": list(sys.path),
                  "closure_status": "observed-system-runtime-not-transitive-B-closure"},
              "plan": resource_plan(ar["size"], sum(x["size"] for x in code), sum(x["size"] for x in dependencies))}
    validate_manifest(result, commit)
    encoded = canonical(result)
    require(len(encoded) <= MANIFEST_CAP, "catalogue output exceeded")
    return encoded


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "inventory":
        sys.stdout.buffer.write(inventory(Path(sys.argv[2]), sys.argv[3]) + b"\n")
    elif len(sys.argv) == 6 and sys.argv[1] == "launcher":
        sys.stdout.buffer.write(launcher(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), sys.argv[5]))
    else:
        raise ChainError("inventory ARCHIVE COMMIT or launcher ARCHIVE SHA MANIFEST SHA only")
