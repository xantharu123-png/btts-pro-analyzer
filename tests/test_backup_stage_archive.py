from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import backup_runtime_databases as backup


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_stage_manifest(stage: Path, live_root: Path) -> Path:
    databases = backup.discover_databases(stage)
    records = []
    for database in databases:
        info = database.stat()
        records.append(
            {
                "path": database.relative_to(stage).as_posix(),
                "size": info.st_size,
                "sha256": _sha256(database),
                "source_device": info.st_dev,
                "source_inode": info.st_ino,
            }
        )
    manifest = stage / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "live_root": str(live_root.resolve()),
                "database_count": len(records),
                "databases": records,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_fresh_marker(path: Path, live_root: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "status": "complete",
                "mode": "fresh-install",
                "application_root": str(live_root.resolve()),
                "previous_head": "0" * 40,
                "previous_writer_blob": "fresh-install",
                "target_head": "1" * 40,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "migration_receipt": {
                    "contract_version": 1,
                    "mode": "fresh-install",
                    "database_count": 0,
                    "databases": [],
                },
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_staged_archive_keeps_physical_members_and_logical_marker_root(tmp_path):
    live_root = tmp_path / "live-app"
    live_root.mkdir()
    stage = tmp_path / "private-stage" / "current"
    database = stage / "runtime_state" / "api_budget.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('staged')")
    manifest = _write_stage_manifest(stage, live_root)
    marker = _write_fresh_marker(tmp_path / "migration.json", live_root)

    archive, count = backup.create_archive(
        tmp_path / "archives",
        root=stage,
        logical_root=live_root,
        stage_manifest_path=manifest,
        migration_marker_path=marker,
    )

    assert count == 1
    assert backup.verify_archive(archive) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone() == (
            "staged",
        )


def test_staged_archive_rejects_wrong_logical_root_and_database_tamper(tmp_path):
    live_root = tmp_path / "live-app"
    live_root.mkdir()
    stage = tmp_path / "private-stage" / "current"
    database = stage / "runtime.db"
    stage.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES (1)")
    manifest = _write_stage_manifest(stage, live_root)

    wrong_root = tmp_path / "wrong-live-app"
    wrong_root.mkdir()
    with pytest.raises(RuntimeError, match="logical root"):
        backup.create_archive(
            tmp_path / "wrong-root-archives",
            root=stage,
            logical_root=wrong_root,
            stage_manifest_path=manifest,
        )

    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO evidence VALUES (2)")
    with pytest.raises(RuntimeError, match="manifest|digest|size"):
        backup.create_archive(
            tmp_path / "tampered-archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )


def test_stage_arguments_are_required_as_one_contract(tmp_path):
    root = tmp_path / "app"
    root.mkdir()

    with pytest.raises(RuntimeError, match="stage manifest"):
        backup.create_archive(
            tmp_path / "archives-one",
            root=root,
            logical_root=root,
        )
    with pytest.raises(RuntimeError, match="logical root"):
        backup.create_archive(
            tmp_path / "archives-two",
            root=root,
            stage_manifest_path=root / "manifest.json",
        )
