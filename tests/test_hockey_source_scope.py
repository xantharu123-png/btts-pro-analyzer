"""Offline source-scope regressions using real native parsing and shared caches."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from scanners.hockey_scanner import HockeyScanner
from test_api_hockey_scanner import (
    DAY, NOW, Transport, catalogue, game, scheduled, scanner,
)


def native_event(adapter):
    return adapter.get_upcoming_games(DAY, DAY)[0]


def nhl_source():
    return SimpleNamespace(errors={}, history_coverage={"status": "complete"},
        get_upcoming_nhl_games=lambda *_: [], get_completed_nhl_games=lambda *_, **__: [])


def test_default_discovery_parses_only_top_five_but_explicit_other_leagues_survive(tmp_path, monkeypatch):
    import config_loader
    monkeypatch.setattr(config_loader, "load_app_config", lambda: SimpleNamespace(api_football_key="offline"))
    owner = HockeyScanner(nhl=nhl_source())
    catalog = [catalogue(), catalogue(identity=8002, name="Swiss League"),
        catalogue(identity=8003, name="SHL", country="Sweden"),
        catalogue(identity=8004, name="Liiga", country="Finland"),
        catalogue(identity=8005, name="DEL", country="Germany")]
    games = [scheduled(league=c["id"], name=c["name"], country=c["country"]["name"], identity=c["id"]*10)
             for c in catalog]
    transport = Transport(catalog=catalog, games=games)
    adapter = scanner(tmp_path, transport=transport, candidates=owner.api.candidates)
    owner.api = adapter
    assert {r["competition"] for r in owner.get_upcoming_games(DAY, DAY)} == {
        "National League", "SHL", "Liiga", "DEL"}
    # Standalone explicit discovery retains the reviewed non-default league.
    standalone = scanner(tmp_path, transport=transport)
    assert "Swiss League" in {r["competition"] for r in standalone.get_upcoming_games(DAY, DAY)}
    assert len(transport.calls) == 2  # both adapters share catalogue/date receipts


@pytest.mark.parametrize("scoped_season", [2025, 2026])
def test_owner_forwards_exact_season_scope_preserving_receipt_and_pending(tmp_path, scoped_season):
    catalog = catalogue()
    catalog["seasons"].append(dict(season=2025, current=False, start="2025-08-01", end="2026-06-30"))
    transport = Transport(catalog=[catalog, catalogue(identity=8002, name="Swiss League")], games=[scheduled()])
    adapter = scanner(tmp_path, transport=transport)
    event = dict(native_event(adapter), season=scoped_season)
    start_time = "2026-05-10T17:00:00+00:00" if scoped_season == 2025 else "2026-10-10T17:00:00+00:00"
    transport.games = [game(season=scoped_season, start=start_time)]
    owner = HockeyScanner(nhl=nhl_source(), api=adapter)
    start = DAY-timedelta(days=365)
    assert owner.get_completed_games(start, DAY, as_of=NOW-timedelta(seconds=1), events=[event]) == []
    assert adapter.history_coverage["requests"] == 1
    assert adapter.history_coverage["resolved_league_seasons"] == 1
    assert owner.history_coverage["pending_observations"] == 1
    assert transport.calls[-1][1]["params"] == {"league": 8001, "season": scoped_season}
    rows = owner.get_completed_games(start, DAY, as_of=NOW, events=[event])
    assert len(rows) == 1 and rows[0]["season"] == scoped_season
    assert rows[0]["result_observed_at"] == NOW.isoformat()
    assert len(transport.calls) == 3  # catalogue, schedule, exact season batch
    # Preserve the adapter's existing inclusive pending-receipt boundary.
    assert owner.history_coverage["pending_observations"] == 1


@pytest.mark.parametrize("changes", [
    {"league_id": True}, {"league_id": 8001.0}, {"league_id": "8001"},
    {"season": True}, {"season": "2026"}, {"season": 2026.0},
    {"competition_id": True}, {"competition_id": "08001"},
    {"source_contract": "foreign"}, {"provider": "NHL"},
    {"source": "NHL"}, {"sport": "basketball"}, {"league_id": -1},
])
def test_malformed_or_foreign_scope_grants_no_requests(tmp_path, changes):
    transport = Transport(games=[scheduled()])
    adapter = scanner(tmp_path, transport=transport)
    event = dict(native_event(adapter), **changes)
    calls_before = deepcopy(transport.calls)
    assert adapter.get_completed_games(DAY-timedelta(days=365), DAY, events=[event]) == []
    assert transport.calls == calls_before
    assert adapter.history_coverage["status"] == "partial"


@pytest.mark.parametrize("wrapped", [False, True])
def test_explicit_empty_scope_does_not_fetch_unrelated_history(tmp_path, wrapped):
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport)
    owner = HockeyScanner(nhl=nhl_source(), api=adapter) if wrapped else adapter
    assert owner.get_completed_games(DAY-timedelta(days=365), DAY, events=[]) == []
    assert transport.calls == []
    assert owner.history_coverage["status"] == "complete"


@pytest.mark.parametrize("changes", [{"league_id": 9999, "competition_id": "9999"},
    {"season": 2024}, {"competition": "Swiss League", "league": "Swiss League"}])
def test_unknown_catalogue_scope_is_partial_not_complete_zero(tmp_path, changes):
    transport = Transport(games=[scheduled()])
    adapter = scanner(tmp_path, transport=transport)
    event = dict(native_event(adapter), **changes)
    calls_before = len(transport.calls)
    assert adapter.get_completed_games(DAY-timedelta(days=365), DAY, events=[event]) == []
    assert len(transport.calls) == calls_before
    assert adapter.history_coverage["status"] == "partial"
    assert adapter.history_coverage["errors"] == ("history_scope_missing",)


def test_empty_catalogue_cannot_report_complete_history(tmp_path):
    transport = Transport(catalog=[catalogue(name="Unreviewed Cup")])
    adapter = scanner(tmp_path, transport=transport)
    assert adapter.get_completed_games(DAY-timedelta(days=365), DAY) == []
    assert adapter.history_coverage["status"] == "partial"
    assert adapter.history_coverage["errors"] == ("history_scope_missing",)
    assert len(transport.calls) == 1


def test_missing_discovery_target_is_reported_without_hiding_valid_games(tmp_path):
    from scanners.api_hockey import DEFAULT_CANDIDATES
    transport = Transport(games=[scheduled()])
    adapter = scanner(tmp_path, transport=transport, candidates=DEFAULT_CANDIDATES)
    assert len(adapter.get_upcoming_games(DAY, DAY)) == 1
    assert adapter.errors == {"schedule": "schedule_scope_missing"}


def test_scoped_history_does_not_enable_paid_nhl_without_explicit_opt_in(tmp_path):
    transport = Transport(catalog=[catalogue(name="NHL", country="USA")],
                          games=[game(name="NHL", country="USA")])
    adapter = scanner(tmp_path, transport=transport)
    event = dict(provider="API-Hockey", source="API-Hockey", sport="ice_hockey",
        source_contract="api-hockey-games-v1", league_id=8001, competition_id="8001",
        competition="NHL", league="NHL", country="USA", season=2026)
    assert adapter.get_completed_games(DAY-timedelta(days=365), DAY, events=[event]) == []
    assert len(transport.calls) == 1  # catalogue only, no duplicate paid NHL history
    assert adapter.history_coverage["status"] == "partial"
    opted_in = scanner(tmp_path, transport=transport, include_nhl=True)
    assert len(opted_in.get_completed_games(DAY-timedelta(days=365), DAY, events=[event])) == 1


@pytest.mark.parametrize("changes", [
    {"provider": "NHL"}, {"provider": "foreign", "source": "foreign"},
    {"provider": ["API-Hockey"]}, {"provider": "NHL", "source": "NHL", "sport": "basketball"},
    {"provider": "NHL", "source": "NHL"},
])
def test_wrapper_does_not_route_foreign_or_conflicting_api_identity_to_nhl(tmp_path, changes):
    transport = Transport(games=[scheduled()])
    adapter = scanner(tmp_path, transport=transport)
    event = dict(native_event(adapter), **changes)
    nhl = nhl_source()
    nhl_calls = []
    nhl.get_completed_nhl_games = lambda *_, **__: nhl_calls.append("unexpected") or []
    owner = HockeyScanner(nhl=nhl, api=adapter)
    calls_before = len(transport.calls)
    assert owner.get_completed_games(DAY-timedelta(days=365), DAY, events=[event]) == []
    assert nhl_calls == [] and len(transport.calls) == calls_before
    assert owner.history_coverage["status"] == "partial"


def test_explicit_nondefault_league_keeps_shared_history_cache(tmp_path):
    from scanners.api_hockey import DEFAULT_CANDIDATES
    transport = Transport(catalog=[catalogue(name="Swiss League")],
                          games=[scheduled(name="Swiss League")])
    standalone = scanner(tmp_path, transport=transport)
    event = native_event(standalone)
    transport.games = [game(name="Swiss League")]
    scoped = scanner(tmp_path, transport=transport, candidates=DEFAULT_CANDIDATES)
    rows = scoped.get_completed_games(DAY-timedelta(days=365), DAY, events=[event])
    assert len(rows) == 1 and rows[0]["competition"] == "Swiss League"
    assert len(transport.calls) == 3
    assert standalone.get_completed_games(DAY-timedelta(days=365), DAY, events=[event]) == rows
    assert len(transport.calls) == 3


def test_real_aggregation_reports_sport_owned_errors_without_leaking_payload(tmp_path):
    from riskobet_automation import RiskSourceBatch, run_riskobet
    from team_sport_forecasts import team_sport_forecast_rows, team_sport_source_coverage
    from test_team_sport_forecasts import _snapshot, NOW as MODEL_NOW
    snapshots = {sport: _snapshot(sport) for sport in ("basketball", "ice_hockey")}
    run = run_riskobet(now=MODEL_NOW, db_path=tmp_path/"risk.db", latest_path=tmp_path/"latest.json",
        basketball_source=RiskSourceBatch("basketball", snapshots=(snapshots["basketball"],)),
        ice_hockey_source=RiskSourceBatch("ice_hockey", snapshots=(snapshots["ice_hockey"],),
            errors=("https://private.invalid/?key=secret",)))
    rows = team_sport_forecast_rows(run, now=MODEL_NOW, target_date=MODEL_NOW.date())
    coverage = team_sport_source_coverage(run, rows, now=MODEL_NOW, target_date=MODEL_NOW.date())
    assert coverage["ice_hockey"]["operational_error_count"] == 1
    assert coverage["basketball"]["operational_error_count"] == 0
    assert "source_operational_error" in coverage["ice_hockey"]["coverage_reasons"]
    assert coverage["basketball"]["coverage_reasons"] == []
    assert coverage["ice_hockey"]["published_model_selection_count"] == 2
    assert "private.invalid" not in str(coverage) and "secret" not in str(coverage)
