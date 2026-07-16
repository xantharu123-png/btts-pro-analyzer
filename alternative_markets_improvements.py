"""Conservative compatibility helpers for alternative-market analysis.

No referee, derby, or weather multiplier is applied without a versioned data
source and chronological validation. H2H data is descriptive only.
"""

import math
from typing import Dict, List, Optional, Tuple


class RefereeDatabase:
    """Compatibility interface; no unverifiable embedded referee data."""

    REFEREE_STATS: Dict[str, Dict] = {}
    LEAGUE_DEFAULTS: Dict[int, Dict] = {}

    @classmethod
    def get_referee_stats(
        cls,
        referee_name: str,
        league_id: Optional[int] = None,
    ) -> Dict:
        return {
            'cards': None,
            'yellows': None,
            'reds': None,
            'fouls': None,
            'sample_size': 0,
            'source': None,
        }

    @classmethod
    def has_referee_data(cls, referee_name: str) -> bool:
        return False


class H2HAnalyzer:
    """Parse completed H2H fixtures without changing another model's output."""

    def __init__(self, api_football_client=None):
        self.api = api_football_client
        self.h2h_cache = {}

    @staticmethod
    def _empty_stats() -> Dict:
        return {
            'matches_played': 0,
            'home_wins': 0,
            'draws': 0,
            'away_wins': 0,
            'home_win_rate': None,
            'draw_rate': None,
            'away_win_rate': None,
            'avg_goals': None,
            'btts_rate': None,
            'over_25_rate': None,
            'avg_cards': None,
            'avg_corners': None,
            'last_5': [],
        }

    def get_h2h_stats(
        self,
        home_team_id: int,
        away_team_id: int,
        last_n: int = 10,
    ) -> Dict:
        cache_key = (home_team_id, away_team_id, last_n)
        if cache_key in self.h2h_cache:
            return self.h2h_cache[cache_key]
        if self.api is None:
            return self._empty_stats()
        try:
            fixtures = self.api.get_h2h(home_team_id, away_team_id, last_n)
        except Exception:
            return self._empty_stats()
        result = self._parse_h2h_data(
            fixtures or [],
            last_n,
            home_team_id,
            away_team_id,
        )
        self.h2h_cache[cache_key] = result
        return result

    def _parse_h2h_data(
        self,
        data: List,
        last_n: int,
        home_team_id: int,
        away_team_id: int,
    ) -> Dict:
        completed = []
        for match in data[:last_n]:
            goals = match.get('goals', {})
            fixture_home_id = match.get('teams', {}).get('home', {}).get('id')
            fixture_away_id = match.get('teams', {}).get('away', {}).get('id')
            fixture_home_score = goals.get('home')
            fixture_away_score = goals.get('away')
            if (
                not isinstance(fixture_home_score, int)
                or not isinstance(fixture_away_score, int)
                or fixture_home_score < 0
                or fixture_away_score < 0
            ):
                continue
            if fixture_home_id == home_team_id and fixture_away_id == away_team_id:
                home_score, away_score = fixture_home_score, fixture_away_score
            elif fixture_home_id == away_team_id and fixture_away_id == home_team_id:
                home_score, away_score = fixture_away_score, fixture_home_score
            else:
                continue
            completed.append((home_score, away_score))

        if not completed:
            return self._empty_stats()

        home_wins = sum(home > away for home, away in completed)
        draws = sum(home == away for home, away in completed)
        away_wins = sum(home < away for home, away in completed)
        sample = len(completed)
        return {
            'matches_played': sample,
            'home_wins': home_wins,
            'draws': draws,
            'away_wins': away_wins,
            'home_win_rate': home_wins / sample,
            'draw_rate': draws / sample,
            'away_win_rate': away_wins / sample,
            'avg_goals': sum(home + away for home, away in completed) / sample,
            'btts_rate': sum(home > 0 and away > 0 for home, away in completed) / sample,
            'over_25_rate': sum(home + away >= 3 for home, away in completed) / sample,
            'avg_cards': None,
            'avg_corners': None,
            'last_5': [
                {
                    'home_score': home,
                    'away_score': away,
                    'btts': home > 0 and away > 0,
                }
                for home, away in completed[:5]
            ],
        }

    def adjust_prediction_with_h2h(
        self,
        base_prediction: Dict,
        h2h_stats: Dict,
        weight: float = 0.15,
    ) -> Dict:
        result = dict(base_prediction)
        result['h2h_adjusted'] = False
        result['h2h_matches'] = h2h_stats.get('matches_played', 0)
        return result


class DerbyDetector:
    """Compatibility interface; rivalry labels do not alter probabilities."""

    @classmethod
    def is_derby(cls, home_team: str, away_team: str) -> Tuple[bool, float]:
        return False, 1.0


class ImprovedCardsPredictor:
    """Poisson baseline available only from observed team card samples."""

    def __init__(self, api_football=None):
        self.api = api_football

    @staticmethod
    def _optional_nonnegative(value) -> Optional[float]:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) and numeric >= 0 else None

    @staticmethod
    def _poisson_over(expected: float, threshold: float) -> float:
        floor_threshold = math.floor(threshold)
        probability_below = sum(
            math.exp(-expected) * expected ** k / math.factorial(k)
            for k in range(floor_threshold + 1)
        )
        return max(0.0, min(1.0, 1.0 - probability_below))

    def predict_cards(self, fixture: Dict) -> Dict:
        home_average = self._optional_nonnegative(fixture.get('home_cards_avg'))
        away_average = self._optional_nonnegative(fixture.get('away_cards_avg'))
        home_sample = fixture.get('home_card_matches', 0)
        away_sample = fixture.get('away_card_matches', 0)
        if (
            home_average is None
            or away_average is None
            or not isinstance(home_sample, int)
            or not isinstance(away_sample, int)
            or min(home_sample, away_sample) < 5
        ):
            return {
                'expected_cards': None,
                'thresholds': {},
                'best_bet': None,
                'data_quality': 'INSUFFICIENT_DATA',
                'calibrated': False,
            }

        expected = home_average + away_average
        thresholds = {}
        for threshold in (2.5, 3.5, 4.5, 5.5, 6.5):
            over_probability = self._poisson_over(expected, threshold)
            thresholds[f'over_{threshold}'] = {
                'probability': round(over_probability * 100.0, 1),
            }
            thresholds[f'under_{threshold}'] = {
                'probability': round((1.0 - over_probability) * 100.0, 1),
            }
        return {
            'expected_cards': round(expected, 2),
            'thresholds': thresholds,
            'best_bet': None,
            'data_quality': 'LIMITED_MODEL',
            'calibrated': False,
        }


def unified_dixon_coles_adjustment(
    home_goals: int,
    away_goals: int,
    home_lambda: float,
    away_lambda: float,
    rho: float = 0.0,
) -> float:
    """Return a Dixon-Coles tau value for an explicitly supplied ``rho``."""
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


class WeatherImpact:
    """Compatibility interface; weather is descriptive until validated."""

    @staticmethod
    def adjust_corners_for_weather(
        expected_corners: float,
        wind_speed: float = 0,
        rain: bool = False,
        temperature: float = 15,
    ) -> float:
        if not math.isfinite(float(expected_corners)) or expected_corners < 0:
            raise ValueError("expected_corners must be finite and non-negative")
        return float(expected_corners)


__all__ = [
    'RefereeDatabase',
    'H2HAnalyzer',
    'DerbyDetector',
    'ImprovedCardsPredictor',
    'unified_dixon_coles_adjustment',
    'WeatherImpact',
]
