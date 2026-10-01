"""Both real Tennis prices are retained without another provider request."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import pytest

import market_consensus as markets
import wettfinder_automation as automation
from config_loader import AppConfig
from ev_signal_sources import ModelSignal
from riskobet_prices import load_shared_price_overlays, shared_price_overlays
from riskobet_surface import build_riskobet_card, compose_riskobet_catalog
from test_market_consensus import _gea_zhang_quote_fixture
from test_riskobet_tennis_prices import NOW, _fixture
from test_wettfinder_automation import _football_snapshot


def _native_fixture():
    row, event = _gea_zhang_quote_fixture(NOW)
    row.update(fixture_source='ESPN', provider_event_id='186197', fixture_id=None)
    return row, event


def _transport(monkeypatch, event):
    calls = []
    def provider(path, _key, **kwargs):
        calls.append((path, kwargs))
        if path == 'sports/':
            return [{'key': 'tennis_atp_china_open', 'active': True}], None
        if path.endswith('/events'):
            return [event], None
        assert kwargs['params']['eventIds'] == event['id']
        return [event], None
    monkeypatch.setattr(markets, '_odds_api_json', provider)
    return calls


def _observations(event=None):
    row, normal = _native_fixture()
    return markets._collect_tennis_event_prices(event or normal, [row], now=NOW)


def test_same_request_collects_both_actual_sides_without_changing_normal_return(monkeypatch):
    row, event = _native_fixture()
    before = deepcopy((row, event))
    calls = _transport(monkeypatch, event)
    old_quotes, old_errors = markets.fetch_tennis_h2h_consensus('dummy', [row], now=NOW)
    baseline_calls = deepcopy(calls)
    calls.clear()
    observations = []
    quotes, errors = markets.fetch_tennis_h2h_consensus(
        'dummy', [row], now=NOW, price_observations=observations)
    assert (quotes, errors) == (old_quotes, old_errors)
    assert calls == baseline_calls and len(calls) == 3
    assert quotes[row['candidate_id']].best_odds == 1.52
    assert {r['selected_competitor']: r['reference_quote']['best_odds'] for r in observations} == {
        'Arthur Gea': 1.52, 'Zhang Zhizhen': 2.70}
    assert len({r['candidate_id'] for r in observations}) == 2
    assert all(r['candidate_id'] != row['candidate_id'] for r in observations)
    assert all(r['reference_quote']['fetched_at'] == NOW.isoformat() for r in observations)
    assert (row, event) == before


def test_opposite_price_is_read_by_native_riskobet_winner_not_model_side(tmp_path, monkeypatch):
    row, event = _native_fixture()
    observations = _observations(event)
    _, candidate = _fixture(selected='Zhang Zhizhen')
    normal = markets.parse_h2h_event_consensus(event, [row], fetched_at=NOW)[row['candidate_id']]
    path = tmp_path/'wettfinder.json'
    path.write_text(json.dumps({'model_candidates': [{**row, 'probability': .79,
        'reference_quote': normal.to_dict()}], 'tennis_price_observations': observations}))
    original = path.read_bytes()
    def forbidden(*_args, **_kwargs):
        raise AssertionError('stored reader may not request providers')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    overlay = load_shared_price_overlays([candidate], path=path, now=NOW)[candidate.candidate_id]
    assert overlay.observed_odds == 2.70 and not overlay.below_floor
    assert overlay.observed_at == NOW.isoformat()
    assert path.read_bytes() == original and tuple(tmp_path.iterdir()) == (path,)


def test_missing_opposite_never_invents_a_complement_quote(monkeypatch):
    row, event = _native_fixture()
    event['bookmakers'][0]['markets'][0]['outcomes'] = [{'name': 'Arthur Gea', 'price': 1.52}]
    _transport(monkeypatch, event)
    observations = []
    quotes, _ = markets.fetch_tennis_h2h_consensus('dummy', [row], now=NOW, price_observations=observations)
    assert quotes[row['candidate_id']].best_odds == 1.52 and len(observations) == 1
    _, candidate = _fixture(selected='Zhang Zhizhen')
    assert not shared_price_overlays([candidate], [], now=NOW, tennis_price_observations=observations)


@pytest.mark.parametrize('price,visible', [(1.12, False), (1.199999999, False), (1.20, True), (2.70, True)])
def test_dedicated_opposite_price_reaches_catalog_floor_without_model_change(price, visible):
    row, event = _native_fixture()
    for outcome in event['bookmakers'][0]['markets'][0]['outcomes']:
        if outcome['name'] == 'Zhizhen Zhang':
            outcome['price'] = price
    _, candidate = _fixture(selected='Zhang Zhizhen')
    original = candidate.to_dict()
    observations = markets._collect_tennis_event_prices(event, [row], now=NOW)
    overlay = shared_price_overlays([candidate], [], now=NOW,
        tennis_price_observations=observations)[candidate.candidate_id]
    assert overlay.observed_odds == price and overlay.below_floor is not visible
    card = build_riskobet_card(candidate, overlay)
    assert bool(compose_riskobet_catalog([card]).cards) is visible
    assert card.model_probability == candidate.model_probability
    assert candidate.to_dict() == original


def test_duplicate_provider_event_id_or_ambiguous_event_never_adds_price_observations(monkeypatch):
    row, event = _native_fixture()
    for discovery_duplicate in (False, True):
        calls = []
        def provider(path, _key, **_kwargs):
            calls.append(path)
            if path == 'sports/':
                return [{'key': 'tennis_atp_china_open', 'active': True}], None
            if path.endswith('/events'):
                return ([event, {**event, 'id': 'other-event'}] if discovery_duplicate else [event]), None
            return [event, deepcopy(event)], None
        monkeypatch.setattr(markets, '_odds_api_json', provider)
        observations = []
        quotes, _ = markets.fetch_tennis_h2h_consensus('dummy', [row], now=NOW, price_observations=observations)
        assert not quotes and not observations
        assert len(calls) == (2 if discovery_duplicate else 3)


def test_missing_native_identity_preserves_normal_return_without_unbound_price_rows(monkeypatch):
    row, event = _native_fixture()
    row.pop('fixture_source')
    _transport(monkeypatch, event)
    observations = []
    quotes, errors = markets.fetch_tennis_h2h_consensus('dummy', [row], now=NOW, price_observations=observations)
    assert not errors and quotes[row['candidate_id']].best_odds == 1.52 and not observations


def test_legacy_model_row_and_dedicated_row_do_not_false_conflict_on_ids():
    legacy, candidate = _fixture()
    observations = _observations()
    overlay = shared_price_overlays([candidate], [legacy], now=NOW,
        tennis_price_observations=observations)[candidate.candidate_id]
    assert overlay.observed_odds == 1.52
    # Even legacy rows with different model IDs are the same quote if all native facts agree.
    duplicate = deepcopy(legacy)
    duplicate['candidate_id'] = 'other-model-id'
    duplicate['reference_quote']['candidate_id'] = 'other-model-id'
    assert shared_price_overlays([candidate], [legacy, duplicate], now=NOW)[candidate.candidate_id].observed_odds == 1.52


def test_conflicting_explicit_price_is_unknown_and_cannot_fall_back_to_convenient_legacy():
    legacy, candidate = _fixture()
    first = _observations()[0]
    row, event = _native_fixture()
    for outcome in event['bookmakers'][0]['markets'][0]['outcomes']:
        if outcome['name'] == 'Arthur Gea':
            outcome['price'] = 1.12
    second = _observations(event)[0]
    assert first['selected_competitor'] == second['selected_competitor'] == 'Arthur Gea'
    assert not shared_price_overlays([candidate], [legacy], now=NOW,
        tennis_price_observations=[first, second, first])


@pytest.mark.parametrize('field,value', [
    ('fixture_source', 'OTHER'), ('provider_event_id', '186198'),
    ('scheduled_start', '2030-09-30T09:00:01+00:00'),
    ('scheduled_start', '2030-09-30T09:00:00'),
    ('competitor_a', 'Other Player'), ('competitor_b', 'Other Player'),
    ('selected_competitor', 'Arthur Gea'), ('market_key', 'TOTAL_OVER_2_5'),
    ('quote_provider_event_id', 'another-provider-event'), ('fixture_id', 186197),
])
def test_opposite_side_rejects_foreign_or_incomplete_binding(field, value):
    observations = [r for r in _observations() if r['selected_competitor'] == 'Zhang Zhizhen']
    observations[0][field] = value
    _, candidate = _fixture(selected='Zhang Zhizhen')
    assert not shared_price_overlays([candidate], [], now=NOW, tennis_price_observations=observations)


@pytest.mark.parametrize('change', [
    dict(event_label='Zhang Zhizhen vs Arthur Gea'),
    dict(starts_at=NOW+timedelta(hours=2)),
    dict(market_key='over_2_5_sets', selection_key='over',
         settlement_contract='riskobet-settlement-v1:tennis:over_2_5_sets:over'),
    dict(settlement_contract='riskobet-settlement-v1:tennis:match_winner:away:retirement'),
])
def test_opposite_quote_never_crosses_kickoff_player_order_or_settlement(change):
    _, candidate = _fixture(selected='Zhang Zhizhen')
    assert not shared_price_overlays([replace(candidate, **change)], [], now=NOW,
        tennis_price_observations=_observations())


def test_original_clocks_are_retained_and_expired_facts_are_pruned():
    observations = _observations()
    # Keep a future kickoff while aging the actual observation; never renew receipt time.
    for row in observations:
        row['scheduled_start'] = (NOW+timedelta(days=3)).isoformat()
        row['reference_quote']['scheduled_start'] = row['scheduled_start']
    current = NOW+timedelta(hours=3)
    kept = markets.bounded_tennis_price_observations(observations, now=current)
    assert len(kept) == 2
    assert all(r['reference_quote']['fetched_at'] == NOW.isoformat() for r in kept)
    assert markets.bounded_tennis_price_observations(observations, now=NOW+timedelta(hours=24, seconds=1)) == []
    for row in observations:
        row['reference_quote']['points'][0]['observed_at'] = (NOW+timedelta(hours=5)).isoformat()
    assert markets.bounded_tennis_price_observations(observations, now=current) == []


def test_boundaries_and_merge_never_accumulate_price_history():
    base = _observations()
    rows = []
    for n in range(10):
        for original in base:
            row = deepcopy(original)
            row['provider_event_id'] = str(n)
            rows.append(row)
    assert len(markets.bounded_tennis_price_observations(rows, now=NOW)) == 20
    assert markets.bounded_tennis_price_observations(rows+[deepcopy(base[0])], now=NOW) == []
    eleven = deepcopy(rows[:11])
    for n, row in enumerate(eleven):
        row['provider_event_id'] = str(n)
    assert markets.bounded_tennis_price_observations(eleven, now=NOW) == []
    huge = deepcopy(base)
    huge[0]['unneeded_model_payload'] = 'x'*(markets.TENNIS_PRICE_MAX_BYTES+1)
    assert markets.bounded_tennis_price_observations(huge, now=NOW) == []
    normal, _ = _native_fixture()
    merged = markets.merge_tennis_price_observations(rows, base, [normal], now=NOW)
    assert len(merged) <= 20 and len({r['provider_event_id'] for r in merged}) <= 10
    # A checked response containing only one side replaces the old opposite price.
    assert markets.merge_tennis_price_observations(base, base[:1], [normal], now=NOW) == base[:1]
    assert markets.merge_tennis_price_observations(base, [], [normal], now=NOW) == []
    assert markets.merge_tennis_price_observations(base, [], [], now=NOW) == base


def test_malformed_or_unencodable_bounded_prices_fail_without_writes_or_crashes(monkeypatch):
    surrogate = _observations()
    surrogate[0]['invalid_extra'] = '\ud800'
    assert markets.bounded_tennis_price_observations(surrogate, now=NOW) == []
    recursive = _observations()
    recursive[0]['recursive_extra'] = recursive
    assert markets.bounded_tennis_price_observations(recursive, now=NOW) == []
    deeply_nested = _observations()
    nested = []
    for _ in range(2000):
        nested = [nested]
    deeply_nested[0]['nested_extra'] = nested
    # Some test environments raise the recursion limit: accepted extra fields
    # are still discarded, while recursion-limited serialization fails unknown.
    kept = markets.bounded_tennis_price_observations(deeply_nested, now=NOW)
    assert not kept or all('nested_extra' not in row for row in kept)
    invalid = _observations()
    invalid[0]['scheduled_start'] = '0001-01-01T00:00:00+14:00'
    invalid[1]['reference_quote']['scheduled_start'] = '0001-01-01T00:00:00+14:00'
    assert markets.bounded_tennis_price_observations(invalid, now=NOW) == []
    def recursion_error(*_args, **_kwargs):
        raise RecursionError('bounded serialization')
    with monkeypatch.context() as patch:
        patch.setattr(markets.json, 'dumps', recursion_error)
        assert markets.bounded_tennis_price_observations(invalid, now=NOW) == []


def test_price_only_refresh_persists_both_sides_in_same_snapshot_without_model_changes(tmp_path, monkeypatch):
    row, event = _native_fixture()
    row.update(key=row['candidate_id'], source='tennis_shadow', status='MODEL_SELECTION',
               probability=.794, conservative_probability=.714, probability_haircut=.08,
               evidence_stage='SHADOW', detail='original-model-text', model_fetched_at=NOW.isoformat())
    path = tmp_path/'wettfinder.json'
    path.write_text(json.dumps({'model_candidates': [row], 'price_check_attempts': {}}))
    calls = _transport(monkeypatch, event)
    summary = automation.refresh_prices_only(state_path=path, config=AppConfig(odds_api_key='dummy'),
        now=NOW, quote_sport='tennis')
    saved = json.loads(path.read_text())
    assert summary['errors'] == 0 and len(calls) == 3
    assert len(saved['tennis_price_observations']) == 2
    assert len(saved['model_candidates']) == 1
    assert all(saved['model_candidates'][0][field] == row[field] for field in
               ('probability', 'detail', 'model_fetched_at', 'selected_competitor'))
    assert tuple(tmp_path.iterdir()) == (path,)


def test_regular_writer_uses_same_default_request_and_persists_observations_separately(tmp_path, monkeypatch):
    row, event = _native_fixture()
    path = tmp_path/'regular.json'
    monkeypatch.setattr(automation, 'STATE_PATH', path)
    calls = _transport(monkeypatch, event)
    signal = ModelSignal(key=row['candidate_id'], label='Gea vs Zhang', probability=.794,
        probability_haircut=.08, evidence_stage='SHADOW', policy_version='test', detail='original',
        sport='Tennis', market_key='H2H', scheduled_start=row['scheduled_start'],
        competitor_a=row['competitor_a'], competitor_b=row['competitor_b'],
        selected_competitor=row['selected_competitor'], fixture_source='ESPN', provider_event_id='186197')
    document = automation.run_wettfinder(now=NOW, state_path=path,
        config=AppConfig(api_football_key=None, odds_api_key='dummy'),
        football_scanner=lambda _date: _football_snapshot(NOW), football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [signal], tennis_model_refresher=lambda **_kwargs: {},
        esports_loader=lambda **_kwargs: [], riskobet_enabled=False,
        esports_settlement_runner=lambda *_args, **_kwargs: {},
        evidence_db_path=tmp_path/'evidence.db', evidence_settlement_runner=lambda **_kwargs: {})
    assert len(calls) == 3 and len(document['tennis_price_observations']) == 2
    tennis_models = [r for r in document['model_candidates'] if r['sport'] == 'Tennis']
    assert len(tennis_models) == 1 and tennis_models[0]['probability'] == .794
    assert tennis_models[0]['selected_competitor'] == 'Arthur Gea'
    assert json.loads(path.read_text())['tennis_price_observations'] == document['tennis_price_observations']
