"""Run the account check only from a due job and only for a contradictory budget."""
from types import SimpleNamespace
import json
import sqlite3

import pytest

import api_budget
from scripts import api_budget_resync, run_football_shadow_due


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setenv("BETBOY_API_BUDGET_DB", str(tmp_path / "ledger.db"))
    monkeypatch.setattr(api_budget_resync, "load_app_config",
                        lambda **_: SimpleNamespace(api_football_key="offline"))
    monkeypatch.setattr(run_football_shadow_due.shadow, "should_fire", lambda _: True)
    monkeypatch.setattr(run_football_shadow_due.shadow, "run",
                        lambda _: {"artifact": {"status": "ok", "errors": []}})
    return api_budget.get_api_budget_governor()


def _sample(governor, reported_remaining):
    call = governor.reserve(api_key="offline", endpoint="fixtures", priority="critical")
    governor.complete(call, response_headers={"x-ratelimit-requests-remaining": str(reported_remaining)},
                      http_status=200)


def test_due_worker_recovers_real_reserve_denial_once_via_status(job, monkeypatch):
    _sample(job, 2400)
    _sample(job, 7498)
    calls = []

    def get(url, **opts):
        calls.append(url)
        return SimpleNamespace(status_code=200, headers={"x-ratelimit-requests-limit": "7500",
                               "x-ratelimit-requests-remaining": "7497"}, json=lambda: {
            "get": "status", "errors": [], "response": {"subscription": {"active": True},
            "requests": {"current": 3, "limit_day": 7500}}})

    monkeypatch.setattr(api_budget.requests, "get", get)
    assert run_football_shadow_due.main() == 0
    assert calls == ["https://v3.football.api-sports.io/status"]
    state = job.snapshot(api_key="offline")
    assert state.observed_remaining == 7497
    assert state.remaining_estimate == 7496  # Locally hold the account request if not yet billed.
    assert run_football_shadow_due.main() == 0
    assert len(calls) == 1


@pytest.mark.parametrize("due,headers", [(False, (2400, 7498)), (True, (7000, 7498)),
                                         (True, (2400, 2399)), (True, ())])
def test_idle_or_healthy_worker_never_probes_provider(job, monkeypatch, due, headers):
    for remaining in headers:
        _sample(job, remaining)
    monkeypatch.setattr(run_football_shadow_due.shadow, "should_fire", lambda _: due)
    monkeypatch.setattr(api_budget.requests, "get", lambda *_a, **_k: pytest.fail("unexpected API call"))
    assert run_football_shadow_due.main() == 0


def test_status_timeout_neither_retries_nor_skips_scheduled_work(job, monkeypatch):
    _sample(job, 2400)
    _sample(job, 7498)
    calls = []

    def timeout(url, **kwargs):
        calls.append(url)
        raise api_budget.requests.Timeout()
    monkeypatch.setattr(api_budget.requests, "get", timeout)
    assert run_football_shadow_due.main() == 0
    assert run_football_shadow_due.main() == 0
    assert len(calls) == 1
    assert job.snapshot(api_key="offline").remaining_estimate == 2398


def test_protected_critical_floor_does_not_fill_journal_with_denied_probes(job, monkeypatch):
    _sample(job, 51)
    _sample(job, 7498)
    monkeypatch.setattr(api_budget.requests, "get", lambda *_a, **_k: pytest.fail("unexpected API call"))
    for _ in range(2):
        assert run_football_shadow_due.main() == 0
    with sqlite3.connect(job.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM api_budget_events").fetchone()[0] == 2


def test_manual_resync_reports_invalid_http_200_as_unconfirmed(job, monkeypatch, capsys):
    _sample(job, 2400)
    _sample(job, 7498)
    def denied(*args, **kwargs):
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {
            "errors": {"access": "denied"}, "response": []})
    monkeypatch.setattr(api_budget.requests, "get", denied)
    assert api_budget_resync.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] != "completed"
