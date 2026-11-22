"""The open page and the actual selected game, never a background scan, own the live tip."""
from datetime import datetime, timedelta, timezone
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

import app
import bet_finder_ui
from test_live_tip_surface import Screen, _analysis


def feed_row(game, stamp, *, analysis=None, red=None):
    analysis = _analysis(game) if analysis is None else analysis
    fixture = {
        "fixture": {"id": game, "date": analysis.get("scheduled_start"),
                    "status": {"short": "1H", "elapsed": 45, "extra": 3}},
        "teams": {"home": {"id": game+100, "name": analysis["home_team"]},
                  "away": {"id": game+200, "name": analysis["away_team"]}},
        "goals": {"home": 1, "away": 0}, "league": {"id": 39, "name": "Testliga"},
        "offline_analysis": analysis, "offline_red": red,
    }
    return {"fixture": fixture, "observed_at": stamp, "detailed_at": stamp}


def mount(monkeypatch, ui, rows, *, connected=lambda: True, unavailable=False):
    ticks, checked = [], []
    def tick(source, *, now, viewer_active):
        if viewer_active():
            ticks.append(now)
        return rows
    def analyze(row, analyzer):
        checked.append(row["fixture"]["id"])
        return row.get("offline_analysis"), row.get("offline_red")
    monkeypatch.setattr(app, "st", ui)
    monkeypatch.setattr(bet_finder_ui, "st", ui)
    ui.fragment = lambda **kwargs: lambda fn: fn
    monkeypatch.setattr(app, "_live_session_connected", connected, raising=False)
    monkeypatch.setattr(app, "_analyze_ticker_fixture", analyze, raising=False)
    def current_detail(number, stamp, fixture):
        row = rows.get(number)
        return nullcontext(row is not None and stamp is not None and row["detailed_at"] == stamp and row["fixture"] == fixture)
    feed = SimpleNamespace(tick=tick, unavailable=unavailable, current_detail=current_detail)
    monkeypatch.setattr(app, "_live_ticker_resources", lambda key: (feed, object()), raising=False)
    monkeypatch.setattr(app, "load_app_config", lambda _st: SimpleNamespace(api_football_key="offline", freemode=False))
    return ticks, checked


def test_inactive_disconnected_or_revoked_view_cannot_tick(monkeypatch):
    import customer_access
    analyzer = SimpleNamespace()
    ui = Screen()
    connected = [True]
    ticks, checked = mount(monkeypatch, ui, {}, connected=lambda: connected[0])
    ui.session_state["workspace"] = "Wettfinder"
    app.render_live(analyzer)
    ui.session_state["workspace"] = "Live"
    connected[0] = False
    app.render_live(analyzer)
    connected[0] = True
    monkeypatch.setenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", "1")
    ui.session_state[customer_access.ACCESS_KEY] = {"account_id": "a"*32}
    ui.context = SimpleNamespace(cookies={})
    monkeypatch.setattr(customer_access, "fetch_access", lambda cookies: {"account_id":"a"*32, "features":["saved"]})
    app.render_live(analyzer)
    assert ticks == checked == []
    assert not any("Modell:" in str(value) for _, value in ui.messages)


@pytest.mark.parametrize("bad_detail", [None, -121, 60])
def test_stand_without_current_detail_has_no_model_or_receipt(monkeypatch, bad_detail):
    now = datetime.now(timezone.utc)
    row = feed_row(1, now)
    row["detailed_at"] = None if bad_detail is None else now+timedelta(seconds=bad_detail)
    ui = Screen({"workspace": "Live"})
    ticks, checked = mount(monkeypatch, ui, {1: row})
    writes = []
    monkeypatch.setattr(app, "record_visible_analysis", lambda *args, **kwargs: writes.append(args))
    app.render_live(SimpleNamespace())
    assert len(ticks) == 1
    assert not writes and not checked
    assert "Datenstand:" in str(ui.messages) and "Kein aktueller" in str(ui.messages)


def test_selected_id_survives_reorder_then_loses_only_its_own_tip(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = {key: feed_row(key, now) for key in [8, 1, 5, 2]}
    ui = Screen({"workspace": "Live"})
    keys = []
    def click(label, *, key, **kwargs):
        keys.append((label, key))
        return key == "live_fixture_1" and len(writes) == 0
    ui.button = click
    mount(monkeypatch, ui, rows)
    writes = []
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, item, **kw: writes.append((c.event_key, list(ui.messages))))
    app.render_live(SimpleNamespace())
    assert [k for _, k in keys] == ["live_fixture_8", "live_fixture_1", "live_fixture_5", "live_fixture_2"]
    assert "45+3" in str(keys) and "1:0" in str(keys)
    first = rows.pop(8)
    rows[8] = first
    app.render_live(SimpleNamespace())
    assert [key for key, _ in writes] == ["1", "1"]
    assert all("Heim1 vs Gast1" in str(messages) and "Modell:" in str(messages) for _, messages in writes)
    ui.messages.clear()
    rows[1]["detailed_at"] = None
    app.render_live(SimpleNamespace())
    assert len(writes) == 2 and "Kein aktueller" in str(ui.messages)


def test_fourth_eligible_game_requires_a_deliberate_click_until_it_finishes(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = {}
    for game in (1, 2, 3, 4):
        data = _analysis(game)
        data["remaining_goals"]["over_0_5_probability"] = {1:61., 2:81., 3:75., 4:70.}[game]
        data["scheduled_start"] = (now - timedelta(minutes=100-game)).isoformat()
        rows[game] = feed_row(game, now, analysis=data)
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, rows)
    writes = []
    click = [None]
    ui.button = lambda label, *, key, **kwargs: key == click[0]
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, item, **kw: writes.append(c.event_key))
    app.render_live(object())
    assert writes == ["2"]  # earliest of the automatic three, not overall earliest
    click[0] = "live_fixture_1"
    app.render_live(object())
    assert writes == ["2", "1"]
    click[0] = None
    rows[1]["fixture"]["fixture"]["date"] = now.isoformat()
    app.render_live(object())
    assert writes[-1] == "1"
    ui.widget_values["live_min_probability_Noch ein Tor"] = 65
    app.render_live(object())
    assert writes == ["2", "1", "1"]
    del rows[1]
    app.render_live(object())
    assert writes == ["2", "1", "1", "2"] and "live_selected_fixture_id" not in ui.session_state


@pytest.mark.parametrize("quality,probs,shown", [
    ("MEDIUM", (.18, .65, .17), True),
    ("LOW", (.18, .65, .17), False),
    ("MEDIUM", (.25, .45, .30), False),
])
def test_click_outside_automatic_red_shortlist_requires_supported_probability_and_quality(monkeypatch, quality, probs, shown):
    from test_live_tip_surface import _red
    now = datetime.now(timezone.utc)
    rows = {n:feed_row(n, now, red=_red(n)) for n in (1, 2, 3, 4)}
    rows[4] = feed_row(4, now, red=_red(4, probs))
    rows[4]["fixture"]["offline_red"]["prediction"]["data_quality"] = quality
    ui = Screen({"workspace":"Live"}, {"live_market_choice":"Nach Platzverweis"})
    mount(monkeypatch, ui, rows)
    ui.button = lambda label, *, key, **kwargs: key == "live_fixture_4"
    writes = []
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, item, **kw: writes.append(c.event_key))
    app.render_live(object())
    assert writes == (["card-4"] if shown else [])


@pytest.mark.parametrize("change", ["goal", "finish", "missing-detail"])
def test_another_viewer_revising_the_fixture_during_model_work_prevents_display(monkeypatch, change):
    from copy import deepcopy
    from live_football_feed import LiveFootballFeed
    now = datetime.now(timezone.utc)
    fixture = feed_row(2, now)["fixture"]
    fixture.update(events=[], statistics=[])
    class Source:
        def discover(self):
            return [deepcopy(fixture)]
        def details(self, ids):
            return [deepcopy(fixture)]
    feed, source = LiveFootballFeed(), Source()
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {})
    monkeypatch.setattr(app, "_live_ticker_resources", lambda key: (feed, source))
    def analyze(old, _analyzer):
        fixture["goals"]["away"] = 1
        if change == "finish":
            fixture["fixture"]["status"]["short"] = "FT"
        elif change == "missing-detail":
            del fixture["statistics"]
        # An independently open viewer received a new revision after this tab's read.
        feed.tick(source, now=now+timedelta(seconds=65))
        return old["offline_analysis"], None
    writes = []
    monkeypatch.setattr(app, "_analyze_ticker_fixture", analyze)
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: writes.append(True))
    app.render_live(object())
    assert not writes and "Modell:" not in str(ui.messages)


def test_discovery_failure_is_not_a_successful_empty_game_list(monkeypatch):
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {}, unavailable=True)
    app.render_live(object())
    text = str(ui.messages)
    assert "nicht verfügbar" in text and "Kein Live-Spiel" not in text


def test_an_unselected_stale_score_is_labelled_in_the_game_list(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = {1:feed_row(1, now), 2:feed_row(2, now - timedelta(minutes=3))}
    ui = Screen({"workspace":"Live"})
    mount(monkeypatch, ui, rows)
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: None)
    app.render_live(object())
    buttons = {key:label for kind, value in ui.messages if kind == "button" for label, key in (value,)}
    assert "Letzter Stand:" in buttons["live_fixture_2"]
    assert "Letzter Stand:" not in buttons["live_fixture_1"]


def test_one_fixture_model_failure_never_hides_other_games_or_creates_a_receipt(monkeypatch):
    stamp = datetime.now(timezone.utc)
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {n:feed_row(n, stamp) for n in (1, 2)})
    def analyze(row, analyzer):
        if row["fixture"]["id"] == 1:
            raise ValueError("private upstream payload")
        return row["offline_analysis"], None
    writes = []
    monkeypatch.setattr(app, "_analyze_ticker_fixture", analyze)
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, *a, **kw: writes.append(c.event_key))
    app.render_live(object())
    assert writes == ["2"] and "private upstream" not in str(ui.messages)
    assert sum(kind == "button" for kind, value in ui.messages) == 2


def test_retained_fragment_rechecks_original_account_before_access(monkeypatch):
    import customer_access
    ui = Screen({"workspace": "Live", customer_access.ACCESS_KEY: {"account_id": "a"*32}})
    ui.context = SimpleNamespace(cookies={})
    current = {"account_id": "a"*32, "features": ["live"]}
    monkeypatch.setenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", "1")
    monkeypatch.setattr(customer_access, "fetch_access", lambda cookies: current)
    ticks, _ = mount(monkeypatch, ui, {})
    fragments = []
    def register(**kwargs):
        def retain(fn):
            fragments.append(fn)
            return fn
        return retain
    ui.fragment = register
    app.render_live(object())
    assert len(ticks) == 1
    current["account_id"] = "b"*32
    fragments[0]()
    assert len(ticks) == 1
    current["account_id"] = "a"*32
    current["features"] = ["saved"]
    fragments[0]()
    assert len(ticks) == 1


def _test_ticker_app():
    import streamlit as st
    import app
    st.session_state["workspace"] = "Live"
    app.render_live(object())


def test_real_streamlit_fixture_buttons_and_market_slider_do_not_restart_scans(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from live_football_feed import LiveFootballFeed
    stamp = datetime.now(timezone.utc)
    fixtures = [feed_row(n, stamp)["fixture"] for n in (10, 20)]
    for fixture in fixtures:
        fixture.update(events=[], statistics=[])
    calls, receipts = [], []
    class Source:
        def discover(self):
            calls.append("discover")
            return fixtures
        def details(self, ids):
            calls.append(tuple(ids))
            return fixtures
    feed = LiveFootballFeed()
    monkeypatch.setattr(app, "_live_session_connected", lambda: True)
    monkeypatch.setattr(app, "_live_ticker_resources", lambda key: (feed, Source()))
    monkeypatch.setattr(app, "load_app_config", lambda st: SimpleNamespace(api_football_key="offline", freemode=False))
    monkeypatch.setattr(app, "_analyze_ticker_fixture", lambda f, _: (f["offline_analysis"], None))
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, *a, **kw: receipts.append((c.event_key, c.market)))
    screen = AppTest.from_function(_test_ticker_app).run(timeout=30)
    assert not screen.exception
    screen.button(key="live_fixture_20").click().run(timeout=30)
    assert not screen.exception and screen.session_state["live_selected_fixture_id"] == 20
    screen.selectbox(key="live_market_choice").set_value("Team trifft noch").run(timeout=30)
    assert not screen.exception and receipts[-1] == ("20", "Team trifft noch")
    screen.slider(key="live_min_probability_Team trifft noch").set_value(80).run(timeout=30)
    assert not screen.exception and any("Kein aktueller" in el.value for el in screen.info)
    assert receipts == [("10", "Noch ein Tor"), ("20", "Noch ein Tor"), ("20", "Team trifft noch")]
    assert calls == ["discover", (10, 20)]
