"""C2 basketball-only CPU comparisons; no source fetch or model activation.

The baseline is the original inclusive-OT Ridge margin model. Its signed
prediction influences are not normalized roster averages. Source-truth and
causal empirical approval remain separate from these internal byte checks.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
import math
import re

import numpy as np
from scipy.special import ndtr

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_number, require_object, require_text,
    event_in_population, validate_base_distribution, validate_event,
    validate_feature_vector, validate_effect_artifact,
)
from context_models.offset import ContextModelError, offset_delta, adjust_parameters

FAMILY = "basketball:margin:including_ot"
BASE_VERSION = "basketball-original-ridge-v1"
REFERENCE_KIND = "basketball-margin-ridge-v1"
FEATURE_VERSION = "basketball-rotation-observed-load-v1"
MODEL_VARIANT = "basketball-signed-ridge-rotation-margin-v1"
COMPARISON_VERSION = "basketball-context-comparison-v1"
COMPARISON_KIND = "basketball-margin-comparison-reference-v1"
FORMATS = {"nba_reg48_including_ot": ("espn", "nba", 48),
           "euroleague_reg40_including_ot": ("euroleague", "euroleague", 40)}


def _number(value, label, *, positive=False):
    require_number(value, label)
    if type(value) is int and int(float(value)) != value:
        raise ContextModelError(f"{label} integer is not exactly representable")
    if positive and value <= 0:
        raise ContextModelError(f"{label} must be strictly positive")
    return value


def margin_distribution(mean: float, scale: float) -> dict:
    """One declared continuous margin law; no clipping or settlement expansion."""
    _number(mean, "expected margin")
    _number(scale, "residual scale", positive=True)
    ratio = mean / scale
    if not math.isfinite(ratio):
        raise ContextModelError("margin standardization overflowed")
    probability = float(ndtr(ratio))
    return {"expected_margin": mean, "residual_scale": scale,
            "home_win": probability, "away_win": 1. - probability}


def basketball_event(event):
    event = validate_event(event)
    if event["sport"] != "basketball" or event["format"] not in FORMATS:
        raise ContextContractError("only explicit basketball inclusive-OT formats are supported")
    source, competition, _ = FORMATS[event["format"]]
    if event["competition"] != competition or not event["event_key"].startswith(source + ":basketball:"):
        raise ContextContractError("basketball provider/competition/format mismatch")
    for side in ("home_id", "away_id"):
        native_subject(event[side], source, "team")
    native_event(event["event_key"], source)
    return event


def native_event(value, source):
    require_text(value, "native basketball event", code=True)
    prefix = source + ":basketball:"
    suffix = value[len(prefix):] if value.startswith(prefix) else ""
    pattern = r"[1-9][0-9]*" if source == "espn" else r"[A-Za-z0-9][A-Za-z0-9_-]*"
    if not re.fullmatch(pattern, suffix):
        raise ContextContractError("unknown native basketball event identity")
    return value


def native_subject(value, source, kind):
    require_text(value, "native basketball subject", code=True)
    prefix = f"{source}:basketball:{kind}:"
    suffix = value[len(prefix):] if value.startswith(prefix) else ""
    pattern = r"[1-9][0-9]*" if source == "espn" else r"[A-Za-z0-9][A-Za-z0-9_-]*"
    if not re.fullmatch(pattern, suffix):
        raise ContextContractError("unknown native basketball team/player identity")
    return value


def basketball_rules(value, format_code):
    require_object(value, {"regulation_minutes", "regulation_periods", "overtime_period_minutes"}, label="basketball source-resolved rules")
    if format_code not in FORMATS:
        raise ContextContractError("unreviewed basketball game rules")
    if (type(value["regulation_minutes"]) is not int or value["regulation_minutes"] != FORMATS[format_code][2]
            or type(value["regulation_periods"]) is not int or value["regulation_periods"] != 4
            or type(value["overtime_period_minutes"]) is not int or value["overtime_period_minutes"] <= 0):
        raise ContextContractError("actual basketball rule scope is missing or inconsistent")
    return dict(value)


def _scope(scope, format_code):
    require_object(scope, {"season", "rules"}, label="basketball source scope")
    require_text(scope["season"], "actual season", code=True)
    return {"season": scope["season"], "rules": basketball_rules(scope["rules"], format_code)}


def _native_team(key, source):
    if not key.startswith("id:"):
        raise ContextContractError("name-only baseline cannot establish native roster joins")
    return native_subject(f"{source}:basketball:team:{key[3:]}", source, "team")


def _source_id(value, label):
    if type(value) is int and value > 0:
        return str(value)
    return require_text(value, label, code=True)


def _reported_team(row, side, source):
    raw = row.get(side + "_team_id") or row.get("team1_id" if side == "home" else "team2_id")
    return native_subject(f"{source}:basketball:team:{_source_id(raw, 'actual native team ID')}", source, "team")


def _recipe_arrays(rows, teams, target, penalty):
    x = np.array([[float(row["home_id"] == team) - float(row["away_id"] == team) for team in teams]
                  + [float(not row["neutral_site"])] for row in rows], dtype=np.float64)
    q = np.array([float(target["home_id"] == team) - float(target["away_id"] == team) for team in teams]
                 + [float(not target["neutral_site"])], dtype=np.float64)
    y = np.array([row["home_score"] - row["away_score"] for row in rows], dtype=np.float64)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            gram = x.T @ x
            regularized = gram + np.diag(penalty)
            coefficients = np.linalg.solve(regularized, x.T @ y)
            effective = float(np.trace(np.linalg.solve(regularized, gram)))
            residuals = y - x @ coefficients
            prior = max(float(np.var(y, ddof=1)), 1.)
            scale = math.sqrt((float(residuals @ residuals) + 5. * prior) / (max(1., len(y) - effective) + 5.))
            influences = q @ np.linalg.solve(regularized, x.T)
        if not np.isfinite(coefficients).all() or not np.isfinite(influences).all() or not math.isfinite(scale) or scale <= 0:
            raise ContextModelError("nonfinite basketball reference replay")
        return coefficients, scale, influences
    except (np.linalg.LinAlgError, ValueError, FloatingPointError, OverflowError) as exc:
        raise ContextModelError("basketball original Ridge reference cannot be replayed") from exc


def validate_basketball_reference(value, history_refs):
    """Replay all declared design/penalty/target bytes; hashes are not source proof."""
    require_object(value, {"schema", "kind", "event", "scope", "neutral_site", "teams", "rows", "penalty",
                          "coefficients", "influences", "residual_scale"}, label="basketball Ridge reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != REFERENCE_KIND:
        raise ContextContractError("unknown basketball reference version")
    event = basketball_event(value["event"])
    source = FORMATS[event["format"]][0]
    _scope(value["scope"], event["format"])
    if type(value["neutral_site"]) is not bool:
        raise ContextContractError("basketball venue orientation must be explicitly known")
    teams, rows = value["teams"], value["rows"]
    if (type(teams) is not list or any(type(team) is not str for team in teams) or not 2 <= len(teams) <= 64
        or len({team.casefold() for team in teams}) != len(teams) or teams != sorted(teams, key=str.casefold)):
        raise ContextContractError("invalid complete Ridge team design")
    for team in teams:
        native_subject(team, source, "team")
    if event["home_id"] not in teams or event["away_id"] not in teams:
        raise ContextContractError("target team absent from original fit")
    if type(rows) is not list or not 40 <= len(rows) <= 1200:
        raise ContextContractError("invalid complete Ridge event inventory")
    expected_refs = {row["ref"]: row for row in history_refs}
    seen = set()
    for row in rows:
        require_object(row, {"ref", "event_key", "home_id", "away_id", "start", "observed", "home_score", "away_score",
                             "neutral_site", "season", "rules"}, label="basketball reference match")
        native_event(row["event_key"], source)
        if row["event_key"] in seen or row["event_key"] == event["event_key"]:
            raise ContextContractError("duplicate or target event in baseline history")
        seen.add(row["event_key"])
        if row["home_id"] == row["away_id"] or any(row[key] not in teams for key in ("home_id", "away_id")):
            raise ContextContractError("historical basketball participant mismatch")
        if type(row["neutral_site"]) is not bool:
            raise ContextContractError("unknown historical neutral-site reference")
        if any(type(row[key]) is not int or row[key] < 0 for key in ("home_score", "away_score")) or row["home_score"] == row["away_score"]:
            raise ContextContractError("basketball inclusive result must be a final untied integer score")
        for key in ("start", "observed"):
            if type(row[key]) is not str or canonical_timestamp(row[key]) != row[key]:
                raise ContextContractError("noncanonical basketball history time")
        if row["start"] >= row["observed"]:
            raise ContextContractError("basketball history is not an observed completion")
        _scope({"season": row["season"], "rules": row["rules"]}, event["format"])
        ref = require_digest(row["ref"])
        if ref != digest({key: item for key, item in row.items() if key != "ref"}):
            raise ContextIntegrityError("basketball historical sport projection changed")
        expected = {"ref": ref, "source": source, "source_event_id": row["event_key"].split(":", 2)[2],
                    "native_event_key": row["event_key"], "event_join": "verified_native", "roster_join": "unresolved"}
        if expected_refs.get(ref) != expected:
            raise ContextIntegrityError("basketball reference inventory/native source binding differs")
    if len(expected_refs) != len(rows) or rows != sorted(rows, key=lambda row: (row["start"], row["event_key"].casefold())):
        raise ContextContractError("Ridge inventory order or count differs")
    if set(teams) != {row[key] for row in rows for key in ("home_id", "away_id")}:
        raise ContextIntegrityError("Ridge design contains an unobserved team column")
    penalty = value["penalty"]
    if type(penalty) is not list or penalty != [5.] * len(teams) + [1e-8]:
        raise ContextContractError("basketball reference must retain actual Ridge penalty")
    for name, count in (("penalty", len(teams) + 1), ("coefficients", len(teams) + 1), ("influences", len(rows))):
        if type(value[name]) is not list or len(value[name]) != count:
            raise ContextContractError("basketball reference dimension mismatch")
        for item in value[name]:
            _number(item, name)
    _number(value["residual_scale"], "reference scale", positive=True)
    coefficients, scale, influences = _recipe_arrays(rows, teams, {**event, "neutral_site": value["neutral_site"]}, penalty)
    if coefficients.tolist() != value["coefficients"] or scale != value["residual_scale"] or influences.tolist() != value["influences"]:
        raise ContextIntegrityError("original basketball Ridge recipe replay mismatch")
    return deepcopy(value)


def validate_basketball_base_reference(base):
    reference = base["reference_weights"]
    if reference["kind"] == COMPARISON_KIND:
        return validate_basketball_comparison(base)
    if base["version"] == COMPARISON_VERSION:
        raise ContextIntegrityError("a comparison label cannot bypass original Ridge replay")
    if reference["kind"] == "unavailable":
        return
    event = reference["event"]
    if event["event_key"] != base["event_key"] or any(row["observed"] >= base["cutoff"] for row in reference["rows"]):
        raise ContextIntegrityError("basketball reference is not the original causal event")
    teams, coefficients = reference["teams"], reference["coefficients"]
    mean = coefficients[teams.index(event["home_id"])] - coefficients[teams.index(event["away_id"])]
    mean += 0. if reference["neutral_site"] else coefficients[-1]
    if base["params"] != {"expected_margin": mean, "residual_scale": reference["residual_scale"]}:
        raise ContextIntegrityError("basketball base parameters differ from original fit")


def export_basketball_base(event, history, as_of, *, context_event, scope=None):
    """Export legacy original bytes; missing source provenance does not hide base."""
    import sports_prematch as legacy
    current = basketball_event(context_event)
    if not isinstance(as_of, datetime):
        raise ContextContractError("basketball export needs actual aware decision time")
    cutoff = canonical_timestamp(as_of)
    identity, missing = legacy._identity("basketball", event, as_of)
    prediction = legacy.predict_prematch("basketball", event, history, as_of)
    if identity is None or prediction.p_home is None:
        raise ContextModelError("no available original basketball basis")
    source, competition, _ = FORMATS[current["format"]]
    actual_target_id = _source_id(event.get("provider_event_id") or event.get("event_id") or event.get("game_id") or event.get("match_id") or event.get("id"), "actual native event ID")
    if (identity.provider != source or identity.competition != competition
            or current["event_key"] != native_event(f"{source}:basketball:{actual_target_id}", source)
            or current["scheduled_start"] != canonical_timestamp(identity.start)
            or current["status"] != "scheduled"):
        raise ContextIntegrityError("original and context basketball event differ")
    for side in ("home", "away"):
        key = getattr(identity, side)
        if key.startswith("id:") and _reported_team(event, side, source) != current[side + "_id"]:
            raise ContextIntegrityError("basketball target team orientation differs")
    matches = legacy._normalise_history("basketball", identity, history, as_of)
    fitted = legacy._fit("basketball", matches)  # Reuses the exact cached legacy fit.
    _, params = legacy._predict(fitted, identity.home, identity.away, identity.neutral)
    params = {key: float(value) for key, value in params.items()}  # Exact float64 -> JSON scalar, no rounding.
    references = []
    reference = {"schema": 1, "kind": "unavailable", "reason": "basketball-native-season-roster-rules-unresolved"}
    if scope is not None:
        try:
            clean_scope = _scope(scope, current["format"])
            if type(event.get("neutral_site")) is not bool:
                raise ContextContractError("actual venue orientation unavailable")
            rows = []
            native_teams = {}
            def bind_team(raw, side):
                key, native = legacy._team(raw, side), _reported_team(raw, side, source)
                if not key.startswith("id:") or (key in native_teams and native_teams[key] != native):
                    raise ContextContractError("ambiguous native-to-legacy team identity mapping")
                native_teams[key] = native
                return native
            for side in ("home", "away"):
                bind_team(event, side)
            for match in matches:
                candidates = [row for row in history if isinstance(row, dict)
                    and legacy._text(row.get("provider") or row.get("source")) == source
                    and legacy._text(row.get("provider_event_id") or row.get("event_id") or row.get("id")) == match.event_id
                    and legacy._time(row.get("result_observed_at") or row.get("observed_at")) == match.observed]
                declarations = [{"season": row.get("season"), "rules": row.get("context_rules")} for row in candidates]
                if not declarations or any(item != declarations[0] for item in declarations):
                    raise ContextContractError("ambiguous historical season/rule projection")
                source_scope = _scope(declarations[0], current["format"])
                if any(type(row.get("neutral_site")) is not bool for row in candidates):
                    raise ContextContractError("unknown historical venue orientation")
                event_ids = {_source_id(row.get("provider_event_id") or row.get("event_id") or row.get("id"), "actual native event ID") for row in candidates}
                if len(event_ids) != 1:
                    raise ContextContractError("ambiguous native-to-legacy event identity mapping")
                for raw in candidates:
                    for side in ("home", "away"):
                        bind_team(raw, side)
                item = {"event_key": native_event(f"{source}:basketball:{next(iter(event_ids))}", source),
                    "home_id": native_teams[match.home], "away_id": native_teams[match.away],
                    "start": canonical_timestamp(match.start), "observed": canonical_timestamp(match.observed),
                    "home_score": match.home_score, "away_score": match.away_score,
                    "neutral_site": match.neutral, **source_scope}
                rows.append({"ref": digest(item), **item})
            teams = [native_teams[team] for team in fitted.teams]
            penalty = [5.] * len(teams) + [1e-8]
            _, _, influences = _recipe_arrays(rows, teams, {**current, "neutral_site": identity.neutral}, penalty)
            references = [{"ref": row["ref"], "source": source, "source_event_id": row["event_key"].split(":", 2)[2],
                "native_event_key": row["event_key"], "event_join": "verified_native", "roster_join": "unresolved"} for row in rows]
            reference = {"schema": 1, "kind": REFERENCE_KIND, "event": current, "scope": clean_scope,
                "neutral_site": identity.neutral, "teams": teams, "rows": rows, "penalty": penalty,
                "coefficients": [float(value) for value in fitted.coefficients], "influences": influences.tolist(), "residual_scale": fitted.residual_scale}
        except ContextContractError:
            # Source capability remains unavailable; never reconstruct missing
            # native IDs/season/rules from names, kickoff or a mean roster.
            references = []
    model_hash = digest({"version": BASE_VERSION, "legacy_model": legacy.MODEL_VERSION,
                         "legacy_input_hash": prediction.input_hash, "fit": asdict(fitted)})
    return validate_base_distribution({"version": BASE_VERSION, "model_hash": model_hash,
        "event_key": current["event_key"], "cutoff": cutoff, "family": FAMILY, "params": params,
        "markets": {"home_win": prediction.p_home, "away_win": prediction.p_away},
        "history_refs": references, "reference_weights": reference})


def basketball_reference_hash(base, event, preprocessing_artifacts=None):
    preprocessing = {} if preprocessing_artifacts is None else preprocessing_artifacts
    if type(preprocessing) is not dict:
        raise ContextContractError("preprocessing references must be an exact hash map")
    for name, value in preprocessing.items():
        require_text(name, "preprocessing name", code=True)
        require_digest(value, "preprocessing artifact")
    return digest({"version": "basketball-context-reference-v1", "base_hash": digest(validate_base_distribution(base)),
        "event_hash": digest(basketball_event(event)), "preprocessing_artifacts": dict(sorted(preprocessing.items()))})


def _selected(observations, decision, kickoff):
    from context_observations import factor_state, freshness_policy
    from context_sources.basketball import SCHEMA, validate_basketball_receipt
    if type(observations) is not tuple:
        raise ContextContractError("basketball context requires selected B1 receipt tuples")
    groups = {}
    for row in observations:
        if type(row) is not dict:
            raise ContextContractError("basketball context requires a B1 receipt")
        factor_state((row,), cutoff=decision, scheduled_start=kickoff,
            policy=freshness_policy(row.get("kind"), schedule_revision=row.get("schedule_revision"), requires_complete=False))
        if row["sport"] != "basketball" or row["source_schema"] != SCHEMA:
            continue
        validate_basketball_receipt(row)
        if row["evidence_class"] == "prospective" and row["observed_at"] <= canonical_timestamp(decision):
            groups.setdefault((row["event_key"], row["payload"]["kind"]), []).append(row)
    selected, conflicts = {}, set()
    for key, history in groups.items():
        newest = max(row["observed_at"] for row in history)
        latest = {row["content_digest"]: row for row in history if row["observed_at"] == newest}
        if len(latest) != 1:
            selected[key] = (None, "conflicting")
            conflicts.update(row["payload"]["event"][side] for row in history for side in ("home_id", "away_id"))
            continue
        row = next(iter(latest.values()))
        state = factor_state((row,), cutoff=decision, scheduled_start=kickoff,
            policy=freshness_policy(row["kind"], schedule_revision=row["schedule_revision"], requires_complete=False))
        selected[key] = (row if row["digest"] in state["usable_refs"] else None, state["state"])
        # Withdrawals and late incomplete revisions supersede the entire event;
        # no lookup can recover individual members from an older collection.
        if key[1] == "appearance" and state["state"] != "available" and row["payload"]["status"] != "cancelled":
            conflicts.update(row["payload"]["event"][side] for row in history for side in ("home_id", "away_id"))
    return selected, conflicts


def _rotation_vector(row):
    """One complete measured/projected signed regulation vector, never health."""
    payload = row["payload"]
    output = {}
    regulation = payload["rules"]["regulation_minutes"]
    for side, sign in (("home_id", 1), ("away_id", -1)):
        team = payload["data"]["teams"][payload["event"][side]]
        if not team["complete"] or team["collection"] != "full_rotation" or not team["players"]:
            return None
        for player in team["players"]:
            if player["regulation_minutes"] is None:
                return None
            if payload["kind"] == "rotation" and player["availability"] in {"questionable", "unknown"}:
                return None
            output[player["player_id"]] = sign * player["regulation_minutes"] / regulation
    return output


def _history_binding(row, reference, target):
    if row is None:
        return False
    payload, ev = row["payload"], row["payload"]["event"]
    return (payload["kind"] == "appearance" and payload["status"] == "completed"
        and ev["format"] == target["format"] and ev["competition"] == target["competition"]
        and all(ev[key] == reference[key] for key in ("event_key", "home_id", "away_id"))
        and ev["scheduled_start"] == reference["start"] and payload["season"] == reference["season"]
        and payload["rules"] == reference["rules"]
        and (payload["data"]["actual_end"] is None or payload["data"]["actual_end"] <= reference["observed"]))


def team_sport_features(sport: str, event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime, preprocessing: dict | None = None) -> dict:
    """C2 only: original signed roster differences and observed inclusive load.

    A missing player in a complete *measured* rotation has measured exposure 0;
    in a complete expected rotation it has expected exposure 0 in that exact
    scenario only. Incomplete rows/cells never acquire a zero. The player
    universe is explicit native membership, not name matching or a fake roster.
    """
    if sport != "basketball" or preprocessing not in (None, {}):
        raise ContextModelError("only basketball without unimplemented participation preprocessing is supported")
    event, original = basketball_event(event), validate_base_distribution(base)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("basketball feature cutoff requires an aware datetime")
    stamp = canonical_timestamp(cutoff)
    if original["family"] != FAMILY or original["version"] != BASE_VERSION or original["event_key"] != event["event_key"] or original["cutoff"] != stamp:
        raise ContextIntegrityError("basketball features require their exact original base/cutoff")
    recipe = original["reference_weights"]
    if recipe["kind"] != "unavailable" and recipe["event"] != event:
        raise ContextIntegrityError("basketball original recipe belongs to another full event revision")
    kickoff = datetime.fromisoformat(event["scheduled_start"])
    selected, conflicts = _selected(observations, cutoff, kickoff)
    values, states, refs = {}, {}, {}

    def put(name, value, used=(), state=None):
        state = state or ("available" if value is not None else "missing")
        if event["status"] != "scheduled" or event["scheduled_start"] <= stamp:
            state = "not_applicable"
        values[name] = value if state == "available" else None
        states[name] = state
        refs[name] = sorted({row["digest"] for row in used}) if state == "available" else []

    current, current_state = selected.get((event["event_key"], "rotation"), (None, "missing"))
    if current is not None and (current["payload"]["event"] != event or recipe["kind"] == "unavailable"
        or {key: current["payload"][key] for key in ("season", "rules")} != recipe["scope"]):
        current, current_state = None, "missing"
    projected = None if current is None else _rotation_vector(current)
    if projected is None and current_state == "available":
        current_state = "missing"
    historical, vectors = [], []
    reference_complete = recipe["kind"] == REFERENCE_KIND
    if reference_complete:
        for match in recipe["rows"]:
            row, _ = selected.get((match["event_key"], "appearance"), (None, "missing"))
            vector = _rotation_vector(row) if _history_binding(row, match, event) else None
            if vector is None:
                reference_complete = False
            else:
                historical.append(row)
                vectors.append(vector)
    good = projected is not None and reference_complete
    membership = sorted(set(projected or {}) | {player for vector in vectors for player in vector})
    for player in membership:
        current_value = None if projected is None else projected.get(player, 0.)
        reference_value = math.fsum(weight * vector.get(player, 0.) for weight, vector in zip(recipe["influences"], vectors)) if reference_complete else None
        put("rotation_current/" + player, current_value, (current,) if current else (), current_state if projected is None else None)
        put("rotation_reference/" + player, reference_value, historical)
        put("rotation_delta/" + player, current_value - reference_value if good else None, [current, *historical] if good else ())
    put("rotation_complete", int(good) if current else None, [current, *historical] if current else ())
    projection = "missing" if current is None else current["payload"]["data"]["status"]
    load = [row for (key, kind), (row, state) in selected.items() if kind == "appearance" and key != event["event_key"] and state == "available"
        and row["payload"]["status"] == "completed" and row["payload"]["event"]["format"] == event["format"]
        and row["payload"]["event"]["competition"] == event["competition"]
        and (row["payload"]["data"]["actual_end"] is None or row["payload"]["data"]["actual_end"] < stamp)]
    load_cases = []
    roots = []
    for side in ("home", "away"):
        team_id = event[side + "_id"]
        rows = [row for row in load if team_id in row["payload"]["data"]["teams"]]
        blocked = "conflicting" if team_id in conflicts else None
        known = [row for row in rows if row["payload"]["data"]["actual_end"] is not None]
        unknown = [row for row in rows if row["payload"]["data"]["actual_end"] is None]
        for days in (1, 3, 7):
            first = canonical_timestamp(cutoff - timedelta(days=days))
            window = [row for row in known if first <= row["payload"]["data"]["actual_end"] < stamp]
            measured = [row for row in window if row["payload"]["data"]["teams"][team_id]["complete"]
                and row["payload"]["data"]["overtime_periods"] is not None
                and row["payload"]["data"]["teams"][team_id]["players"]
                and all(player["inclusive_minutes"] is not None for player in row["payload"]["data"]["teams"][team_id]["players"])]
            uncertain = any(row["payload"]["data"]["result_observed_at"] >= first for row in unknown)
            total = math.fsum(player["inclusive_minutes"] for row in measured for player in row["payload"]["data"]["teams"][team_id]["players"]) if measured else None
            for root, value, used in ((f"observed_inclusive_minutes_{days}d", total, measured),
                (f"observed_inclusive_minutes_complete_{days}d", int(bool(window) and len(measured) == len(window) and not uncertain) if rows else None, rows),
                (f"history_complete_{days}d", 0 if rows else None, rows)):
                put(root + "_" + side, value, used, blocked)
                if root not in roots: roots.append(root)
        last_end = max((row["payload"]["data"]["actual_end"] for row in known), default=None)
        upper = max((row["payload"]["data"]["result_observed_at"] for row in rows), default=None)
        exact = last_end if last_end is not None and all(row["payload"]["data"]["result_observed_at"] <= last_end for row in unknown) else None
        for label, instant in (("minimum", exact or upper), ("exact", exact)):
            root = f"observed_recovery_{label}_hours"
            hours = None if instant is None else (kickoff - datetime.fromisoformat(instant)).total_seconds() / 3600
            put(root + "_" + side, hours, rows, blocked)
            if root not in roots: roots.append(root)
        put("medical_fatigue_" + side, None)
        put("travel_hours_" + side, None)
        case = "no-history" if not rows else "known-end-times" if not unknown else "missing-end-times" if not known else "partial-end-times"
        if unknown and exact is not None and all(row["payload"]["data"]["result_observed_at"] < canonical_timestamp(cutoff - timedelta(days=7)) for row in unknown):
            case = "bounded-irrelevant-end-times"
        load_cases.append(blocked or case)
    for root in roots:
        home, away = root + "_home", root + "_away"
        if states[home] == states[away] == "available":
            put(root + "_delta", values[home] - values[away])
            refs[root + "_delta"] = sorted(set(refs[home]) | set(refs[away]))
        else:
            put(root + "_delta", None, state="conflicting" if "conflicting" in {states[home], states[away]} else "missing")
    availability, availability_state = selected.get((event["event_key"], "availability"), (None, "missing"))
    if availability is not None and (availability["payload"]["event"] != event or recipe["kind"] == "unavailable"
        or {key: availability["payload"][key] for key in ("season", "rules")} != recipe["scope"]):
        availability, availability_state = None, "missing"
    for side in ("home", "away"):
        team = None if availability is None else availability["payload"]["data"]["teams"][event[side + "_id"]]
        for status in ("out", "questionable"):
            count = None if team is None or not team["complete"] else sum(player["availability"] == status for player in team["players"])
            put(f"reported_{status}_count_{side}", count, (availability,) if availability else (), availability_state if availability is None else None)
    scope = "unavailable" if recipe["kind"] != REFERENCE_KIND else digest(recipe["scope"])
    return validate_feature_vector({"version": FEATURE_VERSION, "event_key": event["event_key"], "cutoff": stamp,
        "values": values, "states": states, "refs": refs,
        "coverage": {"version": FEATURE_VERSION + ".coverage", "case": f"rotation-{projection}.{'complete' if good else 'missing'}-reference.scope-{scope}.observed-only." + ".".join(load_cases)},
        "reference_hash": basketball_reference_hash(original, event)})


def _prepare_effect(sport, base, features, artifact, event):
    if sport != "basketball":
        raise ContextModelError("this version implements only basketball")
    # Refuse nesting before recursively validating any supplied comparison.
    if type(base) is not dict or base.get("version") != BASE_VERSION:
        raise ContextModelError("basketball effect requires an original unadjusted Ridge basis")
    original = validate_base_distribution(base)
    event = basketball_event(event)
    features, artifact = validate_feature_vector(features), validate_effect_artifact(artifact)
    if original["family"] != FAMILY or artifact["family"] != FAMILY:
        raise ContextModelError("basketball effect family mismatch")
    if original["reference_weights"]["kind"] != REFERENCE_KIND:
        raise ContextModelError("basketball original native season/rule/roster reference unavailable")
    if (original["reference_weights"]["event"] != event or original["event_key"] != event["event_key"]
        or features["event_key"] != event["event_key"] or features["cutoff"] != original["cutoff"]
        or features["reference_hash"] != basketball_reference_hash(original, event, artifact["preprocessing_artifacts"])):
        raise ContextIntegrityError("basketball original event/base/feature reference binding differs")
    if (artifact["preprocessing_artifacts"] or artifact["model_variant"] != MODEL_VARIANT
        or features["version"] != FEATURE_VERSION or artifact["feature_version"] != FEATURE_VERSION):
        raise ContextModelError("basketball context variant or preprocessing unsupported")
    if (event["status"] != "scheduled" or event["scheduled_start"] <= original["cutoff"]
        or artifact["training_end"] > original["cutoff"] or not event_in_population(event, artifact["population"])
        or artifact["population"]["formats"] != [event["format"]] or artifact["population"]["competitions"] != [event["competition"]]):
        raise ContextModelError("basketball effect is outside its exact causal competition/rule population")
    coverage = features["coverage"]
    scope = digest(original["reference_weights"]["scope"])
    prefixes = tuple(f"rotation-{state}.complete-reference.scope-{scope}.observed-only." for state in ("expected", "confirmed"))
    if (coverage != artifact["coverage"] or coverage["version"] != FEATURE_VERSION + ".coverage"
        or not coverage["case"].startswith(prefixes)):
        raise ContextModelError("basketball coverage cannot borrow complete measured/projection provenance")
    allowed_timing = {"known-end-times", "partial-end-times", "missing-end-times", "no-history", "bounded-irrelevant-end-times", "conflicting"}
    suffix = coverage["case"].split(".observed-only.", 1)[1].split(".")
    if len(suffix) != 2 or not set(suffix) <= allowed_timing:
        raise ContextModelError("unsupported basketball observed history timing case")

    def available(name):
        if features["states"].get(name) != "available" or features["values"].get(name) is None or not features["refs"].get(name):
            raise ContextModelError("basketball effect cannot consume missing or unreferenced features")
        return _number(features["values"][name], "basketball measured feature")

    if available("rotation_complete") != 1:
        raise ContextModelError("basketball original and current complete rotation are required")
    for name in artifact["feature_names"]:
        if name.startswith("rotation_delta/"):
            player = name.split("/", 1)[1]
            native_subject(player, FORMATS[event["format"]][0], "player")
            left, right = "rotation_current/" + player, "rotation_reference/" + player
        else:
            roots = {*(f"observed_inclusive_minutes_{days}d" for days in (1, 3, 7)),
                     "observed_recovery_minimum_hours", "observed_recovery_exact_hours"}
            root = name.removesuffix("_delta")
            if not name.endswith("_delta") or root not in roots:
                raise ContextModelError("unreviewed basketball input; no raw availability/medical penalty")
            left, right = root + "_home", root + "_away"
            if root.startswith("observed_inclusive_minutes_"):
                period = root.rsplit("_", 1)[1]
                for side in ("home", "away"):
                    if available(f"observed_inclusive_minutes_complete_{period}_{side}") != 1:
                        raise ContextModelError("inclusive workload is an incompletely measured observed subset")
            if available(left) < 0 or available(right) < 0:
                raise ContextModelError("observed load or recovery cannot be negative")
        if available(name) != available(left) - available(right):
            raise ContextIntegrityError("basketball signed feature differs from its two referenced operands")
        if features["refs"][name] != sorted(set(features["refs"][left]) | set(features["refs"][right])):
            raise ContextIntegrityError("basketball signed feature provenance differs")
    x = np.array([[features["values"][name] for name in artifact["feature_names"]]], dtype=np.float64)
    return original, features, artifact, event, x


def _effect_values(original, features, artifact, event, x):
    delta = offset_delta(artifact["heads"]["margin"], x)
    mean = float(adjust_parameters(np.array([original["params"]["expected_margin"]], dtype=np.float64), delta, link="identity")[0])
    params = {"expected_margin": mean, "residual_scale": original["params"]["residual_scale"]}
    if params == original["params"]:
        params, markets = deepcopy(original["params"]), deepcopy(original["markets"])
    else:
        probabilities = margin_distribution(mean, params["residual_scale"])
        markets = {key: probabilities[key] for key in ("home_win", "away_win")}
        if any(not 0 < probability < 1 for probability in markets.values()):
            raise ContextModelError("basketball margin comparison saturated its probability domain")
    identity = {"version": COMPARISON_VERSION, "base_hash": digest(original), "event_hash": digest(event),
        "feature_hash": digest(features), "effect_hash": digest({"kind": "context-effect-v1", "payload": artifact})}
    return params, markets, digest(identity)


def validate_basketball_comparison_reference(value, history_refs):
    require_object(value, {"schema", "kind", "original", "features", "effect", "event"}, label="closed basketball comparison reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != COMPARISON_KIND:
        raise ContextContractError("unsupported basketball comparison reference")
    original, _, _, _, _ = _prepare_effect("basketball", value["original"], value["features"], value["effect"], value["event"])
    if history_refs != original["history_refs"]:
        raise ContextIntegrityError("basketball comparison changed its original history inventory")
    return deepcopy(value)


def validate_basketball_comparison(base):
    reference = base["reference_weights"]
    prepared = _prepare_effect("basketball", reference["original"], reference["features"], reference["effect"], reference["event"])
    params, markets, model_hash = _effect_values(*prepared)
    original = prepared[0]
    if (base["version"] != COMPARISON_VERSION or base["event_key"] != original["event_key"] or base["cutoff"] != original["cutoff"]
        or base["params"] != params or base["markets"] != markets or base["model_hash"] != model_hash):
        raise ContextIntegrityError("basketball comparison does not replay from its original base/features/effect")


def apply_team_sport_effect(sport: str, base: dict, features: dict, artifact: dict, *, event: dict) -> dict:
    """Actual fitted B2 identity residual, internal comparison only, no approval."""
    prepared = _prepare_effect(sport, base, features, artifact, event)
    original, features, artifact, event, _ = prepared
    params, markets, model_hash = _effect_values(*prepared)
    return validate_base_distribution({**deepcopy(original), "version": COMPARISON_VERSION, "model_hash": model_hash,
        "params": params, "markets": markets, "reference_weights": {"schema": 1, "kind": COMPARISON_KIND,
            "original": original, "features": features, "effect": artifact, "event": event}})


def team_sport_context_result(sport: str, base: dict, features: dict, effect_artifact: dict, *, event: dict,
                              effect_hash: str, approval: dict | None = None) -> dict:
    """Typed numerical/data fallback; no source fetch or implicit D2 approval."""
    from context_snapshots import select_context_result
    require_object(effect_artifact, {"kind", "payload"}, label="basketball A1 effect envelope")
    require_digest(effect_hash, "basketball A1 effect hash")
    artifact = validate_effect_artifact(effect_artifact["payload"])
    if effect_artifact["kind"] != "context-effect-v1" or digest(effect_artifact) != effect_hash:
        raise ContextIntegrityError("basketball A1 effect identity differs")
    original, event = validate_base_distribution(base), basketball_event(event)
    features = validate_feature_vector(features)
    if features["reference_hash"] != basketball_reference_hash(original, event, artifact["preprocessing_artifacts"]):
        raise ContextIntegrityError("basketball fallback cannot reuse a different original event/reference")
    try:
        comparison = apply_team_sport_effect(sport, original, features, artifact, event=event)
        limitations = []
    except ContextModelError:
        comparison = None
        limitations = ["basketball-numerical-or-measured-comparison-unavailable"]
    return select_context_result(original, comparison, event=event, features=features, effect_artifact=effect_artifact,
        effect_hash=effect_hash, approval=approval,
        factor_roles={name: "applied" if name in artifact["feature_names"] else "not_applied" for name in features["values"]},
        factor_states=dict(features["states"]), limitations=limitations)
