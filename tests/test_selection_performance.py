from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import sqlite3

import pytest

import forecast_evidence as evidence
import selection_performance as performance
from market_consensus import parse_fixture_consensus
from scripts.selection_performance_report import main


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = NOW + timedelta(hours=2)
AS_OF = NOW + timedelta(days=1)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    return tmp_path / "evidence.db"


def candidate(fixture=1, probability=.6, market="BTTS_YES", selection="Ja", start=START):
    return dict(candidate_id=f"{fixture}:{market}", fixture_id=fixture,
        event_identity=f"football:{fixture}", sport="Fußball", source="football_challenge",
        market_key=market, selection=selection, scheduled_start=start.isoformat(),
        probability=probability, minimum_odds=2.5, policy_version="p1",
        modeled_at=(NOW - timedelta(minutes=5)).isoformat(),
        input_cutoff_at=(NOW - timedelta(minutes=10)).isoformat())


def record(db, rows, *, decision=NOW, model="m1"):
    return evidence.record_forecast_run(dict(generated_at=decision.isoformat(),
        selection_policy_version="p1", model_candidates=rows), db, model)


def quote(row, odds=2.0, clock=NOW, prices=None):
    target = performance.exact_market_target(row["market_key"])
    payload = {"response": [{"fixture": {"id": row["fixture_id"], "date": row["scheduled_start"]},
        "update": clock.isoformat(), "bookmakers": [{"id": i, "name": f"Book {i}",
        "bets": [{"name": target[0], "values": [{"value": target[1], "odd": str((prices or {}).get(i, odds))}]}]}
        for i in (1, 2, 3)]}]}
    return parse_fixture_consensus(payload, [row], fetched_at=clock)[row["candidate_id"]].to_dict()


def result(db, monkeypatch, row=None, outcome="WIN", *, actual_start=None, observed=None):
    row = row or candidate()
    observed = observed or _utc(row["scheduled_start"]) + timedelta(hours=2)
    monkeypatch.setattr(evidence, "_now", lambda: max(AS_OF, observed))
    provider = row.get("fixture_source", "api-football").casefold()
    provider_id = row.get("provider_event_id", row["fixture_id"])
    proof = dict(provider=provider, provider_event_id=str(provider_id), source_record_id="terminal:1",
        payload_sha256="a" * 64, settlement_rule="native-fulltime-v1")
    if actual_start is not None:
        proof["actual_starts_at"] = actual_start.isoformat()
    return evidence.append_result(row["event_identity"], row["market_key"], row["selection"], outcome,
        observed_at=observed, provenance=proof, db_path=db)


def _utc(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def report(db, **kwargs):
    return performance.build_selection_performance_report(db, from_day="2030-01-01", through_day="2030-01-01", as_of=AS_OF, **kwargs)


def insert_result_copy(db, **updates):
    with sqlite3.connect(db) as conn:
        raw = conn.execute("SELECT payload_json FROM forecast_results LIMIT 1").fetchone()[0]
        value = json.loads(raw)
        value.update(updates)
        if "provenance" in updates:
            value["provenance"] = updates["provenance"]
        digest = performance._hash(value)
        conn.execute("INSERT INTO forecast_results VALUES(?,?,?,?,?,?,?)", (digest,
            value["event_key"], value["market_key"], value["selection"], value["outcome"],
            value["observed_at"], performance._json(value)))


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "absent" / "evidence.db"
    data = report(path)
    assert data["database_present"] is False
    assert data["summary"]["selections"] == 0
    assert not path.parent.exists()


def test_reader_never_initializes_or_writes_database(db, monkeypatch):
    record(db, [candidate()])
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    monkeypatch.setattr(evidence, "_connect", lambda *_: pytest.fail("writer was invoked"))
    report(db)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_window_query_has_no_correlated_result_plan(db, monkeypatch):
    record(db, [candidate()])
    queries = []
    connect = sqlite3.connect
    def observed_connect(*args, **kwargs):
        conn = connect(*args, **kwargs)
        conn.set_trace_callback(queries.append)
        return conn
    monkeypatch.setattr(performance.sqlite3, "connect", observed_connect)
    report(db)
    assert not any("EXISTS" in sql.upper() for sql in queries)
    assert sum("SELECT event_key FROM forecast_results WHERE observed_at" in sql for sql in queries) == 1


def test_long_read_only_query_aborts_instead_of_returning_partial_report(db):
    record(db, [candidate(i) for i in range(1, 201)])
    with pytest.raises(TimeoutError, match="bounded read-only"):
        report(db, query_timeout_seconds=1e-12)


def test_moved_result_row_cap_is_checked_before_key_deduplication(db, monkeypatch):
    record(db, [candidate()])
    result(db, monkeypatch, actual_start=START)
    insert_result_copy(db, observed_at=(START + timedelta(hours=2, seconds=1)).isoformat())
    insert_result_copy(db, observed_at=(START + timedelta(hours=2, seconds=2)).isoformat())
    monkeypatch.setattr(performance, "_MAX_ROWS", 2)
    with pytest.raises(ValueError, match="moved-event row limit"):
        report(db)


@pytest.mark.parametrize("day,expected_hours", [("2026-03-29", 23), ("2026-10-25", 25)])
def test_zurich_completed_days_respect_dst(tmp_path, day, expected_hours):
    data = performance.build_selection_performance_report(tmp_path / "missing.db", from_day=day,
        through_day=day, as_of="2030-01-01T00:00:00+00:00")
    assert (_utc(data["window_end_exclusive_utc"]) - _utc(data["window_start_utc"])).total_seconds() == expected_hours * 3600


@pytest.mark.parametrize("kwargs", [dict(through_day="2030-01-02"), dict(from_day="2030-01-03"), dict(unit_stake=0), dict(unit_stake=float("nan"))])
def test_rejects_unfinished_or_invalid_ranges(tmp_path, kwargs):
    args = dict(from_day="2030-01-01", through_day="2030-01-01", as_of=AS_OF)
    args.update(kwargs)
    with pytest.raises(ValueError):
        performance.build_selection_performance_report(tmp_path / "absent.db", **args)


def test_internal_pool_is_not_called_visible_customer_tips(db):
    record(db, [candidate()])
    data = report(db)
    assert data["cohort"] == "internal_candidate_pool"
    assert "not proof of customer-visible" in data["limitations"][0]


def test_explicit_empty_cohort_does_not_fall_back_to_internal_pool(db):
    record(db, [candidate()])
    data = report(db, forecast_ids=[])
    assert data["cohort"] == "explicit_forecast_ids"
    assert data["summary"]["selections"] == 0


def test_explicit_id_cohort_is_exact(db):
    recorded = record(db, [candidate(1), candidate(2)])
    data = report(db, forecast_ids=recorded["forecast_ids"][:1])
    assert data["summary"]["selections"] == 1
    assert data["selections"][0]["forecast_id"] == recorded["forecast_ids"][0]


def test_missing_results_remain_unresolved_not_losses(db):
    record(db, [candidate()])
    summary = report(db)["summary"]
    assert summary["unresolved"] == 1
    assert summary["role_binding_coverage"] == {"missing": 1}
    assert summary["losses"] == summary["scored"] == summary["hypothetical_resolved_quote_samples"] == 0
    assert summary["hit_rate"] is summary["hypothetical_roi"] is None


def test_duplicate_revisions_and_policy_changes_count_once(db, monkeypatch):
    record(db, [candidate(probability=.6)])
    later = NOW + timedelta(minutes=10)
    monkeypatch.setattr(evidence, "_now", lambda: later)
    newer = candidate(probability=.9)
    newer["policy_version"] = "p2"
    record(db, [newer], decision=later, model="m2")
    result(db, monkeypatch)
    data = report(db)
    assert data["decision_revisions_read"] == 2
    assert data["duplicate_revisions_collapsed"] == 1
    assert data["summary"]["wins"] == 1
    assert data["selections"][0]["probability"] == .6
    assert len(data["groups"]) == 1
    assert data["groups"][0]["model_version"] == "m1"


def test_first_causal_revision_not_best_later_probability(db, monkeypatch):
    original = candidate()
    original.pop("modeled_at")
    original.pop("input_cutoff_at")
    record(db, [original])
    later = NOW + timedelta(minutes=10)
    monkeypatch.setattr(evidence, "_now", lambda: later)
    ids = record(db, [candidate(probability=.7)], decision=later)["forecast_ids"]
    result(db, monkeypatch)
    data = report(db)
    assert data["selections"][0]["forecast_id"] == ids[0]
    assert data["summary"]["scored"] == 1


def test_missing_input_clocks_allow_outcome_count_but_no_score_or_returns(db, monkeypatch):
    row = candidate()
    row.pop("modeled_at")
    row.pop("input_cutoff_at")
    row["reference_quote"] = quote(row)
    record(db, [row])
    result(db, monkeypatch)
    data = report(db)
    assert data["summary"]["wins"] == 1
    assert data["summary"]["hit_rate"] == 1
    assert data["summary"]["causal_hit_rate"] is None
    assert data["summary"]["scored"] == 0
    assert data["summary"]["hypothetical_resolved_quote_samples"] == 0
    assert data["clock_exclusions"] == {"missing_input_clocks": 1}


def test_brier_log_loss_and_probability_bins_match_hand_calculation(db, monkeypatch):
    one, two = candidate(1, .6), candidate(2, .8)
    record(db, [one, two])
    result(db, monkeypatch, one, "WIN")
    result(db, monkeypatch, two, "LOSS")
    summary = report(db)["summary"]
    assert summary["brier_score"] == pytest.approx((.4 ** 2 + .8 ** 2) / 2)
    assert summary["causal_hit_rate"] == .5
    assert summary["log_loss"] == pytest.approx((-math.log(.6) - math.log(.2)) / 2)
    assert summary["probability_bins"][6]["observed_rate"] == 1
    assert summary["probability_bins"][8]["observed_rate"] == 0


def test_correlated_markets_have_one_unique_event(db, monkeypatch):
    one, two = candidate(), candidate(market="TOTAL_OVER_2_5", selection="Über 2.5")
    record(db, [one, two])
    result(db, monkeypatch, one)
    result(db, monkeypatch, two)
    summary = report(db)["summary"]
    assert summary["selections"] == 2
    assert summary["unique_events"] == summary["events_with_multiple_selections"] == 1


def test_sports_and_providers_with_same_numeric_id_do_not_overlap(db, monkeypatch):
    tennis = candidate()
    tennis.update(sport="Tennis", source="tennis_shadow", event_identity="event_opaque_native_hash",
        fixture_id=None, provider_event_id="1", fixture_source="ESPN", market_key="H2H",
        candidate_id="tennis:1:A", selection="Alice", competitor_a="Alice", competitor_b="Bob", selected_competitor="Alice")
    record(db, [candidate(), tennis])
    result(db, monkeypatch)
    result(db, monkeypatch, tennis)
    summary = report(db)["summary"]
    assert summary["wins"] == summary["unique_events"] == 2


def test_same_native_tennis_id_successor_does_not_inherit_previous_opponent_result(db, monkeypatch):
    first = candidate()
    first.update(sport="Tennis", source="tennis_shadow", event_identity="event_old_pair",
        fixture_id=None, provider_event_id="1", fixture_source="ESPN", market_key="H2H",
        candidate_id="tennis:1:A", selection="Alice", competitor_a="Alice", competitor_b="Bob", selected_competitor="Alice")
    record(db, [first])
    later = NOW + timedelta(minutes=10)
    monkeypatch.setattr(evidence, "_now", lambda: later)
    second = {**first, "event_identity": "event_successor_pair", "competitor_b": "Charlie"}
    record(db, [second], decision=later)
    result(db, monkeypatch, first, "WIN")
    result(db, monkeypatch, second, "LOSS")
    data = report(db)
    assert data["summary"]["wins"] == data["summary"]["losses"] == data["summary"]["scored"] == 0
    assert data["summary"]["unresolved"] == 1
    assert data["clock_exclusions"] == {"native_identity_conflict": 1}
    assert any("participant roles" in e["reason"] for e in data["integrity_errors"])


def test_same_event_key_with_changed_frozen_roles_is_an_explicit_gap(db, monkeypatch):
    first = {**candidate(), "home_team": "Alpha", "away_team": "Beta"}
    record(db, [first])
    later = NOW + timedelta(minutes=10)
    monkeypatch.setattr(evidence, "_now", lambda: later)
    second = {**first, "away_team": "Gamma"}
    record(db, [second], decision=later)
    result(db, monkeypatch, first)
    data = report(db)
    assert data["summary"]["unresolved"] == 1
    assert data["summary"]["scored"] == 0
    assert data["clock_exclusions"] == {"native_identity_conflict": 1}


def test_schedule_only_revision_with_same_roles_retains_first_causal_decision(db, monkeypatch):
    first = {**candidate(), "home_team": "Alpha", "away_team": "Beta"}
    record(db, [first])
    later = NOW + timedelta(minutes=10)
    monkeypatch.setattr(evidence, "_now", lambda: later)
    moved = {**first, "scheduled_start": (START + timedelta(hours=2)).isoformat()}
    record(db, [moved], decision=later)
    result(db, monkeypatch, first, actual_start=START + timedelta(hours=2), observed=START + timedelta(hours=4))
    data = report(db)
    assert data["summary"]["wins"] == data["summary"]["scored"] == 1
    assert data["integrity_error_count"] == 0
    assert data["selections"][0]["decision_at"] == NOW.isoformat()


def test_real_price_above_floor_ignores_old_value_gate(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(row, 1.3)
    record(db, [row])
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT sum(executable) FROM forecast_quotes").fetchone()[0] == 0
    result(db, monkeypatch)
    summary = report(db, unit_stake=10)["summary"]
    assert summary["hypothetical_resolved_quote_samples"] == 1
    assert summary["hypothetical_net_units"] == pytest.approx(.3)
    assert summary["hypothetical_net_amount"] == pytest.approx(3)


def test_known_below_floor_price_is_not_used_for_returns(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(row, 1.02)
    record(db, [row])
    result(db, monkeypatch)
    summary = report(db)["summary"]
    assert summary["quote_coverage"] == {"below_floor": 1}
    assert summary["hypothetical_resolved_quote_samples"] == 0


def test_stale_quote_coverage_does_not_claim_executable_profit(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(row, 3, NOW - timedelta(hours=3))
    record(db, [row])
    result(db, monkeypatch)
    data = report(db)
    assert data["summary"]["quote_coverage"] == {"stale": 1}
    assert data["summary"]["hypothetical_resolved_quote_samples"] == 0
    assert data["selections"][0]["entry_odds"] == 3


def test_bookmaker_ties_use_stable_identity_not_best_odds(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(row, prices={1: 2, 2: 3, 3: 4})
    record(db, [row])
    result(db, monkeypatch)
    data = report(db)
    assert data["selections"][0]["entry_odds"] == 2
    assert data["summary"]["hypothetical_net_units"] == 1


def test_void_is_neither_loss_nor_scored_or_hypothetical_profit(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(row)
    record(db, [row])
    result(db, monkeypatch, row, "VOID")
    summary = report(db)["summary"]
    assert summary["voids"] == summary["hypothetical_void_quote_samples"] == 1
    assert summary["wins"] == summary["losses"] == summary["scored"] == 0
    assert summary["hypothetical_resolved_quote_samples"] == 0


def test_conflicting_terminal_outcomes_are_unresolved_and_integrity_error(db, monkeypatch):
    record(db, [candidate()])
    result(db, monkeypatch)
    insert_result_copy(db, outcome="LOSS")
    data = report(db)
    assert data["summary"]["unresolved"] == 1
    assert data["summary"]["wins"] == data["summary"]["losses"] == 0
    assert any("conflicting" in e["reason"] for e in data["integrity_errors"])


def test_result_from_another_native_provider_is_not_counted(db, monkeypatch):
    record(db, [candidate()])
    result(db, monkeypatch)
    with sqlite3.connect(db) as conn:
        proof = json.loads(conn.execute("SELECT payload_json FROM forecast_results").fetchone()[0])["provenance"]
    insert_result_copy(db, provenance={**proof, "provider_event_id": "999"})
    data = report(db)
    assert data["summary"]["unresolved"] == 1
    assert any("another provider" in e["reason"] for e in data["integrity_errors"])


def test_payload_column_mutation_is_detected(db):
    record(db, [candidate()])
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER forecast_rows_no_update")
        conn.execute("UPDATE forecast_rows SET selection='Nein'")
    data = report(db)
    assert data["summary"]["selections"] == 0
    assert data["integrity_error_count"] == 1


def test_payload_hash_mutation_is_detected(db):
    record(db, [candidate()])
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER forecast_rows_no_update")
        value = json.loads(conn.execute("SELECT payload_json FROM forecast_rows").fetchone()[0])
        value["probability"] = .99
        conn.execute("UPDATE forecast_rows SET payload_json=?", (performance._json(value),))
    data = report(db)
    assert data["summary"]["selections"] == 0
    assert "hash mismatch" in data["integrity_errors"][0]["reason"]


def test_quote_after_decision_is_rejected_even_with_valid_hash(db, monkeypatch):
    row = candidate()
    row["reference_quote"] = quote(row)
    record(db, [row])
    result(db, monkeypatch)
    with sqlite3.connect(db) as conn:
        raw = json.loads(conn.execute("SELECT payload_json FROM forecast_quotes LIMIT 1").fetchone()[0])
        raw["observed_at"] = raw["fetched_at"] = (NOW + timedelta(minutes=1)).isoformat()
        digest = performance._hash(raw)
        conn.execute("INSERT INTO forecast_quotes VALUES(?,?,?,?,?,?,?,?,?)", (digest, raw["forecast_id"],
            raw["kind"], raw["bookmaker_id"], raw["observed_at"], raw["fetched_at"], raw["odds"], int(raw["executable"]), performance._json(raw)))
    data = report(db)
    assert data["summary"]["quote_coverage"] == {"invalid": 1}
    assert data["summary"]["hypothetical_resolved_quote_samples"] == 0


def test_verified_moved_earlier_kickoff_excludes_post_start_decision(db, monkeypatch):
    record(db, [candidate()])
    result(db, monkeypatch, actual_start=NOW - timedelta(minutes=1))
    data = report(db)
    assert data["summary"]["scored"] == 0
    assert data["clock_exclusions"] == {"post_actual_start": 1}


def test_verified_actual_kickoff_moves_event_to_correct_calendar_day(db, monkeypatch):
    row = candidate(start=datetime(2030, 1, 2, 1, tzinfo=timezone.utc))
    record(db, [row])
    result(db, monkeypatch, row, actual_start=START, observed=START + timedelta(hours=2))
    data = report(db)
    assert data["summary"]["wins"] == 1
    assert data["selections"][0]["day"] == "2030-01-01"


def test_future_result_not_available_as_of_is_not_counted(db, monkeypatch):
    record(db, [candidate()])
    result(db, monkeypatch, observed=AS_OF + timedelta(hours=1))
    assert report(db)["summary"]["unresolved"] == 1
    assert report(db)["summary"]["wins"] == 0


def test_cli_prints_json_and_does_not_create_missing_database(tmp_path, capsys):
    path = tmp_path / "missing.db"
    assert main(["--db", str(path), "--from-day", "2030-01-01", "--through-day", "2030-01-01", "--as-of", AS_OF.isoformat()]) == 0
    assert json.loads(capsys.readouterr().out)["database_present"] is False
    assert not path.exists()
