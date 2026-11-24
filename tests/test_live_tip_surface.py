"""Offline: only the automatically chosen, actually displayed market owns a receipt."""
from datetime import datetime, timedelta, timezone
import sqlite3
import sys
from types import SimpleNamespace

import pytest

import app
import bet_finder_ui
from red_card_impact_predictor import RED_CARD_MODEL_VERSION
from scanners.ultra_live_scanner_v3 import UltraLiveScanner
from test_workflow_integrity import _RecordingStreamlit


class Screen(_RecordingStreamlit):
    def button(self, label, **kwargs):
        self.messages.append(("button", (label, kwargs.get("key"))))
        return super().button(label, **kwargs)


def _assert_no_audit_ui(surface):
    text = str(surface.ui.messages).lower()
    for fragment in (
        "bilanz", "trefferquote", "abgerechneten live-analysen", "aktueller modellstand",
        "erste anzeige zählt", "nicht neu gezählt", "nicht gespeichert", "nicht geladen",
    ):
        assert fragment not in text
    for kind, value in surface.ui.messages:
        if kind == "rows":
            assert all("Spiel" in row for row in value)  # Live overview, not the audit table.
    assert not surface.reads


def _analysis(game):
    from live_football_priors import PRIOR_MODEL, PRIOR_REVISION
    return dict(fixture_id=game, home_team=f"Heim{game}", away_team=f"Gast{game}",
                home_team_id=game+100, away_team_id=game+200, home_score=1, away_score=0,
                scheduled_start="2026-11-21T22:00:00Z", minute=45, score="1-0",
                phase_data={"status": "1H", "extra": 3, "remaining_minutes": 45},
                model_version=UltraLiveScanner.MODEL_VERSION + PRIOR_REVISION, prematch_prior_source=PRIOR_MODEL,
                red_cards={"supported": True, "status": "VERIFIED_NONE", "home_count": 0, "away_count": 0, "applied": False},
                xg_data={"home_prior": 1.5, "away_prior": 1., "home_xg": 1.8, "away_xg": .4},
                breakdown={"remaining_home_mean": 1.1, "remaining_away_mean": .5},
                btts_prob=62., btts_confidence="MEDIUM", live_data_quality="MEDIUM",
                remaining_goals={"over_0_5_probability": 71., "home_scores_probability": 57.,
                                 "away_scores_probability": 65.})


def _red(game, probs=(.21, .62, .17)):
    home, away = f"Heim{game}", f"Gast{game}"
    return dict(home=home, away=away, opponent=home, score="1-0", red_side="away",
                prediction_minute=45, fixture_red_card_count=1, model_version=RED_CARD_MODEL_VERSION,
                card={"card_id": f"card-{game}", "minute": 32, "team": away, "team_id": game+200,
                      "match": {"fixture": {"id": game, "date": "2026-11-21T22:00:00Z",
                                            "status": {"elapsed": 45, "short": "1H", "extra": 3}},
                                "teams": {"home": {"id": game+100, "name": home},
                                          "away": {"id": game+200, "name": away}},
                                "goals": {"home": 1, "away": 0}}},
                prediction={"next_goal_by_opponent": probs[0], "next_goal_by_red_team": probs[1],
                            "no_more_goals": probs[2], "data_quality": "MEDIUM"})


def _market_sample(game, market):
    """Deterministic scanner outputs; actual paired market selection and display stay real."""
    analysis = _analysis(game)
    h, a = {"Teamtore": (1.1, .5), "Gesamttore": (.1, .1), "Doppelte Chance": (.4, 1.3),
            "Handicap": (.7, .7)}.get(market, (1.1, .5))
    analysis["breakdown"].update(remaining_home_mean=h, remaining_away_mean=a)
    return analysis


@pytest.fixture
def surface(monkeypatch):
    # Replace only the database I/O, both app renderers and their candidates stay real.
    writes, old_writes, reads, details_at_write = [], [], [], []
    ui = Screen({"workspace": "Live"})
    from test_live_football_board import mount
    feed = {}
    mount(monkeypatch, ui, feed)
    from live_tip_ledger import COMPARISON_POLICY_VERSION
    def record(**row):
        writes.append(row)
        details_at_write.append(list(ui.messages))
        return True
    def stats():
        reads.append(True)
        return {}
    ledger = SimpleNamespace(record_displayed_live_tip=record, live_tip_stats=stats,
                             COMPARISON_POLICY_VERSION=COMPARISON_POLICY_VERSION)
    monkeypatch.setitem(sys.modules, "live_tip_ledger", ledger)
    import redcard_signal_log
    shadow_writer = redcard_signal_log.log_signal
    monkeypatch.setattr(redcard_signal_log, "log_signal", lambda row: old_writes.append(row))
    monkeypatch.setattr(app, "st", ui)
    monkeypatch.setattr(bet_finder_ui, "st", ui)
    monkeypatch.setattr(app, "_job_key", lambda name: f"offline:{name}")
    monkeypatch.setattr(app.scan_jobs, "get_job", lambda key: {"state": "idle"})
    monkeypatch.setattr(app, "_freemode_enabled", lambda: False)
    return SimpleNamespace(ui=ui, feed=feed, ledger=ledger, writes=writes, old=old_writes, reads=reads,
                           details_at_write=details_at_write, shadow_writer=shadow_writer)


def _show(surface, label, *, age=0, items=None, selected=1):
    now = datetime.now(timezone.utc)-timedelta(seconds=age)
    red = label == "Nach Platzverweis"
    ui = surface.ui
    if items is None:
        items = [_red(n) if red else _market_sample(n, label) for n in (1, 2, 3, 4)]
    from test_live_football_board import feed_row
    surface.feed.clear()
    for i, item in enumerate(items):
        game = item["card"]["match"]["fixture"]["id"] if red else item["fixture_id"]
        if red:
            # This fixture has a dismissal model but no independent ordinary forecast.
            surface.feed[game] = feed_row(game, now, red=item)
            surface.feed[game]["fixture"]["offline_analysis"] = None
        else:
            surface.feed[game] = feed_row(game, now, analysis=item)
        if i == selected:
            ui.session_state["live_selected_fixture_id"] = game
    app.render_live(SimpleNamespace(engine=SimpleNamespace(LEAGUES_CONFIG={"league": 39})))
    return now.isoformat()


@pytest.mark.parametrize("label,key,side,prob,pct,visible", [
    ("Teamtore", "ft_team_total", "home_over_1_5", .667128916302, "66,7 %", "Heim{n}: Über 1,5 Tore"),
    ("Gesamttore", "ft_total", "under_1_5", .818730753078, "81,9 %", "Unter 1,5 Tore im Spiel"),
    ("Doppelte Chance", "ft_dc", "x2", .595674016555, "59,6 %", "Gast{n} oder Unentschieden"),
    ("Handicap", "ft_handicap", "away_plus_1_5", .691531257698, "69,2 %", "Gast{n} Handicap +1,5"),
])
def test_each_visible_row_binds_native_snapshot_once_including_the_selected_fixture(surface,label,key,side,prob,pct,visible):
    stamp = _show(surface, label)
    text = str(surface.ui.messages)
    messages = surface.ui.messages
    inspector, = [msg for kind, msg in messages if kind == "markdown" and 'class="lv-pick"' in msg]
    assert visible.format(n=2) in inspector and f'<b>{pct}</b>' in inspector
    scoreboard, = [msg for kind, msg in messages if kind == "markdown" and 'class="lv-scoreline"' in msg]
    assert "Heim2" in scoreboard and "Gast2" in scoreboard
    assert surface.old == []
    assert len(surface.writes) == len(surface.details_at_write) == 4
    for n, (receipt, already_rendered) in enumerate(zip(surface.writes, surface.details_at_write), 1):
        assert receipt == dict(fixture_id=n, market=key, side=side, minute=45, phase="1H", extra=3,
                               home_id=100+n, away_id=200+n, home_goals=1, away_goals=0,
                               probability=pytest.approx(prob), snapshot_at=stamp, model_version=_analysis(n)["model_version"],
                               policy_version=surface.ledger.COMPARISON_POLICY_VERSION)
        button, = [label for kind, value in already_rendered if kind == "button"
                   for label, widget in [value] if widget == f"live_fixture_{n}"]
        from live_football_board import plain_markdown
        assert f"Heim{n} – Gast{n}" in button and plain_markdown(visible.format(n=n)) in button and f"Modell {pct}" in button
    assert any(kind == "markdown" and 'class="lv-pick-reason"' in value and "Heim2 – Gast2, 1:0" in value and "Torchancen" in value
               and "ohne Live-Signale" in value for kind, value in messages)
    assert "keine passende Live-Quote" not in text and "Deine Mindestquote" not in text
    assert [v[1] for kind, v in surface.ui.messages if kind == "button" and (v[1] or "").startswith("live_fixture_")] == [
        "live_fixture_1", "live_fixture_2", "live_fixture_3", "live_fixture_4"]
    _assert_no_audit_ui(surface)


@pytest.mark.parametrize("probs,side", [((.65, .18, .17), "home"), ((.18, .65, .17), "away"), ((.15, .20, .65), "none")])
def test_manual_red_side_remains_separate_after_automatic_market_change(surface,probs,side):
    row = _red(5, probs)
    _show(surface, "Nach Platzverweis", items=[row], selected=0)
    assert not surface.writes  # The scoreboard cannot substitute the specialist for missing paired rates.
    surface.ui.session_state.update(live_worldwide_research=True, red_card_snapshot={
        "scope": "Weltweit", "version": app.RED_CARD_SNAPSHOT_VERSION,
        "scanned_at": datetime.now(timezone.utc).isoformat(), "cards": [row]})
    app.render_live(object())
    assert [(r["fixture_id"], r["side"], r["probability"]) for r in surface.writes] == [(5, side, .65)]
    assert surface.writes[0]["market"] == "red_next" and surface.writes[0]["model_version"] == RED_CARD_MODEL_VERSION


@pytest.mark.parametrize("label", ["Noch ein Tor", "Nach Platzverweis"])
def test_old_snapshot_stays_recognizable_as_history_without_a_new_receipt(surface,label):
    _show(surface, label, age=121)
    assert surface.writes == surface.old == []
    assert "Datenstand:" in str(surface.ui.messages)
    _assert_no_audit_ui(surface)


def test_no_receipt_without_visible_probability_or_source_version(surface):
    rows = [_analysis(4), _analysis(8)]
    rows[0]["breakdown"].pop("remaining_home_mean")
    _show(surface, "Teamtore", items=rows[:1], selected=0)
    rows[1].pop("model_version")
    _show(surface, "Teamtore", items=rows[1:], selected=0)
    assert surface.writes == surface.old == []
    _assert_no_audit_ui(surface)


@pytest.mark.parametrize("damage", ["prediction", "model_version"])
def test_manual_red_receipt_still_needs_a_probability_and_source_version(surface, damage):
    row = _red(4)
    row.pop(damage)
    surface.ui.session_state.update(live_worldwide_research=True, red_card_snapshot={
        "scope": "Weltweit", "version": app.RED_CARD_SNAPSHOT_VERSION,
        "scanned_at": datetime.now(timezone.utc).isoformat(), "cards": [row]})
    app.render_live(object())
    assert not surface.writes
    _assert_no_audit_ui(surface)


def test_empty_page_does_not_read_or_write_the_internal_audit(surface):
    _show(surface, "Noch ein Tor", items=[])
    assert "Kein Live-Spiel" in str(surface.ui.messages)
    assert surface.writes == surface.old == []
    _assert_no_audit_ui(surface)


@pytest.mark.parametrize("error_type", [sqlite3.OperationalError, OSError, ValueError])
def test_ledger_failure_does_not_change_customer_ui(surface, error_type, caplog):
    def unavailable(*args, **kwargs):
        raise error_type("internal audit error detail")
    surface.ledger.record_displayed_live_tip = unavailable
    _show(surface, "Teamtore")
    assert "Heim2: Über 1,5 Tore" in str(surface.ui.messages) and "Modell 66,7 %" in str(surface.ui.messages)
    assert not any(kind in {"warning", "error"} for kind, _ in surface.ui.messages)
    _assert_no_audit_ui(surface)
    assert "internal audit error detail" not in caplog.text
    if error_type is not ValueError:
        assert any(entry.name == "live_tip_surface" and error_type.__name__ in entry.getMessage()
                   for entry in caplog.records)


def test_unavailable_analyzer_does_not_read_the_internal_audit(surface):
    surface.ui.session_state["live_worldwide_research"] = True
    app.render_live(None)
    assert ("info", "Kein Live-Spiel in den unterstützten Ligen verfügbar.") in surface.ui.messages
    assert ("info", "Die manuelle Platzverweis-Suche ist nicht verfügbar.") in surface.ui.messages
    _assert_no_audit_ui(surface)


def test_live_scan_carries_native_stoppage_clock_and_a_pinned_source_version():
    from test_live_redcard_clock_regressions import _LiveAPI, _live_fixture
    row = UltraLiveScanner(None, _LiveAPI()).analyze_live_match_ultra(_live_fixture(45, "1H", 3))
    assert row.get("phase_data", {}).get("extra") == 3 and row.get("model_version")


def test_repeat_display_of_new_scan_keeps_first_visible_baseline_internally(surface, monkeypatch, tmp_path):
    # Use the real store here, so a button rerun, rescan or second viewer cannot inflate the count.
    monkeypatch.delitem(sys.modules, "live_tip_ledger")
    import live_tip_ledger as ledger
    db = tmp_path / "live.db"
    write = ledger.record_displayed_live_tip
    monkeypatch.setattr(ledger, "record_displayed_live_tip", lambda **fields: write(**fields, db_path=db))
    monkeypatch.setattr(ledger, "live_tip_stats", surface.ledger.live_tip_stats)
    row = _market_sample(8, "Teamtore")
    _show(surface, "Teamtore", items=[row], selected=0)
    row.update(minute=61, score="1-1", away_score=1, phase_data={"status": "2H", "extra": None, "remaining_minutes": 29})
    surface.ui.messages.clear()
    _show(surface, "Teamtore", items=[row], selected=0)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT fixture_id,side,minute,extra,home_goals,away_goals FROM live_tips").fetchall() == [
            (8, "home_over_1_5", 45, 3, 1, 0)]
    assert "Heim8: Über 1,5 Tore" in str(surface.ui.messages)
    _assert_no_audit_ui(surface)


@pytest.mark.parametrize("elapsed,extra,phase,card_minute,card_extra,count", [
    (45, 3, "1H", 45, 4, 1),  # 45+4 was retrieved after the fixture snapshot at 45+3.
    (62, None, "2H", 63, None, 1),
    (61, None, "2H", 49, None, 2),
    (61, None, "SUSP", 49, None, 1),
    (90, 8, "2H", 72, None, 1),  # A running injury-time clock gives no time-to-whistle.
    (93, None, "2H", 72, None, 1),
])
def test_inconsistent_red_card_context_never_produces_a_public_model(elapsed,extra,phase,card_minute,card_extra,count):
    from red_card_bot import RedCardBotEnhanced
    bot = RedCardBotEnhanced(api_key="offline", streamlit_mode=False)
    bot.get_live_stats = lambda *args: pytest.fail("no scan for unsupported 11-v-10 model")
    card = _red(3)["card"]
    card.update(minute=card_minute, extra_minute=card_extra)
    card["match"]["fixture"]["status"].update(short=phase, elapsed=elapsed, extra=extra)
    entry = app._red_card_entry(bot, card, fixture_red_card_count=count)
    assert entry["prediction"] is None and entry["error"]


def test_fresh_scan_preserves_separate_shadow_cohort_public_requires_actual_display(surface, monkeypatch, tmp_path):
    import red_card_bot
    monkeypatch.delitem(sys.modules, "live_tip_ledger")
    import live_tip_ledger as ledger
    public, shadow = tmp_path / "public.db", tmp_path / "shadow.db"
    write = ledger.record_displayed_live_tip
    monkeypatch.setattr(ledger, "record_displayed_live_tip", lambda **fields: write(**fields, db_path=public))
    monkeypatch.setattr(ledger, "live_tip_stats", surface.ledger.live_tip_stats)
    monkeypatch.setattr("redcard_signal_log.log_signal", lambda row: surface.shadow_writer(row, db_path=shadow))
    games = [_red(i)["card"] for i in range(1, 6)]
    for game in games:
        game["match"]["league"] = {"id": 39, "name": "Test"}
    bot = red_card_bot.RedCardBotEnhanced(api_key="offline", streamlit_mode=False)
    bot.get_live_matches = lambda leagues: [game["match"] for game in games]
    def offline_events(url, *, params, **kwargs):
        assert url.endswith("/fixtures/events")
        index = params["fixture"] % 10
        card = games[index - 1]
        event = {"type": "Card", "detail": "Red Card", "time": {"elapsed": card["minute"]},
                 "team": {"id": card["team_id"], "name": card["team"]},
                 "player": {"id": 8, "name": "Player"}}
        events = [event]
        if index == 5:
            events.append({"type": "Card", "detail": "Second Yellow card",
                           "team": {}, "player": {"id": None}, "time": {}})
        return SimpleNamespace(status_code=200, json=lambda: {"response": events})
    bot._get = offline_events
    bot.get_live_stats = lambda *args: {"xg_home": .90, "xg_away": 1.1}
    monkeypatch.setattr(red_card_bot, "RedCardBotEnhanced", lambda **kwargs: bot)
    monkeypatch.setattr(app, "_red_card_prematch_priors", lambda *args, **kwargs: (1.4, 1.2))
    snapshot = app._scan_red_cards("offline", None, "Weltweit", streamlit_mode=False)
    assert snapshot["cards"][4]["prediction"] is None and snapshot["cards"][4]["error"]
    assert shadow.exists() and not public.exists()
    with sqlite3.connect(shadow) as conn:
        assert conn.execute("SELECT fixture_id FROM signals ORDER BY fixture_id").fetchall() == [(1,), (2,), (3,), (4,)]
    surface.ui.session_state["red_card_snapshot"] = snapshot
    # A stored worldwide scan is not published merely because somebody opens Live.
    analyzer = SimpleNamespace(engine=SimpleNamespace(LEAGUES_CONFIG={"league": 39}))
    app.render_live(analyzer)
    assert not public.exists()
    # The explicit manual view still records its actually displayed market.
    surface.ui.session_state["live_worldwide_research"] = True
    surface.ui.widget_values["red_card_detail"] = snapshot["cards"][1]["card"]["card_id"]
    app.render_live(analyzer)
    with sqlite3.connect(public) as conn:
        assert conn.execute("SELECT fixture_id FROM live_tips").fetchall() == [(2,)]
    # A slow source fetch must not create a shadow observation from an old score either.
    for game in games:
        game["match"]["fixture"]["id"] += 10
    monkeypatch.setattr(app, "_snapshot_age_seconds", lambda stamp: 121.)
    app._scan_red_cards("offline", [39], "Konfigurierte Ligen", streamlit_mode=False)
    with sqlite3.connect(shadow) as conn:
        assert conn.execute("SELECT COUNT(*) FROM signals").fetchone() == (4,)


def test_unsupported_red_snapshot_does_not_publish_an_unverified_provider_reason(surface):
    row = _red(5)
    row.update(prediction=None, error="Nachspielzeit: Die verbleibende Spielzeit ist unbekannt; keine neue Prognose.")
    _show(surface, "Nach Platzverweis", items=[row], selected=0)
    text = str(surface.ui.messages)
    assert "Kein verlässlicher Live-Tipp" in text and row["error"] not in text
    assert "Geprüft – kein Tipp" not in text and surface.writes == []
