"""Immutable, shared context calculations and explicit baseline selection.

No provider, clock, model fit or market-price input belongs here. A worker
supplies one frozen cutoff and deterministic CPU-only comparison. D2 resolves
the empirical evidence BEFORE this module is called; an envelope's public
content hash verifies transport identity, not the truth of a model approval.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Callable

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, DATA_STATES, MODEL_ROLES,
    canonical_timestamp, digest, event_in_population, require_digest,
    require_list, require_number, require_object, require_text,
    validate_base_distribution, validate_context_approval, validate_context_result,
    validate_effect_artifact, validate_event, validate_feature_vector,
)
from model_artifacts import _connect as _artifact_connect, _decode_object, canonical_bytes


def snapshot_key(
    event: dict, *, base_hash: str, context_refs: tuple[str, ...], feature_version: str,
    feature_hash: str, effect_hash: str | None, decision_at: datetime,
    approval_hash: str | None,
) -> str:
    """Bind the complete input revision, never a reader's tab or current price.

    base_hash is digest(validate_base_distribution(original_base)), not the
    separate global base.model_hash. feature_hash is the digest of the complete
    validated FeatureVector. Callers pass the worker's persisted decision_at on
    every later read; this function never manufactures an implicit 'now'.
    """
    event = validate_event(event)
    require_digest(base_hash, "base hash")
    require_digest(feature_hash, "complete feature hash")
    require_text(feature_version, "feature version", code=True)
    if type(context_refs) is not tuple:
        raise ContextContractError("context refs must be an explicit unique tuple")
    for ref in context_refs:
        require_digest(ref, "context reference")
    if len(set(context_refs)) != len(context_refs):
        raise ContextContractError("context refs must be an explicit unique tuple")
    if effect_hash is not None:
        require_digest(effect_hash, "effect hash")
    if approval_hash is not None:
        require_digest(approval_hash, "approval hash")
        if effect_hash is None:
            raise ContextContractError("approval identity requires its effect identity")
    if not isinstance(decision_at, datetime):
        raise ContextContractError("decision_at must be the shared aware worker datetime")
    return digest({"schema": 1, "event": event, "base_hash": base_hash,
                   "context_refs": sorted(context_refs), "feature_version": feature_version,
                   "feature_hash": feature_hash, "effect_hash": effect_hash,
                   "decision_at": canonical_timestamp(decision_at), "approval_hash": approval_hash})


def _connect(path: Path):
    connection = _artifact_connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""CREATE TABLE IF NOT EXISTS context_snapshots (
            key TEXT PRIMARY KEY NOT NULL,
            payload BLOB NOT NULL,
            payload_digest TEXT NOT NULL
        )""")
        connection.commit()
    except BaseException:
        connection.rollback()
        connection.close()
        raise
    return connection


def _finite_json(value: object) -> None:
    """Reject lossy Python-to-JSON coercions before publishing immutable bytes."""
    if value is None or type(value) in (str, bool):
        return
    if type(value) in (int, float):
        require_number(value, "snapshot number")
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ContextContractError("snapshot JSON keys must be strings")
        for nested in value.values():
            _finite_json(nested)
        return
    if type(value) is list:
        for nested in value:
            _finite_json(nested)
        return
    raise ContextContractError("snapshot must contain only finite actual JSON values")


def _payload_digest(key: str, payload: dict) -> str:
    # Also bind the lookup identity so a valid payload cannot simply be moved
    # to a different input revision without detecting the broken stored record.
    return digest({"key": key, "payload": payload})


def _decode_snapshot(key: str, payload: object, payload_digest: object) -> dict:
    try:
        require_digest(payload_digest, "snapshot payload digest")
        decoded = _decode_object(payload, label="context snapshot")
        _finite_json(decoded)
        if _payload_digest(key, decoded) != payload_digest:
            raise ContextIntegrityError("snapshot payload identity mismatch")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ContextIntegrityError("invalid persisted context snapshot") from exc
    return decoded


def compute_once(path: Path, key: str, compute: Callable[[], dict]) -> dict:
    """Materialize once under A1's trusted-path/transaction rules.

    The callback must be deterministic CPU-only: no network, training, provider
    or database calls. Failure rolls back; a crashed process may recalculate but
    cannot publish partial JSON. Corruption is an error, never a refresh request.
    Caller-visible dictionaries are detached from callback and stored history.
    """
    require_digest(key, "snapshot key")
    if not callable(compute):
        raise ContextContractError("snapshot compute must be callable")
    with closing(_connect(Path(path))) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload, payload_digest FROM context_snapshots WHERE key=?", (key,),
            ).fetchone()
            if existing is not None:
                result = _decode_snapshot(key, *existing)
            else:
                calculated = compute()
                if type(calculated) is not dict:
                    raise ContextContractError("snapshot callback must return a JSON object")
                try:
                    _finite_json(calculated)
                    payload = canonical_bytes(calculated)
                    payload_hash = _payload_digest(key, calculated)
                except (ValueError, TypeError, OverflowError, RecursionError) as exc:
                    raise ContextContractError("snapshot callback did not return canonical finite JSON") from exc
                # Return exactly the persisted representation even on first
                # creation: later mutation of the callback object is harmless.
                result = _decode_snapshot(key, payload, payload_hash)
                connection.execute(
                    "INSERT INTO context_snapshots(key,payload,payload_digest) VALUES (?,?,?)",
                    (key, payload, payload_hash),
                )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return result


def _verified_payload(value: dict, *, kind: str, expected_hash: str | None = None) -> tuple[str, dict]:
    """Check the exact A1 transport supplied by trusted local resolvers."""
    is_approval = kind == "context-approval-v1"
    try:
        require_object(value, {"digest", "kind", "payload"} if is_approval else {"kind", "payload"},
                       label="verified context envelope")
        if value["kind"] != kind:
            raise ContextIntegrityError("wrong verified context artifact kind")
        stated_hash = value["digest"] if is_approval else expected_hash
        require_digest(stated_hash, "verified artifact digest")
        if digest({"kind": kind, "payload": value["payload"]}) != stated_hash:
            raise ContextIntegrityError("verified context artifact hash mismatch")
        validator = validate_context_approval if is_approval else validate_effect_artifact
        payload = validator(value["payload"])
        if canonical_bytes(payload) != canonical_bytes(value["payload"]):
            raise ContextIntegrityError("verified context payload is not canonical")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ContextIntegrityError("invalid verified context artifact") from exc
    return stated_hash, payload


def select_context_result(
    base: dict, comparison: dict | None, *, event: dict, features: dict,
    effect_artifact: dict | None, effect_hash: str | None, approval: dict | None,
    factor_roles: dict, factor_states: dict, limitations: list[str],
) -> dict:
    """Select an already computed distribution, never adjust a prior result.

    B5/B7 own deterministic, coherent comparisons calculated against original
    base.params. This boundary binds their event, cutoff, family and historical
    reference; it does not refit or invent an effect. A numerical model error is
    passed as comparison=None plus a limitation, retaining the valid baseline.
    D2, outside this CPU-only function, resolves reports and empirical approval.
    """
    base = validate_base_distribution(base)
    event = validate_event(event)
    features = validate_feature_vector(features)
    if base["event_key"] != event["event_key"] or features["event_key"] != event["event_key"]:
        raise ContextIntegrityError("context event identities do not match")
    if base["cutoff"] != features["cutoff"]:
        raise ContextIntegrityError("context inputs do not share one decision cutoff")
    if event["sport"] != base["family"].split(":")[0]:
        raise ContextIntegrityError("event and baseline model family do not match")
    esports_comparison = None
    if comparison is not None:
        comparison = validate_base_distribution(comparison)
        for name in ("event_key", "cutoff", "family", "history_refs", "reference_weights"):
            if name == "reference_weights" and base["family"] == "esports:series:winner":
                esports_comparison = comparison["reference_weights"]
                if (comparison["version"] != "esports-context-comparison-v1"
                        or esports_comparison["kind"] != "esports-series-comparison-reference-v1"):
                    raise ContextIntegrityError("esports comparison lacks its owning replay reference")
                for nested, supplied in (("original", base), ("event", event), ("features", features)):
                    if canonical_bytes(esports_comparison[nested]) != canonical_bytes(supplied):
                        raise ContextIntegrityError(f"esports comparison and supplied {nested} differ")
                continue
            if comparison[name] != base[name]:
                raise ContextIntegrityError(f"comparison and original baseline {name} mismatch")
        if set(comparison["markets"]) != set(base["markets"]):
            raise ContextIntegrityError("comparison and baseline market identities mismatch")
        if base["family"] == "tennis:serve" and comparison["params"]["best_of"] != base["params"]["best_of"]:
            raise ContextIntegrityError("context cannot change the baseline tennis match format")

    artifact = None
    if effect_artifact is not None:
        effect_hash, artifact = _verified_payload(effect_artifact, kind="context-effect-v1", expected_hash=effect_hash)
    elif effect_hash is not None or comparison is not None:
        raise ContextIntegrityError("effect/comparison requires its verified artifact")
    if esports_comparison is not None:
        if (artifact is None or canonical_bytes(esports_comparison["effect"]) != canonical_bytes(artifact)
                or digest({"kind": "context-effect-v1", "payload": esports_comparison["effect"]}) != effect_hash):
            raise ContextIntegrityError("esports comparison and actually resolved B3 effect differ")
    approval_digest, approved = (None, None) if approval is None else _verified_payload(approval, kind="context-approval-v1")

    keys = set(features["values"])
    require_object(factor_roles, keys, label="factor roles")
    require_object(factor_states, keys, label="factor states")
    for name in keys:
        if type(factor_roles[name]) is not str or factor_roles[name] not in MODEL_ROLES:
            raise ContextContractError("unknown factor model role")
        if type(factor_states[name]) is not str or factor_states[name] not in DATA_STATES:
            raise ContextContractError("unknown factor data state")
        if factor_states[name] != features["states"][name]:
            raise ContextContractError("factor data state contradicts its actual feature")
        if artifact is not None and name not in artifact["feature_names"] and factor_roles[name] != "not_applied":
            raise ContextContractError("effect does not consume the claimed factor")
    require_list(limitations, "context limitations")
    for limitation in limitations:
        require_text(limitation, "context limitation")
    reasons = list(dict.fromkeys(limitations))
    def note(reason):
        if reason not in reasons:
            reasons.append(reason)

    eligible = artifact is not None
    if event["status"] != "scheduled" or event["scheduled_start"] <= base["cutoff"]:
        eligible = False
        note("context-event-ineligible")
    if artifact is not None:
        if artifact["family"] != base["family"] or not event_in_population(event, artifact["population"]) or (
            artifact["feature_version"] != features["version"] or artifact["coverage"] != features["coverage"]
        ):
            eligible = False
            note("context-effect-scope-mismatch")
        if artifact["training_end"] > base["cutoff"]:
            eligible = False
            note("context-effect-after-cutoff")
        if any(name not in keys or features["states"][name] != "available" for name in artifact["feature_names"]):
            eligible = False
            note("context-features-ineligible")

    approval_applies = False
    if approved is not None:
        common = ("sport", "family", "feature_version", "population", "coverage", "model_variant")
        same_effect = artifact is not None and approved["effect_hash"] == effect_hash
        scope_matches = same_effect and all(approved[name] == artifact[name] for name in common)
        scope_matches = scope_matches and (
            approved["family"] == base["family"] and base["version"] in approved["base_versions"]
            and event_in_population(event, approved["population"])
            and approved["feature_version"] == features["version"] and approved["coverage"] == features["coverage"]
        )
        if not scope_matches:
            note("context-approval-scope-mismatch")
        else:
            if not set(approved["target_markets"]) <= set(base["markets"]):
                raise ContextIntegrityError("approval claims markets outside the bound distribution")
            if approved["evaluated_at"] < artifact["training_end"]:
                raise ContextIntegrityError("approval evaluation precedes its bound effect training")
            if approved["evaluated_at"] > base["cutoff"]:
                note("context-approval-after-cutoff")
            else:
                approval_applies = True

    if not eligible:
        comparison = None
    role = "not_applied" if comparison is None else ("applied" if approval_applies else "experimental")
    used = comparison if role == "applied" else base
    ranks = {"not_applied": 0, "experimental": 1, "applied": 2}
    actual_roles = {
        name: min((factor_roles[name], role), key=ranks.get) if artifact is not None and name in artifact["feature_names"] else "not_applied"
        for name in keys
    }
    result = {
        "event_key": base["event_key"], "base_hash": digest(base), "effect_hash": effect_hash,
        "role": role, "factor_roles": actual_roles, "factor_states": dict(factor_states),
        "feature_refs": features["refs"], "base_params": base["params"],
        "comparison_params": comparison["params"] if comparison is not None else None,
        "used_params": used["params"], "base_markets": base["markets"],
        "comparison_markets": comparison["markets"] if comparison is not None else None,
        "used_markets": used["markets"],
        "delta_pp": {name: 100 * (used["markets"][name] - probability) for name, probability in base["markets"].items()},
        "limitations": reasons, "approval_hash": approval_digest if role == "applied" else None,
        "certified_markets": list(approved["target_markets"]) if role == "applied" else [],
    }
    same_family_artifact = artifact if artifact is not None and artifact["family"] == base["family"] else None
    return validate_context_result(result, family=base["family"], effect_artifact=same_family_artifact)
