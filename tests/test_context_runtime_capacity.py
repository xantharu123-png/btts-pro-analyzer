"""Bounded D4 transport/inventory, not Linux deployment or empirical proof."""
from contextlib import closing
from datetime import datetime, timedelta
import os
import sqlite3
import sys
from pathlib import Path

import pytest

import context_runtime as runtime
from model_artifacts import ArtifactIntegrityError, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_backup import seeded, add_receipt, cli


def test_explicit_memory_mode_preserves_report_and_rejects_unknown_mode(tmp_path):
    path = tmp_path / "context.db"
    seeded(path)
    expected = runtime.verify_context_database(path)
    assert runtime.verify_context_database(path, input_mode="memory") == expected
    with pytest.raises(RuntimeArtifactTrustError, match="unsupported"):
        runtime.verify_context_database(path, input_mode="auto")


def test_large_input_does_not_implicitly_switch_to_file_mode(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    seeded(path)
    monkeypatch.setattr(runtime, "MAX_CONTEXT_IMAGE_BYTES", path.stat().st_size - 1)
    with pytest.raises(RuntimeArtifactTrustError, match="size"):
        runtime.verify_context_database(path)


def test_no_originals_do_not_require_original_replay_code(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    seeded(path)
    def unavailable():
        pytest.fail("unrelated original replay code was requested")
    monkeypatch.setattr("context_runtime_tennis._code_variants", unavailable)
    assert runtime.verify_context_database(path)["counts"]["artifacts"] == 2


def test_sealed_cli_is_explicit_and_fails_closed_on_windows(tmp_path):
    path = tmp_path / "context.db"
    seeded(path)
    result = cli(path, "--sealed-file")
    # A normal writable fixture is never sealed, on any OS.
    assert result.returncode == 1
    assert '"error_type": "RuntimeArtifactTrustError"' in result.stdout


def test_lazy_inventory_complete_independent_values_and_closed_connection(tmp_path):
    from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
    path = tmp_path / "context.db"
    _, atp, wta = seeded(path)
    refs = [add_receipt(path, revision=f"r{i}") for i in range(5)]
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("BEGIN")
        artifacts = VerifiedArtifactMapping(conn)
        receipts = VerifiedReceiptMapping(conn)
        assert set(artifacts) == {atp, wta}
        assert set(receipts) == set(refs)
        assert len(receipts) == 5
        receipts[refs[0]]["payload"]["sets"] = -999
        artifacts[atp]["payload"]["state"].clear()
        assert receipts[refs[0]]["payload"]["sets"] == 3
        assert artifacts[atp]["payload"]["state"]
        assert refs[0] in receipts and "0" * 64 not in receipts
        with pytest.raises(KeyError):
            receipts["0" * 64]
        with pytest.raises(TypeError):
            receipts[refs[0]] = {}
    for operation in (lambda: receipts[refs[0]], lambda: len(artifacts),
                      lambda: refs[0] in receipts, lambda: list(artifacts)):
        with pytest.raises((sqlite3.ProgrammingError, RuntimeArtifactTrustError)):
            operation()


@pytest.mark.parametrize("damage", ["orphan", "unreferenced_receipt"])
def test_complete_inventory_rejects_unreferenced_corruption(tmp_path, damage):
    path = tmp_path / "context.db"
    seeded(path)
    add_receipt(path)
    with closing(sqlite3.connect(path)) as conn, conn:
        if damage == "orphan":
            from context_models.contracts import digest
            content = {"orphan": True}
            conn.execute("INSERT INTO context_contents VALUES (?,?)", (digest(content), canonical_bytes(content)))
        else:
            conn.execute("UPDATE context_observations SET source='wrong-source'")
    with pytest.raises(ArtifactIntegrityError):
        runtime.verify_context_database(path)


def test_lazy_membership_does_not_decode_unopened_final(tmp_path, monkeypatch):
    from context_dataset_helpers import stored_packet
    from context_runtime_inventory import VerifiedReceiptMapping
    import context_observations
    packet = stored_packet(tmp_path)
    finals = {item["event"]["event_key"] for item in packet["plan"]["test_inventory"]}
    original = context_observations._decode_receipt
    def guarded(row):
        if row[2] in finals and row[7] == "match_outcome":
            pytest.fail("protected final decoded")
        return original(row)
    monkeypatch.setattr(context_observations, "_decode_receipt", guarded)
    monkeypatch.setattr(runtime, "_decode_receipt", guarded)
    with closing(sqlite3.connect(packet["path"])) as conn:
        conn.execute("BEGIN")
        refs = {r for r, event, kind in conn.execute(
            "SELECT digest,event_key,kind FROM context_observations") if event in finals and kind == "match_outcome"}
        assert refs
        receipts = VerifiedReceiptMapping(conn, protected_receipts=refs)
        assert refs <= set(receipts)
        for ref in refs:
            assert ref in receipts
            assert "source_schema" not in receipts[ref]
    report = runtime.verify_context_database(packet["path"])
    assert "d2-final-source-replay-not-opened" in report["limitations"]
    with closing(sqlite3.connect(packet["path"])) as conn, conn:
        ordinary = conn.execute("SELECT digest FROM context_observations WHERE kind!='match_outcome' LIMIT 1").fetchone()[0]
        conn.execute("UPDATE context_observations SET source='corrupted-ordinary' WHERE digest=?", (ordinary,))
    with pytest.raises(ArtifactIntegrityError):
        runtime.verify_context_database(packet["path"])


def test_original_descriptors_release_histories_between_cutoffs(tmp_path, monkeypatch):
    from test_tennis_live_worker import configure, run_batch, NOW
    from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
    from context_runtime_tennis import verify_live_originals, LiveReplayDescriptor
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions, decision=NOW-timedelta(seconds=1))
    run_batch(db, predictions)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("BEGIN")
        artifacts, receipts = VerifiedArtifactMapping(conn), VerifiedReceiptMapping(conn)
        clocks = {ref: datetime.fromisoformat(clock) for ref, clock in conn.execute("SELECT digest,created_at FROM artifacts")}
        descriptors = verify_live_originals(artifacts, clocks, receipts, set())
        assert len(descriptors) == 2
        assert all(isinstance(value, LiveReplayDescriptor) for value in descriptors.values())
        assert all(not hasattr(value, "history") and not hasattr(value, "base") for value in descriptors.values())
    assert runtime.verify_context_database(db)["counts"]["snapshots"] == 2


def test_history_budget_rejects_complete_replay_without_truncation(tmp_path, monkeypatch):
    from test_context_runtime_tennis_live import _stored
    from context_runtime_inventory import VerifiedReceiptMapping
    from context_runtime_tennis import _replay_history
    from test_tennis_live_worker import NOW
    db, _ = _stored(monkeypatch, tmp_path)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        complete = _replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        assert type(complete) is tuple and len(complete) == 1
        with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
            _replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=1)
        assert _replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None) == complete


def test_strict_reader_never_accepts_unprovable_platform(tmp_path):
    from context_runtime_input import open_sealed_connection
    if sys.platform == "linux":
        pytest.skip("non-Linux platform fail-closed check")
    path = tmp_path / "context.db"
    seeded(path)
    with pytest.raises(RuntimeArtifactTrustError, match="Linux"):
        with open_sealed_connection(path, max_bytes=1024**3):
            pytest.fail("unprovable sealed reader yielded")


@pytest.fixture
def linux_seal():
    if sys.platform != "linux":
        pytest.skip("real Linux DAC fixtures unavailable on Windows")
    if os.geteuid() == 0:
        pytest.fail("run app/model tests as the application user, never root")
    directory = os.environ.get("CONTEXT_CAPACITY_TEST_ROOT")
    if not directory:
        pytest.skip("controller must provide root-staged CONTEXT_CAPACITY_TEST_ROOT fixtures")
    return Path(directory) / "valid" / "context.db"


def test_linux_real_dac_and_sqlite_readonly(linux_seal):
    from context_runtime_input import open_sealed_connection
    for operation in (lambda: os.open(linux_seal, os.O_WRONLY),
                      lambda: linux_seal.rename(linux_seal.with_suffix(".moved"))):
        with pytest.raises(PermissionError):
            operation()
    with open_sealed_connection(linux_seal, max_bytes=1024**3) as conn:
        assert conn.in_transaction
        assert conn.execute("SELECT count(*) FROM artifacts").fetchone() == (2,)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM artifacts")
    assert runtime.verify_context_database(linux_seal, input_mode="sealed_file") == runtime.verify_context_database(linux_seal)


@pytest.mark.parametrize("damage", ["hardlink", "symlink", "owner", "mode", "ancestor_mode", "sidecar", "wal", "budget"])
def test_linux_sealed_reader_rejects_unsealed_inputs(linux_seal, damage):
    from context_runtime_input import open_sealed_connection
    path = linux_seal if damage == "budget" else linux_seal.parent.parent / damage / "context.db"
    # A missing fixture must never count as a successful trust rejection.
    assert path.exists(), f"controller fixture missing: {damage}"
    with pytest.raises(RuntimeArtifactTrustError):
        with open_sealed_connection(path, max_bytes=1 if damage == "budget" else 1024**3):
            pytest.fail("unsealed input yielded")
