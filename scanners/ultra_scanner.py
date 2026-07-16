"""Cross-sport ranking guard.

Probabilities, heuristic scores, and data coverage from different sports do not
share a common calibration scale. The former synthetic leaderboard is therefore
disabled until every source supplies an out-of-sample calibrated utility metric
under one documented evaluation protocol.
"""

from typing import Dict, List

import streamlit as st


class MultiSportRanker:
    """Compatibility wrapper that refuses unsupported cross-sport ranking."""

    def __init__(self):
        self.opportunities: List[Dict] = []

    def add_opportunity(self, sport: str, opp: Dict):
        raise ValueError(
            "Cross-sport ranking is disabled: inputs are not on a common calibrated scale"
        )

    def calculate_score(self, opp: Dict) -> float:
        raise ValueError(
            "No mathematically supported cross-sport score is configured"
        )

    def get_top_opportunities(self, limit: int = 10, filters: Dict = None) -> List[Dict]:
        return []

    def clear(self):
        self.opportunities = []

    def get_stats(self) -> Dict:
        return {
            'total': 0,
            'by_sport': {},
            'ranking_enabled': False,
        }


def create_ultra_tab(filters: Dict = None):
    st.header("Multi-Sport Live Data")
    st.info(
        "Cross-sport ranking is disabled. Uncalibrated outputs from football, "
        "basketball, tennis, cricket, and e-sports are not comparable."
    )


if __name__ == "__main__":
    st.set_page_config(page_title="Multi-Sport Live Data", layout="wide")
    create_ultra_tab()
