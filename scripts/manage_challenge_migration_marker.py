#!/usr/bin/env python3
"""Publish the root-owned monotonic marker for the one 15K v0 migration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import sqlite3
import stat
import sys
from typing import Any


CONTRACT_VERSION = 1
LEGACY_V0_WRITER_BLOBS = {
    "f96d8b6c340c184e90d644cc310efebf963de1ad",
}
PRODUCTION_MARKER = Path(
    "/etc/betboy/challenge-ledger-v2-migrated.json"
)
PRODUCTION_ROOT = Path("/opt/betboy/app")
DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _absolute_lexical_path(path: Path) -> Path:
    """Make a CLI path absolute without resolving its final symlink."""

    return Path(os.path.abspath(os.fspath(path)))


def _validated_application_root(path: Path) -> Path:
    lexical = _absolute_lexical_path(path)
    if lexical.is_symlink():
        raise RuntimeError("Application root must not be a symlink")
    resolved = lexical.resolve(strict=True)
    if resolved != lexical:
        raise RuntimeError("Application root must not traverse a symlink")
    if not stat.S_ISDIR(os.lstat(resolved).st_mode):
        raise RuntimeError("Application root must be a real directory")
    return resolved


def _is_lower_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_json_file(path: Path, label: str, *, production: bool = False) -> Any:
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError(f"{label} path is unsafe")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(f"{label} cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError(f"{label} must be one regular file")
        if os.name != "nt":
            if production:
                import grp

                expected_group = grp.getgrnam("betboy").gr_gid
                if (
                    info.st_uid != 0
                    or info.st_gid != expected_group
                    or stat.S_IMODE(info.st_mode) != 0o640
                ):
                    raise RuntimeError(
                        f"{label} must be root:betboy mode 0640"
                    )
            elif (
                info.st_uid not in {0, os.geteuid()}
                or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise RuntimeError(f"{label} owner or permissions are unsafe")
        raw = os.read(descriptor, 65_537)
        if len(raw) > 65_536 or os.read(descriptor, 1):
            raise RuntimeError(f"{label} is unexpectedly large")
    finally:
        os.close(descriptor)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is invalid JSON") from exc


def _validate_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict) or set(receipt) != {
        "contract_version",
        "mode",
        "database_count",
        "databases",
    }:
        raise RuntimeError("Migration receipt has an invalid shape")
    databases = receipt["databases"]
    if (
        type(receipt["contract_version"]) is not int
        or receipt["contract_version"] != CONTRACT_VERSION
        or receipt["mode"] not in {"legacy-v0", "fresh-install"}
        or type(receipt["database_count"]) is not int
        or receipt["database_count"] < 0
        or not isinstance(databases, list)
        or receipt["database_count"] != len(databases)
    ):
        raise RuntimeError("Migration receipt is inconsistent")
    if receipt["mode"] == "fresh-install" and databases:
        raise RuntimeError("Fresh-install receipt must not contain databases")
    seen_paths: set[str] = set()
    for record in databases:
        if not isinstance(record, dict) or set(record) != {
            "path",
            "checkpoint_mac",
            "source",
        }:
            raise RuntimeError("Migration receipt database entry is invalid")
        relative = PurePosixPath(str(record["path"]))
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.as_posix() in seen_paths
            or not _is_lower_hex(record["checkpoint_mac"], 64)
            or record["source"] not in {"v0", "v2"}
        ):
            raise RuntimeError("Migration receipt database entry is unsafe")
        seen_paths.add(relative.as_posix())
    return receipt


def _validate_marker(payload: Any, application_root: Path) -> dict[str, Any]:
    base_keys = {
        "contract_version",
        "status",
        "mode",
        "application_root",
        "previous_head",
        "previous_writer_blob",
        "target_head",
    }
    if not isinstance(payload, dict) or payload.get("status") not in {
        "in_progress",
        "complete",
    }:
        raise RuntimeError("Migration marker has an invalid status")
    expected_keys = (
        base_keys
        if payload["status"] == "in_progress"
        else base_keys | {"completed_at", "migration_receipt"}
    )
    if set(payload) != expected_keys:
        raise RuntimeError("Migration marker has an invalid shape")
    root = _validated_application_root(application_root)
    marker_root = Path(str(payload["application_root"]))
    if (
        type(payload["contract_version"]) is not int
        or payload["contract_version"] != CONTRACT_VERSION
        or payload["mode"] not in {"legacy-v0", "fresh-install"}
        or not marker_root.is_absolute()
        or marker_root != root
        or not _is_lower_hex(payload["target_head"], 40)
    ):
        raise RuntimeError("Migration marker provenance is invalid")
    if payload["mode"] == "legacy-v0":
        if (
            not _is_lower_hex(payload["previous_head"], 40)
            or payload["previous_writer_blob"] not in LEGACY_V0_WRITER_BLOBS
        ):
            raise RuntimeError("Migration marker predecessor is invalid")
    elif (
        payload["status"] != "complete"
        or payload["previous_head"] != "0" * 40
        or payload["previous_writer_blob"] != "fresh-install"
    ):
        raise RuntimeError("Fresh-install marker provenance is invalid")
    if payload["status"] == "complete":
        try:
            completed_at = datetime.fromisoformat(
                str(payload["completed_at"]).replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise RuntimeError("Migration marker completion time is invalid") from exc
        if completed_at.tzinfo is None:
            raise RuntimeError("Migration marker completion time lacks a timezone")
        receipt = _validate_receipt(payload["migration_receipt"])
        if receipt["mode"] != payload["mode"]:
            raise RuntimeError("Migration receipt mode does not match its marker")
    return payload


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(marker: Path, payload: dict[str, Any], group_id: int | None) -> None:
    parent = marker.parent
    if marker.is_symlink() or parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("Migration marker path is unsafe")
    production = marker == PRODUCTION_MARKER
    if production and (os.name == "nt" or os.geteuid() != 0 or group_id is None):
        raise RuntimeError("Production migration marker must be published by root")
    temporary = parent / (
        f".{marker.name}.{os.getpid()}.{secrets.token_hex(8)}.partial"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        if production:
            os.fchown(descriptor, 0, group_id)
            os.fchmod(descriptor, 0o640)
        elif os.name != "nt":
            os.fchmod(descriptor, 0o600)
        data = _canonical_bytes(payload)
        written = 0
        while written < len(data):
            count = os.write(descriptor, data[written:])
            if count <= 0:
                raise OSError("short migration marker write")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.replace(temporary, marker)
        _fsync_directory(parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_marker(marker: Path, application_root: Path) -> dict[str, Any]:
    return _validate_marker(
        _read_json_file(
            marker,
            "Migration marker",
            production=marker == PRODUCTION_MARKER,
        ),
        application_root,
    )


def require_complete_marker(marker: Path, application_root: Path) -> dict[str, Any]:
    payload = _read_marker(marker, application_root)
    if payload["status"] != "complete":
        raise RuntimeError("Challenge ledger migration is not complete")
    return payload


def prepare_marker(
    marker: Path,
    application_root: Path,
    *,
    previous_head: str,
    previous_writer_blob: str,
    target_head: str,
    group_id: int | None,
) -> dict[str, Any]:
    if marker.exists():
        current = _read_marker(marker, application_root)
        if current["status"] == "complete":
            return current
        # The trusted marker preserves the original predecessor. After a crash,
        # Git may already be at the target commit, so only the target identity
        # must match when resuming the partially completed multi-DB migration.
        if current["target_head"] != target_head:
            raise RuntimeError("In-progress migration belongs to another rollout")
        return current
    if (
        not _is_lower_hex(previous_head, 40)
        or previous_writer_blob not in LEGACY_V0_WRITER_BLOBS
        or not _is_lower_hex(target_head, 40)
    ):
        raise RuntimeError("First migration predecessor is not allowlisted")
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "in_progress",
        "mode": "legacy-v0",
        "application_root": str(application_root.resolve(strict=True)),
        "previous_head": previous_head,
        "previous_writer_blob": previous_writer_blob,
        "target_head": target_head,
    }
    _publish(marker, payload, group_id)
    return _read_marker(marker, application_root)


def complete_marker(
    marker: Path,
    application_root: Path,
    *,
    target_head: str,
    receipt_path: Path,
    group_id: int | None,
) -> dict[str, Any]:
    current = _read_marker(marker, application_root)
    if current["status"] == "complete":
        return current
    if current["target_head"] != target_head:
        raise RuntimeError("Migration completion target does not match its marker")
    receipt = _validate_receipt(
        _read_json_file(receipt_path, "Migration receipt")
    )
    if receipt["mode"] != current["mode"]:
        raise RuntimeError("Migration receipt mode does not match its marker")
    completed = {
        **current,
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "migration_receipt": receipt,
    }
    _publish(marker, completed, group_id)
    return _read_marker(marker, application_root)


def _has_challenge_database(application_root: Path) -> bool:
    for directory, dirnames, filenames in os.walk(
        application_root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(directory)
        kept: list[str] = []
        for name in dirnames:
            child = current / name
            if name == ".git":
                continue
            if child.is_symlink():
                raise RuntimeError("Fresh-install scan encountered a directory symlink")
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            if path.suffix.casefold() not in DATABASE_SUFFIXES:
                continue
            if path.is_symlink():
                raise RuntimeError("Fresh-install scan encountered a database symlink")
            relative = path.relative_to(application_root)
            if relative == Path("challenge_15k.db") or (
                relative.parts and relative.parts[0] == "challenge_sessions"
            ):
                # These locations are dedicated challenge-ledger slots. Even a
                # schema-free/partially dropped SQLite file is predecessor data,
                # never evidence of a fresh host.
                return True
            try:
                connection = sqlite3.connect(
                    path.resolve(strict=True).as_uri() + "?mode=ro",
                    uri=True,
                    timeout=30,
                )
                try:
                    schema_objects = connection.execute(
                        "SELECT name, tbl_name FROM sqlite_master"
                    ).fetchall()
                finally:
                    connection.close()
            except sqlite3.Error as exc:
                raise RuntimeError(
                    "Fresh-install scan encountered an unreadable database"
                ) from exc
            if any(
                str(name).startswith("challenge_")
                or str(table).startswith("challenge_")
                for name, table in schema_objects
            ):
                return True
    return False


def create_fresh_marker(
    marker: Path,
    application_root: Path,
    *,
    target_head: str,
    group_id: int | None,
) -> dict[str, Any]:
    if marker.exists():
        current = _read_marker(marker, application_root)
        if current["status"] == "complete":
            return current
        raise RuntimeError("Fresh install cannot adopt an in-progress migration")
    if not _is_lower_hex(target_head, 40):
        raise RuntimeError("Fresh-install target is invalid")
    if _has_challenge_database(application_root):
        raise RuntimeError("Fresh install has a pre-existing challenge database")
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "complete",
        "mode": "fresh-install",
        "application_root": str(application_root.resolve(strict=True)),
        "previous_head": "0" * 40,
        "previous_writer_blob": "fresh-install",
        "target_head": target_head,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "migration_receipt": {
            "contract_version": CONTRACT_VERSION,
            "mode": "fresh-install",
            "database_count": 0,
            "databases": [],
        },
    }
    _publish(marker, payload, group_id)
    return _read_marker(marker, application_root)


def _group_id(name: str | None) -> int | None:
    if name is None or os.name == "nt":
        return None
    import grp

    return grp.getgrnam(name).gr_gid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--group")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--previous-head", required=True)
    prepare.add_argument("--previous-writer-blob", required=True)
    prepare.add_argument("--target-head", required=True)
    complete = subparsers.add_parser("complete")
    complete.add_argument("--target-head", required=True)
    complete.add_argument("--receipt", type=Path, required=True)
    fresh = subparsers.add_parser("fresh")
    fresh.add_argument("--target-head", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("require-complete")
    args = parser.parse_args()

    try:
        marker = _absolute_lexical_path(args.marker)
        application_root = _validated_application_root(args.application_root)
        if marker == PRODUCTION_MARKER and application_root != PRODUCTION_ROOT:
            raise RuntimeError(
                "Production marker requires the exact BetBoy application root"
            )
        group_id = _group_id(args.group)
        if args.command == "prepare":
            payload = prepare_marker(
                marker,
                application_root,
                previous_head=args.previous_head,
                previous_writer_blob=args.previous_writer_blob,
                target_head=args.target_head,
                group_id=group_id,
            )
        elif args.command == "complete":
            payload = complete_marker(
                marker,
                application_root,
                target_head=args.target_head,
                receipt_path=_absolute_lexical_path(args.receipt),
                group_id=group_id,
            )
        elif args.command == "fresh":
            payload = create_fresh_marker(
                marker,
                application_root,
                target_head=args.target_head,
                group_id=group_id,
            )
        elif args.command == "require-complete":
            payload = require_complete_marker(marker, application_root)
        else:
            payload = _read_marker(marker, application_root)
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "previous_head": payload["previous_head"],
                "status": payload["status"],
                "target_head": payload["target_head"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
