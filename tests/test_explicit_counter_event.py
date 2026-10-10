"""A complementary probability must name its own market before expansion."""

from copy import deepcopy
from dataclasses import replace
from html.parser import HTMLParser

import pytest

from challenge_engine import MARKET_BY_KEY
from forecast_analysis import build_forecast_analysis, project_football_analysis
from forecast_compact import build_compact_analysis, render_compact_analysis_html
from test_forecast_analysis import NOW, _basis, _row, _signal
from wettfinder_surface import build_wettfinder_card, render_editorial_card_html


class FactSummaries(HTMLParser):
    """Read only native fact summaries, not their initially hidden details."""

    def __init__(self, markup):
        super().__init__()
        self.in_fact = self.in_summary = False
        self.current = []
        self.summaries = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            self.in_fact = 'wf-fact' in dict(attrs).get('class', '').split()
        elif tag == 'summary' and self.in_fact:
            self.in_summary = True
            self.current = []

    def handle_endtag(self, tag):
        if tag == 'summary' and self.in_summary:
            self.summaries.append(' '.join(''.join(self.current).split()))
            self.in_summary = False
        elif tag == 'details':
            self.in_fact = False

    def handle_data(self, text):
        if self.in_summary:
            self.current.append(text)


def signal_for(key, probability, *, home='Parma', away='Lecce'):
    row = _row(key, probability)
    row.update(home_team=home, away_team=away, model_scope='same_competition')
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    spec = MARKET_BY_KEY.get(key)
    return replace(_signal(row), minimum_odds=2.25,
                   market=spec.market if spec else 'Unbekannter Markt',
                   selection=spec.selection if spec else 'Unbekannte Auswahl')


@pytest.mark.parametrize('key, probability, event, percentage, unrelated', [
    ('HOME_CORNERS_OVER_5_5', .186, 'höchstens 5 Ecken für Parma', '81,4 %', 'Tore'),
    ('HOME_OVER_0_5', .615, 'höchstens 0 Tore für Parma', '38,5 %', 'Ecken'),
    ('AWAY_UNDER_1_5', .776, 'mindestens 2 Tore für Lecce', '22,4 %', 'Parma'),
    ('RESULT_HOME', .63, 'Remis oder Auswärtssieg', '37,0 %', 'Tore'),
    ('AWAY_RANGE_2_4', .447, 'Tore für Lecce außerhalb dieses Bereichs', '55,3 %', 'Parma'),
    ('TOTAL_OVER_2_5', .63, 'höchstens 2 Tore insgesamt', '37,0 %', 'für Parma'),
    ('BTTS_YES', .76, 'mindestens ein Team ohne Tor', '24,0 %', 'Ecken'),
])
def test_closed_fact_binds_complementary_probability_to_its_own_market(
    key, probability, event, percentage, unrelated,
):
    # Moving the event back into hidden details, using another market's event,
    # or presenting p instead of 1-p must break this consumer-visible contract.
    signal = signal_for(key, probability)
    analysis = build_forecast_analysis(signal, now=NOW)
    compact = build_compact_analysis(signal, analysis, now=NOW)
    summaries = FactSummaries(render_compact_analysis_html(compact)).summaries
    counter = next(text for text in summaries if text.startswith('Gegenrisiko '))
    assert f'{event}: {percentage}' in counter
    assert unrelated not in counter


def test_parma_corner_and_goal_cards_do_not_share_their_counterevent_or_percentage():
    # These two cards reproduce the reported 61.5% versus 81.4% confusion.
    corner = build_wettfinder_card(signal_for('HOME_CORNERS_OVER_5_5', .186), now=NOW)
    goal = build_wettfinder_card(signal_for('HOME_OVER_0_5', .615), now=NOW)
    corner_html = render_editorial_card_html(corner)
    goal_html = render_editorial_card_html(goal)
    corner_summary = FactSummaries(corner_html).summaries[0]
    goal_summary = FactSummaries(goal_html).summaries[0]
    assert 'höchstens 5 Ecken für Parma: 81,4 %' in corner_summary
    assert 'höchstens 0 Tore für Parma: 38,5 %' in goal_summary
    assert '38,5 %' not in corner_summary and '81,4 %' not in goal_summary
    assert '18.6 %' in corner_html and '61.5 %' in goal_html


@pytest.mark.parametrize('key, probability, event, percentage', [
    ('RESULT_TOTAL_1X_UNDER_3_5', .621,
     'Auswärtssieg ODER mindestens 4 Tore insgesamt', '37,9 %'),
    ('RESULT_TOTAL_X2_UNDER_3_5', .682,
     'Heimsieg ODER mindestens 4 Tore insgesamt', '31,8 %'),
    ('RESULT_TOTAL_12_OVER_1_5', .711,
     'Remis ODER höchstens 1 Tor insgesamt', '28,9 %'),
    ('MIXED_BTTS_OR_OVER_2_5', .634,
     'mindestens ein Team ohne Tor UND höchstens 2 Tore insgesamt', '36,6 %'),
    ('MIXED_HOME_OR_OVER_2_5', .559,
     '(Remis oder Auswärtssieg) UND höchstens 2 Tore insgesamt', '44,1 %'),
    ('MIXED_AWAY_OR_OVER_2_5', .436,
     '(Heimsieg oder Remis) UND höchstens 2 Tore insgesamt', '56,4 %'),
])
def test_known_combo_cards_show_exact_logical_complement_without_a_new_probability(
    key, probability, event, percentage,
):
    # Negating A AND B requires NOT A OR NOT B; negating A OR B requires
    # NOT A AND NOT B. Wrong connectives, sides, grouping or goal boundaries
    # must be visible in the real rendered counterevent, not a hidden fallback.
    signal = signal_for(key, probability)
    before = deepcopy(vars(signal))
    card = build_wettfinder_card(signal, now=NOW)
    summary = FactSummaries(render_editorial_card_html(card)).summaries[0]
    assert f'{event}: {percentage}' in summary
    assert 'Auswahl tritt nicht ein' not in summary
    assert card.model_probability == probability
    assert vars(signal) == before


def test_visible_counterevent_escapes_and_keeps_an_entire_long_team_name():
    team = 'Parma <script>alert("x")</script> & ' + 'EinSehrLangerVereinsname' * 6
    signal = signal_for('HOME_CORNERS_OVER_5_5', .186, home=team)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)
    markup = render_compact_analysis_html(compact)
    assert f'höchstens 5 Ecken für {team}: 81,4 %' in FactSummaries(markup).summaries[0]
    assert '<script>' not in markup
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp;' in markup


def test_unknown_market_counterevent_stays_honest_and_does_not_guess_a_unit():
    signal = signal_for('UNKNOWN_MARKET', .63)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)
    summary = FactSummaries(render_compact_analysis_html(compact)).summaries[0]
    assert 'Auswahl tritt nicht ein: 37,0 %' in summary
    assert 'Tore' not in summary and 'Ecken' not in summary


def test_counterevent_rendering_cannot_change_frozen_model_or_price_inputs():
    signal = signal_for('HOME_CORNERS_OVER_5_5', .186)
    before = deepcopy(vars(signal))
    analysis = build_forecast_analysis(signal, now=NOW)
    compact = build_compact_analysis(signal, analysis, now=NOW)
    render_compact_analysis_html(compact)
    render_editorial_card_html(build_wettfinder_card(signal, now=NOW))
    assert vars(signal) == before
    assert signal.probability == .186 and signal.minimum_odds == 2.25
    assert signal.modeled_at == '2030-01-01T10:00:00+00:00'
    assert signal.input_cutoff_at == '2030-01-01T09:59:00+00:00'
