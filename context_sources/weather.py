"""CPU-only internal weather transport, NOT an implemented provider adapter.

The owning ingestion path must establish source, actual HTTP receipt, venue and
clock semantics before calling this boundary. A valid dictionary or hash does
not independently prove a provider fact. No currently reviewed OpenWeather
adapter supplies this complete transport, and no forecast archive is approved.
In particular, a forecast-valid point is never promoted to an issue time or an
invented three-hour applicability interval.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, normalize_observation,
    require_digest, require_number, require_object, require_text, validate_event,
)

SOURCE_SCHEMA = "football-weather-transport-v1"
KINDS = frozenset({"forecast", "forecast_archive", "actual", "reanalysis"})
METRICS = ("temperature_c", "wind_mps", "rain_3h_mm", "snow_3h_mm")
UNITS = {"temperature": "degC", "wind": "m/s", "precipitation": "mm/3h"}
FIELDS = {"schema", "source_schema", "source", "source_kind", "event_hash", "venue", "units",
          "issued_at", "valid_at", "valid_from", "valid_until", *METRICS}
VENUE_FIELDS = {"venue_id", "venue_revision", "location_type", "coordinate_source", "coordinate_revision",
                "latitude", "longitude", "roof", "roof_revision"}


def weather_window(*, issued_at: datetime, valid_from: datetime, valid_until: datetime,
                   decision_at: datetime, kickoff: datetime) -> bool:
    """Eligibility of genuinely evidenced instants; no clock imputation."""
    values = (issued_at, valid_from, valid_until, decision_at, kickoff)
    if any(not isinstance(value, datetime) for value in values):
        raise ContextContractError("weather eligibility requires five aware datetimes")
    issue, start, end, decision, match = map(canonical_timestamp, values)
    if start >= end:
        raise ContextContractError("weather interval must be nonempty and ordered")
    return issue <= decision < match and start <= match < end


def weather_metadata_gap(payload: dict) -> str | None:
    """Versioned strict outdoor-forecast cohort, separate from source values."""
    if payload["source_kind"] != "forecast":
        return "not-current-forecast"
    if payload["issued_at"] is None:
        return "missing-issue-time"
    if payload["valid_from"] is None or payload["valid_until"] is None:
        return "missing-valid-interval"
    venue = payload["venue"]
    if (venue["venue_id"] is None or venue["venue_revision"] is None or venue["location_type"] != "venue"
            or venue["coordinate_source"] is None or venue["coordinate_revision"] is None
            or venue["latitude"] is None or venue["longitude"] is None):
        return "missing-exact-venue"
    if venue["roof"] == "unknown" or venue["roof_revision"] is None:
        return "missing-roof-state"
    return None


def validate_weather_payload(value: dict, *, observed_at: str) -> dict:
    """Closed numeric allowlist; shape validation is not source certification."""
    require_object(value, FIELDS, label="internal weather transport")
    row = deepcopy(value)
    if type(row["schema"]) is not int or row["schema"] != 1 or row["source_schema"] != SOURCE_SCHEMA:
        raise ContextContractError("unreviewed weather transport schema")
    require_text(row["source"], "weather source identity", code=True)
    if type(row["source_kind"]) is not str or row["source_kind"] not in KINDS:
        raise ContextContractError("weather source kinds cannot be interchanged")
    require_digest(row["event_hash"], "weather event revision")
    if type(row["units"]) is not dict or row["units"] != UNITS:
        raise ContextContractError("weather values require explicit unmixed Celsius/m-s/mm-per-3h units")
    venue = require_object(row["venue"], VENUE_FIELDS, label="weather venue evidence")
    if venue["venue_id"] is not None and (type(venue["venue_id"]) is not str or re.fullmatch(
            r"api-football:venue:[1-9][0-9]*", venue["venue_id"]) is None):
        raise ContextContractError("weather venue needs its native identity or null")
    for field in ("venue_revision", "coordinate_revision", "roof_revision"):
        if venue[field] is not None:
            require_digest(venue[field], field)
    if venue["coordinate_source"] is not None:
        require_text(venue["coordinate_source"], "coordinate source identity", code=True)
    if type(venue["location_type"]) is not str or venue["location_type"] not in {"venue", "city", "unknown"}:
        raise ContextContractError("unreviewed location binding")
    if type(venue["roof"]) is not str or venue["roof"] not in {"open", "closed", "unknown"}:
        raise ContextContractError("unreviewed roof state")
    if (venue["latitude"] is None) != (venue["longitude"] is None):
        raise ContextContractError("both source coordinates or neither are required")
    for field, bound in (("latitude", 90), ("longitude", 180)):
        if venue[field] is not None:
            require_number(venue[field], field, minimum=-bound, maximum=bound)
    for field in ("issued_at", "valid_at", "valid_from", "valid_until"):
        if row[field] is not None:
            if type(row[field]) is not str:
                raise ContextContractError("weather source clocks must be ISO strings or null")
            row[field] = canonical_timestamp(row[field])
    if row["valid_at"] is None:
        raise ContextContractError("weather must retain its actual valid point")
    if (row["valid_from"] is None) != (row["valid_until"] is None):
        raise ContextContractError("partial weather interval is not a supported interval")
    if row["valid_from"] is not None and not row["valid_from"] <= row["valid_at"] < row["valid_until"]:
        raise ContextContractError("weather valid point must belong to its declared interval")
    if row["issued_at"] is not None:
        if row["issued_at"] > observed_at:
            raise ContextContractError("forecast issuance cannot follow the actual receipt")
        if row["source_kind"] in {"forecast", "forecast_archive"} and row["issued_at"] > row["valid_at"]:
            raise ContextContractError("negative forecast horizon is not a prior forecast")
    for field in METRICS:
        if row[field] is not None:
            require_number(row[field], field, minimum=-273.15 if field == "temperature_c" else 0)
    return row


def _complete(payload: dict) -> bool:
    return (weather_metadata_gap(payload) is None and payload["venue"]["roof"] == "open"
            and all(payload[key] is not None for key in METRICS))


def normalize_weather(event: dict, response: dict, *, observed_at: datetime, source_kind: str) -> tuple[dict, ...]:
    """Normalize an internally resolved weather transport into B1 content.

    ``observed_at`` must be the owning source's actual receipt, not the forecast
    valid point or evaluation time. An unbounded valid point is preserved with
    no valid_until; B1 cannot treat it as a kickoff-covering weather interval.
    Unknown issue, roof or exact venue stays unknown. No publication proof is
    invented from forecast initialization. No I/O or cache mutation occurs.
    """
    if not isinstance(observed_at, datetime):
        raise ContextContractError("weather receipt requires an aware datetime")
    target = validate_event(event)
    if target["sport"] != "football" or target["format"] != "90min":
        raise ContextContractError("weather transport owns football regulation context only")
    payload = validate_weather_payload(response, observed_at=canonical_timestamp(observed_at))
    if source_kind != payload["source_kind"]:
        raise ContextContractError("caller cannot relabel the weather source kind")
    if payload["event_hash"] != digest(target):
        raise ContextContractError("weather does not belong to the complete event revision")
    return (normalize_observation({
        "event_key": target["event_key"], "sport": target["sport"], "competition": target["competition"],
        "format": target["format"], "subject_id": f"{target['event_key']}:weather", "kind": "weather",
        "source": payload["source"], "source_schema": SOURCE_SCHEMA, "source_revision": digest(payload),
        "schedule_revision": target["schedule_revision"], "published_at": None, "publication_proof": None,
        "valid_from": payload["valid_from"] or payload["valid_at"], "valid_until": payload["valid_until"],
        "complete": _complete(payload), "payload": payload,
    }, observed_at=observed_at),)


def validate_weather_record(row: dict) -> dict:
    payload = validate_weather_payload(row["payload"], observed_at=row["observed_at"])
    if (payload != row["payload"] or row["source"] != payload["source"] or row["source_schema"] != SOURCE_SCHEMA
            or row["kind"] != "weather" or row["subject_id"] != f"{row['event_key']}:weather"
            or row["sport"] != "football" or row["format"] != "90min"
            or row["source_revision"] != digest(payload) or row["published_at"] is not None
            or row["publication_proof"] is not None or row["complete"] is not _complete(payload)
            or row["valid_from"] != (payload["valid_from"] or payload["valid_at"])
            or row["valid_until"] != payload["valid_until"]):
        raise ContextContractError("weather source/content/clock binding mismatch")
    return payload
