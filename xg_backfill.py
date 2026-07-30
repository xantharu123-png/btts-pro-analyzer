"""Expected-Goals-Backfill: xG aus API-Football in einen lokalen SQLite-Cache
und Annotation der Challenge-Historie.

Datenfluss:
1. ``season_fixture_index`` lädt die abgeschlossenen Saisonspiele einer Liga
   (1 API-Call, gecacht), um CSV-Historienzeilen (Pseudo-IDs) auf API-Fixture-IDs
   abzubilden.
2. ``fetch_missing_xg`` ruft ``fixtures/statistics`` für fehlende Spiele ab
   (1 Call pro Spiel, quotenbewusst über ``max_calls`` begrenzt) und speichert
   das xG-Paar dauerhaft in ``xg_cache.db``.
3. ``annotate_history`` hängt ``xg_home``/``xg_away`` an die ``challenge_stats``
   der Historienzeilen. Die Engine (``_fixture_model``) blendet xG automatisch
   ein, sobald genügend Abdeckung vorliegt — Validierung und Kandidaten
   verwenden dadurch konsistent dasselbe Hybrid-Modell.

Kein Leakage: xG ist Post-Match-Datenlage und wird nur für Spiele verwendet,
die vor dem jeweiligen Anpfiff abgeschlossen wurden (die Engine filtert das).
"""

from __future__ import annotations

import argparse
import configparser
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from football_data_history import _current_team_mapping, _normalized_team_name

XG_CACHE_PATH = Path(__file__).resolve().with_name("xg_cache.db")
SEASON_INDEX_MAX_AGE = timedelta(hours=6)
MAX_XG_VALUE = 12.0

# fetch_list(path, params, label) -> Optional[list[dict]]  (wie ChallengeDataProvider._football_get)
FetchList = Callable[[str, dict[str, Any], str], Optional[list[dict[str, Any]]]]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS xg_values (
    fixture_id INTEGER PRIMARY KEY,
    xg_home REAL,
    xg_away REAL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS xg_missing (
    fixture_id INTEGER PRIMARY KEY,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS season_index (
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (league_id, season)
);
"""

# Zusätzliche Count-Statistiken aus demselben statistics-Call (Ecken/Karten),
# damit auch Ligen ohne football-data-CSV volle Count-Historie bekommen.
_STAT_COLUMNS = {
    "corners_home": "INTEGER",
    "corners_away": "INTEGER",
    "yellow_home": "INTEGER",
    "yellow_away": "INTEGER",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), isolation_level=None)  # Autocommit
    connection.executescript(_SCHEMA)
    info = connection.execute("PRAGMA table_info(xg_values)").fetchall()
    notnull_legacy = any(row[1] == "xg_home" and row[3] for row in info)
    if notnull_legacy:
        # Altschema (xg_home/xg_away NOT NULL) -> Tabelle mit nullable Spalten neu aufbauen.
        connection.execute("ALTER TABLE xg_values RENAME TO xg_values_legacy")
        connection.executescript(_SCHEMA)
        connection.execute(
            "INSERT INTO xg_values (fixture_id, xg_home, xg_away, fetched_at)"
            " SELECT fixture_id, xg_home, xg_away, fetched_at FROM xg_values_legacy"
        )
        connection.execute("DROP TABLE xg_values_legacy")
        info = connection.execute("PRAGMA table_info(xg_values)").fetchall()
    existing = {row[1] for row in info}
    for column, column_type in _STAT_COLUMNS.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE xg_values ADD COLUMN {column} {column_type}")
    return connection


def _fixture_datetime_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_xg_value(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= numeric <= MAX_XG_VALUE:
        return None
    return numeric


def season_fixture_index(
    league_id: int,
    season: int,
    fetch_list: FetchList,
    db_path: Path = XG_CACHE_PATH,
    *,
    max_age: timedelta = SEASON_INDEX_MAX_AGE,
) -> Optional[list[dict[str, Any]]]:
    """Kompakte Liste der abgeschlossenen Saisonspiele (gecacht).

    Einträge: {id, date, home_id, away_id, home_name, away_name}.
    """
    with closing(_connect(db_path)) as connection:
        row = connection.execute(
            "SELECT payload, fetched_at FROM season_index WHERE league_id = ? AND season = ?",
            (int(league_id), int(season)),
        ).fetchone()
        if row is not None:
            fetched_at = _fixture_datetime_utc(row[1])
            if fetched_at is not None and _utcnow() - fetched_at < max_age:
                try:
                    payload = json.loads(row[0])
                except ValueError:
                    payload = None
                if isinstance(payload, list):
                    return payload

    data = fetch_list(
        "fixtures",
        {"league": int(league_id), "season": int(season), "status": "FT"},
        f"xG-Saisonindex Liga {league_id}",
    )
    if data is None:
        return None
    compact: list[dict[str, Any]] = []
    for fixture in data:
        fixture_data = fixture.get("fixture") if isinstance(fixture, dict) else None
        teams = fixture.get("teams") if isinstance(fixture, dict) else None
        if not isinstance(fixture_data, dict) or not isinstance(teams, dict):
            continue
        fixture_id = fixture_data.get("id")
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        played_at = _fixture_datetime_utc(fixture_data.get("date"))
        if (
            isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or fixture_id <= 0
            or played_at is None
            or not isinstance(home.get("id"), int)
            or not isinstance(away.get("id"), int)
        ):
            continue
        compact.append(
            {
                "id": fixture_id,
                "date": played_at.isoformat(),
                "home_id": home["id"],
                "away_id": away["id"],
                "home_name": str(home.get("name") or ""),
                "away_name": str(away.get("name") or ""),
            }
        )
    with closing(_connect(db_path)) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO season_index (league_id, season, payload, fetched_at)"
            " VALUES (?, ?, ?, ?)",
            (int(league_id), int(season), json.dumps(compact), _iso(_utcnow())),
        )
    return compact


def cached_xg(db_path: Path = XG_CACHE_PATH) -> dict[int, tuple[float, float]]:
    """Alle gecachten xG-Paare: api_fixture_id -> (xg_home, xg_away)."""
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT fixture_id, xg_home, xg_away FROM xg_values"
            " WHERE xg_home IS NOT NULL AND xg_away IS NOT NULL"
        ).fetchall()
    return {int(row[0]): (float(row[1]), float(row[2])) for row in rows}


def cached_stats(db_path: Path = XG_CACHE_PATH) -> dict[int, dict[str, tuple[float, float]]]:
    """Alle gecachten Stat-Paare pro Fixture: xg / corners / yellow."""
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT fixture_id, xg_home, xg_away, corners_home, corners_away,"
            " yellow_home, yellow_away FROM xg_values"
        ).fetchall()
    result: dict[int, dict[str, tuple[float, float]]] = {}
    for fixture_id, xg_h, xg_a, c_h, c_a, y_h, y_a in rows:
        entry: dict[str, tuple[float, float]] = {}
        if xg_h is not None and xg_a is not None:
            entry["xg"] = (float(xg_h), float(xg_a))
        if c_h is not None and c_a is not None:
            entry["corners"] = (float(c_h), float(c_a))
        if y_h is not None and y_a is not None:
            entry["yellow"] = (float(y_h), float(y_a))
        if entry:
            result[int(fixture_id)] = entry
    return result


def _cached_missing(db_path: Path) -> set[int]:
    with closing(_connect(db_path)) as connection:
        rows = connection.execute("SELECT fixture_id FROM xg_missing").fetchall()
    return {int(row[0]) for row in rows}


def _parse_count(value: Any, *, maximum: int) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not numeric.is_integer() or not 0 <= numeric <= maximum:
        return None
    return int(numeric)


def _team_stat_map(block: dict[str, Any]) -> Optional[tuple[int, dict[str, Any]]]:
    team = block.get("team")
    entries = block.get("statistics")
    if not isinstance(team, dict) or not isinstance(entries, list):
        return None
    team_id = team.get("id")
    if not isinstance(team_id, int) or isinstance(team_id, bool):
        return None
    values = {
        entry.get("type"): entry.get("value")
        for entry in entries
        if isinstance(entry, dict)
    }
    return team_id, values


def _extract_fixture_stats(
    statistics: list[dict[str, Any]],
    home_id: int,
    away_id: int,
) -> Optional[dict[str, Optional[tuple[float, float]]]]:
    """xG-, Ecken- und Karten-Paare aus fixtures/statistics, Zuordnung per Team-ID.

    Liefert None bei ungültiger Struktur; einzelne Statistiken können fehlen.
    """
    per_team: dict[int, dict[str, Any]] = {}
    for block in statistics:
        if not isinstance(block, dict):
            return None
        mapped = _team_stat_map(block)
        if mapped is None:
            return None
        per_team[mapped[0]] = mapped[1]
    if home_id not in per_team or away_id not in per_team:
        return None
    home, away = per_team[home_id], per_team[away_id]

    def _pair(key: str, parser) -> Optional[tuple[float, float]]:
        home_value = parser(home.get(key))
        away_value = parser(away.get(key))
        if home_value is None or away_value is None:
            return None
        return home_value, away_value

    return {
        "xg": _pair("expected_goals", _parse_xg_value),
        "corners": _pair("Corner Kicks", lambda v: _parse_count(v, maximum=40)),
        "yellow": _pair("Yellow Cards", lambda v: _parse_count(v, maximum=20)),
    }


def fetch_missing_xg(
    fixtures: Iterable[dict[str, Any]],
    fetch_list: FetchList,
    db_path: Path = XG_CACHE_PATH,
    *,
    max_calls: int = 24,
    pause_seconds: float = 0.2,
) -> dict[str, int]:
    """Hole Statistiken für Index-Einträge ohne Cache-Eintrag (quotenbewusst)."""
    with closing(_connect(db_path)) as connection:
        present = {
            int(row[0])
            for row in connection.execute("SELECT fixture_id FROM xg_values").fetchall()
        }
    missing_marked = _cached_missing(db_path)
    todo = [
        entry
        for entry in fixtures
        if entry["id"] not in present and entry["id"] not in missing_marked
    ]
    # Neueste Spiele zuerst: Venue-/Formfenster brauchen vor allem frische Daten.
    todo.sort(key=lambda entry: entry["date"], reverse=True)
    stats = {"fetched": 0, "unavailable": 0, "skipped": len(todo) - min(len(todo), max_calls)}
    with closing(_connect(db_path)) as connection:
        for entry in todo[: max(0, int(max_calls))]:
            data = fetch_list(
                "fixtures/statistics",
                {"fixture": entry["id"]},
                f"Stats Fixture {entry['id']}",
            )
            if data is None:
                stats["skipped"] += 1
                continue
            extracted = _extract_fixture_stats(data, entry["home_id"], entry["away_id"])
            if extracted is None or not any(extracted.values()):
                connection.execute(
                    "INSERT OR REPLACE INTO xg_missing (fixture_id, fetched_at) VALUES (?, ?)",
                    (entry["id"], _iso(_utcnow())),
                )
                stats["unavailable"] += 1
            else:
                xg = extracted.get("xg") or (None, None)
                corners = extracted.get("corners") or (None, None)
                yellow = extracted.get("yellow") or (None, None)
                connection.execute(
                    "INSERT OR REPLACE INTO xg_values (fixture_id, xg_home, xg_away,"
                    " corners_home, corners_away, yellow_home, yellow_away, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry["id"], xg[0], xg[1], corners[0], corners[1],
                        yellow[0], yellow[1], _iso(_utcnow()),
                    ),
                )
                stats["fetched"] += 1
            if pause_seconds > 0:
                time.sleep(pause_seconds)
    return stats


def _index_by_teams_and_date(
    index: Iterable[dict[str, Any]],
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    by_pair: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for entry in index:
        by_pair.setdefault((entry["home_id"], entry["away_id"]), []).append(entry)
    return by_pair


def _resolve_api_fixture(
    history_row: dict[str, Any],
    name_to_team_id: dict[str, int],
    by_pair: dict[tuple[int, int], list[dict[str, Any]]],
) -> Optional[int]:
    """Bilde eine CSV-Historienzeile über Datum (±1 Tag) + Team-Mapping auf die API-ID ab."""
    teams = history_row.get("teams") or {}
    home_norm = _normalized_team_name((teams.get("home") or {}).get("name"))
    away_norm = _normalized_team_name((teams.get("away") or {}).get("name"))
    home_id = name_to_team_id.get(home_norm)
    away_id = name_to_team_id.get(away_norm)
    if home_id is None or away_id is None:
        return None
    candidates = by_pair.get((home_id, away_id))
    if not candidates:
        return None
    played_at = _fixture_datetime_utc((history_row.get("fixture") or {}).get("date"))
    if played_at is None:
        return None
    best: Optional[tuple[float, int]] = None
    for entry in candidates:
        entry_date = _fixture_datetime_utc(entry.get("date"))
        if entry_date is None:
            continue
        delta_days = abs((entry_date - played_at).total_seconds()) / 86_400.0
        if delta_days <= 1.5 and (best is None or delta_days < best[0]):
            best = (delta_days, entry["id"])
    return best[1] if best else None


def _history_stat_entries(history: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Index-ähnliche Einträge aus Historienzeilen mit echten API-IDs.

    Der gecachte Saisonindex kann bis zu SEASON_INDEX_MAX_AGE hinterherhinken;
    der frische API-Tail (jüngster Spieltag) wäre darin noch nicht enthalten.
    Diese Zeilen tragen aber bereits echte (positive) Fixture- und Team-IDs,
    also können ihre Statistiken direkt nachgeladen werden. CSV-Pseudo-IDs
    (negativ) laufen weiterhin über Index und Namensabgleich.
    """
    entries: list[dict[str, Any]] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        stats = row.get("challenge_stats")
        stats = stats if isinstance(stats, dict) else {}
        if all(key in stats for key in ("xg_home", "corners_home", "yellow_cards_home")):
            continue
        fixture_data = row.get("fixture")
        teams = row.get("teams")
        if not isinstance(fixture_data, dict) or not isinstance(teams, dict):
            continue
        fixture_id = fixture_data.get("id")
        home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
        away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
        home_id = home.get("id")
        away_id = away.get("id")
        played_at = _fixture_datetime_utc(fixture_data.get("date"))
        if (
            isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or fixture_id <= 0
            or isinstance(home_id, bool)
            or not isinstance(home_id, int)
            or home_id <= 0
            or isinstance(away_id, bool)
            or not isinstance(away_id, int)
            or away_id <= 0
            or home_id == away_id
            or played_at is None
        ):
            continue
        entries.append(
            {
                "id": fixture_id,
                "date": played_at.isoformat(),
                "home_id": home_id,
                "away_id": away_id,
                "home_name": str(home.get("name") or ""),
                "away_name": str(away.get("name") or ""),
            }
        )
    return entries


def annotate_history(
    history: list[dict[str, Any]],
    league_id: int,
    season: int,
    fetch_list: FetchList,
    db_path: Path = XG_CACHE_PATH,
    *,
    max_new_calls: int = 12,
) -> dict[str, Any]:
    """Reichere Historienzeilen in-place mit challenge_stats.xg_home/xg_away an.

    Liest zuerst nur den Cache, holt dann höchstens ``max_new_calls`` fehlende
    xG-Werte nach (neueste zuerst) und annotiert erneut. Fehler brechen den
    Scan nicht: Es wird einfach mit den vorhandenen Daten weitergearbeitet.
    """
    result: dict[str, Any] = {"annotated": 0, "fetched": 0, "unavailable": 0, "total": len(history)}
    if not history:
        return result

    # Schnellpfad: API-Historien tragen echte (positive) Fixture-IDs.
    index = season_fixture_index(league_id, season, fetch_list, db_path)
    by_pair = _index_by_teams_and_date(index or [])
    history_names = {
        _normalized_team_name((row.get("teams") or {}).get(side, {}).get("name"))
        for row in history
        for side in ("home", "away")
    }
    history_names.discard("")
    api_fixtures_for_mapping = [
        {
            "teams": {
                "home": {"id": entry["home_id"], "name": entry["home_name"]},
                "away": {"id": entry["away_id"], "name": entry["away_name"]},
            }
        }
        for entry in (index or [])
    ]
    name_to_team_id = _current_team_mapping(history_names, api_fixtures_for_mapping)

    def _api_id_for(row: dict[str, Any]) -> Optional[int]:
        fixture_data = row.get("fixture") or {}
        fixture_id = fixture_data.get("id")
        if isinstance(fixture_id, int) and not isinstance(fixture_id, bool) and fixture_id > 0:
            return fixture_id
        return _resolve_api_fixture(row, name_to_team_id, by_pair)

    def _annotate_from_cache() -> None:
        cache = cached_stats(db_path)
        for row in history:
            stats = row.get("challenge_stats")
            if not isinstance(stats, dict):
                stats = {}
                row["challenge_stats"] = stats
            needs_any = any(
                key not in stats
                for key in (
                    "xg_home", "xg_away",
                    "corners_home", "corners_away",
                    "yellow_cards_home", "yellow_cards_away",
                )
            )
            if not needs_any:
                continue
            api_id = _api_id_for(row)
            if api_id is None:
                continue
            entry = cache.get(api_id)
            if entry is None:
                continue
            # Nur fehlende Felder auffüllen; vorhandene (z. B. CSV-) Werte bleiben.
            if "xg" in entry and "xg_home" not in stats:
                stats["xg_home"], stats["xg_away"] = entry["xg"]
            if "corners" in entry and "corners_home" not in stats:
                stats["corners_home"], stats["corners_away"] = entry["corners"]
            if "yellow" in entry and "yellow_cards_home" not in stats:
                stats["yellow_cards_home"], stats["yellow_cards_away"] = entry["yellow"]

    _annotate_from_cache()

    # Fehlende Stats nachladen: Saisonindex (kann bis zu SEASON_INDEX_MAX_AGE
    # hinterherhinken) PLUS frische Historienzeilen mit echten API-IDs — damit
    # bekommt auch der jüngste Spieltag (API-Tail) sofort seine Statistiken.
    todo_entries: dict[int, dict[str, Any]] = {}
    if index:
        needed_ids = {
            api_id
            for api_id in (_api_id_for(row) for row in history)
            if api_id is not None
        }
        for entry in index:
            if entry["id"] in needed_ids:
                todo_entries[entry["id"]] = entry
    for entry in _history_stat_entries(history):
        todo_entries.setdefault(entry["id"], entry)
    if todo_entries:
        fetch_stats = fetch_missing_xg(
            list(todo_entries.values()),
            fetch_list,
            db_path,
            max_calls=max_new_calls,
            pause_seconds=0.2,
        )
        result["fetched"] = fetch_stats["fetched"]
        result["unavailable"] = fetch_stats["unavailable"]
        if fetch_stats["fetched"]:
            _annotate_from_cache()

    result["annotated"] = sum(
        1
        for row in history
        if isinstance(row.get("challenge_stats"), dict)
        and "xg_home" in row["challenge_stats"]
    )
    result["coverage"] = result["annotated"] / result["total"] if result["total"] else 0.0
    return result


def _provider_fetch(api_key: str) -> FetchList:
    import requests

    headers = {"x-apisports-key": api_key}
    base_url = "https://v3.football.api-sports.io"
    last_request = [0.0]

    def _fetch(path: str, params: dict[str, Any], label: str) -> Optional[list[dict[str, Any]]]:
        elapsed = time.monotonic() - last_request[0]
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        last_request[0] = time.monotonic()
        try:
            response = requests.get(
                f"{base_url}/{path}", headers=headers, params=params, timeout=20
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # Netzwerk/JSON — Backfill darf nie crashen
            print(f"FEHLER {label}: {exc}")
            return None
        if payload.get("errors"):
            print(f"FEHLER {label}: {payload['errors']}")
            return None
        data = payload.get("response")
        return data if isinstance(data, list) else None

    return _fetch


def main() -> None:
    parser = argparse.ArgumentParser(description="xG-Backfill für die Challenge-Historie")
    parser.add_argument("--league", type=int, required=True, help="API-League-ID, z. B. 78")
    parser.add_argument("--season", type=int, required=True, help="Saison-Startjahr, z. B. 2025")
    parser.add_argument(
        "--max-calls",
        type=int,
        default=400,
        help="Maximale Zahl neuer statistics-Calls in diesem Lauf",
    )
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(Path(__file__).resolve().with_name("config.ini"), encoding="utf-8")
    api_key = config.get("api", "api_football_key", fallback="").strip() or config.get(
        "api", "api_key", fallback=""
    ).strip()
    if not api_key:
        raise SystemExit("Kein API-Football-Key in config.ini gefunden")

    fetch = _provider_fetch(api_key)
    index = season_fixture_index(args.league, args.season, fetch, max_age=timedelta(0))
    if index is None:
        raise SystemExit("Saisonindex konnte nicht geladen werden (API-Fehler)")
    print(f"Saisonindex: {len(index)} abgeschlossene Spiele")
    stats = fetch_missing_xg(index, fetch, max_calls=args.max_calls, pause_seconds=0.3)
    cache = cached_xg()
    in_season = sum(1 for entry in index if entry["id"] in cache)
    print(
        f"Neu geholt: {stats['fetched']} | ohne xG: {stats['unavailable']} | "
        f"übersprungen: {stats['skipped']} | Cache-Abdeckung Saison: {in_season}/{len(index)}"
    )


if __name__ == "__main__":
    main()
