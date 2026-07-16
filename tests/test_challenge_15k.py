import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from challenge_15k import ChallengeDataProvider
from challenge_engine import (
    ChallengeCandidate,
    MARKET_BY_KEY,
    MARKET_SPECS,
    ValidationMetrics,
    apply_candidate_context,
    build_fixture_candidates,
    market_outcome,
    score_matrix,
    select_quoted_ticket,
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
    validation = ValidationMetrics(100, 0.15, 0.2, 0.25, 0.04, True)
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


class ChallengeProbabilityTests(unittest.TestCase):
    def test_score_matrix_is_normalized(self):
        matrix = score_matrix(1.4, 1.1)

        self.assertAlmostEqual(sum(matrix.values()), 1.0, places=12)
        self.assertGreater(matrix[(1, 1)], 0)

    def test_supported_markets_settle_exactly(self):
        self.assertTrue(market_outcome(MARKET_BY_KEY["BTTS_YES"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["TOTAL_UNDER_3_5"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["HOME_RANGE_2_4"], 2, 0))
        self.assertFalse(market_outcome(MARKET_BY_KEY["DC_X2"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["CORNERS_OVER_5_5"], 4, 3))
        self.assertTrue(market_outcome(MARKET_BY_KEY["HOME_YELLOW_OVER_1_5"], 2, 1))

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
            spec.key: ValidationMetrics(100, 0.15, 0.2, 0.25, 0.04, True)
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
            spec.key: ValidationMetrics(100, 0.15, 0.2, 0.25, 0.04, True)
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
            lineups=None,
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.conservative_probability, original_probability)

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

    def test_stake_is_capped_at_two_percent(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})

        self.assertIsNotNone(ticket)
        self.assertLessEqual(ticket_stake(ticket, 1000), 20.0)


class ChallengeLedgerTests(unittest.TestCase):
    def test_place_and_win_are_cent_accurate_and_idempotent(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id = ledger.place_ticket(
                "2026-07-14",
                ticket,
                2.00,
                datetime.now(timezone.utc).isoformat(),
            )
            self.assertEqual(ledger.settings()["current_balance"], 98.0)

            ledger.settle_ticket(ticket_id, "WON")
            self.assertEqual(ledger.settings()["current_balance"], 102.5)
            with self.assertRaises(ValueError):
                ledger.settle_ticket(ticket_id, "WON")
            self.assertEqual(ledger.settings()["current_balance"], 102.5)

    def test_only_one_non_void_ticket_per_day(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.68)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ledger.place_ticket(
                "2026-07-14",
                ticket,
                2.00,
                datetime.now(timezone.utc).isoformat(),
            )
            with self.assertRaises(ValueError):
                ledger.place_ticket(
                    "2026-07-14",
                    ticket,
                    2.00,
                    datetime.now(timezone.utc).isoformat(),
                )


if __name__ == "__main__":
    unittest.main()
