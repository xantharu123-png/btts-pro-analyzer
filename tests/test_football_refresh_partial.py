"""A missing single-game model must not discard the successful batch peers."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from football_model_refresh import MODEL_REFRESH_VERSION, refresh_fixture_models
from test_challenge_15k import candidate, fixture
from wettfinder_automation import _merge_context_refresh, _football_candidate_record, _challenge_candidate_payload

NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def candidates():
    return [candidate(f'{i}:BTTS_YES', i, .72, kickoff=NOW+timedelta(hours=5)) for i in (1,2)]


def test_unmodelled_fixture_does_not_abort_successful_peer(monkeypatch):
    first, second = candidates()
    provider = Mock()
    provider.details_by_fixture.return_value = {
        i: fixture(i, NOW+timedelta(hours=5), i*10, i*10+1) for i in (1,2)}
    monkeypatch.setattr('football_model_refresh.scan_daily_challenge', lambda *a, **kw: dict(
        modeled_fixture_ids=[1], discovery_candidates=[first], operational_errors=[], errors=[],
        context_fixture_statuses={'1':'verified'}, riskobet_source_candidates=[first]))
    before = deepcopy(second.to_dict())
    result = refresh_fixture_models(provider,[first,second],NOW.date(),now=NOW)
    assert result['model_refresh']['fixture_ids'] == [1]
    assert result['unmodeled_fixture_ids'] == [2]
    assert result['candidates'] == [first]
    assert len(result['operational_errors']) == 1
    assert second.to_dict() == before


def test_late_confirmed_cancellation_is_not_reported_as_model_failure(monkeypatch):
    first,second=candidates()
    provider=Mock()
    provider.details_by_fixture.return_value={
        i:fixture(i,NOW+timedelta(hours=5),i*10,i*10+1) for i in (1,2)}
    monkeypatch.setattr('football_model_refresh.scan_daily_challenge',lambda *a,**kw:dict(
        modeled_fixture_ids=[1,2],invalidated_fixture_ids=[2],operational_errors=[],errors=[],
        discovery_candidates=[first,second],riskobet_source_candidates=[first,second]))
    result=refresh_fixture_models(provider,[first,second],NOW.date(),now=NOW)
    assert result['model_refresh']['fixture_ids']==[1]
    assert result['unmodeled_fixture_ids']==[] and result['invalidated_fixture_ids']==[2]
    assert result['candidates']==[first] and result['riskobet_source_candidates']==[first]


def test_entire_unmodelled_batch_reports_failure_without_fresh_model_clocks(monkeypatch):
    first,second=candidates()
    provider=Mock()
    provider.details_by_fixture.return_value={
        i:fixture(i,NOW+timedelta(hours=5),i*10,i*10+1) for i in (1,2)}
    monkeypatch.setattr('football_model_refresh.scan_daily_challenge',lambda *a,**kw:dict(
        modeled_fixture_ids=[],operational_errors=[],errors=[],discovery_candidates=[]))
    result=refresh_fixture_models(provider,[first,second],NOW.date(),now=NOW)
    assert result['model_refresh']['fixture_ids']==[]
    assert result['unmodeled_fixture_ids']==[1,2] and len(result['operational_errors'])==2
    assert result['candidates']==[]


def state_and_result():
    old = candidates()
    records = [_football_candidate_record(c,context_checked_at=NOW-timedelta(hours=2)) for c in old]
    state = dict(status='completed', candidates=deepcopy(records), basis_candidates=deepcopy(records), errors=[],
        discovery_candidates=[_challenge_candidate_payload(c) for c in old],
        riskobet_source_candidates=[_challenge_candidate_payload(c) for c in old],
        riskobet_context_checked_fixture_ids=[1,2], context_checks={},
        model_checks={str(i):records[i-1]['modeled_at'] for i in (1,2)},
        last_discovery_at=records[0]['modeled_at'], context_accounting_available=True,
        context_fixture_statuses={'1':'verified','2':'verified'})
    new = replace(old[0], probability=.78,expected_home_goals=1.9)
    result = dict(candidates=[new],wettfinder_candidates=[new],riskobet_source_candidates=[new],
        riskobet_context_checked_fixture_ids=[1],context_fixture_statuses={'1':'verified'},
        basis_forecasts=[],unmodeled_fixture_ids=[2],errors=['Fixture 2 model unavailable'],
        operational_errors=['Fixture 2 model unavailable'],
        model_refresh=dict(version=MODEL_REFRESH_VERSION,fixture_ids=[1],
                           modeled_at=NOW.isoformat(),input_cutoff_at=NOW.isoformat()))
    return state,result


def test_partial_merge_preserves_failed_game_in_every_pool_and_its_original_clocks():
    state,result = state_and_result()
    before = deepcopy(state)
    actual = _merge_context_refresh(state,result,fixture_ids=[1,2],checked_at=NOW)
    for name in ('candidates','basis_candidates','discovery_candidates','riskobet_source_candidates'):
        assert [r for r in actual[name] if r['fixture_id']==2] == [r for r in before[name] if r['fixture_id']==2]
    assert actual['model_checks']['2'] == before['model_checks']['2']
    assert actual['model_checks']['1'] == NOW.isoformat()
    assert actual['model_refresh_failed_fixture_ids'] == [2]
    assert actual['context_checks']['2'] == NOW.isoformat()  # attempt, NOT a new model
    assert actual['status'] == 'degraded' and actual['operational_error_count'] == 1
    assert state == before


def test_later_successful_batch_cannot_hide_pending_model_failure_and_repair_clears_it():
    state,result = state_and_result()
    first = _merge_context_refresh(state,result,fixture_ids=[1,2],checked_at=NOW)
    successful = {**result,'unmodeled_fixture_ids':[],'errors':[],'operational_errors':[]}
    next_run = _merge_context_refresh(first,successful,fixture_ids=[1],checked_at=NOW)
    assert next_run['status']=='degraded' and next_run['operational_error_count']==1
    second = candidates()[1]
    repaired = {**successful,'candidates':[second],'wettfinder_candidates':[second],
                'riskobet_source_candidates':[second], 'riskobet_context_checked_fixture_ids':[2],
                'context_fixture_statuses':{'2':'verified'},
                'model_refresh':{**result['model_refresh'],'fixture_ids':[2]}}
    final = _merge_context_refresh(next_run,repaired,fixture_ids=[2],checked_at=NOW)
    assert final['model_refresh_failed_fixture_ids']==[]
    assert final['operational_error_count']==0 and final['status']=='completed'


@pytest.mark.parametrize('change',[
    {'unmodeled_fixture_ids':[1,2]}, {'unmodeled_fixture_ids':[2,99]},
    {'unmodeled_fixture_ids':[True]}, {'unmodeled_fixture_ids':[2,2]},
    {'unmodeled_fixture_ids':[]}, {'operational_errors':[]},
    {'invalidated_fixture_ids':[1]}, {'invalidated_fixture_ids':[99]},
])
def test_partial_accounting_cannot_overlap_escape_scope_or_claim_success(change):
    state,result=state_and_result()
    with pytest.raises(ValueError):
        _merge_context_refresh(state,{**result,**change},fixture_ids=[1,2],checked_at=NOW)


def test_unmodelled_fixture_cannot_supply_fresh_candidates():
    state,result=state_and_result()
    result['candidates'].append(candidates()[1])
    with pytest.raises(ValueError):
        _merge_context_refresh(state,result,fixture_ids=[1,2],checked_at=NOW)
