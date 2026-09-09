"""Closed D1 inputs shared with D2, without training or experiment mutation.

Validation is not empirical approval. A canonical configuration hash binds the
plain returned payload, not an A1 ``kind/payload`` envelope. Source receipts and
resolved cases have separate, explicit identities.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, _names, _sport_json, canonical_timestamp, digest,
    require_digest, require_list, require_number, require_object, require_text,
    validate_coverage, validate_population,
)

FAMILY_CONFIG_FIELDS = frozenset({
    "schema", "sport", "family", "feature_version", "feature_names", "population",
    "coverage", "model_variant", "base_versions", "head_links", "reference_version",
    "preprocessing_artifacts", "groups", "joint_calibration", "target_markets",
    "outcome_contract", "train_end", "tune_end", "alpha_grid",
})
ALPHA_GRID = [0.01, 0.1, 1.0, 10.0, 100.0]
FOOTBALL_RAW_BASE = "football-goals-raw-reference-v1"
FOOTBALL_MODEL = "football-roster-two-head-log-rate-v1"
TENNIS_WINNER_BASE = "tennis-winner-predecision-tour-state-v1"
_FOOTBALL_FEATURE = re.compile(
    r"(home|away)\.(venue|form)_(attack|defense)\.(goals|xg)\.api-football:player:[1-9][0-9]*\Z")


@lru_cache(maxsize=2)
def _serve_catalog(best_of):
    from context_models.tennis_effect import tennis_serve_markets
    return frozenset(tennis_serve_markets({"hold_a": .7, "hold_b": .7, "best_of": best_of}))


def _groups(value, names):
    if type(value) is not dict or not value:
        raise ContextContractError("family groups require an explicit nonempty feature mapping")
    result = {}
    for key, members in value.items():
        _names([key], "factor group")
        members = _names(members, "group features")
        if any(name not in names for name in members) or members != [name for name in names if name in members]:
            raise ContextContractError("group features must preserve the exact artifact order")
        result[key] = members
    if set().union(*(set(members) for members in result.values())) != set(names):
        raise ContextContractError("factor groups must cover every consumed feature")
    return result


def validate_family_config(config: dict) -> dict:
    """Return detached canonical config for the currently implemented families.

    This does not resolve historical rows, fit effects or inspect held-out
    labels. In particular, accepting the serve fitting contract does not claim
    that the current source supplies measured serve successes/trials.
    """
    require_object(config, set(FAMILY_CONFIG_FIELDS), label="family config")
    row = _sport_json(config, label="family config")
    if type(row["schema"]) is not int or row["schema"] != 1:
        raise ContextContractError("unsupported family config schema")
    family = require_text(row["family"], "context family", code=True)
    if family not in {"football:goals:90min", "tennis:winner", "tennis:serve"}:
        raise ContextContractError("no reviewed training law for this family")
    sport = family.split(":")[0]
    if row["sport"] != sport:
        raise ContextContractError("family config sport differs from its law")
    row["population"] = validate_population(row["population"])
    row["coverage"] = validate_coverage(row["coverage"])
    if row["population"]["sport"] != sport:
        raise ContextContractError("family population and sport differ")
    row["feature_names"] = _names(row["feature_names"], "family feature names")
    for field in ("base_versions", "target_markets"):
        row[field] = _names(row[field], field)
        if row[field] != sorted(row[field]):
            raise ContextContractError(f"{field} must be canonical sorted unique names")
    row["groups"] = _groups(row["groups"], row["feature_names"])
    require_object(row["joint_calibration"], {"kind"}, label="joint calibration")
    if row["joint_calibration"] != {"kind": "identity"}:
        raise ContextContractError("legacy separate calibration curves are not a context law")
    if type(row["preprocessing_artifacts"]) is not dict:
        raise ContextContractError("preprocessing must map stable names to artifact hashes")
    for name, ref in row["preprocessing_artifacts"].items():
        _names([name], "preprocessing name")
        require_digest(ref, "preprocessing artifact")
    for key in ("train_end", "tune_end"):
        if type(row[key]) is not str:
            raise ContextContractError("family clocks must be aware ISO strings")
        row[key] = canonical_timestamp(row[key])
    if row["train_end"] >= row["tune_end"]:
        raise ContextContractError("training must precede tuning")
    grid = require_list(row["alpha_grid"], "fixed alpha grid")
    for value in grid:
        require_number(value, "alpha", minimum=0)
    if grid != ALPHA_GRID:
        raise ContextContractError("regularization search must use the predeclared five alphas")
    row["alpha_grid"] = list(ALPHA_GRID)
    if family == "football:goals:90min":
        from challenge_engine import MARKET_SPECS
        from context_models.football_effect import GOAL_KINDS
        if (row["feature_version"] != "football-roster-components-v2"
                or row["reference_version"] != "football-context-reference-v2"
                or row["model_variant"] != FOOTBALL_MODEL
                or row["base_versions"] != [FOOTBALL_RAW_BASE]
                or row["head_links"] != {"home": "log_rate", "away": "log_rate"}
                or row["outcome_contract"] != "football-regulation-ft-v1"
                or row["population"]["formats"] != ["90min"]
                or row["coverage"]["version"] != "football-roster-v1"
                or row["coverage"]["case"] not in {"reported_players", "incomplete", "conflicting",
                                                      "doubtful_scenarios", "reference_unavailable"}):
            raise ContextContractError("unreviewed football fitting/replay law")
        if any(_FOOTBALL_FEATURE.fullmatch(name) is None for name in row["feature_names"]):
            raise ContextContractError("football training consumes only actual B4 component/player columns")
        catalog = {spec.key for spec in MARKET_SPECS if spec.kind in GOAL_KINDS}
    else:
        from context_models.tennis_effect import (
            SERVE_BASE_VERSION, SERVE_VARIANT, WINNER_VARIANT, _COVERAGE_CASES, _FEATURES,
        )
        serve = family == "tennis:serve"
        population = row["population"]
        allowed_formats = {"singles_best_of_3", "singles_best_of_5"} | (set() if serve else {"singles"})
        if (row["feature_version"] != "tennis-performed-load-v2"
                or row["reference_version"] != "tennis-context-reference-v2"
                or row["model_variant"] != (SERVE_VARIANT if serve else WINNER_VARIANT)
                or row["base_versions"] != [SERVE_BASE_VERSION if serve else TENNIS_WINNER_BASE]
                or row["head_links"] != ({"hold_a": "logit", "hold_b": "logit"} if serve else {"winner": "logit"})
                or row["outcome_contract"] != ("tennis-completed-serve-v1" if serve else "tennis-completed-winner-v1")
                or row["preprocessing_artifacts"] or not set(population["formats"]) <= allowed_formats
                or len(population["tours"]) != 1 or population["tours"][0] not in {"ATP", "WTA"}
                or len(population["surfaces"]) != 1 or population["surfaces"][0] not in {"Hard", "Clay", "Grass", "Carpet"}
                or len(population["indoor"]) != 1 or type(population["indoor"][0]) is not bool
                or row["coverage"]["version"] != "tennis-performed-load-coverage-v1"
                or row["coverage"]["case"] not in _COVERAGE_CASES):
            raise ContextContractError("unreviewed or mixed tennis fitting/replay law")
        if any(name not in _FEATURES or (not serve and _FEATURES[name][1] != "delta") for name in row["feature_names"]):
            raise ContextContractError("tennis feature vocabulary violates the owning mirrored law")
        expected_groups = {}
        for name in row["feature_names"]:
            root, side, group = _FEATURES[name]
            expected_groups.setdefault(group, []).append(name)
            counterpart = root + ("_b" if side == "a" else "_a" if side == "b" else "_delta")
            if serve and counterpart not in row["feature_names"]:
                raise ContextContractError("serve configuration lacks a mirrored feature coordinate")
        if row["groups"] != expected_groups:
            raise ContextContractError("tennis groups must retain the B7 workload/recovery mapping")
        catalog = set.intersection(*(set(_serve_catalog(int(fmt[-1]))) for fmt in population["formats"])) if serve else {"winner_a", "winner_b"}
    if not set(row["target_markets"]) <= catalog:
        raise ContextContractError("target market is not in the owning outcome/distribution catalog")
    return deepcopy(row)


def validate_artifact_envelope(value: dict, *, kind: str) -> dict:
    """Check A1 bytes, not provenance supplied by an arbitrary caller."""
    require_object(value, {"digest", "kind", "payload"}, label="resolved A1 artifact")
    require_digest(value["digest"], "artifact digest")
    if value["kind"] != kind:
        raise ContextContractError("resolved artifact has a different kind")
    if digest({"kind": value["kind"], "payload": value["payload"]}) != value["digest"]:
        raise ContextIntegrityError("resolved A1 artifact hash mismatch")
    return deepcopy(value)


def validate_identity_map(envelope: dict) -> dict:
    """Validate the WHOLE dataset map; no name matching or cross-source alias."""
    result = validate_artifact_envelope(envelope, kind="context-native-identity-map-v1")
    payload = result["payload"]
    require_object(payload, {"schema", "policy", "bindings"}, label="dataset native identity map")
    if type(payload["schema"]) is not int or payload["schema"] != 1 or payload["policy"] != "native-source-only-v1":
        raise ContextContractError("unsupported identity resolution policy")
    bindings = require_list(payload["bindings"], "native bindings")
    keys = []
    for binding in bindings:
        require_object(binding, {"event_key", "home_id", "away_id", "source_refs"}, label="native binding")
        key = require_text(binding["event_key"], "native event", code=True)
        if re.fullmatch(r"api-football:football:[1-9][0-9]*", key):
            participant_pattern = r"api-football:team:[1-9][0-9]*"
        elif match := re.fullmatch(r"espn:tennis:(ATP|WTA):match:[1-9][0-9]*", key):
            participant_pattern = rf"espn:tennis:{match[1]}:player:[1-9][0-9]*"
        else:
            raise ContextContractError("unresolved source alias is not a native event")
        for side in ("home_id", "away_id"):
            text = require_text(binding[side], "native participant", code=True)
            if re.fullmatch(participant_pattern, text) is None:
                raise ContextContractError("participant namespace differs from native source/tour")
        if binding["home_id"] == binding["away_id"]:
            raise ContextContractError("native participants must be distinct")
        refs = require_list(binding["source_refs"], "native proof refs")
        for ref in refs:
            require_digest(ref, "native source receipt")
        if not refs or refs != sorted(set(refs)):
            raise ContextContractError("native identity needs sorted unique source receipts")
        keys.append(key)
    if not keys or keys != sorted(set(keys)):
        raise ContextContractError("dataset native events must be nonempty, sorted and unique")
    return result


def resolve_identity_map(envelope: dict, *, observations: tuple[dict, ...],
                         event_keys: tuple[str, ...] | None = None) -> dict:
    """Resolve actual B1 bytes, optionally only an explicitly requested subset.

    Subset resolution retains the full global map hash. Training can thus bind
    a frozen map without opening other events' receipts or final-test labels.
    It never asserts that the unrequested references have been resolved.
    """
    from context_observations import _check_selected_row
    from context_sources.outcomes import validate_football_base_input
    from context_sources.football import _detail_event
    from context_sources.tennis import validate_workload_record
    result = validate_identity_map(envelope)
    if type(observations) is not tuple:
        raise ContextContractError("native resolution needs an immutable B1 receipt inventory")
    by_ref = {}
    for row in observations:
        _check_selected_row(row)
        if row["digest"] in by_ref:
            raise ContextContractError("duplicate physical source receipt")
        by_ref[row["digest"]] = row
    bindings = result["payload"]["bindings"]
    if event_keys is not None:
        if (type(event_keys) is not tuple or not event_keys
                or any(type(key) is not str for key in event_keys)
                or len(set(event_keys)) != len(event_keys)):
            raise ContextContractError("requested native resolution keys must be a nonempty unique tuple")
        if any(key not in {b["event_key"] for b in bindings} for key in event_keys):
            raise ContextContractError("event is missing from the global native identity map")
        bindings = [b for b in bindings if b["event_key"] in event_keys]
    for binding in bindings:
        for ref in binding["source_refs"]:
            row = by_ref.get(ref)
            if row is None or row["event_key"] != binding["event_key"]:
                raise ContextIntegrityError("native identity proof receipt is missing or belongs to another event")
            if row["sport"] == "football":
                validate_football_base_input(row)
                event = _detail_event(row["payload"]["detail"])
                if any(event[key] != binding[key] for key in ("home_id", "away_id")):
                    raise ContextIntegrityError("native source orientation differs from dataset identity")
            elif row["sport"] == "tennis" and row["kind"] == "performed_match":
                payload = validate_workload_record(row)
                if {payload["player_id"], payload["opponent_id"]} != {binding["home_id"], binding["away_id"]}:
                    raise ContextIntegrityError("native tennis participants differ from dataset identity")
            else:
                raise ContextContractError("there is no owning native identity resolver for this receipt")
    return result
