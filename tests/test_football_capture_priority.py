"""Source-budget priority uses real bundles and isolated SQLite receipts.

These synthetic native responses establish capture mechanics, not real player
coverage, a historical publication, or an empirically approved model effect.
"""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import digest
from context_models.football_original_storage import StorageBudgetExceeded
from context_observations import append_bounded_observation_batch
from context_sources.football_capture import _Capture
from context_sources.football_retention import fixture_bundle
from challenge_engine import football_base_history_record
from test_context_football_capture import detail, stored
from test_football_context_provider import NOW, payload


def scheduled(fid, status="NS"):
    raw = detail()
    raw["fixture"]["id"] = fid
    raw["fixture"]["status"]["short"] = status
    return raw


def final(fid):
    raw = scheduled(fid)
    raw["fixture"]["date"] = "2026-09-01T12:00:00+00:00"
    raw["fixture"]["status"]["short"] = "FT"
    raw["goals"] = {"home": 2, "away": 1}
    raw.pop("lineups", None)
    raw.pop("players", None)  # Bulk completed-history responses are summaries.
    return raw


def append_bundle(path, raw, at):
    rows, base = fixture_bundle(raw, at)
    refs, cost = append_bounded_observation_batch(
        path, tuple((row, at) for row in rows), max_new_payload_bytes=100_000,
    )
    return refs, base, cost


def received(worker, raw, at=NOW):
    # Exercise the real response observer but never fetch a provider endpoint.
    worker.record("fixtures", {"id": raw["fixture"]["id"]}, payload([raw]),
                  observed_at=at, status=200)


@pytest.mark.parametrize("status", ["NS", "TBD", "PST"])
def test_two_prematch_targets_precede_interleaved_new_history_at_exact_budget(tmp_path, status):
    # Removing target priority lets FT 211 spend the second target's budget.
    first, history, second = scheduled(111, status), final(211), scheduled(112, status)
    measured = tmp_path / "measure.db"
    _, _, first_cost = append_bundle(measured, first, NOW)
    _, _, second_cost = append_bundle(measured, second, NOW + timedelta(seconds=2))
    budget = first_cost + second_cost
    history_measure = tmp_path / "history-measure.db"
    append_bundle(history_measure, first, NOW)
    _, _, history_cost = append_bundle(history_measure, history, NOW + timedelta(seconds=1))
    assert history_cost < second_cost  # The old order really can spend target 2's bytes.
    path = tmp_path / "capture.db"
    worker = _Capture(path, baseline_enabled=True)
    for offset, raw in enumerate((first, history, second)):
        received(worker, raw, NOW + timedelta(seconds=offset))

    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((first, second, history), max_new_payload_bytes=budget)

    assert set(worker.baseline_refs) == {111, 112}
    assert worker.baseline_budget_excluded_ids == {211}
    assert worker.source_inserted_bytes == budget
    bases = [row for row in stored(path) if row["kind"] == "base_fixture"]
    assert {row["event_key"] for row in bases} == {
        "api-football:football:111", "api-football:football:112",
    }
    assert {row["event_key"]: row["observed_at"] for row in bases} == {
        "api-football:football:111": "2026-09-09T09:00:00.000000Z",
        "api-football:football:112": "2026-09-09T09:00:02.000000Z",
    }


def test_budget_exclusion_still_allows_later_zero_cost_final_reuse(tmp_path):
    # Breaking on the first unaffordable FT would conceal later complete reuse.
    path = tmp_path / "capture.db"
    old, new, target = final(211), final(212), scheduled(111)
    old_refs, base, _ = append_bundle(path, old, NOW - timedelta(seconds=1))
    _, _, target_cost = append_bundle(tmp_path / "measure.db", target, NOW)
    worker = _Capture(path, baseline_enabled=True)
    for raw in (target, new, old):
        received(worker, raw)
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((target, new, old), max_new_payload_bytes=target_cost)

    assert set(worker.baseline_refs) == {111, 211}
    assert worker.baseline_refs[211] == {old_refs[base]}
    assert worker.baseline_budget_excluded_ids == {212}
    assert worker.source_inserted_bytes == target_cost
    reused = [row for row in stored(path) if row["event_key"] == "api-football:football:211"]
    assert {row["observed_at"] for row in reused} == {"2026-09-09T08:59:59.000000Z"}


def test_unaffordable_target_correction_revokes_the_older_target_binding(tmp_path):
    # Reordering only the NS revision, rather than the event's entire received
    # sequence, could hide a newer correction behind a usable old target.
    first, history = scheduled(111), final(211)
    correction = deepcopy(first)
    correction["fixture"]["date"] = "2026-09-09T17:00:00+00:00"
    _, _, cost = append_bundle(tmp_path / "measure.db", first, NOW)
    path = tmp_path / "capture.db"
    worker = _Capture(path, baseline_enabled=True)
    for offset, raw in enumerate((first, history, correction)):
        received(worker, raw, NOW + timedelta(seconds=offset))
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((correction, history), max_new_payload_bytes=cost)

    assert not worker.baseline_refs
    assert worker.baseline_budget_excluded_ids == {111, 211}
    # The old stored receipt remains immutable, but cannot authorize the target.
    bases = [row for row in stored(path) if row["kind"] == "base_fixture"]
    assert len(bases) == 1
    assert bases[0]["event_key"] == "api-football:football:111"
    assert bases[0]["observed_at"] == "2026-09-09T09:00:00.000000Z"


def test_priority_cannot_reuse_an_old_final_across_an_unstored_correction(tmp_path):
    # Collapsing A -> B -> A to the already stored A would invent availability.
    path = tmp_path / "capture.db"
    old = final(211)
    append_bundle(path, old, NOW - timedelta(seconds=1))
    correction = deepcopy(old)
    correction["goals"]["home"] = 3
    target = scheduled(111)
    worker = _Capture(path, baseline_enabled=True)
    for offset, raw in enumerate((old, target, correction, old)):
        received(worker, raw, NOW + timedelta(seconds=offset))
    # Target was received at +1, so measure its real receipt bytes at that clock.
    _, _, target_cost = append_bundle(tmp_path / "exact-measure.db", target, NOW + timedelta(seconds=1))
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((target, old), max_new_payload_bytes=target_cost)

    assert set(worker.baseline_refs) == {111}
    assert worker.baseline_budget_excluded_ids == {211}
    assert worker.source_inserted_bytes == target_cost


def test_budget_exclusions_are_per_flush_native_attempts_not_missing_or_invalid_inputs(tmp_path):
    # A cumulative or blanket exclusion would misdiagnose unattempted inputs;
    # clearing the same set would mutate a publisher's frozen earlier snapshot.
    good, invalid, missing = final(211), final(212), final(213)
    invalid["unknown_provider_field"] = "unsupported native projection"
    csv = deepcopy(missing)
    csv["fixture"]["id"] = -214
    csv["challenge_source"] = "football-data-results-only"
    path = tmp_path / "capture.db"
    worker = _Capture(path, baseline_enabled=True)
    received(worker, good)
    received(worker, invalid)
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((good, invalid, missing, csv), max_new_payload_bytes=0)

    excluded_snapshot = worker.baseline_budget_excluded_ids
    assert excluded_snapshot == {211}
    assert not worker.baseline_refs
    assert not stored(path)
    _, _, cost = append_bundle(tmp_path / "measure.db", good, NOW)
    refs = worker.flush_baseline_receipts((good,), max_new_payload_bytes=cost)
    assert set(refs) == {digest(football_base_history_record(good))}
    assert all(refs.values())
    assert worker.baseline_budget_excluded_ids == set()
    assert excluded_snapshot == {211}
    assert worker.source_inserted_bytes == cost


def test_successful_target_revisions_keep_each_actual_receipt_clock(tmp_path):
    # A priority implementation that chooses only an old or latest revision
    # would discard causal material or manufacture a replacement receipt clock.
    first, history = scheduled(111), final(211)
    correction = deepcopy(first)
    correction["fixture"]["date"] = "2026-09-09T17:00:00+00:00"
    measured = tmp_path / "measure.db"
    _, _, first_cost = append_bundle(measured, first, NOW)
    _, _, correction_cost = append_bundle(measured, correction, NOW + timedelta(seconds=2))
    path = tmp_path / "capture.db"
    worker = _Capture(path, baseline_enabled=True)
    for offset, raw in enumerate((first, history, correction)):
        received(worker, raw, NOW + timedelta(seconds=offset))
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((correction, history),
                                       max_new_payload_bytes=first_cost + correction_cost)

    assert set(worker.baseline_refs) == {111}
    assert len(worker.baseline_refs[111]) == 2
    assert worker.baseline_budget_excluded_ids == {211}
    bases = [row for row in stored(path) if row["kind"] == "base_fixture"]
    assert {row["observed_at"] for row in bases} == {
        "2026-09-09T09:00:00.000000Z", "2026-09-09T09:00:02.000000Z",
    }
    assert all(row["event_key"] == "api-football:football:111" for row in bases)


def test_nonnative_scheduled_scope_cannot_grant_a_final_target_priority(tmp_path):
    # A positive local CSV ID colliding with a real native ID is not authority
    # to reorder that native final ahead of an earlier received native final.
    earlier, later = final(212), final(211)
    local_target = scheduled(211)
    local_target["challenge_source"] = "football-data-results-only"
    _, _, budget = append_bundle(tmp_path / "measure.db", earlier, NOW)
    path = tmp_path / "capture.db"
    worker = _Capture(path, baseline_enabled=True)
    received(worker, earlier)
    received(worker, later)
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((earlier, later, local_target), max_new_payload_bytes=budget)

    assert set(worker.baseline_refs) == {212}
    assert worker.baseline_budget_excluded_ids == {211}
