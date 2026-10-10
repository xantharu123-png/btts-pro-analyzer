"""Highlighting needs real same-artifact checks, not a blanket release flag."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from ev_signal_sources import ModelSignal
from forecast_analysis import (
    forecast_highlight_reason, project_football_analysis, read_football_analysis,
)
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog


NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
CHECKED = "2030-01-01T11:30:00+00:00"


def row():
    value = dict(candidate_id="81:DC_1X", fixture_id=81, home_id=11, away_id=12,
        home_team="Alpha", away_team="Beta", market_key="DC_1X", probability=.75,
        scheduled_start="2030-01-01T16:00:00+00:00", modeled_at=NOW.isoformat(),
        input_cutoff_at=NOW.isoformat(), model_scope="same_competition",
        context={
            "checked_at": CHECKED,
            "h2h": {"status": "neutral", "availability": "available", "matches": 0,
                    "checked_at": CHECKED},
            "weather": {"status": "passed", "availability": "available",
                        "temperature_c": 10., "wind_mps": 2., "rain_3h_mm": 0.,
                        "snow_3h_mm": 0., "veto_applied": False, "checked_at": CHECKED},
            "injuries": {"status": "observed", "availability": "available",
                         "coverage_available": True, "home_missing": 0, "away_missing": 0,
                         "impact_assessment_complete": True, "checked_at": CHECKED},
            "lineups": {"status": "pending", "checked_at": CHECKED},
            "release_context_complete": False,
        })
    comparison = dict(schema="league-market-comparison-v1", fixture_id=81,
        home_id=11, away_id=12, league_id=39, market_key="DC_1X",
        scheduled_start=value["scheduled_start"], prediction_version="test-model-v1",
        validation_prediction_version="test-model-v1", model_skill_supported=True,
        samples=400, successes=200, latest_kickoff="2029-12-31T12:00:00+00:00",
        probabilities=[.75, .70, .80])
    value["analysis_evidence"] = project_football_analysis(value, model_basis={
        **value, "expected_home_goals": 1.8, "expected_away_goals": .9,
        "venue_samples": [12, 12], "form_samples": [6, 6], "market_comparison": comparison})
    return value


def signal(value):
    return ModelSignal(key="81:DC_1X", label="Alpha vs Beta", probability=.75,
        probability_haircut=.08, evidence_stage="SHADOW", policy_version="test-v1",
        detail="", source="automated_wettfinder_forecast", sport="Fußball",
        event_label="Alpha vs Beta", market="Doppelte Chance", selection="1X",
        market_key="DC_1X", candidate_id=value["candidate_id"], fixture_id=81,
        home_team="Alpha", away_team="Beta", home_team_id=11, away_team_id=12,
        scheduled_start=value["scheduled_start"], modeled_at=value["modeled_at"],
        input_cutoff_at=value["input_cutoff_at"], model_scope="same_competition",
        model_version="test-model-v1", context_complete=False,
        price_checked_at=NOW.isoformat(),
        analysis_evidence=read_football_analysis(value, now=NOW))


@pytest.mark.parametrize('lineup', [{'status': 'blocked'},
                                  {'status': 'blocked', 'checked_at': 'invalid'}])
def test_serialized_negative_lineup_survives_without_claiming_a_check_clock(lineup):
    value = row()
    value['analysis_evidence']['context']['lineups'] = lineup
    value['context'] = {}
    current = signal(value)
    from test_highlight_price_checks import _quote
    current = replace(current, reference_quote=_quote(current, fetched_at=NOW).to_dict())
    before = deepcopy(vars(current))
    card = build_wettfinder_card(current, now=NOW)
    catalog = compose_wettfinder_catalog([card])
    assert catalog.featured == ()
    assert [item.key for item in catalog.additional] == [current.key]
    assert card.model_probability == current.probability
    assert vars(current) == before
    assert current.analysis_evidence['context']['lineups'] == {'status': 'blocked'}


def test_serialized_pending_lineup_without_clock_is_not_a_blanket_top_block():
    value = row()
    value['analysis_evidence']['context']['lineups'] = {'status': 'pending'}
    value['context'] = {}
    current = signal(value)
    card = build_wettfinder_card(current, now=NOW)
    assert compose_wettfinder_catalog([card]).featured == (card,)


@pytest.mark.parametrize("axis", ["h2h", "weather", "injuries"])
def test_missing_relevant_check_stays_in_catalog_but_is_not_highlighted(axis):
    value = row()
    value["context"].pop(axis)
    value["analysis_evidence"]["context"].pop(axis, None)
    current = signal(value)
    card = build_wettfinder_card(current, now=NOW)
    catalog = compose_wettfinder_catalog([card])
    assert catalog.featured == ()
    assert [item.key for item in catalog.additional] == ["81:DC_1X"]
    assert card.model_probability == .75
    assert current.reference_quote is None


@pytest.mark.parametrize("axis", ["h2h", "weather", "injuries"])
@pytest.mark.parametrize("age", [76, -1])
def test_old_or_future_original_check_does_not_qualify_for_highlight(axis, age):
    value = row()
    stamp = (NOW - timedelta(minutes=age)).isoformat()
    value["context"][axis]["checked_at"] = stamp
    value["analysis_evidence"]["context"].pop(axis, None)
    assert forecast_highlight_reason(signal(value), now=NOW)


@pytest.mark.parametrize("axis", ["h2h", "weather", "injuries"])
@pytest.mark.parametrize("status", ["unavailable", "blocked", True, []])
def test_failed_or_untyped_checks_cannot_highlight(axis, status):
    value = row()
    value["context"][axis]["status"] = status
    value["analysis_evidence"]["context"].pop(axis, None)
    assert forecast_highlight_reason(signal(value), now=NOW)


@pytest.mark.parametrize("lineup", ["pending", "confirmation_due", "passed"])
def test_current_checks_can_highlight_without_confirmed_lineups_or_bookmaker_price(lineup):
    value = row()
    value["context"]["lineups"]["status"] = lineup
    value["analysis_evidence"]["context"]["lineups"]["status"] = lineup
    current = signal(value)
    card = build_wettfinder_card(current, now=NOW)
    assert not forecast_highlight_reason(current, now=NOW)
    assert [item.key for item in compose_wettfinder_catalog([card]).featured] == ["81:DC_1X"]
    assert current.context_complete is False and current.reference_quote is None
    assert current.probability == .75


def test_legacy_envelope_recovers_same_artifact_checks_without_renewing_clocks():
    value = row()
    before = deepcopy(value)
    value["analysis_evidence"]["context"].pop("h2h", None)
    value["analysis_evidence"]["context"].pop("weather", None)
    actual = read_football_analysis(value, now=NOW)
    assert actual["context"]["h2h"]["checked_at"] == CHECKED
    assert actual["context"]["h2h"]["status"] == "neutral"
    assert actual["context"]["weather"]["checked_at"] == CHECKED
    assert actual["context"]["weather"]["status"] == "passed"
    assert value["context"] == before["context"]
    assert "h2h" not in value["analysis_evidence"]["context"]
    assert not forecast_highlight_reason(signal(value), now=NOW)


@pytest.mark.parametrize("axis,field,bad", [
    ("h2h", "status", "blocked"), ("h2h", "checked_at", "2030-01-01T11:31:00+00:00"),
    ("weather", "status", "blocked"), ("weather", "veto_applied", True),
    ("injuries", "home_missing", 9),
])
def test_conflicting_same_artifact_checks_cannot_choose_the_positive_version(axis, field, bad):
    value = row()
    # A conflicting saved envelope must not be replaced with the raw positive check.
    value["analysis_evidence"]["context"][axis] = deepcopy(value["context"][axis])
    value["analysis_evidence"]["context"][axis][field] = bad
    assert forecast_highlight_reason(signal(value), now=NOW)


@pytest.mark.parametrize("stale", [True, 0, "false", None])
def test_explicit_global_staleness_never_turns_into_a_highlight(stale):
    value = row()
    value["context_stale"] = stale
    assert forecast_highlight_reason(signal(value), now=NOW)


def test_no_hydration_from_another_model_or_event_revision():
    value = row()
    value["fixture_id"] = 82
    assert read_football_analysis(value, now=NOW) is None
    assert forecast_highlight_reason(signal(value), now=NOW)


def test_exact_age_boundary_uses_original_clock_not_model_clock():
    value = row()
    stamp = (NOW - timedelta(minutes=75)).isoformat()
    for axis in ("h2h", "weather", "injuries"):
        value["context"][axis]["checked_at"] = stamp
        value["analysis_evidence"]["context"].pop(axis, None)
    assert not forecast_highlight_reason(signal(value), now=NOW)


def test_partial_weather_envelope_cannot_drop_same_artifact_veto():
    value = row()
    value["analysis_evidence"]["context"]["weather"].pop("veto_applied")
    value["context"]["weather"]["veto_applied"] = True
    assert forecast_highlight_reason(signal(value), now=NOW)


@pytest.mark.parametrize("axis,field,bad", [
    ("weather", "veto_applied", "false"), ("weather", "veto_applied", 0),
    ("weather", "veto_applied", None), ("h2h", "matches", True),
    ("h2h", "matches", -1), ("h2h", "matches", "0"),
])
def test_explicit_untyped_observation_details_do_not_become_a_positive_check(axis, field, bad):
    value = row()
    value["context"][axis][field] = bad
    value["analysis_evidence"]["context"].pop(axis, None)
    assert forecast_highlight_reason(signal(value), now=NOW)
