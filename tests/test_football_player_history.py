"""Native-player context lookup against isolated B1 stores, never live data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import sqlite3

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader
from context_models.replay import ReplayUnavailable
from context_observations import _SELECT, _decode_receipt, append_observation_batch
from context_sources.football import _detail_event, normalize_football_context


NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


def implementation():
    try:
        return importlib.import_module("context_sources.football_player_history")
    except ModuleNotFoundError as exc:
        if exc.name != "context_sources.football_player_history":
            raise
        pytest.fail("native player event-key reader is not implemented")


def fixture(identity=10, *, home=1, away=50, players=(101,), guests=(909,), league=78,
            scheduled=None, completed=True):
    raw = {"fixture": {"id": identity,
            "date": canonical_timestamp(scheduled or NOW - timedelta(days=3)),
            "status": {"short": "FT" if completed else "NS"}},
        "league": {"id": league, "season": 2026},
        "teams": {"home": {"id": home}, "away": {"id": away}},
        "goals": {"home": 2 if completed else None, "away": 1 if completed else None}}
    if completed:
        raw["players"] = [{"team": {"id": team}, "players": [
            {"player": {"id": player}, "statistics": [{"games": {
                "minutes": 70, "substitute": False, "position": "M"}}]}
            for player in members]} for team, members in ((home, players), (away, guests))]
    return raw


def target():
    return fixture(900, home=1, away=2, completed=False, scheduled=NOW + timedelta(hours=6))


def store(path, raw, *, observed=NOW - timedelta(hours=1), injuries=(), lineups=()):
    event = _detail_event(raw)
    records = normalize_football_context(event, injuries=list(injuries), lineups=list(lineups),
        appearances=[raw] if event["status"] == "completed" else [], observed_at=observed)
    return append_observation_batch(path, tuple((record, observed) for record in records))


def selected(path, refs):
    with _reader(path) as connection:
        rows = [connection.execute(_SELECT + " WHERE r.digest=?", (ref,)).fetchone() for ref in refs]
    return tuple({**_decode_receipt(row), "evidence_class": "prospective",
        "effective_at": row[3], "publication_resolution": None} for row in rows)


def lookup(path, rows, *, event=None, cutoff=NOW, max_events=8):
    with _reader(path) as connection:
        return implementation().player_event_keys(connection, rows,
            event=event or _detail_event(target()), cutoff=cutoff, max_events=max_events)


def test_same_native_player_joins_club_and_national_but_not_opponent_closure(tmp_path):
    # Team-only joins lose the Germany game; expanding via Germany opponents
    # incorrectly pulls event 23 into Dortmund player's context.
    path = tmp_path / "players.db"
    seed = store(path, fixture())
    store(path, fixture(22, home=25, away=30, league=5))
    store(path, fixture(21, home=1, away=60))
    store(path, fixture(23, home=70, away=80, players=(909,), guests=(808,)))
    store(path, fixture(24, home=25, away=30, players=(102,), guests=(808,), league=5))
    before = path.read_bytes()
    assert lookup(path, selected(path, seed)) == (
        "api-football:football:21", "api-football:football:22")
    assert path.read_bytes() == before


def test_receipt_window_includes_literal_lower_and_asof_upper_boundaries(tmp_path):
    path = tmp_path / "window.db"
    seed = store(path, fixture())
    old_schedule = NOW - timedelta(days=20)
    store(path, fixture(20, scheduled=old_schedule), observed=NOW - timedelta(days=14))
    store(path, fixture(21, scheduled=old_schedule), observed=NOW - timedelta(days=14, seconds=1))
    store(path, fixture(22), observed=NOW)
    store(path, fixture(23), observed=NOW + timedelta(seconds=1))
    assert lookup(path, selected(path, seed)) == (
        "api-football:football:20", "api-football:football:22")


def test_empty_latest_target_collection_withdraws_old_player_membership(tmp_path):
    path = tmp_path / "withdrawal.db"
    old = store(path, fixture(), observed=NOW - timedelta(hours=3))
    empty = store(path, fixture(players=(), guests=()), observed=NOW - timedelta(hours=1))
    store(path, fixture(20, home=25, away=30, league=5))
    assert lookup(path, selected(path, old + empty)) == ()


def test_replaced_target_collection_does_not_revive_removed_player(tmp_path):
    path = tmp_path / "replacement.db"
    old = store(path, fixture(), observed=NOW - timedelta(hours=3))
    new = store(path, fixture(players=(102,)), observed=NOW - timedelta(hours=1))
    store(path, fixture(20, home=25, away=30, players=(101,), league=5))
    store(path, fixture(21, home=25, away=30, players=(102,), league=5))
    assert lookup(path, selected(path, old + new)) == ("api-football:football:21",)


def test_incomplete_supplied_target_collection_cannot_seed_a_player(tmp_path):
    path = tmp_path / "partial.db"
    seed = store(path, fixture(players=(101, 102)))
    store(path, fixture(20, home=25, away=30, league=5))
    rows = tuple(row for row in selected(path, seed) if row["subject_id"] != "api-football:player:102")
    assert lookup(path, rows) == ()


def test_current_target_availability_seeds_id_without_assumed_minutes(tmp_path):
    path = tmp_path / "current.db"
    raw = target()
    injury = {"fixture": raw["fixture"], "league": raw["league"], "team": {"id": 1},
        "player": {"id": 101, "type": "Doubtful", "reason": None}}
    seed = store(path, raw, injuries=(injury,))
    store(path, fixture(20, home=25, away=30, league=5))
    assert lookup(path, selected(path, seed)) == ("api-football:football:20",)


def test_actual_current_lineup_seeds_starters_and_bench_ids(tmp_path):
    path = tmp_path / "lineup.db"
    raw = target()
    raw["lineups"] = [{"team": {"id": 1},
        "startXI": [{"player": {"id": player, "pos": "M"}} for player in range(101, 112)],
        "substitutes": [{"player": {"id": 112, "pos": "M"}}]}]
    seed = store(path, raw, lineups=(raw,))
    store(path, fixture(20, home=25, away=30, league=5))
    store(path, fixture(21, home=25, away=30, players=(112,), league=5))
    assert lookup(path, selected(path, seed)) == (
        "api-football:football:20", "api-football:football:21")


def test_conflicting_source_collections_cannot_seed_their_ambiguous_players(tmp_path):
    path = tmp_path / "conflicts.db"
    old = store(path, fixture(players=(101,)))
    conflict = store(path, fixture(players=(102,)))
    store(path, fixture(20, home=25, away=30, league=5))
    store(path, fixture(21, home=25, away=30, players=(102,), league=5))
    assert lookup(path, selected(path, old + conflict)) == ()


@pytest.mark.parametrize("case", ["different-event", "stale", "future"])
def test_noncurrent_availability_does_not_seed_cross_squad_lookup(tmp_path, case):
    path = tmp_path / "noncurrent.db"
    raw = target()
    if case == "different-event":
        raw["fixture"]["id"] = 901
    injury = {"fixture": raw["fixture"], "league": raw["league"], "team": {"id": 1},
        "player": {"id": 101, "type": "Doubtful", "reason": None}}
    observed = NOW - timedelta(days=2) if case == "stale" else NOW + timedelta(seconds=1) if case == "future" else NOW - timedelta(hours=1)
    seed = store(path, raw, injuries=(injury,), observed=observed)
    store(path, fixture(20, home=25, away=30, league=5))
    assert lookup(path, selected(path, seed)) == ()


def test_bound_rejects_entire_candidate_scope_instead_of_truncating(tmp_path):
    path = tmp_path / "bound.db"
    seed = store(path, fixture())
    store(path, fixture(20, home=25, away=30, league=5))
    store(path, fixture(21, home=25, away=30, league=5))
    with pytest.raises(ReplayUnavailable, match="bound"):
        lookup(path, selected(path, seed), max_events=1)
    with pytest.raises(ReplayUnavailable, match="bound"):
        lookup(path, selected(path, seed), max_events=0)


@pytest.mark.parametrize("cutoff", [datetime(2026, 10, 12, 12), "2026-10-12T12:00:00+00:00"])
def test_noncanonical_cutoff_is_rejected(tmp_path, cutoff):
    path = tmp_path / "clock.db"
    seed = store(path, fixture())
    with pytest.raises(ContextContractError):
        lookup(path, selected(path, seed), cutoff=cutoff)


@pytest.mark.parametrize("limit", [-1, True, 1.5, 4097])
def test_event_bound_requires_finite_integer(tmp_path, limit):
    path = tmp_path / "limits.db"
    seed = store(path, fixture())
    with pytest.raises(ContextContractError):
        lookup(path, selected(path, seed), max_events=limit)


def test_tampered_seed_receipt_is_not_native_player_evidence(tmp_path):
    path = tmp_path / "tampered.db"
    seed = store(path, fixture())
    rows = deepcopy(selected(path, seed))
    rows[0]["payload"]["minutes"] = 80
    with pytest.raises(ContextIntegrityError):
        lookup(path, rows)


def test_lookup_reads_headers_only_and_never_outcome_payloads(tmp_path):
    path = tmp_path / "headers.db"
    seed = store(path, fixture())
    store(path, fixture(20, home=25, away=30, league=5))
    rows = selected(path, seed)
    with _reader(path) as connection:
        def headers_only(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == "context_contents":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        connection.set_authorizer(headers_only)
        assert implementation().player_event_keys(connection, rows, event=_detail_event(target()),
            cutoff=canonical_timestamp(NOW), max_events=1) == ("api-football:football:20",)


def test_corrupt_nonnative_candidate_header_is_rejected_before_pool_loading(tmp_path):
    path = tmp_path / "bad-header.db"
    seed = store(path, fixture())
    store(path, fixture(20, home=25, away=30, league=5))
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE context_observations SET event_key=? WHERE event_key=?",
            ("api-football:football:020", "api-football:football:20"))
    with pytest.raises(ContextIntegrityError, match="nonnative"):
        lookup(path, selected(path, seed))
