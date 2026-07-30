"""Odds-blind historical match-stat loader for supported European leagues.

Football-Data CSV files contain prices as well as results.  This module uses a
strict allowlist and discards every non-result field before returning data to a
model.  No bookmaker column can cross this boundary.
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import math
import re
import unicodedata
from typing import Any, Optional

import pandas as pd
import requests


FOOTBALL_DATA_DIVISIONS = {
    39: "E0",
    40: "E1",
    41: "E2",
    42: "E3",
    78: "D1",
    79: "D2",
    135: "I1",
    140: "SP1",
    61: "F1",
    88: "N1",
    94: "P1",
    203: "T1",
    144: "B1",
    197: "G1",
}

ALLOWED_COLUMNS = (
    "Date",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "HC",
    "AC",
    "HY",
    "AY",
    "Referee",
)
REQUIRED_COLUMNS = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}

NAME_ALIASES = {
    "ath madrid": "atletico madrid",
    "ath bilbao": "athletic club",
    "betis": "real betis",
    "bayern munich": "bayern munchen",
    "cologne": "koln",
    "frankfurt": "eintracht frankfurt",
    "mgladbach": "borussia monchengladbach",
    "inter": "inter milan",
    "leverkusen": "bayer leverkusen",
    "man city": "manchester city",
    "man united": "manchester united",
    "monchengladbach": "borussia monchengladbach",
    "newcastle": "newcastle united",
    "nottm forest": "nottingham forest",
    "paris sg": "paris saint germain",
    "psg": "paris saint germain",
    "sociedad": "real sociedad",
    "sp lisbon": "sporting cp",
    "st pauli": "fc st pauli",
    "tottenham": "tottenham hotspur",
    "west ham": "west ham united",
    "wolves": "wolverhampton wanderers",
}


def _normalized_team_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("&", " and ").replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(
        r"\b(fc|cf|afc|sc|vfl|vfb|fsv|sv|tsg|rcd|rc|ssc|ac|as|us|cd|ud|calcio|football club)\b",
        " ",
        text,
    )
    text = re.sub(r"\b(1|04|05|1899)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return NAME_ALIASES.get(text, text)


def _pseudo_team_id(normalized_name: str) -> int:
    digest = sha256(normalized_name.encode("utf-8")).digest()
    return -int.from_bytes(digest[:4], "big", signed=False) - 1


def _pseudo_fixture_id(league_id: int, date_text: str, home: str, away: str) -> int:
    token = f"{league_id}|{date_text}|{home}|{away}".encode("utf-8")
    return -int.from_bytes(sha256(token).digest()[:8], "big", signed=False) - 1


def _nonnegative_integer(value: Any, *, maximum: Optional[int] = None) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if (
        not math.isfinite(numeric)
        or numeric < 0
        or not numeric.is_integer()
        or maximum is not None and numeric > maximum
    ):
        return None
    return int(numeric)


def _season_folder(season_start_year: int) -> str:
    if not isinstance(season_start_year, int) or not 1990 <= season_start_year <= 2098:
        raise ValueError("season_start_year is invalid")
    return f"{season_start_year % 100:02d}{(season_start_year + 1) % 100:02d}"


def history_url(league_id: int, season_start_year: int) -> Optional[str]:
    division = FOOTBALL_DATA_DIVISIONS.get(int(league_id))
    if division is None:
        return None
    return f"https://www.football-data.co.uk/mmz4281/{_season_folder(season_start_year)}/{division}.csv"


def _current_team_mapping(
    history_names: set[str],
    upcoming_fixtures: list[dict[str, Any]],
) -> dict[str, int]:
    current_teams: dict[int, str] = {}
    for fixture in upcoming_fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("teams"), dict):
            continue
        for side in ("home", "away"):
            team = fixture["teams"].get(side)
            if not isinstance(team, dict):
                continue
            team_id = team.get("id")
            normalized = _normalized_team_name(team.get("name"))
            if (
                isinstance(team_id, bool)
                or not isinstance(team_id, int)
                or team_id <= 0
                or not normalized
            ):
                continue
            current_teams[team_id] = normalized

    mapping: dict[str, int] = {}
    used_team_ids: set[int] = set()
    for team_id, normalized in current_teams.items():
        if normalized in history_names and normalized not in mapping:
            mapping[normalized] = team_id
            used_team_ids.add(team_id)

    candidates = []
    for team_id, normalized in current_teams.items():
        if team_id in used_team_ids:
            continue
        matches = sorted(
            (
                (SequenceMatcher(None, normalized, name).ratio(), name)
                for name in history_names
                if name not in mapping
            ),
            reverse=True,
        )
        if not matches or matches[0][0] < 0.90:
            continue
        if len(matches) > 1 and matches[0][0] - matches[1][0] < 0.02:
            continue
        candidates.append((matches[0][0], matches[0][1], team_id))

    for _, history_name, team_id in sorted(candidates, reverse=True):
        if history_name in mapping or team_id in used_team_ids:
            continue
        mapping[history_name] = team_id
        used_team_ids.add(team_id)
    return mapping


def parse_history_csv(
    content: bytes,
    league_id: int,
    season_start_year: int,
    upcoming_fixtures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse an allowlisted CSV payload into the internal fixture shape."""
    if (
        isinstance(league_id, bool)
        or not isinstance(league_id, int)
        or league_id <= 0
        or isinstance(season_start_year, bool)
        or not isinstance(season_start_year, int)
        or not 1900 <= season_start_year <= 2100
    ):
        raise ValueError("league and season identifiers are invalid")
    frame = pd.read_csv(BytesIO(content), usecols=lambda column: column in ALLOWED_COLUMNS)
    if not REQUIRED_COLUMNS.issubset(frame.columns):
        raise ValueError("Historical CSV is missing required result columns")
    frame = frame[list(column for column in ALLOWED_COLUMNS if column in frame.columns)].copy()
    frame["parsed_date"] = pd.to_datetime(frame["Date"], dayfirst=True, errors="coerce", utc=True)
    for column in ("FTHG", "FTAG", "HC", "AC", "HY", "AY"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["parsed_date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])

    normalized_names = {
        _normalized_team_name(name)
        for name in pd.concat((frame["HomeTeam"], frame["AwayTeam"])).dropna().unique()
    }
    normalized_names.discard("")
    current_mapping = _current_team_mapping(normalized_names, upcoming_fixtures)
    team_ids = {
        name: current_mapping.get(name, _pseudo_team_id(name))
        for name in normalized_names
    }

    fixtures: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        home_name = str(row["HomeTeam"]).strip()
        away_name = str(row["AwayTeam"]).strip()
        home_normalized = _normalized_team_name(home_name)
        away_normalized = _normalized_team_name(away_name)
        if (
            home_normalized not in team_ids
            or away_normalized not in team_ids
            or home_normalized == away_normalized
            or team_ids[home_normalized] == team_ids[away_normalized]
        ):
            continue
        home_goals = _nonnegative_integer(row["FTHG"])
        away_goals = _nonnegative_integer(row["FTAG"])
        if (
            home_goals is None
            or away_goals is None
            or home_goals > 30
            or away_goals > 30
        ):
            continue
        played_at = row["parsed_date"].to_pydatetime()
        if (
            played_at.year not in {season_start_year, season_start_year + 1}
            or played_at > pd.Timestamp.now(tz="UTC").to_pydatetime()
        ):
            continue
        stats = {}
        stat_columns = {
            "corners_home": "HC",
            "corners_away": "AC",
            "yellow_cards_home": "HY",
            "yellow_cards_away": "AY",
        }
        for key, column in stat_columns.items():
            value = row.get(column)
            maximum = 40 if key.startswith("corners_") else 20
            count = _nonnegative_integer(value, maximum=maximum)
            if count is not None:
                stats[key] = count
        date_text = played_at.isoformat()
        fixtures.append(
            {
                "fixture": {
                    "id": _pseudo_fixture_id(league_id, date_text, home_name, away_name),
                    "date": date_text,
                    "referee": (
                        str(row.get("Referee")).strip()
                        if row.get("Referee") is not None and not pd.isna(row.get("Referee"))
                        else None
                    ),
                },
                "league": {
                    "id": int(league_id),
                    "season": int(season_start_year),
                    "name": f"Football-Data {league_id}",
                },
                "teams": {
                    "home": {"id": team_ids[home_normalized], "name": home_name},
                    "away": {"id": team_ids[away_normalized], "name": away_name},
                },
                "goals": {"home": home_goals, "away": away_goals},
                "challenge_stats": stats,
                "challenge_source": "football-data-results-only",
            }
        )
    unique = {item["fixture"]["id"]: item for item in fixtures}
    return sorted(unique.values(), key=lambda item: item["fixture"]["date"])


def fetch_history(
    league_id: int,
    season_start_year: int,
    upcoming_fixtures: list[dict[str, Any]],
    timeout: int = 20,
) -> Optional[list[dict[str, Any]]]:
    url = history_url(league_id, season_start_year)
    if url is None:
        return None
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return parse_history_csv(
            response.content,
            league_id,
            season_start_year,
            upcoming_fixtures,
        )
    except (requests.RequestException, ValueError, pd.errors.ParserError):
        return None


def _fixture_played_at(item: dict[str, Any]) -> Optional[datetime]:
    fixture = item.get("fixture") if isinstance(item, dict) else None
    if not isinstance(fixture, dict):
        return None
    raw = fixture.get("date")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _tail_match_key(item: dict[str, Any]) -> Optional[tuple[str, str, str]]:
    """Dedupe-Schlüssel: Spieltag + normalisierte Teamnamen (aliasbereinigt)."""
    teams = item.get("teams") if isinstance(item, dict) else None
    if not isinstance(teams, dict):
        return None
    played_at = _fixture_played_at(item)
    home = teams.get("home")
    away = teams.get("away")
    if played_at is None or not isinstance(home, dict) or not isinstance(away, dict):
        return None
    home_name = _normalized_team_name(home.get("name"))
    away_name = _normalized_team_name(away.get("name"))
    if not home_name or not away_name or home_name == away_name:
        return None
    return (played_at.date().isoformat(), home_name, away_name)


def merge_api_tail(
    history: list[dict[str, Any]],
    api_fixtures: Optional[list[dict[str, Any]]],
    *,
    tail_days: int = 7,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Frische API-FT-Ergebnisse der letzten ``tail_days`` Tage einmergen.

    Die Football-Data-CSV hinkt typischerweise 1-3 Tage hinterher; API-Football
    liefert Endstände minutenaktuell. Dedupe läuft über (Spieltag,
    normalisierte Teamnamen) — niemals über Quoten- oder ID-Felder. CSV-Zeilen
    behalten ihre Ecken-/Karten-Stats; neu gemergte API-Spiele tragen keine
    Stats (reine Ergebnisse) und erben die Team-ID der CSV, falls der Name
    dort bekannt ist, damit Form- und Venue-Zählungen konsistent bleiben.
    """
    if not isinstance(history, list):
        return []
    if isinstance(tail_days, bool) or not isinstance(tail_days, int) or tail_days < 1:
        raise ValueError("tail_days is invalid")
    if not isinstance(api_fixtures, list) or not api_fixtures:
        return list(history)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(days=tail_days)

    name_to_id: dict[str, int] = {}
    known: set[tuple[str, str, str]] = set()
    for item in history:
        key = _tail_match_key(item)
        if key is None:
            continue
        known.add(key)
        teams = item.get("teams", {})
        for side, normalized in (("home", key[1]), ("away", key[2])):
            team = teams.get(side)
            team_id = team.get("id") if isinstance(team, dict) else None
            if (
                normalized not in name_to_id
                and not isinstance(team_id, bool)
                and isinstance(team_id, int)
            ):
                name_to_id[normalized] = team_id

    merged = list(history)
    for item in api_fixtures:
        if not isinstance(item, dict):
            continue
        key = _tail_match_key(item)
        if key is None or key in known:
            continue
        played_at = _fixture_played_at(item)
        fixture_data = item.get("fixture")
        goals = item.get("goals")
        fixture_id = fixture_data.get("id") if isinstance(fixture_data, dict) else None
        home_goals = _nonnegative_integer(goals.get("home"), maximum=30) if isinstance(goals, dict) else None
        away_goals = _nonnegative_integer(goals.get("away"), maximum=30) if isinstance(goals, dict) else None
        teams = item.get("teams")
        home_id = teams.get("home", {}).get("id") if isinstance(teams, dict) else None
        away_id = teams.get("away", {}).get("id") if isinstance(teams, dict) else None
        if (
            played_at is None
            or played_at < cutoff
            or played_at > moment
            or home_goals is None
            or away_goals is None
            or isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or fixture_id <= 0
            or isinstance(home_id, bool)
            or not isinstance(home_id, int)
            or home_id <= 0
            or isinstance(away_id, bool)
            or not isinstance(away_id, int)
            or away_id <= 0
            or home_id == away_id
        ):
            continue
        entry = dict(item)  # flache Kopie: API-Original wird nie mutiert
        entry["goals"] = {"home": home_goals, "away": away_goals}
        entry["challenge_stats"] = {}
        entry["challenge_source"] = "api-football-ft-tail"
        patched_teams = {
            side: dict(teams.get(side))
            for side in ("home", "away")
        }
        for side, normalized in (("home", key[1]), ("away", key[2])):
            if normalized in name_to_id:
                patched_teams[side]["id"] = name_to_id[normalized]
        entry["teams"] = patched_teams
        merged.append(entry)
        known.add(key)
    return sorted(merged, key=lambda item: _fixture_played_at(item) or moment)


__all__ = [
    "ALLOWED_COLUMNS",
    "FOOTBALL_DATA_DIVISIONS",
    "fetch_history",
    "history_url",
    "merge_api_tail",
    "parse_history_csv",
]
