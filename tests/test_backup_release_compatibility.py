from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from scripts import backup_runtime_databases as backup


def _backup_script() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "backup_runtime_databases.py"
    )


def _run_legacy_prepare(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_backup_script()),
            "--root",
            str(root),
            "--prepare-readonly-sources",
            "--offline-confirmed",
        ],
        cwd=_backup_script().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_b_accepts_exact_release_a_wal_prepare_call(tmp_path):
    root = tmp_path / "app"
    database = root / "runtime_state" / "api_budget.db"
    database.parent.mkdir(parents=True)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == (
            "wal",
        )
        connection.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('preserved')")
        connection.commit()

    result = _run_legacy_prepare(root)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert (
        "Prepared read-only backup sources: inspected=1 | converted=1"
        in result.stdout
    )
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == (
            "delete",
        )
        assert connection.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert connection.execute("SELECT value FROM evidence").fetchone() == (
            "preserved",
        )
    assert not database.with_name(f"{database.name}-wal").exists()
    assert not database.with_name(f"{database.name}-shm").exists()


def test_release_b_legacy_prepare_is_explicit_and_handles_empty_root(tmp_path):
    root = tmp_path / "empty-app"
    root.mkdir()

    with pytest.raises(RuntimeError, match="explicit offline confirmation"):
        backup.prepare_readonly_backup_sources(root)

    result = _run_legacy_prepare(root)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert (
        "Prepared read-only backup sources: inspected=0 | converted=0"
        in result.stdout
    )
