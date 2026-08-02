from __future__ import annotations

import pytest

from scripts.weekly_report import MIN_EDGE, _minimum_odds


def test_minimum_odds_uses_absolute_probability_edge() -> None:
    probability = 0.70
    assert _minimum_odds(probability) == pytest.approx(
        1.0 / (probability - MIN_EDGE)
    )


def test_minimum_odds_requires_probability_above_edge() -> None:
    assert _minimum_odds(MIN_EDGE) is None
    assert _minimum_odds(None) is None
