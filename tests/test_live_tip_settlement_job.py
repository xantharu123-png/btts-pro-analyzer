"""The existing daily job uses a single fixture budget for public and research receipts."""
import sqlite3
import sys
from datetime import datetime as RealDatetime
from types import SimpleNamespace

import pytest

import redcard_signal_log as job


@pytest.mark.parametrize("limit,public_pending,shadow_state,day,error,want_public,want_shadow", [
    (5, 20, "open", 1, 0, 4, 1),      # a full public queue cannot starve research
    (5, 20, "absent", 1, 0, 5, 0),    # no reserved slot for an absent shadow DB
    (5, 20, "settled", 1, 0, 5, 0),   # nor for an empty shadow queue
    (5, 3, "open", 1, 0, 3, 2),       # short public queue transfers unused capacity
    (5, 0, "open", 1, 0, 0, 5),
    (1, 2, "open", 1, 0, 0, 1),       # 2026-11-01 has an odd UTC ordinal
    (1, 2, "open", 2, 0, 1, 0),
    (1, 0, "open", 2, 0, 0, 1),       # empty public even on its day
    (1, 2, "absent", 1, 0, 1, 0),
    (5, 2, "absent", 2, 0, 2, 0),
    (5, 3, "open", 1, 1, 3, 0),       # stop after provider errors
    (0, 20, "open", 1, 0, 0, 0),
])
def test_daily_job_shares_cap_without_starving_either_queue(
        monkeypatch, tmp_path, limit, public_pending, shadow_state, day, error, want_public, want_shadow):
    public_checked, shadow_checked = [], []
    path = tmp_path / "signals.db"
    if shadow_state != "absent":
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE signals (status TEXT)")
            conn.execute("INSERT INTO signals VALUES (?)", (shadow_state,))
        conn.close()
    monkeypatch.setattr(job, "DB_PATH", path)

    class JobClock(RealDatetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, day, 6, 5, tzinfo=tz)

    monkeypatch.setattr(job, "datetime", JobClock)
    client = object()
    def public(api, *, max_fixtures):
        assert api is client
        count = min(public_pending, max_fixtures)
        public_checked.append(count)
        return {"fixtures_checked": count, "provider_errors": error}
    def research(api, *, max_fixtures):
        assert api is client
        shadow_checked.append(max_fixtures)
        return {"provider_errors": 0}
    monkeypatch.setitem(sys.modules, "live_tip_ledger", SimpleNamespace(settle_displayed_live_tips=public))
    monkeypatch.setattr(sys, "argv", ["redcard_signal_log.py", "--settle", "--max", str(limit)])
    monkeypatch.setattr("config_loader.load_app_config", lambda: SimpleNamespace(api_football_key="offline"))
    monkeypatch.setattr("api_football.APIFootball", lambda *a, **kw: client)
    monkeypatch.setattr(job, "settle_open_signals", research)
    assert job.main() == error
    assert sum(public_checked) == want_public
    assert sum(shadow_checked) == want_shadow
    assert sum(public_checked + shadow_checked) <= limit
    if shadow_state == "absent":
        assert not path.exists()
