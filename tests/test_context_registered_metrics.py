"""Frozen-registry/cohort statistical mechanics on explicit synthetic rows."""
from copy import deepcopy
from datetime import timedelta
import importlib
from pathlib import Path
import runpy

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest


HELPERS = runpy.run_path(str(Path(__file__).parent/"test_context_experiments.py"))


def api():
    return importlib.import_module("context_models.evaluation")


def inputs(tmp_path, *, n=210, second="ready"):
    plan = HELPERS["ready_plan"](tmp_path/"models.db")
    first = plan["hypotheses"][0]
    another = {**deepcopy(first), "ablation": "second", "pretest_status": second}
    if second != "ready":
        another["candidate_artifact"] = None
    definition = {k: another[k] for k in ("family_config_hash", "ablation", "target_markets", "outcome_contract")}
    another["hypothesis_id"] = digest(definition)
    plan["hypotheses"] = sorted([first, another], key=lambda h: h["hypothesis_id"])
    original = plan["test_inventory"][0]
    inventory, rows, distributions = [], [], []
    for i in range(n):
        group, index = i%3, i//3
        decision = HELPERS["CREATED"]+timedelta(days=i//70, minutes=i%70+1)
        event = {**original["event"], "event_key": f"espn:tennis:ATP:match:{i+1}",
                 "scheduled_start": canonical_timestamp(decision+timedelta(hours=2))}
        clock, block = canonical_timestamp(decision), f"test:{i//70}"
        inventory.append({"event": event, "decision_at": clock, "block": block})
        p = (.2, .5, .8)[group]
        outcome = int(index%5 == 0) if group == 0 else int(index%2 == 0) if group == 1 else int(index%5 != 0)
        for market, chance, target in (("winner_a", p, outcome), ("winner_b", 1-p, 1-outcome)):
            rows.append({"event_key": event["event_key"], "market_key": market, "decision_at": clock,
                         "block": block, "p_base": .5, "p_context": chance, "outcome": target})
        distributions.append({"event_key": event["event_key"], "decision_at": clock, "block": block,
                              "outcome_contract": "tennis-completed-winner-v1", "base_logloss": 1., "context_logloss": .9,
                              "tail_policy": "native-winner-bernoulli-log-v1"})
    plan["test_inventory"] = inventory
    values = {h["hypothesis_id"]: tuple(deepcopy(rows)) if h["pretest_status"] == "ready" else () for h in plan["hypotheses"]}
    loss = {h["hypothesis_id"]: tuple(deepcopy(distributions)) if h["pretest_status"] == "ready" else () for h in plan["hypotheses"]}
    return plan, values, loss


def compute(values):
    return api().compare_registered_losses(values[0], results=values[1], distribution_losses=values[2])


def test_all_registered_comparisons_use_one_common_eligible_event_inventory(tmp_path):
    values = inputs(tmp_path)
    plan, results, losses = values
    keys = list(results)
    removed = plan["test_inventory"][0]["event"]["event_key"]
    losses[keys[1]] = tuple(row for row in losses[keys[1]] if row["event_key"] != removed)
    original = deepcopy(values)
    report = compute(values)
    assert values == original
    for comparison in report["hypotheses"].values():
        assert comparison["metrics"]["event_count"] == 209
        assert removed not in {r["event_key"] for r in comparison["metrics"]["event_inventory"]}
        assert any(row["event_key"] == removed for row in comparison["exclusions"])
    assert report["empirical_approval_verified"] is False


@pytest.mark.parametrize("status", ["unsupported", "fit_failed", "insufficient_data", "baseline_control"])
def test_pretest_nonready_remains_in_bh_without_erasing_ready_population(tmp_path, status):
    from model_loss_statistics import benjamini_hochberg_q_values
    report = compute(inputs(tmp_path, second=status))
    ready = next(row for row in report["hypotheses"].values() if row["pretest_status"] == "ready")
    absent = next(row for row in report["hypotheses"].values() if row["pretest_status"] == status)
    assert ready["metrics"]["event_count"] == 210
    assert absent["metrics"] is None and absent["p_value"] == 1.
    assert absent["failures"]
    expected = benjamini_hochberg_q_values({key: row["p_value"] for key, row in report["hypotheses"].items()})
    assert report["q_values"] == expected


def test_counts_are_events_not_two_winner_markets(tmp_path):
    report = compute(inputs(tmp_path, n=199))
    assert all(row["metrics"]["event_count"] == 199 and "insufficient-events" in row["failures"]
               for row in report["hypotheses"].values())


@pytest.mark.parametrize("mutation", ["missing", "unknown", "nonready-results", "different-outcome", "different-base",
                                      "different-base-density", "unfrozen-event", "wrong-decision", "wrong-policy", "duplicate-density"])
def test_registry_or_pairing_mismatch_is_not_silently_discarded(tmp_path, mutation):
    plan, results, losses = inputs(tmp_path, second="unsupported" if mutation == "nonready-results" else "ready")
    keys = list(results)
    if mutation == "missing":
        del results[keys[1]]
    elif mutation == "unknown":
        losses["f"*64] = ()
    elif mutation == "nonready-results":
        absent = next(h["hypothesis_id"] for h in plan["hypotheses"] if h["pretest_status"] == "unsupported")
        ready = next(key for key in results if key != absent)
        results[absent] = deepcopy(results[ready])
    elif mutation in {"different-outcome", "different-base", "unfrozen-event", "wrong-decision"}:
        changed = list(deepcopy(results[keys[1]]))
        field, value = {"different-outcome": ("outcome", 1-changed[0]["outcome"]),
                        "different-base": ("p_base", .4), "unfrozen-event": ("event_key", "espn:tennis:ATP:match:999"),
                        "wrong-decision": ("decision_at", "2026-09-01T23:00:00.000000Z")}[mutation]
        changed[0][field] = value
        results[keys[1]] = tuple(changed)
    else:
        changed = list(deepcopy(losses[keys[1]]))
        if mutation == "different-base-density":
            changed[0]["base_logloss"] = .5
        elif mutation == "wrong-policy":
            changed[0]["tail_policy"] = "epsilon"
        else:
            changed.append(deepcopy(changed[0]))
        losses[keys[1]] = tuple(changed)
    with pytest.raises(ContextContractError):
        compute((plan, results, losses))


def test_missing_target_removes_whole_event_from_every_ready_variant(tmp_path):
    values = inputs(tmp_path)
    key = next(iter(values[1]))
    values[1][key] = values[1][key][1:]
    report = compute(values)
    assert all(h["metrics"]["event_count"] == 209 for h in report["hypotheses"].values())
    assert any(e["reason"] == "missing-target-markets" for h in report["hypotheses"].values() for e in h["exclusions"])


def test_ready_empty_output_is_reported_as_failed_not_relabelled_unsupported(tmp_path):
    values = inputs(tmp_path)
    key = next(iter(values[1]))
    values[1][key], values[2][key] = (), ()
    report = compute(values)
    assert report["hypotheses"][key]["pretest_status"] == "ready"
    assert report["hypotheses"][key]["failures"]
    assert all(h["metrics"]["event_count"] == 0 for h in report["hypotheses"].values())


def test_other_predeclared_population_has_its_own_cohort_not_empty_atp_intersection(tmp_path):
    plan, results, losses = inputs(tmp_path)
    old_key = plan["hypotheses"][1]["hypothesis_id"]
    config = deepcopy(plan["family_configs"][0])
    config["population"]["tours"] = ["WTA"]
    config["population"]["competitions"] = ["espn:WTA:tournament:189-2026"]
    plan["family_configs"] = sorted([*plan["family_configs"], config], key=digest)
    hypothesis = plan["hypotheses"][1]
    hypothesis["family_config_hash"] = digest(config)
    definition = {k: hypothesis[k] for k in ("family_config_hash", "ablation", "target_markets", "outcome_contract")}
    new_key = hypothesis["hypothesis_id"] = digest(definition)
    plan["hypotheses"].sort(key=lambda h: h["hypothesis_id"])
    native = lambda value: value.replace(":ATP:", ":WTA:")
    for original in list(plan["test_inventory"]):
        item = deepcopy(original)
        item["event"].update({field: native(item["event"][field])
                             for field in ("event_key", "home_id", "away_id", "competition")})
        item["event"]["tour"] = "WTA"
        plan["test_inventory"].append(item)
    plan["test_inventory"].sort(key=lambda r: (r["decision_at"], r["event"]["event_key"]))
    results[new_key] = tuple({**r, "event_key": native(r["event_key"])} for r in results.pop(old_key))
    losses.pop(old_key)
    losses[new_key] = ()
    report = compute((plan, results, losses))
    assert report["hypotheses"][new_key]["metrics"]["event_count"] == 0
    assert next(row for key, row in report["hypotheses"].items() if key != new_key)["metrics"]["event_count"] == 210
    assert len({h["cohort_hash"] for h in report["hypotheses"].values()}) == 2


def test_populated_baseline_control_is_descriptive_and_cannot_gain_approval(tmp_path):
    plan, results, losses = inputs(tmp_path, second="baseline_control")
    control = next(h["hypothesis_id"] for h in plan["hypotheses"] if h["pretest_status"] == "baseline_control")
    ready = next(key for key in results if key != control)
    results[control] = tuple({**r, "p_context": r["p_base"]} for r in results[ready][2:])
    losses[control] = tuple({**r, "context_logloss": r["base_logloss"]} for r in losses[ready][1:])
    report = compute((plan, results, losses))
    assert report["hypotheses"][ready]["metrics"]["event_count"] == 210
    row = report["hypotheses"][control]
    assert row["metrics"]["event_count"] == 209
    assert row["metrics"]["mean_advantage"] == 0 and row["metrics"]["distribution_delta"] == 0
    assert row["p_value"] == 1 and report["q_values"][control] == 1
    assert "pretest-status:baseline_control" in row["failures"]
    assert report["empirical_approval_verified"] is False


@pytest.mark.parametrize("source,field,value", [
    ("results", "p_context", float("nan")), ("results", "p_context", True),
    ("results", "outcome", 1.), ("results", "outcome", -1),
    ("results", "p_base", -1), ("results", "p_context", 1.01),
    ("results", "extra", "odds"), ("results", "block", "test:01"),
    ("losses", "base_logloss", float("inf")), ("losses", "context_logloss", True),
    ("losses", "context_logloss", -.001), ("losses", "block", "test:1"),
    ("losses", "decision_at", "2026-09-01T00:01:00"), ("losses", "extra", 1),
])
def test_malformed_rows_do_not_disappear_through_shared_cohort_exclusion(tmp_path, source, field, value):
    values = inputs(tmp_path)
    first, second = list(values[1])
    # Make event1 ineligible in the other variant first. Its own bad row still
    # must be validated before the later intersection would remove that event.
    values[2][second] = values[2][second][1:]
    values[1 if source == "results" else 2][first][0][field] = value
    with pytest.raises(ContextContractError):
        compute(values)


@pytest.mark.parametrize("target", ["results", "losses"])
def test_baseline_control_cannot_contain_an_effect(tmp_path, target):
    values = inputs(tmp_path, second="baseline_control")
    plan, results, losses = values
    control = next(h["hypothesis_id"] for h in plan["hypotheses"] if h["pretest_status"] == "baseline_control")
    ready = next(key for key in results if key != control)
    results[control] = tuple({**r, "p_context": r["p_base"]} for r in results[ready])
    losses[control] = tuple({**r, "context_logloss": r["base_logloss"]} for r in losses[ready])
    if target == "results":
        results[control][0]["p_context"] = .4
    else:
        losses[control][0]["context_logloss"] = .5
    with pytest.raises(ContextContractError):
        compute(values)


def test_provider_input_order_does_not_change_chronological_metrics_or_bh(tmp_path):
    values = inputs(tmp_path)
    original = compute(values)
    for mapping in values[1:]:
        for key in mapping:
            mapping[key] = tuple(reversed(mapping[key]))
    assert compute(values) == original


def test_no_cases_or_labels_from_io_and_no_approval_despite_good_synthetic_metrics(tmp_path, monkeypatch):
    values = inputs(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("pure registered metrics attempted source/storage I/O")
    import model_artifacts
    monkeypatch.setattr(model_artifacts, "load_artifact", forbidden)
    monkeypatch.setattr(model_artifacts, "put_artifact", forbidden)
    report = compute(values)
    assert report["empirical_approval_verified"] is False
    assert "approved" not in report and "approval_hash" not in report
    assert all(h["metrics"]["relative_improvement"] > .02 for h in report["hypotheses"].values())
