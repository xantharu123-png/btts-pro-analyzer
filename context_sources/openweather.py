"""Capture the existing forecast5 response as a city forecast, not stadium truth.

OpenWeather documents ``dt`` as the forecast-valid instant, NOT issue time,
and precipitation as a preceding three-hour accumulation. The actual receipt
proves when this forecast became available to this app. No earlier issue time,
stadium coordinates, roof state or kickoff-wide applicability is invented.
https://openweathermap.org/api/forecast5
"""
from datetime import datetime, timezone

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, normalize_observation,
    require_number, require_object, validate_event,
)

SOURCE = "openweather"
SOURCE_SCHEMA = "openweather-forecast5-city-point-v1"
METRICS = ("temperature_c", "wind_mps", "rain_3h_mm", "snow_3h_mm")
FIELDS = {"schema", "event", "city", "country", "latitude", "longitude",
          "location_scope", "forecast_at", "units", *METRICS}


def forecast_payload(event, *, city, country, latitude, longitude, point):
    """Project only the used numeric source fields; never persist a request URL."""
    event = validate_event(event)
    if event["sport"] != "football" or event["format"] != "90min":
        raise ContextContractError("city forecast requires a regulation football event")
    if type(point) is not dict:
        raise ContextContractError("forecast point must be an actual response object")
    stamp = require_number(point.get("dt"), "forecast valid timestamp", minimum=0)
    try:
        valid = canonical_timestamp(datetime.fromtimestamp(stamp, timezone.utc))
    except (ValueError, OverflowError, OSError) as exc:
        raise ContextContractError("invalid forecast valid timestamp") from exc
    main = point.get("main", {})
    wind = point.get("wind", {})
    if type(main) is not dict or type(wind) is not dict:
        raise ContextContractError("malformed forecast temperature/wind")
    precipitation = {}
    for key in ("rain", "snow"):
        values = point.get(key)
        # The source explicitly omits phenomena which are not forecast.
        # A present but malformed object is not evidence of zero precipitation.
        if values is None and key not in point:
            precipitation[key + "_3h_mm"] = 0.0
        elif type(values) is dict and "3h" in values:
            precipitation[key + "_3h_mm"] = values["3h"]
        else:
            raise ContextContractError("malformed three-hour precipitation")
    payload = {"schema": 1, "event": event, "city": city, "country": country,
        "latitude": latitude, "longitude": longitude, "location_scope": "city",
        "forecast_at": valid, "units": "degC-mps-mm3h",
        "temperature_c": main.get("temp"), "wind_mps": wind.get("speed"), **precipitation}
    return validate_payload(payload)


def validate_payload(payload):
    require_object(payload, FIELDS, label="native city forecast")
    event = validate_event(payload["event"])
    if (type(payload["schema"]) is not int or payload["schema"] != 1
            or event != payload["event"] or event["sport"] != "football"
            or event["format"] != "90min" or payload["location_scope"] != "city"
            or payload["units"] != "degC-mps-mm3h"):
        raise ContextContractError("unsupported native city forecast")
    if (type(payload["city"]) is not str or not payload["city"].strip()
            or type(payload["country"]) is not str):
        raise ContextContractError("forecast must retain the actual location query")
    for key, bound in (("latitude", 90), ("longitude", 180)):
        require_number(payload[key], key, minimum=-bound, maximum=bound)
    if canonical_timestamp(payload["forecast_at"]) != payload["forecast_at"]:
        raise ContextContractError("forecast valid time must be canonical")
    for key in METRICS:
        if payload[key] is not None:
            require_number(payload[key], key, minimum=-273.15 if key == "temperature_c" else 0)
    return dict(payload)


def normalize_forecast(payload, *, observed_at):
    payload = validate_payload(payload)
    event = payload["event"]
    observed = canonical_timestamp(observed_at)
    if event["status"] != "scheduled" or observed >= event["scheduled_start"]:
        raise ContextContractError("a city forecast must be received before kickoff")
    if payload["forecast_at"] < observed:
        raise ContextContractError("past weather point is not a prospective forecast")
    separation = abs((datetime.fromisoformat(payload["forecast_at"])
                      - datetime.fromisoformat(event["scheduled_start"])).total_seconds())
    if separation > 4 * 3600:
        raise ContextContractError("forecast point is outside the existing match-time window")
    return normalize_observation({
        "event_key": event["event_key"], "sport": "football", "competition": event["competition"],
        "format": "90min", "subject_id": event["event_key"] + ":weather", "kind": "weather",
        "source": SOURCE, "source_schema": SOURCE_SCHEMA, "source_revision": digest(payload),
        "schedule_revision": event["schedule_revision"], "published_at": None,
        "publication_proof": None, "valid_from": observed, "valid_until": None,
        "complete": all(payload[key] is not None for key in METRICS), "payload": payload,
    }, observed_at=datetime.fromisoformat(observed))


def validate_record(row):
    expected = normalize_forecast(row["payload"], observed_at=row["observed_at"])
    if any(row.get(key) != value for key, value in expected.items()):
        raise ContextContractError("city forecast source/event/receipt binding mismatch")
    return expected["payload"]
