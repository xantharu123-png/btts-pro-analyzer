from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scanners.cricket_scanner import CricketScanner
from wettfinder_automation import _causal_completed_history


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def test_research_bridge_keeps_later_result_retraction_for_model():
    rows = [
        {"provider": "ESPN", "provider_event_id": "past", "status": status,
         "result_observed_at": (NOW - timedelta(minutes=minutes)).isoformat()}
        for status, minutes in (("completed", 20), ("cancelled", 10))
    ]
    seen = _causal_completed_history(rows, as_of=NOW)
    assert [row["status"] for row in seen] == ["completed", "cancelled"]


@pytest.mark.parametrize("state", ["Complete", "Cancelled", "Abandon", "In Progress", "Postponed"])
def test_cricket_never_relabels_explicit_nonprematch_state_as_upcoming(state):
    scanner = CricketScanner.__new__(CricketScanner)
    info = {"state": state, "matchId": 123, "startDate": 1893492000000,
            "team1": {"teamName": "Alpha"}, "team2": {"teamName": "Beta"}}
    assert scanner._parse_upcoming_match({"matchInfo": info}, source="Cricbuzz") is None


@pytest.mark.parametrize("status", ["Match cancelled", "Match abandoned", "Match postponed", "Beta won by 4 runs"])
def test_cricketdata_future_time_does_not_override_terminal_status(status):
    scanner = CricketScanner.__new__(CricketScanner)
    info = {"id": "123", "teams": ["Alpha", "Beta"], "matchStarted": False,
            "matchEnded": False, "dateTimeGMT": "2030-01-01T18:00:00", "status": status}
    assert scanner._parse_upcoming_match(info, source="CricketData") is None


def test_cricbuzz_numeric_string_timestamp_keeps_real_scheduled_fixture():
    scanner = CricketScanner.__new__(CricketScanner)
    info = {"state": "Preview", "matchId": 123, "startDate": "1893492000000",
            "matchFormat": "T20", "seriesName": "Test T20",
            "team1": {"teamId": 1, "teamName": "Alpha"},
            "team2": {"teamId": 2, "teamName": "Beta"}}
    row = scanner._parse_upcoming_match({"matchInfo": info}, source="Cricbuzz")
    assert row is not None
    assert row["status"] == "upcoming"
    assert row["start_time"] == "2030-01-01T10:00:00+00:00"
