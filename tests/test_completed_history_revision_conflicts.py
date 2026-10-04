"""Unresolved native fixture revisions cannot silently choose model history."""
from copy import deepcopy
from datetime import datetime, timezone
from itertools import permutations

import pytest

from challenge_15k import _bounded_completed_history
from test_football_history_identity import csv_history


NOW = datetime(2026, 10, 4, 7, tzinfo=timezone.utc)


def fixture(fixture_id=123):
    return {
        "fixture": {"id": fixture_id, "date": "2026-10-03T18:45:00+00:00", "status": {"short": "FT"}},
        "league": {"id": 5, "season": 2026},
        "teams": {"home": {"id": 1117, "name": "Greece"}, "away": {"id": 25, "name": "Germany"}},
        "goals": {"home": 2, "away": 0},
    }


@pytest.mark.parametrize("change", [
    "score", "live", "cancelled", "future", "rescheduled_ft", "roles", "foreign_league",
    "invalid_score", "typed_score", "typed_team", "missing_date", "invalid_goals",
])
def test_ambiguous_native_revisions_are_excluded_before_admission_and_without_order_bias(change):
    original, newer = fixture(), fixture()
    if change == "score": newer["goals"] = {"home": 0, "away": 2}
    elif change == "live": newer["fixture"]["status"] = {"short": "1H"}
    elif change == "cancelled": newer["fixture"]["status"] = {"short": "CANC"}
    elif change == "future":
        newer["fixture"]["date"] = "2026-10-05T18:45:00+00:00"
        newer["fixture"]["status"] = {"short": "NS"}
    elif change == "rescheduled_ft": newer["fixture"]["date"] = "2026-10-02T18:45:00+00:00"
    elif change == "roles": newer["teams"]["home"], newer["teams"]["away"] = newer["teams"]["away"], newer["teams"]["home"]
    elif change == "foreign_league": newer["league"]["id"] = 32
    elif change == "invalid_score": newer["goals"]["home"] = -1
    elif change == "typed_score": newer["goals"]["away"] = False
    elif change == "typed_team": newer["teams"]["home"]["id"] = True
    elif change == "missing_date": newer["fixture"].pop("date")
    else: newer["goals"] = None
    other = fixture(124)
    other["fixture"]["date"] = "2026-10-01T18:45:00+00:00"
    before = deepcopy([original, newer, other])
    for rows in permutations((original, newer, other)):
        assert _bounded_completed_history(list(rows), before=NOW, league_id=5) == [other]
    assert [original, newer, other] == before


def test_identical_native_revisions_are_neutral_and_equivalent_timezones_are_the_same_event():
    original, same = fixture(), fixture()
    same["fixture"]["date"] = "2026-10-03T20:45:00+02:00"
    same["fixture"]["status"]["long"] = "Match Finished"
    same["teams"]["home"]["name"] = "Greece renamed for display"
    for rows in ((original, deepcopy(original)), (original, same), (same, original)):
        selected = _bounded_completed_history(list(rows), before=NOW, league_id=5)
        assert len(selected) == 1 and selected[0]["fixture"]["id"] == 123
        assert selected[0]["goals"] == original["goals"]


def test_negative_csv_fixture_identity_and_native_api_tail_are_preserved():
    csv_rows = csv_history()
    tail = fixture(987)
    tail["league"]["id"] = 39
    rows = [*csv_rows, tail, deepcopy(tail)]
    before = deepcopy(rows)
    assert _bounded_completed_history(rows, before=NOW, league_id=39) == [*csv_rows, tail]
    assert rows == before


def test_malformed_fixture_ids_cannot_alias_valid_native_ids():
    original = fixture(1)
    variants = [fixture(True), fixture("1"), fixture(0), {"fixture": {"id": 1}, "goals": None}]
    # A structurally invalid revision with the SAME proper native ID must
    # invalidate the original; bool/string/zero IDs cannot impersonate it.
    assert _bounded_completed_history([original, *variants[:3]], before=NOW) == [original]
    assert _bounded_completed_history([original, variants[3]], before=NOW) == []


def test_conflict_for_one_native_id_never_quarantines_unrelated_native_event():
    one, changed, other = fixture(123), fixture(123), fixture(124)
    changed["goals"]["home"] = 3
    other["fixture"]["date"] = "2026-10-02T18:45:00+00:00"
    assert _bounded_completed_history([one, changed, other], before=NOW) == [other]


def test_exact_event_aliases_with_conflicting_scores_are_all_excluded_in_every_order():
    first, conflict, other = fixture(123), fixture(124), fixture(125)
    conflict["goals"] = {"home": 0, "away": 2}
    other["fixture"]["date"] = "2026-10-02T18:45:00+00:00"
    before = deepcopy([first, conflict, other])
    for rows in permutations((first, conflict, other)):
        assert _bounded_completed_history(list(rows), before=NOW) == [other]
    assert [first, conflict, other] == before


def test_identical_native_event_aliases_use_highest_id_as_stable_tiebreak():
    originals = [fixture(123), fixture(124), fixture(125)]
    before = deepcopy(originals)
    for rows in permutations(originals):
        assert _bounded_completed_history(list(rows), before=NOW) == [originals[2]]
    assert originals == before


def test_conflicting_same_native_id_cannot_be_replaced_by_an_identical_event_alias():
    original, correction, alias = fixture(123), fixture(123), fixture(124)
    correction["goals"] = {"home": 0, "away": 2}
    for rows in permutations((original, correction, alias)):
        assert _bounded_completed_history(list(rows), before=NOW) == []


@pytest.mark.parametrize("status", ["NS", "CANC", "1H", "future"])
@pytest.mark.parametrize("csv_alias", [False, True])
def test_quarantined_old_native_event_cannot_resurrect_via_native_or_csv_alias(status, csv_alias):
    original, revision, alias = fixture(123), fixture(123), fixture(124)
    revision["fixture"]["status"] = {"short": "NS" if status == "future" else status}
    if status == "future":
        revision["fixture"]["date"] = "2026-10-05T18:45:00+00:00"
    if csv_alias:
        alias["fixture"]["id"] = -124
        alias["fixture"].pop("status")
        alias["challenge_source"] = "football-data-results-only"
    before = deepcopy([original, revision, alias])
    for rows in permutations((original, revision, alias)):
        assert _bounded_completed_history(list(rows), before=NOW) == []
    assert [original, revision, alias] == before


@pytest.mark.parametrize("conflicting", [False, True])
def test_native_and_negative_csv_alias_keep_native_or_exclude_conflicting_scores(conflicting):
    csv_row = csv_history()[0]
    assert csv_row["fixture"]["id"] < 0
    native_tail = deepcopy(csv_row)
    native_tail["fixture"]["id"] = 789
    native_tail["fixture"]["status"] = {"short": "FT"}
    native_tail["challenge_source"] = "api-football-ft-tail"
    if conflicting:
        native_tail["goals"]["home"] += 1
    before = deepcopy([csv_row, native_tail])
    for rows in ((csv_row, native_tail), (native_tail, csv_row)):
        assert _bounded_completed_history(list(rows), before=NOW) == ([] if conflicting else [native_tail])
    assert [csv_row, native_tail] == before
