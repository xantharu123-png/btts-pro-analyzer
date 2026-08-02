"""Market-price evaluation with calibration, quote, and Kelly gates.

Model signals remain independent from bookmaker prices. Same-match combos are
disabled until a dependency model has been validated.
"""

import streamlit as st
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import requests
from difflib import SequenceMatcher
import time
import os
import math
from datetime import datetime, timezone

from betting_math import (
    MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
    BettingMathError,
    evaluate_market_price,
    proportional_no_vig_market,
    validate_decimal_odds,
    validate_probability_percent,
)


def _optional_point(value) -> Optional[float]:
    try:
        point = float(value)
    except (TypeError, ValueError):
        return None
    return point if math.isfinite(point) and point > 0 else None


@dataclass
class SmartBet:
    """Struktur für eine Smart Bet Empfehlung"""
    market: str
    sub_market: str
    probability: float
    signal_strength: str
    edge: Optional[float]
    expected_roi: Optional[float]
    reasoning: str
    stake_recommendation: str
    risk_level: str
    real_odds: Optional[float] = None
    bookmaker: Optional[str] = None
    quote_source: Optional[str] = None
    quoted_at: Optional[str] = None
    calibration_method: Optional[str] = None
    calibration_sample: Optional[int] = None
    risk_adjusted_probability: Optional[float] = None
    calibration_haircut: Optional[float] = None
    point_edge: Optional[float] = None
    point_expected_roi: Optional[float] = None
    market_overround: Optional[float] = None
    no_vig_market_probability: Optional[float] = None
    model_market_gap: Optional[float] = None
    kelly_stake: Optional[float] = None
    recommendation_type: str = 'EXPLORATORY_ESTIMATE'
    calibrated: bool = False
    actionable: bool = False
    price_passed: bool = False
    evidence_stage: str = 'RESEARCH'
    
    def to_dict(self):
        return {
            'market': self.market,
            'sub_market': self.sub_market,
            'probability': self.probability,
            'signal_strength': self.signal_strength,
            'edge': self.edge,
            'expected_roi': self.expected_roi,
            'reasoning': self.reasoning,
            'stake_recommendation': self.stake_recommendation,
            'risk_level': self.risk_level,
            'real_odds': self.real_odds,
            'bookmaker': self.bookmaker,
            'quote_source': self.quote_source,
            'quoted_at': self.quoted_at,
            'calibration_method': self.calibration_method,
            'calibration_sample': self.calibration_sample,
            'risk_adjusted_probability': self.risk_adjusted_probability,
            'calibration_haircut': self.calibration_haircut,
            'point_edge': self.point_edge,
            'point_expected_roi': self.point_expected_roi,
            'market_overround': self.market_overround,
            'no_vig_market_probability': self.no_vig_market_probability,
            'model_market_gap': self.model_market_gap,
            'kelly_stake': self.kelly_stake,
            'recommendation_type': self.recommendation_type,
            'calibrated': self.calibrated,
            'actionable': self.actionable,
            'price_passed': self.price_passed,
            'evidence_stage': self.evidence_stage,
        }

    @property
    def confidence(self) -> str:
        """Backward-compatible alias; this is not calibrated confidence."""
        return self.signal_strength


class OddsAPIClient:
    """
    Client für echte Bookmaker Odds
    
    Unterstützte APIs:
    - The Odds API (https://the-odds-api.com/)
    - API-Football Odds
    """
    
    def __init__(self, odds_api_key: str = None, api_football_key: str = None):
        self.odds_api_key = odds_api_key or os.environ.get('ODDS_API_KEY')
        self.api_football_key = api_football_key or os.environ.get('API_FOOTBALL_KEY')
        self.odds_cache = {}
        self.cache_timeout = 300  # 5 minutes
        
    def get_match_odds(self, home_team: str, away_team: str,
                       sport: str = 'soccer', league: str = None,
                       fixture_id: Optional[int] = None,
                       league_id: Optional[int] = None,
                       fixture_date: Optional[str] = None) -> Dict:
        """
        Get real odds from multiple bookmakers
        
        Returns: {
            'btts_yes': {'best_odds': 1.95, 'bookmaker': 'Bet365', 'all_odds': {...}},
            'btts_no': {...},
            'home_win': {...},
            ...
        }
        """
        cache_key = (
            self._normalize_team_name(home_team),
            self._normalize_team_name(away_team),
            sport,
            league,
            fixture_id,
            league_id,
            fixture_date,
        )
        cached = self.odds_cache.get(cache_key)
        if cached and time.monotonic() - cached['stored_at'] < self.cache_timeout:
            return cached['odds']

        result = {}
        
        # API-Football supports exact fixture lookup and is therefore preferred.
        if self.api_football_key and fixture_id:
            try:
                odds = self._get_api_football_odds(fixture_id)
                if odds:
                    self._merge_odds(result, odds)
            except Exception as e:
                print(f"API-Football odds error: {e}")

        odds_sport_keys = {
            39: 'soccer_epl',
            78: 'soccer_germany_bundesliga',
            140: 'soccer_spain_la_liga',
            135: 'soccer_italy_serie_a',
            61: 'soccer_france_ligue_one',
        }
        sport_key = odds_sport_keys.get(league_id)
        if self.odds_api_key and fixture_id and sport_key and fixture_date:
            try:
                odds = self._get_from_odds_api(
                    home_team,
                    away_team,
                    sport_key,
                    fixture_date,
                )
                if odds:
                    self._merge_odds(result, odds)
            except Exception as e:
                print(f"The Odds API error: {e}")
        
        self.odds_cache[cache_key] = {
            'stored_at': time.monotonic(),
            'odds': result,
        }
        return result
    
    def _get_from_odds_api(self, home_team: str, away_team: str,
                           sport_key: str, fixture_date: str) -> Dict:
        """Get odds from The Odds API"""
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        params = {
            'apiKey': self.odds_api_key,
            'regions': 'eu',
            'markets': 'h2h,totals,btts',
            'oddsFormat': 'decimal'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if not isinstance(data, list):
                return {}
            
            # Find matching game
            for game in data:
                if (self._match_team_name(home_team, game.get('home_team', '')) and
                    self._match_team_name(away_team, game.get('away_team', '')) and
                    self._kickoff_matches(fixture_date, game.get('commence_time'))):
                    return self._parse_odds_api_response(game)
        
        return {}
    
    def _get_api_football_odds(self, fixture_id: int) -> Dict:
        """Get odds for specific fixture from API-Football"""
        headers = {'x-apisports-key': self.api_football_key}
        url = f"https://v3.football.api-sports.io/odds"
        params = {'fixture': fixture_id}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, dict) or data.get('errors'):
                    return {}
                return self._parse_api_football_odds(data.get('response', []))
        except (requests.RequestException, ValueError):
            pass
        
        return {}
    
    def _match_team_name(self, name1: str, name2: str) -> bool:
        """Conservatively match normalized team names."""
        n1 = self._normalize_team_name(name1)
        n2 = self._normalize_team_name(name2)
        if not n1 or not n2:
            return False
        return n1 == n2 or SequenceMatcher(None, n1, n2).ratio() >= 0.90

    @staticmethod
    def _kickoff_matches(expected: str, actual: str, tolerance_hours: float = 2.0) -> bool:
        if (
            isinstance(tolerance_hours, bool)
            or not isinstance(tolerance_hours, (int, float))
            or not math.isfinite(float(tolerance_hours))
            or tolerance_hours < 0
        ):
            return False
        try:
            expected_time = datetime.fromisoformat(expected.replace('Z', '+00:00'))
            actual_time = datetime.fromisoformat(actual.replace('Z', '+00:00'))
        except (AttributeError, TypeError, ValueError):
            return False
        if expected_time.tzinfo is None or actual_time.tzinfo is None:
            return False
        return abs((expected_time - actual_time).total_seconds()) <= tolerance_hours * 3600

    def _merge_odds(self, target: Dict, incoming: Dict) -> None:
        for market, quote in incoming.items():
            for bookmaker, odds in (quote.get('all_odds') or {}).items():
                self._update_best_odds(
                    target,
                    market,
                    odds,
                    bookmaker,
                    source=quote.get('source'),
                    quoted_at=quote.get('quoted_at'),
                )

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        normalized = ''.join(ch.lower() if ch.isalnum() else ' ' for ch in name or '')
        ignored = {'fc', 'cf', 'sc', 'afc', 'club'}
        return ' '.join(part for part in normalized.split() if part not in ignored)
    
    def _parse_odds_api_response(self, game: Dict) -> Dict:
        """Parse The Odds API response"""
        result = {}
        if not isinstance(game, dict):
            return result
        
        for bookmaker in game.get('bookmakers', []):
            bookie_name = str(bookmaker.get('title') or '').strip()
            if not bookie_name:
                continue
            
            for market in bookmaker.get('markets', []):
                market_key = market.get('key', '')
                quoted_at = market.get('last_update') or bookmaker.get('last_update')

                def update(selection: str, price) -> None:
                    self._update_best_odds(
                        result,
                        selection,
                        price,
                        bookie_name,
                        source='the_odds_api',
                        quoted_at=quoted_at,
                    )
                
                for outcome in market.get('outcomes', []):
                    price = outcome.get('price')
                    name = str(outcome.get('name') or '').lower()
                    
                    if market_key == 'h2h':
                        if self._match_team_name(name, game.get('home_team', '')):
                            update('home_win', price)
                        elif self._match_team_name(name, game.get('away_team', '')):
                            update('away_win', price)
                        elif name in {'draw', 'tie'}:
                            update('draw', price)
                    
                    elif market_key == 'totals':
                        point = _optional_point(outcome.get('point'))
                        if point is None:
                            continue
                        if 'over' in name:
                            update(f'over_{point}', price)
                        elif 'under' in name:
                            update(f'under_{point}', price)
                    
                    elif market_key == 'btts':
                        if 'yes' in name:
                            update('btts_yes', price)
                        elif 'no' in name:
                            update('btts_no', price)
        
        return result
    
    def _parse_api_football_odds(self, response: List) -> Dict:
        """Parse API-Football odds response"""
        result = {}
        if not isinstance(response, list):
            return result
        
        for entry in response:
            quoted_at = entry.get('update')
            for bookmaker in entry.get('bookmakers', []):
                bookie_name = str(bookmaker.get('name') or '').strip()
                if not bookie_name:
                    continue

                def update(selection: str, odd) -> None:
                    self._update_best_odds(
                        result,
                        selection,
                        odd,
                        bookie_name,
                        source='api_football',
                        quoted_at=quoted_at,
                    )
                
                for bet in bookmaker.get('bets', []):
                    bet_name = str(bet.get('name') or '').lower()
                    
                    for value in bet.get('values', []):
                        odd = value.get('odd')
                        val = str(value.get('value') or '').lower()
                        
                        if 'match winner' in bet_name:
                            if val == 'home':
                                update('home_win', odd)
                            elif val == 'draw':
                                update('draw', odd)
                            elif val == 'away':
                                update('away_win', odd)
                        
                        elif 'both teams score' in bet_name:
                            if val == 'yes':
                                update('btts_yes', odd)
                            elif val == 'no':
                                update('btts_no', odd)
                        
                        elif 'goals over/under' in bet_name:
                            if 'over' in val:
                                threshold = val.replace('over ', '')
                                update(f'over_{threshold}', odd)
                            elif 'under' in val:
                                threshold = val.replace('under ', '')
                                update(f'under_{threshold}', odd)
        
        return result
    
    def _update_best_odds(
        self,
        result: Dict,
        market: str,
        odds: float,
        bookmaker: str,
        *,
        source: Optional[str] = None,
        quoted_at: Optional[str] = None,
    ):
        """Update result with best odds for market"""
        try:
            odds = validate_decimal_odds(odds)
        except BettingMathError:
            return
        if not bookmaker:
            return

        if market not in result:
            result[market] = {
                'best_odds': odds,
                'bookmaker': bookmaker,
                'all_odds': {},
                'source': source,
                'quoted_at': quoted_at,
            }
        
        result[market]['all_odds'][bookmaker] = odds
        
        if odds > result[market]['best_odds']:
            result[market]['best_odds'] = odds
            result[market]['bookmaker'] = bookmaker
            result[market]['source'] = source
            result[market]['quoted_at'] = quoted_at


class SmartBetFinder:
    """Evaluate validated probabilities against verified external prices."""
    
    def __init__(self, odds_api_key: str = None, api_football_key: str = None):
        self.odds_client = OddsAPIClient(odds_api_key, api_football_key)
    
    def get_odds(self, market: str, home_team: str = None,
                 away_team: str = None, market_odds: Optional[Dict] = None,
                 fixture_id: Optional[int] = None,
                 sport: str = 'soccer') -> Tuple[Optional[float], str, bool]:
        """
        Get odds for market.

        Model probabilities are calculated independently. Odds are used only
        afterwards as market price for edge, ROI, and Kelly staking.
        
        Returns: (odds, bookmaker, is_real_odds)
        """
        if market_odds is None and home_team and away_team:
            market_odds = self.odds_client.get_match_odds(
                home_team,
                away_team,
                sport=sport,
                fixture_id=fixture_id,
            )

        quote = (market_odds or {}).get(market)
        if quote:
            bookmaker = str(quote.get('bookmaker') or '').strip()
            source = str(quote.get('source') or '').strip()
            quoted_at = quote.get('quoted_at')
            try:
                odds = validate_decimal_odds(quote.get('best_odds'))
                bookmaker_odds = validate_decimal_odds(
                    (quote.get('all_odds') or {}).get(bookmaker)
                )
            except BettingMathError:
                odds = None
                bookmaker_odds = None
            if (
                odds is not None
                and bookmaker_odds is not None
                and math.isclose(odds, bookmaker_odds, rel_tol=0.0, abs_tol=1e-9)
                and bookmaker
                and source
                and self._quote_is_fresh(quoted_at)
            ):
                return odds, bookmaker, True
        
        return (None, 'NO_MARKET_PRICE', False)

    @staticmethod
    def _utc_datetime(value) -> Optional[datetime]:
        try:
            timestamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                return None
            return timestamp.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _quote_is_fresh(cls, quoted_at, max_age_seconds: int = 600) -> bool:
        timestamp = cls._utc_datetime(quoted_at)
        if timestamp is None:
            return False
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        return -60 <= age <= max_age_seconds

    @classmethod
    def _validated_markets(cls, analysis_results: Dict) -> Dict[str, Dict]:
        validations = analysis_results.get('market_validation') or {}
        eligible = {}
        if not isinstance(validations, dict):
            return eligible
        league_id = analysis_results.get('league_id')
        fixture_time = cls._utc_datetime(analysis_results.get('fixture_date'))
        if (
            not isinstance(league_id, int)
            or isinstance(league_id, bool)
            or league_id <= 0
            or fixture_time is None
            or fixture_time <= datetime.now(timezone.utc)
        ):
            return eligible
        for market, metadata in validations.items():
            if not isinstance(metadata, dict):
                continue
            integer_values = (
                metadata.get('sample_size'),
                metadata.get('calibration_bins'),
                metadata.get('min_bin_size'),
            )
            decimal_values = (
                metadata.get('expected_calibration_error'),
                metadata.get('max_calibration_error'),
                metadata.get('calibration_coverage'),
            )
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not float(value).is_integer()
                for value in integer_values
            ) or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in decimal_values
            ):
                continue
            try:
                sample_size = int(integer_values[0])
                calibration_bins = int(integer_values[1])
                minimum_bin_size = int(integer_values[2])
                ece = float(decimal_values[0])
                max_deviation = float(decimal_values[1])
                calibration_coverage = float(decimal_values[2])
            except (TypeError, ValueError):
                continue
            validation_start = cls._utc_datetime(metadata.get('validation_start'))
            validation_end = cls._utc_datetime(metadata.get('validation_end'))
            raw_league_ids = metadata.get('league_ids')
            if not isinstance(raw_league_ids, (list, tuple, set)):
                continue
            if any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or item <= 0
                for item in raw_league_ids
            ):
                continue
            league_ids = set(raw_league_ids)
            if (
                metadata.get('calibrated') is True
                and metadata.get('out_of_sample') is True
                and sample_size >= 200
                and calibration_bins >= 3
                and minimum_bin_size >= 20
                and minimum_bin_size <= sample_size
                and calibration_bins * minimum_bin_size <= sample_size
                and 0.0 <= ece < 0.05
                and 0.0 <= max_deviation < 0.10
                and 0.80 <= calibration_coverage <= 1.0
                and validation_start is not None
                and validation_end is not None
                and validation_start < validation_end < fixture_time
                and validation_end <= datetime.now(timezone.utc)
                and league_id in league_ids
                and str(metadata.get('method') or '').strip()
                and str(metadata.get('model_version') or '').strip()
            ):
                normalized = dict(metadata)
                normalized.update({
                    'sample_size': sample_size,
                    'expected_calibration_error': ece,
                    'max_calibration_error': max_deviation,
                    'calibration_coverage': calibration_coverage,
                    'calibration_bins': calibration_bins,
                    'min_bin_size': minimum_bin_size,
                    'validation_start': validation_start.isoformat(),
                    'validation_end': validation_end.isoformat(),
                    'league_ids': sorted(league_ids),
                })
                eligible[str(market)] = normalized
        return eligible

    @staticmethod
    def _market_group(market: str) -> Optional[Tuple[str, ...]]:
        if market in {'btts_yes', 'btts_no'}:
            return ('btts_yes', 'btts_no')
        if market in {'home_win', 'draw', 'away_win'}:
            return ('home_win', 'draw', 'away_win')
        if market.startswith('over_'):
            return (market, f"under_{market.removeprefix('over_')}")
        if market.startswith('under_'):
            return (f"over_{market.removeprefix('under_')}", market)
        return None

    @classmethod
    def _market_overround(
        cls,
        market: str,
        market_odds: Dict,
        bookmaker: str,
    ) -> Optional[float]:
        """Validate all sides of one book's market without using them as features."""
        group = cls._market_group(market)
        if group is None:
            return None
        selected_quote = market_odds.get(market)
        if not isinstance(selected_quote, dict):
            return None
        reference_source = str(selected_quote.get('source') or '').strip()
        if not reference_source:
            return None
        prices = []
        for selection in group:
            quote = market_odds.get(selection)
            if not isinstance(quote, dict):
                return None
            if (
                str(quote.get('source') or '').strip() != reference_source
                or not cls._quote_is_fresh(quote.get('quoted_at'))
            ):
                return None
            all_odds = quote.get('all_odds')
            if not isinstance(all_odds, dict):
                return None
            try:
                prices.append(validate_decimal_odds(all_odds.get(bookmaker)))
            except BettingMathError:
                return None
        overround = sum(1.0 / price for price in prices)
        if not math.isfinite(overround) or not 0.98 <= overround <= 1.25:
            return None
        return overround

    @classmethod
    def _no_vig_market_probability(
        cls,
        market: str,
        market_odds: Dict,
        bookmaker: str,
    ) -> Optional[float]:
        """Return the selected side's de-vigged benchmark probability."""
        group = cls._market_group(market)
        if group is None:
            return None
        selected_quote = market_odds.get(market)
        if not isinstance(selected_quote, dict):
            return None
        reference_source = str(selected_quote.get('source') or '').strip()
        if not reference_source:
            return None
        prices = []
        for selection in group:
            quote = market_odds.get(selection)
            if not isinstance(quote, dict):
                return None
            if (
                str(quote.get('source') or '').strip() != reference_source
                or not cls._quote_is_fresh(quote.get('quoted_at'))
            ):
                return None
            try:
                prices.append(
                    validate_decimal_odds(
                        (quote.get('all_odds') or {}).get(bookmaker)
                    )
                )
            except BettingMathError:
                return None
        try:
            no_vig = proportional_no_vig_market(prices)
        except BettingMathError:
            return None
        if not 0.98 <= no_vig.overround <= 1.25:
            return None
        return no_vig.no_vig_probabilities[group.index(market)] * 100.0
    
    def _calculate_edge(self, probability: float, odds: Optional[float]) -> Optional[float]:
        """
        Berechne Edge (Vorteil gegenüber Bookmaker)
        
        Edge = Model Probability - Implied Probability
        """
        if odds is None:
            return None
        try:
            return evaluate_market_price(probability, odds).edge
        except BettingMathError:
            return None
    
    def _calculate_expected_roi(self, probability: float, odds: Optional[float]) -> Optional[float]:
        """
        Berechne Expected ROI
        
        ROI = (Probability × (Odds - 1)) - (1 - Probability)
        """
        if odds is None:
            return None
        try:
            return evaluate_market_price(probability, odds).expected_roi
        except BettingMathError:
            return None
    
    def _calculate_kelly_stake(
        self,
        probability: float,
        odds: Optional[float],
        fraction: float = 0.25,
        probability_haircut: float = 0.0,
    ) -> float:
        """
        Kelly Criterion für optimale Stake-Größe
        
        Kelly % = (bp - q) / b
        where:
        - b = decimal odds - 1
        - p = probability of winning
        - q = probability of losing (1 - p)
        
        fraction: Use fractional Kelly (0.25 = quarter Kelly) for safety
        """
        if odds is None:
            return 0.0
        try:
            metrics = evaluate_market_price(
                probability,
                odds,
                probability_haircut=probability_haircut,
                kelly_fraction=fraction,
                kelly_cap=0.02,
            )
        except BettingMathError:
            return 0.0
        return round(metrics.kelly_fraction * 100.0, 2)
    
    def _get_risk_level(self, probability: float, edge: float) -> str:
        """Bestimme Risiko-Level"""
        return 'UNQUANTIFIED_MODEL_RISK'
    
    def _get_stake_recommendation(self, probability: float, edge: float, 
                                   kelly_stake: float = None) -> str:
        """Stake Empfehlung basierend auf Kelly und Edge"""
        if kelly_stake is None:
            return 'NO STAKE - NO VERIFIED PRICE'
        if kelly_stake <= 0:
            return 'NO BET (non-positive Kelly)'
        return (
            f'{kelly_stake:.1f}% bankroll (quarter Kelly on risk-adjusted '
            'probability, 2% cap, one selection per fixture)'
        )
    
    def find_value_bets(self, analysis_results: Dict, 
                        home_team: str = None,
                        away_team: str = None) -> List[SmartBet]:
        """
        Finde Value Bets aus allen Märkten.

        Der gemeinsame Standard nutzt ausschließlich den risikoadjustierten
        Erwartungswert; eine feste PP-Schwelle ist nicht über Quoten
        vergleichbar.
        """
        value_bets = []
        
        # Sammle alle Wahrscheinlichkeiten
        markets = self._extract_all_probabilities(analysis_results)
        validated_markets = self._validated_markets(analysis_results)
        fixture_id = analysis_results.get('fixture_id')
        league_id = analysis_results.get('league_id')
        fixture_date = analysis_results.get('fixture_date')
        market_odds = {}
        valid_fixture_id = (
            isinstance(fixture_id, int)
            and not isinstance(fixture_id, bool)
            and fixture_id > 0
        )
        if home_team and away_team and valid_fixture_id:
            market_odds = self.odds_client.get_match_odds(
                home_team,
                away_team,
                fixture_id=fixture_id,
                league_id=league_id,
                fixture_date=fixture_date,
            )
        
        for market, prob in markets.items():
            validation = validated_markets.get(market)
            if validation is None:
                continue
            odds, bookmaker, is_real = self.get_odds(
                market,
                home_team,
                away_team,
                market_odds=market_odds,
            )
            if not is_real:
                continue

            overround = self._market_overround(market, market_odds, bookmaker)
            no_vig_probability = self._no_vig_market_probability(
                market,
                market_odds,
                bookmaker,
            )
            if overround is None or no_vig_probability is None:
                continue
            haircut = float(validation['max_calibration_error']) * 100.0
            try:
                metrics = evaluate_market_price(
                    prob,
                    odds,
                    probability_haircut=haircut,
                    kelly_fraction=0.25,
                    kelly_cap=0.02,
                )
            except BettingMathError:
                continue

            if (
                metrics.risk_adjusted_expected_roi
                >= MINIMUM_RISK_ADJUSTED_ROI_PERCENT
                and metrics.kelly_fraction > 0.0
            ):
                kelly = round(metrics.kelly_fraction * 100.0, 2)
                bet = SmartBet(
                    market=self._get_market_category(market),
                    sub_market=market,
                    probability=prob,
                    signal_strength=(
                        'HIGH' if metrics.risk_adjusted_probability >= 70
                        else 'MEDIUM' if metrics.risk_adjusted_probability >= 55
                        else 'LOW'
                    ),
                    edge=round(metrics.risk_adjusted_edge, 1),
                    expected_roi=round(metrics.risk_adjusted_expected_roi, 1),
                    reasoning=self._generate_reasoning(
                        market,
                        prob,
                        metrics.risk_adjusted_probability,
                        haircut,
                        metrics.risk_adjusted_edge,
                        metrics.edge,
                        is_real,
                    ),
                    stake_recommendation=(
                        "NO REAL-MONEY STAKE - Shadow quarter-Kelly reference "
                        f"{kelly:.1f}%"
                    ),
                    risk_level=self._get_risk_level(
                        metrics.risk_adjusted_probability,
                        metrics.risk_adjusted_edge,
                    ),
                    real_odds=odds,
                    bookmaker=bookmaker,
                    quote_source=market_odds[market].get('source'),
                    quoted_at=market_odds[market].get('quoted_at'),
                    calibration_method=validation.get('method'),
                    calibration_sample=int(validation['sample_size']),
                    risk_adjusted_probability=round(
                        metrics.risk_adjusted_probability, 1
                    ),
                    calibration_haircut=round(haircut, 1),
                    point_edge=round(metrics.edge, 1),
                    point_expected_roi=round(metrics.expected_roi, 1),
                    market_overround=round(overround, 4),
                    no_vig_market_probability=round(no_vig_probability, 1),
                    model_market_gap=round(prob - no_vig_probability, 1),
                    kelly_stake=kelly,
                    recommendation_type='SHADOW_VALUE',
                    calibrated=True,
                    actionable=False,
                    price_passed=True,
                    evidence_stage='SHADOW',
                )
                value_bets.append(bet)
        
        value_bets.sort(key=lambda x: x.expected_roi, reverse=True)

        # All markets here belong to one fixture. Without an estimated
        # covariance matrix, multiple stakes would silently compound
        # correlated match risk and selection bias.
        return value_bets[:1]
    
    def find_model_signals(self, analysis_results: Dict,
                           home_team: str = None, away_team: str = None,
                           min_probability: float = 70.0) -> List[SmartBet]:
        """Return exploratory estimates without price-derived metrics."""
        high_conf_bets = []
        
        markets = self._extract_all_probabilities(analysis_results)
        
        for market, prob in markets.items():
            if prob >= min_probability:
                bet = SmartBet(
                    market=self._get_market_category(market),
                    sub_market=market,
                    probability=prob,
                    signal_strength='LARGE_MODEL_MARGIN' if prob >= 80 else 'MODEL_MARGIN',
                    edge=None,
                    expected_roi=None,
                    reasoning=(
                        f"Exploratory estimate: {prob:.0f}%. This output is "
                        "uncalibrated, non-actionable, and has no fair-price claim."
                    ),
                    stake_recommendation='NO STAKE - EXPLORATORY ESTIMATE ONLY',
                    risk_level='MODEL_UNCERTAINTY',
                    real_odds=None,
                    bookmaker=None,
                    kelly_stake=None,
                    recommendation_type='EXPLORATORY_ESTIMATE',
                    calibrated=False,
                    actionable=False,
                    price_passed=False,
                    evidence_stage='RESEARCH',
                )
                high_conf_bets.append(bet)
        
        # Sort by probability
        high_conf_bets.sort(key=lambda x: x.probability, reverse=True)
        
        return high_conf_bets[:10]

    def find_high_confidence_bets(self, *args, **kwargs) -> List[SmartBet]:
        """Backward-compatible alias for model-only probability signals."""
        return self.find_model_signals(*args, **kwargs)
    
    def find_combo_bets(self, analysis_results: Dict,
                        home_team: str = None, away_team: str = None,
                        max_selections: int = 3) -> List[Dict]:
        """Do not create same-match combos without a fitted dependency model.

        Multiplying marginal probabilities assumes independence. Football
        result, goals, corners, and cards are not demonstrably independent, so
        the previous combo edge was mathematically unsupported.
        """
        return []
    
    @staticmethod
    def _probability_to_percent(
        value,
        unit: str = 'percent',
    ) -> Optional[float]:
        """Convert only an explicitly declared unit; never guess from magnitude."""
        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        normalized_unit = str(unit or '').strip().lower()
        if normalized_unit == 'decimal':
            if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
                return None
            numeric *= 100.0
        elif normalized_unit != 'percent':
            return None
        try:
            return validate_probability_percent(numeric)
        except BettingMathError:
            return None

    def _extract_all_probabilities(self, results: Dict) -> Dict[str, float]:
        """Extract coherent market probabilities with explicit units."""
        probs: Dict[str, float] = {}

        def put(market: str, value, unit: str = 'percent') -> None:
            probability = self._probability_to_percent(value, unit)
            if probability is not None:
                probs[market] = probability

        flat_market_map = {
            'btts_probability': 'btts_yes',
            'over_0.5_probability': 'over_0.5',
            'over_1.5_probability': 'over_1.5',
            'over_2.5_probability': 'over_2.5',
            'over_3.5_probability': 'over_3.5',
            'over_4.5_probability': 'over_4.5',
            'home_win_probability': 'home_win',
            'draw_probability': 'draw',
            'away_win_probability': 'away_win',
        }
        for source_key, market_key in flat_market_map.items():
            put(market_key, results.get(source_key), 'percent')

        btts = results.get('btts')
        if isinstance(btts, dict):
            unit = btts.get('probability_unit', 'percent')
            put('btts_yes', btts.get('btts_yes', btts.get('yes')), unit)
            put('btts_no', btts.get('btts_no', btts.get('no')), unit)
            if 'probability' in btts:
                put('btts_yes', btts.get('probability'), unit)

        if 'btts_yes' in probs and 'btts_no' not in probs:
            probs['btts_no'] = 100.0 - probs['btts_yes']
        elif 'btts_no' in probs and 'btts_yes' not in probs:
            probs['btts_yes'] = 100.0 - probs['btts_no']
        if {'btts_yes', 'btts_no'} <= probs.keys():
            if not math.isclose(
                probs['btts_yes'] + probs['btts_no'],
                100.0,
                abs_tol=0.2,
            ):
                probs.pop('btts_yes', None)
                probs.pop('btts_no', None)

        over_under = results.get('over_under')
        if isinstance(over_under, dict):
            container_unit = over_under.get('probability_unit', 'percent')
            aliases = {'over_25': 'over_2.5', 'under_25': 'under_2.5'}
            for raw_key, value in over_under.items():
                key = aliases.get(str(raw_key), str(raw_key))
                if not (key.startswith('over_') or key.startswith('under_')):
                    continue
                if isinstance(value, dict):
                    unit = value.get('probability_unit', container_unit)
                    if key.startswith('over_'):
                        probability = value.get(
                            'probability', value.get('over_probability')
                        )
                    else:
                        probability = value.get(
                            'probability', value.get('under_probability')
                        )
                    put(key, probability, unit)
                else:
                    put(key, value, container_unit)

        for key in list(probs):
            if not key.startswith('over_'):
                continue
            suffix = key.removeprefix('over_')
            under_key = f'under_{suffix}'
            if not suffix.endswith('.5'):
                continue
            if under_key not in probs:
                probs[under_key] = 100.0 - probs[key]
            elif not math.isclose(
                probs[key] + probs[under_key], 100.0, abs_tol=0.2
            ):
                probs.pop(key, None)
                probs.pop(under_key, None)

        match_result = results.get('match_result')
        if isinstance(match_result, dict):
            unit = match_result.get('probability_unit', 'percent')
            put('home_win', match_result.get('home_win'), unit)
            put('draw', match_result.get('draw'), unit)
            put('away_win', match_result.get('away_win'), unit)
        result_keys = {'home_win', 'draw', 'away_win'}
        present_result_keys = result_keys & probs.keys()
        if present_result_keys and (
            present_result_keys != result_keys
            or not math.isclose(
                sum(probs[key] for key in result_keys), 100.0, abs_tol=0.5
            )
        ):
            for key in result_keys:
                probs.pop(key, None)

        for source_name in ('corners', 'cards'):
            source = results.get(source_name)
            if not isinstance(source, dict):
                continue
            container_unit = source.get('probability_unit', 'percent')
            for key, value in source.items():
                if 'over' not in str(key).lower() or not isinstance(value, dict):
                    continue
                put(
                    f'{source_name}_{key}',
                    value.get('probability'),
                    value.get('probability_unit', container_unit),
                )

        return probs
    
    def _get_market_category(self, market: str) -> str:
        """Get market category"""
        if 'btts' in market:
            return 'BTTS'
        elif 'over' in market or 'under' in market:
            return 'Over/Under'
        elif 'win' in market or 'draw' in market:
            return 'Match Result'
        elif 'corner' in market:
            return 'Corners'
        elif 'card' in market:
            return 'Cards'
        else:
            return 'Other'
    
    def _generate_reasoning(
        self,
        market: str,
        probability: float,
        risk_adjusted_probability: float,
        haircut: float,
        risk_adjusted_edge: float,
        point_edge: float,
        is_real: bool,
    ) -> str:
        """Generate reasoning for bet"""
        odds_note = "echte Odds" if is_real else "kein Marktpreis"

        if not is_real:
            return (
                f"Modell-Signal: {probability:.0f}% Wahrscheinlichkeit. "
                "Kein Value-Bet ohne echten Marktpreis."
            )
        
        return (
            f"Calibrated model {probability:.1f}%; empirical calibration "
            f"haircut {haircut:.1f} pp gives {risk_adjusted_probability:.1f}% "
            f"for staking. Risk-adjusted edge {risk_adjusted_edge:.1f} pp "
            f"versus point edge {point_edge:.1f} pp ({odds_note}). The haircut "
            "is a robustness adjustment, not a confidence bound."
        )


def display_smart_bet(bet: SmartBet, rank: int = 1):
    """Display a single SmartBet in Streamlit."""
    odds_text = f"{bet.real_odds:.2f}" if bet.real_odds else "n/a"
    edge_text = f"{bet.edge:.1f} pp" if bet.edge is not None else "n/a"
    roi_text = f"{bet.expected_roi:.1f}%" if bet.expected_roi is not None else "n/a"
    adjusted_probability_text = (
        f"{bet.risk_adjusted_probability:.1f}%"
        if bet.risk_adjusted_probability is not None
        else "n/a"
    )

    with st.container():
        st.markdown(f"#### #{rank} {bet.market}: {bet.sub_market}")
        if bet.recommendation_type in {'VALUE_BET', 'SHADOW_VALUE'}:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Model p", f"{bet.probability:.1f}%")
            col2.metric("Staking p", adjusted_probability_text)
            col3.metric("Adjusted edge", edge_text)
            col4.metric("Odds", odds_text)
            point_roi = (
                f"{bet.point_expected_roi:.1f}%"
                if bet.point_expected_roi is not None else "n/a"
            )
            overround = (
                f"{bet.market_overround * 100.0:.1f}%"
                if bet.market_overround is not None else "n/a"
            )
            st.caption(
                f"Risk-adjusted EV: {roi_text} | Point-estimate EV: "
                f"{point_roi} | Same-book overround: {overround}"
            )
        else:
            col1, col2 = st.columns(2)
            col1.metric("Exploratory estimate", f"{bet.probability:.1f}%")
            col2.metric("Market price", "not checked")
        provenance = (
            f"{bet.bookmaker} via {bet.quote_source} at {bet.quoted_at}"
            if bet.bookmaker and bet.quote_source and bet.quoted_at
            else "NO_MARKET_PRICE"
        )
        calibration = (
            f" | Calibration: {bet.calibration_method}, n={bet.calibration_sample}, "
            f"haircut={bet.calibration_haircut:.1f} pp"
            if bet.calibration_method and bet.calibration_sample
            and bet.calibration_haircut is not None
            else ""
        )
        st.caption(
            f"{provenance}{calibration} | Risk: {bet.risk_level} | "
            f"Evidenz: {bet.evidence_stage}"
        )
        if (
            bet.no_vig_market_probability is not None
            and bet.model_market_gap is not None
        ):
            st.caption(
                f"No-Vig-Marktbenchmark {bet.no_vig_market_probability:.1f} % · "
                f"Modellabstand {bet.model_market_gap:+.1f} pp. Der Benchmark "
                "ist Diagnose und kein Modelleingang."
            )
        st.write(bet.reasoning)
        if bet.recommendation_type in {'VALUE_BET', 'SHADOW_VALUE'}:
            st.write(f"**Shadow-Referenz:** {bet.stake_recommendation}")


def render_smart_bet_finder(analysis_results: Dict, home_team: str = None, away_team: str = None):
    """Streamlit UI für Smart Bet Finder"""
    
    st.markdown("### Verified Price Evaluation")
    st.caption("Exact fixture, fresh quote provenance, calibration gate, and capped Kelly")
    
    # Initialize finder
    finder = SmartBetFinder()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎯 Value Bets", use_container_width=True):
            bets = finder.find_value_bets(analysis_results, home_team, away_team)
            
            if bets:
                st.info(
                    "Ein Kandidat hat Modell- und Preisprüfung bestanden. "
                    "Er bleibt bis zur unabhängigen CLV-/ROI-Freigabe ein "
                    "Shadow-Signal ohne Echtgeld-Einsatz."
                )
                for rank, bet in enumerate(bets, start=1):
                    display_smart_bet(bet, rank)
            else:
                st.warning("Keine Value Bets gefunden")
    
    with col2:
        if st.button("Exploratory Estimates", use_container_width=True):
            bets = finder.find_model_signals(analysis_results, home_team, away_team)
            
            if bets:
                st.info(f"{len(bets)} unkalibrierte Modellschätzungen")
                for bet in bets:
                    with st.expander(f"{bet.market}: {bet.sub_market} | {bet.probability:.0f}%"):
                        st.metric("Model margin", bet.signal_strength)
                        st.write(bet.reasoning)
            else:
                st.warning("Keine ausreichend großen Modellschätzungen gefunden")
    
    with col3:
        if st.button("Combo-Modell", use_container_width=True):
            st.info(
                "Deaktiviert: Kombi-Wahrscheinlichkeiten brauchen ein validiertes "
                "Abhängigkeitsmodell; marginale Wahrscheinlichkeiten dürfen nicht "
                "einfach multipliziert werden."
            )
