"""C3 internal hockey mechanics; source qualification and D1/D2 stay separate.

The reference is measured contributing-game composition, NOT a sensitivity
or decomposition of the nonlinear, constrained original Poisson optimizer.
"""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
import math
import re

import numpy as np
from scipy.stats import skellam

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_bytes, canonical_timestamp,
    digest, require_digest, require_number, require_object, require_text, validate_event,
    validate_base_distribution, validate_feature_vector, validate_effect_artifact, event_in_population,
)
from context_models.offset import ContextModelError, adjust_parameters, offset_delta

FAMILY = "ice_hockey:regulation_goals"
BASE_VERSION = "hockey-original-poisson-v1"
REFERENCE_KIND = "hockey-original-poisson-reference-v1"
REFERENCE_VARIANT = "hockey-observed-contributing-exposure-v1"
FEATURE_VERSION = "hockey-observed-exposure-load-v1"
MODEL_VARIANT = "hockey-role-mirrored-poisson-context-v1"
COMPARISON_VERSION = "hockey-context-comparison-v1"
COMPARISON_KIND = "hockey-context-comparison-reference-v1"
FORMATS = {"nhl_reg60_regular_ot_so": 2, "nhl_reg60_playoff_ot": 3}
MARKETS = frozenset({"home_reg", "draw_reg", "away_reg", "home_inclusive", "away_inclusive"})


def hockey_distribution(home_rate, away_rate, overtime_home_rate):
    """One unchanged Skellam law and fixed original conditional OT conversion."""
    for rate in (home_rate, away_rate):
        if require_number(rate, "hockey regulation rate", minimum=0) <= 0:
            raise ContextModelError("hockey rate must be strictly positive")
        if type(rate) is int and int(float(rate)) != rate:
            raise ContextModelError("hockey rate integer is not exactly representable")
    require_number(overtime_home_rate, "original overtime probability", minimum=0, maximum=1)
    try:
        home = float(skellam.sf(0, home_rate, away_rate))
        draw = float(skellam.pmf(0, home_rate, away_rate))
        away = float(skellam.cdf(-1, home_rate, away_rate))
        inclusive = home + draw*overtime_home_rate
    except (ArithmeticError, ValueError, RuntimeError) as exc:
        raise ContextModelError("hockey distribution failed numerically") from exc
    values = {"home_reg": home, "draw_reg": draw, "away_reg": away,
              "home_inclusive": inclusive, "away_inclusive": 1.-inclusive}
    if (any(not math.isfinite(value) or not 0 <= value <= 1 for value in values.values())
            or not math.isclose(math.fsum((home, draw, away)), 1., rel_tol=0, abs_tol=1e-12)):
        raise ContextModelError("hockey distribution mass is not representable")
    return values


def native_id(value, kind):
    if type(value) is not str or re.fullmatch(rf"nhl:ice_hockey:{kind}[1-9][0-9]*", value) is None:
        raise ContextContractError("unknown native NHL identity")
    return value


def hockey_event(value):
    event = validate_event(value)
    if event["sport"] != "ice_hockey" or event["competition"] != "nhl" or event["format"] not in FORMATS:
        raise ContextContractError("unreviewed NHL event population")
    native_id(event["event_key"], "")
    for side in ("home_id", "away_id"):
        native_id(event[side], "team:")
    return event


def hockey_scope(value, event):
    """Explicit source metadata, never season/game type inferred from a name."""
    require_object(value, {"season", "game_type", "neutral_site", "rule_version"}, label="NHL scope")
    if (type(value["season"]) is not int or value["season"] != 20252026
            or type(value["game_type"]) is not int or value["game_type"] != FORMATS[event["format"]]
            or type(value["neutral_site"]) is not bool or value["rule_version"] != "nhl-2025-26-rule84"):
        raise ContextContractError("NHL actual season/phase/neutral/rule evidence unsupported")
    return dict(value)


_RAW_FIELDS = frozenset({"provider", "source", "competition_id", "league_id", "competition", "league", "tournament",
    "provider_event_id", "event_id", "game_id", "match_id", "id", "starts_at", "start_time", "scheduled_at",
    "home_team_id", "away_team_id", "team1_id", "team2_id", "home_team", "away_team", "team1", "team2",
    "neutral_site", "game_type", "status", "sport", "result_observed_at", "observed_at", "completed_at",
    "winner_side", "home_score_final", "away_score_final", "home_score", "away_score", "result_scope",
    "last_period_type", "season", "context_rule_version"})


def _project(raw):
    if not isinstance(raw, Mapping):
        raise ContextContractError("NHL original sport records must be mappings")
    result = {}
    for key in sorted(_RAW_FIELDS.intersection(raw)):
        value = raw[key]
        if isinstance(value, datetime):
            value = value.isoformat()
        if value is not None and type(value) not in (str, bool, int, float):
            raise ContextContractError("NHL original record has non-JSON sport values")
        if type(value) in (int, float):
            require_number(value, "original NHL sport record")
        result[key] = value
    return result


def _legacy_json(value):
    row = asdict(value)
    # The unchanged optimizer returns NumPy float64 coefficients. Export the
    # same scalar values as actual JSON floats, not NumPy objects inside lists.
    # Their canonical serialized bytes and the original fit remain unchanged.
    return {key: [float(item) for item in val] if key == "coefficients" else
            val.isoformat() if isinstance(val, datetime) else list(val) if isinstance(val, tuple) else val
            for key, val in row.items()}


def _integer_identity(value):
    if type(value) not in (int, str) or re.fullmatch(r"[1-9][0-9]*", str(value)) is None:
        raise ContextContractError("unresolved NHL native integer")
    return str(value)


def _native_projection(row, scope, *, target=False):
    """Source-bound identity, not the legacy name/casefold fallback."""
    import sports_prematch as old
    provider = row.get("provider") or row.get("source")
    if type(provider) is not str or provider not in ("NHL", "nhl") or old._competition(row) != "nhl":
        raise ContextContractError("unresolved NHL source/competition")
    event_id = _integer_identity(row.get("provider_event_id") or row.get("event_id") or row.get("id"))
    home = _integer_identity(row.get("home_team_id"))
    away = _integer_identity(row.get("away_team_id"))
    if home == away:
        raise ContextContractError("NHL participants coincide")
    if (type(row.get("season")) is not int or row["season"] != scope["season"]
            or type(row.get("game_type")) is not int or row["game_type"] != scope["game_type"]
            or type(row.get("neutral_site")) is not bool
            or row.get("context_rule_version") != scope["rule_version"]):
        raise ContextContractError("actual NHL season/rules/neutral metadata unavailable")
    if target and row["neutral_site"] != scope["neutral_site"]:
        raise ContextContractError("target NHL neutral evidence differs")
    return event_id, "nhl:ice_hockey:team:"+home, "nhl:ice_hockey:team:"+away


def _fit_recipe(fitted):
    t = len(fitted.teams)
    return {"version": "legacy-constrained-poisson-sports-prematch-v1", "optimizer": "L-BFGS-B",
        "maxiter": 100, "ftol": 1e-9, "team_penalty": 5., "nuisance_penalty": 0.,
        "bounds": [[-4., 4.]]*(2*t)+[[-5., 5.], [-3., 3.]],
        "initialization": "zero-except-log-max-mean-goals-0.01",
        "design": "ordered-home-away-attack-defense-intercept-half-home",
        "regulation_outcomes": "legacy-one-winning-goal-subtraction-not-observed-period-totals"}


def _original_parts(target, history, cutoff):
    import sports_prematch as old
    identity, missing = old._identity("ice_hockey", target, cutoff)
    if identity is None or missing:
        return None
    matches = old._normalise_history("ice_hockey", identity, history, cutoff)
    if not old._enough_for_event(matches, identity.home, identity.away):
        return None
    fitted = old._fit("ice_hockey", matches)
    predicted = None if fitted is None else old._predict(fitted, identity.home, identity.away, identity.neutral)
    if predicted is None or not math.isfinite(predicted[0]) or not 0 < predicted[0] < 1:
        return None
    probability, details = predicted
    params = {"home_lambda": details["expected_home_goals"], "away_lambda": details["expected_away_goals"],
              "overtime_home_probability": details["overtime_home_rate"]}
    markets = hockey_distribution(params["home_lambda"], params["away_lambda"], params["overtime_home_probability"])
    if markets["home_inclusive"] != probability:
        raise ContextIntegrityError("original NHL law changed")
    canonical = {"version": old.MODEL_VERSION, "sport": "ice_hockey", "identity": _legacy_json(identity),
                 "matches": [_legacy_json(match) for match in matches]}
    model_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return identity, matches, fitted, params, markets, model_hash


def _make_reference(target, history, cutoff, event, scope, parts):
    import sports_prematch as old
    scope = hockey_scope(scope, event)
    native = _native_projection(target, scope, target=True)
    identity, matches, fitted, _, _, _ = parts
    if (native != (event["event_key"].rsplit(":", 1)[1], event["home_id"], event["away_id"])
            or canonical_timestamp(identity.start) != event["scheduled_start"] or event["status"] != "scheduled"):
        raise ContextContractError("source target NHL event/schedule differs")
    # Establish complete causal native identity before the old natural-key dedup.
    latest = {}
    for raw in history:
        if old._text(raw.get("provider") or raw.get("source")) != identity.provider:
            continue
        observed = old._time(raw.get("result_observed_at") or raw.get("observed_at"))
        key = old._text(raw.get("provider_event_id") or raw.get("event_id") or raw.get("id"))
        if observed is None or observed >= min(cutoff, identity.start) or not key or key == identity.event_id:
            continue
        previous = latest.get(key)
        if previous is None or observed > previous[0]: latest[key] = (observed, [raw])
        elif observed == previous[0]: previous[1].append(raw)
    natural = {}
    for _, candidates in latest.values():
        for raw in candidates:
            one = old._normalise_history("ice_hockey", identity, (raw,), cutoff)
            if one:
                m = one[0]
                natural.setdefault((m.start, m.home, m.away), set()).add(m.event_id)
    refs, selected = [], []
    for match in matches:
        if len(natural.get((match.start, match.home, match.away), ())) != 1:
            raise ContextContractError("unresolved natural-key NHL aliases")
        candidates = latest[match.event_id][1]
        proven = []
        for raw in candidates:
            key, home, away = _native_projection(raw, scope)
            if (key != match.event_id or home.rsplit(":", 1)[1] != match.home.removeprefix("id:")
                    or away.rsplit(":", 1)[1] != match.away.removeprefix("id:")):
                raise ContextContractError("legacy folded identity is not a native NHL join")
            proven.append(raw)
        # Identical legacy scores do not merge contradictory native metadata.
        records = {digest(raw): raw for raw in proven}
        if len(records) != 1:
            raise ContextContractError("conflicting native NHL source revisions")
        record = next(iter(records.values()))
        ref = digest(record)
        refs.append({"ref": ref, "source": "nhl", "source_event_id": match.event_id,
            "native_event_key": "nhl:ice_hockey:"+match.event_id, "event_join": "verified_native", "roster_join": "unresolved"})
        selected.append({**_legacy_json(match), "ref": ref})
    reference = {"schema": 1, "kind": REFERENCE_KIND, "variant": REFERENCE_VARIANT,
        "event": event, "scope": scope, "cutoff": canonical_timestamp(cutoff),
        "raw_target": target, "raw_history": list(history), "selected": selected,
        "fit": _legacy_json(fitted), "recipe": _fit_recipe(fitted), "model_version": old.MODEL_VERSION,
        "binding_hash": digest({"event": event, "scope": scope, "raw_target": target})}
    return reference, refs


def export_hockey_base(target, history, cutoff, *, context_event, scope=None):
    """Exact original parameters with optional proven native sample provenance."""
    from context_models.contracts import validate_base_distribution
    event = hockey_event(context_event)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("hockey decision requires aware datetime")
    decision = datetime.fromisoformat(canonical_timestamp(cutoff))
    if type(history) is not tuple:
        raise ContextContractError("original NHL history must be a tuple")
    parts = _original_parts(target, history, decision)
    if parts is None:
        return None  # Preserve the legacy absent neutral/OT/incomplete-model state.
    identity = parts[0]
    if (identity.provider != "nhl" or identity.competition != "nhl"
        or event["event_key"] != "nhl:ice_hockey:"+identity.event_id
        or canonical_timestamp(identity.start) != event["scheduled_start"] or event["status"] != "scheduled"):
        raise ContextIntegrityError("known original NHL event/schedule does not match context")
    if identity.variant != str(FORMATS[event["format"]]):
        raise ContextIntegrityError("known original NHL game type differs from context format")
    for side in ("home", "away"):
        # Bind the ID actually selected by the unchanged legacy precedence,
        # including team1_id/team2_id. Names never establish a native join;
        # this contradiction guard does not certify missing roster provenance.
        model_team = re.fullmatch(r"id:([1-9][0-9]*)", getattr(identity, side))
        if model_team is not None:
            if event[side+"_id"] != "nhl:ice_hockey:team:"+model_team.group(1):
                raise ContextIntegrityError("known original NHL team orientation differs")
    reference, refs = {"schema": 1, "kind": "unavailable", "reason": "unqualified-native-hockey-reference"}, []
    try:
        if len(history) > 20000:
            raise ContextContractError("NHL reference transport inventory exceeds the declared bound")
        projected_target = _project(target)
        projected_history = tuple(_project(raw) for raw in history)
        projected_parts = _original_parts(projected_target, projected_history, decision)
        if projected_parts != parts:
            raise ContextContractError("price-free projection differs from original NHL computation")
        reference, refs = _make_reference(projected_target, projected_history, decision, event, scope, parts)
    except (ContextContractError, KeyError, TypeError, ValueError):
        pass
    result = {"version": BASE_VERSION, "model_hash": parts[-1], "event_key": event["event_key"],
        "cutoff": canonical_timestamp(decision), "family": FAMILY, "params": parts[3], "markets": parts[4],
        "history_refs": refs, "reference_weights": reference}
    return validate_base_distribution(result)


def validate_hockey_reference(value, history_refs):
    if type(value) is dict and value.get("kind") == COMPARISON_KIND:
        require_object(value, {"schema", "kind", "original", "features", "effect", "event"}, label="closed hockey comparison")
        if type(value["schema"]) is not int or value["schema"] != 1:
            raise ContextContractError("unsupported hockey comparison reference schema")
        prepared = _prepare(value["original"], value["features"], value["effect"], value["event"])
        if history_refs != prepared[0]["history_refs"]:
            raise ContextIntegrityError("hockey comparison changed its original history")
        return deepcopy(value)
    required = {"schema", "kind", "variant", "event", "scope", "cutoff", "raw_target", "raw_history", "selected",
                "fit", "recipe", "model_version", "binding_hash"}
    require_object(value, required, label="original constrained NHL reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != REFERENCE_KIND:
        raise ContextContractError("unreviewed NHL reference schema")
    event = hockey_event(value["event"])
    decision = datetime.fromisoformat(canonical_timestamp(value["cutoff"]))
    if type(value["raw_history"]) is not list or len(value["raw_history"]) > 20000:
        raise ContextContractError("NHL replay inventory must be a bounded explicit list")
    target, history = _project(value["raw_target"]), tuple(_project(raw) for raw in value["raw_history"])
    if target != value["raw_target"] or list(history) != value["raw_history"]:
        raise ContextContractError("NHL replay has undeclared record fields")
    parts = _original_parts(target, history, decision)
    if parts is None:
        raise ContextIntegrityError("NHL original sample no longer computes")
    expected, expected_refs = _make_reference(target, history, decision, event, value["scope"], parts)
    if canonical_bytes(expected) != canonical_bytes(value) or canonical_bytes(history_refs) != canonical_bytes(expected_refs):
        raise ContextIntegrityError("NHL original constrained fit/reference does not replay")
    return deepcopy(value)


def validate_hockey_base_reference(base):
    reference = base["reference_weights"]
    if reference["kind"] == "unavailable":
        if base["version"] != BASE_VERSION:
            raise ContextContractError("unavailable NHL reference is not a fitted comparison")
        return
    if reference["kind"] == COMPARISON_KIND:
        return _validate_comparison_base(base)
    parts = _original_parts(reference["raw_target"], tuple(reference["raw_history"]),
                            datetime.fromisoformat(reference["cutoff"]))
    if (base["version"] != BASE_VERSION or base["event_key"] != reference["event"]["event_key"]
            or base["cutoff"] != reference["cutoff"] or base["params"] != parts[3]
            or base["markets"] != parts[4] or base["model_hash"] != parts[5]):
        raise ContextIntegrityError("NHL base is not its exact original replay")


def hockey_reference_hash(base, event, preprocessing_artifacts=None):
    preprocessing = {} if preprocessing_artifacts is None else preprocessing_artifacts
    if type(preprocessing) is not dict:
        raise ContextContractError("hockey preprocessing must be a closed hash map")
    for name, value in preprocessing.items():
        require_text(name, "hockey preprocessing name", code=True)
        require_digest(value, "hockey preprocessing artifact")
    return digest({"version": "hockey-context-reference-v1", "base_hash": digest(validate_base_distribution(base)),
        "event_hash": digest(hockey_event(event)), "preprocessing_artifacts": dict(sorted(preprocessing.items()))})


def _selection(observations, decision, kickoff):
    """Latest whole native events; previous membership is exclusion proof only."""
    from context_observations import _check_selected_row, factor_state, freshness_policy
    from context_sources.ice_hockey import SCHEMA, validate_hockey_receipt
    if type(observations) is not tuple:
        raise ContextContractError("hockey context needs owning B1 receipt tuples")
    stamp, groups = canonical_timestamp(decision), {}
    for row in observations:
        _check_selected_row(row)
        if row["sport"] != "ice_hockey" or row["source_schema"] != SCHEMA:
            continue
        validate_hockey_receipt(row)
        if row["evidence_class"] == "prospective" and row["observed_at"] <= stamp:
            groups.setdefault((row["event_key"], row["payload"]["kind"]), []).append(row)
    selected, uncertainty = {}, {}

    def state(row):
        if row["payload"]["kind"] == "appearance" and row["payload"]["status"] == "cancelled":
            valid = row["valid_from"] <= stamp and (row["valid_until"] is None or stamp < row["valid_until"])
            return "available" if valid else "stale"
        answer = factor_state((row,), cutoff=decision, scheduled_start=kickoff,
            policy=freshness_policy(row["kind"], schedule_revision=row["schedule_revision"], requires_complete=False))
        return answer["state"] if row["digest"] in answer["usable_refs"] else (
            "missing" if answer["state"] == "available" else answer["state"])

    def uncertain(history, latest):
        if latest[0]["payload"]["kind"] != "appearance": return
        upper = [row["payload"]["data"]["result_observed_at"] for row in latest if state(row) == "available"]
        ambiguity = {"upper": max(upper) if len(upper) == len(latest) else None,
                     "proof": tuple({row["digest"]: row for row in history}.values())}
        for team in {row["payload"]["event"][side] for row in history for side in ("home_id", "away_id")}:
            uncertainty.setdefault(team, []).append(ambiguity)

    for key, history in groups.items():
        newest = max(row["observed_at"] for row in history)
        latest = {row["content_digest"]: row for row in history if row["observed_at"] == newest}
        proof = tuple({row["digest"]: row for row in history}.values())
        if len(latest) != 1:
            selected[key] = (None, "conflicting", proof)
            uncertain(history, tuple(latest.values()))
            continue
        row = next(iter(latest.values()))
        status = state(row)
        selected[key] = (row if status == "available" else None, status, proof)
        # Only an effective cancellation can withdraw participation. A stale
        # or future-valid correction remains uncertainty for every prior/new
        # participant; do not resurrect older play or invent a terminal bound.
        effective_cancellation = row["payload"]["status"] == "cancelled" and status == "available"
        if key[1] == "appearance" and not effective_cancellation:
            old_teams = {old["payload"]["event"][side] for old in history for side in ("home_id", "away_id")}
            current_teams = {row["payload"]["event"][side] for side in ("home_id", "away_id")}
            if status != "available" or (not row["complete"] and old_teams != current_teams):
                uncertain(history, (row,))
    return selected, uncertainty


def _history_matches(row, match, recipe):
    if row is None: return False
    payload, ev = row["payload"], row["payload"]["event"]
    scope = recipe["scope"]
    return (payload["kind"] == "appearance" and ev["status"] == "completed"
        and ev["event_key"] == "nhl:ice_hockey:"+match["event_id"]
        and ev["home_id"] == "nhl:ice_hockey:team:"+match["home"].removeprefix("id:")
        and ev["away_id"] == "nhl:ice_hockey:team:"+match["away"].removeprefix("id:")
        and ev["scheduled_start"] == canonical_timestamp(match["start"])
        and ev["format"] == recipe["event"]["format"]
        and all(payload["scope"][key] == scope[key] for key in ("season", "game_type", "rule_version"))
        and payload["scope"]["neutral_site"] == match["neutral"]
        and (payload["data"]["actual_end"] is None or payload["data"]["actual_end"] <= canonical_timestamp(match["observed"])))


def _exposure_vector(team, *, regulation=3600):
    from context_sources.ice_hockey import exposure_complete
    if not exposure_complete(team, "regulation", regulation): return None
    return {(player["role"], player["player_id"]): player["regulation_seconds"] for player in team["players"]}


def _feature_inputs(event, observations, base, cutoff):
    event, original = hockey_event(event), validate_base_distribution(base)
    if not isinstance(cutoff, datetime): raise ContextContractError("hockey feature cutoff needs an aware datetime")
    stamp = canonical_timestamp(cutoff)
    if (original["family"] != FAMILY or original["version"] != BASE_VERSION
        or original["event_key"] != event["event_key"] or original["cutoff"] != stamp):
        raise ContextIntegrityError("hockey features need exact original base/event/cutoff")
    recipe = original["reference_weights"]
    if recipe["kind"] != "unavailable" and recipe["event"] != event:
        raise ContextIntegrityError("hockey original reference has a different full event")
    return event, original, recipe, stamp, datetime.fromisoformat(event["scheduled_start"])


def hockey_scenarios(event, observations, base, *, cutoff):
    """Only explicitly supplied candidate identities; no average or probability."""
    event, original, recipe, _, kickoff = _feature_inputs(event, observations, base, cutoff)
    selected, _ = _selection(observations, cutoff, kickoff)
    row, _, _ = selected.get((event["event_key"], "projection"), (None, "missing", ()))
    if (row is None or recipe["kind"] == "unavailable" or row["payload"]["event"] != event
        or row["payload"]["scope"] != recipe["scope"]): return {}
    return {scenario["scenario_id"]: hockey_features(event, observations, original, cutoff=cutoff, scenario_id=scenario["scenario_id"])
            for scenario in row["payload"]["data"]["scenarios"]}


def hockey_features(event, observations, base, *, cutoff, scenario_id=None):
    """Observed reference composition plus explicit conditional current usage.

    Equal-game measured means are NOT nonlinear optimizer influence weights.
    All values remain source facts/scenarios; learned residuals are separate.
    """
    event, original, recipe, stamp, kickoff = _feature_inputs(event, observations, base, cutoff)
    if scenario_id is not None: require_text(scenario_id, "hockey scenario", code=True)
    selected, uncertainty = _selection(observations, cutoff, kickoff)
    values, states, refs = {}, {}, {}
    def put(name, value, used=(), state=None):
        state = state or ("available" if value is not None else "missing")
        if state == "available" and value is None: state = "missing"
        if event["status"] != "scheduled" or stamp >= event["scheduled_start"]: state = "not_applicable"
        values[name], states[name] = value if state == "available" else None, state
        # Failed/excluded revisions remain audit references, not numeric zeros.
        refs[name] = sorted({row["digest"] for row in used})

    def current(kind):
        row, state, proof = selected.get((event["event_key"], kind), (None, "missing", ()))
        if row is not None and (recipe["kind"] == "unavailable" or row["payload"]["event"] != event
            or row["payload"]["scope"] != recipe["scope"]): return None, "missing", proof
        return row, state, proof

    projection, projection_state, projection_proof = current("projection")
    starter, starter_state, starter_proof = current("starter")
    candidates = [] if projection is None else projection["payload"]["data"]["scenarios"]
    scenario = next((row for row in candidates if row["scenario_id"] == scenario_id), None)
    # Even a lone candidate is not selected implicitly. Source labels are not
    # centrally confirmed participation; callers name the conditional scenario.
    projected, reference, reference_proof, reference_good = {}, {}, {}, {}
    season = None if recipe["kind"] == "unavailable" else recipe["scope"]["season"]
    goalie_cases = []
    for side in ("home", "away"):
        team_id = event[side+"_id"]
        projected[side] = None if scenario is None else _exposure_vector(scenario["teams"][team_id])
        vectors, proofs = [], []
        matches = [] if recipe["kind"] == "unavailable" else [m for m in recipe["selected"]
            if team_id.rsplit(":", 1)[1] in (m["home"].removeprefix("id:"), m["away"].removeprefix("id:"))]
        good = bool(matches)
        for match in matches:
            row, _, proof = selected.get(("nhl:ice_hockey:"+match["event_id"], "appearance"), (None, "missing", ()))
            proofs.extend(proof)
            vector = _exposure_vector(row["payload"]["data"]["teams"][team_id], regulation=row["payload"]["data"]["regulation_seconds"]) if _history_matches(row, match, recipe) else None
            if vector is None: good = False
            else: vectors.append(vector)
        reference[side], reference_proof[side], reference_good[side] = vectors, proofs, good
        ready = projected[side] is not None and good
        put("exposure_complete_"+side, int(ready), [*projection_proof, *proofs])
        candidate_goalie = None if scenario is None or not scenario["teams"][team_id]["regulation_intervals"] else scenario["teams"][team_id]["regulation_intervals"][0]["goalie"]
        confirmed = None if starter is None else starter["payload"]["data"]["teams"][team_id]
        assumed = None if projected[side] is None else int(not (candidate_goalie is not None and confirmed is not None
            and confirmed["status"] == "confirmed" and confirmed["player_id"] == candidate_goalie))
        put("goalie_assumed_"+side, assumed, [*projection_proof, *starter_proof])
        goalie_cases.append("unavailable" if assumed is None else "conditional" if assumed else "confirmed")

    universe = sorted({key for vector in [*projected.values(), *(v for group in reference.values() for v in group)] if vector for key in vector})
    for side in ("home", "away"):
        for role, player in universe:
            suffix = f"{side}/{role}/{season}/{player}"
            current_value = None if projected[side] is None else projected[side].get((role, player), 0)/3600
            # Sum exact reported integer seconds before the one division. An
            # unchanged repeated exposure must not acquire a rounding delta.
            reference_value = sum(vector.get((role, player), 0) for vector in reference[side])/(3600*len(reference[side])) if reference_good[side] else None
            put("exposure_current_"+suffix, current_value, projection_proof, projection_state if current_value is None else None)
            put("exposure_reference_"+suffix, reference_value, reference_proof[side])
            put("exposure_delta_"+suffix, current_value-reference_value if current_value is not None and reference_value is not None else None,
                [*projection_proof, *reference_proof[side]])

    load_cases = _load_features(event, selected, uncertainty, cutoff, stamp, kickoff, put)
    availability, availability_state, availability_proof = current("availability")
    for side in ("home", "away"):
        team = None if availability is None else availability["payload"]["data"]["teams"][event[side+"_id"]]
        for status in ("out", "questionable"):
            count = None if team is None or not team["complete"] or not team["players"] else sum(player["status"] == status for player in team["players"])
            put(f"reported_{status}_count_{side}", count, availability_proof, availability_state if availability is None else None)
    case = f"scope-{digest(recipe['scope']) if recipe['kind'] != 'unavailable' else 'unavailable'}"
    case += f".scenario-{digest({'scenario_id': scenario_id})}.reference-{'complete' if all(reference_good.values()) else 'missing'}"
    case += ".goalies-"+"-".join(goalie_cases)+".observed-"+"-".join(load_cases)
    return validate_feature_vector({"version": FEATURE_VERSION, "event_key": event["event_key"], "cutoff": stamp,
        "values": values, "states": states, "refs": refs,
        "coverage": {"version": FEATURE_VERSION+".coverage", "case": case}, "reference_hash": hockey_reference_hash(original, event)})


def _load_features(event, selected, uncertainty, cutoff, stamp, kickoff, put):
    from context_sources.ice_hockey import exposure_complete
    load = [(row, proof) for (key, kind), (row, state, proof) in selected.items()
        if kind == "appearance" and key != event["event_key"] and row is not None and state == "available"
        and row["payload"]["status"] == "completed"
        and (row["payload"]["data"]["actual_end"] is None or row["payload"]["data"]["actual_end"] <= stamp)]
    cases = []
    for side in ("home", "away"):
        team_id = event[side+"_id"]
        rows = [row for row, _ in load if team_id in row["payload"]["data"]["teams"]]
        proof = [item for row, history in load if team_id in row["payload"]["data"]["teams"] for item in history]
        ambiguous = uncertainty.get(team_id, [])
        proof.extend(row for item in ambiguous for row in item["proof"])
        known = [row for row in rows if row["payload"]["data"]["actual_end"] is not None]
        unknown = [row for row in rows if row["payload"]["data"]["actual_end"] is None]
        blocked_windows = []
        for days in (1, 3, 7):
            first = canonical_timestamp(cutoff-timedelta(days=days))
            blocked = "conflicting" if any(item["upper"] is None or item["upper"] >= first for item in ambiguous) else None
            blocked_windows.append(bool(blocked))
            window = [row for row in known if first <= row["payload"]["data"]["actual_end"] < stamp]
            undecided = any(row["payload"]["data"]["result_observed_at"] >= first for row in unknown)
            for phase in ("regulation", "overtime"):
                good = bool(window) and not undecided and all(exposure_complete(row["payload"]["data"]["teams"][team_id],
                    phase, row["payload"]["data"][phase+"_seconds"]) for row in window)
                for role in ("skater", "goalie"):
                    seconds = sum(player[phase+"_seconds"] for row in window
                        for player in row["payload"]["data"]["teams"][team_id]["players"] if player["role"] == role) if good else None
                    put(f"observed_{phase}_{role}_seconds_{days}d_{side}", seconds, proof, blocked)
                put(f"observed_{phase}_complete_{days}d_{side}", int(good) if rows or ambiguous else None, proof, blocked)
            put(f"history_complete_{days}d_{side}", 0 if rows or ambiguous else None, proof, blocked)
        last = max((row["payload"]["data"]["actual_end"] for row in known), default=None)
        upper = max([*(row["payload"]["data"]["actual_end"] for row in known),
                     *(row["payload"]["data"]["result_observed_at"] for row in unknown)], default=None)
        exact = last if last is not None and all(row["payload"]["data"]["result_observed_at"] <= last for row in unknown) else None
        blocked = "conflicting" if ambiguous and (last is None or any(item["upper"] is None or item["upper"] >= last for item in ambiguous)) else None
        for label, instant in (("minimum", exact or upper), ("exact", exact)):
            value = None if instant is None else (kickoff-datetime.fromisoformat(instant)).total_seconds()/3600
            put(f"observed_recovery_{label}_hours_{side}", value, proof, blocked)
        put("medical_fatigue_"+side, None)
        put("travel_hours_"+side, None)
        case = "empty" if not rows else "exact" if not unknown else "partial" if known else "bounded"
        if blocked or any(blocked_windows): case = "conflicting"
        elif ambiguous or (unknown and exact is not None): case = "partial-exact"
        cases.append(case)
    return cases


def validate_hockey_context_binding(original, event, features, preprocessing=None):
    """Owning B3 identity check, also when a comparison is unavailable."""
    if original["family"] != FAMILY or original["version"] != BASE_VERSION:
        raise ContextIntegrityError("hockey context cannot reuse an adjusted distribution as its original")
    reference = original["reference_weights"]
    if (original["event_key"] != event["event_key"] or features["event_key"] != event["event_key"]
        or original["cutoff"] != features["cutoff"]
        or (reference["kind"] != "unavailable" and reference["event"] != event)
        or features["reference_hash"] != hockey_reference_hash(original, event, preprocessing)):
        raise ContextIntegrityError("hockey full original/event/feature/preprocessing identity mismatch")


def _mirror_name(name):
    if "_home/" in name: return name.replace("_home/", "_away/", 1)
    if "_away/" in name: return name.replace("_away/", "_home/", 1)
    if name.endswith("_home"): return name.removesuffix("_home")+"_away"
    if name.endswith("_away"): return name.removesuffix("_away")+"_home"
    raise ContextModelError("hockey features need explicit mirrored team roles")


def _prepare(base, features, artifact, event):
    if type(base) is not dict or base.get("version") != BASE_VERSION:
        raise ContextModelError("hockey effect requires its unadjusted original Poisson basis")
    original, event = validate_base_distribution(base), hockey_event(event)
    features, artifact = validate_feature_vector(features), validate_effect_artifact(artifact)
    validate_hockey_context_binding(original, event, features, artifact["preprocessing_artifacts"])
    if (artifact["family"] != FAMILY or artifact["model_variant"] != MODEL_VARIANT
        or artifact["feature_version"] != FEATURE_VERSION or features["version"] != FEATURE_VERSION
        or artifact["preprocessing_artifacts"] or original["reference_weights"]["kind"] != REFERENCE_KIND):
        raise ContextModelError("unsupported hockey effect/feature/reference/participation variant")
    if (event["status"] != "scheduled" or event["scheduled_start"] <= original["cutoff"]
        or artifact["training_end"] > original["cutoff"] or not event_in_population(event, artifact["population"])
        or artifact["population"]["formats"] != [event["format"]] or artifact["population"]["competitions"] != ["nhl"]):
        raise ContextModelError("hockey effect outside its actual causal competition/rules population")
    coverage, scope = features["coverage"], original["reference_weights"]["scope"]
    case = coverage["case"]
    rule = (rf"scope-{digest(scope)}\.scenario-[a-f0-9]{{64}}\.reference-(complete|missing)"
            r"\.goalies-(confirmed|conditional|unavailable)-(confirmed|conditional|unavailable)"
            r"\.observed-(empty|exact|partial|bounded|partial-exact|conflicting)-(empty|exact|partial|bounded|partial-exact|conflicting)")
    match = re.fullmatch(rule, case)
    if coverage != artifact["coverage"] or coverage["version"] != FEATURE_VERSION+".coverage" or match is None:
        raise ContextModelError("hockey effect lacks exact owning observed/scenario coverage")

    def available(name, minimum=None, maximum=None):
        if features["states"].get(name) != "available" or not features["refs"].get(name) or features["values"].get(name) is None:
            raise ContextModelError("hockey effect consumes missing/unreferenced information")
        value = require_number(features["values"][name], "hockey measured/scenario operand", minimum=minimum, maximum=maximum)
        if type(value) is int and int(float(value)) != value:
            raise ContextModelError("hockey integer feature cannot be represented exactly")
        return value

    names = artifact["feature_names"]
    try:
        permutation = [names.index(_mirror_name(name)) for name in names]
    except ValueError as exc:
        raise ContextModelError("hockey feature inventory is not closed under role mirroring") from exc
    home, away = artifact["heads"]["home"], artifact["heads"]["away"]
    if (home["alpha"] != away["alpha"] or home["n_rows"] != away["n_rows"]
        or away["coef"] != [home["coef"][i] for i in permutation]
        or away["scale"] != [home["scale"][i] for i in permutation]):
        raise ContextIntegrityError("hockey heads are not one exactly role-mirrored fitted model")
    # In the home equation home skaters attack, away skaters defend and ONLY
    # the away goalie concedes; the complete orientation is mirrored for away.
    # Do not silently reinterpret a goalie's exposure as own attacking strength.
    for index, name in enumerate(names):
        own_goalie = "_home/goalie/" in name or ("_goalie_seconds_" in name and name.endswith("_home"))
        if own_goalie and home["coef"][index] != 0:
            raise ContextIntegrityError("hockey goalie effect must use the conceding role")
    conditional = False
    for name in names:
        if name.startswith("exposure_delta_"):
            parsed = re.fullmatch(r"exposure_delta_(home|away)/(skater|goalie)/([0-9]+)/(.+)", name)
            if parsed is None: raise ContextModelError("unreviewed hockey exposure role")
            side, role, season, player = parsed.groups()
            native_id(player, "player:")
            if season != str(scope["season"]): raise ContextModelError("hockey player vocabulary belongs to another native season")
            if available("exposure_complete_"+side) != 1 or match.group(1) != "complete":
                raise ContextModelError("hockey exposure requires its complete measured reference and explicit projection")
            left, right = name.replace("exposure_delta_", "exposure_current_", 1), name.replace("exposure_delta_", "exposure_reference_", 1)
            if available(name) != available(left, 0, 1)-available(right, 0, 1):
                raise ContextIntegrityError("hockey exposure difference disagrees with its exact operands")
            if features["refs"][name] != sorted(set(features["refs"][left]) | set(features["refs"][right])):
                raise ContextIntegrityError("hockey exposure provenance disagrees with its operands")
            # This v1 projection is one whole conditional lineup. Omitting its
            # goalie columns does not confirm the skater assumptions. A future
            # independently confirmed skater subset needs its own source and
            # coverage contract; observed-only load never enters this branch.
            for goalie_side in ("home", "away"):
                assumed = available("goalie_assumed_"+goalie_side, 0, 1)
                if assumed not in (0, 1) or match.group(2 if goalie_side == "home" else 3) != ("conditional" if assumed else "confirmed"):
                    raise ContextIntegrityError("hockey goalie assumption/confirmation coverage differs")
                conditional = conditional or bool(assumed)
        else:
            load = re.fullmatch(r"observed_(regulation|overtime)_(skater|goalie)_seconds_([137])d_(home|away)", name)
            rest = re.fullmatch(r"observed_recovery_(minimum|exact)_hours_(home|away)", name)
            if load is not None:
                phase, _, days, side = load.groups()
                if available(f"observed_{phase}_complete_{days}d_{side}") != 1:
                    raise ContextModelError("hockey workload is not a completely measured observed window")
            elif rest is None:
                raise ContextModelError("unreviewed hockey effect input; no hardcoded medical or availability penalty")
            available(name, 0)
    x = np.array([[features["values"][name] for name in names]], dtype=np.float64)
    return original, features, artifact, event, x, conditional


def _effect_values(original, features, artifact, event, x, conditional):
    params = deepcopy(original["params"])
    for side in ("home", "away"):
        delta = offset_delta(artifact["heads"][side], x)
        params[side+"_lambda"] = float(adjust_parameters(np.array([params[side+"_lambda"]]), delta, link="log_rate")[0])
    if params == original["params"]:
        params, markets = deepcopy(original["params"]), deepcopy(original["markets"])
    else:
        markets = hockey_distribution(params["home_lambda"], params["away_lambda"], params["overtime_home_probability"])
    identity = {"version": COMPARISON_VERSION, "base_hash": digest(original), "event_hash": digest(event),
        "feature_hash": digest(features), "effect_hash": digest({"kind": "context-effect-v1", "payload": artifact})}
    return params, markets, digest(identity)


def _validate_comparison_base(base):
    reference = base["reference_weights"]
    prepared = _prepare(reference["original"], reference["features"], reference["effect"], reference["event"])
    params, markets, model_hash = _effect_values(*prepared)
    original = prepared[0]
    if (base["version"] != COMPARISON_VERSION or base["event_key"] != original["event_key"]
        or base["cutoff"] != original["cutoff"] or base["model_hash"] != model_hash
        or base["params"] != params or base["markets"] != markets):
        raise ContextIntegrityError("hockey comparison does not replay its original full input identity")


def hockey_comparison_is_conditional(reference):
    """B3 uses owning replay, not a freely supplied 'verified' scenario flag."""
    return _prepare(reference["original"], reference["features"], reference["effect"], reference["event"])[-1]


def apply_hockey_effect(base, features, artifact, *, event):
    """One original baseline, one residual application, no approval or fetching."""
    prepared = _prepare(base, features, artifact, event)
    original, features, artifact, event, _, _ = prepared
    params, markets, model_hash = _effect_values(*prepared)
    return validate_base_distribution({**deepcopy(original), "version": COMPARISON_VERSION, "model_hash": model_hash,
        "params": params, "markets": markets, "reference_weights": {"schema": 1, "kind": COMPARISON_KIND,
            "original": original, "features": features, "effect": artifact, "event": event}})


def hockey_context_result(base, features, effect_artifact, *, event, effect_hash, approval=None):
    """Actual A1 identity before typed model fallback; approval remains D2-owned."""
    from context_snapshots import _verified_payload, select_context_result
    effect_hash, artifact = _verified_payload(effect_artifact, kind="context-effect-v1", expected_hash=effect_hash)
    original, event = validate_base_distribution(base), hockey_event(event)
    features = validate_feature_vector(features)
    validate_hockey_context_binding(original, event, features, artifact["preprocessing_artifacts"])
    try:
        comparison = apply_hockey_effect(original, features, artifact, event=event)
        limitations = []
    except ContextModelError:
        comparison, limitations = None, ["hockey-numerical-or-measured-comparison-unavailable"]
    return select_context_result(original, comparison, event=event, features=features, effect_artifact=effect_artifact,
        effect_hash=effect_hash, approval=approval,
        factor_roles={name: "applied" if name in artifact["feature_names"] else "not_applied" for name in features["values"]},
        factor_states=dict(features["states"]), limitations=limitations)
