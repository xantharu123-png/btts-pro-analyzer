"""Native sport changes are partial data, never a new forecast or hidden damage."""
from datetime import timedelta
import json
import sqlite3

import pytest

from context_observations import append_observation
from context_sources.tennis_status import normalize_tennis_status
from scripts import tennis_daily as daily
from tennis import live_context, shadow
from test_tennis_fixture_availability import correction
from test_tennis_live_worker import NOW, competition, configure, run_batch


@pytest.mark.parametrize('kind,reason', [
    ('missing_player', 'participants_unconfirmed'),
    ('replacement', 'participants_changed'),
    ('started', 'fixture_no_longer_prematch'),
    ('cancelled', 'fixture_no_longer_prematch'),
])
def test_native_change_is_reported_without_a_new_prediction(monkeypatch, tmp_path, kind, reason):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    received = NOW+timedelta(minutes=10)
    correction(db, kind, clock=received)
    frozen = (db.read_bytes(), predictions.read_bytes())
    monkeypatch.setattr(daily.requests, 'get', lambda *a, **k: pytest.fail('network'))
    monkeypatch.setattr(daily, 'predict_match', lambda *a, **k: pytest.fail('invalid pairing modeled'))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=NOW+timedelta(hours=2))
    assert result['status'] == 'partial' and result['errors'] == []
    assert result['refreshed'] == 0 and result['skipped'] == 1
    assert result['provider_checked'] is False
    assert result['native_unavailable'][0]['prediction_id'] == rows[0]['id']
    assert result['native_unavailable'][0]['reason'] == reason
    assert result['native_unavailable'][0]['observed_at'] == received.isoformat(timespec='microseconds').replace('+00:00', 'Z')
    assert len(result['native_unavailable'][0]['receipt']) == 64
    assert frozen == (db.read_bytes(), predictions.read_bytes())


@pytest.mark.parametrize('damage', ['original_receipt_missing', 'source_bytes', 'original_artifact'])
def test_retraction_does_not_hide_broken_original_evidence(monkeypatch, tmp_path, damage):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    correction(db, 'missing_player', clock=NOW+timedelta(minutes=10))
    link = json.loads(rows[0]['context_json'])['context_model']
    with sqlite3.connect(db) as connection:
        if damage == 'original_receipt_missing':
            connection.execute('DELETE FROM context_observations WHERE observed_at < ?', (NOW.isoformat(),))
        elif damage == 'source_bytes':
            connection.execute("UPDATE context_observations SET subject_id='corrupt'")
        else:
            connection.execute('UPDATE artifacts SET payload=? WHERE digest=?', (b'{}', link['original_artifact_hash']))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=NOW+timedelta(hours=2))
    assert result['errors'] and result['native_unavailable'] == []
    assert result['refreshed'] == 0


def test_confirmed_restoration_can_refresh_again(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    correction(db, 'missing_player', clock=NOW+timedelta(minutes=10))
    first = daily.refresh_pending_predictions(db_path=predictions, as_of=NOW+timedelta(hours=2))
    assert first['native_unavailable']
    received = NOW+timedelta(hours=2, minutes=1)
    for row in normalize_tennis_status('ATP', '189-2026', competition(), grouping_slug='mens-singles', observed_at=received):
        append_observation(db, row, observed_at=received)
    later = NOW+timedelta(hours=2, minutes=2)
    monkeypatch.setattr(live_context, '_now', lambda: later+timedelta(seconds=1))
    second = daily.refresh_pending_predictions(db_path=predictions, as_of=later,
        append_observed_at=later+timedelta(seconds=2))
    assert second['status'] == 'complete' and second['refreshed'] == 1
    assert second['native_unavailable'] == [] and second['errors'] == []
    assert len(shadow.latest_predictions(predictions, as_of=later+timedelta(seconds=3))) == 1


@pytest.mark.parametrize('change', ['conflicting', 'different_competition'])
def test_conflicting_or_foreign_source_is_still_an_error(monkeypatch, tmp_path, change):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    received = NOW+timedelta(minutes=10)
    correction(db, 'missing_player', clock=received)
    tournament = '999-2026' if change == 'different_competition' else '189-2026'
    raw = competition()
    if change == 'different_competition':
        raw['competitors'][0]['id'] = None
        received += timedelta(seconds=1)
    for row in normalize_tennis_status('ATP', tournament, raw, grouping_slug='mens-singles', observed_at=received):
        append_observation(db, row, observed_at=received)
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=NOW+timedelta(hours=2))
    assert result['errors'] and result['native_unavailable'] == []
    assert result['refreshed'] == 0


def test_automation_preserves_partial_data_without_false_technical_failure(tmp_path):
    from config_loader import AppConfig
    from test_wettfinder_automation import _football_snapshot
    from wettfinder_automation import run_wettfinder
    unavailable = [{'prediction_id': 1, 'reason': 'participants_unconfirmed'}]
    document = run_wettfinder(now=NOW, state_path=tmp_path/'wettfinder.json',
        config=AppConfig(api_football_key='test'),
        football_scanner=lambda _day: _football_snapshot(NOW),
        football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
        tennis_model_refresher=lambda **_kwargs: {'status': 'partial', 'refreshed': 0,
            'errors': [], 'native_unavailable': unavailable})
    assert document['run_status'] == 'completed'
    assert document['operational_error_count'] == 0
    refresh = document['sources']['tennis']['model_refresh']
    assert refresh['status'] == 'partial' and refresh['native_unavailable'] == unavailable
