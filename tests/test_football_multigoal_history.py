"""Goal-range history is observed joint-event frequency, never model or odds."""
from copy import deepcopy
from dataclasses import replace

import pytest

import sports_form
from sports_form import FormResult, TeamForm
from forecast_compact import CompactAnalysis, render_compact_analysis_html


def forms():
    scores = (
        ((2, 0), (1, 1), (3, 1), (0, 1), (2, 3), (1, 0), (0, 0), (2, 1), (1, 3), (4, 0)),
        ((0, 2), (3, 0), (0, 0), (1, 2), (2, 1), (1, 0), (1, 4), (2, 2), (0, 1), (3, 2)),
    )
    return tuple(TeamForm(name, 'Letzte Spiele · alle Spielorte', tuple(
        FormResult('S' if left > right else 'U' if left == right else 'N', f'{left}:{right}')
        for left, right in rows)) for name, rows in zip(('Alpha', 'Beta'), scores))


def test_actual_five_game_ranges_and_joint_wins_are_counted_not_multiplied():
    rows = sports_form.football_goal_history_rows(forms(), 5)
    assert rows == (
        ('1–3 Tore', '3/5', '4/5'), ('1–4 Tore', '4/5', '4/5'),
        ('2–3 Tore', '2/5', '4/5'), ('2–4 Tore', '3/5', '4/5'),
        ('Sieg + 1–3', '1/5', '2/5'), ('Sieg + 1–4', '2/5', '2/5'),
        ('Sieg + 2–3', '1/5', '2/5'), ('Sieg + 2–4', '2/5', '2/5'),
    )


def test_actual_ten_game_history_uses_all_ten_not_the_first_five_again():
    rows = dict((label, (left, right)) for label, left, right
                in sports_form.football_goal_history_rows(forms(), 10))
    assert rows['1–3 Tore'] == ('5/10', '6/10')
    assert rows['1–4 Tore'] == ('8/10', '7/10')
    assert rows['2–3 Tore'] == ('3/10', '4/10')
    assert rows['2–4 Tore'] == ('6/10', '5/10')
    assert rows['Sieg + 1–3'] == ('3/10', '3/10')
    assert rows['Sieg + 1–4'] == ('5/10', '3/10')
    assert rows['Sieg + 2–3'] == ('2/10', '2/10')
    assert rows['Sieg + 2–4'] == ('4/10', '2/10')


def test_partial_history_reports_true_denominators_without_filling_missing_games():
    first, second = forms()
    short = (replace(first, results=first.results[:3]), replace(second, results=second.results[:2]))
    assert sports_form.football_goal_history_rows(short, 5)[0] == ('1–3 Tore', '2/3', '2/2')


@pytest.mark.parametrize('bad', ['', '2-0', '3:2 extra', '-1:2', '99:0'])
def test_unknown_or_malformed_score_does_not_become_zero_or_false_hit(bad):
    first, second = forms()
    first = replace(first, results=(replace(first.results[0], score=bad), *first.results[1:]))
    assert sports_form.football_goal_history_rows((first, second), 5) == ()


def test_contradictory_outcome_or_other_sport_cannot_be_counted_as_football():
    first, second = forms()
    wrong = replace(first, results=(replace(first.results[0], outcome='N'), *first.results[1:]))
    assert sports_form.football_goal_history_rows((wrong, second), 5) == ()
    assert sports_form.football_goal_history_rows((replace(first, scope='Hartplatz'), second), 5) == ()
    assert sports_form.football_goal_history_rows((first,), 5) == ()


def test_renderer_reuses_existing_five_ten_controls_and_escapes_teams():
    first, second = forms()
    given = (replace(first, team='<Alpha>'), replace(second, team='Beta & Co'))
    before = deepcopy(given)
    markup = sports_form.render_form_html(given, instance_key='fixture:42', include_goal_ranges=True)
    assert markup.count('class="form-goal-markets"') == 2
    assert 'Multigoal &amp; Sieg-Kombis' in markup
    assert 'Gesamttore · Treffer / Spiele' in markup
    assert '<th scope="col">&lt;Alpha&gt;</th>' in markup
    assert '<Alpha>' not in markup
    assert '<td>3/5</td>' in markup and '<td>5/10</td>' in markup
    assert 'Modellwahrscheinlichkeit' not in markup and 'Quote' not in markup
    assert given == before


def test_compact_primary_shows_history_once_secondary_or_other_sport_does_not():
    given = CompactAnalysis('Kurzcheck', (), (), (), 'heute', forms(), football_goal_history=True)
    assert 'Multigoal &amp; Sieg-Kombis' in render_compact_analysis_html(given)
    assert 'Multigoal &amp; Sieg-Kombis' not in render_compact_analysis_html(given, show_form=False)
    assert 'Multigoal &amp; Sieg-Kombis' not in render_compact_analysis_html(replace(given, football_goal_history=False))


def test_no_history_does_not_render_an_empty_statistics_block():
    assert sports_form.render_form_html((), include_goal_ranges=True) == ''


def test_real_card_projection_enables_history_without_changing_its_probability():
    from datetime import timedelta
    from test_football_recent_results import NOW, builder, game
    from test_forecast_analysis import _row, _basis, _signal
    from forecast_analysis import build_forecast_analysis, project_football_analysis
    from forecast_compact import build_compact_analysis
    row = _row('TOTAL_RANGE_1_3', .69)
    history = [game(20+i, score=(2, 1), age=i+1) for i in range(10)]
    history += [game(50+i, home=40, away=12, score=(2, 0), age=i+1) for i in range(10)]
    basis = {**_basis(row), 'customer_recent_results': builder(history, row)}
    row['analysis_evidence'] = project_football_analysis(row, model_basis=basis)
    signal = _signal(row)
    before = deepcopy(vars(signal))
    now = NOW+timedelta(hours=3)
    compact = build_compact_analysis(
        signal, build_forecast_analysis(signal, now=now), now=now)
    markup = render_compact_analysis_html(compact)
    assert compact.football_goal_history is True
    assert 'Multigoal &amp; Sieg-Kombis' in markup
    assert '<td>5/5</td>' in markup and '<td>0/5</td>' in markup
    assert vars(signal) == before
    assert signal.probability == .69


def test_wrong_fixture_history_never_leaks_into_the_range_statistics():
    from datetime import timedelta
    from test_football_recent_results import NOW, builder, game
    from test_forecast_analysis import _row, _basis, _signal
    from forecast_analysis import build_forecast_analysis, project_football_analysis
    from forecast_compact import build_compact_analysis
    row = _row('RESULT_HOME')
    recent = builder([game(20), game(50, home=40, away=12)], row)
    recent['fixture_id'] += 1
    row['analysis_evidence'] = project_football_analysis(row,
        model_basis={**_basis(row), 'customer_recent_results': recent})
    signal, now = _signal(row), NOW+timedelta(hours=3)
    compact = build_compact_analysis(signal, build_forecast_analysis(signal, now=now), now=now)
    assert 'Multigoal &amp; Sieg-Kombis' not in render_compact_analysis_html(compact)


def test_manual_multiple_markets_render_history_once_per_game_not_once_per_market(monkeypatch):
    from types import SimpleNamespace
    from manual_search_filters import SearchFilters
    from test_manual_football_filters import _render
    from test_manual_statistical_selection import candidate
    import football_customer_facts
    rows = [candidate(key, probability, skill, fixture=fixture) for fixture in (1, 2)
            for key, probability, skill in (('RESULT_HOME', .60, .15), ('TOTAL_UNDER_4_5', .85, .03))]
    render, surface, snapshot = _render(monkeypatch, rows)
    surface.markdown = lambda text, **_: surface.messages.append(text)
    monkeypatch.setattr(football_customer_facts, 'manual_football_customer_analysis',
        lambda *_args, **_kwargs: SimpleNamespace(summary='Kurzcheck', counterargument='Gegner',
            facts=(), fact_details=(), details=()))
    monkeypatch.setattr(sports_form, 'manual_football_forms', lambda *_args, **_kwargs: forms())
    before = deepcopy(snapshot)
    rendered = render(SearchFilters())
    assert len(rendered) == 4
    # Two views (5/10) per game, not per market. Distinct games must both retain it.
    assert ' '.join(surface.messages).count('class="form-goal-markets"') == 4
    assert snapshot == before
