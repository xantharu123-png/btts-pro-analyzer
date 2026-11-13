"""Trap filter: pre-registered forward measurement of 09.11.2026 (docs/audits/2026-11-09-fallenfilter-vorab.md)."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from scripts import trap_filter_measurement as tfm

T0 = datetime(2026, 11, 10, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 28, tzinfo=timezone.utc)


def _payload(event, probability, forecast, market="OVER_2_5", selection="Over 2.5"):
    return {"event_key": f"football:{event}", "market_key": market, "selection": selection,
            "probability": probability, "forecast_id": forecast, "sport": "football"}


def _key(event, market="OVER_2_5", selection="Over 2.5"):
    return f"football:{event}", market, selection


def test_first_entry_quote_wins_and_closing_is_ignored():
    rows = [("f1", "entry", 2.10, "api-football:11", "2026-11-10T10:00:00+00:00"),
            ("f1", "entry", 1.80, "api-football:11", "2026-11-10T08:00:00+00:00"),
            ("f1", "closing", 1.50, "api-football:11", "2026-11-10T07:00:00+00:00"),
            ("f2", "entry", 1.00, "api-football:11", "2026-11-10T08:00:00+00:00")]
    quotes = tfm.first_entry_quotes(rows)
    assert quotes["f1"][0] == 1.80 and "f2" not in quotes


def test_selection_quote_is_the_earliest_over_all_forecast_rows_of_the_selection():
    forecast_quotes = {"f2": (1.90, "b", "2026-11-10T08:00:00+00:00"), "f3": (1.70, "b", "2026-11-10T06:00:00+00:00"),
                       "f5": (2.40, "b", "2026-11-10T06:00:00+00:00"), "f4": (2.20, "b", "2026-11-10T06:00:00+00:00"),
                       "f9": (3.00, "b", "2026-11-10T05:00:00+00:00")}
    rows = [("f1", *_key(1)), ("f2", *_key(1)), ("f3", *_key(1)), ("f5", *_key(2)), ("f4", *_key(2)),
            ("f6", *_key(3)), ("f9", *_key(1, selection="Under 2.5"))]
    for order in (rows, rows[::-1]):
        quotes = tfm.selection_entry_quotes(forecast_quotes, order)
        assert {key: quote[0] for key, quote in quotes.items()} == {
            _key(1): 1.70, _key(2): 2.20, _key(1, selection="Under 2.5"): 3.00}


def test_row_published_the_day_before_without_forecast_id_is_classified_by_its_selection():
    first = tfm.first_publications([
        ("2026-11-12T05:00:00+00:00", "wettfinder_automatic", _payload(1, 0.60, None)),
        ("2026-11-13T05:00:00+00:00", "wettfinder_default_inventory", _payload(1, 0.52, "f1")),
        ("2026-11-13T05:00:00+00:00", "wettfinder_default_inventory", _payload(2, 0.60, "f2")),
        ("2026-11-13T05:00:00+00:00", "wettfinder_default_inventory", _payload(3, 0.60, "f3"))])
    forecast_quotes = {"f1": (2.0, "b", "2026-11-13T04:00:00+00:00"), "f2": (1.5, "b", "2026-11-13T04:00:00+00:00")}
    quotes = tfm.selection_entry_quotes(forecast_quotes, [("f1", *_key(1)), ("f2", *_key(2)), ("f3", *_key(3))])
    results = {_key(1): "LOSS", _key(2): "WIN", _key(3): "WIN"}
    records = sorted(tfm.tip_records(first, quotes, results, T0, T1, forecast_quotes), key=lambda r: r["published"])
    assert [(r["p"], r["trap"], r["quote_via"]) for r in records] == [
        (0.60, True, "selection"), (0.60, False, "forecast_id"), (0.60, None, None)]


def test_first_publication_counts_once_and_window_uses_the_first_one():
    early = ("2026-11-09T20:00:00+00:00", "app", _payload(1, 0.6, "f1"))
    again = ("2026-11-10T09:00:00+00:00", "app", _payload(1, 0.6, "f1"))
    new = ("2026-11-11T09:00:00+00:00", "15k", _payload(2, 0.6, "f2"))
    first = tfm.first_publications([new, again, early])
    results = {("football:1", "OVER_2_5", "Over 2.5"): "WIN", ("football:2", "OVER_2_5", "Over 2.5"): "LOSS"}
    quotes = {_key(1): (2.0, "b", "x"), _key(2): (2.0, "b", "x")}
    records = tfm.tip_records(first, quotes, results, T0, T1)
    assert [(r["surface"], r["win"]) for r in records] == [("15k", False)]


def test_trap_boundary_and_missing_quote():
    first = {("e", "m", str(i)): (T0 + timedelta(hours=1), "app",
                                  {"probability": p, "forecast_id": f"f{i}", "sport": "football"})
             for i, p in enumerate((0.55, 0.549, 0.70))}
    quotes = {("e", "m", "0"): (2.0, "b", "x"), ("e", "m", "1"): (2.0, "b", "x")}
    results = {key: "WIN" for key in first}
    records = sorted(tfm.tip_records(first, quotes, results, T0, T1), key=lambda r: r["p"])
    assert [r["trap"] for r in records] == [False, True, None]


def test_void_and_open_results_are_left_out():
    first = {("e", "m", s): (T0 + timedelta(hours=1), "app", {"probability": 0.6, "forecast_id": "f"})
             for s in ("a", "b", "c")}
    results = tfm.latest_results([("e", "m", "a", "win", "2026-11-11T00:00:00+00:00"),
                                  ("e", "m", "b", "VOID", "2026-11-11T00:00:00+00:00")])
    records = tfm.tip_records(first, {key: (1.5, "b", "x") for key in first}, results, T0, T1)
    assert len(records) == 1 and records[0]["win"]


def _rows(n, p, hits, trap):
    return [{"p": p, "win": i < hits, "trap": trap, "odds": 2.0} for i in range(n)]


def test_verdict_needs_enough_traps_and_both_conditions():
    rest = _rows(600, 0.62, 375, False)
    assert tfm.verdict(_rows(149, 0.61, 70, True) + rest)["status"] == "not_enough_data"
    passed = tfm.verdict(_rows(200, 0.61, 94, True) + rest)
    assert passed["status"] == "passed" and all(c["met"] for c in passed["conditions"])
    honest = tfm.verdict(_rows(200, 0.61, 122, True) + rest)
    assert honest["status"] == "failed" and not honest["conditions"][0]["met"]
    weak_rest = tfm.verdict(_rows(200, 0.61, 94, True) + _rows(600, 0.62, 280, False))
    assert weak_rest["status"] == "failed" and weak_rest["conditions"][0]["met"]
    assert not weak_rest["conditions"][1]["met"]


def test_load_reads_both_databases_read_only(tmp_path):
    tips, evidence = tmp_path / "consumer_tips.db", tmp_path / "forecast_evidence.db"
    with sqlite3.connect(tips) as conn:
        conn.execute("create table consumer_tip_publications (publication_id text, surface text, "
                     "first_observed_at text)")
        conn.execute("create table consumer_tips (publication_id text, payload_json text)")
        conn.execute("insert into consumer_tip_publications values ('p1', 'app', '2026-11-10T09:00:00+00:00')")
        conn.execute("insert into consumer_tips values ('p1', ?)", (json.dumps(_payload(7, 0.66, "f7")),))
        conn.execute("insert into consumer_tip_publications values ('p2', 'wettfinder_automatic', "
                     "'2026-11-10T10:00:00+00:00')")
        conn.execute("insert into consumer_tips values ('p2', ?)", (json.dumps(_payload(8, 0.50, None)),))
    with sqlite3.connect(evidence) as conn:
        conn.execute("create table forecast_quotes (forecast_id text, kind text, odds real, bookmaker_id text, "
                     "observed_at text)")
        conn.execute("create table forecast_results (event_key text, market_key text, selection text, "
                     "outcome text, observed_at text)")
        conn.execute("create table forecast_rows (forecast_id text, event_key text, market_key text, "
                     "selection text)")
        conn.executemany("insert into forecast_rows values (?, ?, 'OVER_2_5', 'Over 2.5')",
                         [("f7", "football:7"), ("f8a", "football:8"), ("f8b", "football:8")])
        conn.execute("insert into forecast_quotes values ('f8b', 'entry', 2.50, 'api-football:11', "
                     "'2026-11-11T08:00:00+00:00')")
        conn.execute("insert into forecast_results values ('football:8', 'OVER_2_5', 'Over 2.5', 'WIN', "
                     "'2026-11-12T00:00:00+00:00')")
        conn.execute("insert into forecast_quotes values ('f7', 'entry', 1.95, 'api-football:11', "
                     "'2026-11-10T08:00:00+00:00')")
        conn.execute("insert into forecast_results values ('football:7', 'OVER_2_5', 'Over 2.5', 'LOSS', "
                     "'2026-11-11T00:00:00+00:00')")
    first, quotes, results, forecast_quotes = tfm.load(tips, evidence)
    records = tfm.tip_records(first, quotes, results, T0, T1, forecast_quotes)
    assert records == [
        {"sport": "football", "surface": "app", "published": T0 + timedelta(hours=9), "p": 0.66, "odds": 1.95,
         "trap": True, "quote_via": "forecast_id", "win": False},
        {"sport": "football", "surface": "wettfinder_automatic", "published": T0 + timedelta(hours=10), "p": 0.50,
         "odds": 2.50, "trap": True, "quote_via": "selection", "win": True}]
