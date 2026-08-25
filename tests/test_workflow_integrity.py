from datetime import date, datetime, timedelta, timezone
from dataclasses import replace
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

import app
import alternative_markets_tab_extended as market_tab
from betting_math import BETTING_POLICY_VERSION
from advanced_analyzer import calculate_evidence_score
from alternative_markets import PreMatchAlternativeAnalyzer
from alternative_markets_tab_extended import (
    _api_football_items,
    _market_result_day_label,
    _market_scope_signature,
)
from api_football import APIFootball
from challenge_engine import ChallengeCandidate
from config_loader import AppConfig
from ev_signal_sources import ModelSignal
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from market_consensus import (
    REFERENCE_SOURCE,
    MarketConsensus,
    QuotePoint,
    serialize_consensus_map,
)
from red_card_bot import RED_CARD_MONITORED_LEAGUE_IDS, RedCardBotEnhanced


class _ProgressStub:
    def progress(self, _value, **_kwargs):
        return None

    def empty(self):
        return None

    def caption(self, _value):
        return None


class _RecordingExpander:
    def __init__(self, streamlit, label):
        self.streamlit = streamlit
        self.label = label

    def __enter__(self):
        self.streamlit.expander_stack.append(self.label)
        return self.streamlit

    def __exit__(self, _exc_type, _exc, _traceback):
        assert self.streamlit.expander_stack.pop() == self.label


class _RecordingStreamlit:
    def __init__(self, session_state=None):
        self.session_state = session_state or {}
        self.expanders = []
        self.expander_stack = []
        self.messages = []

    @property
    def current_expander(self):
        return self.expander_stack[-1] if self.expander_stack else None

    def expander(self, label, *, expanded=False):
        self.expanders.append((label, expanded))
        return _RecordingExpander(self, label)

    def button(self, _label, **_kwargs):
        return False

    def caption(self, value):
        self.messages.append(("caption", value))

    def divider(self):
        return None

    def error(self, value):
        self.messages.append(("error", value))

    def info(self, value):
        self.messages.append(("info", value))

    def markdown(self, value):
        self.messages.append(("markdown", value))

    def subheader(self, value):
        self.messages.append(("subheader", value))

    def warning(self, value):
        self.messages.append(("warning", value))


def _extreme_short_quote(candidate_id, now):
    return MarketConsensus(
        fixture_id=1,
        candidate_id=candidate_id,
        market_key="AWAY_UNDER_1_5",
        bet_name="Total - Away",
        value_name="Under 1.5",
        consensus_odds=1.14,
        conservative_odds=1.14,
        lowest_odds=1.12,
        best_odds=1.17,
        bookmaker_count=5,
        quoted_at=now.isoformat(),
        fetched_at=now.isoformat(),
        source=REFERENCE_SOURCE,
        points=(
            QuotePoint(
                "A", 1.12,
                bookmaker_id="api-football:a",
                observed_at=now.isoformat(),
            ),
            QuotePoint(
                "B", 1.14,
                bookmaker_id="api-football:b",
                observed_at=now.isoformat(),
            ),
            QuotePoint(
                "C", 1.14,
                bookmaker_id="api-football:c",
                observed_at=now.isoformat(),
            ),
            QuotePoint(
                "D", 1.16,
                bookmaker_id="api-football:d",
                observed_at=now.isoformat(),
            ),
            QuotePoint(
                "E", 1.17,
                bookmaker_id="api-football:e",
                observed_at=now.isoformat(),
            ),
        ),
        scheduled_start="2030-01-02T15:00:00+00:00",
    )


def _automatic_forecast(key, *, reference_quote=None):
    return ModelSignal(
        key=key,
        label=f"{key}: Team 2 unter 1,5",
        probability=0.741,
        probability_haircut=0.165,
        evidence_stage="SHADOW",
        policy_version=BETTING_POLICY_VERSION,
        detail="Testmodell",
        scheduled_start="2030-01-02T15:00:00+00:00",
        minimum_odds=1.79,
        source="automated_wettfinder_forecast",
        sport="Fußball",
        event_label=f"{key} Heim vs Gast",
        market="Team 2 Gesamttore",
        selection="Unter 1,5",
        reference_quote=(
            reference_quote.to_dict() if reference_quote is not None else None
        ),
        context_summary="Kontext vollständig geprüft",
    )


def _manual_forecast(key, fixture_id):
    return ChallengeCandidate(
        candidate_id=key,
        fixture_id=fixture_id,
        league_id=39,
        league_name="Test League",
        kickoff="2030-01-02T15:00:00+00:00",
        home_team_id=fixture_id * 10,
        away_team_id=fixture_id * 10 + 1,
        home_team=f"Home {fixture_id}",
        away_team=f"Away {fixture_id}",
        market_key="AWAY_UNDER_1_5",
        market="Team 2 Gesamttore",
        selection="Unter 1,5",
        probability=0.741,
        conservative_probability=0.576,
        probability_haircut_pp=16.5,
        model_price=1.35,
        evidence_score=90.0,
        model_spread_pp=2.0,
        expected_home_goals=1.5,
        expected_away_goals=0.8,
        venue_samples=(10, 10),
        form_samples=(6, 6),
        validation=None,
        context={
            "h2h": {"status": "neutral"},
            "injuries": {"status": "observed"},
            "weather": {"status": "passed"},
            "lineups": {"status": "pending"},
            "blocked_reasons": [],
        },
    )


def test_automatic_server_signal_becomes_a_price_check_candidate():
    signal = ModelSignal(
        key="server-1",
        label="A vs B: Sieg A",
        probability=0.65,
        probability_haircut=0.05,
        evidence_stage="SHADOW",
        policy_version=BETTING_POLICY_VERSION,
        detail="Servermodell",
        scheduled_start="2030-01-01T15:00:00+00:00",
        minimum_odds=1.72,
        source="automated_wettfinder",
        sport="Fußball",
        event_label="A vs B",
        market="Doppelte Chance",
        selection="1X",
    )

    candidate = app._automated_signal_candidate(signal)

    assert candidate.event_key == "server-1"
    assert candidate.sport == "Fußball"
    assert candidate.event_label == "A vs B"
    assert candidate.market == "Doppelte Chance"
    assert candidate.selection == "1X"
    assert candidate.model_probability == 65.0
    assert candidate.risk_adjusted_probability == 60.0
    assert candidate.minimum_odds == 1.72


def test_automatic_target_label_uses_the_actual_scan_date(monkeypatch):
    monkeypatch.setattr(app, "zurich_today", lambda: date(2030, 1, 1))

    assert app._automatic_target_label("2030-01-01") == "Heute"
    assert app._automatic_target_label("2030-01-02") == "Morgen"
    assert app._automatic_target_label("2030-01-03") == "03.01.2030"


def test_automatic_surface_overlays_only_the_exact_released_scheduler_row(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    forecast = _automatic_forecast("released-row")
    released = replace(
        forecast,
        evidence_stage="RELEASED",
        source="automated_wettfinder",
    )
    status = SimpleNamespace(
        target_search_date=now.date().isoformat(),
        generated_at=now,
        last_discovery_at=now,
        football_status="completed",
        fixtures_found=1,
        fixtures_modeled=1,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=True,
        operational_error_count=0,
    )
    rendered = []
    monkeypatch.setattr(app, "st", _RecordingStreamlit())
    monkeypatch.setattr(app, "automated_wettfinder_status", lambda: status)
    monkeypatch.setattr(app, "automated_wettfinder_forecasts", lambda: [forecast])
    monkeypatch.setattr(app, "automated_wettfinder_signals", lambda: [released])
    monkeypatch.setattr(
        app,
        "render_price_decision",
        lambda candidate, **_kwargs: rendered.append(candidate),
    )

    app._render_automated_daily_selection()

    assert len(rendered) == 1
    assert rendered[0].event_key == forecast.key
    assert rendered[0].evidence_stage == "RELEASED"


def test_automatic_price_summary_explains_why_models_were_not_published():
    status = SimpleNamespace(
        price_status_counts=(("TOO_LOW", 1), ("UNAVAILABLE", 2)),
        price_checked_count=3,
        approved_candidates=3,
    )

    summary = app._automatic_price_summary(status)

    assert summary == (
        "Preisprüfung: 3 Modellmärkte geprüft · 1 unter der Value-Grenze · "
        "2 ohne exakt passende Marktquote"
    )


def test_automatic_price_summary_reports_pending_exact_prices():
    status = SimpleNamespace(
        price_status_counts=(),
        price_checked_count=0,
        approved_candidates=2,
    )

    assert "keine verwendbare exakte Marktquote" in app._automatic_price_summary(
        status
    )


def test_internal_price_summary_is_not_rendered_in_consumer_daily_selection():
    source = inspect.getsource(app._render_automated_daily_selection)
    assert "_automatic_price_summary" not in source
    assert "_automatic_consumer_summary" not in source
    assert "_automatic_partial_scope_notice" in source
    assert "fixtures_found" not in source
    assert "fixtures_modeled" not in source
    assert "price_status_counts" not in source
    assert "VPS" not in source
    assert "Marktkandidaten" not in source
    assert "Tagestipp {index}" not in source
    assert "status.generated_at" in source
    assert "status.last_discovery_at" in source


def test_automatic_empty_surface_uses_only_short_consumer_copy(monkeypatch):
    now = datetime.now(timezone.utc)
    status = SimpleNamespace(
        target_search_date=now.date().isoformat(),
        generated_at=now,
        last_discovery_at=now,
        football_status="completed",
        fixtures_found=205,
        fixtures_modeled=144,
        base_candidates=0,
        base_fixture_count=0,
        context_verified_fixtures=0,
        context_data_incomplete_fixtures=12,
        context_unchecked_fixtures=49,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=False,
        approved_candidates=0,
        price_checked_count=27,
        price_status_counts=(("TOO_LOW", 18), ("UNAVAILABLE", 9)),
        operational_error_count=0,
    )
    recording_st = _RecordingStreamlit()

    monkeypatch.setattr(app, "st", recording_st)
    monkeypatch.setattr(app, "automated_wettfinder_status", lambda: status)
    monkeypatch.setattr(app, "automated_wettfinder_forecasts", lambda: [])
    monkeypatch.setattr(app, "automated_wettfinder_signals", lambda: [])

    app._render_automated_daily_selection()

    infos = [value for kind, value in recording_st.messages if kind == "info"]
    warnings = [
        value for kind, value in recording_st.messages if kind == "warning"
    ]
    public_text = " ".join(
        str(value) for _kind, value in recording_st.messages
    )
    assert infos == [
        "Für diesen Spieltag liegt aktuell keine passende Fußball-Auswahl vor."
    ]
    assert len(warnings) == 1
    assert warnings[0] == (
        "Ein Teil des Spieltags konnte wegen unvollständiger Daten nicht "
        "zuverlässig bewertet werden."
    )
    assert "61" not in warnings[0]
    assert "Spiele gefunden" not in public_text
    assert "Kontextdaten geprüft" not in public_text
    assert "Preisprüfung" not in public_text
    assert "Value-Grenze" not in public_text


def test_automatic_forecast_surface_shows_one_compact_hint_and_warning(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    status = SimpleNamespace(
        target_search_date=now.date().isoformat(),
        generated_at=now,
        last_discovery_at=now,
        football_status="degraded",
        fixtures_found=40,
        fixtures_modeled=37,
        context_data_incomplete_fixtures=1,
        context_unchecked_fixtures=2,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=False,
        operational_error_count=1,
    )
    recording_st = _RecordingStreamlit()

    monkeypatch.setattr(app, "st", recording_st)
    monkeypatch.setattr(app, "automated_wettfinder_status", lambda: status)
    monkeypatch.setattr(
        app,
        "automated_wettfinder_forecasts",
        lambda: [_automatic_forecast("primary")],
    )
    monkeypatch.setattr(app, "automated_wettfinder_signals", lambda: [])
    monkeypatch.setattr(app, "render_price_decision", lambda *_args, **_kwargs: None)

    app._render_automated_daily_selection()

    infos = [value for kind, value in recording_st.messages if kind == "info"]
    warnings = [
        value for kind, value in recording_st.messages if kind == "warning"
    ]
    public_text = " ".join(
        str(value) for _kind, value in recording_st.messages
    )
    assert infos == [
        "Modellprognosen bleiben unabhängig vom Wettpreis sichtbar. Eine "
        "vorhandene Vergleichsquote wird direkt an der Auswahl eingeordnet."
    ]
    assert len(warnings) == 1
    assert warnings[0] == (
        "Ein Teil des Spieltags konnte wegen unvollständiger Daten nicht "
        "zuverlässig bewertet werden. Die angezeigten Auswahlen wurden "
        "vollständig geprüft."
    )
    assert "3 weitere" not in warnings[0]
    assert "Spiele gefunden" not in public_text
    assert "Tagesumfang" not in public_text
    assert "Preisprüfungen" not in public_text


def test_tennis_failure_does_not_create_a_football_scope_warning(monkeypatch):
    now = datetime.now(timezone.utc)
    status = SimpleNamespace(
        target_search_date=now.date().isoformat(),
        generated_at=now,
        last_discovery_at=now,
        football_status="completed",
        fixtures_found=1,
        fixtures_modeled=1,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=True,
        # Global degraded state comes from Tennis; football itself is healthy.
        operational_error_count=1,
        football_operational_error_count=0,
    )
    recording_st = _RecordingStreamlit()

    monkeypatch.setattr(app, "st", recording_st)
    monkeypatch.setattr(app, "automated_wettfinder_status", lambda: status)
    monkeypatch.setattr(
        app,
        "automated_wettfinder_forecasts",
        lambda: [_automatic_forecast("healthy-football")],
    )
    monkeypatch.setattr(app, "automated_wettfinder_signals", lambda: [])
    monkeypatch.setattr(app, "render_price_decision", lambda *_args, **_kwargs: None)

    app._render_automated_daily_selection()

    warnings = [
        value for kind, value in recording_st.messages if kind == "warning"
    ]
    assert warnings == []


def test_automatic_surface_keeps_primary_order_and_all_forecasts(monkeypatch):
    now = datetime.now(timezone.utc)
    extreme = _automatic_forecast(
        "sporting-alverca-away-under-1-5",
        reference_quote=_extreme_short_quote(
            "sporting-alverca-away-under-1-5",
            now,
        ),
    )
    primary = [
        _automatic_forecast("primary-a"),
        _automatic_forecast("primary-b"),
        _automatic_forecast("primary-c"),
    ]
    forecasts = [extreme, *primary]
    status = SimpleNamespace(
        target_search_date=now.date().isoformat(),
        generated_at=now,
        last_discovery_at=now,
        football_status="completed",
        fixtures_found=4,
        fixtures_modeled=4,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=True,
        operational_error_count=0,
    )
    recording_st = _RecordingStreamlit()
    rendered = []

    monkeypatch.setattr(app, "st", recording_st)
    monkeypatch.setattr(app, "automated_wettfinder_status", lambda: status)
    monkeypatch.setattr(app, "automated_wettfinder_signals", lambda: [])
    monkeypatch.setattr(app, "automated_wettfinder_forecasts", lambda: forecasts)
    monkeypatch.setattr(
        app,
        "render_price_decision",
        lambda candidate, **_kwargs: rendered.append(
            (recording_st.current_expander, candidate.event_key)
        ),
    )

    app._render_automated_daily_selection()

    assert [key for _group, key in rendered] == [
        "primary-a",
        "primary-b",
        "primary-c",
        "sporting-alverca-away-under-1-5",
    ]
    short_group = next(
        (label, expanded)
        for label, expanded in recording_st.expanders
        if label.startswith("Sehr kurze Quoten")
    )
    assert short_group[1] is False
    assert rendered[-1][0] == short_group[0]
    assert len({key for _group, key in rendered}) == len(forecasts)


def test_automatic_surface_promotes_useful_market_and_keeps_all_others(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    team_totals = [
        replace(
            _automatic_forecast(f"away-under-{index}"),
            context_complete=False,
        )
        for index in range(1, 4)
    ]
    osasuna = replace(
        _automatic_forecast("osasuna-result-total"),
        label="Osasuna: 1X und Unter 3,5",
        event_label="Osasuna vs Real Sociedad",
        market="Resultat & Gesamttore 3,5",
        selection="1X und Unter 3,5",
        context_complete=True,
    )
    forecasts = [*team_totals, osasuna]
    status = SimpleNamespace(
        target_search_date=now.date().isoformat(),
        generated_at=now,
        last_discovery_at=now,
        football_status="completed",
        fixtures_found=4,
        fixtures_modeled=4,
        context_data_incomplete_fixtures=3,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=True,
        operational_error_count=0,
    )
    recording_st = _RecordingStreamlit()
    rendered = []

    monkeypatch.setattr(app, "st", recording_st)
    monkeypatch.setattr(app, "automated_wettfinder_status", lambda: status)
    monkeypatch.setattr(app, "automated_wettfinder_signals", lambda: [])
    monkeypatch.setattr(app, "automated_wettfinder_forecasts", lambda: forecasts)
    monkeypatch.setattr(
        app,
        "render_price_decision",
        lambda candidate, **_kwargs: rendered.append(
            (recording_st.current_expander, candidate.event_key)
        ),
    )

    app._render_automated_daily_selection()

    assert [key for _group, key in rendered] == [
        "osasuna-result-total",
        "away-under-1",
        "away-under-2",
        "away-under-3",
    ]
    primary_group = rendered[0][0]
    assert [group for group, _key in rendered[:2]] == [primary_group, primary_group]
    assert all(group != primary_group for group, _key in rendered[2:])
    assert all(
        str(group).startswith("Weitere Märkte zu ")
        for group, _key in rendered[2:]
    )
    assert len({key for _group, key in rendered}) == len(forecasts)


def test_manual_surface_keeps_primary_order_and_all_forecasts(monkeypatch):
    now = datetime.now(timezone.utc)
    extreme = _manual_forecast("sporting-alverca-away-under-1-5", 1)
    primary = [
        _manual_forecast("primary-a", 2),
        _manual_forecast("primary-b", 3),
        _manual_forecast("primary-c", 4),
    ]
    forecasts = [extreme, *primary]
    search_date = now.date()
    available_leagues = list(ALTERNATIVE_MARKET_LEAGUES)
    scope = _market_scope_signature(
        available_leagues,
        search_date,
        search_date,
    )
    scope.update(
        max_fixtures=market_tab.MAX_SCAN_FIXTURES,
        market_scope="Beste Märkte",
        market_kinds=None,
    )
    snapshot = {
        "version": market_tab.MARKET_SNAPSHOT_VERSION,
        "scanned_at": now.isoformat(),
        "scope": scope,
        "shortlist": [],
        "model_shortlist": forecasts,
        "reference_quotes": serialize_consensus_map(
            {extreme.candidate_id: _extreme_short_quote(extreme.candidate_id, now)}
        ),
        "price_checked_at": now.isoformat(),
        "price_checked_count": 1,
        "fixtures_found": 4,
        "fixtures_modeled": 4,
        "context_data_incomplete_fixtures": 0,
        "context_unchecked_fixtures": 0,
        "deferred_context_fixtures": 0,
        "context_scope_complete": True,
        "operational_error_count": 0,
    }
    recording_st = _RecordingStreamlit(
        {"market_bet_finder_snapshot": snapshot}
    )
    rendered = []

    monkeypatch.setattr(market_tab, "st", recording_st)
    monkeypatch.setattr(
        market_tab,
        "load_app_config",
        lambda _st: SimpleNamespace(api_football_key="api", weather_key=None),
    )
    monkeypatch.setattr(
        market_tab,
        "_segmented",
        lambda _label, options, _key, _default: options[0],
    )
    monkeypatch.setattr(market_tab.scan_jobs, "session_scope", lambda _state: "test")
    monkeypatch.setattr(market_tab.scan_jobs, "scoped_key", lambda *_args: "job")
    monkeypatch.setattr(
        market_tab.scan_jobs,
        "get_job",
        lambda _key: {"state": "idle"},
    )
    monkeypatch.setattr(
        market_tab,
        "render_price_decision",
        lambda candidate, **_kwargs: rendered.append(
            (recording_st.current_expander, candidate.event_key)
        ),
    )

    market_tab.create_alternative_markets_tab_extended(
        market_scope="Beste Märkte",
        search_date=search_date,
        search_end_date=search_date,
        embedded=True,
    )

    assert [key for _group, key in rendered] == [
        "primary-a",
        "primary-b",
        "primary-c",
        "sporting-alverca-away-under-1-5",
    ]
    short_group = next(
        (label, expanded)
        for label, expanded in recording_st.expanders
        if label.startswith("Sehr kurze Quoten")
    )
    assert short_group[1] is False
    assert rendered[-1][0] == short_group[0]
    assert len({key for _group, key in rendered}) == len(forecasts)


def test_manual_surface_promotes_useful_market_and_keeps_all_others(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    team_totals = []
    for index in range(1, 4):
        item = _manual_forecast(f"away-under-{index}", index)
        item.context["release_context_complete"] = False
        team_totals.append(item)
    osasuna = replace(
        _manual_forecast("osasuna-result-total", 4),
        home_team="Osasuna",
        away_team="Real Sociedad",
        market_key="RESULT_TOTAL_1X_UNDER_3_5",
        market="Resultat & Gesamttore 3,5",
        selection="1X und Unter 3,5",
    )
    osasuna.context["release_context_complete"] = True
    forecasts = [*team_totals, osasuna]
    search_date = now.date()
    available_leagues = list(ALTERNATIVE_MARKET_LEAGUES)
    scope = _market_scope_signature(available_leagues, search_date, search_date)
    scope.update(
        max_fixtures=market_tab.MAX_SCAN_FIXTURES,
        market_scope="Beste Märkte",
        market_kinds=None,
    )
    snapshot = {
        "version": market_tab.MARKET_SNAPSHOT_VERSION,
        "scanned_at": now.isoformat(),
        "scope": scope,
        "shortlist": [],
        "model_shortlist": forecasts,
        "reference_quotes": {},
        "price_checked_at": None,
        "price_checked_count": 0,
        "fixtures_found": 4,
        "fixtures_modeled": 4,
        "context_data_incomplete_fixtures": 3,
        "context_unchecked_fixtures": 0,
        "deferred_context_fixtures": 0,
        "context_scope_complete": True,
        "operational_error_count": 0,
    }
    recording_st = _RecordingStreamlit(
        {"market_bet_finder_snapshot": snapshot}
    )
    rendered = []

    monkeypatch.setattr(market_tab, "st", recording_st)
    monkeypatch.setattr(
        market_tab,
        "load_app_config",
        lambda _st: SimpleNamespace(api_football_key="api", weather_key=None),
    )
    monkeypatch.setattr(
        market_tab,
        "_segmented",
        lambda _label, options, _key, _default: options[0],
    )
    monkeypatch.setattr(market_tab.scan_jobs, "session_scope", lambda _state: "test")
    monkeypatch.setattr(market_tab.scan_jobs, "scoped_key", lambda *_args: "job")
    monkeypatch.setattr(
        market_tab.scan_jobs,
        "get_job",
        lambda _key: {"state": "idle"},
    )
    monkeypatch.setattr(
        market_tab,
        "render_price_decision",
        lambda candidate, **_kwargs: rendered.append(
            (recording_st.current_expander, candidate.event_key)
        ),
    )

    market_tab.create_alternative_markets_tab_extended(
        market_scope="Beste Märkte",
        search_date=search_date,
        search_end_date=search_date,
        embedded=True,
    )

    assert [key for _group, key in rendered] == [
        "osasuna-result-total",
        "away-under-1",
        "away-under-2",
        "away-under-3",
    ]
    primary_group = rendered[0][0]
    assert [group for group, _key in rendered[:2]] == [primary_group, primary_group]
    assert all(group != primary_group for group, _key in rendered[2:])
    assert all(
        str(group).startswith("Weitere Märkte zu ")
        for group, _key in rendered[2:]
    )
    assert len({key for _group, key in rendered}) == len(forecasts)


def test_automatic_signal_group_accepts_persisted_football_spelling():
    assert app._is_football_sport("Fussball") is True
    assert app._is_football_sport("Fußball") is True
    assert app._is_football_sport(" fussball ") is True
    assert app._is_football_sport("Tennis") is False


def test_zero_football_does_not_drop_other_automatic_sports():
    football, other = app._partition_automated_signals(
        [
            SimpleNamespace(sport="Tennis", key="tennis"),
            SimpleNamespace(sport="E-Sport", key="esports"),
        ]
    )

    assert football == []
    assert [signal.key for signal in other] == ["tennis", "esports"]


def test_automatic_candidate_from_partial_day_discloses_remaining_scope():
    status = SimpleNamespace(
        fixtures_found=21,
        fixtures_modeled=21,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=1,
        deferred_context_fixtures=0,
        context_accounting_available=True,
        context_scope_complete=False,
    )

    message = app._automatic_partial_scope_notice(status)

    assert message is not None
    assert "angezeigten Auswahlen wurden vollständig geprüft" in message
    assert "1 weiteres Spiel" not in message


def test_automatic_summary_proves_model_zero_before_quote_check():
    status = SimpleNamespace(
        football_status="completed",
        fixtures_found=40,
        fixtures_modeled=37,
        base_candidates=0,
        base_fixture_count=0,
        context_verified_fixtures=0,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_scope_complete=True,
        approved_candidates=0,
        price_checked_count=0,
        operational_error_count=0,
    )

    evidence, message, incomplete = app._automatic_consumer_summary(status)

    assert evidence == (
        "40 Spiele gefunden · 37 modelliert · 0 vollständig bestätigte Auswahlen"
    )
    assert "engere Auswahl" in message
    assert "Quote wurde deshalb noch nicht geprüft" in message
    assert "3 weitere gefundene Spiele konnten nicht modelliert werden" in message
    assert incomplete is True


def test_automatic_summary_never_turns_degraded_run_into_quality_rejection():
    status = SimpleNamespace(
        football_status="degraded",
        fixtures_found=7,
        fixtures_modeled=5,
        base_candidates=1,
        base_fixture_count=1,
        context_verified_fixtures=0,
        context_data_incomplete_fixtures=1,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_scope_complete=False,
        approved_candidates=0,
        price_checked_count=0,
        operational_error_count=1,
    )

    _, message, incomplete = app._automatic_consumer_summary(status)

    assert "nicht vollständig abgeschlossen" in message
    assert "kein Qualitätsurteil" in message
    assert incomplete is True


def test_degraded_summary_never_calls_stale_candidate_fully_confirmed():
    status = SimpleNamespace(
        football_status="degraded",
        fixtures_found=7,
        fixtures_modeled=7,
        base_candidates=1,
        base_fixture_count=1,
        context_verified_fixtures=1,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_scope_complete=True,
        approved_candidates=1,
        price_checked_count=1,
        operational_error_count=1,
    )

    evidence, message, incomplete = app._automatic_consumer_summary(status)

    assert "1 vollständig bestätigte Auswahl" not in evidence
    assert "Ergebnis nicht vollständig belegt" in evidence
    assert "kein Qualitätsurteil" in message
    assert incomplete is True


def test_automatic_summary_keeps_confirmed_selection_when_other_game_is_pending():
    status = SimpleNamespace(
        football_status="completed",
        fixtures_found=3,
        fixtures_modeled=3,
        base_candidates=3,
        base_fixture_count=3,
        context_verified_fixtures=2,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=1,
        deferred_context_fixtures=0,
        context_scope_complete=False,
        context_accounting_available=True,
        operational_error_count=0,
        approved_candidates=1,
        price_checked_count=1,
    )

    evidence, message, incomplete = app._automatic_consumer_summary(status)

    assert "1 vollständig bestätigte Auswahl" in evidence
    assert "1 Preisprüfung" in evidence
    assert "keine Auswahl bestätigt" not in message
    assert "keine aktuelle Vergleichsquote spielbar" in message
    assert "1 weiteres Spiel" in message
    assert incomplete is True


def test_legacy_automatic_context_scope_is_unknown_without_zero_pending_claim():
    status = SimpleNamespace(
        football_status="completed",
        fixtures_found=10,
        fixtures_modeled=10,
        base_candidates=4,
        base_fixture_count=0,
        context_verified_fixtures=0,
        context_data_incomplete_fixtures=0,
        context_unchecked_fixtures=0,
        deferred_context_fixtures=0,
        context_scope_complete=False,
        context_accounting_available=False,
        operational_error_count=0,
        approved_candidates=0,
        price_checked_count=0,
    )

    _, message, incomplete = app._automatic_consumer_summary(status)

    assert "Umfang der vollständigen Kontextprüfung" in message
    assert "0 weitere Spiele" not in message
    assert incomplete is True


def test_all_sports_copy_says_each_tab_is_a_separate_search():
    source = inspect.getsource(app.render_wettfinder)
    assert "getrennte Sportbereiche" in source
    assert "Ergebnis gilt nur für diesen Sport" in source


def test_public_navigation_exposes_no_admin_settings_or_training_route():
    sidebar_source = inspect.getsource(app._render_sidebar)
    main_source = inspect.getsource(app.main)
    assert "Einstellungen" not in sidebar_source
    assert "toggle_settings" not in sidebar_source
    assert "render_settings" not in main_source
    assert "Modell neu trainieren" not in sidebar_source

    challenge_source = inspect.getsource(app._challenge_15k.render_challenge_15k)
    assert "Challenge-Konto einstellen" in challenge_source


def test_shadow_tennis_history_is_not_a_consumer_tips_area():
    import my_tips

    source = inspect.getsource(my_tips.render_my_tips)
    assert "Tennis" not in source
    assert "render_tennis_history" not in source


def test_consumer_multi_sport_and_live_views_hide_provider_diagnostics():
    multi_source = inspect.getsource(app.render_multi_sport)
    live_source = inspect.getsource(app._render_live_football)
    red_card_source = inspect.getsource(app._render_red_cards)

    assert "PandaScore-Key" not in multi_source
    assert "Providerfehler" not in multi_source
    assert 'snapshot["errors"].items()' not in multi_source
    assert "Live-Prüfdetails" not in live_source
    assert "st.json" not in live_source
    assert "Platzverweis-Prüfdetails" not in red_card_source


def test_shared_finder_offers_every_sport_a_fourteen_day_horizon():
    assert app.SEARCH_HORIZONS == {
        "Heute": 0,
        "3 Tage voraus": 3,
        "7 Tage voraus": 7,
        "14 Tage voraus": 14,
    }
    assert app.FOOTBALL_SEARCH_HORIZONS is app.SEARCH_HORIZONS
    assert set(app.FINDER_SPORT_OPTIONS) == {
        "Alle",
        "Fußball",
        "Tennis",
        "Basketball",
        "Eishockey",
        "Cricket",
        "E-Sport",
    }


def test_all_finder_selection_expands_to_every_sport_once():
    assert app._finder_sports_for_selection("Alle") == app.FINDER_SINGLE_SPORT_OPTIONS
    assert app._finder_sports_for_selection("Tennis") == ("Tennis",)
    assert len(set(app._finder_sports_for_selection("Alle"))) == 6

    with pytest.raises(ValueError, match="Unbekannte Sportart"):
        app._finder_sports_for_selection("Curling")


def test_multi_sport_jobs_are_isolated_per_sport():
    names = {app._multi_sport_job_name(sport) for sport in app.MULTI_SPORT_OPTIONS}

    assert len(names) == len(app.MULTI_SPORT_OPTIONS)
    assert "multi_sport_basketball" in names
    assert "multi_sport_esport" in names


def test_all_sports_ui_keeps_multi_sport_widget_keys_isolated():
    source = Path(app.__file__).read_text(encoding="utf-8")

    assert 'key=f"run_multi_sport_{sport_key}"' in source
    assert 'bankroll_key=f"multi_sport_bankroll_{sport_key}"' in source


def test_multi_sport_window_rejects_reverse_and_overlong_ranges():
    start = date(2030, 1, 1)

    with pytest.raises(ValueError, match="höchstens 14 Tage"):
        app._validate_multi_sport_window(start, start + timedelta(days=15))
    with pytest.raises(ValueError, match="höchstens 14 Tage"):
        app._validate_multi_sport_window(start, start - timedelta(days=1))


def test_full_league_scans_have_no_confirmation_or_provider_warning():
    root = Path(__file__).resolve().parents[1]
    challenge_source = (root / "challenge_15k.py").read_text(encoding="utf-8")
    app_source = (root / "app.py").read_text(encoding="utf-8")

    assert "challenge_confirm_full_league_scan" not in challenge_source
    assert "full_scan_confirmed" not in challenge_source
    assert "Provider-Aufrufe" not in challenge_source
    assert "Provider-Aufrufe" not in app_source
    assert "NOCH KEINE WETTFREIGABE" not in challenge_source
    assert "Mathematische Vorfilterung" not in challenge_source
    assert "Provider- oder Coverage-Meldungen" not in challenge_source


def test_red_card_monitor_uses_the_full_canonical_league_scope():
    assert len(RED_CARD_MONITORED_LEAGUE_IDS) == 51
    assert set(RED_CARD_MONITORED_LEAGUE_IDS) == set(ALTERNATIVE_MARKET_LEAGUES)


def test_app_formats_new_league_codes_from_existing_catalog_symbols():
    assert app._league_label_for_code("NOR1") == "Norway: Eliteserien"
    assert app._league_label_for_code("unknown") == "UNKNOWN"


def test_market_worker_forwards_detailed_progress(monkeypatch):
    updates = []
    provider = object()
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
        search_end_date=None,
        allow_above_challenge_probability=False,
        progress_cb=None,
    ):
        assert received_provider is provider
        assert league_ids == [78, 39]
        assert max_fixtures == 1200
        assert search_end_date == search_date + timedelta(days=7)
        assert allow_above_challenge_probability is True
        progress_cb(0.25, "Liga 1/2")
        progress_cb(1.0, "Fertig")
        return {"search_date": search_date.isoformat()}

    monkeypatch.setattr(market_tab, "scan_daily_challenge", fake_scan)
    search_date = datetime.now().date()
    result = market_tab._run_market_scan_worker(
        "api-key",
        None,
        [78, 39],
        search_date,
        search_date + timedelta(days=7),
        1200,
        {"league_ids": [39, 78]},
        progress_cb=lambda fraction, text: updates.append((fraction, text)),
    )

    assert updates == [
        (0.225, "Liga 1/2"),
        (0.9, "Fertig"),
        (0.92, "Marktquoten der Modellkandidaten werden verglichen"),
        (1.0, "Tipps und Marktpreise sind bereit"),
    ]
    assert result["scope"] == {"league_ids": [39, 78]}


def test_multi_sport_worker_reports_real_phases(monkeypatch):
    start_date = date(2030, 1, 1)
    end_date = start_date + timedelta(days=7)
    monkeypatch.setattr(
        app,
        "_fetch_multi_sport_snapshot",
        lambda _sport, _detail, _start, _end: {"items": [{}, {}]},
    )
    updates = []

    result = app._run_multi_sport_worker(
        "Basketball",
        "NBA",
        start_date,
        end_date,
        progress_cb=lambda fraction, text: updates.append((fraction, text)),
    )

    assert [fraction for fraction, _text in updates] == [
        0.05,
        0.25,
        0.90,
        1.0,
    ]
    assert result["snapshot"]["items"] == [{}, {}]
    assert result["scope_key"].endswith("2030-01-01:2030-01-08")


def test_live_recommendation_snapshot_age_requires_timezone_and_freshness():
    now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)

    assert app._snapshot_age_seconds(now.isoformat(), now=now) == 0
    assert app._snapshot_age_seconds(
        (now - timedelta(seconds=181)).isoformat(),
        now=now,
    ) == 181
    assert app._snapshot_age_seconds("2026-07-20T10:00:00", now=now) is None


def test_persisted_football_signal_keeps_point_probability_and_haircut_separate(
    monkeypatch,
):
    monkeypatch.setattr(
        app,
        "prematch_btts_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(
            model_ready=True,
            model_probability=64.0,
            probability_haircut=12.0,
            evidence_stage="SHADOW",
            selection="Ja",
        ),
    )
    frame = pd.DataFrame(
        [
            {
                "Home": "A",
                "Away": "B",
                "League": "BL1",
                "Date": "2026-08-03",
                "_analysis": {"details": {"ml_active": True}},
            }
        ]
    )

    signal = app._persist_prematch(frame)["signals"][0]

    assert signal["p"] == pytest.approx(0.64)
    assert signal["haircut"] == pytest.approx(0.12)
    assert signal["evidence_stage"] == "SHADOW"
    assert signal["policy_version"] == BETTING_POLICY_VERSION


def test_multi_sport_fetches_only_the_selected_basketball_scope(monkeypatch):
    from scanners import basketball_scanner

    calls = []

    class FakeBasketballScanner:
        def __init__(self):
            self.errors = {}

        def get_upcoming_games(self, league, start_date, end_date):
            calls.append(("basketball", league, start_date, end_date))
            return [
                {
                    "home_team": "Home",
                    "away_team": "Away",
                    "league": league,
                    "status": "upcoming",
                    "start_time": "2030-01-02T19:00:00+01:00",
                }
            ]

        def calculate_scoring_projection(self, _game):
            raise AssertionError("Legacy projection must not run")

        def get_upcoming_nhl_games(self, _start_date, _end_date):
            raise AssertionError("NHL must not be fetched for Basketball")

    monkeypatch.setattr(
        basketball_scanner,
        "BasketballScanner",
        FakeBasketballScanner,
    )

    start_date = date(2030, 1, 1)
    end_date = start_date + timedelta(days=7)
    snapshot = app._fetch_multi_sport_snapshot(
        "Basketball",
        "NBA",
        start_date,
        end_date,
    )

    assert calls == [("basketball", "NBA", start_date, end_date)]
    assert snapshot["sport"] == "Basketball"
    assert snapshot["detail_filter"] == "NBA"
    assert len(snapshot["items"]) == 1
    assert "nhl" not in snapshot
    assert "Home vs Away" in app._multi_sport_event_label(
        "Basketball", snapshot["items"][0]
    )


def test_multi_sport_eishockey_does_not_run_basketball_scan(monkeypatch):
    from scanners import basketball_scanner

    calls = []

    class FakeBasketballScanner:
        def __init__(self):
            self.errors = {}

        def get_upcoming_games(self, _league, _start_date, _end_date):
            raise AssertionError("Basketball must not be fetched for Eishockey")

        def get_upcoming_nhl_games(self, start_date, end_date):
            calls.append("nhl")
            return [
                {
                    "home_team": "ZSC",
                    "away_team": "SCB",
                    "status": "upcoming",
                    "start_time": "2030-01-03T18:00:00+01:00",
                }
            ]

    monkeypatch.setattr(
        basketball_scanner,
        "BasketballScanner",
        FakeBasketballScanner,
    )

    snapshot = app._fetch_multi_sport_snapshot(
        "Eishockey",
        None,
        date(2030, 1, 1),
        date(2030, 1, 8),
    )

    assert calls == ["nhl"]
    assert snapshot["sport"] == "Eishockey"
    assert "SCB @ ZSC" in app._multi_sport_event_label(
        "Eishockey", snapshot["items"][0]
    )


def test_multi_sport_esports_filter_is_scoped_to_pandascore(monkeypatch):
    from scanners import esports_scanner

    calls = []

    class FakeEsportsScanner:
        def __init__(self):
            self.api_key = "configured"
            self.errors = {}

        def get_upcoming_matches(self, game, start_date, end_date):
            calls.append((game, start_date, end_date))
            return [
                {
                    "team1": "Alpha",
                    "team2": "Beta",
                    "game": "VALORANT",
                    "status": "upcoming",
                    "begin_at": "2030-01-04T12:00:00Z",
                }
            ]

        def analyze_match(self, _match):
            raise AssertionError("Legacy exploratory estimate must not run")

    monkeypatch.setattr(esports_scanner, "EsportsScanner", FakeEsportsScanner)

    start_date = date(2030, 1, 1)
    end_date = date(2030, 1, 8)
    snapshot = app._fetch_multi_sport_snapshot(
        "E-Sport",
        "Valorant",
        start_date,
        end_date,
    )

    assert calls == [("valorant", start_date, end_date)]
    assert snapshot["sport"] == "E-Sport"
    assert snapshot["credentials_available"] is True
    assert "Alpha vs Beta" in app._multi_sport_event_label(
        "E-Sport", snapshot["items"][0]
    )


def test_multi_sport_rejects_filters_from_another_sport():
    with pytest.raises(ValueError):
        app._fetch_multi_sport_snapshot("Tennis", "CS2")
    with pytest.raises(ValueError):
        app._fetch_multi_sport_snapshot("E-Sport", "NBA")


def test_multi_sport_release_is_fail_closed_during_shadow_ramp_up():
    blocker = app._multi_sport_release_blockers(
        "E-Sport",
        {"status": "upcoming"},
        esports_release={"ready": False, "settled": 5, "required": 300},
    )
    assert blocker
    assert "5/300" in blocker[0]


def test_esport_calibration_alone_never_unlocks_real_money():
    blocker = app._multi_sport_release_blockers(
        "E-Sport",
        {"status": "upcoming"},
        esports_release={
            "ready": False,
            "calibration_ready": True,
            "price_evidence_ready": False,
            "settled": 300,
            "required": 300,
        },
    )

    assert blocker
    assert "CLV" in blocker[0]


def test_multi_sport_live_esport_is_separate_from_prematch_release():
    blocker = app._multi_sport_release_blockers(
        "E-Sport",
        {"status": "live"},
        esports_release={"ready": True, "settled": 100, "required": 100},
    )
    assert blocker
    assert "Live-Wetten" in blocker[0]


def test_basketball_and_nhl_require_independent_release_evidence():
    assert app._multi_sport_release_blockers("Basketball", {})
    assert app._multi_sport_release_blockers("Eishockey", {})


def test_multi_sport_tennis_event_label_uses_verified_set_score():
    label = app._multi_sport_event_label("Tennis", {
        "player1": "Player A",
        "player2": "Player B",
        "player1_score": 1,
        "player2_score": 0,
    })

    assert label == "Player A vs Player B | 1:0"


def test_multi_sport_cricket_event_label_uses_current_innings_fields():
    label = app._multi_sport_event_label("Cricket", {
        "team1": "Alpha",
        "team2": "Beta",
        "current_runs": 191,
        "current_wickets": 4,
        "current_over": 40.2,
    })

    assert label == "Alpha vs Beta | 191/4 nach 40.2 Over"


def test_football_data_org_key_is_never_used_as_api_football_key(monkeypatch):
    monkeypatch.setattr(
        app,
        "load_app_config",
        lambda _st: AppConfig(api_key="football-data-only"),
    )
    app.get_analyzer.clear()
    try:
        assert app.get_analyzer() is None
    finally:
        app.get_analyzer.clear()


def test_evidence_score_full_coverage_and_agreement_is_100():
    result = calculate_evidence_score(12, 12, 5, 5, [64.0, 64.0, 64.0])

    assert result["score"] == pytest.approx(100.0)
    assert result["agreement_score"] == pytest.approx(100.0)
    assert sum(result["contributions"].values()) == pytest.approx(100.0)


def test_evidence_score_without_form_is_capped_at_80():
    result = calculate_evidence_score(12, 12, 0, 0, [60.0, 60.0, 60.0])

    assert result["score"] == pytest.approx(80.0)
    assert result["contributions"]["home_form"] == 0.0
    assert result["contributions"]["away_form"] == 0.0


def test_evidence_score_penalizes_active_model_disagreement():
    aligned = calculate_evidence_score(12, 12, 5, 5, [60.0, 60.0, 60.0])
    divergent = calculate_evidence_score(12, 12, 5, 5, [60.0, 60.0, 60.0, 100.0])

    assert divergent["score"] < aligned["score"]
    assert divergent["agreement_score"] < aligned["agreement_score"]


def test_evidence_score_rejects_ambiguous_inputs():
    with pytest.raises(ValueError):
        calculate_evidence_score(True, 12, 5, 5, [60.0, 60.0])
    with pytest.raises(ValueError):
        calculate_evidence_score(12, 12, 5, 5, [60.0])
    with pytest.raises(ValueError):
        calculate_evidence_score(12, 12, 5, 5, [60.0, 101.0])
    with pytest.raises(ValueError):
        calculate_evidence_score(12.5, 12, 5, 5, [60.0, 61.0])


def test_live_quality_filter_has_two_distinct_levels():
    analyses = [
        {"id": "low", "btts_prob": 65.0, "btts_confidence": "LOW"},
        {"id": "medium", "btts_prob": 70.0, "btts_confidence": "MEDIUM"},
        {"id": "insufficient", "btts_prob": None, "btts_confidence": "INSUFFICIENT"},
        {"id": "complete", "btts_prob": 100.0, "btts_confidence": "COMPLETE"},
    ]

    calculable = app._filter_live_opportunities(analyses, 60, "Berechenbar")
    complete_basis = app._filter_live_opportunities(
        analyses, 60, "Live-xG + Prematch"
    )

    assert [item["id"] for item in calculable] == ["medium", "low"]
    assert [item["id"] for item in complete_basis] == ["medium"]


def test_live_market_filter_uses_selected_remaining_goal_probability():
    analyses = [
        {
            "id": "high-btts",
            "home_team": "A",
            "away_team": "B",
            "btts_prob": 90.0,
            "btts_confidence": "MEDIUM",
            "live_data_quality": "MEDIUM",
            "remaining_goals": {
                "over_0_5_probability": 40.0,
                "home_scores_probability": 35.0,
                "away_scores_probability": 20.0,
            },
        },
        {
            "id": "high-rest",
            "home_team": "C",
            "away_team": "D",
            "btts_prob": 45.0,
            "btts_confidence": "MEDIUM",
            "live_data_quality": "MEDIUM",
            "remaining_goals": {
                "over_0_5_probability": 75.0,
                "home_scores_probability": 30.0,
                "away_scores_probability": 65.0,
            },
        },
    ]

    another_goal = app._filter_live_opportunities(
        analyses,
        60,
        "Streng: Live-xG + Prematch (empfohlen)",
        "Noch ein Tor",
    )
    team_goal = app._filter_live_opportunities(
        analyses,
        60,
        "Streng: Live-xG + Prematch (empfohlen)",
        "Team trifft noch",
    )

    assert [item["id"] for item in another_goal] == ["high-rest"]
    assert [item["id"] for item in team_goal] == ["high-rest"]
    probability, selection = app._live_market_signal(analyses[1], "Team trifft noch")
    assert probability == pytest.approx(65.0)
    assert selection == "D trifft noch"


def test_strict_live_data_basis_is_the_ui_default():
    assert app.LIVE_DATA_BASIS_OPTIONS[0] == "Streng: Live-xG + Prematch (empfohlen)"


def test_equal_team_goal_probabilities_do_not_create_a_team_selection():
    probability, selection = app._live_market_signal(
        {
            "home_team": "A",
            "away_team": "B",
            "remaining_goals": {
                "home_scores_probability": 45.0,
                "away_scores_probability": 45.0,
            },
        },
        "Team trifft noch",
    )

    assert probability is None
    assert selection == "Kein klarer Teamvorteil"


def test_prematch_scan_collects_before_probability_filter(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "BTTS %": "42.0%",
                "Data Quality": "70.0%",
                "Home": "A",
                "Away": "B",
            }
        ]
    )
    analyzer = Mock()
    analyzer.analyze_upcoming_matches.return_value = frame
    monkeypatch.setattr(app.st, "progress", lambda _value: _ProgressStub())
    monkeypatch.setattr(app.st, "empty", _ProgressStub)

    search_date = date(2030, 1, 2)
    result = app._scan_prematch(
        analyzer,
        ["BL1"],
        7,
        search_date,
    )

    analyzer.analyze_upcoming_matches.assert_called_once_with(
        "BL1",
        days_ahead=7,
        min_probability=0,
        start_date=search_date,
    )
    assert result.iloc[0]["BTTS_num"] == pytest.approx(42.0)

    updates = []
    app._scan_prematch(
        analyzer,
        ["BL1"],
        7,
        search_date,
        progress_cb=lambda fraction, text: updates.append((fraction, text)),
    )
    fractions = [fraction for fraction, _text in updates]
    assert fractions == sorted(fractions)
    assert fractions[0] == 0.01
    assert fractions[-1] == 1.0
    assert any("Liga 1/1" in text for _fraction, text in updates)


def test_scope_signatures_are_order_independent():
    search_date = date(2030, 1, 2)
    assert app._scope_signature(
        ["PL", "BL1"],
        7,
        search_date,
    ) == app._scope_signature(
        ["BL1", "PL"],
        7,
        search_date,
    )
    assert app._scope_signature(["PL"], 7, search_date) == {
        "leagues": ["PL"],
        "days_ahead": 7,
        "start_date": "2030-01-02",
    }
    assert app._scope_signature(
        ["PL"],
        7,
        search_date,
    ) != app._scope_signature(
        ["PL"],
        7,
        date(2030, 1, 3),
    )
    assert (
        app._prematch_window_label(
            app._scope_signature(["PL"], 7, search_date),
            today=search_date,
        )
        == "Heute (02.01.2030) bis 09.01.2030"
    )
    assert _market_scope_signature([78, 39], pd.Timestamp("2026-07-11").date()) == {
        "league_ids": [39, 78],
        "date": "2026-07-11",
        "end_date": "2026-07-11",
    }
    assert _market_scope_signature(
        [78, 39],
        date(2026, 7, 11),
        date(2026, 7, 25),
    ) == {
        "league_ids": [39, 78],
        "date": "2026-07-11",
        "end_date": "2026-07-25",
    }
    assert (
        _market_result_day_label(
            {"scope": {"date": "2030-01-03"}},
            today=search_date,
        )
        == "Morgen"
    )
    assert (
        _market_result_day_label(
            {
                "scope": {
                    "date": "2030-01-02",
                    "end_date": "2030-01-09",
                }
            },
            today=search_date,
        )
        == "02.01.2030 bis 09.01.2030"
    )


def test_api_football_uses_explicit_scan_window():
    api = APIFootball("test-key")
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"errors": [], "response": []}
    api._get = Mock(return_value=response)

    result = api.get_upcoming_fixtures(
        "PL",
        7,
        start_date=date(2030, 1, 2),
    )

    assert result == []
    params = api._get.call_args.kwargs["params"]
    assert params["from"] == "2030-01-02"
    assert params["to"] == "2030-01-09"
    assert params["season"] == 2029


def test_api_football_http_200_provider_error_is_not_treated_as_empty_success():
    response = Mock(
        status_code=200,
        json=Mock(return_value={"errors": {"access": "account suspended"}, "response": []}),
    )
    response.raise_for_status = Mock()

    with pytest.raises(ValueError, match="account suspended"):
        _api_football_items(response, "fixtures")


def test_alternative_market_provider_records_http_200_account_error():
    analyzer = PreMatchAlternativeAnalyzer("api")
    response = Mock(
        status_code=200,
        json=Mock(return_value={"errors": {"access": "account suspended"}, "response": []}),
    )

    assert analyzer._response_data(response, "team stats", list) is None
    assert "suspended" in analyzer.errors["team stats"]


def test_red_card_bot_respects_explicit_credentials_outside_streamlit():
    bot = RedCardBotEnhanced(
        api_key="explicit-api",
        telegram_token="explicit-token",
        telegram_chat_id="explicit-chat",
        streamlit_mode=False,
    )

    assert bot.api_key == "explicit-api"
    assert bot.telegram_token == "explicit-token"
    assert bot.telegram_chat_id == "explicit-chat"


def test_telegram_reuses_preloaded_live_stats(monkeypatch):
    bot = RedCardBotEnhanced(
        api_key="api",
        telegram_token="token",
        telegram_chat_id="chat",
        streamlit_mode=False,
    )
    bot.get_live_stats = Mock()
    prediction = object()
    bot.predictor = Mock()
    bot.predictor.predict.return_value = prediction
    bot.predictor.format_prediction.return_value = "model output"
    response = Mock(status_code=200)
    monkeypatch.setattr("red_card_bot.requests.post", Mock(return_value=response))
    card = {
        "player": "Player",
        "team": "Home",
        "team_id": 1,
        "minute": 55,
        "match": {
            "fixture": {"id": 10, "status": {"elapsed": 70}},
            "teams": {
                "home": {"id": 1, "name": "Home"},
                "away": {"id": 2, "name": "Away"},
            },
            "goals": {"home": 1, "away": 0},
            "league": {"name": "League", "country": "Country"},
        },
    }

    sent = bot.send_telegram_alert_with_stats(
        card,
        live_stats=None,
        fetch_live_stats=False,
    )

    assert sent is True
    bot.get_live_stats.assert_not_called()
    assert bot.predictor.predict.call_args.kwargs["live_stats"] is None
    assert bot.predictor.predict.call_args.kwargs["minute"] == 70
    assert bot.predictor.format_prediction.call_args.kwargs["red_card_minute"] == 55


def test_red_card_app_prediction_uses_current_snapshot_minute():
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    bot.get_live_stats = Mock(return_value={"xg_home": 0.9, "xg_away": 0.4})
    card = {
        "player": "Player",
        "team": "Home",
        "team_id": 1,
        "minute": 55,
        "match": {
            "fixture": {"id": 10, "status": {"elapsed": 70}},
            "teams": {
                "home": {"id": 1, "name": "Home"},
                "away": {"id": 2, "name": "Away"},
            },
            "goals": {"home": 1, "away": 0},
            "league": {"name": "League", "country": "Country"},
        },
    }

    entry = app._red_card_entry(bot, card)

    assert entry["prediction_minute"] == 70
    assert entry["prediction"]["minute"] == 70
    assert entry["card"]["minute"] == 55


def test_red_card_provider_records_http_errors(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    monkeypatch.setattr(
        "red_card_bot.requests.get",
        Mock(return_value=Mock(status_code=503)),
    )

    assert bot.get_live_matches() == []
    assert bot.errors == [{"operation": "live_matches", "message": "HTTP 503"}]


def test_red_card_provider_records_http_200_account_errors(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    response = Mock(
        status_code=200,
        json=Mock(return_value={"errors": {"access": "account suspended"}, "response": []}),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))

    assert bot.get_live_stats(1, 10, 20) is None
    assert bot.errors == [{
        "operation": "live_stats",
        "message": "{'access': 'account suspended'}",
    }]


def test_red_card_empty_league_scope_does_not_expand_to_worldwide(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    response = Mock(
        status_code=200,
        json=Mock(
            return_value={
                "response": [
                    {"league": {"id": 78}, "fixture": {"id": 1}},
                ]
            }
        ),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))

    assert bot.get_live_matches([]) == []


def test_red_card_event_rejects_boolean_extra_time(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    match = {
        "fixture": {"id": 1, "status": {"elapsed": 50}},
        "league": {"id": 39},
        "teams": {"home": {"id": 10}, "away": {"id": 20}},
        "goals": {"home": 1, "away": 0},
    }
    response = Mock(
        status_code=200,
        json=Mock(return_value={
            "response": [{
                "type": "Card",
                "detail": "Red Card",
                "player": {"id": 7, "name": "Player"},
                "team": {"id": 10, "name": "Home"},
                "time": {"elapsed": 50, "extra": False},
            }],
        }),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))

    assert bot.check_match_for_red_cards(match) == []


def test_red_card_finder_can_recheck_a_seen_live_event(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    match = {
        "fixture": {"id": 1, "status": {"elapsed": 50}},
        "league": {"id": 39},
        "teams": {"home": {"id": 10}, "away": {"id": 20}},
        "goals": {"home": 1, "away": 0},
    }
    response = Mock(
        status_code=200,
        json=Mock(return_value={
            "response": [{
                "type": "Card",
                "detail": "Red Card",
                "player": {"id": 7, "name": "Player"},
                "team": {"id": 10, "name": "Home"},
                "time": {"elapsed": 50, "extra": 0},
            }],
        }),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))
    bot.alerted_cards = {"1_10_7_50_0": 1.0}

    assert bot.check_match_for_red_cards(match) == []
    assert len(bot.check_match_for_red_cards(match, include_seen=True)) == 1


def test_h2h_provider_rejects_wrong_fixture_membership(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    response = Mock(
        status_code=200,
        json=Mock(return_value={
            "response": [{
                "teams": {"home": {"id": 10}, "away": {"id": 30}},
                "goals": {"home": 1, "away": 1},
            }],
        }),
    )
    monkeypatch.setattr("api_football.requests.get", Mock(return_value=response))

    assert client.get_h2h(10, 20) == []
    assert client.last_error == "head-to-head: invalid fixture data"


def test_live_provider_exposes_http_failure(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    monkeypatch.setattr(
        "api_football.requests.get",
        Mock(return_value=Mock(status_code=429)),
    )

    assert client.get_live_matches() == []
    assert client.last_error == "live fixtures: HTTP 429"


def test_live_provider_exposes_http_200_account_error(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    monkeypatch.setattr(
        "api_football.requests.get",
        Mock(
            return_value=Mock(
                status_code=200,
                json=Mock(
                    return_value={
                        "errors": {"access": "Your account is suspended"},
                        "response": [],
                    }
                ),
            )
        ),
    )

    assert client.get_live_matches() == []
    assert "suspended" in client.last_error
