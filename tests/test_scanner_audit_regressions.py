"""Offline regressions for the October 2 scanner audit, not betting-quality evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import threading
import time

import pytest

import advanced_analyzer as advanced
import challenge_engine as engine
import scan_jobs
import shadow_clv_automation as shadow
from scripts import run_football_shadow_due as shadow_job
from tests.test_football_original_capture import values


def test_count_market_uses_its_own_required_history_age():
    fixture, history = values()
    kickoff = engine._fixture_datetime(fixture)
    for row in history:
        row['fixture']['date'] = (engine._fixture_datetime(row) - timedelta(days=60)).isoformat()
    fresh = []
    for number in range(6):
        for home, away in ((1, 3), (4, 2)):
            row = deepcopy(history[0])
            row['fixture']['id'] = 8000 + len(fresh)
            row['fixture']['date'] = (kickoff - timedelta(days=number + 1)).isoformat()
            row['teams']['home']['id'], row['teams']['away']['id'] = home, away
            row['challenge_stats'] = {}
            fresh.append(row)
    model = engine.fixture_market_probabilities(fixture, history + fresh)
    assert model['freshness_days'] < 10
    assert model['count_models']['corners']['freshness_days'] > 60
    candidates = engine.build_fixture_candidates(fixture, history + fresh, {})
    corner = next(c for c in candidates if c.market_key == 'CORNERS_OVER_5_5')
    assert 'Letzte Formbeobachtung ist zu alt' in corner.blocked_reasons


def test_projection_failure_is_confined_to_its_own_family(monkeypatch):
    import football_joint_calibration as joint
    original = joint.calibrate_joint_distribution
    def fail_corners(matrix, specs, calibration):
        effective, diagnostics = original(matrix, specs, calibration)
        if specs[0].kind in {'corner_total', 'team_corners'}:
            return matrix, {**diagnostics, 'success': False, 'status': 'raw-fallback'}
        return effective, diagnostics
    monkeypatch.setattr(joint, 'calibrate_joint_distribution', fail_corners)
    fixture, history = values()
    candidates = engine.build_fixture_candidates(fixture, history, {})
    result = next(c for c in candidates if c.market_key == 'RESULT_HOME')
    corner = next(c for c in candidates if c.market_key == 'CORNERS_OVER_5_5')
    assert not any('Kalibrierung fehlgeschlagen' in reason for reason in result.blocked_reasons)
    assert any('Kalibrierung fehlgeschlagen' in reason for reason in corner.blocked_reasons)


def test_old_generation_cannot_persist_after_clear_and_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_jobs, 'JOBS_DIR', tmp_path)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    key = 'oct2-persistence-generation'
    def old_payload(value):
        started.set()
        assert release.wait(5), 'test publication watchdog'
        return {'value': value}
    original_persist = scan_jobs._persist
    def observe(name, payload, **kwargs):
        try:
            return original_persist(name, payload, **kwargs)
        finally:
            if payload['value'] == 'old':
                finished.set()
    monkeypatch.setattr(scan_jobs, '_persist', observe)
    try:
        assert scan_jobs.start_job(key, lambda progress_cb: 'old',
            persist_name='same', persist_fn=old_payload)
        assert started.wait(5)
        scan_jobs.clear_job(key)
        assert scan_jobs.start_job(key, lambda progress_cb: 'new',
            persist_name='same', persist_fn=lambda value: {'value': value})
        deadline = time.monotonic() + 5
        while scan_jobs.get_job(key)['state'] != 'done' and time.monotonic() < deadline:
            time.sleep(.01)
        assert scan_jobs.get_job(key)['result'] == 'new'
        release.set()
        assert finished.wait(5)
        assert scan_jobs.load_persisted('same')['value'] == 'new'
    finally:
        release.set()
        scan_jobs.clear_job(key)


def test_analyzer_cache_expires_and_failure_does_not_reuse_stale_stats(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(advanced.time, 'monotonic', lambda: clock[0])
    state = {'value': 1., 'calls': 0, 'fail': False}
    class API:
        def __init__(self, *_args): pass
        def get_team_statistics(self, *_args):
            state['calls'] += 1
            if state['fail']: return None
            return {'btts_rate_home': 50., 'btts_rate_total': 50.,
                'avg_goals_scored_home': state['value'], 'avg_goals_conceded_home': 1.,
                'btts_sample_home': 5, 'btts_sample_total': 10}
    monkeypatch.setattr('api_football.APIFootball', API)
    analyzer = advanced.AdvancedBTTSAnalyzer.__new__(advanced.AdvancedBTTSAnalyzer)
    analyzer._team_stats_cache = {}
    analyzer.api_football_key = 'offline'
    assert analyzer._get_season_stats(1, 39, 'home')['avg_scored'] == 1
    state['value'] = 4.
    assert analyzer._get_season_stats(1, 39, 'home')['avg_scored'] == 1
    assert state['calls'] == 1
    clock[0] += advanced.STATS_CACHE_TTL_SECONDS
    assert analyzer._get_season_stats(1, 39, 'home')['avg_scored'] == 4
    state['fail'] = True
    clock[0] += advanced.STATS_CACHE_TTL_SECONDS
    assert analyzer._get_season_stats(1, 39, 'home') is None
    assert analyzer._get_season_stats(1, 39, 'home') is None
    assert state['calls'] == 3  # bounded failure retry, no stale-as-fresh fallback


def test_shadow_failed_schedule_is_not_completed_and_only_failed_league_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, 'SHADOW_DB', tmp_path / 'shadow.db')
    clock = [datetime(2026, 10, 2, 12, tzinfo=timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]
    monkeypatch.setattr(shadow, 'datetime', Clock)
    day = clock[0].date()
    calls = []
    def fixtures(league, *_args):
        calls.append(league)
        return None if league == 40 and calls.count(40) == 1 else []
    provider = SimpleNamespace(fixtures_by_date=fixtures)
    shadow.errors.clear()
    assert shadow.step_schedule(provider, [39, 40], day, False) == 0
    with shadow._connect() as connection:
        assert shadow._meta_get(connection, shadow._schedule_marker(day, [39, 40])) is None
    assert shadow.step_schedule(provider, [39, 40], day, False) == 0
    assert calls == [39, 40]  # retry cooldown, successful empty answer retained
    clock[0] += shadow.SCHEDULE_RETRY_DELAY
    assert shadow.step_schedule(provider, [39, 40], day, False) == 0
    assert calls == [39, 40, 40]
    with shadow._connect() as connection:
        assert shadow._meta_get(connection, shadow._schedule_marker(day, [39, 40])) is not None
        assert shadow._meta_get(connection, shadow._schedule_marker(day, [39, 40, 41])) is None


def test_schedule_attempts_are_bounded_even_when_forced(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, 'SHADOW_DB', tmp_path / 'shadow.db')
    calls = []
    provider = SimpleNamespace(fixtures_by_date=lambda *args: calls.append(args) or None)
    day = datetime(2026, 10, 2, tzinfo=timezone.utc).date()
    for _ in range(8):
        shadow.errors.clear()
        shadow.step_schedule(provider, [39], day, True)
        assert shadow.errors, 'exhausted failures must not become a successful run'
    assert len(calls) == shadow.SCHEDULE_MAX_ATTEMPTS
    with shadow._connect() as connection:
        assert shadow._meta_get(connection, shadow._schedule_marker(day, [39])) is None


def test_shadow_unreadable_database_is_error_not_idle(tmp_path, monkeypatch):
    path = tmp_path / 'broken.db'
    path.write_bytes(b'not a sqlite database')
    monkeypatch.setattr(shadow_job.shadow, 'should_fire',
        lambda _ctx: shadow._shadow_work_due(datetime(2026, 10, 2, 12, tzinfo=timezone.utc), path))
    assert shadow_job.main() == 1


def test_shadow_wrapper_returns_failure_for_reported_errors(monkeypatch):
    monkeypatch.setattr(shadow_job.shadow, 'should_fire', lambda _ctx: True)
    monkeypatch.setattr(shadow_job.shadow, 'run', lambda _ctx: {'artifact': {'errors': ['fixtures HTTP 500']}})
    assert shadow_job.main() == 1
