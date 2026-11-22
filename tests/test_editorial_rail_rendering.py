"""Selection labels at the Streamlit boundary (offline; no publication run)."""
import pytest
from streamlit.testing.v1 import AppTest


def _render_mixed_rail(conflicting_winner=False):
    from dataclasses import replace
    from app import _render_editorial_rail
    from daily3_selection import daily3_choices, doublebet_preview_choices
    from test_daily3_selection import NOW, _admitted, _admitted_football, tennis
    from wettfinder_surface import build_wettfinder_card

    today, = daily3_choices([_admitted_football(1, 'HOME_UNDER_2_5')], now=NOW)
    preview, = doublebet_preview_choices([_admitted_football(2, 'AWAY_UNDER_2_5', start_hours=32)], now=NOW)
    # Raw original names may contain HTML-significant characters on either side.
    today = replace(today, signal=replace(today.signal, home_team='FC <Rot>',
                                         event_label='FC <Rot> vs Auswärtsteam 1'))
    preview = replace(preview, signal=replace(preview.signal, away_team='Blau & Weiß',
                                              event_label='Heimteam 2 vs Blau & Weiß'))
    bound_name = 'Spieler A' if conflicting_winner else 'Spieler B'
    original = replace(tennis(), selection=bound_name, selected_competitor=bound_name)
    winner, = daily3_choices([_admitted(original)], now=NOW)
    tennis_signal = replace(winner.signal, selection='Spieler B')
    tennis_card = build_wettfinder_card(tennis_signal, now=NOW)
    _render_editorial_rail((today, replace(winner, signal=tennis_signal)), (tennis_card,),
                           daily3_allowed=True, target_label='Heute', as_of=NOW, preview_choices=(preview,))


@pytest.fixture
def rail(monkeypatch, tmp_path):
    monkeypatch.setattr('runtime_paths.RUNTIME_STATE_DIR', tmp_path)
    rendered = AppTest.from_function(_render_mixed_rail).run(timeout=30)
    assert not rendered.exception
    return [item.value for item in rendered.markdown]


@pytest.mark.parametrize(('event', 'bet'), [
    ('FC &lt;Rot&gt; vs Auswärtsteam 1', 'FC &lt;Rot&gt;: Unter 2,5 Tore'),
    ('Heimteam 2 vs Blau &amp; Weiß', 'Blau &amp; Weiß: Unter 2,5 Tore'),
])
def test_doublebet_today_and_preview_name_the_exact_team_in_the_selection(rail, event, bet):
    row, = (html for html in rail if 'se-rail-choice' in html and event in html)
    assert '<span>' + bet + '</span>' in row


def test_tennis_picture_card_names_the_winner_market_not_just_the_player(rail):
    card, = (html for html in rail if 'se-tennis-copy' in html)
    assert '<p>Sieg Spieler B · 76' in card


def test_conflicting_winner_is_not_asserted_in_either_doublebet_or_tennis_card(monkeypatch, tmp_path):
    monkeypatch.setattr('runtime_paths.RUNTIME_STATE_DIR', tmp_path)
    rendered = AppTest.from_function(_render_mixed_rail, args=(True,)).run(timeout=30)
    assert not rendered.exception
    rows = [item.value for item in rendered.markdown if 'Spieler A vs Spieler B' in item.value]
    assert len(rows) == 2  # selected Doublebet signal and the independently built tennis card
    for row in rows:
        assert 'Siegauswahl nicht eindeutig' in row
        assert 'Sieg Spieler A' not in row and 'Sieg Spieler B' not in row
