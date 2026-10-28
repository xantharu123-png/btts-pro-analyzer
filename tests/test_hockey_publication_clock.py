"""Whole daily artifact after a slow research source, with no provider I/O.

The actual football price parser and actual hockey model produce the fixture
rows. These tests prove publication-clock consistency, not live league access,
predictive quality or permission to place a bet.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from config_loader import AppConfig
from ev_signal_sources import (
    _load_automated_wettfinder_document,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
)
from market_consensus import parse_fixture_consensus
from riskobet_candidates import adapt_ice_hockey_research
from riskobet_domain import RiskRunSnapshot, RunStatus
from test_api_hockey_integration import NOW as HOCKEY_NOW, api_event, api_history
from test_wettfinder_automation import _challenge_candidate, _football_snapshot
from wettfinder_automation import run_wettfinder


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def _hockey_result(modeled_at):
    shift = NOW - HOCKEY_NOW
    event = api_event()
    event.update(
        starts_at=(NOW + timedelta(hours=6)).isoformat(),
        source_observed_at=modeled_at.isoformat(),
        season=NOW.year,
    )
    history = deepcopy(api_history())
    for row in history:
        row["season"] = NOW.year
        for field in ("start_time", "result_observed_at"):
            row[field] = (datetime.fromisoformat(row[field]) + shift).isoformat()
    return adapt_ice_hockey_research(event, history, modeled_at=modeled_at)


@pytest.mark.parametrize("delay,kickoff_delay,strict_count,football_count,price_status", [
    (timedelta(seconds=1), timedelta(hours=5), 1, 1, "PLAYABLE"),
    (timedelta(minutes=2), timedelta(minutes=1), 0, 0, None),
    # The floor ignores price freshness; a 36-minute research delay keeps the price.
    pytest.param(timedelta(minutes=36), timedelta(hours=5), 0, 1, "STALE", marks=pytest.mark.price_policy("gate")),
], ids=("fresh-control", "kickoff-during-research", "price-expires-during-research"))
def test_slow_research_keeps_entire_artifact_readable_without_renewing_prices(
    tmp_path, delay, kickoff_delay, strict_count, football_count, price_status,
):
    clock = [NOW]
    snapshot = _football_snapshot(NOW)
    candidate = _challenge_candidate(NOW + kickoff_delay)
    candidate.context = dict(snapshot["shortlist"][0].context)
    snapshot.update(
        shortlist=[candidate], discovery_candidates=[candidate],
        fixture_kickoffs=[candidate.kickoff],
    )
    price_calls = []

    def quote_loader(rows):
        price_calls.append(tuple(row["candidate_id"] for row in rows))
        payload = {"response": [{
            "fixture": {"id": candidate.fixture_id, "date": candidate.kickoff},
            "update": NOW.isoformat(),
            "bookmakers": [{
                "id": identity, "name": f"Book {identity}",
                "bets": [{"name": "Both Teams Score", "values": [
                    {"value": "Yes", "odd": "2.05"},
                ]}],
            } for identity in range(1, 5)],
        }]}
        return parse_fixture_consensus(payload, rows, fetched_at=NOW), []

    def risk_runner(**kwargs):
        clock[0] = NOW + delay
        result = _hockey_result(clock[0])
        return RiskRunSnapshot(
            started_at=kwargs["now"], completed_at=clock[0],
            status=RunStatus.COMPLETE, snapshots=(result.snapshot,),
            candidates=result.candidates,
        )

    path = tmp_path / "wettfinder.json"
    document = run_wettfinder(
        state_path=path, clock=lambda: clock[0],
        config=AppConfig(api_football_key="offline-fixture"),
        football_scanner=lambda _day: snapshot,
        football_context_refresher=lambda *_args: {},
        football_quote_loader=quote_loader,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True, riskobet_sources={}, riskobet_runner=risk_runner,
    )

    assert document["generated_at"] == clock[0].isoformat()
    assert price_calls == [(candidate.candidate_id,)]  # No second price scan.
    assert candidate.probability == .72
    assert document["football"]["candidates"][0]["probability"] == .72
    assert len(document["candidates"]) == strict_count
    assert len(document["challenge_release_candidates"]) == strict_count
    source = document["sources"]["football"]
    assert source["published_recommendation_count"] == strict_count
    assert source["challenge_release_candidate_count"] == strict_count
    assert source["published_model_selection_count"] == football_count

    football_rows = [row for row in document["model_candidates"]
                     if row["source"] == "football_challenge"]
    hockey_rows = [row for row in document["model_candidates"]
                   if row["source"] == "team_sport_research"]
    assert len(football_rows) == football_count
    assert len(hockey_rows) == 2
    assert all(row["modeled_at"] == clock[0].isoformat() for row in hockey_rows)
    assert all(row["scheduled_start"] > document["generated_at"] for row in hockey_rows)
    if football_rows:
        row = football_rows[0]
        assert row["probability"] == .72
        assert row["modeled_at"] == NOW.isoformat()
        assert row["input_cutoff_at"] == NOW.isoformat()
        assert row["reference_price_status"] == price_status
        assert row["reference_price_evaluated_at"] == clock[0].isoformat()
        quote = row["reference_quote"]
        assert quote["fetched_at"] == quote["quoted_at"] == NOW.isoformat()
        assert all(point["observed_at"] == NOW.isoformat() for point in quote["points"])
        if price_status != "PLAYABLE":
            assert not any(name in row for name in (
                "reference_quote_source", "reference_quote_executable_odds",
                "reference_quote_bookmaker", "reference_quote_bookmaker_id",
                "reference_quote_observed_at",
            ))

    loaded = _load_automated_wettfinder_document(path, now=clock[0])
    assert loaded is not None
    assert len(automated_wettfinder_forecasts(path, now=clock[0])) == 2 + football_count
    assert len(automated_wettfinder_signals(path, now=clock[0])) == strict_count
