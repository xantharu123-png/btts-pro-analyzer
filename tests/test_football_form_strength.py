"""Form strength as an opt-in goal basis (pre-registered test 06.11.2026)."""
import math
from datetime import datetime, timedelta, timezone

import pytest

import challenge_engine as engine
import football_form_strength as form
from tests.test_challenge_15k import fixture

FORM = engine.GOAL_MODEL_FORM_STRENGTH
KICKOFF = datetime(2030, 3, 1, 18, tzinfo=timezone.utc)


def _league(league_id=39, games=40):
    """Round robin of six teams; team 1 wins every match 2:0, team 2 loses every match 0:1."""
    rows, index = [], 0
    teams = [1, 2, 3, 4, 5, 6]
    for round_number in range(games // 3):
        for offset in range(3):
            home = teams[(round_number + offset) % 6]
            away = teams[(round_number + offset + 3) % 6]
            if home == 1 or away == 2:
                score = (2, 0) if home == 1 else (1, 0)
            elif away == 1 or home == 2:
                score = (0, 2) if away == 1 else (0, 1)
            else:
                score = (1 + index % 2, index % 3)
            rows.append(fixture(5000 + index, KICKOFF - timedelta(days=200 - 3 * round_number, hours=offset),
                                home, away, *score, league_id=league_id))
            index += 1
    return rows


def test_registry_keeps_the_basis_off_and_unreleasable():
    assert FORM in engine.GOAL_MODELS and FORM not in engine.GOAL_MODEL_OPTIONS
    version = engine.prediction_version_for_goal_model(FORM)
    assert version != engine.CHALLENGE_PREDICTION_VERSION
    assert engine.goal_model_for_prediction_version(version) is None
    assert form.VERSION == "form-strength-v1-20261106"
    assert (form.KAPPA, form.WINDOW, form.MIN_GAMES) == (0.11, 10, 5)


def test_team_form_uses_the_last_ten_league_games_before_kickoff_only():
    history = _league()
    later = fixture(9000, KICKOFF + timedelta(days=1), 1, 3, 0, 9)
    other_league = fixture(9001, KICKOFF - timedelta(days=1), 1, 3, 0, 9, league_id=140)
    kwargs = {"fixture_datetime": engine._fixture_datetime, "fixture_score": engine._fixture_score}
    value = form.team_form(history + [later, other_league], 1, 39, KICKOFF, **kwargs)
    assert value == form.team_form(history, 1, 39, KICKOFF, **kwargs) == 2.0
    assert form.team_form(history, 2, 39, KICKOFF, **kwargs) == -1.0
    assert form.team_form(history[:6], 1, 39, KICKOFF, **kwargs) is None  # fewer than five matches


def test_form_basis_multiplies_every_rate_variant_by_the_preregistered_factor():
    history = _league()
    target = fixture(900, KICKOFF, 1, 2, league_id=39)
    legacy = engine._fixture_model(target, history)
    adjusted = engine._fixture_model(target, history, goal_model=FORM)
    home_factor, away_factor = math.exp(0.11 * 3.0), math.exp(-0.11 * 3.0)
    for key in ("active_lambdas", "season_lambdas", "form_lambdas"):
        assert adjusted[key][0] == pytest.approx(legacy[key][0] * home_factor, rel=1e-12)
        assert adjusted[key][1] == pytest.approx(legacy[key][1] * away_factor, rel=1e-12)
    assert adjusted["form_strength"] == form.form_strength_annotation(2.0, -1.0)
    assert "form_strength" not in legacy


def test_without_enough_games_the_form_basis_applies_no_factor(monkeypatch):
    history = _league()
    target = fixture(900, KICKOFF, 1, 2, league_id=39)
    legacy = engine._fixture_model(target, history)
    real = form.team_form
    # Team 2 has fewer than MIN_GAMES league matches in this scenario (e.g. a promoted club).
    monkeypatch.setattr(form, "team_form", lambda h, team, *a, **k: None if team == 2 else real(h, team, *a, **k))
    adjusted = engine._fixture_model(target, history, goal_model=FORM)
    assert adjusted["active_lambdas"] == legacy["active_lambdas"]
    assert adjusted["season_lambdas"] == legacy["season_lambdas"]
    assert adjusted["form_strength"] is None


def test_form_basis_fails_closed_outside_the_tested_league_path():
    history = _league()
    target = fixture(900, KICKOFF, 1, 2, league_id=39)
    assert engine._fixture_model(target, history, team_history=history, goal_model=FORM) is None
    national = {**target, "challenge_senior_national_team": True}
    assert engine._fixture_model(national, history, goal_model=FORM) is None
    for uefa in (2, 3, 848):
        cup = _league(league_id=uefa)
        assert engine._fixture_model(fixture(900, KICKOFF, 1, 2, league_id=uefa), cup) is not None
        assert engine._fixture_model(fixture(900, KICKOFF, 1, 2, league_id=uefa), cup, goal_model=FORM) is None


def test_factors_accept_only_an_unchanged_annotation():
    note = form.form_strength_annotation(1.5, -0.5)
    assert form.form_strength_factors(note) == (note["home_factor"], note["away_factor"])
    for broken in ({**note, "home_factor": note["home_factor"] * 1.01}, {**note, "version": "other"},
                   {**note, "extra": 1}, {**note, "away_form": float("nan")}, {**note, "home_form": True},
                   {**note, "home_form": 11.0}, None, "note"):
        assert form.form_strength_factors(broken) is None
    assert form.form_strength_annotation(None, 1.0) is None
    assert form.form_strength_annotation(12.0, 1.0) is None


def test_provenance_never_signs_form_adjusted_rates():
    history = _league()
    target = fixture(900, KICKOFF, 1, 2, league_id=39)
    model = engine._fixture_model(target, history, goal_model=FORM, include_provenance=True)
    assert model["history_refs"] == []
    assert model["reference_weights"] == {"schema": 1, "kind": "unavailable",
                                          "reason": "football-form-strength-not-modeled"}


def test_walk_forward_records_equal_the_study_recipe():
    """The opt-in basis reproduces the patched study path of output/formstaerke-20261106/study.py."""
    history = sorted(_league(games=60), key=engine._fixture_datetime)
    expected_records = {}
    original = engine._fixture_model

    def study_patch(target, league_history, *args, **kwargs):
        model = original(target, league_history, *args, **kwargs)
        if model is None:
            return model
        kwargs_form = {"fixture_datetime": engine._fixture_datetime, "fixture_score": engine._fixture_score}
        kickoff = engine._fixture_datetime(target)
        sh = form.team_form(league_history, target["teams"]["home"]["id"], 39, kickoff, **kwargs_form)
        sa = form.team_form(league_history, target["teams"]["away"]["id"], 39, kickoff, **kwargs_form)
        if sh is None or sa is None:
            return model
        for key in ("active_lambdas", "season_lambdas", "form_lambdas"):
            h, a = model[key]
            model[key] = (h * math.exp(0.11 * (sh - sa)), a * math.exp(0.11 * (sa - sh)))
        return model

    engine._fixture_model = study_patch
    try:
        expected_records = engine._walk_forward_market_records(history)
    finally:
        engine._fixture_model = original
    actual = engine._walk_forward_market_records(history, goal_model=FORM)
    legacy = engine._walk_forward_market_records(history)
    key = "RESULT_HOME"
    assert actual[key]["probabilities"] == pytest.approx(expected_records[key]["probabilities"], rel=1e-12)
    assert actual[key]["probabilities"] != legacy[key]["probabilities"]


def test_measurement_scores_only_new_games_of_both_arms():
    from scripts.form_strength_measurement import league_losses, scored_records, verdict
    history = sorted(_league(games=60), key=engine._fixture_datetime)
    since = engine._fixture_datetime(history[45])
    live = scored_records(history, engine.GOAL_MODEL_LEGACY, since)
    adjusted = scored_records(history, FORM, since)
    assert set(live) == {spec.key for spec in engine.GOAL_MARKET_SPECS}
    later_ids = {str(item["fixture"]["id"]) for item in history if engine._fixture_datetime(item) >= since}
    assert set(live["RESULT_HOME"]) <= later_ids and live["RESULT_HOME"]
    totals, bands = league_losses(live, adjusted)
    assert totals["n"] == sum(len(pairs) for pairs in live.values())
    assert totals["db"] != 0.0
    summary = verdict({39: totals, 140: totals}, bands)
    assert summary["forecasts"] == 2 * totals["n"] and len(summary["conditions"]) == 4
    nothing = scored_records(history, FORM, engine._fixture_datetime(history[-1]) + timedelta(days=1))
    assert verdict({39: league_losses(nothing, nothing)[0]}, bands)["status"] == "not_enough_data"
