"""Synthetic freeze/open lifecycle checks; none is an empirical model trial."""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextContractError, digest
from model_artifacts import load_artifact, put_artifact, canonical_bytes


UTC = timezone.utc
CREATED = datetime(2026, 9, 1, tzinfo=UTC)
OPENED = datetime(2026, 9, 4, tzinfo=UTC)


def api():
    return importlib.import_module("context_models.experiments")


def plan(path, *, first_event=1):
    config = json.loads((Path(__file__).parent/"fixtures/context/training/tennis-winner-family-v1.json").read_text(encoding="utf-8"))
    definition = {"family_config_hash": digest(config), "ablation": "baseline",
                  "target_markets": config["target_markets"], "outcome_contract": config["outcome_contract"]}
    hypothesis = {"hypothesis_id": digest(definition), **definition, "candidate_artifact": None,
                  "pretest_status": "baseline_control"}
    inventory, bindings = [], []
    for i in range(3):
        decision = CREATED+timedelta(days=i, hours=1)
        event = {"event_key": f"espn:tennis:ATP:match:{first_event+i}", "sport": "tennis",
                 "home_id": "espn:tennis:ATP:player:1", "away_id": "espn:tennis:ATP:player:2",
                 "competition": "espn:ATP:tournament:189-2026", "format": "singles_best_of_3",
                 "scheduled_start": (decision+timedelta(hours=2)).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                 "schedule_revision": "native-v1", "status": "scheduled", "tour": "ATP", "surface": "Hard", "indoor": False}
        inventory.append({"event": event, "decision_at": decision.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                          "block": f"test:{i}"})
        bindings.append({"event_key": event["event_key"], "home_id": event["home_id"],
                         "away_id": event["away_id"], "source_refs": [str(i+1)*64]})
    identity = {"schema": 1, "policy": "native-source-only-v1", "bindings": sorted(bindings, key=lambda r: r["event_key"])}
    identity_hash = put_artifact(path, kind="context-native-identity-map-v1", payload=identity, created_at=CREATED)
    return {"schema": 1, "dataset_hash": "a"*64, "event_identity_hash": identity_hash,
            "code_revision": "b"*40, "base_versions": config["base_versions"], "family_configs": [config],
            "train_end": config["train_end"], "tune_end": config["tune_end"],
            "test_blocks": [[(CREATED+timedelta(days=i)).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                             (CREATED+timedelta(days=i+1)).isoformat(timespec="microseconds").replace("+00:00", "Z")]
                            for i in range(3)],
            "target_markets": config["target_markets"], "outcome_contracts": [config["outcome_contract"]],
            "candidate_artifacts": [], "policy_version": "context-paired-hac-bh-v1",
            "availability_classes": ["prospective"], "created_at": "2026-09-01T00:00:00.000000Z",
            "hypotheses": [hypothesis], "test_inventory": inventory}


def freeze(path, value):
    return api().freeze_experiment(path, value, created_at=CREATED)


def test_freeze_is_immutable_exact_repeatable_and_does_not_claim_approval(tmp_path):
    path = tmp_path/"models.db"
    value = plan(path)
    before = deepcopy(value)
    ref = freeze(path, value)
    assert ref == freeze(path, value)
    assert load_artifact(path, ref) == {"kind": "context-experiment-v1", "payload": value}
    assert value == before
    assert not any(k in value for k in ("approved", "passed", "actual_quality"))


@pytest.mark.parametrize("field,value", [("schema", True), ("code_revision", "short"),
    ("policy_version", "force"), ("candidate_artifacts", ["c"*64]), ("target_markets", ["winner_a"]),
    ("availability_classes", ["provider_verified"]), ("outcome_contracts", []),
    ("created_at", "2026-09-01T00:00:01Z"), ("extra", "odds")])
def test_closed_plan_rejects_unbound_or_unsupported_policy_fields(tmp_path, field, value):
    path = tmp_path/"models.db"
    data = plan(path)
    data[field] = value
    with pytest.raises(ContextContractError):
        freeze(path, data)


def test_hypothesis_identity_cannot_hide_a_changed_definition(tmp_path):
    path = tmp_path/"models.db"
    value = plan(path)
    value["hypotheses"][0]["ablation"] = "joint"
    with pytest.raises(ContextContractError):
        freeze(path, value)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown-config", "ready-null", "failed-candidate"])
def test_all_pretest_hypotheses_remain_in_one_explicit_registry(tmp_path, mutation):
    path = tmp_path/"models.db"
    value = plan(path)
    item = value["hypotheses"][0]
    if mutation == "missing":
        value["hypotheses"] = []
    elif mutation == "duplicate":
        value["hypotheses"].append(deepcopy(item))
    elif mutation == "unknown-config":
        item["family_config_hash"] = "c"*64
    elif mutation == "ready-null":
        item["pretest_status"] = "ready"
    else:
        item["pretest_status"], item["candidate_artifact"] = "fit_failed", "c"*64
    with pytest.raises(ContextContractError):
        freeze(path, value)


@pytest.mark.parametrize("mutation", ["duplicate", "wrong-block", "late-decision", "label", "wrong-player", "wrong-scope"])
def test_unlabeled_inventory_is_one_native_event_at_one_actual_decision(tmp_path, mutation):
    path = tmp_path/"models.db"
    value = plan(path)
    item = value["test_inventory"][0]
    if mutation == "duplicate":
        value["test_inventory"].append(deepcopy(item))
    elif mutation == "wrong-block":
        item["block"] = "test:1"
    elif mutation == "late-decision":
        item["decision_at"] = item["event"]["scheduled_start"]
    elif mutation == "label":
        item["outcome"] = 1
    elif mutation == "wrong-player":
        item["event"]["home_id"] = "espn:tennis:ATP:player:999"
    else:
        item["event"]["tour"] = "WTA"
    with pytest.raises(ContextContractError):
        freeze(path, value)


def test_opening_is_original_a1_record_and_exact_rerun_keeps_clock(tmp_path):
    path = tmp_path/"models.db"
    value = plan(path)
    ref = freeze(path, value)
    opening = api().open_test_inventory(path, ref, opened_at=OPENED)
    again = api().open_test_inventory(path, ref, opened_at=OPENED+timedelta(days=1))
    assert opening == again
    record = load_artifact(path, opening)
    assert record["kind"] == "context-test-opening-v1"
    assert record["payload"]["experiment_hash"] == ref
    assert record["payload"]["event_keys"] == sorted(r["event"]["event_key"] for r in value["test_inventory"])
    assert record["payload"]["opened_at"] == "2026-09-04T00:00:00.000000Z"


def test_changed_dataset_or_clock_does_not_make_opened_matches_untouched(tmp_path):
    path = tmp_path/"models.db"
    first = plan(path)
    ref = freeze(path, first)
    api().open_test_inventory(path, ref, opened_at=OPENED)
    changed = deepcopy(first)
    changed["dataset_hash"] = "f"*64
    with pytest.raises(ContextContractError, match="opened"):
        freeze(path, changed)
    assert api().open_test_inventory(path, ref, opened_at=OPENED) is not None


def test_two_prefrozen_experiments_cannot_both_open_same_final_events(tmp_path):
    path = tmp_path/"models.db"
    first = plan(path)
    changed = {**deepcopy(first), "dataset_hash": "d"*64}
    a, b = freeze(path, first), freeze(path, changed)
    api().open_test_inventory(path, a, opened_at=OPENED)
    with pytest.raises(ContextContractError, match="opened"):
        api().open_test_inventory(path, b, opened_at=OPENED)


def test_new_actual_event_inventory_may_open_after_previous_trial(tmp_path):
    path = tmp_path/"models.db"
    a = freeze(path, plan(path))
    api().open_test_inventory(path, a, opened_at=OPENED)
    b = freeze(path, plan(path, first_event=50))
    assert api().open_test_inventory(path, b, opened_at=OPENED) != a


def test_corrupt_prior_opening_is_not_ignored_as_an_unavailable_trial(tmp_path):
    path = tmp_path/"models.db"
    ref = freeze(path, plan(path))
    opening = api().open_test_inventory(path, ref, opened_at=OPENED)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE artifacts SET payload=? WHERE digest=?", (canonical_bytes({"bad": True}), opening))
    with pytest.raises(ValueError):
        freeze(path, plan(path, first_event=70))


def test_opening_before_the_frozen_creation_clock_fails(tmp_path):
    path = tmp_path/"models.db"
    ref = freeze(path, plan(path))
    with pytest.raises(ContextContractError):
        api().open_test_inventory(path, ref, opened_at=CREATED-timedelta(seconds=1))


def test_whole_frozen_inventory_is_opened_not_a_successful_subset(tmp_path):
    path = tmp_path/"models.db"
    ref = freeze(path, plan(path))
    with pytest.raises(TypeError):
        api().open_test_inventory(path, ref, opened_at=OPENED, event_keys=["espn:tennis:ATP:match:1"])


def ready_plan(path, *, mutate=None, stored_at=CREATED-timedelta(days=1), kind="context-effect-v1"):
    import numpy as np
    from context_models.offset import fit_offset
    value = plan(path)
    config = value["family_configs"][0]
    effect = {k: deepcopy(config[k]) for k in ("schema", "sport", "family", "feature_version", "feature_names",
              "preprocessing_artifacts", "joint_calibration", "population", "coverage", "model_variant")}
    fit = fit_offset(np.array([[-1., 0.], [1., 1.], [0., -1.]]*20), np.zeros(60),
                     np.array([0., 1., 0.]*20), link="logit", alpha=1.)
    effect.update(heads={"winner": fit}, training_end=config["train_end"], training_refs_hash="e"*64)
    if mutate:
        mutate(effect)
    ref = put_artifact(path, kind=kind, payload=effect, created_at=stored_at)
    hypothesis = value["hypotheses"][0]
    hypothesis.update(candidate_artifact=ref, pretest_status="ready", ablation="joint")
    definition = {k: hypothesis[k] for k in ("family_config_hash", "ablation", "target_markets", "outcome_contract")}
    hypothesis["hypothesis_id"] = digest(definition)
    value["candidate_artifacts"] = [ref]
    return value


def test_ready_candidate_is_resolved_as_the_exact_matching_fitted_artifact(tmp_path):
    path = tmp_path/"models.db"
    value = ready_plan(path)
    ref = freeze(path, value)
    assert load_artifact(path, ref)["payload"]["candidate_artifacts"] == value["candidate_artifacts"]


@pytest.mark.parametrize("key,value", [("feature_names", ["observed_recovery_exact_hours_delta", "observed_sets_1d_delta"]),
    ("feature_version", "tennis-performed-load-v1"), ("training_end", "2026-08-02T00:00:00Z"),
    ("coverage", {"version": "tennis-performed-load-coverage-v1", "case": "missing"}),
    ("model_variant", "other-v1")])
def test_candidate_cannot_borrow_frozen_feature_scope_or_training_period(tmp_path, key, value):
    path = tmp_path/"models.db"
    data = ready_plan(path, mutate=lambda e: e.update({key: value}))
    with pytest.raises(ContextContractError):
        freeze(path, data)


def test_candidate_created_after_freeze_is_not_a_predeclared_fit(tmp_path):
    path = tmp_path/"models.db"
    data = ready_plan(path, stored_at=CREATED+timedelta(seconds=1))
    with pytest.raises(ContextContractError, match="after"):
        freeze(path, data)


def test_generic_artifact_cannot_pose_as_a_ready_context_effect(tmp_path):
    path = tmp_path/"models.db"
    with pytest.raises(ContextContractError):
        freeze(path, ready_plan(path, kind="arbitrary"))


def test_candidate_regularization_cannot_expand_the_search_after_the_fact(tmp_path):
    path = tmp_path/"models.db"
    data = ready_plan(path, mutate=lambda e: e["heads"]["winner"].update(alpha=2.))
    with pytest.raises(ContextContractError):
        freeze(path, data)


def test_two_simultaneous_openers_cannot_reserve_the_same_canonical_events(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    path = tmp_path/"models.db"
    data = plan(path)
    refs = (freeze(path, data), freeze(path, {**deepcopy(data), "dataset_hash": "d"*64}))
    barrier = threading.Barrier(2, timeout=5)

    def opening(ref):
        barrier.wait()
        try:
            return api().open_test_inventory(path, ref, opened_at=OPENED)
        except ContextContractError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(opening, refs))
    assert sum(value is not None for value in outcomes) == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind='context-test-opening-v1'").fetchone()[0] == 1


def test_failed_opening_transaction_keeps_no_partial_reservation(tmp_path, monkeypatch):
    path = tmp_path/"models.db"
    ref = freeze(path, plan(path))
    original = api()._persist

    def fail_after_insert(*args, **kw):
        original(*args, **kw)
        raise RuntimeError("injected before commit")

    with monkeypatch.context() as patcher:
        patcher.setattr(api(), "_persist", fail_after_insert)
        with pytest.raises(RuntimeError):
            api().open_test_inventory(path, ref, opened_at=OPENED)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind='context-test-opening-v1'").fetchone()[0] == 0
    assert api().open_test_inventory(path, ref, opened_at=OPENED)


def artifact_rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT digest,kind,payload,created_at FROM artifacts ORDER BY digest").fetchall()


def test_candidate_creation_cannot_precede_its_own_training_end(tmp_path):
    path = tmp_path/"models.db"
    data = ready_plan(path, stored_at=datetime(2026, 7, 31, tzinfo=UTC))
    before = artifact_rows(path)
    with pytest.raises(ContextContractError):
        freeze(path, data)
    assert artifact_rows(path) == before


def test_identity_map_created_after_freeze_cannot_be_a_frozen_reference(tmp_path):
    path = tmp_path/"models.db"
    data = plan(path)
    payload = load_artifact(path, data["event_identity_hash"])["payload"]
    payload["bindings"][0]["source_refs"] = ["f"*64]
    data["event_identity_hash"] = put_artifact(path, kind="context-native-identity-map-v1", payload=payload,
                                               created_at=CREATED+timedelta(microseconds=1))
    before = artifact_rows(path)
    with pytest.raises(ContextContractError):
        freeze(path, data)
    assert artifact_rows(path) == before


@pytest.mark.parametrize("offset", [-1, 1])
@pytest.mark.parametrize("operation", ["freeze", "open"])
def test_existing_experiment_actual_creation_must_equal_its_payload_clock(tmp_path, offset, operation):
    path = tmp_path/"models.db"
    data = plan(path)
    ref = put_artifact(path, kind=api().EXPERIMENT_KIND, payload=data,
                       created_at=CREATED+timedelta(microseconds=offset))
    before = artifact_rows(path)
    with pytest.raises(ContextContractError):
        if operation == "freeze":
            freeze(path, data)
        else:
            api().open_test_inventory(path, ref, opened_at=OPENED)
    assert artifact_rows(path) == before


@pytest.mark.parametrize("offset", [-1, 1])
@pytest.mark.parametrize("operation", ["freeze", "open"])
def test_opening_actual_creation_must_equal_its_original_payload_clock(tmp_path, offset, operation):
    path = tmp_path/"models.db"
    data = plan(path)
    ref = freeze(path, data)
    payload = {"schema": 1, "experiment_hash": ref, "event_identity_hash": data["event_identity_hash"],
               "event_keys": sorted(r["event"]["event_key"] for r in data["test_inventory"]),
               "opened_at": OPENED.isoformat(timespec="microseconds").replace("+00:00", "Z")}
    put_artifact(path, kind=api().OPENING_KIND, payload=payload,
                 created_at=OPENED+timedelta(microseconds=offset))
    before = artifact_rows(path)
    with pytest.raises(ContextContractError):
        if operation == "freeze":
            freeze(path, data)
        else:
            api().open_test_inventory(path, ref, opened_at=OPENED+timedelta(seconds=1))
    assert artifact_rows(path) == before


@pytest.mark.parametrize("kind", ["context-test-opening-v2", "ordinary-metadata", "tennis-tour-state", "context-experiment-v1"])
@pytest.mark.parametrize("operation", ["freeze", "open"])
def test_kind_corruption_cannot_filter_an_opening_out_before_its_hash_check(tmp_path, kind, operation):
    path = tmp_path/"models.db"
    data = plan(path)
    ref = freeze(path, data)
    changed = {**deepcopy(data), "dataset_hash": "d"*64}
    other = freeze(path, changed)
    opening = api().open_test_inventory(path, ref, opened_at=OPENED)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE artifacts SET kind=? WHERE digest=?", (kind, opening))
        connection.commit()
    before = artifact_rows(path)
    with pytest.raises(ValueError):
        if operation == "freeze":
            freeze(path, changed)
        else:
            api().open_test_inventory(path, other, opened_at=OPENED)
    assert artifact_rows(path) == before


def test_valid_unrelated_artifacts_survive_whole_inventory_hash_check(tmp_path):
    path = tmp_path/"models.db"
    data = ready_plan(path, stored_at=datetime(2026, 8, 1, tzinfo=UTC))
    generic = put_artifact(path, kind="unrelated-metadata-v1", payload={"note": "unchanged"}, created_at=CREATED)
    before = load_artifact(path, generic)
    ref = freeze(path, data)
    assert api().open_test_inventory(path, ref, opened_at=OPENED)
    assert load_artifact(path, generic) == before


def test_equivalent_aware_a1_clock_representation_does_not_change_original_opening(tmp_path):
    path = tmp_path/"models.db"
    ref = freeze(path, plan(path))
    opening = api().open_test_inventory(path, ref, opened_at=OPENED)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?", ("2026-09-01T02:00:00+02:00", ref))
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?", ("2026-09-04T02:00:00+02:00", opening))
        connection.commit()
    before = artifact_rows(path)
    assert api().open_test_inventory(path, ref, opened_at=OPENED) == opening
    assert artifact_rows(path) == before
