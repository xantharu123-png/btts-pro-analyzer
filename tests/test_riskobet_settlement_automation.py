from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

import pytest
import esports_shadow as esports_shadow_module

from esports_shadow import EsportsShadowLog
from riskobet_candidates import adapt_esports_shadow
from riskobet_domain import (
    ContextState,
    EvidenceStage,
    EventModelSnapshot,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
    RiskRunSnapshot,
    RunStatus,
    canonical_input_hash,
    stable_event_key,
)
from riskobet_settlement import (
    EventStatus,
    FootballResult,
    SettlementResult,
    SettlementStatus,
    SettlementInputError,
    TennisResult,
    parse_settlement_contract,
)
from riskobet_settlement_automation import (
    MAX_SHADOW_ROWS_PER_SOURCE,
    ObservedResult,
    ResultLoadBatch,
    SettlementRequest,
    esports_result_loader,
    football_result_loader,
    run_riskobet_settlements,
    tennis_result_loader,
)
from riskobet_store import RiskBetStore


MODELED = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = datetime(2030, 1, 1, 18, tzinfo=timezone.utc)
NOW = datetime(2030, 1, 1, 21, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> RiskBetStore:
    return RiskBetStore(tmp_path / "riskobet.db", tmp_path / "riskobet_latest.json")


def _published_run(
    store: RiskBetStore,
    *,
    sport: str = "football",
    provider: str = "api-football",
    provider_id: str = "77",
    markets: tuple[tuple[str, str], ...] = (("result_90_minutes", "away"),),
    factors: tuple[FactorEvidence, ...] | None = None,
    stage: EvidenceStage = EvidenceStage.SHADOW,
    source_row_id: int | None = None,
    run_offset_minutes: int = 0,
) -> RiskRunSnapshot:
    event_key = stable_event_key(sport, provider, provider_id)
    if factors is None and sport == "football":
        factors = (
            FactorEvidence(
                factor_key=f"football_fixture_id:{provider_id}",
                summary="Frozen provider identity",
                source="api-football.fixtures",
                observed_at=MODELED - timedelta(minutes=1),
                imported_at=MODELED,
                fresh_until=START,
                role=FactorRole.DISPLAY_ONLY,
            ),
        )
    elif factors is None and sport == "tennis":
        resolved_row_id = source_row_id
        if resolved_row_id is None:
            suffix = provider_id.rsplit("-", 1)[-1]
            resolved_row_id = int(suffix) if suffix.isdigit() else 3
        factors = (
            FactorEvidence(
                factor_key=f"tennis_prediction_id:{resolved_row_id}",
                summary="Frozen tennis source identity",
                source="tennis_shadow.predictions",
                observed_at=MODELED - timedelta(minutes=1),
                imported_at=MODELED,
                fresh_until=START,
                role=FactorRole.DISPLAY_ONLY,
            ),
        )
    elif factors is None and sport == "esports":
        factors = tuple(
            FactorEvidence(
                factor_key=key,
                summary="Frozen e-sport source identity",
                source="esports_shadow_predictions",
                observed_at=MODELED - timedelta(minutes=1),
                imported_at=MODELED,
                fresh_until=START,
                role=FactorRole.DISPLAY_ONLY,
            )
            for key in (
                f"esports_match_id:{int(provider_id)}",
                "esports_team1_id:999",
                "esports_team2_id:1000",
            )
        )
    event_label = "A vs B" if sport == "tennis" else "Favorite vs Underdog"
    snapshot = EventModelSnapshot(
        event_key=event_key,
        sport=sport,
        competition="Test",
        event_label=event_label,
        starts_at=START,
        modeled_at=MODELED,
        input_cutoff_at=MODELED - timedelta(minutes=1),
        model_version=f"{sport}-test-v1",
        input_hash=canonical_input_hash({"sport": sport, "provider_id": provider_id}),
        factors=tuple(factors or ()),
    )
    candidates = tuple(
        RiskCandidate(
            snapshot_id=snapshot.snapshot_id,
            event_key=event_key,
            sport=sport,
            competition="Test",
            event_label=event_label,
            starts_at=START,
            market_key=market,
            market_label=market,
            selection_key=selection,
            selection_label=selection,
            model_probability=0.30,
            cautious_probability=0.25,
            stage=stage,
            context_state=ContextState.PARTIAL,
            policy_version="riskobet-policy-test-v1",
            pros=("Causal model factor",),
            cons=("Favorite remains stronger",),
            settlement_contract=(
                f"riskobet-settlement-v1:{sport}:{market}:{selection}"
                if stage is not EvidenceStage.RESEARCH
                else None
            ),
        )
        for market, selection in markets
    )
    run = RiskRunSnapshot(
        started_at=MODELED + timedelta(minutes=run_offset_minutes),
        completed_at=MODELED + timedelta(minutes=run_offset_minutes + 1),
        status=RunStatus.COMPLETE,
        snapshots=(snapshot,),
        candidates=candidates,
    )
    store.append_run(run)
    store.publish_latest(run.run_id)
    return run


def _terminal_rows(store: RiskBetStore) -> list[tuple[str, str, str]]:
    with sqlite3.connect(store.db_path) as connection:
        return connection.execute(
            "SELECT candidate_id, result, detail_json FROM settlements ORDER BY candidate_id"
        ).fetchall()


def test_two_markets_use_one_event_call_and_publish_terminal_results(tmp_path: Path):
    store = _store(tmp_path)
    run = _published_run(
        store,
        markets=(
            ("result_90_minutes", "away"),
            ("underdog_team_over_0_5_90_minutes", "away"),
        ),
    )
    calls: list[tuple[SettlementRequest, ...]] = []

    def loader(requests, _now):
        calls.append(requests)
        return (
            ObservedResult(
                sport="football",
                event_key=requests[0].event_key,
                observed_at=NOW - timedelta(minutes=10),
                result=FootballResult(EventStatus.FINAL, 1, 2),
                source_result_id="api-football:fixture:77:FT",
            ),
        )

    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"football": loader},
    )

    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert calls[0][0].candidate_ids == tuple(
        sorted(candidate.candidate_id for candidate in run.candidates)
    )
    assert summary.terminal_settlements == 2
    assert summary.unresolved_candidates == 0
    assert summary.published is True
    rows = _terminal_rows(store)
    assert [row[1] for row in rows] == ["WON", "WON"]
    detail = json.loads(rows[0][2])
    assert detail["context"]["canonical_result"] == {
        "away_goals_90": 2,
        "home_goals_90": 1,
        "away_goals_after_extra_time": None,
        "home_goals_after_extra_time": None,
        "status": "final",
        "type": "FootballResult",
        "winner_after_penalties": None,
    }
    assert "quote" not in rows[0][2].casefold()
    assert store.read_latest()["candidates"][0]["settlements"]


def test_terminal_second_run_is_idempotent_and_does_not_call_provider(tmp_path: Path):
    store = _store(tmp_path)
    run = _published_run(store)
    first_calls = 0

    def first_loader(requests, _now):
        nonlocal first_calls
        first_calls += 1
        return (
            ObservedResult(
                "football",
                requests[0].event_key,
                NOW - timedelta(minutes=5),
                FootballResult(EventStatus.FINAL, 2, 0),
                "api-football:fixture:77:FT",
            ),
        )

    first = run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"football": first_loader}
    )

    def must_not_run(_requests, _now):
        raise AssertionError("terminal candidate was queried again")

    second = run_riskobet_settlements(
        store=store, now=NOW + timedelta(minutes=30),
        result_loaders={"football": must_not_run},
    )

    assert first_calls == 1
    assert first.terminal_settlements == 1
    assert second.due_candidates == 0
    assert second.terminal_settlements == 0
    assert len(_terminal_rows(store)) == 1
    assert store.read_latest()["run_id"] == run.run_id


def test_ambiguous_candidate_is_unresolved_without_blocking_settlement_runner(
    tmp_path: Path,
):
    store = _store(tmp_path)
    first_run = _published_run(store)
    first_snapshot = first_run.snapshots[0]
    first_candidate = first_run.candidates[0]
    conflicting_snapshot = replace(
        first_snapshot,
        input_hash=canonical_input_hash({"provider_id": "77", "revision": 2}),
    )
    conflicting_candidate = replace(
        first_candidate,
        snapshot_id=conflicting_snapshot.snapshot_id,
    )
    conflicting_run = RiskRunSnapshot(
        started_at=MODELED + timedelta(minutes=2),
        completed_at=MODELED + timedelta(minutes=3),
        status=RunStatus.COMPLETE,
        snapshots=(conflicting_snapshot,),
        candidates=(conflicting_candidate,),
    )
    store.append_run(conflicting_run)
    store.publish_latest(conflicting_run.run_id)

    def must_not_run(_requests, _now):
        raise AssertionError("ambiguous candidate must not reach a provider")

    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"football": must_not_run},
    )

    assert summary.due_candidates == 1
    assert summary.due_events == 0
    assert summary.unresolved_candidates == 1
    assert summary.terminal_settlements == 0
    assert summary.errors == ("automation:ambiguous_settlement_revisions",)
    assert _terminal_rows(store) == []


def test_crash_after_database_append_is_healed_without_provider_retry(tmp_path: Path):
    store = _store(tmp_path)
    run = _published_run(store)
    candidate = run.candidates[0]
    store.append_terminal_settlement(
        candidate_id=candidate.candidate_id,
        snapshot_id=candidate.snapshot_id,
        result=SettlementResult(
            SettlementStatus.LOSS,
            "football_result_90_minutes",
        ),
        settled_at=NOW - timedelta(minutes=5),
        settlement_version=candidate.settlement_contract,
        detail={
            "event_key": candidate.event_key,
            "source_result_id": "api-football:fixture:77:FT",
            "result_observed_at": (NOW - timedelta(minutes=5)).isoformat(),
            "canonical_result": {
                "type": "FootballResult",
                "status": "final",
                "home_goals_90": 1,
                "away_goals_90": 0,
            },
        },
    )
    assert store.read_latest()["candidates"][0]["settlements"] == []

    def forbidden(_requests, _now):
        raise AssertionError("terminal candidate was queried again")

    summary = run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"football": forbidden}
    )

    assert summary.due_candidates == 0
    assert summary.terminal_settlements == 0
    assert summary.published is True
    assert store.read_latest()["candidates"][0]["settlements"][0]["result"] == "LOST"


def test_store_wide_open_candidate_survives_replacement_of_latest_run(tmp_path: Path):
    store = _store(tmp_path)
    old_run = _published_run(store, provider_id="77")
    newest_run = _published_run(
        store,
        provider_id="88",
        run_offset_minutes=1,
    )
    assert store.read_latest()["run_id"] == newest_run.run_id

    def loader(requests, _now):
        old_event = stable_event_key("football", "api-football", "77")
        assert {request.event_key for request in requests} == {
            old_event,
            stable_event_key("football", "api-football", "88"),
        }
        return (
            ObservedResult(
                "football",
                old_event,
                NOW - timedelta(minutes=5),
                FootballResult(EventStatus.FINAL, 0, 1),
                "api-football:fixture:77:FT",
            ),
        )

    summary = run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"football": loader}
    )

    assert summary.terminal_settlements == 1
    assert summary.unresolved_candidates == 1
    assert _terminal_rows(store)[0][0] == old_run.candidates[0].candidate_id
    assert store.read_latest()["run_id"] == newest_run.run_id


def test_unresolved_poll_never_writes_database_rows(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(store)
    calls = 0

    def loader(requests, observed):
        nonlocal calls
        calls += 1
        return (
            ObservedResult(
                "football",
                requests[0].event_key,
                observed,
                FootballResult(EventStatus.LIVE, 0, 0),
                "api-football:fixture:77:LIVE",
            ),
        )

    first = run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"football": loader}
    )
    second = run_riskobet_settlements(
        store=store, now=NOW + timedelta(minutes=5),
        result_loaders={"football": loader},
    )

    assert calls == 2
    assert first.unresolved_candidates == second.unresolved_candidates == 1
    assert _terminal_rows(store) == []
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 0


@pytest.mark.parametrize("bad_time", [START - timedelta(seconds=1), NOW + timedelta(seconds=1)])
def test_wrong_identity_or_noncausal_result_stays_open(tmp_path: Path, bad_time: datetime):
    store = _store(tmp_path)
    _published_run(store)

    def loader(requests, _now):
        return (
            ObservedResult(
                "football",
                requests[0].event_key,
                bad_time,
                FootballResult(EventStatus.FINAL, 0, 1),
                "provider:result:77",
            ),
            ObservedResult(
                "football",
                stable_event_key("football", "api-football", "999"),
                NOW,
                FootballResult(EventStatus.FINAL, 0, 1),
                "provider:result:999",
            ),
        )

    summary = run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"football": loader}
    )

    assert summary.terminal_settlements == 0
    assert summary.unresolved_candidates == 1
    assert "football:result_identity_or_time_invalid" in summary.errors
    assert _terminal_rows(store) == []


def test_three_duplicate_results_keep_event_ambiguous_and_open(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(store)

    def loader(requests, _now):
        observation = ObservedResult(
            "football",
            requests[0].event_key,
            NOW - timedelta(minutes=5),
            FootballResult(EventStatus.FINAL, 0, 1),
            "api-football:fixture:77:FT",
        )
        return (observation, observation, observation)

    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"football": loader},
    )

    assert summary.terminal_settlements == 0
    assert summary.unresolved_candidates == 1
    assert "football:duplicate_event_result" in summary.errors
    assert _terminal_rows(store) == []


def test_bounded_result_poll_rotates_across_all_open_events(tmp_path: Path):
    store = _store(tmp_path)
    for provider_id in ("70", "71", "72"):
        _published_run(store, provider_id=provider_id)
    seen: list[str] = []

    def loader(requests, _now):
        assert len(requests) == 1
        seen.append(requests[0].event_key)
        return ResultLoadBatch()

    for index in range(3):
        summary = run_riskobet_settlements(
            store=store,
            now=NOW + timedelta(minutes=30 * index),
            result_loaders={"football": loader},
            max_events_per_sport=1,
        )
        assert summary.due_candidates == 3
        assert summary.due_events == 1
        assert summary.unresolved_candidates == 3

    assert len(set(seen)) == 3


def test_provider_error_is_isolated_and_secret_text_is_not_exposed(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(store)

    def broken(_requests, _now):
        raise RuntimeError("secret-provider-token")

    summary = run_riskobet_settlements(
        store=store, now=NOW, result_loaders={"football": broken}
    )

    encoded = json.dumps(summary.to_dict())
    assert summary.unresolved_candidates == 1
    assert summary.errors == ("football:result_source_failed_runtimeerror",)
    assert "secret-provider-token" not in encoded
    assert _terminal_rows(store) == []


def test_default_football_loader_is_bounded_and_rejects_wrong_fixture(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(store)

    class Provider:
        def __init__(self):
            self.calls = []

        def details_by_fixture(self, fixture_ids):
            self.calls.append(fixture_ids)
            return {
                77: {
                    "fixture": {"id": 999, "status": {"short": "FT"}},
                    "goals": {"home": 0, "away": 1},
                }
            }

    provider = Provider()
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        football_provider=provider,
    )

    assert provider.calls == [[77]]
    assert summary.terminal_settlements == 0
    assert "football:provider_identity_mismatch" in summary.errors


def test_default_football_loader_settles_ft_but_not_aet(tmp_path: Path):
    class Provider:
        def __init__(self, status):
            self.status = status
            self.calls = 0

        def details_by_fixture(self, fixture_ids):
            self.calls += 1
            return {
                fixture_ids[0]: {
                    "fixture": {"id": fixture_ids[0], "status": {"short": self.status}},
                    "goals": {"home": 0, "away": 1},
                }
            }

    ft_store = RiskBetStore(tmp_path / "ft.db", tmp_path / "ft.json")
    _published_run(ft_store)
    ft = run_riskobet_settlements(store=ft_store, now=NOW, football_provider=Provider("FT"))
    assert ft.terminal_settlements == 1

    aet_store = RiskBetStore(tmp_path / "aet.db", tmp_path / "aet.json")
    _published_run(aet_store)
    aet_provider = Provider("AET")
    aet = run_riskobet_settlements(store=aet_store, now=NOW, football_provider=aet_provider)
    assert aet_provider.calls == 1
    assert aet.terminal_settlements == 0
    assert "football:regulation_score_unproven" in aet.errors


def test_tennis_existing_schema_without_result_clock_fails_open(tmp_path: Path):
    store = _store(tmp_path)
    run = _published_run(
        store,
        sport="tennis",
        provider="ESPN",
        provider_id="tennis-1",
        markets=(("match_winner", "away"),),
    )
    db = tmp_path / "tennis.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE predictions (id INTEGER PRIMARY KEY, settled INTEGER, "
            "player_a TEXT, player_b TEXT, provider_event_id TEXT, fixture_source TEXT, "
            "actual_winner TEXT, ret_flag INTEGER)"
        )
        connection.execute(
            "INSERT INTO predictions VALUES (1,1,'A','B','tennis-1','ESPN','B',0)"
        )
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"tennis": tennis_result_loader(db)},
    )
    assert summary.terminal_settlements == 0
    assert "tennis:result_observed_at_missing" in summary.errors
    assert run.candidates[0].event_key == stable_event_key("tennis", "ESPN", "tennis-1")


def test_tennis_exact_stable_key_and_proven_set_score_settle_two_markets(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(
        store,
        sport="tennis",
        provider="ESPN",
        provider_id="tennis-2",
        markets=(("match_winner", "away"), ("over_2_5_sets", "over")),
    )
    db = tmp_path / "tennis.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE predictions (id INTEGER PRIMARY KEY, settled INTEGER, "
            "player_a TEXT, player_b TEXT, provider_event_id TEXT, fixture_source TEXT, "
            "actual_winner TEXT, ret_flag INTEGER, settled_at TEXT, set_score TEXT, "
            "termination TEXT)"
        )
        connection.execute(
            "INSERT INTO predictions VALUES "
            "(2,1,'A','B','tennis-2','ESPN','B',0,?, '1:2','normal')",
            ((NOW - timedelta(minutes=15)).isoformat(),),
        )
        connection.executemany(
            "INSERT INTO predictions VALUES "
            "(?,1,'Noise A','Noise B',?,'ESPN','Noise A',0,?,'2:0','normal')",
            (
                (
                    1000 + index,
                    f"noise-{index}",
                    (NOW - timedelta(minutes=10)).isoformat(),
                )
                for index in range(MAX_SHADOW_ROWS_PER_SOURCE + 1)
            ),
        )
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"tennis": tennis_result_loader(db)},
    )
    assert summary.terminal_settlements == 2
    assert [row[1] for row in _terminal_rows(store)] == ["WON", "WON"]


def test_tennis_retirement_with_observation_time_voids_without_set_score(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(
        store,
        sport="tennis",
        provider="ESPN",
        provider_id="tennis-ret",
        markets=(("match_winner", "away"),),
    )
    db = tmp_path / "tennis.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE predictions (id INTEGER PRIMARY KEY, settled INTEGER, "
            "player_a TEXT, player_b TEXT, provider_event_id TEXT, fixture_source TEXT, "
            "actual_winner TEXT, ret_flag INTEGER, settled_at TEXT, termination TEXT)"
        )
        connection.execute(
            "INSERT INTO predictions VALUES "
            "(3,1,'A','B','tennis-ret','ESPN',NULL,1,?,'retirement')",
            ((NOW - timedelta(minutes=10)).isoformat(),),
        )
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"tennis": tennis_result_loader(db)},
    )
    assert summary.terminal_settlements == 1
    assert _terminal_rows(store)[0][1] == "VOID"


def test_esports_series_result_does_not_invent_map_score(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(
        store,
        sport="esports",
        provider="pandascore",
        provider_id="55",
        markets=(("series_winner", "away"), ("at_least_one_map", "away")),
    )
    db = tmp_path / "esports.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE esports_shadow_predictions (match_id INTEGER PRIMARY KEY, "
            "settled INTEGER, winner_team_id INTEGER, settled_at TEXT, "
            "selected_team_id INTEGER, selection TEXT, team1 TEXT, team2 TEXT, "
            "score1 INTEGER, score2 INTEGER, team1_id INTEGER, team2_id INTEGER, "
            "termination TEXT, final_score1 INTEGER, final_score2 INTEGER)"
        )
        # score1/score2 are the frozen prematch 0:0 and must not settle a map market.
        connection.execute(
            "INSERT INTO esports_shadow_predictions VALUES (55,1,999,?,999,'Favorite',"
            "'Favorite','Underdog',0,0,999,1000,'normal',NULL,NULL)",
            ((NOW - timedelta(minutes=5)).isoformat(),),
        )
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"esports": esports_result_loader(db)},
    )
    assert summary.terminal_settlements == 0
    assert summary.unresolved_candidates == 2
    assert _terminal_rows(store) == []


def test_esports_winner_without_explicit_termination_fails_open(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(
        store,
        sport="esports",
        provider="pandascore",
        provider_id="56",
        markets=(("series_winner", "away"),),
    )
    db = tmp_path / "esports.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE esports_shadow_predictions (match_id INTEGER PRIMARY KEY, "
            "settled INTEGER, winner_team_id INTEGER, settled_at TEXT, "
            "selected_team_id INTEGER, selection TEXT, team1 TEXT, team2 TEXT)"
        )
        connection.execute(
            "INSERT INTO esports_shadow_predictions VALUES "
            "(56,1,999,?,999,'Favorite','Favorite','Underdog')",
            ((NOW - timedelta(minutes=5)).isoformat(),),
        )

    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"esports": esports_result_loader(db)},
    )

    assert summary.terminal_settlements == 0
    assert "esports:termination_unproven" in summary.errors


def test_esports_exact_ids_and_old_result_survive_large_shadow_history(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(
        store,
        sport="esports",
        provider="pandascore",
        provider_id="55",
        markets=(("series_winner", "away"), ("at_least_one_map", "away")),
    )
    db = tmp_path / "esports-large.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE esports_shadow_predictions (match_id INTEGER PRIMARY KEY, "
            "settled INTEGER, winner_team_id INTEGER, settled_at TEXT, "
            "selected_team_id INTEGER, selection TEXT, team1 TEXT, team2 TEXT, "
            "team1_id INTEGER, team2_id INTEGER, termination TEXT, "
            "final_score1 INTEGER, final_score2 INTEGER)"
        )
        connection.execute(
            "INSERT INTO esports_shadow_predictions VALUES "
            "(55,1,1000,?,999,'Favorite','Favorite','Underdog',"
            "999,1000,'normal',1,2)",
            ((NOW - timedelta(minutes=15)).isoformat(),),
        )
        connection.executemany(
            "INSERT INTO esports_shadow_predictions VALUES "
            "(?,1,2000,?,2000,'Noise A','Noise A','Noise B',"
            "2000,2001,'normal',2,0)",
            (
                (
                    1000 + index,
                    (NOW - timedelta(minutes=5)).isoformat(),
                )
                for index in range(MAX_SHADOW_ROWS_PER_SOURCE + 1)
            ),
        )

    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"esports": esports_result_loader(db)},
    )

    assert summary.terminal_settlements == 2
    assert summary.unresolved_candidates == 0
    assert {row[1] for row in _terminal_rows(store)} == {"WON"}


def test_esports_explicit_cancel_voids_without_invented_map_score(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(
        store,
        sport="esports",
        provider="pandascore",
        provider_id="57",
        markets=(("series_winner", "away"),),
    )
    db = tmp_path / "esports.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE esports_shadow_predictions (match_id INTEGER PRIMARY KEY, "
            "settled INTEGER, winner_team_id INTEGER, settled_at TEXT, "
            "selected_team_id INTEGER, selection TEXT, team1 TEXT, team2 TEXT, "
            "team1_id INTEGER, team2_id INTEGER, termination TEXT, "
            "final_score1 INTEGER, final_score2 INTEGER)"
        )
        connection.execute(
            "INSERT INTO esports_shadow_predictions VALUES "
            "(57,1,NULL,?,999,'Favorite','Favorite','Underdog',"
            "999,1000,'cancelled',NULL,NULL)",
            ((NOW - timedelta(minutes=5)).isoformat(),),
        )
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"esports": esports_result_loader(db)},
    )
    assert summary.terminal_settlements == 1
    assert _terminal_rows(store)[0][1] == "VOID"


def test_real_esports_writer_adapter_and_default_loader_settle_end_to_end(
    tmp_path: Path,
    monkeypatch,
):
    class ControlledDateTime(datetime):
        current = MODELED

        @classmethod
        def now(cls, tz=None):
            value = cls.current
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    def history(team_id: int, opponent_id: int, wins: int, start_id: int):
        return [
            {
                "match_id": start_id + index,
                "begin_at": f"2029-12-{1 + index:02d}T10:00:00Z",
                "end_at": f"2029-12-{1 + index:02d}T12:00:00Z",
                "opponent_id": opponent_id,
                "won": index < wins,
                "number_of_games": 3,
            }
            for index in range(20)
        ]

    monkeypatch.setattr(esports_shadow_module, "datetime", ControlledDateTime)
    db = tmp_path / "real-esports.db"
    log = EsportsShadowLog(db)
    match = {
        "id": 55,
        "game": "CS2",
        "team1": "Alpha",
        "team2": "Beta",
        "team1_id": 7,
        "team2_id": 8,
        "team1_score": 0,
        "team2_score": 0,
        "series_type": 3,
        "status": "upcoming",
        "begin_at": START.isoformat(),
        "team1_stats": {"matches": 20, "wins": 15},
        "team2_stats": {"matches": 20, "wins": 8},
        "team1_history": history(7, 100, 15, 1000),
        "team2_history": history(8, 100, 8, 2000),
    }
    assert log.log_predictions([match]) == 1
    adapted = adapt_esports_shadow(db, as_of=MODELED + timedelta(minutes=1))
    assert len(adapted) == 1
    assert adapted[0].candidates

    store = _store(tmp_path)
    run = RiskRunSnapshot(
        started_at=MODELED + timedelta(minutes=1),
        completed_at=MODELED + timedelta(minutes=2),
        status=RunStatus.COMPLETE,
        snapshots=(adapted[0].snapshot,),
        candidates=adapted[0].candidates,
    )
    store.append_run(run)
    store.publish_latest(run.run_id)

    ControlledDateTime.current = NOW - timedelta(minutes=5)
    assert log.settle_open(
        lambda _match_id: {
            "winner_team_id": 8,
            "team1_id": 7,
            "team2_id": 8,
            "score1": 1,
            "score2": 2,
            "termination": "normal",
        }
    ) == 1
    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        esports_db_path=db,
    )

    assert summary.terminal_settlements == len(adapted[0].candidates)
    assert summary.unresolved_candidates == 0
    assert {row[1] for row in _terminal_rows(store)} == {"WON"}


def test_research_and_future_candidates_are_never_queried(tmp_path: Path):
    research_store = _store(tmp_path)
    _published_run(research_store, stage=EvidenceStage.RESEARCH)

    def forbidden(_requests, _now):
        raise AssertionError("non-settleable candidate queried")

    summary = run_riskobet_settlements(
        store=research_store,
        now=NOW,
        result_loaders={"football": forbidden},
    )
    assert summary.due_candidates == 0


def test_contract_parser_binds_sport_market_and_selection():
    parsed = parse_settlement_contract(
        "riskobet-settlement-v1:football:result_90_minutes:away"
    )
    assert parsed.sport.value == "football"
    assert parsed.market.value == "result_90_minutes"
    assert parsed.selection.value == "away"

    for invalid in (
        " riskobet-settlement-v1:football:result_90_minutes:away",
        "riskobet-settlement-v1:football:result_90_minutes:away:extra",
        "riskobet-settlement-v9:football:result_90_minutes:away",
        "riskobet-settlement-v1:football:result_90_minutes:over",
    ):
        with pytest.raises(SettlementInputError):
            parse_settlement_contract(invalid)


def test_result_loader_runs_once_per_sport_and_event_limit_is_bounded(tmp_path: Path):
    store = _store(tmp_path)
    _published_run(store)
    calls = []

    def loader(requests, _now):
        calls.append(requests)
        return ResultLoadBatch()

    summary = run_riskobet_settlements(
        store=store,
        now=NOW,
        result_loaders={"football": loader},
        max_events_per_sport=1,
    )
    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert summary.due_events == 1
