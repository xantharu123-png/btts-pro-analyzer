"""Compact, source-bound opponent comparison alongside a captured ORIGINAL.

This is NOT an activated goal model. It uses only the exact already-frozen
native receipts, keeps the customer's captured distribution untouched, and
references its existing binding/manifest instead of storing history again.
The regularised joint attack/defence fit is one argument, not three votes.
"""
from copy import deepcopy
from datetime import datetime
import hashlib

import model_artifacts as storage
import football_opponent_strength as opponent
from football_original import FootballOriginal
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_object,
)

KIND = "football-opponent-adjusted-comparison-v1"
VERSION = "football-opponent-adjusted-goals-v1"
MAX_PAYLOAD_BYTES = 16_384


def recipe():
    """A distinct frozen recipe; no old calibration or validation is inherited."""
    import challenge_engine as engine
    return {
        "version": VERSION,
        "fit_version": opponent.VERSION,
        "family": "football:goals:90min",
        "history_days": opponent.HISTORY_DAYS,
        "minimum_matches": opponent.MIN_MATCHES,
        "minimum_team_matches": opponent.MIN_TEAM_MATCHES,
        "maximum_matches": opponent.MAX_MATCHES,
        "maximum_teams": opponent.MAX_TEAMS,
        "team_penalty": opponent.TEAM_PENALTY,
        "fit": "joint-regularized-poisson-attack-opponent-defense-home-designation",
        "home_designation": "original-neutral-or-unknown-disables-host-coefficient",
        "calibration": "identity-new-recipe-no-inherited-market-calibrators",
        "score_law": "challenge-score-matrix-25plus-v1",
        "market_catalog_hash": digest([
            {"key": spec.key, "kind": spec.kind, "side": spec.side,
             "threshold": spec.threshold, "low": spec.low, "high": spec.high}
            for spec in engine.GOAL_MARKET_SPECS
        ]),
    }


def _sources(original, binding, receipts):
    """Resolve real clocks/latest revisions, not free fields on result rows."""
    import challenge_engine as engine
    from context_sources.football import _detail_event
    from context_sources.football_native import football_native_provenance
    from context_sources.outcomes import validate_football_base_input
    from context_observations import _check_selected_row
    if type(original) is not FootballOriginal or type(receipts) is not tuple:
        raise ContextContractError("opponent comparison needs a captured original and frozen source tuple")
    packet = original.to_dict()
    require_object(binding, {
        "schema", "source_state", "code_state", "empirical_state", "native_event",
        "decision_at", "captured_at", "original_manifest_digest", "original_logical_digest",
        "code_digest", "prediction_version", "model_contract_signature", "target_record",
        "consumed_receipts", "inspected_receipts", "unresolved",
    }, label="opponent original source binding")
    if (type(binding["schema"]) is not int or binding["schema"] != 1
            or binding["code_state"] != "execution-fingerprint-only"
            or binding["empirical_state"] != "not-evaluated"
            or binding["source_state"] not in {"captured", "partial"}
            or type(binding["unresolved"]) is not dict):
        raise ContextIntegrityError("opponent comparison received an invalid original binding")
    if binding["source_state"] != "captured" or binding["unresolved"]:
        raise opponent.ComparisonUnavailable("native-original-sources-incomplete")
    if (binding["captured_at"] != packet["captured_at"]
            or binding["original_logical_digest"] != hashlib.sha256(original._bytes).hexdigest()
            or any(binding[key] != packet[key] for key in ("prediction_version", "model_contract_signature"))):
        raise ContextIntegrityError("opponent comparison differs from its actual original")
    decision = binding["decision_at"]
    if canonical_timestamp(decision) != decision:
        raise ContextIntegrityError("opponent decision clock is not canonical")
    if (binding["native_event"] != _detail_event(packet["fixture"])
            or decision > packet["captured_at"]):
        raise ContextIntegrityError("opponent comparison is not the same prematch native event")
    if packet["captured_at"] >= binding["native_event"]["scheduled_start"]:
        # A slow but otherwise valid legacy calculation may finish after the
        # kickoff. It is not prospective comparison evidence, but this optional
        # research record must not turn that legacy publication into a crash.
        raise opponent.ComparisonUnavailable("original-finished-after-kickoff")
    expected = {row["ref"] for row in packet["goal_provenance"]["history_refs"]} | {binding["target_record"]}
    if set(binding["consumed_receipts"]) != expected or set(binding["inspected_receipts"]) != expected:
        raise ContextIntegrityError("opponent binding does not cover the captured input union")
    inspected = set()
    for groups in (binding["consumed_receipts"], binding["inspected_receipts"]):
        for refs in groups.values():
            if type(refs) is not list or not refs or refs != sorted(set(refs)):
                raise ContextIntegrityError("opponent source references are incomplete or noncanonical")
            inspected.update(require_digest(ref) for ref in refs)
    by_ref, native = {}, []
    for raw in receipts:
        # freeze_named_receipts returns actual B1 rows; add only the real
        # prospective receipt interpretation, never an earlier publication.
        if ("evidence_class" in raw and raw["evidence_class"] != "prospective"
                or "effective_at" in raw and raw["effective_at"] != raw["observed_at"]
                or raw.get("publication_resolution") is not None):
            raise ContextIntegrityError("opponent source is not an actual prospective receipt")
        row = {**raw, "effective_at": raw["observed_at"],
               "evidence_class": "prospective", "publication_resolution": None}
        _check_selected_row(row)
        validate_football_base_input(row)
        if row["digest"] in by_ref or row["observed_at"] > decision:
            raise ContextIntegrityError("opponent source is duplicated or later than its decision")
        by_ref[row["digest"]] = row
        native.append({"detail": row["payload"]["detail"], "observed_at": row["observed_at"]})
    if set(by_ref) != inspected:
        raise ContextIntegrityError("opponent sources differ from the named frozen dependencies")
    target = packet["fixture"]
    cutoff = datetime.fromisoformat(decision)
    _, league, _, _, _ = opponent._identity(target)
    # Free imported 'result_observed_at' values do not confer source authority.
    original_rows = tuple({key: value for key, value in row.items() if key != "result_observed_at"}
                          for row in opponent._bounded_rows(packet["league_history"]))
    eligible = opponent._matches(original_rows, league, cutoff, target["fixture"]["id"])
    eligible_ids = {row.fixture_id for row in eligible}
    selected = {digest(engine.football_base_history_record(row)): row for row in original_rows
                if row["fixture"]["id"] in eligible_ids}
    target_ref = digest(engine.football_base_history_record(target))
    if target_ref != binding["target_record"]:
        raise ContextIntegrityError("opponent target record differs from its binding")
    selected[target_ref] = target
    records = {ref: engine.football_base_history_record(row) for ref, row in selected.items()}
    provenance = football_native_provenance(tuple(selected.values()), tuple(native), decision_at=cutoff)
    bindings = engine._football_native_bindings(provenance, records, target_ref)
    if set(bindings) != set(selected):
        raise ContextIntegrityError("opponent inputs have no latest matching native receipt")
    history, identities = [], []
    for ref, row in sorted(selected.items()):
        evidence = provenance["records"][ref]["payload"]
        matched = sorted(source["digest"] for source in receipts
                         if source["digest"] in binding["inspected_receipts"].get(ref, ())
                         and source["observed_at"] == evidence["observed_at"])
        if not matched or matched != binding["consumed_receipts"].get(ref):
            raise ContextIntegrityError("opponent consumed receipt differs from the actual latest revision")
        identities.append([ref, matched, evidence["observed_at"], opponent._home_effect_known(row)])
        if ref != target_ref:
            checked = deepcopy(row)
            checked["result_observed_at"] = evidence["observed_at"]
            history.append(checked)
    return target, tuple(history), cutoff, digest(identities)


def prepare_opponent_comparison(original, binding, receipts):
    """One compact new-version all-goal-market comparison, never activation.

    A missing/insufficient cohort raises ComparisonUnavailable. Invalid hashes,
    receipt swaps or future revisions raise integrity errors and must propagate.
    The caller publishes atomically with the original under its existing budget.
    """
    import challenge_engine as engine
    from context_models.football_original_publication import BINDING_KIND
    target, history, cutoff, input_hash = _sources(original, binding, receipts)
    result = opponent.compare_football_goal_strength(target, history, cutoff)
    law = {(home, away): mass for home, away, mass in result.score_law}
    current_recipe = recipe()
    fit_hash = digest({"recipe": current_recipe, "input_hash": input_hash,
                       "teams": result.fit.teams, "coefficients": result.fit.coefficients})
    payload = {
        "schema": 1, "model_version": VERSION, "family": "football:goals:90min",
        "role": "experimental-not-applied", "empirically_qualified": False,
        "original_binding_ref": digest({"kind": BINDING_KIND, "payload": binding}),
        "original_manifest_ref": require_digest(binding["original_manifest_digest"]),
        "original_code_ref": require_digest(binding["code_digest"]),
        "event_key": binding["native_event"]["event_key"], "decision_at": binding["decision_at"],
        "recipe": current_recipe, "input_hash": input_hash, "fit_hash": fit_hash,
        "model_hash": digest({"version": VERSION, "recipe": current_recipe,
                              "input_hash": input_hash, "fit_hash": fit_hash,
                              "executed_code_ref": require_digest(binding["code_digest"])}),
        "training_matches": len(result.fit.matches), "training_teams": len(result.fit.teams),
        "receipt_clock_matches": result.receipt_clock_matches,
        "params": {"home_lambda": result.expected_home_goals, "away_lambda": result.expected_away_goals},
        "markets": {spec.key: engine.market_probability(law, spec) for spec in engine.GOAL_MARKET_SPECS},
    }
    prepared = storage.prepare_artifact(kind=KIND, payload=payload)
    if len(prepared.payload_bytes) > MAX_PAYLOAD_BYTES:
        raise ContextIntegrityError("compact opponent comparison exceeds its fixed payload bound")
    return prepared


def reconstruct_opponent_comparison(connection, binding_ref, *, latest):
    """Read-only owning reconstruction from already stored original/B1 inputs."""
    from context_models.football_training import _load_publication
    from context_observations import _SELECT, _decode_receipt
    binding, original, _ = _load_publication(connection, require_digest(binding_ref),
        latest=canonical_timestamp(latest))
    refs = sorted({ref for values in binding["payload"]["inspected_receipts"].values() for ref in values})
    receipts = []
    for ref in refs:
        raw = connection.execute(_SELECT + " WHERE r.digest=?", (ref,)).fetchone()
        if raw is None:
            raise ContextIntegrityError("opponent comparison is missing an existing native receipt")
        receipts.append(_decode_receipt(raw))
    return prepare_opponent_comparison(original, binding["payload"], tuple(receipts))
