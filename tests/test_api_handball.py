from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from zoneinfo import ZoneInfo

import pytest
import requests

from api_budget import APIBudgetGovernor
from scanners import api_handball as adapter
from scanners.api_handball import APIHandballClient, HandballSourceError


UTC = timezone.utc
NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
COUNTRY = {'id': 13, 'name': 'Germany', 'code': 'DE'}
LEAGUE = {'id': 39, 'name': 'Bundesliga', 'type': 'League'}


def catalogue():
    return {**LEAGUE, 'country': COUNTRY.copy(), 'seasons': [
        {'season': 2025, 'start': '2025-08-27', 'end': '2026-06-07', 'current': False},
        {'season': 2026, 'start': '2026-08-27', 'end': '2027-06-06', 'current': True},
    ]}


def game(game_id=106, *, start='2026-11-25T19:30:00+01:00', status='NS'):
    final = status == 'FT'
    return {
        'id': game_id,
        'date': start,
        'timestamp': int(datetime.fromisoformat(start).timestamp()),
        'country': COUNTRY.copy(),
        'league': {**LEAGUE, 'season': 2026},
        'status': {'short': status},
        'teams': {'home': {'id': 315, 'name': 'Füchse Berlin'}, 'away': {'id': 339, 'name': 'Gummersbach'}},
        'periods': {'first': {'home': 16 if final else None, 'away': 15 if final else None},
                    'second': {'home': 13 if final else None, 'away': 14 if final else None}},
        'scores': {'home': 29 if final else None, 'away': 29 if final else None},
    }


def bookmaker(book_id=4, name='Bet365'):
    return {'id': book_id, 'name': name, 'bets': [{'id': 1, 'name': '3Way Result', 'values': [
        {'value': 'Away', 'odd': '3.50'}, {'value': 'Home', 'odd': '1.55'}, {'value': 'Draw', 'odd': 9},
    ]}]}


def price(*books):
    return {'game_id': 106, 'league': {**LEAGUE, 'season': 2026}, 'country': COUNTRY.copy(),
            'updated': '2026-11-25T07:04:12+00:00', 'bookmakers': list(books)}


def response(endpoint, rows, **overrides):
    return {'get': endpoint, 'errors': [], 'results': len(rows), 'response': rows, **overrides}


class Response:
    headers = {'x-ratelimit-requests-limit': '100'}

    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self.payload, ValueError):
            raise self.payload
        return self.payload


@pytest.fixture
def api(tmp_path):
    db_path = tmp_path / 'budget.db'
    governor = APIBudgetGovernor(db_path, daily_limit=100,
                                 critical_floor=5, recommendation_reserve=10, background_reserve=15)
    replies = {
        'leagues': Response(response('leagues', [catalogue()])),
        'games': Response(response('games', [game()])),
        'odds': Response(response('odds', [price(bookmaker())])),
    }
    requests_made = []

    def get(url, **kwargs):
        requests_made.append((url, kwargs))
        reply = replies[url.rsplit('/', 1)[-1]]
        if isinstance(reply, requests.RequestException):
            raise reply
        return reply

    return APIHandballClient('dummy-test-key', governor=governor, get=get), replies, requests_made, db_path


def test_confirms_native_league_and_returns_utc_ordered_regulation_results(api):
    client, replies, calls, db_path = api
    replies['games'] = Response(response('games', [game(), game(105, start='2026-11-21T19:30:00+01:00', status='FT')]))
    matches = client.bundesliga_games(2026)
    assert [(match.game_id, match.status, match.home_score, match.away_score) for match in matches] == [
        (105, 'FT', 29, 29), (106, 'NS', None, None),
    ]
    match = matches[0]
    assert (match.league_id, match.season, match.home_id, match.away_id, match.home, match.away) == (
        39, 2026, 315, 339, 'Füchse Berlin', 'Gummersbach',
    )
    assert match.starts_at == datetime(2026, 11, 21, 18, 30, tzinfo=UTC)
    assert match.starts_at.tzinfo is UTC
    assert [(url, args['params']) for url, args in calls] == [
        ('https://v1.handball.api-sports.io/leagues', {'id': 39}),
        ('https://v1.handball.api-sports.io/games', {'league': 39, 'season': 2026}),
    ]
    assert all(args['headers'] == {'x-apisports-key': 'dummy-test-key'} and args['allow_redirects'] is False
               for _, args in calls)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute('SELECT provider, endpoint, http_status, error FROM api_budget_events ORDER BY id').fetchall() == [
            ('api-sports-handball', 'leagues', 200, None), ('api-sports-handball', 'games', 200, None),
        ]


@pytest.mark.parametrize('patch', [{'country': {'name': 'Austria', 'code': 'AT', 'id': 13}},
                                   {'id': 50}, {'type': 'Cup'}, {'seasons': []}])
def test_never_loads_games_for_unconfirmed_bundesliga_season(api, patch):
    client, replies, calls, _ = api
    replies['leagues'] = Response(response('leagues', [catalogue() | patch]))
    with pytest.raises(HandballSourceError, match='^handball_league_unconfirmed$'):
        client.bundesliga_games(2026)
    assert len(calls) == 1


def test_disallows_incomplete_pages_not_zero_games(api):
    client, replies, _, _ = api
    replies['games'] = Response(response('games', [game()], paging={'current': 1, 'total': 2}))
    with pytest.raises(HandballSourceError, match='^api_incomplete_page$'):
        client.bundesliga_games(2026)


@pytest.mark.parametrize('patch', [{'league': {**LEAGUE, 'season': 2025}},
                                   {'timestamp': 1}, {'country': {'name': 'Germany', 'id': 13, 'code': 'AT'}},
                                   {'teams': {'home': {'id': 315, 'name': 'Berlin'},
                                              'away': {'id': 315, 'name': 'Gummersbach'}}}])
def test_native_game_identity_contradictions_stop_the_season(api, patch):
    client, replies, _, _ = api
    replies['games'] = Response(response('games', [game() | patch]))
    with pytest.raises(HandballSourceError, match='^handball_invalid_game$'):
        client.bundesliga_games(2026)


def test_duplicate_event_id_cannot_vote_twice_in_training(api):
    client, replies, _, _ = api
    replies['games'] = Response(response('games', [game(), game()]))
    with pytest.raises(HandballSourceError, match='^handball_duplicate_game$'):
        client.bundesliga_games(2026)


def test_ft_score_disagreeing_with_regulation_halves_is_not_training_data(api):
    client, replies, _, _ = api
    bad_game = game(105, start='2026-11-24T18:30:00+00:00', status='FT') | {'scores': {'home': 31, 'away': 29}}
    replies['games'] = Response(response('games', [bad_game, game()]))
    matches = client.bundesliga_games(2026)
    assert [(m.game_id, m.status, m.home_score, m.away_score) for m in matches] == [
        (105, 'FT', None, None), (106, 'NS', None, None),
    ]


@pytest.mark.parametrize('status', ['POST', 'AOT', 'AP', 'AW', 'H1'])
def test_native_non_regulation_statuses_never_supply_training_score(api, status):
    client, replies, _, _ = api
    replies['games'] = Response(response('games', [game(status=status) | {'scores': {'home': 31, 'away': 29}}]))
    [match] = client.bundesliga_games(2026)
    assert (match.status, match.home_score, match.away_score) == (status, None, None)


def test_uses_one_bookmakers_exact_ordered_regulation_triplet_only(api):
    client, replies, calls, _ = api
    partial = bookmaker(5, 'partial')
    partial['bets'][0]['values'].pop()
    wrong_period = bookmaker(6, 'half')
    wrong_period['bets'][0]['name'] = '3Way Result - 1st Half'
    wrong_id = bookmaker(7, 'wrong-id')
    wrong_id['bets'][0]['id'] = 2
    duplicate = bookmaker(8, 'duplicated-side')
    duplicate['bets'][0]['values'].append({'value': 'Home', 'odd': 2.00})
    replies['odds'] = Response(response('odds', [price(partial, wrong_period, wrong_id, duplicate, bookmaker())]))
    [match] = client.bundesliga_games(2026)
    assert client.prices(match, now=NOW) == {'Bet365': (1.55, 9.0, 3.5)}
    assert calls[-1][0] == 'https://v1.handball.api-sports.io/odds'
    assert calls[-1][1]['params'] == {'game': 106, 'bet': 1}


@pytest.mark.parametrize('patch', [{'game_id': 105}, {'league': {**LEAGUE, 'season': 2025}},
                                   {'updated': '2026-11-23T04:00:00+00:00'},
                                   {'updated': '2026-11-25T12:00:01+00:00'},
                                   {'updated': '2026-11-25T11:00:00'},
                                   {'date': '2026-11-25T18:29:00+00:00'},
                                   {'timestamp': 1},
                                   {'teams': {'home': {'id': 339}, 'away': {'id': 315}}}])
def test_prices_with_wrong_identity_or_clock_cannot_enter_benchmark(api, patch):
    client, replies, _, _ = api
    replies['odds'] = Response(response('odds', [price(bookmaker()) | patch]))
    [match] = client.bundesliga_games(2026)
    assert client.prices(match, now=NOW) == {}


def test_kickoff_blocks_request_and_does_not_look_like_an_observed_quote(api):
    client, _, calls, _ = api
    [match] = client.bundesliga_games(2026)
    assert client.prices(match, now=match.starts_at) == {}
    assert len(calls) == 2


def test_price_age_uses_elapsed_time_on_autumn_clock_change(api):
    client, replies, _, _ = api
    replies['games'] = Response(response('games', [game(start='2026-10-25T21:00:00+01:00')]))
    # 36 h 30 min old in absolute time but only 35 h 30 min on the local clock.
    replies['odds'] = Response(response('odds', [price(bookmaker()) | {'updated': '2026-10-24T01:30:00Z'}]))
    [match] = client.bundesliga_games(2026)
    now = datetime(2026, 10, 25, 15, tzinfo=ZoneInfo('Europe/Berlin'))
    assert client.prices(match, now=now) == {}


def test_minute_reserve_denies_tenth_call_before_network(api):
    client, _, calls, _ = api
    [match] = client.bundesliga_games(2026)
    for _ in range(7):
        assert client.prices(match, now=NOW)
    with pytest.raises(HandballSourceError, match='^api_rate_limit_deferred$'):
        client.prices(match, now=NOW)
    assert len(calls) == 9


@pytest.mark.parametrize(('reply', 'code'), [
    (Response({'errors': {'plan': 'private-provider-text'}, 'response': []}), 'api_plan_error'),
    (Response({'errors': {'quota': 'private-provider-text'}, 'response': []}), 'api_reported_error'),
    (Response({'errors': [], 'response': []}, status=429), 'api_rate_limit'),
    (Response(ValueError('private-provider-text')), 'api_invalid_json'),
    (requests.Timeout('private-provider-text'), 'api_transport_error'),
])
def test_provider_fault_is_distinguished_from_no_games_and_never_persists_raw_text(api, reply, code):
    client, replies, _, db_path = api
    replies['games'] = reply
    with pytest.raises(HandballSourceError, match=f'^{code}$') as caught:
        client.bundesliga_games(2026)
    assert caught.value.code == code
    with sqlite3.connect(db_path) as connection:
        assert connection.execute('SELECT error FROM api_budget_events ORDER BY id DESC LIMIT 1').fetchone() == (code,)


# Test-only native IDs; the production adapter must discover these from the catalogue.
EUROPE = (
    ('ES', 'Spain', 301, 'Liga ASOBAL', 801),
    ('DE', 'Germany', 13, 'Bundesliga', 39),
    ('DK', 'Denmark', 303, 'Herre Handbold Ligaen', 803),
    ('FR', 'France', 304, 'Starligue', 804),
    ('HU', 'Hungary', 305, 'NB I', 805),
)


def europa_profile(code):
    profile = next((p for p in getattr(adapter, 'HANDBALL_LEAGUES', ()) if p.code == code), None)
    assert profile is not None, f'no catalogue profile for {code}'
    return profile


def european_catalogue(entry):
    code, country, country_id, name, native_id = entry
    return catalogue() | {'id': native_id, 'name': name, 'country': {
        'id': country_id, 'name': country, 'code': code,
    }}


def identity(row):
    return {'country': row['country'].copy(), 'league': {
        'id': row['id'], 'name': row['name'], 'type': row['type'], 'season': 2026,
    }}


def test_five_exact_leagues_share_one_catalogue_and_use_discovered_native_ids(api):
    client, replies, calls, _ = api
    catalogue_rows = [european_catalogue(item) for item in EUROPE]
    replies['leagues'] = Response(response('leagues', catalogue_rows + [
        catalogue_rows[0] | {'id': 901, 'name': 'Liga ASOBAL Women'},
        catalogue_rows[0] | {'id': 902, 'type': 'Cup'},
        catalogue_rows[0] | {'id': 903, 'country': {'id': 9, 'name': 'Portugal', 'code': 'PT'}},
    ]))
    assert [(p.code, p.name) for p in getattr(adapter, 'HANDBALL_LEAGUES', ())] == [
        ('ES', 'Liga ASOBAL'), ('DE', 'Bundesliga'), ('DK', 'Herre Handbold Ligaen'),
        ('FR', 'Starligue'), ('HU', 'NB I'),
    ]
    expected_requests = [('leagues', {})]
    for entry, row in zip(EUROPE, catalogue_rows, strict=True):
        replies['games'] = Response(response('games', [game() | identity(row)]))
        [match] = client.league_games(europa_profile(entry[0]), 2026)
        assert (match.league_id, match.season, match.game_id) == (entry[-1], 2026, 106)
        expected_requests.append(('games', {'league': entry[-1], 'season': 2026}))
    assert [(url.rsplit('/', 1)[-1], args['params']) for url, args in calls] == expected_requests


@pytest.mark.parametrize('problem', ['wrong_name', 'wrong_code', 'wrong_country', 'second_match',
                                    'same_id_unrelated_league', 'reserved_german_id', 'wrong_type',
                                    'no_season', 'bad_season_start', 'invalid_id'])
def test_unconfirmed_league_does_not_block_another_leagues_season(api, problem):
    client, replies, calls, _ = api
    spanish, danish = map(european_catalogue, (EUROPE[0], EUROPE[2]))
    uncertain = {
        'wrong_name': [spanish | {'name': 'ASOBAL'}],
        'wrong_code': [spanish | {'country': spanish['country'] | {'code': 'AD'}}],
        'wrong_country': [spanish | {'country': spanish['country'] | {'name': 'Portugal'}}],
        'second_match': [spanish, spanish | {'id': 999}],
        'same_id_unrelated_league': [spanish, spanish | {'name': 'First Division'}],
        'reserved_german_id': [spanish | {'id': 39}],
        'wrong_type': [spanish | {'type': 'Cup'}],
        'no_season': [spanish | {'seasons': spanish['seasons'][:1]}],
        'bad_season_start': [spanish | {'seasons': [{'season': 2026, 'start': '2025-08-27', 'end': '2027-06-06'}]}],
        'invalid_id': [spanish | {'id': '801'}],
    }[problem]
    replies['leagues'] = Response(response('leagues', [*uncertain, danish]))
    replies['games'] = Response(response('games', [game() | identity(danish)]))
    with pytest.raises(HandballSourceError, match='^handball_league_unconfirmed$'):
        client.league_games(europa_profile('ES'), 2026)
    [match] = client.league_games(europa_profile('DK'), 2026)
    assert match.league_id == 803
    assert [(url.rsplit('/', 1)[-1], args['params']) for url, args in calls] == [
        ('leagues', {}), ('games', {'league': 803, 'season': 2026}),
    ]


def test_denied_catalogue_is_not_retried_for_the_next_country(api):
    client, replies, calls, _ = api
    replies['leagues'] = Response({'errors': {'plan': 'private-provider-text'}})
    for code in ('ES', 'DE', 'DK', 'FR', 'HU'):
        with pytest.raises(HandballSourceError, match='^api_plan_error$'):
            client.league_games(europa_profile(code), 2026)
    assert [(url.rsplit('/', 1)[-1], args['params']) for url, args in calls] == [('leagues', {})]


@pytest.mark.parametrize(('start', 'country_patch'), [
    ('2026-11-25T19:30:00+01:00', {'id': 99}),
    ('2027-06-07T00:00:00+02:00', {}),
])
def test_games_require_the_confirmed_country_id_and_local_season_dates(api, start, country_patch):
    client, replies, _, _ = api
    french = european_catalogue(EUROPE[3])
    replies['leagues'] = Response(response('leagues', [french]))
    invalid = game(start=start) | identity(french)
    invalid['country'].update(country_patch)
    replies['games'] = Response(response('games', [invalid]))
    with pytest.raises(HandballSourceError, match='^handball_invalid_game$'):
        client.league_games(europa_profile('FR'), 2026)


def test_non_german_prices_bind_the_confirmed_league_country_and_season(api):
    client, replies, calls, _ = api
    french = european_catalogue(EUROPE[3])
    replies['leagues'] = Response(response('leagues', [french]))
    replies['games'] = Response(response('games', [game() | identity(french)]))
    [match] = client.league_games(europa_profile('FR'), 2026)
    correct = price(bookmaker()) | identity(french)
    replies['odds'] = Response(response('odds', [correct]))
    assert client.prices(match, now=NOW) == {'Bet365': (1.55, 9.0, 3.5)}
    assert calls[-1][1]['params'] == {'game': 106, 'bet': 1}
    for patch in (
        {'country': correct['country'] | {'name': 'Spain'}},
        {'country': correct['country'] | {'id': 99}},
        {'league': correct['league'] | {'id': 39}},
        {'league': correct['league'] | {'name': 'Proligue'}},
        {'league': correct['league'] | {'season': 2025}},
    ):
        replies['odds'] = Response(response('odds', [correct | patch]))
        assert client.prices(match, now=NOW) == {}
    assert client.prices(replace(match, league_id=39), now=NOW) == {}
    assert len(calls) == 8


def test_prices_do_not_treat_a_relabelled_game_as_a_second_leagues_match(api):
    client, replies, calls, _ = api
    spanish, german = map(european_catalogue, EUROPE[:2])
    replies['leagues'] = Response(response('leagues', [spanish, german]))
    replies['games'] = Response(response('games', [game(start='2026-11-25T20:00:00+01:00') | identity(spanish)]))
    [match] = client.league_games(europa_profile('ES'), 2026)
    replies['games'] = Response(response('games', [game()]))
    [german_match] = client.league_games(europa_profile('DE'), 2026)
    assert match.game_id == german_match.game_id
    # An odds relay without optional time and team metadata must not hide a cross-league mix-up.
    assert client.prices(replace(match, league_id=39), now=NOW) == {}
    assert len(calls) == 3


def native_price(game_id=106, *, updated='2026-11-25T07:04:12+00:00'):
    return {
        'game': {'id': game_id},
        'league': {**LEAGUE, 'season': 2026, 'logo': 'https://example.test/league.png'},
        'country': {**COUNTRY, 'flag': 'https://example.test/country.png'},
        'update': updated,
        'bookmakers': [bookmaker()],
    }


def test_native_league_odds_are_matched_to_the_confirmed_upcoming_games_in_one_request(api):
    client, replies, calls, _ = api
    replies['games'] = Response(response('games', [
        game(), game(105, start='2026-11-24T19:00:00+00:00', status='FT'),
        game(104, start='2026-11-25T11:30:00+00:00'),
    ]))
    partial = bookmaker(5, 'partial')
    partial['bets'][0]['values'].pop()
    native = native_price()
    native['bookmakers'].append(partial)
    replies['odds'] = Response(response('odds', [native, native_price(105), native_price(104), native_price(999)]))
    assert client.league_prices(europa_profile('DE'), 2026, now=NOW) == {}
    assert calls == []
    client.league_games(europa_profile('DE'), 2026)
    markets = client.league_prices(europa_profile('DE'), 2026, now=NOW)
    assert set(markets) == {106}
    assert markets[106].updated_at == datetime(2026, 11, 25, 7, 4, 12, tzinfo=UTC)
    assert markets[106].bookmakers == {'Bet365': (1.55, 9.0, 3.5)}
    assert [(url.rsplit('/', 1)[-1], args['params']) for url, args in calls] == [
        ('leagues', {}), ('games', {'league': 39, 'season': 2026}),
        ('odds', {'league': 39, 'season': 2026, 'bet': 1}),
    ]


@pytest.mark.parametrize('legacy', [False, True], ids=['league-batch', 'individual-game'])
@pytest.mark.parametrize(('source', 'received', 'kickoff', 'accepted'), [
    ('2026-11-25T12:00:01Z', '2026-11-25T12:00:02Z', '2026-11-25T18:30:00Z', True),
    ('2026-11-24T00:00:00Z', '2026-11-25T12:00:02Z', '2026-11-25T18:30:00Z', False),
    ('2026-11-24T00:00:02Z', '2026-11-25T12:00:02Z', '2026-11-25T18:30:00Z', True),
    ('2026-11-25T11:59:59Z', '2026-11-25T12:00:02Z', '2026-11-25T12:00:02Z', False),
    ('2026-11-25T11:59:59Z', '2026-11-25T12:00:02Z', '2026-11-25T12:00:01Z', False),
    ('2026-11-25T11:59:58Z', '2026-11-25T11:59:59Z', '2026-11-25T18:30:00Z', False),
    ('2026-11-25T11:59:59Z', '2026-11-25T12:00:02', '2026-11-25T18:30:00Z', False),
], ids=['in-flight-update', 'expired-in-flight', 'exact-36h-at-receipt', 'kickoff', 'after-kickoff',
        'clock-reversed', 'naive-receipt-clock'])
def test_odds_validate_provider_time_and_kickoff_at_receipt(tmp_path, legacy, source, received, kickoff, accepted):
    profile = europa_profile('DE')
    current = NOW
    payloads = {'leagues': [catalogue()], 'games': [game(start=kickoff)], 'odds': [native_price(updated=source)]}

    def get(url, **_):
        nonlocal current
        endpoint = url.rsplit('/', 1)[-1]
        if endpoint == 'odds':
            current = datetime.fromisoformat(received)
        return Response(response(endpoint, payloads[endpoint]))

    governor = APIBudgetGovernor(tmp_path / 'budget.db', daily_limit=100, critical_floor=5,
                                 recommendation_reserve=10, background_reserve=15)
    client = APIHandballClient('dummy-test-key', governor=governor, get=get, clock=lambda: current)
    [match] = client.league_games(profile, 2026)
    if legacy:
        books = client.prices(match, now=NOW)
    else:
        market = client.league_prices(profile, 2026, now=NOW).get(match.game_id)
        books = market.bookmakers if market else {}

    assert books == ({'Bet365': (1.55, 9.0, 3.5)} if accepted else {})


@pytest.mark.parametrize('patch', [
    {'game_id': 105},
    {'game_id': '106'},
    {'updated': '2026-11-25T07:04:13+00:00'},
    {'updated': '2026-11-25T07:04:12'},
    {'update': '2026-11-23T23:59:00+00:00'},
    {'update': '2026-11-25T12:00:01+00:00'},
    {'game': {'id': 106, 'date': '2026-11-25T18:00:00+00:00'}},
    {'country': {**COUNTRY, 'id': 99}},
    {'league': {**LEAGUE, 'season': 2025}},
])
def test_native_odds_reject_conflicting_aliases_or_invalid_identity_and_clock(api, patch):
    client, replies, _, _ = api
    client.league_games(europa_profile('DE'), 2026)
    replies['odds'] = Response(response('odds', [native_price() | patch]))
    assert client.league_prices(europa_profile('DE'), 2026, now=NOW) == {}


def test_matching_aliases_are_accepted_but_conflicting_duplicate_prices_are_not(api):
    client, replies, _, _ = api
    replies['games'] = Response(response('games', [game(), game(107)]))
    client.league_games(europa_profile('DE'), 2026)
    valid = native_price() | {'game_id': 106, 'updated': '2026-11-25T08:04:12+01:00'}
    first = native_price(107)
    contradictory = native_price(107, updated='2026-11-25T07:05:01+00:00')
    replies['odds'] = Response(response('odds', [valid, valid.copy(), first, contradictory, first]))
    markets = client.league_prices(europa_profile('DE'), 2026, now=NOW)
    assert set(markets) == {106}


def test_duplicate_markets_with_different_bookmaker_ids_are_not_identical(api):
    client, replies, _, _ = api
    client.league_games(europa_profile('DE'), 2026)
    first, contradictory = native_price(), native_price() | {'bookmakers': [bookmaker(99)]}
    replies['odds'] = Response(response('odds', [first, contradictory]))
    assert client.league_prices(europa_profile('DE'), 2026, now=NOW) == {}


def test_verified_paid_handball_caps_the_worker_at_eleven_requests(api):
    client, replies, calls, _ = api
    for reply in replies.values():
        reply.headers = {'X-RateLimit-Limit': '300', 'X-Ratelimit-Requests-Limit': '7500'}
    [match] = client.bundesliga_games(2026)
    for _ in range(9):
        assert client.prices(match, now=NOW)
    with pytest.raises(HandballSourceError, match='^api_rate_limit_deferred$'):
        client.prices(match, now=NOW)
    assert len(calls) == 11


@pytest.mark.parametrize('headers', [
    {'x-ratelimit-requests-limit': '7500'},
    {'x-ratelimit-requests-limit': '7500', 'x-ratelimit-limit': '10'},
    {'x-ratelimit-requests-limit': '100', 'x-ratelimit-limit': '300'},
])
def test_unverified_paid_rate_stays_at_nine_requests(api, headers):
    client, replies, calls, _ = api
    for reply in replies.values():
        reply.headers = headers
    [match] = client.bundesliga_games(2026)
    for _ in range(7):
        assert client.prices(match, now=NOW)
    with pytest.raises(HandballSourceError, match='^api_rate_limit_deferred$'):
        client.prices(match, now=NOW)
    assert len(calls) == 9


def test_paid_europe_worker_executes_eleven_native_requests_and_binds_each_price(tmp_path):
    from handball_pilot import run_europe

    db_path = tmp_path / 'budget.db'
    catalogue_rows = [european_catalogue(entry) for entry in EUROPE]
    rows_by_id = {row['id']: row for row in catalogue_rows}
    expected_home_prices = {801: 1.8, 39: 1.9, 803: 2.0, 804: 2.1, 805: 2.2}
    history = [game(number, start=(NOW - timedelta(days=number)).isoformat(), status='FT')
               for number in range(1, 41)]
    calls = []

    def get(url, *, params, **kwargs):
        endpoint = url.rsplit('/', 1)[-1]
        calls.append((endpoint, params))
        if endpoint == 'leagues':
            rows = catalogue_rows
        else:
            league_id = params['league']
            league_identity = identity(rows_by_id[league_id])
            if endpoint == 'games':
                rows = [row | league_identity for row in [*history, game(), game(107)]]
            else:
                assert endpoint == 'odds'
                good = native_price() | league_identity
                good['bookmakers'][0]['bets'][0]['values'][1]['odd'] = str(expected_home_prices[league_id])
                wrong_country = native_price(107) | league_identity | {
                    'country': {'id': 555, 'name': 'Austria', 'code': 'AT'},
                }
                rows = [good, wrong_country]
        reply = Response(response(endpoint, rows))
        reply.headers = {'X-RateLimit-Limit': '300', 'X-RateLimit-Requests-Limit': '7500',
                         'X-RateLimit-Requests-Remaining': '7490'}
        return reply

    client = APIHandballClient('dummy-test-key', governor=APIBudgetGovernor(db_path), get=get)
    report = run_europe(client, directory=tmp_path, clock=lambda: NOW)

    assert calls[0] == ('leagues', {})
    assert len(calls) == 11
    assert len({params['league'] for endpoint, params in calls if endpoint == 'odds'}) == 5
    for code, _, _, _, native_id in EUROPE:
        assert calls.count(('games', {'league': native_id, 'season': 2026})) == 1
        assert calls.count(('odds', {'league': native_id, 'season': 2026, 'bet': 1})) == 1
        lane = report['leagues'][code]
        assert (lane['price_checks'], lane['quote_fixtures'], lane['priced'], lane['modelled']) == (1, 1, 1, 2)
        suffix = '' if code == 'DE' else f'_{code.lower()}'
        forecasts = json.loads((tmp_path / f'handball_pilot{suffix}_2026.json').read_text(encoding='utf-8'))['forecasts']
        assert forecasts['106']['fixture'][0] == native_id
        assert forecasts['106']['odds'] == {'Bet365': [expected_home_prices[native_id], 9.0, 3.5]}
        assert forecasts['106']['price_source_at'] == '2026-11-25T07:04:12+00:00'
        assert forecasts['106']['price_observed_at'] == NOW.isoformat()
        assert 'odds' not in forecasts['107']
