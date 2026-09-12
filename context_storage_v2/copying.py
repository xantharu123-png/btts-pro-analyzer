"""A complete, private legacy copy, without publication or representation change.

This C1 boundary preserves every closed-schema logical key, SQLite type and raw
value. It copies a held standalone input and independently inventories both
readers. A returned receipt is historical identity evidence, not a B proof or a
live reader, and never permits deleting/replacing the original.

The complete source-plus-copy pair and the supplied *whole* workspace directory
are charged here. Other active inputs, open/unlinked SQLite temporary files,
archives outside that directory and process CPU/RAM still belong to the future
global/native preparation owner. These checks are not an OS disk quota or a
claim that the entire C/B resource contract has already been implemented.
"""
from dataclasses import dataclass, fields
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time

from context_runtime_transaction import TrackedConnection
from runtime_paths import _assert_no_symlink_components

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits
from .inventory import RawInventory, _HeldRead, compare_raw, inventory_raw


COPY_FORMAT = "context-complete-legacy-copy-v2"
_METADATA_RESERVE = 64 * 1024
_MAX_ENTRIES = 100000
_MAX_DEPTH = 32
_MAX_COPY_SECONDS = 300


@dataclass(frozen=True)
class CopyReceipt:
    format_version: str
    path: Path
    source_sha256: str
    copy_sha256: str
    source_bytes: int
    copy_bytes: int
    inventory: RawInventory


def _limits_identity(limits):
    if type(limits) is not StorageLimits:
        raise StorageLimitError("complete copy requires the exact approved limits")
    StorageLimits.__post_init__(limits)
    return tuple(getattr(limits, field.name) for field in fields(StorageLimits))


def _file_identity(path):
    _assert_no_symlink_components(path)
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise StorageIntegrityError("complete copy requires one regular standalone file")
    return (value.st_dev, value.st_ino, value.st_nlink, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _no_companions(path):
    if any(os.path.lexists(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise StorageIntegrityError("complete copy source has a SQLite companion")


def _directory_identity(path):
    _assert_no_symlink_components(path)
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode):
        raise StorageIntegrityError("copy workspace must be an existing real directory")
    return value.st_dev, value.st_ino, value.st_mode


def _workspace_bytes(directory):
    """Bounded traversal of all named files, including nested and hidden ones."""
    count = 0
    def visit(path, depth):
        nonlocal count
        if depth > _MAX_DEPTH:
            raise StorageLimitError("copy workspace exceeds its explicit traversal depth")
        _directory_identity(path)
        total = 0
        with os.scandir(path) as entries:
            for entry in entries:
                count += 1
                if count > _MAX_ENTRIES:
                    raise StorageLimitError("copy workspace exceeds its explicit entry budget")
                candidate = Path(entry.path)
                _assert_no_symlink_components(candidate)
                # Windows DirEntry's cached stat lacks a usable hard-link
                # count; the real owning lstat is required for this boundary.
                value = candidate.lstat()
                if stat.S_ISDIR(value.st_mode):
                    total += max(value.st_size, getattr(value, "st_blocks", 0) * 512)
                    total += visit(candidate, depth + 1)
                elif stat.S_ISREG(value.st_mode) and value.st_nlink == 1:
                    total += max(value.st_size, getattr(value, "st_blocks", 0) * 512)
                else:
                    raise StorageIntegrityError("copy workspace contains a link or special file")
        return total
    return visit(directory, 0)


def _hash_file(path, block_bytes, check):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            check()
            piece = stream.read(min(block_bytes, 1024**2))
            if not piece:
                break
            hasher.update(piece)
    check()
    return hasher.hexdigest()


def copy_legacy(source, *, directory, expected_source_sha256, limits=DEFAULT_LIMITS) -> CopyReceipt:
    """Create one new private copy; no source writes, reused output or commits.

    The caller supplies an already sealed source and the whole new job workspace.
    expected_source_sha256 comes from that separately sealed input owner; it is
    not itself a filesystem seal or a grant of semantic approval.
    POSIX DAC sealing and other processes' allocations require the owning native
    boundary, not a caller-supplied success flag. Failure returns no receipt and
    intentionally leaves any newly created partial output charged to the job.
    """
    limit_identity = _limits_identity(limits)
    if type(expected_source_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256) is None:
        raise StorageIntegrityError("complete copy needs the original sealed source digest")
    deadline = time.monotonic() + _MAX_COPY_SECONDS
    if type(source) is not TrackedConnection:
        raise StorageIntegrityError("complete copy requires its exact source connection")
    databases = tuple(sqlite3.Connection.execute(source, "PRAGMA database_list"))
    main = next((row[2] for row in databases if row[1] == "main"), None)
    if not main:
        raise StorageIntegrityError("complete copy requires an on-disk source")
    source_path = _assert_no_symlink_components(Path(main))
    source_identity = _file_identity(source_path)
    source_size = source_identity[4]
    _no_companions(source_path)
    # A checkpointed WAL file can have no companions while retaining 02/02 in
    # its header. Reject before SQLite's first schema/page read can create WAL
    # side files, even on a mode=ro connection.
    with source_path.open("rb") as header_stream:
        header = header_stream.read(100)
    if (len(header) != 100 or header[:16] != b"SQLite format 3\0"
            or header[18:20] != b"\x01\x01"):
        raise StorageIntegrityError("complete copy requires a standalone rollback-mode SQLite header")
    if _file_identity(source_path) != source_identity:
        raise StorageIntegrityError("complete copy source changed before admission")
    source_guard = _HeldRead(source)
    directory = _assert_no_symlink_components(Path(directory))
    directory_identity = _directory_identity(directory)
    page_size = source.execute("PRAGMA main.page_size").fetchone()[0]
    page_count = source.execute("PRAGMA main.page_count").fetchone()[0]
    if (type(page_size) is not int or type(page_count) is not int or page_count < 1
            or page_size < 512 or page_size > 65536 or page_size & (page_size - 1)):
        raise StorageIntegrityError("complete copy has invalid source page dimensions")
    image_size = page_size * page_count
    if page_size > limits.block_bytes:
        raise StorageLimitError("one SQLite page exceeds the explicit copy block limit")
    if max(source_size, image_size) + source_size > limits.input_bytes:
        raise StorageLimitError("combined complete source and copy exceed input admission")

    def source_check():
        if _limits_identity(limits) != limit_identity:
            raise StorageLimitError("complete copy limits changed during execution")
        if time.monotonic() > deadline:
            raise StorageLimitError("complete copy exceeded its bounded operation deadline")
        source_guard.check()
        if _file_identity(source_path) != source_identity:
            raise StorageIntegrityError("complete copy source changed during execution")
        _no_companions(source_path)
        if _directory_identity(directory) != directory_identity:
            raise StorageIntegrityError("complete copy workspace identity changed")

    def capacity_check(remaining):
        source_check()
        if _workspace_bytes(directory) + remaining + _METADATA_RESERVE > limits.workspace_bytes:
            raise StorageLimitError("complete copy and existing workspace exceed allocation")
        if shutil.disk_usage(directory).free < limits.min_free_bytes + remaining + _METADATA_RESERVE:
            raise StorageLimitError("complete copy cannot preserve the free-space reserve")

    capacity_check(source_size)
    before = inventory_raw(source, limits=limits)
    source_hash = _hash_file(source_path, limits.block_bytes, source_check)
    if source_hash != expected_source_sha256:
        raise StorageIntegrityError("complete copy input differs from its sealed source digest")
    capacity_check(source_size)
    allocation = Path(tempfile.mkdtemp(prefix="context-copy-", dir=directory))
    copied_path = allocation / "legacy-copy.sqlite"
    # Atomic exclusive creation prevents overwriting even an unexpectedly
    # pre-existing output. The native owner additionally owns the private tree.
    fd = os.open(copied_path, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0), 0o600)
    source_fd = reader = None
    try:
        # Keep this exact newly-created descriptor until verification finishes.
        # Never reopen an output by path for writing: a replacement at such a
        # reopen could overwrite an unrelated existing database before rejection.
        allocated = os.fstat(fd)
        file_id = (allocated.st_dev, allocated.st_ino)
        source_fd = os.open(source_path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        def bound_files():
            source_check()
            source_info = os.fstat(source_fd)
            actual_source = (source_info.st_dev, source_info.st_ino, source_info.st_nlink,
                             source_info.st_mode, source_info.st_size,
                             source_info.st_mtime_ns, source_info.st_ctime_ns)
            # Windows fstat and path stat use different ctime semantics. The
            # complete path identity (including ctime) is already held above;
            # bind the shared handle/path identity and mtime without coercion.
            if actual_source[:6] != source_identity[:6]:
                raise StorageIntegrityError("complete copy source descriptor changed")
            output_info = os.fstat(fd)
            output_path = _file_identity(copied_path)
            if (output_info.st_dev, output_info.st_ino) != file_id or output_info.st_nlink != 1:
                raise StorageIntegrityError("complete copy output descriptor changed")
            if output_path[:2] != file_id or output_path[4] != output_info.st_size:
                raise StorageIntegrityError("complete copy output path was replaced")
        bound_files()
        written, actual_hash = 0, hashlib.sha256()
        while written < source_size:
            bound_files()
            piece = os.read(source_fd, min(source_size - written, limits.block_bytes, 1024**2))
            if not piece:
                raise StorageIntegrityError("complete copy source ended before its bound size")
            bound_files()
            actual_hash.update(piece)
            offset = 0
            while offset < len(piece):
                bound_files()
                count = os.write(fd, memoryview(piece)[offset:])
                if count <= 0:
                    raise StorageIntegrityError("complete copy made no output progress")
                offset += count
                written += count
                bound_files()
            capacity_check(source_size - written)
        if os.read(source_fd, 1) or actual_hash.hexdigest() != source_hash:
            raise StorageIntegrityError("complete copy source raw bytes changed")
        os.fsync(fd)
        bound_files()
        _no_companions(copied_path)
        copy_identity = _file_identity(copied_path)
        if copy_identity[4] != source_size:
            raise StorageIntegrityError("complete copy image size differs from source dimensions")
        reader = sqlite3.connect(copied_path.as_uri() + "?mode=ro", uri=True, factory=TrackedConnection)
        reader.execute("PRAGMA query_only=ON")
        reader.execute("PRAGMA trusted_schema=OFF")
        reader.execute("BEGIN")
        complete = compare_raw(source, reader, limits=limits)
        if complete != before:
            raise StorageIntegrityError("complete copy source inventory changed")
        copy_hash = _hash_file(copied_path, limits.block_bytes, bound_files)
        if _file_identity(copied_path) != copy_identity or copy_hash != source_hash:
            raise StorageIntegrityError("complete copied image changed during verification")
        if _hash_file(source_path, limits.block_bytes, source_check) != source_hash:
            raise StorageIntegrityError("complete copy source raw bytes changed")
        capacity_check(0)
        return CopyReceipt(COPY_FORMAT, copied_path, source_hash, copy_hash, source_size,
                           copy_identity[4], complete)
    except sqlite3.Error as exc:
        raise StorageIntegrityError("complete private copy could not be established") from exc
    finally:
        if reader is not None:
            reader.close()
        if source_fd is not None:
            os.close(source_fd)
        os.close(fd)
