"""Offline source-contract tests; no live weather request or quality claim."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from context_sources.football import _detail_event
from context_sources.openweather import forecast_payload, normalize_forecast, validate_record
from test_context_football_capture import detail, stored
from test_football_context_provider import NOW, payload, provider


def weather_payload():
    event = _detail_event(detail())
    return forecast_payload(event, city="Porto", country="Portugal", latitude=41.1,
        longitude=-8.6, point={"dt": datetime.fromisoformat(event["scheduled_start"]).timestamp(),
                              "main": {"temp": 18.0}, "wind": {"speed": 4.0}})


def test_native_forecast_preserves_receipt_and_city_scope_without_inventing_issue():
    value = weather_payload()
    row = normalize_forecast(value, observed_at=NOW)
    assert row["published_at"] is None and row["publication_proof"] is None
    assert row["valid_from"] == canonical_timestamp(NOW) and row["valid_until"] is None
    assert row["complete"] and value["location_scope"] == "city"
    assert value["rain_3h_mm"] == value["snow_3h_mm"] == 0
    assert validate_record({**row, "observed_at": canonical_timestamp(NOW)}) == value
    assert "issued_at" not in value and "roof" not in value


@pytest.mark.parametrize("key,value", [("temperature_c", True), ("wind_mps", -1),
    ("rain_3h_mm", float("nan")), ("latitude", 91), ("longitude", False)])
def test_invalid_source_numbers_do_not_enter_training(key, value):
    data = weather_payload()
    data[key] = value
    with pytest.raises(ContextContractError):
        normalize_forecast(data, observed_at=NOW)


@pytest.mark.parametrize("key", ["main", "wind", "rain", "snow"])
def test_malformed_present_source_is_not_zero_or_healthy(key):
    data = {"dt": datetime.fromisoformat(_detail_event(detail())["scheduled_start"]).timestamp(),
            "main": {"temp": 18.0}, "wind": {"speed": 4.0}, key: None}
    with pytest.raises(ContextContractError):
        forecast_payload(_detail_event(detail()), city="Porto", country="Portugal",
            latitude=41.1, longitude=-8.6, point=data)


@pytest.mark.parametrize("reason", ["after-kickoff", "old-point", "distant-point"])
def test_wrong_weather_time_is_not_prematch_evidence(reason):
    data = weather_payload()
    observed = NOW
    if reason == "after-kickoff":
        observed = datetime.fromisoformat(data["event"]["scheduled_start"])
    elif reason == "old-point":
        data["forecast_at"] = canonical_timestamp(NOW - timedelta(minutes=1))
    else:
        data["forecast_at"] = canonical_timestamp(datetime.fromisoformat(data["event"]["scheduled_start"]) + timedelta(hours=5))
    with pytest.raises(ContextContractError):
        normalize_forecast(data, observed_at=observed)


def test_existing_weather_request_is_persisted_and_cache_does_not_refresh_clock(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    import challenge_15k
    fixture = detail()
    fixture["fixture"]["venue"] = {"city": "Porto"}
    fixture["league"]["country"] = "Portugal"
    owner, calls = provider(monkeypatch, details=payload([fixture]))
    owner.weather_key = "secret-weather-key"
    clocks = iter([NOW, NOW + timedelta(seconds=1)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(clocks))
    weather_calls = []
    class Response:
        def __init__(self, value): self.value = value
        def raise_for_status(self): pass
        def json(self): return deepcopy(self.value)
    point = {"dt": datetime.fromisoformat(fixture["fixture"]["date"]).timestamp(),
             "main": {"temp": 18.0}, "wind": {"speed": 4.0}}
    def get(url, **kwargs):
        weather_calls.append((url, kwargs))
        return Response([{"lat": 41.1, "lon": -8.6}] if "/geo/" in url else {"list": [point]})
    monkeypatch.setattr(challenge_15k.requests, "get", get)
    path = tmp_path / "context.db"
    with capture_football_worker(owner, path=path):
        owner.details_by_fixture([fixture["fixture"]["id"]])
        first = owner.weather(fixture)
        assert owner.weather(fixture) == first
    rows = [row for row in stored(path) if row["kind"] == "weather"]
    assert len(weather_calls) == 2 and len(rows) == 1
    assert rows[0]["observed_at"] == canonical_timestamp(NOW + timedelta(seconds=1))
    assert rows[0]["payload"]["temperature_c"] == first["temperature_c"] == 18.0
    assert "secret-weather-key" not in str(rows)


@pytest.mark.parametrize("reason", ["unknown-event", "late-event", "changed-venue", "changed-schedule"])
def test_weather_cannot_be_bound_to_unknown_late_or_changed_fixture(tmp_path, reason):
    from context_sources.football_capture import _Capture
    fixture = detail()
    fixture["fixture"]["venue"] = {"city": "Porto"}
    capture = _Capture(tmp_path / "context.db")
    if reason != "unknown-event":
        capture.record("fixtures", {"id": fixture["fixture"]["id"]}, payload([fixture]),
            observed_at=NOW + timedelta(seconds=1) if reason == "late-event" else NOW, status=200)
    if reason == "changed-venue":
        fixture["fixture"]["venue"]["city"] = "Madrid"
    if reason == "changed-schedule":
        fixture["fixture"]["date"] = canonical_timestamp(datetime.fromisoformat(fixture["fixture"]["date"]) + timedelta(hours=1))
    capture.record_weather(fixture, point={"dt": datetime.fromisoformat(fixture["fixture"]["date"]).timestamp()},
        latitude=41., longitude=-8., observed_at=NOW)
    assert not capture.weather_receipts
    assert "Kontext-Capture: native-event-binding-unavailable" in capture.errors


def selected_forecast(tmp_path, value=None, observed=NOW):
    from tests.test_football_weather_features import store_rows
    return store_rows(tmp_path, (normalize_forecast(value or weather_payload(), observed_at=observed),),
        observed, cutoff=observed)


def forecast_features(rows, target=None, cutoff=NOW):
    from context_models.football_city_weather import city_weather_features
    from tests.test_football_weather_features import base
    target = target or weather_payload()["event"]
    return city_weather_features(target, rows, base(target, cutoff=cutoff), cutoff=cutoff)


def test_city_forecast_has_own_model_features_and_no_fake_stadium_claim(tmp_path):
    rows = selected_forecast(tmp_path)
    result = forecast_features(rows, cutoff=NOW + timedelta(minutes=30))
    assert result["version"] == "football-city-forecast-features-v1"
    assert result["values"]["temperature_c"] == 18.
    assert result["values"]["receipt_age_hours"] == .5
    assert result["values"]["forecast_to_kickoff_hours"] == 0.
    assert all(result["refs"].values())
    assert result["coverage"]["case"] == "city-point-not-stadium"


def test_later_forecast_does_not_enter_earlier_decision(tmp_path):
    rows = selected_forecast(tmp_path, observed=NOW + timedelta(seconds=1))
    assert set(forecast_features(rows)["states"].values()) == {"missing"}


def test_new_partial_forecast_does_not_borrow_old_temperature(tmp_path):
    selected_forecast(tmp_path)
    newer = weather_payload()
    newer["temperature_c"] = None
    all_rows = selected_forecast(tmp_path, newer, observed=NOW + timedelta(seconds=1))
    result = forecast_features(all_rows, cutoff=NOW + timedelta(seconds=2))
    assert result["values"]["temperature_c"] is None
    assert result["states"]["temperature_c"] == "missing"
    assert result["values"]["wind_mps"] == 4.


def test_simultaneous_contradictory_city_forecasts_cannot_be_averaged(tmp_path):
    selected_forecast(tmp_path)
    conflict = weather_payload()
    conflict["wind_mps"] = 30.
    rows = selected_forecast(tmp_path, conflict)
    assert set(forecast_features(rows)["states"].values()) == {"conflicting"}


def test_changed_schedule_does_not_reuse_old_weather(tmp_path):
    rows = selected_forecast(tmp_path)
    target = deepcopy(weather_payload()["event"])
    target["scheduled_start"] = canonical_timestamp(datetime.fromisoformat(target["scheduled_start"]) + timedelta(hours=1))
    target["schedule_revision"] = "rescheduled"
    assert set(forecast_features(rows, target)["states"].values()) == {"stale"}


def test_weather_outside_worker_does_not_create_capture_clock_or_late_evidence(monkeypatch, tmp_path):
    import challenge_15k
    from context_sources.football_capture import capture_football_worker
    fixture = detail()
    fixture["fixture"]["venue"] = {"city": "Porto"}
    owner, _ = provider(monkeypatch, details=payload([fixture]))
    owner.weather_key = "secret-weather-key"
    def forbidden():
        raise AssertionError("disabled observation must not create a new capture clock")
    monkeypatch.setattr(owner, "_context_received_at", forbidden)
    class Response:
        def __init__(self, value): self.value = value
        def raise_for_status(self): pass
        def json(self): return self.value
    point = {"dt": datetime.fromisoformat(fixture["fixture"]["date"]).timestamp(),
             "main": {"temp": 18}, "wind": {"speed": 4}}
    monkeypatch.setattr(challenge_15k.requests, "get", lambda url, **kwargs:
        Response([{"lat": 41., "lon": -8.}] if "/geo/" in url else {"list": [point]}))
    assert owner.weather(fixture)["temperature_c"] == 18
    assert not owner._weather_receipts
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    with capture_football_worker(owner, path=tmp_path / "context.db"):
        owner.details_by_fixture([fixture["fixture"]["id"]])
        assert owner.weather(fixture)["temperature_c"] == 18
    assert not any(row["kind"] == "weather" for row in stored(tmp_path / "context.db"))
