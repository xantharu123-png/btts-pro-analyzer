"""Permanent C2 regression: explicit synthetic native revisions, never live data."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import canonical_timestamp, digest
from context_models.team_sports import team_sport_context_result
from context_observations import append_observation, observations_as_of
from test_basketball_context import (
    NOW, artifact, event, feature_packet, inputs, normalized, packet, receipt,
    rotation_team, rules, transport,
)


def recent(key, end=12, bound=11):
    raw = transport(kind="appearance")
    raw["event"]["event_key"] = f"espn:basketball:{key}"
    raw["event"]["scheduled_start"] = canonical_timestamp(NOW-timedelta(hours=end+2))
    raw["data"].update(actual_start=raw["event"]["scheduled_start"],
                       actual_end=canonical_timestamp(NOW-timedelta(hours=end)),
                       result_observed_at=canonical_timestamp(NOW-timedelta(hours=bound)))
    return raw


def conflict(instant):
    raw = recent(401899920, end=242, bound=240)
    raw["data"]["actual_start"] = raw["data"]["actual_end"] = None
    raw["data"]["result_observed_at"] = canonical_timestamp(instant)
    other = deepcopy(raw)
    other["data"]["teams"][event()["home_id"]]["players"][0]["inclusive_minutes"] = None
    return receipt(raw), receipt(other)


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("reverse", [False, True])
def test_partial_participant_revision_keeps_uncertainty_for_previous_team(side, reverse):
    base, _, records = packet()
    older, latest = recent(401899921, 30, 29), recent(401899922, 10, 9)
    before = (*records, receipt(older, NOW-timedelta(minutes=20)), receipt(latest, NOW-timedelta(minutes=20)))
    assert feature_packet(base, before)["values"][f"observed_recovery_exact_hours_{side}"] == 16.
    changed = deepcopy(latest)
    previous = changed["event"][side+"_id"]
    changed["event"][side+"_id"] = "espn:basketball:team:99"
    changed["data"]["teams"]["espn:basketball:team:99"] = changed["data"]["teams"].pop(previous)
    changed["data"]["actual_start"] = changed["data"]["actual_end"] = None
    for team in changed["data"]["teams"].values():
        team.update(complete=False, collection="partial", players=[])
    values = (*before, receipt(changed, NOW-timedelta(minutes=5)))
    fv = feature_packet(base, tuple(reversed(values)) if reverse else values)
    assert fv["values"][f"observed_recovery_exact_hours_{side}"] is None
    assert fv["values"][f"observed_inclusive_minutes_complete_3d_{side}"] != 1


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_conflict_bounds_are_independent_for_each_window_and_kept_in_provenance(days, microseconds):
    base, _, records = packet()
    pair = conflict(NOW-timedelta(days=days)+timedelta(microseconds=microseconds))
    values = (*records, receipt(recent(401899923)), *pair)
    fv = feature_packet(base, values)
    for side in ("home", "away"):
        name = f"observed_inclusive_minutes_complete_{days}d_{side}"
        if microseconds < 0:
            assert fv["values"][name] == 1
            assert {row["digest"] for row in pair} <= set(fv["refs"][name])
        else:
            assert fv["values"][name] != 1


@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_conflicting_receipt_equality_does_not_prove_latest_actual_end(microseconds):
    base, _, records = packet()
    pair = conflict(NOW-timedelta(hours=12)+timedelta(microseconds=microseconds))
    fv = feature_packet(base, (*records, receipt(recent(401899924)), *pair))
    for side in ("home", "away"):
        name = f"observed_recovery_exact_hours_{side}"
        assert fv["values"][name] == (18. if microseconds < 0 else None)
        if microseconds < 0:
            assert {row["digest"] for row in pair} <= set(fv["refs"][name])


def test_ancient_conflict_still_invalidates_its_required_roster_reference():
    base, raws, records = packet()
    changed = deepcopy(raws[1])
    changed["data"]["teams"][changed["event"]["home_id"]]["players"][0]["regulation_minutes"] = None
    fv = feature_packet(base, (*records, receipt(changed, NOW-timedelta(minutes=30))))
    assert fv["values"]["rotation_complete"] != 1


def test_ambiguous_recent_participation_cannot_enter_fitted_effect_after_real_sqlite(tmp_path):
    base, raws, _ = packet()
    older, latest = recent(401899925, 30, 29), recent(401899926, 10, 9)
    previous = latest["event"]["away_id"]
    latest["data"]["teams"].pop(previous)
    latest["event"]["away_id"] = "espn:basketball:team:9"
    latest["data"]["teams"][latest["event"]["away_id"]] = rotation_team(latest["event"]["away_id"], load=True)
    changed = deepcopy(latest)
    previous = changed["event"]["home_id"]
    changed["data"]["teams"].pop(previous)
    changed["event"]["home_id"] = "espn:basketball:team:99"
    changed["data"]["teams"][changed["event"]["home_id"]] = rotation_team(changed["event"]["home_id"], load=True)
    changed["data"]["actual_start"] = changed["data"]["actual_end"] = None
    for team in changed["data"]["teams"].values():
        team.update(complete=False, collection="partial", players=[])
    path = tmp_path/"actual-receipts.db"
    all_rows = [(raw, NOW-timedelta(minutes=30)) for raw in [*raws, older, latest]] + [(changed, NOW-timedelta(minutes=1))]
    versions = {}
    for raw, clock in all_rows:
        append_observation(path, normalized(raw, clock)[0], observed_at=clock)
        versions[raw["event"]["event_key"]] = raw["event"]["schedule_revision"]
    records = tuple(r for key, revision in versions.items() for r in observations_as_of(path, key, cutoff=NOW, schedule_revision=revision))
    fv = feature_packet(base, records)
    effect = artifact(base, fv, name="observed_recovery_exact_hours_delta", beta=.2)
    envelope = {"kind": "context-effect-v1", "payload": effect}
    result = team_sport_context_result("basketball", base, fv, envelope, event=event(), effect_hash=digest(envelope))
    assert result["role"] == "not_applied" and result["comparison_params"] is None
    assert result["used_params"] == base["params"]


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("complete", [False, True])
def test_participant_lineage_survives_actual_b1_selection_without_reviving_old_minutes(tmp_path, side, reverse, complete):
    base, raws, _ = packet()
    older, latest = recent(401899927, 30, 29), recent(401899928, 12, 11)
    changed = deepcopy(latest)
    previous = changed["event"][side+"_id"]
    changed["event"][side+"_id"] = "espn:basketball:team:99"
    changed["data"]["teams"].pop(previous)
    changed["data"]["teams"]["espn:basketball:team:99"] = rotation_team("espn:basketball:team:99", load=True)
    if not complete:
        changed["data"]["actual_start"] = changed["data"]["actual_end"] = None
        for team in changed["data"]["teams"].values():
            team.update(complete=False, collection="partial", players=[])
    versions = [(raw, NOW-timedelta(minutes=30)) for raw in [*raws, older, latest]]
    versions.append((changed, NOW-timedelta(minutes=1)))
    path = tmp_path/"participant-lineage.db"
    if reverse:
        versions.reverse()
    for raw, clock in versions:
        append_observation(path, normalized(raw, clock)[0], observed_at=clock)
    events = {raw["event"]["event_key"]: raw["event"]["schedule_revision"] for raw, _ in versions}
    selected = tuple(row for key, revision in events.items()
        for row in observations_as_of(path, key, cutoff=NOW, schedule_revision=revision))
    lineage = [row for row in selected if row["event_key"] == latest["event"]["event_key"]]
    assert len(lineage) == 2 and len({row["subject_id"] for row in lineage}) == 2
    fv = feature_packet(base, selected)
    name = f"observed_recovery_exact_hours_{side}"
    assert fv["values"][name] == (36. if complete else None)
    # A complete correction removes the old participant; its old 18-hour rest
    # may not be revived merely because its identity receipt is retained.
    assert fv["values"][f"observed_inclusive_minutes_complete_3d_{side}"] == (1. if complete else None)


@pytest.mark.parametrize("clock", [-1, 1])
def test_same_participant_corrections_still_select_latest_causal_values_once_in_b1(tmp_path, clock):
    base, raws, _ = packet()
    older = recent(401899929, 12, 11)
    changed = recent(401899929, 6, 5)
    path = tmp_path/"same-participants.db"
    versions = [(raw, NOW-timedelta(minutes=30)) for raw in [*raws, older]]
    versions.append((changed, NOW+timedelta(microseconds=clock)))
    for raw, observed in versions:
        append_observation(path, normalized(raw, observed)[0], observed_at=observed)
    events = {raw["event"]["event_key"]: raw["event"]["schedule_revision"] for raw, _ in versions}
    selected = tuple(row for key, revision in events.items()
        for row in observations_as_of(path, key, cutoff=NOW, schedule_revision=revision))
    lineage = [row for row in selected if row["event_key"] == older["event"]["event_key"]]
    assert len(lineage) == 1
    fv = feature_packet(base, selected)
    assert fv["values"]["observed_recovery_exact_hours_home"] == (12. if clock < 0 else 18.)
    assert fv["values"]["observed_inclusive_minutes_complete_1d_home"] == 1.


@pytest.mark.parametrize("clock", [-1, 1])
@pytest.mark.parametrize("same_case", [False, True])
def test_full_causal_native_event_pool_not_latest_casefold_projection(clock, same_case):
    import sports_prematch
    target, rows = inputs()
    ids = {str(i): code for i, code in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "ZZZ"), 1)}
    rule40 = {**rules(), "regulation_minutes": 40}
    target.update(provider="euroleague", competition="Euroleague", provider_event_id="E2026_TARGET", home_team_id="AAA", away_team_id="ZZZ")
    for i, row in enumerate(rows):
        row.update(provider="euroleague", competition="Euroleague", provider_event_id=f"E2026_{i+1}", context_rules=rule40,
                   home_team_id=ids[row["home_team_id"]], away_team_id=ids[row["away_team_id"]])
    changed = deepcopy(rows[0])
    if not same_case:
        changed["provider_event_id"] = changed["provider_event_id"].lower()
    changed["result_observed_at"] = canonical_timestamp(NOW+timedelta(microseconds=clock))
    rows.append(changed)
    ev = {**event(), "event_key": "euroleague:basketball:E2026_TARGET", "competition": "euroleague",
          "format": "euroleague_reg40_including_ot", "home_id": "euroleague:basketball:team:AAA", "away_id": "euroleague:basketball:team:ZZZ"}
    before = sports_prematch.predict_prematch("basketball", target, rows, NOW)
    result = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=ev, scope={"season": "2026", "rules": rule40})
    assert result["markets"] == {"home_win": before.p_home, "away_win": before.p_away}
    assert (result["reference_weights"]["kind"] == "unavailable") is (clock < 0 and not same_case)
