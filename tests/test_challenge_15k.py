from contextlib import closing
from collections import Counter
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import challenge_15k
from challenge_15k import (
    CHALLENGE_SPORT_OPTIONS,
    ChallengeDataProvider,
    MAX_DISCOVERY_MARKETS_PER_FIXTURE,
    MAX_SCAN_FIXTURES,
    _auto_recheck_scope_allowed,
    _automatic_challenge_ticket,
    _challenge_sports_for_selection,
    _context_scope_facts,
    _discovery_candidate_pool,
    _forecast_candidate_pool,
    _league_season_segments,
    _price_candidate_pool,
    _ranked_fixture_ids,
    _recommendation_day_label,
    _render_price_check,
    _run_challenge_scan_worker,
    _scan_candidate_diagnostics,
    _segmented,
    _shortlist_counts,
    refresh_discovered_candidates,
    scan_no_result_copy,
    scan_daily_challenge,
)
from challenge_engine import (
    ChallengeCandidate,
    MARKET_BY_KEY,
    MARKET_SPECS,
    MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST,
    MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
    UNVALIDATED_TRANSFER_REASON,
    ValidationMetrics,
    apply_candidate_context,
    build_fixture_candidates,
    candidate_context_summary,
    candidate_is_forecast_credible,
    candidate_is_credible,
    challenge_stake_cap,
    consecutive_wins_to_target,
    expected_log_growth,
    kelly_reference_stake,
    market_is_basic_forecast,
    market_outcome,
    score_matrix,
    risk_managed_ticket_stake,
    select_forecast_shortlist,
    select_basis_forecasts,
    select_model_ticket,
    select_quoted_ticket,
    select_shortlist,
    ticket_stake,
    validate_league_markets,
)
from challenge_store import ChallengeLedger
from football_data_history import parse_history_csv
from price_ledger import PriceLedger, PriceQuote
from market_consensus import parse_fixture_consensus


def test_cached_market_artifact_builds_and_saves_one_paired_cold_result():
    history = [{"fixture": {"id": 1}}]
    artifact = ({"market": "validation"}, {"market": "calibration"})

    with (
        patch("challenge_15k.load_model_artifact", return_value=None) as load_mock,
        patch(
            "challenge_15k.build_market_model_artifact",
            return_value=artifact,
        ) as build_mock,
        patch("challenge_15k.save_model_artifact") as save_mock,
    ):
        result = challenge_15k._cached_market_artifact.__wrapped__(39, 2025, history)

    assert result == artifact
    load_mock.assert_called_once_with(
        challenge_15k.CHALLENGE_MODEL_SIGNATURE,
        39,
        2025,
        history,
    )
    build_mock.assert_called_once_with(history)
    save_mock.assert_called_once_with(
        challenge_15k.CHALLENGE_MODEL_SIGNATURE,
        39,
        2025,
        history,
        artifact[0],
        artifact[1],
    )


def test_cached_market_artifact_reuses_persistent_hit_without_rebuilding():
    history = [{"fixture": {"id": 1}}]
    artifact = ({"market": "validation"}, {"market": "calibration"})

    with (
        patch("challenge_15k.load_model_artifact", return_value=artifact) as load_mock,
        patch("challenge_15k.build_market_model_artifact") as build_mock,
        patch("challenge_15k.save_model_artifact") as save_mock,
    ):
        result = challenge_15k._cached_market_artifact.__wrapped__(39, 2025, history)

    assert result == artifact
    load_mock.assert_called_once_with(
        challenge_15k.CHALLENGE_MODEL_SIGNATURE,
        39,
        2025,
        history,
    )
    build_mock.assert_not_called()
    save_mock.assert_not_called()


def _complete_context() -> dict:
    return {
        "model_transfer": {"status": "passed"},
        "h2h": {"status": "neutral"},
        "injuries": {"status": "observed"},
        "weather": {"status": "passed"},
        "lineups": {"status": "pending", "required": False},
    }


def test_context_scope_facts_never_claims_fixture_21_was_checked():
    candidates = [
        SimpleNamespace(fixture_id=fixture_id, context=_complete_context())
        for fixture_id in range(1, 22)
    ]

    facts = _context_scope_facts(candidates, list(range(1, 21)), set())

    assert facts["base_fixture_count"] == 21
    assert facts["context_verified_fixtures"] == 20
    assert facts["context_data_incomplete_fixtures"] == 0
    assert facts["context_unchecked_fixtures"] == 1
    assert facts["context_scope_complete"] is False
    assert facts["context_fixture_statuses"] == {
        **{str(fixture_id): "verified" for fixture_id in range(1, 21)},
        "21": "unchecked",
    }
    assert facts["context_fixture_provenance"]["21"]["scope_status"] == "unchecked"
    assert facts["context_fixture_provenance"]["21"]["checked_at"] is None


def test_context_scope_facts_treats_explicit_optional_unavailability_as_checked():
    optional_unavailable = _complete_context()
    optional_unavailable["weather"] = {"status": "unavailable"}
    optional_unavailable["h2h"] = {"status": "unavailable"}
    optional_unavailable["injuries"] = {"status": "unavailable"}

    facts = _context_scope_facts(
        [SimpleNamespace(fixture_id=7, context=optional_unavailable)],
        [7],
        set(),
    )

    assert facts["context_verified_fixtures"] == 1
    assert facts["context_data_incomplete_fixtures"] == 0
    assert facts["context_unchecked_fixtures"] == 0
    assert facts["context_scope_complete"] is True


def test_context_scope_facts_counts_terminal_kickoff_rejection_as_checked():
    facts = _context_scope_facts(
        [
            SimpleNamespace(
                fixture_id=8,
                context={
                    "passed": False,
                    "blocked_reasons": ["Spiel hat bereits begonnen"],
                },
            )
        ],
        [8],
        set(),
    )

    assert facts["context_verified_fixtures"] == 1
    assert facts["context_data_incomplete_fixtures"] == 0
    assert facts["context_scope_complete"] is True
    assert facts["context_fixture_statuses"] == {"8": "verified"}


def test_context_scope_facts_persists_axis_status_and_timestamps():
    context = _complete_context()
    context["checked_at"] = "2030-01-01T12:00:00+00:00"
    context["h2h"] = {
        "status": "unavailable",
        "availability": "provider_unavailable",
        "checked_at": "2030-01-01T12:00:00+00:00",
    }
    context["weather"] = {
        "status": "observed",
        "availability": "available",
        "checked_at": "2030-01-01T12:00:00+00:00",
        "forecast_at": "2030-01-01T14:00:00+00:00",
    }

    facts = _context_scope_facts(
        [
            SimpleNamespace(
                fixture_id=9,
                model_scope=MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST,
                context=context,
            )
        ],
        [9],
        set(),
    )

    provenance = facts["context_fixture_provenance"]["9"]
    assert provenance["scope_status"] == "verified"
    assert provenance["checked_at"] == "2030-01-01T12:00:00+00:00"
    assert provenance["model_scopes"] == [
        MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
    ]
    assert provenance["axes"]["h2h"]["statuses"] == ["unavailable"]
    assert provenance["axes"]["h2h"]["availability"] == [
        "provider_unavailable"
    ]
    assert provenance["axes"]["weather"]["observed_at"] == (
        "2030-01-01T14:00:00+00:00"
    )


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
    item.context = {
        "passed": eligible,
        "forecast_passed": eligible,
        "release_context_complete": eligible,
        "release_eligible": eligible,
        "blocked_reasons": [] if eligible else ["blocked"],
    }
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


def reference_quote_for(item, now, odds=("2.05", "2.10", "2.15", "2.20")):
    payload = {
        "errors": [],
        "response": [
            {
                "fixture": {"id": item.fixture_id},
                "update": now.isoformat(),
                "bookmakers": [
                    {
                        "name": f"Book {index}",
                        "bets": [
                            {
                                "name": "Both Teams Score",
                                "values": [
                                    {"value": "Yes", "odd": value},
                                ],
                            }
                        ],
                    }
                    for index, value in enumerate(odds, start=1)
                ],
            }
        ],
    }
    return parse_fixture_consensus(payload, [item], fetched_at=now)[
        item.candidate_id
    ]


class ChallengeProbabilityTests(unittest.TestCase):
    def test_challenge_sport_dropdown_offers_all_shared_sports(self):
        self.assertEqual(
            CHALLENGE_SPORT_OPTIONS,
            (
                "Alle",
                "Fußball",
                "Tennis",
                "Basketball",
                "Eishockey",
                "Cricket",
                "E-Sport",
            ),
        )
        self.assertEqual(_challenge_sports_for_selection("Alle"), ("Fußball",))
        self.assertEqual(_challenge_sports_for_selection("Tennis"), ())

    def test_daily_discovery_pool_limits_markets_per_fixture(self):
        fixture_one = [
            candidate(
                f"1:MARKET_{index}",
                1,
                0.60 + index / 1000.0,
            )
            for index in range(MAX_DISCOVERY_MARKETS_PER_FIXTURE + 3)
        ]
        fixture_two = [candidate("2:BTTS", 2, 0.65)]

        pool = _discovery_candidate_pool(
            fixture_one + fixture_two,
            [1, 2],
        )

        self.assertEqual(
            sum(item.fixture_id == 1 for item in pool),
            MAX_DISCOVERY_MARKETS_PER_FIXTURE,
        )
        self.assertTrue(any(item.fixture_id == 2 for item in pool))

    def test_daily_discovery_pool_preserves_market_family_diversity(self):
        high_probability_results = [
            replace(
                candidate(f"1:RESULT_{index}", 1, 0.90 - index / 1000),
                market_key="RESULT_HOME",
            )
            for index in range(8)
        ]
        diverse = [
            replace(candidate("1:BTTS", 1, 0.70), market_key="BTTS_YES"),
            replace(
                candidate("1:TOTAL", 1, 0.69),
                market_key="TOTAL_OVER_2_5",
            ),
            replace(
                candidate("1:CORNERS", 1, 0.68),
                market_key="CORNERS_OVER_8_5",
            ),
            replace(
                candidate("1:YELLOW", 1, 0.67),
                market_key="YELLOW_OVER_2_5",
            ),
        ]

        pool = _discovery_candidate_pool(
            high_probability_results + diverse,
            [1],
        )
        kinds = {MARKET_BY_KEY[item.market_key].kind for item in pool}

        self.assertEqual(len(pool), MAX_DISCOVERY_MARKETS_PER_FIXTURE)
        self.assertTrue(
            {"result", "btts", "total", "corner_total", "yellow_total"}
            <= kinds
        )

    def test_segmented_omits_default_when_session_value_already_exists(self):
        fake_streamlit = Mock()
        fake_streamlit.session_state = {"mode": "B"}
        fake_streamlit.segmented_control.return_value = "B"

        with patch("challenge_15k.st", fake_streamlit):
            self.assertEqual(_segmented("Mode", ["A", "B"], "mode", "A"), "B")

        kwargs = fake_streamlit.segmented_control.call_args.kwargs
        self.assertNotIn("default", kwargs)

    def test_segmented_supplies_default_for_new_session_key(self):
        fake_streamlit = Mock()
        fake_streamlit.session_state = {}
        fake_streamlit.segmented_control.return_value = "A"

        with patch("challenge_15k.st", fake_streamlit):
            self.assertEqual(_segmented("Mode", ["A", "B"], "mode", "A"), "A")

        self.assertEqual(
            fake_streamlit.segmented_control.call_args.kwargs["default"],
            "A",
        )

    def test_shortlist_counts_markets_and_unique_games_separately(self):
        markets = [
            candidate("1:BTTS", 1, 0.70),
            candidate("1:OVER_25", 1, 0.68),
            candidate("2:HOME_OVER_05", 2, 0.72),
        ]

        self.assertEqual(_shortlist_counts(markets), (3, 2))

    def test_price_pool_skips_broad_basis_market_from_one_fixture(self):
        favorite = candidate("1:RESULT_HOME", 1, 0.73)
        favorite = replace(
            favorite,
            market_key="RESULT_HOME",
            market="Endergebnis",
            selection="Home 1",
        )
        alternative = candidate("1:TOTAL_UNDER_4_5", 1, 0.69)
        alternative = replace(
            alternative,
            market_key="TOTAL_UNDER_4_5",
            market="Gesamttore",
            selection="Unter 4,5",
        )

        pool = _price_candidate_pool([favorite, alternative])

        self.assertEqual(
            [item.candidate_id for item in pool],
            ["1:RESULT_HOME"],
        )
        self.assertEqual(len(select_shortlist(pool, max_candidates=3)), 1)

    def test_price_pool_excludes_markets_without_an_exact_quote_mapping(self):
        mappable = candidate("1:BTTS_YES", 1, 0.70)
        unmappable = replace(
            candidate("2:HOME_RANGE_1_3", 2, 0.71),
            market_key="HOME_RANGE_1_3",
            market="Team 1 Gesamttore",
            selection="1-3 Tore",
        )

        pool = _price_candidate_pool([unmappable, mappable])

        self.assertEqual([item.candidate_id for item in pool], ["1:BTTS_YES"])

    def test_forecast_pool_keeps_market_without_exact_quote_mapping(self):
        mappable = candidate("1:BTTS_YES", 1, 0.70)
        unmappable = replace(
            candidate("2:HOME_RANGE_1_3", 2, 0.71),
            market_key="HOME_RANGE_1_3",
            market="Team 1 Gesamttore",
            selection="1-3 Tore",
        )

        forecast_pool = _forecast_candidate_pool([unmappable, mappable])
        price_pool = _price_candidate_pool([unmappable, mappable])

        self.assertEqual(
            [item.candidate_id for item in forecast_pool],
            ["2:HOME_RANGE_1_3", "1:BTTS_YES"],
        )
        self.assertEqual(
            [item.candidate_id for item in price_pool],
            ["1:BTTS_YES"],
        )

    def test_forecast_shortlist_keeps_provisional_but_release_shortlist_does_not(self):
        validated = candidate("1:BTTS", 1, 0.68)
        provisional = candidate("2:BTTS", 2, 0.72)
        provisional.model_scope = MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
        provisional.context = {
            "passed": True,
            "forecast_passed": True,
            "release_eligible": False,
            "blocked_reasons": [],
            "model_transfer": {"status": "provisional"},
        }
        weaker_same_fixture = candidate("2:BTTS_ALT", 2, 0.69)
        weaker_same_fixture.model_scope = (
            MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
        )
        weaker_same_fixture.context = dict(provisional.context)

        price_pool = _price_candidate_pool(
            [validated, provisional, weaker_same_fixture]
        )
        forecast = select_forecast_shortlist(
            price_pool,
            max_candidates=3,
        )

        self.assertEqual(
            {item.candidate_id for item in price_pool},
            {"1:BTTS", "2:BTTS", "2:BTTS_ALT"},
        )
        self.assertEqual(
            [item.candidate_id for item in forecast],
            ["2:BTTS", "1:BTTS"],
        )
        self.assertEqual(
            [item.candidate_id for item in select_shortlist(forecast, 3)],
            ["1:BTTS"],
        )

    def test_scan_worker_prices_every_market_in_the_fixture_pool(self):
        favorite = candidate("1:RESULT_HOME", 1, 0.73)
        alternative = candidate("1:TOTAL_UNDER_4_5", 1, 0.69)
        snapshot = {
            "shortlist": [favorite],
            "price_candidates": [favorite, alternative],
        }
        provider = Mock(api_key="test")

        with (
            patch("challenge_15k.scan_daily_challenge", return_value=snapshot),
            patch(
                "challenge_15k.fetch_football_consensus",
                return_value=({}, []),
            ) as fetch_quotes,
        ):
            result = _run_challenge_scan_worker(
                provider,
                [39],
                date(2030, 1, 1),
                20,
            )

        self.assertEqual(
            fetch_quotes.call_args.args[1],
            [favorite, alternative],
        )
        self.assertEqual(result["price_checked_markets"], 2)
        self.assertEqual(result["price_checked_fixtures"], 1)

    def test_recommendation_day_label_uses_scanned_date(self):
        today = date(2030, 1, 1)

        self.assertEqual(
            _recommendation_day_label("2030-01-01", today=today),
            "Heute",
        )
        self.assertEqual(
            _recommendation_day_label("2030-01-02", today=today),
            "Morgen",
        )
        self.assertEqual(
            _recommendation_day_label("2030-01-04", today=today),
            "Am 04.01.2030",
        )
        self.assertEqual(
            _recommendation_day_label("ungültig", today=today),
            "Für den gewählten Spieltag",
        )

    def test_empty_recommendation_uses_snapshot_day(self):
        fake_streamlit = MagicMock()
        snapshot = {
            "shortlist": [],
            "search_date": "2030-01-02",
            "fixtures_found": 19,
            "fixtures_modeled": 8,
        }

        with (
            patch("challenge_15k.st", fake_streamlit),
            patch(
                "challenge_15k._challenge_today",
                return_value=date(2030, 1, 1),
            ),
        ):
            _render_price_check(snapshot, Mock(), {})

        fake_streamlit.info.assert_called_once_with(
            "Für diesen Spieltag gibt es aktuell keinen 15K-Tipp."
        )
        detail = fake_streamlit.caption.call_args.args[0]
        self.assertIn("alle Voraussetzungen", detail)
        self.assertNotIn("Marktkandidaten", detail)
        self.assertNotIn("Walk-forward", detail)

    def test_unmapped_forecast_is_rendered_without_ticket_or_stake(self):
        fake_streamlit = MagicMock()
        unmappable = replace(
            candidate("2:HOME_RANGE_1_3", 2, 0.71),
            market_key="HOME_RANGE_1_3",
            market="Team 1 Gesamttore",
            selection="1-3 Tore",
        )
        snapshot = {
            "shortlist": [],
            "forecast_shortlist": [unmappable],
            "price_candidates": [],
            "reference_quotes": {},
        }

        with patch("challenge_15k.st", fake_streamlit):
            _render_price_check(snapshot, Mock(), {})

        visible_markdown = " ".join(
            str(call.args[0])
            for call in fake_streamlit.markdown.call_args_list
            if call.args
        )
        visible_info = " ".join(
            str(call.args[0])
            for call in fake_streamlit.info.call_args_list
            if call.args
        )
        self.assertIn("Team 1 Gesamttore", visible_markdown)
        self.assertIn("MODELL-AUSWAHL", visible_info)
        self.assertIn("keine exakt passende Vergleichsquote", visible_info)
        self.assertIn("kein Einsatz bewertet", visible_info)
        fake_streamlit.success.assert_not_called()

    def test_hidden_price_candidate_cannot_build_15k_ticket(self):
        fake_streamlit = MagicMock()
        visible = candidate("1:BTTS_YES", 1, 0.75)
        hidden = candidate("2:BTTS_YES", 2, 0.65)
        snapshot = {
            "shortlist": [],
            "forecast_shortlist": [visible],
            "price_candidates": [hidden],
            "reference_quotes": {},
        }

        with (
            patch("challenge_15k.st", fake_streamlit),
            patch(
                "challenge_15k._automatic_challenge_ticket",
                return_value=(None, {}),
            ) as ticket_builder,
        ):
            _render_price_check(snapshot, Mock(), {})

        self.assertEqual(ticket_builder.call_args.args[0], [])
        fake_streamlit.success.assert_not_called()

    def test_scan_diagnostics_separates_model_and_context_gates(self):
        transfer_only = candidate("1:BTTS", 1, 0.70)
        transfer_only.blocked_reasons = [UNVALIDATED_TRANSFER_REASON]
        transfer_only.context = {}
        multiply_blocked = candidate("2:BTTS", 2, 0.69)
        multiply_blocked.blocked_reasons = [
            UNVALIDATED_TRANSFER_REASON,
            "Markt hat das Walk-forward-Gate nicht bestanden",
        ]
        multiply_blocked.context = {}
        context_blocked = candidate("3:BTTS", 3, 0.68)
        context_blocked.context = {
            "passed": False,
            "blocked_reasons": ["Wetterdaten fehlen"],
        }

        diagnostics = _scan_candidate_diagnostics(
            [transfer_only, multiply_blocked, context_blocked]
        )

        self.assertEqual(diagnostics["market_candidates"], 3)
        self.assertEqual(diagnostics["configured_market_definitions"], len(MARKET_SPECS))
        self.assertEqual(diagnostics["modeled_market_definitions"], 1)
        self.assertEqual(
            diagnostics["model_blocked_counts"][UNVALIDATED_TRANSFER_REASON],
            2,
        )
        self.assertEqual(
            diagnostics["context_blocked_counts"]["Wetterdaten fehlen"],
            1,
        )
        self.assertEqual(diagnostics["transfer_only_candidates"], 1)
        self.assertEqual(diagnostics["transfer_only_fixtures"], 1)
        self.assertEqual(diagnostics["transfer_only_examples"][0]["fixture_id"], 1)

    def test_no_result_copy_does_not_claim_skipped_context_failed(self):
        headline, detail = scan_no_result_copy(
            {
                "fixtures_found": 38,
                "fixtures_modeled": 37,
                "market_candidates": 1480,
                "base_candidates": 0,
                "context_fixtures": 0,
            },
            day_label="Heute",
            recommendation_label="Markt-Empfehlung",
        )

        self.assertEqual(headline, "Heute keine belastbare Markt-Empfehlung.")
        self.assertIn("1480 Marktkandidaten", detail)
        self.assertIn("wurden deshalb nicht abgefragt", detail)

    def test_shortlist_keeps_only_one_market_per_game(self):
        markets = [
            candidate("1:BTTS", 1, 0.74),
            candidate("1:OVER_25", 1, 0.73),
            candidate("2:HOME_OVER_05", 2, 0.72),
            candidate("3:UNDER_35", 3, 0.71),
        ]

        shortlist = select_shortlist(markets, max_candidates=3)

        self.assertEqual(len(shortlist), 3)
        self.assertEqual([item.fixture_id for item in shortlist], [1, 2, 3])
        self.assertEqual(shortlist[0].candidate_id, "1:BTTS")

    def test_broad_safety_markets_are_basis_forecasts_not_top_selections(self):
        broad_keys = {
            "TOTAL_OVER_0_5",
            "TOTAL_UNDER_4_5",
            "HOME_OVER_0_5",
            "AWAY_OVER_0_5",
            "HOME_UNDER_2_5",
            "AWAY_UNDER_2_5",
            "HOME_RANGE_1_3",
            "AWAY_RANGE_1_3",
            "DC_1X",
            "MIXED_BTTS_OR_OVER_2_5",
            "CORNERS_OVER_5_5",
            "HOME_YELLOW_OVER_0_5",
        }
        for market_key in broad_keys:
            with self.subTest(market_key=market_key):
                self.assertTrue(market_is_basic_forecast(market_key))

        for market_key in {
            "RESULT_HOME",
            "BTTS_YES",
            "TOTAL_OVER_2_5",
            "HOME_OVER_1_5",
            "CORNERS_OVER_8_5",
            "YELLOW_OVER_2_5",
        }:
            with self.subTest(market_key=market_key):
                self.assertFalse(market_is_basic_forecast(market_key))

    def test_top_selection_excludes_trivial_high_probability_market(self):
        broad = replace(
            candidate("1:HOME_OVER_0_5", 1, 0.90),
            market_key="HOME_OVER_0_5",
            market="Team 1 Gesamttore",
            selection="Über 0.5",
        )
        useful = replace(
            candidate("2:BTTS_YES", 2, 0.66),
            market_key="BTTS_YES",
            market="Beide Teams treffen",
            selection="Ja",
        )

        self.assertEqual(select_forecast_shortlist([broad, useful]), [useful])
        self.assertEqual(select_basis_forecasts([broad, useful]), [broad])

    def test_context_summary_discloses_missing_inputs_without_blocking_price(self):
        item = candidate("1:BTTS_YES", 1, 0.70)
        item.context.update(
            {
                "h2h": {"status": "neutral"},
                "injuries": {"status": "observed"},
                "weather": {"status": "unavailable"},
                "lineups": {"status": "pending"},
            }
        )

        summary = candidate_context_summary(item)

        self.assertIn("H2H geprüft, kein belastbares Veto", summary)
        self.assertIn("Ausfälle berücksichtigt", summary)
        self.assertIn("Wetter nicht verfügbar", summary)
        self.assertIn("Aufstellungen noch offen", summary)

    def test_context_ranking_prefers_useful_market_over_trivial_probability(self):
        broad = replace(
            candidate("1:AWAY_UNDER_2_5", 1, 0.91),
            market_key="AWAY_UNDER_2_5",
            market="Team 2 Gesamttore",
            selection="Unter 2.5",
        )
        useful = replace(
            candidate("2:TOTAL_OVER_2_5", 2, 0.62),
            market_key="TOTAL_OVER_2_5",
            market="Gesamttore",
            selection="Über 2.5",
        )

        self.assertEqual(_ranked_fixture_ids([broad, useful], limit=1), [2])

    def test_oos_utility_ranks_two_core_markets_before_raw_probability(self):
        high_probability_low_skill = replace(
            candidate("1:RESULT_HOME", 1, 0.80),
            market_key="RESULT_HOME",
            validation=replace(
                candidate("validation-a", 91, 0.70).validation,
                relative_improvement=0.03,
            ),
        )
        lower_probability_high_skill = replace(
            candidate("2:BTTS_YES", 2, 0.65),
            market_key="BTTS_YES",
            validation=replace(
                candidate("validation-b", 92, 0.70).validation,
                relative_improvement=0.20,
            ),
        )

        selected = select_forecast_shortlist(
            [high_probability_low_skill, lower_probability_high_skill],
            max_candidates=2,
        )

        self.assertEqual(
            [item.candidate_id for item in selected],
            ["2:BTTS_YES", "1:RESULT_HOME"],
        )

    def test_public_catalog_is_diverse_and_never_filled_with_basis_markets(self):
        market_keys = [
            "RESULT_HOME",
            "RESULT_DRAW",
            "RESULT_AWAY",
            "BTTS_YES",
            "BTTS_NO",
            "BTTS_YES",
            "TOTAL_OVER_2_5",
            "TOTAL_UNDER_2_5",
            "TOTAL_OVER_3_5",
            "HOME_OVER_1_5",
            "AWAY_OVER_1_5",
            "HOME_UNDER_1_5",
            "CORNERS_OVER_8_5",
            "CORNERS_UNDER_8_5",
            "CORNERS_OVER_9_5",
            "HOME_OVER_0_5",
        ]
        pool = [
            replace(
                candidate(f"{index}:{market_key}", index, 0.80 - index / 200),
                market_key=market_key,
            )
            for index, market_key in enumerate(market_keys, start=1)
        ]

        selected = select_forecast_shortlist(pool, max_candidates=15)
        kinds = [MARKET_BY_KEY[item.market_key].kind for item in selected]

        self.assertEqual(len(selected), 15)
        self.assertEqual(len({item.fixture_id for item in selected}), 15)
        self.assertTrue(all(count <= 3 for count in Counter(kinds).values()))
        self.assertEqual(len(set(kinds[:3])), 3)
        self.assertNotIn("HOME_OVER_0_5", {item.market_key for item in selected})

    def test_diversity_prefill_never_exceeds_requested_maximum(self):
        market_keys = [
            "RESULT_HOME",
            "BTTS_YES",
            "TOTAL_OVER_2_5",
            "CORNERS_OVER_8_5",
        ]
        pool = [
            replace(
                candidate(f"{index}:{market_key}", index, 0.75),
                market_key=market_key,
            )
            for index, market_key in enumerate(market_keys, start=1)
        ]

        selected = select_forecast_shortlist(pool, max_candidates=3)

        self.assertEqual(len(selected), 3)

    def test_diversity_never_recreates_three_card_cap_for_one_market_kind(self):
        pool = [
            replace(
                candidate(f"{index}:BTTS_YES", index, 0.80 - index / 100),
                market_key="BTTS_YES",
            )
            for index in range(1, 11)
        ]

        selected = select_forecast_shortlist(pool, max_candidates=10)

        self.assertEqual(len(selected), 10)
        self.assertEqual(len({item.fixture_id for item in selected}), 10)

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
    def test_domestic_history_uses_current_league_and_drops_other_competitions(self):
        target_day = date(2026, 8, 4)
        kickoff = datetime(2026, 8, 4, 18, tzinfo=timezone.utc)
        domestic = [
            fixture(
                100 + index,
                kickoff - timedelta(days=10 + index),
                1,
                20 + index,
                2,
                1,
                league_id=113,
            )
            for index in range(6)
        ]
        other = fixture(
            999,
            kickoff - timedelta(days=2),
            1,
            2,
            1,
            1,
            league_id=2,
        )
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(
            side_effect=[
                [
                    {
                        "league": {"id": 113, "name": "Allsvenskan", "type": "League"},
                        "country": {"name": "Sweden"},
                        "seasons": [
                            {
                                "year": 2026,
                                "start": "2026-03-01",
                                "end": "2026-11-30",
                                "current": True,
                            }
                        ],
                    },
                    {
                        "league": {"id": 2, "name": "Champions League", "type": "Cup"},
                        "country": {"name": "World"},
                        "seasons": [{"year": 2026, "current": True}],
                    },
                ],
                domestic + [other],
            ]
        )

        result = provider.domestic_team_history(1, target_day, kickoff)

        self.assertEqual(result["league_id"], 113)
        self.assertEqual(result["season"], 2026)
        self.assertEqual(len(result["fixtures"]), 6)
        self.assertTrue(
            all(item["league"]["id"] == 113 for item in result["fixtures"])
        )

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

    @patch("challenge_15k.requests.get")
    def test_fixture_range_uses_one_inclusive_provider_request(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"errors": [], "response": []}
        get.return_value = response
        provider = ChallengeDataProvider("test-key", None)
        provider._rate_limit = lambda: None

        result = provider.upcoming_fixtures_range(
            39,
            2026,
            date(2026, 8, 5),
            date(2026, 8, 19),
        )

        self.assertEqual(result, [])
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["from"], "2026-08-05")
        self.assertEqual(params["to"], "2026-08-19")
        self.assertNotIn("date", params)

    @patch("challenge_15k.current_season_start_year_for_id")
    def test_range_is_split_at_a_provider_season_boundary(self, season_for_day):
        start = date(2030, 6, 29)
        season_for_day.side_effect = (
            lambda _league_id, day: 2029 if day < date(2030, 7, 1) else 2030
        )

        segments = _league_season_segments(
            39,
            start,
            date(2030, 7, 3),
        )

        self.assertEqual(
            segments,
            [
                (2029, date(2030, 6, 29), date(2030, 6, 30)),
                (2030, date(2030, 7, 1), date(2030, 7, 3)),
            ],
        )

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
            ([39], datetime.now().date(), MAX_SCAN_FIXTURES + 1),
        )
        for league_ids, search_date, max_fixtures in invalid_requests:
            with self.subTest(league_ids=league_ids, max_fixtures=max_fixtures):
                with self.assertRaises(ValueError):
                    scan_daily_challenge(provider, league_ids, search_date, max_fixtures)
        provider.upcoming_fixtures.assert_not_called()

        with self.assertRaises(ValueError):
            scan_daily_challenge(
                provider,
                [39],
                datetime.now().date(),
                8,
                search_end_date=datetime.now().date() + timedelta(days=15),
            )
        provider.upcoming_fixtures_range.assert_not_called()

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
        progress_updates = []

        snapshot = scan_daily_challenge(
            provider,
            [39],
            datetime.now().date(),
            8,
            progress_cb=lambda fraction, text: progress_updates.append(
                (fraction, text)
            ),
        )

        self.assertEqual(snapshot["fixtures_found"], 1)
        self.assertTrue(any("ungültige Einträge" in error for error in snapshot["errors"]))
        self.assertTrue(any("doppelter Provider-Eintrag" in error for error in snapshot["errors"]))
        fractions = [fraction for fraction, _text in progress_updates]
        self.assertGreaterEqual(len(fractions), 8)
        self.assertEqual(fractions, sorted(fractions))
        self.assertEqual(fractions[-1], 1.0)
        self.assertTrue(
            any("Liga 1/1" in text for _fraction, text in progress_updates)
        )
        self.assertTrue(
            any("modelliert" in text for _fraction, text in progress_updates)
        )

    def test_range_scan_fetches_each_league_once_and_keeps_window_scope(self):
        provider = Mock()
        provider.errors = []
        search_date = datetime.now().date()
        search_end_date = search_date + timedelta(days=7)
        upcoming = fixture(
            901,
            datetime.now(timezone.utc) + timedelta(days=1),
            10,
            11,
        )
        provider.upcoming_fixtures_range.return_value = [upcoming]
        provider.completed_history.return_value = []
        provider.coverage.return_value = {"injuries": True, "lineups": True}

        snapshot = scan_daily_challenge(
            provider,
            [39],
            search_date,
            8,
            search_end_date=search_end_date,
        )

        provider.upcoming_fixtures_range.assert_called_once_with(
            39,
            unittest.mock.ANY,
            search_date,
            search_end_date,
        )
        provider.upcoming_fixtures.assert_not_called()
        self.assertEqual(snapshot["fixtures_found"], 1)
        self.assertEqual(snapshot["search_date"], search_date.isoformat())
        self.assertEqual(snapshot["search_end_date"], search_end_date.isoformat())
        self.assertEqual(snapshot["scope"]["end_date"], search_end_date.isoformat())

    @patch("challenge_15k._cached_market_calibration", return_value={})
    @patch("challenge_15k._cached_market_validation")
    @patch("challenge_15k.annotate_history_xg", return_value={"coverage": 1.0})
    def test_uefa_scan_uses_domestic_team_history_for_sparse_qualifier(
        self,
        _annotate,
        validation,
        _calibration,
    ):
        target_day = date(2030, 8, 4)
        kickoff = datetime(2030, 8, 4, 18, tzinfo=timezone.utc)
        upcoming = fixture(900, kickoff, 1, 2, league_id=2)
        league_history = [
            fixture(
                1000 + index,
                kickoff - timedelta(days=200 - index),
                100 + index % 6,
                200 + index % 6,
                1 + index % 3,
                index % 2,
                league_id=2,
            )
            for index in range(30)
        ]
        home_history = [
            fixture(
                2000 + index,
                kickoff - timedelta(days=8 + index),
                1,
                300 + index,
                2,
                1,
                league_id=113,
            )
            for index in range(8)
        ]
        away_history = [
            fixture(
                3000 + index,
                kickoff - timedelta(days=8 + index),
                400 + index,
                2,
                1,
                1,
                league_id=332,
            )
            for index in range(8)
        ]
        validation.return_value = {
            spec.key: credible_validation()
            for spec in MARKET_SPECS
        }
        provider = Mock()
        provider.errors = []
        provider.upcoming_fixtures.return_value = [upcoming]
        provider.completed_history.return_value = league_history
        provider.coverage.return_value = {"injuries": False, "lineups": False}
        provider.domestic_team_history.side_effect = [
            {"league_id": 113, "season": 2026, "fixtures": home_history},
            {"league_id": 332, "season": 2026, "fixtures": away_history},
        ]
        provider.injuries_by_fixture.return_value = {900: []}
        provider.details_by_fixture.return_value = {900: upcoming}
        provider.h2h.return_value = []
        provider.weather.return_value = {
            "temperature_c": 20.0,
            "wind_kmh": 5.0,
            "precipitation_mm": 0.0,
        }

        snapshot = scan_daily_challenge(
            provider,
            [2],
            target_day,
            8,
        )

        self.assertEqual(snapshot["fixtures_found"], 1)
        self.assertEqual(snapshot["fixtures_modeled"], 1)
        self.assertEqual(snapshot["continental_fixtures_found"], 1)
        self.assertEqual(snapshot["continental_fallback_modeled"], 1)
        self.assertEqual(snapshot["continental_fallback_failed"], 0)
        self.assertEqual(snapshot["approved_candidates"], 0)
        self.assertGreater(snapshot["base_candidates"], 0)
        self.assertEqual(snapshot["context_fixtures"], 1)
        self.assertEqual(snapshot["continental_provisional_scope_fixtures"], 1)
        self.assertGreater(snapshot["forecast_candidates"], 0)
        self.assertEqual(snapshot["forecast_fixture_count"], 1)
        self.assertGreater(snapshot["provisional_forecast_candidates"], 0)
        self.assertEqual(snapshot["provisional_forecast_fixtures"], 1)
        self.assertEqual(len(snapshot["forecast_shortlist"]), 1)
        self.assertGreater(snapshot["price_candidate_count"], 0)
        self.assertEqual(snapshot["configured_market_definitions"], len(MARKET_SPECS))
        self.assertEqual(snapshot["modeled_market_definitions"], 40)
        self.assertGreater(snapshot["market_candidates"], 0)
        self.assertEqual(
            sum(item["configured"] for item in snapshot["market_coverage"]),
            len(MARKET_SPECS),
        )
        self.assertEqual(
            sum(item["modeled"] for item in snapshot["market_coverage"]),
            40,
        )
        self.assertTrue(snapshot["base_shortlist"])
        self.assertNotIn(UNVALIDATED_TRANSFER_REASON, snapshot["blocked_counts"])
        forecast = snapshot["forecast_shortlist"][0]
        self.assertEqual(
            forecast.model_scope,
            MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST,
        )
        self.assertTrue(candidate_is_forecast_credible(forecast))
        self.assertFalse(candidate_is_credible(forecast))
        self.assertFalse(forecast.context["release_eligible"])
        self.assertEqual(
            forecast.context["model_transfer"]["status"],
            "provisional",
        )
        self.assertIsNotNone(snapshot["context_checked_at"])
        self.assertTrue(
            all(
                not candidate.market_key.startswith(("CORNERS_", "YELLOW_"))
                for candidate in snapshot["base_shortlist"]
            )
        )

        provider.domestic_team_history.side_effect = [
            {"league_id": 113, "season": 2026, "fixtures": home_history},
            {"league_id": 332, "season": 2026, "fixtures": away_history},
        ]
        with patch(
            "challenge_15k._conservative_validation_map",
            return_value={},
        ):
            unvalidated = scan_daily_challenge(
                provider,
                [2],
                target_day,
                8,
            )

        self.assertEqual(unvalidated["base_candidates"], 0)
        self.assertEqual(unvalidated["forecast_shortlist"], [])
        self.assertGreater(
            unvalidated["blocked_counts"][UNVALIDATED_TRANSFER_REASON],
            0,
        )


class ChallengeContextTests(unittest.TestCase):
    def test_unvalidated_cross_competition_transfer_cannot_be_recommended(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )
        item.model_scope = MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED

        apply_candidate_context(
            item,
            h2h_fixtures=[],
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 18.0,
                "wind_mps": 2.0,
                "rain_3h_mm": 0.0,
                "snow_3h_mm": 0.0,
            },
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertFalse(item.context["passed"])
        self.assertEqual(item.context["model_transfer"]["status"], "blocked")
        self.assertIn(UNVALIDATED_TRANSFER_REASON, item.context["blocked_reasons"])
        self.assertFalse(candidate_is_forecast_credible(item))
        self.assertFalse(candidate_is_credible(item))

    def test_provisional_transfer_is_forecast_credible_but_never_tip_credible(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )
        item.model_scope = MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST

        apply_candidate_context(
            item,
            h2h_fixtures=None,
            injuries=None,
            injury_coverage=False,
            weather=None,
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertTrue(item.context["forecast_passed"])
        self.assertFalse(item.context["release_eligible"])
        self.assertTrue(item.forecast_eligible)
        self.assertFalse(item.eligible)
        self.assertTrue(candidate_is_forecast_credible(item))
        self.assertFalse(candidate_is_credible(item))
        self.assertEqual(item.context["model_transfer"]["status"], "provisional")
        self.assertEqual(item.context["h2h"]["status"], "unavailable")
        self.assertEqual(item.context["injuries"]["status"], "unavailable")
        self.assertEqual(item.context["weather"]["status"], "unavailable")
        item.context["release_eligible"] = True
        self.assertFalse(candidate_is_forecast_credible(item))
        self.assertFalse(candidate_is_credible(item))

    def test_h2h_provider_failure_is_explicit_unavailable_not_neutral(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )

        apply_candidate_context(
            item,
            h2h_fixtures=None,
            injuries=[],
            injury_coverage=True,
            weather=None,
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertTrue(candidate_is_forecast_credible(item))
        self.assertFalse(candidate_is_credible(item))
        self.assertFalse(item.context["release_context_complete"])
        self.assertFalse(item.context["release_eligible"])
        self.assertEqual(select_shortlist([item]), [])
        self.assertEqual(select_forecast_shortlist([item]), [item])
        quote = reference_quote_for(item, now)
        ticket, statuses = _automatic_challenge_ticket(
            [item],
            {item.candidate_id: quote},
            now=now,
        )
        self.assertEqual(statuses[item.candidate_id].code, "PLAYABLE")
        self.assertIsNone(ticket)
        self.assertEqual(item.context["h2h"]["status"], "unavailable")
        self.assertEqual(
            item.context["h2h"]["availability"],
            "provider_unavailable",
        )
        self.assertEqual(item.context["h2h"]["matches"], 0)

    def test_missing_release_flag_is_never_strictly_credible(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )
        apply_candidate_context(
            item,
            h2h_fixtures=[],
            injuries=[],
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 18.0,
                "wind_mps": 2.0,
                "rain_3h_mm": 0.0,
                "snow_3h_mm": 0.0,
            },
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertTrue(candidate_is_credible(item))
        item.context.pop("release_context_complete")
        self.assertTrue(candidate_is_forecast_credible(item))
        self.assertFalse(candidate_is_credible(item))
        item.context["release_context_complete"] = True
        item.context.pop("release_eligible")
        self.assertTrue(candidate_is_forecast_credible(item))
        self.assertFalse(candidate_is_credible(item))
        self.assertEqual(select_shortlist([item]), [])

    def test_raw_injury_counts_are_observed_but_never_a_veto(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )
        injuries = [
            {
                "team": {"id": 10},
                "player": {
                    "id": 100 + index,
                    "name": f"Player {index}",
                    "type": "Missing Fixture",
                },
            }
            for index in range(8)
        ]

        apply_candidate_context(
            item,
            h2h_fixtures=[],
            injuries=injuries,
            injury_coverage=True,
            weather={
                "status": "ok",
                "temperature_c": 18.0,
                "wind_mps": 2.0,
                "rain_3h_mm": 0.0,
                "snow_3h_mm": 0.0,
            },
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertTrue(candidate_is_credible(item))
        self.assertTrue(item.context["release_context_complete"])
        self.assertEqual(item.context["injuries"]["status"], "observed")
        self.assertEqual(item.context["injuries"]["home_missing"], 8)
        self.assertEqual(len(item.context["injuries"]["home_names"]), 8)
        self.assertEqual(item.context["injuries"]["material_vetoes"], [])

    def test_only_explicit_verified_material_injury_impact_can_veto(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )

        apply_candidate_context(
            item,
            h2h_fixtures=[],
            injuries=[
                {
                    "team": {"id": 10},
                    "player": {"id": 100, "name": "Key Player", "type": "Missing"},
                    "material_impact": {"verified": True, "veto": True},
                }
            ],
            injury_coverage=True,
            weather=None,
            lineups=None,
            now=now,
            require_lineups=False,
        )

        self.assertFalse(candidate_is_forecast_credible(item))
        self.assertEqual(item.context["injuries"]["status"], "blocked")
        self.assertEqual(item.context["injuries"]["material_vetoes"], ["Key Player"])

    def test_suppressive_extreme_weather_blocks_over_but_not_under(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        over = candidate(
            "1:TOTAL_OVER_2_5",
            1,
            0.70,
            kickoff=now + timedelta(hours=3),
        )
        over.market_key = "TOTAL_OVER_2_5"
        under = candidate(
            "2:TOTAL_UNDER_2_5",
            2,
            0.70,
            kickoff=now + timedelta(hours=3),
        )
        under.market_key = "TOTAL_UNDER_2_5"
        extreme = {
            "status": "ok",
            "temperature_c": 12.0,
            "wind_mps": 13.0,
            "rain_3h_mm": 7.0,
            "snow_3h_mm": 0.0,
        }
        for item in (over, under):
            apply_candidate_context(
                item,
                h2h_fixtures=[],
                injuries=[],
                injury_coverage=True,
                weather=extreme,
                lineups=None,
                now=now,
                require_lineups=False,
            )

        self.assertFalse(candidate_is_forecast_credible(over))
        self.assertEqual(over.context["weather"]["status"], "blocked")
        self.assertEqual(over.context["weather"]["market_effect"], "adverse")
        self.assertTrue(candidate_is_credible(under))
        self.assertEqual(under.context["weather"]["status"], "observed")
        self.assertEqual(under.context["weather"]["market_effect"], "aligned")
        self.assertFalse(under.context["weather"]["veto_applied"])

    def test_targeted_refresh_uses_only_persisted_candidate_fixtures(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(minutes=50),
        )
        item.context = {}

        class FixtureOnlyProvider:
            def __init__(self):
                self.errors = []

            def details_by_fixture(self, fixture_ids):
                self.fixture_ids = fixture_ids
                detail = fixture(
                    1,
                    now + timedelta(minutes=50),
                    10,
                    11,
                )
                detail["lineups"] = confirmed_lineups()
                return {1: detail}

            @staticmethod
            def injuries_by_fixture(fixture_ids):
                return {fixture_id: [] for fixture_id in fixture_ids}

            @staticmethod
            def coverage(_league_id, _season):
                return {"injuries": True, "lineups": True}

            @staticmethod
            def h2h(_home_team_id, _away_team_id):
                return [
                    fixture(
                        100 + index,
                        now - timedelta(days=30 + index),
                        10,
                        11,
                        1,
                        1,
                    )
                    for index in range(3)
                ]

            @staticmethod
            def weather(_fixture):
                return {
                    "status": "ok",
                    "temperature_c": 16,
                    "wind_mps": 2,
                    "rain_3h_mm": 0,
                    "snow_3h_mm": 0,
                }

        provider = FixtureOnlyProvider()
        result = refresh_discovered_candidates(
            provider,
            [item],
            now.date(),
            now=now,
        )

        self.assertEqual(provider.fixture_ids, [1])
        self.assertEqual(result["fixture_ids"], [1])
        self.assertEqual(len(result["shortlist"]), 1)
        self.assertTrue(result["shortlist"][0].eligible)

    def test_targeted_refresh_does_not_require_unpublished_lineups(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(hours=5),
        )
        provider = Mock()
        provider.errors = []
        provider.details_by_fixture.return_value = {
            1: fixture(1, now + timedelta(hours=5), 10, 11)
        }
        provider.injuries_by_fixture.return_value = {1: []}
        provider.coverage.return_value = {"injuries": True, "lineups": True}
        provider.h2h.return_value = [
            fixture(
                100 + index,
                now - timedelta(days=30 + index),
                10,
                11,
                1,
                1,
            )
            for index in range(3)
        ]
        provider.weather.return_value = {
            "status": "ok",
            "temperature_c": 16,
            "wind_mps": 2,
            "rain_3h_mm": 0,
            "snow_3h_mm": 0,
        }

        result = refresh_discovered_candidates(
            provider,
            [item],
            now.date(),
            now=now,
        )

        self.assertEqual(len(result["shortlist"]), 1)
        refreshed = result["shortlist"][0]
        self.assertTrue(refreshed.context["passed"])
        self.assertEqual(refreshed.context["lineups"]["status"], "pending")
        self.assertFalse(refreshed.context["lineups"]["required"])

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
            require_lineups=True,
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
            require_lineups=True,
        )

        self.assertFalse(item.eligible)
        self.assertIn(
            "Aufstellungen sind noch nicht verifiziert",
            item.context["blocked_reasons"],
        )

    def test_lineups_are_optional_without_explicit_opt_in(self):
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

    def test_missing_h2h_is_neutral_instead_of_blocking_candidate(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(days=1),
        )

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
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.context["h2h"]["status"], "neutral")
        self.assertEqual(item.context["h2h"]["matches"], 0)
        self.assertFalse(
            any("H2H" in reason for reason in item.context["blocked_reasons"])
        )

    def test_three_contradictory_h2h_matches_are_too_few_for_a_veto(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(days=1),
        )
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 0, 0)
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
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.context["h2h"]["status"], "neutral")
        self.assertEqual(item.context["h2h"]["matches"], 3)
        self.assertEqual(item.context["h2h"]["hits"], 0)

    def test_six_recent_strongly_contradictory_h2h_matches_veto(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(days=1),
        )
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 0, 0)
            for index in range(6)
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
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertFalse(item.eligible)
        self.assertEqual(item.context["h2h"]["status"], "blocked")
        self.assertLess(
            item.context["h2h"]["upper_confidence_bound"],
            item.context["h2h"]["veto_threshold"],
        )
        self.assertIn(
            "Aktuelles H2H widerspricht der Auswahl statistisch deutlich",
            item.context["blocked_reasons"],
        )

    def test_h2h_older_than_three_years_is_not_used_for_a_veto(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:BTTS",
            1,
            0.70,
            kickoff=now + timedelta(days=1),
        )
        h2h = [
            fixture(
                100 + index,
                now - timedelta(days=4 * 365 + index),
                10,
                11,
                0,
                0,
            )
            for index in range(6)
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
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.context["h2h"]["status"], "neutral")
        self.assertEqual(item.context["h2h"]["meetings_considered"], 0)

    def test_count_market_h2h_without_count_stats_is_neutral(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:CORNERS_OVER_9_5",
            1,
            0.70,
            kickoff=now + timedelta(days=1),
        )
        item.market_key = "CORNERS_OVER_9_5"
        h2h = [
            fixture(100 + index, now - timedelta(days=30 + index), 10, 11, 2, 1)
            for index in range(10)
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
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.context["h2h"]["status"], "neutral")
        self.assertEqual(item.context["h2h"]["meetings_considered"], 10)
        self.assertEqual(item.context["h2h"]["matches"], 0)

    def test_count_h2h_flips_historical_home_and_away_roles(self):
        now = datetime.now(timezone.utc)
        item = candidate(
            "1:HOME_CORNERS_OVER_5_5",
            1,
            0.70,
            kickoff=now + timedelta(days=1),
        )
        item.market_key = "HOME_CORNERS_OVER_5_5"
        h2h = [
            fixture(
                100 + index,
                now - timedelta(days=30 + index),
                11,
                10,
                1,
                2,
                stats={"corners_home": 2, "corners_away": 7},
            )
            for index in range(6)
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
            lineups=confirmed_lineups(),
            now=now,
        )

        self.assertTrue(item.eligible)
        self.assertEqual(item.context["h2h"]["status"], "passed")
        self.assertEqual(item.context["h2h"]["hits"], 6)

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
            require_lineups=True,
        )

        self.assertFalse(item.eligible)
        self.assertIn("Aufstellungen fehlen kurz vor Anpfiff", item.context["blocked_reasons"])


class ChallengeTicketTests(unittest.TestCase):
    def test_challenge_rejects_legs_below_practical_odds_floor(self):
        item = candidate("1:BTTS", 1, 0.95)

        self.assertEqual(item.minimum_odds, 1.25)
        self.assertIsNone(
            select_quoted_ticket(
                [item],
                {"1:BTTS": 1.24},
                odds_min=1.01,
                odds_max=3.0,
            )
        )
        self.assertIsNotNone(
            select_quoted_ticket(
                [item],
                {"1:BTTS": 1.25},
                odds_min=1.01,
                odds_max=3.0,
            )
        )

    def test_ticket_uses_at_most_three_unique_fixtures_and_target_odds(self):
        candidates = [
            candidate("1:BTTS", 1, 0.70),
            candidate("2:BTTS", 2, 0.69),
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
        self.assertAlmostEqual(ticket.model_dependency_factor, 0.95545)
        self.assertLess(ticket.joint_probability, 0.70 * 0.69)
        self.assertAlmostEqual(ticket.dependence_floor_probability, 0.39)

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
        second = candidate("2:BTTS", 2, 0.69)
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
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket_stake(ticket, 1000), 50.0)
        self.assertEqual(ticket_stake(ticket, 1000, 0.25), 250.0)
        capped_ticket = replace(ticket, stake_fraction=0.02)
        self.assertEqual(ticket_stake(capped_ticket, 101.25, 0.25), 25.31)
        self.assertEqual(kelly_reference_stake(capped_ticket, 101.25), 2.02)
        self.assertEqual(risk_managed_ticket_stake(capped_ticket, 101.25), 2.02)
        self.assertLess(expected_log_growth(ticket, 0.25), 0.0)
        self.assertEqual(challenge_stake_cap(100.05, 0.25), 25.01)
        self.assertEqual(challenge_stake_cap(100.06, 0.05), 5.0)

    def test_rollover_growth_projection_matches_target_math(self):
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 2.0, 0.25), 23)
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 3.0, 0.25), 13)
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 2.0, 0.10), 53)
        self.assertEqual(consecutive_wins_to_target(100, 15_000, 2.5, 0.01), 337)
        self.assertEqual(consecutive_wins_to_target(15_000, 15_000, 2.0, 0.25), 0)


class ChallengeLedgerTests(unittest.TestCase):
    def test_placed_ticket_has_verified_append_only_n1bet_price_ids(self):
        candidates = [
            candidate("1:BTTS", 1, 0.70),
            candidate("2:BTTS", 2, 0.69),
        ]
        ticket = select_quoted_ticket(
            candidates,
            {"1:BTTS": 1.50, "2:BTTS": 1.50},
        )
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id = ledger.place_ticket(
                "2026-07-14",
                ticket,
                ticket_stake(ticket, 100.0),
                datetime.now(timezone.utc).isoformat(),
            )
            stored = ledger.get_ticket(ticket_id)
            observation_ids = [
                leg["quote_observation_id"] for leg in stored["legs"]
            ]
            self.assertTrue(all(value > 0 for value in observation_ids))
            prices = PriceLedger(db_path)
            self.assertEqual(prices.verify_chain(), (True, None))
            self.assertEqual(
                [prices.get(value).bookmaker for value in observation_ids],
                ["N1Bet", "N1Bet"],
            )

    def test_ticket_rejects_quote_observation_from_another_candidate(self):
        candidates = [
            candidate("1:BTTS", 1, 0.70),
            candidate("2:BTTS", 2, 0.69),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            captured = datetime.now(timezone.utc)
            price_ledger = PriceLedger(db_path)
            observations = price_ledger.append_many(
                [
                    PriceQuote(
                        sport="FOOTBALL",
                        event_id=str(item.fixture_id),
                        event_name=f"{item.home_team} vs {item.away_team}",
                        scheduled_start=item.kickoff,
                        market_key=item.market_key,
                        market_name=item.market,
                        selection_key=item.candidate_id,
                        selection_name=item.selection,
                        decimal_odds=1.50,
                        captured_at=captured,
                    )
                    for item in candidates
                ],
                now=captured,
            )
            ticket = select_quoted_ticket(
                candidates,
                {"1:BTTS": 1.50, "2:BTTS": 1.50},
                quote_observation_ids={
                    "1:BTTS": observations[1].id,
                    "2:BTTS": observations[0].id,
                },
            )
            self.assertIsNotNone(ticket)
            with self.assertRaisesRegex(ValueError, "does not match"):
                ledger.place_ticket(
                    "2026-07-14",
                    ticket,
                    ticket_stake(ticket, 100.0),
                    captured.isoformat(),
                )

    def test_place_and_win_are_cent_accurate_and_idempotent(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
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

    def test_played_odds_drive_the_real_payout(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ledger.set_stake_fraction(0.25)
            ticket_id = ledger.place_ticket(
                "2026-07-14",
                ticket,
                25.0,
                datetime.now(timezone.utc).isoformat(),
                played_odds=2.40,
            )

            stored = ledger.get_ticket(ticket_id)
            self.assertEqual(stored["reference_total_odds"], 2.25)
            self.assertEqual(stored["total_odds"], 2.40)
            ledger.settle_ticket(ticket_id, "WON")
            self.assertEqual(ledger.settings()["current_balance"], 135.0)

    def test_manual_past_win_updates_balance_and_is_labeled(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")

            ticket_id = ledger.record_manual_result(
                "2026-07-13",
                "Frankreich vs Spanien: Über 5 Ecken",
                25.0,
                2.40,
                "WON",
            )

            stored = ledger.get_ticket(ticket_id)
            self.assertEqual(stored["entry_source"], "MANUAL")
            self.assertEqual(stored["status"], "WON")
            self.assertEqual(stored["payout"], 60.0)
            self.assertEqual(stored["legs"][0]["label"], "Frankreich vs Spanien: Über 5 Ecken")
            self.assertEqual(ledger.settings()["current_balance"], 135.0)
            self.assertEqual(
                sum(item["amount"] for item in ledger.transactions()),
                135.0,
            )

    def test_manual_result_respects_available_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")

            with self.assertRaisesRegex(ValueError, "available balance"):
                ledger.record_manual_result(
                    "2026-07-13",
                    "Zu hoher Einsatz",
                    100.01,
                    2.0,
                    "WON",
                )

    def test_fractional_cent_ui_cap_matches_ledger_floor(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ledger.set_balance(100.05)
            ledger.set_stake_fraction(0.25)
            maximum = challenge_stake_cap(
                ledger.settings()["current_balance"],
                ledger.settings()["stake_fraction"],
            )
            self.assertEqual(maximum, 25.01)
            with self.assertRaisesRegex(ValueError, "challenge limit"):
                ledger.place_ticket(
                    "2026-07-13",
                    ticket,
                    25.02,
                    datetime.now(timezone.utc).isoformat(),
                )
            ticket_id = ledger.place_ticket(
                "2026-07-13",
                ticket,
                maximum,
                datetime.now(timezone.utc).isoformat(),
            )
            self.assertGreater(ticket_id, 0)

    def test_only_one_non_void_ticket_per_day(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
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
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
        ticket = select_quoted_ticket(candidates, {"1:BTTS": 1.50, "2:BTTS": 1.50})
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ledger.set_stake_fraction(0.25)
            stake = ticket_stake(ticket, 100.0, 0.25)
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
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
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

    def test_ledger_cannot_bypass_three_percent_leg_value_gate(self):
        candidates = [
            candidate("1:BTTS", 1, 0.70),
            candidate("2:BTTS", 2, 0.80),
        ]
        legacy_ticket = select_quoted_ticket(
            candidates,
            {
                "1:BTTS": 1.025 / 0.70,
                "2:BTTS": 1.50,
            },
            minimum_leg_roi=0.02,
        )
        self.assertIsNotNone(legacy_ticket)
        self.assertLess(legacy_ticket.legs[0].expected_roi, 0.03)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            with self.assertRaisesRegex(ValueError, "value gate"):
                ledger.place_ticket(
                    "2026-07-14",
                    legacy_ticket,
                    ticket_stake(legacy_ticket, 100.0),
                    datetime.now(timezone.utc).isoformat(),
                )

    def test_legacy_database_migrates_to_capped_shadow_default(self):
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
                connection.execute(
                    """
                    CREATE TABLE challenge_tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        analysis_date TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        quote_verified_at TEXT NOT NULL,
                        settled_at TEXT,
                        status TEXT NOT NULL,
                        stake_cents INTEGER NOT NULL,
                        payout_cents INTEGER NOT NULL DEFAULT 0,
                        total_odds REAL NOT NULL,
                        joint_probability REAL NOT NULL,
                        expected_roi REAL NOT NULL,
                        legs_json TEXT NOT NULL
                    )
                    """
                )
                connection.commit()

            ledger = ChallengeLedger(db_path)

            self.assertEqual(ledger.settings()["stake_fraction"], 0.05)
            ledger.set_stake_fraction(0.25)
            self.assertEqual(ledger.settings()["stake_fraction"], 0.25)
            with closing(sqlite3.connect(db_path)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(challenge_tickets)"
                    )
                }
            self.assertIn("played_odds", columns)
            self.assertIn("entry_source", columns)

    def test_legacy_high_stake_policy_is_reset_and_defensively_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy-high-risk.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE challenge_settings (
                        id INTEGER PRIMARY KEY,
                        starting_balance_cents INTEGER NOT NULL,
                        current_balance_cents INTEGER NOT NULL,
                        target_balance_cents INTEGER NOT NULL,
                        stake_fraction_bps INTEGER NOT NULL DEFAULT 2500
                            CHECK (stake_fraction_bps BETWEEN 500 AND 10000),
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO challenge_settings
                    VALUES (1, 10000, 10000, 1500000, 9000, 'now')
                    """
                )
                connection.commit()

            ledger = ChallengeLedger(db_path)
            self.assertEqual(ledger.settings()["stake_fraction"], 0.05)

            # The legacy CHECK still permits 90%. Every read and money path
            # must nevertheless enforce the current hard maximum.
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "UPDATE challenge_settings SET stake_fraction_bps=9000 WHERE id=1"
                )
                connection.commit()
            self.assertEqual(ledger.settings()["stake_fraction"], 0.25)
            candidates = [
                candidate("1:BTTS", 1, 0.70),
                candidate("2:BTTS", 2, 0.69),
            ]
            ticket = select_quoted_ticket(
                candidates,
                {"1:BTTS": 1.50, "2:BTTS": 1.50},
            )
            self.assertIsNotNone(ticket)
            with self.assertRaisesRegex(ValueError, "challenge limit"):
                ledger.place_ticket(
                    "2026-07-13",
                    ticket,
                    25.01,
                    datetime.now(timezone.utc).isoformat(),
                )

    def test_transactions_reconcile_exactly_with_current_balance(self):
        candidates = [candidate("1:BTTS", 1, 0.70), candidate("2:BTTS", 2, 0.69)]
        ticket = select_quoted_ticket(
            candidates,
            {"1:BTTS": 1.50, "2:BTTS": 1.50},
        )
        self.assertIsNotNone(ticket)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            self.assertEqual(ledger.settings()["stake_fraction"], 0.05)
            stake = ticket_stake(ticket, 100.0)
            ticket_id = ledger.place_ticket(
                "2026-07-14",
                ticket,
                stake,
                datetime.now(timezone.utc).isoformat(),
            )
            ledger.settle_ticket(ticket_id, "LOST")
            ledger.set_balance(80.0)

            transactions = ledger.transactions()
            self.assertEqual(transactions[-1]["balance_after"], 80.0)
            self.assertEqual(
                sum(item["amount"] for item in transactions),
                ledger.settings()["current_balance"],
            )
            self.assertEqual(
                ledger.settings()["net_external_funding"],
                85.0,
            )


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
        candidate(f"{fid}:BTTS", fid, 0.70 - idx * 0.01)
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

    def test_lost_ticket_keeps_real_remaining_balance(self):
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
            self.assertEqual(summary["resets"], 0)
            self.assertEqual(ledger.get_ticket(ticket_id)["status"], "LOST")
            settings = ledger.settings()
            self.assertEqual(settings["current_balance"], 95.0)
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
    def test_periodic_recheck_rejects_oversized_league_scope(self):
        self.assertTrue(_auto_recheck_scope_allowed(list(range(1, 13))))
        self.assertFalse(_auto_recheck_scope_allowed(list(range(1, 14))))
        self.assertFalse(_auto_recheck_scope_allowed([]))

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


def _lineup_block(team_id, players=11):
    return {
        "team": {"id": team_id},
        "formation": "4-4-2",
        "coach": {"name": f"Coach {team_id}"},
        "startXI": [
            {"player": {"id": team_id * 100 + i, "name": f"Spieler {team_id}-{i}"}}
            for i in range(1, players + 1)
        ],
    }


class LineupDisplayTests(unittest.TestCase):
    def test_valid_lineups_extract_both_sides(self):
        from challenge_engine import extract_lineup_display

        display = extract_lineup_display([_lineup_block(10), _lineup_block(11)], 10, 11)
        self.assertEqual(set(display), {"home", "away"})
        self.assertEqual(display["home"]["formation"], "4-4-2")
        self.assertEqual(display["home"]["coach"], "Coach 10")
        self.assertEqual(len(display["home"]["starters"]), 11)
        self.assertEqual(display["away"]["starters"][0], "Spieler 11-1")

    def test_partial_and_invalid_data(self):
        from challenge_engine import extract_lineup_display

        one_side = extract_lineup_display([_lineup_block(10)], 10, 11)
        self.assertEqual(set(one_side), {"home"})
        forged = [
            {"team": {"id": team_id}, "startXI": [None] * 11}
            for team_id in (10, 11)
        ]
        self.assertEqual(extract_lineup_display(forged, 10, 11), {})
        self.assertEqual(extract_lineup_display(None, 10, 11), {})
        self.assertEqual(extract_lineup_display([_lineup_block(10, players=9)], 10, 11), {})
        duplicate = [_lineup_block(10), _lineup_block(10)]
        self.assertEqual(set(extract_lineup_display(duplicate, 10, 11)), {"home"})
        wrong = [_lineup_block(999), _lineup_block(998)]
        self.assertEqual(extract_lineup_display(wrong, 10, 11), {})


class _LineupProvider:
    """Provider-Double: liefert Fixture-Details mit Lineups, zählt Aufrufe."""

    def __init__(self, details):
        self._details = details
        self.requests = []

    def details_by_fixture(self, fixture_ids):
        self.requests.append(list(fixture_ids))
        return {fid: self._details.get(fid) for fid in fixture_ids}


class LineupRefreshTests(unittest.TestCase):
    def test_refresh_fills_missing_displays_without_touching_gates(self):
        from challenge_15k import _refresh_lineup_displays

        item = candidate("1:X", 1, 0.70)
        item.context = {"passed": True, "lineups": {"required": False, "display": {}}}
        snapshot = {"shortlist": [item]}
        provider = _LineupProvider(
            {1: {"fixture": {"id": 1}, "lineups": [_lineup_block(10), _lineup_block(11)]}}
        )

        updated = _refresh_lineup_displays(provider, snapshot)

        self.assertEqual(updated, 1)
        self.assertEqual(provider.requests, [[1]])
        display = item.context["lineups"]["display"]
        self.assertEqual(len(display["home"]["starters"]), 11)
        self.assertTrue(item.context["passed"])

    def test_refresh_skips_complete_candidates_without_api_call(self):
        from challenge_15k import _refresh_lineup_displays

        item = candidate("1:X", 1, 0.70)
        complete = {
            "home": {"formation": None, "coach": None, "starters": ["A"] * 11},
            "away": {"formation": None, "coach": None, "starters": ["B"] * 11},
        }
        item.context = {"passed": True, "lineups": {"display": complete}}
        provider = _LineupProvider({})

        updated = _refresh_lineup_displays(provider, {"shortlist": [item]})

        self.assertEqual(updated, 0)
        self.assertEqual(provider.requests, [])


class AutomaticReferenceTicketTests(unittest.TestCase):
    def test_fresh_multi_book_reference_builds_and_persists_ticket(self):
        now = datetime.now(timezone.utc)
        item = candidate("1:BTTS", 1, 0.60, kickoff=now + timedelta(days=1))
        quote = reference_quote_for(item, now)

        ticket, statuses = _automatic_challenge_ticket(
            [item],
            {item.candidate_id: quote},
            now=now,
        )

        self.assertIsNotNone(ticket)
        self.assertEqual(statuses[item.candidate_id].code, "PLAYABLE")
        self.assertEqual(ticket.legs[0].quote_source, quote.source)
        self.assertAlmostEqual(ticket.legs[0].odds, quote.conservative_odds)

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = ChallengeLedger(Path(tmpdir) / "challenge.db")
            ledger.set_stake_fraction(0.25)
            ticket_id = ledger.place_ticket(
                now.date().isoformat(),
                ticket,
                25.0,
                now.isoformat(),
            )
            stored = ledger.get_ticket(ticket_id)

        self.assertIsNone(stored["legs"][0]["quote_observation_id"])
        self.assertEqual(stored["legs"][0]["quote_source"], quote.source)
        self.assertEqual(stored["legs"][0]["bookmaker_count"], 4)

    def test_thin_reference_never_builds_15k_ticket(self):
        now = datetime.now(timezone.utc)
        item = candidate("1:BTTS", 1, 0.60, kickoff=now + timedelta(days=1))
        quote = reference_quote_for(item, now, odds=("2.10", "2.15"))

        ticket, statuses = _automatic_challenge_ticket(
            [item],
            {item.candidate_id: quote},
            now=now,
        )

        self.assertIsNone(ticket)
        self.assertEqual(statuses[item.candidate_id].code, "THIN")


if __name__ == "__main__":
    unittest.main()
