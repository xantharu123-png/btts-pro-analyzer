"""Frozen-registry statistical assembly, not empirical activation authority.

These pure mechanics accept already resolved/scored inputs. They cannot prove
the original source receipts, replay, fit, local opening or complete case pool.
The owning evaluator must establish those separately; no approval is emitted.
Malformed input is an error even if its event would later leave the cohort.
"""
from __future__ import annotations

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, event_in_population,
    require_number, require_object,
)
from context_models.distribution_losses import distribution_policy
from context_models.experiments import validate_experiment
from context_models.validation import event_loss_coverage, paired_cohort_metrics
from model_loss_statistics import benjamini_hochberg_q_values


_LOSS_FIELDS = {"event_key", "decision_at", "block", "outcome_contract",
                "base_logloss", "context_logloss", "tail_policy"}
_COHORT_FIELDS = ("sport", "family", "population", "coverage", "target_markets",
                  "outcome_contract", "base_versions")


def _membership(row, inventory):
    key = row["event_key"]
    if type(key) is not str or key not in inventory:
        raise ContextContractError("loss event is outside the frozen family inventory")
    if type(row["decision_at"]) is not str:
        raise ContextContractError("loss decision must be an aware JSON timestamp")
    decision = canonical_timestamp(row["decision_at"])
    if (decision, row["block"]) != (inventory[key]["decision_at"], inventory[key]["block"]):
        raise ContextContractError("loss decision or block differs from the frozen event")


def _distributions(values, inventory, *, family, contract):
    if type(values) is not tuple:
        raise ContextContractError("distribution inventory must be an explicit tuple")
    owning_contract, policy = distribution_policy(family)
    if owning_contract != contract:
        raise ContextContractError("frozen contract differs from the owning distribution")
    by_event = {}
    for row in values:
        require_object(row, _LOSS_FIELDS, label="registered distribution loss")
        _membership(row, inventory)
        key = row["event_key"]
        if key in by_event:
            raise ContextContractError("duplicate native distribution event")
        if row["outcome_contract"] != contract or row["tail_policy"] != policy:
            raise ContextContractError("distribution loss differs from owning outcome/tail policy")
        # The currently supported owning scorers are discrete probability
        # masses. A future continuous density requires its own explicit law.
        for field in ("base_logloss", "context_logloss"):
            require_number(row[field], field, minimum=0)
        by_event[key] = row
    return by_event, policy


def _same_baseline(group):
    """Compare every overlapping original fact before favorable subsetting."""
    targets, densities = {}, {}
    for item in group:
        for row in item["rows"]:
            key = row["event_key"], row["market_key"]
            facts = row["p_base"], row["outcome"]
            if key in targets and targets[key] != facts:
                raise ContextContractError("comparable variants differ in original base or outcome")
            targets[key] = facts
        for key, row in item["distribution"].items():
            if key in densities and densities[key] != row["base_logloss"]:
                raise ContextContractError("comparable variants differ in original distribution loss")
            densities[key] = row["base_logloss"]


def _exclusions(item, selected):
    complete = {row["event_key"] for row in item["coverage"]["events"]}
    partial = {row["event_key"]: row for row in item["coverage"]["excluded"]}
    exclusions = []
    for key in item["inventory"]:
        if key in selected:
            continue
        if key in partial:
            exclusions.append(dict(partial[key]))
        elif key not in complete:
            exclusions.append({"event_key": key, "reason": "missing-prediction"})
        elif key not in item["distribution"]:
            exclusions.append({"event_key": key, "reason": "missing-distribution"})
        else:
            exclusions.append({"event_key": key, "reason": "outside-shared-ready-cohort"})
    return exclusions


def compare_registered_losses(plan: dict, *, results: dict, distribution_losses: dict) -> dict:
    """Use exact shared event cohorts, then one BH family for the whole registry.

    Ready variants with equal declared population/coverage/base/target contracts
    use the intersection of complete targets AND owning distribution losses.
    Missing variants remain in the registry. Non-ready entries do not erase a
    ready cohort; a ready computation cannot relabel itself after seeing tests.
    Raw rows must be D1/D2-generated, never taken from user/CLI loss claims.
    """
    plan = validate_experiment(plan)
    hypotheses = {h["hypothesis_id"]: h for h in plan["hypotheses"]}
    for value in (results, distribution_losses):
        if type(value) is not dict or set(value) != set(hypotheses):
            raise ContextContractError("every registered hypothesis requires exactly one explicit inventory")
    configs = {digest(c): c for c in plan["family_configs"]}
    groups, prepared = {}, {}
    for key, hypothesis in hypotheses.items():
        config = configs[hypothesis["family_config_hash"]]
        status = hypothesis["pretest_status"]
        rows, losses = results[key], distribution_losses[key]
        if type(rows) is not tuple or type(losses) is not tuple:
            raise ContextContractError("hypothesis inventories must be explicit tuples")
        if status not in {"ready", "baseline_control"} and (rows or losses):
            raise ContextContractError("nonready hypothesis cannot supply final-test predictions")
        inventory = {r["event"]["event_key"]: r for r in plan["test_inventory"]
                     if event_in_population(r["event"], config["population"])}
        coverage = event_loss_coverage(rows, target_markets=tuple(config["target_markets"]))
        for row in rows:
            _membership(row, inventory)
        distributions, policy = _distributions(losses, inventory, family=config["family"],
                                               contract=config["outcome_contract"])
        if status == "baseline_control" and (
                any(r["p_base"] != r["p_context"] for r in rows)
                or any(r["base_logloss"] != r["context_logloss"] for r in losses)):
            raise ContextContractError("baseline control must preserve original predictions and loss")
        item = {"config": config, "hypothesis": hypothesis, "rows": rows,
                "coverage": coverage, "distribution": distributions, "tail_policy": policy,
                "inventory": inventory,
                "eligible": {r["event_key"] for r in coverage["events"]} & set(distributions)}
        prepared[key] = item
        cohort = digest({field: config[field] for field in _COHORT_FIELDS})
        groups.setdefault(cohort, []).append(key)

    output = {}
    for cohort, keys in groups.items():
        members = [prepared[k] for k in keys]
        _same_baseline(members)
        ready = [item for item in members if item["hypothesis"]["pretest_status"] == "ready"]
        shared = set.intersection(*(item["eligible"] for item in ready)) if ready else set()
        for key in keys:
            item = prepared[key]
            config, status = item["config"], item["hypothesis"]["pretest_status"]
            # A control is descriptive only and never constrains ready cases.
            selected = shared if status == "ready" else item["eligible"] if status == "baseline_control" else set()
            metrics = None
            if status == "ready" or (status == "baseline_control" and (item["rows"] or item["distribution"])):
                rows = tuple(r for r in item["rows"] if r["event_key"] in selected)
                losses = tuple(item["distribution"][k] for k in item["inventory"] if k in selected)
                metrics = paired_cohort_metrics(
                    rows, losses, target_markets=tuple(config["target_markets"]),
                    test_blocks=tuple(tuple(b) for b in plan["test_blocks"]),
                    outcome_contract=config["outcome_contract"], tail_policy=item["tail_policy"])
            failures = list(metrics["pre_multiplicity_failures"]) if metrics else []
            if status != "ready":
                failures.append(f"pretest-status:{status}")
            output[key] = {"pretest_status": status, "cohort_hash": cohort,
                           "expected_event_count": len(item["inventory"]),
                           "eligible_event_count": len(item["eligible"]),
                           "metrics": metrics, "exclusions": _exclusions(item, selected),
                           "p_value": metrics["p_value"] if metrics and status == "ready" else 1.,
                           "failures": failures}
    output = {key: output[key] for key in hypotheses}
    q_values = benjamini_hochberg_q_values({key: row["p_value"] for key, row in output.items()})
    for key, row in output.items():
        if q_values[key] > .05:
            row["failures"].append("bh-fdr")
    return {"schema": 1, "policy_version": plan["policy_version"], "hypotheses": output,
            "q_values": q_values, "empirical_approval_verified": False}
