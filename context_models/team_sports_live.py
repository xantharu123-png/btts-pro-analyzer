"""Same-call originals, not native receipt resolution or empirical approval.

The pure validators check a closed, price-free captured model and its forward
law. Only the explicitly named offline replay fits a target. Neither a public
digest nor a caller-supplied receipt link proves that an external source supplied
the data. P4b/D4 own that separate resolution and publication boundary.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math

import numpy as np

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_number, require_object, validate_event,
)
from context_models.ice_hockey import hockey_distribution, hockey_event, hockey_scope
from context_models.team_sports import basketball_event, margin_distribution
from model_artifacts import canonical_bytes

ORIGINAL_ARTIFACT_KIND = "team-sports-live-original-v1"
RECEIPT_KIND = "team-sports-live-receipt-refs-v1"
BASE_VERSIONS = {"basketball": "basketball-live-original-margin-v1",
                 "ice_hockey": "hockey-live-original-poisson-v1"}
ORIGIN_KINDS = {"basketball": "basketball-live-margin-origin-v1",
                "ice_hockey": "hockey-live-poisson-origin-v1"}
FAMILIES = {"basketball": "basketball:margin:including_ot",
            "ice_hockey": "ice_hockey:regulation_goals"}
MODEL_RECIPE = "sports-prematch-inline-captured-fit-v1"
MAX_RAW_HISTORY = 20000
# All actual legacy selection/model inputs, plus explicitly separate native
# declarations. Display/bookmaker/price data are not part of this projection.
RAW_FIELDS = frozenset({"provider", "source", "competition_id", "league_id", "competition",
    "league", "tournament", "provider_event_id", "event_id", "game_id", "match_id", "id",
    "starts_at", "start_time", "scheduled_at", "home_team_id", "away_team_id", "team1_id",
    "team2_id", "home_team", "away_team", "team1", "team2", "neutral_site", "game_type",
    "status", "sport", "result_observed_at", "observed_at", "completed_at", "winner_side",
    "home_score_final", "away_score_final", "home_score", "away_score", "result_scope",
    "last_period_type", "season", "context_rules", "context_rule_version"})


@dataclass(frozen=True)
class CapturedTeamSportOriginal:
    original: dict
    base: dict | None
    context_unavailable_reason: str | None


def _exact(a, b):
    try:
        return canonical_bytes(a) == canonical_bytes(b)
    except (TypeError, ValueError) as exc:
        raise ContextContractError("captured original comparison needs finite JSON") from exc


def _json(value):
    """Encode actual datetime/tuple/numpy-float values, never stringify objects."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ContextContractError("original input keys must be strings")
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, np.floating):
        value = float(value)
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ContextContractError("original projection needs finite JSON values")


def _project(row):
    if not isinstance(row, Mapping):
        return None  # ignored by the actual legacy normalizer, not a sport fact
    selected = {key: row[key] for key in RAW_FIELDS if key in row}
    # Source rules are the one nested supported declaration. Its unrelated
    # fields (including price metadata) were never baseline model inputs.
    if isinstance(selected.get("context_rules"), Mapping):
        selected["context_rules"] = {key: selected["context_rules"][key] for key in
            ("regulation_minutes", "regulation_periods", "overtime_period_minutes")
            if key in selected["context_rules"]}
    for key, item in selected.items():
        if key != "context_rules" and isinstance(item, (Mapping, list, tuple)):
            raise ContextContractError("unsupported structured original input")
    return _json(selected)


def _clock(value):
    if type(value) is not str or canonical_timestamp(value) != value:
        raise ContextContractError("captured decision clock must be canonical UTC")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _float(value, label, *, positive=False):
    if type(value) is not float:
        raise ContextContractError(f"{label} must be the actual JSON float")
    require_number(value, label)
    if positive and value <= 0:
        raise ContextContractError(f"{label} must be positive")
    return value


def _binding(value, size):
    require_object(value, {"schema", "kind", "event_receipt", "history_receipts", "artifact_refs"},
                   label="unresolved original receipt links")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != RECEIPT_KIND:
        raise ContextContractError("unknown original receipt-link version")
    if value["event_receipt"] is not None:
        require_digest(value["event_receipt"], "event receipt link")
    if type(value["history_receipts"]) is not list or type(value["artifact_refs"]) is not list:
        raise ContextContractError("receipt/artifact links must be lists")
    positions = []
    for item in value["history_receipts"]:
        require_object(item, {"input_index", "receipt"}, label="actual raw-input receipt link")
        position = item["input_index"]
        if type(position) is not int or not 0 <= position < size:
            raise ContextContractError("receipt input index is outside actual raw history")
        positions.append(position)
        require_digest(item["receipt"], "history receipt link")
    if positions != sorted(set(positions)):
        raise ContextContractError("history receipt indexes must be unique and ordered")
    for item in value["artifact_refs"]:
        require_digest(item, "unresolved artifact link")
    if value["artifact_refs"] != sorted(set(value["artifact_refs"])):
        raise ContextContractError("artifact links must be unique and ordered")
    return deepcopy(value)


def _actual_parts(sport, inputs, decision):
    import sports_prematch as legacy
    require_object(inputs, {"event", "history"}, label="price-free actual inputs")
    if type(inputs["event"]) is not dict or type(inputs["history"]) is not list or len(inputs["history"]) > MAX_RAW_HISTORY:
        raise ContextContractError("captured input inventory is malformed or too large")
    if not _exact(_project(inputs["event"]), inputs["event"]):
        raise ContextContractError("unknown or price-bearing target input field")
    for row in inputs["history"]:
        if not _exact(_project(row), row):
            raise ContextContractError("unknown or price-bearing history input field")
    identity, _ = legacy._identity(sport, inputs["event"], decision)
    matches = legacy._normalise_history(sport, identity, inputs["history"], decision) if identity else ()
    return identity, matches


def _input_hash(version, sport, identity, matches):
    record = {"version": version, "sport": sport,
              "identity": _json(asdict(identity)) if identity else None,
              "matches": [_json(asdict(item)) for item in matches]}
    # Exact legacy hash recipe, including its +00:00 clocks; not B1 hashing.
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _fit_shape(value, sport, identity, matches):
    if value is None:
        return None
    require_object(value, {"sport", "teams", "coefficients", "residual_scale", "overtime_home_rate", "overtime_games"},
                   label="actual captured inline fit")
    teams = sorted({team for match in matches for team in (match.home, match.away)})
    if value["sport"] != sport or type(value["teams"]) is not list or value["teams"] != teams or not teams:
        raise ContextIntegrityError("fit team order is not the actual design")
    width = len(teams) + 1 if sport == "basketball" else 2 * len(teams) + 2
    if type(value["coefficients"]) is not list or len(value["coefficients"]) != width:
        raise ContextContractError("captured fit has incorrect parameter dimensions")
    for number in value["coefficients"]:
        _float(number, "fit coefficient")
    if type(value["overtime_games"]) is not int or value["overtime_games"] < 0:
        raise ContextContractError("OT count must be an actual integer")
    if sport == "basketball":
        _float(value["residual_scale"], "captured residual scale", positive=True)
        if value["overtime_home_rate"] is not None or value["overtime_games"] != 0:
            raise ContextContractError("basketball fit cannot inherit a hockey OT model")
    else:
        if value["residual_scale"] is not None:
            raise ContextContractError("hockey fit cannot inherit a margin scale")
        if value["overtime_home_rate"] is not None:
            _float(value["overtime_home_rate"], "original OT probability")
            if not 0 <= value["overtime_home_rate"] <= 1:
                raise ContextContractError("invalid original OT probability")
        if value["overtime_games"] != sum(match.extra_time and not match.neutral for match in matches):
            raise ContextIntegrityError("original OT count differs from actual contributing games")
    if identity is None:
        raise ContextIntegrityError("captured fit has no target identity")
    import sports_prematch as legacy
    if not legacy._enough_for_event(matches, identity.home, identity.away) or len(teams) > legacy.MAX_TEAMS:
        raise ContextIntegrityError("captured fit cannot have bypassed original model eligibility")
    return value


def _forward(fit, identity):
    if fit is None:
        return None, {}
    teams, coefs = fit["teams"], fit["coefficients"]
    if identity.home not in teams or identity.away not in teams:
        return None, {}
    h, a = teams.index(identity.home), teams.index(identity.away)
    try:
        if fit["sport"] == "basketball":
            margin = coefs[h] - coefs[a] + (0.0 if identity.neutral else coefs[-1])
            values = {"expected_margin": margin, "residual_scale": fit["residual_scale"]}
            probability = margin_distribution(margin, fit["residual_scale"])["home_win"]
        else:
            if fit["overtime_home_rate"] is None or identity.neutral:
                return None, {}
            t = len(teams)
            home_effect = coefs[-1] / 2.0
            home = math.exp(coefs[-2] + coefs[h] + coefs[t+a] + home_effect)
            away = math.exp(coefs[-2] + coefs[a] + coefs[t+h] - home_effect)
            markets = hockey_distribution(home, away, fit["overtime_home_rate"])
            values = {"expected_home_goals": home, "expected_away_goals": away,
                "p_home_regulation": markets["home_reg"], "p_draw_regulation": markets["draw_reg"],
                "overtime_home_rate": fit["overtime_home_rate"]}
            probability = markets["home_inclusive"]
    except (ArithmeticError, ValueError, RuntimeError) as exc:
        raise ContextContractError("captured original forward law is not representable") from exc
    return probability if math.isfinite(probability) and 0 < probability < 1 else None, values


def _auxiliary(sport, fit, identity, matches):
    if fit is None or identity is None:
        return None
    if sport == "ice_hockey":
        return {"kind": "hockey-inline-contributing-sample-indices-v1",
            "role": "model-design-rows-not-native-receipts",
            "regulation_outcomes": "legacy-one-winning-goal-subtraction-not-observed-period-totals",
            "sample_indices_home": [i for i, m in enumerate(matches) if identity.home in (m.home, m.away)],
            "sample_indices_away": [i for i, m in enumerate(matches) if identity.away in (m.home, m.away)]}
    teams = fit["teams"]
    x = np.array([[float(m.home == team) - float(m.away == team) for team in teams]
                   + [float(not m.neutral)] for m in matches], dtype=np.float64)
    q = np.array([float(identity.home == team) - float(identity.away == team) for team in teams]
                 + [float(not identity.neutral)], dtype=np.float64)
    penalty = [5.] * len(teams) + [1e-8]
    try:
        # Auxiliary influence only. No target y, coefficient solve, scale fit,
        # inverse Hessian or positive renormalization in this path.
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            influences = q @ np.linalg.solve(x.T @ x + np.diag(penalty), x.T)
    except (ArithmeticError, ValueError, np.linalg.LinAlgError) as exc:
        raise ContextContractError("captured signed influence is not representable") from exc
    if not np.isfinite(influences).all():
        raise ContextContractError("captured signed influence is not finite")
    return {"kind": "basketball-inline-signed-ridge-influence-v1",
        "role": "model-design-rows-not-native-receipts", "penalty": penalty,
        "influences": influences.tolist()}


def _native_binding(sport, event, raw, identity):
    """Raw native declarations never inherit the legacy model's defaults."""
    if event is None:
        return None, "native-event-unavailable", False
    current = validate_event(event)
    if not _exact(current, event) or current["sport"] != sport:
        raise ContextIntegrityError("supplied native event is not canonical for this sport")
    if identity is None:
        return None, "original-model-unavailable", False
    from context_models import team_sports as bb
    from context_models import ice_hockey as nhl
    if (current["scheduled_start"] != canonical_timestamp(identity.start) or current["status"] != "scheduled"
            or current["competition"] != identity.competition):
        raise ContextIntegrityError("current native schedule/status/competition differs from original input")
    source = identity.provider
    raw_id = raw.get("provider_event_id") or raw.get("event_id") or raw.get("game_id") or raw.get("match_id") or raw.get("id")
    if sport == "basketball":
        if source not in {"espn", "euroleague"}:
            return None, "native-source-unsupported", False
        try:
            expected_id = bb._source_id(raw_id, "actual target ID")
            expected_key = bb.native_event(f"{source}:basketball:{expected_id}", source)
        except ContextContractError:
            return None, "native-target-event-identity-unavailable", False
        try:
            expected_sides = {side: bb._reported_team(raw, side, source) for side in ("home", "away")
                              if raw.get(side+"_team_id") or raw.get("team1_id" if side == "home" else "team2_id")}
        except ContextContractError:
            return None, "native-target-team-identity-unavailable", False
    else:
        if source != "nhl":
            return None, "native-source-unsupported", False
        try:
            expected_id = nhl._integer_identity(raw_id)
            expected_key = "nhl:ice_hockey:" + str(expected_id)
            nhl.native_id(expected_key, "")
        except ContextContractError:
            return None, "native-target-event-identity-unavailable", False
        expected_sides = {}
        for side in ("home", "away"):
            team = raw.get(side+"_team_id") or raw.get("team1_id" if side == "home" else "team2_id")
            if team is not None:
                try:
                    expected_sides[side] = "nhl:ice_hockey:team:" + str(nhl._integer_identity(team))
                except ContextContractError:
                    return None, "native-target-team-identity-unavailable", False
    if current["event_key"] != expected_key or any(current[side+"_id"] != team for side, team in expected_sides.items()):
        raise ContextIntegrityError("actual raw native target identity/orientation differs")
    if len(expected_sides) != 2 or not identity.home.startswith("id:") or not identity.away.startswith("id:"):
        return None, "native-target-team-identity-unavailable", False
    if sport == "basketball":
        if current["format"] not in bb.FORMATS:
            return None, "native-format-unsupported", False
        basketball_event(current)
        if (source, identity.competition) != bb.FORMATS[current["format"]][:2]:
            raise ContextIntegrityError("basketball native format/source differs")
    else:
        if current["format"] not in nhl.FORMATS or identity.variant == "1":
            return None, "native-format-unsupported", False
        hockey_event(current)
        if identity.variant != str(nhl.FORMATS[current["format"]]):
            raise ContextIntegrityError("actual hockey game type differs from native format")
    if type(raw.get("neutral_site")) is not bool:
        return None, "native-neutral-site-unavailable", True
    if raw["neutral_site"] != identity.neutral:
        raise ContextIntegrityError("raw native neutral site differs from original execution")
    try:
        if sport == "basketball":
            scope = bb._scope({"season": raw.get("season"), "rules": raw.get("context_rules")}, current["format"])
            scope = {**scope, "neutral_site": raw["neutral_site"]}
        else:
            scope = hockey_scope({"season": raw.get("season"), "game_type": raw.get("game_type"),
                "neutral_site": raw["neutral_site"], "rule_version": raw.get("context_rule_version")}, current)
    except ContextContractError:
        return None, "native-scope-unreviewed-or-missing", True
    return scope, "native-receipts-unresolved", True


def validate_captured_team_sport_original(value):
    """Pure internal consistency only; never DB/source or fitted provenance."""
    import sports_prematch as legacy
    require_object(value, {"schema", "kind", "sport", "cutoff", "event", "event_hash", "inputs", "inputs_hash",
        "model", "outputs", "native_scope", "receipt_binding", "source_resolution", "auxiliary_reference"},
        label="same-call team-sport original")
    if (type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != ORIGINAL_ARTIFACT_KIND
            or type(value["sport"]) is not str or value["sport"] not in FAMILIES):
        raise ContextContractError("unknown captured team-sport original version")
    sport = value["sport"]
    decision = _clock(value["cutoff"])
    if value["source_resolution"] != "unresolved":
        raise ContextContractError("P4a receipt links are not an owning source resolver")
    model = require_object(value["model"], {"version", "recipe", "input_hash", "identity", "matches", "fit"}, label="captured inline model")
    if model["version"] != legacy.MODEL_VERSION or model["recipe"] != MODEL_RECIPE:
        raise ContextContractError("unsupported original model recipe/version")
    identity, matches = _actual_parts(sport, value["inputs"], decision)
    expected_model = {"identity": _json(asdict(identity)) if identity else None,
        "matches": [_json(asdict(match)) for match in matches],
        "input_hash": _input_hash(model["version"], sport, identity, matches)}
    if any(not _exact(model[key], expected) for key, expected in expected_model.items()):
        raise ContextIntegrityError("captured normalization or actual original input hash differs")
    if (value["inputs_hash"] != digest(value["inputs"])
            or value["event_hash"] != (digest(value["event"]) if value["event"] is not None else None)):
        raise ContextIntegrityError("captured full input/native event binding differs")
    fit = _fit_shape(model["fit"], sport, identity, matches)
    outputs = require_object(value["outputs"], {"p_home", "p_away", "values", "missing"}, label="actual original output")
    p_home, values = _forward(fit, identity)
    expected = {"p_home": p_home, "p_away": 1.0-p_home if p_home is not None else None, "values": values}
    if any(not _exact(outputs[key], item) for key, item in expected.items()):
        raise ContextIntegrityError("captured original outputs differ from the actual fit's forward law")
    if type(outputs["missing"]) is not list or any(type(item) is not str or not item for item in outputs["missing"]):
        raise ContextContractError("original missing-data explanations must be actual text")
    if (p_home is None) != bool(outputs["missing"]):
        raise ContextIntegrityError("missing model and original missing-data status differ")
    scope, _, _ = _native_binding(sport, value["event"], value["inputs"]["event"], identity)
    if not _exact(scope, value["native_scope"]):
        raise ContextIntegrityError("native scope cannot be supplied by a canonical model default")
    _binding(value["receipt_binding"], len(value["inputs"]["history"]))
    if not _exact(value["auxiliary_reference"], _auxiliary(sport, fit, identity, matches)):
        raise ContextIntegrityError("original auxiliary reference differs from its actual design")
    return deepcopy(value)


def _base_from_original(original):
    sport = original["sport"]
    p, values = original["outputs"]["p_home"], original["outputs"]["values"]
    if p is None:
        return None
    if sport == "basketball":
        params = deepcopy(values)
        markets = {"home_win": p, "away_win": original["outputs"]["p_away"]}
    else:
        params = {"home_lambda": values["expected_home_goals"], "away_lambda": values["expected_away_goals"],
                  "overtime_home_probability": values["overtime_home_rate"]}
        markets = hockey_distribution(*params.values())
    model_hash = digest({"kind": MODEL_RECIPE, "sport": sport, "model": original["model"]})
    return {"version": BASE_VERSIONS[sport], "model_hash": model_hash, "event_key": original["event"]["event_key"],
        "cutoff": original["cutoff"], "family": FAMILIES[sport], "params": params, "markets": markets,
        "history_refs": [], "reference_weights": {"schema": 1, "kind": ORIGIN_KINDS[sport], "original": deepcopy(original)}}


def validate_team_sport_live_reference(value, history_refs):
    require_object(value, {"schema", "kind", "original"}, label="captured live original reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] not in ORIGIN_KINDS.values():
        raise ContextContractError("unknown captured original reference kind")
    if type(history_refs) is not list or history_refs != []:
        raise ContextContractError("unresolved links cannot certify native/roster history refs")
    original = validate_captured_team_sport_original(value["original"])
    if value["kind"] != ORIGIN_KINDS[original["sport"]]:
        raise ContextContractError("captured original reference sport differs")
    return deepcopy(value)


def validate_team_sport_live_origin(base, event=None):
    # Called from the shared shape validator too: do not recursively call it.
    require_object(base, {"version", "model_hash", "event_key", "cutoff", "family", "params", "markets", "history_refs", "reference_weights"},
                   label="captured original base")
    ref = validate_team_sport_live_reference(base["reference_weights"], base["history_refs"])
    original = ref["original"]
    identity, _ = _actual_parts(original["sport"], original["inputs"], _clock(original["cutoff"]))
    _, _, compatible = _native_binding(original["sport"], original["event"], original["inputs"]["event"], identity)
    if not compatible or original["outputs"]["p_home"] is None:
        raise ContextContractError("captured model has no compatible available native base")
    if event is not None and not _exact(validate_event(event), original["event"]):
        raise ContextIntegrityError("supplied full native Event differs from captured original")
    if not _exact(_base_from_original(original), base):
        raise ContextIntegrityError("original base parameters/markets/model/event differ from capture")
    return deepcopy(base)


def _build(sport, original, *, event, receipt_binding):
    import sports_prematch as legacy
    if type(original) is not legacy.OriginalPrematch or original.sport != sport:
        raise ContextContractError("builder requires the actual same-sport OriginalPrematch capture")
    if (type(original.prediction) is not legacy.PrematchPrediction
            or original.fitted is not None and type(original.fitted) is not legacy._Fit
            or original.identity is not None and type(original.identity) is not legacy._Identity
            or type(original.matches) is not tuple or any(type(item) is not legacy._Match for item in original.matches)
            or type(original.raw_history) is not tuple):
        raise ContextContractError("captured original parts have been replaced with untyped objects")
    if original.prediction.sport != sport or original.prediction.input_hash != original.input_hash:
        raise ContextIntegrityError("captured prediction and model identity differ")
    if not _exact(original.prediction.p_home, original.probability):
        raise ContextIntegrityError("captured prediction and original probability differ")
    if len(original.raw_history) > MAX_RAW_HISTORY:
        raise ContextContractError("raw original history exceeds the capture bound")
    inputs = {"event": _project(original.raw_event), "history": [_project(row) for row in original.raw_history]}
    model = {"version": original.prediction.model_version, "recipe": MODEL_RECIPE, "input_hash": original.input_hash,
        "identity": _json(asdict(original.identity)) if original.identity else None,
        "matches": [_json(asdict(row)) for row in original.matches],
        "fit": _json(asdict(original.fitted)) if original.fitted else None}
    native = validate_event(event) if event is not None else None
    if event is not None and not _exact(native, event):
        raise ContextContractError("supplied native Event must already be canonical")
    scope, reason, compatible = _native_binding(sport, native, inputs["event"], original.identity)
    if receipt_binding is None:
        receipt_binding = {"schema": 1, "kind": RECEIPT_KIND, "event_receipt": None, "history_receipts": [], "artifact_refs": []}
    value = {"schema": 1, "kind": ORIGINAL_ARTIFACT_KIND, "sport": sport,
        "cutoff": canonical_timestamp(original.as_of), "event": native, "event_hash": digest(native) if native else None,
        "inputs": inputs, "inputs_hash": digest(inputs), "model": model,
        "outputs": {"p_home": original.prediction.p_home, "p_away": original.prediction.p_away,
            "values": _json(dict(original.values)), "missing": list(original.prediction.missing)},
        "native_scope": scope, "receipt_binding": deepcopy(receipt_binding), "source_resolution": "unresolved",
        "auxiliary_reference": _auxiliary(sport, model["fit"], original.identity, original.matches)}
    validated = validate_captured_team_sport_original(value)
    base = _base_from_original(validated) if compatible and original.probability is not None else None
    if base is not None:
        validate_team_sport_live_origin(base, native)
    if original.probability is None:
        reason = "original-model-unavailable"
    return CapturedTeamSportOriginal(deepcopy(validated), deepcopy(base), reason)


def build_basketball_live_original(original, *, event=None, receipt_binding=None):
    return _build("basketball", original, event=event, receipt_binding=receipt_binding)


def build_hockey_live_original(original, *, event=None, receipt_binding=None):
    return _build("ice_hockey", original, event=event, receipt_binding=receipt_binding)


def replay_team_sport_live_origin(base):
    """Explicit fresh offline model replay; still no native source resolution."""
    import sports_prematch as legacy
    original_base = validate_team_sport_live_origin(base)
    origin = original_base["reference_weights"]["original"]
    identity, matches = _actual_parts(origin["sport"], origin["inputs"], _clock(origin["cutoff"]))
    actual_fit = getattr(legacy._fit, "__wrapped__", legacy._fit)(origin["sport"], matches)
    if actual_fit is None or not _exact(_json(asdict(actual_fit)), origin["model"]["fit"]):
        raise ContextIntegrityError("offline original fitted coefficients/scale/OT replay differs")
    result = legacy._predict(actual_fit, identity.home, identity.away, identity.neutral)
    if result is None or not _exact(result[0], origin["outputs"]["p_home"]) or not _exact(_json(result[1]), origin["outputs"]["values"]):
        raise ContextIntegrityError("offline original prediction replay differs")
    return deepcopy(original_base)
