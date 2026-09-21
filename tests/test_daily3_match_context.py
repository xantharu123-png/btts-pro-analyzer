from dataclasses import replace

from daily3_selection import daily3_choices
from forecast_selection import select_consumer_forecasts
from test_daily3_selection import NOW, football


def test_favourite_baseline_not_confused_with_a_match_specific_form_signal():
    obvious = football(1, 'HOME_OVER_0_5', .97, baseline=.5, variants=(.97, .969, .973))
    supported = football(2, 'AWAY_OVER_0_5', .77, baseline=.7, variants=(.77, .72, .86))
    choices = daily3_choices([obvious, supported], now=NOW)
    assert [c.signal.key for c in choices] == [supported.key]
    assert obvious in select_consumer_forecasts([obvious, supported], now=NOW)
    assert obvious.probability == .97


def test_same_market_allowed_on_either_side_only_with_actual_match_signal():
    for key in ('HOME_OVER_0_5', 'AWAY_OVER_0_5', 'AWAY_UNDER_2_5', 'HOME_RANGE_1_3'):
        item = football(1, key, .78, variants=(.78, .73, .87))
        assert daily3_choices([item], now=NOW)[0].signal is item


def test_no_reverse_form_no_noise_and_no_riskier_fillers():
    for variants in ((.96, .97, .93), (.96, .96, .96), (.96, .955, .975), (.72, .65, .93)):
        item = football(probability=variants[0], variants=variants)
        assert daily3_choices([item], now=NOW) == ()


def test_qualified_match_signals_rank_defensively_independent_of_price():
    favourite = football(1, 'HOME_OVER_0_5', .94, variants=(.94, .915, .985))
    alternative = football(2, 'AWAY_OVER_0_5', .80, variants=(.8, .72, .94))
    before = daily3_choices([favourite, alternative], now=NOW)
    # Both have a genuine saved same-match form signal. Relevance admits both;
    # the approved defensive priority then prefers lower modeled loss risk.
    # A favourite WITHOUT such a signal remains excluded by the test above.
    assert before[0].signal is favourite
    changed = [replace(s, minimum_odds=999, probability_haircut=.001) for s in (alternative, favourite)]
    assert [c.signal.key for c in daily3_choices(changed, now=NOW)] == [c.signal.key for c in before]
    assert 'Formsignal' in before[0].comparison.summary
    assert before[0].comparison.match_reference_probability == .915


def test_caption_reports_actual_change_not_the_smaller_ranking_contrast():
    item = football(probability=.8, variants=(.8, .7, .75))
    comparison = daily3_choices([item], now=NOW)[0].comparison
    assert comparison.margin == .05
    assert '+10,0 Prozentpunkte' in comparison.summary
