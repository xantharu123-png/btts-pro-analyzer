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
                    "status": {"short": analysis["phase_data"]["status"], "elapsed": analysis["minute"],
                               "extra": analysis["phase_data"]["extra"]}},
        "teams": {"home": {"id": game+100, "name": analysis["home_team"]},
                  "away": {"id": game+200, "name": analysis["away_team"]}},
        "goals": {"home": analysis["home_score"], "away": analysis["away_score"]},
        "league": {"id": 39, "name": "Testliga"},
        "offline_analysis": analysis, "offline_red": red,
    }
    return {"fixture": fixture, "observed_at": stamp, "detailed_at": stamp}


def mount(monkeypatch, ui, rows, *, connected=lambda: True, unavailable=False):
    from live_football_feed import LiveFeedView, LiveRefreshIssue
    ticks, checked = [], []
    def tick(source, *, now, viewer_active):
        if viewer_active():
            ticks.append(now)
        return LiveFeedView(rows, LiveRefreshIssue.TEMPORARY_ERROR if unavailable else None, False)
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
    feed = SimpleNamespace(tick_view=tick, awaiting_discovery=lambda _now: False, current_detail=current_detail)
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


def test_highest_probability_opens_without_click_manual_selection_sticks_until_finished(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = {}
    for game in (1, 2, 3, 4):
        data = _analysis(game)
        data["remaining_goals"]["over_0_5_probability"] = {1:61., 2:81., 3:85., 4:70.}[game]
        data["scheduled_start"] = (now - timedelta(minutes=100-game)).isoformat()
        rows[game] = feed_row(game, now, analysis=data)
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, rows)
    writes = []
    click = [None]
    ui.button = lambda label, *, key, **kwargs: key == click[0]
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, item, **kw: writes.append(c.event_key))
    app.render_live(object())
    assert writes == ["3"]  # highest model probability, independent of kick-off
    click[0] = "live_fixture_1"
    app.render_live(object())
    assert writes == ["3", "1"]
    click[0] = None
    rows[1]["fixture"]["fixture"]["date"] = now.isoformat()
    app.render_live(object())
    assert writes[-1] == "1"
    rows[1]["fixture"]["offline_analysis"]["live_data_quality"] = "LOW"
    app.render_live(object())
    assert writes == ["3", "1", "1"]
    del rows[1]
    app.render_live(object())
    assert writes == ["3", "1", "1", "3"] and "live_selected_fixture_id" not in ui.session_state


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
    for row in rows.values():
        row["fixture"]["offline_analysis"]["live_data_quality"] = "LOW"
    ui = Screen({"workspace":"Live"})
    mount(monkeypatch, ui, rows)
    ui.button = lambda label, *, key, **kwargs: key == "live_fixture_4"
    writes = []
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, item, **kw: writes.append(c.event_key))
    app.render_live(object())
    assert writes == (["card-4"] if shown else [])


@pytest.mark.parametrize("bad", ["low", "late", "multiple", "foreign-game", "missing-side", "wrong-total",
                                 "foreign-label", "wrong-opponent"])
def test_even_the_only_dismissal_cannot_bypass_eligibility(monkeypatch, bad):
    from test_live_tip_surface import _red
    red = _red(1)
    if bad == "low":
        red["prediction"]["data_quality"] = "LOW"
    elif bad == "late":
        red["prediction"]["too_late_for_signal"] = True
    elif bad == "multiple":
        red["fixture_red_card_count"] = 2
    elif bad == "foreign-game":
        red["card"]["match"]["fixture"]["id"] = 2
    elif bad == "missing-side":
        del red["prediction"]["no_more_goals"]
    elif bad == "wrong-total":
        red["prediction"]["no_more_goals"] = .79
    elif bad == "foreign-label":
        red["card"]["team"] = "Fremder Verein"
    else:
        red["opponent"] = "Fremder Verein"
    row = feed_row(1, datetime.now(timezone.utc), red=red)
    row["fixture"]["offline_analysis"]["live_data_quality"] = "LOW"
    ui = Screen({"workspace": "Live"}, {"live_market_choice":"Nach Platzverweis"})
    mount(monkeypatch, ui, {1:row})
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: pytest.fail("unqualified receipt"))
    app.render_live(object())
    assert "Kein aktueller" in str(ui.messages) and "Modell:" not in str(ui.messages)


@pytest.mark.parametrize("case,expected", [
    ("warm", ("next_goal", "any", "Mindestens 1 weiteres Tor", .674)),
    ("dismissal", ("red_next", "home", "Nächstes Tor · 1", .660621370588)),
    ("late-no-card", None),
])
def test_grouped_native_model_to_visible_market_and_frozen_receipt(monkeypatch, tmp_path, case, expected):
    import sqlite3
    import requests
    import live_tip_ledger
    from live_football_feed import LiveFootballFeed
    from test_live_football_source import native, warm
    fixture = native()
    if case == "late-no-card":
        fixture["fixture"]["status"]["elapsed"] = 86
        fixture["goals"]["home"] = 4
        fixture["statistics"][0]["statistics"][1]["value"] = 0
        fixture["events"] = [
            {"time":{"elapsed":minute}, "team":{"id":1}, "type":"Goal", "detail":"Normal Goal"}
            for minute in (31, 51, 64, 78)]
    analyzer = warm(fixture, monkeypatch) if case != "dismissal" else None
    analyze = app._analyze_ticker_fixture
    ui = Screen({"workspace":"Live"})
    mount(monkeypatch, ui, {})
    feed = LiveFootballFeed()
    calls = []
    class OfflineSource:
        def discover(self):
            calls.append("discover")
            return [fixture]
        def details(self, ids):
            calls.append(tuple(ids))
            return [fixture]
    monkeypatch.setattr(app, "_live_ticker_resources", lambda key: (feed, OfflineSource()))
    monkeypatch.setattr(app, "_analyze_ticker_fixture", analyze)
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **kw: pytest.fail("unexpected HTTP"))
    db = tmp_path / "tips.db"
    write = live_tip_ledger.record_displayed_live_tip
    monkeypatch.setattr(live_tip_ledger, "record_displayed_live_tip", lambda **kw: write(**kw, db_path=db))
    app.render_live(analyzer or object())
    assert calls == ["discover", (81,)]
    if expected is None:
        assert "Kein aktueller" in str(ui.messages) and "4:0" in str(ui.messages)
        assert not db.exists()
    else:
        market, side, label, probability = expected
        assert label in str(ui.messages)
        with sqlite3.connect(db) as connection:
            rows = connection.execute("SELECT fixture_id, home_id, away_id, minute, home_goals, away_goals, "
                                      "market, side, probability FROM live_tips").fetchall()
        assert rows == [(81, 1, 2, 60, 1, 0, market, side, pytest.approx(probability))]


@pytest.mark.parametrize("bad", ["weak-at-86", "changed-teams", "changed-score", "changed-minute",
                                 "unsupported-reds", "decided-btts"])
def test_score_only_or_unbound_model_is_not_a_recommendation(monkeypatch, bad):
    data = _analysis(9)
    data.update(minute=86, home_score=4, score="4-0", btts_prob=6., phase_data={"status":"2H", "extra":None})
    data["remaining_goals"].update(over_0_5_probability=13., home_scores_probability=8., away_scores_probability=6.)
    if bad != "weak-at-86":
        data["btts_prob"] = 80.
    if bad == "decided-btts":
        data.update(away_score=1, score="4-1")
    row = feed_row(9, datetime.now(timezone.utc), analysis=data)
    if bad == "changed-teams":
        data["away_team_id"] = 600
    elif bad == "changed-score":
        data["home_score"] = 3
    elif bad == "changed-minute":
        data["minute"] = 32
    elif bad == "unsupported-reds":
        data["red_cards"] = {"supported":False}
    ui = Screen({"workspace":"Live"}, {"live_market_choice":"Beide treffen"})
    mount(monkeypatch, ui, {9:row})
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: pytest.fail("invalid receipt"))
    app.render_live(object())
    assert "Kein aktueller" in str(ui.messages) and "Modell:" not in str(ui.messages)


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


@pytest.mark.parametrize("failure,expected", [
    ("protected_reserve", "für die Tagesläufe reserviert"),
    ("ticker_limit", "Tageslimit des Live-Tickers erreicht"),
    ("unknown_budget_limit", "Ein Abruflimit verhindert die Live-Aktualisierung"),
    ("budget_unavailable", "Abrufkontingent konnte nicht geprüft werden"),
    ("jobs_deferred", "Hintergrundläufe haben Vorrang"),
    ("provider_error", "Live-Daten des Anbieters sind derzeit nicht verfügbar"),
    ("temporary_error", "Live-Aktualisierung ist vorübergehend gestört"),
])
def test_live_board_explains_failed_refresh_and_keeps_last_score(monkeypatch, failure, expected):
    import api_budget
    from live_football_feed import LiveFootballFeed
    from live_football_source import LiveFootballSource
    from test_live_football_source import response

    stamp = datetime.now(timezone.utc) - timedelta(seconds=70)
    fixture = feed_row(1, stamp)["fixture"]
    fixture.update(events=[], statistics=[])
    feed = LiveFootballFeed(monotonic=lambda: 0)
    attempts = []
    failed = False

    def get(url, **kwargs):
        attempts.append(kwargs["params"])
        if not failed:
            return response([fixture], kwargs["params"])
        if failure in {"protected_reserve", "ticker_limit", "unknown_budget_limit"}:
            raise api_budget.APIBudgetExceeded("private quota detail", reason=failure)
        if failure == "budget_unavailable":
            raise api_budget.APIBudgetUnavailable("private DB detail")
        if failure == "provider_error":
            return response([], kwargs["params"], errors={"private": "provider payload"})
        raise api_budget.requests.ReadTimeout("private URL")

    monkeypatch.setattr(api_budget, "api_football_get", get)
    source = LiveFootballSource("offline", ready=lambda: not failed or failure != "jobs_deferred")
    feed.tick(source, now=stamp)
    failed = True
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {})
    monkeypatch.setattr(app, "_live_ticker_resources", lambda key: (feed, source))
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: pytest.fail("stale model receipt"))
    app.render_live(object())
    app.render_live(object())  # another render during the existing backoff

    rendered = str(ui.messages)
    assert expected in rendered
    assert "1:0" in rendered and "Datenstand:" in rendered
    assert "Kein Live-Spiel" not in rendered and "private" not in rendered
    last = feed.tick(source, now=stamp + timedelta(seconds=90))[1]
    assert last["observed_at"] == stamp and last["detailed_at"] is None
    assert len(attempts) == (2 if failure == "jobs_deferred" else 3)
    failed = False
    recovered_at = stamp + timedelta(seconds=200)
    recovered = feed.tick(source, now=recovered_at)[1]
    assert recovered["observed_at"] == recovered_at and not feed.unavailable


def test_partial_live_data_is_reported_and_full_success_clears_status(monkeypatch):
    import api_budget
    from live_football_feed import LiveFootballFeed
    from live_football_source import LiveFootballSource
    from test_live_football_source import response

    now = datetime.now(timezone.utc)
    stamp = now - timedelta(seconds=70)
    fixtures = [feed_row(game, stamp)["fixture"] for game in (1, 2)]
    for fixture in fixtures:
        fixture.update(events=[], statistics=[])
    next_rows = fixtures
    monkeypatch.setattr(api_budget, "api_football_get", lambda url, **kw: response(next_rows, kw["params"]))
    feed = LiveFootballFeed(monotonic=lambda: 0)
    source = LiveFootballSource("offline", ready=lambda: True)
    feed.tick(source, now=stamp)
    next_rows = fixtures[:1]
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {})
    monkeypatch.setattr(app, "_live_ticker_resources", lambda key: (feed, source))
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: None)
    app.render_live(object())
    assert "Live-Daten sind unvollständig" in str(ui.messages)
    assert sum(kind == "button" for kind, _ in ui.messages) == 2
    next_rows = fixtures
    feed.tick(source, now=now + timedelta(seconds=65))
    ui.messages.clear()
    app.render_live(object())
    assert "Live-Daten sind unvollständig" not in str(ui.messages)


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


def test_open_manual_snapshot_expires_on_timed_tick_without_new_global_scan(monkeypatch):
    from test_live_tip_surface import _red
    snapshot = {"scope": "Weltweit", "version": app.RED_CARD_SNAPSHOT_VERSION,
                "scanned_at": datetime.now(timezone.utc).isoformat(), "cards": [_red(7)]}
    ui = Screen({"workspace": "Live", "red_card_snapshot": snapshot})
    mount(monkeypatch, ui, {})
    fragments, writes = [], []
    def retain(fn):
        fragments.append(fn)
        return fn
    ui.fragment = lambda **kwargs: retain
    monkeypatch.setattr(app, "_freemode_enabled", lambda: False)
    monkeypatch.setattr(app, "_job_key", lambda name: "offline:" + name)
    monkeypatch.setattr(app.scan_jobs, "get_job", lambda key: {"state": "idle"})
    monkeypatch.setattr(app.scan_jobs, "start_job", lambda *a, **kw: pytest.fail("passive worldwide scan"))
    monkeypatch.setattr(app, "record_visible_analysis",
                        lambda candidate, row, **kw: writes.append((candidate.event_key, kw["red"])))
    app.render_live(object())
    assert writes == []  # Stored results do not opt in on the user's behalf.
    ui.session_state["live_worldwide_research"] = True
    app.render_live(object())
    assert writes == [("card-7", True)] and "Modell:" in str(ui.messages)
    # Only the timer reruns from here; a page refresh must not be required.
    ui.messages.clear()
    snapshot["scanned_at"] = (datetime.now(timezone.utc) - timedelta(seconds=121)).isoformat()
    fragments[-1]()
    assert "weltweite Suche bei Bedarf erneut starten" in str(ui.messages)
    assert "Modell:" not in str(ui.messages) and writes == [("card-7", True)]


def _test_ticker_app():
    import streamlit as st
    import app
    st.session_state["workspace"] = "Live"
    app.render_live(object())


def test_real_streamlit_picks_the_best_market_without_widgets_or_new_requests(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from live_football_feed import LiveFootballFeed
    stamp = datetime.now(timezone.utc)
    fixtures = [feed_row(n, stamp)["fixture"] for n in (10, 20)]
    for fixture in fixtures:
        fixture.update(events=[], statistics=[])
    fixtures[1]["offline_analysis"]["remaining_goals"]["away_scores_probability"] = 82.
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
    assert not screen.selectbox and not screen.slider
    assert receipts == [("20", "Team trifft noch")]
    screen.button(key="live_fixture_10").click().run(timeout=30)
    assert not screen.exception and screen.session_state["live_selected_fixture_id"] == 10
    assert receipts == [("20", "Team trifft noch"), ("10", "Noch ein Tor")]
    assert calls == ["discover", (10, 20)]
