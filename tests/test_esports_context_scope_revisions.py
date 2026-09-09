"""C4 R1c: partial native scope revisions cannot certify an empty history.

Real temporary B1 SQLite, synthetic native transport; not live/empirical proof.
"""
from copy import deepcopy
from datetime import timedelta

import pytest

from test_esports_context import NOW, case, native_event, source
from test_esports_context_revisions import revise


def history_with_scope_revision(*, team=7, cancellation=False, complete=False):
    event = native_event(8890, team, 100, status="completed", start=NOW-timedelta(hours=8))
    completed = source("series", event, {
        "actual_start": (NOW-timedelta(hours=7)).isoformat(),
        "actual_end": (NOW-timedelta(hours=3)).isoformat(),
        "winner_id": event["home_id"], "score_a": 2, "score_b": 0,
    })
    records = [(completed, NOW-timedelta(hours=2, minutes=59))]
    if cancellation:
        cancelled = source("map", {**event, "status": "cancelled"}, {
            "map_id": "pandascore:esports:map:8891", "winner_id": None,
            "actual_start": None, "actual_end": None,
        })
        later = source("map", event, {"map_id": "pandascore:esports:map:8891",
            "winner_id": event["home_id"], "actual_start": (NOW-timedelta(hours=5)).isoformat(),
            "actual_end": (NOW-timedelta(hours=4)).isoformat()})
        records.extend(((cancelled, NOW-timedelta(hours=2)), (later, NOW-timedelta(hours=1))))
    revision = deepcopy(completed)
    revision["scope"]["season_id"] = 2027
    if not complete:
        revision["data"].update(winner_id=None, score_a=None, score_b=None, actual_start=None, actual_end=None)
    records.append((revision, NOW-timedelta(minutes=30)))
    return records


def assert_uncertain(features, side):
    names = [f"observed_series_count_{days}d_{side}" for days in (1, 3, 7)]
    names += [f"observed_series_count_{days}d_complete_{side}" for days in (1, 3, 7)]
    names += [f"observed_recovery_{kind}_hours_{side}" for kind in ("exact", "minimum")]
    for name in names:
        assert features["values"][name] is None, (name, features["values"][name])
        assert features["states"][name] != "available"
        assert features["refs"][name] == []


@pytest.mark.parametrize("team,side", [(7, "home"), (8, "away")])
@pytest.mark.parametrize("cancellation", [False, True])
@pytest.mark.parametrize("complete", [False, True])
def test_new_native_scope_retires_old_scope_only_when_own_fact_is_complete(case, tmp_path, team, side, cancellation, complete):
    records = history_with_scope_revision(team=team, cancellation=cancellation, complete=complete)
    observations, features = revise(case, tmp_path, records)
    relevant = [row for row in observations if row["event_key"] == records[0][0]["event"]["event_key"]]
    assert {row["payload"]["scope"]["season_id"] for row in relevant} == {2026, 2027}
    assert max(relevant, key=lambda row: row["observed_at"])["complete"] is complete
    if complete:
        for root in [*(f"observed_series_count_{days}d" for days in (1, 3, 7)),
                     "observed_recovery_exact_hours", "observed_recovery_minimum_hours"]:
            key = root+"_"+side
            assert features["values"][key] == case["features"]["values"][key]
        assert features["values"]["observed_series_count_1d_"+side] == 0
        assert features["values"]["observed_recovery_exact_hours_"+side] == 150
    else:
        assert_uncertain(features, side)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_scope_revision_uses_actual_receipt_at_microsecond_cutoff(case, tmp_path, offset):
    records = history_with_scope_revision()
    records[-1] = records[-1][0], NOW+timedelta(microseconds=offset)
    _, features = revise(case, tmp_path, records)
    if offset > 0:
        assert features["values"]["observed_series_count_1d_home"] == 1
        assert features["values"]["observed_recovery_exact_hours_home"] == 9
    else:
        assert_uncertain(features, "home")


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_expiry_does_not_convert_known_partial_scope_change_to_zero(case, tmp_path, offset):
    records = history_with_scope_revision()
    records[-1][0]["valid_until"] = (NOW+timedelta(microseconds=offset)).isoformat()
    _, features = revise(case, tmp_path, records)
    assert_uncertain(features, "home")


def test_same_scope_unknown_end_remains_receipt_bound_not_false_exact_recovery(case, tmp_path):
    records = history_with_scope_revision()
    records[-1][0]["scope"]["season_id"] = 2026
    _, features = revise(case, tmp_path, records)
    assert features["values"]["observed_series_count_1d_home"] is None
    assert features["values"]["observed_recovery_exact_hours_home"] is None
    assert features["values"]["observed_recovery_minimum_hours_home"] == 6.5
    assert features["values"]["history_complete_home"] == 0
