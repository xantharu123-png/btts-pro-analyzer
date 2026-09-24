"""Product regressions from the real September 21 audit, not happy-path mocks."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import challenge_15k
from challenge_engine import MARKET_BY_KEY
from daily3_selection import daily3_choices
from test_challenge_15k import candidate
from test_daily3_selection import NOW, football


def market(key, fixture=1):
    spec = MARKET_BY_KEY[key]
    return replace(candidate(f'{fixture}:{key}', fixture, .75), market_key=key,
                   market=spec.market, selection=spec.selection)


@pytest.mark.parametrize('keys', [
    ('RESULT_HOME', 'RESULT_AWAY'), ('AWAY_UNDER_1_5', 'AWAY_OVER_1_5'),
    ('HOME_UNDER_1_5', 'HOME_OVER_1_5'), ('RESULT_HOME', 'DC_X2'),
])
def test_15k_never_reintroduces_opposing_rows_or_ticket_candidates(monkeypatch, keys):
    rows = [market(k) for k in keys]
    snapshot = dict(shortlist=[], forecast_shortlist=rows, basis_forecasts=rows,
                    price_candidates=rows, reference_quotes={})
    original = deepcopy(snapshot)
    rendered = []
    builder = MagicMock(return_value=(None, {}, {}))
    monkeypatch.setattr(challenge_15k, 'st', MagicMock())
    monkeypatch.setattr(challenge_15k, '_render_challenge_candidate',
                        lambda row, *_: rendered.append(row))
    monkeypatch.setattr(challenge_15k, '_automatic_challenge_ticket', builder)
    challenge_15k._render_price_check(snapshot, MagicMock(), {})
    assert len(rendered) == 1
    assert builder.call_args.args[0] == rendered
    assert snapshot == original  # Keep the complete internal model distribution.


def test_daily3_risk_priority_precedes_form_margin_and_pool_order():
    higher_risk = football(1, probability=.74, variants=(.74, .70, .74))
    lower_risk = football(2, probability=.88, variants=(.88, .85, .88))
    for pool in ([higher_risk, lower_risk], [lower_risk, higher_risk]):
        choices = daily3_choices(pool, now=NOW)
        assert [c.signal.probability for c in choices] == [.88, .74]


@pytest.mark.parametrize('injuries, expected', [
    ({'availability': 'not_covered', 'coverage_available': False, 'status': 'unavailable',
      'checked_at': NOW.isoformat()}, 'nicht abgedeckt'),
    ({}, 'offen'),
    ({'availability': 'available', 'coverage_available': True, 'status': 'observed',
      'checked_at': (NOW-timedelta(hours=2)).isoformat(), 'home_missing': 0, 'away_missing': 0}, 'veraltet'),
    ({'availability': 'available', 'coverage_available': True, 'status': 'observed',
      'checked_at': NOW.isoformat(), 'home_missing': 0, 'away_missing': 0}, '0 Heim · 0 Gast'),
    ({'availability': 'available', 'coverage_available': True, 'status': 'observed',
      'checked_at': NOW.isoformat(), 'home_missing': True, 'away_missing': 0}, 'offen'),
])
def test_injury_fact_distinguishes_missing_stale_and_verified_zero(injuries, expected):
    from forecast_compact import football_injury_fact
    fact = football_injury_fact({'injuries': injuries}, 'Manta', 'Orense', now=NOW)
    assert fact.value == expected
    assert fact.warning == (expected != '0 Heim · 0 Gast')


def test_15k_injury_rendering_uses_shared_unknown_state(monkeypatch):
    st = MagicMock()
    columns = [MagicMock(), MagicMock(), MagicMock()]
    st.columns.return_value = columns
    monkeypatch.setattr(challenge_15k, 'st', st)
    row = replace(market('RESULT_HOME'), context={'injuries': {
        'availability': 'not_covered', 'coverage_available': False,
        'status': 'unavailable', 'checked_at': NOW.isoformat()}})
    challenge_15k._render_candidate_context(row)
    assert columns[1].metric.call_args.args[1] == 'nicht abgedeckt'
    assert columns[1].metric.call_args.kwargs['help']


def test_existing_riskobet_data_can_publish_new_explanations_without_rewriting_history(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    import sqlite3
    import subprocess
    import sys
    import types
    import riskobet_candidates as current
    from riskobet_automation import RiskSourceBatch, run_riskobet
    from riskobet_store import RiskBetStore
    from test_riskobet_candidates import create_tennis_db, insert_tennis, MODELED_AT
    root = Path(__file__).resolve().parents[1]
    prior_source = subprocess.check_output(['git', 'show',
        '1e2c6f5c19b8ba32d8a970c622109e049f8c4060:riskobet_candidates.py'], cwd=root).decode('utf-8')
    prior = types.ModuleType('riskobet_pre_product_repair')
    prior.__file__ = str(root/'riskobet_candidates.py')
    monkeypatch.setitem(sys.modules, prior.__name__, prior)
    exec(compile(prior_source, prior.__file__, 'exec'), prior.__dict__)
    source = tmp_path/'tennis.db'
    create_tennis_db(source)
    insert_tennis(source, row_id=1, p_a=.35, markets='{}')
    with sqlite3.connect(source) as db:
        db.execute('UPDATE predictions SET context_json=?', (json.dumps({'players': {
            'a': {'facts': ['Player A: 3 Sätze beobachtet.']}}}),))
    store = RiskBetStore(tmp_path/'risk.db', tmp_path/'latest.json')
    old = prior.adapt_tennis_shadow(source, as_of=MODELED_AT)[0]
    old_batch = RiskSourceBatch(sport='tennis', snapshots=(old.snapshot,), candidates=old.candidates)
    run_riskobet(tennis_source=old_batch, store=store, now=MODELED_AT)
    before = store.read_latest()
    new = current.adapt_tennis_shadow(source, as_of=MODELED_AT)[0]
    assert new.snapshot.snapshot_id != old.snapshot.snapshot_id
    assert new.candidates[0].candidate_id != old.candidates[0].candidate_id
    assert new.candidates[0].model_probability == old.candidates[0].model_probability
    run_riskobet(tennis_source=(new,), store=store, now=MODELED_AT+timedelta(minutes=1))
    assert store.read_latest()['candidates'][0]['pros'] == list(new.candidates[0].pros)
    with sqlite3.connect(store.db_path) as db:
        stored = json.loads(db.execute('SELECT payload_json FROM snapshots WHERE snapshot_id=?',
                                      (old.snapshot.snapshot_id,)).fetchone()[0])
    assert stored == before['snapshots'][0]
