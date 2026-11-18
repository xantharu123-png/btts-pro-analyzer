"""Owner 18.11.2026 („Ja, reparieren“): a provider rate limit must not drop tomorrow's leagues.

Evidence from the production request ledger (``api_budget_events``, read only, since 08.11.2026): every HTTP 429 on
API-Football came 1.3 to 3.0 s after the tenth API-Hockey request within one minute (12 of 19 such minutes) and
never after nine or fewer (0 of 15). The price refresh sends up to eight odds requests plus one to three game
requests per sport, so it reached exactly the ten requests a minute of the free API-Sports plans. On 18.11.2026 the
block lasted about 20 s; the night run's search for tomorrow started inside it and lost 34 of 66 leagues.

Three parts: (A) the price refresh stays below the minute limit, (B) a worker's football provider waits once after
a rate limit and retries, (C) no single requests are fired into a rate limit.
"""
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

import api_budget
import challenge_15k
import riskobet_settlement_automation as settlement
import team_sport_prices as prices
import wettfinder_automation as automation
from api_budget import APIBudgetGovernor, APIBudgetPriority
from test_team_sport_prices import NOW, Governor, odds, row

SIDE = 'api-sports-basketball'
HOCKEY = 'api-sports-ice_hockey'


def _governor(tmp_path):
    return APIBudgetGovernor(tmp_path / 'budget.db', daily_limit=100,
                             critical_floor=5, recommendation_reserve=10, background_reserve=15)


def _reserve(governor, when, *, provider=SIDE, api_key='test'):
    return governor.reserve(api_key=api_key, endpoint='games', priority=APIBudgetPriority.BACKGROUND,
                            provider=provider, now=when)


# --- (A) the ledger knows the last minute, the refresh stays below ten requests ------------------------------------

def test_ledger_counts_recent_requests_per_provider_and_account(tmp_path):
    governor = _governor(tmp_path)
    start = datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)
    for seconds in (0, 10, 70):
        _reserve(governor, start + timedelta(seconds=seconds))
    _reserve(governor, start + timedelta(seconds=70), provider='api-sports-ice_hockey')
    _reserve(governor, start + timedelta(seconds=70), api_key='other-account')

    def count(seconds_after, **changes):
        arguments = dict(api_key='test', provider=SIDE, seconds=60, now=start + timedelta(seconds=seconds_after))
        return governor.recent_request_count(**{**arguments, **changes})

    assert count(12) == 2
    assert count(60) == 2  # a request exactly sixty seconds old still counts
    assert count(75) == 1  # only the request at +70 s is younger than a minute
    assert count(75, provider='api-sports-ice_hockey') == 1
    assert count(75, provider='api-football') == 0
    assert count(75, api_key='nobody') == 0
    assert count(200) == 0


def test_blocked_reservations_are_not_requests(tmp_path):
    governor = APIBudgetGovernor(tmp_path / 'budget.db', daily_limit=20,
                                 critical_floor=1, recommendation_reserve=2, background_reserve=18)
    start = datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)
    for _ in range(2):
        _reserve(governor, start)
    with pytest.raises(api_budget.APIBudgetExceeded):
        _reserve(governor, start)  # never sent: below the background reserve
    assert governor.recent_request_count(api_key='test', provider=SIDE, seconds=60, now=start) == 2


def test_a_request_that_failed_was_still_sent(tmp_path):
    governor = _governor(tmp_path)
    start = datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)
    governor.complete(_reserve(governor, start), http_status=500, error='ValueError',
                      now=start + timedelta(seconds=1))
    governor.complete(_reserve(governor, start), http_status=200, now=start + timedelta(seconds=1))
    assert governor.recent_request_count(api_key='test', provider=SIDE, seconds=60,
                                         now=start + timedelta(seconds=5)) == 2


def test_a_corrupt_ledger_is_a_deferral_as_before_and_no_operational_error(tmp_path):
    governor = _governor(tmp_path)
    (tmp_path / 'budget.db').write_bytes(b'this is not a database ' * 80)
    with pytest.raises(api_budget.APIBudgetUnavailable):
        governor.recent_request_count(api_key='test', provider=SIDE, seconds=60)
    calls, rows = [], _events(2)
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=tmp_path / 'prices.json',
                                               governor=governor, get=_transport(rows, calls))
    # No bound from the ledger; the reservation of the request itself then defers the game, as before.
    assert calls == [] and summary['errors'] == [] and summary['status'] == 'budget_deferred'
    assert summary['budget_deferred'] == ['basketball:APIBudgetUnavailable'] * 2


def _events(count, *, dates=1, days=None, **changes):
    """`count` basketball games with their own teams, spread over `dates` UTC days (or the given day offsets)."""
    result = []
    for index in range(count):
        start = NOW + timedelta(hours=6, minutes=index, days=days[index] if days else index % dates)
        result.append(row(**{**dict(provider_event_id=f'event-{index}', competitor_a=f'Club {index}',
                                    competitor_b=f'Guest {index}', selected_competitor=f'Club {index}',
                                    selection=f'Club {index}', candidate_id=f'candidate-{index}',
                                    key=f'candidate-{index}', scheduled_start=start.isoformat()), **changes}))
    return result


def _game(name, *, hours=6.0, **changes):
    """One basketball game with its own teams, `hours` after NOW."""
    start = NOW + timedelta(hours=hours)
    return row(**{**dict(provider_event_id=f'event-{name}', competitor_a=f'Club {name}',
                         competitor_b=f'Guest {name}', selected_competitor=f'Club {name}', selection=f'Club {name}',
                         candidate_id=f'candidate-{name}', key=f'candidate-{name}',
                         scheduled_start=start.isoformat()), **changes})


NHL_SCHEDULE = 'https://api-web.nhle.com/v1/schedule/'


def _nhl_rows():
    """Both sides of one native NHL game (Ottawa at home against Washington), six hours after NOW."""
    return [row('ice_hockey', side=side, provider_event_id='2026020288', competitor_a='OTT', competitor_b='WSH',
                selected_competitor='OTT' if side == 'home' else 'WSH') for side in ('home', 'away')]


def _nhl_week(url, *, listed=True):
    """Like api-web.nhle.com/v1/schedule/{date}: seven days from that date, the game under its date."""
    start = NOW + timedelta(hours=6)
    entry = {'id': 2026020288, 'startTimeUTC': start.isoformat().replace('+00:00', 'Z'),
             'homeTeam': {'abbrev': 'OTT', 'placeName': {'default': 'Ottawa'}, 'commonName': {'default': 'Senators'}},
             'awayTeam': {'abbrev': 'WSH', 'placeName': {'default': 'Washington'},
                          'commonName': {'default': 'Capitals'}}}
    first = date.fromisoformat(url.rsplit('/', 1)[1])
    return {'gameWeek': [{'date': (first + timedelta(days=i)).isoformat(),
                          'games': [entry] if listed and first + timedelta(days=i) == start.date() else []}
                         for i in range(7)]}


def _transport(rows, calls, priced=None):
    games = {index + 1: dict(id=index + 1, date=r['scheduled_start'], league={'name': r['competition']},
                             status={'short': 'NS'},
                             teams={'home': {'name': r['competitor_a']}, 'away': {'name': r['competitor_b']}})
             for index, r in enumerate(rows)}

    def get(url, **kwargs):
        assert url.startswith(prices.HOSTS['basketball']), url
        calls.append(url.rsplit('/', 1)[-1])
        if url.endswith('/games'):
            day = kwargs['params']['date']
            response = [game for game in games.values() if game['date'].startswith(day)]
        else:
            if priced is not None:
                priced.append(games[kwargs['params']['game']]['teams']['home']['name'])
            response = odds(games[kwargs['params']['game']])
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {'errors': [], 'response': response})
    return get


def _document(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_price_refresh_stays_below_the_minute_limit_of_the_side_api(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, calls = _governor(tmp_path), tmp_path / 'prices.json', []
    rows = _events(8, dates=2)  # two game requests plus eight odds requests would be ten in one minute
    get = _transport(rows, calls)
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=path, governor=governor, get=get)
    assert prices.SIDE_REQUESTS_PER_MINUTE == 9
    assert calls.count('games') == 2 and calls.count('odds') == 7 and len(calls) == 9
    assert summary['checked'] == 7 and summary['status'] == 'complete'
    assert summary['budget_deferred'] == ['basketball:minute_limit'] and summary['errors'] == []
    assert governor.recent_request_count(api_key='test', provider=SIDE, seconds=60) == 9
    # The game left out keeps no attempt stamp: the next run takes it, the seven priced games rest three hours.
    del calls[:]
    clock[0] += timedelta(minutes=30)
    later = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW + timedelta(minutes=30), path=path,
                                             governor=governor, get=get)
    assert calls == ['games', 'odds'] and later['checked'] == 1 and later['budget_deferred'] == []
    assert later['quotes'] == 8


def test_minute_limit_counts_what_other_code_requested_in_the_same_minute(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, calls = _governor(tmp_path), []
    for _ in range(5):  # e.g. the scanner of the same run, 55 s earlier: still inside the minute
        _reserve(governor, clock[0] - timedelta(seconds=55))
    rows = _events(8)
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=tmp_path / 'prices.json',
                                               governor=governor, get=_transport(rows, calls))
    assert calls == ['games', 'odds', 'odds', 'odds']
    assert summary['checked'] == 3 and summary['budget_deferred'] == ['basketball:minute_limit']


def test_a_game_on_a_new_day_needs_room_for_its_game_list_too(tmp_path, monkeypatch):
    # The shape of 18.11.2026: seven games on one UTC day, one on the next. The eighth needs a game list and
    # its odds; with one request left it must wait, or the minute would reach ten.
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, calls = _governor(tmp_path), []
    rows = _events(8, days=[0] * 7 + [1])
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=tmp_path / 'prices.json',
                                               governor=governor, get=_transport(rows, calls))
    assert calls.count('games') == 1 and calls.count('odds') == 7
    assert summary['checked'] == 7 and summary['budget_deferred'] == ['basketball:minute_limit']
    assert governor.recent_request_count(api_key='test', provider=SIDE, seconds=60) == 8


def test_a_game_left_out_goes_first_in_the_next_due_run(tmp_path, monkeypatch):
    # The quotes timer and REFRESH_AFTER are both three hours: the seven priced games are often due again in
    # the next run. Without precedence the same late game would wait run after run.
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, calls, priced = _governor(tmp_path), tmp_path / 'prices.json', [], []
    rows = _events(8, dates=2)
    get = _transport(rows, calls, priced)
    prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=path, governor=governor, get=get)
    assert sorted(priced) == [f'Club {index}' for index in (0, 1, 2, 3, 4, 5, 6)]
    waiting = _document(path)['minute_deferred']
    assert len(waiting) == 1 and '|event-7|' in waiting[0] and waiting[0] not in _document(path)['attempts']
    del calls[:], priced[:]
    step = timedelta(hours=3, seconds=5)
    clock[0] += step
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW + step, path=path,
                                               governor=governor, get=get)
    assert priced[0] == 'Club 7' and len(calls) == 9
    assert summary['budget_deferred'] == ['basketball:minute_limit'] and summary['quotes'] == 8
    waiting = _document(path)['minute_deferred']
    assert len(waiting) == 1 and '|event-7|' not in waiting[0]
    # The game left out this time keeps its older quote; it is neither refreshed nor dropped.
    left_out = next(r for r in rows if f"|{r['provider_event_id']}|" in waiting[0])
    assert prices.load_cached_quote(left_out, now=NOW + step, path=path) is not None


def test_a_waiting_price_only_row_never_passes_a_model_row(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, calls, priced = _governor(tmp_path), tmp_path / 'prices.json', [], []
    snapshot = _events(1)[0]
    model = row(provider_event_id='model-1', competitor_a='Club M', competitor_b='Guest M',
                selected_competitor='Club M', selection='Club M', candidate_id='model', key='model',
                source='team_sport_research', scheduled_start=(NOW + timedelta(hours=9)).isoformat())
    get = _transport([snapshot, model], calls, priced)
    for _ in range(9):
        _reserve(governor, clock[0] - timedelta(seconds=20))
    prices.refresh_team_sport_prices([snapshot], api_key='test', now=NOW, path=path, governor=governor, get=get)
    assert calls == [] and len(_document(path)['minute_deferred']) == 1
    clock[0] += timedelta(minutes=5)
    for _ in range(7):  # room for one game list and one odds request
        _reserve(governor, clock[0] - timedelta(seconds=20))
    prices.refresh_team_sport_prices([snapshot, model], api_key='test', now=NOW + timedelta(minutes=5), path=path,
                                     governor=governor, get=get)
    assert priced == ['Club M'] and calls == ['games', 'odds']
    assert '|event-0|' in _document(path)['minute_deferred'][0]


def test_who_waits_longest_goes_first(tmp_path, monkeypatch):
    # Room for one game per run (a game list and its odds), three games due in every run: each one gets its
    # turn. Ordered by start alone, the earliest of the waiting games would pass the one that waits longer.
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, calls, priced = _governor(tmp_path), tmp_path / 'prices.json', [], []
    rows = [_game(name, hours=20 + index / 60) for index, name in enumerate('XYZ')]
    get = _transport(rows, calls, priced)
    step = timedelta(hours=3, seconds=5)
    waiting = []
    for run in range(4):
        for _ in range(7):
            _reserve(governor, clock[0] - timedelta(seconds=20))
        prices.refresh_team_sport_prices(rows, api_key='test', now=NOW + run * step, path=path,
                                         governor=governor, get=get)
        waiting.append([key.split('|')[2] for key in _document(path)['minute_deferred']])
        clock[0] += step
    assert priced == ['Club X', 'Club Y', 'Club Z', 'Club X']
    assert waiting == [['event-Y', 'event-Z'], ['event-Z', 'event-X'], ['event-X', 'event-Y'],
                       ['event-Y', 'event-Z']]


def test_a_waiting_game_keeps_its_place_while_the_cap_keeps_it_out(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, calls, priced = _governor(tmp_path), tmp_path / 'prices.json', [], []
    waiting_game, earlier_game = _game('0'), _game('V', hours=5)
    models = [_game(f'M{index}', hours=8 + index / 60, source='team_sport_research') for index in range(8)]
    get = _transport([waiting_game, earlier_game, *models], calls, priced)
    for _ in range(9):
        _reserve(governor, clock[0] - timedelta(seconds=20))
    prices.refresh_team_sport_prices([waiting_game], api_key='test', now=NOW, path=path, governor=governor, get=get)
    assert priced == [] and len(_document(path)['minute_deferred']) == 1
    # Second run: eight model rows take the per-sport cap, the waiting game is not reached.
    clock[0] += timedelta(minutes=5)
    prices.refresh_team_sport_prices([waiting_game, *models], api_key='test', now=NOW + timedelta(minutes=5),
                                     path=path, governor=governor, get=get)
    assert len(priced) == 8 and 'Club 0' not in priced
    assert [key.split('|')[2] for key in _document(path)['minute_deferred']] == ['event-0']
    # Third run: the model rows rest, room for one game. The game that waits goes before the earlier start.
    del priced[:]
    clock[0] += timedelta(minutes=5)
    for _ in range(7):
        _reserve(governor, clock[0] - timedelta(seconds=20))
    prices.refresh_team_sport_prices([waiting_game, earlier_game, *models], api_key='test',
                                     now=NOW + timedelta(minutes=10), path=path, governor=governor, get=get)
    assert priced == ['Club 0']
    assert [key.split('|')[2] for key in _document(path)['minute_deferred']] == ['event-V']


def test_a_waiting_game_that_is_gone_leaves_the_list(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path = _governor(tmp_path), tmp_path / 'prices.json'
    gone, other = _game('0'), _game('1', hours=7)

    def unexpected(*args, **kwargs):
        raise AssertionError('the minute is used up')
    for run, rows in enumerate(([gone, other], [other])):  # the second run no longer lists the first game
        for _ in range(9):
            _reserve(governor, clock[0] - timedelta(seconds=20))
        prices.refresh_team_sport_prices(rows, api_key='test', now=NOW + run * timedelta(minutes=5), path=path,
                                         governor=governor, get=unexpected)
        assert [key.split('|')[2] for key in _document(path)['minute_deferred']] == \
            [r['provider_event_id'] for r in rows]
        clock[0] += timedelta(minutes=5)


def test_each_sport_has_its_own_minute(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, calls = _governor(tmp_path), []
    for _ in range(9):
        _reserve(governor, clock[0] - timedelta(seconds=20), provider=HOCKEY)
    hockey, basketball = _nhl_rows(), _events(3)
    side_api = _transport(basketball, calls)

    def get(url, **kwargs):
        if url.startswith(NHL_SCHEDULE):
            return SimpleNamespace(status_code=200, headers={}, json=lambda: _nhl_week(url))
        return side_api(url, **kwargs)  # asserts the basketball host: no hockey request may be sent

    summary = prices.refresh_team_sport_prices([*hockey, *basketball], api_key='test', now=NOW,
                                               path=tmp_path / 'prices.json', governor=governor, get=get)
    assert calls == ['games', 'odds', 'odds', 'odds']
    assert summary['checked'] == 3 and summary['status'] == 'complete'
    assert summary['budget_deferred'] == ['ice_hockey:minute_limit'] and summary['identity_gaps'] == []
    assert governor.recent_request_count(api_key='test', provider=HOCKEY, seconds=60) == 9


def test_a_used_up_minute_does_not_hide_an_identity_gap(tmp_path, monkeypatch):
    # An event that became ambiguous needs no request: its old quote goes and the gap is reported, also when
    # the minute is used up.
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, calls = _governor(tmp_path), tmp_path / 'prices.json', []
    first = row()
    prices.refresh_team_sport_prices([first], api_key='test', now=NOW, path=path, governor=governor,
                                     get=_transport([first], calls))
    assert prices.load_cached_quote(first, now=NOW, path=path) is not None
    step = timedelta(hours=3, seconds=5)
    clock[0] += step
    for _ in range(9):
        _reserve(governor, clock[0] - timedelta(seconds=20))
    duplicate = dict(first, provider_event_id='other-native-event', candidate_id='other', key='other')

    def unexpected(*args, **kwargs):
        raise AssertionError('no request for an ambiguous event')
    summary = prices.refresh_team_sport_prices([first, duplicate], api_key='test', now=NOW + step, path=path,
                                               governor=governor, get=unexpected)
    assert summary['identity_gaps'] == ['basketball:ambiguous_origin_events'] * 2
    assert summary['budget_deferred'] == [] and summary['status'] == 'complete' and summary['quotes'] == 0
    assert prices.load_cached_quote(first, now=NOW + step, path=path) is None


def test_games_left_out_do_not_use_up_the_cap_of_eight(tmp_path, monkeypatch):
    # Eight games wait for the minute; a later pair that became ambiguous is still reached and reported.
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path = _governor(tmp_path), tmp_path / 'prices.json'
    for _ in range(9):
        _reserve(governor, clock[0] - timedelta(seconds=20))
    late = row(scheduled_start=(NOW + timedelta(hours=7)).isoformat())
    duplicate = dict(late, provider_event_id='other-native-event', candidate_id='other', key='other')

    def unexpected(*args, **kwargs):
        raise AssertionError('the minute is used up and an ambiguous event needs no request')
    summary = prices.refresh_team_sport_prices([*_events(8), late, duplicate], api_key='test', now=NOW, path=path,
                                               governor=governor, get=unexpected)
    assert summary['identity_gaps'] == ['basketball:ambiguous_origin_events'] * 2
    assert summary['budget_deferred'] == ['basketball:minute_limit'] and summary['checked'] == 0
    assert len(_document(path)['minute_deferred']) == 8


def test_a_used_up_minute_does_not_hide_an_nhl_game_that_left_the_schedule(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 18, 2, 41, 24, tzinfo=timezone.utc)]
    monkeypatch.setattr(api_budget, '_utc_now', lambda: clock[0])
    governor, path, hockey, listed = _governor(tmp_path), tmp_path / 'prices.json', _nhl_rows(), [True]
    native = dict(id=81, date=hockey[0]['scheduled_start'], league={'name': 'NHL'}, status={'short': 'NS'},
                  teams={'home': {'name': 'Ottawa Senators'}, 'away': {'name': 'Washington Capitals'}})

    def get(url, **kwargs):
        if url.startswith(NHL_SCHEDULE):
            return SimpleNamespace(status_code=200, headers={}, json=lambda: _nhl_week(url, listed=listed[0]))
        assert listed[0] and url.startswith(prices.HOSTS['ice_hockey']), url
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {
            'errors': [], 'response': [native] if url.endswith('/games') else odds(native)})

    first = prices.refresh_team_sport_prices(hockey, api_key='test', now=NOW, path=path, governor=governor, get=get)
    assert first['quotes'] == 2 and first['identity_gaps'] == []
    step = timedelta(hours=3, seconds=5)
    clock[0] += step
    for _ in range(9):
        _reserve(governor, clock[0] - timedelta(seconds=20), provider=HOCKEY)
    listed[0] = False
    summary = prices.refresh_team_sport_prices(hockey, api_key='test', now=NOW + step, path=path,
                                               governor=governor, get=get)
    assert summary['identity_gaps'] == ['ice_hockey:native_identity_unbound']
    assert summary['budget_deferred'] == [] and summary['quotes'] == 0


def test_refresh_without_a_ledger_double_is_unchanged(tmp_path):
    calls, rows = [], _events(8, dates=2)
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=tmp_path / 'prices.json',
                                               governor=Governor(), get=_transport(rows, calls))
    assert len(calls) == 10 and summary['checked'] == 8 and summary['budget_deferred'] == []


def test_an_unreadable_ledger_gives_no_bound_and_does_not_stop_the_refresh(tmp_path):
    class Unreadable(Governor):
        def recent_request_count(self, **kwargs):
            raise api_budget.APIBudgetUnavailable('ledger locked')
    calls, rows = [], _events(8, dates=2)
    summary = prices.refresh_team_sport_prices(rows, api_key='test', now=NOW, path=tmp_path / 'prices.json',
                                               governor=Unreadable(), get=_transport(rows, calls))
    assert len(calls) == 10 and summary['checked'] == 8 and summary['errors'] == []


# --- (B) one bounded wait after a rate limit, only where a worker asks for it ---------------------------------------

class _Response:
    def __init__(self, status, response=(), errors=None):
        self.status_code, self.headers, self._response, self._errors = status, {}, list(response), errors or []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Client Error', response=self)

    def json(self):
        return {'errors': self._errors, 'response': self._response}


def _provider(monkeypatch, statuses, *, worker):
    provider = challenge_15k.ChallengeDataProvider('test-key', None)
    if worker:
        provider.enable_rate_limit_retry()
    monkeypatch.setattr(provider, '_rate_limit', lambda: None)
    sleeps, calls, queue = [], [], list(statuses)
    monkeypatch.setattr(challenge_15k.time, 'sleep', sleeps.append)

    def fetch(url, **kwargs):
        calls.append(kwargs['label'])
        return _Response(queue.pop(0) if queue else 200, [{'fixture': {'id': 1}}])
    monkeypatch.setattr(challenge_15k, 'api_football_get', fetch)
    return provider, calls, sleeps


def test_worker_provider_waits_once_and_retries_a_rate_limited_request(monkeypatch):
    provider, calls, sleeps = _provider(monkeypatch, [429, 200], worker=True)
    data = provider.upcoming_fixtures(78, 2026, NOW.date())
    assert data == [{'fixture': {'id': 1}}]
    assert calls == ['Fixtures Liga 78', 'Fixtures Liga 78']
    assert sleeps == [challenge_15k.RATE_LIMIT_RETRY_DELAY_SECONDS] == [30.0]
    # The first answer is not an operational error once the retry succeeded.
    assert provider.errors == [] and provider.last_request_rate_limited is False


def test_default_provider_never_waits(monkeypatch):
    # App pages, manual scans and price paths: a visitor must not wait half a minute.
    provider, calls, sleeps = _provider(monkeypatch, [429, 200], worker=False)
    assert provider.upcoming_fixtures(78, 2026, NOW.date()) is None
    assert calls == ['Fixtures Liga 78'] and sleeps == []
    assert len(provider.errors) == 1 and provider.errors[0].startswith('Fixtures Liga 78: 429')
    assert provider.last_request_rate_limited is True and provider.last_request_budget_deferred is False


def test_a_lasting_rate_limit_costs_one_wait_per_provider_not_one_per_request(monkeypatch):
    provider, calls, sleeps = _provider(monkeypatch, [429] * 6, worker=True)
    results = [provider.upcoming_fixtures(league, 2026, NOW.date()) for league in (78, 39, 140, 135)]
    assert results == [None] * 4
    assert calls == ['Fixtures Liga 78', 'Fixtures Liga 78', 'Fixtures Liga 39', 'Fixtures Liga 140',
                     'Fixtures Liga 135']
    assert sleeps == [30.0] and len(provider.errors) == 4
    assert provider.last_request_rate_limited is True


def test_only_a_rate_limit_is_retried(monkeypatch):
    provider, calls, sleeps = _provider(monkeypatch, [503, 200], worker=True)
    assert provider.upcoming_fixtures(78, 2026, NOW.date()) is None
    assert calls == ['Fixtures Liga 78'] and sleeps == []
    assert provider.last_request_rate_limited is False
    # A later rate limit of the same provider still gets its one wait.
    provider, calls, sleeps = _provider(monkeypatch, [503, 429, 200], worker=True)
    provider.upcoming_fixtures(78, 2026, NOW.date())
    assert provider.upcoming_fixtures(39, 2026, NOW.date()) == [{'fixture': {'id': 1}}]
    assert calls == ['Fixtures Liga 78', 'Fixtures Liga 39', 'Fixtures Liga 39'] and sleeps == [30.0]


def test_worker_helper_enables_the_wait_and_tolerates_test_doubles(monkeypatch):
    provider = automation._worker_football_provider('test-key', None)
    assert isinstance(provider, challenge_15k.ChallengeDataProvider)
    assert provider._retry_rate_limited is True
    assert challenge_15k.ChallengeDataProvider('test-key', None)._retry_rate_limited is False
    double = object()
    monkeypatch.setattr(automation, 'ChallengeDataProvider', lambda *_args: double)
    assert automation._worker_football_provider('test-key', None) is double


def test_the_night_and_quotes_workers_build_their_football_providers_with_the_helper():
    import inspect
    source = inspect.getsource(automation)
    # The scan for today and tomorrow, the context refresh, the appearance history and the result settlement.
    assert source.count('_worker_football_provider(') == 5  # the helper itself and four worker call sites
    worker_calls = [line.strip() for line in source.splitlines()
                    if 'ChallengeDataProvider(' in line and 'def ' not in line]
    assert worker_calls == ['provider = ChallengeDataProvider(api_key, weather_key)']


def test_the_night_runs_riskobet_results_wait_too(monkeypatch):
    # run_riskobet_settlements builds its own football provider; only the night run's result stage uses it.
    created = []

    class Double:
        def __init__(self, *_args):
            self.waits = False
            created.append(self)

        def enable_rate_limit_retry(self):
            self.waits = True
    monkeypatch.setattr(settlement, 'ChallengeDataProvider', Double)
    config = SimpleNamespace(api_football_key='test-key', weather_key=None)
    arguments = dict(config=config, tennis_db_path='unused', esports_db_path='unused')
    assert callable(settlement._default_loader('football', football_provider=None, **arguments))
    assert [provider.waits for provider in created] == [True]
    # A provider handed in by the caller is used as it is.
    given = Double()
    assert callable(settlement._default_loader('football', football_provider=given, **arguments))
    assert given.waits is False and len(created) == 2


# --- (C) no single requests into a rate limit ----------------------------------------------------------------------

def test_details_do_not_fire_single_requests_into_a_rate_limit(monkeypatch):
    provider, calls, sleeps = _provider(monkeypatch, [429] * 9, worker=False)
    assert provider.details_by_fixture([11, 12, 13]) == {11: None, 12: None, 13: None}
    assert calls == ['Fixture-Details'] and sleeps == []
    # With the worker's wait the batch itself is retried once; still no single requests when that fails too.
    provider, calls, sleeps = _provider(monkeypatch, [429] * 9, worker=True)
    assert provider.details_by_fixture([11, 12, 13]) == {11: None, 12: None, 13: None}
    assert calls == ['Fixture-Details', 'Fixture-Details'] and sleeps == [30.0]


def test_details_keep_the_single_request_fallback_for_other_failures(monkeypatch):
    provider, calls, _sleeps = _provider(monkeypatch, [503, 200, 200], worker=False)
    result = provider.details_by_fixture([1, 2])
    assert calls == ['Fixture-Details', 'Fixture-Details 1', 'Fixture-Details 2']
    assert result[1] == {'fixture': {'id': 1}} and result[2] is None  # the double answers fixture 1 only


def test_an_earlier_rate_limit_does_not_switch_off_a_later_fallback(monkeypatch):
    # The flag belongs to the last request only. Here the batch fails without an HTTP error (the provider
    # reports an error in the body), after an earlier request of the same provider was rate limited.
    provider = challenge_15k.ChallengeDataProvider('test-key', None)
    monkeypatch.setattr(provider, '_rate_limit', lambda: None)
    monkeypatch.setattr(challenge_15k.time, 'sleep', lambda seconds: pytest.fail('a plain provider never waits'))
    answers = [_Response(429), _Response(200, errors={'requests': 'provider trouble'}),
               _Response(200, [{'fixture': {'id': 1}}]), _Response(200, [{'fixture': {'id': 2}}])]
    calls = []

    def fetch(url, **kwargs):
        calls.append(kwargs['label'])
        return answers.pop(0)
    monkeypatch.setattr(challenge_15k, 'api_football_get', fetch)
    assert provider.upcoming_fixtures(78, 2026, NOW.date()) is None
    assert provider.last_request_rate_limited is True
    result = provider.details_by_fixture([1, 2])
    assert calls == ['Fixtures Liga 78', 'Fixture-Details', 'Fixture-Details 1', 'Fixture-Details 2']
    assert result == {1: {'fixture': {'id': 1}}, 2: {'fixture': {'id': 2}}}
    assert provider.last_request_rate_limited is False
