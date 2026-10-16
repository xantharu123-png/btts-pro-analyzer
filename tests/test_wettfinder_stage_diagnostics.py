"""Worker diagnostics must not change decisions, callbacks or output contracts."""
import json

import pytest

import wettfinder_automation as worker


def test_stage_preserves_exact_result_and_callback_arguments(monkeypatch, capsys):
    clocks = iter((20.0, 23.25))
    monkeypatch.setattr(worker, 'perf_counter', lambda: next(clocks))
    result = object()
    calls = []

    def callback(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    assert worker._logged_stage('forecast_results', callback, 7, db_path='private') is result
    assert calls == [((7,), {'db_path': 'private'})]
    captured = capsys.readouterr()
    assert captured.out == ''
    records = [json.loads(line) for line in captured.err.splitlines()]
    assert records == [
        {'diagnostic': 'wettfinder_stage', 'stage': 'forecast_results', 'phase': 'started'},
        {'diagnostic': 'wettfinder_stage', 'stage': 'forecast_results', 'phase': 'completed',
         'elapsed_seconds': 3.25},
    ]
    assert 'private' not in captured.err


@pytest.mark.parametrize('failure', [RuntimeError('private-provider-token'),
                                   KeyboardInterrupt('private-provider-token')])
def test_failed_stage_logs_no_exception_text_and_preserves_exception(failure, capsys):
    def callback():
        raise failure

    with pytest.raises(type(failure)) as caught:
        worker._logged_stage('forecast_results', callback)
    assert caught.value is failure
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'private-provider-token' not in captured.err
    records = [json.loads(line) for line in captured.err.splitlines()]
    assert [row['phase'] for row in records] == ['started', 'failed']
    assert records[-1]['elapsed_seconds'] >= 0


@pytest.mark.parametrize('failure', [BrokenPipeError(), ValueError('closed stream'),
                                   RuntimeError('custom writer'), TypeError('custom writer')])
def test_unavailable_diagnostic_stream_does_not_change_result(monkeypatch, failure):
    def broken_print(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(worker, 'print', broken_print, raising=False)
    result = object()
    assert worker._logged_stage('forecast_results', lambda: result) is result


def test_unavailable_diagnostic_stream_does_not_mask_work_exception(monkeypatch):
    def broken_print(*_args, **_kwargs):
        raise OSError('diagnostics unavailable')

    monkeypatch.setattr(worker, 'print', broken_print, raising=False)
    failure = RuntimeError('callback failure')

    def callback():
        raise failure

    with pytest.raises(RuntimeError) as caught:
        worker._logged_stage('forecast_results', callback)
    assert caught.value is failure


def test_production_stages_preserve_document_order_and_private_callbacks(tmp_path, monkeypatch, capsys):
    """Exercise the real production-path gate without shared data or providers."""
    from contextlib import nullcontext
    from copy import deepcopy
    from datetime import datetime, timezone

    from config_loader import AppConfig
    from test_wettfinder_automation import _football_snapshot
    import context_sources.football_appearances as appearances
    import forecast_evidence
    import tip_publication

    now = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
    config = AppConfig(api_football_key='private-test-key')
    private_tennis = tmp_path / 'tennis.db'
    private_esports = tmp_path / 'esports.db'
    private_evidence = tmp_path / 'forecast.db'
    private_risk = tmp_path / 'riskobet.db'
    private_risk_latest = tmp_path / 'riskobet_latest.json'
    monkeypatch.setattr(worker, 'TENNIS_DB', private_tennis)
    monkeypatch.setattr(worker, 'ESPORTS_DB', private_esports)
    monkeypatch.setattr(worker, 'load_app_config', lambda: config)
    monkeypatch.setattr(worker, 'capture_football_worker', lambda *_args, **_kwargs: nullcontext())
    real_write_state = worker.write_state
    real_logged_stage = worker._logged_stage
    calls = []
    provider = object()
    context_done = False

    def scanner(day):
        calls.append('football_discovery')
        assert day == now.date()
        snapshot = _football_snapshot(now)
        snapshot['discovery_candidates'] = list(snapshot['shortlist'])
        return snapshot

    def context_due(_state, *, now):
        return [] if context_done else [1]

    def context_refresh(pool, day, checked_at):
        nonlocal context_done
        calls.append('football_context')
        assert day == now.date() and checked_at == now and pool
        context_done = True
        candidates = _football_snapshot(now)['shortlist']
        return {'candidates': candidates, 'wettfinder_candidates': candidates,
                'context_fixture_statuses': {'1': 'verified'},
                'operational_errors': [], 'errors': []}

    def tennis_refresh(*, db_path, as_of):
        calls.append('tennis_refresh')
        assert db_path == private_tennis and as_of == now
        return {'status': 'completed', 'errors': []}

    def sources(_football_state, *, now, target_date, research_due,
                nhl_capture_path=None, nhl_capture_report=None):
        calls.append('riskobet_sources')
        assert target_date == now.date() and research_due is True
        data = {sport: () for sport in ('football', 'tennis', 'basketball', 'ice_hockey', 'esports')}
        return data, {sport: True for sport in data}

    def risk_results(**kwargs):
        calls.append('riskobet_results')
        assert kwargs['db_path'] == private_risk and kwargs['latest_path'] == private_risk_latest
        return {'run_id': None, 'due_candidates': 0, 'due_events': 0, 'checked_sports': [],
                'terminal_settlements': 0, 'unresolved_candidates': 0, 'published': False,
                'error_count': 0, 'operational_error_count': 0, 'errors': []}

    def risk_models(**kwargs):
        calls.append('riskobet_models')
        assert kwargs['db_path'] == private_risk and kwargs['latest_path'] == private_risk_latest
        return {'status': 'COMPLETE', 'run_id': 'private-run', 'snapshots': [],
                'candidates': [], 'errors': []}

    def esports_results(db_path, *, now):
        calls.append('esports_results')
        assert db_path == private_esports
        return {'status': 'completed', 'checked': 0, 'settled': 0}

    def record(document, db_path, *, model_version):
        calls.append('forecast_recording')
        assert db_path == private_evidence and document['model_candidates']
        assert model_version == worker.CHALLENGE_PREDICTION_VERSION
        return {'run_id': 'private-evidence-run', 'recorded': len(document['model_candidates']),
                'rejected': [], 'quotes_rejected': []}

    def provider_factory(key, weather_key):
        assert key == config.api_football_key and weather_key == config.weather_key
        return provider

    def forecast_results(**kwargs):
        calls.append('forecast_results')
        assert kwargs['db_path'] == private_evidence and kwargs['football_provider'] is provider
        assert kwargs['tennis_db_path'] == private_tennis and kwargs['esports_db_path'] == private_esports
        return {'status': 'completed', 'operational_error_count': 0}

    def football_appearances(actual_provider, *, now):
        calls.append('football_appearances')
        assert actual_provider is provider
        return {'status': 'completed', 'requested_count': 0}

    def publish(document, path):
        calls.append('forecast_publication')
        assert path.parent == tmp_path
        return real_write_state(document, path)

    def receipt(path):
        calls.append('tip_receipts')
        assert path.parent == tmp_path
        return {'status': 'completed'}

    monkeypatch.setattr(worker, 'football_context_due_fixture_ids', context_due)
    monkeypatch.setattr(worker, '_riskobet_default_sources', sources)
    monkeypatch.setattr(worker, 'ChallengeDataProvider', provider_factory)
    monkeypatch.setattr(forecast_evidence, 'record_forecast_run', record)
    monkeypatch.setattr(appearances, 'refresh_football_appearances', football_appearances)
    monkeypatch.setattr(worker, 'write_state', publish)
    monkeypatch.setattr(tip_publication, 'record_automatic_publication', receipt)

    documents, callbacks = [], []
    captures = []
    for enabled in (True, False):
        path = tmp_path / ('timed.json' if enabled else 'untimed.json')
        # Keep the real same-path comparison, but its canonical path is private.
        monkeypatch.setattr(worker, 'STATE_PATH', path)
        assert worker._same_artifact_path(path, worker.STATE_PATH)
        monkeypatch.setattr(worker, '_logged_stage', real_logged_stage if enabled
                            else lambda _name, callback, *args, **kwargs: callback(*args, **kwargs))
        calls.clear()
        context_done = False
        document = worker.run_wettfinder(
            now=now, state_path=path, config=config, force_football=True,
            football_scanner=scanner, football_context_refresher=context_refresh,
            football_quote_loader=lambda _rows: ({}, []), tennis_quote_loader=lambda _rows: ({}, []),
            tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
            tennis_model_refresher=tennis_refresh, riskobet_enabled=True,
            riskobet_runner=risk_models, riskobet_settlement_runner=risk_results,
            riskobet_db_path=private_risk, riskobet_latest_path=private_risk_latest,
            evidence_db_path=private_evidence, evidence_settlement_runner=forecast_results,
            esports_settlement_runner=esports_results,
        )
        assert json.loads(path.read_text(encoding='utf-8')) == json.loads(json.dumps(document))
        assert document['operational_error_count'] == 0
        assert 'wettfinder_stage' not in json.dumps(document)
        documents.append(deepcopy(document))
        callbacks.append(tuple(calls))
        captures.append(capsys.readouterr())

    assert documents[0] == documents[1]
    expected = ('football_discovery', 'football_context', 'tennis_refresh', 'riskobet_sources',
                'riskobet_results', 'riskobet_models', 'esports_results', 'forecast_recording',
                'forecast_results', 'football_appearances', 'forecast_publication', 'tip_receipts')
    assert callbacks == [expected, expected]
    assert captures[0].out == captures[1].out == captures[1].err == ''
    records = [json.loads(line) for line in captures[0].err.splitlines()]
    assert [(row['stage'], row['phase']) for row in records] == [
        (stage, phase) for stage in expected for phase in ('started', 'completed')]
    assert all(row['elapsed_seconds'] >= 0 for row in records if row['phase'] == 'completed')
    assert config.api_football_key not in captures[0].err
    assert not any(path.exists() for path in (
        private_tennis, private_esports, private_evidence, private_risk, private_risk_latest))
