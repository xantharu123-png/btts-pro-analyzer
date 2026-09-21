from contextlib import closing
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from esports_shadow import EsportsShadowLog, settle_due_predictions
from test_esports_shadow import _match

NOW = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)
RESULT = dict(winner_team_id=7, team1_id=7, team2_id=8, score1=2, score2=0, termination='normal')


def overdue(log, match_id, *, checked=None):
    log.log_predictions([_match(match_id)])
    with closing(log._connect()) as con:
        con.execute('UPDATE esports_shadow_predictions SET scheduled_at=?,logged_at=?,last_checked_at=? WHERE match_id=?',
                    ((NOW-timedelta(days=1)).isoformat(), (NOW-timedelta(days=2)).isoformat(),
                     checked.isoformat() if checked else None, match_id))
        con.commit()


def test_future_and_unknown_kickoffs_never_consume_result_budget(tmp_path):
    log = EsportsShadowLog(tmp_path/'esports.db')
    log.log_predictions([_match(i) for i in range(1, 16)])
    with closing(log._connect()) as con:
        con.execute('UPDATE esports_shadow_predictions SET scheduled_at=NULL WHERE match_id=1')
        con.commit()
    overdue(log, 99, checked=NOW-timedelta(days=1))
    called = []
    def fetch(mid):
        called.append(mid)
        return RESULT
    assert log.settle_open(fetch, now=NOW, max_calls=15) == 1
    assert called == [99]


def test_fresh_due_arrivals_cannot_starve_an_older_retry(tmp_path):
    log = EsportsShadowLog(tmp_path/'esports.db')
    overdue(log, 99, checked=NOW-timedelta(days=1))
    for i in range(1, 16):
        overdue(log, i)
    with closing(log._connect()) as con:
        con.execute('UPDATE esports_shadow_predictions SET logged_at=? WHERE match_id<>99', (NOW.isoformat(),))
        con.commit()
    called = []
    def fetch(mid):
        called.append(mid)
        return RESULT if mid == 99 else None
    assert log.settle_open(fetch, now=NOW, max_calls=1) == 1
    assert called == [99]


def test_missing_results_rotate_and_fetch_errors_are_reported(tmp_path):
    log = EsportsShadowLog(tmp_path/'esports.db')
    overdue(log, 1)
    overdue(log, 2)
    called = []
    def fetch(mid):
        called.append(mid)
        raise RuntimeError('provider unavailable')
    assert log.settle_open(fetch, now=NOW, max_calls=1) == 0
    assert log.settlement_diagnostics['fetch_errors'] == 1
    assert log.settle_open(fetch, now=NOW+timedelta(minutes=30), max_calls=1) == 0
    assert called == [1, 2]
    assert log.summary()['open'] == 2


@pytest.mark.parametrize('value', [-1, True, 1.5, 501])
def test_result_budget_is_bounded(tmp_path, value):
    log = EsportsShadowLog(tmp_path/'esports.db')
    with pytest.raises(ValueError):
        log.settle_open(lambda _: RESULT, now=NOW, max_calls=value)


def test_result_only_pass_does_not_discover_or_query_prices(tmp_path):
    path = tmp_path/'esports.db'
    log = EsportsShadowLog(path)
    for mid in range(20):
        overdue(log, mid+1)
    calls = []
    def fetch(mid):
        calls.append(mid)
        return RESULT
    scanner = SimpleNamespace(api_key='test', errors={}, get_match_result=fetch)
    result = settle_due_predictions(path, scanner=scanner, now=NOW)
    assert result == dict(status='completed', settled=15, checked=15,
                         fetch_errors=0, pending=0, provider_error_count=0)
    assert len(calls) == 15
    assert log.summary()['open'] == 5


def test_result_only_pass_reports_provider_failure(tmp_path):
    path = tmp_path/'esports.db'
    overdue(EsportsShadowLog(path), 1)
    def fetch(mid):
        raise RuntimeError('failed')
    scanner = SimpleNamespace(api_key='test', errors={}, get_match_result=fetch)
    result = settle_due_predictions(path, scanner=scanner, now=NOW)
    assert result['status'] == 'partial'
    assert result['fetch_errors'] == 1
    assert result['settled'] == 0


def test_absent_database_or_key_never_calls_provider(tmp_path):
    scanner = SimpleNamespace(api_key='', errors={})
    path = tmp_path/'absent.db'
    assert settle_due_predictions(path, scanner=scanner)['status'] == 'no_database'
    assert not path.exists()
    EsportsShadowLog(path)
    assert settle_due_predictions(path, scanner=scanner)['status'] == 'missing_api_key'


def test_native_http_failure_is_partial_not_merely_pending(tmp_path, monkeypatch):
    import scanners.esports_scanner as provider
    monkeypatch.setattr(provider, 'load_app_config', lambda *_: SimpleNamespace(pandascore_key='test'))
    monkeypatch.setattr(provider.requests, 'get', lambda *args, **kwargs: SimpleNamespace(status_code=429))
    path = tmp_path/'esports.db'
    overdue(EsportsShadowLog(path), 1)
    scanner = provider.EsportsScanner()
    report = settle_due_predictions(path, scanner=scanner, now=NOW)
    assert report['status'] == 'partial'
    assert report['provider_error_count'] == 1
    assert report['settled'] == 0
    assert EsportsShadowLog(path).summary()['open'] == 1
    monkeypatch.setattr(provider.requests, 'get', lambda *args, **kwargs: SimpleNamespace(
        status_code=200, json=lambda: {'id': 1, 'status': 'running'}))
    retried = settle_due_predictions(path, scanner=scanner, now=NOW+timedelta(minutes=30))
    assert retried['status'] == 'completed'
    assert retried['provider_error_count'] == 0
    assert retried['pending'] == 1
    assert retried['settled'] == 0


@pytest.mark.parametrize('first_result', [None, RESULT, dict(void=True, termination='cancelled', team1_id=7, team2_id=8)])
def test_network_calls_never_hold_a_database_write_lock(tmp_path, first_result):
    import sqlite3
    path = tmp_path/'esports.db'
    log = EsportsShadowLog(path)
    overdue(log, 1)
    overdue(log, 2)
    def fetch(mid):
        with closing(sqlite3.connect(path, timeout=0)) as other:
            other.execute('BEGIN IMMEDIATE')
            other.rollback()
        return first_result if mid == 1 else RESULT
    assert log.settle_open(fetch, now=NOW, max_calls=2) == (1 if first_result is None else 2)
    assert log.settlement_diagnostics['fetch_errors'] == 0
