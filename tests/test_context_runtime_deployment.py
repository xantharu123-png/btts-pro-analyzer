"""Release readiness is deliberately separate from historical model evidence."""
from contextlib import closing
import json
import sqlite3

import pytest

from context_runtime_deployment import DEPLOYMENT_CHECKS, verify_context_deployment
from model_artifacts import ArtifactIntegrityError, publish_slots
from runtime_paths import RuntimeArtifactTrustError
from tests.test_context_runtime_backup import NOW, add_receipt, seeded


def test_operational_check_loads_both_tours_without_history_replay(tmp_path, monkeypatch):
    import context_runtime
    import context_runtime_inventory
    import context_runtime_tennis
    import context_runtime_semantics
    path = tmp_path / "context.db"
    manifest, atp, wta = seeded(path)
    add_receipt(path)
    before = path.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail("deployment attempted historical model replay")
    monkeypatch.setattr(context_runtime, "_verify_connection", forbidden)
    monkeypatch.setattr(context_runtime_inventory.VerifiedReceiptMapping, "validate_all", forbidden)
    monkeypatch.setattr(context_runtime_semantics, "verify_d2_artifacts", forbidden)
    monkeypatch.setattr(context_runtime_tennis, "verify_live_originals", forbidden)
    report = verify_context_deployment(path)
    assert report["schema"] == 2 and report["verification_level"] == "deployment"
    assert report["checks"] == DEPLOYMENT_CHECKS
    assert report["historical_analysis_verified"] is report["empirical_approval_verified"] is False
    assert report["active_manifest"] == manifest
    assert report["tour_states"] == {"ATP": atp, "WTA": wta}
    assert report["counts"]["observations"] == 1
    assert path.read_bytes() == before
    assert [entry.name for entry in tmp_path.iterdir()] == ["context.db"]


@pytest.mark.parametrize("defect", ["schema", "version", "artifact-hash", "missing-active",
                                  "manifest-hash", "typed-tour", "foreign-key"])
def test_operational_check_still_rejects_broken_storage_and_active_models(tmp_path, defect):
    path = tmp_path / "context.db"
    manifest, atp, wta = seeded(path)
    if defect == "typed-tour":
        publish_slots(path, {"tennis:ATP": wta}, expected_manifest=manifest, published_at=NOW)
    else:
        with closing(sqlite3.connect(path)) as connection:
            if defect == "schema": connection.execute("CREATE TABLE unexpected(value TEXT)")
            elif defect == "version": connection.execute("PRAGMA user_version=1")
            elif defect == "artifact-hash": connection.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b'{}', atp))
            elif defect == "missing-active": connection.execute("DELETE FROM artifacts WHERE digest=?", (atp,))
            elif defect == "manifest-hash": connection.execute("UPDATE manifests SET payload=?", (b'{}',))
            elif defect == "foreign-key": connection.execute("UPDATE active_manifest SET digest=?", ("f" * 64,))
            connection.commit()
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_deployment(path)
    assert path.read_bytes() == before


def test_cli_deployment_is_explicit_and_never_claims_historical_approval(tmp_path, capsys):
    from scripts.verify_context_runtime import main
    path = tmp_path / "context.db"
    seeded(path)
    assert main(["--database", str(path), "--deployment-check"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verification_level"] == "deployment"
    assert report["historical_analysis_verified"] is False
    assert "active_slots" not in report and report["active_slot_count"] == 2
    assert "d2_verified" not in report
    assert main(["--database", str(path)]) == 0
    historical = json.loads(capsys.readouterr().out)
    assert historical["verification_level"] == "structural"
    assert historical["schema"] == 1 and "d2_verified" in historical


@pytest.mark.parametrize("defect", [None, "uncoupled", "missing-report"])
def test_active_approval_references_are_checked_without_granting_activation(tmp_path, defect):
    from tests.test_context_runtime_backup import put_effect_pair
    from context_models.activation import verify_approval
    path = tmp_path / "context.db"
    manifest, _, _ = seeded(path)
    effect, approval, _, approval_payload = put_effect_pair(path)
    slots = {f"context-approval:{effect}": approval}
    if defect != "uncoupled":
        slots["context-effect:tennis"] = effect
    publish_slots(path, slots, expected_manifest=manifest, published_at=NOW)
    if defect == "missing-report":
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("DELETE FROM artifacts WHERE digest=?", (approval_payload["report_hash"],))
            connection.commit()
    if defect is not None:
        with pytest.raises(ArtifactIntegrityError):
            verify_context_deployment(path)
    else:
        assert verify_context_deployment(path)["empirical_approval_verified"] is False
        # An opaque old evaluation remains unapproved by the unchanged owning
        # activation validator even when storage is operationally loadable.
        with closing(sqlite3.connect(path)) as connection, pytest.raises(ValueError):
            verify_approval(connection, approval)


def test_deployment_sealed_mode_uses_streaming_reader_and_distinct_disk_envelope(tmp_path, monkeypatch):
    import context_runtime_input
    import context_runtime_deployment
    calls = []
    path = tmp_path / "context.db"
    seeded(path)
    def sealed(selected, *, max_bytes):
        calls.append((selected, max_bytes))
        return context_runtime_deployment._open_database(selected)
    monkeypatch.setattr(context_runtime_input, "open_sealed_connection", sealed)
    assert verify_context_deployment(path, input_mode="sealed_file")["verification_level"] == "deployment"
    assert calls == [(path, 4 * 1024 ** 3)]
    with pytest.raises(RuntimeArtifactTrustError):
        verify_context_deployment(path, input_mode="unknown")
