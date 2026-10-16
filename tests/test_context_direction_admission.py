"""Context controls TOP admission, never the model's coherent direction."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from daily3_selection import daily3_choices
from forecast_selection import select_consumer_forecasts
from test_highlight_price_checks import NOW, _quote, _signal
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog


def _priced_signal(market_key, probability, **kwargs):
    """Keep public price admission satisfied while varying model/context facts."""
    signal = _signal(market_key, probability, **kwargs)
    return replace(signal, price_checked_at=NOW.isoformat(),
                   reference_quote=_quote(signal, fetched_at=NOW, odds=1.9).to_dict())


@pytest.mark.parametrize("axis", ["h2h", "weather", "injuries"])
@pytest.mark.parametrize("problem", ["missing", "stale", "daily_boundary", "expired_daily"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("representation", ["signals", "cards"])
def test_context_admission_cannot_replace_home_model_direction_in_signals_or_cards(axis, problem, reverse, representation):
    # Break caught: a presentation-only context deficit outranks the larger same-revision model probability.
    home = _priced_signal("RESULT_HOME", .75)
    away = _priced_signal("RESULT_AWAY", .72)
    evidence = deepcopy(home.analysis_evidence)
    if problem == "missing":
        evidence["context"].pop(axis)
    elif problem in ("stale", "daily_boundary"):
        age = timedelta(minutes=76) if problem == "stale" else timedelta(hours=24)
        evidence["context"][axis]["checked_at"] = (NOW-age).isoformat()
    else:
        evidence["context"][axis]["checked_at"] = (NOW-timedelta(hours=24, seconds=1)).isoformat()
    home = replace(home, analysis_evidence=evidence)
    signals = [away, home] if reverse else [home, away]
    before = [deepcopy(vars(signal)) for signal in signals]
    if representation == "signals":
        selected = select_consumer_forecasts(signals, now=NOW)
        assert [signal.key for signal in selected] == ["81:RESULT_HOME"]
        assert selected[0] is home
    else:
        cards = [build_wettfinder_card(signal, signal.reference_quote, now=NOW) for signal in signals]
        catalog = compose_wettfinder_catalog(cards)
        assert catalog.featured == ()
        assert [card.key for card in catalog.additional] == ["81:RESULT_HOME"]
        assert catalog.additional[0].model_probability == .75
        assert not catalog.additional[0].highlight_eligible
        assert all(card.observed_odds == 1.9 and card.reference_quote is not None
                   and not card.quote_floor_excluded for card in cards)
    if problem in ("stale", "daily_boundary"):
        # The 75-minute TOP rule is unchanged, but the automatic Daily3 day
        # view keeps its original observations for 24h. It cannot re-anchor
        # the opposing side merely because one observation is 76 minutes old.
        assert [choice.signal.key for choice in daily3_choices(signals, now=NOW)] == [home.key]
    else:
        assert daily3_choices(signals, now=NOW) == ()
    assert [vars(signal) for signal in signals] == before


@pytest.mark.parametrize("problem", ["missing_model_facts", "future_model_clock", "old_model_clock"])
def test_supported_current_model_still_outranks_larger_unqualified_probability(problem):
    # Break caught: separating context qualification accidentally weakens required model identity/evidence/clocks.
    home = _priced_signal("RESULT_HOME", .75)
    if problem == "missing_model_facts":
        away = replace(_priced_signal("RESULT_AWAY", .95), analysis_evidence=None)
    else:
        clock = NOW+timedelta(seconds=1) if problem == "future_model_clock" else NOW-timedelta(hours=25)
        away = _priced_signal("RESULT_AWAY", .95, modeled_at=clock)
    for signals in ([away, home], [home, away]):
        assert select_consumer_forecasts(signals, now=NOW)[0] is home
        catalog = compose_wettfinder_catalog([
            build_wettfinder_card(signal, signal.reference_quote, now=NOW) for signal in signals
        ])
        assert [card.key for card in catalog.featured + catalog.additional] == ["81:RESULT_HOME"]


@pytest.mark.parametrize("axis", ["h2h", "weather", "injuries"])
@pytest.mark.parametrize("odds", [None, 1.19])
@pytest.mark.parametrize("reverse", [False, True])
def test_context_deficit_and_unpublishable_winner_cannot_promote_priced_opposition(axis, odds, reverse):
    # Break caught: removing the model winner for context/price re-anchors a priced opposing side.
    home = _priced_signal("RESULT_HOME", .75)
    evidence = deepcopy(home.analysis_evidence)
    evidence["context"].pop(axis)
    quote = None if odds is None else _quote(home, fetched_at=NOW, odds=odds).to_dict()
    home = replace(home, analysis_evidence=evidence, reference_quote=quote)
    away = _priced_signal("RESULT_AWAY", .72)
    signals = [away, home] if reverse else [home, away]
    before = [deepcopy(vars(signal)) for signal in signals]

    assert select_consumer_forecasts(signals, now=NOW) == [home]
    cards = [build_wettfinder_card(signal, signal.reference_quote, now=NOW) for signal in signals]
    by_key = {card.key: card for card in cards}
    assert by_key[home.key].quote_floor_excluded
    assert not by_key[away.key].quote_floor_excluded
    assert by_key[away.key].highlight_eligible
    catalog = compose_wettfinder_catalog(cards)
    assert catalog.featured == () and catalog.additional == ()
    assert daily3_choices(signals, now=NOW) == ()
    assert [vars(signal) for signal in signals] == before
