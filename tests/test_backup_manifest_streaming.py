from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime, timezone

import pytest

from scripts import backup_runtime_databases as backup


@pytest.fixture
def manifest_archive(tmp_path):
    database = tmp_path / "runtime.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE evidence (payload BLOB NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES (zeroblob(?))", (3 * 1024 * 1024 + 17,))
    key = b"1" * 64 + b"\n"
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_head": "a" * 40,
        "database_count": 1,
        "databases": [{
            "path": "runtime.db",
            "source_size": database.stat().st_size,
            "backup_size": database.stat().st_size,
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        }],
        "integrity_key": {
            "path": backup.INTEGRITY_KEY_ARCHIVE_PATH,
            "sha256": hashlib.sha256(key).hexdigest(),
        },
    }
    path = tmp_path / "manifest.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(database, "runtime.db")
        archive.writestr(backup.INTEGRITY_KEY_ARCHIVE_PATH, key)
        archive.writestr("MANIFEST.json", json.dumps(manifest))
    return path, manifest


def test_complete_restore_never_reads_a_whole_database_member(manifest_archive, monkeypatch):
    path, _ = manifest_archive
    original_read = zipfile.ZipExtFile.read
    reads = []

    def bounded_read(self, size=-1):
        if self.name == "runtime.db":
            assert 0 < size <= 1024 * 1024, "database reads must be bounded to 1 MiB"
            reads.append(size)
        return original_read(self, size)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", bounded_read)
    assert backup.verify_archive(path) == 1
    assert len(reads) > 3


@pytest.mark.parametrize("mutation", ["digest", "declared_size", "member_size"])
def test_streamed_manifest_still_rejects_digest_and_size_mismatches(manifest_archive, mutation):
    path, manifest = manifest_archive
    with zipfile.ZipFile(path) as archive:
        member = archive.getinfo("runtime.db")
        if mutation == "digest":
            manifest["databases"][0]["sha256"] = "0" * 64
        elif mutation == "declared_size":
            manifest["databases"][0]["backup_size"] += 1
        else:
            # Declared ZIP/manifest lengths agree, but the decompressed bytes do not.
            member.file_size += 1
            manifest["databases"][0]["backup_size"] += 1
        with pytest.raises(RuntimeError, match="database digest is invalid"):
            backup._validate_embedded_manifest(
                manifest, archive, [member],
                [archive.getinfo(backup.INTEGRITY_KEY_ARCHIVE_PATH)], [],
            )


def test_streaming_still_checks_zip_crc(manifest_archive):
    path, manifest = manifest_archive
    with zipfile.ZipFile(path) as archive:
        member = archive.getinfo("runtime.db")
        member.CRC ^= 1
        with pytest.raises(zipfile.BadZipFile, match="CRC"):
            backup._validate_embedded_manifest(
                manifest, archive, [member],
                [archive.getinfo(backup.INTEGRITY_KEY_ARCHIVE_PATH)], [],
            )
