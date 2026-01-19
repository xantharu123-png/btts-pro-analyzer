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

# Database imports
import sqlite3


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
        'BL1': 78,    # 🇩🇪 Bundesliga
        'PL': 39,     # 🇬🇧 Premier League
        'PD': 140,    # 🇪🇸 La Liga
        'SA': 135,    # 🇮🇹 Serie A
        'FL1': 61,    # 🇫🇷 Ligue 1
        'DED': 88,    # 🇳🇱 Eredivisie
        'PPL': 94,    # 🇵🇹 Primeira Liga
        'TSL': 203,   # 🇹🇷 Süper Lig
        'ELC': 40,    # 🇬🇧 Championship
        'BL2': 79,    # 🇩🇪 Bundesliga 2
        'MX1': 262,   # 🇲🇽 Liga MX
        'BSA': 71,    # 🇧🇷 Brasileirão
        
        # TIER 1: EUROPEAN CUPS
        'CL': 2,      # 🏆 Champions League
        'EL': 3,      # 🏆 Europa League
        'ECL': 848,   # 🏆 Conference League
        
        # TIER 2: EU EXPANSION
        'SC1': 179,   # 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Premiership
        'BE1': 144,   # 🇧🇪 Belgian Pro League
        'SL1': 207,   # 🇨🇭 Swiss Super League
        'AL1': 218,   # 🇦🇹 Austrian Bundesliga
        
        # TIER 3: GOAL FESTIVALS
        'SPL': 265,   # 🇸🇪 Allsvenskan
        'ESI': 330,   # 🇵🇾 Paraguay
        'IS2': 165,   # 🇮🇸 Iceland
        'ALE': 188,   # 🇦🇱 Albania
        
        # TIER 4: GLOBAL
        'ED1': 89,    # 🇩🇰 Danish Superliga
        'CHL': 209,   # 🇨🇱 Chile
        'ALL': 113,   # 🇯🇵 J-League
        'QSL': 292,   # 🇶🇦 Qatar
        'UAE': 301,   # 🇦🇪 UAE
    }
    
    def __init__(self, api_key: str, db_path: str = "btts_data.db"):
        """Initialize Data Engine with Supabase or SQLite"""
        self.api_key = api_key
        self.db_path = db_path
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key}
        self.last_request = 0
        self.min_delay = 0.5
        
        # Check for Supabase URL
        self.supabase_url = self._get_supabase_url()
        
        # Lazy check for PostgreSQL
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
    
    def _get_supabase_url(self) -> Optional[str]:
        """Get Supabase URL from Streamlit secrets or environment"""
        # Try Streamlit secrets first
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'SUPABASE_DB_URL' in st.secrets:
                return st.secrets['SUPABASE_DB_URL']
        except:
            pass
        
        # Try environment variable
        return os.environ.get('SUPABASE_DB_URL')
    
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
            c.execute('CREATE INDEX IF NOT EXISTS idx_league ON matches(league_code)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_date ON matches(date)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team_id)')
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
    
    # =========================================================
    # FETCH METHODS
    # =========================================================
    
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
                print(f"⚠️ No matches found for {league_code} season {season}")
                return 0
            
            conn = self._get_connection()
            c = conn.cursor()
            ph = self._get_placeholder()
            
            saved = 0
            for match in fixtures:
                try:
                    fixture = match.get('fixture', {})
                    teams = match.get('teams', {})
                    goals = match.get('goals', {})
                    
                    fixture_id = fixture.get('id')
                    home_goals = goals.get('home') or 0
                    away_goals = goals.get('away') or 0
                    btts = 1 if (home_goals > 0 and away_goals > 0) else 0
                    
                    if self.use_postgres:
                        # PostgreSQL: UPSERT
                        c.execute(f'''
                            INSERT INTO matches 
                            (id, league_code, league_id, date, home_team, away_team,
                             home_team_id, away_team_id, home_goals, away_goals, 
                             btts, total_goals, fetched_at)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                            ON CONFLICT (id) DO UPDATE SET
                                home_goals = EXCLUDED.home_goals,
                                away_goals = EXCLUDED.away_goals,
                                btts = EXCLUDED.btts,
                                total_goals = EXCLUDED.total_goals,
                                fetched_at = EXCLUDED.fetched_at
                        ''', (
                            fixture_id, league_code, league_id,
                            fixture.get('date'),
                            teams.get('home', {}).get('name'),
                            teams.get('away', {}).get('name'),
                            teams.get('home', {}).get('id'),
                            teams.get('away', {}).get('id'),
                            home_goals, away_goals, btts,
                            home_goals + away_goals,
                            datetime.now().isoformat()
                        ))
                    else:
                        # SQLite: INSERT OR REPLACE
                        c.execute(f'''
                            INSERT OR REPLACE INTO matches 
                            (id, league_code, league_id, date, home_team, away_team,
                             home_team_id, away_team_id, home_goals, away_goals, 
                             btts, total_goals, fetched_at)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ''', (
                            fixture_id, league_code, league_id,
                            fixture.get('date'),
                            teams.get('home', {}).get('name'),
                            teams.get('away', {}).get('name'),
                            teams.get('home', {}).get('id'),
                            teams.get('away', {}).get('id'),
                            home_goals, away_goals, btts,
                            home_goals + away_goals,
                            datetime.now().isoformat()
                        ))
                    saved += 1
                    
                except Exception as e:
                    print(f"⚠️ Error saving match: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            print(f"✅ {league_code}: {saved} matches saved")
            return saved
            
        except Exception as e:
            print(f"❌ Error fetching {league_code}: {e}")
            return 0
    
    def fetch_all_leagues(self, season: int = 2025) -> int:
        """Fetch ALL 28 leagues"""
        print(f"\n{'='*60}")
        print(f"🔥 FETCHING ALL {len(self.LEAGUES_CONFIG)} LEAGUES (Season {season})")
        print(f"{'='*60}\n")
        
        total_matches = 0
        
        for idx, league_code in enumerate(self.LEAGUES_CONFIG.keys(), 1):
            print(f"[{idx}/{len(self.LEAGUES_CONFIG)}] ", end="")
            matches = self.fetch_league_matches(league_code, season)
            total_matches += matches
            time.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"✅ TOTAL: {total_matches} MATCHES FROM {len(self.LEAGUES_CONFIG)} LEAGUES!")
        print(f"{'='*60}\n")
        
        return total_matches
    
    def get_match_count(self) -> int:
        """Get total number of matches in database"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM matches')
            count = c.fetchone()[0]
            conn.close()
            return count
        except:
            return 0
    
    def get_matches_for_training(self) -> List[Dict]:
        """Get all matches for ML training"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            
            c.execute('''
                SELECT id, league_code, home_team, away_team, 
                       home_goals, away_goals, btts, total_goals, date
                FROM matches
                ORDER BY date DESC
            ''')
            
            columns = ['id', 'league_code', 'home_team', 'away_team', 
                      'home_goals', 'away_goals', 'btts', 'total_goals', 'date']
            rows = c.fetchall()
            conn.close()
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            print(f"❌ Error getting matches: {e}")
            return []
    
    # =========================================================
    # STATS METHODS
    # =========================================================
    
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


# Quick test
if __name__ == '__main__':
    print("=" * 60)
    print("DATA ENGINE TEST")
    print("=" * 60)
    
    engine = DataEngine(api_key="test_key")
    print(f"\n✅ Initialized with {len(engine.LEAGUES_CONFIG)} leagues")
    print(f"📊 Database type: {'PostgreSQL (Supabase)' if engine.use_postgres else 'SQLite'}")
    print(f"📊 Current matches in DB: {engine.get_match_count()}")
#   S u p a b a s e   S u p p o r t  
 