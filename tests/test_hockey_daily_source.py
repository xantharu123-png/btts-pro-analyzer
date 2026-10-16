"""Offline daily-owner trace: fixture sources, real hockey model mathematics.

Synthetic schedules/history prove wiring, not provider entitlement, live league
coverage, calibration, injury effects, or a profitable betting strategy.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import json
import sqlite3
from types import SimpleNamespace

import pytest

import scanners.hockey_scanner as hockey
import forecast_evidence
from config_loader import AppConfig
from ev_signal_sources import automated_wettfinder_forecasts
from riskobet_automation import load_latest_riskobet, run_riskobet
from riskobet_domain import EvidenceStage, stable_event_key
from riskobet_store import RiskBetStore
from sports_prematch import API_HOCKEY_MODEL_VERSION, MODEL_VERSION, predict_prematch
from team_sport_forecasts import team_sport_forecast_rows, valid_research_row
from team_sport_prices import _binding, snapshot_price_rows
from tip_publication import compact_signal_row
from wettfinder_automation import _default_ice_hockey_risk_source, run_wettfinder
from test_api_hockey_integration import api_event, api_history
from test_sports_prematch import NOW, event, history


def fixture_sources(monkeypatch, *, nhl_events=None, api_events=None, api_error=None):
    calls = []
    nhl_events = [event('ice_hockey')] if nhl_events is None else nhl_events
    api_events = [api_event()] if api_events is None else api_events

    def schedule(provider, rows, start, end):
        calls.append((provider, 'schedule', start, end))
        return deepcopy(rows)

    def completed(provider, rows, start, end, *, as_of, events=None):
        calls.append((provider, 'history', start, end, as_of))
        return deepcopy(rows)

    nhl = SimpleNamespace(errors={}, history_coverage={'status': 'complete'},
        get_upcoming_nhl_games=lambda start, end: schedule('NHL', nhl_events, start, end),
        get_completed_nhl_games=lambda start, end, **kwargs:
            completed('NHL', history('ice_hockey'), start, end, **kwargs))
    api = SimpleNamespace(errors={'schedule': api_error} if api_error else {},
        history_coverage={'status': 'partial' if api_error else 'complete'},
        get_upcoming_games=lambda start, end: schedule('API-Hockey', api_events, start, end),
        get_completed_games=lambda start, end, **kwargs:
            completed('API-Hockey', api_history(), start, end, **kwargs))
    scanner = hockey.HockeyScanner(nhl=nhl, api=api)
    monkeypatch.setattr(hockey, 'HockeyScanner', lambda: scanner)
    return scanner, calls


def test_default_daily_hockey_hook_uses_both_sources_once_and_keeps_native_publications(monkeypatch):
    scanner, calls = fixture_sources(monkeypatch)
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert not batch.errors
    assert len(batch.snapshots) == len(batch.candidates) == 2
    assert calls == [
        ('NHL', 'schedule', NOW.date(), NOW.date()),
        ('API-Hockey', 'schedule', NOW.date(), NOW.date()),
        ('NHL', 'history', NOW.date()-timedelta(days=365), NOW.date(), NOW),
        ('API-Hockey', 'history', NOW.date()-timedelta(days=365), NOW.date(), NOW),
    ]
    assert scanner.history_coverage == {'status': 'complete', 'pending_observations': 0}
    expected = {
        'NHL': predict_prematch('ice_hockey', event('ice_hockey'), history('ice_hockey'), NOW),
        'API-Hockey': predict_prematch('ice_hockey', api_event(), api_history(), NOW),
    }
    for snapshot in batch.snapshots:
        forecast = snapshot.team_sport_forecast
        calculated = expected[forecast.provider]
        assert forecast.p_home == pytest.approx(calculated.p_home)
        assert forecast.model_input_hash == calculated.input_hash
        assert forecast.training_games == 84
        assert forecast.model_version == (API_HOCKEY_MODEL_VERSION if forecast.provider == 'API-Hockey' else MODEL_VERSION)
        assert snapshot.event_key == stable_event_key('ice_hockey', forecast.provider, forecast.provider_event_id)
        assert forecast.p_home_regulation <= forecast.p_home <= forecast.p_home_regulation + forecast.p_draw_regulation
    assert all(candidate.stage is EvidenceStage.RESEARCH for candidate in batch.candidates)
    rows = team_sport_forecast_rows(batch, now=NOW, target_date=NOW.date())
    assert len(rows) == 4
    assert all(valid_research_row(row, now=NOW) for row in rows)
    assert all(row['statistical_release_passed'] is False for row in rows)
    for row in rows:
        compact = compact_signal_row(row)
        assert compact['event_key'] == row['event_identity']
        assert compact['snapshot_id'] == row['team_sport_snapshot']['snapshot_id']
    native_prices = [row for row in snapshot_price_rows(batch.snapshots) if row['fixture_source'] == 'API-Hockey']
    assert len(native_prices) == 2
    assert all(_binding(row)[7:] == ('1', '8') for row in native_prices)


def test_unavailable_paid_hockey_source_does_not_remove_existing_nhl_model(monkeypatch):
    _, calls = fixture_sources(monkeypatch, api_events=[], api_error='entitlement_missing')
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert len(batch.snapshots) == 1 and batch.snapshots[0].team_sport_forecast.provider == 'NHL'
    assert batch.snapshots[0].team_sport_forecast.p_home is not None
    assert batch.errors == ('entitlement_missing',)
    assert [call[0] for call in calls if call[1] == 'history'] == ['NHL']
    assert len(team_sport_forecast_rows(batch, now=NOW, target_date=NOW.date())) == 2


def test_api_only_day_does_not_load_unneeded_nhl_history(monkeypatch):
    _, calls = fixture_sources(monkeypatch, nhl_events=[])
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert len(batch.snapshots) == 1 and batch.snapshots[0].team_sport_forecast.provider == 'API-Hockey'
    assert batch.snapshots[0].team_sport_forecast.p_home is not None
    assert [call[0] for call in calls if call[1] == 'history'] == ['API-Hockey']
    assert all(candidate.stage is EvidenceStage.RESEARCH for candidate in batch.candidates)


def test_explicit_daily_history_loader_is_not_followed_by_a_second_scanner_history(monkeypatch):
    _, calls = fixture_sources(monkeypatch)
    history_calls = []

    def own_history(**kwargs):
        history_calls.append(kwargs)
        return history('ice_hockey') + api_history()

    batch = _default_ice_hockey_risk_source(NOW.date(), NOW, history_loader=own_history)
    assert len(batch.snapshots) == 2 and not batch.errors
    assert len(history_calls) == 1
    assert history_calls[0]['sport'] == 'ice_hockey' and history_calls[0]['as_of'] == NOW
    assert {row['provider'] for row in history_calls[0]['events']} == {'NHL', 'API-Hockey'}
    assert not any(call[1] == 'history' for call in calls)


def test_started_events_do_not_trigger_historical_load_or_daily_publication(monkeypatch):
    _, calls = fixture_sources(monkeypatch,
        nhl_events=[event('ice_hockey', starts_at=(NOW-timedelta(minutes=1)).isoformat())], api_events=[])
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert batch.snapshots == batch.candidates == ()
    assert not any(call[1] == 'history' for call in calls)
    assert team_sport_forecast_rows(batch, now=NOW, target_date=NOW.date()) == []


def test_actual_schedule_receipt_after_owner_start_uses_post_history_model_clock(monkeypatch):
    received = NOW + timedelta(seconds=5)
    history_cutoff, modeled = NOW + timedelta(seconds=6), NOW + timedelta(seconds=10)
    _, calls = fixture_sources(monkeypatch, nhl_events=[],
        api_events=[dict(api_event(), source_observed_at=received.isoformat())])
    clocks = iter((history_cutoff, modeled))
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW, clock=lambda: next(clocks))
    assert not batch.errors and len(batch.snapshots) == 1
    snapshot = batch.snapshots[0]
    forecast = snapshot.team_sport_forecast
    assert forecast.provider == 'API-Hockey' and forecast.p_home is not None
    assert forecast.source_observed_at == received  # Never backdate the receipt to NOW.
    assert snapshot.modeled_at == forecast.modeled_at == snapshot.input_cutoff_at == modeled
    assert [call[-1] for call in calls if call[1] == 'history'] == [history_cutoff]
    # The actual model, not a substituted chance, consumed the same older history.
    expected = predict_prematch('ice_hockey', dict(api_event(), source_observed_at=received.isoformat()), api_history(), modeled)
    assert forecast.p_home == pytest.approx(expected.p_home)
    assert forecast.model_input_hash == expected.input_hash
    rows = team_sport_forecast_rows(batch, now=modeled, target_date=NOW.date())
    assert len(rows) == 2 and all(valid_research_row(row, now=modeled) for row in rows)


def test_event_starting_during_history_is_not_modeled_or_published(monkeypatch):
    _, calls = fixture_sources(monkeypatch,
        api_events=[dict(api_event(), starts_at=(NOW+timedelta(seconds=8)).isoformat(),
                         source_observed_at=(NOW+timedelta(seconds=5)).isoformat())])
    clocks = iter((NOW+timedelta(seconds=6), NOW+timedelta(seconds=10)))
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW, clock=lambda: next(clocks))
    assert not batch.errors and len(batch.snapshots) == 1
    assert batch.snapshots[0].team_sport_forecast.provider == 'NHL'
    assert [call[-1] for call in calls if call[1] == 'history'] == [NOW+timedelta(seconds=6)]*2
    assert all(row['fixture_source'] == 'NHL' for row in
               team_sport_forecast_rows(batch, now=NOW+timedelta(seconds=10), target_date=NOW.date()))


def test_repaired_schedule_does_not_retain_stale_wrapper_error(monkeypatch):
    scanner, _ = fixture_sources(monkeypatch, api_events=[], api_error='entitlement_missing')
    assert scanner.get_upcoming_games(NOW.date(), NOW.date())
    assert scanner.errors
    scanner.api.errors.clear()
    scanner.api.get_upcoming_games = lambda *args: [api_event()]
    repaired = scanner.get_upcoming_games(NOW.date(), NOW.date())
    assert {row['provider'] for row in repaired} == {'NHL', 'API-Hockey'}
    assert scanner.errors == {}


def test_repaired_history_does_not_retain_stale_wrapper_error_or_partial_coverage(monkeypatch):
    scanner, _ = fixture_sources(monkeypatch)
    events = scanner.get_upcoming_games(NOW.date(), NOW.date())
    scanner.api.errors['history'] = 'provider_response_error'
    scanner.api.history_coverage = {'status': 'partial'}
    first = scanner.get_completed_games(NOW.date()-timedelta(days=365), NOW.date(), as_of=NOW, events=events)
    assert len(first) == 168 and scanner.errors and scanner.history_coverage['status'] == 'partial'
    scanner.api.errors.clear()
    scanner.api.history_coverage = {'status': 'complete'}
    repaired = scanner.get_completed_games(NOW.date()-timedelta(days=365), NOW.date(), as_of=NOW, events=events)
    assert len(repaired) == 168 and scanner.errors == {}
    assert scanner.history_coverage['status'] == 'complete'


def test_unexpected_api_schedule_failure_retains_valid_nhl_discovery(monkeypatch):
    scanner, _ = fixture_sources(monkeypatch)

    def failed(*args, **kwargs):
        raise RuntimeError('synthetic transport failure')

    scanner.api.get_upcoming_games = failed
    found = scanner.get_upcoming_games(NOW.date(), NOW.date())
    assert len(found) == 1 and found[0]['provider'] == 'NHL'
    assert scanner.errors  # Retention is not a false all-sources-success claim.
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert len(batch.snapshots) == 1 and batch.snapshots[0].team_sport_forecast.p_home is not None
    assert batch.errors


def test_unexpected_api_history_failure_retains_nhl_results_and_partial_coverage(monkeypatch):
    scanner, _ = fixture_sources(monkeypatch)
    events = scanner.get_upcoming_games(NOW.date(), NOW.date())

    def failed(*args, **kwargs):
        raise RuntimeError('synthetic transport failure')

    scanner.api.get_completed_games = failed
    found = scanner.get_completed_games(NOW.date()-timedelta(days=365), NOW.date(), as_of=NOW, events=events)
    assert len(found) == 84 and all(row['provider'] == 'NHL' for row in found)
    assert scanner.errors and scanner.history_coverage['status'] == 'partial'
    batch = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert len(batch.snapshots) == 2
    forecasts = {s.team_sport_forecast.provider: s.team_sport_forecast for s in batch.snapshots}
    assert forecasts['NHL'].p_home is not None
    assert forecasts['API-Hockey'].p_home is None and forecasts['API-Hockey'].missing
    assert batch.errors


def test_real_risk_run_persists_completion_after_actual_hockey_model_clock(monkeypatch, tmp_path):
    fixture_sources(monkeypatch, nhl_events=[],
        api_events=[dict(api_event(), source_observed_at=(NOW+timedelta(seconds=5)).isoformat())])
    source_clocks = iter((NOW+timedelta(seconds=6), NOW+timedelta(seconds=10)))
    store = RiskBetStore(tmp_path/'riskobet.db', tmp_path/'latest.json')
    run = run_riskobet(ice_hockey_source=lambda: _default_ice_hockey_risk_source(
        NOW.date(), NOW, clock=lambda: next(source_clocks)), store=store,
        now=NOW, clock=lambda: NOW+timedelta(seconds=12))
    assert run.started_at == NOW and run.completed_at == NOW+timedelta(seconds=12)
    assert len(run.snapshots) == 1
    assert run.snapshots[0].modeled_at == NOW+timedelta(seconds=10) <= run.completed_at
    assert run.snapshots[0].team_sport_forecast.p_home is not None
    restored = load_latest_riskobet(store=store, rehydrate=True)
    assert restored.to_dict() == run.to_dict()
    assert restored.completed_at >= restored.snapshots[0].modeled_at


def test_live_owner_publication_clock_preserves_fresh_hockey_rows_for_real_readers(monkeypatch, tmp_path):
    """Actual model, store, evidence recorder and reader share one causal clock.

    No fixed ``now`` is passed to the owner: its publication must follow the
    later child computation, not retain the pre-loader time. All transports
    below return fixtures; neither a provider nor a production path is used.
    """
    received = NOW + timedelta(seconds=5)
    modeled = NOW + timedelta(seconds=10)
    finished = NOW + timedelta(seconds=12)
    recorded = NOW + timedelta(seconds=13)
    _, calls = fixture_sources(monkeypatch,
        api_events=[dict(api_event(), source_observed_at=received.isoformat())])
    source_clocks = iter((NOW+timedelta(seconds=6), modeled))
    runtime = [NOW]
    sources = {sport: () for sport in
               ('football', 'tennis', 'basketball', 'ice_hockey', 'cricket', 'esports')}
    sources['ice_hockey'] = lambda: _default_ice_hockey_risk_source(
        NOW.date(), NOW, clock=lambda: next(source_clocks))
    monkeypatch.setattr(forecast_evidence, '_now', lambda: recorded)

    def real_runner(**kwargs):
        assert kwargs['now'] == NOW
        run = run_riskobet(**kwargs, clock=lambda: finished)
        runtime[0] = run.completed_at
        return run

    empty_football = {
        'scanned_at': NOW.isoformat(), 'fixtures_found': 0, 'fixtures_modeled': 0,
        'base_candidates': 0, 'base_fixture_count': 0, 'context_fixtures': 0,
        'context_verified_fixtures': 0, 'context_data_incomplete_fixtures': 0,
        'context_unchecked_fixtures': 0, 'deferred_context_fixtures': 0,
        'context_scope_complete': True, 'context_fixture_statuses': {},
        'fixture_kickoffs': {}, 'shortlist': [], 'errors': [],
    }
    state_path, evidence_path = tmp_path/'wettfinder.json', tmp_path/'forecast_evidence.db'
    document = run_wettfinder(
        clock=lambda: runtime[0], state_path=state_path,
        config=AppConfig(api_football_key='offline-fixture'),
        football_scanner=lambda _day: deepcopy(empty_football),
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda *_args, **_kwargs: ({}, []),
        tennis_quote_loader=lambda *_args, **_kwargs: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
        riskobet_enabled=True, riskobet_runner=real_runner, riskobet_sources=sources,
        evidence_db_path=evidence_path,
    )
    assert document['run_status'] == 'completed' and document['operational_error_count'] == 0
    assert document['riskobet']['status'] == 'complete'
    assert document['generated_at'] == finished.isoformat()
    assert len(document['model_candidates']) == 4
    assert all(datetime.fromisoformat(row['modeled_at']) == modeled <= finished
               for row in document['model_candidates'])
    assert {row['fixture_source'] for row in document['model_candidates']} == {'NHL', 'API-Hockey'}
    assert document['forecast_evidence']['status'] == 'completed'
    assert document['forecast_evidence']['recorded'] == 4
    assert document['forecast_evidence']['rejected_count'] == 0
    assert document['team_sport_prices']['status'] == 'not_requested_for_isolated_run'

    # Read the persisted owner artifact through the actual customer loader.
    forecasts = automated_wettfinder_forecasts(state_path, now=recorded)
    assert len(forecasts) == 4
    assert {row.fixture_source for row in forecasts} == {'NHL', 'API-Hockey'}
    assert all(row.statistical_release_passed is False for row in forecasts)
    assert all(datetime.fromisoformat(row.modeled_at) == modeled for row in forecasts)
    with sqlite3.connect(evidence_path.resolve().as_uri()+'?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        evidence_rows = connection.execute('SELECT decision_at,payload_json FROM forecast_rows').fetchall()
    assert len(evidence_rows) == 4
    assert all(decision == finished.isoformat() for decision, _ in evidence_rows)
    assert all(json.loads(payload)['modeled_at'] == modeled.isoformat() for _, payload in evidence_rows)
    assert [call[-1] for call in calls if call[1] == 'history'] == [NOW+timedelta(seconds=6)]*2
    assert len(calls) == 4  # Two fixture schedules plus two fixture histories only.


@pytest.mark.parametrize('start_seconds,finish_seconds,error', [
    (0, 9, 'source model clock'), (11, 10, 'started_at'),
])
def test_invalid_run_completion_fails_before_any_append(monkeypatch, tmp_path, start_seconds, finish_seconds, error):
    fixture_sources(monkeypatch, nhl_events=[],
        api_events=[dict(api_event(), source_observed_at=(NOW+timedelta(seconds=5)).isoformat())])
    source_clocks = iter((NOW+timedelta(seconds=6), NOW+timedelta(seconds=10)))
    store = RiskBetStore(tmp_path/'riskobet.db', tmp_path/'latest.json')
    appended = []

    def unexpected_append(run):
        appended.append(run)
        raise AssertionError('An invalid completion must not reach the persistent append')

    monkeypatch.setattr(store, 'append_run', unexpected_append)
    with pytest.raises(ValueError, match=error):
        run_riskobet(ice_hockey_source=lambda: _default_ice_hockey_risk_source(
            NOW.date(), NOW, clock=lambda: next(source_clocks)), store=store,
            now=NOW+timedelta(seconds=start_seconds), clock=lambda: NOW+timedelta(seconds=finish_seconds))
    assert appended == [] and not store.latest_path.exists()
    with sqlite3.connect(store.db_path.resolve().as_uri()+'?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        assert connection.execute('SELECT count(*) FROM runs').fetchone()[0] == 0


@pytest.mark.parametrize('method,start,end,kwargs', [
    ('get_upcoming_games', NOW.date(), NOW.date()+timedelta(days=15), {}),
    ('get_upcoming_games', NOW.date(), NOW.date()-timedelta(days=1), {}),
    ('get_upcoming_games', NOW, NOW.date(), {}),
    ('get_completed_games', NOW.date(), NOW.date()-timedelta(days=1), {}),
    ('get_completed_games', NOW.date(), NOW.date(), {'as_of': NOW.replace(tzinfo=None)}),
])
def test_invalid_wrapper_window_or_naive_cutoff_fails_before_provider_methods(monkeypatch, method, start, end, kwargs):
    scanner, calls = fixture_sources(monkeypatch)
    with pytest.raises(ValueError):
        getattr(scanner, method)(start, end, **kwargs)
    assert calls == []
