from __future__ import annotations

import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts import backup_runtime_databases as backup
from scripts import run_football_shadow_due as football_job


def test_wettfinder_timer_is_installed_and_enabled_by_deploy_scripts():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy" / "systemd" / "betboy-wettfinder.service"
    ).read_text(encoding="utf-8")
    timer = (
        root / "deploy" / "systemd" / "betboy-wettfinder.timer"
    ).read_text(encoding="utf-8")
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    bootstrap = (root / "deploy" / "bootstrap_server.sh").read_text(
        encoding="utf-8"
    )

    assert "wettfinder_automation.py" in service
    assert "OnCalendar=*-*-* *:07:00" in timer
    assert "enable --now betboy-wettfinder.timer" in update
    assert "betboy-wettfinder.timer" in bootstrap


def test_football_job_skips_when_no_work_is_due(monkeypatch, capsys):
    called = False

    def fake_run(_ctx):
        nonlocal called
        called = True

    monkeypatch.setattr(football_job.shadow, "should_fire", lambda _ctx: False)
    monkeypatch.setattr(football_job.shadow, "run", fake_run)

    assert football_job.main() == 0
    assert called is False
    assert '"status": "idle"' in capsys.readouterr().out


def test_football_job_runs_due_work(monkeypatch, capsys):
    received = {}

    def fake_run(ctx):
        received.update(ctx)
        return {"artifact": {"status": "ok"}}

    monkeypatch.setattr(football_job.shadow, "should_fire", lambda _ctx: True)
    monkeypatch.setattr(football_job.shadow, "run", fake_run)

    assert football_job.main() == 0
    assert received["input"]["max_fixtures"] == 60
    assert '"status": "ok"' in capsys.readouterr().out


def test_sqlite_backup_is_consistent_and_prunes_old_archives(tmp_path):
    root = tmp_path / "app"
    source = root / "tennis" / "data" / "tennis_shadow.db"
    source.parent.mkdir(parents=True)
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE picks (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO picks (name) VALUES ('Alpha')")

    output = tmp_path / "backups"
    now = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    archive, count = backup.create_archive(output, root=root, now=now)

    assert count == 1
    assert backup.verify_archive(archive) == 1
    assert archive.name == "betboy-sqlite-20300102T030405Z.zip"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(tmp_path / "restored")
    restored = tmp_path / "restored" / "tennis" / "data" / "tennis_shadow.db"
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT name FROM picks").fetchone()[0] == "Alpha"

    old = output / "betboy-sqlite-20291201T000000Z.zip"
    old.write_bytes(b"old")
    old_timestamp = datetime(2029, 12, 1, tzinfo=timezone.utc).timestamp()
    old.touch()
    import os

    os.utime(old, (old_timestamp, old_timestamp))
    assert backup.prune_archives(output, retention_days=14, now=now) == 1
    assert not old.exists()


def test_backup_verifier_rejects_an_invalid_sqlite_member(tmp_path):
    archive = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("runtime_state/api_budget.db", b"not a database")

    import pytest

    with pytest.raises(RuntimeError, match="not restorable"):
        backup.verify_archive(archive)
