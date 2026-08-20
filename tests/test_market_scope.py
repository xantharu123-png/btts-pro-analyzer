from datetime import date, datetime, timezone
import inspect
from types import SimpleNamespace

import alternative_markets_tab_extended as market_tab
from challenge_engine import market_specs
from market_consensus import MarketConsensus, QuotePoint


def test_every_finder_market_scope_maps_to_supported_model_kinds():
    supported = {spec.kind for spec in market_specs()}
    assert market_tab.FOOTBALL_MARKET_SCOPES["Beste Märkte"] is None
    for label, kinds in market_tab.FOOTBALL_MARKET_SCOPES.items():
        if label == "Beste Märkte":
            continue
        assert kinds
        assert set(kinds) <= supported


def test_market_worker_forwards_selected_market_kinds(monkeypatch):
    provider = object()
    received = {}
    monkeypatch.setattr(
        market_tab,
        "ChallengeDataProvider",
        lambda *_args: provider,
    )

    def fake_scan(
        received_provider,
        league_ids,
        search_date,
        max_fixtures,
        *,
        search_end_date,
        market_kinds,
        progress_cb=None,
    ):
        received.update(
            provider=received_provider,
            leagues=league_ids,
            date=search_date,
            end_date=search_end_date,
            max_fixtures=max_fixtures,
            market_kinds=market_kinds,
        )
        return {"shortlist": []}

    monkeypatch.setattr(market_tab, "scan_daily_challenge", fake_scan)
    market_tab._run_market_scan_worker(
        "api-key",
        None,
        [78],
        date(2030, 1, 2),
        date(2030, 1, 9),
        1200,
        {"league_ids": [78]},
        frozenset({"btts"}),
    )

    assert received == {
        "provider": provider,
        "leagues": [78],
        "date": date(2030, 1, 2),
        "end_date": date(2030, 1, 9),
        "max_fixtures": 1200,
        "market_kinds": {"btts"},
    }


def test_market_worker_rejects_only_the_cheap_market_not_the_fixture(monkeypatch):
    now = datetime.now(timezone.utc)
    favorite = SimpleNamespace(
        candidate_id="fixture-1-home",
        fixture_id=1,
        minimum_odds=1.50,
    )
    alternative = SimpleNamespace(
        candidate_id="fixture-1-under-4-5",
        fixture_id=1,
        minimum_odds=1.50,
    )
    snapshot = {
        "shortlist": [favorite],
        "price_candidates": [favorite, alternative],
        "approved_candidates": 1,
    }
    checked = []
    selection_pool = []

    def quote(candidate, conservative_odds, best_odds):
        return MarketConsensus(
            fixture_id=1,
            candidate_id=candidate.candidate_id,
            market_key="TEST",
            bet_name="Test",
            value_name="Test",
            consensus_odds=conservative_odds,
            conservative_odds=conservative_odds,
            lowest_odds=conservative_odds,
            best_odds=best_odds,
            bookmaker_count=4,
            quoted_at=now.isoformat(),
            fetched_at=now.isoformat(),
            source="test",
            points=(
                QuotePoint("A", conservative_odds),
                QuotePoint("B", conservative_odds),
                QuotePoint("C", best_odds),
                QuotePoint("D", best_odds),
            ),
        )

    def fetch_quotes(_api_key, rows):
        checked.extend(rows)
        return {
            favorite.candidate_id: quote(favorite, 1.25, 1.30),
            alternative.candidate_id: quote(alternative, 1.80, 1.85),
        }, []

    def choose_after_price(rows, max_candidates):
        selection_pool.extend(rows)
        return list(rows)[:max_candidates]

    monkeypatch.setattr(
        market_tab,
        "ChallengeDataProvider",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        market_tab,
        "scan_daily_challenge",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(market_tab, "fetch_football_consensus", fetch_quotes)
    monkeypatch.setattr(market_tab, "select_shortlist", choose_after_price)

    result = market_tab._run_market_scan_worker(
        "api-key",
        None,
        [78],
        date(2030, 1, 2),
        date(2030, 1, 2),
        1200,
        {"league_ids": [78]},
    )["challenge"]

    assert checked == [favorite, alternative]
    assert selection_pool == [alternative]
    assert result["model_shortlist"] == [favorite]
    assert result["shortlist"] == [alternative]
    assert result["price_checked_count"] == 2
    assert result["price_fixture_count"] == 1
    assert result["price_status_counts"] == {
        "TOO_LOW": 1,
        "PLAYABLE": 1,
    }
    assert market_tab._price_check_summary(result) == (
        "Preisprüfung: 2 Modellmärkte aus 1 Spiel geprüft · "
        "1 unter der Mindestquote · 1 preislich spielbar"
    )


def test_market_worker_keeps_model_selection_when_no_price_is_playable(monkeypatch):
    candidate = SimpleNamespace(
        candidate_id="fixture-7-home",
        fixture_id=7,
        minimum_odds=1.80,
    )
    snapshot = {
        "shortlist": [candidate],
        "price_candidates": [candidate],
    }
    now = datetime.now(timezone.utc).isoformat()
    quote = MarketConsensus(
        fixture_id=7,
        candidate_id=candidate.candidate_id,
        market_key="HOME",
        bet_name="Winner",
        value_name="Home",
        consensus_odds=1.60,
        conservative_odds=1.60,
        lowest_odds=1.55,
        best_odds=1.70,
        bookmaker_count=3,
        quoted_at=now,
        fetched_at=now,
        source="test",
        points=(
            QuotePoint("A", 1.55),
            QuotePoint("B", 1.60),
            QuotePoint("C", 1.70),
        ),
    )
    monkeypatch.setattr(market_tab, "ChallengeDataProvider", lambda *_args: object())
    monkeypatch.setattr(
        market_tab,
        "scan_daily_challenge",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        market_tab,
        "fetch_football_consensus",
        lambda *_args, **_kwargs: ({candidate.candidate_id: quote}, []),
    )

    result = market_tab._run_market_scan_worker(
        "api-key",
        None,
        [78],
        date(2030, 1, 2),
        date(2030, 1, 2),
        1200,
        {"league_ids": [78]},
    )["challenge"]

    assert result["model_shortlist"] == [candidate]
    assert result["shortlist"] == []
    assert result["price_status_counts"] == {"TOO_LOW": 1}


def test_consumer_empty_state_contains_no_pipeline_diagnostics():
    headline, detail = market_tab._consumer_no_tip_copy(
        {
            "fixtures_found": 205,
            "fixtures_modeled": 144,
            "base_candidates": 119,
            "model_blocked_counts": {"Walk-forward-Gate": 5947},
            "coverage_notices": ["xG Liga 39: 0/380"],
        },
        day_label="19.08.2026 bis 22.08.2026",
    )

    visible = f"{headline} {detail}"
    assert "aktuell kein passender Tipp" in visible
    for internal_term in (
        "Walk-forward",
        "Marktkandidaten",
        "UEFA-Transfergate",
        "xG Liga",
        "Preisprüfung",
    ):
        assert internal_term not in visible


def test_public_market_renderer_does_not_render_internal_scan_diagnostics():
    source = inspect.getsource(market_tab.create_alternative_markets_tab_extended)
    assert "render_football_scan_diagnostics" not in source
    assert 'st.expander("Suchprüfung"' not in source
    assert "Hauptsperre:" not in source
    assert "job.get('error')" not in source
