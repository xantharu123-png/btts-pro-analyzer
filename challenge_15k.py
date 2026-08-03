"""Responsive 15K challenge workspace with strict model and price gates."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path
import time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import scan_jobs

from api_budget import (
    APIBudgetError,
    APIBudgetPriority,
    api_football_get,
)
from betting_math import minimum_acceptable_odds
from challenge_engine import (
    ChallengeCandidate,
    COUNT_MARKET_KINDS,
    MARKET_BY_KEY,
    MAX_CHALLENGE_STAKE_FRACTION,
    MIN_LEG_EXPECTED_ROI,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    MarketSpec,
    apply_candidate_context,
    build_fixture_candidates,
    consecutive_wins_to_target,
    expected_log_growth,
    extract_lineup_display,
    fit_market_calibration,
    market_outcome,
    market_specs,
    select_model_ticket,
    select_quoted_ticket,
    select_shortlist,
    risk_managed_ticket_stake,
    ticket_stake,
    ticket_dependency_factor,
    validate_league_markets,
)
from challenge_store import ChallengeLedger
from config_loader import load_app_config
from ui_components import (
    milestone_bar_html,
    plain_german,
    render_empty_state,
    scan_progress_fragment,
)
from football_data_history import fetch_history as fetch_stat_history
from football_data_history import merge_api_tail
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from price_ledger import (
    PriceLedger,
    PriceLedgerError,
    PriceLedgerIntegrityError,
    PriceQuote,
)
from season_utils import current_season_start_year_for_id
from xg_backfill import annotate_history as annotate_history_xg


CHALLENGE_SNAPSHOT_VERSION = 5
CHALLENGE_WORKSPACE_VERSION = 5
CHALLENGE_TIMEZONE = ZoneInfo("Europe/Zurich")
DEFAULT_CHALLENGE_LEAGUES = (78, 39, 140, 135, 61)  # xG-validierte Top-5-Ligen
API_TAIL_DAYS = 7  # Frische-Tail: API-FT-Ergebnisse über die CSV-Historie legen
MIN_HISTORY_GAMES = 220  # darunter wird die Vorsaison vorangestellt (Cold-Start)
MAX_CONTEXT_FIXTURES = 20
MAX_DISCOVERY_MARKETS_PER_FIXTURE = 8
# Safety-Ventil, kein Modell-Limit: Alle gültigen Provider-Fixtures der
# gewählten Ligen werden modelliert. Die zusätzlichen Pflichtkontext-Checks
# bleiben über MAX_CONTEXT_FIXTURES gedeckelt.
MAX_SCAN_FIXTURES = 400
QUOTE_MAX_AGE_MINUTES = 10
SNAPSHOT_MAX_AGE_MINUTES = 20
XG_MAX_NEW_CALLS_PER_SCAN = 12
# Auto-Nachprüfung: Die App wartet selbst auf frischen Pflichtkontext
# (H2H-Lage, Ausfälle, Wetter und bestätigte Startaufstellungen), statt dass
# der Nutzer den ganzen Tag manuell neu scannt. Läuft nur, solange die Seite
# offen ist und noch kein Kandidat freigegeben wurde.
AUTO_RECHECK_WINDOW_MINUTES = 80
AUTO_RECHECK_MIN_GAP_MINUTES = 12
AUTO_RECHECK_POLL_SECONDS = 180
MAX_AUTO_RECHECK_LEAGUES = 12


def _challenge_today(now: Optional[datetime] = None) -> date:
    """Return the current calendar date in the challenge timezone.

    Provider requests use ``timezone=Europe/Zurich``; the search date must be
    derived from the same zone, otherwise a UTC server picks the wrong match
    day between 00:00 and 02:00 Swiss time.
    """
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return reference.astimezone(CHALLENGE_TIMEZONE).date()


def _positive_integer(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _fixture_kickoff(fixture: dict[str, Any]) -> Optional[datetime]:
    fixture_data = fixture.get("fixture")
    if not isinstance(fixture_data, dict):
        return None
    try:
        kickoff = datetime.fromisoformat(str(fixture_data.get("date")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if kickoff.tzinfo is None:
        return None
    return kickoff.astimezone(timezone.utc)


def _valid_upcoming_fixture(value: Any, expected_league_id: int) -> bool:
    if not isinstance(value, dict):
        return False
    fixture_data = value.get("fixture")
    league = value.get("league")
    teams = value.get("teams")
    if not all(isinstance(item, dict) for item in (fixture_data, league, teams)):
        return False
    home = teams.get("home")
    away = teams.get("away")
    if not isinstance(home, dict) or not isinstance(away, dict):
        return False
    fixture_id = _positive_integer(fixture_data.get("id"))
    league_id = _positive_integer(league.get("id"))
    home_id = _positive_integer(home.get("id"))
    away_id = _positive_integer(away.get("id"))
    if None in (fixture_id, league_id, home_id, away_id):
        return False
    if league_id != expected_league_id or home_id == away_id:
        return False
    home_name = home.get("name")
    away_name = away.get("name")
    if (
        not isinstance(home_name, str)
        or not home_name.strip()
        or not isinstance(away_name, str)
        or not away_name.strip()
    ):
        return False
    return _fixture_kickoff(value) is not None


def _validate_scan_inputs(
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
) -> None:
    if not isinstance(league_ids, list) or not league_ids:
        raise ValueError("league_ids must be a non-empty list")
    if any(_positive_integer(league_id) is None for league_id in league_ids):
        raise ValueError("league_ids must contain only positive integer IDs")
    if len(set(league_ids)) != len(league_ids):
        raise ValueError("league_ids must not contain duplicates")
    if not isinstance(search_date, date) or isinstance(search_date, datetime):
        raise ValueError("search_date must be a date")
    if (
        isinstance(max_fixtures, bool)
        or not isinstance(max_fixtures, int)
        or not 1 <= max_fixtures <= MAX_SCAN_FIXTURES
    ):
        raise ValueError(
            f"max_fixtures must be an integer between 1 and {MAX_SCAN_FIXTURES}"
        )


def _segmented(label: str, options: list[str], key: str, default: str) -> str:
    if hasattr(st, "segmented_control"):
        kwargs: dict[str, Any] = {
            "key": key,
            "selection_mode": "single",
        }
        if key not in st.session_state:
            kwargs["default"] = default
        value = st.segmented_control(label, options, **kwargs)
        return value or default
    index = None if key in st.session_state else options.index(default)
    return st.radio(label, options, index=index, horizontal=True, key=key) or default


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


CHALLENGE_SESSIONS_DIR = Path(__file__).resolve().parent / "challenge_sessions"


@st.cache_resource
def _challenge_ledger(session_scope: str) -> ChallengeLedger:
    """Keep public Streamlit sessions out of each other's bankroll."""
    account_id = hashlib.sha256(session_scope.encode("utf-8")).hexdigest()[:24]
    CHALLENGE_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return ChallengeLedger(CHALLENGE_SESSIONS_DIR / f"{account_id}.db")


def _challenge_job_key() -> str:
    scope = scan_jobs.session_scope(st.session_state)
    return scan_jobs.scoped_key("challenge_15k", scope)


@st.cache_data(ttl=6 * 3600, max_entries=32, show_spinner=False)
def _cached_market_validation(
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
):
    """Cache expensive walk-forward results; history content is part of the key."""
    del league_id, season
    return validate_league_markets(history)


@st.cache_data(ttl=6 * 3600, max_entries=32, show_spinner=False)
def _cached_market_calibration(
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
):
    """Kalibrierungskarten pro Liga; Cache-Schlüssel ist der Historieninhalt."""
    del league_id, season
    return fit_market_calibration(history)


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
        *,
        priority: APIBudgetPriority | str = APIBudgetPriority.RECOMMENDATION,
    ) -> Optional[list[dict[str, Any]]]:
        self._rate_limit()
        try:
            response = api_football_get(
                f"{self.base_url}/{path}",
                headers=self.headers,
                params=params,
                timeout=20,
                priority=priority,
                label=label,
            )
            response.raise_for_status()
            payload = response.json()
        except (APIBudgetError, requests.RequestException, ValueError) as exc:
            self.errors.append(f"{label}: {exc}")
            return None
        if not isinstance(payload, dict):
            self.errors.append(f"{label}: ungültige Provider-Antwort")
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
        if any(not isinstance(item, dict) for item in data):
            self.errors.append(f"{label}: ungültige Einträge in der Provider-Antwort")
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

    def recent_ft_results(
        self,
        league_id: int,
        season: int,
        from_date: date,
        to_date: date,
    ) -> Optional[list[dict[str, Any]]]:
        """Endstände der letzten Tage aus API-Football (Frische-Tail für die CSV)."""
        return self._football_get(
            "fixtures",
            {
                "league": league_id,
                "season": season,
                "status": "FT",
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "timezone": "Europe/Zurich",
            },
            f"FT-Tail Liga {league_id}",
            priority=APIBudgetPriority.BACKGROUND,
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
            today = datetime.now(CHALLENGE_TIMEZONE).date()
            tail = self.recent_ft_results(
                league_id,
                season,
                today - timedelta(days=API_TAIL_DAYS),
                today,
            )
            history = (
                merge_api_tail(statistical_history, tail, tail_days=API_TAIL_DAYS)
                if tail
                else list(statistical_history)
            )
        else:
            history = self._football_get(
                "fixtures",
                {"league": league_id, "season": season, "status": "FT"},
                f"Historie Liga {league_id}",
                priority=APIBudgetPriority.BACKGROUND,
            ) or []
        if (
            len(history) < MIN_HISTORY_GAMES
            and isinstance(season, int)
            and not isinstance(season, bool)
            and season > 2020
        ):
            # Cold-Start-Schutz: bei dünner Saison (Saisonstart, kleine Ligen)
            # die Vorsaison voranstellen, sonst erreicht die Validierung nie
            # genügend Walk-forward-Beobachtungen.
            previous = fetch_stat_history(league_id, season - 1, upcoming_fixtures)
            if not previous:
                previous = self._football_get(
                    "fixtures",
                    {"league": league_id, "season": season - 1, "status": "FT"},
                    f"Vorsaison Liga {league_id}",
                    priority=APIBudgetPriority.BACKGROUND,
                )
            if previous:
                history = list(previous) + list(history)
        return history or None

    def coverage(self, league_id: int, season: int) -> dict[str, bool]:
        data = self._football_get(
            "leagues",
            {"id": league_id, "season": season},
            f"Coverage Liga {league_id}",
        )
        if not data:
            return {"injuries": False, "lineups": False}
        seasons = data[0].get("seasons") or []
        if not isinstance(seasons, list):
            self.errors.append(f"Coverage Liga {league_id}: ungültige Saisondaten")
            return {"injuries": False, "lineups": False}
        seasons = [item for item in seasons if isinstance(item, dict)]
        season_data = next(
            (
                item
                for item in seasons
                if not isinstance(item.get("year"), bool)
                and item.get("year") == season
            ),
            None,
        )
        if season_data is None:
            self.errors.append(f"Coverage Liga {league_id}: Saison {season} fehlt")
            return {"injuries": False, "lineups": False}
        coverage = season_data.get("coverage") or {}
        if not isinstance(coverage, dict):
            self.errors.append(f"Coverage Liga {league_id}: ungültige Abdeckungsdaten")
            return {"injuries": False, "lineups": False}
        fixtures = coverage.get("fixtures") or {}
        if not isinstance(fixtures, dict):
            fixtures = {}
        return {
            "injuries": coverage.get("injuries") is True,
            "lineups": fixtures.get("lineups") is True,
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
                    if fallback is None:
                        result[fixture_id] = None
                        continue
                    valid_fallback = all(
                        isinstance(entry.get("fixture"), dict)
                        and entry["fixture"].get("id") == fixture_id
                        for entry in fallback
                    )
                    if valid_fallback:
                        result[fixture_id] = fallback
                    else:
                        self.errors.append(
                            f"Verletzungen Fixture {fixture_id}: ungültige Fixture-Zuordnung"
                        )
                        result[fixture_id] = None
                continue
            response_ids = []
            for entry in data:
                fixture_data = entry.get("fixture")
                fixture_id = fixture_data.get("id") if isinstance(fixture_data, dict) else None
                if _positive_integer(fixture_id) is None or fixture_id not in chunk:
                    response_ids = []
                    break
                response_ids.append(fixture_id)
            if data and not response_ids:
                self.errors.append("Verletzungen: ungültige Fixture-Zuordnung")
                for fixture_id in chunk:
                    result[fixture_id] = None
                continue
            for entry, fixture_id in zip(data, response_ids):
                if result[fixture_id] is not None:
                    result[fixture_id].append(entry)
        return result

    def _background_football_get(
        self,
        path: str,
        params: dict[str, Any],
        label: str,
    ) -> Optional[list[dict[str, Any]]]:
        return self._football_get(
            path,
            params,
            label,
            priority=APIBudgetPriority.BACKGROUND,
        )

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
                    if (
                        fallback
                        and len(fallback) == 1
                        and isinstance(fallback[0].get("fixture"), dict)
                        and fallback[0]["fixture"].get("id") == fixture_id
                    ):
                        result[fixture_id] = fallback[0]
                    elif fallback:
                        self.errors.append(
                            f"Fixture-Details {fixture_id}: ungültige Fixture-Zuordnung"
                        )
                continue
            batch_valid = True
            response_ids: set[int] = set()
            for fixture in data:
                fixture_data = fixture.get("fixture")
                fixture_id = fixture_data.get("id") if isinstance(fixture_data, dict) else None
                if (
                    _positive_integer(fixture_id) is None
                    or fixture_id not in chunk
                    or fixture_id in response_ids
                ):
                    batch_valid = False
                    break
                response_ids.add(fixture_id)
            if not batch_valid:
                self.errors.append("Fixture-Details: ungültige Fixture-Zuordnung")
                for fixture_id in chunk:
                    result[fixture_id] = None
                continue
            for fixture in data:
                result[fixture["fixture"]["id"]] = fixture
        return result

    def statistics_by_fixture(self, fixture_id: int) -> Optional[list[dict[str, Any]]]:
        """Team-Statistiken (Ecken, Gelbe Karten) eines Spiels.

        Wird für die Abrechnung von Zählmarkt-Tickets gebraucht: Ohne diesen
        Feed bleiben Ecken-/Karten-Legs bewusst offen, statt auf Toren
        abgerechnet zu werden.
        """
        data = self._football_get(
            "fixtures/statistics",
            {"fixture": fixture_id},
            f"Statistik Fixture {fixture_id}",
        )
        if data is None:
            return None
        valid = all(
            isinstance(entry, dict)
            and isinstance(entry.get("team"), dict)
            and _positive_integer(entry["team"].get("id")) is not None
            and isinstance(entry.get("statistics"), list)
            for entry in data
        )
        if not valid:
            self.errors.append(f"Statistik Fixture {fixture_id}: ungültige Provider-Antwort")
            return None
        return data

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
            if not isinstance(locations, list) or not locations or not isinstance(locations[0], dict):
                self._weather_cache[cache_key] = None
                return None
            latitude = locations[0].get("lat")
            longitude = locations[0].get("lon")
            if (
                isinstance(latitude, bool)
                or isinstance(longitude, bool)
                or not isinstance(latitude, (int, float))
                or not isinstance(longitude, (int, float))
                or not math.isfinite(float(latitude))
                or not math.isfinite(float(longitude))
                or not -90 <= float(latitude) <= 90
                or not -180 <= float(longitude) <= 180
            ):
                self._weather_cache[cache_key] = None
                return None
            forecast_response = requests.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "appid": self.weather_key,
                    "units": "metric",
                    "lang": "de",
                },
                timeout=15,
            )
            forecast_response.raise_for_status()
            forecast_payload = forecast_response.json()
            forecasts = (
                forecast_payload.get("list")
                if isinstance(forecast_payload, dict)
                else None
            )
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            self.errors.append(f"Wetter {city}: {exc}")
            self._weather_cache[cache_key] = None
            return None
        if not isinstance(forecasts, list):
            self.errors.append(f"Wetter {city}: ungültige Provider-Antwort")
            self._weather_cache[cache_key] = None
            return None
        valid_forecasts = []
        for item in forecasts:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("dt")
            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, (int, float))
                or not math.isfinite(float(timestamp))
                or timestamp <= 0
            ):
                continue
            valid_forecasts.append(item)
        if not valid_forecasts:
            self._weather_cache[cache_key] = None
            return None
        nearest = min(
            valid_forecasts,
            key=lambda item: abs(datetime.fromtimestamp(item["dt"], timezone.utc) - kickoff),
        )
        forecast_time = datetime.fromtimestamp(nearest["dt"], timezone.utc)
        if abs((forecast_time - kickoff).total_seconds()) > 4 * 3600:
            self._weather_cache[cache_key] = None
            return None
        main_data = nearest.get("main") if isinstance(nearest.get("main"), dict) else {}
        wind_data = nearest.get("wind") if isinstance(nearest.get("wind"), dict) else {}
        rain_data = nearest.get("rain") if isinstance(nearest.get("rain"), dict) else {}
        snow_data = nearest.get("snow") if isinstance(nearest.get("snow"), dict) else {}
        weather_items = nearest.get("weather")
        weather_item = (
            weather_items[0]
            if isinstance(weather_items, list)
            and weather_items
            and isinstance(weather_items[0], dict)
            else {}
        )
        result = {
            "status": "ok",
            "forecast_at": forecast_time.isoformat(),
            "temperature_c": main_data.get("temp"),
            "wind_mps": wind_data.get("speed"),
            "rain_3h_mm": rain_data.get("3h", 0.0),
            "snow_3h_mm": snow_data.get("3h", 0.0),
            "description": weather_item.get("description"),
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


def _discovery_candidate_pool(
    candidates: list[ChallengeCandidate],
    fixture_ids: list[int],
) -> list[ChallengeCandidate]:
    """Keep a diverse, bounded market pool for later fixture-only refreshes."""
    allowed = set(fixture_ids)
    per_fixture: dict[int, int] = {}
    selected: list[ChallengeCandidate] = []
    for candidate in sorted(candidates, key=_candidate_rank, reverse=True):
        if candidate.fixture_id not in allowed:
            continue
        count = per_fixture.get(candidate.fixture_id, 0)
        if count >= MAX_DISCOVERY_MARKETS_PER_FIXTURE:
            continue
        selected.append(candidate)
        per_fixture[candidate.fixture_id] = count + 1
    return selected


def _ranked_fixture_ids(
    candidates: list[ChallengeCandidate],
    *,
    limit: int = MAX_CONTEXT_FIXTURES,
) -> list[int]:
    """Rank fixtures by their strongest price-independent market."""
    best_by_fixture: dict[int, ChallengeCandidate] = {}
    for candidate in candidates:
        current = best_by_fixture.get(candidate.fixture_id)
        if current is None or _candidate_rank(candidate) > _candidate_rank(current):
            best_by_fixture[candidate.fixture_id] = candidate
    return [
        candidate.fixture_id
        for candidate in sorted(
            best_by_fixture.values(),
            key=_candidate_rank,
            reverse=True,
        )[:limit]
    ]


def _run_challenge_scan_worker(
    provider: "ChallengeDataProvider",
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
    progress_cb=None,
) -> dict[str, Any]:
    """Run the Streamlit-free scan with real phase progress."""
    return scan_daily_challenge(
        provider,
        league_ids,
        search_date,
        max_fixtures,
        progress_cb=progress_cb,
    )


def _candidate_kickoff(candidate: ChallengeCandidate) -> Optional[datetime]:
    """Anpfiff eines Kandidaten als UTC-Datum, sonst None."""
    try:
        kickoff = datetime.fromisoformat(str(candidate.kickoff).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if kickoff.tzinfo is None:
        return None
    return kickoff.astimezone(timezone.utc)


def _auto_recheck_eligible(snapshot: Any, search_date: date) -> bool:
    """Auto-Nachprüfung nur im Wartezustand: nichts freigegeben, aber
    mathematisch tragfähige Kandidaten vorhanden — und nur für heute,
    weil der Live-Kontext erst am Spieltag entsteht."""
    return (
        isinstance(snapshot, dict)
        and not snapshot.get("shortlist")
        and bool(snapshot.get("base_shortlist"))
        and search_date == _challenge_today()
    )


def _auto_recheck_scope_allowed(league_ids: list[int]) -> bool:
    """Keep periodic context rescans within a predictable provider budget."""
    return 0 < len(league_ids) <= MAX_AUTO_RECHECK_LEAGUES


def _auto_recheck_decision(
    base_shortlist: list[ChallengeCandidate],
    now: datetime,
    last_attempt: Optional[datetime],
    seen_fixture_ids: set[int],
) -> dict[str, Any]:
    """Reine Entscheidung: Muss der Kontext-Scan jetzt automatisch neu laufen?

    Feuert, wenn ein Shortlist-Spiel neu ins Kontextfenster gerückt ist
    (Anpfiff innerhalb AUTO_RECHECK_WINDOW_MINUTES) oder wenn Spiele im
    Fenster auf verspätet veröffentlichten Kontext warten und der
    Mindestabstand verstrichen ist. Feuert nie öfter als
    AUTO_RECHECK_MIN_GAP_MINUTES und nie für Spiele nach Anpfiff.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    window_end = now + timedelta(minutes=AUTO_RECHECK_WINDOW_MINUTES)
    grace_start = now - timedelta(minutes=5)
    in_window: set[int] = set()
    next_kickoff: Optional[datetime] = None
    for candidate in base_shortlist:
        kickoff = _candidate_kickoff(candidate)
        if kickoff is None:
            continue
        if grace_start <= kickoff <= window_end:
            in_window.add(candidate.fixture_id)
        elif kickoff > window_end and (next_kickoff is None or kickoff < next_kickoff):
            next_kickoff = kickoff
    gap_ok = (
        last_attempt is None
        or (now - last_attempt) >= timedelta(minutes=AUTO_RECHECK_MIN_GAP_MINUTES)
    )
    decision: dict[str, Any] = {
        "due": False,
        "in_window": in_window,
        "next_kickoff": next_kickoff,
        "reason": "",
    }
    if not in_window:
        decision["reason"] = "Kein Shortlist-Spiel im Kontextfenster."
        return decision
    if not gap_ok:
        decision["reason"] = "Mindestabstand zwischen den Prüfläufen noch nicht erreicht."
        return decision
    if in_window - seen_fixture_ids:
        decision["due"] = True
        decision["reason"] = "Neue Shortlist-Spiele sind ins Kontextfenster gerückt."
        return decision
    decision["due"] = True
    decision["reason"] = "Spiele warten im Fenster auf verspäteten Kontext — Nachprüfung fällig."
    return decision


def _refresh_lineup_displays(provider: "ChallengeDataProvider", snapshot: dict[str, Any]) -> int:
    """Lädt bestätigte Aufstellungen für freigegebene Kandidaten nach.

    Leichtgewichtig: nur Fixture-Details, keine Gates, keine Preise — der
    Snapshot und ein laufender Preis-Check bleiben unverändert. Gibt die
    Zahl der Kandidaten zurück, deren Anzeige neu befüllt wurde.
    """
    shortlist = snapshot.get("shortlist") or []
    pending = [
        candidate
        for candidate in shortlist
        if len(((candidate.context or {}).get("lineups") or {}).get("display") or {}) < 2
    ]
    if not pending:
        return 0
    fixture_ids = sorted({candidate.fixture_id for candidate in pending})
    details = provider.details_by_fixture(fixture_ids)
    updated = 0
    for candidate in pending:
        detail = details.get(candidate.fixture_id)
        if not isinstance(detail, dict):
            continue
        display = extract_lineup_display(
            detail.get("lineups"), candidate.home_team_id, candidate.away_team_id
        )
        if not display:
            continue
        context = candidate.context if isinstance(candidate.context, dict) else {}
        lineups_summary = dict(context.get("lineups") or {})
        lineups_summary["display"] = display
        context["lineups"] = lineups_summary
        candidate.context = context
        updated += 1
    return updated


def _lineup_refresh_tick(
    snapshot: dict[str, Any], api_football_key: str, weather_key: Optional[str]
) -> None:
    """Nach der Freigabe: holt bestätigte Aufstellungen nach, sobald sie
    veröffentlicht sind (ca. 60 Minuten vor Anpfiff). Nur Anzeige —
    Gates, Shortlist und Preise bleiben unberührt."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=5)
    window_end = now + timedelta(minutes=75)
    due = [
        candidate
        for candidate in (snapshot.get("shortlist") or [])
        if len(((candidate.context or {}).get("lineups") or {}).get("display") or {}) < 2
        and (kickoff := _candidate_kickoff(candidate)) is not None
        and window_start <= kickoff <= window_end
    ]
    if not due:
        return
    try:
        last_poll = datetime.fromisoformat(
            str(st.session_state.get("challenge_lineup_poll_at") or "")
        ).astimezone(timezone.utc)
    except (TypeError, ValueError):
        last_poll = None
    if last_poll is not None and (now - last_poll) < timedelta(
        seconds=AUTO_RECHECK_POLL_SECONDS
    ):
        return
    st.session_state["challenge_lineup_poll_at"] = now.isoformat()
    provider = ChallengeDataProvider(api_football_key, weather_key)
    updated = _refresh_lineup_displays(provider, snapshot)
    if updated:
        st.toast("Aufstellungsanzeige aktualisiert; das Pflichtgate war bereits erfüllt.")
        st.rerun()


@st.fragment(run_every=AUTO_RECHECK_POLL_SECONDS)
def _challenge_auto_recheck_fragment(
    api_football_key: str,
    weather_key: Optional[str],
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
) -> None:
    """Wartet an Stelle des Nutzers auf frischen Pflichtkontext.

    Sobald Shortlist-Spiele ins Fenster rutschen, prüft die App H2H,
    Ausfälle, Wetter und bestätigte Startaufstellungen erneut. Das läuft nur,
    solange nichts freigegeben ist und die Seite offen bleibt.
    """
    snapshot = st.session_state.get("challenge_snapshot")
    if not isinstance(snapshot, dict):
        return
    if snapshot.get("shortlist"):
        # Nach der strikten Freigabe ist kein Gate-Rescan mehr nötig. Fehlende
        # Namen/Formation können für die Anzeige nachgeladen werden.
        _lineup_refresh_tick(snapshot, api_football_key, weather_key)
        return
    if not _auto_recheck_eligible(snapshot, search_date):
        return
    if not _auto_recheck_scope_allowed(league_ids):
        st.caption(
            "Der Vollscan wird zum Schutz des API-Kontingents nicht automatisch "
            f"wiederholt. Für automatische Nachprüfungen höchstens "
            f"{MAX_AUTO_RECHECK_LEAGUES} Ligen gezielt auswählen."
        )
        return
    if scan_jobs.get_job(_challenge_job_key()).get("state") == "running":
        return
    now = datetime.now(timezone.utc)
    try:
        last_attempt = datetime.fromisoformat(
            str(st.session_state.get("challenge_auto_recheck_at") or "")
        ).astimezone(timezone.utc)
    except (TypeError, ValueError):
        last_attempt = None
    seen = st.session_state.get("challenge_auto_seen")
    if not isinstance(seen, set):
        seen = set()
    decision = _auto_recheck_decision(
        snapshot["base_shortlist"], now, last_attempt, seen
    )
    if not decision["due"]:
        next_kickoff = decision.get("next_kickoff")
        if next_kickoff is not None:
            st.caption(
                "Auto-Prüfung aktiv: Nächster Shortlist-Anpfiff um "
                f"{next_kickoff.astimezone(CHALLENGE_TIMEZONE).strftime('%H:%M')} — "
                "die App prüft dann selbstständig erneut, solange diese Seite offen bleibt."
            )
        return
    st.session_state["challenge_auto_recheck_at"] = now.isoformat()
    st.session_state["challenge_auto_seen"] = set(decision["in_window"]) | seen
    provider = ChallengeDataProvider(api_football_key, weather_key)
    scan_jobs.start_job(
        _challenge_job_key(),
        _run_challenge_scan_worker,
        args=(provider, list(league_ids), search_date, max_fixtures),
    )
    st.toast("Kontextfenster erreicht — die Shortlist wird automatisch erneut geprüft.")
    st.rerun()


def scan_daily_challenge(
    provider: ChallengeDataProvider,
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
    *,
    progress_cb=None,
) -> dict[str, Any]:
    """Run one explicit, quota-aware daily challenge scan."""
    _validate_scan_inputs(league_ids, search_date, max_fixtures)
    if progress_cb:
        progress_cb(
            0.01,
            f"Scan für {len(league_ids)} Ligen wird vorbereitet",
        )
    fixtures: list[dict[str, Any]] = []
    histories: dict[int, list[dict[str, Any]]] = {}
    coverage: dict[int, dict[str, bool]] = {}
    seasons: dict[int, int] = {}

    league_total = len(league_ids)
    for league_index, league_id in enumerate(league_ids):
        league_name = ALTERNATIVE_MARKET_LEAGUES.get(
            league_id,
            f"Liga {league_id}",
        )
        if progress_cb:
            progress_cb(
                0.03 + 0.45 * league_index / league_total,
                f"Liga {league_index + 1}/{league_total}: {league_name}",
            )
        season = current_season_start_year_for_id(league_id, search_date)
        seasons[league_id] = season
        upcoming = provider.upcoming_fixtures(league_id, season, search_date)
        if upcoming is None:
            continue
        valid_upcoming = [
            fixture
            for fixture in upcoming
            if _valid_upcoming_fixture(fixture, league_id)
        ]
        invalid_count = len(upcoming) - len(valid_upcoming)
        if invalid_count:
            provider.errors.append(
                f"Fixtures Liga {league_id}: {invalid_count} ungültige Einträge verworfen"
            )
        fixtures.extend(valid_upcoming)
        if valid_upcoming:
            history = provider.completed_history(league_id, season, valid_upcoming)
            if history:
                try:
                    xg_stats = annotate_history_xg(
                        history,
                        league_id,
                        season,
                        provider._background_football_get,
                        max_new_calls=XG_MAX_NEW_CALLS_PER_SCAN,
                    )
                    if xg_stats.get("coverage", 0.0) < 0.5:
                        provider.errors.append(
                            f"xG Liga {league_id}: nur {xg_stats.get('annotated', 0)}/"
                            f"{xg_stats.get('total', 0)} Spiele mit xG — Tormodell dominant"
                        )
                except Exception as exc:  # xG ist optional, der Scan läuft ohne weiter
                    provider.errors.append(f"xG Liga {league_id}: Annotation fehlgeschlagen ({exc})")
            histories[league_id] = history or []
            coverage[league_id] = provider.coverage(league_id, season)
        if progress_cb:
            progress_cb(
                0.03 + 0.45 * (league_index + 1) / league_total,
                f"Liga {league_index + 1}/{league_total} geladen",
            )

    if progress_cb:
        progress_cb(0.50, "Spiele werden bereinigt und sortiert")
    fixtures.sort(key=lambda item: _fixture_kickoff(item) or datetime.max.replace(tzinfo=timezone.utc))
    unique_fixtures: list[dict[str, Any]] = []
    seen_fixture_ids: set[int] = set()
    for fixture in fixtures:
        fixture_id = fixture["fixture"]["id"]
        if fixture_id in seen_fixture_ids:
            provider.errors.append(f"Fixture {fixture_id}: doppelter Provider-Eintrag verworfen")
            continue
        seen_fixture_ids.add(fixture_id)
        unique_fixtures.append(fixture)
    fixtures = unique_fixtures
    fixtures = fixtures[:max_fixtures]

    history_items = [
        (league_id, history)
        for league_id, history in histories.items()
        if history
    ]
    validations: dict[int, dict[str, Any]] = {}
    history_total = len(history_items)
    for history_index, (league_id, history) in enumerate(history_items):
        if progress_cb:
            progress_cb(
                0.52 + 0.09 * history_index / max(1, history_total),
                f"Walk-forward-Validierung {history_index + 1}/{history_total}",
            )
        validations[league_id] = _cached_market_validation(
            league_id,
            seasons[league_id],
            history,
        )
    if progress_cb:
        progress_cb(0.61, "Wahrscheinlichkeiten werden kalibriert")
    calibrations: dict[int, dict[str, Any]] = {}
    for history_index, (league_id, history) in enumerate(history_items):
        if progress_cb:
            progress_cb(
                0.61 + 0.09 * history_index / max(1, history_total),
                f"Kalibrierung {history_index + 1}/{history_total}",
            )
        calibrations[league_id] = _cached_market_calibration(
            league_id,
            seasons[league_id],
            history,
        )
    if progress_cb:
        progress_cb(
            0.70,
            f"{len(fixtures)} Spiele werden mathematisch modelliert",
        )
    all_candidates: list[ChallengeCandidate] = []
    fixture_total = len(fixtures)
    progress_stride = max(1, fixture_total // 20)
    for fixture_index, fixture in enumerate(fixtures):
        league_id = fixture.get("league", {}).get("id")
        all_candidates.extend(
            build_fixture_candidates(
                fixture,
                histories.get(league_id, []),
                validations.get(league_id, {}),
                calibrations.get(league_id, {}),
            )
        )
        if progress_cb and (
            (fixture_index + 1) % progress_stride == 0
            or fixture_index + 1 == fixture_total
        ):
            progress_cb(
                0.70 + 0.14 * (fixture_index + 1) / max(1, fixture_total),
                f"Spiel {fixture_index + 1}/{fixture_total} modelliert",
            )

    base_candidates = [candidate for candidate in all_candidates if candidate.base_eligible]
    context_fixture_ids = _ranked_fixture_ids(base_candidates)
    if progress_cb:
        progress_cb(
            0.85,
            f"Live-Kontext für {len(context_fixture_ids)} Top-Spiele",
        )
    injuries = provider.injuries_by_fixture(context_fixture_ids) if context_fixture_ids else {}
    details = provider.details_by_fixture(context_fixture_ids) if context_fixture_ids else {}
    fixture_by_id = {
        fixture["fixture"]["id"]: fixture
        for fixture in fixtures
    }
    h2h_by_fixture: dict[int, Optional[list[dict[str, Any]]]] = {}
    weather_by_fixture: dict[int, Optional[dict[str, Any]]] = {}
    context_total = len(context_fixture_ids)
    for context_index, fixture_id in enumerate(context_fixture_ids):
        if progress_cb:
            progress_cb(
                0.88 + 0.08 * context_index / max(1, context_total),
                f"H2H und Wetter {context_index + 1}/{context_total}",
            )
        fixture = fixture_by_id[fixture_id]
        teams = fixture.get("teams", {})
        h2h_by_fixture[fixture_id] = provider.h2h(
            teams.get("home", {}).get("id"),
            teams.get("away", {}).get("id"),
        )
        weather_by_fixture[fixture_id] = provider.weather(fixture)

    if progress_cb:
        progress_cb(0.96, "Kontextgates werden angewendet")
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
            lineups=(
                detail.get("lineups")
                if isinstance(detail, dict) and league_coverage.get("lineups") is True
                else None
            ),
            require_lineups=True,
        )
        contextualized.append(candidate)

    shortlist = select_shortlist(contextualized, max_candidates=3)
    model_ticket = select_model_ticket(shortlist)
    base_shortlist = sorted(base_candidates, key=_candidate_rank, reverse=True)[:10]
    discovery_candidates = _discovery_candidate_pool(
        base_candidates,
        context_fixture_ids,
    )
    blocked_counts: dict[str, int] = {}
    for candidate in all_candidates:
        reasons = candidate.blocked_reasons or candidate.context.get("blocked_reasons", [])
        for reason in set(reasons):
            blocked_counts[reason] = blocked_counts.get(reason, 0) + 1
    if progress_cb:
        progress_cb(
            1.0,
            f"Fertig: {len(fixtures)} Spiele, {len(shortlist)} Freigaben",
        )
    return {
        "version": CHALLENGE_SNAPSHOT_VERSION,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "scope": _scope_signature(league_ids, search_date, max_fixtures),
        "search_date": search_date.isoformat(),
        "fixture_kickoffs": [
            kickoff.isoformat()
            for kickoff in (
                _fixture_kickoff(fixture)
                for fixture in fixtures
            )
            if kickoff is not None
        ],
        "fixtures_found": len(fixtures),
        "fixtures_modeled": len({candidate.fixture_id for candidate in all_candidates}),
        "base_candidates": len(base_candidates),
        "context_fixtures": len(context_fixture_ids),
        "approved_candidates": len(shortlist),
        "shortlist": shortlist,
        "base_shortlist": base_shortlist,
        "discovery_candidates": discovery_candidates,
        "model_ticket": model_ticket,
        "blocked_counts": blocked_counts,
        "errors": list(provider.errors),
    }


def refresh_discovered_candidates(
    provider: ChallengeDataProvider,
    candidates: list[ChallengeCandidate],
    search_date: date,
    *,
    now: Optional[datetime] = None,
    max_candidates: int = 3,
) -> dict[str, Any]:
    """Refresh only persisted candidate fixtures, never the full league pool."""
    if not isinstance(search_date, date) or isinstance(search_date, datetime):
        raise ValueError("search_date must be a date")
    if (
        isinstance(max_candidates, bool)
        or not isinstance(max_candidates, int)
        or not 1 <= max_candidates <= 6
    ):
        raise ValueError("max_candidates must be an integer between 1 and 6")
    if not isinstance(candidates, list) or any(
        not isinstance(candidate, ChallengeCandidate) for candidate in candidates
    ):
        raise ValueError("candidates must contain ChallengeCandidate objects")

    refreshed = [deepcopy(candidate) for candidate in candidates]
    base_candidates = [
        candidate for candidate in refreshed if candidate.base_eligible
    ]
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    else:
        checked_at = checked_at.astimezone(timezone.utc)
    fixture_ids = _ranked_fixture_ids(base_candidates)
    if not fixture_ids:
        return {
            "checked_at": checked_at.isoformat(),
            "fixture_ids": [],
            "shortlist": [],
            "candidates": [],
            "blocked_counts": {},
            "errors": list(provider.errors),
        }

    details = provider.details_by_fixture(fixture_ids)
    injuries = provider.injuries_by_fixture(fixture_ids)
    coverage: dict[int, dict[str, bool]] = {}
    for candidate in base_candidates:
        if candidate.fixture_id not in fixture_ids or candidate.league_id in coverage:
            continue
        season = current_season_start_year_for_id(candidate.league_id, search_date)
        coverage[candidate.league_id] = provider.coverage(
            candidate.league_id,
            season,
        )

    representative = {
        candidate.fixture_id: candidate
        for candidate in sorted(base_candidates, key=_candidate_rank)
        if candidate.fixture_id in fixture_ids
    }
    h2h_by_fixture: dict[int, Optional[list[dict[str, Any]]]] = {}
    weather_by_fixture: dict[int, Optional[dict[str, Any]]] = {}
    for fixture_id, candidate in representative.items():
        h2h_by_fixture[fixture_id] = provider.h2h(
            candidate.home_team_id,
            candidate.away_team_id,
        )
        detail = details.get(fixture_id)
        weather_by_fixture[fixture_id] = (
            provider.weather(detail) if isinstance(detail, dict) else None
        )

    contextualized: list[ChallengeCandidate] = []
    for candidate in base_candidates:
        if candidate.fixture_id not in fixture_ids:
            continue
        detail = details.get(candidate.fixture_id)
        league_coverage = coverage.get(candidate.league_id, {})
        apply_candidate_context(
            candidate,
            h2h_fixtures=h2h_by_fixture.get(candidate.fixture_id),
            injuries=injuries.get(candidate.fixture_id),
            injury_coverage=bool(league_coverage.get("injuries")),
            weather=weather_by_fixture.get(candidate.fixture_id),
            lineups=(
                detail.get("lineups")
                if isinstance(detail, dict)
                and league_coverage.get("lineups") is True
                else None
            ),
            now=checked_at,
            require_lineups=True,
        )
        contextualized.append(candidate)

    shortlist = select_shortlist(
        contextualized,
        max_candidates=max_candidates,
    )
    blocked_counts: dict[str, int] = {}
    for candidate in contextualized:
        reasons = candidate.blocked_reasons or candidate.context.get(
            "blocked_reasons",
            [],
        )
        for reason in set(reasons):
            blocked_counts[reason] = blocked_counts.get(reason, 0) + 1
    return {
        "checked_at": checked_at.isoformat(),
        "fixture_ids": fixture_ids,
        "shortlist": shortlist,
        "candidates": contextualized,
        "blocked_counts": blocked_counts,
        "errors": list(provider.errors),
    }


# Zählmarkt-Abrechnung: Ecken/Gelbe Karten kommen aus fixtures/statistics,
# NICHT aus dem Endstand. Dieselben Obergrenzen wie beim Historien-Import.
_COUNT_STAT_BOUNDS = {"corners": 40, "yellow_cards": 20}
_COUNT_STAT_TYPES = {"Corner Kicks": "corners", "Yellow Cards": "yellow_cards"}


def _count_stat_value(value: Any, maximum: int) -> Optional[int]:
    """Statistikwert des Providers: strikt nicht-negative ganze Zahl mit Obergrenze."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            return None
        value = int(value)
    if not isinstance(value, int) or not 0 <= value <= maximum:
        return None
    return value


def count_stats_from_response(
    data: Any,
    home_team_id: Any,
    away_team_id: Any,
) -> dict[str, int]:
    """Ecken/Gelbe Karten Heim/Auswärts aus einer fixtures/statistics-Antwort.

    Strikte Team-Zuordnung: genau die beiden erwarteten Teams, jedes genau
    einmal. Bei jeder Unklarheit {} — die Abrechnung bleibt dann offen,
    statt auf falschen Zahlen zu entscheiden.
    """
    home_id = _positive_integer(home_team_id)
    away_id = _positive_integer(away_team_id)
    if home_id is None or away_id is None or home_id == away_id:
        return {}
    if not isinstance(data, list) or len(data) != 2:
        return {}
    result: dict[str, int] = {}
    seen: set[int] = set()
    for entry in data:
        if not isinstance(entry, dict):
            return {}
        team = entry.get("team")
        team_id = team.get("id") if isinstance(team, dict) else None
        if team_id not in {home_id, away_id} or team_id in seen:
            return {}
        seen.add(team_id)
        statistics = entry.get("statistics")
        if not isinstance(statistics, list):
            return {}
        prefix = "home" if team_id == home_id else "away"
        for item in statistics:
            if not isinstance(item, dict):
                continue
            family = _COUNT_STAT_TYPES.get(str(item.get("type")))
            if family is None:
                continue
            parsed = _count_stat_value(item.get("value"), _COUNT_STAT_BOUNDS[family])
            if parsed is not None:
                result[f"{family}_{prefix}"] = parsed
    return result


# Endstand nur über reguläre Spielzeit ("FT"). Verlängerung/Elfmeterschießen
# ("AET"/"PEN") wertet der Buchmacher für 90-Minuten-Märkte anders — diese
# Tickets bleiben zur manuellen Abrechnung offen.
SETTLED_STATUSES = {"FT"}
VOID_STATUSES = {"PST", "CANC", "ABD", "AWD", "WO"}


def _spec_by_market_selection() -> dict[tuple[str, str], MarketSpec]:
    mapping: dict[tuple[str, str], MarketSpec] = {}
    for spec in market_specs():
        mapping.setdefault((spec.market, spec.selection), spec)
    return mapping


def auto_settle_open_tickets(
    ledger: ChallengeLedger,
    provider: ChallengeDataProvider,
    *,
    max_api_calls: int = 10,
) -> dict[str, int]:
    """Settle pending challenge tickets against final API results.

    A loss remains a real loss. AET/PEN results and mixed void/decided tickets
    stay open for manual settlement. Never raises: settlement must not break
    the UI.
    """
    summary = {"won": 0, "lost": 0, "void": 0, "open": 0, "resets": 0}
    try:
        pending = ledger.pending_tickets()
    except Exception:
        return summary
    if not pending:
        return summary
    spec_by_key = _spec_by_market_selection()
    fixture_cache: dict[int, Optional[dict[str, Any]]] = {}
    api_calls = 0

    def fixture_details(fixture_id: int) -> Optional[dict[str, Any]]:
        nonlocal api_calls
        if fixture_id in fixture_cache:
            return fixture_cache[fixture_id]
        if api_calls >= max_api_calls:
            return None
        api_calls += 1
        try:
            data = provider.details_by_fixture([fixture_id])
            fixture_cache[fixture_id] = data.get(fixture_id)
        except Exception:
            fixture_cache[fixture_id] = None
        return fixture_cache[fixture_id]

    stats_cache: dict[int, Optional[dict[str, int]]] = {}

    def count_values(
        fixture_id: int, details: dict[str, Any], kind: str
    ) -> Optional[tuple[int, int]]:
        """Ecken-/Karten-Zählwerte eines FT-Spiels aus der Provider-Statistik.

        Liefert None, wenn der Feed fehlt oder unklar ist — das Leg bleibt
        dann zur manuellen Abrechnung offen, statt auf Toren entschieden
        zu werden.
        """
        nonlocal api_calls
        if fixture_id not in stats_cache:
            if api_calls >= max_api_calls:
                return None
            api_calls += 1
            teams = details.get("teams") or {}
            home_id = _positive_integer((teams.get("home") or {}).get("id"))
            away_id = _positive_integer((teams.get("away") or {}).get("id"))
            cached: Optional[dict[str, int]] = None
            if home_id is not None and away_id is not None:
                try:
                    response = provider.statistics_by_fixture(fixture_id)
                except Exception:
                    response = None
                if response is not None:
                    counts = count_stats_from_response(response, home_id, away_id)
                    cached = counts or None
            stats_cache[fixture_id] = cached
        counts = stats_cache[fixture_id]
        if not counts:
            return None
        if kind in {"corner_total", "team_corners"}:
            pair = (counts.get("corners_home"), counts.get("corners_away"))
        else:
            pair = (counts.get("yellow_cards_home"), counts.get("yellow_cards_away"))
        home_value, away_value = pair
        if home_value is None or away_value is None:
            return None
        return (home_value, away_value)

    for ticket in pending:
        legs = ticket.get("legs") or []
        if not legs:
            summary["open"] += 1
            continue
        leg_wins = 0
        leg_losses = 0
        leg_voids = 0
        undecided = False
        for leg in legs:
            spec = spec_by_key.get(
                (str(leg.get("market", "")), str(leg.get("selection", "")))
            )
            fixture_id = leg.get("fixture_id")
            if spec is None or fixture_id is None:
                undecided = True
                break
            details = fixture_details(int(fixture_id))
            if details is None:
                undecided = True
                break
            fixture_data = details.get("fixture") or {}
            status = str(
                (fixture_data.get("status") or {}).get("short", "")
            ).upper()
            if status in VOID_STATUSES:
                leg_voids += 1
                continue
            if status not in SETTLED_STATUSES:
                undecided = True
                break
            if spec.kind in COUNT_MARKET_KINDS:
                # Zählmärkte (Ecken, Gelbe Karten) werden NUR mit echten
                # Zählwerten aus der Statistik abgerechnet — niemals mit
                # Toren. Fehlt der Feed, bleibt das Leg offen.
                counts = count_values(int(fixture_id), details, spec.kind)
                if counts is None:
                    undecided = True
                    break
                home, away = counts
            else:
                goals = details.get("goals") or {}
                home, away = goals.get("home"), goals.get("away")
                if (
                    isinstance(home, bool)
                    or isinstance(away, bool)
                    or not isinstance(home, int)
                    or not isinstance(away, int)
                ):
                    undecided = True
                    break
            if market_outcome(spec, home, away):
                leg_wins += 1
            else:
                leg_losses += 1
        if undecided:
            summary["open"] += 1
            continue
        try:
            if leg_voids == len(legs):
                ledger.settle_ticket(int(ticket["id"]), "VOID")
                summary["void"] += 1
            elif leg_voids:
                # Gemischt entschieden/storniert: manuelle Abrechnung.
                summary["open"] += 1
            elif leg_losses == 0 and leg_wins == len(legs):
                ledger.settle_ticket(int(ticket["id"]), "WON")
                summary["won"] += 1
            else:
                ledger.settle_ticket(int(ticket["id"]), "LOST")
                summary["lost"] += 1
        except Exception:
            summary["open"] += 1
    return summary


def _auto_settle_feedback(ledger: ChallengeLedger) -> None:
    """Run auto-settlement once per render when tickets are pending."""
    try:
        if not ledger.pending_tickets():
            return
        config = load_app_config(st)
        if not config.api_football_key:
            return
        summary = auto_settle_open_tickets(
            ledger,
            ChallengeDataProvider(config.api_football_key, config.weather_key),
        )
    except Exception:
        return
    if summary.get("lost"):
        st.warning(f"{summary['lost']} Ticket(s) als verloren abgerechnet.")
    if summary.get("won"):
        st.success(f"{summary['won']} Ticket(s) gewonnen und abgerechnet.")
    if summary.get("void"):
        st.info(f"{summary['void']} Ticket(s) storniert — Einsatz zurückgebucht.")


def _render_progress(ledger: ChallengeLedger) -> dict[str, Any]:
    settings = ledger.settings()
    current = settings["current_balance"]
    target = settings["target_balance"]
    start = settings["starting_balance"]
    stake_fraction = settings["stake_fraction"]
    values = (
        ("Guthaben", _format_euro(current)),
        ("Ziel", _format_euro(target)),
        ("Noch offen", _format_euro(max(0.0, target - current))),
        ("Shadow-Einsatz", _format_euro(current * stake_fraction)),
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
    st.markdown(milestone_bar_html(current, target, start), unsafe_allow_html=True)
    wins_needed = consecutive_wins_to_target(current, target, 2.5, stake_fraction)
    if current >= target:
        st.success("Ziel erreicht: 15.000 € sind geknackt.")
    elif wins_needed is not None:
        st.caption(
            f"Rechnerisch: {wins_needed} Gewinne in Folge bei Quote 2,50 "
            f"und {int(round(stake_fraction * 100))} % Roll-over bis zum Ziel. Kein Versprechen, nur Mathematik."
        )
    return settings


def _render_account(ledger: ChallengeLedger, settings: dict[str, Any]) -> None:
    st.subheader("Challenge-Konto")
    stake_percent = st.slider(
        "Einsatzanteil je Ticket (%)",
        min_value=5,
        max_value=int(MAX_CHALLENGE_STAKE_FRACTION * 100),
        value=int(round(settings["stake_fraction"] * 100)),
        step=5,
        key="challenge_stake_percent",
    )
    if st.button(
        "Einsatzanteil speichern",
        type="primary",
        width="stretch",
        key="challenge_save_stake_fraction",
    ):
        try:
            ledger.set_stake_fraction(stake_percent / 100.0)
            st.success("Einsatzanteil aktualisiert.")
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))

    preview_fraction = stake_percent / 100.0
    loss_balance = settings["current_balance"] * (1.0 - preview_fraction)
    wins_at_two = consecutive_wins_to_target(
        settings["current_balance"],
        settings["target_balance"],
        2.0,
        preview_fraction,
    )
    wins_at_three = consecutive_wins_to_target(
        settings["current_balance"],
        settings["target_balance"],
        3.0,
        preview_fraction,
    )
    projection = st.columns(3)
    projection[0].metric(
        "Quote 2,00",
        f"{wins_at_two} Siege" if wins_at_two is not None else "nicht erreichbar",
    )
    projection[1].metric(
        "Quote 3,00",
        f"{wins_at_three} Siege" if wins_at_three is not None else "nicht erreichbar",
    )
    projection[2].metric("Saldo nach Verlust", _format_euro(loss_balance))
    if stake_percent == int(MAX_CHALLENGE_STAKE_FRACTION * 100):
        st.warning(
            "25 % je Ticket ist bereits eine extreme Challenge-Simulation. "
            "Es ist keine professionelle Echtgeld-Einsatzempfehlung."
        )

    st.divider()
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
        "Das Ziel bleibt 15.000 €. Der Einsatzanteil wird immer vom aktuellen Guthaben "
        "berechnet; es gibt keine Martingale-Verdopplung nach Verlusten. Manuelle "
        "Einzahlungen oder Korrekturen werden im Kontobuch ausgewiesen. Ein offenes "
        "Ticket muss vor dem nächsten Ticket abgerechnet sein."
    )

    with st.expander("⚙️ Erweitert — Gefahrenzone"):
        st.caption(
            "Setzt die Challenge komplett zurück: Guthaben und Startwert gehen "
            "zurück auf den Anfang. Die bisherige Ticket-Historie bleibt im "
            "Verlauf erhalten. Nur nutzen, wenn die Challenge wirklich neu "
            "starten soll."
        )
        reset_text = st.text_input(
            'Bestätigung 1 von 2: „RESET" eintippen',
            key="challenge_reset_text",
        )
        reset_check = st.checkbox(
            "Bestätigung 2 von 2: Ich verstehe, dass der aktuelle "
            "Challenge-Fortschritt verworfen wird.",
            key="challenge_reset_check",
        )
        if st.button(
            "Challenge endgültig zurücksetzen",
            type="secondary",
            width="stretch",
            key="challenge_reset_button",
        ):
            if reset_text.strip().upper() != "RESET" or not reset_check:
                st.warning("Nicht zurückgesetzt: Beide Bestätigungen sind nötig.")
            else:
                try:
                    fresh = ledger.settings()
                    ledger.set_balance(fresh["starting_balance"], reset_start=True)
                    st.success("Challenge wurde zurückgesetzt — Neustart ab jetzt.")
                    st.rerun()
                except ValueError:
                    st.warning(
                        "Es gibt noch ein offenes Ticket. Erst abrechnen, "
                        "dann zurücksetzen."
                    )


def _render_equity_curve(ledger: ChallengeLedger, settings: dict[str, Any]) -> None:
    """Render the exact account path from the append-only transaction ledger."""
    tickets = ledger.tickets()
    transactions = ledger.transactions()
    settled = [
        ticket
        for ticket in tickets
        if ticket["status"] in ("WON", "LOST", "VOID") and ticket.get("settled_at")
    ]
    start = float(settings["starting_balance"])
    if not transactions:
        st.caption(
            "Noch keine Kontobewegung vorhanden. Jeder spätere Punkt ist eine "
            "echte Buchung — kein Backtest."
        )
        return

    times = [item["created_at"] for item in transactions]
    balances = [float(item["balance_after"]) for item in transactions]
    marker_colors = []
    for item in transactions:
        if item["kind"] in {"PAYOUT", "VOID_REFUND"}:
            marker_colors.append("#16784b")
        elif item["kind"] == "STAKE":
            marker_colors.append("#b4232f")
        elif item["kind"] in {
            "OPENING_BALANCE",
            "BALANCE_ADJUSTMENT",
            "CHALLENGE_RESET",
        }:
            marker_colors.append("#1d4ed8")
        else:
            marker_colors.append("#66707a")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=times,
            y=balances,
            mode="lines+markers",
            line={"color": "#16784b", "width": 2},
            marker={"size": 9, "color": marker_colors},
            hovertemplate="%{x|%d.%m.%Y %H:%M}<br>Guthaben: %{y:,.2f} €<extra></extra>",
        )
    )
    figure.add_hline(
        y=float(settings["target_balance"]),
        line_dash="dot",
        line_color="#a45f00",
        annotation_text="Ziel",
        annotation_position="top left",
    )
    figure.add_hline(y=start, line_dash="dot", line_color="#dfe3e7")
    figure.update_layout(
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=280,
        showlegend=False,
        xaxis={"showgrid": False},
        yaxis={"title": "Guthaben €", "gridcolor": "#eceef0"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

    wins = sum(ticket["status"] == "WON" for ticket in settled)
    losses = sum(ticket["status"] == "LOST" for ticket in settled)
    decided = wins + losses
    staked_total = sum(float(ticket["stake"]) for ticket in settled)
    betting_net = sum(
        float(ticket["payout"]) - float(ticket["stake"])
        for ticket in settled
    )
    kpis = st.columns(4)
    kpis[0].metric(
        "Wett-P/L",
        f"{betting_net:+,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
    )
    kpis[1].metric(
        "Trefferquote",
        f"{wins}/{decided}" if decided else "—",
    )
    kpis[2].metric(
        "ROI auf Einsatz",
        f"{(betting_net / staked_total) * 100:+.1f} %"
        if staked_total > 0
        else "—",
    )
    kpis[3].metric(
        "Netto finanziert",
        _format_euro(settings.get("net_external_funding", 0.0)),
    )


def _render_history(ledger: ChallengeLedger) -> None:
    settings = ledger.settings()
    _render_equity_curve(ledger, settings)
    tickets = ledger.tickets()
    if not tickets:
        st.info("Noch kein Challenge-Ticket eingetragen.")
    transactions = ledger.transactions()
    if transactions:
        with st.expander("Kontobewegungen"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Zeit": item["created_at"],
                            "Art": item["kind"],
                            "Betrag €": item["amount"],
                            "Saldo €": item["balance_after"],
                            "Ticket": item["ticket_id"],
                        }
                        for item in reversed(transactions)
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
    if not tickets:
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


def _format_kickoff(raw: str) -> str:
    """'2026-07-31T18:30:00+00:00' -> '31.07. 20:30' (lokale Zeit)."""
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(CHALLENGE_TIMEZONE).strftime("%d.%m. %H:%M")
    except (ValueError, TypeError):
        return str(raw or "?")


def _shortlist_frame(shortlist: list[ChallengeCandidate]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Anpfiff": _format_kickoff(candidate.kickoff),
                "Match": f"{candidate.home_team} vs {candidate.away_team}",
                "Markt": candidate.market,
                "Auswahl": candidate.selection,
                "Modell %": round(candidate.probability * 100, 1),
                "Konservativ %": round(candidate.conservative_probability * 100, 1),
                "Evidenz": candidate.evidence_score,
                "Mindestquote": round(candidate.minimum_odds, 2),
            }
            for candidate in shortlist
        ]
    )


def _shortlist_counts(shortlist: list[ChallengeCandidate]) -> tuple[int, int]:
    """Return market and unique-fixture counts for an honest UI summary."""
    return len(shortlist), len({candidate.fixture_id for candidate in shortlist})


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
    checks[3].metric("Mindestquote", f"{candidate.minimum_odds:.2f}")
    lineup_display = (context.get("lineups") or {}).get("display") or {}
    if lineup_display:
        with st.expander("Bestätigte Aufstellungen", expanded=False):
            lineup_cols = st.columns(2)
            for col, side, team_name in (
                (lineup_cols[0], "home", candidate.home_team),
                (lineup_cols[1], "away", candidate.away_team),
            ):
                info = lineup_display.get(side)
                if not info:
                    col.caption(f"{team_name}: noch nicht veröffentlicht")
                    continue
                formation = f" ({info['formation']})" if info.get("formation") else ""
                col.markdown(f"**{team_name}**{formation}")
                if info.get("coach"):
                    col.caption(f"Coach: {info['coach']}")
                col.markdown(
                    "\n".join(
                        f"{index}. {name}"
                        for index, name in enumerate(info.get("starters", []), start=1)
                    )
                )


def _render_price_check(
    snapshot: dict[str, Any],
    ledger: ChallengeLedger,
    settings: dict[str, Any],
) -> None:
    shortlist: list[ChallengeCandidate] = snapshot["shortlist"]
    if not shortlist:
        found = snapshot.get("fixtures_found", 0)
        modeled = snapshot.get("fixtures_modeled", 0)
        base_shortlist = snapshot.get("base_shortlist") or []
        if base_shortlist:
            market_count, fixture_count = _shortlist_counts(base_shortlist)
            fixture_label = (
                "einem Spiel" if fixture_count == 1 else f"{fixture_count} Spielen"
            )
            st.warning(
                f"NOCH KEINE WETTFREIGABE - {market_count} mathematisch "
                f"vorgefilterte Märkte aus {fixture_label}. Es fehlen noch "
                "Pflichtdaten (H2H, Ausfälle, Wetter oder bestätigte "
                "Startaufstellungen). Erst danach wird der N1Bet-Preis geprüft."
            )
        else:
            st.error("KEINE WETTE HEUTE — kein Kandidat besteht alle Prüfkriterien.")
        st.caption(
            f"{found} Spiele gefunden; {modeled} davon lieferten genug gültige "
            "Statistik für eine Modellbewertung. Ligakalender und Provider-Abdeckung "
            "können diese Zahl verkleinern. Fehlende Evidenz wird nicht geschätzt."
        )
        if snapshot.get("blocked_counts"):
            with st.expander("Warum wurden Kandidaten abgelehnt?"):
                st.caption(
                    "Jedes Spiel wird auf mehreren Märkten geprüft und kann mehrere "
                    "Ablehnungsgründe gleichzeitig haben. Die Tabelle zählt, wie oft "
                    "jeder Grund vorkam — reine Diagnose, keine Handlungsaufforderung."
                )
                audit = pd.DataFrame(
                    [
                        {"Grund": plain_german(reason), "Anzahl": count}
                        for reason, count in sorted(
                            snapshot["blocked_counts"].items(),
                            key=lambda item: item[1],
                            reverse=True,
                        )[:10]
                    ]
                )
                st.dataframe(audit, width="stretch", hide_index=True)
        if base_shortlist:
            st.subheader("Mathematische Vorfilterung - noch keine Empfehlung")
            st.caption(
                "Ein Spiel kann hier mit mehreren Märkten erscheinen. Diese Zeilen sind "
                "keine Wetttipps: Sie bestehen nur Modell, Walk-forward-Validierung und "
                "Evidenz. H2H, Ausfälle, Wetter und bestätigte Startaufstellungen sind "
                "verbindliche Veto-Gates. Erst wenn alle passen, folgt die N1Bet-Preisprüfung."
            )
            st.dataframe(
                _shortlist_frame(base_shortlist), width="stretch", hide_index=True
            )
            st.caption(
                "Mindestquote = der erste Preis, der nach konservativem "
                "Modellabschlag mindestens 3 % Risiko-EV erreicht. Zahlt N1Bet "
                "WENIGER als die Mindestquote, "
                "ist es keine Wette — egal wie „sicher“ sich der Tipp anfühlt. "
                "Zahlt N1Bet mehr, entsteht ein Preis-Check."
            )
        return

    st.subheader("Modell-Shortlist")
    st.dataframe(_shortlist_frame(shortlist), width="stretch", hide_index=True)
    preview = snapshot.get("model_ticket") or ()
    if preview:
        preview_text = " + ".join(
            f"{candidate.home_team} vs {candidate.away_team}: {candidate.selection}"
            for candidate in preview
        )
        dependency_factor = ticket_dependency_factor(preview)
        preview_probability = (
            math.prod(candidate.conservative_probability for candidate in preview)
            * dependency_factor
        )
        preview_price = minimum_acceptable_odds(
            preview_probability * 100.0,
            minimum_expected_roi_percent=MIN_LEG_EXPECTED_ROI * 100.0,
        )
        st.info(
            f"Quotenfreie Modellkombination: {preview_text} | "
            f"Mindestquote kombiniert {preview_price:.2f}"
        )

    st.subheader("N1Bet-Preisprüfung")
    current_quote_result = st.session_state.get("challenge_quote_result")
    has_current_ticket = (
        isinstance(current_quote_result, dict)
        and current_quote_result.get("snapshot_time") == snapshot["scanned_at"]
        and current_quote_result.get("ticket") is not None
    )
    if not has_current_ticket:
        st.info(
            "PREIS ERFORDERLICH: Für jede gewünschte Auswahl die aktuelle N1Bet-Quote eintragen; "
            "0 lässt den Markt aus."
        )
    st.caption(
        "Die Preise werden erst jetzt manuell ergänzt. Eine niedrige Quote erhöht keine "
        "Modellwahrscheinlichkeit; ein negativer Einzel- oder Ticket-EV sperrt die Auswahl."
    )
    count_market_candidates = [
        candidate
        for candidate in shortlist
        if MARKET_BY_KEY[candidate.market_key].kind in COUNT_MARKET_KINDS
    ]
    if count_market_candidates:
        st.warning(
            "Ecken-/Kartenmärkte in der Shortlist: Das Modell rechnet mit API-Zählungen ab. "
            "Buchmacherregeln (z. B. zweite Gelbe Karte, Karten für Trainer oder Bank, Karten "
            "nach Abpfiff, zurückgenommene Ecken) können abweichen. Vor der Abgabe die "
            "N1Bet-Marktregeln prüfen; bei Abweichung den Markt auslassen."
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
        implausible_entries = [
            f"{candidate.home_team} vs {candidate.away_team} "
            f"({odds_by_candidate.get(candidate.candidate_id, 0.0):.2f})"
            for candidate in shortlist
            if 0.0 < odds_by_candidate.get(candidate.candidate_id, 0.0) <= 1.0
        ]
        if implausible_entries:
            st.warning(
                "Ungültige Quote (kleiner oder gleich 1,00) eingegeben und ignoriert: "
                + "; ".join(implausible_entries)
                + ". Dezimalquoten müssen über 1,00 liegen; 0 bedeutet Markt nicht verfügbar."
            )
        checked_at = datetime.now(timezone.utc)
        valid_price_candidates = [
            candidate
            for candidate in shortlist
            if odds_by_candidate.get(candidate.candidate_id, 0.0) > 1.0
        ]
        price_ledger = PriceLedger(ledger.db_path)
        price_error = None
        try:
            observations = price_ledger.append_many(
                (
                    PriceQuote(
                        sport="FOOTBALL",
                        event_id=str(candidate.fixture_id),
                        event_name=(
                            f"{candidate.home_team} vs {candidate.away_team}"
                        ),
                        scheduled_start=candidate.kickoff,
                        market_key=candidate.market_key,
                        market_name=candidate.market,
                        selection_key=candidate.candidate_id,
                        selection_name=candidate.selection,
                        decimal_odds=odds_by_candidate[candidate.candidate_id],
                        phase="ENTRY",
                        source="MANUAL",
                        captured_at=checked_at,
                        line=MARKET_BY_KEY[candidate.market_key].threshold,
                        model_ref=(
                            f"challenge-snapshot-v{CHALLENGE_SNAPSHOT_VERSION}:"
                            f"{snapshot['scanned_at']}"
                        ),
                        metadata={
                            "candidate_id": candidate.candidate_id,
                            "league_id": candidate.league_id,
                        },
                    )
                    for candidate in valid_price_candidates
                ),
                now=checked_at,
            )
        except (PriceLedgerError, PriceLedgerIntegrityError) as exc:
            observations = []
            price_error = str(exc)
            st.error(f"PREIS NICHT GESPEICHERT: {exc}")
        observation_ids = {
            candidate.candidate_id: observation.id
            for candidate, observation in zip(
                valid_price_candidates,
                observations,
            )
        }
        ticket = (
            select_quoted_ticket(
                shortlist,
                odds_by_candidate,
                quote_observation_ids=observation_ids,
            )
            if len(observations) == len(valid_price_candidates)
            else None
        )
        st.session_state["challenge_quote_result"] = {
            "snapshot_time": snapshot["scanned_at"],
            "checked_at": checked_at.isoformat(),
            "ticket": ticket,
        }
        if ticket is None and price_error is None:
            st.error(
                "NICHT WETTEN: Keine Kombination erfüllt Zielquote, Einzel-Value und Mindest-EV gemeinsam."
            )

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
            f"Zusätzlicher Kombi-Modellfehlerabschlag: Faktor "
            f"{ticket.model_dependency_factor:.3f}. "
            f"Abhängigkeitsfreie Fréchet-Stressgrenze: "
            f"{ticket.dependence_floor_probability * 100:.1f} %."
        )
    current_balance = settings["current_balance"]
    stake_fraction = settings["stake_fraction"]
    stake = ticket_stake(ticket, current_balance, stake_fraction)
    risk_stake = risk_managed_ticket_stake(ticket, current_balance)
    log_growth = expected_log_growth(ticket, stake_fraction)
    win_balance = current_balance - stake + stake * ticket.total_odds
    loss_balance = current_balance - stake
    wins_remaining = consecutive_wins_to_target(
        current_balance,
        settings["target_balance"],
        ticket.total_odds,
        stake_fraction,
    )
    stake_metrics = st.columns(4)
    stake_metrics[0].metric("Shadow-Einsatz", _format_euro(stake))
    stake_metrics[1].metric("Saldo bei Gewinn", _format_euro(win_balance))
    stake_metrics[2].metric("Saldo bei Verlust", _format_euro(loss_balance))
    stake_metrics[3].metric("Risikoreferenz", _format_euro(risk_stake))
    if wins_remaining is not None and wins_remaining > 0:
        path_probability = ticket.joint_probability ** wins_remaining
        st.caption(
            f"Bei unveränderter Quote wären {wins_remaining} Siege in Folge bis zum Ziel nötig. "
            f"Modellpfad unter identischer Trefferchance: {path_probability * 100:.3f} %."
        )
    if log_growth <= 0.0:
        st.warning(
            "Der gewählte Shadow-Einsatz hat bei dieser Quote und "
            "Trefferwahrscheinlichkeit negatives erwartetes Log-Wachstum. "
            "Er ist mathematisch überzogen; die Risikoreferenz ist maßgeblich."
        )
    elif stake > risk_stake:
        st.warning(
            "Der Shadow-Einsatz liegt über der 5-%-gedeckelten "
            "Viertel-Kelly-Risikoreferenz. Das beschleunigt nur die Simulation, "
            "nicht den nachgewiesenen Vorteil."
        )
    if stale:
        st.warning(
            "PREIS ERFORDERLICH: Die geprüften N1Bet-Preise sind älter als 10 Minuten. Erneut prüfen."
        )
        return
    if stake <= 0:
        st.error("NICHT WETTEN: Kein verfügbares Guthaben für einen Einsatz.")
        return
    st.info(
        f"SHADOW-TICKET: {len(ticket.legs)} Spiel(e) @ Gesamtquote "
        f"{ticket.total_odds:.2f} | simulierter Shadow-Einsatz "
        f"{stake:.2f} €. Die Preisprüfung ist bestanden; eine "
        "Echtgeldfreigabe benötigt noch unabhängige CLV-/ROI-Evidenz."
    )
    if st.button(
        f"Shadow-Ticket mit {stake:.2f} € eintragen",
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
            st.success(f"Shadow-Ticket #{ticket_id} eingetragen.")
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
    st.caption(
        "Freigabe erst, wenn Modell, Walk-forward, H2H, Ausfälle und Wetter "
        "passen sowie bestätigte Startaufstellungen vollständig vorliegen. "
        "Danach prüft der N1Bet-Preis "
        "den Value. Bis zum unabhängigen Evidenznachweis bleibt das Ergebnis "
        "ein Shadow-Ticket ohne Echtgeld-Einsatz."
    )

    controls = st.columns(2)
    with controls[0]:
        date_mode = _segmented(
            "Spieltag",
            ["Heute", "Morgen"],
            "challenge_date_mode",
            "Heute",
        )
    search_date = (
        _challenge_today()
        if date_mode == "Heute"
        else _challenge_today() + timedelta(days=1)
    )
    # Kein künstliches Modell-Limit: Alle gültigen Fixtures der gewählten
    # Ligen werden modelliert. Die zusätzlichen Pflichtkontext-Checks bleiben
    # über MAX_CONTEXT_FIXTURES gedeckelt; MAX_SCAN_FIXTURES ist nur das
    # technische Sicherheitsventil.
    max_fixtures = MAX_SCAN_FIXTURES
    controls[1].caption(
        "Alle Spiele der gewählten Ligen werden modelliert; "
        "Pflichtkontext inklusive Aufstellungen für höchstens 20 Spiele."
    )

    available_ids = list(ALTERNATIVE_MARKET_LEAGUES)
    favorites = [league_id for league_id in DEFAULT_CHALLENGE_LEAGUES if league_id in available_ids]
    all_scope_label = f"Alle ({len(available_ids)})"
    favorite_scope_label = f"Favoriten ({len(favorites)})"
    league_scope = _segmented(
        "Ligen",
        [all_scope_label, favorite_scope_label, "Auswahl"],
        "challenge_league_scope_v2",
        all_scope_label,
    )
    full_scan_confirmed = True
    if league_scope == favorite_scope_label:
        selected_leagues = favorites
        st.caption(", ".join(ALTERNATIVE_MARKET_LEAGUES[item] for item in selected_leagues))
    elif league_scope == all_scope_label:
        selected_leagues = available_ids
        st.warning(
            f"Vollscan über {len(selected_leagues)} Ligen: deutlich mehr Provider-Aufrufe "
            "und uneinheitliche Saison-/Kontextabdeckung. Die mathematischen und "
            "fachlichen Gates bleiben für jede Liga unverändert streng."
        )
        full_scan_confirmed = st.checkbox(
            f"{len(selected_leagues)}-Ligen-Vollscan bewusst starten",
            value=False,
            key="challenge_confirm_full_league_scan",
        )
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_ids,
            default=favorites,
            format_func=lambda league_id: ALTERNATIVE_MARKET_LEAGUES.get(league_id, str(league_id)),
            key="challenge_selected_leagues",
        )

    if st.button(
        "Challenge-Kandidaten finden",
        type="primary",
        width="stretch",
        key="run_challenge_scan",
        disabled=not full_scan_confirmed,
    ):
        if not selected_leagues:
            st.warning("Mindestens eine Liga auswählen.")
        elif scan_jobs.get_job(_challenge_job_key())["state"] == "running":
            st.info("Der Challenge-Scan läuft bereits im Hintergrund.")
        else:
            provider = ChallengeDataProvider(config.api_football_key, config.weather_key)
            st.session_state.pop("challenge_auto_recheck_at", None)
            st.session_state.pop("challenge_auto_seen", None)
            scan_jobs.start_job(
                _challenge_job_key(),
                _run_challenge_scan_worker,
                args=(provider, list(selected_leagues), search_date, max_fixtures),
            )

    job = scan_jobs.get_job(_challenge_job_key())
    if job["state"] == "running":
        scan_progress_fragment(_challenge_job_key(), "15K-Scan")
    elif job["state"] == "done":
        st.session_state["challenge_snapshot"] = job.get("result")
        st.session_state.pop("challenge_quote_result", None)
        scan_jobs.clear_job(_challenge_job_key())
    elif job["state"] == "error":
        st.error(f"Challenge-Wettfinder fehlgeschlagen: {job.get('error')}")
        scan_jobs.clear_job(_challenge_job_key())

    snapshot = st.session_state.get("challenge_snapshot")
    if not isinstance(snapshot, dict):
        render_empty_state(
            "So funktioniert die Challenge-Suche",
            [
                "Spieltag und Ligen wählen, dann „Challenge-Kandidaten finden“ klicken.",
                "Das Modell prüft quotenfrei bis zu drei streng gefilterte Spiele.",
                "Erst danach entscheidet der N1Bet-Preis über eine Freigabe.",
            ],
            duration_hint=(
                "Dauer: provider- und cacheabhängig. Ein kalter 51-Ligen-Vollscan "
                "kann mehrere Minuten dauern; solange neue Fortschrittsmeldungen "
                "eintreffen, läuft er weiter."
            ),
        )
        return
    if snapshot.get("version") != CHALLENGE_SNAPSHOT_VERSION:
        st.warning("Dieses Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return
    current_scope = _scope_signature(selected_leagues, search_date, max_fixtures)
    if snapshot.get("scope") != current_scope:
        st.warning("Datum, Liga oder Prüfumfang wurden seit dem Ergebnis geändert. Wetten neu suchen.")
        return

    st.caption(f"Datenstand: {_format_time(snapshot.get('scanned_at'))}")
    try:
        scanned_at = datetime.fromisoformat(snapshot["scanned_at"]).astimezone(timezone.utc)
        snapshot_age = (
            datetime.now(timezone.utc) - scanned_at
        ).total_seconds() / 60.0
    except (KeyError, TypeError, ValueError):
        snapshot_age = float("inf")
    if snapshot_age > SNAPSHOT_MAX_AGE_MINUTES or snapshot_age < -1:
        if not _auto_recheck_eligible(snapshot, search_date):
            st.warning(
                "Dieser Datenstand ist nicht mehr aktuell. Verletzungen, Wetter "
                "und Anstoßstatus müssen neu geprüft werden."
            )
            return
        st.info(
            "Wartezustand: Der Datenstand ist älter, aber noch ohne Wettfreigabe. "
            "Die Auto-Prüfung scannt selbstständig neu, sobald frischer Pflichtkontext "
            "(H2H, Ausfälle, Wetter und bestätigte Startaufstellungen) für "
            "Shortlist-Spiele verfügbar wird."
        )
    counts = st.columns(4)
    counts[0].metric("Gefunden", snapshot["fixtures_found"])
    counts[1].metric("Modelliert", snapshot["fixtures_modeled"])
    counts[2].metric("Kontext-Spiele (max. 20)", snapshot["context_fixtures"])
    counts[3].metric("Freigegeben", snapshot["approved_candidates"])
    if snapshot.get("errors"):
        st.warning(
            f"{len(snapshot['errors'])} Provider- oder Coverage-Meldungen wurden protokolliert."
        )
        st.caption(
            "Fehlende Pflichtdaten sperren den betroffenen Kandidaten. Rein optionale "
            "Hinweise, etwa geringe xG-Abdeckung, sind transparent sichtbar, sperren "
            "aber nicht automatisch. Maßgeblich sind die ausgewiesenen Ablehnungsgründe."
        )
        st.dataframe(
            pd.DataFrame(
                {"Provider-Meldung": snapshot["errors"][:8]}
            ),
            width="stretch",
            hide_index=True,
        )
    _render_price_check(snapshot, ledger, settings)
    if _auto_recheck_eligible(snapshot, search_date):
        _challenge_auto_recheck_fragment(
            config.api_football_key,
            config.weather_key,
            list(selected_leagues),
            search_date,
            max_fixtures,
        )


def render_challenge_15k() -> None:
    """Render the complete challenge workspace."""
    session_scope = scan_jobs.session_scope(st.session_state)
    ledger = _challenge_ledger(session_scope)
    _auto_settle_feedback(ledger)
    settings = _render_progress(ledger)
    st.caption(
        f"Einsatzanteil {settings['stake_fraction'] * 100:.0f} % | "
        "Tageszielquote 2,00-3,00 | maximal drei verschiedene Spiele | "
        "Shadow-Phase: Buchmacherpreise erst nach der Modellfreigabe"
    )
    challenge_views = ["Wettfinder", "Verlauf", "Konto"]
    if st.session_state.get("challenge_workspace") not in challenge_views:
        st.session_state["challenge_workspace"] = "Wettfinder"
    mode = _segmented(
        "Challenge-Bereich",
        challenge_views,
        "challenge_workspace",
        "Wettfinder",
    )
    if mode == "Wettfinder":
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


__all__ = [
    "ChallengeDataProvider",
    "refresh_discovered_candidates",
    "render_challenge_15k",
    "scan_daily_challenge",
]
