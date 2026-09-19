"""Shared physical lists preserve all existing logical snapshot identities."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError
from context_snapshot_storage import MAGIC, compact_snapshots, pack_payload
from context_snapshots import _connect, _decode_snapshot, _payload_digest, compute_once
from model_artifacts import canonical_bytes


def packet(count=1000, market="home"):
    return {"observation_refs": [hashlib.sha256(str(i).encode()).hexdigest() for i in range(count)],
            "selection": market, "p": .46, "text": "Müdigkeit"}


def logical_rows(path):
    with sqlite3.connect(path) as con:
        return {key: canonical_bytes(_decode_snapshot(key, raw, sha, connection=con))
                for key, raw, sha in con.execute("SELECT key,payload,payload_digest FROM context_snapshots")}


def test_shared_list_is_stored_once_and_logical_identity_is_unchanged(tmp_path):
    path = tmp_path/"context.db"
    first, second = packet(), packet(market="away")
    assert compute_once(path, "a"*64, lambda: first) == first
    assert compute_once(path, "b"*64, lambda: second) == second
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT count(*) FROM context_snapshot_references").fetchone() == (1,)
        assert con.execute("SELECT sum(length(payload)) FROM context_snapshot_reference_blocks").fetchone() == (32_000,)
        for key, raw, sha in con.execute("SELECT key,payload,payload_digest FROM context_snapshots"):
            assert raw.startswith(MAGIC) and len(raw) < 500
            expected = first if key == "a"*64 else second
            assert sha == _payload_digest(key, expected)
            assert _decode_snapshot(key, raw, sha, connection=con) == expected
    first["observation_refs"].clear()
    assert len(compute_once(path, "a"*64, lambda: pytest.fail("already stored"))["observation_refs"]) == 1000


@pytest.mark.parametrize("defect", ["delete", "bytes", "text", "key", "header", "wrong-list"])
def test_corrupt_shared_storage_cannot_be_recomputed(tmp_path, defect):
    path = tmp_path/"context.db"
    compute_once(path, "a"*64, lambda: packet())
    with sqlite3.connect(path) as con:
        if defect == "delete": con.execute("DELETE FROM context_snapshot_references")
        elif defect == "bytes": con.execute("UPDATE context_snapshot_references SET payload=?", (b"x"*32_000,))
        elif defect == "text": con.execute("UPDATE context_snapshot_references SET payload=CAST(payload AS TEXT)")
        elif defect == "key": con.execute("UPDATE context_snapshot_references SET digest=?", ("c"*64,))
        elif defect == "header": con.execute("UPDATE context_snapshots SET payload=?", (MAGIC+b'{"header":{},"refs_digest":"' + b"d"*64 + b'"}',))
        else:
            changed = packet()
            changed["observation_refs"].reverse()
            raw, reference = pack_payload(changed)
            con.execute("INSERT INTO context_snapshot_references VALUES (?,?)", reference)
            con.execute("UPDATE context_snapshots SET payload=?", (raw,))
    with pytest.raises(ContextIntegrityError):
        compute_once(path, "a"*64, lambda: pytest.fail("must not replace corrupt snapshot"))


def test_compaction_is_atomic_idempotent_and_preserves_legacy_bytes(tmp_path):
    path = tmp_path/"context.db"
    con = _connect(path)
    for key, value in (("a"*64, packet()), ("b"*64, packet(market="away")), ("c"*64, {"legacy": True})):
        con.execute("INSERT INTO context_snapshots VALUES (?,?,?)", (key, canonical_bytes(value), _payload_digest(key, value)))
    con.commit()
    con.close()
    before = logical_rows(path)
    report = compact_snapshots(path, vacuum=True)
    assert report["converted_snapshots"] == 2 and report["shared_reference_sets"] == 1
    assert report["database_bytes_after"] < report["database_bytes_before"]
    assert logical_rows(path) == before
    assert compact_snapshots(path)["converted_snapshots"] == 0


@pytest.mark.parametrize("inline_only", [False, True])
def test_late_corruption_rolls_back_every_conversion(tmp_path, inline_only):
    path = tmp_path/"context.db"
    con = _connect(path)
    for key in ("a"*64, "b"*64):
        con.execute("INSERT INTO context_snapshots VALUES (?,?,?)", (key, canonical_bytes(packet()), _payload_digest(key, packet())))
    con.execute("UPDATE context_snapshots SET payload_digest=? WHERE key=?", ("f"*64, "b"*64))
    con.commit()
    before = con.execute("SELECT * FROM context_snapshots ORDER BY key").fetchall()
    con.close()
    with pytest.raises(ContextIntegrityError): compact_snapshots(path, inline_only=inline_only)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT * FROM context_snapshots ORDER BY key").fetchall() == before
        assert con.execute("SELECT count(*) FROM context_snapshot_references").fetchone() == (0,)


def test_parallel_publications_share_one_list(tmp_path):
    path = tmp_path/"context.db"
    def publish(i):
        return compute_once(path, hashlib.sha256(str(i).encode()).hexdigest(), lambda: packet(market=str(i)))
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert len(list(pool.map(publish, range(8)))) == 8
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT count(*) FROM context_snapshot_references").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM context_snapshots").fetchone() == (8,)


@pytest.mark.parametrize("count", [0, 127, 128, 1000])
def test_compaction_retains_order_duplicates_and_boundary(count, tmp_path):
    value = packet(count)
    value["observation_refs"] = ["a"*64]*count
    assert compute_once(tmp_path/"db", "d"*64, lambda: value) == value


def test_growing_sorted_history_reuses_unchanged_prefix_blocks(tmp_path):
    path = tmp_path/"db"
    first = packet(10_000)
    first["observation_refs"].sort()
    compute_once(path, "a"*64, lambda: first)
    with sqlite3.connect(path) as con:
        before = dict(con.execute("SELECT digest,length(payload) FROM context_snapshot_reference_blocks"))
    extra = hashlib.sha256(b"new receipt").hexdigest()
    second = {**first, "observation_refs": sorted(first["observation_refs"] + [extra])}
    assert compute_once(path, "b"*64, lambda: second) == second
    with sqlite3.connect(path) as con:
        after = dict(con.execute("SELECT digest,length(payload) FROM context_snapshot_reference_blocks"))
    assert before.keys() <= after.keys()
    assert len(after)-len(before) == 1
    assert sum(after.values())-sum(before.values()) < 3000
    assert logical_rows(path)["a"*64] == canonical_bytes(first)


@pytest.mark.parametrize("defect", ["missing", "bytes", "text"])
def test_corrupt_shared_block_is_rejected(tmp_path, defect):
    path = tmp_path/"db"
    value = packet()
    value["observation_refs"].sort()
    compute_once(path, "a"*64, lambda: value)
    with sqlite3.connect(path) as con:
        if defect == "missing": con.execute("DELETE FROM context_snapshot_reference_blocks")
        elif defect == "bytes": con.execute("UPDATE context_snapshot_reference_blocks SET payload=?", (b"x"*32,))
        else: con.execute("UPDATE context_snapshot_reference_blocks SET payload='text'")
    with pytest.raises(ContextIntegrityError): compute_once(path, "a"*64, lambda: pytest.fail("must not replace"))


def test_deployment_verifier_checks_shared_links_without_model_replay(tmp_path):
    from context_runtime_deployment import verify_context_deployment
    from model_artifacts import ArtifactIntegrityError
    path = tmp_path/"context.db"
    compute_once(path, "a"*64, lambda: packet())
    assert verify_context_deployment(path)["counts"]["snapshots"] == 1
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM context_snapshot_references")
    with pytest.raises(ArtifactIntegrityError): verify_context_deployment(path)


@pytest.mark.parametrize("count", [500_000, 500_001, 1_050_001])
def test_large_histories_never_fall_back_to_a_full_list_per_snapshot(tmp_path, count):
    """Cross both the former 500k cutoff and the 512-block reader limit."""
    path = tmp_path / "large.db"
    first = packet(count)
    second = {**first, "selection": "away"}
    assert compute_once(path, "a" * 64, lambda: first) == first
    with sqlite3.connect(path) as con:
        initial_blocks = dict(con.execute(
            "SELECT digest,length(payload) FROM context_snapshot_reference_blocks"))
    assert compute_once(path, "b" * 64, lambda: second) == second
    with sqlite3.connect(path) as con:
        assert dict(con.execute(
            "SELECT digest,length(payload) FROM context_snapshot_reference_blocks")) == initial_blocks
        assert sum(initial_blocks.values()) == count * 32
        assert con.execute("SELECT count(*) FROM context_snapshot_references").fetchone() == (1,)
        for key, raw, sha in con.execute("SELECT key,payload,payload_digest FROM context_snapshots"):
            assert len(raw) < 500, "a snapshot must not contain the complete history list"
            expected = first if key == "a" * 64 else second
            assert _decode_snapshot(key, raw, sha, connection=con) == expected
    assert compute_once(path, "b" * 64, lambda: pytest.fail("must reuse stored snapshot")) == second


@pytest.mark.parametrize("inline_only", [False, True])
def test_compaction_recovers_oversized_legacy_snapshots_without_changing_identity(tmp_path, inline_only):
    path = tmp_path / "legacy-large.db"
    existing = packet()
    compute_once(path, "a" * 64, lambda: existing)
    value = packet(500_001)
    key = "c" * 64
    original = canonical_bytes(value)
    original_hash = _payload_digest(key, value)
    con = _connect(path)
    con.execute("INSERT INTO context_snapshots VALUES (?,?,?)", (key, original, original_hash))
    con.commit()
    con.close()
    report = compact_snapshots(path, vacuum=True, inline_only=inline_only)
    assert report["converted_snapshots"] == 1
    assert report["logical_snapshot_bytes"] == len(original) + (0 if inline_only else len(canonical_bytes(existing)))
    assert report["database_bytes_after"] < report["database_bytes_before"] * .60
    with sqlite3.connect(path) as con:
        raw, sha = con.execute("SELECT payload,payload_digest FROM context_snapshots WHERE key=?", (key,)).fetchone()
        assert sha == original_hash
        assert len(raw) < 500
        assert canonical_bytes(_decode_snapshot(key, raw, sha, connection=con)) == original
        existing_raw, existing_hash = con.execute("SELECT payload,payload_digest FROM context_snapshots WHERE key=?", ("a" * 64,)).fetchone()
        assert _decode_snapshot("a" * 64, existing_raw, existing_hash, connection=con) == existing
