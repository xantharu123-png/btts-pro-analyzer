"""Real same-call results, not prose or synthetic consumer rows."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

import team_customer_facts as facts_api
from sports_prematch import predict_prematch
from test_sports_prematch import NOW, event, history


def capture(sport='ice_hockey', rows=None):
    target = event(sport, source_observed_at=NOW.isoformat())
    rows = history(sport) if rows is None else rows
    captures = []
    prediction = predict_prematch(sport, target, rows, NOW, original_capture=captures.append)
    return target, captures[0], prediction


def forecast(target, prediction):
    return dict(sport=prediction.sport, provider=target['provider'],
        provider_event_id=target['provider_event_id'], home_id=target['home_team_id'],
        away_id=target['away_team_id'], home=target['home_team'], away=target['away_team'],
        starts_at=target['starts_at'], modeled_at=NOW.isoformat(),
        model_input_hash=prediction.input_hash,
        model_scope='including_overtime_shootout' if prediction.sport == 'ice_hockey' else 'including_overtime',
        home_games=prediction.home_games, away_games=prediction.away_games,
        latest_result_observed_at=prediction.latest_result_observed_at)


@pytest.mark.parametrize('sport', ['basketball', 'ice_hockey'])
def test_real_capture_transports_ten_unique_clock_bound_final_results(sport):
    target, original, prediction = capture(sport)
    before = deepcopy(original.raw_history)
    facts = facts_api.team_recent_facts(original)
    assert facts['schema'] == 'team-recent-results-v2'
    assert facts['provider'] == target['provider']
    assert facts['competition'] == target['competition']
    assert facts['starts_at'] == target['starts_at']
    assert facts['competitor_a_id'] == '1' and facts['competitor_b_id'] == '8'
    assert facts['input_cutoff_at'] == NOW.isoformat()
    assert original.raw_history == before
    for side in ('a_results', 'b_results'):
        assert len(facts[side]) == 10
        assert len({r['event_id'] for r in facts[side]}) == 10
        assert [r['start'] for r in facts[side]] == sorted((r['start'] for r in facts[side]), reverse=True)
        assert all(r['result_observed_at'] < facts['input_cutoff_at'] for r in facts[side])
        assert all(type(r['won']) is bool and r['score'] and r['opponent_id'] for r in facts[side])
    if sport == 'ice_hockey':
        # match-57 is an actual 2:1 SO final, whose model inputs are 1:1.
        row = next(r for r in facts['a_results'] if r['event_id'] == 'match-57')
        assert row['score'] == '2:1' and row['won'] is True
    checked = facts_api.validate_team_recent_results(facts, forecast(target, prediction),
        competition=target['competition'], input_cutoff_at=NOW)
    assert checked == facts


def test_raw_metadata_requires_provider_scope_and_participant_binding():
    target, original, prediction = capture()
    real = facts_api.team_recent_facts(original)
    top_id = real['a_results'][0].get('event_id', 'match-83')
    for field, value in [('provider', 'Wrong'), ('competition', 'Wrong'),
                         ('game_type', 3), ('home_team_id', '999'),
                         ('winner_side', 'away')]:
        raw = deepcopy(original.raw_history)
        for row in raw:
            if row['provider_event_id'] == top_id:
                row[field] = value
        altered = replace(original, raw_history=raw)
        result = facts_api.team_recent_facts(altered)['a_results'][0]
        assert result['score'] is None and result['opponent'] is None
        assert result['won'] is True and result['start'] == real['a_results'][0]['start']


@pytest.mark.parametrize('field,value', [
    ('sport', 'basketball'), ('provider', 'ESPN'), ('competition', 'NBA'),
    ('provider_event_id', 'wrong'), ('competitor_a_id', '999'),
    ('competitor_a', 'Other'), ('source_input_hash', 'a'*64),
    ('starts_at', (NOW + timedelta(days=1)).isoformat()),
    ('modeled_at', (NOW + timedelta(seconds=1)).isoformat()),
    ('input_cutoff_at', (NOW + timedelta(seconds=1)).isoformat()),
    ('scope', 'regulation'), ('extra', 'unclosed'),
])
def test_wrong_envelope_cannot_bind_to_forecast(field, value):
    target, original, prediction = capture()
    facts = facts_api.team_recent_facts(original)
    facts[field] = value
    with pytest.raises(ValueError):
        facts_api.validate_team_recent_results(facts, forecast(target, prediction),
            competition='NHL', input_cutoff_at=NOW)


@pytest.mark.parametrize('field,value', [
    ('won', 1), ('team_identity', 'id:999'), ('opponent_identity', 'id:1'),
    ('opponent_id', '999'), ('event_id', 'future-match'), ('scope', 'regulation'),
    ('result_observed_at', NOW.isoformat()), ('start', NOW.isoformat()),
    ('score', '1:5'), ('score', '2:2'), ('opponent', ''), ('extra', 1),
])
def test_malformed_or_contradictory_result_is_rejected(field, value):
    target, original, prediction = capture()
    facts = facts_api.team_recent_facts(original)
    facts['a_results'][0][field] = value
    with pytest.raises(ValueError):
        facts_api.validate_team_recent_results(facts, forecast(target, prediction))


def test_duplicate_unordered_overlong_rows_are_rejected():
    target, original, prediction = capture()
    for transform in (lambda rows: rows + [rows[0]],
                      lambda rows: [rows[0], rows[0]],
                      lambda rows: list(reversed(rows))):
        facts = facts_api.team_recent_facts(original)
        facts['a_results'] = transform(facts['a_results'])
        with pytest.raises(ValueError):
            facts_api.validate_team_recent_results(facts, forecast(target, prediction))


def test_optional_missing_details_stay_missing_and_nested_evidence_is_owned():
    target, original, prediction = capture()
    facts = facts_api.team_recent_facts(original)
    for row in facts['a_results']:
        row.update(score=None, opponent=None, opponent_id=None)
    frozen = facts_api.freeze_team_recent_results(facts, forecast(target, prediction))
    facts['a_results'][0]['won'] = False
    assert frozen['a_results'][0]['won'] is True
    assert frozen['a_results'][0]['score'] is None
    with pytest.raises(TypeError):
        frozen['a_results'][0]['won'] = False


def test_future_retraction_and_duplicate_alias_do_not_create_form_results():
    rows = history()
    correction = {**rows[-1], 'status': 'retracted',
        'result_observed_at': (NOW - timedelta(seconds=1)).isoformat()}
    alias = {**rows[-2], 'provider_event_id': 'alias'}
    future = {**rows[-3], 'provider_event_id': 'future-result',
        'result_observed_at': NOW.isoformat()}
    target, original, prediction = capture(rows=rows + [correction, alias, future])
    facts = facts_api.team_recent_facts(original)
    ids = {r['event_id'] for side in ('a_results', 'b_results') for r in facts[side]}
    assert 'match-83' not in ids and 'future-result' not in ids
    assert not {'alias', 'match-82'} <= ids
    assert facts_api.validate_team_recent_results(facts, forecast(target, prediction)) == facts


def test_new_typed_contract_reaches_customer_explanation_without_prose_fallback():
    from types import SimpleNamespace
    target, original, prediction = capture()
    facts = facts_api.team_recent_facts(original)
    basis = {**forecast(target, prediction), 'model_version': 'sports-prematch-research-v1',
        'p_home': prediction.p_home, 'p_away': prediction.p_away,
        'missing': [], 'factors': list(prediction.factors)}
    signal = SimpleNamespace(sport='Eishockey', probability=prediction.p_home,
        competitor_a='Team 1', competitor_b='Team 8', selected_competitor='Team 1',
        provider_event_id='future-match', modeled_at=NOW.isoformat(),
        fixture_source='NHL', competition='NHL', team_sport_snapshot={
            'competition': 'NHL', 'input_cutoff_at': NOW.isoformat(),
            'team_sport_forecast': basis, 'customer_recent_results': facts})
    recent = facts_api.team_customer_explanation(signal)['recent']
    assert len(recent) == 2
    assert 'Team 8' in recent[0] and '4:2' in recent[0]
    facts['a_results'][0]['won'] = False
    assert facts_api.team_customer_explanation(signal)['recent'] == ()
