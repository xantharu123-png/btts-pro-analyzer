from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import zipfile

from scripts import backup_runtime_databases as backup
from scripts import stage_runtime_databases as stage


def test_live_wal_stage_archive_verify_and_restore_end_to_end(tmp_path):
    live_root = tmp_path / "live-app"
    database = live_root / "runtime_state" / "api_budget.db"
    database.parent.mkdir(parents=True)
    current_stage = tmp_path / "private-stage" / "current"
    current_stage.mkdir(parents=True)

    with closing(sqlite3.connect(database)) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
        writer.execute("INSERT INTO evidence VALUES ('from-live-wal')")
        writer.commit()

        manifest = stage.stage_databases(live_root, current_stage)
        archive, count = backup.create_archive(
            tmp_path / "archives",
            root=current_stage,
            logical_root=live_root,
            stage_manifest_path=current_stage / "manifest.json",
        )

        assert writer.execute("PRAGMA journal_mode").fetchone() == ("wal",)

    assert manifest["database_count"] == 1
    assert count == 1
    assert backup.verify_archive(archive) == 1

    restored_root = tmp_path / "restored"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(restored_root)
    restored = restored_root / "runtime_state" / "api_budget.db"
    with closing(sqlite3.connect(restored)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == (
            "delete",
        )
        assert connection.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert connection.execute("SELECT value FROM evidence").fetchone() == (
            "from-live-wal",
        )
