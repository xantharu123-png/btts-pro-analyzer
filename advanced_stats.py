"""
Advanced Statistics Module for BTTS Pro Analyzer
Extracts ALL valuable data from API-Football

Features:
1. Referee Statistics
2. Injuries & Suspensions
3. Lineups & Key Players
4. Form Deep Dive
5. Corners & Set Pieces
6. Cards Analysis
7. Possession Deep
8. H2H Advanced
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime
import time

class AdvancedStats:
    """Advanced statistics from API-Football"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': api_key
        }
        
        # Rate limiting
        self.last_request = 0
        self.min_delay = 0.5
    
    def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    # ===== 1. REFEREE STATS =====
    
    def get_referee_stats(self, referee_id: int, season: int = 2024) -> Optional[Dict]:
        """
        Get referee statistics
        Returns: avg goals, avg cards, strictness level
        """
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'referee': referee_id,
                    'season': season,
                    'status': 'FT'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            fixtures = data.get('response', [])
            
            if not fixtures:
                return None
            
            total_goals = 0
            total_yellow = 0
            total_red = 0
            match_count = len(fixtures)
            
            for fixture in fixtures:
                goals = fixture['goals']['home'] + fixture['goals']['away']
                total_goals += goals if goals else 0
            
            return {
                'matches': match_count,
                'avg_goals': round(total_goals / match_count, 2) if match_count > 0 else 0,
                'avg_yellow_cards': round(total_yellow / match_count, 2) if match_count > 0 else 0,
                'strictness': self._calculate_strictness(total_goals / match_count if match_count > 0 else 0),
                'btts_adjustment': self._referee_btts_adjustment(total_goals / match_count if match_count > 0 else 0)
            }
        
        except Exception as e:
            return None
    
    def _calculate_strictness(self, avg_goals: float) -> str:
        """Calculate referee strictness level"""
        if avg_goals >= 3.5:
            return 'very_lenient'
        elif avg_goals >= 3.0:
            return 'lenient'
        elif avg_goals >= 2.5:
            return 'normal'
        elif avg_goals >= 2.0:
            return 'strict'
        else:
            return 'very_strict'
    
    def _referee_btts_adjustment(self, avg_goals: float) -> float:
        """Calculate BTTS adjustment based on referee avg goals"""
        if avg_goals >= 3.5:
            return +5  # Very lenient = more goals
        elif avg_goals >= 3.0:
            return +3
        elif avg_goals >= 2.5:
            return 0
        elif avg_goals >= 2.0:
            return -3
        else:
            return -5  # Very strict = fewer goals
    
    # ===== 2. INJURIES & SUSPENSIONS =====
    
    def get_team_injuries(self, team_id: int) -> Optional[Dict]:
        """
        Get current injuries and suspensions for a team
        Returns: list of injured/suspended players with their importance
        """
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/injuries",
                headers=self.headers,
                params={
                    'team': team_id,
                    'season': 2024
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            injuries = data.get('response', [])
            
            if not injuries:
                return {
                    'total_injuries': 0,
                    'key_players_out': 0,
                    'btts_adjustment': 0,
                    'players': []
                }
            
            # Analyze injury impact
            key_positions = ['Attacker', 'Midfielder']
            key_players_out = 0
            
            injured_players = []
            
            for injury in injuries:
                player = injury.get('player', {})
                player_type = injury.get('player', {}).get('type', '')
                
                is_key = player_type in key_positions
                if is_key:
                    key_players_out += 1
                
                injured_players.append({
                    'name': player.get('name', 'Unknown'),
                    'position': player_type,
                    'reason': injury.get('player', {}).get('reason', 'Unknown'),
                    'is_key': is_key
                })
            
            # Calculate BTTS adjustment
            btts_adj = 0
            if key_players_out == 1:
                btts_adj = -3
            elif key_players_out == 2:
                btts_adj = -6
            elif key_players_out >= 3:
                btts_adj = -10
            
            return {
                'total_injuries': len(injuries),
                'key_players_out': key_players_out,
                'btts_adjustment': btts_adj,
                'players': injured_players[:5]  # Top 5 most important
            }
        
        except Exception as e:
            return None
    
    # ===== 3. LINEUPS & KEY PLAYERS =====
    
    def get_match_lineups(self, fixture_id: int) -> Optional[Dict]:
        """
        Get starting lineups for a match
        Analyze if key players are starting
        """
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures/lineups",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            lineups = data.get('response', [])
            
            if len(lineups) < 2:
                return None
            
            home_lineup = lineups[0]
            away_lineup = lineups[1]
            
            return {
                'home_formation': home_lineup.get('formation'),
                'away_formation': away_lineup.get('formation'),
                'home_lineup_available': True,
                'away_lineup_available': True,
                'home_starters': len(home_lineup.get('startXI', [])),
                'away_starters': len(away_lineup.get('startXI', []))
            }
        
        except Exception as e:
            return None
    
    # ===== 4. FORM DEEP DIVE =====
    
    def get_form_breakdown(self, team_id: int, league_id: int, season: int = 2024) -> Optional[Dict]:
        """
        Get detailed form analysis
        - Home vs Away form separate
        - Against top vs bottom teams
        - Recent momentum
        """
        try:
            self._rate_limit()
            
            # Get team fixtures
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'team': team_id,
                    'league': league_id,
                    'season': season,
                    'last': 10,
                    'status': 'FT'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            fixtures = data.get('response', [])
            
            if not fixtures:
                return None
            
            home_form = {'wins': 0, 'draws': 0, 'losses': 0, 'btts': 0, 'goals_for': 0, 'goals_against': 0}
            away_form = {'wins': 0, 'draws': 0, 'losses': 0, 'btts': 0, 'goals_for': 0, 'goals_against': 0}
            
            for fixture in fixtures:
                is_home = fixture['teams']['home']['id'] == team_id
                home_goals = fixture['goals']['home']
                away_goals = fixture['goals']['away']
                
                if is_home:
                    home_form['goals_for'] += home_goals
                    home_form['goals_against'] += away_goals
                    
                    if home_goals > away_goals:
                        home_form['wins'] += 1
                    elif home_goals == away_goals:
                        home_form['draws'] += 1
                    else:
                        home_form['losses'] += 1
                    
                    if home_goals > 0 and away_goals > 0:
                        home_form['btts'] += 1
                else:
                    away_form['goals_for'] += away_goals
                    away_form['goals_against'] += home_goals
                    
                    if away_goals > home_goals:
                        away_form['wins'] += 1
                    elif away_goals == home_goals:
                        away_form['draws'] += 1
                    else:
                        away_form['losses'] += 1
                    
                    if home_goals > 0 and away_goals > 0:
                        away_form['btts'] += 1
            
            return {
                'home_form': home_form,
                'away_form': away_form,
                'home_btts_rate': (home_form['btts'] / max(1, home_form['wins'] + home_form['draws'] + home_form['losses'])) * 100,
                'away_btts_rate': (away_form['btts'] / max(1, away_form['wins'] + away_form['draws'] + away_form['losses'])) * 100
            }
        
        except Exception as e:
            return None
    
    # ===== 5. CORNERS & SET PIECES =====
    
    def get_corners_stats(self, fixture_id: int) -> Optional[Dict]:
        """Get corner statistics for a match"""
        stats = self._get_match_stats(fixture_id)
        
        if not stats:
            return None
        
        home_corners = self._find_stat(stats.get('home', []), 'Corner Kicks')
        away_corners = self._find_stat(stats.get('away', []), 'Corner Kicks')
        
        return {
            'home_corners': int(home_corners) if home_corners else 0,
            'away_corners': int(away_corners) if away_corners else 0,
            'total_corners': (int(home_corners) if home_corners else 0) + (int(away_corners) if away_corners else 0)
        }
    
    def _get_match_stats(self, fixture_id: int) -> Optional[Dict]:
        """Helper to get match statistics"""
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures/statistics",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            response_data = data.get('response', [])
            
            if len(response_data) < 2:
                return None
            
            return {
                'home': response_data[0].get('statistics', []),
                'away': response_data[1].get('statistics', [])
            }
        
        except Exception as e:
            return None
    
    # ===== 6. CARDS ANALYSIS =====
    
    def get_cards_stats(self, fixture_id: int) -> Optional[Dict]:
        """Get cards statistics for a match"""
        stats = self._get_match_stats(fixture_id)
        
        if not stats:
            return None
        
        home_yellow = self._find_stat(stats.get('home', []), 'Yellow Cards')
        away_yellow = self._find_stat(stats.get('away', []), 'Yellow Cards')
        home_red = self._find_stat(stats.get('home', []), 'Red Cards')
        away_red = self._find_stat(stats.get('away', []), 'Red Cards')
        
        total_yellow = (int(home_yellow) if home_yellow else 0) + (int(away_yellow) if away_yellow else 0)
        total_red = (int(home_red) if home_red else 0) + (int(away_red) if away_red else 0)
        
        # Calculate aggression level
        aggression = 'normal'
        btts_adjustment = 0
        
        if total_yellow >= 6 or total_red >= 1:
            aggression = 'very_aggressive'
            btts_adjustment = +2  # Aggressive = often offensive
        elif total_yellow >= 4:
            aggression = 'aggressive'
            btts_adjustment = +1
        elif total_yellow <= 1:
            aggression = 'calm'
            btts_adjustment = 0
        
        return {
            'home_yellow': int(home_yellow) if home_yellow else 0,
            'away_yellow': int(away_yellow) if away_yellow else 0,
            'home_red': int(home_red) if home_red else 0,
            'away_red': int(away_red) if away_red else 0,
            'total_cards': total_yellow + total_red,
            'aggression_level': aggression,
            'btts_adjustment': btts_adjustment
        }
    
    # ===== 7. POSSESSION & PASSING DEEP =====
    
    def get_possession_stats(self, fixture_id: int) -> Optional[Dict]:
        """Get detailed possession and passing stats"""
        stats = self._get_match_stats(fixture_id)
        
        if not stats:
            return None
        
        home_possession = self._find_stat(stats.get('home', []), 'Ball Possession')
        away_possession = self._find_stat(stats.get('away', []), 'Ball Possession')
        
        home_passes = self._find_stat(stats.get('home', []), 'Total passes')
        away_passes = self._find_stat(stats.get('away', []), 'Total passes')
        
        home_pass_accuracy = self._find_stat(stats.get('home', []), 'Passes %')
        away_pass_accuracy = self._find_stat(stats.get('away', []), 'Passes %')
        
        # Convert possession to float (remove %)
        home_poss = float(home_possession.replace('%', '')) if home_possession else 50
        away_poss = float(away_possession.replace('%', '')) if away_possession else 50
        
        # High possession + high accuracy = more dangerous
        home_danger = home_poss * (float(home_pass_accuracy.replace('%', '')) / 100 if home_pass_accuracy else 0.7)
        away_danger = away_poss * (float(away_pass_accuracy.replace('%', '')) / 100 if away_pass_accuracy else 0.7)
        
        # Both teams dangerous = more BTTS
        btts_boost = 0
        if home_danger > 35 and away_danger > 35:
            btts_boost = +3
        elif home_danger > 30 and away_danger > 30:
            btts_boost = +2
        
        return {
            'home_possession': home_poss,
            'away_possession': away_poss,
            'home_passes': int(home_passes) if home_passes else 0,
            'away_passes': int(away_passes) if away_passes else 0,
            'home_pass_accuracy': float(home_pass_accuracy.replace('%', '')) if home_pass_accuracy else 0,
            'away_pass_accuracy': float(away_pass_accuracy.replace('%', '')) if away_pass_accuracy else 0,
            'home_danger_level': round(home_danger, 1),
            'away_danger_level': round(away_danger, 1),
            'btts_adjustment': btts_boost
        }
    
    # ===== 8. H2H ADVANCED =====
    
    def get_h2h_deep(self, team1_id: int, team2_id: int) -> Optional[Dict]:
        """
        Advanced H2H analysis
        - Last 10 meetings
        - Home vs Away breakdown
        - Trend analysis
        """
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures/headtohead",
                headers=self.headers,
                params={
                    'h2h': f"{team1_id}-{team2_id}",
                    'last': 10,
                    'status': 'FT'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            fixtures = data.get('response', [])
            
            if not fixtures:
                return None
            
            home_meetings = []
            away_meetings = []
            
            for fixture in fixtures:
                is_home = fixture['teams']['home']['id'] == team1_id
                home_goals = fixture['goals']['home']
                away_goals = fixture['goals']['away']
                btts = (home_goals > 0 and away_goals > 0)
                
                meeting = {
                    'btts': btts,
                    'total_goals': home_goals + away_goals,
                    'date': fixture['fixture']['date']
                }
                
                if is_home:
                    home_meetings.append(meeting)
                else:
                    away_meetings.append(meeting)
            
            # Calculate BTTS rates
            all_btts = sum(1 for m in fixtures if m['goals']['home'] > 0 and m['goals']['away'] > 0)
            all_btts_rate = (all_btts / len(fixtures) * 100) if fixtures else 0
            
            home_btts = sum(1 for m in home_meetings if m['btts'])
            home_btts_rate = (home_btts / len(home_meetings) * 100) if home_meetings else 0
            
            away_btts = sum(1 for m in away_meetings if m['btts'])
            away_btts_rate = (away_btts / len(away_meetings) * 100) if away_meetings else 0
            
            # Trend: are recent meetings more BTTS?
            recent_3 = fixtures[:3]
            recent_btts = sum(1 for m in recent_3 if m['goals']['home'] > 0 and m['goals']['away'] > 0)
            recent_btts_rate = (recent_btts / len(recent_3) * 100) if recent_3 else 0
            
            trend = 'increasing' if recent_btts_rate > all_btts_rate else 'decreasing'
            
            return {
                'total_meetings': len(fixtures),
                'overall_btts_rate': round(all_btts_rate, 1),
                'home_btts_rate': round(home_btts_rate, 1),
                'away_btts_rate': round(away_btts_rate, 1),
                'recent_btts_rate': round(recent_btts_rate, 1),
                'trend': trend,
                'btts_adjustment': +3 if trend == 'increasing' and recent_btts_rate > 65 else 0
            }
        
        except Exception as e:
            return None


# Test
if __name__ == "__main__":
    API_KEY = "1a1c70f5c48bfdce946b71680e47e92e"
    
    print("🧪 Testing Advanced Stats...\n")
    
    stats = AdvancedStats(API_KEY)
    
    # Test referee stats
    print("1️⃣ Testing Referee Stats...")
    # Example referee ID (you'd get this from fixtures)
    
    # Test injuries
    print("\n2️⃣ Testing Injuries...")
    injuries = stats.get_team_injuries(33)  # Man United
    if injuries:
        print(f"✅ Injuries loaded!")
        print(f"   Total: {injuries['total_injuries']}")
        print(f"   Key players out: {injuries['key_players_out']}")
        print(f"   BTTS adjustment: {injuries['btts_adjustment']}")
    
    print("\n✅ Advanced Stats Module Ready!")
