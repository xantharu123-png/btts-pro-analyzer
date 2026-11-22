"""Live is a full-page scoreboard with a single, immediately visible detail pane."""
from streamlit.testing.v1 import AppTest


def _live_board(*, highest=3, malformed_league=False):
    from datetime import datetime, timezone

    import streamlit as st
    from live_football_board import Game, render_board

    now = datetime.now(timezone.utc)
    numbers = range(1, 8)
    games = [
        Game(n, f"Heim {n} – Gast {n}", "45+3′", "1:0", None,
             {"league": "Unbekannt" if malformed_league and n == 1 else {"name": "Testliga"}},
             now, now) for n in numbers
    ]

    def show(game, text):
        st.write(text)
        return True

    choices = {2: "Tipp zwei", 3: "Tipp drei"}
    preferred_id = st.session_state.get("test_preferred_id", highest)
    render_board(st, games, choices, preferred_id=preferred_id, format_time=lambda _: "14:20",
                 render_tip=show, reasons={}, now=now)


def _keyed_child(parent, key):
    return next((e for e in parent.children.values()
                 if getattr(getattr(e, "proto", None), "id", "").endswith(f"-{key}")), None)


def test_tip_precedes_native_scoreboard_in_document_order():
    screen = AppTest.from_function(_live_board).run()
    assert not screen.exception
    nodes = list(screen.main)
    detail = next(i for i, el in enumerate(nodes) if getattr(el, "value", None) == "Tipp drei")
    scores = next(i for i, el in enumerate(nodes) if getattr(el, "key", None) == "live_fixture_1")
    assert detail < scores


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
    assert "Testliga" in screen.button(key="live_fixture_2").label


def test_best_candidate_opens_first_and_click_can_hold_a_game_without_a_tip():
    screen = AppTest.from_function(_live_board).run()
    assert not screen.exception
    assert [node.value for node in screen.markdown if node.value.startswith("Tipp ")] == ["Tipp drei"]
    screen.button(key="live_fixture_1").click().run()
    assert not screen.exception
    assert any("Kein aktueller Modellvorschlag" in info.value for info in screen.info)
    assert not any(node.value.startswith("Tipp ") for node in screen.markdown)
    screen.run()
    assert any("Kein aktueller Modellvorschlag" in info.value for info in screen.info)


def test_resume_automatic_follows_the_current_best_and_its_successor():
    screen = AppTest.from_function(_live_board).run()
    assert not any(button.key == "live_resume_automatic" for button in screen.button)
    screen.button(key="live_fixture_1").click().run()
    assert any("Kein aktueller Modellvorschlag" in info.value for info in screen.info)
    screen.session_state["test_preferred_id"] = 2
    screen.button(key="live_resume_automatic").click().run()
    assert not screen.exception
    assert [node.value for node in screen.markdown if node.value.startswith("Tipp ")] == ["Tipp zwei"]
    assert not any(button.key == "live_resume_automatic" for button in screen.button)
    screen.session_state["test_preferred_id"] = 3
    screen.run()
    assert [node.value for node in screen.markdown if node.value.startswith("Tipp ")] == ["Tipp drei"]


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
    assert not view.exception and any(el.value == "Tipp zwei" for el in view.markdown)
    view.session_state["test_view"] = "Wettfinder"
    view.run()
    assert not view.exception and any(el.value == "Wettfinder geöffnet" for el in view.markdown)
    view.session_state["test_view"] = "Live"
    view.run()
    assert not view.exception and any(el.value == "Tipp drei" for el in view.markdown)
