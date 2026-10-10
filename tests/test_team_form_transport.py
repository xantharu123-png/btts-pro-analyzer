"""Real producer/persistence regressions, not manually injected form payloads."""
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from ev_signal_sources import ModelSignal
from forecast_analysis import build_forecast_analysis
from forecast_compact import build_compact_analysis
from riskobet_automation import snapshot_from_dict
from riskobet_candidates import adapt_research_matchwinner
from riskobet_domain import RiskRunSnapshot, RunStatus
from riskobet_store import RiskBetStore
from sports_form import render_form_html
from team_sport_forecasts import team_sport_forecast_rows
from test_sports_prematch import NOW, event, history


@pytest.mark.parametrize('sport', ['basketball', 'ice_hockey'])
def test_actual_adapter_store_json_and_card_preserve_ten_recent_games(tmp_path, sport):
    snapshot = adapt_research_matchwinner(sport,
        event(sport, source_observed_at=NOW.isoformat()), history(sport), modeled_at=NOW).snapshot
    run = RiskRunSnapshot(started_at=NOW, completed_at=NOW, status=RunStatus.COMPLETE,
        snapshots=(snapshot,))
    store = RiskBetStore(tmp_path / 'risk.db')
    store.append_run(run)
    payload = json.loads(json.dumps(store.load_run(run.run_id)['snapshots'][0]))
    restored = snapshot_from_dict(payload)
    from riskobet_ui import _snapshot
    assert _snapshot(payload) == restored == snapshot
    row = team_sport_forecast_rows(SimpleNamespace(snapshots=(restored,)),
        now=NOW, target_date=NOW.date())[0]
    signal = ModelSignal(**{k: v for k, v in row.items() if k in ModelSignal.__dataclass_fields__},
        event_label=row['event'])
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)
    assert len(compact.forms) == 2
    assert [len(form.results) for form in compact.forms] == [10, 10]
    assert compact.forms[1].results[0].opponent == 'Team 7'
    assert compact.forms[1].results[0].score == ('100:109' if sport == 'basketball' else '1:3')
    markup = render_form_html(compact.forms)
    assert '5 Spiele' in markup and '10 Spiele' in markup and 'Team 7' in markup
    assert signal.probability == snapshot.team_sport_forecast.p_home
    assert signal.team_sport_snapshot['team_sport_forecast']['model_input_hash'] == snapshot.team_sport_forecast.model_input_hash


@pytest.mark.parametrize('sport,legacy_hash,legacy_id', [
    ('basketball', 'bfc3221f31c212c2217f367b7438e1668abb30c3697adaab6f3a309ae3c5cf25',
     'snapshot_2d63be4e5bedd846e6d854f5e471ba6d6048204dfbd6adce96e05d8583544b26'),
    ('ice_hockey', 'd18ad3566a9b039e50c551a1af2ecc7cb5a9d9721224b177e46777ffe76e364c',
     'snapshot_818846c4327799de9b1e07dc3febaadc134a2812675a62f6c06e7c6d72dddc30'),
])
def test_legacy_revision_is_unchanged_and_new_form_revision_can_coexist(tmp_path, sport, legacy_hash, legacy_id):
    current = adapt_research_matchwinner(sport,
        event(sport, source_observed_at=NOW.isoformat()), history(sport), modeled_at=NOW).snapshot
    legacy = replace(current, input_hash=legacy_hash, customer_recent_results=None)
    assert legacy.snapshot_id == legacy_id
    old_bytes = json.dumps(legacy.to_dict(), sort_keys=True)
    assert 'customer_recent_results' not in legacy.to_dict()
    store = RiskBetStore(tmp_path / 'risk.db')
    old_run = RiskRunSnapshot(started_at=NOW, completed_at=NOW,
        status=RunStatus.COMPLETE, snapshots=(legacy,))
    store.append_run(old_run)
    new_run = RiskRunSnapshot(started_at=NOW, completed_at=NOW,
        status=RunStatus.COMPLETE, snapshots=(current,))
    store.append_run(new_run)
    assert current.input_hash != legacy_hash and current.snapshot_id != legacy_id
    assert json.dumps(store.load_run(old_run.run_id)['snapshots'][0], sort_keys=True) == old_bytes
    assert store.load_run(new_run.run_id)['snapshots'][0]['customer_recent_results']


def test_sidecar_is_detached_immutable_and_bound_to_snapshot_identity():
    snapshot = adapt_research_matchwinner('basketball',
        event('basketball', source_observed_at=NOW.isoformat()), history('basketball'), modeled_at=NOW).snapshot
    with pytest.raises(TypeError):
        snapshot.customer_recent_results['a_results'][0]['score'] = '128:100'
    exported = snapshot.to_dict()
    exported['customer_recent_results']['a_results'][0]['score'] = '128:100'
    event_id = exported['customer_recent_results']['a_results'][0]['event_id']
    for row in exported['customer_recent_results']['b_results']:
        if row['event_id'] == event_id:
            row['score'] = '100:128'
    assert snapshot.customer_recent_results['a_results'][0]['score'] == '127:100'
    with pytest.raises(ValueError, match='snapshot_id'):
        snapshot_from_dict(exported)


def test_actual_nhl_form_tiles_expand_only_exact_reviewed_team_identities():
    target = event('ice_hockey', home_team='BOS', home_team_id='6',
        away_team='PHI', away_team_id='4', source_observed_at=NOW.isoformat())
    rows = history('ice_hockey')
    for result in rows:
        for side in ('home', 'away'):
            if result[side + '_team_id'] in ('6', '4'):
                result[side + '_team'] = {'6': 'BOS', '4': 'PHI'}[result[side + '_team_id']]
    snapshot = adapt_research_matchwinner('ice_hockey', target, rows, modeled_at=NOW).snapshot
    row = team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)),
        now=NOW, target_date=NOW.date())[0]
    signal = ModelSignal(**{k: v for k, v in row.items() if k in ModelSignal.__dataclass_fields__},
        event_label=row['event'])
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)
    assert [form.team for form in compact.forms] == ['Boston Bruins', 'Philadelphia Flyers']
    assert any(result.opponent == 'Boston Bruins' for result in compact.forms[1].results)
    assert signal.competitor_a == 'BOS' and signal.competitor_b == 'PHI'


@pytest.mark.parametrize('change', [
    {'competition': 'Wrong'}, {'input_cutoff_at': (NOW - timedelta(minutes=1)).isoformat()},
])
def test_store_rejects_correctly_hashed_but_misbound_recent_results(change):
    from riskobet_store import canonical_json, _digest
    snapshot = adapt_research_matchwinner('basketball',
        event('basketball', source_observed_at=NOW.isoformat()), history('basketball'), modeled_at=NOW).snapshot
    payload = {**snapshot.to_dict(), **change}
    encoded = canonical_json(payload)
    row = {key: payload[key] for key in ('snapshot_id', 'event_key', 'sport', 'model_version',
        'input_hash', 'modeled_at')}
    row.update(payload_json=encoded, content_hash=_digest(encoded))
    with pytest.raises(ValueError):
        snapshot_from_dict(payload)
    with pytest.raises(ValueError):
        RiskBetStore._verified_snapshot_row(row)
