from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

import runtime_paths
from model_artifacts import (
    ManifestConflict,
    canonical_bytes,
    load_artifact,
    load_manifest,
    put_artifact,
    publish_slots,
)


def test_publish_keeps_other_tour_and_rejects_stale_writer(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    atp = put_artifact(path, kind="test", payload={"tour": "ATP"}, created_at=now)
    wta = put_artifact(path, kind="test", payload={"tour": "WTA"}, created_at=now)
    first = publish_slots(
        path,
        {"tennis:ATP": atp},
        expected_manifest=None,
        published_at=now,
    )
    with pytest.raises(ManifestConflict):
        publish_slots(
            path,
            {"tennis:WTA": wta},
            expected_manifest=None,
            published_at=now,
        )
    publish_slots(
        path,
        {"tennis:WTA": wta},
        expected_manifest=first,
        published_at=now,
    )
    assert load_manifest(path)[1] == {
        "tennis:ATP": atp,
        "tennis:WTA": wta,
    }
    assert load_artifact(path, atp)["payload"] == {"tour": "ATP"}


def test_canonical_bytes_is_stable_utf8_and_rejects_non_json_values():
    assert canonical_bytes({"z": 1, "a": "Grüße"}) == (
        b'{"a":"Gr\xc3\xbc\xc3\x9fe","z":1}'
    )
    with pytest.raises(ValueError):
        canonical_bytes({"value": float("nan")})
    with pytest.raises(TypeError):
        canonical_bytes({"value": Path("not-json")})


def test_artifact_identity_depends_only_on_kind_and_payload(tmp_path):
    path = tmp_path / "models.db"
    first_time = datetime(2026, 9, 7, tzinfo=timezone.utc)
    later_time = datetime(2026, 9, 8, tzinfo=timezone.utc)

    first = put_artifact(
        path,
        kind="tour-state",
        payload={"tour": "ATP", "revision": 1},
        created_at=first_time,
    )
    repeated = put_artifact(
        path,
        kind="tour-state",
        payload={"revision": 1, "tour": "ATP"},
        created_at=later_time,
    )
    changed = put_artifact(
        path,
        kind="tour-state",
        payload={"tour": "ATP", "revision": 2},
        created_at=later_time,
    )

    assert repeated == first
    assert changed != first
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT created_at FROM artifacts WHERE digest=?", (first,)
        ).fetchone() == (first_time.isoformat(),)


def test_artifact_and_manifest_hash_the_documented_envelopes(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    artifact = put_artifact(
        path,
        kind="tour-state",
        payload={"tour": "ATP", "revision": 1},
        created_at=now,
    )
    manifest = publish_slots(
        path,
        {"tennis:ATP": artifact},
        expected_manifest=None,
        published_at=now,
    )

    assert artifact == "7f62e8d652697c6291d88b9ba3f83d9ffad8d49addbc9dc278f0b4ef6167c478"
    assert manifest == "cce776a4f8d4fc79c9168b4b06685eaa2d16973ac70eef8c6eb296802b8cb471"


def test_existing_digest_rejects_changed_payload(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    digest = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE artifacts SET payload=? WHERE digest=?",
            (canonical_bytes({"v": 2}), digest),
        )

    with pytest.raises(ValueError, match="collision"):
        put_artifact(path, kind="test", payload={"v": 1}, created_at=now)


def test_context_model_database_has_a_dedicated_runtime_path():
    assert runtime_paths.CONTEXT_MODEL_DB_PATH == (
        runtime_paths.RUNTIME_STATE_DIR / "context_models.db"
    )


@pytest.mark.parametrize("operation", ["artifact", "manifest"])
def test_writes_reject_naive_timestamps(tmp_path, operation):
    path = tmp_path / "models.db"
    naive = datetime(2026, 9, 7)
    if operation == "artifact":
        call = lambda: put_artifact(
            path,
            kind="test",
            payload={"tour": "ATP"},
            created_at=naive,
        )
    else:
        call = lambda: publish_slots(
            path,
            {},
            expected_manifest=None,
            published_at=naive,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        call()


def test_artifact_payload_must_be_an_object(tmp_path):
    with pytest.raises(TypeError, match="payload"):
        put_artifact(
            tmp_path / "models.db",
            kind="test",
            payload=["not", "an", "object"],
            created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )


def test_missing_artifact_rolls_back_entire_publication(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    artifact = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    first = publish_slots(path, {"one": artifact}, expected_manifest=None, published_at=now)
    with sqlite3.connect(path) as connection:
        count_before = connection.execute("SELECT COUNT(*) FROM manifests").fetchone()[0]

    with pytest.raises(KeyError):
        publish_slots(
            path,
            {"two": artifact, "missing": "f" * 64},
            expected_manifest=first,
            published_at=now,
        )

    assert load_manifest(path) == (first, {"one": artifact})
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM manifests").fetchone()[0] == count_before


def test_malformed_hashes_are_rejected_before_lookup(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="SHA-256"):
        load_artifact(path, "not-a-hash")
    with pytest.raises(ValueError, match="SHA-256"):
        publish_slots(
            path,
            {"tennis:ATP": "ABC"},
            expected_manifest=None,
            published_at=now,
        )


def test_load_artifact_rejects_noncanonical_or_duplicate_json(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    digest = put_artifact(path, kind="test", payload={"tour": "ATP"}, created_at=now)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE artifacts SET payload=? WHERE digest=?",
            (b'{"tour":"ATP","tour":"ATP"}', digest),
        )
    with pytest.raises(ValueError, match="duplicate"):
        load_artifact(path, digest)


def test_load_artifact_rejects_hash_mismatch_and_nonfinite_json(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    digest = put_artifact(path, kind="test", payload={"tour": "ATP"}, created_at=now)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE artifacts SET payload=? WHERE digest=?",
            (b'{"tour":"WTA"}', digest),
        )
    with pytest.raises(ValueError, match="hash"):
        load_artifact(path, digest)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE artifacts SET payload=? WHERE digest=?",
            (b'{"rating":NaN}', digest),
        )
    with pytest.raises(ValueError, match="finite"):
        load_artifact(path, digest)


def test_manifest_rejects_duplicate_encoded_slots_even_if_hash_matches(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    artifact = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    publish_slots(path, {"tennis:ATP": artifact}, expected_manifest=None, published_at=now)
    duplicate = (
        '{"tennis:ATP":"' + artifact + '","tennis:ATP":"' + artifact + '"}'
    ).encode("utf-8")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE manifests SET payload=?", (duplicate,))

    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(path)


def test_manifest_rejects_tampered_payload_and_dangling_active_row(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    artifact = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    publish_slots(path, {"one": artifact}, expected_manifest=None, published_at=now)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE manifests SET payload=?",
            (canonical_bytes({"other": artifact}),),
        )
    with pytest.raises(ValueError, match="manifest hash"):
        load_manifest(path)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "UPDATE active_manifest SET digest=? WHERE id=1", ("e" * 64,)
        )
    with pytest.raises(ValueError, match="missing manifest"):
        load_manifest(path)


def test_publish_rejects_corrupt_referenced_artifact_and_rolls_back(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    artifact = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE artifacts SET payload=? WHERE digest=?",
            (canonical_bytes({"v": 2}), artifact),
        )

    with pytest.raises(ValueError, match="artifact hash"):
        publish_slots(
            path,
            {"one": artifact},
            expected_manifest=None,
            published_at=now,
        )
    assert load_manifest(path) == (None, {})


def test_concurrent_publish_allows_exactly_one_compare_and_swap(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    atp = put_artifact(path, kind="test", payload={"tour": "ATP"}, created_at=now)
    wta = put_artifact(path, kind="test", payload={"tour": "WTA"}, created_at=now)

    def attempt(slot, digest):
        try:
            return publish_slots(
                path,
                {slot: digest},
                expected_manifest=None,
                published_at=now,
            )
        except ManifestConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda args: attempt(*args),
                (("tennis:ATP", atp), ("tennis:WTA", wta)),
            )
        )

    assert sum(result is not None for result in results) == 1
    assert len(load_manifest(path)[1]) == 1


def test_first_install_uses_real_sqlite_types_and_keeps_history(tmp_path):
    path = tmp_path / "missing" / "models.db"
    assert load_manifest(path) == (None, {})
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    first_artifact = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    second_artifact = put_artifact(path, kind="test", payload={"v": 2}, created_at=now)
    first = publish_slots(path, {"one": first_artifact}, expected_manifest=None, published_at=now)
    second = publish_slots(path, {"two": second_artifact}, expected_manifest=first, published_at=now)

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT typeof(payload), typeof(created_at) FROM artifacts LIMIT 1"
        ).fetchone() == ("blob", "text")
        assert connection.execute(
            "SELECT typeof(payload), typeof(published_at) FROM manifests LIMIT 1"
        ).fetchone() == ("blob", "text")
        assert connection.execute(
            "SELECT digest, predecessor FROM manifests ORDER BY rowid"
        ).fetchall() == [(first, None), (second, first)]


def test_runtime_database_rejects_symlink_path(tmp_path, monkeypatch):
    path = (tmp_path / "models.db").absolute()
    original_lstat = runtime_paths.os.lstat

    def symlink_lstat(candidate, *args, **kwargs):
        if Path(candidate).absolute() == path:
            parent_stat = original_lstat(path.parent, *args, **kwargs)
            return SimpleNamespace(
                st_mode=runtime_paths.stat.S_IFLNK,
                st_uid=getattr(parent_stat, "st_uid", 0),
                st_dev=parent_stat.st_dev,
                st_ino=parent_stat.st_ino,
            )
        return original_lstat(candidate, *args, **kwargs)

    monkeypatch.setattr(runtime_paths.os, "lstat", symlink_lstat)
    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="symlink"):
        load_manifest(path)


def test_runtime_database_rejects_wrong_owner(tmp_path, monkeypatch):
    path = tmp_path / "models.db"
    assert load_manifest(path) == (None, {})
    actual_owner = path.stat().st_uid
    monkeypatch.setattr(
        runtime_paths,
        "_trusted_owner_ids",
        lambda: {actual_owner + 1},
    )

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="owner"):
        load_manifest(path)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_runtime_database_rejects_group_writable_file(tmp_path):
    path = tmp_path / "models.db"
    assert load_manifest(path) == (None, {})
    path.chmod(0o660)

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="writable"):
        load_manifest(path)
