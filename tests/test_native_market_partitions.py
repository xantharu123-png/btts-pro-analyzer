"""Already received opposite prices survive without extra provider requests."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from market_consensus import MarketConsensus, exact_market_target, parse_fixture_consensus, parse_h2h_event_consensus
from test_forecast_market_comparison import NOW, START, candidate


def football_row(key="HOME_OVER_0_5", selection="Über 0.5"):
    return dict(candidate(), candidate_id="1:"+key, market_key=key, selection=selection)


def football_prices(row=None, *, books=None):
    row = row or football_row()
    payload = {"response": [{"fixture": {"id": 1, "date": START.isoformat()}, "update": NOW.isoformat(),
        "bookmakers": books or [{"id": 1, "name": "Native Book", "bets": [
            {"name": exact_market_target("HOME_OVER_0_5")[0], "values": [
                {"value": "Over 0.5", "odd": "1.4"}, {"value": "Under 0.5", "odd": "3.5"}]},
            {"name": "Match Winner", "values": [{"value": "Home", "odd": "2.0"},
                {"value": "Draw", "odd": "3.2"}, {"value": "Away", "odd": "4.0"}]},
            {"name": "Double Chance", "values": [{"value": "Home/Draw", "odd": "1.4"}]}]}]}]}
    return parse_fixture_consensus(payload, [row], fetched_at=NOW)[row["candidate_id"]]


def test_football_single_selected_side_keeps_both_native_line_prices():
    quote = football_prices()
    parts = quote.native_market_partitions
    assert len(parts) == 1
    assert parts[0]["market_key"] == "HOME_0_5"
    assert parts[0]["outcomes"] == [{"selection": "OVER", "odds": 1.4}, {"selection": "UNDER", "odds": 3.5}]
    assert MarketConsensus.from_dict(quote.to_dict()) == quote


def test_double_chance_retains_complete_result_partition_not_overlapping_dc_prices():
    quote = football_prices(football_row("DC_1X", "1X"))
    assert quote.best_odds == 1.4
    part, = quote.native_market_partitions
    assert part["market_key"] == "RESULT"
    assert [outcome["selection"] for outcome in part["outcomes"]] == ["HOME", "DRAW", "AWAY"]


@pytest.mark.parametrize("sport", ["basketball", "ice_hockey"])
def test_team_winner_keeps_real_counter_price(sport):
    from test_team_sport_prices import NOW as TEAM_NOW, game, odds, row
    from team_sport_prices import parse_game_quotes
    fixture = row(sport)
    native = game(sport)
    before = deepcopy((fixture, native))
    quote = parse_game_quotes(odds(native), [fixture], native, fetched_at=TEAM_NOW)[fixture["candidate_id"]]
    assert len(quote.native_market_partitions) == 3
    for part in quote.native_market_partitions:
        assert part["market_key"] == "H2H"
        assert {outcome["selection"] for outcome in part["outcomes"]} == {fixture["competitor_a"], fixture["competitor_b"]}
        assert len(part["outcomes"]) == 2 and all(outcome["odds"] > 1 for outcome in part["outcomes"])
    assert (fixture, native) == before


def test_esports_single_side_keeps_real_series_counter_price():
    from test_esports_prices import quote as esports_quote
    quote = esports_quote()
    assert len(quote.native_market_partitions) == 2
    assert all(len(part["outcomes"]) == 2 for part in quote.native_market_partitions)


def test_tennis_native_counterpart_is_retained_by_quote_parser_itself():
    from test_market_consensus import _gea_zhang_quote_fixture
    from test_riskobet_tennis_prices import NOW as TENNIS_NOW
    row, event = _gea_zhang_quote_fixture(TENNIS_NOW)
    quote = parse_h2h_event_consensus(event, [row], fetched_at=TENNIS_NOW)[row["candidate_id"]]
    part, = quote.native_market_partitions
    assert part["market_key"] == "H2H"
    assert {item["selection"]: item["odds"] for item in part["outcomes"]} == {
        "Arthur Gea": 1.52, "Zhang Zhizhen": 2.7}


def test_legacy_quotes_omit_new_optional_metadata_when_absent():
    from test_bet_finder_ui import _quote
    original = _quote()
    assert "native_market_partitions" not in original.to_dict()


@pytest.mark.parametrize('sport', ['football', 'tennis', 'basketball', 'ice_hockey', 'esports'])
def test_native_partition_serialization_is_json_native_and_roundtrips_each_price_source(sport):
    if sport == 'football':
        quote = football_prices()
    elif sport == 'tennis':
        from test_market_consensus import _gea_zhang_quote_fixture
        from test_riskobet_tennis_prices import NOW as TENNIS_NOW
        row, event = _gea_zhang_quote_fixture(TENNIS_NOW)
        quote = parse_h2h_event_consensus(event, [row], fetched_at=TENNIS_NOW)[row['candidate_id']]
    elif sport == 'esports':
        from test_esports_prices import quote as esports_quote
        quote = esports_quote()
    else:
        from test_team_sport_prices import NOW as TEAM_NOW, game, odds, row
        from team_sport_prices import parse_game_quotes
        fixture, native = row(sport), game(sport)
        quote = parse_game_quotes(odds(native), [fixture], native, fetched_at=TEAM_NOW)[fixture['candidate_id']]
    payload = quote.to_dict()
    assert type(payload['native_market_partitions']) is list and payload['native_market_partitions']
    stored = json.loads(json.dumps(payload, allow_nan=False))
    assert stored == payload
    loaded = MarketConsensus.from_dict(stored)
    assert loaded == quote and loaded.to_dict() == stored
    payload['native_market_partitions'].clear()
    assert quote.native_market_partitions  # Returned JSON containers own their copies.


def test_incomplete_cross_book_or_cross_receipt_partitions_are_not_invented():
    row = football_row()
    books = [{"id": 1, "name": "One", "bets": [{"name": exact_market_target("HOME_OVER_0_5")[0], "values": [
        {"value": "Over 0.5", "odd": "1.4"}]}]},
        {"id": 2, "name": "Other", "bets": [{"name": exact_market_target("HOME_OVER_0_5")[0], "values": [
        {"value": "Under 0.5", "odd": "3.5"}]}]}]
    assert not football_prices(row, books=books).native_market_partitions


@pytest.mark.parametrize('damage', ['period', 'family', 'book', 'clock', 'fetch', 'duplicate',
                                    'opposite_missing', 'selected_price', 'bool_price'])
def test_malformed_optional_partition_is_dropped_without_changing_valid_offer(damage):
    quote = football_prices()
    payload = quote.to_dict()
    part = payload['native_market_partitions'][0]
    if damage == 'period': part['period'] = 'first_half'
    elif damage == 'family': part['market_key'] = 'AWAY_0_5'
    elif damage == 'book': part['bookmaker_id'] = 'other'
    elif damage == 'clock': part['observed_at'] = (NOW-timedelta(seconds=1)).isoformat()
    elif damage == 'fetch': part['fetched_at'] = (NOW-timedelta(seconds=1)).isoformat()
    elif damage == 'duplicate': part['outcomes'][1]['selection'] = part['outcomes'][0]['selection']
    elif damage == 'opposite_missing': part['outcomes'].pop()
    elif damage == 'selected_price': part['outcomes'][0]['odds'] += .1
    else: part['outcomes'][1]['odds'] = True
    loaded = MarketConsensus.from_dict(payload)
    assert loaded is not None and loaded.best_odds == quote.best_odds
    assert loaded.native_market_partitions == ()


def test_tennis_reversed_provider_name_alias_keeps_both_real_prices():
    from test_forecast_tennis_market_capture import fixture
    _, document = fixture()
    observations = document['tennis_price_observations']
    assert len(observations) == 2
    for observation in observations:
        quote = MarketConsensus.from_dict(observation['reference_quote'])
        assert quote is not None and len(quote.native_market_partitions) == 1


def test_conflicting_complete_same_receipt_partition_is_dropped_not_last_wins():
    quote = football_prices()
    payload = quote.to_dict()
    other = deepcopy(payload['native_market_partitions'][0])
    other['outcomes'][1]['odds'] += .1
    payload['native_market_partitions'].append(other)
    loaded = MarketConsensus.from_dict(payload)
    assert loaded is not None and loaded.native_market_partitions == ()
