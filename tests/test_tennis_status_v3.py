"""Actual B1 SQLite revision regressions for the explicit B6 v3 adapter."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextContractError, digest, validate_base_distribution, validate_event
from context_models.tennis import tennis_features as legacy_features
from context_sources.tennis import normalize_tennis_workload
from test_context_tennis_capture import NOW, competition, persist, records
from test_tennis_context_features import base, event, native_row


def read(db, cutoff=NOW, tour="ATP"):
    from context_sources.tennis_status import tennis_observations_as_of
    return tennis_observations_as_of(db, cutoff=cutoff, tour=tour)


def features(db, cutoff=NOW, ev=None):
    from context_models.tennis_v3 import tennis_features_v3
    ev = ev or event()
    return tennis_features_v3(ev, read(db, cutoff=cutoff, tour=ev["tour"]), base(ev, cutoff=cutoff), cutoff=cutoff)


def legacy(db, *, match="101", player="1", opponent="9", clock=NOW-timedelta(hours=2)):
    rows = normalize_tennis_workload((native_row(match, player, opponent),), observed_at=clock)
    persist(db, rows, clock=clock)
    return rows


@pytest.mark.parametrize("change", [
    {"status": {"type": {"state": "in", "completed": False, "name": "STATUS_IN_PROGRESS"}}},
    {"status": {"type": {"state": "post", "completed": True, "name": "STATUS_CANCELED"}}},
    {"status": {"type": {"state": "post", "completed": True, "name": "STATUS_ABANDONED"}}},
    {"competitors": []}, {"competitors": [{"id": None}, {"id": "9"}]},
    {"date": None}, {"date": "bad-time"}, {"status": None},
])
def test_new_nonterminal_or_defective_revision_retracts_old_load_and_rest(tmp_path, change):
    db = tmp_path / "history.db"
    legacy(db)
    before = features(db)
    assert before["values"]["observed_sets_1d_a"] == 3
    corrected = records(competition(**change))
    persist(db, corrected, clock=NOW-timedelta(hours=1))
    after = features(db)
    for name in ("observed_sets_1d_a", "observed_recovery_minimum_hours_a", "observed_recovery_exact_hours_a"):
        assert after["values"][name] is None
        assert after["states"][name] == "missing"
    # The old adapter still means v2; new records do not mutate an old history.
    assert legacy_features(event(), read(db), base(), cutoff=NOW)["values"]["observed_sets_1d_a"] == 3
    old_cutoff = NOW-timedelta(hours=1, microseconds=1)
    assert features(db, cutoff=old_cutoff)["values"]["observed_sets_1d_a"] == 3


@pytest.mark.parametrize("old_state", ["in", "cancelled", "unknown"])
def test_later_terminal_status_without_own_complete_pair_never_revives_older_match(tmp_path, old_state):
    db = tmp_path / "history.db"
    legacy(db)
    raw = competition(status={"type": {"state": old_state, "completed": False, "name": old_state}})
    persist(db, records(raw), clock=NOW-timedelta(hours=1))
    later = NOW-timedelta(minutes=30)
    new = records(clock=later)
    persist(db, new[:2], clock=later)  # status and only one actual projection
    assert features(db)["values"]["observed_recovery_minimum_hours_a"] is None
    persist(db, new[2:], clock=later)
    result = features(db)
    assert result["values"]["observed_recovery_minimum_hours_a"] == 6.5
    assert result["values"]["observed_recovery_exact_hours_a"] is None
    assert result["values"]["observed_sets_1d_a"] is None  # no invented ESPN end


def test_whole_event_participant_and_schedule_revision_precedes_player_filter(tmp_path):
    db = tmp_path / "history.db"
    legacy(db)
    raw = competition(date="2026-09-08T20:00Z")
    raw["competitors"][0]["id"], raw["competitors"][1]["id"] = "3", "9"
    new = records(raw)
    persist(db, new, clock=NOW-timedelta(hours=1))
    assert len({row["schedule_revision"] for row in read(db)}) == 2
    assert features(db)["values"]["observed_recovery_minimum_hours_a"] is None
    ev = event(home_id="espn:tennis:ATP:player:3")
    assert features(db, ev=ev)["values"]["observed_recovery_minimum_hours_a"] == 7.


def test_same_time_conflicting_revisions_cannot_borrow_partial_opponents(tmp_path):
    db = tmp_path / "history.db"
    first = records()
    other_raw = competition()
    other_raw["competitors"][0]["linescores"][0]["value"] = 7
    other = records(other_raw)
    persist(db, first[:2] + other[:1] + other[2:], clock=NOW-timedelta(hours=1))
    result = features(db)
    assert result["states"]["observed_recovery_minimum_hours_a"] == "conflicting"
    assert result["values"]["observed_recovery_minimum_hours_a"] is None


def test_duplicate_genuine_response_once_and_both_pair_refs_are_bound(tmp_path):
    db = tmp_path / "history.db"
    new = records()
    all_refs = set(persist(db, new, clock=NOW-timedelta(hours=1)))
    first = features(db)
    persist(db, new, clock=NOW-timedelta(hours=1))
    assert features(db) == first
    assert set(first["refs"]["observed_recovery_minimum_hours_a"]) == all_refs
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone()[0] == 3


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_correction_at_cutoff_is_eligible_but_future_receipt_is_not(tmp_path, delta):
    db = tmp_path / "history.db"
    legacy(db)
    at = NOW+timedelta(microseconds=delta)
    new = records(competition(competitors=[]), clock=at)
    persist(db, new, clock=at)
    assert features(db)["values"]["observed_sets_1d_a"] == (3 if delta > 0 else None)


def test_unrelated_tour_namespace_does_not_retract_other_player(tmp_path):
    db = tmp_path / "history.db"
    legacy(db)
    new = records(competition(competitors=[]), tour="WTA", slug="womens-singles")
    persist(db, new, clock=NOW-timedelta(hours=1))
    assert features(db)["values"]["observed_sets_1d_a"] == 3


def test_old_and_paired_coverage_and_full_new_reference_are_distinct(tmp_path):
    db = tmp_path / "history.db"
    legacy(db)
    old = features(db)
    persist(db, records(), clock=NOW-timedelta(hours=1))
    new = features(db)
    assert old["version"] == new["version"] == "tennis-performed-load-v3"
    assert old["coverage"]["case"].startswith("legacy-only.")
    assert new["coverage"]["case"].startswith("status-paired.")
    assert new["reference_hash"] == digest({"version": "tennis-context-reference-v3",
        "base_hash": digest(validate_base_distribution(base())), "event_hash": digest(validate_event(event()))})


def test_new_bad_workload_after_paired_terminal_cannot_be_ignored_as_legacy(tmp_path):
    db = tmp_path / "history.db"
    persist(db, records(), clock=NOW-timedelta(hours=1))
    legacy(db, clock=NOW-timedelta(minutes=20))
    assert features(db)["values"]["observed_recovery_minimum_hours_a"] is None


def test_missing_reader_path_remains_missing_without_creating_database(tmp_path):
    db = tmp_path / "absent.db"
    assert read(db) == () and not db.exists()


def test_changed_persisted_status_payload_is_an_integrity_error(tmp_path):
    db = tmp_path / "history.db"
    persist(db, records(), clock=NOW-timedelta(hours=1))
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE context_contents SET payload=CAST(replace(CAST(payload AS TEXT), 'STATUS_FINAL', 'STATUS_OTHER') AS BLOB) WHERE CAST(payload AS TEXT) LIKE '%STATUS_FINAL%'")
        connection.commit()
    with pytest.raises(ContextContractError):
        read(db)


def test_unrelated_native_match_does_not_change_target_coverage(tmp_path):
    db = tmp_path / "history.db"
    legacy(db)
    before = features(db)
    raw = competition(id="808", competitors=[{"id": "77"}, {"id": "88"}], date=None)
    persist(db, records(raw), clock=NOW-timedelta(hours=1))
    assert features(db) == before


@pytest.mark.parametrize("kind", ["started", "cancelled", "participant-change", "schedule-change", "defective"])
def test_target_native_revision_cannot_leave_stale_event_context_eligible(tmp_path, kind):
    db = tmp_path / "history.db"
    legacy(db)
    raw = competition(id="999", date=event()["scheduled_start"],
        status={"type": {"state": "pre", "completed": False, "name": "STATUS_SCHEDULED"}})
    if kind == "started":
        raw["status"] = {"type": {"state": "in", "completed": False, "name": "STATUS_IN_PROGRESS"}}
    elif kind == "cancelled":
        raw["status"] = {"type": {"state": "pre", "completed": False, "name": "STATUS_CANCELLED"}}
    elif kind == "participant-change":
        raw["competitors"][0]["id"] = "3"
    elif kind == "schedule-change":
        raw["date"] = "2026-09-09T19:00Z"
    else:
        raw["competitors"] = []
    persist(db, records(raw), clock=NOW-timedelta(hours=1))
    answer = features(db)
    assert answer["values"]["observed_sets_1d_a"] is None
    assert answer["states"]["observed_sets_1d_a"] == ("not_applicable" if kind in {"started", "cancelled"} else "missing")


def test_matching_target_schedule_status_does_not_change_measured_history(tmp_path):
    db = tmp_path / "history.db"
    legacy(db)
    before = features(db)
    raw = competition(id="999", date=event()["scheduled_start"],
        status={"type": {"state": "pre", "completed": False, "name": "STATUS_SCHEDULED"}})
    target = records(raw)
    receipt = persist(db, target, clock=NOW-timedelta(hours=1))[0]
    answer = features(db)
    assert answer["values"] == before["values"]
    assert receipt in answer["refs"]["observed_sets_1d_a"]


@pytest.mark.parametrize("field,value", [
    ("valid_from", "2026-09-10T12:00:00.000000Z"),
    ("valid_until", "2026-09-09T11:30:00.000000Z"),
    ("published_at", "2026-09-08T12:00:00.000000Z"),
    ("complete", True), ("source_revision", "a"*64),
    ("schedule_revision", "another-schedule"), ("subject_id", "espn:tennis:ATP:player:1"),
])
def test_rehashed_wrong_status_envelope_is_not_valid_native_history(tmp_path, field, value):
    db = tmp_path / "changed.db"
    row = deepcopy(records()[0])
    row[field] = value
    persist(db, (row,), clock=NOW-timedelta(hours=1))
    with pytest.raises(ContextContractError):
        read(db)


def test_appending_old_status_with_a_new_clock_cannot_refresh_its_pair(tmp_path):
    db = tmp_path / "wrong-clock.db"
    persist(db, records(), clock=NOW)
    with pytest.raises(ContextContractError):
        read(db)


def test_changed_outer_index_cannot_hide_actual_status_correction(tmp_path):
    db = tmp_path / "index.db"
    persist(db, records(), clock=NOW-timedelta(hours=1))
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE context_observations SET event_key='other:football:123' WHERE kind='event_status'")
        connection.commit()
    with pytest.raises(ContextContractError):
        read(db)


def test_distinct_latest_status_pairs_with_equal_totals_remain_conflicting(tmp_path):
    db = tmp_path / "conflict.db"
    first, raw = records(), competition()
    raw["competitors"][0]["linescores"][0]["value"] = 7
    raw["competitors"][0]["linescores"][1]["value"] = 5
    persist(db, first + records(raw), clock=NOW-timedelta(hours=1))
    assert features(db)["states"]["observed_recovery_minimum_hours_a"] == "conflicting"
