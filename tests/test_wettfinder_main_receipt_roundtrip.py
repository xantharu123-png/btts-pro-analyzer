"""Prospective worker -> immutable source -> settlement -> Zurich matchday, offline."""
from datetime import timedelta
from types import SimpleNamespace

import consumer_tip_history
import ev_signal_sources
import forecast_evidence
from consumer_tip_performance import build_consumer_tip_performance_report
from tip_publication import compact_signal_row, record_automatic_publication
from test_consumer_tip_performance import AS_OF, NOW
from test_daily3_selection import football
from test_publication_odds_floor import priced


def test_real_worker_matches_losing_main_tip_and_does_not_promote_hidden_winner(tmp_path, monkeypatch):
    forecasts, tips = tmp_path / 'forecasts.db', tmp_path / 'tips.db'
    monkeypatch.setattr(forecast_evidence, '_now', lambda: NOW)
    monkeypatch.setattr(consumer_tip_history, '_now', lambda: NOW)
    signals = [priced(football(i, probability=p, now=NOW), (1.8,)*3, now=NOW)
               for i, p in ((177, .79), (178, .62))]
    rows = [dict(compact_signal_row(s), source='football_challenge',
                 home_id=s.home_team_id, away_id=s.away_team_id) for s in signals]
    frozen = forecast_evidence.record_forecast_run(
        dict(generated_at=NOW.isoformat(), selection_policy_version='test-v1', model_candidates=rows),
        forecasts, 'test-model-v1')
    assert len(frozen['forecast_ids']) == 2
    snapshot = SimpleNamespace(status=SimpleNamespace(generated_at=NOW), forecasts=signals)
    monkeypatch.setattr(ev_signal_sources, 'automated_wettfinder_snapshot', lambda *args, **kw: snapshot)
    for _ in range(2):  # identical publication, not a second selection
        receipt = record_automatic_publication('offline', as_of=NOW, db_path=tips, forecast_db_path=forecasts)
        assert receipt['status'] == 'completed'

    monkeypatch.setattr(forecast_evidence, '_now', lambda: AS_OF)
    for signal, outcome in zip(signals, ('LOSS', 'WIN')):
        fixture = signal.fixture_id
        forecast_evidence.append_result(f'football:{fixture}', 'RESULT_HOME', signal.selection, outcome,
            observed_at=AS_OF, provenance=dict(provider='api-football', provider_event_id=str(fixture),
                source_record_id=f'terminal:{fixture}', payload_sha256='a'*64, settlement_rule='football-fulltime-v1'),
            db_path=forecasts)
    def view(cutoff):
        return build_consumer_tip_performance_report(tips, forecasts, from_day='2030-01-01',
            through_day='2030-01-01', surface='wettfinder_default_inventory', as_of=cutoff)['matchday']
    early, final = view(AS_OF - timedelta(hours=2)), view(AS_OF)
    assert early['first_main_card']['summary']['open'] == 1
    assert final['all_distinct_markets']['summary']['decided'] == 2
    assert final['first_main_card']['summary']['losses'] == 1
    assert final['first_main_card']['summary']['wins'] == 0
    assert [(r['event_key'], r['probability']) for r in final['first_main_card']['rows']
            if r['status'] == 'LOSS'] == [('football:177', .79)]
