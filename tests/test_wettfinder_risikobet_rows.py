"""Owner 15.11.2026: the Wettfinder game list in the RisikoBet look („ganz wie RisikoBet“)."""
from dataclasses import replace

import pytest

import app
from test_wettfinder_game_groups import card
from test_workflow_integrity import _RecordingStreamlit
from wettfinder_surface import format_probability, render_wettfinder_row_html


def test_row_shows_sport_league_kickoff_pick_model_and_reasons_like_risikobet():
    c = card()
    html = render_wettfinder_row_html(c, competition='UEFA <Nations> League')
    assert html.startswith('<article class="rb-row wf-rb-row"')
    meta = html.split('<span class="rb-row-meta">')[1].split('</span>')[0]
    assert meta == f'{c.sport} · UEFA &lt;Nations&gt; League · {c.scheduled_start_label}'
    assert f'<strong>{c.event_label}</strong>' in html
    assert f'<strong>{c.display_selection or c.selection}</strong>' in html
    assert f'Modell <strong>{format_probability(c.model_probability)}</strong>' in html
    assert '<b>Grundlage:</b> ' + c.compact_analysis.summary in html
    for absent in ('class="se-event', 'class="se-shield', 'Mindestquote', 'Buchmacher'):
        assert absent not in html


def test_row_without_league_or_reasons_keeps_a_clean_head():
    c = replace(card(), compact_analysis=None, analysis_basis='', analysis_caution='')
    html = render_wettfinder_row_html(c)
    meta = html.split('<span class="rb-row-meta">')[1].split('</span>')[0]
    assert meta == f'{c.sport} · {c.scheduled_start_label}'
    assert '<div class="rb-row-reasons"></div>' in html


def test_caution_is_the_contra_line_and_highlights_get_no_visible_badge():
    c = replace(card(), analysis_caution='Gegner stark in Form')
    html = render_wettfinder_row_html(c, featured=True)
    assert '<b>Contra:</b> Gegner stark in Form' in html
    assert 'data-featured="true"' in html
    assert 'MODELL-AUSWAHL' not in html.upper()


LONG_CONTEXT = ('H2H geprüft, kein belastbares Veto · Ausfälle nicht verfügbar · Wetter geprüft · '
                'Aufstellungen für vollständige Bestätigung noch offen')


def test_context_is_a_small_line_never_a_badge_and_can_be_left_out():
    # Live on 15.11.2026 the long context sentence filled an uppercase pill on every market.
    c = replace(card(), context_label=LONG_CONTEXT)
    html = render_wettfinder_row_html(c)
    assert 'rb-badge' not in html and 'rb-row-status' not in html
    assert f'<span class="rb-row-missing">Kontext: {LONG_CONTEXT}</span>' in html
    assert 'Kontext:' not in render_wettfinder_row_html(c, show_context=False)
    assert 'Kontext:' not in render_wettfinder_row_html(replace(c, context_label='ausstehend'))


def test_game_card_shows_the_context_once_on_its_first_row(monkeypatch):
    from wettfinder_surface import WettfinderCatalog
    first, second = (replace(card(1, key), context_label=LONG_CONTEXT) for key in ('AWAY_OVER_2_5', 'DC_X2'))
    other = replace(card(2, 'BTTS_YES'), context_label=LONG_CONTEXT)
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(WettfinderCatalog((first,), (second, other), ()),
                                 {c.key: (None, c) for c in (first, second, other)}, sport_filter='Alle')
    rows = [text for text, _kwargs, _context in recording.markdown_calls if 'class="rb-row wf-rb-row"' in text]
    assert len(rows) == 3
    assert [('Kontext:' in text) for text in rows] == [True, False, True]


@pytest.mark.parametrize('row,expected', [
    ({'competition': 'NHL', 'league_id': 39}, 'NHL'),
    ({'league_id': 5}, 'UEFA Nations League'),
    ({'league_id': 141}, 'Spain: Segunda División'),
    ({'league_id': 39}, 'England: Premier League'),
    ({'competition': '  ', 'league_id': 999999}, None),
    ({'league_id': True}, None),
    ({'league_id': '39'}, None),
    ({}, None),
])
def test_stored_row_league_label_for_the_row_head(row, expected):
    from ev_signal_sources import row_competition
    assert row_competition(row) == expected


def test_stylesheet_gives_the_wettfinder_list_the_risikobet_row_rules(monkeypatch):
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._apply_app_styles()
    css = next(text for text, _kwargs, _context in recording.markdown_calls if '<style>' in text)
    assert css.count('<style>') == 1 and css.count('</style>') == 1
    # RisikoBet keeps its own rules; the Wettfinder list gets the same ones under its keys.
    assert '.st-key-riskobet_page .rb-row {' in css
    assert '.st-key-wettfinder_v2_additional .rb-row {' in css
    assert '[class*="st-key-wettfinder_game_row_"]' in css
    assert css.index('.st-key-wettfinder_v2_additional .rb-row {') < css.index('</style>')


# --- Owner 17.11.2026: „es sieht nicht wirklich wie das vom RisikoBet aus“ -----------------------------------------
# The game details now follow the RisikoBet detail: goal table, recent results as plain lines, closed drawer.

WALES = [(1, 3), (0, 1), (2, 1), (0, 2), (0, 1), (1, 1), (3, 0), (2, 2), (1, 0), (0, 0)]
PORTUGAL = [(1, 4), (2, 1), (4, 2), (2, 1), (1, 0), (2, 0), (0, 0), (3, 1), (1, 2), (2, 2)]


def _forms(count=10):
    from sports_form import FormResult, TeamForm

    def side(team, scores):
        return TeamForm(team, 'Letzte Spiele · alle Spielorte', tuple(
            FormResult('S' if a > b else 'N' if a < b else 'U', f'{a}:{b}', f'Gegner {index}',
                       f'2026-10-{30 - index:02d}T18:00:00+00:00', 'Liga', 'Heim')
            for index, (a, b) in enumerate(scores[:count], 1)))
    return side('Wales', WALES), side('Portugal', PORTUGAL)


def test_goal_table_uses_the_risikobet_detail_layout():
    from sports_form import GOAL_HISTORY_NOTE, render_goal_history_html
    html = render_goal_history_html(_forms(), instance_key='k')
    assert html.startswith('<section class="sports-form" aria-label="Historische Multigoal-Treffer">'
                           '<div class="form-heading"><h4>Multigoal &amp; Sieg-Kombis</h4>'
                           '<div class="form-toggle" role="group" aria-label="Anzahl Spiele">')
    assert f'<small>{GOAL_HISTORY_NOTE}</small>' in html
    head = '<th scope="col">Gesamttore</th><th scope="col">Wales</th><th scope="col">Portugal</th>'
    assert html.count(head) == 2
    assert 'form-window-5' in html and 'form-window-10' in html and 'value="10"' in html
    assert '<tr><th scope="row">1–3 Tore</th><td>4/5</td><td>3/5</td></tr>' in html
    assert '<tr><th scope="row">Sieg + 1–3</th><td>1/5</td><td>3/5</td></tr>' in html
    for absent in ('Aktuelle Form', 'form-result', 'form-team', 'Gegner &', 'checked', 'Letzte Spiele'):
        assert absent not in html
    assert render_goal_history_html(_forms(), instance_key='other').count('goals-') == html.count('goals-')
    assert render_goal_history_html(_forms(), instance_key='other') != html  # own radio group per card


def test_goal_table_offers_ten_games_only_with_ten_results_per_side():
    from sports_form import render_goal_history_html
    html = render_goal_history_html(_forms(7))
    assert 'form-ten-unavailable' in html and 'form-window-10' not in html and 'value="10"' not in html
    assert render_goal_history_html(()) == ''
    assert render_goal_history_html(_forms()[:1]) == ''


def test_goal_table_markup_is_the_one_of_the_risikobet_page():
    import inspect
    import riskobet_ui
    import sports_form
    risk = inspect.getsource(riskobet_ui._football_goal_history_html)
    ours = inspect.getsource(sports_form.render_goal_history_html)
    for fragment in ('<section class="sports-form" aria-label="Historische Multigoal-Treffer">',
                     '<div class="form-heading"><h4>Multigoal &amp; Sieg-Kombis</h4>',
                     '<div class="form-toggle" role="group" aria-label="Anzahl Spiele">',
                     'aria-label="5 Spiele (Standardansicht)">',
                     '<section class="form-goal-markets">',
                     '<table><thead><tr><th scope="col">Gesamttore</th>'):
        assert fragment in risk and fragment in ours, fragment
    assert sports_form.GOAL_HISTORY_NOTE in risk


def test_recent_results_are_plain_lines_like_the_risikobet_detail():
    from sports_form import FormResult, TeamForm, form_text_lines
    wales, portugal = form_text_lines(_forms())
    assert wales.startswith('Wales: 1S · 0U · 4N (5) / 3S · 3U · 4N (10); Gegner (10): Gegner 1 1:3; Gegner 2 0:1; ')
    assert wales.endswith('Gegner 10 0:0')
    assert portugal.startswith('Portugal: 4S · 0U · 1N (5) / 6S · 2U · 2N (10); Gegner (10): Gegner 1 1:4; ')
    assert form_text_lines(_forms(7))[0].startswith('Wales: 1S · 0U · 4N (5); Gegner (7): ')
    assert form_text_lines(_forms(3))[0] == 'Wales: 1S · 0U · 2N (3 erfasst); Gegner (3): Gegner 1 1:3; Gegner 2 0:1; Gegner 3 2:1'
    # Sports without draws: wins per window like the RisikoBet tennis lines, surface once.
    wins = (True, True, False, True, True, False, True, False, False, True)
    tennis = tuple(TeamForm(name, 'Hartplatz', tuple(FormResult('S' if won else 'N') for won in wins))
                   for name in ('Ben Shelton', 'Alexander Zverev'))
    expected = ('Belag: Hartplatz', 'Ben Shelton: 4/5 Siege · 6/10 Siege', 'Alexander Zverev: 4/5 Siege · 6/10 Siege')
    assert form_text_lines(tennis) == expected
    # Real tennis rows name opponent and sets. The RisikoBet tennis card shows the record only, so does this
    # line; the single results are in the drawer.
    with_opponents = tuple(TeamForm(name, 'Hartplatz', tuple(
        FormResult('S' if won else 'N', '2:0' if won else '1:2', f'Gegner {index}', rank=20 + index)
        for index, won in enumerate(wins))) for name in ('Ben Shelton', 'Alexander Zverev'))
    assert form_text_lines(with_opponents) == expected
    assert form_text_lines((TeamForm('Team A', 'Serien · erfasste Reihenfolge',
                                     tuple(FormResult('S') for _ in range(4))),)) == ('Team A: 4/4 Siege',)
    assert form_text_lines(()) == ()


def test_long_opponent_lists_fall_back_to_five_results_like_risikobet():
    from sports_form import FormResult, TeamForm, form_text_lines
    long_name = 'Sehr langer Vereinsname mit vielen Zeichen und Zusatz '
    form = TeamForm('Heim', 'Letzte Spiele · alle Spielorte', tuple(
        FormResult('S', '2:0', f'{long_name}{index}') for index in range(10)))
    line, = form_text_lines((form,))
    assert len(line) <= 600 and '; Gegner (5): ' in line and line.startswith('Heim: 5S · 0U · 0N (5) / 10S · 0U · 0N (10)')


def test_analysis_drawer_lines_carry_facts_details_and_known_results_once():
    from forecast_compact import CompactAnalysis, Fact, compact_analysis_alerts, compact_analysis_lines
    compact = CompactAnalysis('Kurz', (
        Fact('Gegenrisiko', 'mindestens 3 Tore: 20,8 %', ('mindestens 3 Tore', 'Modellschätzung.')),
        Fact('Form Wales', '1S · 0U · 1N'),
        Fact('Basis', '12 / 12 A-Länderspiele', ('Modellschätzung.',)),
        # A football market fact lists the games it counted (other date format, „Gast“ instead of „Auswärts“).
        Fact('Wales-Spiele · mindestens 3 Tore insgesamt', '1/2 zuletzt', (
            'Wales · 2026-10-29 · Gegner 1: 1:3 (Heim; Liga)', 'Wales · 2026-10-28 · Gegner 2: 0:1 (Heim; Liga)',
            'Gezählt sind erfasste Spiele.')),
    ), ('Außenseiter-Szenario', 'Ligavergleich nicht bestätigt'), (), 'Stand', _forms(2), True)
    lines = compact_analysis_lines(compact)
    # „mindestens 3 Tore“ only repeats its own headline and is left out; a repeated detail appears once.
    assert lines[:5] == ('Gegenrisiko: mindestens 3 Tore: 20,8 %', 'Modellschätzung.',
                         'Basis: 12 / 12 A-Länderspiele',
                         'Wales-Spiele · mindestens 3 Tore insgesamt: 1/2 zuletzt', 'Gezählt sind erfasste Spiele.')
    assert len(lines) == len(set(lines))
    # Every game stands once, in the drawer's own format, not a second time from the market fact.
    assert not any('2026-10-29' in line or '2026-10-28' in line for line in lines)
    assert sum('Gegner 1: 1:3' in line for line in lines) == 1
    assert not any(line.startswith('Form Wales') for line in lines)
    assert 'Wales: Letzte Spiele · alle Spielorte' in lines
    assert 'Wales · 29.10.2026 · Gegner 1: 1:3 (Niederlage; Heim; Liga)' in lines
    assert 'Portugal · 28.10.2026 · Gegner 2: 2:1 (Sieg; Heim; Liga)' in lines
    # Internal method notes stay out, as on the card before.
    assert compact_analysis_alerts(compact) == ('Außenseiter-Szenario',)


def test_two_equal_results_stay_two_games_in_the_drawer():
    from forecast_compact import CompactAnalysis, compact_analysis_lines
    from sports_form import FormResult, TeamForm
    twice = TeamForm('Jannik Sinner', 'Hartplatz', tuple(
        FormResult('S', '2:0', 'Taylor Fritz', '2026-11-10', 'Turnierdatum') for _ in range(2)))
    lines = compact_analysis_lines(CompactAnalysis('Kurz', (), (), (), 'Stand', (twice,), False))
    assert lines == ('Jannik Sinner: Hartplatz',) + (
        'Jannik Sinner · 10.11.2026 · Taylor Fritz: 2:0 (Sieg; Turnierdatum)',) * 2


def test_team_sport_lines_use_the_customer_sentence_of_the_risikobet_card():
    from forecast_compact import CompactAnalysis, Fact, compact_analysis_lines, compact_form_lines
    from sports_form import form_text_lines
    sentence = 'Boston Bruins: 4/5 Siege · 6/10 Siege; zuletzt: S 3:2 gegen Team 1, N 1:4 gegen Team 2'
    series = 'Letzte 5 Serien: Team A 4/5 Siege · Team B 3/5 Siege.'
    compact = CompactAnalysis('Kurz', (
        Fact('Letzte Spiele', 'Boston Bruins', (sentence,)), Fact('Letzte Spiele', 'Letzte 5 Serien', (series,)),
        Fact('Gegenargument', 'Gegenseite', ('Die Gegenseite gewann zuletzt öfter.',)),
    ), (), (), 'Stand', (), False)
    # The sentence RisikoBet shows is the line under the table and is not repeated in the drawer.
    assert compact_form_lines(compact) == (sentence, series)
    assert compact_analysis_lines(compact) == ('Gegenargument: Gegenseite', 'Die Gegenseite gewann zuletzt öfter.')
    # Football and tennis have no such sentence: their lines come from the validated result rows.
    football = CompactAnalysis('Kurz', (), (), (), 'Stand', _forms(), True)
    assert compact_form_lines(football) == form_text_lines(_forms())


def test_plain_markdown_keeps_names_and_results_literal():
    from wettfinder_surface import plain_markdown
    assert plain_markdown('1. FC Köln: 3S · 1U · 1N (5)') == r'1\. FC Köln: 3S · 1U · 1N \(5\)'
    assert plain_markdown('A [x](https://invalid) *b* $1$') == r'A \[x\]\(https://invalid\) \*b\* \$1\$'
    assert plain_markdown('- minus\nzwei') == r'\- minus zwei'
    assert plain_markdown('Wales: 1S · 0U · 4N; Gegner 1 1:3') == 'Wales: 1S · 0U · 4N; Gegner 1 1:3'


def _render_one_game(monkeypatch, c):
    from wettfinder_surface import WettfinderCatalog
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(WettfinderCatalog((c,), (), ()), {c.key: (None, c)}, sport_filter='Alle')
    return recording


def test_game_card_details_follow_the_risikobet_order_without_result_tiles(monkeypatch):
    c = card()
    c = replace(c, compact_analysis=replace(c.compact_analysis, forms=_forms(), football_goal_history=True,
                                            warnings=('Außenseiter-Szenario', 'Ligavergleich nicht bestätigt')))
    recording = _render_one_game(monkeypatch, c)
    assert ('markdown', '## Spiele') in recording.event_log
    html = '\n'.join(text for text, _kwargs, _context in recording.markdown_calls)
    assert html.index('class="rb-row wf-rb-row"') < html.index('<h4>Multigoal &amp; Sieg-Kombis</h4>')
    for absent in ('Aktuelle Form', 'class="form-result', 'form-opponent', 'class="wf-fact', 'wf-analysis',
                   'wf-additional-heading'):
        assert absent not in html
    captions = [value for kind, value in recording.messages if kind == 'caption']
    assert any(value.startswith(r'Wales: 1S · 0U · 4N \(5\) / 3S · 3U · 4N \(10\); Gegner \(10\): ')
               for value in captions)
    assert any(value.startswith(r'Portugal: 4S · 0U · 1N \(5\) / 6S · 2U · 2N \(10\); ') for value in captions)
    # One closed drawer per game, like „Analyse anzeigen“ on the RisikoBet page; the game itself stays open.
    assert recording.expanders == [('Analyse anzeigen', False)]
    assert recording.expander_keys[0].startswith('wettfinder_game_analysis_')
    # The drawer is one element with one paragraph per line (Streamlit builds closed drawers on every rerun).
    drawer, = [text for text, _kwargs, context in recording.markdown_calls
               if any(kind == 'expander' for kind, _label in context)]
    paragraphs = drawer.split('\n\n')
    assert paragraphs[0].startswith('Gegenrisiko: ')
    assert any(line.startswith(r'Wales · 29.10.2026 · Gegner 1: 1:3 \(Niederlage') for line in paragraphs)
    assert not [value for kind, value in recording.messages if kind == 'write']
    # The RisikoBet detail order: table, result lines, visible warning, drawer. Internal notes stay out.
    shown = [(kind, str(value)) for kind, value in recording.messages]

    def position(kind, text):
        return next(index for index, (k, v) in enumerate(shown) if k == kind and text in v)

    assert (position('markdown', 'Multigoal') < position('caption', 'Wales:') < position('caption', 'Portugal:')
            < position('caption', 'Außenseiter-Szenario') < position('markdown', 'Gegenrisiko: '))
    assert not any('Ligavergleich' in value for _kind, value in shown)
    order = [kind if kind == 'expander' else 'table' for kind, value in recording.event_log
             if kind == 'expander' or kind == 'markdown' and 'Multigoal' in value]
    assert order == ['table', 'expander']


def test_bookmark_stays_with_each_market_and_every_game_has_one_drawer(monkeypatch):
    from types import SimpleNamespace
    from wettfinder_surface import WettfinderCatalog
    first, second, other = card(1, 'AWAY_OVER_2_5'), card(1), card(2, 'BTTS_YES')
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    calls = []
    monkeypatch.setattr(app, '_automated_signal_candidate', lambda signal: signal)
    monkeypatch.setattr(app, 'render_tip_bookmark', lambda candidate, *, key, source: calls.append(
        (key, source, tuple(recording.context_stack))))
    signal = SimpleNamespace(competition=None)
    app._render_wettfinder_games(WettfinderCatalog((first,), (second, other), ()),
                                 {c.key: (signal, c) for c in (first, second, other)}, sport_filter='Alle')
    # „Tipp merken“ once per market, inside that market's own container, never in the drawer.
    assert len(calls) == 3 and len({key for key, _source, _context in calls}) == 3
    for _key, source, context in calls:
        assert source == 'Wettfinder'
        assert context[-1][0] == 'container' and str(context[-1][1]).startswith('wettfinder_v2_game_market_')
        assert not any(kind == 'expander' for kind, _label in context)
    # Two games, two closed drawers with their own keys; the game with two markets still has one.
    assert recording.expanders == [('Analyse anzeigen', False)] * 2
    assert len(set(recording.expander_keys)) == 2


def test_tennis_card_shows_surface_and_records_only_and_single_results_in_the_drawer(monkeypatch):
    from test_sports_editorial import NOW as EDITORIAL_NOW, editorial_tennis
    from wettfinder_surface import build_wettfinder_card
    c = build_wettfinder_card(editorial_tennis(), now=EDITORIAL_NOW)
    assert len(c.compact_analysis.forms) == 2
    recording = _render_one_game(monkeypatch, c)
    html = '\n'.join(text for text, _kwargs, _context in recording.markdown_calls)
    assert 'Multigoal' not in html and 'class="form-result' not in html
    captions = [value for kind, value in recording.messages if kind == 'caption']
    assert captions[0] == 'Belag: Sand'
    records = [value for value in captions[1:] if 'Siege' in value]
    # Like the RisikoBet tennis card: the record per player, no opponent list in the line.
    assert len(records) == 2 and all('Gegner' not in value and '/10 Siege' in value for value in records)
    assert recording.expanders == [('Analyse anzeigen', False)]
    drawer, = [text for text, _kwargs, context in recording.markdown_calls
               if any(kind == 'expander' for kind, _label in context)]
    assert 'Tennisspieler 1' in drawer and 'Damaliger Weltrang: 20' in drawer


def test_game_without_facts_or_results_gets_no_empty_drawer(monkeypatch):
    c = card()
    c = replace(c, compact_analysis=replace(c.compact_analysis, facts=(), forms=(), warnings=()))
    recording = _render_one_game(monkeypatch, c)
    assert recording.expanders == []
    assert 'Multigoal' not in '\n'.join(text for text, _kwargs, _context in recording.markdown_calls)


def test_games_sit_in_the_risikobet_grid_two_cards_per_row(monkeypatch):
    from wettfinder_surface import WettfinderCatalog
    cards = [card(1), card(2, 'BTTS_YES'), card(3, 'HOME_OVER_1_5')]
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(WettfinderCatalog((), tuple(cards), ()), {c.key: (None, c) for c in cards},
                                 sport_filter='Alle')
    assert 'wettfinder_game_grid' in recording.containers
    assert [len(group) for group in recording.column_groups] == [2, 2]
    columns = [next(label for kind, label in context if kind == 'column')
               for text, _kwargs, context in recording.markdown_calls if 'class="rb-row wf-rb-row"' in text]
    # Row-oriented: reading order and DOM order are the same, also when the columns stack on a phone.
    assert columns == ['column-0-0', 'column-0-1', 'column-1-0']


def test_stylesheet_gives_the_wettfinder_the_risikobet_grid_and_detail_rules(monkeypatch):
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._apply_app_styles()
    css = next(text for text, _kwargs, _context in recording.markdown_calls if '<style>' in text)
    # RisikoBet keeps its grid; the Wettfinder gets the same rules under its own keys.
    assert '.st-key-riskobet_featured_grid [data-testid="stColumn"]' in css
    assert '.st-key-wettfinder_game_grid [data-testid="stColumn"]' in css
    # The detail block has its own few rules; the RisikoBet action grid (two columns) is never copied onto
    # table, lines and drawer.
    assert '[class*="st-key-riskobet_actions_"] > [data-testid="stVerticalBlock"]' in css
    assert '[class*="st-key-wettfinder_game_details_"] {' in css
    assert '[class*="st-key-wettfinder_game_details_"] > [data-testid="stVerticalBlock"]' not in css
    # No line above the first row of a card; the heading size only where two cards share the main column.
    assert '[class*="st-key-wettfinder_game_row_"] > [class*="st-key-wettfinder_v2_game_market_"]:first-child' in css
    import re
    assert re.search(r'@media \(min-width: 761px\) \{\s*\.st-key-wettfinder_game_grid \.form-heading h4 \{', css)
    # The page layout's wide column gap must not push the second card of a row to the next line.
    assert ('.st-key-editorial_auto_layout .st-key-wettfinder_game_grid [data-testid="stHorizontalBlock"]'
            in css)
    assert '.st-key-wettfinder_v2_additional [class*="st-key-bookmark_"] button {' in css
