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
