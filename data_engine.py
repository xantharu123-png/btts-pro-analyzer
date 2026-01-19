"""
DATA ENGINE - SUPABASE/POSTGRESQL VERSION
==========================================
Nutzt Supabase (PostgreSQL) für persistente Daten auf Streamlit Cloud.
Fallback auf SQLite für lokale Entwicklung.

Season: 2025 (für 2024/25 Saison)
"""

import os
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3

# ========== SUPABASE DEBUG BEIM IMPORT ==========
print("=" * 50)
print("🔍 SUPABASE CONNECTION TEST")
print("=" * 50)

_SUPABASE_URL_CACHE = None

try:
    import streamlit as st
    print("✅ streamlit importiert")
    
    if hasattr(st, 'secrets'):
        print(f"   st.secrets vorhanden: True")
        try:
            keys = list(st.secrets.keys())
            print(f"   Verfügbare Keys: {keys}")
        except Exception as e:
            print(f"   Keys auflisten fehlgeschlagen: {e}")
        
        if 'SUPABASE_DB_URL' in st.secrets:
            _SUPABASE_URL_CACHE = st.secrets['SUPABASE_DB_URL']
            print(f"✅ SUPABASE_DB_URL gefunden!")
            print(f"   Länge: {len(_SUPABASE_URL_CACHE)}")
            print(f"   Start: {_SUPABASE_URL_CACHE[:35]}...")
        else:
            print("❌ SUPABASE_DB_URL NICHT in st.secrets!")
    else:
        print("   st.secrets vorhanden: False")
except Exception as e:
    print(f"❌ Streamlit Import Fehler: {e}")

# Fallback: Environment
if not _SUPABASE_URL_CACHE:
    _SUPABASE_URL_CACHE = os.environ.get('SUPABASE_DB_URL')
    if _SUPABASE_URL_CACHE:
        print(f"✅ SUPABASE_DB_URL aus Environment geladen")

# Test PostgreSQL Connection
try:
    import psycopg2
    print("✅ psycopg2 importiert")
    
    if _SUPABASE_URL_CACHE:
        try:
            test_conn = psycopg2.connect(_SUPABASE_URL_CACHE)
            test_conn.close()
            print("✅ POSTGRESQL VERBINDUNG ERFOLGREICH!")
        except Exception as e:
            print(f"❌ PostgreSQL Connection Error: {e}")
except ImportError:
    print("❌ psycopg2 NICHT installiert!")

print("=" * 50)
# ========== DEBUG ENDE ==========


def _check_postgres():
    """Check if psycopg2 is available (lazy import)"""
    try:
        import psycopg2
        return True
    except ImportError:
        return False


class DataEngine:
    """Data Engine for BTTS Pro Analyzer - Supabase/PostgreSQL Support"""
    
    # ALL 28 LEAGUES
    LEAGUES_CONFIG = {
        # TIER 1: TOP LEAGUES
        'BL1': 78,    # Bundesliga
        'PL': 39,     # Premier League
        'PD': 140,    # La Liga
        'SA': 135,    # Serie A
        'FL1': 61,    # Ligue 1
        'DED': 88,    # Eredivisie
        'PPL': 94,    # Primeira Liga
        'TSL': 203,   # Super Lig
        'ELC': 40,    # Championship
        'BL2': 79,    # Bundesliga 2
        'MX1': 262,   # Liga MX
        'BSA': 71,    # Brasileirao
        
        # TIER 1: EUROPEAN CUPS
        'CL': 2,      # Champions League
        'EL': 3,      # Europa League
        'ECL': 848,   # Conference League
        
        # TIER 2: EU EXPANSION
        'SC1': 179,   # Scottish Premiership
        'BE1': 144,   # Belgian Pro League
        'SL1': 207,   # Swiss Super League
        'AL1': 218,   # Austrian Bundesliga
        
        # TIER 3: GOAL FESTIVALS
        'SPL': 265,   # Allsvenskan
        'ESI': 330,   # Paraguay
        'IS2': 165,   # Iceland
        'ALE': 188,   # Albania
        
        # TIER 4: GLOBAL
        'ED1': 89,    # Danish Superliga
        'CHL': 209,   # Chile
        'ALL': 113,   # J-League
        'QSL': 292,   # Qatar
        'UAE': 301,   # UAE
    }
    
    def __init__(self, api_key: str, db_path: str = "btts_data.db"):
        """Initialize Data Engine with Supabase or SQLite"""
        self.api_key = api_key
        self.db_path = db_path
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key}
        self.last_request = 0
        self.min_delay = 0.5
        
        # Use cached URL from module-level check
        global _SUPABASE_URL_CACHE
        self.supabase_url = _SUPABASE_URL_CACHE
        
        # Check PostgreSQL availability
        postgres_available = _check_postgres()
        self.use_postgres = bool(self.supabase_url and postgres_available)
        
        if self.use_postgres:
            print("✅ Using Supabase (PostgreSQL) - Data persists!")
        else:
            if self.supabase_url and not postgres_available:
                print("⚠️ SUPABASE_DB_URL found but psycopg2 not available!")
            print("⚠️ Using SQLite (local) - Data lost on restart!")
        
        # Initialize database
        self._init_database()
        print(f"✅ Data Engine initialized with {len(self.LEAGUES_CONFIG)} leagues!")
    
    def _get_connection(self):
        """Get database connection (PostgreSQL or SQLite)"""
        if self.use_postgres:
            import psycopg2
            return psycopg2.connect(self.supabase_url)
        else:
            return sqlite3.connect(self.db_path)
    
    def _get_placeholder(self) -> str:
        """Get SQL placeholder (? for SQLite, %s for PostgreSQL)"""
        return "%s" if self.use_postgres else "?"
    
    def _init_database(self):
        """Create database tables"""
        conn = self._get_connection()
        c = conn.cursor()
        
        if self.use_postgres:
            # PostgreSQL Schema
            c.execute('''
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
            
            # Indexes
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_league ON matches(league_code)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_date ON matches(date)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team_id)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team_id)')
            except:
                pass
        else:
            # SQLite Schema
            c.execute('''
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
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_league ON matches(league_code)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_date ON matches(date)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_teams ON matches(home_team_id, away_team_id)')
        
        conn.commit()
        conn.close()
        print(f"✅ Database initialized ({'PostgreSQL' if self.use_postgres else 'SQLite'})")
    
    def _rate_limit(self):
        """Respect API rate limits"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    def fetch_league_matches(self, league_code: str, season: int = 2025, 
                            force_refresh: bool = False) -> int:
        """Fetch and store ALL finished matches for a league"""
        league_id = self.LEAGUES_CONFIG.get(league_code)
        if not league_id:
            print(f"❌ Unknown league: {league_code}")
            return 0
        
        print(f"📡 Fetching {league_code} (season {season})...")
        
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': season,
                    'status': 'FT'
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ API Error {response.status_code} for {league_code}")
                return 0
            
            data = response.json()
            fixtures = data.get('response', [])
            
            if not fixtures:
                print(f"⚠️ No finished matches for {league_code}")
                return 0
            
            # Process matches
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            count = 0
            for fixture in fixtures:
                try:
                    match_id = fixture['fixture']['id']
                    match_date = fixture['fixture']['date'][:10]
                    home_team = fixture['teams']['home']['name']
                    away_team = fixture['teams']['away']['name']
                    home_id = fixture['teams']['home']['id']
                    away_id = fixture['teams']['away']['id']
                    home_goals = fixture['goals']['home'] or 0
                    away_goals = fixture['goals']['away'] or 0
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
                              datetime.now().isoformat()))
                    else:
                        c.execute(f'''
                            INSERT OR REPLACE INTO matches 
                            (id, league_code, league_id, date, home_team, away_team,
                             home_team_id, away_team_id, home_goals, away_goals,
                             btts, total_goals, fetched_at)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ''', (match_id, league_code, league_id, match_date, home_team, away_team,
                              home_id, away_id, home_goals, away_goals, btts, total,
                              datetime.now().isoformat()))
                    
                    count += 1
                    
                except Exception as e:
                    continue
            
            conn.commit()
            conn.close()
            
            print(f"✅ {league_code}: {count} matches stored")
            return count
            
        except Exception as e:
            print(f"❌ Error fetching {league_code}: {e}")
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
        except:
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
                ''', (team_id, team_id, team_id, team_id, league_code))
            
            row = c.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                return {
                    'matches_played': row[0],
                    'avg_scored': round(row[1] or 1.3, 2),
                    'avg_conceded': round(row[2] or 1.2, 2),
                    'btts_rate': round(row[3] or 50, 1)
                }
            
            return {
                'matches_played': 0,
                'avg_scored': 1.3,
                'avg_conceded': 1.2,
                'btts_rate': 55
            }
            
        except Exception as e:
            print(f"⚠️ Stats error: {e}")
            return {
                'matches_played': 0,
                'avg_scored': 1.3,
                'avg_conceded': 1.2,
                'btts_rate': 55
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
                return {'btts_rate': 50, 'avg_scored': 1.3, 'avg_conceded': 1.2, 'matches': 0}
            
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
            print(f"⚠️ Form error: {e}")
            return {'btts_rate': 50, 'avg_scored': 1.3, 'avg_conceded': 1.2, 'matches': 0}
    
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
                return {'btts_rate': 50, 'avg_goals': 2.5, 'matches_played': 0}
            
            btts_count = sum(r[2] for r in rows)
            total_goals = sum(r[0] + r[1] for r in rows)
            
            return {
                'btts_rate': round(btts_count / len(rows) * 100, 1),
                'avg_goals': round(total_goals / len(rows), 2),
                'matches_played': len(rows)
            }
            
        except Exception as e:
            print(f"⚠️ H2H error: {e}")
            return {'btts_rate': 50, 'avg_goals': 2.5, 'matches_played': 0}
    
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
                    'avg_home_scored': round(row[1] or 1.5, 2),
                    'avg_away_scored': round(row[2] or 1.2, 2),
                    'avg_home_conceded': round(row[2] or 1.2, 2),
                    'avg_away_conceded': round(row[1] or 1.5, 2),
                    'avg_total_goals': round(row[3] or 2.7, 2),
                    'btts_rate': round(row[4] or 52, 1)
                }
            
            return {
                'total_matches': 0,
                'avg_home_scored': 1.5,
                'avg_away_scored': 1.2,
                'avg_home_conceded': 1.2,
                'avg_away_conceded': 1.5,
                'avg_total_goals': 2.7,
                'btts_rate': 52
            }
            
        except Exception as e:
            print(f"⚠️ League stats error: {e}")
            return None


if __name__ == '__main__':
    print("=" * 60)
    print("DATA ENGINE TEST")
    print("=" * 60)
    
    engine = DataEngine(api_key="test_key")
    print(f"\n✅ Initialized with {len(engine.LEAGUES_CONFIG)} leagues")
    print(f"Database type: {'PostgreSQL (Supabase)' if engine.use_postgres else 'SQLite'}")
    print(f"Current matches in DB: {engine.get_match_count()}")
