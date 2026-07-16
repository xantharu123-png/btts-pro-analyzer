"""Responsive 15K challenge workspace with strict model and price gates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import time
from typing import Any, Optional

import pandas as pd
import requests
import streamlit as st

from challenge_engine import (
    ChallengeCandidate,
    CROSS_LEG_MODEL_FACTOR,
    MAX_STAKE_FRACTION,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    apply_candidate_context,
    build_fixture_candidates,
    select_model_ticket,
    select_quoted_ticket,
    select_shortlist,
    ticket_stake,
    validate_league_markets,
)
from challenge_store import ChallengeLedger
from config_loader import load_app_config
from football_data_history import fetch_history as fetch_stat_history
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from season_utils import current_season_start_year_for_id


CHALLENGE_SNAPSHOT_VERSION = 1
DEFAULT_CHALLENGE_LEAGUES = (78, 39, 140)
MAX_CONTEXT_FIXTURES = 8
QUOTE_MAX_AGE_MINUTES = 10


def _segmented(label: str, options: list[str], key: str, default: str) -> str:
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


def _format_time(value: Optional[str]) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _format_euro(value: float) -> str:
    text = f"{float(value):,.2f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def _scope_signature(league_ids: list[int], search_date: date, max_fixtures: int) -> dict[str, Any]:
    return {
        "league_ids": sorted(int(league_id) for league_id in league_ids),
        "date": search_date.isoformat(),
        "max_fixtures": int(max_fixtures),
    }


@st.cache_resource
def _challenge_ledger() -> ChallengeLedger:
    return ChallengeLedger()


@st.cache_data(ttl=6 * 3600, max_entries=32, show_spinner=False)
def _cached_market_validation(
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
):
    """Cache expensive walk-forward results; history content is part of the key."""
    del league_id, season
    return validate_league_markets(history)


class ChallengeDataProvider:
    """Small provider wrapper with structured errors and per-scan caching."""

    def __init__(self, api_key: str, weather_key: Optional[str]):
        self.api_key = api_key
        self.weather_key = weather_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self.errors: list[str] = []
        self._last_request = 0.0
        self._weather_cache: dict[tuple[str, str], Optional[dict[str, Any]]] = {}

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.monotonic()

    def _football_get(
        self,
        path: str,
        params: dict[str, Any],
        label: str,
    ) -> Optional[list[dict[str, Any]]]:
        self._rate_limit()
        try:
            response = requests.get(
                f"{self.base_url}/{path}",
                headers=self.headers,
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.errors.append(f"{label}: {exc}")
            return None
        provider_errors = payload.get("errors")
        if provider_errors:
            plan_error = (
                provider_errors.get("plan")
                if isinstance(provider_errors, dict)
                else None
            )
            if plan_error and "do not have access to this season" in str(plan_error):
                self.errors.append(
                    f"{label}: Der aktuelle API-Tarif hat keinen Zugriff auf diese Saison "
                    "(laut Provider nur 2022 bis 2024)."
                )
            else:
                self.errors.append(f"{label}: {provider_errors}")
            return None
        data = payload.get("response")
        if not isinstance(data, list):
            self.errors.append(f"{label}: ungültige Provider-Antwort")
            return None
        return data

    def upcoming_fixtures(self, league_id: int, season: int, search_date: date) -> Optional[list[dict[str, Any]]]:
        return self._football_get(
            "fixtures",
            {
                "league": league_id,
                "season": season,
                "date": search_date.isoformat(),
                "timezone": "Europe/Zurich",
                "status": "NS",
            },
            f"Fixtures Liga {league_id}",
        )

    def completed_history(
        self,
        league_id: int,
        season: int,
        upcoming_fixtures: list[dict[str, Any]],
    ) -> Optional[list[dict[str, Any]]]:
        statistical_history = fetch_stat_history(
            league_id,
            season,
            upcoming_fixtures,
        )
        if statistical_history:
            return statistical_history
        return self._football_get(
            "fixtures",
            {"league": league_id, "season": season, "status": "FT"},
            f"Historie Liga {league_id}",
        )

    def coverage(self, league_id: int, season: int) -> dict[str, bool]:
        data = self._football_get(
            "leagues",
            {"id": league_id, "season": season},
            f"Coverage Liga {league_id}",
        )
        if not data:
            return {"injuries": False, "lineups": False}
        seasons = data[0].get("seasons") or []
        season_data = next(
            (item for item in seasons if item.get("year") == season),
            seasons[-1] if seasons else {},
        )
        coverage = season_data.get("coverage") or {}
        fixtures = coverage.get("fixtures") or {}
        return {
            "injuries": bool(coverage.get("injuries")),
            "lineups": bool(fixtures.get("lineups")),
        }

    def h2h(self, home_team_id: int, away_team_id: int) -> Optional[list[dict[str, Any]]]:
        return self._football_get(
            "fixtures/headtohead",
            {"h2h": f"{home_team_id}-{away_team_id}", "last": 10},
            f"H2H {home_team_id}-{away_team_id}",
        )

    def injuries_by_fixture(self, fixture_ids: list[int]) -> dict[int, Optional[list[dict[str, Any]]]]:
        result: dict[int, Optional[list[dict[str, Any]]]] = {fixture_id: [] for fixture_id in fixture_ids}
        for start in range(0, len(fixture_ids), 20):
            chunk = fixture_ids[start : start + 20]
            data = self._football_get(
                "injuries",
                {"ids": "-".join(str(fixture_id) for fixture_id in chunk)},
                "Verletzungen",
            )
            if data is None:
                for fixture_id in chunk:
                    fallback = self._football_get(
                        "injuries",
                        {"fixture": fixture_id},
                        f"Verletzungen Fixture {fixture_id}",
                    )
                    result[fixture_id] = fallback
                continue
            for entry in data:
                fixture_id = entry.get("fixture", {}).get("id")
                if fixture_id in result and result[fixture_id] is not None:
                    result[fixture_id].append(entry)
        return result

    def details_by_fixture(self, fixture_ids: list[int]) -> dict[int, Optional[dict[str, Any]]]:
        result: dict[int, Optional[dict[str, Any]]] = {fixture_id: None for fixture_id in fixture_ids}
        for start in range(0, len(fixture_ids), 20):
            chunk = fixture_ids[start : start + 20]
            data = self._football_get(
                "fixtures",
                {"ids": "-".join(str(fixture_id) for fixture_id in chunk)},
                "Fixture-Details",
            )
            if data is None:
                for fixture_id in chunk:
                    fallback = self._football_get(
                        "fixtures",
                        {"id": fixture_id},
                        f"Fixture-Details {fixture_id}",
                    )
                    if fallback:
                        result[fixture_id] = fallback[0]
                continue
            for fixture in data:
                fixture_id = fixture.get("fixture", {}).get("id")
                if fixture_id in result:
                    result[fixture_id] = fixture
        return result

    def weather(self, fixture: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not self.weather_key:
            return None
        kickoff_text = fixture.get("fixture", {}).get("date")
        try:
            kickoff = datetime.fromisoformat(str(kickoff_text).replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            kickoff = kickoff.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
        venue = fixture.get("fixture", {}).get("venue") or {}
        city = str(venue.get("city") or "").strip()
        country = str(fixture.get("league", {}).get("country") or "").strip()
        if not city:
            return None
        cache_key = (f"{city},{country}", kickoff.strftime("%Y-%m-%dT%H"))
        if cache_key in self._weather_cache:
            return self._weather_cache[cache_key]

        try:
            geocode = requests.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={
                    "q": f"{city},{country}" if country else city,
                    "limit": 1,
                    "appid": self.weather_key,
                },
                timeout=15,
            )
            geocode.raise_for_status()
            locations = geocode.json()
            if not locations:
                self._weather_cache[cache_key] = None
                return None
            forecast_response = requests.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "lat": locations[0]["lat"],
                    "lon": locations[0]["lon"],
                    "appid": self.weather_key,
                    "units": "metric",
                    "lang": "de",
                },
                timeout=15,
            )
            forecast_response.raise_for_status()
            forecasts = forecast_response.json().get("list") or []
        except (requests.RequestException, ValueError, KeyError) as exc:
            self.errors.append(f"Wetter {city}: {exc}")
            self._weather_cache[cache_key] = None
            return None
        if not forecasts:
            self._weather_cache[cache_key] = None
            return None
        nearest = min(
            forecasts,
            key=lambda item: abs(datetime.fromtimestamp(item.get("dt", 0), timezone.utc) - kickoff),
        )
        forecast_time = datetime.fromtimestamp(nearest.get("dt", 0), timezone.utc)
        if abs((forecast_time - kickoff).total_seconds()) > 4 * 3600:
            self._weather_cache[cache_key] = None
            return None
        weather_items = nearest.get("weather") or [{}]
        result = {
            "status": "ok",
            "forecast_at": forecast_time.isoformat(),
            "temperature_c": nearest.get("main", {}).get("temp"),
            "wind_mps": nearest.get("wind", {}).get("speed"),
            "rain_3h_mm": nearest.get("rain", {}).get("3h", 0.0),
            "snow_3h_mm": nearest.get("snow", {}).get("3h", 0.0),
            "description": weather_items[0].get("description"),
        }
        self._weather_cache[cache_key] = result
        return result


def _candidate_rank(candidate: ChallengeCandidate) -> tuple[float, float, float]:
    validation_improvement = (
        candidate.validation.relative_improvement
        if candidate.validation and candidate.validation.relative_improvement is not None
        else -1.0
    )
    return (
        candidate.conservative_probability,
        candidate.evidence_score,
        validation_improvement,
    )


def scan_daily_challenge(
    provider: ChallengeDataProvider,
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
) -> dict[str, Any]:
    """Run one explicit, quota-aware daily challenge scan."""
    fixtures: list[dict[str, Any]] = []
    histories: dict[int, list[dict[str, Any]]] = {}
    coverage: dict[int, dict[str, bool]] = {}
    seasons: dict[int, int] = {}

    for league_id in league_ids:
        season = current_season_start_year_for_id(league_id, search_date)
        seasons[league_id] = season
        upcoming = provider.upcoming_fixtures(league_id, season, search_date)
        if upcoming is None:
            continue
        fixtures.extend(upcoming)
        if upcoming:
            history = provider.completed_history(league_id, season, upcoming)
            histories[league_id] = history or []
            coverage[league_id] = provider.coverage(league_id, season)

    fixtures.sort(key=lambda item: item.get("fixture", {}).get("date", ""))
    fixtures = fixtures[:max_fixtures]
    fixture_ids = {fixture.get("fixture", {}).get("id") for fixture in fixtures}
    fixtures = [fixture for fixture in fixtures if isinstance(fixture.get("fixture", {}).get("id"), int)]

    validations = {
        league_id: _cached_market_validation(
            league_id,
            seasons[league_id],
            history,
        )
        for league_id, history in histories.items()
        if history
    }
    all_candidates: list[ChallengeCandidate] = []
    for fixture in fixtures:
        league_id = fixture.get("league", {}).get("id")
        all_candidates.extend(
            build_fixture_candidates(
                fixture,
                histories.get(league_id, []),
                validations.get(league_id, {}),
            )
        )

    base_candidates = [candidate for candidate in all_candidates if candidate.base_eligible]
    best_by_fixture: dict[int, ChallengeCandidate] = {}
    for candidate in base_candidates:
        current = best_by_fixture.get(candidate.fixture_id)
        if current is None or _candidate_rank(candidate) > _candidate_rank(current):
            best_by_fixture[candidate.fixture_id] = candidate
    context_fixture_ids = [
        candidate.fixture_id
        for candidate in sorted(best_by_fixture.values(), key=_candidate_rank, reverse=True)[:MAX_CONTEXT_FIXTURES]
    ]
    injuries = provider.injuries_by_fixture(context_fixture_ids) if context_fixture_ids else {}
    details = provider.details_by_fixture(context_fixture_ids) if context_fixture_ids else {}
    fixture_by_id = {
        fixture["fixture"]["id"]: fixture
        for fixture in fixtures
        if fixture.get("fixture", {}).get("id") in fixture_ids
    }
    h2h_by_fixture: dict[int, Optional[list[dict[str, Any]]]] = {}
    weather_by_fixture: dict[int, Optional[dict[str, Any]]] = {}
    for fixture_id in context_fixture_ids:
        fixture = fixture_by_id[fixture_id]
        teams = fixture.get("teams", {})
        h2h_by_fixture[fixture_id] = provider.h2h(
            teams.get("home", {}).get("id"),
            teams.get("away", {}).get("id"),
        )
        weather_by_fixture[fixture_id] = provider.weather(fixture)

    contextualized: list[ChallengeCandidate] = []
    for candidate in base_candidates:
        if candidate.fixture_id not in context_fixture_ids:
            candidate.context = {
                "passed": False,
                "blocked_reasons": ["Nicht in der begrenzten Kontext-Shortlist"],
            }
            contextualized.append(candidate)
            continue
        detail = details.get(candidate.fixture_id) or {}
        league_coverage = coverage.get(candidate.league_id, {})
        apply_candidate_context(
            candidate,
            h2h_fixtures=h2h_by_fixture.get(candidate.fixture_id),
            injuries=injuries.get(candidate.fixture_id),
            injury_coverage=bool(league_coverage.get("injuries")),
            weather=weather_by_fixture.get(candidate.fixture_id),
            lineups=detail.get("lineups") if isinstance(detail, dict) else None,
        )
        contextualized.append(candidate)

    shortlist = select_shortlist(contextualized, max_candidates=6)
    model_ticket = select_model_ticket(shortlist)
    blocked_counts: dict[str, int] = {}
    for candidate in all_candidates:
        reasons = candidate.blocked_reasons or candidate.context.get("blocked_reasons", [])
        for reason in set(reasons):
            blocked_counts[reason] = blocked_counts.get(reason, 0) + 1
    return {
        "version": CHALLENGE_SNAPSHOT_VERSION,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "scope": _scope_signature(league_ids, search_date, max_fixtures),
        "search_date": search_date.isoformat(),
        "fixtures_found": len(fixtures),
        "fixtures_modeled": len({candidate.fixture_id for candidate in all_candidates}),
        "base_candidates": len(base_candidates),
        "context_fixtures": len(context_fixture_ids),
        "approved_candidates": len([candidate for candidate in contextualized if candidate.eligible]),
        "shortlist": shortlist,
        "model_ticket": model_ticket,
        "blocked_counts": blocked_counts,
        "errors": list(provider.errors),
    }


def _render_progress(ledger: ChallengeLedger) -> dict[str, Any]:
    settings = ledger.settings()
    current = settings["current_balance"]
    target = settings["target_balance"]
    start = settings["starting_balance"]
    progress = 1.0 if target <= start and current >= target else (current - start) / max(target - start, 0.01)
    progress = max(0.0, min(1.0, progress))
    values = (
        ("Guthaben", _format_euro(current)),
        ("Ziel", _format_euro(target)),
        ("Noch offen", _format_euro(max(0.0, target - current))),
        ("Max. Einsatz", _format_euro(current * MAX_STAKE_FRACTION)),
    )
    stats_html = "".join(
        '<div class="bb-challenge-stat">'
        f'<div class="bb-challenge-label">{label}</div>'
        f'<div class="bb-challenge-value">{value}</div>'
        "</div>"
        for label, value in values
    )
    st.markdown(
        f'<div class="bb-challenge-grid">{stats_html}</div>',
        unsafe_allow_html=True,
    )
    st.progress(progress)
    return settings


def _render_account(ledger: ChallengeLedger, settings: dict[str, Any]) -> None:
    st.subheader("Challenge-Konto")
    balance = st.number_input(
        "Guthaben korrigieren",
        min_value=0.0,
        value=float(settings["current_balance"]),
        step=10.0,
        format="%.2f",
        key="challenge_balance_input",
    )
    actions = st.columns(2)
    if actions[0].button("Aktuelles Guthaben setzen", width="stretch"):
        try:
            ledger.set_balance(balance)
            st.success("Guthaben aktualisiert.")
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
    if actions[1].button("Startwert und Guthaben setzen", width="stretch"):
        try:
            ledger.set_balance(balance, reset_start=True)
            st.success("Start- und aktuelles Guthaben wurden gesetzt.")
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
    st.caption(
        "Das Ziel bleibt 15.000 €. Es gibt höchstens ein Ticket pro Tag, keine Einsatzverdopplung "
        "nach Verlusten und höchstens 2 % Fractional-Kelly pro Ticket."
    )


def _render_history(ledger: ChallengeLedger) -> None:
    tickets = ledger.tickets()
    if not tickets:
        st.info("Noch kein Challenge-Ticket eingetragen.")
        return
    frame = pd.DataFrame(
        [
            {
                "ID": ticket["id"],
                "Datum": ticket["analysis_date"],
                "Status": ticket["status"],
                "Legs": len(ticket["legs"]),
                "Quote": round(ticket["total_odds"], 2),
                "Einsatz €": ticket["stake"],
                "Auszahlung €": ticket["payout"],
            }
            for ticket in tickets
        ]
    )
    st.dataframe(frame, width="stretch", hide_index=True)

    pending = ledger.pending_tickets()
    if not pending:
        return
    selected_id = st.selectbox(
        "Offenes Ticket",
        [ticket["id"] for ticket in pending],
        format_func=lambda ticket_id: next(
            f"#{ticket['id']} | {ticket['analysis_date']} | {ticket['total_odds']:.2f}"
            for ticket in pending
            if ticket["id"] == ticket_id
        ),
        key="challenge_pending_ticket",
    )
    result = _segmented(
        "Abrechnung",
        ["Gewonnen", "Verloren", "Storniert"],
        "challenge_settlement",
        "Gewonnen",
    )
    if st.button("Ticket abrechnen", type="primary", width="stretch"):
        status = {"Gewonnen": "WON", "Verloren": "LOST", "Storniert": "VOID"}[result]
        try:
            ledger.settle_ticket(selected_id, status)
            st.success("Ticket abgerechnet.")
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))


def _shortlist_frame(shortlist: list[ChallengeCandidate]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Match": f"{candidate.home_team} vs {candidate.away_team}",
                "Markt": candidate.market,
                "Auswahl": candidate.selection,
                "Modell %": round(candidate.probability * 100, 1),
                "Konservativ %": round(candidate.conservative_probability * 100, 1),
                "Evidenz": candidate.evidence_score,
                "Modellpreis": round(candidate.model_price, 2),
            }
            for candidate in shortlist
        ]
    )


def _render_candidate_context(candidate: ChallengeCandidate) -> None:
    context = candidate.context
    h2h = context.get("h2h", {})
    injuries = context.get("injuries", {})
    weather = context.get("weather", {})
    checks = st.columns(4)
    h2h_hits = h2h.get("hits")
    h2h_value = (
        f"{h2h_hits}/{h2h.get('matches', 0)}"
        if h2h_hits is not None
        else f"geprüft ({h2h.get('matches', 0)})"
    )
    checks[0].metric(
        "H2H",
        h2h_value,
    )
    checks[1].metric(
        "Ausfälle H/A",
        f"{injuries.get('home_missing', 0)}/{injuries.get('away_missing', 0)}",
    )
    checks[2].metric(
        "Wetter",
        f"{weather.get('temperature_c', 'n/a')} °C",
    )
    checks[3].metric("Modellpreis", f"{candidate.model_price:.2f}")


def _render_price_check(
    snapshot: dict[str, Any],
    ledger: ChallengeLedger,
    settings: dict[str, Any],
) -> None:
    shortlist: list[ChallengeCandidate] = snapshot["shortlist"]
    if not shortlist:
        st.warning("0 Tipps: Kein Kandidat hat heute alle Modell- und Kontext-Gates bestanden.")
        if snapshot.get("blocked_counts"):
            audit = pd.DataFrame(
                [
                    {"Blocker": reason, "Kandidaten": count}
                    for reason, count in sorted(
                        snapshot["blocked_counts"].items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:10]
                ]
            )
            st.dataframe(audit, width="stretch", hide_index=True)
        return

    st.subheader("Modell-Shortlist")
    st.dataframe(_shortlist_frame(shortlist), width="stretch", hide_index=True)
    preview = snapshot.get("model_ticket") or ()
    if preview:
        preview_text = " + ".join(
            f"{candidate.home_team} vs {candidate.away_team}: {candidate.selection}"
            for candidate in preview
        )
        preview_price = (
            math.prod(candidate.model_price for candidate in preview)
            / (CROSS_LEG_MODEL_FACTOR ** max(0, len(preview) - 1))
        )
        st.info(f"Quotenfreie Modellkombination: {preview_text} | Modellpreis {preview_price:.2f}")

    st.subheader("N1Bet-Preisprüfung")
    st.caption(
        "Die Preise werden erst jetzt manuell ergänzt. Eine niedrige Quote erhöht keine "
        "Modellwahrscheinlichkeit; ein negativer Einzel- oder Ticket-EV sperrt die Auswahl."
    )
    odds_by_candidate: dict[str, float] = {}
    for index, candidate in enumerate(shortlist, start=1):
        st.markdown(
            f"**{index}. {candidate.home_team} vs {candidate.away_team}**  \n"
            f"{candidate.market}: {candidate.selection}"
        )
        _render_candidate_context(candidate)
        odds_by_candidate[candidate.candidate_id] = st.number_input(
            "Aktuelle N1Bet-Quote",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.01,
            format="%.2f",
            key=f"challenge_odds_{candidate.candidate_id}",
            help="0 bedeutet: Markt nicht verfügbar. Die Quote ist nur Preis, kein Sicherheitsmaß.",
        )
        st.divider()

    if st.button(
        "N1Bet-Preise prüfen",
        type="primary",
        width="stretch",
        key="challenge_check_quotes",
    ):
        ticket = select_quoted_ticket(shortlist, odds_by_candidate)
        st.session_state["challenge_quote_result"] = {
            "snapshot_time": snapshot["scanned_at"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ticket": ticket,
        }
        if ticket is None:
            st.warning("Keine Kombination erfüllt Zielquote, Einzel-Value und Mindest-EV gemeinsam.")

    quote_result = st.session_state.get("challenge_quote_result")
    if not isinstance(quote_result, dict) or quote_result.get("snapshot_time") != snapshot["scanned_at"]:
        return
    ticket = quote_result.get("ticket")
    if ticket is None:
        return
    checked_at = datetime.fromisoformat(quote_result["checked_at"])
    quote_age = (datetime.now(timezone.utc) - checked_at.astimezone(timezone.utc)).total_seconds() / 60.0
    stale = quote_age > QUOTE_MAX_AGE_MINUTES

    st.subheader("Finales Ticket")
    ticket_metrics = st.columns(4)
    ticket_metrics[0].metric("Spiele", len(ticket.legs))
    ticket_metrics[1].metric("Gesamtquote", f"{ticket.total_odds:.2f}")
    ticket_metrics[2].metric("Konservativ", f"{ticket.joint_probability * 100:.1f} %")
    ticket_metrics[3].metric("Modell-EV", f"{ticket.expected_roi * 100:.1f} %")
    final_rows = [
        {
            "Match": f"{leg.candidate.home_team} vs {leg.candidate.away_team}",
            "Empfehlung": f"{leg.candidate.market}: {leg.candidate.selection}",
            "N1Bet": round(leg.odds, 2),
            "Konservativ %": round(leg.candidate.conservative_probability * 100, 1),
        }
        for leg in ticket.legs
    ]
    st.dataframe(pd.DataFrame(final_rows), width="stretch", hide_index=True)
    if len(ticket.legs) > 1:
        st.caption(
            f"Zusätzlicher Kombi-Modellfehlerabschlag: Faktor {ticket.model_dependency_factor:.3f}."
        )
    stake = ticket_stake(ticket, settings["current_balance"])
    st.info(
        f"Einsatz nach 1/4-Kelly und 2-%-Kappe: {stake:.2f} €. "
        f"Mögliche Auszahlung: {stake * ticket.total_odds:.2f} €."
    )
    if stale:
        st.warning("Die manuell geprüften N1Bet-Preise sind älter als 10 Minuten. Erneut prüfen.")
        return
    if stake <= 0:
        st.warning("Kein verfügbares Guthaben für einen Einsatz.")
        return
    if st.button(
        f"Ticket mit {stake:.2f} € eintragen",
        width="stretch",
        key="challenge_place_ticket",
    ):
        try:
            ticket_id = ledger.place_ticket(
                snapshot["search_date"],
                ticket,
                stake,
                quote_result["checked_at"],
            )
            st.session_state.pop("challenge_quote_result", None)
            st.success(f"Ticket #{ticket_id} eingetragen.")
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))


def _render_analysis(ledger: ChallengeLedger, settings: dict[str, Any]) -> None:
    config = load_app_config(st)
    if not config.api_football_key:
        st.error("API-Football-Key fehlt.")
        return
    if not config.weather_key:
        st.warning("Wetter-Key fehlt. Der strikte Kontext-Gate wird daher keine Tipps freigeben.")

    controls = st.columns(2)
    with controls[0]:
        date_mode = _segmented(
            "Spieltag",
            ["Heute", "Morgen"],
            "challenge_date_mode",
            "Heute",
        )
    search_date = datetime.now().date() if date_mode == "Heute" else (datetime.now() + timedelta(days=1)).date()
    max_fixtures = controls[1].slider(
        "Max. analysierte Spiele",
        3,
        12,
        8,
        key="challenge_max_fixtures",
        help="Begrenzt Provider-Aufrufe und Kontextprüfungen; final bleiben höchstens drei Spiele.",
    )

    available_ids = list(ALTERNATIVE_MARKET_LEAGUES)
    favorites = [league_id for league_id in DEFAULT_CHALLENGE_LEAGUES if league_id in available_ids]
    league_scope = _segmented(
        "Ligen",
        ["Favoriten", "Auswahl", "Alle"],
        "challenge_league_scope",
        "Favoriten",
    )
    if league_scope == "Favoriten":
        selected_leagues = favorites
        st.caption(", ".join(ALTERNATIVE_MARKET_LEAGUES[item] for item in selected_leagues))
    elif league_scope == "Alle":
        selected_leagues = available_ids
        st.caption(f"{len(selected_leagues)} Ligen; dieser Scan benötigt entsprechend mehr Provider-Aufrufe.")
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_ids,
            default=favorites,
            format_func=lambda league_id: ALTERNATIVE_MARKET_LEAGUES.get(league_id, str(league_id)),
            key="challenge_selected_leagues",
        )

    if st.button(
        "Tagesanalyse starten",
        type="primary",
        width="stretch",
        key="run_challenge_scan",
    ):
        if not selected_leagues:
            st.warning("Mindestens eine Liga auswählen.")
        else:
            try:
                provider = ChallengeDataProvider(config.api_football_key, config.weather_key)
                with st.spinner("Quotenfreie Modelle, Validierung und Kontext werden geprüft..."):
                    st.session_state["challenge_snapshot"] = scan_daily_challenge(
                        provider,
                        selected_leagues,
                        search_date,
                        max_fixtures,
                    )
                st.session_state.pop("challenge_quote_result", None)
            except Exception as exc:
                st.error(f"Challenge-Analyse fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("challenge_snapshot")
    if not isinstance(snapshot, dict):
        st.info("Noch kein Challenge-Snapshot in dieser Sitzung.")
        return
    if snapshot.get("version") != CHALLENGE_SNAPSHOT_VERSION:
        st.warning("Dieser Snapshot stammt aus einer älteren App-Version. Neu analysieren.")
        return
    current_scope = _scope_signature(selected_leagues, search_date, max_fixtures)
    if snapshot.get("scope") != current_scope:
        st.warning("Datum, Liga oder Scanlimit wurden seit dem Snapshot geändert. Neu analysieren.")
        return

    st.caption(f"Snapshot: {_format_time(snapshot.get('scanned_at'))}")
    counts = st.columns(4)
    counts[0].metric("Gefunden", snapshot["fixtures_found"])
    counts[1].metric("Modelliert", snapshot["fixtures_modeled"])
    counts[2].metric("Kontext geprüft", snapshot["context_fixtures"])
    counts[3].metric("Freigegeben", snapshot["approved_candidates"])
    if snapshot.get("errors"):
        st.warning(
            f"{len(snapshot['errors'])} Provider- oder Coverage-Prüfungen waren unvollständig; "
            "betroffene Kandidaten wurden nicht freigegeben."
        )
        st.dataframe(
            pd.DataFrame(
                {"Provider-Meldung": snapshot["errors"][:8]}
            ),
            width="stretch",
            hide_index=True,
        )
    _render_price_check(snapshot, ledger, settings)


def render_challenge_15k() -> None:
    """Render the complete challenge workspace."""
    ledger = _challenge_ledger()
    settings = _render_progress(ledger)
    st.caption(
        "Tageszielquote 2,00-3,00 | maximal drei verschiedene Spiele | "
        "Buchmacherpreise erst nach der Modellfreigabe"
    )
    mode = _segmented(
        "Challenge-Bereich",
        ["Analyse", "Verlauf", "Konto"],
        "challenge_workspace",
        "Analyse",
    )
    if mode == "Analyse":
        _render_analysis(ledger, settings)
    elif mode == "Verlauf":
        _render_history(ledger)
    else:
        _render_account(ledger, settings)

    st.divider()
    st.caption(
        "Aktiv freigabefähig: Endergebnis, doppelte Chance, BTTS, Gesamt- und Teamtore, "
        "ausgewählte kombinierte Torwetten, Eckbälle und gelbe Karten. Jeder Markt benötigt sein "
        "eigenes Walk-forward-Gate. Early Payout, Ganzzahl-Handicaps und Halbzeitmärkte bleiben ausgeschlossen."
    )


__all__ = ["ChallengeDataProvider", "render_challenge_15k", "scan_daily_challenge"]
