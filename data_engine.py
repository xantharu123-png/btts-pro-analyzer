"""
DATA ENGINE - KORRIGIERTE VERSION
==================================
Season: 2025 (für 2025/26 Saison - wir sind in Januar 2026!)
Fixes: fetch_league_matches speichert jetzt korrekt in DB
"""

import sqlite3
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path


class DataEngine:
    """Data Engine for BTTS Pro Analyzer"""
    
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
        """Initialize Data Engine"""
        self.api_key = api_key
        self.db_path = db_path
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-apisports-key': api_key
        }
        self.last_request = 0
        self.min_delay = 0.5
        
        # Initialize database
        self._init_database()
        print(f"✅ Data Engine initialized with {len(self.LEAGUES_CONFIG)} leagues!")
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Matches table
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
        
        # Index for faster queries
        c.execute('CREATE INDEX IF NOT EXISTS idx_league ON matches(league_code)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_date ON matches(date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_teams ON matches(home_team_id, away_team_id)')
        
        conn.commit()
        conn.close()
    
    def _rate_limit(self):
        """Respect API rate limits"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    # =========================================================
    # FETCH METHODS - KORRIGIERT MIT SEASON 2025
    # =========================================================
    
    def fetch_league_matches(self, league_code: str, season: int = 2025, 
                            force_refresh: bool = False) -> int:
        """
        Fetch and store ALL finished matches for a league
        
        WICHTIG: season=2025 für die aktuelle Saison 2025/26!
        
        Args:
            league_code: Liga-Code (z.B. 'BL1')
            season: Season Jahr (2025 = Saison 2025/26)
            force_refresh: Erzwinge Neuladen
        
        Returns:
            Anzahl der gespeicherten Spiele
        """
        league_id = self.LEAGUES_CONFIG.get(league_code)
        if not league_id:
            print(f"❌ Unknown league: {league_code}")
            return 0
        
        print(f"📡 Fetching {league_code} (season {season})...")
        
        try:
            self._rate_limit()
            
            # Fetch ALL finished matches for this season
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': season,
                    'status': 'FT'  # Full Time - gets ALL finished matches
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
            
            # Save to database
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
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
                    
                    c.execute('''
                        INSERT OR REPLACE INTO matches 
                        (id, league_code, league_id, date, home_team, away_team,
                         home_team_id, away_team_id, home_goals, away_goals, 
                         btts, total_goals, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        fixture_id,
                        league_code,
                        league_id,
                        fixture.get('date'),
                        teams.get('home', {}).get('name'),
                        teams.get('away', {}).get('name'),
                        teams.get('home', {}).get('id'),
                        teams.get('away', {}).get('id'),
                        home_goals,
                        away_goals,
                        btts,
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
        """
        Fetch ALL 28 leagues
        
        Args:
            season: 2025 für aktuelle Saison!
        
        Returns:
            Total number of matches fetched
        """
        print(f"\n{'='*60}")
        print(f"🔥 FETCHING ALL {len(self.LEAGUES_CONFIG)} LEAGUES (Season {season})")
        print(f"{'='*60}\n")
        
        total_matches = 0
        
        for idx, league_code in enumerate(self.LEAGUES_CONFIG.keys(), 1):
            print(f"[{idx}/{len(self.LEAGUES_CONFIG)}] ", end="")
            matches = self.fetch_league_matches(league_code, season)
            total_matches += matches
            time.sleep(1)  # Rate limit between leagues
        
        print(f"\n{'='*60}")
        print(f"✅ TOTAL: {total_matches} MATCHES FROM {len(self.LEAGUES_CONFIG)} LEAGUES!")
        print(f"{'='*60}\n")
        
        return total_matches
    
    def get_match_count(self) -> int:
        """Get total number of matches in database"""
        try:
            conn = sqlite3.connect(self.db_path)
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
            conn = sqlite3.connect(self.db_path)
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
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if venue == 'home':
                c.execute('''
                    SELECT 
                        COUNT(*) as matches,
                        AVG(home_goals) as avg_scored,
                        AVG(away_goals) as avg_conceded,
                        SUM(btts) * 100.0 / COUNT(*) as btts_rate
                    FROM matches
                    WHERE home_team_id = ? AND league_code = ?
                ''', (team_id, league_code))
            elif venue == 'away':
                c.execute('''
                    SELECT 
                        COUNT(*) as matches,
                        AVG(away_goals) as avg_scored,
                        AVG(home_goals) as avg_conceded,
                        SUM(btts) * 100.0 / COUNT(*) as btts_rate
                    FROM matches
                    WHERE away_team_id = ? AND league_code = ?
                ''', (team_id, league_code))
            else:
                c.execute('''
                    SELECT 
                        COUNT(*) as matches,
                        AVG(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as avg_scored,
                        AVG(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as avg_conceded,
                        SUM(btts) * 100.0 / COUNT(*) as btts_rate
                    FROM matches
                    WHERE (home_team_id = ? OR away_team_id = ?) AND league_code = ?
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
            
            # Default values
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
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if venue == 'home':
                c.execute('''
                    SELECT home_goals, away_goals, btts
                    FROM matches
                    WHERE home_team_id = ? AND league_code = ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (team_id, league_code, last_n))
            elif venue == 'away':
                c.execute('''
                    SELECT away_goals, home_goals, btts
                    FROM matches
                    WHERE away_team_id = ? AND league_code = ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (team_id, league_code, last_n))
            else:
                c.execute('''
                    SELECT 
                        CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END,
                        CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END,
                        btts
                    FROM matches
                    WHERE (home_team_id = ? OR away_team_id = ?) AND league_code = ?
                    ORDER BY date DESC
                    LIMIT ?
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
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT home_goals, away_goals, btts, home_team_id
                FROM matches
                WHERE (home_team_id = ? AND away_team_id = ?)
                   OR (home_team_id = ? AND away_team_id = ?)
                ORDER BY date DESC
                LIMIT ?
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
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT 
                    COUNT(*) as total_matches,
                    AVG(home_goals) as avg_home_scored,
                    AVG(away_goals) as avg_away_scored,
                    AVG(total_goals) as avg_total,
                    SUM(btts) * 100.0 / COUNT(*) as btts_rate
                FROM matches
                WHERE league_code = ?
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
    
    # Test ohne echten API Key
    engine = DataEngine(api_key="test_key")
    print(f"\n✅ Initialized with {len(engine.LEAGUES_CONFIG)} leagues")
    print(f"📊 Current matches in DB: {engine.get_match_count()}")
    print(f"\n⚠️ Run fetch_all_leagues(season=2025) to populate database!")
