"""Real capture seam with synthetic fixtures; never model-effect qualification."""
from copy import deepcopy
from datetime import timedelta
import importlib
import json
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_observations import append_observation
from context_sources.outcomes import normalize_football_base_input
from test_context_football_capture import stored
from test_football_context_provider import NOW, payload, provider, sample


def implementation():
    return importlib.import_module('context_sources.football_appearances')


def completed(identity=None, *, details=False):
    raw = deepcopy(sample()['calls'][0]['samples'][0])
    if identity is not None:
        raw['fixture']['id'] = identity
    if not details:
        for name in ('players', 'lineups', 'statistics', 'events'):
            raw.pop(name, None)
    return raw


def seed(path, raw, clock):
    record = normalize_football_base_input(raw, observed_at=clock)
    return append_observation(path, record, observed_at=clock)


def test_known_result_gets_one_budgeted_full_detail_and_real_player_minutes(tmp_path, monkeypatch):
    from api_budget import APIBudgetPriority
    path = tmp_path / 'context.db'
    original_ref = seed(path, completed(), NOW - timedelta(minutes=2))
    original = stored(path)
    owner, calls = provider(monkeypatch, details=payload([completed(details=True)]))
    monkeypatch.setattr(owner, '_context_received_at', lambda: NOW)
    report = implementation().refresh_football_appearances(owner, path=path, now=NOW)
    assert len(calls) == 1
    assert calls[0][1]['params'] == {'ids': str(completed()['fixture']['id'])}
    assert calls[0][1]['priority'] == APIBudgetPriority.BACKGROUND
    assert calls[0][1]['allow_redirects'] is False
    assert report['requested_count'] == 1 and report['status'] == 'player_data_captured'
    assert report['player_record_count'] == 46 and report['player_fixture_count'] == 1
    after = stored(path)
    appearances = [row for row in after if row['kind'] == 'appearance']
    assert len(appearances) == 46
    assert any(row['payload']['regulation_minutes'] == 90 for row in appearances)
    assert all(row['observed_at'] == canonical_timestamp(NOW) for row in appearances)
    assert all(row['published_at'] is None for row in appearances)
    assert next(row for row in after if row['digest'] == original_ref) == original[0]
    assert owner._context_capture is None


def test_recent_detail_avoids_redundant_fetch_after_summary_without_certifying_consumer_reuse(tmp_path, monkeypatch):
    path = tmp_path / 'context.db'
    seed(path, completed(details=True), NOW - timedelta(minutes=3))
    seed(path, completed(), NOW - timedelta(minutes=1))
    owner, calls = provider(monkeypatch)
    result = implementation().refresh_football_appearances(owner, path=path, now=NOW)
    assert calls == [] and result['requested_count'] == 0
    assert result['status'] == 'no_request_due'
    assert result['player_record_count'] == result['player_fixture_count'] == 0


def test_empty_detail_has_one_day_backoff_and_is_not_complete_player_coverage(tmp_path, monkeypatch):
    path = tmp_path / 'context.db'
    raw = completed()
    raw['players'] = []
    seed(path, raw, NOW - timedelta(minutes=1))
    owner, calls = provider(monkeypatch)
    assert implementation().refresh_football_appearances(owner, path=path, now=NOW)['requested_count'] == 0
    assert calls == []
    ids = implementation().pending_appearance_ids(path, now=NOW + timedelta(days=1))
    assert ids == (raw['fixture']['id'],)


def test_missing_database_does_not_initialize_or_fetch(tmp_path, monkeypatch):
    path = tmp_path / 'missing.db'
    owner, calls = provider(monkeypatch)
    assert implementation().refresh_football_appearances(owner, path=path, now=NOW)['status'] == 'no_request_due'
    assert not path.exists() and calls == []
    assert list(tmp_path.iterdir()) == []


def test_selection_is_bounded_rotates_and_ignores_future_or_nonterminal_receipts(tmp_path):
    path = tmp_path / 'context.db'
    for number in range(1, 27):
        seed(path, completed(number), NOW - timedelta(minutes=1))
    seed(path, completed(80), NOW + timedelta(minutes=1))
    upcoming = completed(90)
    upcoming['fixture']['date'] = (NOW + timedelta(days=1)).isoformat()
    upcoming['fixture']['status']['short'] = 'NS'
    upcoming['goals'] = {'home': None, 'away': None}
    seed(path, upcoming, NOW - timedelta(minutes=1))
    module = implementation()
    first = module.pending_appearance_ids(path, now=NOW)
    second = module.pending_appearance_ids(path, now=NOW + timedelta(minutes=30))
    assert len(first) == len(second) == 20 and len(set(first)) == 20
    assert 80 not in first and 90 not in first and set(first) != set(second)


@pytest.mark.parametrize('field', ['goals', 'schedule', 'players'])
def test_changed_full_detail_or_new_result_does_not_reuse_wrong_revision(tmp_path, field):
    path = tmp_path / 'context.db'
    seed(path, completed(details=True), NOW - timedelta(minutes=2))
    newer = completed()
    if field == 'goals':
        newer['goals']['home'] += 1
    elif field == 'schedule':
        newer['fixture']['date'] = (NOW - timedelta(days=2)).isoformat()
    else:
        # Explicit empty is a fresh withdrawal: don't revive earlier players,
        # but also don't hammer that empty source again within the day.
        newer['players'] = []
    seed(path, newer, NOW - timedelta(minutes=1))
    ids = implementation().pending_appearance_ids(path, now=NOW)
    assert ids == (() if field == 'players' else (newer['fixture']['id'],))


def test_conflicting_latest_identity_is_not_selected_for_enrichment(tmp_path):
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    alternative = completed()
    alternative['teams']['home']['id'] += 1
    seed(path, alternative, NOW - timedelta(minutes=1))
    assert implementation().pending_appearance_ids(path, now=NOW) == ()


def test_invalid_stored_selected_receipt_fails_before_network(tmp_path, monkeypatch):
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    with sqlite3.connect(path) as con:
        con.execute('UPDATE context_contents SET payload=?', (b'{}',))
    owner, calls = provider(monkeypatch)
    with pytest.raises(ContextIntegrityError):
        implementation().refresh_football_appearances(owner, path=path, now=NOW)
    assert calls == []


def test_failed_request_does_not_fan_out_or_change_existing_history(tmp_path, monkeypatch):
    import requests
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    old = stored(path)
    owner, calls = provider(monkeypatch, details=requests.HTTPError('unavailable'))
    result = implementation().refresh_football_appearances(owner, path=path, now=NOW)
    assert len(calls) == 1 and result['status'] == 'unavailable'
    assert stored(path) == old and owner._context_capture is None


@pytest.mark.parametrize('limit', [True, 0, -1, 21, '20'])
def test_invalid_budget_rejected_before_read_or_fetch(tmp_path, limit):
    with pytest.raises(ValueError):
        implementation().pending_appearance_ids(tmp_path / 'missing.db', now=NOW, limit=limit)


@pytest.mark.parametrize('failure', ['summary', 'empty_response', 'empty_players', 'http', 'json', 'projection'])
def test_unsuccessful_player_capture_has_durable_one_day_retry_backoff(tmp_path, monkeypatch, failure):
    import requests
    path = tmp_path / 'context.db'
    raw = completed()
    seed(path, raw, NOW - timedelta(minutes=1))
    if failure == 'empty_response':
        response = payload([])
    elif failure == 'http':
        response = requests.HTTPError('unavailable')
    elif failure == 'json':
        response = ValueError('invalid JSON')
    else:
        returned = completed(details=failure == 'projection')
        if failure == 'empty_players':
            returned['players'] = []
        if failure == 'projection':
            returned['players'][0]['players'][0]['statistics'][0]['games']['minutes'] = 999
        response = payload([returned])
    owner, calls = provider(monkeypatch, details=response)
    monkeypatch.setattr(owner, '_context_received_at', lambda: NOW)
    module = implementation()
    first = module.refresh_football_appearances(owner, path=path, now=NOW)
    assert len(calls) == 1
    assert first['status'] not in {'captured', 'up_to_date', 'player_data_captured'}
    assert first['player_record_count'] == first['player_fixture_count'] == 0
    assert not any(row['kind'] == 'appearance' and row['subject_id'].startswith('api-football:player:')
                   for row in stored(path))
    state_path = module._attempt_state_path(path)
    state = json.loads(state_path.read_text(encoding='utf-8'))
    assert state == {'schema': 1, 'purpose': 'football-appearance-request-reservations',
                     'reservations': {module._attempt_key(module._identity(raw)): canonical_timestamp(NOW)}}
    assert all('observed_at' not in key for key in state)
    state_bytes = state_path.read_bytes()
    # Reload plus a fresh provider must not reset persisted operational state.
    module = importlib.reload(module)
    restarted, restarted_calls = provider(monkeypatch, details=response)
    monkeypatch.setattr(restarted, '_context_received_at', lambda: NOW + timedelta(days=1))
    second = module.refresh_football_appearances(restarted, path=path, now=NOW + timedelta(minutes=30))
    assert restarted_calls == [] and second['status'] == 'no_request_due'
    assert second['requested_count'] == 0 and state_path.read_bytes() == state_bytes
    assert module.pending_appearance_ids(path, now=NOW + timedelta(days=1) - timedelta(microseconds=1)) == ()
    assert module.pending_appearance_ids(path, now=NOW + timedelta(days=1)) == (raw['fixture']['id'],)
    module.refresh_football_appearances(restarted, path=path, now=NOW + timedelta(days=1))
    assert len(restarted_calls) == 1


@pytest.mark.parametrize('changed', ['goals', 'schedule', 'league', 'season', 'home', 'away'])
def test_request_backoff_does_not_cover_changed_native_identity(tmp_path, monkeypatch, changed):
    import requests
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    owner, calls = provider(monkeypatch, details=requests.HTTPError('unavailable'))
    module = implementation()
    module.refresh_football_appearances(owner, path=path, now=NOW)
    assert module.pending_appearance_ids(path, now=NOW + timedelta(seconds=1)) == ()
    revised = completed()
    if changed == 'goals':
        revised['goals']['home'] += 1
    elif changed == 'schedule':
        revised['fixture']['date'] = (NOW - timedelta(days=2)).isoformat()
    elif changed in {'league', 'season'}:
        revised['league']['id' if changed == 'league' else 'season'] += 1
    else:
        revised['teams'][changed]['id'] += 100
    seed(path, revised, NOW + timedelta(seconds=1))
    module.refresh_football_appearances(owner, path=path, now=NOW + timedelta(seconds=2))
    assert len(calls) == 2


def test_failed_first_batch_does_not_starve_unattempted_ids(tmp_path, monkeypatch):
    import requests
    path = tmp_path / 'context.db'
    for identity in range(1, 27):
        seed(path, completed(identity), NOW - timedelta(minutes=1))
    owner, calls = provider(monkeypatch, details=requests.HTTPError('unavailable'))
    module = implementation()
    first = module.refresh_football_appearances(owner, path=path, now=NOW)
    second = module.refresh_football_appearances(owner, path=path, now=NOW + timedelta(seconds=1))
    assert first['requested_count'] == 20 and second['requested_count'] == 6
    batches = [set(call[1]['params']['ids'].split('-')) for call in calls]
    assert len(calls) == 2 and batches[0].isdisjoint(batches[1])
    assert module.pending_appearance_ids(path, now=NOW + timedelta(minutes=30)) == ()


def test_reservation_failure_stops_before_network_and_keeps_history(tmp_path, monkeypatch):
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    before = stored(path)
    owner, calls = provider(monkeypatch)
    module = implementation()
    def fail(*_args, **_kwargs):
        raise OSError('reservation storage unavailable')
    monkeypatch.setattr(module, 'atomic_write_bytes', fail)
    with pytest.raises(OSError, match='reservation storage unavailable'):
        module.refresh_football_appearances(owner, path=path, now=NOW)
    assert calls == [] and stored(path) == before


def test_corrupt_reservation_state_fails_closed_without_request_or_overwrite(tmp_path, monkeypatch):
    import requests
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    owner, calls = provider(monkeypatch, details=requests.HTTPError('unavailable'))
    module = implementation()
    module.refresh_football_appearances(owner, path=path, now=NOW)
    state_path = module._attempt_state_path(path)
    damaged = b'{"schema":1,"purpose":"wrong","reservations":{}}'
    state_path.write_bytes(damaged)
    with pytest.raises(ContextIntegrityError, match='appearance request reservation'):
        module.refresh_football_appearances(owner, path=path, now=NOW + timedelta(minutes=30))
    assert len(calls) == 1 and state_path.read_bytes() == damaged


def test_older_worker_entry_clock_cannot_erase_newer_existing_reservation(tmp_path, monkeypatch):
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    owner, calls = provider(monkeypatch, details=payload([]))
    implementation().refresh_football_appearances(owner, path=path, now=NOW + timedelta(seconds=1))
    state_path = implementation()._attempt_state_path(path)
    saved = state_path.read_bytes()
    result = implementation().refresh_football_appearances(owner, path=path, now=NOW)
    assert len(calls) == 1 and result['requested_count'] == 0
    assert state_path.read_bytes() == saved


def test_concurrent_worker_sees_reservation_before_network_finishes(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    path = tmp_path / 'context.db'
    seed(path, completed(), NOW - timedelta(minutes=1))
    first, calls = provider(monkeypatch, details=payload([]))
    second = type(first)('test-key-never-persisted', None)
    entered, finish = Event(), Event()
    fetch = first._background_football_get
    def blocked(*args, **kwargs):
        entered.set()
        assert finish.wait(5)
        return fetch(*args, **kwargs)
    monkeypatch.setattr(first, '_background_football_get', blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(implementation().refresh_football_appearances, first, path=path, now=NOW)
        try:
            assert entered.wait(5)
            result = implementation().refresh_football_appearances(second, path=path, now=NOW)
            assert result['requested_count'] == 0
        finally:
            finish.set()
        assert future.result()['requested_count'] == 1
    assert len(calls) == 1


@pytest.mark.parametrize('production', [False, True])
def test_normal_worker_enriches_once_only_on_canonical_server_path(tmp_path, monkeypatch, production):
    import wettfinder_automation as automation
    from config_loader import AppConfig
    calls, owner = [], object()
    state = tmp_path / 'latest.json'
    if production:
        monkeypatch.setattr(automation, 'STATE_PATH', state)
    monkeypatch.setattr(automation, 'ChallengeDataProvider', lambda *_: owner)

    def enrich(actual, **kwargs):
        assert actual is owner and kwargs['now'] == NOW
        calls.append('history')
        return {'status': 'captured', 'requested_count': 2}

    monkeypatch.setattr(implementation(), 'refresh_football_appearances', enrich)
    result = automation.run_wettfinder(now=NOW, state_path=state,
        config=AppConfig(api_football_key='test'), riskobet_enabled=False,
        football_scanner=lambda _: {'scanned_at': NOW.isoformat(), 'fixtures_found': 0,
            'context_fixture_statuses': {}, 'shortlist': [], 'errors': []},
        tennis_loader=lambda **_: [], esports_loader=lambda **_: [],
        tennis_model_refresher=lambda **_: {'status': 'unchanged', 'errors': []},
        evidence_db_path=tmp_path / 'evidence.db',
        evidence_settlement_runner=lambda **_: {'operational_error_count': 0})
    assert calls == (['history'] if production else [])
    assert result.get('football_context_history') == (
        {'status': 'captured', 'requested_count': 2} if production else None)
    assert result['model_candidates'] == [] and result['candidates'] == []
