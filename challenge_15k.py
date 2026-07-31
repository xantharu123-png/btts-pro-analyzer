"""Responsive 15K challenge workspace with strict model and price gates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from challenge_engine import (
    ChallengeCandidate,
    COUNT_MARKET_KINDS,
    CROSS_LEG_MODEL_FACTOR,
    MARKET_BY_KEY,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    MarketSpec,
    apply_candidate_context,
    build_fixture_candidates,
    consecutive_wins_to_target,
    fit_market_calibration,
    kelly_reference_stake,
    market_outcome,
    market_specs,
    select_model_ticket,
    select_quoted_ticket,
    select_shortlist,
    ticket_stake,
    validate_league_markets,
)
from challenge_store import ChallengeLedger
from config_loader import load_app_config
from ui_components import milestone_bar_html, plain_german, render_empty_state
from football_data_history import fetch_history as fetch_stat_history
from football_data_history import merge_api_tail
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from season_utils import current_season_start_year_for_id
from xg_backfill import annotate_history as annotate_history_xg


CHALLENGE_SNAPSHOT_VERSION = 3
CHALLENGE_WORKSPACE_VERSION = 3
CHALLENGE_TIMEZONE = ZoneInfo("Europe/Zurich")
DEFAULT_CHALLENGE_LEAGUES = (78, 39, 140, 135, 61)  # xG-validierte Top-5-Ligen
API_TAIL_DAYS = 7  # Frische-Tail: API-FT-Ergebnisse über die CSV-Historie legen
MIN_HISTORY_GAMES = 220  # darunter wird die Vorsaison vorangestellt (Cold-Start)
MAX_CONTEXT_FIXTURES = 20
# Safety-Ventil, kein Modell-Limit: ALLE Spiele der gewählten Ligen werden
# modelliert (lokal, kostenlos). Teuer sind nur die Kontext-Checks, und die
# bleiben über MAX_CONTEXT_FIXTURES gedeckelt.
MAX_SCAN_FIXTURES = 400
QUOTE_MAX_AGE_MINUTES = 10
SNAPSHOT_MAX_AGE_MINUTES = 20
XG_MAX_NEW_CALLS_PER_SCAN = 12


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


def scan_daily_challenge(
    provider: ChallengeDataProvider,
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
) -> dict[str, Any]:
    """Run one explicit, quota-aware daily challenge scan."""
    _validate_scan_inputs(league_ids, search_date, max_fixtures)
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
                        provider._football_get,
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

    validations = {
        league_id: _cached_market_validation(
            league_id,
            seasons[league_id],
            history,
        )
        for league_id, history in histories.items()
        if history
    }
    calibrations = {
        league_id: _cached_market_calibration(
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
                calibrations.get(league_id, {}),
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
            lineups=(
                detail.get("lineups")
                if isinstance(detail, dict) and league_coverage.get("lineups") is True
                else None
            ),
        )
        contextualized.append(candidate)

    shortlist = select_shortlist(contextualized, max_candidates=3)
    model_ticket = select_model_ticket(shortlist)
    base_shortlist = sorted(base_candidates, key=_candidate_rank, reverse=True)[:10]
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
        "approved_candidates": len(shortlist),
        "shortlist": shortlist,
        "base_shortlist": base_shortlist,
        "model_ticket": model_ticket,
        "blocked_counts": blocked_counts,
        "errors": list(provider.errors),
    }


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

    Challenge rule: a lost ticket restarts the challenge at the starting
    balance. AET/PEN results and mixed void/decided tickets stay open for
    manual settlement. Never raises — settlement must not break the UI.
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
                # Challenge-Regel: Bei Verlust geht alles von vorne.
                try:
                    settings = ledger.settings()
                    ledger.set_balance(settings["starting_balance"], reset_start=True)
                    summary["resets"] += 1
                except ValueError:
                    pass
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
    if summary.get("resets"):
        st.warning(
            "Ticket verloren — die Challenge wurde automatisch auf den "
            "Startwert zurückgesetzt. Es geht von vorne los."
        )
    elif summary.get("lost"):
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
        ("Challenge-Einsatz", _format_euro(current * stake_fraction)),
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
        max_value=100,
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
    if stake_percent == 100:
        st.warning("100 % Roll-over: Eine verlorene Wette setzt das Challenge-Guthaben auf 0 €.")

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
        "berechnet; es gibt kein Nachschießen und keine Martingale-Verdopplung nach Verlusten. "
        "Ein offenes Ticket muss vor dem nächsten Ticket abgerechnet sein."
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
    """Equity curve from settled challenge tickets — the build-in-public proof."""
    tickets = ledger.tickets()
    settled = [
        ticket
        for ticket in tickets
        if ticket["status"] in ("WON", "LOST", "VOID") and ticket.get("settled_at")
    ]
    settled.sort(key=lambda ticket: ticket["settled_at"])
    start = float(settings["starting_balance"])
    if not settled:
        st.caption(
            "Die Guthabenkurve startet mit dem ersten abgerechneten Ticket. "
            "Jeder Punkt ist ein echtes Ergebnis — kein Backtest."
        )
        return

    times = [min(ticket["created_at"] for ticket in tickets)]
    balances = [start]
    deltas = [0.0]
    balance = start
    wins = losses = 0
    staked_total = 0.0
    for ticket in settled:
        stake = float(ticket["stake"])
        staked_total += stake
        if ticket["status"] == "WON":
            delta = float(ticket["payout"]) - stake
            wins += 1
        elif ticket["status"] == "LOST":
            delta = -stake
            losses += 1
        else:
            delta = 0.0
        balance += delta
        times.append(ticket["settled_at"])
        balances.append(balance)
        deltas.append(delta)

    marker_colors = [
        "#66707a" if index == 0 else ("#16784b" if deltas[index] > 0 else ("#b4232f" if deltas[index] < 0 else "#66707a"))
        for index in range(len(balances))
    ]
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

    decided = wins + losses
    net = balance - start
    kpis = st.columns(3)
    kpis[0].metric("Netto", f"{net:+,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
    kpis[1].metric(
        "Trefferquote",
        f"{wins}/{decided}" if decided else "—",
    )
    kpis[2].metric(
        "ROI auf Einsatz",
        f"{(net / staked_total) * 100:+.1f} %" if staked_total > 0 else "—",
    )


def _render_history(ledger: ChallengeLedger) -> None:
    settings = ledger.settings()
    _render_equity_curve(ledger, settings)
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
                "Mindestquote": round(candidate.model_price, 2),
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
    checks[3].metric("Mindestquote", f"{candidate.model_price:.2f}")


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
            st.warning(
                f"NOCH KEINE WETTFREIGABE — {len(base_shortlist)} Märkte bestehen "
                "die Mathematik und warten auf Live-Kontext (Aufstellungen, ca. "
                "60 Minuten vor Anpfiff) und den N1Bet-Preis."
            )
        else:
            st.error("KEINE WETTE HEUTE — kein Kandidat besteht alle Prüfkriterien.")
        st.caption(
            f"{found} Spiele gefunden, aber nur für {modeled} davon lag genug Statistik "
            "für eine Modellbewertung vor. In der Sommerpause ist das normal: "
            "Das Modell wettet nur bei ausreichender Evidenz."
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
            st.subheader("Modell-Shortlist — Kontext & Quote offen")
            st.caption(
                "Diese Märkte bestehen die Mathematik-Gates (Modell, Walk-forward-Validierung, "
                "Evidenz). Was noch fehlt: der Live-Kontext (bestätigte Aufstellungen, Ausfälle, "
                "Wetter, H2H) — der steht ca. 60 Minuten vor Anpfiff bereit — und danach der "
                "N1Bet-Preis. Kurz vor Anpfiff erneut suchen. Keine Wettfreigabe ohne Kontext + Quote."
            )
            st.dataframe(
                _shortlist_frame(base_shortlist), width="stretch", hide_index=True
            )
            st.caption(
                "Mindestquote = die fairste Quote, die das Modell nach konservativem "
                "Abschlag noch akzeptiert. Zahlt N1Bet WENIGER als die Mindestquote, "
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
        preview_price = (
            math.prod(candidate.model_price for candidate in preview)
            / (CROSS_LEG_MODEL_FACTOR ** max(0, len(preview) - 1))
        )
        st.info(f"Quotenfreie Modellkombination: {preview_text} | Mindestquote kombiniert {preview_price:.2f}")

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
        ticket = select_quoted_ticket(shortlist, odds_by_candidate)
        st.session_state["challenge_quote_result"] = {
            "snapshot_time": snapshot["scanned_at"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ticket": ticket,
        }
        if ticket is None:
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
            f"Zusätzlicher Kombi-Modellfehlerabschlag: Faktor {ticket.model_dependency_factor:.3f}."
        )
    current_balance = settings["current_balance"]
    stake_fraction = settings["stake_fraction"]
    stake = ticket_stake(ticket, current_balance, stake_fraction)
    kelly_stake = kelly_reference_stake(ticket, current_balance)
    win_balance = current_balance - stake + stake * ticket.total_odds
    loss_balance = current_balance - stake
    wins_remaining = consecutive_wins_to_target(
        current_balance,
        settings["target_balance"],
        ticket.total_odds,
        stake_fraction,
    )
    stake_metrics = st.columns(4)
    stake_metrics[0].metric("Challenge-Einsatz", _format_euro(stake))
    stake_metrics[1].metric("Saldo bei Gewinn", _format_euro(win_balance))
    stake_metrics[2].metric("Saldo bei Verlust", _format_euro(loss_balance))
    stake_metrics[3].metric("¼-Kelly-Referenz", _format_euro(kelly_stake))
    if wins_remaining is not None and wins_remaining > 0:
        path_probability = ticket.joint_probability ** wins_remaining
        st.caption(
            f"Bei unveränderter Quote wären {wins_remaining} Siege in Folge bis zum Ziel nötig. "
            f"Modellpfad unter identischer Trefferchance: {path_probability * 100:.3f} %."
        )
    if stake_fraction >= 1.0:
        st.warning("All-in-Stufe: Eine Niederlage beendet die Challenge mit 0 € Guthaben.")
    if stale:
        st.warning(
            "PREIS ERFORDERLICH: Die geprüften N1Bet-Preise sind älter als 10 Minuten. Erneut prüfen."
        )
        return
    if stake <= 0:
        st.error("NICHT WETTEN: Kein verfügbares Guthaben für einen Einsatz.")
        return
    st.success(
        f"WETTEN: {len(ticket.legs)} Spiel(e) @ Gesamtquote {ticket.total_odds:.2f} | "
        f"Challenge-Einsatz {stake:.2f} €"
    )
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
    st.caption(
        "Eine finale Freigabe ist erst mit bestätigten Startaufstellungen möglich. "
        "Frühere Suchen bleiben bewusst ohne Ticketfreigabe."
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
    # Kein künstliches Limit: ALLE Spiele der gewählten Ligen werden
    # modelliert (lokal). Die teuren Live-Kontext-Checks bleiben über
    # MAX_CONTEXT_FIXTURES gedeckelt; MAX_SCAN_FIXTURES ist nur das
    # technische Sicherheitsventil.
    max_fixtures = MAX_SCAN_FIXTURES
    controls[1].caption(
        "Alle Spiele der gewählten Ligen werden modelliert; "
        "Live-Kontext (H2H, Wetter, Aufstellung) für die 20 stärksten Kandidaten."
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
        st.caption(f"{len(selected_leagues)} Ligen; diese Suche benötigt entsprechend mehr Provider-Aufrufe.")
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_ids,
            default=favorites,
            format_func=lambda league_id: ALTERNATIVE_MARKET_LEAGUES.get(league_id, str(league_id)),
            key="challenge_selected_leagues",
        )

    if st.button(
        "Challenge-Wetten finden",
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
                st.error(f"Challenge-Wettfinder fehlgeschlagen: {exc}")

    snapshot = st.session_state.get("challenge_snapshot")
    if not isinstance(snapshot, dict):
        render_empty_state(
            "So funktioniert die Challenge-Suche",
            [
                "Spieltag und Ligen wählen, dann „Challenge-Wetten finden“ klicken.",
                "Das Modell prüft quotenfrei bis zu drei streng gefilterte Spiele.",
                "Erst danach entscheidet der N1Bet-Preis über eine Freigabe.",
            ],
            duration_hint="Dauer: je nach Ligaanzahl etwa 30–90 Sekunden.",
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
        st.warning(
            "Dieser Datenstand ist nicht mehr aktuell. Verletzungen, Wetter, "
            "Aufstellungen und Anstoßstatus müssen neu geprüft werden."
        )
        return
    counts = st.columns(4)
    counts[0].metric("Gefunden", snapshot["fixtures_found"])
    counts[1].metric("Modelliert", snapshot["fixtures_modeled"])
    counts[2].metric("Kontext geprüft (Top 20)", snapshot["context_fixtures"])
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
    _auto_settle_feedback(ledger)
    settings = _render_progress(ledger)
    st.caption(
        f"Einsatzanteil {settings['stake_fraction'] * 100:.0f} % | "
        "Tageszielquote 2,00-3,00 | maximal drei verschiedene Spiele | "
        "Buchmacherpreise erst nach der Modellfreigabe"
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


__all__ = ["ChallengeDataProvider", "render_challenge_15k", "scan_daily_challenge"]
