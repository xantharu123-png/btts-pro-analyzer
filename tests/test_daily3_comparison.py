from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from daily3_comparison import baseline_upper, build_market_comparisons
from daily3_selection import daily3_choices
from forecast_selection import select_consumer_forecasts
from test_daily3_selection import NOW, football


def test_wilson_endpoints_and_counts():
    assert baseline_upper(0, 100) == pytest.approx(.0369934982)
    assert baseline_upper(100, 100) == pytest.approx(1)
    assert baseline_upper(50, 100) == pytest.approx(.5961684696)
    for k, n in ((True, 100), (1, False), (101, 100), (-1, 100), (0, 0)):
        with pytest.raises(ValueError):
            baseline_upper(k, n)


def test_model_disagreement_cannot_be_hidden_by_high_active_probability():
    s = football(probability=.95, variants=(.95, .69, .90))
    assert daily3_choices([s], now=NOW) == ()
    assert select_consumer_forecasts([s], now=NOW) == [s]


def test_missing_comparison_does_not_rewrite_or_remove_normal_forecast():
    s = football(probability=.98, comparison=False)
    assert daily3_choices([s], now=NOW) == ()
    assert select_consumer_forecasts([s], now=NOW) == [s]
    assert s.probability == .98


@pytest.mark.parametrize('key', ['HOME_OVER_0_5', 'AWAY_UNDER_2_5', 'HOME_UNDER_1_5'])
def test_no_market_name_ban_and_no_high_probability_ceiling(key):
    s = football(key=key, probability=.95, baseline=.50)
    assert daily3_choices([s], now=NOW)[0].signal is s


@pytest.mark.parametrize('field,value', [
    ('fixture_id', 99), ('home_id', True), ('away_id', 99), ('market_key', 'BTTS_YES'),
    ('scheduled_start', '2031-01-01T00:00:00+00:00'), ('prediction_version', 'wrong'),
    ('validation_prediction_version', 'wrong'), ('model_skill_supported', False),
    ('samples', 199), ('samples', True), ('successes', -1), ('successes', 401),
    ('latest_kickoff', NOW.isoformat()), ('probabilities', [.99, .99, .99]),
    ('probabilities', [.75, float('nan'), .8]), ('probabilities', [.75, True, .8]),
])
def test_wrong_or_insufficient_evidence_cannot_qualify(field, value):
    s = football()
    envelope = deepcopy(s.analysis_evidence)
    envelope['basis']['market_comparison'][field] = value
    assert daily3_choices([replace(s, analysis_evidence=envelope)], now=NOW) == ()


def history_rows():
    return [dict(fixture=dict(id=100+i, date=(NOW-timedelta(days=i+1)).isoformat(), status={'short':'FT'}),
                 league={'id':39}, teams={'home':{'id':10}, 'away':{'id':11}},
                 goals={'home':int(i % 2 == 0), 'away':0}) for i in range(240)]


def target():
    return dict(fixture=dict(id=1, date=(NOW+timedelta(hours=3)).isoformat()), league={'id':39},
                teams={'home':{'id':2}, 'away':{'id':3}})


def build(rows):
    from test_challenge_market_eligibility import _credible_metric
    return build_market_comparisons(target(), rows, {'HOME_OVER_0_5':(.8,.75,.78)},
        {'HOME_OVER_0_5':_credible_metric()}, prediction_version=_credible_metric().prediction_version, as_of=NOW)


def test_baseline_uses_only_unique_completed_same_league_past_matches():
    rows = history_rows()
    baseline = build(rows)['HOME_OVER_0_5']
    future, other, ongoing, overtime = (deepcopy(rows[0]) for _ in range(4))
    future['fixture']['date'] = (NOW+timedelta(minutes=1)).isoformat()
    other['league']['id'] = 140
    ongoing['fixture']['status']['short'] = '2H'
    overtime['fixture']['status']['short'] = 'AET'
    actual = build(rows + rows + [future, other, ongoing, overtime])['HOME_OVER_0_5']
    assert actual == baseline
    assert actual['samples'] == 240 and actual['successes'] == 120
    assert actual['probabilities'] == [.8,.75,.78]


def test_conflicting_duplicate_does_not_supply_a_comparison():
    rows = history_rows()
    changed = deepcopy(rows[0])
    changed['goals']['home'] = 0
    assert build(rows+[changed]) == {}


def test_incomplete_history_rows_do_not_break_the_normal_model_run():
    rows = history_rows()
    malformed = [None, {}, {'league':None}, {'league':{'id':39}, 'fixture':None}]
    for name, value in [('teams', None), ('teams', {'home':None}), ('goals', None)]:
        row = deepcopy(rows[0])
        row[name] = value
        malformed.append(row)
    assert build(rows+malformed) == build(rows)


def test_comparison_observation_does_not_recalculate_or_change_model_output(monkeypatch):
    from challenge_engine import build_fixture_candidates
    from test_challenge_market_eligibility import _credible_metric
    model = dict(projection_success=True, freshness_days=1., active_lambdas=(1.4,.6),
        venue_samples=(12,12), form_samples=(6,6), probabilities={'HOME_OVER_0_5':(.8,.75,.78)},
        count_models={}, xg_coverage=0.)
    calls = []
    def existing_model(*args, **kwargs):
        calls.append(1)
        return deepcopy(model)
    monkeypatch.setattr('challenge_engine.fixture_market_probabilities', existing_model)
    fixture = target()
    # Real producer clock precedes the test's fixed 2030 historical data.
    from datetime import datetime, timezone
    shift = NOW - datetime.now(timezone.utc)
    rows = history_rows()
    for row in rows:
        row['fixture']['date'] = (datetime.fromisoformat(row['fixture']['date'])-shift).isoformat()
    with_comparison = build_fixture_candidates(fixture, iter(rows), {'HOME_OVER_0_5':_credible_metric()},
                                                candidate_profile='wettfinder')[0].to_dict()
    monkeypatch.setattr('daily3_comparison.build_market_comparisons', lambda *a, **kw: {})
    without = build_fixture_candidates(fixture, iter(rows), {'HOME_OVER_0_5':_credible_metric()},
                                       candidate_profile='wettfinder')[0].to_dict()
    assert with_comparison.pop('market_comparison')['samples'] == 240
    assert with_comparison == without
    assert len(calls) == 2


def test_historical_csv_pseudo_team_ids_are_not_discarded():
    rows = history_rows()
    for row in rows:
        row['teams']['home']['id'] = -100
        row['teams']['away']['id'] = -101
    assert build(rows)['HOME_OVER_0_5']['samples'] == 240


def test_comparison_survives_real_candidate_and_public_analysis_serialization():
    import json
    from test_challenge_integrity import _candidate
    from forecast_analysis import read_football_analysis
    c = _candidate(NOW, probability=.8)
    c.probability = .8
    fixture = dict(fixture=dict(id=c.fixture_id, date=c.kickoff), league={'id':c.league_id},
                   teams={'home':{'id':c.home_team_id}, 'away':{'id':c.away_team_id}})
    rows = history_rows()
    for row in rows:
        row['league']['id'] = c.league_id
    c.market_comparison = build_market_comparisons(fixture, rows,
        {c.market_key:(.8,.78,.77)}, {c.market_key:c.validation},
        prediction_version=c.prediction_version, as_of=NOW)[c.market_key]
    payload = c.to_dict()
    assert payload['market_comparison'] == c.market_comparison
    # Store fixed-size aggregates, never another copy of the match history.
    assert len(json.dumps(c.market_comparison).encode()) < 1024
    from wettfinder_automation import _football_candidate_record
    # Projection needs exactly bound metadata, but it never changes the model.
    record = _football_candidate_record(c, context_checked_at=NOW)
    assert record is not None and record['probability'] == .8
    evidence = read_football_analysis(record, now=NOW)
    assert evidence['basis']['market_comparison']['probabilities'] == [.8,.78,.77]


def test_existing_15k_candidate_payload_does_not_gain_a_null_financial_field():
    from test_challenge_integrity import _candidate
    c = _candidate(NOW)
    assert 'market_comparison' not in c.to_dict()
