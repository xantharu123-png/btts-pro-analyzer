"""New live selections are bound to their visible market and its regulation settlement."""
from types import SimpleNamespace
import sqlite3

import pytest

import live_tip_ledger as ledger
import live_tip_surface as surface
from test_live_tip_ledger import NOW, Provider, fixture, goal, record, settle, stats


def observation():
    candidate = SimpleNamespace(market="Spielausgang", selection="Sieg Blau",
                                forecast_available=True, model_probability=76.)
    row = dict(fixture_id=123, home_team="Blau", away_team="Rot",
               home_team_id=10, away_team_id=20, minute=61, phase_data=dict(status="2H", extra=None),
               home_score=1, away_score=0, model_version="live-comparison-source",
               live_comparison=dict(market="ft_result", side="home", label="Sieg Blau",
                                    market_label="Spielausgang", reason="Blau jetzt stärker als vor Anpfiff."))
    return candidate, row


def test_new_receipt_uses_visible_label_native_side_and_unique_first_display(tmp_path, monkeypatch):
    candidate, row = observation()
    db = tmp_path / "live.db"
    writer = ledger.record_displayed_live_tip
    monkeypatch.setattr(ledger, "record_displayed_live_tip",
                        lambda **kw: writer(**({"db_path": db, "now": NOW} | kw)))
    for p in (76., 88.):
        candidate.model_probability = p
        surface.record_visible_analysis(candidate, row, snapshot_at=NOW, age_seconds=0)
    assert db.exists()
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT market,side,probability,home_id,away_id,minute,phase,extra,"
                            "home_goals,away_goals,policy_version FROM live_tips").fetchall() == [
            ("ft_result", "home", .76, 10, 20, 61, "2H", 0, 1, 0, ledger.COMPARISON_POLICY_VERSION)]
    assert not record(db, "ft_result", "home", probability=.89)
    assert stats(db)["ft_result"] == dict(won=0, lost=0, open=1, void=0)


@pytest.mark.parametrize("tamper", ["wrong_side", "made_up_category", "made_up_label", "wrong_line",
                                    "null_metadata", "older_market_as_fallback", "missing_reason"])
def test_malformed_comparison_never_uses_another_market_or_the_legacy_fallback(tamper):
    candidate, row = observation()
    info = row["live_comparison"]
    if tamper == "wrong_side":
        info["side"] = "away"
    elif tamper == "made_up_category":
        candidate.market = info["market_label"] = "Gesamttore"
    elif tamper == "made_up_label":
        candidate.selection = info["label"] = "Sieg Rot"
    elif tamper == "wrong_line":
        info.update(market="ft_total", side="over_1_5", label="Über 2,5 Tore im Spiel", market_label="Gesamttore")
        candidate.market, candidate.selection = info["market_label"], info["label"]
    elif tamper == "missing_reason":
        info.pop("reason")
    else:
        candidate.market, candidate.selection = "Noch ein Tor", "Mindestens 1 weiteres Tor"
        row["live_comparison"] = None if tamper == "null_metadata" else {}
    assert surface.live_snapshot_fields(candidate, row, red=False) is None


def test_ft_markets_settle_without_event_call_and_exclude_extra_time(tmp_path):
    db = tmp_path / "results.db"
    for market, side in (("ft_result", "home"), ("ft_result", "away"),
                         ("ft_total", "over_2_5"), ("ft_btts", "no")):
        assert record(db, market, side)
    api = Provider({123: fixture("AET", (2, 0), (2, 3))})
    assert settle(db, api)["settled"] == 4
    assert api.calls == [("fixtures", {"id": 123})]
    assert stats(db)["ft_result"] == dict(won=1, lost=1, open=0, void=0)
    assert stats(db)["ft_total"]["lost"] == stats(db)["ft_btts"]["won"] == 1


def test_overlap_preserves_old_receipt_and_versions_the_first_new_choice(tmp_path):
    db = tmp_path / "transition.db"
    assert record(db, "team_scores", "home")
    assert not record(db, "team_scores", "home", policy_version=ledger.COMPARISON_POLICY_VERSION)
    assert record(db, "team_scores", "away", policy_version=ledger.COMPARISON_POLICY_VERSION)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT side,policy_version FROM live_tips ORDER BY id").fetchall() == [
            ("home", ledger.POLICY_VERSION), ("away", ledger.COMPARISON_POLICY_VERSION)]


def test_closed_total_or_negative_btts_never_creates_receipt(tmp_path):
    db = tmp_path / "closed.db"
    for market, side in (("ft_total", "under_2_5"), ("ft_total", "over_2_5"), ("ft_btts", "no")):
        with pytest.raises(ValueError):
            record(db, market, side, home_goals=2, away_goals=1)


def test_new_negative_btts_never_uses_the_legacy_positive_btts_storage_key(tmp_path):
    # The older worker interprets every btts row as YES regardless of side.
    db = tmp_path / "live.db"
    with pytest.raises(ValueError):
        record(db, "btts", "no")
    assert not db.exists()


def test_next_scorer_needs_verified_order_even_in_a_mixed_market_fixture(tmp_path):
    db = tmp_path / "mixed.db"
    assert record(db, "ft_result", "home")
    assert record(db, "next_scorer", "away")
    assert record(db, "next_scorer", "none")
    api = Provider({123: fixture()}, {"response": [goal(10, 70), goal(20, 80)]})
    assert settle(db, api)["settled"] == 1
    assert stats(db)["ft_result"]["lost"] == 1 and stats(db)["next_scorer"]["open"] == 2
    api.events = {"response": [goal(10, 15), goal(20, 90, 9)]}
    assert settle(db, api)["settled"] == 2
    assert stats(db)["next_scorer"] == dict(won=1, lost=1, open=0, void=0)


def test_var_removed_goal_does_not_block_new_absolute_markets_or_reclassify_old_receipts(tmp_path):
    db = tmp_path / "var.db"
    for market, side in (("ft_result", "home"), ("ft_result", "draw"), ("btts", "yes"),
                         ("ft_btts", "no"), ("next_scorer", "none"), ("team_scores", "away")):
        assert record(db, market, side, policy_version=ledger.COMPARISON_POLICY_VERSION)
    assert record(db, "btts", "yes", fixture_id=124)  # Existing policy keeps its historical rule.
    assert record(db, "ft_result", "draw", fixture_id=125)
    finals = {n: fixture(fulltime=(0, 0), fixture_id=n) for n in (123, 124, 125)}
    finals[125]["teams"]["home"]["id"] = 99  # A final for the wrong home team is no evidence.
    assert settle(db, Provider(finals, {"response": []}))["settled"] == 4
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT fixture_id,market,side,status FROM live_tips ORDER BY id").fetchall() == [
            (123, "ft_result", "home", "lost"), (123, "ft_result", "draw", "won"),
            (123, "btts", "yes", "lost"), (123, "ft_btts", "no", "won"),
            (123, "next_scorer", "none", "open"), (123, "team_scores", "away", "open"),
            (124, "btts", "yes", "open"), (125, "ft_result", "draw", "open")]
