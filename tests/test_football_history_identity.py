"""CSV result identities must survive the native-history boundary."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from challenge_15k import _bounded_completed_history
from football_data_history import merge_api_tail, parse_history_csv


NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def csv_history():
    upcoming = [{"teams": {"home": {"id": 42, "name": "Arsenal"},
                           "away": {"id": 49, "name": "Chelsea"}}}]
    return parse_history_csv(
        b"Date,HomeTeam,AwayTeam,FTHG,FTAG\n"
        b"01/08/2025,Arsenal,Tottenham,2,1\n"
        b"02/08/2025,Newcastle,Chelsea,1,2\n"
        b"03/08/2025,Newcastle,Tottenham,1,1\n", 39, 2025, upcoming)


def test_csv_opponents_outside_refresh_batch_keep_their_history():
    rows = csv_history()
    before = deepcopy(rows)
    actual = _bounded_completed_history(rows, before=NOW, league_id=39)
    assert actual == rows and rows == before
    assert actual[0]["teams"]["home"]["id"] == 42
    assert actual[0]["teams"]["away"]["id"] < 0


def test_native_tail_with_csv_opponent_identity_is_retained():
    rows = csv_history()
    tail = {"fixture": {"id": 123, "date": "2026-09-19T12:00:00+00:00", "status": {"short": "FT"}},
            "league": {"id": 39, "season": 2026},
            "teams": {"home": {"id": 34, "name": "Newcastle"},
                      "away": {"id": 47, "name": "Tottenham"}},
            "goals": {"home": 1, "away": 0}}
    merged = merge_api_tail(rows, [tail], now=NOW)
    assert merged[-1]["teams"]["home"]["id"] < 0
    assert _bounded_completed_history(merged, before=NOW, league_id=39) == merged
    assert tail["teams"]["home"]["id"] == 34


@pytest.mark.parametrize("change", ["native", "unknown_source", "wrong_name", "wrong_id", "zero", "bool", "string", "live", "future", "foreign_league"])
def test_invalid_or_unbound_synthetic_team_never_enters_history(change):
    row = deepcopy(csv_history()[0])
    if change == "native":
        row.pop("challenge_source")
        row["fixture"]["status"] = {"short": "FT"}
    elif change == "unknown_source": row["challenge_source"] = "other"
    elif change == "wrong_name": row["teams"]["away"]["name"] = "Different Club"
    elif change == "wrong_id": row["teams"]["away"]["id"] -= 1
    elif change == "zero": row["teams"]["away"]["id"] = 0
    elif change == "bool": row["teams"]["away"]["id"] = True
    elif change == "string": row["teams"]["away"]["id"] = str(row["teams"]["away"]["id"])
    elif change == "live": row["fixture"]["status"] = {"short": "1H"}
    elif change == "future": row["fixture"]["date"] = "2026-09-21T12:00:00+00:00"
    else: row["league"]["id"] = 40
    assert not _bounded_completed_history([row], before=NOW, league_id=39)
