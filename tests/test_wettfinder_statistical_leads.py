"""Statistical event leads survive chronological presentation sorting."""
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
def test_statistical_lead_never_compares_foreign_revision_or_participant_rank(changes):
    from forecast_selection import select_event_leads
    current = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    foreign = replace(card(signal(1, 'RESULT_HOME', .60, .12)), **changes)
    assert select_event_leads([current, foreign]) == [current]


def test_missing_revision_clocks_cannot_masquerade_as_one_statistical_revision():
    from forecast_selection import select_event_leads
    current = replace(card(signal(1, 'TOTAL_UNDER_4_5', .90, .01)), modeled_at=None)
    unknown = replace(card(signal(1, 'RESULT_HOME', .60, .12)), modeled_at=None)
    assert select_event_leads([current, unknown]) == [current]


def test_statistical_lead_is_selected_once_before_sort_and_is_permutation_invariant():
    lead = card(signal(1, 'RESULT_HOME', .60, .12))
    broad = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    other = card(signal(2, 'RESULT_HOME', .75, .08))
    for ordered in permutations((lead, broad, other)):
        catalog = compose_wettfinder_catalog(ordered)
        groups = group_wettfinder_games(catalog)
        assert {group.fixture_id if hasattr(group, 'fixture_id') else group.cards[0].fixture_id:
                group.lead.key for group in groups} == {1: lead.key, 2: other.key}
        assert broad.key not in {item.key for item in catalog.featured}
        assert {item.key for item in catalog.featured + catalog.additional} == {lead.key, broad.key, other.key}


def test_real_renderer_orders_games_by_selected_lead_not_secondary_market_probability(monkeypatch):
    import app
    lead = card(signal(1, 'RESULT_HOME', .60, .12))
    broad = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    middle = card(signal(2, 'RESULT_HOME', .75, .08))
    lower_alternative = card(signal(1, 'HOME_UNDER_2_5', .80, .02))
    cards = (broad, middle, lower_alternative, lead)
    before = deepcopy(cards)
    catalog = compose_wettfinder_catalog(cards)
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(catalog, {item.key: (None, item) for item in cards}, sport_filter='Alle')
    html = [text for text, _, _ in recording.markdown_calls if 'data-key=' in text]
    # Keep the legacy ID. Equal starts retain producer game order; the chosen
    # lead and the priority among its secondary markets remain unchanged.
    assert [next(item.key for item in cards if f'data-key="{item.key}"' in text) for text in html] == [
        lead.key, broad.key, lower_alternative.key, middle.key]
    assert cards == before


def test_low_price_lead_is_not_replaced_by_opposite_direction_or_promoted_secondary():
    home = card(signal(1, 'RESULT_HOME', .60, .12, price=1.12))
    away = card(signal(1, 'RESULT_AWAY', .40, .20))
    broad = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    catalog = compose_wettfinder_catalog((away, broad, home))
    assert catalog.event_leads == (home,)
    assert {item.key for item in catalog.featured + catalog.additional} == {broad.key}
    assert not catalog.featured
    group, = group_wettfinder_games(catalog)
    assert group.lead is home and group.cards == (broad,)
