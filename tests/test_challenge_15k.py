from contextlib import closing
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest.mock import Mock, patch

from challenge_15k import ChallengeDataProvider, scan_daily_challenge
from challenge_engine import (
    ChallengeCandidate,
    MARKET_BY_KEY,
    MARKET_SPECS,
    ValidationMetrics,
    apply_candidate_context,
    build_fixture_candidates,
    candidate_is_credible,
    consecutive_wins_to_target,
    kelly_reference_stake,
    market_outcome,
    score_matrix,
    select_model_ticket,
    select_quoted_ticket,
    select_shortlist,
    ticket_stake,
    validate_league_markets,
)
from challenge_store import ChallengeLedger
from football_data_history import parse_history_csv


def fixture(
    fixture_id,
    played_at,
    home_id,
    away_id,
    home_goals=None,
    away_goals=None,
    league_id=39,
    stats=None,
):
    return {
        "fixture": {
            "id": fixture_id,
            "date": played_at.astimezone(timezone.utc).isoformat(),
            "venue": {"city": "London"},
            "referee": "R Test",
        },
        "league": {"id": league_id, "name": "Test League", "country": "England"},
        "teams": {
            "home": {"id": home_id, "name": f"Team {home_id}"},
            "away": {"id": away_id, "name": f"Team {away_id}"},
        },
        "goals": {"home": home_goals, "away": away_goals},
        "challenge_stats": stats or {},
    }


def candidate(candidate_id, fixture_id, probability, *, kickoff=None, eligible=True):
    validation = ValidationMetrics(
        300, 0.15, 0.2, 0.25, 0.04, True,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.06,
    )
    item = ChallengeCandidate(
        candidate_id=candidate_id,
        fixture_id=fixture_id,
        league_id=39,
        league_name="Test League",
        kickoff=(kickoff or (datetime.now(timezone.utc) + timedelta(days=1))).isoformat(),
        home_team_id=fixture_id * 10,
        away_team_id=fixture_id * 10 + 1,
        home_team=f"Home {fixture_id}",
        away_team=f"Away {fixture_id}",
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
        probability=probability + 0.03,
        conservative_probability=probability,
        probability_haircut_pp=3.0,
        model_price=1.0 / probability,
        evidence_score=90.0,
        model_spread_pp=2.0,
        expected_home_goals=1.5,
        expected_away_goals=1.2,
        venue_samples=(10, 10),
        form_samples=(6, 6),
        validation=validation,
    )
    item.context = {"passed": eligible, "blocked_reasons": [] if eligible else ["blocked"]}
    return item


def credible_validation():
    return ValidationMetrics(
        300,
        0.15,
        0.20,
        0.25,
        0.04,
        True,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.06,
    )


def confirmed_lineups(home_team_id=10, away_team_id=11):
    return [
        {
            "team": {"id": team_id},
            "startXI": [
                {"player": {"id": side * 100 + index}}
                for index in range(1, 12)
            ],
        }
        for side, team_id in ((1, home_team_id), (2, away_team_id))
    ]


class ChallengeProbabilityTests(unittest.TestCase):
    def test_score_matrix_is_normalized(self):
        matrix = score_matrix(1.4, 1.1)

        self.assertAlmostEqual(sum(matrix.values()), 1.0, places=12)
        self.assertGreater(matrix[(1, 1)], 0)

    def test_score_matrix_preserves_high_rate_mean_and_rejects_short_cutoff(self):
        matrix = score_matrix(8.0, 8.0)
        home_mean = sum(home * value for (home, _), value in matrix.items())

        self.assertAlmostEqual(home_mean, 8.0, places=4)
        with self.assertRaises(ValueError):
            score_matrix(4.0, 4.0, max_goals=5)

    def test_supported_markets_settle_exactly(self):
        self.assertTrue(market_outcome(MARKET_BY_KEY["BTTS_YES"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["TOTAL_UNDER_3_5"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["HOME_RANGE_2_4"], 2, 0))
        self.assertFalse(market_outcome(MARKET_BY_KEY["DC_X2"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["CORNERS_OVER_5_5"], 4, 3))
        self.assertTrue(market_outcome(MARKET_BY_KEY["HOME_YELLOW_OVER_1_5"], 2, 1))

        with self.assertRaises(ValueError):
            market_outcome(MARKET_BY_KEY["BTTS_YES"], True, 1)

    def test_fixture_candidates_are_created_without_any_odds_input(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        history = []
        fixture_id = 1
        for index in range(10):
            history.append(fixture(fixture_id, start + timedelta(days=index * 4), 1, 3, 2, 1))
            fixture_id += 1
            history.append(fixture(fixture_id, start + timedelta(days=index * 4 + 1), 4, 2, 1, 1))
            fixture_id += 1
            history.append(fixture(fixture_id, start + timedelta(days=index * 4 + 2), 5, 6, 1, 0))
            fixture_id += 1
            history.append(fixture(fixture_id, start + timedelta(days=index * 4 + 3), 6, 5, 0, 1))
            fixture_id += 1
        target = fixture(999, start + timedelta(days=45), 1, 2)
        validation = {
            spec.key: credible_validation()
            for spec in MARKET_SPECS
        }

        candidates = build_fixture_candidates(target, history, validation)

        self.assertTrue(candidates)
        self.assertTrue(any(item.base_eligible for item in candidates))
        self.assertFalse(any(hasattr(item, "bookmaker_odds") for item in candidates))

    def test_expanding_window_validation_produces_only_past_based_observations(self):
        start = datetime(2025, 8, 1, tzinfo=timezone.utc)
        teams = list(range(1, 9))
        history = []
        fixture_id = 1
        for cycle in range(12):
            for index, home_id in enumerate(teams):
                away_id = teams[(index + cycle + 1) % len(teams)]
                if away_id == home_id:
                    away_id = teams[(index + 2) % len(teams)]
                history.append(
                    fixture(
                        fixture_id,
                        start + timedelta(days=fixture_id),
                        home_id,
                        away_id,
                        (home_id + cycle) % 4,
                        (away_id + cycle) % 3,
                        stats={
                            "corners_home": 3 + (home_id + cycle) % 5,
                            "corners_away": 2 + (away_id + cycle) % 5,
                            "yellow_cards_home": 1 + (home_id + cycle) % 3,
                            "yellow_cards_away": 1 + (away_id + cycle) % 3,
                        },
                    )
                )
                fixture_id += 1

        metrics = validate_league_markets(history)

        self.assertEqual(set(metrics), {spec.key for spec in MARKET_SPECS})
        self.assertGreater(metrics["BTTS_YES"].observations, 0)
        self.assertLess(metrics["BTTS_YES"].observations, len(history))
        self.assertGreater(metrics["CORNERS_OVER_5_5"].observations, 0)

    def test_walk_forward_validation_hides_all_same_day_results(self):
        start = datetime(2026, 4, 1, 10, tzinfo=timezone.utc)
        history = [
            fixture(1, start, 1, 2, 1, 0),
            fixture(2, start + timedelta(hours=8), 3, 4, 0, 1),
            fixture(3, start + timedelta(days=1), 1, 3, 1, 1),
        ]
        prior_sizes = []

        def fake_probabilities(_fixture, prior):
            prior_sizes.append(len(prior))
            return {
                "probabilities": {
                    spec.key: (0.5, 0.5, 0.5)
                    for spec in MARKET_SPECS
                }
            }

        with patch(
            "challenge_engine.fixture_market_probabilities",
            side_effect=fake_probabilities,
        ):
            validate_league_markets(history)

        self.assertEqual(prior_sizes, [0, 0, 2])

    def test_corner_candidates_require_their_own_validated_history(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        history = []
        fixture_id = 1
        for index in range(10):
            stats_a = {
                "corners_home": 5 + index % 3,
                "corners_away": 3 + index % 2,
                "yellow_cards_home": 2,
                "yellow_cards_away": 2,
            }
            stats_b = {
                "corners_home": 4 + index % 2,
                "corners_away": 5 + index % 3,
                "yellow_cards_home": 1,
                "yellow_cards_away": 3,
            }
            history.append(
                fixture(fixture_id, start + timedelta(days=index * 4), 1, 3, 2, 1, stats=stats_a)
            )
            fixture_id += 1
            history.append(
                fixture(fixture_id, start + timedelta(days=index * 4 + 1), 4, 2, 1, 1, stats=stats_b)
            )
            fixture_id += 1
            history.append(
                fixture(fixture_id, start + timedelta(days=index * 4 + 2), 5, 6, 1, 0, stats=stats_a)
            )
            fixture_id += 1
            history.append(
                fixture(fixture_id, start + timedelta(days=index * 4 + 3), 6, 5, 0, 1, stats=stats_b)
            )
            fixture_id += 1
        target = fixture(999, start + timedelta(days=45), 1, 2)
        validation = {
            spec.key: credible_validation()
            for spec in MARKET_SPECS
        }

        candidates = build_fixture_candidates(target, history, validation)

        corner_candidates = [item for item in candidates if item.market_key.startswith("CORNERS_")]
        self.assertTrue(corner_candidates)
        self.assertTrue(any(item.base_eligible for item in corner_candidates))
        self.assertTrue(all(item.expected_unit == "Ecken" for item in corner_candidates))
        self.assertTrue(any(item.market_key.startswith("YELLOW_") for item in candidates))

        target_without_referee = fixture(1000, start + timedelta(days=45), 1, 2)
        target_without_referee["fixture"]["referee"] = None
        without_referee = build_fixture_candidates(
            target_without_referee,
            history,
            validation,
        )
        self.assertFalse(any(item.market_key.startswith("YELLOW_") for item in without_referee))


class FootballDataBoundaryTests(unittest.TestCase):
    def test_parser_whitelists_stats_and_drops_all_bookmaker_fields(self):
        csv_content = (
            "Date,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC,HY,AY,B365H,AvgH\n"
            "01/08/2025,Man United,Arsenal,2,1,7,3,2,4,1.50,1.55\n"
        ).encode("utf-8")
        upcoming = [
            {
                "teams": {
                    "home": {"id": 50, "name": "Manchester United"},
                    "away": {"id": 42, "name": "Arsenal"},
                }
            }
        ]

        history = parse_history_csv(csv_content, 39, 2025, upcoming)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["teams"]["home"]["id"], 50)
        self.assertEqual(history[0]["teams"]["away"]["id"], 42)
        self.assertEqual(history[0]["challenge_stats"]["corners_home"], 7)
        serialized = str(history[0])
        self.assertNotIn("B365", serialized)
        self.assertNotIn("AvgH", serialized)
        self.assertNotIn("1.50", serialized)

    def test_parser_never_truncates_fractional_result_or_count_data(self):
        csv_content = (
            "Date,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC,HY,AY\n"
            "01/08/2025,Alpha,Beta,1.5,1,7,3,2,4\n"
            "02/08/2025,Alpha,Beta,2,1,7.5,3,2,4\n"
        ).encode("utf-8")

        history = parse_history_csv(csv_content, 39, 2025, [])

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["goals"], {"home": 2, "away": 1})
        self.assertNotIn("corners_home", history[0]["challenge_stats"])


class ChallengeProviderTests(unittest.TestCase):
    @patch("challenge_15k.requests.get")
    def test_current_season_plan_error_is_localized_and_not_treated_as_empty(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "errors": {
                "plan": "Free plans do not have access to this season, try from 2022 to 2024."
            },
            "response": [],
        }
        get.return_value = response
        provider = ChallengeDataProvider("test-key", None)
        provider._rate_limit = lambda: None

        result = provider.upcoming_fixtures(39, 2026, datetime(2026, 7, 14).date())

        self.assertIsNone(result)
        self.assertIn("keinen Zugriff auf diese Saison", provider.errors[0])
        self.assertEqual(get.call_args.kwargs["params"]["status"], "NS")

    @patch("challenge_15k.requests.get")
    def test_mixed_provider_response_is_rejected_as_invalid(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"errors": [], "response": [{}, None]}
        get.return_value = response
        provider = ChallengeDataProvider("test-key", None)
        provider._rate_limit = lambda: None

        result = provider.upcoming_fixtures(39, 2026, datetime(2026, 7, 14).date())

        self.assertIsNone(result)
        self.assertIn("ungültige Einträge", provider.errors[0])

    def test_coverage_never_falls_back_to_a_different_season(self):
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(return_value=[{
            "seasons": [{
                "year": 2025,
                "coverage": {
                    "injuries": True,
                    "fixtures": {"lineups": True},
                },
            }],
        }])

        coverage = provider.coverage(39, 2026)

        self.assertEqual(coverage, {"injuries": False, "lineups": False})
        self.assertTrue(any("Saison 2026 fehlt" in error for error in provider.errors))

    def test_scan_rejects_ambiguous_request_parameters_before_provider_calls(self):
        provider = Mock()

        invalid_requests = (
            ([True], datetime.now().date(), 8),
            ([39, 39], datetime.now().date(), 8),
            ([39], datetime.now(timezone.utc), 8),
            ([39], datetime.now().date(), True),
            ([39], datetime.now().date(), 401),
        )
        for league_ids, search_date, max_fixtures in invalid_requests:
            with self.subTest(league_ids=league_ids, max_fixtures=max_fixtures):
                with self.assertRaises(ValueError):
                    scan_daily_challenge(provider, league_ids, search_date, max_fixtures)
        provider.upcoming_fixtures.assert_not_called()

    def test_scan_drops_malformed_and_duplicate_upcoming_fixtures(self):
        provider = Mock()
        provider.errors = []
        valid = fixture(
            900,
            datetime.now(timezone.utc) + timedelta(days=1),
            10,
            11,
        )
        provider.upcoming_fixtures.return_value = [None, valid, valid]
        provider.completed_history.return_value = []
        provider.coverage.return_value = {"injuries": True, "lineups": True}

        snapshot = scan_daily_challenge(
            provider,
            [39],
            datetime.now().date(),
            8,
        )

        self.assertEqual(snapshot["fixtures_found"], 1)
        self.assertTrue(any("ungültige Einträge" in error for error in snapshot["errors"]))
        self.assertTrue(any("doppelter Provider-Eintrag" in error for error in snapshot["errors"]))


class ChallengeContextTests(unittest.TestCase):
    def test_all_context_gates_pass_without_changing_probability(self):
        item = candidate("1:BTTS", 1, 0.70)
        original_probability = item.conservative_probability
        now = datetime.now(timezone.utc)
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 1, 1)
            for index in range(3)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=h2h,
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
                "description": "klar",
            },
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.conservative_probability, original_probability)

    def test_placeholder_lineups_never_count_as_confirmed(self):
        item = candidate("1:BTTS", 1, 0.70)
        now = datetime.now(timezone.utc)
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 1, 1)
            for index in range(3)
        ]
        forged_lineups = [
            {"team": {"id": team_id}, "startXI": [None] * 11}
            for team_id in (10, 11)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=h2h,
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
            },
            lineups=forged_lineups,
            now=now,
        )

        self.assertFalse(item.eligible)
        self.assertIn("Aufstellungen", " ".join(item.context["blocked_reasons"]))

    def test_unconfirmed_lineups_block_even_before_final_hour(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=5),
        )
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 1, 1)
            for index in range(3)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=h2h,
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
            },
            lineups=None,
            now=now,
        )

        self.assertFalse(item.eligible)
        self.assertIn(
            "Aufstellungen sind noch nicht verifiziert",
            item.context["blocked_reasons"],
        )

    def test_lineups_optional_do_not_block_when_disabled(self):
        item = candidate("1:BTTS", 1, 0.70)
        now = datetime.now(timezone.utc)
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 1, 1)
            for index in range(3)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=h2h,
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
                "description": "klar",
            },
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertTrue(item.eligible)
        self.assertNotIn("Aufstellung", " ".join(item.context["blocked_reasons"]))
        self.assertFalse(item.context["lineups"]["required"])

    def test_placeholder_lineups_still_ignored_when_optional(self):
        item = candidate("1:BTTS", 1, 0.70)
        now = datetime.now(timezone.utc)
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 1, 1)
            for index in range(3)
        ]
        forged_lineups = [
            {"team": {"id": team_id}, "startXI": [None] * 11}
            for team_id in (10, 11)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=h2h,
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
            },
            lineups=forged_lineups,
            now=now,
            require_lineups=False,
        )

        self.assertTrue(item.eligible)

    def test_missing_h2h_blocks_candidate(self):
        item = candidate("1:BTTS", 1, 0.70)

        apply_candidate_context(
            item,
            h2h_fixtures=[],
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
            },
            lineups=None,
        )

        self.assertFalse(item.eligible)
        self.assertIn("H2H-Stichprobe fehlt", item.context["blocked_reasons"])

    def test_missing_lineups_block_inside_the_final_hour(self):
        now = datetime.now(timezone.utc)
        item = candidate("1:BTTS", 1, 0.70, kickoff=now + timedelta(minutes=30))
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 1, 1)
            for index in range(3)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=h2h,
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 12,
                "wind_mps": 3,
                "rain_3h_mm": 0,
                "snow_3h_mm": 0,
            },
            lineups=[],
            now=now,
        )

        self.assertFalse(item.eligible)
        self.assertIn("Aufstellungen fehlen kurz vor Anpfiff", item.context["blocked_reasons"])


class ChallengeTicketTests(unittest.TestCase):
    def test_ticket_uses_at_most_three_unique_fixtures_and_target_odds(self):
        candidates = [
            candidate("1:BTTS", 1, 0.70),
            candidate("2:BTTS", 2, 0.68),
            candidate("3:BTTS", 3, 0.65),
        ]

        ticket = select_quoted_ticket(
            candidates,
            {"1:BTTS": 1.50, "2:BTTS": 1.50, "3:BTTS": 1.55},
        )

        self.assertIsNotNone(ticket)
        self.assertLessEqual(len(ticket.legs), 3)
        self.assertEqual(len({leg.candidate.fixture_id for leg in ticket.legs}), len(ticket.legs))
        self.assertGreaterEqual(ticket.total_odds, 2.0)
        self.assertLessEqual(ticket.total_odds, 3.0)
        self.assertAlmostEqual(ticket.model_dependency_factor, 0.97)
        self.assertLess(ticket.joint_probability, 0.70 * 0.68)

    def test_negative_value_single_leg_cannot_hide_in_ticket(self):
        candidates = [
            candidate("1:BTTS", 1, 0.60),
            candidate("2:BTTS", 2, 0.80),
        ]

        ticket = select_quoted_ticket(
            candidates,
            {"1:BTTS": 1.50, "2:BTTS": 1.50},
        )

        self.assertIsNone(ticket)

    def test_blocked_candidate_cannot_be_revived_by_high_odds(self):
        blocked = candidate("1:BTTS", 1, 0.70, eligible=False)

        ticket = select_quoted_ticket([blocked], {"1:BTTS": 2.50})

        self.assertIsNone(ticket)

    def test_selection_rechecks_validation_instead_of_trusting_passed_flag(self):
        item = candidate("1:BTTS", 1, 0.70)
        item.validation = ValidationMetrics(
            10,
            0.10,
            0.20,
            0.50,
            0.01,
            True,
            calibration_bins=1,
            min_bin_size=10,
            max_calibration_error=0.01,
        )

        self.assertFalse(candidate_is_credible(item))
        self.assertEqual(select_shortlist([item]), [])
        self.assertEqual(select_model_ticket([item]), ())
        self.assertIsNone(select_quoted_ticket([item], {"1:BTTS": 2.50}))

    def test_started_fixture_is_never_selected(self):
        started = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        self.assertEqual(select_model_ticket([started]), ())
        self.assertIsNone(select_quoted_ticket([started], {"1:BTTS": 2.50}))

    def test_ticket_rejects_repeated_team_across_different_fixtures(self):
        first = candidate("1:BTTS", 1, 0.70)
        second = candidate("2:BTTS", 2, 0.68)
        second.home_team_id = first.away_team_id

        self.assertEqual(select_model_ticket([first, second]), ())
        self.assertIsNone(select_quoted_ticket(
            [first, second],
            {"1:BTTS": 1.50, "2:BTTS": 1.50},
        ))

    def test_each_leg_must_have_value_even_when_combination_roi_is_positive(self):
        candidates = [
            candidate("1:BTTS", 1, 0.70),
            candidate("2:BTTS", 2, 0.80),
        ]

        ticket = select_quoted_ticket(
            candidates,
            {"1:BTTS": 1.45, "2:BTTS": 1.50},
        )

        self.assertIsNone(ticket)

    def test_challenge_stake_is_separate_from_kelly_reference(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket_stake(ticket, 1000), 1000.0)
        self.assertEqual(ticket_stake(ticket, 1000, 0.25), 250.0)
        capped_ticket = replace(ticket, stake_fraction=0.02)
        self.assertEqual(ticket_stake(capped_ticket, 101.25, 0.25), 25.31)
        self.assertEqual(kelly_reference_stake(capped_ticket, 101.25), 2.02)

    def test_rollover_growth_projection_matches_target_math(self):
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 2.0, 1.0), 8)
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 3.0, 1.0), 5)
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 2.0, 0.5), 13)
        self.assertEqual(consecutive_wins_to_target(15_000, 15_000, 2.0, 1.0), 0)


class ChallengeLedgerTests(unittest.TestCase):
    def test_place_and_win_are_cent_accurate_and_idempotent(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            stake = ticket_stake(ticket, 100.0)
            ticket_id = ledger.place_ticket(
                "2026-07-14",
                ticket,
                stake,
                datetime.now(timezone.utc).isoformat(),
            )
            self.assertEqual(ledger.settings()["current_balance"], 100.0 - stake)

            ledger.settle_ticket(ticket_id, "WON")
            payout = (
                Decimal(str(stake)) * Decimal(str(ticket.total_odds))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            expected_balance = float(Decimal("100.00") - Decimal(str(stake)) + payout)
            self.assertEqual(ledger.settings()["current_balance"], expected_balance)
            with self.assertRaises(ValueError):
                ledger.settle_ticket(ticket_id, "WON")
            self.assertEqual(ledger.settings()["current_balance"], expected_balance)

    def test_only_one_non_void_ticket_per_day(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            stake = ticket_stake(ticket, 100.0)
            ledger.place_ticket(
                "2026-07-14",
                ticket,
                stake,
                datetime.now(timezone.utc).isoformat(),
            )
            with self.assertRaises(ValueError):
                ledger.place_ticket(
                    "2026-07-14",
                    ticket,
                    stake,
                    datetime.now(timezone.utc).isoformat(),
                )

    def test_open_ticket_blocks_new_placement_even_on_another_date(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ledger.set_stake_fraction(0.5)
            stake = ticket_stake(ticket, 100.0, 0.5)
            ticket_id = ledger.place_ticket(
                "2026-07-14",
                ticket,
                stake,
                datetime.now(timezone.utc).isoformat(),
            )
            # A second ticket for tomorrow would stack concurrent exposure.
            with self.assertRaises(ValueError):
                ledger.place_ticket(
                    "2026-07-15",
                    ticket,
                    stake,
                    datetime.now(timezone.utc).isoformat(),
                )
            # Once the open ticket is settled, the next match day is allowed.
            ledger.settle_ticket(ticket_id, "LOST")
            second_stake = ticket_stake(
                ticket,
                ledger.settings()["current_balance"],
                ledger.settings()["stake_fraction"],
            )
            second_id = ledger.place_ticket(
                "2026-07-15",
                ticket,
                second_stake,
                datetime.now(timezone.utc).isoformat(),
            )
            self.assertGreater(second_id, ticket_id)

    def test_ledger_recomputes_ticket_math_quote_age_and_challenge_cap(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ledger.set_stake_fraction(0.25)
            stake = ticket_stake(ticket, 100.0, 0.25)
            with self.assertRaises(ValueError):
                ledger.place_ticket(
                    "2026-07-14",
                    ticket,
                    stake,
                    (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat(),
                )
            with self.assertRaises(ValueError):
                ledger.place_ticket(
                    "2026-07-14",
                    replace(ticket, expected_roi=0.50),
                    stake,
                    datetime.now(timezone.utc).isoformat(),
                )
            with self.assertRaises(ValueError):
                ledger.place_ticket(
                    "2026-07-14",
                    ticket,
                    stake + 0.01,
                    datetime.now(timezone.utc).isoformat(),
                )

    def test_legacy_database_migrates_to_full_rollover_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE challenge_settings (
                        id INTEGER PRIMARY KEY,
                        starting_balance_cents INTEGER NOT NULL,
                        current_balance_cents INTEGER NOT NULL,
                        target_balance_cents INTEGER NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO challenge_settings VALUES (1, 10000, 10000, 1500000, 'now')"
                )
                connection.commit()

            ledger = ChallengeLedger(db_path)

            self.assertEqual(ledger.settings()["stake_fraction"], 1.0)
            ledger.set_stake_fraction(0.25)
            self.assertEqual(ledger.settings()["stake_fraction"], 0.25)


class _SettleProvider:
    """Provider-Double: liefert vorbereitete Fixture-Details."""

    def __init__(self, fixtures_by_id):
        self._fixtures = fixtures_by_id
        self.calls = 0

    def details_by_fixture(self, fixture_ids):
        self.calls += 1
        return {fid: self._fixtures.get(fid) for fid in fixture_ids}


def _result_fixture(fixture_id, home, away, status="FT"):
    item = fixture(
        fixture_id,
        datetime.now(timezone.utc) - timedelta(hours=3),
        home_id=fixture_id * 10,
        away_id=fixture_id * 10 + 1,
        home_goals=home,
        away_goals=away,
    )
    item["fixture"]["status"] = {"short": status}
    return item


def _placed_ticket(ledger, fixture_ids=(1, 2)):
    candidates = [
        candidate(f"{fid}:BTTS", fid, 0.70 - idx * 0.02)
        for idx, fid in enumerate(fixture_ids)
    ]
    ticket = select_quoted_ticket(
        candidates, {item.candidate_id: 1.50 for item in candidates}
    )
    assert ticket is not None
    stake = ticket_stake(ticket, ledger.settings()["current_balance"])
    ticket_id = ledger.place_ticket(
        "2026-07-14",
        ticket,
        stake,
        datetime.now(timezone.utc).isoformat(),
    )
    return ticket_id, ticket, stake


class AutoSettleTests(unittest.TestCase):
    def test_won_ticket_pays_out_and_keeps_start(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id, ticket, stake = _placed_ticket(ledger)
            provider = _SettleProvider(
                {
                    1: _result_fixture(1, 2, 1),
                    2: _result_fixture(2, 1, 3),
                }
            )
            summary = auto_settle_open_tickets(ledger, provider)
            self.assertEqual(summary["won"], 1)
            self.assertEqual(summary["resets"], 0)
            payout = (
                Decimal(str(stake)) * Decimal(str(ticket.total_odds))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            expected = float(Decimal("100.00") - Decimal(str(stake)) + payout)
            self.assertAlmostEqual(ledger.settings()["current_balance"], expected, places=2)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "WON")

    def test_lost_ticket_restarts_challenge_at_start_balance(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id, _ticket, _stake = _placed_ticket(ledger)
            provider = _SettleProvider(
                {
                    1: _result_fixture(1, 2, 1),
                    2: _result_fixture(2, 0, 0),  # BTTS Ja verloren
                }
            )
            summary = auto_settle_open_tickets(ledger, provider)
            self.assertEqual(summary["lost"], 1)
            self.assertEqual(summary["resets"], 1)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "LOST")
            settings = ledger.settings()
            self.assertEqual(settings["current_balance"], 100.0)
            self.assertEqual(settings["starting_balance"], 100.0)

    def test_running_and_aet_games_stay_open(self):
        from challenge_15k import auto_settle_open_tickets

        for status in ("1H", "AET", "PEN"):
            with tempfile.TemporaryDirectory() as tmp:
                ledger = ChallengeLedger(Path(tmp) / "challenge.db")
                ticket_id, _ticket, stake = _placed_ticket(ledger)
                provider = _SettleProvider(
                    {
                        1: _result_fixture(1, 2, 1),
                        2: _result_fixture(2, 1, 0, status=status),
                    }
                )
                summary = auto_settle_open_tickets(ledger, provider)
                self.assertEqual(summary["open"], 1, status)
                self.assertEqual(ledger.get_ticket(ticket_id)["status"], "PENDING")
                self.assertEqual(
                    ledger.settings()["current_balance"], 100.0 - stake, status
                )

    def test_all_void_legs_voids_ticket_and_returns_stake(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id, _ticket, _stake = _placed_ticket(ledger)
            provider = _SettleProvider(
                {
                    1: _result_fixture(1, 0, 0, status="PST"),
                    2: _result_fixture(2, 0, 0, status="CANC"),
                }
            )
            summary = auto_settle_open_tickets(ledger, provider)
            self.assertEqual(summary["void"], 1)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "VOID")
            self.assertEqual(ledger.settings()["current_balance"], 100.0)

    def test_api_cap_keeps_ticket_open(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id, _ticket, _stake = _placed_ticket(ledger)
            provider = _SettleProvider({1: _result_fixture(1, 2, 1)})
            summary = auto_settle_open_tickets(ledger, provider, max_api_calls=1)
            self.assertEqual(summary["open"], 1)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "PENDING")

    def test_spec_mapping_covers_all_market_specs(self):
        from challenge_15k import _spec_by_market_selection

        mapping = _spec_by_market_selection()
        self.assertEqual(len(mapping), len(MARKET_SPECS))


class CountStatsResponseTests(unittest.TestCase):
    def test_valid_response_maps_home_away(self):
        from challenge_15k import count_stats_from_response

        data = [
            {"team": {"id": 10}, "statistics": [
                {"type": "Corner Kicks", "value": 6},
                {"type": "Yellow Cards", "value": 1},
                {"type": "Ball Possession", "value": "55%"},
            ]},
            {"team": {"id": 11}, "statistics": [
                {"type": "Corner Kicks", "value": "5"},
                {"type": "Yellow Cards", "value": 2},
            ]},
        ]
        counts = count_stats_from_response(data, 10, 11)
        self.assertEqual(counts["corners_home"], 6)
        self.assertEqual(counts["corners_away"], 5)
        self.assertEqual(counts["yellow_cards_home"], 1)
        self.assertEqual(counts["yellow_cards_away"], 2)

    def test_invalid_values_are_skipped(self):
        from challenge_15k import count_stats_from_response

        data = [
            {"team": {"id": 10}, "statistics": [
                {"type": "Corner Kicks", "value": True},
                {"type": "Yellow Cards", "value": 99},
                {"type": "Corner Kicks", "value": None},
            ]},
            {"team": {"id": 11}, "statistics": [
                {"type": "Corner Kicks", "value": -3},
            ]},
        ]
        self.assertEqual(count_stats_from_response(data, 10, 11), {})

    def test_wrong_or_duplicate_teams_rejected(self):
        from challenge_15k import count_stats_from_response

        wrong = [
            {"team": {"id": 999}, "statistics": []},
            {"team": {"id": 11}, "statistics": []},
        ]
        self.assertEqual(count_stats_from_response(wrong, 10, 11), {})
        duplicate = [
            {"team": {"id": 10}, "statistics": []},
            {"team": {"id": 10}, "statistics": []},
        ]
        self.assertEqual(count_stats_from_response(duplicate, 10, 11), {})
        self.assertEqual(count_stats_from_response([], 10, 11), {})
        self.assertEqual(count_stats_from_response(None, 10, 11), {})
        self.assertEqual(count_stats_from_response([{"team": {"id": 10}, "statistics": []}], 10, 11), {})
        self.assertEqual(count_stats_from_response([], 10, 10), {})


class _StatsSettleProvider(_SettleProvider):
    """Provider-Double mit Statistik-Endpunkt für Zählmarkt-Abrechnung."""

    def __init__(self, fixtures_by_id, stats_by_id):
        super().__init__(fixtures_by_id)
        self._stats = stats_by_id

    def statistics_by_fixture(self, fixture_id):
        return self._stats.get(fixture_id)


def _corner_stats_response(home_id, away_id, corners_home, corners_away):
    return [
        {"team": {"id": home_id}, "statistics": [
            {"type": "Corner Kicks", "value": corners_home},
        ]},
        {"team": {"id": away_id}, "statistics": [
            {"type": "Corner Kicks", "value": corners_away},
        ]},
    ]


def _corner_candidate(fixture_id):
    item = candidate(f"{fixture_id}:CORNERS_OVER_9_5", fixture_id, 0.70)
    item.market_key = "CORNERS_OVER_9_5"
    item.market = "Eckbälle: Gesamtzahl"
    item.selection = "Über 9.5"
    return item


def _placed_count_ticket(ledger, fixture_ids=(1, 2)):
    candidates = [_corner_candidate(fid) for fid in fixture_ids]
    ticket = select_quoted_ticket(
        candidates, {item.candidate_id: 1.50 for item in candidates}
    )
    assert ticket is not None
    stake = ticket_stake(ticket, ledger.settings()["current_balance"])
    return ledger.place_ticket(
        "2026-07-14",
        ticket,
        stake,
        datetime.now(timezone.utc).isoformat(),
    )


class CountSettlementTests(unittest.TestCase):
    def test_corner_ticket_settles_on_corner_counts_not_goals(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id = _placed_count_ticket(ledger)
            # Tore wären verloren (4 bzw. 2 < 9,5), Ecken gewonnen (11 >= 10).
            provider = _StatsSettleProvider(
                {
                    1: _result_fixture(1, 2, 2),
                    2: _result_fixture(2, 1, 1),
                },
                {
                    1: _corner_stats_response(10, 11, 6, 5),
                    2: _corner_stats_response(20, 21, 7, 4),
                },
            )
            summary = auto_settle_open_tickets(ledger, provider)
            self.assertEqual(summary["won"], 1)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "WON")

    def test_missing_statistics_keeps_count_ticket_open(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id = _placed_count_ticket(ledger)
            provider = _StatsSettleProvider(
                {
                    1: _result_fixture(1, 5, 4),
                    2: _result_fixture(2, 3, 3),
                },
                {},
            )
            summary = auto_settle_open_tickets(ledger, provider)
            self.assertEqual(summary["open"], 1)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "PENDING")

    def test_wrong_team_mapping_keeps_count_ticket_open(self):
        from challenge_15k import auto_settle_open_tickets

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id = _placed_count_ticket(ledger)
            provider = _StatsSettleProvider(
                {
                    1: _result_fixture(1, 5, 4),
                    2: _result_fixture(2, 3, 3),
                },
                {
                    1: _corner_stats_response(999, 998, 8, 8),
                    2: _corner_stats_response(20, 21, 7, 4),
                },
            )
            summary = auto_settle_open_tickets(ledger, provider)
            self.assertEqual(summary["open"], 1)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "PENDING")


class AutoRecheckTests(unittest.TestCase):
    def test_eligible_only_in_waiting_state_today(self):
        from challenge_15k import _auto_recheck_eligible, _challenge_today

        today = _challenge_today()
        waiting = {"shortlist": [], "base_shortlist": [object()]}
        released = {"shortlist": [object()], "base_shortlist": [object()]}
        empty = {"shortlist": [], "base_shortlist": []}
        self.assertTrue(_auto_recheck_eligible(waiting, today))
        self.assertFalse(_auto_recheck_eligible(released, today))
        self.assertFalse(_auto_recheck_eligible(empty, today))
        self.assertFalse(_auto_recheck_eligible(waiting, today + timedelta(days=1)))
        self.assertFalse(_auto_recheck_eligible(None, today))

    def test_no_window_means_no_fire_but_next_kickoff_known(self):
        from challenge_15k import _auto_recheck_decision

        now = datetime.now(timezone.utc)
        later = now + timedelta(hours=3)
        item = candidate("1:X", 1, 0.70, kickoff=later)
        decision = _auto_recheck_decision([item], now, None, set())
        self.assertFalse(decision["due"])
        self.assertEqual(decision["in_window"], set())
        self.assertEqual(decision["next_kickoff"], later)

    def test_new_window_entry_fires(self):
        from challenge_15k import _auto_recheck_decision

        now = datetime.now(timezone.utc)
        item = candidate("1:X", 1, 0.70, kickoff=now + timedelta(minutes=60))
        decision = _auto_recheck_decision([item], now, None, set())
        self.assertTrue(decision["due"])
        self.assertEqual(decision["in_window"], {1})

    def test_min_gap_blocks_immediate_refire(self):
        from challenge_15k import _auto_recheck_decision

        now = datetime.now(timezone.utc)
        item = candidate("1:X", 1, 0.70, kickoff=now + timedelta(minutes=60))
        decision = _auto_recheck_decision([item], now, now - timedelta(minutes=5), set())
        self.assertFalse(decision["due"])

    def test_retry_after_gap_when_context_still_missing(self):
        from challenge_15k import _auto_recheck_decision

        now = datetime.now(timezone.utc)
        item = candidate("1:X", 1, 0.70, kickoff=now + timedelta(minutes=60))
        decision = _auto_recheck_decision([item], now, now - timedelta(minutes=20), {1})
        self.assertTrue(decision["due"])

    def test_long_past_kickoff_leaves_window(self):
        from challenge_15k import _auto_recheck_decision

        now = datetime.now(timezone.utc)
        item = candidate("1:X", 1, 0.70, kickoff=now - timedelta(minutes=30))
        decision = _auto_recheck_decision([item], now, None, set())
        self.assertFalse(decision["due"])
        self.assertIsNone(decision["next_kickoff"])


if __name__ == "__main__":
    unittest.main()
