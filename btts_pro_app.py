"""Responsive BetBoy analysis workspace."""

import math
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from advanced_analyzer import AdvancedBTTSAnalyzer, ML_FEATURE_NAMES, ML_MODEL_PATH
from alternative_markets_tab_extended import create_alternative_markets_tab_extended
from challenge_15k import render_challenge_15k
from config_loader import load_app_config


PAGE_INFO = {
    "Spiele": (
        "Spiele analysieren",
        "Prematch-Signale filtern, vergleichen und im selben Ablauf prüfen.",
    ),
    "Märkte": (
        "Märkte prüfen",
        "Modellpreise und verifizierte externe Quoten strikt getrennt auswerten.",
    ),
    "Live": (
        "Live-Lage",
        "Live-Spiele und Platzverweise nur auf ausdrücklichen Abruf analysieren.",
    ),
    "Modell": (
        "Modell und Daten",
        "Validierung, Datenbestand und Training an einem Ort verwalten.",
    ),
    "15K Challenge": (
        "15K Challenge",
        "Bis zu drei streng geprüfte Spiele; N1Bet-Preise kommen erst nach der Modellfreigabe hinzu.",
    ),
    "Multi-Sport": (
        "Multi-Sport",
        "Provider-Snapshots sportweise ansehen, ohne Scores zu vermischen.",
    ),
}

PREMATCH_SNAPSHOT_VERSION = 2
LIVE_SNAPSHOT_VERSION = 3
RED_CARD_SNAPSHOT_VERSION = 2
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


def _get_supabase_url() -> Optional[str]:
    """Return the configured PostgreSQL URL when available."""
    return load_app_config(st).supabase_db_url


def _get_db_connection(db_path: str = "btts_data.db"):
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
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_analyzer():
    """Initialize the analyzer from the central configuration."""
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
    """Return provider account state without exposing credential material."""
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
        }

    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        detail = errors.get("access") if isinstance(errors, dict) else str(errors)
        state = "suspended" if "suspend" in str(detail).lower() else "error"
        return {
            "state": state,
            "label": "Live-API gesperrt" if state == "suspended" else "Live-API Fehler",
            "detail": str(detail),
        }

    provider_response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(provider_response, dict):
        return {
            "state": "error",
            "label": "Live-API Status unklar",
            "detail": f"HTTP {response.status_code}",
        }

    subscription = provider_response.get("subscription") or {}
    active = subscription.get("active")
    plan = str(subscription.get("plan") or "aktiv")
    if active is False:
        return {
            "state": "suspended",
            "label": "Live-API inaktiv",
            "detail": f"Tarif: {plan}",
        }
    return {
        "state": "active",
        "label": f"Live-API aktiv ({plan})",
        "detail": "",
    }


def _render_sidebar(analyzer) -> str:
    with st.sidebar:
        st.markdown("## BetBoy")
        st.caption("Analyse-Arbeitsplatz")
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


def _render_prematch_results(results: pd.DataFrame, min_probability: int, min_quality: int) -> None:
    eligible = results[
        (results["BTTS_num"] >= min_probability)
        & (results["Quality_num"] >= min_quality)
    ].copy()
    if eligible.empty:
        st.warning("Kein gespeichertes Ergebnis erfüllt die aktuellen Filter.")
        return

    st.subheader("Ergebnisse")
    summary = st.columns(4)
    summary[0].metric("Matches", len(eligible))
    summary[1].metric("BTTS im Mittel", f"{eligible['BTTS_num'].mean():.1f}%")
    summary[2].metric("Qualität im Mittel", f"{eligible['Quality_num'].mean():.1f}%")
    summary[3].metric("Ligen", eligible["League"].nunique())

    preferred_columns = [
        "Date",
        "League",
        "Home",
        "Away",
        "BTTS %",
        "Data Quality",
        "Modellstatus",
        "xG Total",
    ]
    display_columns = [column for column in preferred_columns if column in eligible.columns]
    display_frame = eligible[display_columns].rename(
        columns={"Data Quality": "Evidenzscore"}
    )
    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        height=min(430, 72 + len(eligible) * 35),
    )

    options = list(range(len(eligible)))
    detail_key = "prematch_detail_match"
    if st.session_state.get(detail_key) not in options:
        st.session_state[detail_key] = options[0]
    selected_position = st.selectbox(
        "Match im Detail",
        options,
        format_func=lambda position: (
            f"{eligible.iloc[position].get('Home', 'Home')} vs "
            f"{eligible.iloc[position].get('Away', 'Away')} | "
            f"{eligible.iloc[position].get('Date', 'n/a')}"
        ),
        key=detail_key,
    )
    selected_row = eligible.iloc[selected_position]
    detail_view = _segmented(
        "Detailansicht",
        ["Überblick", "Modelle", "Teams"],
        "prematch_detail_view",
        "Überblick",
    )
    if detail_view == "Überblick":
        _render_match_overview(selected_row)
    elif detail_view == "Modelle":
        _render_match_models(selected_row)
    else:
        _render_match_teams(selected_row)


def render_matches(analyzer) -> None:
    if analyzer is None:
        st.error("API-Football-Key fehlt. Konfiguration unter Modell prüfen.")
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
        st.caption(", ".join(selected_leagues))
    elif league_scope == "Alle":
        selected_leagues = available_leagues
        st.caption(f"{len(selected_leagues)} konfigurierte Ligen")
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_leagues,
            default=defaults,
            key="prematch_leagues",
        )

    action_columns = st.columns([1, 2])
    run_scan = action_columns[0].button(
        "Spiele analysieren",
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
                st.warning("Für diese Auswahl wurden keine kommenden Spiele gefunden.")
            else:
                st.success(f"{len(results)} Matches geladen.")
        except Exception as exc:
            st.error(f"Analyse fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("prematch_snapshot")
    if not isinstance(snapshot, dict):
        st.info("Noch kein Prematch-Snapshot in dieser Sitzung.")
        return
    if snapshot.get("version") != PREMATCH_SNAPSHOT_VERSION:
        st.warning("Dieser Prematch-Snapshot stammt aus einer älteren App-Version. Neu scannen.")
        return
    current_scope = _scope_signature(selected_leagues, days_ahead)
    if snapshot.get("scope") != current_scope:
        st.warning("Liga oder Zeitraum wurden seit dem Snapshot geändert. Neu scannen.")
        return
    results = snapshot.get("results")
    st.caption(f"Snapshot: {_format_snapshot_time(snapshot.get('scanned_at'))}")
    if not isinstance(results, pd.DataFrame) or results.empty:
        st.info("Dieser Snapshot enthält keine kommenden Spiele.")
        return
    _render_prematch_results(results, min_probability, min_quality)


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
        return None, "Ungültige Analyse"
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
    for match in matches:
        analysis = scanner.analyze_live_match_ultra(match)
        if analysis:
            analyses.append(analysis)
    return {
        "version": LIVE_SNAPSHOT_VERSION,
        "scanned_at": datetime.now().astimezone().isoformat(),
        "provider_matches": len(all_matches),
        "supported_matches": len(matches),
        "analyses": analyses,
        "provider_error": api.last_error,
    }


def _render_live_football(analyzer) -> None:
    st.subheader("Live-Spiele")
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
            "Seit dem letzten Live-Snapshot wurde ein neuer Platzverweis erkannt. "
            "Der alte Snapshot wurde verworfen; bitte neu scannen."
        )
    if st.button(
        "Live-Scan starten",
        type="primary",
        use_container_width=True,
        key="run_live_football",
    ):
        try:
            with st.spinner("Live-Spiele werden analysiert..."):
                snapshot = _scan_live_football(analyzer)
                st.session_state["live_football_snapshot"] = snapshot
                st.session_state.pop("live_snapshot_invalidated_by_red_card", None)
        except Exception as exc:
            st.error(f"Live-Scan fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("live_football_snapshot")
    if not snapshot:
        st.info("Noch kein Live-Snapshot in dieser Sitzung.")
        return
    if snapshot.get("version") != LIVE_SNAPSHOT_VERSION:
        st.warning("Dieser Live-Snapshot stammt aus einer älteren App-Version. Neu scannen.")
        return

    st.caption(f"Snapshot: {_format_snapshot_time(snapshot.get('scanned_at'))}")
    opportunities = _filter_live_opportunities(
        snapshot.get("analyses", []),
        minimum_probability,
        minimum_quality,
        market,
    )
    if snapshot.get("provider_error"):
        st.warning(f"Live-Provider nicht vollständig verfügbar: {snapshot['provider_error']}")
    counts = st.columns(4)
    counts[0].metric("Provider-Spiele", snapshot["provider_matches"])
    counts[1].metric("Unterstützte Spiele", snapshot["supported_matches"])
    counts[2].metric("Analysiert", len(snapshot.get("analyses", [])))
    counts[3].metric("Filtertreffer", len(opportunities))

    if not opportunities:
        st.info("Kein Spiel erfüllt die Filter dieses Snapshots.")
        return

    rows = []
    for item in opportunities:
        probability, selection = _live_market_signal(item, market)
        red_cards = item.get("red_cards") or {}
        home_red = red_cards.get("home_count")
        away_red = red_cards.get("away_count")
        red_card_label = (
            f"{home_red}/{away_red}"
            if home_red is not None and away_red is not None
            else "n/a"
        )
        rows.append(
            {
                "Minute": item.get("minute"),
                "Match": f"{item.get('home_team')} vs {item.get('away_team')}",
                "Stand": item.get("score"),
                "Auswahl": selection,
                "Modell %": probability,
                "Datenbasis": LIVE_QUALITY_LABELS.get(
                    item.get("live_data_quality"),
                    item.get("live_data_quality", "n/a"),
                ),
                "Rot H/A": red_card_label,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    live_detail_options = list(range(len(opportunities)))
    live_detail_key = "live_match_detail"
    if st.session_state.get(live_detail_key) not in live_detail_options:
        st.session_state[live_detail_key] = live_detail_options[0]
    selected = st.selectbox(
        "Live-Match im Detail",
        live_detail_options,
        format_func=lambda index: rows[index]["Match"],
        key=live_detail_key,
    )
    item = opportunities[selected]
    from ultra_live_scanner_v3 import display_ultra_opportunity

    live_detail_options = ["Kernmärkte", "Modelleingaben"]
    if st.session_state.get("live_detail_view") not in live_detail_options:
        st.session_state["live_detail_view"] = live_detail_options[0]
    detail_view = _segmented(
        "Detailansicht",
        live_detail_options,
        "live_detail_view",
        "Kernmärkte",
    )
    if detail_view == "Kernmärkte":
        display_ultra_opportunity(item)
    else:
        st.json(
            {
                "Modell": item.get("breakdown", {}),
                "Restspiel": item.get("remaining_goals", {}),
                "Platzverweise": item.get("red_cards", {}),
            },
            expanded=False,
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
    telegram_token: Optional[str],
    telegram_chat_id: Optional[str],
    enable_browser: bool,
    enable_telegram: bool,
    league_ids: Optional[list[int]],
    scope_label: str,
) -> dict:
    from red_card_bot import RedCardBotEnhanced

    alert_system = RedCardBotEnhanced(
        api_key=api_key,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        streamlit_mode=True,
    )
    live_matches = alert_system.get_live_matches(league_ids)
    cards = []
    for match in live_matches:
        for card in alert_system.check_match_for_red_cards(match):
            entry = _red_card_entry(alert_system, card)
            if enable_browser:
                st.toast(f"Platzverweis: {card['player']} ({card['team']})")
            if enable_telegram and alert_system.send_telegram_alert_with_stats(
                card,
                live_stats=entry.get("live_stats"),
                fetch_live_stats=False,
            ):
                entry["telegram_sent"] = True
            else:
                entry["telegram_sent"] = False
            alert_system._mark_alerted(card["card_id"])
            cards.append(entry)
    return {
        "version": RED_CARD_SNAPSHOT_VERSION,
        "scanned_at": datetime.now().astimezone().isoformat(),
        "scope": scope_label,
        "live_matches": len(live_matches),
        "cards": cards,
        "errors": list(alert_system.errors),
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
    st.subheader("Platzverweise")
    scope_options = ["Konfigurierte Ligen", "Weltweit"]
    if st.session_state.get("red_card_scope") not in scope_options:
        st.session_state["red_card_scope"] = scope_options[0]
    scan_scope = st.selectbox(
        "Scan-Umfang",
        scope_options,
        key="red_card_scope",
        help=(
            "Konfigurierte Ligen begrenzt Event-Abfragen. Weltweit prüft jedes vom Provider "
            "gelieferte Live-Spiel und kann viel API-Quota benötigen."
        ),
    )
    league_ids = (
        sorted(set(analyzer.engine.LEAGUES_CONFIG.values()))
        if scan_scope == "Konfigurierte Ligen"
        else None
    )
    setting_columns = st.columns(2)
    enable_browser = setting_columns[0].checkbox(
        "Browser-Hinweis", value=True, key="red_browser_alert"
    )
    configured_telegram = bool(config.telegram_bot_token and config.telegram_chat_id)
    enable_telegram = setting_columns[1].checkbox(
        "Telegram",
        value=configured_telegram,
        key="red_telegram_alert",
    )

    telegram_token = config.telegram_bot_token
    telegram_chat_id = config.telegram_chat_id
    if enable_telegram and not configured_telegram:
        credential_columns = st.columns(2)
        telegram_token = credential_columns[0].text_input(
            "Telegram Bot-Token", type="password", key="red_telegram_token"
        )
        telegram_chat_id = credential_columns[1].text_input(
            "Telegram Chat-ID", key="red_telegram_chat_id"
        )

    if st.button(
        "Auf neue Platzverweise prüfen",
        type="primary",
        use_container_width=True,
        key="run_red_card_scan",
    ):
        if not config.api_football_key:
            st.error("API-Football-Key fehlt.")
        elif enable_telegram and (not telegram_token or not telegram_chat_id):
            st.warning("Für Telegram werden Bot-Token und Chat-ID benötigt.")
        else:
            try:
                with st.spinner("Live-Ereignisse werden geprüft..."):
                    red_card_snapshot = _scan_red_cards(
                        config.api_football_key,
                        telegram_token,
                        telegram_chat_id,
                        enable_browser,
                        enable_telegram,
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
                st.error(f"Platzverweis-Scan fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("red_card_snapshot")
    if not snapshot:
        st.info("Noch kein Platzverweis-Snapshot in dieser Sitzung.")
        return
    if snapshot.get("version") != RED_CARD_SNAPSHOT_VERSION:
        st.warning("Dieser Platzverweis-Snapshot stammt aus einer älteren App-Version. Neu scannen.")
        return
    if snapshot.get("scope") != scan_scope:
        st.warning("Der Scan-Umfang wurde seit dem Snapshot geändert. Neu scannen.")
        return

    st.caption(
        f"Snapshot: {_format_snapshot_time(snapshot.get('scanned_at'))} | "
        f"Umfang: {snapshot.get('scope')}"
    )
    if snapshot.get("errors"):
        st.warning(
            f"{len(snapshot['errors'])} Provider-Abfragen sind fehlgeschlagen; "
            "vorhandene Ereignisse bleiben sichtbar."
        )
    summary = st.columns(2)
    summary[0].metric("Live-Spiele", snapshot["live_matches"])
    summary[1].metric("Neue Platzverweise", len(snapshot["cards"]))
    if not snapshot["cards"]:
        st.info("Keine neuen Platzverweise gefunden.")
        return

    labels = [
        f"{entry['home']} vs {entry['away']} | {entry['card']['player']}"
        for entry in snapshot["cards"]
    ]
    detail_key = "red_card_detail"
    detail_options = list(range(len(labels)))
    if st.session_state.get(detail_key) not in detail_options:
        st.session_state[detail_key] = detail_options[0]
    selected = st.selectbox(
        "Ereignis im Detail",
        detail_options,
        format_func=lambda index: labels[index],
        key=detail_key,
    )
    _render_red_card_detail(snapshot["cards"][selected])


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
        st.caption(f"{len(selected)} konfigurierte Ligen")
    else:
        defaults = [code for code in ["BL1", "PL", "PD"] if code in available]
        selected = st.multiselect(
            "Ligen",
            available,
            default=defaults,
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


def _fetch_multi_sport_snapshot(game_filter: str) -> dict:
    """Fetch one cross-provider snapshot after an explicit user action."""
    import sys

    scanner_path = str(Path(__file__).parent / "scanners")
    if scanner_path not in sys.path:
        sys.path.insert(0, scanner_path)
    snapshot = {
        "scanned_at": datetime.now().astimezone().isoformat(),
        "game_filter": game_filter,
        "basketball": [],
        "nhl": [],
        "tennis": [],
        "cricket": [],
        "esports": [],
        "esports_key_available": False,
        "errors": {},
    }

    basketball = None
    try:
        from basketball_scanner import BasketballScanner

        basketball = BasketballScanner()
    except Exception:
        snapshot["errors"]["basketball_scanner"] = "Scanner nicht verfügbar"

    try:
        if basketball is None:
            raise RuntimeError("basketball scanner unavailable")
        for game in basketball.scan_live_games("All"):
            item = dict(game)
            item["projection"] = basketball.calculate_scoring_projection(game)
            snapshot["basketball"].append(item)
        for provider, message in basketball.errors.items():
            snapshot["errors"][f"basketball_{provider}"] = message
    except Exception:
        snapshot["errors"]["basketball"] = "Provider nicht verfügbar"

    try:
        if basketball is None:
            raise RuntimeError("basketball scanner unavailable")
        snapshot["nhl"] = basketball.get_live_nhl_games()
        if basketball.errors.get("nhl"):
            snapshot["errors"]["nhl"] = basketball.errors["nhl"]
    except Exception:
        snapshot["errors"]["nhl"] = "Provider nicht verfügbar"

    try:
        from tennis_scanner import TennisScanner

        tennis = TennisScanner()
        snapshot["tennis"] = tennis.get_live_matches()
        if tennis.last_error:
            snapshot["errors"]["tennis"] = tennis.last_error
    except Exception:
        snapshot["errors"]["tennis"] = "Provider nicht verfügbar"

    try:
        from cricket_scanner import CricketScanner

        cricket = CricketScanner()
        snapshot["cricket"] = cricket.get_live_matches()
        if cricket.last_error:
            snapshot["errors"]["cricket"] = cricket.last_error
    except Exception:
        snapshot["errors"]["cricket"] = "Provider nicht verfügbar"

    try:
        from esports_scanner import EsportsScanner

        esports = EsportsScanner()
        snapshot["esports_key_available"] = bool(esports.api_key)
        if esports.api_key:
            for match in esports.get_live_matches(game_filter.lower()):
                item = dict(match)
                item["_analysis"] = esports.analyze_match(match)
                snapshot["esports"].append(item)
            for provider, message in esports.errors.items():
                snapshot["errors"][f"esports_{provider}"] = message
    except Exception:
        snapshot["errors"]["esports"] = "Provider nicht verfügbar"
    return snapshot


def _multi_sport_frame(snapshot: dict, sport: str) -> pd.DataFrame:
    if sport == "Basketball":
        return pd.DataFrame(
            [
                {
                    "Match": f"{game['home_team']} vs {game['away_team']}",
                    "Periode": f"Q{game.get('period', 'n/a')}",
                    "Stand": f"{game.get('home_score', 'n/a')}-{game.get('away_score', 'n/a')}",
                    "Lineare Total-Projektion": _format_optional(game.get("projection"), 1),
                }
                for game in snapshot["basketball"]
            ]
        )
    if sport == "NHL":
        return pd.DataFrame(
            [
                {
                    "Match": f"{game['away_team']} @ {game['home_team']}",
                    "Periode": f"P{game.get('period', 'n/a')}",
                    "Stand": f"{game.get('away_score', 'n/a')}-{game.get('home_score', 'n/a')}",
                    "Uhr": game.get("game_clock") or "n/a",
                }
                for game in snapshot["nhl"]
            ]
        )
    if sport == "Tennis":
        return pd.DataFrame(
            [
                {
                    "Match": f"{match['player1']} vs {match['player2']}",
                    "Turnier": match.get("tournament", "ATP/WTA"),
                    "Stand": f"{match.get('player1_score', 'n/a')}-{match.get('player2_score', 'n/a')}",
                    "Aufschlag": match.get("server", "n/a"),
                }
                for match in snapshot["tennis"]
            ]
        )
    if sport == "Cricket":
        return pd.DataFrame(
            [
                {
                    "Match": f"{match['team1']} vs {match['team2']}",
                    "Format": match.get("format", "T20"),
                    "Over": match.get("current_over", "n/a"),
                    "Run Rate": match.get("run_rate", "n/a"),
                }
                for match in snapshot["cricket"]
            ]
        )
    return pd.DataFrame(
        [
            {
                "Match": f"{match['team1']} vs {match['team2']}",
                "Game": match.get("game", "n/a"),
                "Stand": f"{match.get('team1_score', 'n/a')}-{match.get('team2_score', 'n/a')}",
                "Explorative Lücke": (
                    match.get("_analysis", {}).get("probability_gap")
                    if match.get("_analysis")
                    else "n/a"
                ),
                "Datenabdeckung %": (
                    match.get("_analysis", {}).get("data_coverage")
                    if match.get("_analysis")
                    else "n/a"
                ),
            }
            for match in snapshot["esports"]
        ]
    )


def render_multi_sport() -> None:
    game_filter = _segmented(
        "E-Sport-Filter",
        ["All", "CS2", "LoL", "Dota2", "Valorant"],
        "esports_game_filter",
        "All",
    )
    if st.button(
        "Provider-Snapshot laden",
        type="primary",
        use_container_width=True,
        key="run_multi_sport",
    ):
        with st.spinner("Externe Provider werden abgefragt..."):
            st.session_state["multi_sport_snapshot"] = _fetch_multi_sport_snapshot(game_filter)

    snapshot = st.session_state.get("multi_sport_snapshot")
    if not snapshot:
        st.info("Noch kein Multi-Sport-Snapshot in dieser Sitzung.")
        return

    st.caption(
        f"Snapshot: {_format_snapshot_time(snapshot.get('scanned_at'))} | "
        f"E-Sport-Filter: {snapshot['game_filter']}"
    )
    if snapshot.get("game_filter") != game_filter:
        st.warning("Der E-Sport-Filter wurde seit dem Snapshot geändert. Für aktuelle E-Sport-Daten neu laden.")
    counts = st.columns(5)
    counts[0].metric("Basketball", len(snapshot["basketball"]))
    counts[1].metric("NHL", len(snapshot["nhl"]))
    counts[2].metric("Tennis", len(snapshot["tennis"]))
    counts[3].metric("Cricket", len(snapshot["cricket"]))
    counts[4].metric("E-Sport", len(snapshot["esports"]))

    sport = _segmented(
        "Sport",
        ["Basketball", "NHL", "Tennis", "Cricket", "E-Sport"],
        "multi_sport_view",
        "Basketball",
    )
    if sport == "E-Sport" and not snapshot["esports_key_available"]:
        st.warning("Für E-Sport ist ein PandaScore-Key erforderlich.")
    frame = _multi_sport_frame(snapshot, sport)
    if frame.empty:
        st.info("Dieser Provider hat keine Live-Daten geliefert.")
    else:
        st.dataframe(frame, use_container_width=True, hide_index=True)

    if snapshot["errors"]:
        st.warning("Mindestens ein externer Provider war für diesen Snapshot nicht verfügbar.")
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
    st.caption(
        "Sportübergreifendes Ranking bleibt deaktiviert: unkalibrierte Scores verschiedener "
        "Sportarten sind mathematisch nicht vergleichbar."
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
        analyzer = get_analyzer()
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
    elif workspace == "Modell":
        render_model(analyzer)
    elif workspace == "15K Challenge":
        render_challenge_15k()
    else:
        render_multi_sport()

    st.divider()
    st.caption(
        "Modellwahrscheinlichkeiten können falsch sein. Glücksspiel birgt finanzielles Risiko; "
        "kein Ergebnis ist garantiert."
    )


if __name__ == "__main__":
    main()
