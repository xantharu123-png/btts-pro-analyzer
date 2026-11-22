"""Small, shared cache of API-Football league/season capabilities, not match data."""
from contextlib import closing
import sqlite3
from time import time

from runtime_paths import (
    RUNTIME_STATE_DIR, RuntimeArtifactTrustError, prepare_trusted_runtime_database_path,
)


CACHE_PATH = RUNTIME_STATE_DIR / "football_coverage.db"
TTL_SECONDS = 24 * 60 * 60
MAX_ENTRIES = 512
_CACHE_ERRORS = (OSError, sqlite3.Error, RuntimeArtifactTrustError)
_TABLE = """CREATE TABLE IF NOT EXISTS api_football_coverage_v1 (
    league INTEGER NOT NULL, season INTEGER NOT NULL, observed REAL NOT NULL,
    injuries INTEGER NOT NULL CHECK(injuries IN (0, 1)),
    lineups INTEGER NOT NULL CHECK(lineups IN (0, 1)), PRIMARY KEY (league, season))"""


def _valid_key(league_id, season):
    return all(type(value) is int and 0 < value < 2**63 for value in (league_id, season))


def load_coverage(league_id: int, season: int) -> dict[str, bool] | None:
    """A cache failure is a miss, never an assertion that a league is uncovered."""
    if not _valid_key(league_id, season):
        return None
    try:
        if not CACHE_PATH.is_file():
            return None
        path = prepare_trusted_runtime_database_path(CACHE_PATH)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.25)) as db:
            row = db.execute("""SELECT observed, injuries, lineups FROM api_football_coverage_v1
                WHERE league=? AND season=?""", (league_id, season)).fetchone()
    except _CACHE_ERRORS:
        return None
    if (not row or type(row[0]) not in (float, int) or not 0 <= time() - row[0] < TTL_SECONDS
            or any(type(value) is not int or value not in (0, 1) for value in row[1:])):
        return None
    return {"injuries": bool(row[1]), "lineups": bool(row[2])}


def remember_coverage(league_id: int, season: int, data) -> dict[str, bool] | None:
    """Only admit a unique matching native identity and two explicit provider booleans."""
    if not _valid_key(league_id, season) or not isinstance(data, list) or len(data) != 1:
        return None
    item = data[0]
    if not isinstance(item, dict) or not isinstance(league := item.get("league"), dict):
        return None
    seasons = item.get("seasons")
    if (type(league.get("id")) is not int or league["id"] != league_id or not isinstance(seasons, list)
            or any(not isinstance(s, dict) or type(s.get("year")) is not int for s in seasons)):
        return None
    matches = [s for s in seasons if s["year"] == season]
    if len(matches) != 1 or not isinstance(coverage := matches[0].get("coverage"), dict):
        return None
    fixtures = coverage.get("fixtures")
    if (type(coverage.get("injuries")) is not bool or not isinstance(fixtures, dict)
            or type(fixtures.get("lineups")) is not bool):
        return None
    injuries, lineups = coverage["injuries"], fixtures["lineups"]
    observed = time()
    try:
        path = prepare_trusted_runtime_database_path(CACHE_PATH)
        with closing(sqlite3.connect(path, timeout=0.25)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(_TABLE)
            db.execute("DELETE FROM api_football_coverage_v1 WHERE observed <= ? OR observed > ?",
                       (observed - TTL_SECONDS, time()))
            db.execute("""INSERT INTO api_football_coverage_v1 (league,season,observed,injuries,lineups)
                VALUES (?,?,?,?,?) ON CONFLICT(league,season) DO UPDATE SET
                observed=excluded.observed, injuries=excluded.injuries, lineups=excluded.lineups
                WHERE excluded.observed >= api_football_coverage_v1.observed""",
                       (league_id, season, observed, injuries, lineups))
            db.execute("""DELETE FROM api_football_coverage_v1 WHERE rowid IN (
                SELECT rowid FROM api_football_coverage_v1 ORDER BY observed DESC, rowid DESC LIMIT -1 OFFSET ?)""",
                       (MAX_ENTRIES,))
    except _CACHE_ERRORS:
        pass  # Read-only/corrupt/busy cache: the actual provider answer still owns this call.
    return {"injuries": injuries, "lineups": lineups}
