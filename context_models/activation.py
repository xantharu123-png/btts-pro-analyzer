"""Scoped D2 evidence resolution, separate from active-manifest publication."""
from __future__ import annotations

from pathlib import Path

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    event_in_population, require_digest, validate_base_distribution, validate_context_approval,
    validate_effect_artifact, validate_event, validate_feature_vector,
)
from context_models.dataset import _artifact, _reader
from context_models.experiments import _artifact_created_at, _load_experiment
from model_artifacts import _load_active, _load_artifact, canonical_bytes

APPROVAL_KIND = "context-approval-v1"


def _approval_payloads(report, *, report_hash, plan):
    """Internal producer AFTER owning recomputation, never a public-row API."""
    from context_models.evaluator import _policy
    statistics = _policy(plan, results={key: tuple(value) for key, value in report["results"].items()},
        distribution_losses={key: tuple(value) for key, value in report["distribution_losses"].items()},
        ready_failures=report["ready_failures"])
    if canonical_bytes(statistics) != canonical_bytes(report["statistics"]):
        raise ContextIntegrityError("reported policy differs from the complete recomputed registry")
    configs = {digest(config): config for config in plan["family_configs"]}
    approvals = []
    for hypothesis in plan["hypotheses"]:
        hid = hypothesis["hypothesis_id"]
        row = statistics["hypotheses"][hid]
        if hypothesis["pretest_status"] != "ready" or row["failures"]:
            continue
        config = configs[hypothesis["family_config_hash"]]
        payload = {"schema": 1, "decision": "approved", "hypothesis_id": hid,
            "experiment_hash": report["experiment_hash"], "report_hash": report_hash,
            "effect_hash": hypothesis["candidate_artifact"], "dataset_hash": report["dataset_hash"],
            "event_identity_hash": report["event_identity_hash"], "code_revision": report["code_revision"],
            "policy_version": report["policy_version"], "evaluated_at": report["evaluated_at"],
            "test_events_hash": digest(row["metrics"]["event_inventory"]),
            **{key: config[key] for key in ("base_versions", "sport", "family", "feature_version", "population",
                                          "coverage", "model_variant", "target_markets", "outcome_contract")}}
        approvals.append(validate_context_approval(payload))
    return approvals


def _verify_approval(connection, approval_hash: str) -> dict:
    """Verify historical A1/B1 evidence on an existing read-only connection.

    No active-slot dependency and no writes. D4 can pass its already verified
    in-memory SQLite image; no source path is opened by this function.
    Full fit/source replay belongs outside per-card CPU snapshot calculations.
    """
    from context_models.evaluator import verify_evaluation
    from context_models.training_contracts import validate_artifact_envelope
    approval_hash = require_digest(approval_hash, "approval identity")
    envelope = validate_artifact_envelope({"digest": approval_hash, **_load_artifact(connection, approval_hash)}, kind=APPROVAL_KIND)
    approval = validate_context_approval(envelope["payload"])
    if canonical_bytes(approval) != canonical_bytes(envelope["payload"]):
        raise ContextIntegrityError("stored approval is not canonical")
    report = verify_evaluation(connection, approval["report_hash"])["payload"]
    plan = _load_experiment(connection, approval["experiment_hash"])
    if (report["experiment_hash"] != approval["experiment_hash"]
            or _artifact_created_at(connection, approval_hash) != approval["evaluated_at"]):
        raise ContextIntegrityError("approval provenance or actual creation clock differs")
    expected = _approval_payloads(report, report_hash=approval["report_hash"], plan=plan)
    if not any(canonical_bytes(approval) == canonical_bytes(row) for row in expected):
        raise ContextIntegrityError("claimed approval is not produced by the complete source-resolved policy")
    effect = validate_effect_artifact(_artifact(connection, approval["effect_hash"], "context-effect-v1",
        latest=plan["created_at"])["payload"])
    if any(effect[key] != approval[key] for key in ("sport", "family", "feature_version", "population", "coverage", "model_variant")):
        raise ContextIntegrityError("approval and actual fitted effect scope differ")
    return envelope


def verify_approval(connection, approval_hash: str) -> dict:
    """Historical no-write/no-active-slot verification on A1/B1 SQLite."""
    import sqlite3
    from model_artifacts import ArtifactIntegrityError
    try:
        return _verify_approval(connection, approval_hash)
    except (ContextContractError, ArtifactIntegrityError, sqlite3.DatabaseError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ContextIntegrityError):
            raise
        raise ContextIntegrityError("stored approval evidence is malformed or unresolved") from exc


def approved_effect(path: Path, *, effect_hash: str, event: dict, features: dict, base: dict) -> dict | None:
    """Actual active approval for this exact effect/scope, otherwise baseline."""
    effect_hash = require_digest(effect_hash, "requested effect")
    event, base, features = validate_event(event), validate_base_distribution(base), validate_feature_vector(features)
    if (event["event_key"] != base["event_key"] or base["event_key"] != features["event_key"]
            or base["cutoff"] != features["cutoff"]):
        raise ContextIntegrityError("approval request does not share its original event/decision")
    if not Path(path).exists():
        return None
    with _reader(path) as connection:
        manifest, slots = _load_active(connection)
        approval_hash = slots.get("context-approval:"+effect_hash)
        if approval_hash is None:
            return None
        # Verify claimed evidence before scope fallback; a corrupt claim must
        # never be disguised as harmless inapplicability.
        envelope = verify_approval(connection, approval_hash)
        approval = envelope["payload"]
        if approval["effect_hash"] != effect_hash or effect_hash not in slots.values():
            raise ContextIntegrityError("active approval is not coupled to its actual requested effect")
        publication = connection.execute("SELECT published_at FROM manifests WHERE digest=?", (manifest,)).fetchone()[0]
        effect = validate_effect_artifact(_artifact(connection, effect_hash, "context-effect-v1", latest=approval["evaluated_at"])["payload"])
        if (canonical_timestamp(publication) > base["cutoff"] or approval["evaluated_at"] > base["cutoff"]
                or event["status"] != "scheduled" or base["cutoff"] >= event["scheduled_start"]
                or base["family"] != approval["family"] or base["version"] not in approval["base_versions"]
                or not event_in_population(event, approval["population"])
                or features["version"] != approval["feature_version"] or features["coverage"] != approval["coverage"]):
            return None
        if not set(approval["target_markets"]) <= set(base["markets"]):
            raise ContextIntegrityError("claimed approval targets are absent from the original base distribution")
        if any(features["states"].get(name) != "available" or not features["refs"].get(name) for name in effect["feature_names"]):
            return None
        # Validate the full original Base/Event reference identity, without
        # actually applying the fitted numerical effect in this resolver.
        if event["sport"] == "football":
            from context_models.football_effect import _checked
        elif event["sport"] == "tennis":
            from context_models.tennis_effect import _prepare as _checked
        else:
            raise ContextIntegrityError("approval has no owning family input validator")
        _checked(base, features, effect, event)
        return envelope
