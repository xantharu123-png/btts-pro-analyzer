"""Native whole-revision and time attacks through real temporary B1 SQLite."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_models.esports import esports_features, esports_context_result
from test_esports_context import NOW, case, effect, ingest, lineup_data, native_event, source


def revise(case, tmp_path, extra):
    observations = ingest(tmp_path / "revised.sqlite", case["event"], [*case["records"], *extra])
    features = esports_features(case["event"], observations, case["base"], cutoff=NOW)
    return observations, features


def series_record(identity, *, team=7, end=None, receipt=None, winner=True):
    ev = native_event(identity, team, 100, status="completed", start=NOW - timedelta(days=14))
    data = {"actual_start": None, "actual_end": None if end is None else end.isoformat(),
            "winner_id": ev["home_id"] if winner else None, "score_a": 2 if winner else None, "score_b": 0 if winner else None}
    return source("series", ev, data), receipt or NOW - timedelta(minutes=1)


def test_whole_current_lineup_removal_does_not_reuse_old_player(case, tmp_path):
    raw = deepcopy(case["records"][-1][0])
    team = raw["data"]["teams"][case["event"]["home_id"]]
    team["players"] = []
    team["complete"] = False
    observations, fv = revise(case, tmp_path, [(raw, NOW - timedelta(minutes=1))])
    key = "participation_delta/1/2026/pandascore:esports:player:701"
    assert fv["values"][key] is None and fv["refs"][key] == []
    artifact = effect({**case, "features": fv})
    envelope = {"kind": "context-effect-v1", "payload": artifact}
    result = esports_context_result(case["base"], fv, envelope, event=case["event"], effect_hash=digest(envelope))
    assert result["role"] == "not_applied" and result["used_params"] == case["base"]["params"]


def test_simultaneous_whole_roster_content_changes_cannot_be_stitched(case, tmp_path):
    one = deepcopy(case["records"][-1][0])
    two = deepcopy(one)
    two["data"]["teams"][case["event"]["home_id"]]["players"][0]["participated"] = True
    _, fv = revise(case, tmp_path, [(one, NOW - timedelta(minutes=1)), (two, NOW - timedelta(minutes=1))])
    key = "participation_delta/1/2026/pandascore:esports:player:701"
    assert fv["states"][key] == "conflicting"
    assert fv["values"][key] is None and fv["refs"][key] == []


def test_historical_observed_lineup_withdrawal_never_restores_old_exposure(case, tmp_path):
    raw = deepcopy(case["records"][1][0])
    for team in raw["data"]["teams"].values():
        team.update(complete=False, players=[])
    _, fv = revise(case, tmp_path, [(raw, NOW - timedelta(minutes=1))])
    assert fv["values"]["participation_complete"] == 0
    assert fv["values"]["participation_delta/1/2026/pandascore:esports:player:701"] is None


def test_participant_correction_survives_b1_selection_and_blocks_former_team_load(case, tmp_path):
    old = deepcopy(case["records"][0][0])
    changed = deepcopy(old)
    changed["event"]["home_id"] = "pandascore:esports:team:999"
    changed["data"].update(winner_id=None, score_a=None, score_b=None, actual_start=None, actual_end=None)
    observations, fv = revise(case, tmp_path, [(changed, NOW - timedelta(minutes=1))])
    retained = [r for r in observations if r["event_key"] == old["event"]["event_key"] and r["payload"]["kind"] == "series"]
    assert len(retained) == 2
    assert len({r["subject_id"] for r in retained}) == 2
    assert fv["states"]["observed_series_count_7d_home"] == "conflicting"
    assert fv["refs"]["observed_series_count_7d_home"] == []


@pytest.mark.parametrize("offset, complete", [(-1, 1), (0, 0), (1, 0)])
def test_unknown_end_receipt_is_only_strict_window_exclusion_bound(case, tmp_path, offset, complete):
    receipt = NOW - timedelta(days=1) + timedelta(microseconds=offset)
    _, fv = revise(case, tmp_path, [series_record(8001, receipt=receipt)])
    assert fv["values"]["observed_series_count_1d_complete_home"] == complete
    assert fv["values"]["observed_series_count_1d_home"] == (0 if complete else None)
    assert fv["values"]["observed_series_count_3d_home"] is None
    assert fv["values"]["observed_recovery_exact_hours_home"] is None
    assert fv["values"]["observed_recovery_minimum_hours_home"] == pytest.approx(30 - offset / 3_600_000_000)


@pytest.mark.parametrize("offset, exact", [(-1, True), (0, False), (1, False)])
def test_known_latest_end_excludes_unknown_only_strictly_after_its_receipt(case, tmp_path, offset, exact):
    latest = NOW - timedelta(hours=3)
    _, fv = revise(case, tmp_path, [series_record(8002, end=latest, receipt=latest + timedelta(minutes=1)),
                                  series_record(8003, receipt=latest + timedelta(microseconds=offset))])
    assert (fv["values"]["observed_recovery_exact_hours_home"] is not None) is exact
    if exact:
        assert fv["values"]["observed_recovery_exact_hours_home"] == 9
        assert "partial-exact-end-times" in fv["coverage"]["case"]
    assert fv["values"]["history_complete_home"] == 0


def test_series_score_and_best_of_do_not_create_map_records(case):
    fv = case["features"]
    assert fv["values"]["observed_series_count_7d_home"] == 2
    assert fv["values"]["observed_map_count_7d_home"] is None
    assert fv["values"]["observed_map_count_7d_complete_home"] is None


def test_individual_map_identity_dedup_and_parent_conflict(case, tmp_path):
    ev = native_event(8004, 7, 100, status="completed", start=NOW - timedelta(hours=5))
    raw = source("map", ev, {"map_id": "pandascore:esports:map:81", "winner_id": ev["home_id"],
                            "actual_start": None, "actual_end": (NOW - timedelta(hours=4)).isoformat()})
    duplicate = deepcopy(raw)
    _, once = revise(case, tmp_path / "same", [(raw, NOW - timedelta(hours=3)), (duplicate, NOW - timedelta(hours=3))])
    assert once["values"]["observed_map_count_1d_home"] == 1
    duplicate["event"]["event_key"] = "pandascore:esports:8005"
    _, conflict = revise(case, tmp_path / "other", [(raw, NOW - timedelta(hours=3)), (duplicate, NOW - timedelta(hours=3))])
    assert conflict["states"]["observed_map_count_1d_home"] == "conflicting"


def test_future_map_receipt_does_not_change_current_features(case, tmp_path):
    ev = native_event(8006, 7, 100, status="completed")
    raw = source("map", ev, {"map_id": "pandascore:esports:map:82", "winner_id": ev["home_id"],
                            "actual_start": None, "actual_end": (NOW + timedelta(minutes=1)).isoformat()})
    _, fv = revise(case, tmp_path, [(raw, NOW + timedelta(minutes=2))])
    assert fv == case["features"]


def test_partial_actual_series_result_is_not_full_observed_window(case, tmp_path):
    _, fv = revise(case, tmp_path, [series_record(8007, end=NOW - timedelta(hours=3), winner=False)])
    assert fv["values"]["observed_series_count_1d_home"] is None
    assert fv["values"]["observed_series_count_1d_complete_home"] == 0


@pytest.mark.parametrize("bad", [None, [], {}, True, "same-name"])
def test_invalid_native_winner_types_are_closed_errors(case, bad):
    from context_sources.esports import normalize_esports_context
    raw, receipt = series_record(8008)
    raw["data"]["winner_id"] = bad
    with pytest.raises(ContextContractError):
        normalize_esports_context(case["event"], (raw,), observed_at=receipt)


@pytest.mark.parametrize("mutate", [
    lambda raw: raw["scope"].update(season_id=None),
    lambda raw: raw["scope"].update(title_id=True),
    lambda raw: raw["scope"].update(competition_id=10),
    lambda raw: raw["scope"].update(title="missing-game"),
    lambda raw: raw["scope"]["rules"].update(best_of=5),
    lambda raw: raw["scope"]["rules"].update(forfeit=True),
    lambda raw: raw["scope"]["rules"].update(starting_maps_a=1),
    lambda raw: raw["data"].update(status="team_roster"),
    lambda raw: raw["data"].update(odds=1.5),
    lambda raw: raw.update(valid_from="2020-01-01T00:00:00Z"),
])
def test_source_native_scope_types_rules_and_no_backdating(case, mutate):
    from context_sources.esports import normalize_esports_context
    raw = deepcopy(case["records"][-1][0])
    mutate(raw)
    with pytest.raises(ContextContractError):
        normalize_esports_context(case["event"], (raw,), observed_at=NOW)


def test_same_native_player_cannot_join_both_teams(case):
    from context_sources.esports import normalize_esports_context
    raw = deepcopy(case["records"][-1][0])
    raw["data"]["teams"][case["event"]["away_id"]]["players"][0]["player_id"] = "pandascore:esports:player:701"
    with pytest.raises(ContextContractError):
        normalize_esports_context(case["event"], (raw,), observed_at=NOW)


def test_current_candidate_lineup_is_not_confirmed_or_half_probability(case, tmp_path):
    raw = deepcopy(case["records"][-1][0])
    raw["data"]["status"] = "candidate"
    raw["data"]["teams"][case["event"]["home_id"]]["players"][0]["participated"] = None
    _, fv = revise(case, tmp_path, [(raw, NOW - timedelta(minutes=1))])
    assert "lineup-candidate.partial" in fv["coverage"]["case"]
    assert fv["values"]["participation_delta/1/2026/pandascore:esports:player:701"] is None


def test_persistently_absent_player_is_not_subtracted_again(case, tmp_path):
    records = deepcopy(case["records"])
    for raw, receipt in records:
        if raw["kind"] == "observed_lineup" and "pandascore:esports:team:7" in raw["data"]["teams"]:
            raw["data"]["teams"]["pandascore:esports:team:7"]["players"][0]["participated"] = False
    observations = ingest(tmp_path / "persistent.sqlite", case["event"], records)
    fv = esports_features(case["event"], observations, case["base"], cutoff=NOW)
    assert fv["values"]["participation_current/1/2026/pandascore:esports:player:701"] == 0
    assert fv["values"]["participation_reference/1/2026/pandascore:esports:player:701"] == 0
    assert fv["values"]["participation_delta/1/2026/pandascore:esports:player:701"] == 0


def test_native_projection_rejects_backdated_b1_content_even_with_valid_sqlite_hashes(case, tmp_path):
    from context_sources.esports import normalize_esports_context
    from context_observations import append_observation, observations_as_of
    path = tmp_path / "backdated.sqlite"
    row = normalize_esports_context(case["event"], (case["records"][-1][0],), observed_at=NOW)[0]
    row["valid_from"] = canonical_timestamp(NOW - timedelta(days=1))
    append_observation(path, row, observed_at=NOW)
    selected = observations_as_of(path, case["event"]["event_key"], cutoff=NOW, schedule_revision=case["event"]["schedule_revision"])
    with pytest.raises(ContextContractError):
        esports_features(case["event"], selected, case["base"], cutoff=NOW)


def test_late_retrospective_receipt_is_not_numeric_source_evidence(case, tmp_path):
    from context_sources.esports import normalize_esports_context
    from context_observations import append_observation, observations_as_of
    path = tmp_path / "late.sqlite"
    raw, _ = series_record(8010, end=NOW - timedelta(hours=1))
    later = NOW + timedelta(days=1)
    for row in normalize_esports_context(case["event"], (raw,), observed_at=later):
        append_observation(path, row, observed_at=later)
    rows = observations_as_of(path, raw["event"]["event_key"], cutoff=NOW, schedule_revision=raw["event"]["schedule_revision"], mode="historical")
    assert rows[0]["evidence_class"] == "retrospective"
    fv = esports_features(case["event"], (*case["observations"], *rows), case["base"], cutoff=NOW)
    assert fv == case["features"]


def test_new_lineup_native_participants_invalidate_old_other_kind_series_values(case, tmp_path):
    raw = deepcopy(case["records"][39][0])
    assert raw["kind"] == "observed_lineup"
    old_team = raw["event"]["home_id"]
    raw["event"]["home_id"] = "pandascore:esports:team:999"
    raw["data"]["teams"][raw["event"]["home_id"]] = raw["data"]["teams"].pop(old_team)
    _, fv = revise(case, tmp_path, [(raw, NOW - timedelta(minutes=1))])
    assert fv["states"]["observed_series_count_7d_home"] == "conflicting"
    assert fv["values"]["observed_series_count_7d_home"] is None


def test_actual_target_cancellation_invalidates_stale_scheduled_lineup(case, tmp_path):
    event = {**case["event"], "status": "cancelled"}
    cancellation = source("series", event, {"actual_start": None, "actual_end": None, "winner_id": None, "score_a": None, "score_b": None})
    _, fv = revise(case, tmp_path, [(cancellation, NOW - timedelta(minutes=1))])
    assert fv["states"]["participation_complete"] == "not_applicable"
    assert all(value is None for value in fv["values"].values())


def test_normal_parent_series_completion_keeps_a_previously_completed_native_map(case, tmp_path):
    started = native_event(8011, 7, 100, status="started", start=NOW - timedelta(hours=5))
    observed_map = source("map", started, {"map_id": "pandascore:esports:map:83", "winner_id": started["home_id"],
        "actual_start": (NOW - timedelta(hours=5)).isoformat(), "actual_end": (NOW - timedelta(hours=4)).isoformat()})
    completed = {**started, "status": "completed"}
    observed_series = source("series", completed, {"winner_id": completed["home_id"], "score_a": 2, "score_b": 0,
        "actual_start": (NOW - timedelta(hours=5)).isoformat(), "actual_end": (NOW - timedelta(hours=2)).isoformat()})
    _, fv = revise(case, tmp_path, [(observed_map, NOW - timedelta(hours=3)), (observed_series, NOW - timedelta(hours=1))])
    assert fv["values"]["observed_map_count_1d_home"] == 1
    assert fv["values"]["observed_map_count_1d_complete_home"] == 1
    assert fv["values"]["observed_series_count_1d_home"] == 1
