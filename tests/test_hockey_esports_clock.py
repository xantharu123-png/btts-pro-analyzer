"""A slow hockey research batch must not invalidate cached esports prices.

Native provider fixtures are parsed locally. This proves artifact/clock
consistency only, not live price coverage or prediction quality.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

import esports_prices
from config_loader import AppConfig
from ev_signal_sources import (
    _load_automated_wettfinder_document,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
)
from market_consensus import wettfinder_reference_price_status
from riskobet_domain import RiskRunSnapshot, RunStatus
from test_esports_prices import _worker_signal, event
from test_hockey_publication_clock import NOW, _hockey_result
from test_wettfinder_automation import _football_snapshot
from wettfinder_automation import _signal_record, run_wettfinder


@pytest.mark.parametrize("delay,expected_status", [
    (timedelta(seconds=1), "OBSERVED"),
    (timedelta(minutes=2), "UNAVAILABLE"),
], ids=("fresh-observation-control", "observation-expires-during-hockey"))
def test_hockey_completion_rechecks_esports_observation_without_renewal(
    tmp_path, monkeypatch, delay, expected_status,
):
    clock = [NOW]
    observed = NOW - timedelta(hours=23, minutes=59)
    kickoff = (NOW + timedelta(hours=6)).isoformat()
    native = deepcopy(event())
    native["startTime"] = kickoff
    for bookmaker in native["bookmakerOdds"].values():
        for market in bookmaker["markets"].values():
            for outcome in market["outcomes"].values():
                for player in outcome["players"].values():
                    player["changedAt"] = observed.isoformat()
    cache = {
        "schema": "esports-prices-v1", "fetched_at": observed.isoformat(),
        "events": [native],
    }
    signal = replace(_worker_signal(), scheduled_start=kickoff)
    original = _signal_record(signal)
    attachment_calls = []
    initial_quotes = []

    def attach(rows, *, now, path):
        attachment_calls.append(tuple(row["candidate_id"] for row in rows))
        priced = []
        for row in rows:
            quote = esports_prices.load_cached_quote(row, now=now, document=cache)
            assert quote is not None
            assert wettfinder_reference_price_status(
                quote, row["minimum_odds"], candidate=row, now=now,
            ).code == "OBSERVED"
            initial_quotes.append(quote.to_dict())
            priced.append({**row, "reference_quote": quote.to_dict()})
        return priced

    def forbidden_refresh(**_kwargs):
        pytest.fail("publication revalidation must not make another price request")

    original_attach = esports_prices.attach_cached_esports_prices
    monkeypatch.setattr(esports_prices, "attach_cached_esports_prices", attach)
    monkeypatch.setattr(esports_prices, "refresh_esports_prices", forbidden_refresh)
    price_calls = []

    def football_quotes(rows):
        price_calls.append(tuple(row["candidate_id"] for row in rows))
        return {}, []

    def research_runner(**kwargs):
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
        football_scanner=lambda _day: _football_snapshot(NOW),
        football_context_refresher=lambda *_args: {},
        football_quote_loader=football_quotes,
        tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [signal],
        riskobet_enabled=True, riskobet_sources={}, riskobet_runner=research_runner,
    )

    assert document["generated_at"] == clock[0].isoformat()
    assert attachment_calls == [(signal.key,)]
    assert price_calls == [("fixture-1-btts",)]
    rows = [row for row in document["model_candidates"]
            if row["source"] == "esports_shadow"]
    assert len(rows) == 1
    row = rows[0]
    assert row["key"] == row["candidate_id"] == signal.key
    assert row["probability"] == signal.probability == .61
    assert row["fixture_source"] == "pandascore"
    assert row["provider_event_id"] == "123"
    assert row["quote_provider_event_id"] == "native123"
    for name in ("event_identity", "competitor_a", "competitor_b",
                 "selected_competitor", "selection", "market_key",
                 "modeled_at", "input_cutoff_at", "model_version"):
        assert row[name] == original[name]
    assert row["evidence_stage"] == "SHADOW"
    assert row["status"] == "MODEL_SELECTION"
    assert "release_contract" not in row
    assert row["reference_price_status"] == expected_status
    assert row["reference_price_evaluated_at"] == clock[0].isoformat()
    assert row["reference_quote"] == initial_quotes[0]
    quote = row["reference_quote"]
    assert quote["fetched_at"] == quote["quoted_at"] == observed.isoformat()
    assert quote["origin_provider"] == "pandascore"
    assert quote["origin_event_id"] == "123"
    assert all(point["observed_at"] == observed.isoformat()
               for point in quote["points"])
    assert not any(name in row for name in (
        "reference_quote_source", "reference_quote_executable_odds",
        "reference_quote_bookmaker", "reference_quote_bookmaker_id",
        "reference_quote_observed_at",
    ))
    assert document["candidates"] == document["challenge_release_candidates"] == []
    assert document["sources"]["esports"]["published_recommendation_count"] == 0
    assert document["sources"]["esports"]["price_checked_count"] == 0
    hockey = [row for row in document["model_candidates"]
              if row["source"] == "team_sport_research"]
    assert len(hockey) == 2
    assert all(row["modeled_at"] == clock[0].isoformat() for row in hockey)
    assert _load_automated_wettfinder_document(path, now=clock[0]) is not None
    monkeypatch.setattr(esports_prices, "attach_cached_esports_prices", original_attach)
    assert len(automated_wettfinder_forecasts(path, now=clock[0])) == 4
    assert automated_wettfinder_signals(path, now=clock[0]) == []
