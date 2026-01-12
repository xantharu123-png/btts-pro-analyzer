"""
Advanced Data Engine for BTTS Analysis
Handles data fetching, caching, and calculation of real BTTS statistics
"""

import sqlite3
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import time
from pathlib import Path


class DataEngine:
    """
    Enhanced data engine with:
    - SQLite caching
    - Real BTTS calculation from match results
    - Home/Away differentiation
    - Form analysis
    - Head-to-head history
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db"):
        self.api_key = api_key
        self.base_url = "https://api.football-data.org/v4"
        self.db_path = db_path
        self.init_database()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 6  # 10 requests per minute = 6 seconds between requests
        
        # League mappings
        self.leagues = {
            'Bundesliga': 'BL1',
            'Premier League': 'PL',
            'La Liga': 'PD',
            'Serie A': 'SA',
            'Ligue 1': 'FL1',
            'Eredivisie': 'DED',
            'Championship': 'ELC',
            'Primeira Liga': 'PPL'
        }
    
    def init_database(self):
        """Initialize SQLite database with all necessary tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Teams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                short_name TEXT,
                league_code TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        # Matches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id INTEGER PRIMARY KEY,
                home_team_id INTEGER,
                away_team_id INTEGER,
                league_code TEXT,
                match_date TIMESTAMP,
                home_score INTEGER,
                away_score INTEGER,
                status TEXT,
                btts INTEGER,
                total_goals INTEGER,
                last_updated TIMESTAMP,
                FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
                FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
            )
        ''')
        
        # Team statistics cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_stats (
                team_id INTEGER,
                league_code TEXT,
                season TEXT,
                venue TEXT, -- 'home' or 'away'
                matches_played INTEGER,
                btts_count INTEGER,
                btts_rate REAL,
                goals_scored INTEGER,
                goals_conceded INTEGER,
                avg_goals_scored REAL,
                avg_goals_conceded REAL,
                wins INTEGER,
                draws INTEGER,
                losses INTEGER,
                last_updated TIMESTAMP,
                PRIMARY KEY (team_id, league_code, season, venue),
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        ''')
        
        # Head to head cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS head_to_head (
                team1_id INTEGER,
                team2_id INTEGER,
                matches_played INTEGER,
                btts_count INTEGER,
                btts_rate REAL,
                avg_total_goals REAL,
                last_updated TIMESTAMP,
                PRIMARY KEY (team1_id, team2_id)
            )
        ''')
        
        # Predictions tracking (for backtesting)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                prediction_date TIMESTAMP,
                btts_probability REAL,
                confidence_level TEXT,
                ml_prediction REAL,
                actual_btts INTEGER,
                was_correct INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Database initialized successfully")
    
    def _rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            print(f"⏳ Rate limiting... waiting {sleep_time:.1f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _api_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with rate limiting and error handling"""
        if not self.api_key:
            return None
        
        self._rate_limit()
        
        headers = {'X-Auth-Token': self.api_key}
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("⚠️ Rate limit reached. Waiting 60 seconds...")
                time.sleep(60)
                return self._api_request(endpoint, params)
            else:
                print(f"⚠️ API error {response.status_code}: {response.text[:100]}")
                return None
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None
    
    def fetch_and_store_matches(self, league_code: str, season: str = "2024") -> int:
        """
        Fetch all matches for a league and store in database
        Returns: number of matches stored
        """
        print(f"📥 Fetching matches for {league_code} (Season {season})...")
        
        # Get all matches for the season
        data = self._api_request(f"competitions/{league_code}/matches", {'season': season})
        
        if not data or 'matches' not in data:
            print(f"⚠️ No data for {league_code}")
            return 0
        
        matches = data['matches']
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stored_count = 0
        
        for match in matches:
            match_id = match['id']
            home_team = match['homeTeam']
            away_team = match['awayTeam']
            score = match.get('score', {}).get('fullTime', {})
            
            # Store teams
            for team in [home_team, away_team]:
                cursor.execute('''
                    INSERT OR REPLACE INTO teams (team_id, name, short_name, league_code, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (team['id'], team['name'], team.get('shortName'), league_code, datetime.now()))
            
            # Only store finished matches
            if match['status'] == 'FINISHED' and score.get('home') is not None:
                home_score = score['home']
                away_score = score['away']
                btts = 1 if (home_score > 0 and away_score > 0) else 0
                total_goals = home_score + away_score
                
                cursor.execute('''
                    INSERT OR REPLACE INTO matches 
                    (match_id, home_team_id, away_team_id, league_code, match_date, 
                     home_score, away_score, status, btts, total_goals, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id, home_team['id'], away_team['id'], league_code,
                    match['utcDate'], home_score, away_score, match['status'],
                    btts, total_goals, datetime.now()
                ))
                
                stored_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Stored {stored_count} finished matches for {league_code}")
        return stored_count
    
    def calculate_team_stats(self, team_id: int, league_code: str, season: str = "2024"):
        """Calculate and cache team statistics (home/away separate)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for venue in ['home', 'away']:
            if venue == 'home':
                query = '''
                    SELECT COUNT(*) as matches, 
                           SUM(btts) as btts_count,
                           SUM(home_score) as goals_scored,
                           SUM(away_score) as goals_conceded,
                           SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) as draws,
                           SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) as losses
                    FROM matches
                    WHERE home_team_id = ? AND league_code = ? AND status = 'FINISHED'
                '''
            else:
                query = '''
                    SELECT COUNT(*) as matches,
                           SUM(btts) as btts_count,
                           SUM(away_score) as goals_scored,
                           SUM(home_score) as goals_conceded,
                           SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) as draws,
                           SUM(CASE WHEN away_score < home_score THEN 1 ELSE 0 END) as losses
                    FROM matches
                    WHERE away_team_id = ? AND league_code = ? AND status = 'FINISHED'
                '''
            
            cursor.execute(query, (team_id, league_code))
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                matches, btts_count, goals_scored, goals_conceded, wins, draws, losses = result
                
                btts_rate = (btts_count / matches * 100) if matches > 0 else 0
                avg_goals_scored = goals_scored / matches if matches > 0 else 0
                avg_goals_conceded = goals_conceded / matches if matches > 0 else 0
                
                cursor.execute('''
                    INSERT OR REPLACE INTO team_stats
                    (team_id, league_code, season, venue, matches_played, btts_count, btts_rate,
                     goals_scored, goals_conceded, avg_goals_scored, avg_goals_conceded,
                     wins, draws, losses, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team_id, league_code, season, venue, matches, btts_count, btts_rate,
                    goals_scored, goals_conceded, avg_goals_scored, avg_goals_conceded,
                    wins, draws, losses, datetime.now()
                ))
        
        conn.commit()
        conn.close()
    
    def get_team_stats(self, team_id: int, league_code: str, venue: str) -> Optional[Dict]:
        """Get cached team statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM team_stats
            WHERE team_id = ? AND league_code = ? AND venue = ?
            ORDER BY last_updated DESC LIMIT 1
        ''', (team_id, league_code, venue))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'team_id': result[0],
                'matches_played': result[4],
                'btts_count': result[5],
                'btts_rate': result[6],
                'goals_scored': result[7],
                'goals_conceded': result[8],
                'avg_goals_scored': result[9],
                'avg_goals_conceded': result[10],
                'wins': result[11],
                'draws': result[12],
                'losses': result[13]
            }
        return None
    
    def calculate_head_to_head(self, team1_id: int, team2_id: int) -> Dict:
        """Calculate head-to-head statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all matches between these teams
        cursor.execute('''
            SELECT COUNT(*) as matches,
                   SUM(btts) as btts_count,
                   AVG(total_goals) as avg_goals
            FROM matches
            WHERE ((home_team_id = ? AND away_team_id = ?)
                   OR (home_team_id = ? AND away_team_id = ?))
                  AND status = 'FINISHED'
        ''', (team1_id, team2_id, team2_id, team1_id))
        
        result = cursor.fetchone()
        
        if result and result[0] > 0:
            matches, btts_count, avg_goals = result
            btts_rate = (btts_count / matches * 100) if matches > 0 else 0
            
            # Cache the result
            cursor.execute('''
                INSERT OR REPLACE INTO head_to_head
                (team1_id, team2_id, matches_played, btts_count, btts_rate, avg_total_goals, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (team1_id, team2_id, matches, btts_count, btts_rate, avg_goals or 0, datetime.now()))
            
            conn.commit()
            conn.close()
            
            return {
                'matches_played': matches,
                'btts_count': btts_count,
                'btts_rate': btts_rate,
                'avg_total_goals': avg_goals or 0
            }
        
        conn.close()
        return {'matches_played': 0, 'btts_count': 0, 'btts_rate': 0, 'avg_total_goals': 0}
    
    def get_recent_form(self, team_id: int, league_code: str, venue: str = 'all', last_n: int = 5) -> Dict:
        """Get recent form for a team"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if venue == 'home':
            query = '''
                SELECT home_score, away_score, btts, total_goals, match_date
                FROM matches
                WHERE home_team_id = ? AND league_code = ? AND status = 'FINISHED'
                ORDER BY match_date DESC LIMIT ?
            '''
        elif venue == 'away':
            query = '''
                SELECT away_score as home_score, home_score as away_score, btts, total_goals, match_date
                FROM matches
                WHERE away_team_id = ? AND league_code = ? AND status = 'FINISHED'
                ORDER BY match_date DESC LIMIT ?
            '''
        else:  # all
            query = '''
                SELECT 
                    CASE WHEN home_team_id = ? THEN home_score ELSE away_score END as team_score,
                    CASE WHEN home_team_id = ? THEN away_score ELSE home_score END as opponent_score,
                    btts, total_goals, match_date
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?) 
                      AND league_code = ? AND status = 'FINISHED'
                ORDER BY match_date DESC LIMIT ?
            '''
            cursor.execute(query, (team_id, team_id, team_id, team_id, league_code, last_n))
        
        if venue != 'all':
            cursor.execute(query, (team_id, league_code, last_n))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {
                'matches': 0,
                'btts_rate': 0,
                'avg_goals_scored': 0,
                'avg_goals_conceded': 0,
                'avg_total_goals': 0,
                'form_string': ''
            }
        
        btts_count = sum(1 for r in results if r[2] == 1)
        goals_scored = sum(r[0] for r in results)
        goals_conceded = sum(r[1] for r in results)
        total_goals = sum(r[3] for r in results)
        
        # Form string (W-D-L)
        form_string = []
        for r in results:
            if r[0] > r[1]:
                form_string.append('W')
            elif r[0] == r[1]:
                form_string.append('D')
            else:
                form_string.append('L')
        
        return {
            'matches': len(results),
            'btts_rate': (btts_count / len(results) * 100) if results else 0,
            'avg_goals_scored': goals_scored / len(results) if results else 0,
            'avg_goals_conceded': goals_conceded / len(results) if results else 0,
            'avg_total_goals': total_goals / len(results) if results else 0,
            'form_string': '-'.join(form_string)
        }
    
    def get_rest_days(self, team_id: int, league_code: str) -> Dict:
        """
        Calculate days of rest since last match
        FATIGUE FACTOR: Teams with less rest perform worse
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get last 2 matches to calculate rest days
        cursor.execute('''
            SELECT match_date
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
                  AND league_code = ?
                  AND status = 'FINISHED'
            ORDER BY match_date DESC
            LIMIT 2
        ''', (team_id, team_id, league_code))
        
        results = cursor.fetchall()
        conn.close()
        
        if len(results) < 2:
            return {
                'days_rest': 7,  # Default if no data
                'fatigue_factor': 1.0,
                'freshness_bonus': 0
            }
        
        # Calculate days between matches
        from datetime import datetime
        last_match = datetime.fromisoformat(results[0][0].replace('Z', '+00:00'))
        prev_match = datetime.fromisoformat(results[1][0].replace('Z', '+00:00'))
        
        days_rest = (last_match - prev_match).days
        
        # Fatigue factor (less rest = more fatigue)
        if days_rest < 3:
            fatigue_factor = 0.88  # Very tired (e.g. midweek + weekend)
            freshness_bonus = -8
        elif days_rest < 4:
            fatigue_factor = 0.93  # Tired
            freshness_bonus = -4
        elif days_rest >= 7:
            fatigue_factor = 1.05  # Well rested
            freshness_bonus = +5
        elif days_rest >= 10:
            fatigue_factor = 1.08  # Very fresh
            freshness_bonus = +8
        else:
            fatigue_factor = 1.0   # Normal
            freshness_bonus = 0
        
        return {
            'days_rest': days_rest,
            'fatigue_factor': fatigue_factor,
            'freshness_bonus': freshness_bonus
        }
    
    def get_momentum(self, team_id: int, league_code: str, venue: str) -> Dict:
        """
        Analyze scoring/conceding momentum (trend over last 5 games)
        MOMENTUM MATTERS: Teams on upward trend perform better
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if venue == 'home':
            query = '''
                SELECT home_score, away_score, match_date
                FROM matches
                WHERE home_team_id = ? AND league_code = ? AND status = 'FINISHED'
                ORDER BY match_date DESC LIMIT 5
            '''
        else:
            query = '''
                SELECT away_score as home_score, home_score as away_score, match_date
                FROM matches
                WHERE away_team_id = ? AND league_code = ? AND status = 'FINISHED'
                ORDER BY match_date DESC LIMIT 5
            '''
        
        cursor.execute(query, (team_id, league_code))
        results = cursor.fetchall()
        conn.close()
        
        if len(results) < 3:
            return {
                'scoring_trend': 'stable',
                'conceding_trend': 'stable',
                'momentum_bonus': 0
            }
        
        # Analyze trends (recent 2 vs previous 3)
        recent_goals = sum(r[0] for r in results[:2]) / 2
        previous_goals = sum(r[0] for r in results[2:]) / 3
        
        recent_conceded = sum(r[1] for r in results[:2]) / 2
        previous_conceded = sum(r[1] for r in results[2:]) / 3
        
        # Determine trends
        scoring_trend = 'increasing' if recent_goals > previous_goals * 1.2 else \
                       'decreasing' if recent_goals < previous_goals * 0.8 else \
                       'stable'
        
        conceding_trend = 'increasing' if recent_conceded > previous_conceded * 1.2 else \
                         'decreasing' if recent_conceded < previous_conceded * 0.8 else \
                         'stable'
        
        # Calculate momentum bonus for BTTS
        momentum_bonus = 0
        
        # Positive momentum for scoring
        if scoring_trend == 'increasing':
            momentum_bonus += 5
        elif scoring_trend == 'decreasing':
            momentum_bonus -= 3
        
        # Conceding more = higher BTTS (bad defense)
        if conceding_trend == 'increasing':
            momentum_bonus += 8  # Bad defense = opponent likely scores
        elif conceding_trend == 'decreasing':
            momentum_bonus -= 5  # Good defense = opponent less likely
        
        return {
            'scoring_trend': scoring_trend,
            'conceding_trend': conceding_trend,
            'momentum_bonus': momentum_bonus,
            'recent_goals_avg': round(recent_goals, 2),
            'recent_conceded_avg': round(recent_conceded, 2)
        }
    
    def get_motivation_factor(self, team_id: int, league_code: str) -> Dict:
        """
        Determine team motivation based on table position
        MOTIVATION MATTERS: Teams fighting for something play differently
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get team's position in table
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN home_team_id = ? THEN 
                    CASE WHEN home_score > away_score THEN 3
                         WHEN home_score = away_score THEN 1
                         ELSE 0 END
                    WHEN away_team_id = ? THEN
                    CASE WHEN away_score > home_score THEN 3
                         WHEN away_score = home_score THEN 1
                         ELSE 0 END
                    END) as points,
                COUNT(*) as matches
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
                  AND league_code = ?
                  AND status = 'FINISHED'
        ''', (team_id, team_id, team_id, team_id, league_code))
        
        result = cursor.fetchone()
        
        if not result or result[1] < 5:
            conn.close()
            return {
                'position_estimate': 'mid_table',
                'motivation_level': 'normal',
                'btts_adjustment': 0
            }
        
        points = result[0] or 0
        matches = result[1]
        points_per_game = points / matches
        
        # Estimate position based on points per game
        # Championship: ~90-95 pts for promotion, ~50 pts for relegation
        # EPL/other big leagues: similar ratios
        
        if points_per_game >= 2.2:  # Top teams (>80 pts in 38 games)
            position = 'top'
            motivation = 'championship'
            btts_adj = +5  # Fighting for title = more offensive
        elif points_per_game >= 1.8:  # European spots
            position = 'european'
            motivation = 'high'
            btts_adj = +3  # Want to win = offensive
        elif points_per_game >= 1.3:  # Safe mid-table
            position = 'mid_table'
            motivation = 'normal'
            btts_adj = 0  # Nothing to play for = unpredictable
        elif points_per_game >= 1.0:  # Lower mid-table
            position = 'lower_mid'
            motivation = 'low'
            btts_adj = -2  # Slightly cautious
        else:  # Relegation battle
            position = 'relegation'
            motivation = 'desperate'
            btts_adj = -8  # Very defensive, fighting for survival
        
        conn.close()
        
        return {
            'position_estimate': position,
            'motivation_level': motivation,
            'btts_adjustment': btts_adj,
            'points_per_game': round(points_per_game, 2)
        }
    
    def refresh_league_data(self, league_code: str, season: str = "2024"):
        """Refresh all data for a league"""
        print(f"\n🔄 Refreshing data for {league_code}...")
        
        # Fetch and store matches
        match_count = self.fetch_and_store_matches(league_code, season)
        
        if match_count == 0:
            print(f"⚠️ No matches to process for {league_code}")
            return
        
        # Get all teams in this league
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT team_id FROM teams WHERE league_code = ?', (league_code,))
        teams = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f"📊 Calculating stats for {len(teams)} teams...")
        
        # Calculate stats for each team
        for team_id in teams:
            self.calculate_team_stats(team_id, league_code, season)
        
        print(f"✅ Data refresh complete for {league_code}")


if __name__ == "__main__":
    # Test the data engine
    print("=== Data Engine Test ===\n")
    
    engine = DataEngine(api_key='ef8c2eb9be6b43fe8353c99f51904c0f')
    
    # Refresh Bundesliga data
    engine.refresh_league_data('BL1', '2024')
    
    print("\n=== Test Complete ===")
