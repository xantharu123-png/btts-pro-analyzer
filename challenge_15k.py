"""Responsive 15K challenge workspace with strict model and price gates."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path
import time
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import scan_jobs

from account_identity import storage_scope
from api_budget import (
    APIBudgetError,
    APIBudgetPriority,
    api_football_get,
)
from challenge_engine import (
    ChallengeCandidate,
    COUNT_MARKET_KINDS,
    MARKET_BY_KEY,
    MAX_CHALLENGE_STAKE_FRACTION,
    MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
    MODEL_SCOPE_SAME_COMPETITION,
    MIN_LEG_EXPECTED_ROI,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    UNVALIDATED_TRANSFER_REASON,
    MarketSpec,
    ValidationMetrics,
    apply_candidate_context,
    build_fixture_candidates,
    candidate_is_credible,
    challenge_stake_cap,
    consecutive_wins_to_target,
    extract_lineup_display,
    fit_market_calibration,
    fixture_market_probabilities,
    market_outcome,
    market_specs,
    select_model_ticket,
    select_quoted_ticket,
    select_shortlist,
    risk_managed_ticket_stake,
    ticket_stake,
    validate_league_markets,
)
from challenge_model_cache import load_model_artifact, save_model_artifact
from challenge_store import ChallengeLedger
from config_loader import load_app_config
from date_context import ZURICH_TIMEZONE, german_day_label, zurich_today
from ui_components import (
    milestone_bar_html,
    scan_progress_fragment,
)
from football_data_history import fetch_history as fetch_stat_history
from football_data_history import merge_api_tail
from league_catalog import ALTERNATIVE_MARKET_LEAGUES, LEAGUE_BY_ID
from market_consensus import (
    MarketConsensus,
    deserialize_consensus_map,
    fetch_football_consensus,
    reference_price_status,
    serialize_consensus_map,
)
from season_utils import current_season_start_year_for_id
from xg_backfill import annotate_history as annotate_history_xg


CHALLENGE_SNAPSHOT_VERSION = 13
CHALLENGE_WORKSPACE_VERSION = 9
CHALLENGE_TIMEZONE = ZURICH_TIMEZONE
DEFAULT_CHALLENGE_LEAGUES = (78, 39, 140, 135, 61)  # xG-validierte Top-5-Ligen
CHALLENGE_SPORT_OPTIONS = (
    "Alle",
    "Fußball",
    "Tennis",
    "Basketball",
    "Eishockey",
    "Cricket",
    "E-Sport",
)
CHALLENGE_ENABLED_SPORTS = ("Fußball",)
API_TAIL_DAYS = 7  # Frische-Tail: API-FT-Ergebnisse über die CSV-Historie legen
MIN_HISTORY_GAMES = 220  # darunter wird die Vorsaison vorangestellt (Cold-Start)
MAX_CONTEXT_FIXTURES = 20
MAX_DISCOVERY_MARKETS_PER_FIXTURE = 8
MAX_PRICE_CHECK_FIXTURES = 10
# Safety-Ventil, kein Modell-Limit: Alle gültigen Provider-Fixtures der
# gewählten Ligen werden modelliert. Die zusätzlichen Pflichtkontext-Checks
# bleiben über MAX_CONTEXT_FIXTURES gedeckelt.
MAX_SCAN_FIXTURES = 1200
MAX_SCAN_HORIZON_DAYS = 14
WEATHER_CONTEXT_HORIZON_DAYS = 5
SNAPSHOT_MAX_AGE_MINUTES = 20
XG_MAX_NEW_CALLS_PER_SCAN = 12
CONTINENTAL_LEAGUE_IDS = frozenset({2, 3, 848})
DOMESTIC_HISTORY_LAST_FIXTURES = 60
# Auto-Nachprüfung: Die App wartet selbst auf frischen Pflichtkontext
# (Ausfälle und Wetter; H2H ergänzend), statt dass der Nutzer den ganzen Tag
# manuell neu scannt. Aufstellungen werden später nur zur Anzeige ergänzt.
# Läuft nur, solange die Seite offen ist und noch kein Kandidat freigegeben wurde.
AUTO_RECHECK_WINDOW_MINUTES = 80
AUTO_RECHECK_MIN_GAP_MINUTES = 12
AUTO_RECHECK_POLL_SECONDS = 180
MAX_AUTO_RECHECK_LEAGUES = 12

MARKET_KIND_LABELS = {
    "result": "Endergebnis",
    "double_chance": "Doppelte Chance",
    "btts": "Beide Teams treffen",
    "total": "Gesamttore",
    "team_total": "Teamtore",
    "team_range": "Teamtore 1-3 / 2-4",
    "result_total": "Resultat & Tore",
    "mixed_or": "Gemischte Chance",
    "corner_total": "Eckbälle gesamt",
    "team_corners": "Team-Eckbälle",
    "yellow_total": "Gelbe Karten gesamt",
    "team_yellow": "Team-Karten",
}
MARKET_KIND_DETAILS = {
    "result": "1 / X / 2",
    "double_chance": "1X / X2 / 12",
    "btts": "Ja / Nein",
    "total": "Über / Unter 0,5 bis 4,5",
    "team_total": "je Team Über / Unter 0,5 bis 2,5",
    "team_range": "je Team 1-3 oder 2-4 Tore",
    "result_total": "1X & U3,5 / X2 & U3,5 / 12 & Ü1,5",
    "mixed_or": "BTTS / Heimsieg / Auswärtssieg ODER Ü2,5",
    "corner_total": "Über / Unter 5,5 bis 11,5",
    "team_corners": "je Team Über / Unter 2,5 bis 5,5",
    "yellow_total": "Über / Unter 1,5 bis 4,5",
    "team_yellow": "je Team Über / Unter 0,5 bis 2,5",
}


# Explicitly bump this value only when probability, validation or calibration
# semantics change. Context-only policy edits must not invalidate the costly
# walk-forward artifacts.
CHALLENGE_MODEL_SIGNATURE = "challenge-engine:9d0d520bdaed83095d75"


def _challenge_today(now: Optional[datetime] = None) -> date:
    """Return the current calendar date in the challenge timezone.

    Provider requests use ``timezone=Europe/Zurich``; the search date must be
    derived from the same zone, otherwise a UTC server picks the wrong match
    day between 00:00 and 02:00 Swiss time.
    """
    return zurich_today(now)


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
    search_end_date: Optional[date] = None,
) -> None:
    if not isinstance(league_ids, list) or not league_ids:
        raise ValueError("league_ids must be a non-empty list")
    if any(_positive_integer(league_id) is None for league_id in league_ids):
        raise ValueError("league_ids must contain only positive integer IDs")
    if len(set(league_ids)) != len(league_ids):
        raise ValueError("league_ids must not contain duplicates")
    if not isinstance(search_date, date) or isinstance(search_date, datetime):
        raise ValueError("search_date must be a date")
    end_date = search_end_date or search_date
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise ValueError("search_end_date must be a date")
    horizon_days = (end_date - search_date).days
    if not 0 <= horizon_days <= MAX_SCAN_HORIZON_DAYS:
        raise ValueError(
            "search_end_date must be between search_date and "
            f"{MAX_SCAN_HORIZON_DAYS} days later"
        )
    if (
        isinstance(max_fixtures, bool)
        or not isinstance(max_fixtures, int)
        or not 1 <= max_fixtures <= MAX_SCAN_FIXTURES
    ):
        raise ValueError(
            f"max_fixtures must be an integer between 1 and {MAX_SCAN_FIXTURES}"
        )


def _continental_team_history(
    provider: "ChallengeDataProvider",
    fixture: dict[str, Any],
    search_date: date,
) -> Optional[dict[str, Any]]:
    kickoff = _fixture_kickoff(fixture)
    teams = fixture.get("teams")
    if kickoff is None or not isinstance(teams, dict):
        return None
    team_ids: list[int] = []
    for side in ("home", "away"):
        team = teams.get(side)
        if not isinstance(team, dict):
            return None
        team_id = _positive_integer(team.get("id"))
        if team_id is None:
            return None
        team_ids.append(team_id)

    combined: list[dict[str, Any]] = []
    profiles: list[tuple[int, int]] = []
    for team_id in team_ids:
        profile = provider.domestic_team_history(team_id, search_date, kickoff)
        if not isinstance(profile, dict):
            return None
        league_id = _positive_integer(profile.get("league_id"))
        season = _positive_integer(profile.get("season"))
        if league_id is None or season is None:
            return None
        fixtures = profile.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            return None
        profiles.append((league_id, season))
        combined.extend(item for item in fixtures if isinstance(item, dict))

    unique: dict[int, dict[str, Any]] = {}
    for item in combined:
        fixture_data = item.get("fixture")
        if not isinstance(fixture_data, dict):
            continue
        fixture_id = _positive_integer(fixture_data.get("id"))
        if fixture_id is not None:
            unique[fixture_id] = item
    if not unique:
        return None
    return {
        "fixtures": sorted(
            unique.values(),
            key=lambda item: _fixture_kickoff(item)
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        "profiles": tuple(profiles),
    }


def _conservative_validation_map(
    validation_maps: list[dict[str, ValidationMetrics]],
) -> dict[str, ValidationMetrics]:
    """Require every source league and retain the weakest metric per gate."""
    if not validation_maps:
        return {}
    combined: dict[str, ValidationMetrics] = {}
    for spec in market_specs():
        metrics = [
            validation.get(spec.key)
            for validation in validation_maps
        ]
        if any(not isinstance(metric, ValidationMetrics) for metric in metrics):
            continue
        valid_metrics = [metric for metric in metrics if metric is not None]
        weakest = min(
            valid_metrics,
            key=lambda metric: (
                metric.relative_improvement
                if metric.relative_improvement is not None
                else -math.inf
            ),
        )
        worst_calibration = max(
            valid_metrics,
            key=lambda metric: (
                metric.max_calibration_error
                if metric.max_calibration_error is not None
                else math.inf
            ),
        )
        raw_brier_values = [
            metric.raw_brier_score
            for metric in valid_metrics
            if metric.raw_brier_score is not None
        ]
        combined[spec.key] = ValidationMetrics(
            observations=min(metric.observations for metric in valid_metrics),
            brier_score=weakest.brier_score,
            baseline_brier_score=weakest.baseline_brier_score,
            relative_improvement=min(
                metric.relative_improvement
                if metric.relative_improvement is not None
                else -math.inf
                for metric in valid_metrics
            ),
            expected_calibration_error=max(
                metric.expected_calibration_error
                if metric.expected_calibration_error is not None
                else math.inf
                for metric in valid_metrics
            ),
            passed=all(metric.passed is True for metric in valid_metrics),
            calibration_bins=min(
                metric.calibration_bins for metric in valid_metrics
            ),
            min_bin_size=min(metric.min_bin_size for metric in valid_metrics),
            max_calibration_error=worst_calibration.max_calibration_error,
            max_error_bin_size=worst_calibration.max_error_bin_size,
            max_error_bin_mean_probability=(
                worst_calibration.max_error_bin_mean_probability
            ),
            raw_brier_score=max(raw_brier_values) if raw_brier_values else None,
        )
    return combined


def _conservative_calibration_map(
    calibration_maps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Use the lowest calibrated probability across both source leagues."""
    if not calibration_maps:
        return {}
    combined: dict[str, Any] = {}
    for spec in market_specs():
        curves = [
            calibration.get(spec.key)
            for calibration in calibration_maps
        ]
        if any(curve is None or not callable(curve) for curve in curves):
            continue

        def conservative_curve(
            probability: float,
            source_curves: tuple[Any, ...] = tuple(curves),
        ) -> float:
            return min(
                [float(probability)]
                + [float(curve(probability)) for curve in source_curves]
            )

        combined[spec.key] = conservative_curve
    return combined


def _transfer_probe_validation_map() -> dict[str, ValidationMetrics]:
    """Optimistic validation used only to decide which source leagues to test.

    The probe can only widen the expensive-validation shortlist. Final
    candidates are rebuilt exclusively with real source-league metrics.
    """
    probe = ValidationMetrics(
        observations=300,
        brier_score=0.15,
        baseline_brier_score=0.20,
        relative_improvement=0.25,
        expected_calibration_error=0.0,
        passed=True,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.0,
        max_error_bin_size=30,
        max_error_bin_mean_probability=0.5,
        raw_brier_score=0.15,
    )
    return {
        spec.key: probe
        for spec in market_specs()
    }


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


def _challenge_sports_for_selection(sport: str) -> tuple[str, ...]:
    if sport == "Alle":
        return CHALLENGE_ENABLED_SPORTS
    if sport not in CHALLENGE_SPORT_OPTIONS:
        raise ValueError(f"Unbekannte Sportart: {sport}")
    return (sport,) if sport in CHALLENGE_ENABLED_SPORTS else ()


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


def _scope_signature(
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
    search_end_date: Optional[date] = None,
) -> dict[str, Any]:
    scope = {
        "league_ids": sorted(int(league_id) for league_id in league_ids),
        "date": search_date.isoformat(),
        "max_fixtures": int(max_fixtures),
    }
    end_date = search_end_date or search_date
    if end_date != search_date:
        scope["end_date"] = end_date.isoformat()
    return scope


CHALLENGE_SESSIONS_DIR = Path(__file__).resolve().parent / "challenge_sessions"


@st.cache_resource
def _challenge_ledger(session_scope: str) -> ChallengeLedger:
    """Keep browser accounts out of each other's bankroll."""
    account_id = hashlib.sha256(session_scope.encode("utf-8")).hexdigest()[:24]
    CHALLENGE_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return ChallengeLedger(CHALLENGE_SESSIONS_DIR / f"{account_id}.db")


def _challenge_job_key() -> str:
    scope = scan_jobs.session_scope(st.session_state)
    return scan_jobs.scoped_key("challenge_15k", scope)


@st.cache_data(ttl=6 * 3600, max_entries=64, show_spinner=False)
def _cached_market_artifact(
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
):
    cached = load_model_artifact(
        CHALLENGE_MODEL_SIGNATURE,
        league_id,
        season,
        history,
    )
    if cached is not None:
        return cached
    validation = validate_league_markets(history)
    calibration = fit_market_calibration(history)
    save_model_artifact(
        CHALLENGE_MODEL_SIGNATURE,
        league_id,
        season,
        history,
        validation,
        calibration,
    )
    return validation, calibration


@st.cache_data(ttl=6 * 3600, max_entries=64, show_spinner=False)
def _cached_market_validation(
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
):
    return _cached_market_artifact(league_id, season, history)[0]


@st.cache_data(ttl=6 * 3600, max_entries=64, show_spinner=False)
def _cached_market_calibration(
    league_id: int,
    season: int,
    history: list[dict[str, Any]],
):
    return _cached_market_artifact(league_id, season, history)[1]


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
        self._domestic_history_cache: dict[
            tuple[int, str], Optional[dict[str, Any]]
        ] = {}

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

    def upcoming_fixtures_range(
        self,
        league_id: int,
        season: int,
        start_date: date,
        end_date: date,
    ) -> Optional[list[dict[str, Any]]]:
        """Fetch an inclusive fixture window in one provider request."""
        return self._football_get(
            "fixtures",
            {
                "league": league_id,
                "season": season,
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "timezone": "Europe/Zurich",
                "status": "NS",
            },
            f"Fixtures Liga {league_id} {start_date.isoformat()} bis {end_date.isoformat()}",
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

    def domestic_team_history(
        self,
        team_id: int,
        search_date: date,
        before: datetime,
    ) -> Optional[dict[str, Any]]:
        """Return recent results from the team's current domestic league.

        Continental qualifiers do not contain enough same-competition team
        history for many clubs. The UEFA competition remains the goal-
        environment prior; this method supplies only team-level form and
        home/away observations. Both domestic source leagues are validated
        separately before a candidate can pass.
        """
        valid_team_id = _positive_integer(team_id)
        if (
            valid_team_id is None
            or not isinstance(search_date, date)
            or isinstance(search_date, datetime)
            or not isinstance(before, datetime)
            or before.tzinfo is None
        ):
            return None
        cache_key = (valid_team_id, search_date.isoformat())
        if cache_key in self._domestic_history_cache:
            return self._domestic_history_cache[cache_key]

        league_entries = self._football_get(
            "leagues",
            {"team": valid_team_id},
            f"Heimatliga Team {valid_team_id}",
        )
        recent = self._football_get(
            "fixtures",
            {
                "team": valid_team_id,
                "last": DOMESTIC_HISTORY_LAST_FIXTURES,
                "status": "FT",
                "timezone": "Europe/Zurich",
            },
            f"Teamhistorie {valid_team_id}",
        )
        if league_entries is None or recent is None:
            self._domestic_history_cache[cache_key] = None
            return None

        recent_by_league: dict[int, list[dict[str, Any]]] = {}
        for fixture in recent:
            league = fixture.get("league")
            teams = fixture.get("teams")
            kickoff = _fixture_kickoff(fixture)
            if (
                not isinstance(league, dict)
                or not isinstance(teams, dict)
                or kickoff is None
                or kickoff >= before.astimezone(timezone.utc)
            ):
                continue
            league_id = _positive_integer(league.get("id"))
            home = teams.get("home")
            away = teams.get("away")
            if (
                league_id is None
                or not isinstance(home, dict)
                or not isinstance(away, dict)
                or valid_team_id not in {home.get("id"), away.get("id")}
            ):
                continue
            goals = fixture.get("goals")
            if (
                not isinstance(goals, dict)
                or isinstance(goals.get("home"), bool)
                or isinstance(goals.get("away"), bool)
                or not isinstance(goals.get("home"), int)
                or not isinstance(goals.get("away"), int)
                or goals.get("home") < 0
                or goals.get("away") < 0
            ):
                continue
            recent_by_league.setdefault(league_id, []).append(fixture)

        candidates: list[tuple[tuple[int, int, int, int], int, int]] = []
        for entry in league_entries:
            league = entry.get("league")
            if not isinstance(league, dict) or league.get("type") != "League":
                continue
            league_id = _positive_integer(league.get("id"))
            if league_id is None or league_id in CONTINENTAL_LEAGUE_IDS:
                continue
            country = entry.get("country")
            country_name = (
                country.get("name")
                if isinstance(country, dict)
                else str(country or "")
            )
            if str(country_name).strip().casefold() == "world":
                continue
            seasons = entry.get("seasons")
            if not isinstance(seasons, list):
                continue
            for season in seasons:
                if not isinstance(season, dict):
                    continue
                year = _positive_integer(season.get("year"))
                if year is None:
                    continue
                contains_date = False
                try:
                    start = date.fromisoformat(str(season.get("start")))
                    end = date.fromisoformat(str(season.get("end")))
                    contains_date = start <= search_date <= end
                except (TypeError, ValueError):
                    pass
                is_current = season.get("current") is True
                if not contains_date and not is_current:
                    continue
                sample = len(recent_by_league.get(league_id, []))
                score = (
                    int(contains_date),
                    int(is_current),
                    sample,
                    int(league_id in LEAGUE_BY_ID),
                )
                candidates.append((score, league_id, year))

        if not candidates:
            self._domestic_history_cache[cache_key] = None
            return None
        _score, league_id, season = max(candidates, key=lambda item: item[0])
        fixtures = sorted(
            recent_by_league.get(league_id, []),
            key=lambda item: _fixture_kickoff(item)
            or datetime.min.replace(tzinfo=timezone.utc),
        )
        if not fixtures:
            self._domestic_history_cache[cache_key] = None
            return None
        result = {
            "league_id": league_id,
            "season": season,
            "fixtures": fixtures,
        }
        self._domestic_history_cache[cache_key] = result
        return result

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


def _scan_candidate_diagnostics(
    candidates: list[ChallengeCandidate],
    selected_market_kinds: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Describe every scan phase without implying that skipped gates failed."""
    configured_specs = [
        spec
        for spec in market_specs()
        if selected_market_kinds is None or spec.kind in selected_market_kinds
    ]
    configured_by_kind: dict[str, int] = {}
    for spec in configured_specs:
        configured_by_kind[spec.kind] = configured_by_kind.get(spec.kind, 0) + 1

    modeled_keys_by_kind: dict[str, set[str]] = {}
    candidate_counts_by_kind: dict[str, int] = {}
    model_blocked_counts: dict[str, int] = {}
    context_blocked_counts: dict[str, int] = {}
    blocked_counts: dict[str, int] = {}
    transfer_only: list[ChallengeCandidate] = []

    for candidate in candidates:
        spec = MARKET_BY_KEY.get(candidate.market_key)
        if spec is not None:
            modeled_keys_by_kind.setdefault(spec.kind, set()).add(candidate.market_key)
            candidate_counts_by_kind[spec.kind] = (
                candidate_counts_by_kind.get(spec.kind, 0) + 1
            )

        model_reasons = set(candidate.blocked_reasons)
        context_reasons = set(candidate.context.get("blocked_reasons", []))
        for reason in model_reasons:
            model_blocked_counts[reason] = model_blocked_counts.get(reason, 0) + 1
        if not model_reasons:
            for reason in context_reasons:
                context_blocked_counts[reason] = (
                    context_blocked_counts.get(reason, 0) + 1
                )
        for reason in model_reasons or context_reasons:
            blocked_counts[reason] = blocked_counts.get(reason, 0) + 1
        if model_reasons == {UNVALIDATED_TRANSFER_REASON}:
            transfer_only.append(candidate)

    market_coverage = []
    for kind in MARKET_KIND_LABELS:
        configured = configured_by_kind.get(kind, 0)
        if configured <= 0:
            continue
        market_coverage.append(
            {
                "kind": kind,
                "label": MARKET_KIND_LABELS[kind],
                "details": MARKET_KIND_DETAILS[kind],
                "configured": configured,
                "modeled": len(modeled_keys_by_kind.get(kind, set())),
                "candidates": candidate_counts_by_kind.get(kind, 0),
            }
        )

    transfer_only.sort(key=_candidate_rank, reverse=True)
    return {
        "market_candidates": len(candidates),
        "configured_market_definitions": len(configured_specs),
        "modeled_market_definitions": len(
            {candidate.market_key for candidate in candidates}
        ),
        "market_coverage": market_coverage,
        "model_blocked_counts": model_blocked_counts,
        "context_blocked_counts": context_blocked_counts,
        "blocked_counts": blocked_counts,
        "transfer_only_candidates": len(transfer_only),
        "transfer_only_fixtures": len(
            {candidate.fixture_id for candidate in transfer_only}
        ),
        "transfer_only_examples": [
            {
                "fixture_id": candidate.fixture_id,
                "kickoff": candidate.kickoff,
                "match": f"{candidate.home_team} vs {candidate.away_team}",
                "market": candidate.market,
                "selection": candidate.selection,
                "model_percent": round(candidate.probability * 100.0, 1),
                "conservative_percent": round(
                    candidate.conservative_probability * 100.0,
                    1,
                ),
                "evidence": round(candidate.evidence_score, 1),
            }
            for candidate in transfer_only[:10]
        ],
    }


def _split_provider_messages(errors: list[str]) -> tuple[list[str], list[str]]:
    """Separate optional xG coverage notes from operational provider errors."""
    coverage_notices = [
        error
        for error in errors
        if str(error).startswith("xG Liga ") and "Tormodell dominant" in str(error)
    ]
    operational_errors = [error for error in errors if error not in coverage_notices]
    return coverage_notices, operational_errors


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


def _price_candidate_pool(
    candidates: list[ChallengeCandidate],
    *,
    max_fixtures: int = MAX_PRICE_CHECK_FIXTURES,
) -> list[ChallengeCandidate]:
    """Keep several credible markets per fixture until the price gate."""
    if (
        isinstance(max_fixtures, bool)
        or not isinstance(max_fixtures, int)
        or max_fixtures < 1
    ):
        raise ValueError("max_fixtures must be a positive integer")
    eligible = [
        candidate
        for candidate in candidates
        if candidate_is_credible(candidate)
    ]
    fixture_ids = _ranked_fixture_ids(eligible, limit=max_fixtures)
    return _discovery_candidate_pool(eligible, fixture_ids)


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


def _context_scope_facts(
    candidates: list[ChallengeCandidate],
    context_fixture_ids: list[int],
    deferred_fixture_ids: set[int],
) -> dict[str, Any]:
    """Return consumer-safe facts about how much of the model pool was verified.

    A strict context gate can be fail-closed without pretending that every
    modeled fixture received H2H, injury and weather verification. These
    counters deliberately contain no provider messages or model internals.
    """

    base_fixture_ids = {candidate.fixture_id for candidate in candidates}
    selected_fixture_ids = set(context_fixture_ids) & base_fixture_ids
    deferred_ids = set(deferred_fixture_ids) & base_fixture_ids

    def data_is_complete(context: object) -> bool:
        if not isinstance(context, dict):
            return False
        terminal_reasons = {"Spiel hat bereits begonnen", "Anstoßzeit ist ungültig"}
        blocked_reasons = context.get("blocked_reasons")
        if isinstance(blocked_reasons, list) and terminal_reasons.intersection(
            str(reason) for reason in blocked_reasons
        ):
            return True
        required_statuses = {
            "model_transfer": {"passed", "blocked"},
            "h2h": {"passed", "blocked", "neutral"},
            "injuries": {"passed", "blocked"},
            "weather": {"passed", "blocked"},
        }
        for section, allowed in required_statuses.items():
            value = context.get(section)
            if not isinstance(value, dict) or value.get("status") not in allowed:
                return False
        return True

    incomplete_ids: set[int] = set()
    for fixture_id in selected_fixture_ids:
        fixture_candidates = [
            candidate for candidate in candidates if candidate.fixture_id == fixture_id
        ]
        if not fixture_candidates or not all(
            data_is_complete(candidate.context) for candidate in fixture_candidates
        ):
            incomplete_ids.add(fixture_id)

    unchecked_ids = base_fixture_ids - selected_fixture_ids - deferred_ids
    verified_ids = selected_fixture_ids - incomplete_ids
    statuses = {
        str(fixture_id): (
            "verified"
            if fixture_id in verified_ids
            else "data_incomplete"
            if fixture_id in incomplete_ids
            else "deferred"
            if fixture_id in deferred_ids
            else "unchecked"
        )
        for fixture_id in sorted(base_fixture_ids)
    }
    return {
        "base_fixture_count": len(base_fixture_ids),
        "context_verified_fixtures": len(verified_ids),
        "context_data_incomplete_fixtures": len(incomplete_ids),
        "context_unchecked_fixtures": len(unchecked_ids),
        "context_scope_complete": not (
            incomplete_ids or unchecked_ids or deferred_ids
        ),
        "context_fixture_statuses": statuses,
    }


def _run_challenge_scan_worker(
    provider: "ChallengeDataProvider",
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
    progress_cb=None,
) -> dict[str, Any]:
    """Run the model scan, then price only the final shortlist."""
    def model_progress(value: float, text: str) -> None:
        if progress_cb:
            progress_cb(min(0.90, max(0.0, float(value)) * 0.90), text)

    snapshot = scan_daily_challenge(
        provider,
        league_ids,
        search_date,
        max_fixtures,
        progress_cb=model_progress if progress_cb else None,
    )
    if progress_cb:
        progress_cb(0.92, "Marktquoten der Modellkandidaten werden verglichen")
    price_candidates = (
        snapshot.get("price_candidates")
        or snapshot.get("shortlist")
        or []
    )
    quotes, quote_errors = fetch_football_consensus(
        provider.api_key,
        price_candidates,
    )
    snapshot["reference_quotes"] = serialize_consensus_map(quotes)
    snapshot["quote_errors"] = quote_errors
    snapshot["price_checked_markets"] = len(price_candidates)
    snapshot["price_checked_fixtures"] = len(
        {candidate.fixture_id for candidate in price_candidates}
    )
    snapshot["price_checked_at"] = datetime.now(timezone.utc).isoformat()
    if progress_cb:
        progress_cb(1.0, "Modell- und Preisprüfung ist abgeschlossen")
    return snapshot


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
    """Holt bestätigte Aufstellungen nach, sobald sie veröffentlicht sind.

    Das ist nur eine Anzeigeaktualisierung; Modell, Shortlist und Preise
    bleiben unverändert.
    """
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
        st.toast("Bestätigte Aufstellungen wurden ergänzt.")
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

    Sobald Shortlist-Spiele ins Fenster rutschen, prüft die App Ausfälle,
    Wetter und ergänzendes H2H erneut. Das läuft nur, solange nichts freigegeben
    ist und die Seite offen bleibt.
    """
    snapshot = st.session_state.get("challenge_snapshot")
    if not isinstance(snapshot, dict):
        return
    if snapshot.get("shortlist"):
        # Fehlende Namen und Formationen werden nur für die Anzeige nachgeladen.
        _lineup_refresh_tick(snapshot, api_football_key, weather_key)
        return
    if not _auto_recheck_eligible(snapshot, search_date):
        return
    if not _auto_recheck_scope_allowed(league_ids):
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
                "Automatische Prüfung aktiv: Nächster relevanter Anpfiff um "
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
    st.toast("Neue Spieldaten sind verfügbar. Die Auswahl wird aktualisiert.")
    st.rerun()


def _league_season_segments(
    league_id: int,
    start_date: date,
    end_date: date,
) -> list[tuple[int, date, date]]:
    """Split a short search window whenever the provider season changes."""
    segments: list[tuple[int, date, date]] = []
    segment_start = start_date
    segment_season = current_season_start_year_for_id(league_id, start_date)
    current = start_date + timedelta(days=1)
    while current <= end_date:
        season = current_season_start_year_for_id(league_id, current)
        if season != segment_season:
            segments.append(
                (segment_season, segment_start, current - timedelta(days=1))
            )
            segment_start = current
            segment_season = season
        current += timedelta(days=1)
    segments.append((segment_season, segment_start, end_date))
    return segments


def scan_daily_challenge(
    provider: ChallengeDataProvider,
    league_ids: list[int],
    search_date: date,
    max_fixtures: int,
    *,
    search_end_date: Optional[date] = None,
    market_kinds: Optional[set[str]] = None,
    progress_cb=None,
) -> dict[str, Any]:
    """Run one explicit, quota-aware scan over at most fourteen days."""
    end_date = search_end_date or search_date
    _validate_scan_inputs(league_ids, search_date, max_fixtures, end_date)
    supported_market_kinds = {spec.kind for spec in market_specs()}
    selected_market_kinds = (
        {str(kind).strip() for kind in market_kinds if str(kind).strip()}
        if market_kinds is not None
        else None
    )
    if selected_market_kinds is not None:
        unknown_market_kinds = selected_market_kinds - supported_market_kinds
        if not selected_market_kinds or unknown_market_kinds:
            unknown = ", ".join(sorted(unknown_market_kinds)) or "leere Auswahl"
            raise ValueError(f"Unbekannter Markt-Scope: {unknown}")
    if progress_cb:
        progress_cb(
            0.01,
            f"Scan für {len(league_ids)} Ligen wird vorbereitet",
        )
    fixtures: list[dict[str, Any]] = []
    histories: dict[tuple[int, int], list[dict[str, Any]]] = {}
    coverage: dict[tuple[int, int], dict[str, bool]] = {}
    fixture_competitions: dict[int, tuple[int, int]] = {}

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
        for season, segment_start, segment_end in _league_season_segments(
            league_id,
            search_date,
            end_date,
        ):
            if segment_start == segment_end:
                upcoming = provider.upcoming_fixtures(
                    league_id,
                    season,
                    segment_start,
                )
            else:
                upcoming = provider.upcoming_fixtures_range(
                    league_id,
                    season,
                    segment_start,
                    segment_end,
                )
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
            for fixture in valid_upcoming:
                fixture_competitions[fixture["fixture"]["id"]] = (
                    league_id,
                    season,
                )
            if valid_upcoming:
                history = provider.completed_history(
                    league_id,
                    season,
                    valid_upcoming,
                )
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
                        provider.errors.append(
                            f"xG Liga {league_id}: Annotation fehlgeschlagen ({exc})"
                        )
                competition = (league_id, season)
                histories[competition] = history or []
                coverage[competition] = provider.coverage(league_id, season)
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
    if len(fixtures) > max_fixtures:
        provider.errors.append(
            f"Fixture-Limit erreicht: {len(fixtures)} gefunden, "
            f"nur die ersten {max_fixtures} modelliert"
        )
    fixtures = fixtures[:max_fixtures]

    history_items = [
        (competition, history)
        for competition, history in histories.items()
        if history
    ]
    validations: dict[tuple[int, int], dict[str, Any]] = {}
    history_total = len(history_items)
    for history_index, (competition, history) in enumerate(history_items):
        league_id, season = competition
        if progress_cb:
            progress_cb(
                0.52 + 0.09 * history_index / max(1, history_total),
                f"Walk-forward-Validierung {history_index + 1}/{history_total}",
            )
        validations[competition] = _cached_market_validation(
            league_id,
            season,
            history,
        )
    if progress_cb:
        progress_cb(0.61, "Wahrscheinlichkeiten werden kalibriert")
    calibrations: dict[tuple[int, int], dict[str, Any]] = {}
    for history_index, (competition, history) in enumerate(history_items):
        league_id, season = competition
        if progress_cb:
            progress_cb(
                0.61 + 0.09 * history_index / max(1, history_total),
                f"Kalibrierung {history_index + 1}/{history_total}",
            )
        calibrations[competition] = _cached_market_calibration(
            league_id,
            season,
            history,
        )

    fixture_team_histories: dict[int, list[dict[str, Any]]] = {}
    fixture_domestic_profiles: dict[int, tuple[tuple[int, int], ...]] = {}
    continental_fixture_ids = {
        fixture["fixture"]["id"]
        for fixture in fixtures
        if fixture.get("league", {}).get("id") in CONTINENTAL_LEAGUE_IDS
    }
    fallback_targets = []
    for fixture in fixtures:
        league_id = fixture.get("league", {}).get("id")
        if league_id not in CONTINENTAL_LEAGUE_IDS:
            continue
        competition = fixture_competitions.get(fixture["fixture"]["id"])
        if fixture_market_probabilities(
            fixture,
            histories.get(competition, []),
        ) is None:
            fallback_targets.append(fixture)

    fallback_failed: set[int] = set()
    for fallback_index, fixture in enumerate(fallback_targets):
        fixture_id = fixture["fixture"]["id"]
        if progress_cb:
            progress_cb(
                0.70 + 0.04 * fallback_index / max(1, len(fallback_targets)),
                (
                    "Heimatliga-Historie für UEFA-Spiel "
                    f"{fallback_index + 1}/{len(fallback_targets)}"
                ),
            )
        kickoff = _fixture_kickoff(fixture)
        fixture_search_date = (
            kickoff.astimezone(CHALLENGE_TIMEZONE).date()
            if kickoff is not None
            else search_date
        )
        fallback_data = _continental_team_history(
            provider,
            fixture,
            fixture_search_date,
        )
        league_id = fixture.get("league", {}).get("id")
        team_history = (
            fallback_data.get("fixtures")
            if isinstance(fallback_data, dict)
            else None
        )
        profiles = (
            fallback_data.get("profiles")
            if isinstance(fallback_data, dict)
            else None
        )
        if (
            isinstance(team_history, list)
            and team_history
            and isinstance(profiles, tuple)
            and len(profiles) == 2
            and fixture_market_probabilities(
                fixture,
                histories.get(fixture_competitions.get(fixture_id), []),
                team_history=team_history,
            )
            is not None
        ):
            fixture_team_histories[fixture_id] = team_history
            fixture_domestic_profiles[fixture_id] = profiles
        else:
            fallback_failed.add(fixture_id)

    fixture_by_id = {
        fixture["fixture"]["id"]: fixture
        for fixture in fixtures
    }
    transfer_probe = _transfer_probe_validation_map()
    validation_target_fixture_ids: set[int] = set()
    for fixture_id, team_history in fixture_team_histories.items():
        fixture = fixture_by_id[fixture_id]
        competition = fixture_competitions.get(fixture_id)
        probe_candidates = build_fixture_candidates(
            fixture,
            histories.get(competition, []),
            transfer_probe,
            {},
            team_history=team_history,
        )
        if any(candidate.base_eligible for candidate in probe_candidates):
            validation_target_fixture_ids.add(fixture_id)

    domestic_requests: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for fixture_id, profiles in fixture_domestic_profiles.items():
        if fixture_id not in validation_target_fixture_ids:
            continue
        fixture = fixture_by_id[fixture_id]
        for profile in set(profiles):
            domestic_requests.setdefault(profile, []).append(fixture)

    domestic_validations: dict[tuple[int, int], dict[str, ValidationMetrics]] = {}
    domestic_calibrations: dict[tuple[int, int], dict[str, Any]] = {}
    domestic_total = len(domestic_requests)
    for domestic_index, ((league_id, season), source_fixtures) in enumerate(
        domestic_requests.items()
    ):
        if progress_cb:
            progress_cb(
                0.74 + 0.08 * domestic_index / max(1, domestic_total),
                (
                    "Heimatliga-Validierung "
                    f"{domestic_index + 1}/{domestic_total}"
                ),
            )
        competition = (league_id, season)
        if histories.get(competition):
            history = histories[competition]
            validation = validations.get(competition, {})
            calibration = calibrations.get(competition, {})
        else:
            history = provider.completed_history(
                league_id,
                season,
                source_fixtures,
            ) or []
            validation = (
                _cached_market_validation(league_id, season, history)
                if history
                else {}
            )
            calibration = (
                _cached_market_calibration(league_id, season, history)
                if history
                else {}
            )
        domestic_validations[(league_id, season)] = validation
        domestic_calibrations[(league_id, season)] = calibration

    fixture_validations: dict[int, dict[str, ValidationMetrics]] = {}
    fixture_calibrations: dict[int, dict[str, Any]] = {}
    for fixture_id, profiles in fixture_domestic_profiles.items():
        unique_profiles = list(dict.fromkeys(profiles))
        fixture_validations[fixture_id] = _conservative_validation_map(
            [
                domestic_validations.get(profile, {})
                for profile in unique_profiles
            ]
        )
        fixture_calibrations[fixture_id] = _conservative_calibration_map(
            [
                domestic_calibrations.get(profile, {})
                for profile in unique_profiles
            ]
        )

    if progress_cb:
        progress_cb(
            0.82,
            f"{len(fixtures)} Spiele werden mathematisch modelliert",
        )
    all_candidates: list[ChallengeCandidate] = []
    fixture_total = len(fixtures)
    progress_stride = max(1, fixture_total // 20)
    for fixture_index, fixture in enumerate(fixtures):
        fixture_id = fixture["fixture"]["id"]
        competition = fixture_competitions.get(fixture_id)
        validation = (
            fixture_validations.get(fixture_id, {})
            if fixture_id in fixture_team_histories
            else validations.get(competition, {})
        )
        calibration = (
            fixture_calibrations.get(fixture_id, {})
            if fixture_id in fixture_team_histories
            else calibrations.get(competition, {})
        )
        fixture_candidates = build_fixture_candidates(
            fixture,
            histories.get(competition, []),
            validation,
            calibration,
            team_history=fixture_team_histories.get(fixture_id),
            model_scope=(
                MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED
                if fixture_id in fixture_team_histories
                else MODEL_SCOPE_SAME_COMPETITION
            ),
        )
        if fixture_id in fixture_team_histories:
            for candidate in fixture_candidates:
                candidate.reasons.append(
                    "Teamform und Heim/Auswärts-Stichprobe aus den jeweiligen Heimatligen"
                )
        all_candidates.extend(fixture_candidates)
        if progress_cb and (
            (fixture_index + 1) % progress_stride == 0
            or fixture_index + 1 == fixture_total
        ):
            progress_cb(
                0.82 + 0.02 * (fixture_index + 1) / max(1, fixture_total),
                f"Spiel {fixture_index + 1}/{fixture_total} modelliert",
            )

    if selected_market_kinds is not None:
        all_candidates = [
            candidate
            for candidate in all_candidates
            if MARKET_BY_KEY[candidate.market_key].kind in selected_market_kinds
        ]

    base_candidates = [candidate for candidate in all_candidates if candidate.base_eligible]
    context_candidates = base_candidates
    deferred_context_fixture_ids: set[int] = set()
    if end_date > search_date:
        context_deadline = datetime.now(timezone.utc) + timedelta(
            days=WEATHER_CONTEXT_HORIZON_DAYS
        )
        context_candidates = []
        for candidate in base_candidates:
            kickoff = _candidate_kickoff(candidate)
            if kickoff is not None and kickoff <= context_deadline:
                context_candidates.append(candidate)
            else:
                deferred_context_fixture_ids.add(candidate.fixture_id)
    context_fixture_ids = _ranked_fixture_ids(context_candidates)
    if progress_cb:
        progress_cb(
            0.85,
            f"Live-Kontext für {len(context_fixture_ids)} Top-Spiele",
        )
    injuries = provider.injuries_by_fixture(context_fixture_ids) if context_fixture_ids else {}
    details = provider.details_by_fixture(context_fixture_ids) if context_fixture_ids else {}
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
            reason = (
                "Pflichtkontext liegt noch außerhalb des Fünf-Tage-Fensters"
                if candidate.fixture_id in deferred_context_fixture_ids
                else "Nicht in der begrenzten Kontext-Shortlist"
            )
            candidate.context = {
                "passed": False,
                "blocked_reasons": [reason],
            }
            contextualized.append(candidate)
            continue
        detail = details.get(candidate.fixture_id) or {}
        league_coverage = coverage.get(
            fixture_competitions.get(candidate.fixture_id),
            {},
        )
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
            require_lineups=False,
        )
        contextualized.append(candidate)

    price_candidates = _price_candidate_pool(contextualized)
    shortlist = select_shortlist(price_candidates, max_candidates=3)
    model_ticket = select_model_ticket(price_candidates)
    base_shortlist = sorted(base_candidates, key=_candidate_rank, reverse=True)[:10]
    discovery_candidates = _discovery_candidate_pool(
        base_candidates,
        context_fixture_ids,
    )
    diagnostics = _scan_candidate_diagnostics(
        all_candidates,
        selected_market_kinds,
    )
    context_scope_facts = _context_scope_facts(
        contextualized,
        context_fixture_ids,
        deferred_context_fixture_ids,
    )
    coverage_notices, operational_errors = _split_provider_messages(provider.errors)
    if progress_cb:
        progress_cb(
            1.0,
            f"Fertig: {len(fixtures)} Spiele, {len(shortlist)} Freigaben",
        )
    return {
        "version": CHALLENGE_SNAPSHOT_VERSION,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "scope": _scope_signature(
            league_ids,
            search_date,
            max_fixtures,
            end_date,
        ),
        "search_date": search_date.isoformat(),
        "search_end_date": end_date.isoformat(),
        "market_kinds": (
            sorted(selected_market_kinds)
            if selected_market_kinds is not None
            else None
        ),
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
        "continental_fixtures_found": len(continental_fixture_ids),
        "continental_fallback_modeled": len(fixture_team_histories),
        "continental_fallback_failed": len(fallback_failed),
        "continental_validation_fixtures": len(validation_target_fixture_ids),
        "base_candidates": len(base_candidates),
        "context_fixtures": len(context_fixture_ids),
        "deferred_context_fixtures": len(deferred_context_fixture_ids),
        **context_scope_facts,
        "approved_candidates": len(shortlist),
        "shortlist": shortlist,
        "price_candidates": price_candidates,
        "price_candidate_count": len(price_candidates),
        "price_fixture_count": len(
            {candidate.fixture_id for candidate in price_candidates}
        ),
        "base_shortlist": base_shortlist,
        "discovery_candidates": discovery_candidates,
        "model_ticket": model_ticket,
        **diagnostics,
        "coverage_notices": coverage_notices,
        "operational_errors": operational_errors,
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
            require_lineups=False,
        )
        contextualized.append(candidate)

    price_candidates = _price_candidate_pool(contextualized)
    shortlist = select_shortlist(price_candidates, max_candidates=max_candidates)
    blocked_counts: dict[str, int] = {}
    for candidate in contextualized:
        reasons = candidate.blocked_reasons or candidate.context.get(
            "blocked_reasons",
            [],
        )
        for reason in set(reasons):
            blocked_counts[reason] = blocked_counts.get(reason, 0) + 1
    context_scope_facts = _context_scope_facts(contextualized, fixture_ids, set())
    coverage_notices, operational_errors = _split_provider_messages(provider.errors)
    return {
        "checked_at": checked_at.isoformat(),
        "fixture_ids": fixture_ids,
        "shortlist": shortlist,
        "price_candidates": price_candidates,
        "candidates": contextualized,
        "blocked_counts": blocked_counts,
        **context_scope_facts,
        "coverage_notices": coverage_notices,
        "operational_errors": operational_errors,
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


CHALLENGE_RESULT_LABELS = {
    "PENDING": "Offen",
    "WON": "Gewonnen",
    "LOST": "Verloren",
    "VOID": "Storniert",
}


def _ticket_description(ticket: dict[str, Any]) -> str:
    labels: list[str] = []
    for leg in ticket.get("legs") or []:
        if leg.get("manual"):
            label = str(leg.get("label") or "Manuell nachgetragene Wette").strip()
        else:
            match = str(leg.get("match") or "Spiel").strip()
            market = str(leg.get("market") or "Markt").strip()
            selection = str(leg.get("selection") or "Auswahl").strip()
            label = f"{match}: {market} - {selection}"
        if label:
            labels.append(label)
    return " + ".join(labels) or "Wette ohne Beschreibung"


def _render_ledger_notice() -> None:
    notice = st.session_state.pop("challenge_ledger_notice", None)
    if notice:
        st.success(str(notice))


def _render_pending_ticket_actions(
    ledger: ChallengeLedger,
    *,
    key_prefix: str,
) -> bool:
    pending = ledger.pending_tickets()
    if not pending:
        return False

    ticket = pending[0]
    st.subheader("Offene 15K-Wette")
    with st.container(border=True):
        st.markdown(f"**{_ticket_description(ticket)}**")
        st.caption(
            f"Ticket #{ticket['id']} · {ticket['analysis_date']} · "
            f"Einsatz {_format_euro(ticket['stake'])} · "
            f"Gesamtquote {ticket['total_odds']:.2f} · "
            f"mögliche Auszahlung {_format_euro(ticket['stake'] * ticket['total_odds'])}"
        )
        result = _segmented(
            "Ergebnis",
            ["Gewonnen", "Verloren", "Storniert"],
            f"{key_prefix}_settlement",
            "Gewonnen",
        )
        if st.button(
            "Ergebnis verbuchen",
            type="primary",
            width="stretch",
            key=f"{key_prefix}_settle_button",
        ):
            status = {
                "Gewonnen": "WON",
                "Verloren": "LOST",
                "Storniert": "VOID",
            }[result]
            try:
                settled = ledger.settle_ticket(int(ticket["id"]), status)
                balance = ledger.settings()["current_balance"]
                st.session_state["challenge_ledger_notice"] = (
                    f"Ticket #{settled['id']} als {result.lower()} verbucht. "
                    f"Neues Guthaben: {_format_euro(balance)}."
                )
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
    return True


@st.dialog("Vergangene 15K-Wette nachtragen")
def _render_manual_result_dialog(ledger: ChallengeLedger) -> None:
    settings = ledger.settings()
    if ledger.pending_tickets():
        st.warning("Zuerst die offene 15K-Wette abrechnen.")
        return
    suggested_stake = challenge_stake_cap(
        settings["current_balance"],
        settings["stake_fraction"],
    )
    maximum_stake = float(settings["current_balance"])
    if maximum_stake < 0.01:
        st.warning("Kein Challenge-Guthaben für eine Nachtragung verfügbar.")
        return

    st.caption(
        "Für eine Nachtragung zählt der tatsächlich damals gespielte Einsatz. "
        "Der heutige Einsatzanteil begrenzt nur neue 15K-Tickets."
    )

    with st.form("challenge_manual_result_form"):
        bet_date = st.date_input(
            "Wettdatum",
            value=_challenge_today() - timedelta(days=1),
            max_value=_challenge_today(),
        )
        description = st.text_input(
            "Gespielte Wette",
            placeholder="z. B. Team A - Team B: Über 1,5 Tore",
            max_chars=300,
        )
        values = st.columns(2)
        stake = values[0].number_input(
            "Tatsächlicher Einsatz",
            min_value=0.01,
            max_value=maximum_stake,
            value=suggested_stake,
            step=1.0,
            format="%.2f",
        )
        total_odds = values[1].number_input(
            "Tatsächliche Gesamtquote",
            min_value=1.01,
            max_value=100.0,
            value=2.0,
            step=0.01,
            format="%.2f",
        )
        result = st.radio(
            "Ergebnis",
            ["Gewonnen", "Verloren", "Storniert"],
            horizontal=True,
        )
        submitted = st.form_submit_button(
            "Wette nachtragen",
            type="primary",
            width="stretch",
        )
    st.caption(
        "Die Nachtragung aktualisiert das Guthaben und bleibt im Verlauf als "
        "manuell erfasst gekennzeichnet."
    )
    if not submitted:
        return

    status = {
        "Gewonnen": "WON",
        "Verloren": "LOST",
        "Storniert": "VOID",
    }[result]
    try:
        ticket_id = ledger.record_manual_result(
            bet_date.isoformat(),
            description,
            stake,
            total_odds,
            status,
        )
        balance = ledger.settings()["current_balance"]
        st.session_state["challenge_ledger_notice"] = (
            f"Vergangene Wette #{ticket_id} als {result.lower()} nachgetragen. "
            f"Neues Guthaben: {_format_euro(balance)}."
        )
        st.rerun(scope="app")
    except ValueError as exc:
        st.warning(str(exc))


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
    if stake_percent > 5:
        st.warning(
            f"{stake_percent} % je Ticket überschreitet den vorsichtigen "
            "Sicherheitswert. Das ist eine bewusst aggressive "
            "Challenge-Simulation und keine professionelle "
            "Echtgeld-Einsatzempfehlung."
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
                "Status": CHALLENGE_RESULT_LABELS.get(ticket["status"], ticket["status"]),
                "Wette": _ticket_description(ticket),
                "Erfasst": (
                    "Nachgetragen"
                    if ticket.get("entry_source") == "MANUAL"
                    else "15K-Tagestipp"
                ),
                "Legs": len(ticket["legs"]),
                "Quote": round(ticket["total_odds"], 2),
                "Einsatz €": ticket["stake"],
                "Auszahlung €": ticket["payout"],
            }
            for ticket in tickets
        ]
    )
    st.dataframe(frame, width="stretch", hide_index=True)

    _render_pending_ticket_actions(ledger, key_prefix="challenge_history")


def _format_kickoff(raw: str) -> str:
    """'2026-07-31T18:30:00+00:00' -> '31.07. 20:30' (lokale Zeit)."""
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(CHALLENGE_TIMEZONE).strftime("%d.%m. %H:%M")
    except (ValueError, TypeError):
        return str(raw or "?")


def _recommendation_day_label(
    raw_search_date: Any,
    *,
    today: Optional[date] = None,
) -> str:
    """Return the day label for the date that was actually scanned."""
    return german_day_label(
        raw_search_date,
        today=today or _challenge_today(),
    )


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


def scan_no_result_copy(
    snapshot: dict[str, Any],
    *,
    day_label: str,
    recommendation_label: str,
) -> tuple[str, str]:
    """Explain the furthest completed gate instead of blaming skipped checks."""
    found = int(snapshot.get("fixtures_found") or 0)
    modeled = int(snapshot.get("fixtures_modeled") or 0)
    market_candidates = int(snapshot.get("market_candidates") or 0)
    base_candidates = int(snapshot.get("base_candidates") or 0)
    context_fixtures = int(snapshot.get("context_fixtures") or 0)
    deferred_context = int(snapshot.get("deferred_context_fixtures") or 0)
    headline = f"{day_label} keine belastbare {recommendation_label}."

    if found <= 0:
        detail = "Im gewählten Zeitraum wurden keine verwertbaren Spiele gefunden."
    elif modeled <= 0:
        detail = (
            f"{found} Spiele wurden gefunden, aber für keines reichte die Statistik "
            "für eine Modellbewertung."
        )
    elif market_candidates > 0 and base_candidates <= 0:
        detail = (
            f"{market_candidates} Marktkandidaten aus {modeled} modellierten Spielen "
            "scheiterten bereits an Modell- oder Walk-forward-Prüfungen. H2H, "
            "Ausfälle und Wetter wurden deshalb nicht abgefragt."
        )
    elif base_candidates > 0 and context_fixtures <= 0 and deferred_context > 0:
        detail = (
            f"{base_candidates} Marktkandidaten bestanden die Modellprüfung, liegen "
            "aber noch außerhalb des verfügbaren Kontextfensters."
        )
    elif base_candidates > 0:
        detail = (
            f"{base_candidates} Marktkandidaten bestanden die Modellprüfung; "
            f"für {context_fixtures} Spiele wurde Live-Kontext geprüft. Dort blieb "
            "keine Auswahl freigabefähig."
        )
    else:
        detail = (
            f"{found} Spiele wurden gefunden und {modeled} modelliert, aber es "
            "entstand kein freigabefähiger Marktkandidat."
        )
    return headline, detail


def render_football_scan_diagnostics(
    snapshot: dict[str, Any],
    *,
    approved_count: Optional[int] = None,
) -> None:
    """Render the shared football gate and market coverage audit."""
    approved = (
        int(snapshot.get("approved_candidates") or 0)
        if approved_count is None
        else int(approved_count)
    )
    metric_values = (
        ("Spiele gefunden", int(snapshot.get("fixtures_found") or 0)),
        ("Spiele modelliert", int(snapshot.get("fixtures_modeled") or 0)),
        ("Marktprüfungen", int(snapshot.get("market_candidates") or 0)),
        ("Modell bestanden", int(snapshot.get("base_candidates") or 0)),
        ("Kontext-Spiele", int(snapshot.get("context_fixtures") or 0)),
        ("Freigegeben", approved),
    )
    for offset in range(0, len(metric_values), 3):
        columns = st.columns(3)
        for column, (label, value) in zip(columns, metric_values[offset : offset + 3]):
            column.metric(label, value)

    deferred_context = int(snapshot.get("deferred_context_fixtures") or 0)
    if deferred_context:
        st.caption(
            f"{deferred_context} spätere Spiele liegen noch außerhalb des "
            "verfügbaren Kontextfensters."
        )
    continental = int(snapshot.get("continental_fixtures_found") or 0)
    if continental:
        fallback_modeled = int(snapshot.get("continental_fallback_modeled") or 0)
        fallback_failed = int(snapshot.get("continental_fallback_failed") or 0)
        message = (
            f"UEFA-Qualifikation: {continental} Spiele gefunden, "
            f"{fallback_modeled} mit Heimatliga-Historie modelliert"
        )
        if fallback_failed:
            message += f", {fallback_failed} ohne ausreichende Teamstichprobe"
        st.caption(message + ".")

    configured = int(snapshot.get("configured_market_definitions") or 0)
    modeled = int(snapshot.get("modeled_market_definitions") or 0)
    coverage = snapshot.get("market_coverage")
    if isinstance(coverage, list) and coverage:
        st.markdown("**Geprüfte Wettarten**")
        st.caption(
            f"{modeled} von {configured} konfigurierten Marktdefinitionen konnten "
            "für mindestens ein Spiel berechnet werden."
        )
        coverage_frame = pd.DataFrame(
            [
                {
                    "Wettart": item.get("label"),
                    "Ausprägungen": item.get("details"),
                    "Konfiguriert": item.get("configured", 0),
                    "Berechnet": item.get("modeled", 0),
                    "Prüfungen": item.get("candidates", 0),
                }
                for item in coverage
            ]
        )
        st.dataframe(coverage_frame, width="stretch", hide_index=True)

    model_blocked_counts = snapshot.get("model_blocked_counts")
    if not isinstance(model_blocked_counts, dict):
        model_blocked_counts = snapshot.get("blocked_counts")
    if isinstance(model_blocked_counts, dict) and model_blocked_counts:
        st.markdown("**Modell- und Validierungssperren**")
        st.caption(
            "Gezählt werden Marktkandidaten; ein Kandidat kann mehrere Sperrgründe haben."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"Sperrgrund": reason, "Marktkandidaten": count}
                    for reason, count in sorted(
                        model_blocked_counts.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    context_blocked_counts = snapshot.get("context_blocked_counts")
    if isinstance(context_blocked_counts, dict) and context_blocked_counts:
        st.markdown("**Kontextsperren**")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Sperrgrund": reason, "Marktkandidaten": count}
                    for reason, count in sorted(
                        context_blocked_counts.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    transfer_only = int(snapshot.get("transfer_only_candidates") or 0)
    transfer_examples = snapshot.get("transfer_only_examples")
    if transfer_only and isinstance(transfer_examples, list):
        st.markdown("**Nur am UEFA-Transfergate gesperrt - keine Empfehlungen**")
        st.caption(
            f"{transfer_only} Marktkandidaten bestanden die übrigen Modellprüfungen. "
            "Ihr Heimatliga-Modell ist für UEFA-Duelle noch nicht historisch validiert; "
            "der Live-Kontext wurde daher nicht geprüft."
        )
        if transfer_examples:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Spiel": item.get("match"),
                            "Markt": item.get("market"),
                            "Auswahl": item.get("selection"),
                            "Konservativ %": item.get("conservative_percent"),
                            "Evidenz": item.get("evidence"),
                        }
                        for item in transfer_examples
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

    coverage_notices = snapshot.get("coverage_notices")
    if isinstance(coverage_notices, list) and coverage_notices:
        st.caption("Datenabdeckung: " + " | ".join(map(str, coverage_notices)))
    operational_errors = snapshot.get("operational_errors")
    if isinstance(operational_errors, list) and operational_errors:
        st.warning(
            f"{len(operational_errors)} technische Provider-Prüfungen waren unvollständig."
        )
        st.dataframe(
            pd.DataFrame({"Provider-Meldung": operational_errors}),
            width="stretch",
            hide_index=True,
        )


def _render_candidate_context(candidate: ChallengeCandidate) -> None:
    context = candidate.context
    h2h = context.get("h2h", {})
    injuries = context.get("injuries", {})
    weather = context.get("weather", {})
    checks = st.columns(4)
    h2h_hits = h2h.get("hits")
    h2h_matches = int(h2h.get("matches") or 0)
    if h2h.get("status") == "neutral":
        h2h_value = f"Neutral ({h2h_matches})"
    elif h2h_hits is not None:
        h2h_value = f"{h2h_hits}/{h2h_matches}"
    else:
        h2h_value = "n/a"
    checks[0].metric(
        "H2H",
        h2h_value,
        help=h2h.get("reason"),
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
    else:
        st.caption("Aufstellungen: noch nicht veröffentlicht")


def _automatic_challenge_ticket(
    shortlist: list[ChallengeCandidate],
    reference_quotes: dict[str, MarketConsensus],
    *,
    now: Optional[datetime] = None,
):
    """Build a ticket only from fresh, exact, conservative market prices."""
    odds_by_candidate: dict[str, float] = {}
    metadata_by_candidate: dict[str, dict[str, Any]] = {}
    statuses = {}
    for candidate in shortlist:
        quote = reference_quotes.get(candidate.candidate_id)
        status = reference_price_status(
            quote,
            candidate.minimum_odds,
            now=now,
        )
        statuses[candidate.candidate_id] = status
        if quote is None or status.usable_odds is None:
            continue
        odds_by_candidate[candidate.candidate_id] = status.usable_odds
        metadata_by_candidate[candidate.candidate_id] = {
            "source": quote.source,
            "quoted_at": quote.quoted_at,
            "fetched_at": quote.fetched_at,
            "bookmaker_count": quote.bookmaker_count,
            # The selected price is the lower quartile. The best price is
            # retained only as transparent evidence, never for ticket math.
            "quote_low": quote.conservative_odds,
            "quote_high": quote.best_odds,
        }
    return (
        select_quoted_ticket(
            shortlist,
            odds_by_candidate,
            quote_metadata_by_candidate=metadata_by_candidate,
            now=now,
        ),
        statuses,
    )


def _render_challenge_candidate(
    candidate: ChallengeCandidate,
    quote: Optional[MarketConsensus],
    status,
    index: int,
) -> None:
    st.markdown(f"### {index}. {candidate.market}: {candidate.selection}")
    st.caption(f"{candidate.home_team} vs {candidate.away_team}")
    summary = st.columns(4)
    summary[0].metric("Modell", f"{candidate.probability * 100:.1f} %")
    summary[1].metric(
        "Vorsichtige Prognose",
        f"{candidate.conservative_probability * 100:.1f} %",
    )
    summary[2].metric("Mindestquote", f"{candidate.minimum_odds:.2f}")
    summary[3].metric(
        "Aktuelle Quote",
        f"{quote.conservative_odds:.2f}" if quote is not None else "offen",
    )
    if status.code == "PLAYABLE" and quote is not None:
        st.success(
            f"PASSENDE QUOTE: {quote.conservative_odds:.2f}. Die Auswahl wird "
            "erst als 15K-Tagestipp angezeigt, wenn auch das gesamte Ticket passt."
        )
    elif status.code == "BORDERLINE" and quote is not None:
        st.info(
            f"MODELL-AUSWAHL BLEIBT: Nur einzelne Anbieter erreichen "
            f"mindestens {candidate.minimum_odds:.2f}; der Preis ist deshalb "
            "noch nicht zuverlässig bestätigt."
        )
    elif status.code == "TOO_LOW" and quote is not None:
        st.info(
            f"MODELL-AUSWAHL BLEIBT: Die beste beobachtete Quote "
            f"{quote.best_odds:.2f} liegt unter der benötigten Quote "
            f"{candidate.minimum_odds:.2f}. Nicht zu diesem Preis spielen."
        )
    else:
        reason = {
            "THIN": "Zu wenige Anbieter für eine automatische Preisfreigabe",
            "STALE": "Der Marktvergleich ist nicht mehr aktuell",
            "UNAVAILABLE": "Aktuell liegt keine exakt passende Vergleichsquote vor",
            "INVALID_MINIMUM": "Die Mindestquote ist nicht belastbar",
        }.get(status.code, "Keine automatische Preisfreigabe")
        st.info(
            f"MODELL-AUSWAHL: {candidate.selection}. {reason}. Ohne "
            "belastbaren Preis kann der mögliche Spielausgang gezeigt, aber "
            "kein Einsatz bewertet werden."
        )
    _render_candidate_context(candidate)


def _render_price_check(
    snapshot: dict[str, Any],
    ledger: ChallengeLedger,
    settings: dict[str, Any],
) -> None:
    shortlist: list[ChallengeCandidate] = snapshot["shortlist"]
    if not shortlist:
        st.info("Für diesen Spieltag gibt es aktuell keinen 15K-Tipp.")
        st.caption(
            "Aktuell erfüllt keine Auswahl alle Voraussetzungen für einen "
            "15K-Tipp."
        )
        return

    price_candidates: list[ChallengeCandidate] = (
        snapshot.get("price_candidates") or shortlist
    )
    reference_quotes = deserialize_consensus_map(snapshot.get("reference_quotes"))
    ticket, statuses = _automatic_challenge_ticket(
        price_candidates,
        reference_quotes,
    )

    st.subheader("Auswahlen und Quoten")
    st.caption(
        "Diese Auswahlen sind noch keine Tipps. Erst eine passende aktuelle "
        "Quote kann daraus einen 15K-Tagestipp machen."
    )
    if any(
        MARKET_BY_KEY[candidate.market_key].kind in COUNT_MARKET_KINDS
        for candidate in price_candidates
    ):
        st.warning(
            "Bei Ecken und Karten können Abrechnungsregeln zwischen Anbietern "
            "abweichen. Auswahl und Linie müssen beim eigenen Anbieter identisch sein."
        )

    for index, candidate in enumerate(shortlist, start=1):
        _render_challenge_candidate(
            candidate,
            reference_quotes.get(candidate.candidate_id),
            statuses[candidate.candidate_id],
            index,
        )
        if index < len(shortlist):
            st.divider()

    if ticket is None:
        st.warning(
            "Aktuell gibt es keinen 15K-Tagestipp: Kein automatisch geprüfter "
            "Preis ergibt ein freigegebenes Ticket zwischen Quote 2,00 und 3,00."
        )
        return

    st.subheader("15K-Tagestipp")
    ticket_metrics = st.columns(4)
    ticket_metrics[0].metric("Spiele", len(ticket.legs))
    ticket_metrics[1].metric("Gesamtquote", f"{ticket.total_odds:.2f}")
    ticket_metrics[2].metric(
        "Vorsichtige Prognose",
        f"{ticket.joint_probability * 100:.1f} %",
    )
    ticket_metrics[3].metric(
        "Einsatz",
        _format_euro(settings["current_balance"] * settings["stake_fraction"]),
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Match": (
                        f"{leg.candidate.home_team} vs {leg.candidate.away_team}"
                    ),
                    "Empfehlung": (
                        f"{leg.candidate.market}: {leg.candidate.selection}"
                    ),
                    "Referenzquote": round(leg.odds, 2),
                    "Mindestquote": round(leg.candidate.minimum_odds, 2),
                }
                for leg in ticket.legs
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    if len(ticket.legs) > 1:
        st.caption(
            f"Zusätzlicher Kombi-Modellfehlerabschlag: Faktor "
            f"{ticket.model_dependency_factor:.3f}. "
            f"Abhängigkeitsfreie Fréchet-Stressgrenze: "
            f"{ticket.dependence_floor_probability * 100:.1f} %."
        )

    current_balance = settings["current_balance"]
    stake_fraction = settings["stake_fraction"]
    suggested_stake = ticket_stake(ticket, current_balance, stake_fraction)
    risk_stake = risk_managed_ticket_stake(ticket, current_balance)
    if suggested_stake <= 0:
        st.error("Kein verfügbares Challenge-Guthaben für diesen Tipp.")
        return
    if ledger.pending_tickets():
        st.info(
            "Dieser Tagestipp kann erst als gespielt markiert werden, wenn die "
            "offene 15K-Wette oben abgerechnet ist."
        )
        return

    entry_fingerprint = hashlib.sha256(
        (
            f"{snapshot['search_date']}:{current_balance:.2f}:"
            + ":".join(leg.candidate.candidate_id for leg in ticket.legs)
        ).encode("utf-8")
    ).hexdigest()[:12]
    entry_fields = st.columns(2)
    played_stake = entry_fields[0].number_input(
        "Tatsächlicher Einsatz",
        min_value=0.01,
        max_value=challenge_stake_cap(current_balance, stake_fraction),
        value=suggested_stake,
        step=1.0,
        format="%.2f",
        key=f"challenge_played_stake_{entry_fingerprint}",
    )
    played_total_odds = entry_fields[1].number_input(
        "Tatsächliche Gesamtquote",
        min_value=1.01,
        max_value=100.0,
        value=round(ticket.total_odds, 2),
        step=0.01,
        format="%.2f",
        key=f"challenge_played_odds_{entry_fingerprint}",
    )
    actual_fraction = played_stake / current_balance
    log_growth = (
        ticket.joint_probability
        * math.log1p(actual_fraction * (played_total_odds - 1.0))
        + (1.0 - ticket.joint_probability) * math.log1p(-actual_fraction)
    )
    played_expected_roi = ticket.joint_probability * played_total_odds - 1.0
    price_is_valid = (
        TARGET_ODDS_MIN <= played_total_odds <= TARGET_ODDS_MAX
        and played_expected_roi >= MIN_LEG_EXPECTED_ROI
    )
    win_balance = (
        current_balance - played_stake + played_stake * played_total_odds
    )
    loss_balance = current_balance - played_stake
    wins_remaining = consecutive_wins_to_target(
        current_balance,
        settings["target_balance"],
        played_total_odds,
        actual_fraction,
    )
    stake_metrics = st.columns(4)
    stake_metrics[0].metric("Challenge-Einsatz", _format_euro(played_stake))
    stake_metrics[1].metric("Saldo bei Gewinn", _format_euro(win_balance))
    stake_metrics[2].metric("Saldo bei Verlust", _format_euro(loss_balance))
    stake_metrics[3].metric("Vorsichtiger Einsatz", _format_euro(risk_stake))
    if wins_remaining is not None and wins_remaining > 0:
        path_probability = ticket.joint_probability ** wins_remaining
        st.caption(
            f"Bei unveränderter Quote wären {wins_remaining} Siege in Folge bis "
            f"zum Ziel nötig. Wahrscheinlichkeit dieser Siegesserie laut Modell: "
            f"{path_probability * 100:.4f} %."
        )
    if log_growth <= 0.0:
        st.warning(
            "Der gewählte Challenge-Einsatz ist für dieses Risiko zu hoch. "
            "Der niedrigere vorsichtige Einsatz wäre sicherer."
        )
    elif played_stake > risk_stake:
        st.warning(
            "Der Challenge-Einsatz liegt über dem vorsichtig berechneten Wert. "
            "Das erhöht das Verlustrisiko deutlich."
        )
    st.success(
        f"15K-TIPP: {len(ticket.legs)} Spiel(e) @ Gesamtquote "
        f"{ticket.total_odds:.2f} | empfohlener Einsatz {suggested_stake:.2f} €. "
        "Auswahl, Modell und konservativer Marktpreis bestehen die Prüfungen."
    )
    st.caption(
        "Die App platziert keine Wette. Beim eigenen Anbieter müssen Auswahl, "
        "Linie und mindestens die angezeigte Mindestquote übereinstimmen."
    )
    if not price_is_valid:
        st.warning(
            "Diese tatsächliche Gesamtquote erfüllt den 15K-Korridor oder den "
            "konservativen Value-Mindestwert nicht. Sie kann nicht als offizieller "
            "15K-Tagestipp gespeichert werden."
        )
    if st.button(
        f"Als gespielt markieren und {played_stake:.2f} € abbuchen",
        type="primary",
        width="stretch",
        key="challenge_place_ticket",
        disabled=not price_is_valid,
    ):
        try:
            ticket_id = ledger.place_ticket(
                snapshot["search_date"],
                ticket,
                played_stake,
                snapshot.get("price_checked_at") or snapshot["scanned_at"],
                played_odds=played_total_odds,
            )
            st.session_state["challenge_ledger_notice"] = (
                f"Ticket #{ticket_id} als gespielt markiert. "
                f"{_format_euro(played_stake)} Einsatz wurden vom Guthaben abgezogen."
            )
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))


def _render_analysis(ledger: ChallengeLedger, settings: dict[str, Any]) -> None:
    config = load_app_config(st)
    if not config.api_football_key or not config.weather_key:
        st.error("Die 15K-Suche ist vorübergehend nicht verfügbar.")
        return
    st.caption(
        "BetBoy prüft jede Auswahl und die dazugehörige Quote automatisch."
    )

    controls = st.columns(3)
    with controls[0]:
        sport_scope = st.selectbox(
            "Sport",
            list(CHALLENGE_SPORT_OPTIONS),
            key="challenge_sport",
        )
    with controls[1]:
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
    controls[2].caption(
        "Alle Spiele der gewählten Ligen werden durchsucht."
    )

    enabled_sports = _challenge_sports_for_selection(sport_scope)
    if not enabled_sports:
        st.info(
            f"{sport_scope} ist im Wettfinder verfügbar. Dafür gibt es derzeit "
            "noch keine 15K-Tipps."
        )
        return
    if sport_scope == "Alle":
        st.caption("Aktuell 15K-fähig: Fußball.")

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
    if league_scope == favorite_scope_label:
        selected_leagues = favorites
        st.caption(", ".join(ALTERNATIVE_MARKET_LEAGUES[item] for item in selected_leagues))
    elif league_scope == all_scope_label:
        selected_leagues = available_ids
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
    ):
        if not selected_leagues:
            st.warning("Mindestens eine Liga auswählen.")
        elif scan_jobs.get_job(_challenge_job_key())["state"] == "running":
            st.info("Die 15K-Suche läuft bereits im Hintergrund.")
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
        scan_progress_fragment(_challenge_job_key(), "15K-Suche")
    elif job["state"] == "done":
        st.session_state["challenge_snapshot"] = job.get("result")
        st.session_state.pop("challenge_quote_result", None)
        scan_jobs.clear_job(_challenge_job_key())
    elif job["state"] == "error":
        st.error("Die 15K-Suche konnte nicht abgeschlossen werden.")
        scan_jobs.clear_job(_challenge_job_key())

    snapshot = st.session_state.get("challenge_snapshot")
    if not isinstance(snapshot, dict):
        st.info("Noch keine 15K-Suche für diese Auswahl.")
        return
    if snapshot.get("version") != CHALLENGE_SNAPSHOT_VERSION:
        st.warning("Dieses Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return
    current_scope = _scope_signature(selected_leagues, search_date, max_fixtures)
    if snapshot.get("scope") != current_scope:
        st.warning("Datum, Liga oder Prüfumfang wurden seit dem Ergebnis geändert. Wetten neu suchen.")
        return

    st.caption(
        f"Datenstand: {_format_time(snapshot.get('scanned_at'))} · "
        f"{snapshot.get('fixtures_found', 0)} Spiele geprüft"
    )
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
            "Dieses Ergebnis wird automatisch neu geprüft, sobald die nötigen "
            "aktuellen Spieldaten vorliegen."
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
    """Render the focused challenge finder without nested workspace tabs."""
    ledger = _challenge_ledger(storage_scope(st.session_state))
    _auto_settle_feedback(ledger)
    _render_ledger_notice()
    settings = _render_progress(ledger)
    st.caption(
        f"Einsatzanteil {settings['stake_fraction'] * 100:.0f} % | "
        "Tageszielquote 2,00-3,00 | maximal drei verschiedene Spiele | "
        "automatische Prüfung von Auswahl und Quote"
    )
    _render_pending_ticket_actions(ledger, key_prefix="challenge_main")
    with st.expander("Challenge-Konto einstellen", expanded=False):
        _render_account(ledger, ledger.settings())
    if st.button(
        "Vergangene Wette nachtragen",
        icon=":material/history:",
        key="challenge_open_manual_result",
    ):
        _render_manual_result_dialog(ledger)
    _render_analysis(ledger, settings)


def render_challenge_history() -> None:
    """Render challenge tickets in the shared records workspace."""
    ledger = _challenge_ledger(storage_scope(st.session_state))
    _auto_settle_feedback(ledger)
    _render_ledger_notice()
    _render_history(ledger)


def render_challenge_account() -> None:
    """Render challenge bankroll controls in settings."""
    ledger = _challenge_ledger(storage_scope(st.session_state))
    _render_account(ledger, ledger.settings())


__all__ = [
    "ChallengeDataProvider",
    "refresh_discovered_candidates",
    "render_challenge_account",
    "render_challenge_15k",
    "render_challenge_history",
    "scan_daily_challenge",
]
