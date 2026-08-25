from __future__ import annotations

import hashlib
import json
import os
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


def _rewrite_stage_manifest(manifest: Path, payload: dict[str, object]) -> None:
    manifest.write_text(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _make_stage(
    tmp_path: Path,
    *,
    database_names: tuple[str, ...] = ("runtime.db",),
) -> tuple[Path, Path, list[Path], Path]:
    live_root = tmp_path / "live-app"
    live_root.mkdir()
    stage = tmp_path / "private-stage" / "current"
    databases = []
    for index, name in enumerate(database_names):
        database = stage / name
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE evidence (value INTEGER NOT NULL)")
            connection.execute("INSERT INTO evidence VALUES (?)", (index,))
        databases.append(database)
    manifest = _write_stage_manifest(stage, live_root)
    return live_root, stage, databases, manifest


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


def test_staged_archive_rejects_duplicate_manifest_json_key(tmp_path):
    live_root, stage, _, manifest = _make_stage(tmp_path)
    raw = manifest.read_text(encoding="utf-8")
    needle = '"contract_version":1'
    assert needle in raw
    manifest.write_text(
        raw.replace(
            needle,
            '"contract_version":1,"contract_version":1',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        backup.create_archive(
            tmp_path / "archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )


@pytest.mark.parametrize(
    "mutation,database_names",
    [
        ("traversal", ("runtime.db",)),
        ("unsorted", ("a.db", "z.db")),
        ("bool-as-int", ("runtime.db",)),
    ],
)
def test_staged_archive_rejects_unsafe_manifest_database_records(
    tmp_path,
    mutation,
    database_names,
):
    live_root, stage, _, manifest = _make_stage(
        tmp_path,
        database_names=database_names,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if mutation == "traversal":
        payload["databases"][0]["path"] = "../runtime.db"
    elif mutation == "unsorted":
        payload["databases"].reverse()
    else:
        payload["databases"][0]["size"] = True
    _rewrite_stage_manifest(manifest, payload)

    with pytest.raises(RuntimeError, match="database path is unsafe"):
        backup.create_archive(
            tmp_path / "archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )


@pytest.mark.parametrize("extra_kind", ["file", "directory"])
def test_staged_archive_rejects_extra_stage_inventory(tmp_path, extra_kind):
    live_root, stage, _, manifest = _make_stage(tmp_path)
    if extra_kind == "file":
        (stage / "unexpected.txt").write_text("not declared\n", encoding="utf-8")
    else:
        (stage / "unexpected-directory").mkdir()

    with pytest.raises(RuntimeError, match="missing or extra (files|directories)"):
        backup.create_archive(
            tmp_path / "archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )


def test_staged_archive_rejects_symlinked_database(tmp_path):
    live_root, stage, _, manifest = _make_stage(tmp_path)
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"outside")
    database_link = stage / "linked.db"
    try:
        database_link.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"database symlinks are unavailable on this platform: {exc}")

    with pytest.raises(RuntimeError, match="unsafe file"):
        backup.create_archive(
            tmp_path / "archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )


def test_staged_archive_rejects_hardlinked_database(tmp_path):
    live_root, stage, databases, manifest = _make_stage(tmp_path)
    try:
        os.link(databases[0], tmp_path / "outside-hardlink.db")
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"database hardlinks are unavailable on this platform: {exc}")

    with pytest.raises(RuntimeError, match="unsafe file"):
        backup.create_archive(
            tmp_path / "archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )


def test_staged_archive_revalidates_manifest_after_database_copy(
    tmp_path,
    monkeypatch,
):
    live_root, stage, databases, manifest = _make_stage(tmp_path)
    database = databases[0]
    original_backup_database = backup.backup_database
    tampered = False

    def copy_then_tamper(source: Path, destination: Path) -> None:
        nonlocal tampered
        original_backup_database(source, destination)
        if source == database and not tampered:
            with source.open("ab") as handle:
                handle.write(b"tamper-after-copy")
            tampered = True

    monkeypatch.setattr(backup, "backup_database", copy_then_tamper)

    with pytest.raises(RuntimeError, match="digest or size differs"):
        backup.create_archive(
            tmp_path / "archives",
            root=stage,
            logical_root=live_root,
            stage_manifest_path=manifest,
        )
    assert tampered is True
