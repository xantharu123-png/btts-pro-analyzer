"""
API-Football Integration - FINAL FIXED VERSION
✅ Correct header: x-apisports-key
Season selection is dynamic.
✅ All required methods included
"""

import math
import requests
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from api_budget import APIBudgetPriority, api_football_get
from date_context import ZURICH_TIMEZONE
from season_utils import (
    current_season_start_year,
    current_season_start_year_for_id,
)
from league_catalog import ANALYZER_LEAGUE_IDS

class APIFootball:
    """API-Football wrapper for the canonical 48-league catalog."""
    
    def __init__(
        self,
        api_key: str,
        *,
        budget_priority: APIBudgetPriority | str = APIBudgetPriority.RECOMMENDATION,
    ):
        self.api_key = api_key
        self.budget_priority = (
            budget_priority
            if isinstance(budget_priority, APIBudgetPriority)
            else APIBudgetPriority(str(budget_priority).strip().lower())
        )
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

    @staticmethod
    def _finite_nonnegative(value, *, maximum: Optional[float] = None) -> Optional[float]:
        if isinstance(value, bool):
            return None
        try:
            numeric = float(str(value).replace('%', '').strip())
        except (TypeError, ValueError):
            return None
        if (
            not math.isfinite(numeric)
            or numeric < 0
            or maximum is not None and numeric > maximum
        ):
            return None
        return numeric

    @classmethod
    def _nonnegative_integer(cls, value, *, maximum: Optional[int] = None) -> Optional[int]:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        if maximum is not None and value > maximum:
            return None
        return value

    @classmethod
    def _positive_integer(cls, value) -> Optional[int]:
        numeric = cls._nonnegative_integer(value)
        return numeric if numeric is not None and numeric > 0 else None

    def _response_data(self, response, label: str, expected_type):
        """Validate HTTP status, provider errors, and response shape."""
        if response.status_code != 200:
            self.last_error = f"{label}: HTTP {response.status_code}"
            return None
        try:
            payload = response.json()
        except ValueError:
            self.last_error = f"{label}: invalid JSON"
            return None
        provider_error = self._payload_error(payload)
        if provider_error:
            self.last_error = f"{label}: {provider_error}"
            return None
        data = payload.get('response') if isinstance(payload, dict) else None
        if not isinstance(data, expected_type):
            self.last_error = f"{label}: invalid response payload"
            return None
        if expected_type is list and any(not isinstance(item, dict) for item in data):
            self.last_error = f"{label}: invalid response entries"
            return None
        return data

    @classmethod
    def _completed_fixture_values(cls, fixture) -> Optional[tuple[int, int, int, int]]:
        if not isinstance(fixture, dict):
            return None
        teams = fixture.get('teams')
        goals = fixture.get('goals')
        if not isinstance(teams, dict) or not isinstance(goals, dict):
            return None
        home = teams.get('home')
        away = teams.get('away')
        if not isinstance(home, dict) or not isinstance(away, dict):
            return None
        home_id = cls._positive_integer(home.get('id'))
        away_id = cls._positive_integer(away.get('id'))
        home_goals = cls._nonnegative_integer(goals.get('home'), maximum=30)
        away_goals = cls._nonnegative_integer(goals.get('away'), maximum=30)
        if (
            home_id is None
            or away_id is None
            or home_id == away_id
            or home_goals is None
            or away_goals is None
        ):
            return None
        return home_id, away_id, home_goals, away_goals
    
    def _rate_limit(self):
        """Ensure minimum time between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _get(self, url: str, **kwargs):
        return api_football_get(
            url,
            priority=self.budget_priority,
            **kwargs,
        )

    def _request(self, endpoint: str, params: Dict) -> Dict:
        """Rate-limitter Roh-GET: volles Provider-Payload-Dict ({} bei Fehler).

        Für Settlement-Pfade (z. B. redcard_signal_log), die das Payload
        selbst interpretieren. Fehler landen in self.last_error.
        """
        self.last_error = None
        self._rate_limit()
        try:
            response = self._get(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                params=params,
                timeout=15,
            )
        except Exception as e:
            self.last_error = f"{endpoint}: {type(e).__name__}"
            return {}
        if response.status_code != 200:
            self.last_error = f"{endpoint}: HTTP {response.status_code}"
            return {}
        try:
            payload = response.json()
        except ValueError:
            self.last_error = f"{endpoint}: invalid JSON"
            return {}
        provider_error = self._payload_error(payload)
        if provider_error:
            self.last_error = f"{endpoint}: {provider_error}"
            return {}
        return payload if isinstance(payload, dict) else {}
    
    def get_upcoming_fixtures(
        self,
        league_code: str,
        days_ahead: int = 7,
        *,
        start_date: Optional[date] = None,
    ) -> List[Dict]:
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
        if (
            not isinstance(league_code, str)
            or not league_code.strip()
            or isinstance(days_ahead, bool)
            or not isinstance(days_ahead, int)
            or not 1 <= days_ahead <= 30
            or (
                start_date is not None
                and (
                    isinstance(start_date, datetime)
                    or not isinstance(start_date, date)
                )
            )
        ):
            self.last_error = "upcoming fixtures: invalid request parameters"
            return []
        league_id = self.league_ids.get(league_code)
        if not league_id:
            print(f"WARNING: Unknown league code: {league_code}")
            return []
        
        self._rate_limit()
        
        # Calculate date range
        first_day = start_date or datetime.now(ZURICH_TIMEZONE).date()
        end_date = first_day + timedelta(days=days_ahead)
        
        try:
            response = self._get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': current_season_start_year(league_code, first_day),
                    'from': first_day.isoformat(),
                    'to': end_date.strftime('%Y-%m-%d'),
                    'status': 'NS'  # Not Started
                },
                timeout=15
            )
            
            fixtures = self._response_data(
                response,
                f"fixtures {league_code}",
                list,
            )
            if fixtures is not None:
                
                print(f"Found {len(fixtures)} upcoming fixtures for {league_code}")
                
                result = []
                for fixture in fixtures:
                    try:
                        fixture_id = self._positive_integer(fixture['fixture']['id'])
                        home_team_id = self._positive_integer(fixture['teams']['home']['id'])
                        away_team_id = self._positive_integer(fixture['teams']['away']['id'])
                        home_team = str(fixture['teams']['home']['name'] or '').strip()
                        away_team = str(fixture['teams']['away']['name'] or '').strip()
                        fixture_date = str(fixture['fixture']['date'] or '').strip()
                        kickoff = datetime.fromisoformat(fixture_date.replace('Z', '+00:00'))
                        fixture_league_id = self._positive_integer(fixture['league']['id'])
                        league_name = fixture['league']['name']
                        if (
                            fixture_id is None
                            or home_team_id is None
                            or away_team_id is None
                            or home_team_id == away_team_id
                            or not home_team
                            or not away_team
                            or home_team == away_team
                            or kickoff.tzinfo is None
                            or kickoff.astimezone(timezone.utc) <= datetime.now(timezone.utc)
                            or fixture_league_id != league_id
                            or not isinstance(league_name, str)
                            or not league_name.strip()
                        ):
                            continue
                        result.append({
                            'fixture_id': fixture_id,
                            'date': fixture_date,
                            'home_team': home_team,
                            'away_team': away_team,
                            'home_team_id': home_team_id,
                            'away_team_id': away_team_id,
                            'league_code': league_code,
                            'league_name': league_name.strip()
                        })
                    except (KeyError, TypeError, ValueError, AttributeError) as e:
                        print(f"WARNING: Missing data in fixture: {e}")
                        continue
                
                return result
            print(f"ERROR: {self.last_error or 'fixture request failed'}")
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
            response = self._get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            matches = self._response_data(response, "live fixtures", list)
            return matches if matches is not None else []
                
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
        self.last_error = None
        fixture_id = self._positive_integer(fixture_id)
        home_team_id = self._positive_integer(home_team_id)
        away_team_id = self._positive_integer(away_team_id)
        if (
            fixture_id is None
            or home_team_id is None
            or away_team_id is None
            or home_team_id == away_team_id
        ):
            self.last_error = "fixture statistics: invalid identifiers"
            return None
        self._rate_limit()
        
        try:
            response = self._get(
                f"{self.base_url}/fixtures/statistics",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            stats_list = self._response_data(
                response,
                f"fixture statistics {fixture_id}",
                list,
            )
            if stats_list is not None:
                if len(stats_list) >= 2:
                    stats_by_team = {}
                    for item in stats_list:
                        if not isinstance(item, dict):
                            continue
                        team = item.get('team')
                        statistics = item.get('statistics')
                        if not isinstance(team, dict) or not isinstance(statistics, list):
                            continue
                        team_id = self._positive_integer(team.get('id'))
                        if team_id is not None:
                            stats_by_team[team_id] = statistics
                    home_stats = stats_by_team.get(home_team_id)
                    away_stats = stats_by_team.get(away_team_id)
                    if home_stats is None or away_stats is None:
                        return None

                    def get_stat(stats, stat_type):
                        for s in stats:
                            if not isinstance(s, dict):
                                continue
                            if s.get('type') == stat_type:
                                val = s.get('value')
                                if stat_type == 'Ball Possession':
                                    return self._finite_nonnegative(val, maximum=100.0)
                                if stat_type == 'expected_goals':
                                    # Provider delivers xG as decimal text such as
                                    # "1.34"; an integer-only parse would silently
                                    # disable every live-xG data-quality tier.
                                    return self._finite_nonnegative(val, maximum=20.0)
                                if stat_type == 'Red Cards' and val is None:
                                    # API-Football includes the field with JSON null
                                    # when the verified count is zero. A missing field
                                    # still falls through to None below.
                                    return 0
                                return self._nonnegative_integer(val, maximum=5000)
                        return None

                    result = {
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
                    return result
                self.last_error = f"fixture statistics {fixture_id}: both teams are required"
            
            return None
            
        except Exception as e:
            self.last_error = f"fixture statistics {fixture_id}: {type(e).__name__}"
            print(f"WARNING: Stats error: {e}")
            return None
    
    def get_team_statistics(self, team_id: int, league_id: int,
                            season: Optional[int] = None) -> Optional[Dict]:
        """Get team statistics from API-Football"""
        self.last_error = None
        team_id = self._positive_integer(team_id)
        league_id = self._positive_integer(league_id)
        if team_id is None or league_id is None:
            self.last_error = "team statistics: invalid identifiers"
            return None
        season = season if season is not None else current_season_start_year_for_id(league_id)
        season = self._nonnegative_integer(season)
        if season is None or not 1900 <= season <= 2100:
            self.last_error = "team statistics: invalid season"
            return None
        self._rate_limit()
        
        try:
            response = self._get(
                f"{self.base_url}/teams/statistics",
                headers=self.headers,
                params={
                    'team': team_id,
                    'league': league_id,
                    'season': season
                },
                timeout=15
            )
            
            stats = self._response_data(
                response,
                f"team statistics {team_id}",
                dict,
            )
            if stats is not None:
                if stats:
                    
                    print(f"API returned team: {stats.get('team')}")
                    
                    # Extract relevant statistics
                    fixtures = stats.get('fixtures', {})
                    goals = stats.get('goals', {})
                    
                    played = fixtures.get('played', {}) if isinstance(fixtures, dict) else {}
                    if not isinstance(played, dict) or not isinstance(goals, dict):
                        self.last_error = f"team statistics {team_id}: invalid aggregates"
                        return None
                    played_home = self._nonnegative_integer(played.get('home'), maximum=200)
                    played_away = self._nonnegative_integer(played.get('away'), maximum=200)
                    clean_sheet = stats.get('clean_sheet', {})
                    failed_to_score = stats.get('failed_to_score', {})
                    if not isinstance(clean_sheet, dict) or not isinstance(failed_to_score, dict):
                        self.last_error = f"team statistics {team_id}: invalid count aggregates"
                        return None
                    clean_sheets_home = self._nonnegative_integer(clean_sheet.get('home'), maximum=200)
                    clean_sheets_away = self._nonnegative_integer(clean_sheet.get('away'), maximum=200)
                    failed_to_score_home = self._nonnegative_integer(failed_to_score.get('home'), maximum=200)
                    failed_to_score_away = self._nonnegative_integer(failed_to_score.get('away'), maximum=200)
                    aggregate_counts = (
                        played_home,
                        played_away,
                        clean_sheets_home,
                        clean_sheets_away,
                        failed_to_score_home,
                        failed_to_score_away,
                    )
                    if any(value is None for value in aggregate_counts):
                        self.last_error = f"team statistics {team_id}: invalid count aggregates"
                        return None
                    if (
                        clean_sheets_home > played_home
                        or clean_sheets_away > played_away
                        or failed_to_score_home > played_home
                        or failed_to_score_away > played_away
                    ):
                        self.last_error = f"team statistics {team_id}: inconsistent count aggregates"
                        return None
                    btts_rates = self._get_btts_rates(team_id, league_id, season)

                    scored_home = self._finite_nonnegative(
                        goals.get('for', {}).get('average', {}).get('home'),
                        maximum=20.0,
                    )
                    scored_away = self._finite_nonnegative(
                        goals.get('for', {}).get('average', {}).get('away'),
                        maximum=20.0,
                    )
                    conceded_home = self._finite_nonnegative(
                        goals.get('against', {}).get('average', {}).get('home'),
                        maximum=20.0,
                    )
                    conceded_away = self._finite_nonnegative(
                        goals.get('against', {}).get('average', {}).get('away'),
                        maximum=20.0,
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
                self.last_error = f"team statistics {team_id}: empty response"
            
            return None
            
        except Exception as e:
            self.last_error = f"team statistics {team_id}: {type(e).__name__}"
            print(f"WARNING: Team stats error: {e}")
            return None

    def _get_btts_rates(self, team_id: int, league_id: int, season: int,
                        limit: int = 20) -> Dict:
        """Calculate BTTS rates from finished fixtures without aggregate overlap bias."""
        empty = {
            'home_rate': None,
            'away_rate': None,
            'total_rate': None,
            'home_matches': 0,
            'away_matches': 0,
            'total_matches': 0,
        }
        if (
            self._positive_integer(team_id) is None
            or self._positive_integer(league_id) is None
            or self._nonnegative_integer(season) is None
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            self.last_error = "BTTS history: invalid request parameters"
            return empty
        self._rate_limit()
        try:
            response = self._get(
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
            fixtures = self._response_data(
                response,
                f"BTTS history {team_id}",
                list,
            )
            if fixtures is None:
                return empty
        except Exception as exc:
            self.last_error = f"BTTS history {team_id}: {type(exc).__name__}"
            return empty

        counts = {'home': [0, 0], 'away': [0, 0]}
        for fixture in fixtures:
            values = self._completed_fixture_values(fixture)
            if values is None or team_id not in values[:2]:
                self.last_error = f"BTTS history {team_id}: invalid fixture data"
                return empty
            home_id, away_id, home_score, away_score = values
            venue = 'home' if home_id == team_id else 'away'
            counts[venue][1] += 1
            if home_score > 0 and away_score > 0:
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
    
    def get_fixture_events(self, fixture_id: int) -> List[Dict]:
        """Get timeline events (goals, cards, subs) for one fixture."""
        self.last_error = None
        fixture_id = self._positive_integer(fixture_id)
        if fixture_id is None:
            self.last_error = "fixture events: invalid fixture id"
            return []
        self._rate_limit()
        try:
            response = self._get(
                f"{self.base_url}/fixtures/events",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15,
            )
            data = self._response_data(
                response,
                f"fixture events {fixture_id}",
                list,
            )
            return data if data is not None else []
        except Exception as e:
            self.last_error = f"fixture events {fixture_id}: {type(e).__name__}"
            print(f"WARNING: Fixture events error: {e}")
            return []

    def get_team_leagues(self, team_id: int) -> List[Dict]:
        """Get all leagues a team participates in (used for domestic-league fallback)."""
        self.last_error = None
        team_id = self._positive_integer(team_id)
        if team_id is None:
            self.last_error = "team leagues: invalid team id"
            return []
        self._rate_limit()
        try:
            response = self._get(
                f"{self.base_url}/leagues",
                headers=self.headers,
                params={'team': team_id},
                timeout=15,
            )
            data = self._response_data(
                response,
                f"team leagues {team_id}",
                list,
            )
            return data if data is not None else []
        except Exception as e:
            self.last_error = f"team leagues {team_id}: {type(e).__name__}"
            print(f"WARNING: Team leagues error: {e}")
            return []

    def get_h2h(self, team1_id: int, team2_id: int, last_n: int = 10) -> List[Dict]:
        """Get head-to-head matches"""
        self.last_error = None
        team1_id = self._positive_integer(team1_id)
        team2_id = self._positive_integer(team2_id)
        if (
            team1_id is None
            or team2_id is None
            or team1_id == team2_id
            or isinstance(last_n, bool)
            or not isinstance(last_n, int)
            or not 1 <= last_n <= 100
        ):
            self.last_error = "head-to-head: invalid request parameters"
            return []
        self._rate_limit()
        
        try:
            response = self._get(
                f"{self.base_url}/fixtures/headtohead",
                headers=self.headers,
                params={
                    'h2h': f'{team1_id}-{team2_id}',
                    'last': last_n
                },
                timeout=15
            )
            
            matches = self._response_data(response, "head-to-head", list)
            if matches is None:
                return []
            for match in matches:
                values = self._completed_fixture_values(match)
                if values is None or set(values[:2]) != {team1_id, team2_id}:
                    self.last_error = "head-to-head: invalid fixture data"
                    return []
            return matches
            
        except Exception as e:
            self.last_error = f"head-to-head: {type(e).__name__}"
            print(f"WARNING: H2H error: {e}")
            return []
    
    def get_last_matches(self, team_id: int, league_id: int, n: int = 5) -> List[Dict]:
        """Get last N matches for a team"""
        self.last_error = None
        team_id = self._positive_integer(team_id)
        league_id = self._positive_integer(league_id)
        if (
            team_id is None
            or league_id is None
            or isinstance(n, bool)
            or not isinstance(n, int)
            or not 1 <= n <= 100
        ):
            self.last_error = "last matches: invalid request parameters"
            return []
        self._rate_limit()
        
        try:
            response = self._get(
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
            
            matches = self._response_data(response, f"last matches {team_id}", list)
            if matches is None:
                return []
            for match in matches:
                values = self._completed_fixture_values(match)
                league = match.get('league')
                match_league_id = (
                    self._positive_integer(league.get('id'))
                    if isinstance(league, dict)
                    else None
                )
                if (
                    values is None
                    or team_id not in values[:2]
                    or match_league_id != league_id
                ):
                    self.last_error = f"last matches {team_id}: invalid fixture data"
                    return []
            return matches
            
        except Exception as e:
            self.last_error = f"last matches {team_id}: {type(e).__name__}"
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
        self.last_error = None
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
        team_id = self._positive_integer(team_id)
        if (
            team_id is None
            or isinstance(n, bool)
            or not isinstance(n, int)
            or not 1 <= n <= 100
        ):
            self.last_error = "team form: invalid request parameters"
            return empty
        if league_id is not None:
            league_id = self._positive_integer(league_id)
            if league_id is None:
                self.last_error = "team form: invalid league identifier"
                return empty
            season = season if season is not None else current_season_start_year_for_id(
                league_id
            )
            season = self._nonnegative_integer(season)
            if season is None or not 1900 <= season <= 2100:
                self.last_error = "team form: invalid season"
                return empty
        self._rate_limit()
        
        try:
            params = {
                'team': team_id,
                'last': n,
                'status': 'FT',
            }
            if league_id is not None:
                params['league'] = league_id
                params['season'] = season
            response = self._get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params=params,
                timeout=15
            )
            
            matches = self._response_data(
                response,
                f"team form {team_id}",
                list,
            )
            if matches is not None:
                
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
                    values = self._completed_fixture_values(match)
                    if values is None or team_id not in values[:2]:
                        self.last_error = f"team form {team_id}: invalid fixture data"
                        return empty
                    home_id, away_id, home_goals, away_goals = values
                        
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
            self.last_error = f"team form {team_id}: {type(e).__name__}"
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
