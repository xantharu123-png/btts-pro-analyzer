from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3

import pytest

import consumer_tip_history as history
import forecast_evidence as evidence
from consumer_tip_performance import build_consumer_tip_performance_report
from market_consensus import parse_fixture_consensus


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = NOW+timedelta(hours=4)
AS_OF = NOW+timedelta(days=1)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_now", lambda: NOW)
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    return tmp_path/"consumer.db", tmp_path/"forecast.db"


def row(fixture=1, **changes):
    return dict(candidate_id=f"{fixture}:BTTS_YES", fixture_id=fixture,
                event_identity=f"football:{fixture}", sport="Fußball",
                source="football_challenge", market_key="BTTS_YES", selection="Ja",
                scheduled_start=START.isoformat(), probability=.6,
                model_version="m1", policy_version="p1",
                modeled_at=(NOW-timedelta(minutes=5)).isoformat(),
                input_cutoff_at=(NOW-timedelta(minutes=10)).isoformat(), **changes)


def quote(item, odds=2.0, clock=NOW):
    payload = {"response": [{"fixture": {"id": item["fixture_id"], "date": item["scheduled_start"]},
        "update": clock.isoformat(), "bookmakers": [
            {"id": index, "name": f"Book {index}", "bets": [
                {"name": "Both Teams Score", "values": [{"value": "Yes", "odd": str(odds)}]}]}
            for index in (1, 2, 3)]}]}
    return parse_fixture_consensus(payload, [item], fetched_at=clock)[item["candidate_id"]].to_dict()


def freeze(db, item):
    return evidence.record_forecast_run(dict(generated_at=NOW.isoformat(),
        selection_policy_version="p1", model_candidates=[item]), db, "m1")["forecast_ids"][0]


def publish(db, item, *, surface="wettfinder:top", clock=NOW):
    return history.record_tip_publication(db, surface=surface, rows=[item], as_of=clock)


def settle(db, monkeypatch, fixture=1, outcome="WIN", actual_start=None):
    monkeypatch.setattr(evidence, "_now", lambda: AS_OF)
    proof = dict(provider="api-football", provider_event_id=str(fixture), source_record_id=f"terminal:{fixture}",
                 payload_sha256="a"*64, settlement_rule="football-fulltime-v1")
    if actual_start:
        proof["actual_starts_at"] = actual_start.isoformat()
    return evidence.append_result(f"football:{fixture}", "BTTS_YES", "Ja", outcome,
        observed_at=START+timedelta(hours=2), provenance=proof, db_path=db)


def report(paths, **kwargs):
    return build_consumer_tip_performance_report(*paths, from_day="2030-01-01",
        through_day="2030-01-01", as_of=AS_OF, **kwargs)


def test_no_history_never_falls_back_to_internal_forecast_pool(paths):
    freeze(paths[1], row())
    result = report(paths)
    assert result["cohort"] == "archived_publications" and result["summary"]["selections"] == 0
    assert not paths[0].exists()


def test_empty_publication_is_honest_and_readonly(paths):
    history.record_tip_publication(paths[0], surface="daily3", rows=[], as_of=NOW)
    before = hashlib.sha256(paths[0].read_bytes()).hexdigest()
    result = report(paths)
    assert result["publication_count"] == 1 and result["summary"]["selections"] == 0
    assert hashlib.sha256(paths[0].read_bytes()).hexdigest() == before
    assert not paths[1].exists()


def test_roi_uses_actual_publication_price_not_original_forecast_entry(paths, monkeypatch):
    item = row()
    item["reference_quote"] = quote(item, odds=3)
    forecast_id = freeze(paths[1], item)
    captured = NOW+timedelta(minutes=30)
    monkeypatch.setattr(history, "_now", lambda: captured)
    item["reference_quote"] = quote(item, odds=1.5, clock=captured)
    item["forecast_id"] = forecast_id
    publish(paths[0], item, clock=captured)
    settle(paths[1], monkeypatch)
    result = report(paths, unit_stake=10)
    assert result["summary"]["wins"] == 1
    assert result["summary"]["hypothetical_net_amount"] == 5
    assert result["selections"][0]["entry_odds"] == 1.5
    assert result["publication_quote_source"] == "actual_publication_capture"


def test_first_capture_not_best_later_price_or_probability(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["reference_quote"] = quote(item, odds=1.5)
    publish(paths[0], item)
    later = NOW+timedelta(minutes=20)
    monkeypatch.setattr(history, "_now", lambda: later)
    item["reference_quote"] = quote(item, odds=5, clock=later)
    publish(paths[0], item, clock=later, surface="daily3")
    settle(paths[1], monkeypatch)
    data = report(paths)
    assert data["summary"]["hypothetical_net_units"] == .5
    assert data["archive_revisions_collapsed"] == 1
    only_daily3 = report(paths, surface="daily3")
    assert only_daily3["summary"]["hypothetical_net_units"] == 4


@pytest.mark.parametrize("kind", ["missing", "stale", "below_floor"])
def test_missing_stale_low_price_does_not_invent_profit_or_loss(paths, monkeypatch, kind):
    item = row()
    freeze(paths[1], item)
    if kind != "missing":
        item["reference_quote"] = quote(item, odds=1.1 if kind == "below_floor" else 2,
            clock=NOW-timedelta(hours=2) if kind == "stale" else NOW)
    publish(paths[0], item)
    settle(paths[1], monkeypatch)
    result = report(paths)
    assert result["summary"]["wins"] == 1
    assert result["summary"]["hypothetical_resolved_quote_samples"] == 0
    assert result["summary"]["hypothetical_roi"] is None
    assert result["selections"][0]["quote_status"] == kind


def test_forecast_hint_is_rebound_not_trusted_and_mismatch_is_gap(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["forecast_id"] = "b"*64
    publish(paths[0], item)
    settle(paths[1], monkeypatch)
    data = report(paths)
    assert data["summary"]["selections"] == 0
    assert data["linkage_gap_reasons"] == {"archived_forecast_binding_mismatch": 1}


def test_unknown_model_clocks_and_frozen_riskobet_snapshot_are_gaps(paths):
    item = row()
    freeze(paths[1], item)
    item["model_version"] = "another-model"
    item["snapshot_id"] = "a"*64
    publish(paths[0], item)
    data = report(paths)
    assert data["linkage_gap_reasons"] == {"unlinked_frozen_snapshot": 1}
    assert data["summary"]["selections"] == 0


@pytest.mark.parametrize("field", ["model_version", "policy_version", "modeled_at", "input_cutoff_at"])
def test_missing_original_model_identity_cannot_be_inferred_from_matching_probability(paths, field):
    item = row()
    freeze(paths[1], item)
    item[field] = None
    publish(paths[0], item)
    result = report(paths)
    assert result["summary"]["selections"] == 0
    assert result["linkage_gap_reasons"] == {"missing_exact_model_identity": 1}


@pytest.mark.parametrize("change", ["wrong_market", "wrong_selection", "wrong_fixture", "after_capture", "after_observation", "stale", "no_bookmaker"])
def test_publication_quote_is_revalidated_independently_of_archive_status(change):
    from consumer_tip_performance import _published_quote
    tip = dict(row(), starts_at=START.isoformat(), sport="football")
    tip["quote"] = dict(status="observed", odds=2.0, bookmaker_id="1",
        observed_at=NOW.isoformat(), fetched_at=NOW.isoformat(), source="API-Football Mehrbuchmacher",
        starts_at=START.isoformat(), market_key="BTTS_YES", bet_name="Both Teams Score", selection="Yes", fixture_id=1)
    field, value = {
        "wrong_market": ("market_key", "TOTAL_OVER_25"),
        "wrong_selection": ("selection", "No"),
        "wrong_fixture": ("fixture_id", 2),
        "after_capture": ("fetched_at", (NOW+timedelta(seconds=1)).isoformat()),
        "after_observation": ("observed_at", (NOW+timedelta(seconds=1)).isoformat()),
        "stale": ("observed_at", (NOW-timedelta(hours=1)).isoformat()),
        "no_bookmaker": ("bookmaker_id", ""),
    }[change]
    tip["quote"][field] = value
    status, odds = _published_quote(tip, NOW, START)
    assert status == ("stale" if change == "stale" else "invalid")
    assert odds is None


def test_actual_kickoff_before_capture_prevents_profit(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["reference_quote"] = quote(item)
    publish(paths[0], item)
    settle(paths[1], monkeypatch, actual_start=NOW-timedelta(minutes=1))
    data = report(paths)
    assert data["summary"]["selections"] == 0
    assert data["linkage_gap_reasons"] == {"publication_after_actual_start": 1}


def test_unresolved_results_and_voids_are_not_losses(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["reference_quote"] = quote(item)
    publish(paths[0], item)
    assert report(paths)["summary"]["unresolved"] == 1
    settle(paths[1], monkeypatch, outcome="VOID")
    summary = report(paths)["summary"]
    assert summary["voids"] == 1 and summary["losses"] == 0
    assert summary["hypothetical_resolved_quote_samples"] == 0


def test_complete_report_is_nonmutating_for_both_databases(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    publish(paths[0], item)
    settle(paths[1], monkeypatch)
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    monkeypatch.setattr(evidence, "_connect", lambda *_: pytest.fail("writer invoked"))
    report(paths)
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == before


def test_report_metadata_excludes_archives_of_unrelated_event_days(paths, monkeypatch):
    old = NOW-timedelta(days=3)
    monkeypatch.setattr(history, "_now", lambda: old)
    item = row()
    item.update(scheduled_start=(old+timedelta(hours=4)).isoformat(),
                modeled_at=(old-timedelta(minutes=5)).isoformat(),
                input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
    publish(paths[0], item, clock=old)
    data = report(paths)
    assert data["publication_count"] == data["unique_archived_selections"] == 0


def test_mixed_inventory_counts_only_target_event_day(paths):
    today, future = row(), row(2)
    future["scheduled_start"] = (START+timedelta(days=2)).isoformat()
    freeze(paths[1], today)
    freeze(paths[1], future)
    history.record_tip_publication(paths[0], surface="wettfinder:top", rows=[today, future], as_of=NOW)
    data = report(paths)
    assert data["unique_archived_selections"] == data["summary"]["selections"] == 1


def test_archived_counter_uses_actual_day_and_preserves_first_capture(paths, monkeypatch):
    old = NOW-timedelta(days=2)
    item = row()
    item.update(scheduled_start=(old+timedelta(hours=4)).isoformat(),
                modeled_at=(old-timedelta(minutes=5)).isoformat(),
                input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
    monkeypatch.setattr(history, "_now", lambda: old)
    monkeypatch.setattr(evidence, "_now", lambda: old)
    evidence.record_forecast_run(dict(generated_at=old.isoformat(),
        selection_policy_version="p1", model_candidates=[item]), paths[1], "m1")
    publish(paths[0], item, clock=old)
    monkeypatch.setattr(history, "_now", lambda: NOW)
    changed = dict(item, scheduled_start=START.isoformat())
    publish(paths[0], changed)
    settle(paths[1], monkeypatch, actual_start=START)
    data = report(paths)
    assert data["unique_archived_selections"] == data["summary"]["selections"] == 1
    assert data["selections"][0]["first_observed_at"] == old.isoformat()
