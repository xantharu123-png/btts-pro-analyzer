"""Conservative ranker for externally produced, calibrated model signals.

This module does not infer probabilities from score, possession, xG, cards, or
corners. It only ranks upstream signals that explicitly declare calibration and
provenance. Market price, edge, EV, and stake remain outside this component.
"""

import math
from typing import Dict, List

import streamlit as st


class BestBetFinder:
    """Compatibility API for ranking eligible model signals."""

    def __init__(self):
        self.all_bets: List[Dict] = []

    @staticmethod
    def _eligible_signal(raw: Dict) -> Dict | None:
        if not isinstance(raw, dict) or raw.get('calibrated') is not True:
            return None
        source = str(raw.get('source') or '').strip()
        market = str(raw.get('market') or '').strip()
        selection = str(raw.get('selection') or '').strip()
        try:
            probability = float(raw.get('probability'))
        except (TypeError, ValueError):
            return None
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
