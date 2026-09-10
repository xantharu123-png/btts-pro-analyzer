"""Explicit Linux root-sealed SQLite transport; no permissive fallback.

Root is the trusted stager, not the verifier's application-code executor. The
application cannot change any path component, file bytes or SQLite companions.
The held descriptor and every ancestor remain bound across SQLite's path open.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import sys

from model_artifacts import ArtifactIntegrityError
from runtime_paths import RuntimeArtifactTrustError


def _directory_identity(info):
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeArtifactTrustError("sealed context ancestors must be root-owned and app-unwritable")
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid


def _file_identity(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & ~0o440):
        raise RuntimeArtifactTrustError("sealed context file must be root-owned single-link 0440 or stricter")
    return (info.st_dev, info.st_ino, info.st_nlink, info.st_mode, info.st_uid,
            info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _check_seal(path, descriptor, expected, ancestors):
    for name, fd, identity in ancestors:
        if (_directory_identity(os.fstat(fd)) != identity
                or _directory_identity(os.lstat(name)) != identity):
            raise RuntimeArtifactTrustError("sealed context ancestor changed identity")
    if _file_identity(os.fstat(descriptor)) != expected or _file_identity(os.lstat(path)) != expected:
        raise RuntimeArtifactTrustError("sealed context descriptor/path changed identity or bytes")
    for suffix in ("-wal", "-shm", "-journal"):
        if os.path.lexists(path.with_name(path.name + suffix)):
            raise RuntimeArtifactTrustError("sealed context has a SQLite companion")


def _stream_hash(descriptor, size):
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        block = os.read(descriptor, min(1024 * 1024, remaining))
        if not block:
            raise RuntimeArtifactTrustError("sealed context was truncated")
        digest.update(block)
        remaining -= len(block)
    if os.read(descriptor, 1):
        raise RuntimeArtifactTrustError("sealed context grew during verification")
    return digest.digest()


@contextmanager
def open_sealed_connection(path, *, max_bytes):
    """Yield query-only SQLite in a read transaction after proving the seal."""
    if sys.platform != "linux" or not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY")):
        raise RuntimeArtifactTrustError("sealed context file verification requires Linux DAC")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise RuntimeArtifactTrustError("invalid sealed context input budget")
    path = Path(path)
    if ".." in path.parts:
        raise RuntimeArtifactTrustError("sealed context path cannot traverse parents")
    path = path.absolute()
    connection = None
    try:
        with ExitStack() as stack:
            ancestors = []
            current = Path(path.anchor)
            parent_fd = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, parent_fd)
            ancestors.append((current, parent_fd, _directory_identity(os.fstat(parent_fd))))
            for part in path.parts[1:-1]:
                current = current / part
                parent_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                stack.callback(os.close, parent_fd)
                ancestors.append((current, parent_fd, _directory_identity(os.fstat(parent_fd))))
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
            stack.callback(os.close, descriptor)
            expected = _file_identity(os.fstat(descriptor))
            size = os.fstat(descriptor).st_size
            if size > max_bytes:
                raise RuntimeArtifactTrustError("sealed context input size exceeds budget")
            _check_seal(path, descriptor, expected, ancestors)
            from context_runtime import _validate_image_header
            _validate_image_header(os.read(descriptor, 100), size)
            before = _stream_hash(descriptor, size)
            _check_seal(path, descriptor, expected, ancestors)
            # The immutable promise is justified by DAC above, not accepted
            # from a caller boolean or used to bypass an untrusted live WAL.
            connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)
            stack.callback(connection.close)
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA cache_size=-8192")
            connection.execute("PRAGMA mmap_size=0")
            connection.execute("BEGIN")
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            _check_seal(path, descriptor, expected, ancestors)
            yield connection
            _check_seal(path, descriptor, expected, ancestors)
            if _stream_hash(descriptor, size) != before:
                raise RuntimeArtifactTrustError("sealed context SHA256 changed during verification")
            _check_seal(path, descriptor, expected, ancestors)
    except (OSError, MemoryError) as exc:
        raise RuntimeArtifactTrustError("sealed context input or resource verification failed") from exc
    except sqlite3.Error as exc:
        raise ArtifactIntegrityError("sealed context SQLite verification failed") from exc
