from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import market_consensus
from betting_math import BETTING_POLICY_VERSION
from challenge_engine import (
    MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST,
    MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
    ChallengeCandidate,
    ValidationMetrics,
)
from config_loader import AppConfig
from ev_signal_sources import (
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
    parse_h2h_event_consensus,
    parse_fixture_consensus,
)
from multi_sport_recommendations import ESPORTS_MODEL_VERSION
from wettfinder_automation import (
    AUTOMATION_VERSION,
    _active_football_candidates,
    _apply_reference_quotes,
    _default_football_scan,
    _football_candidate_record,
    _football_state_from_snapshot,
    _merge_context_refresh,
    _signal_record,
    build_daily_forecast_catalog,
    build_model_selection_ledger,
    football_context_due_fixture_ids,
    football_due,
    load_state,
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
    }
    payload = {
        "errors": [],
        "response": [
            {
                "fixture": {"id": 1},
                "update": now.isoformat(),
                "bookmakers": [
                    {
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


def test_context_refresh_reranks_new_stronger_fixture_into_full_catalog():
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
    assert len(fixture_ids) == 15
    assert fixture_ids[0] == 16
    assert 15 not in fixture_ids


def test_context_refresh_does_not_fall_back_to_basic_candidates():
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

    assert refreshed["candidates"] == []


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

    catalog = build_daily_forecast_catalog(
        football,
        [*tennis, *esports],
        now=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
        target_date=date(2030, 1, 1),
    )

    assert [row["sport"] for row in catalog].count("Fussball") == 15
    assert [row["sport"] for row in catalog].count("Tennis") == 3
    assert [row["sport"] for row in catalog].count("E-Sport") == 3
    assert len(catalog) == 21


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


def test_target_date_switches_at_2300_zurich():
    before = datetime(2030, 1, 1, 21, 59, tzinfo=UTC)
    after = datetime(2030, 1, 1, 22, 0, tzinfo=UTC)

    assert target_search_date(before) == date(2030, 1, 1)
    assert target_search_date(after) == date(2030, 1, 2)


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


def test_default_football_discovery_scans_all_configured_leagues(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "wettfinder_automation.ChallengeDataProvider",
        lambda *_args, **_kwargs: object(),
    )

    def fake_scan(_provider, league_ids, search_date, max_fixtures):
        captured.update(
            league_ids=league_ids,
            search_date=search_date,
            max_fixtures=max_fixtures,
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
        "Fussball",
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
    assert [row["sport"] for row in document["model_candidates"]] == ["Fussball"]


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
                    "fixture": {"id": 1},
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "name": name,
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [{"value": "Yes", "odd": odds}],
                                }
                            ],
                        }
                        for name, odds in (
                            ("Book A", "1.90"),
                            ("Book B", "1.95"),
                            ("Book C", "2.00"),
                            ("Book D", "2.05"),
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
    assert model_selection["status"] == "MODEL_SELECTION"
    assert model_selection["candidate_id"] == tip["candidate_id"]
    assert tip["reference_price_status"] == "PLAYABLE"
    assert model_selection["reference_price_status"] == "PLAYABLE"
    assert tip["reference_quote"]["bookmaker_count"] == 4
    assert tip["reference_quote"]["conservative_odds"] == 1.9375
    read_at = now + timedelta(minutes=30)
    forecasts = automated_wettfinder_forecasts(state_path, now=read_at)
    signals = automated_wettfinder_signals(state_path, now=read_at)
    assert [row.key for row in forecasts] == [model_selection["key"]]
    assert [row.key for row in signals] == [tip["key"]]


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
                    "fixture": {"id": 1},
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
                            "name": name,
                            "bets": [
                                {
                                    "name": "Both Teams Score",
                                    "values": [{"value": "Yes", "odd": odds}],
                                }
                            ],
                        }
                        for name, odds in (
                            ("Book A", "1.20"),
                            ("Book B", "1.22"),
                            ("Book C", "1.24"),
                            ("Book D", "1.26"),
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
        "Fussball",
        "E-Sport",
    }
    football_model = next(
        row for row in document["model_candidates"] if row["sport"] == "Fussball"
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
                    "fixture": {"id": 4},
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
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


def test_runner_never_uses_alternative_price_to_replace_model_pick(tmp_path):
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
        item.context = {"passed": True, "blocked_reasons": []}

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
                    "fixture": {"id": 1},
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
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
    ]
    assert document["sources"]["football"]["price_checked_count"] == 1
    assert document["sources"]["football"]["price_fixture_count"] == 1
    assert document["sources"]["football"]["price_status_counts"] == {
        "TOO_LOW": 1,
    }
    assert [row["candidate_id"] for row in document["model_candidates"]] == [
        "fixture-1-home"
    ]
    assert document["candidates"] == []


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
                    "fixture": {"id": 1},
                    "update": scanned.isoformat(),
                    "bookmakers": [
                        {
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
    assert refresh_calls == [([1], now + timedelta(minutes=30))]
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
                QuotePoint(f"Book {index}", price)
                for index, price in enumerate(ordered, start=1)
            ),
            provider_event_id="provider-tennis-model-1",
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
        "Fussball",
        "Tennis",
        "E-Sport",
    }
    assert {row["sport"] for row in second["model_candidates"]} == {
        "Fussball",
        "Tennis",
        "E-Sport",
    }
    priced = {row["sport"]: row for row in second["model_candidates"]}
    assert priced["Tennis"]["reference_price_status"] == "PLAYABLE"
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

    document = run_wettfinder(
        now=now,
        state_path=tmp_path / "wettfinder.json",
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
    assert secret not in str(document)


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


def test_runner_keeps_basis_forecast_visible_but_never_promotes_it(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    useful = _challenge_candidate(now + timedelta(hours=5))
    useful.context = {"passed": True, "blocked_reasons": []}
    basis = replace(
        useful,
        candidate_id="fixture-1-away-under-1-5",
        market_key="AWAY_UNDER_1_5",
        market="Team 2 Gesamttore",
        selection="Unter 1.5",
    )
    basis.context = {"passed": True, "blocked_reasons": []}
    snapshot = _football_snapshot(now)
    snapshot["forecast_shortlist"] = [useful]
    snapshot["basis_forecasts"] = [basis]

    def quote_loader(rows):
        basis_row = next(
            row for row in rows if row["candidate_id"] == basis.candidate_id
        )
        prices = (2.40, 2.45, 2.50, 2.55)
        return {
            basis.candidate_id: MarketConsensus(
                fixture_id=1,
                candidate_id=basis.candidate_id,
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
                    QuotePoint(f"Book {index}", price)
                    for index, price in enumerate(prices, start=1)
                ),
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
    assert set(by_id) == {useful.candidate_id, basis.candidate_id}
    assert by_id[basis.candidate_id]["is_basic_forecast"] is True
    assert by_id[basis.candidate_id]["reference_price_status"] == "PLAYABLE"
    assert document["football"]["basis_candidates"][0]["candidate_id"] == (
        basis.candidate_id
    )
    assert document["sources"]["football"]["price_checked_count"] == 2
    assert document["candidates"] == []


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
                    "fixture": {"id": 1},
                    "update": observed_at.isoformat(),
                    "bookmakers": [
                        {
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
                    "fixture": {"id": 1},
                    "update": now.isoformat(),
                    "bookmakers": [
                        {
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
