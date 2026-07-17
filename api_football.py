"""
API-Football Integration - FINAL FIXED VERSION
✅ Correct header: x-apisports-key
Season selection is dynamic.
✅ All required methods included
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from season_utils import (
    current_season_start_year,
    current_season_start_year_for_id,
)
from league_catalog import ANALYZER_LEAGUE_IDS

class APIFootball:
    """API-Football wrapper with all 28 leagues"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://v3.football.api-sports.io'
        self.headers = {
            'x-apisports-key': api_key  # CORRECTED
        }
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
        self.last_error: Optional[str] = None
        
        self.league_ids = ANALYZER_LEAGUE_IDS.copy()
        
        print(f"API-Football initialized with {len(self.league_ids)} leagues")

    @staticmethod
    def _payload_error(payload) -> Optional[str]:
        if not isinstance(payload, dict):
            return "Invalid provider payload"
        errors = payload.get('errors')
        if not errors:
            return None
        if isinstance(errors, dict):
            return "; ".join(f"{key}: {value}" for key, value in errors.items())
        return str(errors)
    
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
        self.last_error = None
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"WARNING: Unknown league code: {league_code}")
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
                    'season': current_season_start_year(league_code),
                    'from': today.strftime('%Y-%m-%d'),
                    'to': end_date.strftime('%Y-%m-%d'),
                    'status': 'NS'  # Not Started
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                provider_error = self._payload_error(data)
                if provider_error:
                    self.last_error = provider_error
                    print(f"ERROR: API provider error for {league_code}: {provider_error}")
                    return []
                fixtures = data.get('response', [])
                if not isinstance(fixtures, list):
                    self.last_error = "Invalid fixtures response"
                    return []
                
                print(f"Found {len(fixtures)} upcoming fixtures for {league_code}")
                
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
                        print(f"WARNING: Missing data in fixture: {e}")
                        continue
                
                return result
            else:
                self.last_error = f"HTTP {response.status_code}"
                print(f"ERROR: API status {response.status_code} for {league_code}")
                return []
                
        except Exception as e:
            self.last_error = type(e).__name__
            print(f"ERROR: Could not fetch fixtures for {league_code}: {e}")
            return []
    
    def get_live_matches(self) -> List[Dict]:
        """Get all live matches across all leagues"""
        self.last_error = None
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
                provider_error = self._payload_error(data)
                if provider_error:
                    self.last_error = provider_error
                    return []
                return data.get('response', [])
            else:
                self.last_error = f"HTTP {response.status_code}"
                print(f"ERROR: API status {response.status_code}")
                return []
                
        except Exception as e:
            self.last_error = str(e)
            print(f"ERROR: {e}")
            return []
    
    def get_match_statistics(
        self,
        fixture_id: int,
        home_team_id: int,
        away_team_id: int,
    ) -> Optional[Dict]:
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
                    stats_by_team = {
                        item.get('team', {}).get('id'): item.get('statistics', [])
                        for item in stats_list
                    }
                    home_stats = stats_by_team.get(home_team_id)
                    away_stats = stats_by_team.get(away_team_id)
                    if home_stats is None or away_stats is None:
                        return None
                    
                    def get_stat(stats, stat_type):
                        for s in stats:
                            if s.get('type') == stat_type:
                                val = s.get('value')
                                if val is None:
                                    return None
                                if isinstance(val, str):
                                    val = val.replace('%', '')
                                try:
                                    return float(val)
                                except (TypeError, ValueError):
                                    return None
                        return None
                    
                    return {
                        # Shots
                        'shots_home': get_stat(home_stats, 'Total Shots'),
                        'shots_away': get_stat(away_stats, 'Total Shots'),
                        'shots_on_target_home': get_stat(home_stats, 'Shots on Goal'),
                        'shots_on_target_away': get_stat(away_stats, 'Shots on Goal'),
                        'shots_off_target_home': get_stat(home_stats, 'Shots off Goal'),
                        'shots_off_target_away': get_stat(away_stats, 'Shots off Goal'),
                        'shots_blocked_home': get_stat(home_stats, 'Blocked Shots'),
                        'shots_blocked_away': get_stat(away_stats, 'Blocked Shots'),
                        'shots_inside_box_home': get_stat(home_stats, 'Shots insidebox'),
                        'shots_inside_box_away': get_stat(away_stats, 'Shots insidebox'),
                        
                        # Cards (CRITICAL FOR ALTERNATIVE MARKETS!)
                        'yellow_cards_home': get_stat(home_stats, 'Yellow Cards'),
                        'yellow_cards_away': get_stat(away_stats, 'Yellow Cards'),
                        'red_cards_home': get_stat(home_stats, 'Red Cards'),
                        'red_cards_away': get_stat(away_stats, 'Red Cards'),
                        
                        # Fouls (CRITICAL FOR CARD PREDICTIONS!)
                        'fouls_home': get_stat(home_stats, 'Fouls'),
                        'fouls_away': get_stat(away_stats, 'Fouls'),
                        
                        # Corners (CRITICAL FOR CORNER MARKET!)
                        'corners_home': get_stat(home_stats, 'Corner Kicks'),
                        'corners_away': get_stat(away_stats, 'Corner Kicks'),
                        
                        # Possession & xG
                        'possession_home': get_stat(home_stats, 'Ball Possession'),
                        'possession_away': get_stat(away_stats, 'Ball Possession'),
                        'xg_home': get_stat(home_stats, 'expected_goals'),
                        'xg_away': get_stat(away_stats, 'expected_goals'),
                        
                        # Additional useful stats
                        'attacks_home': get_stat(home_stats, 'Total attacks'),
                        'attacks_away': get_stat(away_stats, 'Total attacks'),
                        'dangerous_attacks_home': get_stat(home_stats, 'Dangerous attacks'),
                        'dangerous_attacks_away': get_stat(away_stats, 'Dangerous attacks'),
                        'offsides_home': get_stat(home_stats, 'Offsides'),
                        'offsides_away': get_stat(away_stats, 'Offsides'),
                        'saves_home': get_stat(home_stats, 'Goalkeeper Saves'),
                        'saves_away': get_stat(away_stats, 'Goalkeeper Saves'),
                        'passes_home': get_stat(home_stats, 'Total passes'),
                        'passes_away': get_stat(away_stats, 'Total passes'),
                        'passes_accurate_home': get_stat(home_stats, 'Passes accurate'),
                        'passes_accurate_away': get_stat(away_stats, 'Passes accurate')
                    }
            
            return None
            
        except Exception as e:
            print(f"WARNING: Stats error: {e}")
            return None
    
    def get_team_statistics(self, team_id: int, league_id: int,
                            season: Optional[int] = None) -> Optional[Dict]:
        """Get team statistics from API-Football"""
        season = season or current_season_start_year_for_id(league_id)
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
                    
                    print(f"API returned team: {stats.get('team')}")
                    
                    # Extract relevant statistics
                    fixtures = stats.get('fixtures', {})
                    goals = stats.get('goals', {})
                    
                    home_stats = fixtures.get('played', {}).get('home', 0)
                    away_stats = fixtures.get('played', {}).get('away', 0)
                    total_stats = fixtures.get('played', {}).get('total', 0)
                    
                    clean_sheets_home = int(stats.get('clean_sheet', {}).get('home', 0))
                    clean_sheets_away = int(stats.get('clean_sheet', {}).get('away', 0))
                    failed_to_score_home = int(stats.get('failed_to_score', {}).get('home', 0))
                    failed_to_score_away = int(stats.get('failed_to_score', {}).get('away', 0))
                    btts_rates = self._get_btts_rates(team_id, league_id, season)
                    
                    # Convert string values to float
                    def safe_float(value, default):
                        try:
                            return float(value) if value is not None else default
                        except (TypeError, ValueError):
                            return default
                    
                    played_home = int(home_stats) if home_stats else 0
                    played_away = int(away_stats) if away_stats else 0
                    scored_home = safe_float(
                        goals.get('for', {}).get('average', {}).get('home'),
                        None,
                    )
                    scored_away = safe_float(
                        goals.get('for', {}).get('average', {}).get('away'),
                        None,
                    )
                    conceded_home = safe_float(
                        goals.get('against', {}).get('average', {}).get('home'),
                        None,
                    )
                    conceded_away = safe_float(
                        goals.get('against', {}).get('average', {}).get('away'),
                        None,
                    )

                    def weighted_average(home_value, away_value):
                        observations = []
                        if home_value is not None and played_home > 0:
                            observations.append((home_value, played_home))
                        if away_value is not None and played_away > 0:
                            observations.append((away_value, played_away))
                        total = sum(sample for _, sample in observations)
                        return (
                            sum(value * sample for value, sample in observations) / total
                            if total > 0
                            else None
                        )

                    return {
                        'team_name': stats.get('team', {}).get('name', 'Unknown'),
                        'matches_played_home': played_home,
                        'matches_played_away': played_away,
                        'avg_goals_scored_home': scored_home,
                        'avg_goals_scored_away': scored_away,
                        'avg_goals_conceded_home': conceded_home,
                        'avg_goals_conceded_away': conceded_away,
                        'avg_goals_scored_total': weighted_average(
                            scored_home,
                            scored_away,
                        ),
                        'avg_goals_conceded_total': weighted_average(
                            conceded_home,
                            conceded_away,
                        ),
                        'btts_rate_home': btts_rates['home_rate'],
                        'btts_rate_away': btts_rates['away_rate'],
                        'btts_rate_total': btts_rates['total_rate'],
                        'btts_sample_home': btts_rates['home_matches'],
                        'btts_sample_away': btts_rates['away_matches'],
                        'btts_sample_total': btts_rates['total_matches'],
                        'clean_sheets_home': clean_sheets_home,
                        'clean_sheets_away': clean_sheets_away,
                        'failed_to_score_home': failed_to_score_home,
                        'failed_to_score_away': failed_to_score_away
                    }
            
            return None
            
        except Exception as e:
            print(f"WARNING: Team stats error: {e}")
            return None

    def _get_btts_rates(self, team_id: int, league_id: int, season: int,
                        limit: int = 20) -> Dict:
        """Calculate BTTS rates from finished fixtures without aggregate overlap bias."""
        self._rate_limit()
        empty = {
            'home_rate': None,
            'away_rate': None,
            'total_rate': None,
            'home_matches': 0,
            'away_matches': 0,
            'total_matches': 0,
        }
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'team': team_id,
                    'league': league_id,
                    'season': season,
                    'status': 'FT',
                    'last': limit,
                },
                timeout=15,
            )
            if response.status_code != 200:
                return empty
            fixtures = response.json().get('response', [])
        except Exception:
            return empty

        counts = {'home': [0, 0], 'away': [0, 0]}
        for fixture in fixtures:
            home_id = fixture.get('teams', {}).get('home', {}).get('id')
            home_goals = fixture.get('goals', {}).get('home')
            away_goals = fixture.get('goals', {}).get('away')
            if home_goals is None or away_goals is None:
                continue
            venue = 'home' if home_id == team_id else 'away'
            counts[venue][1] += 1
            if home_goals > 0 and away_goals > 0:
                counts[venue][0] += 1

        home_btts, home_matches = counts['home']
        away_btts, away_matches = counts['away']
        total_btts = home_btts + away_btts
        total_matches = home_matches + away_matches

        def rate(btts: int, matches: int) -> Optional[float]:
            return round(btts / matches * 100.0, 1) if matches else None

        return {
            'home_rate': rate(home_btts, home_matches),
            'away_rate': rate(away_btts, away_matches),
            'total_rate': rate(total_btts, total_matches),
            'home_matches': home_matches,
            'away_matches': away_matches,
            'total_matches': total_matches,
        }
    
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
            print(f"WARNING: H2H error: {e}")
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
                    'season': current_season_start_year_for_id(league_id),
                    'last': n
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', [])
            
            return []
            
        except Exception as e:
            print(f"WARNING: Last matches error: {e}")
            return []
    
    def get_head_to_head(self, team1_id: int, team2_id: int, last_n: int = 10) -> List[Dict]:
        """Alias for get_h2h - used by advanced_analyzer"""
        return self.get_h2h(team1_id, team2_id, last_n)
    
    def get_team_last_matches(
        self,
        team_id: int,
        n: int = 5,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> Dict:
        """
        Get last N matches for a team and calculate form stats
        Used by advanced_analyzer for form calculation
        """
        self._rate_limit()
        empty = {
            'matches_played': 0,
            'btts_rate': None,
            'avg_goals_scored': None,
            'avg_goals_conceded': None,
            'form_string': '',
            'wins': 0,
            'draws': 0,
            'losses': 0,
        }
        
        try:
            params = {
                'team': team_id,
                'last': n,
                'status': 'FT',
            }
            if league_id is not None:
                params['league'] = league_id
                params['season'] = season or current_season_start_year_for_id(
                    league_id
                )
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('response', [])
                
                if not matches:
                    return empty
                
                # Calculate stats from matches
                btts_count = 0
                total_scored = 0
                total_conceded = 0
                wins = 0
                draws = 0
                losses = 0
                form_string = ""
                
                for match in matches:
                    try:
                        home_id = match['teams']['home']['id']
                        away_id = match['teams']['away']['id']
                        home_goals = match['goals']['home']
                        away_goals = match['goals']['away']
                        if home_goals is None or away_goals is None:
                            continue
                        
                        # Determine if this team was home or away
                        if home_id == team_id:
                            scored = home_goals
                            conceded = away_goals
                            if home_goals > away_goals:
                                wins += 1
                                form_string += "W"
                            elif home_goals < away_goals:
                                losses += 1
                                form_string += "L"
                            else:
                                draws += 1
                                form_string += "D"
                        else:
                            scored = away_goals
                            conceded = home_goals
                            if away_goals > home_goals:
                                wins += 1
                                form_string += "W"
                            elif away_goals < home_goals:
                                losses += 1
                                form_string += "L"
                            else:
                                draws += 1
                                form_string += "D"
                        
                        total_scored += scored
                        total_conceded += conceded
                        
                        # BTTS if both teams scored
                        if home_goals > 0 and away_goals > 0:
                            btts_count += 1
                            
                    except (KeyError, TypeError):
                        continue
                
                matches_played = wins + draws + losses
                if matches_played == 0:
                    return empty
                btts_rate = btts_count / matches_played * 100
                avg_scored = total_scored / matches_played
                avg_conceded = total_conceded / matches_played
                
                return {
                    'matches_played': matches_played,
                    'btts_rate': round(btts_rate, 1),
                    'avg_goals_scored': round(avg_scored, 2),
                    'avg_goals_conceded': round(avg_conceded, 2),
                    'form_string': form_string,
                    'wins': wins,
                    'draws': draws,
                    'losses': losses
                }
            
            return empty
            
        except Exception as e:
            print(f"WARNING: Form error: {e}")
            return empty


# Test
if __name__ == '__main__':
    print("\n" + "="*60)
    print("API-FOOTBALL TEST")
    print("="*60)
    
    api_key = input("\nEnter API key (or press Enter to skip): ").strip()
    
    if api_key:
        api = APIFootball(api_key)
        
        print("\nTesting get_upcoming_fixtures() for Premier League...")
        fixtures = api.get_upcoming_fixtures('PL', days_ahead=7)
        
        if fixtures:
            print(f"\nFound {len(fixtures)} upcoming fixtures")
            for f in fixtures[:3]:
                print(f"   {f['home_team']} vs {f['away_team']} - {f['date'][:10]}")
        else:
            print("\nNo fixtures found")
    else:
        print("\nTest skipped (no API key)")
    
    print("\nAPI-Football module loaded successfully")
