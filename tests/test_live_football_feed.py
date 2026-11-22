"""Viewer-driven API-Football clock, tested without a provider or shared ledger."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from zoneinfo import ZoneInfo

import pytest

import api_budget


START = datetime(2026, 11, 22, 14, tzinfo=timezone.utc)


def at(seconds):
    return START + timedelta(seconds=seconds)


def match(number, *, phase="2H", home=0):
    return {
        "fixture": {"id": number, "status": {"short": phase, "elapsed": 50}},
        "teams": {"home": {"id": 100 + number}, "away": {"id": 300 + number}},
        "goals": {"home": home, "away": 0}, "league": {"id": 39},
        "events": [], "statistics": [],
    }


class Source:
    def __init__(self, count):
        self.ids = range(1, count + 1)
        self.calls = []

    def discover(self):
        self.calls.append("discovery")
        return [match(i) for i in self.ids]

    def details(self, ids):
        self.calls.append(tuple(ids))
        return [match(i) for i in reversed(ids)]


def feed(monotonic=lambda: 0):
    from live_football_feed import LiveFootballFeed
    return LiveFootballFeed(monotonic=monotonic)


@pytest.mark.parametrize("count,batches", [(0, 0), (1, 1), (20, 1), (21, 2), (80, 4)])
def test_viewer_ticks_share_five_minutes_of_batches_and_never_catch_up(count, batches):
    ticker, source = feed(), Source(count)
    assert not source.calls
    for sec in range(0, 300, 15):
        result = ticker.tick(source, now=at(sec))
        ticker.tick(source, now=at(sec))  # another viewer or market
        assert set(result) == set(source.ids)
        assert all(v["detailed_at"] == at(60 * (sec // 60)) for v in result.values())
    assert source.calls.count("discovery") == 1
    groups = [g for g in source.calls if isinstance(g, tuple)]
    assert len(groups) == 5 * batches
    assert all(len(g) <= 20 for g in groups)
    assert sorted(i for g in groups for i in g) == sorted(list(source.ids) * 5)
    before = len(source.calls)
    ticker.tick(source, now=at(1100))
    assert len(source.calls) - before == 1 + batches


def test_partial_batch_removes_stale_evidence_without_refreshing_absent_or_wrong_identity():
    ticker, source = feed(), Source(6)
    ticker.tick(source, now=at(0))
    wrong = match(4)
    wrong["teams"]["home"], wrong["teams"]["away"] = wrong["teams"]["away"], wrong["teams"]["home"]
    partial = match(6, home=1)
    partial.pop("events")
    source.details = lambda ids: [match(1, home=2), match(3), match(3), wrong, match(5, phase="FT"), partial, match(99)]
    result = ticker.tick(source, now=at(60))
    assert set(result) == {1, 2, 3, 4, 6}
    assert result[1]["fixture"]["goals"]["home"] == 2 and result[1]["detailed_at"] == at(60)
    for i in (2, 3, 4):
        assert result[i]["observed_at"] == at(0) and result[i]["detailed_at"] is None
    assert result[6]["fixture"]["goals"]["home"] == 1
    assert result[6]["observed_at"] == at(60) and result[6]["detailed_at"] is None


def test_provider_error_invalidates_evidence_and_backs_off_without_losing_scores():
    ticker, source = feed(), Source(21)
    ticker.tick(source, now=at(0))
    def unavailable(ids):
        source.calls.append(tuple(ids))
        raise RuntimeError("provider rate limit")
    source.details = unavailable
    last = len(source.calls)
    for sec in (60, 61, 119, 120):
        result = ticker.tick(source, now=at(sec))
        assert len(result) == 21
        assert all(v["observed_at"] == at(0) and v["detailed_at"] is None for v in result.values())
        assert len(source.calls) == last + 1
    ticker.tick(source, now=at(185))
    assert len(source.calls) == last + 2


def test_successful_empty_discovery_clears_scores_unlike_discovery_failure():
    ticker, source = feed(), Source(1)
    ticker.tick(source, now=at(0))
    source.discover = lambda: (_ for _ in ()).throw(RuntimeError("unavailable"))
    result = ticker.tick(source, now=at(300))
    assert result[1]["observed_at"] == at(0) and result[1]["detailed_at"] is None
    source.discover = lambda: []
    assert ticker.tick(source, now=at(605)) == {}


def test_first_discovery_failure_is_not_reported_as_a_verified_empty_board():
    ticker, source = feed(), Source(0)
    assert not ticker.unavailable
    source.discover = lambda: (_ for _ in ()).throw(RuntimeError("private error text"))
    assert ticker.tick(source, now=at(0)) == {} and ticker.unavailable is True
    assert ticker.tick(source, now=at(240)) == {} and ticker.unavailable is True
    source.discover = lambda: []
    assert ticker.tick(source, now=at(300)) == {} and ticker.unavailable is False


def test_fresh_detail_pass_recovers_availability_without_waiting_for_discovery():
    ticker, source = feed(), Source(1)
    ticker.tick(source, now=at(0))
    normal = source.details
    source.details = lambda ids: (_ for _ in ()).throw(RuntimeError("unavailable"))
    ticker.tick(source, now=at(60))
    assert ticker.unavailable is True
    source.details = normal
    ticker.tick(source, now=at(180))
    assert ticker.unavailable is False


def test_concurrent_tab_reads_changed_discovery_before_detail_finishes_without_duplicate_request():
    ticker, source = feed(), Source(1)
    ticker.tick(source, now=at(0))
    source.discover = lambda: [match(1, home=1)]
    entered, release = Event(), Event()
    def slow(ids):
        entered.set()
        assert release.wait(5)
        return [match(1, home=1)]
    source.details = slow
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(ticker.tick, source, now=at(300))
        try:
            assert entered.wait(3)
            result = pool.submit(ticker.tick, source, now=at(300)).result(timeout=1)
            assert result[1]["fixture"]["goals"]["home"] == 1 and result[1]["detailed_at"] is None
        finally:
            release.set()
        assert worker.result(timeout=3)[1]["detailed_at"] == at(300)


def test_disconnected_viewer_never_starts_a_followup_request():
    ticker, source = feed(), Source(80)
    def visible():
        return len(source.calls) < 2
    assert not ticker.tick(source, now=at(0), viewer_active=lambda: False) and not source.calls
    assert ticker.tick(source, now=at(0), viewer_active=visible) == {}
    assert source.calls == ["discovery", tuple(range(1, 21))]


def test_fall_back_clock_uses_real_elapsed_minutes_and_returns_utc():
    ticker, source = feed(), Source(1)
    zone = ZoneInfo("Europe/Zurich")
    before = datetime(2026, 10, 25, 2, 59, tzinfo=zone, fold=0)
    after = datetime(2026, 10, 25, 2, 0, tzinfo=zone, fold=1)
    ticker.tick(source, now=before)
    result = ticker.tick(source, now=after)
    assert source.calls == ["discovery", (1,), (1,)]
    assert result[1]["detailed_at"].utcoffset() == timedelta(0)


def test_slow_earlier_group_does_not_allow_last_group_to_repeat_inside_a_minute():
    runtime = [0]
    ticker, source = feed(lambda: runtime[0]), Source(21)
    normal = source.details
    def delayed(ids):
        result = normal(ids)
        if len(source.calls) == 2:
            runtime[0] += 18
        return result
    source.details = delayed
    result = ticker.tick(source, now=at(0))
    assert result[1]["detailed_at"] == at(0) and result[21]["detailed_at"] == at(18)
    ticker.tick(source, now=at(60))
    assert source.calls.count((21,)) == 1
    ticker.tick(source, now=at(78))
    assert source.calls.count((21,)) == 2


def test_reader_never_offers_121_second_old_or_future_detail_during_pending_request():
    ticker, source = feed(), Source(1)
    ticker.tick(source, now=at(0))
    entered, release = Event(), Event()
    def slow(ids):
        entered.set()
        assert release.wait(5)
        return [match(1)]
    source.details = slow
    with ThreadPoolExecutor(max_workers=1) as pool:
        active = pool.submit(ticker.tick, source, now=at(60))
        try:
            assert entered.wait(3)
            for seconds, expected in ((-1, None), (120, at(0)), (121, None)):
                result = ticker.tick(source, now=at(seconds))
                assert result[1]["observed_at"] == at(0) and result[1]["detailed_at"] == expected
        finally:
            release.set()
        active.result(timeout=3)


def test_ticker_daily_limit_is_atomic_and_separate_from_priority_reserve(tmp_path):
    db = tmp_path / "quota.db"
    gov = api_budget.APIBudgetGovernor(db)
    def reserve(governor, *, now=START, cost=1, key="a", endpoint="live-ticker:details"):
        return governor.reserve(api_key=key, priority="critical", endpoint=endpoint, now=now, cost=cost)
    r = reserve(gov, cost=499)
    assert r.priority == api_budget.APIBudgetPriority.BACKGROUND
    def last_permit(i):
        try:
            reserve(api_budget.APIBudgetGovernor(db))
            return True
        except api_budget.APIBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(last_permit, (1, 2))) == [False, True]
    assert reserve(gov, endpoint="regular").remaining_after == 6999
    assert reserve(gov, key="b").remaining_after == 7499
    assert reserve(gov, now=at(36000)).remaining_after == 7499  # UTC midnight
    gov.reconcile_usage(api_key="b", used=5000, daily_limit=7500, now=START)
    with pytest.raises(api_budget.APIBudgetExceeded):
        reserve(gov, key="b")


def test_ticker_timeout_is_charged_once_only(tmp_path, monkeypatch):
    gov = api_budget.APIBudgetGovernor(tmp_path / "quota.db")
    monkeypatch.setattr(api_budget, "get_api_budget_governor", lambda: gov)
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise api_budget.requests.ReadTimeout()
    monkeypatch.setattr(api_budget.requests, "get", timeout)
    monkeypatch.setattr(api_budget.time, "sleep", lambda _: None)
    with pytest.raises(api_budget.requests.ReadTimeout):
        api_budget.api_football_get("https://invalid.test/fixtures", label="live-ticker:discovery",
                                    headers={"x-apisports-key": "local"})
    assert len(calls) == 1 and gov.snapshot(api_key="local").remaining_estimate == 7499


def test_ticker_does_not_follow_unreserved_provider_redirect(tmp_path, monkeypatch):
    gov = api_budget.APIBudgetGovernor(tmp_path / "quota.db")
    monkeypatch.setattr(api_budget, "get_api_budget_governor", lambda: gov)
    requests = []
    def redirect(url, **kwargs):
        requests.append(kwargs["allow_redirects"])
        return type("Response", (), {"status_code": 302, "headers": {}})()
    monkeypatch.setattr(api_budget.requests, "get", redirect)
    api_budget.api_football_get("https://invalid.test/fixtures", label="live-ticker:details",
                                headers={"x-apisports-key": "local"}, allow_redirects=True)
    assert requests == [False]
