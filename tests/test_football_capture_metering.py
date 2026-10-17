"""v2 charges successful writes; abandoned permits remain fully reserved."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest
import football_context_collection as c

NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def reserve(tmp_path, now=NOW):
    return c.reserve_metered_capture(tmp_path / 'v2.json',
        model_path=tmp_path / 'models.db', legacy_path=tmp_path / 'v1.json', now=now)


def finish(tmp_path, permit, size=100, source=50, now=NOW):
    return c.finish_metered_capture(tmp_path / 'v2.json', permit['reservation_id'],
        usage={'inserted_payload_bytes': size, 'source_inserted_payload_bytes': source}, now=now)


def test_completed_small_captures_do_not_exhaust_32_attempt_lifetime(tmp_path):
    for index in range(40):
        permit = reserve(tmp_path, NOW + timedelta(days=index))
        assert permit['status'] == 'reserved'
        assert finish(tmp_path, permit, now=NOW + timedelta(days=index))['status'] == 'completed'
    state = json.loads((tmp_path / 'v2.json').read_text())
    assert state['total_committed'] == 6000
    assert state['pending'] == {}


def test_abandoned_permits_keep_full_budget_and_daily_limit(tmp_path):
    assert reserve(tmp_path)['status'] == 'reserved'
    assert reserve(tmp_path)['status'] == 'reserved'
    before = (tmp_path / 'v2.json').read_bytes()
    assert reserve(tmp_path)['status'] == 'daily_limit'
    assert (tmp_path / 'v2.json').read_bytes() == before
    assert reserve(tmp_path, NOW - timedelta(days=1))['status'] == 'clock_before_reservation'


def test_completed_usage_releases_only_known_unused_reservation(tmp_path):
    permit = reserve(tmp_path)
    first = finish(tmp_path, permit)
    assert first['charged_bytes'] == 150
    assert finish(tmp_path, permit) == first
    with pytest.raises(c.ContextIntegrityError):
        finish(tmp_path, permit, source=51)
    with pytest.raises(c.ContextIntegrityError):
        c.finish_metered_capture(tmp_path/'v2.json', 'a'*32,
            usage={'inserted_payload_bytes': 0, 'source_inserted_payload_bytes': 0}, now=NOW)
    assert reserve(tmp_path)['status'] == 'reserved'


def test_old_exhausted_ledger_is_preserved_and_linked_not_reset(tmp_path):
    old = {'schema': c.SCHEMA, 'day': NOW.date().isoformat(),
           'daily_reserved': c.DAILY_BYTES, 'total_reserved': c.TOTAL_BYTES}
    (tmp_path/'v1.json').write_bytes(c.canonical_bytes(old))
    before = (tmp_path/'v1.json').read_bytes()
    permit = reserve(tmp_path)
    assert permit['status'] == 'reserved'
    assert (tmp_path/'v1.json').read_bytes() == before
    (tmp_path/'v1.json').write_bytes(c.canonical_bytes({**old, 'day': '2030-01-02'}))
    with pytest.raises(c.ContextIntegrityError):
        reserve(tmp_path)


def test_first_v2_admission_cannot_bypass_future_legacy_reservation_day(tmp_path):
    old = {'schema': c.SCHEMA, 'day': (NOW+timedelta(days=1)).date().isoformat(),
           'daily_reserved': c.SESSION_BYTES, 'total_reserved': c.SESSION_BYTES}
    (tmp_path/'v1.json').write_bytes(c.canonical_bytes(old))
    before = (tmp_path/'v1.json').read_bytes()
    assert reserve(tmp_path)['status'] == 'clock_before_reservation'
    assert (tmp_path/'v1.json').read_bytes() == before
    assert not (tmp_path/'v2.json').exists()


def test_real_owned_payload_baseline_read_only_and_total_cap(tmp_path):
    db = tmp_path/'models.db'
    with sqlite3.connect(db) as connection:
        connection.execute('CREATE TABLE artifacts(kind TEXT, payload BLOB)')
        connection.execute('INSERT INTO artifacts VALUES (?, ?)', ('football-original-body-v1', b'a'*2000))
        connection.execute('INSERT INTO artifacts VALUES (?, ?)', ('tennis-v1', b'b'*5000))
    before = db.read_bytes()
    permit = reserve(tmp_path)
    assert json.loads((tmp_path/'v2.json').read_text())['total_committed'] == 2000
    assert db.read_bytes() == before
    finish(tmp_path, permit)
    with sqlite3.connect(db) as connection:
        connection.execute('INSERT INTO artifacts VALUES (?, zeroblob(?))',
                           ('football-original-json-chunk-v1', c.TOTAL_BYTES))
    assert reserve(tmp_path, NOW+timedelta(days=1))['status'] == 'total_limit'


def test_concurrent_admission_and_midnight_completion(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        permits = list(pool.map(lambda _: reserve(tmp_path), range(6)))
    assert sum(p['status'] == 'reserved' for p in permits) == 2
    tomorrow = NOW + timedelta(days=1)
    new = reserve(tmp_path, tomorrow)
    old = next(p for p in permits if p['status'] == 'reserved')
    finish(tmp_path, old, now=tomorrow)
    state = json.loads((tmp_path/'v2.json').read_text())
    assert state['daily_committed'] == 0  # Daily scope is admission day.
    assert new['status'] == 'reserved'


@pytest.mark.parametrize('usage', [
    {'inserted_payload_bytes': True, 'source_inserted_payload_bytes': 0},
    {'inserted_payload_bytes': -1, 'source_inserted_payload_bytes': 0},
    {'inserted_payload_bytes': c.LIMITS['max_worker_payload_bytes']+1, 'source_inserted_payload_bytes': 0},
    {'inserted_payload_bytes': 0},
])
def test_bad_completion_does_not_refund(tmp_path, usage):
    permit = reserve(tmp_path)
    before = (tmp_path/'v2.json').read_bytes()
    with pytest.raises((ValueError, c.ContextIntegrityError)):
        c.finish_metered_capture(tmp_path/'v2.json', permit['reservation_id'], usage=usage, now=NOW)
    assert (tmp_path/'v2.json').read_bytes() == before


def test_missing_store_is_not_created_and_low_disk_does_not_allocate(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(c.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1))
    assert reserve(tmp_path)['status'] == 'storage_reserve'
    assert not (tmp_path/'models.db').exists()
    assert not (tmp_path/'v2.json').exists()
