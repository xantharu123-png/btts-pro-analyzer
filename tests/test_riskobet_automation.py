from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from riskobet_automation import (
    SPORT_ORDER,
    RiskSourceBatch,
    load_latest_riskobet,
    run_riskobet,
)
from riskobet_domain import (
    ContextState,
    EvidenceStage,
    EventModelSnapshot,
    RiskCandidate,
    RiskRunSnapshot,
    RunStatus,
    canonical_input_hash,
    stable_event_key,
)
from riskobet_store import RiskBetStore


NOW = datetime(2030, 6, 4, 10, tzinfo=timezone.utc)


def _event(sport, number=1, *, probability=0.31, markets=1):
    event_key = stable_event_key(sport, "test-provider", f"{sport}-{number}")
    snapshot = EventModelSnapshot(
        event_key=event_key,
        sport=sport,
        competition=f"{sport} test",
        event_label=f"Underdog {number} vs Favorite {number}",
        starts_at=NOW + timedelta(hours=6, minutes=number),
        modeled_at=NOW,
        input_cutoff_at=NOW - timedelta(minutes=1),
        model_version=f"{sport}-risk-v1",
        input_hash=canonical_input_hash(
            {"sport": sport, "event": number, "probability": probability}
        ),
        missing_core_data=("historical core sample",) if probability is None else (),
    )
    candidates = tuple(
        RiskCandidate(
            snapshot_id=snapshot.snapshot_id,
            event_key=snapshot.event_key,
            sport=sport,
            competition=snapshot.competition,
            event_label=snapshot.event_label,
            starts_at=snapshot.starts_at,
            market_key=f"underdog_scenario_{index}",
            market_label=f"Außenseiter-Szenario {index}",
            selection_key=f"underdog_{index}",
            selection_label=f"Underdog {number} Szenario {index}",
            model_probability=probability,
            cautious_probability=(
                None if probability is None else max(0.0, probability - index / 100)
            ),
            stage=EvidenceStage.RESEARCH,
            context_state=(
                ContextState.OPEN if probability is None else ContextState.FRESH
            ),
            policy_version="riskobet-policy-v1",
            pros=("Messbarer sportlicher Upside-Faktor",),
            cons=("Der Favorit bleibt nach Basismodell stärker",),
            missing_core_data=(
                ("historical core sample",) if probability is None else ()
            ),
        )
        for index in range(1, markets + 1)
    )
    return RiskSourceBatch(sport=sport, snapshots=(snapshot,), candidates=candidates)


def _store(tmp_path):
    return RiskBetStore(
        tmp_path / "riskobet.db",
        tmp_path / "riskobet_latest.json",
    )


def _field_names(value):
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_field_names(item))
        return result
    if isinstance(value, list):
        result = set()
        for item in value:
            result.update(_field_names(item))
        return result
    return set()


def test_run_publishes_atomically_and_is_idempotent(tmp_path):
    store = _store(tmp_path)
    source = _event("football")

    first = run_riskobet(football_source=source, store=store, now=NOW)
    second = run_riskobet(football_source=source, store=store, now=NOW)

    assert first.run_id == second.run_id
    payload = json.loads(store.latest_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == first.run_id
    assert payload["status"] == "COMPLETE"
    assert not list(tmp_path.glob("*.tmp"))
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_all_six_sports_are_aggregated_without_provider_calls(tmp_path):
    store = _store(tmp_path)
    sources = {f"{sport}_source": _event(sport) for sport in SPORT_ORDER}

    run = run_riskobet(store=store, now=NOW, **sources)

    assert run.status is RunStatus.COMPLETE
    assert {snapshot.sport for snapshot in run.snapshots} == set(SPORT_ORDER)
    assert {candidate.sport for candidate in run.candidates} == set(SPORT_ORDER)


def test_six_successfully_empty_sources_are_each_called_once_and_complete(tmp_path):
    store = _store(tmp_path)
    calls = {sport: 0 for sport in SPORT_ORDER}

    def source(sport):
        def load():
            calls[sport] += 1
            return RiskSourceBatch(sport=sport)

        return load

    run = run_riskobet(
        store=store,
        now=NOW,
        **{f"{sport}_source": source(sport) for sport in SPORT_ORDER},
    )

    assert run.status is RunStatus.COMPLETE
    assert run.snapshots == ()
    assert run.candidates == ()
    assert calls == {sport: 1 for sport in SPORT_ORDER}


def test_adapter_result_sequences_are_accepted(tmp_path):
    class AdapterResult:
        def __init__(self, batch):
            self.snapshot = batch.snapshots[0]
            self.candidates = batch.candidates

    store = _store(tmp_path)
    result = AdapterResult(_event("tennis"))

    run = run_riskobet(tennis_source=(result,), store=store, now=NOW)

    assert len(run.snapshots) == 1
    assert run.candidates[0].sport == "tennis"


def test_source_isolation_keeps_healthy_sport_when_another_returns_wrong_sport(
    tmp_path,
):
    store = _store(tmp_path)

    run = run_riskobet(
        football_source=_event("football"),
        tennis_source=lambda: _event("football", number=2),
        store=store,
        now=NOW,
    )

    assert run.status is RunStatus.PARTIAL
    assert {candidate.sport for candidate in run.candidates} == {"football"}
    assert any(error.startswith("tennis:") for error in run.errors)


def test_failed_partial_source_never_erases_unrelated_candidates(tmp_path):
    store = _store(tmp_path)

    def broken():
        raise RuntimeError("temporary tennis database failure")

    run = run_riskobet(
        football_source=_event("football"),
        tennis_source=broken,
        esports_source=_event("esports"),
        store=store,
        now=NOW,
    )

    assert run.status is RunStatus.PARTIAL
    assert {candidate.sport for candidate in run.candidates} == {
        "football",
        "esports",
    }
    published = load_latest_riskobet(store=store)
    assert published is not None
    assert {item["sport"] for item in published["candidates"]} == {
        "football",
        "esports",
    }


def test_same_zurich_day_reuses_research_when_refresh_not_due_or_fails(tmp_path):
    store = _store(tmp_path)
    original = run_riskobet(
        basketball_source=_event("basketball", probability=None),
        ice_hockey_source=_event("ice_hockey", probability=None),
        store=store,
        now=NOW,
    )
    original_ids = {candidate.candidate_id for candidate in original.candidates}

    def failed_cricket_refresh():
        raise RuntimeError("provider unavailable")

    second = run_riskobet(
        football_source=_event("football", number=9),
        cricket_source=failed_cricket_refresh,
        source_due={"basketball": False, "ice_hockey": False},
        store=store,
        now=NOW + timedelta(hours=1),
    )

    assert second.status is RunStatus.PARTIAL
    assert original_ids <= {candidate.candidate_id for candidate in second.candidates}
    assert {
        candidate.sport
        for candidate in second.candidates
        if candidate.candidate_id in original_ids
    } == {"basketball", "ice_hockey"}
    assert all(
        candidate.model_probability is None
        for candidate in second.candidates
        if candidate.sport in {"basketball", "ice_hockey"}
    )


def test_source_failure_reuses_same_day_research_for_that_sport(tmp_path):
    store = _store(tmp_path)
    first = run_riskobet(
        cricket_source=_event("cricket", probability=None),
        store=store,
        now=NOW,
    )

    def failed():
        raise RuntimeError("history refresh failed")

    second = run_riskobet(
        cricket_source=failed,
        store=store,
        now=NOW + timedelta(minutes=30),
    )

    assert second.status is RunStatus.PARTIAL
    assert second.candidates == first.candidates
    assert any(error.startswith("cricket:") for error in second.errors)


def test_due_but_missing_source_is_partial_and_reuses_only_fresh_prior(tmp_path):
    store = _store(tmp_path)
    first = run_riskobet(
        cricket_source=_event("cricket", probability=None),
        store=store,
        now=NOW,
    )

    second = run_riskobet(
        football_source=_event("football", number=500),
        source_due={"cricket": True},
        store=store,
        now=NOW + timedelta(minutes=30),
    )

    assert second.status is RunStatus.PARTIAL
    assert first.candidates[0] in second.candidates
    assert "cricket: source_unavailable" in second.errors


def test_probability_ranking_is_price_free_and_max_two_per_event(tmp_path):
    store = _store(tmp_path)
    source = _event("football", markets=3)

    run = run_riskobet(football_source=source, store=store, now=NOW)
    payload = store.read_latest()

    assert len(run.candidates) == 2
    assert payload is not None
    forbidden = ("odd", "quote", "price", "bookmaker", "minimum")
    fields = {field.casefold() for field in _field_names(payload)}
    assert not any(token in field for field in fields for token in forbidden)


def test_equal_time_event_revisions_fail_closed_in_aggregation(tmp_path):
    first = _event("football", probability=0.31)
    second = _event("football", probability=0.32)
    assert first.snapshots[0].event_key == second.snapshots[0].event_key
    assert first.snapshots[0].snapshot_id != second.snapshots[0].snapshot_id
    source = RiskSourceBatch(
        sport="football",
        snapshots=(first.snapshots[0], second.snapshots[0]),
        candidates=(first.candidates[0], second.candidates[0]),
    )

    with pytest.raises(ValueError, match="ambiguous equal-time"):
        run_riskobet(
            football_source=source,
            store=_store(tmp_path),
            now=NOW,
        )


def test_all_attempted_sources_failing_is_failed_not_empty_complete(tmp_path):
    store = _store(tmp_path)

    def failed():
        raise RuntimeError("offline")

    run = run_riskobet(
        source_loaders={sport: failed for sport in SPORT_ORDER},
        store=store,
        now=NOW,
        reuse_same_day_research=False,
    )

    assert run.status is RunStatus.FAILED
    assert not run.candidates
    assert len(run.errors) == len(SPORT_ORDER)


def test_total_failure_keeps_previous_published_snapshot(tmp_path):
    store = _store(tmp_path)
    healthy = run_riskobet(
        football_source=_event("football"),
        store=store,
        now=NOW,
    )

    def failed():
        raise RuntimeError("offline")

    failed_run = run_riskobet(
        source_loaders={sport: failed for sport in SPORT_ORDER},
        store=store,
        now=NOW + timedelta(minutes=10),
        reuse_same_day_research=False,
    )

    assert failed_run.status is RunStatus.FAILED
    assert store.read_latest()["run_id"] == healthy.run_id


def test_latest_helper_rehydrates_and_page_read_path_is_provider_free(tmp_path):
    store = _store(tmp_path)
    run = run_riskobet(football_source=_event("football"), store=store, now=NOW)

    loaded = load_latest_riskobet(store=store, rehydrate=True)

    assert isinstance(loaded, RiskRunSnapshot)
    assert loaded == run


def test_latest_helper_recovers_missing_json_read_only_from_verified_database(
    tmp_path,
):
    store = _store(tmp_path)
    run = run_riskobet(football_source=_event("football"), store=store, now=NOW)
    store.latest_path.unlink()
    before = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in tmp_path.iterdir()
    }

    payload = load_latest_riskobet(store=store)
    rehydrated = load_latest_riskobet(store=store, rehydrate=True)

    after = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in tmp_path.iterdir()
    }
    assert payload["run_id"] == run.run_id
    assert rehydrated == run
    assert not store.latest_path.exists()
    assert after == before


def test_zero_source_wakeup_is_noop_and_never_replaces_latest(tmp_path):
    store = _store(tmp_path)
    original = run_riskobet(
        football_source=_event("football"),
        store=store,
        now=NOW,
    )
    before = store.latest_path.read_bytes()

    repeated = run_riskobet(store=store, now=NOW + timedelta(minutes=30))

    assert repeated.run_id == original.run_id
    assert store.latest_path.read_bytes() == before
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_zero_source_without_prior_fails_without_publishing_latest(tmp_path):
    store = _store(tmp_path)

    run = run_riskobet(store=store, now=NOW)

    assert run.status is RunStatus.FAILED
    assert run.errors == ("automation: no_source_configured",)
    assert not store.latest_path.exists()


def test_failed_source_reuses_only_still_upcoming_same_day_research(tmp_path):
    store = _store(tmp_path)
    original = run_riskobet(
        basketball_source=_event("basketball", number=500, probability=None),
        cricket_source=_event("cricket", probability=None),
        store=store,
        now=NOW,
    )
    assert {candidate.sport for candidate in original.candidates} == {
        "basketball",
        "cricket",
    }

    def failed():
        raise RuntimeError("private provider detail")

    later = NOW + timedelta(hours=7)
    run = run_riskobet(
        football_source=_event("football", number=600),
        cricket_source=failed,
        source_due={"basketball": False},
        store=store,
        now=later,
    )

    assert run.status is RunStatus.PARTIAL
    assert "basketball" in {candidate.sport for candidate in run.candidates}
    assert "cricket" not in {candidate.sport for candidate in run.candidates}


def test_public_source_errors_are_sanitized_in_run_and_latest(tmp_path):
    store = _store(tmp_path)
    secret = "provider-secret-token-123"

    def broken():
        raise RuntimeError(secret)

    run = run_riskobet(
        football_source=_event("football"),
        tennis_source=broken,
        store=store,
        now=NOW,
    )

    assert run.errors == ("tennis: source_failed:RuntimeError",)
    assert secret not in json.dumps(run.to_dict())
    assert secret not in store.latest_path.read_text(encoding="utf-8")
