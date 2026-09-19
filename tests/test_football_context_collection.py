from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

import pytest
import football_context_collection as collection

NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def test_daily_limit_and_failed_attempts_are_not_refunded(tmp_path):
    path = tmp_path / 'capture.json'
    first = collection.reserve_original_capture(path, now=NOW)
    second = collection.reserve_original_capture(path, now=NOW)
    assert first == second and first['status'] == 'reserved'
    assert sum(first['limits'][key] for key in ('max_worker_payload_bytes', 'max_source_payload_bytes')) == collection.SESSION_BYTES
    before = path.read_bytes()
    assert collection.reserve_original_capture(path, now=NOW)['status'] == 'daily_limit'
    assert path.read_bytes() == before
    assert collection.reserve_original_capture(path, now=NOW + timedelta(days=1))['status'] == 'reserved'


def test_total_limit_cannot_be_reset_by_midnight_or_clock_reversal(tmp_path):
    path = tmp_path / 'capture.json'
    for day in range(collection.TOTAL_BYTES // collection.DAILY_BYTES):
        for _ in range(collection.DAILY_BYTES // collection.SESSION_BYTES):
            assert collection.reserve_original_capture(path, now=NOW + timedelta(days=day))['status'] == 'reserved'
    before = path.read_bytes()
    assert collection.reserve_original_capture(path, now=NOW + timedelta(days=30))['status'] == 'total_limit'
    assert collection.reserve_original_capture(path, now=NOW)['status'] == 'clock_before_reservation'
    assert path.read_bytes() == before


def test_concurrent_producers_share_one_reservation_limit(tmp_path):
    path = tmp_path / 'capture.json'
    with ThreadPoolExecutor(max_workers=4) as workers:
        statuses = list(workers.map(lambda _: collection.reserve_original_capture(path, now=NOW)['status'], range(6)))
    assert statuses.count('reserved') == 2
    assert statuses.count('daily_limit') == 4


@pytest.mark.parametrize('key,value', [('daily_reserved', True), ('total_reserved', -1),
                                      ('day', '20300101'), ('schema', 'unknown')])
def test_invalid_counter_is_not_reset(tmp_path, key, value):
    path = tmp_path / 'capture.json'
    collection.reserve_original_capture(path, now=NOW)
    data = json.loads(path.read_text())
    data[key] = value
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises((ValueError, collection.ContextIntegrityError)):
        collection.reserve_original_capture(path, now=NOW)
    assert path.read_bytes() == before


def test_no_space_and_naive_clock_do_not_allocate(tmp_path, monkeypatch):
    from types import SimpleNamespace
    path = tmp_path / 'capture.json'
    monkeypatch.setattr(collection.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1))
    assert collection.reserve_original_capture(path, now=NOW)['status'] == 'storage_reserve'
    assert not path.exists()
    with pytest.raises(ValueError):
        collection.reserve_original_capture(path, now=NOW.replace(tzinfo=None))


@pytest.mark.parametrize('production,explicit_scanner', [(True, False), (False, False), (True, True)])
def test_automatic_entry_connects_only_canonical_real_scanner(tmp_path, monkeypatch, production, explicit_scanner):
    import wettfinder_automation as automation
    import context_sources.football_appearances as appearances
    from config_loader import AppConfig
    seen = []
    def scan(*args, **kwargs):
        seen.append(kwargs.get('original_capture_limits'))
        return {'candidates': [], 'errors': [], 'operational_errors': [],
                'fixtures_found': 0, 'fixtures_modeled': 0}
    monkeypatch.setattr(automation, '_same_artifact_path', lambda *_: production)
    monkeypatch.setattr(automation, '_default_football_scan', scan)
    monkeypatch.setattr(appearances, 'refresh_football_appearances', lambda *_a, **_k: {'status': 'no_request_due'})
    document = automation.run_wettfinder(state_path=tmp_path/'wettfinder.json', now=NOW,
        config=AppConfig(api_football_key='test-key'), force_football=True,
        football_scanner=scan if explicit_scanner else None,
        tennis_loader=lambda **_: [], esports_loader=lambda **_: [], riskobet_enabled=False,
        evidence_db_path=tmp_path/'evidence.db', evidence_settlement_runner=lambda **_: {})
    assert len(seen) == 1
    if production and not explicit_scanner:
        assert seen[0] == collection.LIMITS
        assert document['football_original_admission']['status'] == 'reserved'
    else:
        assert seen == [None]
        assert 'football_original_admission' not in document
        assert not (tmp_path/'football-original-admission.json').exists()


def test_default_refresh_shares_one_permit_after_an_empty_first_batch(tmp_path, monkeypatch):
    from dataclasses import replace
    import wettfinder_automation as automation
    import context_sources.football_appearances as appearances
    from config_loader import AppConfig
    from test_wettfinder_automation import _challenge_candidate
    batches, seen = iter(([1], [2], [])), []
    monkeypatch.setattr(automation, '_same_artifact_path', lambda *_: True)
    monkeypatch.setattr(automation, 'football_context_due_fixture_ids', lambda *_a, **_k: next(batches, []))
    monkeypatch.setattr(automation, 'football_models_due', lambda *_a, **_k: True)
    monkeypatch.setattr(automation, '_discovered_candidates_for_fixtures', lambda _state, ids:
        [replace(_challenge_candidate(NOW+timedelta(minutes=80)), fixture_id=ids[0])])
    monkeypatch.setattr(automation, '_merge_context_refresh', lambda state, *_a, **_k: state)
    monkeypatch.setattr(appearances, 'refresh_football_appearances', lambda *_a, **_k: {'status':'no_request_due'})
    def refresh(*args, **kwargs):
        seen.append(kwargs)
        return {}  # First group has no calculation; the next must still get the budget.
    monkeypatch.setattr(automation, '_default_football_context_refresh', refresh)
    document = automation.run_wettfinder(state_path=tmp_path/'wettfinder.json', now=NOW,
        config=AppConfig(api_football_key='test-key'), force_football=True,
        football_scanner=lambda _: {'candidates':[], 'errors':[], 'operational_errors':[],
            'fixtures_found':0, 'fixtures_modeled':0}, tennis_loader=lambda **_: [],
        esports_loader=lambda **_: [], riskobet_enabled=False,
        evidence_db_path=tmp_path/'evidence.db', evidence_settlement_runner=lambda **_: {})
    assert len(seen) == 2
    assert all(call['original_capture_limits'] == collection.LIMITS for call in seen)
    assert seen[0]['original_capture_budget'] is seen[1]['original_capture_budget']
    assert json.loads((tmp_path/'football-original-admission.json').read_text())['total_reserved'] == collection.SESSION_BYTES
    assert document['football_original_usage'] == {'inserted_payload_bytes':0, 'source_inserted_payload_bytes':0}
