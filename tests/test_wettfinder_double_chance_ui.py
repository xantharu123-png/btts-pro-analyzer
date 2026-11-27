"""The double-chance display keeps canonical sides and only proven 1X2 splits."""
from dataclasses import replace
from html import escape

import pytest

from challenge_engine import CHALLENGE_PREDICTION_VERSION
from daily3_comparison import Comparison
from forecast_analysis import project_football_analysis
from test_forecast_analysis import NOW, _basis, _row, _signal
from wettfinder_surface import (
    best_wettfinder_by_market, build_wettfinder_card, compose_wettfinder_catalog, render_wettfinder_row_html,
)


def double_chance(key, p, *, result=None, swap=False):
    row = _row(key, p)
    row['model_scope'] = 'same_competition'
    row['model_version'] = CHALLENGE_PREDICTION_VERSION
    row['home_team'], row['away_team'] = ('Alpha & Nord', 'Beta <Süd>')
    if swap:
        row['home_team'], row['away_team'] = row['away_team'], row['home_team']
        row['home_id'], row['away_id'] = row['away_id'], row['home_id']
    basis = _basis(row)
    if result is not None:
        basis['result_probabilities'] = list(result)
    row['analysis_evidence'] = project_football_analysis(row, model_basis=basis)
    signal = replace(_signal(row), market='Doppelte Chance', selection='native selection unchanged',
                     model_version=CHALLENGE_PREDICTION_VERSION)
    return signal


@pytest.mark.parametrize('key,p,title,fragments,contra', [
    ('DC_1X', .74, 'Sieg Alpha & Nord oder Remis (1X)', ('Sieg Alpha & Nord: 51,0 %', 'Remis: 23,0 %'),
     'Auswärtssieg: 26,0 %'),
    ('DC_X2', .49, 'Sieg Beta <Süd> oder Remis (X2)', ('Sieg Beta <Süd>: 26,0 %', 'Remis: 23,0 %'),
     'Heimsieg: 51,0 %'),
    ('DC_12', .77, 'Kein Remis (12)', ('Sieg Alpha & Nord: 51,0 %', 'Sieg Beta <Süd>: 26,0 %'),
     'Remis: 23,0 %'),
])
def test_actual_row_names_the_market_and_matching_components(key, p, title, fragments, contra):
    signal = double_chance(key, p, result=(.51, .23, .26))
    card = build_wettfinder_card(signal, now=NOW)
    markup = render_wettfinder_row_html(card)
    assert f'<strong>{escape(title)}</strong>' in markup
    assert 'native selection unchanged' not in markup and card.selection == signal.selection
    assert all(escape(fragment) in markup for fragment in fragments)
    assert contra in markup
    assert card.result_probabilities == (.51, .23, .26)
    assert card.model_probability == p


def test_symmetric_reorientation_uses_the_away_team_for_x2():
    card = build_wettfinder_card(double_chance('DC_X2', .74, result=(.26, .23, .51), swap=True), now=NOW)
    markup = render_wettfinder_row_html(card)
    assert '<strong>Sieg Alpha &amp; Nord oder Remis (X2)</strong>' in markup
    assert 'Sieg Alpha &amp; Nord: 51,0 %' in markup and 'Heimsieg: 26,0 %' in markup


@pytest.mark.parametrize('result', [None, (.25, .24, .51), (.51, float('nan'), .26)])
def test_missing_or_invalid_split_shows_real_selection_and_opposing_probability_without_guessing(result):
    card = build_wettfinder_card(double_chance('DC_1X', .74, result=result), now=NOW)
    markup = render_wettfinder_row_html(card)
    assert 'Sieg Alpha &amp; Nord oder Remis: 74,0 % im Modell' in markup
    assert 'Auswärtssieg: 26,0 %' in markup and ' + Remis:' not in markup
    assert 'Sieg Alpha &amp; Nord:' not in markup and card.result_probabilities is None


@pytest.mark.parametrize('field,value', [('away_id', 11), ('modeled_at', '2030-01-01T10:01:00+00:00')])
def test_tampered_role_or_model_clock_cannot_supply_the_split(field, value):
    signal = double_chance('DC_X2', .49, result=(.51, .23, .26))
    signal.analysis_evidence['identity'][field] = value
    card = build_wettfinder_card(signal, now=NOW)
    markup = render_wettfinder_row_html(card)
    assert '<strong>Sieg Beta &lt;Süd&gt; oder Remis (X2)</strong>' in markup
    assert 'Sieg Beta &lt;Süd&gt; oder Remis: 49,0 % im Modell' in markup
    assert 'Remis: 23,0 %' not in markup and card.result_probabilities is None


@pytest.mark.parametrize('key,p,covers_modal', [('DC_X2', .49, False), ('DC_1X', .74, True)])
def test_featured_fallback_still_requires_coverage_of_modal_outcome(key, p, covers_modal):
    card = build_wettfinder_card(double_chance(key, p, result=(.51, .23, .26)), now=NOW)
    eligible = replace(card, modeled_at=None, highlight_eligible=True, price_check_completed=True,
                       highlight_comparison=Comparison(.12, .49, .45, 325), quote_floor_excluded=False)
    catalog = compose_wettfinder_catalog([eligible])
    if covers_modal:
        assert catalog.featured == (eligible,) and not catalog.additional
    else:
        assert not catalog.featured and catalog.additional == (eligible,)


def test_normal_catalog_keeps_off_modal_alternative_but_best_by_market_does_not_nominate_it():
    def offered(signal):
        card = build_wettfinder_card(replace(signal, key=signal.market_key), now=NOW)
        return replace(card, quote_floor_excluded=False)

    # Independent total stays the same-revision event anchor. Thus the
    # rejected nomination is not just caused by an absent event anchor.
    total = offered(replace(double_chance('TOTAL_OVER_0_5', .82), market='Gesamttore', selection='Über 0,5'))
    off_modal = offered(double_chance('DC_X2', .49, result=(.51, .23, .26)))
    covering = offered(double_chance('DC_1X', .74, result=(.51, .23, .26)))
    catalog = compose_wettfinder_catalog([off_modal, total])
    assert catalog.event_leads == (total,)
    assert off_modal in catalog.additional and off_modal not in catalog.featured
    assert 'Kaderstand' in render_wettfinder_row_html(off_modal)
    assert best_wettfinder_by_market(catalog, family='Doppelte Chance').additional == ()
    assert best_wettfinder_by_market(catalog).additional == (total,)

    with_covering = compose_wettfinder_catalog([off_modal, total, covering])
    assert off_modal in with_covering.additional
    assert best_wettfinder_by_market(with_covering, family='Doppelte Chance').additional == (covering,)
