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
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0:
        return None
    return numeric


def poisson_probability(k: int, lambda_: float) -> float:
    """Return ``P(X=k)`` for a Poisson random variable."""
    if not isinstance(k, int) or k < 0:
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
    if rate is None or not math.isfinite(float(threshold)):
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
    if not isinstance(k, int) or k < 0 or mean is None or not dispersion:
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
    if not math.isfinite(rho) or not -0.3 <= rho <= 0.3:
        raise ValueError("rho must be finite and between -0.3 and 0.3")
    if home_lambda < 0 or away_lambda < 0:
        raise ValueError("goal rates cannot be negative")
    if home_goals == 0 and away_goals == 0:
        tau = 1 - home_lambda * away_lambda * rho
    elif home_goals == 1 and away_goals == 0:
        tau = 1 + away_lambda * rho
    elif home_goals == 0 and away_goals == 1:
        tau = 1 + home_lambda * rho
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

    def _rate_limit(self):
        elapsed = time.monotonic() - self.last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request = time.monotonic()

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
        season = season or current_season_start_year_for_id(league_id)
        cache_key = ('team', team_id, league_id, season)
        if cache_key in self.cache:
            return self.cache[cache_key]
        if not self.api_key or not team_id or not league_id:
            return self._empty_team_stats()

        self._rate_limit()
        try:
            response = requests.get(
                f"{self.base_url}/teams/statistics",
                headers=self.headers,
                params={'team': team_id, 'league': league_id, 'season': season},
                timeout=15,
            )
            if response.status_code != 200:
                return self._empty_team_stats()
            data = response.json().get('response') or {}
        except (requests.RequestException, ValueError):
            return self._empty_team_stats()

        played = data.get('fixtures', {}).get('played', {})
        played_home = int(played.get('home') or 0)
        played_away = int(played.get('away') or 0)
        total_played = played_home + played_away
        if total_played <= 0:
            return self._empty_team_stats()

        goals = data.get('goals', {})
        goals_for = goals.get('for', {}).get('total', {})
        goals_against = goals.get('against', {}).get('total', {})
        totals_for = [
            _optional_nonnegative(goals_for.get('home')),
            _optional_nonnegative(goals_for.get('away')),
        ]
        totals_against = [
            _optional_nonnegative(goals_against.get('home')),
            _optional_nonnegative(goals_against.get('away')),
        ]

        def card_total(periods: Dict) -> Tuple[float, int]:
            total = 0.0
            observations = 0
            for period in (periods or {}).values():
                if not isinstance(period, dict):
                    continue
                value = _optional_nonnegative(period.get('total'))
                if value is not None:
                    total += value
                    observations += 1
            return total, observations

        cards = data.get('cards', {})
        yellows, yellow_periods = card_total(cards.get('yellow', {}))
        reds, red_periods = card_total(cards.get('red', {}))
        has_card_data = yellow_periods + red_periods > 0
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
            'yellow_cards_avg': round(yellows / total_played, 2) if has_card_data else None,
            'red_cards_avg': round(reds / total_played, 3) if has_card_data else None,
            'total_cards_avg': (
                round((yellows + reds) / total_played, 2)
                if has_card_data else None
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
            if response.status_code != 200:
                return None
            entries = response.json().get('response') or []
        except (requests.RequestException, ValueError):
            return None

        by_team = {
            entry.get('team', {}).get('id'): entry.get('statistics', [])
            for entry in entries
        }
        home_stats = by_team.get(home_team_id)
        away_stats = by_team.get(away_team_id)
        if home_stats is None or away_stats is None:
            return None

        def get_stat(stats: List[Dict], stat_type: str) -> Optional[float]:
            for stat in stats:
                if stat.get('type') == stat_type:
                    return _optional_nonnegative(stat.get('value'))
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
        season = (
            season or current_season_start_year_for_id(league_id)
            if league_id is not None else None
        )
        cache_key = ('corners', team_id, league_id, season, n_matches)
        if cache_key in self.cache:
            return self.cache[cache_key]
        if not self.api_key or not team_id:
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
            if response.status_code != 200:
                return self._empty_corner_stats()
            fixtures = response.json().get('response') or []
        except (requests.RequestException, ValueError):
            return self._empty_corner_stats()

        corners_for = []
        corners_against = []
        for fixture in fixtures:
            home_id = fixture.get('teams', {}).get('home', {}).get('id')
            away_id = fixture.get('teams', {}).get('away', {}).get('id')
            fixture_id = fixture.get('fixture', {}).get('id')
            if not fixture_id or team_id not in {home_id, away_id}:
                continue
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
            'model_price': round(1.0 / probability, 2) if probability > 0 else None,
            'calibrated': False,
        }

    def analyze_prematch_corners(self, fixture: Dict) -> Dict:
        league_id = fixture.get('league_id')
        season = fixture.get('season') or current_season_start_year_for_id(league_id)
        home = self.get_team_corner_stats(
            fixture.get('home_team_id'), league_id, season=season
        )
        away = self.get_team_corner_stats(
            fixture.get('away_team_id'), league_id, season=season
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
        }

    def analyze_prematch_cards(self, fixture: Dict) -> Dict:
        league_id = fixture.get('league_id')
        season = fixture.get('season') or current_season_start_year_for_id(league_id)
        home = self.get_team_statistics(fixture.get('home_team_id'), league_id, season)
        away = self.get_team_statistics(fixture.get('away_team_id'), league_id, season)
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
        }


def _inplay_count_thresholds(
    current: int,
    minute: int,
    thresholds: List[float],
) -> Tuple[float, Dict]:
    if minute < 15 or minute > 90 or current < 0:
        raise ValueError("minute must be 15..90 and current count non-negative")
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
        home = stats.get('yellow_cards_home')
        away = stats.get('yellow_cards_away')
        if minute < 15 or not isinstance(home, (int, float)) or not isinstance(away, (int, float)):
            return {'market': 'YELLOW_CARDS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT'}
        current = int(home + away)
        expected, thresholds = _inplay_count_thresholds(current, minute, [2.5, 3.5, 4.5, 5.5])
        return {
            'market': 'YELLOW_CARDS', 'current_cards': current,
            'expected_total': round(expected, 2), 'thresholds': thresholds,
            'recommendation': None, 'confidence': 'LIMITED', 'calibrated': False,
        }


class CornerPredictor:
    def predict_corners(self, match_data: Dict, minute: int) -> Dict:
        stats = match_data.get('stats') or {}
        home = stats.get('corners_home')
        away = stats.get('corners_away')
        if minute < 15 or not isinstance(home, (int, float)) or not isinstance(away, (int, float)):
            return {'market': 'CORNERS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT'}
        current = int(home + away)
        expected, thresholds = _inplay_count_thresholds(current, minute, [7.5, 8.5, 9.5, 10.5, 11.5])
        return {
            'market': 'CORNERS', 'current_corners': current,
            'expected_total': round(expected, 2), 'thresholds': thresholds,
            'recommendation': None, 'confidence': 'LIMITED', 'calibrated': False,
        }


class ShotPredictor:
    def predict_shots(self, match_data: Dict, minute: int) -> Dict:
        stats = match_data.get('stats') or {}
        required = ('shots_home', 'shots_away', 'shots_on_target_home', 'shots_on_target_away')
        if minute < 15 or any(not isinstance(stats.get(key), (int, float)) for key in required):
            return {'market': 'SHOTS', 'thresholds': {}, 'recommendation': None, 'confidence': 'INSUFFICIENT'}
        shots = int(stats['shots_home'] + stats['shots_away'])
        shots_on_target = int(stats['shots_on_target_home'] + stats['shots_on_target_away'])
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
            'confidence': 'LIMITED', 'calibrated': False,
        }


class TeamSpecialPredictor:
    def predict_team_specials(self, match_data: Dict, minute: int) -> Dict:
        return {'market': 'TEAM_SPECIALS', 'opportunities': [], 'data_quality': 'INSUFFICIENT_MODEL'}


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
        return {'highest': candidates[0] if candidates else None, 'all': candidates, 'calibrated': False}


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
        if len(goals_scored) < self.MIN_SAMPLE or len(goals_scored) != len(goals_conceded):
            raise ValueError("At least five equally paired completed matches are required")
        values = [*goals_scored, *goals_conceded]
        if any(_optional_nonnegative(value) is None for value in values):
            raise ValueError("Goal histories must be finite and non-negative")
        offensive = sum(goals_scored) / len(goals_scored)
        defensive = sum(goals_conceded) / len(goals_conceded)

        valid_xg = (
            xg_for is not None and xg_against is not None
            and len(xg_for) == len(goals_scored)
            and len(xg_against) == len(goals_conceded)
            and all(_optional_nonnegative(value) is not None for value in [*xg_for, *xg_against])
        )
        return TeamStrength(
            offensive=offensive,
            defensive=defensive,
            xg_for=sum(xg_for) / len(xg_for) if valid_xg else offensive,
            xg_against=sum(xg_against) / len(xg_against) if valid_xg else defensive,
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
        max_goals: int = 12,
        use_dixon_coles: bool = False,
        rho: float = 0.0,
    ) -> Dict[Tuple[int, int], float]:
        if home_lambda < 0 or away_lambda < 0 or max_goals < 1:
            raise ValueError("Invalid score-model inputs")
        probabilities = {}
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                probability = (
                    poisson_probability(home_goals, home_lambda)
                    * poisson_probability(away_goals, away_lambda)
                )
                if use_dixon_coles:
                    probability *= dixon_coles_adjustment(
                        home_goals, away_goals, home_lambda, away_lambda, rho
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
        return home_win + draw, draw + away_win, home_win + away_win

    def calculate_over_under(
        self,
        home_lambda: float,
        away_lambda: float,
        thresholds: Optional[List[float]] = None,
    ) -> Dict[float, Tuple[float, float]]:
        total = home_lambda + away_lambda
        return {
            threshold: (
                poisson_over_probability(total, threshold),
                1.0 - poisson_over_probability(total, threshold),
            )
            for threshold in (thresholds or [0.5, 1.5, 2.5, 3.5, 4.5])
        }

    @staticmethod
    def calculate_btts(home_lambda: float, away_lambda: float) -> Tuple[float, float]:
        yes = (1.0 - math.exp(-home_lambda)) * (1.0 - math.exp(-away_lambda))
        return yes, 1.0 - yes

    @staticmethod
    def _signal(selection: str, probability: float) -> Optional[Dict]:
        if probability < 0.60:
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
            model_price_home=1.0 / home_win if home_win > 0 else None,
            model_price_draw=1.0 / draw if draw > 0 else None,
            model_price_away=1.0 / away_win if away_win > 0 else None,
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
