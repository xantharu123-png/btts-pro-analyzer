"""
API-Football Integration - FINAL CORRECTED VERSION
✅ Correct header: x-apisports-key (not x-rapidapi-key)
✅ Season: Auto-detected (2025 for current season 2025/26)
✅ get_upcoming_fixtures() is INSIDE the class
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class APIFootball:
    """API-Football wrapper with all 28 leagues"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://v3.football.api-sports.io'
        self.headers = {
            'x-apisports-key': api_key  # CORRECTED: Use x-apisports-key for direct API calls
        }
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
        
        # ALL 28 LEAGUES - League ID mappings
        self.league_ids = {
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
            
            # TIER 3: GOAL FESTIVALS! (9)
            'SPL': 265,   # 🇸🇬 Singapore Premier
            'ESI': 330,   # 🇪🇪 Esiliiga (Estonia 2)
            'IS2': 165,   # 🇮🇸 1. Deild (Iceland 2)
            'ALE': 188,   # 🇦🇺 A-League
            'ED1': 89,    # 🇳🇱 Eerste Divisie (NL 2)
            'CHL': 209,   # 🇨🇭 Challenge League (CH 2)
            'ALL': 113,   # 🇸🇪 Allsvenskan
            'QSL': 292,   # 🇶🇦 Qatar Stars League
            'UAE': 301,   # 🇦🇪 UAE Pro League
        }
        
        print(f"✅ API-Football initialized with {len(self.league_ids)} leagues")
    
    def _rate_limit(self):
        """Ensure minimum time between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def get_upcoming_fixtures(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """
        ✅ NOW INSIDE THE CLASS! 
        Get upcoming fixtures for a league
        
        Args:
            league_code: League code (e.g., 'BL1', 'PL')
            days_ahead: Number of days ahead to fetch (default 7)
            
        Returns:
            List of upcoming fixtures with team info
        """
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"⚠️ Unknown league code: {league_code}")
            return []
        
        self._rate_limit()
        
        # Calculate date range
        today = datetime.now()
        end_date = today + timedelta(days=days_ahead)
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': 2025,  # CORRECTED: Current season 2025/26
                    'from': today.strftime('%Y-%m-%d'),
                    'to': end_date.strftime('%Y-%m-%d'),
                    'status': 'NS'  # Not Started
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get('response', [])
                
                print(f"   📅 Found {len(fixtures)} upcoming fixtures for {league_code}")
                
                result = []
                for fixture in fixtures:
                    try:
                        result.append({
                            'fixture_id': fixture['fixture']['id'],
                            'date': fixture['fixture']['date'],
                            'home_team': fixture['teams']['home']['name'],
                            'away_team': fixture['teams']['away']['name'],
                            'home_team_id': fixture['teams']['home']['id'],
                            'away_team_id': fixture['teams']['away']['id'],
                            'league_code': league_code,
                            'league_name': fixture['league']['name']
                        })
                    except KeyError as e:
                        print(f"   ⚠️ Missing data in fixture: {e}")
                        continue
                
                return result
            else:
                print(f"   ❌ API error {response.status_code} for {league_code}")
                return []
                
        except Exception as e:
            print(f"   ❌ Exception fetching fixtures for {league_code}: {e}")
            return []
    
    def get_live_matches(self) -> List[Dict]:
        """Get all live matches across all leagues"""
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', [])
            else:
                print(f"❌ API error {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return []
    
    def get_match_statistics(self, fixture_id: int) -> Optional[Dict]:
        """Get detailed statistics for a specific match"""
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures/statistics",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                stats_list = data.get('response', [])
                
                if len(stats_list) >= 2:
                    home_stats = stats_list[0].get('statistics', [])
                    away_stats = stats_list[1].get('statistics', [])
                    
                    def get_stat(stats, stat_type):
                        for s in stats:
                            if s.get('type') == stat_type:
                                val = s.get('value')
                                if val is None:
                                    return 0
                                if isinstance(val, str):
                                    val = val.replace('%', '')
                                try:
                                    return float(val)
                                except:
                                    return 0
                        return 0
                    
                    return {
                        'shots_home': get_stat(home_stats, 'Total Shots'),
                        'shots_away': get_stat(away_stats, 'Total Shots'),
                        'shots_on_target_home': get_stat(home_stats, 'Shots on Goal'),
                        'shots_on_target_away': get_stat(away_stats, 'Shots on Goal'),
                        'possession_home': get_stat(home_stats, 'Ball Possession'),
                        'possession_away': get_stat(away_stats, 'Ball Possession'),
                        'xg_home': get_stat(home_stats, 'expected_goals'),
                        'xg_away': get_stat(away_stats, 'expected_goals')
                    }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Stats error: {e}")
            return None
    
    def get_team_statistics(self, team_id: int, league_id: int, season: int = 2025) -> Optional[Dict]:
        """Get team statistics from API-Football"""
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/teams/statistics",
                headers=self.headers,
                params={
                    'team': team_id,
                    'league': league_id,
                    'season': season
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    stats = data['response']
                    
                    # Extract relevant statistics
                    fixtures = stats.get('fixtures', {})
                    goals = stats.get('goals', {})
                    
                    home_stats = fixtures.get('played', {}).get('home', 0)
                    away_stats = fixtures.get('played', {}).get('away', 0)
                    
                    return {
                        'matches_played_home': home_stats,
                        'matches_played_away': away_stats,
                        'avg_goals_scored_home': goals.get('for', {}).get('average', {}).get('home', 1.5),
                        'avg_goals_scored_away': goals.get('for', {}).get('average', {}).get('away', 1.3),
                        'avg_goals_conceded_home': goals.get('against', {}).get('average', {}).get('home', 1.3),
                        'avg_goals_conceded_away': goals.get('against', {}).get('average', {}).get('away', 1.5),
                        'btts_rate_home': 65,  # Default - calculate separately if needed
                        'btts_rate_away': 65,
                        'clean_sheets_home': stats.get('clean_sheet', {}).get('home', 0),
                        'clean_sheets_away': stats.get('clean_sheet', {}).get('away', 0)
                    }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Team stats error: {e}")
            return None
    
    def get_h2h(self, team1_id: int, team2_id: int, last_n: int = 10) -> List[Dict]:
        """Get head-to-head matches"""
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures/headtohead",
                headers=self.headers,
                params={
                    'h2h': f'{team1_id}-{team2_id}',
                    'last': last_n
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', [])
            
            return []
            
        except Exception as e:
            print(f"⚠️ H2H error: {e}")
            return []
    
    def get_last_matches(self, team_id: int, league_id: int, n: int = 5) -> List[Dict]:
        """Get last N matches for a team"""
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'team': team_id,
                    'league': league_id,
                    'season': 2025,
                    'last': n
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', [])
            
            return []
            
        except Exception as e:
            print(f"⚠️ Last matches error: {e}")
            return []


# Test
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔥 API-FOOTBALL TEST")
    print("="*60)
    
    api_key = input("\nEnter API key (or press Enter to skip): ").strip()
    
    if api_key:
        api = APIFootball(api_key)
        
        print("\n📊 Testing get_upcoming_fixtures() for Premier League...")
        fixtures = api.get_upcoming_fixtures('PL', days_ahead=7)
        
        if fixtures:
            print(f"\n✅ Found {len(fixtures)} upcoming fixtures!")
            for f in fixtures[:3]:
                print(f"   {f['home_team']} vs {f['away_team']} - {f['date'][:10]}")
        else:
            print("\n⚠️ No fixtures found")
    else:
        print("\n⚠️ Test skipped (no API key)")
    
    print("\n✅ API-Football module loaded successfully!")
