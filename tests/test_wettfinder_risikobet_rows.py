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
