"""D1 train-only selection on full synthetic native cases, not real evidence."""
from copy import deepcopy
from datetime import datetime, timedelta
import math

import numpy as np
import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_training_helpers import NOW, envelope
from test_context_training_cases import football_case


@pytest.fixture(scope="module")
def cohort(tmp_path_factory):
    from context_models.football import football_features
    from context_models.replay import replay_base_distribution
    from context_models.training_cases import assemble_training_cases
    path = tmp_path_factory.mktemp("d1-fit")
    pairs = [football_case(path, decision=NOW-timedelta(days=days), event_id=9000+i,
                           minute_shift=i, goals=goals)
             for i, (days, goals) in enumerate(((9, (0, 1)), (8, (4, 0)), (5, (2, 2)), (4, (1, 0))))]
    config = deepcopy(pairs[0][1])
    config.update(train_end=canonical_timestamp(NOW-timedelta(days=7)), tune_end=canonical_timestamp(NOW-timedelta(days=1)))
    identities = envelope("context-native-identity-map-v1", {"schema": 1, "policy": "native-source-only-v1",
        "bindings": [resolved["artifacts"][resolved["case"]["payload"]["event_identity_hash"]]["payload"]["bindings"][0]
                     for resolved, _ in pairs]})
    cases = []
    for resolved, _ in pairs:
        payload = resolved["case"]["payload"]
        old_replay = resolved["artifacts"][payload["replay_ref"]]
        recipe = resolved["artifacts"][old_replay["payload"]["recipe_hash"]]
        history = tuple(row for row in resolved["observations"] if row["kind"] == "base_fixture")
        decision = datetime.fromisoformat(payload["base"]["cutoff"])
        replay = replay_base_distribution("football", payload["event"], history, decision_at=decision,
                                          reconstructed_at=NOW, recipe=recipe, identity_map=identities)
        base = replay["payload"]["base"]
        source_rows = tuple(row for row in resolved["observations"] if row["kind"] != "match_outcome")
        features = football_features(payload["event"], source_rows, base, cutoff=decision)
        payload.update(base=base, features=features, replay_ref=replay["digest"],
                       event_identity_hash=identities["digest"], family_config_hash=digest(config))
        resolved["case"] = envelope("context-training-case-v1", payload)
        resolved["artifacts"] = {obj["digest"]: obj for obj in (replay, recipe, identities)}
        cases.append(resolved)
    cases = tuple(cases)
    assembly = assemble_training_cases(cases, config)
    assert assembly["canonical_events"] == 4 and not assembly["excluded"]
    return assembly["rows"], cases, config


def test_actual_train_family_selects_five_train_only_candidates_by_event_brier(cohort):
    from context_models.training import fit_family, train_family
    rows, cases, config = deepcopy(cohort)
    before = deepcopy((rows, cases, config))
    report = fit_family(rows, config, cases=cases)
    assert report["status"] == "fitted"
    assert report["training_events"] == report["tuning_events"] == 2
    assert len(report["alpha_scores"]) == 5
    scored = [row for row in report["alpha_scores"] if row["status"] == "scored"]
    assert all((row["mean_brier"] is None) == (row["status"] == "fit_failed") for row in report["alpha_scores"])
    selected = min(scored, key=lambda row: (row["mean_brier"], -row["alpha"]))
    assert report["selected_alpha"] == selected["alpha"]
    assert report["artifact"]["training_end"] == config["train_end"]
    assert all(head["n_rows"] == 2 for head in report["artifact"]["heads"].values())
    expected_scale = np.std([row["x"] for row in rows if row["head"] == "home" and row["decision_at"] < config["train_end"]], axis=0)
    assert report["artifact"]["heads"]["home"]["scale"] == np.maximum(expected_scale, 1e-8).tolist()
    assert train_family(rows, config, cases=cases) == report["artifact"]
    assert (rows, cases, config) == before


def test_free_training_array_cannot_override_recomputed_case_values(cohort):
    from context_models.training import fit_family
    rows, cases, config = deepcopy(cohort)
    rows[0]["x"][0] += 1
    with pytest.raises(ContextContractError, match="reconstructed|case|rows"):
        fit_family(rows, config, cases=cases)


def test_final_case_is_rejected_before_any_outcome_receipt_is_opened(cohort, monkeypatch):
    import context_models.training as training
    import context_models.training_cases as assembly
    rows, cases, config = deepcopy(cohort)
    config["tune_end"] = canonical_timestamp(NOW-timedelta(days=6))
    for case in cases:
        case["case"]["payload"]["family_config_hash"] = digest(config)
        case["case"] = envelope("context-training-case-v1", case["case"]["payload"])
        case["observations"] = object()  # Reading outcome storage would fail.
    def forbidden(*args, **kwargs):
        raise AssertionError("final labels were opened")
    monkeypatch.setattr(assembly, "assemble_training_cases", forbidden)
    with pytest.raises(ContextContractError, match="final|tuning"):
        training.fit_family(rows, config, cases=cases)


def test_absent_training_data_returns_report_but_artifact_projection_raises():
    from context_models.training import fit_family, train_family, TrainingUnavailable
    from test_context_training_contracts import winner_config
    config = winner_config()
    report = fit_family((), config, cases=())
    assert report["status"] == "insufficient_data" and report["artifact"] is None
    with pytest.raises(TrainingUnavailable):
        train_family((), config, cases=())


def test_exact_tuning_tie_prefers_larger_declared_alpha(cohort):
    from context_models.training import _fit_cohort
    rows, cases, config = deepcopy(cohort)
    # Explicit numerical unit fixture, not a public receipt-valid input: all
    # x=0 makes every candidate the same original distribution on tune.
    for row in rows:
        row["x"] = [0.]
    for case in cases:
        case["case"]["payload"]["features"]["values"][config["feature_names"][0]] = 0.
    report = _fit_cohort(rows, cases, config, exclusions=())
    assert report["status"] == "fitted" and report["selected_alpha"] == 100.
    assert len({score["mean_brier"] for score in report["alpha_scores"]}) == 1


def test_one_failed_tuning_case_cannot_be_removed_for_one_alpha(cohort, monkeypatch):
    import context_models.training as training
    from context_models.offset import ContextModelError
    import context_models.football_effect as football
    rows, cases, config = deepcopy(cohort)
    original = football.apply_football_effect
    def fail_one(base, features, artifact, *, event):
        if artifact["heads"]["home"]["alpha"] == .01 and event["event_key"].endswith("9003"):
            raise ContextModelError("synthetic complete prediction failure")
        return original(base, features, artifact, event=event)
    monkeypatch.setattr(football, "apply_football_effect", fail_one)
    report = training._fit_cohort(rows, cases, config, exclusions=())
    assert report["alpha_scores"][0]["status"] == "fit_failed"
    assert report["alpha_scores"][0]["mean_brier"] is None
    assert report["selected_alpha"] != .01
