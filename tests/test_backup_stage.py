from __future__ import annotations

from contextlib import closing
import hashlib
import importlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading

import pytest


def _stage_module():
    module_name = "scripts.stage_runtime_databases"
    assert importlib.util.find_spec(module_name) is not None, (
        "the standalone runtime database stager is missing"
    )
    return importlib.import_module(module_name)


def _readonly_uri(path: Path) -> str:
    return path.resolve(strict=True).as_uri() + "?mode=ro"


def test_stage_directory_mode_is_fixed_before_unprivileged_chown():
    stage = _stage_module()
    source = inspect.getsource(stage._create_stage_directories)

    assert source.index("os.fchmod(current_fd, 0o750)") < source.index(
        "os.fchown(current_fd, live_uid, backup_gid)"
    )


def test_stage_databases_copies_live_wal_and_publishes_exact_manifest(tmp_path):
    stage = _stage_module()
    live_root = tmp_path / "app"
    database = live_root / "runtime_state" / "api_budget.db"
    database.parent.mkdir(parents=True)
    current = tmp_path / "private-stage" / "current"
    current.mkdir(parents=True)

    with closing(sqlite3.connect(database)) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY, value TEXT)")
        writer.execute("INSERT INTO evidence(value) VALUES ('preserved')")
        writer.commit()
        source_info = database.stat()

        manifest = stage.stage_databases(live_root, current)

        assert writer.execute("PRAGMA journal_mode").fetchone() == ("wal",)

    staged_database = current / "runtime_state" / "api_budget.db"
    with closing(sqlite3.connect(_readonly_uri(staged_database), uri=True)) as copied:
        assert copied.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert copied.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert copied.execute("SELECT value FROM evidence").fetchone() == (
            "preserved",
        )

    expected_record = {
        "path": "runtime_state/api_budget.db",
        "sha256": hashlib.sha256(staged_database.read_bytes()).hexdigest(),
        "size": staged_database.stat().st_size,
        "source_device": source_info.st_dev,
        "source_inode": source_info.st_ino,
    }
    expected_manifest = {
        "contract_version": 1,
        "database_count": 1,
        "databases": [expected_record],
        "live_root": str(live_root.resolve(strict=True)),
    }
    assert manifest == expected_manifest
    manifest_path = current / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == expected_manifest
    assert manifest_path.read_bytes() == (
        json.dumps(
            expected_manifest,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    assert not staged_database.with_name(f"{staged_database.name}-wal").exists()
    assert not staged_database.with_name(f"{staged_database.name}-shm").exists()
    if os.name != "nt":
        assert staged_database.stat().st_mode & 0o777 == 0o440
        assert manifest_path.stat().st_mode & 0o777 == 0o440
        assert current.stat().st_mode & 0o777 == 0o550


def test_production_entrypoint_verifies_permanent_drop_before_live_access(
    monkeypatch,
):
    stage = _stage_module()
    assert hasattr(stage, "run_production_stage"), (
        "the privileged production entrypoint is missing"
    )
    events: list[str] = []

    monkeypatch.setattr(
        stage,
        "_disable_dumpability",
        lambda: events.append("dumpable"),
    )
    monkeypatch.setattr(
        stage,
        "_require_initial_privileges",
        lambda: events.append("initial-security"),
    )
    monkeypatch.setattr(
        stage,
        "_resolve_production_identity",
        lambda: (1234, 2345),
    )
    monkeypatch.setattr(
        stage,
        "_adopt_backup_group",
        lambda gid: events.append(f"group:{gid}"),
    )
    monkeypatch.setattr(
        stage,
        "_create_stage_directories",
        lambda uid, gid: events.append(f"stage:{uid}:{gid}") or (17, 19),
    )
    monkeypatch.setattr(
        stage,
        "_drop_user_permanently",
        lambda uid: events.append(f"user:{uid}"),
    )
    monkeypatch.setattr(
        stage,
        "_verify_permanent_drop",
        lambda uid, gid: events.append(f"verified:{uid}:{gid}"),
    )

    def fake_stage_databases(live_root, current_stage, **kwargs):
        assert events[-1] == "verified:1234:2345"
        assert live_root == stage.PRODUCTION_LIVE_ROOT
        assert current_stage == stage.PRODUCTION_CURRENT_STAGE
        assert kwargs["expected_stage_identity"] == (17, 19)
        assert kwargs["expected_uid"] == 1234
        assert kwargs["expected_gid"] == 2345
        events.append("live-access")
        return {"database_count": 0}

    monkeypatch.setattr(stage, "stage_databases", fake_stage_databases)

    assert stage.run_production_stage() == {"database_count": 0}
    assert events == [
        "dumpable",
        "initial-security",
        "group:2345",
        "stage:1234:2345",
        "user:1234",
        "verified:1234:2345",
        "live-access",
    ]


def test_stage_rejects_a_database_added_during_the_snapshot(tmp_path, monkeypatch):
    stage = _stage_module()
    live_root = tmp_path / "app"
    first = live_root / "runtime_state" / "first.db"
    first.parent.mkdir(parents=True)
    with closing(sqlite3.connect(first)) as connection:
        connection.execute("CREATE TABLE evidence (value TEXT)")
        connection.execute("INSERT INTO evidence VALUES ('first')")
        connection.commit()
    current = tmp_path / "private-stage" / "current"
    current.mkdir(parents=True)
    original_stage_database = stage._stage_database
    late = first.with_name("late.db")

    def stage_then_add_database(*args, **kwargs):
        record = original_stage_database(*args, **kwargs)
        with closing(sqlite3.connect(late)) as connection:
            connection.execute("CREATE TABLE evidence (value TEXT)")
            connection.execute("INSERT INTO evidence VALUES ('late')")
            connection.commit()
        return record

    monkeypatch.setattr(stage, "_stage_database", stage_then_add_database)

    with pytest.raises(RuntimeError, match="inventory changed"):
        stage.stage_databases(live_root, current)
    assert not (current / "manifest.json").exists()


def test_stage_excludes_streamlit_internal_state(tmp_path):
    stage = _stage_module()
    live_root = tmp_path / "app"
    runtime_database = live_root / "runtime_state" / "runtime.db"
    streamlit_database = live_root / ".streamlit" / "internal.db"
    for database in (runtime_database, streamlit_database):
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE evidence (value INTEGER)")
            connection.commit()
    current = tmp_path / "private-stage" / "current"
    current.mkdir(parents=True)

    manifest = stage.stage_databases(live_root, current)

    assert [record["path"] for record in manifest["databases"]] == [
        "runtime_state/runtime.db"
    ]
    assert not (current / ".streamlit").exists()


def test_online_stage_is_consistent_while_wal_writer_keeps_committing(tmp_path):
    stage = _stage_module()
    live_root = tmp_path / "app"
    database = live_root / "runtime_state" / "busy.db"
    database.parent.mkdir(parents=True)
    current = tmp_path / "private-stage" / "current"
    current.mkdir(parents=True)
    ready = threading.Event()
    stop = threading.Event()
    errors: list[BaseException] = []

    with closing(sqlite3.connect(database)) as keeper:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY)")
        keeper.commit()

        def write_rows() -> None:
            try:
                with closing(sqlite3.connect(database, timeout=30)) as writer:
                    writer.execute("PRAGMA busy_timeout=30000")
                    value = 1
                    while not stop.is_set():
                        writer.execute("INSERT INTO evidence VALUES (?)", (value,))
                        writer.commit()
                        ready.set()
                        value += 1
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)
                ready.set()

        writer_thread = threading.Thread(target=write_rows)
        writer_thread.start()
        assert ready.wait(timeout=10)
        try:
            stage.stage_databases(live_root, current)
        finally:
            stop.set()
            writer_thread.join(timeout=10)

        assert keeper.execute("PRAGMA journal_mode").fetchone() == ("wal",)

    assert not writer_thread.is_alive()
    assert errors == []
    staged_database = current / "runtime_state" / "busy.db"
    with closing(sqlite3.connect(_readonly_uri(staged_database), uri=True)) as copied:
        ids = [row[0] for row in copied.execute("SELECT id FROM evidence ORDER BY id")]
        assert ids
        assert ids == list(range(1, len(ids) + 1))
        assert copied.execute("PRAGMA quick_check").fetchall() == [("ok",)]


def test_stage_recovers_a_hot_delete_journal_before_copying(tmp_path):
    stage = _stage_module()
    live_root = tmp_path / "app"
    database = live_root / "runtime_state" / "crashed.db"
    database.parent.mkdir(parents=True)
    current = tmp_path / "private-stage" / "current"
    current.mkdir(parents=True)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA journal_mode=DELETE").fetchone() == (
            "delete",
        )
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('committed')")
        connection.commit()

    crashed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,sqlite3,sys;"
                "p=sys.argv[1];c=sqlite3.connect(p);"
                "c.execute('PRAGMA journal_mode=DELETE');"
                "c.execute('PRAGMA synchronous=FULL');"
                "c.execute('BEGIN IMMEDIATE');"
                "c.execute(\"UPDATE evidence SET value='uncommitted'\");"
                "assert os.path.exists(p+'-journal');"
                "os._exit(0)"
            ),
            str(database),
        ],
        check=False,
    )
    assert crashed.returncode == 0
    journal = database.with_name(f"{database.name}-journal")
    assert journal.exists()

    stage.stage_databases(live_root, current)

    staged_database = current / "runtime_state" / "crashed.db"
    with closing(sqlite3.connect(_readonly_uri(staged_database), uri=True)) as copied:
        assert copied.execute("SELECT value FROM evidence").fetchone() == (
            "committed",
        )
        assert copied.execute("PRAGMA quick_check").fetchall() == [("ok",)]
    with closing(sqlite3.connect(database)) as recovered:
        assert recovered.execute("SELECT value FROM evidence").fetchone() == (
            "committed",
        )
        assert recovered.execute("PRAGMA quick_check").fetchall() == [("ok",)]


def test_drop_verification_checks_zero_caps_and_attempts_root_regain(monkeypatch):
    stage = _stage_module()
    live_uid = 1234
    backup_gid = 2345
    regain_attempts: list[tuple[int, int, int]] = []
    monkeypatch.setattr(stage.os, "getresuid", lambda: (live_uid,) * 3, raising=False)
    monkeypatch.setattr(
        stage.os,
        "getresgid",
        lambda: (backup_gid,) * 3,
        raising=False,
    )
    monkeypatch.setattr(stage.os, "getgroups", lambda: [], raising=False)
    monkeypatch.setattr(
        stage,
        "_linux_status",
        lambda: {
            "CapInh": 0,
            "CapPrm": 0,
            "CapEff": 0,
            "CapBnd": stage.REQUIRED_CAPABILITIES,
            "CapAmb": 0,
            "NoNewPrivs": 1,
        },
    )
    monkeypatch.setattr(stage, "_prctl", lambda option, argument=0: 0)

    def reject_root(real: int, effective: int, saved: int) -> None:
        regain_attempts.append((real, effective, saved))
        raise PermissionError("permanent drop")

    monkeypatch.setattr(stage.os, "setresuid", reject_root, raising=False)

    stage._verify_permanent_drop(live_uid, backup_gid)
    assert regain_attempts == [(0, 0, 0)]

    monkeypatch.setattr(
        stage,
        "_linux_status",
        lambda: {
            "CapInh": 0,
            "CapPrm": 0,
            "CapEff": 1,
            "CapBnd": stage.REQUIRED_CAPABILITIES,
            "CapAmb": 0,
            "NoNewPrivs": 1,
        },
    )
    with pytest.raises(RuntimeError, match="retained process capabilities"):
        stage._verify_permanent_drop(live_uid, backup_gid)
