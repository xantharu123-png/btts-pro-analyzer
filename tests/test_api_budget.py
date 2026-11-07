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
