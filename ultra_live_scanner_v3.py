"""Live football probability model with explicit data-quality gates.

Observed xG is never synthesized from shots or score. When available, a
data-gated pre-match goal prior is combined with accumulated live xG using a
documented pseudo-exposure. Outputs are uncalibrated model signals and never a
market-value statement.
"""

import math
from typing import Dict, Optional, Tuple

import streamlit as st


class UltraLiveScanner:
    MATCH_END_MINUTE = 93
    PRIOR_PSEUDO_MINUTES = 30

    def __init__(self, analyzer, api_football):
        self.analyzer = analyzer
        self.api_football = api_football

    @staticmethod
    def _optional_nonnegative(value) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric) or numeric < 0:
            return None
        return numeric

    def _get_prematch_goal_priors(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
    ) -> Tuple[Optional[float], Optional[float]]:
        if self.analyzer is None or not hasattr(self.analyzer, 'engine'):
            return None, None
        league_code = next(
            (
                code
                for code, configured_id in self.analyzer.engine.LEAGUES_CONFIG.items()
                if configured_id == league_id
            ),
            None,
        )
        if league_code is None:
            return None, None
        analysis = self.analyzer.analyze_match(home_team_id, away_team_id, league_code)
        if not analysis or analysis.get('error'):
            return None, None
        details = analysis.get('details', {})
        return (
            self._optional_nonnegative(details.get('expected_home_goals')),
            self._optional_nonnegative(details.get('expected_away_goals')),
        )

    def _remaining_goal_means(
        self,
        xg_home: Optional[float],
        xg_away: Optional[float],
        minute: int,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[float], str]:
        if not isinstance(minute, (int, float)) or minute < 0:
            raise ValueError("minute must be non-negative")
        remaining = max(0.0, self.MATCH_END_MINUTE - float(minute))
        observed = [
            self._optional_nonnegative(xg_home),
            self._optional_nonnegative(xg_away),
        ]
        priors = [
            self._optional_nonnegative(prior_home),
            self._optional_nonnegative(prior_away),
        ]

        means = []
        for observed_xg, prior_full_match in zip(observed, priors):
            rate = None
            if observed_xg is not None and minute > 0:
                if prior_full_match is not None:
                    prior_rate = prior_full_match / self.MATCH_END_MINUTE
                    rate = (
                        prior_rate * self.PRIOR_PSEUDO_MINUTES + observed_xg
                    ) / (self.PRIOR_PSEUDO_MINUTES + float(minute))
                elif minute >= 15:
                    rate = observed_xg / float(minute)
            elif prior_full_match is not None:
                rate = prior_full_match / self.MATCH_END_MINUTE
            means.append(rate * remaining if rate is not None else None)

        if all(value is not None for value in observed) and all(
            value is not None for value in priors
        ):
            quality = 'MEDIUM'
        elif all(value is not None for value in means):
            quality = 'LOW'
        else:
            quality = 'INSUFFICIENT'
        return means[0], means[1], quality

    def analyze_live_match_ultra(self, match: Dict) -> Optional[Dict]:
        try:
            fixture = match['fixture']
            teams = match['teams']
            goals = match['goals']
            league = match['league']

            fixture_id = int(fixture['id'])
            home_team_id = int(teams['home']['id'])
            away_team_id = int(teams['away']['id'])
            minute = int(fixture.get('status', {}).get('elapsed') or 0)
            if goals.get('home') is None or goals.get('away') is None:
                return None
            home_score = int(goals['home'])
            away_score = int(goals['away'])

            stats = self.api_football.get_match_statistics(
                fixture_id,
                home_team_id,
                away_team_id,
            ) if self.api_football is not None else None
            xg_home = self._optional_nonnegative((stats or {}).get('xg_home'))
            xg_away = self._optional_nonnegative((stats or {}).get('xg_away'))
            prior_home, prior_away = self._get_prematch_goal_priors(
                home_team_id,
                away_team_id,
                int(league['id']),
            )

            btts = self._calculate_btts_probability(
                home_score,
                away_score,
                xg_home,
                xg_away,
                minute,
                prior_home,
                prior_away,
            )
            totals = self._calculate_over_under(
                home_score,
                away_score,
                xg_home,
                xg_away,
                minute,
                prior_home,
                prior_away,
            )
            next_goal = self._calculate_next_goal(
                home_score,
                away_score,
                xg_home,
                xg_away,
                minute,
                stats or {},
                prior_home,
                prior_away,
            )

            return {
                'fixture_id': fixture_id,
                'home_team': teams['home']['name'],
                'away_team': teams['away']['name'],
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'minute': minute,
                'score': f"{home_score}-{away_score}",
                'home_score': home_score,
                'away_score': away_score,
                'btts_prob': round(btts['probability'], 1) if btts['probability'] is not None else None,
                'btts_confidence': btts['data_quality'],
                'btts_recommendation': self._get_btts_recommendation(
                    btts['probability'], btts['data_quality']
                ),
                'over_under': {
                    'expected_total_goals': totals['expected_total'],
                    'over_25_probability': totals['over_25_prob'],
                    'thresholds': totals['thresholds'],
                    'recommendation': totals['recommendation'],
                    'confidence': totals['data_quality'],
                },
                'next_goal': next_goal,
                'league': league.get('name', 'Unknown'),
                'breakdown': {
                    'base': btts['base_prob'],
                    'observed_xg_home': xg_home,
                    'observed_xg_away': xg_away,
                    'prematch_home_goal_prior': prior_home,
                    'prematch_away_goal_prior': prior_away,
                    'remaining_home_mean': btts['remaining_home_mean'],
                    'remaining_away_mean': btts['remaining_away_mean'],
                    'game_phase': self._get_phase(minute),
                },
                'stats': stats,
                'xg_data': {
                    'home_xg': xg_home,
                    'away_xg': xg_away,
                    'home_prior': prior_home,
                    'away_prior': prior_away,
                },
                'phase_data': {'phase': self._get_phase(minute)},
                'recommendation_type': 'EXPLORATORY_ESTIMATE',
                'calibrated': False,
                'actionable': False,
            }
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    def _calculate_btts_probability(
        self,
        home_score: int,
        away_score: int,
        xg_home: Optional[float],
        xg_away: Optional[float],
        minute: int,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
    ) -> Dict:
        if home_score > 0 and away_score > 0:
            return {
                'probability': 100.0,
                'data_quality': 'COMPLETE',
                'p_home_scores': 100.0,
                'p_away_scores': 100.0,
                'base_prob': 100.0,
                'remaining_home_mean': 0.0,
                'remaining_away_mean': 0.0,
                'is_complete': True,
            }

        remaining_home, remaining_away, quality = self._remaining_goal_means(
            xg_home,
            xg_away,
            minute,
            prior_home,
            prior_away,
        )
        if remaining_home is None or remaining_away is None:
            return {
                'probability': None,
                'data_quality': 'INSUFFICIENT',
                'p_home_scores': None,
                'p_away_scores': None,
                'base_prob': None,
                'remaining_home_mean': remaining_home,
                'remaining_away_mean': remaining_away,
                'is_complete': False,
            }

        p_home_scores = 100.0 if home_score > 0 else self._poisson_at_least_one(remaining_home)
        p_away_scores = 100.0 if away_score > 0 else self._poisson_at_least_one(remaining_away)
        probability = p_home_scores * p_away_scores / 100.0
        return {
            'probability': max(0.0, min(100.0, probability)),
            'data_quality': quality,
            'p_home_scores': p_home_scores,
            'p_away_scores': p_away_scores,
            'base_prob': probability,
            'remaining_home_mean': remaining_home,
            'remaining_away_mean': remaining_away,
            'is_complete': False,
        }

    @staticmethod
    def _poisson_at_least_one(expected_goals: float) -> float:
        if expected_goals < 0:
            raise ValueError("expected_goals cannot be negative")
        return (1.0 - math.exp(-expected_goals)) * 100.0

    @staticmethod
    def _poisson_at_least_n(expected: float, goals_needed: int) -> float:
        if expected < 0:
            raise ValueError("expected cannot be negative")
        if goals_needed <= 0:
            return 100.0
        probability_below = sum(
            expected ** goals * math.exp(-expected) / math.factorial(goals)
            for goals in range(goals_needed)
        )
        return max(0.0, min(100.0, (1.0 - probability_below) * 100.0))

    def _calculate_over_under(
        self,
        home_score: int,
        away_score: int,
        xg_home: Optional[float],
        xg_away: Optional[float],
        minute: int,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
    ) -> Dict:
        current_goals = home_score + away_score
        remaining_home, remaining_away, quality = self._remaining_goal_means(
            xg_home,
            xg_away,
            minute,
            prior_home,
            prior_away,
        )
        if remaining_home is None or remaining_away is None:
            return {
                'expected_total': None,
                'over_25_prob': None,
                'thresholds': {},
                'recommendation': 'INSUFFICIENT DATA',
                'data_quality': 'INSUFFICIENT',
            }

        remaining_mean = remaining_home + remaining_away
        expected_total = current_goals + remaining_mean
        thresholds = {}
        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            goals_needed = math.floor(threshold) + 1 - current_goals
            over_probability = self._poisson_at_least_n(remaining_mean, goals_needed)
            thresholds[f'over_{threshold}'] = {
                'threshold': threshold,
                'status': 'HIT' if goals_needed <= 0 else 'ACTIVE',
                'over_probability': round(over_probability, 1),
                'under_probability': round(100.0 - over_probability, 1),
                'goals_needed': max(0, goals_needed),
            }

        over_25_probability = thresholds['over_2.5']['over_probability']
        if over_25_probability >= 70:
            recommendation = 'OVER 2.5 EXPLORATORY ESTIMATE'
        elif over_25_probability <= 30:
            recommendation = 'UNDER 2.5 EXPLORATORY ESTIMATE'
        else:
            recommendation = 'NO CLEAR TOTALS SIGNAL'
        return {
            'expected_total': round(expected_total, 2),
            'over_25_prob': over_25_probability,
            'thresholds': thresholds,
            'recommendation': recommendation,
            'data_quality': quality,
        }

    def _poisson_over_threshold(self, expected: float, goals_needed: int) -> float:
        return self._poisson_at_least_n(expected, goals_needed)

    def _calculate_next_goal(
        self,
        home_score: int,
        away_score: int,
        xg_home: Optional[float],
        xg_away: Optional[float],
        minute: int,
        stats: Dict,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
    ) -> Dict:
        remaining_home, remaining_away, quality = self._remaining_goal_means(
            xg_home,
            xg_away,
            minute,
            prior_home,
            prior_away,
        )
        if remaining_home is None or remaining_away is None:
            return {
                'home_prob': None,
                'away_prob': None,
                'no_goal_prob': None,
                'favorite': None,
                'probability_gap': None,
                'recommendation': 'INSUFFICIENT DATA',
                'confidence': 'INSUFFICIENT',
            }

        total_mean = remaining_home + remaining_away
        no_goal_probability = math.exp(-total_mean) * 100.0
        any_goal_probability = 100.0 - no_goal_probability
        if total_mean > 0:
            home_probability = any_goal_probability * remaining_home / total_mean
            away_probability = any_goal_probability * remaining_away / total_mean
        else:
            home_probability = away_probability = 0.0

        favorite = None
        if home_probability > away_probability:
            favorite = 'HOME'
        elif away_probability > home_probability:
            favorite = 'AWAY'
        gap = abs(home_probability - away_probability)
        if favorite and gap >= 20:
            recommendation = f'{favorite} NEXT GOAL EXPLORATORY ESTIMATE'
        elif favorite and gap >= 10:
            recommendation = f'{favorite} SLIGHT MODEL ADVANTAGE'
        else:
            recommendation = 'NO CLEAR NEXT-GOAL SIGNAL'

        return {
            'home_prob': round(home_probability, 1),
            'away_prob': round(away_probability, 1),
            'no_goal_prob': round(no_goal_probability, 1),
            'favorite': favorite,
            'probability_gap': round(gap, 1),
            'recommendation': recommendation,
            'confidence': quality,
        }

    @staticmethod
    def _get_btts_recommendation(probability: Optional[float], data_quality: str) -> str:
        if data_quality == 'COMPLETE':
            return 'BTTS COMPLETE'
        if probability is None:
            return 'INSUFFICIENT DATA'
        if probability >= 70:
            return 'BTTS EXPLORATORY ESTIMATE'
        if probability >= 55:
            return 'WEAK BTTS EXPLORATORY ESTIMATE'
        return 'NO BTTS SIGNAL'

    @staticmethod
    def _get_phase(minute: int) -> str:
        if minute < 15:
            return 'OPENING'
        if minute < 30:
            return 'PROBING'
        if minute < 45:
            return 'PRE_HT'
        if minute < 60:
            return 'POST_HT'
        if minute < 75:
            return 'LATE'
        return 'CLOSING'


def display_ultra_opportunity(match: Dict):
    """Render one API-backed live model result."""
    phase = match.get('breakdown', {}).get('game_phase', 'UNKNOWN')
    quality = match.get('btts_confidence', 'INSUFFICIENT')
    quality_label = {
        'LOW': 'Berechenbar',
        'MEDIUM': 'Live-xG + Prematch',
        'INSUFFICIENT': 'Unzureichend',
        'COMPLETE': 'BTTS bereits eingetreten',
    }.get(quality, quality)
    st.subheader(f"Live {match['minute']}' | {phase}")
    st.write(f"**{match['home_team']} vs {match['away_team']}**")
    st.caption(f"{match['league']} | Score: {match['score']}")

    btts = match.get('btts_prob')
    totals = match.get('over_under', {})
    next_goal = match.get('next_goal', {})
    columns = st.columns(3)
    columns[0].metric(
        "BTTS",
        "Complete" if quality == 'COMPLETE'
        else f"{btts:.1f}%" if btts is not None else "n/a",
    )
    expected_total = totals.get('expected_total_goals')
    columns[1].metric(
        "Expected total",
        f"{expected_total:.2f}" if expected_total is not None else "n/a",
    )
    favorite = next_goal.get('favorite')
    favorite_probability = next_goal.get(
        'home_prob' if favorite == 'HOME' else 'away_prob'
    ) if favorite else None
    columns[2].metric(
        "Next-goal side",
        f"{favorite} {favorite_probability:.1f}%"
        if favorite_probability is not None else "n/a",
    )
    st.caption(
        f"Datenbasis: {quality_label} | "
        "Uncalibrated exploratory estimate; not actionable and no market price checked"
    )
    st.write(match.get('btts_recommendation', 'INSUFFICIENT DATA'))
    st.write(totals.get('recommendation', 'INSUFFICIENT DATA'))
    st.write(next_goal.get('recommendation', 'INSUFFICIENT DATA'))


__all__ = ['UltraLiveScanner', 'display_ultra_opportunity']
