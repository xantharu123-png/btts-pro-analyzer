"""Responsive BetBoy analysis workspace."""

import importlib
from functools import wraps
import math
import sqlite3
import threading
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from typing import Optional
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

import league_catalog as _league_catalog
from account_identity import ensure_account_scope
from api_budget import APIBudgetPriority, api_football_get


_REQUIRED_LEAGUE_CATALOG_VERSION = 2
if getattr(_league_catalog, "CATALOG_VERSION", 0) < _REQUIRED_LEAGUE_CATALOG_VERSION:
    _league_catalog = importlib.reload(_league_catalog)

import advanced_analyzer as _advanced_analyzer
import alternative_markets_tab_extended as _alternative_markets
import challenge_15k as _challenge_15k
import football_recommendations as _football_recommendations
import scan_jobs

_REQUIRED_ANALYZER_MODULE_VERSION = 3
if getattr(_advanced_analyzer, "ANALYZER_MODULE_VERSION", 0) < _REQUIRED_ANALYZER_MODULE_VERSION:
    _advanced_analyzer = importlib.reload(_advanced_analyzer)

_REQUIRED_CHALLENGE_WORKSPACE_VERSION = 9
if getattr(_challenge_15k, "CHALLENGE_WORKSPACE_VERSION", 0) < _REQUIRED_CHALLENGE_WORKSPACE_VERSION:
    _challenge_15k = importlib.reload(_challenge_15k)

_REQUIRED_MARKET_WORKFLOW_VERSION = 10
if getattr(_alternative_markets, "MARKET_WORKFLOW_VERSION", 0) < _REQUIRED_MARKET_WORKFLOW_VERSION:
    _alternative_markets = importlib.reload(_alternative_markets)

_REQUIRED_FOOTBALL_RECOMMENDATIONS_VERSION = 3
if (
    getattr(_football_recommendations, "FOOTBALL_RECOMMENDATIONS_VERSION", 0)
    < _REQUIRED_FOOTBALL_RECOMMENDATIONS_VERSION
):
    _football_recommendations = importlib.reload(_football_recommendations)

AdvancedBTTSAnalyzer = _advanced_analyzer.AdvancedBTTSAnalyzer
ML_FEATURE_NAMES = _advanced_analyzer.ML_FEATURE_NAMES
ML_MODEL_PATH = _advanced_analyzer.ML_MODEL_PATH
create_alternative_markets_tab_extended = (
    _alternative_markets.create_alternative_markets_tab_extended
)
render_challenge_15k = _challenge_15k.render_challenge_15k
live_football_candidate = _football_recommendations.live_football_candidate
prematch_btts_candidate = _football_recommendations.prematch_btts_candidate
red_card_candidate = _football_recommendations.red_card_candidate

from bet_finder_ui import render_price_decision
from betting_math import BETTING_POLICY_VERSION
from ev_signal_sources import (
    AutomatedWettfinderStatus,
    ModelSignal,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
    automated_wettfinder_status,
)
from ui_components import plain_german, scan_progress_fragment
from config_loader import load_app_config
from date_context import german_date_window, zurich_today
from league_catalog import ALTERNATIVE_MARKET_LEAGUES, ANALYZER_LEAGUE_IDS
from multi_sport_recommendations import (
    EVIDENCE_RELEASED,
    RecommendationCandidate,
    build_candidate,
)


PAGE_INFO = {
    "Wettfinder": (
        "Wettfinder",
        "Berechnete Auswahlen nach Qualitätsprüfung; Marktpreis und Mindestquote werden getrennt bewertet.",
    ),
    "Live": (
        "Live Wettfinder",
        "Aktuelle Spieldaten werden in konkrete Live-Auswahlen und klare Mindestquoten übersetzt.",
    ),
    "15K": (
        "15K Challenge",
        "Bis zu drei streng geprüfte Spiele für das nächste Challenge-Ticket.",
    ),
    "Meine Tipps": (
        "Meine Tipps",
        "Gemerkte Tipps, 15K-Tickets und der transparente Ergebnisverlauf an einem Ort.",
    ),
}

MAIN_PAGES = ("Wettfinder", "Live", "15K", "Meine Tipps")
LEGACY_PAGE_ALIASES = {
    "Spiele": "Wettfinder",
    "Märkte": "Wettfinder",
    "Wett-Check": "Wettfinder",
    "Multi-Sport": "Wettfinder",
    "Tennis": "Wettfinder",
    "15K Challenge": "15K",
}

# Seiten mit Hintergrund-Scans: Läuft einer dieser Jobs, dreht in der
# Sidebar neben dem Seitennamen ein Rädchen (CSS, siehe _scan_spinner_css).
PAGE_SCAN_JOBS = {
    "Wettfinder": (
        "prematch",
        "markets",
        "tennis",
        "multi_sport",
        "multi_sport_basketball",
        "multi_sport_eishockey",
        "multi_sport_tennis",
        "multi_sport_cricket",
        "multi_sport_esport",
    ),
    "Live": ("live", "red_cards"),
    "15K": ("challenge_15k",),
    "Meine Tipps": (),
}

PREMATCH_SNAPSHOT_VERSION = 4
LIVE_SNAPSHOT_VERSION = 4
RED_CARD_SNAPSHOT_VERSION = 3
DEFAULT_PREMATCH_LEAGUES = ("BL1", "PL", "PD")
LIVE_QUALITY_LABELS = {
    "LOW": "Basis: teilweise Daten",
    "MEDIUM": "Streng: Live-xG + Prematch",
}
LIVE_DATA_BASIS_OPTIONS = (
    "Streng: Live-xG + Prematch (empfohlen)",
    "Basis: teilweise Daten",
)
LIVE_MARKET_OPTIONS = ("BTTS", "Noch ein Tor", "Team trifft noch")
MULTI_SPORT_OPTIONS = (
    "Basketball",
    "Eishockey",
    "Tennis",
    "Cricket",
    "E-Sport",
)
FINDER_SINGLE_SPORT_OPTIONS = (
    "Fußball",
    "Tennis",
    "Basketball",
    "Eishockey",
    "Cricket",
    "E-Sport",
)
FINDER_SPORT_OPTIONS = ("Alle", *FINDER_SINGLE_SPORT_OPTIONS)
SEARCH_HORIZONS = {
    "Heute": 0,
    "3 Tage voraus": 3,
    "7 Tage voraus": 7,
    "14 Tage voraus": 14,
}
# Backward-compatible name for callers/tests from the football-only rollout.
FOOTBALL_SEARCH_HORIZONS = SEARCH_HORIZONS
MULTI_SPORT_FILTER_OPTIONS = {
    "Basketball": ("Alle Ligen", "NBA", "EuroLeague"),
    "E-Sport": ("Alle Spiele", "CS2", "LoL", "Dota2", "Valorant"),
}


def _league_label_for_code(league_code: str) -> str:
    """Format a league code using catalog symbols present before this release."""
    code = str(league_code).upper()
    league_id = ANALYZER_LEAGUE_IDS.get(code)
    return ALTERNATIVE_MARKET_LEAGUES.get(league_id, code)


def _get_supabase_url() -> Optional[str]:
    """Return the configured PostgreSQL URL when available."""
    return load_app_config(st).supabase_db_url


def _freemode_enabled() -> bool:
    """Research display flag; recommendation vetoes always remain active."""
    try:
        return bool(load_app_config(st).freemode)
    except Exception:
        return False


def _session_scope_id() -> str:
    return scan_jobs.session_scope(st.session_state)


def _job_key(name: str) -> str:
    return scan_jobs.scoped_key(name, _session_scope_id())


def _finder_sports_for_selection(sport: str) -> tuple[str, ...]:
    if sport == "Alle":
        return FINDER_SINGLE_SPORT_OPTIONS
    if sport not in FINDER_SINGLE_SPORT_OPTIONS:
        raise ValueError(f"Unbekannte Sportart: {sport}")
    return (sport,)


def _multi_sport_job_name(sport: str) -> str:
    key_parts = {
        "Basketball": "basketball",
        "Eishockey": "eishockey",
        "Tennis": "tennis",
        "Cricket": "cricket",
        "E-Sport": "esport",
    }
    try:
        return f"multi_sport_{key_parts[sport]}"
    except KeyError as exc:
        raise ValueError(f"Unbekannte Sportart: {sport}") from exc


_ANALYZER_LOCKS_GUARD = threading.Lock()
_ANALYZER_LOCKS: dict[int, threading.RLock] = {}


def _serialized_analyzer(position: int = 0):
    """Serialize mutable analyzer access while keeping unrelated jobs parallel."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            analyzer = (
                args[position]
                if len(args) > position
                else kwargs.get("analyzer")
            )
            if analyzer is None:
                return fn(*args, **kwargs)
            analyzer_id = id(analyzer)
            with _ANALYZER_LOCKS_GUARD:
                lock = _ANALYZER_LOCKS.setdefault(
                    analyzer_id,
                    threading.RLock(),
                )
            with lock:
                return fn(*args, **kwargs)

        return wrapped

    return decorate


def _get_db_connection(db_path: str = "betboy_data.db"):
    """Open the configured PostgreSQL database or the local SQLite fallback."""
    supabase_url = _get_supabase_url()
    if supabase_url:
        try:
            import psycopg2

            return psycopg2.connect(supabase_url)
        except ImportError:
            print("WARNING: psycopg2 is not installed")
        except Exception as exc:
            print(f"WARNING: PostgreSQL connection error: {exc}")
    from db_paths import LEGACY_DB_NAME, PRIMARY_DB_NAME, ensure_primary_db

    if db_path in (LEGACY_DB_NAME, PRIMARY_DB_NAME):
        db_path = ensure_primary_db()
    return sqlite3.connect(db_path)


def _format_optional(value, decimals: int = 1, suffix: str = "") -> str:
    """Format observed or model values without inventing a fallback."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "n/a"


def _numeric_or_zero(value) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _format_snapshot_time(value: Optional[str]) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def _snapshot_age_seconds(
    value: Optional[str],
    *,
    now: Optional[datetime] = None,
) -> Optional[float]:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if timestamp.tzinfo is None:
        return None
    reference = now or datetime.now().astimezone()
    if reference.tzinfo is None:
        return None
    return (reference.astimezone() - timestamp.astimezone()).total_seconds()


def _scope_signature(
    leagues: list[str],
    days_ahead: int,
    search_date: Optional[date] = None,
) -> dict:
    start_date = search_date or zurich_today()
    if isinstance(start_date, datetime) or not isinstance(start_date, date):
        raise ValueError("search_date must be a date")
    return {
        "leagues": sorted(str(league) for league in leagues),
        "days_ahead": int(days_ahead),
        "start_date": start_date.isoformat(),
    }


def _prematch_window_label(
    scope: object,
    *,
    today: Optional[date] = None,
) -> str:
    if not isinstance(scope, dict):
        return "unbekannt"
    return german_date_window(
        scope.get("start_date"),
        scope.get("days_ahead"),
        today=today or zurich_today(),
    )


def _percent_series(series: pd.Series) -> pd.Series:
    """Normalize percentages that arrive as strings or zero-to-one values."""
    cleaned = series.astype(str).str.rstrip("%").str.strip()
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return numeric.map(lambda value: value * 100 if pd.notna(value) and abs(value) <= 1 else value)


def _segmented(label: str, options: list[str], key: str, default: str) -> str:
    """Use a segmented control with a radio fallback for older Streamlit builds."""
    if hasattr(st, "segmented_control"):
        value = st.segmented_control(
            label,
            options,
            default=default,
            key=key,
            selection_mode="single",
        )
        return value or default
    return st.radio(label, options, index=options.index(default), horizontal=True, key=key)


def _apply_app_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bb-ink: #202428;
            --bb-muted: #66707a;
            --bb-line: #dfe3e7;
            --bb-surface: #ffffff;
            --bb-canvas: #f6f7f8;
            --bb-green: #16784b;
            --bb-red: #b4232f;
            --bb-amber: #a45f00;
        }

        html, body, [class*="css"] {
            letter-spacing: 0 !important;
        }

        body, [data-testid="stAppViewContainer"] {
            background: var(--bb-canvas);
            color: var(--bb-ink);
            overflow-x: hidden;
        }

        [data-testid="stMain"] .block-container {
            max-width: 1380px;
            padding: 3rem 1.5rem 3rem;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--bb-line);
            background: var(--bb-surface);
        }

        [data-testid="stSidebarContent"] {
            padding-top: 1rem;
        }

        h1 {
            color: var(--bb-ink);
            font-size: 2rem !important;
            line-height: 1.15 !important;
            margin-bottom: 0.25rem !important;
        }

        h2 {
            color: var(--bb-ink);
            font-size: 1.35rem !important;
            line-height: 1.25 !important;
        }

        h3 {
            color: var(--bb-ink);
            font-size: 1.05rem !important;
            line-height: 1.3 !important;
        }

        p, label, [data-testid="stMarkdownContainer"] {
            overflow-wrap: anywhere;
        }

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            max-width: 100%;
            overflow-wrap: anywhere;
            white-space: normal !important;
        }

        .bb-context {
            color: var(--bb-green);
            font-size: 0.75rem;
            font-weight: 750;
            letter-spacing: 0 !important;
            margin: 0 0 0.25rem;
            text-transform: uppercase;
        }

        .bb-status {
            align-items: center;
            color: var(--bb-ink);
            display: flex;
            font-size: 0.88rem;
            gap: 0.55rem;
            margin: 0.35rem 0;
        }

        .bb-dot {
            background: var(--bb-green);
            border-radius: 50%;
            flex: 0 0 0.55rem;
            height: 0.55rem;
            width: 0.55rem;
        }

        .bb-dot.warn { background: var(--bb-amber); }
        .bb-dot.error { background: var(--bb-red); }

        .bb-challenge-grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 0.35rem;
        }

        .bb-challenge-stat {
            border-top: 2px solid var(--bb-line);
            min-width: 0;
            padding: 0.7rem 0 0.25rem;
        }

        .bb-challenge-label {
            color: var(--bb-ink);
            font-size: 0.88rem;
            margin-bottom: 0.35rem;
        }

        .bb-challenge-value {
            color: var(--bb-ink);
            font-size: 1.55rem;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }

        [data-testid="stMetric"] {
            border-top: 2px solid var(--bb-line);
            padding: 0.7rem 0 0.15rem;
        }

        [data-testid="stMetricValue"] {
            color: var(--bb-ink);
            font-size: 1.55rem;
            line-height: 1.2;
            overflow-wrap: anywhere;
            white-space: normal;
        }

        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button,
        [data-baseweb="button-group"] button {
            border-radius: 6px !important;
            min-height: 2.75rem;
        }

        [data-testid="stButton"] button p,
        [data-testid="stFormSubmitButton"] button p {
            white-space: normal;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid var(--bb-line);
            border-radius: 6px;
            overflow: hidden;
        }

        [data-testid="stAlert"] {
            border-radius: 6px;
        }

        [data-baseweb="button-group"] {
            flex-wrap: wrap;
        }

        div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input,
        [data-testid="stDateInput"] input {
            min-height: 2.75rem;
        }

        .stPlotlyChart,
        [data-testid="stDataFrame"] {
            max-width: 100%;
            overflow-x: auto;
        }

        /* --- Edge / EV badges; edge is diagnostic, risk-EV drives price status --- */
        .bb-edge-badge {
            border-radius: 6px;
            display: inline-block;
            font-size: 0.95rem;
            font-weight: 650;
            margin: 0.15rem 0.4rem 0.15rem 0;
            padding: 0.35rem 0.7rem;
        }
        .bb-edge-label {
            font-size: 0.75rem;
            font-weight: 750;
            opacity: 0.75;
            text-transform: uppercase;
        }
        .bb-edge-strong { background: #e3f3ea; color: #16784b; }
        .bb-edge-ok { background: #fdf3e0; color: #a45f00; }
        .bb-edge-weak { background: #fbe9ea; color: #b4232f; }
        .bb-edge-none { background: #eceef0; color: #66707a; }

        /* --- Informative empty states --- */
        .bb-empty {
            background: var(--bb-surface);
            border: 1px solid var(--bb-line);
            border-radius: 8px;
            margin: 0.5rem 0 1rem;
            padding: 1.1rem 1.25rem;
        }
        .bb-empty-title {
            color: var(--bb-ink);
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .bb-empty-steps {
            color: var(--bb-muted);
            list-style: none;
            margin: 0 0 0.6rem;
            padding: 0;
        }
        .bb-empty-steps li {
            align-items: center;
            display: flex;
            gap: 0.55rem;
            margin: 0.3rem 0;
        }
        .bb-empty-step-num {
            align-items: center;
            background: var(--bb-green);
            border-radius: 50%;
            color: #ffffff;
            display: inline-flex;
            flex: 0 0 1.3rem;
            font-size: 0.78rem;
            font-weight: 700;
            height: 1.3rem;
            justify-content: center;
            width: 1.3rem;
        }
        .bb-empty-duration {
            color: var(--bb-muted);
            font-size: 0.82rem;
            margin-bottom: 0.8rem;
        }
        .bb-empty-example {
            background: var(--bb-canvas);
            border: 1px dashed var(--bb-line);
            border-radius: 6px;
            padding: 0.6rem 0.8rem;
        }
        .bb-empty-example-tag {
            color: var(--bb-green);
            display: block;
            font-size: 0.72rem;
            font-weight: 750;
            margin-bottom: 0.2rem;
            text-transform: uppercase;
        }
        .bb-empty-example-line {
            color: var(--bb-ink);
            font-weight: 650;
        }
        .bb-empty-example-pick {
            color: var(--bb-muted);
            font-size: 0.88rem;
        }

        /* --- 15K milestone bar (log scale) --- */
        .bb-mile-wrap {
            margin: 1.4rem 0 2.6rem;
            padding-top: 0.4rem;
            position: relative;
        }
        .bb-mile-track {
            background: #e4e7ea;
            border-radius: 4px;
            height: 10px;
            position: relative;
        }
        .bb-mile-fill {
            background: var(--bb-green);
            border-radius: 4px;
            height: 100%;
            transition: width 0.4s ease;
        }
        .bb-mile-marker {
            position: absolute;
            top: -3px;
            transform: translateX(-50%);
        }
        .bb-mile-marker.bb-align-right {
            transform: translateX(-100%);
        }
        .bb-mile-marker.bb-align-right .bb-mile-tick {
            margin: 0 0 0 auto;
        }
        .bb-mile-marker.bb-align-right .bb-mile-label {
            text-align: right;
        }
        .bb-mile-tick {
            background: var(--bb-muted);
            height: 16px;
            margin: 0 auto;
            width: 2px;
        }
        .bb-mile-marker.passed .bb-mile-tick {
            background: var(--bb-green);
        }
        .bb-mile-label {
            color: var(--bb-muted);
            font-size: 0.72rem;
            margin-top: 3px;
            text-align: center;
            white-space: nowrap;
        }
        .bb-mile-marker.passed .bb-mile-label {
            color: var(--bb-green);
            font-weight: 700;
        }
        .bb-mile-current {
            position: absolute;
            top: -6px;
            transform: translateX(-50%);
        }
        .bb-mile-current.bb-align-left {
            transform: none;
        }
        .bb-mile-current.bb-align-left .bb-mile-dot {
            margin: 0;
        }
        .bb-mile-current.bb-align-left .bb-mile-current-label {
            margin-left: -3px;
        }
        .bb-mile-current.bb-align-right {
            transform: translateX(-100%);
        }
        .bb-mile-current.bb-align-right .bb-mile-dot {
            margin: 0 0 0 auto;
        }
        .bb-mile-current.bb-align-right .bb-mile-current-label {
            margin-right: -3px;
        }
        .bb-mile-dot {
            background: #ffffff;
            border: 3px solid var(--bb-green);
            border-radius: 50%;
            height: 16px;
            margin: 0 auto;
            width: 16px;
        }
        .bb-mile-current-label {
            background: var(--bb-green);
            border-radius: 4px;
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: 700;
            margin-top: 5px;
            padding: 2px 6px;
            white-space: nowrap;
        }

        /* --- Mobile bottom navigation (hidden on desktop) --- */
        .st-key-bb_bottomnav {
            display: none;
        }

        @media (max-width: 767px) {
            .st-key-bb_bottomnav {
                background: var(--bb-surface);
                border-top: 1px solid var(--bb-line);
                bottom: 0;
                display: block;
                left: 0;
                padding: 0.3rem 0.35rem calc(0.3rem + env(safe-area-inset-bottom, 0px));
                position: fixed;
                right: 0;
                z-index: 999;
            }

            .st-key-bb_bottomnav [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap;
                gap: 0.3rem;
            }

            .st-key-bb_bottomnav [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                flex: 1 1 0 !important;
                min-width: 0 !important;
                width: auto !important;
            }

            .st-key-bb_bottomnav [data-testid="stButton"] button {
                font-size: 0.7rem !important;
                line-height: 1.15 !important;
                min-height: 2.9rem !important;
                padding: 0.15rem 0.1rem !important;
                width: 100%;
            }

            .st-key-bb_bottomnav [data-testid="stButton"] button p {
                font-size: 0.7rem !important;
            }

            [data-testid="stMain"] .block-container {
                padding-bottom: 5.5rem !important;
            }
        }

        @media (max-width: 900px) {
            [data-testid="stMain"] .block-container {
                padding: 3rem 1rem 2.5rem;
            }

            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
                gap: 0.75rem;
            }

            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                flex: 1 1 calc(50% - 0.75rem) !important;
                min-width: 220px !important;
                width: auto !important;
            }

            .bb-challenge-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 640px) {
            [data-testid="stMain"] .block-container {
                padding: 3rem 0.75rem 2rem;
            }

            h1 { font-size: 1.65rem !important; }
            h2 { font-size: 1.2rem !important; }

            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                flex: 1 1 100% !important;
                min-width: 100% !important;
                width: 100% !important;
            }

            [data-testid="stButton"] button,
            [data-testid="stFormSubmitButton"] button {
                min-height: 3rem;
                width: 100%;
            }

            [data-testid="stMetricValue"] {
                font-size: 1.35rem;
            }

            .bb-challenge-grid {
                gap: 0.75rem;
            }

            .bb-challenge-value {
                font-size: 1.35rem;
            }

            .bb-mile-label {
                font-size: 0.62rem;
            }

            .bb-mile-current-label {
                font-size: 0.68rem;
            }
        }

        /* Keep the direct mobile navigation usable after the generic
           responsive column rules above have been applied. */
        @media (max-width: 767px) {
            [data-testid="stMain"] .block-container {
                padding-bottom: calc(6.25rem + env(safe-area-inset-bottom, 0px)) !important;
            }

            .st-key-bb_bottomnav {
                padding-right: 0.35rem;
            }

            .st-key-bb_bottomnav [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.3rem;
                overflow-x: hidden;
            }

            .st-key-bb_bottomnav [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                flex: 1 1 0 !important;
                min-width: 0 !important;
                width: auto !important;
            }
        }

        @media (max-width: 430px) {
            [data-testid="stMain"] .block-container {
                padding-bottom: calc(6.25rem + env(safe-area-inset-bottom, 0px)) !important;
            }

            .st-key-bb_bottomnav [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
            }

            .st-key-bb_bottomnav [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                flex: 0 0 calc(25% - 0.225rem) !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_analyzer(
    module_version: int = _REQUIRED_ANALYZER_MODULE_VERSION,
    session_scope_id: str = "system",
):
    """Initialize the analyzer from the central configuration."""
    if module_version != _REQUIRED_ANALYZER_MODULE_VERSION:
        raise ValueError("Unsupported analyzer module version")
    config = load_app_config(st)
    if not config.api_football_key:
        return None
    return AdvancedBTTSAnalyzer(
        api_key=config.api_football_key,
        weather_api_key=config.weather_key,
        api_football_key=config.api_football_key,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _api_football_health(api_key: str) -> dict:
    """Return provider account state without exposing credential material.

    ``checked_at`` is cached together with the result, so it honestly shows
    when the check actually ran — not when the page was rendered.
    """
    checked_at = datetime.now().astimezone().isoformat()
    try:
        response = api_football_get(
            "https://v3.football.api-sports.io/status",
            headers={"x-apisports-key": api_key},
            timeout=8,
            priority=APIBudgetPriority.RECOMMENDATION,
            label="account status",
        )
        payload = response.json()
    except Exception as exc:
        return {
            "state": "unreachable",
            "label": "Live-API nicht erreichbar",
            "detail": type(exc).__name__,
            "checked_at": checked_at,
        }

    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        if isinstance(errors, dict):
            raw_detail = errors.get("access") or "; ".join(
                f"{key}: {value}" for key, value in errors.items()
            )
        else:
            raw_detail = str(errors)
        detail_text = str(raw_detail).strip() or "Unbekannter API-Fehler"
        lowered = detail_text.casefold()
        if "suspend" in lowered:
            state, label = "suspended", "Live-API gesperrt"
        elif "ratelimit" in lowered.replace(" ", "") or "rate limit" in lowered:
            # Kurzzeit-Limit (pro Minute): transient, kein harter Fehler
            state, label = "error", "Live-API Kurzzeit-Limit"
        else:
            state, label = "error", "Live-API Fehler"
        return {
            "state": state,
            "label": label,
            "detail": detail_text,
            "checked_at": checked_at,
        }

    provider_response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(provider_response, dict):
        return {
            "state": "error",
            "label": "Live-API Status unklar",
            "detail": f"HTTP {response.status_code}",
            "checked_at": checked_at,
        }

    subscription = provider_response.get("subscription") or {}
    active = subscription.get("active")
    plan = str(subscription.get("plan") or "aktiv")
    if active is False:
        return {
            "state": "suspended",
            "label": "Live-API inaktiv",
            "detail": f"Tarif: {plan}",
            "checked_at": checked_at,
        }
    return {
        "state": "active",
        "label": f"Live-API aktiv ({plan})",
        "detail": "",
        "checked_at": checked_at,
    }


def _format_stand(moment: Optional[datetime]) -> str:
    """German relative timestamp: 'heute 14:32', 'gestern 21:40', '27.07. 14:32'."""
    if moment is None:
        return "unbekannt"
    local = moment.astimezone()
    now = datetime.now().astimezone()
    if local.date() == now.date():
        return f"heute {local:%H:%M}"
    if (now.date() - local.date()).days == 1:
        return f"gestern {local:%H:%M}"
    return f"{local:%d.%m. %H:%M}"


def _stats_freshness() -> Optional[datetime]:
    """Newest modification time across the writable data stores."""
    candidates = (
        Path(__file__).resolve().parent / "shadow_clv.db",
        Path(__file__).resolve().parent / "xg_cache.db",
        Path(__file__).resolve().parent / "challenge_15k.db",
    )
    mtimes = [
        datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        for path in candidates
        if path.exists()
    ]
    return max(mtimes) if mtimes else None


def _scan_spinner_css(running_pages: set) -> str:
    """CSS für ein drehendes Rädchen (Border-Spinner) am Radio-Label jeder
    Seite, deren Hintergrund-Scan läuft. Greift der Selektor nach einer
    Streamlit-DOM-Änderung nicht mehr, fehlt schlicht das Rädchen — die
    Caption-Zeile darunter bleibt als Fallback."""
    order = list(MAIN_PAGES)
    rules = []
    for page in sorted(running_pages):
        if page not in order:
            continue
        nth = order.index(page) + 1
        rules.append(
            'section[data-testid="stSidebar"] [data-testid="stRadio"] '
            f'[role="radiogroup"] > label:nth-of-type({nth}) p::after {{'
            'content: ""; display: inline-block; width: 0.72em; height: 0.72em; '
            "margin-left: 0.45em; vertical-align: -0.08em; "
            "border: 2px solid rgba(128, 128, 128, 0.35); "
            "border-top-color: #22c55e; border-radius: 50%; "
            "animation: bbNavSpin 0.8s linear infinite; }"
        )
    if not rules:
        return ""
    return (
        "<style>@keyframes bbNavSpin { to { transform: rotate(360deg); } }"
        + "".join(rules)
        + "</style>"
    )


@st.fragment(run_every=2)
def _sidebar_scan_poller() -> None:
    """Löst nur dann einen Voll-Rerun aus, wenn sich die Menge der Seiten
    mit laufendem Scan ändert — so erscheint und verschwindet das Rädchen
    von selbst, ohne Dauer-Reruns."""
    running = frozenset(
        scan_jobs.running_pages(PAGE_SCAN_JOBS, scope=_session_scope_id())
    )
    if running != st.session_state.get("_nav_running_pages"):
        st.session_state["_nav_running_pages"] = running
        st.rerun()


def _render_sidebar(analyzer) -> str:
    del analyzer  # Adminfunktionen sind nicht Teil der öffentlichen Navigation.
    with st.sidebar:
        st.markdown("## BetBoy")
        st.caption("Wettfinder")
        previous_workspace = st.session_state.get("workspace")
        if previous_workspace == "System":
            st.session_state["workspace"] = "Wettfinder"
            st.session_state["settings_open"] = False
        elif previous_workspace in LEGACY_PAGE_ALIASES:
            st.session_state["workspace"] = LEGACY_PAGE_ALIASES[previous_workspace]
        elif previous_workspace not in MAIN_PAGES:
            st.session_state["workspace"] = "Wettfinder"

        workspace = st.radio(
            "Arbeitsbereich",
            list(MAIN_PAGES),
            label_visibility="collapsed",
            key="workspace",
        )
        st.session_state["settings_open"] = False
        st.session_state.setdefault("_nav_running_pages", frozenset())
        running_scan_pages = scan_jobs.running_pages(
            PAGE_SCAN_JOBS,
            scope=_session_scope_id(),
        )
        if running_scan_pages:
            st.markdown(
                _scan_spinner_css(running_scan_pages), unsafe_allow_html=True
            )
            st.caption("Suche läuft: " + ", ".join(sorted(running_scan_pages)))
        _sidebar_scan_poller()

    return workspace


def _persist_prematch(results) -> Optional[dict]:
    """Verdichtet den BTTS-Scan zu Wett-Check-Signalen (JSON-bar)."""
    if not isinstance(results, pd.DataFrame) or results.empty:
        return {"signals": []}
    rows = []
    for row in results.head(40).to_dict("records"):
        analysis = row.get("_analysis")
        analysis = analysis if isinstance(analysis, dict) else {}
        details = analysis.get("details")
        details = details if isinstance(details, dict) else {}
        candidate = prematch_btts_candidate(
            row,
            snapshot_age_seconds=0.0,
            validated_model_available=details.get("ml_active") is True,
            freemode=False,
        )
        probability = candidate.model_probability
        haircut = candidate.probability_haircut
        if not candidate.model_ready or probability is None or haircut is None:
            continue
        rows.append(
            {
                "home": row.get("Home"),
                "away": row.get("Away"),
                "league": row.get("League"),
                "date": str(row.get("Date")),
                "market": f"BTTS {candidate.selection}",
                "p": probability / 100.0,
                "haircut": haircut / 100.0,
                "evidence_stage": candidate.evidence_stage,
                "policy_version": BETTING_POLICY_VERSION,
            }
        )
    return {"signals": rows}


def _persist_red_cards(snapshot: dict) -> Optional[dict]:
    """Verdichtet den Platzverweis-Scan zu Wett-Check-Signalen."""
    if not isinstance(snapshot, dict):
        return {"signals": []}
    rows = []
    for entry in (snapshot.get("cards") or [])[:20]:
        if not isinstance(entry, dict):
            continue
        candidate = red_card_candidate(
            entry,
            snapshot_age_seconds=0.0,
            freemode=False,
        )
        probability = candidate.model_probability
        haircut = candidate.probability_haircut
        home, away = entry.get("home"), entry.get("away")
        if (
            not candidate.model_ready
            or probability is None
            or haircut is None
            or not home
            or not away
        ):
            continue
        rows.append(
            {
                "home": home,
                "away": away,
                "league": None,
                "date": snapshot.get("scanned_at"),
                "market": f"Nächstes Tor: {candidate.selection}",
                "p": probability / 100.0,
                "haircut": haircut / 100.0,
                "evidence_stage": candidate.evidence_stage,
                "policy_version": BETTING_POLICY_VERSION,
            }
        )
    return {"signals": rows}


def _persist_live(snapshot: dict) -> Optional[dict]:
    """Verdichtet den Live-Scan zu Wett-Check-Signalen (alle drei Märkte).

    Nutzt dieselbe _live_market_signal-Logik wie die Live-Seite, damit die
    Wett-Check-Wahrscheinlichkeit exakt der Seiten-Logik entspricht
    (Live-Werte liegen in Prozent vor → /100).
    """
    if not isinstance(snapshot, dict):
        return {"signals": []}
    rows = []
    for item in (snapshot.get("analyses") or [])[:40]:
        if not isinstance(item, dict):
            continue
        home, away = item.get("home_team"), item.get("away_team")
        if not home or not away:
            continue
        score = item.get("score")
        minute = item.get("minute")
        context = (
            f"Stand {score}, {minute}'"
            if score is not None and minute is not None
            else "Live"
        )
        for market in LIVE_MARKET_OPTIONS:
            probability, selection = _live_market_signal(item, market)
            if probability is None or not 0.0 < probability < 100.0:
                continue
            candidate = live_football_candidate(
                item,
                market=market,
                selection=selection,
                probability=probability,
                snapshot_age_seconds=0.0,
                freemode=False,
            )
            if (
                not candidate.model_ready
                or candidate.model_probability is None
                or candidate.probability_haircut is None
            ):
                continue
            rows.append(
                {
                    "home": home,
                    "away": away,
                    "league": item.get("league"),
                    "date": snapshot.get("scanned_at"),
                    "market": f"Live: {selection} ({context})",
                    "p": candidate.model_probability / 100.0,
                    "haircut": candidate.probability_haircut / 100.0,
                    "evidence_stage": candidate.evidence_stage,
                    "policy_version": BETTING_POLICY_VERSION,
                }
            )
    return {"signals": rows}


def _prepare_results(results: list[pd.DataFrame]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    combined = pd.concat(results, ignore_index=True)
    required = {"BTTS %", "Data Quality"}
    if not required.issubset(combined.columns):
        raise ValueError("Analyzer result is missing probability or data-quality columns")
    combined["BTTS_num"] = _percent_series(combined["BTTS %"])
    combined["Quality_num"] = _percent_series(combined["Data Quality"])
    return combined


@_serialized_analyzer()
def _scan_prematch(
    analyzer,
    leagues: list[str],
    days_ahead: int,
    search_date: Optional[date] = None,
    progress_cb=None,
) -> pd.DataFrame:
    # Hintergrund-tauglich: mit progress_cb keinerlei st.*-Aufrufe.
    scan_start = search_date or zurich_today()
    if isinstance(scan_start, datetime) or not isinstance(scan_start, date):
        raise ValueError("search_date must be a date")
    progress = None if progress_cb else st.progress(0)
    status = None if progress_cb else st.empty()
    collected = []
    total = max(len(leagues), 1)
    if progress_cb:
        progress_cb(0.01, f"{len(leagues)} Ligen werden vorbereitet")
    try:
        for index, league_code in enumerate(leagues):
            if progress_cb:
                progress_cb(
                    0.03 + 0.92 * index / total,
                    f"Liga {index + 1}/{len(leagues)}: "
                    f"{_league_label_for_code(league_code)}",
                )
            else:
                status.caption(f"Analysiere {league_code} ({index + 1}/{len(leagues)})")
            league_results = analyzer.analyze_upcoming_matches(
                league_code,
                days_ahead=days_ahead,
                min_probability=0,
                start_date=scan_start,
            )
            if league_results is not None and not league_results.empty:
                league_results = league_results.copy()
                league_results["League"] = league_code
                collected.append(league_results)
            if progress_cb:
                progress_cb(
                    0.03 + 0.92 * (index + 1) / total,
                    f"Liga {index + 1}/{len(leagues)} abgeschlossen",
                )
            else:
                fraction = (index + 1) / total
                progress.progress(
                    fraction,
                    text=f"{int(round(fraction * 100))} % · "
                    f"Liga {index + 1}/{len(leagues)}",
                )
    finally:
        if status is not None:
            status.empty()
        if progress is not None:
            progress.empty()
    result = _prepare_results(collected)
    if progress_cb:
        progress_cb(1.0, f"Fertig: {len(result)} Spiele modelliert")
    return result


def _analysis_for_row(row: pd.Series) -> dict:
    value = row.get("_analysis")
    return value if isinstance(value, dict) else {}


def _render_match_overview(row: pd.Series) -> None:
    analysis = _analysis_for_row(row)
    st.subheader(f"{row.get('Home', 'Home')} vs {row.get('Away', 'Away')}")
    st.caption(f"{row.get('League', 'n/a')} | {row.get('Date', 'n/a')}")

    metrics = st.columns(3)
    metrics[0].metric("BTTS", row.get("BTTS %", "n/a"))
    metrics[1].metric("Evidenzscore", row.get("Data Quality", "n/a"))
    metrics[2].metric("Erwartete Tore", row.get("xG Total", "n/a"))

    model_status = row.get("Modellstatus", "Keine Schätzung")
    st.info(
        f"Explorative Modellschätzung: {model_status}. Nicht kalibriert, nicht "
        "einsatzfähig und ohne verifizierte Quote keine Value-Aussage."
    )

    home_stats = analysis.get("home_stats", {})
    away_stats = analysis.get("away_stats", {})
    home_form = analysis.get("home_form", {})
    away_form = analysis.get("away_form", {})
    insights = []
    if _numeric_or_zero(home_stats.get("btts_rate")) >= 70 and _numeric_or_zero(
        away_stats.get("btts_rate")
    ) >= 70:
        insights.append("Beide Teams haben am jeweiligen Spielort eine hohe BTTS-Rate.")
    if _numeric_or_zero(home_stats.get("avg_goals_scored")) >= 2 and _numeric_or_zero(
        away_stats.get("avg_goals_scored")
    ) >= 1.5:
        insights.append("Beide Offensiven liegen über den aktiven Schwellen.")
    if _numeric_or_zero(home_stats.get("avg_goals_conceded")) >= 1.3 and _numeric_or_zero(
        away_stats.get("avg_goals_conceded")
    ) >= 1.3:
        insights.append("Beide Defensiven lassen im Mittel mindestens 1,3 Tore zu.")
    if (
        _numeric_or_zero(home_form.get("matches_played")) >= 3
        and _numeric_or_zero(away_form.get("matches_played")) >= 3
        and _numeric_or_zero(home_form.get("btts_rate")) >= 60
        and _numeric_or_zero(away_form.get("btts_rate")) >= 60
    ):
        insights.append("Die jüngste Ligafrom unterstützt das BTTS-Signal.")

    if insights:
        st.markdown("**Einordnung**")
        for insight in insights:
            st.write(f"- {insight}")
    else:
        st.caption("Keine zusätzliche Auffälligkeit oberhalb der festen Signalschwellen.")


def _render_match_models(row: pd.Series) -> None:
    analysis = _analysis_for_row(row)
    if not analysis:
        st.info("Für dieses Match ist kein Methoden-Breakdown gespeichert.")
        return

    ml_active = bool(analysis.get("details", {}).get("ml_active"))
    model_rows = [
        {
            "Methode": "Statistisches Aggregat",
            "Wahrscheinlichkeit": analysis.get("statistical_probability"),
            "Gewicht": 0 if ml_active else 60,
        },
        {
            "Methode": "Poisson-Basis",
            "Wahrscheinlichkeit": analysis.get("poisson_btts"),
            "Gewicht": 0 if ml_active else 40,
        },
    ]
    if ml_active and analysis.get("ml_probability") is not None:
        model_rows.append(
            {
                "Methode": "Walk-forward ML",
                "Wahrscheinlichkeit": analysis["ml_probability"],
                "Gewicht": 100,
            }
        )

    methods = pd.DataFrame(model_rows).dropna(subset=["Wahrscheinlichkeit"])
    if methods.empty:
        st.info("Keine vergleichbaren Modellwerte vorhanden.")
        return

    figure = go.Figure(
        go.Bar(
            x=methods["Wahrscheinlichkeit"],
            y=methods["Methode"],
            orientation="h",
            marker_color=["#202428", "#1f8a70", "#d38b18"][: len(methods)],
            text=methods["Wahrscheinlichkeit"].map(lambda value: f"{value:.1f}%"),
            textposition="auto",
        )
    )
    figure.update_layout(
        height=260,
        margin=dict(l=0, r=12, t=12, b=30),
        xaxis_title="BTTS-Wahrscheinlichkeit (%)",
        yaxis_title=None,
        showlegend=False,
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    st.dataframe(methods, use_container_width=True, hide_index=True)
    evidence = analysis.get("details", {}).get("evidence_breakdown", {})
    contributions = evidence.get("contributions", {})
    if contributions:
        labels = {
            "home_venue": ("Heim-Venue-Stichprobe", 30.0),
            "away_venue": ("Auswärts-Venue-Stichprobe", 30.0),
            "home_form": ("Heimform", 10.0),
            "away_form": ("Auswärtsform", 10.0),
            "model_agreement": ("Modellübereinstimmung", 20.0),
        }
        evidence_rows = [
            {
                "Evidenzkomponente": labels[key][0],
                "Punkte": round(float(contributions.get(key, 0.0)), 1),
                "Maximum": labels[key][1],
            }
            for key in labels
        ]
        st.markdown("### Evidenzscore")
        st.dataframe(pd.DataFrame(evidence_rows), use_container_width=True, hide_index=True)
        samples = evidence.get("samples", {})
        st.caption(
            "Stichproben Heim/Auswärts/Form: "
            f"{samples.get('home_venue_matches', 0)}/"
            f"{samples.get('away_venue_matches', 0)}/"
            f"{samples.get('home_form_matches', 0)}/"
            f"{samples.get('away_form_matches', 0)}. "
            "Der Score ist kein kalibriertes Sicherheits- oder Gewinnmaß."
        )
    st.caption("H2H ist deskriptiv und besitzt im aktiven Modell kein Gewicht.")


def _render_team_block(name: str, venue: str, stats: dict, form: dict) -> None:
    st.markdown(f"### {name}")
    st.caption(venue)
    st.write(f"Spiele: **{stats.get('matches_played', 0)}**")
    st.write(f"BTTS-Rate: **{_format_optional(stats.get('btts_rate'), 1, '%')}**")
    st.write(f"Tore/Spiel: **{_format_optional(stats.get('avg_goals_scored'), 2)}**")
    st.write(f"Gegentore/Spiel: **{_format_optional(stats.get('avg_goals_conceded'), 2)}**")
    st.write(f"Form: **{form.get('form_string', 'n/a')}**")
    st.write(f"Form-BTTS: **{_format_optional(form.get('btts_rate'), 1, '%')}**")


def _render_match_teams(row: pd.Series) -> None:
    analysis = _analysis_for_row(row)
    if not analysis:
        st.info("Für dieses Match sind keine Teamdetails gespeichert.")
        return

    columns = st.columns(2)
    with columns[0]:
        _render_team_block(
            str(row.get("Home", "Home")),
            "Heim",
            analysis.get("home_stats", {}),
            analysis.get("home_form", {}),
        )
    with columns[1]:
        _render_team_block(
            str(row.get("Away", "Away")),
            "Auswärts",
            analysis.get("away_stats", {}),
            analysis.get("away_form", {}),
        )

    h2h = analysis.get("h2h", {})
    st.divider()
    st.markdown("### Direkter Vergleich")
    st.caption("Nur deskriptiv; kein Eingang in Modell oder Konfidenz.")
    h2h_columns = st.columns(3)
    h2h_columns[0].metric("Spiele", h2h.get("matches_played", 0))
    h2h_columns[1].metric("BTTS", h2h.get("btts_count", 0))
    h2h_columns[2].metric("BTTS-Rate", _format_optional(h2h.get("btts_rate"), 1, "%"))


def _render_prematch_results(
    results: pd.DataFrame,
    min_probability: int,
    min_quality: int,
    *,
    scanned_at: Optional[str],
    validated_model_available: bool,
) -> None:
    btts_probability = pd.to_numeric(results["BTTS_num"], errors="coerce")
    likely_btts_probability = pd.concat(
        [btts_probability, 100.0 - btts_probability],
        axis=1,
    ).max(axis=1)
    eligible = results[
        (likely_btts_probability >= min_probability)
        & (results["Quality_num"] >= min_quality)
    ].copy()
    if eligible.empty:
        st.error(
            "KEINE WETTE — kein Spiel erreicht die gewählten Mindestwerte. "
            "Die Schwellen lassen sich oben im Filter lockern."
        )
        return

    snapshot_age = _snapshot_age_seconds(scanned_at)
    candidate_rows = []
    for _, row in eligible.iterrows():
        candidate = prematch_btts_candidate(
            row,
            snapshot_age_seconds=snapshot_age,
            validated_model_available=validated_model_available,
            freemode=_freemode_enabled(),
        )
        candidate_rows.append((candidate, row))
    candidate_rows.sort(
        key=lambda item: (
            item[0].model_ready,
            item[0].risk_adjusted_probability or -1.0,
            _numeric_or_zero(item[1].get("Quality_num")),
        ),
        reverse=True,
    )
    shortlist = candidate_rows[:3]
    ready_rows = [(candidate, row) for candidate, row in shortlist if candidate.model_ready]

    if not ready_rows:
        st.warning(
            f"KEINE WETTE — keines der {len(candidate_rows)} geprüften Spiele "
            "besteht alle Prüf- und Freigabekriterien. Die quotenfreie "
            "Prognose bleibt trotzdem sichtbar."
        )
        st.caption(
            "Die Quote hat diese Spiele nicht aussortiert. Warum die "
            "preisunabhängige Modellprüfung fehlt, steht direkt beim Kandidaten."
        )
        selectable_rows = shortlist
    else:
        st.success(
            f"{len(ready_rows)} von {len(candidate_rows)} geprüften Spielen bestehen "
            "die Modellprüfung. Der automatische Marktvergleich bewertet danach, "
            "ob der angebotene Preis die Mindestquote erreicht."
        )
        selectable_rows = ready_rows

    if selectable_rows:
        options = list(range(len(selectable_rows)))
        selected_position = st.selectbox(
            "Spiel auswählen",
            options,
            format_func=lambda position: (
                f"{selectable_rows[position][0].event_label} | "
                f"{selectable_rows[position][0].market}: "
                f"{selectable_rows[position][0].selection or 'keine Auswahl'}"
            ),
            key="prematch_bet_candidate",
        )
        candidate, selected_row = selectable_rows[selected_position]
        render_price_decision(
            candidate,
            key=f"prematch_{candidate.event_key}_{scanned_at}",
            bankroll_key="football_bet_finder_bankroll",
            save_source="Fußball BTTS",
        )

    with st.expander(f"Alle {len(candidate_rows)} geprüften Spiele mit Einzelgründen"):
        display_frame = pd.DataFrame(
            [
                {
                    "Modellprüfung": (
                        "✅ Bestanden" if item.model_ready else "❌ Blockiert"
                    ),
                    "Zeit": row.get("Date"),
                    "Liga": row.get("League"),
                    "Spiel": item.event_label,
                    "Auswahl": item.selection,
                    "Modell %": item.model_probability,
                    "Mindestquote": item.minimum_odds,
                    "Grund": "" if item.model_ready else plain_german(
                        item.blockers[0] if item.blockers else "Kriterien nicht erfüllt"
                    ),
                }
                for item, row in shortlist
            ]
        )
        st.dataframe(display_frame, use_container_width=True, hide_index=True)


def render_matches(analyzer) -> None:
    if analyzer is None:
        st.error("Die Fußball-Suche ist vorübergehend nicht verfügbar.")
        return

    search_date = zurich_today()
    st.subheader("Filter")
    filter_columns = st.columns(3)
    min_probability = filter_columns[0].slider(
        "Min. wahrscheinlichere BTTS-Auswahl (%)",
        50,
        90,
        60,
        5,
        key="prematch_min_probability",
        help="Modellwahrscheinlichkeit ohne Buchmacherquote; wird lokal auf den Snapshot angewendet.",
    )
    min_quality = filter_columns[1].slider(
        "Min. Evidenzscore (%)",
        50,
        95,
        60,
        5,
        key="prematch_min_quality",
        help=(
            "Kein Gewinnmaß: 60 Punkte Venue-Stichproben, 20 Punkte Formstichproben "
            "und 20 Punkte Modellübereinstimmung."
        ),
    )
    days_ahead = filter_columns[2].slider(
        "Tage voraus", 1, 14, 7, key="prematch_days_ahead"
    )

    available_leagues = list(analyzer.engine.LEAGUES_CONFIG)
    defaults = [code for code in DEFAULT_PREMATCH_LEAGUES if code in available_leagues]
    if not defaults:
        defaults = available_leagues[: min(3, len(available_leagues))]
    all_scope_label = f"Alle ({len(available_leagues)})"
    favorite_scope_label = f"Favoriten ({len(defaults)})"
    league_scope = _segmented(
        "Ligen",
        [all_scope_label, favorite_scope_label, "Auswahl"],
        "prematch_league_scope_v2",
        all_scope_label,
    )
    if league_scope == favorite_scope_label:
        selected_leagues = defaults
        st.caption(
            ", ".join(_league_label_for_code(code) for code in selected_leagues)
        )
    elif league_scope == all_scope_label:
        selected_leagues = available_leagues
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_leagues,
            default=defaults,
            format_func=_league_label_for_code,
            key="prematch_leagues",
        )

    action_columns = st.columns([1, 2])
    run_scan = action_columns[0].button(
        "BTTS-Wetten finden",
        type="primary",
        use_container_width=True,
        key="run_prematch_scan",
    )
    if run_scan and not selected_leagues:
        st.warning("Mindestens eine Liga auswählen.")
    elif run_scan:
        if scan_jobs.get_job(_job_key("prematch"))["state"] == "running":
            st.info("Der BTTS-Scan läuft bereits im Hintergrund.")
        else:
            st.session_state["prematch_pending_scope"] = _scope_signature(
                selected_leagues,
                days_ahead,
                search_date,
            )
            scan_jobs.start_job(
                _job_key("prematch"),
                _scan_prematch,
                args=(
                    analyzer,
                    list(selected_leagues),
                    days_ahead,
                    search_date,
                ),
                persist_name="prematch",
                persist_fn=_persist_prematch,
                persist_scope=_session_scope_id(),
            )

    job = scan_jobs.get_job(_job_key("prematch"))
    if job["state"] == "running":
        scan_progress_fragment(
            _job_key("prematch"),
            "BTTS-Scan",
        )
    elif job["state"] == "done":
        results = job.get("result")
        snapshot = {
            "version": PREMATCH_SNAPSHOT_VERSION,
            "scanned_at": datetime.now().astimezone().isoformat(),
            "scope": st.session_state.pop(
                "prematch_pending_scope",
                _scope_signature(selected_leagues, days_ahead, search_date),
            ),
            "results": results,
        }
        st.session_state["prematch_snapshot"] = snapshot
        st.session_state["prematch_results"] = results
        st.session_state["all_results"] = results
        scan_jobs.clear_job(_job_key("prematch"))
        if results.empty:
            window_label = _prematch_window_label(snapshot.get("scope"))
            st.error(
                f"NICHT WETTEN: Im Zeitraum {window_label} wurden für diese "
                "Auswahl keine kommenden Spiele gefunden."
            )
        else:
            st.success(f"{len(results)} Spiele geprüft — Ergebnis:")
    elif job["state"] == "error":
        st.error("Die BTTS-Suche konnte nicht abgeschlossen werden.")
        scan_jobs.clear_job(_job_key("prematch"))

    snapshot = st.session_state.get("prematch_snapshot")
    if not isinstance(snapshot, dict):
        st.info("Noch keine BTTS-Suche für diese Auswahl.")
        return
    if snapshot.get("version") != PREMATCH_SNAPSHOT_VERSION:
        st.warning("Dieses Prematch-Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return
    current_scope = _scope_signature(selected_leagues, days_ahead, search_date)
    if snapshot.get("scope") != current_scope:
        st.warning("Liga oder Zeitraum wurden seit dem Ergebnis geändert. Wetten neu suchen.")
        return
    results = snapshot.get("results")
    window_label = _prematch_window_label(snapshot.get("scope"))
    st.caption(
        f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))} · "
        f"Suchzeitraum: {window_label}"
    )
    if not isinstance(results, pd.DataFrame) or results.empty:
        st.info(f"Im Zeitraum {window_label} wurden keine kommenden Spiele gefunden.")
        return
    _render_prematch_results(
        results,
        min_probability,
        min_quality,
        scanned_at=snapshot.get("scanned_at"),
        validated_model_available=bool(analyzer.model_trained),
    )


def _live_probability(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    return probability if math.isfinite(probability) and 0.0 <= probability <= 100.0 else None


def _live_market_signal(analysis: dict, market: str) -> tuple[Optional[float], str]:
    """Return the selected live-market probability and its concrete selection."""
    if not isinstance(analysis, dict):
        return None, "Ungültige Modelldaten"
    if market == "BTTS":
        return _live_probability(analysis.get("btts_prob")), "Beide Teams treffen"

    remaining = analysis.get("remaining_goals")
    if not isinstance(remaining, dict):
        return None, "Restspiel nicht berechenbar"
    if market == "Noch ein Tor":
        return (
            _live_probability(remaining.get("over_0_5_probability")),
            "Mindestens 1 weiteres Tor",
        )
    if market == "Team trifft noch":
        home_probability = _live_probability(remaining.get("home_scores_probability"))
        away_probability = _live_probability(remaining.get("away_scores_probability"))
        if home_probability is None or away_probability is None:
            return None, "Teamtor nicht berechenbar"
        if math.isclose(home_probability, away_probability, abs_tol=0.05):
            return None, "Kein klarer Teamvorteil"
        if home_probability > away_probability:
            return home_probability, f"{analysis.get('home_team', 'Heimteam')} trifft noch"
        return away_probability, f"{analysis.get('away_team', 'Auswärtsteam')} trifft noch"
    raise ValueError("Unbekannter Live-Markt")


def _filter_live_opportunities(
    analyses: list[dict],
    minimum_probability: int,
    minimum_quality: str,
    market: str = "BTTS",
) -> list[dict]:
    quality_rank = {"LOW": 1, "MEDIUM": 2}
    required_rank = {
        "Basis: teilweise Daten": 1,
        "Berechenbar": 1,
        "Streng: Live-xG + Prematch (empfohlen)": 2,
        "Live-xG + Prematch": 2,
    }.get(minimum_quality)
    if required_rank is None:
        raise ValueError("Unbekannte Live-Datenbasis")
    if market not in LIVE_MARKET_OPTIONS:
        raise ValueError("Unbekannter Live-Markt")

    opportunities = []
    for analysis in analyses:
        probability, _ = _live_market_signal(analysis, market)
        quality = analysis.get(
            "live_data_quality",
            analysis.get("btts_confidence", "INSUFFICIENT"),
        )
        if market == "BTTS" and analysis.get("btts_confidence") == "COMPLETE":
            continue
        if probability is None:
            continue
        if probability >= minimum_probability and quality_rank.get(quality, 0) >= required_rank:
            opportunities.append(analysis)
    return sorted(
        opportunities,
        key=lambda item: _live_market_signal(item, market)[0] or 0.0,
        reverse=True,
    )


@_serialized_analyzer()
def _scan_live_football(analyzer, config=None, progress_cb=None) -> dict:
    from api_football import APIFootball
    from ultra_live_scanner_v3 import UltraLiveScanner

    scanned_at = datetime.now().astimezone().isoformat()
    if config is None:
        config = load_app_config(st)
    if not config.api_football_key:
        raise ValueError("API-Football-Key fehlt")

    if progress_cb:
        progress_cb(0.03, "Live-Spielplan wird geladen")
    api = APIFootball(config.api_football_key)
    scanner = UltraLiveScanner(analyzer, api)
    all_matches = api.get_live_matches()
    supported_ids = set(api.league_ids.values())
    matches = [
        match
        for match in all_matches
        if match.get("league", {}).get("id") in supported_ids
    ]
    if progress_cb:
        progress_cb(
            0.12,
            f"{len(matches)} unterstützte Live-Spiele gefunden",
        )

    analyses = []
    skipped = 0
    # Hintergrund-tauglich: mit progress_cb keinerlei st.*-Aufrufe.
    progress = None if progress_cb else st.progress(0.0, text="Live-Spiele werden analysiert...")
    total = max(1, len(matches))
    for index, match in enumerate(matches):
        analysis = scanner.analyze_live_match_ultra(match)
        if analysis:
            analyses.append(analysis)
        else:
            skipped += 1
        if progress_cb:
            progress_cb(
                0.12 + 0.83 * (index + 1) / total,
                f"Live-Spiel {index + 1}/{len(matches)} analysiert",
            )
        else:
            fraction = (index + 1) / total
            progress.progress(
                fraction,
                text=f"{int(round(fraction * 100))} % · "
                f"Live-Spiel {index + 1}/{len(matches)}",
            )
    if progress is not None:
        progress.empty()
    insufficient = sum(
        1 for item in analyses if item.get("live_data_quality") == "INSUFFICIENT"
    )
    provider_note = None
    if insufficient:
        provider_note = (
            f"{insufficient} von {len(matches)} Live-Spielen ohne verwertbare "
            "Live-Statistik (kleinere Ligen ohne Provider-Coverage)."
        )
    if progress_cb:
        progress_cb(1.0, f"Fertig: {len(analyses)} Live-Analysen")
    return {
        "version": LIVE_SNAPSHOT_VERSION,
        "scanned_at": scanned_at,
        "provider_matches": len(all_matches),
        "supported_matches": len(matches),
        "analyses": analyses,
        "skipped_matches": skipped,
        "provider_error": provider_note,
    }


def _render_live_football(analyzer, market: str) -> None:
    if market not in LIVE_MARKET_OPTIONS:
        raise ValueError("Unbekannter Live-Markt")
    market_notes = {
        "BTTS": "Beide Teams treffen bis zum Spielende; der aktuelle Spielstand zählt mit.",
        "Noch ein Tor": (
            "Restspiel-Markt: Es zählt mindestens ein Tor nach diesem Snapshot. "
            "Nicht mit dem normalen Live-Gesamttor-Markt verwechseln."
        ),
        "Team trifft noch": "Restspiel-Markt: Das angezeigte Team erzielt nach dem Snapshot noch ein Tor.",
    }
    st.caption(market_notes[market])

    minimum_probability = st.slider(
        "Min. Modellwahrscheinlichkeit (%)",
        0,
        100,
        55,
        key=f"live_min_probability_{market}",
        help="Lokaler Filter auf den aktuellen Live-Snapshot; löst keinen neuen Provider-Abruf aus.",
    )
    minimum_quality = LIVE_DATA_BASIS_OPTIONS[0]
    if st.session_state.get("live_snapshot_invalidated_by_red_card"):
        st.warning(
            "Seit dem letzten Live-Datenstand wurde ein neuer Platzverweis erkannt. "
            "Der alte Datenstand wurde verworfen; Live-Wetten neu suchen."
        )
    if st.button(
        "Live-Wetten finden",
        type="primary",
        use_container_width=True,
        key="run_live_football",
    ):
        if scan_jobs.get_job(_job_key("live"))["state"] == "running":
            st.info("Der Live-Scan läuft bereits im Hintergrund.")
        else:
            config = load_app_config(st)
            if not config.api_football_key:
                st.error("Die Live-Suche ist vorübergehend nicht verfügbar.")
            else:
                scan_jobs.start_job(
                    _job_key("live"),
                    _scan_live_football,
                    args=(analyzer,),
                    kwargs={"config": config},
                    persist_name="live",
                    persist_fn=_persist_live,
                    persist_scope=_session_scope_id(),
                )

    job = scan_jobs.get_job(_job_key("live"))
    if job["state"] == "running":
        scan_progress_fragment(
            _job_key("live"),
            "Live-Scan",
        )
    elif job["state"] == "done":
        st.session_state["live_football_snapshot"] = job.get("result")
        st.session_state.pop("live_snapshot_invalidated_by_red_card", None)
        scan_jobs.clear_job(_job_key("live"))
    elif job["state"] == "error":
        st.error("Die Live-Suche konnte nicht abgeschlossen werden.")
        scan_jobs.clear_job(_job_key("live"))

    snapshot = st.session_state.get("live_football_snapshot")
    if not snapshot:
        st.info("Noch keine Live-Suche für diese Wettart.")
        return
    if snapshot.get("version") != LIVE_SNAPSHOT_VERSION:
        st.warning("Dieses Live-Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return

    st.caption(f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))}")
    analyses = snapshot.get("analyses", [])
    opportunities = _filter_live_opportunities(
        analyses,
        minimum_probability,
        minimum_quality,
        market,
    )
    if snapshot.get("provider_error"):
        st.caption(f"Provider-Hinweis: {snapshot['provider_error']}")

    if not opportunities:
        st.error(
            "NICHT WETTEN: Kein Live-Spiel über dem Markt-, Daten- und "
            "Wahrscheinlichkeits-Gate. Alle Live-Spiele stehen unten im Überblick."
        )
    else:
        snapshot_age = _snapshot_age_seconds(snapshot.get("scanned_at"))
        candidate_items = []
        for item in opportunities:
            probability, selection = _live_market_signal(item, market)
            candidate = live_football_candidate(
                item,
                market=market,
                selection=selection,
                probability=probability,
                snapshot_age_seconds=snapshot_age,
                freemode=_freemode_enabled(),
            )
            candidate_items.append((candidate, item))
        candidate_items.sort(
            key=lambda pair: (
                pair[0].model_ready,
                pair[0].risk_adjusted_probability or -1.0,
            ),
            reverse=True,
        )
        candidate_items = candidate_items[:3]
        live_detail_options = list(range(len(candidate_items)))
        live_detail_key = "live_match_detail"
        if st.session_state.get(live_detail_key) not in live_detail_options:
            st.session_state[live_detail_key] = live_detail_options[0]
        selected = st.selectbox(
            "Wettkandidat",
            live_detail_options,
            format_func=lambda index: (
                f"{'PREIS PRÜFEN' if candidate_items[index][0].model_ready else 'NICHT WETTEN'} | "
                f"{candidate_items[index][0].event_label} | {candidate_items[index][0].selection}"
            ),
            key=live_detail_key,
        )
        candidate, _item = candidate_items[selected]
        render_price_decision(
            candidate,
            key=f"live_{candidate.event_key}_{market}_{snapshot.get('scanned_at')}",
            bankroll_key="football_bet_finder_bankroll",
            save_source="Fußball Live",
            live_price=True,
        )

    # Live-Überblick: IMMER alle unterstützten Live-Spiele mit Modellwerten
    # zeigen — auch wenn kein Kandidat das Gate passiert. Volle Transparenz
    # über den aktuellen Spieltag statt leerer Fehlerseite.
    board_rows = []
    for item in analyses:
        probability, _signal = _live_market_signal(item, market)
        over_under = item.get("over_under") or {}
        board_rows.append(
            {
                "Spiel": f"{item.get('home_team', '?')} – {item.get('away_team', '?')}",
                "Liga": item.get("league", "?"),
                "Stand": item.get("score", "?"),
                "Min.": item.get("minute", "?"),
                "BTTS %": item.get("btts_prob"),
                "Ü 2,5 %": over_under.get("over_25_probability"),
                f"{market} %": probability,
                "Daten": item.get(
                    "live_data_quality", item.get("btts_confidence", "INSUFFICIENT")
                ),
            }
        )
    board_rows.sort(
        key=lambda row: (
            row[f"{market} %"] is None,
            -(row[f"{market} %"] or 0.0),
            -(row["Min."] if isinstance(row["Min."], int) else 0),
        )
    )
    with st.expander(
        f"Live-Überblick: alle {len(board_rows)} unterstützten Spiele",
        expanded=not opportunities,
    ):
        if board_rows:
            st.dataframe(board_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aktuell keine Live-Spiele in den unterstützten Ligen.")
        skipped = snapshot.get("skipped_matches", 0)
        if skipped:
            st.caption(
                f"{skipped} weitere Live-Spiele ohne gültigen Spielstand/Minute "
                "(z. B. gerade angelaufen oder Provider-Lücke)."
            )


def _red_card_entry(
    alert_system,
    card: dict,
    analyzer=None,
    api_key: Optional[str] = None,
) -> dict:
    match = card["match"]
    fixture_id = match["fixture"]["id"]
    home = match["teams"]["home"]
    away = match["teams"]["away"]
    home_goals = match.get("goals", {}).get("home")
    away_goals = match.get("goals", {}).get("away")
    entry = {
        "card": card,
        "home": home["name"],
        "away": away["name"],
        "score": f"{home_goals}-{away_goals}" if home_goals is not None and away_goals is not None else "n/a",
        "live_stats": None,
        "prediction": None,
        "prediction_minute": None,
        "error": None,
    }
    if home_goals is None or away_goals is None:
        entry["error"] = "Aktueller Spielstand fehlt"
        return entry

    if card.get("team_id") == home["id"]:
        red_side = "home"
        opponent = away["name"]
    elif card.get("team_id") == away["id"]:
        red_side = "away"
        opponent = home["name"]
    else:
        entry["error"] = "Team des Platzverweises ist nicht eindeutig"
        return entry

    entry["red_side"] = red_side
    entry["opponent"] = opponent
    snapshot_minute = alert_system.model_snapshot_minute(match)
    if snapshot_minute is None:
        entry["error"] = "Aktuelle Spielminute liegt außerhalb des unterstützten 0-93-Modells"
        return entry
    entry["prediction_minute"] = snapshot_minute
    entry["live_stats"] = alert_system.get_live_stats(fixture_id, home["id"], away["id"])
    if alert_system.predictor:
        prior_home, prior_away = _red_card_prematch_priors(
            home["id"],
            away["id"],
            match.get("league", {}).get("id"),
            _analyzer=analyzer,
            api_key=api_key,
        )
        prediction = alert_system.predictor.predict(
            minute=snapshot_minute,
            home_goals=home_goals,
            away_goals=away_goals,
            red_card_team=red_side,
            live_stats=entry["live_stats"],
            prior_home_goals=prior_home,
            prior_away_goals=prior_away,
            red_card_minute=card.get("minute"),
        )
        entry["prediction"] = asdict(prediction)
    return entry


@st.cache_data(ttl=3600, show_spinner=False)
def _red_card_prematch_priors(
    home_team_id: int,
    away_team_id: int,
    league_id,
    _analyzer=None,
    api_key: Optional[str] = None,
):
    """Prematch-Torerwartung fuer das Rotkarten-Kontextmodell (Staerke-Daempfung)."""
    if not isinstance(league_id, int):
        return None, None
    try:
        from api_football import APIFootball
        from ultra_live_scanner_v3 import UltraLiveScanner

        if _analyzer is None or not api_key:
            return None, None
        api = APIFootball(api_key)
        scanner = UltraLiveScanner(_analyzer, api)
        return scanner._get_prematch_goal_priors(home_team_id, away_team_id, league_id)
    except Exception:
        return None, None


@_serialized_analyzer(position=3)
def _scan_red_cards(
    api_key: str,
    league_ids: Optional[list[int]],
    scope_label: str,
    analyzer=None,
    progress_cb=None,
    streamlit_mode: bool = True,
) -> dict:
    import red_card_bot as red_card_module

    if getattr(red_card_module, "RED_CARD_BOT_VERSION", 0) < 2:
        red_card_module = importlib.reload(red_card_module)
    RedCardBotEnhanced = red_card_module.RedCardBotEnhanced

    scanned_at = datetime.now().astimezone().isoformat()
    if progress_cb:
        progress_cb(0.03, "Live-Spielplan wird geladen")
    # Hintergrund-tauglich: im Worker streamlit_mode=False, weil der Bot
    # sonst st.session_state ohne Session-Kontext anfasst.
    finder = RedCardBotEnhanced(
        api_key=api_key,
        streamlit_mode=streamlit_mode,
    )
    live_matches = finder.get_live_matches(league_ids)
    if progress_cb:
        progress_cb(
            0.15,
            f"{len(live_matches)} Live-Spiele werden geprüft",
        )
    cards = []
    total = max(len(live_matches), 1)
    for index, match in enumerate(live_matches):
        match_cards = finder.check_match_for_red_cards(match, include_seen=True)
        for card in match_cards:
            entry = _red_card_entry(
                finder,
                card,
                analyzer=analyzer,
                api_key=api_key,
            )
            entry["fixture_red_card_count"] = len(match_cards)
            cards.append(entry)
        if progress_cb:
            progress_cb(
                0.15 + 0.80 * (index + 1) / total,
                f"Spiel {index + 1}/{len(live_matches)} auf Platzverweise geprüft",
            )
    if progress_cb:
        progress_cb(1.0, f"Fertig: {len(cards)} Platzverweise gefunden")
    return {
        "version": RED_CARD_SNAPSHOT_VERSION,
        "scanned_at": scanned_at,
        "scope": scope_label,
        "live_matches": len(live_matches),
        "cards": cards,
        "errors": list(finder.errors),
    }


def _render_red_card_detail(entry: dict) -> None:
    card = entry["card"]
    st.subheader(f"{entry['home']} vs {entry['away']}")
    caption_parts = [
        entry["score"],
        f"Platzverweis Minute {card['minute']}",
        f"{card['player']} ({card['team']})",
    ]
    if entry.get("prediction_minute") is not None:
        caption_parts.append(f"Modell-Snapshot Minute {entry['prediction_minute']}")
    st.caption(" | ".join(caption_parts))
    if entry.get("error"):
        st.warning(entry["error"])
        return

    prediction = entry.get("prediction")
    if not prediction:
        st.warning("Für dieses Ereignis ist kein Wirkungsmodell verfügbar.")
        return

    next_goal = st.columns(3)
    next_goal[0].metric(
        f"{entry['opponent']} trifft",
        f"{prediction['next_goal_by_opponent'] * 100:.0f}%",
    )
    next_goal[1].metric(
        f"{card['team']} trifft",
        f"{prediction['next_goal_by_red_team'] * 100:.0f}%",
    )
    next_goal[2].metric("Kein Tor mehr", f"{prediction['no_more_goals'] * 100:.0f}%")

    outcomes = st.columns(3)
    outcomes[0].metric(
        f"{entry['opponent']} gewinnt",
        f"{prediction['opponent_wins'] * 100:.0f}%",
    )
    outcomes[1].metric("Unentschieden", f"{prediction['draw'] * 100:.0f}%")
    outcomes[2].metric(
        f"{card['team']} gewinnt",
        f"{prediction['red_team_wins'] * 100:.0f}%",
    )
    st.caption(
        f"Modell-Datenbasis: {prediction['data_quality']} | Erwartete Zeit bis zum nächsten Tor: "
        f"{prediction['expected_minutes_to_goal']:.0f} Minuten"
    )

    context = prediction.get("context_effects") or {}
    adjustments = context.get("adjustments") or []
    if adjustments:
        ratio = context.get("strength_ratio")
        ratio_label = (
            f" | Stärkeverhältnis 10-Mann-Team: {ratio:.2f}x"
            if isinstance(ratio, (int, float))
            else ""
        )
        st.caption(
            "Kontext-Adjustment: " + "; ".join(adjustments) + ratio_label
        )

    live_stats = entry.get("live_stats")
    if live_stats:
        stats = pd.DataFrame(
            [
                {
                    "Team": entry["home"],
                    "Ballbesitz %": live_stats.get("possession_home"),
                    "Schüsse aufs Tor": live_stats.get("shots_on_goal_home"),
                    "Angriffe": live_stats.get("total_attacks_home"),
                },
                {
                    "Team": entry["away"],
                    "Ballbesitz %": live_stats.get("possession_away"),
                    "Schüsse aufs Tor": live_stats.get("shots_on_goal_away"),
                    "Angriffe": live_stats.get("total_attacks_away"),
                },
            ]
        )
        st.dataframe(stats, use_container_width=True, hide_index=True)

    if prediction["too_late_for_signal"]:
        st.warning("Zu wenig Restzeit für ein belastbares Modellsignal.")
    elif prediction["model_signals"]:
        st.info("Modellsignale: " + " | ".join(prediction["model_signals"]))
    if prediction["risk_flags"]:
        st.warning("Risikofaktoren: " + " | ".join(prediction["risk_flags"]))


def _render_red_cards(analyzer) -> None:
    config = load_app_config(st)
    st.subheader("Platzverweis-Wetten")
    scope_options = ["Konfigurierte Ligen", "Weltweit"]
    if st.session_state.get("red_card_scope") not in scope_options:
        st.session_state["red_card_scope"] = scope_options[0]
    scan_scope = st.selectbox(
        "Suchumfang",
        scope_options,
        key="red_card_scope",
        help=(
            "Konfigurierte Ligen begrenzt Event-Abfragen. Weltweit prüft jedes vom Provider "
            "gelieferte Live-Spiel und benötigt entsprechend mehr API-Quota."
        ),
    )
    league_ids = (
        sorted(set(analyzer.engine.LEAGUES_CONFIG.values()))
        if scan_scope == "Konfigurierte Ligen"
        else None
    )
    if st.button(
        "Platzverweis-Wetten finden",
        type="primary",
        use_container_width=True,
        key="run_red_card_scan",
    ):
        if not config.api_football_key:
            st.error("Die Platzverweis-Suche ist vorübergehend nicht verfügbar.")
        elif scan_jobs.get_job(_job_key("red_cards"))["state"] == "running":
            st.info("Der Platzverweis-Scan läuft bereits im Hintergrund.")
        else:
            scan_jobs.start_job(
                _job_key("red_cards"),
                _scan_red_cards,
                args=(config.api_football_key, league_ids, scan_scope, analyzer),
                kwargs={"streamlit_mode": False},
                persist_name="red_cards",
                persist_fn=_persist_red_cards,
                persist_scope=_session_scope_id(),
            )

    job = scan_jobs.get_job(_job_key("red_cards"))
    if job["state"] == "running":
        scan_progress_fragment(
            _job_key("red_cards"),
            "Platzverweis-Scan",
        )
    elif job["state"] == "done":
        red_card_snapshot = job.get("result")
        st.session_state["red_card_snapshot"] = red_card_snapshot
        if isinstance(red_card_snapshot, dict) and red_card_snapshot.get("cards"):
            st.session_state.pop("live_football_snapshot", None)
            st.session_state["live_snapshot_invalidated_by_red_card"] = (
                red_card_snapshot.get("scanned_at")
            )
        scan_jobs.clear_job(_job_key("red_cards"))
    elif job["state"] == "error":
        st.error("Die Platzverweis-Suche konnte nicht abgeschlossen werden.")
        scan_jobs.clear_job(_job_key("red_cards"))

    snapshot = st.session_state.get("red_card_snapshot")
    if not snapshot:
        st.info("Noch keine Platzverweis-Suche.")
        return
    if snapshot.get("version") != RED_CARD_SNAPSHOT_VERSION:
        st.warning("Dieses Platzverweis-Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return
    if snapshot.get("scope") != scan_scope:
        st.warning("Der Suchumfang wurde seit dem Ergebnis geändert. Wetten neu suchen.")
        return

    st.caption(
        f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))} | "
        f"Umfang: {snapshot.get('scope')}"
    )
    if snapshot.get("errors"):
        st.warning(
            f"{len(snapshot['errors'])} Provider-Abfragen sind fehlgeschlagen; "
            "vorhandene Ereignisse bleiben sichtbar."
        )
    if not snapshot["cards"]:
        st.error("NICHT WETTEN: Kein aktueller Platzverweis mit prüfbarem Markt gefunden.")
        return

    snapshot_age = _snapshot_age_seconds(snapshot.get("scanned_at"))
    candidate_entries = [
        (
            red_card_candidate(
                entry,
                snapshot_age_seconds=snapshot_age,
                freemode=_freemode_enabled(),
            ),
            entry,
        )
        for entry in snapshot["cards"]
    ]
    candidate_entries.sort(
        key=lambda pair: (
            pair[0].model_ready,
            pair[0].risk_adjusted_probability or -1.0,
        ),
        reverse=True,
    )
    # Shadow-Logging: jede bewertete Platzverweis-Prediction still sichern
    # (Abrechnung nach Abpfiff via redcard_signal_log --settle im Cron).
    try:
        from redcard_signal_log import log_signal as _log_red_card_signal

        for _, _entry in candidate_entries:
            _log_red_card_signal(_entry)
    except Exception:
        pass
    candidate_entries = candidate_entries[:3]
    detail_key = "red_card_detail"
    detail_options = list(range(len(candidate_entries)))
    if st.session_state.get(detail_key) not in detail_options:
        st.session_state[detail_key] = detail_options[0]
    selected = st.selectbox(
        "Wettkandidat",
        detail_options,
        format_func=lambda index: (
            f"{'PREIS PRÜFEN' if candidate_entries[index][0].model_ready else 'NICHT WETTEN'} | "
            f"{candidate_entries[index][0].event_label} | {candidate_entries[index][0].selection}"
        ),
        key=detail_key,
    )
    candidate, _entry = candidate_entries[selected]
    render_price_decision(
        candidate,
        key=f"red_card_{candidate.event_key}_{snapshot.get('scanned_at')}",
        bankroll_key="football_bet_finder_bankroll",
        save_source="Fußball Live Platzverweis",
        live_price=True,
    )

def render_live(analyzer) -> None:
    if analyzer is None:
        st.error("Analyzer nicht bereit.")
        return
    market_label = st.selectbox(
        "Wettart",
        ["Noch ein Tor", "Team trifft noch", "Beide treffen", "Nach Platzverweis"],
        key="live_market_choice",
    )
    if market_label == "Nach Platzverweis":
        _render_red_cards(analyzer)
    else:
        market = "BTTS" if market_label == "Beide treffen" else market_label
        _render_live_football(analyzer, market)


def _render_model_validation(analyzer) -> None:
    if analyzer.model_trained:
        metrics = analyzer.model_metrics
        st.success("Das ML-Modell hat das chronologische Brier-Gate bestanden.")
        columns = st.columns(4)
        columns[0].metric("Training", metrics.get("training_matches", 0))
        columns[1].metric("Holdout", metrics.get("validation_matches", 0))
        columns[2].metric("Brier", _format_optional(metrics.get("brier_score"), 4))
        columns[3].metric(
            "Basis-Brier", _format_optional(metrics.get("baseline_brier_score"), 4)
        )

        importance = pd.DataFrame(
            {
                "Merkmal": ML_FEATURE_NAMES,
                "Bedeutung": analyzer.ml_model.feature_importances_,
            }
        ).sort_values("Bedeutung", ascending=True)
        figure = px.bar(
            importance,
            x="Bedeutung",
            y="Merkmal",
            orientation="h",
            color_discrete_sequence=["#1f8a70"],
        )
        figure.update_layout(height=390, margin=dict(l=0, r=12, t=12, b=30))
        st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    elif analyzer.model_metrics:
        st.warning(
            "ML ist inaktiv, weil es die chronologische Prävalenz-Baseline nicht geschlagen hat."
        )
    else:
        st.warning("ML ist wegen zu wenig leakage-freier Trainingsdaten inaktiv.")

    if ML_MODEL_PATH.exists():
        trained_at = datetime.fromtimestamp(ML_MODEL_PATH.stat().st_mtime).strftime(
            "%d.%m.%Y %H:%M"
        )
        st.caption(f"Modelldatei zuletzt geändert: {trained_at}")


def _run_data_refresh(analyzer, leagues: list[str], force: bool) -> int:
    progress = st.progress(
        0.01,
        text=f"1 % · {len(leagues)} Ligen werden vorbereitet",
    )
    status = st.empty()
    refreshed = 0
    total = max(len(leagues), 1)
    try:
        for index, league_code in enumerate(leagues):
            status.caption(f"Lade {league_code} ({index + 1}/{len(leagues)})")
            analyzer.engine.fetch_league_matches(league_code, force_refresh=force)
            refreshed += 1
            fraction = (index + 1) / total
            progress.progress(
                fraction,
                text=f"{int(round(fraction * 100))} % · "
                f"Liga {index + 1}/{len(leagues)} aktualisiert",
            )
    finally:
        status.empty()
        progress.empty()
    return refreshed


def _smart_refresh(analyzer, leagues: list[str]) -> int:
    connection = _get_db_connection("btts_data.db")
    refreshed = 0
    progress = st.progress(
        0.01,
        text=f"1 % · {len(leagues)} Ligen werden geprüft",
    )
    status = st.empty()
    try:
        cursor = connection.cursor()
        placeholder = "%s" if hasattr(connection, "info") else "?"
        total = max(len(leagues), 1)
        for index, league_code in enumerate(leagues):
            status.caption(f"Prüfe {league_code} ({index + 1}/{len(leagues)})")
            cursor.execute(
                f"SELECT MAX(date) FROM matches WHERE league_code = {placeholder}",
                (league_code,),
            )
            row = cursor.fetchone()
            last_date = row[0] if row else None
            is_current = False
            if last_date:
                try:
                    last_day = pd.to_datetime(last_date).date()
                    is_current = (datetime.now().date() - last_day).days <= 2
                except (TypeError, ValueError, OverflowError):
                    is_current = False
            if not is_current:
                analyzer.engine.fetch_league_matches(league_code, force_refresh=False)
                refreshed += 1
            fraction = (index + 1) / total
            progress.progress(
                fraction,
                text=f"{int(round(fraction * 100))} % · "
                f"Liga {index + 1}/{len(leagues)} geprüft",
            )
    finally:
        connection.close()
        status.empty()
        progress.empty()
    return refreshed


def _training_match_count() -> int:
    connection = _get_db_connection("btts_data.db")
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches WHERE btts IS NOT NULL")
        return int(cursor.fetchone()[0])
    finally:
        connection.close()


def _render_data_management(analyzer) -> None:
    available = list(analyzer.engine.LEAGUES_CONFIG)
    all_scope_label = f"Alle ({len(available)})"
    scope = _segmented(
        "Datenumfang",
        [all_scope_label, "Auswahl"],
        "data_league_scope_v2",
        all_scope_label,
    )
    if scope == all_scope_label:
        selected = available
    else:
        defaults = [code for code in ["BL1", "PL", "PD"] if code in available]
        selected = st.multiselect(
            "Ligen",
            available,
            default=defaults,
            format_func=_league_label_for_code,
            key="data_selected_leagues",
        )

    refresh_columns = st.columns(2)
    smart = refresh_columns[0].button(
        "Nur veraltete Daten laden",
        use_container_width=True,
        key="smart_data_refresh",
    )
    full = refresh_columns[1].button(
        (
            "Alle Ligen komplett neu laden"
            if scope == all_scope_label
            else "Auswahl komplett neu laden"
        ),
        use_container_width=True,
        key="full_data_refresh",
    )
    if (smart or full) and not selected:
        st.warning("Mindestens eine Liga auswählen.")
    elif smart:
        try:
            refreshed = _smart_refresh(analyzer, selected)
            if refreshed:
                st.success(f"{refreshed} Ligen aktualisiert.")
            else:
                st.info("Alle gewählten Ligen sind höchstens zwei Tage alt.")
        except Exception as exc:
            st.error(f"Smart-Update fehlgeschlagen: {exc}")
    elif full:
        try:
            refreshed = _run_data_refresh(analyzer, selected, force=True)
            st.success(f"{refreshed} Ligen vollständig geladen.")
        except Exception as exc:
            st.error(f"Vollständiges Update fehlgeschlagen: {exc}")

    st.divider()
    st.subheader("Training")
    training_scope = _segmented(
        "Trainingsumfang",
        ["Gewählte Ligen", "Alle Ligen"],
        "training_scope",
        "Gewählte Ligen",
    )
    training_leagues = selected if training_scope == "Gewählte Ligen" else available
    if st.button(
        "Modell neu trainieren",
        type="primary",
        use_container_width=True,
        key="retrain_model",
    ):
        if not training_leagues:
            st.warning("Mindestens eine Liga auswählen.")
            return
        try:
            _run_data_refresh(
                analyzer,
                training_leagues,
                force=training_scope == "Alle Ligen",
            )
            with st.spinner("Chronologische Modellvalidierung läuft..."):
                succeeded = analyzer.train_model()
            matches = _training_match_count()
            if succeeded:
                st.success(f"Modell-Gate bestanden; {matches} gespeicherte Matches.")
            else:
                st.warning(
                    "Kandidat hat das Brier-Gate nicht bestanden; das zuvor validierte Modell bleibt aktiv."
                )
        except Exception as exc:
            st.error(f"Training fehlgeschlagen: {exc}")


def render_model(analyzer) -> None:
    if analyzer is None:
        st.error("Analyzer nicht bereit. API-Schlüssel in Secrets, Environment oder config.ini prüfen.")
        return
    mode = _segmented(
        "Modellbereich",
        ["Validierung", "Daten"],
        "model_workspace",
        "Validierung",
    )
    if mode == "Validierung":
        _render_model_validation(analyzer)
    else:
        _render_data_management(analyzer)


def _multi_sport_scope_key(
    sport: str,
    detail_filter: Optional[str],
    search_date: Optional[date] = None,
    search_end_date: Optional[date] = None,
) -> str:
    start_date = search_date or zurich_today()
    end_date = search_end_date or start_date
    return (
        f"{sport}:{detail_filter or 'all'}:"
        f"{start_date.isoformat()}:{end_date.isoformat()}"
    )


def _validate_multi_sport_window(
    search_date: Optional[date],
    search_end_date: Optional[date],
) -> tuple[date, date]:
    start_date = search_date or zurich_today()
    end_date = search_end_date or start_date
    if (
        isinstance(start_date, datetime)
        or not isinstance(start_date, date)
        or isinstance(end_date, datetime)
        or not isinstance(end_date, date)
    ):
        raise ValueError("Suchzeitraum muss aus Datumswerten bestehen")
    if not 0 <= (end_date - start_date).days <= 14:
        raise ValueError("Suchzeitraum darf höchstens 14 Tage voraus reichen")
    return start_date, end_date


def _multi_sport_event_label(sport: str, item: dict) -> str:
    if item.get("status") == "upcoming":
        raw_start = item.get("start_time") or item.get("begin_at")
        try:
            start = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
            kickoff = start.astimezone().strftime("%d.%m., %H:%M")
        except (TypeError, ValueError):
            kickoff = "Termin offen"
        if sport == "Eishockey":
            matchup = (
                f"{item.get('away_team', 'AWAY')} @ "
                f"{item.get('home_team', 'HOME')}"
            )
        elif sport == "Tennis":
            matchup = (
                f"{item.get('player1', 'Spieler 1')} vs "
                f"{item.get('player2', 'Spieler 2')}"
            )
        else:
            home = item.get("home_team") or item.get("team1") or "Team 1"
            away = item.get("away_team") or item.get("team2") or "Team 2"
            matchup = f"{home} vs {away}"
        return f"{matchup} | {kickoff}"
    if sport == "Basketball":
        return (
            f"{item.get('home_team', 'HOME')} vs {item.get('away_team', 'AWAY')} | "
            f"Q{item.get('period', 'n/a')} | {item.get('home_score', 'n/a')}:"
            f"{item.get('away_score', 'n/a')}"
        )
    if sport == "Eishockey":
        return (
            f"{item.get('away_team', 'AWAY')} @ {item.get('home_team', 'HOME')} | "
            f"P{item.get('period', 'n/a')} | {item.get('away_score', 'n/a')}:"
            f"{item.get('home_score', 'n/a')}"
        )
    if sport == "Tennis":
        return (
            f"{item.get('player1', 'Spieler 1')} vs {item.get('player2', 'Spieler 2')} | "
            f"{item.get('player1_score', 'n/a')}:{item.get('player2_score', 'n/a')}"
        )
    if sport == "Cricket":
        score = (
            f"{item.get('current_runs')}/{item.get('current_wickets')}"
            if item.get("current_runs") is not None
            and item.get("current_wickets") is not None
            else "n/a"
        )
        return (
            f"{item.get('team1', 'Team 1')} vs {item.get('team2', 'Team 2')} | "
            f"{score} nach {item.get('current_over', 'n/a')} Over"
        )
    return (
        f"{item.get('team1', 'Team 1')} vs {item.get('team2', 'Team 2')} | "
        f"{item.get('team1_score', 'n/a')}:{item.get('team2_score', 'n/a')}"
    )


def _fetch_multi_sport_snapshot(
    sport: str,
    detail_filter: Optional[str] = None,
    search_date: Optional[date] = None,
    search_end_date: Optional[date] = None,
) -> dict:
    """Fetch upcoming events for one sport and an explicit date window."""
    if sport not in MULTI_SPORT_OPTIONS:
        raise ValueError(f"Unbekannte Sportart: {sport}")
    start_date, end_date = _validate_multi_sport_window(
        search_date,
        search_end_date,
    )
    valid_filters = MULTI_SPORT_FILTER_OPTIONS.get(sport)
    if valid_filters:
        detail_filter = detail_filter or valid_filters[0]
        if detail_filter not in valid_filters:
            raise ValueError(f"Ungültiger Filter für {sport}: {detail_filter}")
    elif detail_filter is not None:
        raise ValueError(f"{sport} unterstützt keinen Detailfilter")

    snapshot = {
        "version": 3,
        "scanned_at": datetime.now().astimezone().isoformat(),
        "sport": sport,
        "detail_filter": detail_filter,
        "search_date": start_date.isoformat(),
        "search_end_date": end_date.isoformat(),
        "items": [],
        "credentials_available": True,
        "errors": {},
    }

    if sport == "Basketball":
        try:
            from scanners.basketball_scanner import BasketballScanner

            scanner = BasketballScanner()
            provider_filter = {
                "Alle Ligen": "All",
                "NBA": "NBA",
                "EuroLeague": "Euroleague",
            }[detail_filter]
            for game in scanner.get_upcoming_games(
                provider_filter,
                start_date,
                end_date,
            ):
                snapshot["items"].append(dict(game))
            for provider, message in scanner.errors.items():
                snapshot["errors"][provider] = message
        except Exception:
            snapshot["errors"]["Basketball"] = "Provider nicht verfügbar"
        return snapshot

    if sport == "Eishockey":
        try:
            from scanners.basketball_scanner import BasketballScanner

            scanner = BasketballScanner()
            snapshot["items"] = scanner.get_upcoming_nhl_games(
                start_date,
                end_date,
            )
            for provider, message in scanner.errors.items():
                snapshot["errors"][provider] = message
        except Exception:
            snapshot["errors"]["NHL"] = "Provider nicht verfügbar"
        return snapshot

    if sport == "Tennis":
        try:
            from scripts.tennis_daily import fetch_fixtures

            total_days = (end_date - start_date).days + 1
            for offset in range(total_days):
                target_date = start_date + timedelta(days=offset)
                for fixture in fetch_fixtures(target_date.isoformat()):
                    snapshot["items"].append(
                        {
                            "match_id": fixture.get("provider_event_id"),
                            "player1": fixture.get("player_a"),
                            "player2": fixture.get("player_b"),
                            "tournament": fixture.get("tournament"),
                            "status": "upcoming",
                            "start_time": fixture.get("scheduled_start_utc"),
                            "source": fixture.get("fixture_source"),
                        }
                    )
        except Exception:
            snapshot["errors"]["Tennis"] = "Provider nicht verfügbar"
        return snapshot

    if sport == "Cricket":
        try:
            from scanners.cricket_scanner import CricketScanner

            scanner = CricketScanner()
            snapshot["items"] = scanner.get_upcoming_matches(
                start_date,
                end_date,
            )
            if scanner.last_error:
                snapshot["errors"]["Cricket"] = scanner.last_error
        except Exception:
            snapshot["errors"]["Cricket"] = "Provider nicht verfügbar"
        return snapshot

    try:
        from scanners.esports_scanner import EsportsScanner

        scanner = EsportsScanner()
        snapshot["credentials_available"] = bool(scanner.api_key)
        if scanner.api_key:
            provider_filter = "all" if detail_filter == "Alle Spiele" else detail_filter.lower()
            for match in scanner.get_upcoming_matches(
                provider_filter,
                start_date,
                end_date,
            ):
                snapshot["items"].append(dict(match))
            for provider, message in scanner.errors.items():
                snapshot["errors"][provider] = message
    except Exception:
        snapshot["errors"]["PandaScore"] = "Provider nicht verfügbar"
    return snapshot


def _run_multi_sport_worker(
    sport: str,
    detail_filter: Optional[str] = None,
    search_date: Optional[date] = None,
    search_end_date: Optional[date] = None,
    progress_cb=None,
) -> dict:
    """Hintergrund-Worker für den Multi-Sport-Scan (thread-sicher, kein st.*)."""
    if progress_cb:
        progress_cb(0.05, "wird vorbereitet")
        progress_cb(0.25, "Provider wird abgefragt")
    start_date, end_date = _validate_multi_sport_window(
        search_date,
        search_end_date,
    )
    snapshot = _fetch_multi_sport_snapshot(
        sport,
        detail_filter,
        start_date,
        end_date,
    )
    if progress_cb:
        progress_cb(
            0.90,
            f"{len(snapshot.get('items') or [])} Ereignisse werden ausgewertet",
        )
        progress_cb(1.0, "Fertig")
    return {
        "scope_key": _multi_sport_scope_key(
            sport,
            detail_filter,
            start_date,
            end_date,
        ),
        "snapshot": snapshot,
    }


def _render_esports_shadow_status() -> None:
    """Compact proof line: shadow-log calibration for e-sport candidates."""
    try:
        from esports_shadow import DEFAULT_DB_PATH, EsportsShadowLog

        if not DEFAULT_DB_PATH.exists():
            return
        log = EsportsShadowLog()
        summary = log.summary()
        release = log.release_status()
    except Exception:
        return
    predictions = summary.get("predictions") or 0
    settled = summary.get("settled") or 0
    if not predictions:
        return
    if settled:
        st.caption(
            f"E-Sport Shadow-Protokoll (nur Pre-Match): {predictions} Tipps protokolliert | "
            f"{settled}/{release['required']} abgerechnet | Treffer {summary['hit_rate']} % bei Ø "
            f"risikoadjustiert {summary['avg_risk_adjusted_probability']} % | "
            f"{summary['open']} offen | "
            f"{'Freigabe aktiv' if release['ready'] else 'Lernphase, noch keine Wettfreigabe'}"
        )
    else:
        st.caption(
            f"E-Sport Shadow-Protokoll: {predictions} Tipps protokolliert, "
            "Abrechnung nach Spielende."
        )


def _multi_sport_release_blockers(
    sport: str,
    item: dict,
    esports_release: Optional[dict] = None,
) -> tuple[str, ...]:
    if sport == "Basketball":
        return (
            "Das Live-Totalmodell besitzt noch keinen unabhängigen "
            "Out-of-sample- und Closing-Line-Nachweis.",
        )
    if sport == "Eishockey":
        return (
            "Das NHL-Totalmodell besitzt noch keinen unabhängigen "
            "Out-of-sample- und Goalie-spezifischen Nachweis.",
        )
    if sport != "E-Sport":
        return ()
    if item.get("status") != "upcoming":
        return (
            "Das E-Sport-Shadow-Gate validiert nur Pre-Match bei Serienstand 0:0, "
            "nicht score-konditionierte Live-Wetten.",
        )
    if esports_release is None:
        try:
            from esports_shadow import EsportsShadowLog

            esports_release = EsportsShadowLog().release_status()
        except Exception:
            esports_release = {"ready": False, "settled": 0, "required": 300}
    if (
        esports_release.get("ready") is True
        and esports_release.get("price_evidence_ready") is True
    ):
        return ()
    if (
        esports_release.get("calibration_ready") is True
        and esports_release.get("price_evidence_ready") is not True
    ):
        return (
            "E-Sport ist kalibrierungsreif, aber timestamped Opening-/Closing-"
            "Quoten, CLV und ein positives Rendite-Konfidenzintervall fehlen.",
        )
    return (
        "E-Sport ist noch in der ehrlichen Shadow-Anlaufphase: "
        f"{int(esports_release.get('settled') or 0)}/"
        f"{int(esports_release.get('required') or 300)} Prematch-Fälle abgerechnet.",
    )


def render_multi_sport(
    preselected_sport: Optional[str] = None,
    search_date: Optional[date] = None,
    search_end_date: Optional[date] = None,
) -> None:
    if preselected_sport is not None and preselected_sport not in MULTI_SPORT_OPTIONS:
        raise ValueError(f"Unbekannte Sportart: {preselected_sport}")
    start_date, end_date = _validate_multi_sport_window(
        search_date,
        search_end_date,
    )
    sport = preselected_sport or st.selectbox(
        "Sportart",
        list(MULTI_SPORT_OPTIONS),
        key="multi_sport_selected_sport",
    )
    job_key = _job_key(_multi_sport_job_name(sport))
    sport_key = _multi_sport_job_name(sport).removeprefix("multi_sport_")
    detail_filter = None
    filter_options = MULTI_SPORT_FILTER_OPTIONS.get(sport)
    if filter_options:
        detail_filter = st.selectbox(
            "Liga" if sport == "Basketball" else "Spiel",
            list(filter_options),
            key=f"multi_sport_filter_{sport_key}",
        )
    snapshots = st.session_state.get("multi_sport_snapshots")
    if not isinstance(snapshots, dict):
        snapshots = {}
        st.session_state["multi_sport_snapshots"] = snapshots
    scope_key = _multi_sport_scope_key(
        sport,
        detail_filter,
        start_date,
        end_date,
    )
    if st.button(
        f"{sport}-Suche starten",
        type="primary",
        use_container_width=True,
        key=f"run_multi_sport_{sport_key}",
    ):
        if scan_jobs.get_job(job_key)["state"] == "running":
            st.info(f"Die {sport}-Suche läuft bereits im Hintergrund.")
        else:
            scan_jobs.start_job(
                job_key,
                _run_multi_sport_worker,
                args=(sport, detail_filter, start_date, end_date),
            )

    job = scan_jobs.get_job(job_key)
    if job["state"] == "running":
        scan_progress_fragment(
            job_key,
            f"{sport}-Suche",
        )
    elif job["state"] == "done":
        result = job.get("result") or {}
        result_scope = result.get("scope_key")
        result_snapshot = result.get("snapshot")
        if result_scope and isinstance(result_snapshot, dict):
            snapshots[result_scope] = result_snapshot
        scan_jobs.clear_job(job_key)
    elif job["state"] == "error":
        st.error(f"Die {sport}-Suche konnte nicht abgeschlossen werden.")
        scan_jobs.clear_job(job_key)

    snapshot = snapshots.get(scope_key)
    if not snapshot:
        st.info(f"Noch keine {sport}-Suche.")
        return

    snapshot_items = snapshot.get("items")
    snapshot_items = snapshot_items if isinstance(snapshot_items, list) else []
    item_count = len(snapshot_items)
    events_label = f"{item_count} anstehende Ereignisse"
    caption_parts = [
        f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))}",
        f"Zeitraum: {start_date:%d.%m.%Y} bis {end_date:%d.%m.%Y}",
        events_label,
    ]
    if detail_filter:
        caption_parts.append(f"Filter: {detail_filter}")
    st.caption(" | ".join(caption_parts))

    snapshot_age = _snapshot_age_seconds(snapshot.get("scanned_at"))
    missing_esports_key = sport == "E-Sport" and not snapshot.get(
        "credentials_available"
    )
    if missing_esports_key:
        st.info("Die E-Sport-Suche ist vorübergehend nicht verfügbar.")

    if snapshot.get("errors"):
        st.caption(f"Ein Teil der {sport}-Daten ist derzeit nicht verfügbar.")

    if not snapshot_items:
        if not missing_esports_key:
            st.info(f"Keine anstehenden {sport}-Ereignisse im Zeitraum.")
        return

    selected_index = st.selectbox(
        "Spiel",
        list(range(len(snapshot_items))),
        format_func=lambda index: _multi_sport_event_label(sport, snapshot_items[index]),
        key=f"multi_sport_event_{scope_key}",
    )
    selected_item = snapshot_items[selected_index]
    is_upcoming = (
        isinstance(selected_item, dict) and selected_item.get("status") == "upcoming"
    )
    max_snapshot_age = 3600 if is_upcoming else 180
    if snapshot_age is None or snapshot_age < -30 or snapshot_age > max_snapshot_age:
        if is_upcoming:
            st.error(
                "NICHT WETTEN: Pre-Match-Datenstand ist ungültig oder älter als eine Stunde."
            )
        else:
            st.error("NICHT WETTEN: Live-Snapshot ist ungültig oder älter als drei Minuten.")
        return
    if is_upcoming:
        st.caption(
            "Pre-Match-Bewertung aus Team-Historien (Serienstand 0:0). "
            "Lineups, Marktlinie und tatsächliche Quote vor Abgabe prüfen."
        )
    snapshot_token = str(snapshot.get("scanned_at") or "snapshot").replace(":", "_")
    line_value = None
    if sport in {"Basketball", "Eishockey"} and not is_upcoming:
        line_label = (
            "Buchmacher-Gesamtpunkte-Linie (x,5)"
            if sport == "Basketball"
            else "Buchmacher-Gesamttore-Linie (x,5)"
        )
        raw_line = st.text_input(
            line_label,
            placeholder="z. B. 221,5" if sport == "Basketball" else "z. B. 5,5",
            key=f"multi_sport_line_{scope_key}_{selected_index}_{snapshot_token}",
        ).strip()
        if not raw_line:
            st.info("Für diesen Markt zuerst die exakte angebotene Linie eintragen.")
            return
        try:
            line_value = float(raw_line.replace(",", "."))
        except ValueError:
            line_value = raw_line
        # A mistyped line changes the model probability itself, so the line
        # needs the same explicit bookmaker cross-check as the price.
        line_confirmed = st.checkbox(
            f"Linie {raw_line} wurde unmittelbar beim Buchmacher abgeglichen",
            value=False,
            key=f"multi_sport_line_confirmed_{scope_key}_{selected_index}_{snapshot_token}",
        )
        if not line_confirmed:
            st.info("Bitte die angebotene Linie abgleichen und bestätigen.")
            return

    candidate = build_candidate(
        sport,
        selected_item,
        market_line=line_value,
    )
    release_blockers = _multi_sport_release_blockers(sport, selected_item)
    if release_blockers:
        candidate = replace(
            candidate,
            blockers=tuple(dict.fromkeys(candidate.blockers + release_blockers)),
        )
    elif sport == "E-Sport":
        candidate = replace(candidate, evidence_stage=EVIDENCE_RELEASED)

    if candidate.expected_total is not None:
        st.caption(f"Erwartete Gesamtzahl: {candidate.expected_total:.2f}")
    render_price_decision(
        candidate,
        key=f"multi_sport_{scope_key}_{selected_index}_{snapshot_token}",
        bankroll_key=f"multi_sport_bankroll_{sport_key}",
        save_source=f"{sport} Wettfinder",
    )


def _automated_signal_candidate(signal: ModelSignal) -> RecommendationCandidate:
    probability = signal.probability * 100.0
    haircut = signal.probability_haircut * 100.0
    adjusted = probability - haircut
    return RecommendationCandidate(
        event_key=signal.key,
        sport=signal.sport or "Sport",
        event_label=signal.event_label or signal.label,
        market=signal.market or "Auswahl",
        selection=signal.selection or signal.label,
        line=None,
        model_probability=round(probability, 2),
        risk_adjusted_probability=round(adjusted, 2),
        probability_haircut=round(haircut, 2),
        fair_odds=round(100.0 / probability, 3),
        minimum_odds=signal.minimum_odds,
        model_name=signal.detail,
        expected_total=None,
        evidence=(
            signal.detail,
            (
                "Automatischer Marktvergleich liegt vor."
                if signal.reference_quote is not None
                else "Modellprognose und Wettpreis werden getrennt bewertet."
            ),
        ),
        blockers=(
            ()
            if signal.minimum_odds is not None
            else ("Keine belastbare Mindestquote berechenbar.",)
        ),
        evidence_stage=signal.evidence_stage,
    )


def _automatic_target_label(value: Optional[str]) -> str:
    try:
        target = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return "Spieltag unbekannt"
    today = zurich_today()
    if target == today:
        return "Heute"
    if target == today + timedelta(days=1):
        return "Morgen"
    return target.strftime("%d.%m.%Y")


_AUTOMATIC_PRICE_STATUS_LABELS = {
    "TOO_LOW": "unter der Mindestquote",
    "UNAVAILABLE": "ohne exakt passende Marktquote",
    "BORDERLINE": "nur bei einzelnen Anbietern ausreichend",
    "THIN": "mit zu wenigen Vergleichsanbietern",
    "STALE": "mit veraltetem Marktstand",
    "INVALID_MINIMUM": "mit ungültiger Mindestquote",
    "PLAYABLE": "preislich spielbar",
}


def _automatic_price_summary(status: AutomatedWettfinderStatus) -> Optional[str]:
    """Format internal price diagnostics; never render this in consumer UI."""
    counts = dict(status.price_status_counts)
    parts = [
        f"{counts[code]} {_AUTOMATIC_PRICE_STATUS_LABELS[code]}"
        for code in _AUTOMATIC_PRICE_STATUS_LABELS
        if counts.get(code)
    ]
    if parts:
        checked = status.price_checked_count or sum(counts.values())
        return f"Preisprüfung: {checked} Modellmärkte geprüft · " + " · ".join(parts)
    if status.approved_candidates > 0:
        return (
            "Preisprüfung: Modellkandidaten sind vorhanden, aber aktuell liegt "
            "keine verwendbare exakte Marktquote vor."
        )
    return None


def _automatic_consumer_summary(
    status: AutomatedWettfinderStatus,
) -> tuple[str, str, bool]:
    """Describe the automatic result without claiming more than it verified."""

    found = status.fixtures_found
    modeled = status.fixtures_modeled
    approved = status.approved_candidates
    base_fixtures = status.base_fixture_count
    verified = status.context_verified_fixtures
    pending = status.context_unchecked_fixtures + status.deferred_context_fixtures
    unmodeled = max(found - modeled, 0)
    run_complete = status.football_status == "completed" and getattr(
        status,
        "operational_error_count",
        0,
    ) == 0
    evidence_parts = [
        f"{found} {'Spiel' if found == 1 else 'Spiele'} gefunden",
        f"{modeled} modelliert",
    ]
    if base_fixtures > 0:
        evidence_parts.extend(
            (
                f"{base_fixtures} {'Spiel' if base_fixtures == 1 else 'Spiele'} "
                "in der engeren Auswahl",
                f"{verified} vollständig geprüft",
            )
        )
    if run_complete:
        evidence_parts.append(
            f"{approved} "
            f"{'vollständig bestätigte Auswahl' if approved == 1 else 'vollständig bestätigte Auswahlen'}"
        )
    else:
        evidence_parts.append("Ergebnis nicht vollständig belegt")
    if run_complete and approved > 0:
        evidence_parts.append(
            f"{status.price_checked_count} "
            f"{'Preisprüfung' if status.price_checked_count == 1 else 'Preisprüfungen'}"
        )
    evidence = " · ".join(evidence_parts)

    if not run_complete:
        return (
            evidence,
            "Der automatische Lauf wurde nicht vollständig abgeschlossen. "
            "BetBoy gibt deshalb kein Qualitätsurteil ab.",
            True,
        )
    if found <= 0:
        return (
            evidence,
            "Für den gewählten Spieltag wurden keine anstehenden Fußballspiele "
            "gefunden.",
            False,
        )
    if modeled <= 0:
        return (
            evidence,
            "Die gefundenen Spiele konnten nicht belastbar modelliert werden. "
            "BetBoy gibt deshalb kein Qualitätsurteil ab.",
            True,
        )
    if approved > 0:
        if status.price_checked_count > 0:
            price_message = (
                f"Bei {status.price_checked_count} Preisprüfungen war keine "
                "aktuelle Vergleichsquote spielbar."
            )
        else:
            price_message = (
                "Für die bestätigten Auswahlen lag keine prüfbare aktuelle "
                "Vergleichsquote vor."
            )
        coverage_notes = []
        if unmodeled > 0:
            coverage_notes.append(
                f"{unmodeled} weitere gefundene "
                f"{'Spiel konnte' if unmodeled == 1 else 'Spiele konnten'} "
                "nicht modelliert werden."
            )
        if status.context_data_incomplete_fixtures > 0:
            coverage_notes.append(
                "Weitere Spiele konnten wegen unvollständiger Daten nicht "
                "abschließend geprüft werden."
            )
        if pending > 0:
            pending_label = (
                "1 weiteres Spiel"
                if pending == 1
                else f"{pending} weitere Spiele"
            )
            coverage_notes.append(
                f"Für {pending_label} "
                f"{'steht' if pending == 1 else 'stehen'} die vollständige "
                "Prüfung noch aus."
            )
        elif status.base_candidates > 0 and (
            not status.context_accounting_available
            or not status.context_scope_complete
        ):
            coverage_notes.append(
                "Der vollständige Prüfumfang dieses Laufs ist nicht belegt."
            )
        return (
            evidence,
            " ".join(
                [price_message, "Die Prognose bleibt davon unberührt."]
                + coverage_notes
            ),
            bool(coverage_notes),
        )
    if status.context_data_incomplete_fixtures > 0:
        return (
            evidence,
            "Ein Teil der benötigten Daten war nicht vollständig verfügbar. "
            "Deshalb wurde kein Tipp freigegeben; das ist keine negative "
            "Aussage über den möglichen Spielausgang.",
            True,
        )
    if pending > 0:
        pending_label = (
            "1 weiteres Spiel"
            if pending == 1
            else f"{pending} weitere Spiele"
        )
        return (
            evidence,
            f"Unter den {verified} vollständig geprüften Spielen wurde keine "
            f"Auswahl bestätigt. Für {pending_label} "
            f"{'steht' if pending == 1 else 'stehen'} die vollständige "
            "Prüfung noch aus. Die Quote war nicht der Ablehnungsgrund.",
            True,
        )
    if status.base_candidates > 0 and (
        not getattr(status, "context_accounting_available", False)
        or not status.context_scope_complete
    ):
        return (
            evidence,
            "Der Umfang der vollständigen Kontextprüfung ist für diesen Lauf "
            "nicht vollständig belegt. Deshalb gibt BetBoy kein abschließendes "
            "Qualitätsurteil ab.",
            True,
        )
    if status.base_candidates <= 0:
        unmodeled_note = (
            f" {unmodeled} weitere gefundene "
            f"{'Spiel konnte' if unmodeled == 1 else 'Spiele konnten'} nicht "
            "modelliert werden."
            if unmodeled > 0
            else ""
        )
        return (
            evidence,
            "Kein Spiel kam in die engere Auswahl. "
            "Eine Quote wurde deshalb noch nicht geprüft."
            + unmodeled_note,
            unmodeled > 0,
        )
    return (
        evidence,
        f"Unter den {verified} vollständig geprüften Spielen wurde keine Auswahl "
        "bestätigt. Die Quote war nicht der Ablehnungsgrund.",
        False,
    )


def _is_football_sport(value: object) -> bool:
    """Accept the canonical and legacy spelling used by persisted signals."""

    normalized = str(value or "").strip().casefold().replace("ß", "ss")
    return normalized == "fussball"


def _partition_automated_signals(signals: list) -> tuple[list, list]:
    football = [signal for signal in signals if _is_football_sport(signal.sport)]
    other = [signal for signal in signals if not _is_football_sport(signal.sport)]
    return football, other


def _automatic_partial_scope_notice(
    status: AutomatedWettfinderStatus,
) -> Optional[str]:
    pending = (
        status.context_data_incomplete_fixtures
        + status.context_unchecked_fixtures
        + status.deferred_context_fixtures
    )
    unmodeled = max(status.fixtures_found - status.fixtures_modeled, 0)
    if (
        unmodeled <= 0
        and pending <= 0
        and status.context_accounting_available
        and status.context_scope_complete
    ):
        return None
    details = []
    if unmodeled > 0:
        details.append(
            f"{unmodeled} weitere "
            f"{'Spiel konnte' if unmodeled == 1 else 'Spiele konnten'} nicht "
            "modelliert werden"
        )
    if pending > 0:
        pending_label = (
            "1 weiteres Spiel" if pending == 1 else f"{pending} weitere Spiele"
        )
        details.append(
            f"für {pending_label} ist die vollständige "
            "Prüfung nicht belegt"
        )
    if not status.context_accounting_available:
        details.append("der vollständige Prüfumfang ist nicht belegt")
    suffix = f" ({'; '.join(details)})." if details else "."
    return (
        "Die angezeigten Auswahlen stammen aus vollständig geprüften Spielen; "
        "der gesamte Tagesumfang ist noch nicht vollständig geprüft" + suffix
    )


def _render_automated_daily_selection() -> None:
    status = automated_wettfinder_status()
    signals = automated_wettfinder_signals()
    forecasts = automated_wettfinder_forecasts()
    if status is None:
        with st.expander("Automatischer Check", expanded=False):
            st.caption("Separater planmäßiger Lauf, unabhängig von der Suche darunter.")
            st.info("Aktuell ist noch kein Ergebnis verfügbar.")
        return

    target_label = _automatic_target_label(status.target_search_date)
    football_signals, other_signals = _partition_automated_signals(signals)
    football_forecasts, other_forecasts = _partition_automated_signals(forecasts)
    priced_keys = {signal.key for signal in signals}
    football_forecasts = [
        signal for signal in football_forecasts if signal.key not in priced_keys
    ]
    other_forecasts = [
        signal for signal in other_forecasts if signal.key not in priced_keys
    ]
    if status.football_status != "completed":
        football_signals = []
    with st.expander(
        f"Automatischer Fußball-Check · {target_label}",
        expanded=bool(football_signals or football_forecasts),
    ):
        st.caption("Separater planmäßiger Lauf, unabhängig von der Suche darunter.")
        time_parts = [f"Ergebnisstand: {_format_stand(status.generated_at)}"]
        if status.last_discovery_at is not None:
            time_parts.append(
                f"Fußball geprüft: {_format_stand(status.last_discovery_at)}"
            )
        st.caption(" · ".join(time_parts))

        if not football_signals and not football_forecasts:
            evidence, message, incomplete = _automatic_consumer_summary(status)
            st.caption(evidence)
            if incomplete:
                st.warning(message)
            else:
                st.info(message)
        else:
            partial_scope_notice = _automatic_partial_scope_notice(status)
            if partial_scope_notice:
                st.warning(partial_scope_notice)
            if status.football_status != "completed" or status.operational_error_count:
                st.warning(
                    "Der gesamte Tageslauf war nicht vollständig. Angezeigt werden "
                    "nur Auswahlen aus Spielen mit eigener vollständiger Prüfung."
                )
            if football_signals:
                st.success(
                    f"{len(football_signals)} automatisch berechnete "
                    f"Wett-Auswahl{'en' if len(football_signals) != 1 else ''} "
                    "mit passender Vergleichsquote."
                )
            elif football_forecasts:
                st.info(
                    f"{len(football_forecasts)} automatisch berechnete "
                    f"Wett-Auswahl{'en' if len(football_forecasts) != 1 else ''}. "
                    "Eine fehlende oder zu niedrige Quote ändert die Prognose nicht."
                )
            displayed = [*football_signals, *football_forecasts]
            for index, selected in enumerate(displayed, start=1):
                st.markdown(f"### Berechnete Auswahl {index}")
                render_price_decision(
                    _automated_signal_candidate(selected),
                    key=f"automated_{selected.key}",
                    bankroll_key="automated_finder_bankroll",
                    save_source="Automatischer Wettfinder",
                    reference_quote=selected.reference_quote,
                    allow_manual_check=True,
                )
                if index < len(displayed):
                    st.divider()

    other_displayed = [*other_signals, *other_forecasts]
    if other_displayed:
        with st.expander("Automatische Auswahlen · weitere Sportarten", expanded=True):
            st.caption(
                "Diese Auswahlen stammen aus den getrennten Tennis- und "
                "E-Sport-Modellen. Preis und Prognose werden separat bewertet."
            )
            for index, selected in enumerate(other_displayed, start=1):
                st.markdown(f"### Berechnete Auswahl {index}")
                render_price_decision(
                    _automated_signal_candidate(selected),
                    key=f"automated_other_{selected.key}",
                    bankroll_key="automated_finder_bankroll",
                    save_source="Automatischer Wettfinder",
                    reference_quote=selected.reference_quote,
                    allow_manual_check=True,
                )
                if index < len(other_displayed):
                    st.divider()


def _render_selected_finder(
    sport: str,
    search_date: date,
    search_end_date: date,
    football_market_scope: str,
) -> None:
    if sport == "Fußball":
        create_alternative_markets_tab_extended(
            market_scope=football_market_scope,
            search_date=search_date,
            search_end_date=search_end_date,
            embedded=True,
        )
        return
    if sport == "Tennis":
        from tennis_tab import render_tennis_finder

        render_tennis_finder(search_date, search_end_date)
        return
    render_multi_sport(
        preselected_sport=sport,
        search_date=search_date,
        search_end_date=search_end_date,
    )


def render_wettfinder() -> None:
    """One sport-first entry point for every pre-match finder."""
    _render_automated_daily_selection()
    st.divider()
    st.subheader("Eigene Suche")
    controls = st.columns(3)
    with controls[0]:
        sport = st.selectbox(
            "Sport",
            list(FINDER_SPORT_OPTIONS),
            index=1,
            key="finder_sport",
            format_func=lambda value: (
                "Alle Bereiche (separate Suchen)" if value == "Alle" else value
            ),
        )

    with controls[1]:
        horizon_label = st.selectbox(
            "Zeitraum",
            list(SEARCH_HORIZONS),
            index=2,
            key="finder_search_horizon",
        )
    search_date = zurich_today()
    search_end_date = search_date + timedelta(
        days=SEARCH_HORIZONS[horizon_label]
    )
    selected_sports = _finder_sports_for_selection(sport)

    football_market_scope = "Beste Märkte"
    if "Fußball" in selected_sports:
        with controls[2]:
            football_market_scope = st.selectbox(
                "Wettart" if sport == "Fußball" else "Fußball-Wettart",
                list(_alternative_markets.FOOTBALL_MARKET_SCOPES),
                key="finder_football_market",
            )

    if sport == "Alle":
        st.caption(
            "Alle zeigt getrennte Sportbereiche. Jede Suche wird im jeweiligen "
            "Tab separat gestartet; das Ergebnis gilt nur für diesen Sport."
        )
        sport_tabs = st.tabs(list(selected_sports))
        for sport_tab, selected_sport in zip(sport_tabs, selected_sports):
            with sport_tab:
                _render_selected_finder(
                    selected_sport,
                    search_date,
                    search_end_date,
                    football_market_scope,
                )
        return

    _render_selected_finder(
        sport,
        search_date,
        search_end_date,
        football_market_scope,
    )


def _render_system_status(analyzer) -> None:
    st.subheader("Status")
    if analyzer and analyzer.model_trained:
        model_state = "Validiertes ML aktiv"
        model_class = "bb-dot"
    elif analyzer:
        model_state = "Statistikmodell aktiv; ML gesperrt"
        model_class = "bb-dot warn"
    else:
        model_state = "Analyzer nicht bereit"
        model_class = "bb-dot error"
    st.markdown(
        f'<div class="bb-status"><span class="{model_class}"></span>{model_state}</div>',
        unsafe_allow_html=True,
    )

    config = load_app_config(st)
    if config.api_football_key:
        api_health = _api_football_health(config.api_football_key)
        api_class = "bb-dot" if api_health["state"] == "active" else "bb-dot error"
        api_state = api_health["label"]
    else:
        api_health = {"state": "missing", "detail": ""}
        api_class = "bb-dot warn"
        api_state = "Live-API fehlt"
    st.markdown(
        f'<div class="bb-status"><span class="{api_class}"></span>{api_state}</div>',
        unsafe_allow_html=True,
    )
    stats_stand = _stats_freshness()
    if stats_stand is not None:
        st.caption(f"Datenstand: {_format_stand(stats_stand)}")
    if api_health.get("detail") and api_health["state"] in {"suspended", "error"}:
        st.caption(api_health["detail"])


def render_settings(analyzer) -> None:
    section = st.selectbox(
        "Bereich",
        ["Modellvalidierung", "Datenbestand", "15K Konto"],
        key="settings_section",
    )
    if section == "15K Konto":
        from challenge_15k import render_challenge_account

        render_challenge_account()
        return
    if analyzer is None:
        st.error("Analyzer nicht bereit. API-Schlüssel in Secrets oder Environment prüfen.")
        return
    if section == "Modellvalidierung":
        _render_model_validation(analyzer)
    else:
        _render_system_status(analyzer)
        _render_data_management(analyzer)


def _render_mobile_nav(workspace: str) -> None:
    """Bottom navigation for small screens; hidden on desktop via CSS.

    The sidebar radio stays the single state source: the click callback runs
    before the next script run and only sets the same ``workspace`` key.
    """
    short_labels = {
        "Wettfinder": ("Tipps", ":material/search:"),
        "Live": ("Live", ":material/bolt:"),
        "15K": ("15K", ":material/emoji_events:"),
        "Meine Tipps": ("Meine", ":material/bookmarks:"),
    }

    def _go(page: str) -> None:
        st.session_state["workspace"] = page
        st.session_state["settings_open"] = False

    with st.container(key="bb_bottomnav"):
        columns = st.columns(len(short_labels), gap="small")
        for column, (page, (label, icon)) in zip(columns, short_labels.items()):
            column.button(
                label,
                key=f"bb_bottomnav_{page}",
                icon=icon,
                type="primary" if page == workspace else "secondary",
                use_container_width=True,
                on_click=_go,
                args=(page,),
            )


def main() -> None:
    st.set_page_config(
        page_title="BetBoy",
        page_icon=":material/sports_soccer:",
        layout="wide",
        initial_sidebar_state="auto",
    )
    _apply_app_styles()
    ensure_account_scope(st)
    session_scope_id = _session_scope_id()

    try:
        analyzer = get_analyzer(
            _REQUIRED_ANALYZER_MODULE_VERSION,
            session_scope_id,
        )
        st.session_state.pop("analyzer_error", None)
    except Exception as exc:
        analyzer = None
        st.session_state["analyzer_error"] = str(exc)

    workspace = _render_sidebar(analyzer)
    title, caption = PAGE_INFO[workspace]
    st.markdown(f'<div class="bb-context">BetBoy / {workspace}</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(caption)

    if st.session_state.get("analyzer_error"):
        st.error("Die App konnte nicht vollständig gestartet werden.")

    if workspace == "Wettfinder":
        render_wettfinder()
    elif workspace == "Live":
        render_live(analyzer)
    elif workspace == "15K":
        render_challenge_15k()
    elif workspace == "Meine Tipps":
        from my_tips import render_my_tips

        render_my_tips()
    else:
        st.error("Dieser Bereich ist nicht verfügbar.")

    st.divider()
    st.caption(
        "Modellwahrscheinlichkeiten können falsch sein. Glücksspiel birgt finanzielles Risiko; "
        "kein Ergebnis ist garantiert."
    )
    _render_mobile_nav(st.session_state.get("workspace", "Wettfinder"))


if __name__ == "__main__":
    main()
