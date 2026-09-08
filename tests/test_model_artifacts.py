from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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


def _stat_with(file_stat, **changes):
    fields = {
        name: getattr(file_stat, name)
        for name in dir(file_stat)
        if name.startswith("st_")
    }
    fields.update(changes)
    return SimpleNamespace(**fields)


def _trusted_stat(file_stat):
    return _stat_with(
        file_stat,
        st_mode=file_stat.st_mode
        & ~(runtime_paths.stat.S_IWGRP | runtime_paths.stat.S_IWOTH),
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


def test_artifact_rejects_non_string_keys_recursively_before_database_write(
    tmp_path,
):
    path = tmp_path / "models.db"
    with pytest.raises(TypeError, match="JSON object keys must be strings"):
        put_artifact(
            path,
            kind="test",
            payload={"nested": [{2: "two", 10: "ten"}]},
            created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )

    assert not path.exists()


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


def test_manifest_hash_is_verified_before_publication_cutoff(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    artifact = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    publish_slots(path, {"one": artifact}, expected_manifest=None, published_at=now)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE manifests SET published_at=?",
            ((now + timedelta(minutes=1)).isoformat(),),
        )

    with pytest.raises(ValueError, match="manifest hash"):
        load_manifest(path, decision_cutoff=now)


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


def test_first_install_requests_private_mode_for_every_missing_parent(
    tmp_path,
    monkeypatch,
):
    parents = [
        tmp_path / "first",
        tmp_path / "first" / "second",
        tmp_path / "first" / "second" / "third",
    ]
    path = parents[-1] / "models.db"
    original_mkdir = runtime_paths.os.mkdir
    created_modes = {}

    def record_successful_mkdir(candidate, mode=0o777, *args, **kwargs):
        result = original_mkdir(candidate, mode, *args, **kwargs)
        created_modes[Path(candidate).absolute()] = mode
        return result

    monkeypatch.setattr(runtime_paths.os, "mkdir", record_successful_mkdir)

    assert load_manifest(path) == (None, {})
    assert created_modes == {
        parent.absolute(): 0o700
        for parent in parents
    }


@pytest.mark.skipif(os.name == "nt", reason="POSIX process umask")
def test_posix_first_install_is_private_with_group_permissive_umask(tmp_path):
    parents = [
        tmp_path / "first",
        tmp_path / "first" / "second",
        tmp_path / "first" / "second" / "third",
    ]
    path = parents[-1] / "models.db"
    previous_umask = os.umask(0o002)
    try:
        assert load_manifest(path) == (None, {})
    finally:
        os.umask(previous_umask)

    assert [runtime_paths.stat.S_IMODE(parent.stat().st_mode) for parent in parents] == [
        0o700,
        0o700,
        0o700,
    ]


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
    original_lstat = runtime_paths.os.lstat

    def wrong_database_owner_lstat(candidate, *args, **kwargs):
        actual = original_lstat(candidate, *args, **kwargs)
        if Path(candidate).absolute() == path.absolute():
            return _stat_with(
                _trusted_stat(actual),
                st_uid=actual_owner + 1,
            )
        return _trusted_stat(actual)

    monkeypatch.setattr(
        runtime_paths.os,
        "lstat",
        wrong_database_owner_lstat,
    )
    monkeypatch.setattr(
        runtime_paths,
        "_trusted_owner_ids",
        lambda: {0, actual_owner},
    )

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="owner"):
        load_manifest(path)


def test_runtime_database_rejects_writable_ancestor_before_creating_parents(
    tmp_path,
    monkeypatch,
):
    replaceable = tmp_path / "replaceable"
    replaceable.mkdir()
    target = replaceable / "future" / "nested" / "models.db"
    original_lstat = runtime_paths.os.lstat
    replaceable_stat = original_lstat(replaceable)
    unsafe_mode = (
        replaceable_stat.st_mode | runtime_paths.stat.S_IWOTH
    ) & ~runtime_paths.stat.S_ISVTX

    def unsafe_ancestor_lstat(candidate, *args, **kwargs):
        actual = original_lstat(candidate, *args, **kwargs)
        if Path(candidate).absolute() == replaceable.absolute():
            return _stat_with(
                actual,
                st_mode=unsafe_mode,
                st_uid=replaceable_stat.st_uid,
            )
        return _trusted_stat(actual)

    monkeypatch.setattr(runtime_paths.os, "lstat", unsafe_ancestor_lstat)
    monkeypatch.setattr(
        runtime_paths,
        "_trusted_owner_ids",
        lambda: {0, replaceable_stat.st_uid},
    )

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="writable"):
        load_manifest(target)
    assert not target.parent.exists()


def test_runtime_database_rejects_untrusted_ancestor_owner_before_creation(
    tmp_path,
    monkeypatch,
):
    replaceable = tmp_path / "replaceable"
    replaceable.mkdir()
    target = replaceable / "future" / "models.db"
    original_lstat = runtime_paths.os.lstat
    replaceable_stat = original_lstat(replaceable)

    def untrusted_ancestor_lstat(candidate, *args, **kwargs):
        actual = original_lstat(candidate, *args, **kwargs)
        if Path(candidate).absolute() == replaceable.absolute():
            return _stat_with(
                actual,
                st_mode=replaceable_stat.st_mode,
                st_uid=replaceable_stat.st_uid + 1,
            )
        return _trusted_stat(actual)

    monkeypatch.setattr(runtime_paths.os, "lstat", untrusted_ancestor_lstat)
    monkeypatch.setattr(
        runtime_paths,
        "_trusted_owner_ids",
        lambda: {0, replaceable_stat.st_uid},
    )

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="owner"):
        load_manifest(target)
    assert not target.parent.exists()


def test_runtime_database_allows_trusted_sticky_writable_ancestor(
    tmp_path,
    monkeypatch,
):
    sticky = tmp_path / "sticky"
    sticky.mkdir()
    target = sticky / "future" / "models.db"
    original_lstat = runtime_paths.os.lstat
    sticky_stat = original_lstat(sticky)
    sticky_mode = (
        sticky_stat.st_mode
        | runtime_paths.stat.S_IWOTH
        | runtime_paths.stat.S_ISVTX
    )

    def sticky_ancestor_lstat(candidate, *args, **kwargs):
        actual = original_lstat(candidate, *args, **kwargs)
        if Path(candidate).absolute() == sticky.absolute():
            return _stat_with(
                actual,
                st_mode=sticky_mode,
                st_uid=sticky_stat.st_uid,
            )
        return _trusted_stat(actual)

    monkeypatch.setattr(runtime_paths.os, "lstat", sticky_ancestor_lstat)
    monkeypatch.setattr(
        runtime_paths,
        "_trusted_owner_ids",
        lambda: {0, sticky_stat.st_uid},
    )

    assert load_manifest(target) == (None, {})


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_posix_runtime_database_rejects_real_nonsticky_writable_ancestor(
    tmp_path,
):
    replaceable = tmp_path / "replaceable"
    replaceable.mkdir()
    replaceable.chmod(0o777)
    target = replaceable / "future" / "nested" / "models.db"

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="writable"):
        load_manifest(target)
    assert not target.parent.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_posix_runtime_database_allows_real_trusted_sticky_ancestor(tmp_path):
    sticky = tmp_path / "sticky"
    sticky.mkdir()
    sticky.chmod(0o1777)
    target = sticky / "future" / "models.db"

    assert load_manifest(target) == (None, {})


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_runtime_database_rejects_group_writable_file(tmp_path):
    path = tmp_path / "models.db"
    assert load_manifest(path) == (None, {})
    path.chmod(0o660)

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="writable"):
        load_manifest(path)
