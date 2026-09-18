"""Synthetic transport tests, not source or predictive qualification."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import importlib.util
import json
import sqlite3

import pytest

import challenge_engine as engine
import football_original
import model_artifacts as artifacts
from football_original import FootballOriginal
from tests.test_football_base_provenance import fixture, history, target
from tests.test_football_original_capture import calibration


NOW = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


def test_owning_storage_api_exists():
    assert importlib.util.find_spec("context_models.football_original_storage") is not None


@pytest.fixture
def storage():
    name = "context_models.football_original_storage"
    assert importlib.util.find_spec(name) is not None, "owning lossless storage is missing"
    return importlib.import_module(name)


def capture(monkeypatch, *, rows=None, current=None, teams=None, curves=None, at=NOW):
    monkeypatch.setattr(football_original, "_capture_now", lambda: at)
    saved = []
    engine.fixture_market_probabilities(target() if current is None else current,
        history() if rows is None else rows, curves, team_history=teams,
        original_capture=saved.append)
    assert len(saved) == 1
    return saved[0]


def rows_in(path):
    with sqlite3.connect(path) as conn:
        return dict((row[0], row[1:]) for row in conn.execute(
            "SELECT digest,kind,payload,created_at FROM artifacts"))


def test_exact_owning_roundtrip_and_distinct_physical_identity(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch, curves=calibration())
    plan = storage.prepare_original(original)
    assert plan.logical_digest == hashlib.sha256(original._bytes).hexdigest()
    assert plan.manifest_digest != plan.logical_digest
    path = tmp_path / "model.db"
    result = storage.store_original(path, original, created_at=NOW,
        max_new_payload_bytes=plan.payload_bytes)
    assert result.manifest_digest == plan.manifest_digest
    assert result.inserted_payload_bytes == plan.payload_bytes
    assert storage.load_original(path, result.manifest_digest)._bytes == original._bytes
    stored = rows_in(path)
    assert len(stored) == len(plan.artifacts)
    assert all(row[1] != original._bytes for row in stored.values())
    assert set(row[0] for row in stored.values()) == {storage.CHUNK_KIND, storage.BODY_KIND, storage.MANIFEST_KIND}


def test_repeated_capture_adds_only_manifest_preserves_all_existing_clocks(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch)
    path = tmp_path / "model.db"
    storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=4_000_000)
    before = rows_in(path)
    later = capture(monkeypatch, at=NOW + timedelta(seconds=1))
    result = storage.store_original(path, later, created_at=NOW + timedelta(seconds=2), max_new_payload_bytes=8192)
    after = rows_in(path)
    assert {k: after[k] for k in before} == before
    added = set(after) - set(before)
    assert added == {result.manifest_digest}
    assert after[result.manifest_digest][0] == storage.MANIFEST_KIND
    assert 0 < result.inserted_payload_bytes <= 8192
    retry = storage.store_original(path, later, created_at=NOW + timedelta(days=1), max_new_payload_bytes=0)
    assert retry.inserted_payload_bytes == 0 and rows_in(path) == after


def test_fixed_paths_share_sixteen_equal_priors_and_keep_duplicates(storage, monkeypatch, tmp_path):
    raw = [fixture(i + 1, i // 4, *([(1, 3), (4, 2), (5, 6), (7, 8)][i % 4])) for i in range(128)]
    raw.append(deepcopy(raw[-1]))
    original = capture(monkeypatch, rows=raw, teams=list(reversed(raw)))
    plan = storage.prepare_original(original)
    body = json.loads(next(obj.payload_bytes for obj in plan.artifacts if obj.kind == storage.BODY_KIND))
    priors = [term["prior_refs"]["digest"] for head in body["goal_provenance"]["reference_weights"]["heads"].values()
        for component in head["components"].values() for term in (component["goals"], component["xg"])]
    assert len(priors) == 16 and len(set(priors)) == 1
    path = tmp_path / "model.db"
    result = storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=4_000_000)
    restored = storage.load_original(path, result.manifest_digest)
    assert restored._bytes == original._bytes
    assert restored.to_dict()["league_history"][-2:] == [original.to_dict()["league_history"][-1]] * 2


def test_unavailable_provenance_stays_literal(storage, monkeypatch, tmp_path):
    raw = history()
    raw[2]["challenge_stats"] = {"xg_home": 10 ** 1000, "xg_away": 1.0}
    original = capture(monkeypatch, rows=raw)
    assert original.to_dict()["goal_provenance"]["reference_weights"]["kind"] == "unavailable"
    plan = storage.prepare_original(original)
    body = json.loads(next(obj.payload_bytes for obj in plan.artifacts if obj.kind == storage.BODY_KIND))
    assert body["goal_provenance"] == original.to_dict()["goal_provenance"]
    result = storage.store_original(tmp_path / "m.db", original, created_at=NOW, max_new_payload_bytes=4_000_000)
    assert storage.load_original(tmp_path / "m.db", result.manifest_digest)._bytes == original._bytes


@pytest.mark.parametrize("change", ["event", "score", "xg", "order", "recipe"])
def test_real_model_changes_reuse_only_unchanged_arrays(storage, monkeypatch, change):
    before = storage.prepare_original(capture(monkeypatch))
    raw, current, curves = history(), target(), None
    if change == "event": current["fixture"]["id"] += 1
    if change == "score": raw[0]["goals"]["home"] += 1
    if change == "xg": raw[4]["challenge_stats"]["xg_home"] += .123456789012345
    if change == "order": raw.reverse()
    if change == "recipe": curves = calibration()
    after = storage.prepare_original(capture(monkeypatch, rows=raw, current=current, curves=curves))
    first_chunks = {a.digest for a in before.artifacts if a.kind == storage.CHUNK_KIND}
    second_chunks = {a.digest for a in after.artifacts if a.kind == storage.CHUNK_KIND}
    assert before.body_digest != after.body_digest
    assert before.logical_digest != after.logical_digest
    if change in {"event", "recipe"}:
        assert first_chunks == second_chunks
    else:
        assert first_chunks != second_chunks


@pytest.mark.parametrize("budget", [-1, True, 1.0, float("inf"), None])
def test_budget_is_required_finite_integer_before_mutation(storage, monkeypatch, tmp_path, budget):
    with pytest.raises((ValueError, TypeError)):
        storage.store_original(tmp_path / "m.db", capture(monkeypatch), created_at=NOW, max_new_payload_bytes=budget)
    assert not (tmp_path / "m.db").exists()


def test_budget_failure_has_no_partial_objects_and_outer_publication_can_roll_back(storage, monkeypatch, tmp_path):
    plan = storage.prepare_original(capture(monkeypatch))
    path = tmp_path / "m.db"
    with closing(artifacts._connect(path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(storage.StorageBudgetExceeded):
            storage.publish_prepared(conn, plan, created_at=NOW, max_new_payload_bytes=plan.payload_bytes - 1)
        assert conn.in_transaction and conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 0
        result = storage.publish_prepared(conn, plan, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
        assert result.inserted_payload_bytes == plan.payload_bytes
        conn.rollback()
    assert rows_in(path) == {}


@pytest.mark.parametrize("fault", ["collision", "readback"])
def test_atomic_collision_and_trigger_readback_failure_leave_no_orphans(storage, monkeypatch, tmp_path, fault):
    original = capture(monkeypatch)
    plan = storage.prepare_original(original)
    path = tmp_path / "m.db"
    with closing(artifacts._connect(path)) as conn, conn:
        if fault == "collision":
            conn.execute("INSERT INTO artifacts VALUES (?,?,?,?)", (plan.manifest_digest, "wrong", b'{}', NOW.isoformat()))
        else:
            conn.execute("CREATE TRIGGER corrupt AFTER INSERT ON artifacts WHEN NEW.kind='football-original-storage-manifest-v1' BEGIN UPDATE artifacts SET payload=x'7b7d' WHERE digest=NEW.digest; END")
    before = rows_in(path)
    with pytest.raises(ValueError):
        storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
    assert rows_in(path) == before


def test_concurrent_connections_deduplicate_and_zero_budget_retry(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch)
    plan = storage.prepare_original(original)
    path = tmp_path / "m.db"
    def write(_):
        return storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(write, range(4)))
    assert sum(result.inserted_payload_bytes for result in results) == plan.payload_bytes
    assert len(rows_in(path)) == len(plan.artifacts)
    assert storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=0).inserted_payload_bytes == 0


@pytest.mark.parametrize("mutation", ["schema", "clock", "kind", "array", "oversize", "recursive"])
def test_invalid_owning_packets_fail_before_database_creation(storage, monkeypatch, tmp_path, mutation):
    value = capture(monkeypatch).to_dict()
    if mutation == "schema": value["schema"] = True
    if mutation == "clock": value["captured_at"] = NOW.isoformat()
    if mutation == "kind": value["kind"] = "unknown"
    if mutation == "array": value["league_history"] = {}
    if mutation == "oversize": value["prediction_version"] = "x" * (4 * 1024 * 1024)
    if mutation == "recursive": value["league_history"] = [{"schema": 1, "kind": storage.CHUNK_KIND, "digest": "0" * 64}]
    with pytest.raises(ValueError):
        storage.store_original(tmp_path / "m.db", FootballOriginal(artifacts.canonical_bytes(value)), created_at=NOW, max_new_payload_bytes=8_000_000)
    assert not (tmp_path / "m.db").exists()


@pytest.mark.parametrize("part", ["manifest", "body", "chunk"])
@pytest.mark.parametrize("fault", ["missing", "hash", "created_type", "future"])
def test_required_raw_objects_and_actual_clocks_are_checked(storage, monkeypatch, tmp_path, part, fault):
    original = capture(monkeypatch)
    plan = storage.prepare_original(original)
    path = tmp_path / "m.db"
    storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
    ref = {"manifest": plan.manifest_digest, "body": plan.body_digest,
        "chunk": next(a.digest for a in plan.artifacts if a.kind == storage.CHUNK_KIND)}[part]
    with sqlite3.connect(path) as conn:
        if fault == "missing": conn.execute("DELETE FROM artifacts WHERE digest=?", (ref,))
        if fault == "hash": conn.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b'{}', ref))
        if fault == "created_type": conn.execute("UPDATE artifacts SET created_at=? WHERE digest=?", (b'bad', ref))
        if fault == "future":
            # Manifest creation cannot predate capture; dependencies cannot postdate manifest.
            clock = NOW - timedelta(seconds=1) if part == "manifest" else NOW + timedelta(seconds=1)
            conn.execute("UPDATE artifacts SET created_at=? WHERE digest=?", (clock.isoformat(timespec="microseconds").replace("+00:00", "Z"), ref))
    with pytest.raises((ValueError, KeyError)):
        storage.load_original(path, plan.manifest_digest)


def test_season380_payload_reuse_and_sqlite_growth(storage, monkeypatch, tmp_path, capsys):
    raw = [fixture(i + 1, i // 4, *([(1, 3), (4, 2), (5, 6), (7, 8)][i % 4])) for i in range(380)]
    current = fixture(10001, 100, 1, 2, xg=False, goals=False)
    original = capture(monkeypatch, rows=raw, current=current)
    plan = storage.prepare_original(original)
    assert plan.payload_bytes < len(original._bytes) * .4
    path = tmp_path / "season.db"
    with closing(artifacts._connect(path)): pass
    empty_size = path.stat().st_size
    storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
    first_size = path.stat().st_size
    later = capture(monkeypatch, rows=raw, current=current, at=NOW + timedelta(seconds=1))
    added = storage.store_original(path, later, created_at=NOW + timedelta(seconds=1), max_new_payload_bytes=8192)
    repeat_size = path.stat().st_size
    assert 0 < added.inserted_payload_bytes <= 8192
    assert storage.load_original(path, plan.manifest_digest)._bytes == original._bytes
    with capsys.disabled():
        print({"expanded_bytes": len(original._bytes), "unique_payload_bytes": plan.payload_bytes,
            "unique_objects": len(plan.artifacts), "initial_sqlite_growth": first_size - empty_size,
            "repeat_payload_bytes": added.inserted_payload_bytes, "repeat_sqlite_growth": repeat_size - first_size})


def test_late_trigger_mutating_an_earlier_chunk_is_detected_and_rolled_back(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch)
    path = tmp_path / "m.db"
    with closing(artifacts._connect(path)) as conn, conn:
        conn.execute("CREATE TRIGGER corrupt_prior AFTER INSERT ON artifacts WHEN NEW.kind='football-original-storage-manifest-v1' BEGIN UPDATE artifacts SET payload=x'7b7d' WHERE kind='football-original-json-chunk-v1'; END")
    with pytest.raises(ValueError):
        storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=4_000_000)
    assert rows_in(path) == {}


def test_creation_before_capture_is_rejected_before_any_database_mutation(storage, monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        storage.store_original(tmp_path / "m.db", capture(monkeypatch), created_at=NOW - timedelta(seconds=1), max_new_payload_bytes=4_000_000)
    assert not (tmp_path / "m.db").exists()


def test_outer_unrelated_writes_survive_failed_savepoint(storage, monkeypatch, tmp_path):
    plan = storage.prepare_original(capture(monkeypatch))
    path = tmp_path / "m.db"
    with closing(artifacts._connect(path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO artifacts VALUES (?,?,?,?)", ("1" * 64, "outer-sentinel", b'{}', NOW.isoformat()))
        with pytest.raises(storage.StorageBudgetExceeded):
            storage.publish_prepared(conn, plan, created_at=NOW, max_new_payload_bytes=0)
        conn.commit()
    assert set(rows_in(path)) == {"1" * 64}


def test_python_decode_occurs_only_after_read_snapshot_release(storage, monkeypatch, tmp_path):
    from contextlib import contextmanager
    original = capture(monkeypatch)
    path = tmp_path / "m.db"
    result = storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=4_000_000)
    reader, decode = storage._reader, artifacts._decode_artifact_row
    active = []
    @contextmanager
    def tracked(path):
        with reader(path) as conn:
            active.append(True)
            try: yield conn
            finally: active.pop()
    def checked(*args):
        assert not active, "Python decoded while the read transaction was held"
        return decode(*args)
    monkeypatch.setattr(storage, "_reader", tracked)
    monkeypatch.setattr(artifacts, "_decode_artifact_row", checked)
    assert storage.load_original(path, result.manifest_digest)._bytes == original._bytes


def test_reading_missing_db_does_not_create_it(storage, tmp_path):
    path = tmp_path / "absent.db"
    with pytest.raises(ValueError): storage.load_original(path, "0" * 64)
    assert not path.exists()


@pytest.mark.parametrize("fault", ["ref_extra", "ref_kind", "ref_schema", "digest", "logical", "chunk_type", "chunk_schema", "recursive", "expanded_bomb", "manifest_large", "nul_key", "duplicate_key", "noncanonical", "nonfinite", "sql_json"])
def test_forged_valid_hash_graphs_and_addressing_hints_fail_closed(storage, monkeypatch, tmp_path, fault):
    original = capture(monkeypatch)
    path = tmp_path / "m.db"
    result = storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=4_000_000)
    plan = storage.prepare_original(original)
    saved = rows_in(path)
    body = json.loads(saved[plan.body_digest][1])
    manifest = json.loads(saved[plan.manifest_digest][1])
    def forge(kind, payload):
        # Direct insertion deliberately bypasses the owner, but preserves A1 hash.
        encoded = artifacts.canonical_bytes(payload)
        digest = hashlib.sha256(artifacts.canonical_bytes({"kind": kind, "payload": payload})).hexdigest()
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?)", (digest, kind, encoded, "2026-09-18T12:00:00.000000Z"))
        return digest
    if fault.startswith("ref_") or fault == "digest":
        ref = body["league_history"]
        if fault == "ref_extra": ref["values"] = []
        if fault == "ref_kind": ref["kind"] = storage.BODY_KIND
        if fault == "ref_schema": ref["schema"] = True
        if fault == "digest": ref["digest"] = "F" * 64
    if fault in {"chunk_type", "chunk_schema", "recursive", "expanded_bomb"}:
        payload = {"schema": 1, "values": []}
        if fault == "chunk_type": payload["values"] = {}
        if fault == "chunk_schema": payload["schema"] = True
        if fault == "recursive": payload["values"] = [dict(body["league_history"])]
        if fault == "expanded_bomb": payload["values"] = ["x" * 300_000]
        digest = forge(storage.CHUNK_KIND, payload)
        if fault == "expanded_bomb":
            for head in body["goal_provenance"]["reference_weights"]["heads"].values():
                for component in head["components"].values():
                    for metric in ("goals", "xg"): component[metric]["prior_refs"]["digest"] = digest
        else: body["league_history"]["digest"] = digest
    if fault == "nul_key": body["league_history\x00forged"] = body.pop("league_history")
    manifest["body"]["digest"] = forge(storage.BODY_KIND, body)
    if fault == "logical": manifest["logical_digest"] = "0" * 64
    if fault == "manifest_large": manifest["extra"] = "x" * 8192
    ref = forge(storage.MANIFEST_KIND, manifest)
    if fault in {"duplicate_key", "noncanonical", "nonfinite", "sql_json"}:
        payload = artifacts.canonical_bytes(manifest)
        if fault == "duplicate_key": payload = b'{"schema":1,' + payload[1:]
        if fault == "noncanonical": payload = b' ' + payload
        if fault == "nonfinite": payload = payload.replace(b'"schema":1', b'"schema":NaN')
        if fault == "sql_json": payload = b'not-json'
        with sqlite3.connect(path) as conn: conn.execute("UPDATE artifacts SET payload=? WHERE digest=?", (payload, ref))
    before = rows_in(path)
    with pytest.raises(ValueError): storage.load_original(path, ref)
    assert rows_in(path) == before


def test_snapshot_remains_consistent_during_real_concurrent_rewrite(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch)
    path = tmp_path / "m.db"
    plan = storage.prepare_original(original)
    storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO artifacts VALUES (?,?,?,?)", ("2" * 64, "unrelated-corrupt", b'not-json', "bad"))
    raw_reader = storage._raw
    changed = []
    chunk = next(obj.digest for obj in plan.artifacts if obj.kind == storage.CHUNK_KIND)
    def concurrent_reader(conn, ref, limit):
        row = raw_reader(conn, ref, limit)
        if not changed:
            changed.append(True)
            with sqlite3.connect(path) as writer:
                writer.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b'{}', chunk))
        return row
    monkeypatch.setattr(storage, "_raw", concurrent_reader)
    assert storage.load_original(path, plan.manifest_digest)._bytes == original._bytes
    with pytest.raises(ValueError): storage.load_original(path, plan.manifest_digest)


@pytest.mark.parametrize("clock", ["bad", "2026-09-18T12:00:00+00:00", "2026-09-18T12:00:01.000000Z"])
def test_reused_dependency_actual_clock_cannot_be_replaced_by_retry_clock(storage, monkeypatch, tmp_path, clock):
    original = capture(monkeypatch)
    plan = storage.prepare_original(original)
    path = tmp_path / "m.db"
    storage.store_original(path, original, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
    with sqlite3.connect(path) as conn: conn.execute("UPDATE artifacts SET created_at=? WHERE digest=?", (clock, plan.body_digest))
    before = rows_in(path)
    with pytest.raises(ValueError):
        storage.store_original(path, original, created_at=NOW + timedelta(days=1), max_new_payload_bytes=0)
    assert rows_in(path) == before


def test_outer_caller_can_atomically_add_a1_binding_without_expanded_original(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch)
    plan = storage.prepare_original(original)
    path = tmp_path / "m.db"
    with closing(artifacts._connect(path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        result = storage.publish_prepared(conn, plan, created_at=NOW, max_new_payload_bytes=plan.payload_bytes)
        binding = artifacts.prepare_artifact(kind="test-only-outer-binding", payload={"original": result.manifest_digest})
        artifacts._insert_artifact(conn, binding, NOW.isoformat())
        conn.commit()
    assert binding.digest in rows_in(path)
    assert storage.load_original(path, result.manifest_digest)._bytes == original._bytes


def test_storage_rejects_plain_json_noncanonical_bytes_and_wrong_prepared_type(storage, monkeypatch, tmp_path):
    original = capture(monkeypatch)
    with pytest.raises(TypeError): storage.prepare_original(original.to_dict())
    with pytest.raises(ValueError): storage.prepare_original(FootballOriginal(b' ' + original._bytes))
    with closing(artifacts._connect(tmp_path / "m.db")) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(TypeError): storage.publish_prepared(conn, {}, created_at=NOW, max_new_payload_bytes=0)
        conn.rollback()
