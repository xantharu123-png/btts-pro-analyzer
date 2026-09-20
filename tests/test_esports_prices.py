from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
import requests

import esports_prices as prices
from api_budget import APIBudgetExceeded, APIBudgetUnavailable
from market_consensus import (MarketConsensus, quote_matches_candidate, quote_below_publication_floor,
    wettfinder_reference_price_status, wettfinder_consensus)
from oddspapi_client import OddsPapiClient, MONTH_PROVIDER, DAY_PROVIDER

NOW = datetime(2030, 1, 15, 10, tzinfo=timezone.utc)
KEY = 'fixture-only-not-a-real-api-key'


def row(**changes):
    return dict(candidate_id='esports-123', key='esports-123', source='esports_shadow',
        sport='E-Sport', competition='CS2', fixture_source='pandascore', provider_event_id='123',
        competitor_a='Sparta eSports', competitor_b='Inox Division', selected_competitor='Sparta eSports',
        selection='Sieg Sparta eSports', market_key='H2H', probability=.61,
        scheduled_start=(NOW+timedelta(hours=6)).isoformat()) | changes


def event(*, sport=17, first=2.5, second=1.48):
    market, a, b = prices.MARKETS[sport]
    return dict(fixtureId='native123', sportId=sport, participant1Id=101, participant2Id=102,
        tournamentId=456, statusId=0, hasOdds=True, trueStartTime=None, trueEndTime=None,
        participant1Name='Sparta eSports', participant2Name='Inox Division',
        startTime=(NOW+timedelta(hours=6)).isoformat(), bookmakerOdds={slug:{
            'bookmakerIsActive': True, 'suspended': False, 'bookmakerFixtureId': 'book123',
            'markets': {str(market): {'marketActive': True, 'outcomes': {
                str(k): {'players': {'0': {'active': True, 'price': value,
                    'playerName': None, 'exchangeMeta': None, 'changedAt': NOW.isoformat()}}}
                for k, value in ((a,first),(b,second))}}}}
            for slug in prices.BOOKMAKERS})


def document(*events):
    return dict(schema='esports-prices-v1', fetched_at=NOW.isoformat(), events=list(events or [event()]))


def quote(r=None, e=None):
    return prices.load_cached_quote(r or row(), now=NOW, document=document(e or event()))


@pytest.mark.parametrize('sport,game', [(16,'DOTA2'),(17,'CS2'),(18,'LoL'),(61,'Valorant')])
def test_exact_series_for_each_supported_game(sport, game):
    r = row(competition=game)
    q = quote(r, event(sport=sport))
    assert q.best_odds == 2.5 and q.bookmaker_count == 2
    assert q.event_discipline == sport and quote_matches_candidate(q, r)
    assert MarketConsensus.from_dict(q.to_dict()) == q
    assert wettfinder_consensus(q, now=NOW) is None
    assert wettfinder_reference_price_status(q, 1.5, candidate=r, now=NOW).code == 'OBSERVED'
    assert not q.is_fresh(NOW) and not q.is_wettfinder_fresh(NOW)


def test_reversed_native_order_prices_the_right_team():
    e = event(); e['participant1Name'],e['participant2Name'] = e['participant2Name'],e['participant1Name']
    assert quote(e=e).best_odds == 1.48
    assert quote(row(selected_competitor='Inox Division'), e).best_odds == 2.5


@pytest.mark.parametrize('changes', [dict(competition='LoL'), dict(competition='Unknown'),
    dict(market_key='MAP_WINNER'),dict(fixture_source='other'), dict(provider_event_id=''),
    dict(selected_competitor='Wrong'),dict(competitor_a='Sparta Academy'),
    dict(scheduled_start=(NOW+timedelta(hours=7)).isoformat())])
def test_wrong_game_market_identity_or_start_never_inherits(changes):
    assert quote(row(**changes)) is None


@pytest.mark.parametrize('field,value', [('statusId',1),('statusId',False),('hasOdds',False),
    ('trueStartTime',NOW.isoformat()),('participant1Id',True),('participant2Id',101),
    ('startTime',(NOW-timedelta(minutes=1)).isoformat())])
def test_not_live_or_malformed_event(field,value):
    e=event(); e[field]=value
    assert quote(e=e) is None


@pytest.mark.parametrize('change', ['map','three_way','inactive_book','suspended','inactive_market',
    'inactive_point','player','exchange','future_clock','invalid_other_price','missing_book_id','malformed'])
def test_invalid_exact_market_fails_closed(change):
    e=event()
    for book in e['bookmakerOdds'].values():
        m=book['markets']['171']; p=m['outcomes']['171']['players']['0']
        if change=='map': book['markets']={'172':m}
        if change=='three_way': m['outcomes']['999']=deepcopy(m['outcomes']['171'])
        if change=='inactive_book': book['bookmakerIsActive']=False
        if change=='suspended': book['suspended']=True
        if change=='inactive_market': m['marketActive']=False
        if change=='inactive_point': p['active']=False
        if change=='player': p['playerName']='Player'
        if change=='exchange': p['exchangeMeta']={'liquidity':100}
        if change=='future_clock': p['changedAt']=(NOW+timedelta(hours=1)).isoformat()
        if change=='invalid_other_price': m['outcomes']['172']['players']['0']['price']=1
        if change=='missing_book_id': book.pop('bookmakerFixtureId')
        if change=='malformed': m['outcomes']['171']['players']['0']=[]
    assert quote(e=e) is None


def test_duplicates_staleness_kickoff_and_bound_floor():
    r=row(); e=event(first=1.1999)
    q=quote(r,e)
    assert quote_below_publication_floor(q,candidate=r,now=NOW)
    assert not quote_below_publication_floor(quote(r,event(first=1.20)),candidate=r,now=NOW)
    assert prices.load_cached_quote(r,now=NOW,document=document(e,deepcopy(e))) is None
    for clock in (NOW+timedelta(hours=6),NOW+timedelta(days=2),NOW-timedelta(hours=1)):
        assert prices.load_cached_quote(r,now=clock,document=document(e)) is None
    assert not quote_matches_candidate(replace(q,origin_event_id='124'),r)
    assert not quote_matches_candidate(replace(q,event_discipline=18),r)
    assert not quote_matches_candidate(replace(q,event_discipline=True),r)


class Client:
    def __init__(self, e=None): self.calls=[];self.e=e or event();self.fail=False;self.duplicate=False
    def authorize(self): return {'limit':250,'used':0,'remaining':250}
    def ensure_refresh_budget(self, required_calls=3):
        if self.fail: raise APIBudgetExceeded('test')
    def get(self,endpoint,params):
        self.calls.append((endpoint,params))
        e=deepcopy(self.e)
        if endpoint=='fixtures': return [e]
        assert set(params)=={'tournamentIds','bookmaker','verbosity','language'}
        e['bookmakerOdds']={params['bookmaker']:e['bookmakerOdds'][params['bookmaker']]}
        return [e,e] if self.duplicate else [e]


def test_shared_bounded_refresh_and_read_only_reuse(tmp_path):
    p=tmp_path/'esports_quotes.json'; c=Client()
    result=prices.refresh_esports_prices(api_key=KEY,now=NOW,path=p,client=c)
    assert result=={'status':'complete','errors':[],'events':1}
    assert len(c.calls)==3 and p.stat().st_size < 5000
    rows=prices.attach_cached_esports_prices([row()],now=NOW,path=p)
    assert rows[0]['probability']==.61 and rows[0]['reference_quote']['best_odds']==2.5
    assert prices.load_cached_quote(row(candidate_id='new-model'),now=NOW,path=p).candidate_id=='new-model'
    assert prices.refresh_esports_prices(api_key=KEY,now=NOW+timedelta(minutes=30),path=p,client=c)['status']=='cached'
    assert len(c.calls)==3 and KEY not in p.read_text()


def test_native_five_tournament_limit_batches_without_dropping_disciplines(tmp_path):
    class BatchedClient(Client):
        def get(self,endpoint,params):
            self.calls.append((endpoint,params))
            all_events=[]
            for i in range(8):
                e=event(sport=(16,17,18,61)[i%4])
                e.update(tournamentId=500+i,fixtureId=f'event{i}')
                all_events.append(e)
            if endpoint=='fixtures': return all_events
            requested=list(map(int,params['tournamentIds'].split(',')))
            assert 1 <= len(requested) <= 5
            return [e for e in all_events if e['tournamentId'] in requested]
    p=tmp_path/'quotes.json'; c=BatchedClient()
    result=prices.refresh_esports_prices(api_key=KEY,now=NOW,path=p,client=c)
    assert result=={'status':'complete','errors':[],'events':8}
    assert len(c.calls)==5
    assert {e['sportId'] for e in json.loads(p.read_text())['events']}=={16,17,18,61}
    assert prices.refresh_esports_prices(api_key=KEY,now=NOW+timedelta(hours=12),path=p,client=c)['status']=='cached'
    assert len(c.calls)==5


def test_failed_budget_keeps_old_observation_without_new_timestamp(tmp_path):
    p=tmp_path/'esports_quotes.json'; c=Client()
    prices.refresh_esports_prices(api_key=KEY,now=NOW,path=p,client=c)
    c.fail=True
    result=prices.refresh_esports_prices(api_key=KEY,now=NOW+timedelta(hours=12),path=p,client=c)
    saved=json.loads(p.read_text())
    assert result['status']=='failed' and saved['fetched_at']==NOW.isoformat() and len(c.calls)==3


def test_duplicate_response_and_schedule_changes_remove_prices(tmp_path):
    p=tmp_path/'esports_quotes.json'; c=Client()
    c.e['startTime']=(NOW+timedelta(hours=22)).isoformat()
    prices.refresh_esports_prices(api_key=KEY,now=NOW,path=p,client=c)
    c.duplicate=True
    result=prices.refresh_esports_prices(api_key=KEY,now=NOW+timedelta(hours=12),path=p,client=c)
    assert result['status']=='partial' and result['events']==1  # keep old timestamp on wholly failed refresh
    assert json.loads(p.read_text())['fetched_at']==NOW.isoformat()
    c.duplicate=False;c.e['statusId']=3
    prices.refresh_esports_prices(api_key=KEY,now=NOW+timedelta(hours=14),path=p,client=c)
    assert not json.loads(p.read_text())['events']


def response(body, status=200):
    r=requests.Response();r.status_code=status
    r._content=json.dumps(body).encode();r._content_consumed=True
    return r


def account(**changes):
    return {'current_subscription_id':'sub','subscriptions':[dict(subscription_id='sub',
        is_active=True,auto_renew=False,price=None,request_limit=250,request_count=0)|changes]}


@pytest.fixture
def no_delay(monkeypatch):
    monkeypatch.setattr('oddspapi_client.time.sleep',lambda *_:None)


def test_shared_month_day_budget_and_free_account(tmp_path,no_delay):
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        assert kwargs['allow_redirects'] is False and kwargs['params']['apiKey']==KEY
        return response(account() if url.endswith('account') else [])
    c=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=get,now=NOW)
    assert c.authorize()['remaining']==250
    for _ in range(7): c.get('fixtures',{'from':'a','to':'b'})
    with pytest.raises(APIBudgetExceeded): c.get('fixtures',{})
    with pytest.raises(APIBudgetExceeded): c.ensure_refresh_budget()
    assert len(calls)==8
    other=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=get,now=NOW)
    other.authorize()
    with pytest.raises(APIBudgetExceeded): other.get('fixtures',{})
    assert other.month.snapshot(api_key=KEY,provider=MONTH_PROVIDER,now=NOW).remaining_estimate==243


@pytest.mark.parametrize('changes',[{'price':1},{'auto_renew':True},{'is_active':False},
    {'request_limit':500},{'request_count':-1},{'request_count':0.5},{'request_limit':True},{'price':False}])
def test_no_paid_or_malformed_plan(tmp_path,no_delay,changes):
    c=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=lambda *a,**k:response(account(**changes)),now=NOW)
    with pytest.raises(APIBudgetUnavailable): c.authorize()
    with pytest.raises(APIBudgetUnavailable): c.get('fixtures',{})


def test_month_account_reconciliation_never_increases_budget(tmp_path,no_delay):
    c=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=lambda *a,**k:response(account(request_count=224)),now=NOW)
    c.authorize()
    with pytest.raises(APIBudgetExceeded): c.ensure_refresh_budget()
    c.get_http=lambda *a,**k:response(account())
    c.authorize()
    assert c.month.snapshot(api_key=KEY,provider=MONTH_PROVIDER,now=NOW).remaining_estimate==26


def test_unknown_requests_and_secret_transport_errors(tmp_path,no_delay):
    def fail(*args,**kwargs): raise requests.ConnectionError('url?apiKey='+KEY)
    c=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=fail,now=NOW)
    with pytest.raises(APIBudgetUnavailable) as exc: c.authorize()
    assert KEY not in str(exc.value)
    for endpoint,params in [('account',{}),('../fixtures',{}),('fixtures',{'apiKey':'other'})]:
        with pytest.raises(APIBudgetUnavailable): c.get(endpoint,params)
    c.get_http=lambda *a,**k:response({},302)
    with pytest.raises(APIBudgetUnavailable): c.authorize()


def test_riskobet_series_price_does_not_price_a_map(tmp_path):
    from riskobet_domain import stable_event_key
    from riskobet_prices import load_shared_price_overlays
    key=stable_event_key('esports','pandascore','123')
    snap=SimpleNamespace(sport='esports',competition='CS2',event_key=key,team_sport_forecast=None,
        event_label='Sparta eSports vs Inox Division', starts_at=NOW+timedelta(hours=6),
        factors=(SimpleNamespace(factor_key='esports_match_id:123'),))
    def candidate(market):
        return SimpleNamespace(candidate_id=market,event_key=key,sport='esports',competition='CS2',
            market_key=market,selection_key='away',selection_label='Inox Division',starts_at=snap.starts_at,
            settlement_contract=f'riskobet-settlement-v1:esports:{market}:away')
    prices.refresh_esports_prices(api_key=KEY,now=NOW,path=tmp_path/'esports_quotes.json',client=Client())
    overlays=load_shared_price_overlays([candidate('series_winner'),candidate('at_least_one_map')],
        [snap],now=NOW,path=tmp_path/'wettfinder_latest.json')
    assert set(overlays)=={'series_winner'}
    assert overlays['series_winner'].observed_odds==1.48


def test_worker_and_public_reader_reuse_the_cache(tmp_path):
    from config_loader import AppConfig
    from esports_shadow import ESPORTS_MODEL_VERSION
    from betting_math import BETTING_POLICY_VERSION
    from ev_signal_sources import ModelSignal, automated_wettfinder_forecasts
    from wettfinder_automation import run_wettfinder
    from test_wettfinder_automation import _football_snapshot
    r=row(); names=ModelSignal.__dataclass_fields__
    signal=ModelSignal(**{k:v for k,v in r.items() if k in names},label='CS2 winner',
        detail='Real model fixture',market='Match Winner',event_label='Sparta eSports vs Inox Division',
        probability_haircut=.1,evidence_stage='SHADOW',policy_version=f'{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}')
    prices.refresh_esports_prices(api_key=KEY,now=NOW,path=tmp_path/'esports_quotes.json',client=Client())
    path=tmp_path/'wettfinder_latest.json'
    output=run_wettfinder(now=NOW,state_path=path,config=AppConfig(oddspapi_key=KEY),
        football_scanner=lambda d:_football_snapshot(NOW),football_quote_loader=lambda rows:({},[]),
        tennis_loader=lambda **kw:[],esports_loader=lambda **kw:[signal],riskobet_enabled=False)
    assert output['sources']['esports']['reference_quote_count']==1
    saved=[r for r in output['model_candidates'] if r['source']=='esports_shadow'][0]
    assert saved['probability']==.61 and saved['reference_quote']['best_odds']==2.5
    assert saved['evidence_stage']=='SHADOW'
    forecasts=automated_wettfinder_forecasts(path,now=NOW)
    selected=next(s for s in forecasts if s.sport=='E-Sport')
    assert selected.probability==.61 and selected.reference_quote['best_odds']==2.5
    from wettfinder_surface import build_wettfinder_card
    card=build_wettfinder_card(selected,selected.reference_quote,now=NOW)
    assert card.observed_odds==2.5 and card.price_code=='OBSERVED'


def test_config_key_loaded_without_affecting_other_credentials(monkeypatch,tmp_path):
    from config_loader import load_app_config
    monkeypatch.setenv('ODDSPAPI_KEY',KEY)
    assert load_app_config(config_path=tmp_path/'missing.ini').oddspapi_key==KEY


def test_two_native_events_do_not_share_one_named_price(tmp_path):
    p=tmp_path/'esports_quotes.json'
    prices.refresh_esports_prices(api_key=KEY,now=NOW,path=p,client=Client())
    result=prices.attach_cached_esports_prices([row(),row(provider_event_id='124',candidate_id='different')],now=NOW,path=p)
    assert all(r['reference_quote'] is None for r in result)


def test_oversized_response_is_rejected(tmp_path,no_delay,monkeypatch):
    monkeypatch.setattr('oddspapi_client.MAX_RESPONSE_BYTES',100)
    c=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=lambda *a,**k:response({'data':'x'*101}),now=NOW)
    with pytest.raises(APIBudgetUnavailable): c.authorize()


def test_parallel_clients_share_atomic_budget(tmp_path,no_delay):
    from concurrent.futures import ThreadPoolExecutor
    calls=[]
    def run(_):
        def get(url,**kw):
            if not url.endswith('account'): calls.append(url)
            return response(account() if url.endswith('account') else [])
        c=OddsPapiClient(KEY,db_path=tmp_path/'api.db',get=get,now=NOW)
        c.authorize()
        try: c.get('fixtures',{}); return True
        except APIBudgetExceeded: return False
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(run,range(12)))==7
    assert len(calls)==7


def test_legacy_quote_serialization_has_no_new_null_field():
    from test_team_sport_prices import row as team_row, game, odds, NOW as team_now
    from team_sport_prices import parse_game_quotes
    r=team_row()
    q=next(iter(parse_game_quotes(odds(),[r],game(),fetched_at=team_now).values()))
    assert 'event_discipline' not in q.to_dict()


@pytest.mark.parametrize('source',['esports_shadow','automated_wettfinder_forecast'])
def test_daily3_and_wettfinder_do_not_change_probability_for_quote(tmp_path,source):
    from ev_signal_sources import ModelSignal
    from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog
    from daily3_selection import daily3_choices
    r=row(source=source);names=ModelSignal.__dataclass_fields__
    signal=ModelSignal(**{k:v for k,v in r.items() if k in names},label='CS2 winner',
        detail='Fixture',market='Match Winner',event_label='Sparta eSports vs Inox Division',
        probability_haircut=.1,evidence_stage='SHADOW',policy_version='test',context_complete=True)
    low=replace(signal,reference_quote=quote(e=event(first=1.19)).to_dict())
    allowed=replace(signal,reference_quote=quote(e=event(first=1.20)).to_dict())
    assert low.probability==allowed.probability==signal.probability
    low_catalog=compose_wettfinder_catalog([build_wettfinder_card(low,low.reference_quote,now=NOW)])
    allowed_catalog=compose_wettfinder_catalog([build_wettfinder_card(allowed,allowed.reference_quote,now=NOW)])
    assert not low_catalog.featured + low_catalog.additional
    assert allowed_catalog.featured + allowed_catalog.additional
    # Only exclusion is asserted here; an observation does not release a SHADOW model.
    assert not daily3_choices([low],now=NOW)
