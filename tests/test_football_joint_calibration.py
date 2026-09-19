"""Joint-law invariants; expected set relations are independent of calibration."""
import pytest
import challenge_engine as engine
from tests.test_football_original_capture import values


def test_fitted_complementary_targets_remain_a_probability_law():
    fixture, history = values()
    probabilities = [.1 + .8 * i / 100 for i in range(101)]
    outcomes = [int(i >= 50) for i in range(101)]
    curve = engine._fit_calibration_map(probabilities, outcomes)
    complement = engine._fit_calibration_map([1-p for p in probabilities], [1-y for y in outcomes])
    maps = {key: curve for key in ('RESULT_AWAY', 'RESULT_HOME')}
    maps.update({key: complement for key in ('DC_1X', 'DC_X2')})
    result = engine.fixture_market_probabilities(fixture, history, maps)
    p = result['probabilities']
    for variant in range(3):
        assert p['RESULT_AWAY'][variant] + p['DC_1X'][variant] == pytest.approx(1, abs=1e-10)
        assert p['RESULT_HOME'][variant] + p['DC_X2'][variant] == pytest.approx(1, abs=1e-10)
        assert sum(p[key][variant] for key in ('RESULT_HOME','RESULT_DRAW','RESULT_AWAY')) == pytest.approx(1, abs=1e-10)


def test_projection_identity_sparse_extremes_and_determinism():
    from football_joint_calibration import calibrate_joint_distribution
    specs = engine.GOAL_MARKET_SPECS
    raw = {(0,0): .4, (1,0): .3, (0,1): .3, (9,9): 0.0}
    assert calibrate_joint_distribution(raw, specs, {})[0] == raw
    assert calibrate_joint_distribution(raw, specs, {s.key: lambda p:p for s in specs})[0] == raw
    maps = {s.key: lambda p: 1.0 for s in specs}
    effective, diagnostics = calibrate_joint_distribution(raw, specs, maps)
    reordered, _ = calibrate_joint_distribution(dict(reversed(list(raw.items()))), tuple(reversed(specs)), maps)
    assert effective == reordered
    assert sum(effective.values()) == pytest.approx(1, abs=1e-12)
    assert min(effective.values()) >= 0 and effective[9,9] == 0
    assert diagnostics['success'] is True


@pytest.mark.parametrize('target', [float('nan'), float('inf'), -.1, 1.1, 'bad', True])
def test_invalid_targets_fail_before_publication(target):
    from football_joint_calibration import calibrate_joint_distribution
    with pytest.raises(ValueError, match='target'):
        calibrate_joint_distribution({(0,0):1.0}, engine.GOAL_MARKET_SPECS, {'RESULT_DRAW':lambda p:target})


def test_zero_support_rejected_and_solver_failure_is_raw_fallback(monkeypatch):
    import football_joint_calibration as joint
    from types import SimpleNamespace
    with pytest.raises(ValueError):
        joint.calibrate_joint_distribution({(0,0):0.0}, engine.GOAL_MARKET_SPECS, {})
    with pytest.raises(ValueError):
        joint.calibrate_joint_distribution({(0,0):True}, engine.GOAL_MARKET_SPECS, {})
    raw={(0,0):.5,(1,0):.5}
    monkeypatch.setattr(joint, 'minimize', lambda *a, **kw: SimpleNamespace(success=False, message='test failure', nit=200))
    effective, diagnostics = joint.calibrate_joint_distribution(raw, engine.GOAL_MARKET_SPECS, {'RESULT_DRAW': lambda p:.9})
    assert effective == raw and diagnostics['success'] is False
    assert diagnostics['status'] == 'raw-fallback'


def test_all_families_variants_marginals_means_and_capture_parity():
    fixture, history = values()
    curves = {s.key: (lambda p: .1 + .7*p) for s in engine.MARKET_SPECS}
    captured=[]
    model = engine.fixture_market_probabilities(fixture, history, curves, original_capture=captured.append)
    plain = engine.fixture_market_probabilities(fixture, history, curves)
    assert model == plain
    capture = captured[0].to_dict()
    assert capture['schema'] == 2
    for family, specs in [('goals',engine.GOAL_MARKET_SPECS),('corners',engine.CORNER_MARKET_SPECS),('yellow',engine.YELLOW_MARKET_SPECS)]:
        for index,variant in enumerate(('active','season','form')):
            record = model['distribution_capture']['families'][family][variant]
            matrix={(h,a):p for h,a,p in record['effective_cells']}
            assert sum(matrix.values()) == pytest.approx(1, abs=1e-12)
            for spec in specs:
                marginal=sum(p for (h,a),p in matrix.items() if engine.market_outcome(spec,h,a))
                assert model['probabilities'][spec.key][index] == pytest.approx(marginal, abs=1e-12)
            means=tuple(sum(cell[side]*p for cell,p in matrix.items()) for side in (0,1))
            public=model[variant+'_lambdas'] if family=='goals' else model['count_models'][family][variant+'_counts']
            assert public == pytest.approx(means, abs=1e-12)
    assert capture['distribution_capture']==model['distribution_capture']
    p=model['probabilities']
    for index in range(3):
        assert p['HOME_OVER_1_5'][index] <= p['HOME_OVER_0_5'][index]
        assert p['BTTS_YES'][index]+p['BTTS_NO'][index] == pytest.approx(1,abs=1e-10)
        assert p['BTTS_YES'][index] <= min(p['HOME_OVER_0_5'][index],p['AWAY_OVER_0_5'][index])
        assert p['MIXED_BTTS_OR_OVER_2_5'][index] >= max(p['BTTS_YES'][index],p['TOTAL_OVER_2_5'][index])
        assert p['MIXED_BTTS_OR_OVER_2_5'][index] <= p['BTTS_YES'][index]+p['TOTAL_OVER_2_5'][index]
        assert p['RESULT_TOTAL_1X_UNDER_3_5'][index] <= min(p['DC_1X'][index],p['TOTAL_UNDER_3_5'][index])
        for over in (key for key in p if '_OVER_' in key or key.startswith('OVER_')):
            under=over.replace('OVER_','UNDER_')
            if under in p:
                assert p[over][index]+p[under][index] == pytest.approx(1,abs=1e-10)
        for prefix, low, high in [('CORNERS', '5_5','11_5'),('YELLOW','1_5','4_5'),
                                  ('HOME_CORNERS','2_5','5_5'),('AWAY_CORNERS','2_5','5_5')]:
            assert p[prefix+'_OVER_'+high][index]<=p[prefix+'_OVER_'+low][index]


def test_walk_forward_uses_identical_prior_day_joint_path(monkeypatch):
    from copy import deepcopy
    from datetime import datetime,timedelta
    from tests.test_calibration import league_history
    rows = league_history(cycles=24)
    last=deepcopy(rows[-1]);last['fixture']['id']+=10000
    last['fixture']['date']=(datetime.fromisoformat(last['fixture']['date'])+timedelta(hours=8)).isoformat()
    rows.append(last)
    production = engine.fixture_market_probabilities
    seen=[]
    def observe(fixture, prior, calibration=None, **kwargs):
        day=datetime.fromisoformat(fixture['fixture']['date']).date()
        assert all(datetime.fromisoformat(row['fixture']['date']).date()<day for row in prior)
        model=production(fixture, prior, calibration, **kwargs)
        if model is not None:
            seen.append(({key:model[key] for key in ('probabilities','raw_probabilities')}, calibration))
        return model
    monkeypatch.setattr(engine, 'fixture_market_probabilities', observe)
    records=engine._walk_forward_market_records(rows)
    assert any(maps for _,maps in seen)
    assert records['RESULT_HOME']['probabilities'] == [m['probabilities']['RESULT_HOME'][0] for m,_ in seen]
    assert records['RESULT_HOME']['raw'] == [m['raw_probabilities']['RESULT_HOME'][0] for m,_ in seen]
    assert all(metric.prediction_version == engine.CHALLENGE_PREDICTION_VERSION for metric in engine._validation_metrics_from_records(records).values())
    assert seen[-1][1] is seen[-2][1]  # One frozen set of maps for a whole day.
    changed=deepcopy(rows)
    changed[-2]['goals']={'home':12,'away':0}
    changed[-1]['goals']={'home':0,'away':12}
    perturbed=engine._walk_forward_market_records(changed)
    for key in records:
        assert perturbed[key]['probabilities']==records[key]['probabilities']
        assert perturbed[key]['raw']==records[key]['raw']


def test_current_release_requires_matching_candidate_and_validation_versions(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(engine,'candidate_is_forecast_credible',lambda c:True)
    monkeypatch.setattr(engine,'_credible_statistical_release_validation',lambda v:True)
    c=SimpleNamespace(validation=SimpleNamespace(prediction_version=None), prediction_version=None,
        model_scope=engine.MODEL_SCOPE_SAME_COMPETITION,context={'passed':True,'release_context_complete':True,'release_eligible':True})
    assert not engine.candidate_is_wettfinder_release_credible(c)
    c.prediction_version=engine.CHALLENGE_PREDICTION_VERSION
    assert not engine.candidate_is_wettfinder_release_credible(c)
    c.validation.prediction_version=engine.CHALLENGE_PREDICTION_VERSION
    assert engine.candidate_is_wettfinder_release_credible(c)


def test_original_v2_closed_schema_and_v1_transport(monkeypatch,tmp_path):
    import json
    import model_artifacts
    from football_original import FootballOriginal
    from context_models import football_original_storage as storage
    from tests.test_football_original_storage import capture,NOW
    original=capture(monkeypatch)
    stored=storage.store_original(tmp_path/'v2.db',original,created_at=NOW,max_new_payload_bytes=4_000_000)
    assert storage.load_original(tmp_path/'v2.db',stored.manifest_digest)._bytes==original._bytes
    for mutation in ({'schema':3},{'schema':True},{'kind':'football-original-market-calculation-v1'},{'extra':1}):
        packet=original.to_dict();packet.update(mutation)
        with pytest.raises(model_artifacts.ArtifactIntegrityError):
            storage.prepare_original(FootballOriginal(model_artifacts.canonical_bytes(packet)))
    packet=original.to_dict();packet.pop('distribution_capture')
    with pytest.raises(model_artifacts.ArtifactIntegrityError):
        storage.prepare_original(FootballOriginal(model_artifacts.canonical_bytes(packet)))


def test_persisted_unversioned_football_row_cannot_release():
    from ev_signal_sources import _football_recommendation_release_eligible
    from wettfinder_automation import _football_record_release_eligible as _football_row_release_eligible
    row={'context':{'release_context_complete':True,'release_eligible':True},'model_scope':'same_competition',
         'context_stale':False,'statistical_release_passed':True,'paired_loss_mean':.05,
         'paired_loss_hac_standard_error':.005,'paired_loss_lower_confidence_bound':.04,
         'paired_loss_p_value':.00001,'fdr_q_value':.0009,'tested_hypotheses':90}
    assert not _football_recommendation_release_eligible(row)
    assert not _football_row_release_eligible(row)
    row.update(prediction_version=engine.CHALLENGE_PREDICTION_VERSION,validation_prediction_version=engine.CHALLENGE_PREDICTION_VERSION)
    assert _football_recommendation_release_eligible(row)
    assert _football_row_release_eligible(row)


def test_two_atom_objective_and_within_atom_raw_proportions():
    from football_joint_calibration import calibrate_joint_distribution
    spec=engine.MARKET_BY_KEY['RESULT_HOME']
    raw={(0,0):.5,(1,0):.1,(2,0):.4}
    effective, diagnostics=calibrate_joint_distribution(raw,(spec,),{spec.key:lambda p:.9})
    # Minimize .5*(x-.9)^2+.5*((x-.5)^2+((1-x)-.5)^2): x=1.9/3.
    assert effective[1,0]+effective[2,0] == pytest.approx(1.9/3,abs=1e-8)
    assert effective[2,0]/effective[1,0] == pytest.approx(4,abs=1e-12)


def test_legacy_v1_bytes_remain_readable_without_invented_distributions(monkeypatch,tmp_path):
    import sys
    from tests.football_legacy_reference import load
    from tests.test_football_original_storage import NOW
    from football_original import FootballOriginal
    from context_models import football_original_storage as storage
    legacy=load('challenge_engine'); owning=load('football_original')
    fixture,history=values(); originals=[]
    with monkeypatch.context() as past:
        past.setitem(sys.modules,'challenge_engine',legacy)
        past.setitem(sys.modules,'football_original',owning)
        past.setattr(owning,'_capture_now',lambda:NOW)
        legacy.fixture_market_probabilities(fixture,history,original_capture=originals.append)
    raw=originals[0]._bytes
    original=FootballOriginal(raw)
    assert original.to_dict()['schema']==1
    assert 'distribution_capture' not in original.to_dict()
    stored=storage.store_original(tmp_path/'v1.db',original,created_at=NOW,max_new_payload_bytes=4_000_000)
    restored=storage.load_original(tmp_path/'v1.db',stored.manifest_digest)
    assert restored._bytes==raw and 'distribution_capture' not in restored.to_dict()


def test_historical_authenticated_ticket_reads_and_settles_without_redefinition(monkeypatch,tmp_path):
    import json,sqlite3
    from dataclasses import asdict
    from datetime import datetime,timezone
    import challenge_store
    from tests.football_legacy_reference import load
    from tests.test_challenge_integrity import _candidate
    old=load('challenge_engine')
    now=datetime.now(timezone.utc)
    payload=asdict(_candidate(now))
    payload.pop('prediction_version');payload['validation'].pop('prediction_version')
    payload.pop('market_comparison')  # Optional new presentation metadata did not exist in the old ticket schema.
    payload['validation']=old.ValidationMetrics(**payload['validation'])
    candidate=old.ChallengeCandidate(**payload)
    ticket=old.select_quoted_ticket([candidate],{candidate.candidate_id:2.10},now=now)
    assert ticket is not None
    db=tmp_path/'historic.db'
    ledger=challenge_store.ChallengeLedger(db)
    with monkeypatch.context() as past:
        # Replay the actual old admission function only during old issuance.
        for name in ('candidate_is_credible','risk_managed_ticket_stake',
                     'ticket_stake_passes_log_growth_gate','QuotedTicket'):
            past.setattr(challenge_store,name,getattr(old,name))
        ticket_id=ledger.place_ticket(now.date().isoformat(),ticket,old.ticket_stake(ticket,100),now.isoformat())
    with sqlite3.connect(db) as conn:
        before=conn.execute('SELECT legs_json,ticket_definition_hash FROM challenge_tickets WHERE id=?',(ticket_id,)).fetchone()
    assert 'prediction_version' not in before[0]
    restored=challenge_store.ChallengeLedger(db)
    assert restored.get_ticket(ticket_id)['ticket_definition_hash']==before[1]
    assert restored.settle_ticket(ticket_id,'LOST')['status']=='LOST'
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT legs_json,ticket_definition_hash FROM challenge_tickets WHERE id=?',(ticket_id,)).fetchone()==before
    assert restored.verify_financial_ledger()==(True,None)


def test_unversioned_candidate_serialization_preserves_absent_fields():
    from dataclasses import replace
    from datetime import datetime,timezone
    from tests.test_challenge_integrity import _candidate
    candidate=_candidate(datetime.now(timezone.utc))
    candidate=replace(candidate,prediction_version=None,validation=replace(candidate.validation,prediction_version=None))
    payload=candidate.to_dict()
    assert 'prediction_version' not in payload
    assert 'prediction_version' not in payload['validation']


def test_projection_failure_keeps_raw_law_and_blocks_candidates(monkeypatch):
    import football_joint_calibration as joint
    from types import SimpleNamespace
    fixture,history=values()
    curves={s.key:lambda p:.25+.5*p for s in engine.MARKET_SPECS}
    monkeypatch.setattr(joint,'minimize',lambda *a,**kw:SimpleNamespace(success=False,nit=200,message='bounded test failure'))
    model=engine.fixture_market_probabilities(fixture,history,curves)
    assert model['probabilities']==model['raw_probabilities']
    assert model['projection_success'] is False
    candidates=engine.build_fixture_candidates(fixture,history,{},curves)
    assert candidates and all(any('Kalibrierung fehlgeschlagen' in reason for reason in c.blocked_reasons) for c in candidates)
    assert all(not engine.candidate_is_wettfinder_release_credible(c) for c in candidates)


def test_cross_league_validation_keeps_only_agreeing_versions():
    from challenge_15k import _conservative_validation_map
    from dataclasses import replace
    metric=engine.ValidationMetrics(300,.15,.2,.25,.04,True,prediction_version=engine.CHALLENGE_PREDICTION_VERSION)
    combined=_conservative_validation_map([{'RESULT_HOME':metric},{'RESULT_HOME':metric}])
    assert combined['RESULT_HOME'].prediction_version==engine.CHALLENGE_PREDICTION_VERSION
    stale=replace(metric,prediction_version=None)
    combined=_conservative_validation_map([{'RESULT_HOME':metric},{'RESULT_HOME':stale}])
    assert combined['RESULT_HOME'].prediction_version is None


@pytest.mark.parametrize('case',['missing-diagnostic','extra-record','extra-family','boolean-recipe',
    'wrong-diagnostic-law','negative-cell','duplicate-cell','boolean-count','missing-family',
    'malformed-status','malformed-count-models'])
def test_v2_distribution_capture_is_a_closed_typed_law(case,monkeypatch):
    from tests.test_football_original_storage import capture
    from football_original import FootballOriginal
    from context_models import football_original_storage as storage
    import model_artifacts
    packet=capture(monkeypatch).to_dict()
    distribution=packet['distribution_capture'];record=distribution['families']['goals']['active']
    if case=='missing-diagnostic': record['diagnostics'].pop('success')
    elif case=='extra-record': record['extra']=1
    elif case=='extra-family': distribution['families']['extra']={}
    elif case=='boolean-recipe': distribution['recipe']['prior_anchor']=True
    elif case=='wrong-diagnostic-law': record['diagnostics']['law_version']='old'
    elif case=='negative-cell': record['effective_cells'][0][2]=-.1
    elif case=='duplicate-cell': record['effective_cells'].append(record['effective_cells'][0])
    elif case=='boolean-count': record['effective_cells'][0][0]=True
    elif case=='missing-family': distribution['families'].pop('goals')
    elif case=='malformed-status': record['diagnostics']['status']=[]
    elif case=='malformed-count-models': packet['count_models']=None
    with pytest.raises(model_artifacts.ArtifactIntegrityError):
        storage.prepare_original(FootballOriginal(model_artifacts.canonical_bytes(packet)))


def test_active_only_validation_projects_exact_production_law_without_unused_variants(monkeypatch):
    import football_joint_calibration as joint
    fixture,history=values()
    curves={s.key:lambda p:.1+.8*p for s in engine.MARKET_SPECS}
    full=engine.fixture_market_probabilities(fixture,history,curves)
    calls=[];solver=joint.minimize
    def counted(*args,**kwargs):
        calls.append(1)
        return solver(*args,**kwargs)
    monkeypatch.setattr(joint,'minimize',counted)
    active=engine.fixture_market_probabilities(fixture,history,curves,_validation_only=True)
    assert len(calls)==3
    assert active['probability_variants']==('active',)
    for key in full['probabilities']:
        assert active['probabilities'][key]==(full['probabilities'][key][0],)
        assert active['raw_probabilities'][key]==(full['raw_probabilities'][key][0],)
    with pytest.raises(ValueError,match='validation'):
        engine.fixture_market_probabilities(fixture,history,curves,_validation_only=True,original_capture=lambda value:None)


def test_previous_prediction_cache_cannot_qualify_current_law(tmp_path):
    from challenge_model_cache import save_model_artifact,load_model_artifact
    from tests.football_legacy_reference import load
    fixture,history=values()
    path=tmp_path/'cache.db'
    old=load('challenge_engine')
    metric=engine.ValidationMetrics(300,.15,.2,.25,.04,True)
    save_model_artifact(old.CHALLENGE_PREDICTION_VERSION,39,2026,history,{'RESULT_HOME':metric},{},db_path=path)
    assert load_model_artifact(engine.CHALLENGE_PREDICTION_VERSION,39,2026,history,db_path=path) is None
    current=engine.ValidationMetrics(300,.15,.2,.25,.04,True,prediction_version=engine.CHALLENGE_PREDICTION_VERSION)
    save_model_artifact(engine.CHALLENGE_PREDICTION_VERSION,39,2026,history,{'RESULT_HOME':current},{},db_path=path)
    restored,_=load_model_artifact(engine.CHALLENGE_PREDICTION_VERSION,39,2026,history,db_path=path)
    assert restored['RESULT_HOME'].prediction_version==engine.CHALLENGE_PREDICTION_VERSION
