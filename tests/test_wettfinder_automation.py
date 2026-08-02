from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from config_loader import AppConfig
from ev_signal_sources import ModelSignal
from wettfinder_automation import (
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
    return {
        "scanned_at": now.isoformat(),
        "fixtures_found": 2,
        "fixture_kickoffs": [
            "2030-01-01T15:00:00+00:00",
            "2030-01-01T18:00:00+00:00",
        ],
        "shortlist": [
            {
                "candidate_id": "fixture-1-over",
                "fixture_id": 1,
                "league_name": "Test League",
                "kickoff": "2030-01-01T15:00:00+00:00",
                "home_team": "FC Alpha",
                "away_team": "FC Beta",
                "market": "Tore",
                "selection": "Ueber 1.5",
                "probability": 0.72,
                "conservative_probability": 0.63,
                "evidence_score": 84.0,
                "model_spread_pp": 3.2,
            }
        ],
        "errors": [],
    }


def test_target_date_switches_at_2300_zurich():
    before = datetime(2030, 1, 1, 21, 59, tzinfo=UTC)
    after = datetime(2030, 1, 1, 22, 0, tzinfo=UTC)

    assert target_search_date(before) == date(2030, 1, 1)
    assert target_search_date(after) == date(2030, 1, 2)


def test_football_due_uses_event_distance_instead_of_blind_hourly_scan():
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
    assert far.minimum_gap == timedelta(hours=12)
    assert near.due is True
    assert near.minimum_gap == timedelta(minutes=45)


def test_football_due_never_rescans_when_all_known_events_started():
    search_date = date(2030, 1, 1)
    decision = football_due(
        {
            "status": "completed",
            "search_date": search_date.isoformat(),
            "last_attempt_at": "2030-01-01T10:00:00+00:00",
            "fixture_kickoffs": ["2030-01-01T11:00:00+00:00"],
        },
        now=datetime(2030, 1, 1, 12, 0, tzinfo=UTC),
        search_date=search_date,
    )
    assert decision.due is False
    assert decision.reason == "all_known_events_started"


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
    assert second["sources"]["football"]["due_reason"] == "event_window_not_due"
    assert load_state(state_path)["generated_at"] == second["generated_at"]


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
        "blocked_no_validated_model"
    )
