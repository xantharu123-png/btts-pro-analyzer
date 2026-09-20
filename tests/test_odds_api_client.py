from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest
import requests

from api_budget import APIBudgetExceeded, APIBudgetUnavailable, APIBudgetPriority
from odds_api_client import OddsAPIClient, MONTH_PROVIDER, DAY_PROVIDER, request_cost

NOW = datetime(2030, 1, 15, 10, tzinfo=timezone.utc)
PATH = 'sports/tennis_atp_test/odds'
PARAMS = {'regions': 'eu', 'markets': 'h2h'}
KEY = 'test-key-not-a-real-credential'


def response(payload=None, headers=None, status=200):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = json.dumps(payload or []).encode()
    return result


def remaining(client, now=NOW, provider=MONTH_PROVIDER):
    governor = client.month if provider == MONTH_PROVIDER else client.day
    return governor.snapshot(api_key=KEY, provider=provider, now=now).remaining_estimate


@pytest.mark.parametrize('path,params,cost', [
    ('sports', {}, 0), ('sports/tennis_atp_test/events', {}, 0),
    (PATH, PARAMS, 1),
    (PATH, {'regions': 'eu,uk', 'markets': 'h2h,totals,h2h'}, 4),
    (PATH, {'bookmakers': ','.join(f'b{i}' for i in range(11)), 'markets': 'h2h,totals'}, 4),
    ('sports/tennis_atp_test/events/id123/odds', PARAMS, 1),
])
def test_worst_case_credit_cost(path, params, cost):
    assert request_cost(path, params) == cost


@pytest.mark.parametrize('path,params', [
    ('https://other.invalid/sports', {}), ('../sports', {}),
    ('historical/sports/tennis_atp_test/odds', PARAMS),
    (PATH, {'regions': 'eu,', 'markets': 'h2h'}),
    (PATH, {'regions': 'unknown', 'markets': 'h2h'}),
    (PATH, {'regions': 'eu', 'markets': True}),
])
def test_unknown_cost_fails_before_transport(tmp_path, path, params):
    client = OddsAPIClient(tmp_path / 'budget.db')
    with pytest.raises(APIBudgetUnavailable):
        client.get(path, api_key=KEY, params=params, get=lambda *_a, **_k: pytest.fail('HTTP'))


def test_day_limit_and_free_discovery_share_one_ledger(tmp_path):
    db = tmp_path / 'budget.db'
    client = OddsAPIClient(db)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        assert kwargs['allow_redirects'] is False
        return response()
    for _ in range(16):
        client.get(PATH, api_key=KEY, params=PARAMS, now=NOW, get=get)
    with pytest.raises(APIBudgetExceeded):
        OddsAPIClient(db).get(PATH, api_key=KEY, params=PARAMS, now=NOW, get=get)
    assert len(calls) == 16
    assert remaining(client) == 484
    client.get('sports/', api_key=KEY, now=NOW, get=get)
    assert len(calls) == 17 and remaining(client) == 484
    client.get(PATH, api_key=KEY, params=PARAMS, now=NOW + timedelta(days=1), get=get)
    assert remaining(client, NOW + timedelta(days=1)) == 483


def test_month_reserve_survives_midnight_and_resets_only_next_month(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    client.month.reconcile_usage(api_key=KEY, used=474, daily_limit=500,
                                provider=MONTH_PROVIDER, now=NOW)
    client.get(PATH, api_key=KEY, params=PARAMS, now=NOW, get=lambda *_a, **_k: response())
    with pytest.raises(APIBudgetExceeded):
        client.get(PATH, api_key=KEY, params=PARAMS, now=NOW + timedelta(days=1),
                   get=lambda *_a, **_k: pytest.fail('HTTP'))
    february = NOW.replace(month=2, day=1)
    client.get(PATH, api_key=KEY, params=PARAMS, now=february, get=lambda *_a, **_k: response())
    assert remaining(client, february) == 499


def test_multi_credit_reservation_is_atomic_at_floor(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    client.month.reconcile_usage(api_key=KEY, used=473, daily_limit=500,
                                provider=MONTH_PROVIDER, now=NOW)
    with pytest.raises(APIBudgetExceeded):
        client.get(PATH, api_key=KEY, params={'regions': 'eu', 'markets': 'h2h,totals,spreads'},
                   now=NOW, get=lambda *_a, **_k: pytest.fail('HTTP'))
    assert remaining(client) == 27


def test_shared_parallel_clients_cannot_overspend(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    def call(_index):
        try:
            client.get(PATH, api_key=KEY, params=PARAMS, now=NOW, get=lambda *_a, **_k: response())
            return True
        except APIBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(call, range(24)))
    assert sum(outcomes) == 16
    assert remaining(client) == 484


def test_provider_headers_reconcile_free_calls_without_raising_allowance(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    client.get('sports', api_key=KEY, now=NOW,
               get=lambda *_a, **_k: response(headers={'X-Requests-Remaining': '30', 'X-Requests-Used': '470'}))
    assert remaining(client) == 30
    client.get('sports', api_key=KEY, now=NOW,
               get=lambda *_a, **_k: response(headers={'x-requests-remaining': '500', 'x-requests-used': '0'}))
    assert remaining(client) == 30


def test_exhausted_provider_and_missing_ledger_never_make_paid_call(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    client.get('sports', api_key=KEY, now=NOW,
               get=lambda *_a, **_k: response(headers={'x-requests-remaining': '0'}))
    with pytest.raises(APIBudgetExceeded):
        client.get(PATH, api_key=KEY, params=PARAMS, now=NOW, get=lambda *_a, **_k: pytest.fail('HTTP'))
    with pytest.raises(APIBudgetUnavailable):
        OddsAPIClient(tmp_path)


def test_transport_failure_is_charged_conservatively_without_key_in_error_or_ledger(tmp_path):
    db = tmp_path / 'budget.db'
    client = OddsAPIClient(db)
    def fail(*_args, **_kwargs):
        raise requests.Timeout('URL contained apiKey=' + KEY)
    with pytest.raises(APIBudgetUnavailable) as error:
        client.get(PATH, api_key=KEY, params=PARAMS, now=NOW, get=fail)
    assert KEY not in str(error.value)
    assert remaining(client) == 499
    with sqlite3.connect(db) as connection:
        dump = '\n'.join(connection.iterdump())
    assert KEY not in dump


def test_cannot_override_auth_or_follow_redirects(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    with pytest.raises(APIBudgetUnavailable):
        client.get(PATH, api_key=KEY, params={**PARAMS, 'apiKey': 'another'},
                   get=lambda *_a, **_k: pytest.fail('HTTP'))
    def redirect(_url, **kwargs):
        assert kwargs['allow_redirects'] is False
        return response(status=302)
    assert client.get('sports', api_key=KEY, now=NOW, get=redirect).status_code == 302


def candidates_and_events():
    candidates, events = [], []
    for index, (a, b) in enumerate([('Alice Garcia', 'Bea Martin'), ('Carla Costa', 'Dana Silva')]):
        start = (NOW + timedelta(hours=6 + index)).isoformat()
        candidates.append(dict(candidate_id=f'c{index}', sport='Tennis', market_key='H2H',
                               competitor_a=a, competitor_b=b, selected_competitor=a,
                               scheduled_start=start, competition='ATP Test'))
        events.append(dict(id=f'e{index}', sport_key='tennis_atp_test', home_team=a, away_team=b,
                           commence_time=start, bookmakers=[dict(key=f'b{i}', title=f'Book {i}',
                           last_update=NOW.isoformat(), markets=[dict(key='h2h', outcomes=[
                               dict(name=a, price=1.9 + i/100), dict(name=b, price=2.05)])]) for i in range(3)]))
    return candidates, events


@pytest.mark.parametrize('alter', ['none', 'duplicate', 'foreign_id', 'wrong_side'])
def test_tennis_batch_has_one_credit_and_preserves_exact_binding(tmp_path, monkeypatch, alter):
    import market_consensus as market
    client = OddsAPIClient(tmp_path / 'budget.db')
    candidates, events = candidates_and_events()
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs['params']))
        if url.endswith('/sports'):
            return response([dict(key='tennis_atp_test', group='Tennis', active=True)])
        if url.endswith('/events'):
            return response(events)
        assert url.endswith('/sports/tennis_atp_test/odds')
        assert kwargs['params']['eventIds'] == 'e0,e1'
        payload = json.loads(json.dumps(events))
        if alter == 'duplicate':
            payload.append(payload[0])
        elif alter == 'foreign_id':
            payload[0]['id'] = 'not-requested'
        elif alter == 'wrong_side':
            payload[0]['home_team'] = 'Different Person'
        return response(payload)
    monkeypatch.setattr(market, 'odds_api_get', lambda path, **kwargs: client.get(path, **kwargs, now=NOW, get=get))
    quotes, errors = market.fetch_tennis_h2h_consensus(KEY, candidates, now=NOW)
    assert errors == []
    assert set(quotes) == ({'c0', 'c1'} if alter == 'none' else {'c1'})
    assert len(calls) == 3
    assert remaining(client) == 499


def test_scanner_uses_same_budgeted_transport(monkeypatch):
    from scanners import smart_bet_finder as scanner
    calls = []
    monkeypatch.setattr(scanner, 'odds_api_get', lambda path, **kwargs: calls.append((path, kwargs)) or response())
    scanner.OddsAPIClient(odds_api_key=KEY)._get_from_odds_api('A', 'B', 'soccer_epl', NOW.isoformat())
    assert len(calls) == 1
    assert calls[0][1]['api_key'] == KEY
    assert 'apiKey' not in calls[0][1]['params']


@pytest.mark.parametrize('cost', [0, -1, True, 1.5, '1'])
def test_invalid_cost_never_changes_quota(tmp_path, cost):
    client = OddsAPIClient(tmp_path / 'budget.db')
    with pytest.raises(APIBudgetUnavailable):
        client.month.reserve(api_key=KEY, endpoint=PATH, provider=MONTH_PROVIDER,
                             priority=APIBudgetPriority.BACKGROUND, now=NOW, cost=cost)
    assert remaining(client) == 500


def test_monthly_event_remains_auditable_late_in_month(tmp_path):
    db = tmp_path / 'budget.db'
    client = OddsAPIClient(db)
    late = NOW.replace(day=31)
    client.get(PATH, api_key=KEY, params=PARAMS, now=late, get=lambda *_a, **_k: response())
    with sqlite3.connect(db) as connection:
        month_row = connection.execute(
            'SELECT quota_day, started_at, decision FROM api_budget_events WHERE provider=?',
            (MONTH_PROVIDER,),
        ).fetchone()
    assert month_row == ('2030-01-01', late.isoformat(), 'COMPLETED')


def test_free_plan_is_not_promoted_by_larger_provider_headers(tmp_path):
    client = OddsAPIClient(tmp_path / 'budget.db')
    client.get('sports', api_key=KEY, now=NOW,
               get=lambda *_a, **_k: response(headers={'x-requests-remaining': '20000', 'x-requests-used': '0'}))
    assert remaining(client) == 500


def test_guard_errors_are_sanitized_and_expected_quota_is_not_job_failure(monkeypatch):
    import market_consensus as market
    from wettfinder_automation import _operational_quote_errors
    def blocked(*_args, **_kwargs):
        raise APIBudgetExceeded('must not expose ' + KEY)
    monkeypatch.setattr(market, 'odds_api_get', blocked)
    payload, error = market._odds_api_json(PATH, KEY, params=PARAMS)
    assert payload is None and error == 'APIBudgetExceeded'
    assert _operational_quote_errors(['Tennisquote test: APIBudgetExceeded']) == []
    assert _operational_quote_errors(['Tennisquote test: APIBudgetUnavailable'])
