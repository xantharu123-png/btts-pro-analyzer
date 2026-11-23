"""The alternative view narrows the offered pool without promoting a new tip."""

from dataclasses import replace

import pytest

import wettfinder_surface as surface
from test_daily3_selection import NOW, _admitted, football, tennis
from test_publication_odds_floor import priced


def _football(fixture, key, probability, *, utility=.12, price=1.8):
    signal = replace(football(fixture, key, probability), selection_rank=[utility, 80., .12, -1., -8., .6])
    if 'CORNERS' in key:
        evidence = signal.analysis_evidence
        signal = replace(signal, analysis_evidence={**evidence, 'basis': {
            **evidence['basis'], 'expected_market_home': 5.1, 'expected_market_away': 4.2, 'expected_unit': 'Ecken',
        }})
    signal = priced(signal, (price,) * 3)
    return surface.build_wettfinder_card(signal, signal.reference_quote, now=NOW)


@pytest.mark.price_policy('floor')
@pytest.mark.parametrize(('family', 'market'), [
    ('Sieger & Ergebnis', 'RESULT_HOME'),
    ('Doppelte Chance', 'DC_1X'),
    ('Tore Über/Unter', 'TOTAL_OVER_1_5'),
    ('Tore Über/Unter', 'HOME_UNDER_2_5'),
    ('Torbereiche', 'TOTAL_RANGE_1_4'),
    ('Torbereiche', 'HOME_RANGE_1_3'),
    ('Beide treffen', 'BTTS_YES'),
    ('Ecken', 'CORNERS_UNDER_11_5'),
    ('Ecken', 'HOME_CORNERS_OVER_2_5'),
    ('Karten', 'YELLOW_UNDER_4_5'),
    ('Karten', 'HOME_YELLOW_OVER_0_5'),
    ('Kombimärkte', 'RESULT_TOTAL_1X_UNDER_3_5'),
    ('Kombimärkte', 'MIXED_BTTS_OR_OVER_2_5'),
    ('Weitere Wettarten', 'UNRECOGNIZED_MARKET'),
])
def test_market_key_has_one_family_not_inferred_from_the_display_label(family, market):
    known = market != 'UNRECOGNIZED_MARKET'
    # Mixed markets have no exact provider quote. The current price contract
    # allows a model-only row below the unpriced chance cap.
    original = surface.build_wettfinder_card(football(1, market if known else 'RESULT_HOME', .60), now=NOW)
    original = replace(original, market_key=market, market='Anzeigetext Über Tore')
    catalog = surface.compose_wettfinder_catalog([original])

    assert family in surface.WETTFINDER_MARKET_FAMILIES
    for option in surface.WETTFINDER_MARKET_FAMILIES[1:]:
        projected = surface.best_wettfinder_by_market(catalog, family=option)
        assert projected.additional == ((original,) if option == family else ())


def test_all_families_pick_by_raw_probability_per_fixture_without_mutating_original():
    lower = _football(1, 'TOTAL_UNDER_4_5', .7002, utility=.4, price=2.4)
    winner = _football(1, 'HOME_UNDER_2_5', .7004, utility=.02, price=1.8)
    corners = _football(1, 'CORNERS_UNDER_11_5', .78)
    separate_fixture = _football(2, 'TOTAL_UNDER_4_5', .79)
    catalog = surface.compose_wettfinder_catalog([lower, winner, corners, separate_fixture])
    original = catalog.featured + catalog.additional

    projected = surface.best_wettfinder_by_market(catalog, min_probability=.70)

    assert not projected.featured
    assert {id(row) for row in projected.additional} == {id(row) for row in (winner, corners, separate_fixture)}
    assert len(projected.additional_groups) == 2
    assert projected.event_leads == catalog.event_leads
    assert catalog.featured + catalog.additional == original
    assert lower in original


def test_ties_are_stable_and_rank_is_not_the_tiebreaker():
    later = _football(1, 'TOTAL_UNDER_4_5', .75, utility=.4)
    earlier = _football(1, 'HOME_UNDER_2_5', .75, utility=.02)
    for cards in ([later, earlier], [earlier, later]):
        catalog = surface.compose_wettfinder_catalog(cards)
        projected = surface.best_wettfinder_by_market(catalog, family='Tore Über/Unter')
        assert projected.additional == (earlier,)


def test_family_projection_does_not_reintroduce_a_price_exclusion_or_an_opposite_direction():
    home = _football(1, 'RESULT_HOME', .90, price=1.12)
    away = _football(1, 'RESULT_AWAY', .10)
    visible = _football(1, 'TOTAL_UNDER_4_5', .75)
    catalog = surface.compose_wettfinder_catalog([away, home, visible])

    assert surface.best_wettfinder_by_market(catalog, family='Sieger & Ergebnis').additional == ()
    projected = surface.best_wettfinder_by_market(catalog)
    assert projected.additional == (visible,)
    assert projected.event_leads == (home,)


@pytest.mark.parametrize('change', [
    {'modeled_at': '2029-12-31T06:59:00Z'},
    {'model_version': 'older-model'},
    {'policy_version': 'older-policy'},
    {'fixture_source': 'other-native-source'},
])
def test_family_and_minimum_chance_do_not_fall_back_to_a_different_revision(change):
    anchor = _football(1, 'TOTAL_UNDER_4_5', .82)
    weak = _football(1, 'HOME_CORNERS_OVER_2_5', .68)
    foreign = replace(_football(1, 'CORNERS_UNDER_11_5', .90), **change)
    # Explicit visibility snapshot: the parent selected its revision on the complete
    # coherent pool; that decision cannot be recreated inside the family filter.
    catalog = surface.WettfinderCatalog((anchor,), (weak, foreign), (), (anchor,))

    assert surface.best_wettfinder_by_market(catalog, family='Ecken').additional == (weak,)
    projected = surface.best_wettfinder_by_market(catalog, family='Ecken', min_probability=.70)
    assert projected.additional == projected.additional_groups == projected.event_leads == ()


@pytest.mark.parametrize('invalid_probability', [
    None, True, '.80', float('nan'), float('inf'), -0.1, 1.01, pytest.param(10**1000, id='huge-int'),
])
def test_malformed_chance_cannot_appear_even_with_a_zero_floor(invalid_probability):
    anchor = _football(1, 'TOTAL_UNDER_4_5', .82)
    malformed = replace(_football(1, 'CORNERS_UNDER_11_5', .75), model_probability=invalid_probability)
    catalog = surface.WettfinderCatalog((anchor,), (malformed,), (), (anchor,))

    assert surface.best_wettfinder_by_market(catalog).additional == (anchor,)


def test_native_h2h_keeps_its_exact_identity_and_uses_the_visible_chance_floor():
    signal = _admitted(replace(tennis(), probability=.6996, model_version='native-tennis-model'))
    native = surface.build_wettfinder_card(signal, signal.reference_quote, now=NOW)
    unversioned = replace(native, key='no-revision', provider_event_id='t2', model_version=None)
    catalog = surface.compose_wettfinder_catalog([native, unversioned])

    projected = surface.best_wettfinder_by_market(catalog, family='Sieger & Ergebnis', min_probability=.70)
    assert len(projected.additional) == 1 and projected.additional[0] is native
    assert surface.best_wettfinder_by_market(catalog, min_probability=.701).additional == ()


@pytest.mark.parametrize('filters', [{'family': 'Unknown'}, {'min_probability': True}, {'min_probability': 1.1}])
def test_invalid_filter_does_not_silently_show_a_broader_pool(filters):
    catalog = surface.compose_wettfinder_catalog([])
    with pytest.raises(ValueError):
        surface.best_wettfinder_by_market(catalog, **filters)
