"""Actual local B1/A1/B3 SQLite mechanics using explicitly synthetic hockey data."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextContractError, canonical_bytes, canonical_timestamp, digest
from context_observations import append_observation
from test_ice_hockey_context import NOW, event, base, implementation
from test_ice_hockey_sources import raw, normalized, team, source
from test_ice_hockey_features import receipt, full_inputs
from test_ice_hockey_effects import replacement, fitted_artifact, approval


def write(path, item, observed=NOW):
    return append_observation(path, normalized(item, observed), observed_at=observed)


def read(path, keys, cutoff=NOW):
    return tuple(row for key in sorted(set(keys)) for row in source().hockey_observations_as_of(
        path, key, cutoff=cutoff, schedule_revision=event()["schedule_revision"]))


def calculate(path, keys, original=None, *, cutoff=NOW):
    return implementation().hockey_features(event(), read(path, keys, cutoff), original or base(),
        cutoff=cutoff, scenario_id="candidate-a")


def historical_item(*, event_id=2025021888, end_hours=30, team_id=None):
    item = raw()
    start, end = NOW-timedelta(hours=end_hours+2), NOW-timedelta(hours=end_hours)
    item["event"].update(event_key="nhl:ice_hockey:"+str(event_id), scheduled_start=canonical_timestamp(start))
    if team_id is not None: item["event"]["home_id"] = team_id
    item["data"].update(actual_start=canonical_timestamp(start), actual_end=canonical_timestamp(end),
        result_observed_at=canonical_timestamp(end), teams={item["event"][side]: team(item["event"][side]) for side in ("home_id", "away_id")})
    return item


def incomplete(item):
    for usage in item["data"]["teams"].values():
        usage.update(complete=False, players=[], regulation_intervals=None, overtime_intervals=None)
    return item


def change_team(item, side, new_id):
    old = item["event"][side+"_id"]
    item["event"][side+"_id"] = new_id
    item["data"]["teams"].pop(old)
    item["data"]["teams"][new_id] = team(new_id)


def test_full_actual_sqlite_source_b2_b3_and_compute_once_roundtrip(tmp_path):
    from model_artifacts import put_artifact, load_artifact
    from context_snapshots import compute_once, snapshot_key
    original, items = full_inputs()
    player, _ = replacement(items)
    path = tmp_path/"hockey.db"
    refs = [write(path, item) for item in items]
    rows = read(path, [item["event"]["event_key"] for item in items])
    assert {row["digest"] for row in rows} == set(refs)
    fv = implementation().hockey_features(event(), rows, original, cutoff=NOW, scenario_id="candidate-a")
    artifact = fitted_artifact(fv, names=[f"exposure_delta_{side}/skater/20252026/{player}" for side in ("home", "away")])
    effect_hash = put_artifact(path, payload=artifact, kind="context-effect-v1", created_at=NOW-timedelta(days=7))
    loaded = load_artifact(path, effect_hash)
    approved = approval(artifact)
    calls = []
    key = snapshot_key(event=event(), base_hash=digest(original), context_refs=tuple(sorted(set(refs))),
        feature_version=fv["version"], feature_hash=digest(fv), effect_hash=effect_hash, decision_at=NOW,
        approval_hash=approved["digest"])
    def compute():
        calls.append(1)
        return implementation().hockey_context_result(original, fv, loaded, event=event(), effect_hash=effect_hash, approval=approved)
    first, second = compute_once(path, key, compute), compute_once(path, key, compute)
    assert first == second and calls == [1]
    assert first["role"] == "applied"
    assert first["used_params"] != original["params"]
    assert first["used_params"]["overtime_home_probability"] == original["params"]["overtime_home_probability"]


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("last", ["leave-incomplete", "leave-complete", "return-incomplete", "return-complete"])
def test_actual_sqlite_participant_leave_return_never_stitches_prior_projection(tmp_path, side, last):
    path = tmp_path/"lineage.db"
    old = historical_item(event_id=2025021777, end_hours=120)
    recent = historical_item(end_hours=30)
    moved = deepcopy(recent)
    moved["event"]["schedule_revision"] = "corrected-2"
    change_team(moved, side, "nhl:ice_hockey:team:9")
    moved = incomplete(moved) if last == "leave-incomplete" else moved
    revisions = [old, recent, moved]
    if last.startswith("return"):
        returned = deepcopy(recent)
        returned["event"]["schedule_revision"] = "corrected-3"
        revisions.append(incomplete(returned) if last == "return-incomplete" else returned)
    refs = [write(path, item, NOW-timedelta(minutes=10-i)) for i, item in enumerate(revisions)]
    keys = [item["event"]["event_key"] for item in revisions]
    selected = read(path, keys)
    assert set(refs) == {row["digest"] for row in selected}
    fv = calculate(path, keys)
    exact = "observed_recovery_exact_hours_"+side
    if last.endswith("incomplete"):
        assert fv["values"][exact] is None and fv["states"][exact] == "conflicting"
        assert fv["values"]["observed_regulation_skater_seconds_3d_"+side] is None
    else:
        assert fv["values"][exact] == (126 if last == "leave-complete" else 36)
    assert refs[1] in fv["refs"][exact] or last == "leave-complete"


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("micros", [-1, 0, 1])
@pytest.mark.parametrize("conflicting", [False, True])
def test_actual_unknown_terminal_receipt_window_bounds_and_conflict_refs(tmp_path, days, micros, conflicting):
    path = tmp_path/"bounds.db"
    current = historical_item(end_hours=12)
    unknown = historical_item(event_id=2025021777, end_hours=days*24+10)
    upper = NOW-timedelta(days=days)+timedelta(microseconds=micros)
    unknown["data"].update(actual_start=None, actual_end=None, result_observed_at=canonical_timestamp(upper))
    all_items = [current, unknown]
    if conflicting:
        other = deepcopy(unknown)
        change_team(other, "away", "nhl:ice_hockey:team:9")
        all_items.append(other)
    refs = [write(path, item) for item in all_items]
    fv = calculate(path, [item["event"]["event_key"] for item in all_items])
    name = f"observed_regulation_skater_seconds_{days}d_home"
    assert fv["values"][name] == (18100 if micros < 0 else None)
    assert set(refs) <= set(fv["refs"][name])
    assert fv["values"]["observed_recovery_exact_hours_home"] == 18


@pytest.mark.parametrize("kind", ["projection", "starter", "availability"])
def test_current_facts_exact_schedule_old_revision_does_not_refresh(tmp_path, kind):
    path = tmp_path/"current.db"
    item = raw(kind)
    item["event"]["schedule_revision"] = "former"
    write(path, item)
    assert read(path, [event()["event_key"]]) == ()
    item["event"]["schedule_revision"] = event()["schedule_revision"]
    write(path, item)
    rows = read(path, [event()["event_key"]])
    assert len(rows) == 1 and rows[0]["schedule_revision"] == event()["schedule_revision"]


def test_owning_reader_preserves_old_schedule_history_for_reference_but_never_mix_latest(tmp_path):
    original, items = full_inputs()
    historical = next(item for item in items if item["kind"] == "appearance" and event()["home_id"] in item["data"]["teams"])
    historical["event"]["schedule_revision"] = "historic-original-schedule"
    path = tmp_path/"reference.db"
    for item in items: write(path, item, NOW-timedelta(minutes=1))
    keys = [item["event"]["event_key"] for item in items]
    assert calculate(path, keys, original)["values"]["exposure_complete_home"] == 1
    revised = incomplete(deepcopy(historical))
    revised["event"]["schedule_revision"] = "historic-correction"
    new_ref = write(path, revised)
    result = calculate(path, keys, original)
    assert result["values"]["exposure_complete_home"] == 0
    assert new_ref in result["refs"]["exposure_complete_home"]
    assert len(source().hockey_observations_as_of(path, historical["event"]["event_key"], cutoff=NOW, schedule_revision="irrelevant")) == 2


@pytest.mark.parametrize("receipt_shift", [-1, 0, 1])
def test_latest_receipt_cutoff_does_not_import_a_future_correction(tmp_path, receipt_shift):
    path = tmp_path/"future.db"
    item = historical_item()
    write(path, item, NOW-timedelta(minutes=1))
    changed = incomplete(deepcopy(item))
    changed["event"]["schedule_revision"] = "update"
    write(path, changed, NOW+timedelta(microseconds=receipt_shift))
    fv = calculate(path, [item["event"]["event_key"]])
    assert fv["values"]["observed_regulation_skater_seconds_3d_home"] == (18100 if receipt_shift > 0 else None)
    assert fv["values"]["observed_recovery_exact_hours_home"] == 36  # Actual end remains known in same participants.


@pytest.mark.parametrize("mutation", ["payload", "receipt-clock", "index-kind", "missing-content"])
def test_real_database_corruption_fails_before_future_or_kind_filter(tmp_path, mutation):
    path = tmp_path/"corrupt.db"
    item = historical_item()
    reference = write(path, item, NOW+timedelta(minutes=1))
    with sqlite3.connect(path) as db:
        if mutation == "payload": db.execute("UPDATE context_contents SET payload=?", (b"{}",))
        elif mutation == "receipt-clock": db.execute("UPDATE context_observations SET observed_at=?", (canonical_timestamp(NOW),))
        elif mutation == "index-kind": db.execute("UPDATE context_observations SET kind='availability'")
        else: db.execute("DELETE FROM context_contents")
    with pytest.raises(ContextContractError): read(path, [item["event"]["event_key"]])


def test_actual_wal_read_is_one_snapshot_and_later_query_sees_correction(tmp_path, monkeypatch):
    import context_observations
    path = tmp_path/"wal.db"
    item = historical_item()
    first = write(path, item, NOW-timedelta(minutes=1))
    with sqlite3.connect(path) as db: assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    corrected = incomplete(deepcopy(item))
    original_decode, appended = context_observations._decode_receipt, []
    def decode(row):
        value = original_decode(row)
        if not appended:
            appended.append(True)
            write(path, corrected)
        return value
    monkeypatch.setattr(context_observations, "_decode_receipt", decode)
    first_read = read(path, [item["event"]["event_key"]])
    assert [row["digest"] for row in first_read] == [first]
    assert len(read(path, [item["event"]["event_key"]])) == 2


@pytest.mark.parametrize("path_case", ["bad-key", "bad-revision", "symlink"])
def test_owning_reader_keeps_existing_a1_path_contract(tmp_path, path_case):
    path = tmp_path/"safe.db"
    item = historical_item()
    write(path, item)
    key, revision = item["event"]["event_key"], "s1"
    if path_case == "bad-key": key = "nhl:ice_hockey:0"
    elif path_case == "bad-revision": revision = "../other"
    else:
        linked = tmp_path/"linked.db"
        try: linked.symlink_to(path)
        except OSError: pytest.skip("Windows symlink privilege unavailable")
        path = linked
    with pytest.raises((ContextContractError, ValueError, PermissionError)):
        source().hockey_observations_as_of(path, key, cutoff=NOW, schedule_revision=revision)
