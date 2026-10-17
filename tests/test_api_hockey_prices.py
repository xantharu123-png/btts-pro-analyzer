"""Native API-Hockey prices never borrow NHL/name-only identities."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import SimpleNamespace

import pytest

from market_consensus import MarketConsensus, observed_consensus, quote_below_publication_floor
from model_artifacts import canonical_bytes
import team_sport_prices as prices
from test_team_sport_prices import NOW, Governor, _worker_snapshot, game, odds, row


def native_row(side='home', **changes):
    candidate = row('ice_hockey', side, fixture_source='API-Hockey', provider_event_id='81',
                    competitor_a_id='11', competitor_b_id='22', competition='National League')
    candidate.update(changes)
    return candidate


def native_game():
    return dict(id=81, date=native_row()['scheduled_start'],
                league={'id': 23, 'name': 'National League', 'season': 2026},
                status={'short': 'NS'},
                teams={'home': {'id': 11, 'name': 'Team 1'},
                       'away': {'id': 22, 'name': 'Team 8'}})


@pytest.mark.parametrize('side', ['home', 'away'])
@pytest.mark.parametrize('competition', ['National League', 'Swiss League'])
def test_native_price_requires_own_game_and_bilateral_team_ids(side, competition):
    candidate, native = native_row(side, competition=competition), native_game()
    native['league']['name'] = competition
    quote = prices.parse_game_quotes(odds(native), [candidate], native, fetched_at=NOW)[candidate['candidate_id']]
    assert quote.origin_provider == 'API-Hockey'
    assert quote.origin_event_id == quote.provider_event_id == '81'
    assert MarketConsensus.from_dict(quote.to_dict()) == quote
    assert observed_consensus(quote, candidate=candidate, now=NOW) == quote
    assert not quote.is_fresh(NOW)
    assert prices._binding(candidate)[7:] == ('11', '22')


@pytest.mark.parametrize('mutation', [
    {'competitor_a_id': None}, {'competitor_b_id': ''}, {'competitor_a_id': True},
    {'competitor_a_id': 11},
    {'competitor_a_id': '011'}, {'competitor_a_id': '22'}, {'competitor_a_id': '33'},
    {'competitor_a_id': '9'*5000}, {'provider_event_id': '081'},
    {'provider_event_id': '82'}, {'provider_event_id': 81}, {'provider_event_id': ' 81 '},
    {'fixture_source': 'api-hockey'}, {'fixture_source': ' API-Hockey '},
    {'competition': 'national league'}, {'competition': 'Unreviewed League'},
])
def test_native_candidate_cannot_substitute_missing_or_changed_identity(mutation):
    candidate = dict(native_row(), **mutation)
    native = native_game()
    assert prices.parse_game_quotes(odds(native), [candidate], native, fetched_at=NOW) == {}


@pytest.mark.parametrize('mutation', ['event', 'home_id', 'away_id', 'reversed', 'league', 'start', 'finished', 'duplicate'])
def test_native_game_cannot_supply_another_fixture_or_role(mutation):
    candidate, native = native_row(), native_game()
    if mutation == 'event':
        native['id'] = 82
    elif mutation == 'home_id':
        native['teams']['home']['id'] = 33
    elif mutation == 'away_id':
        native['teams']['away']['id'] = True
    elif mutation == 'reversed':
        native['teams']['home']['id'], native['teams']['away']['id'] = 22, 11
    elif mutation == 'league':
        native['league']['name'] = 'Swiss League'
    elif mutation == 'start':
        native['date'] = '2026-09-05T19:00:00+00:00'
    elif mutation == 'finished':
        native['status']['short'] = 'FT'
    supplied = [native, deepcopy(native)] if mutation == 'duplicate' else [native]
    assert prices.match_game(candidate, supplied, ('Team 1', 'Team 8')) is None


@pytest.mark.parametrize('value,excluded', [('1.19', True), ('1.1999999999', True), ('1.20', False)])
def test_native_price_floor_uses_real_exact_offer(value, excluded):
    candidate, native = native_row(), native_game()
    quote = prices.parse_game_quotes(odds(native, home=value), [candidate], native, fetched_at=NOW)[candidate['candidate_id']]
    assert quote_below_publication_floor(quote, candidate=candidate, now=NOW) is excluded


def test_native_cache_is_role_bound_and_shared_across_same_model_revisions(tmp_path):
    path, calls, governor = tmp_path/'prices.json', [], Governor()
    native = native_game()
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, headers={}, json=lambda:
            {'errors': [], 'response': [native] if url.endswith('/games') else odds(native)})
    candidates = [native_row(side) for side in ('home', 'away')]
    summary = prices.refresh_team_sport_prices(candidates, api_key='fixture', now=NOW,
        path=path, governor=governor, get=get)
    assert summary['checked'] == 1 and summary['quotes'] == 2
    assert len(calls) == len(governor.completed) == 2
    assert all(call['provider'] == 'api-sports-ice_hockey' for call in governor.calls)
    changed_model = dict(candidates[0], candidate_id='new-model', key='new-model')
    assert prices.load_cached_quote(changed_model, now=NOW, path=path).best_odds == 1.75
    replacement = dict(changed_model, competitor_a_id='33')
    assert prices._key(replacement) != prices._key(changed_model)
    assert prices.load_cached_quote(replacement, now=NOW, path=path) is None
    assert len(calls) == 2  # Reader/model revision never contacts a provider.


def test_native_conflicting_role_ids_fail_before_any_request(tmp_path):
    def unexpected(*args, **kwargs):
        raise AssertionError('No provider permitted for ambiguous native roles')
    candidate = native_row()
    other = dict(native_row('away'), competitor_a_id='33')
    summary = prices.refresh_team_sport_prices([candidate, other], api_key='fixture', now=NOW,
        path=tmp_path/'prices.json', governor=Governor(), get=unexpected)
    assert summary['checked'] == summary['quotes'] == 0
    assert summary['errors'] == ['ice_hockey:ValueError']


def test_snapshot_transport_adds_native_ids_only_to_api_hockey():
    legacy = _worker_snapshot()
    assert hashlib.sha256(canonical_bytes(prices.snapshot_price_rows((legacy,)))).hexdigest() == (
        'be6aab06041636f634afe6fbde43ea70ddae3e6ffbada04e3a8bbaca81334c04')
    forecast = replace(legacy.team_sport_forecast, sport='ice_hockey', provider='API-Hockey',
        provider_event_id='81', home_id='11', away_id='22', model_scope='including_overtime_shootout')
    native = SimpleNamespace(team_sport_forecast=forecast, event_key='ice_hockey:api-hockey:81',
                             starts_at=legacy.starts_at, competition='National League')
    projected = prices.snapshot_price_rows((native,))
    assert len(projected) == 2
    assert all((r['competitor_a_id'], r['competitor_b_id']) == ('11', '22') for r in projected)
    assert all(prices._binding(r) for r in projected)


@pytest.mark.parametrize('sport,key,quote_hash', [
    ('basketball', 'a22e98c898b6c5dc6b5632d70f07d50dfb5a71649ef53339185aecfed94e73b7',
     '360b7faea1442c67f328b02e1d808c3cb592d1df0907a91731b05420cfabf78c'),
    ('ice_hockey', 'c6f53dca96db57e2b1fdde6b8ab1c351d5ab6d9f46520122491527dabe71b0be',
     '1eaa5740c974ac93664ea3b22e177e2fbae7be4009071969a954ab224a276320'),
])
def test_existing_nhl_and_basketball_price_identity_bytes_are_unchanged(sport, key, quote_hash):
    candidate, native = row(sport), game(sport)
    assert len(prices._binding(candidate)) == 7
    assert prices._key(candidate) == key
    quote = prices.parse_game_quotes(odds(native), [candidate], native, fetched_at=NOW)[candidate['candidate_id']]
    payload = quote.to_dict()
    assert len(payload.pop('native_market_partitions')) == 3
    # Measurement metadata is new; the quote's existing identity/price bytes
    # and a legacy persisted quote without that optional field stay unchanged.
    assert hashlib.sha256(canonical_bytes(payload)).hexdigest() == quote_hash
    assert canonical_bytes(MarketConsensus.from_dict(payload).to_dict()) == canonical_bytes(payload)
