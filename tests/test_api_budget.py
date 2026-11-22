from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import api_budget
from api_budget import (
    APIBudgetExceeded,
    APIBudgetGovernor,
    APIBudgetPriority,
)


def _governor(tmp_path) -> APIBudgetGovernor:
    return APIBudgetGovernor(
        tmp_path / "budget.db",
        daily_limit=20,
        critical_floor=1,
        recommendation_reserve=4,
        background_reserve=8,
    )


def test_priority_reserves_protect_recommendation_and_critical_calls(tmp_path):
    governor = _governor(tmp_path)
    key = "secret-test-key"

    for index in range(12):
        governor.reserve(
            api_key=key,
            endpoint=f"history-{index}",
            priority=APIBudgetPriority.BACKGROUND,
        )
    with pytest.raises(APIBudgetExceeded):
        governor.reserve(
            api_key=key,
            endpoint="history-blocked",
            priority=APIBudgetPriority.BACKGROUND,
        )

    for index in range(4):
        governor.reserve(
            api_key=key,
            endpoint=f"analysis-{index}",
            priority=APIBudgetPriority.RECOMMENDATION,
        )
    with pytest.raises(APIBudgetExceeded):
        governor.reserve(
            api_key=key,
            endpoint="analysis-blocked",
            priority=APIBudgetPriority.RECOMMENDATION,
        )

    for index in range(3):
        governor.reserve(
            api_key=key,
            endpoint=f"settlement-{index}",
            priority=APIBudgetPriority.CRITICAL,
        )
    with pytest.raises(APIBudgetExceeded):
        governor.reserve(
            api_key=key,
            endpoint="critical-floor",
            priority=APIBudgetPriority.CRITICAL,
        )


def test_provider_header_can_lower_but_not_raise_conservative_estimate(tmp_path):
    governor = _governor(tmp_path)
    key = "key"
    reservation = governor.reserve(
        api_key=key,
        endpoint="fixtures",
        priority=APIBudgetPriority.RECOMMENDATION,
    )
    governor.complete(
        reservation,
        response_headers={
            "x-ratelimit-requests-limit": "30",
            "x-ratelimit-requests-remaining": "11",
        },
        http_status=200,
    )
    assert governor.snapshot(api_key=key).remaining_estimate == 11
    assert governor.snapshot(api_key=key).daily_limit == 30

    second = governor.reserve(
        api_key=key,
        endpoint="fixtures",
        priority=APIBudgetPriority.RECOMMENDATION,
    )
    governor.complete(
        second,
        response_headers={"x-ratelimit-requests-remaining": "25"},
        http_status=200,
    )
    assert governor.snapshot(api_key=key).remaining_estimate == 10


def test_plan_upgrade_during_the_day_replaces_the_stale_estimate(tmp_path):
    """23.10.2026: the free tier (100/day) was paid up to Pro (7 500/day) at midday.

    Within one plan the estimate never rises; a higher provider limit means a
    new plan, and only the provider's own count is then truthful.
    """
    governor = _governor(tmp_path)
    key = "key"
    first = governor.reserve(api_key=key, endpoint="fixtures", priority=APIBudgetPriority.RECOMMENDATION)
    governor.complete(first, response_headers={
        "x-ratelimit-requests-limit": "10", "x-ratelimit-requests-remaining": "9"}, http_status=200)
    assert (governor.snapshot(api_key=key).daily_limit, governor.snapshot(api_key=key).remaining_estimate) == (10, 9)
    # Still the small plan: the header can only lower.
    second = governor.reserve(api_key=key, endpoint="fixtures", priority=APIBudgetPriority.CRITICAL)
    governor.complete(second, response_headers={
        "x-ratelimit-requests-limit": "10", "x-ratelimit-requests-remaining": "9"}, http_status=200)
    assert governor.snapshot(api_key=key).remaining_estimate == 8
    # Plan upgrade: the provider now reports a larger limit, the stale estimate is replaced.
    third = governor.reserve(api_key=key, endpoint="status", priority=APIBudgetPriority.CRITICAL)
    governor.complete(third, response_headers={
        "x-ratelimit-requests-limit": "20", "x-ratelimit-requests-remaining": "17"}, http_status=200)
    snapshot = governor.snapshot(api_key=key)
    assert (snapshot.daily_limit, snapshot.remaining_estimate) == (20, 17)
    # The same through the authoritative account status.
    reconciled = governor.reconcile_usage(api_key=key, used=2, daily_limit=20)
    assert reconciled.remaining_estimate == 17  # unchanged plan: still never raised above the estimate
    governor.complete(governor.reserve(api_key=key, endpoint="x", priority=APIBudgetPriority.CRITICAL),
                      response_headers={"x-ratelimit-requests-limit": "20", "x-ratelimit-requests-remaining": "5"},
                      http_status=200)
    assert governor.snapshot(api_key=key).remaining_estimate == 5
    upgraded = governor.reconcile_usage(api_key=key, used=1, daily_limit=30)
    assert (upgraded.daily_limit, upgraded.remaining_estimate) == (30, 29)


def test_quota_day_resets_without_copying_prior_usage(tmp_path):
    governor = _governor(tmp_path)
    start = datetime(2026, 8, 2, 23, 59, tzinfo=timezone.utc)
    governor.reserve(
        api_key="key",
        endpoint="today",
        priority=APIBudgetPriority.RECOMMENDATION,
        now=start,
    )
    tomorrow = governor.snapshot(
        api_key="key",
        now=start + timedelta(minutes=2),
    )
    assert tomorrow.remaining_estimate == 20


def test_account_status_reconciles_midday_usage(tmp_path):
    governor = _governor(tmp_path)
    governor.reserve(
        api_key="key",
        endpoint="first",
        priority=APIBudgetPriority.RECOMMENDATION,
    )
    snapshot = governor.reconcile_usage(
        api_key="key",
        used=13,
        daily_limit=20,
    )
    assert snapshot.remaining_estimate == 7
    assert snapshot.observed_remaining == 7


def test_concurrent_reservations_are_atomic(tmp_path):
    governor = APIBudgetGovernor(
        tmp_path / "budget.db",
        daily_limit=50,
        critical_floor=1,
        recommendation_reserve=5,
        background_reserve=10,
    )

    def reserve(index: int) -> int:
        return governor.reserve(
            api_key="shared-key",
            endpoint=f"fixture-{index}",
            priority=APIBudgetPriority.RECOMMENDATION,
        ).remaining_after

    with ThreadPoolExecutor(max_workers=8) as pool:
        remaining = list(pool.map(reserve, range(30)))
    assert len(set(remaining)) == 30
    assert governor.snapshot(api_key="shared-key").remaining_estimate == 20


def test_independent_governors_share_delete_journal_atomically(tmp_path):
    database = tmp_path / "budget.db"
    APIBudgetGovernor(
        database,
        daily_limit=50,
        critical_floor=1,
        recommendation_reserve=5,
        background_reserve=10,
    )

    def reserve(index: int) -> int:
        governor = APIBudgetGovernor(
            database,
            daily_limit=50,
            critical_floor=1,
            recommendation_reserve=5,
            background_reserve=10,
        )
        return governor.reserve(
            api_key="shared-key",
            endpoint=f"fixture-{index}",
            priority=APIBudgetPriority.RECOMMENDATION,
        ).remaining_after

    with ThreadPoolExecutor(max_workers=8) as pool:
        remaining = list(pool.map(reserve, range(30)))

    assert len(set(remaining)) == 30
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_budget_ledger_uses_concurrent_wal_journal_mode(tmp_path):
    database = tmp_path / "budget.db"

    _governor(tmp_path)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_budget_ledger_never_stores_raw_api_key(tmp_path):
    governor = _governor(tmp_path)
    secret = "this-must-not-land-in-sqlite"
    governor.reserve(
        api_key=secret,
        endpoint="fixtures",
        priority=APIBudgetPriority.RECOMMENDATION,
    )
    with sqlite3.connect(tmp_path / "budget.db") as connection:
        dump = "\n".join(connection.iterdump())
    assert secret not in dump


def test_budgeted_get_observes_provider_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("BETBOY_API_BUDGET_DB", str(tmp_path / "wrapped.db"))
    monkeypatch.setenv("BETBOY_API_DAILY_LIMIT", "100")
    monkeypatch.setenv("BETBOY_API_CRITICAL_FLOOR", "2")
    monkeypatch.setenv("BETBOY_API_RECOMMENDATION_RESERVE", "10")
    monkeypatch.setenv("BETBOY_API_BACKGROUND_RESERVE", "30")
    api_budget.reset_api_budget_governor_cache()

    class Response:
        status_code = 200
        headers = {
            "x-ratelimit-requests-limit": "100",
            "x-ratelimit-requests-remaining": "77",
        }

    monkeypatch.setattr(api_budget.requests, "get", lambda *_args, **_kwargs: Response())
    response = api_budget.api_football_get(
        "https://v3.football.api-sports.io/fixtures",
        headers={"x-apisports-key": "wrapped-key"},
        priority=APIBudgetPriority.RECOMMENDATION,
    )
    assert response.status_code == 200
    snapshot = api_budget.get_api_budget_governor().snapshot(api_key="wrapped-key")
    assert snapshot.remaining_estimate == 77


def _wrapped_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("BETBOY_API_BUDGET_DB", str(tmp_path / "wrapped.db"))
    monkeypatch.setenv("BETBOY_API_DAILY_LIMIT", "100")
    monkeypatch.setenv("BETBOY_API_CRITICAL_FLOOR", "2")
    monkeypatch.setenv("BETBOY_API_RECOMMENDATION_RESERVE", "10")
    monkeypatch.setenv("BETBOY_API_BACKGROUND_RESERVE", "30")
    api_budget.reset_api_budget_governor_cache()
    monkeypatch.setattr(api_budget.time, "sleep", lambda _seconds: None)


class _OkResponse:
    status_code = 200
    headers = {}


def test_one_timeout_is_retried_once_with_its_own_reservation(tmp_path, monkeypatch):
    """06./07.11.2026: single API-Football read timeouts failed whole nightly runs."""
    _wrapped_budget(tmp_path, monkeypatch)
    calls = []

    def flaky(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise api_budget.requests.ReadTimeout("read timed out")
        return _OkResponse()

    monkeypatch.setattr(api_budget.requests, "get", flaky)
    response = api_budget.api_football_get("https://v3.football.api-sports.io/fixtures",
                                           headers={"x-apisports-key": "retry-key"})
    assert response.status_code == 200 and len(calls) == 2
    with sqlite3.connect(tmp_path / "wrapped.db") as connection:
        assert connection.execute("SELECT COUNT(*), SUM(error = 'ReadTimeout') FROM api_budget_events").fetchone() == (2, 1)


def test_a_second_timeout_and_other_errors_are_not_retried_further(tmp_path, monkeypatch):
    _wrapped_budget(tmp_path, monkeypatch)
    calls = []

    def always_timeout(*_args, **_kwargs):
        calls.append(1)
        raise api_budget.requests.ConnectTimeout("connect timed out")

    monkeypatch.setattr(api_budget.requests, "get", always_timeout)
    with pytest.raises(api_budget.requests.Timeout):
        api_budget.api_football_get("https://v3.football.api-sports.io/fixtures",
                                    headers={"x-apisports-key": "retry-key"})
    assert len(calls) == 2

    calls.clear()

    def broken(*_args, **_kwargs):
        calls.append(1)
        raise api_budget.requests.ConnectionError("refused")

    monkeypatch.setattr(api_budget.requests, "get", broken)
    with pytest.raises(api_budget.requests.ConnectionError):
        api_budget.api_football_get("https://v3.football.api-sports.io/fixtures",
                                    headers={"x-apisports-key": "retry-key"})
    assert len(calls) == 1


_STATUS_URL = "https://v3.football.api-sports.io/status"
_AUTO_STATUS = "account rollover check"


def _sticky_account(tmp_path, monkeypatch):
    _wrapped_budget(tmp_path, monkeypatch)
    gov = api_budget.get_api_budget_governor()
    for reported in (25, 98):
        ticket = gov.reserve(api_key="key", endpoint="fixtures", priority="critical")
        gov.complete(ticket, response_headers={"x-ratelimit-requests-remaining": str(reported)},
                     http_status=200)
    return gov


def _status_response(current=15, *, code=200, errors=None, active=True):
    class Response:
        status_code = code
        headers = {}

        def json(self):
            return {"errors": [] if errors is None else errors, "response": {
                "subscription": {"active": active}, "requests": {"current": current, "limit_day": 100}}}

    return Response()


def _request_status(**kwargs):
    return api_budget.api_football_get(_STATUS_URL, headers={"x-apisports-key": "key"},
                                      priority="critical", **kwargs)


def test_status_repairs_sticky_estimate_without_refunding_uncertain_units(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    failed = gov.reserve(api_key="key", endpoint="timeout", priority="critical", cost=2)
    gov.complete(failed, error="Timeout")
    gov.reserve(api_key="key", endpoint="in flight", priority="critical", cost=3)
    def successful(*args, **kwargs):
        return _status_response()
    monkeypatch.setattr(api_budget.requests, "get", successful)
    _request_status(label=_AUTO_STATUS)
    result = gov.snapshot(api_key="key")
    # 85 authoritative; hold 2 failed + 3 in flight + the status call itself.
    assert (result.remaining_estimate, result.observed_remaining) == (79, 85)
    assert gov.reserve(api_key="key", endpoint="live-ticker:details", priority="background").remaining_after == 78


@pytest.mark.parametrize("response", [_status_response(code=429), _status_response(errors={"quota": "denied"}),
                                      _status_response(active=False), _status_response(current=-1),
                                      _status_response(current=True)])
def test_untrusted_status_does_not_repair_budget(tmp_path, monkeypatch, response):
    gov = _sticky_account(tmp_path, monkeypatch)
    monkeypatch.setattr(api_budget.requests, "get", lambda *a, **k: response)
    _request_status()
    assert gov.snapshot(api_key="key").remaining_estimate == 23


def test_overlapping_lower_response_cannot_be_overwritten_by_status(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    slow = gov.reserve(api_key="key", endpoint="fixtures", priority="critical")
    def overlap(*args, **kwargs):
        gov.complete(slow, response_headers={"x-ratelimit-requests-remaining": "3"}, http_status=429)
        return _status_response()
    monkeypatch.setattr(api_budget.requests, "get", overlap)
    _request_status()
    result = gov.snapshot(api_key="key")
    assert (result.remaining_estimate, result.observed_remaining) == (3, 3)


def test_status_cannot_undo_downgrade_in_headers_or_upgrade_on_incomplete_payload(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    response = _status_response()
    response.headers = {"x-ratelimit-requests-limit": "10", "x-ratelimit-requests-remaining": "7"}
    monkeypatch.setattr(api_budget.requests, "get", lambda *a, **k: response)
    _request_status()
    result = gov.snapshot(api_key="key")
    # Tighten remaining but don't manufacture a downgrade + future fake upgrade.
    assert (result.daily_limit, result.remaining_estimate) == (100, 7)
    response.headers = {"x-ratelimit-requests-limit": "100", "x-ratelimit-requests-remaining": "85"}
    api_budget.api_football_get("https://v3.football.api-sports.io/fixtures",
                               headers={"x-apisports-key": "key"}, priority="critical")
    assert gov.snapshot(api_key="key").remaining_estimate == 6
    response.headers = {"x-ratelimit-requests-limit": "150", "x-ratelimit-requests-remaining": "135"}
    response.json = lambda: {"response": {"requests": {"current": 15, "limit_day": 100}}}
    _request_status()
    result = gov.snapshot(api_key="key")
    assert (result.daily_limit, result.remaining_estimate) == (100, 5)


def test_status_crossing_midnight_does_not_set_next_day_usage(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    before = datetime(2026, 11, 22, 23, 59, 59, tzinfo=timezone.utc)
    after = before + timedelta(seconds=2)
    monkeypatch.setattr(api_budget, "_utc_now", lambda: before)
    def crosses(*args, **kwargs):
        monkeypatch.setattr(api_budget, "_utc_now", lambda: after)
        return _status_response(current=80)
    monkeypatch.setattr(api_budget.requests, "get", crosses)
    _request_status()
    assert gov.snapshot(api_key="key", now=after).remaining_estimate == 100


@pytest.mark.parametrize("code", [429, 500])
def test_failed_response_cannot_manufacture_a_downgrade_then_upgrade(tmp_path, monkeypatch, code):
    gov = _sticky_account(tmp_path, monkeypatch)
    for status, limit, remaining in ((code, 10, 7), (200, 100, 85)):
        ticket = gov.reserve(api_key="key", endpoint="fixtures", priority="critical")
        gov.complete(ticket, http_status=status, response_headers={
            "x-ratelimit-requests-limit": str(limit), "x-ratelimit-requests-remaining": str(remaining)})
    result = gov.snapshot(api_key="key")
    assert (result.daily_limit, result.remaining_estimate) == (100, 6)


def test_only_exact_status_url_can_replace_an_observation(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    monkeypatch.setattr(api_budget.requests, "get", lambda *a, **k: _status_response())
    api_budget.api_football_get("https://other.invalid/status", headers={"x-apisports-key": "key"},
                               priority="critical")
    result = gov.snapshot(api_key="key")
    assert (result.remaining_estimate, result.observed_remaining) == (23, 98)


def test_consistent_status_cannot_refund_successes_even_if_usage_is_zero(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    monkeypatch.setattr(api_budget.requests, "get", lambda *a, **k: _status_response(current=0))
    _request_status()
    assert gov.snapshot(api_key="key").remaining_estimate == 97


def test_concurrent_workers_can_reserve_only_one_rollover_check(tmp_path, monkeypatch):
    gov = _sticky_account(tmp_path, monkeypatch)
    def reserve(_):
        try:
            gov.reserve(api_key="key", priority="critical", endpoint=_AUTO_STATUS)
        except APIBudgetExceeded as exc:
            return exc.reason
        return "admitted"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(8)))
    assert sorted(results) == ["admitted"] + ["already_checked"] * 7


def test_rollover_call_rechecks_need_and_only_attempts_once_even_on_timeout(tmp_path, monkeypatch):
    _wrapped_budget(tmp_path, monkeypatch)
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise api_budget.requests.Timeout()
    monkeypatch.setattr(api_budget.requests, "get", timeout)
    with pytest.raises(APIBudgetExceeded) as exc:
        _request_status(label=_AUTO_STATUS)
    assert exc.value.reason == "not_needed" and not calls
    _sticky_account(tmp_path, monkeypatch)
    with pytest.raises(api_budget.requests.Timeout):
        _request_status(label=_AUTO_STATUS)
    with pytest.raises(APIBudgetExceeded) as exc:
        _request_status(label=_AUTO_STATUS)
    assert exc.value.reason == "already_checked" and calls == [1]


def test_floor_and_ticker_cap_have_distinct_machine_reasons(tmp_path):
    gov = APIBudgetGovernor(tmp_path / "budget.db")
    gov.reserve(api_key="key", endpoint="live-ticker:details", cost=500, priority="background")
    with pytest.raises(APIBudgetExceeded) as exc:
        gov.reserve(api_key="key", endpoint="live-ticker:details", priority="background")
    assert exc.value.reason == "ticker_limit"
    gov.reconcile_usage(api_key="key", used=5000, daily_limit=7500)
    with pytest.raises(APIBudgetExceeded) as exc:
        gov.reserve(api_key="key", endpoint="jobs", priority="background")
    assert exc.value.reason == "protected_reserve"
    assert APIBudgetExceeded("other").reason == "unknown"
