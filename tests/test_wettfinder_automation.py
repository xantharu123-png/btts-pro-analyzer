from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from challenge_engine import (
    MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
    ChallengeCandidate,
    ValidationMetrics,
)
from config_loader import AppConfig
from ev_signal_sources import AUTOMATED_WETTFINDER_VERSION, ModelSignal
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from market_consensus import parse_fixture_consensus
from wettfinder_automation import (
    AUTOMATION_VERSION,
    _default_football_scan,
    _football_candidate_record,
    _football_state_from_snapshot,
    _merge_context_refresh,
    _signal_record,
    football_context_due_fixture_ids,
    football_due,
    load_state,
    run_wettfinder,
    select_candidates,
    select_price_check_candidates,
    target_search_date,
)


UTC = timezone.utc


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
    candidate.context = {"passed": True, "blocked_reasons": []}
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


def test_football_record_rejects_unvalidated_cross_competition_model():
    candidate = _challenge_candidate(datetime(2030, 1, 1, 15, 0, tzinfo=UTC))
    candidate.context = {"passed": True, "blocked_reasons": []}
    candidate.model_scope = MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED

    assert _football_candidate_record(candidate) is None


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
    assert document["sources"]["football"]["candidate_count"] == 0
    assert document["sources"]["football"]["price_checked_count"] == 0
    assert document["candidates"] == []


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
        state_path=tmp_path / "wettfinder.json",
        config=AppConfig(api_football_key="test"),
        football_scanner=lambda _search_date: _football_snapshot(now),
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
    )

    assert document["bookmaker_data_used"] is True
    assert document["sources"]["football"]["reference_quote_count"] == 1
    tip = document["candidates"][0]
    assert document["quote_required"] is True
    assert tip["status"] == "RECOMMENDED"
    assert tip["reference_price_status"] == "PLAYABLE"
    assert tip["reference_quote"]["bookmaker_count"] == 4
    assert tip["reference_quote"]["conservative_odds"] == 1.9375


def test_runner_never_publishes_unpriced_or_too_low_model_candidates(tmp_path):
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    level_up = ModelSignal(
        key="esports-level-up",
        label="DOTA2 · Level UP vs Team Lynx · Sieg Level UP",
        probability=0.6815,
        probability_haircut=0.2572,
        evidence_stage="SHADOW",
        policy_version="risk-ev-3pct-v1:subgraph-elo-v2",
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
    assert document["bookmaker_data_used"] is True
    assert document["sources"]["football"]["price_status_counts"] == {
        "TOO_LOW": 1
    }
    assert document["sources"]["esports"]["candidate_count"] == 1


def test_runner_checks_full_football_pool_before_selecting_top_three(tmp_path):
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
        candidate.context = {"passed": True, "blocked_reasons": []}
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
    assert [row["fixture_id"] for row in document["candidates"]] == [4]


def test_runner_rejects_only_the_too_cheap_market_not_the_fixture(tmp_path):
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
        "fixture-1-under-4-5",
    ]
    assert document["sources"]["football"]["price_checked_count"] == 2
    assert document["sources"]["football"]["price_fixture_count"] == 1
    assert document["sources"]["football"]["price_status_counts"] == {
        "TOO_LOW": 1,
        "PLAYABLE": 1,
    }
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
