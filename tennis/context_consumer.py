"""Read the same immutable winner revision for normal and RisikoBet cards.

No source, model decoding/fitting/prediction, approval creation or publication.
The producer/D4 own source truth and replay. This seam binds the consumer's
actual Shadow row to the saved A1 original and B3 winner only, never set markets.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from context_consumers import _read_context_snapshot
from context_copy import public_context_summary
from context_links import ContextReference
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, require_object,
)
from context_models.dataset import _artifact
from context_models.experiments import _artifact_created_at
from context_models.tennis_live import (
    MARKETS, ORIGINAL_ARTIFACT_KIND, validate_context_model,
    validate_live_winner_origin, validate_original_publication,
)
from context_transport import project_context_market
from model_artifacts import canonical_bytes
from tennis.state_codec import _STATE_KEYS


def _same(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def _decision(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContextIntegrityError("live Shadow decision must be its actual numeric UTC clock")
    try:
        return canonical_timestamp(datetime.fromtimestamp(value, timezone.utc))
    except (ValueError, OverflowError, OSError) as exc:
        raise ContextIntegrityError("invalid live Shadow decision") from exc


def _object(raw):
    # Only these explicit legacy forms mean absence. False/0/containers are
    # present malformed metadata, never permission to use a rounded fallback.
    if raw is None or (type(raw) is str and raw == ""):
        return {}
    if type(raw) is not str:
        raise ContextIntegrityError("stored tennis context must be JSON text")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContextIntegrityError("duplicate stored tennis context key")
            result[key] = value
        return result
    def invalid(_):
        raise ContextIntegrityError("invalid stored tennis context constant")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (TypeError, ValueError) as exc:
        raise ContextIntegrityError("invalid stored tennis context") from exc
    if type(value) is not dict:
        raise ContextIntegrityError("stored tennis context must be an object")
    return value


def _state_header(payload, *, tour):
    """Bind the known A1 header, without decoding or replaying its model.

    The state codec owns this closed schema. Its nested Elo/Serve values,
    training provenance and model replay still belong to the producer/D4.
    """
    require_object(payload, {"schema", "training_cutoff", "state"}, label="tennis state envelope")
    state = require_object(payload["state"], _STATE_KEYS, label="tennis state")
    if (type(payload["schema"]) is not int or payload["schema"] != 1
            or type(state["schema"]) is not int or state["schema"] != 1
            or type(state["tour"]) is not str or state["tour"] != tour):
        raise ContextIntegrityError("referenced tennis state header differs from the original tour")


def _artifact_schema(connection):
    actual = connection.execute("SELECT type FROM sqlite_master WHERE name='artifacts'").fetchall()
    expected = [(0, "digest", "TEXT", 0, None, 1, 0), (1, "kind", "TEXT", 1, None, 0, 0),
                (2, "payload", "BLOB", 1, None, 0, 0), (3, "created_at", "TEXT", 1, None, 0, 0)]
    if actual != [("table",)] or connection.execute("PRAGMA table_xinfo(artifacts)").fetchall() != expected:
        raise ContextIntegrityError("referenced original artifact schema is invalid")


def _groups(features):
    # Explicit owning feature names: unknown/new names are not guessed into a
    # medical or numerical explanation. Exact recovery is not a lower bound.
    names = set(features)
    workload = [f"observed_{metric}_{days}d_{side}"
        for metric in ("sets", "games", "minutes") for days in (1, 3, 7) for side in ("a", "b")]
    recovery = [f"observed_recovery_{kind}_hours_{side}" for kind in ("exact", "minimum") for side in ("a", "b")]
    return {key: [name for name in values if name in names] for key, values in
            (("workload", workload), ("recovery", recovery)) if any(name in names for name in values)}


def load_tennis_winner_context(row: dict, *, path: Path | None = None) -> dict | None:
    """Absent legacy field is optional; a present invalid link is an error.

    Read one snapshot plus its actual original/state artifacts in a single
    read-only transaction. Both probabilities retain the stored full precision.
    No fallback to rounded/older predictions and no wall-clock cache are used.
    """
    context = _object(row.get("context_json"))
    if "context_model" not in context:
        return None
    sidecar = validate_context_model(context["context_model"])
    event, cutoff, reference = sidecar["event"], sidecar["cutoff"], sidecar["reference"]
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    try:
        appended = canonical_timestamp(row["append_observed_at"])
        if (row["fixture_source"] != "ESPN" or row["tour"] != event["tour"]
                or event["event_key"] != f"espn:tennis:{row['tour']}:match:{row['provider_event_id']}"
                or canonical_timestamp(row["scheduled_start_utc"]) != event["scheduled_start"]
                or _decision(row["created_utc"]) != cutoff or appended < cutoff):
            raise ContextIntegrityError("shared winner belongs to a different Shadow event/decision")
        with _read_context_snapshot(Path(path), reference, expected_event=event,
                expected_cutoff=cutoff) as (connection, payload):
            base = validate_live_winner_origin(payload["base"], event)
            origin = base["reference_weights"]
            _artifact_schema(connection)
            original = _artifact(connection, sidecar["original_artifact_hash"], ORIGINAL_ARTIFACT_KIND, latest=appended)
            published = _artifact_created_at(connection, sidecar["original_artifact_hash"])
            validate_original_publication(original["payload"], created_at=published)
            if not _same(original["payload"], {"schema": 1, "origin": origin}):
                raise ContextIntegrityError("consumer sidecar refers to another original publication")
            # Only read/check immutable A1 bytes and actual publication time;
            # native historical identity/model replay remain producer/D4 work.
            state = _artifact(connection, base["model_hash"], "tennis-tour-state", latest=cutoff)
            _state_header(state["payload"], tour=event["tour"])
            model_inputs = context.get("model_inputs")
            if type(model_inputs) is not dict or model_inputs.get("model_artifact_hash") != base["model_hash"]:
                raise ContextIntegrityError("Shadow model differs from its saved original")
            expected_inputs = {"player_a": row["player_a"], "player_b": row["player_b"],
                "surface": row["surface"] if row["surface"] in ("Hard", "Clay", "Grass", "Carpet") else None,
                "best_of": row["best_of"], "tour": row["tour"], "indoor": model_inputs.get("indoor")}
            if (any(not _same(origin["inputs"][key], value) for key, value in expected_inputs.items())
                    or any(not _same(round(origin["values"][key], 4), row[column])
                           for key, column in (("p_a_raw", "p_raw"), ("p_a_cal", "p_cal")))):
                raise ContextIntegrityError("Shadow row differs from its exact original inputs/probabilities")
            projections, summaries = {}, {}
            for side, market in MARKETS.items():
                projections[side] = project_context_market(payload, reference, market)
                summary = public_context_summary({**payload["result"], "selected_market": market,
                    "factor_groups": _groups(payload["features"]["values"])})
                basis = ("Spielstärke und Belag im Grundmodell berücksichtigt. "
                         if origin["inputs"]["surface"] is not None else
                         "Spielstärke im Grundmodell; Belag nicht eindeutig zugeordnet. ")
                summaries[side] = basis + summary["summary"]
            result = {"context_ref": ContextReference.from_dict(reference),
                "probabilities": {side: projection["used_probability"] for side, projection in projections.items()},
                "base_probabilities": {side: projection["base_probability"] for side, projection in projections.items()},
                "delta_pp": {side: projection["delta_pp"] for side, projection in projections.items()},
                "summaries": summaries, "event": deepcopy(event), "cutoff": cutoff}
        return result
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ContextContractError):
            raise
        raise ContextIntegrityError("invalid revision-bound live tennis consumer input") from exc
