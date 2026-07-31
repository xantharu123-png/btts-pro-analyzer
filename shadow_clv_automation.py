"""BetBoy Shadow Mode: automated CLV evidence collection.

One run performs every due step, idempotently:

1. Settle finished predictions from verified API-Football final scores.
2. Capture closing quotes inside the 15-minute pre-kickoff window.
3. Load the day's fixture schedule once per Zurich calendar day.
4. Evaluate each fixture 75-20 minutes before kickoff with the real BetBoy
   model pipeline (walk-forward validation + context gates: confirmed lineups,
   injuries, H2H, weather) and log passing BTTS candidates with the verified
   Bet365 opening quote into the CLV ledger.

Model and price stay strictly separated; the ledger enforces identical
bookmaker and source for opening and closing quotes.
"""

import json
import math
import os
import pickle
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

import requests  # noqa: E402

from challenge_engine import (  # noqa: E402
    MARKET_BY_KEY,
    apply_candidate_context,
    build_fixture_candidates,
    candidate_is_credible,
    fit_market_calibration,
    market_outcome,
    validate_league_markets,
)
from clv_tracker import CLVTracker  # noqa: E402
from config_loader import load_app_config  # noqa: E402
from football_data_history import fetch_history as fetch_stat_history  # noqa: E402
from football_data_history import merge_api_tail  # noqa: E402
from league_catalog import LEAGUES  # noqa: E402
from season_utils import current_season_start_year_for_id  # noqa: E402
from xg_backfill import annotate_history as _annotate_xg  # noqa: E402

def _zurich_offset(moment_utc: datetime) -> timedelta:
    """Return the Zurich UTC offset (CET/CEST) without relying on tzdata.

    The managed Windows runtime ships no timezone database, so the EU rule is
    computed directly: CEST runs from the last Sunday of March 01:00 UTC to
    the last Sunday of October 01:00 UTC.
    """
    year = moment_utc.year
    march_end = datetime(year, 3, 31, tzinfo=timezone.utc)
    cest_start = (march_end - timedelta(days=(march_end.weekday() + 1) % 7)).replace(hour=1)
    october_end = datetime(year, 10, 31, tzinfo=timezone.utc)
    cest_end = (october_end - timedelta(days=(october_end.weekday() + 1) % 7)).replace(hour=1)
    return timedelta(hours=2) if cest_start <= moment_utc < cest_end else timedelta(hours=1)


def _zurich_time(moment_utc: datetime) -> datetime:
    return moment_utc + _zurich_offset(moment_utc)


SHADOW_DB = PROJECT_DIR / "shadow_clv.db"
CACHE_DIR = PROJECT_DIR / ".shadow_cache"
BOOKMAKER_NAME = "Bet365"
QUOTE_SOURCE = "API-Football"
BTTS_MARKET_LABEL = "Beide Teams treffen"
CLOSING_WINDOW = timedelta(minutes=15)
EVAL_EARLIEST = timedelta(minutes=20)
EVAL_LATEST = timedelta(minutes=75)
EVAL_FINAL_RETRY_MINUTES = 30  # Kontext-gesperrte Fixtures werden bis -30 min erneut versucht
SETTLE_GRACE = timedelta(hours=2)
FT_STATUSES = {"FT", "AET", "PEN"}
MIN_HISTORY_GAMES = 220  # darunter wird die Vorsaison vorangestellt (Cold-Start)

# Tor-basierte Märkte mit eindeutigem Buchmacher-Pendant (Bet365 via API-Football).
# Nur diese Märkte werden geloggt: Settlement braucht Endstände, Ecken/Karten-
# Märkte wären ohne Statistik-Feed nicht abrechenbar.
_QUOTE_BETS = {
    "RESULT_HOME": ("Match Winner", "Home"),
    "RESULT_DRAW": ("Match Winner", "Draw"),
    "RESULT_AWAY": ("Match Winner", "Away"),
    "DC_1X": ("Double Chance", "1X"),
    "DC_X2": ("Double Chance", "X2"),
    "DC_12": ("Double Chance", "12"),
    "BTTS_YES": ("Both Teams Score", "Yes"),
    "BTTS_NO": ("Both Teams Score", "No"),
    "TOTAL_OVER_0_5": ("Goals Over/Under", "Over 0.5"),
    "TOTAL_UNDER_0_5": ("Goals Over/Under", "Under 0.5"),
    "TOTAL_OVER_1_5": ("Goals Over/Under", "Over 1.5"),
    "TOTAL_UNDER_1_5": ("Goals Over/Under", "Under 1.5"),
    "TOTAL_OVER_2_5": ("Goals Over/Under", "Over 2.5"),
    "TOTAL_UNDER_2_5": ("Goals Over/Under", "Under 2.5"),
    "TOTAL_OVER_3_5": ("Goals Over/Under", "Over 3.5"),
    "TOTAL_UNDER_3_5": ("Goals Over/Under", "Under 3.5"),
    "TOTAL_OVER_4_5": ("Goals Over/Under", "Over 4.5"),
    "TOTAL_UNDER_4_5": ("Goals Over/Under", "Under 4.5"),
}

errors: list[str] = []


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc)


def _positive_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _fixture_kickoff(fixture: dict) -> datetime | None:
    fixture_data = fixture.get("fixture")
    if not isinstance(fixture_data, dict):
        return None
    return _parse_iso(fixture_data.get("date"))


def _valid_fixture(value, expected_league_id: int) -> bool:
    if not isinstance(value, dict):
        return False
    fixture_data, league, teams = (
        value.get("fixture"), value.get("league"), value.get("teams"),
    )
    if not all(isinstance(item, dict) for item in (fixture_data, league, teams)):
        return False
    home, away = teams.get("home"), teams.get("away")
    if not isinstance(home, dict) or not isinstance(away, dict):
        return False
    ids = (
        _positive_int(fixture_data.get("id")),
        _positive_int(league.get("id")),
        _positive_int(home.get("id")),
        _positive_int(away.get("id")),
    )
    if None in ids or ids[1] != expected_league_id or ids[2] == ids[3]:
        return False
    if not str(home.get("name") or "").strip() or not str(away.get("name") or "").strip():
        return False
    return _fixture_kickoff(value) is not None


# --------------------------------------------------------------------------
# Provider (lean mirror of the app's ChallengeDataProvider)
# --------------------------------------------------------------------------

class ShadowProvider:
    def __init__(self, api_key: str, weather_key: str | None):
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self.weather_key = weather_key
        self._last_request = 0.0

    def _get(self, path: str, params: dict, label: str):
        elapsed = time.monotonic() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.monotonic()
        try:
            response = requests.get(
                f"{self.base_url}/{path}", headers=self.headers,
                params=params, timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{label}: {exc}")
            return None
        if not isinstance(payload, dict) or payload.get("errors"):
            errors.append(f"{label}: {payload.get('errors') if isinstance(payload, dict) else 'ungültige Antwort'}")
            return None
        data = payload.get("response")
        if not isinstance(data, list):
            errors.append(f"{label}: ungültige Provider-Antwort")
            return None
        return data

    def fixtures_by_date(self, league_id: int, season: int, day: date):
        return self._get(
            "fixtures",
            {"league": league_id, "season": season, "date": day.isoformat(),
             "timezone": "Europe/Zurich", "status": "NS"},
            f"Fixtures Liga {league_id}",
        )

    def fixtures_by_ids(self, ids: list[int]):
        if not ids:
            return []
        return self._get(
            "fixtures", {"ids": "-".join(str(i) for i in ids[:20])}, "Fixture-Details",
        ) or []

    def ft_history(self, league_id: int, season: int):
        return self._get(
            "fixtures", {"league": league_id, "season": season, "status": "FT"},
            f"Historie Liga {league_id}",
        )

    def ft_tail(self, league_id: int, season: int, from_date, to_date):
        """Endstände der letzten Tage (Frische-Tail über der CSV-Historie)."""
        return self._get(
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

    def coverage(self, league_id: int, season: int) -> dict:
        data = self._get("leagues", {"id": league_id, "season": season}, f"Coverage Liga {league_id}")
        if not data:
            return {"injuries": False, "lineups": False}
        seasons = [s for s in (data[0].get("seasons") or []) if isinstance(s, dict)]
        season_data = next((s for s in seasons if s.get("year") == season), None)
        coverage = (season_data or {}).get("coverage") or {}
        fixtures = coverage.get("fixtures") or {}
        return {
            "injuries": coverage.get("injuries") is True,
            "lineups": isinstance(fixtures, dict) and fixtures.get("lineups") is True,
        }

    def h2h(self, home_id: int, away_id: int):
        return self._get("fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": 10}, "H2H")

    def injuries(self, fixture_id: int):
        return self._get("injuries", {"fixture": fixture_id}, f"Verletzungen {fixture_id}")

    def fixture_details(self, fixture_id: int):
        data = self._get("fixtures", {"id": fixture_id}, f"Details {fixture_id}")
        if data and len(data) == 1 and isinstance(data[0].get("fixture"), dict):
            return data[0]
        return None

    def odds(self, fixture_id: int):
        return self._get("odds", {"fixture": fixture_id}, f"Quoten {fixture_id}")

    def weather(self, fixture: dict):
        if not self.weather_key:
            return None
        kickoff = _fixture_kickoff(fixture)
        venue = fixture.get("fixture", {}).get("venue") or {}
        city = str(venue.get("city") or "").strip()
        country = str(fixture.get("league", {}).get("country") or "").strip()
        if kickoff is None or not city:
            return None
        try:
            geocode = requests.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={"q": f"{city},{country}" if country else city, "limit": 1,
                        "appid": self.weather_key},
                timeout=15,
            )
            geocode.raise_for_status()
            locations = geocode.json()
            if not isinstance(locations, list) or not locations:
                return None
            lat, lon = locations[0].get("lat"), locations[0].get("lon")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                return None
            forecast_response = requests.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"lat": lat, "lon": lon, "appid": self.weather_key,
                        "units": "metric", "lang": "de"},
                timeout=15,
            )
            forecast_response.raise_for_status()
            forecasts = forecast_response.json().get("list")
        except (requests.RequestException, ValueError, TypeError) as exc:
            errors.append(f"Wetter {city}: {exc}")
            return None
        if not isinstance(forecasts, list):
            return None
        valid = [
            item for item in forecasts
            if isinstance(item, dict) and isinstance(item.get("dt"), (int, float))
            and not isinstance(item.get("dt"), bool) and item["dt"] > 0
        ]
        if not valid:
            return None
        nearest = min(valid, key=lambda item: abs(
            datetime.fromtimestamp(item["dt"], timezone.utc) - kickoff))
        forecast_time = datetime.fromtimestamp(nearest["dt"], timezone.utc)
        if abs((forecast_time - kickoff).total_seconds()) > 4 * 3600:
            return None
        main = nearest.get("main") if isinstance(nearest.get("main"), dict) else {}
        wind = nearest.get("wind") if isinstance(nearest.get("wind"), dict) else {}
        rain = nearest.get("rain") if isinstance(nearest.get("rain"), dict) else {}
        snow = nearest.get("snow") if isinstance(nearest.get("snow"), dict) else {}
        return {
            "status": "ok",
            "forecast_at": forecast_time.isoformat(),
            "temperature_c": main.get("temp"),
            "wind_mps": wind.get("speed"),
            "rain_3h_mm": rain.get("3h", 0.0),
            "snow_3h_mm": snow.get("3h", 0.0),
            "description": (
                nearest.get("weather", [{}])[0].get("description")
                if isinstance(nearest.get("weather"), list) and nearest.get("weather")
                else "n/a"
            ),
        }


# --------------------------------------------------------------------------
# Shadow DB (own tables next to the CLVTracker predictions table)
# --------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(SHADOW_DB)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS shadow_fixtures (
            fixture_id INTEGER PRIMARY KEY,
            zurich_date TEXT NOT NULL,
            league_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff TEXT NOT NULL,
            evaluated INTEGER NOT NULL DEFAULT 0
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS shadow_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )"""
    )
    return connection


def _meta_get(connection, key: str):
    row = connection.execute(
        "SELECT value FROM shadow_meta WHERE key = ?", (key,),
    ).fetchone()
    return row[0] if row else None


def _meta_set(connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO shadow_meta (key, value) VALUES (?, ?)", (key, value),
    )


# --------------------------------------------------------------------------
# Per-day caches (history + walk-forward validation are expensive)
# --------------------------------------------------------------------------

def _cache_path(kind: str, league_id: int, season: int, day: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{kind}_{league_id}_{season}_{day}.pkl"


def _cached_history(provider, league_id, season, fixture, day):
    path = _cache_path("history", league_id, season, day)
    if path.exists():
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except (pickle.PickleError, EOFError, OSError):
            path.unlink(missing_ok=True)
    history = fetch_stat_history(league_id, season, [fixture])
    if history:
        try:
            day_date = date.fromisoformat(day)
            tail = provider.ft_tail(
                league_id, season, day_date - timedelta(days=7), day_date,
            )
        except Exception as exc:  # Tail ist optional, CSV allein reicht
            errors.append(f"FT-Tail Liga {league_id}: Abruf fehlgeschlagen ({exc})")
            tail = None
        if tail:
            history = merge_api_tail(history, tail, tail_days=7)
    if not history:
        history = provider.ft_history(league_id, season)
    history = history or []
    if (
        len(history) < MIN_HISTORY_GAMES
        and isinstance(season, int)
        and not isinstance(season, bool)
        and season > 2020
    ):
        # Cold-Start-Schutz: dünne Saison (Sommerligen, Saisonstart) bekommt
        # die Vorsaison vorangestellt, sonst erreicht die Validierung nie n>=200.
        previous = fetch_stat_history(league_id, season - 1, [fixture])
        if not previous:
            try:
                previous = provider.ft_history(league_id, season - 1)
            except Exception as exc:  # Vorsaison ist optional
                errors.append(f"Vorsaison Liga {league_id}: Abruf fehlgeschlagen ({exc})")
                previous = None
        if previous:
            history = list(previous) + list(history)
    if history:
        try:
            _annotate_xg(history, league_id, season, provider._get, max_new_calls=8)
        except Exception as exc:  # xG ist optional, Shadow läuft ohne weiter
            errors.append(f"xG Liga {league_id}: Annotation fehlgeschlagen ({exc})")
    with path.open("wb") as handle:
        pickle.dump(history, handle)
    return history


def _cached_validation(league_id, season, history, day):
    path = _cache_path("validation", league_id, season, day)
    if path.exists():
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except (pickle.PickleError, EOFError, OSError):
            path.unlink(missing_ok=True)
    validation = validate_league_markets(history)
    with path.open("wb") as handle:
        pickle.dump(validation, handle)
    return validation


def _cached_calibration(league_id, season, history, day):
    path = _cache_path("calibration", league_id, season, day)
    if path.exists():
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except (pickle.PickleError, EOFError, OSError):
            path.unlink(missing_ok=True)
    calibration = fit_market_calibration(history)
    with path.open("wb") as handle:
        pickle.dump(calibration, handle)
    return calibration


# --------------------------------------------------------------------------
# Quote extraction (strictly one bookmaker for opening and closing)
# --------------------------------------------------------------------------

def _market_quote(odds_response, market_key: str):
    """Quote für einen tor-basierten Markt aus dem Bet365-Block (öffnend/schließend)."""
    target = _QUOTE_BETS.get(market_key)
    if target is None:
        return None
    bet_name, value_name = target
    if not isinstance(odds_response, list) or not odds_response:
        return None
    bookmakers = odds_response[0].get("bookmakers") or []
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, dict):
            continue
        if str(bookmaker.get("name") or "").casefold() != BOOKMAKER_NAME.casefold():
            continue
        for bet in bookmaker.get("bets") or []:
            if not isinstance(bet, dict) or bet.get("name") != bet_name:
                continue
            for value in bet.get("values") or []:
                if not isinstance(value, dict) or str(value.get("value")) != value_name:
                    continue
                try:
                    quote = float(str(value.get("odd")).strip())
                except (TypeError, ValueError):
                    return None
                return quote if math.isfinite(quote) and quote > 1.0 else None
    return None


def _btts_quote(odds_response, market_key: str):
    """Legacy-Wrapper (BTTS) auf die allgemeine Markt-Quote."""
    return _market_quote(odds_response, market_key)


# --------------------------------------------------------------------------
# Run steps
# --------------------------------------------------------------------------

def step_settle(tracker: CLVTracker, provider: ShadowProvider, now: datetime) -> int:
    threshold = _utc_iso(now - SETTLE_GRACE)
    with _connect() as connection:
        rows = connection.execute(
            """SELECT id, fixture_id, prediction, market_type FROM predictions
               WHERE result IS NULL AND fixture_kickoff < ?""",
            (threshold,),
        ).fetchall()
    if not rows:
        return 0
    fixture_ids = sorted({row[1] for row in rows})
    details = provider.fixtures_by_ids(fixture_ids)
    by_id = {}
    for fixture in details:
        fixture_data = fixture.get("fixture") if isinstance(fixture, dict) else None
        fixture_id = fixture_data.get("id") if isinstance(fixture_data, dict) else None
        if _positive_int(fixture_id):
            by_id[fixture_id] = fixture
    settled = 0
    for prediction_id, fixture_id, selection, market_type in rows:
        fixture = by_id.get(fixture_id)
        if not fixture:
            continue
        status = str(fixture.get("fixture", {}).get("status", {}).get("short") or "")
        if status not in FT_STATUSES:
            continue
        goals = fixture.get("goals") or {}
        home_goals, away_goals = goals.get("home"), goals.get("away")
        if (
            isinstance(home_goals, bool) or isinstance(away_goals, bool)
            or not isinstance(home_goals, int) or not isinstance(away_goals, int)
            or home_goals < 0 or away_goals < 0
        ):
            continue
        spec = MARKET_BY_KEY.get(str(market_type))
        if spec is not None and spec.key in _QUOTE_BETS:
            try:
                won = market_outcome(spec, home_goals, away_goals)
            except ValueError:
                continue
        else:
            # Legacy-Zeilen (Marktlabel "Beide Teams treffen", Auswahl Ja/Nein)
            both_scored = home_goals > 0 and away_goals > 0
            won = both_scored if str(selection).strip() == "Ja" else not both_scored
        try:
            tracker.settle_prediction(
                prediction_id, "Won" if won else "Lost", home_goals, away_goals,
            )
            settled += 1
        except (ValueError, KeyError) as exc:
            errors.append(f"Settlement {prediction_id}: {exc}")
    return settled


def step_closing(tracker: CLVTracker, provider: ShadowProvider, now: datetime) -> int:
    start, end = _utc_iso(now), _utc_iso(now + CLOSING_WINDOW)
    with _connect() as connection:
        rows = connection.execute(
            """SELECT id, fixture_id, prediction, market_type FROM predictions
               WHERE closing_odds IS NULL AND result IS NULL
               AND fixture_kickoff >= ? AND fixture_kickoff <= ?""",
            (start, end),
        ).fetchall()
    captured = 0
    for prediction_id, fixture_id, selection, market_type in rows:
        market_key = (
            str(market_type)
            if str(market_type) in _QUOTE_BETS
            else ("BTTS_YES" if str(selection).strip() == "Ja" else "BTTS_NO")
        )
        quote = _market_quote(provider.odds(fixture_id), market_key)
        if quote is None:
            errors.append(f"Closing {fixture_id}: {BOOKMAKER_NAME}-Quote {market_key} fehlt")
            continue
        try:
            tracker.update_closing_odds(
                prediction_id, quote,
                bookmaker=BOOKMAKER_NAME, quote_source=QUOTE_SOURCE,
            )
            captured += 1
        except (ValueError, KeyError) as exc:
            errors.append(f"Closing {fixture_id}: {exc}")
    return captured


def step_schedule(provider: ShadowProvider, league_ids: list[int], zurich_today: date,
                  force: bool) -> int:
    with _connect() as connection:
        marker = f"schedule:{zurich_today.isoformat()}"
        if _meta_get(connection, marker) and not force:
            return 0
        loaded = 0
        for league_id in league_ids:
            season = current_season_start_year_for_id(league_id, zurich_today)
            fixtures = provider.fixtures_by_date(league_id, season, zurich_today)
            for fixture in fixtures or []:
                if not _valid_fixture(fixture, league_id):
                    continue
                fixture_data = fixture["fixture"]
                teams = fixture["teams"]
                connection.execute(
                    """INSERT OR REPLACE INTO shadow_fixtures
                       (fixture_id, zurich_date, league_id, season, home_team,
                        away_team, kickoff, evaluated)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                    (
                        fixture_data["id"], zurich_today.isoformat(), league_id, season,
                        teams["home"]["name"].strip(), teams["away"]["name"].strip(),
                        _utc_iso(_fixture_kickoff(fixture)),
                    ),
                )
                loaded += 1
        _meta_set(connection, marker, _utc_iso(datetime.now(timezone.utc)))
        connection.commit()
    return loaded


def step_evaluate(tracker: CLVTracker, provider: ShadowProvider, now: datetime,
                  zurich_today: date, max_fixtures: int) -> dict:
    earliest, latest = _utc_iso(now + EVAL_EARLIEST), _utc_iso(now + EVAL_LATEST)
    with _connect() as connection:
        rows = connection.execute(
            """SELECT fixture_id, league_id, season, home_team, away_team, kickoff
               FROM shadow_fixtures
               WHERE evaluated = 0 AND kickoff >= ? AND kickoff <= ?
               ORDER BY kickoff LIMIT ?""",
            (earliest, latest, max_fixtures),
        ).fetchall()
    result = {"evaluated": 0, "logged": 0}
    for fixture_id, league_id, season, home_team, away_team, kickoff_text in rows:
        detail = provider.fixture_details(fixture_id)
        if not detail:
            errors.append(f"Fixture {fixture_id}: Details fehlen")
            continue
        history = _cached_history(
            provider, league_id, season, detail, zurich_today.isoformat(),
        )
        validation = _cached_validation(league_id, season, history, zurich_today.isoformat())
        calibration = _cached_calibration(league_id, season, history, zurich_today.isoformat())
        candidates = build_fixture_candidates(detail, history, validation, calibration)
        coverage = provider.coverage(league_id, season)
        teams = detail.get("teams", {})
        home_id = teams.get("home", {}).get("id")
        away_id = teams.get("away", {}).get("id")
        h2h = provider.h2h(home_id, away_id) if home_id and away_id else None
        injuries = provider.injuries(fixture_id)
        weather = provider.weather(detail)
        lineups = detail.get("lineups") if coverage.get("lineups") is True else None

        base_candidates = [
            candidate
            for candidate in candidates
            if candidate.base_eligible and candidate.market_key in _QUOTE_BETS
        ]
        credible = []
        for candidate in base_candidates:
            apply_candidate_context(
                candidate,
                h2h_fixtures=h2h,
                injuries=injuries,
                injury_coverage=bool(coverage.get("injuries")),
                weather=weather,
                lineups=lineups,
            )
            if candidate_is_credible(candidate):
                credible.append(candidate)
        pick = max(
            credible,
            key=lambda c: (c.conservative_probability, c.evidence_score),
            default=None,
        )
        if pick is not None:
            with _connect() as connection:
                existing = connection.execute(
                    """SELECT COUNT(*) FROM predictions
                       WHERE fixture_id = ? AND market_type = ?""",
                    (fixture_id, pick.market_key),
                ).fetchone()[0]
            if existing == 0:
                quote = _market_quote(provider.odds(fixture_id), pick.market_key)
                if quote is None:
                    errors.append(
                        f"Fixture {fixture_id}: {BOOKMAKER_NAME}-Quote {pick.market_key} fehlt – nicht geloggt"
                    )
                else:
                    try:
                        tracker.record_prediction(
                            fixture_id=fixture_id,
                            home_team=home_team,
                            away_team=away_team,
                            market_type=pick.market_key,
                            prediction=pick.selection,
                            odds=quote,
                            model_probability=pick.conservative_probability * 100.0,
                            confidence=int(round(min(100.0, max(0.0, pick.evidence_score)))),
                            bookmaker=BOOKMAKER_NAME,
                            quote_source=QUOTE_SOURCE,
                            fixture_kickoff=kickoff_text,
                            data_quality="shadow",
                        )
                        result["logged"] += 1
                    except ValueError as exc:
                        errors.append(f"Logging {fixture_id}: {exc}")
        # Terminal-Logik: nur endgültig abhaken, wenn (a) ein Pick geloggt wurde
        # oder (b) das Modell grundsätzlich nichts anbietet (ändert sich heute
        # nicht mehr) oder (c) der Anpfiff so nah ist, dass kein Retry mehr
        # hilft. Kontext-Sperren (Aufstellungen erscheinen erst ~-60 min,
        # Wetter ggf. später) dürfen kein einmaliges Abhaken auslösen — sonst
        # wäre das Fixture für immer verloren, bevor die Daten da sind.
        terminal = pick is not None or not base_candidates
        if not terminal:
            kickoff_dt = _fixture_kickoff({"fixture": {"date": kickoff_text}})
            minutes_left = (
                (kickoff_dt - now).total_seconds() / 60.0
                if kickoff_dt is not None
                else 0.0
            )
            terminal = minutes_left <= EVAL_FINAL_RETRY_MINUTES
        if terminal:
            with _connect() as connection:
                connection.execute(
                    "UPDATE shadow_fixtures SET evaluated = 1 WHERE fixture_id = ?",
                    (fixture_id,),
                )
                connection.commit()
            result["evaluated"] += 1
        else:
            result["deferred"] = result.get("deferred", 0) + 1
    return result


# --------------------------------------------------------------------------
# Artifact
# --------------------------------------------------------------------------

def _counts() -> tuple[int, int]:
    with _connect() as connection:
        open_count = connection.execute(
            "SELECT COUNT(*) FROM predictions WHERE result IS NULL",
        ).fetchone()[0]
        pending_closing = connection.execute(
            """SELECT COUNT(*) FROM predictions
               WHERE closing_odds IS NULL AND result IS NULL""",
        ).fetchone()[0]
    return open_count, pending_closing


def _recent(tracker: CLVTracker) -> list[dict]:
    recent = []
    for item in tracker.get_recent_predictions(10):
        recent.append({
            "match": f"{item['home_team']} vs {item['away_team']}",
            "prediction": item["prediction"],
            "odds": item["odds"],
            "closing_odds": item["closing_odds"],
            "clv_percent": item["clv"],
            "result": item["result"],
            "profit": item["profit"],
            "kickoff": item["fixture_kickoff"],
        })
    return recent


def _verdict(stats_all: dict, stats_30: dict) -> str:
    clv_bets = stats_all.get("clv_bets") or 0
    avg_clv = stats_all.get("avg_clv")
    if clv_bets < 30:
        return (
            f"Shadow-Phase: {clv_bets} abgerechnete Wetten mit gültigem Closing. "
            "Ein belastbares CLV-Urteil braucht mindestens ~30, besser 100+ – "
            "kein echtes Geld vor positivem CLV."
        )
    direction = "positiv" if (avg_clv or 0) > 0 else "negativ"
    return (
        f"CLV über {clv_bets} Wetten: {avg_clv:+.2f} % ({direction}). "
        + (
            "Das Modell schlägt die Closing Line im Schnitt – weiter beobachten."
            if (avg_clv or 0) > 0
            else "Das Modell schlägt die Closing Line nicht – kein echter Edge belegt."
        )
    )


def _extract_input(ctx) -> dict:
    if isinstance(ctx, dict):
        candidate = ctx.get("input")
    else:
        candidate = getattr(ctx, "input", None)
    if isinstance(candidate, str):
        try:
            candidate = json.loads(candidate)
        except ValueError:
            candidate = None
    return candidate if isinstance(candidate, dict) else {}


def run(ctx):
    """Managed runner entrypoint: perform all due shadow-mode steps once."""
    run_input = _extract_input(ctx)
    league_ids = run_input.get("league_ids") or [league.league_id for league in LEAGUES]
    league_ids = [int(value) for value in league_ids if _positive_int(value)] or [
        league.league_id for league in LEAGUES
    ]
    max_fixtures = run_input.get("max_fixtures")
    if not isinstance(max_fixtures, int) or isinstance(max_fixtures, bool) or not 1 <= max_fixtures <= 40:
        max_fixtures = 12
    force_schedule = run_input.get("force_schedule") is True

    config = load_app_config(config_path=PROJECT_DIR / "config.ini")
    if not config.api_football_key:
        raise SystemExit("API-Football-Schlüssel fehlt in config.ini")
    provider = ShadowProvider(config.api_football_key, config.weather_key)
    tracker = CLVTracker(db_path=str(SHADOW_DB))

    now = datetime.now(timezone.utc)
    zurich_today = _zurich_time(now).date()

    settled = step_settle(tracker, provider, now)
    closings = step_closing(tracker, provider, now)
    scheduled = step_schedule(provider, league_ids, zurich_today, force_schedule)
    evaluation = step_evaluate(tracker, provider, now, zurich_today, max_fixtures)

    stats_30 = tracker.get_clv_statistics(days=30)
    stats_all = tracker.get_clv_statistics(days=36500)
    open_count, pending_closing = _counts()

    artifact = {
        "run_at": _utc_iso(now),
        "zurich_date": zurich_today.isoformat(),
        "actions": {
            "fixtures_scheduled": scheduled,
            "fixtures_evaluated": evaluation["evaluated"],
            "fixtures_deferred": evaluation.get("deferred", 0),
            "predictions_logged": evaluation["logged"],
            "closings_captured": closings,
            "predictions_settled": settled,
        },
        "stats_30d": stats_30,
        "stats_all": stats_all,
        "open_count": open_count,
        "pending_closing": pending_closing,
        "recent": _recent(tracker),
        "errors": errors[-15:],
        "verdict": _verdict(stats_all, stats_30),
        "reference_bookmaker": BOOKMAKER_NAME,
        "quote_source": QUOTE_SOURCE,
    }
    wrapper = {"artifact": artifact}
    output_file = os.environ.get("DAIMON_BLUEPRINT_AUTOMATION_OUTPUT_FILE")
    if output_file:
        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(wrapper, handle)
    return wrapper
