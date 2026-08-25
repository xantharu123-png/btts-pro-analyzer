#!/usr/bin/env python3
"""Provision the external 15K HMAC key once, atomically and fail-closed."""

from __future__ import annotations

import argparse
from contextlib import closing
import ctypes
import errno
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import sys


PRODUCTION_KEY = Path("/etc/betboy/challenge-ledger-hmac.key")
PRODUCTION_MARKER = Path(
    "/etc/betboy/challenge-ledger-v2-migrated.json"
)
PRODUCTION_ROOT = Path("/opt/betboy/app")
DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
EXCLUDED_PARTS = {
    ".codex_test_venv",
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    ".venv",
    "__pycache__",
    "backups_runtime",
}
HMAC_SCHEMA_COLUMNS = {
    "financial_chain_version",
    "financial_anchor_hash",
    "settlement_chain_version",
    "settlement_anchor_hash",
}


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_key(
    path: Path,
    *,
    production: bool,
    group_id: int | None,
) -> bytes | None:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError("Ledger HMAC key cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        payload = os.read(descriptor, 1024)
        extra = os.read(descriptor, 1)
    finally:
        os.close(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError("Ledger HMAC key must be one regular file")
    if production:
        if (
            group_id is None
            or info.st_uid != 0
            or info.st_gid != group_id
            or stat.S_IMODE(info.st_mode) != 0o640
        ):
            raise RuntimeError("Ledger HMAC key must be root:betboy mode 0640")
    elif os.name != "nt" and info.st_mode & (stat.S_IWGRP | stat.S_IRWXO):
        raise RuntimeError("Local ledger HMAC key permissions are unsafe")
    if (
        extra
        or len(payload) != 65
        or not payload.endswith(b"\n")
        or any(byte not in b"0123456789abcdef" for byte in payload[:-1])
    ):
        raise RuntimeError("Ledger HMAC key has an invalid format")
    return payload


def _challenge_anchor_state(root: Path, *, fresh_install: bool) -> str | None:
    if root.is_symlink():
        raise RuntimeError("Application root must not be a symlink")
    resolved_root = root.resolve(strict=True)
    if not stat.S_ISDIR(os.lstat(resolved_root).st_mode):
        raise RuntimeError("Application root must be a real directory")
    for directory, dirnames, filenames in os.walk(
        resolved_root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(directory)
        kept: list[str] = []
        for name in dirnames:
            child = current / name
            if name in EXCLUDED_PARTS or name.startswith(".pytest_tmp"):
                continue
            child_info = os.lstat(child)
            if stat.S_ISLNK(child_info.st_mode):
                raise RuntimeError("Key anchor scan encountered a directory symlink")
            if not stat.S_ISDIR(child_info.st_mode):
                raise RuntimeError("Key anchor scan encountered a non-directory")
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            if path.suffix.casefold() not in DATABASE_SUFFIXES:
                continue
            info = os.lstat(path)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or info.st_nlink != 1
            ):
                raise RuntimeError("Key anchor scan found an unsafe database")
            uri = path.resolve(strict=True).as_uri() + "?mode=ro"
            try:
                with closing(
                    sqlite3.connect(uri, uri=True, timeout=30)
                ) as connection:
                    connection.execute("PRAGMA query_only=ON")
                    tables = {
                        str(row[0])
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    if "challenge_settings" not in tables:
                        if "challenge_integrity_checkpoint" in tables:
                            return "challenge integrity checkpoint"
                        continue
                    if fresh_install:
                        return "pre-existing challenge database"
                    columns = {
                        str(row[1])
                        for row in connection.execute(
                            "PRAGMA table_info(challenge_settings)"
                        )
                    }
                    if (
                        "challenge_integrity_checkpoint" in tables
                        or "challenge_settlement_events" in tables
                        or HMAC_SCHEMA_COLUMNS & columns
                    ):
                        return "HMAC-era challenge database"
            except sqlite3.Error as exc:
                raise RuntimeError(
                    f"Key anchor scan cannot inspect database: {path}"
                ) from exc
    return None


def _rename_no_replace(
    source: Path,
    destination: Path,
    *,
    allow_link_fallback: bool,
) -> bool:
    """Atomically publish without replacing an existing destination."""

    if os.name != "nt":
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(source),
                -100,
                os.fsencode(destination),
                1,
            )
            if result == 0:
                return True
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                return False
            if error not in {errno.ENOSYS, errno.EINVAL}:
                raise OSError(error, os.strerror(error), destination)
            if not allow_link_fallback:
                raise RuntimeError(
                    "Atomic no-replace key publication is unavailable"
                )
    if not allow_link_fallback:
        raise RuntimeError("Atomic no-replace key publication is unavailable")
    try:
        os.link(source, destination, follow_symlinks=False)
    except FileExistsError:
        return False
    source.unlink()
    return True


def _publish_candidate(
    path: Path,
    *,
    production: bool,
    group_id: int | None,
) -> None:
    temporary = path.parent / (
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.partial"
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        descriptor = os.open(temporary, flags, 0o600)
        try:
            payload = secrets.token_hex(32).encode("ascii") + b"\n"
            written = 0
            while written < len(payload):
                count = os.write(descriptor, payload[written:])
                if count <= 0:
                    raise OSError("short ledger HMAC key write")
                written += count
            if production:
                if group_id is None:
                    raise RuntimeError("Production ledger key group is unavailable")
                os.fchown(descriptor, 0, group_id)
                os.fchmod(descriptor, 0o640)
            elif os.name != "nt":
                os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _rename_no_replace(
            temporary,
            path,
            allow_link_fallback=not production,
        )
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
            _fsync_directory(path.parent)
        except FileNotFoundError:
            pass


def ensure_integrity_key(
    key_path: Path,
    application_root: Path,
    marker_path: Path,
    *,
    production: bool = False,
    group_id: int | None = None,
    fresh_install: bool = False,
) -> bytes:
    key_path = Path(os.path.abspath(os.fspath(key_path)))
    application_root = Path(os.path.abspath(os.fspath(application_root)))
    marker_path = Path(os.path.abspath(os.fspath(marker_path)))
    if production and (
        os.name == "nt"
        or os.geteuid() != 0
        or key_path != PRODUCTION_KEY
        or marker_path != PRODUCTION_MARKER
        or application_root != PRODUCTION_ROOT
    ):
        raise RuntimeError("Production ledger key paths or authority are invalid")
    parent_info = os.lstat(key_path.parent)
    if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode):
        raise RuntimeError("Ledger key directory must be a real directory")
    if production and (
        group_id is None
        or parent_info.st_uid != 0
        or parent_info.st_gid != group_id
        or stat.S_IMODE(parent_info.st_mode) != 0o750
    ):
        raise RuntimeError("Ledger key directory must be root:betboy mode 0750")

    if fresh_install:
        if os.path.lexists(marker_path):
            raise RuntimeError("Fresh install has a pre-existing migration marker")
        anchor = _challenge_anchor_state(application_root, fresh_install=True)
        if anchor is not None:
            raise RuntimeError(f"Fresh install has {anchor}")

    existing = _read_key(
        key_path,
        production=production,
        group_id=group_id,
    )
    if existing is not None:
        return existing

    if os.path.lexists(marker_path):
        raise RuntimeError(
            "Ledger HMAC key is missing while a migration marker exists; "
            "restore the original key"
        )
    anchor = _challenge_anchor_state(application_root, fresh_install=fresh_install)
    if anchor is not None:
        raise RuntimeError(
            f"Ledger HMAC key is missing while {anchor} exists; "
            "restore the original key"
        )
    # Recheck immediately before no-clobber publication. Runtime writers must
    # already be stopped by the updater, so this closes the remaining local race.
    if os.path.lexists(marker_path) or _challenge_anchor_state(
        application_root,
        fresh_install=fresh_install,
    ) is not None:
        raise RuntimeError("Ledger key anchor appeared during provisioning")
    _publish_candidate(
        key_path,
        production=production,
        group_id=group_id,
    )
    result = _read_key(
        key_path,
        production=production,
        group_id=group_id,
    )
    if result is None:
        raise RuntimeError("Ledger HMAC key publication did not persist")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--group")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--fresh-install", action="store_true")
    args = parser.parse_args()
    group_id = None
    if args.group and os.name != "nt":
        import grp

        group_id = grp.getgrnam(args.group).gr_gid
    try:
        ensure_integrity_key(
            args.key,
            args.application_root,
            args.marker,
            production=args.production,
            group_id=group_id,
            fresh_install=args.fresh_install,
        )
    except (OSError, RuntimeError, sqlite3.Error, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
