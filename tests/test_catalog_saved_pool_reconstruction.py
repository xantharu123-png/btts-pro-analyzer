"""Saved producer candidates repair an old lossy view without rerunning models."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from ev_signal_sources import _minimum_odds, automated_wettfinder_forecasts
from market_consensus import MarketConsensus
from test_catalog_statistical_selection import ilves_rows
from test_daily3_selection import NOW
from test_ev_signal_sources import _automatic_document
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog


def saved_document():
    raw = ilves_rows(1.80)
    for item in raw:
        item['context_checked_at'] = NOW.isoformat()
        item['prediction_version'] = item['model_version']
        item['minimum_odds'] = _minimum_odds(item['probability'], item['probability_haircut'])
    # Old writer lost HOME. Only the lossy view received bookmaker quotes.
    ledger = [deepcopy(item) for item in raw if item['market_key'] not in {'RESULT_HOME', 'RESULT_AWAY'}]
    from wettfinder_automation import _apply_reference_quotes
    quotes = {item['candidate_id']: MarketConsensus.from_dict(item['reference_quote']) for item in ledger}
    _apply_reference_quotes(ledger, ledger, quotes, now=NOW)
    for item in ledger:
        item['status'] = 'MODEL_SELECTION'
    for item in raw:
        item.pop('reference_quote', None)
        item['reference_price_status'] = 'UNAVAILABLE'
    document = _automatic_document(ledger)
    document['generated_at'] = NOW.isoformat()
    document['football'].update(candidates=raw, discovery_model_version='test-model-v1')
    return document


def test_saved_complete_pool_restores_modal_direction_and_retains_exact_price_receipts(tmp_path, monkeypatch):
    document = saved_document()
    artifact = tmp_path / 'wettfinder.json'
    artifact.write_text(json.dumps(document), encoding='utf-8')
    before = artifact.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError('Reading saved model candidates must not contact a provider or write state')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    assert {signal.market_key for signal in forecasts} == {
        'RESULT_HOME', 'DC_1X', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
    home = next(signal for signal in forecasts if signal.market_key == 'RESULT_HOME')
    assert home.probability == .486390 and home.reference_quote is None
    assert home.modeled_at == NOW.isoformat()
    assert home.input_cutoff_at == (NOW-timedelta(minutes=1)).isoformat()
    for signal in forecasts:
        if signal.market_key != 'RESULT_HOME':
            assert signal.reference_quote is not None
            assert signal.reference_quote['fetched_at'] == NOW.isoformat()
    cards = [build_wettfinder_card(signal, signal.reference_quote, now=NOW) for signal in forecasts]
    public = compose_wettfinder_catalog(cards)
    assert {card.market_key for card in public.featured + public.additional} == {
        'DC_1X', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
    assert artifact.read_bytes() == before


@pytest.mark.parametrize('change', ['failed', 'wrong_day', 'missing_model', 'unverified_accounting',
    'foreign_source', 'foreign_model', 'foreign_ids', 'future_model', 'foreign_analysis',
    'malformed_conservative', 'overflow_rank', 'overflow_minimum'])
def test_invalid_raw_producer_state_never_replaces_valid_legacy_ledger(change, tmp_path):
    document = saved_document()
    state = document['football']
    if change == 'failed':
        state['status'] = 'failed'
    elif change == 'wrong_day':
        state['search_date'] = '2029-12-31'
    elif change == 'missing_model':
        state.pop('discovery_model_version')
    elif change == 'unverified_accounting':
        state['context_accounting_available'] = False
    else:
        for item in state['candidates']:
            if change == 'foreign_source':
                item['source'] = 'foreign'
            elif change == 'foreign_model':
                item['model_version'] = 'other'
            elif change == 'foreign_ids':
                item['home_id'] = True
            elif change == 'future_model':
                item['modeled_at'] = (NOW+timedelta(minutes=1)).isoformat()
            elif change == 'malformed_conservative':
                item['conservative_probability'] = .999
            elif change == 'overflow_rank':
                item['selection_rank'] = [10 ** 1000] * 6
            elif change == 'overflow_minimum':
                item['minimum_odds'] = 10 ** 1000
            else:
                item['analysis_evidence']['identity']['fixture_id'] = 999
    artifact = tmp_path / 'wettfinder.json'
    artifact.write_text(json.dumps(document), encoding='utf-8')
    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    # Legacy validation behavior is retained, not repaired by unrelated rows.
    if change == 'unverified_accounting':
        assert forecasts == []
    else:
        assert {signal.market_key for signal in forecasts} == {
            'DC_1X', 'DC_X2', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
