"""Alternative-market probability baselines with strict data gates.

All outputs are model-only and uncalibrated. No bookmaker price, edge, ROI,
or stake is inferred in this module.
"""

from dataclasses import dataclass
import math
import time
from typing import Dict, List, Optional, Tuple

import requests

from season_utils import current_season_start_year_for_id


def _optional_nonnegative(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0:
        return None
    return numeric


def _optional_count(value, *, maximum: Optional[int] = None) -> Optional[int]:
    numeric = _optional_nonnegative(value)
    if (
        numeric is None
        or not numeric.is_integer()
        or maximum is not None and numeric > maximum
    ):
        return None
    return int(numeric)


def _positive_integer(value) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def poisson_probability(k: int, lambda_: float) -> float:
    """Return ``P(X=k)`` for a Poisson random variable."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        return 0.0
    rate = _optional_nonnegative(lambda_)
    if rate is None:
        return 0.0
    if rate == 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(k * math.log(rate) - rate - math.lgamma(k + 1))


def poisson_over_probability(expected: float, threshold: float) -> float:
    """Return ``P(X > threshold)`` for a Poisson count."""
    rate = _optional_nonnegative(expected)
    if (
        rate is None
        or isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
    ):
        raise ValueError("expected and threshold must be finite")
    floor_threshold = math.floor(threshold)
    if floor_threshold < 0:
        return 1.0
    probability_below = sum(
        poisson_probability(k, rate) for k in range(floor_threshold + 1)
    )
    return max(0.0, min(1.0, 1.0 - probability_below))


def negative_binomial_probability(k: int, mu: float, alpha: float = 0.3) -> float:
    """Return an NB2 count probability with variance ``mu + alpha*mu^2``."""
    mean = _optional_nonnegative(mu)
    dispersion = _optional_nonnegative(alpha)
    if isinstance(k, bool) or not isinstance(k, int) or k < 0 or mean is None or not dispersion:
        return 0.0
    if mean == 0:
        return 1.0 if k == 0 else 0.0
    size = 1.0 / dispersion
    success_probability = size / (size + mean)
    log_probability = (
        math.lgamma(k + size)
        - math.lgamma(k + 1)
        - math.lgamma(size)
        + size * math.log(success_probability)
        + k * math.log1p(-success_probability)
    )
    return math.exp(log_probability)


def dixon_coles_adjustment(
    home_goals: int,
    away_goals: int,
    home_lambda: float,
    away_lambda: float,
    rho: float = 0.0,
) -> float:
    """Return Dixon-Coles tau for an explicitly supplied dependence value."""
    if (
        isinstance(rho, bool)
        or not isinstance(rho, (int, float))
        or not math.isfinite(float(rho))
        or not -0.3 <= float(rho) <= 0.3
    ):
        raise ValueError("rho must be finite and between -0.3 and 0.3")
    home_rate = _optional_nonnegative(home_lambda)
    away_rate = _optional_nonnegative(away_lambda)
    if home_rate is None or away_rate is None:
        raise ValueError("goal rates cannot be negative")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (home_goals, away_goals)
    ):
        raise ValueError("goals must be non-negative integers")
    if home_goals == 0 and away_goals == 0:
        tau = 1 - home_rate * away_rate * rho
    elif home_goals == 1 and away_goals == 0:
        tau = 1 + away_rate * rho
    elif home_goals == 0 and away_goals == 1:
        tau = 1 + home_rate * rho
    elif home_goals == 1 and away_goals == 1:
        tau = 1 - rho
    else:
        tau = 1.0
    return max(0.0, tau)


class PreMatchAlternativeAnalyzer:
    """Build count baselines from completed API-Football observations."""

    MIN_SAMPLE = 5

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key}
        self.last_request = 0.0
        self.cache = {}
        self.errors: Dict[str, str] = {}

    def _rate_limit(self):
        elapsed = time.monotonic() - self.last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request = time.monotonic()

    def _response_data(self, response, label: str, expected_type):
        if response.status_code != 200:
            self.errors[label] = f"HTTP {response.status_code}"
            return None
        try:
            payload = response.json()
        except ValueError:
            self.errors[label] = "invalid JSON"
            return None
        if not isinstance(payload, dict):
            self.errors[label] = "invalid provider payload"
            return None
        provider_errors = payload.get('errors')
        if provider_errors:
            self.errors[label] = str(provider_errors)
            return None
        data = payload.get('response')
        if not isinstance(data, expected_type):
            self.errors[label] = "invalid response payload"
            return None
        if expected_type is list and any(not isinstance(item, dict) for item in data):
            self.errors[label] = "invalid response entries"
            return None
        return data

    @staticmethod
    def _empty_team_stats() -> Dict:
        return {
            'matches_played': 0,
            'goals_scored_avg': None,
            'goals_conceded_avg': None,
            'yellow_cards_avg': None,
            'red_cards_avg': None,
            'total_cards_avg': None,
        }

    @staticmethod
    def _empty_corner_stats() -> Dict:
        return {
            'avg_corners_for': None,
            'avg_corners_against': None,
            'matches': 0,
        }

    def get_team_statistics(
        self,
        team_id: int,
        league_id: int,
        season: Optional[int] = None,
    ) -> Dict:
        team_id = _positive_integer(team_id)
        league_id = _positive_integer(league_id)
        if team_id is None or league_id is None:
            return self._empty_team_stats()
        season = season if season is not None else current_season_start_year_for_id(league_id)
        if (
            isinstance(season, bool)
            or not isinstance(season, int)
            or not 1900 <= season <= 2100
        ):
            return self._empty_team_stats()
        cache_key = ('team', team_id, league_id, season)
        if cache_key in self.cache:
            return self.cache[cache_key]
        if not self.api_key:
            return self._empty_team_stats()

        self._rate_limit()
        try:
            response = requests.get(
                f"{self.base_url}/teams/statistics",
                headers=self.headers,
                params={'team': team_id, 'league': league_id, 'season': season},
                timeout=15,
            )
            data = self._response_data(response, f'team_{team_id}', dict)
            if data is None:
                return self._empty_team_stats()
        except (requests.RequestException, ValueError):
            return self._empty_team_stats()

        fixtures_data = data.get('fixtures')
        played = fixtures_data.get('played') if isinstance(fixtures_data, dict) else None
        if not isinstance(played, dict):
            self.errors[f'team_{team_id}'] = 'invalid fixture aggregates'
            return self._empty_team_stats()
        played_home = _optional_count(played.get('home'), maximum=200)
        played_away = _optional_count(played.get('away'), maximum=200)
        if played_home is None or played_away is None:
            self.errors[f'team_{team_id}'] = 'invalid match counts'
            return self._empty_team_stats()
        total_played = played_home + played_away
        if total_played <= 0:
            return self._empty_team_stats()

        goals = data.get('goals')
        goals_for_group = goals.get('for') if isinstance(goals, dict) else None
        goals_against_group = goals.get('against') if isinstance(goals, dict) else None
        goals_for = goals_for_group.get('total') if isinstance(goals_for_group, dict) else None
        goals_against = (
            goals_against_group.get('total')
            if isinstance(goals_against_group, dict)
            else None
        )
        if not isinstance(goals_for, dict) or not isinstance(goals_against, dict):
            self.errors[f'team_{team_id}'] = 'invalid goal aggregates'
            return self._empty_team_stats()
        totals_for = [
            _optional_count(goals_for.get('home'), maximum=total_played * 30),
            _optional_count(goals_for.get('away'), maximum=total_played * 30),
        ]
        totals_against = [
            _optional_count(goals_against.get('home'), maximum=total_played * 30),
            _optional_count(goals_against.get('away'), maximum=total_played * 30),
        ]

        def card_total(periods: Dict) -> Tuple[Optional[int], int]:
            if not isinstance(periods, dict):
                return None, 0
            total = 0.0
            observations = 0
            for period in periods.values():
                if not isinstance(period, dict):
                    return None, 0
                value = _optional_count(period.get('total'), maximum=total_played * 20)
                if value is None:
                    return None, 0
                total += value
                observations += 1
            return int(total), observations

        cards = data.get('cards')
        cards = cards if isinstance(cards, dict) else {}
        yellows, yellow_periods = card_total(cards.get('yellow'))
        reds, red_periods = card_total(cards.get('red'))
        has_yellows = yellows is not None and yellow_periods > 0
        has_reds = reds is not None and red_periods > 0
        result = {
            'matches_played': total_played,
            'goals_scored_avg': (
                round(sum(totals_for) / total_played, 2)
                if all(value is not None for value in totals_for)
                else None
            ),
            'goals_conceded_avg': (
                round(sum(totals_against) / total_played, 2)
                if all(value is not None for value in totals_against)
                else None
            ),
            'yellow_cards_avg': round(yellows / total_played, 2) if has_yellows else None,
            'red_cards_avg': round(reds / total_played, 3) if has_reds else None,
            'total_cards_avg': (
                round((yellows + reds) / total_played, 2)
                if has_yellows and has_reds else None
            ),
        }
        self.cache[cache_key] = result
        return result

    def _get_fixture_statistics(
        self,
        fixture_id: int,
        home_team_id: int,
        away_team_id: int,
    ) -> Optional[Dict]:
        fixture_id = _positive_integer(fixture_id)
        home_team_id = _positive_integer(home_team_id)
        away_team_id = _positive_integer(away_team_id)
        if (
            fixture_id is None
            or home_team_id is None
            or away_team_id is None
            or home_team_id == away_team_id
        ):
            return None
        cache_key = ('fixture_stats', fixture_id)
        if cache_key in self.cache:
            return self.cache[cache_key]
        self._rate_limit()
        try:
            response = requests.get(
                f"{self.base_url}/fixtures/statistics",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15,
            )
            entries = self._response_data(
                response,
                f'fixture_stats_{fixture_id}',
                list,
            )
            if entries is None:
                return None
        except (requests.RequestException, ValueError):
            return None

        by_team = {}
        for entry in entries:
            team = entry.get('team')
            statistics = entry.get('statistics')
            team_id = team.get('id') if isinstance(team, dict) else None
            if (
                _positive_integer(team_id) is None
                or not isinstance(statistics, list)
                or team_id in by_team
            ):
                self.errors[f'fixture_stats_{fixture_id}'] = 'invalid team statistics'
                return None
            by_team[team_id] = statistics
        home_stats = by_team.get(home_team_id)
        away_stats = by_team.get(away_team_id)
        if home_stats is None or away_stats is None:
            return None

        def get_stat(stats: List[Dict], stat_type: str) -> Optional[float]:
            for stat in stats:
                if not isinstance(stat, dict):
                    return None
                if stat.get('type') == stat_type:
                    return _optional_count(stat.get('value'), maximum=40)
            return None

        result = {
            'corners_home': get_stat(home_stats, 'Corner Kicks'),
            'corners_away': get_stat(away_stats, 'Corner Kicks'),
        }
        self.cache[cache_key] = result
        return result

    def get_team_corner_stats(
        self,
        team_id: int,
        league_id: Optional[int] = None,
        n_matches: int = 10,
        season: Optional[int] = None,
    ) -> Dict:
        team_id = _positive_integer(team_id)
        if team_id is None:
            return self._empty_corner_stats()
        if league_id is not None:
            league_id = _positive_integer(league_id)
            if league_id is None:
                return self._empty_corner_stats()
        if (
            isinstance(n_matches, bool)
            or not isinstance(n_matches, int)
            or not 1 <= n_matches <= 50
        ):
            return self._empty_corner_stats()
        season = (
            season if season is not None else current_season_start_year_for_id(league_id)
            if league_id is not None else None
        )
        if season is not None and (
            isinstance(season, bool)
            or not isinstance(season, int)
            or not 1900 <= season <= 2100
        ):
            return self._empty_corner_stats()
        cache_key = ('corners', team_id, league_id, season, n_matches)
        if cache_key in self.cache:
            return self.cache[cache_key]
        if not self.api_key:
            return self._empty_corner_stats()

        params = {'team': team_id, 'last': n_matches, 'status': 'FT'}
        if league_id is not None:
            params.update({'league': league_id, 'season': season})
        self._rate_limit()
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params=params,
                timeout=15,
            )
            fixtures = self._response_data(
                response,
                f'team_fixtures_{team_id}',
                list,
            )
            if fixtures is None:
                return self._empty_corner_stats()
        except (requests.RequestException, ValueError):
            return self._empty_corner_stats()

        corners_for = []
        corners_against = []
        for fixture in fixtures:
            teams = fixture.get('teams')
            fixture_data = fixture.get('fixture')
            home = teams.get('home') if isinstance(teams, dict) else None
            away = teams.get('away') if isinstance(teams, dict) else None
            home_id = home.get('id') if isinstance(home, dict) else None
            away_id = away.get('id') if isinstance(away, dict) else None
            fixture_id = fixture_data.get('id') if isinstance(fixture_data, dict) else None
            if (
                _positive_integer(fixture_id) is None
                or _positive_integer(home_id) is None
                or _positive_integer(away_id) is None
                or home_id == away_id
                or team_id not in {home_id, away_id}
            ):
                self.errors[f'team_fixtures_{team_id}'] = 'invalid fixture data'
                return self._empty_corner_stats()
            stats = self._get_fixture_statistics(fixture_id, home_id, away_id)
            if not stats:
                continue
            home_corners = stats.get('corners_home')
            away_corners = stats.get('corners_away')
            if home_corners is None or away_corners is None:
                continue
            if team_id == home_id:
                corners_for.append(home_corners)
                corners_against.append(away_corners)
            else:
                corners_for.append(away_corners)
                corners_against.append(home_corners)

        result = {
            'avg_corners_for': (
                round(sum(corners_for) / len(corners_for), 2)
                if corners_for else None
            ),
            'avg_corners_against': (
                round(sum(corners_against) / len(corners_against), 2)
                if corners_against else None
            ),
            'matches': len(corners_for),
        }
        self.cache[cache_key] = result
        return result

    @staticmethod
    def _data_quality(home_sample: int, away_sample: int) -> str:
        minimum = min(home_sample, away_sample)
        if minimum >= 10:
            return 'MEDIUM'
        if minimum >= 5:
            return 'LIMITED'
        return 'INSUFFICIENT_DATA'

    @staticmethod
    def _strongest_side(thresholds: Dict) -> Optional[Dict]:
        candidates = []
        for data in thresholds.values():
            over = float(data['probability']) / 100.0
            threshold = data['threshold']
            candidates.extend((('OVER', threshold, over), ('UNDER', threshold, 1.0 - over)))
        if not candidates:
            return None
        side, threshold, probability = max(candidates, key=lambda item: item[2])
        return {
            'selection': f"{side} {threshold}",
            'probability': round(probability * 100.0, 1),
            'model_price': None,
            'calibrated': False,
            'actionable': False,
            'recommendation_type': 'EXPLORATORY_ESTIMATE',
        }

    @staticmethod
    def _fixture_inputs(fixture: Dict) -> Optional[Tuple[int, int, int, int]]:
        if not isinstance(fixture, dict):
            return None
        league_id = _positive_integer(fixture.get('league_id'))
        home_team_id = _positive_integer(fixture.get('home_team_id'))
        away_team_id = _positive_integer(fixture.get('away_team_id'))
        season = fixture.get('season')
        if league_id is None or home_team_id is None or away_team_id is None:
            return None
        if home_team_id == away_team_id:
            return None
        if season is None:
            season = current_season_start_year_for_id(league_id)
        if (
            isinstance(season, bool)
            or not isinstance(season, int)
            or not 1900 <= season <= 2100
        ):
            return None
        return league_id, home_team_id, away_team_id, season

    def analyze_prematch_corners(self, fixture: Dict) -> Dict:
        inputs = self._fixture_inputs(fixture)
        if inputs is None:
            safe_fixture = fixture if isinstance(fixture, dict) else {}
            return self._empty_analysis('PRE_MATCH_CORNERS', safe_fixture, 0, 0)
        league_id, home_team_id, away_team_id, season = inputs
        home = self.get_team_corner_stats(
            home_team_id, league_id, season=season
        )
        away = self.get_team_corner_stats(
            away_team_id, league_id, season=season
        )
        quality = self._data_quality(home['matches'], away['matches'])
        values = (
            home.get('avg_corners_for'), home.get('avg_corners_against'),
            away.get('avg_corners_for'), away.get('avg_corners_against'),
        )
        if quality == 'INSUFFICIENT_DATA' or any(value is None for value in values):
            return self._empty_analysis('PRE_MATCH_CORNERS', fixture, home['matches'], away['matches'])

        home_expected = (home['avg_corners_for'] + away['avg_corners_against']) / 2.0
        away_expected = (away['avg_corners_for'] + home['avg_corners_against']) / 2.0
        expected = home_expected + away_expected
        thresholds = {
            f'over_{threshold}': {
                'threshold': threshold,
                'probability': round(poisson_over_probability(expected, threshold) * 100.0, 1),
                'expected': round(expected, 2),
                'calibrated': False,
            }
            for threshold in (7.5, 8.5, 9.5, 10.5, 11.5, 12.5)
        }
        return {
            'market': 'PRE_MATCH_CORNERS',
            'fixture': self._fixture_name(fixture),
            'expected_total': round(expected, 2),
            'home_expected': round(home_expected, 2),
            'away_expected': round(away_expected, 2),
            'weather': {'applied': False},
            'thresholds': thresholds,
            'best_signal': self._strongest_side(thresholds),
            'confidence': quality,
            'data_quality': {'home_matches': home['matches'], 'away_matches': away['matches']},
            'calibrated': False,
            'actionable': False,
        }

    def analyze_prematch_cards(self, fixture: Dict) -> Dict:
        inputs = self._fixture_inputs(fixture)
        if inputs is None:
            safe_fixture = fixture if isinstance(fixture, dict) else {}
            return self._empty_analysis('PRE_MATCH_CARDS', safe_fixture, 0, 0)
        league_id, home_team_id, away_team_id, season = inputs
        home = self.get_team_statistics(home_team_id, league_id, season)
        away = self.get_team_statistics(away_team_id, league_id, season)
        quality = self._data_quality(home['matches_played'], away['matches_played'])
        if (
            quality == 'INSUFFICIENT_DATA'
            or home.get('total_cards_avg') is None
            or away.get('total_cards_avg') is None
        ):
            result = self._empty_analysis(
                'PRE_MATCH_CARDS', fixture, home['matches_played'], away['matches_played']
            )
            result.update({
                'is_derby': False,
                'derby_factor': 1.0,
                'referee': {'name': fixture.get('referee') or 'Unknown', 'has_data': False},
            })
            return result

        home_expected = home['total_cards_avg']
        away_expected = away['total_cards_avg']
        expected = home_expected + away_expected
        thresholds = {
            f'over_{threshold}': {
                'threshold': threshold,
                'probability': round(poisson_over_probability(expected, threshold) * 100.0, 1),
                'expected': round(expected, 2),
                'calibrated': False,
            }
            for threshold in (2.5, 3.5, 4.5, 5.5, 6.5)
        }
        return {
            'market': 'PRE_MATCH_CARDS',
            'fixture': self._fixture_name(fixture),
            'expected_total': round(expected, 2),
            'home_expected': round(home_expected, 2),
            'away_expected': round(away_expected, 2),
            'thresholds': thresholds,
            'best_signal': self._strongest_side(thresholds),
            'confidence': quality,
            'data_quality': {
                'home_matches': home['matches_played'],
                'away_matches': away['matches_played'],
                'referee_data': False,
            },
            'is_derby': False,
            'derby_factor': 1.0,
            'referee': {
                'name': fixture.get('referee') or 'Unknown',
                'avg_cards': None,
                'has_data': False,
                'impact': 'not applied',
                'source': None,
            },
            'card_unit': 'one API card event; settlement rules are not modeled',
            'calibrated': False,
            'actionable': False,
        }

    @staticmethod
    def _fixture_name(fixture: Dict) -> str:
        return f"{fixture.get('home_team', 'Home')} vs {fixture.get('away_team', 'Away')}"

    def _empty_analysis(
        self,
        market: str,
        fixture: Dict,
        home_sample: int,
        away_sample: int,
    ) -> Dict:
        return {
            'market': market,
            'fixture': self._fixture_name(fixture),
            'expected_total': None,
            'home_expected': None,
            'away_expected': None,
            'thresholds': {},
            'best_signal': None,
            'confidence': 'INSUFFICIENT_DATA',
            'data_quality': {'home_matches': home_sample, 'away_matches': away_sample},
            'calibrated': False,
            'actionable': False,
        }


def _inplay_count_thresholds(
    current: int,
    minute: int,
    thresholds: List[float],
) -> Tuple[float, Dict]:
    if (
        isinstance(minute, bool)
        or not isinstance(minute, int)
        or minute < 15
        or minute > 90
        or isinstance(current, bool)
        or not isinstance(current, int)
        or current < 0
        or current > 500
        or not isinstance(thresholds, list)
        or not thresholds
        or any(
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(float(threshold))
            or threshold < 0
            or not math.isclose(float(threshold) % 1.0, 0.5, abs_tol=1e-9)
            for threshold in thresholds
        )
    ):
        raise ValueError("invalid in-play count model inputs")
    remaining = 90 - minute
    future_mean = current / minute * remaining
    expected_total = current + future_mean
    result = {}
    for threshold in thresholds:
        required_future = max(0, math.floor(threshold) + 1 - current)
        probability = (
            1.0 if required_future == 0
            else 1.0 - sum(
                poisson_probability(k, future_mean) for k in range(required_future)
            )
        )
        result[f'over_{threshold}'] = {
            'threshold': threshold,
            'probability': round(max(0.0, min(1.0, probability)) * 100.0, 1),
            'calibrated': False,
        }
    return expected_total, result


class CardPredictor:
    def predict_cards(self, match_data: Dict, minute: int) -> Dict:
        stats = match_data.get('stats') or {}
        home = _optional_count(stats.get('yellow_cards_home'), maximum=20)
        away = _optional_count(stats.get('yellow_cards_away'), maximum=20)
        if not isinstance(minute, int) or isinstance(minute, bool) or not 15 <= minute <= 90 or home is None or away is None:
            return {'market': 'YELLOW_CARDS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT', 'calibrated': False, 'actionable': False}
        current = home + away
        expected, thresholds = _inplay_count_thresholds(current, minute, [2.5, 3.5, 4.5, 5.5])
        return {
            'market': 'YELLOW_CARDS', 'current_cards': current,
            'expected_total': round(expected, 2), 'thresholds': thresholds,
            'recommendation': None, 'confidence': 'LIMITED', 'calibrated': False,
            'actionable': False,
        }


class CornerPredictor:
    def predict_corners(self, match_data: Dict, minute: int) -> Dict:
        stats = match_data.get('stats') or {}
        home = _optional_count(stats.get('corners_home'), maximum=40)
        away = _optional_count(stats.get('corners_away'), maximum=40)
        if not isinstance(minute, int) or isinstance(minute, bool) or not 15 <= minute <= 90 or home is None or away is None:
            return {'market': 'CORNERS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT', 'calibrated': False, 'actionable': False}
        current = home + away
        expected, thresholds = _inplay_count_thresholds(current, minute, [7.5, 8.5, 9.5, 10.5, 11.5])
        return {
            'market': 'CORNERS', 'current_corners': current,
            'expected_total': round(expected, 2), 'thresholds': thresholds,
            'recommendation': None, 'confidence': 'LIMITED', 'calibrated': False,
            'actionable': False,
        }


class ShotPredictor:
    def predict_shots(self, match_data: Dict, minute: int) -> Dict:
        stats = match_data.get('stats') or {}
        required = ('shots_home', 'shots_away', 'shots_on_target_home', 'shots_on_target_away')
        counts = {
            key: _optional_count(stats.get(key), maximum=100)
            for key in required
        }
        if not isinstance(minute, int) or isinstance(minute, bool) or not 15 <= minute <= 90 or any(value is None for value in counts.values()):
            return {'market': 'SHOTS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT', 'calibrated': False, 'actionable': False}
        shots = counts['shots_home'] + counts['shots_away']
        shots_on_target = counts['shots_on_target_home'] + counts['shots_on_target_away']
        if shots_on_target > shots:
            return {'market': 'SHOTS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT', 'calibrated': False, 'actionable': False}
        expected_shots, shot_thresholds = _inplay_count_thresholds(
            shots, minute, [20.5, 22.5, 24.5, 26.5, 28.5]
        )
        expected_sot, sot_thresholds = _inplay_count_thresholds(
            shots_on_target, minute, [6.5, 7.5, 8.5, 9.5, 10.5]
        )
        return {
            'market': 'SHOTS',
            'total_shots': {'current': shots, 'expected': round(expected_shots, 2), 'thresholds': shot_thresholds, 'recommendation': None},
            'shots_on_target': {'current': shots_on_target, 'expected': round(expected_sot, 2), 'thresholds': sot_thresholds, 'recommendation': None},
            'confidence': 'LIMITED', 'calibrated': False, 'actionable': False,
        }


class TeamSpecialPredictor:
    def predict_team_specials(self, match_data: Dict, minute: int) -> Dict:
        return {'market': 'TEAM_SPECIALS', 'opportunities': [], 'data_quality': 'INSUFFICIENT_MODEL', 'calibrated': False, 'actionable': False}


class HighestProbabilityFinder:
    """Compatibility wrapper that ranks only probabilities supplied upstream."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def find_highest_probability(self, fixture: Dict, btts_probability: float = None) -> Dict:
        candidates = []
        probability = _optional_nonnegative(btts_probability)
        if probability is not None and probability <= 100:
            candidates.append({'market': 'BTTS', 'selection': 'YES', 'probability': probability})
        candidates.sort(key=lambda item: item['probability'], reverse=True)
        return {'highest': candidates[0] if candidates else None, 'all': candidates, 'calibrated': False, 'actionable': False}


@dataclass
class TeamStrength:
    offensive: float
    defensive: float
    xg_for: float
    xg_against: float
    form_factor: float
    home_away_factor: float


@dataclass
class MatchPrediction:
    home_xg: float
    away_xg: float
    total_xg: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    home_or_draw: float
    draw_or_away: float
    home_or_away: float
    over_under: Dict[float, Tuple[float, float]]
    btts_yes: float
    btts_no: float
    best_result_signal: Optional[Dict]
    best_double_chance_signal: Optional[Dict]
    best_over_under_signal: Optional[Dict]
    model_price_home: Optional[float]
    model_price_draw: Optional[float]
    model_price_away: Optional[float]


class MatchResultPredictor:
    """Independent-Poisson baseline from league and venue-specific histories."""

    MIN_SAMPLE = 5

    def __init__(self, league_id: int, api_client=None):
        if isinstance(league_id, bool) or not isinstance(league_id, int) or league_id <= 0:
            raise ValueError("league_id must be a positive integer")
        self.league_id = league_id
        self.api_client = api_client

    def calculate_team_strength(
        self,
        goals_scored: List[int],
        goals_conceded: List[int],
        is_home: bool,
        xg_for: Optional[List[float]] = None,
        xg_against: Optional[List[float]] = None,
    ) -> TeamStrength:
        if (
            not isinstance(goals_scored, list)
            or not isinstance(goals_conceded, list)
            or len(goals_scored) < self.MIN_SAMPLE
            or len(goals_scored) != len(goals_conceded)
        ):
            raise ValueError("At least five equally paired completed matches are required")
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in [*goals_scored, *goals_conceded]
        ):
            raise ValueError("Goal histories must contain integer counts")
        scored = [_optional_count(value, maximum=30) for value in goals_scored]
        conceded = [_optional_count(value, maximum=30) for value in goals_conceded]
        if any(value is None for value in [*scored, *conceded]):
            raise ValueError("Goal histories must contain non-negative integer counts")
        offensive = sum(scored) / len(scored)
        defensive = sum(conceded) / len(conceded)

        valid_xg = (
            isinstance(xg_for, list) and isinstance(xg_against, list)
            and len(xg_for) == len(goals_scored)
            and len(xg_against) == len(goals_conceded)
            and all(
                (value := _optional_nonnegative(item)) is not None and value <= 20.0
                for item in [*xg_for, *xg_against]
            )
        )
        normalized_xg_for = [_optional_nonnegative(value) for value in xg_for] if valid_xg else []
        normalized_xg_against = (
            [_optional_nonnegative(value) for value in xg_against]
            if valid_xg else []
        )
        return TeamStrength(
            offensive=offensive,
            defensive=defensive,
            xg_for=sum(normalized_xg_for) / len(normalized_xg_for) if valid_xg else offensive,
            xg_against=(
                sum(normalized_xg_against) / len(normalized_xg_against)
                if valid_xg else defensive
            ),
            form_factor=1.0,
            home_away_factor=1.0,
        )

    def calculate_expected_goals(
        self,
        attacking_strength: float,
        defensive_weakness: float,
        is_home: bool,
        form_factor: float = 1.0,
    ) -> float:
        attack = _optional_nonnegative(attacking_strength)
        defense = _optional_nonnegative(defensive_weakness)
        if attack is None or defense is None:
            raise ValueError("Strength inputs must be finite and non-negative")
        return (attack + defense) / 2.0

    def calculate_score_probability(
        self,
        home_lambda: float,
        away_lambda: float,
        max_goals: int = 25,
        use_dixon_coles: bool = False,
        rho: float = 0.0,
    ) -> Dict[Tuple[int, int], float]:
        home_rate = _optional_nonnegative(home_lambda)
        away_rate = _optional_nonnegative(away_lambda)
        if (
            home_rate is None
            or away_rate is None
            or home_rate > 8
            or away_rate > 8
            or isinstance(max_goals, bool)
            or not isinstance(max_goals, int)
            or max_goals < 5
            or not isinstance(use_dixon_coles, bool)
        ):
            raise ValueError("Invalid score-model inputs")

        def marginal(rate: float) -> list[float]:
            values = [poisson_probability(goals, rate) for goals in range(max_goals + 1)]
            tail = max(0.0, 1.0 - sum(values))
            if tail > 0.00001:
                raise ValueError("max_goals truncates too much probability mass")
            values[-1] += tail
            mass = sum(values)
            return [value / mass for value in values]

        home_probabilities = marginal(home_rate)
        away_probabilities = marginal(away_rate)
        probabilities = {}
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                probability = (
                    home_probabilities[home_goals]
                    * away_probabilities[away_goals]
                )
                if use_dixon_coles:
                    probability *= dixon_coles_adjustment(
                        home_goals, away_goals, home_rate, away_rate, rho
                    )
                probabilities[(home_goals, away_goals)] = probability
        mass = sum(probabilities.values())
        if mass <= 0:
            raise ValueError("Score matrix has no probability mass")
        return {score: probability / mass for score, probability in probabilities.items()}

    def calculate_match_result(self, home_lambda: float, away_lambda: float) -> Tuple[float, float, float]:
        scores = self.calculate_score_probability(home_lambda, away_lambda)
        return (
            sum(probability for (home, away), probability in scores.items() if home > away),
            sum(probability for (home, away), probability in scores.items() if home == away),
            sum(probability for (home, away), probability in scores.items() if home < away),
        )

    @staticmethod
    def calculate_double_chance(home_win: float, draw: float, away_win: float) -> Tuple[float, float, float]:
        probabilities = (home_win, draw, away_win)
        if (
            any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
                for value in probabilities
            )
            or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-6)
        ):
            raise ValueError("1X2 probabilities must be finite and sum to one")
        return home_win + draw, draw + away_win, home_win + away_win

    def calculate_over_under(
        self,
        home_lambda: float,
        away_lambda: float,
        thresholds: Optional[List[float]] = None,
    ) -> Dict[float, Tuple[float, float]]:
        home_rate = _optional_nonnegative(home_lambda)
        away_rate = _optional_nonnegative(away_lambda)
        if home_rate is None or away_rate is None:
            raise ValueError("Goal rates must be finite and non-negative")
        if home_rate > 8.0 or away_rate > 8.0:
            raise ValueError("Goal rates exceed the supported model range")
        total = home_rate + away_rate
        active_thresholds = thresholds or [0.5, 1.5, 2.5, 3.5, 4.5]
        if (
            not isinstance(active_thresholds, list)
            or not active_thresholds
            or any(
                isinstance(threshold, bool)
                or not isinstance(threshold, (int, float))
                or not math.isfinite(float(threshold))
                or threshold < 0
                or not math.isclose(float(threshold) % 1.0, 0.5, abs_tol=1e-9)
                for threshold in active_thresholds
            )
        ):
            raise ValueError("Totals thresholds must be non-negative half lines")
        return {
            threshold: (
                poisson_over_probability(total, threshold),
                1.0 - poisson_over_probability(total, threshold),
            )
            for threshold in active_thresholds
        }

    @staticmethod
    def calculate_btts(home_lambda: float, away_lambda: float) -> Tuple[float, float]:
        home_rate = _optional_nonnegative(home_lambda)
        away_rate = _optional_nonnegative(away_lambda)
        if (
            home_rate is None
            or away_rate is None
            or home_rate > 8.0
            or away_rate > 8.0
        ):
            raise ValueError("Goal rates must be finite and non-negative")
        yes = (1.0 - math.exp(-home_rate)) * (1.0 - math.exp(-away_rate))
        return yes, 1.0 - yes

    @staticmethod
    def _signal(selection: str, probability: float) -> Optional[Dict]:
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(float(probability))
            or not 0.0 <= float(probability) <= 1.0
            or probability < 0.60
        ):
            return None
        return {
            'market': selection,
            'prob': probability,
            'model_price': None,
            'signal_score': probability,
            'calibrated': False,
            'actionable': False,
            'recommendation_type': 'EXPLORATORY_ESTIMATE',
        }

    def find_best_signals(
        self,
        home_win: float,
        draw: float,
        away_win: float,
        home_or_draw: float,
        draw_or_away: float,
        home_or_away: float,
        over_under: Dict[float, Tuple[float, float]],
    ) -> Dict:
        result_candidates = [('Home Win', home_win), ('Draw', draw), ('Away Win', away_win)]
        double_candidates = [('1X', home_or_draw), ('X2', draw_or_away), ('12', home_or_away)]
        total_candidates = [
            (f'Over {threshold}', over) for threshold, (over, _) in over_under.items()
        ] + [
            (f'Under {threshold}', under) for threshold, (_, under) in over_under.items()
        ]

        def strongest(candidates):
            selection, probability = max(candidates, key=lambda item: item[1])
            return self._signal(selection, probability)

        return {
            'result': strongest(result_candidates),
            'double_chance': strongest(double_candidates),
            'over_under': strongest(total_candidates),
        }

    def predict_match(
        self,
        home_team_data: Dict,
        away_team_data: Dict,
        home_team_id: int = None,
        away_team_id: int = None,
        home_team_name: str = None,
        away_team_name: str = None,
    ) -> MatchPrediction:
        home = self.calculate_team_strength(
            home_team_data['goals_scored'], home_team_data['goals_conceded'], True,
            home_team_data.get('xg_for'), home_team_data.get('xg_against'),
        )
        away = self.calculate_team_strength(
            away_team_data['goals_scored'], away_team_data['goals_conceded'], False,
            away_team_data.get('xg_for'), away_team_data.get('xg_against'),
        )
        home_xg = self.calculate_expected_goals(home.offensive, away.defensive, True)
        away_xg = self.calculate_expected_goals(away.offensive, home.defensive, False)
        home_win, draw, away_win = self.calculate_match_result(home_xg, away_xg)
        home_or_draw, draw_or_away, home_or_away = self.calculate_double_chance(
            home_win, draw, away_win
        )
        totals = self.calculate_over_under(home_xg, away_xg)
        btts_yes, btts_no = self.calculate_btts(home_xg, away_xg)
        signals = self.find_best_signals(
            home_win, draw, away_win,
            home_or_draw, draw_or_away, home_or_away,
            totals,
        )
        return MatchPrediction(
            home_xg=home_xg,
            away_xg=away_xg,
            total_xg=home_xg + away_xg,
            home_win_prob=home_win,
            draw_prob=draw,
            away_win_prob=away_win,
            home_or_draw=home_or_draw,
            draw_or_away=draw_or_away,
            home_or_away=home_or_away,
            over_under=totals,
            btts_yes=btts_yes,
            btts_no=btts_no,
            best_result_signal=signals['result'],
            best_double_chance_signal=signals['double_chance'],
            best_over_under_signal=signals['over_under'],
            model_price_home=None,
            model_price_draw=None,
            model_price_away=None,
        )


__all__ = [
    'PreMatchAlternativeAnalyzer',
    'HighestProbabilityFinder',
    'CardPredictor',
    'CornerPredictor',
    'ShotPredictor',
    'TeamSpecialPredictor',
    'TeamStrength',
    'MatchPrediction',
    'MatchResultPredictor',
    'poisson_probability',
    'negative_binomial_probability',
    'dixon_coles_adjustment',
]
