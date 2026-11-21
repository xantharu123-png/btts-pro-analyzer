from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from daily_accumulators import _offers
from market_consensus import MarketConsensus, parse_fixture_consensus, parse_h2h_event_consensus
from test_market_consensus import _candidate, _gea_zhang_quote_fixture, _payload


def test_another_football_page_cannot_renew_a_bookmakers_38_minute_old_receipt():
    now = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
    recent = now - timedelta(minutes=2)
    entries = [_payload(stamp, provider_ids=True)['response'][0]
               for stamp in [now - timedelta(minutes=40), recent]]
    entries[0]['bookmakers'] = entries[0]['bookmakers'][:1]
    entries[1]['bookmakers'] = entries[1]['bookmakers'][1:]
    candidate = _candidate()
    quote = parse_fixture_consensus({'response': entries}, [candidate], fetched_at=now,
                                    entry_received_at=[now-timedelta(minutes=38), recent])[candidate['candidate_id']]
    # As in the worker: first persist and parse the exact provider response.
    restored = MarketConsensus.from_dict(quote.to_dict())
    offers = _offers(restored, now)
    assert 'api-football:1' not in offers
    assert set(offers) == {'api-football:2', 'api-football:3', 'api-football:4'}
    assert all(offer['fetched_at'] == '2030-01-01T09:58:00+00:00' for offer in offers.values())


@pytest.mark.parametrize('market,bet,side', [
    ('DC_1X', 'Double Chance', 'Home/Draw'),
    ('HOME_RANGE_1_3', 'Home Team Exact Goals Number', '1-3'),
])
def test_new_native_single_side_prices_keep_their_actual_page_time_without_a_partition(market,bet,side):
    now = datetime(2030,1,1,10,tzinfo=timezone.utc)
    payload = _payload(now, provider_ids=True)
    for book in payload['response'][0]['bookmakers']:
        book['bets'] = [{'name':bet, 'values':[{'value':side, 'odd':'1.62'}]}]
    candidate = _candidate(market)
    q = parse_fixture_consensus(payload, [candidate], fetched_at=now)[candidate['candidate_id']]
    raw = q.to_dict()
    assert raw['points'][0].get('fetched_at') == now.isoformat()
    assert not raw.get('native_market_partitions')
    assert _offers(MarketConsensus.from_dict(raw), now)['api-football:1']['odds'] == 1.62
    for point in [*raw['points'],raw['executable_quote']]:
        point.pop('fetched_at',None)
    legacy = MarketConsensus.from_dict(raw)
    assert legacy.to_dict() == raw
    assert _offers(legacy, now) == {}


def test_old_football_offer_needs_an_exact_partition_for_its_own_side_and_price():
    now = datetime(2030,1,1,10,tzinfo=timezone.utc)
    q = parse_fixture_consensus(_payload(now,provider_ids=True), [_candidate()], fetched_at=now)
    raw = next(iter(q.values())).to_dict()
    for point in [*raw['points'],raw['executable_quote']]:
        point.pop('fetched_at',None)
    restored = MarketConsensus.from_dict(raw)
    assert restored.to_dict() == raw
    assert len(_offers(restored,now)) == 4
    part = raw['native_market_partitions'][0]
    book = part['bookmaker_id']
    bad = deepcopy(part)
    next(item for item in bad['outcomes'] if item['selection'] == 'YES')['odds'] = 4.
    raw['native_market_partitions'][0] = bad
    assert book not in _offers(MarketConsensus.from_dict(raw), now)


def test_single_native_tennis_event_response_preserves_its_receipt_even_if_only_one_side_was_sent():
    now = datetime(2030,9,30,8,tzinfo=timezone.utc)
    candidate, payload = _gea_zhang_quote_fixture(now-timedelta(minutes=1))
    payload['bookmakers'][0]['markets'][0]['outcomes'].pop(0)
    q = parse_h2h_event_consensus(payload,[candidate],fetched_at=now)[candidate['candidate_id']]
    assert not q.native_market_partitions
    raw = q.to_dict()
    assert all('fetched_at' not in p for p in raw['points'])
    assert MarketConsensus.from_dict(raw).to_dict() == raw
    assert _offers(MarketConsensus.from_dict(raw),now) == {
        'odds-api:pinnacle': {'observed_at':'2030-09-30T07:59:00+00:00',
                              'fetched_at':'2030-09-30T08:00:00+00:00','odds':1.52}}


@pytest.mark.parametrize("timestamp", [
    "2030-01-01T09:59:59+00:00", "2030-01-01T10:00:01+00:00", "2030-01-01T10:00:00", "bad",
])
def test_bad_individual_clock_does_not_certify_an_offer_or_erase_other_books(timestamp):
    now = datetime(2030,1,1,10,tzinfo=timezone.utc)
    q = parse_fixture_consensus(_payload(now,provider_ids=True), [_candidate()], fetched_at=now)
    raw = next(iter(q.values())).to_dict()
    raw.pop("native_market_partitions")
    raw["points"][0]["fetched_at"] = timestamp
    offers = _offers(MarketConsensus.from_dict(raw), now)
    assert set(offers) == {'api-football:2', 'api-football:3', 'api-football:4'}


def test_disagreement_in_the_duplicate_executable_clock_only_withholds_that_book():
    now = datetime(2030,1,1,10,tzinfo=timezone.utc)
    q = parse_fixture_consensus(_payload(now,provider_ids=True), [_candidate()], fetched_at=now)
    raw = next(iter(q.values())).to_dict()
    raw.pop('native_market_partitions')
    disputed = raw['executable_quote']['bookmaker_id']
    raw['executable_quote']['fetched_at'] = '2030-01-01T09:59:00+00:00'
    restored = MarketConsensus.from_dict(raw)
    assert restored is not None and restored.best_odds == 1.91
    assert set(_offers(restored,now)) == {p['bookmaker_id'] for p in raw['points']} - {disputed}
