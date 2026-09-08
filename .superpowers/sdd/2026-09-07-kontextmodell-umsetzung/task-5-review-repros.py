"""Independent B1 review regressions; isolated fixtures, no provider calls.

Reviewed source: 9a4e04f7aa65ea5f9f0a1e8e7ef91216951274e6.
Failing assertions encode required behavior, not the observed implementation.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from context_observations import (
    append_observation, factor_state, freshness_policy, observations_as_of,
)
from context_models.contracts import ContextContractError, ContextIntegrityError
import runtime_paths


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
EVENT = "review-source:football:1"
OTHER = "review-source:football:2"


def record(**changes):
    return {
        "event_key": EVENT, "sport": "football", "competition": "39",
        "format": "90min", "subject_id": "review-source:player:7",
        "kind": "availability", "source": "review-source",
        "source_schema": "review-fixture-v1", "source_revision": "r1",
        "schedule_revision": "s1", "published_at": None,
        "publication_proof": None, "valid_from": NOW.isoformat(),
        "valid_until": None, "complete": False, "payload": {"status": "out"},
        **changes,
    }


def query(path, *, event=EVENT, schedule="s1", cutoff=NOW, mode="prospective"):
    return observations_as_of(path, event, cutoff=cutoff, schedule_revision=schedule, mode=mode)


def state(rows, **policy_options):
    return factor_state(
        rows, cutoff=NOW, scheduled_start=NOW + timedelta(hours=10),
        policy=freshness_policy(
            "availability", schedule_revision="s1", requires_complete=False,
            **policy_options,
        ),
    )


@pytest.mark.parametrize("case", [
    "future_retrospective", "wrong_revision", "unrelated_wrong_revision",
    "stale_secondary", "precedence_loser",
])
def test_available_refs_exclude_nonconsumed_observations(tmp_path, case):
    path = tmp_path / "models.db"
    current = append_observation(path, record(), observed_at=NOW)
    policy_options = {}
    if case == "future_retrospective":
        ignored = append_observation(
            path, record(source_revision="r2", payload={"status": "available"}),
            observed_at=NOW + timedelta(days=1),
        )
        rows = query(path, mode="historical")
    elif case in {"wrong_revision", "unrelated_wrong_revision"}:
        event = OTHER if case == "unrelated_wrong_revision" else EVENT
        ignored = append_observation(
            path, record(event_key=event, schedule_revision="s2"), observed_at=NOW,
        )
        rows = query(path) + query(path, event=event, schedule="s2")
    elif case == "stale_secondary":
        ignored = append_observation(
            path, record(source="old-source", valid_from=(NOW - timedelta(hours=7)).isoformat()),
            observed_at=NOW - timedelta(hours=7),
        )
        rows = query(path)
    else:
        ignored = append_observation(
            path, record(source="secondary", payload={"status": "available"}), observed_at=NOW,
        )
        rows = query(path)
        policy_options = {"source_precedence": ["review-source", "secondary"]}
    result = state(rows, **policy_options)
    assert result["state"] == "available"
    assert current in result["refs"]
    assert ignored not in result["refs"], (case, result)


@pytest.mark.parametrize("status", ["cancelled", "started", "completed"])
def test_unrelated_event_status_cannot_disable_current_event(tmp_path, status):
    path = tmp_path / "models.db"
    append_observation(path, record(), observed_at=NOW)
    append_observation(
        path, record(event_key=OTHER, kind="event_status", subject_id="review-source:fixture:2",
                     payload={"status": status}), observed_at=NOW,
    )
    rows = query(path) + query(path, event=OTHER)
    try:
        result = state(rows)
    except ContextContractError:
        return  # Rejecting mixed-event input is also safe.
    assert result["state"] == "available", result


@pytest.mark.parametrize("validity", ["future", "expired"])
def test_status_outside_its_valid_interval_cannot_disable_current_event(tmp_path, validity):
    path = tmp_path / "models.db"
    append_observation(path, record(), observed_at=NOW)
    interval = (
        {"valid_from": (NOW + timedelta(hours=1)).isoformat()}
        if validity == "future" else
        {"valid_from": (NOW - timedelta(hours=1)).isoformat(), "valid_until": NOW.isoformat()}
    )
    append_observation(
        path, record(kind="event_status", subject_id="review-source:fixture:1",
                     payload={"status": "cancelled"}, **interval), observed_at=NOW,
    )
    result = state(query(path))
    assert result["state"] == "available", (validity, result)


def test_stale_fact_cannot_make_fresh_empty_player_payload_available(tmp_path):
    path = tmp_path / "models.db"
    append_observation(
        path, record(valid_from=(NOW - timedelta(hours=7)).isoformat()),
        observed_at=NOW - timedelta(hours=7),
    )
    append_observation(
        path, record(source="fresh-empty-source", payload={"status": None}), observed_at=NOW,
    )
    result = state(query(path))
    assert result["state"] != "available", result


def test_precedence_loser_cannot_supply_required_collection_completeness(tmp_path):
    path = tmp_path / "models.db"
    append_observation(
        path, record(subject_id="review-source:team:1", complete=True, payload={"players": []}),
        observed_at=NOW,
    )
    append_observation(
        path, record(source="official", subject_id="review-source:team:1", complete=False,
                     payload={"players": ["review-source:player:7"]}), observed_at=NOW,
    )
    result = factor_state(
        query(path), cutoff=NOW, scheduled_start=NOW + timedelta(hours=10),
        policy=freshness_policy(
            "availability", schedule_revision="s1", requires_complete=True,
            source_precedence=["official", "review-source"],
        ),
    )
    assert result["state"] == "missing", result
    assert result["coverage"] == "incomplete"


def test_control_current_same_event_cancellation_is_effective(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, record(), observed_at=NOW)
    append_observation(
        path, record(kind="event_status", subject_id="review-source:fixture:1",
                     payload={"status": "cancelled"}), observed_at=NOW,
    )
    assert state(query(path))["state"] == "not_applicable"


def test_control_future_receipt_alone_cannot_make_factor_available(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, record(), observed_at=NOW + timedelta(days=1))
    assert query(path) == ()
    historical = query(path, mode="historical")
    assert historical[0]["evidence_class"] == "retrospective"
    assert state(historical)["state"] == "missing"


def test_control_exact_receipt_retry_and_recheck_are_immutable(tmp_path):
    path = tmp_path / "models.db"
    first = append_observation(path, record(), observed_at=NOW)
    assert append_observation(path, record(), observed_at=NOW) == first
    later = append_observation(path, record(), observed_at=NOW + timedelta(minutes=1))
    assert first != later
    assert query(path)[0]["digest"] == first
    assert query(path, cutoff=NOW + timedelta(minutes=1))[0]["digest"] == later
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone() == (2,)


def test_control_public_read_and_retry_reject_content_corruption(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, record(), observed_at=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE context_contents SET payload=?", (b"{\"bad\":true}",))
    with pytest.raises(ContextIntegrityError):
        query(path)
    with pytest.raises(ContextIntegrityError):
        append_observation(path, record(), observed_at=NOW)


@pytest.mark.parametrize("operation", ["append", "read"])
def test_control_b1_public_calls_reuse_a1_symlink_trust_guard(tmp_path, monkeypatch, operation):
    path = tmp_path / "models.db"
    real_lstat = runtime_paths.os.lstat

    def fake_leaf_symlink(candidate, *args, **kwargs):
        if Path(candidate) == path:
            return SimpleNamespace(st_mode=runtime_paths.stat.S_IFLNK)
        return real_lstat(candidate, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(runtime_paths.os, "lstat", fake_leaf_symlink)
        with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="symlink"):
            if operation == "append":
                append_observation(path, record(), observed_at=NOW)
            else:
                query(path)
    assert not path.exists()
