"""Pre-match city-forecast features from the existing OpenWeather capture.

City observations are not exact stadium/roof observations. They have their own
version and cannot masquerade as the strict football-weather-features-v1 input.
Age and kickoff offset stay numerical features; no five-minute lineup gate or
assumed issue time is introduced. This builder assigns no effect coefficient.
"""
from datetime import datetime

from context_models.contracts import ContextContractError, canonical_timestamp
from context_models.football_load import _context, _feature_builder
from context_observations import _check_selected_row
from context_sources.openweather import METRICS, SOURCE_SCHEMA, validate_record

VERSION = "football-city-forecast-features-v1"


def city_weather_features(event, observations, base, *, cutoff):
    event, decision, reference = _context(event, base, cutoff)
    clock = canonical_timestamp(decision)
    if type(observations) is not tuple:
        raise ContextContractError("city weather needs a frozen receipt tuple")
    eligible = []
    for row in observations:
        _check_selected_row(row)
        if row["kind"] != "weather" or row["source_schema"] != SOURCE_SCHEMA:
            continue
        validate_record(row)
        if row["event_key"] != event["event_key"]:
            raise ContextContractError("city weather mixes distinct native events")
        if row["evidence_class"] == "prospective" and row["observed_at"] <= clock:
            eligible.append(row)
    latest = max((row["observed_at"] for row in eligible), default=None)
    selected = {row["digest"]: row for row in eligible if row["observed_at"] == latest}
    state, case, used, payload = "missing", "no-city-forecast", (), None
    if event["status"] != "scheduled":
        state, case = "not_applicable", "event-not-scheduled"
    elif len(selected) > 1:
        state, case = "conflicting", "simultaneous-city-forecasts"
    elif selected:
        row = next(iter(selected.values()))
        if row["payload"]["event"] != event:
            state, case = "stale", "different-event-revision"
        else:
            state, case, used, payload = "available", "city-point-not-stadium", (row,), row["payload"]
    _, _, _, put, finish = _feature_builder(event, decision, reference, VERSION)
    for key in METRICS:
        put(key, payload[key] if payload is not None else None, used,
            None if state == "available" else state)
    age = (decision - datetime.fromisoformat(latest)).total_seconds() / 3600 if payload is not None else None
    offset = ((datetime.fromisoformat(payload["forecast_at"]) - datetime.fromisoformat(event["scheduled_start"])).total_seconds()
              / 3600 if payload is not None else None)
    put("receipt_age_hours", age, used, None if state == "available" else state)
    put("forecast_to_kickoff_hours", offset, used, None if state == "available" else state)
    if payload is not None and any(payload[key] is None for key in METRICS):
        case += ".partial-values"
    return finish(case)
