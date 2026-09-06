from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from riskobet_automation import run_riskobet
from riskobet_candidates import (
    ESPORTS_WIN_MIN_PROBABILITY,
    FOOTBALL_CONTEXT_TTL,
    FOOTBALL_ONE_GOAL_MAX_PROBABILITY,
    FOOTBALL_WIN_MIN_PROBABILITY,
    RESEARCH_WIN_MIN_PROBABILITY,
    TENNIS_WIN_MIN_PROBABILITY,
    adapt_basketball_research,
    adapt_cricket_research,
    adapt_esports_shadow,
    adapt_football_candidates,
    adapt_ice_hockey_research,
    adapt_tennis_shadow,
    football_risk_bundle,
    football_risk_source_pool,
    select_football_risk_sources,
)
from riskobet_domain import ContextState, EvidenceStage
from riskobet_store import RiskBetStore


UTC = timezone.utc
MODELED_AT = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
KICKOFF = MODELED_AT + timedelta(hours=4)


def football_candidate(
    market_key: str,
    probability: float,
    *,
    fixture_id: int = 77,
    expected_home_goals: float = 1.1,
    expected_away_goals: float = 1.8,
    context: dict | None = None,
    model_price: float = 99.0,
) -> SimpleNamespace:
    labels = {
        "RESULT_HOME": ("Endergebnis", "Heimsieg"),
        "RESULT_DRAW": ("Endergebnis", "Unentschieden"),
        "RESULT_AWAY": ("Endergebnis", "Auswärtssieg"),
        "DC_1X": ("Doppelte Chance", "1X"),
        "DC_X2": ("Doppelte Chance", "X2"),
        "HOME_OVER_0_5": ("Team 1 Gesamttore", "Über 0.5"),
        "HOME_OVER_1_5": ("Team 1 Gesamttore", "Über 1.5"),
        "AWAY_OVER_0_5": ("Team 2 Gesamttore", "Über 0.5"),
        "AWAY_OVER_1_5": ("Team 2 Gesamttore", "Über 1.5"),
    }
    market, selection = labels[market_key]
    return SimpleNamespace(
        candidate_id=f"{fixture_id}:{market_key}",
        fixture_id=fixture_id,
        league_id=10,
        league_name="Test League",
        kickoff=KICKOFF.isoformat(),
        home_team_id=100,
        away_team_id=200,
        home_team="Home Underdog",
        away_team="Away Favourite",
        market_key=market_key,
        market=market,
        selection=selection,
        probability=probability,
        conservative_probability=max(0.0, probability - 0.08),
        probability_haircut_pp=8.0,
        model_price=model_price,
        minimum_odds=11.0,
        offered_odds=42.0,
        evidence_score=77.0,
        model_spread_pp=5.0,
        expected_home_goals=expected_home_goals,
        expected_away_goals=expected_away_goals,
        venue_samples=(12, 14),
        form_samples=(6, 6),
        validation=None,
        model_scope="same_competition",
        reasons=[],
        blocked_reasons=["normal gate deliberately irrelevant"],
        context=context or {},
    )


def football_pool(
    *,
    home_win: float = 0.20,
    draw: float = 0.25,
    away_win: float = 0.55,
    dc: float = 0.45,
    one_goal: float = 0.65,
    two_goals: float = 0.25,
    expected_home_goals: float = 1.1,
    context: dict | None = None,
) -> list[SimpleNamespace]:
    return [
        football_candidate(
            "RESULT_HOME",
            home_win,
            expected_home_goals=expected_home_goals,
            context=context,
        ),
        football_candidate(
            "RESULT_DRAW",
            draw,
            expected_home_goals=expected_home_goals,
            context=context,
        ),
        football_candidate(
            "RESULT_AWAY",
            away_win,
            expected_home_goals=expected_home_goals,
            context=context,
        ),
        football_candidate(
            "DC_1X",
            dc,
            expected_home_goals=expected_home_goals,
            context=context,
        ),
        football_candidate(
            "HOME_OVER_0_5",
            one_goal,
            expected_home_goals=expected_home_goals,
            context=context,
        ),
        football_candidate(
            "HOME_OVER_1_5",
            two_goals,
            expected_home_goals=expected_home_goals,
            context=context,
        ),
        # Prove the support pool drops unrelated markets.
        SimpleNamespace(
            **{
                **football_candidate("RESULT_DRAW", 0.25).__dict__,
                "candidate_id": "77:TOTAL_OVER_2_5",
                "market_key": "TOTAL_OVER_2_5",
            }
        ),
    ]


def complete_context(checked_at: datetime) -> dict:
    return {
        "release_context_complete": True,
        "checked_at": checked_at.isoformat(),
        "h2h": {"status": "neutral", "reason": "keine belastbare Gegenindikation"},
        # These are the real successful statuses produced by
        # challenge_engine.apply_candidate_context.
        "injuries": {"status": "observed", "reason": "keine bestätigten Ausfälle"},
        "weather": {
            "status": "observed",
            "reason": "Extremwetter unterstützt den Markt",
            "market_effect": "aligned",
            "veto_applied": False,
        },
        "lineups": {"status": "passed", "reason": "bestätigt"},
        "reference_price": 2.5,
        "bookmaker_quote": 7.0,
    }


def test_football_selects_at_most_two_before_normal_gates_and_support_is_reproducible():
    pool = football_pool(two_goals=0.42)
    selected = select_football_risk_sources(pool)
    assert 1 <= len(selected) <= 2
    assert all(item.blocked_reasons for item in selected)
    support = football_risk_source_pool(pool)
    assert {item.market_key for item in support} == {
        "RESULT_HOME",
        "RESULT_DRAW",
        "RESULT_AWAY",
        "DC_1X",
        "HOME_OVER_0_5",
        "HOME_OVER_1_5",
    }
    assert [item.candidate_id for item in select_football_risk_sources(support)] == [
        item.candidate_id for item in selected
    ]
    direct = adapt_football_candidates(pool, modeled_at=MODELED_AT)
    compact = adapt_football_candidates(support, modeled_at=MODELED_AT)
    assert len(direct) == len(compact) == 1
    assert [c.candidate_id for c in direct[0].candidates] == [
        c.candidate_id for c in compact[0].candidates
    ]


def test_football_quote_fields_do_not_change_selection_ranking_or_snapshot():
    first = football_pool()
    second = football_pool()
    for index, candidate in enumerate(second):
        candidate.model_price = 1.01 + index
        candidate.minimum_odds = 1000.0 + index
        candidate.offered_odds = 5000.0 - index
    selected_first = select_football_risk_sources(first)
    selected_second = select_football_risk_sources(second)
    assert [item.candidate_id for item in selected_first] == [
        item.candidate_id for item in selected_second
    ]
    one = football_risk_bundle(
        selected_first,
        source_pool=football_risk_source_pool(first),
        modeled_at=MODELED_AT,
    )
    two = football_risk_bundle(
        selected_second,
        source_pool=football_risk_source_pool(second),
        modeled_at=MODELED_AT,
    )
    assert one.snapshot.snapshot_id == two.snapshot.snapshot_id
    assert [item.candidate_id for item in one.candidates] == [
        item.candidate_id for item in two.candidates
    ]
    assert all("price" not in candidate.to_dict() for candidate in one.candidates)
    assert all("odds" not in candidate.to_dict() for candidate in one.candidates)


def test_football_identity_is_fail_closed_and_bundle_order_is_stable():
    pool = football_pool()
    selected = select_football_risk_sources(pool)
    support = football_risk_source_pool(pool)
    forward = football_risk_bundle(
        selected,
        source_pool=support,
        modeled_at=MODELED_AT,
    )
    reverse = football_risk_bundle(
        list(reversed(selected)),
        source_pool=list(reversed(support)),
        modeled_at=MODELED_AT,
    )
    assert forward.snapshot.snapshot_id == reverse.snapshot.snapshot_id
    assert [item.candidate_id for item in forward.candidates] == [
        item.candidate_id for item in reverse.candidates
    ]
    assert forward.snapshot.factors[0].factor_key == "football_fixture_id:77"
    assert forward.snapshot.factors[0].observed_at <= forward.snapshot.input_cutoff_at

    corrupt = football_pool()
    corrupt[-2].home_team = "Different Identity"
    assert select_football_risk_sources(corrupt) == []
    assert football_risk_source_pool(corrupt) == []


def test_football_refetch_with_a_new_causal_clock_creates_a_new_snapshot_revision():
    """Repeated automation runs must not collide in the immutable store."""

    pool = football_pool()
    selected = select_football_risk_sources(pool)
    support = football_risk_source_pool(pool)
    first = football_risk_bundle(
        selected,
        source_pool=support,
        modeled_at=MODELED_AT,
        input_cutoff_at=MODELED_AT,
    )
    refetched_at = MODELED_AT + timedelta(minutes=10)
    refetched = football_risk_bundle(
        selected,
        source_pool=support,
        modeled_at=refetched_at,
        input_cutoff_at=refetched_at,
    )

    assert refetched.snapshot.snapshot_id != first.snapshot.snapshot_id
    assert refetched.snapshot.input_hash != first.snapshot.input_hash


def test_football_refetch_persists_and_becomes_the_settlement_revision(tmp_path):
    pool = football_pool()
    selected = select_football_risk_sources(pool)
    support = football_risk_source_pool(pool)
    first = football_risk_bundle(
        selected,
        source_pool=support,
        modeled_at=MODELED_AT,
        input_cutoff_at=MODELED_AT,
    )
    refetched_at = MODELED_AT + timedelta(minutes=10)
    refetched = football_risk_bundle(
        selected,
        source_pool=support,
        modeled_at=refetched_at,
        input_cutoff_at=refetched_at,
    )
    store = RiskBetStore(tmp_path / "riskobet.db", tmp_path / "riskobet_latest.json")

    run_riskobet(football_source=(first,), store=store, now=MODELED_AT)
    second_run = run_riskobet(
        football_source=(refetched,),
        store=store,
        now=refetched_at,
    )

    assert store.read_latest()["run_id"] == second_run.run_id
    targets = store.load_due_settlement_targets(as_of=KICKOFF + timedelta(minutes=1))
    assert targets
    assert {target["snapshot"]["snapshot_id"] for target in targets} == {
        refetched.snapshot.snapshot_id
    }


def test_football_rejects_extreme_underdog_and_trivial_one_goal_without_factor():
    assert FOOTBALL_WIN_MIN_PROBABILITY > 0.05
    assert FOOTBALL_ONE_GOAL_MAX_PROBABILITY < 0.90
    extreme = football_pool(
        home_win=0.04,
        draw=0.12,
        away_win=0.84,
        dc=0.90,
        one_goal=0.92,
        two_goals=0.08,
        expected_home_goals=0.55,
    )
    assert select_football_risk_sources(extreme) == []
    assert adapt_football_candidates(extreme, modeled_at=MODELED_AT) == ()

    no_factor = football_pool(
        home_win=0.10,
        draw=0.10,
        away_win=0.80,
        dc=0.82,
        one_goal=0.60,
        two_goals=0.10,
        expected_home_goals=0.70,
    )
    assert select_football_risk_sources(no_factor) == []
    with_factor = football_pool(
        home_win=0.10,
        draw=0.10,
        away_win=0.80,
        dc=0.82,
        one_goal=0.60,
        two_goals=0.10,
        expected_home_goals=1.05,
    )
    selected = select_football_risk_sources(with_factor)
    assert [item.market_key for item in selected] == ["HOME_OVER_0_5"]


@pytest.mark.parametrize(
    ("checked_delta", "complete", "expected"),
    [
        (timedelta(minutes=30), True, ContextState.FRESH),
        (FOOTBALL_CONTEXT_TTL + timedelta(seconds=1), True, ContextState.STALE),
        (timedelta(minutes=30), False, ContextState.PARTIAL),
    ],
)
def test_football_context_state_uses_completeness_and_75_minute_ttl(
    checked_delta: timedelta,
    complete: bool,
    expected: ContextState,
):
    context = complete_context(MODELED_AT - checked_delta)
    context["release_context_complete"] = complete
    if not complete:
        context["lineups"] = {"status": "pending", "reason": "noch offen"}
    pool = football_pool(context=context)
    selected = select_football_risk_sources(pool)
    result = football_risk_bundle(
        selected,
        source_pool=football_risk_source_pool(pool),
        modeled_at=MODELED_AT,
    )
    assert {candidate.context_state for candidate in result.candidates} == {expected}
    for factor in result.snapshot.factors[1:]:
        assert factor.fresh_until <= MODELED_AT - checked_delta + FOOTBALL_CONTEXT_TTL


def test_football_without_context_is_open():
    pool = football_pool()
    result = football_risk_bundle(
        select_football_risk_sources(pool),
        source_pool=football_risk_source_pool(pool),
        modeled_at=MODELED_AT,
    )
    assert {candidate.context_state for candidate in result.candidates} == {
        ContextState.OPEN
    }


def test_football_placeholder_gate_mapping_is_not_real_context():
    pool = football_pool(
        context={
            "passed": False,
            "blocked_reasons": ["Pflichtkontext wird im Hintergrund nachgeladen"],
        }
    )
    result = football_risk_bundle(
        select_football_risk_sources(pool),
        source_pool=football_risk_source_pool(pool),
        modeled_at=MODELED_AT,
    )
    assert {candidate.context_state for candidate in result.candidates} == {
        ContextState.OPEN
    }


def create_tennis_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY,
                created_utc REAL NOT NULL,
                scheduled_start_utc TEXT,
                provider_event_id TEXT,
                fixture_source TEXT,
                tour TEXT,
                tournament TEXT,
                surface TEXT,
                best_of INTEGER,
                player_a TEXT,
                player_b TEXT,
                p_cal REAL,
                markets_json TEXT,
                gates_json TEXT,
                odds_a REAL,
                odds_b REAL,
                settled INTEGER,
                model_version TEXT
            )
            """
        )


def insert_tennis(
    path: Path,
    *,
    row_id: int,
    p_a: float,
    markets: str,
    odds_a: float = 2.0,
    odds_b: float = 2.0,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                (MODELED_AT - timedelta(minutes=5)).timestamp(),
                KICKOFF.isoformat(),
                f"tennis-{row_id}",
                "ESPN",
                "ATP",
                "Test Open",
                "Hard",
                3,
                "Player A",
                "Player B",
                p_a,
                markets,
                "{}",
                odds_a,
                odds_b,
                0,
                "tennis-v-test",
            ),
        )


def test_tennis_adapter_is_price_neutral_bounded_and_guards_extreme_winner(tmp_path: Path):
    path = tmp_path / "tennis.db"
    create_tennis_db(path)
    insert_tennis(
        path,
        row_id=1,
        p_a=0.35,
        markets=(
            '{"over_2_5_sets":0.45,"set_handicap_a_minus_1_5":0.12,'
            '"set_handicap_b_minus_1_5":0.35}'
        ),
    )
    insert_tennis(
        path,
        row_id=2,
        p_a=0.03,
        markets=(
            '{"over_2_5_sets":0.10,"set_handicap_a_minus_1_5":0.01,'
            '"set_handicap_b_minus_1_5":0.94}'
        ),
    )
    assert TENNIS_WIN_MIN_PROBABILITY > 0.05
    output = adapt_tennis_shadow(path, as_of=MODELED_AT)
    assert len(output) == 2
    assert 1 <= len(output[0].candidates) <= 2
    assert output[1].candidates == ()
    assert all(candidate.stage is EvidenceStage.SHADOW for candidate in output[0].candidates)
    first_snapshot = output[0].snapshot.snapshot_id
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE predictions SET odds_a=99, odds_b=101 WHERE id=1")
    repeated = adapt_tennis_shadow(path, as_of=MODELED_AT)
    assert repeated[0].snapshot.snapshot_id == first_snapshot
    assert [item.candidate_id for item in repeated[0].candidates] == [
        item.candidate_id for item in output[0].candidates
    ]
    later = adapt_tennis_shadow(path, as_of=MODELED_AT + timedelta(minutes=10))
    assert later[0].snapshot.to_dict() == repeated[0].snapshot.to_dict()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE predictions SET created_utc=? WHERE id=1",
            ((MODELED_AT - timedelta(minutes=1)).timestamp(),),
        )
    refetched = adapt_tennis_shadow(path, as_of=MODELED_AT + timedelta(minutes=10))
    assert refetched[0].snapshot.snapshot_id != repeated[0].snapshot.snapshot_id


def create_esports_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE esports_shadow_predictions (
                match_id INTEGER PRIMARY KEY,
                logged_at TEXT,
                game TEXT,
                team1 TEXT,
                team2 TEXT,
                team1_id INTEGER,
                team2_id INTEGER,
                selection TEXT,
                status TEXT,
                series_type INTEGER,
                score1 INTEGER,
                score2 INTEGER,
                elo1 REAL,
                elo2 REAL,
                model_probability REAL,
                risk_adjusted_probability REAL,
                minimum_odds REAL,
                settled INTEGER,
                scheduled_at TEXT,
                model_version TEXT
            )
            """
        )


def insert_esports(path: Path, row_id: int, favorite_probability: float, elo_gap: float) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO esports_shadow_predictions VALUES (
                ?, ?, 'CS2', 'Team A', 'Team B', 7, 8, 'Team B', 'upcoming', 3,
                0, 0, ?, 1600, ?, ?, 9.9, 0, ?, 'esports-v-test'
            )
            """,
            (
                row_id,
                (MODELED_AT - timedelta(minutes=5)).isoformat(),
                1600 - elo_gap,
                favorite_probability,
                max(0.0, favorite_probability - 12.0),
                KICKOFF.isoformat(),
            ),
        )


def test_esports_adapter_uses_complement_map_math_and_extreme_guard(tmp_path: Path):
    path = tmp_path / "esports.db"
    create_esports_db(path)
    insert_esports(path, 1, 70.0, 120.0)
    insert_esports(path, 2, 98.0, 450.0)
    assert ESPORTS_WIN_MIN_PROBABILITY > 0.05
    output = adapt_esports_shadow(path, as_of=MODELED_AT)
    assert len(output) == 2
    assert [item.market_key for item in output[0].candidates] == [
        "series_winner",
        "at_least_one_map",
    ]
    assert output[0].candidates[0].model_probability == pytest.approx(0.30)
    assert 0.30 < output[0].candidates[1].model_probability < 0.85
    assert output[1].candidates == ()
    snapshot_id = output[0].snapshot.snapshot_id
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE esports_shadow_predictions SET minimum_odds=500")
    repeated = adapt_esports_shadow(path, as_of=MODELED_AT)
    assert repeated[0].snapshot.snapshot_id == snapshot_id
    later = adapt_esports_shadow(path, as_of=MODELED_AT + timedelta(minutes=10))
    assert later[0].snapshot.to_dict() == repeated[0].snapshot.to_dict()


def scanner_event(sport: str) -> dict:
    if sport == "basketball":
        return {
            "source": "ESPN",
            "status": "upcoming",
            "game_id": "nba-1",
            "league": "NBA",
            "home_team": "Alpha",
            "away_team": "Beta",
            "start_time": KICKOFF.isoformat(),
            "source_observed_at": MODELED_AT.isoformat(),
            "odds": 123.0,
        }
    if sport == "ice_hockey":
        return {
            "source": "NHL",
            "status": "upcoming",
            "game_id": 2026020001,
            "league": "NHL",
            "game_type": 2,
            "home_team": "Alpha",
            "away_team": "Beta",
            "start_time": KICKOFF.isoformat(),
            "source_observed_at": MODELED_AT.isoformat(),
        }
    return {
        "source": "Cricbuzz",
        "status": "upcoming",
        "match_id": "cricket-1",
        "tournament": "Test Cup",
        "format": "T20",
        "neutral_site": True,
        "team1": "Alpha",
        "team2": "Beta",
        "start_time": KICKOFF.isoformat(),
        "source_observed_at": MODELED_AT.isoformat(),
    }


def research_history(team: str, wins: int, games: int, *, sport: str = "basketball") -> list[dict]:
    rows = []
    event = scanner_event(sport)
    for index in range(games):
        team_home = index % 2 == 0
        opponent = f"Common Opponent-{index % 4}"
        winner = "home" if (index < wins) == team_home else "away"
        completed = MODELED_AT - timedelta(days=index + 1)
        extra_time = sport == "ice_hockey" and index % 4 == 0
        winner_score = 3 if extra_time else 4 + index % 2 if sport == "ice_hockey" else 108 + index % 5
        loser_score = 2 if sport == "ice_hockey" else 100
        rows.append(
            {
                "provider": event["source"],
                "competition": event.get("league", event.get("tournament")),
                "provider_event_id": f"{sport}-{team}-{index}",
                "status": "completed",
                "start_time": (completed - timedelta(hours=3)).isoformat(),
                "completed_at": completed.isoformat(),
                "result_observed_at": (completed + timedelta(minutes=2)).isoformat(),
                "result_scope": {"basketball": "including_overtime", "ice_hockey": "including_overtime_shootout", "cricket": "match_winner"}[sport],
                "game_type": event.get("game_type"),
                "format": event.get("format"),
                "neutral_site": sport == "cricket",
                "last_period_type": "OT" if extra_time else "REG",
                "home_team": team if team_home else opponent,
                "away_team": opponent if team_home else team,
                "home_score": winner_score if winner == "home" else loser_score,
                "away_score": winner_score if winner == "away" else loser_score,
                "winner_side": winner,
                "closing_odds": 99.0,
            }
        )
    return rows


@pytest.mark.parametrize(
    ("adapter", "sport", "market"),
    [
        (adapt_basketball_research, "basketball", "match_winner_including_ot"),
        (adapt_ice_hockey_research, "ice_hockey", "match_winner_including_ot"),
        (adapt_cricket_research, "cricket", "match_winner"),
    ],
)
def test_research_adapters_accept_real_scanner_fields_and_calculate_only_with_history(
    adapter,
    sport: str,
    market: str,
):
    history = research_history("Alpha", 13, 20, sport=sport) + research_history("Beta", 7, 20, sport=sport)
    result = adapter(scanner_event(sport), history, modeled_at=MODELED_AT)
    assert result.snapshot.sport == sport
    assert result.snapshot.competition in {"NBA", "NHL", "Test Cup"}
    candidate = result.candidates[0]
    assert candidate.market_key == market
    assert candidate.stage is EvidenceStage.RESEARCH
    assert candidate.model_probability is not None
    assert 0.0 < candidate.model_probability < 0.5
    # A research fit does not manufacture an individual confidence lower bound.
    assert candidate.cautious_probability is None

    missing = adapter(scanner_event(sport), history[:3], modeled_at=MODELED_AT)
    candidate = missing.candidates[0]
    assert candidate.model_probability is None
    assert candidate.cautious_probability is None
    assert candidate.selection_key == "open"
    assert candidate.missing_core_data
    assert any("vor Start erforderlich" in item for item in candidate.missing_core_data)
    assert any("mindestens 40" in item for item in candidate.missing_core_data)


def test_research_history_is_causal_and_identity_is_price_neutral():
    event = scanner_event("basketball")
    history = research_history("Alpha", 13, 20) + research_history("Beta", 7, 20)
    baseline = adapt_basketball_research(event, history, modeled_at=MODELED_AT)
    future = {**history[0], "provider_event_id": "future-event",
        "completed_at": (KICKOFF + timedelta(hours=2)).isoformat(),
        "result_observed_at": (KICKOFF + timedelta(hours=2, minutes=2)).isoformat(),
    }
    with_future = adapt_basketball_research(
        {**event, "odds": 1.01, "bookmaker_price": 1000.0},
        [*history, future],
        modeled_at=MODELED_AT,
    )
    assert with_future.snapshot.snapshot_id == baseline.snapshot.snapshot_id
    assert with_future.candidates[0].candidate_id == baseline.candidates[0].candidate_id
    assert (
        with_future.candidates[0].model_probability
        == baseline.candidates[0].model_probability
    )
    assert with_future.snapshot.input_cutoff_at < with_future.snapshot.starts_at

    later_read = adapt_basketball_research(
        event,
        history,
        modeled_at=MODELED_AT + timedelta(minutes=10),
    )
    assert later_read.snapshot.snapshot_id != baseline.snapshot.snapshot_id
    assert later_read.snapshot.modeled_at == MODELED_AT + timedelta(minutes=10)
    assert later_read.snapshot.event_key == baseline.snapshot.event_key
    assert later_read.candidates[0].model_probability == baseline.candidates[0].model_probability
    refetched_event = {
        **event,
        "source_observed_at": (MODELED_AT + timedelta(minutes=1)).isoformat(),
    }
    refetched = adapt_basketball_research(
        refetched_event,
        history,
        modeled_at=MODELED_AT + timedelta(minutes=10),
    )
    assert refetched.snapshot.snapshot_id != baseline.snapshot.snapshot_id


def test_research_requires_explicit_source_clock_and_never_uses_start_as_completion():
    event = scanner_event("basketball")
    without_source_clock = dict(event)
    without_source_clock.pop("source_observed_at")
    with pytest.raises(ValueError, match="source_observed_at or fetched_at"):
        adapt_basketball_research(
            without_source_clock,
            [],
            modeled_at=MODELED_AT,
        )

    started_but_not_timestamped_as_complete = {
        "status": "final",
        "start_time": (MODELED_AT - timedelta(hours=2)).isoformat(),
        "home_team": "Alpha",
        "away_team": "Opponent",
        "winner_side": "home",
    }
    result = adapt_basketball_research(
        event,
        [started_but_not_timestamped_as_complete],
        modeled_at=MODELED_AT,
    )
    candidate = result.candidates[0]
    assert candidate.model_probability is None
    assert any("0 vorhanden" in item for item in candidate.missing_core_data)
    later = adapt_basketball_research(
        event,
        [started_but_not_timestamped_as_complete],
        modeled_at=MODELED_AT + timedelta(minutes=10),
    )
    assert later.snapshot.snapshot_id != result.snapshot.snapshot_id
    assert later.snapshot.modeled_at == MODELED_AT + timedelta(minutes=10)
    assert later.candidates[0].model_probability is None


def test_research_accepts_explicit_result_observation_clock():
    event = scanner_event("basketball")
    history = research_history("Alpha", 13, 20) + research_history("Beta", 7, 20)
    row = dict(history[0])
    row["result_observed_at"] = row.pop("completed_at")
    result = adapt_basketball_research(
        event,
        [row, *history[1:]],
        modeled_at=MODELED_AT,
    )
    assert result.candidates[0].model_probability is not None


def test_research_equal_strength_does_not_invent_an_underdog_probability():
    history = research_history("Alpha", 10, 20, sport="cricket") + research_history("Beta", 10, 20, sport="cricket")
    result = adapt_cricket_research(
        scanner_event("cricket"), history, modeled_at=MODELED_AT
    )
    candidate = result.candidates[0]
    assert candidate.model_probability is None
    assert candidate.selection_key == "open"
    assert "Kein eindeutiger Außenseiter" in candidate.missing_core_data[-1]


def test_research_extreme_outsider_is_not_forced_into_the_catalog():
    assert RESEARCH_WIN_MIN_PROBABILITY > 0.05
    history = research_history("Alpha", 20, 20) + research_history("Beta", 0, 20)
    result = adapt_basketball_research(
        scanner_event("basketball"), history, modeled_at=MODELED_AT
    )
    assert result.snapshot.sport == "basketball"
    assert result.candidates == ()


def test_adapters_reject_post_start_model_time():
    with pytest.raises(ValueError, match="pre-match"):
        adapt_basketball_research(
            scanner_event("basketball"),
            [],
            modeled_at=KICKOFF + timedelta(seconds=1),
        )
