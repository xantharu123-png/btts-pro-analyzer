from datetime import date, datetime, timezone
import inspect
from types import SimpleNamespace

import alternative_markets_tab_extended as market_tab
import bet_finder_ui
from challenge_engine import market_specs
from market_consensus import (
    MarketConsensus,
    QuotePoint,
    REFERENCE_SOURCE,
    exact_market_target,
)


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
        market_key="RESULT_HOME",
        minimum_odds=1.50,
    )
    alternative = SimpleNamespace(
        candidate_id="fixture-1-under-4-5",
        fixture_id=1,
        market_key="TOTAL_UNDER_4_5",
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
        bet_name, value_name = exact_market_target(candidate.market_key)
        return MarketConsensus(
            fixture_id=1,
            candidate_id=candidate.candidate_id,
            market_key=candidate.market_key,
            bet_name=bet_name,
            value_name=value_name,
            consensus_odds=conservative_odds,
            conservative_odds=conservative_odds,
            lowest_odds=conservative_odds,
            best_odds=best_odds,
            bookmaker_count=4,
            quoted_at=now.isoformat(),
            fetched_at=now.isoformat(),
            source=REFERENCE_SOURCE,
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
    assert selection_pool == []
    assert result["model_shortlist"] == [favorite]
    assert result["shortlist"] == []
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
        market_key="RESULT_HOME",
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
        market_key=candidate.market_key,
        bet_name="Match Winner",
        value_name="Home",
        consensus_odds=1.60,
        conservative_odds=1.60,
        lowest_odds=1.55,
        best_odds=1.70,
        bookmaker_count=3,
        quoted_at=now,
        fetched_at=now,
        source=REFERENCE_SOURCE,
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


def test_market_worker_prices_basis_for_annotation_without_strict_promotion(
    monkeypatch,
):
    forecast = SimpleNamespace(
        candidate_id="fixture-7-result-total",
        fixture_id=7,
        minimum_odds=1.80,
    )
    basis = SimpleNamespace(
        candidate_id="fixture-7-away-under-2-5",
        fixture_id=7,
        market_key="AWAY_UNDER_2_5",
        minimum_odds=1.40,
    )
    snapshot = {
        "shortlist": [],
        "forecast_shortlist": [forecast],
        "basis_forecasts": [basis],
        "price_candidates": [],
    }
    checked = []
    now = datetime.now(timezone.utc)
    basis_quote = MarketConsensus(
        fixture_id=7,
        candidate_id=basis.candidate_id,
        market_key=basis.market_key,
        bet_name="Total - Away",
        value_name="Under 2.5",
        consensus_odds=1.50,
        conservative_odds=1.50,
        lowest_odds=1.50,
        best_odds=1.50,
        bookmaker_count=4,
        quoted_at=now.isoformat(),
        fetched_at=now.isoformat(),
        source=REFERENCE_SOURCE,
        points=(
            QuotePoint("A", 1.50),
            QuotePoint("B", 1.50),
            QuotePoint("C", 1.50),
            QuotePoint("D", 1.50),
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
        lambda _api_key, rows: (
            checked.extend(rows) or {basis.candidate_id: basis_quote},
            [],
        ),
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

    assert result["model_shortlist"] == [forecast, basis]
    assert checked == [basis]
    assert result["price_candidates"] == []
    assert result["shortlist"] == []
    assert basis.candidate_id in result["reference_quotes"]
    assert result["price_status_counts"] == {"PLAYABLE": 1}


def test_consumer_merge_keeps_model_order_beyond_featured_three():
    priced = SimpleNamespace(candidate_id="fixture-1-under", fixture_id=1)
    same_fixture_model = SimpleNamespace(candidate_id="fixture-1-home", fixture_id=1)
    same_fixture_basis = SimpleNamespace(candidate_id="fixture-1-basis", fixture_id=1)
    unpriced_two = SimpleNamespace(candidate_id="fixture-2-home", fixture_id=2)
    unpriced_three = SimpleNamespace(candidate_id="fixture-3-btts", fixture_id=3)
    overflow = SimpleNamespace(candidate_id="fixture-4-over", fixture_id=4)

    displayed = market_tab._merge_consumer_market_rows(
        [priced],
        [
            same_fixture_model,
            same_fixture_basis,
            unpriced_two,
            unpriced_three,
            overflow,
        ],
    )

    assert displayed == [
        same_fixture_model,
        same_fixture_basis,
        unpriced_two,
        unpriced_three,
        overflow,
    ]


def test_consumer_partition_relegates_only_confirmed_extreme_short_prices():
    now = datetime.now(timezone.utc)
    extreme = SimpleNamespace(
        candidate_id="sporting-alverca-away-under-1-5",
        minimum_odds=1.79,
    )
    missing = SimpleNamespace(candidate_id="missing-price", minimum_odds=1.80)
    ordinary_too_low = SimpleNamespace(
        candidate_id="ordinary-too-low",
        minimum_odds=1.79,
    )
    exact_cutoff = SimpleNamespace(
        candidate_id="exact-extreme-short-cutoff",
        minimum_odds=1.79,
    )
    thin_short = SimpleNamespace(candidate_id="thin-short", minimum_odds=1.79)
    stale_short = SimpleNamespace(candidate_id="stale-short", minimum_odds=1.79)

    def quote(candidate, odds, best, *, fetched_at=now, prices=None):
        if prices is None:
            prices = (odds, odds, best, best)
        return MarketConsensus(
            fixture_id=1,
            candidate_id=candidate.candidate_id,
            market_key="AWAY_UNDER_1_5",
            bet_name="Team Total",
            value_name="Away Under 1.5",
            consensus_odds=odds,
            conservative_odds=odds,
            lowest_odds=odds,
            best_odds=best,
            bookmaker_count=len(prices),
            quoted_at=fetched_at.isoformat(),
            fetched_at=fetched_at.isoformat(),
            source="test",
            points=tuple(
                QuotePoint(chr(ord("A") + index), price)
                for index, price in enumerate(prices)
            ),
        )

    quotes = {
        extreme.candidate_id: quote(extreme, 1.14, 1.17),
        ordinary_too_low.candidate_id: quote(ordinary_too_low, 1.45, 1.51),
        exact_cutoff.candidate_id: quote(exact_cutoff, 1.20, 1.25),
        thin_short.candidate_id: quote(
            thin_short,
            1.14,
            1.17,
            prices=(1.14, 1.17),
        ),
        stale_short.candidate_id: quote(
            stale_short,
            1.14,
            1.17,
            fetched_at=now.replace(year=now.year - 1),
        ),
    }

    primary, extreme_short = bet_finder_ui.partition_consumer_forecasts(
        [
            extreme,
            missing,
            ordinary_too_low,
            exact_cutoff,
            thin_short,
            stale_short,
        ],
        quote_for=lambda candidate: quotes.get(candidate.candidate_id),
        now=now,
    )

    assert primary == [
        missing,
        ordinary_too_low,
        exact_cutoff,
        thin_short,
        stale_short,
    ]
    assert extreme_short == [extreme]
    assert sorted(primary + extreme_short, key=lambda row: row.candidate_id) == sorted(
        [
            extreme,
            missing,
            ordinary_too_low,
            exact_cutoff,
            thin_short,
            stale_short,
        ],
        key=lambda row: row.candidate_id,
    )


def test_featured_partition_allows_team_under_one_five_without_repetition():
    repeated_team_totals = [
        SimpleNamespace(
            candidate_id=f"away-under-{index}",
            fixture_id=index,
            market_key="AWAY_UNDER_1_5",
            market="Team 2 Gesamttore",
            selection="Unter 1.5",
            context={"release_context_complete": False},
        )
        for index in range(1, 4)
    ]
    osasuna = SimpleNamespace(
        candidate_id="osasuna-result-total",
        fixture_id=4,
        market_key="RESULT_TOTAL_1X_UNDER_3_5",
        market="Resultat & Gesamttore 3,5",
        selection="1X und Unter 3,5",
        context={"release_context_complete": True},
    )

    featured, additional = bet_finder_ui.partition_consumer_featured_forecasts(
        [*repeated_team_totals, osasuna],
        max_featured=3,
    )

    assert featured == [osasuna, repeated_team_totals[0]]
    assert additional == repeated_team_totals[1:]
    assert featured + additional == [
        osasuna,
        repeated_team_totals[0],
        repeated_team_totals[1],
        repeated_team_totals[2],
    ]


def test_featured_partition_allows_only_one_selection_per_fixture():
    first_fixture_primary = SimpleNamespace(
        candidate_id="fixture-1-result-total",
        fixture_id=1,
        market_key="RESULT_TOTAL_1X_UNDER_3_5",
        market="Resultat & Gesamttore 3,5",
        selection="1X und Unter 3,5",
        context={"release_context_complete": True},
    )
    same_fixture_other_market = SimpleNamespace(
        candidate_id="fixture-1-btts",
        fixture_id=1,
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
        context={"release_context_complete": True},
    )
    second_fixture = SimpleNamespace(
        candidate_id="fixture-2-result",
        fixture_id=2,
        market_key="RESULT_HOME",
        market="Endergebnis",
        selection="Heimsieg",
        context={"release_context_complete": True},
    )

    featured, additional = bet_finder_ui.partition_consumer_featured_forecasts(
        [first_fixture_primary, same_fixture_other_market, second_fixture],
        max_featured=3,
    )

    assert featured == [first_fixture_primary, second_fixture]
    assert additional == [same_fixture_other_market]


def test_featured_partition_allows_only_one_selection_per_market_family():
    home_win = SimpleNamespace(
        candidate_id="fixture-1-home",
        fixture_id=1,
        market_key="RESULT_HOME",
        market="Endergebnis",
        selection="Heimsieg",
        context={"release_context_complete": True},
    )
    away_win = SimpleNamespace(
        candidate_id="fixture-2-away",
        fixture_id=2,
        market_key="RESULT_AWAY",
        market="Endergebnis",
        selection="Auswärtssieg",
        context={"release_context_complete": True},
    )
    btts = SimpleNamespace(
        candidate_id="fixture-3-btts",
        fixture_id=3,
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
        context={"release_context_complete": True},
    )

    featured, additional = bet_finder_ui.partition_consumer_featured_forecasts(
        [home_win, away_win, btts],
        max_featured=3,
    )

    assert featured == [home_win, btts]
    assert additional == [away_win]


def test_market_worker_keeps_fully_checked_catalog_beyond_three(monkeypatch):
    catalog = [
        SimpleNamespace(
            candidate_id=f"fixture-{index}-core",
            fixture_id=index,
            minimum_odds=1.80,
        )
        for index in range(1, 9)
    ]
    monkeypatch.setattr(market_tab, "ChallengeDataProvider", lambda *_args: object())
    monkeypatch.setattr(
        market_tab,
        "scan_daily_challenge",
        lambda *_args, **_kwargs: {
            "forecast_shortlist": catalog,
            "shortlist": [],
            "price_candidates": [],
        },
    )
    monkeypatch.setattr(
        market_tab,
        "fetch_football_consensus",
        lambda *_args, **_kwargs: ({}, []),
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

    assert result["model_shortlist"] == catalog
    assert result["shortlist"] == []


def test_consumer_empty_state_contains_no_pipeline_diagnostics():
    evidence, message, incomplete = market_tab._consumer_no_tip_copy(
        {
            "fixtures_found": 205,
            "fixtures_modeled": 144,
            "base_candidates": 119,
            "base_fixture_count": 21,
            "context_verified_fixtures": 20,
            "context_unchecked_fixtures": 1,
            "model_blocked_counts": {"Walk-forward-Gate": 5947},
            "coverage_notices": ["xG Liga 39: 0/380"],
        },
        day_label="19.08.2026 bis 22.08.2026",
    )

    visible = f"{evidence} {message}"
    assert "205 Spiele gefunden" in evidence
    assert "144 modelliert" in evidence
    assert "21 Spiele in der engeren Auswahl" in evidence
    assert "20 mit verfügbaren Kontextdaten geprüft" in evidence
    assert "Für 1 weiteres Spiel" in message
    assert "Quote war nicht der Ablehnungsgrund" in message
    assert incomplete is True
    for internal_term in (
        "Walk-forward",
        "Marktkandidaten",
        "UEFA-Transfergate",
        "xG Liga",
        "Preisprüfung",
    ):
        assert internal_term not in visible


def test_consumer_empty_state_distinguishes_model_zero_from_price_zero():
    evidence, message, incomplete = market_tab._consumer_no_tip_copy(
        {
            "fixtures_found": 40,
            "fixtures_modeled": 40,
            "base_candidates": 0,
            "base_fixture_count": 0,
            "price_checked_count": 0,
        },
        day_label="Heute",
    )

    assert evidence == "Heute · 40 Spiele gefunden · 40 modelliert"
    assert "engere Auswahl" in message
    assert "Quote wurde deshalb noch nicht geprüft" in message
    assert incomplete is False


def test_consumer_empty_state_marks_missing_context_data_as_incomplete():
    _, message, incomplete = market_tab._consumer_no_tip_copy(
        {
            "fixtures_found": 12,
            "fixtures_modeled": 12,
            "base_fixture_count": 3,
            "context_verified_fixtures": 2,
            "context_data_incomplete_fixtures": 1,
        },
        day_label="Heute",
    )

    assert incomplete is True
    assert "benötigten Daten war nicht vollständig" in message
    assert "negative Aussage" in message


def test_consumer_empty_state_never_turns_provider_failure_into_empty_schedule():
    evidence, message, incomplete = market_tab._consumer_no_tip_copy(
        {
            "fixtures_found": 0,
            "fixtures_modeled": 0,
            "operational_error_count": 3,
        },
        day_label="Heute",
    )

    assert evidence == "Heute · 0 Spiele gefunden · 0 modelliert"
    assert "nicht vollständig abgeschlossen" in message
    assert "keine anstehenden Spiele" not in message
    assert incomplete is True


def test_manual_scan_audit_is_sanitized_but_keeps_decision_counts():
    payload = market_tab._market_audit_payload(
        {
            "scope": {"league_ids": [39], "date": "2030-01-02"},
            "challenge": {
                "scanned_at": "2030-01-02T10:00:00+00:00",
                "fixtures_found": 5,
                "fixtures_modeled": 4,
                "base_fixture_count": 2,
                "context_verified_fixtures": 1,
                "context_data_incomplete_fixtures": 1,
                "context_scope_complete": False,
                "price_checked_at": "2030-01-02T10:01:00+00:00",
                "model_blocked_counts": {"internal rule": 9},
                "context_blocked_counts": {"internal context": 2},
                "operational_errors": ["secret provider detail"],
                "quote_errors": ["secret quote detail"],
            },
        }
    )

    assert payload is not None
    assert payload["status"] == "data_incomplete"
    assert payload["fixtures_found"] == 5
    assert payload["context_verified_fixtures"] == 1
    assert payload["operational_error_count"] == 1
    assert payload["price_checked_at"] == "2030-01-02T10:01:00+00:00"
    assert payload["model_blocked_counts"] == {"internal rule": 9}
    assert "secret provider detail" not in repr(payload)
    assert "secret quote detail" not in repr(payload)


def test_manual_scan_audit_calls_unchecked_scope_partial():
    payload = market_tab._market_audit_payload(
        {
            "scope": {},
            "challenge": {
                "context_scope_complete": False,
                "context_unchecked_fixtures": 1,
                "operational_errors": [],
            },
        }
    )

    assert payload is not None
    assert payload["status"] == "partial"


def test_manual_scan_audit_calls_unmodeled_fixture_scope_partial():
    payload = market_tab._market_audit_payload(
        {
            "scope": {},
            "challenge": {
                "fixtures_found": 5,
                "fixtures_modeled": 4,
                "context_scope_complete": True,
                "operational_errors": [],
            },
        }
    )

    assert payload is not None
    assert payload["status"] == "partial"


def test_partial_manual_scan_keeps_candidates_but_discloses_incomplete_scope():
    message = market_tab._consumer_partial_scope_notice(
        {"operational_error_count": 2},
        has_candidates=True,
    )

    assert message is not None
    assert "nur teilweise abgeschlossen" in message
    assert "gesamte gewählte Suchumfang" in message
    assert market_tab._consumer_partial_scope_notice(
        {"operational_error_count": 2},
        has_candidates=False,
    ) is None


def test_candidate_from_unchecked_context_scope_has_consumer_warning():
    message = market_tab._consumer_partial_scope_notice(
        {
            "fixtures_found": 21,
            "fixtures_modeled": 21,
            "context_unchecked_fixtures": 1,
            "context_scope_complete": False,
        },
        has_candidates=True,
    )

    assert message is not None
    assert "gesamte gewählte Suchumfang ist nicht vollständig belegt" in message


def test_public_market_renderer_does_not_render_internal_scan_diagnostics():
    source = inspect.getsource(market_tab.create_alternative_markets_tab_extended)
    assert "render_football_scan_diagnostics" not in source
    assert 'st.expander("Suchprüfung"' not in source
    assert "Hauptsperre:" not in source
    assert "job.get('error')" not in source
