"""
BASKETBALL & NHL LIVE OBSERVATION SCANNER
API observations are real; no betting probability is inferred from score alone.

Features:
- Real NBA API Integration (stats.nba.com)
- Real Euroleague API Integration
- Real NHL API Integration (api-web.nhle.com)
- Live scores and clock-aware straight-line scoring projections

Author: Miroslav
Date: January 2026
"""

import streamlit as st
import requests
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import time
import re
import math

logger = logging.getLogger(__name__)
SEARCH_TIMEZONE = ZoneInfo("Europe/Zurich")

class BasketballScanner:
    """
    Real Basketball + NHL Scanner - NBA + Euroleague + NHL
    Uses actual APIs and real-time data
    """
    
    def __init__(self):
        self.errors: Dict[str, str] = {}
        # NBA Stats API
        self.nba_api_base = "https://stats.nba.com/stats"
        self.nba_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'x-nba-stats-origin': 'stats',
            'x-nba-stats-token': 'true',
            'Referer': 'https://stats.nba.com/',
        }
        
        # Euroleague API
        self.euroleague_api_base = "https://live.euroleague.net/api"
        self.euroleague_games_base = "https://api-live.euroleague.net/v2"
        
        # Alternative: NBA.com live scoreboard
        self.nba_live_url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
        self.espn_nba_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        
        # NHL API
        self.nhl_api_url = "https://api-web.nhle.com/v1/scoreboard/now"
        self.nhl_schedule_base = "https://api-web.nhle.com/v1/schedule"

    @staticmethod
    def _date_window(start_date: date, end_date: date) -> tuple[date, date]:
        if (
            isinstance(start_date, datetime)
            or not isinstance(start_date, date)
            or isinstance(end_date, datetime)
            or not isinstance(end_date, date)
            or not 0 <= (end_date - start_date).days <= 14
        ):
            raise ValueError("Date window must span zero to fourteen days")
        return start_date, end_date

    @staticmethod
    def _localized_text(value) -> Optional[str]:
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, dict):
            text = str(value.get('default') or '').strip()
        else:
            text = ''
        return text or None

    @staticmethod
    def _event_start(value) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def get_upcoming_games(
        self,
        league: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        """Upcoming NBA/EuroLeague fixtures in an inclusive date window."""
        self._date_window(start_date, end_date)
        games = []
        if league in {"NBA", "All"}:
            games.extend(
                self._get_espn_upcoming_basketball_games(
                    self.espn_nba_url,
                    "NBA",
                    start_date,
                    end_date,
                )
            )
        if league in {"Euroleague", "All"}:
            games.extend(
                self._get_upcoming_euroleague_games(
                    start_date,
                    end_date,
                )
            )
        return sorted(games, key=lambda item: item.get('start_time') or '')

    def get_completed_games(self, league: str, start_date: date, end_date: date, *, as_of=None) -> List[Dict]:
        """Observed final NBA/EuroLeague results, with a bounded persistent cache."""
        from scanners.completed_history import completed_basketball

        return completed_basketball(self, league, start_date, end_date, as_of=as_of)

    def get_completed_nhl_games(self, start_date: date, end_date: date, *, as_of=None) -> List[Dict]:
        """Observed final NHL results including overtime/shootout winners."""
        from scanners.completed_history import completed_nhl

        return completed_nhl(self, start_date, end_date, as_of=as_of)

    def _get_upcoming_euroleague_games(
        self,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        """Upcoming EuroLeague fixtures from the official season schedule."""
        season_codes = {
            self._euroleague_season_code(
                datetime.combine(day, datetime.min.time(), tzinfo=SEARCH_TIMEZONE)
            )
            for day in (start_date, end_date)
        }
        games = []
        seen = set()
        errors = []
        for season_code in sorted(season_codes):
            try:
                response = requests.get(
                    (
                        f"{self.euroleague_games_base}/competitions/E/seasons/"
                        f"{season_code}/games"
                    ),
                    params={'limit': 500},
                    timeout=15,
                )
                if response.status_code != 200:
                    errors.append(f"{season_code}: HTTP {response.status_code}")
                    continue
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{season_code}: {type(exc).__name__}")
                continue
            rows = payload.get('data', []) if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                errors.append(f"{season_code}: invalid payload")
                continue
            for row in rows:
                if not isinstance(row, dict) or row.get('played') is True:
                    continue
                start = self._event_start(row.get('utcDate'))
                if (
                    start is None
                    or not start_date
                    <= start.astimezone(SEARCH_TIMEZONE).date()
                    <= end_date
                ):
                    continue
                local = row.get('local', {})
                road = row.get('road', {})
                local_club = local.get('club', {}) if isinstance(local, dict) else {}
                road_club = road.get('club', {}) if isinstance(road, dict) else {}
                home_team = (
                    self._team_code(local_club, 'code')
                    or self._team_code(local_club, 'abbreviatedName')
                )
                away_team = (
                    self._team_code(road_club, 'code')
                    or self._team_code(road_club, 'abbreviatedName')
                )
                game_id = row.get('id') or row.get('identifier') or row.get('gameCode')
                if (
                    not home_team
                    or not away_team
                    or home_team == away_team
                    or isinstance(game_id, bool)
                    or not isinstance(game_id, (int, str))
                    or not str(game_id).strip()
                    or str(game_id) in seen
                ):
                    continue
                seen.add(str(game_id))
                venue = row.get('venue', {})
                venue_name = (
                    self._localized_text(venue.get('name'))
                    if isinstance(venue, dict)
                    else self._localized_text(venue)
                )
                games.append({
                    'league': 'Euroleague',
                    'game_id': game_id,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_team_id': self._team_code(local_club, 'code'),
                    'away_team_id': self._team_code(road_club, 'code'),
                    'status': 'upcoming',
                    'start_time': start.isoformat(),
                    'venue': venue_name or 'Unknown',
                    'source': 'EuroLeague',
                })
        if errors:
            self.errors['euroleague_schedule'] = '; '.join(errors[:4])
        else:
            self.errors.pop('euroleague_schedule', None)
        return games

    def _get_espn_upcoming_basketball_games(
        self,
        url: str,
        league: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        error_key = f"{league.casefold()}_schedule"
        errors = []
        games = []
        seen = set()
        total_days = (end_date - start_date).days + 1
        for offset in range(total_days):
            target_date = start_date + timedelta(days=offset)
            try:
                response = requests.get(
                    url,
                    headers={
                        'User-Agent': self.nba_headers['User-Agent'],
                        'Accept': 'application/json',
                    },
                    params={
                        'dates': target_date.strftime('%Y%m%d'),
                        'limit': 100,
                    },
                    timeout=10,
                )
                if response.status_code != 200:
                    errors.append(f"{target_date}: HTTP {response.status_code}")
                    continue
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{target_date}: {type(exc).__name__}")
                continue
            events = payload.get('events', []) if isinstance(payload, dict) else None
            if not isinstance(events, list):
                errors.append(f"{target_date}: invalid payload")
                continue
            for event in events:
                competitions = event.get('competitions', []) if isinstance(event, dict) else []
                if not isinstance(competitions, list):
                    continue
                for competition in competitions:
                    parsed = self._parse_espn_upcoming_basketball_game(
                        event,
                        competition,
                        league,
                    )
                    if not parsed or parsed['game_id'] in seen:
                        continue
                    start = self._event_start(parsed.get('start_time'))
                    if (
                        start is None
                        or not start_date
                        <= start.astimezone(SEARCH_TIMEZONE).date()
                        <= end_date
                    ):
                        continue
                    seen.add(parsed['game_id'])
                    games.append(parsed)
        if errors:
            self.errors[error_key] = '; '.join(errors[:4])
        else:
            self.errors.pop(error_key, None)
        return games

    def _parse_espn_upcoming_basketball_game(
        self,
        event: Dict,
        competition: Dict,
        league: str,
    ) -> Optional[Dict]:
        if not isinstance(event, dict) or not isinstance(competition, dict):
            return None
        status = competition.get('status', {})
        status_type = status.get('type', {}) if isinstance(status, dict) else {}
        if not isinstance(status_type, dict) or status_type.get('state') != 'pre':
            return None
        competitors = competition.get('competitors', [])
        if not isinstance(competitors, list) or len(competitors) != 2:
            return None
        sides = {
            item.get('homeAway'): item
            for item in competitors
            if isinstance(item, dict) and item.get('homeAway') in {'home', 'away'}
        }
        home = sides.get('home')
        away = sides.get('away')
        if not isinstance(home, dict) or not isinstance(away, dict):
            return None
        home_data = home.get('team', {})
        away_data = away.get('team', {})
        home_team = (
            self._team_code(home_data, 'abbreviation')
            or self._team_code(home_data, 'displayName')
        )
        away_team = (
            self._team_code(away_data, 'abbreviation')
            or self._team_code(away_data, 'displayName')
        )
        game_id = competition.get('id') or event.get('id')
        start = competition.get('date') or event.get('date')
        if (
            not home_team
            or not away_team
            or home_team == away_team
            or isinstance(game_id, bool)
            or not isinstance(game_id, (int, str))
            or not str(game_id).strip()
            or self._event_start(start) is None
        ):
            return None
        venue = competition.get('venue', {})
        return {
            'league': league,
            'game_id': game_id,
            'home_team': home_team,
            'away_team': away_team,
            'home_team_id': self._team_code(home_data, 'id'),
            'away_team_id': self._team_code(away_data, 'id'),
            'status': 'upcoming',
            'start_time': start,
            'venue': (
                str(venue.get('fullName') or 'Unknown').strip()
                if isinstance(venue, dict)
                else 'Unknown'
            ) or 'Unknown',
            'source': 'ESPN',
        }

    def get_upcoming_nhl_games(
        self,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        """Upcoming NHL fixtures using the league's official weekly schedule."""
        self._date_window(start_date, end_date)
        self.errors.pop('nhl_schedule', None)
        cursor = start_date.isoformat()
        visited = set()
        games = []
        seen = set()
        errors = []
        for _ in range(4):
            if cursor in visited:
                break
            visited.add(cursor)
            try:
                response = requests.get(
                    f"{self.nhl_schedule_base}/{cursor}",
                    headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                    timeout=10,
                )
                if response.status_code != 200:
                    errors.append(f"{cursor}: HTTP {response.status_code}")
                    break
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{cursor}: {type(exc).__name__}")
                break
            weeks = payload.get('gameWeek', []) if isinstance(payload, dict) else None
            if not isinstance(weeks, list):
                errors.append(f"{cursor}: invalid payload")
                break
            for day_group in weeks:
                day_games = day_group.get('games', []) if isinstance(day_group, dict) else []
                if not isinstance(day_games, list):
                    continue
                for game in day_games:
                    if not isinstance(game, dict) or game.get('gameState') not in {'FUT', 'PRE'}:
                        continue
                    start = self._event_start(game.get('startTimeUTC'))
                    home = game.get('homeTeam', {})
                    away = game.get('awayTeam', {})
                    game_id = game.get('id')
                    home_team = (
                        self._localized_text(home.get('abbrev'))
                        if isinstance(home, dict)
                        else None
                    )
                    away_team = (
                        self._localized_text(away.get('abbrev'))
                        if isinstance(away, dict)
                        else None
                    )
                    if (
                        start is None
                        or not start_date
                        <= start.astimezone(SEARCH_TIMEZONE).date()
                        <= end_date
                        or not home_team
                        or not away_team
                        or home_team == away_team
                        or not isinstance(game_id, int)
                        or isinstance(game_id, bool)
                        or game_id <= 0
                        or game_id in seen
                    ):
                        continue
                    seen.add(game_id)
                    venue = game.get('venue', {})
                    games.append({
                        'league': 'NHL',
                        'game_id': game_id,
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_team_id': self._team_code(home, 'id'),
                        'away_team_id': self._team_code(away, 'id'),
                        'status': 'upcoming',
                        'start_time': start.isoformat(),
                        'venue': self._localized_text(venue) or 'Unknown',
                        'game_type': game.get('gameType'),
                        'season': game.get('season'),
                        'neutral_site': game.get('neutralSite') is True,
                        'source': 'NHL',
                    })
            next_cursor = payload.get('nextStartDate') if isinstance(payload, dict) else None
            if not isinstance(next_cursor, str):
                break
            try:
                next_date = date.fromisoformat(next_cursor)
            except ValueError:
                break
            if next_date > end_date:
                break
            cursor = next_cursor
        if errors:
            self.errors['nhl_schedule'] = '; '.join(errors[:4])
        return sorted(games, key=lambda item: item.get('start_time') or '')

    @staticmethod
    def _whole_score(value) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, str):
            text = value.strip()
            return int(text) if text.isdigit() else None
        if not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number) or number < 0 or not number.is_integer():
            return None
        return int(number)

    @staticmethod
    def _team_code(team: Dict, key: str) -> Optional[str]:
        if not isinstance(team, dict):
            return None
        value = str(team.get(key) or '').strip()
        return value or None
    
    def get_live_nhl_games(self) -> List[Dict]:
        """Get real-time NHL games"""
        self.errors.pop('nhl', None)
        try:
            response = requests.get(
                self.nhl_api_url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, dict):
                    self.errors['nhl'] = 'Invalid provider payload'
                    logger.warning("NHL live API returned an invalid payload")
                    return []
                date_groups = data.get('gamesByDate', [])
                if not isinstance(date_groups, list):
                    self.errors['nhl'] = 'Invalid games list'
                    return []
                live_games = []
                
                # NHL API returns games grouped by date
                for date_group in date_groups:
                    games = date_group.get('games', []) if isinstance(date_group, dict) else []
                    if not isinstance(games, list):
                        continue
                    for game in games:
                        if not isinstance(game, dict):
                            continue
                        # LIVE, CRIT (critical/close game), or in progress
                        if game.get('gameState') in ['LIVE', 'CRIT']:
                            parsed = self._parse_nhl_game(game)
                            if parsed:
                                live_games.append(parsed)
                
                return live_games
            logger.warning("NHL live API returned HTTP %s", response.status_code)
            self.errors['nhl'] = f"HTTP {response.status_code}"
            return []
                
        except (requests.RequestException, ValueError) as exc:
            self.errors['nhl'] = type(exc).__name__
            logger.warning("NHL live data request failed: %s", type(exc).__name__)
            return []
    
    def _parse_nhl_game(self, game: Dict) -> Optional[Dict]:
        """Parse NHL game data into our format"""
        if not isinstance(game, dict):
            return None
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})
        if not isinstance(home, dict) or not isinstance(away, dict):
            return None
        home_score = self._whole_score(home.get('score'))
        away_score = self._whole_score(away.get('score'))
        home_team = self._team_code(home, 'abbrev')
        away_team = self._team_code(away, 'abbrev')
        game_id = game.get('id')
        period = game.get('period')
        clock = game.get('clock')
        if (
            home_score is None
            or away_score is None
            or not home_team
            or not away_team
            or home_team == away_team
            or not isinstance(game_id, int)
            or isinstance(game_id, bool)
            or game_id <= 0
            or isinstance(period, bool)
            or not isinstance(period, int)
            or period < 1
            or not isinstance(clock, dict)
            or not isinstance(clock.get('timeRemaining'), str)
        ):
            return None
        
        return {
            'league': 'NHL',
            'game_id': game_id,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock['timeRemaining'],
            'game_status': game.get('gameState', 'Live'),
            'venue': (
                str(game.get('venue', {}).get('default') or 'Unknown').strip()
                if isinstance(game.get('venue'), dict)
                else 'Unknown'
            ) or 'Unknown',
            'source': 'NHL',
        }
    
    def analyze_nhl_game(self, game: Dict) -> Optional[Dict]:
        """No NHL signal is emitted without team-strength and goalie inputs."""
        return None
        
    def get_live_nba_games(self) -> List[Dict]:
        """
        Get real-time NBA games
        Uses NBA.com live scoreboard API
        """
        self.errors.pop('nba', None)
        primary_error = None
        try:
            response = requests.get(
                self.nba_live_url,
                headers=self.nba_headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                scoreboard = data.get('scoreboard', {}) if isinstance(data, dict) else None
                games = scoreboard.get('games', []) if isinstance(scoreboard, dict) else None
                if isinstance(games, list):
                    live_games = []
                    for game in games:
                        if isinstance(game, dict) and game.get('gameStatus') == 2:
                            parsed = self._parse_nba_game(game)
                            if parsed:
                                parsed['source'] = 'NBA.com'
                                live_games.append(parsed)
                    self.errors.pop('nba', None)
                    return live_games
                primary_error = 'Invalid provider payload'
            else:
                primary_error = f"NBA.com HTTP {response.status_code}"
        except (requests.RequestException, ValueError) as exc:
            primary_error = f"NBA.com {type(exc).__name__}"

        fallback = self._get_live_nba_games_espn()
        if fallback is not None:
            self.errors.pop('nba', None)
            return fallback
        self.errors['nba'] = f"{primary_error or 'NBA.com unavailable'}; ESPN unavailable"
        logger.warning("NBA live providers did not return a usable response")
        return []

    def _get_live_nba_games_espn(self) -> Optional[List[Dict]]:
        """Use ESPN's public scoreboard when NBA.com's CDN blocks the host."""
        try:
            response = requests.get(
                self.espn_nba_url,
                headers={'User-Agent': self.nba_headers['User-Agent'], 'Accept': 'application/json'},
                timeout=10,
            )
            if response.status_code != 200:
                return None
            data = response.json()
            events = data.get('events', []) if isinstance(data, dict) else None
            if not isinstance(events, list):
                return None
            live_games = []
            for event in events:
                if not isinstance(event, dict):
                    continue
                competitions = event.get('competitions', [])
                if not isinstance(competitions, list):
                    continue
                for competition in competitions:
                    parsed = self._parse_espn_nba_game(event, competition)
                    if parsed:
                        live_games.append(parsed)
            return live_games
        except (requests.RequestException, ValueError):
            return None

    def _parse_espn_nba_game(self, event: Dict, competition: Dict) -> Optional[Dict]:
        if not isinstance(event, dict) or not isinstance(competition, dict):
            return None
        status = competition.get('status', {})
        status_type = status.get('type', {}) if isinstance(status, dict) else {}
        if not isinstance(status_type, dict) or status_type.get('state') != 'in':
            return None
        competitors = competition.get('competitors', [])
        if not isinstance(competitors, list) or len(competitors) != 2:
            return None
        by_side = {
            item.get('homeAway'): item
            for item in competitors
            if isinstance(item, dict) and item.get('homeAway') in {'home', 'away'}
        }
        home = by_side.get('home')
        away = by_side.get('away')
        if not isinstance(home, dict) or not isinstance(away, dict):
            return None
        home_team_data = home.get('team', {})
        away_team_data = away.get('team', {})
        home_team = self._team_code(home_team_data, 'abbreviation')
        away_team = self._team_code(away_team_data, 'abbreviation')
        home_score = self._whole_score(home.get('score'))
        away_score = self._whole_score(away.get('score'))
        game_id = competition.get('id') or event.get('id')
        period = status.get('period')
        clock = status.get('displayClock')
        if (
            not home_team
            or not away_team
            or home_team == away_team
            or home_score is None
            or away_score is None
            or isinstance(game_id, bool)
            or not isinstance(game_id, (int, str))
            or not str(game_id).strip()
            or isinstance(period, bool)
            or not isinstance(period, int)
            or period < 1
            or not isinstance(clock, str)
        ):
            return None
        venue = competition.get('venue', {})
        return {
            'league': 'NBA',
            'game_id': game_id,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock,
            'game_status': str(status_type.get('detail') or 'Live').strip() or 'Live',
            'home_stats': {},
            'away_stats': {},
            'venue': (
                str(venue.get('fullName') or 'Unknown').strip()
                if isinstance(venue, dict)
                else 'Unknown'
            ) or 'Unknown',
            'source': 'ESPN',
        }
    
    def _parse_nba_game(self, game: Dict) -> Optional[Dict]:
        """Parse NBA game data into our format"""
        if not isinstance(game, dict):
            return None
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})
        if not isinstance(home, dict) or not isinstance(away, dict):
            return None
        home_score = self._whole_score(home.get('score'))
        away_score = self._whole_score(away.get('score'))
        home_team = self._team_code(home, 'teamTricode')
        away_team = self._team_code(away, 'teamTricode')
        game_id = game.get('gameId')
        period = game.get('period')
        clock = game.get('gameClock')
        if (
            home_score is None
            or away_score is None
            or not home_team
            or not away_team
            or home_team == away_team
            or isinstance(game_id, bool)
            or not isinstance(game_id, (int, str))
            or not str(game_id).strip()
            or isinstance(period, bool)
            or not isinstance(period, int)
            or period < 1
            or not isinstance(clock, str)
        ):
            return None
        
        return {
            'league': 'NBA',
            'game_id': game_id,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock,
            'game_status': game.get('gameStatusText', 'Live'),
            'home_stats': home.get('statistics') if isinstance(home.get('statistics'), dict) else {},
            'away_stats': away.get('statistics') if isinstance(away.get('statistics'), dict) else {},
        }
    
    def get_live_euroleague_games(self) -> List[Dict]:
        """
        Get real-time Euroleague games
        """
        self.errors.pop('euroleague', None)
        season_code = self._euroleague_season_code()
        try:
            games_url = (
                f"{self.euroleague_games_base}/competitions/E/seasons/"
                f"{season_code}/games"
            )
            response = requests.get(games_url, params={'limit': 500}, timeout=15)
            if response.status_code != 200:
                self.errors['euroleague'] = f"Schedule HTTP {response.status_code}"
                return []
            payload = response.json()
            games = payload.get('data', []) if isinstance(payload, dict) else None
            if not isinstance(games, list):
                self.errors['euroleague'] = 'Invalid schedule payload'
                return []

            candidates = self._nearby_euroleague_games(games)
            live_games = []
            header_errors = []
            for game in candidates[:10]:
                game_code = game.get('gameCode')
                if (
                    isinstance(game_code, bool)
                    or not isinstance(game_code, int)
                    or game_code <= 0
                ):
                    continue
                try:
                    header_response = requests.get(
                        f"{self.euroleague_api_base}/Header",
                        params={'gamecode': game_code, 'seasoncode': season_code},
                        timeout=10,
                    )
                    if header_response.status_code != 200:
                        header_errors.append(
                            f"Game {game_code}: HTTP {header_response.status_code}"
                        )
                        continue
                    header = header_response.json()
                except (requests.RequestException, ValueError) as exc:
                    header_errors.append(f"Game {game_code}: {type(exc).__name__}")
                    continue
                if not isinstance(header, dict):
                    header_errors.append(f"Game {game_code}: invalid payload")
                    continue
                if header.get('Live') is not True:
                    continue
                enriched = dict(header)
                enriched['_game_code'] = game_code
                parsed = self._parse_euroleague_game(enriched)
                if parsed:
                    live_games.append(parsed)

            if header_errors:
                self.errors['euroleague'] = '; '.join(header_errors[:3])
            else:
                self.errors.pop('euroleague', None)
            return live_games
        except (requests.RequestException, ValueError) as exc:
            self.errors['euroleague'] = type(exc).__name__
            logger.warning("Euroleague live data request failed: %s", type(exc).__name__)
            return []

    @staticmethod
    def _euroleague_season_code(now: Optional[datetime] = None) -> str:
        current = now or datetime.now(timezone.utc)
        start_year = current.year if current.month >= 7 else current.year - 1
        return f"E{start_year}"

    @staticmethod
    def _nearby_euroleague_games(
        games: List[Dict],
        now: Optional[datetime] = None,
    ) -> List[Dict]:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        nearby = []
        for game in games:
            if not isinstance(game, dict):
                continue
            raw_date = game.get('utcDate')
            if not isinstance(raw_date, str):
                continue
            try:
                start = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            except ValueError:
                continue
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if start - timedelta(minutes=30) <= current <= start + timedelta(hours=4):
                nearby.append(game)
        return nearby
    
    def _parse_euroleague_game(self, game: Dict) -> Optional[Dict]:
        """Parse Euroleague game data"""
        if not isinstance(game, dict):
            return None
        home_score = self._whole_score(game.get('ScoreA'))
        away_score = self._whole_score(game.get('ScoreB'))
        home_team = str(game.get('TeamA') or '').strip() or None
        away_team = str(game.get('TeamB') or '').strip() or None
        game_id = game.get('_game_code')
        period = self._period_number(game.get('Quarter'))
        clock = game.get('RemainingPartialTime')
        if (
            home_score is None
            or away_score is None
            or not home_team
            or not away_team
            or home_team == away_team
            or isinstance(game_id, bool)
            or not isinstance(game_id, (int, str))
            or not str(game_id).strip()
            or period is None
            or not isinstance(clock, str)
            or not clock.strip()
        ):
            return None
        return {
            'league': 'Euroleague',
            'game_id': game_id,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock.strip(),
            'game_status': 'Live',
            'venue': str(game.get('Stadium') or 'Unknown').strip() or 'Unknown',
            'source': 'EuroLeague',
        }

    @staticmethod
    def _period_number(value) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 1 else None
        if not isinstance(value, str):
            return None
        text = value.strip().upper()
        if text in {'OT', 'OVERTIME', 'EXTRA TIME'}:
            return 5
        numbers = re.findall(r"\d+", text)
        if len(numbers) != 1:
            return None
        period = int(numbers[0])
        return period if period >= 1 else None
    
    def scan_live_games(self, league: str = "All") -> List[Dict]:
        """
        Scan for all live games based on league selection
        
        Args:
            league: "NBA", "Euroleague", or "All"
        """
        all_games = []
        
        if league in ["NBA", "All"]:
            nba_games = self.get_live_nba_games()
            all_games.extend(nba_games)
        
        if league in ["Euroleague", "All"]:
            euroleague_games = self.get_live_euroleague_games()
            all_games.extend(euroleague_games)
        
        return all_games
    
    @staticmethod
    def _clock_minutes_remaining(clock) -> Optional[float]:
        if not isinstance(clock, str):
            return None
        iso_match = re.fullmatch(r"PT(?:(\d+)M)?([\d.]+)S", clock)
        if iso_match:
            try:
                minutes = int(iso_match.group(1) or 0)
                seconds = float(iso_match.group(2))
            except ValueError:
                return None
            if not math.isfinite(seconds) or not 0 <= seconds < 60:
                return None
            return minutes + seconds / 60.0
        plain_match = re.fullmatch(r"(\d+):(\d{2})", clock)
        if plain_match:
            seconds = int(plain_match.group(2))
            if seconds > 59:
                return None
            return int(plain_match.group(1)) + seconds / 60.0
        return None

    def calculate_scoring_projection(self, game: Dict) -> Optional[float]:
        """Straight-line projection from score and actual game clock."""
        league = game.get('league')
        if league not in {'NBA', 'Euroleague'}:
            return None
        try:
            period = int(game.get('period'))
            home_score = float(game.get('home_score'))
            away_score = float(game.get('away_score'))
            total_score = home_score + away_score
        except (TypeError, ValueError):
            return None
        if (
            isinstance(game.get('period'), bool)
            or isinstance(game.get('home_score'), bool)
            or isinstance(game.get('away_score'), bool)
            or not math.isfinite(home_score)
            or not math.isfinite(away_score)
            or not math.isfinite(total_score)
            or home_score < 0
            or away_score < 0
            or not home_score.is_integer()
            or not away_score.is_integer()
            or total_score < 0
            or period < 1
            or period > 4
        ):
            return None

        period_minutes = 12 if league == 'NBA' else 10
        remaining = self._clock_minutes_remaining(game.get('game_clock'))
        if remaining is None or not 0 <= remaining <= period_minutes:
            return None
        elapsed = (period - 1) * period_minutes + (period_minutes - remaining)
        regulation_minutes = period_minutes * 4
        if elapsed < 2:
            return None
        return round(total_score / elapsed * regulation_minutes, 1)
    
    def analyze_quarter_winner(self, game: Dict) -> Optional[Dict]:
        """No quarter-winner signal is emitted from score differential alone."""
        return None
    
    def analyze_total_points(self, game: Dict) -> Optional[Dict]:
        """No totals signal is emitted without a validated scoring model and line."""
        return None
    
    def analyze_player_props(self, game: Dict) -> List[Dict]:
        """No player output is emitted without detailed player statistics."""
        return []


def create_basketball_tab(league: str = "All"):
    """
    Main Basketball Tab Creator
    API-backed live observations.
    """
    st.header("🏀 BASKETBALL LIVE SCANNER")
    st.markdown(f"### {league} - Real-Time Analysis")
    
    scanner = BasketballScanner()
    
    # Scan for live games
    with st.spinner(f"🔍 Scanning for live {league} games..."):
        games = scanner.scan_live_games(league)
    
    if not games:
        st.warning(f"⚠️ No live {league} games at this moment")
        return
    
    st.success(f"✅ Found {len(games)} live {league} game(s)!")
    
    # Analyze each game
    for game in games:
        analyze_and_display_game(game, scanner)


def analyze_and_display_game(game: Dict, scanner: BasketballScanner):
    """Display one live game and its clock-aware score projection."""
    home = game['home_team']
    away = game['away_team']
    period = game.get('period', 1)
    clock = game.get('game_clock', '12:00')
    
    with st.expander(
        f"🏀 {home} vs {away} - Q{period} {clock} [{game['home_score']}-{game['away_score']}]",
        expanded=True
    ):
        # Game Info
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("League", game['league'])
        
        with col2:
            score_diff = abs(game['home_score'] - game['away_score'])
            leader = home if game['home_score'] > game['away_score'] else away
            st.metric("Score", f"{game['home_score']}-{game['away_score']}", 
                     f"{leader} +{score_diff}")
        
        with col3:
            projection = scanner.calculate_scoring_projection(game)
            st.metric(
                "Straight-line total",
                f"{projection:.1f}" if projection is not None else "n/a",
            )
        
        with col4:
            st.metric("Period", f"Q{period}", clock)
        
        st.markdown("---")
        
        st.info(
            "Live observation only. Team-strength, possession, lineup, and "
            "out-of-sample calibration are required before a model signal is emitted."
        )


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Basketball Scanner - Real Time",
        page_icon="🏀",
        layout="wide"
    )
    
    st.title("🏀 Basketball Scanner - Real-Time Analysis")
    
    league = st.radio(
        "Select League:",
        ["NBA", "Euroleague", "All"],
        horizontal=True
    )
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    create_basketball_tab(league)
