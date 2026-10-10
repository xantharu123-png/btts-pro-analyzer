"""Context controls TOP admission, never the model's coherent direction."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from daily3_selection import daily3_choices
from forecast_selection import select_consumer_forecasts
from test_highlight_price_checks import NOW, _signal
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog


@pytest.mark.parametrize("axis", ["h2h", "weather", "injuries"])
@pytest.mark.parametrize("problem", ["missing", "stale"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("representation", ["signals", "cards"])
def test_context_admission_cannot_replace_home_model_direction_in_signals_or_cards(axis, problem, reverse, representation):
    # Break caught: a presentation-only context deficit outranks the larger same-revision model probability.
    home = replace(_signal("RESULT_HOME", .75), price_checked_at=NOW.isoformat())
    away = replace(_signal("RESULT_AWAY", .72), price_checked_at=NOW.isoformat())
    evidence = deepcopy(home.analysis_evidence)
    if problem == "missing":
        evidence["context"].pop(axis)
    else:
        evidence["context"][axis]["checked_at"] = (NOW-timedelta(minutes=76)).isoformat()
    home = replace(home, analysis_evidence=evidence)
    signals = [away, home] if reverse else [home, away]
    if representation == "signals":
        selected = select_consumer_forecasts(signals, now=NOW)
        assert [signal.key for signal in selected] == ["81:RESULT_HOME"]
        assert selected[0] is home
    else:
        cards = [build_wettfinder_card(signal, now=NOW) for signal in signals]
        catalog = compose_wettfinder_catalog(cards)
        assert catalog.featured == ()
        assert [card.key for card in catalog.additional] == ["81:RESULT_HOME"]
        assert catalog.additional[0].model_probability == .75
        assert not catalog.additional[0].highlight_eligible
        assert all(card.observed_odds is None and card.price_code == "UNAVAILABLE" for card in cards)
    assert daily3_choices(signals, now=NOW) == ()


@pytest.mark.parametrize("problem", ["missing_model_facts", "future_model_clock", "old_model_clock"])
def test_supported_current_model_still_outranks_larger_unqualified_probability(problem):
    # Break caught: separating context qualification accidentally weakens required model identity/evidence/clocks.
    home = replace(_signal("RESULT_HOME", .75), price_checked_at=NOW.isoformat())
    if problem == "missing_model_facts":
        away = replace(_signal("RESULT_AWAY", .95), analysis_evidence=None)
    else:
        clock = NOW+timedelta(seconds=1) if problem == "future_model_clock" else NOW-timedelta(hours=25)
        away = _signal("RESULT_AWAY", .95, modeled_at=clock)
    for signals in ([away, home], [home, away]):
        assert select_consumer_forecasts(signals, now=NOW)[0] is home
        catalog = compose_wettfinder_catalog([build_wettfinder_card(signal, now=NOW) for signal in signals])
        assert [card.key for card in catalog.featured + catalog.additional] == ["81:RESULT_HOME"]
