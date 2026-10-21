import math

import pytest

from tennis.backtest import _devig


def test_devig_rejects_nan_and_invalid_prices_and_normalises_valid_ones():
    assert _devig(float("nan"), 1.8) is None
    assert _devig(1.8, float("nan")) is None
    assert _devig(float("inf"), 1.8) is None
    assert _devig("x", 1.8) is None
    assert _devig(1.0, 2.0) is None
    pw, pl = _devig(1.5, 2.6)
    assert math.isclose(pw + pl, 1.0) and pw > pl
