"""Offline behavioral proof of manual controls and exact E-Sport offers."""
import copy
from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from manual_search_filters import SearchFilters
from test_multi_sport_recommendations import _esports_match

NOW = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)


def test_market_group_filters_accept_members_not_unrelated_markets():
    filters = SearchFilters(market_kind=frozenset({"result", "double_chance"}))
    assert filters.matches(probability=.60, market_kind="result")
    assert filters.matches(probability=.60, market_kind="double_chance")
    assert not filters.matches(probability=.60, market_kind="team_corners")


def test_exact_percentage_range_accepts_the_complement_without_changing_it():
    from tennis_tab import _favorite_probability
    probability = _favorite_probability({"p_cal": .42})
    assert probability == .5800000000000001
    assert SearchFilters(probability_max=.58).matches(probability=probability)
    assert SearchFilters(probability_min=.58, probability_max=.58).matches(probability=probability)
    assert not SearchFilters(probability_max=.58).matches(probability=.5800001)


def test_football_market_choice_filters_the_full_cache_not_a_new_scan_scope(monkeypatch):
    import app
    calls = []
    monkeypatch.setattr(app, "create_alternative_markets_tab_extended", lambda **kw: calls.append(kw))
    monkeypatch.setattr(app.st, "caption", lambda *_args: None)
    from datetime import date
    app._render_selected_finder("Fußball", date(2030, 1, 1), date(2030, 1, 2), "Ecken",
                                search_filters=SearchFilters(probability_min=.55))
    assert calls[0]["market_scope"] == "Beste Märkte"
    assert calls[0]["search_filters"].probability_min == .55
    assert calls[0]["search_filters"].matches(probability=.60, market_kind="team_corners")
    assert not calls[0]["search_filters"].matches(probability=.60, market_kind="total")


def _rows(items, filters):
    try:
        from manual_search_results import esports_search_results
    except ImportError:
        pytest.fail("Manual E-Sport results must use the actual probability and exact cached offer")
    return esports_search_results(items, filters, now=NOW)


def _match():
    return dict(_esports_match(), status="upcoming", source="PandaScore",
                begin_at="2026-08-01T18:00:00Z", team1_score=0, team2_score=0)


def _prices(monkeypatch, price=1.80, opponent=2.10, **event_changes):
    from test_esports_prices import event
    fixture = event()
    fixture.update(dict(startTime="2026-08-01T18:00:00Z",
                        participant1Name="Alpha", participant2Name="Beta") | event_changes)
    for book in fixture["bookmakerOdds"].values():
        points = book["markets"]["171"]["outcomes"]
        for outcome, value in (("171", price), ("172", opponent)):
            points[outcome]["players"]["0"].update(price=value, changedAt=NOW.isoformat())
    monkeypatch.setattr("esports_prices._read", lambda _path: {
        "schema": "esports-prices-v1", "fetched_at": NOW.isoformat(), "events": [fixture]})


def test_esports_range_filters_preserve_model_and_read_the_correct_offer(monkeypatch):
    _prices(monkeypatch)
    match = _match()
    original = copy.deepcopy(match)
    rows = _rows([match], SearchFilters(quote_min=1.20, quote_max=2.00))
    assert len(rows) == 1
    assert rows[0].candidate.selection == "Alpha"
    assert 50 < rows[0].candidate.model_probability < 99
    assert rows[0].quote.best_odds == 1.80
    assert _rows([match], SearchFilters(probability_min=.99)) == []
    assert _rows([match], SearchFilters(quote_min=1.90)) == []
    assert match == original


@pytest.mark.parametrize("price", [1.02, 1.19])
def test_known_below_floor_esports_offer_is_not_displayed(monkeypatch, price):
    _prices(monkeypatch, price=price)
    assert _rows([_match()], SearchFilters()) == []


@pytest.mark.parametrize("changes", [
    {"participant1Name": "Wrong Team"}, {"startTime": "2026-08-02T18:00:00Z"},
])
def test_wrong_event_or_start_offer_cannot_satisfy_quote_range(monkeypatch, changes):
    _prices(monkeypatch, **changes)
    assert _rows([_match()], SearchFilters(quote_min=1.20)) == []
    assert len(_rows([_match()], SearchFilters())) == 1


def test_opposite_side_offer_is_not_used_for_the_favorite(monkeypatch):
    _prices(monkeypatch, price=1.02, opponent=8.00)
    assert _rows([_match()], SearchFilters(quote_min=1.20)) == []


def test_ambiguous_native_events_do_not_share_one_offer(monkeypatch):
    _prices(monkeypatch)
    assert _rows([_match(), dict(_match(), id=56)], SearchFilters(quote_min=1.20)) == []


def _manual_screen():
    import streamlit as st
    from test_unified_navigation import _navigation_namespace
    st.session_state["wettfinder_mode_v2"] = "Eigene Suche"
    namespace = _navigation_namespace(st, ("search",))
    namespace["_render_selected_finder"] = lambda sport, *_args, **kw: st.json({
        "sport": sport, "filters": vars(kw["search_filters"])})
    namespace["render_wettfinder"]()


def test_real_manual_controls_forward_probability_and_quote_ranges():
    app = AppTest.from_function(_manual_screen).run(timeout=30)
    assert not app.exception
    assert [x.value for x in app.subheader] == ["Manuelle Suche"]
    app.selectbox(key="finder_sport").select("Tennis")
    app.run(timeout=30)
    assert not app.exception
    app.slider(key="finder_manual_filters_probability").set_range(55, 75)
    app.checkbox(key="finder_manual_filters_quote_enabled").check()
    app.run(timeout=30)
    app.number_input(key="finder_manual_filters_quote_max").set_value(2.50)
    app.selectbox(key="finder_manual_market").select("Match-Sieger")
    app.run(timeout=30)
    assert not app.exception
    import json
    result = json.loads(app.json[0].value)
    assert result == {"sport": "Tennis", "filters": {
        "probability_min": .55, "probability_max": .75,
        "quote_min": 1.20, "quote_max": 2.50, "market_kind": "match_winner"}}


def test_all_sport_tabs_receive_the_same_filter_without_starting_a_scan():
    import json
    app = AppTest.from_function(_manual_screen).run(timeout=30)
    app.selectbox(key="finder_sport").select("Alle").run(timeout=30)
    assert not app.exception
    assert [json.loads(x.value)["sport"] for x in app.json] == [
        "Fußball", "Tennis", "Basketball", "Eishockey", "Cricket", "E-Sport"]
    assert all(json.loads(x.value)["filters"]["probability_min"] == 0 for x in app.json)
