"""
API-Football Integration for BTTS Pro Analyzer
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
        
        # League ID mappings
        self.league_ids = {
            'BL1': 78, 'PL': 39, 'PD': 140, 'SA': 135, 'FL1': 61,
            'DED': 88, 'PPL': 94, 'TSL': 203, 'ELC': 40, 'BL2': 79,
            'MX1': 262, 'BSA': 71, 'CL': 2, 'EL': 3, 'ECL': 848,
            'SC1': 179, 'BE1': 144, 'SL1': 207, 'AL1': 218,
            'SPL': 265, 'ESI': 330, 'IS2': 165, 'ALE': 188,
            'ED1': 89, 'CHL': 209, 'ALL': 113, 'QSL': 292, 'UAE': 301,
        }
        
        self.last_request = 0
        self.min_delay = 0.5
    
    def _rate_limit(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    def test_connection(self) -> bool:
        try:
            self._rate_limit()
            response = requests.get(f"{self.base_url}/status", headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API-Football connected!")
                return True
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def get_upcoming_fixtures(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming fixtures for a league"""
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"⚠️ Unknown league code: {league_code}")
            return []
        
        self._rate_limit()
        
        today = datetime.now()
        end_date = today + timedelta(days=days_ahead)
        
        params = {
            'league': league_id,
            'season': 2025,  # WICHTIG: Season 2025!
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
            return []
        except Exception as e:
            print(f"❌ Error fetching fixtures: {e}")
            return []
    
    def get_live_matches(self) -> List[Dict]:
        """Get all currently live matches"""
        self._rate_limit()
        
        try:
            print(f"\n{'='*60}")
            print(f"🔍 FETCHING ALL LIVE MATCHES...")
            print(f"{'='*60}")
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            print(f"📨 Response Status: {response.status_code}")
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            all_matches = data.get('response', [])
            
            print(f"✅ Found {len(all_matches)} total live matches!")
            
            our_league_ids = set(self.league_ids.values())
            our_matches = []
            
            print(f"\n🔍 Filtering for our 28 leagues...")
            for match in all_matches:
                league_id = match.get('league', {}).get('id')
                home = match.get('teams', {}).get('home', {}).get('name', 'Unknown')
                away = match.get('teams', {}).get('away', {}).get('name', 'Unknown')
                league_name = match.get('league', {}).get('name', 'Unknown')
                
                print(f"   Found: {home} vs {away} ({league_name}, ID: {league_id})")
                
                if league_id in our_league_ids:
                    print(f"      ✅ INCLUDED!")
                    our_matches.append(match)
                else:
                    print(f"      ⏭️ Skipped (league not in our 28)")
            
            print(f"\n✅ TOTAL IN OUR LEAGUES: {len(our_matches)}")
            return our_matches
        
        except Exception as e:
            print(f"❌ Error fetching live matches: {e}")
            return []
    
    def get_league_matches(self, league_code: str, season: int = 2025) -> List[Dict]:
        """Get all finished matches for a league"""
        league_id = self.league_ids.get(league_code)
        if not league_id:
            return []
        
        try:
            self._rate_limit()
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'league': league_id, 'season': season, 'status': 'FT'},
                timeout=15
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            fixtures = data.get('response', [])
            matches = []
            
            for fixture in fixtures:
                try:
                    match_data = self._parse_fixture(fixture)
                    if match_data:
                        matches.append(match_data)
                except:
                    continue
            
            print(f"✅ Loaded {len(matches)} matches for {league_code}")
            return matches
        
        except Exception as e:
            print(f"❌ Error loading {league_code}: {e}")
            return []
    
    def _parse_fixture(self, fixture: Dict) -> Optional[Dict]:
        try:
            home_score = fixture['goals']['home']
            away_score = fixture['goals']['away']
            
            if home_score is None or away_score is None:
                return None
            
            return {
                'match_id': fixture['fixture']['id'],
                'home_team': fixture['teams']['home']['name'],
                'away_team': fixture['teams']['away']['name'],
                'home_team_id': fixture['teams']['home']['id'],
                'away_team_id': fixture['teams']['away']['id'],
                'home_score': home_score,
                'away_score': away_score,
                'match_date': fixture['fixture']['date'],
                'btts': (home_score > 0 and away_score > 0),
                'total_goals': home_score + away_score
            }
        except:
            return None
    
    def get_match_statistics(self, fixture_id: int) -> Optional[Dict]:
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
            
            return {
                'xg_home': self._find_stat(home_stats, 'expected_goals'),
                'xg_away': self._find_stat(away_stats, 'expected_goals'),
                'shots_home': self._find_stat(home_stats, 'Total Shots'),
                'shots_away': self._find_stat(away_stats, 'Total Shots'),
            }
        except:
            return None
    
    def _find_stat(self, stats: List[Dict], stat_name: str):
        for stat in stats:
            if stat.get('type') == stat_name:
                return stat.get('value')
        return None
    
    def get_team_xg_average(self, team_id: int, league_id: int, season: int = 2025) -> Optional[Dict]:
        return None  # Simplified
    
    def get_team_statistics(self, team_id: int, league_id: int, season: int = 2025) -> Optional[Dict]:
        """
        Get REAL team statistics from API-Football
        Endpoint: /teams/statistics
        """
        try:
            self._rate_limit()
            
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
            
            if response.status_code != 200:
                print(f"❌ Team stats API error: {response.status_code}")
                return None
            
            data = response.json()
            
            if not data.get('response'):
                return None
            
            stats = data['response']
            
            # Extract relevant statistics
            fixtures = stats.get('fixtures', {})
            goals = stats.get('goals', {})
            
            total_home = fixtures.get('played', {}).get('home', 0) or 0
            total_away = fixtures.get('played', {}).get('away', 0) or 0
            total_matches = total_home + total_away
            
            goals_home_scored = goals.get('for', {}).get('total', {}).get('home', 0) or 0
            goals_away_scored = goals.get('for', {}).get('total', {}).get('away', 0) or 0
            goals_home_conceded = goals.get('against', {}).get('total', {}).get('home', 0) or 0
            goals_away_conceded = goals.get('against', {}).get('total', {}).get('away', 0) or 0
            
            # Calculate averages
            avg_scored_home = goals_home_scored / total_home if total_home > 0 else 1.5
            avg_scored_away = goals_away_scored / total_away if total_away > 0 else 1.2
            avg_conceded_home = goals_home_conceded / total_home if total_home > 0 else 1.2
            avg_conceded_away = goals_away_conceded / total_away if total_away > 0 else 1.4
            
            # BTTS calculation from clean sheets
            clean_sheets = stats.get('clean_sheet', {})
            cs_home = clean_sheets.get('home', 0) or 0
            cs_away = clean_sheets.get('away', 0) or 0
            
            # Failed to score
            failed_to_score = stats.get('failed_to_score', {})
            fts_home = failed_to_score.get('home', 0) or 0
            fts_away = failed_to_score.get('away', 0) or 0
            
            # BTTS rate = matches where both scored
            # = matches - (clean sheets + failed to score - both)
            # Approximate: (1 - CS%) * (1 - FTS%)
            cs_rate_home = cs_home / total_home if total_home > 0 else 0.25
            cs_rate_away = cs_away / total_away if total_away > 0 else 0.2
            fts_rate_home = fts_home / total_home if total_home > 0 else 0.2
            fts_rate_away = fts_away / total_away if total_away > 0 else 0.25
            
            btts_rate_home = (1 - cs_rate_home) * (1 - fts_rate_home) * 100
            btts_rate_away = (1 - cs_rate_away) * (1 - fts_rate_away) * 100
            
            return {
                'team_id': team_id,
                'team_name': stats.get('team', {}).get('name', 'Unknown'),
                'matches_played_home': total_home,
                'matches_played_away': total_away,
                'avg_goals_scored_home': round(avg_scored_home, 2),
                'avg_goals_scored_away': round(avg_scored_away, 2),
                'avg_goals_conceded_home': round(avg_conceded_home, 2),
                'avg_goals_conceded_away': round(avg_conceded_away, 2),
                'btts_rate_home': round(btts_rate_home, 1),
                'btts_rate_away': round(btts_rate_away, 1),
                'clean_sheets_home': cs_home,
                'clean_sheets_away': cs_away,
                'failed_to_score_home': fts_home,
                'failed_to_score_away': fts_away,
            }
            
        except Exception as e:
            print(f"❌ Error getting team statistics: {e}")
            return None


if __name__ == "__main__":
    api = APIFootball("YOUR_API_KEY")
    api.test_connection()
