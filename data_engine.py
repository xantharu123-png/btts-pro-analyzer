"""
DATA ENGINE - SUPABASE/POSTGRESQL VERSION
==========================================
Nutzt Supabase (PostgreSQL) für persistente Daten auf Streamlit Cloud.
Fallback auf SQLite für lokale Entwicklung.

Season is selected dynamically per competition.
"""

import os
import time
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
import sqlite3

from api_budget import APIBudgetPriority, api_football_get
from config_loader import load_app_config
from season_utils import current_season_start_year
from league_catalog import ANALYZER_LEAGUE_IDS


def _load_supabase_url() -> Optional[str]:
    """Load the Supabase URL without printing secret material."""
    st_module = None
    try:
        import streamlit as st
        st_module = st
    except Exception:
        pass

    return load_app_config(st_module).supabase_db_url


_SUPABASE_URL_CACHE = _load_supabase_url()


def _check_postgres():
    """Check if psycopg2 is available (lazy import)."""
    try:
        import psycopg2
        return True
    except ImportError:
        return False


def _table_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _sqlite_legacy_table_name(cursor) -> str:
    base_name = "matches_legacy"
    table_name = base_name
    suffix = 1
    while _table_exists(cursor, table_name):
        suffix += 1
        table_name = f"{base_name}_{suffix}"
    return table_name


def _create_matches_table(cursor, use_postgres: bool):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            league_code TEXT,
            league_id INTEGER,
            date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_goals INTEGER,
            away_goals INTEGER,
            btts INTEGER,
            total_goals INTEGER,
            fetched_at TEXT
        )
    ''')


def _create_matches_indexes(cursor, use_postgres: bool):
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_league ON matches(league_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON matches(date)")
    if use_postgres:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team_id)")
    else:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_teams ON matches(home_team_id, away_team_id)")


def _migrate_sqlite_matches_if_needed(cursor):
    """Migrate the old local SQLite schema to the canonical matches schema."""
    if not _table_exists(cursor, "matches"):
        return

    columns = _table_columns(cursor, "matches")
    canonical = {"id", "date", "home_goals", "away_goals", "home_team", "away_team"}
    if canonical.issubset(columns):
        return

    legacy_required = {"match_id", "match_date", "home_score", "away_score"}
    if not legacy_required.issubset(columns):
        return

    legacy_name = _sqlite_legacy_table_name(cursor)
    cursor.execute(f"ALTER TABLE matches RENAME TO {legacy_name}")
    _create_matches_table(cursor, use_postgres=False)

    cursor.execute(f'''
        INSERT OR IGNORE INTO matches (
            id, league_code, league_id, date, home_team, away_team,
            home_team_id, away_team_id, home_goals, away_goals,
            btts, total_goals, fetched_at
        )
        SELECT
            m.match_id,
            m.league_code,
            NULL,
            m.match_date,
            COALESCE(home_team.name, 'Team ' || m.home_team_id),
            COALESCE(away_team.name, 'Team ' || m.away_team_id),
            m.home_team_id,
            m.away_team_id,
            m.home_score,
            m.away_score,
            m.btts,
            m.total_goals,
            m.last_updated
        FROM {legacy_name} m
        LEFT JOIN teams home_team ON home_team.team_id = m.home_team_id
        LEFT JOIN teams away_team ON away_team.team_id = m.away_team_id
    ''')


def _init_postgres_schema(cursor):
    _create_matches_table(cursor, use_postgres=True)
    try:
        _create_matches_indexes(cursor, use_postgres=True)
    except Exception:
        pass


def _init_sqlite_schema(cursor):
    _migrate_sqlite_matches_if_needed(cursor)
    _create_matches_table(cursor, use_postgres=False)
    _create_matches_indexes(cursor, use_postgres=False)


class DataEngine:
    """Data Engine for BetBoy - Supabase/PostgreSQL Support"""
    
    LEAGUES_CONFIG = ANALYZER_LEAGUE_IDS
    
    def __init__(self, api_key: str, db_path: str = "btts_data.db"):
        """Initialize Data Engine with Supabase or SQLite"""
        self.api_key = api_key
        self.db_path = db_path
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key}
        self.last_request = 0
        self.min_delay = 0.5
        self.last_error: Optional[str] = None
        
        # Use cached URL from module-level check
        global _SUPABASE_URL_CACHE
        self.supabase_url = _SUPABASE_URL_CACHE
        self.database_warning: Optional[str] = None
        
        # Check PostgreSQL availability
        postgres_available = _check_postgres()
        self.use_postgres = bool(self.supabase_url and postgres_available)
        
        if self.use_postgres:
            print("Using Supabase (PostgreSQL) - data persists.")
        else:
            if self.supabase_url and not postgres_available:
                print("SUPABASE_DB_URL found but psycopg2 is not available.")
            print("Using SQLite (local).")
        
        # A stale Streamlit secret must not make the whole analyzer unusable.
        # Streamlit's local SQLite storage is ephemeral, but it is still a
        # functional read/write fallback until the Supabase URL is corrected.
        try:
            self._init_database()
        except Exception as exc:
            if not self.use_postgres:
                raise
            self.database_warning = (
                "Supabase ist nicht erreichbar; diese Sitzung nutzt lokalen "
                f"SQLite-Speicher ({type(exc).__name__})."
            )
            print(f"WARNING: {self.database_warning}")
            self.use_postgres = False
            self.supabase_url = None
            self._init_database()
        print(f"Data Engine initialized with {len(self.LEAGUES_CONFIG)} leagues.")
    
    def _get_connection(self):
        """Get database connection (PostgreSQL or SQLite)"""
        if self.use_postgres:
            import psycopg2
            return psycopg2.connect(self.supabase_url)
        else:
            from db_paths import LEGACY_DB_NAME, PRIMARY_DB_NAME, ensure_primary_db
            if self.db_path in (LEGACY_DB_NAME, PRIMARY_DB_NAME):
                self.db_path = ensure_primary_db()
            return sqlite3.connect(self.db_path)
    
    def _get_placeholder(self) -> str:
        """Get SQL placeholder (? for SQLite, %s for PostgreSQL)"""
        return "%s" if self.use_postgres else "?"
    
    def _init_database(self):
        """Create or migrate database tables."""
        conn = self._get_connection()
        c = conn.cursor()

        if self.use_postgres:
            _init_postgres_schema(c)
        else:
            _init_sqlite_schema(c)

        conn.commit()
        conn.close()
        print(f"Database initialized ({'PostgreSQL' if self.use_postgres else 'SQLite'})")
    
    def _rate_limit(self):
        """Respect API rate limits"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    def fetch_league_matches(self, league_code: str, season: Optional[int] = None,
                            force_refresh: bool = False) -> int:
        """Fetch and store ALL finished matches for a league"""
        self.last_error = None
        if not isinstance(league_code, str) or not league_code.strip():
            self.last_error = "Invalid league code"
            return 0
        league_id = self.LEAGUES_CONFIG.get(league_code)
        if not league_id:
            self.last_error = "Unknown league code"
            print(f"ERROR: Unknown league: {league_code}")
            return 0
        season = season if season is not None else current_season_start_year(league_code)
        if (
            isinstance(season, bool)
            or not isinstance(season, int)
            or not 1900 <= season <= 2100
            or not isinstance(force_refresh, bool)
        ):
            self.last_error = "Invalid fetch parameters"
            return 0
        
        print(f"Fetching {league_code} (season {season})...")
        
        try:
            self._rate_limit()
            
            response = api_football_get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': season,
                    'status': 'FT'
                },
                timeout=30,
                priority=APIBudgetPriority.BACKGROUND,
                label=f"historical fixtures {league_code}",
            )
            
            if response.status_code != 200:
                self.last_error = f"HTTP {response.status_code}"
                print(f"ERROR: API status {response.status_code} for {league_code}")
                return 0
            
            data = response.json()
            provider_errors = data.get('errors') if isinstance(data, dict) else None
            if provider_errors:
                self.last_error = (
                    "; ".join(f"{key}: {value}" for key, value in provider_errors.items())
                    if isinstance(provider_errors, dict)
                    else str(provider_errors)
                )
                print(f"ERROR: API provider error for {league_code}: {self.last_error}")
                return 0
            fixtures = data.get('response') if isinstance(data, dict) else None
            if not isinstance(fixtures, list):
                self.last_error = "Invalid fixtures response"
                return 0
            
            if not fixtures:
                print(f"WARNING: No finished matches for {league_code}")
                return 0

            normalized_fixtures = []
            seen_fixture_ids = set()
            for fixture in fixtures:
                try:
                    match_id = fixture['fixture']['id']
                    match_date = fixture['fixture']['date']
                    home_team = fixture['teams']['home']['name']
                    away_team = fixture['teams']['away']['name']
                    home_id = fixture['teams']['home']['id']
                    away_id = fixture['teams']['away']['id']
                    home_goals = fixture['goals']['home']
                    away_goals = fixture['goals']['away']
                    fixture_league_id = fixture['league']['id']
                    if not isinstance(match_date, str) or not match_date.strip():
                        raise ValueError
                    parsed_date = datetime.fromisoformat(
                        match_date.replace('Z', '+00:00')
                    )
                except (KeyError, TypeError, ValueError, AttributeError):
                    self.last_error = "Invalid fixture entry"
                    return 0
                if (
                    parsed_date.tzinfo is None
                    or isinstance(match_id, bool)
                    or not isinstance(match_id, int)
                    or match_id <= 0
                    or match_id in seen_fixture_ids
                    or isinstance(fixture_league_id, bool)
                    or fixture_league_id != league_id
                    or isinstance(home_id, bool)
                    or isinstance(away_id, bool)
                    or not isinstance(home_id, int)
                    or not isinstance(away_id, int)
                    or home_id <= 0
                    or away_id <= 0
                    or home_id == away_id
                    or not isinstance(home_team, str)
                    or not isinstance(away_team, str)
                    or not home_team.strip()
                    or not away_team.strip()
                    or home_team.strip() == away_team.strip()
                    or parsed_date.astimezone(timezone.utc) > datetime.now(timezone.utc)
                    or isinstance(home_goals, bool)
                    or isinstance(away_goals, bool)
                    or not isinstance(home_goals, int)
                    or not isinstance(away_goals, int)
                    or not 0 <= home_goals <= 30
                    or not 0 <= away_goals <= 30
                ):
                    self.last_error = "Invalid fixture entry"
                    return 0
                seen_fixture_ids.add(match_id)
                normalized_fixtures.append((
                    match_id,
                    match_date,
                    home_team.strip(),
                    away_team.strip(),
                    home_id,
                    away_id,
                    home_goals,
                    away_goals,
                ))

            # Process matches
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()

            count = 0
            for (
                match_id,
                match_date,
                home_team,
                away_team,
                home_id,
                away_id,
                home_goals,
                away_goals,
            ) in normalized_fixtures:
                try:
                    btts = 1 if (home_goals > 0 and away_goals > 0) else 0
                    total = home_goals + away_goals
                    
                    # Upsert
                    if self.use_postgres:
                        c.execute(f'''
                            INSERT INTO matches (id, league_code, league_id, date, home_team, away_team,
                                               home_team_id, away_team_id, home_goals, away_goals,
                                               btts, total_goals, fetched_at)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                            ON CONFLICT (id) DO UPDATE SET
                                home_goals = EXCLUDED.home_goals,
                                away_goals = EXCLUDED.away_goals,
                                btts = EXCLUDED.btts,
                                total_goals = EXCLUDED.total_goals,
                                fetched_at = EXCLUDED.fetched_at
                        ''', (match_id, league_code, league_id, match_date, home_team, away_team,
                              home_id, away_id, home_goals, away_goals, btts, total, 
                              datetime.now(timezone.utc).isoformat()))
                    else:
                        c.execute(f'''
                            INSERT OR REPLACE INTO matches 
                            (id, league_code, league_id, date, home_team, away_team,
                             home_team_id, away_team_id, home_goals, away_goals,
                             btts, total_goals, fetched_at)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ''', (match_id, league_code, league_id, match_date, home_team, away_team,
                              home_id, away_id, home_goals, away_goals, btts, total,
                              datetime.now(timezone.utc).isoformat()))
                    
                    count += 1
                    
                except (KeyError, TypeError, ValueError) as exc:
                    conn.rollback()
                    conn.close()
                    raise ValueError("Could not store normalized fixture batch") from exc
            
            conn.commit()
            conn.close()
            
            print(f"{league_code}: {count} matches stored")
            return count
            
        except Exception as e:
            self.last_error = type(e).__name__
            print(f"ERROR: Could not fetch {league_code}: {e}")
            return 0
    
    def get_match_count(self, league_code: str = None) -> int:
        """Get total matches in database"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            if league_code:
                c.execute(f'SELECT COUNT(*) FROM matches WHERE league_code = {ph}', (league_code,))
            else:
                c.execute('SELECT COUNT(*) FROM matches')
            
            count = c.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
    
    def get_team_stats(self, team_id: int, league_code: str, venue: str = 'all') -> Optional[Dict]:
        """Get team statistics from database"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            if venue == 'home':
                c.execute(f'''
                    SELECT 
                        COUNT(*) as matches,
                        AVG(home_goals) as avg_scored,
                        AVG(away_goals) as avg_conceded,
                        SUM(btts) * 100.0 / COUNT(*) as btts_rate
                    FROM matches
                    WHERE home_team_id = {ph} AND league_code = {ph}
                      AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                      AND btts IS NOT NULL
                ''', (team_id, league_code))
            elif venue == 'away':
                c.execute(f'''
                    SELECT 
                        COUNT(*) as matches,
                        AVG(away_goals) as avg_scored,
                        AVG(home_goals) as avg_conceded,
                        SUM(btts) * 100.0 / COUNT(*) as btts_rate
                    FROM matches
                    WHERE away_team_id = {ph} AND league_code = {ph}
                      AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                      AND btts IS NOT NULL
                ''', (team_id, league_code))
            else:
                c.execute(f'''
                    SELECT 
                        COUNT(*) as matches,
                        AVG(CASE WHEN home_team_id = {ph} THEN home_goals ELSE away_goals END) as avg_scored,
                        AVG(CASE WHEN home_team_id = {ph} THEN away_goals ELSE home_goals END) as avg_conceded,
                        SUM(btts) * 100.0 / COUNT(*) as btts_rate
                    FROM matches
                    WHERE (home_team_id = {ph} OR away_team_id = {ph}) AND league_code = {ph}
                      AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                      AND btts IS NOT NULL
                ''', (team_id, team_id, team_id, team_id, league_code))
            
            row = c.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                return {
                    'matches_played': row[0],
                    'avg_scored': round(row[1], 2) if row[1] is not None else None,
                    'avg_conceded': round(row[2], 2) if row[2] is not None else None,
                    'btts_rate': round(row[3], 1) if row[3] is not None else None,
                }

            return {
                'matches_played': 0,
                'avg_scored': None,
                'avg_conceded': None,
                'btts_rate': None,
            }
            
        except Exception as e:
            print(f"Stats error: {e}")
            return {
                'matches_played': 0,
                'avg_scored': None,
                'avg_conceded': None,
                'btts_rate': None,
            }
    
    def get_recent_form(self, team_id: int, league_code: str, 
                       venue: str = 'all', last_n: int = 5) -> Optional[Dict]:
        """Get recent form for a team"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            if venue == 'home':
                c.execute(f'''
                    SELECT home_goals, away_goals, btts
                    FROM matches
                    WHERE home_team_id = {ph} AND league_code = {ph}
                    ORDER BY date DESC
                    LIMIT {ph}
                ''', (team_id, league_code, last_n))
            elif venue == 'away':
                c.execute(f'''
                    SELECT away_goals, home_goals, btts
                    FROM matches
                    WHERE away_team_id = {ph} AND league_code = {ph}
                    ORDER BY date DESC
                    LIMIT {ph}
                ''', (team_id, league_code, last_n))
            else:
                c.execute(f'''
                    SELECT 
                        CASE WHEN home_team_id = {ph} THEN home_goals ELSE away_goals END,
                        CASE WHEN home_team_id = {ph} THEN away_goals ELSE home_goals END,
                        btts
                    FROM matches
                    WHERE (home_team_id = {ph} OR away_team_id = {ph}) AND league_code = {ph}
                    ORDER BY date DESC
                    LIMIT {ph}
                ''', (team_id, team_id, team_id, team_id, league_code, last_n))
            
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                return {
                    'btts_rate': None,
                    'avg_scored': None,
                    'avg_conceded': None,
                    'matches': 0,
                }
            
            btts_count = sum(r[2] for r in rows)
            avg_scored = sum(r[0] for r in rows) / len(rows)
            avg_conceded = sum(r[1] for r in rows) / len(rows)
            
            return {
                'btts_rate': round(btts_count / len(rows) * 100, 1),
                'avg_scored': round(avg_scored, 2),
                'avg_conceded': round(avg_conceded, 2),
                'matches': len(rows)
            }
            
        except Exception as e:
            print(f"Form error: {e}")
            return {
                'btts_rate': None,
                'avg_scored': None,
                'avg_conceded': None,
                'matches': 0,
            }
    
    def calculate_head_to_head(self, team1_id: int, team2_id: int, 
                               last_n: int = 10) -> Optional[Dict]:
        """Calculate H2H statistics"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            c.execute(f'''
                SELECT home_goals, away_goals, btts, home_team_id
                FROM matches
                WHERE (home_team_id = {ph} AND away_team_id = {ph})
                   OR (home_team_id = {ph} AND away_team_id = {ph})
                ORDER BY date DESC
                LIMIT {ph}
            ''', (team1_id, team2_id, team2_id, team1_id, last_n))
            
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                return {'btts_rate': None, 'avg_goals': None, 'matches_played': 0}
            
            btts_count = sum(r[2] for r in rows)
            total_goals = sum(r[0] + r[1] for r in rows)
            
            return {
                'btts_rate': round(btts_count / len(rows) * 100, 1),
                'avg_goals': round(total_goals / len(rows), 2),
                'matches_played': len(rows)
            }
            
        except Exception as e:
            print(f"H2H error: {e}")
            return {'btts_rate': None, 'avg_goals': None, 'matches_played': 0}
    
    def get_league_stats(self, league_code: str) -> Optional[Dict]:
        """Get league-wide statistics"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            c.execute(f'''
                SELECT 
                    COUNT(*) as total_matches,
                    AVG(home_goals) as avg_home_scored,
                    AVG(away_goals) as avg_away_scored,
                    AVG(total_goals) as avg_total,
                    SUM(btts) * 100.0 / COUNT(*) as btts_rate
                FROM matches
                WHERE league_code = {ph}
            ''', (league_code,))
            
            row = c.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                return {
                    'total_matches': row[0],
                    'avg_home_scored': round(row[1], 2) if row[1] is not None else None,
                    'avg_away_scored': round(row[2], 2) if row[2] is not None else None,
                    'avg_home_conceded': round(row[2], 2) if row[2] is not None else None,
                    'avg_away_conceded': round(row[1], 2) if row[1] is not None else None,
                    'avg_total_goals': round(row[3], 2) if row[3] is not None else None,
                    'btts_rate': round(row[4], 1) if row[4] is not None else None,
                }
            
            return {
                'total_matches': 0,
                'avg_home_scored': None,
                'avg_away_scored': None,
                'avg_home_conceded': None,
                'avg_away_conceded': None,
                'avg_total_goals': None,
                'btts_rate': None,
            }
            
        except Exception as e:
            print(f"League stats error: {e}")
            return None


if __name__ == '__main__':
    print("=" * 60)
    print("DATA ENGINE TEST")
    print("=" * 60)
    
    engine = DataEngine(api_key="test_key")
    print(f"\nInitialized with {len(engine.LEAGUES_CONFIG)} leagues")
    print(f"Database type: {'PostgreSQL (Supabase)' if engine.use_postgres else 'SQLite'}")
    print(f"Current matches in DB: {engine.get_match_count()}")
