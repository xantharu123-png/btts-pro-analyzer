"""Temporary D4 storage mechanics, never empirical/model activation evidence."""

from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier, Event
import zipfile

import pytest

from context_observations import append_observation
from context_runtime_transaction import TrackedConnection
from context_snapshots import compute_once, select_context_result, snapshot_key
from context_models.contracts import digest
from model_artifacts import ArtifactIntegrityError, canonical_bytes, load_manifest, put_artifact, publish_slots
from tennis.elo import SurfaceElo
from tennis.model_state import ModelState
from tennis.serve_model import ServeReturnModel
from tennis.state_codec import encode_state


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def tour_payload(tour, *, generation=1):
    elo = SurfaceElo()
    for _ in range(generation):
        elo.update("synthetic a", "synthetic b", "Hard")
    state = ModelState(
        elo, ServeReturnModel(), 1., 0., 1, NOW.timestamp(), "2026-09-08",
        .3 if tour == "ATP" else 0., tour_scope=tour,
        stats_through_kind="tournament_start_proxy" if tour == "ATP" else "result_date",
    )
    return {"schema": 1, "training_cutoff": NOW.isoformat(),
            "state": encode_state(state, tour=tour)}


def put_tour(path, tour, *, generation=1):
    return put_artifact(path, kind="tennis-tour-state",
                        payload=tour_payload(tour, generation=generation), created_at=NOW)


def add_receipt(path, *, revision="r1", observed_at=NOW):
    return append_observation(path, {
        "event_key": "espn:tennis:42", "sport": "tennis", "competition": "atp:us-open",
        "format": "singles_best_of_3", "subject_id": "espn:player:1", "kind": "workload",
        "source": "espn", "source_schema": "synthetic-load-v1", "source_revision": revision,
        "schedule_revision": "s1", "published_at": None, "publication_proof": None,
        "valid_from": NOW.isoformat(), "valid_until": None, "complete": False,
        "payload": {"sets": 3},
    }, observed_at=observed_at)


def stored_rows(path, table):
    # Table is always a literal controlled by these tests, never CLI input.
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)) as con:
        return con.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()


def seeded(path):
    atp, wta = put_tour(path, "ATP"), put_tour(path, "WTA")
    first = publish_slots(path, {"tennis:ATP": atp, "tennis:WTA": wta},
                          expected_manifest=None, published_at=NOW)
    return first, atp, wta


def test_rollback_publishes_new_identity_without_rewinding_newer_facts(tmp_path):
    from model_artifacts import rollback_model_slots

    path = tmp_path / "context_models.db"
    first, old_atp, wta = seeded(path)
    next_atp = put_tour(path, "ATP", generation=2)
    current = publish_slots(path, {"tennis:ATP": next_atp}, expected_manifest=first,
                            published_at=NOW + timedelta(minutes=1))
    add_receipt(path)
    add_receipt(path, revision="r2", observed_at=NOW + timedelta(hours=1))
    payload = {"used_markets": {"winner_a": .6, "winner_b": .4}}
    compute_once(path, "a" * 64, lambda: payload)
    untouched = {table: stored_rows(path, table) for table in
                 ("artifacts", "context_contents", "context_observations", "context_snapshots")}
    previous_manifests = stored_rows(path, "manifests")

    restored = rollback_model_slots(path, first, expected_manifest=current,
                                    published_at=NOW + timedelta(hours=2))

    assert restored not in {first, current}
    assert load_manifest(path) == (restored, {"tennis:ATP": old_atp, "tennis:WTA": wta})
    assert len(stored_rows(path, "manifests")) == len(previous_manifests) + 1
    assert all(row in stored_rows(path, "manifests") for row in previous_manifests)
    assert {table: stored_rows(path, table) for table in untouched} == untouched
    assert compute_once(path, "a" * 64, lambda: pytest.fail("history was recalculated")) == payload


def test_context_verification_is_read_only_and_checks_both_typed_tours(tmp_path):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    first, atp, wta = seeded(path)
    before = path.read_bytes()
    report = verify_context_database(path)
    assert report["active_manifest"] == first
    assert report["active_slots"] == {"tennis:ATP": atp, "tennis:WTA": wta}
    assert report["counts"]["artifacts"] == 2
    assert report["counts"]["manifests"] == 1
    assert report["tour_states"] == {"ATP": atp, "WTA": wta}
    assert report["verification_level"] == "structural"
    assert report["empirical_approval_verified"] is False
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["context_models.db"]


def model_event():
    return {"event_key": "espn:tennis:42", "sport": "tennis", "competition": "atp:us-open",
            "format": "singles_best_of_3", "home_id": "espn:player:1", "away_id": "espn:player:2",
            "scheduled_start": "2026-09-09T18:00:00.000000Z", "schedule_revision": "s1",
            "status": "scheduled", "tour": "ATP", "surface": "Hard", "indoor": False}


def effect_payload(*, generation=1, preprocessing=None):
    return {"schema": 1, "sport": "tennis", "family": "tennis:winner", "feature_version": "synthetic-v1",
            "feature_names": ["load_difference"], "heads": {
                "winner": {"link": "logit", "scale": [1.], "coef": [-.1*generation], "alpha": .1, "n_rows": 2}},
            "preprocessing_artifacts": preprocessing or {}, "joint_calibration": {"kind": "identity"},
            "training_end": "2026-09-01T12:00:00.000000Z", "training_refs_hash": "a"*64,
            "population": {"sport": "tennis", "competitions": ["atp:us-open"], "formats": ["singles_best_of_3"],
                           "tours": ["ATP"], "surfaces": ["Hard"], "indoor": [False]},
            "coverage": {"version": "synthetic-load-v1", "case": "observed-only"}, "model_variant": "synthetic-storage-v1"}


def put_effect_pair(path, *, generation=1):
    effect = effect_payload(generation=generation)
    ref = put_artifact(path, kind="context-effect-v1", payload=effect, created_at=NOW)
    # D1/D2 schemas/resolvers are not implemented. These explicitly opaque
    # artifacts test reference transport only and MUST prevent CLI exit zero.
    report = put_artifact(path, kind="context-evaluation-v1", payload={"synthetic_transport_only": generation}, created_at=NOW)
    experiment = put_artifact(path, kind="context-experiment-v1", payload={"synthetic_transport_only": generation}, created_at=NOW)
    approval = {"schema": 1, "decision": "approved", "hypothesis_id": "1"*64,
                "experiment_hash": experiment, "report_hash": report, "effect_hash": ref,
                "dataset_hash": "2"*64, "event_identity_hash": "3"*64, "code_revision": "4"*40,
                "policy_version": "synthetic-policy-v1", "base_versions": ["synthetic-original-v1"],
                **{name: deepcopy(effect[name]) for name in ("sport", "family", "feature_version", "population", "coverage", "model_variant")},
                "target_markets": ["winner_a", "winner_b"], "outcome_contract": "tennis:winner-v1",
                "test_events_hash": "5"*64, "evaluated_at": "2026-09-09T12:00:00.000000Z"}
    approved = put_artifact(path, kind="context-approval-v1", payload=approval, created_at=NOW)
    return ref, approved, effect, approval


def add_context_snapshot(path, ref, effect, *, snapshot_identity=None):
    receipt = add_receipt(path)
    original = {"version": "synthetic-original-v1", "model_hash": ref,
                "event_key": model_event()["event_key"], "cutoff": "2026-09-09T12:00:00.000000Z",
                "family": "tennis:winner", "params": {"p_a": .6}, "markets": {"winner_a": .6, "winner_b": .4},
                "history_refs": [], "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "synthetic"}}
    features = {"version": "synthetic-v1", "event_key": original["event_key"], "cutoff": original["cutoff"],
                "values": {"load_difference": 3.}, "states": {"load_difference": "available"},
                "refs": {"load_difference": [receipt]}, "coverage": effect["coverage"], "reference_hash": "6"*64}
    key = snapshot_key(model_event(), base_hash=digest(original), context_refs=(receipt,),
                       feature_version=features["version"], feature_hash=digest(features), effect_hash=ref,
                       decision_at=NOW, approval_hash=None)
    comparison = {**original, "version": "synthetic-comparison-v1", "model_hash": "7"*64,
                  "params": {"p_a": .55}, "markets": {"winner_a": .55, "winner_b": .45}}
    result = select_context_result(original, comparison, event=model_event(), features=features,
                                   effect_artifact={"kind": "context-effect-v1", "payload": effect}, effect_hash=ref,
                                   approval=None, factor_roles={"load_difference": "experimental"},
                                   factor_states=features["states"], limitations=[])
    compute_once(path, snapshot_identity or key, lambda: result)
    return snapshot_identity or key, result


def test_real_stage_archive_restore_preserves_tours_receipts_and_b3_bytes(tmp_path):
    from context_runtime import verify_context_database, verify_context_backup_location
    from scripts import stage_runtime_databases as stage, backup_runtime_databases as backup
    from tennis.tour_state import _decode_wrapper

    root = tmp_path / "app"
    path = root / "runtime_state" / "context_models.db"
    first, _, _ = seeded(path)
    effect, approval, payload, _ = put_effect_pair(path)
    current = publish_slots(path, {"arbitrary-effect-slot": effect, f"context-approval:{effect}": approval},
                            expected_manifest=first, published_at=NOW)
    key, result = add_context_snapshot(path, effect, payload)
    add_receipt(path, revision="later-unchanged-facts", observed_at=NOW+timedelta(hours=1))
    before = verify_context_database(path)
    before_rows = {table: stored_rows(path, table) for table in
                   ("artifacts", "manifests", "context_observations", "context_contents", "context_snapshots")}
    assert verify_context_backup_location(path, application_root=root) == "runtime_state/context_models.db"
    expected_predictions = {}
    for tour in ("ATP", "WTA"):
        state = _decode_wrapper(tour_payload(tour), tour)
        expected_predictions[tour] = state.calibrate_match(state.elo.win_probability("synthetic a", "synthetic b", "Hard"),
                                                           "synthetic a", "synthetic b", tour=tour)
    current_stage = tmp_path / "private-stage" / "current"
    current_stage.mkdir(parents=True)
    # Actual uncheckpointed WAL, not an ordinary file copy or in-memory fake.
    with closing(sqlite3.connect(path)) as keeper:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        # Hold a real older read snapshot: an idle connection alone does not
        # establish that the closing B1 writer leaves uncheckpointed frames.
        keeper.execute("BEGIN")
        assert keeper.execute("SELECT count(*) FROM context_observations").fetchone() == (2,)
        main_before = path.read_bytes()
        wal_receipt = add_receipt(path, revision="live-wal", observed_at=NOW+timedelta(hours=2))
        before_rows["context_contents"] = stored_rows(path, "context_contents")
        before_rows["context_observations"] = stored_rows(path, "context_observations")
        assert len(before_rows["context_observations"]) == 3
        assert keeper.execute("SELECT count(*) FROM context_observations").fetchone() == (2,)
        assert Path(str(path) + "-wal").stat().st_size > 0
        assert path.read_bytes() == main_before
        manifest = stage.stage_databases(root, current_stage)
        archive, count = backup.create_archive(tmp_path / "archives", root=current_stage,
                                              logical_root=root, stage_manifest_path=current_stage / "manifest.json", now=NOW)
        assert keeper.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    assert manifest["database_count"] == count == backup.verify_archive(archive) == 1
    assert manifest["databases"][0]["path"] == "runtime_state/context_models.db"
    # Only the one already verified EXPECTED member is restored to a new tree;
    # no extractall(), member-driven destination, overwrite or productive root.
    restored = tmp_path / "restored" / "runtime_state" / "context_models.db"
    # Explicit private restoration, independent of the host's ordinary 0002
    # umask. Do not relax the verifier to accept group-writable test fixtures.
    restored.parent.parent.mkdir(mode=0o700)
    restored.parent.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.namelist() == ["runtime_state/context_models.db"]
        descriptor = os.open(restored, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(zipped.read("runtime_state/context_models.db"))
    after = verify_context_database(restored)
    assert after["active_manifest"] == current
    assert after["verification_level"] == before["verification_level"] == "transport_only"
    assert after["empirical_approval_verified"] is False
    assert "d3-snapshot-input-binding-unavailable" in after["limitations"]
    assert "d2-approval-evidence-resolution-unavailable" in after["limitations"]
    assert {table: stored_rows(restored, table) for table in before_rows} == before_rows
    assert wal_receipt in {row[0] for row in stored_rows(restored, "context_observations")}
    assert compute_once(restored, key, lambda: pytest.fail("restored history recomputed")) == result
    for tour in ("ATP", "WTA"):
        selected = after["tour_states"][tour]
        raw = next(row[2] for row in stored_rows(restored, "artifacts") if row[0] == selected)
        state = _decode_wrapper(json.loads(raw), tour)
        assert state.calibrate_match(state.elo.win_probability("synthetic a", "synthetic b", "Hard"),
                                     "synthetic a", "synthetic b", tour=tour) == expected_predictions[tour]


def test_rollback_removes_new_pointer_slots_without_deleting_artifacts_or_money(tmp_path):
    from model_artifacts import rollback_model_slots
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    first, _, _ = seeded(path)
    old_effect, old_approval, _, _ = put_effect_pair(path)
    target = publish_slots(path, {"effect-slot": old_effect, f"context-approval:{old_effect}": old_approval},
                           expected_manifest=first, published_at=NOW)
    new_effect, new_approval, _, _ = put_effect_pair(path, generation=2)
    # Existing generic publisher merges. Use a distinct new slot so both
    # historical approvals still have their own paired effects at this point.
    current = publish_slots(path, {"new-effect-slot": new_effect, f"context-approval:{new_effect}": new_approval},
                            expected_manifest=target, published_at=NOW+timedelta(minutes=1))
    money = tmp_path / "separate-financial-history.db"
    with closing(sqlite3.connect(money)) as con:
        con.execute("CREATE TABLE preservation_sentinel(value BLOB NOT NULL)")
        con.execute("INSERT INTO preservation_sentinel VALUES (?)", (b"external-financial-history",))
        con.commit()
    money_bytes, old_artifacts = money.read_bytes(), stored_rows(path, "artifacts")
    new = rollback_model_slots(path, target, expected_manifest=current, published_at=NOW+timedelta(hours=1))
    report = verify_context_database(path)
    assert report["active_manifest"] == new
    assert report["active_slots"]["effect-slot"] == old_effect
    assert report["active_slots"][f"context-approval:{old_effect}"] == old_approval
    assert "new-effect-slot" not in report["active_slots"]
    assert f"context-approval:{new_effect}" not in report["active_slots"]
    assert stored_rows(path, "artifacts") == old_artifacts
    assert money.read_bytes() == money_bytes
    audit = json.loads(stored_rows(path, "context_model_rollbacks")[0][1])
    assert audit == {"schema": 1, "expected_manifest": current, "target_manifest": target,
                     "new_manifest": new, "reason": "operator-requested-model-rollback",
                     "published_at": (NOW+timedelta(hours=1)).isoformat()}


@pytest.mark.parametrize("mutation", ["artifact-hash", "artifact-json", "artifact-blob", "artifact-null", "manifest-hash",
    "manifest-predecessor", "manifest-missing-reference", "active-id", "schema-trigger", "schema-view", "schema-version",
    "observation-hash", "observation-content", "observation-index", "observation-orphan", "snapshot-hash", "snapshot-key"])
def test_read_only_verifier_rejects_corruption_without_repair(tmp_path, mutation):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    first, atp, _ = seeded(path)
    add_receipt(path)
    compute_once(path, "a"*64, lambda: {"used_markets": {"winner_a": .6}})
    statements = {
        "artifact-hash": ("UPDATE artifacts SET digest=? WHERE digest=?", ("d"*64, atp)),
        "artifact-json": ("UPDATE artifacts SET payload=? WHERE digest=?", (b'{"bad":1,"bad":1}', atp)),
        "artifact-blob": ("UPDATE artifacts SET payload=CAST(payload AS TEXT) WHERE digest=?", (atp,)),
        "artifact-null": ("UPDATE artifacts SET digest=NULL WHERE digest=?", (atp,)),
        "manifest-hash": ("UPDATE manifests SET published_at=?", ((NOW+timedelta(days=1)).isoformat(),)),
        "manifest-predecessor": ("UPDATE manifests SET predecessor=?", ("e"*64,)),
        "manifest-missing-reference": ("DELETE FROM artifacts WHERE digest=?", (atp,)),
        "active-id": ("UPDATE active_manifest SET id=2", ()),
        "schema-trigger": ("CREATE TRIGGER forbidden AFTER INSERT ON artifacts BEGIN DELETE FROM manifests; END", ()),
        "schema-view": ("CREATE VIEW forbidden AS SELECT * FROM artifacts", ()),
        "schema-version": ("PRAGMA user_version=1", ()),
        "observation-hash": ("UPDATE context_observations SET digest=?", ("f"*64,)),
        "observation-content": ("UPDATE context_contents SET payload=?", (b'{}',)),
        "observation-index": ("UPDATE context_observations SET observed_at=?", (NOW.isoformat(),)),
        "observation-orphan": ("DELETE FROM context_observations", ()),
        "snapshot-hash": ("UPDATE context_snapshots SET payload=?", (b'{}',)),
        "snapshot-key": ("UPDATE context_snapshots SET key=?", ("e"*64,)),
    }
    with closing(sqlite3.connect(path)) as con:
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute(*statements[mutation])
        con.commit()
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["legacy", "wrong-tour", "bool-schema", "float-samples", "future-coverage", "wta-serve", "bad-elo"])
def test_canonically_rehashed_invalid_tour_payload_is_still_rejected(tmp_path, mutation):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    payload = tour_payload("WTA" if mutation == "wta-serve" else "ATP")
    if mutation == "legacy":
        payload["state"]["tour"] = "legacy-combined"
    elif mutation == "wrong-tour":
        payload = tour_payload("WTA")
    elif mutation == "bool-schema":
        payload["schema"] = True
    elif mutation == "float-samples":
        payload["state"]["cal_samples"] = 1.5
    elif mutation == "future-coverage":
        payload["state"]["stats_through"] = "2026-09-10"
    elif mutation == "wta-serve":
        payload["state"]["serve_weight"] = .3
    else:
        payload["state"]["elo"] = {"forged": "unknown"}
    artifact = put_artifact(path, kind="tennis-tour-state", payload=payload, created_at=NOW)
    publish_slots(path, {"tennis:ATP": artifact}, expected_manifest=None, published_at=NOW)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


@pytest.mark.parametrize("mutation", ["slot-hash", "slot-name", "missing-effect-slot", "missing-effect", "missing-report", "missing-experiment",
                                     "wrong-report-kind", "mismatched-scope", "bad-fit", "missing-preprocessing"])
def test_effect_approval_coupling_and_references_are_not_public_hash_only(tmp_path, mutation):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    ref, approved, effect, approval = put_effect_pair(path)
    slots = {"free-effect-slot": ref, f"context-approval:{ref}": approved}
    if mutation in {"missing-effect", "missing-report", "missing-experiment"}:
        # Create manifest first; then simulate a broken persisted reference.
        publish_slots(path, slots, expected_manifest=None, published_at=NOW)
        removed = ref if mutation == "missing-effect" else approval["report_hash" if mutation == "missing-report" else "experiment_hash"]
        with closing(sqlite3.connect(path)) as con:
            con.execute("DELETE FROM artifacts WHERE digest=?", (removed,))
            con.commit()
    else:
        if mutation == "slot-hash":
            slots = {"free-effect-slot": ref, f"context-approval:{'f'*64}": approved}
        elif mutation == "slot-name":
            slots = {"free-effect-slot": ref, "arbitrary-approval": approved}
        elif mutation == "missing-effect-slot":
            slots.pop("free-effect-slot")
        elif mutation in {"wrong-report-kind", "mismatched-scope"}:
            if mutation == "wrong-report-kind":
                approval["report_hash"] = ref
            else:
                approval["population"]["surfaces"] = ["Clay"]
            slots[f"context-approval:{ref}"] = put_artifact(path, kind="context-approval-v1", payload=approval, created_at=NOW)
        else:
            if mutation == "bad-fit":
                effect["heads"]["winner"]["n_rows"] = 2.5
            else:
                effect["preprocessing_artifacts"] = {"workload": "f"*64}
            bad = put_artifact(path, kind="context-effect-v1", payload=effect, created_at=NOW)
            slots = {"free-effect-slot": bad}
        publish_slots(path, slots, expected_manifest=None, published_at=NOW)
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)
    assert path.read_bytes() == before


def test_real_b3_snapshot_with_deleted_numeric_receipt_fails_reference_check(tmp_path):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    ref, _, effect, _ = put_effect_pair(path)
    add_context_snapshot(path, ref, effect)
    with closing(sqlite3.connect(path)) as con:
        con.execute("DELETE FROM context_observations")
        con.execute("DELETE FROM context_contents")
        con.commit()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


def test_opaque_legacy_snapshot_and_unknown_artifact_do_not_claim_complete_verification(tmp_path):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    seeded(path)
    compute_once(path, "a"*64, lambda: {"unbound_inputs": True})
    put_artifact(path, kind="not-a-recognized-schema", payload={"finite": True}, created_at=NOW)
    report = verify_context_database(path)
    assert report["verification_level"] == "transport_only"
    assert report["limitations"] == ["d3-snapshot-input-binding-unavailable", "unrecognized-artifact-schema"]


@pytest.mark.parametrize("clock_error", ["built-after-created", "created-after-published", "manifest-before-predecessor"])
def test_hash_valid_structures_reject_impossible_declared_publication_order(tmp_path, clock_error):
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    if clock_error == "built-after-created":
        artifact = put_artifact(path, kind="tennis-tour-state", payload=tour_payload("ATP"), created_at=NOW-timedelta(seconds=1))
        publish_slots(path, {"tennis:ATP": artifact}, expected_manifest=None, published_at=NOW)
    elif clock_error == "created-after-published":
        artifact = put_tour(path, "ATP")
        publish_slots(path, {"tennis:ATP": artifact}, expected_manifest=None, published_at=NOW-timedelta(seconds=1))
    else:
        artifact = put_tour(path, "ATP")
        first = publish_slots(path, {"tennis:ATP": artifact}, expected_manifest=None, published_at=NOW+timedelta(seconds=1))
        publish_slots(path, {}, expected_manifest=first, published_at=NOW)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


def test_rollback_cas_and_failure_after_audit_insert_are_atomic(tmp_path, monkeypatch):
    from model_artifacts import ManifestConflict, rollback_model_slots
    import context_runtime

    path = tmp_path / "context_models.db"
    first, _, _ = seeded(path)
    second = publish_slots(path, {"tennis:ATP": put_tour(path, "ATP", generation=2)}, expected_manifest=first, published_at=NOW)
    before = path.read_bytes()
    with pytest.raises(ManifestConflict):
        rollback_model_slots(path, first, expected_manifest=first, published_at=NOW)
    assert path.read_bytes() == before
    original_connect = sqlite3.connect
    events = []
    class FailingConnection(TrackedConnection):
        def execute(self, sql, parameters=()):
            if sql.startswith("INSERT INTO context_model_rollbacks"):
                events.append("audit-inserted")
            if sql.startswith("UPDATE active_manifest"):
                raise sqlite3.OperationalError("injected after audit insert")
            return super().execute(sql, parameters)
    def failing_connect(*args, **kwargs):
        kwargs["factory"] = FailingConnection
        return original_connect(*args, **kwargs)
    monkeypatch.setattr(context_runtime.sqlite3, "connect", failing_connect)
    with pytest.raises(sqlite3.OperationalError):
        rollback_model_slots(path, first, expected_manifest=second, published_at=NOW)
    assert events == ["audit-inserted"]
    assert path.read_bytes() == before
    monkeypatch.undo()
    assert load_manifest(path)[0] == second
    with closing(sqlite3.connect(path)) as con:
        assert con.execute("SELECT name FROM sqlite_master WHERE name='context_model_rollbacks'").fetchone() is None


def test_two_rollback_publishers_share_one_cas_winner_and_one_audit(tmp_path):
    from model_artifacts import ManifestConflict, rollback_model_slots
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    first, _, _ = seeded(path)
    second = publish_slots(path, {"tennis:ATP": put_tour(path, "ATP", generation=2)}, expected_manifest=first, published_at=NOW)
    barrier = Barrier(2)
    def worker(_):
        barrier.wait(timeout=5)
        try:
            return rollback_model_slots(path, first, expected_manifest=second, published_at=NOW+timedelta(seconds=1))
        except ManifestConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert results.count("conflict") == 1
    assert verify_context_database(path)["counts"]["rollbacks"] == 1


@pytest.mark.parametrize("target", ["self", "missing", "future-time"])
def test_rollback_requires_real_earlier_history_and_current_publication_clock(tmp_path, target):
    from model_artifacts import rollback_model_slots

    path = tmp_path / "context_models.db"
    first, _, _ = seeded(path)
    second = publish_slots(path, {"tennis:ATP": put_tour(path, "ATP", generation=2)}, expected_manifest=first, published_at=NOW)
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        rollback_model_slots(path, second if target == "self" else "f"*64 if target == "missing" else first,
                             expected_manifest=second, published_at=NOW-timedelta(seconds=1) if target == "future-time" else NOW)
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["digest", "reason", "target", "expected", "new", "time", "schema"])
def test_rollback_audit_closed_schema_and_manifest_links_are_checked(tmp_path, mutation):
    from model_artifacts import rollback_model_slots
    from context_runtime import verify_context_database

    path = tmp_path / "context_models.db"
    first, _, _ = seeded(path)
    second = publish_slots(path, {"tennis:ATP": put_tour(path, "ATP", generation=2)}, expected_manifest=first, published_at=NOW)
    rollback_model_slots(path, first, expected_manifest=second, published_at=NOW+timedelta(seconds=1))
    key, raw = stored_rows(path, "context_model_rollbacks")[0]
    row = json.loads(raw)
    if mutation == "reason": row["reason"] = "forged"
    if mutation == "target": row["target_manifest"] = second
    if mutation == "expected": row["expected_manifest"] = first
    if mutation == "new": row["new_manifest"] = first
    if mutation == "time": row["published_at"] = NOW.isoformat()
    if mutation == "schema": row["schema"] = True
    with closing(sqlite3.connect(path)) as con:
        con.execute("UPDATE context_model_rollbacks SET digest=?,payload=?", ("e"*64 if mutation == "digest" else digest(row), canonical_bytes(row)))
        con.commit()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


def test_online_wal_snapshot_contains_one_complete_manifest_transaction(tmp_path):
    from context_runtime import verify_context_database
    from scripts.stage_runtime_databases import stage_databases

    root = tmp_path / "app"
    path = root / "runtime_state" / "context_models.db"
    first, _, _ = seeded(path)
    staged = tmp_path / "stage"
    staged.mkdir()
    ready, release = Event(), Event()
    errors = []
    new_payload = tour_payload("ATP", generation=2)
    ref = digest({"kind": "tennis-tour-state", "payload": new_payload})
    old_slots = load_manifest(path)[1]
    slots = {**old_slots, "tennis:ATP": ref}
    manifest_payload = {"predecessor": first, "slots": slots, "published_at": NOW.isoformat()}
    new = digest(manifest_payload)
    def writer():
        try:
            with closing(sqlite3.connect(path)) as con:
                con.execute("BEGIN IMMEDIATE")
                con.execute("INSERT INTO artifacts VALUES (?,?,?,?)", (ref, "tennis-tour-state", canonical_bytes(new_payload), NOW.isoformat()))
                con.execute("INSERT INTO manifests VALUES (?,?,?,?)", (new, first, canonical_bytes(slots), NOW.isoformat()))
                con.execute("UPDATE active_manifest SET digest=?", (new,))
                ready.set()
                assert release.wait(10)
                con.commit()
        except BaseException as exc:
            errors.append(exc)
            ready.set()
    with closing(sqlite3.connect(path)) as keeper:
        keeper.execute("PRAGMA journal_mode=WAL")
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(writer)
            assert ready.wait(5)
            # Pending writer has all three changes uncommitted. Reader backup
            # must see the complete preceding state, not the inserted artifact.
            try:
                stage_databases(root, staged)
                before = verify_context_database(staged / "runtime_state" / "context_models.db")
                assert before["active_manifest"] == first
                assert before["counts"]["artifacts"] == 2
            finally:
                release.set()
            pending.result(timeout=5)
        assert not errors
        after_stage = tmp_path / "stage-after"
        after_stage.mkdir()
        stage_databases(root, after_stage)
        after = verify_context_database(after_stage / "runtime_state" / "context_models.db")
        assert after["active_manifest"] == new
        assert after["counts"]["artifacts"] == 3
        assert after["active_slots"]["tennis:ATP"] == ref


def cli(path, *extra):
    return subprocess.run([sys.executable, "-B", "scripts/verify_context_runtime.py", "--database", str(path), *map(str, extra)],
                          capture_output=True, text=True, timeout=30)


def test_cli_exit_levels_and_error_output_are_truthful_and_secret_free(tmp_path):
    path = tmp_path / "context_models.db"
    seeded(path)
    answer = cli(path, "--backup-root", tmp_path)
    assert answer.returncode == 0, answer.stderr
    assert json.loads(answer.stdout)["empirical_approval_verified"] is False
    compute_once(path, "a"*64, lambda: {"unbound": True})
    answer = cli(path)
    assert answer.returncode == 2
    assert json.loads(answer.stdout)["verification_level"] == "transport_only"
    with closing(sqlite3.connect(path)) as con:
        con.execute("UPDATE artifacts SET payload=?", (b'{"secret":"do-not-print"}',))
        con.commit()
    answer = cli(path)
    assert answer.returncode == 1
    assert "do-not-print" not in answer.stdout + answer.stderr
    assert json.loads(answer.stdout)["status"] == "failed"


def test_cli_does_not_echo_arbitrary_slot_names_as_diagnostics(tmp_path):
    path = tmp_path / "context_models.db"
    first, atp, _ = seeded(path)
    publish_slots(path, {"do-not-print-credential": atp}, expected_manifest=first, published_at=NOW)
    answer = cli(path)
    assert answer.returncode == 0
    assert "do-not-print-credential" not in answer.stdout + answer.stderr


def test_missing_path_and_configured_path_outside_backup_are_not_created_or_promoted(tmp_path):
    from context_runtime import verify_context_database, verify_context_backup_location
    from runtime_paths import RuntimeArtifactTrustError

    missing = tmp_path / "absent" / "context_models.db"
    with pytest.raises(FileNotFoundError):
        verify_context_database(missing)
    assert cli(missing).returncode == 1
    assert not missing.parent.exists()
    path = tmp_path / "outside" / "context_models.db"
    seeded(path)
    application = tmp_path / "app"
    application.mkdir()
    with pytest.raises(RuntimeArtifactTrustError, match="outside"):
        verify_context_backup_location(path, application_root=application)
    assert cli(path, "--backup-root", application).returncode == 1
    assert not list(application.iterdir())


def test_read_only_verifier_does_not_ignore_live_wal_or_create_companions(tmp_path):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "context_models.db"
    seeded(path)
    with closing(sqlite3.connect(path)) as con:
        con.execute("PRAGMA journal_mode=WAL")
        add_receipt(path)
        before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
        with pytest.raises(RuntimeArtifactTrustError, match="sealed stage"):
            verify_context_database(path)
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


@pytest.mark.parametrize("parent", [False, True])
def test_real_symlink_path_is_rejected_when_platform_allows_it(tmp_path, parent):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    actual = tmp_path / "actual" / "context_models.db"
    seeded(actual)
    link = tmp_path / "linked" if parent else tmp_path / "linked.db"
    try:
        link.symlink_to(actual.parent if parent else actual, target_is_directory=parent)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"actual symlink creation unavailable: {exc}")
    with pytest.raises(RuntimeArtifactTrustError):
        verify_context_database(link / actual.name if parent else link)


def test_hardlink_database_and_non_database_path_are_rejected(tmp_path):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    actual = tmp_path / "context_models.db"
    seeded(actual)
    with pytest.raises(RuntimeArtifactTrustError):
        verify_context_database(tmp_path)
    linked = tmp_path / "linked.db"
    os.link(actual, linked)
    with pytest.raises(RuntimeArtifactTrustError):
        verify_context_database(linked)


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner/mode enforcement; Windows uses ACLs")
def test_world_writable_database_rejected_without_modification(tmp_path):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    actual = tmp_path / "context_models.db"
    seeded(actual)
    actual.chmod(0o666)
    before = actual.read_bytes()
    with pytest.raises(RuntimeArtifactTrustError):
        verify_context_database(actual)
    assert actual.read_bytes() == before


def foreign_football_effect():
    effect = effect_payload()
    fit = {**effect["heads"]["winner"], "link": "log_rate"}
    return {**effect, "sport": "football", "family": "football:goals:90min",
            "heads": {side: deepcopy(fit) for side in ("home", "away")},
            "population": {"sport": "football", "competitions": ["39"], "formats": ["90min"],
                           "tours": [None], "surfaces": [None], "indoor": [None]}}


@pytest.mark.parametrize("operation", ["verify", "rollback"])
def test_unconsumed_cross_family_b3_fallback_preserves_history(tmp_path, operation):
    from context_runtime import verify_context_database
    from model_artifacts import rollback_model_slots

    path = tmp_path / "models.db"
    first, _, _ = seeded(path)
    next_atp = put_tour(path, "ATP", generation=2)
    current = publish_slots(path, {"tennis:ATP": next_atp}, expected_manifest=first, published_at=NOW)
    foreign = foreign_football_effect()
    ref = put_artifact(path, kind="context-effect-v1", payload=foreign, created_at=NOW)
    key, result = add_context_snapshot(path, ref, foreign)
    assert result["role"] == "not_applied"
    assert result["comparison_params"] is result["comparison_markets"] is None
    assert "context-effect-scope-mismatch" in result["limitations"]
    before = path.read_bytes()
    rows = {table: stored_rows(path, table) for table in
            ("artifacts", "context_observations", "context_contents", "context_snapshots")}
    if operation == "verify":
        report = verify_context_database(path)
        assert report["verification_level"] == "transport_only"
        assert path.read_bytes() == before
    else:
        rollback_model_slots(path, first, expected_manifest=current, published_at=NOW)
    assert compute_once(path, key, lambda: pytest.fail("valid baseline was recalculated")) == result
    assert {table: stored_rows(path, table) for table in rows} == rows


def test_readonly_verifier_opens_only_query_only_in_memory_sqlite(tmp_path, monkeypatch):
    from context_runtime import verify_context_database

    path = tmp_path / "models.db"
    seeded(path)
    before = path.read_bytes()
    real_connect = sqlite3.connect
    calls, images = [], []

    class MemoryOnly(TrackedConnection):
        def deserialize(self, data, *, name="main"):
            images.append(bytes(data))
            return super().deserialize(data, name=name)

        def execute(self, sql, *args):
            if sql == "BEGIN":
                for setting, expected in (("query_only", 1), ("trusted_schema", 0), ("temp_store", 2)):
                    assert super().execute("PRAGMA " + setting).fetchone() == (expected,)
                with pytest.raises(sqlite3.OperationalError, match="readonly"):
                    super().execute("CREATE TABLE forbidden_write(value)")
            return super().execute(sql, *args)

    def memory_only(database, *args, **kwargs):
        calls.append(database)
        assert database == ":memory:", "readonly SQLite must never see the mutable source path"
        kwargs["factory"] = MemoryOnly
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", memory_only)
    assert verify_context_database(path)["verification_level"] == "structural"
    assert calls == [":memory:"] and images == [before]
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["models.db"]


@pytest.mark.parametrize("boundary", ["descriptor_read", "before_deserialize"])
def test_sealed_image_rejects_real_wal_transition_without_touching_source(tmp_path, monkeypatch, boundary):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    real_connect, real_read = sqlite3.connect, os.read
    identity = path.stat().st_dev, path.stat().st_ino
    keeper, captured, calls = None, [], []

    def transition():
        nonlocal keeper
        if keeper is not None:
            return
        keeper = real_connect(path)
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("UPDATE artifacts SET created_at=?", ((NOW-timedelta(hours=1)).isoformat(),))
        keeper.commit()
        assert Path(str(path)+"-wal").stat().st_size > 0
        captured.append({suffix: Path(str(path)+suffix).read_bytes() for suffix in ("", "-wal", "-shm")})
        assert captured[0][""][18:20] == bytes([2, 2])

    def read_with_real_writer(fd, amount):
        info = os.fstat(fd)
        if boundary == "descriptor_read" and (info.st_dev, info.st_ino) == identity:
            transition()
        return real_read(fd, amount)

    class InterleavingMemory(TrackedConnection):
        def deserialize(self, data, *, name="main"):
            if boundary == "before_deserialize":
                transition()
            return super().deserialize(data, name=name)

    def memory_only(database, *args, **kwargs):
        calls.append(database)
        assert database == ":memory:", "readonly verification must not open the source in SQLite"
        kwargs["factory"] = InterleavingMemory
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(os, "read", read_with_real_writer)
    monkeypatch.setattr(sqlite3, "connect", memory_only)
    try:
        with pytest.raises(RuntimeArtifactTrustError):
            verify_context_database(path)
        assert len(captured) == 1, "the actual independent writer must run"
        assert {suffix: Path(str(path)+suffix).read_bytes() for suffix in captured[0]} == captured[0]
        assert not set(calls) - {":memory:"}
    finally:
        if keeper is not None:
            keeper.close()


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_sealed_image_rejects_even_empty_companions(tmp_path, suffix):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    companion = Path(str(path)+suffix)
    companion.write_bytes(b"")
    companion.chmod(0o600)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(RuntimeArtifactTrustError, match="sealed stage"):
        verify_context_database(path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_sealed_image_has_a_hard_input_size_limit_before_sqlite_open(tmp_path, monkeypatch):
    import context_runtime
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    assert context_runtime.MAX_CONTEXT_IMAGE_BYTES == 64 * 1024 * 1024
    image_bytes = path.stat().st_size
    monkeypatch.setattr(context_runtime, "MAX_CONTEXT_IMAGE_BYTES", image_bytes)
    assert context_runtime.verify_context_database(path)["verification_level"] == "structural"
    monkeypatch.setattr(context_runtime, "MAX_CONTEXT_IMAGE_BYTES", image_bytes-1)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: pytest.fail("oversize image reached SQLite"))
    with pytest.raises(RuntimeArtifactTrustError, match="image size"):
        context_runtime.verify_context_database(path)


@pytest.mark.parametrize("capability", ["missing", "not_supported"])
def test_missing_deserializer_fails_closed_without_a_file_fallback(tmp_path, monkeypatch, capability):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    before = path.read_bytes()
    real_connect, calls = sqlite3.connect, []

    class NoDeserialize(TrackedConnection):
        if capability == "missing":
            deserialize = None
        else:
            def deserialize(self, *args, **kwargs):
                raise sqlite3.NotSupportedError("test-only unsupported deserialize")

    def memory_only(database, *args, **kwargs):
        calls.append(database)
        assert database == ":memory:"
        kwargs["factory"] = NoDeserialize
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", memory_only)
    with pytest.raises(RuntimeArtifactTrustError, match="deserialize"):
        verify_context_database(path)
    assert calls == [":memory:"] and path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["experimental", "applied", "comparison", "factor-role", "approval",
                                     "certified-market", "changed-used", "missing-effect"])
def test_foreign_effect_exception_never_permits_false_consumption(tmp_path, mutation):
    from context_runtime import verify_context_database

    path = tmp_path / "models.db"
    seeded(path)
    foreign = foreign_football_effect()
    ref = put_artifact(path, kind="context-effect-v1", payload=foreign, created_at=NOW)
    _, original = add_context_snapshot(path, ref, foreign)
    altered = deepcopy(original)
    if mutation in ("experimental", "applied"):
        altered["role"] = mutation
    elif mutation == "comparison":
        altered["comparison_params"], altered["comparison_markets"] = altered["base_params"], altered["base_markets"]
    elif mutation == "factor-role":
        altered["factor_roles"]["load_difference"] = "experimental"
    elif mutation == "approval":
        altered["approval_hash"] = "e"*64
    elif mutation == "certified-market":
        altered["certified_markets"] = ["winner_a"]
    elif mutation == "changed-used":
        altered["used_params"] = {"p_a": .7}
        altered["used_markets"] = {"winner_a": .7, "winner_b": .3}
    else:
        altered["effect_hash"] = "e"*64
    compute_once(path, "f"*64, lambda: altered)
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("boundary", ["after_image", "before_return"])
def test_same_file_delete_commit_cannot_overtake_image_capture(tmp_path, monkeypatch, boundary):
    import context_runtime
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    real_connect, real_verify = sqlite3.connect, context_runtime._verify_connection
    captured = []

    def commit_actual_change():
        with closing(real_connect(path)) as writer:
            assert writer.execute("PRAGMA journal_mode").fetchone() == ("delete",)
            writer.execute("UPDATE artifacts SET created_at=?", ((NOW-timedelta(hours=1)).isoformat(),))
            writer.commit()
        captured.append(path.read_bytes())

    class ChangeAfterImage(TrackedConnection):
        def deserialize(self, data, *, name="main"):
            if boundary == "after_image":
                commit_actual_change()
            return super().deserialize(data, name=name)

    def memory_only(database, *args, **kwargs):
        assert database == ":memory:"
        kwargs["factory"] = ChangeAfterImage
        return real_connect(database, *args, **kwargs)

    def change_before_return(connection):
        result = real_verify(connection)
        if boundary == "before_return":
            commit_actual_change()
        return result

    monkeypatch.setattr(sqlite3, "connect", memory_only)
    monkeypatch.setattr(context_runtime, "_verify_connection", change_before_return)
    with pytest.raises(RuntimeArtifactTrustError):
        context_runtime.verify_context_database(path)
    assert len(captured) == 1 and path.read_bytes() == captured[0]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["models.db"]


@pytest.mark.parametrize("mutation", ["mtime", "size", "hardlink", "new-journal"])
def test_source_fingerprint_and_companions_rechecked_before_return(tmp_path, monkeypatch, mutation):
    import context_runtime
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    original = context_runtime._verify_connection
    captured = []

    def mutate_after_verification(connection):
        result = original(connection)
        if mutation == "mtime":
            info = path.stat()
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns+1000000000))
        elif mutation == "size":
            with path.open("ab") as handle:
                handle.write(b"x")
        elif mutation == "hardlink":
            os.link(path, tmp_path / "external-link.db")
        else:
            Path(str(path)+"-journal").write_bytes(b"")
        captured.append({p.name: p.read_bytes() for p in tmp_path.iterdir()})
        return result

    monkeypatch.setattr(context_runtime, "_verify_connection", mutate_after_verification)
    with pytest.raises(RuntimeArtifactTrustError):
        context_runtime.verify_context_database(path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == captured[0]


@pytest.mark.parametrize("corruption", ["signature", "truncated", "page-size", "header-mode"])
def test_sealed_image_rejects_bad_header_without_invoking_sqlite(tmp_path, monkeypatch, corruption):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    data = bytearray(path.read_bytes())
    if corruption == "signature":
        data[0] = 0
    elif corruption == "truncated":
        data = data[:20]
    elif corruption == "page-size":
        data[16:18] = bytes([0, 3])
    else:
        data[18:20] = bytes([2, 2])
    path.write_bytes(data)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: pytest.fail("invalid header reached SQLite"))
    with pytest.raises((ArtifactIntegrityError, RuntimeArtifactTrustError)):
        verify_context_database(path)
    assert path.read_bytes() == data


@pytest.mark.parametrize("failure", [sqlite3.DatabaseError, MemoryError])
def test_in_memory_setup_failures_are_typed_and_close_the_connection(tmp_path, monkeypatch, failure):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    path = tmp_path / "models.db"
    seeded(path)
    before = path.read_bytes()
    real_connect, connections = sqlite3.connect, []

    class FailingMemory(TrackedConnection):
        def deserialize(self, data, *, name="main"):
            raise failure("test-only memory engine setup failure")

    def memory_only(database, *args, **kwargs):
        assert database == ":memory:"
        kwargs["factory"] = FailingMemory
        connection = real_connect(database, *args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", memory_only)
    with pytest.raises((ArtifactIntegrityError, RuntimeArtifactTrustError)):
        verify_context_database(path)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    assert path.read_bytes() == before


def test_actual_read_descriptor_for_another_file_is_rejected(tmp_path, monkeypatch):
    from context_runtime import verify_context_database
    from runtime_paths import RuntimeArtifactTrustError

    requested, other = tmp_path / "requested.db", tmp_path / "other.db"
    seeded(requested)
    seeded(other)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    real_open = os.open

    def wrong_descriptor(path, flags, *args, **kwargs):
        return real_open(other if Path(path) == requested else path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", wrong_descriptor)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: pytest.fail("wrong file reached SQLite"))
    with pytest.raises(RuntimeArtifactTrustError, match="identity"):
        verify_context_database(requested)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
