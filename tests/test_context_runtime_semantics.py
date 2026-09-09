"""Actual local A1/B1/D1/D2 replay, synthetic sport inputs, no activation claim."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta
import math
import os
from pathlib import Path
import sqlite3
import json
import zipfile

import pytest

from context_dataset_helpers import EVALUATED, copy_packet, stored_packet
from context_models.contracts import digest
from context_models.evaluator import evaluate_experiment
from context_runtime import verify_context_database
from model_artifacts import ArtifactIntegrityError, canonical_bytes, put_artifact


@pytest.fixture(scope="module")
def packets(tmp_path_factory):
    unopened = stored_packet(tmp_path_factory.mktemp("d4-d2-unopened"))
    opened = copy_packet(unopened, tmp_path_factory.mktemp("d4-d2-evaluated"))
    report = evaluate_experiment(opened["path"], opened["experiment_ref"], evaluated_at=EVALUATED)
    assert report["approvals"] == []  # Three synthetic finals are NOT 200 real events.
    opened["evaluation"] = report
    return unopened, opened


def sealed_copy(packet, tmp_path):
    result = copy_packet(packet, tmp_path)
    with closing(sqlite3.connect(result["path"])) as connection:
        assert connection.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",)
    os.chmod(result["path"], 0o600)
    return result


def add_artifact(packet, kind, payload):
    return put_artifact(packet["path"], kind=kind, payload=payload, created_at=EVALUATED)


def test_actual_stored_evaluation_replays_without_writing_or_approving(packets, tmp_path, monkeypatch):
    packet = sealed_copy(packets[1], tmp_path)
    before = packet["path"].read_bytes()
    original = sqlite3.connect
    paths = []
    def memory_only(path, *args, **kwargs):
        paths.append(path)
        assert path == ":memory:"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", memory_only)
    result = verify_context_database(packet["path"])
    assert result["verification_level"] == "structural"
    assert result["d2_verified"]["evaluations"] == [packet["evaluation"]["digest"]]
    assert result["d2_verified"]["approvals"] == []
    assert result["empirical_approval_verified"] is False
    assert paths == [":memory:"]
    assert packet["path"].read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["copy.db"]


def test_unopened_final_labels_remain_unread_and_report_incomplete(packets, tmp_path, monkeypatch):
    import context_observations
    import context_runtime
    packet = sealed_copy(packets[0], tmp_path)
    finals = {item["event"]["event_key"] for item in packet["plan"]["test_inventory"]}
    original = context_observations._decode_receipt
    seen = []
    def guarded(row):
        # Actual B1 SELECT: receipt/content/event/clock/revision/source/subject/kind/BLOB.
        if row[2] in finals and row[7] == "match_outcome":
            pytest.fail("unopened final outcome body was decoded")
        seen.append(row[0])
        return original(row)
    monkeypatch.setattr(context_observations, "_decode_receipt", guarded)
    monkeypatch.setattr(context_runtime, "_decode_receipt", guarded)
    before = packet["path"].read_bytes()
    result = verify_context_database(packet["path"])
    assert result["verification_level"] == "transport_only"
    assert "d2-final-source-replay-not-opened" in result["limitations"]
    assert result["d2_verified"]["evaluations"] == []
    assert result["counts"]["observations"] > len(finals)
    assert seen
    assert packet["path"].read_bytes() == before


@pytest.mark.parametrize("change", ["drop_hypothesis", "probability", "clock"])
def test_inactive_rehashed_evaluation_is_not_trusted(packets, tmp_path, change):
    packet = sealed_copy(packets[1], tmp_path)
    payload = deepcopy(packet["evaluation"]["payload"])
    hid = packet["hypothesis_id"]
    if change == "drop_hypothesis":
        payload["results"].pop(hid)
        payload["statistics"]["hypotheses"].pop(hid)
        payload["statistics"]["q_values"].pop(hid)
    elif change == "probability":
        row = payload["results"][hid][0]
        row["p_context"] = math.nextafter(row["p_context"], 1.)
    else:
        payload["evaluated_at"] = "2026-09-08T00:00:00.000000Z"
    changed = add_artifact(packet, "context-evaluation-v1", payload)
    assert changed != packet["evaluation"]["digest"]
    before = packet["path"].read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])
    assert packet["path"].read_bytes() == before


def test_missing_opening_fails_before_owning_final_decode(packets, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    packet = sealed_copy(packets[1], tmp_path)
    opening = packet["evaluation"]["payload"]["opening_hash"]
    with closing(sqlite3.connect(packet["path"])) as connection:
        connection.execute("DELETE FROM artifacts WHERE digest=?", (opening,))
        connection.commit()
    final_refs = {case["case"]["payload"]["outcome_ref"] for case in packet["cases"][4:]}
    original = dataset._receipt
    def guarded(connection, ref):
        assert ref not in final_refs, "final body was inspected before its original opening"
        return original(connection, ref)
    monkeypatch.setattr(dataset, "_receipt", guarded)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])


def test_unused_fit_candidate_score_is_recomputed(packets, tmp_path):
    packet = sealed_copy(packets[1], tmp_path)
    forged = deepcopy(packet["fit"])
    unused = next(row for row in forged["alpha_scores"]
                  if row["status"] == "scored" and row["effect_hash"] != forged["effect_hash"])
    unused["mean_brier"] = math.nextafter(unused["mean_brier"], 1.)
    add_artifact(packet, "context-fit-v1", forged)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])


@pytest.mark.parametrize("change", ["event_key", "kind", "clock", "content-hash", "blob-type"])
def test_unopened_protection_cannot_hide_physical_index_or_byte_corruption(packets, tmp_path, change, monkeypatch):
    import context_runtime
    packet = sealed_copy(packets[0], tmp_path)
    receipt = packet["cases"][4]["case"]["payload"]["outcome_ref"]
    with closing(sqlite3.connect(packet["path"])) as connection:
        content = connection.execute("SELECT content_digest FROM context_observations WHERE digest=?", (receipt,)).fetchone()[0]
        if change == "event_key":
            connection.execute("UPDATE context_observations SET event_key='unfrozen-event' WHERE digest=?", (receipt,))
        elif change == "kind":
            connection.execute("UPDATE context_observations SET kind='base_fixture' WHERE digest=?", (receipt,))
        elif change == "clock":
            connection.execute("UPDATE context_observations SET observed_at='2026-09-01' WHERE digest=?", (receipt,))
        elif change == "blob-type":
            connection.execute("UPDATE context_contents SET payload=CAST(payload AS TEXT) WHERE content_digest=?", (content,))
        else:
            connection.execute("UPDATE context_contents SET payload=? WHERE content_digest=?", (b"{}", content))
        connection.commit()
    def forbidden(*args):
        pytest.fail("physical preflight failure must precede generic body decoding")
    monkeypatch.setattr(context_runtime, "_decode_receipt", forbidden)
    before = packet["path"].read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])
    assert packet["path"].read_bytes() == before


def test_three_event_report_cannot_gain_inactive_approval(packets, tmp_path, monkeypatch):
    import context_models.activation as activation
    packet = sealed_copy(packets[1], tmp_path)
    report = packet["evaluation"]
    config = packet["plan"]["family_configs"][0]
    metrics = report["payload"]["statistics"]["hypotheses"][packet["hypothesis_id"]]["metrics"]
    fake = {"schema": 1, "decision": "approved", "hypothesis_id": packet["hypothesis_id"],
        "experiment_hash": packet["experiment_ref"], "report_hash": report["digest"],
        "effect_hash": packet["fit"]["effect_hash"], "dataset_hash": packet["plan"]["dataset_hash"],
        "event_identity_hash": packet["plan"]["event_identity_hash"],
        "code_revision": packet["plan"]["code_revision"], "policy_version": packet["plan"]["policy_version"],
        **{key: config[key] for key in ("base_versions", "sport", "family", "feature_version", "population",
            "coverage", "model_variant", "target_markets", "outcome_contract")},
        "test_events_hash": digest(metrics["event_inventory"]), "evaluated_at": report["payload"]["evaluated_at"]}
    ref = add_artifact(packet, "context-approval-v1", fake)
    original = activation.verify_approval
    calls = []
    def actual_owner(connection, approval_hash):
        calls.append(approval_hash)
        assert connection.in_transaction
        assert connection.execute("PRAGMA query_only").fetchone() == (1,)
        databases = connection.execute("PRAGMA database_list").fetchall()
        assert (0, "main", "") in databases
        assert all(name in {"main", "temp"} and filename == "" for _, name, filename in databases)
        assert connection.execute("PRAGMA temp_store").fetchone() == (2,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM artifacts")
        return original(connection, approval_hash)
    monkeypatch.setattr(activation, "verify_approval", actual_owner)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])
    assert calls == [ref]


def test_legitimately_opened_final_bodies_receive_owning_validation(packets, tmp_path, monkeypatch):
    import context_sources.outcomes as outcomes
    packet = sealed_copy(packets[1], tmp_path)
    final_refs = {case["case"]["payload"]["outcome_ref"] for case in packet["cases"][4:]}
    original = outcomes.validate_outcome_record
    seen = set()
    def checked(row, *, event):
        seen.add(row["digest"])
        return original(row, event=event)
    monkeypatch.setattr(outcomes, "validate_outcome_record", checked)
    result = verify_context_database(packet["path"])
    assert final_refs <= seen
    assert result["d2_verified"]["evaluations"] == [packet["evaluation"]["digest"]]


@pytest.mark.parametrize("change", ["subset", "clock", "wrong-experiment"])
def test_wrong_opening_never_authorizes_generic_or_owning_final_decode(packets, tmp_path, change, monkeypatch):
    import context_runtime
    import context_models.dataset as dataset
    packet = sealed_copy(packets[1], tmp_path)
    with closing(sqlite3.connect(packet["path"])) as connection:
        opening = json.loads(connection.execute("SELECT payload FROM artifacts WHERE kind='context-test-opening-v1'").fetchone()[0])
        connection.execute("DELETE FROM artifacts WHERE kind='context-test-opening-v1'")
        connection.commit()
    if change == "subset":
        opening["event_keys"] = opening["event_keys"][:-1]
    elif change == "clock":
        opening["opened_at"] = packet["plan"]["created_at"]
    else:
        opening["experiment_hash"] = "e" * 64
    add_artifact(packet, "context-test-opening-v1", opening)
    def forbidden(*args, **kwargs):
        pytest.fail("incorrect opening reached any body decoder")
    monkeypatch.setattr(context_runtime, "_decode_receipt", forbidden)
    monkeypatch.setattr(dataset, "_receipt", forbidden)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])


@pytest.mark.parametrize("kind", ["context-experiment-v1", "context-dataset-v1", "context-fit-v1",
    "context-training-case-v1", "context-base-replay-v1", "context-native-identity-map-v1"])
def test_known_schema_claims_are_not_opaque_legacy(kind, tmp_path):
    path = tmp_path / "malformed.db"
    put_artifact(path, kind=kind, payload={"schema": 1}, created_at=EVALUATED)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


@pytest.mark.parametrize("schema", [True, 1., "1", None, 0])
def test_invalid_schema_type_is_not_an_unknown_capability(schema, tmp_path):
    path = tmp_path / "schema.db"
    put_artifact(path, kind="context-dataset-v1", payload={"schema": schema}, created_at=EVALUATED)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


@pytest.mark.parametrize("kind,payload", [
    ("context-experiment-v1", {"synthetic_transport_only": 1}),
    ("context-evaluation-v1", {"schema": 2, "future_data": []}),
    ("context-dataset-v1", {"schema": 2, "future_data": []}),
    ("unrecognized-future-kind", {"schema": 1, "future_data": []}),
])
def test_true_unknown_schema_remains_transport_only_exit_two(kind, payload, tmp_path, capsys):
    from scripts.verify_context_runtime import main
    path = tmp_path / "unknown.db"
    put_artifact(path, kind=kind, payload=payload, created_at=EVALUATED)
    before = path.read_bytes()
    assert main(["--database", str(path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["verification_level"] == "transport_only"
    assert result["empirical_approval_verified"] is False
    assert result["d2_verified"]["approvals"] == []
    assert path.read_bytes() == before


def test_prefreeze_orphans_are_not_completed_with_invented_config(packets, tmp_path):
    packet = sealed_copy(packets[0], tmp_path)
    with closing(sqlite3.connect(packet["path"])) as connection:
        connection.execute("DELETE FROM artifacts WHERE kind='context-experiment-v1'")
        connection.commit()
    before = packet["path"].read_bytes()
    result = verify_context_database(packet["path"])
    assert result["verification_level"] == "transport_only"
    assert {"d2-dataset-owning-experiment-unavailable", "d1-fit-owning-replay-unavailable",
            "d1-case-owning-replay-unavailable", "d1-original-replay-context-unavailable"} <= set(result["limitations"])
    assert not any(result["d2_verified"].values())
    assert packet["path"].read_bytes() == before


@pytest.mark.parametrize("state", ["available", "missing", "stale", "conflicting", "not_applicable"])
@pytest.mark.parametrize("defect", ["missing", "future-final"])
def test_orphan_case_every_explicit_feature_receipt_remains_physical_evidence(
        packets, tmp_path, state, defect):
    packet = sealed_copy(packets[0], tmp_path)
    with closing(sqlite3.connect(packet["path"])) as connection:
        connection.execute("DELETE FROM artifacts WHERE kind='context-experiment-v1'")
        connection.commit()
    case = deepcopy(packet["cases"][0]["case"]["payload"])
    names = sorted(name for name, refs in case["features"]["refs"].items()
                   if refs and case["features"]["states"][name] == "available")
    assert len(names) > 1
    name = names[-1]  # Not just the first configured feature or first ref.
    ref = ("f" * 64 if defect == "missing" else
           packet["cases"][-1]["case"]["payload"]["outcome_ref"])
    case["features"]["refs"][name] = sorted({*case["features"]["refs"][name], ref})
    case["features"]["states"][name] = state
    if state in {"missing", "not_applicable"}:
        case["features"]["values"][name] = None
    add_artifact(packet, "context-training-case-v1", case)
    before = packet["path"].read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])
    assert packet["path"].read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["copy.db"]


@pytest.mark.parametrize("case_index", [0, -1])
@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_orphan_feature_receipt_obeys_original_decision_not_later_case_creation(
        packets, tmp_path, case_index, microseconds):
    from context_models.contracts import OBSERVATION_FIELDS
    from context_observations import append_observation

    packet = sealed_copy(packets[0], tmp_path)
    with closing(sqlite3.connect(packet["path"])) as connection:
        connection.execute("DELETE FROM artifacts WHERE kind='context-experiment-v1'")
        connection.commit()
    resolved = packet["cases"][case_index]
    case = deepcopy(resolved["case"]["payload"])
    name = next(name for name, refs in case["features"]["refs"].items() if refs)
    original = case["features"]["refs"][name][0]
    record = next(row for row in resolved["observations"] if row["digest"] == original)
    actual_receipt = datetime.fromisoformat(case["features"]["cutoff"]) + timedelta(microseconds=microseconds)
    assert actual_receipt < EVALUATED
    ref = append_observation(packet["path"], {key: record[key] for key in OBSERVATION_FIELDS},
                             observed_at=actual_receipt)
    case["features"]["refs"][name] = sorted({*case["features"]["refs"][name], ref})
    add_artifact(packet, "context-training-case-v1", case)
    before = packet["path"].read_bytes()
    if microseconds > 0:
        with pytest.raises(ArtifactIntegrityError):
            verify_context_database(packet["path"])
    else:
        result = verify_context_database(packet["path"])
        assert result["verification_level"] == "transport_only"
        assert "d1-case-owning-replay-unavailable" in result["limitations"]
        assert not any(result["d2_verified"].values())
        assert result["empirical_approval_verified"] is False
    assert packet["path"].read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["copy.db"]


def test_explicit_future_feature_ref_rejects_before_decoding_unopened_final_body(
        packets, tmp_path, monkeypatch):
    import context_observations
    import context_runtime

    packet = sealed_copy(packets[0], tmp_path)
    case = deepcopy(packet["cases"][0]["case"]["payload"])
    name = next(name for name, refs in case["features"]["refs"].items() if refs)
    ref = packet["cases"][-1]["case"]["payload"]["outcome_ref"]
    case["features"]["refs"][name] = sorted({*case["features"]["refs"][name], ref})
    add_artifact(packet, "context-training-case-v1", case)
    original = context_observations._decode_receipt
    def no_final_decode(row):
        assert row[0] != ref, "physical feature guard opened the final outcome body"
        return original(row)
    monkeypatch.setattr(context_observations, "_decode_receipt", no_final_decode)
    monkeypatch.setattr(context_runtime, "_decode_receipt", no_final_decode)
    before = packet["path"].read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])
    assert packet["path"].read_bytes() == before


@pytest.mark.parametrize("kind", ["context-base-replay-recipe-v1", "context-base-replay-v1",
    "context-native-identity-map-v1", "context-fit-v1", "context-training-case-v1"])
def test_actual_missing_inactive_reference_is_not_an_orphan_capability_gap(packets, tmp_path, kind):
    packet = sealed_copy(packets[0], tmp_path)
    with closing(sqlite3.connect(packet["path"])) as connection:
        connection.execute("DELETE FROM artifacts WHERE digest=(SELECT digest FROM artifacts WHERE kind=? LIMIT 1)", (kind,))
        connection.commit()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])


@pytest.mark.parametrize("change", ["status", "count", "rows-hash", "selected", "score", "reason", "partition"])
def test_orphan_known_fit_cannot_hide_config_independent_contradictions(packets, tmp_path, change):
    packet = sealed_copy(packets[0], tmp_path)
    with closing(sqlite3.connect(packet["path"])) as connection:
        connection.execute("DELETE FROM artifacts WHERE kind='context-experiment-v1'")
        connection.commit()
    forged = deepcopy(packet["fit"])
    if change == "status":
        forged["status"] = "arbitrary-synthetic-approval"
    elif change == "count":
        forged["training_events"] = True
    elif change == "rows-hash":
        forged["rows_hash"] = "not-a-hash"
    elif change == "selected":
        forged["artifact"] = None
    elif change == "score":
        forged["alpha_scores"][0]["mean_brier"] = 1.5
    elif change == "reason":
        forged["reason"] = "fitted-with-failure"
    else:
        forged["tuning_case_hashes"] = forged["training_case_hashes"]
    add_artifact(packet, "context-fit-v1", forged)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])


@pytest.mark.parametrize("change", ["subset", "map", "clock"])
def test_unknown_extra_opening_cannot_hide_a_damaged_known_opening(packets, tmp_path, change):
    packet = sealed_copy(packets[0], tmp_path)
    payload = deepcopy(packets[1]["evaluation"]["payload"])
    opening = {"schema": 1, "experiment_hash": packet["experiment_ref"],
        "event_identity_hash": packet["plan"]["event_identity_hash"],
        "event_keys": sorted(item["event"]["event_key"] for item in packet["plan"]["test_inventory"]),
        "opened_at": payload["opened_at"]}
    if change == "subset":
        opening["event_keys"] = opening["event_keys"][:-1]
    elif change == "map":
        opening["event_identity_hash"] = "e" * 64
    else:
        opening["opened_at"] = packet["plan"]["created_at"]
    add_artifact(packet, "context-test-opening-v1", opening)
    add_artifact(packet, "context-test-opening-v1", {"schema": 2, "future_inventory": []})
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(packet["path"])


def test_unknown_extra_opening_keeps_valid_known_opening_unresolved(packets, tmp_path, monkeypatch):
    import context_runtime
    packet = sealed_copy(packets[1], tmp_path)
    add_artifact(packet, "context-test-opening-v1", {"schema": 2, "future_inventory": []})
    finals = {item["event"]["event_key"] for item in packet["plan"]["test_inventory"]}
    original = context_runtime._decode_receipt
    def guarded(row):
        assert not (row[2] in finals and row[7] == "match_outcome")
        return original(row)
    monkeypatch.setattr(context_runtime, "_decode_receipt", guarded)
    result = verify_context_database(packet["path"])
    assert result["verification_level"] == "transport_only"
    assert "d2-opening-semantics-unavailable" in result["limitations"]
    assert "d2-evaluation-opening-unavailable" in result["limitations"]
    assert result["d2_verified"]["evaluations"] == []


def test_actual_two_hypothesis_d2_wal_stage_archive_restore_preserves_losers(packets, tmp_path):
    """Real local backup/restore, synthetic source data; no empirical pass."""
    from context_dataset_helpers import FROZEN
    from context_models.experiments import freeze_experiment
    from scripts import stage_runtime_databases as stage, backup_runtime_databases as backup
    from test_context_runtime_backup import stored_rows

    packet = sealed_copy(packets[0], tmp_path)
    plan = deepcopy(packet["plan"])
    definition = {key: plan["hypotheses"][0][key] for key in
                  ("family_config_hash", "ablation", "target_markets", "outcome_contract")}
    definition["ablation"] = "baseline-control"
    control_id = digest(definition)
    plan["hypotheses"].append({**definition, "hypothesis_id": control_id,
                              "candidate_artifact": None, "pretest_status": "baseline_control"})
    plan["hypotheses"].sort(key=lambda row: row["hypothesis_id"])
    # Construct an independent pre-freeze fixture, not a rewrite of any
    # opened experiment. Its original source/fit/database receipts are real.
    with closing(sqlite3.connect(packet["path"])) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind='context-test-opening-v1'").fetchone() == (0,)
        connection.execute("DELETE FROM artifacts WHERE kind='context-experiment-v1'")
        connection.commit()
    ref = freeze_experiment(packet["path"], plan, created_at=FROZEN)
    root = tmp_path / "app"
    root.mkdir(mode=0o700)
    (root / "runtime_state").mkdir(mode=0o700)
    path = root / "runtime_state" / "context_models.db"
    with closing(sqlite3.connect(packet["path"])) as source, closing(sqlite3.connect(path)) as target:
        source.backup(target)
    os.chmod(path, 0o600)
    staged = tmp_path / "private-stage"
    staged.mkdir(mode=0o700)
    tables = ("artifacts", "context_observations", "context_contents")
    with closing(sqlite3.connect(path)) as keeper:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("BEGIN")
        before_count = keeper.execute("SELECT count(*) FROM artifacts").fetchone()[0]
        main_bytes = path.read_bytes()
        evaluated = evaluate_experiment(path, ref, evaluated_at=EVALUATED)
        assert evaluated["approvals"] == []
        report = evaluated["payload"]
        assert set(report["statistics"]["hypotheses"]) == {packet["hypothesis_id"], control_id}
        assert report["statistics"]["q_values"][control_id] == 1.
        assert keeper.execute("SELECT count(*) FROM artifacts").fetchone()[0] == before_count
        assert Path(str(path) + "-wal").stat().st_size > 0
        assert path.read_bytes() == main_bytes
        expected_rows = {table: stored_rows(path, table) for table in tables}
        assert len(expected_rows["artifacts"]) > before_count
        manifest = stage.stage_databases(root, staged)
        archive, count = backup.create_archive(tmp_path / "archives", root=staged,
            logical_root=root, stage_manifest_path=staged / "manifest.json", now=EVALUATED)
    assert manifest["database_count"] == count == backup.verify_archive(archive) == 1
    restored_root = tmp_path / "restored"
    restored_root.mkdir(mode=0o700)
    (restored_root / "runtime_state").mkdir(mode=0o700)
    restored = restored_root / "runtime_state" / "context_models.db"
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.namelist() == ["runtime_state/context_models.db"]
        descriptor = os.open(restored, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(zipped.read("runtime_state/context_models.db"))
    before = restored.read_bytes()
    verified = verify_context_database(restored)
    assert verified["verification_level"] == "structural"
    assert verified["d2_verified"]["evaluations"] == [evaluated["digest"]]
    assert verified["d2_verified"]["approvals"] == []
    assert verified["empirical_approval_verified"] is False
    assert restored.read_bytes() == before
    assert {table: stored_rows(restored, table) for table in tables} == expected_rows
    assert sorted(p.name for p in restored.parent.iterdir()) == ["context_models.db"]

    # Rehashed inactive report cannot hide the losing/control hypothesis.
    changed = deepcopy(report)
    for field in ("hypotheses", "q_values"):
        del changed["statistics"][field][control_id]
    changed["results"].pop(control_id)
    add_artifact({"path": restored}, "context-evaluation-v1", changed)
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(restored)
