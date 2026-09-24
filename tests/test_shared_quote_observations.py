from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
import json

import pytest

import market_consensus as mc
import riskobet_ui as ui
from riskobet_domain import stable_event_key
from riskobet_prices import football_market, shared_price_overlays
from riskobet_surface import RiskBetPriceOverlay, build_riskobet_card, compose_riskobet_catalog
from test_market_consensus import _payload, _candidate
from test_wettfinder_surface import NOW, _signal, _quote
from test_riskobet_ui import _bundle, _view, RecordingStreamlit, _rendered_candidate_ids
from wettfinder_surface import build_wettfinder_card, render_top_card_html, wettfinder_quote_binding_candidate, wettfinder_recommendation_candidate
from bet_finder_ui import evaluate_reference_price
from multi_sport_recommendations import evaluate_candidate_price
from unittest.mock import MagicMock, Mock


def test_import_keeps_provider_last_observation_but_never_releases_it(monkeypatch):
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: _payload(NOW-timedelta(hours=3), provider_ids=True))
    monkeypatch.setattr(mc, 'api_football_get', lambda *a, **k: response)
    quotes, errors = mc.fetch_football_consensus('test', [_candidate()], now=NOW)
    quote = quotes[_candidate()['candidate_id']]
    assert not errors
    assert quote.quoted_at == (NOW-timedelta(hours=3)).isoformat()
    assert mc.observed_consensus(quote, candidate=_candidate(), now=NOW) is not None
    assert mc.wettfinder_consensus(quote, now=NOW) is None
    assert not quote.is_fresh(NOW)
    assert mc.reference_price_status(quote, 1.2, now=NOW).code == 'STALE'


def test_stale_price_is_visible_with_original_clock_not_current_or_executable():
    signal = _signal()
    old = NOW - timedelta(hours=3)
    quote = mc.wettfinder_consensus(_quote(signal), now=NOW)
    quote = replace(quote, quoted_at=old.isoformat(), points=tuple(replace(p, observed_at=old.isoformat()) for p in quote.points))
    binding = wettfinder_quote_binding_candidate(signal)
    evaluation = evaluate_reference_price(wettfinder_recommendation_candidate(signal), quote, bankroll=100, reference_binding_candidate=binding, now=NOW)
    assert evaluation.status.code == 'STALE'
    assert evaluation.decision is None
    card = build_wettfinder_card(signal, quote, now=NOW, price_evaluation=evaluation)
    markup = render_top_card_html(card)
    assert card.observed_odds == quote.best_odds
    assert 'Letzte Quote' in markup and 'Stand:' in markup
    assert '>Aktuell<' not in markup
    assert not card.confirmed_tip


def test_last_known_low_quote_filters_proposal_without_becoming_executable():
    signal = _signal()
    quote = _quote(signal, (1.12,)*3, fetched_at=NOW-timedelta(hours=3))
    assert mc.quote_below_publication_floor(quote, candidate=wettfinder_quote_binding_candidate(signal), now=NOW)
    evaluation = evaluate_reference_price(wettfinder_recommendation_candidate(signal), quote, bankroll=100,
        reference_binding_candidate=wettfinder_quote_binding_candidate(signal), now=NOW)
    assert evaluation.status.code == 'STALE' and evaluation.decision is None
    assert build_wettfinder_card(signal, quote, now=NOW, price_evaluation=evaluation).quote_floor_excluded


@pytest.mark.parametrize('problem', ['foreign', 'future', 'ancient', 'unidentified'])
def test_display_quote_never_recovers_unbound_or_invalid_prices(problem):
    signal = _signal()
    quote = _quote(signal)
    if problem == 'foreign':
        quote = replace(quote, fixture_id=99999)
    elif problem == 'unidentified':
        quote = replace(quote, points=tuple(replace(p, bookmaker_id=None) for p in quote.points))
    else:
        stamp = NOW + timedelta(hours=2) if problem == 'future' else NOW-timedelta(days=2)
        quote = replace(quote, quoted_at=stamp.isoformat(), points=tuple(replace(p, observed_at=stamp.isoformat()) for p in quote.points))
    assert mc.observed_consensus(quote, candidate=wettfinder_quote_binding_candidate(signal), now=NOW) is None


@pytest.mark.parametrize('market,side,expected', [
    ('result_90_minutes','home','RESULT_HOME'), ('result_90_minutes','away','RESULT_AWAY'),
    ('draw_90_minutes','draw','RESULT_DRAW'), ('double_chance_90_minutes','home_or_draw','DC_1X'),
    ('double_chance_90_minutes','away_or_draw','DC_X2'),
    ('underdog_team_over_0_5_90_minutes','home','HOME_OVER_0_5'),
    ('underdog_team_over_1_5_90_minutes','away','AWAY_OVER_1_5'),
])
def test_riskobet_uses_exact_settlement_market(market, side, expected):
    c = SimpleNamespace(sport='football', market_key=market, selection_key=side,
        settlement_contract=f'riskobet-settlement-v1:football:{market}:{side}')
    assert football_market(c) == expected
    c.settlement_contract += ':extra_time'
    assert football_market(c) is None


def risk_price_fixture(price=1.12):
    signal = _signal()
    quote = replace(_quote(signal, (price,)*3), bet_name='Double Chance', value_name='Home/Draw')
    row = {**wettfinder_quote_binding_candidate(signal), 'reference_quote': quote.to_dict()}
    _, template = _bundle('shared')
    candidate = replace(template, event_key=stable_event_key('football','api-football',str(signal.fixture_id)),
        starts_at=NOW+timedelta(hours=5), market_key='double_chance_90_minutes', selection_key='home_or_draw',
        settlement_contract='riskobet-settlement-v1:football:double_chance_90_minutes:home_or_draw')
    candidate = replace(candidate, starts_at=datetime.fromisoformat(signal.scheduled_start))
    return row, candidate


def test_riskobet_shared_native_quote_and_floor_are_reused_without_model_mutation():
    row,candidate = risk_price_fixture()
    before = candidate.to_dict()
    overlays = shared_price_overlays([candidate], [row], now=NOW)
    overlay = overlays[candidate.candidate_id]
    assert overlay.observed_odds == 1.12 and overlay.below_floor
    card = build_riskobet_card(candidate, overlay)
    assert compose_riskobet_catalog([card]).cards == (card,)
    assert candidate.to_dict() == before
    assert not shared_price_overlays([replace(candidate, starts_at=candidate.starts_at+timedelta(days=1))], [row], now=NOW)
    assert not shared_price_overlays([candidate], [{**row,'fixture_id':888888}], now=NOW)


@pytest.mark.parametrize('sport', ['football','tennis','basketball','ice_hockey','esports'])
def test_riskobet_manual_quote_does_not_filter_any_sport(monkeypatch,sport):
    bundle = _bundle('manual', sport=sport)
    view = _view(bundle)
    candidate = bundle[1]
    key = f'riskobet-quote-{ui._widget_suffix(candidate)}'
    fake = RecordingStreamlit(session_state={key: '1.12'})
    monkeypatch.setattr(ui,'st',fake)
    monkeypatch.setattr(ui,'load_riskobet_view',lambda *a: view)
    ui.render_riskobet()
    assert _rendered_candidate_ids(fake) == [candidate.candidate_id]
    assert ('Eigene Dezimalquote',key) not in fake.text_inputs
    fake.session_state[key] = '1.20'
    ui.render_riskobet()
    assert set(_rendered_candidate_ids(fake)) == {candidate.candidate_id}


@pytest.mark.parametrize('sport', ['Fussball','Tennis','Basketball','Eishockey','E-Sport'])
@pytest.mark.parametrize('price', [1.12, 1.19999999999])
def test_shared_live_and_prematch_execution_floor_is_strict_for_every_sport(sport,price):
    base = wettfinder_recommendation_candidate(_signal())
    candidate = replace(base,sport=sport,model_probability=99.0,risk_adjusted_probability=98.0,
        probability_haircut=1.0,minimum_odds=1.20,evidence_stage='RELEASED',release_pending=False)
    decision = evaluate_candidate_price(candidate,price,bankroll=100,quote_confirmed=True)
    assert decision.status == 'NO_BET'
    assert decision.stake_amount == 0


def test_15k_removes_low_offer_before_rendering_and_ticket_selection(monkeypatch):
    import challenge_15k as challenge
    from test_challenge_15k import candidate
    item = candidate('123:BTTS_YES',123,.75)
    now = datetime.now(tz=NOW.tzinfo)
    payload = _payload(now, values={'Book': '1.12'}, provider_ids=True)
    payload['response'][0]['fixture']['id'] = item.fixture_id
    payload['response'][0]['fixture']['date'] = item.kickoff
    quotes = mc.parse_fixture_consensus(payload,[item],fetched_at=now)
    fake = MagicMock()
    ticket = Mock(side_effect=AssertionError('filtered proposal must not reach ticket selection'))
    monkeypatch.setattr(challenge,'st',fake)
    monkeypatch.setattr(challenge,'_automatic_challenge_ticket',ticket)
    ledger = Mock()
    challenge._render_price_check(dict(shortlist=[item],reference_quotes=mc.serialize_consensus_map(quotes)),ledger,{})
    fake.info.assert_called_once_with('Aktuell keine passende 15K-Auswahl.')
    ticket.assert_not_called()
    assert not ledger.mock_calls


@pytest.mark.parametrize('sport', ['Fussball','Tennis','Basketball','Eishockey','E-Sport'])
def test_shared_manual_live_surface_keeps_only_correction_controls_below_floor(monkeypatch,sport):
    import bet_finder_ui as common
    fake = MagicMock()
    fake.session_state = {'bet_odds_low': '1,12','bet_confirmed_low':True}
    monkeypatch.setattr(common,'st',fake)
    correction = Mock(return_value=None)
    monkeypatch.setattr(common,'_render_manual_check',correction)
    c = replace(wettfinder_recommendation_candidate(_signal()),sport=sport)
    assert common.render_price_decision(c,key='low',allow_manual_check=True) is None
    correction.assert_called_once()
    fake.subheader.assert_not_called()
    fake.metric.assert_not_called()


@pytest.mark.parametrize('status', ['PRICE_REQUIRED', 'MODEL_SELECTION'])
def test_price_only_refresh_preserves_model_and_discovery_clocks(tmp_path,status):
    from wettfinder_automation import refresh_prices_only, _signal_record
    s = _signal()
    row = {**_signal_record(s), **wettfinder_quote_binding_candidate(s)}
    row['status'] = status
    path = tmp_path/'prices.json'
    document = dict(generated_at=NOW.isoformat(),model_candidates=[row],candidates=[dict(row)],sources={})
    path.write_text(json.dumps(document),encoding='utf-8')
    q = mc.wettfinder_consensus(_quote(s),now=NOW)
    calls=[]
    def loader(rows):
        calls.append(rows)
        return {q.candidate_id:q},[]
    summary = refresh_prices_only(state_path=path, now=NOW, quote_loader=loader)
    after = json.loads(path.read_text(encoding='utf-8'))
    assert summary['fixtures'] == 1 and summary['quotes'] == 1 and len(calls) == 1
    assert after['generated_at'] == document['generated_at']
    for field,value in row.items():
        if not field.startswith(('reference_', 'quote_')):
            assert after['model_candidates'][0][field] == value
    assert after['model_candidates'][0]['reference_quote']['best_odds'] == 1.84
    assert after['candidates'] == []  # No new money release from a quote-only update.


def test_price_refresh_aborts_if_model_snapshot_changed_during_fetch(tmp_path):
    from wettfinder_automation import refresh_prices_only, _signal_record
    path = tmp_path/'prices.json'
    path.write_text(json.dumps(dict(model_candidates=[_signal_record(_signal())])),encoding='utf-8')
    def racing_loader(rows):
        path.write_text('{"newer":true}',encoding='utf-8')
        return {},[]
    with pytest.raises(RuntimeError,match='snapshot changed'):
        refresh_prices_only(state_path=path, now=NOW, quote_loader=racing_loader)
    assert json.loads(path.read_text()) == {'newer':True}
