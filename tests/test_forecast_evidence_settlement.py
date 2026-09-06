from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

import forecast_evidence as evidence
from challenge_engine import MARKET_SPECS, MARKET_BY_KEY


DECISION = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = DECISION + timedelta(hours=2)
NOW = START + timedelta(hours=3)


def football_row(fixture_id=1, market="BTTS_YES"):
    return {
        "candidate_id": f"{fixture_id}:{market}", "fixture_id": fixture_id,
        "event_identity": f"football:{fixture_id}", "sport": "football",
        "fixture_source": "api-football", "provider_event_id": str(fixture_id),
        "home_id": 10, "away_id": 20, "home_team": "Alpha", "away_team": "Beta",
        "market_key": market, "selection": MARKET_BY_KEY[market].selection,
        "scheduled_start": START.isoformat(), "probability": .6,
        "modeled_at": DECISION.isoformat(), "input_cutoff_at": DECISION.isoformat(),
    }


def record(db, monkeypatch, rows):
    monkeypatch.setattr(evidence, "_now", lambda: DECISION)
    saved = evidence.record_forecast_run({"generated_at": DECISION.isoformat(),
        "selection_policy_version": "policy-v1", "model_candidates": rows}, db, "model-v1")
    assert saved["recorded"] == len(rows)
    monkeypatch.setattr(evidence, "_now", lambda: NOW)


def results(db):
    with sqlite3.connect(db) as connection:
        return [json.loads(row[0]) for row in connection.execute(
            "SELECT payload_json FROM forecast_results ORDER BY event_key,market_key,selection")]


class FootballProvider:
    def __init__(self, *, status="FT", missing_counts=False):
        self.calls = []
        self.status = status
        self.missing_counts = missing_counts

    def details_by_fixture(self, ids):
        self.calls.append(("details", tuple(ids)))
        return {fixture_id: {"fixture": {"id": fixture_id, "date": START.isoformat(),
            "status": {"short": self.status}}, "teams": {
                "home": {"id": 10, "name": "Alpha"}, "away": {"id": 20, "name": "Beta"}},
            "goals": {"home": 2, "away": 1}, "score": {"fulltime": {"home": 2, "away": 1}}}
            for fixture_id in ids}

    def statistics_by_fixture(self, fixture_id):
        self.calls.append(("statistics", fixture_id))
        if self.missing_counts:
            return None
        return [{"team": {"id": team_id}, "statistics": [
            {"type": "Corner Kicks", "value": corners},
            {"type": "Yellow Cards", "value": yellow}]}
            for team_id, corners, yellow in ((10, 6, 1), (20, 2, 3))]


def run(db, **kwargs):
    from forecast_evidence_settlement import run_forecast_evidence_settlements
    return run_forecast_evidence_settlements(db_path=db, now=NOW, **kwargs)


def test_all_football_markets_settle_from_one_event_and_statistics_observation(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row(market=spec.key) for spec in MARKET_SPECS])
    provider = FootballProvider()
    summary = run(db, football_provider=provider)
    assert summary["terminal_results"] == len(MARKET_SPECS)
    assert summary["unresolved_forecasts"] == 0
    by_market = {item["market_key"]: item["outcome"] for item in results(db)}
    assert {key: by_market[key] for key in (
        "BTTS_YES", "CORNERS_OVER_7_5", "CORNERS_OVER_8_5", "HOME_YELLOW_OVER_1_5"
    )} == {"BTTS_YES": "WIN", "CORNERS_OVER_7_5": "WIN",
          "CORNERS_OVER_8_5": "LOSS", "HOME_YELLOW_OVER_1_5": "LOSS"}
    assert provider.calls == [("details", (1,)), ("statistics", 1)]
    summary = run(db, football_provider=provider)
    assert summary["terminal_results"] == 0
    assert summary["operational_error_count"] == 0
    assert len(provider.calls) == 2
    assert evidence.build_quality_report(db, as_of=NOW)["groups"][0]["scored"] == 1


@pytest.mark.parametrize("status", ["1H", "NS", "AET", "PEN", "CANC", "PST", "AWD", "WO"])
def test_elapsed_time_and_non_regulation_statuses_never_make_result(tmp_path, monkeypatch, status):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row()])
    assert run(db, football_provider=FootballProvider(status=status))["terminal_results"] == 0
    assert results(db) == []


def test_missing_counts_leave_only_count_markets_open(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row(), football_row(market="CORNERS_OVER_7_5")])
    summary = run(db, football_provider=FootballProvider(missing_counts=True))
    assert summary["terminal_results"] == summary["unresolved_forecasts"] == 1
    assert results(db)[0]["market_key"] == "BTTS_YES"


@pytest.mark.parametrize("mutation", ["event", "team", "start", "bool_score", "selection"])
def test_mismatched_native_football_identity_or_invalid_score_fails_closed(tmp_path, monkeypatch, mutation):
    db = tmp_path / "evidence.db"
    row = football_row()
    if mutation == "selection":
        row["selection"] = "Nein"
    record(db, monkeypatch, [row])
    provider = FootballProvider()
    original = provider.details_by_fixture
    def details(ids):
        data = original(ids)
        if mutation == "event": data[1]["fixture"]["id"] = 2
        if mutation == "team": data[1]["teams"]["home"]["id"] = 99
        if mutation == "start": data[1]["fixture"]["date"] = (START + timedelta(days=1)).isoformat()
        if mutation == "bool_score": data[1]["goals"]["home"] = True
        return data
    provider.details_by_fixture = details
    summary = run(db, football_provider=provider)
    assert summary["terminal_results"] == 0
    assert summary["operational_error_count"] == 1


def test_finite_budget_rotates_and_missing_causal_clocks_never_trigger_provider(tmp_path, monkeypatch):
    from forecast_evidence_settlement import run_forecast_evidence_settlements
    db = tmp_path / "evidence.db"
    rows = [football_row(i) for i in range(1, 4)]
    rows.append(football_row(4)); rows[-1].pop("input_cutoff_at")
    record(db, monkeypatch, rows)
    provider = FootballProvider(status="NS")
    for step in range(3):
        summary = run_forecast_evidence_settlements(db_path=db, now=NOW+timedelta(minutes=30*step),
            football_provider=provider, max_events_per_sport=1)
        assert summary["checked_events"] == 1
    assert {call[1][0] for call in provider.calls} == {1, 2, 3}


def h2h_row(sport="tennis"):
    row = football_row()
    row.update(candidate_id=f"{sport}:55", sport=sport, event_identity=f"native-model-{sport}:55",
        provider_event_id="55", fixture_source="ESPN" if sport == "tennis" else "pandascore",
        market_key="H2H", selection="Beta", competitor_a="Alpha", competitor_b="Beta",
        selected_competitor="Beta", competitor_a_id="10", competitor_b_id="20")
    return row


def tennis_db(path, *, observed=NOW, termination="normal", winner="Beta", provider="ESPN"):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE predictions (id INTEGER PRIMARY KEY, settled INTEGER, "
            "player_a TEXT, player_b TEXT, provider_event_id TEXT, fixture_source TEXT, "
            "actual_winner TEXT, ret_flag INTEGER, result_observed_at TEXT, termination TEXT, "
            "player_a_sets INTEGER, player_b_sets INTEGER, scheduled_start_utc TEXT)")
        connection.execute("INSERT INTO predictions VALUES (7,1,'Alpha','Beta','55',?,?,0,?,?,1,2,?)",
            (provider, winner, observed.isoformat() if observed else None, termination, START.isoformat()))


def test_tennis_native_identity_result_time_and_source_db_are_preserved(tmp_path, monkeypatch):
    db, source = tmp_path / "evidence.db", tmp_path / "tennis.db"
    record(db, monkeypatch, [h2h_row()])
    tennis_db(source)
    before = source.read_bytes()
    summary = run(db, tennis_db_path=source)
    assert summary["terminal_results"] == 1
    assert results(db)[0]["outcome"] == "WIN"
    assert results(db)[0]["provenance"]["provider_event_id"] == "55"
    assert source.read_bytes() == before


@pytest.mark.parametrize("change", ["missing_time", "future_time", "before_start", "unknown_termination", "wrong_provider"])
def test_tennis_missing_or_mismatched_real_observation_stays_unresolved(tmp_path, monkeypatch, change):
    db, source = tmp_path / "evidence.db", tmp_path / "tennis.db"
    record(db, monkeypatch, [h2h_row()])
    tennis_db(source, observed={"missing_time": None, "future_time": NOW+timedelta(seconds=1),
        "before_start": START-timedelta(seconds=1)}.get(change, NOW),
        termination="unknown" if change == "unknown_termination" else "normal",
        provider="Sofascore" if change == "wrong_provider" else "ESPN")
    assert run(db, tennis_db_path=source)["terminal_results"] == 0


def test_esports_h2h_uses_real_winner_and_exact_competitor_ids(tmp_path, monkeypatch):
    db, source = tmp_path / "evidence.db", tmp_path / "esports.db"
    record(db, monkeypatch, [h2h_row("esports")])
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE esports_shadow_predictions (match_id INTEGER PRIMARY KEY, "
            "settled INTEGER, winner_team_id INTEGER, settled_at TEXT, selected_team_id INTEGER, "
            "selection TEXT, team1 TEXT, team2 TEXT, team1_id INTEGER, team2_id INTEGER, "
            "termination TEXT, final_score1 INTEGER, final_score2 INTEGER, scheduled_at TEXT)")
        connection.execute("INSERT INTO esports_shadow_predictions VALUES "
            "(55,1,10,?,20,'Beta','Alpha','Beta',10,20,'normal',2,1,?)", (NOW.isoformat(), START.isoformat()))
    before = source.read_bytes()
    assert run(db, esports_db_path=source)["terminal_results"] == 1
    assert results(db)[0]["outcome"] == "LOSS"
    assert source.read_bytes() == before


def test_missing_evidence_database_is_not_created(tmp_path):
    path = tmp_path / "missing.db"
    assert run(path)["terminal_results"] == 0
    assert not path.exists()


def test_aliases_for_one_native_event_reuse_statistics_observation(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    first = football_row(market="CORNERS_OVER_7_5")
    second = {**football_row(market="CORNERS_OVER_8_5"), "event_identity": "football:api-football:1"}
    record(db, monkeypatch, [first, second])
    provider = FootballProvider()
    assert run(db, football_provider=provider)["terminal_results"] == 2
    assert provider.calls == [("details", (1,)), ("statistics", 1)]


def test_native_event_budget_is_not_consumed_by_internal_aliases(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    first = football_row(market="CORNERS_OVER_7_5")
    second = {**football_row(market="CORNERS_OVER_8_5"), "event_identity": "football:api-football:1"}
    record(db, monkeypatch, [first, second])
    assert run(db, football_provider=FootballProvider(), max_events_per_sport=1)["terminal_results"] == 2


@pytest.mark.parametrize("mutation", ["teams_list", "team_list", "float_fixture", "bool_team", "duplicate_stat"])
def test_malformed_football_payload_does_not_crash_or_score(tmp_path, monkeypatch, mutation):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row(market="CORNERS_OVER_7_5")])
    provider = FootballProvider()
    original = provider.details_by_fixture
    def details(ids):
        data = original(ids)
        if mutation == "teams_list": data[1]["teams"] = ["bad"]
        if mutation == "team_list": data[1]["teams"]["home"] = ["bad"]
        if mutation == "float_fixture": data[1]["fixture"]["id"] = 1.0
        if mutation == "bool_team": data[1]["teams"]["home"]["id"] = True
        return data
    provider.details_by_fixture = details
    stats = provider.statistics_by_fixture
    def statistics(fixture_id):
        data = stats(fixture_id)
        if mutation == "duplicate_stat":
            data[0]["statistics"].append({"type": "Corner Kicks", "value": 10})
        return data
    provider.statistics_by_fixture = statistics
    summary = run(db, football_provider=provider)
    assert summary["terminal_results"] == 0
    assert summary["operational_error_count"] == 1


def test_football_source_failure_is_reported_without_fabricated_outcome(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row()])
    class Failing:
        def details_by_fixture(self, _ids):
            raise RuntimeError("token=private-provider-message")
    summary = run(db, football_provider=Failing())
    assert summary["terminal_results"] == 0
    assert summary["unresolved_forecasts"] == 1
    assert "football:result_source_failed" in summary["errors"]
    assert "private-provider-message" not in json.dumps(summary)
    assert summary["operational_error_count"] == 1


def test_conflicting_tennis_result_revisions_never_choose_a_convenient_winner(tmp_path, monkeypatch):
    db, source = tmp_path / "evidence.db", tmp_path / "tennis.db"
    record(db, monkeypatch, [h2h_row()])
    tennis_db(source)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO predictions SELECT 8,settled,player_a,player_b,provider_event_id,"
            "fixture_source,'Alpha',ret_flag,result_observed_at,termination,2,1,scheduled_start_utc "
            "FROM predictions WHERE id=7")
    summary = run(db, tennis_db_path=source)
    assert summary["terminal_results"] == 0
    assert summary["operational_error_count"] == 1


def test_tennis_walkover_is_explicit_void_not_a_loss(tmp_path, monkeypatch):
    db, source = tmp_path / "evidence.db", tmp_path / "tennis.db"
    record(db, monkeypatch, [h2h_row()])
    tennis_db(source, termination="walkover", winner=None)
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE predictions SET player_a_sets=NULL,player_b_sets=NULL")
    assert run(db, tennis_db_path=source)["terminal_results"] == 1
    assert results(db)[0]["outcome"] == "VOID"
    assert evidence.build_quality_report(db, as_of=NOW)["groups"][0]["scored"] == 0


def test_source_update_during_native_read_cannot_be_bound_to_old_payload_hash(tmp_path, monkeypatch):
    import forecast_evidence_settlement as settlement
    db, source = tmp_path / "evidence.db", tmp_path / "tennis.db"
    record(db, monkeypatch, [h2h_row()])
    tennis_db(source)
    original = settlement.tennis_result_loader
    def changed_loader(path):
        loader = original(path)
        def load(requests, now):
            answer = loader(requests, now)
            with sqlite3.connect(path) as connection:
                connection.execute("UPDATE predictions SET actual_winner='Alpha',player_a_sets=2,player_b_sets=1")
            return answer
        return load
    monkeypatch.setattr(settlement, "tennis_result_loader", changed_loader)
    assert run(db, tennis_db_path=source)["terminal_results"] == 0


def test_expected_result_coverage_is_not_an_operational_failure(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row(1), football_row(2)])
    unconfigured = run(db)
    assert unconfigured["errors"] == ["football:result_source_unconfigured"]
    assert unconfigured["operational_error_count"] == 0
    bounded = run(db, football_provider=FootballProvider(status="NS"), max_events_per_sport=1)
    assert "football:event_budget_reached" in bounded["errors"]
    assert bounded["unresolved_forecasts"] == 2
    assert bounded["operational_error_count"] == 0


def test_wrong_provider_result_identity_is_an_operational_failure(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row()])
    provider = FootballProvider()
    original = provider.details_by_fixture
    def wrong(ids):
        result = original(ids)
        result[1]["fixture"]["id"] = 123
        return result
    provider.details_by_fixture = wrong
    summary = run(db, football_provider=provider)
    assert summary["terminal_results"] == 0
    assert summary["errors"] == ["football:result_identity_mismatch"]
    assert summary["operational_error_count"] == 1


def test_native_database_corruption_is_not_reported_as_normal_coverage(tmp_path, monkeypatch):
    db, source = tmp_path / "evidence.db", tmp_path / "tennis.db"
    record(db, monkeypatch, [h2h_row()])
    missing = run(db, tennis_db_path=source)
    assert missing["operational_error_count"] == 0
    source.write_bytes(b"not a SQLite database")
    corrupted = run(db, tennis_db_path=source)
    assert "tennis:native_result_unavailable" in corrupted["errors"]
    assert corrupted["operational_error_count"] == 1
    assert corrupted["unresolved_forecasts"] == 1


def test_evidence_write_failure_is_counted_without_claiming_a_result(tmp_path, monkeypatch):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row()])
    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("write failure")
    monkeypatch.setattr(evidence, "append_result", broken)
    summary = run(db, football_provider=FootballProvider())
    assert summary["terminal_results"] == 0
    assert summary["unresolved_forecasts"] == 1
    assert summary["operational_error_count"] == 1


@pytest.mark.parametrize("kind,expected", [("no_observation", 0), ("batch_shape", 1), ("event_shape", 1), ("missing_status", 1)])
def test_absent_provider_observation_is_distinct_from_corrupt_result_payload(tmp_path, monkeypatch, kind, expected):
    db = tmp_path / "evidence.db"
    record(db, monkeypatch, [football_row()])
    provider = FootballProvider()
    original = provider.details_by_fixture
    def details(ids):
        if kind == "no_observation": return None
        if kind == "batch_shape": return ["invalid batch"]
        if kind == "event_shape": return {1: "invalid event"}
        answer = original(ids)
        answer[1]["fixture"].pop("status")
        return answer
    provider.details_by_fixture = details
    summary = run(db, football_provider=provider)
    assert summary["terminal_results"] == 0
    assert summary["operational_error_count"] == expected
