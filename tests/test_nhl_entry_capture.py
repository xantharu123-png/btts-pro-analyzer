"""Nightly evidence consumes already-retrieved NHL prices without changing tips."""
from copy import deepcopy
from datetime import timedelta
import json
import sqlite3

import pytest

import forecast_evidence
import team_sport_prices as prices
from config_loader import AppConfig
from riskobet_domain import RiskRunSnapshot, RunStatus
from selection_performance import build_selection_performance_report
from test_team_sport_forecasts import _snapshot
from test_team_sport_prices import NOW, game, odds
from wettfinder_automation import run_wettfinder


ENTRY_AT = NOW + timedelta(seconds=3)
START = NOW + timedelta(hours=6)


def _cache(tmp_path, snapshots, fetched_at, *, damage=None):
    rows = prices.snapshot_price_rows(snapshots)
    rows = [row for row in rows if row['fixture_source'] == 'NHL']
    native = game('ice_hockey')
    books = odds(native)
    entries = {}
    for row in rows:
        key = prices._key(row)
        bound = {**row, 'candidate_id': key, 'key': key}
        trade_time = (fetched_at-timedelta(seconds=1)
                      if damage == 'different_counter_clock' and row['selection'] == row['competitor_a'] else fetched_at)
        quote = prices.parse_game_quotes(books, [bound], native, fetched_at=trade_time)[key].to_dict()
        if damage == 'missing_counter_partition' and row['selection'] == row['competitor_a']:
            quote.pop('native_market_partitions')
        entries[key] = {'binding': list(prices._binding(row)), 'quote': quote}
    (tmp_path / 'team_sport_quotes.json').write_text(json.dumps({
        'schema': 1, 'attempts': {}, 'quotes': entries}), encoding='utf-8')


def _run(monkeypatch, tmp_path, *, fetched_at, damage=None, expected_count=4, evidence_settlement_runner=None):
    from requests.sessions import Session
    monkeypatch.setattr(Session, 'request', lambda *_args, **_kwargs: pytest.fail('unexpected API request'))
    snapshots = (_snapshot('ice_hockey'), _snapshot('basketball'))
    risk = RiskRunSnapshot(started_at=NOW, completed_at=NOW, status=RunStatus.COMPLETE, snapshots=snapshots)
    if fetched_at is not None:
        _cache(tmp_path, snapshots, fetched_at, damage=damage)
    wall = [NOW]

    def after_cache(*_args, **_kwargs):
        wall[0] = ENTRY_AT
        return {'status': 'completed'}

    database = tmp_path / 'evidence.db'
    monkeypatch.setattr(forecast_evidence, '_now', lambda: ENTRY_AT + timedelta(seconds=1))
    artifact = run_wettfinder(clock=lambda: wall[0], state_path=tmp_path/'wettfinder.json',
        config=AppConfig(), tennis_loader=lambda **_kw: [], esports_loader=lambda **_kw: [],
        riskobet_runner=lambda **_kw: risk, esports_settlement_runner=after_cache, evidence_db_path=database,
        evidence_settlement_runner=evidence_settlement_runner)
    assert artifact['generated_at'] == NOW.isoformat()
    assert artifact['forecast_evidence'].get('recorded') == expected_count
    assert artifact['forecast_evidence']['rejected_count'] == 0
    assert artifact['forecast_evidence']['quote_rejected_count'] == 0
    assert all(row.get('reference_quote') is None for row in artifact['model_candidates'])
    return artifact, database, snapshots


def _read(database, query):
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        return db.execute(query).fetchall()


@pytest.mark.price_policy('floor')
def test_daily_nhl_entry_freezes_both_sides_using_the_actual_cache_clock_without_roi(monkeypatch, tmp_path):
    fetched_at = NOW + timedelta(seconds=2)
    artifact, database, _ = _run(monkeypatch, tmp_path, fetched_at=fetched_at)
    rows = _read(database, 'SELECT sport,decision_at,payload_json FROM forecast_rows ORDER BY sport,selection')
    assert [(sport, decision) for sport, decision, _ in rows] == [
        ('basketball', NOW.isoformat()), ('basketball', NOW.isoformat()),
        ('ice_hockey', ENTRY_AT.isoformat()), ('ice_hockey', ENTRY_AT.isoformat())]
    metadata = artifact['forecast_evidence']
    assert metadata['nhl_entry']['status'] == 'recorded' and metadata['nhl_entry']['recorded'] == 2
    assert metadata['run_id'] != metadata['nhl_entry']['run_id']
    assert set(_read(database, 'SELECT DISTINCT run_id FROM forecast_rows')) == {
        (metadata['run_id'],), (metadata['nhl_entry']['run_id'],)}
    source = {r['key']: r for r in artifact['model_candidates']}
    for sport, _, raw in rows:
        p = json.loads(raw)
        assert p['modeled_at'] == NOW.isoformat()
        assert p['probability'] == source[p['candidate_id']]['probability']
        assert p['input_cutoff_at'] == source[p['candidate_id']]['input_cutoff_at']
        assert p['quote_identity']['fixture_source'] == ('NHL' if sport == 'ice_hockey' else 'ESPN')

    quoted = _read(database, 'SELECT kind,observed_at,fetched_at,executable,payload_json FROM forecast_quotes')
    assert len(quoted) == 6
    for kind, observed, fetched, executable, raw in quoted:
        assert (kind, observed, fetched, executable) == ('entry', fetched_at.isoformat(), fetched_at.isoformat(), 0)
        market = json.loads(raw)['native_market_partition']
        assert market['period'] == 'including_overtime_shootout'
        assert market['outcomes'] == [{'selection': 'Team 1', 'odds': 1.75}, {'selection': 'Team 8', 'odds': 2.3}]

    terminal = START + timedelta(hours=4)
    monkeypatch.setattr(forecast_evidence, '_now', lambda: terminal)
    for sport, _, raw in rows:
        if sport != 'ice_hockey':
            continue
        p = json.loads(raw)
        forecast_evidence.append_result(p['event_key'], 'H2H', p['selection'], 'WIN' if p['selection'] == 'Team 1' else 'LOSS',
            db_path=database, observed_at=terminal, provenance={
                'provider': 'NHL', 'provider_event_id': 'future-match', 'source_record_id': 'nhl:future-match:final',
                'payload_sha256': 'a'*64, 'settlement_rule': 'full-match-winner-with-ot'})
    summary = build_selection_performance_report(database, from_day='2026-09-05', through_day='2026-09-05',
                                                as_of=terminal+timedelta(days=1))
    nhl = [r for r in summary['selections'] if r['sport'] == 'ice_hockey']
    assert {r['outcome'] for r in nhl} == {'WIN', 'LOSS'}
    assert all(r['quote_status'] == 'fresh' and r['hypothetical_return_units'] is None for r in nhl)
    assert summary['summary']['hypothetical_resolved_quote_samples'] == 0
    assert summary['summary']['hypothetical_roi'] is None


@pytest.mark.parametrize('damage,fetched_offset', [
    (None, None), (None, 4), (None, -2100), ('missing_counter_partition', 2), ('different_counter_clock', 2)])
def test_no_entry_for_missing_future_stale_or_inconsistent_odds(monkeypatch, tmp_path, damage, fetched_offset):
    at = None if fetched_offset is None else NOW + timedelta(seconds=fetched_offset)
    _, database, _ = _run(monkeypatch, tmp_path, fetched_at=at, damage=damage)
    assert _read(database, 'SELECT decision_at FROM forecast_rows') == [(NOW.isoformat(),)]*4
    assert _read(database, 'SELECT kind FROM forecast_quotes') == []


def test_a_later_regular_quote_pass_cannot_backfill_an_unpriced_first_forecast(monkeypatch, tmp_path):
    artifact, database, _ = _run(monkeypatch, tmp_path, fetched_at=None)
    later = START - timedelta(minutes=30)
    updated = deepcopy(artifact)
    for row in updated['model_candidates']:
        if row['fixture_source'] == 'NHL':
            native = game('ice_hockey')
            q = prices.parse_game_quotes(odds(native), [row], native, fetched_at=later)[row['candidate_id']]
            row['reference_quote'] = q.to_dict()
    monkeypatch.setattr(forecast_evidence, '_now', lambda: later+timedelta(seconds=1))
    after = forecast_evidence.record_current_closing_quotes(updated, db_path=database, model_version='unused-default')
    assert after['recorded'] == 6
    assert _read(database, 'SELECT DISTINCT kind FROM forecast_quotes') == [('closing',)]
    assert _read(database, 'SELECT decision_at FROM forecast_rows') == [(NOW.isoformat(),)]*4


def test_optional_nhl_entry_failure_does_not_hide_ordinary_forecasts_or_skip_settlement(monkeypatch, tmp_path):
    recorder = forecast_evidence.record_forecast_run

    def fail_only_nhl(document, path, **kwargs):
        sports = {r['fixture_source'] for r in document['model_candidates']}
        if sports == {'NHL'}:
            raise OSError('diagnostic text must not enter the snapshot')
        return recorder(document, path, **kwargs)

    monkeypatch.setattr(forecast_evidence, 'record_forecast_run', fail_only_nhl)
    seen = []

    def settle(*, db_path, **_kwargs):
        seen.extend(_read(db_path, 'SELECT DISTINCT sport FROM forecast_rows'))
        return {'terminal_results': 0, 'operational_error_count': 0}

    state, db, _ = _run(monkeypatch, tmp_path, fetched_at=NOW + timedelta(seconds=2),
                        expected_count=2, evidence_settlement_runner=settle)
    assert seen == [('basketball',)]
    assert state['forecast_evidence']['status'] == 'partial'
    assert state['forecast_evidence']['nhl_entry'] == {'status': 'failed', 'failure_type': 'OSError'}
    assert state['forecast_evidence']['settlement']['terminal_results'] == 0
    # A failed optional write must not backdate a second overlapping NHL entry.
    assert _read(db, 'SELECT DISTINCT sport FROM forecast_rows') == [('basketball',)]
