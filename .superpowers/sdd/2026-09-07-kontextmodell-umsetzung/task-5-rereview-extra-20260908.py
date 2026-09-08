"""Bounded independent checks of risks introduced by B1 source selection fixes."""

from copy import deepcopy
from datetime import timedelta
from itertools import permutations
from pathlib import Path
import runpy

import pytest

_original = runpy.run_path(str(Path(__file__).with_name("task-5-rereview-repros-20260908.py")))
NOW, EVENT, OTHER = (_original[name] for name in ("NOW", "EVENT", "OTHER"))
record, query, state = (_original[name] for name in ("record", "query", "state"))
append_observation, factor_state, freshness_policy = (
    _original[name] for name in ("append_observation", "factor_state", "freshness_policy")
)
ContextContractError = _original["ContextContractError"]


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_order_duplicates_and_excluded_sources_cannot_change_usable_metadata(tmp_path, order):
    path = tmp_path / "models.db"
    winner = append_observation(path, record(), observed_at=NOW)
    empty = append_observation(path, record(source="empty", payload={"status": None}), observed_at=NOW)
    stale = append_observation(
        path, record(source="stale", valid_from=(NOW - timedelta(hours=7)).isoformat(),
                     payload={"status": "available"}), observed_at=NOW - timedelta(hours=7),
    )
    rows = query(path)
    arranged = tuple(rows[index] for index in order)
    untouched = deepcopy(arranged)
    options = {
        "source_precedence": ["review-source", "empty", "stale"],
        "source_max_age_seconds": {"review-source": 3600, "empty": 1, "stale": 2},
    }
    result = state(arranged, **options)
    assert result == state(arranged + arranged, **options)
    assert arranged == untouched
    assert result == {
        "state": "available", "refs": sorted([winner, empty, stale]),
        "usable_refs": [winner], "coverage": "incomplete",
        "fresh_until": "2026-09-07T13:00:00.000000Z", "policy_version": "context-freshness-v1",
    }


@pytest.mark.parametrize("policy_precedence", [[], ["review-source"]])
def test_simultaneous_empty_revision_cannot_be_dropped_to_hide_same_source_conflict(tmp_path, policy_precedence):
    path = tmp_path / "models.db"
    a = append_observation(path, record(), observed_at=NOW)
    b = append_observation(path, record(source_revision="r2", payload={"status": None}), observed_at=NOW)
    result = state(query(path), source_precedence=policy_precedence)
    assert result["state"] == "conflicting"
    assert result["usable_refs"] == []
    assert result["refs"] == sorted([a, b])
    assert result["fresh_until"] is None


@pytest.mark.parametrize("scope", ["event", "competition", "format", "sport"])
@pytest.mark.parametrize("early_return", ["policy", "kickoff"])
def test_mixed_scope_must_raise_even_when_policy_or_clock_would_return_early(tmp_path, scope, early_return):
    path = tmp_path / "models.db"
    append_observation(path, record(), observed_at=NOW)
    changed = {
        "event": {"event_key": OTHER}, "competition": {"competition": "140"},
        "format": {"format": "120min"},
        "sport": {"sport": "tennis", "event_key": "review-source:tennis:1"},
    }[scope]
    append_observation(
        path, record(kind="event_status", subject_id="review-source:fixture:9",
                     payload={"status": "cancelled"}, **changed), observed_at=NOW,
    )
    rows = query(path)
    if "event_key" in changed:
        rows += query(path, event=changed["event_key"])
    with pytest.raises(ContextContractError, match="scope"):
        factor_state(
            rows, cutoff=NOW,
            scheduled_start=NOW if early_return == "kickoff" else NOW + timedelta(hours=10),
            policy=freshness_policy(
                "availability", schedule_revision="s1", requires_complete=False,
                event_status="cancelled" if early_return == "policy" else "scheduled",
            ),
        )


@pytest.mark.parametrize("condition", ["stale", "future_validity", "wrong_schedule", "walkover", "unfinished"])
def test_all_nonavailable_factors_have_empty_usable_provenance(tmp_path, condition):
    path = tmp_path / "models.db"
    row, observed, kind, schedule = record(), NOW, "availability", "s1"
    if condition == "stale":
        observed -= timedelta(hours=7)
        row["valid_from"] = observed.isoformat()
    elif condition == "future_validity":
        row["valid_from"] = (NOW + timedelta(minutes=1)).isoformat()
    elif condition == "wrong_schedule":
        row["schedule_revision"] = schedule = "s2"
    else:
        row.update(kind="workload", complete=True,
                   payload={"status": "walkover" if condition == "walkover" else "started", "games": None})
        kind = "workload"
    receipt = append_observation(path, row, observed_at=observed)
    result = factor_state(
        query(path, schedule=schedule), cutoff=NOW, scheduled_start=NOW + timedelta(hours=10),
        policy=freshness_policy(kind, schedule_revision="s1", requires_complete=False),
    )
    assert result["state"] != "available"
    assert result["usable_refs"] == []
    assert result["refs"] == [receipt]
    assert result["fresh_until"] is None


def test_weather_future_forecast_validity_is_not_confused_with_future_status(tmp_path):
    path = tmp_path / "models.db"
    start = NOW + timedelta(hours=2)
    receipt = append_observation(
        path, record(kind="weather", complete=True, payload={"temperature_c": 20},
                     valid_from=start.isoformat(), valid_until=(start + timedelta(hours=1)).isoformat()),
        observed_at=NOW,
    )
    result = factor_state(
        query(path), cutoff=NOW, scheduled_start=start,
        policy=freshness_policy("weather", schedule_revision="s1", requires_complete=True),
    )
    assert result["state"] == "available"
    assert result["usable_refs"] == [receipt]
    assert result["fresh_until"] == "2026-09-07T15:00:00.000000Z"


def test_agreeing_sources_are_both_usable_without_undeclared_precedence(tmp_path):
    path = tmp_path / "models.db"
    a = append_observation(path, record(), observed_at=NOW)
    b = append_observation(path, record(source="second"), observed_at=NOW)
    result = state(query(path))
    assert result["state"] == "available"
    assert result["usable_refs"] == result["refs"] == sorted([a, b])
