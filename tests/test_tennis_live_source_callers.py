"""Canonical callers use the explicit source contract and real publication owners."""
from datetime import timedelta

import pytest


def test_canonical_daily_opts_into_explicit_indexed_live_contract(monkeypatch, tmp_path):
    from contextlib import closing
    from context_observations import _connect as source_connection
    import sys
    from context_tennis_index_build import initialize_index, build_index
    from scripts import tennis_daily as daily
    from tennis import live_context, shadow
    from test_tennis_live_worker import configure, NOW
    db, predictions, _, calls = configure(monkeypatch, tmp_path)
    with closing(source_connection(db)):
        pass
    initialize_index(db)
    assert build_index(db).status == 'ready'
    actual_worker, transports = live_context.live_worker, []
    def observed_worker(**kwargs):
        transports.append(kwargs.get('source_transport'))
        return actual_worker(**kwargs)
    monkeypatch.setattr(live_context, 'live_worker', observed_worker)
    monkeypatch.setattr(sys, 'argv', ['tennis_daily.py', '2026-09-09'])
    def existing_scan(args):
        fixtures = daily.fetch_fixtures_espn(args.date)
        daily.scan_fixtures(args.date, fixtures, decision_at=NOW,
            db_path=predictions, surfaces={}, workload_history=(),
            append_observed_at=NOW+timedelta(seconds=2))
        return 0
    monkeypatch.setattr(daily, '_run_daily', existing_scan)
    assert daily.main() == 0
    assert transports == ['tennis-live-indexed-source-v1']
    assert len(shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))) == 1
    assert len(calls) == 2  # Existing synthetic fixture receptions only.


def test_canonical_pending_refresh_opts_in_without_network(monkeypatch, tmp_path):
    from context_tennis_index_build import initialize_index, build_index
    from scripts import tennis_daily as daily
    from tennis import live_context
    from test_tennis_live_worker import configure, run_batch, NOW
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)  # Existing default legacy API remains valid.
    initialize_index(db)
    assert build_index(db).status == 'ready'
    later = NOW+timedelta(hours=2, minutes=30)
    monkeypatch.setattr(live_context, '_now', lambda: later+timedelta(seconds=1))
    monkeypatch.setattr(daily.requests, 'get', lambda *a, **k: pytest.fail('network during existing-state refresh'))
    actual_worker, transports = live_context.LiveWorker, []
    def observed_worker(*args, **kwargs):
        transports.append(kwargs.get('source_transport'))
        return actual_worker(*args, **kwargs)
    monkeypatch.setattr(live_context, 'LiveWorker', observed_worker)
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=later,
        append_observed_at=later+timedelta(seconds=2))
    assert result['refreshed'] == 1 and not result['errors']
    assert transports == ['tennis-live-indexed-source-v1']
