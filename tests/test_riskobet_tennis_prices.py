"""Read-only exact reuse of already stored tennis winner offers."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from market_consensus import parse_h2h_event_consensus
from riskobet_domain import stable_event_key
from riskobet_prices import load_shared_price_overlays, shared_price_overlays
from riskobet_surface import build_riskobet_card, compose_riskobet_catalog
from test_market_consensus import _gea_zhang_quote_fixture
from test_riskobet_ui import _bundle


NOW = datetime(2030, 9, 30, 8, tzinfo=timezone.utc)


def _fixture(price=1.52, *, selected='Arthur Gea', age=timedelta()):
    observed = NOW - age
    row, event = _gea_zhang_quote_fixture(observed, selected=selected)
    row.update(fixture_source='ESPN', provider_event_id='186197')
    for outcome in event['bookmakers'][0]['markets'][0]['outcomes']:
        if outcome['name'] == ('Arthur Gea' if selected == 'Arthur Gea' else 'Zhizhen Zhang'):
            outcome['price'] = price
    quote = parse_h2h_event_consensus(event, [row], fetched_at=observed)[row['candidate_id']]
    row.update(reference_quote=quote.to_dict(), quote_provider_event_id=quote.provider_event_id)
    _, template = _bundle('tennis-shared-price', sport='tennis')
    side = 'home' if selected == row['competitor_a'] else 'away'
    candidate = replace(template, event_key=stable_event_key('tennis', 'ESPN', '186197'),
        starts_at=datetime.fromisoformat(row['scheduled_start']),
        event_label=f"{row['competitor_a']} vs {row['competitor_b']}",
        market_key='match_winner', selection_key=side, selection_label=selected,
        settlement_contract=f'riskobet-settlement-v1:tennis:match_winner:{side}')
    return row, candidate


@pytest.mark.parametrize('price, visible', [(1.12, False), (1.199999999, False), (1.20, True), (1.52, True)])
@pytest.mark.parametrize('selected', ['Arthur Gea', 'Zhang Zhizhen'])
def test_exact_tennis_winner_offer_reaches_actual_catalog_floor_without_model_mutation(price, visible, selected):
    row, candidate = _fixture(price, selected=selected)
    before_row, before_candidate = deepcopy(row), candidate.to_dict()
    overlay = shared_price_overlays([candidate], [row], now=NOW)[candidate.candidate_id]
    assert overlay.observed_odds == price and overlay.below_floor is not visible
    assert overlay.observed_at == row['reference_quote']['points'][0]['observed_at']
    card = build_riskobet_card(candidate, overlay)
    assert bool(compose_riskobet_catalog([card]).cards) is visible
    assert row == before_row and candidate.to_dict() == before_candidate
    assert card.model_probability == candidate.model_probability
    assert card.evidence_code == candidate.stage.value


@pytest.mark.parametrize('field, value', [
    ('fixture_source', 'OTHER'), ('provider_event_id', '186198'),
    ('fixture_source', None), ('provider_event_id', None),
    ('scheduled_start', '2030-09-30T09:00:01+00:00'),
    ('scheduled_start', '2030-09-30T09:00:00'),
    ('scheduled_start', 'not-a-time'), ('market_key', 'TOTAL_OVER_2_5'),
    ('competitor_a', 'Other Player'), ('competitor_b', 'Other Player'),
    ('selected_competitor', 'Zhang Zhizhen'), ('quote_provider_event_id', 'different-odds-event'),
    ('sport', 'Basketball'), ('fixture_id', 186197), ('reference_quote', None),
])
def test_foreign_incomplete_or_mismatched_normal_row_never_supplies_a_tennis_quote(field, value):
    row, candidate = _fixture()
    assert not shared_price_overlays([candidate], [{**row, field: value}], now=NOW)


@pytest.mark.parametrize('change', [
    {'starts_at': NOW + timedelta(hours=2)},
    {'event_key': stable_event_key('tennis', 'ESPN', '186198')},
    {'event_label': 'Zhang Zhizhen vs Arthur Gea'},
    {'event_label': 'Other Player vs Zhang Zhizhen'},
    {'selection_label': 'Zhang Zhizhen'},
    {'selection_key': 'away', 'settlement_contract': 'riskobet-settlement-v1:tennis:match_winner:away'},
    {'market_key': 'over_2_5_sets', 'selection_key': 'over',
     'settlement_contract': 'riskobet-settlement-v1:tennis:over_2_5_sets:over'},
    {'market_key': 'plus_1_5_sets', 'settlement_contract': 'riskobet-settlement-v1:tennis:plus_1_5_sets:home'},
    {'settlement_contract': 'riskobet-settlement-v1:tennis:match_winner:home:retirement'},
])
def test_winner_quote_cannot_cross_event_order_side_market_or_settlement_contract(change):
    row, candidate = _fixture()
    assert not shared_price_overlays([replace(candidate, **change)], [row], now=NOW)


def test_stale_exact_quote_retains_original_clock_and_still_applies_existing_display_floor():
    row, candidate = _fixture(1.12, age=timedelta(hours=3))
    overlay = shared_price_overlays([candidate], [row], now=NOW)[candidate.candidate_id]
    assert overlay.status == 'STALE' and overlay.below_floor
    assert overlay.observed_at == (NOW-timedelta(hours=3)).isoformat()
    assert not compose_riskobet_catalog([build_riskobet_card(candidate, overlay)]).cards
    row, candidate = _fixture(age=timedelta(days=2))
    assert not shared_price_overlays([candidate], [row], now=NOW)


def test_conflicting_duplicate_and_expired_match_fail_unknown_not_convenient_price():
    low, candidate = _fixture(1.12)
    high, _ = _fixture(1.52)
    assert not shared_price_overlays([candidate], [low, high, low], now=NOW)
    assert not shared_price_overlays([candidate], [low], now=candidate.starts_at)
    assert not shared_price_overlays([candidate], [], now=NOW)
    card = build_riskobet_card(candidate)
    assert card.observed_odds is None and compose_riskobet_catalog([card]).cards


def test_load_reuses_stored_tennis_rows_without_fetching_or_changing_publication(tmp_path, monkeypatch):
    import requests
    def forbidden(*_args, **_kwargs):
        raise AssertionError('read-only quote reuse must not fetch providers')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    row, candidate = _fixture(1.12)
    path = tmp_path / 'wettfinder_latest.json'
    path.write_text(json.dumps({'model_candidates': [row]}), encoding='utf-8')
    before = path.read_bytes()
    overlays = load_shared_price_overlays((c for c in [candidate]), path=path, now=NOW)
    assert overlays[candidate.candidate_id].below_floor
    assert path.read_bytes() == before
    assert tuple(tmp_path.iterdir()) == (path,)
