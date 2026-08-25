#!/usr/bin/env python3
"""Stage consistent SQLite snapshots for the hardened BetBoy backup job."""

from __future__ import annotations

import argparse
from contextlib import closing
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any


DATABASE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})
EXCLUDED_PARTS = frozenset(
    {
        ".codex_test_venv",
        ".git",
        ".pytest_cache",
        ".pytest_tmp",
        ".streamlit",
        "__pycache__",
        "backups_runtime",
    }
)
MANIFEST_NAME = "manifest.json"
PRODUCTION_LIVE_ROOT = Path("/opt/betboy/app")
PRODUCTION_STAGE_OUTER = Path("/tmp/betboy-backup-stage")
PRODUCTION_CURRENT_STAGE = PRODUCTION_STAGE_OUTER / "current"
PRODUCTION_LIVE_USER = "betboy"
PRODUCTION_BACKUP_GROUP = "betboy-backup"

CAP_CHOWN = 0
CAP_SETGID = 6
CAP_SETUID = 7
REQUIRED_CAPABILITIES = (1 << CAP_CHOWN) | (1 << CAP_SETGID) | (1 << CAP_SETUID)
PR_GET_DUMPABLE = 3
PR_SET_DUMPABLE = 4


def _fsync_file(path: Path) -> None:
    with path.open("rb+") as handle:
        os.fsync(handle.fileno())


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


def _validated_directory(path: Path, label: str) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path)))
    if lexical.is_symlink():
        raise RuntimeError(f"{label} must not be a symlink")
    resolved = lexical.resolve(strict=True)
    if resolved != lexical:
        raise RuntimeError(f"{label} must not traverse a symlink")
    info = os.lstat(resolved)
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"{label} must be a real directory")
    return resolved


def discover_databases(live_root: Path) -> list[Path]:
    root = _validated_directory(live_root, "Live application root")
    databases: list[Path] = []

    def fail_walk(error: OSError) -> None:
        raise RuntimeError("Cannot traverse the live database root") from error

    for directory, dirnames, filenames in os.walk(
        root,
        topdown=True,
        onerror=fail_walk,
        followlinks=False,
    ):
        current = Path(directory)
        kept: list[str] = []
        for name in dirnames:
            if name in EXCLUDED_PARTS:
                continue
            child = current / name
            child_info = os.lstat(child)
            if stat.S_ISLNK(child_info.st_mode):
                raise RuntimeError("Database path must not traverse a symlink")
            if not stat.S_ISDIR(child_info.st_mode):
                raise RuntimeError("Database traversal encountered a non-directory")
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
                raise RuntimeError(
                    "Database source must be one regular, non-linked file"
                )
            try:
                path.resolve(strict=True).relative_to(root)
            except ValueError as exc:
                raise RuntimeError("Database source escapes its live root") from exc
            databases.append(path)
    return sorted(databases)


def _database_inventory(
    databases: list[Path],
    root: Path,
) -> dict[str, tuple[int, int]]:
    inventory: dict[str, tuple[int, int]] = {}
    for database in databases:
        info = os.lstat(database)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_nlink != 1
        ):
            raise RuntimeError("Database inventory contains an unsafe source")
        inventory[database.relative_to(root).as_posix()] = (
            info.st_dev,
            info.st_ino,
        )
    return inventory


def _same_source(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        stat.S_ISREG(after.st_mode)
        and not stat.S_ISLNK(after.st_mode)
        and after.st_nlink == 1
        and (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RuntimeError("Staged database is not one regular file")
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ):
            raise RuntimeError("Staged database changed while hashing")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _stage_database(
    source: Path,
    destination: Path,
    *,
    expected_uid: int | None = None,
    expected_gid: int | None = None,
) -> dict[str, Any]:
    before = os.lstat(source)
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_nlink != 1
    ):
        raise RuntimeError("Database source must be one regular, non-linked file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(destination):
        raise RuntimeError("Staged database destination already exists")

    source_uri = source.as_uri() + "?mode=rw"
    try:
        with closing(
            sqlite3.connect(source_uri, uri=True, timeout=30)
        ) as source_connection:
            opened = os.lstat(source)
            if not _same_source(before, opened):
                raise RuntimeError(
                    "Database source changed identity while it was opened"
                )
            source_connection.execute("PRAGMA busy_timeout=30000")
            with closing(sqlite3.connect(destination, timeout=30)) as destination_connection:
                destination_connection.execute("PRAGMA busy_timeout=30000")
                selected = destination_connection.execute(
                    "PRAGMA journal_mode=DELETE"
                ).fetchone()
                if selected != ("delete",):
                    raise RuntimeError("Staged database requires DELETE journal mode")
                source_connection.backup(destination_connection)
                selected = destination_connection.execute(
                    "PRAGMA journal_mode=DELETE"
                ).fetchone()
                if selected != ("delete",):
                    raise RuntimeError("Staged database requires DELETE journal mode")
                if (
                    destination_connection.execute("PRAGMA quick_check").fetchall()
                    != [("ok",)]
                ):
                    raise RuntimeError("Staged database failed SQLite quick_check")
    except sqlite3.Error as exc:
        raise RuntimeError(f"Cannot stage SQLite database {source}") from exc

    after = os.lstat(source)
    if not _same_source(before, after):
        raise RuntimeError("Database source changed identity during staging")
    for suffix in ("-wal", "-shm", "-journal"):
        companion = destination.with_name(f"{destination.name}{suffix}")
        if os.path.lexists(companion):
            raise RuntimeError("Staged database retained a SQLite companion file")

    _fsync_file(destination)
    destination.chmod(0o440)
    staged_info = os.lstat(destination)
    if (
        not stat.S_ISREG(staged_info.st_mode)
        or staged_info.st_nlink != 1
        or (expected_uid is not None and staged_info.st_uid != expected_uid)
        or (expected_gid is not None and staged_info.st_gid != expected_gid)
    ):
        raise RuntimeError("Staged database is not one regular file")
    return {
        "path": "",
        "sha256": _hash_file(destination),
        "size": staged_info.st_size,
        "source_device": before.st_dev,
        "source_inode": before.st_ino,
    }


def stage_databases(
    live_root: Path,
    current_stage: Path,
    *,
    expected_stage_identity: tuple[int, int] | None = None,
    expected_uid: int | None = None,
    expected_gid: int | None = None,
) -> dict[str, Any]:
    """Copy all live SQLite files into one sealed, self-contained stage."""

    root = _validated_directory(live_root, "Live application root")
    current = _validated_directory(current_stage, "Current backup stage")
    current_info = os.lstat(current)
    if (
        (
            expected_stage_identity is not None
            and (current_info.st_dev, current_info.st_ino)
            != expected_stage_identity
        )
        or (expected_uid is not None and current_info.st_uid != expected_uid)
        or (expected_gid is not None and current_info.st_gid != expected_gid)
    ):
        raise RuntimeError("Current backup stage changed identity or ownership")
    if any(current.iterdir()):
        raise RuntimeError("Current backup stage must start empty")

    databases = discover_databases(root)
    initial_inventory = _database_inventory(databases, root)
    records: list[dict[str, Any]] = []
    for source in databases:
        relative = source.relative_to(root)
        destination = current / relative
        record = _stage_database(
            source,
            destination,
            expected_uid=expected_uid,
            expected_gid=expected_gid,
        )
        record["path"] = relative.as_posix()
        records.append(record)

    final_databases = discover_databases(root)
    if _database_inventory(final_databases, root) != initial_inventory:
        raise RuntimeError("Live database inventory changed during staging")

    manifest: dict[str, Any] = {
        "contract_version": 1,
        "live_root": str(root),
        "database_count": len(records),
        "databases": records,
    }
    manifest_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    manifest_path = current / MANIFEST_NAME
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(manifest_path, flags, 0o440)
    try:
        view = memoryview(manifest_bytes)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise RuntimeError("Cannot write backup stage manifest")
            view = view[written:]
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o440)
        else:
            os.chmod(manifest_path, 0o440)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

    directories = sorted(
        (path for path in current.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        directory.chmod(0o550)
        _fsync_directory(directory)
    current.chmod(0o550)
    _fsync_directory(current)
    sealed_info = os.lstat(current)
    if (
        (current_info.st_dev, current_info.st_ino)
        != (sealed_info.st_dev, sealed_info.st_ino)
        or (expected_uid is not None and sealed_info.st_uid != expected_uid)
        or (expected_gid is not None and sealed_info.st_gid != expected_gid)
        or (os.name != "nt" and stat.S_IMODE(sealed_info.st_mode) != 0o550)
    ):
        raise RuntimeError("Current backup stage was not sealed safely")
    return manifest


def _linux_status() -> dict[str, int]:
    try:
        lines = Path("/proc/self/status").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise RuntimeError("Cannot read the Linux process security state") from exc
    values: dict[str, int] = {}
    for line in lines:
        key, separator, raw = line.partition(":")
        if not separator:
            continue
        if key in {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"}:
            values[key] = int(raw.strip(), 16)
        elif key == "NoNewPrivs":
            values[key] = int(raw.strip(), 10)
    required = {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs"}
    if set(values) != required:
        raise RuntimeError("Linux process security state is incomplete")
    return values


def _prctl(option: int, argument: int = 0) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(
        ctypes.c_int(option),
        ctypes.c_ulong(argument),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(result)


def _disable_dumpability() -> None:
    if os.name != "posix":
        raise RuntimeError("Production staging requires Linux")
    if _prctl(PR_SET_DUMPABLE, 0) != 0 or _prctl(PR_GET_DUMPABLE) != 0:
        raise RuntimeError("Cannot disable process dumpability")


def _require_initial_privileges() -> None:
    if os.name != "posix" or not hasattr(os, "getresuid"):
        raise RuntimeError("Production staging requires Linux credential APIs")
    if os.geteuid() != 0 or os.getresuid() != (0, 0, 0):
        raise RuntimeError("Production staging must start with all root UIDs")
    status = _linux_status()
    if (
        status["NoNewPrivs"] != 1
        or status["CapInh"] != 0
        or status["CapPrm"] != REQUIRED_CAPABILITIES
        or status["CapEff"] != REQUIRED_CAPABILITIES
        or status["CapBnd"] != REQUIRED_CAPABILITIES
        or status["CapAmb"] != 0
    ):
        raise RuntimeError("Production staging has an unsafe capability contract")


def _resolve_production_identity() -> tuple[int, int]:
    import grp
    import pwd

    live_uid = pwd.getpwnam(PRODUCTION_LIVE_USER).pw_uid
    backup_gid = grp.getgrnam(PRODUCTION_BACKUP_GROUP).gr_gid
    if live_uid <= 0 or backup_gid <= 0:
        raise RuntimeError("Production staging identities must be unprivileged")
    return live_uid, backup_gid


def _adopt_backup_group(backup_gid: int) -> None:
    os.umask(0o027)
    os.setgroups([])
    os.setresgid(backup_gid, backup_gid, backup_gid)
    if os.getresgid() != (backup_gid, backup_gid, backup_gid) or os.getgroups():
        raise RuntimeError("Cannot adopt the isolated backup group")


def _create_stage_directories(live_uid: int, backup_gid: int) -> tuple[int, int]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    temporary_fd = os.open("/tmp", flags)
    outer_fd: int | None = None
    current_fd: int | None = None
    try:
        temporary_info = os.fstat(temporary_fd)
        if (
            not stat.S_ISDIR(temporary_info.st_mode)
            or temporary_info.st_uid != 0
            or stat.S_IMODE(temporary_info.st_mode) != 0o1777
        ):
            raise RuntimeError("Private /tmp has unsafe ownership or mode")
        os.mkdir(PRODUCTION_STAGE_OUTER.name, 0o710, dir_fd=temporary_fd)
        outer_fd = os.open(PRODUCTION_STAGE_OUTER.name, flags, dir_fd=temporary_fd)
        outer_info = os.fstat(outer_fd)
        if (
            not stat.S_ISDIR(outer_info.st_mode)
            or outer_info.st_uid != 0
            or outer_info.st_gid != backup_gid
            or stat.S_IMODE(outer_info.st_mode) != 0o710
        ):
            raise RuntimeError("Backup stage outer directory is unsafe")
        os.mkdir(PRODUCTION_CURRENT_STAGE.name, 0o750, dir_fd=outer_fd)
        current_fd = os.open(PRODUCTION_CURRENT_STAGE.name, flags, dir_fd=outer_fd)
        os.fchmod(current_fd, 0o750)
        os.fchown(current_fd, live_uid, backup_gid)
        current_info = os.fstat(current_fd)
        if (
            not stat.S_ISDIR(current_info.st_mode)
            or current_info.st_uid != live_uid
            or current_info.st_gid != backup_gid
            or stat.S_IMODE(current_info.st_mode) != 0o750
        ):
            raise RuntimeError("Current backup stage directory is unsafe")
        os.fsync(current_fd)
        os.fsync(outer_fd)
        os.fsync(temporary_fd)
        return current_info.st_dev, current_info.st_ino
    finally:
        if current_fd is not None:
            os.close(current_fd)
        if outer_fd is not None:
            os.close(outer_fd)
        os.close(temporary_fd)


def _drop_user_permanently(live_uid: int) -> None:
    os.setresuid(live_uid, live_uid, live_uid)


def _verify_permanent_drop(live_uid: int, backup_gid: int) -> None:
    if (
        os.getresuid() != (live_uid, live_uid, live_uid)
        or os.getresgid() != (backup_gid, backup_gid, backup_gid)
        or os.getgroups()
    ):
        raise RuntimeError("Production staging did not drop every credential")
    status = _linux_status()
    if status["NoNewPrivs"] != 1 or any(
        status[name] != 0 for name in ("CapInh", "CapPrm", "CapEff", "CapAmb")
    ):
        raise RuntimeError("Production staging retained process capabilities")
    if _prctl(PR_GET_DUMPABLE) != 0:
        raise RuntimeError("Production staging became dumpable after credential drop")
    try:
        os.setresuid(0, 0, 0)
    except OSError:
        pass
    else:
        raise RuntimeError("Production staging could regain root credentials")
    if os.getresuid() != (live_uid, live_uid, live_uid):
        raise RuntimeError("Root-regain test changed the staging identity")


def run_production_stage() -> dict[str, Any]:
    """Create the fixed production stage after an irreversible privilege drop."""

    _disable_dumpability()
    _require_initial_privileges()
    live_uid, backup_gid = _resolve_production_identity()
    _adopt_backup_group(backup_gid)
    stage_identity = _create_stage_directories(live_uid, backup_gid)
    _drop_user_permanently(live_uid)
    _disable_dumpability()
    _verify_permanent_drop(live_uid, backup_gid)
    return stage_databases(
        PRODUCTION_LIVE_ROOT,
        PRODUCTION_CURRENT_STAGE,
        expected_stage_identity=stage_identity,
        expected_uid=live_uid,
        expected_gid=backup_gid,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage BetBoy runtime databases for the backup service"
    )
    parser.parse_args(argv)
    manifest = run_production_stage()
    print(f"Staged runtime databases: {manifest['database_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
