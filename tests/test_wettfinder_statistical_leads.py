"""Game leads are the most probable shown selection and survive presentation sorting.

Owner decision 23.10.2026 (docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md):
the producer's ``selection_rank`` stays on the rows but no longer picks the lead.
"""
from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest

from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced
from test_workflow_integrity import _RecordingStreamlit
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog, group_wettfinder_games


def signal(fixture, key, probability, utility, *, price=1.80):
    candidate = replace(football(fixture, key, probability),
        selection_rank=[utility, 80., utility / .8, -1., -8., probability-.08])
    return priced(candidate, (price,) * 3)


def card(candidate):
    return build_wettfinder_card(candidate, candidate.reference_quote, now=NOW)


def test_validated_statistical_rank_survives_signal_and_card_projection():
    candidate = signal(1, 'RESULT_HOME', .60, .12)
    expected = (.12, 80., .15, -1., -8., .52)
    assert candidate.selection_rank == expected
    assert card(candidate).selection_rank == expected
    from ev_signal_sources import _automated_analysis_fields
    assert _automated_analysis_fields(vars(candidate), now=NOW)['selection_rank'] == expected


@pytest.mark.parametrize('rank', [None, [], [True]*6, [float('nan')]*6, [float('inf')]*6,
                                  ['.9']*6, [10**1000]*6])
def test_malformed_optional_rank_is_not_relabelled_as_statistical_support(rank):
    candidate = replace(football(), selection_rank=rank)
    assert candidate.selection_rank is None
    assert card(candidate).selection_rank is None
    assert replace(card(football()), selection_rank=rank).selection_rank is None


@pytest.mark.parametrize('changes', [
    {'model_version': 'other'}, {'input_cutoff_at': '2029-12-31T01:00:00Z'},
    {'home_team_id': 999}, {'scheduled_start': '2030-01-01T11:00:00Z'},
])
def test_lead_never_compares_foreign_revision_or_participant_probability(changes):
    from forecast_selection import select_event_leads
    current = card(signal(1, 'RESULT_HOME', .60, .12))
    foreign = replace(card(signal(1, 'TOTAL_UNDER_4_5', .90, .01)), **changes)
    assert select_event_leads([current, foreign]) == [current]


def test_missing_revision_clocks_cannot_masquerade_as_one_revision():
    from forecast_selection import select_event_leads
    current = replace(card(signal(1, 'RESULT_HOME', .60, .12)), modeled_at=None)
    unknown = replace(card(signal(1, 'TOTAL_UNDER_4_5', .90, .01)), modeled_at=None)
    # Legacy preference keeps the first row; the public catalog invents no lead.
    assert select_event_leads([current, unknown]) == [current]
    assert select_event_leads([current, unknown], require_comparable=True) == []


def test_lead_is_the_most_probable_selection_regardless_of_producer_rank():
    from forecast_selection import select_event_leads
    ranked = card(signal(1, 'RESULT_HOME', .60, .12))
    probable = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    corners = card(signal(1, 'HOME_UNDER_2_5', .80, .30))
    assert ranked.selection_rank > probable.selection_rank
    for ordered in permutations((ranked, probable, corners)):
        assert select_event_leads(list(ordered)) == [probable]


def test_equal_probabilities_break_ties_by_stable_market_key_not_input_order():
    from forecast_selection import select_event_leads
    draw = card(signal(1, 'RESULT_DRAW', .40, .05))
    home = card(signal(1, 'RESULT_HOME', .40, .01))
    assert select_event_leads([draw, home]) == [home]
    assert select_event_leads([home, draw]) == [home]


def test_most_probable_lead_is_selected_once_before_sort_and_is_permutation_invariant():
    lead = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    narrow = card(signal(1, 'RESULT_HOME', .60, .12))
    other = card(signal(2, 'RESULT_HOME', .75, .08))
    for ordered in permutations((lead, narrow, other)):
        catalog = compose_wettfinder_catalog(ordered)
        groups = group_wettfinder_games(catalog)
        assert {group.fixture_id if hasattr(group, 'fixture_id') else group.cards[0].fixture_id:
                group.lead.key for group in groups} == {1: lead.key, 2: other.key}
        assert narrow.key not in {item.key for item in catalog.featured}
        assert {item.key for item in catalog.featured + catalog.additional} == {lead.key, narrow.key, other.key}


def test_real_renderer_orders_games_by_selected_lead_not_secondary_market_probability(monkeypatch):
    import app
    lead = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    narrow = card(signal(1, 'RESULT_HOME', .60, .12))
    middle = card(signal(2, 'RESULT_HOME', .75, .08))
    lower_alternative = card(signal(1, 'HOME_UNDER_2_5', .80, .02))
    cards = (narrow, middle, lower_alternative, lead)
    before = deepcopy(cards)
    catalog = compose_wettfinder_catalog(cards)
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(catalog, {item.key: (None, item) for item in cards}, sport_filter='Alle')
    html = [text for text, _, _ in recording.markdown_calls if 'data-key=' in text]
    # Keep the legacy ID. Equal starts retain producer game order; the most
    # probable lead comes first, its secondary markets follow by probability.
    assert [next(item.key for item in cards if f'data-key="{item.key}"' in text) for text in html] == [
        lead.key, lower_alternative.key, narrow.key, middle.key]
    assert cards == before


def test_low_price_lead_is_not_replaced_by_opposite_direction_or_promoted_secondary():
    home = card(signal(1, 'RESULT_HOME', .60, .12, price=1.12))
    away = card(signal(1, 'RESULT_AWAY', .40, .20))
    broad = card(signal(1, 'TOTAL_UNDER_4_5', .50, .01))
    catalog = compose_wettfinder_catalog((away, broad, home))
    assert catalog.event_leads == (home,)
    assert {item.key for item in catalog.featured + catalog.additional} == {broad.key}
    assert not catalog.featured
    group, = group_wettfinder_games(catalog)
    assert group.lead is home and group.cards == (broad,)
    assert group.visible_lead is broad
