from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json

import market_consensus
import wettfinder_automation
from betting_math import BETTING_POLICY_VERSION
from challenge_engine import (
    MARKET_BY_KEY,
    MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST,
    MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
    ChallengeCandidate,
    ValidationMetrics,
    select_quoted_ticket,
)
from config_loader import AppConfig
from ev_signal_sources import (
    AUTOMATED_SELECTION_POLICY_VERSION,
    AUTOMATED_WETTFINDER_VERSION,
    ModelSignal,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
)
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from market_consensus import (
    MarketConsensus,
    ODDS_API_REFERENCE_SOURCE,
    QuotePoint,
    REFERENCE_SOURCE,
    exact_market_target,
    parse_h2h_event_consensus,
    parse_fixture_consensus,
)
from multi_sport_recommendations import ESPORTS_MODEL_VERSION
from riskobet_automation import SPORT_ORDER
from riskobet_domain import RiskRunSnapshot, RunStatus
from riskobet_store import FrozenRevisionError
from wettfinder_automation import (
    AUTOMATION_VERSION,
    _active_football_candidates,
    _apply_reference_quotes,
    _default_football_scan,
    _football_candidate_record,
    _football_state_from_snapshot,
    _merge_context_refresh,
    _signal_record,
    build_scheduled_challenge_snapshot,
    build_daily_forecast_catalog,
    build_model_selection_ledger,
    football_context_due_fixture_ids,
    football_due,
    load_state,
    riskobet_research_refresh_due,
    run_wettfinder,
    select_candidates,
    select_price_check_candidates,
    target_search_date,
)


UTC = timezone.utc


def test_apply_reference_quotes_rejects_wrong_market_fixture_and_source():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    row = {
        "candidate_id": "1:BTTS_YES",
        "fixture_id": 1,
        "market_key": "BTTS_YES",
        "sport": "Fussball",
        "source": "football_challenge",
        "minimum_odds": 1.80,
        "scheduled_start": (now + timedelta(hours=5)).isoformat(),
    }
    payload = {
        "errors": [],
        "response": [
            {
                "fixture": {
                    "id": 1,
                    "date": (now + timedelta(hours=5)).isoformat(),
                },
                "update": now.isoformat(),
                "bookmakers": [
                    {
                        "id": index,
                        "name": f"Book {index}",
                        "bets": [
                            {
                                "name": "Both Teams Score",
                                "values": [{"value": "Yes", "odd": "2.05"}],
                            }
                        ],
                    }
                    for index in range(1, 5)
                ],
            }
        ],
    }
    quote = parse_fixture_consensus(
        payload,
        [row],
        fetched_at=now,
    )[row["candidate_id"]]
    mismatches = (
        replace(quote, market_key="BTTS_NO"),
        replace(quote, fixture_id=2),
        replace(
            quote,
            source=ODDS_API_REFERENCE_SOURCE,
            provider_event_id="wrong-provider-event",
        ),
    )

    for mismatched in mismatches:
        model_row = dict(row)
        price_row = dict(row)
        counts, playable = _apply_reference_quotes(
            [model_row],
            [price_row],
            {row["candidate_id"]: mismatched},
            now=now,
        )

        assert counts == {"UNAVAILABLE": 1}
        assert playable == []
        assert model_row["reference_price_status"] == "UNAVAILABLE"
        assert "reference_quote" not in model_row


def test_apply_reference_quotes_keeps_name_only_legacy_visible_not_playable():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    row = {
        "candidate_id": "1:BTTS_YES",
        "fixture_id": 1,
        "market_key": "BTTS_YES",
        "sport": "Fussball",
        "source": "football_challenge",
        "selection": "Ja",
        "minimum_odds": 1.80,
        "scheduled_start": (now + timedelta(hours=5)).isoformat(),
    }
    payload = {
        "response": [{
            "fixture": {
                "id": 1,
                "date": row["scheduled_start"],
            },
            "update": now.isoformat(),
            "bookmakers": [
                {
                    "name": f"Legacy Book {index}",
                    "bets": [{
                        "name": "Both Teams Score",
                        "values": [{"value": "Yes", "odd": "2.05"}],
                    }],
                }
                for index in range(1, 5)
            ],
        }],
    }
    quote = parse_fixture_consensus(
        payload,
        [row],
        fetched_at=now,
    )[row["candidate_id"]]
    model_row = dict(row)
    price_row = dict(row)

    counts, playable = _apply_reference_quotes(
        [model_row],
        [price_row],
        {row["candidate_id"]: quote},
        now=now,
    )

    assert counts == {"UNAVAILABLE": 1}
    assert playable == []
    assert model_row["reference_quote"] == quote.to_dict()
    assert model_row["reference_price_status"] == "UNAVAILABLE"
    assert "reference_quote_executable_odds" not in model_row


def test_football_state_propagates_operational_failure_with_nonempty_schedule():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state = _football_state_from_snapshot(
        {
            "scanned_at": now.isoformat(),
            "fixtures_found": 5,
            "fixtures_modeled": 4,
            "errors": ["Liga 39 konnte nicht geladen werden"],
            "operational_errors": ["Liga 39 konnte nicht geladen werden"],
            "context_fixture_statuses": {},
        },
        attempted_at=now,
        search_date=now.date(),
    )

    assert state["status"] == "degraded"
    assert state["discovery_operational_error_count"] == 1
    assert state["operational_error_count"] == 1
    assert state["context_accounting_available"] is False


def test_discovery_timestamp_never_marks_unchecked_context_as_fresh():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    first = _challenge_candidate(now + timedelta(minutes=80))
    second = replace(
        first,
        fixture_id=2,
        candidate_id="fixture-2-btts",
    )
    state = _football_state_from_snapshot(
        {
            "scanned_at": now.isoformat(),
            "context_checked_at": (now - timedelta(minutes=2)).isoformat(),
            "base_fixture_count": 2,
            "context_verified_fixtures": 1,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 1,
            "deferred_context_fixtures": 0,
            "context_scope_complete": False,
            "context_fixture_statuses": {
                "1": "verified",
                "2": "unchecked",
            },
            "discovery_candidates": [first, second],
            "errors": [],
        },
        attempted_at=now,
        search_date=now.date(),
    )

    assert state["context_checks"] == {
        "1": (now - timedelta(minutes=2)).isoformat(),
    }
    assert football_context_due_fixture_ids(state, now=now) == [2]


def test_context_refresh_recomputes_coverage_from_per_fixture_statuses():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state = {
        "status": "completed",
        "candidates": [],
        "errors": [],
        "context_checks": {},
        "context_accounting_available": True,
        "context_fixture_statuses": {
            "1": "data_incomplete",
            "2": "verified",
        },
    }
    refreshed = _merge_context_refresh(
        state,
        {
            "context_fixture_statuses": {"1": "verified"},
            "operational_errors": [],
            "errors": [],
            "candidates": [],
        },
        fixture_ids=[1],
        checked_at=now,
    )

    assert refreshed["context_verified_fixtures"] == 2
    assert refreshed["context_data_incomplete_fixtures"] == 0
    assert refreshed["context_scope_complete"] is True
    assert refreshed["status"] == "completed"


def test_context_refresh_never_hides_discovery_failure():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state = {
        "status": "degraded",
        "last_discovery_at": None,
        "discovery_operational_error_count": 1,
        "context_operational_error_count": 0,
        "operational_error_count": 1,
        "candidates": [],
        "errors": ["Liga konnte nicht geladen werden"],
        "context_checks": {},
        "context_accounting_available": True,
        "context_fixture_statuses": {"1": "data_incomplete"},
    }

    refreshed = _merge_context_refresh(
        state,
        {
            "context_fixture_statuses": {"1": "verified"},
            "operational_errors": [],
            "errors": [],
            "candidates": [],
        },
        fixture_ids=[1],
        checked_at=now,
    )

    assert refreshed["context_scope_complete"] is True
    assert refreshed["discovery_operational_error_count"] == 1
    assert refreshed["operational_error_count"] == 1
    assert refreshed["status"] == "degraded"


def test_context_refresh_replaces_fixture_without_changing_catalog_order():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidates = []
    records = []
    for fixture_id in (1, 2, 3, 4):
        item = replace(
            _challenge_candidate(now + timedelta(hours=5)),
            fixture_id=fixture_id,
            candidate_id=f"fixture-{fixture_id}-btts",
            home_team=f"Home {fixture_id}",
            away_team=f"Away {fixture_id}",
        )
        item.context = {
            "passed": True,
            "forecast_passed": True,
            "release_context_complete": True,
            "release_eligible": True,
            "blocked_reasons": [],
        }
        candidates.append(item)
        records.append(_football_candidate_record(item, context_checked_at=now))
    refreshed_first = replace(candidates[0], probability=0.71)
    state = {
        "status": "completed",
        "candidates": records,
        "errors": [],
        "context_checks": {},
        "context_accounting_available": True,
        "context_fixture_statuses": {
            str(fixture_id): "verified" for fixture_id in (1, 2, 3, 4)
        },
    }

    refreshed = _merge_context_refresh(
        state,
        {
            "forecast_shortlist": [refreshed_first],
            "context_fixture_statuses": {"1": "verified"},
            "operational_errors": [],
            "errors": [],
        },
        fixture_ids=[1],
        checked_at=now + timedelta(minutes=30),
    )

    assert [row["fixture_id"] for row in refreshed["candidates"]] == [1, 2, 3, 4]
    assert refreshed["approved_candidates"] == 4


def test_context_refresh_reranks_new_stronger_fixture_without_truncating_pool():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    records = []
    statuses = {}
    for fixture_id in range(1, 16):
        item = replace(
            _challenge_candidate(now + timedelta(hours=5)),
            fixture_id=fixture_id,
            candidate_id=f"fixture-{fixture_id}-btts",
            home_team=f"Home {fixture_id}",
            away_team=f"Away {fixture_id}",
            validation=replace(
                _challenge_candidate(now + timedelta(hours=5)).validation,
                relative_improvement=0.20 - fixture_id / 1000,
            ),
        )
        item.context = {
            "passed": True,
            "forecast_passed": True,
            "release_context_complete": True,
            "release_eligible": True,
            "blocked_reasons": [],
        }
        records.append(_football_candidate_record(item, context_checked_at=now))
        statuses[str(fixture_id)] = "verified"

    stronger = replace(
        _challenge_candidate(now + timedelta(hours=5)),
        fixture_id=16,
        candidate_id="fixture-16-btts",
        home_team="Home 16",
        away_team="Away 16",
        validation=replace(
            _challenge_candidate(now + timedelta(hours=5)).validation,
            relative_improvement=0.30,
        ),
    )
    stronger.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "blocked_reasons": [],
    }
    statuses["16"] = "data_incomplete"
    state = {
        "status": "completed",
        "candidates": records,
        "errors": [],
        "context_checks": {},
        "context_accounting_available": True,
        "context_fixture_statuses": statuses,
    }

    refreshed = _merge_context_refresh(
        state,
        {
            "forecast_shortlist": [stronger],
            "context_fixture_statuses": {"16": "verified"},
            "operational_errors": [],
            "errors": [],
        },
        fixture_ids=[16],
        checked_at=now + timedelta(minutes=30),
    )

    fixture_ids = [row["fixture_id"] for row in refreshed["candidates"]]
    assert len(fixture_ids) == 16
    assert fixture_ids[0] == 16
    assert fixture_ids[1:] == list(range(1, 16))


def test_context_refresh_keeps_credible_basic_market_in_wettfinder_catalog():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    basic = replace(
        _challenge_candidate(now + timedelta(hours=5)),
        candidate_id="fixture-1-home-over-0-5",
        market_key="HOME_OVER_0_5",
        market="Team 1 Gesamttore",
        selection="Über 0.5",
    )
    basic.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "blocked_reasons": [],
    }
    state = {
        "status": "completed",
        "candidates": [],
        "errors": [],
        "context_checks": {},
        "context_accounting_available": True,
        "context_fixture_statuses": {"1": "data_incomplete"},
    }

    refreshed = _merge_context_refresh(
        state,
        {
            "forecast_shortlist": [],
            "candidates": [basic],
            "context_fixture_statuses": {"1": "verified"},
            "operational_errors": [],
            "errors": [],
        },
        fixture_ids=[1],
        checked_at=now + timedelta(minutes=30),
    )

    assert [row["candidate_id"] for row in refreshed["candidates"]] == [
        basic.candidate_id
    ]


def test_active_football_catalog_preserves_all_fifteen_positions():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    rows = []
    for fixture_id in range(1, 16):
        row = _candidate(
            f"football-{fixture_id}",
            probability=0.60 + fixture_id / 100,
            haircut=0.05,
            event=f"football-event-{fixture_id}",
        )
        row.update(
            sport="Fussball",
            fixture_id=fixture_id,
            market_key="BTTS_YES",
            source="football_challenge",
            context_checked_at=now.isoformat(),
        )
        rows.append(row)

    active = _active_football_candidates(
        {"candidates": rows},
        now=now,
        target_date=date(2030, 1, 1),
    )

    assert [row["fixture_id"] for row in active] == list(range(1, 16))


def _candidate(
    key: str,
    *,
    probability: float,
    haircut: float,
    event: str | None = None,
) -> dict:
    conservative = probability - haircut
    return {
        "key": key,
        "sport": "Tennis",
        "event": event or key,
        "event_identity": event or key,
        "label": key,
        "market": "Match Winner",
        "selection": key,
        "probability": probability,
        "probability_haircut": haircut,
        "conservative_probability": conservative,
        "minimum_odds": 2.0,
        "evidence_stage": "SHADOW",
        "policy_version": "test",
        "scheduled_start": "2030-01-01T20:00:00+00:00",
        "status": "PRICE_REQUIRED",
        "source": "test",
        "detail": "test",
    }


def _football_model_row(
    key: str,
    *,
    fixture_id: int,
    market_key: str,
    is_basic_forecast: bool,
    probability: float = 0.70,
) -> dict:
    row = _candidate(
        key,
        probability=probability,
        haircut=0.05,
        event=f"football-event-{fixture_id}",
    )
    row.update(
        candidate_id=key,
        sport="Fussball",
        fixture_id=fixture_id,
        market_key=market_key,
        market=market_key,
        selection=key,
        source="football_challenge",
        is_basic_forecast=is_basic_forecast,
        reference_price_status="UNAVAILABLE",
    )
    return row


def _football_snapshot(now: datetime) -> dict:
    candidate = _challenge_candidate(datetime(2030, 1, 1, 15, 0, tzinfo=UTC))
    candidate.context = {
        "passed": True,
        "blocked_reasons": [],
        "release_context_complete": True,
        "release_eligible": True,
    }
    return {
        "scanned_at": now.isoformat(),
        "fixtures_found": 2,
        "fixtures_modeled": 2,
        "base_candidates": 1,
        "base_fixture_count": 1,
        "context_fixtures": 1,
        "context_verified_fixtures": 1,
        "context_data_incomplete_fixtures": 0,
        "context_unchecked_fixtures": 0,
        "deferred_context_fixtures": 0,
        "context_scope_complete": True,
        "context_fixture_statuses": {"1": "verified"},
        "fixture_kickoffs": [
            "2030-01-01T15:00:00+00:00",
            "2030-01-01T18:00:00+00:00",
        ],
        "shortlist": [candidate],
        "errors": [],
    }


def _challenge_candidate(kickoff: datetime) -> ChallengeCandidate:
    validation = ValidationMetrics(
        300,
        0.15,
        0.20,
        0.25,
        0.04,
        True,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.06,
        paired_loss_mean=0.04,
        paired_loss_hac_standard_error=0.01,
        paired_loss_lower_confidence_bound=0.02,
        paired_loss_p_value=0.01,
        fdr_q_value=0.02,
        tested_hypotheses=90,
        statistical_release_passed=True,
    )
    return ChallengeCandidate(
        candidate_id="fixture-1-btts",
        fixture_id=1,
        league_id=39,
        league_name="Test League",
        kickoff=kickoff.isoformat(),
        home_team_id=10,
        away_team_id=11,
        home_team="FC Alpha",
        away_team="FC Beta",
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
        probability=0.72,
        conservative_probability=0.63,
        probability_haircut_pp=9.0,
        model_price=1.0 / 0.63,
        evidence_score=84.0,
        model_spread_pp=3.2,
        expected_home_goals=1.5,
        expected_away_goals=1.2,
        venue_samples=(10, 10),
        form_samples=(6, 6),
        validation=validation,
    )


def test_automation_writer_and_reader_share_one_artifact_version():
    assert AUTOMATION_VERSION == AUTOMATED_WETTFINDER_VERSION
    assert AUTOMATED_WETTFINDER_VERSION == 17
    assert AUTOMATED_SELECTION_POLICY_VERSION == "useful-selection-catalog-v14"


def test_football_record_persists_paired_statistical_release_evidence():
    candidate = _challenge_candidate(
        datetime(2030, 1, 1, 15, 0, tzinfo=UTC)
    )
    candidate.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "blocked_reasons": [],
    }

    record = _football_candidate_record(candidate)

    assert record is not None
    assert record["statistical_release_passed"] is True
    assert record["paired_loss_mean"] == 0.04
    assert record["paired_loss_hac_standard_error"] == 0.01
    assert record["paired_loss_lower_confidence_bound"] == 0.02
    assert record["paired_loss_p_value"] == 0.01
    assert record["fdr_q_value"] == 0.02
    assert record["tested_hypotheses"] == 90


def test_scheduled_artifact_rebuilds_15k_forecast_and_exact_quote(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    snapshot = _football_snapshot(now)
    candidate = snapshot["shortlist"][0]
    snapshot["discovery_candidates"] = [candidate]
    prices = (2.00, 2.05, 2.10, 2.15)
    quote = MarketConsensus(
        fixture_id=candidate.fixture_id,
        candidate_id=candidate.candidate_id,
        market_key=candidate.market_key,
        bet_name="Both Teams Score",
        value_name="Yes",
        consensus_odds=2.075,
        conservative_odds=2.0375,
        lowest_odds=2.00,
        best_odds=2.15,
        bookmaker_count=4,
        quoted_at=now.isoformat(),
        fetched_at=now.isoformat(),
        source=REFERENCE_SOURCE,
        points=tuple(
            QuotePoint(
                bookmaker=f"Book {index}",
                odds=odds,
                bookmaker_id=f"api-football:{index}",
                observed_at=now.isoformat(),
            )
            for index, odds in enumerate(prices, start=1)
        ),
        scheduled_start=candidate.kickoff,
        event_home=candidate.home_team,
        event_away=candidate.away_team,
    )

    artifact_path = tmp_path / "wettfinder.json"
    document = run_wettfinder(
        now=now,
        state_path=artifact_path,
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot,
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda _rows: (
            {candidate.candidate_id: quote},
            [],
        ),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )
    scope = {
        "league_ids": list(ALTERNATIVE_MARKET_LEAGUES),
        "date": now.date().isoformat(),
        "max_fixtures": 1200,
    }

    automatic = build_scheduled_challenge_snapshot(document, scope=scope)

    assert automatic is not None
    assert automatic["automatic_source"] == "wettfinder_systemd_timer"
    assert automatic["scope"] == scope
    assert [item.candidate_id for item in automatic["shortlist"]] == [
        candidate.candidate_id
    ]
    assert automatic["reference_quotes"][candidate.candidate_id] == quote.to_dict()
    assert build_scheduled_challenge_snapshot(
        document,
        scope={**scope, "date": "2030-01-02"},
    ) is None
    assert build_scheduled_challenge_snapshot(
        document,
        scope={**scope, "league_ids": [candidate.league_id]},
    ) is None
    assert build_scheduled_challenge_snapshot(
        {**document, "sources": ["corrupt"]},
        scope=scope,
    ) is None
    missing_release_pool = dict(document)
    missing_release_pool.pop("challenge_release_candidates")
    assert build_scheduled_challenge_snapshot(
        missing_release_pool,
        scope=scope,
    ) is None
    tampered_release_pool = json.loads(json.dumps(document))
    tampered_release_pool["challenge_release_candidates"][0][
        "release_contract"
    ] = "tampered"
    assert build_scheduled_challenge_snapshot(
        tampered_release_pool,
        scope=scope,
    ) is None


def test_scheduled_15k_uses_full_release_pool_not_normal_top_three(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    base = _challenge_candidate(now + timedelta(hours=5))
    candidates: list[ChallengeCandidate] = []
    odds_by_id: dict[str, float] = {}
    for index in range(1, 5):
        if index < 4:
            probability = 0.90
            conservative = 0.84
            evidence = 100.0 - index
            market_key = "BTTS_YES"
            odds = 1.25
        else:
            probability = 0.62
            conservative = 0.55
            evidence = 72.0
            market_key = "TOTAL_OVER_2_5"
            odds = 2.20
        spec = MARKET_BY_KEY[market_key]
        candidate = replace(
            base,
            candidate_id=f"fixture-{index}-{market_key}",
            fixture_id=index,
            home_team_id=index * 2 + 10,
            away_team_id=index * 2 + 11,
            home_team=f"Home {index}",
            away_team=f"Away {index}",
            market_key=market_key,
            market=spec.market,
            selection=spec.selection,
            probability=probability,
            conservative_probability=conservative,
            probability_haircut_pp=round(
                (probability - conservative) * 100.0,
                6,
            ),
            model_price=1.0 / conservative,
            evidence_score=evidence,
        )
        candidate.context = {
            "passed": True,
            "forecast_passed": True,
            "blocked_reasons": [],
            "release_context_complete": True,
            "release_eligible": True,
        }
        candidates.append(candidate)
        odds_by_id[candidate.candidate_id] = odds

    snapshot = {
        "scanned_at": now.isoformat(),
        "fixtures_found": 4,
        "fixtures_modeled": 4,
        "base_candidates": 4,
        "base_fixture_count": 4,
        "context_fixtures": 4,
        "context_verified_fixtures": 4,
        "context_data_incomplete_fixtures": 0,
        "context_unchecked_fixtures": 0,
        "deferred_context_fixtures": 0,
        "context_scope_complete": True,
        "context_fixture_statuses": {
            str(index): "verified" for index in range(1, 5)
        },
        "fixture_kickoffs": [candidate.kickoff for candidate in candidates],
        "shortlist": candidates,
        "discovery_candidates": candidates,
        "errors": [],
    }

    def quote(candidate: ChallengeCandidate) -> MarketConsensus:
        bet_name, value_name = exact_market_target(candidate.market_key) or (
            "",
            "",
        )
        odds = odds_by_id[candidate.candidate_id]
        return MarketConsensus(
            fixture_id=candidate.fixture_id,
            candidate_id=candidate.candidate_id,
            market_key=candidate.market_key,
            bet_name=bet_name,
            value_name=value_name,
            consensus_odds=odds,
            conservative_odds=odds,
            lowest_odds=odds,
            best_odds=odds,
            bookmaker_count=4,
            quoted_at=now.isoformat(),
            fetched_at=now.isoformat(),
            source=REFERENCE_SOURCE,
            points=tuple(
                QuotePoint(
                    bookmaker=f"Book {bookmaker}",
                    odds=odds,
                    bookmaker_id=f"api-football:{bookmaker}",
                    observed_at=now.isoformat(),
                )
                for bookmaker in range(1, 5)
            ),
            scheduled_start=candidate.kickoff,
            event_home=candidate.home_team,
            event_away=candidate.away_team,
        )

    artifact_path = tmp_path / "wettfinder.json"
    document = run_wettfinder(
        now=now,
        state_path=artifact_path,
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot,
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda _rows: (
            {
                candidate.candidate_id: quote(candidate)
                for candidate in candidates
            },
            [],
        ),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )
    automatic = build_scheduled_challenge_snapshot(document)

    assert len(document["candidates"]) == 3
    assert len(document["challenge_release_candidates"]) == 4
    assert len(
        automated_wettfinder_forecasts(
            artifact_path,
            now=now + timedelta(minutes=1),
        )
    ) == 4
    assert automatic is not None
    assert len(automatic["shortlist"]) == 4
    assert select_quoted_ticket(
        automatic["shortlist"],
        odds_by_id,
        now=now,
    ).legs[0].candidate.candidate_id == "fixture-4-TOTAL_OVER_2_5"


def test_completed_zero_forecast_run_is_a_valid_scheduled_15k_snapshot(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    snapshot = {
        "scanned_at": now.isoformat(),
        "fixtures_found": 12,
        "fixtures_modeled": 10,
        "base_candidates": 0,
        "base_fixture_count": 0,
        "context_fixtures": 0,
        "context_verified_fixtures": 0,
        "context_data_incomplete_fixtures": 0,
        "context_unchecked_fixtures": 0,
        "deferred_context_fixtures": 0,
        "context_scope_complete": True,
        "context_fixture_statuses": {},
        "fixture_kickoffs": [],
        "shortlist": [],
        "discovery_candidates": [],
        "errors": [],
    }
    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot,
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    automatic = build_scheduled_challenge_snapshot(document)

    assert automatic is not None
    assert automatic["automatic_run_status"] == "completed"
    assert automatic["fixtures_found"] == 12
    assert automatic["fixtures_modeled"] == 10
    assert automatic["forecast_shortlist"] == []
    assert automatic["shortlist"] == []


def test_scheduled_15k_never_promotes_a_model_quote_without_release_execution(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    snapshot = _football_snapshot(now)
    candidate = snapshot["shortlist"][0]
    snapshot["discovery_candidates"] = [candidate]
    prices = (2.00, 2.05, 2.10, 2.15)
    quote = MarketConsensus(
        fixture_id=candidate.fixture_id,
        candidate_id=candidate.candidate_id,
        market_key=candidate.market_key,
        bet_name="Both Teams Score",
        value_name="Yes",
        consensus_odds=2.075,
        conservative_odds=2.0375,
        lowest_odds=2.00,
        best_odds=2.15,
        bookmaker_count=4,
        quoted_at=now.isoformat(),
        fetched_at=now.isoformat(),
        source=REFERENCE_SOURCE,
        points=tuple(
            QuotePoint(
                bookmaker=f"Book {index}",
                odds=odds,
                observed_at=now.isoformat(),
            )
            for index, odds in enumerate(prices, start=1)
        ),
        scheduled_start=candidate.kickoff,
        event_home=candidate.home_team,
        event_away=candidate.away_team,
    )
    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot,
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda _rows: (
            {candidate.candidate_id: quote},
            [],
        ),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    automatic = build_scheduled_challenge_snapshot(
        document,
        scope={
            "league_ids": list(ALTERNATIVE_MARKET_LEAGUES),
            "date": now.date().isoformat(),
            "max_fixtures": 1200,
        },
    )

    assert document["candidates"] == []
    assert document["model_candidates"][0]["reference_price_status"] == "UNAVAILABLE"
    assert automatic is not None
    assert automatic["shortlist"] == []
    assert automatic["price_candidates"] == []
    assert [item.candidate_id for item in automatic["forecast_shortlist"]] == [
        candidate.candidate_id
    ]


def test_scheduled_artifact_keeps_forecast_but_blocks_release_on_degraded_source(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    snapshot = _football_snapshot(now)
    candidate = snapshot["shortlist"][0]
    snapshot["discovery_candidates"] = [candidate]
    snapshot["operational_errors"] = ["provider partial"]
    snapshot["errors"] = ["provider partial"]
    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot,
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    automatic = build_scheduled_challenge_snapshot(document)

    assert automatic is not None
    assert automatic["shortlist"] == []
    assert [item.candidate_id for item in automatic["forecast_shortlist"]] == [
        candidate.candidate_id
    ]


def test_previous_automation_artifact_version_is_rejected(tmp_path):
    state_path = tmp_path / "legacy-wettfinder.json"
    state_path.write_text(
        f'{{"version": {AUTOMATION_VERSION - 1}}}',
        encoding="utf-8",
    )

    assert load_state(state_path) == {}
    assert automated_wettfinder_forecasts(
        state_path,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    ) == []


def test_one_model_ledger_preserves_model_order_without_price_priority():
    strict_a = _candidate("strict-a", probability=0.66, haircut=0.05, event="A")
    strict_b = _candidate("strict-b", probability=0.64, haircut=0.05, event="B")
    forecast_same_event = _candidate(
        "forecast-a", probability=0.90, haircut=0.05, event="A"
    )
    forecast_c = _candidate("forecast-c", probability=0.80, haircut=0.05, event="C")
    forecast_d = _candidate("forecast-d", probability=0.79, haircut=0.05, event="D")

    ledger = build_model_selection_ledger(
        [strict_a, strict_b],
        [forecast_d, forecast_same_event, forecast_c],
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        target_date=date(2030, 1, 1),
    )

    assert [row["key"] for row in ledger] == [
        "forecast-d",
        "forecast-a",
        "forecast-c",
    ]
    assert all(row["status"] == "MODEL_SELECTION" for row in ledger)
    assert strict_a["status"] == "PRICE_REQUIRED"


def test_daily_catalog_reserves_space_for_tennis_and_esports():
    football = []
    for index in range(15):
        row = _candidate(
            f"football-{index}",
            probability=0.70,
            haircut=0.05,
            event=f"football-event-{index}",
        )
        row["sport"] = "Fussball"
        football.append(row)
    tennis = [
        _candidate(
            f"tennis-{index}",
            probability=0.68,
            haircut=0.05,
            event=f"tennis-event-{index}",
        )
        for index in range(4)
    ]
    esports = []
    for index in range(4):
        row = _candidate(
            f"esports-{index}",
            probability=0.66,
            haircut=0.05,
            event=f"esports-event-{index}",
        )
        row["sport"] = "E-Sport"
        esports.append(row)
    basis = [
        _football_model_row(
            "football-basic-overflow",
            fixture_id=99,
            market_key="HOME_OVER_0_5",
            is_basic_forecast=True,
        )
    ]

    catalog = build_daily_forecast_catalog(
        football,
        [*tennis, *esports],
        football_basis_rows=basis,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        target_date=date(2030, 1, 1),
    )

    assert [row["sport"] for row in catalog].count("Fussball") == 15
    assert [row["sport"] for row in catalog].count("Tennis") == 3
    assert [row["sport"] for row in catalog].count("E-Sport") == 3
    assert len(catalog) == 21


def test_daily_catalog_caps_repeated_basic_forecasts_without_banning_them():
    informative = [
        _football_model_row(
            f"informative-{index}",
            fixture_id=index,
            market_key=market_key,
            is_basic_forecast=False,
        )
        for index, market_key in enumerate(
            ("BTTS_YES", "TOTAL_OVER_2_5", "AWAY_UNDER_1_5"),
            start=1,
        )
    ]
    basis = [
        *[
            _football_model_row(
                f"home-over-{index}",
                fixture_id=10 + index,
                market_key="HOME_OVER_0_5",
                is_basic_forecast=True,
                probability=0.80 - index / 100,
            )
            for index in range(1, 7)
        ],
        *[
            _football_model_row(
                f"double-chance-{index}",
                fixture_id=20 + index,
                market_key="DC_1X",
                is_basic_forecast=True,
            )
            for index in range(1, 4)
        ],
        *[
            _football_model_row(
                f"home-under-{index}",
                fixture_id=30 + index,
                market_key="HOME_UNDER_2_5",
                is_basic_forecast=True,
            )
            for index in range(1, 3)
        ],
    ]

    catalog = build_daily_forecast_catalog(
        informative,
        [],
        football_basis_rows=basis,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        target_date=date(2030, 1, 1),
    )
    football = [row for row in catalog if row["sport"] == "Fussball"]
    simple = [row for row in football if row["is_basic_forecast"] is True]

    assert [row["key"] for row in football[:3]] == [
        row["key"] for row in informative
    ]
    assert len(football) == 7
    assert len(simple) == 4
    assert [row["key"] for row in simple] == [
        "home-over-1",
        "home-over-2",
        "double-chance-1",
        "double-chance-2",
    ]
    assert sum(row["market_key"] == "HOME_OVER_0_5" for row in simple) == 2


def test_daily_catalog_applies_fixture_cap_across_primary_and_basic_rows():
    primary = [
        _football_model_row(
            f"fixture-primary-{index}",
            fixture_id=1,
            market_key=f"PRIMARY_{index}",
            is_basic_forecast=False,
        )
        for index in range(1, 9)
    ]
    basis = [
        _football_model_row(
            f"fixture-basic-{index}",
            fixture_id=1,
            market_key=market_key,
            is_basic_forecast=True,
        )
        for index, market_key in enumerate(
            ("HOME_OVER_0_5", "DC_1X", "HOME_UNDER_2_5", "DC_X2"),
            start=1,
        )
    ]

    catalog = build_daily_forecast_catalog(
        primary,
        [],
        football_basis_rows=basis,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        target_date=date(2030, 1, 1),
    )

    assert [row["key"] for row in catalog] == [
        row["key"] for row in primary
    ]
    assert len(catalog) == 8


def test_daily_basic_catalog_is_independent_of_reference_price_status():
    basis = [
        _football_model_row(
            f"home-over-{index}",
            fixture_id=index,
            market_key="HOME_OVER_0_5",
            is_basic_forecast=True,
        )
        for index in range(1, 6)
    ]
    priced_basis = [dict(row) for row in basis]
    for row, status in zip(
        priced_basis,
        ("PLAYABLE", "TOO_LOW", "UNAVAILABLE", "THIN", "STALE"),
    ):
        row["reference_price_status"] = status

    kwargs = {
        "now": datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        "target_date": date(2030, 1, 1),
    }
    missing_price_catalog = build_daily_forecast_catalog(
        [], [], football_basis_rows=basis, **kwargs
    )
    mixed_price_catalog = build_daily_forecast_catalog(
        [], [], football_basis_rows=priced_basis, **kwargs
    )

    assert [row["key"] for row in missing_price_catalog] == [
        "home-over-1",
        "home-over-2",
    ]
    assert [row["key"] for row in mixed_price_catalog] == [
        row["key"] for row in missing_price_catalog
    ]


def test_runner_prices_full_model_pool_before_display_cap(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    kickoff = now + timedelta(hours=5)
    base = _challenge_candidate(kickoff)
    market_keys = (
        "BTTS_YES",
        "BTTS_NO",
        "TOTAL_OVER_2_5",
        "TOTAL_UNDER_3_5",
        "RESULT_HOME",
        "AWAY_UNDER_1_5",
        "CORNERS_OVER_8_5",
        "YELLOW_OVER_3_5",
    )
    model_pool = []
    for fixture_id in (1, 2):
        for market_key in market_keys:
            spec = MARKET_BY_KEY[market_key]
            candidate = replace(
                base,
                candidate_id=f"fixture-{fixture_id}-{market_key.lower()}",
                fixture_id=fixture_id,
                home_team_id=fixture_id * 10,
                away_team_id=fixture_id * 10 + 1,
                home_team=f"Home {fixture_id}",
                away_team=f"Away {fixture_id}",
                market_key=market_key,
                market=spec.market,
                selection=spec.selection,
            )
            candidate.context = {
                "passed": True,
                "forecast_passed": True,
                "release_context_complete": True,
                "release_eligible": True,
                "blocked_reasons": [],
            }
            model_pool.append(candidate)
    snapshot = {
        "scanned_at": now.isoformat(),
        "fixtures_found": 2,
        "fixtures_modeled": 2,
        "base_candidates": len(model_pool),
        "base_fixture_count": 2,
        "context_fixtures": 2,
        "context_verified_fixtures": 2,
        "context_data_incomplete_fixtures": 0,
        "context_unchecked_fixtures": 0,
        "deferred_context_fixtures": 0,
        "context_scope_complete": True,
        "context_fixture_statuses": {"1": "verified", "2": "verified"},
        "fixture_kickoffs": [kickoff.isoformat()],
        "wettfinder_candidates": model_pool,
        "discovery_candidates": model_pool,
        "errors": [],
    }
    priced_ids = []

    def quote_loader(rows):
        priced_ids.extend(row["candidate_id"] for row in rows)
        return {}, []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert len(priced_ids) == 16
    assert len(set(priced_ids)) == 16
    assert document["sources"]["football"]["price_checked_count"] == 16
    assert sum(
        row["source"] == "football_challenge"
        for row in document["model_candidates"]
    ) == 15


def test_persisted_model_signal_keeps_event_market_and_selection_separate():
    signal = ModelSignal(
        key="esports-1",
        label="CS2 · Alpha vs Beta · Sieg Alpha",
        probability=0.65,
        probability_haircut=0.05,
        evidence_stage="SHADOW",
        policy_version="test-policy",
        detail="Testmodell",
        scheduled_start="2030-01-01T15:00:00+00:00",
        minimum_odds=1.72,
        sport="E-Sport",
        event_label="CS2 · Alpha vs Beta",
        market="Match Winner",
        selection="Sieg Alpha",
    )

    record = _signal_record(signal)

    assert record is not None
    assert record["sport"] == "E-Sport"
    assert record["event"] == "CS2 · Alpha vs Beta"
    assert record["market"] == "Match Winner"
    assert record["selection"] == "Sieg Alpha"


def test_tennis_event_identity_deduplicates_legacy_keys_and_name_punctuation():
    signal = ModelSignal(
        key="tennis-a",
        label="Anna-Lena vs Bea",
        probability=0.65,
        probability_haircut=0.05,
        evidence_stage="SHADOW",
        policy_version="tennis-test",
        detail="Persistiertes Tennis-Modell",
        scheduled_start="2030-01-01T15:00:00+00:00",
        sport="Tennis",
        event_label="Anna-Lena vs Bea",
        market="Match Winner",
        selection="Sieg Anna-Lena",
        competitor_a="Anna-Lena",
        competitor_b="Bea",
        selected_competitor="Anna-Lena",
        competition="Winston-Salem",
    )
    legacy = replace(
        signal,
        key="tennis-b-legacy",
        event_label="Anna Lena vs Bea",
        competitor_a="Anna Lena",
        selected_competitor="Anna Lena",
        competition="Winston Salem",
    )
    corrected_time = replace(
        signal,
        key="tennis-c-corrected-time",
        scheduled_start="2030-01-01T15:05:00+00:00",
    )
    next_day = replace(
        signal,
        key="tennis-d-next-day",
        scheduled_start="2030-01-02T15:00:00+00:00",
    )
    rows = [
        _signal_record(item)
        for item in (signal, legacy, corrected_time, next_day)
    ]

    assert all(row is not None for row in rows)
    first, duplicate, corrected, tomorrow = rows
    assert first["event_identity"] == duplicate["event_identity"]
    assert first["event_identity"] == corrected["event_identity"]
    assert first["event_identity"] != tomorrow["event_identity"]
    selected = select_candidates(
        rows,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        target_date=date(2030, 1, 1),
    )
    assert [row["key"] for row in selected] == ["tennis-a"]


def test_target_date_keeps_late_same_day_fixtures_until_midnight():
    before = datetime(2030, 1, 1, 21, 59, tzinfo=UTC)
    after = datetime(2030, 1, 1, 22, 0, tzinfo=UTC)

    assert target_search_date(before) == date(2030, 1, 1)
    assert target_search_date(after) == date(2030, 1, 1)


def test_degraded_discovery_retries_on_the_next_half_hour_tick():
    previous = {
        "status": "degraded",
        "search_date": "2030-01-01",
        "last_attempt_at": "2030-01-01T10:00:00+00:00",
    }

    early = football_due(
        previous,
        now=datetime(2030, 1, 1, 10, 20, tzinfo=UTC),
        search_date=date(2030, 1, 1),
    )
    next_tick = football_due(
        previous,
        now=datetime(2030, 1, 1, 10, 30, tzinfo=UTC),
        search_date=date(2030, 1, 1),
    )

    assert early.due is False
    assert early.reason == "degraded_backoff"
    assert next_tick.due is True
    assert next_tick.reason == "retry_degraded_scan"


def test_football_discovery_runs_only_once_for_current_target_date():
    search_date = date(2030, 1, 1)
    previous = {
        "status": "completed",
        "search_date": search_date.isoformat(),
        "last_attempt_at": "2030-01-01T06:00:00+00:00",
        "fixture_kickoffs": ["2030-01-01T20:00:00+00:00"],
    }

    far = football_due(
        previous,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        search_date=search_date,
    )
    near = football_due(
        previous,
        now=datetime(2030, 1, 1, 18, 30, tzinfo=UTC),
        search_date=search_date,
    )

    assert far.due is False
    assert far.reason == "daily_discovery_current"
    assert near.due is False
    assert near.reason == "daily_discovery_current"


def test_context_due_uses_only_near_persisted_fixture_ids():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    near = _challenge_candidate(now + timedelta(minutes=80)).to_dict()
    far = _challenge_candidate(now + timedelta(hours=4)).to_dict()
    far["fixture_id"] = 2
    far["candidate_id"] = "fixture-2-btts"
    state = {
        "discovery_candidates": [near, far],
        "context_checks": {},
    }

    assert football_context_due_fixture_ids(state, now=now) == [1]

    state["context_checks"] = {"1": now.isoformat()}
    assert football_context_due_fixture_ids(
        state,
        now=now + timedelta(minutes=10),
    ) == []


def test_context_due_batches_cover_the_complete_near_kickoff_pool():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    discovery = []
    for fixture_id in range(1, 46):
        item = replace(
            _challenge_candidate(now + timedelta(minutes=80)),
            fixture_id=fixture_id,
            candidate_id=f"fixture-{fixture_id}-btts",
        )
        discovery.append(item.to_dict())
    state = {"discovery_candidates": discovery, "context_checks": {}}

    batches = []
    for _ in range(3):
        batch = football_context_due_fixture_ids(state, now=now)
        batches.append(batch)
        state["context_checks"].update(
            {str(fixture_id): now.isoformat() for fixture_id in batch}
        )

    assert [len(batch) for batch in batches] == [20, 20, 5]
    assert sorted(fixture_id for batch in batches for fixture_id in batch) == list(
        range(1, 46)
    )


def test_default_football_discovery_scans_all_configured_leagues(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "wettfinder_automation.ChallengeDataProvider",
        lambda *_args, **_kwargs: object(),
    )

    def fake_scan(
        _provider,
        league_ids,
        search_date,
        max_fixtures,
        *,
        allow_above_challenge_probability=False,
    ):
        captured.update(
            league_ids=league_ids,
            search_date=search_date,
            max_fixtures=max_fixtures,
            allow_above_challenge_probability=(
                allow_above_challenge_probability
            ),
        )
        return {}

    monkeypatch.setattr(
        "wettfinder_automation.scan_daily_challenge",
        fake_scan,
    )

    _default_football_scan(
        date(2030, 1, 2),
        AppConfig(api_football_key="test"),
    )

    assert captured["league_ids"] == list(ALTERNATIVE_MARKET_LEAGUES)
    assert len(captured["league_ids"]) == 51
    assert captured["allow_above_challenge_probability"] is True


def test_selection_is_probability_first_deduplicated_and_maximum_three():
    rows = [
        _candidate("low", probability=0.60, haircut=0.08),
        _candidate("best", probability=0.76, haircut=0.08),
        _candidate("same-event", probability=0.75, haircut=0.08, event="best"),
        _candidate("third", probability=0.69, haircut=0.07),
        _candidate("fourth", probability=0.68, haircut=0.07),
    ]
    selected = select_candidates(
        rows,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    )

    assert [row["key"] for row in selected] == ["best", "third", "fourth"]
    assert len(selected) == 3
    assert all("offered_odds" not in row for row in selected)


def test_selection_rejects_unknown_evidence_stage():
    row = _candidate("unknown", probability=0.75, haircut=0.08)
    row["evidence_stage"] = "TRUST_ME"

    assert select_candidates(
        [row],
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    ) == []


def test_selection_never_leaks_tomorrow_into_today_artifact():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    today = _candidate("today", probability=0.68, haircut=0.07)
    tomorrow = _candidate("tomorrow", probability=0.90, haircut=0.05)
    tomorrow["scheduled_start"] = "2030-01-02T08:00:00+00:00"

    selected = select_candidates(
        [tomorrow, today],
        now=now,
        target_date=date(2030, 1, 1),
    )

    assert [row["key"] for row in selected] == ["today"]


def test_price_pool_keeps_multiple_markets_for_the_same_fixture():
    rows = [
        _candidate("home-win", probability=0.78, haircut=0.08, event="match-1"),
        _candidate("under-4-5", probability=0.72, haircut=0.07, event="match-1"),
        _candidate("other", probability=0.68, haircut=0.07, event="match-2"),
    ]

    selected = select_price_check_candidates(
        rows,
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    )

    assert [row["key"] for row in selected] == [
        "home-win",
        "under-4-5",
        "other",
    ]


def test_runner_prices_first_ten_catalog_fixtures_by_model_utility(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    base = _challenge_candidate(now + timedelta(hours=5))
    catalog = []
    for fixture_id in range(1, 13):
        probability = 0.70 + fixture_id / 100.0
        candidate = replace(
            base,
            fixture_id=fixture_id,
            candidate_id=f"fixture-{fixture_id}-btts",
            home_team=f"Home {fixture_id}",
            away_team=f"Away {fixture_id}",
            probability=probability,
            conservative_probability=probability - 0.09,
            model_price=1.0 / (probability - 0.09),
            validation=replace(
                base.validation,
                relative_improvement=0.30 - fixture_id / 100.0,
            ),
        )
        candidate.context = {"passed": True, "blocked_reasons": []}
        catalog.append(candidate)

    def scan(_search_date):
        return {
            "scanned_at": now.isoformat(),
            "fixtures_found": 12,
            "fixtures_modeled": 12,
            "base_candidates": 12,
            "base_fixture_count": 12,
            "context_fixtures": 12,
            "context_verified_fixtures": 12,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 0,
            "deferred_context_fixtures": 0,
            "context_scope_complete": True,
            "context_fixture_statuses": {
                str(candidate.fixture_id): "verified" for candidate in catalog
            },
            "fixture_kickoffs": [candidate.kickoff for candidate in catalog],
            "forecast_shortlist": catalog,
            "shortlist": catalog,
            "errors": [],
        }

    checked_ids = []

    def quote_loader(rows):
        checked_ids.extend(row["fixture_id"] for row in rows)
        return {}, []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=scan,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert [row["fixture_id"] for row in document["model_candidates"]] == list(
        range(1, 13)
    )
    assert checked_ids == list(range(1, 11))


def test_football_record_rejects_unvalidated_cross_competition_model():
    candidate = _challenge_candidate(datetime(2030, 1, 1, 15, 0, tzinfo=UTC))
    candidate.context = {"passed": True, "blocked_reasons": []}
    candidate.model_scope = MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED

    assert _football_candidate_record(candidate) is None


def test_football_record_keeps_provisional_uefa_forecast_in_shadow():
    candidate = _challenge_candidate(datetime(2030, 1, 1, 15, 0, tzinfo=UTC))
    candidate.model_scope = MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
    candidate.context = {
        "passed": True,
        "forecast_passed": True,
        "release_eligible": False,
        "blocked_reasons": [],
        "model_transfer": {"status": "provisional"},
    }

    record = _football_candidate_record(candidate)

    assert record is not None
    assert record["evidence_stage"] == "SHADOW"
    assert record["model_scope"] == MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
    assert "Transfer-Prüfphase" in record["detail"]


def test_runner_reuses_persisted_models_and_skips_not_due_football(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state_path = tmp_path / "wettfinder.json"
    calls = 0

    def football_scan(_search_date):
        nonlocal calls
        calls += 1
        return _football_snapshot(now)

    tennis = ModelSignal(
        key="tennis-1-A",
        label="Tennis - A vs B - Sieg A",
        probability=0.66,
        probability_haircut=0.08,
        evidence_stage="SHADOW",
        policy_version="tennis-test",
        detail="Persistiertes Tennis-Modell",
        scheduled_start="2030-01-01T16:00:00+00:00",
    )

    first = run_wettfinder(
        now=now,
        state_path=state_path,
        config=AppConfig(api_football_key="test"),
        football_scanner=football_scan,
        tennis_loader=lambda **_kwargs: [tennis],
        esports_loader=lambda **_kwargs: [],
    )
    second = run_wettfinder(
        now=now + timedelta(minutes=10),
        state_path=state_path,
        config=AppConfig(api_football_key="test"),
        football_scanner=football_scan,
        tennis_loader=lambda **_kwargs: [tennis],
        esports_loader=lambda **_kwargs: [],
    )

    assert calls == 1
    assert first["bookmaker_data_used"] is False
    assert first["quote_required"] is True
    assert first["candidates"] == []
    assert {row["sport"] for row in first["model_candidates"]} == {
        "Fußball",
        "Tennis",
    }
    assert first["sources"]["football"]["price_status_counts"] == {
        "UNAVAILABLE": 1
    }
    assert second["sources"]["football"]["due_reason"] == "daily_discovery_current"
    assert load_state(state_path)["generated_at"] == second["generated_at"]


def test_runner_never_publishes_candidate_from_degraded_football_scan(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)

    def degraded_scan(_search_date):
        snapshot = _football_snapshot(now)
        snapshot["operational_errors"] = ["Eine Liga konnte nicht geladen werden"]
        snapshot["errors"] = list(snapshot["operational_errors"])
        return snapshot

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=degraded_scan,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert document["football"]["status"] == "degraded"
    assert document["football"]["operational_error_count"] == 1
    assert document["sources"]["football"]["candidate_count"] == 1
    assert document["sources"]["football"]["price_checked_count"] == 1
    assert document["candidates"] == []
    assert [row["sport"] for row in document["model_candidates"]] == ["Fußball"]


def test_runner_prices_verified_fixture_even_when_later_fixtures_are_unchecked(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidate = _challenge_candidate(now + timedelta(hours=5))
    candidate.context = {"passed": True, "blocked_reasons": []}
    statuses = {"1": "verified"}
    statuses.update({str(index): "unchecked" for index in range(2, 22)})

    def scan(_search_date):
        return {
            "scanned_at": now.isoformat(),
            "fixtures_found": 21,
            "fixtures_modeled": 21,
            "base_candidates": 21,
            "base_fixture_count": 21,
            "context_fixtures": 1,
            "context_verified_fixtures": 1,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 20,
            "deferred_context_fixtures": 0,
            "context_scope_complete": False,
            "context_fixture_statuses": statuses,
            "fixture_kickoffs": [candidate.kickoff],
            "shortlist": [candidate],
            "errors": [],
        }

    checked = []

    def quote_loader(rows):
        checked.extend(row["fixture_id"] for row in rows)
        return {}, []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=scan,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert checked == [1]
    assert document["football"]["context_scope_complete"] is False
    assert document["sources"]["football"]["price_checked_count"] == 1


def test_runner_persists_automatic_reference_quote_for_football_tip(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state_path = tmp_path / "wettfinder.json"

    def quote_loader(rows):
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": name,
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [{"value": "Yes", "odd": odds}],
                                }
                            ],
                        }
                        for index, (name, odds) in enumerate(
                            (
                                ("Book A", "1.90"),
                                ("Book B", "1.95"),
                                ("Book C", "2.00"),
                                ("Book D", "2.05"),
                            ),
                            start=1,
                        )
                    ],
                }
            ]
        }
        return parse_fixture_consensus(payload, rows, fetched_at=now), []

    document = run_wettfinder(
        now=now,
        state_path=state_path,
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _search_date: _football_snapshot(now),
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert document["bookmaker_data_used"] is True
    assert document["sources"]["football"]["reference_quote_count"] == 1
    tip = document["candidates"][0]
    model_selection = document["model_candidates"][0]
    assert document["quote_required"] is True
    assert tip["status"] == "RECOMMENDED"
    assert tip["evidence_stage"] == "RELEASED"
    assert tip["release_contract"] == "football-hac-fdr-context-price-v1"
    assert model_selection["status"] == "MODEL_SELECTION"
    assert model_selection["evidence_stage"] == "SHADOW"
    assert model_selection["candidate_id"] == tip["candidate_id"]
    assert tip["reference_price_status"] == "PLAYABLE"
    assert model_selection["reference_price_status"] == "PLAYABLE"
    assert tip["reference_quote"]["bookmaker_count"] == 4
    assert tip["reference_quote"]["conservative_odds"] == 1.9375
    assert tip["reference_quote_executable_odds"] == 1.95
    assert tip["reference_quote_bookmaker"] == "Book B"
    assert tip["reference_quote_bookmaker_id"] == "api-football:2"
    assert tip["reference_quote_observed_at"] == now.isoformat()
    assert tip["reference_quote_source"] == REFERENCE_SOURCE
    assert model_selection["reference_quote_executable_odds"] == 1.95
    read_at = now + timedelta(minutes=30)
    forecasts = automated_wettfinder_forecasts(state_path, now=read_at)
    signals = automated_wettfinder_signals(state_path, now=read_at)
    assert [row.key for row in forecasts] == [model_selection["key"]]
    assert [row.key for row in signals] == [tip["key"]]
    assert signals[0].evidence_stage == "RELEASED"

    tampered = json.loads(state_path.read_text(encoding="utf-8"))
    tampered["candidates"][0]["release_contract"] = "unreviewed-release"
    state_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert automated_wettfinder_signals(state_path, now=read_at) == []


def test_runner_never_publishes_unpriced_or_too_low_model_candidates(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    level_up = ModelSignal(
        key="esports-level-up",
        label="DOTA2 · Level UP vs Team Lynx · Sieg Level UP",
        probability=0.6815,
        probability_haircut=0.2572,
        evidence_stage="SHADOW",
        policy_version=f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}",
        detail="E-Sport-Pre-Match-Modell · Shadow",
        scheduled_start="2030-01-01T18:00:00+00:00",
        sport="E-Sport",
        event_label="DOTA2 · Level UP vs Team Lynx",
        market="Match Winner",
        selection="Sieg Level UP",
    )

    def too_low_loader(rows):
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": name,
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [{"value": "Yes", "odd": odds}],
                                }
                            ],
                        }
                        for index, (name, odds) in enumerate(
                            (
                                ("Book A", "1.20"),
                                ("Book B", "1.22"),
                                ("Book C", "1.24"),
                                ("Book D", "1.26"),
                            ),
                            start=1,
                        )
                    ],
                }
            ]
        }
        return parse_fixture_consensus(payload, rows, fetched_at=now), []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _search_date: _football_snapshot(now),
        football_quote_loader=too_low_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [level_up],
    )

    assert document["candidates"] == []
    assert {row["sport"] for row in document["model_candidates"]} == {
        "Fußball",
        "E-Sport",
    }
    football_model = next(
        row for row in document["model_candidates"] if row["sport"] == "Fußball"
    )
    assert football_model["reference_price_status"] == "TOO_LOW"
    assert football_model["reference_quote"]["bookmaker_count"] == 4
    assert document["bookmaker_data_used"] is True
    assert document["sources"]["football"]["price_status_counts"] == {
        "TOO_LOW": 1
    }
    assert document["sources"]["esports"]["candidate_count"] == 1


def test_runner_keeps_unmapped_forecast_out_of_quote_provider(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    unmapped = replace(
        _challenge_candidate(now + timedelta(hours=5)),
        candidate_id="fixture-1-result-total",
        market_key="RESULT_TOTAL_1X_UNDER_3_5",
        market="Resultat & Tore",
        selection="1X & Unter 3.5",
    )
    unmapped.context = {"passed": True, "blocked_reasons": []}

    def scan(_search_date):
        return {
            "scanned_at": now.isoformat(),
            "fixtures_found": 1,
            "fixtures_modeled": 1,
            "base_candidates": 1,
            "base_fixture_count": 1,
            "context_fixtures": 1,
            "context_verified_fixtures": 1,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 0,
            "deferred_context_fixtures": 0,
            "context_scope_complete": True,
            "context_fixture_statuses": {"1": "verified"},
            "fixture_kickoffs": [unmapped.kickoff],
            "shortlist": [unmapped],
            "forecast_shortlist": [unmapped],
            "errors": [],
        }

    quote_calls = []

    def quote_loader(rows):
        quote_calls.append(list(rows))
        return {}, []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=scan,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert quote_calls == []
    assert [
        row["candidate_id"] for row in document["model_candidates"]
    ] == ["fixture-1-result-total"]
    assert document["model_candidates"][0]["reference_price_status"] == (
        "UNAVAILABLE"
    )
    assert document["sources"]["football"]["price_checked_count"] == 0
    assert document["candidates"] == []


def test_runner_keeps_checked_catalog_beyond_featured_top_three(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    base = _challenge_candidate(now + timedelta(hours=5))
    shortlist = []
    for fixture_id, probability in ((1, 0.82), (2, 0.78), (3, 0.74), (4, 0.70)):
        candidate = replace(
            base,
            fixture_id=fixture_id,
            candidate_id=f"fixture-{fixture_id}-btts",
            home_team=f"Home {fixture_id}",
            away_team=f"Away {fixture_id}",
            probability=probability,
            conservative_probability=probability - 0.09,
            model_price=1.0 / (probability - 0.09),
        )
        candidate.context = {
            "passed": True,
            "blocked_reasons": [],
            "release_context_complete": True,
            "release_eligible": True,
        }
        shortlist.append(candidate)

    def scan(_search_date):
        return {
            "scanned_at": now.isoformat(),
            "fixtures_found": 4,
            "fixtures_modeled": 4,
            "base_candidates": 4,
            "base_fixture_count": 4,
            "context_fixtures": 4,
            "context_verified_fixtures": 4,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 0,
            "deferred_context_fixtures": 0,
            "context_scope_complete": True,
            "context_fixture_statuses": {
                str(candidate.fixture_id): "verified" for candidate in shortlist
            },
            "fixture_kickoffs": [candidate.kickoff for candidate in shortlist],
            "shortlist": shortlist,
            "errors": [],
        }

    checked_ids = []

    def quote_loader(rows):
        checked_ids.extend(row["fixture_id"] for row in rows)
        target = next(row for row in rows if row["fixture_id"] == 4)
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 4,
                        "date": target["scheduled_start"],
                    },
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": f"Book {index}",
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [{"value": "Yes", "odd": "1.90"}],
                                }
                            ],
                        }
                        for index in range(1, 5)
                    ],
                }
            ]
        }
        return parse_fixture_consensus(payload, [target], fetched_at=now), []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=scan,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert checked_ids == [1, 2, 3, 4]
    assert [row["fixture_id"] for row in document["model_candidates"]] == [
        1,
        2,
        3,
        4,
    ]
    assert [row["fixture_id"] for row in document["candidates"]] == [4]
    assert document["candidates"][0]["reference_price_status"] == "PLAYABLE"


def test_runner_prices_and_keeps_alternative_market_from_same_fixture(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    base = _challenge_candidate(now + timedelta(hours=5))
    home_win = replace(
        base,
        candidate_id="fixture-1-home",
        market_key="RESULT_HOME",
        market="Endergebnis",
        selection="FC Alpha",
        probability=0.82,
        conservative_probability=0.73,
        model_price=1.0 / 0.73,
    )
    under_goals = replace(
        base,
        candidate_id="fixture-1-under-4-5",
        market_key="TOTAL_UNDER_4_5",
        market="Gesamttore",
        selection="Unter 4,5",
        probability=0.78,
        conservative_probability=0.69,
        model_price=1.0 / 0.69,
    )
    for item in (home_win, under_goals):
        item.context = {
            "passed": True,
            "forecast_passed": True,
            "release_context_complete": True,
            "release_eligible": True,
            "blocked_reasons": [],
        }

    def scan(_search_date):
        return {
            "scanned_at": now.isoformat(),
            "fixtures_found": 1,
            "fixtures_modeled": 1,
            "base_candidates": 2,
            "base_fixture_count": 1,
            "context_fixtures": 1,
            "context_verified_fixtures": 1,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 0,
            "deferred_context_fixtures": 0,
            "context_scope_complete": True,
            "context_fixture_statuses": {"1": "verified"},
            "fixture_kickoffs": [home_win.kickoff],
            "shortlist": [home_win, under_goals],
            "errors": [],
        }

    checked_rows = []

    def quote_loader(rows):
        checked_rows.extend(rows)
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": f"Book {index}",
                            "bets": [
                                {
                                    "name": "Match Winner",
                                    "values": [
                                        {"value": "Home", "odd": "1.25"}
                                    ],
                                },
                                {
                                    "name": "Goals Over/Under",
                                    "values": [
                                        {"value": "Under 4.5", "odd": "1.80"}
                                    ],
                                },
                            ],
                        }
                        for index in range(1, 5)
                    ],
                }
            ]
        }
        return parse_fixture_consensus(payload, rows, fetched_at=now), []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=scan,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert [row["candidate_id"] for row in checked_rows] == [
        "fixture-1-home",
        "fixture-1-under-4-5",
    ]
    assert document["sources"]["football"]["price_checked_count"] == 2
    assert document["sources"]["football"]["price_fixture_count"] == 1
    assert document["sources"]["football"]["price_status_counts"] == {
        "TOO_LOW": 1,
        "PLAYABLE": 1,
    }
    assert [row["candidate_id"] for row in document["model_candidates"]] == [
        "fixture-1-home",
        "fixture-1-under-4-5",
    ]
    assert [row["candidate_id"] for row in document["candidates"]] == [
        "fixture-1-under-4-5"
    ]


def test_runner_refreshes_runtime_clock_after_a_long_discovery(tmp_path):
    started = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    scanned = started + timedelta(minutes=12)
    context_done = scanned + timedelta(seconds=1)
    completed = scanned + timedelta(minutes=1)
    moments = iter((started, scanned, context_done, completed))

    def clock():
        return next(moments)

    snapshot = _football_snapshot(scanned)
    checked_rows = []

    def quote_loader(rows):
        checked_rows.extend(rows)
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": scanned.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": f"Book {index}",
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [
                                        {"value": "Yes", "odd": "1.95"}
                                    ],
                                }
                            ],
                        }
                        for index in range(1, 5)
                    ],
                }
            ]
        }
        return parse_fixture_consensus(
            payload,
            rows,
            fetched_at=context_done,
        ), []

    document = run_wettfinder(
        clock=clock,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _search_date: snapshot,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert len(checked_rows) == 1
    assert document["generated_at"] == completed.isoformat()
    assert document["sources"]["football"]["price_checked_count"] == 1
    assert document["sources"]["football"]["price_fixture_count"] == 1


def test_runner_refreshes_only_daily_pool_fixture_without_rescanning(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state_path = tmp_path / "wettfinder.json"
    scan_calls = 0
    refresh_calls = []
    pool_candidate = _challenge_candidate(now + timedelta(minutes=80))

    def football_scan(_search_date):
        nonlocal scan_calls
        scan_calls += 1
        return {
            "scanned_at": now.isoformat(),
            "fixtures_found": 1,
            "fixtures_modeled": 1,
            "base_candidates": 2,
            "base_fixture_count": 1,
            "context_fixtures": 0,
            "context_verified_fixtures": 0,
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 1,
            "deferred_context_fixtures": 0,
            "context_scope_complete": False,
            "context_fixture_statuses": {"1": "unchecked"},
            "blocked_counts": {"Transfer nicht validiert": 4},
            "continental_fixtures_found": 1,
            "continental_fallback_modeled": 1,
            "continental_fallback_failed": 0,
            "fixture_kickoffs": [pool_candidate.kickoff],
            "shortlist": [],
            "discovery_candidates": [pool_candidate],
            "errors": [],
        }

    def context_refresh(candidates, _search_date, checked_at):
        refresh_calls.append(
            ([candidate.fixture_id for candidate in candidates], checked_at)
        )
        for item in candidates:
            item.context = {"passed": True, "blocked_reasons": []}
        return {
            "shortlist": candidates[:1],
            "context_fixture_statuses": {"1": "verified"},
            "operational_errors": [],
            "errors": [],
            "blocked_counts": {},
        }

    common = {
        "state_path": state_path,
        "config": AppConfig(api_football_key="test"),
        "football_scanner": football_scan,
        "football_context_refresher": context_refresh,
        "tennis_loader": lambda **_kwargs: [],
        "esports_loader": lambda **_kwargs: [],
    }
    run_wettfinder(now=now, **common)
    refreshed = run_wettfinder(now=now + timedelta(minutes=30), **common)
    run_wettfinder(now=now + timedelta(minutes=40), **common)

    def failed_context_refresh(*_args, **_kwargs):
        raise RuntimeError("temporary context outage")

    degraded = run_wettfinder(
        now=now + timedelta(minutes=60),
        **{
            **common,
            "football_context_refresher": failed_context_refresh,
        },
    )

    assert scan_calls == 1
    assert refreshed["football"]["base_candidates"] == 2
    assert refreshed["football"]["blocked_counts"] == {
        "Transfer nicht validiert": 4
    }
    # Unchecked discovery fixtures are refreshed immediately; once they are
    # inside the two-hour window, the 25-minute freshness contract schedules
    # the next update without waiting for a browser session.
    assert refresh_calls == [
        ([1], now),
        ([1], now + timedelta(minutes=30)),
    ]
    assert refreshed["sources"]["football"]["context_status"] == "refreshed"
    assert refreshed["candidates"] == []
    assert refreshed["sources"]["football"]["price_status_counts"] == {
        "UNAVAILABLE": 1
    }
    assert degraded["football"]["status"] == "degraded"
    assert degraded["sources"]["football"]["status"] == "degraded"
    assert degraded["sources"]["football"]["context_status"] == "degraded"


def test_runner_fails_closed_without_api_key_but_still_writes_state(tmp_path):
    document = run_wettfinder(
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert document["sources"]["football"]["status"] == "degraded"
    assert document["candidates"] == []
    assert document["sources"]["basketball"]["status"] == (
        "live_only_no_prematch_model"
    )


def test_runner_reprices_each_supported_reused_candidate_on_every_run(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state_path = tmp_path / "wettfinder.json"
    scan_calls = 0
    football_quote_calls: list[list[str]] = []
    tennis_quote_calls: list[list[str]] = []

    def football_scan(_search_date):
        nonlocal scan_calls
        scan_calls += 1
        return _football_snapshot(now)

    tennis = ModelSignal(
        key="tennis-model-1-A",
        label="Tennis - Alice vs Bea - Sieg Alice",
        probability=0.66,
        probability_haircut=0.08,
        evidence_stage="SHADOW",
        policy_version="tennis-test",
        detail="Persistiertes Tennis-Modell",
        scheduled_start="2030-01-01T16:00:00+00:00",
        sport="Tennis",
        event_label="Alice vs Bea",
        market="Match Winner",
        selection="Sieg Alice",
        competitor_a="Alice",
        competitor_b="Bea",
        selected_competitor="Alice",
    )
    esports = ModelSignal(
        key="esports-match-2",
        label="DOTA2 - Level UP vs Team Lynx - Sieg Level UP",
        probability=0.68,
        probability_haircut=0.10,
        evidence_stage="SHADOW",
        policy_version="esports-test",
        detail="Persistiertes E-Sport-Modell",
        scheduled_start="2030-01-01T18:00:00+00:00",
        sport="E-Sport",
        event_label="DOTA2 - Level UP vs Team Lynx",
        market="Match Winner",
        selection="Sieg Level UP",
        competitor_a="Level UP",
        competitor_b="Team Lynx",
        selected_competitor="Level UP",
    )

    def consensus(row, prices, fetched_at):
        ordered = sorted(prices)
        return MarketConsensus(
            fixture_id=None,
            candidate_id=row["candidate_id"],
            market_key="H2H",
            bet_name="h2h",
            value_name=row["selected_competitor"],
            consensus_odds=(ordered[1] + ordered[2]) / 2,
            conservative_odds=ordered[0] + (ordered[1] - ordered[0]) * 0.75,
            lowest_odds=ordered[0],
            best_odds=ordered[-1],
            bookmaker_count=4,
            quoted_at=fetched_at.isoformat(),
            fetched_at=fetched_at.isoformat(),
            source=ODDS_API_REFERENCE_SOURCE,
            points=tuple(
                QuotePoint(
                    f"Book {index}",
                    price,
                    bookmaker_id=f"odds-api:book-{index}",
                    observed_at=fetched_at.isoformat(),
                )
                for index, price in enumerate(ordered, start=1)
            ),
            provider_event_id="provider-tennis-model-1",
            scheduled_start=row["scheduled_start"],
            event_home=row["competitor_a"],
            event_away=row["competitor_b"],
        )

    def football_quotes(rows):
        football_quote_calls.append([row["candidate_id"] for row in rows])
        return {}, []

    def tennis_quotes(rows):
        tennis_quote_calls.append([row["candidate_id"] for row in rows])
        fetched_at = now + timedelta(
            minutes=10 * (len(tennis_quote_calls) - 1)
        )
        row = rows[0]
        return {
            row["candidate_id"]: consensus(
                row,
                [1.90, 1.95, 2.00, 2.05],
                fetched_at,
            ),
        }, []

    common = {
        "state_path": state_path,
        "config": AppConfig(api_football_key="test", odds_api_key="odds-test"),
        "football_scanner": football_scan,
        "football_quote_loader": football_quotes,
        "tennis_quote_loader": tennis_quotes,
        "tennis_loader": lambda **_kwargs: [tennis],
        "esports_loader": lambda **_kwargs: [esports],
    }
    first = run_wettfinder(now=now, **common)
    second = run_wettfinder(now=now + timedelta(minutes=10), **common)

    assert scan_calls == 1
    assert football_quote_calls == [
        ["fixture-1-btts"],
        ["fixture-1-btts"],
    ]
    assert tennis_quote_calls == [
        ["tennis-model-1-A"],
        ["tennis-model-1-A"],
    ]
    assert {row["sport"] for row in first["model_candidates"]} == {
        "Fußball",
        "Tennis",
        "E-Sport",
    }
    assert {row["sport"] for row in second["model_candidates"]} == {
        "Fußball",
        "Tennis",
        "E-Sport",
    }
    priced = {row["sport"]: row for row in second["model_candidates"]}
    assert priced["Tennis"]["reference_price_status"] == "PLAYABLE"
    assert priced["Tennis"]["quote_provider_event_id"] == (
        "provider-tennis-model-1"
    )
    assert priced["Tennis"]["reference_quote"]["executable_quote"] == {
        "bookmaker": "Book 2",
        "odds": 1.95,
        "bookmaker_id": "odds-api:book-2",
        "observed_at": (now + timedelta(minutes=10)).isoformat(),
    }
    assert priced["E-Sport"]["reference_price_status"] == "UNAVAILABLE"
    assert priced["Tennis"]["reference_quote"]["fetched_at"] == (
        now + timedelta(minutes=10)
    ).isoformat()
    assert [row["sport"] for row in second["candidates"]] == ["Tennis"]
    assert second["sources"]["tennis"]["price_checked_count"] == 1
    assert second["sources"]["tennis"]["reference_quote_count"] == 1
    assert second["sources"]["esports"]["price_provider_status"] == (
        "unsupported_no_verified_odds_provider"
    )


def test_quote_loader_exception_details_are_never_persisted(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    secret = "api-key=must-not-be-persisted"
    tennis = ModelSignal(
        key="tennis-secret-test-A",
        label="Tennis - Alice vs Bea - Sieg Alice",
        probability=0.66,
        probability_haircut=0.08,
        evidence_stage="SHADOW",
        policy_version="tennis-test",
        detail="Persistiertes Tennis-Modell",
        scheduled_start="2030-01-01T16:00:00+00:00",
        sport="Tennis",
        event_label="Alice vs Bea",
        market="Match Winner",
        selection="Sieg Alice",
        competitor_a="Alice",
        competitor_b="Bea",
        selected_competitor="Alice",
    )

    def fail_with_secret(_rows):
        raise RuntimeError(f"provider URL leaked {secret}")

    state_path = tmp_path / "wettfinder.json"
    document = run_wettfinder(
        now=now,
        state_path=state_path,
        config=AppConfig(api_football_key="test", odds_api_key="odds-test"),
        football_scanner=lambda _search_date: _football_snapshot(now),
        football_quote_loader=fail_with_secret,
        tennis_quote_loader=fail_with_secret,
        tennis_loader=lambda **_kwargs: [tennis],
        esports_loader=lambda **_kwargs: [],
    )

    expected = ["Quotenabruf fehlgeschlagen (RuntimeError)"]
    assert document["sources"]["football"]["quote_errors"] == expected
    assert document["sources"]["tennis"]["quote_errors"] == expected
    assert document["run_status"] == "degraded"
    assert document["operational_error_count"] == 2
    assert load_state(state_path) == document
    assert secret not in str(document)


def test_tennis_quote_failure_keeps_strict_football_and_drops_tennis_tip(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    tennis = ModelSignal(
        key="tennis-source-failure-A",
        label="Tennis - Alice vs Bea - Sieg Alice",
        probability=0.66,
        probability_haircut=0.08,
        evidence_stage="SHADOW",
        policy_version="tennis-test",
        detail="Persistiertes Tennis-Modell",
        scheduled_start="2030-01-01T16:00:00+00:00",
        sport="Tennis",
        event_label="Alice vs Bea",
        market="Match Winner",
        selection="Sieg Alice",
        competitor_a="Alice",
        competitor_b="Bea",
        selected_competitor="Alice",
    )

    def football_quotes(rows):
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": f"Football Book {index}",
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [
                                        {"value": "Yes", "odd": odds}
                                    ],
                                }
                            ],
                        }
                        for index, odds in enumerate(
                            ("1.90", "1.95", "2.00", "2.05"),
                            start=1,
                        )
                    ],
                }
            ]
        }
        return parse_fixture_consensus(payload, rows, fetched_at=now), []

    def degraded_tennis_quotes(rows):
        row = rows[0]
        prices = (1.90, 1.95, 2.00, 2.05)
        quote = MarketConsensus(
            fixture_id=None,
            candidate_id=row["candidate_id"],
            market_key="H2H",
            bet_name="h2h",
            value_name=row["selected_competitor"],
            consensus_odds=1.975,
            conservative_odds=1.9375,
            lowest_odds=1.90,
            best_odds=2.05,
            bookmaker_count=4,
            quoted_at=now.isoformat(),
            fetched_at=now.isoformat(),
            source=ODDS_API_REFERENCE_SOURCE,
            points=tuple(
                QuotePoint(
                    f"Tennis Book {index}",
                    price,
                    bookmaker_id=f"odds-api:tennis-{index}",
                    observed_at=now.isoformat(),
                )
                for index, price in enumerate(prices, start=1)
            ),
            provider_event_id="provider-tennis-source-failure",
            scheduled_start=row["scheduled_start"],
            event_home=row["competitor_a"],
            event_away=row["competitor_b"],
        )
        return (
            {row["candidate_id"]: quote},
            ["Quotenabruf fehlgeschlagen (TimeoutError)"],
        )

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test", odds_api_key="odds-test"),
        football_scanner=lambda _search_date: _football_snapshot(now),
        football_quote_loader=football_quotes,
        tennis_quote_loader=degraded_tennis_quotes,
        tennis_loader=lambda **_kwargs: [tennis],
        esports_loader=lambda **_kwargs: [],
    )

    assert document["run_status"] == "degraded"
    assert document["operational_error_count"] == 1
    assert document["sources"]["football"]["operational_error_count"] == 0
    assert document["sources"]["tennis"]["operational_error_count"] == 1
    assert [row["source"] for row in document["candidates"]] == [
        "football_challenge"
    ]
    assert document["candidates"][0]["reference_price_status"] == "PLAYABLE"
    assert any(
        row["source"] == "tennis_shadow"
        for row in document["model_candidates"]
    )
    assert document["sources"]["tennis"]["published_recommendation_count"] == 0


def test_normal_missing_market_coverage_is_not_an_operational_failure(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    tennis = ModelSignal(
        key="tennis-coverage-A",
        label="Tennis - Alice vs Bea - Sieg Alice",
        probability=0.66,
        probability_haircut=0.08,
        evidence_stage="SHADOW",
        policy_version="tennis-test",
        detail="Persistiertes Tennis-Modell",
        scheduled_start="2030-01-01T16:00:00+00:00",
        sport="Tennis",
        event_label="Alice vs Bea",
        market="Match Winner",
        selection="Sieg Alice",
        competitor_a="Alice",
        competitor_b="Bea",
        selected_competitor="Alice",
    )

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test", odds_api_key="odds-test"),
        football_scanner=lambda _search_date: _football_snapshot(now),
        football_quote_loader=lambda _rows: ({}, []),
        tennis_quote_loader=lambda _rows: (
            {},
            ["The Odds API meldet keine aktive Tennis-Konkurrenz"],
        ),
        tennis_loader=lambda **_kwargs: [tennis],
        esports_loader=lambda **_kwargs: [],
    )

    assert document["run_status"] == "completed"
    assert document["operational_error_count"] == 0
    assert document["sources"]["tennis"]["reference_quote_count"] == 0


def test_main_returns_nonzero_for_persisted_operational_failure(
    monkeypatch,
    capsys,
):
    document = {
        "run_status": "degraded",
        "operational_error_count": 1,
        "generated_at": "2030-01-01T10:00:00+00:00",
        "candidates": [],
        "model_candidates": [],
        "bookmaker_data_used": False,
        "sources": {
            "football": {
                "status": "degraded",
                "due_reason": "retry_degraded_scan",
                "context_status": "degraded",
                "discovery_scope": 51,
            }
        },
    }
    monkeypatch.setattr(
        wettfinder_automation,
        "run_wettfinder",
        lambda **_kwargs: document,
    )

    assert wettfinder_automation.main(["--state-path", "ignored.json"]) == 1
    assert '"status": "degraded"' in capsys.readouterr().out


def test_tennis_consensus_requires_exact_event_and_real_bookmaker_points():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidate = {
        "candidate_id": "tennis-model-1-A",
        "sport": "Tennis",
        "competitor_a": "Alice Garcia",
        "competitor_b": "Béa Martin",
        "selected_competitor": "Alice Garcia",
        "scheduled_start": "2030-01-01T16:00:00+00:00",
    }
    payload = {
        "id": "provider-event-123",
        "home_team": "Béa Martin",
        "away_team": "Alice Garcia",
        "commence_time": "2030-01-01T16:05:00Z",
        "bookmakers": [
            {
                "key": f"book-{index}",
                "title": f"Book {index}",
                "last_update": now.isoformat(),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Alice Garcia", "price": price},
                            {"name": "Béa Martin", "price": 1.80},
                        ],
                    }
                ],
            }
            for index, price in enumerate(
                (1.90, 1.95, 2.00, 2.05),
                start=1,
            )
        ],
    }

    quotes = parse_h2h_event_consensus(
        payload,
        [candidate],
        fetched_at=now,
    )

    quote = quotes["tennis-model-1-A"]
    assert quote.provider_event_id == "provider-event-123"
    assert quote.fixture_id is None
    assert quote.bookmaker_count == 4
    assert [point.odds for point in quote.points] == [1.90, 1.95, 2.00, 2.05]
    assert MarketConsensus.from_dict(quote.to_dict()) == quote

    wrong_player = {**candidate, "competitor_a": "Alice Garcia Junior"}
    wrong_time = {
        **candidate,
        "scheduled_start": "2030-01-01T20:30:00+00:00",
    }
    assert parse_h2h_event_consensus(payload, [wrong_player]) == {}
    assert parse_h2h_event_consensus(payload, [wrong_time]) == {}
    for bookmaker in payload["bookmakers"]:
        bookmaker.pop("last_update")
    unstamped = parse_h2h_event_consensus(
        payload,
        [candidate],
        fetched_at=now,
    )
    assert unstamped == {}


def test_tennis_fetch_refuses_unbounded_ambiguous_sport_key_scan(monkeypatch):
    calls: list[str] = []

    def fake_json(path, _api_key, **_kwargs):
        calls.append(path)
        if path == "sports/":
            return [
                {
                    "key": f"tennis_tournament_{index}",
                    "group": "Tennis",
                    "title": f"Tournament {index}",
                    "active": True,
                }
                for index in range(20)
            ], None
        raise AssertionError("event discovery must not start ambiguously")

    monkeypatch.setattr(market_consensus, "_odds_api_json", fake_json)
    quotes, errors = market_consensus.fetch_tennis_h2h_consensus(
        "real-key-not-used-by-test",
        [
            {
                "candidate_id": "tennis-model-1-A",
                "sport": "Tennis",
                "competitor_a": "Alice",
                "competitor_b": "Bea",
                "selected_competitor": "Alice",
                "scheduled_start": "2030-01-01T16:00:00+00:00",
                "competition": "ATP Unknown Event",
            }
        ],
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    )

    assert quotes == {}
    assert calls == ["sports/"]
    assert any("Provider-Sportkey" in error for error in errors)


def test_runner_can_release_team_under_one_five_at_a_good_price(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    useful = _challenge_candidate(now + timedelta(hours=5))
    useful.context = {"passed": True, "blocked_reasons": []}
    team_under = replace(
        useful,
        candidate_id="fixture-2-away-under-1-5",
        fixture_id=2,
        home_team_id=20,
        away_team_id=21,
        home_team="FC Gamma",
        away_team="FC Delta",
        market_key="AWAY_UNDER_1_5",
        market="Team 2 Gesamttore",
        selection="Unter 1.5",
    )
    team_under.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "blocked_reasons": [],
    }
    snapshot = _football_snapshot(now)
    snapshot["forecast_shortlist"] = [useful, team_under]
    snapshot["base_fixture_count"] = 2
    snapshot["context_fixtures"] = 2
    snapshot["context_verified_fixtures"] = 2
    snapshot["context_fixture_statuses"] = {"1": "verified", "2": "verified"}

    def quote_loader(rows):
        team_under_row = next(
            row for row in rows if row["candidate_id"] == team_under.candidate_id
        )
        assert team_under_row["is_basic_forecast"] is False
        prices = (2.40, 2.45, 2.50, 2.55)
        return {
            team_under.candidate_id: MarketConsensus(
                fixture_id=2,
                candidate_id=team_under.candidate_id,
                market_key="AWAY_UNDER_1_5",
                bet_name="Total - Away",
                value_name="Under 1.5",
                consensus_odds=2.475,
                conservative_odds=2.4375,
                lowest_odds=2.40,
                best_odds=2.55,
                bookmaker_count=4,
                quoted_at=now.isoformat(),
                fetched_at=now.isoformat(),
                source=REFERENCE_SOURCE,
                points=tuple(
                    QuotePoint(
                        f"Book {index}",
                        price,
                        bookmaker_id=f"api-football:{index}",
                        observed_at=now.isoformat(),
                    )
                    for index, price in enumerate(prices, start=1)
                ),
                scheduled_start=team_under_row["scheduled_start"],
            )
        }, []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _search_date: snapshot,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    by_id = {
        row["candidate_id"]: row for row in document["model_candidates"]
    }
    assert set(by_id) == {useful.candidate_id, team_under.candidate_id}
    assert by_id[team_under.candidate_id]["is_basic_forecast"] is False
    assert by_id[team_under.candidate_id]["reference_price_status"] == "PLAYABLE"
    assert document["football"]["basis_candidates"] == []
    assert document["sources"]["football"]["price_checked_count"] == 2
    assert [row["candidate_id"] for row in document["candidates"]] == [
        team_under.candidate_id
    ]


def test_runner_reprices_same_day_football_after_context_ttl_without_release(
    tmp_path,
):
    scanned_at = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state_path = tmp_path / "wettfinder.json"
    scan_calls = 0
    quote_calls: list[list[str]] = []

    def scan(_search_date):
        nonlocal scan_calls
        scan_calls += 1
        return _football_snapshot(scanned_at)

    def quote_loader(rows):
        quote_calls.append([row["candidate_id"] for row in rows])
        observed_at = scanned_at + timedelta(
            minutes=90 * (len(quote_calls) - 1)
        )
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": observed_at.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": f"Book {index}",
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [
                                        {"value": "Yes", "odd": "2.05"}
                                    ],
                                }
                            ],
                        }
                        for index in range(1, 5)
                    ],
                }
            ]
        }
        return parse_fixture_consensus(
            payload,
            rows,
            fetched_at=observed_at,
        ), []

    common = {
        "state_path": state_path,
        "config": AppConfig(api_football_key="test"),
        "football_scanner": scan,
        "football_quote_loader": quote_loader,
        "tennis_loader": lambda **_kwargs: [],
        "esports_loader": lambda **_kwargs: [],
    }
    run_wettfinder(now=scanned_at, **common)
    stale = run_wettfinder(
        now=scanned_at + timedelta(minutes=90),
        **common,
    )

    assert scan_calls == 1
    assert quote_calls == [
        ["fixture-1-btts"],
        ["fixture-1-btts"],
    ]
    assert len(stale["model_candidates"]) == 1
    model_row = stale["model_candidates"][0]
    assert model_row["candidate_id"] == "fixture-1-btts"
    assert model_row["reference_price_status"] == "PLAYABLE"
    assert model_row["context_complete"] is False
    assert "veraltet" in model_row["context_summary"]
    assert stale["candidates"] == []


def test_playable_price_cannot_release_incomplete_candidate_context(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    snapshot = _football_snapshot(now)
    candidate = snapshot["shortlist"][0]
    candidate.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": False,
        "release_eligible": False,
        "lineup_status": "confirmation_due",
        "injury_impact_status": "unassessed",
        "blocked_reasons": [],
    }

    def quote_loader(rows):
        payload = {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": rows[0]["scheduled_start"],
                    },
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "id": index,
                            "name": f"Book {index}",
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [
                                        {"value": "Yes", "odd": "2.05"}
                                    ],
                                }
                            ],
                        }
                        for index in range(1, 5)
                    ],
                }
            ]
        }
        return parse_fixture_consensus(
            payload,
            rows,
            fetched_at=now,
        ), []

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _search_date: snapshot,
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert len(document["model_candidates"]) == 1
    model_row = document["model_candidates"][0]
    assert model_row["reference_price_status"] == "PLAYABLE"
    assert model_row["context_complete"] is False
    assert document["candidates"] == []


def test_pre_gate_riskobet_pool_is_persisted_and_joined_into_one_context_batch():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    risk = replace(
        _challenge_candidate(now + timedelta(minutes=80)),
        candidate_id="fixture-1-away-win-risk",
        market_key="RESULT_AWAY",
        market="Sieger 1X2",
        selection="FC Beta",
        probability=0.34,
        conservative_probability=0.28,
        probability_haircut_pp=6.0,
        model_price=1.0 / 0.28,
        blocked_reasons=["Markt hat das Walk-forward-Gate nicht bestanden"],
    )
    assert risk.base_eligible is False
    state = _football_state_from_snapshot(
        {
            "scanned_at": now.isoformat(),
            "fixtures_found": 1,
            "fixtures_modeled": 1,
            "riskobet_source_candidates": [risk],
            "errors": [],
        },
        attempted_at=now,
        search_date=now.date(),
    )

    assert state["riskobet_source_candidate_count"] == 1
    assert football_context_due_fixture_ids(state, now=now) == [1]
    mixed = wettfinder_automation._discovered_candidates_for_fixtures(
        state,
        [1],
    )
    assert [candidate.candidate_id for candidate in mixed] == [risk.candidate_id]

    risk.context = {
        "passed": True,
        "forecast_passed": False,
        "release_context_complete": True,
        "release_eligible": False,
        "checked_at": (now + timedelta(minutes=1)).isoformat(),
        "blocked_reasons": [],
    }
    refreshed = _merge_context_refresh(
        state,
        {
            "candidates": [],
            "riskobet_source_candidates": [risk],
            "errors": [],
            "operational_errors": [],
        },
        fixture_ids=[1],
        checked_at=now + timedelta(minutes=1),
    )

    assert refreshed["riskobet_source_candidate_count"] == 1
    assert refreshed["riskobet_source_candidates"][0]["context"][
        "checked_at"
    ] == (now + timedelta(minutes=1)).isoformat()
    assert refreshed.get("candidates", []) == []


def test_initial_shared_risk_context_is_persisted_and_not_refetched():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    risk = replace(
        _challenge_candidate(now + timedelta(minutes=80)),
        candidate_id="fixture-1-away-win-risk",
        market_key="RESULT_AWAY",
        market="Sieger 1X2",
        selection="FC Beta",
        probability=0.34,
        conservative_probability=0.28,
        probability_haircut_pp=6.0,
        model_price=1.0 / 0.28,
        blocked_reasons=["Markt hat das Walk-forward-Gate nicht bestanden"],
    )
    risk.context = {
        "passed": True,
        "forecast_passed": False,
        "release_context_complete": True,
        "release_eligible": False,
        "checked_at": now.isoformat(),
        "blocked_reasons": [],
    }

    state = _football_state_from_snapshot(
        {
            "scanned_at": now.isoformat(),
            "context_checked_at": now.isoformat(),
            "fixtures_found": 1,
            "fixtures_modeled": 1,
            "riskobet_source_candidates": [risk],
            "riskobet_context_checked_fixture_ids": [1],
            "errors": [],
        },
        attempted_at=now,
        search_date=now.date(),
    )

    assert state["riskobet_context_checked_fixture_ids"] == [1]
    assert state["context_checks"] == {"1": now.isoformat()}
    assert football_context_due_fixture_ids(state, now=now) == []


def test_football_risk_snapshot_clock_is_stable_until_inputs_change():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    base = _challenge_candidate(now + timedelta(hours=4))
    specs = (
        ("RESULT_HOME", "Endergebnis", "FC Alpha", 0.20),
        ("RESULT_DRAW", "Endergebnis", "Unentschieden", 0.25),
        ("RESULT_AWAY", "Endergebnis", "FC Beta", 0.55),
        ("DC_1X", "Doppelte Chance", "1X", 0.45),
        ("HOME_OVER_0_5", "Team 1 Gesamttore", "Über 0.5", 0.65),
        ("HOME_OVER_1_5", "Team 1 Gesamttore", "Über 1.5", 0.25),
    )
    risk_pool = [
        replace(
            base,
            candidate_id=f"fixture-1-{market_key.casefold()}",
            market_key=market_key,
            market=market,
            selection=selection,
            probability=probability,
            conservative_probability=probability - 0.08,
            probability_haircut_pp=8.0,
            model_price=1.0 / (probability - 0.08),
            blocked_reasons=[
                "Markt hat das Walk-forward-Gate nicht bestanden"
            ],
        )
        for market_key, market, selection, probability in specs
    ]
    state = _football_state_from_snapshot(
        {
            "scanned_at": now.isoformat(),
            "fixtures_found": 1,
            "fixtures_modeled": 1,
            "riskobet_source_candidates": risk_pool,
            "errors": [],
        },
        attempted_at=now,
        search_date=now.date(),
    )

    first = wettfinder_automation._riskobet_football_source(
        state,
        now=now + timedelta(minutes=5),
        target_date=now.date(),
    )
    repeated = wettfinder_automation._riskobet_football_source(
        state,
        now=now + timedelta(minutes=35),
        target_date=now.date(),
    )

    assert len(first) == len(repeated) == 1
    assert first[0].snapshot.modeled_at == now
    assert repeated[0].snapshot.modeled_at == now
    assert first[0].snapshot.snapshot_id == repeated[0].snapshot.snapshot_id

    refreshed_state = dict(state)
    refreshed_state["last_discovery_at"] = (now + timedelta(minutes=10)).isoformat()
    refreshed_state["last_success_at"] = (now + timedelta(minutes=10)).isoformat()
    refetched = wettfinder_automation._riskobet_football_source(
        refreshed_state,
        now=now + timedelta(minutes=35),
        target_date=now.date(),
    )

    assert len(refetched) == 1
    assert refetched[0].snapshot.modeled_at == now + timedelta(minutes=10)
    assert refetched[0].snapshot.snapshot_id != first[0].snapshot.snapshot_id


def test_research_batch_uses_injected_completed_causal_history_once():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    event = {
        "source": "ESPN",
        "game_id": "nba-1",
        "league": "NBA",
        "home_team": "Alpha",
        "away_team": "Beta",
        "start_time": (now + timedelta(hours=6)).isoformat(),
    }
    history = []
    for team, wins in (("Alpha", 2), ("Beta", 6)):
        for index in range(8):
            history.append(
                {
                    "status": "final",
                    "completed_at": (
                        now - timedelta(days=index + 1)
                    ).isoformat(),
                    "home_team": team,
                    "away_team": f"Opponent-{team}-{index}",
                    "winner_side": "home" if index < wins else "away",
                }
            )
    history.append(
        {
            "status": "final",
            "completed_at": (now + timedelta(minutes=1)).isoformat(),
            "home_team": "Alpha",
            "away_team": "Future leak",
            "winner_side": "home",
        }
    )
    calls = []

    def history_loader(**kwargs):
        calls.append(kwargs)
        return history

    batch = wettfinder_automation._riskobet_research_batch(
        "basketball",
        [event],
        wettfinder_automation.adapt_basketball_research,
        now=now,
        history_loader=history_loader,
    )

    assert len(calls) == 1
    assert calls[0]["as_of"] == now
    assert calls[0]["events"][0]["source_observed_at"] == now.isoformat()
    assert len(batch.candidates) == 1
    assert batch.candidates[0].model_probability is not None
    assert batch.snapshots[0].modeled_at == now
    assert sorted(factor.sample_size for factor in batch.snapshots[0].factors) == [8, 8]


def test_research_without_completed_history_stays_open_without_probability():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    batch = wettfinder_automation._riskobet_research_batch(
        "cricket",
        [
            {
                "source": "Cricbuzz",
                "match_id": "cricket-1",
                "tournament": "Test Cup",
                "team1": "Alpha",
                "team2": "Beta",
                "start_time": (now + timedelta(hours=6)).isoformat(),
            }
        ],
        wettfinder_automation.adapt_cricket_research,
        now=now,
    )

    assert len(batch.candidates) == 1
    assert batch.candidates[0].model_probability is None
    assert batch.candidates[0].selection_key == "open"
    assert batch.candidates[0].missing_core_data


def test_riskobet_context_never_displaces_normal_wettfinder_batch_priority():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    normal = [
        {
            "fixture_id": fixture_id,
            "kickoff": (now + timedelta(minutes=70 + fixture_id)).isoformat(),
        }
        for fixture_id in range(1, 21)
    ]
    risk_only = [
        {
            "fixture_id": 999,
            "kickoff": (now + timedelta(minutes=5)).isoformat(),
        }
    ]

    due = football_context_due_fixture_ids(
        {
            "discovery_candidates": normal,
            "riskobet_source_candidates": risk_only,
            "context_checks": {},
        },
        now=now,
    )

    assert due == list(range(1, 21))


def test_explicit_riskobet_runner_is_isolated_from_prices_and_uses_temp_paths(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    captured = {}
    sources = {
        sport: ()
        for sport in (
            "football",
            "tennis",
            "basketball",
            "ice_hockey",
            "cricket",
            "esports",
        )
    }

    def runner(**kwargs):
        captured.update(kwargs)
        return {
            "status": "COMPLETE",
            "run_id": "run_test",
            "snapshots": [],
            "candidates": [],
            "errors": [],
        }

    state_path = tmp_path / "wettfinder.json"
    document = run_wettfinder(
        now=now,
        state_path=state_path,
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: _football_snapshot(now),
        football_context_refresher=lambda *_args: {},
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True,
        riskobet_runner=runner,
        riskobet_sources=sources,
    )

    assert document["riskobet"]["status"] == "complete"
    assert captured["db_path"] == tmp_path / "riskobet.db"
    assert captured["latest_path"] == tmp_path / "riskobet_latest.json"
    assert captured["football_source"] == ()
    assert "football_quote_loader" not in captured
    assert "reference_quotes" not in captured
    assert not (tmp_path / "riskobet.db").exists()
    assert not (tmp_path / "riskobet_latest.json").exists()


def test_riskobet_settlement_runs_before_new_model_publication(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    order = []
    result_loader = lambda _requests, _observed: ()

    def settlement_runner(**kwargs):
        order.append("settlement")
        assert kwargs["result_loaders"] == {"football": result_loader}
        assert kwargs["db_path"] == tmp_path / "riskobet.db"
        assert kwargs["latest_path"] == tmp_path / "riskobet_latest.json"
        return {
            "run_id": "prior-run",
            "due_candidates": 1,
            "due_events": 1,
            "checked_sports": ["football"],
            "terminal_settlements": 1,
            "unresolved_candidates": 0,
            "published": True,
            "error_count": 0,
            "errors": [],
        }

    def risk_runner(**_kwargs):
        order.append("model")
        return {
            "status": "COMPLETE",
            "run_id": "new-run",
            "snapshots": [],
            "candidates": [],
            "errors": [],
        }

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: _football_snapshot(now),
        football_context_refresher=lambda *_args: {},
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True,
        riskobet_runner=risk_runner,
        riskobet_settlement_runner=settlement_runner,
        riskobet_result_loaders={"football": result_loader},
        riskobet_sources={sport: () for sport in (
            "football", "tennis", "basketball", "ice_hockey", "cricket", "esports"
        )},
    )

    assert order == ["settlement", "model"]
    assert document["riskobet"]["settlement"]["terminal_settlements"] == 1
    assert document["riskobet"]["run_id"] == "new-run"


def test_riskobet_settlement_failure_is_sanitized_and_model_run_continues(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    calls = []

    def failed_settlement(**_kwargs):
        raise RuntimeError("private-provider-token")

    def risk_runner(**_kwargs):
        calls.append("model")
        return {
            "status": "COMPLETE",
            "run_id": "new-run",
            "snapshots": [],
            "candidates": [],
            "errors": [],
        }

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: _football_snapshot(now),
        football_context_refresher=lambda *_args: {},
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True,
        riskobet_runner=risk_runner,
        riskobet_settlement_runner=failed_settlement,
        riskobet_sources={sport: () for sport in (
            "football", "tennis", "basketball", "ice_hockey", "cricket", "esports"
        )},
    )

    assert calls == ["model"]
    encoded = json.dumps(document["riskobet"])
    assert "private-provider-token" not in encoded
    assert document["riskobet"]["settlement"]["errors"] == [
        "automation:settlement_failed_runtimeerror"
    ]


def test_riskobet_integrity_failure_prevents_new_model_publication(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    calls = []

    def failed_settlement(**_kwargs):
        raise FrozenRevisionError("tampered store")

    def forbidden_model(**_kwargs):
        calls.append("model")
        raise AssertionError("model must not publish over an integrity failure")

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: _football_snapshot(now),
        football_context_refresher=lambda *_args: {},
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True,
        riskobet_runner=forbidden_model,
        riskobet_settlement_runner=failed_settlement,
        riskobet_sources={sport: () for sport in (
            "football", "tennis", "basketball", "ice_hockey", "cricket", "esports"
        )},
    )

    assert calls == []
    assert document["riskobet"]["status"] == "failed"
    assert document["riskobet"]["failure_type"] == "FrozenRevisionError"
    assert "tampered store" not in json.dumps(document)


def test_temp_wettfinder_path_does_not_enable_default_riskobet_side_effects(
    tmp_path,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: _football_snapshot(now),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert "riskobet" not in document
    assert not (tmp_path / "riskobet.db").exists()
    assert not (tmp_path / "riskobet_latest.json").exists()


def test_riskobet_research_retry_detects_missing_corrupt_and_failed_sources(
    tmp_path,
):
    target = date(2030, 1, 1)
    latest = tmp_path / "riskobet_latest.json"
    completed_attempts = {
        sport: {"date": target.isoformat(), "status": "completed"}
        for sport in ("basketball", "ice_hockey", "cricket")
    }
    previous = {
        "riskobet": {"research_source_attempts": completed_attempts}
    }

    assert riskobet_research_refresh_due(
        previous,
        latest_path=latest,
        target_date=target,
    ) is True

    latest.write_text("{broken", encoding="utf-8")
    assert riskobet_research_refresh_due(
        previous,
        latest_path=latest,
        target_date=target,
    ) is True
    latest.write_text(
        json.dumps(
            RiskRunSnapshot(
                started_at=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
                completed_at=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
                status=RunStatus.COMPLETE,
            ).to_dict()
        ),
        encoding="utf-8",
    )
    assert riskobet_research_refresh_due(
        previous,
        latest_path=latest,
        target_date=target,
    ) is False
    failed = json.loads(json.dumps(previous))
    failed["riskobet"]["research_source_attempts"]["cricket"][
        "status"
    ] = "failed"
    assert riskobet_research_refresh_due(
        failed,
        latest_path=latest,
        target_date=target,
    ) is True


def test_default_riskobet_sources_execute_exactly_the_six_due_adapters(monkeypatch):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    calls = []

    def recorder(sport):
        def run(*_args, **_kwargs):
            calls.append(sport)
            return ()

        return run

    monkeypatch.setattr(
        wettfinder_automation, "_riskobet_football_source", recorder("football")
    )
    monkeypatch.setattr(
        wettfinder_automation, "adapt_tennis_shadow", recorder("tennis")
    )
    monkeypatch.setattr(
        wettfinder_automation, "adapt_esports_shadow", recorder("esports")
    )
    monkeypatch.setattr(
        wettfinder_automation,
        "_default_basketball_risk_source",
        recorder("basketball"),
    )
    monkeypatch.setattr(
        wettfinder_automation,
        "_default_ice_hockey_risk_source",
        recorder("ice_hockey"),
    )
    monkeypatch.setattr(
        wettfinder_automation, "_default_cricket_risk_source", recorder("cricket")
    )

    sources, due = wettfinder_automation._riskobet_default_sources(
        {},
        now=now,
        target_date=now.date(),
        research_due=True,
    )
    assert tuple(sport for sport in SPORT_ORDER if sport in sources) == SPORT_ORDER
    assert due == {sport: True for sport in SPORT_ORDER}
    for sport in SPORT_ORDER:
        sources[sport]()
    assert calls == list(SPORT_ORDER)

    calls.clear()
    sources, due = wettfinder_automation._riskobet_default_sources(
        {},
        now=now,
        target_date=now.date(),
        research_due=False,
    )
    assert set(sources) == {"football", "tennis", "esports"}
    assert due == {
        "football": True,
        "tennis": True,
        "basketball": False,
        "ice_hockey": False,
        "cricket": False,
        "esports": True,
    }
    for sport in ("football", "tennis", "esports"):
        sources[sport]()
    assert calls == ["football", "tennis", "esports"]


def test_failed_research_attempt_is_retried_without_new_football_discovery(
    tmp_path,
    monkeypatch,
):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    state_path = tmp_path / "wettfinder.json"
    latest_path = tmp_path / "riskobet_latest.json"
    attempts = {
        sport: {
            "date": now.date().isoformat(),
            "status": "failed" if sport == "cricket" else "completed",
        }
        for sport in ("basketball", "ice_hockey", "cricket")
    }
    state_path.write_text(
        json.dumps(
            {
                "version": AUTOMATION_VERSION,
                "betting_policy_version": BETTING_POLICY_VERSION,
                "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                "football": {
                    "status": "completed",
                    "search_date": now.date().isoformat(),
                    "last_attempt_at": (now - timedelta(minutes=5)).isoformat(),
                    "context_checks": {},
                    "discovery_candidates": [],
                    "riskobet_source_candidates": [],
                    "candidates": [],
                    "basis_candidates": [],
                },
                "riskobet": {"research_source_attempts": attempts},
            }
        ),
        encoding="utf-8",
    )
    latest_path.write_text(
        json.dumps(
            RiskRunSnapshot(
                started_at=now,
                completed_at=now,
                status=RunStatus.COMPLETE,
            ).to_dict()
        ),
        encoding="utf-8",
    )
    captured = {}

    def safe_sources(_football_state, *, now, target_date, research_due):
        captured["research_due"] = research_due
        sources = {
            sport: ()
            for sport in (
                "football",
                "tennis",
                "basketball",
                "ice_hockey",
                "cricket",
                "esports",
            )
        }
        return sources, {sport: True for sport in sources}

    monkeypatch.setattr(wettfinder_automation, "_same_artifact_path", lambda *_: True)
    monkeypatch.setattr(
        wettfinder_automation,
        "_riskobet_default_sources",
        safe_sources,
    )

    document = run_wettfinder(
        now=now,
        state_path=state_path,
        config=AppConfig(api_football_key="test"),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_runner=lambda **_kwargs: {
            "status": "COMPLETE",
            "run_id": "run_retry",
            "snapshots": [],
            "candidates": [],
            "errors": [],
        },
        riskobet_settlement_runner=lambda **_kwargs: {
            "run_id": None,
            "due_candidates": 0,
            "due_events": 0,
            "checked_sports": [],
            "terminal_settlements": 0,
            "unresolved_candidates": 0,
            "published": False,
            "error_count": 0,
            "errors": [],
        },
        riskobet_latest_path=latest_path,
    )

    assert captured["research_due"] is True
    assert document["sources"]["football"]["due_reason"] == (
        "daily_discovery_current"
    )
    assert document["riskobet"]["research_source_attempts"]["cricket"] == {
        "date": now.date().isoformat(),
        "status": "completed",
    }


def test_riskobet_failure_summary_never_leaks_exception_details(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    secret = "provider-secret-token-123"

    def failed_runner(**_kwargs):
        raise RuntimeError(secret)

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: _football_snapshot(now),
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True,
        riskobet_runner=failed_runner,
        riskobet_sources={},
    )

    assert document["riskobet"]["status"] == "failed"
    assert document["riskobet"]["failure_type"] == "RuntimeError"
    assert secret not in json.dumps(document)
