from dataclasses import replace
from datetime import timedelta
from itertools import permutations

import pytest

from daily3_selection import daily3_choices
from forecast_analysis import build_forecast_analysis
from forecast_selection import select_consumer_forecasts
from test_daily3_selection import NOW, football, tennis
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog, render_compact_row_html


def esports(*, age=0):
    clock = (NOW - timedelta(hours=age)).isoformat()
    return replace(tennis(), key='esports', sport='E-Sport', modeled_at=clock,
        context_evidence={'schema': 'esports-card-basis-v1', 'provider_event_id': 't1',
            'competitor_a': 'Spieler A', 'competitor_b': 'Spieler B', 'modeled_at': clock,
            'elo_a': 1700, 'elo_b': 1500})


def cards(rows):
    return [build_wettfinder_card(s, now=NOW) for s in rows]


def test_frozen_opposing_choices_share_one_scenario_without_price_ranking():
    inputs = [football(key=k, probability=p) for k, p in (
        ('RESULT_AWAY', .195253), ('RESULT_HOME', .551276), ('DC_X2', .454140), ('DC_1X', .806871))]
    original_probabilities = [s.probability for s in inputs]
    for ordering in permutations(inputs):
        for pool in (ordering, tuple(replace(s, minimum_odds=999, evidence_stage='RELEASED') for s in ordering)):
            catalog = compose_wettfinder_catalog(cards(pool))
            choices = daily3_choices(pool, now=NOW)
            keys = {c.market_key for c in catalog.featured + catalog.additional}
            assert 'RESULT_AWAY' not in keys
            assert choices[0].signal.market_key in {'RESULT_HOME', 'DC_1X'}
            assert choices[0].signal.market_key in keys
            assert 'DC_X2' not in keys
            assert 'RESULT_HOME' in keys
    assert [s.probability for s in inputs] == original_probabilities


@pytest.mark.parametrize('signal', [esports(age=14), replace(esports(), modeled_at=None),
    replace(esports(), context_evidence=None)])
def test_unqualified_forecasts_remain_visible_but_never_highlighted(signal):
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert not catalog.featured
    assert [c.key for c in catalog.additional] == [signal.key]
    assert catalog.additional[0].highlight_reason


def test_exact_esports_explanation_is_shared_and_rejects_foreign_evidence():
    signal = esports()
    analysis = build_forecast_analysis(signal, now=NOW)
    assert 'Elo 1700' in analysis.basis
    assert 'Elo 1700' in daily3_choices([signal], now=NOW)[0].basis
    assert len(compose_wettfinder_catalog(cards([signal])).featured) == 1
    for changed in (replace(signal, competitor_a='Foreign'),
                    replace(signal, modeled_at=(NOW-timedelta(minutes=1)).isoformat())):
        assert 'Elo 1700' not in build_forecast_analysis(changed, now=NOW).basis
        assert not compose_wettfinder_catalog(cards([changed])).featured


@pytest.mark.parametrize('kind,label', [('result_date', 'Ergebnisdatum'), ('tournament_start_proxy', 'Turnierstart-Proxy')])
def test_tennis_data_age_is_not_replaced_by_recalculation_time(kind, label):
    signal = tennis()
    context = {**signal.context_evidence, 'model_inputs': {**signal.context_evidence['model_inputs'],
        'stats_through': '2000-01-01', 'stats_through_kind': kind,
        'model_built_at': (NOW-timedelta(days=1)).isoformat(), 'training_cutoff': NOW.isoformat()}}
    signal = replace(signal, context_evidence=context)
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert not catalog.featured
    assert not daily3_choices([signal], now=NOW)
    markup = render_compact_row_html(catalog.additional[0])
    assert '01.01.2000' in markup and label in markup
    assert 'Berechnet' in markup and '2030' in markup
    assert '31.12.2029' in markup  # build date is independent too
    assert 'operative' not in markup and '14 Tage' not in markup


def test_tennis_unknown_data_date_stays_unknown_and_neutral():
    signal = tennis(coverage=False)
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert not catalog.featured
    assert 'Datenstand unbekannt' in render_compact_row_html(catalog.additional[0])


def test_opposing_lower_goal_rate_is_called_out_as_outsider():
    assert 'Außenseiter' in build_forecast_analysis(football(key='RESULT_AWAY', probability=.2), now=NOW).basis


def test_shared_selector_returns_original_objects_and_canonical_probability_ties():
    home, away = football(probability=.4), football(key='RESULT_AWAY', probability=.4)
    for pool in ((home, away), (away, home)):
        selected = select_consumer_forecasts(pool, now=NOW)
        assert len(selected) == 1 and selected[0] is home
        assert select_consumer_forecasts(cards(pool), now=NOW)[0].market_key == 'RESULT_HOME'


@pytest.mark.parametrize('change', [{'model_version': 'other'}, {'policy_version': 'other'},
    {'model_scope': 'other'}, {'home_team_id': 999}])
def test_direction_probabilities_are_not_compared_across_model_or_participant_identity(change):
    # Both neutral objects are equally unsupported. A foreign .95 must not
    # defeat HOME solely through a cross-revision/cross-participant comparison.
    home = replace(football(probability=.2), analysis_evidence=None)
    away = replace(football(key='RESULT_AWAY', probability=.95), analysis_evidence=None, **change)
    for pool in ((home, away), (away, home)):
        selected = select_consumer_forecasts(pool, now=NOW)
        assert selected[0] is home


def test_canonical_clock_compares_equivalent_zones_but_new_revision_wins_by_time():
    home = replace(football(probability=.6), analysis_evidence=None)
    equivalent = replace(football(key='RESULT_AWAY', probability=.8),
        modeled_at='2030-01-01T13:00:00+01:00', analysis_evidence=None)
    assert select_consumer_forecasts([home, equivalent], now=NOW)[0] is equivalent
    older = football(probability=.9, now=NOW-timedelta(minutes=1))
    newer = football(key='RESULT_AWAY', probability=.2)
    assert select_consumer_forecasts([older, newer], now=NOW)[0] is newer
    assert select_consumer_forecasts([newer, older], now=NOW)[0] is newer


def test_stale_or_unexplained_opponent_cannot_anchor_a_supported_current_direction():
    home = football(probability=.3)
    stale = football(key='RESULT_AWAY', probability=.9, now=NOW-timedelta(hours=3))
    unsupported = replace(football(key='RESULT_AWAY', probability=.9), analysis_evidence=None)
    for opposite in (stale, unsupported):
        assert select_consumer_forecasts([opposite, home], now=NOW)[0] is home
        assert compose_wettfinder_catalog(cards([opposite, home])).featured[0].market_key == 'RESULT_HOME'


@pytest.mark.parametrize('key', ['HOME_OVER_0_5', 'AWAY_OVER_0_5', 'HOME_UNDER_1_5', 'AWAY_UNDER_1_5'])
def test_simple_markets_remain_in_both_consumer_pools(key):
    signal = football(key=key)
    assert select_consumer_forecasts([signal], now=NOW)[0] is signal
    assert daily3_choices([signal], now=NOW)[0].signal is signal
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert (catalog.featured + catalog.additional)[0].market_key == key


def test_complete_pool_precedes_occupied_slots_and_pagination():
    home, away = football(probability=.6), football(key='RESULT_AWAY', probability=.4)
    pool = [away, *[football(i) for i in range(2, 52)], home]
    catalog = compose_wettfinder_catalog(cards(pool), max_featured=1)
    visible = catalog.featured + catalog.additional
    assert home.key in {c.key for c in visible} and away.key not in {c.key for c in visible}
    choices = daily3_choices(pool, now=NOW, used_slots=2)
    assert len(choices) == 1
    assert choices[0].signal.key in {c.key for c in visible}


@pytest.mark.parametrize('minutes,eligible', [(150, True), (151, False), (-1, False)])
def test_highlight_clock_window_uses_actual_model_clock(minutes, eligible):
    signal = esports(age=minutes/60)
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert bool(catalog.featured) is eligible


@pytest.mark.parametrize('days,eligible', [(14, True), (15, False), (-1, False)])
def test_tennis_coverage_review_boundary_is_presentation_only(days, eligible):
    signal = tennis()
    context = {**signal.context_evidence, 'model_inputs': {**signal.context_evidence['model_inputs'],
        'stats_through': (NOW-timedelta(days=days)).date().isoformat()}}
    signal = replace(signal, context_evidence=context)
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert bool(catalog.featured) is eligible
    assert (catalog.featured + catalog.additional)[0].model_probability == .76


def test_public_card_retains_model_identity_not_private_context():
    signal = tennis()
    card = cards([signal])[0]
    for field in ('modeled_at', 'input_cutoff_at', 'model_version', 'policy_version', 'model_scope'):
        assert getattr(card, field) == getattr(signal, field)
    assert not hasattr(card, 'context_evidence') and not hasattr(card, 'analysis_evidence')


def test_different_input_cutoffs_are_not_one_probability_revision():
    home = replace(football(probability=.2), analysis_evidence=None)
    away = replace(football(key='RESULT_AWAY', probability=.9), analysis_evidence=None,
                   input_cutoff_at=(NOW-timedelta(hours=1)).isoformat())
    assert select_consumer_forecasts([away, home], now=NOW)[0] is home


def test_same_key_clock_with_foreign_participant_is_stably_resolved():
    first = replace(football(), analysis_evidence=None)
    foreign = replace(first, home_team_id=999)
    assert select_consumer_forecasts([first, foreign], now=NOW) == select_consumer_forecasts([foreign, first], now=NOW)


def test_comparable_btts_and_h2h_directions_choose_their_own_stronger_probability():
    yes, no = football(key='BTTS_YES', probability=.4), football(key='BTTS_NO', probability=.6)
    a = replace(tennis(), probability=.4)
    b = replace(a, key='tennis-b', selected_competitor='Spieler B', selection='Sieg Spieler B', probability=.6)
    for pool in permutations((yes, no, a, b)):
        selected = select_consumer_forecasts(pool, now=NOW)
        assert {s.key for s in selected} == {no.key, b.key}
        assert {c.key for c in compose_wettfinder_catalog(cards(pool)).featured} == {no.key, b.key}


@pytest.mark.parametrize('field', ['model_built_at', 'training_cutoff'])
def test_tennis_future_provenance_cannot_be_hidden_by_current_calculation(field):
    signal = tennis()
    context = {**signal.context_evidence, 'model_inputs': {**signal.context_evidence['model_inputs'],
        field: (NOW+timedelta(days=1)).isoformat()}}
    signal = replace(signal, context_evidence=context)
    catalog = compose_wettfinder_catalog(cards([signal]))
    assert not catalog.featured and not daily3_choices([signal], now=NOW)
    assert '02.01.2030' in render_compact_row_html(catalog.additional[0])


def test_tennis_foreign_players_or_observation_clock_are_not_explanatory_evidence():
    original = tennis()
    for signal in (replace(original, competitor_a='Foreign'),
                   replace(original, modeled_at=(NOW-timedelta(minutes=1)).isoformat())):
        analysis = build_forecast_analysis(signal, now=NOW)
        assert not analysis.supported and 'Sand' not in analysis.basis
        assert 'Datenstand unbekannt' in analysis.data_age
        assert not compose_wettfinder_catalog(cards([signal])).featured


def test_model_dates_are_readable_local_dates_not_raw_internal_diagnostics():
    card = cards([tennis()])[0]
    markup = render_compact_row_html(card)
    assert 'Berechnet: 01.01.2030 13:00' in markup
    assert 'Modellaufbau: 01.01.2030 13:00' in markup
    assert 'Trainingsstichtag: 01.01.2030 13:00' in markup
    assert '2030-01-01T' not in markup


@pytest.mark.parametrize('key', ['HOME_OVER_0_5', 'AWAY_OVER_0_5', 'HOME_UNDER_2_5',
    'AWAY_UNDER_2_5', 'DC_1X', 'DC_X2', 'TOTAL_OVER_0_5', 'MIXED_BTTS_OR_OVER_2_5',
    'HOME_CORNERS_OVER_2_5', 'YELLOW_UNDER_4_5'])
def test_fresh_exactly_evidenced_former_basis_market_can_highlight_without_forcing_three(key):
    signal = football(key=key)
    if 'CORNERS' in key or 'YELLOW' in key:
        evidence = signal.analysis_evidence
        signal = replace(signal, analysis_evidence={**evidence, 'basis': {**evidence['basis'],
            'expected_market_home': 3.2, 'expected_market_away': 2.1,
            'expected_unit': 'Ecken' if 'CORNERS' in key else 'Gelbe Karten'}})
    for candidate in (signal, replace(signal, minimum_odds=999, evidence_stage='RELEASED')):
        catalog = compose_wettfinder_catalog(cards([candidate]))
        assert [card.market_key for card in catalog.featured] == [key]
        assert not catalog.additional
        choices = daily3_choices([candidate], now=NOW)
        assert len(choices) == 1 and choices[0].signal is candidate
    unsupported = replace(signal, analysis_evidence=None)
    assert not compose_wettfinder_catalog(cards([unsupported])).featured
    assert not daily3_choices([unsupported], now=NOW)


def test_market_categories_do_not_override_shared_canonical_preference():
    # Independent events share model time. A category demotion must not move
    # the ordinary event-1 forecast behind the unrelated event-2 forecast.
    dc, home = football(1, key='DC_X2', probability=.75), football(2, probability=.8)
    for pool in ((dc, home), (home, dc)):
        shared = select_consumer_forecasts(pool, now=NOW)
        assert shared == [dc, home]
        catalog = compose_wettfinder_catalog(cards(pool), max_featured=1)
        assert [card.market_key for card in catalog.featured] == ['DC_X2']
        # Daily3's approved defensive profile is intentionally different;
        # it must not change the ordinary catalog's canonical ordering.
        assert daily3_choices(pool, now=NOW)[0].signal is home


def test_result_direction_anchor_does_not_override_a_newer_or_supported_revision():
    dc = football(key='DC_X2', probability=.4)
    old_home = football(probability=.6, now=NOW-timedelta(minutes=1))
    unsupported_home = replace(football(probability=.6), analysis_evidence=None)
    for home in (old_home, unsupported_home):
        assert select_consumer_forecasts([home, dc], now=NOW) == [dc]
