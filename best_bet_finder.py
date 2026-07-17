"""Conservative ranker for externally produced, calibrated model signals.

This module does not infer probabilities from score, possession, xG, cards, or
corners. It only ranks upstream signals that explicitly declare calibration and
provenance. Market price, edge, EV, and stake remain outside this component.
"""

import math
from datetime import datetime, timezone
from typing import Dict, List

import streamlit as st


class BestBetFinder:
    """Compatibility API for ranking eligible model signals."""

    def __init__(self):
        self.all_bets: List[Dict] = []

    @staticmethod
    def _utc_datetime(value) -> datetime | None:
        try:
            timestamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return None
        if timestamp.tzinfo is None:
            return None
        return timestamp.astimezone(timezone.utc)

    @classmethod
    def _credible_validation(cls, raw: Dict) -> bool:
        validation = raw.get('validation')
        if not isinstance(validation, dict):
            return False
        league_id = raw.get('league_id')
        league_ids = validation.get('league_ids')
        validation_end = cls._utc_datetime(validation.get('validation_end'))
        kickoff = cls._utc_datetime(raw.get('fixture_kickoff'))
        integer_values = (
            validation.get('sample_size'),
            validation.get('calibration_bins'),
            validation.get('min_bin_size'),
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not float(value).is_integer()
            for value in integer_values
        ):
            return False
        try:
            decimal_values = (
                validation.get('expected_calibration_error'),
                validation.get('max_calibration_error'),
                validation.get('calibration_coverage'),
            )
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in decimal_values
            ):
                return False
            sample_size = int(integer_values[0])
            calibration_bins = int(integer_values[1])
            min_bin_size = int(integer_values[2])
            ece = float(decimal_values[0])
            max_error = float(decimal_values[1])
            calibration_coverage = float(decimal_values[2])
        except (TypeError, ValueError, OverflowError):
            return False
        return bool(
            validation.get('calibrated') is True
            and validation.get('out_of_sample') is True
            and isinstance(league_id, int)
            and not isinstance(league_id, bool)
            and league_id > 0
            and isinstance(league_ids, list)
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value > 0
                for value in league_ids
            )
            and league_id in league_ids
            and sample_size >= 200
            and calibration_bins >= 3
            and min_bin_size >= 20
            and min_bin_size <= sample_size
            and calibration_bins * min_bin_size <= sample_size
            and math.isfinite(ece)
            and math.isfinite(max_error)
            and 0.0 <= ece <= 0.08
            and 0.0 <= max_error <= 0.12
            and 0.80 <= calibration_coverage <= 1.0
            and str(validation.get('model_version') or '').strip()
            and validation_end is not None
            and kickoff is not None
            and validation_end <= datetime.now(timezone.utc)
            and validation_end < kickoff
        )

    @staticmethod
    def _eligible_signal(raw: Dict) -> Dict | None:
        if (
            not isinstance(raw, dict)
            or raw.get('calibrated') is not True
            or not BestBetFinder._credible_validation(raw)
        ):
            return None
        source = str(raw.get('source') or '').strip()
        market = str(raw.get('market') or '').strip()
        selection = str(raw.get('selection') or '').strip()
        probability = raw.get('probability')
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            return None
        probability = float(probability)
        if (
            not source
            or not market
            or not selection
            or not math.isfinite(probability)
            or not 0.0 <= probability <= 100.0
        ):
            return None

        return {
            'market': market,
            'selection': selection,
            'probability': probability,
            'model_price': round(100.0 / probability, 2) if probability > 0 else None,
            'calibrated': True,
            'source': source,
            'current_status': raw.get('current_status'),
            'reasoning': raw.get('reasoning') or 'Calibrated upstream model signal',
            'recommendation_type': 'MODEL_SIGNAL',
        }

    def find_best_bet(self, match_data: Dict, minute: int, stats: Dict) -> Dict:
        raw_signals = (
            match_data.get('market_probabilities')
            or stats.get('market_probabilities')
            or []
        )
        eligible = [
            signal
            for signal in (self._eligible_signal(raw) for raw in raw_signals)
            if signal is not None
        ]
        eligible.sort(key=lambda signal: signal['probability'], reverse=True)
        self.all_bets = eligible
        best_signal = eligible[0] if eligible else None
        return {
            # Compatibility aliases for existing callers.
            'best_bet': best_signal,
            'best_signal': best_signal,
            'top_5': eligible[:5],
            'high_probability_bets': [
                signal for signal in eligible if signal['probability'] >= 65.0
            ],
            'all_bets': eligible,
            'total_markets_analyzed': len(eligible),
            'match_info': {
                'home_team': match_data.get('home_team'),
                'away_team': match_data.get('away_team'),
                'score': f"{match_data.get('home_score', 0)}-{match_data.get('away_score', 0)}",
                'minute': minute,
            },
            'status': 'OK' if eligible else 'NO_CALIBRATED_SIGNALS',
        }


def display_best_bet(result: Dict):
    """Display the strongest eligible model signal without a price claim."""
    signal = result.get('best_signal') or result.get('best_bet')
    if not signal:
        st.info("No calibrated upstream model signal is available.")
        return

    columns = st.columns(3)
    columns[0].metric("Market", signal['market'])
    columns[1].metric("Selection", signal['selection'])
    columns[2].metric("Model probability", f"{signal['probability']:.1f}%")
    st.caption(
        f"Source: {signal['source']} | Model-implied decimal price: "
        f"{signal['model_price'] if signal['model_price'] is not None else 'n/a'} | "
        "No market price checked"
    )
    st.write(signal['reasoning'])


__all__ = ['BestBetFinder', 'display_best_bet']
