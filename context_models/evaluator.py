"""Owning offline evaluation: actual receipts/cases/fits before policy metrics.

No free loss-row input, force flag, provider call, active-slot publication or
empirical shortcut. Synthetic tests establish this mechanism, not real quality.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_object,
)
from context_models.dataset import _artifact, _prepare, _reader, outcome_revisions, prepare_dataset, resolve_case
from context_models.distribution_losses import DistributionScoringError, paired_distribution_losses
from context_models.evaluation import compare_registered_losses
from context_models.experiments import _artifact_created_at, _openings, _persist, open_test_inventory
from context_models.offset import ContextModelError
from context_models.replay import ReplayUnavailable, replay_code_hashes
from context_models.training import case_market_targets
from context_models.training_contracts import validate_resolved_case
from model_artifacts import _connect, canonical_bytes
from model_loss_statistics import benjamini_hochberg_q_values

EVALUATION_KIND = "context-evaluation-v1"
EVALUATOR_VERSION = "source-resolved-context-evaluator-v1"
REPORT_FIELDS = {"schema", "evaluator_version", "implementation_hashes", "experiment_hash", "dataset_hash",
    "event_identity_hash", "code_revision", "policy_version", "opening_hash", "opened_at", "evaluated_at",
    "config_hashes", "fit_refs", "effect_refs", "case_refs", "observation_refs", "results", "distribution_losses",
    "case_outcomes", "outcome_revision_refs", "training_outcome_revision_refs", "pretest_exclusions", "ready_failures", "statistics"}


def implementation_hashes():
    root = Path(__file__).resolve().parents[1]
    names = set(replay_code_hashes("football")) | {
        "context_models/dataset.py", "context_models/evaluator.py", "context_models/activation.py",
        "context_models/evaluation.py", "context_models/validation.py", "context_models/distribution_losses.py",
        "context_models/training.py", "context_models/training_cases.py", "context_models/experiments.py",
        "context_models/football.py", "context_models/football_effect.py", "context_models/tennis.py",
        "context_models/tennis_effect.py", "context_models/offset.py", "model_loss_statistics.py", "tennis/simulator.py",
    }
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(names)}


def _comparison(base, features, effect, *, event):
    if effect is None:
        return deepcopy(base)
    if event["sport"] == "football":
        from context_models.football_effect import apply_football_effect
        return apply_football_effect(base, features, effect, event=event)
    if event["sport"] == "tennis":
        from context_models.tennis_effect import apply_tennis_effect
        return apply_tennis_effect(base, features, effect, event=event)
    raise ContextContractError("no owning source-resolved comparison family")


def _policy(plan, *, results, distribution_losses, ready_failures):
    """Failure p=1 BEFORE a fresh whole-registry BH, unchanged formula."""
    stats = compare_registered_losses(plan, results=results, distribution_losses=distribution_losses)
    if set(ready_failures) != set(stats["hypotheses"]):
        raise ContextIntegrityError("ready-failure inventory differs from frozen hypotheses")
    for key, row in stats["hypotheses"].items():
        row["failures"] = [reason for reason in row["failures"] if reason != "bh-fdr"]
        if ready_failures[key]:
            if row["pretest_status"] != "ready":
                raise ContextIntegrityError("nonready hypothesis cannot be relabelled a failed-ready fit")
            row["p_value"] = 1.
            row["failures"].append("ready-computation-failure")
    stats["q_values"] = benjamini_hochberg_q_values({key: row["p_value"] for key, row in stats["hypotheses"].items()})
    for key, row in stats["hypotheses"].items():
        if stats["q_values"][key] > .05:
            row["failures"].append("bh-fdr")
    # This helper remains mechanics. The surrounding report binds all sources;
    # approval eligibility is derived only after full recomputation below.
    return stats


def _compute(connection, checked, *, experiment_hash, evaluated_at):
    plan, dataset = checked["plan"], checked["dataset"]
    clock = canonical_timestamp(evaluated_at)
    openings, _ = _openings(connection)
    if experiment_hash not in openings:
        raise ContextIntegrityError("whole frozen inventory must be durably opened before final labels")
    opening_ref, opening = openings[experiment_hash]
    if clock < opening["opened_at"]:
        raise ContextIntegrityError("evaluation cannot precede its original opening")
    configs = {digest(config): config for config in plan["family_configs"]}
    inventory = {r["event"]["event_key"]: r for r in plan["test_inventory"]}
    results = {h["hypothesis_id"]: [] for h in plan["hypotheses"]}
    losses, ready_failures = deepcopy(results), deepcopy(results)
    case_outcomes, pretest_exclusions, outcome_revision_refs = [], [], {}
    for group in dataset["groups"]:
        config_ref = group["family_config_hash"]
        config = configs[config_ref]
        hypotheses = [h for h in plan["hypotheses"] if h["family_config_hash"] == config_ref]
        for missing in group["unavailable_final"]:
            pretest_exclusions.append({"family_config_hash": config_ref, **missing})
        for item in group["final_cases"]:
            header = checked["headers"][item["case_ref"]]["payload"]
            event, base, features = header["event"], header["base"], header["features"]
            key = event["event_key"]
            status = {"family_config_hash": config_ref, "case_ref": item["case_ref"], "event_key": key,
                      "status": "resolved", "reason": None, "outcome_ref": header["outcome_ref"]}
            try:
                resolved = resolve_case(connection, item, config=config, plan=plan, latest=clock)
                outcome = next(row for row in resolved["observations"] if row["digest"] == header["outcome_ref"])
                revision_refs, conflicting = outcome_revisions(connection, outcome, event=event, through=clock)
                outcome_revision_refs[header["outcome_ref"]] = revision_refs
                if conflicting:
                    status.update(status="conflicting", reason="frozen_outcome_superseded_or_conflicting")
                    case_outcomes.append(status)
                    for hypothesis in hypotheses:
                        if hypothesis["pretest_status"] == "ready":
                            ready_failures[hypothesis["hypothesis_id"]].append({"event_key": key, "case_ref": item["case_ref"],
                                "error_type": "FrozenOutcomeConflict", "reason": status["reason"]})
                    continue
                resolved = validate_resolved_case(resolved, config=config)
            except ReplayUnavailable as exc:
                status.update(status=exc.status, reason=exc.reason)
                case_outcomes.append(status)
                continue
            case_outcomes.append(status)
            targets = case_market_targets(resolved, config["target_markets"])
            for hypothesis in hypotheses:
                hid = hypothesis["hypothesis_id"]
                if hypothesis["pretest_status"] not in {"ready", "baseline_control"}:
                    continue
                effect = None if hypothesis["pretest_status"] == "baseline_control" else checked["fits"][config_ref]["artifact"]
                try:
                    comparison = _comparison(base, features, effect, event=event)
                    distribution = paired_distribution_losses(base, comparison, outcome, event=event,
                        block=inventory[key]["block"])
                    market_rows = [{"event_key": key, "decision_at": base["cutoff"], "block": inventory[key]["block"],
                        "market_key": market, "p_base": base["markets"][market], "p_context": comparison["markets"][market],
                        "outcome": targets[market]} for market in config["target_markets"]]
                except (ContextModelError, DistributionScoringError, ArithmeticError) as exc:
                    if hypothesis["pretest_status"] != "ready":
                        raise ContextContractError("original baseline control cannot be scored") from exc
                    ready_failures[hid].append({"event_key": key, "case_ref": item["case_ref"],
                                               "error_type": type(exc).__name__, "reason": str(exc)})
                    continue
                # Commit complete event rows together; no selective targets.
                results[hid].extend(market_rows)
                losses[hid].append(distribution)
    results = {key: tuple(rows) for key, rows in results.items()}
    losses = {key: tuple(rows) for key, rows in losses.items()}
    stats = _policy(plan, results=results, distribution_losses=losses, ready_failures=ready_failures)
    all_items = [item for group in dataset["groups"] for phase in ("training_cases", "final_cases") for item in group[phase]]
    report = {"schema": 1, "evaluator_version": EVALUATOR_VERSION, "implementation_hashes": implementation_hashes(),
        "experiment_hash": experiment_hash, "dataset_hash": plan["dataset_hash"], "event_identity_hash": plan["event_identity_hash"],
        "code_revision": plan["code_revision"], "policy_version": plan["policy_version"],
        "opening_hash": opening_ref, "opened_at": opening["opened_at"], "evaluated_at": clock,
        "config_hashes": sorted(configs), "fit_refs": sorted({g["fit_ref"] for g in dataset["groups"] if g["fit_ref"] is not None}),
        "effect_refs": sorted({ref for fit in checked["fits"].values() if fit is not None for ref in fit["candidate_artifacts"]}),
        "case_refs": sorted({item["case_ref"] for item in all_items}),
        "observation_refs": sorted({ref for item in all_items for ref in item["observation_refs"]}
                                   | {ref for refs in outcome_revision_refs.values() for ref in refs}
                                   | {ref for refs in checked["training_outcome_revision_refs"].values() for ref in refs}),
        "results": {key: list(rows) for key, rows in results.items()},
        "distribution_losses": {key: list(rows) for key, rows in losses.items()},
        "case_outcomes": case_outcomes, "outcome_revision_refs": outcome_revision_refs,
        "training_outcome_revision_refs": checked["training_outcome_revision_refs"],
        "pretest_exclusions": pretest_exclusions, "ready_failures": ready_failures,
        "statistics": stats}
    canonical_bytes(report)
    return report


def _verify_evaluation(connection, report_hash):
    """Recompute historical evidence on a caller's read-only SQLite snapshot."""
    from model_artifacts import _load_artifact
    from context_models.training_contracts import validate_artifact_envelope
    envelope = validate_artifact_envelope({"digest": report_hash, **_load_artifact(connection, report_hash)}, kind=EVALUATION_KIND)
    report = envelope["payload"]
    require_object(report, REPORT_FIELDS, label="source-resolved evaluation")
    if (type(report["schema"]) is not int or report["schema"] != 1 or report["evaluator_version"] != EVALUATOR_VERSION
            or report["implementation_hashes"] != implementation_hashes()):
        raise ContextIntegrityError("evaluation implementation differs from the exact original source proof")
    if canonical_timestamp(report["evaluated_at"]) != report["evaluated_at"] or _artifact_created_at(connection, report_hash) != report["evaluated_at"]:
        raise ContextIntegrityError("evaluation clock differs from its actual A1 insertion")
    checked = _prepare(connection, report["experiment_hash"], evaluated_at=report["evaluated_at"])
    recomputed = _compute(connection, checked, experiment_hash=report["experiment_hash"], evaluated_at=report["evaluated_at"])
    if canonical_bytes(recomputed) != canonical_bytes(report):
        raise ContextIntegrityError("evaluation does not reproduce its original source/fit/loss/policy evidence")
    return envelope


def verify_evaluation(connection, report_hash):
    """Typed integrity failure for any malformed stored evaluation claim."""
    import sqlite3
    from model_artifacts import ArtifactIntegrityError
    try:
        return _verify_evaluation(connection, report_hash)
    except (ContextContractError, ArtifactIntegrityError, sqlite3.DatabaseError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ContextIntegrityError):
            raise
        raise ContextIntegrityError("stored evaluation evidence is malformed or unresolved") from exc


def evaluate_experiment(path: Path, experiment_hash: str, *, evaluated_at: datetime) -> dict:
    """Evaluate only a frozen source-resolved dataset; emit no active manifest.

    The opening is committed separately and survives every subsequent failure.
    The offline writer transaction then prevents a source mutation between the
    second preflight, computation and immutable report insertion.
    """
    if not isinstance(evaluated_at, datetime):
        raise ContextContractError("evaluation needs an actual aware runner clock")
    prepare_dataset(path, experiment_hash, evaluated_at=evaluated_at)
    open_test_inventory(path, experiment_hash, opened_at=evaluated_at)
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            checked = _prepare(connection, experiment_hash, evaluated_at=evaluated_at)
            report = _compute(connection, checked, experiment_hash=experiment_hash, evaluated_at=evaluated_at)
            ref = _persist(connection, kind=EVALUATION_KIND, payload=report, created_at=evaluated_at)
            from context_models.activation import _approval_payloads
            approvals = []
            for payload in _approval_payloads(report, report_hash=ref, plan=checked["plan"]):
                approval_ref = _persist(connection, kind="context-approval-v1", payload=payload, created_at=evaluated_at)
                approvals.append({"digest": approval_ref, "kind": "context-approval-v1", "payload": payload})
            connection.commit()
            return {"digest": ref, "kind": EVALUATION_KIND, "payload": report, "approvals": approvals}
        except BaseException:
            connection.rollback()
            raise
