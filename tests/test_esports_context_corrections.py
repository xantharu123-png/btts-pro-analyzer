"""C4 review regressions: real B1 status corrections and exact derived values.

Native-shaped input is expressly synthetic; this is not live feed or D2 proof.
"""
from copy import deepcopy
from datetime import timedelta
import math

import pytest

from context_models.contracts import ContextIntegrityError, digest
from context_models.esports import apply_esports_effect, esports_context_result
from model_artifacts import canonical_bytes
from test_esports_context import NOW, case, effect, lineup_data, native_event, source
from test_esports_context_revisions import revise


def completed_then_started(team=7):
    event = native_event(8900, team, 100, status="completed", start=NOW-timedelta(hours=7))
    completed = source("series", event, {"actual_start": (NOW-timedelta(hours=7)).isoformat(),
        "actual_end": (NOW-timedelta(hours=3)).isoformat(), "winner_id": event["home_id"], "score_a": 2, "score_b": 0})
    ongoing = source("map", {**event, "status": "started"}, {
        "map_id": "pandascore:esports:map:8901", "winner_id": event["away_id"],
        "actual_start": (NOW-timedelta(hours=2, minutes=30)).isoformat(),
        "actual_end": (NOW-timedelta(hours=2)).isoformat()})
    return [(completed, NOW-timedelta(hours=2, minutes=59)), (ongoing, NOW-timedelta(hours=1))]


@pytest.mark.parametrize("team,side", [(7, "home"), (8, "away")])
@pytest.mark.parametrize("days", [1, 3, 7])
def test_new_started_parent_withdraws_old_terminal_series_for_each_window(case, tmp_path, team, side, days):
    observations, features = revise(case, tmp_path, completed_then_started(team))
    relevant = [row for row in observations if row["event_key"] == "pandascore:esports:8900"]
    assert {row["payload"]["event"]["status"] for row in relevant} == {"completed", "started"}
    root = f"observed_series_count_{days}d"
    for name in (root+"_"+side, root+"_complete_"+side):
        assert features["values"][name] is None
        assert features["states"][name] == "conflicting"
        assert features["refs"][name] == []
    # A completed map in an ongoing parent remains an actual map, not a series.
    assert features["values"]["observed_map_count_1d_"+side] == 1


@pytest.mark.parametrize("team,side", [(7, "home"), (8, "away")])
@pytest.mark.parametrize("timing", ["exact", "minimum"])
def test_started_correction_is_neither_an_exact_series_end_nor_a_terminal_upper_bound(case, tmp_path, team, side, timing):
    _, features = revise(case, tmp_path, completed_then_started(team))
    name = f"observed_recovery_{timing}_hours_{side}"
    assert features["values"][name] is None
    assert features["states"][name] == "conflicting"
    assert features["refs"][name] == []


@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_started_correction_respects_actual_microsecond_receipt_cutoff(case, tmp_path, shift):
    records = completed_then_started()
    records[-1] = records[-1][0], NOW+timedelta(microseconds=shift)
    observations, features = revise(case, tmp_path, records)
    name = "observed_series_count_1d_home"
    if shift > 0:
        assert features["values"][name] == 1
        assert features["values"]["observed_recovery_exact_hours_home"] == 9
        assert all(row["observed_at"] <= case["base"]["cutoff"] for row in observations)
    else:
        assert features["values"][name] is None
        assert features["values"]["observed_recovery_exact_hours_home"] is None


def test_later_actual_terminal_series_revision_restores_only_its_new_end(case, tmp_path):
    records = completed_then_started()
    completed = deepcopy(records[0][0])
    completed["data"]["actual_end"] = (NOW-timedelta(minutes=45)).isoformat()
    _, features = revise(case, tmp_path, [*records, (completed, NOW-timedelta(minutes=30))])
    assert features["values"]["observed_series_count_1d_home"] == 1
    assert features["values"]["observed_map_count_1d_home"] == 1
    assert features["values"]["observed_recovery_exact_hours_home"] == 6.75


@pytest.mark.parametrize("fact", ["observed_lineup", "same_map"])
def test_later_nonseries_fact_cannot_reinstate_retracted_series_end(case, tmp_path, fact):
    records = completed_then_started()
    if fact == "observed_lineup":
        event = records[0][0]["event"]
        newer = source("observed_lineup", event, lineup_data(event))
    else:
        newer = deepcopy(records[-1][0])
        newer["event"]["status"] = "completed"
    observations, features = revise(case, tmp_path, [*records, (newer, NOW-timedelta(minutes=30))])
    assert features["values"]["observed_series_count_1d_home"] is None
    assert features["values"]["observed_recovery_exact_hours_home"] is None
    assert features["values"]["observed_recovery_minimum_hours_home"] is None
    assert features["values"]["observed_map_count_1d_home"] == 1
    retained = [row for row in observations if row["event_key"] == "pandascore:esports:8900"]
    assert any(row["payload"]["event"]["status"] == "started" for row in retained)


def test_later_same_map_refresh_preserves_started_proof_until_new_terminal_series(case, tmp_path):
    records = completed_then_started()
    newer_map = deepcopy(records[-1][0])
    newer_map["event"]["status"] = "completed"
    newer_series = deepcopy(records[0][0])
    newer_series["data"]["actual_end"] = (NOW-timedelta(minutes=45)).isoformat()
    observations, features = revise(case, tmp_path, [*records, (newer_map, NOW-timedelta(minutes=30)),
        (newer_series, NOW-timedelta(minutes=20))])
    assert features["values"]["observed_series_count_1d_home"] == 1
    assert features["values"]["observed_recovery_exact_hours_home"] == 6.75
    assert features["values"]["observed_map_count_1d_home"] == 1
    assert any(row["payload"]["event"]["status"] == "started" for row in observations
               if row["event_key"] == "pandascore:esports:8900")


def test_expired_started_receipt_does_not_restore_the_withdrawn_terminal_claim(case, tmp_path):
    records = completed_then_started()
    records[-1][0]["valid_until"] = (NOW-timedelta(minutes=30)).isoformat()
    _, features = revise(case, tmp_path, records)
    assert features["values"]["observed_series_count_1d_home"] is None
    assert features["values"]["observed_recovery_exact_hours_home"] is None


def test_new_terminal_revision_cannot_end_before_its_known_completed_map(case, tmp_path):
    records = completed_then_started()
    # A new receipt alone cannot make the old 09:00 end consistent with its
    # own individually completed map ending at 10:00.
    repeated_old_end = deepcopy(records[0][0])
    _, features = revise(case, tmp_path, [*records, (repeated_old_end, NOW-timedelta(minutes=30))])
    assert features["values"]["observed_series_count_1d_home"] is None
    assert features["values"]["observed_recovery_exact_hours_home"] is None
    assert features["values"]["observed_map_count_1d_home"] == 1


def test_old_unversioned_subject_is_not_silently_rewritten_as_status_evidence(case, tmp_path):
    from context_models.esports import esports_features
    from context_observations import append_observation, observations_as_of
    from context_sources.esports import normalize_esports_context
    raw, received = completed_then_started()[0]
    normalized = normalize_esports_context(case["event"], (raw,), observed_at=received)[0]
    event = raw["event"]
    old_identity = digest({"participants": {name: event[name] for name in ("home_id", "away_id")}, "scope": raw["scope"]})
    normalized["subject_id"] = event["event_key"]+":participants:"+old_identity+":fact:series"
    path = tmp_path / "old-subject.sqlite"
    append_observation(path, normalized, observed_at=received)
    observations = observations_as_of(path, event["event_key"], cutoff=NOW, schedule_revision=event["schedule_revision"])
    from context_models.contracts import ContextContractError
    with pytest.raises(ContextContractError, match="projection/clocks"):
        esports_features(case["event"], (*case["observations"], *observations), case["base"], cutoff=NOW)


@pytest.mark.parametrize("name", ["participation_delta/1/2026/pandascore:esports:player:702",
                                  "observed_series_count_1d_delta", "observed_recovery_exact_hours_delta"])
@pytest.mark.parametrize("epsilon", [math.nextafter(0., 1.), 9e-13, -9e-13])
def test_signed_zero_must_match_exactly_for_participation_counts_and_recovery(case, name, epsilon):
    assert case["features"]["values"][name] == 0
    features = deepcopy(case["features"])
    features["values"][name] = epsilon
    artifact = effect(case, names=[name], coefficient=1e12)
    with pytest.raises(ContextIntegrityError, match="measured components"):
        apply_esports_effect(case["base"], features, artifact, event=case["event"])


@pytest.mark.parametrize("direction", [0., -math.inf])
def test_nonzero_signed_value_one_ulp_perturbation_is_not_authenticated(case, direction):
    name = "participation_delta/1/2026/pandascore:esports:player:701"
    assert case["features"]["values"][name] == -1
    features = deepcopy(case["features"])
    features["values"][name] = math.nextafter(-1., direction)
    with pytest.raises(ContextIntegrityError, match="measured components"):
        apply_esports_effect(case["base"], features, effect(case), event=case["event"])


def test_subtolerance_signed_tamper_cannot_enter_the_b3_comparison(case):
    name = "participation_delta/1/2026/pandascore:esports:player:702"
    features = deepcopy(case["features"])
    features["values"][name] = 9e-13
    envelope = {"kind": "context-effect-v1", "payload": effect(case, names=[name], coefficient=1e12)}
    with pytest.raises(ContextIntegrityError, match="measured components"):
        esports_context_result(case["base"], features, envelope, event=case["event"], effect_hash=digest(envelope))


@pytest.mark.parametrize("name", ["participation_delta/1/2026/pandascore:esports:player:702",
                                  "observed_series_count_1d_delta", "observed_recovery_exact_hours_delta"])
def test_genuine_signed_zero_retains_original_parameter_and_market_bytes(case, name):
    artifact = effect(case, names=[name], coefficient=1e12)
    actual = apply_esports_effect(case["base"], case["features"], artifact, event=case["event"])
    for key in ("params", "markets"):
        assert canonical_bytes(actual[key]) == canonical_bytes(case["base"][key])
