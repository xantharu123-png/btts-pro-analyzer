from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import combinations
import math

import pytest

import sports_prematch as model


NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def event(sport="basketball", **changes):
    providers = {"basketball": "ESPN", "ice_hockey": "NHL", "cricket": "Cricbuzz"}
    leagues = {"basketball": "NBA", "ice_hockey": "NHL", "cricket": "League T20"}
    result = {
        "provider": providers[sport], "provider_event_id": "future-match",
        "competition": leagues[sport], "home_team_id": "1", "away_team_id": "8",
        "home_team": "Team 1", "away_team": "Team 8", "neutral_site": False,
        "starts_at": (NOW + timedelta(hours=6)).isoformat(), "game_type": 2,
        "format": "t20", "status": "upcoming",
    }
    result.update(changes)
    return result


def history(sport="basketball", *, newly_imported=False):
    identity = event(sport)
    rows = []
    for cycle in range(3):
        for a, b in combinations(range(1, 9), 2):
            h, away = (a, b) if cycle % 2 == 0 else (b, a)
            i = len(rows)
            start = NOW - timedelta(days=100 - i)
            observed = NOW - timedelta(minutes=1) if newly_imported else start + timedelta(hours=4)
            margin = 3 * (away - h) + 3 + (i % 7 - 3)
            if margin == 0:
                margin = 1
            row = {
                "provider": identity["provider"], "provider_event_id": f"match-{i}",
                "competition": identity["competition"], "sport": sport,
                "start_time": start.isoformat(), "result_observed_at": observed.isoformat(),
                "status": "completed", "home_team_id": str(h), "away_team_id": str(away),
                "home_team": f"Team {h}", "away_team": f"Team {away}",
                "winner_side": "home" if margin > 0 else "away", "neutral_site": False,
                "home_score": 100 + margin, "away_score": 100,
                "result_scope": model._SCOPES[sport], "format": "t20", "game_type": 2,
            }
            if sport == "ice_hockey":
                home_goals = max(0, 4 - h // 3 + i % 2)
                away_goals = max(0, 3 - away // 3 + (i + 1) % 2)
                if i % 3 == 0:
                    home_goals = away_goals = i % 4
                period = "REG"
                if home_goals == away_goals:
                    period = "OT" if i % 2 == 0 else "SO"
                    if i % 5 != 0:
                        home_goals += 1
                    else:
                        away_goals += 1
                row.update(home_score=home_goals, away_score=away_goals,
                    winner_side="home" if home_goals > away_goals else "away",
                    last_period_type=period)
            elif sport == "cricket":
                row.update(home_score=None, away_score=None)
            rows.append(row)
    return rows


@pytest.mark.parametrize("sport", ["basketball", "ice_hockey", "cricket"])
def test_sport_specific_prediction_and_observed_prequential_evidence(sport):
    result = model.predict_prematch(sport, event(sport), history(sport), NOW)
    assert result.p_home is not None, result.missing
    assert 0 < result.p_home < 1
    assert result.p_away == pytest.approx(1 - result.p_home)
    assert result.training_games == 84
    assert result.home_games == result.away_games == 21
    assert 0 < result.evaluation.count <= model.MAX_EVALUATION_GAMES
    assert math.isfinite(result.evaluation.brier_score)
    assert math.isfinite(result.evaluation.baseline_brier_score)
    assert result.evidence_stage == "RESEARCH"
    assert result.risk_probability is None
    assert result.factors
    assert result.to_dict()["latest_result_observed_at"].endswith("+00:00")


def test_basketball_margin_changes_strength_even_with_identical_winners():
    rows = history()
    bigger_margins = deepcopy(rows)
    for row in bigger_margins:
        if row["home_team_id"] == "1" and row["winner_side"] == "home":
            row["home_score"] += 20
        elif row["away_team_id"] == "1" and row["winner_side"] == "away":
            row["away_score"] += 20
    original = model.predict_prematch("basketball", event(away_team_id="2"), rows, NOW)
    updated = model.predict_prematch("basketball", event(away_team_id="2"), bigger_margins, NOW)
    assert updated.p_home != pytest.approx(original.p_home)
    assert updated.input_hash != original.input_hash
    assert [r["winner_side"] for r in rows] == [r["winner_side"] for r in bigger_margins]


def test_hockey_derives_regulation_ties_and_keeps_ot_separate():
    target = event("ice_hockey")
    identity, missing = model._identity("ice_hockey", target, NOW)
    rows = history("ice_hockey")
    normal = model._normalise_history("ice_hockey", identity, rows, NOW)
    overtime = [m for m in normal if m.extra_time]
    assert overtime and all(m.home_score == m.away_score for m in overtime)
    result = model.predict_prematch("ice_hockey", target, rows, NOW)
    assert result.p_home_regulation is not None
    assert result.p_draw_regulation > 0
    assert result.p_home > result.p_home_regulation
    assert result.p_home <= result.p_home_regulation + result.p_draw_regulation


def test_hockey_strength_decomposition_uses_defence_and_not_only_attack():
    # Home has the better attack but a much worse defence. It must not be
    # described as the stronger side just because it scores plenty of goals.
    fitted = model._Fit("ice_hockey", ("a", "b"),
        (.5, .0, .8, -.2, 1.0, .1), overtime_home_rate=.5, overtime_games=20)
    identity = model._Identity("NHL", "NHL", "2", "target", NOW, "a", "b", False)
    values = model._strength_components(fitted, identity)
    assert values == pytest.approx({"attack": .5, "defence": -1.0, "venue": .1})
    p, rates = model._predict(fitted, "a", "b", False)
    assert sum(values.values()) == pytest.approx(math.log(
        rates["expected_home_goals"] / rates["expected_away_goals"]))
    assert p < .5


def test_basketball_strength_decomposition_keeps_neutral_venue_neutral():
    fitted = model._Fit("basketball", ("a", "b"), (3., 5., 4.), residual_scale=10.)
    identity = model._Identity("ESPN", "NBA", "", "target", NOW, "a", "b", True)
    values = model._strength_components(fitted, identity)
    assert values == {"strength": -2., "venue": 0.}
    _, prediction = model._predict(fitted, "a", "b", True)
    assert sum(values.values()) == prediction["expected_margin"]


@pytest.mark.parametrize("sport", ["basketball", "ice_hockey"])
def test_same_call_strength_factor_contains_actual_fitted_components(sport):
    captures = []
    prediction = model.predict_prematch(sport, event(sport), history(sport), NOW,
        original_capture=captures.append)
    original = captures[0]
    components = model._strength_components(original.fitted, original.identity)
    before = prediction.to_dict()
    assert model.team_strength_factor(original) == model._strength_factor(sport, components)
    assert prediction.to_dict() == before
    assert len(prediction.factors) == 2


@pytest.mark.parametrize("sport", ["basketball", "ice_hockey"])
def test_owning_adapter_binds_strength_fact_without_changing_base_prediction(sport):
    from riskobet_candidates import adapt_research_matchwinner
    captures = []
    target = event(sport, source_observed_at=NOW.isoformat())
    result = adapt_research_matchwinner(sport, target, history(sport), modeled_at=NOW,
        original_capture=captures.append)
    original = captures[0]
    forecast = result.snapshot.team_sport_forecast
    assert forecast.factors == (*original.prediction.factors, model.team_strength_factor(original))
    assert forecast.model_input_hash == original.input_hash
    assert forecast.p_home.hex() == original.prediction.p_home.hex()
    assert len(original.prediction.factors) == 2


def test_hockey_never_treats_unidentified_final_score_as_regulation_goals():
    rows = history("ice_hockey")
    for row in rows:
        row.pop("last_period_type")
    result = model.predict_prematch("ice_hockey", event("ice_hockey"), rows, NOW)
    assert result.p_home is None
    assert result.training_games == 0


def test_hockey_without_overtime_sample_has_no_full_match_probability():
    rows = [r for r in history("ice_hockey") if r["last_period_type"] == "REG"]
    result = model.predict_prematch("ice_hockey", event("ice_hockey"), rows, NOW)
    assert result.p_home is None
    assert result.missing


@pytest.mark.parametrize("sport", ["basketball", "ice_hockey", "cricket"])
def test_new_archive_does_not_invent_historical_observation_times(sport):
    result = model.predict_prematch(sport, event(sport), history(sport, newly_imported=True), NOW)
    assert result.p_home is not None, result.missing
    assert result.evaluation.count == 0
    assert result.evaluation.brier_score is None
    assert result.evaluation.baseline_brier_score is None


@pytest.mark.parametrize("sport", ["basketball", "ice_hockey", "cricket"])
def test_future_observations_target_results_and_foreign_competitions_do_not_leak(sport):
    rows = history(sport)
    original = model.predict_prematch(sport, event(sport), rows, NOW)
    pollution = []
    for field, value in [
        ("provider", "AnotherProvider"), ("competition", "AnotherLeague"),
        ("result_observed_at", NOW.isoformat()),
        ("result_observed_at", (NOW + timedelta(seconds=1)).isoformat()),
        ("provider_event_id", "future-match"),
    ]:
        row = deepcopy(rows[0])
        row[field] = value
        if field == "competition":
            row["provider_event_id"] = "another-competition-event"
        pollution.append(row)
    modified = model.predict_prematch(sport, event(sport), [*rows, *pollution], NOW)
    assert modified == original


def test_cricket_formats_and_explicit_winners_are_required():
    rows = history("cricket")
    assert model.predict_prematch("cricket", event("cricket", format="odi"), rows, NOW).p_home is None
    test_cricket = model.predict_prematch("cricket", event("cricket", format="test"), rows, NOW)
    assert test_cricket.p_home is None
    assert any("Remis" in note for note in test_cricket.missing)
    for row in rows:
        row.pop("winner_side")
        row.update(home_score=999, away_score=1)
    assert model.predict_prematch("cricket", event("cricket"), rows, NOW).p_home is None


def test_duplicates_and_alias_event_ids_do_not_inflate_evidence():
    rows = history()
    original = model.predict_prematch("basketball", event(), rows, NOW)
    aliases = deepcopy(rows)
    for row in aliases:
        row["provider_event_id"] += "-alias"
    modified = model.predict_prematch("basketball", event(), [*rows, *rows, *aliases], NOW)
    assert modified.training_games == original.training_games
    assert modified.p_home == original.p_home


def test_later_invalid_revision_does_not_resurrect_old_completed_score():
    rows = history()
    revisions = deepcopy(rows)
    for row in revisions:
        row["status"] = "cancelled"
        row["result_observed_at"] = (NOW - timedelta(seconds=5)).isoformat()
    result = model.predict_prematch("basketball", event(), [*rows, *revisions], NOW)
    assert result.training_games == 0
    assert result.p_home is None


@pytest.mark.parametrize("sport,field,value", [
    ("basketball", "competition", "Corrected league"),
    ("basketball", "sport", "cricket"),
    ("ice_hockey", "game_type", 3),
    ("cricket", "format", "odi"),
])
def test_latest_scope_correction_does_not_resurrect_old_in_scope_result(sport, field, value):
    rows = history(sport)
    revisions = deepcopy(rows)
    for row in revisions:
        row[field] = value
        row["result_observed_at"] = (NOW - timedelta(seconds=5)).isoformat()
    result = model.predict_prematch(sport, event(sport), [*rows, *revisions], NOW)
    assert result.training_games == 0
    assert result.p_home is None


def test_ambiguous_simultaneous_revision_is_not_double_counted_or_guessed():
    rows = history()
    contradictory = deepcopy(rows[0])
    contradictory["home_score"] += 10
    result = model.predict_prematch("basketball", event(), [*rows, contradictory], NOW)
    assert result.training_games == 83


def test_insufficient_or_disconnected_team_history_returns_no_coinflip():
    result = model.predict_prematch("basketball", event(), history()[:10], NOW)
    assert result.p_home is None and result.missing
    unknown = model.predict_prematch("basketball", event(home_team_id="999"), history(), NOW)
    assert unknown.p_home is None


def test_repeated_events_share_fitted_competition_model_and_evaluation():
    model._fit.cache_clear()
    model._evaluate.cache_clear()
    rows = history()
    model.predict_prematch("basketball", event(), rows, NOW)
    misses = model._fit.cache_info().misses
    model.predict_prematch("basketball", event(provider_event_id="other", home_team_id="2"), rows, NOW)
    assert model._fit.cache_info().misses == misses
    assert model._evaluate.cache_info().hits == 1


def test_event_identity_clock_and_finished_event_are_not_inferred():
    with pytest.raises(ValueError, match="timezone"):
        model.predict_prematch("basketball", event(), history(), NOW.replace(tzinfo=None))
    past = event(starts_at=(NOW - timedelta(seconds=1)).isoformat())
    assert model.predict_prematch("basketball", past, history(), NOW).p_home is None
    absent_competition = event(competition="")
    assert model.predict_prematch("basketball", absent_competition, history(), NOW).p_home is None


@pytest.mark.parametrize("status", [None, "", "cancelled", "postponed", "live", "completed", "unknown"])
def test_unconfirmed_or_non_prematch_status_never_receives_a_forecast(status):
    assert model.predict_prematch("basketball", event(status=status), history(), NOW).p_home is None


def test_nhl_schedule_preserves_actual_model_variant_and_venue_contract():
    from datetime import date
    from unittest.mock import Mock, patch
    from scanners.basketball_scanner import BasketballScanner

    scanner = BasketballScanner.__new__(BasketballScanner)
    scanner.nhl_schedule_base = "https://nhl.test/schedule"
    scanner.errors = {}
    response = Mock(status_code=200)
    response.json.return_value = {"gameWeek": [{"games": [{
        "id": 2030020001, "gameState": "FUT", "gameType": 2,
        "season": 20302031, "neutralSite": True,
        "startTimeUTC": "2030-01-03T23:00:00Z",
        "homeTeam": {"abbrev": "TOR", "id": 10},
        "awayTeam": {"abbrev": "MTL", "id": 8},
    }]}]}
    with patch("scanners.basketball_scanner.requests.get", return_value=response):
        rows = scanner.get_upcoming_nhl_games(date(2030, 1, 1), date(2030, 1, 7))
    assert len(rows) == 1
    assert rows[0]["game_type"] == 2
    assert rows[0]["season"] == 20302031
    assert rows[0]["neutral_site"] is True
    assert rows[0]["home_team_id"] == "10"
