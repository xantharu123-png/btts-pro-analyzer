"""Odds-blind historical match-stat loader for supported European leagues.

Football-Data CSV files contain prices as well as results.  This module uses a
strict allowlist and discards every non-result field before returning data to a
model.  No bookmaker column can cross this boundary.
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from difflib import SequenceMatcher
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
    mapping: dict[str, int] = {}
    for fixture in upcoming_fixtures:
        for side in ("home", "away"):
            team = fixture.get("teams", {}).get(side, {})
            team_id = team.get("id")
            normalized = _normalized_team_name(team.get("name"))
            if not isinstance(team_id, int) or not normalized:
                continue
            exact = next((name for name in history_names if name == normalized), None)
            if exact is not None:
                mapping[exact] = team_id
                continue
            matches = sorted(
                (
                    (SequenceMatcher(None, normalized, name).ratio(), name)
                    for name in history_names
                ),
                reverse=True,
            )
            if matches and matches[0][0] >= 0.84:
                mapping[matches[0][1]] = team_id
    return mapping


def parse_history_csv(
    content: bytes,
    league_id: int,
    season_start_year: int,
    upcoming_fixtures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse an allowlisted CSV payload into the internal fixture shape."""
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
        if home_normalized not in team_ids or away_normalized not in team_ids:
            continue
        home_goals = int(row["FTHG"])
        away_goals = int(row["FTAG"])
        if min(home_goals, away_goals) < 0:
            continue
        played_at = row["parsed_date"].to_pydatetime()
        stats = {}
        stat_columns = {
            "corners_home": "HC",
            "corners_away": "AC",
            "yellow_cards_home": "HY",
            "yellow_cards_away": "AY",
        }
        for key, column in stat_columns.items():
            value = row.get(column)
            if value is not None and not pd.isna(value) and float(value) >= 0:
                stats[key] = int(value)
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
    return sorted(fixtures, key=lambda item: item["fixture"]["date"])


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


__all__ = [
    "ALLOWED_COLUMNS",
    "FOOTBALL_DATA_DIVISIONS",
    "fetch_history",
    "history_url",
    "parse_history_csv",
]
