"""Public live receipts are prospective, first-display observations, not shadow rows."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest


NOW = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)


def record(db, market="next_goal", side="any", **changes):
    from live_tip_ledger import record_displayed_live_tip

    values = dict(fixture_id=123, market=market, side=side, minute=61, phase="2H", extra=None,
                  home_goals=1, away_goals=0, home_id=10, away_id=20, probability=0.73,
                  snapshot_at=NOW - timedelta(seconds=30), model_version="test-model-v1", now=NOW)
    return record_displayed_live_tip(**(values | changes), db_path=db)


def stats(db):
    from live_tip_ledger import live_tip_stats

    return live_tip_stats(db_path=db)


def test_empty_stats_and_settlement_do_not_create_files_or_call_provider(tmp_path):
    db = tmp_path / "not-created" / "public.db"
    assert stats(db) == {name: dict(won=0, lost=0, open=0, void=0)
                         for name in ("next_goal", "team_scores", "btts", "red_next")}
    api = Provider({})
    assert settle(db, api)["fixtures_checked"] == 0
    assert api.calls == []
    assert not db.parent.exists()


def test_invalid_ledger_is_reported_not_rendered_as_zero(tmp_path):
    db = tmp_path / "public.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE live_tips(market,status)")
        c.execute("INSERT INTO live_tips VALUES('unknown','won')")
    with pytest.raises(sqlite3.DatabaseError):
        stats(db)


def test_freezes_first_display_not_each_rerender_and_preserves_exact_selection(tmp_path):
    db = tmp_path / "public.db"
    assert record(db, "team_scores", "home", extra=0)
    assert not record(db, "team_scores", "home", minute=70, probability=.88,
                      now=NOW + timedelta(seconds=40))
    assert record(db, "team_scores", "away", minute=70)
    assert stats(db)["team_scores"] == dict(won=0, lost=0, open=2, void=0)
    with sqlite3.connect(db) as c:
        home = c.execute("SELECT minute,phase,extra,home_goals,away_goals,home_id,away_id,"
                         "probability,model_version,policy_version,snapshot_at,shown_at "
                         "FROM live_tips WHERE side='home'").fetchone()
    assert home[:9] == (61, "2H", 0, 1, 0, 10, 20, .73, "test-model-v1")
    assert home[9]
    assert datetime.fromisoformat(home[10]) == NOW - timedelta(seconds=30)
    assert datetime.fromisoformat(home[11]) == NOW


@pytest.mark.parametrize("changes", [
    {"snapshot_at": NOW - timedelta(seconds=121)}, {"snapshot_at": NOW + timedelta(microseconds=1)},
    {"snapshot_at": NOW.replace(tzinfo=None)}, {"snapshot_at": None}, {"phase": "FT"},
    {"phase": "ET"}, {"phase": "2H", "minute": 33}, {"phase": "1H", "minute": 88},
    {"minute": 60, "extra": 2}, {"home_id": True}, {"home_id": 20}, {"fixture_id": -1},
    {"away_goals": None}, {"home_goals": False}, {"probability": float("nan")},
    {"probability": 73}, {"model_version": ""}, {"market": "next_goal", "side": "home"},
    {"market": "btts", "side": "yes", "away_goals": 1},
])
def test_unverifiable_or_already_decided_preconditions_never_write(tmp_path, changes):
    db = tmp_path / "public.db"
    with pytest.raises(ValueError):
        record(db, **changes)
    assert not db.exists()


def test_identity_drift_cannot_attach_later_selection_to_another_match(tmp_path):
    db = tmp_path / "public.db"
    record(db)
    with pytest.raises(ValueError):
        record(db, "team_scores", "home", home_id=11)
    assert stats(db)["team_scores"]["open"] == 0


def fixture(status="FT", fulltime=(1, 1), goals=None, fixture_id=123):
    def pair(values):
        return {"home": values[0], "away": values[1]}
    return {"fixture": {"id": fixture_id, "status": {"short": status}},
            "teams": {"home": {"id": 10}, "away": {"id": 20}},
            "score": {"fulltime": pair(fulltime)}, "goals": pair(goals or fulltime)}


def goal(team, minute, extra=0):
    return {"type": "Goal", "detail": "Normal Goal", "team": {"id": team},
            "time": {"elapsed": minute, "extra": extra}}


class Provider:
    last_error = None

    def __init__(self, fixtures, events=None):
        self.fixtures = fixtures
        self.events = events
        self.calls = []

    def _request(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint == "fixtures":
            return {"response": [self.fixtures[params["id"]]]}
        assert endpoint == "fixtures/events" and set(params) == {"fixture"}
        return self.events


def settle(db, provider, limit=25):
    from live_tip_ledger import settle_displayed_live_tips

    return settle_displayed_live_tips(provider, max_fixtures=limit, db_path=db,
                                     now=NOW + timedelta(hours=3), sleep_seconds=0)


def test_all_four_settle_once_on_one_fixture_including_late_stoppage_goal(tmp_path):
    db = tmp_path / "public.db"
    for market, side in [("next_goal", "any"), ("team_scores", "home"), ("team_scores", "away"),
                         ("btts", "yes"), ("red_next", "away"), ("red_next", "none")]:
        record(db, market, side)
    api = Provider({123: fixture()}, {"response": [goal(20, 90, 9), goal(10, 15)]})
    result = settle(db, api)
    assert result["fixtures_checked"] == 1 and result["settled"] == 6
    assert api.calls == [("fixtures", {"id": 123}), ("fixtures/events", {"fixture": 123})]
    assert stats(db) == {
        "next_goal": dict(won=1, lost=0, open=0, void=0),
        "team_scores": dict(won=1, lost=1, open=0, void=0),
        "btts": dict(won=1, lost=0, open=0, void=0),
        "red_next": dict(won=1, lost=1, open=0, void=0),
    }
    assert settle(db, api)["fixtures_checked"] == 0


@pytest.mark.parametrize("end", ["AET", "PEN"])
def test_regulation_only_even_when_extra_time_changes_score(tmp_path, end):
    db = tmp_path / "public.db"
    record(db, "next_goal", "any")
    record(db, "btts", "yes")
    record(db, "red_next", "none")
    api = Provider({123: fixture(end, (1, 0), goals=(1, 2))},
                   {"response": [goal(10, 15), goal(20, 91), goal(20, 115)]})
    assert settle(db, api)["settled"] == 3
    actual = stats(db)
    assert actual["next_goal"]["lost"] == actual["btts"]["lost"] == actual["red_next"]["won"] == 1


@pytest.mark.parametrize("change", ["regressed", "swapped", "wrong_id", "extra_no_fulltime",
                                    "ft_conflict", "invalid_status", "malformed"])
def test_unverified_final_fixture_never_counts_as_loss(tmp_path, change):
    db = tmp_path / "public.db"
    record(db)
    end = fixture()
    if change == "regressed":
        end = fixture(fulltime=(0, 1))
    elif change == "swapped":
        end["teams"] = {"home": {"id": 20}, "away": {"id": 10}}
    elif change == "wrong_id":
        end["fixture"]["id"] = False
    elif change == "extra_no_fulltime":
        end = fixture("PEN", fulltime=(None, None), goals=(1, 2))
    elif change == "ft_conflict":
        end = fixture(fulltime=(1, 0), goals=(1, 1))
    elif change == "invalid_status":
        end["fixture"]["status"]["short"] = ["FT"]
    else:
        end["teams"]["away"] = True
    assert settle(db, Provider({123: end}))["settled"] == 0
    assert stats(db)["next_goal"] == dict(won=0, lost=0, open=1, void=0)


@pytest.mark.parametrize("events,error", [
    ({}, 1), ({"response": [], "errors": {"quota": "reached"}}, 1),
    ({"response": [goal(10, 15)]}, 0),
    ({"response": [goal(10, 15), goal(20, 60)]}, 0),  # away goal before observation conflicts with 1:0
])
def test_missing_timeline_keeps_only_order_dependent_tip_open(tmp_path, events, error):
    db = tmp_path / "public.db"
    record(db, "red_next", "away")
    record(db, "btts", "yes")
    api = Provider({123: fixture()}, events)
    result = settle(db, api)
    assert result["settled"] == 1 and result["provider_errors"] == error
    assert stats(db)["red_next"] == dict(won=0, lost=0, open=1, void=0)
    assert stats(db)["btts"]["won"] == 1


def test_var_correction_replaces_snapshot_goal_no_false_loss_on_relative_markets(tmp_path):
    db = tmp_path / "public.db"
    for market, side in (("next_goal","any"), ("team_scores","home"), ("red_next","none"), ("btts","yes")):
        record(db, market, side)
    # Shown 1:0 at 61'. VAR removed that goal: only the replacement at 80' counts.
    api = Provider({123: fixture(fulltime=(1, 0))}, {"response": [goal(10, 80)]})
    assert settle(db, api)["settled"] == 1
    counts = stats(db)
    assert counts["btts"]["lost"] == 1
    for market in ("next_goal","team_scores","red_next"):
        assert counts[market] == dict(open=1, won=0, lost=0, void=0)


def test_halftime_after_all_first_half_stoppage_but_before_second_half(tmp_path):
    db = tmp_path / "public.db"
    for market, side in (("next_goal","any"), ("team_scores","home"), ("red_next","away")):
        record(db, market, side, phase="HT", minute=45)
    api = Provider({123: fixture()}, {"response": [goal(10, 45, 12), goal(20, 46)]})
    assert settle(db, api)["settled"] == 3
    actual = stats(db)
    assert actual["next_goal"]["won"] == actual["team_scores"]["lost"] == actual["red_next"]["won"] == 1


def test_two_next_teams_at_same_minute_only_blocks_the_order_question(tmp_path):
    db = tmp_path / "public.db"
    for market, side in (("next_goal","any"), ("team_scores","home"), ("red_next","away")):
        record(db, market, side)
    api = Provider({123: fixture(fulltime=(2, 1))}, {"response": [goal(10, 12), goal(10, 80), goal(20, 80)]})
    assert settle(db, api)["settled"] == 2
    counts = stats(db)
    assert counts["red_next"]["open"] == counts["next_goal"]["won"] == counts["team_scores"]["won"] == 1


@pytest.mark.parametrize("status", ["CANC", "ABD", "AWD", "WO"])
def test_definitive_void_is_separate_and_does_not_require_score_or_events(tmp_path, status):
    db = tmp_path / "public.db"
    record(db)
    end = fixture(status, (None, None))
    api = Provider({123: end})
    assert settle(db, api)["void"] == 1
    assert stats(db)["next_goal"] == dict(won=0, lost=0, open=0, void=1)
    assert len(api.calls) == 1


def test_budget_rotates_past_unresolved_fixture_and_never_fetches_events_for_btts_only(tmp_path):
    db = tmp_path / "public.db"
    record(db, "btts", "yes", fixture_id=100)
    record(db, "btts", "yes", fixture_id=101)
    api = Provider({100: fixture("PST", fixture_id=100), 101: fixture(fixture_id=101)})
    assert settle(db, api, limit=0)["fixtures_checked"] == 0
    assert settle(db, api, limit=1)["still_running"] == 1
    assert settle(db, api, limit=1)["settled"] == 1
    assert api.calls == [("fixtures", {"id": 100}), ("fixtures", {"id": 101})]
    assert stats(db)["btts"] == dict(won=1, lost=0, open=1, void=0)
