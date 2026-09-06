from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import sqlite3

import pytest

import forecast_evidence as evidence
from market_consensus import parse_fixture_consensus


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = NOW+timedelta(hours=2)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    return tmp_path / "evidence.db"


def candidate(fixture=1, probability=.6):
    return {
        "candidate_id": f"{fixture}:BTTS_YES", "fixture_id": fixture,
        "event_identity": f"football:{fixture}", "sport":"Fußball",
        "source":"football_challenge", "market_key":"BTTS_YES", "selection":"Ja",
        "scheduled_start":START.isoformat(), "probability":probability,
        "conservative_probability":probability-.05, "minimum_odds":1.5,
        "modeled_at":(NOW-timedelta(minutes=5)).isoformat(),
        "input_cutoff_at":(NOW-timedelta(minutes=10)).isoformat(),
        "policy_version":"selection-v1", "context":{"weather":{"status":"observed"}},
    }


def document(rows, decision=NOW):
    return {"generated_at":decision.isoformat(),"selection_policy_version":"catalog-v1","model_candidates":rows}


def quote(row, odds=2.0, captured=NOW):
    payload = {"response":[{"fixture":{"id":row["fixture_id"],"date":row["scheduled_start"]},"update":captured.isoformat(),"bookmakers":[{"id":i,"name":f"Book {i}","bets":[{"name":"Both Teams Score","values":[{"value":"Yes","odd":str(odds)}]}]} for i in (1,2,3)]}]}
    return parse_fixture_consensus(payload,[row],fetched_at=captured)[row["candidate_id"]]


def result(db, fixture=1, outcome="WIN", observed=START+timedelta(hours=2)):
    return evidence.append_result(
        f"football:{fixture}", "BTTS_YES", "Ja", outcome,
        observed_at=observed, db_path=db,
        provenance={"provider":"api-football","provider_event_id":str(fixture),"source_record_id":f"fixture:{fixture}:final","payload_sha256":"a"*64,"settlement_rule":"football-fulltime-v1"},
    )


def test_distinct_decisions_are_frozen_retries_are_idempotent(db, monkeypatch):
    original = candidate()
    original["context"]["api_key"] = "must-not-be-stored"
    original["context"]["reason"] = "token=must-not-be-stored"
    one = evidence.record_forecast_run(document([original]), db, "model-v1")
    assert evidence.record_forecast_run(document([original]), db, "model-v1")["run_id"] == one["run_id"]
    later = NOW+timedelta(minutes=30)
    monkeypatch.setattr(evidence,"_now",lambda:later)
    newer = candidate(probability=.63)
    two = evidence.record_forecast_run(document([newer],later),db,"model-v1")
    assert one["forecast_ids"] != two["forecast_ids"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM forecast_rows").fetchone()[0] == 2
        assert "must-not-be-stored" not in " ".join(r[0] for r in conn.execute("SELECT payload_json FROM forecast_rows"))
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):
            conn.execute("UPDATE forecast_rows SET model_version='wrong'")


def test_capture_never_backfills_past_games_or_future_model_information(db, monkeypatch):
    rows = [candidate(i) for i in range(1,4)]
    rows[0]["scheduled_start"] = (NOW-timedelta(seconds=1)).isoformat()
    rows[1]["modeled_at"] = (NOW+timedelta(seconds=1)).isoformat()
    rows[2]["input_cutoff_at"] = NOW.isoformat()
    recorded = evidence.record_forecast_run(document(rows),db,"model-v1")
    assert recorded["recorded"] == 0
    assert len(recorded["rejected"]) == 3
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=1))
    assert evidence.record_forecast_run(document([candidate()]),db,"model-v1")["recorded"] == 0


def test_future_document_cannot_be_labeled_prospective(db):
    with pytest.raises(ValueError,match="future"):
        evidence.record_forecast_run(document([candidate()],NOW+timedelta(hours=1)),db,"model-v1")


def test_unresolved_adapter_queue_is_read_only_unique_and_causal(db, monkeypatch):
    assert evidence.unresolved_forecasts(db,as_of=START) == []
    assert not db.exists()
    initial = candidate()
    initial.pop("modeled_at")
    initial.pop("input_cutoff_at")
    evidence.record_forecast_run(document([initial]),db,"model-v1")
    later = NOW+timedelta(minutes=10)
    monkeypatch.setattr(evidence,"_now",lambda:later)
    second = evidence.record_forecast_run(document([candidate()],later),db,"model-v1")
    assert evidence.unresolved_forecasts(db,as_of=NOW+timedelta(minutes=30)) == []
    rows = evidence.unresolved_forecasts(db,as_of=START+timedelta(hours=3))
    assert len(rows) == 1
    assert rows[0]["forecast_id"] == second["forecast_ids"][0]
    assert rows[0]["quote_identity"]["fixture_id"] == 1
    assert rows[0]["causal_provenance_complete"] is True
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=3))
    result(db)
    assert evidence.unresolved_forecasts(db,as_of=START+timedelta(hours=3)) == []
    assert len(evidence.unresolved_forecasts(db,as_of=START+timedelta(hours=1))) == 1


def test_result_cannot_switch_native_provider_or_event_identity(db, monkeypatch):
    row = candidate()
    row.update(sport="Tennis",event_identity="tennis:123",fixture_id=999,
               provider_event_id="123",fixture_source="ESPN")
    evidence.record_forecast_run(document([row]),db,"model-v1")
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=3))
    proof = {"provider":"espn","provider_event_id":"123","source_record_id":"123:final",
             "payload_sha256":"a"*64,"settlement_rule":"tennis-match-winner-v1"}
    with pytest.raises(ValueError,match="provider differs"):
        evidence.append_result("tennis:123","BTTS_YES","Ja","WIN",observed_at=START+timedelta(hours=2),
                               provenance={**proof,"provider":"sofascore"},db_path=db)
    with pytest.raises(ValueError,match="event differs"):
        evidence.append_result("tennis:123","BTTS_YES","Ja","WIN",observed_at=START+timedelta(hours=2),
                               provenance={**proof,"provider_event_id":"999"},db_path=db)
    evidence.append_result("tennis:123","BTTS_YES","Ja","WIN",observed_at=START+timedelta(hours=2),
                           provenance=proof,db_path=db)


def test_missing_input_clocks_are_counted_but_not_scored(db, monkeypatch):
    row = candidate()
    row.pop("modeled_at"); row.pop("input_cutoff_at")
    evidence.record_forecast_run(document([row]),db,"model-v1")
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=3))
    result(db)
    group = evidence.build_quality_report(db,as_of=START+timedelta(hours=3))["groups"][0]
    assert group["wins"] == 1
    assert group["unknown_input_clocks"] == 1
    assert group["scored"] == 0
    assert group["brier_score"] is None
    assert group["hypothetical_unit_roi"] is None


def test_prequential_scores_match_hand_calculation_and_clv_needs_no_result(db, monkeypatch):
    a, b = candidate(1,.6), candidate(2,.8)
    a["reference_quote"] = quote(a).to_dict()
    record = evidence.record_forecast_run(document([a,b]),db,"model-v1")
    assert record["quotes_rejected"] == []
    closing_time = START-timedelta(minutes=5)
    monkeypatch.setattr(evidence,"_now",lambda:closing_time)
    evidence.append_quote_observation(record["forecast_ids"][0],quote(a,1.8,closing_time),kind="closing",db_path=db)
    before = evidence.build_quality_report(db,as_of=closing_time)["groups"][0]
    assert before["scored"] == 0
    assert before["same_book_raw_clv_samples"] == 1
    assert before["same_book_raw_clv"] == pytest.approx(2/1.8-1)
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=3))
    result(db,1,"WIN"); result(db,2,"LOSS")
    group = evidence.build_quality_report(db,as_of=START+timedelta(hours=3))["groups"][0]
    assert group["unique_events"] == group["decision_revisions"] == group["scored"] == 2
    assert group["brier_score"] == pytest.approx((.4**2+.8**2)/2)
    assert group["log_loss"] == pytest.approx((-math.log(.6)-math.log(.2))/2)
    assert group["hypothetical_executable_samples"] == 1
    assert group["hypothetical_unit_roi"] == 1.0
    assert group["calibration_bins"][6]["n"] == 1
    assert group["calibration_bins"][8]["observed_rate"] == 0


def test_quote_identity_and_entry_capture_time_are_strict(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(candidate(2)).to_dict()
    bad = evidence.record_forecast_run(document([row]),db,"model-v1")
    assert bad["recorded"] == 1
    assert len(bad["quotes_rejected"]) == 1
    later = NOW+timedelta(minutes=1)
    monkeypatch.setattr(evidence,"_now",lambda:later)
    with pytest.raises(ValueError,match="after decision"):
        evidence.append_quote_observation(bad["forecast_ids"][0],quote(candidate(),captured=later),kind="entry",db_path=db)


def test_repeated_scans_do_not_inflate_scores_and_first_executable_quote_is_kept(db, monkeypatch):
    first = evidence.record_forecast_run(document([candidate(probability=.6)]),db,"model-v1")
    later = NOW+timedelta(minutes=30)
    monkeypatch.setattr(evidence,"_now",lambda:later)
    assert evidence.record_forecast_run(document([candidate(probability=.6)]),db,"model-v1")["run_id"] == first["run_id"]
    row = candidate(probability=.8)
    row["modeled_at"] = (later-timedelta(minutes=1)).isoformat()
    row["reference_quote"] = quote(row,captured=later).to_dict()
    evidence.record_forecast_run(document([row],later),db,"model-v1")
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=3))
    result(db)
    group = evidence.build_quality_report(db,as_of=START+timedelta(hours=3))["groups"][0]
    assert group["decision_revisions"] == 2
    assert group["unique_events"] == group["scored"] == group["wins"] == 1
    assert group["brier_score"] == pytest.approx(.4**2)
    assert group["hypothetical_executable_samples"] == 1
    assert group["hypothetical_unit_roi"] == 1.0


def test_future_context_observation_is_not_saved_as_known_at_decision(db):
    row = candidate()
    row["context_checked_at"] = (NOW+timedelta(seconds=1)).isoformat()
    record = evidence.record_forecast_run(document([row]),db,"model-v1")
    assert record["recorded"] == 0
    assert "context" in record["rejected"][0]["reason"]


def test_results_require_source_proof_exact_event_and_consistent_terminal(db, monkeypatch):
    evidence.record_forecast_run(document([candidate()]),db,"model-v1")
    monkeypatch.setattr(evidence,"_now",lambda:START+timedelta(hours=3))
    result(db)
    with pytest.raises(ValueError,match="contradictory"):
        result(db,outcome="LOSS")
    with pytest.raises(ValueError,match="matching"):
        result(db,fixture=2)
    proof={"provider":"manual","provider_event_id":"1","source_record_id":"test","payload_sha256":"a"*64,"settlement_rule":"manual"}
    with pytest.raises(ValueError,match="recognized"):
        evidence.append_result("football:1","BTTS_YES","Ja",True,observed_at=START+timedelta(hours=2),provenance=proof,db_path=db)


def test_report_missing_database_is_read_only_and_account_db_is_refused(tmp_path):
    missing = tmp_path/"missing.db"
    assert evidence.build_quality_report(missing)["database_present"] is False
    assert not missing.exists()
    account = tmp_path/"account.db"
    with sqlite3.connect(account) as conn:
        conn.execute("CREATE TABLE accounts(balance INTEGER)")
    with pytest.raises(ValueError,match="own database"):
        evidence._connect(account)
    with sqlite3.connect(account) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("accounts",)]


def test_report_cli_only_prints_json(tmp_path,capsys):
    from scripts.selection_quality_report import main
    assert main(["--db",str(tmp_path/"missing.db")]) == 0
    assert json.loads(capsys.readouterr().out)["database_present"] is False


def test_current_final_hour_quotes_automatically_bind_to_first_executable_forecast(db, monkeypatch):
    first = candidate()
    first["reference_quote"] = quote(first).to_dict()
    initial = evidence.record_forecast_run(document([first]), db, "model-v1")
    close_time = START-timedelta(minutes=5)
    monkeypatch.setattr(evidence, "_now", lambda: close_time)
    latest = candidate(probability=.7)
    # Internal model revision IDs may change; provider event/selection must not.
    latest["candidate_id"] = "revision-two:BTTS_YES"
    latest["reference_quote"] = quote(latest, 1.8, close_time).to_dict()
    saved = evidence.record_forecast_run(document([latest],close_time), db, "model-v1")
    assert saved["closing_quotes_recorded"] == 3
    with sqlite3.connect(db) as connection:
        closings = connection.execute("SELECT forecast_id FROM forecast_quotes WHERE kind='closing'").fetchall()
    assert {row[0] for row in closings} == {initial["forecast_ids"][0]}
    report = evidence.build_quality_report(db, as_of=close_time)["groups"][0]
    assert report["same_book_raw_clv_samples"] == 1
    assert report["same_book_raw_clv"] == pytest.approx(2/1.8-1)
    assert evidence.record_forecast_run(document([latest],close_time), db, "model-v1")["closing_quotes_recorded"] == 0


@pytest.mark.parametrize("reason", ["stale", "after_start", "native_identity_changed", "missing_model_clocks"])
def test_automatic_closing_capture_never_backfills_or_crosses_native_identity(db, monkeypatch, reason):
    first = candidate()
    if reason == "missing_model_clocks":
        first.pop("modeled_at"); first.pop("input_cutoff_at")
    first["reference_quote"] = quote(first).to_dict()
    evidence.record_forecast_run(document([first]), db, "model-v1")
    current = START+timedelta(minutes=1) if reason == "after_start" else START-timedelta(minutes=1)
    captured = START-timedelta(minutes=40) if reason == "stale" else START-timedelta(minutes=2)
    monkeypatch.setattr(evidence, "_now", lambda: current)
    latest = candidate()
    if reason == "native_identity_changed":
        latest["provider_event_id"] = "99"
    latest["reference_quote"] = quote(latest, 1.8, captured).to_dict()
    saved = evidence.record_forecast_run(document([latest],current), db, "model-v1")
    assert saved["closing_quotes_recorded"] == 0
    assert evidence.build_quality_report(db, as_of=current)["groups"][0]["same_book_raw_clv_samples"] == 0
