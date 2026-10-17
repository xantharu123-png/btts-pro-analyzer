"""Explicit non-FT results never become regulation-goal training observations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import challenge_engine as engine


NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def result(number=1, status="FT", *, source=None):
    row = {
        "fixture": {"id": number, "date": (NOW - timedelta(days=1)).isoformat()},
        "league": {"id": 39, "season": 2026},
        "teams": {"home": {"id": number * 2}, "away": {"id": number * 2 + 1}},
        "goals": {"home": 2, "away": 1},
        "score": {"fulltime": {"home": 1, "away": 1}},
    }
    if status is not None:
        row["fixture"]["status"] = {"short": status}
    if source is not None:
        row["challenge_source"] = source
    return row


@pytest.mark.parametrize("status", ["AET", "PEN", "1H", "HT", "2H", "LIVE", "NS", "ABD"])
def test_explicit_non_ft_score_is_not_a_completed_regulation_result(status):
    row = result(status=status)
    before = deepcopy(row)
    assert engine._fixture_score(row) is None
    assert engine._is_completed_before(row, NOW) is False
    assert row == before


@pytest.mark.parametrize("status,source", [("FT", None), (None, None),
    (None, "football-data-results-only")])
def test_ft_and_statusless_frozen_inputs_keep_the_existing_goal_contract(status, source):
    row = result(status=status, source=source)
    assert engine._fixture_score(row) == (2, 1)
    assert engine._is_completed_before(row, NOW) is True
    assert engine._is_completed_before(row, NOW - timedelta(days=1)) is False


def test_public_history_provider_keeps_strict_ft_csv_boundary(monkeypatch):
    import challenge_15k

    rows = [result(1), result(2, None, source="football-data-results-only"),
        result(3, None), result(4, "AET"), result(5, "PEN"), result(6, "LIVE")]
    before = deepcopy(rows)
    # Only transport/cache acquisition is replaced. The public provider's
    # identity/status/date sanitation and returned rows remain the real code.
    monkeypatch.setattr(challenge_15k, "fetch_stat_history", lambda *a, **kw: rows)
    provider = challenge_15k.ChallengeDataProvider("unused", None)
    monkeypatch.setattr(provider, "recent_ft_results", lambda *a, **kw: [])
    upcoming = result(99, "NS")
    upcoming["fixture"]["date"] = (NOW + timedelta(days=1)).isoformat()
    upcoming["goals"] = {"home": None, "away": None}
    actual = provider.completed_history(39, 2026, [upcoming])
    assert {row["fixture"]["id"] for row in actual} == {1, 2}
    assert rows == before
