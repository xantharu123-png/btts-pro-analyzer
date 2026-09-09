"""Synthetic measured hockey mechanics; no real source/training qualification."""
from copy import deepcopy
from datetime import datetime, timedelta
from fractions import Fraction
import math

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from test_ice_hockey_context import NOW, event, scope, base, implementation
from test_ice_hockey_sources import raw, normalized, team


def receipt(item, observed=NOW):
    content = normalized(item, observed)
    stamp, content_hash = canonical_timestamp(observed), digest(content)
    return {**content, "content_digest": content_hash,
        "digest": digest({"content_digest": content_hash, "observed_at": stamp}),
        "observed_at": stamp, "effective_at": stamp, "evidence_class": "prospective", "publication_resolution": None}


def historical(original=None):
    original = original or base()
    results = []
    for match in original["reference_weights"]["selected"]:
        item = raw()
        item["event"].update(event_key="nhl:ice_hockey:"+match["event_id"],
            home_id="nhl:ice_hockey:team:"+match["home"].removeprefix("id:"),
            away_id="nhl:ice_hockey:team:"+match["away"].removeprefix("id:"),
            scheduled_start=canonical_timestamp(match["start"]))
        start = datetime.fromisoformat(match["start"])
        item["data"].update(actual_start=canonical_timestamp(start), actual_end=canonical_timestamp(start+timedelta(hours=2)),
            result_observed_at=canonical_timestamp(match["observed"]),
            teams={item["event"][side]: team(item["event"][side]) for side in ("home_id", "away_id")})
        results.append(item)
    return results


def full_inputs():
    original = base()
    return original, [*historical(original), raw("projection"), raw("starter"), raw("availability")]


def features(items, original=None, *, cutoff=NOW, current=None, scenario_id="candidate-a"):
    return implementation().hockey_features(current or event(), tuple(receipt(item) for item in items),
        original or base(), cutoff=cutoff, scenario_id=scenario_id)


def test_measured_reference_averages_each_actual_contributing_team_game_once():
    original, items = full_inputs()
    result = features(items, original)
    assert result["values"]["exposure_complete_home"] == 1
    assert result["values"]["exposure_complete_away"] == 1
    for side in ("home", "away"):
        native = event()[side+"_id"]
        measured = [item for item in items if item["kind"] == "appearance" and native in item["data"]["teams"]]
        assert measured
        for player in team(native)["players"]:
            stem = f'{side}/{player["role"]}/20252026/{player["player_id"]}'
            expected = float(sum(Fraction(next(p["regulation_seconds"] for p in item["data"]["teams"][native]["players"]
                if p["player_id"] == player["player_id"]), 3600) for item in measured)/len(measured))
            assert result["values"]["exposure_reference_"+stem] == expected
            assert result["values"]["exposure_delta_"+stem] == 0
            assert len(result["refs"]["exposure_reference_"+stem]) == len(measured)
    assert result["reference_hash"] == implementation().hockey_reference_hash(original, event())


@pytest.mark.parametrize("side", ["home", "away"])
def test_missing_required_reference_cells_do_not_become_zero_or_heal_from_old_load(side):
    original, items = full_inputs()
    native = event()[side+"_id"]
    affected = next(item for item in items if item["kind"] == "appearance" and native in item["data"]["teams"])
    affected["data"]["teams"][native]["players"][0]["regulation_seconds"] = None
    result = features(items, original)
    assert result["values"]["exposure_complete_"+side] == 0
    assert all(value is None for key, value in result["values"].items() if key.startswith("exposure_delta_"+side+"/"))


def test_unknown_goalie_preserves_two_explicit_unweighted_scenarios_not_confirmed_or_averaged():
    original, items = full_inputs()
    projection = next(item for item in items if item["kind"] == "projection")
    alternative = deepcopy(projection["data"]["scenarios"][0])
    alternative["scenario_id"] = "candidate-b"
    projection["data"]["scenarios"].append(alternative)
    items = [item for item in items if item["kind"] != "starter"]
    result = implementation().hockey_scenarios(event(), tuple(receipt(item) for item in items), original, cutoff=NOW)
    assert list(result) == ["candidate-a", "candidate-b"]
    assert all(value["values"]["goalie_assumed_home"] == 1 for value in result.values())
    assert result["candidate-a"]["coverage"] != result["candidate-b"]["coverage"]
    unspecified = features(items, original, scenario_id=None)
    assert unspecified["values"]["exposure_complete_home"] == 0
    assert unspecified["values"]["goalie_assumed_home"] is None


def test_performed_seconds_are_separate_skater_goalie_regulation_and_ot():
    result = features([raw()])
    assert result["values"]["observed_regulation_skater_seconds_3d_home"] == 18100
    assert result["values"]["observed_regulation_goalie_seconds_3d_home"] == 3500
    assert result["values"]["observed_overtime_skater_seconds_3d_home"] == 900
    assert result["values"]["observed_overtime_goalie_seconds_3d_home"] == 300
    assert result["values"]["observed_recovery_exact_hours_home"] == 36
    assert result["values"]["history_complete_3d_home"] == 0
    assert result["values"]["medical_fatigue_home"] is None
    assert result["values"]["travel_hours_home"] is None


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_workload_lower_window_bound_is_inclusive(days, microseconds):
    item = raw()
    end = NOW-timedelta(days=days)+timedelta(microseconds=microseconds)
    item["data"].update(actual_start=canonical_timestamp(end-timedelta(hours=2)), actual_end=canonical_timestamp(end),
        result_observed_at=canonical_timestamp(end))
    result = features([item])
    name = f"observed_regulation_skater_seconds_{days}d_home"
    assert result["values"][name] == (18100 if microseconds >= 0 else None)
    assert result["values"]["observed_recovery_exact_hours_home"] == pytest.approx((event_start()-end).total_seconds()/3600)


def event_start():
    return datetime.fromisoformat(event()["scheduled_start"])


def test_end_equal_decision_is_exact_rest_not_performed_window():
    item = raw()
    item["data"].update(actual_start=canonical_timestamp(NOW-timedelta(hours=2)), actual_end=canonical_timestamp(NOW),
        result_observed_at=canonical_timestamp(NOW))
    result = features([item])
    assert result["values"]["observed_recovery_exact_hours_home"] == 6
    assert result["values"]["observed_regulation_skater_seconds_7d_home"] is None


@pytest.mark.parametrize("mutation", ["event", "reference", "clock", "original"])
def test_features_bind_full_original_event_and_cutoff(mutation):
    original, current, cutoff = base(), event(), NOW
    if mutation == "event": current["schedule_revision"] = "rescheduled"
    elif mutation == "reference": original["reference_weights"]["selected"][0]["ref"] = "1"*64
    elif mutation == "clock": cutoff += timedelta(microseconds=1)
    else: original["version"] = "hockey-context-comparison-v1"
    with pytest.raises(ContextContractError):
        features([raw()], original, current=current, cutoff=cutoff)


@pytest.mark.parametrize("latest_kind", ["empty", "missing-cell", "expired", "future"])
def test_newest_projection_revision_never_falls_back_to_prior_complete_lineup(latest_kind):
    original, items = full_inputs()
    projection = next(item for item in items if item["kind"] == "projection")
    items.remove(projection)
    rows = [receipt(item) for item in items]
    old = receipt(projection, NOW-timedelta(minutes=2))
    rows.append(old)
    new = deepcopy(projection)
    if latest_kind in ("empty", "future"): new["data"]["scenarios"] = []
    elif latest_kind == "missing-cell": new["data"]["scenarios"][0]["teams"][event()["home_id"]]["players"][0]["regulation_seconds"] = None
    else:
        new["valid_from"] = canonical_timestamp(NOW-timedelta(minutes=2))
        new["valid_until"] = canonical_timestamp(NOW)
    rows.append(receipt(new, NOW+timedelta(microseconds=1) if latest_kind == "future" else NOW))
    fv = implementation().hockey_features(event(), tuple(rows), original, cutoff=NOW, scenario_id="candidate-a")
    assert fv["values"]["exposure_complete_home"] == (1 if latest_kind == "future" else 0)


def test_duplicate_ingestion_and_later_identical_historical_receipt_do_not_double_weight_game():
    original, items = full_inputs()
    rows = [receipt(item, NOW-timedelta(minutes=1)) for item in items]
    one = next(item for item in items if item["kind"] == "appearance" and event()["home_id"] in item["data"]["teams"])
    before = implementation().hockey_features(event(), tuple(rows), original, cutoff=NOW, scenario_id="candidate-a")
    rows.extend([rows[0], rows[0], receipt(one)])
    after = implementation().hockey_features(event(), tuple(rows), original, cutoff=NOW, scenario_id="candidate-a")
    assert before["values"] == after["values"]
    assert before["states"] == after["states"]
    assert before["reference_hash"] == after["reference_hash"]
    assert before["refs"] != after["refs"]  # The actual refreshed receipt still binds the snapshot.


@pytest.mark.parametrize("mutation", ["partial", "phase-missing", "future-time"])
def test_reference_binding_never_infers_missing_regulation_or_consumes_future_toi(mutation):
    original, items = full_inputs()
    sample = next(item for item in items if item["kind"] == "appearance" and event()["home_id"] in item["data"]["teams"])
    if mutation == "partial": sample["data"]["teams"][event()["home_id"]]["regulation_intervals"] = None
    elif mutation == "phase-missing": sample["data"]["regulation_seconds"] = None
    else:
        sample["data"]["actual_end"] = canonical_timestamp(NOW)
        sample["data"]["result_observed_at"] = canonical_timestamp(NOW)
    fv = features(items, original)
    assert fv["values"]["exposure_complete_home"] == 0
