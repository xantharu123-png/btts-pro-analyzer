"""Closing-odds benchmark rows from football-data.co.uk, separate from the model.

The model history loader (``football_data_history``) discards every price
column through its allowlist; that boundary is unchanged. This module reads the
price columns of the same CSV files into a separate table keyed by the same
pseudo fixture id, so a validation can compare model probabilities with the
no-vig closing market. Benchmark rows are never passed to a model function
(audit 2026-10-16, K2: "Modell vor Preis" forbids prices as model input, not as
a validation benchmark).

Column families (football-data.co.uk notes): closing 1X2 ``PSCH/PSCD/PSCA``
(Pinnacle), ``B365CH/..``, ``MaxCH/..``, ``AvgCH/..``; closing over/under 2.5
``PC>2.5/PC<2.5``, ``B365C>2.5/..``, ``MaxC>2.5/..``, ``AvgC>2.5/..``. Seasons
before 2019/20 carry only the earlier (non-closing) prices ``PSH/..``,
``P>2.5/..``; those rows are labelled ``closing=False``.
"""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from football_data_history import (
    FOOTBALL_DATA_DIVISIONS, _pseudo_fixture_id, _season_folder, history_url, parse_history_csv,
)

BENCHMARK_SCHEMA = "football-data-closing-benchmark-v1"
# Column prefixes per provider for 1X2 and for over/under 2.5.
PROVIDERS = {
    "pinnacle": ("PS", "P"),
    "bet365": ("B365", "B365"),
    "max": ("Max", "Max"),
    "avg": ("Avg", "Avg"),
}
REFERENCE_PROVIDER = "pinnacle"
OFFER_PROVIDERS = ("max", "bet365", "pinnacle", "avg")


def _odds(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 1.0:
        return None
    return number


def _three_way(row: dict, prefix: str, closing: bool) -> Optional[tuple[float, float, float]]:
    suffix = "C" if closing else ""
    values = tuple(_odds(row.get(f"{prefix}{suffix}{side}")) for side in ("H", "D", "A"))
    return values if all(v is not None for v in values) else None


def _two_way(row: dict, prefix: str, closing: bool) -> Optional[tuple[float, float]]:
    suffix = "C" if closing else ""
    over, under = _odds(row.get(f"{prefix}{suffix}>2.5")), _odds(row.get(f"{prefix}{suffix}<2.5"))
    return (over, under) if over is not None and under is not None else None


def parse_benchmark_csv(content: bytes, league_id: int, season_start_year: int) -> dict[int, dict[str, Any]]:
    """Price rows keyed by the pseudo fixture id used by ``parse_history_csv``."""
    if isinstance(league_id, bool) or not isinstance(league_id, int) or league_id <= 0:
        raise ValueError("league identifier is invalid")
    frame = pd.read_csv(BytesIO(content))
    if not {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}.issubset(frame.columns):
        raise ValueError("Benchmark CSV is missing required result columns")
    frame["parsed_date"] = pd.to_datetime(frame["Date"], dayfirst=True, errors="coerce", utc=True)
    frame = frame.dropna(subset=["parsed_date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    rows: dict[int, dict[str, Any]] = {}
    for row in frame.to_dict("records"):
        home_name, away_name = str(row["HomeTeam"]).strip(), str(row["AwayTeam"]).strip()
        date_text = row["parsed_date"].to_pydatetime().isoformat()
        fixture_id = _pseudo_fixture_id(league_id, date_text, home_name, away_name)
        if fixture_id in rows:
            continue
        entry: dict[str, Any] = {
            "schema": BENCHMARK_SCHEMA, "fixture_id": fixture_id, "league_id": int(league_id),
            "season": int(season_start_year), "date": date_text, "home": home_name, "away": away_name,
            "result": {}, "ou25": {}, "closing": {},
        }
        for provider, (three_prefix, two_prefix) in PROVIDERS.items():
            for closing in (True, False):
                if provider not in entry["result"]:
                    three = _three_way(row, three_prefix, closing)
                    if three is not None:
                        entry["result"][provider] = three
                        entry["closing"][f"result:{provider}"] = closing
                if provider not in entry["ou25"]:
                    two = _two_way(row, two_prefix, closing)
                    if two is not None:
                        entry["ou25"][provider] = two
                        entry["closing"][f"ou25:{provider}"] = closing
        if entry["result"] or entry["ou25"]:
            rows[fixture_id] = entry
    return rows


def benchmark_file_path(directory: Path | str, league_id: int, season_start_year: int) -> Optional[Path]:
    division = FOOTBALL_DATA_DIVISIONS.get(int(league_id))
    if division is None:
        return None
    return Path(directory) / f"{_season_folder(season_start_year)}_{division}.csv"


def download_benchmark_csv(league_id: int, season_start_year: int, directory: Path | str,
                           *, timeout: int = 30, overwrite: bool = False) -> Optional[Path]:
    """Save one season CSV into ``directory`` (data only; nothing is executed)."""
    import requests

    target = benchmark_file_path(directory, league_id, season_start_year)
    url = history_url(league_id, season_start_year)
    if target is None or url is None:
        return None
    if target.exists() and not overwrite:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    if b"HomeTeam" not in response.content[:4096]:
        raise ValueError(f"unexpected payload for {url}")
    target.write_bytes(response.content)
    return target


def load_season(directory: Path | str, league_id: int, season_start_year: int
                ) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """(odds-blind model fixtures, separate benchmark rows) for one saved season."""
    path = benchmark_file_path(directory, league_id, season_start_year)
    if path is None or not path.exists():
        return [], {}
    content = path.read_bytes()
    fixtures = parse_history_csv(content, league_id, season_start_year, [])
    benchmark = parse_benchmark_csv(content, league_id, season_start_year)
    return fixtures, benchmark


def load_league(directory: Path | str, league_id: int, seasons: list[int]
                ) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[int]]:
    fixtures: list[dict[str, Any]] = []
    benchmark: dict[int, dict[str, Any]] = {}
    loaded: list[int] = []
    for season in sorted(seasons):
        season_fixtures, season_benchmark = load_season(directory, league_id, season)
        if not season_fixtures:
            continue
        fixtures.extend(season_fixtures)
        benchmark.update(season_benchmark)
        loaded.append(season)
    fixtures.sort(key=lambda item: item["fixture"]["date"])
    return fixtures, benchmark, loaded


__all__ = [
    "BENCHMARK_SCHEMA", "OFFER_PROVIDERS", "PROVIDERS", "REFERENCE_PROVIDER",
    "benchmark_file_path", "download_benchmark_csv", "load_league", "load_season", "parse_benchmark_csv",
]
