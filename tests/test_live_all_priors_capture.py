"""Offline regression: fixture-level goal priors belong to the model, not its market shortlist."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

import challenge_15k as scan
import challenge_engine as engine
from tests.test_challenge_15k import candidate, fixture


def run_scan(monkeypatch, matches, *, league=39):
    kickoff = datetime.fromisoformat(matches[0]["fixture"]["date"])
    history = [fixture(2000 + i, kickoff - timedelta(days=i + 2), 10 if i % 2 else 11,
                       11 if i % 2 else 10, 1 + i % 3, i % 2, league_id=league) for i in range(60)]
    provider = Mock(spec=scan.ChallengeDataProvider)
    provider.errors = []
    provider.upcoming_fixtures.return_value = matches
    provider.completed_history.return_value = history
    provider.coverage.return_value = {}
    provider.injuries_by_fixture.return_value = {}
    provider.details_by_fixture.return_value = {}
    provider.h2h.return_value = []
    monkeypatch.setattr(scan, "_cached_market_validation", lambda *args: {})
    monkeypatch.setattr(scan, "_cached_market_calibration", lambda *args: {})
    monkeypatch.setattr(scan, "annotate_history_xg", lambda *args, **kwargs: {"coverage": 1})
    snapshot = scan.scan_daily_challenge(provider, [league], kickoff.astimezone(scan.CHALLENGE_TIMEZONE).date(),
        100, market_kinds={"corner_total"}, candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER)
    return snapshot, provider


def test_all_22_modeled_pairs_survive_empty_market_pool_once_without_extra_requests(monkeypatch):
    before = datetime.now(timezone.utc)
    kickoff = (before + timedelta(days=1)).replace(microsecond=0)
    matches = [fixture(i, kickoff, 10, 11) for i in range(1, 23)]
    actual_pairs = {}
    compute = engine.fixture_market_probabilities

    def measured(match, *args, **kwargs):
        fid = match["fixture"]["id"]
        assert fid not in actual_pairs, "the daily scan must not recompute a match to obtain its prior"
        model = compute(match, *args, **kwargs)
        actual_pairs[fid] = model["active_lambdas"]
        return model

    monkeypatch.setattr(scan, "fixture_market_probabilities", measured)
    monkeypatch.setattr(engine, "fixture_market_probabilities", measured)
    snapshot, provider = run_scan(monkeypatch, matches)
    after = datetime.now(timezone.utc)
    assert snapshot["fixtures_found"] == 22
    assert snapshot["fixtures_modeled"] == snapshot["context_fixtures"] == 0  # selected market absent
    assert set(actual_pairs) == set(range(1, 23))
    # Three league calls plus the existing bounded RisikoBet batch, never a new call for omitted fixtures.
    assert [call[0] for call in provider.method_calls] == [
        "upcoming_fixtures", "completed_history", "coverage", "injuries_by_fixture", "details_by_fixture",
        *(["h2h"] * 20),
    ]
    assert "live_goal_priors" in snapshot
    packet = snapshot["live_goal_priors"]
    assert packet["version"] == 1
    assert len(packet["rows"]) == 22
    # The published goal basis is a three-decimal contract: even with no candidate,
    # the live model must receive the same pair an existing Wettfinder card would carry.
    assert any(mean != round(mean, 3) for mean in actual_pairs[1])
    assert (packet["rows"][0]["expected_home_goals"], packet["rows"][0]["expected_away_goals"]) == (1.552, 1.153)
    for row, fid in zip(packet["rows"], range(1, 23), strict=True):
        assert before <= datetime.fromisoformat(row["modeled_at"]) <= after < kickoff
        assert row == {
            "fixture_id": fid, "league_id": 39, "home_id": 10, "away_id": 11,
            "home_team": "Team 10", "away_team": "Team 11", "scheduled_start": kickoff.isoformat(),
            "modeled_at": row["modeled_at"], "model_version": engine.FORM_STRENGTH_PREDICTION_VERSION,
            "model_scope": "same_competition",
            "expected_home_goals": round(actual_pairs[fid][0], 3),
            "expected_away_goals": round(actual_pairs[fid][1], 3),
        }


def test_successful_goal_model_survives_when_candidate_builder_emits_no_market(monkeypatch):
    kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    match = fixture(77, kickoff, 10, 11)
    compute = engine.fixture_market_probabilities
    def no_market(*args, **kwargs):
        model = compute(*args, **kwargs)
        return {**model, "probabilities": {}}

    monkeypatch.setattr(engine, "fixture_market_probabilities", no_market)
    snapshot, provider = run_scan(monkeypatch, [match])
    assert snapshot["football_recent_results"] == {}
    assert snapshot["base_candidates"] == 0
    assert [r["fixture_id"] for r in snapshot["live_goal_priors"]["rows"]] == [77]
    assert [call[0] for call in provider.method_calls] == ["upcoming_fixtures", "completed_history", "coverage"]


def test_bounded_refresh_does_not_issue_replacement_priors(monkeypatch):
    from football_model_refresh import refresh_fixture_models
    now = datetime.now(timezone.utc)
    kickoff = (now + timedelta(days=1)).replace(microsecond=0)
    match = fixture(1, kickoff, 10, 11)
    previous = candidate("1:BTTS_YES", 1, .60, kickoff=kickoff)
    provider = Mock(spec=scan.ChallengeDataProvider)
    provider.errors = []
    provider.details_by_fixture.return_value = {1: match}
    provider.completed_history.return_value = [
        fixture(1000 + i, now - timedelta(days=i + 1), 10 if i % 2 else 11,
                11 if i % 2 else 10, 1 + i % 3, i % 2) for i in range(60)
    ]
    provider.coverage.return_value = {}
    provider.injuries_by_fixture.return_value = {}
    provider.h2h.return_value = []
    provider.weather.return_value = None
    monkeypatch.setattr(scan, "_cached_market_validation", lambda *args: {})
    monkeypatch.setattr(scan, "_cached_market_calibration", lambda *args: {})
    monkeypatch.setattr(scan, "annotate_history_xg", lambda *args, **kwargs: {"coverage": 1})
    snapshot = refresh_fixture_models(provider, [previous], kickoff.astimezone(scan.CHALLENGE_TIMEZONE).date(), now=now)
    assert snapshot["model_refresh"]["fixture_ids"] == [1]
    assert "live_goal_priors" not in snapshot


@pytest.mark.parametrize("damage", ["no_status", "already_live", "past", "timestamp_conflict",
    "season_conflict", "no_model", "non_production_basis", "failed_goal_projection", "national_flag",
    "conflicting_duplicate", "already_scored", "wrong_modeled_basis", "continental"])
def test_unproven_or_late_models_never_become_live_priors(monkeypatch, damage):
    kickoff = (datetime.now(timezone.utc) + timedelta(days=-1 if damage == "past" else 1)).replace(microsecond=0)
    league = 3 if damage == "continental" else 39
    match = fixture(15, kickoff, 10, 11, league_id=league)
    matches = [match]
    if damage == "no_status":
        del match["fixture"]["status"]
    elif damage == "already_live":
        match["fixture"]["status"]["short"] = "1H"
    elif damage == "timestamp_conflict":
        match["fixture"]["timestamp"] = int(kickoff.timestamp()) - 1
    elif damage == "season_conflict":
        match["league"]["season"] = 1990
    elif damage == "no_model":
        match["teams"]["home"]["id"] = 999
    elif damage == "non_production_basis":
        monkeypatch.setattr(scan, "PRODUCTION_GOAL_MODEL", engine.GOAL_MODEL_LEGACY)
    elif damage == "failed_goal_projection":
        from football_joint_calibration import calibrate_joint_distribution
        def failed(*args, **kwargs):
            matrix, diag = calibrate_joint_distribution(*args, **kwargs)
            return matrix, {**diag, "success": False, "status": "raw-fallback"}
        monkeypatch.setattr("football_joint_calibration.calibrate_joint_distribution", failed)
    elif damage == "national_flag":
        match["challenge_senior_national_team"] = True
    elif damage == "conflicting_duplicate":
        matches.append(fixture(15, kickoff, 11, 10))
    elif damage == "already_scored":
        match["goals"]["home"] = 1
    elif damage == "wrong_modeled_basis":
        compute = engine.fixture_market_probabilities
        def wrong_basis(*args, **kwargs):
            return {**compute(*args, **kwargs), "goal_model": engine.GOAL_MODEL_LEGACY}
        monkeypatch.setattr(engine, "fixture_market_probabilities", wrong_basis)
    snapshot, _ = run_scan(monkeypatch, matches, league=league)
    assert snapshot.get("live_goal_priors") == {"version": 1, "rows": []}
