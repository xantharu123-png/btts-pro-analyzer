"""A market benchmark requires a complete native outcome set, not one price."""
from datetime import timedelta
import json
import sqlite3

import pytest

import forecast_evidence as evidence
from tests.test_forecast_evidence import NOW, START, candidate, document
from market_consensus import parse_fixture_consensus


def pair(db, monkeypatch, *, p=.7, fixture=1, books=(1,), decision=NOW):
    monkeypatch.setattr(evidence, "_now", lambda: decision)
    rows = [candidate(fixture, p), candidate(fixture, 1-p)]
    rows[1].update(candidate_id=f"{fixture}:BTTS_NO", market_key="BTTS_NO", selection="Nein")
    rows[1]["conservative_probability"] = max(0., 1-p-.05)
    payload = {"response": [{"fixture": {"id": fixture, "date": START.isoformat()},
        "update": decision.isoformat(), "bookmakers": [{"id": book, "name": f"Book {book}",
        "bets": [{"name": "Both Teams Score", "values": [
            {"value": "Yes", "odd": "2.0"}, {"value": "No", "odd": "1.8"}]}]}
        for book in books]}]}
    prices = parse_fixture_consensus(payload, rows, fetched_at=decision)
    for row in rows:
        row["reference_quote"] = prices[row["candidate_id"]].to_dict()
    return evidence.record_forecast_run(document(rows, decision), db, "model-v1")


def settle(db, monkeypatch, fixture=1):
    monkeypatch.setattr(evidence, "_now", lambda: START+timedelta(hours=3))
    proof = {"provider": "api-football", "provider_event_id": str(fixture),
        "source_record_id": f"fixture:{fixture}:final", "payload_sha256": "a"*64,
        "settlement_rule": "football-fulltime-v1"}
    for key, selection, outcome in (("BTTS_YES", "Ja", "WIN"), ("BTTS_NO", "Nein", "LOSS")):
        evidence.append_result(f"football:{fixture}", key, selection, outcome,
            observed_at=START+timedelta(hours=2), provenance=proof, db_path=db)


def report(db):
    from forecast_market_comparison import build_market_comparison
    return build_market_comparison(db, as_of=START+timedelta(hours=3))


def test_complete_no_vig_pair_scores_same_independent_events_read_only(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    pair(db, monkeypatch, books=(1, 2, 3))
    settle(db, monkeypatch)
    before = db.read_bytes()
    value = report(db)
    assert db.read_bytes() == before
    group = value["groups"][0]
    assert group["kind"] == "entry"
    assert group["unique_events"] == group["market_sets"] == 1
    assert group["bookmaker_snapshots"] == 3
    assert group["model_brier"] == pytest.approx(.3**2)
    market_p = (1/2)/(1/2+1/1.8)
    assert group["market_brier"] == pytest.approx((1-market_p)**2)
    assert group["brier_advantage"] == pytest.approx(group["market_brier"]-.09)
    assert value["coverage"]["closing_quotes"] == 0


@pytest.mark.parametrize("damage", ["missing_side", "other_book", "other_clock", "other_fetch",
    "native_event", "different_start", "future_price", "unknown_input_clock", "invalid_probability_sum",
    "inconsistent_results", "duplicate_conflict"])
def test_incomplete_or_mismatched_markets_are_not_normalized(tmp_path, monkeypatch, damage):
    db = tmp_path/"evidence.db"
    saved = pair(db, monkeypatch)
    settle(db, monkeypatch)
    with sqlite3.connect(db) as conn:
        for operation in ("update", "delete"):
            for table in ("forecast_rows", "forecast_quotes", "forecast_results"):
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_no_{operation}")
        target = saved["forecast_ids"][1]
        if damage == "missing_side":
            conn.execute("DELETE FROM forecast_quotes WHERE forecast_id=?", (target,))
        elif damage in {"other_book", "other_clock", "other_fetch", "future_price"}:
            column, changed = {"other_book": ("bookmaker_id", "elsewhere"),
                "other_clock": ("observed_at", (NOW-timedelta(seconds=1)).isoformat()),
                "other_fetch": ("fetched_at", (NOW-timedelta(seconds=1)).isoformat()),
                "future_price": ("fetched_at", (START+timedelta(seconds=1)).isoformat())}[damage]
            conn.execute(f"UPDATE forecast_quotes SET {column}=? WHERE forecast_id=?", (changed, target))
        elif damage in {"native_event", "different_start"}:
            row = conn.execute("SELECT payload_json FROM forecast_quotes WHERE forecast_id=?", (target,)).fetchone()
            payload = json.loads(row[0])
            payload[{"native_event": "fixture_id", "different_start": "starts_at"}[damage]] = (
                99 if damage == "native_event" else (START+timedelta(hours=1)).isoformat())
            conn.execute("UPDATE forecast_quotes SET payload_json=? WHERE forecast_id=?", (json.dumps(payload), target))
        elif damage in {"unknown_input_clock", "invalid_probability_sum"}:
            row = conn.execute("SELECT payload_json FROM forecast_rows WHERE forecast_id=?", (target,)).fetchone()
            payload = json.loads(row[0])
            payload["input_cutoff_at" if damage == "unknown_input_clock" else "probability"] = (
                None if damage == "unknown_input_clock" else .6)
            conn.execute("UPDATE forecast_rows SET payload_json=? WHERE forecast_id=?", (json.dumps(payload), target))
        elif damage == "inconsistent_results":
            conn.execute("UPDATE forecast_results SET outcome='WIN'")
        else:
            original = conn.execute("SELECT payload_json FROM forecast_quotes WHERE forecast_id=?", (target,)).fetchone()
            payload = json.loads(original[0])
            payload["odds"] += .1
            conn.execute("INSERT INTO forecast_quotes SELECT 'conflict',forecast_id,kind,bookmaker_id,"
                "observed_at,fetched_at,odds+.1,executable,? FROM forecast_quotes WHERE forecast_id=?", (json.dumps(payload), target))
    assert report(db)["groups"] == []


def test_repeated_decisions_never_replace_earliest_causal_probability(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    pair(db, monkeypatch, p=.7)
    pair(db, monkeypatch, p=.99, decision=NOW+timedelta(minutes=10))
    settle(db, monkeypatch)
    group = report(db)["groups"][0]
    assert group["model_brier"] == pytest.approx(.09)
    assert group["unique_events"] == 1


def test_missing_database_is_not_created_and_cli_is_opt_in(tmp_path, capsys):
    db = tmp_path/"missing.db"
    assert report(db)["database_present"] is False
    assert not db.exists()
    from scripts.selection_quality_report import main
    assert main(["--db", str(db), "--market-comparison"]) == 0
    assert "market_comparison" in json.loads(capsys.readouterr().out)


def test_closing_is_distinct_from_entry_and_keeps_original_probability(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    saved = pair(db, monkeypatch)
    close = START-timedelta(minutes=5)
    monkeypatch.setattr(evidence, "_now", lambda: close)
    with sqlite3.connect(db) as conn:
        rows = [json.loads(row[0])["quote_identity"] for row in conn.execute(
            "SELECT payload_json FROM forecast_rows ORDER BY market_key DESC")]
    payload = {"response": [{"fixture": {"id": 1, "date": START.isoformat()},
        "update": close.isoformat(), "bookmakers": [{"id": 1, "name": "Book 1",
        "bets": [{"name": "Both Teams Score", "values": [
            {"value": "Yes", "odd": "1.2"}, {"value": "No", "odd": "5.0"}]}]}]}]}
    prices = parse_fixture_consensus(payload, rows, fetched_at=close)
    for forecast_id, row in zip(saved["forecast_ids"], rows):
        evidence.append_quote_observation(forecast_id, prices[row["candidate_id"]], kind="closing", db_path=db)
    settle(db, monkeypatch)
    groups = {group["kind"]: group for group in report(db)["groups"]}
    assert set(groups) == {"entry", "closing"}
    assert groups["closing"]["model_brier"] == groups["entry"]["model_brier"]
    assert groups["closing"]["market_brier"] < groups["entry"]["market_brier"]


def test_three_way_result_is_not_reduced_to_a_binary_pair(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    rows = []
    for side, selection, probability in (("HOME", "Heimsieg", .5), ("DRAW", "Unentschieden", .3), ("AWAY", "Auswärtssieg", .2)):
        row = candidate(probability=probability)
        row.update(candidate_id="1:RESULT_"+side, market_key="RESULT_"+side, selection=selection)
        rows.append(row)
    payload = {"response": [{"fixture": {"id": 1, "date": START.isoformat()}, "update": NOW.isoformat(),
        "bookmakers": [{"id": 1, "name": "Book 1", "bets": [{"name": "Match Winner", "values": [
            {"value": "Home", "odd": "2.0"}, {"value": "Draw", "odd": "3.0"}, {"value": "Away", "odd": "4.0"}]}]}]}]}
    quotes = parse_fixture_consensus(payload, rows, fetched_at=NOW)
    for row in rows:
        row["reference_quote"] = quotes[row["candidate_id"]].to_dict()
    evidence.record_forecast_run(document(rows), db, "model-v1")
    monkeypatch.setattr(evidence, "_now", lambda: START+timedelta(hours=3))
    proof = {"provider": "api-football", "provider_event_id": "1", "source_record_id": "1:final",
        "payload_sha256": "a"*64, "settlement_rule": "football-fulltime-v1"}
    for row in rows:
        evidence.append_result("football:1", row["market_key"], row["selection"],
            "WIN" if row["market_key"] == "RESULT_HOME" else "LOSS", observed_at=START+timedelta(hours=2),
            provenance=proof, db_path=db)
    group = report(db)["groups"][0]
    assert group["model_brier"] == pytest.approx((.5**2+.3**2+.2**2)/3)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER forecast_quotes_no_delete")
        conn.execute("DELETE FROM forecast_quotes WHERE forecast_id=(SELECT forecast_id FROM forecast_rows WHERE market_key='RESULT_DRAW')")
    assert report(db)["groups"] == []


def test_overlapping_or_integer_line_markets_are_not_exhaustive_price_sets():
    from forecast_market_comparison import _contract
    for key in ("DC_1X", "HOME_RANGE_1_3", "TOTAL_OVER_2_0", "RESULT_TOTAL_12_OVER_1_5"):
        assert _contract({"sport": "football", "market_key": key}, {}) is None
    assert _contract({"sport": "football", "market_key": "HOME_CORNERS_OVER_3_5"}, {}) == (
        "HOME_CORNERS_3_5", "OVER", ("OVER", "UNDER"))


def test_independent_count_does_not_grow_with_more_bookmakers_or_revisions(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    pair(db, monkeypatch, fixture=1, books=(1, 2, 3))
    pair(db, monkeypatch, fixture=2, books=(1, 2, 3), p=.6)
    settle(db, monkeypatch, fixture=1)
    settle(db, monkeypatch, fixture=2)
    group = report(db)["groups"][0]
    assert group["unique_events"] == 2
    assert group["bookmaker_snapshots"] == 6
    assert group["paired_hac_standard_error"] is not None


@pytest.mark.parametrize("damage", ["native_list", "identity_list", "probability_bool", "forecast_json",
                                   "result_json", "result_native", "contradictory_result"])
def test_malformed_store_rows_are_excluded_not_scored_or_crashed(tmp_path, monkeypatch, damage):
    db = tmp_path/"evidence.db"
    saved = pair(db, monkeypatch)
    settle(db, monkeypatch)
    with sqlite3.connect(db) as conn:
        for table in ("forecast_rows", "forecast_results"):
            conn.execute(f"DROP TRIGGER {table}_no_update")
        if damage in {"native_list", "identity_list", "probability_bool", "forecast_json"}:
            payload = json.loads(conn.execute("SELECT payload_json FROM forecast_rows WHERE forecast_id=?",
                                             (saved["forecast_ids"][1],)).fetchone()[0])
            if damage == "native_list":
                payload["quote_identity"]["home_id"] = []
            elif damage == "identity_list":
                payload["quote_identity"] = []
            else:
                payload["probability"] = True
            conn.execute("UPDATE forecast_rows SET payload_json=? WHERE forecast_id=?",
                         ("{" if damage == "forecast_json" else json.dumps(payload), saved["forecast_ids"][1]))
        elif damage == "contradictory_result":
            conn.execute("INSERT INTO forecast_results SELECT 'contradiction',event_key,market_key,selection,"
                         "'WIN',observed_at,payload_json FROM forecast_results WHERE market_key='BTTS_NO'")
        else:
            result_id, raw = conn.execute("SELECT result_id,payload_json FROM forecast_results WHERE market_key='BTTS_NO'").fetchone()
            payload = json.loads(raw)
            payload["provenance"]["provider_event_id"] = "unrelated"
            conn.execute("UPDATE forecast_results SET payload_json=? WHERE result_id=?",
                         ("{" if damage == "result_json" else json.dumps(payload), result_id))
    assert report(db)["groups"] == []


def test_malformed_full_market_selection_does_not_crash_report(tmp_path, monkeypatch):
    from test_forecast_tennis_market_capture import fixture, settle as settle_tennis, NOW as TENNIS_NOW
    db = tmp_path/"evidence.db"
    row, document = fixture()
    monkeypatch.setattr(evidence, "_now", lambda: TENNIS_NOW)
    evidence.record_forecast_run(document, db, "test-tennis")
    observed = settle_tennis(db, row, monkeypatch)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER forecast_quotes_no_update")
        payload = json.loads(conn.execute("SELECT payload_json FROM forecast_quotes").fetchone()[0])
        payload["complete_market"]["outcomes"][1]["selection"] = []
        conn.execute("UPDATE forecast_quotes SET payload_json=?", (json.dumps(payload),))
    from forecast_market_comparison import build_market_comparison
    assert build_market_comparison(db, as_of=observed)["groups"] == []
