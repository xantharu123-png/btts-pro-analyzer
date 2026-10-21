from dataclasses import replace

import pytest

from market_consensus import EDGE_CAP_FLAG, MarketConsensus, edge_cap_pp, wettfinder_reference_price_status
from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced


def _status(probability, monkeypatch, cap):
    if cap is None:
        monkeypatch.delenv(EDGE_CAP_FLAG, raising=False)
    else:
        monkeypatch.setenv(EDGE_CAP_FLAG, cap)
    signal = replace(priced(football(probability=probability), (1.8,) * 3), minimum_odds=1.5)
    quote = MarketConsensus.from_dict(signal.reference_quote)
    return wettfinder_reference_price_status(quote, signal.minimum_odds, candidate=signal, now=NOW)


def test_cap_is_off_without_the_flag_and_parses_positive_numbers(monkeypatch):
    monkeypatch.delenv(EDGE_CAP_FLAG, raising=False)
    assert edge_cap_pp() is None
    for raw, expected in (("8", 8.0), ("7,5", 7.5), ("0", None), ("-3", None), ("x", None), ("", None)):
        monkeypatch.setenv(EDGE_CAP_FLAG, raw)
        assert edge_cap_pp() == expected


def test_playable_price_is_demoted_only_above_the_cap(monkeypatch):
    # Consensus 1.80 implies 55.6 %: p = 0.80 is 24 pp above, p = 0.60 is 4 pp above.
    assert _status(0.80, monkeypatch, None).code == "PLAYABLE"
    capped = _status(0.80, monkeypatch, "8")
    assert capped.code == "EDGE_CAP" and capped.usable_odds is None and "24." in capped.label
    assert _status(0.60, monkeypatch, "8").code == "PLAYABLE"
    assert _status(0.80, monkeypatch, "30").code == "PLAYABLE"


def test_non_playable_statuses_are_untouched_by_the_cap(monkeypatch):
    monkeypatch.setenv(EDGE_CAP_FLAG, "8")
    signal = priced(football(probability=0.80), (1.8,) * 3)  # Minimum 2.00: TOO_LOW before any cap.
    quote = MarketConsensus.from_dict(signal.reference_quote)
    assert wettfinder_reference_price_status(quote, signal.minimum_odds, candidate=signal, now=NOW).code == "TOO_LOW"
    assert wettfinder_reference_price_status(None, 1.5, candidate=signal, now=NOW).code == "UNAVAILABLE"
