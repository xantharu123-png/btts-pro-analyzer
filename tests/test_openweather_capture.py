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


def weather_fixture(start, *, fixture_id=1575469, city="Porto", country="Portugal"):
    fixture = detail()
    fixture["fixture"]["id"] = fixture_id
    fixture["fixture"]["date"] = start
    fixture["fixture"]["venue"] = {"city": city}
    fixture["league"]["country"] = country
    return fixture


def forecast_point(at, temperature):
    return {"dt": datetime.fromisoformat(at).timestamp(),
            "main": {"temp": temperature}, "wind": {"speed": 4.0}}


def stub_weather(monkeypatch, points):
    import challenge_15k
    calls = []
    class Response:
        def __init__(self, value): self.value = value
        def raise_for_status(self): pass
        def json(self): return deepcopy(self.value)
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response([{"lat": 41.1, "lon": -8.6}] if "/geo/" in url else {"list": points})
    monkeypatch.setattr(challenge_15k.requests, "get", get)
    return calls


@pytest.mark.parametrize("second_start", ["2026-09-09T10:40:00+00:00", "2026-09-09T12:40:00+02:00"])
def test_weather_reselects_cached_forecast_for_exact_minute_without_another_request(monkeypatch, second_start):
    from challenge_15k import ChallengeDataProvider
    points = [forecast_point("2026-09-09T09:00:00+00:00", 11.),
              forecast_point("2026-09-09T12:00:00+00:00", 27.)]
    calls = stub_weather(monkeypatch, points)
    owner = ChallengeDataProvider("test-football", "test-weather")
    first = owner.weather(weather_fixture("2026-09-09T10:20:00+00:00"))
    second = owner.weather(weather_fixture(second_start, fixture_id=1575470))
    assert first["forecast_at"] == "2026-09-09T09:00:00+00:00"
    assert second["forecast_at"] == "2026-09-09T12:00:00+00:00"
    assert second["temperature_c"] == 27.
    assert len(calls) == 2


def test_weather_minute_reselection_preserves_both_native_bindings_and_original_clock(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    fixtures = [weather_fixture("2026-09-09T10:20:00+00:00"),
                weather_fixture("2026-09-09T10:40:00+00:00", fixture_id=1575470)]
    owner, _ = provider(monkeypatch, details=payload(fixtures))
    owner.weather_key = "test-weather"
    received = NOW - timedelta(hours=3)
    clocks = iter([received, received + timedelta(seconds=1)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(clocks))
    points = [forecast_point("2026-09-09T09:00:00+00:00", 11.),
              forecast_point("2026-09-09T12:00:00+00:00", 27.)]
    calls = stub_weather(monkeypatch, points)
    path = tmp_path / "context.db"
    with capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469, 1575470])
        owner.weather(fixtures[0])
        owner.weather(fixtures[1])
        owner.weather(fixtures[0])
    rows = [row for row in stored(path) if row["kind"] == "weather"]
    assert len(calls) == 2 and len(rows) == 2
    assert {row["observed_at"] for row in rows} == {canonical_timestamp(received + timedelta(seconds=1))}
    assert {row["event_key"]: row["payload"]["temperature_c"] for row in rows} == {
        "api-football:football:1575469": 11., "api-football:football:1575470": 27.}


@pytest.mark.parametrize("change", ["hour", "date", "country", "city"])
def test_weather_cache_does_not_reuse_another_existing_query_scope(monkeypatch, change):
    from challenge_15k import ChallengeDataProvider
    points = [forecast_point("2026-09-09T09:00:00+00:00", 11.),
              forecast_point("2026-09-09T12:00:00+00:00", 27.),
              forecast_point("2026-09-10T12:00:00+00:00", 33.)]
    calls = stub_weather(monkeypatch, points)
    owner = ChallengeDataProvider("test-football", "test-weather")
    owner.weather(weather_fixture("2026-09-09T10:20:00+00:00"))
    kwargs = {"fixture_id": 1575470}
    start = "2026-09-09T10:40:00+00:00"
    if change == "hour": start = "2026-09-09T11:40:00+00:00"
    if change == "date": start = "2026-09-10T10:40:00+00:00"
    if change == "country": kwargs["country"] = "Brazil"
    if change == "city": kwargs["city"] = "Lisbon"
    result = owner.weather(weather_fixture(start, **kwargs))
    assert result["temperature_c"] == (33. if change == "date" else 27.)
    assert len(calls) == 4


@pytest.mark.parametrize("bad_time", [1e100, 10**400, float("inf"), float("nan"), True, -1, "bad"])
def test_unrepresentable_weather_point_time_is_skipped_without_aborting(monkeypatch, bad_time):
    from challenge_15k import ChallengeDataProvider
    valid = forecast_point("2026-09-09T12:00:00+00:00", 27.)
    calls = stub_weather(monkeypatch, [{"dt": bad_time}, valid])
    owner = ChallengeDataProvider("test-football", "test-weather")
    result = owner.weather(weather_fixture("2026-09-09T10:40:00+00:00"))
    assert result["temperature_c"] == 27.
    assert len(calls) == 2


def test_only_unrepresentable_forecast_points_are_negatively_cached(monkeypatch):
    from challenge_15k import ChallengeDataProvider
    calls = stub_weather(monkeypatch, [{"dt": 1e100}])
    owner = ChallengeDataProvider("test-football", "test-weather")
    assert owner.weather(weather_fixture("2026-09-09T10:20:00+00:00")) is None
    assert owner.weather(weather_fixture("2026-09-09T10:40:00+00:00")) is None
    assert len(calls) == 2


@pytest.mark.parametrize("excess", ["points", "bytes"])
def test_oversized_forecast_response_is_not_retained_or_retried_for_another_minute(monkeypatch, excess):
    from challenge_15k import ChallengeDataProvider
    point = forecast_point("2026-09-09T12:00:00+00:00", 27.)
    points = [point] * 65 if excess == "points" else [{**point, "unexpected_blob": "x" * 65536}]
    calls = stub_weather(monkeypatch, points)
    owner = ChallengeDataProvider("test-football", "test-weather")
    assert owner.weather(weather_fixture("2026-09-09T10:20:00+00:00")) is None
    assert owner.weather(weather_fixture("2026-09-09T10:40:00+00:00")) is None
    assert len(calls) == 2


def test_cached_response_rechecks_existing_four_hour_limit_for_each_kickoff(monkeypatch):
    from challenge_15k import ChallengeDataProvider
    calls = stub_weather(monkeypatch, [forecast_point("2026-09-09T14:05:00+00:00", 27.)])
    owner = ChallengeDataProvider("test-football", "test-weather")
    assert owner.weather(weather_fixture("2026-09-09T10:00:00+00:00")) is None
    assert owner.weather(weather_fixture("2026-09-09T10:10:00+00:00"))["temperature_c"] == 27.
    assert owner.weather(weather_fixture("2026-09-09T10:00:00+00:00")) is None
    assert len(calls) == 2


def test_cached_weather_values_are_detached_from_caller_mutation(monkeypatch):
    from challenge_15k import ChallengeDataProvider
    calls = stub_weather(monkeypatch, [forecast_point("2026-09-09T12:00:00+00:00", 27.)])
    owner = ChallengeDataProvider("test-football", "test-weather")
    fixture = weather_fixture("2026-09-09T10:40:00+00:00")
    first = owner.weather(fixture)
    first["temperature_c"] = 99.
    assert owner.weather(fixture)["temperature_c"] == 27.
    assert len(calls) == 2


def test_cached_partial_forecast_does_not_borrow_old_point_values(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    fixtures = [weather_fixture("2026-09-09T10:20:00+00:00"),
                weather_fixture("2026-09-09T10:40:00+00:00", fixture_id=1575470)]
    owner, _ = provider(monkeypatch, details=payload(fixtures))
    owner.weather_key = "test-weather"
    received = NOW - timedelta(hours=3)
    clocks = iter([received, received + timedelta(seconds=1)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(clocks))
    second = forecast_point("2026-09-09T12:00:00+00:00", 27.)
    second["main"] = {}
    calls = stub_weather(monkeypatch, [forecast_point("2026-09-09T09:00:00+00:00", 11.), second])
    path = tmp_path / "context.db"
    with capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469, 1575470])
        assert owner.weather(fixtures[0])["temperature_c"] == 11.
        assert owner.weather(fixtures[1])["temperature_c"] is None
    row = next(row for row in stored(path) if row["kind"] == "weather"
               and row["event_key"] == "api-football:football:1575470")
    assert not row["complete"] and row["payload"]["temperature_c"] is None
    assert row["payload"]["wind_mps"] == 4.
    assert row["observed_at"] == canonical_timestamp(received + timedelta(seconds=1))
    assert len(calls) == 2


def test_cached_point_before_original_receipt_cannot_become_prospective_weather(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    fixture = weather_fixture("2026-09-09T10:20:00+00:00")
    owner, _ = provider(monkeypatch, details=payload([fixture]))
    owner.weather_key = "test-weather"
    clocks = iter([NOW, NOW + timedelta(seconds=1)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(clocks))
    calls = stub_weather(monkeypatch, [forecast_point("2026-09-09T09:00:00+00:00", 11.)])
    path = tmp_path / "context.db"
    with capture_football_worker(owner, path=path) as capture:
        owner.details_by_fixture([fixture["fixture"]["id"]])
        owner.weather(fixture)
        owner.weather(fixture)
    assert not any(row["kind"] == "weather" for row in stored(path))
    assert "Kontext-Capture: native-projection-unavailable" in capture.errors
    assert len(calls) == 2
