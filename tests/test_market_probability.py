from datetime import datetime, timezone
import math

import pytest

from betting_math import no_vig_market
from market_consensus import (
    EDGE_CAP_FLAG, MarketConsensus, QuotePoint, REFERENCE_SOURCE, native_partition, no_vig_market_probability,
    reference_price_status,
)

NOW = datetime(2030, 1, 1, 7, tzinfo=timezone.utc)
BOOKS = {"b1": (1.80, 3.60, 4.50), "b2": (1.85, 3.50, 4.40), "b3": (1.75, 3.70, 4.60)}


def _quote(market_key="RESULT_HOME", *, books=BOOKS, partitions=True, side_index=0):
    observed = (NOW.replace(minute=0)).isoformat()
    fetched = NOW.isoformat()
    points = tuple(QuotePoint(bookmaker=name, odds=odds[side_index], bookmaker_id=f"api-football:{name}",
                              observed_at=observed) for name, odds in books.items())
    prices = sorted(p.odds for p in points)
    parts = tuple(native_partition("RESULT", "football_90_minutes", f"api-football:{name}", observed, fetched,
                                   list(zip(("HOME", "DRAW", "AWAY"), odds))) for name, odds in books.items()) if partitions else ()
    return MarketConsensus(
        fixture_id=1, candidate_id="1:" + market_key, market_key=market_key, bet_name="Match Winner",
        value_name={"RESULT_HOME": "Home", "RESULT_DRAW": "Draw", "RESULT_AWAY": "Away", "DC_1X": "Home/Draw"}[market_key],
        consensus_odds=prices[len(prices) // 2], conservative_odds=prices[0], lowest_odds=prices[0], best_odds=prices[-1],
        bookmaker_count=len(points), quoted_at=observed, fetched_at=fetched, source=REFERENCE_SOURCE, points=points,
        scheduled_start=(NOW.replace(hour=15)).isoformat(), event_home="Heim", event_away="Gast",
        native_market_partitions=parts,
    )


def test_median_shin_probability_of_the_selected_side_and_double_chance_sum():
    expected = sorted(no_vig_market(odds, "shin").no_vig_probabilities[0] for odds in BOOKS.values())[1]
    assert no_vig_market_probability(_quote()) == pytest.approx(expected)
    assert 0.52 < expected < 0.58  # Shin: the favourite keeps more than proportional removal would give.
    home = no_vig_market_probability(_quote("RESULT_HOME"))
    draw = no_vig_market_probability(_quote("RESULT_DRAW", side_index=1))
    away = no_vig_market_probability(_quote("RESULT_AWAY", side_index=2))
    assert math.isclose(home + draw + away, 1.0, abs_tol=0.01)  # Medians of three books, not one law.
    assert no_vig_market_probability(_quote("DC_1X")) == pytest.approx(
        sorted(sum(no_vig_market(odds, "shin").no_vig_probabilities[:2]) for odds in BOOKS.values())[1])
    assert no_vig_market_probability(_quote(partitions=False)) is None


def test_edge_cap_prefers_the_no_vig_probability_and_falls_back_to_the_consensus_proxy(monkeypatch):
    monkeypatch.setenv(EDGE_CAP_FLAG, "8")
    quote = _quote()
    market = no_vig_market_probability(quote)
    capped = reference_price_status(quote, 1.5, now=NOW, model_probability=market + 0.12)
    assert capped.code == "EDGE_CAP" and capped.market_basis == "no-vig"
    assert capped.market_probability == pytest.approx(market)
    fine = reference_price_status(quote, 1.5, now=NOW, model_probability=market + 0.05)
    assert fine.code == "PLAYABLE"
    proxy = reference_price_status(_quote(partitions=False), 1.5, now=NOW, model_probability=0.75)
    assert proxy.code == "EDGE_CAP" and proxy.market_basis == "consensus-implied"
    assert proxy.market_probability == pytest.approx(1.0 / 1.80)
    monkeypatch.delenv(EDGE_CAP_FLAG, raising=False)
    assert reference_price_status(quote, 1.5, now=NOW, model_probability=0.95).code == "PLAYABLE"
