"""Source-bound evaluation mechanics; seven synthetic events cannot approve."""
import sqlite3
from copy import deepcopy
from datetime import timedelta

import pytest

from context_dataset_helpers import EVALUATED, copy_packet
from test_context_dataset import prepared


def test_evaluator_recomputes_markets_and_density_after_durable_whole_opening(prepared, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    from context_models.evaluator import evaluate_experiment, verify_evaluation
    from context_models.experiments import _openings
    packet = copy_packet(prepared, tmp_path)
    final_refs = {c["case"]["payload"]["outcome_ref"] for c in packet["cases"][4:]}
    original = dataset._receipt
    def guarded(connection, ref):
        if ref in final_refs:
            openings, _ = _openings(connection)
            assert openings[packet["experiment_ref"]][1]["event_keys"] == sorted(
                row["event"]["event_key"] for row in packet["plan"]["test_inventory"])
        return original(connection, ref)
    monkeypatch.setattr(dataset, "_receipt", guarded)
    result = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    payload = result["payload"]
    key = packet["hypothesis_id"]
    assert len(payload["results"][key]) == 9
    assert len(payload["distribution_losses"][key]) == 3
    assert payload["statistics"]["hypotheses"][key]["metrics"]["event_count"] == 3
    assert result["approvals"] == []
    with dataset._reader(packet["path"]) as connection:
        assert verify_evaluation(connection, result["digest"])["payload"] == payload


def test_numerical_ready_failure_is_not_a_favorable_coverage_exclusion(prepared, tmp_path, monkeypatch):
    import context_models.evaluator as evaluator
    from context_models.offset import ContextModelError
    packet = copy_packet(prepared, tmp_path)
    def broken(*args, **kwargs):
        raise ContextModelError("explicit numerical edge")
    monkeypatch.setattr(evaluator, "_comparison", broken)
    result = evaluator.evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    key = packet["hypothesis_id"]
    assert len(result["payload"]["ready_failures"][key]) == 3
    metric = result["payload"]["statistics"]["hypotheses"][key]
    assert metric["pretest_status"] == "ready"
    assert metric["p_value"] == 1 and result["payload"]["statistics"]["q_values"][key] == 1
    assert "ready-computation-failure" in metric["failures"]
    assert result["approvals"] == []


def test_corrupt_final_outer_index_is_rejected_before_opening(prepared, tmp_path):
    from context_models.contracts import ContextIntegrityError
    from context_models.evaluator import evaluate_experiment
    packet = copy_packet(prepared, tmp_path)
    final = packet["cases"][-1]["case"]["payload"]["outcome_ref"]
    with sqlite3.connect(packet["path"]) as connection:
        connection.execute("UPDATE context_observations SET source='corrupted' WHERE digest=?", (final,))
    with pytest.raises(ContextIntegrityError):
        evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    with sqlite3.connect(packet["path"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-test-opening-v1'").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-evaluation-v1'").fetchone()[0] == 0


def test_corrupt_final_semantics_keep_durable_opening_and_cannot_publish_report(prepared, tmp_path):
    from context_models.contracts import ContextContractError, OBSERVATION_FIELDS, digest
    from context_models.evaluator import evaluate_experiment
    from model_artifacts import canonical_bytes, put_artifact
    from context_dataset_helpers import BUILT
    from test_context_dataset import _refreeze
    packet = copy_packet(prepared, tmp_path)
    final_case = packet["cases"][-1]
    header = deepcopy(final_case["case"]["payload"])
    old_ref = header["outcome_ref"]
    original = next(row for row in final_case["observations"] if row["digest"] == old_ref)
    content = {field: deepcopy(original[field]) for field in OBSERVATION_FIELDS}
    content["payload"]["result"]["goals_home"] = -1  # valid JSON/header, invalid owning goal result
    content["source_revision"] = digest(content["payload"])
    content_ref = digest(content)
    ref = digest({"content_digest": content_ref, "observed_at": original["observed_at"]})
    with sqlite3.connect(packet["path"]) as connection:
        connection.execute("INSERT INTO context_contents VALUES (?,?)", (content_ref, canonical_bytes(content)))
        connection.execute("INSERT INTO context_observations VALUES (?,?,?,?,?,?,?,?)", (ref, content_ref,
            content["event_key"], original["observed_at"], content["schedule_revision"], content["source"],
            content["subject_id"], content["kind"]))
    header["outcome_ref"] = ref
    case_ref = put_artifact(packet["path"], kind="context-training-case-v1", payload=header, created_at=BUILT)
    dataset = deepcopy(packet["dataset"])
    item = dataset["groups"][0]["final_cases"][-1]
    item["case_ref"] = case_ref
    item["observation_refs"] = sorted(ref if value == old_ref else value for value in item["observation_refs"])
    experiment_ref = _refreeze(packet, dataset)
    with pytest.raises(ContextContractError):
        evaluate_experiment(packet["path"], experiment_ref, evaluated_at=EVALUATED)
    with sqlite3.connect(packet["path"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-test-opening-v1'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-evaluation-v1'").fetchone()[0] == 0


def test_exact_rerun_retains_the_first_opening(prepared, tmp_path):
    from context_models.evaluator import evaluate_experiment
    packet = copy_packet(prepared, tmp_path)
    first = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    same = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    later = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED+timedelta(hours=1))
    assert first == same
    assert later["payload"]["opening_hash"] == first["payload"]["opening_hash"]
    assert later["payload"]["opened_at"] == first["payload"]["opened_at"]
    assert later["digest"] != first["digest"]


def test_owner_failed_ready_p_one_enters_bh_before_other_hypotheses(tmp_path):
    from context_models.evaluator import _policy
    from model_loss_statistics import benjamini_hochberg_q_values
    from test_context_registered_metrics import inputs
    plan, results, losses = inputs(tmp_path)
    keys = list(results)
    failures = {key: [] for key in keys}
    failures[keys[0]] = [{"event_key": "synthetic-failure", "reason": "arithmetic"}]
    stats = _policy(plan, results=results, distribution_losses=losses, ready_failures=failures)
    assert stats["hypotheses"][keys[0]]["metrics"]["p_value"] < 1
    assert stats["hypotheses"][keys[0]]["p_value"] == 1
    assert stats["q_values"] == benjamini_hochberg_q_values({key: row["p_value"] for key, row in stats["hypotheses"].items()})


def test_baseline_control_uses_actual_sources_but_never_obtains_approval(prepared, tmp_path):
    from context_models.evaluator import evaluate_experiment
    from context_models.experiments import freeze_experiment
    from context_models.contracts import digest
    from model_artifacts import put_artifact
    from context_dataset_helpers import BUILT, FROZEN
    packet = copy_packet(prepared, tmp_path)
    dataset, plan = deepcopy(packet["dataset"]), deepcopy(packet["plan"])
    dataset["groups"][0]["fit_ref"] = None
    plan["dataset_hash"] = put_artifact(packet["path"], kind="context-dataset-v1", payload=dataset, created_at=BUILT)
    plan["candidate_artifacts"] = []
    plan["hypotheses"][0].update(pretest_status="baseline_control", candidate_artifact=None)
    ref = freeze_experiment(packet["path"], plan, created_at=FROZEN)
    report = evaluate_experiment(packet["path"], ref, evaluated_at=EVALUATED)
    key = packet["hypothesis_id"]
    assert len(report["payload"]["results"][key]) == 9
    assert all(row["p_base"] == row["p_context"] for row in report["payload"]["results"][key])
    assert all(row["base_logloss"] == row["context_logloss"] for row in report["payload"]["distribution_losses"][key])
    assert report["payload"]["statistics"]["hypotheses"][key]["p_value"] == 1 and report["approvals"] == []


@pytest.fixture(scope="module")
def evaluated(prepared, tmp_path_factory):
    from context_models.evaluator import evaluate_experiment
    packet = copy_packet(prepared, tmp_path_factory.mktemp("evaluated-d2"))
    packet["evaluation"] = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    return packet


@pytest.mark.parametrize("mutation", ["rows", "outcome", "statistics", "code", "opening", "receipts", "extra"])
def test_rehashed_report_is_not_evidence_for_modified_sources_or_metrics(evaluated, tmp_path, mutation):
    from context_models.evaluator import verify_evaluation
    from context_models.dataset import _reader
    from context_models.contracts import ContextIntegrityError
    from model_artifacts import put_artifact
    packet = copy_packet(evaluated, tmp_path)
    report = deepcopy(packet["evaluation"]["payload"])
    key = packet["hypothesis_id"]
    if mutation == "rows":
        report["results"][key][0]["p_context"] = .9
    elif mutation == "outcome":
        report["results"][key][0]["outcome"] = 1-report["results"][key][0]["outcome"]
    elif mutation == "statistics":
        report["statistics"]["hypotheses"][key]["failures"] = []
    elif mutation == "code":
        report["implementation_hashes"]["context_models/dataset.py"] = "f"*64
    elif mutation == "opening":
        report["opening_hash"] = "f"*64
    elif mutation == "receipts":
        report["observation_refs"].pop()
    else:
        report["passed"] = True
    ref = put_artifact(packet["path"], kind="context-evaluation-v1", payload=report, created_at=EVALUATED)
    with _reader(packet["path"]) as connection, pytest.raises(ContextIntegrityError):
        verify_evaluation(connection, ref)


def test_historical_verifier_accepts_memory_snapshot_and_performs_no_writes(evaluated):
    from context_models.evaluator import verify_evaluation
    with sqlite3.connect(evaluated["path"]) as source, sqlite3.connect(":memory:") as memory:
        source.backup(memory)
        memory.execute("PRAGMA query_only=ON")
        before = memory.total_changes
        assert verify_evaluation(memory, evaluated["evaluation"]["digest"])["digest"] == evaluated["evaluation"]["digest"]
        assert memory.total_changes == before


@pytest.mark.parametrize("when, changed", [("before", True), ("equal", True), ("simultaneous", True), ("after", True),
                                           ("before", False), ("equal", False)])
def test_actual_terminal_rechecks_and_corrections_respect_report_clock(prepared, tmp_path, when, changed):
    from datetime import datetime
    from context_models.evaluator import evaluate_experiment
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_outcome
    from context_training_helpers import detail
    packet = copy_packet(prepared, tmp_path)
    case = packet["cases"][-1]
    header = case["case"]["payload"]
    outcome = next(r for r in case["observations"] if r["digest"] == header["outcome_ref"])
    result = outcome["payload"]["result"]
    goals = result["goals_home"]+int(changed), result["goals_away"]
    clock = {"before": EVALUATED-timedelta(seconds=1), "equal": EVALUATED, "after": EVALUATED+timedelta(seconds=1),
             "simultaneous": datetime.fromisoformat(outcome["observed_at"])}[when]
    raw = detail(9006, datetime.fromisoformat(header["event"]["scheduled_start"]), goals=goals)
    ref = append_observation(packet["path"], normalize_football_outcome(header["event"], raw, observed_at=clock), observed_at=clock)
    evaluated_result = evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    report = evaluated_result["payload"]
    key = packet["hypothesis_id"]
    if changed and when != "after":
        assert report["ready_failures"][key]
        assert report["statistics"]["hypotheses"][key]["p_value"] == 1
        assert ref in report["outcome_revision_refs"][header["outcome_ref"]]
        assert len(report["distribution_losses"][key]) == 2
    else:
        assert report["ready_failures"][key] == []
        assert len(report["distribution_losses"][key]) == 3
        assert (ref in report["outcome_revision_refs"][header["outcome_ref"]]) == (when != "after")
    assert evaluated_result["approvals"] == []


def test_correction_received_later_does_not_rewrite_historical_report(evaluated, tmp_path):
    from datetime import datetime
    from context_models.evaluator import verify_evaluation
    from context_models.dataset import _reader
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_outcome
    from context_training_helpers import detail
    packet = copy_packet(evaluated, tmp_path)
    header = packet["cases"][-1]["case"]["payload"]
    raw = detail(9006, datetime.fromisoformat(header["event"]["scheduled_start"]), goals=(9, 9))
    later = EVALUATED+timedelta(seconds=1)
    append_observation(packet["path"], normalize_football_outcome(header["event"], raw, observed_at=later), observed_at=later)
    with _reader(packet["path"]) as connection:
        assert verify_evaluation(connection, packet["evaluation"]["digest"])["payload"] == packet["evaluation"]["payload"]


def test_known_native_tennis_replay_gap_is_explicit_unavailable_not_zero_or_approval(tmp_path):
    from test_context_experiments import plan as make_plan, CREATED, OPENED
    from context_models.contracts import digest
    from context_models.experiments import freeze_experiment
    from context_models.evaluator import evaluate_experiment
    from model_artifacts import put_artifact
    path = tmp_path/"unsupported.db"
    plan = make_plan(path)
    config_ref = digest(plan["family_configs"][0])
    dataset = {"schema": 1, "event_identity_hash": plan["event_identity_hash"], "groups": [{
        "family_config_hash": config_ref, "fit_ref": None, "training_cases": [], "final_cases": [],
        "unavailable_final": [{"event_key": row["event"]["event_key"], "decision_at": row["decision_at"],
                               "reason": "native_to_state_key_source_resolver_unavailable"} for row in plan["test_inventory"]]}]}
    plan["dataset_hash"] = put_artifact(path, kind="context-dataset-v1", payload=dataset, created_at=CREATED)
    ref = freeze_experiment(path, plan, created_at=CREATED)
    result = evaluate_experiment(path, ref, evaluated_at=OPENED)
    assert result["approvals"] == []
    assert len(result["payload"]["pretest_exclusions"]) == 3
    assert result["payload"]["observation_refs"] == []
    assert all(not rows for rows in result["payload"]["results"].values())
