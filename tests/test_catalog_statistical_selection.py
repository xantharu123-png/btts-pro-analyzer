"""Regression: market skill chooses the scenario before display probabilities."""
from copy import deepcopy
from itertools import permutations

import pytest

from betting_math import BETTING_POLICY_VERSION
from challenge_engine import MARKET_SPECS
from ev_signal_sources import automated_wettfinder_forecasts
from forecast_selection import select_consumer_forecasts
from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced
from test_wettfinder_automation import _bind_football_model_revision, _football_model_row
from wettfinder_automation import build_daily_forecast_catalog
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog


def row(key, probability, *, skill=.05):
    value = _football_model_row(key, fixture_id=1, market_key=key,
                               is_basic_forecast=False, probability=probability)
    _bind_football_model_revision(value)
    value['selection_rank'] = [skill, 80., skill / .8, -1., -5., probability - .05]
    return value


def catalog(rows):
    return build_daily_forecast_catalog(rows, [], now=NOW, target_date=NOW.date())


def test_ilves_complete_revision_retains_modal_home_before_broad_cover_selection():
    # Live 2026-10-17 marginal probabilities, not invented independent events.
    # Reintroducing the cross-family raw-p ordering drops HOME for DC_X2.
    rows = [row(key, p) for key, p in (
        ('RESULT_HOME', .486390), ('RESULT_AWAY', .251021),
        ('DC_1X', .748979), ('DC_X2', .513610),
        ('TOTAL_UNDER_4_5', .889489), ('HOME_UNDER_2_5', .818604))]
    original = deepcopy(rows)
    for ordered in permutations(rows):
        selected = catalog(ordered)
        assert {item['market_key'] for item in selected} == {
            'RESULT_HOME', 'DC_1X', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
    assert rows == original


def test_lower_marginal_better_statistical_market_defeats_conflicting_broad_cover():
    # Exact different lines; this is skill choice, not a direction comparison.
    supported = row('TOTAL_OVER_2_5', .61, skill=.12)
    broad = row('TOTAL_UNDER_1_5', .85, skill=.01)
    for ordered in ((supported, broad), (broad, supported)):
        assert [item['market_key'] for item in catalog(ordered)] == ['TOTAL_OVER_2_5']


@pytest.mark.parametrize('rank', [None, [], [.9] * 5, [True] * 6,
    [float('nan')] * 6, [float('inf')] * 6, [10 ** 1000] * 6, ['.9'] * 6])
def test_malformed_statistical_rank_cannot_displace_supported_market(rank):
    strong = row('TOTAL_OVER_2_5', .61, skill=.12)
    malformed = {**row('TOTAL_UNDER_1_5', .85), 'selection_rank': rank}
    for ordered in ((strong, malformed), (malformed, strong)):
        assert [item['market_key'] for item in catalog(ordered)] == ['TOTAL_OVER_2_5']


def test_row_without_publication_key_cannot_suppress_valid_market():
    strong = row('TOTAL_OVER_2_5', .61, skill=.12)
    malformed = row('TOTAL_UNDER_1_5', .85, skill=.20)
    malformed.pop('key')
    assert [item['market_key'] for item in catalog([malformed, strong])] == ['TOTAL_OVER_2_5']


@pytest.mark.parametrize('spec', MARKET_SPECS, ids=lambda spec: spec.key)
def test_no_supported_market_is_categorically_excluded(spec):
    assert [item['market_key'] for item in catalog([row(spec.key, .57)])] == [spec.key]


@pytest.mark.parametrize('strong_key,weak_key', [
    ('RESULT_HOME', 'DC_X2'),
    ('DC_12', 'TOTAL_UNDER_0_5'),
    ('BTTS_YES', 'TOTAL_UNDER_1_5'),
    ('TOTAL_OVER_3_5', 'RESULT_TOTAL_1X_UNDER_3_5'),
    ('HOME_OVER_2_5', 'TOTAL_UNDER_2_5'),
    ('HOME_RANGE_1_3', 'TOTAL_UNDER_0_5'),
    ('HOME_RANGE_2_4', 'TOTAL_UNDER_1_5'),
    ('AWAY_RANGE_1_3', 'TOTAL_UNDER_0_5'),
    ('AWAY_RANGE_2_4', 'TOTAL_UNDER_1_5'),
    ('RESULT_TOTAL_12_OVER_1_5', 'TOTAL_UNDER_1_5'),
    ('MIXED_BTTS_OR_OVER_2_5', 'TOTAL_UNDER_0_5'),
    ('CORNERS_UNDER_5_5', 'HOME_CORNERS_OVER_5_5'),
    ('HOME_CORNERS_OVER_5_5', 'CORNERS_UNDER_5_5'),
    ('YELLOW_UNDER_1_5', 'HOME_YELLOW_OVER_1_5'),
    ('HOME_YELLOW_OVER_1_5', 'YELLOW_UNDER_1_5'),
])
def test_each_supported_family_can_defeat_a_lower_skill_conflicting_cover(strong_key, weak_key):
    # Hand-checked disjoint predicates. In particular 0 total goals cannot
    # coexist with 1-3/2-4 home or away goals. Do not derive expectations from
    # the production conflict helper: a broken helper must fail these tests.
    strong, weak = row(strong_key, .57, skill=.14), row(weak_key, .87, skill=.01)
    for ordered in ((strong, weak), (weak, strong)):
        assert [item['market_key'] for item in catalog(ordered)] == [strong_key]


@pytest.mark.parametrize('over', [spec for spec in MARKET_SPECS
    if spec.side and spec.side.endswith('over') and spec.kind in {
        'total', 'team_total', 'corner_total', 'team_corners', 'yellow_total', 'team_yellow'}],
    ids=lambda spec: spec.key)
def test_exact_opposing_line_uses_probability_before_statistical_market_rank(over):
    under_key = over.key.replace('_OVER_', '_UNDER_')
    stronger_direction = row(under_key, .76, skill=.01)
    weaker_direction = row(over.key, .24, skill=.20)
    for ordered in ((stronger_direction, weaker_direction), (weaker_direction, stronger_direction)):
        assert [item['market_key'] for item in catalog(ordered)] == [under_key]


def test_statistical_choice_is_jointly_coherent_not_only_pairwise_possible():
    rows = [row('TOTAL_UNDER_2_5', .70, skill=.12),
            row('HOME_OVER_0_5', .80, skill=.10),
            row('AWAY_OVER_1_5', .85, skill=.01)]
    for ordered in permutations(rows):
        assert {item['market_key'] for item in catalog(ordered)} == {
            'TOTAL_UNDER_2_5', 'HOME_OVER_0_5'}


@pytest.mark.parametrize('range_key,home_key,away_key', [
    ('TOTAL_RANGE_1_3', 'HOME_OVER_1_5', 'AWAY_OVER_1_5'),
    ('TOTAL_RANGE_1_4', 'HOME_OVER_2_5', 'AWAY_OVER_1_5'),
    ('TOTAL_RANGE_2_4', 'HOME_OVER_2_5', 'AWAY_OVER_1_5'),
])
def test_total_multigoal_range_participates_in_joint_goal_constraints(range_key, home_key, away_key):
    # Each pair is possible, but the two team lower bounds exceed the total
    # range's inclusive upper bound when all three predicates are combined.
    rows = [row(range_key, .65, skill=.15), row(home_key, .72, skill=.10),
            row(away_key, .80, skill=.01)]
    for ordered in permutations(rows):
        assert {item['market_key'] for item in catalog(ordered)} == {range_key, home_key}


def ilves_rows(home_price=1.12):
    rows = []
    for key, probability in (
        ('RESULT_HOME', .486390), ('RESULT_AWAY', .251021),
        ('DC_1X', .748979), ('DC_X2', .513610),
        ('TOTAL_UNDER_4_5', .889489), ('HOME_UNDER_2_5', .818604)):
        signal = priced(football(key=key, probability=probability),
                        (home_price,) * 3 if key == 'RESULT_HOME' else (1.80,) * 3)
        value = {**vars(signal), 'source': 'football_challenge',
                 'home_id': signal.home_team_id, 'away_id': signal.away_team_id,
                 'event_identity': 'football:1', 'event': signal.event_label,
                 'status': 'PRICE_REQUIRED', 'policy_version': BETTING_POLICY_VERSION,
                 'conservative_probability': probability - signal.probability_haircut,
                 'selection_rank': [.05, 80., .0625, -1., -8., probability - .08]}
        value.pop('context_ref')  # Production omits absent references, not null.
        rows.append(value)
    return rows


@pytest.mark.parametrize('home_price', [1.12, 1.80])
def test_ilves_catalog_survives_real_reader_cards_and_low_price_does_not_flip_direction(tmp_path, home_price):
    rows = ilves_rows(home_price)
    before = deepcopy(rows)
    chosen = catalog(rows)
    document = {'model_candidates': chosen, 'football': {
        'context_accounting_available': True, 'context_fixture_statuses': {'1': 'verified'},
        'base_fixture_count': 1, 'context_verified_fixtures': 1,
        'context_data_incomplete_fixtures': 0, 'context_unchecked_fixtures': 0,
        'deferred_context_fixtures': 0, 'context_fixtures': 1, 'context_scope_complete': True}}
    forecasts = automated_wettfinder_forecasts(tmp_path / 'wettfinder.json', now=NOW,
                                              _loaded=(document, NOW, []))
    assert {s.market_key for s in forecasts} == {
        'RESULT_HOME', 'DC_1X', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
    assert {s.market_key for s in select_consumer_forecasts(forecasts, now=NOW)} == {
        'RESULT_HOME', 'DC_1X', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
    cards = [build_wettfinder_card(s, s.reference_quote, now=NOW) for s in forecasts]
    public = compose_wettfinder_catalog(cards)
    visible = {card.market_key for card in public.featured + public.additional}
    assert visible == ({'DC_1X', 'TOTAL_UNDER_4_5', 'HOME_UNDER_2_5'}
                       | ({'RESULT_HOME'} if home_price >= 1.20 else set()))
    assert rows == before
