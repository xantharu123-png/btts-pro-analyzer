"""Live football probability model with explicit data-quality gates.

Observed xG is never synthesized from shots or score. When available, a
data-gated pre-match goal prior is combined with accumulated live xG using a
documented pseudo-exposure. Outputs are uncalibrated model signals and never a
market-value statement.
"""

import math
from typing import Dict, List, Optional, Tuple

import streamlit as st

from league_catalog import LEAGUE_BY_ID
from red_card_impact_predictor import RedCardImpactPredictor


class UltraLiveScanner:
    MATCH_END_MINUTE = 93
    PRIOR_PSEUDO_MINUTES = 30
    MAX_RED_CARDS_PER_TEAM = 3
    # Continental competitions and cups never serve as a domestic fallback
    # source: teams carry no season statistics inside them.
    EXCLUDED_FALLBACK_LEAGUE_IDS = frozenset({2, 3, 848, 209})

    def __init__(self, analyzer, api_football):
        self.analyzer = analyzer
        self.api_football = api_football
        self._domestic_league_cache: Dict[int, List[int]] = {}
        self._red_card_minute_cache: Dict[int, Optional[int]] = {}

    @staticmethod
    def _optional_nonnegative(value, maximum: float = 20.0) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric) or numeric < 0 or numeric > maximum:
            return None
        return numeric

    @classmethod
    def _optional_count(cls, value) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if (
            not math.isfinite(numeric)
            or not numeric.is_integer()
            or not 0 <= numeric <= cls.MAX_RED_CARDS_PER_TEAM
        ):
            return None
        return int(numeric)

    @classmethod
    def _red_card_state(
        cls,
        stats: Optional[Dict],
        home_score: Optional[int] = None,
        away_score: Optional[int] = None,
        minute: Optional[int] = None,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
        red_card_minute: Optional[int] = None,
    ) -> Dict:
        """Return a fail-closed red-card adjustment for the remaining match.

        When score/minute/prematch priors are supplied, the flat multipliers
        are context-adjusted (strength damping, bus/attack score state, late
        shell). Without context the historical flat factors apply.
        """
        stats = stats if isinstance(stats, dict) else {}
        home_count = cls._optional_count(stats.get('red_cards_home'))
        away_count = cls._optional_count(stats.get('red_cards_away'))

        base = {
            'home_count': home_count,
            'away_count': away_count,
            'home_factor': 1.0,
            'away_factor': 1.0,
            'detected': bool((home_count or 0) + (away_count or 0)),
            'applied': False,
            'supported': True,
            'inferred_zero_side': None,
            'context': None,
        }
        if home_count is None or away_count is None:
            if base['detected']:
                return {
                    **base,
                    'status': 'INCOMPLETE_DISMISSAL_STATE',
                    'supported': False,
                }
            return {**base, 'status': 'UNAVAILABLE'}
        if home_count == 0 and away_count == 0:
            return {**base, 'status': 'VERIFIED_NONE'}

        # The shared prior is defined for the common 11-v-10 state only.
        if home_count + away_count != 1:
            return {
                **base,
                'status': 'UNSUPPORTED_COMPLEX_DISMISSAL_STATE',
                'supported': False,
            }

        red_card_team = 'home' if home_count == 1 else 'away'
        context = None
        if (
            isinstance(home_score, int)
            and isinstance(away_score, int)
            and isinstance(minute, int)
        ):
            effects = RedCardImpactPredictor.context_adjusted_effects(
                red_card_team,
                home_score,
                away_score,
                minute,
                prior_home_goals=prior_home,
                prior_away_goals=prior_away,
                red_card_minute=red_card_minute,
            )
            context = {
                'strength_ratio': effects['strength_ratio'],
                'goal_diff_red_team': effects['goal_diff_red_team'],
                'minutes_since_card': effects['minutes_since_card'],
                'adjustments': effects['adjustments'],
            }
        else:
            effects = RedCardImpactPredictor.RED_CARD_EFFECTS

        if red_card_team == 'home':
            return {
                **base,
                'status': 'HOME_DISMISSED_ADJUSTED',
                'home_factor': (
                    effects['red_team_penalty']
                    * effects['home_red_extra_penalty']
                ),
                'away_factor': effects['opponent_boost'],
                'applied': True,
                'context': context,
            }
        return {
            **base,
            'status': 'AWAY_DISMISSED_ADJUSTED',
            'home_factor': effects['opponent_boost'],
            'away_factor': (
                effects['red_team_penalty']
                * effects['away_red_extra_penalty']
            ),
            'applied': True,
            'context': context,
        }

    def _get_red_card_minute(
        self,
        fixture_id: int,
        stats: Optional[Dict],
    ) -> Optional[int]:
        """Minute of the first red card, from fixture events (cached).

        Events are only fetched when the statistics actually show a
        dismissal — otherwise the call would waste provider quota. The
        first red card minute is immutable once it happened, so the
        per-fixture cache never goes stale for this purpose.
        """
        stats = stats if isinstance(stats, dict) else {}
        if not (stats.get('red_cards_home') or stats.get('red_cards_away')):
            return None
        if fixture_id in self._red_card_minute_cache:
            return self._red_card_minute_cache[fixture_id]
        minute_found: Optional[int] = None
        try:
            events = self.api_football.get_fixture_events(fixture_id)
        except Exception:
            events = []
        red_minutes = []
        for event in events or []:
            if not isinstance(event, dict):
                continue
            if event.get('type') != 'Card':
                continue
            if 'Red' not in str(event.get('detail') or ''):
                continue
            elapsed = event.get('time', {}).get('elapsed')
            if isinstance(elapsed, int) and not isinstance(elapsed, bool) and elapsed >= 0:
                red_minutes.append(elapsed)
        if red_minutes:
            minute_found = min(red_minutes)
        self._red_card_minute_cache[fixture_id] = minute_found
        return minute_found

    def _resolve_domestic_league_id(self, team_id: int) -> Optional[int]:
        """Resolve a team's domestic league via /teams/leagues (cached).

        Only league-type competitions already present in our catalog qualify;
        continental competitions and cups are excluded because teams carry no
        season statistics inside them.
        """
        if team_id in self._domestic_league_cache:
            cached = self._domestic_league_cache[team_id]
            return cached[0] if cached else None
        candidates: List[int] = []
        try:
            entries = self.api_football.get_team_leagues(team_id)
        except Exception:
            entries = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            league = entry.get('league', {})
            if not isinstance(league, dict):
                continue
            league_id = league.get('id')
            if (
                league.get('type') != 'League'
                or not isinstance(league_id, int)
                or league_id in self.EXCLUDED_FALLBACK_LEAGUE_IDS
                or league_id not in LEAGUE_BY_ID
                or league_id in candidates
            ):
                continue
            candidates.append(league_id)
        self._domestic_league_cache[team_id] = candidates
        return candidates[0] if candidates else None

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
        if league_code is not None:
            analysis = self.analyzer.analyze_match(home_team_id, away_team_id, league_code)
            if analysis and not analysis.get('error'):
                details = analysis.get('details', {})
                priors = (
                    self._optional_nonnegative(details.get('expected_home_goals')),
                    self._optional_nonnegative(details.get('expected_away_goals')),
                )
                if priors != (None, None):
                    return priors
        # Domestic fallback: continental qualifiers pair teams that share no
        # competition, so each side's rates come from its own domestic league.
        home_league_id = self._resolve_domestic_league_id(home_team_id)
        away_league_id = self._resolve_domestic_league_id(away_team_id)
        if home_league_id is None or away_league_id is None:
            return None, None
        if not hasattr(self.analyzer, 'cross_league_expected_goals'):
            return None, None
        lambda_home, lambda_away = self.analyzer.cross_league_expected_goals(
            home_team_id,
            away_team_id,
            home_league_id,
            away_league_id,
        )
        return (
            self._optional_nonnegative(lambda_home),
            self._optional_nonnegative(lambda_away),
        )

    def _remaining_goal_means(
        self,
        xg_home: Optional[float],
        xg_away: Optional[float],
        minute: int,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
        red_card_state: Optional[Dict] = None,
    ) -> Tuple[Optional[float], Optional[float], str]:
        if (
            isinstance(minute, bool)
            or not isinstance(minute, (int, float))
            or not math.isfinite(float(minute))
            or minute < 0
            or minute > self.MATCH_END_MINUTE
        ):
            raise ValueError("minute must be between 0 and 93")
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

        if red_card_state and red_card_state.get('detected'):
            if red_card_state.get('supported') is not True:
                return None, None, 'INSUFFICIENT'
            if all(value is not None for value in means):
                means[0] *= float(red_card_state.get('home_factor', 1.0))
                means[1] *= float(red_card_state.get('away_factor', 1.0))
        elif (
            red_card_state
            and red_card_state.get('status') == 'UNAVAILABLE'
            and quality == 'MEDIUM'
        ):
            quality = 'LOW'
        return means[0], means[1], quality

    def analyze_live_match_ultra(self, match: Dict) -> Optional[Dict]:
        try:
            fixture = match['fixture']
            teams = match['teams']
            goals = match['goals']
            league = match['league']

            raw_fixture_id = fixture.get('id')
            raw_home_team_id = teams.get('home', {}).get('id')
            raw_away_team_id = teams.get('away', {}).get('id')
            raw_league_id = league.get('id')
            identifiers = (
                raw_fixture_id,
                raw_home_team_id,
                raw_away_team_id,
                raw_league_id,
            )
            if any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
                for value in identifiers
            ) or raw_home_team_id == raw_away_team_id:
                return None
            fixture_id = raw_fixture_id
            home_team_id = raw_home_team_id
            away_team_id = raw_away_team_id
            raw_minute = fixture.get('status', {}).get('elapsed')
            raw_home_score = goals.get('home')
            raw_away_score = goals.get('away')
            if (
                raw_minute is None
                or isinstance(raw_minute, bool)
                or not isinstance(raw_minute, int)
                or isinstance(raw_home_score, bool)
                or isinstance(raw_away_score, bool)
                or not isinstance(raw_home_score, int)
                or not isinstance(raw_away_score, int)
            ):
                return None
            minute = raw_minute
            if goals.get('home') is None or goals.get('away') is None:
                return None
            home_score = raw_home_score
            away_score = raw_away_score
            if (
                not 0 <= minute <= self.MATCH_END_MINUTE
                or home_score < 0
                or away_score < 0
                or home_score > 30
                or away_score > 30
            ):
                return None

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
                raw_league_id,
            )
            red_card_minute = self._get_red_card_minute(
                fixture_id, stats
            )
            red_card_state = self._red_card_state(
                stats,
                home_score=home_score,
                away_score=away_score,
                minute=minute,
                prior_home=prior_home,
                prior_away=prior_away,
                red_card_minute=red_card_minute,
            )

            btts = self._calculate_btts_probability(
                home_score,
                away_score,
                xg_home,
                xg_away,
                minute,
                prior_home,
                prior_away,
                red_card_state,
            )
            totals = self._calculate_over_under(
                home_score,
                away_score,
                xg_home,
                xg_away,
                minute,
                prior_home,
                prior_away,
                red_card_state,
            )
            remaining_goals = self._calculate_remaining_goal_markets(
                xg_home,
                xg_away,
                minute,
                prior_home,
                prior_away,
                red_card_state,
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
                red_card_state,
            )
            base_home_mean, base_away_mean, _ = self._remaining_goal_means(
                xg_home,
                xg_away,
                minute,
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
                'live_data_quality': remaining_goals['data_quality'],
                'remaining_goals': remaining_goals,
                'over_under': {
                    'expected_total_goals': totals['expected_total'],
                    'over_25_probability': totals['over_25_prob'],
                    'thresholds': totals['thresholds'],
                    'recommendation': totals['recommendation'],
                    'confidence': totals['data_quality'],
                },
                'next_goal': next_goal,
                'red_cards': red_card_state,
                'league': league.get('name', 'Unknown'),
                'breakdown': {
                    'base': btts['base_prob'],
                    'observed_xg_home': xg_home,
                    'observed_xg_away': xg_away,
                    'prematch_home_goal_prior': prior_home,
                    'prematch_away_goal_prior': prior_away,
                    'remaining_home_mean': btts['remaining_home_mean'],
                    'remaining_away_mean': btts['remaining_away_mean'],
                    'unadjusted_remaining_home_mean': base_home_mean,
                    'unadjusted_remaining_away_mean': base_away_mean,
                    'red_card_home_factor': red_card_state['home_factor'],
                    'red_card_away_factor': red_card_state['away_factor'],
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
        red_card_state: Optional[Dict] = None,
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
            red_card_state,
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
        red_card_state: Optional[Dict] = None,
    ) -> Dict:
        current_goals = home_score + away_score
        remaining_home, remaining_away, quality = self._remaining_goal_means(
            xg_home,
            xg_away,
            minute,
            prior_home,
            prior_away,
            red_card_state,
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

    def _calculate_remaining_goal_markets(
        self,
        xg_home: Optional[float],
        xg_away: Optional[float],
        minute: int,
        prior_home: Optional[float] = None,
        prior_away: Optional[float] = None,
        red_card_state: Optional[Dict] = None,
    ) -> Dict:
        """Calculate markets settled only on goals scored after this snapshot."""
        remaining_home, remaining_away, quality = self._remaining_goal_means(
            xg_home,
            xg_away,
            minute,
            prior_home,
            prior_away,
            red_card_state,
        )
        if remaining_home is None or remaining_away is None:
            return {
                'expected_remaining_goals': None,
                'over_0_5_probability': None,
                'under_0_5_probability': None,
                'over_1_5_probability': None,
                'under_1_5_probability': None,
                'home_scores_probability': None,
                'away_scores_probability': None,
                'team_signal_side': None,
                'team_signal_probability': None,
                'recommendation': 'INSUFFICIENT DATA',
                'data_quality': 'INSUFFICIENT',
            }

        total_mean = remaining_home + remaining_away
        over_05 = self._poisson_at_least_n(total_mean, 1)
        over_15 = self._poisson_at_least_n(total_mean, 2)
        home_scores = self._poisson_at_least_one(remaining_home)
        away_scores = self._poisson_at_least_one(remaining_away)
        if home_scores > away_scores:
            team_side = 'HOME'
            team_probability = home_scores
        elif away_scores > home_scores:
            team_side = 'AWAY'
            team_probability = away_scores
        else:
            team_side = None
            team_probability = home_scores

        if over_05 >= 70.0:
            recommendation = 'AT LEAST ONE MORE GOAL EXPLORATORY ESTIMATE'
        elif over_05 <= 30.0:
            recommendation = 'NO MORE GOAL EXPLORATORY ESTIMATE'
        else:
            recommendation = 'NO CLEAR REMAINING-GOAL SIGNAL'
        return {
            'expected_remaining_goals': round(total_mean, 3),
            'over_0_5_probability': round(over_05, 1),
            'under_0_5_probability': round(100.0 - over_05, 1),
            'over_1_5_probability': round(over_15, 1),
            'under_1_5_probability': round(100.0 - over_15, 1),
            'home_scores_probability': round(home_scores, 1),
            'away_scores_probability': round(away_scores, 1),
            'team_signal_side': team_side,
            'team_signal_probability': round(team_probability, 1),
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
        red_card_state: Optional[Dict] = None,
    ) -> Dict:
        remaining_home, remaining_away, quality = self._remaining_goal_means(
            xg_home,
            xg_away,
            minute,
            prior_home,
            prior_away,
            red_card_state,
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
    phase_label = {
        'OPENING': 'Anfangsphase',
        'PROBING': 'Frühe Phase',
        'PRE_HT': 'Vor der Pause',
        'POST_HT': 'Nach der Pause',
        'LATE': 'Späte Phase',
        'CLOSING': 'Schlussphase',
    }.get(phase, phase)
    quality = match.get('live_data_quality', match.get('btts_confidence', 'INSUFFICIENT'))
    quality_label = {
        'LOW': 'Basis: teilweise Daten',
        'MEDIUM': 'Streng: Live-xG + Prematch',
        'INSUFFICIENT': 'Unzureichend',
        'COMPLETE': 'BTTS bereits eingetreten',
    }.get(quality, quality)
    st.subheader(f"Live {match['minute']}' | {phase_label}")
    st.write(f"**{match['home_team']} vs {match['away_team']}**")
    st.caption(f"{match['league']} | Spielstand: {match['score']}")

    btts = match.get('btts_prob')
    remaining = match.get('remaining_goals', {})
    totals = match.get('over_under', {})
    primary = st.columns(2)
    primary[0].metric(
        "BTTS",
        "Bereits erfüllt" if match.get('btts_confidence') == 'COMPLETE'
        else f"{btts:.1f}%" if btts is not None else "n/a",
    )
    another_goal = remaining.get('over_0_5_probability')
    primary[1].metric(
        "Mindestens 1 weiteres Tor",
        f"{another_goal:.1f}%" if another_goal is not None else "n/a",
    )

    team_goals = st.columns(2)
    home_scores = remaining.get('home_scores_probability')
    away_scores = remaining.get('away_scores_probability')
    team_goals[0].metric(
        f"{match['home_team']} trifft noch",
        f"{home_scores:.1f}%" if home_scores is not None else "n/a",
    )
    team_goals[1].metric(
        f"{match['away_team']} trifft noch",
        f"{away_scores:.1f}%" if away_scores is not None else "n/a",
    )

    red_cards = match.get('red_cards') or {}
    if red_cards.get('detected') and red_cards.get('supported') is not True:
        st.error(
            "Nicht vollständig unterstützter Platzverweis-Zustand: Die "
            "Restspiel-Prognose ist gesperrt, "
            "weil das Modell diesen Mannschaftsbestand nicht verlässlich abbildet."
        )
    elif red_cards.get('applied'):
        st.warning(
            "Platzverweis erkannt: Die Resttor-Raten wurden für 11 gegen 10 neu "
            "berechnet. Der verwendete Wirkungsabschlag ist noch nicht kalibriert."
        )

    no_more = remaining.get('under_0_5_probability')
    over_15 = remaining.get('over_1_5_probability')
    expected_remaining = remaining.get('expected_remaining_goals')
    detail_parts = []
    if no_more is not None:
        detail_parts.append(f"Kein weiteres Tor {no_more:.1f}%")
    if over_15 is not None:
        detail_parts.append(f"Mindestens 2 weitere Tore {over_15:.1f}%")
    if expected_remaining is not None:
        detail_parts.append(f"Erwartete Resttore {expected_remaining:.2f}")
    if detail_parts:
        st.caption(" | ".join(detail_parts))

    expected_total = totals.get('expected_total_goals')
    over_25 = totals.get('over_25_probability')
    if expected_total is not None and over_25 is not None:
        st.caption(
            f"Gesamtspiel inklusive aktuellem Stand: Erwartete Tore {expected_total:.2f} | "
            f"Über 2,5 {over_25:.1f}%"
        )
    st.caption(
        f"Datenbasis: {quality_label} | "
        "Unkalibrierte Modellschätzung; keine Wettfreigabe und keine Quote geprüft."
    )
    st.caption(
        "Restspiel bedeutet: Es zählen nur Tore nach diesem Snapshot. Ein normales "
        "Live-Over/Under berücksichtigt dagegen den bereits vorhandenen Spielstand."
    )


__all__ = ['UltraLiveScanner', 'display_ultra_opportunity']
