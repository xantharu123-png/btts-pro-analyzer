"""Create consistent compressed backups of BetBoy runtime SQLite databases."""

from __future__ import annotations

import argparse
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PARTS = {
    ".codex_test_venv",
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    "__pycache__",
    "backups_runtime",
}


def discover_databases(root: Path = ROOT) -> list[Path]:
    databases = []
    for path in root.rglob("*.db"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_file():
            databases.append(path)
    return sorted(databases)


def backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.resolve().as_posix()}?mode=ro"
    with closing(
        sqlite3.connect(source_uri, uri=True, timeout=30)
    ) as source_conn:
        with closing(sqlite3.connect(destination)) as destination_conn:
            source_conn.backup(destination_conn)


def create_archive(
    output_dir: Path,
    *,
    root: Path = ROOT,
    now: datetime | None = None,
) -> tuple[Path, int]:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / f"betboy-sqlite-{stamp}.zip"
    databases = discover_databases(root)

    with tempfile.TemporaryDirectory(prefix="betboy-backup-") as temp_dir:
        stage = Path(temp_dir)
        for source in databases:
            relative = source.relative_to(root)
            backup_database(source, stage / relative)

        partial_path = output_dir / f".{final_path.name}.partial"
        with zipfile.ZipFile(
            partial_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for staged in sorted(stage.rglob("*.db")):
                archive.write(staged, staged.relative_to(stage).as_posix())
        partial_path.replace(final_path)

    return final_path, len(databases)


def prune_archives(
    output_dir: Path,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    removed = 0
    for archive in output_dir.glob("betboy-sqlite-*.zip"):
        try:
            stamp = archive.stem.removeprefix("betboy-sqlite-")
            created = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if created < cutoff:
            archive.unlink()
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "backups_runtime",
    )
    parser.add_argument("--retention-days", type=int, default=14)
    args = parser.parse_args()
    if args.retention_days < 1:
        parser.error("--retention-days must be at least 1")

    archive, count = create_archive(args.output_dir)
    removed = prune_archives(
        args.output_dir,
        retention_days=args.retention_days,
    )
    print(f"Backup: {archive} | databases={count} | pruned={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
