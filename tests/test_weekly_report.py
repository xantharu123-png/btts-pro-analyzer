from __future__ import annotations

import pytest

from scripts.weekly_report import _minimum_odds
from tennis.predict import SIDE_MARKET_PROBABILITY_HAIRCUT


def test_minimum_odds_uses_haircut_and_risk_adjusted_roi() -> None:
    probability = 0.70
    # (1 + 3% target ROI) / (70% - 10pp haircut), rounded up to cents.
    assert _minimum_odds(probability) == pytest.approx(1.72)


def test_minimum_odds_requires_probability_above_haircut() -> None:
    assert _minimum_odds(SIDE_MARKET_PROBABILITY_HAIRCUT) is None
    assert _minimum_odds(None) is None
