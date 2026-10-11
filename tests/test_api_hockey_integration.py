"""Offline contract tests; synthetic Swiss IDs are not live coverage evidence."""
from copy import deepcopy
from datetime import timedelta
from dataclasses import replace
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

import sports_prematch as model
from test_sports_prematch import NOW, event, history
from riskobet_candidates import adapt_ice_hockey_research
from riskobet_domain import stable_event_key
from riskobet_settlement import IceHockeyMarket, Selection, SettlementStatus, settle_ice_hockey
from riskobet_settlement_automation import SettlementRequest, ice_hockey_result_loader
from scanners.completed_history import CompletedHistoryStore
from scanners.hockey_scanner import HockeyScanner, completed_hockey_loader
from tip_publication import compact_signal_row
from team_sport_forecasts import team_sport_forecast_rows


def api_event(**changes):
    return event("ice_hockey", provider="API-Hockey", source="API-Hockey",
        provider_event_id="9000", competition="National League", competition_id="8001",
        league_id=8001, source_contract="api-hockey-games-v1", season=2026,
        game_type=None, source_observed_at=NOW.isoformat(), **changes)


def api_history():
    rows = history("ice_hockey")
    for i, row in enumerate(rows):
        row.update(provider="API-Hockey", source="API-Hockey", provider_event_id=str(i+1),
                   event_id=str(i+1), competition="National League", competition_id="8001",
                   league_id=8001, source_contract="api-hockey-games-v1", season=2026, game_type=None)
        row["regulation_home_score"] = row["home_score"] - int(row["last_period_type"] != "REG" and row["winner_side"] == "home")
        row["regulation_away_score"] = row["away_score"] - int(row["last_period_type"] != "REG" and row["winner_side"] == "away")
    return rows


def test_new_native_league_has_own_model_and_unchanged_nhl():
    old = model.predict_prematch("ice_hockey", event("ice_hockey"), history("ice_hockey"), NOW)
    result = model.predict_prematch("ice_hockey", api_event(), api_history(), NOW)
    assert result.training_games == 84 and result.p_home is not None
    assert result.model_version == model.API_HOCKEY_MODEL_VERSION
    assert old.model_version == model.MODEL_VERSION
    assert result.input_hash != old.input_hash
    # Identical underlying regulation histories give identical mathematics.
    assert result.p_home == old.p_home
    assert result.p_home_regulation <= result.p_home <= result.p_home_regulation + result.p_draw_regulation


def test_api_shootout_total_never_becomes_60_minute_goal():
    rows = api_history()
    identity, missing = model._identity("ice_hockey", api_event(), NOW)
    assert not missing
    row = next(row for row in rows if row["last_period_type"] == "SO")
    row["home_score" if row["winner_side"] == "home" else "away_score"] += 3
    matches = model._normalise_history("ice_hockey", identity, rows, NOW)
    found = next(m for m in matches if m.event_id == row["provider_event_id"])
    assert found.home_score == found.away_score == row["regulation_home_score"]
    assert found.extra_time
    assert len(matches) == 84


@pytest.mark.parametrize("field,value", [("season", 2025), ("competition_id", "8002"),
    ("source_contract", "nhl"), ("regulation_home_score", None),
    ("regulation_home_score", -1), ("regulation_home_score", True),
    ("home_team_id", None), ("home_team_id", True), ("home_team_id", -1),
    ("home_team_id", "01"), ("league_id", "8002")])
def test_wrong_source_season_or_score_cannot_reuse_an_older_result(field, value):
    rows = api_history()
    correction = deepcopy(rows[0])
    correction.update({field: value, "result_observed_at": (NOW-timedelta(seconds=1)).isoformat()})
    identity, _ = model._identity("ice_hockey", api_event(), NOW)
    selected = model._normalise_history("ice_hockey", identity, [*rows, correction], NOW)
    assert len(selected) == 83
    assert not any(row.event_id == correction["provider_event_id"] for row in selected)


@pytest.mark.parametrize("field,value", [("source_contract", None), ("season", True),
    ("home_team_id", True), ("provider_event_id", "guess"), ("league_id", 8),
    ("competition", "Unreviewed Cup"), ("home_team_id", "9"*5000)])
def test_new_provider_cannot_enter_nhl_contract(field, value):
    candidate = api_event()
    candidate[field] = value
    result = model.predict_prematch("ice_hockey", candidate, api_history(), NOW)
    assert result.p_home is None and result.missing


def test_real_frozen_research_can_be_published_without_nhl_scope_alias():
    result = adapt_ice_hockey_research(api_event(), api_history(), modeled_at=NOW)
    snapshot = result.snapshot
    assert snapshot.team_sport_forecast.provider == "API-Hockey"
    assert snapshot.team_sport_forecast.model_version == model.API_HOCKEY_MODEL_VERSION
    rows = team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)), now=NOW, target_date=NOW.date())
    assert len(rows) == 2
    small = compact_signal_row(rows[0])
    assert small["event_key"] == stable_event_key("ice_hockey", "API-Hockey", "9000")
    assert small["snapshot_id"] == snapshot.snapshot_id


def test_shared_scanner_keeps_native_providers_and_reuses_one_history_batch():
    calls = []
    nhl_event = event("ice_hockey")
    nhl = SimpleNamespace(errors={}, history_coverage={"status": "complete"},
        get_upcoming_nhl_games=lambda *args: [nhl_event],
        get_completed_nhl_games=lambda *args, **kwargs: calls.append("nhl") or history("ice_hockey"))
    api = SimpleNamespace(errors={}, history_coverage={"status": "complete"},
        get_upcoming_games=lambda *args: [api_event()],
        get_completed_games=lambda *args, **kwargs: calls.append("api") or api_history())
    scanner = HockeyScanner(nhl=nhl, api=api)
    found = scanner.get_upcoming_games(NOW.date(), NOW.date())
    assert {row["provider"] for row in found} == {"NHL", "API-Hockey"}
    load = completed_hockey_loader(scanner, NOW.date())
    rows = load(as_of=NOW, events=found)
    assert len(rows) == 168 and calls == ["nhl", "api"]
    assert load.coverage["status"] == "complete"


def result_cache(tmp_path):
    received = NOW + timedelta(hours=8)
    store = CompletedHistoryStore(tmp_path/"history.db", clock=lambda: received)
    row = api_history()[0]
    row.update(start_time=(NOW+timedelta(hours=6)).isoformat(), home_score=6, away_score=2,
        regulation_home_score=2, regulation_away_score=2, last_period_type="SO", winner_side="home")
    store.record("API-Hockey", "native-game", [row])
    identity = dict(provider="API-Hockey", provider_event_id=row["provider_event_id"],
        home_id=row["home_team_id"], away_id=row["away_team_id"], home=row["home_team"], away=row["away_team"])
    request = SettlementRequest("ice_hockey", stable_event_key("ice_hockey", "API-Hockey", row["provider_event_id"]),
        NOW+timedelta(hours=6), "frozen", f'{row["home_team"]} vs {row["away_team"]}', (), ("candidate",),
        team_sport_identity=identity)
    return store.path, received, request


def test_settlement_reads_exact_received_result_without_api_or_cache_writes(tmp_path):
    path, now, request = result_cache(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    batch = ice_hockey_result_loader(path)((request,), now)
    assert not batch.issues and len(batch.results) == 1
    result = batch.results[0].result
    assert (result.home_goals_60, result.away_goals_60) == (2, 2)
    assert (result.home_goals_final, result.away_goals_final) == (6, 2)
    assert settle_ice_hockey(result, IceHockeyMarket.MATCH_WINNER_INCLUDING_OT, Selection.HOME).status == SettlementStatus.WIN
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert not ice_hockey_result_loader(path)((request,), now-timedelta(seconds=1)).results


@pytest.mark.parametrize("field,value", [("home_id", "999"), ("provider_event_id", "999"),
    ("provider", "NHL"), ("away", "Another team")])
def test_settlement_does_not_transfer_result_to_wrong_native_identity(tmp_path, field, value):
    path, now, request = result_cache(tmp_path)
    request = replace(request, team_sport_identity={**request.team_sport_identity, field: value})
    batch = ice_hockey_result_loader(path)((request,), now)
    assert not batch.results and batch.issues


def test_corrupt_cached_score_is_not_silently_settled(tmp_path):
    path, now, request = result_cache(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE history_result_revisions SET payload=replace(payload, '\"home_score\":6', '\"home_score\":7')")
    with pytest.raises(ValueError, match="digest"):
        ice_hockey_result_loader(path)((request,), now)


def test_new_failed_source_response_cannot_resurrect_old_cached_final(tmp_path):
    path, before, request = result_cache(tmp_path)
    current = before + timedelta(minutes=31)
    store = CompletedHistoryStore(path, clock=lambda: current)
    key = "league:8001:season:2026"
    assert store.reserve("API-Hockey", key, ttl=timedelta(hours=20), daily_limit=48)
    store.record("API-Hockey", key, (), error="ValueError")
    assert len(ice_hockey_result_loader(path)((request,), before).results) == 1
    batch = ice_hockey_result_loader(path)((request,), current)
    assert not batch.results and batch.issues[0].code == "native_result_unavailable"
