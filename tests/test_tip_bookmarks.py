"""Real store/render boundaries for personal model bookmarks (not bets)."""
from __future__ import annotations

import ast
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

import bet_finder_ui as ui
from bet_finder_candidates import build_probability_candidate
from multi_sport_recommendations import evaluate_candidate_price
from riskobet_surface import RiskBetPriceOverlay
from tip_store import TipStore


T0 = datetime(2030, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2030, 1, 2, tzinfo=timezone.utc)
T2 = datetime(2030, 1, 3, tzinfo=timezone.utc)
SCOPE = "a" * 32

# Literal pre-repair schema: expectations do not reuse the new table builder.
LEGACY_SCHEMA = """
CREATE TABLE saved_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, scope_id TEXT NOT NULL,
    identity_key TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    sport TEXT NOT NULL, event_key TEXT NOT NULL, event_label TEXT NOT NULL,
    market TEXT NOT NULL, selection TEXT NOT NULL, model_probability REAL NOT NULL,
    risk_adjusted_probability REAL NOT NULL, minimum_odds REAL NOT NULL,
    quoted_odds REAL NOT NULL, decision_status TEXT NOT NULL, evidence_stage TEXT NOT NULL,
    stake_amount REAL NOT NULL DEFAULT 0, source TEXT NOT NULL,
    result TEXT CHECK (result IS NULL OR result IN ('WON', 'LOST', 'VOID')),
    settled_at TEXT, archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    UNIQUE(scope_id, identity_key)
);
CREATE INDEX idx_saved_tips_state ON saved_tips(scope_id, archived, result, updated_at DESC);
"""


def _legacy_database(db_path, *, status="BET", stage="RELEASED"):
    with sqlite3.connect(db_path) as connection:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute("INSERT INTO saved_tips VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            71, SCOPE, "legacy-identity", T0.isoformat(), T1.isoformat(), "Tennis", "old-71",
            "Original Alpha vs Beta", "Sieger", "Alpha", 65.12345, 60.23456, 1.90123,
            2.23456, status, stage, 17.12345, "Original source", "LOST", T1.isoformat(), 0,
        ))
        # Deleted IDs must not become available for reuse after the rebuild.
        connection.execute("UPDATE sqlite_sequence SET seq=99 WHERE name='saved_tips'")
        row = connection.execute("SELECT * FROM saved_tips").fetchone()
        types = connection.execute("SELECT typeof(model_probability), typeof(stake_amount), typeof(id) FROM saved_tips").fetchone()
    return row, types


def test_legacy_nullable_migration_preserves_exact_rows_types_ids_and_sequence(tmp_path):
    db_path = tmp_path / "tips.db"
    original, types = _legacy_database(db_path)

    TipStore(db_path, scope_id=SCOPE)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT * FROM saved_tips").fetchone() == original
        assert connection.execute("SELECT typeof(model_probability), typeof(stake_amount), typeof(id) FROM saved_tips").fetchone() == types
        assert connection.execute("SELECT seq FROM sqlite_sequence WHERE name='saved_tips'").fetchone() == (99,)
        columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(saved_tips)")}
    assert columns["quoted_odds"] == 0, "legacy table cannot store truthful unknown quotes"
    assert columns["risk_adjusted_probability"] == columns["minimum_odds"] == 0


def test_constructor_never_archives_settled_legacy_model_rows(tmp_path):
    db_path = tmp_path / "tips.db"
    original, _ = _legacy_database(db_path, status="SHADOW", stage="SHADOW")

    TipStore(db_path, scope_id=SCOPE)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT * FROM saved_tips").fetchone() == original


def test_nullable_migration_failure_rolls_back_dropped_table_and_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "tips.db"
    original, _ = _legacy_database(db_path)

    class _FailRename(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql.strip().upper().startswith("ALTER TABLE"):
                raise sqlite3.OperationalError("injected rename failure")
            return super().execute(sql, *args)

    def connection(store):
        conn = sqlite3.connect(store.db_path, factory=_FailRename)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(TipStore, "_connect", connection)
    with pytest.raises(sqlite3.OperationalError, match="injected rename failure"):
        TipStore(db_path, scope_id=SCOPE)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT * FROM saved_tips").fetchone() == original
        assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name='saved_tips'").fetchone() == (99,)
        assert {row[1]: row[3] for row in conn.execute("PRAGMA table_info(saved_tips)")}["quoted_odds"] == 1
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_saved_tips_state'").fetchone()
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='saved_tips_upgrade'").fetchone() is None


def _candidate(sport="Fußball"):
    return build_probability_candidate(
        event_key="fixture-17", sport=sport, event_label="Alpha vs Beta",
        market="Sieger", selection="Alpha", model_probability=60.0,
        probability_haircut=5.0, model_name="Testmodell", evidence=("Modell",),
        evidence_stage="SHADOW",
    )


def _decision(odds=2.0):
    return evaluate_candidate_price(
        replace(_candidate(), evidence_stage="RELEASED"), odds,
        bankroll=100.0, quote_confirmed=True,
    )


@pytest.mark.parametrize("sport", ["Fußball", "Tennis", "E-Sport"])
def test_quote_free_visible_model_is_saved_without_price_or_stake(tmp_path, sport):
    store = TipStore(tmp_path / "tips.db", scope_id=SCOPE)
    assert callable(getattr(store, "save_bookmark", None)), "quote-free bookmark path is missing"
    tip = store.save_bookmark(_candidate(sport), source="Wettfinder", now=T0)

    assert (tip.sport, tip.decision_status, tip.evidence_stage) == (sport, "BOOKMARK", "SHADOW")
    assert tip.quoted_odds is None
    assert tip.stake_amount == 0.0
    assert TipStore(tmp_path / "tips.db", scope_id=SCOPE).list_tips() == [tip]
    assert TipStore(tmp_path / "tips.db", scope_id="b" * 32).list_tips() == []


def test_visible_model_without_price_haircut_can_be_bookmarked(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    assert callable(getattr(store, "save_bookmark", None)), "quote-free bookmark path is missing"
    candidate = replace(_candidate(), risk_adjusted_probability=None, minimum_odds=None,
                        blockers=("Keine Value-Grenze",))
    tip = store.save_bookmark(candidate, source="Manuelle Suche")
    assert tip.model_probability == 60.0
    assert tip.risk_adjusted_probability is None
    assert tip.minimum_odds is None


@pytest.mark.parametrize("result", ["WON", "LOST", "VOID"])
def test_settled_price_tip_keeps_original_snapshot_on_later_save(tmp_path, result):
    store = TipStore(tmp_path / "tips.db")
    first = store.save_decision(_decision(), source="Original", now=T0)
    store.settle(first.id, result, now=T1)
    original = store.list_tips(active=False)[0]
    updated = replace(_decision(2.3), stake_amount=99.0,
                      candidate=replace(_decision(2.3).candidate, model_probability=80.0))

    assert store.save_decision(updated, source="Spätere Prüfung", now=T2) == original
    assert store.list_tips(active=False) == [original]
    assert store.list_tips(active=True) == []


def test_settled_tip_cannot_be_archived_directly_or_by_a_failed_recheck(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    decision = _decision()
    tip = store.save_decision(decision, source="Original", now=T0)
    store.settle(tip.id, "LOST", now=T1)
    original = store.list_tips(active=False)[0]

    with pytest.raises(ValueError):
        store.archive(tip.id)
    store.archive_candidate(sport=tip.sport, event_key=tip.event_key,
                            market=tip.market, selection=tip.selection)
    assert store.list_tips(active=False) == [original]


def test_price_recheck_does_not_remove_a_personal_bookmark(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    assert callable(getattr(store, "save_bookmark", None)), "quote-free bookmark path is missing"
    tip = store.save_bookmark(_candidate(), source="Wettfinder")
    store.archive_candidate(sport=tip.sport, event_key=tip.event_key,
                            market=tip.market, selection=tip.selection)
    assert store.list_tips() == [tip]


def test_archived_priced_identity_is_not_silently_bookmarked_or_rewritten(tmp_path):
    db_path = tmp_path / "tips.db"
    store = TipStore(db_path)
    tip = store.save_decision(_decision(), source="Original", now=T0)
    store.archive(tip.id)
    with sqlite3.connect(db_path) as connection:
        original = connection.execute("SELECT * FROM saved_tips").fetchone()

    with pytest.raises(ValueError, match="bereits"):
        store.save_bookmark(_candidate(), source="Wettfinder", now=T2)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT * FROM saved_tips").fetchone() == original


def test_settled_bookmark_retains_identity_result_and_model_snapshot(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    assert callable(getattr(store, "save_bookmark", None)), "quote-free bookmark path is missing"
    tip = store.save_bookmark(_candidate(), source="Wettfinder", now=T0)
    store.settle(tip.id, "WON", now=T1)
    original = store.list_tips(active=False)[0]
    changed = replace(_candidate(), model_probability=85.0)

    assert store.save_bookmark(changed, source="Neu", now=T2) == original
    assert store.save_decision(_decision(2.3), source="Preisprüfung", now=T2) == original
    with pytest.raises(ValueError):
        store.settle(tip.id, "LOST", now=T2)
    assert store.list_tips(active=False) == [original]


class _Surface:
    """Only the UI boundary is fake; save handlers and SQLite stay real."""
    def __init__(self, clicked=True):
        self.session_state = {"_betboy_account_scope": SCOPE}
        self.clicked = clicked
        self.buttons = []
        self.messages = []

    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs))
        return self.clicked

    def container(self, **kwargs):
        return nullcontext()

    def expander(self, *args, **kwargs):
        return nullcontext()

    def columns(self, count):
        return [self] * count

    def metric(self, label, value):
        self.messages.append((label, value))

    def __getattr__(self, name):
        if name in {"toast", "markdown", "caption", "write", "subheader", "info", "warning", "dataframe"}:
            return lambda value, **kwargs: self.messages.append((name, value))
        raise AttributeError(name)


def test_model_selection_click_saves_the_actual_selection_without_price_evaluation(tmp_path, monkeypatch):
    surface = _Surface()
    monkeypatch.setattr(ui, "st", surface)
    monkeypatch.setattr(ui, "TipStore", partial(TipStore, tmp_path / "tips.db"))
    monkeypatch.setattr(ui, "evaluate_reference_price", lambda *a, **k: pytest.fail("bookmark evaluated price"))

    ui.render_model_selection(_candidate())

    tips = TipStore(tmp_path / "tips.db", scope_id=SCOPE).list_tips()
    assert len(tips) == 1, "visible model selection has no working save action"
    assert (tips[0].selection, tips[0].quoted_odds, tips[0].stake_amount) == ("Alpha", None, 0.0)
    assert surface.buttons[0][0] == "Tipp merken"


def _manual_tennis_row(probability=0.70):
    from tennis import shadow

    return dict(
        id=71, created_utc=T0.timestamp(), match_date="2030-01-01",
        tour="ATP", tournament="Test Open", fixture_source="ESPN",
        provider_event_id="native-71", scheduled_start_utc=T1.isoformat(),
        surface="Hard", best_of=3, player_a="Alpha", player_b="Beta",
        p_raw=probability, p_cal=probability, markets_json="{}", context_json="{}",
        gates_json=json.dumps({
            "Belag": {"passed": True, "detail": "Hard"},
            "Erfahrung": {"passed": True, "detail": "400 / 300 Matches"},
            "Aufschlag-Daten": {"passed": True, "detail": "5000 / 4000"},
            "Quote/Risiko-EV": {"passed": False, "detail": "Keine Quote"},
        }),
        verdict="KEINE WETTE", recommended_side=None, recommended_edge=None,
        odds_a=1.01, odds_b=9.99, settled=0,
        model_version=shadow.TENNIS_MODEL_VERSION,
        policy_version=shadow.TENNIS_POLICY_VERSION,
    )


@pytest.fixture
def manual_tennis_bookmark_surface(tmp_path, monkeypatch):
    import tennis_tab

    surface = _Surface()
    path = tmp_path / "tips.db"
    # Only UI and the destination path are substituted. The real account-scope
    # validator, renderer, bookmark handler and SQLite conflict rules run.
    monkeypatch.delenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", raising=False)
    monkeypatch.setattr(tennis_tab, "st", surface)
    monkeypatch.setattr(ui, "st", surface)
    monkeypatch.setattr(ui, "TipStore", partial(TipStore, path))

    def no_price_evaluation(*_args, **_kwargs):
        pytest.fail("remembering a manual tennis model evaluated a price")

    monkeypatch.setattr(ui, "evaluate_reference_price", no_price_evaluation)
    monkeypatch.setattr(tennis_tab, "evaluate_market_price", no_price_evaluation)
    return tennis_tab, surface, path


@pytest.mark.parametrize("probability,selection", [(0.70, "Sieg Alpha"), (0.30, "Sieg Beta")])
@pytest.mark.parametrize("observed_odds", [None, 2.60])
def test_manual_tennis_card_saves_visible_native_favorite_without_price_release(
        manual_tennis_bookmark_surface, probability, selection, observed_odds):
    tennis_tab, surface, path = manual_tennis_bookmark_surface
    row = _manual_tennis_row(probability)
    original_row = dict(row)
    price = None if observed_odds is None else RiskBetPriceOverlay(
        candidate_id="manual-tennis:71", observed_odds=observed_odds,
        observed_at=T0.isoformat(), bookmaker="Test Bookmaker",
    )

    tennis_tab._render_match_card(row, price=price)

    tips = TipStore(path, scope_id=SCOPE).list_tips()
    assert len(tips) == 1, "manual tennis model has no working personal bookmark"
    tip = tips[0]
    # Literal SHA-256 of tennis<US>ESPN<US>native-71, not the mapper under test.
    assert tip.event_key == "event_43b90087651e8a20814c64b1ac2d9b5e2601c7290dd43cfbd5c3437197adfe31"
    assert (tip.sport, tip.event_label, tip.market, tip.selection) == (
        "Tennis", "Alpha vs Beta", "Match Winner", selection,
    )
    assert (tip.model_probability, tip.risk_adjusted_probability) == (70.0, 55.0)
    assert (tip.decision_status, tip.evidence_stage, tip.source) == (
        "BOOKMARK", "SHADOW", "Manuelle Suche",
    )
    assert tip.quoted_odds is None and tip.stake_amount == 0.0
    assert TipStore(path, scope_id="b" * 32).list_tips() == []
    assert [label for label, _ in surface.buttons] == ["Tipp merken"]
    assert row == original_row


@pytest.mark.parametrize("change", [
    {"fixture_source": ""},
    {"provider_event_id": None},
    {"gates_json": json.dumps({"Belag": {"passed": False, "detail": "Unbekannt"}})},
])
def test_manual_tennis_unbound_or_model_blocked_card_cannot_create_a_bookmark(
        manual_tennis_bookmark_surface, change):
    tennis_tab, surface, path = manual_tennis_bookmark_surface

    tennis_tab._render_match_card({**_manual_tennis_row(), **change})

    assert not surface.buttons
    assert not path.exists()


def test_manual_tennis_bookmark_has_no_transient_session_scope_fallback(
        manual_tennis_bookmark_surface):
    tennis_tab, surface, path = manual_tennis_bookmark_surface
    surface.session_state = {"_betboy_session_scope": "b" * 32}

    tennis_tab._render_match_card(_manual_tennis_row())

    assert [label for label, _ in surface.buttons] == ["Tipp merken"]
    assert not path.exists(), "missing durable account scope wrote a personal tip"


def test_manual_tennis_later_model_cannot_replace_settled_personal_snapshot(
        manual_tennis_bookmark_surface):
    tennis_tab, _, path = manual_tennis_bookmark_surface
    tennis_tab._render_match_card(_manual_tennis_row())
    store = TipStore(path, scope_id=SCOPE)
    tips = store.list_tips()
    assert len(tips) == 1, "manual tennis card omitted its save action"
    store.settle(tips[0].id, "LOST", now=T1)
    original = store.list_tips(active=False)

    tennis_tab._render_match_card(_manual_tennis_row(0.90))

    assert store.list_tips(active=False) == original
    assert store.list_tips(active=True) == []


@pytest.mark.parametrize("sport", ["Fussball", "Tennis", "E-Sport"])
def test_real_game_renderer_invokes_bookmark_action_and_persists_sport_selection(tmp_path, monkeypatch, sport):
    from test_wettfinder_surface import _signal, NOW
    import wettfinder_surface as cards

    signal = _signal("save-real-card", sport=sport)
    card = cards.build_wettfinder_card(signal, now=NOW)
    group = cards.WettfinderFixtureGroup("test:fixture", "Alpha vs Beta", (card,))
    surface = _Surface()
    monkeypatch.setattr(ui, "st", surface)
    monkeypatch.setattr(ui, "TipStore", partial(TipStore, tmp_path / "tips.db"))
    monkeypatch.setattr(ui, "evaluate_reference_price", lambda *a, **k: pytest.fail("game action evaluated price"))
    # Importing app starts unrelated runtime services. Execute its unchanged
    # real rendering functions, with UI and storage boundaries supplied here.
    names = {"_wettfinder_game_key", "_remember_wettfinder_game_state", "_render_wettfinder_game"}
    tree = ast.parse((Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8"))
    namespace = dict(st=surface, hashlib=hashlib, wettfinder_game_label=cards.wettfinder_game_label,
                     render_editorial_card_html=cards.render_editorial_card_html,
                     _automated_signal_candidate=cards.wettfinder_recommendation_candidate)
    if hasattr(ui, "render_tip_bookmark"):
        namespace["render_tip_bookmark"] = ui.render_tip_bookmark
    exec(compile(ast.Module([node for node in tree.body if isinstance(node, ast.FunctionDef)
                           and node.name in names], type_ignores=[]), "app-render-functions", "exec"), namespace)

    namespace["_render_wettfinder_game"](group, {card.key: (signal, card)}, set())

    tips = TipStore(tmp_path / "tips.db", scope_id=SCOPE).list_tips()
    assert len(tips) == 1, "sport card renderer omitted the bookmark action"
    assert (tips[0].sport, tips[0].selection) == (sport, signal.selection)
    assert tips[0].decision_status == "BOOKMARK"
    assert tips[0].quoted_odds is None


def test_my_tips_renders_quote_free_collection_without_fictional_odds(tmp_path, monkeypatch):
    import my_tips

    store = TipStore(tmp_path / "tips.db", scope_id=SCOPE)
    assert callable(getattr(store, "save_bookmark", None)), "quote-free bookmark path is missing"
    store.save_bookmark(_candidate(), source="Wettfinder")
    surface = _Surface(clicked=False)
    monkeypatch.setattr(my_tips, "st", surface)
    monkeypatch.setattr(my_tips, "TipStore", partial(TipStore, tmp_path / "tips.db"))

    my_tips.render_saved_tips()

    shown = str(surface.messages)
    assert "Alpha vs Beta" in shown
    assert "Modellauswahl" in shown
    assert ("Quote", "Nicht geprüft") in surface.messages
    assert "Einsatz" not in shown and "ROI" not in shown
