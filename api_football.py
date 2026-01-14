"""
API-Football Integration for BTTS Pro Analyzer
Provides xG (Expected Goals) and advanced statistics

API-Football: https://www.api-football.com
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime
import time

class APIFootball:
    """Interface to API-Football for xG and advanced stats"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': api_key
        }
        
        # League ID mappings (API-Football league IDs) - ALL 28 LEAGUES
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
        
        # Rate limiting
        self.last_request = 0
        self.min_delay = 0.5  # Seconds between requests
    
    def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    def test_connection(self) -> bool:
        """Test if API key works"""
        try:
            self._rate_limit()
            response = requests.get(
                f"{self.base_url}/status",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API-Football connected!")
                print(f"Account: {data.get('response', {}).get('account', {}).get('firstname', 'Unknown')}")
                print(f"Requests today: {data.get('response', {}).get('requests', {}).get('current', 0)}")
                print(f"Limit: {data.get('response', {}).get('requests', {}).get('limit_day', 0)}")
                return True
            else:
                print(f"❌ API Error: {response.status_code}")
                return False
        
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def get_league_matches(self, league_code: str, season: int = 2024) -> List[Dict]:
        """
        Get all finished matches for a league with xG data
        """
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"⚠️ League {league_code} not found")
            return []
        
        try:
            self._rate_limit()
            
            # Get fixtures with statistics
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
            
            if response.status_code != 200:
                print(f"❌ API Error for {league_code}: {response.status_code}")
                return []
            
            data = response.json()
            
            if 'response' not in data:
                print(f"⚠️ No data for {league_code}")
                return []
            
            fixtures = data['response']
            matches = []
            
            for fixture in fixtures:
                try:
                    match_data = self._parse_fixture(fixture)
                    if match_data:
                        matches.append(match_data)
                except Exception as e:
                    continue
            
            print(f"✅ Loaded {len(matches)} matches for {league_code}")
            return matches
        
        except Exception as e:
            print(f"❌ Error loading {league_code}: {e}")
            return []
    
    def _parse_fixture(self, fixture: Dict) -> Optional[Dict]:
        """Parse a fixture and extract relevant data"""
        try:
            # Basic match info
            match_id = fixture['fixture']['id']
            match_date = fixture['fixture']['date']
            
            home_team = fixture['teams']['home']['name']
            away_team = fixture['teams']['away']['name']
            home_id = fixture['teams']['home']['id']
            away_id = fixture['teams']['away']['id']
            
            # Scores
            home_score = fixture['goals']['home']
            away_score = fixture['goals']['away']
            
            if home_score is None or away_score is None:
                return None
            
            # Check if match has statistics
            # Note: We need to make separate call for xG
            # For now, we'll mark it for later xG fetch
            
            return {
                'match_id': match_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_team_id': home_id,
                'away_team_id': away_id,
                'home_score': home_score,
                'away_score': away_score,
                'match_date': match_date,
                'btts': (home_score > 0 and away_score > 0),
                'total_goals': home_score + away_score
            }
        
        except Exception as e:
            return None
    
    def get_match_statistics(self, fixture_id: int) -> Optional[Dict]:
        """
        Get detailed statistics including xG for a specific match
        """
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
            
            if 'response' not in data or len(data['response']) < 2:
                return None
            
            # Extract statistics for home and away
            home_stats = data['response'][0]['statistics']
            away_stats = data['response'][1]['statistics']
            
            # Find xG values
            home_xg = self._find_stat(home_stats, 'expected_goals')
            away_xg = self._find_stat(away_stats, 'expected_goals')
            
            # Other useful stats
            home_shots = self._find_stat(home_stats, 'Total Shots')
            away_shots = self._find_stat(away_stats, 'Total Shots')
            
            home_shots_target = self._find_stat(home_stats, 'Shots on Goal')
            away_shots_target = self._find_stat(away_stats, 'Shots on Goal')
            
            return {
                'xg_home': float(home_xg) if home_xg else None,
                'xg_away': float(away_xg) if away_xg else None,
                'shots_home': int(home_shots) if home_shots else None,
                'shots_away': int(away_shots) if away_shots else None,
                'shots_on_target_home': int(home_shots_target) if home_shots_target else None,
                'shots_on_target_away': int(away_shots_target) if away_shots_target else None
            }
        
        except Exception as e:
            return None
    
    def _find_stat(self, stats: List[Dict], stat_name: str) -> Optional[str]:
        """Find a specific statistic from stats list"""
        for stat in stats:
            if stat.get('type') == stat_name:
                return stat.get('value')
        return None
    
    def get_team_xg_average(self, team_id: int, league_id: int, season: int = 2024) -> Optional[Dict]:
        """
        Get average xG for/against for a team
        """
        try:
            # Get team's fixtures
            self._rate_limit()
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'team': team_id,
                    'league': league_id,
                    'season': season,
                    'status': 'FT'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            fixtures = data.get('response', [])
            
            xg_for = []
            xg_against = []
            
            for fixture in fixtures:
                fixture_id = fixture['fixture']['id']
                stats = self.get_match_statistics(fixture_id)
                
                if stats and stats['xg_home'] and stats['xg_away']:
                    if fixture['teams']['home']['id'] == team_id:
                        xg_for.append(stats['xg_home'])
                        xg_against.append(stats['xg_away'])
                    else:
                        xg_for.append(stats['xg_away'])
                        xg_against.append(stats['xg_home'])
            
            if not xg_for:
                return None
            
            return {
                'matches': len(xg_for),
                'avg_xg_for': sum(xg_for) / len(xg_for),
                'avg_xg_against': sum(xg_against) / len(xg_against)
            }
        
        except Exception as e:
            return None


    def get_upcoming_fixtures(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """
        Get upcoming fixtures for a league
        
        Args:
            league_code: League code (e.g., 'BL1', 'PL')
            days_ahead: Number of days ahead to fetch (default 7)
            
        Returns:
            List of upcoming fixtures with team info
        """
        from datetime import datetime, timedelta
        
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"⚠️ Unknown league code: {league_code}")
            return []
        
        self._rate_limit()
        
        # Calculate date range
        today = datetime.now()
        end_date = today + timedelta(days=days_ahead)
        
        params = {
            'league': league_id,
            'season': 2025,  # Current season 2025/2026
            'from': today.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'status': 'NS'  # Not Started
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('response'):
                    fixtures = []
                    for fixture in data['response']:
                        fixtures.append({
                            'fixture_id': fixture['fixture']['id'],
                            'date': fixture['fixture']['date'],
                            'home_team': fixture['teams']['home']['name'],
                            'home_team_id': fixture['teams']['home']['id'],
                            'away_team': fixture['teams']['away']['name'],
                            'away_team_id': fixture['teams']['away']['id'],
                            'league_id': league_id,
                            'league_code': league_code
                        })
                    return fixtures
                else:
                    print(f"⚠️ No upcoming fixtures found for {league_code}")
                    return []
            else:
                print(f"❌ API error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching fixtures: {e}")
            return []


# Test function
if __name__ == "__main__":
    API_KEY = "1a1c70f5c48bfdce946b71680e47e92e"
    
    print("🧪 Testing API-Football Integration...\n")
    
    api = APIFootball(API_KEY)
    
    # Test connection
    if api.test_connection():
        print("\n✅ Connection successful!\n")
        
        # Test getting Bundesliga matches
        print("📊 Testing Bundesliga data...")
        matches = api.get_league_matches('BL1', season=2024)
        
        if matches:
            print(f"✅ Found {len(matches)} Bundesliga matches")
            print(f"\nSample match:")
            print(f"  {matches[0]['home_team']} vs {matches[0]['away_team']}")
            print(f"  Score: {matches[0]['home_score']}-{matches[0]['away_score']}")
            print(f"  BTTS: {matches[0]['btts']}")
        
        # Test upcoming fixtures
        print(f"\n📅 Testing upcoming fixtures...")
        upcoming = api.get_upcoming_fixtures('BL1', days_ahead=7)
        if upcoming:
            print(f"✅ Found {len(upcoming)} upcoming matches")
    else:
        print("❌ Connection failed!")

