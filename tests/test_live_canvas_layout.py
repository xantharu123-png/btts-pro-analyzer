"""Live is a full-page scoreboard with a single, immediately visible detail pane."""
from streamlit.testing.v1 import AppTest


def _live_board(*, highest=3, malformed_league=False):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    import streamlit as st
    from live_football_board import Game, render_board

    now = datetime.now(timezone.utc)
    numbers = range(1, 8)
    games = [
        Game(n, f"Heim {n} – Gast {n}", "45+3′", "1:0", None,
             {"league": "Unbekannt" if malformed_league and n == 1 else
                        {"id": 207, "name": "Testliga", "country": "Switzerland"},
              "teams": {"home": {"name": f"Heim {n}"}, "away": {"name": f"Gast {n}"}},
              "fixture": {"id": n, "status": {"short": "1H", "elapsed": 45, "extra": 3}}},
             now, now) for n in numbers
    ]

    def publish_pick(game, pair, emit):
        emit(pair[0])
        return True

    choices = {n: (SimpleNamespace(selection=pick, market="Team trifft noch",
                                   model_probability=prob, blockers=()), {}, False)
               for n, pick, prob in ((2, "Heim 2 trifft noch", 65.0), (3, "Gast 3 trifft noch", 68.0))}
    preferred_id = st.session_state.get("test_preferred_id", highest)
    render_board(st, games, choices, preferred_id=preferred_id, format_time=lambda _: "14:20",
                 publish_pick=publish_pick, reasons={1: "Geprüft – kein Tipp"}, now=now)


def _keyed_child(parent, key):
    return next((e for e in parent.children.values()
                 if getattr(getattr(e, "proto", None), "id", "").endswith(f"-{key}")), None)


def _inspector(screen):
    return " ".join(node.value for node in screen.markdown
                    if 'class="lv-' in node.value and ("lv-pick" in node.value or "lv-no-pick" in node.value))


def test_all_game_ideas_are_readable_before_selecting_an_inspector():
    screen = AppTest.from_function(_live_board).run()
    assert not screen.exception
    nodes = list(screen.main)
    detail = next(i for i, el in enumerate(nodes) if "lv-scoreline" in str(getattr(el, "value", "")))
    scores = next(i for i, el in enumerate(nodes) if getattr(el, "key", None) == "live_fixture_1")
    assert scores < detail
    assert "Heim 2 trifft noch" in screen.button(key="live_fixture_2").label
    assert "Gast 3 trifft noch" in screen.button(key="live_fixture_3").label


def test_seven_live_fixtures_are_in_page_flow_not_a_fixed_height_scroll_box():
    screen = AppTest.from_function(_live_board).run()
    assert not screen.exception
    assert [button.key for button in screen.button] == [f"live_fixture_{n}" for n in range(1, 8)]
    assert not [
        el for el in screen.main
        if hasattr(getattr(el, "proto", None), "height_config")
        and el.proto.height_config.WhichOneof("height_spec") == "pixel_height"
    ]


def test_invalid_optional_league_metadata_does_not_hide_the_scoreboard():
    screen = AppTest.from_function(_live_board, kwargs={"malformed_league": True}).run()
    assert not screen.exception
    assert "1:0" in screen.button(key="live_fixture_1").label
    assert any("Testliga" in node.value and "lv-league" in node.value for node in screen.markdown)


def test_styled_html_sections_use_intrinsic_height_and_native_buttons_fill_the_scoreboard():
    from editorial_theme import editorial_css
    css = editorial_css()
    assert '.lv-list-title span,' not in css, 'Text inside a Streamlit heading must inherit its heading font'
    # Streamlit's prose rules compensate for a missing trailing paragraph margin.
    # The bespoke scoreboard writes divs/headings instead, so must opt out.
    assert '.st-key-live_board [data-testid="stMarkdownContainer"]:has([class^="lv-"]) {margin-bottom:0' in css
    assert 'button span[data-has-shortcut]' in css
    # Streamlit wraps each keyed child; its actual grid item must not swallow
    # the inspector's mobile grid-row and desktop sticky positioning.
    assert '[data-testid="stLayoutWrapper"]:has(> :is(.st-key-live_detail,.st-key-live_scoreboard)) {display:contents;}' in css


def test_best_candidate_opens_first_and_click_can_hold_a_game_without_a_tip():
    screen = AppTest.from_function(_live_board).run()
    assert not screen.exception
    assert "Gast 3 trifft noch" in _inspector(screen)
    screen.button(key="live_fixture_1").click().run()
    assert not screen.exception
    assert "Geprüft – kein Tipp" in _inspector(screen)
    assert "Gast 3 trifft noch" not in _inspector(screen)
    screen.run()
    assert "Geprüft – kein Tipp" in _inspector(screen)


def test_resume_automatic_follows_the_current_best_and_its_successor():
    screen = AppTest.from_function(_live_board).run()
    assert not any(button.key == "live_resume_automatic" for button in screen.button)
    screen.button(key="live_fixture_1").click().run()
    assert "Geprüft – kein Tipp" in _inspector(screen)
    screen.session_state["test_preferred_id"] = 2
    screen.button(key="live_resume_automatic").click().run()
    assert not screen.exception
    assert "Heim 2 trifft noch" in _inspector(screen)
    assert not any(button.key == "live_resume_automatic" for button in screen.button)
    screen.session_state["test_preferred_id"] = 3
    screen.run()
    assert "Gast 3 trifft noch" in _inspector(screen)


def _live_main():
    import app
    app.main()


def test_live_dispatch_is_in_a_page_level_container_not_a_column(monkeypatch):
    import app
    import streamlit as st

    monkeypatch.setattr(app, "bind_customer", lambda _ui: True)
    monkeypatch.setattr(app, "require_feature", lambda _ui, _feature: None)
    monkeypatch.setattr(app, "_session_scope_id", lambda: "offline-layout")
    monkeypatch.setattr(app, "get_analyzer", lambda *_args: object())
    monkeypatch.setattr(app, "_render_sidebar", lambda _analyzer: "Live")
    monkeypatch.setattr(app, "render_live", lambda _analyzer: st.write("Spielstand-Prüfung"))
    monkeypatch.setattr(app, "render_legal_footer", lambda _ui: None)
    screen = AppTest.from_function(_live_main).run(timeout=30)
    assert not screen.exception
    canvas = _keyed_child(screen.main, "live_page")
    assert canvas is not None
    assert any(node.value == "Spielstand-Prüfung" for node in canvas.markdown)
    assert len(screen.sidebar.markdown) == 0


def test_new_visit_starts_automatic_but_regular_ticks_preserve_clicked_game(monkeypatch):
    import app
    import streamlit as st

    monkeypatch.setattr(app, "bind_customer", lambda _: True)
    monkeypatch.setattr(app, "require_feature", lambda *_: None)
    monkeypatch.setattr(app, "_session_scope_id", lambda: "offline-nav")
    monkeypatch.setattr(app, "get_analyzer", lambda *_: object())
    monkeypatch.setattr(app, "_render_sidebar", lambda _: st.session_state.get("test_view", "Live"))
    monkeypatch.setattr(app, "render_live", lambda _: _live_board())
    monkeypatch.setattr(app, "render_wettfinder", lambda: st.write("Wettfinder geöffnet"))
    monkeypatch.setattr(app, "render_legal_footer", lambda _: None)
    view = AppTest.from_function(_live_main).run(timeout=30)
    view.button(key="live_fixture_2").click().run()
    view.run()
    assert not view.exception and "Heim 2 trifft noch" in _inspector(view)
    view.session_state["test_view"] = "Wettfinder"
    view.run()
    assert not view.exception and any(el.value == "Wettfinder geöffnet" for el in view.markdown)
    view.session_state["test_view"] = "Live"
    view.run()
    assert not view.exception and "Gast 3 trifft noch" in _inspector(view)


def test_pitch_image_is_a_decodable_local_asset_embedded_only_for_live():
    import base64
    from io import BytesIO
    import re

    from PIL import Image
    import editorial_theme

    assert "data:image/webp" not in editorial_theme.editorial_css()
    exported = getattr(editorial_theme, "live_pitch_css", lambda: "")()
    embedded = re.search(r"data:image/webp;base64,([A-Za-z0-9+/=]+)", exported)
    assert embedded, "Live inspector needs its local pitch image without requesting an image service"
    raw = base64.b64decode(embedded.group(1), validate=True)
    with Image.open(BytesIO(raw)) as img:
        assert img.format == "WEBP" and img.width > img.height
        img.verify()
