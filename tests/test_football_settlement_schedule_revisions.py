"""A frozen football schedule revision needs actual native result identity."""
from dataclasses import replace
from datetime import timedelta

import pytest

from riskobet_domain import canonical_input_hash
from riskobet_settlement import EventStatus, FootballResult
from riskobet_settlement_automation import FootballFixtureIdentity, ObservedResult, run_riskobet_settlements
from test_riskobet_settlement_automation import MODELED, NOW, START, _published_run, _store, _terminal_rows


def revised_runs(tmp_path):
    store = _store(tmp_path)
    first = _published_run(store)
    snapshot = replace(first.snapshots[0], starts_at=START + timedelta(minutes=30),
        modeled_at=MODELED + timedelta(minutes=10), input_cutoff_at=MODELED + timedelta(minutes=9),
        input_hash=canonical_input_hash({"fixture": 77, "schedule_revision": 2}))
    candidate = replace(first.candidates[0], snapshot_id=snapshot.snapshot_id,
        starts_at=snapshot.starts_at, market_key="underdog_team_over_0_5_90_minutes",
        market_label="underdog_team_over_0_5_90_minutes",
        settlement_contract="riskobet-settlement-v1:football:underdog_team_over_0_5_90_minutes:away")
    revised = replace(first, snapshots=(snapshot,), candidates=(candidate,),
        started_at=MODELED + timedelta(minutes=10), completed_at=MODELED + timedelta(minutes=11))
    store.append_run(revised)
    store.publish_latest(revised.run_id)
    return store, first, revised


class Provider:
    def __init__(self, *, date=None, names=("Favorite", "Underdog"), fixture_id=77):
        self.calls = []
        self.item = {"fixture": {"id": fixture_id, "date": date, "status": {"short": "FT"}},
            "teams": {"home": {"id": 10, "name": names[0]}, "away": {"id": 20, "name": names[1]}},
            "goals": {"home": 1, "away": 2}}

    def details_by_fixture(self, ids):
        self.calls.append(ids)
        return {77: self.item}


def test_moved_fixture_is_settled_once_with_native_pair_and_frozen_schedule(tmp_path):
    store, first, revised = revised_runs(tmp_path)
    frozen = [(r.snapshot_id, r.input_hash, r.starts_at) for r in (first.snapshots[0], revised.snapshots[0])]
    provider = Provider(date=revised.snapshots[0].starts_at.isoformat())
    result = run_riskobet_settlements(store=store, now=NOW, football_provider=provider)
    assert result.errors == ()
    assert result.terminal_settlements == 2 and result.unresolved_candidates == 0
    assert provider.calls == [[77]]
    assert len(_terminal_rows(store)) == 2
    for run in (first, revised):
        saved = store.load_run(run.run_id)["snapshots"][0]
        assert (saved["snapshot_id"], saved["input_hash"]) == (run.snapshots[0].snapshot_id, run.snapshots[0].input_hash)
    assert frozen == [(r.snapshot_id, r.input_hash, r.starts_at) for r in (first.snapshots[0], revised.snapshots[0])]
    again = run_riskobet_settlements(store=store, now=NOW, football_provider=provider)
    assert again.terminal_settlements == 0 and provider.calls == [[77]]


@pytest.mark.parametrize("change", ["missing_date", "unfrozen_date", "wrong_pair", "reversed_pair", "wrong_id", "missing_team"])
def test_moved_fixture_without_matching_native_identity_remains_unsettled(tmp_path, change):
    store, _, revised = revised_runs(tmp_path)
    provider = Provider(date=revised.snapshots[0].starts_at.isoformat())
    if change == "missing_date": provider.item["fixture"].pop("date")
    elif change == "unfrozen_date": provider.item["fixture"]["date"] = (START + timedelta(days=1)).isoformat()
    elif change == "wrong_pair": provider.item["teams"]["away"]["name"] = "Replacement"
    elif change == "reversed_pair": provider.item["teams"]["home"], provider.item["teams"]["away"] = provider.item["teams"]["away"], provider.item["teams"]["home"]
    elif change == "wrong_id": provider.item["fixture"]["id"] = 88
    else: provider.item["teams"].pop("away")
    result = run_riskobet_settlements(store=store, now=NOW, football_provider=provider)
    assert result.terminal_settlements == 0 and result.unresolved_candidates == 2
    assert _terminal_rows(store) == []
    assert "football:event_snapshot_ambiguous" not in result.errors
    assert any(code in result.errors for code in ("football:provider_identity_mismatch", "football:native_identity_unproven", "football:schedule_revision_unresolved"))


def test_custom_result_loader_cannot_bypass_moved_fixture_identity_proof(tmp_path):
    store, _, _ = revised_runs(tmp_path)
    calls = []
    def loader(requests, observed):
        calls.append(requests)
        return (ObservedResult("football", requests[0].event_key, observed,
            FootballResult(EventStatus.FINAL, 1, 2), "api-football:fixture:77:FT"),)
    result = run_riskobet_settlements(store=store, now=NOW, result_loaders={"football": loader})
    assert len(calls) == 1 and calls[0][0].requires_native_identity
    assert result.errors == ("football:native_identity_unproven",)
    assert result.terminal_settlements == 0 and result.unresolved_candidates == 2
    assert _terminal_rows(store) == []


def test_result_before_revised_start_cannot_settle_later_candidate(tmp_path):
    store, _, _ = revised_runs(tmp_path)
    provider = Provider(date=START.isoformat())
    result = run_riskobet_settlements(store=store, now=START + timedelta(minutes=10), football_provider=provider)
    # The later candidate is not due at all; its frozen start is not rewritten.
    assert result.terminal_settlements == 1
    assert len(_terminal_rows(store)) == 1


@pytest.mark.parametrize("change", ["id", "pair", "reversed", "start", "naive_start"])
def test_injected_native_proof_is_checked_by_runner_not_only_provider(tmp_path, change):
    store, _, revised = revised_runs(tmp_path)
    identity = FootballFixtureIdentity(77, revised.snapshots[0].starts_at, "Favorite", "Underdog")
    if change == "id": identity = replace(identity, fixture_id=88)
    elif change == "pair": identity = replace(identity, away_name="Replacement")
    elif change == "reversed": identity = replace(identity, home_name="Underdog", away_name="Favorite")
    elif change == "start": identity = replace(identity, starts_at=START + timedelta(days=1))
    else: identity = replace(identity, starts_at=START.replace(tzinfo=None))
    def loader(requests, observed):
        return (ObservedResult("football", requests[0].event_key, observed,
            FootballResult(EventStatus.FINAL, 1, 2), "api-football:fixture:77:FT", identity),)
    result = run_riskobet_settlements(store=store, now=NOW, result_loaders={"football": loader})
    assert result.terminal_settlements == 0 and result.unresolved_candidates == 2
    assert result.errors == (("football:provider_identity_mismatch",) if change in {"id", "pair", "reversed"}
        else ("football:schedule_revision_unresolved",))
    assert _terminal_rows(store) == []


def test_legacy_start_result_cannot_score_a_model_built_after_actual_kickoff(tmp_path):
    store, first, revised = revised_runs(tmp_path)
    snapshot = replace(revised.snapshots[0], modeled_at=START + timedelta(minutes=15),
        input_cutoff_at=START + timedelta(minutes=14), input_hash=canonical_input_hash({"revision": 3}))
    third = replace(revised, snapshots=(snapshot,),
        candidates=(replace(revised.candidates[0], snapshot_id=snapshot.snapshot_id),),
        started_at=START + timedelta(minutes=15), completed_at=START + timedelta(minutes=16))
    store.append_run(third)
    store.publish_latest(third.run_id)
    result = run_riskobet_settlements(store=store, now=NOW, football_provider=Provider(date=START.isoformat()))
    assert result.terminal_settlements == 1 and result.unresolved_candidates == 1
    assert result.errors == ("football:schedule_revision_unresolved",)
    assert len(_terminal_rows(store)) == 1


@pytest.mark.parametrize("change", ["observed_before_native_start", "wrong_source_id"])
def test_native_identity_proof_also_binds_source_and_actual_result_clock(tmp_path, change):
    store, _, revised = revised_runs(tmp_path)
    identity = FootballFixtureIdentity(77, revised.snapshots[0].starts_at, "Favorite", "Underdog")
    def loader(requests, observed):
        return (ObservedResult("football", requests[0].event_key,
            START + timedelta(minutes=10) if change == "observed_before_native_start" else observed,
            FootballResult(EventStatus.FINAL, 1, 2),
            "api-football:fixture:88:FT" if change == "wrong_source_id" else "api-football:fixture:77:FT", identity),)
    result = run_riskobet_settlements(store=store, now=NOW, result_loaders={"football": loader})
    assert result.terminal_settlements == 0 and result.unresolved_candidates == 2
    assert result.errors == (("football:result_identity_or_time_invalid",)
        if change == "observed_before_native_start" else ("football:provider_identity_mismatch",))
