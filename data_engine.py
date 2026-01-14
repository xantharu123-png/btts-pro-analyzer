"""
Data Engine with COMPLETE 28 LEAGUES Configuration
Updated: January 2026
"""

import requests
import sqlite3
from datetime import datetime, timedelta
import time

class DataEngine:
    """Enhanced data engine with 28 leagues support"""
    
    # 🔥 COMPLETE 28 LEAGUES CONFIGURATION
    LEAGUES_CONFIG = {
        # TIER 1: TOP LEAGUES (12)
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
        
        # TIER 1: EUROPEAN CUPS (3)
        'CL': 2,      # 🏆 Champions League
        'EL': 3,      # 🏆 Europa League
        'ECL': 848,   # 🏆 Conference League
        
        # TIER 2: EU EXPANSION (4)
        'SC1': 179,   # 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Premiership
        'BE1': 144,   # 🇧🇪 Belgian Pro League
        'SL1': 207,   # 🇨🇭 Swiss Super League
        'AL1': 218,   # 🇦🇹 Austrian Bundesliga
        
        # TIER 3: GOAL FESTIVALS! 🎊 (9)
        'SPL': 265,   # 🇸🇬 Singapore Premier (4.0+ Goals!)
        'ESI': 330,   # 🇪🇪 Esiliiga (Estonia 2)
        'IS2': 165,   # 🇮🇸 1. Deild (Iceland 2)
        'ALE': 188,   # 🇦🇺 A-League
        'ED1': 89,    # 🇳🇱 Eerste Divisie (NL 2)
        'CHL': 209,   # 🇨🇭 Challenge League (CH 2)
        'ALL': 113,   # 🇸🇪 Allsvenskan
        'QSL': 292,   # 🇶🇦 Qatar Stars League
        'UAE': 301,   # 🇦🇪 UAE Pro League
    }
    
    def __init__(self, api_key, db_path='btts_data.db'):
        """Initialize with 28 leagues"""
        self.api_key = api_key
        self.base_url = 'https://v3.football.api-sports.io'
        self.headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': api_key
        }
        self.db_path = db_path
        self.init_database()
        
        # Start background loading for all 28 leagues
        print(f"🔥 Data Engine initialized with {len(self.LEAGUES_CONFIG)} leagues!")
        
    def init_database(self):
        """Initialize SQLite database"""
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
                home_goals INTEGER,
                away_goals INTEGER,
                btts INTEGER,
                total_goals INTEGER,
                fetched_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    
    def fetch_league_matches(self, league_code, season=2024, force_refresh=False):
        """Fetch matches for a specific league"""
        league_id = self.LEAGUES_CONFIG.get(league_code)
        if not league_id:
            print(f"❌ Unknown league: {league_code}")
            return []
        
        # Check cache first
        if not force_refresh:
            cached = self._get_cached_matches(league_code, season)
            if cached:
                print(f"✅ Using cached data for {league_code} ({len(cached)} matches)")
                return cached
        
        # Fetch from API
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': season,
                    'status': 'FT'  # Finished matches only
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('response', [])
                
                # Save to database
                self._save_matches(matches, league_code, league_id)
                
                print(f"✅ Fetched {len(matches)} matches for {league_code}")
                return matches
            else:
                print(f"❌ API Error for {league_code}: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching {league_code}: {e}")
            return []
    
    def fetch_all_leagues(self, season=2024):
        """Fetch ALL 28 leagues"""
        print(f"\n{'='*60}")
        print(f"🔥 FETCHING ALL 28 LEAGUES...")
        print(f"{'='*60}\n")
        
        total_matches = 0
        
        for idx, league_code in enumerate(self.LEAGUES_CONFIG.keys(), 1):
            print(f"[{idx}/{len(self.LEAGUES_CONFIG)}] Fetching {league_code}...")
            
            matches = self.fetch_league_matches(league_code, season)
            total_matches += len(matches)
            
            # Rate limiting
            time.sleep(0.5)
        
        print(f"\n{'='*60}")
        print(f"✅ FETCHED {total_matches} TOTAL MATCHES FROM 28 LEAGUES!")
        print(f"{'='*60}\n")
        
        return total_matches
    
    def _get_cached_matches(self, league_code, season):
        """Get matches from cache"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT * FROM matches 
                WHERE league_code = ? 
                AND date LIKE ?
                ORDER BY date DESC
            ''', (league_code, f"{season}%"))
            
            rows = c.fetchall()
            conn.close()
            
            return rows if rows else None
            
        except Exception as e:
            print(f"❌ Cache error: {e}")
            return None
    
    def _save_matches(self, matches, league_code, league_id):
        """Save matches to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            for match in matches:
                fixture = match.get('fixture', {})
                teams = match.get('teams', {})
                goals = match.get('goals', {})
                
                home_goals = goals.get('home', 0)
                away_goals = goals.get('away', 0)
                btts = 1 if (home_goals > 0 and away_goals > 0) else 0
                
                c.execute('''
                    INSERT OR REPLACE INTO matches 
                    (id, league_code, league_id, date, home_team, away_team, 
                     home_goals, away_goals, btts, total_goals, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    fixture.get('id'),
                    league_code,
                    league_id,
                    fixture.get('date'),
                    teams.get('home', {}).get('name'),
                    teams.get('away', {}).get('name'),
                    home_goals,
                    away_goals,
                    btts,
                    home_goals + away_goals,
                    datetime.now().isoformat()
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Save error: {e}")
    
    def _rate_limit(self):
        """Basic rate limiting"""
        time.sleep(0.1)
    
    def get_league_stats(self, league_code):
        """Get statistics for a league"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT 
                    COUNT(*) as total_matches,
                    AVG(btts) as btts_rate,
                    AVG(total_goals) as avg_goals
                FROM matches
                WHERE league_code = ?
            ''', (league_code,))
            
            row = c.fetchone()
            conn.close()
            
            if row:
                return {
                    'total_matches': row[0],
                    'btts_rate': row[1] * 100 if row[1] else 0,
                    'avg_goals': row[2] if row[2] else 0
                }
            return None
            
        except Exception as e:
            print(f"❌ Stats error: {e}")
            return None


# Quick test
if __name__ == '__main__':
    engine = DataEngine('YOUR_API_KEY')
    print(f"\n✅ Data Engine ready with {len(engine.LEAGUES_CONFIG)} leagues!")
    
    for code, id in list(engine.LEAGUES_CONFIG.items())[:5]:
        print(f"  {code}: League ID {id}")
