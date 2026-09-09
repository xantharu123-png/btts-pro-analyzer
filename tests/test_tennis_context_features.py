"""B6 mechanics use synthetic times; the dated ESPN fixture is not live evidence."""

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import json
from pathlib import Path

import pytest

from context_models.tennis import recovery_bounds, tennis_features
from context_models.contracts import ContextContractError
from context_observations import append_observation, observations_as_of
from context_sources.tennis import normalize_tennis_workload


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def test_result_observation_is_not_match_end():
    result = recovery_bounds(
        next_start=NOW + timedelta(hours=24), result_observed_at=NOW, ended_at=None,
    )
    assert result == {"minimum_hours": 24.0, "exact_hours": None}


def test_actual_end_provides_exact_and_separate_receipt_bound():
    result = recovery_bounds(
        next_start=NOW + timedelta(hours=24), result_observed_at=NOW,
        ended_at=NOW - timedelta(hours=2),
    )
    assert result == {"minimum_hours": 24.0, "exact_hours": 26.0}


@pytest.mark.parametrize("kwargs", [
    {"next_start": NOW.replace(tzinfo=None)},
    {"result_observed_at": NOW.replace(tzinfo=None)},
    {"ended_at": NOW.replace(tzinfo=None)},
    {"next_start": NOW - timedelta(microseconds=1)},
    {"ended_at": NOW + timedelta(microseconds=1)},
])
def test_invalid_recovery_chronology_is_not_repaired(kwargs):
    with pytest.raises(ValueError):
        recovery_bounds(**{
            "next_start": NOW + timedelta(hours=24), "result_observed_at": NOW,
            "ended_at": None, **kwargs,
        })


def native_row(event_id="1", player="1", opponent="9", *, hours=18, duration=120, sets=(2, 1), **changes):
    ended = NOW - timedelta(hours=hours)
    return {
        "source_schema": "tennis-shadow-native-v1", "fixture_source": "ESPN",
        "provider_event_id": event_id, "tour": "ATP", "tournament_id": "189-2026",
        "player_a_id": player, "player_b_id": opponent, "settled": 1, "termination": "normal",
        "scheduled_start_utc": (ended - timedelta(hours=3)).isoformat(),
        "actual_start_utc": (ended - timedelta(minutes=duration or 120)).isoformat(), "actual_end_utc": ended.isoformat(),
        "result_observed_at": (ended + timedelta(minutes=10)).isoformat(),
        "player_a_sets": sets[0], "player_b_sets": sets[1], "total_games": 27,
        "match_duration_minutes": duration, **changes,
    }


def event(**changes):
    return {
        "event_key": "espn:tennis:ATP:match:999", "sport": "tennis", "competition": "espn:ATP:tournament:189-2026",
        "format": "singles", "home_id": "espn:tennis:ATP:player:1", "away_id": "espn:tennis:ATP:player:2",
        "scheduled_start": (NOW + timedelta(hours=6)).isoformat(), "schedule_revision": "next-s1", "status": "scheduled",
        "tour": "ATP", "surface": "Hard", "indoor": False, **changes,
    }


def base(ev=None, *, cutoff=NOW):
    ev = ev or event()
    return {
        "version": "synthetic-base-v1", "model_hash": "b" * 64, "event_key": ev["event_key"],
        "cutoff": cutoff.isoformat(), "family": "tennis:winner", "params": {"p_a": .6},
        "markets": {"winner_a": .6, "winner_b": .4}, "history_refs": [],
        "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "synthetic-no-reference-roster"},
    }


def stored(tmp_path, rows, *, receipt=NOW - timedelta(minutes=1), cutoff=NOW, historical=False):
    db = tmp_path / "b6-observations.db"
    records = normalize_tennis_workload(tuple(rows), observed_at=receipt)
    scopes = set()
    for row in records:
        append_observation(db, row, observed_at=receipt)
        scopes.add((row["event_key"], row["schedule_revision"]))
    return tuple(item for key, schedule in sorted(scopes) for item in observations_as_of(
        db, key, cutoff=cutoff, schedule_revision=schedule, mode="historical" if historical else "prospective",
    ))


def features(tmp_path, rows, *, ev=None, **kwargs):
    ev = ev or event()
    return tennis_features(ev, stored(tmp_path, rows, **kwargs), base(ev), cutoff=NOW)


def test_five_set_vs_three_set_counts_games_minutes_and_native_refs(tmp_path):
    result = features(tmp_path, [native_row(sets=(3, 2), duration=305), native_row("2", "2", sets=(2, 1), duration=150)])
    assert result["values"]["observed_sets_1d_delta"] == 2
    assert result["values"]["observed_minutes_1d_delta"] == 155
    assert result["values"]["observed_games_1d_delta"] == 0
    assert len(result["refs"]["observed_sets_1d_delta"]) == 2
    assert result["values"]["observed_sets_complete_1d_a"] == 1
    assert result["values"]["history_complete_1d_a"] == 0
    assert "observed-only.exact-observed" in result["coverage"]["case"]


def test_duration_missing_does_not_erase_sets_or_become_zero(tmp_path):
    result = features(tmp_path, [native_row(duration=None), native_row("2", "2")])
    assert result["values"]["observed_sets_1d_delta"] == 0
    assert result["values"]["observed_minutes_1d_a"] is None
    assert result["values"]["observed_minutes_1d_delta"] is None
    assert result["states"]["observed_minutes_1d_delta"] == "missing"
    assert result["refs"]["observed_minutes_1d_a"] == []
    assert result["values"]["observed_minutes_complete_1d_a"] == 0


def test_empty_history_is_not_a_healthy_zero_load_or_complete_collection(tmp_path):
    result = features(tmp_path, [])
    assert all(value is None for value in result["values"].values())
    assert all(state == "missing" for state in result["states"].values())
    assert all(ref == [] for ref in result["refs"].values())


def test_unknown_end_is_not_replaced_by_schedule_or_result_receipt(tmp_path):
    result = features(tmp_path, [native_row(actual_end_utc=None), native_row("2", "2", actual_end_utc=None)])
    assert result["values"]["observed_sets_1d_a"] is None
    assert result["values"]["observed_recovery_minimum_hours_a"] == pytest.approx(23 + 5 / 6)
    assert result["values"]["observed_recovery_exact_hours_a"] is None
    assert result["values"]["recovery_is_exact_a"] == 0
    assert "receipt-bound-observed.missing-end-times" in result["coverage"]["case"]


def test_exact_recovery_uses_end_not_receipt_or_old_planned_start(tmp_path):
    result = features(tmp_path, [native_row()])
    assert result["values"]["observed_recovery_exact_hours_a"] == 24
    assert result["values"]["observed_recovery_minimum_hours_a"] < 24


def test_1_3_7_day_windows_are_24h_end_based_intervals_not_calendar_dates(tmp_path):
    result = features(tmp_path, [native_row("1", hours=24), native_row("2", hours=24.01),
                                  native_row("3", hours=72), native_row("4", hours=168), native_row("5", hours=168.01)])
    assert result["values"]["observed_matches_1d_a"] == 1
    assert result["values"]["observed_matches_3d_a"] == 3
    assert result["values"]["observed_matches_7d_a"] == 4


def test_timezone_counterparts_near_midnight_produce_identical_content_and_features(tmp_path):
    row = native_row(hours=13)
    counterpart = deepcopy(row)
    for key in ("actual_start_utc", "actual_end_utc", "scheduled_start_utc", "result_observed_at"):
        counterpart[key] = datetime.fromisoformat(row[key]).astimezone(timezone(timedelta(hours=13))).isoformat()
    first = normalize_tennis_workload((row,), observed_at=NOW)
    assert first == normalize_tennis_workload((counterpart,), observed_at=NOW)
    observations = stored(tmp_path, [row])
    result = tennis_features(event(), observations, base(), cutoff=NOW)
    shifted = NOW.astimezone(timezone(timedelta(hours=-11)))
    assert result == tennis_features(event(), observations, base(cutoff=shifted), cutoff=shifted)


def test_native_duplicate_pages_or_shadow_rows_do_not_double_count(tmp_path):
    row = native_row()
    selected = stored(tmp_path, [row, deepcopy(row)])
    one = tennis_features(event(), selected, base(), cutoff=NOW)
    two = tennis_features(event(), selected + selected, base(), cutoff=NOW)
    assert one == two
    assert one["values"]["observed_matches_1d_a"] == 1


def test_participant_swap_negates_all_signed_load_features(tmp_path):
    observations = stored(tmp_path, [native_row(sets=(3, 2), duration=300), native_row("2", "2", sets=(2, 0), duration=90)])
    original = tennis_features(event(), observations, base(), cutoff=NOW)
    swapped = event(home_id=event()["away_id"], away_id=event()["home_id"])
    result = tennis_features(swapped, observations, base(swapped), cutoff=NOW)
    for key, value in original["values"].items():
        if key.endswith("_delta") and value is not None:
            assert result["values"][key] == -value
            assert result["refs"][key] == original["refs"][key]


def test_wta_same_numeric_player_id_cannot_join_atp(tmp_path):
    result = features(tmp_path, [native_row(tour="WTA")])
    assert result["values"]["observed_sets_1d_a"] is None
    ev = event(event_key="espn:tennis:WTA:match:999", tour="WTA", competition="espn:WTA:tournament:189-2026",
               home_id="espn:tennis:WTA:player:1", away_id="espn:tennis:WTA:player:2")
    assert features(tmp_path, [native_row(tour="WTA")], ev=ev)["values"]["observed_sets_1d_a"] == 3


def test_no_fuzzy_name_or_missing_native_player_fallback():
    row = native_row(player_a_id=None)
    with pytest.raises(ContextContractError, match="native"):
        normalize_tennis_workload((row,), observed_at=NOW)


def test_late_correction_does_not_rewrite_past_features_or_refs(tmp_path):
    original = stored(tmp_path, [native_row(sets=(2, 0))])
    before = tennis_features(event(), original, base(), cutoff=NOW)
    new = stored(tmp_path, [native_row(sets=(3, 2))], receipt=NOW + timedelta(minutes=1), cutoff=NOW, historical=True)
    replay = tennis_features(event(), new, base(), cutoff=NOW)
    assert replay == before
    assert any(row["evidence_class"] == "retrospective" for row in new)


def test_latest_causal_revision_is_used_once(tmp_path):
    old = stored(tmp_path, [native_row(sets=(2, 0))], receipt=NOW - timedelta(minutes=2))
    new = stored(tmp_path, [native_row(sets=(3, 2))])
    result = tennis_features(event(), old + new, base(), cutoff=NOW)
    assert result["values"]["observed_sets_1d_a"] == 5
    assert set(result["refs"]["observed_sets_1d_a"]) <= {row["digest"] for row in new}


def test_equal_time_differing_revisions_are_conflicting_not_extra_matches(tmp_path):
    selected = stored(tmp_path, [native_row(sets=(2, 0)), native_row(sets=(3, 2))])
    result = tennis_features(event(), selected, base(), cutoff=NOW)
    assert result["states"]["observed_sets_1d_a"] == "conflicting"
    assert result["values"]["observed_sets_1d_a"] is None
    assert result["refs"]["observed_sets_1d_a"] == []


@pytest.mark.parametrize("change", [
    {"actual_start_utc": (NOW + timedelta(hours=1)).isoformat()},
    {"actual_end_utc": (NOW + timedelta(hours=1)).isoformat()},
    {"actual_start_utc": (NOW - timedelta(hours=17)).isoformat()},
    {"result_observed_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"scheduled_start_utc": (NOW + timedelta(hours=1)).isoformat()},
    {"actual_end_utc": "2026-09-08T12:00:00"},
    {"match_duration_minutes": 0}, {"match_duration_minutes": float("nan")},
    {"player_a_sets": True}, {"total_games": 27.5},
])
def test_inconsistent_source_chronology_and_counts_are_rejected(change):
    with pytest.raises(ContextContractError):
        normalize_tennis_workload((native_row(**change),), observed_at=NOW)


def test_future_scheduled_fixture_is_not_completed_workload(tmp_path):
    row = native_row(settled=0, scheduled_start_utc=(NOW + timedelta(days=1)).isoformat())
    assert normalize_tennis_workload((row,), observed_at=NOW) == ()


def test_walkover_creates_no_played_work_or_recovery_claim(tmp_path):
    result = features(tmp_path, [native_row(termination="walkover")])
    assert all(value is None for value in result["values"].values())


def test_retirement_keeps_observed_partial_work_but_never_diagnoses_a_player(tmp_path):
    scores = [{"a": 6, "b": 4, "completed": True}, {"a": 2, "b": 1, "completed": False}]
    row = native_row(termination="retirement", set_scores=scores, player_a_sets=1, player_b_sets=0, total_games=13)
    result = features(tmp_path, [row])
    assert result["values"]["observed_sets_1d_a"] == 1
    assert result["values"]["observed_games_1d_a"] == 13
    assert result["values"]["incomplete_matches_1d_a"] == 1
    assert result["values"]["availability_a"] is None
    assert result["values"]["return_from_absence_a"] is None
    assert result["values"]["travel_hours_a"] is None
    assert "injur" not in json.dumps(result).lower()


def test_baseline_parameters_and_input_observations_are_not_modified(tmp_path):
    observations = stored(tmp_path, [native_row()])
    ev, original_base = event(), base()
    before = deepcopy((ev, observations, original_base))
    first = tennis_features(ev, observations, original_base, cutoff=NOW)
    changed_base = {**original_base, "params": {"p_a": .2}, "markets": {"winner_a": .2, "winner_b": .8}}
    assert first == tennis_features(ev, observations, changed_base, cutoff=NOW)
    assert (ev, observations, original_base) == before


def test_unknown_availability_source_or_raw_flag_is_not_promoted(tmp_path):
    observations = stored(tmp_path, [native_row()])
    row = observations[0]
    content = {key: value for key, value in row.items() if key not in {
        "digest", "content_digest", "observed_at", "effective_at", "evidence_class", "publication_resolution",
    }}
    content.update(kind="availability", source_schema="claimed-available", payload={"status": "out", "verified": True})
    db = tmp_path / "claimed.db"
    append_observation(db, content, observed_at=NOW - timedelta(minutes=1))
    selected = observations_as_of(db, row["event_key"], cutoff=NOW, schedule_revision=row["schedule_revision"])
    result = tennis_features(event(), selected, base(), cutoff=NOW)
    assert result["states"]["availability_a"] == "missing"
    assert result["refs"]["availability_a"] == []


@pytest.mark.parametrize("status", ["cancelled", "started", "completed"])
def test_non_scheduled_target_does_not_use_load(status, tmp_path):
    result = features(tmp_path, [native_row()], ev=event(status=status))
    assert all(value is None for value in result["values"].values())
    assert all(state == "not_applicable" for state in result["states"].values())


def test_decision_at_or_after_next_start_cannot_be_backdated(tmp_path):
    ev = event(scheduled_start=NOW.isoformat())
    with pytest.raises(ContextContractError, match="precede"):
        features(tmp_path, [native_row()], ev=ev)


def test_dated_real_espn_samples_preserve_known_facts_without_fabricated_times():
    path = Path(__file__).resolve().parent / "fixtures/tennis_context_espn_20260907.json"
    probe = json.loads(path.read_text(encoding="utf-8"))
    received = datetime.fromisoformat(probe["received_at"])
    rows = tuple({"source_schema": "espn-scoreboard-v1", "tour": probe["tour"],
                  "tournament_id": sample["event_id"], "competition": sample} for sample in probe["examples"])
    records = normalize_tennis_workload(rows, observed_at=received)
    assert len(records) == 4
    assert {record["payload"]["games"] for record in records} == {22, 17}
    assert {record["payload"]["sets"] for record in records} == {2}
    assert all(record["complete"] is False for record in records)
    assert all(record["payload"]["minutes"] is None for record in records)
    assert all(record["payload"]["actual_start"] is None and record["payload"]["actual_end"] is None for record in records)
    assert all(record["payload"]["result_observed_at"].startswith("2026-09-07") for record in records)
    assert all(record["payload"]["scheduled_start"].startswith("2026-08-24") for record in records)
    assert all(record["format"] == "singles" for record in records)  # Not the misleading best-of-5 field.


def espn_row():
    return {"source_schema": "espn-scoreboard-v1", "tour": "ATP", "tournament_id": "189-2026",
            "competition": {"id": "123", "date": (NOW - timedelta(days=1)).isoformat(),
                            "status": {"type": {"state": "post", "completed": True, "name": "STATUS_FINAL"}},
                            "competitors": [{"id": "1", "linescores": [{"value": 6, "winner": True}]},
                                            {"id": "2", "linescores": [{"value": 4, "winner": False}]}]}}


def test_missing_set_completion_flags_do_not_fabricate_zero_completed_sets():
    row = espn_row()
    for competitor in row["competition"]["competitors"]:
        competitor["linescores"][0].pop("winner")
    normalized = normalize_tennis_workload((row,), observed_at=NOW)
    assert all(item["payload"]["sets"] is None for item in normalized)
    assert all(item["payload"]["games"] == 10 for item in normalized)


def test_conflicting_same_event_schedule_revisions_do_not_count_twice(tmp_path):
    first = native_row()
    second = native_row(scheduled_start_utc=(NOW - timedelta(hours=22)).isoformat())
    rows = stored(tmp_path, [first, second])
    result = tennis_features(event(), rows, base(), cutoff=NOW)
    assert result["states"]["observed_sets_1d_a"] == "conflicting"
    assert result["values"]["observed_sets_1d_a"] is None


@pytest.mark.parametrize("mutation", [
    {"source_revision": "caller-changed-source"},
    {"event_key": "espn:tennis:ATP:match:not-native"},
    {"complete": True},
])
def test_normalized_source_binding_cannot_be_relabelled_as_complete_or_native(mutation, tmp_path):
    records = normalize_tennis_workload((native_row(),), observed_at=NOW - timedelta(minutes=1))
    db = tmp_path / "modified.db"
    row = {**records[0], **mutation}
    append_observation(db, row, observed_at=NOW - timedelta(minutes=1))
    observations = observations_as_of(db, row["event_key"], cutoff=NOW, schedule_revision=row["schedule_revision"])
    with pytest.raises(ContextContractError):
        tennis_features(event(), observations, base(), cutoff=NOW)


def test_espn_normalization_ignores_quote_fields_instead_of_using_them():
    original = espn_row()
    priced = deepcopy(original)
    priced["competition"]["odds"] = [{"bookmaker": "example", "price": 3.5}]
    assert normalize_tennis_workload((original,), observed_at=NOW) == normalize_tennis_workload((priced,), observed_at=NOW)


def test_no_actual_date_startdate_enddate_or_periods_inferred_from_raw_espn_keys():
    row = espn_row()
    row["competition"].update(startDate=(NOW - timedelta(hours=5)).isoformat(), endDate=NOW.isoformat(),
                              format={"regulation": {"periods": 5}}, duration=999)
    result = normalize_tennis_workload((row,), observed_at=NOW)[0]["payload"]
    assert result["actual_start"] is result["actual_end"] is result["minutes"] is None
    assert result["sets"] == 1  # Actual supplied set line, never periods=5.


def test_native_workload_ingestion_seam_does_not_promote_legacy_name_only_rows():
    from tennis.workload import native_workload_records
    row = native_row()
    assert native_workload_records((row,), observed_at=NOW) == normalize_tennis_workload((row,), observed_at=NOW)
    row.pop("player_a_id")
    with pytest.raises(ContextContractError):
        native_workload_records((row,), observed_at=NOW)


def test_duration_longer_than_actual_match_interval_is_a_source_conflict():
    row = native_row(match_duration_minutes=181)
    with pytest.raises(ContextContractError, match="duration"):
        normalize_tennis_workload((row,), observed_at=NOW)


def test_unknown_duration_and_unknown_sets_have_independent_time_coverage(tmp_path):
    result = features(tmp_path, [native_row(duration=None, player_a_sets=None)])
    assert result["values"]["observed_sets_1d_a"] is None
    assert result["values"]["observed_games_1d_a"] == 27
    assert result["coverage"]["case"].endswith("known-end-times")


def test_a_newer_walkover_correction_removes_old_claimed_played_load(tmp_path):
    old = stored(tmp_path, [native_row()], receipt=NOW - timedelta(minutes=2))
    new = stored(tmp_path, [native_row(termination="walkover")])
    result = tennis_features(event(), old + new, base(), cutoff=NOW)
    assert result["values"]["observed_sets_1d_a"] is None
    assert result["refs"]["observed_sets_1d_a"] == []


def test_partial_games_do_not_erase_an_observed_completed_set():
    row = espn_row()
    row["competition"]["competitors"][1].pop("linescores")
    records = normalize_tennis_workload((row,), observed_at=NOW)
    assert all(record["payload"]["sets"] == 1 for record in records)
    assert all(record["payload"]["games"] is None for record in records)


def test_feature_cutoff_requires_an_actual_aware_datetime():
    with pytest.raises(ContextContractError):
        tennis_features(event(), (), base(), cutoff=NOW.isoformat())


def test_existing_espn_page_and_native_shadow_ingestion_share_one_native_fact(tmp_path):
    source = espn_row()
    shadow = native_row("123", "1", "2", actual_start_utc=None, actual_end_utc=None,
                        scheduled_start_utc=source["competition"]["date"], result_observed_at=NOW.isoformat(),
                        player_a_sets=1, player_b_sets=0, total_games=10, match_duration_minutes=None,
                        set_scores=[{"a": 6, "b": 4, "completed": True}])
    assert normalize_tennis_workload((source,), observed_at=NOW) == normalize_tennis_workload((shadow,), observed_at=NOW)
    selected = stored(tmp_path, [source, shadow], receipt=NOW)
    assert len(selected) == 2  # Two participants, not two versions of each match.
    result = tennis_features(event(), selected + selected, base(), cutoff=NOW)
    assert len(result["refs"]["observed_recovery_minimum_hours_a"]) == 1


def test_future_retrospective_receipts_are_audit_only_not_feature_references(tmp_path):
    rows = stored(tmp_path, [native_row()], receipt=NOW + timedelta(days=1), cutoff=NOW, historical=True)
    assert rows and all(row["evidence_class"] == "retrospective" for row in rows)
    result = tennis_features(event(), rows, base(), cutoff=NOW)
    assert all(value is None for value in result["values"].values())
    assert all(refs == [] for refs in result["refs"].values())
