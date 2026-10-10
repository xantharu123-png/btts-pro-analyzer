from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

import team_sport_prices as prices
from market_consensus import (MarketConsensus, quote_matches_candidate,
    observed_consensus, quote_below_publication_floor, wettfinder_consensus,
    wettfinder_reference_price_status, reference_price_status)

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def row(sport='basketball', side='home', **changes):
    result = dict(candidate_id='candidate-'+sport+'-'+side, key='candidate-'+sport+'-'+side,
        sport=sport, fixture_source='ESPN' if sport == 'basketball' else 'NHL',
        provider_event_id='native-1', scheduled_start=(NOW+timedelta(hours=6)).isoformat(),
        competitor_a='Team 1', competitor_b='Team 8', selected_competitor='Team 1' if side == 'home' else 'Team 8',
        market_key='H2H', selection='Team 1' if side == 'home' else 'Team 8', competition='NBA' if sport == 'basketball' else 'NHL')
    result.update(changes)
    return result


def game(sport='basketball'):
    r = row(sport)
    return dict(id=81, date=r['scheduled_start'], league={'name': r['competition']},
        status={'short': 'NS'}, teams={'home': {'name': 'Team 1'}, 'away': {'name': 'Team 8'}})


def odds(g=None, home='1.75', away='2.30'):
    return [{'game': g or game(), 'bookmakers': [
        {'id': index, 'name': 'Book '+str(index), 'bets': [
            {'id': 2, 'name': 'Home/Away', 'values': [{'value': 'Home', 'odd': home}, {'value': 'Away', 'odd': away}]}]}
        for index in (1, 2, 3)]}]


@pytest.mark.parametrize('sport', ['basketball', 'ice_hockey'])
@pytest.mark.parametrize('side', ['home', 'away'])
def test_native_full_game_price_roundtrips_without_execution(sport, side):
    candidate, native = row(sport, side), game(sport)
    quote = prices.parse_game_quotes(odds(native), [candidate], native, fetched_at=NOW)[candidate['candidate_id']]
    assert quote_matches_candidate(quote, candidate)
    assert quote.best_odds == (1.75 if side == 'home' else 2.3)
    assert MarketConsensus.from_dict(quote.to_dict()) == quote
    assert observed_consensus(quote, candidate=candidate, now=NOW) == quote
    assert not quote.is_fresh(NOW)
    assert not quote.is_wettfinder_fresh(NOW)
    assert wettfinder_consensus(quote, now=NOW) is None
    assert reference_price_status(quote, 1.3, now=NOW).usable_odds is None
    status = wettfinder_reference_price_status(quote, 1.3, candidate=candidate, now=NOW)
    assert status.code == 'OBSERVED' and status.usable_odds is None
    at_start = NOW + timedelta(hours=6)
    assert observed_consensus(quote, candidate=candidate, now=at_start) is None
    assert wettfinder_reference_price_status(quote, 1.3, candidate=candidate, now=at_start).code == 'UNAVAILABLE'


@pytest.mark.parametrize('field,value', [
    ('fixture_source','another-source'), ('provider_event_id','another-game'),
    ('scheduled_start',(NOW+timedelta(hours=7)).isoformat()),
    ('competitor_a','Other Team'), ('selected_competitor','Team 8'),
    ('market_key','REGULATION_WINNER'), ('sport','tennis'), ('candidate_id','other'),
])
def test_quote_cannot_move_to_another_origin_or_selection(field, value):
    r = row(); q = prices.parse_game_quotes(odds(),[r],game(),fetched_at=NOW)[r['candidate_id']]
    wrong = dict(r, **{field: value})
    assert not quote_matches_candidate(q, wrong)
    assert observed_consensus(q,candidate=wrong,now=NOW) is None


@pytest.mark.parametrize('mutation', ['wrong_game','wrong_start','reverse','threeway','period','draw','duplicate','bad_opponent','finished'])
def test_parser_rejects_ambiguous_or_wrong_market(mutation):
    native, payload, candidate = game(), odds(), row()
    if mutation=='wrong_game': payload[0]['game']['id']=9
    elif mutation=='wrong_start': candidate['scheduled_start']=(NOW+timedelta(hours=7)).isoformat()
    elif mutation=='reverse': candidate.update(competitor_a='Team 8',competitor_b='Team 1')
    elif mutation=='finished': native['status']['short']='FT';payload[0]['game']=native
    else:
        for b in payload[0]['bookmakers']:
            m=b['bets'][0]
            if mutation=='threeway': m['id']=1;m['name']='3Way Result'
            elif mutation=='period': m['name']='Home/Away 1st Period'
            elif mutation=='draw': m['values'].append({'value':'Draw','odd':'5'})
            elif mutation=='duplicate': other=deepcopy(m);other['values'][0]['odd']='4';b['bets'].append(other)
            elif mutation=='bad_opponent': m['values'][1]['odd']='nan'
    assert prices.parse_game_quotes(payload,[candidate],native,fetched_at=NOW)=={}


@pytest.mark.parametrize('price,excluded',[('1.19',True),('1.1999999999',True),('1.20',False),('2.1',False)])
def test_observation_floor_exact_unrounded(price,excluded):
    r=row();q=prices.parse_game_quotes(odds(home=price),[r],game(),fetched_at=NOW)[r['candidate_id']]
    assert quote_below_publication_floor(q,candidate=r,now=NOW) is excluded
    assert not quote_below_publication_floor(q,candidate=r,now=NOW+timedelta(days=2))


class Governor:
    def __init__(self): self.calls=[];self.completed=[]
    def reserve(self,**kwargs): self.calls.append(kwargs);return len(self.calls)
    def complete(self,*args,**kwargs): self.completed.append((args,kwargs))


def test_refresh_is_shared_bounded_and_survives_model_revision(tmp_path):
    path=tmp_path/'quotes.json';calls=[];governor=Governor()
    def get(url,**kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(status_code=200,headers={},json=lambda:{'errors':[], 'response':[game()] if url.endswith('/games') else odds()})
    rows=[row(side=side) for side in ('home','away')]
    summary=prices.refresh_team_sport_prices(rows,api_key='test',now=NOW,path=path,governor=governor,get=get)
    assert summary['quotes']==2 and summary['checked']==1
    assert len(calls)==2 and len(governor.completed)==2
    assert all(c['provider']=='api-sports-basketball' for c in governor.calls)
    revised=dict(rows[0],candidate_id='new-model',key='new-model')
    quote=prices.load_cached_quote(revised,now=NOW,path=path)
    assert quote.candidate_id=='new-model' and quote.best_odds==1.75
    prices.refresh_team_sport_prices([revised,rows[1]],api_key='test',now=NOW+timedelta(minutes=30),path=path,governor=governor,get=get)
    assert len(calls)==2
    assert prices.load_cached_quote(revised,now=NOW+timedelta(hours=6),path=path) is None
    assert path.stat().st_size<10000
    assert prices.attach_cached_team_prices([revised],now=NOW,path=path)[0]['reference_quote']['best_odds']==1.75


def test_cached_quote_does_not_survive_corrupt_binding_or_provider(tmp_path):
    path=tmp_path/'quotes.json';r=row();q=prices.parse_game_quotes(odds(),[r],game(),fetched_at=NOW)[r['candidate_id']]
    key=prices._key(r)
    doc={'schema':1,'attempts':{},'quotes':{key:{'binding':list(prices._binding(r)),'quote':replace(q,candidate_id=key).to_dict()}}}
    for field in ('origin_event_id','origin_provider','event_home'):
        bad=deepcopy(doc);bad['quotes'][key]['quote'][field]='other'
        assert prices.load_cached_quote(r,now=NOW,document=bad) is None


def test_nhl_abbreviations_resolved_only_by_exact_native_event():
    r=row('ice_hockey',competitor_a='NJD',competitor_b='NYI',selected_competitor='NJD')
    entry={'id':'native-1','startTimeUTC':r['scheduled_start'],
        'homeTeam':{'abbrev':'NJD','placeName':{'default':'New Jersey'},'commonName':{'default':'Devils'}},
        'awayTeam':{'abbrev':'NYI','placeName':{'default':'New York'},'commonName':{'default':'Islanders'}}}
    payload={'gameWeek':[{'games':[entry]}]}
    assert prices._nhl_names(r,payload)==('New Jersey Devils','New York Islanders')
    assert prices._nhl_names(dict(r,provider_event_id='other'),payload) is None
    payload['gameWeek'][0]['games'].append(entry)
    assert prices._nhl_names(r,payload) is None


def test_no_requests_without_supported_models(tmp_path):
    def unexpected(*args,**kwargs): raise AssertionError('request')
    assert prices.refresh_team_sport_prices([row('tennis')],api_key='test',now=NOW,path=tmp_path/'x',get=unexpected)['status']=='no_events'
    assert prices.refresh_team_sport_prices([row()],api_key='',now=NOW,path=tmp_path/'x',get=unexpected)['status']=='missing_key'


def test_cache_writer_lock_rejects_parallel_work(tmp_path):
    path=tmp_path/'quotes.json'
    with prices._writer_lock(path):
        result=prices.refresh_team_sport_prices([row()],api_key='test',now=NOW,path=path)
    assert result['status']=='unavailable'


def test_native_budget_protects_free_daily_quota_and_records_failures(tmp_path):
    from api_budget import APIBudgetGovernor, APIBudgetExceeded
    governor=APIBudgetGovernor(tmp_path/'budget.db',daily_limit=20,
        critical_floor=1,recommendation_reserve=2,background_reserve=3)
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=200,headers={'x-ratelimit-requests-remaining':'3',
            'x-ratelimit-requests-limit':'20'},json=lambda:{'errors':[], 'response':[]})
    assert prices._json_get('basketball','games',{'date':'2026-09-05'},'secret',governor=governor,get=get)==[]
    with pytest.raises(APIBudgetExceeded):
        prices._json_get('basketball','games',{'date':'2026-09-05'},'secret',governor=governor,get=get)
    assert len(calls)==1


def test_request_failure_does_not_log_secret_or_repeat_each_ui_refresh(tmp_path):
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        raise RuntimeError('https://example.test?apiKey=secret')
    path=tmp_path/'prices.json'
    summary=prices.refresh_team_sport_prices([row()],api_key='secret',now=NOW,path=path,governor=Governor(),get=get)
    assert summary['status']=='partial' and 'secret' not in path.read_text(encoding='utf-8')
    prices.refresh_team_sport_prices([row()],api_key='secret',now=NOW+timedelta(minutes=30),path=path,governor=Governor(),get=get)
    assert len(calls)==1


def test_forecast_consumer_reuses_exact_cached_price_without_network(tmp_path,monkeypatch):
    import ev_signal_sources as sources
    from test_team_sport_forecasts import _signal_and_input
    _,r=_signal_and_input()
    q=prices.parse_game_quotes(odds(),[r],game(),fetched_at=NOW)[r['candidate_id']]
    key=prices._key(r)
    doc={'schema':1,'attempts':{},'quotes':{key:{'binding':list(prices._binding(r)), 'quote':replace(q,candidate_id=key).to_dict()}}}
    (tmp_path/'team_sport_quotes.json').write_text(json.dumps(doc),encoding='utf-8')
    rows=sources.automated_wettfinder_forecasts(tmp_path/'wettfinder_latest.json',now=NOW,
        _loaded=({'model_candidates':[r]},NOW,[]))
    assert len(rows)==1 and rows[0].reference_quote['best_odds'] == q.best_odds
    assert rows[0].probability==r['probability']
    assert rows[0].modeled_at==r['modeled_at']


def test_real_model_card_and_riskobet_reuse_same_observation(tmp_path):
    from test_team_sport_forecasts import _signal_and_input
    from wettfinder_surface import build_wettfinder_card,render_compact_row_html
    from riskobet_automation import snapshot_from_dict
    from riskobet_prices import shared_price_overlays
    from riskobet_domain import RiskCandidate, EvidenceStage, ContextState
    signal, r=_signal_and_input()
    quote=prices.parse_game_quotes(odds(),[r],game(),fetched_at=NOW)[r['candidate_id']]
    signal=replace(signal,reference_quote=quote.to_dict())
    card=build_wettfinder_card(signal,quote,now=NOW)
    assert card.price_code=='OBSERVED' and card.observed_odds==1.75 and not card.confirmed_tip
    assert 'Abgerufen:' in render_compact_row_html(card)
    snapshot=snapshot_from_dict(r['team_sport_snapshot'])
    candidate=RiskCandidate(snapshot_id=snapshot.snapshot_id,event_key=snapshot.event_key,
        sport='basketball',competition='NBA',event_label=snapshot.event_label,starts_at=snapshot.starts_at,
        market_key='match_winner_including_ot',market_label='Sieger',selection_key='home',selection_label=r['competitor_a'],
        model_probability=.4,cautious_probability=None,stage=EvidenceStage.RESEARCH,context_state=ContextState.PARTIAL,
        policy_version='test',pros=('test',),cons=('test',),missing_core_data=(),
        settlement_contract='riskobet-settlement-v1:basketball:match_winner_including_ot:home')
    overlay=shared_price_overlays([candidate],[dict(r,reference_quote=quote.to_dict())],now=NOW)[candidate.candidate_id]
    assert overlay.status=='OBSERVED' and overlay.observed_odds==1.75
    from riskobet_prices import load_shared_price_overlays
    key=prices._key(r)
    doc={'schema':1,'attempts':{},'quotes':{key:{'binding':list(prices._binding(r)),
        'quote':replace(quote,candidate_id=key).to_dict()}}}
    (tmp_path/'team_sport_quotes.json').write_text(json.dumps(doc),encoding='utf-8')
    result=load_shared_price_overlays([candidate],[snapshot],now=NOW,path=tmp_path/'absent-normal-pool.json')
    assert result[candidate.candidate_id]==overlay


def test_duplicate_native_events_never_inherit_one_bookmaker_game(tmp_path):
    def unexpected(*args,**kwargs): raise AssertionError('ambiguous request')
    r=row();duplicate=dict(r,provider_event_id='other-native-event',candidate_id='other')
    result=prices.refresh_team_sport_prices([r,duplicate],api_key='test',now=NOW,path=tmp_path/'quotes.json',governor=Governor(),get=unexpected)
    assert result['quotes']==0 and result['checked']==0
    assert result['errors']==['basketball:ValueError','basketball:ValueError']


def test_schedule_correction_removes_cached_price(tmp_path):
    path=tmp_path/'quotes.json';modified=False
    def get(url,**kwargs):
        g=game()
        if modified: g['date']=(NOW+timedelta(hours=7)).isoformat()
        return SimpleNamespace(status_code=200,headers={},json=lambda:{'errors':[], 'response':[g] if url.endswith('/games') else odds()})
    prices.refresh_team_sport_prices([row()],api_key='test',now=NOW,path=path,governor=Governor(),get=get)
    assert prices.load_cached_quote(row(),now=NOW,path=path) is not None
    modified=True
    prices.refresh_team_sport_prices([row()],api_key='test',now=NOW+timedelta(hours=3),path=path,governor=Governor(),get=get)
    assert prices.load_cached_quote(row(),now=NOW+timedelta(hours=3),path=path) is None


def test_request_budget_caps_each_sport_to_eight_events(tmp_path):
    calls=[]
    rows=[row(provider_event_id=str(i),competitor_a='Club '+str(i),selected_competitor='Club '+str(i)) for i in range(20)]
    def get(url,**kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=200,headers={},json=lambda:{'errors':[], 'response':[]})
    result=prices.refresh_team_sport_prices(rows,api_key='test',now=NOW,path=tmp_path/'prices.json',governor=Governor(),get=get)
    assert result['checked']==8 and len(calls)==1


def _worker_snapshot():
    """A literal immutable existing forecast, never a model execution."""
    from riskobet_domain import EventModelSnapshot, FactorEvidence, stable_event_key
    from team_sport_forecasts import TeamSportForecast

    start = NOW + timedelta(hours=6)
    forecast = TeamSportForecast(schema='team-sport-forecast-v1', sport='basketball',
        provider='ESPN', provider_event_id='native-1', home_id='1', away_id='8',
        home='Team 1', away='Team 8', starts_at=start, modeled_at=NOW, source_observed_at=NOW,
        model_version='fixture-v1', model_input_hash='a'*64, p_home=.61, p_away=.39,
        market_contract='match_winner_including_ot', model_scope='including_overtime',
        training_games=84, home_games=21, away_games=21,
        evaluation=dict(count=24, brier_score=.22, baseline_brier_score=.25, log_loss=.60,
                        method='results-observed-before-evaluated-kickoff'),
        latest_result_observed_at=NOW, missing=(), factors=('Observed fixture history',),
        limitations=('Research model not independently confirmed',))
    factor = FactorEvidence('history', 'Observed fixture history', 'ESPN', NOW, NOW, start,
                            coverage=1.0, sample_size=84)
    return EventModelSnapshot(stable_event_key('basketball', 'ESPN', 'native-1'),
        'basketball', 'NBA', 'Team 1 vs Team 8', start, NOW, NOW, 'fixture-v1', 'a'*64,
        factors=(factor,), team_sport_forecast=forecast)


@pytest.mark.parametrize('mode', ['configured', 'missing_key', 'isolated', 'no_snapshots'])
def test_worker_refreshes_existing_team_snapshot_prices_only_in_configured_production(
        monkeypatch, tmp_path, mode):
    from config_loader import AppConfig
    from riskobet_domain import RiskRunSnapshot, RunStatus
    from test_esports_prices import _price_worker_options
    from wettfinder_automation import run_wettfinder

    snapshot = _worker_snapshot()
    original = snapshot.to_dict()
    run = RiskRunSnapshot(NOW, NOW, RunStatus.COMPLETE,
                         snapshots=() if mode == 'no_snapshots' else (snapshot,))
    options = _price_worker_options(monkeypatch, tmp_path, now=NOW, production=mode != 'isolated')
    governor, calls = Governor(), []

    def transport(url, **kwargs):
        calls.append(url)
        assert kwargs['headers']['x-apisports-key'] == 'fixture-key'
        return SimpleNamespace(status_code=200, headers={}, json=lambda:
            {'errors': [], 'response': [game()] if url.endswith('/games') else odds()})

    actual_refresh = prices.refresh_team_sport_prices
    monkeypatch.setattr(prices, 'refresh_team_sport_prices',
        lambda rows, **kwargs: actual_refresh(rows, governor=governor, get=transport, **kwargs))
    output = run_wettfinder(**options,
        config=AppConfig(api_football_key=None if mode == 'missing_key' else 'fixture-key'),
        esports_loader=lambda **_kwargs: [], riskobet_enabled=True, riskobet_sources={},
        riskobet_runner=lambda **_kwargs: run)
    assert output['riskobet']['status'] == 'complete'
    summary = output['team_sport_prices']
    assert summary.get('provider_status') == {
        'configured': 'configured', 'missing_key': 'missing_api_key',
        'isolated': 'not_requested_for_isolated_run', 'no_snapshots': 'configured'}[mode]
    if mode == 'configured':
        assert summary['checked'] == 1 and summary['quotes'] == 2
        assert len(calls) == 2 and len(governor.completed) == 2
        assert prices.load_cached_quote(row(), now=NOW, path=tmp_path/'team_sport_quotes.json').best_odds == 1.75
        assert prices.load_cached_quote(row(side='away'), now=NOW, path=tmp_path/'team_sport_quotes.json').best_odds == 2.30
        options['now'] = NOW + timedelta(minutes=30)
        again = run_wettfinder(**options, config=AppConfig(api_football_key='fixture-key'),
            esports_loader=lambda **_kwargs: [], riskobet_enabled=True, riskobet_sources={},
            riskobet_runner=lambda **_kwargs: run)
        assert again['team_sport_prices']['checked'] == 0
        assert len(calls) == 2
        assert [(r['key'], r['probability']) for r in output['model_candidates']] == [
            (r['key'], r['probability']) for r in again['model_candidates']]
    else:
        assert not calls
        assert not (tmp_path/'team_sport_quotes.json').exists()
    assert snapshot.to_dict() == original
    assert 'fixture-key' not in json.dumps(output)
