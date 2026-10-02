"""Offline regressions for live clocks and trustworthy red-card settlement."""

from __future__ import annotations

import pytest

from redcard_pattern_report import fine_phase_stats, phase_stats
from redcard_signal_log import _connect, log_signal, settle_open_signals
from scanners.ultra_live_scanner_v3 import UltraLiveScanner


class _LiveAPI:
    def __init__(self):
        self.calls = 0

    def get_match_statistics(self, *args):
        self.calls += 1
        return {"xg_home": 1.4, "xg_away": 1.1,
                "red_cards_home": 0, "red_cards_away": 0}


def _live_fixture(minute=93, phase="2H", extra=None):
    return {
        "fixture": {"id": 1, "status": {"elapsed": minute, "short": phase, "extra": extra}},
        "teams": {"home": {"id": 10, "name": "Home"},
                  "away": {"id": 20, "name": "Away"}},
        "goals": {"home": 1, "away": 0},
        "league": {"id": 39, "name": "League"},
    }


@pytest.mark.parametrize("minute,extra", [(90, None), (93, 8), (98, 8), (90, 4)])
def test_running_stoppage_clock_never_invents_zero_future_risk(minute, extra):
    api = _LiveAPI()
    result = UltraLiveScanner(None, api).analyze_live_match_ultra(
        _live_fixture(minute=minute, extra=extra))
    assert result is not None
    # The provider's elapsed injury-time field is not the referee's remaining
    # time. Do not manufacture an end time or a 100% no-goal probability.
    assert result["next_goal"]["no_goal_prob"] is None
    assert result["remaining_goals"]["under_0_5_probability"] is None
    assert result["phase_data"]["status"] == "2H"
    assert result["phase_data"]["remaining_minutes"] is None


@pytest.mark.parametrize("phase", ["ET", "BT", "P", "FT", "AET", "PEN", "SUSP", None])
def test_non_regulation_phases_are_not_regulation_live_models(phase):
    api = _LiveAPI()
    assert UltraLiveScanner(None, api).analyze_live_match_ultra(
        _live_fixture(minute=92, phase=phase)) is None
    assert api.calls == 0


def test_regular_live_clock_has_known_minimum_time_and_probability_mass():
    result = UltraLiveScanner(None, _LiveAPI()).analyze_live_match_ultra(
        _live_fixture(minute=60))
    assert result["phase_data"]["remaining_minutes"] == 30
    p = result["next_goal"]
    assert p["no_goal_prob"] < 100
    assert sum(p[key] for key in ("home_prob", "away_prob", "no_goal_prob")) == pytest.approx(100, abs=.15)


def test_first_half_injury_time_keeps_second_half_without_fake_whistle():
    result = UltraLiveScanner(None, _LiveAPI()).analyze_live_match_ultra(
        _live_fixture(minute=45, phase="1H", extra=5))
    assert result["phase_data"]["remaining_minutes"] == 45
    assert result["phase_data"]["elapsed_minutes"] == 50
    assert result["breakdown"]["remaining_home_mean"] == pytest.approx(1.4 / 50 * 45)
    assert result["phase_data"]["phase"] == "PRE_HT"


def test_halftime_phase_is_not_second_half_and_requires_a_plausible_clock():
    scanner = UltraLiveScanner(None, _LiveAPI())
    result = scanner.analyze_live_match_ultra(_live_fixture(minute=45, phase="HT"))
    assert result["phase_data"]["phase"] == "HALF_TIME"
    assert scanner.analyze_live_match_ultra(_live_fixture(minute=30, phase="HT")) is None


def _signal():
    return {
        "card": {"match": {"fixture": {"id": 123}, "league": {"name": "Test"}}, "minute": 40},
        "home": "Home", "away": "Away", "score": "0-0", "red_side": "home",
        "prediction_minute": 60, "fixture_red_card_count": 1,
        "prediction": {"next_goal_by_opponent": .5, "next_goal_by_red_team": .2,
                       "no_more_goals": .3, "too_late_for_signal": False, "data_quality": "LOW"},
    }


class _SettlementAPI:
    last_error = None

    def __init__(self, events, final=(0, 0), *, event_error=None, status="FT"):
        self.events = events
        self.final = final
        self.event_error = event_error
        self.status = status

    def _request(self, endpoint, params):
        self.last_error = None
        if endpoint == "fixtures":
            return {"response": [{"fixture": {"id": 123, "status": {"short": self.status}},
                                  "teams": {"home": {"id": 10}, "away": {"id": 20}},
                                  "goals": {"home": self.final[0], "away": self.final[1]},
                                  "score": {"fulltime": {"home": self.final[0], "away": self.final[1]}}}]}
        self.last_error = self.event_error
        return self.events


@pytest.mark.parametrize("events,error", [({}, "events: HTTP 503"),
                                          ({}, None), ({"response": None}, None),
                                          ({"response": []}, "events: HTTP 429"),
                                          ({"response": [], "errors": {"quota": "limit"}}, None)])
def test_failed_or_invalid_event_response_keeps_signal_open(tmp_path, events, error):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    result = settle_open_signals(_SettlementAPI(events, final=(0, 1), event_error=error),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 0
    conn = _connect(db)
    row = conn.execute("SELECT status,outcome,brier FROM signals").fetchone()
    conn.close()
    assert tuple(row) == ("open", None, None)


@pytest.mark.parametrize("final", [(0, 1), (1, 0)])
def test_empty_events_cannot_prove_no_goal_when_score_changed(tmp_path, final):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    result = settle_open_signals(_SettlementAPI({"response": []}, final=final),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 0


def test_legitimate_empty_event_response_and_unchanged_score_can_settle(tmp_path):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    result = settle_open_signals(_SettlementAPI({"response": []}),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 1


def test_incomplete_goal_list_does_not_settle_even_when_one_goal_is_known(tmp_path):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    goal = {"type": "Goal", "time": {"elapsed": 75}, "team": {"id": 20}}
    result = settle_open_signals(_SettlementAPI({"response": [goal]}, final=(1, 1)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 0


@pytest.mark.parametrize("goal", [
    {"type": "Goal", "time": {"elapsed": None}, "team": {"id": 20}},
    {"type": "Goal", "time": {"elapsed": 75}, "team": "invalid"},
    {"type": "Goal", "time": {"elapsed": 75}, "team": {"id": 20.0}},
    {"type": "Goal", "time": {"elapsed": 75, "extra": True}, "team": {"id": 20}},
])
def test_unverifiable_goal_event_stays_open_without_crashing(tmp_path, goal):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    result = settle_open_signals(_SettlementAPI({"response": [goal]}, final=(0, 1)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 0
    assert result["unverified_events"] == 1


def test_missed_penalty_is_not_a_goal_outcome(tmp_path):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    event = {"type": "Goal", "detail": "Missed Penalty", "time": {"elapsed": 75}, "team": {"id": 20}}
    result = settle_open_signals(_SettlementAPI({"response": [event]}), sleep_seconds=0, db_path=db)
    assert result["settled"] == 1
    conn = _connect(db)
    assert conn.execute("SELECT outcome FROM signals").fetchone()[0] == "no_goal"
    conn.close()


def test_confirmed_goal_outcome_is_scored_from_complete_goal_evidence(tmp_path):
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    event = {"type": "Goal", "time": {"elapsed": 75}, "team": {"id": 20}}
    result = settle_open_signals(_SettlementAPI({"response": [event]}, final=(0, 1)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 1
    conn = _connect(db)
    assert tuple(conn.execute("SELECT outcome,brier FROM signals").fetchone()) == ("opponent", pytest.approx(.38))
    conn.close()


@pytest.mark.parametrize("phase,extra", [("1H", 3), ("HT", None)])
def test_native_first_half_clock_is_bound_and_past_injury_goal_can_settle(tmp_path, phase, extra):
    import json
    db = tmp_path / "signals.db"
    entry = _signal()
    entry.update(prediction_minute=45, score="1-0")
    entry["card"]["match"]["fixture"]["status"] = {"short": phase, "elapsed": 45, "extra": extra}
    assert log_signal(entry, db_path=db)
    event = {"type": "Goal", "time": {"elapsed": 45, "extra": 1}, "team": {"id": 10}}
    result = settle_open_signals(_SettlementAPI({"response": [event]}, final=(1, 0)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 1
    conn = _connect(db)
    row = conn.execute("SELECT outcome,context_json FROM signals").fetchone()
    conn.close()
    assert row["outcome"] == "no_goal"
    assert json.loads(row["context_json"])["snapshot_clock"] == {
        "phase": phase, "elapsed": 45, "extra": extra or 0}


def test_first_half_stoppage_goal_precedes_second_half_goal_in_settlement(tmp_path):
    db = tmp_path / "signals.db"
    entry = _signal()
    entry["prediction_minute"] = 40
    entry["card"]["match"]["fixture"]["status"] = {"short": "1H", "elapsed": 40, "extra": None}
    assert log_signal(entry, db_path=db)
    events = [{"type": "Goal", "time": {"elapsed": 45, "extra": 4}, "team": {"id": 10}},
              {"type": "Goal", "time": {"elapsed": 46}, "team": {"id": 20}}]
    result = settle_open_signals(_SettlementAPI({"response": events}, final=(1, 1)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 1
    conn = _connect(db)
    assert conn.execute("SELECT outcome FROM signals").fetchone()[0] == "red_team"
    conn.close()


def test_second_half_snapshot_does_not_count_first_half_added_goal_again(tmp_path):
    db = tmp_path / "signals.db"
    entry = _signal()
    entry.update(prediction_minute=46, score="1-0")
    entry["card"]["match"]["fixture"]["status"] = {"short": "2H", "elapsed": 46, "extra": None}
    assert log_signal(entry, db_path=db)
    events = [{"type": "Goal", "time": {"elapsed": 45, "extra": 4}, "team": {"id": 10}},
              {"type": "Goal", "time": {"elapsed": 75}, "team": {"id": 20}}]
    result = settle_open_signals(_SettlementAPI({"response": events}, final=(1, 1)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 1
    conn = _connect(db)
    assert conn.execute("SELECT outcome FROM signals").fetchone()[0] == "opponent"
    conn.close()


def test_legacy_snapshot_without_native_first_half_clock_stays_open_if_ambiguous(tmp_path):
    db = tmp_path / "signals.db"
    entry = _signal()
    entry.update(prediction_minute=45, score="1-0")
    assert log_signal(entry, db_path=db)
    event = {"type": "Goal", "time": {"elapsed": 45, "extra": 1}, "team": {"id": 10}}
    result = settle_open_signals(_SettlementAPI({"response": [event]}, final=(1, 0)),
                                 sleep_seconds=0, db_path=db)
    assert result["settled"] == 0


@pytest.mark.parametrize("clock", [
    {"phase": [], "elapsed": 60, "extra": 0},
    {"phase": "2H", "elapsed": 59, "extra": 0},
    {"phase": "ET", "elapsed": 60, "extra": 0},
    {"phase": "2H", "elapsed": 60, "extra": False},
])
def test_invalid_bound_snapshot_clock_stays_open_without_crashing(tmp_path, clock):
    import json
    db = tmp_path / "signals.db"
    assert log_signal(_signal(), db_path=db)
    conn = _connect(db)
    conn.execute("UPDATE signals SET context_json=?", (json.dumps({"snapshot_clock": clock}),))
    conn.commit()
    conn.close()
    result = settle_open_signals(_SettlementAPI({"response": []}), sleep_seconds=0, db_path=db)
    assert result["settled"] == 0
    assert result["unverified_events"] == 1


def test_first_goal_result_minute_comes_from_validated_period_clock():
    from redcard_signal_log import _first_goal_after
    event = {"type": "Goal", "time": {"elapsed": 92}, "team": {"id": 20}}
    assert _first_goal_after([event], 90, "FT") == (92, 20)
    # A packed clock plus a positive extra field is not a native Goal clock:
    # reject ambiguity rather than count those minutes twice.
    event["time"]["extra"] = 2
    assert _first_goal_after([event], 90, "FT") is None


@pytest.mark.parametrize("provider_errors,unverified,expected", [(1, 0, 1), (0, 1, 0), (0, 0, 0)])
def test_settlement_cli_reports_provider_failure_without_treating_pending_as_crash(
        monkeypatch, provider_errors, unverified, expected):
    from types import SimpleNamespace
    import redcard_signal_log as log

    monkeypatch.setattr("sys.argv", ["redcard_signal_log.py", "--settle"])
    monkeypatch.setattr("config_loader.load_app_config", lambda: SimpleNamespace(api_football_key="offline"))
    monkeypatch.setattr("api_football.APIFootball", lambda *a, **kw: object())
    monkeypatch.setattr(log, "settle_open_signals", lambda *a, **kw:
                        {"settled": 0, "provider_errors": provider_errors, "unverified_events": unverified})
    assert log.main() == expected


@pytest.mark.parametrize("red_minute", [0, 20, 43, 73, 83, 90, 93])
def test_phase_exposure_partitions_the_entire_observation_window(red_minute):
    case = {"complex": False, "red_minute": red_minute, "goals_after": []}
    for report in (phase_stats, fine_phase_stats):
        stats = report([case])
        assert sum(item["exposure"] for item in stats.values()) == 93 - red_minute


def test_integer_phase_boundaries_assign_each_goal_exactly_once():
    times = [0, 10, 11, 20, 21, 30, 31, 40, 41, 45, 46]
    case = {"complex": False, "red_minute": 0,
            "goals_after": [{"since_card": m, "by_11_team": True} for m in times]}
    coarse, fine = phase_stats([case]), fine_phase_stats([case])
    assert sum(item["goals_11"] for item in coarse.values()) == len(times)
    assert sum(item["goals_11"] for item in fine.values()) == len(times)
    assert coarse["0-20"]["goals_11"] == 4
    assert coarse["21-40"]["goals_11"] == 4
    assert fine["11-20"]["goals_11"] == 2


def test_every_possible_minute_has_equal_coarse_and_fine_exposure():
    cases = [{"complex": False, "red_minute": minute, "goals_after": []} for minute in range(94)]
    expected = sum(93 - minute for minute in range(94))
    for report in (phase_stats, fine_phase_stats):
        assert sum(item["exposure"] for item in report(cases).values()) == expected
