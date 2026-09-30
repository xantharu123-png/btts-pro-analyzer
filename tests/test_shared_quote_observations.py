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
    assert compose_riskobet_catalog([card]).cards == ()
    assert candidate.to_dict() == before
    assert not shared_price_overlays([replace(candidate, starts_at=candidate.starts_at+timedelta(days=1))], [row], now=NOW)
    assert not shared_price_overlays([candidate], [{**row,'fixture_id':888888}], now=NOW)


@pytest.mark.parametrize('sport', ['football','tennis','basketball','ice_hockey','esports'])
def test_riskobet_manual_quote_floor_applies_to_every_sport(monkeypatch,sport):
    bundle = _bundle('manual', sport=sport)
    view = _view(bundle)
    candidate = bundle[1]
    key = f'riskobet-quote-{ui._widget_suffix(candidate)}'
    fake = RecordingStreamlit(session_state={key: '1.12'})
    monkeypatch.setattr(ui,'st',fake)
    monkeypatch.setattr(ui,'load_riskobet_view',lambda *a: view)
    ui.render_riskobet()
    assert _rendered_candidate_ids(fake) == []
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


@pytest.mark.parametrize('price,visible', [(1.12, False), (1.199999999, False), (1.20, True)])
def test_active_15k_model_surface_obeys_bound_floor_before_slot_selection(monkeypatch, price, visible):
    import challenge_15k as challenge
    from test_challenge_15k import candidate
    item = candidate('123:BTTS_YES', 123, .75)
    now = datetime.now(tz=NOW.tzinfo)
    payload = _payload(now, values={'Book': str(price)}, provider_ids=True)
    payload['response'][0]['fixture'].update(id=item.fixture_id, date=item.kickoff)
    quotes = mc.parse_fixture_consensus(payload, [item], fetched_at=now)
    assert item.candidate_id in quotes
    fake, ledger = MagicMock(), Mock()
    fake.multiselect.return_value = []
    monkeypatch.setattr(challenge, 'st', fake)
    challenge._render_model_challenge(dict(challenge_model_candidates=[item],
        reference_quotes=mc.serialize_consensus_map(quotes)), ledger, {})
    assert fake.multiselect.called is visible
    assert fake.markdown.called is visible
    assert not ledger.mock_calls


def test_riskobet_page_reuses_bound_shared_prices_without_new_fetch(monkeypatch):
    bundle = _bundle('shared-floor')
    view = _view(bundle)
    candidate = view.candidates[0]
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, 'st', fake)
    monkeypatch.setattr(ui, 'load_riskobet_view', lambda *a: view)
    monkeypatch.setattr(ui, 'load_shared_price_overlays', lambda *a: {
        candidate.candidate_id: RiskBetPriceOverlay(candidate_id=candidate.candidate_id,
            status='AVAILABLE', observed_odds=1.12, below_floor=True)})
    ui.render_riskobet()
    assert not _rendered_candidate_ids(fake)


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


def _tennis_price_fixture(price=1.90, books=4):
    from wettfinder_automation import _signal_record
    from ev_signal_sources import TENNIS_POLICY_VERSION
    signal = _signal('tennis-gea', sport='Tennis', market='Match Winner',
                     selection='Sieg A', market_key='H2H')
    signal = replace(signal, candidate_id=signal.key, policy_version=TENNIS_POLICY_VERSION)
    row = _signal_record(signal)
    row['status'] = 'MODEL_SELECTION'
    event = dict(id='odds-gea', home_team='A', away_team='B',
                 commence_time=row['scheduled_start'], bookmakers=[
        dict(key=f'book-{i}', title=f'Book {i}', last_update=NOW.isoformat(), markets=[
            dict(key='h2h', outcomes=[dict(name='A', price=price), dict(name='B', price=2.10)])])
        for i in range(books)
    ])
    quote = mc.parse_h2h_event_consensus(event, [row], fetched_at=NOW)[row['candidate_id']]
    return signal, row, quote


@pytest.mark.parametrize('price', [1.12, 1.90])
def test_tennis_price_only_keeps_models_clocks_order_and_other_sports(tmp_path, price):
    from copy import deepcopy
    from wettfinder_automation import refresh_prices_only
    signal, row, quote = _tennis_price_fixture(price)
    other = dict(key='other', source='football_challenge', probability=.41,
                 reference_quote={'untouched': True}, status='MODEL_SELECTION')
    path = tmp_path/'tennis-prices.json'
    document = dict(generated_at=NOW.isoformat(), model_candidates=[other, row],
        candidates=[deepcopy(other), deepcopy(row)], football={'scanned_at':'original'},
        challenge_release_candidates=[{'untouched': True}], riskobet={'untouched': True},
        sources={'football':{'untouched':True}, 'tennis':{'modeled_at':'original'}})
    path.write_text(json.dumps(document), encoding='utf-8')
    calls = []
    def loader(rows):
        calls.append(rows)
        return {quote.candidate_id:quote}, []
    summary = refresh_prices_only(state_path=path, now=NOW, quote_loader=loader, quote_sport='tennis')
    after = json.loads(path.read_text(encoding='utf-8'))
    assert summary['sport'] == 'tennis' and summary['checked'] == summary['quotes'] == 1
    assert len(calls) == 1 and calls[0][0]['candidate_id'] == row['candidate_id']
    for field in ('generated_at','football','riskobet','challenge_release_candidates'):
        assert after[field] == document[field]
    assert after['model_candidates'][0] == other
    assert after['sources']['football'] == document['sources']['football']
    assert after['sources']['tennis']['modeled_at'] == 'original'
    for field, value in row.items():
        if not field.startswith(('reference_', 'quote_')):
            assert after['model_candidates'][1][field] == value
    assert after['model_candidates'][1]['reference_quote']['fetched_at'] == NOW.isoformat()
    assert after['candidates'] == [other]  # Never create a money release from a display refresh.
    assert after['bookmaker_data_used'] is True
    assert mc.quote_below_publication_floor(quote, candidate=row, now=NOW) is (price < 1.20)
    assert build_wettfinder_card(signal, quote, now=NOW).quote_floor_excluded is (price < 1.20)


@pytest.mark.parametrize('problem', ['none', 'mismatch', 'stale'])
def test_tennis_cached_quote_preserves_original_clock_and_exact_binding(tmp_path, problem):
    from copy import deepcopy
    from wettfinder_automation import _apply_reference_quotes, _tennis_price_check_candidates
    _, row, quote = _tennis_price_fixture()
    row['reference_quote'] = quote.to_dict()
    if problem == 'mismatch':
        row['scheduled_start'] = (NOW+timedelta(hours=4)).isoformat()
    current = NOW+timedelta(minutes=10 if problem != 'stale' else 50)
    previous = deepcopy(row)
    selected = _tennis_price_check_candidates([row], now=current, target_date=current.date(),
        previous_checks={row['key']:current.isoformat()})
    assert selected == []
    _apply_reference_quotes([row], selected, {}, now=current, previous_rows=[previous],
                            price_evaluated_at=current)
    after = row
    assert after['probability'] == row['probability']
    if problem == 'mismatch':
        assert 'reference_quote' not in after and after['reference_price_status'] == 'UNAVAILABLE'
    else:
        assert after['reference_quote']['fetched_at'] == NOW.isoformat()
        assert after['reference_price_status'] == ('PLAYABLE' if problem == 'none' else 'STALE')


def test_tennis_price_only_aborts_on_snapshot_change_and_never_runs_a_scan(tmp_path, monkeypatch):
    import wettfinder_automation as automation
    _, row, _ = _tennis_price_fixture()
    path = tmp_path/'racing-tennis.json'
    path.write_text(json.dumps(dict(model_candidates=[row])), encoding='utf-8')
    monkeypatch.setattr(automation, 'run_wettfinder', lambda **_kwargs: pytest.fail('model scan'))
    def racing_loader(_rows):
        path.write_text('{"newer":true}', encoding='utf-8')
        return {}, []
    with pytest.raises(RuntimeError, match='snapshot changed'):
        automation.refresh_prices_only(state_path=path, now=NOW, quote_loader=racing_loader, quote_sport='tennis')
    assert json.loads(path.read_text()) == {'newer':True}


@pytest.mark.parametrize('outcome', ['thin', 'no_coverage', 'failure'])
def test_tennis_price_only_keeps_coverage_separate_from_safe_provider_failures(tmp_path, outcome):
    from wettfinder_automation import refresh_prices_only
    _, row, quote = _tennis_price_fixture(books=1)
    path = tmp_path/'coverage.json'
    path.write_text(json.dumps(dict(model_candidates=[row], candidates=[])), encoding='utf-8')
    def loader(_rows):
        if outcome == 'failure':
            raise RuntimeError('private-provider-credential')
        if outcome == 'no_coverage':
            return {}, ['The Odds API meldet keine aktive Tennis-Konkurrenz']
        return {quote.candidate_id:quote}, []
    summary = refresh_prices_only(state_path=path, now=NOW, quote_loader=loader, quote_sport='tennis')
    after = json.loads(path.read_text(encoding='utf-8'))
    assert summary['operational_errors'] == int(outcome == 'failure')
    assert after['model_candidates'][0]['probability'] == row['probability']
    assert after['model_candidates'][0]['reference_price_status'] == ('THIN' if outcome == 'thin' else 'UNAVAILABLE')
    assert 'private-provider-credential' not in path.read_text(encoding='utf-8')
    assert after['candidates'] == []


def test_tennis_price_only_cli_dispatches_without_full_model_run(monkeypatch, capsys):
    import wettfinder_automation as automation
    calls = []
    monkeypatch.setattr(automation, 'run_wettfinder', lambda **_kwargs: pytest.fail('model scan'))
    monkeypatch.setattr(automation, 'refresh_prices_only', lambda **kwargs:
        calls.append(kwargs) or {'errors':1, 'operational_errors':0})
    assert automation.main(['--quotes-only', '--quote-sport', 'tennis', '--state-path', 'fixture.json']) == 0
    assert calls == [{'state_path':'fixture.json', 'quote_sport':'tennis'}]
    assert 'operational_errors' in capsys.readouterr().out


def test_tennis_quote_sport_requires_quote_only_mode(monkeypatch):
    import wettfinder_automation as automation
    monkeypatch.setattr(automation, 'run_wettfinder', lambda **_kwargs: pytest.fail('model scan'))
    with pytest.raises(SystemExit) as exc:
        automation.main(['--quote-sport', 'tennis'])
    assert exc.value.code == 2


@pytest.mark.parametrize('busy_check', [1, 2])
def test_tennis_canonical_price_only_requires_idle_before_fetch_and_publish(tmp_path, monkeypatch, busy_check):
    import subprocess
    import wettfinder_automation as automation
    _, row, quote = _tennis_price_fixture()
    path = tmp_path/'canonical.json'
    path.write_text(json.dumps(dict(model_candidates=[row])), encoding='utf-8')
    original = path.read_bytes()
    monkeypatch.setattr(automation, 'STATE_PATH', path)
    checks, fetches = [], []
    def service_state(*_args, **_kwargs):
        checks.append(True)
        return SimpleNamespace(stdout='active' if len(checks) == busy_check else 'inactive')
    monkeypatch.setattr(subprocess, 'run', service_state)
    def loader(_rows):
        fetches.append(True)
        return {quote.candidate_id:quote}, []
    with pytest.raises(RuntimeError, match='must be idle'):
        automation.refresh_prices_only(state_path=path, now=NOW, quote_loader=loader, quote_sport='tennis')
    assert path.read_bytes() == original
    assert len(checks) == busy_check and len(fetches) == busy_check-1


@pytest.mark.parametrize('order', [('tennis','football'), ('football','tennis')])
def test_sequential_price_refresh_uses_independent_row_clocks_in_real_reader(tmp_path, order):
    from copy import deepcopy
    from ev_signal_sources import automated_wettfinder_snapshot
    from wettfinder_automation import refresh_prices_only
    from test_ev_signal_sources import _automatic_document, _playable_automatic_candidate, _model_overlay
    _, tennis, tennis_quote = _tennis_price_fixture()
    generated = NOW-timedelta(hours=1)
    tennis.update(modeled_at=generated.isoformat(), input_cutoff_at=generated.isoformat())
    strict = _playable_automatic_candidate(generated_at=generated.isoformat())
    football = _model_overlay(strict)
    document = _automatic_document([football, tennis], candidates=[strict])
    document['generated_at'] = generated.isoformat()
    document['sources']['football'].update(challenge_release_candidate_count=1, published_recommendation_count=1)
    original = deepcopy(document)
    path = tmp_path/'real-reader.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    assert automated_wettfinder_snapshot(path, now=NOW).status is not None
    for index, sport in enumerate(order):
        current = NOW+timedelta(minutes=5*index)
        def loader(rows):
            if sport == 'tennis':
                quote = replace(tennis_quote, fetched_at=current.isoformat(), quoted_at=current.isoformat(),
                    points=tuple(replace(p, observed_at=current.isoformat()) for p in tennis_quote.points))
            else:
                fresh = _playable_automatic_candidate(generated_at=current.isoformat())
                quote = mc.MarketConsensus.from_dict(fresh['reference_quote'])
            return {quote.candidate_id:quote}, []
        refresh_prices_only(state_path=path, now=current, quote_loader=loader, quote_sport=sport)
        after = json.loads(path.read_text(encoding='utf-8'))
        snapshot = automated_wettfinder_snapshot(path, now=current)
        assert snapshot.status is not None and len(snapshot.forecasts) == 2
        assert after['generated_at'] == original['generated_at']
        assert [r['key'] for r in after['model_candidates']] == [r['key'] for r in original['model_candidates']]
        for before, row in zip(original['model_candidates'], after['model_candidates']):
            for field, value in before.items():
                if not field.startswith(('reference_', 'quote_')):
                    assert row[field] == value
        if sport == 'tennis' and index == 0:
            assert after['candidates'] == original['candidates']
            assert after['challenge_release_candidates'] == original['challenge_release_candidates']
            assert after['sources']['football'] == original['sources']['football']
    assert after['candidates'] == after['challenge_release_candidates'] == []
    assert after['sources']['football']['challenge_release_candidate_count'] == 0
    assert after['sources']['football']['published_recommendation_count'] == 0
    stamps = {r['source']:r['reference_price_evaluated_at'] for r in after['model_candidates']}
    assert stamps[{'football':'football_challenge','tennis':'tennis_shadow'}[order[0]]] == NOW.isoformat()
    assert stamps[{'football':'football_challenge','tennis':'tennis_shadow'}[order[1]]] == (NOW+timedelta(minutes=5)).isoformat()


def test_explicit_tennis_price_retry_ignores_automatic_gap(tmp_path):
    from wettfinder_automation import refresh_prices_only
    _, row, quote = _tennis_price_fixture()
    path = tmp_path/'explicit-retry.json'
    path.write_text(json.dumps(dict(model_candidates=[row], candidates=[],
        price_check_attempts={row['key']:NOW.isoformat()})), encoding='utf-8')
    calls = []
    def loader(rows):
        calls.append(rows)
        return {quote.candidate_id:quote}, []
    summary = refresh_prices_only(state_path=path, now=NOW, quote_loader=loader, quote_sport='tennis')
    assert summary['checked'] == summary['quotes'] == 1 and len(calls) == 1


@pytest.mark.parametrize('bad_stamp', ['future', 'before_publication', 'naive', 'invalid'])
def test_actual_reader_rejects_invalid_price_evaluation_clock(tmp_path, bad_stamp):
    from ev_signal_sources import automated_wettfinder_snapshot
    from wettfinder_automation import _apply_reference_quotes
    from test_ev_signal_sources import _automatic_document
    _, row, quote = _tennis_price_fixture()
    generated = NOW-timedelta(hours=1)
    document = _automatic_document([row])
    document['generated_at'] = generated.isoformat()
    _apply_reference_quotes([row], [dict(row)], {quote.candidate_id:quote}, now=NOW, price_evaluated_at=NOW)
    row['reference_price_evaluated_at'] = {
        'future':(NOW+timedelta(seconds=1)).isoformat(),
        'before_publication':(generated-timedelta(seconds=1)).isoformat(),
        'naive':NOW.replace(tzinfo=None).isoformat(), 'invalid':'not-a-clock'}[bad_stamp]
    path = tmp_path/'bad-price-clock.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    assert automated_wettfinder_snapshot(path, now=NOW).status is None


def test_real_reader_keeps_model_when_cached_price_genuinely_expires(tmp_path):
    from copy import deepcopy
    from ev_signal_sources import automated_wettfinder_snapshot
    from wettfinder_automation import _apply_reference_quotes
    from test_ev_signal_sources import _automatic_document
    _, row, quote = _tennis_price_fixture()
    document = _automatic_document([row])
    document['generated_at'] = (NOW-timedelta(hours=1)).isoformat()
    _apply_reference_quotes([row], [dict(row)], {quote.candidate_id:quote}, now=NOW, price_evaluated_at=NOW)
    current = NOW+timedelta(minutes=50)
    _apply_reference_quotes([row], [], {}, now=current, previous_rows=[deepcopy(row)], price_evaluated_at=current)
    assert row['reference_price_status'] == 'STALE'
    assert row['reference_quote']['fetched_at'] == NOW.isoformat()
    assert row['reference_price_evaluated_at'] == current.isoformat()
    assert not any(field.startswith('reference_quote_') for field in row)
    path = tmp_path/'expired-price.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    snapshot = automated_wettfinder_snapshot(path, now=current)
    assert snapshot.status is not None and len(snapshot.forecasts) == 1
    # A normal publication reevaluates at its own generated clock, never
    # blindly carries the earlier display-only decision clock forward.
    _apply_reference_quotes([row], [], {}, now=current, previous_rows=[deepcopy(row)])
    assert 'reference_price_evaluated_at' not in row
