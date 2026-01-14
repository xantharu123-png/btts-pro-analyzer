"""
API-Football Integration for BTTS Pro Analyzer
Provides xG (Expected Goals) and advanced statistics

API-Football: https://www.api-football.com
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
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
        
        # League ID mappings (API-Football league IDs)
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
            
            # TIER 3: GOAL FESTIVALS! 🎊 (9)
            'SPL': 265,   # 🇸🇬 Singapore Premier
            'ESI': 330,   # 🇪🇪 Esiliiga
            'IS2': 165,   # 🇮🇸 1. Deild
            'ALE': 188,   # 🇦🇺 A-League
            'ED1': 89,    # 🇳🇱 Eerste Divisie
            'CHL': 209,   # 🇨🇭 Challenge League
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
    
    def get_upcoming_fixtures(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """
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
        
        params = {
            'league': league_id,
            'season': 2025,  # Season 2025/26
            'from': today.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
        }
        
        try:
            print(f"📡 Fetching fixtures for {league_code} (ID: {league_id})...")
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('response'):
                    fixtures = []
                    for fixture in data['response']:
                        status = fixture['fixture']['status']['short']
                        # Nur nicht-gestartete Spiele
                        if status in ['NS', 'TBD', 'SUSP', 'PST']:
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
                    print(f"✅ Found {len(fixtures)} upcoming fixtures for {league_code}")
                    return fixtures
                else:
                    print(f"⚠️ No fixtures found for {league_code}")
                    return []
            else:
                print(f"❌ API error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching fixtures: {e}")
            return []
    
    def get_live_matches(self) -> List[Dict]:
        """
        Get all currently live matches
        """
        self._rate_limit()
        
        try:
            print(f"\n{'='*60}")
            print(f"🔍 FETCHING ALL LIVE MATCHES...")
            print(f"{'='*60}")
            
            print(f"\n📡 Making API request to: {self.base_url}/fixtures")
            print(f"   Params: live=all")
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            print(f"📨 Response Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                return []
            
            data = response.json()
            all_matches = data.get('response', [])
            
            print(f"✅ Found {len(all_matches)} total live matches!")
            
            # Filter für unsere Ligen
            print(f"\n🔍 Filtering for our 28 leagues...")
            our_league_ids = set(self.league_ids.values())
            
            our_matches = []
            for match in all_matches:
                league_id = match.get('league', {}).get('id')
                home = match.get('teams', {}).get('home', {}).get('name', 'Unknown')
                away = match.get('teams', {}).get('away', {}).get('name', 'Unknown')
                league_name = match.get('league', {}).get('name', 'Unknown')
                
                print(f"   Found: {home} vs {away} ({league_name}, ID: {league_id})")
                
                if league_id in our_league_ids:
                    print(f"      ✅ ADDED to analysis!")
                    our_matches.append(match)
                else:
                    print(f"      ⏭️ Skipped (league not in our 28)")
            
            print(f"\n✅ TOTAL IN OUR LEAGUES: {len(our_matches)}")
            return our_matches
        
        except Exception as e:
            print(f"❌ Error fetching live matches: {e}")
            return []
    
    def get_league_matches(self, league_code: str, season: int = 2025) -> List[Dict]:
        """
        Get all finished matches for a league with xG data
        """
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"⚠️ League {league_code} not found")
            return []
        
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
            match_id = fixture['fixture']['id']
            match_date = fixture['fixture']['date']
            
            home_team = fixture['teams']['home']['name']
            away_team = fixture['teams']['away']['name']
            home_id = fixture['teams']['home']['id']
            away_id = fixture['teams']['away']['id']
            
            home_score = fixture['goals']['home']
            away_score = fixture['goals']['away']
            
            if home_score is None or away_score is None:
                return None
            
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
            
            home_stats = data['response'][0]['statistics']
            away_stats = data['response'][1]['statistics']
            
            home_xg = self._find_stat(home_stats, 'expected_goals')
            away_xg = self._find_stat(away_stats, 'expected_goals')
            
            home_shots = self._find_stat(home_stats, 'Total Shots')
            away_shots = self._find_stat(away_stats, 'Total Shots')
            
            home_shots_target = self._find_stat(home_stats, 'Shots on Goal')
            away_shots_target = self._find_stat(away_stats, 'Shots on Goal')
            
            home_corners = self._find_stat(home_stats, 'Corner Kicks')
            away_corners = self._find_stat(away_stats, 'Corner Kicks')
            
            home_fouls = self._find_stat(home_stats, 'Fouls')
            away_fouls = self._find_stat(away_stats, 'Fouls')
            
            home_yellow = self._find_stat(home_stats, 'Yellow Cards')
            away_yellow = self._find_stat(away_stats, 'Yellow Cards')
            
            home_red = self._find_stat(home_stats, 'Red Cards')
            away_red = self._find_stat(away_stats, 'Red Cards')
            
            home_possession = self._find_stat(home_stats, 'Ball Possession')
            away_possession = self._find_stat(away_stats, 'Ball Possession')
            
            return {
                'xg_home': float(home_xg) if home_xg else None,
                'xg_away': float(away_xg) if away_xg else None,
                'shots_home': int(home_shots) if home_shots else None,
                'shots_away': int(away_shots) if away_shots else None,
                'shots_on_target_home': int(home_shots_target) if home_shots_target else None,
                'shots_on_target_away': int(away_shots_target) if away_shots_target else None,
                'corners_home': int(home_corners) if home_corners else None,
                'corners_away': int(away_corners) if away_corners else None,
                'fouls_home': int(home_fouls) if home_fouls else None,
                'fouls_away': int(away_fouls) if away_fouls else None,
                'yellow_home': int(home_yellow) if home_yellow else None,
                'yellow_away': int(away_yellow) if away_yellow else None,
                'red_home': int(home_red) if home_red else None,
                'red_away': int(away_red) if away_red else None,
                'possession_home': home_possession,
                'possession_away': away_possession
            }
        
        except Exception as e:
            return None
    
    def _find_stat(self, stats: List[Dict], stat_name: str) -> Optional[str]:
        """Find a specific statistic from stats list"""
        for stat in stats:
            if stat.get('type') == stat_name:
                value = stat.get('value')
                if value is not None:
                    # Handle percentage strings like "55%"
                    if isinstance(value, str) and '%' in value:
                        return value.replace('%', '')
                    return value
        return None
    
    def get_team_xg_average(self, team_id: int, league_id: int, season: int = 2025) -> Optional[Dict]:
        """
        Get average xG for/against for a team
        """
        try:
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


# Test function
if __name__ == "__main__":
    API_KEY = "YOUR_API_KEY"
    
    print("🧪 Testing API-Football Integration...\n")
    
    api = APIFootball(API_KEY)
    
    if api.test_connection():
        print("\n✅ Connection successful!\n")
        
        # Test upcoming fixtures
        print("📅 Testing upcoming fixtures...")
        fixtures = api.get_upcoming_fixtures('BL1', days_ahead=7)
        if fixtures:
            print(f"✅ Found {len(fixtures)} upcoming Bundesliga matches")
            for f in fixtures[:3]:
                print(f"   {f['home_team']} vs {f['away_team']} - {f['date']}")
