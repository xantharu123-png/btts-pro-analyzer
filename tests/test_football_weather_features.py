"""C1 CPU mechanics. Weather transports below are explicitly SYNTHETIC.

They prove no OpenWeather entitlement, stadium coordinates, forecast archive,
trained coefficient or activation. Real schedule evidence is separately marked.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest, validate_base_distribution, validate_event
from context_observations import append_observation, observations_as_of
from context_sources.weather import normalize_weather, weather_window
from context_models.football_load import (
    football_schedule_features, football_weather_features, normalize_football_schedule,
)

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
START = NOW + timedelta(hours=4)


def event():
    return {"event_key": "api-football:football:100", "sport": "football", "competition": "39", "format": "90min",
            "home_id": "api-football:team:1", "away_id": "api-football:team:2",
            "scheduled_start": canonical_timestamp(START), "schedule_revision": "schedule-v1", "status": "scheduled"}


def base(target=None, cutoff=NOW):
    return {"version": "football-goals-baseline-v1", "model_hash": "a" * 64,
            "event_key": (target or event())["event_key"], "cutoff": canonical_timestamp(cutoff),
            "family": "football:goals:90min", "params": {"home_lambda": 1.5, "away_lambda": 1.2},
            "markets": {"home_win": .44}, "history_refs": [],
            "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "legacy-reference-unavailable"}}


def weather(target=None):
    target = target or event()
    return {"schema": 1, "source_schema": "football-weather-transport-v1", "source": "synthetic-weather",
            "source_kind": "forecast", "event_hash": digest(validate_event(target)),
            "venue": {"venue_id": "api-football:venue:1", "venue_revision": "b" * 64,
                      "location_type": "venue", "coordinate_source": "synthetic-stadium",
                      "coordinate_revision": "c" * 64, "latitude": 47., "longitude": 8.,
                      "roof": "open", "roof_revision": "d" * 64},
            "units": {"temperature": "degC", "wind": "m/s", "precipitation": "mm/3h"},
            "issued_at": canonical_timestamp(NOW - timedelta(hours=1)),
            "valid_at": target["scheduled_start"],
            "valid_from": canonical_timestamp(START - timedelta(hours=1)),
            "valid_until": canonical_timestamp(START + timedelta(hours=2)),
            "temperature_c": 18., "wind_mps": 4., "rain_3h_mm": .5, "snow_3h_mm": 0.}


def timeline(fixture=90, home=1, away=3, *, competition=39, end=NOW - timedelta(hours=30), status="FT"):
    return {"fixture_id": fixture, "home_id": home, "away_id": away, "competition_id": competition,
            "season": 2026, "status": status, "scheduled_start": canonical_timestamp(end - timedelta(hours=2)),
            "actual_start": canonical_timestamp(end - timedelta(hours=2)), "actual_end": canonical_timestamp(end),
            "minutes": 95., "result_observed_at": canonical_timestamp(end + timedelta(minutes=2))}


def store_rows(tmp_path, rows, observed=NOW, *, cutoff=NOW, historical=False):
    path = tmp_path / "context.db"
    scopes = set()
    for row in rows:
        append_observation(path, row, observed_at=observed)
        scopes.add((row["event_key"], row["schedule_revision"]))
    return tuple(row for key, schedule in sorted(scopes) for row in observations_as_of(
        path, key, cutoff=cutoff, schedule_revision=schedule, mode="historical" if historical else "prospective"))


def stored_weather(tmp_path, raw=None, *, observed=NOW, target=None, cutoff=NOW):
    raw = weather(target) if raw is None else raw
    return store_rows(tmp_path, normalize_weather(target or event(), raw, observed_at=observed,
        source_kind=raw["source_kind"]), observed, cutoff=cutoff, historical=True)


def stored_load(tmp_path, raw=None, *, observed=NOW, cutoff=NOW):
    return store_rows(tmp_path, normalize_football_schedule(tuple(raw or [timeline()]), observed_at=observed,
        source_schema="football-completed-transport-v1"), observed, cutoff=cutoff, historical=True)


def test_later_forecast_is_not_prior_evidence():
    assert not weather_window(issued_at=NOW + timedelta(hours=1), valid_from=START - timedelta(hours=1),
        valid_until=START + timedelta(hours=2), decision_at=NOW, kickoff=START)


@pytest.mark.parametrize("field", ["issued_at", "valid_from", "valid_until", "decision_at", "kickoff"])
def test_weather_window_requires_all_five_real_aware_clocks(field):
    values = {"issued_at": NOW, "valid_from": START, "valid_until": START + timedelta(hours=1), "decision_at": NOW, "kickoff": START}
    values[field] = values[field].replace(tzinfo=None)
    with pytest.raises(ContextContractError):
        weather_window(**values)


def test_window_is_half_open_and_cannot_include_started_decision():
    assert weather_window(issued_at=NOW, valid_from=START, valid_until=START + timedelta(seconds=1), decision_at=NOW, kickoff=START)
    assert not weather_window(issued_at=NOW, valid_from=NOW, valid_until=START, decision_at=NOW, kickoff=START)
    assert not weather_window(issued_at=NOW, valid_from=NOW, valid_until=START + timedelta(hours=1), decision_at=START, kickoff=START)


def test_synthetic_qualified_forecast_preserves_measured_fields_and_zero(tmp_path):
    result = football_weather_features(event(), stored_weather(tmp_path), base(), cutoff=NOW)
    assert result["version"] == "football-weather-features-v1"
    assert result["values"] == {"temperature_c": 18., "wind_mps": 4., "rain_3h_mm": .5,
                                "snow_3h_mm": 0., "forecast_horizon_hours": 5.}
    assert set(result["states"].values()) == {"available"}
    assert all(result["refs"].values())


@pytest.mark.parametrize("key", ["issued_at", "valid_from", "valid_until"])
def test_unknown_forecast_clock_is_not_invented_from_valid_point(tmp_path, key):
    raw = weather()
    raw[key] = None
    if key in {"valid_from", "valid_until"}:
        raw["valid_from"] = raw["valid_until"] = None
    rows = stored_weather(tmp_path, raw)
    assert rows[0]["payload"][key] is None
    result = football_weather_features(event(), rows, base(), cutoff=NOW)
    assert set(result["states"].values()) == {"missing"}
    assert all(value is None for value in result["values"].values())
    assert not any(result["refs"].values())


@pytest.mark.parametrize("kind", ["actual", "reanalysis", "forecast_archive"])
def test_nonprospective_source_kind_cannot_enter_strict_forecast(tmp_path, kind):
    raw = weather()
    raw["source_kind"] = kind
    rows = stored_weather(tmp_path, raw)
    assert rows[0]["payload"]["source_kind"] == kind
    result = football_weather_features(event(), rows, base(), cutoff=NOW)
    assert all(value is None for value in result["values"].values())


@pytest.mark.parametrize("change", [{"venue_id": None}, {"location_type": "city"}, {"latitude": None, "longitude": None},
    {"coordinate_revision": None}, {"venue_revision": None}, {"roof": "unknown", "roof_revision": None}])
def test_missing_venue_or_roof_is_not_exact_stadium_weather(tmp_path, change):
    raw = weather()
    raw["venue"].update(change)
    result = football_weather_features(event(), stored_weather(tmp_path, raw), base(), cutoff=NOW)
    assert all(value is None for value in result["values"].values())
    assert set(result["states"].values()) == {"missing"}


def test_verified_closed_roof_is_distinct_from_unknown_roof(tmp_path):
    raw = weather()
    raw["venue"]["roof"] = "closed"
    result = football_weather_features(event(), stored_weather(tmp_path, raw), base(), cutoff=NOW)
    assert set(result["states"].values()) == {"not_applicable"}
    assert not any(result["refs"].values())


@pytest.mark.parametrize("units", ["metric", {"temperature": "degF", "wind": "m/s", "precipitation": "mm/3h"},
    {"temperature": "degC", "wind": "mph", "precipitation": "mm/3h"},
    {"temperature": "degC", "wind": "m/s", "precipitation": "mm/h"}])
def test_mixed_or_implicit_units_are_rejected(units):
    raw = weather()
    raw["units"] = units
    with pytest.raises(ContextContractError):
        normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast")


@pytest.mark.parametrize("key,value", [("temperature_c", True), ("temperature_c", -274), ("temperature_c", float("nan")),
    ("wind_mps", -1), ("rain_3h_mm", "0"), ("snow_3h_mm", float("inf")), ("schema", True)])
def test_weather_fields_are_closed_finite_source_values(key, value):
    raw = weather()
    raw[key] = value
    with pytest.raises(ContextContractError):
        normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast")


@pytest.mark.parametrize("key", ["odds", "marketPrice", "unknown"])
def test_closed_weather_transport_never_accepts_price_or_unknown_fields(key):
    raw = weather()
    raw[key] = 2.
    with pytest.raises(ContextContractError):
        normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast")


def test_weather_late_receipt_staleness_and_reschedule_keep_basis(tmp_path):
    target_base = base()
    late = stored_weather(tmp_path, observed=NOW + timedelta(seconds=1))
    assert not any(football_weather_features(event(), late, target_base, cutoff=NOW)["refs"].values())
    raw = weather()
    raw["issued_at"] = canonical_timestamp(NOW - timedelta(hours=4))
    stale = stored_weather(tmp_path, raw, observed=NOW - timedelta(hours=3))
    assert set(football_weather_features(event(), stale, target_base, cutoff=NOW)["states"].values()) == {"stale"}
    current = stored_weather(tmp_path)
    moved = {**event(), "scheduled_start": canonical_timestamp(START + timedelta(days=1)), "schedule_revision": "moved"}
    assert not any(football_weather_features(moved, current, base(moved), cutoff=NOW)["refs"].values())
    assert target_base == base()


def test_new_unknown_weather_revision_cannot_refresh_previous_value(tmp_path):
    first = weather()
    first["issued_at"] = canonical_timestamp(NOW - timedelta(hours=2))
    old = stored_weather(tmp_path, first, observed=NOW - timedelta(hours=1))
    missing = weather()
    missing["issued_at"] = None
    new = stored_weather(tmp_path, missing)
    result = football_weather_features(event(), old + new, base(), cutoff=NOW)
    assert not any(result["refs"].values())


def test_simultaneous_weather_revision_conflicts_and_tampering(tmp_path):
    first = stored_weather(tmp_path)
    raw = weather()
    raw["wind_mps"] = 20.
    other = stored_weather(tmp_path, raw)
    result = football_weather_features(event(), first + other, base(), cutoff=NOW)
    assert set(result["states"].values()) == {"conflicting"}
    altered = deepcopy(first)
    altered[0]["payload"]["temperature_c"] = 30.
    with pytest.raises(ContextContractError):
        football_weather_features(event(), altered, base(), cutoff=NOW)


def test_partial_weather_keeps_only_measured_numbers(tmp_path):
    raw = weather()
    raw["rain_3h_mm"] = None
    result = football_weather_features(event(), stored_weather(tmp_path, raw), base(), cutoff=NOW)
    assert result["values"]["rain_3h_mm"] is None
    assert result["refs"]["rain_3h_mm"] == []
    assert result["values"]["snow_3h_mm"] == 0


def test_native_domestic_and_international_completed_events_count_once(tmp_path):
    domestic = timeline(90, competition=39)
    continental = timeline(91, competition=2, end=NOW - timedelta(hours=60))
    rows = stored_load(tmp_path, [domestic, continental, domestic])
    result = football_schedule_features(event(), rows, cutoff=NOW, base=base())
    assert result["values"]["observed_matches_total_home"] == 2
    assert result["values"]["observed_matches_3d_home"] == 2
    assert result["values"]["observed_minutes_3d_home"] == 190.
    assert result["values"]["observed_recovery_exact_hours_home"] == 34.
    assert result["values"]["observed_recovery_minimum_hours_home"] == pytest.approx(34 - 2 / 60)
    assert result["values"]["history_complete_3d_home"] == 0
    assert result["values"]["observed_matches_total_away"] is None
    assert result["values"]["travel_hours_home"] is None


def test_real_api_detail_never_turns_elapsed_into_duration_or_exact_end(tmp_path):
    sample = json.loads((Path(__file__).parent / "fixtures/context/football/c1-schedule-20260907.json").read_text(encoding="utf-8"))
    received = datetime.fromisoformat(sample["received_at"])
    records = normalize_football_schedule(tuple(sample["examples"]), observed_at=received)
    assert {row["payload"]["actual_end"] for row in records} == {None}
    assert {row["payload"]["minutes"] for row in records} == {None}
    rows = store_rows(tmp_path, records, observed=received)
    target = {**event(), "home_id": "api-football:team:531", "away_id": "api-football:team:536"}
    result = football_schedule_features(target, rows, cutoff=NOW, base=base(target))
    assert result["values"]["observed_matches_total_home"] == 1
    assert result["values"]["observed_recovery_exact_hours_home"] is None
    assert result["values"]["observed_recovery_minimum_hours_home"] > 0
    assert result["values"]["observed_matches_7d_home"] is None
    assert result["values"]["observed_minutes_7d_home"] is None


@pytest.mark.parametrize("status", ["NS", "PST", "CANC", "ABD", "AWD", "WO", "1H", "2H", "TBD"])
def test_unplayed_or_unfinished_fixtures_add_no_load(tmp_path, status):
    raw = timeline(status=status)
    raw.update(actual_start=None, actual_end=None, minutes=None)
    result = football_schedule_features(event(), stored_load(tmp_path, [raw]), cutoff=NOW, base=base())
    assert result["values"]["observed_matches_total_home"] is None


def test_later_cancellation_withdraws_previous_completed_claim(tmp_path):
    old = stored_load(tmp_path, observed=NOW - timedelta(hours=1))
    revised = timeline(status="CANC")
    revised.update(actual_start=None, actual_end=None, minutes=None, result_observed_at=canonical_timestamp(NOW))
    new = stored_load(tmp_path, [revised])
    result = football_schedule_features(event(), old + new, cutoff=NOW, base=base())
    assert result["values"]["observed_matches_total_home"] is None


def test_unknown_match_end_has_receipt_bound_but_no_window_or_zero_minutes(tmp_path):
    raw = timeline()
    raw.update(actual_start=None, actual_end=None, minutes=None)
    result = football_schedule_features(event(), stored_load(tmp_path, [raw]), cutoff=NOW, base=base())
    assert result["values"]["observed_matches_total_home"] == 1
    assert result["values"]["observed_recovery_minimum_hours_home"] > 0
    assert result["values"]["observed_recovery_exact_hours_home"] is None
    assert result["values"]["observed_minutes_3d_home"] is None
    assert result["values"]["observed_matches_3d_home"] is None


def test_completed_receipt_after_cutoff_cannot_supply_load(tmp_path):
    rows = stored_load(tmp_path, observed=NOW + timedelta(minutes=1))
    result = football_schedule_features(event(), rows, cutoff=NOW, base=base())
    assert not any(result["refs"].values())


@pytest.mark.parametrize("change", [{"fixture_id": -1}, {"home_id": True}, {"away_id": 1}, {"minutes": 0},
    {"minutes": 121.}, {"actual_end": canonical_timestamp(NOW + timedelta(hours=1))},
    {"result_observed_at": canonical_timestamp(NOW + timedelta(seconds=1))}, {"odds": 1.8}])
def test_timeline_rejects_native_type_duration_and_causal_forgery(change):
    with pytest.raises(ContextContractError):
        normalize_football_schedule(({**timeline(), **change},), observed_at=NOW, source_schema="football-completed-transport-v1")


def test_complete_event_identity_blocks_partial_or_mixed_team_projections(tmp_path):
    rows = stored_load(tmp_path)
    partial = tuple(row for row in rows if row["subject_id"] == "api-football:team:1")
    assert not any(football_schedule_features(event(), partial, cutoff=NOW, base=base())["refs"].values())
    changed = timeline(away=2)
    more = stored_load(tmp_path, [changed])
    result = football_schedule_features(event(), rows + more, cutoff=NOW, base=base())
    assert result["states"]["observed_matches_total_home"] == "conflicting"


def test_new_participant_revision_removes_old_team_load(tmp_path):
    old = stored_load(tmp_path, observed=NOW - timedelta(hours=1))
    current = stored_load(tmp_path, [timeline(home=4)])
    result = football_schedule_features(event(), old + current, cutoff=NOW, base=base())
    assert result["values"]["observed_matches_total_home"] is None


def test_event_orientation_and_full_baseline_are_in_feature_identity(tmp_path):
    rows = stored_load(tmp_path)
    original = football_schedule_features(event(), rows, cutoff=NOW, base=base())
    reversed_event = {**event(), "home_id": event()["away_id"], "away_id": event()["home_id"]}
    reversed_result = football_schedule_features(reversed_event, rows, cutoff=NOW, base=base(reversed_event))
    assert reversed_result["values"]["observed_matches_total_away"] == original["values"]["observed_matches_total_home"]
    assert reversed_result["reference_hash"] != original["reference_hash"]
    expected = digest({"version": "football-context-reference-v2", "base_hash": digest(validate_base_distribution(base())),
                       "event_hash": digest(validate_event(event())), "preprocessing": []})
    assert original["reference_hash"] == expected
    changed_base = base()
    changed_base["params"]["home_lambda"] = 1.6
    assert football_schedule_features(event(), rows, cutoff=NOW, base=changed_base)["reference_hash"] != expected


def test_stored_numeric_tampering_does_not_enter_timeline(tmp_path):
    rows = deepcopy(stored_load(tmp_path))
    rows[0]["payload"]["minutes"] = 100.
    with pytest.raises(ContextContractError):
        football_schedule_features(event(), rows, cutoff=NOW, base=base())


def test_signed_window_features_reference_only_their_two_actual_operands(tmp_path):
    rows = stored_load(tmp_path, [timeline(90, end=NOW - timedelta(hours=10)),
                                 timeline(91, end=NOW - timedelta(hours=60)),
                                 timeline(92, home=2, end=NOW - timedelta(hours=12))])
    result = football_schedule_features(event(), rows, cutoff=NOW, base=base())
    expected = sorted(set(result["refs"]["observed_minutes_1d_home"]) | set(result["refs"]["observed_minutes_1d_away"]))
    assert len(expected) == 2
    assert result["refs"]["observed_minutes_1d_delta"] == expected


@pytest.mark.parametrize("join", ["verified_native", "unresolved"])
def test_known_baseline_team_identity_cannot_change_for_weather_or_load(join):
    from test_context_contracts import football_reference_base
    original = {**football_reference_base(), "event_key": event()["event_key"], "cutoff": canonical_timestamp(NOW)}
    for head in original["reference_weights"]["heads"].values():
        for component in head["components"].values():
            component["team_join"] = join
    changed = {**event(), "home_id": event()["away_id"], "away_id": event()["home_id"]}
    with pytest.raises(ContextContractError, match="orientation"):
        football_schedule_features(changed, (), cutoff=NOW, base=original)
    with pytest.raises(ContextContractError, match="orientation"):
        football_weather_features(changed, (), original, cutoff=NOW)


def test_match_ending_at_decision_is_not_prior_completed_load(tmp_path):
    raw = timeline(end=NOW)
    raw["result_observed_at"] = canonical_timestamp(NOW)
    result = football_schedule_features(event(), stored_load(tmp_path, [raw]), cutoff=NOW, base=base())
    assert result["values"]["observed_matches_total_home"] is None


def test_signed_features_preserve_conflict_state(tmp_path):
    first = stored_load(tmp_path)
    revised = stored_load(tmp_path, [timeline(away=2)])
    result = football_schedule_features(event(), first + revised, cutoff=NOW, base=base())
    assert result["states"]["observed_matches_total_delta"] == "conflicting"


def test_fresh_target_status_invalidates_weather_without_mutating_event_dict(tmp_path):
    from context_models.contracts import normalize_observation
    weather_rows = stored_weather(tmp_path)
    status = normalize_observation({"event_key": event()["event_key"], "sport": "football", "competition": "39",
        "format": "90min", "subject_id": event()["event_key"], "kind": "event_status", "source": "api-football",
        "source_schema": "fixture-status-v1", "source_revision": "status-cancelled", "schedule_revision": "schedule-v1",
        "published_at": None, "publication_proof": None, "valid_from": canonical_timestamp(NOW), "valid_until": None,
        "complete": True, "payload": {"status": "cancelled"}}, observed_at=NOW)
    statuses = store_rows(tmp_path, (status,))
    result = football_weather_features(event(), weather_rows + statuses, base(), cutoff=NOW)
    assert set(result["states"].values()) == {"not_applicable"}


def test_raw_price_and_unknown_fields_do_not_change_native_sport_record():
    sample = json.loads((Path(__file__).parent / "fixtures/context/football/c1-schedule-20260907.json").read_text(encoding="utf-8"))
    original = sample["examples"][0]
    changed = deepcopy(original)
    changed.update(odds={"anything": 1.05}, arbitrary="not-a-sport-field")
    changed["fixture"]["bookmakerPrice"] = 1000.
    before = normalize_football_schedule((original,), observed_at=NOW)
    after = normalize_football_schedule((changed,), observed_at=NOW)
    assert digest(before) == digest(after)


def test_csv_positive_id_cannot_claim_the_native_source():
    sample = json.loads((Path(__file__).parent / "fixtures/context/football/c1-schedule-20260907.json").read_text(encoding="utf-8"))
    raw = {**sample["examples"][0], "challenge_source": "football-data-results-only"}
    with pytest.raises(ContextContractError):
        normalize_football_schedule((raw,), observed_at=NOW)


def test_empty_history_is_unknown_not_zero_or_complete():
    result = football_schedule_features(event(), (), cutoff=NOW, base=base())
    assert all(value is None for value in result["values"].values())
    assert not any(result["refs"].values())


@pytest.mark.parametrize("days,offset,count", [(1, 0, 1), (1, -1, None), (3, 0, 1), (7, 0, 1)])
def test_performed_load_windows_have_exact_end_time_boundaries(tmp_path, days, offset, count):
    raw = timeline(end=NOW - timedelta(days=days) + timedelta(seconds=offset))
    result = football_schedule_features(event(), stored_load(tmp_path, [raw]), cutoff=NOW, base=base())
    assert result["values"][f"observed_matches_{days}d_home"] == count


def test_forecast_publication_and_valid_point_never_replace_receipt_clock(tmp_path):
    raw = weather()
    raw["issued_at"] = canonical_timestamp(NOW + timedelta(seconds=1))
    with pytest.raises(ContextContractError):
        normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast")
    valid = stored_weather(tmp_path)
    assert valid[0]["published_at"] is None and valid[0]["publication_proof"] is None
    assert valid[0]["observed_at"] == canonical_timestamp(NOW)
    assert valid[0]["observed_at"] != valid[0]["payload"]["valid_at"]


@pytest.mark.parametrize("field,value", [("event_hash", "a" * 64), ("source_kind", "actual")])
def test_weather_transport_cannot_relabel_scope_or_kind(field, value):
    raw = weather()
    raw[field] = value
    with pytest.raises(ContextContractError):
        normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast")


def test_new_c1_versions_do_not_inherit_injury_only_b5(tmp_path):
    from context_models.football_effect import apply_football_effect
    from test_football_context_model import inputs, event as injury_event
    original, _, injury_artifact = inputs()
    target = injury_event()
    forecasts = football_weather_features(target, (), original, cutoff=NOW)
    workload = football_schedule_features(target, (), cutoff=NOW, base=original)
    for feature in (forecasts, workload):
        with pytest.raises(ContextContractError, match="feature version"):
            apply_football_effect(original, feature, injury_artifact, event=target)


def test_sanitized_real_projection_is_bound_to_the_original_record_bytes():
    import hashlib
    sample = json.loads((Path(__file__).parent / "fixtures/context/football/c1-schedule-20260907.json").read_text(encoding="utf-8"))
    original_bytes = (Path(__file__).parents[1] / sample["original_path"]).read_bytes()
    assert hashlib.sha256(original_bytes).hexdigest() == sample["original_sha256"]
    original = json.loads(original_bytes)
    assert sample["received_at"] == original["received_at"]
    for projected in sample["examples"]:
        source = next(row for row in original["examples"] if row["fixture"]["id"] == projected["fixture"]["id"])
        assert projected["league"] == {key: source["league"][key] for key in ("id", "season")}
        assert projected["teams"] == {side: {"id": source["teams"][side]["id"]} for side in ("home", "away")}
        for key, value in projected["fixture"].items():
            if key == "status":
                assert value == {field: source["fixture"][key][field] for field in value}
            else:
                assert source["fixture"][key] == value


def test_weather_and_load_are_pure_cpu_and_preserve_input_objects(tmp_path, monkeypatch):
    import requests
    import sqlite3
    raw, played = weather(), timeline()
    forecast_rows, schedule_rows = stored_weather(tmp_path, raw), stored_load(tmp_path, [played])
    original = deepcopy((raw, played, forecast_rows, schedule_rows))

    def forbidden(*args, **kwargs):
        raise AssertionError("C1 feature mechanics must not do I/O")

    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast")
    normalize_football_schedule((played,), observed_at=NOW, source_schema="football-completed-transport-v1")
    football_weather_features(event(), forecast_rows, base(), cutoff=NOW)
    football_schedule_features(event(), schedule_rows, cutoff=NOW, base=base())
    assert (raw, played, forecast_rows, schedule_rows) == original


@pytest.mark.parametrize("feature_kind", ["weather", "load"])
def test_changed_decision_requires_a_fresh_base_revision(feature_kind):
    with pytest.raises(ContextContractError, match="decision"):
        if feature_kind == "weather":
            football_weather_features(event(), (), base(), cutoff=NOW + timedelta(seconds=1))
        else:
            football_schedule_features(event(), (), cutoff=NOW + timedelta(seconds=1), base=base())


def test_forecast_canonical_timezone_and_json_order_do_not_change_identity():
    raw = weather()
    modified = {key: deepcopy(raw[key]) for key in reversed(raw)}
    for key in ("issued_at", "valid_at", "valid_from", "valid_until"):
        modified[key] = datetime.fromisoformat(modified[key]).astimezone(timezone(timedelta(hours=2))).isoformat()
    assert digest(normalize_weather(event(), modified, observed_at=NOW, source_kind="forecast")) == digest(
        normalize_weather(event(), raw, observed_at=NOW, source_kind="forecast"))
