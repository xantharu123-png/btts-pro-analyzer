"""
Data Engine with COMPLETE 28 LEAGUES Configuration
Updated: January 2026 - FINAL CORRECTED VERSION
All bugs fixed: realistic defaults, proper methods, clean database
"""

import requests
import sqlite3
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional

class DataEngine:
    """Enhanced data engine with 28 leagues support and all required methods"""
    
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
        
        print(f"🔥 Data Engine initialized with {len(self.LEAGUES_CONFIG)} leagues!")
    
    def init_database(self):
        """Initialize SQLite database with automatic schema fix"""
        # 🔥 STEP 1: Check if old database has wrong schema
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Check if matches table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
            table_exists = c.fetchone()
            
            if table_exists:
                # Check current schema
                c.execute("PRAGMA table_info(matches)")
                columns = [col[1] for col in c.fetchall()]
                
                # If home_team column doesn't exist, we have old schema - DROP IT!
                if columns and 'home_team' not in columns:
                    print("⚠️ OLD DATABASE SCHEMA DETECTED!")
                    print(f"   Found columns: {columns}")
                    print("   Expected: home_team, away_team")
                    print("🔥 DROPPING OLD TABLE AND RECREATING...")
                    c.execute("DROP TABLE IF EXISTS matches")
                    conn.commit()
                    print("✅ Old table dropped successfully")
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Schema check error (will create new): {e}")
        
        # 🔥 STEP 2: Create table with correct schema
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
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
        
        # Create indexes for faster queries
        c.execute('CREATE INDEX IF NOT EXISTS idx_league ON matches(league_code)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team)')
        
        conn.commit()
        conn.close()
        print("✅ Database ready with correct schema")
    
    def get_team_stats(self, team_id, league_code, venue='home'):
        """
        Get team statistics with REALISTIC defaults (65% BTTS, 1.5-1.6 goals)
        Returns defaults if no data or error
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # First check if table has correct schema
            c.execute("PRAGMA table_info(matches)")
            columns = [col[1] for col in c.fetchall()]
            
            if 'home_team' not in columns:
                conn.close()
                print(f"⚠️ Database schema mismatch - using defaults")
                return self._get_default_stats(team_id, league_code, venue)
            
            if venue == 'home':
                c.execute('''
                    SELECT home_team,
                           COUNT(*) as matches,
                           SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                           SUM(home_goals) as scored,
                           SUM(away_goals) as conceded,
                           SUM(btts) as btts_count,
                           SUM(CASE WHEN away_goals = 0 THEN 1 ELSE 0 END) as clean_sheets
                    FROM matches
                    WHERE league_code = ? AND home_team LIKE ?
                    GROUP BY home_team
                ''', (league_code, f'%{team_id}%'))
            else:
                c.execute('''
                    SELECT away_team,
                           COUNT(*) as matches,
                           SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN away_goals = home_goals THEN 1 ELSE 0 END) as draws,
                           SUM(away_goals) as scored,
                           SUM(home_goals) as conceded,
                           SUM(btts) as btts_count,
                           SUM(CASE WHEN home_goals = 0 THEN 1 ELSE 0 END) as clean_sheets
                    FROM matches
                    WHERE league_code = ? AND away_team LIKE ?
                    GROUP BY away_team
                ''', (league_code, f'%{team_id}%'))
            
            row = c.fetchone()
            conn.close()
            
            if row and row[1] >= 5:  # At least 5 matches
                matches = row[1]
                return {
                    'team_id': team_id,
                    'team_name': row[0],
                    'matches_played': matches,
                    'wins': row[2],
                    'draws': row[3],
                    'avg_goals_scored': round(row[4] / matches, 2),
                    'avg_goals_conceded': round(row[5] / matches, 2),
                    'btts_rate': round((row[6] / matches) * 100, 1),
                    'btts_count': row[6],
                    'clean_sheets': row[7]
                }
            
            # Not enough data - use defaults
            return self._get_default_stats(team_id, league_code, venue)
            
        except Exception as e:
            print(f"⚠️ Stats error for team {team_id}: {e}")
            return self._get_default_stats(team_id, league_code, venue)
    
    def _get_default_stats(self, team_id, league_code, venue='home'):
        """
        REALISTIC league-specific defaults (updated from 50% to 65% BTTS)
        """
        league_defaults = {
            # High-scoring leagues (BTTS ~65-75%)
            'BL1': {'scored': 1.7, 'conceded': 1.5, 'btts': 68},
            'PL': {'scored': 1.6, 'conceded': 1.4, 'btts': 62},
            'DED': {'scored': 1.8, 'conceded': 1.6, 'btts': 70},
            'ALL': {'scored': 1.9, 'conceded': 1.7, 'btts': 72},
            'SPL': {'scored': 2.0, 'conceded': 1.8, 'btts': 75},
            'ALE': {'scored': 1.8, 'conceded': 1.7, 'btts': 68},
            'ED1': {'scored': 1.9, 'conceded': 1.7, 'btts': 71},
            
            # Medium-scoring leagues (BTTS ~55-65%)
            'PD': {'scored': 1.4, 'conceded': 1.2, 'btts': 58},
            'SA': {'scored': 1.5, 'conceded': 1.3, 'btts': 60},
            'FL1': {'scored': 1.5, 'conceded': 1.3, 'btts': 58},
            'PPL': {'scored': 1.5, 'conceded': 1.4, 'btts': 62},
            'TSL': {'scored': 1.6, 'conceded': 1.5, 'btts': 65},
            'SC1': {'scored': 1.6, 'conceded': 1.4, 'btts': 63},
            'BE1': {'scored': 1.6, 'conceded': 1.5, 'btts': 64},
            
            # Lower-scoring leagues (BTTS ~50-55%)
            'ELC': {'scored': 1.4, 'conceded': 1.3, 'btts': 55},
            'BL2': {'scored': 1.5, 'conceded': 1.4, 'btts': 58},
            
            # Default (realistic average)
            'DEFAULT': {'scored': 1.6, 'conceded': 1.5, 'btts': 65},
        }
        
        defaults = league_defaults.get(league_code, league_defaults['DEFAULT'])
        
        # Adjust for venue (home teams score more, concede less)
        if venue == 'home':
            return {
                'team_id': team_id,
                'team_name': f'Team {team_id}',
                'matches_played': 0,
                'wins': 0,
                'draws': 0,
                'avg_goals_scored': defaults['scored'] + 0.1,
                'avg_goals_conceded': defaults['conceded'] - 0.1,
                'btts_rate': defaults['btts'],
                'btts_count': 0,
                'clean_sheets': 0
            }
        else:
            return {
                'team_id': team_id,
                'team_name': f'Team {team_id}',
                'matches_played': 0,
                'wins': 0,
                'draws': 0,
                'avg_goals_scored': defaults['scored'] - 0.1,
                'avg_goals_conceded': defaults['conceded'] + 0.1,
                'btts_rate': defaults['btts'],
                'btts_count': 0,
                'clean_sheets': 0
            }
    
    def get_recent_form(self, team_id, league_code, venue='home', n_matches=5):
        """Get recent form for a team"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if venue == 'home':
                c.execute('''
                    SELECT date, home_goals, away_goals, btts
                    FROM matches
                    WHERE league_code = ? AND home_team LIKE ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (league_code, f'%{team_id}%', n_matches))
            else:
                c.execute('''
                    SELECT date, away_goals, home_goals, btts
                    FROM matches
                    WHERE league_code = ? AND away_team LIKE ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (league_code, f'%{team_id}%', n_matches))
            
            rows = c.fetchall()
            conn.close()
            
            if len(rows) >= 3:
                btts_count = sum(1 for r in rows if r[3] == 1)
                goals_scored = sum(r[1] for r in rows)
                goals_conceded = sum(r[2] for r in rows)
                
                return {
                    'matches': len(rows),
                    'btts_count': btts_count,
                    'btts_rate': round((btts_count / len(rows)) * 100, 1),
                    'avg_goals_scored': round(goals_scored / len(rows), 2),
                    'avg_goals_conceded': round(goals_conceded / len(rows), 2)
                }
            
            # Not enough data - return league defaults
            return {
                'matches': 0,
                'btts_count': 0,
                'btts_rate': 65,  # Realistic default (was 50)
                'avg_goals_scored': 1.6,  # Realistic default (was 1.2)
                'avg_goals_conceded': 1.5  # Realistic default (was 1.3)
            }
            
        except Exception as e:
            print(f"⚠️ Form error: {e}")
            return {
                'matches': 0,
                'btts_count': 0,
                'btts_rate': 65,
                'avg_goals_scored': 1.6,
                'avg_goals_conceded': 1.5
            }
    
    def calculate_head_to_head(self, home_team_id, away_team_id):
        """Calculate H2H statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT COUNT(*), SUM(btts), AVG(home_goals + away_goals)
                FROM matches
                WHERE (home_team LIKE ? AND away_team LIKE ?)
                   OR (home_team LIKE ? AND away_team LIKE ?)
            ''', (f'%{home_team_id}%', f'%{away_team_id}%',
                  f'%{away_team_id}%', f'%{home_team_id}%'))
            
            row = c.fetchone()
            conn.close()
            
            if row and row[0] >= 3:
                return {
                    'matches': row[0],
                    'btts_count': row[1] or 0,
                    'btts_rate': round(((row[1] or 0) / row[0]) * 100, 1),
                    'avg_total_goals': round(row[2] or 0, 2)
                }
            
            return {'matches': 0, 'btts_count': 0, 'btts_rate': 65, 'avg_total_goals': 3.0}
            
        except Exception as e:
            print(f"⚠️ H2H error: {e}")
            return {'matches': 0, 'btts_count': 0, 'btts_rate': 65, 'avg_total_goals': 3.0}
    
    def get_rest_days(self, team_id, league_code):
        """Get days since last match"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT MAX(date)
                FROM matches
                WHERE league_code = ?
                  AND (home_team LIKE ? OR away_team LIKE ?)
            ''', (league_code, f'%{team_id}%', f'%{team_id}%'))
            
            last_match = c.fetchone()[0]
            conn.close()
            
            if last_match:
                last_date = datetime.strptime(last_match, '%Y-%m-%d')
                days = (datetime.now() - last_date).days
                return max(0, min(days, 30))
            
            return 7  # Default
            
        except Exception as e:
            return 7
    
    def get_momentum(self, team_id, league_code, venue='home'):
        """Calculate momentum from last 3 matches"""
        try:
            form = self.get_recent_form(team_id, league_code, venue, 3)
            if form['matches'] >= 3:
                return form['btts_rate']
            return 65
        except:
            return 65
    
    def get_league_stats(self, league_code):
        """Get overall league statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT COUNT(*),
                       AVG(CAST(btts AS REAL)),
                       AVG(total_goals)
                FROM matches
                WHERE league_code = ?
            ''', (league_code,))
            
            row = c.fetchone()
            conn.close()
            
            if row:
                return {
                    'total_matches': row[0],
                    'btts_rate': row[1] * 100 if row[1] else 65,
                    'avg_goals': row[2] if row[2] else 3.0
                }
            return None
            
        except Exception as e:
            print(f"❌ Stats error: {e}")
            return None


# Quick test
if __name__ == '__main__':
    print("✅ Data Engine module loaded successfully!")
    print(f"📊 Configured for {len(DataEngine.LEAGUES_CONFIG)} leagues")
