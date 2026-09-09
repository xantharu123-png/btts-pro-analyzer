"""Actual sanitized source shapes; synthetic chronology changes are labelled."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, canonical_timestamp, digest

NOW = datetime(2026, 9, 9, 9, tzinfo=timezone.utc)


def raw():
    data = json.loads((Path(__file__).parent / "fixtures/context/football/api-football-20260909.json").read_text(encoding="utf-8"))
    call = data["calls"][0]
    return tuple(call["samples"]), tuple({"detail": detail, "observed_at": canonical_timestamp(call["received_at"])} for detail in call["samples"])


def build(rows, receipts, cutoff=NOW):
    from context_sources.football_native import football_native_provenance
    return football_native_provenance(rows, receipts, decision_at=cutoff)


def test_actual_adapter_material_binds_only_the_exact_requested_base_records():
    rows, receipts = raw()
    proof = build(rows, receipts)
    records = {digest(engine.football_base_history_record(row)): engine.football_base_history_record(row) for row in rows}
    current_ref = digest(engine.football_base_history_record(rows[1]))
    checked = engine._football_native_bindings(proof, records, current_ref)
    assert len(checked) == 2 and all(row["native_event_key"].startswith("api-football:football:") for row in checked.values())
    assert checked[digest(engine.football_base_history_record(rows[0]))]["roster_join"] == "verified_native"
    assert checked[current_ref]["roster_join"] == "unresolved"
    appearances = proof["records"][digest(engine.football_base_history_record(rows[0]))]["payload"]["appearances"]
    assert len(appearances) == 46 and sum(row["minutes"] is not None for row in appearances) == 32
    assert proof["decision_at"] == canonical_timestamp(NOW)


@pytest.mark.parametrize("field", ["fixture_id", "home_id", "away_id", "league_id", "season", "scheduled_start", "goals_home"])
def test_mismatched_base_identity_remains_unresolved_not_source_relabelled(field):
    rows, receipts = raw()
    rows = deepcopy(rows)
    paths = {"fixture_id": ("fixture", "id"), "home_id": ("teams", "home", "id"), "away_id": ("teams", "away", "id"),
             "league_id": ("league", "id"), "season": ("league", "season"), "scheduled_start": ("fixture", "date"), "goals_home": ("goals", "home")}
    target = rows[0]
    path = paths[field]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = "2026-08-23T15:00:00+00:00" if field == "scheduled_start" else 999
    assert digest(engine.football_base_history_record(rows[0])) not in build(rows, receipts)["records"]


def test_csv_even_with_positive_local_id_is_never_promoted_to_native():
    rows, receipts = raw()
    rows = deepcopy(rows)
    rows[0]["challenge_source"] = "football-data-results-only"
    assert digest(engine.football_base_history_record(rows[0])) not in build(rows, receipts)["records"]


def test_source_received_today_cannot_be_used_for_yesterdays_decision():
    rows, receipts = raw()
    assert build(rows, receipts, NOW - timedelta(days=1))["records"] == {}


def test_nonbaseline_native_details_are_not_claimed_as_baseline_inputs():
    rows, receipts = raw()
    proof = build((rows[1],), receipts)
    assert set(proof["records"]) == {digest(engine.football_base_history_record(rows[1]))}


def test_simultaneous_conflicting_native_corrections_are_not_lexically_chosen():
    rows, receipts = raw()
    changed = deepcopy(receipts[0])
    changed["detail"]["goals"]["home"] += 1
    assert digest(engine.football_base_history_record(rows[0])) not in build(rows, receipts + (changed,))["records"]


def test_later_corrected_result_cannot_certify_an_older_different_base_result():
    rows, receipts = raw()
    changed = deepcopy(receipts[0])
    changed["observed_at"] = canonical_timestamp(NOW - timedelta(minutes=1))
    changed["detail"]["goals"]["home"] += 1
    assert digest(engine.football_base_history_record(rows[0])) not in build(rows, receipts + (changed,))["records"]


def test_duplicate_native_response_is_idempotent():
    rows, receipts = raw()
    assert build(rows, receipts + receipts) == build(rows, receipts)


def test_malformed_receipt_clock_or_unknown_transport_is_not_a_source_proof():
    rows, receipts = raw()
    changed = deepcopy(receipts[0])
    changed["observed_at"] = "2026-09-09T09:00:00"
    with pytest.raises(ContextContractError):
        build(rows, (changed,))
    with pytest.raises(ContextContractError):
        build(rows, ({**receipts[0], "verified": True},))
