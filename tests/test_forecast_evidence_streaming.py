"""Real SQLite regression fixtures for the history report's streaming contract."""

from datetime import datetime, timezone
import json
import sqlite3
import tracemalloc

import pytest

import forecast_evidence as evidence


AS_OF = "2030-01-01T14:00:00+00:00"
DECISION = "2030-01-01T10:00:00+00:00"
START = "2030-01-01T12:00:00+00:00"


def _database(path):
    connection = sqlite3.connect(path)
    connection.executescript(evidence._SCHEMA)
    return connection


def _forecast(connection, forecast_id, event, probability=.6, *, decision=DECISION,
              causal=True, recorded=None, sport="football", market="BTTS_YES",
              selection="Ja", model="model-v1", policy="policy-v1", padding=""):
    payload = json.dumps({"probability": probability,
                          "causal_provenance_complete": causal,
                          "recorded_at": recorded or decision,
                          "context": {"unused_history": padding}})
    connection.execute("INSERT INTO forecast_rows VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (forecast_id, "run", event, sport, market, selection,
                        model, policy, START, decision, payload))


def _result(connection, result_id, event, outcome, *, observed="2030-01-01T13:00:00+00:00",
            actual_start=None, market="BTTS_YES", selection="Ja", padding=""):
    proof = {} if actual_start is None else {"actual_starts_at": actual_start}
    connection.execute("INSERT INTO forecast_results VALUES(?,?,?,?,?,?,?)",
                       (result_id, event, market, selection, outcome, observed,
                        json.dumps({"provenance": proof, "unused_history": padding})))


def _quote(connection, quote_id, forecast_id, odds=2.0, *, kind="entry", book="1",
           observed=DECISION, fetched=None, executable=True, padding=""):
    connection.execute("INSERT INTO forecast_quotes VALUES(?,?,?,?,?,?,?,?,?)",
                       (quote_id, forecast_id, kind, book, observed, fetched or observed,
                        odds, int(executable), json.dumps({"unused_history": padding})))


def _empty_bins():
    # Literal boundaries deliberately independent of production bin generation.
    return [dict(lower=low, upper=high, n=0, mean_probability=None, observed_rate=None)
            for low, high in ((0.0, .1), (.1, .2), (.2, .3), (.3, .4), (.4, .5),
                              (.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.0))]


def _summary(*, sport="football", market="BTTS_YES", model="model-v1", policy="policy-v1",
             revisions=1, events=1, causal=1, unknown=0, wins=0, losses=0,
             voids=0, unresolved=0, scored=0, entry=0, executable=0,
             brier=None, log_loss=None, return_n=0, roi=None, clv_n=0, clv=None,
             selections=1, first_causal=1, bins=None):
    return dict(sport=sport, market=market, model_version=model, policy_version=policy,
                decision_revisions=revisions, unique_events=events, causal_forecasts=causal,
                unknown_input_clocks=unknown, wins=wins, losses=losses, voids=voids,
                unresolved=unresolved, scored=scored, entry_quote_coverage=entry,
                executable_entry_coverage=executable, brier_score=brier, log_loss=log_loss,
                hypothetical_executable_samples=return_n, hypothetical_unit_roi=roi,
                same_book_raw_clv_samples=clv_n, same_book_raw_clv=clv,
                calibration_bins=bins if bins is not None else _empty_bins(),
                unique_event_selections=selections, first_causal_observations=first_causal,
                quote_coverage_unit="decision revisions")


def test_literal_report_preserves_causal_firsts_prices_cutoffs_and_group_order(tmp_path):
    # Catches latest-revision dedup, insertion-order dedup, policy/model merging,
    # planned-kickoff scoring and choosing a later executable revision's odds.
    path = tmp_path / "literal-history.db"
    with _database(path) as connection:
        _forecast(connection, "a3", "a", .95, decision="2030-01-01T10:30:00+00:00")
        _forecast(connection, "a2", "a", .9, decision="2030-01-01T10:20:00+00:00")
        _forecast(connection, "a1", "a", .6, decision="2030-01-01T10:10:00+00:00")
        _forecast(connection, "a0", "a", .1, causal=False)
        _forecast(connection, "b1", "b", .1)  # Same clock, inserted before b0.
        _forecast(connection, "b0", "b", .8)
        _forecast(connection, "c", "c", .5)
        _forecast(connection, "d1", "d", .7, decision="2030-01-01T10:30:00+00:00")
        _forecast(connection, "d0", "d", .4)
        _forecast(connection, "e", "e", .9, decision="2030-01-01T10:15:00+00:00")
        _forecast(connection, "g", "g", .9)
        _forecast(connection, "a-model2", "a", .2, model="model-v2")
        _forecast(connection, "a-policy2", "a", .9, policy="policy-v2")
        _forecast(connection, "a-other-market", "a", .5, market="OU", selection="Over")
        _forecast(connection, "tennis", "t", .5, sport="tennis")
        _forecast(connection, "future", "future", .99, decision="2030-01-01T15:00:00+00:00")
        for event, outcome in (("a", "WIN"), ("b", "LOSS"), ("c", "VOID")):
            _result(connection, event, event, outcome)
        _result(connection, "e", "e", "LOSS", actual_start="2030-01-01T10:10:00+00:00")
        _result(connection, "g", "g", "WIN", observed=DECISION)
        _result(connection, "a-OU", "a", "LOSS", market="OU", selection="Over")
        _result(connection, "future-t", "t", "WIN", observed="2030-01-01T14:00:00.000001+00:00")
        _result(connection, "future-d", "d", "WIN", observed="2030-01-01T15:00:00+00:00")
        _quote(connection, "a0-entry", "a0", 2.5)
        _quote(connection, "a1-reference", "a1", executable=False)
        _quote(connection, "a2-a", "a2", 2.0)
        _quote(connection, "a2-z", "a2", 3.0)  # Equal observation, greatest ID wins.
        _quote(connection, "a3-entry", "a3", 5.0)
        _quote(connection, "b0-entry", "b0")
        _quote(connection, "b1-entry", "b1", 9.0)
        _quote(connection, "g-entry", "g")  # Result at decision gives no ROI.
        _quote(connection, "e-entry", "e", observed="2030-01-01T10:20:00+00:00")
        _quote(connection, "future-d-entry", "d0", observed="2030-01-01T14:00:00.000001+00:00")
        _quote(connection, "a2-close-a", "a2", 2.5, kind="closing", observed=START)
        _quote(connection, "a2-close-z", "a2", 2.0, kind="closing", observed=START)
        _quote(connection, "a2-other-book", "a2", 1.2, kind="closing", book="2", observed=START)
        _quote(connection, "a2-after-start", "a2", 1.0, kind="closing",
               observed="2030-01-01T12:00:00.000001+00:00")
        _quote(connection, "b0-other-book", "b0", 1.0, kind="closing", book="2", observed=START)

    bins = _empty_bins()
    bins[6].update(n=1, mean_probability=.6, observed_rate=1.0)
    bins[8].update(n=1, mean_probability=.8, observed_rate=0.0)
    policy_bins = _empty_bins()
    policy_bins[9].update(n=1, mean_probability=.9, observed_rate=1.0)
    model_bins = _empty_bins()
    model_bins[2].update(n=1, mean_probability=.2, observed_rate=1.0)
    market_bins = _empty_bins()
    market_bins[5].update(n=1, mean_probability=.5, observed_rate=0.0)
    expected_groups = [
        _summary(revisions=11, events=6, causal=9, unknown=2, wins=2, losses=2,
                 voids=1, unresolved=1, scored=2, entry=7, executable=6,
                 brier=pytest.approx(.4, abs=1e-12),
                 log_loss=pytest.approx(1.0601317681000455, abs=1e-12),
                 return_n=2, roi=.5, clv_n=1, clv=.5, selections=6, first_causal=5, bins=bins),
        _summary(policy="policy-v2", wins=1, scored=1,
                 brier=pytest.approx(.01, abs=1e-12),
                 log_loss=pytest.approx(.10536051565782628, abs=1e-12), bins=policy_bins),
        _summary(model="model-v2", wins=1, scored=1,
                 brier=pytest.approx(.64, abs=1e-12),
                 log_loss=pytest.approx(1.6094379124341003, abs=1e-12), bins=model_bins),
        _summary(market="OU", losses=1, scored=1, brier=.25,
                 log_loss=pytest.approx(.6931471805599453, abs=1e-12), bins=market_bins),
        _summary(sport="tennis", unresolved=1),
    ]
    report = evidence.build_quality_report(path, as_of=AS_OF)
    assert report == dict(
        as_of=AS_OF, database_present=True, groups=expected_groups,
        scoring_policy="First causal decision per event/selection/model/policy; returns use first executable causal decision independently.",
        limitations=[
            "Different selections from the same event remain correlated; unique event counts are shown.",
            "Observed quote returns are hypothetical equal-unit returns, not actual wagers or profit proof.",
            "CLV is the raw same-book odds ratio; no no-vig market probability is inferred.",
            "Missing input clocks are excluded from strict prequential scoring.",
            "Verified actual kickoff overrides the planned start for causal scoring and prices; frozen forecasts stay unchanged.",
        ],
        sport_coverage=[dict(sport="football", forecast_revisions=14, unique_events=6,
                            events_with_any_result=5, events_without_results=1),
                        dict(sport="tennis", forecast_revisions=1, unique_events=1,
                             events_with_any_result=0, events_without_results=1)],
    )


def test_forecast_payload_memory_does_not_grow_with_repeated_revisions(tmp_path):
    # Catches eager forecasts/group lists or any replacement payload buffer.
    path = tmp_path / "large-forecast-history.db"
    padding = "context-not-needed-for-scoring-" + "x" * (64 * 1024)
    with _database(path) as connection:
        for index in range(2048):
            _forecast(connection, f"revision-{index:06}", "same-event", .6, padding=padding)
        _result(connection, "terminal", "same-event", "WIN")
    del padding
    tracemalloc.start()
    try:
        report = evidence.build_quality_report(path, as_of=AS_OF)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    group = report["groups"][0]
    assert group["decision_revisions"] == 2048
    assert group["scored"] == group["wins"] == group["unique_events"] == 1
    assert group["brier_score"] == pytest.approx(.16, abs=1e-12)
    print(f"forecast-history traced peak: {peak} bytes")
    assert peak < 8 * 1024 * 1024, f"Forecast payloads retained: {peak} bytes"


def test_quote_cache_does_not_retain_unused_provider_payloads(tmp_path):
    # Catches SELECT * / cached quote payloads even when forecast streaming works.
    path = tmp_path / "large-quote-history.db"
    padding = "x" * (512 * 1024)
    with _database(path) as connection:
        _forecast(connection, "one", "one", .6)
        _result(connection, "terminal", "one", "LOSS")
        for index in range(32):
            _quote(connection, f"quote-{index:04}", "one", 2.0, padding=padding)
    del padding
    tracemalloc.start()
    try:
        report = evidence.build_quality_report(path, as_of=AS_OF)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    group = report["groups"][0]
    assert group["entry_quote_coverage"] == group["executable_entry_coverage"] == 1
    assert group["hypothetical_executable_samples"] == 1
    assert group["hypothetical_unit_roi"] == -1.0
    assert group["brier_score"] == pytest.approx(.36, abs=1e-12)
    print(f"quote-history traced peak: {peak} bytes")
    assert peak < 4 * 1024 * 1024, f"Unused quote payloads retained: {peak} bytes"


def test_report_observes_one_read_only_snapshot_during_concurrent_append(tmp_path, monkeypatch):
    # Catches splitting results/quotes/forecasts across transactions or writing
    # migrations during a report. A real WAL writer commits after snapshot starts.
    path = tmp_path / "snapshot-history.db"
    with _database(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        _forecast(connection, "first", "event", .6)
    connect = sqlite3.connect
    appended = False

    def report_connect(*args, **kwargs):
        nonlocal appended
        connection = connect(*args, **kwargs)

        def append_after_read_starts(sql):
            nonlocal appended
            if sql.startswith("SELECT") and "forecast_rows" in sql and not appended:
                appended = True
                with connect(path) as writer:
                    _forecast(writer, "second", "other-event", .9)
                    _result(writer, "terminal", "event", "WIN")
                    _quote(writer, "entry", "first", 3.0)

        connection.set_trace_callback(append_after_read_starts)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(evidence.sqlite3, "connect", report_connect)
        report = evidence.build_quality_report(path, as_of=AS_OF)
    assert appended
    assert report["groups"] == [_summary(unresolved=1)]
    refreshed = evidence.build_quality_report(path, as_of=AS_OF)["groups"][0]
    assert refreshed["decision_revisions"] == 2
    assert refreshed["wins"] == refreshed["scored"] == 1
    assert refreshed["hypothetical_unit_roi"] == 2.0


def test_empty_existing_database_has_no_groups_or_coverage_and_is_not_changed(tmp_path):
    # Catches manufactured empty cohorts and report-time schema/index writes.
    path = tmp_path / "empty-history.db"
    _database(path).close()
    before = path.read_bytes()
    report = evidence.build_quality_report(path, as_of=datetime(2030, 1, 1, 14, tzinfo=timezone.utc))
    assert report["database_present"] is True
    assert report["groups"] == report["sport_coverage"] == []
    assert path.read_bytes() == before
