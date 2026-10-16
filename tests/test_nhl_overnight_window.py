"""Offline daily NHL horizon; real source/model/catalog/ledger/reader boundaries."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from config_loader import AppConfig
from ev_signal_sources import automated_wettfinder_forecasts
from riskobet_candidates import adapt_research_matchwinner
from scanners.basketball_scanner import BasketballScanner
from scanners.hockey_scanner import HockeyScanner
from team_sport_forecasts import team_sport_forecast_rows, team_sport_source_coverage
from wettfinder_automation import _default_ice_hockey_risk_source, _ranked_candidates, _riskobet_default_sources, run_wettfinder
from test_sports_prematch import event, history

NOW = datetime(2026, 10, 16, 1, 35, tzinfo=timezone.utc)  # 03:35 Zurich
TARGET = date(2026, 10, 16)
OVERNIGHT = datetime(2026, 10, 17, 1, tzinfo=timezone.utc)


def source_fixture(monkeypatch, starts):
    """Only HTTP and completed provider transports are substituted."""
    import requests
    import scanners.hockey_scanner as hockey
    raw = [dict(id=2026020001+i, gameState='FUT', gameType=2, season=20262027,
        startTimeUTC=start.isoformat(), homeTeam={'id': 1, 'abbrev': 'NJD'},
        awayTeam={'id': 8, 'abbrev': 'MTL'}, venue={'default': 'Arena'})
        for i, start in enumerate(starts)]
    requests_seen, api_windows = [], []
    def http(url, **kwargs):
        assert '/schedule/' in url
        requests_seen.append(url)
        return SimpleNamespace(status_code=200, url=url,
            json=lambda: {'gameWeek': [{'games': deepcopy(raw)}]})
    monkeypatch.setattr(requests, 'get', http)
    nhl = BasketballScanner()
    nhl.get_completed_nhl_games = lambda *_args, **_kwargs: history('ice_hockey')
    api = SimpleNamespace(errors={}, history_coverage={},
        get_upcoming_games=lambda start, end: api_windows.append((start, end)) or [],
        get_completed_games=lambda *_args, **_kwargs: [])
    scanner = HockeyScanner(nhl=nhl, api=api)
    monkeypatch.setattr(hockey, 'HockeyScanner', lambda: scanner)
    return scanner, requests_seen, api_windows


def daily_batch(monkeypatch, starts, *, now=NOW, target=TARGET, collector=None, clock=None):
    scanner, calls, api_windows = source_fixture(monkeypatch, starts)
    sources, _ = _riskobet_default_sources({}, now=now, target_date=target,
        research_due=True, clock=clock or (lambda: now))
    if collector is None:
        batch = sources['ice_hockey']()
    else:
        batch = _default_ice_hockey_risk_source(target, now, clock=clock or (lambda: now),
            context_collector=collector, include_overnight_nhl=True)
    return batch, scanner, calls, api_windows


def test_native_overnight_daily_source_survives_actual_catalog_ledger_and_reader(monkeypatch, tmp_path):
    from riskobet_automation import run_riskobet
    import forecast_evidence
    batch, _, calls, api_windows = daily_batch(monkeypatch, [OVERNIGHT])
    assert len(batch.snapshots) == 1
    forecast = batch.snapshots[0].team_sport_forecast
    assert forecast.provider == 'NHL' and forecast.starts_at == OVERNIGHT and forecast.p_home is not None
    projected = team_sport_forecast_rows(batch, now=NOW, target_date=TARGET)
    assert len(projected) == 2
    assert len(_ranked_candidates(projected, now=NOW, target_date=TARGET)) == 2
    assert team_sport_source_coverage(batch, projected, now=NOW, target_date=TARGET)['ice_hockey']['snapshot_count'] == 1
    run = run_riskobet(ice_hockey_source=lambda: batch, now=NOW,
        db_path=tmp_path/'risk.db', latest_path=tmp_path/'risk.json')
    monkeypatch.setattr(forecast_evidence, '_now', lambda: NOW)
    state, evidence = tmp_path/'wettfinder.json', tmp_path/'evidence.db'
    document = run_wettfinder(now=NOW, state_path=state, config=AppConfig(),
        tennis_loader=lambda **_kw: [], esports_loader=lambda **_kw: [],
        riskobet_runner=lambda **_kw: run, evidence_db_path=evidence)
    assert len(document['model_candidates']) == 2
    assert document['forecast_evidence']['recorded'] == 2
    with sqlite3.connect(evidence) as connection:
        assert connection.execute('SELECT count(*) FROM forecast_rows').fetchone() == (2,)
    loaded = automated_wettfinder_forecasts(state, now=NOW)
    assert len(loaded) == 2 and {r.scheduled_start for r in loaded} == {OVERNIGHT.isoformat()}
    assert document['candidates'] == document['challenge_release_candidates'] == []
    assert len(calls) == 1 and api_windows == [(TARGET, TARGET)]


@pytest.mark.parametrize('offset,expected', [(timedelta(hours=24), 1),
    (timedelta(hours=24, seconds=1), 0), (timedelta(0), 0), (timedelta(seconds=-1), 0)])
def test_daily_source_filters_real_elapsed_boundary_before_history_and_context(monkeypatch, offset, expected):
    captured = []
    batch, _, _, _ = daily_batch(monkeypatch, [NOW+offset], collector=lambda **kw: captured.append(kw))
    assert len(batch.snapshots) == expected
    assert len(captured) == expected
    if expected:
        assert len(captured[0]['events']) == 1


def test_manual_calendar_window_and_isolated_default_remain_exact(monkeypatch):
    scanner, _, api_windows = source_fixture(monkeypatch, [OVERNIGHT])
    assert scanner.get_upcoming_games(TARGET, TARGET) == []
    assert _default_ice_hockey_risk_source(TARGET, NOW).snapshots == ()
    assert len(scanner.get_upcoming_games(TARGET, TARGET+timedelta(days=1))) == 1
    assert api_windows == [(TARGET, TARGET), (TARGET, TARGET), (TARGET, date(2026, 10, 17))]


@pytest.mark.parametrize('nhl_end', [TARGET-timedelta(days=1), TARGET+timedelta(days=15), NOW, '2026-10-17'])
def test_native_expanded_end_validates_before_any_provider_call(monkeypatch, nhl_end):
    scanner, calls, api_windows = source_fixture(monkeypatch, [OVERNIGHT])
    with pytest.raises(ValueError):
        scanner.get_upcoming_games(TARGET, TARGET, nhl_end=nhl_end)
    assert calls == api_windows == []


@pytest.mark.parametrize('sport,provider,now,start,target,expected', [
    ('ice_hockey', 'NHL', NOW, OVERNIGHT, TARGET, 2),
    ('ice_hockey', 'NHL', NOW, NOW+timedelta(hours=24), TARGET, 2),
    ('ice_hockey', 'NHL', NOW, NOW+timedelta(hours=24, seconds=1), TARGET, 0),
    ('ice_hockey', 'NHL', NOW, OVERNIGHT, date(2026, 10, 15), 0),
    ('ice_hockey', 'API-Hockey', NOW, OVERNIGHT, TARGET, 0),
    ('basketball', 'ESPN', NOW, OVERNIGHT, TARGET, 0),
])
def test_projection_and_catalog_only_extend_valid_native_nhl(sport, provider, now, start, target, expected):
    from dataclasses import replace
    snapshot = adapt_research_matchwinner(sport,
        event(sport, starts_at=start.isoformat(), source_observed_at=now.isoformat()),
        history(sport), modeled_at=now).snapshot
    if provider != snapshot.team_sport_forecast.provider:
        from riskobet_domain import stable_event_key
        snapshot = replace(snapshot, event_key=stable_event_key(sport, provider, 'future-match'),
            customer_recent_results=None, team_sport_forecast=replace(snapshot.team_sport_forecast, provider=provider))
    run = SimpleNamespace(snapshots=(snapshot,))
    rows = team_sport_forecast_rows(run, now=now, target_date=target)
    assert len(rows) == expected
    # Generate valid immutable rows on the actual game date independently of
    # automatic admission: an empty projection must not hide a catalog bug.
    game_date_rows = team_sport_forecast_rows(run, now=now,
        target_date=start.astimezone(ZoneInfo('Europe/Zurich')).date())
    assert len(game_date_rows) == 2
    assert len(_ranked_candidates(game_date_rows, now=now, target_date=target)) == expected
    assert team_sport_source_coverage(run, rows, now=now, target_date=target)[sport]['snapshot_count'] == (1 if expected else 0)


@pytest.mark.parametrize('now', [datetime(2026, 3, 28, 2, 35, tzinfo=timezone.utc),
    datetime(2026, 10, 24, 1, 35, tzinfo=timezone.utc)])
def test_dst_horizon_is_elapsed_24_hours_not_local_day(monkeypatch, now):
    target = now.astimezone(ZoneInfo('Europe/Zurich')).date()
    batch, _, _, windows = daily_batch(monkeypatch,
        [now+timedelta(hours=24), now+timedelta(hours=24, seconds=1)], now=now, target=target)
    assert len(batch.snapshots) == 1
    assert batch.snapshots[0].starts_at == now+timedelta(hours=24)
    assert windows == [(target, target)]


def test_historical_daily_target_cannot_borrow_current_rolling_games(monkeypatch):
    batch, _, _, _ = daily_batch(monkeypatch, [OVERNIGHT], target=TARGET-timedelta(days=1))
    assert batch.snapshots == ()


def test_daily_history_and_collector_share_only_post_schedule_eligible_events(monkeypatch):
    captured = []
    clocks = iter((NOW, NOW+timedelta(seconds=5), NOW+timedelta(seconds=10)))
    batch, _, calls, windows = daily_batch(monkeypatch,
        [NOW+timedelta(seconds=3), OVERNIGHT, NOW+timedelta(hours=24, seconds=6)],
        collector=lambda **kw: captured.append(kw), clock=lambda: next(clocks))
    assert len(batch.snapshots) == 1
    assert batch.snapshots[0].starts_at == OVERNIGHT
    assert batch.snapshots[0].team_sport_forecast.source_observed_at == NOW+timedelta(seconds=5)
    assert batch.snapshots[0].modeled_at == NOW+timedelta(seconds=10)
    assert len(captured) == 1
    assert [r['game_id'] for r in captured[0]['events']] == [2026020002]
    assert len(calls) == 1 and windows == [(TARGET, TARGET)]


def test_daily_horizon_does_not_model_game_started_during_history(monkeypatch):
    captured = []
    clocks = iter((NOW, NOW+timedelta(seconds=5), NOW+timedelta(seconds=10)))
    batch, _, _, _ = daily_batch(monkeypatch, [NOW+timedelta(seconds=8)],
        collector=lambda **kw: captured.append(kw), clock=lambda: next(clocks))
    assert len(captured) == 1
    assert batch.snapshots == ()


def test_same_day_automatic_opt_in_preserves_baseline_full_model_snapshot(monkeypatch):
    start = NOW+timedelta(hours=12)
    source_fixture(monkeypatch, [start])
    baseline = _default_ice_hockey_risk_source(TARGET, NOW)
    sources, _ = _riskobet_default_sources({}, now=NOW, target_date=TARGET,
        research_due=True, clock=lambda: NOW)
    automatic = sources['ice_hockey']()
    assert len(automatic.snapshots) == 1
    assert automatic.snapshots == baseline.snapshots
    assert automatic.candidates == baseline.candidates


def test_catalog_does_not_extend_nhl_exception_from_forged_provider_label():
    snapshot = adapt_research_matchwinner('basketball',
        event(starts_at=OVERNIGHT.isoformat(), source_observed_at=NOW.isoformat()),
        history(), modeled_at=NOW).snapshot
    rows = team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)), now=NOW,
        target_date=OVERNIGHT.astimezone(ZoneInfo('Europe/Zurich')).date())
    assert len(rows) == 2
    assert _ranked_candidates(rows, now=NOW, target_date=TARGET) == []
    forged = [dict(row, fixture_source='NHL', sport='Eishockey') for row in rows]
    assert _ranked_candidates(forged, now=NOW, target_date=TARGET) == []
