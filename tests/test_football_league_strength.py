"""UEFA league strength for the home-league transfer model (plan 2026-11-05, step 1)."""
import math
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

import challenge_engine as engine
import football_league_strength as strength
from challenge_engine import MARKET_SPECS, MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
from challenge_15k import scan_daily_challenge
from football_original import football_original_inputs
from tests.test_challenge_15k import credible_validation, fixture

KICKOFF = datetime(2030, 8, 4, 18, tzinfo=timezone.utc)


def _uefa_history():
    return [fixture(1000 + index, KICKOFF - timedelta(days=200 - index), 100 + index % 6, 200 + index % 6,
                    1 + index % 3, index % 2, league_id=2) for index in range(30)]


def _domestic(home_league, away_league):
    home = [fixture(2000 + index, KICKOFF - timedelta(days=8 + index), 1, 300 + index, 2, 1,
                    league_id=home_league) for index in range(8)]
    away = [fixture(3000 + index, KICKOFF - timedelta(days=8 + index), 400 + index, 2, 1, 1,
                    league_id=away_league) for index in range(8)]
    return home, away


def test_annotation_uses_the_fitted_law_for_both_sides():
    note = strength.league_strength_annotation(39, 389)
    gap = strength.STRENGTHS[39] - strength.STRENGTHS[389]
    assert note == {"version": strength.VERSION, "home_league_id": 39, "away_league_id": 389,
                    "home_factor": math.exp(strength.HOME_OFFSET + gap),
                    "away_factor": math.exp(strength.AWAY_OFFSET - gap)}
    assert note["home_factor"] > 2.5 and note["away_factor"] < 0.4  # England at home against Kazakhstan
    same = strength.league_strength_annotation(78, 78)
    assert same["home_factor"] == math.exp(strength.HOME_OFFSET)
    assert same["away_factor"] == math.exp(strength.AWAY_OFFSET)


@pytest.mark.parametrize("home, away", [(39, 999999), (999999, 39), (True, 39), (0, 39), (-5, 39), ("39", 39)])
def test_league_without_estimate_or_invalid_id_has_no_annotation(home, away):
    assert strength.league_strength_annotation(home, away) is None


def test_factors_accept_only_an_unchanged_annotation():
    note = strength.league_strength_annotation(140, 207)
    assert strength.league_strength_factors(note) == (note["home_factor"], note["away_factor"])
    for broken in ({**note, "home_factor": note["home_factor"] * 1.01}, {**note, "version": "other"},
                   {**note, "extra": 1}, {key: value for key, value in note.items() if key != "away_factor"},
                   {**note, "home_league_id": 999999}, {**note, "away_factor": float("nan")},
                   {**note, "away_factor": True}, None, "annotation"):
        assert strength.league_strength_factors(broken) is None


def test_model_multiplies_every_rate_variant_and_records_the_factor():
    home, away = _domestic(39, 389)
    target = fixture(900, KICKOFF, 1, 2, league_id=2)
    plain = engine._fixture_model(target, _uefa_history(), team_history=home + away)
    note = strength.league_strength_annotation(39, 389)
    adjusted = engine._fixture_model({**target, "challenge_league_strength": note}, _uefa_history(),
                                     team_history=home + away)
    for key in ("active_lambdas", "season_lambdas", "form_lambdas"):
        assert adjusted[key][0] == pytest.approx(plain[key][0] * note["home_factor"], rel=1e-12)
        assert adjusted[key][1] == pytest.approx(plain[key][1] * note["away_factor"], rel=1e-12)
    assert adjusted["league_strength"] == note
    assert "league_strength" not in plain
    assert adjusted["venue_samples"] == plain["venue_samples"]


def test_model_fails_closed_on_a_foreign_annotation_and_on_too_high_rates(monkeypatch):
    home, away = _domestic(39, 389)
    target = fixture(900, KICKOFF, 1, 2, league_id=2)
    note = strength.league_strength_annotation(39, 389)
    forged = {**target, "challenge_league_strength": {**note, "home_factor": 1.0}}
    assert engine._fixture_model(forged, _uefa_history(), team_history=home + away) is None
    monkeypatch.setitem(strength.STRENGTHS, 39, 3.0)
    huge = strength.league_strength_annotation(39, 389)
    assert engine._fixture_model({**target, "challenge_league_strength": huge}, _uefa_history(),
                                 team_history=home + away) is None


def test_provenance_never_signs_adjusted_rates():
    home, away = _domestic(39, 389)
    target = {**fixture(900, KICKOFF, 1, 2, league_id=2),
              "challenge_league_strength": strength.league_strength_annotation(39, 389)}
    model = engine._fixture_model(target, _uefa_history(), team_history=home + away, include_provenance=True)
    assert model["history_refs"] == []
    assert model["reference_weights"] == {"schema": 1, "kind": "unavailable",
                                          "reason": "football-league-strength-not-modeled"}


def test_original_capture_keeps_the_annotation():
    note = strength.league_strength_annotation(61, 218)
    target = {**fixture(900, KICKOFF, 1, 2, league_id=2), "challenge_league_strength": note}
    inputs = football_original_inputs(target, [], None, logical_history_cutoff=KICKOFF)
    assert inputs["fixture"]["challenge_league_strength"] == note
    plain = football_original_inputs(fixture(900, KICKOFF, 1, 2, league_id=2), [], None,
                                     logical_history_cutoff=KICKOFF)
    assert "challenge_league_strength" not in plain["fixture"]


def _provider(home_league, away_league):
    home, away = _domestic(home_league, away_league)
    upcoming = fixture(900, KICKOFF, 1, 2, league_id=2)
    provider = Mock()
    provider.errors = []
    provider.upcoming_fixtures.return_value = [upcoming]
    provider.completed_history.return_value = _uefa_history()
    provider.coverage.return_value = {"injuries": False, "lineups": False}
    provider.domestic_team_history.side_effect = [
        {"league_id": home_league, "season": 2026, "fixtures": home},
        {"league_id": away_league, "season": 2026, "fixtures": away},
    ]
    provider.injuries_by_fixture.return_value = {900: []}
    provider.details_by_fixture.return_value = {900: upcoming}
    provider.h2h.return_value = []
    provider.weather.return_value = {"temperature_c": 20.0, "wind_kmh": 5.0, "precipitation_mm": 0.0}
    return provider, upcoming


def _scan(provider):
    with patch("challenge_15k._cached_market_calibration", return_value={}), \
            patch("challenge_15k._cached_market_validation",
                  return_value={spec.key: credible_validation() for spec in MARKET_SPECS}), \
            patch("challenge_15k.annotate_history_xg", return_value={"coverage": 1.0}):
        return scan_daily_challenge(provider, [2], date(2030, 8, 4), 8)


def test_scan_applies_league_strength_to_the_transfer_forecast():
    provider, upcoming = _provider(113, 332)
    snapshot = _scan(provider)
    assert snapshot["continental_league_strength_missing"] == 0
    assert snapshot["provisional_forecast_fixtures"] == 1
    assert upcoming["challenge_league_strength"] == strength.league_strength_annotation(113, 332)
    forecast = snapshot["forecast_shortlist"][0]
    assert forecast.model_scope == MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
    assert any(reason.startswith("Ligastärke aus Europapokal-Duellen eingerechnet") for reason in forecast.reasons)
    home, away = _domestic(113, 332)
    plain = engine._fixture_model(fixture(900, KICKOFF, 1, 2, league_id=2), _uefa_history(),
                                  team_history=home + away)
    note = strength.league_strength_annotation(113, 332)
    assert forecast.expected_home_goals == round(plain["active_lambdas"][0] * note["home_factor"], 3)
    assert forecast.expected_away_goals == round(plain["active_lambdas"][1] * note["away_factor"], 3)


def test_scan_without_league_estimate_keeps_no_transfer_forecast():
    provider, upcoming = _provider(113, 999999)
    snapshot = _scan(provider)
    assert snapshot["continental_league_strength_missing"] == 1
    assert snapshot["continental_validation_fixtures"] == 0
    assert snapshot["provisional_forecast_fixtures"] == 0
    assert snapshot["forecast_shortlist"] == []
    assert "challenge_league_strength" not in upcoming
    # No domestic validation is fetched for a game that cannot get a forecast.
    assert all(call.args[0] == 2 for call in provider.completed_history.call_args_list)
