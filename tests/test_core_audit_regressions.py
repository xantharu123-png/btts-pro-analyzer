"""Regression cases for the 2026-09-05 selection-quality audit."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

import challenge_15k
from challenge_15k import ChallengeDataProvider, refresh_discovered_candidates
from challenge_engine import (
    MARKET_SPECS,
    build_fixture_candidates,
    candidate_is_credible,
    candidate_is_wettfinder_release_credible,
    select_model_ticket,
    select_quoted_ticket,
    select_wettfinder_catalog,
)
from test_challenge_15k import candidate, confirmed_lineups, fixture
from test_challenge_market_eligibility import _credible_metric


NOW = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)


def _built(probability, *, profile="challenge", market="BTTS_YES", metric=None):
    target = fixture(1, NOW + timedelta(hours=1), 10, 11)
    model = {
        "projection_success": True,
        "freshness_days": 1.0,
        "active_lambdas": (1.4, 0.6),
        "venue_samples": (12, 12),
        "form_samples": (6, 6),
        "probabilities": {market: (probability,) * 3},
        "count_models": {},
        "xg_coverage": 0.0,
    }
    with patch("challenge_engine.fixture_market_probabilities", return_value=model):
        row = build_fixture_candidates(
            target, [], {market: metric or _credible_metric()},
            candidate_profile=profile,
        )[0]
    row.context = {
        "passed": True, "forecast_passed": True,
        "release_context_complete": True, "release_eligible": True,
        "blocked_reasons": [],
    }
    return row


@pytest.mark.parametrize("probability,market", [
    (0.30, "RESULT_AWAY"), (0.35, "RESULT_DRAW"),
    (0.57, "BTTS_YES"), (0.94, "AWAY_UNDER_2_5"),
])
def test_normal_profile_is_independent_of_15k_corridor(probability, market):
    legacy = _built(probability, market=market)
    normal = _built(probability, market=market, profile="wettfinder")
    assert legacy.blocked_reasons
    assert normal.blocked_reasons == []
    assert normal.probability == legacy.probability
    assert normal.conservative_probability == legacy.conservative_probability
    assert select_wettfinder_catalog([normal], require_release=True) == [normal]
    assert candidate_is_wettfinder_release_credible(normal)
    assert not candidate_is_credible(normal)
    assert select_model_ticket([normal], now=NOW) == ()
    assert select_quoted_ticket(
        [normal], {normal.candidate_id: max(1.5, 1.1 / normal.conservative_probability)},
        now=NOW, odds_min=1.01, odds_max=100.0,
    ) is None


def test_normal_profile_does_not_bypass_model_validation_or_context():
    metric = replace(_credible_metric(), passed=False)
    assert _built(0.57, profile="wettfinder", metric=metric).blocked_reasons
    row = _built(0.57, profile="wettfinder")
    row.context["release_context_complete"] = False
    assert not candidate_is_wettfinder_release_credible(row)


def test_exact_55_percent_is_inside_challenge_corridor_but_lower_values_are_not():
    boundary = _built(0.60)
    below = _built(0.599999)
    assert boundary.conservative_probability == 0.55
    assert boundary.blocked_reasons == []
    assert candidate_is_credible(boundary)
    assert "Konservative Wahrscheinlichkeit unter 55 %" in below.blocked_reasons
    assert not candidate_is_credible(below)


@pytest.mark.parametrize("profile", [None, True, "", "riskobet", []])
def test_unknown_candidate_profile_is_rejected(profile):
    with pytest.raises(ValueError, match="candidate_profile"):
        build_fixture_candidates({}, [], {}, candidate_profile=profile)


def _history(start, count, *, days_ago):
    return [
        fixture(start + index, NOW - timedelta(days=days_ago + index), 10, 11, 2, 1)
        for index in range(count)
    ]


def test_completed_history_keeps_previous_season_across_220_boundary():
    prior = _history(1000, 380, days_ago=230)
    current = _history(2000, 220, days_ago=1)
    target = [fixture(9999, NOW + timedelta(hours=3), 10, 11)]
    provider = ChallengeDataProvider("test", None)
    provider.recent_ft_results = Mock(return_value=[])
    provider._football_get = Mock(return_value=[])
    results = []
    for count in (219, 220, 221):
        season_rows = current[:count] if count <= 220 else [
            *current, fixture(2221, NOW - timedelta(hours=3), 20, 21, 1, 0),
        ]
        with patch("challenge_15k.fetch_stat_history", side_effect=[season_rows, prior]):
            results.append(provider.completed_history(39, 2026, target))
    assert [len(rows) for rows in results] == [599, 600, 601]
    assert {row["fixture"]["id"] for row in results[0]} <= {
        row["fixture"]["id"] for row in results[1]
    }


def test_nations_league_uses_recent_cross_competition_team_results_not_2022():
    now = datetime.now(timezone.utc)
    target = [fixture(9999, now + timedelta(hours=3), 10, 11, league_id=5)]
    provider = ChallengeDataProvider("test", None)
    qualification = fixture(2601, now - timedelta(days=21), 10, 100, 2, 1, league_id=32)
    qualification["league"].update(
        name="World Cup - Qualification Europe", country="World",
    )
    friendly = fixture(2602, now - timedelta(days=10), 101, 11, 0, 1, league_id=10)
    friendly["league"].update(name="Friendlies", country="World")
    shared = fixture(2603, now - timedelta(days=7), 10, 11, 1, 1, league_id=5)
    shared["league"].update(name="UEFA Nations League", country="World")
    old = fixture(2201, now - timedelta(days=1400), 10, 11, 3, 0, league_id=5)
    old["league"].update(name="UEFA Nations League", country="World")
    club = fixture(2604, now - timedelta(days=3), 10, 200, 5, 0, league_id=4)
    club["league"].update(name="Friendlies Clubs", country="World")
    youth = fixture(2605, now - timedelta(days=2), 10, 201, 4, 0, league_id=10)
    youth["league"].update(name="Friendlies", country="World")
    youth["teams"]["away"]["name"] = "Test U21"
    calls = []

    def get_history(endpoint, params, _label, **_kwargs):
        assert endpoint == "fixtures" and params["status"] == "FT"
        calls.append(params)
        return {
            5: [shared, old],
            32: [qualification],
            10: [friendly, club, youth],
        }.get(params["league"], [])

    provider._football_get = Mock(side_effect=get_history)
    with patch("challenge_15k.fetch_stat_history") as csv_history:
        result = provider.completed_history(5, 2026, target)

    csv_history.assert_not_called()
    assert {row["fixture"]["id"] for row in result} == {2601, 2602, 2603}
    assert next(row for row in result if row["fixture"]["id"] == 2602)[
        "challenge_venue_unknown"
    ] is True
    assert {call["league"] for call in calls} == set(
        challenge_15k.NATIONAL_HISTORY_LEAGUES
    )
    assert all("team" not in call for call in calls)
    assert len(calls) == len(challenge_15k.NATIONAL_HISTORY_LEAGUES) * len(
        range((now - timedelta(days=730)).year, now.year + 1)
    )
    assert {call["season"] for call in calls} == set(
        range((now - timedelta(days=730)).year, now.year + 1)
    )
    assert all(call["from"] > "2022-12-31" for call in calls)


def test_neutral_international_results_count_as_form_not_home_advantage():
    from challenge_engine import _league_goal_means, _team_observations

    now = datetime.now(timezone.utc)
    neutral = fixture(2601, now - timedelta(days=3), 10, 11, 2, 0, league_id=10)
    neutral["challenge_neutral_venue"] = True
    home = fixture(2602, now - timedelta(days=2), 10, 12, 1, 0, league_id=5)
    assert len(_team_observations([neutral, home], 10, now, venue=None, limit=6)) == 2
    assert len(_team_observations([neutral, home], 10, now, venue="home", limit=6)) == 1
    assert _league_goal_means([neutral] * 24, now) is None


def test_nations_league_history_fails_closed_if_a_team_fetch_fails():
    now = datetime.now(timezone.utc)
    target = [fixture(9999, now + timedelta(hours=3), 10, 11, league_id=5)]
    provider = ChallengeDataProvider("test", None)
    provider._football_get = Mock(side_effect=[[], None])
    assert provider.completed_history(5, 2026, target) is None


def test_nations_league_bulk_history_excludes_unrelated_non_uefa_games():
    now = datetime.now(timezone.utc)
    target = fixture(9999, now + timedelta(hours=3), 10, 11, league_id=5)
    nations = fixture(2601, now - timedelta(days=120), 10, 11, 1, 0, league_id=5)
    nations["league"].update(name="UEFA Nations League", country="World")
    european_qualifier = fixture(2602, now - timedelta(days=90), 12, 13, 2, 1, league_id=32)
    european_qualifier["league"].update(name="World Cup - Qualification Europe", country="World")
    friendly = fixture(2603, now - timedelta(days=10), 10, 101, 2, 0, league_id=10)
    friendly["league"].update(name="Friendlies", country="World")
    unrelated_friendly = fixture(2604, now - timedelta(days=8), 201, 202, 1, 1, league_id=10)
    unrelated_friendly["league"].update(name="Friendlies", country="World")
    provider = ChallengeDataProvider("test", None)
    provider._football_get = Mock(side_effect=lambda _path, params, _label, **_kwargs: {
        5: [nations], 32: [european_qualifier], 10: [friendly, unrelated_friendly],
    }.get(params["league"], []))
    rows = provider.completed_history(5, 2026, [target])
    assert {row["fixture"]["id"] for row in rows} == {2601, 2603}


def test_recent_national_friendly_changes_form_but_not_goal_prior():
    from challenge_engine import _league_goal_means, fixture_market_probabilities

    now = datetime.now(timezone.utc)
    target = fixture(9999, now + timedelta(hours=3), 10, 11, league_id=5)
    history = [
        fixture(
            3000 + index, now - timedelta(days=400 - index * 15),
            10, 100 + index, 1, 0, league_id=32,
        )
        for index in range(12)
    ] + [
        fixture(
            4000 + index, now - timedelta(days=399 - index * 15),
            200 + index, 11, 1, 1, league_id=32,
        )
        for index in range(12)
    ]
    friendly = fixture(5000, now - timedelta(days=2), 10, 300, 5, 0, league_id=10)
    friendly["challenge_venue_unknown"] = True
    prior_before = _league_goal_means(history, now)
    prior_after = _league_goal_means([*history, friendly], now)
    assert prior_after == prior_before
    baseline = fixture_market_probabilities(target, history)
    updated = fixture_market_probabilities(target, [*history, friendly])
    assert baseline is not None and updated is not None
    assert updated["active_lambdas"][0] > baseline["active_lambdas"][0]
    assert updated["probabilities"]["RESULT_HOME"][0] > baseline["probabilities"]["RESULT_HOME"][0]


def test_national_model_uses_real_overall_samples_without_invented_venue_games():
    from challenge_engine import _fixture_model, fixture_market_probabilities

    now = datetime.now(timezone.utc)
    history = [
        fixture(6000 + index, now - timedelta(days=120 - index),
                10, 100 + index, 2, 1, league_id=10)
        for index in range(12)
    ] + [
        fixture(7000 + index, now - timedelta(days=119 - index),
                200 + index, 11, 1, 1, league_id=10)
        for index in range(12)
    ]
    for row in history:
        row["challenge_venue_unknown"] = True
        row["challenge_senior_national_team"] = True
    target = fixture(9999, now + timedelta(hours=3), 10, 11, league_id=5)
    model = _fixture_model(target, history)
    assert model is not None
    assert model["national_samples"] == (12, 12)
    assert model["venue_samples"] == (0, 0)
    assert model["form_samples"] == (6, 6)
    future = fixture(9998, now + timedelta(hours=4), 10, 11, 9, 0, league_id=5)
    future["challenge_senior_national_team"] = True
    assert _fixture_model(target, [*history, future])["active_lambdas"] == model["active_lambdas"]
    captures = []
    probabilities = fixture_market_probabilities(
        target, history, original_capture=captures.append,
    )
    assert probabilities is not None and len(captures) == 1
    original = captures[0].to_dict()
    assert original["goal_model"]["venue_samples"] == [0, 0]
    assert original["goal_model"]["national_samples"] == [12, 12]
    assert all(row["challenge_senior_national_team"] is True
               for row in original["league_history"])
    assert all(row["challenge_venue_unknown"] is True
               for row in original["league_history"])
    assert original["goal_provenance"]["reference_weights"]["kind"] == "unavailable"


def test_national_neutral_target_removes_host_effect_and_is_walk_forward_target():
    from challenge_engine import _fixture_model, _walk_forward_market_records

    now = datetime.now(timezone.utc)
    history = [
        fixture(8000 + index, now - timedelta(days=120 - index),
                10, 100 + index, 2, 1, league_id=5)
        for index in range(12)
    ] + [
        fixture(9000 + index, now - timedelta(days=119 - index),
                200 + index, 11, 2, 1, league_id=5)
        for index in range(12)
    ]
    for row in history:
        row["challenge_senior_national_team"] = True
    hosted = fixture(9999, now + timedelta(hours=3), 10, 11, league_id=5)
    neutral = fixture(9997, now + timedelta(hours=3), 10, 11, 1, 1, league_id=10)
    neutral["challenge_neutral_venue"] = True
    neutral["challenge_senior_national_team"] = True
    host_model = _fixture_model(hosted, history)
    neutral_model = _fixture_model(neutral, history)
    assert host_model is not None and neutral_model is not None
    assert host_model["active_lambdas"][0] > neutral_model["active_lambdas"][0]
    assert host_model["active_lambdas"][1] < neutral_model["active_lambdas"][1]
    before = _walk_forward_market_records(history)
    after = _walk_forward_market_records([*history, neutral])
    assert len(after["RESULT_HOME"]["outcomes"]) == len(before["RESULT_HOME"]["outcomes"]) + 1


def test_nations_league_scan_uses_pooled_national_scope_without_context_release():
    from test_challenge_market_eligibility import _credible_metric

    now = datetime.now(timezone.utc)
    kickoff = now + timedelta(hours=3)
    target = fixture(9999, kickoff, 10, 11, league_id=5)
    history = [
        fixture(
            3000 + index, now - timedelta(days=245 - index * 20),
            10, 100 + index, 1 + index % 2, 0, league_id=32,
        )
        for index in range(12)
    ] + [
        fixture(
            4000 + index, now - timedelta(days=244 - index * 20),
            200 + index, 11, 1, index % 2, league_id=32,
        )
        for index in range(12)
    ]
    for row in history:
        row["challenge_senior_national_team"] = True
    provider = Mock()
    provider.errors = []
    provider.upcoming_fixtures.return_value = [target]
    provider.completed_history.return_value = history
    provider.coverage.return_value = {"injuries": False, "lineups": False}
    provider.injuries_by_fixture.return_value = {9999: []}
    provider.details_by_fixture.return_value = {9999: target}
    provider.h2h.return_value = []
    provider.weather.return_value = None
    with (
        patch(
            "challenge_15k._cached_market_validation",
            return_value={spec.key: _credible_metric() for spec in MARKET_SPECS},
        ),
        patch("challenge_15k._cached_market_calibration", return_value={}),
    ):
        snapshot = challenge_15k.scan_daily_challenge(
            provider, [5], kickoff.astimezone(challenge_15k.CHALLENGE_TIMEZONE).date(),
            8, candidate_profile="wettfinder",
        )

    assert snapshot["fixtures_found"] == snapshot["fixtures_modeled"] == 1
    assert snapshot["base_shortlist"]
    assert all(
        row.model_scope == challenge_15k.MODEL_SCOPE_SENIOR_NATIONAL
        for row in snapshot["base_shortlist"]
    )
    assert snapshot["approved_candidates"] == 0
    for row in history:
        del row["challenge_senior_national_team"]
    with (
        patch(
            "challenge_15k._cached_market_validation",
            return_value={spec.key: _credible_metric() for spec in MARKET_SPECS},
        ),
        patch("challenge_15k._cached_market_calibration", return_value={}),
    ):
        unmarked = challenge_15k.scan_daily_challenge(
            provider, [5], kickoff.astimezone(challenge_15k.CHALLENGE_TIMEZONE).date(),
            8, candidate_profile="wettfinder",
        )
    assert unmarked["fixtures_modeled"] == 1
    assert unmarked["base_candidates"] == 0


def test_completed_history_is_causal_unique_and_bounded():
    before = NOW
    rows = _history(1000, challenge_15k.MAX_HISTORY_GAMES + 5, days_ago=1)
    duplicate = deepcopy(rows[0])
    duplicate["fixture"]["id"] = 99999
    future = fixture(99998, before + timedelta(hours=1), 10, 11, 5, 0)
    live = fixture(99997, before - timedelta(hours=1), 10, 11, 1, 0)
    live["fixture"]["status"] = {"short": "1H"}
    invalid = fixture(99996, before - timedelta(hours=2), 10, 11, True, 0)
    result = challenge_15k._bounded_completed_history(
        [*rows, rows[2], duplicate, future, live, invalid], before=before,
    )
    assert len(result) == challenge_15k.MAX_HISTORY_GAMES
    assert result[-1]["fixture"]["id"] == 99999
    assert all(challenge_15k._fixture_kickoff(row) < before for row in result)
    assert not {99998, 99997, 99996} & {row["fixture"]["id"] for row in result}


def test_normal_fixture_twenty_one_ninth_market_survives_background_refresh():
    kickoff = NOW + timedelta(minutes=80)
    first_context_batch = [
        candidate(f"{fixture_id}:BTTS", fixture_id, 0.70, kickoff=kickoff)
        for fixture_id in range(1, 21)
    ]
    fixture_twenty_one = [
        replace(
            candidate(
                f"21:{spec.key}",
                21,
                0.70 - index / 1000,
                kickoff=kickoff,
            ),
            market_key=spec.key,
            market=spec.market,
            selection=spec.selection,
        )
        for index, spec in enumerate(MARKET_SPECS[:9])
    ]

    background_pool = challenge_15k._discovery_candidate_pool(
        [*first_context_batch, *fixture_twenty_one],
        list(range(1, 22)),
        candidate_profile="wettfinder",
    )
    persisted_fixture = [
        row for row in background_pool if row.fixture_id == 21
    ]
    ninth_candidate_id = fixture_twenty_one[8].candidate_id

    detail = fixture(21, kickoff, 210, 211)
    detail["fixture"]["status"] = {"short": "NS"}
    detail["lineups"] = confirmed_lineups()
    provider = Mock()
    provider.errors = []
    provider.details_by_fixture.return_value = {21: detail}
    provider.injuries_by_fixture.return_value = {21: []}
    provider.coverage.return_value = {"injuries": True, "lineups": True}
    provider.h2h.return_value = [
        fixture(200 + index, NOW - timedelta(days=30 + index), 210, 211, 1, 1)
        for index in range(3)
    ]
    provider.weather.return_value = {
        "status": "ok", "temperature_c": 16, "wind_mps": 2,
        "rain_3h_mm": 0, "snow_3h_mm": 0,
    }

    refreshed = refresh_discovered_candidates(
        provider,
        persisted_fixture,
        NOW.date(),
        now=NOW,
    )

    assert len(persisted_fixture) == 9
    assert ninth_candidate_id in {
        row.candidate_id for row in refreshed["wettfinder_candidates"]
    }
    provider.h2h.assert_called_once_with(210, 211)
    provider.weather.assert_called_once_with(detail)


def _refresh_provider(detail):
    provider = Mock()
    provider.errors = []
    provider.details_by_fixture.return_value = {1: detail}
    provider.injuries_by_fixture.return_value = {1: []}
    provider.coverage.return_value = {"injuries": True, "lineups": True}
    provider.h2h.return_value = [
        fixture(100 + i, NOW - timedelta(days=30 + i), 10, 11, 1, 1)
        for i in range(3)
    ]
    provider.weather.return_value = {
        "status": "ok", "temperature_c": 16, "wind_mps": 2,
        "rain_3h_mm": 0, "snow_3h_mm": 0,
    }
    return provider


def _detail():
    detail = fixture(1, NOW + timedelta(minutes=80), 10, 11)
    detail["fixture"]["status"] = {"short": "NS"}
    detail["lineups"] = confirmed_lineups()
    return detail


def test_refresh_reconciles_new_kickoff_without_mutating_frozen_source():
    row = candidate("1:BTTS", 1, 0.70, kickoff=NOW + timedelta(minutes=50))
    detail = _detail()
    result = refresh_discovered_candidates(
        _refresh_provider(detail), [row], NOW.date(), now=NOW,
    )
    current = result["wettfinder_candidates"][0]
    assert current.kickoff == detail["fixture"]["date"]
    assert row.kickoff == (NOW + timedelta(minutes=50)).isoformat()
    assert candidate_is_credible(current)
    assert result["invalidated_fixture_ids"] == []


@pytest.mark.parametrize("case", [
    "missing", "unknown_status", "CANC", "PST", "FT", "1H",
    "tomorrow", "invalid_date", "past", "other_fixture", "other_teams",
])
def test_refresh_never_releases_an_invalid_or_no_longer_current_event(case):
    row = candidate("1:BTTS", 1, 0.70, kickoff=NOW + timedelta(minutes=50))
    detail = _detail()
    if case == "missing":
        detail = None
    elif case == "unknown_status":
        detail["fixture"].pop("status")
    elif case in ("CANC", "PST", "FT", "1H"):
        detail["fixture"]["status"]["short"] = case
    elif case == "tomorrow":
        detail["fixture"]["date"] = (NOW + timedelta(days=1)).isoformat()
    elif case == "invalid_date":
        detail["fixture"]["date"] = "invalid"
    elif case == "past":
        detail["fixture"]["date"] = (NOW - timedelta(minutes=1)).isoformat()
    elif case == "other_fixture":
        detail["fixture"]["id"] = 2
    elif case == "other_teams":
        detail["teams"]["away"]["id"] = 12
    result = refresh_discovered_candidates(
        _refresh_provider(detail), [row], NOW.date(), now=NOW,
    )
    assert result["wettfinder_candidates"] == []
    assert result["shortlist"] == []
    assert result["invalidated_fixture_ids"] == [1]
    assert result["riskobet_source_candidates"] == []
    assert not result["candidates"][0].context["release_eligible"]
    if case == "tomorrow":
        assert result["candidates"][0].kickoff == detail["fixture"]["date"]
def test_prediction_version_does_not_change_authenticated_ticket_contract():
    from challenge_engine import CHALLENGE_MODEL_CONTRACT_SIGNATURE, CHALLENGE_PREDICTION_VERSION
    from challenge_15k import CHALLENGE_MODEL_SIGNATURE, CHALLENGE_SNAPSHOT_VERSION

    assert CHALLENGE_MODEL_CONTRACT_SIGNATURE == "challenge-engine:hac-fdr-executable-frechet-v11"
    assert CHALLENGE_MODEL_SIGNATURE == CHALLENGE_MODEL_CONTRACT_SIGNATURE
    assert CHALLENGE_PREDICTION_VERSION != CHALLENGE_MODEL_CONTRACT_SIGNATURE
    assert CHALLENGE_SNAPSHOT_VERSION >= 21
