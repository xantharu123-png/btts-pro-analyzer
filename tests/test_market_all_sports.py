"""Native market measurement reuses received prices, not selection/EV gates."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import sqlite3

import pytest

import forecast_evidence as evidence
from forecast_market_comparison import build_market_comparison
from riskobet_domain import stable_event_key
from test_native_market_partitions import football_prices, football_row
from test_forecast_market_comparison import NOW, START


def save(db, monkeypatch, row, now):
    monkeypatch.setattr(evidence, '_now', lambda: now)
    row.update(modeled_at=now.isoformat(), input_cutoff_at=now.isoformat(), probability=.7,
               conservative_probability=None)
    original = deepcopy(row)
    result = evidence.record_forecast_run(dict(generated_at=now.isoformat(),
        selection_policy_version='native-test', model_candidates=[row]), db, 'native-test')
    assert result['recorded'] == 1 and result['quotes_rejected'] == []
    assert row == original
    return result


def settle(db, monkeypatch, row, now):
    monkeypatch.setattr(evidence, '_now', lambda: now)
    evidence.append_result(row['event_identity'], row['market_key'], row['selection'], 'WIN',
        db_path=db, observed_at=now, provenance=dict(provider=row.get('fixture_source') or 'api-football',
        provider_event_id=str(row.get('provider_event_id') or row['fixture_id']), source_record_id='native:final',
        payload_sha256='a'*64, settlement_rule='native-final-v1'))


@pytest.mark.parametrize('key,selection', [('HOME_OVER_0_5', 'Über 0.5'), ('DC_1X', '1X')])
def test_single_football_selection_compares_only_against_complete_real_partition(tmp_path, monkeypatch, key, selection):
    row = football_row(key, selection)
    row['reference_quote'] = football_prices(row).to_dict()
    db = tmp_path/'evidence.db'
    save(db, monkeypatch, row, NOW)
    settled = START+timedelta(hours=3)
    settle(db, monkeypatch, row, settled)
    before = db.read_bytes()
    report = build_market_comparison(db, as_of=settled)
    assert db.read_bytes() == before
    assert report['groups'] == []  # Never turn one 3-way model side into a distribution.
    group, = report['selection_groups']
    expected = (1/1.4)/(1/1.4+1/3.5) if key != 'DC_1X' else (1/2+1/3.2)/(1/2+1/3.2+1/4)
    assert group['model_brier'] == pytest.approx(.09)
    assert group['market_brier'] == pytest.approx((1-expected)**2)
    assert group['unique_events'] == 1
    assert report['sport_coverage']['football']['matched_unique_events'] == 1


@pytest.mark.parametrize('sport', ['basketball', 'ice_hockey', 'esports', 'tennis'])
def test_one_native_winner_forecast_retains_real_opposing_odds_for_binary_measurement(tmp_path, monkeypatch, sport):
    if sport in {'basketball', 'ice_hockey'}:
        from test_team_sport_prices import row as team_row, game, odds, NOW as decision
        from team_sport_prices import parse_game_quotes
        row = team_row(sport)
        quote = parse_game_quotes(odds(game(sport)), [row], game(sport), fetched_at=decision)[row['candidate_id']]
        row['event_identity'] = stable_event_key(sport, row['fixture_source'], row['provider_event_id'])
        expected = (1/1.75)/(1/1.75+1/2.30)
    elif sport == 'esports':
        from test_esports_prices import row as esports_row, quote as esports_quote, NOW as decision
        row = esports_row(selection='Sparta eSports', competitor_a_id=1, competitor_b_id=2)
        quote = esports_quote(row)
        row['event_identity'] = stable_event_key(sport, row['fixture_source'], row['provider_event_id'])
        expected = (1/2.5)/(1/2.5+1/1.48)
    else:
        from test_forecast_tennis_market_capture import fixture, NOW as decision
        row, _ = fixture()
        from market_consensus import MarketConsensus
        quote = MarketConsensus.from_dict(row['reference_quote'])
        expected = (1/1.52)/(1/1.52+1/2.7)
    row['reference_quote'] = quote.to_dict()
    db = tmp_path/'evidence.db'
    save(db, monkeypatch, row, decision)
    settled = evidence._utc(row['scheduled_start'])+timedelta(hours=3)
    settle(db, monkeypatch, row, settled)
    report = build_market_comparison(db, as_of=settled)
    group, = report['selection_groups']
    assert group['sport'] == sport and group['unique_events'] == 1
    assert group['market_brier'] == pytest.approx((1-expected)**2)
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM forecast_rows').fetchone()[0] == 1


@pytest.mark.parametrize('damage', ['period', 'opposite_missing', 'native_event', 'book', 'clock', 'selected_price', 'duplicate'])
def test_optional_native_partition_is_not_allowed_to_cross_contracts(tmp_path, monkeypatch, damage):
    row = football_row()
    row['reference_quote'] = football_prices(row).to_dict()
    db = tmp_path/'evidence.db'
    save(db, monkeypatch, row, NOW)
    settled = START+timedelta(hours=3)
    settle(db, monkeypatch, row, settled)
    with sqlite3.connect(db) as conn:
        conn.execute('DROP TRIGGER forecast_quotes_no_update')
        raw, = conn.execute('SELECT payload_json FROM forecast_quotes').fetchone()
        payload = json.loads(raw)
        part = payload['native_market_partition']
        if damage == 'period': part['period'] = 'first_half'
        elif damage == 'opposite_missing': part['outcomes'].pop()
        elif damage == 'native_event': part['provider_event_id'] = '999'
        elif damage == 'book': part['bookmaker_id'] = 'elsewhere'
        elif damage == 'clock': part['observed_at'] = (NOW-timedelta(seconds=1)).isoformat()
        elif damage == 'selected_price': part['outcomes'][0]['odds'] += .1
        else: part['outcomes'][1]['selection'] = part['outcomes'][0]['selection']
        conn.execute('UPDATE forecast_quotes SET payload_json=?', (json.dumps(payload),))
    assert build_market_comparison(db, as_of=settled)['selection_groups'] == []


def test_all_six_sports_have_honest_coverage_even_when_no_native_cricket_prices_exist(tmp_path):
    missing = tmp_path/'absent.db'
    result = build_market_comparison(missing)
    assert set(result['sport_coverage']) == {'football', 'tennis', 'basketball', 'ice_hockey', 'esports', 'cricket'}
    assert result['sport_coverage']['cricket']['matched_unique_events'] == 0
    assert result['sport_coverage']['cricket']['native_price_adapter'] is False
    assert not missing.exists()


@pytest.mark.parametrize('sport,provider', [('basketball', 'ESPN'), ('basketball', 'EuroLeague'),
                                         ('ice_hockey', 'NHL'), ('ice_hockey', 'API-Hockey')])
def test_completed_team_cache_resolves_frozen_winners_without_scanning(tmp_path, monkeypatch, sport, provider):
    from forecast_evidence_settlement import run_forecast_evidence_settlements
    from scanners.completed_history import CompletedHistoryStore, result_row
    from test_team_sport_prices import row as team_row, NOW as decision
    row = team_row(sport, fixture_source=provider, competitor_a_id='101', competitor_b_id='202',
        event_identity=stable_event_key(sport, provider, 'native-1'))
    db = tmp_path/'evidence.db'
    save(db, monkeypatch, row, decision)
    start = evidence._utc(row['scheduled_start'])
    settled = start+timedelta(hours=4)
    history = tmp_path/'history.db'
    native = result_row(provider=provider, event_id='native-1', start=start, home='Team 1', away='Team 8',
        home_id='101', away_id='202', home_score=4 if sport == 'ice_hockey' else 104,
        away_score=2 if sport == 'ice_hockey' else 102, sport=sport,
        result_scope='including_overtime_shootout' if sport == 'ice_hockey' else 'including_overtime',
        last_period_type='REG', regulation_home_score=4, regulation_away_score=2,
        source_contract='api-hockey-games-v1', league_id=3, season=2026)
    store = CompletedHistoryStore(history, clock=lambda: settled)
    store.record(provider, 'already-received', [native])
    before = hashlib.sha256(history.read_bytes()).hexdigest()
    monkeypatch.setattr(evidence, '_now', lambda: settled)
    outcome = run_forecast_evidence_settlements(db_path=db, now=settled, team_history_path=history)
    assert outcome['terminal_results'] == 1 and outcome['operational_error_count'] == 0
    assert hashlib.sha256(history.read_bytes()).hexdigest() == before
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT outcome FROM forecast_results').fetchone()[0] == 'WIN'


@pytest.mark.parametrize('damage', ['team', 'scope', 'score', 'status', 'hash', 'time'])
def test_invalid_basketball_cache_never_settles_from_elapsed_time(tmp_path, monkeypatch, damage):
    from forecast_evidence_settlement import run_forecast_evidence_settlements
    from scanners.completed_history import CompletedHistoryStore, result_row
    from test_team_sport_prices import row as team_row, NOW as decision
    row = team_row('basketball', competitor_a_id='101', competitor_b_id='202',
        event_identity=stable_event_key('basketball', 'ESPN', 'native-1'))
    db = tmp_path/'evidence.db'
    save(db, monkeypatch, row, decision)
    start = evidence._utc(row['scheduled_start']); settled = start+timedelta(hours=4)
    history = tmp_path/'history.db'
    native = result_row(provider='ESPN', event_id='native-1', start=start, home='Team 1', away='Team 8',
        home_id='101', away_id='202', home_score=104, away_score=102, sport='basketball',
        result_scope='including_overtime')
    field, value = {'team': ('home_team_id', '999'), 'scope': ('result_scope', 'regulation'),
        'score': ('home_score', True), 'status': ('status', 'retracted'),
        'time': ('start_time', (start+timedelta(hours=1)).isoformat()), 'hash': ('home_score', 105)}[damage]
    native[field] = value
    CompletedHistoryStore(history, clock=lambda: settled).record('ESPN', 'received', [native])
    if damage == 'hash':
        with sqlite3.connect(history) as conn:
            conn.execute("UPDATE history_result_revisions SET digest=?", ('a'*64,))
    monkeypatch.setattr(evidence, '_now', lambda: settled)
    outcome = run_forecast_evidence_settlements(db_path=db, now=settled, team_history_path=history)
    assert outcome['terminal_results'] == 0


def test_cricket_without_native_price_adapter_stays_an_explicit_data_gap(tmp_path, monkeypatch):
    decision = NOW
    row = dict(candidate_id='cricket-1', event_identity='cricket:Cricbuzz:1', sport='cricket',
        fixture_source='Cricbuzz', provider_event_id='1', scheduled_start=START.isoformat(),
        competitor_a='A', competitor_b='B', selected_competitor='A', market_key='H2H', selection='A')
    db = tmp_path/'evidence.db'
    save(db, monkeypatch, row, decision)
    settled = START+timedelta(hours=8)
    settle(db, monkeypatch, row, settled)
    result = build_market_comparison(db, as_of=settled)
    assert result['selection_groups'] == []
    assert result['sport_coverage']['cricket']['first_causal_selections'] == 1
    assert result['sport_coverage']['cricket']['resolved_selections'] == 1
    assert result['sport_coverage']['cricket']['native_price_adapter'] is False


@pytest.mark.parametrize('damage', ['oversized', 'blob', 'same_clock_conflict'])
def test_team_result_rejects_unbounded_or_ambiguous_body_before_materializing(tmp_path, monkeypatch, damage):
    from forecast_evidence_settlement import _cached_team_result
    now = START+timedelta(hours=3)
    history = tmp_path/'history.db'
    payload = ('\N{EURO SIGN}'*30000) if damage == 'oversized' else b'not-text'
    with sqlite3.connect(history) as conn:
        # A malformed imported DB cannot rely on the regular primary key.
        conn.execute('CREATE TABLE history_result_revisions(provider,event_id,observed_at,digest,payload)')
        conn.execute('INSERT INTO history_result_revisions VALUES(?,?,?,?,?)',
            ('ESPN', '1', now.isoformat(), 'a'*64, payload if damage != 'same_clock_conflict' else '{}'))
        if damage == 'same_clock_conflict':
            conn.execute('INSERT INTO history_result_revisions VALUES(?,?,?,?,?)',
                ('ESPN', '1', now.isoformat(), 'b'*64, '{"changed":true}'))
    statements = []
    connect = sqlite3.connect
    def traced(*args, **kwargs):
        conn = connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn
    monkeypatch.setattr(sqlite3, 'connect', traced)
    identity = ('basketball', 'espn', '1', START, 'A', 'B', '10', '20')
    assert _cached_team_result(identity, [], history, now) is None
    assert any('length(CAST(payload AS BLOB))' in sql for sql in statements)
    assert not any(sql.startswith('SELECT payload FROM history_result_revisions') for sql in statements)


@pytest.mark.parametrize('change', ['oversized', 'valid_opposite_result'])
def test_concurrent_hockey_cache_change_cannot_cross_two_reader_snapshots(tmp_path, monkeypatch, change):
    import forecast_evidence_settlement as settlements
    from test_api_hockey_integration import result_cache
    history, now, request = result_cache(tmp_path)
    with sqlite3.connect(history) as conn:
        assert conn.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    identity = request.team_sport_identity
    native_identity = ('ice_hockey', 'api-hockey', identity['provider_event_id'], request.starts_at,
        identity['home'], identity['away'], identity['home_id'], identity['away_id'])
    actual_loader = settlements.ice_hockey_result_loader
    def replace_between_reads(path):
        def load(requests, clock):
            with sqlite3.connect(path) as conn:
                raw, = conn.execute('SELECT payload FROM history_result_revisions').fetchone()
                if change == 'oversized':
                    replacement = '\N{EURO SIGN}'*30000
                else:
                    payload = json.loads(raw)
                    payload.update(home_score=2, away_score=6, winner_side='away')
                    replacement = json.dumps(payload, separators=(',', ':'), sort_keys=True)
                conn.execute('UPDATE history_result_revisions SET payload=?,digest=?',
                    (replacement, hashlib.sha256(replacement.encode('utf-8')).hexdigest()))
            return actual_loader(path)(requests, clock)
        return load
    monkeypatch.setattr(settlements, 'ice_hockey_result_loader', replace_between_reads)
    rows = [dict(forecast_id='frozen', candidate_id='frozen')]
    assert settlements._cached_team_result(native_identity, rows, history, now) is None


@pytest.mark.parametrize('damage', ['oversized', 'blob', 'same_clock_conflict'])
def test_hockey_owner_itself_checks_scalar_size_before_body(tmp_path, monkeypatch, damage):
    from test_api_hockey_integration import result_cache
    from riskobet_settlement_automation import ice_hockey_result_loader
    history, now, request = result_cache(tmp_path)
    with sqlite3.connect(history) as conn:
        if damage == 'same_clock_conflict':
            conn.execute('ALTER TABLE history_result_revisions RENAME TO old_results')
            conn.execute('CREATE TABLE history_result_revisions AS SELECT * FROM old_results')
            conn.execute('INSERT INTO history_result_revisions SELECT * FROM old_results')
        else:
            conn.execute('UPDATE history_result_revisions SET payload=?',
                ('\N{EURO SIGN}'*30000 if damage == 'oversized' else b'not-text',))
    statements = []
    connect = sqlite3.connect
    def traced(*args, **kwargs):
        conn = connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn
    monkeypatch.setattr(sqlite3, 'connect', traced)
    result = ice_hockey_result_loader(history)((request,), now)
    assert not result.results and result.issues[0].code == 'native_result_unavailable'
    assert not any(sql.startswith('SELECT payload FROM history_result_revisions') for sql in statements)
