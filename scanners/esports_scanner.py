"""PandaScore live match provider for e-sports (CS2, LoL, Dota 2, Valorant).

Delivers running matches, verified series state, and bounded team histories.
The probability model lives in ``multi_sport_recommendations`` (Beta-
Bradley-Terry Series v1) — this module intentionally contains no betting
estimates anymore.
"""

import math
import streamlit as st
import requests
from typing import Dict, List, Optional

from config_loader import load_app_config

class EsportsScanner:
    """E-Sports live data provider with strict payload validation."""

    MAX_LIVE_MATCHES_PER_GAME = 6
    MAX_UPCOMING_MATCHES_PER_GAME = 6

    def __init__(self):
        self.pandascore_base = "https://api.pandascore.co"
        self.api_key = load_app_config(st).pandascore_key or ''

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }

        # Cache for team stats to avoid repeated API calls
        self._stats_cache = {}
        self.errors: Dict[str, str] = {}

    def get_live_matches(self, game: str = "all") -> List[Dict]:
        """Running matches from Pandascore."""
        return self._scan(game, ("running", "live"))

    def get_upcoming_matches(self, game: str = "all") -> List[Dict]:
        """Not-yet-started matches from Pandascore, soonest first."""
        return self._scan(game, ("upcoming", "upcoming"))

    def get_matches(self, game: str = "all") -> List[Dict]:
        """Live plus upcoming matches in one bounded scan."""
        return self._scan(game, ("running", "live"), ("upcoming", "upcoming"))

    def _scan(self, game: str, *endpoints: tuple) -> List[Dict]:
        self.errors = {}
        if not self.api_key:
            self.errors["credentials"] = "PandaScore key missing"
            return []

        games_map = {
            'cs2': 'csgo',
            'lol': 'lol',
            'dota2': 'dota2',
            'valorant': 'valorant'
        }

        if game != 'all' and game not in games_map:
            self.errors['selection'] = 'Unsupported game'
            return []

        games_to_scan = list(games_map.keys()) if game == 'all' else [game]
        all_matches: List[Dict] = []
        for g in games_to_scan:
            api_game = games_map.get(g, g)
            for endpoint, status in endpoints:
                error_key = g if len(endpoints) == 1 else f"{status}_{g}"
                all_matches.extend(
                    self._fetch_endpoint(api_game, g.upper(), endpoint, status, error_key)
                )
        return all_matches

    def _fetch_endpoint(
        self,
        api_game: str,
        game_label: str,
        endpoint: str,
        status: str,
        error_key: str,
    ) -> List[Dict]:
        limit = (
            self.MAX_LIVE_MATCHES_PER_GAME
            if status == "live"
            else self.MAX_UPCOMING_MATCHES_PER_GAME
        )
        url = f"{self.pandascore_base}/{api_game}/matches/{endpoint}"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params={'per_page': limit, 'sort': 'begin_at'},
                timeout=10,
            )
        except (requests.RequestException, ValueError) as exc:
            self.errors[error_key] = type(exc).__name__
            return []
        if response.status_code != 200:
            self.errors[error_key] = f"HTTP {response.status_code}"
            return []
        try:
            matches = response.json()
        except ValueError:
            self.errors[error_key] = "Invalid provider payload"
            return []
        if not isinstance(matches, list):
            self.errors[error_key] = "Invalid provider payload"
            return []
        formatted_matches: List[Dict] = []
        for match in matches[:limit]:
            formatted = self._format_match(match, game_label, status=status)
            if formatted:
                formatted_matches.append(formatted)
        return formatted_matches

    def _format_match(self, match: Dict, game: str, status: str = "live") -> Optional[Dict]:
        """Format match with team stats.

        ``status`` is "live" (running match, verified scoreboard required)
        or "upcoming" (not started, score fixed at 0:0).
        """
        try:
            if not isinstance(match, dict) or status not in {"live", "upcoming"}:
                return None
            opponents = match.get('opponents', [])
            if not isinstance(opponents, list) or len(opponents) != 2:
                return None

            if not all(isinstance(item, dict) for item in opponents):
                return None
            team1 = opponents[0].get('opponent', {})
            team2 = opponents[1].get('opponent', {})
            if not isinstance(team1, dict) or not isinstance(team2, dict):
                return None

            team1_id = team1.get('id')
            team2_id = team2.get('id')
            team1_name = str(team1.get('name') or '').strip()
            team2_name = str(team2.get('name') or '').strip()
            match_id = match.get('id')
            if (
                not isinstance(team1_id, int)
                or isinstance(team1_id, bool)
                or team1_id <= 0
                or not isinstance(team2_id, int)
                or isinstance(team2_id, bool)
                or team2_id <= 0
                or team1_id == team2_id
                or not team1_name
                or not team2_name
                or team1_name.casefold() == team2_name.casefold()
                or not isinstance(match_id, int)
                or isinstance(match_id, bool)
                or match_id <= 0
            ):
                return None

            if status == "upcoming":
                if str(match.get('status') or '').lower() != 'not_started':
                    return None
                score1, score2 = 0, 0
            else:
                if str(match.get('status') or '').lower() != 'running':
                    return None
                results = match.get('results', [])
                if not isinstance(results, list):
                    return None
                scores_by_team = {
                    result.get('team_id'): result.get('score')
                    for result in results
                    if isinstance(result, dict) and result.get('team_id') is not None
                }
                score1 = scores_by_team.get(team1_id)
                score2 = scores_by_team.get(team2_id)
                if (
                    isinstance(score1, bool)
                    or isinstance(score2, bool)
                    or not isinstance(score1, (int, float))
                    or not isinstance(score2, (int, float))
                    or not math.isfinite(float(score1))
                    or not math.isfinite(float(score2))
                    or float(score1) < 0
                    or float(score2) < 0
                    or not float(score1).is_integer()
                    or not float(score2).is_integer()
                ):
                    return None
                score1 = int(score1)
                score2 = int(score2)

            begin_at = match.get('begin_at')
            if begin_at is not None and not isinstance(begin_at, str):
                begin_at = None

            series_type = match.get('number_of_games')
            can_estimate = (
                isinstance(series_type, int)
                and not isinstance(series_type, bool)
                and series_type > 0
                and series_type % 2 == 1
            )

            # Historical calls are useful only when the series model can consume them.
            game_slug = 'csgo' if game == 'CS2' else game.lower()
            if can_estimate:
                team1_stats = self._get_team_stats(team1_id, game_slug)
                team2_stats = self._get_team_stats(team2_id, game_slug)
            else:
                team1_stats = self._empty_stats()
                team2_stats = self._empty_stats()

            tournament = match.get('tournament', {})
            tournament_name = (
                str(tournament.get('name') or 'Unknown').strip()
                if isinstance(tournament, dict)
                else 'Unknown'
            ) or 'Unknown'

            return {
                'id': match_id,
                'game': game if game != 'CSGO' else 'CS2',
                'team1': team1_name,
                'team2': team2_name,
                'team1_id': team1_id,
                'team2_id': team2_id,
                'team1_score': score1,
                'team2_score': score2,
                'tournament': tournament_name,
                'series_type': series_type,
                'team1_stats': team1_stats,
                'team2_stats': team2_stats,
                'status': status,
                'begin_at': begin_at,
                'source': 'PandaScore',
            }
        except (AttributeError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _empty_stats() -> Dict:
        return {'win_rate': None, 'matches': 0, 'wins': 0, 'form': []}

    def _get_team_stats(self, team_id: int, game: str) -> Dict:
        """Get REAL team statistics from last matches"""
        if not isinstance(team_id, int) or isinstance(team_id, bool) or team_id <= 0:
            return self._empty_stats()

        # Check cache
        cache_key = f"{game}_{team_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]

        try:
            # The team endpoint guarantees membership. The former
            # filter[opponent_id] query selected the opponent instead.
            url = f"{self.pandascore_base}/teams/{team_id}/matches"
            params = {
                'sort': '-begin_at',
                'per_page': 50,
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=10)

            if response.status_code == 200:
                matches = response.json()
                if not isinstance(matches, list):
                    self.errors[f'team_{team_id}'] = 'Invalid provider payload'
                    stats = self._empty_stats()
                    self._stats_cache[cache_key] = stats
                    return stats
                if matches:
                    wins = 0
                    total = 0
                    form = []  # Last 5 results: W/L

                    for m in matches:
                        if str(m.get('status') or '').lower() != 'finished':
                            continue
                        opponent_ids = {
                            item.get('opponent', {}).get('id')
                            for item in (m.get('opponents') or [])
                            if isinstance(item, dict)
                        }
                        if team_id not in opponent_ids:
                            continue
                        winner = m.get('winner', {})
                        winner_id = winner.get('id') if winner else None
                        if winner_id is None:
                            continue
                        won = winner_id == team_id
                        total += 1

                        if won:
                            wins += 1

                        if len(form) < 5:
                            form.append('W' if won else 'L')
                        if total >= 20:
                            break

                    if total == 0:
                        stats = self._empty_stats()
                        self._stats_cache[cache_key] = stats
                        return stats
                    win_rate = wins / total * 100

                    stats = {
                        'win_rate': round(win_rate, 1),
                        'matches': total,
                        'wins': wins,
                        'form': form
                    }

                    self._stats_cache[cache_key] = stats
                    return stats
            else:
                self.errors[f'team_{team_id}'] = f'HTTP {response.status_code}'
        except (requests.RequestException, ValueError) as exc:
            self.errors[f'team_{team_id}'] = type(exc).__name__

        stats = self._empty_stats()
        self._stats_cache[cache_key] = stats
        return stats
