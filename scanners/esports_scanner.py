"""PandaScore live match provider for e-sports (CS2, LoL, Dota 2, Valorant).

Delivers running matches, verified series state, and bounded team histories.
The probability model lives in ``multi_sport_recommendations`` (Beta-
Bradley-Terry Series v1) — this module intentionally contains no betting
estimates anymore.
"""

import math
import requests
from typing import Dict, List, Optional

try:  # Automation-Runner ohne streamlit: Secrets entfallen, config.ini/env greifen
    import streamlit as st
except ImportError:  # pragma: no cover - nur ausserhalb der Streamlit-App
    st = None

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
                team1_history = self._get_team_history(team1_id, game_slug)[:20]
                team2_history = self._get_team_history(team2_id, game_slug)[:20]
                team1_stats = self._get_team_stats(team1_id, game_slug)
                team2_stats = self._get_team_stats(team2_id, game_slug)
            else:
                team1_history = []
                team2_history = []
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
                'team1_history': team1_history,
                'team2_history': team2_history,
                'status': status,
                'begin_at': begin_at,
                'source': 'PandaScore',
            }
        except (AttributeError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _empty_stats() -> Dict:
        return {'win_rate': None, 'matches': 0, 'wins': 0, 'form': []}

    def get_match_result(self, match_id: int) -> Optional[Dict]:
        """Finished-match result for shadow settlement.

        Returns {"winner_team_id": int} for finished matches, else None
        (still running, not started, or invalid payload).
        """
        if (
            not self.api_key
            or not isinstance(match_id, int)
            or isinstance(match_id, bool)
            or match_id <= 0
        ):
            return None
        try:
            response = requests.get(
                f"{self.pandascore_base}/matches/{match_id}",
                headers=self.headers,
                timeout=10,
            )
        except (requests.RequestException, ValueError):
            return None
        if response.status_code != 200:
            return None
        try:
            match = response.json()
        except ValueError:
            return None
        if not isinstance(match, dict):
            return None
        if str(match.get("status") or "").lower() != "finished":
            return None
        winner = match.get("winner")
        winner_id = winner.get("id") if isinstance(winner, dict) else None
        if (
            not isinstance(winner_id, int)
            or isinstance(winner_id, bool)
            or winner_id <= 0
        ):
            return None
        return {"winner_team_id": winner_id}

    def _get_team_history(self, team_id: int, game: str) -> List[Dict]:
        """Raw finished-match history for a team (newest first, max 50).

        One cached API call per team; both the aggregate stats and the
        ELO subgraph are derived from this single payload.
        """
        if not isinstance(team_id, int) or isinstance(team_id, bool) or team_id <= 0:
            return []
        cache_key = f"hist_{game}_{team_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        history: List[Dict] = []
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
                else:
                    for m in matches:
                        if not isinstance(m, dict):
                            continue
                        if str(m.get('status') or '').lower() != 'finished':
                            continue
                        match_id = m.get('id')
                        opponent_ids = []
                        for item in (m.get('opponents') or []):
                            if not isinstance(item, dict):
                                continue
                            opponent = item.get('opponent')
                            if isinstance(opponent, dict) and isinstance(
                                opponent.get('id'), int
                            ) and not isinstance(opponent.get('id'), bool):
                                opponent_ids.append(opponent['id'])
                        if (
                            team_id not in opponent_ids
                            or len(opponent_ids) != 2
                            or not isinstance(match_id, int)
                            or isinstance(match_id, bool)
                            or match_id <= 0
                        ):
                            continue
                        winner = m.get('winner', {})
                        winner_id = winner.get('id') if isinstance(winner, dict) else None
                        if winner_id not in opponent_ids:
                            continue
                        number_of_games = m.get('number_of_games')
                        if (
                            not isinstance(number_of_games, int)
                            or isinstance(number_of_games, bool)
                            or number_of_games < 1
                        ):
                            number_of_games = None
                        begin_at = m.get('begin_at')
                        history.append(
                            {
                                'match_id': match_id,
                                'begin_at': begin_at if isinstance(begin_at, str) else '',
                                'opponent_id': [oid for oid in opponent_ids if oid != team_id][0],
                                'won': winner_id == team_id,
                                'number_of_games': number_of_games,
                            }
                        )
            else:
                self.errors[f'team_{team_id}'] = f'HTTP {response.status_code}'
        except (requests.RequestException, ValueError) as exc:
            self.errors[f'team_{team_id}'] = type(exc).__name__
        self._stats_cache[cache_key] = history
        return history

    def _get_team_stats(self, team_id: int, game: str) -> Dict:
        """Aggregate stats derived from the cached raw history."""
        history = self._get_team_history(team_id, game)[:20]
        if not history:
            return self._empty_stats()
        wins = sum(1 for item in history if item['won'])
        total = len(history)
        form = ['W' if item['won'] else 'L' for item in history[:5]]
        return {
            'win_rate': round(wins / total * 100, 1),
            'matches': total,
            'wins': wins,
            'form': form,
        }
