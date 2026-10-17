"""Persist both real tennis prices with one frozen model, without API calls."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

import forecast_evidence as evidence
import market_consensus as markets
from forecast_market_comparison import build_market_comparison
from test_market_consensus import _gea_zhang_quote_fixture

NOW = datetime(2030, 9, 30, 8, tzinfo=timezone.utc)


def fixture(now=NOW):
    row, event = _gea_zhang_quote_fixture(now)
    row.update(fixture_id=None, fixture_source="ESPN", provider_event_id="186197",
        event_identity="tennis:ESPN:186197", selection="Arthur Gea", probability=.7,
        conservative_probability=.6, minimum_odds=1.2, modeled_at=(NOW-timedelta(minutes=1)).isoformat(),
        input_cutoff_at=(NOW-timedelta(minutes=2)).isoformat())
    quote = markets.parse_h2h_event_consensus(event, [row], fetched_at=now)[row["candidate_id"]]
    row.update(reference_quote=quote.to_dict(), quote_provider_event_id=quote.provider_event_id)
    observations = markets._collect_tennis_event_prices(event, [row], now=now)
    return row, {"generated_at": NOW.isoformat(), "selection_policy_version": "native-test-v1",
        "model_candidates": [row], "tennis_price_observations": observations}


def settle(db, row, monkeypatch):
    observed = datetime.fromisoformat(row["scheduled_start"])+timedelta(hours=3)
    monkeypatch.setattr(evidence, "_now", lambda: observed)
    evidence.append_result(row["event_identity"], "H2H", "Arthur Gea", "WIN", observed_at=observed,
        provenance={"provider": "espn", "provider_event_id": "186197", "source_record_id": "186197:final",
            "payload_sha256": "a"*64, "settlement_rule": "tennis-match-winner-v1"}, db_path=db)
    return observed


def test_native_pair_is_persisted_but_no_opposing_forecast_or_manual_price_is_created(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    row, document = fixture()
    original = deepcopy(document)
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    saved = evidence.record_forecast_run(document, db, "tennis-model-test")
    assert saved["recorded"] == 1 and not saved["quotes_rejected"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM forecast_rows").fetchone()[0] == 1
        payload = json.loads(conn.execute("SELECT payload_json FROM forecast_quotes").fetchone()[0])
        assert payload["complete_market"]["outcomes"] == [
            {"selection": "Arthur Gea", "odds": 1.52}, {"selection": "Zhang Zhizhen", "odds": 2.7}]
        assert {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} == evidence._TABLES
    assert document == original
    observed = settle(db, row, monkeypatch)
    before = db.read_bytes()
    report = build_market_comparison(db, as_of=observed)
    assert db.read_bytes() == before
    assert report["coverage"]["binary_complement_report_selections"] == 1
    group = report["groups"][0]
    assert group["sport"] == "tennis" and group["unique_events"] == 1
    assert group["model_brier"] == pytest.approx(.3**2)
    assert group["market_brier"] == pytest.approx((1-2.7/(1.52+2.7))**2)


@pytest.mark.parametrize("damage", ["missing", "book", "clock", "fetch", "native_event", "participants"])
def test_counter_price_never_crosses_native_event_book_or_clock(tmp_path, monkeypatch, damage):
    db = tmp_path/"evidence.db"
    row, document = fixture()
    observations = document["tennis_price_observations"]
    other = next(item for item in observations if item["selected_competitor"] == "Zhang Zhizhen")
    if damage == "missing":
        observations.remove(other)
    elif damage in {"native_event", "participants"}:
        other["provider_event_id" if damage == "native_event" else "competitor_b"] = "Other"
    else:
        quote = markets.MarketConsensus.from_dict(other["reference_quote"])
        point = quote.points[0]
        if damage == "book":
            quote = replace(quote, points=(replace(point, bookmaker_id="elsewhere", bookmaker="Elsewhere"),))
        elif damage == "clock":
            changed = (NOW-timedelta(seconds=1)).isoformat()
            quote = replace(quote, quoted_at=changed, points=(replace(point, observed_at=changed),))
        else:
            quote = replace(quote, fetched_at=(NOW+timedelta(seconds=1)).isoformat())
        other["reference_quote"] = quote.to_dict()
    monkeypatch.setattr(evidence, "_now", lambda: NOW+timedelta(seconds=2))
    saved = evidence.record_forecast_run(document, db, "tennis-model-test")
    assert not saved["quotes_rejected"]
    with sqlite3.connect(db) as conn:
        payload = json.loads(conn.execute("SELECT payload_json FROM forecast_quotes").fetchone()[0])
        assert "complete_market" not in payload
    observed = settle(db, row, monkeypatch)
    assert build_market_comparison(db, as_of=observed)["groups"] == []


def test_quote_only_closing_refresh_preserves_native_pair_and_frozen_probability(tmp_path, monkeypatch):
    db = tmp_path/"evidence.db"
    row, document = fixture()
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    evidence.record_forecast_run(document, db, "tennis-model-test")
    close = datetime.fromisoformat(row["scheduled_start"])-timedelta(minutes=5)
    fresh_row, fresh = fixture(close)
    monkeypatch.setattr(evidence, "_now", lambda: close)
    original_forecasts = None
    with sqlite3.connect(db) as conn:
        original_forecasts = conn.execute("SELECT * FROM forecast_rows").fetchall()
    result = evidence.record_current_closing_quotes(fresh, db_path=db, model_version="tennis-model-test")
    assert result["recorded"] == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT * FROM forecast_rows").fetchall() == original_forecasts
        payload = json.loads(conn.execute("SELECT payload_json FROM forecast_quotes WHERE kind='closing'").fetchone()[0])
        assert len(payload["complete_market"]["outcomes"]) == 2
    observed = settle(db, row, monkeypatch)
    assert {group["kind"] for group in build_market_comparison(db, as_of=observed)["groups"]} == {"entry", "closing"}
