"""Responsive BetBoy analysis workspace."""

import importlib
import math
import sqlite3
from dataclasses import asdict
from datetime import datetime
from typing import Optional
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

import league_catalog as _league_catalog


_REQUIRED_LEAGUE_CATALOG_VERSION = 2
if getattr(_league_catalog, "CATALOG_VERSION", 0) < _REQUIRED_LEAGUE_CATALOG_VERSION:
    _league_catalog = importlib.reload(_league_catalog)

import advanced_analyzer as _advanced_analyzer
import alternative_markets_tab_extended as _alternative_markets
import challenge_15k as _challenge_15k
import football_recommendations as _football_recommendations

_REQUIRED_ANALYZER_MODULE_VERSION = 3
if getattr(_advanced_analyzer, "ANALYZER_MODULE_VERSION", 0) < _REQUIRED_ANALYZER_MODULE_VERSION:
    _advanced_analyzer = importlib.reload(_advanced_analyzer)

_REQUIRED_CHALLENGE_WORKSPACE_VERSION = 3
if getattr(_challenge_15k, "CHALLENGE_WORKSPACE_VERSION", 0) < _REQUIRED_CHALLENGE_WORKSPACE_VERSION:
    _challenge_15k = importlib.reload(_challenge_15k)

_REQUIRED_MARKET_WORKFLOW_VERSION = 4
if getattr(_alternative_markets, "MARKET_WORKFLOW_VERSION", 0) < _REQUIRED_MARKET_WORKFLOW_VERSION:
    _alternative_markets = importlib.reload(_alternative_markets)

_REQUIRED_FOOTBALL_RECOMMENDATIONS_VERSION = 2
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
from ui_components import plain_german, render_empty_state
from config_loader import load_app_config
from league_catalog import ALTERNATIVE_MARKET_LEAGUES, ANALYZER_LEAGUE_IDS
from multi_sport_recommendations import build_candidate


PAGE_INFO = {
    "Spiele": (
        "Spiele Wettfinder",
        "Bis zu drei geprüfte Spiel-Auswahlen; die N1Bet-Quote entscheidet erst danach über den Preis.",
    ),
    "Märkte": (
        "Markt Wettfinder",
        "Für den Spieltag bis zu drei konkrete Markt-Auswahlen finden und anschließend den N1Bet-Preis prüfen.",
    ),
    "Live": (
        "Live Wettfinder",
        "Frische Live-Daten in eine konkrete Wette oder ein eindeutiges Nicht-wetten übersetzen.",
    ),
    "System": (
        "Wettfinder-System",
        "Validierung, Datenbestand und Modelltraining für die Wettfinder verwalten.",
    ),
    "15K Challenge": (
        "15K Challenge",
        "Bis zu drei streng geprüfte Spiele; N1Bet-Preise kommen erst nach der Modellfreigabe hinzu.",
    ),
    "Multi-Sport": (
        "Multi-Sport Wettfinder",
        "Modell zuerst, N1Bet-Preis danach: wetten nur bei positivem risikoadjustiertem Value.",
    ),
    "Tennis": (
        "Tennis Wettfinder",
        "Tägliche Modell-Vorhersagen (Shadow); N1Bet-Preis manuell prüfen — Wette nur wenn alle Prüfungen grün sind.",
    ),
}

PREMATCH_SNAPSHOT_VERSION = 3
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


def _scope_signature(leagues: list[str], days_ahead: int) -> dict:
    return {
        "leagues": sorted(str(league) for league in leagues),
        "days_ahead": int(days_ahead),
    }


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

        /* --- Edge / EV badges (traffic light follows the 4/6 pp price gate) --- */
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
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_analyzer(module_version: int = _REQUIRED_ANALYZER_MODULE_VERSION):
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
        response = requests.get(
            "https://v3.football.api-sports.io/status",
            headers={"x-apisports-key": api_key},
            timeout=8,
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
        detail = errors.get("access") if isinstance(errors, dict) else str(errors)
        state = "suspended" if "suspend" in str(detail).lower() else "error"
        return {
            "state": state,
            "label": "Live-API gesperrt" if state == "suspended" else "Live-API Fehler",
            "detail": str(detail),
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


def _render_sidebar(analyzer) -> str:
    with st.sidebar:
        st.markdown("## BetBoy")
        st.caption("Wettfinder")
        if st.session_state.get("workspace") not in PAGE_INFO:
            st.session_state["workspace"] = "Spiele"
        workspace = st.radio(
            "Arbeitsbereich",
            list(PAGE_INFO),
            label_visibility="collapsed",
            key="workspace",
        )

        st.divider()
        st.caption("SYSTEMSTATUS")
        if analyzer and analyzer.model_trained:
            st.markdown(
                '<div class="bb-status"><span class="bb-dot"></span>'
                "Validiertes ML aktiv</div>",
                unsafe_allow_html=True,
            )
        elif analyzer:
            st.markdown(
                '<div class="bb-status"><span class="bb-dot warn"></span>'
                "Statistisches Modell aktiv</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="bb-status"><span class="bb-dot error"></span>'
                "Analyzer nicht bereit</div>",
                unsafe_allow_html=True,
            )

        config = load_app_config(st)
        if config.api_football_key:
            api_health = _api_football_health(config.api_football_key)
            api_state = api_health["label"]
            api_class = "bb-dot" if api_health["state"] == "active" else "bb-dot error"
        else:
            api_health = {"state": "missing", "detail": ""}
            api_state = "Live-API fehlt"
            api_class = "bb-dot warn"
        st.markdown(
            f'<div class="bb-status"><span class="{api_class}"></span>{api_state}</div>',
            unsafe_allow_html=True,
        )
        checked_at = api_health.get("checked_at")
        if checked_at:
            st.caption(f"API geprüft: {_format_stand(datetime.fromisoformat(checked_at))}")
        stats_stand = _stats_freshness()
        if stats_stand is not None:
            st.caption(f"Datenstand: {_format_stand(stats_stand)}")
        if api_health.get("detail") and api_health["state"] in {"suspended", "error"}:
            st.caption(api_health["detail"])

        if analyzer and analyzer.engine.database_warning:
            st.markdown(
                '<div class="bb-status"><span class="bb-dot warn"></span>'
                "Datenbank: lokaler Ersatz</div>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.caption(
            "Quoten sind nur Preise. Modellwahrscheinlichkeiten entstehen unabhängig davon."
        )
    return workspace


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


def _scan_prematch(analyzer, leagues: list[str], days_ahead: int) -> pd.DataFrame:
    progress = st.progress(0)
    status = st.empty()
    collected = []
    total = max(len(leagues), 1)
    try:
        for index, league_code in enumerate(leagues):
            status.caption(f"Analysiere {league_code} ({index + 1}/{len(leagues)})")
            league_results = analyzer.analyze_upcoming_matches(
                league_code,
                days_ahead=days_ahead,
                min_probability=0,
            )
            if league_results is not None and not league_results.empty:
                league_results = league_results.copy()
                league_results["League"] = league_code
                collected.append(league_results)
            progress.progress((index + 1) / total)
    finally:
        status.empty()
        progress.empty()
    return _prepare_results(collected)


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
    eligible = results[
        (results["BTTS_num"] >= min_probability)
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
        st.error(
            f"KEINE WETTE — keines der {len(candidate_rows)} geprüften Spiele "
            "besteht alle Prüfkriterien."
        )
        st.caption(
            "Das ist Absicht, kein Fehler: Das Modell wettet nur bei ausreichender "
            "Evidenz. Warum jedes Spiel durchgefallen ist, steht in der Liste unten."
        )
    else:
        st.success(
            f"{len(ready_rows)} von {len(candidate_rows)} geprüften Spielen bestehen "
            "alle Prüfkriterien. Jetzt nur noch die exakte N1Bet-Quote prüfen."
        )
        options = list(range(len(ready_rows)))
        selected_position = st.selectbox(
            "Spiel auswählen",
            options,
            format_func=lambda position: (
                f"{ready_rows[position][0].event_label} | "
                f"{ready_rows[position][0].market}: {ready_rows[position][0].selection or 'keine Auswahl'}"
            ),
            key="prematch_bet_candidate",
        )
        candidate, selected_row = ready_rows[selected_position]
        render_price_decision(
            candidate,
            key=f"prematch_{candidate.event_key}_{scanned_at}",
            bankroll_key="football_bet_finder_bankroll",
        )

    with st.expander(f"Alle {len(candidate_rows)} geprüften Spiele mit Einzelgründen"):
        display_frame = pd.DataFrame(
            [
                {
                    "Freigabe": "✅ Ja" if item.model_ready else "❌ Nein",
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
        st.error("API-Football-Key fehlt. Konfiguration unter System prüfen.")
        return

    st.subheader("Filter")
    filter_columns = st.columns(3)
    min_probability = filter_columns[0].slider(
        "Min. BTTS (%)",
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
    league_scope = _segmented(
        "Ligen",
        ["Favoriten", "Auswahl", "Alle"],
        "prematch_league_scope",
        "Favoriten",
    )
    defaults = [code for code in DEFAULT_PREMATCH_LEAGUES if code in available_leagues]
    if not defaults:
        defaults = available_leagues[: min(3, len(available_leagues))]
    if league_scope == "Favoriten":
        selected_leagues = defaults
        st.caption(
            ", ".join(_league_label_for_code(code) for code in selected_leagues)
        )
    elif league_scope == "Alle":
        selected_leagues = available_leagues
        st.caption(
            f"{len(selected_leagues)} konfigurierte Ligen; diese Suche benötigt "
            "entsprechend mehr Provider-Aufrufe."
        )
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
        try:
            results = _scan_prematch(
                analyzer,
                selected_leagues,
                days_ahead,
            )
            snapshot = {
                "version": PREMATCH_SNAPSHOT_VERSION,
                "scanned_at": datetime.now().astimezone().isoformat(),
                "scope": _scope_signature(selected_leagues, days_ahead),
                "results": results,
            }
            st.session_state["prematch_snapshot"] = snapshot
            st.session_state["prematch_results"] = results
            st.session_state["all_results"] = results
            if results.empty:
                st.error("NICHT WETTEN: Für diese Auswahl wurden keine kommenden Spiele gefunden.")
            else:
                st.success(f"{len(results)} Spiele geprüft — Ergebnis:")
        except Exception as exc:
            st.error(f"Wettfinder fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("prematch_snapshot")
    if not isinstance(snapshot, dict):
        render_empty_state(
            "So funktioniert die BTTS-Suche",
            [
                "Mindestwerte und Ligen wählen, dann „BTTS-Wetten finden“ klicken.",
                "Das Modell filtert quotenfrei bis zu drei geprüfte Auswahlen.",
                "Erst die exakte N1Bet-Quote entscheidet über WETTEN oder NICHT WETTEN.",
            ],
            duration_hint="Dauer: je nach Ligaanzahl etwa 30–90 Sekunden.",
        )
        return
    if snapshot.get("version") != PREMATCH_SNAPSHOT_VERSION:
        st.warning("Dieses Prematch-Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return
    current_scope = _scope_signature(selected_leagues, days_ahead)
    if snapshot.get("scope") != current_scope:
        st.warning("Liga oder Zeitraum wurden seit dem Ergebnis geändert. Wetten neu suchen.")
        return
    results = snapshot.get("results")
    st.caption(f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))}")
    if not isinstance(results, pd.DataFrame) or results.empty:
        st.info("Dieser Snapshot enthält keine kommenden Spiele.")
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


def _scan_live_football(analyzer) -> dict:
    from api_football import APIFootball
    from ultra_live_scanner_v3 import UltraLiveScanner

    scanned_at = datetime.now().astimezone().isoformat()
    config = load_app_config(st)
    if not config.api_football_key:
        raise ValueError("API-Football-Key fehlt")

    api = APIFootball(config.api_football_key)
    scanner = UltraLiveScanner(analyzer, api)
    all_matches = api.get_live_matches()
    supported_ids = set(api.league_ids.values())
    matches = [
        match
        for match in all_matches
        if match.get("league", {}).get("id") in supported_ids
    ]

    analyses = []
    skipped = 0
    progress = st.progress(0.0, text="Live-Spiele werden analysiert...")
    total = max(1, len(matches))
    for index, match in enumerate(matches):
        analysis = scanner.analyze_live_match_ultra(match)
        if analysis:
            analyses.append(analysis)
        else:
            skipped += 1
        progress.progress(
            (index + 1) / total,
            text=f"Live-Spiel {index + 1} von {len(matches)} wird analysiert...",
        )
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
    return {
        "version": LIVE_SNAPSHOT_VERSION,
        "scanned_at": scanned_at,
        "provider_matches": len(all_matches),
        "supported_matches": len(matches),
        "analyses": analyses,
        "skipped_matches": skipped,
        "provider_error": provider_note,
    }


def _render_live_football(analyzer) -> None:
    st.subheader("Live-Wetten")
    market = _segmented(
        "Live-Markt",
        list(LIVE_MARKET_OPTIONS),
        "live_market",
        "Noch ein Tor",
    )
    market_notes = {
        "BTTS": "Beide Teams treffen bis zum Spielende; der aktuelle Spielstand zählt mit.",
        "Noch ein Tor": (
            "Restspiel-Markt: Es zählt mindestens ein Tor nach diesem Snapshot. "
            "Nicht mit dem normalen Live-Gesamttor-Markt verwechseln."
        ),
        "Team trifft noch": "Restspiel-Markt: Das angezeigte Team erzielt nach dem Snapshot noch ein Tor.",
    }
    st.caption(market_notes[market])

    filter_columns = st.columns(2)
    minimum_probability = filter_columns[0].slider(
        "Min. Modellwahrscheinlichkeit (%)",
        0,
        100,
        55,
        key=f"live_min_probability_{market}",
        help="Lokaler Filter auf den aktuellen Live-Snapshot; löst keinen neuen Provider-Abruf aus.",
    )
    if st.session_state.get("live_min_quality") not in LIVE_DATA_BASIS_OPTIONS:
        st.session_state["live_min_quality"] = LIVE_DATA_BASIS_OPTIONS[0]
    minimum_quality = filter_columns[1].selectbox(
        "Live-Datenbasis",
        LIVE_DATA_BASIS_OPTIONS,
        index=0,
        key="live_min_quality",
        help=(
            "Streng verlangt für beide Teams Live-xG, einen Prematch-Prior und einen "
            "verwertbaren Platzverweisstand. Basis lässt auch Schätzungen mit nur einer "
            "vollständigen Datenquelle zu."
        ),
    )
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
        try:
            with st.spinner("Live-Wetten werden geprüft..."):
                snapshot = _scan_live_football(analyzer)
                st.session_state["live_football_snapshot"] = snapshot
                st.session_state.pop("live_snapshot_invalidated_by_red_card", None)
        except Exception as exc:
            st.error(f"Live-Wettfinder fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("live_football_snapshot")
    if not snapshot:
        render_empty_state(
            "So funktioniert die Live-Suche",
            [
                "Live-Markt und Datenbasis wählen, dann „Live-Wetten finden“ klicken.",
                "Das Modell übersetzt frische Live-Daten in eine klare Entscheidung.",
                "Ergebnis: WETTEN, NICHT WETTEN oder PREIS ERFORDERLICH.",
            ],
            duration_hint="Dauer: wenige Sekunden — Live-Daten liegen bereits vor.",
        )
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
        candidate, item = candidate_items[selected]
        render_price_decision(
            candidate,
            key=f"live_{candidate.event_key}_{market}_{snapshot.get('scanned_at')}",
            bankroll_key="football_bet_finder_bankroll",
        )

        with st.expander("Live-Prüfdetails"):
            counts = st.columns(4)
            counts[0].metric("Provider-Spiele", snapshot["provider_matches"])
            counts[1].metric("Unterstützt", snapshot["supported_matches"])
            counts[2].metric("Berechnet", len(analyses))
            counts[3].metric("Kandidaten", len(candidate_items))
            st.json(
                {
                    "Modell": item.get("breakdown", {}),
                    "Restspiel": item.get("remaining_goals", {}),
                    "Platzverweise": item.get("red_cards", {}),
                },
                expanded=False,
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


def _red_card_entry(alert_system, card: dict) -> dict:
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
        prediction = alert_system.predictor.predict(
            minute=snapshot_minute,
            home_goals=home_goals,
            away_goals=away_goals,
            red_card_team=red_side,
            live_stats=entry["live_stats"],
        )
        entry["prediction"] = asdict(prediction)
    return entry


def _scan_red_cards(
    api_key: str,
    league_ids: Optional[list[int]],
    scope_label: str,
) -> dict:
    import red_card_bot as red_card_module

    if getattr(red_card_module, "RED_CARD_BOT_VERSION", 0) < 2:
        red_card_module = importlib.reload(red_card_module)
    RedCardBotEnhanced = red_card_module.RedCardBotEnhanced

    scanned_at = datetime.now().astimezone().isoformat()
    finder = RedCardBotEnhanced(
        api_key=api_key,
        streamlit_mode=True,
    )
    live_matches = finder.get_live_matches(league_ids)
    cards = []
    for match in live_matches:
        match_cards = finder.check_match_for_red_cards(match, include_seen=True)
        for card in match_cards:
            entry = _red_card_entry(finder, card)
            entry["fixture_red_card_count"] = len(match_cards)
            cards.append(entry)
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
            st.error("API-Football-Key fehlt.")
        else:
            try:
                with st.spinner("Platzverweis-Wetten werden geprüft..."):
                    red_card_snapshot = _scan_red_cards(
                        config.api_football_key,
                        league_ids,
                        scan_scope,
                    )
                    st.session_state["red_card_snapshot"] = red_card_snapshot
                    if red_card_snapshot.get("cards"):
                        st.session_state.pop("live_football_snapshot", None)
                        st.session_state["live_snapshot_invalidated_by_red_card"] = (
                            red_card_snapshot.get("scanned_at")
                        )
            except Exception as exc:
                st.error(f"Platzverweis-Wettfinder fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("red_card_snapshot")
    if not snapshot:
        render_empty_state(
            "So funktioniert die Platzverweis-Suche",
            [
                "Filter wählen und die Suche starten.",
                "Das Modell bewertet Spiele mit erhöhter Platzverweis-Wahrscheinlichkeit.",
                "Erst die exakte Quote entscheidet über WETTEN oder NICHT WETTEN.",
            ],
            duration_hint="Dauer: je nach Ligaanzahl etwa 30–90 Sekunden.",
        )
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
            red_card_candidate(entry, snapshot_age_seconds=snapshot_age),
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
    candidate, entry = candidate_entries[selected]
    render_price_decision(
        candidate,
        key=f"red_card_{candidate.event_key}_{snapshot.get('scanned_at')}",
        bankroll_key="football_bet_finder_bankroll",
    )
    with st.expander("Platzverweis-Prüfdetails"):
        st.caption(
            f"{snapshot['live_matches']} Live-Spiele geprüft | "
            f"{len(snapshot['cards'])} Platzverweise bewertet"
        )
        _render_red_card_detail(entry)


def render_live(analyzer) -> None:
    if analyzer is None:
        st.error("Analyzer nicht bereit.")
        return
    mode = _segmented(
        "Live-Bereich",
        ["Spiele", "Platzverweise"],
        "live_workspace",
        "Spiele",
    )
    if mode == "Spiele":
        _render_live_football(analyzer)
    else:
        _render_red_cards(analyzer)


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
    progress = st.progress(0)
    status = st.empty()
    refreshed = 0
    total = max(len(leagues), 1)
    try:
        for index, league_code in enumerate(leagues):
            status.caption(f"Lade {league_code} ({index + 1}/{len(leagues)})")
            analyzer.engine.fetch_league_matches(league_code, force_refresh=force)
            refreshed += 1
            progress.progress((index + 1) / total)
    finally:
        status.empty()
        progress.empty()
    return refreshed


def _smart_refresh(analyzer, leagues: list[str]) -> int:
    connection = _get_db_connection("btts_data.db")
    refreshed = 0
    progress = st.progress(0)
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
            progress.progress((index + 1) / total)
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
    scope = _segmented(
        "Datenumfang",
        ["Auswahl", "Alle"],
        "data_league_scope",
        "Auswahl",
    )
    if scope == "Alle":
        selected = available
        st.caption(
            f"{len(selected)} konfigurierte Ligen; vollständige Datenupdates "
            "benötigen entsprechend mehr Provider-Aufrufe."
        )
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
        "Auswahl komplett neu laden",
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


def _multi_sport_scope_key(sport: str, detail_filter: Optional[str]) -> str:
    return f"{sport}:{detail_filter or 'all'}"


def _multi_sport_event_label(sport: str, item: dict) -> str:
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
) -> dict:
    """Fetch only the provider selected by the user."""
    if sport not in MULTI_SPORT_OPTIONS:
        raise ValueError(f"Unbekannte Sportart: {sport}")
    valid_filters = MULTI_SPORT_FILTER_OPTIONS.get(sport)
    if valid_filters:
        detail_filter = detail_filter or valid_filters[0]
        if detail_filter not in valid_filters:
            raise ValueError(f"Ungültiger Filter für {sport}: {detail_filter}")
    elif detail_filter is not None:
        raise ValueError(f"{sport} unterstützt keinen Detailfilter")

    snapshot = {
        "version": 2,
        "scanned_at": datetime.now().astimezone().isoformat(),
        "sport": sport,
        "detail_filter": detail_filter,
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
            for game in scanner.scan_live_games(provider_filter):
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
            snapshot["items"] = scanner.get_live_nhl_games()
            if scanner.errors.get("nhl"):
                snapshot["errors"]["NHL"] = scanner.errors["nhl"]
        except Exception:
            snapshot["errors"]["NHL"] = "Provider nicht verfügbar"
        return snapshot

    if sport == "Tennis":
        try:
            from scanners.tennis_scanner import TennisScanner

            scanner = TennisScanner()
            snapshot["items"] = scanner.get_live_matches()
            if scanner.last_error:
                snapshot["errors"]["Tennis"] = scanner.last_error
        except Exception:
            snapshot["errors"]["Tennis"] = "Provider nicht verfügbar"
        return snapshot

    if sport == "Cricket":
        try:
            from scanners.cricket_scanner import CricketScanner

            scanner = CricketScanner()
            snapshot["items"] = scanner.get_live_matches()
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
            for match in scanner.get_live_matches(provider_filter):
                snapshot["items"].append(dict(match))
            for provider, message in scanner.errors.items():
                snapshot["errors"][provider] = message
    except Exception:
        snapshot["errors"]["PandaScore"] = "Provider nicht verfügbar"
    return snapshot


def render_multi_sport() -> None:
    sport = st.selectbox(
        "Sportart",
        list(MULTI_SPORT_OPTIONS),
        key="multi_sport_selected_sport",
    )
    detail_filter = None
    filter_options = MULTI_SPORT_FILTER_OPTIONS.get(sport)
    if filter_options:
        detail_filter = st.selectbox(
            "Liga" if sport == "Basketball" else "Spiel",
            list(filter_options),
            key=f"multi_sport_filter_{sport.lower().replace('-', '_')}",
        )

    snapshots = st.session_state.get("multi_sport_snapshots")
    if not isinstance(snapshots, dict):
        snapshots = {}
        st.session_state["multi_sport_snapshots"] = snapshots
    scope_key = _multi_sport_scope_key(sport, detail_filter)
    if st.button(
        f"{sport}-Wettvorschläge aktualisieren",
        type="primary",
        use_container_width=True,
        key="run_multi_sport",
    ):
        with st.spinner(f"{sport}-Modelle werden aktualisiert..."):
            snapshots[scope_key] = _fetch_multi_sport_snapshot(sport, detail_filter)

    snapshot = snapshots.get(scope_key)
    if not snapshot:
        render_empty_state(
            f"So funktioniert die {sport}-Suche",
            [
                "Sportart und Liga wählen, dann „Wettvorschläge aktualisieren“ klicken.",
                "Das Modell berechnet quotenfreie Wahrscheinlichkeiten.",
                "Wetten nur bei positivem risikoadjustiertem Value.",
            ],
            duration_hint="Dauer: wenige Sekunden bis etwa eine Minute.",
        )
        return

    snapshot_items = snapshot.get("items")
    snapshot_items = snapshot_items if isinstance(snapshot_items, list) else []
    item_count = len(snapshot_items)
    caption_parts = [
        f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))}",
        f"{item_count} Live-Ereignisse",
    ]
    if detail_filter:
        caption_parts.append(f"Filter: {detail_filter}")
    sources = sorted({
        str(item.get("source")).strip()
        for item in snapshot_items or []
        if isinstance(item, dict) and str(item.get("source") or "").strip()
    })
    if sources:
        caption_parts.append(f"Quelle: {', '.join(sources)}")
    st.caption(" | ".join(caption_parts))

    snapshot_age = _snapshot_age_seconds(snapshot.get("scanned_at"))
    if snapshot_age is None or snapshot_age < -30 or snapshot_age > 180:
        st.error("NICHT WETTEN: Live-Snapshot ist ungültig oder älter als drei Minuten.")
        return

    missing_esports_key = sport == "E-Sport" and not snapshot.get(
        "credentials_available"
    )
    if missing_esports_key:
        st.error("NICHT WETTEN: Für E-Sport fehlt der PandaScore-Key.")

    if snapshot.get("errors"):
        st.warning(f"Eine {sport}-Teilquelle war nicht vollständig verfügbar.")
        with st.expander("Providerfehler"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Provider": provider, "Fehler": message}
                        for provider, message in snapshot["errors"].items()
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

    if not snapshot_items:
        if not missing_esports_key:
            st.error(
                f"NICHT WETTEN: Keine laufenden {sport}-Ereignisse mit prüfbarem Markt."
            )
        return

    selected_index = st.selectbox(
        "Spiel",
        list(range(len(snapshot_items))),
        format_func=lambda index: _multi_sport_event_label(sport, snapshot_items[index]),
        key=f"multi_sport_event_{scope_key}",
    )
    selected_item = snapshot_items[selected_index]
    snapshot_token = str(snapshot.get("scanned_at") or "snapshot").replace(":", "_")
    line_value = None
    if sport in {"Basketball", "Eishockey"}:
        line_label = (
            "N1Bet-Gesamtpunkte-Linie (x,5)"
            if sport == "Basketball"
            else "N1Bet-Gesamttore-Linie (x,5)"
        )
        raw_line = st.text_input(
            line_label,
            placeholder="z. B. 221,5" if sport == "Basketball" else "z. B. 5,5",
            key=f"multi_sport_line_{scope_key}_{selected_index}_{snapshot_token}",
        ).strip()
        if not raw_line:
            st.info("Für diesen Markt zuerst die exakte N1Bet-Linie eintragen.")
            return
        try:
            line_value = float(raw_line.replace(",", "."))
        except ValueError:
            line_value = raw_line
        # A mistyped line changes the model probability itself, so the line
        # needs the same explicit bookmaker cross-check as the price.
        line_confirmed = st.checkbox(
            f"Linie {raw_line} wurde unmittelbar mit N1Bet abgeglichen",
            value=False,
            key=f"multi_sport_line_confirmed_{scope_key}_{selected_index}_{snapshot_token}",
        )
        if not line_confirmed:
            st.info("Bitte die N1Bet-Linie abgleichen und bestätigen.")
            return

    candidate = build_candidate(
        sport,
        selected_item,
        market_line=line_value,
    )
    if candidate.blockers:
        st.error("NICHT WETTEN — das Modell gibt diese Auswahl nicht frei.")
        st.markdown("\n".join(f"- {plain_german(reason)}" for reason in candidate.blockers))
        return

    if candidate.expected_total is not None:
        st.caption(f"Posteriorer Total-Erwartungswert: {candidate.expected_total:.2f}")
    render_price_decision(
        candidate,
        key=f"multi_sport_{scope_key}_{selected_index}_{snapshot_token}",
        bankroll_key="multi_sport_bankroll",
    )


def _render_mobile_nav(workspace: str) -> None:
    """Bottom navigation for small screens; hidden on desktop via CSS.

    The sidebar radio stays the single state source: the click callback runs
    before the next script run and only sets the same ``workspace`` key.
    """
    short_labels = {
        "Spiele": "🎯 Spiele",
        "Märkte": "📈 Märkte",
        "Live": "⚡ Live",
        "System": "⚙️ System",
        "15K Challenge": "🏆 15K",
        "Multi-Sport": "🏀 Multi",
        "Tennis": "🎾 Tennis",
    }

    def _go(page: str) -> None:
        st.session_state["workspace"] = page

    with st.container(key="bb_bottomnav"):
        columns = st.columns(len(short_labels), gap="small")
        for column, (page, label) in zip(columns, short_labels.items()):
            column.button(
                label,
                key=f"bb_bottomnav_{page}",
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

    try:
        analyzer = get_analyzer(_REQUIRED_ANALYZER_MODULE_VERSION)
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
        st.error(f"Analyzer konnte nicht initialisiert werden: {st.session_state['analyzer_error']}")

    if workspace == "Spiele":
        render_matches(analyzer)
    elif workspace == "Märkte":
        create_alternative_markets_tab_extended()
    elif workspace == "Live":
        render_live(analyzer)
    elif workspace == "System":
        render_model(analyzer)
    elif workspace == "15K Challenge":
        render_challenge_15k()
    elif workspace == "Tennis":
        from tennis_tab import render_tennis_page

        render_tennis_page()
    else:
        render_multi_sport()

    st.divider()
    st.caption(
        "Modellwahrscheinlichkeiten können falsch sein. Glücksspiel birgt finanzielles Risiko; "
        "kein Ergebnis ist garantiert."
    )
    _render_mobile_nav(workspace)


if __name__ == "__main__":
    main()
