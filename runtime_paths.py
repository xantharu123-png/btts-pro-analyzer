"""Canonical paths for mutable BetBoy runtime artifacts.

Versioned seed/evidence files stay in their historical repository locations.
Services and scheduled jobs must write mutable state below ``runtime_state``
and generated reports below ``runtime_reports`` so a healthy production run
does not dirty the Git worktree.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat
import tempfile
from typing import BinaryIO, Iterator


PROJECT_ROOT = Path(__file__).resolve().parent


def _configured_dir(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else default


RUNTIME_STATE_DIR = _configured_dir(
    "BETBOY_RUNTIME_STATE_DIR",
    PROJECT_ROOT / "runtime_state",
)
RUNTIME_REPORT_DIR = _configured_dir(
    "BETBOY_REPORT_DIR",
    PROJECT_ROOT / "runtime_reports",
)

PIPELINE_LOG_DIR = RUNTIME_STATE_DIR / "logs"
TENNIS_RUNTIME_STATE_DIR = RUNTIME_STATE_DIR / "tennis"
TENNIS_MODEL_STATE_PATH = TENNIS_RUNTIME_STATE_DIR / "model_state.pkl"
TENNIS_CALIBRATION_WATCH_PATH = (
    TENNIS_RUNTIME_STATE_DIR / "calibration_watch_latest.json"
)
TENNIS_WEEKLY_REPORT_DIR = RUNTIME_REPORT_DIR / "tennis"

# Read-only compatibility inputs. These files may contain a versioned seed or
# historical evidence, but future automation must never overwrite them.
PACKAGED_TENNIS_MODEL_STATE_PATH = (
    PROJECT_ROOT / "tennis" / "data" / "model_state.pkl"
)
LEGACY_TENNIS_CALIBRATION_WATCH_PATH = (
    PROJECT_ROOT / "tennis" / "data" / "calibration_watch_latest.json"
)


class RuntimeArtifactTrustError(RuntimeError):
    """A mutable executable artifact crossed the documented trust boundary."""


def _absolute_without_resolving(path: Path) -> Path:
    """Return an absolute path without following a possibly hostile symlink."""

    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_symlink_components(path: Path) -> Path:
    """Reject symlinks in every existing component of ``path``.

    Runtime pickle files are executable Python input.  Following a symlink from
    a service-writable directory would let a different file silently become
    trusted, so both the leaf and its existing parents are checked.
    """

    absolute = _absolute_without_resolving(path)
    current = absolute
    while True:
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(mode):
                raise RuntimeArtifactTrustError(
                    f"runtime artifact path must not contain symlinks: {absolute}"
                )
            is_junction = getattr(current, "is_junction", None)
            if callable(is_junction) and is_junction():
                raise RuntimeArtifactTrustError(
                    f"runtime artifact path must not contain junctions: {absolute}"
                )
        parent = current.parent
        if parent == current:
            break
        current = parent
    return absolute


def _trusted_owner_ids() -> set[int] | None:
    """Return trusted POSIX owners; Windows ownership is enforced by ACLs."""

    get_effective_uid = getattr(os, "geteuid", None)
    if get_effective_uid is None:
        return None
    return {0, int(get_effective_uid())}


def _validate_trusted_pickle_stat(path: Path, file_stat: os.stat_result) -> None:
    if not stat.S_ISREG(file_stat.st_mode):
        raise RuntimeArtifactTrustError(
            f"runtime pickle must be a regular file: {path}"
        )
    trusted_owners = _trusted_owner_ids()
    if trusted_owners is None:
        return
    if file_stat.st_uid not in trusted_owners:
        raise RuntimeArtifactTrustError(
            f"runtime pickle has an untrusted owner: {path}"
        )
    if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise RuntimeArtifactTrustError(
            f"runtime pickle must not be group/world writable: {path}"
        )


def validate_trusted_pickle_path(path: Path) -> Path:
    """Validate a pickle path without deserializing it.

    Pickle remains necessary for the current model classes in this release.
    It must therefore only be loaded from a non-symlink regular file owned by
    the current service account or root (and not group/world writable on
    POSIX).  Pickles downloaded from providers or copied from an untrusted host
    are never valid runtime input.
    """

    absolute = _assert_no_symlink_components(Path(path))
    file_stat = os.lstat(absolute)
    _validate_trusted_pickle_stat(absolute, file_stat)
    return absolute


@contextmanager
def open_trusted_pickle(path: Path) -> Iterator[BinaryIO]:
    """Open a validated pickle for reading without following the leaf symlink."""

    absolute = validate_trusted_pickle_path(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(absolute, flags)
    try:
        opened_stat = os.fstat(descriptor)
        _validate_trusted_pickle_stat(absolute, opened_stat)
        current_stat = os.lstat(absolute)
        if stat.S_ISLNK(current_stat.st_mode) or (
            opened_stat.st_dev,
            opened_stat.st_ino,
        ) != (
            current_stat.st_dev,
            current_stat.st_ino,
        ):
            raise RuntimeArtifactTrustError(
                f"runtime pickle changed while it was being opened: {absolute}"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            yield handle
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def atomic_write_bytes(path: Path, payload: bytes) -> Path:
    """Replace ``path`` atomically after fully writing and syncing a temp file."""

    target = _absolute_without_resolving(Path(path))
    _assert_no_symlink_components(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(target.parent)
    if target.is_symlink():
        raise RuntimeArtifactTrustError(
            f"runtime artifact target must not be a symlink: {target}"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        if os.name != "nt":
            directory_descriptor = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return target


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Encode and atomically replace a mutable text artifact."""

    return atomic_write_bytes(Path(path), text.encode(encoding))
