"""Inclusive, price-free multigoals and exact future provider range contracts."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import math
import subprocess
import sys
from types import ModuleType

import pytest

import challenge_engine as engine
import football_joint_calibration as joint
from market_consensus import exact_market_target, parse_fixture_consensus, quote_matches_candidate
from tests.test_football_original_capture import values, calibration


NEW_KEYS = {'TOTAL_RANGE_1_3', 'TOTAL_RANGE_1_4', 'TOTAL_RANGE_2_4', 'TOTAL_RANGE_2_3',
            'HOME_RANGE_1_4', 'AWAY_RANGE_1_4'}


@pytest.mark.parametrize('key,score,want', [
    ('TOTAL_RANGE_1_4', (0, 0), False), ('TOTAL_RANGE_1_4', (1, 0), True),
    ('TOTAL_RANGE_1_4', (1, 2), True), ('TOTAL_RANGE_1_4', (2, 2), True),
    ('TOTAL_RANGE_1_4', (2, 3), False), ('TOTAL_RANGE_1_3', (2, 2), False),
    ('TOTAL_RANGE_2_4', (1, 0), False), ('TOTAL_RANGE_2_4', (1, 1), True),
    ('HOME_RANGE_1_4', (0, 4), False), ('HOME_RANGE_1_4', (4, 0), True),
    ('AWAY_RANGE_1_4', (4, 0), False), ('AWAY_RANGE_1_4', (0, 4), True),
    ('HOME_RANGE_1_4', (5, 0), False), ('AWAY_RANGE_1_4', (0, 5), False),
])
def test_inclusive_range_settlement_does_not_mix_total_and_team(key, score, want):
    assert key in engine.MARKET_BY_KEY
    assert engine.market_outcome(engine.MARKET_BY_KEY[key], *score) is want


def test_range_marginal_is_the_hand_summed_joint_mass_not_independent_approximation():
    assert NEW_KEYS <= engine.MARKET_BY_KEY.keys()
    raw = {(0, 0): .1, (1, 0): .2, (0, 3): .3, (2, 2): .15, (5, 0): .25}
    assert engine.market_probability(raw, engine.MARKET_BY_KEY['TOTAL_RANGE_1_4']) == pytest.approx(.65)
    assert engine.market_probability(raw, engine.MARKET_BY_KEY['TOTAL_RANGE_1_3']) == pytest.approx(.5)
    assert engine.market_probability(raw, engine.MARKET_BY_KEY['HOME_RANGE_1_4']) == pytest.approx(.35)


def test_extended_catalog_projects_same_calibrated_q_without_changing_old_market_bytes(monkeypatch):
    assert NEW_KEYS <= engine.MARKET_BY_KEY.keys()
    fixture, history = values()
    curves = calibration()
    model = engine.fixture_market_probabilities(fixture, history, curves)
    # Compare the actual pre-extension v14 sources in this SAME numerical
    # runtime. A cross-runtime SLSQP/BLAS output hash is not a source baseline.
    revision = '6c106d56dea4b09da4b448dad3ef064ce4b6d826'
    sources = {name: subprocess.check_output(['git', 'show', f'{revision}:{name}.py'])
               for name in ('challenge_engine', 'football_joint_calibration')}
    with monkeypatch.context() as patch:
        modules = {name: ModuleType(name) for name in sources}
        for name, module in modules.items():
            module.__file__ = sys.modules[name].__file__
            patch.setitem(sys.modules, name, module)
        for name, module in modules.items():
            exec(compile(sources[name], f'<git:{revision}:{name}.py>', 'exec'), module.__dict__)
        previous = modules['challenge_engine']
        assert previous.CHALLENGE_PREDICTION_VERSION == 'challenge-engine:coherent-joint-calibration-v14'
        previous_curves = {spec.key: previous.MarketCalibration(curves[spec.key].points, curves[spec.key].samples)
                           for spec in previous.MARKET_SPECS if spec.key in curves}
        baseline = previous.fixture_market_probabilities(fixture, history, previous_curves)
        baseline_keys = {spec.key for spec in previous.MARKET_SPECS}
    old = {k: v for k, v in model['probabilities'].items() if k not in NEW_KEYS}
    assert len(baseline_keys) == 90
    assert set(old) == set(baseline['probabilities']) == baseline_keys
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert canonical(old) == canonical(baseline['probabilities'])
    assert canonical(model['distribution_capture']['families']['goals']) == canonical(
        baseline['distribution_capture']['families']['goals'])
    assert len(model['probabilities']) == 96
    assert all(math.isfinite(p) and 0 <= p <= 1 for ps in model['probabilities'].values() for p in ps)
    for index, variant in enumerate(('active', 'season', 'form')):
        cells = model['distribution_capture']['families']['goals'][variant]['effective_cells']
        want = math.fsum(p for h, a, p in cells if 1 <= h+a <= 4)
        assert model['probabilities']['TOTAL_RANGE_1_4'][index] == pytest.approx(want, abs=1e-14)
        assert model['probabilities']['TOTAL_RANGE_1_3'][index] <= want
        assert model['probabilities']['TOTAL_RANGE_2_4'][index] <= want
        for side in ('HOME', 'AWAY'):
            assert model['probabilities'][side+'_RANGE_1_3'][index] <= model['probabilities'][side+'_RANGE_1_4'][index]


@pytest.mark.parametrize('law', [joint.LEGACY_LAW_VERSION, joint.LAW_VERSION])
def test_new_range_curve_cannot_refit_an_immutable_legacy_law(law):
    assert NEW_KEYS <= engine.MARKET_BY_KEY.keys()
    raw = {(0, 0): .6, (1, 0): .4}
    legacy = engine.GOAL_MARKET_SPECS
    base = {'RESULT_HOME': lambda p: p+.1}
    old, _ = joint.calibrate_joint_distribution(raw, legacy, base, law_version=law)
    extended, _ = joint.calibrate_joint_distribution(raw, engine.GOAL_PROJECTION_MARKET_SPECS,
        {**base, 'TOTAL_RANGE_1_4': lambda p: .99}, law_version=law)
    assert extended == old


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def candidate(key='TOTAL_RANGE_1_4'):
    return {'candidate_id': '42:'+key, 'fixture_id': 42, 'market_key': key,
            'sport': 'Fussball', 'source': 'football_challenge', 'selection': '1-4 Tore',
            'scheduled_start': '2030-01-01T16:00:00+00:00'}


def payload(name='Total Goals Number By Ranges', value='1-4', bet_id=186, odd='1.25'):
    return {'errors': [], 'response': [{'fixture': {'id': 42, 'date': '2030-01-01T16:00:00+00:00'},
        'update': NOW.isoformat(), 'bookmakers': [{'id': 1, 'name': 'Example Book', 'bets': [
            {'id': bet_id, 'name': name, 'values': [{'value': value, 'odd': odd}]}]}]}]}


@pytest.mark.parametrize('key,name,bet_id', [
    ('TOTAL_RANGE_1_4', 'Total Goals Number By Ranges', 186),
    ('TOTAL_RANGE_1_4', 'Number of Goals In Match (Range)', 223),
    ('HOME_RANGE_1_4', 'Home Team Exact Goals Number', 40),
    ('AWAY_RANGE_1_4', 'Away Team Exact Goals Number', 41),
])
def test_only_explicit_future_provider_range_has_a_native_bookmaker_price(key, name, bet_id):
    row = candidate(key)
    quotes = parse_fixture_consensus(payload(name, bet_id=bet_id), [row], fetched_at=NOW)
    assert row['candidate_id'] in quotes
    quote = quotes[row['candidate_id']]
    assert quote.executable_point.odds == 1.25
    assert quote.bookmaker_count == 1
    assert quote_matches_candidate(quote, row)
    assert not quote_matches_candidate(quote, {**row, 'selection': '1-3 Tore'})
    assert not quote_matches_candidate(quote, {**row, 'selection': '4-1 Tore'})
    assert not quote_matches_candidate(quote, {**row, 'selection': '1-4 Tore erste Halbzeit'})
    assert not quote_matches_candidate(quote, {**row, 'scheduled_start': '2030-01-01T18:00:00+00:00'})
    assert not quote_matches_candidate(replace(quote, source='unknown'), row)
    assert not quote_matches_candidate(quote, {key: value for key, value in row.items() if key != 'selection'})


@pytest.mark.parametrize('name,value,bet_id', [
    ('Total Goals Number By Ranges - First Half', '1-4', 186),
    ('Total Goals Number By Ranges', '4-1', 186),
    ('Total Goals Number By Ranges', '1+', 186),
    ('Total Goals Number By Ranges', '1-4', 40),
    ('Home Team Exact Goals Number', '1-4', 40),
    ('Correct Score', '1-4', 10), ('Goals Over/Under', 'Over 0.5', 5),
    ('Total Goals Number By Ranges', '1-4 First Half', 186),
])
def test_wrong_period_source_side_and_nonliteral_values_never_create_range_quotes(name, value, bet_id):
    assert not parse_fixture_consensus(payload(name, value, bet_id), [candidate()], fetched_at=NOW)


def test_individual_exact_counts_or_open_ended_values_are_never_aggregated_into_a_range_price():
    data = payload('Home Team Exact Goals Number', bet_id=40)
    data['response'][0]['bookmakers'][0]['bets'][0]['values'] = [
        {'value': value, 'odd': '2.00'} for value in ('0', '1', '2', '3', '4', 'more 3', 'more 4')]
    assert not parse_fixture_consensus(data, [candidate('HOME_RANGE_1_4')], fetched_at=NOW)


@pytest.mark.parametrize('odds,want', [('1.19', True), ('1.20', False), ('1.25', False)])
def test_range_publication_floor_uses_the_exact_native_offer(odds, want):
    from market_consensus import quote_below_publication_floor
    row = candidate()
    quote = parse_fixture_consensus(payload(odd=odds), [row], fetched_at=NOW)[row['candidate_id']]
    assert quote_below_publication_floor(quote, candidate=row, now=NOW) is want
    assert not quote_below_publication_floor(quote, candidate={**row, 'selection': '2-4 Tore'}, now=NOW)


def test_range_quotes_keep_exact_literal_endpoints_and_current_provider_clock():
    row = candidate()
    quote = parse_fixture_consensus(payload(value='1 – 4'), [row], fetched_at=NOW)[row['candidate_id']]
    assert quote.value_name == '1-4'
    stale = payload()
    stale['response'][0]['update'] = (NOW-timedelta(hours=3)).isoformat()
    assert not parse_fixture_consensus(stale, [row], fetched_at=NOW)


def test_total_range_customer_facts_use_match_total_and_show_both_failure_tails():
    assert 'TOTAL_RANGE_1_4' in engine.MARKET_BY_KEY
    from forecast_analysis import _contract, _rate_copy
    from football_customer_facts import recent_football_goal_market_facts
    spec = engine.MARKET_BY_KEY['TOTAL_RANGE_1_4']
    contract, counter = _contract(spec, 'Alpha', 'Beta')
    assert contract == '1–4 Tore insgesamt'
    assert counter == 'höchstens 0 Tore oder mindestens 5 Tore insgesamt'
    assert '2,5 Tore insgesamt' in _rate_copy(spec, {'expected_home_goals': 1.5, 'expected_away_goals': 1.0}, 'Alpha', 'Beta')
    rows = [{'scored': h, 'conceded': a, 'played_at': '2030-01-01', 'opponent': 'Other',
             'venue': 'home', 'competition': 'League'} for h, a in [(0, 0), (1, 0), (2, 1), (2, 2), (3, 2)]]
    facts, _ = recent_football_goal_market_facts({'home': rows, 'away': []}, spec, home='Alpha', away='Beta')
    assert facts == (('Alpha-Spiele · 1–4 Tore insgesamt', '3/5 zuletzt'),)


def test_new_range_uses_its_own_chronological_outcomes_and_never_borrows_old_validation():
    from tests.test_calibration import league_history
    from copy import deepcopy
    rows = league_history(cycles=12)
    records = engine._walk_forward_market_records(rows)
    assert len(records) == 96
    assert records['TOTAL_RANGE_1_4']['outcomes']
    assert records['TOTAL_RANGE_1_4']['outcomes'] != records['HOME_RANGE_1_3']['outcomes']
    changed = deepcopy(rows)
    changed[-1]['goals'] = {'home': 0, 'away': 0}
    changed_records = engine._walk_forward_market_records(changed)
    assert changed_records['TOTAL_RANGE_1_4']['probabilities'] == records['TOTAL_RANGE_1_4']['probabilities']
    fixture, history = values()
    old_metric = engine.ValidationMetrics(observations=300, brier_score=.1,
        baseline_brier_score=.2, relative_improvement=.5, expected_calibration_error=.01, passed=True)
    candidates = engine.build_fixture_candidates(fixture, history, {'HOME_RANGE_1_3': old_metric},
        candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER)
    new = next(row for row in candidates if row.market_key == 'TOTAL_RANGE_1_4')
    assert new.validation is None
    assert engine.candidate_is_wettfinder_release_credible(new) is False


def test_total_range_survives_pure_html_analysis_with_exact_counterrisk_and_no_provider_prose():
    from tests.test_forecast_analysis import _row, _basis, _signal
    from forecast_analysis import project_football_analysis, build_forecast_analysis
    from forecast_compact import build_compact_analysis, render_compact_analysis_html
    row = _row('TOTAL_RANGE_1_4', .75)
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    signal = _signal(row)
    analysis = build_forecast_analysis(signal, now=NOW+timedelta(hours=2))
    html = render_compact_analysis_html(build_compact_analysis(signal, analysis, now=NOW+timedelta(hours=2)))
    assert analysis.supported
    assert '2,66 Tore insgesamt' in analysis.basis
    assert 'höchstens 0 Tore oder mindestens 5 Tore insgesamt' in html
    assert 'NEVER DISPLAY PROVIDER REASON' not in html
    assert 'NEVER DISPLAY DETAIL' not in html
