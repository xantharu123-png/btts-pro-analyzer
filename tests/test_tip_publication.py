from datetime import timedelta
import hashlib
import json
import sqlite3

import pytest

import consumer_tip_history as history
import forecast_evidence as evidence
import tip_publication as publication
from test_selection_performance import NOW, candidate, record


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, '_now', lambda: NOW)
    monkeypatch.setattr(history, '_now', lambda: NOW)
    return tmp_path / 'evidence.db', tmp_path / 'tips.db'


def signal_row(**changes):
    row = candidate()
    row.update(home_team='Home', away_team='Away', home_team_id=10, away_team_id=20)
    row.update(changes)
    return publication.compact_signal_row(row)


def test_compaction_does_not_copy_or_read_large_context():
    class Signal:
        key = 'safe'
        sport = 'Tennis'
        @property
        def context_evidence(self):
            pytest.fail('full context must never be read')
        @property
        def analysis_evidence(self):
            pytest.fail('large form lists must not be copied')
    data = publication.compact_signal_row(Signal())
    assert set(data) == {'key', 'sport', 'featured_role'}


def test_real_immutable_forecast_is_bound_without_database_changes(paths):
    forecast, _ = paths
    raw = candidate()
    record(forecast, [raw])
    before = hashlib.sha256(forecast.read_bytes()).hexdigest()
    row = publication.compact_signal_row(raw)
    result = publication.bind_forecast_ids([row], as_of=NOW, db_path=forecast)
    with sqlite3.connect(forecast) as conn:
        expected = conn.execute('SELECT forecast_id FROM forecast_rows').fetchone()[0]
    assert result[0]['forecast_id'] == expected
    assert hashlib.sha256(forecast.read_bytes()).hexdigest() == before
    assert 'forecast_id' not in row


@pytest.mark.parametrize('field,value', [
    ('probability', .61), ('candidate_id', 'other'), ('market_key', 'RESULT_AWAY'),
    ('selection', 'Nein'), ('event_key', 'football:999'),
    ('home_team', 'New Home'), ('away_team', 'New Away'),
    ('home_team_id', 999), ('away_team_id', 998),
    ('modeled_at', (NOW-timedelta(minutes=4)).isoformat()),
    ('input_cutoff_at', (NOW-timedelta(minutes=9)).isoformat()),
    ('model_version', 'foreign-model'), ('policy_version', 'foreign-policy'),
])
def test_foreign_revision_or_participants_never_bind(paths, field, value):
    forecast, _ = paths
    raw = candidate()
    raw.update(home_team='Home', away_team='Away', home_id=10, away_id=20)
    record(forecast, [raw])
    row = publication.compact_signal_row(raw)
    row.update(home_team_id=10, away_team_id=20)
    row[field] = value
    assert 'forecast_id' not in publication.bind_forecast_ids([row], as_of=NOW, db_path=forecast)[0]


def test_missing_forecast_store_does_not_accept_supplied_hint(paths):
    forecast, _ = paths
    row = signal_row(forecast_id='a'*64)
    row['forecast_id'] = 'a'*64
    assert 'forecast_id' not in publication.bind_forecast_ids([row], as_of=NOW, db_path=forecast)[0]
    assert not forecast.exists()


def test_orphan_forecast_cannot_be_bound_even_with_valid_row_hash(paths):
    forecast, _ = paths
    raw = candidate()
    record(forecast, [raw])
    with sqlite3.connect(forecast) as conn:
        triggers = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='forecast_runs'")]
        for trigger in triggers:
            conn.execute(f'DROP TRIGGER "{trigger}"')
        conn.execute('DELETE FROM forecast_runs')
    assert 'forecast_id' not in publication.bind_forecast_ids(
        [publication.compact_signal_row(raw)], as_of=NOW, db_path=forecast)[0]


def test_only_selected_order_and_roles_are_archived(paths):
    forecast, receipts = paths
    rows = [candidate(fixture=i) for i in (2, 1)]
    record(forecast, rows + [candidate(fixture=3)])
    for row in rows:
        row['key'] = row['candidate_id']
    result = publication.record_signal_catalog('automatic', rows, as_of=NOW,
        featured_keys=[rows[0]['key']], source_run_id='version-1',
        db_path=receipts, forecast_db_path=forecast)
    assert result['status'] == 'recorded'
    saved = history.read_tip_publications(receipts)[0]['tips']
    assert [tip['fixture_id'] for tip in saved] == [2, 1]
    assert [tip['featured_role'] for tip in saved] == ['featured', 'catalogue']
    assert all(tip.get('forecast_id') for tip in saved)


def test_optional_receipt_failure_never_interrupts_ui(paths, monkeypatch):
    forecast, receipts = paths
    def fail(*args, **kwargs):
        raise OSError('database unavailable')
    monkeypatch.setattr(history, 'record_tip_publication', fail)
    result = publication.record_selected_tips('automatic', [], as_of=NOW,
        db_path=receipts, forecast_db_path=forecast)
    assert result['status'] == 'unavailable'


def test_empty_selected_inventory_is_not_full_candidate_pool(paths):
    forecast, receipts = paths
    record(forecast, [candidate()])
    publication.record_signal_catalog('automatic', [], as_of=NOW,
        db_path=receipts, forecast_db_path=forecast)
    assert history.read_tip_publications(receipts)[0]['tips'] == []


def test_worker_archives_shared_selected_catalogue_without_provider_calls(paths, monkeypatch):
    from types import SimpleNamespace
    import ev_signal_sources
    from test_daily3_selection import football
    forecast, receipts = paths
    status = SimpleNamespace(generated_at=NOW)
    snapshot = SimpleNamespace(status=status, forecasts=(football(start_hours=6),))
    monkeypatch.setattr(ev_signal_sources, 'automated_wettfinder_snapshot', lambda *a, **k: snapshot)
    result = publication.record_automatic_publication('existing-model.json', as_of=NOW,
        db_path=receipts, forecast_db_path=forecast)
    assert result['status'] == 'completed'
    saved = history.read_tip_publications(receipts)
    assert {entry['surface'] for entry in saved} == {'wettfinder_default_inventory', 'daily3_default_plan'}
    assert len(saved[0]['tips']) <= 1


def test_worker_does_not_record_unknown_source_as_empty_publication(paths, monkeypatch):
    from types import SimpleNamespace
    import ev_signal_sources
    forecast, receipts = paths
    monkeypatch.setattr(ev_signal_sources, 'automated_wettfinder_snapshot',
        lambda *a, **k: SimpleNamespace(status=None, forecasts=()))
    assert publication.record_automatic_publication('unknown', as_of=NOW,
        db_path=receipts, forecast_db_path=forecast)['status'] == 'source_unavailable'
    assert not receipts.exists()


def test_cli_missing_publication_history_never_falls_back_to_candidate_pool(paths, capsys):
    from scripts.selection_performance_report import main
    from test_selection_performance import AS_OF
    forecast, receipts = paths
    record(forecast, [candidate()])
    assert main(['--db', str(forecast), '--history-db', str(receipts),
        '--from-day', '2030-01-01', '--through-day', '2030-01-01',
        '--as-of', AS_OF.isoformat()]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['cohort'] == 'archived_publications'
    assert report['summary']['selections'] == 0
    assert report['unique_archived_selections'] == 0
    assert not receipts.exists()


def test_cli_surface_filter_requires_publication_history(paths, capsys):
    from scripts.selection_performance_report import main
    forecast, _ = paths
    with pytest.raises(SystemExit) as error:
        main(['--db', str(forecast), '--surface', 'daily3_plan',
              '--from-day', '2030-01-01', '--through-day', '2030-01-01'])
    assert error.value.code == 2
    assert '--surface requires --history-db' in capsys.readouterr().err


@pytest.fixture(scope='module', params=[
    ('ice_hockey', 'NHL', 'NHL'),
    ('basketball', 'ESPN', 'NBA'),
    ('basketball', 'EuroLeague', 'EuroLeague'),
])
def research_snapshot(request):
    """Actual closed same-call models, using existing synthetic result fixtures."""
    from riskobet_candidates import adapt_research_matchwinner
    from test_sports_prematch import NOW as team_now, event, history as result_history
    sport, provider, competition = request.param
    target = event(sport, provider=provider, competition=competition,
                   source_observed_at=team_now.isoformat())
    rows = [dict(row, provider=provider, competition=competition)
            for row in result_history(sport)]
    return adapt_research_matchwinner(sport, target, rows, modeled_at=team_now).snapshot


def research_row_and_signal(snapshot):
    from types import SimpleNamespace
    from ev_signal_sources import ModelSignal
    from team_sport_forecasts import team_sport_forecast_rows
    row = team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)),
        now=snapshot.modeled_at, target_date=snapshot.starts_at.date())[0]
    args = {key: value for key, value in row.items() if key in ModelSignal.__dataclass_fields__}
    return row, ModelSignal(**args, event_label=row['event'])


@pytest.mark.parametrize('as_mapping', [False, True])
def test_research_compaction_reuses_exact_frozen_event_and_snapshot(research_snapshot, as_mapping):
    row, signal = research_row_and_signal(research_snapshot)
    compact = publication.compact_signal_row(row if as_mapping else signal)
    assert compact['event_key'] == row['event_identity'] == research_snapshot.event_key
    assert compact['snapshot_id'] == research_snapshot.snapshot_id
    assert compact['candidate_id'] == row['candidate_id']
    assert compact['probability'] == row['probability']
    assert 'team_sport_snapshot' not in compact
    assert 'team_sport_forecast' not in compact
    assert len(json.dumps(compact)) < 3000


def test_research_publication_binds_real_forecast_without_rewriting_it(
        paths, monkeypatch, research_snapshot):
    from team_sport_forecasts import POLICY
    forecast, receipts = paths
    decision = research_snapshot.modeled_at
    observed = decision+timedelta(minutes=1)
    monkeypatch.setattr(evidence, '_now', lambda: decision)
    monkeypatch.setattr(history, '_now', lambda: observed)
    row, signal = research_row_and_signal(research_snapshot)
    result = evidence.record_forecast_run(
        dict(generated_at=decision.isoformat(), selection_policy_version=POLICY,
             model_candidates=[row]), forecast, research_snapshot.model_version)
    assert result['recorded'] == 1 and result['rejected'] == []
    before = hashlib.sha256(forecast.read_bytes()).hexdigest()
    saved = publication.record_signal_catalog('automatic', [signal], as_of=observed,
        db_path=receipts, forecast_db_path=forecast)
    assert saved['status'] == 'recorded'
    tip = history.read_tip_publications(receipts)[0]['tips'][0]
    assert tip['event_key'] == research_snapshot.event_key
    assert tip['snapshot_id'] == research_snapshot.snapshot_id
    assert tip['forecast_id'] == result['forecast_ids'][0]
    assert tip['probability'] == row['probability']
    assert hashlib.sha256(forecast.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('field,value', [
    ('provider_event_id', 'different-native-event'),
    ('fixture_source', 'foreign-provider'),
    ('sport', 'Cricket'),
    ('event_key', 'event_'+'b'*64),
    ('event_identity', 'event_'+'b'*64),
    ('snapshot_id', 'snapshot_'+'b'*64),
    ('scheduled_start', '2050-01-01T00:00:00+00:00'),
    ('modeled_at', '2050-01-01T00:00:00+00:00'),
    ('input_cutoff_at', '2050-01-01T00:00:00+00:00'),
    ('market_key', 'RESULT_HOME'),
    ('selection', 'unrelated-side'),
    ('selected_competitor', 'unrelated-side'),
    ('competitor_a_id', 'other-team'),
    ('probability', .001),
])
@pytest.mark.parametrize('as_mapping', [False, True])
def test_research_publication_rejects_changed_native_scope_clocks_and_side(
        research_snapshot, field, value, as_mapping):
    from types import SimpleNamespace
    row, signal = research_row_and_signal(research_snapshot)
    changed = dict(row) if as_mapping else dict(vars(signal))
    changed[field] = value
    with pytest.raises(ValueError, match='publication research'):
        publication.compact_signal_row(changed if as_mapping else SimpleNamespace(**changed))


@pytest.mark.parametrize('alias', ['event_key', 'event_identity'])
def test_research_publication_does_not_overrule_conflicting_event_alias(research_snapshot, alias):
    row, _ = research_row_and_signal(research_snapshot)
    row.update(event_key=research_snapshot.event_key, event_identity=research_snapshot.event_key)
    row[alias] = 'event_'+'f'*64
    with pytest.raises(ValueError, match='publication research'):
        publication.compact_signal_row(row)


@pytest.mark.parametrize('provider,competition', [
    ('foreign-provider', 'NHL'), ('ESPN', 'NHL'), ('NHL', 'NBA'),
])
def test_research_publication_requires_supported_provider_competition_scope(
        research_snapshot, provider, competition):
    from dataclasses import replace
    from riskobet_domain import stable_event_key
    from team_sport_forecasts import valid_research_row
    payload = replace(research_snapshot.team_sport_forecast, provider=provider)
    changed = replace(research_snapshot, competition=competition,
        event_key=stable_event_key(payload.sport, provider, payload.provider_event_id),
        team_sport_forecast=payload)
    row, _ = research_row_and_signal(changed)
    assert valid_research_row(row)  # Self-consistent, but wrong native source scope.
    with pytest.raises(ValueError, match='publication research provider'):
        publication.compact_signal_row(row)
