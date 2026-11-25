from datetime import datetime, timezone
import sqlite3
from zoneinfo import ZoneInfo

import pytest
import requests

from api_budget import APIBudgetGovernor
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
