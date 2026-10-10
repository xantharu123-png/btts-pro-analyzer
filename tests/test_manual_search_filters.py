"""A price/probability filter must match actual values, not implied prices."""
import importlib
import json
import math

import pytest
from streamlit.testing.v1 import AppTest


def filters(**kwargs):
    try:
        module = importlib.import_module("manual_search_filters")
    except ModuleNotFoundError:
        pytest.fail("The real manual selection filter is not implemented")
    return module.SearchFilters(**kwargs)


@pytest.mark.parametrize("probability,want", [(.599, False), (.60, True), (.75, True), (.80, True), (.801, False)])
def test_probability_range_includes_only_the_requested_percentages(probability, want):
    assert filters(probability_min=.60, probability_max=.80).matches(probability=probability) is want


@pytest.mark.parametrize("quote,want", [(1.19, False), (1.20, True), (1.80, True), (2.50, True), (2.51, False), (None, False), (math.nan, False), (True, False)])
def test_active_price_range_requires_an_actual_finite_matching_price(quote, want):
    assert filters(quote_min=1.20, quote_max=2.50).matches(probability=.70, quote=quote) is want


def test_missing_price_is_allowed_without_a_price_filter_but_low_known_price_is_not():
    query = filters()
    assert query.matches(probability=.70, quote=None)
    assert not query.matches(probability=.70, quote=1.02)


def test_quote_and_probability_are_independent_and_filters_do_not_change_values():
    query = filters(probability_min=.55, probability_max=.65, quote_min=1.20, quote_max=2.00)
    rows = [{"probability": .60, "quote": 1.80}, {"probability": .81, "quote": 1.80}, {"probability": .60, "quote": 2.10}]
    before = [dict(row) for row in rows]
    actual = [row for row in rows if query.matches(**row)]
    assert actual == [{"probability": .60, "quote": 1.80}]
    assert rows == before


def test_market_filter_never_accepts_a_different_market():
    query = filters(market_kind="match_winner")
    assert query.matches(probability=.70, market_kind="match_winner")
    assert not query.matches(probability=.70, market_kind="total_sets")
    assert not query.matches(probability=.70)


def test_unmodeled_fixture_cannot_pass_an_active_probability_filter():
    assert filters().matches(probability=None)
    assert not filters(probability_min=.01).matches(probability=None)


@pytest.mark.parametrize("kwargs", [
    {"probability_min": -.1}, {"probability_max": 1.1},
    {"probability_min": .8, "probability_max": .5},
    {"probability_min": True}, {"probability_max": math.inf},
    {"quote_min": 1.19}, {"quote_max": 1.10},
    {"quote_min": 2.50, "quote_max": 1.50}, {"quote_min": math.nan},
])
def test_invalid_or_inverted_ranges_cannot_be_used(kwargs):
    try:
        module = importlib.import_module("manual_search_filters")
    except ModuleNotFoundError:
        pytest.fail("The real manual selection filter is not implemented")
    with pytest.raises(ValueError):
        module.SearchFilters(**kwargs)


def _filter_ui():
    import streamlit as st
    from manual_search_filters import render_search_filters
    query = render_search_filters(st, key_prefix="manual_test")
    data = [("match-a", .60, 1.80), ("match-b", .81, 1.80), ("match-c", .60, None), ("match-d", .60, 2.60)]
    st.write([name for name, probability, price in data if query.matches(probability=probability, quote=price)])


def test_ui_controls_apply_both_filters_without_an_api_or_model_run():
    # Fails if the controls are decorative, price-less rows slip through, or
    # percentages are used as probabilities without converting 60 to .60.
    filters()
    app = AppTest.from_function(_filter_ui).run(timeout=30)
    assert not app.exception
    app.slider[0].set_range(55, 65)
    app.checkbox[0].check().run(timeout=30)
    assert not app.exception
    app.number_input[1].set_value(2.00).run(timeout=30)
    assert not app.exception
    assert json.loads(app.json[-1].value) == ["match-a"]


def test_inverted_ui_price_range_is_an_error_not_unfiltered_results():
    filters()
    app = AppTest.from_function(_filter_ui).run(timeout=30)
    app.checkbox[0].check().run(timeout=30)
    app.number_input[0].set_value(3.00)
    app.number_input[1].set_value(2.00).run(timeout=30)
    assert not app.exception
    assert app.error
    assert not app.json
