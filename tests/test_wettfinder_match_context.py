"""Prominence needs a match-specific reason, not just a high probability."""
from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest

from daily3_selection import daily3_choices
from test_daily3_selection import NOW, _admitted, football
from wettfinder_surface import (
    build_wettfinder_card, compose_wettfinder_catalog,
    render_compact_row_html, render_top_card_html,
)


def catalog(signals):
    return compose_wettfinder_catalog([build_wettfinder_card(s, s.reference_quote, now=NOW) for s in signals])


def _priced_football(*args, **kwargs):
    from market_consensus import exact_market_target
    signal = football(*args, **kwargs)
    return _admitted(signal) if exact_market_target(signal.market_key) else signal


@pytest.mark.parametrize('variants', [
    (.898628, .91655, .818378),  # Reported Fluminense under 2.5, 20 September.
    (.96, .97, .93), (.96, .96, .96), (.96, .955, .975),
])
def test_broad_forecast_without_supporting_form_is_not_promoted(variants):
    signal = _priced_football(key='AWAY_UNDER_2_5', probability=variants[0], variants=variants)
    result = catalog([signal])
    assert result.featured == ()
    assert [c.key for c in result.additional] == [signal.key]
    card = result.additional[0]
    assert card.model_probability == signal.probability
    # Even direct rendering cannot turn a neutral forecast into a highlight.
    for html in (render_top_card_html(card), render_compact_row_html(card, featured=True)):
        assert 'MODELL-AUSWAHL' not in html
        assert 'Formsignal:' not in html


@pytest.mark.parametrize('key', [
    'HOME_OVER_0_5', 'AWAY_OVER_0_5', 'HOME_UNDER_2_5',
    'AWAY_UNDER_2_5', 'HOME_RANGE_1_3',
])
def test_no_market_or_home_away_ban_when_same_match_has_supporting_form(key):
    signal = _priced_football(key=key, probability=.78, variants=(.78, .73, .87))
    result = catalog([signal])
    if key == 'HOME_RANGE_1_3':
        from market_consensus import exact_market_target
        from forecast_analysis import build_forecast_analysis
        from daily3_comparison import football_form_comparison
        # This native feed has no exact 1-3 range offer. Its model and match
        # reason remain sound without manufacturing publication price proof.
        assert exact_market_target(key) is None and signal.reference_quote is None
        assert build_forecast_analysis(signal, now=NOW).supported
        assert football_form_comparison(signal, now=NOW) is not None
        assert signal.probability == .78
        assert not result.featured and not result.additional
        return
    assert [c.key for c in result.featured] == [signal.key]
    card = result.featured[0]
    for html in (render_top_card_html(card), render_compact_row_html(card, grouped=True, featured=True)):
        assert 'MODELL-AUSWAHL' in html
        assert html.count('Formsignal: +5,0 Prozentpunkte zum Grundmodell (73,0%).') == 1
    assert 'Formsignal:' not in render_compact_row_html(card)


def test_missing_comparison_stays_visible_without_promotion():
    signal = _priced_football(comparison=False)
    result = catalog([signal])
    assert result.featured == ()
    assert [c.key for c in result.additional] == [signal.key]


@pytest.mark.parametrize('field,value', [
    ('fixture_id', 999), ('market_key', 'BTTS_YES'), ('home_id', 999),
    ('prediction_version', 'other'), ('model_skill_supported', False),
])
def test_foreign_or_unvalidated_comparison_cannot_promote_a_forecast(field, value):
    signal = _priced_football()
    evidence = deepcopy(signal.analysis_evidence)
    evidence['basis']['market_comparison'][field] = value
    signal = replace(signal, analysis_evidence=evidence)
    result = catalog([signal])
    assert not result.featured
    assert [c.key for c in result.additional] == [signal.key]


def test_rank_by_match_signal_not_probability_price_or_input_position():
    favourite = _priced_football(1, 'HOME_OVER_0_5', .94, variants=(.94, .915, .985))
    alternative = _priced_football(2, 'AWAY_OVER_0_5', .80, variants=(.8, .72, .94))
    btts = _priced_football(3, 'BTTS_YES', .76, variants=(.76, .69, .83))
    for signals in permutations((favourite, alternative, btts)):
        result = catalog(signals)
        assert [c.key for c in result.featured] == [alternative.key, btts.key]
        assert [c.key for c in result.additional] == [favourite.key]
        for price in (None, 1.01, 999.0):
            repriced = compose_wettfinder_catalog([
                replace(c, observed_odds=price, value_threshold=999.0,
                        price_code='UNAVAILABLE' if price is None else 'TOO_LOW')
                for c in reversed(result.featured + result.additional)
            ])
            assert [c.key for c in repriced.featured] == [alternative.key, btts.key]


def test_normal_wettfinder_does_not_inherit_daily3_probability_floor():
    signal = _priced_football(probability=.60, variants=(.60, .54, .78))
    assert daily3_choices([signal], now=NOW) == ()
    assert [c.key for c in catalog([signal]).featured] == [signal.key]


def test_form_interest_cannot_reverse_modal_result_or_conflicting_double_chance():
    # Same live match as the reported Fluminense example. Only the outsider
    # has positive form; it must not replace the model's modal home outcome.
    signals = [
        _priced_football(key='RESULT_HOME', probability=.406799, variants=(.406799, .434143, .339440)),
        _priced_football(key='RESULT_AWAY', probability=.315701, variants=(.315701, .287089, .394854)),
        _priced_football(key='DC_1X', probability=.684299, variants=(.684299, .712911, .605146)),
        _priced_football(key='DC_X2', probability=.593201, variants=(.593201, .565857, .660560)),
    ]
    for ordering in permutations(signals):
        result = catalog(ordering)
        keys = {c.market_key for c in result.featured + result.additional}
        assert 'RESULT_HOME' in keys
        assert not keys & {'RESULT_AWAY', 'DC_X2'}
        assert not result.featured


def test_favourite_strength_alone_cannot_fill_a_featured_slot():
    obvious = _priced_football(1, 'HOME_OVER_0_5', .97, variants=(.97, .969, .973))
    supported = _priced_football(2, 'AWAY_OVER_0_5', .77, variants=(.77, .72, .86))
    result = catalog([obvious, supported])
    assert [c.key for c in result.featured] == [supported.key]
    assert [c.key for c in result.additional] == [obvious.key]
