"""Manual filters use the complete, price-blind football direction first."""

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import alternative_markets_tab_extended as market_tab
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from manual_search_filters import SearchFilters
from market_consensus import (
    MarketConsensus, QuotePoint, REFERENCE_SOURCE, deserialize_consensus_map,
    exact_market_target, serialize_consensus_map,
)
from test_manual_selection_coherence import _Surface, _row


def _quote(row, price, now, *, observed_at=None):
    bet, value = exact_market_target(row.market_key)
    observed = observed_at or now.isoformat()
    return MarketConsensus(
        fixture_id=row.fixture_id, candidate_id=row.candidate_id,
        market_key=row.market_key, bet_name=bet, value_name=value,
        consensus_odds=price, conservative_odds=price, lowest_odds=price,
        best_odds=price, bookmaker_count=1, quoted_at=observed,
        fetched_at=now.isoformat(), source=REFERENCE_SOURCE,
        points=(QuotePoint("Book", price, bookmaker_id="api-football:7",
                           observed_at=observed),),
        scheduled_start=row.kickoff,
    )


def _render(monkeypatch, rows, *, quotes=None, job_result=None):
    now = datetime.now(timezone.utc)
    scope = market_tab._market_scope_signature(
        list(ALTERNATIVE_MARKET_LEAGUES), now.date(), now.date(),
    )
    scope.update(max_fixtures=market_tab.MAX_SCAN_FIXTURES,
                 market_scope="Beste Märkte", market_kinds=None)
    snapshot = {
        "version": market_tab.MARKET_SNAPSHOT_VERSION,
        "scanned_at": now.isoformat(), "scope": scope,
        "shortlist": rows, "model_shortlist": rows,
        "reference_quotes": serialize_consensus_map(quotes or {}),
        "context_scope_complete": True, "operational_error_count": 0,
    }
    surface, rendered = _Surface(snapshot), []
    monkeypatch.setattr(market_tab, "st", surface)
    monkeypatch.setattr(market_tab, "load_app_config", lambda _st: SimpleNamespace(
        api_football_key="test", weather_key=None,
    ))
    monkeypatch.setattr(market_tab, "_segmented", lambda _label, options, *_: options[0])
    monkeypatch.setattr(market_tab.scan_jobs, "session_scope", lambda _: "test")
    monkeypatch.setattr(market_tab.scan_jobs, "scoped_key", lambda *_: "test")
    monkeypatch.setattr(market_tab.scan_jobs, "get_job", lambda _: (
        {"state": "done", "result": {"scope": scope, "challenge": job_result}}
        if job_result is not None else {"state": "idle"}
    ))
    monkeypatch.setattr(market_tab.scan_jobs, "clear_job", lambda _: None)
    monkeypatch.setattr(market_tab, "_strict_market_candidate", lambda row: SimpleNamespace(
        event_key=row.candidate_id,
    ))
    monkeypatch.setattr(market_tab, "candidate_context_summary", lambda _: "Analyse")
    monkeypatch.setattr(market_tab, "render_model_selection", lambda candidate, **_: (
        rendered.append(candidate.event_key)
    ))

    def render(filters):
        rendered.clear()
        surface.messages.clear()
        market_tab.create_alternative_markets_tab_extended(
            search_date=now.date(), search_end_date=now.date(), embedded=True,
            search_filters=filters,
        )
        return list(rendered)

    return render, surface, snapshot


def test_probability_filter_can_find_a_cached_candidate_after_25(monkeypatch):
    rows = [_row("BTTS_YES", fixture=i, probability=.90) for i in range(1, 31)]
    rows[-1].probability = .61
    render, surface, snapshot = _render(monkeypatch, rows)
    before = deepcopy(snapshot)

    assert render(SearchFilters(probability_min=.60, probability_max=.62)) == [
        "30:BTTS_YES",
    ]
    assert "1 passende Auswahl" in " ".join(surface.messages)
    assert "30 gespeicherten" in " ".join(surface.messages)
    assert snapshot == before


def test_matching_count_is_before_the_visible_25_cap(monkeypatch):
    rows = [_row("BTTS_YES", fixture=i, probability=.61) for i in range(1, 31)]
    render, surface, _ = _render(monkeypatch, rows)

    rendered = render(SearchFilters(probability_min=.60, probability_max=.62))

    assert rendered == [f"{i}:BTTS_YES" for i in range(1, 26)]
    assert "30 passende Auswahlen" in " ".join(surface.messages)
    assert "25 angezeigt" in " ".join(surface.messages)


def test_filter_is_before_eight_markets_per_fixture_cap(monkeypatch):
    keys = ["TOTAL_UNDER_0_5", "TOTAL_UNDER_1_5", "TOTAL_UNDER_2_5",
            "TOTAL_UNDER_3_5", "TOTAL_UNDER_4_5", "HOME_UNDER_0_5",
            "HOME_UNDER_1_5", "HOME_UNDER_2_5", "AWAY_UNDER_0_5"]
    rows = [_row(key, probability=.90) for key in keys]
    rows[-1].probability = .61
    render, _, _ = _render(monkeypatch, rows)

    assert render(SearchFilters(probability_min=.60, probability_max=.62)) == [
        "1:AWAY_UNDER_0_5",
    ]


@pytest.mark.parametrize("filters", [
    SearchFilters(probability_min=.80), SearchFilters(quote_min=2.0, quote_max=3.0),
])
def test_filters_never_replace_the_coherent_direction(monkeypatch, filters):
    now = datetime.now(timezone.utc)
    anchor = _row("RESULT_HOME", complete=True, probability=.55)
    opposing = _row("RESULT_AWAY", probability=.90)
    other = _row("RESULT_AWAY", fixture=2, probability=.85)
    rows = [anchor, opposing, other]
    render, _, _ = _render(monkeypatch, rows, quotes={
        anchor.candidate_id: _quote(anchor, 1.5, now),
        opposing.candidate_id: _quote(opposing, 2.5, now),
        other.candidate_id: _quote(other, 2.3, now),
    })

    assert render(filters) == ["2:RESULT_AWAY"]


def test_market_kind_filter_applies_after_full_direction_and_before_partition(monkeypatch):
    home, opposing = _row("RESULT_HOME", complete=True), _row("RESULT_AWAY")
    total, corners = _row("TOTAL_OVER_1_5"), _row("CORNERS_OVER_5_5")
    render, _, _ = _render(monkeypatch, [home, opposing, total, corners])

    assert render(SearchFilters(market_kind="total")) == ["1:TOTAL_OVER_1_5"]


@pytest.mark.parametrize("bad_binding", ["fixture", "market", "start", "clock", "expired"])
def test_quote_range_rejects_foreign_or_unobserved_prices(monkeypatch, bad_binding):
    now = datetime.now(timezone.utc)
    row = _row("BTTS_YES")
    quote = _quote(row, 2.0, now)
    if bad_binding == "fixture":
        quote = replace(quote, fixture_id=999)
    elif bad_binding == "market":
        quote = replace(quote, market_key="BTTS_NO")
    elif bad_binding == "start":
        quote = replace(quote, scheduled_start="2030-01-03T15:00:00+00:00")
    elif bad_binding == "clock":
        quote = replace(quote, points=(replace(quote.points[0], observed_at=None),))
    else:
        quote = _quote(row, 2.0, now, observed_at=(now - timedelta(days=2)).isoformat())
    render, surface, _ = _render(monkeypatch, [row], quotes={row.candidate_id: quote})

    assert render(SearchFilters(quote_min=1.8, quote_max=2.1)) == []
    assert "Keine gespeicherte Auswahl passt" in " ".join(surface.messages)
    assert "keine Auswahl alle Qualitätsregeln" not in " ".join(surface.messages)


def test_quote_filter_uses_native_best_offer_not_model_minimum_or_consensus(monkeypatch):
    now = datetime.now(timezone.utc)
    row = _row("BTTS_YES", probability=.64)
    row.minimum_odds = 10.0
    quote = _quote(row, 1.5, now)
    quote = replace(quote, consensus_odds=1.85, conservative_odds=1.675,
                    best_odds=2.2, bookmaker_count=2,
                    points=(*quote.points, replace(quote.points[0], bookmaker_id="api-football:8", odds=2.2)))
    render, _, snapshot = _render(monkeypatch, [row], quotes={row.candidate_id: quote})
    before = deepcopy(snapshot)

    assert render(SearchFilters(quote_min=2.2, quote_max=2.2)) == ["1:BTTS_YES"]
    assert snapshot == before


def test_unpriced_rows_remain_without_quote_filter_and_no_rerender_fetch(monkeypatch):
    now = datetime.now(timezone.utc)
    unpriced, cheap, priced = [_row("BTTS_YES", fixture=i) for i in range(1, 4)]
    render, _, snapshot = _render(monkeypatch, [unpriced, cheap, priced], quotes={
        cheap.candidate_id: _quote(cheap, 1.19, now),
        priced.candidate_id: _quote(priced, 2.0, now),
    })
    monkeypatch.setattr(market_tab, "fetch_football_consensus", lambda *_a, **_k: pytest.fail(
        "Changing presentation filters must not fetch prices",
    ))
    before = deepcopy(snapshot)

    assert render(SearchFilters()) == ["1:BTTS_YES", "3:BTTS_YES"]
    assert render(SearchFilters(quote_min=1.2, quote_max=3.0)) == ["3:BTTS_YES"]
    assert render(SearchFilters()) == ["1:BTTS_YES", "3:BTTS_YES"]
    assert snapshot == before


def test_cards_show_the_real_filter_quote_and_never_substitute_model_minimum(monkeypatch):
    now = datetime.now(timezone.utc)
    priced, missing = _row("BTTS_YES"), _row("BTTS_YES", fixture=2)
    priced.minimum_odds, missing.minimum_odds = 10.0, 7.0
    render, surface, _ = _render(monkeypatch, [priced, missing], quotes={
        priced.candidate_id: _quote(priced, 2.2, now),
    })

    assert render(SearchFilters()) == ["1:BTTS_YES", "2:BTTS_YES"]
    assert "Quote 2.20" in surface.messages
    assert "Quote —" in surface.messages
    assert "Quote 10.00" not in surface.messages
    assert "Quote 7.00" not in surface.messages


def test_done_job_cache_retains_all_candidates_for_later_filters(monkeypatch):
    rows = [_row("BTTS_YES", fixture=i, probability=.90) for i in range(1, 31)]
    rows[-1].probability = .61
    challenge = {"scanned_at": datetime.now(timezone.utc).isoformat(),
                 "shortlist": rows, "model_shortlist": rows, "context_scope_complete": True}
    render, surface, _ = _render(monkeypatch, [], job_result=challenge)

    assert render(SearchFilters(probability_min=.60, probability_max=.62)) == ["30:BTTS_YES"]
    saved = surface.session_state["market_bet_finder_snapshot"]
    assert saved["model_shortlist"] == rows
    assert saved["shortlist"] == rows


def test_explicit_worker_prices_the_uncapped_catalog_once_and_keeps_model_values(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [_row("BTTS_YES", fixture=i, probability=.61) for i in range(1, 31)]
    snapshot = {"wettfinder_candidates": rows, "scanned_at": now.isoformat()}
    original = deepcopy(rows)
    checked, selection_limits = [], []
    monkeypatch.setattr(market_tab, "ChallengeDataProvider", lambda *_: object())
    monkeypatch.setattr(market_tab, "scan_daily_challenge", lambda *_a, **_k: snapshot)

    def select(candidates, max_candidates=None, *, max_per_fixture=None):
        selection_limits.append((max_candidates, max_per_fixture))
        return list(candidates) if max_candidates is None else list(candidates)[:max_candidates]

    quote = _quote(rows[-1], 2.0, now)

    def fetch(api_key, candidates, **kwargs):
        checked.append((api_key, list(candidates), kwargs))
        return {rows[-1].candidate_id: quote}, ["one fixture unavailable"]

    monkeypatch.setattr(market_tab, "select_wettfinder_catalog", select)
    monkeypatch.setattr(market_tab, "fetch_football_consensus", fetch)

    result = market_tab._run_market_scan_worker(
        "test-key", None, [78], date(2030, 1, 2), date(2030, 1, 2),
        1200, {"league_ids": [78]},
    )["challenge"]

    assert selection_limits == [(None, None)]
    assert len(checked) == 1
    assert checked[0][0:2] == ("test-key", rows)
    assert result["model_shortlist"] == rows
    assert result["shortlist"] == rows
    assert rows == original
    assert deserialize_consensus_map(result["reference_quotes"]) == {rows[-1].candidate_id: quote}
    assert result["quote_errors"] == ["one fixture unavailable"]
    assert result["price_checked_count"] == 30
    assert result["price_fixture_count"] == 30
    assert result["price_checked_at"] is not None


def test_worker_never_caches_a_quote_from_a_different_fixture_start(monkeypatch):
    now = datetime.now(timezone.utc)
    row = _row("BTTS_YES")
    quote = replace(_quote(row, 2.0, now), scheduled_start="2030-01-03T15:00:00+00:00")
    monkeypatch.setattr(market_tab, "ChallengeDataProvider", lambda *_: object())
    monkeypatch.setattr(market_tab, "scan_daily_challenge", lambda *_a, **_k: {"shortlist": [row]})
    monkeypatch.setattr(market_tab, "select_wettfinder_catalog", lambda rows, **_: list(rows))
    monkeypatch.setattr(market_tab, "fetch_football_consensus", lambda *_a, **_k: ({row.candidate_id: quote}, []))

    result = market_tab._run_market_scan_worker(
        "test-key", None, [78], date(2030, 1, 2), date(2030, 1, 2),
        1200, {"league_ids": [78]},
    )["challenge"]

    assert result["reference_quotes"] == {}
    assert result["model_shortlist"] == [row]


def test_explicit_worker_reuses_budgeted_fixture_batch_without_per_market_requests(monkeypatch):
    import market_consensus
    from api_budget import APIBudgetPriority

    rows = [_row("BTTS_YES", fixture=7), _row("TOTAL_UNDER_4_5", fixture=7),
            _row("BTTS_YES", fixture=8)]
    requested = []
    monkeypatch.setattr(market_tab, "ChallengeDataProvider", lambda *_: object())
    monkeypatch.setattr(market_tab, "scan_daily_challenge", lambda *_a, **_k: {"shortlist": rows})
    monkeypatch.setattr(market_tab, "select_wettfinder_catalog", lambda candidates, **_: list(candidates))

    def request(_url, *, params, priority, **_kwargs):
        requested.append((params, priority))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"response": []})

    monkeypatch.setattr(market_consensus, "api_football_get", request)

    result = market_tab._run_market_scan_worker(
        "test-key", None, [78], date(2030, 1, 2), date(2030, 1, 2),
        1200, {"league_ids": [78]},
    )["challenge"]

    assert requested == [({"fixture": 7}, APIBudgetPriority.RECOMMENDATION),
                         ({"fixture": 8}, APIBudgetPriority.RECOMMENDATION)]
    assert result["model_shortlist"] == rows
    assert result["shortlist"] == rows
    assert result["reference_quotes"] == {}
    assert result["price_fixture_count"] == 2
