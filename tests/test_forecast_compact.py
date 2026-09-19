from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from html.parser import HTMLParser

import pytest

from challenge_engine import _injury_summary
from forecast_analysis import build_forecast_analysis, project_football_analysis, read_football_analysis
from forecast_compact import build_compact_analysis, render_compact_analysis_html
from test_forecast_analysis import NOW, _row, _basis, _signal


class InitialText(HTMLParser):
    """Native details expose only their summary until activated."""
    def __init__(self, markup):
        super().__init__()
        self.details = self.summary = 0
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.details += tag == 'details'
        self.summary += tag == 'summary'

    def handle_endtag(self, tag):
        self.details -= tag == 'details'
        self.summary -= tag == 'summary'

    def handle_data(self, text):
        if not self.details or self.summary:
            self.text.append(text)

    @property
    def visible(self):
        return ' '.join(self.text)


def row_with_names():
    row = _row('DC_1X', .776)
    row['model_scope'] = 'same_competition'
    row['context']['injuries'].update(
        home_missing=3, away_missing=7, home_questionable=1, away_questionable=0,
        home_missing_names=['Heim A', 'Heim B', 'Heim C'],
        away_missing_names=[f'Gast {i}' for i in range(7)],
        home_questionable_names=['Heim fraglich'], away_questionable_names=[],
        home_names=['Heim A', 'Heim B', 'Heim C', 'Heim fraglich'],
        away_names=[f'Gast {i}' for i in range(7)])
    return row


def compact(row=None):
    row = row or row_with_names()
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    signal = _signal(row)
    return build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)


def test_short_visible_facts_keep_material_warning_and_full_optional_details():
    result = compact()
    markup = render_compact_analysis_html(result)
    visible = InitialText(markup).visible
    assert 'Torprognose: 1,53 : 1,13 (Heim : Gast)' in visible
    for text in ('Ausfälle', '3 Heim · 7 Gast', 'Aufstellung', 'offen', 'Gegenrisiko',
                 '22,4 %', 'Basis', '12 Heim · 12 Gast', 'Ausfallwirkung nicht eingerechnet'):
        assert text in visible
    assert 'Heim A' not in visible and 'Das Modell erwartet' not in visible
    assert len(visible.split()) < 65
    assert 'Alpha · 3 Ausfälle: Heim A, Heim B, Heim C' in markup
    assert 'Alpha · 1 fraglich: Heim fraglich' in markup
    assert 'Beta · 7 Ausfälle: Gast 0, Gast 1' in markup
    assert '12 Heimspiele' in markup and 'je 6 letzte Spiele' in markup
    assert 'Berechnet: 01.01.2030 11:00' in visible
    assert 'Kaderstand: 01.01.2030 12:30' in markup
    assert '<details class="wf-fact"><summary>' in markup
    assert ' onclick' not in markup and '<button' not in markup


def test_names_are_enriched_from_same_observation_without_persisted_duplication():
    row = row_with_names()
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    assert 'Heim A' not in str(row['analysis_evidence'])
    original = deepcopy(row)
    projected = read_football_analysis(row, now=NOW)
    assert projected['context']['injuries']['home_missing_names'] == ['Heim A', 'Heim B', 'Heim C']
    assert row == original
    signal = _signal(row)
    assert read_football_analysis(vars(signal), now=NOW) == projected


@pytest.mark.parametrize('field, value', [
    ('checked_at', '2030-01-01T11:31:00+00:00'),
    ('status', 'blocked'), ('availability', 'unavailable'),
    ('coverage_available', False), ('home_missing', 4), ('away_missing', 8),
    ('home_questionable', 0), ('away_questionable', 1),
])
def test_names_from_different_observation_never_join_frozen_counts(field, value):
    row = row_with_names()
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    row['context']['injuries'][field] = value
    result = read_football_analysis(row, now=NOW)['context']['injuries']
    assert not any(key.endswith('_names') for key in result)


def test_no_context_names_if_market_or_native_identity_is_misbound():
    row = row_with_names()
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    row['home_id'] = 999
    assert read_football_analysis(row, now=NOW) is None


@pytest.mark.parametrize('doubtful', [None, 1])
def test_legacy_mixed_names_do_not_imply_confirmed_absences(doubtful):
    row = row_with_names()
    injuries = row['context']['injuries']
    injuries.pop('home_missing_names')
    injuries.pop('home_questionable_names')
    if doubtful is None:
        injuries.pop('home_questionable')
    else:
        injuries['home_questionable'] = doubtful
    result = compact(row)
    details = ' '.join(next(f.details for f in result.facts if f.label == 'Ausfälle'))
    assert 'Alpha · 3 Ausfälle: Namen nicht verfügbar' in details
    assert 'gemeldete Spieler, Status nicht einzeln zugeordnet: Heim A' in details


def test_legacy_names_can_be_absences_when_doubtful_count_is_explicitly_zero():
    row = row_with_names()
    injuries = row['context']['injuries']
    injuries.pop('home_missing_names')
    injuries['home_questionable'] = 0
    injuries['home_names'] = ['Heim A', 'Heim B', 'Heim C']
    result = compact(row)
    details = ' '.join(next(f.details for f in result.facts if f.label == 'Ausfälle'))
    assert 'Alpha · 3 Ausfälle: Heim A, Heim B, Heim C' in details


@pytest.mark.parametrize('names, expected', [
    ([], 'Namen nicht verfügbar'), (['Heim A'], 'Heim A (Liste unvollständig)'),
    (['A', 'B', 'C', 'D'], 'Namen nicht eindeutig zugeordnet'),
    (['777'], 'Namen nicht verfügbar'), (['A\nB'], 'Namen nicht verfügbar'),
    (['x' * 121], 'Namen nicht verfügbar'), (['x'] * 101, 'Namen nicht verfügbar'),
    ([{'name': 'injected'}], 'Namen nicht verfügbar'),
])
def test_incomplete_invalid_or_overlong_names_have_honest_fallback(names, expected):
    row = row_with_names()
    row['context']['injuries']['home_missing_names'] = names
    result = compact(row)
    assert f'Alpha · 3 Ausfälle: {expected}' in ' '.join(
        next(f.details for f in result.facts if f.label == 'Ausfälle'))


def test_player_names_and_team_names_cannot_inject_html():
    row = row_with_names()
    row['home_team'] = '<img src=x onerror="bad()">'
    row['context']['injuries']['home_missing_names'] = ['<script>bad()</script>', 'B', 'C']
    markup = render_compact_analysis_html(compact(row))
    assert '<script>' not in markup and '<img' not in markup
    assert '&lt;script&gt;bad()&lt;/script&gt;' in markup
    assert '&lt;img src=x onerror=&quot;bad()&quot;&gt;' in markup


@pytest.mark.parametrize('age', [timedelta(minutes=76), timedelta(minutes=-1)])
def test_old_or_future_context_does_not_show_names_or_current_counts(age):
    row = row_with_names()
    for axis in ('injuries', 'lineups'):
        row['context'][axis]['checked_at'] = (NOW - age).isoformat()
    markup = render_compact_analysis_html(compact(row))
    visible = InitialText(markup).visible
    assert 'veraltet' in visible and 'Aufstellung' in visible
    assert '3 Heim · 7 Gast' not in markup and 'Heim A' not in markup
    assert 'bestätigt' not in visible


@pytest.mark.parametrize('kind', ['missing', 'stale', 'unavailable'])
def test_unavailable_or_globally_stale_context_never_means_zero_absences(kind):
    row = row_with_names()
    if kind == 'missing':
        row['context'] = {}
    elif kind == 'stale':
        row['context']['stale'] = True
    else:
        row['context']['injuries']['availability'] = 'unavailable'
    markup = render_compact_analysis_html(compact(row))
    assert '3 Heim · 7 Gast' not in markup and 'Heim A' not in markup
    assert '0 Heim' not in markup and 'gesund' not in markup


@pytest.mark.parametrize('model_age', [None, timedelta(hours=3)])
def test_missing_or_stale_model_clock_warning_stays_visible(model_age):
    row = row_with_names()
    row['modeled_at'] = (NOW - model_age).isoformat() if model_age else None
    row['input_cutoff_at'] = row['modeled_at']
    visible = InitialText(render_compact_analysis_html(compact(row))).visible
    assert ('Modellstand nicht aktuell belegt' if model_age else 'Modellzeit unbekannt') in visible


def test_tennis_retains_actual_data_age_in_details_and_limitations_in_view():
    from test_daily3_selection import tennis
    signal = tennis()
    analysis = build_forecast_analysis(signal, now=NOW)
    result = build_compact_analysis(signal, analysis, now=NOW)
    markup = render_compact_analysis_html(result)
    visible = InitialText(markup).visible
    assert 'Sand' in visible and 'Aufschlagdaten berücksichtigt' in visible
    assert 'Verletzungs-/Müdigkeitseffekte nicht belegt' in visible
    assert analysis.data_age in ' '.join(result.explanation)


def test_absence_metadata_deduplicates_players_without_changing_model_decisions():
    def player(pid, name, kind='Missing Fixture', team=10):
        return {'team': {'id': team}, 'player': {'id': pid, 'name': name, 'type': kind}}
    missing = player(1, 'Heim A')
    passed, result, reason = _injury_summary([
        missing, deepcopy(missing), player(2, 'Heim fraglich', 'Questionable'),
        player(3, 'Gast A', team=11)], 10, 11, True)
    assert passed is True and reason is None
    assert result['home_missing'] == 1 and result['away_missing'] == 1
    assert result['home_questionable'] == 1
    assert result['home_missing_names'] == ['Heim A']
    assert result['home_questionable_names'] == ['Heim fraglich']
    assert result['away_missing_names'] == ['Gast A']
    assert result['impact_assessment_complete'] is False
    assert result['material_vetoes'] == []


def test_display_changes_do_not_change_probabilities_prices_or_daily3_choices():
    from daily3_selection import daily3_choices
    from test_daily3_selection import football
    pool = [football(i, probability=.8) for i in range(1, 4)]
    before = deepcopy([vars(s) for s in pool])
    keys = [c.signal.key for c in daily3_choices(pool, now=NOW)]
    for signal in pool:
        analysis = build_forecast_analysis(signal, now=NOW)
        left = build_compact_analysis(signal, analysis, now=NOW)
        right = build_compact_analysis(replace(signal, minimum_odds=999), analysis, now=NOW)
        assert left == right
        render_compact_analysis_html(left)
    assert [vars(s) for s in pool] == before
    assert [c.signal.key for c in daily3_choices(pool, now=NOW)] == keys
