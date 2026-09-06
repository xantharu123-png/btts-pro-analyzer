from datetime import datetime, timedelta, timezone

import pytest

from market_consensus import parse_fixture_consensus
from wettfinder_automation import _apply_reference_quotes


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def row_and_quote():
    row = {
        "key": "test", "candidate_id": "1:BTTS_YES", "fixture_id": 1,
        "market_key": "BTTS_YES", "sport": "Fußball", "source": "football_challenge",
        "minimum_odds": 1.8, "probability": .65,
        "selection": "Ja",
        "scheduled_start": (NOW + timedelta(hours=6)).isoformat(),
    }
    raw = {"response": [{"fixture": {"id": 1, "date": row["scheduled_start"]},
        "update": NOW.isoformat(), "bookmakers": [
            {"id": i, "name": f"Book{i}", "bets": [{"name": "Both Teams Score", "values": [{"value": "Yes", "odd": "2.05"}]}]}
            for i in range(1, 5)
        ]}]}
    quote = parse_fixture_consensus(raw, [row], fetched_at=NOW)[row["candidate_id"]]
    return row, {**row, "reference_quote": quote.to_dict()}


def test_still_fresh_cached_price_retains_playability_during_rotation():
    row, previous = row_and_quote()
    _, playable = _apply_reference_quotes([row], [], {}, now=NOW + timedelta(minutes=5), previous_rows=[previous])
    assert row["reference_price_status"] == "PLAYABLE"
    assert playable == [row]
    assert row["reference_quote"]["fetched_at"] == NOW.isoformat()
    assert row["probability"] == .65


@pytest.mark.parametrize("change", ["stale", "moved", "market"])
def test_old_or_mismatching_cached_price_never_releases_forecast(change):
    row, previous = row_and_quote()
    now = NOW + timedelta(minutes=5)
    if change == "stale":
        now = NOW + timedelta(hours=2)
    elif change == "moved":
        row["scheduled_start"] = (NOW + timedelta(hours=8)).isoformat()
    else:
        row["market_key"] = "BTTS_NO"
    _, playable = _apply_reference_quotes([row], [], {}, now=now, previous_rows=[previous])
    assert playable == []
    assert row["reference_price_status"] != "PLAYABLE"
    assert row["probability"] == .65
