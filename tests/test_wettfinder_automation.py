from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from challenge_engine import (
    MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
    ChallengeCandidate,
    ValidationMetrics,
)
from config_loader import AppConfig
from ev_signal_sources import AUTOMATED_WETTFINDER_VERSION, ModelSignal
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from wettfinder_automation import (
    AUTOMATION_VERSION,
    _default_football_scan,
    _football_candidate_record,
    football_context_due_fixture_ids,
    football_due,
    load_state,
    run_wettfinder,
    select_candidates,
    target_search_date,
)


UTC = timezone.utc


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
    assert len(first["candidates"]) == 2
    assert second["sources"]["football"]["due_reason"] == "daily_discovery_current"
    assert load_state(state_path)["generated_at"] == second["generated_at"]


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

    assert scan_calls == 1
    assert refreshed["football"]["base_candidates"] == 2
    assert refreshed["football"]["blocked_counts"] == {
        "Transfer nicht validiert": 4
    }
    assert refresh_calls == [([1], now + timedelta(minutes=30))]
    assert refreshed["sources"]["football"]["context_status"] == "refreshed"
    assert len(refreshed["candidates"]) == 1


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
