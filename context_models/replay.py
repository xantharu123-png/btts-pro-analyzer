"""Receipt-bound offline base replay; no backdated live state or activation.

Football v1 reuses the original raw goal mathematics on actual native detail
receipts. It deliberately does not claim legacy per-market calibration parity
or fabricate challenge_stats from provider columns. Tennis state replay remains
unsupported until an owning native-to-state-key source resolver exists.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_list, require_object, validate_base_distribution, validate_event,
)
from context_models.training_contracts import (
    FOOTBALL_RAW_BASE, resolve_identity_map, validate_artifact_envelope,
)


class ReplayUnavailable(ContextContractError):
    """Supported math has no sufficient owning causal source path here."""

    def __init__(self, reason: str, *, status: str = "unsupported"):
        self.reason, self.status = reason, status
        super().__init__(reason)


def replay_code_hashes(sport: str) -> dict[str, str]:
    """Exact repository source bytes of the initial replay/math/proof path."""
    if sport != "football":
        raise ReplayUnavailable("native_to_state_key_source_resolver_unavailable")
    paths = ("challenge_engine.py", "context_sources/football.py", "context_sources/football_native.py",
             "context_sources/outcomes.py", "context_models/contracts.py", "context_models/replay.py",
             "context_models/training_contracts.py", "context_observations.py", "model_artifacts.py")
    root = Path(__file__).resolve().parents[1]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}


def _recipe(envelope: dict, *, sport: str) -> dict:
    envelope = validate_artifact_envelope(envelope, kind="context-base-replay-recipe-v1")
    value = envelope["payload"]
    require_object(value, {"schema", "sport", "family", "base_version", "code_revision", "code_hashes",
                           "input_refs", "target_markets", "state_ref", "calibrator_ref"}, label="base replay recipe")
    if (type(value["schema"]) is not int or value["schema"] != 1 or value["sport"] != sport
            or value["family"] != "football:goals:90min" or value["base_version"] != FOOTBALL_RAW_BASE
            or value["state_ref"] is not None or value["calibrator_ref"] is not None):
        raise ContextContractError("unsupported raw-goal replay recipe or borrowed calibration")
    if type(value["code_revision"]) is not str or re.fullmatch(r"[0-9a-f]{40}", value["code_revision"]) is None:
        raise ContextContractError("replay requires a full declared Git code revision")
    if value["code_hashes"] != replay_code_hashes(sport):
        raise ContextIntegrityError("replay recipe differs from the actual calculation source bytes")
    refs = require_list(value["input_refs"], "replay input refs")
    for ref in refs:
        require_digest(ref, "base input receipt")
    if not refs or refs != sorted(set(refs)):
        raise ContextContractError("replay requires sorted unique actual source receipt refs")
    return envelope


def _selected_native_rows(history, *, decision):
    from context_sources.outcomes import validate_football_base_input
    if type(history) is not tuple:
        raise ContextContractError("replay history must be a frozen B1 tuple")
    latest = {}
    for row in history:
        row = validate_football_base_input(row)
        if row["observed_at"] > decision or row["effective_at"] > decision:
            raise ReplayUnavailable("late_import_is_not_predecision_base_evidence")
        if row["evidence_class"] != "prospective":
            raise ReplayUnavailable("native_base_has_no_owning_archival_publication_resolver")
        earlier = latest.get(row["event_key"])
        if earlier is None or row["observed_at"] > earlier[0]["observed_at"]:
            latest[row["event_key"]] = [row]
        elif row["observed_at"] == earlier[0]["observed_at"] and row["content_digest"] not in {r["content_digest"] for r in earlier}:
            earlier.append(row)
    if any(len(rows) != 1 for rows in latest.values()):
        raise ReplayUnavailable("ambiguous_simultaneous_native_base_revision")
    return tuple(latest[key][0] for key in sorted(latest))


def replay_base_distribution(sport: str, event: dict, history: tuple[dict, ...], *,
                             decision_at: datetime, reconstructed_at: datetime,
                             recipe: dict, identity_map: dict) -> dict:
    """Return separate A1 replay evidence containing an unchanged B1 base.

    ``reconstructed_at`` is the owning offline runner's actual clock, never a
    replacement live state built_at. Its evidence class describes source
    availability; the versioned envelope remains a RECONSTRUCTION, not a past
    forecast. Hashes check bytes, not a caller's truthfulness about ingestion.
    """
    if sport != "football":
        raise ReplayUnavailable("native_to_state_key_source_resolver_unavailable" if sport == "tennis"
                                else "owning_base_replay_family_unavailable")
    import challenge_engine as engine
    from context_models.football_effect import GOAL_KINDS
    from context_sources.football import _detail_event
    from context_sources.football_native import football_native_provenance
    event = validate_event(event)
    decision, actual = canonical_timestamp(decision_at), canonical_timestamp(reconstructed_at)
    if (event["sport"] != sport or event["format"] != "90min" or event["status"] != "scheduled"
            or decision >= event["scheduled_start"] or actual < decision):
        raise ContextContractError("replay event or actual reconstruction clock is not eligible")
    recipe = _recipe(recipe, sport=sport)
    rows = _selected_native_rows(history, decision=decision)
    if sorted(row["digest"] for row in rows) != recipe["payload"]["input_refs"]:
        raise ContextIntegrityError("recipe must identify exactly the latest resolved native input receipts")
    # Selection above validates every supplied receipt and its causal clock.
    # A frozen native identity proof may name an earlier still-valid receipt;
    # only the mathematical recipe/baseline must use the latest revision.
    identities = resolve_identity_map(identity_map, observations=history, event_keys=(event["event_key"],))
    binding = next(row for row in identities["payload"]["bindings"] if row["event_key"] == event["event_key"])
    if any(binding[key] != event[key] for key in ("home_id", "away_id")):
        raise ContextIntegrityError("original event differs from the whole-dataset native mapping")
    target_rows = [row for row in rows if row["event_key"] == event["event_key"]]
    if len(target_rows) != 1:
        raise ReplayUnavailable("missing_predecision_native_target_receipt")
    target = target_rows[0]["payload"]["detail"]
    if _detail_event(target) != event:
        raise ContextIntegrityError("original event schedule/status/scope differs from source receipt")
    past = []
    for row in rows:
        if row is target_rows[0]:
            continue
        raw = row["payload"]["detail"]
        native = _detail_event(raw)
        if native["competition"] != event["competition"]:
            raise ReplayUnavailable("cross_competition_history_needs_a_separate_recipe")
        if native["status"] != "completed" or native["scheduled_start"] >= decision:
            raise ContextContractError("base history contains unfinished or future target inputs")
        past.append(raw)
    specs = {spec.key: spec for spec in engine.MARKET_SPECS if spec.kind in GOAL_KINDS}
    keys = require_list(recipe["payload"]["target_markets"], "replay target markets")
    if (not keys or any(type(key) is not str or key not in specs for key in keys)
            or keys != sorted(set(keys))):
        raise ContextContractError("raw goal replay has an unknown or ambiguous market contract")
    raw_receipts = tuple({"detail": row["payload"]["detail"], "observed_at": row["observed_at"]} for row in rows)
    provenance = football_native_provenance((target, *past), raw_receipts, decision_at=decision_at)
    model = engine._fixture_model(target, past, include_provenance=True, native_provenance=provenance)
    if model is None:
        raise ReplayUnavailable("insufficient_native_history_for_original_goal_model", status="insufficient_data")
    home, away = model["active_lambdas"]
    matrix = engine.score_matrix(home, away)
    base = validate_base_distribution({"version": FOOTBALL_RAW_BASE,
        "model_hash": digest({"recipe_hash": recipe["digest"], "event_hash": digest(event),
                              "event_identity_hash": identities["digest"], "decision_at": decision}),
        "event_key": event["event_key"], "cutoff": decision, "family": "football:goals:90min",
        "params": {"home_lambda": home, "away_lambda": away},
        "markets": {key: engine.market_probability(matrix, specs[key]) for key in keys},
        "history_refs": model["history_refs"], "reference_weights": model["reference_weights"]})
    payload = {"schema": 1, "base": base, "event_hash": digest(event), "recipe_hash": recipe["digest"],
        "input_refs_hash": digest(recipe["payload"]["input_refs"]), "event_identity_hash": identities["digest"],
        "logical_training_cutoff": decision, "reconstructed_at": actual, "evidence_class": "prospective"}
    envelope = {"kind": "context-base-replay-v1", "payload": payload}
    return {"digest": digest(envelope), **deepcopy(envelope)}
