"""Void shadow tips on postponed, called-off or moved fixtures (owner decision 01.11.2026).

Report: docs/audits/2026-11-01-shadow-verschobene-spiele.md. Two Ukrainian tips of 31.10.2026
were taken about an hour before kick-off; the matches moved to 2.11. A void tip never settles,
so the later match cannot turn the quote for the original date into a win or a loss.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

import shadow_clv_automation as shadow
from challenge_engine import MARKET_BY_KEY
from clv_tracker import CLVTracker

MARKET = "TOTAL_UNDER_3_5"


def _fixture(fixture_id, date, status, goals=(None, None)):
    return {"fixture": {"id": fixture_id, "date": date, "status": {"short": status}},
            "goals": {"home": goals[0], "away": goals[1]}}


class _Provider:
    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.calls = []

    def fixtures_by_ids(self, ids):
        self.calls.append(list(ids))
        return [self.fixtures[fixture_id] for fixture_id in ids if fixture_id in self.fixtures]


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.db"
    tracker = CLVTracker(db_path=str(db_path))
    monkeypatch.setattr(shadow, "SHADOW_DB", db_path)
    shadow.errors.clear()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    kickoff = shadow._utc_iso(now - timedelta(hours=3))
    created = shadow._utc_iso(now - timedelta(hours=4))
    selection = MARKET_BY_KEY[MARKET].selection
    with shadow._connect() as connection:
        for fixture_id in (501, 502):
            connection.execute(
                """INSERT INTO predictions (fixture_id, home_team, away_team, market_type, prediction, odds,
                   model_version, policy_version, created_at, fixture_kickoff)
                   VALUES (?, 'Home FC', 'Away FC', ?, ?, 1.6, ?, ?, ?, ?)""",
                (fixture_id, MARKET, selection, shadow.SHADOW_MODEL_VERSION, shadow.SHADOW_POLICY_VERSION,
                 created, kickoff))
        connection.execute(
            """INSERT INTO shadow_unpriced (fixture_id, model_version, policy_version, home_team, away_team,
               market_key, selection, model_probability, reason, fixture_kickoff, created_at)
               VALUES (501, ?, ?, 'Home FC', 'Away FC', ?, ?, 0.66, 'no_bet365_market', ?, ?)""",
            (shadow.SHADOW_MODEL_VERSION, shadow.SHADOW_POLICY_VERSION, MARKET, selection, kickoff, created))
        connection.execute(
            """INSERT INTO shadow_published (candidate_id, kind, zurich_date, fixture_id, market_key, first_seen_at,
               kickoff) VALUES ('501:TOTAL_UNDER_3_5', 'main', '2026-10-31', 501, ?, ?, ?)""",
            (MARKET, created, kickoff))
        connection.commit()
    return SimpleNamespace(tracker=tracker, now=now, kickoff=kickoff)


@pytest.mark.parametrize(("status", "reason"), [
    ("PST", "status_pst"), ("CANC", "status_canc"), ("ABD", "status_abd"), ("AWD", "status_awd"),
    ("WO", "status_wo"),
])
def test_called_off_statuses_void_the_tip(status, reason):
    assert shadow._void_reason(_fixture(1, "2026-10-31T16:00:00+00:00", status), "2026-10-31T16:00:00+00:00") == reason


def test_a_kickoff_moved_by_more_than_twelve_hours_voids_the_tip():
    logged = "2026-10-31T16:00:00+00:00"
    assert shadow._void_reason(_fixture(1, "2026-11-02T11:00:00+00:00", "FT", (1, 0)), logged) == "kickoff_moved"
    assert shadow._void_reason(_fixture(1, "2026-10-29T16:00:00+00:00", "NS"), logged) == "kickoff_moved"
    assert shadow._void_reason(_fixture(1, "2026-11-01T05:00:00+01:00", "FT", (1, 0)), logged) is None  # 12 h
    assert shadow._void_reason(_fixture(1, "2026-10-31T17:30:00+01:00", "FT", (1, 0)), logged) is None
    assert shadow._void_reason(_fixture(1, None, "FT", (1, 0)), logged) is None
    assert shadow._void_reason(None, logged) is None
    assert shadow._void_reason({"fixture": {"status": "PST"}}, logged) is None


def test_void_tips_stay_out_of_settlement_and_results(ledger):
    moved = shadow._utc_iso(ledger.now + timedelta(hours=40))
    provider = _Provider({501: _fixture(501, moved, "NS"),
                          502: _fixture(502, ledger.kickoff, "FT", (2, 1))})
    assert shadow.step_void(provider, ledger.now) == 3  # priced, unpriced and published row of 501
    with shadow._connect() as connection:
        rows = connection.execute(
            "SELECT ledger, row_key, fixture_id, reason, provider_status, logged_kickoff, provider_kickoff "
            "FROM shadow_void ORDER BY ledger").fetchall()
    assert [row[0] for row in rows] == ["predictions", "published", "unpriced"]
    assert rows[1][1] == "501:TOTAL_UNDER_3_5|main|2026-10-31"
    assert {row[2:] for row in rows} == {(501, "kickoff_moved", "NS", ledger.kickoff, moved)}

    # The match is played later: the void tips still never settle.
    provider.fixtures[501] = _fixture(501, moved, "FT", (5, 0))
    assert shadow.step_settle(ledger.tracker, provider, ledger.now) == 1
    assert shadow.step_settle_unpriced(provider, ledger.now) == 0
    assert shadow.step_settle_published(provider, ledger.now) == 0
    assert shadow.errors == []
    results = shadow._result_statistics(shadow.SHADOW_MODEL_VERSION)
    assert results["settled"] == 1 and results["won"] == 1 and results["voided"] == 1
    unpriced = shadow._unpriced_statistics(shadow.SHADOW_MODEL_VERSION)
    assert unpriced["tips"] == 1 and unpriced["settled"] == 0 and unpriced["voided"] == 1
    assert shadow._counts() == (0, 0)
    calls = len(provider.calls)
    assert shadow.step_void(provider, ledger.now) == 0 and len(provider.calls) == calls  # nothing open any more


def test_an_unknown_or_unchanged_fixture_keeps_the_tip_open(ledger):
    provider = _Provider({502: _fixture(502, ledger.kickoff, "FT", (2, 1))})
    assert shadow.step_void(provider, ledger.now) == 0
    assert shadow.step_settle_unpriced(provider, ledger.now) == 0
    with sqlite3.connect(shadow.SHADOW_DB) as connection:
        assert connection.execute("SELECT COUNT(*) FROM shadow_void").fetchone()[0] == 0


def test_the_run_voids_before_it_settles_and_reports_the_count():
    source = Path(shadow.__file__).read_text(encoding="utf-8")
    assert source.index("voided = step_void(provider, now)") < source.index(
        "settled = step_settle(tracker, provider, now)")
    assert '"tips_voided": voided,' in source
    assert shadow.VOID_KICKOFF_SHIFT == timedelta(hours=12)
    assert shadow.VOID_STATUSES == {"PST", "CANC", "ABD", "AWD", "WO"}
