"""The same native snapshot owns the table row and the match inspector."""
from datetime import datetime, timezone

import pytest

import app
import live_football_board
from test_live_football_board import feed_row, mount
from test_live_tip_surface import Screen, _analysis


@pytest.mark.parametrize("kind,status", [
    ("below", "Geprüft – kein Tipp"), ("no-detail", "Nur Spielstand verfügbar"),
    ("clock", "Live-Stand nicht eindeutig"), ("version", "Live-Stand nicht eindeutig"),
    ("unknown-quality", "Kein verlässlicher Live-Tipp"), ("absent-market", "Kein verlässlicher Live-Tipp"),
    ("wrong-team", "Live-Stand nicht eindeutig"), ("late", "Keine neuen Tipps ab Minute 90"),
])
def test_result_text_distinguishes_completed_evaluation_from_missing_or_foreign_data(monkeypatch, kind, status):
    data = _analysis(1)
    if kind == "below":
        # At 45 minutes the two rates equal 1/2 the pregame means: no uplift on any market.
        data["breakdown"].update(remaining_home_mean=.75, remaining_away_mean=.5)
    if kind == "late":
        data.update(minute=90, phase_data={"status": "2H", "extra": 1})
    row = feed_row(1, datetime.now(timezone.utc), analysis=data)
    if kind == "no-detail":
        row["detailed_at"] = None
    elif kind == "clock":
        data["minute"] += 1
    elif kind == "version":
        data["model_version"] = ""
    elif kind == "unknown-quality":
        data["live_data_quality"] = "LOW"
    elif kind == "wrong-team":
        data["away_team_id"] += 1
    elif kind == "absent-market":
        data["breakdown"].pop("remaining_home_mean")
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {1: row})
    seen = {}
    def capture(ui, games, candidates, **options):
        assert not candidates
        seen.update(options["reasons"])
    monkeypatch.setattr(live_football_board, "render_board", capture)
    app._render_live_football(object(), viewer_active=lambda: True)
    assert seen == {1: status}


@pytest.mark.parametrize("change", ["none", "revoked", "revised"])
def test_each_visible_pick_rechecks_snapshot_and_owner_but_row_and_inspector_share_receipt(monkeypatch, change):
    ui = Screen({"workspace": "Live"})
    rows = {1: feed_row(1, datetime.now(timezone.utc))}
    mount(monkeypatch, ui, rows)
    active, actual = [True], []
    def capture(ui, games, candidates, **options):
        publish = options.get("publish_pick")
        assert callable(publish), "Rendering a pick needs the guarded publication callback"
        emit = lambda c: actual.append(("display", c.selection))
        game, = games
        assert publish(game, candidates[game.id], emit)
        if change == "revoked":
            active[0] = False
        elif change == "revised":
            rows[1]["detailed_at"] = None
        assert publish(game, candidates[game.id], emit) is (change == "none")
    monkeypatch.setattr(live_football_board, "render_board", capture)
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, *_, **kw: actual.append(("record", c.selection)))
    app._render_live_football(object(), viewer_active=lambda: active[0])
    want = [("display", "Heim1: Über 1,5 Tore"), ("record", "Heim1: Über 1,5 Tore")]
    assert actual == want + ([want[0]] if change == "none" else [])


@pytest.mark.parametrize("coverage,reason", [
    ("prematch", "Keine Vorabprognose"),
    ("no-xg", "Live-Torchancen (xG) fehlen"),
    ("waiting", "Nur Spielstand verfügbar"),
])
def test_real_coverage_names_what_is_missing_without_hiding_the_score(monkeypatch, coverage, reason):
    from test_live_football_source import native
    from live_football_source import analyze_detail
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    fixture = native()
    fixture["fixture"]["date"] = (now - timedelta(hours=1)).isoformat()
    fixture["events"] = [e for e in fixture["events"] if e["type"] != "Card"]
    for group in fixture["statistics"]:
        for stat in group["statistics"]:
            if stat["type"] == "Red Cards":
                stat["value"] = 0
        if coverage == "no-xg":
            group["statistics"] = [s for s in group["statistics"] if s["type"] != "expected_goals"]
    fid = fixture["fixture"]["id"]
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {fid: {"fixture": fixture, "observed_at": now,
                                  "detailed_at": None if coverage == "waiting" else now}})
    monkeypatch.setattr(app, "_analyze_ticker_fixture", lambda row, _: analyze_detail(row))
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **k: pytest.fail("No pick was calculated"))
    app._render_live_football(object(), viewer_active=lambda: True)
    assert any(kind == "button" and live_football_board.plain_markdown(reason) in value[0]
               and "1:0" in value[0] for kind, value in ui.messages)
    assert any(kind == "markdown" and 'class="lv-no-pick"' in value and reason in value for kind, value in ui.messages)


def test_masthead_uses_an_unambiguous_german_zurich_calendar_date(monkeypatch):
    from datetime import date
    monkeypatch.setattr(app, "zurich_today", lambda: date(2026, 11, 22))
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {})
    app.render_live(object())
    heads = [v for kind, v in ui.messages if kind == "markdown" and 'class="bb-live-mast"' in v]
    assert len(heads) == 1 and "Sonntag, 22.11.2026" in heads[0] and "Live Wettfinder" in heads[0]


@pytest.mark.parametrize("phase,minute,extra,home,label", [
    ("1H", 0, None, 0, "Anpfiff"),
    ("BT", 105, None, 1, "Verlängerung"),
    ("ET", 111, None, 1, "Verlängerung"),
    ("P", 120, None, 2, "Elfmeterschießen"),
    ("P", 90, None, 2, "Elfmeterschießen"),  # Direct shoot-out, without extra time.
    ("ET", 40, None, 0, "Spielzeit unklar"),
    ("ET", True, None, 0, "Spielzeit unklar"),
    ("P", 120, -1, 2, "Spielzeit unklar"),
    ("BT", 105, None, None, "Spielstand unklar"),
    ("1H", 0, 3, 0, "Spielzeit unklar"),
])
@pytest.mark.parametrize("details", [True, False])
def test_scoreboard_phase_explains_nonapplicable_markets_without_inventing_a_pick(
        monkeypatch, phase, minute, extra, home, label, details):
    now = datetime.now(timezone.utc)
    row = feed_row(1, now)
    row["fixture"]["fixture"]["status"].update(short=phase, elapsed=minute, extra=extra)
    row["fixture"]["goals"]["home"] = home
    if not details:
        row["detailed_at"] = None
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {1: row})
    app._render_live_football(object(), viewer_active=lambda: True)
    assert any(kind == "button" and label in msg[0] for kind, msg in ui.messages)
    assert not any(kind == "button" and ":green[" in msg[0] for kind, msg in ui.messages)


def test_open_board_masthead_follows_zurich_midnight_on_fragment_rerun(monkeypatch):
    from datetime import date
    today = [date(2026, 11, 22)]
    monkeypatch.setattr(app, "zurich_today", lambda: today[0])
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {})
    fragments = []
    def fragment(**_kw):
        def register(fn):
            fragments.append(fn)
            return fn
        return register
    ui.fragment = fragment
    app.render_live(object())
    assert sum('class="bb-live-mast"' in str(msg) for _, msg in ui.messages) == 1
    ui.messages.clear()
    today[0] = date(2026, 11, 23)
    fragments[0]()
    heads = [msg for kind, msg in ui.messages if kind == "markdown" and 'class="bb-live-mast"' in msg]
    assert len(heads) == 1 and "Montag, 23.11.2026" in heads[0]


def test_first_revocation_stops_access_checks_and_all_later_picks_in_same_fragment(monkeypatch):
    ui = Screen({"workspace": "Live"})
    now = datetime.now(timezone.utc)
    mount(monkeypatch, ui, {i: feed_row(i, now) for i in range(1, 5)})
    attempts_after_denial = []
    def access(owner):
        if any(kind == "button" and msg[1] == "live_fixture_1" for kind, msg in ui.messages):
            attempts_after_denial.append(True)
            return len(attempts_after_denial) > 1  # No retry/recovery halfway through this render.
        return True
    monkeypatch.setattr(app, "_live_viewer_active", access)
    seen = []
    monkeypatch.setattr(app, "record_visible_analysis", lambda c, item, **kw: seen.append(item["fixture_id"]))
    app.render_live(object())
    assert len(attempts_after_denial) == 1
    assert seen == [1]


@pytest.mark.parametrize("case", ["early", "closed", "foreign"])
def test_early_closed_or_foreign_specialist_does_not_attest_an_automatic_market(monkeypatch, case):
    from test_live_tip_surface import _red
    data = _analysis(1)
    minute = 11 if case == "early" else 89
    phase = "1H" if case == "early" else "2H"
    data.update(minute=minute, phase_data={"status": phase, "extra": None, "remaining_minutes": 90-minute})
    data["breakdown"].update(remaining_home_mean=1.5*(90-minute)/90, remaining_away_mean=(90-minute)/90)
    red = _red(1)
    red["card"]["minute"] = min(minute, 32)
    red["card"]["match"]["fixture"]["status"].update(short=phase, elapsed=minute, extra=None)
    red.update(prediction_minute=minute)
    red["prediction"].update(data_quality="LIMITED" if case == "early" else "MEDIUM",
                             too_late_for_signal=case != "early")
    if case == "foreign":
        red["card"]["match"]["fixture"]["id"] = 2
    ui = Screen({"workspace": "Live"})
    mount(monkeypatch, ui, {1: feed_row(1, datetime.now(timezone.utc), analysis=data, red=red)})
    monkeypatch.setattr(app, "record_visible_analysis", lambda *a, **kw: pytest.fail("Closed red model emitted a tip"))
    app.render_live(object())
    assert any(kind == "button" and "Geprüft – kein Tipp" in msg[0] for kind, msg in ui.messages)
    assert not any(kind == "markdown" and 'class="lv-pick"' in msg for kind, msg in ui.messages)
