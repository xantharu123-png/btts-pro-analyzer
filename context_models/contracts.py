"""Closed JSON contracts for the causal context pipeline.

These checks validate data identities and shapes, not the truth of a source or
the predictive quality of a model. An unknown value stays unknown; validation
must never manufacture healthy players, observed durations or model approval.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import re

from model_artifacts import canonical_bytes


class ContextContractError(ValueError):
    """A context record violates a declared type or causal contract."""


class ContextIntegrityError(ContextContractError):
    """A persisted identity or claimed verified record cannot be validated."""


SPORTS = frozenset({"football", "tennis", "basketball", "ice_hockey", "esports"})
DATA_STATES = frozenset({"available", "missing", "stale", "conflicting", "not_applicable"})
MODEL_ROLES = frozenset({"not_applied", "experimental", "applied"})
EVIDENCE_CLASSES = frozenset({"prospective", "archival_verified", "retrospective"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]*\Z")
_PRICE_WORDS = re.compile(
    r"(^|[^a-z])(odds|prices?|bookmakers?|quotes?|quoten|roi|ev|release|approval)([^a-z]|$)",
    re.IGNORECASE,
)


def _is_price_name(name: str) -> bool:
    # Normalized producers own their exact allowlists. This independent guard
    # also catches conventional camelCase, concatenated and numbered price keys.
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    lowered = name.casefold()
    return bool(_PRICE_WORDS.search(separated)) or any(word in lowered for word in ("odds", "price", "bookmaker", "quote", "quoten"))


def canonical_timestamp(value: str | datetime) -> str:
    """Normalize an aware instant to fixed UTC microseconds before hashing."""
    try:
        instant = datetime.fromisoformat(value) if type(value) is str else value
        if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
            raise ContextContractError("timestamp must be timezone-aware")
        return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError, TypeError) as exc:
        raise ContextContractError("timestamp must be a valid timezone-aware instant") from exc


def _iso_timestamp(value: object, label: str) -> str:
    if type(value) is not str:
        raise ContextContractError(f"{label} must be a timezone-aware ISO string")
    return canonical_timestamp(value)


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_digest(value: object, label: str = "digest") -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ContextContractError(f"{label} must be a lowercase SHA-256 digest")
    return value


def require_text(value: object, label: str, *, code: bool = False) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ContextContractError(f"{label} must be a nonempty string")
    if code and _CODE.fullmatch(value) is None:
        raise ContextContractError(f"{label} must be a stable code")
    return value


def require_object(value: object, required: set[str], *, optional: set[str] = frozenset(), label: str) -> dict:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ContextContractError(f"{label} must be a JSON object")
    if set(value) - required - optional or required - set(value):
        raise ContextContractError(f"{label} has missing or unknown fields")
    return value


def require_number(value: object, label: str, *, minimum: float | None = None, maximum: float | None = None) -> int | float:
    if type(value) not in (int, float):
        raise ContextContractError(f"{label} must be a finite JSON number, not bool")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ContextContractError(f"{label} is outside its finite permitted range")
    return value


def require_list(value: object, label: str) -> list:
    if type(value) is not list:
        raise ContextContractError(f"{label} must be a JSON list")
    return value


def require_sport(value: object) -> str:
    if type(value) is not str or value not in SPORTS:
        raise ContextContractError("unsupported context sport")
    return value


def require_native_key(value: object, label: str = "event_key", *, sport: str | None = None) -> str:
    key = require_text(value, label, code=True)
    parts = key.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise ContextContractError(f"{label} requires source:sport:native-id")
    if sport is not None and parts[1] != sport:
        raise ContextContractError(f"{label} sport mismatch")
    return key


def _sport_json(value: object, *, label: str = "payload") -> object:
    """Copy finite JSON source data, without accepting executable/provider types."""
    if value is None or type(value) in (str, bool):
        return value
    if type(value) in (int, float):
        return require_number(value, label)
    if type(value) is list:
        return [_sport_json(item, label=label) for item in value]
    if type(value) is dict:
        copied = {}
        for key, item in value.items():
            require_text(key, f"{label} key")
            if _is_price_name(key):
                raise ContextContractError(f"{label} cannot contain price or release fields")
            copied[key] = _sport_json(item, label=f"{label}.{key}")
        return copied
    raise ContextContractError(f"{label} contains a non-JSON value")


OBSERVATION_FIELDS = frozenset({
    "event_key", "sport", "competition", "format", "subject_id", "kind", "source",
    "source_schema", "source_revision", "schedule_revision", "published_at",
    "publication_proof", "valid_from", "valid_until", "complete", "payload",
})


def normalize_observation(record: dict, *, observed_at: datetime) -> dict:
    """Normalize source content; the separately supplied receipt is never copied."""
    require_object(record, OBSERVATION_FIELDS, label="observation")
    if not isinstance(observed_at, datetime):
        raise ContextContractError("observed_at must be an ingestion datetime")
    receipt = canonical_timestamp(observed_at)
    row = {}
    for key in OBSERVATION_FIELDS - {"published_at", "publication_proof", "valid_from", "valid_until", "complete", "payload"}:
        row[key] = require_text(record[key], key, code=True)
    require_sport(row["sport"])
    require_native_key(row["event_key"], sport=row["sport"])
    if ":" not in row["subject_id"]:
        raise ContextContractError("subject_id requires a native identity namespace")
    row["published_at"] = None if record["published_at"] is None else _iso_timestamp(record["published_at"], "published_at")
    if row["published_at"] is not None and row["published_at"] > receipt:
        raise ContextContractError("publication cannot follow the actual receipt")
    row["valid_from"] = _iso_timestamp(record["valid_from"], "valid_from")
    row["valid_until"] = None if record["valid_until"] is None else _iso_timestamp(record["valid_until"], "valid_until")
    if row["valid_until"] is not None and row["valid_until"] <= row["valid_from"]:
        raise ContextContractError("valid_until must follow valid_from")
    if type(record["complete"]) is not bool:
        raise ContextContractError("complete must be boolean")
    row["complete"] = record["complete"]
    if type(record["payload"]) is not dict:
        raise ContextContractError("payload must be a normalized source object")
    row["payload"] = _sport_json(record["payload"])
    proof = record["publication_proof"]
    if proof is not None and type(proof) is not dict:
        raise ContextContractError("publication_proof must be an untrusted reference object or null")
    row["publication_proof"] = _sport_json(proof, label="publication_proof")
    return row


def _enum(value: object, allowed: set | frozenset, label: str):
    if type(value) is not str or value not in allowed:
        raise ContextContractError(f"unsupported {label}")
    return value


def _native_subject(value: object, label: str) -> str:
    value = require_text(value, label, code=True)
    if ":" not in value or any(not part for part in value.split(":")):
        raise ContextContractError(f"{label} requires a native identity namespace")
    return value


def _names(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    require_list(value, label)
    for name in value:
        require_text(name, label, code=True)
        if _is_price_name(name):
            raise ContextContractError(f"{label} cannot include price or release features")
    if len(set(value)) != len(value) or (not value and not allow_empty):
        raise ContextContractError(f"{label} must be nonempty and contain unique names")
    return list(value)


def _refs(value: object, label: str) -> list[str]:
    require_list(value, label)
    for ref in value:
        require_digest(ref, label)
    if value != sorted(set(value)):
        raise ContextContractError(f"{label} must be sorted unique observation hashes")
    return list(value)


def validate_coverage(value: dict) -> dict:
    require_object(value, {"version", "case"}, label="model coverage")
    return {name: require_text(value[name], f"coverage {name}", code=True) for name in ("version", "case")}


def normalize_population(value: dict) -> dict:
    """Construct a closed explicit scope; no wildcard or inferred population."""
    fields = {"sport", "competitions", "formats", "tours", "surfaces", "indoor"}
    require_object(value, fields, label="population")
    normalized = {"sport": require_sport(value["sport"])}
    for name in fields - {"sport"}:
        items = require_list(value[name], f"population {name}")
        if not items:
            raise ContextContractError("population allowed sets cannot be empty")
        for item in items:
            if name == "indoor":
                if item is not None and type(item) is not bool:
                    raise ContextContractError("population indoor must contain bool or null")
            elif item is None and name in {"tours", "surfaces"}:
                continue
            else:
                require_text(item, f"population {name}", code=True)
        unique = {canonical_bytes(item): item for item in items}
        normalized[name] = [unique[key] for key in sorted(unique)]
    if normalized["sport"] != "tennis" and any(normalized[name] != [None] for name in ("tours", "surfaces", "indoor")):
        raise ContextContractError("non-tennis scope cannot claim tennis metadata")
    if normalized["sport"] == "tennis":
        for tour in normalized["tours"]:
            if tour is not None:
                _enum(tour, {"ATP", "WTA"}, "tennis tour")
    return normalized


def validate_population(value: dict) -> dict:
    normalized = normalize_population(value)
    if canonical_bytes(normalized) != canonical_bytes(value):
        raise ContextContractError("population must already be normalized")
    return normalized


def validate_event(value: dict) -> dict:
    required = {"event_key", "sport", "competition", "format", "home_id", "away_id", "scheduled_start", "schedule_revision", "status"}
    require_object(value, required, optional={"tour", "surface", "indoor"}, label="event")
    row = dict(value)
    sport = require_sport(row["sport"])
    require_native_key(row["event_key"], sport=sport)
    for name in ("competition", "format", "schedule_revision"):
        require_text(row[name], name, code=True)
    for name in ("home_id", "away_id"):
        _native_subject(row[name], name)
    if row["home_id"] == row["away_id"]:
        raise ContextContractError("event participants must be distinct native identities")
    row["scheduled_start"] = _iso_timestamp(row["scheduled_start"], "scheduled_start")
    _enum(row["status"], {"scheduled", "cancelled", "started", "completed"}, "event status")
    if sport != "tennis" and any(key in row for key in ("tour", "surface", "indoor")):
        raise ContextContractError("tennis metadata belongs only to tennis events")
    if row.get("tour") is not None:
        _enum(row["tour"], {"ATP", "WTA"}, "tennis tour")
    if row.get("surface") is not None:
        require_text(row["surface"], "surface", code=True)
    if row.get("indoor") is not None and type(row["indoor"]) is not bool:
        raise ContextContractError("indoor must be bool or null")
    return row


def event_in_population(event: dict, population: dict) -> bool:
    event, population = validate_event(event), validate_population(population)
    return event["sport"] == population["sport"] and all(
        event.get(field) in population[allowed]
        for field, allowed in (("competition", "competitions"), ("format", "formats"),
                               ("tour", "tours"), ("surface", "surfaces"), ("indoor", "indoor"))
    )


def validate_feature_vector(value: dict) -> dict:
    require_object(value, {"version", "event_key", "cutoff", "values", "states", "refs", "coverage", "reference_hash"}, label="feature vector")
    row = dict(value)
    require_text(row["version"], "feature version", code=True)
    require_native_key(row["event_key"])
    row["cutoff"] = _iso_timestamp(row["cutoff"], "feature cutoff")
    require_digest(row["reference_hash"], "reference_hash")
    row["coverage"] = validate_coverage(row["coverage"])
    if any(type(row[name]) is not dict for name in ("values", "states", "refs")):
        raise ContextContractError("feature values, states and refs must be objects")
    keys = set(row["values"])
    if keys != set(row["states"]) or keys != set(row["refs"]):
        raise ContextContractError("feature values/states/refs must share the same names")
    _names(list(keys), "feature names", allow_empty=True)
    for name in keys:
        state = _enum(row["states"][name], DATA_STATES, "feature data state")
        number = row["values"][name]
        if number is not None:
            require_number(number, f"feature {name}")
        if state == "available" and number is None:
            raise ContextContractError("available feature needs its actual numeric value")
        if state in {"missing", "not_applicable"} and number is not None:
            raise ContextContractError("missing or inapplicable feature cannot invent a value")
        _refs(row["refs"][name], f"feature refs {name}")
    return {**row, "values": dict(row["values"]), "states": dict(row["states"]),
            "refs": {key: list(refs) for key, refs in row["refs"].items()}}


def _family(value: object) -> str:
    return _enum(value, {"football:goals:90min", "tennis:winner", "tennis:serve"}, "context model family")


def validate_parameters(value: dict, family: str) -> dict:
    family = _family(family)
    required = {"home_lambda", "away_lambda"} if family == "football:goals:90min" else (
        {"p_a"} if family == "tennis:winner" else {"hold_a", "hold_b", "best_of"})
    require_object(value, required, label="base parameters")
    for name in required:
        number = value[name]
        if name == "best_of":
            if type(number) is not int or number not in {3, 5}:
                raise ContextContractError("best_of must be the actual integer 3 or 5")
        elif name.endswith("lambda"):
            if require_number(number, name, minimum=0) <= 0:
                raise ContextContractError("count rates must be strictly positive")
        else:
            require_number(number, name, minimum=0, maximum=1)
            if name.startswith("hold_") and number in (0, 1):
                raise ContextContractError("serve probabilities must be strictly interior")
    return dict(value)


def validate_markets(value: dict, *, family: str | None = None) -> dict:
    """Validate typed probabilities, NOT an owning adapter's supported catalog."""
    if type(value) is not dict or not value:
        raise ContextContractError("markets must be a nonempty probability mapping")
    _names(list(value), "market identifiers")
    for name, probability in value.items():
        require_number(probability, f"market {name}", minimum=0, maximum=1)
    if family == "tennis:winner":
        if set(value) != {"winner_a", "winner_b"} or not math.isclose(sum(value.values()), 1, rel_tol=0, abs_tol=1e-12):
            raise ContextContractError("tennis winner markets must be exact complementary A/B outcomes")
    return dict(value)


def validate_history_refs(value: list) -> list[dict]:
    require_list(value, "history refs")
    refs = set()
    copied = []
    for row in value:
        require_object(row, {"ref", "source", "source_event_id", "native_event_key", "event_join", "roster_join"}, label="history reference")
        ref = require_digest(row["ref"], "history ref")
        if ref in refs:
            raise ContextContractError("duplicate history identity")
        refs.add(ref)
        require_text(row["source"], "history source", code=True)
        require_text(row["source_event_id"], "source event id")
        if _CODE.fullmatch(row["source_event_id"]) is None and re.fullmatch(r"-[0-9]+", row["source_event_id"]) is None:
            raise ContextContractError("source event id must be a stable native or unresolved CSV identifier")
        for name in ("event_join", "roster_join"):
            _enum(row[name], {"verified_native", "unresolved"}, name)
        if row["native_event_key"] is not None:
            key = require_native_key(row["native_event_key"], "native history event")
            namespace, _, native_id = key.split(":", 2)
            if namespace != row["source"] or native_id != row["source_event_id"]:
                raise ContextContractError("history native identity/source mismatch")
        if row["event_join"] == "verified_native" and row["native_event_key"] is None:
            raise ContextContractError("verified native event join needs its actual key")
        if row["roster_join"] == "verified_native" and row["event_join"] != "verified_native":
            raise ContextContractError("verified roster join needs verified native event join")
        copied.append(dict(row))
    return copied


def _weighted_refs(value: list, available: set[str], label: str) -> float:
    require_list(value, label)
    seen, weights = set(), []
    for row in value:
        require_object(row, {"ref", "weight"}, label=label)
        ref = require_digest(row["ref"], label)
        if ref not in available or ref in seen:
            raise ContextContractError(f"{label} has duplicate or undeclared history reference")
        seen.add(ref)
        weights.append(require_number(row["weight"], label, minimum=0, maximum=1))
    return math.fsum(weights)


def validate_reference_weights(value: dict, history_refs: list[dict], *, family: str) -> dict:
    require_object(value, {"schema", "kind"}, optional={"reason", "heads"}, label="reference weights")
    if type(value["schema"]) is not int or value["schema"] != 1:
        raise ContextContractError("unknown reference weights schema")
    if value["kind"] == "unavailable":
        require_object(value, {"schema", "kind", "reason"}, label="unavailable reference")
        require_text(value["reason"], "reference unavailability reason", code=True)
        return dict(value)
    if value["kind"] != "football-goals-v1" or family != "football:goals:90min":
        raise ContextContractError("unsupported reference weights variant")
    require_object(value, {"schema", "kind", "heads"}, label="football reference weights")
    require_object(value["heads"], {"home", "away"}, label="reference heads")
    available = {row["ref"] for row in validate_history_refs(history_refs)}
    identities = {}
    for side, head in value["heads"].items():
        require_object(head, {"outer_weights", "pair_weights", "components"}, label="reference head")
        require_object(head["outer_weights"], {"venue", "form"}, label="outer weights")
        require_object(head["pair_weights"], {"venue", "form"}, label="pair weights")
        for name, expected in (("venue", .75), ("form", .25)):
            if require_number(head["outer_weights"][name], "outer weight") != expected:
                raise ContextContractError("reference does not preserve base venue/form weights")
            pair = head["pair_weights"][name]
            require_object(pair, {"attack", "defense"}, label="pair weights")
            if any(require_number(number, "pair weight") != .5 for number in pair.values()):
                raise ContextContractError("reference does not preserve base attack/defense weights")
        require_object(head["components"], {"venue_attack", "venue_defense", "form_attack", "form_defense"}, label="reference components")
        for name, component in head["components"].items():
            require_object(component, {"team_id", "team_join", "scope", "prior_raw_weight", "metric_weights", "goals", "xg"}, label="reference component")
            if component["team_id"] is not None:
                _native_subject(component["team_id"], "reference team")
            _enum(component["team_join"], {"verified_native", "unresolved"}, "team join")
            if component["team_join"] == "verified_native" and component["team_id"] is None:
                raise ContextContractError("verified reference team needs native identity")
            is_form = name.startswith("form_")
            expected_scope = "all_form" if is_form else ("home_venue" if (side == "home") == name.endswith("attack") else "away_venue")
            if component["scope"] != expected_scope:
                raise ContextContractError("reference component venue scope mismatch")
            if require_number(component["prior_raw_weight"], "prior pseudo-count") != (3 if is_form else 4):
                raise ContextContractError("reference must preserve actual base prior pseudo-count")
            mixture = component["metric_weights"]
            require_object(mixture, {"goals", "xg"}, label="reference metric mixture")
            for number in mixture.values():
                require_number(number, "metric weight", minimum=0, maximum=1)
            expected_mixture = {"goals": 1, "xg": 0} if component["xg"] is None else {"goals": .4, "xg": .6}
            if mixture != expected_mixture:
                raise ContextContractError("reference must preserve the actual conditional goal/xG mixture")
            for metric in ("goals", "xg"):
                term = component[metric]
                if term is None and metric == "xg":
                    continue
                require_object(term, {"samples", "prior_weight", "prior_value", "prior_refs"}, label="reference metric term")
                prior = require_number(term["prior_weight"], "normalized prior weight", minimum=0, maximum=1)
                require_number(term["prior_value"], "league prior value", minimum=0)
                total = _weighted_refs(term["samples"], available, "component samples") + prior
                if not math.isclose(total, 1, rel_tol=0, abs_tol=1e-12):
                    raise ContextContractError("component sample/prior weights must sum to one")
                prior_total = _weighted_refs(term["prior_refs"], available, "league prior refs")
                if term["prior_refs"] and not math.isclose(prior_total, 1, rel_tol=0, abs_tol=1e-12):
                    raise ContextContractError("league prior references must be separately normalized")
                if prior > 0 and not term["prior_refs"]:
                    raise ContextContractError("used league prior needs actual historical references")
            identities[(side, name)] = (component["team_id"], component["team_join"])
        for role in ("attack", "defense"):
            if identities[(side, "venue_" + role)] != identities[(side, "form_" + role)]:
                raise ContextContractError("venue/form components disagree on reference team identity")
    if identities[("home", "venue_attack")] != identities[("away", "venue_defense")] or identities[("away", "venue_attack")] != identities[("home", "venue_defense")]:
        raise ContextContractError("home/away reference heads disagree on team identity")
    home_id, away_id = identities[("home", "venue_attack")][0], identities[("away", "venue_attack")][0]
    if home_id is not None and home_id == away_id:
        raise ContextContractError("reference must distinguish the two actual teams")
    return _sport_json(value, label="reference weights")


def validate_base_distribution(value: dict) -> dict:
    require_object(value, {"version", "model_hash", "event_key", "cutoff", "family", "params", "markets", "history_refs", "reference_weights"}, label="base distribution")
    row = dict(value)
    require_text(row["version"], "base version", code=True)
    require_digest(row["model_hash"], "base model hash")
    family = _family(row["family"])
    require_native_key(row["event_key"], sport=family.split(":")[0])
    row["cutoff"] = _iso_timestamp(row["cutoff"], "base cutoff")
    row["params"] = validate_parameters(row["params"], family)
    row["markets"] = validate_markets(row["markets"], family=family)
    if family == "tennis:winner" and not math.isclose(row["params"]["p_a"], row["markets"]["winner_a"], rel_tol=0, abs_tol=1e-12):
        raise ContextContractError("winner parameter and market probability mismatch")
    row["history_refs"] = validate_history_refs(row["history_refs"])
    row["reference_weights"] = validate_reference_weights(row["reference_weights"], row["history_refs"], family=family)
    return row


_HEADS = {"football:goals:90min": ({"home", "away"}, "log_rate"),
          "tennis:winner": ({"winner"}, "logit"), "tennis:serve": ({"hold_a", "hold_b"}, "logit")}


def validate_offset_fit(value: dict) -> dict:
    """One closed fitted-head schema shared by storage and numeric readers.

    Schema validity neither certifies convergence/training provenance nor
    supplies the additional artifact-level ordered features and family scope.
    """
    require_object(value, {"link", "scale", "coef", "alpha", "n_rows"}, label="offset fit")
    _enum(value["link"], {"log_rate", "logit", "identity"}, "offset link")
    scales = require_list(value["scale"], "offset scales")
    coefficients = require_list(value["coef"], "offset coefficients")
    if not scales or len(scales) != len(coefficients):
        raise ContextContractError("offset fit dimensions must be equal and nonempty")
    for scale in scales:
        require_number(scale, "offset scale", minimum=1e-8)
    for coefficient in coefficients:
        require_number(coefficient, "offset coefficient")
    require_number(value["alpha"], "offset regularization", minimum=0)
    if type(value["n_rows"]) is not int or value["n_rows"] < 2:
        raise ContextContractError("offset fit sample count must be an integer >= 2")
    return {**value, "scale": list(scales), "coef": list(coefficients)}


def validate_effect_artifact(value: dict) -> dict:
    required = {"schema", "sport", "family", "feature_version", "feature_names", "heads", "preprocessing_artifacts", "joint_calibration",
                "training_end", "training_refs_hash", "population", "coverage", "model_variant"}
    require_object(value, required, label="effect artifact")
    row = dict(value)
    if type(row["schema"]) is not int or row["schema"] != 1:
        raise ContextContractError("unknown effect schema")
    family = _family(row["family"])
    if require_sport(row["sport"]) != family.split(":")[0]:
        raise ContextContractError("effect sport/family mismatch")
    for name in ("feature_version", "model_variant"):
        require_text(row[name], name, code=True)
    row["feature_names"] = _names(row["feature_names"], "effect feature names")
    expected_heads, link = _HEADS[family]
    require_object(row["heads"], expected_heads, label="effect named heads")
    for head in row["heads"].values():
        head = validate_offset_fit(head)
        if head["link"] != link:
            raise ContextContractError("effect head link/family mismatch")
        if len(head["scale"]) != len(row["feature_names"]):
            raise ContextContractError("head dimensions must match the exact feature order")
    if type(row["preprocessing_artifacts"]) is not dict:
        raise ContextContractError("preprocessing artifacts must map names to immutable hashes")
    for name, artifact_hash in row["preprocessing_artifacts"].items():
        _names([name], "preprocessing name")
        require_digest(artifact_hash, "preprocessing artifact")
    require_object(row["joint_calibration"], {"kind"}, label="joint calibration")
    if row["joint_calibration"]["kind"] != "identity":
        raise ContextContractError("joint calibration variant requires its owning model validator")
    row["training_end"] = _iso_timestamp(row["training_end"], "effect training end")
    require_digest(row["training_refs_hash"])
    row["population"] = validate_population(row["population"])
    if row["population"]["sport"] != row["sport"]:
        raise ContextContractError("effect population sport mismatch")
    row["coverage"] = validate_coverage(row["coverage"])
    return _sport_json(row, label="effect artifact")


def validate_training_row(value: dict, *, effect_artifact: dict | None = None) -> dict:
    fields = {"event_key", "decision_at", "result_observed_at", "block", "population", "coverage", "feature_names", "x", "offset",
              "target", "trials", "base_hash", "feature_refs", "evidence_class", "family", "head"}
    require_object(value, fields, label="training row")
    row = dict(value)
    family = _family(row["family"])
    _enum(row["head"], _HEADS[family][0], "training family/head routing")
    require_native_key(row["event_key"], sport=family.split(":")[0])
    require_text(row["block"], "training time block", code=True)
    for name in ("decision_at", "result_observed_at"):
        row[name] = _iso_timestamp(row[name], name)
    if row["result_observed_at"] <= row["decision_at"]:
        raise ContextContractError("training result must be observed after its prediction decision")
    row["population"] = validate_population(row["population"])
    if row["population"]["sport"] != family.split(":")[0]:
        raise ContextContractError("training row population/family mismatch")
    row["coverage"] = validate_coverage(row["coverage"])
    row["feature_names"] = _names(row["feature_names"], "training feature names")
    require_list(row["x"], "training x")
    if len(row["x"]) != len(row["feature_names"]):
        raise ContextContractError("training feature vector dimensions mismatch")
    for number in row["x"]:
        require_number(number, "training feature")
    require_number(row["offset"], "training offset")
    require_number(row["target"], "training target", minimum=0)
    if family == "football:goals:90min":
        if row["trials"] is not None or row["target"] != int(row["target"]):
            raise ContextContractError("goal target must be a count with no binomial trials")
    else:
        require_number(row["trials"], "binomial trials", minimum=1)
        if row["trials"] != int(row["trials"]) or row["target"] != int(row["target"]) or row["target"] > row["trials"]:
            raise ContextContractError("binomial target/trials must be legal observed counts")
        if family == "tennis:winner" and row["trials"] != 1:
            raise ContextContractError("winner training requires one binary trial")
    require_digest(row["base_hash"])
    require_object(row["feature_refs"], set(row["feature_names"]), label="training feature refs")
    for name, refs in row["feature_refs"].items():
        _refs(refs, name)
    _enum(row["evidence_class"], EVIDENCE_CLASSES, "training evidence class")
    if effect_artifact is not None:
        artifact = validate_effect_artifact(effect_artifact)
        if family != artifact["family"] or row["head"] not in artifact["heads"]:
            raise ContextContractError("training row and effect family/head mismatch")
        if row["feature_names"] != artifact["feature_names"]:
            raise ContextContractError("training and artifact ordered features differ")
        if row["population"] != artifact["population"] or row["coverage"] != artifact["coverage"]:
            raise ContextContractError("training/effect scope mismatch")
        if row["result_observed_at"] > artifact["training_end"]:
            raise ContextContractError("training result arrived after artifact training cutoff")
    return _sport_json(row, label="training row")


def validate_context_result(value: dict, *, family: str, effect_artifact: dict | None = None) -> dict:
    fields = {"event_key", "base_hash", "effect_hash", "role", "factor_roles", "factor_states", "feature_refs",
              "base_params", "comparison_params", "used_params", "base_markets", "comparison_markets", "used_markets", "delta_pp", "limitations"}
    require_object(value, fields, label="context result")
    row = dict(value)
    family = _family(family)
    require_native_key(row["event_key"], sport=family.split(":")[0])
    require_digest(row["base_hash"])
    if row["effect_hash"] is not None:
        require_digest(row["effect_hash"])
    role = _enum(row["role"], MODEL_ROLES, "context model role")
    artifact = validate_effect_artifact(effect_artifact) if effect_artifact is not None else None
    if artifact is not None and (artifact["family"] != family or row["effect_hash"] is None):
        raise ContextContractError("context result/effect family or identity mismatch")
    keys = set(row["factor_roles"]) if type(row["factor_roles"]) is dict else set()
    for name in ("factor_roles", "factor_states", "feature_refs"):
        require_object(row[name], keys, label=name)
    _names(list(keys), "factor names", allow_empty=True)
    rank = {"not_applied": 0, "experimental": 1, "applied": 2}
    for name in keys:
        factor_role = _enum(row["factor_roles"][name], MODEL_ROLES, "factor model role")
        _enum(row["factor_states"][name], DATA_STATES, "factor data state")
        _refs(row["feature_refs"][name], "factor refs")
        if rank[factor_role] > rank[role]:
            raise ContextContractError("factor role exceeds the overall context role")
        if factor_role != "not_applied" and (artifact is None or name not in artifact["feature_names"]):
            raise ContextContractError("effect does not consume the claimed factor")
        if factor_role != "not_applied" and row["factor_states"][name] != "available":
            raise ContextContractError("ineligible factor cannot claim a modeled role")
    for name in ("base_params", "used_params"):
        row[name] = validate_parameters(row[name], family)
    for name in ("base_markets", "used_markets"):
        row[name] = validate_markets(row[name], family=family)
    has_comparison = row["comparison_params"] is not None or row["comparison_markets"] is not None
    if has_comparison:
        row["comparison_params"] = validate_parameters(row["comparison_params"], family)
        row["comparison_markets"] = validate_markets(row["comparison_markets"], family=family)
        if row["effect_hash"] is None:
            raise ContextContractError("comparison requires its effect identity")
    if role != "not_applied" and (not has_comparison or artifact is None):
        raise ContextContractError("modeled result role requires comparison and consumed effect")
    if role != "not_applied" and not set(artifact["feature_names"]) <= keys:
        raise ContextContractError("modeled result must retain states for every consumed feature")
    if family == "tennis:winner":
        for prefix in ("base", "used", "comparison"):
            if row[prefix + "_params"] is not None and not math.isclose(
                row[prefix + "_params"]["p_a"], row[prefix + "_markets"]["winner_a"], rel_tol=0, abs_tol=1e-12,
            ):
                raise ContextContractError("context winner parameters and markets disagree")
    prefix = "comparison" if role == "applied" else "base"
    if row["used_params"] != row[prefix + "_params"] or row["used_markets"] != row[prefix + "_markets"]:
        raise ContextContractError("used distribution contradicts the actual role")
    if set(row["used_markets"]) != set(row["base_markets"]):
        raise ContextContractError("used/base market identities mismatch")
    if has_comparison and set(row["comparison_markets"]) != set(row["base_markets"]):
        raise ContextContractError("comparison/base market identities mismatch")
    require_object(row["delta_pp"], set(row["used_markets"]), label="context probability deltas")
    for name, delta in row["delta_pp"].items():
        require_number(delta, "probability delta", minimum=-100, maximum=100)
        expected = 100 * (row["used_markets"][name] - row["base_markets"][name])
        if not math.isclose(delta, expected, rel_tol=0, abs_tol=1e-10):
            raise ContextContractError("stored probability delta is not the actually used change")
    require_list(row["limitations"], "context limitations")
    for limitation in row["limitations"]:
        require_text(limitation, "context limitation")
    return _sport_json(row, label="context result")
