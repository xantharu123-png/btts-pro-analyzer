"""Real POINT/D4 unopened-label ownership, never a public approval fixture."""
from contextlib import closing, contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp, digest
from context_models.experiments import freeze_experiment
from context_models.tennis_point_original import POINT_ORIGINAL_KIND
from context_observations import append_observation
from context_runtime import verify_context_database
from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
from context_runtime_tennis import verify_live_originals
from context_runtime_transaction import TrackedConnection
from context_sources.outcomes import normalize_tennis_outcome
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import ArtifactIntegrityError, put_artifact
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_tennis_live import _point_stored
from test_context_tennis_outcome_capture import completed
from test_tennis_live_worker import NOW, competition


def unopened_point_packet(monkeypatch, tmp_path, *, tour="ATP"):
    db, rows = _point_stored(monkeypatch, tmp_path, tour=tour)
    origin = json.loads(rows[0]["context_json"])["context_model"]
    owner_ref = origin["original_artifact_hash"]
    with sqlite3.connect(db) as connection:
        publication = json.loads(connection.execute(
            "SELECT payload FROM artifacts WHERE digest=?", (owner_ref,)).fetchone()[0])
        point_refs = [r for (r,) in connection.execute(
            "SELECT digest FROM artifacts WHERE kind=?", (POINT_ORIGINAL_KIND,))]
    origin = publication["origin"]
    event = origin["event"]
    # A genuinely normalized earlier-schedule label: physically older than
    # the current scheduled receipt, but in the raw ANY-kind LIMIT 2 window.
    earlier = deepcopy(event)
    earlier["scheduled_start"] = canonical_timestamp(NOW-timedelta(hours=2))
    earlier["schedule_revision"] = digest({"event_key": event["event_key"],
        "scheduled_start": earlier["scheduled_start"]})
    final = completed(event_id=event["event_key"].rsplit(":", 1)[-1])
    final["date"] = earlier["scheduled_start"]
    source = {"source_schema": "espn-scoreboard-v1", "tour": tour,
        "tournament_id": "189-2026", "competition": final}
    received = NOW-timedelta(seconds=20)
    label = normalize_tennis_outcome(earlier, source, observed_at=received)
    assert label is not None
    label_ref = append_observation(db, label, observed_at=received)
    # The real historical replay gap, not a fabricated live training case.
    config = json.loads((Path(__file__).parent/
        "fixtures/context/training/tennis-winner-family-v1.json").read_text())
    config["population"].update(competitions=[event["competition"]],
        formats=["singles"], tours=[tour])
    config_ref = digest(config)
    created = NOW-timedelta(seconds=5)
    identity = put_artifact(db, kind="context-native-identity-map-v1", payload={
        "schema": 1, "policy": "native-source-only-v1", "bindings": [{
            "event_key": event["event_key"], "home_id": event["home_id"],
            "away_id": event["away_id"], "source_refs": [origin["native_receipt"]]}]},
        created_at=created)
    dataset = put_artifact(db, kind="context-dataset-v1", payload={"schema": 1,
        "event_identity_hash": identity, "groups": [{"family_config_hash": config_ref,
            "training_cases": [], "final_cases": [], "fit_ref": None,
            "unavailable_final": [{"event_key": event["event_key"],
                "decision_at": origin["cutoff"],
                "reason": "native_to_state_key_source_resolver_unavailable"}]}]},
        created_at=created)
    definition = {"family_config_hash": config_ref, "ablation": "full",
        "target_markets": config["target_markets"], "outcome_contract": config["outcome_contract"]}
    plan = {"schema": 1, "dataset_hash": dataset, "event_identity_hash": identity,
        "code_revision": "a"*40, "base_versions": config["base_versions"],
        "family_configs": [config], "train_end": config["train_end"], "tune_end": config["tune_end"],
        "test_blocks": [[canonical_timestamp(NOW-timedelta(hours=1)+timedelta(days=i)),
            canonical_timestamp(NOW-timedelta(hours=1)+timedelta(days=i+1))] for i in range(3)],
        "target_markets": config["target_markets"],
        "outcome_contracts": [config["outcome_contract"]], "candidate_artifacts": [],
        "policy_version": "context-paired-hac-bh-v1", "availability_classes": ["prospective"],
        "created_at": canonical_timestamp(created), "hypotheses": [{**definition,
            "hypothesis_id": digest(definition), "candidate_artifact": None,
            "pretest_status": "baseline_control"}], "test_inventory": [{"event": {**event, "surface": "Hard", "indoor": False},
                "decision_at": origin["cutoff"], "block": "test:0"}]}
    experiment = freeze_experiment(db, plan, created_at=created)
    return db, origin, owner_ref, point_refs, label_ref, experiment


def observe_real_decoder(monkeypatch, protected, *, reject=True):
    import context_observations
    import context_runtime
    import context_models.tennis_point_original as point
    import context_sources.tennis_outcome_capture as outcomes
    real = context_observations._decode_receipt
    seen = []
    def observed(raw):
        if raw[0] in protected:
            seen.append(raw[0])
            if reject:
                pytest.fail("D4 decoded a genuine unopened POINT final")
        return real(raw)
    for module in (context_observations, context_runtime, point, outcomes):
        monkeypatch.setattr(module, "_decode_receipt", observed)
    return seen


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("reject", [False, True])
def test_full_d4_never_opens_actual_older_protected_label(monkeypatch, tmp_path, tour, reject):
    db, origin, owner, points, label, experiment = unopened_point_packet(monkeypatch, tmp_path, tour=tour)
    assert len(points) == (1 if tour == "ATP" else 0)  # WTA genuinely owns no POINT serve law.
    seen = observe_real_decoder(monkeypatch, {label}, reject=reject)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    report = verify_context_database(db)
    assert report["d2_verified"]["experiments"] == [experiment]
    assert report["d2_verified"]["evaluations"] == []
    assert report["d2_verified"]["approvals"] == []
    assert report["empirical_approval_verified"] is False
    assert "d2-final-source-replay-not-opened" in report["limitations"]
    assert report["counts"]["snapshots"] == 1
    assert seen == []
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


@contextmanager
def real_owners(db, protected):
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as connection:
        connection.execute("BEGIN")
        artifacts = VerifiedArtifactMapping(connection)
        receipts = VerifiedReceiptMapping(connection, protected_receipts=protected)
        _, cache = receipts._validate_all_with_tennis(artifacts)
        clocks = {ref: datetime.fromisoformat(clock) for ref, clock in connection.execute(
            "SELECT digest,created_at FROM artifacts")}
        owners = verify_live_originals(artifacts, clocks, receipts, set(), history_cache=cache)
        yield connection, artifacts, receipts, owners


@pytest.mark.parametrize("change", ["missing", "equal_clock", "current_status", "current_identity", "current_schedule"])
def test_full_d4_native_revisions_still_fail_closed_without_opening_final(monkeypatch, tmp_path, change):
    db, origin, owner, points, label, experiment = unopened_point_packet(monkeypatch, tmp_path)
    native = competition()
    clock = NOW-timedelta(seconds=9)
    if change == "missing":
        # A removed physical owner cannot be waived by the protected final.
        with sqlite3.connect(db) as connection:
            connection.execute("DELETE FROM context_observations WHERE digest=?", (origin["native_receipt"],))
    else:
        if change == "equal_clock":
            clock = NOW-timedelta(seconds=10)
            native["competitors"][1]["id"] = "3"
        elif change == "current_status":
            native["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS", completed=False)
        elif change == "current_identity": native["competitors"][1]["id"] = "3"
        elif change == "current_schedule": native["date"] = canonical_timestamp(NOW+timedelta(hours=6))
        row = normalize_tennis_status("ATP", "189-2026", native,
            grouping_slug="mens-singles", observed_at=clock)[0]
        append_observation(db, row, observed_at=clock)
    seen = observe_real_decoder(monkeypatch, {label})
    before = db.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(db)
    assert seen == [] and db.read_bytes() == before


@pytest.mark.parametrize("change", ["wrong_ref", "fake_dict", "boolean", "callback", "wrong_connection", "ended", "unvalidated",
    "fake_artifacts", "fake_receipts", "fake_cache", "cache_callback", "changed_inventory"])
def test_point_requires_real_same_transaction_winner_owner(monkeypatch, tmp_path, change):
    import context_models.tennis_point_original as point
    db, origin, owner_ref, points, label, _ = unopened_point_packet(monkeypatch, tmp_path)
    seen = observe_real_decoder(monkeypatch, {label})
    with real_owners(db, {label}) as (connection, artifacts, receipts, owners):
        descriptor = owners[owner_ref]
        if change == "wrong_ref": descriptor = replace(descriptor, artifact_ref=origin["state_hash"])
        elif change == "fake_dict": descriptor = {"artifact_ref": owner_ref, "receipts": receipts, "artifacts": artifacts}
        elif change == "boolean": descriptor = True
        elif change == "callback": descriptor = lambda: True
        elif change == "fake_artifacts": descriptor = replace(descriptor, artifacts=dict(artifacts))
        elif change == "fake_receipts": descriptor = replace(descriptor, receipts=dict(receipts))
        elif change == "fake_cache": descriptor = replace(descriptor, history_cache={"complete": True})
        elif change == "cache_callback": descriptor = replace(descriptor, history_cache=lambda: True)
        elif change == "wrong_connection":
            with real_owners(db, {label}) as (_, _, _, other_owners):
                with pytest.raises((ContextIntegrityError, RuntimeArtifactTrustError)):
                    point._read_original(connection, points[0], {}, owning=other_owners[owner_ref])
            assert seen == []
            return
        elif change == "ended":
            connection.rollback()
            connection.execute("BEGIN")
        elif change == "unvalidated":
            descriptor = replace(descriptor, receipts=VerifiedReceiptMapping(connection, protected_receipts={label}), history_cache=None)
        elif change == "changed_inventory":
            connection.execute("UPDATE context_observations SET source=? WHERE digest=?",
                ("changed-after-physical-proof", origin["native_receipt"]))
        with pytest.raises((ContextIntegrityError, RuntimeArtifactTrustError)):
            point._read_original(connection, points[0], {}, owning=descriptor)
    assert seen == []


def test_real_owner_cold_fallback_keeps_final_opaque(monkeypatch, tmp_path):
    import context_models.tennis_point_original as point
    db, origin, owner_ref, points, label, _ = unopened_point_packet(monkeypatch, tmp_path)
    seen = observe_real_decoder(monkeypatch, {label})
    before = db.read_bytes()
    with real_owners(db, {label}) as (connection, _, _, owners):
        # The actual complete receipt owner remains mandatory when the
        # optional encoded native projection is absent or capacity-bypassed.
        descriptor = replace(owners[owner_ref], history_cache=None)
        actual, _, created = point._read_original(connection, points[0], {}, owning=descriptor)
        assert actual == origin
        assert created == "2026-09-09T12:00:01.000000Z"
    assert seen == [] and db.read_bytes() == before


@pytest.mark.parametrize("value", [None, True, {"verified": True}])
def test_d4_owner_key_membership_is_not_native_proof(monkeypatch, tmp_path, value):
    import context_models.tennis_point_original as point
    db, _, owner_ref, _, label, _ = unopened_point_packet(monkeypatch, tmp_path)
    seen = observe_real_decoder(monkeypatch, {label})
    with real_owners(db, {label}) as (connection, artifacts, _, _):
        with pytest.raises(ContextIntegrityError):
            point.verify_point_originals(connection, artifacts, {owner_ref: value})
    assert seen == []


def test_d4_checks_all_orphan_points_and_direct_score_remains_unmasked(monkeypatch, tmp_path):
    import context_models.tennis_point_original as point
    from model_artifacts import load_artifact
    db, origin, owner_ref, points, label, _ = unopened_point_packet(monkeypatch, tmp_path)
    # Direct reads have no D2 owner and retain the existing two-row physical
    # native check. The observing wrapper returns the actual decoder result.
    seen = observe_real_decoder(monkeypatch, {label}, reject=False)
    assert point.read_point_score(db, points[0], as_of=NOW+timedelta(seconds=3)) is None
    assert seen == [label]
    assert point.point_scores_as_of(db, as_of=NOW+timedelta(seconds=3), event_keys={origin["event"]["event_key"]}) == ()
    assert seen == [label, label]
    orphan = deepcopy(load_artifact(db, points[0])["payload"])
    orphan["winner_original_hash"] = "f"*64
    put_artifact(db, kind=POINT_ORIGINAL_KIND, payload=orphan, created_at=NOW+timedelta(seconds=1))
    before = db.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(db)
    assert db.read_bytes() == before
