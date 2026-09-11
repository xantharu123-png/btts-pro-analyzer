"""D2 pre-opening dataset inventory and source resolution boundaries."""
from copy import deepcopy
from datetime import datetime, timedelta
import sqlite3

import pytest

from context_dataset_helpers import BUILT, FROZEN, EVALUATED, cached_packet, copy_packet
from context_models.contracts import canonical_timestamp


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    return cached_packet(tmp_path_factory)


def test_real_sqlite_case_pool_and_all_five_fits_replay_exactly(prepared, tmp_path):
    from context_models.dataset import prepare_dataset
    packet = copy_packet(prepared, tmp_path)
    checked = prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
    assert checked["dataset"] == packet["dataset"]
    assert checked["fits"][packet["dataset"]["groups"][0]["family_config_hash"]] == packet["fit"]
    assert len(checked["final_headers"]) == 3


def test_closed_dataset_rejects_caller_proof_flags_and_implicit_omission(prepared):
    from context_models.dataset import validate_dataset
    from context_models.contracts import ContextContractError
    value = deepcopy(prepared["dataset"])
    value["verified"] = True
    with pytest.raises(ContextContractError):
        validate_dataset(value)


def test_final_labels_are_not_resolved_by_preparation(prepared, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    packet = copy_packet(prepared, tmp_path)
    final_refs = {c["case"]["payload"]["outcome_ref"] for c in packet["cases"][4:]}
    original = dataset._receipt
    def guarded(connection, ref):
        assert ref not in final_refs, "final label resolved before whole-inventory opening"
        return original(connection, ref)
    monkeypatch.setattr(dataset, "_receipt", guarded)
    decoder = dataset._decode_receipt
    def decoder_guard(stored):
        assert stored[0] not in final_refs, "final label decoder ran before whole-inventory opening"
        return decoder(stored)
    monkeypatch.setattr(dataset, "_decode_receipt", decoder_guard)
    dataset.prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)


def _refreeze(packet, dataset):
    from model_artifacts import put_artifact
    from context_models.experiments import freeze_experiment
    plan = deepcopy(packet["plan"])
    plan["dataset_hash"] = put_artifact(packet["path"], kind="context-dataset-v1", payload=dataset, created_at=BUILT)
    return freeze_experiment(packet["path"], plan, created_at=FROZEN)


@pytest.mark.parametrize("mutation", ["omitted-final", "duplicated-final", "final-in-training", "free-unavailable", "no-fit", "wrong-map", "case-pool-missing-own-result"])
def test_invalid_whole_inventory_fails_before_any_receipt_read(prepared, tmp_path, monkeypatch, mutation):
    import context_models.dataset as dataset
    from context_models.contracts import ContextContractError
    packet = copy_packet(prepared, tmp_path)
    value = deepcopy(packet["dataset"])
    group = value["groups"][0]
    if mutation == "omitted-final":
        group["final_cases"].pop()
    elif mutation == "duplicated-final":
        group["final_cases"].append(group["final_cases"][0])
    elif mutation == "final-in-training":
        group["training_cases"].append(group["final_cases"].pop())
    elif mutation == "free-unavailable":
        group["final_cases"].pop()
        header = packet["cases"][-1]["case"]["payload"]
        group["unavailable_final"].append({"event_key": header["event"]["event_key"],
            "decision_at": header["base"]["cutoff"], "reason": "provider_missing"})
    elif mutation == "no-fit":
        group["fit_ref"] = None
    elif mutation == "wrong-map":
        value["event_identity_hash"] = "f"*64
    else:
        group["final_cases"][0]["observation_refs"].remove(packet["cases"][4]["case"]["payload"]["outcome_ref"])
    ref = _refreeze(packet, value)
    monkeypatch.setattr(dataset, "_receipt", lambda *args: pytest.fail("labels accessed before inventory validation"))
    with pytest.raises(ContextContractError):
        dataset.prepare_dataset(packet["path"], ref, evaluated_at=EVALUATED)


@pytest.mark.parametrize("target", ["dataset", "fit", "case", "effect"])
def test_actual_a1_insertion_clock_cannot_follow_freeze(prepared, tmp_path, target):
    from context_models.dataset import prepare_dataset
    from context_models.contracts import ContextIntegrityError
    packet = copy_packet(prepared, tmp_path)
    refs = {"dataset": packet["plan"]["dataset_hash"], "fit": packet["dataset"]["groups"][0]["fit_ref"],
            "case": packet["cases"][-1]["case"]["digest"], "effect": packet["fit"]["effect_hash"]}
    with sqlite3.connect(packet["path"]) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?", (canonical_timestamp(EVALUATED), refs[target]))
    with pytest.raises(ContextIntegrityError):
        prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)


def test_newer_stored_native_revision_cannot_be_hidden_by_omitting_its_reference(prepared, tmp_path):
    from context_models.dataset import prepare_dataset
    from context_models.contracts import ContextIntegrityError
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    packet = copy_packet(prepared, tmp_path)
    first = packet["cases"][0]
    old = next(r for r in first["observations"] if r["kind"] == "base_fixture" and r["payload"]["detail"]["fixture"]["status"]["short"] == "FT")
    corrected = deepcopy(old["payload"]["detail"])
    corrected["goals"]["home"] += 1
    receipt = datetime.fromisoformat(first["case"]["payload"]["base"]["cutoff"])-timedelta(minutes=1)
    append_observation(packet["path"], normalize_football_base_input(corrected, observed_at=receipt), observed_at=receipt)
    with pytest.raises(ContextIntegrityError, match="omits an already-known"):
        prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)


def test_missing_database_is_not_created_by_preparation(tmp_path):
    from context_models.dataset import prepare_dataset
    from context_models.contracts import ContextIntegrityError
    path = tmp_path/"missing"/"model.db"
    with pytest.raises(ContextIntegrityError):
        prepare_dataset(path, "0"*64, evaluated_at=EVALUATED)
    assert not path.parent.exists()


def test_declared_training_pool_cannot_smuggle_a_final_outcome_before_opening(prepared, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    from context_models.contracts import ContextContractError
    packet = copy_packet(prepared, tmp_path)
    value = deepcopy(packet["dataset"])
    final_ref = packet["cases"][-1]["case"]["payload"]["outcome_ref"]
    pool = value["groups"][0]["training_cases"][0]["observation_refs"]
    pool.append(final_ref)
    pool.sort()
    ref = _refreeze(packet, value)
    original = dataset._receipt
    def guarded(connection, receipt):
        assert receipt != final_ref, "a training pool caused pre-opening final-label access"
        return original(connection, receipt)
    monkeypatch.setattr(dataset, "_receipt", guarded)
    with pytest.raises(ContextContractError):
        dataset.prepare_dataset(packet["path"], ref, evaluated_at=EVALUATED)


@pytest.mark.parametrize("mutation", ["score-one-ulp", "nonselected-coefficient", "pretest-status"])
def test_even_rehashed_syntactically_valid_fit_must_reproduce_original_training(prepared, tmp_path, mutation):
    from context_models.dataset import prepare_dataset
    from context_models.contracts import ContextIntegrityError, digest
    from context_models.experiments import freeze_experiment
    from context_models.training_contracts import validate_fit_result
    from model_artifacts import put_artifact
    import math
    packet = copy_packet(prepared, tmp_path)
    fit, dataset, plan = deepcopy(packet["fit"]), deepcopy(packet["dataset"]), deepcopy(packet["plan"])
    if mutation == "pretest-status":
        fit.update(status="unsupported", reason="caller_status", artifact=None, effect_hash=None, selected_alpha=None,
                   alpha_scores=[], candidate_artifacts={})
        plan["hypotheses"][0].update(pretest_status="unsupported", candidate_artifact=None)
        plan["candidate_artifacts"] = []
    else:
        score = next(row for row in fit["alpha_scores"] if row["status"] == "scored" and row["effect_hash"] != fit["effect_hash"])
        if mutation == "score-one-ulp":
            score["mean_brier"] = math.nextafter(score["mean_brier"], math.inf)
        else:
            old_ref = score["effect_hash"]
            candidate = fit["candidate_artifacts"].pop(old_ref)
            candidate["heads"]["home"]["coef"][0] = math.nextafter(candidate["heads"]["home"]["coef"][0], math.inf)
            new_ref = put_artifact(packet["path"], kind="context-effect-v1", payload=candidate, created_at=BUILT)
            fit["candidate_artifacts"][new_ref] = candidate
            score["effect_hash"] = new_ref
    assert validate_fit_result(fit, config=plan["family_configs"][0]) == fit
    dataset["groups"][0]["fit_ref"] = put_artifact(packet["path"], kind="context-fit-v1", payload=fit, created_at=BUILT)
    plan["dataset_hash"] = put_artifact(packet["path"], kind="context-dataset-v1", payload=dataset, created_at=BUILT)
    ref = freeze_experiment(packet["path"], plan, created_at=FROZEN)
    with pytest.raises(ContextIntegrityError, match="does not exactly reproduce"):
        prepare_dataset(packet["path"], ref, evaluated_at=EVALUATED)


def test_corrupted_kind_index_cannot_hide_an_undeclared_known_source_revision(prepared, tmp_path):
    from context_models.dataset import prepare_dataset
    from context_models.contracts import ContextIntegrityError
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    packet = copy_packet(prepared, tmp_path)
    first = packet["cases"][0]
    old = next(r for r in first["observations"] if r["kind"] == "base_fixture" and r["payload"]["detail"]["fixture"]["status"]["short"] == "FT")
    corrected = deepcopy(old["payload"]["detail"])
    corrected["goals"]["home"] += 1
    receipt = datetime.fromisoformat(first["case"]["payload"]["base"]["cutoff"])-timedelta(minutes=1)
    ref = append_observation(packet["path"], normalize_football_base_input(corrected, observed_at=receipt), observed_at=receipt)
    with sqlite3.connect(packet["path"]) as connection:
        connection.execute("UPDATE context_observations SET kind='match_outcome' WHERE digest=?", (ref,))
    with pytest.raises(ContextIntegrityError):
        prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)


def test_changed_event_index_cannot_hide_an_undeclared_native_correction(prepared, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    from context_models.contracts import ContextIntegrityError
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    packet = copy_packet(prepared, tmp_path)
    first = packet["cases"][0]
    old = next(r for r in first["observations"] if r["kind"] == "base_fixture" and r["payload"]["detail"]["fixture"]["status"]["short"] == "FT")
    corrected = deepcopy(old["payload"]["detail"])
    corrected["goals"]["home"] += 1
    receipt = datetime.fromisoformat(first["case"]["payload"]["base"]["cutoff"])-timedelta(minutes=1)
    ref = append_observation(packet["path"], normalize_football_base_input(corrected, observed_at=receipt), observed_at=receipt)
    with sqlite3.connect(packet["path"]) as connection:
        connection.execute("UPDATE context_observations SET event_key='football:api-football:9999999' WHERE digest=?", (ref,))
    final_refs = {c["case"]["payload"]["outcome_ref"] for c in packet["cases"][4:]}
    original = dataset._decode_receipt
    def guarded(stored):
        assert stored[0] not in final_refs, "final outcome body decoded by index preflight"
        return original(stored)
    monkeypatch.setattr(dataset, "_decode_receipt", guarded)
    with pytest.raises(ContextIntegrityError):
        dataset.prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)


@pytest.mark.parametrize("phase,index", [("train", 0), ("tune", 2)])
@pytest.mark.parametrize("when,changed", [("before", True), ("equal", True), ("after", True), ("before", False)])
def test_training_terminal_corrections_use_original_phase_not_today(prepared, tmp_path, monkeypatch, phase, index, when, changed):
    import context_models.dataset as dataset
    from context_models.contracts import ContextIntegrityError
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_outcome
    from context_training_helpers import detail
    packet = copy_packet(prepared, tmp_path)
    case = packet["cases"][index]
    header = case["case"]["payload"]
    outcome = next(r for r in case["observations"] if r["digest"] == header["outcome_ref"])
    result = outcome["payload"]["result"]
    boundary = datetime.fromisoformat(packet["plan"][phase+"_end"])
    receipt = boundary + timedelta(seconds={"before": -1, "equal": 0, "after": 1}[when])
    raw = detail(9000+index, datetime.fromisoformat(header["event"]["scheduled_start"]),
                 goals=(result["goals_home"]+int(changed), result["goals_away"]))
    ref = append_observation(packet["path"], normalize_football_outcome(header["event"], raw, observed_at=receipt), observed_at=receipt)
    if when == "after":
        original = dataset._receipt
        def guard(connection, candidate):
            assert candidate != ref, "later-than-original-phase label was read while reproducing training"
            return original(connection, candidate)
        monkeypatch.setattr(dataset, "_receipt", guard)
    if changed and when != "after":
        from context_models.evaluator import evaluate_experiment
        original_bytes = packet["path"].read_bytes()
        with pytest.raises(ContextIntegrityError, match="original train/tune"):
            evaluate_experiment(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
        assert packet["path"].read_bytes() == original_bytes
    else:
        checked = dataset.prepare_dataset(packet["path"], packet["experiment_ref"], evaluated_at=EVALUATED)
        assert checked["fits"]
        assert (ref in checked["training_outcome_revision_refs"][header["outcome_ref"]]) == (when != "after")
    with sqlite3.connect(packet["path"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-test-opening-v1'").fetchone()[0] == 0


def test_outer_projection_capability_failure_is_explicit_and_never_decodes_labels(prepared, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    from context_models.contracts import ContextIntegrityError
    packet = copy_packet(prepared, tmp_path)
    def forbidden(*args):
        pytest.fail("outer projection called full source body decoder")
    monkeypatch.setattr(dataset, "_decode_receipt", forbidden)
    with dataset._reader(packet["path"]) as connection:
        connection.create_function("json_valid", 1, lambda value: 0)
        with pytest.raises(ContextIntegrityError, match="projection capability"):
            dataset._physical_receipt_preflight(connection)


def test_outer_projection_binds_each_opaque_receipt_by_named_mapping_without_decoding(prepared, tmp_path, monkeypatch):
    import context_models.dataset as dataset
    packet = copy_packet(prepared, tmp_path)

    class BindingCapture(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            cursor = super().execute(sql, parameters)
            if isinstance(parameters, dict):
                self.named_bindings.append(parameters.copy())
            return cursor

    monkeypatch.setattr(
        dataset,
        "_decode_receipt",
        lambda *args: pytest.fail("outer projection decoded a protected receipt body"),
    )
    with sqlite3.connect(packet["path"], factory=BindingCapture) as connection:
        expected = [row[0] for row in connection.execute("SELECT payload FROM context_contents")]
        connection.named_bindings = []

        dataset._physical_receipt_preflight(connection)

        assert connection.named_bindings == [{"opaque": opaque} for opaque in expected]
