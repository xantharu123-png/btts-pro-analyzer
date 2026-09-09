"""Historical parent corrections survive later unrelated native facts.

These real SQLite tests use synthetic source payloads, not observed PandaScore
data or empirical effect approval. No result/ledger history is rewritten.
"""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError
from test_esports_context import NOW, case, lineup_data, source
from test_esports_context_corrections import completed_then_started
from test_esports_context_revisions import revise


def lifecycle(team, status, fact):
    first, _ = completed_then_started(team)
    original = first[0]
    ev = {**original["event"], "status": status}
    if fact == "map":
        data = {"map_id": "pandascore:esports:map:8901", "winner_id": None,
                "actual_start": None, "actual_end": None}
        correction = source("map", ev, data)
        later = source("map", original["event"], {**data,
            "winner_id": original["event"]["home_id"],
            "actual_start": (NOW-timedelta(hours=5)).isoformat(),
            "actual_end": (NOW-timedelta(hours=4)).isoformat()})
    else:
        data = {"status": "observed", "teams": {key: {"complete": False, "players": []}
                for key in (ev["home_id"], ev["away_id"])}}
        correction = source("observed_lineup", ev, data)
        later = source("observed_lineup", original["event"], lineup_data(original["event"]))
    return [first, (correction, NOW-timedelta(hours=2)), (later, NOW-timedelta(hours=1))]


@pytest.mark.parametrize("status,fact", [("started", "map"), ("cancelled", "map"), ("cancelled", "observed_lineup")])
@pytest.mark.parametrize("team,side", [(7, "home"), (8, "away")])
def test_every_nonterminal_parent_retraction_survives_other_completed_facts(case, tmp_path, status, fact, team, side):
    rows, features = revise(case, tmp_path, lifecycle(team, status, fact))
    assert any(row["payload"]["event"]["status"] == status for row in rows)
    for days in (1, 3, 7):
        assert features["values"][f"observed_series_count_{days}d_{side}"] is None
    for timing in ("exact", "minimum"):
        assert features["values"][f"observed_recovery_{timing}_hours_{side}"] is None


@pytest.mark.parametrize("fact", ["map", "observed_lineup"])
def test_known_parent_cancel_cannot_be_undone_by_its_expiry(case, tmp_path, fact):
    records = lifecycle(7, "cancelled", fact)
    correction = records[1][0]
    correction["valid_until"] = (NOW-timedelta(minutes=90)).isoformat()
    _, features = revise(case, tmp_path, records)
    assert features["values"]["observed_series_count_1d_home"] is None
    assert features["values"]["observed_recovery_exact_hours_home"] is None


@pytest.mark.parametrize("fact", ["map", "observed_lineup"])
def test_source_cannot_invent_future_valid_from_for_known_cancel(case, tmp_path, fact):
    records = lifecycle(7, "cancelled", fact)
    records[1][0]["valid_from"] = (NOW+timedelta(minutes=90)).isoformat()
    with pytest.raises(ContextContractError):
        revise(case, tmp_path, records)


@pytest.mark.parametrize("status,fact", [("started", "map"), ("cancelled", "map"), ("cancelled", "observed_lineup")])
def test_new_actual_consistent_series_revision_restores_only_its_own_fact(case, tmp_path, status, fact):
    records = lifecycle(7, status, fact)
    newer = deepcopy(records[0][0])
    newer["data"]["actual_end"] = (NOW-timedelta(minutes=45)).isoformat()
    _, features = revise(case, tmp_path, [*records, (newer, NOW-timedelta(minutes=30))])
    assert features["values"]["observed_series_count_1d_home"] == 1
    assert features["values"]["observed_recovery_exact_hours_home"] == 6.75


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_cancel_evidence_uses_real_receipt_cutoff_not_later_metadata(case, tmp_path, offset):
    records = lifecycle(7, "cancelled", "map")
    records[1] = records[1][0], NOW+timedelta(microseconds=offset)
    _, features = revise(case, tmp_path, records)
    expected = 1 if offset > 0 else None
    assert features["values"]["observed_series_count_1d_home"] == expected
    assert features["values"]["observed_recovery_exact_hours_home"] == (9 if offset > 0 else None)
