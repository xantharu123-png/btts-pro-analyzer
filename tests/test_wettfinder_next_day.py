"""Folgetag (owner decision 02.11.2026): a match day with fewer football games lists the next day.

The next day's games are model selections only. They never become a tip, a 15K row, a
Daily3 choice or an archived publication, and a failure there leaves today unchanged.
"""
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

import wettfinder_automation as automation
from config_loader import AppConfig
from ev_signal_sources import (
    NEXT_DAY_MIN_GAMES,
    _load_automated_wettfinder_document,
    automated_next_day,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
    listed_next_day_signal,
)
from tests.test_wettfinder_automation import _football_snapshot

UTC = timezone.utc
NOW = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
TODAY, TOMORROW = date(2030, 1, 1), date(2030, 1, 2)


def _today_snapshot(**changes) -> dict:
    # Below 65 % an unpriced tip stays visible under the 1.20 display floor
    # (as in test_run_without_any_bookmaker_quote_keeps_its_unpriced_tips).
    snapshot = _football_snapshot(NOW)
    original = snapshot["shortlist"][0]
    candidate = replace(original, probability=0.45, conservative_probability=0.38,
                        probability_haircut_pp=7.0, model_price=1.0 / 0.38, **changes)
    candidate.context = dict(original.context)
    snapshot.update(shortlist=[], wettfinder_candidates=[candidate], discovery_candidates=[candidate])
    return snapshot


def _next_day_snapshot() -> dict:
    snapshot = _today_snapshot(candidate_id="fixture-2-btts", fixture_id=2,
                               kickoff="2030-01-02T15:00:00+00:00")
    snapshot.update(context_fixture_statuses={"2": "verified"},
                    fixture_kickoffs=["2030-01-02T15:00:00+00:00"])
    return snapshot


def _refuse_context(*_args):
    raise AssertionError("no context refresh expected")


def _run(tmp_path, scanner, **kwargs):
    artifact = tmp_path / "wettfinder.json"
    document = automation.run_wettfinder(
        now=NOW, state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=scanner, football_context_refresher=_refuse_context,
        football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [], **kwargs,
    )
    return artifact, document


def _scanner(calls, *, fail_next_day=False):
    def scan(day):
        calls.append(day)
        if day == TOMORROW:
            if fail_next_day:
                raise RuntimeError("provider down for key=secret")
            return _next_day_snapshot()
        return _today_snapshot()
    return scan


def _fixture_ids(rows):
    return {row.get("fixture_id") for row in rows}


def test_threshold_is_thirty_games():
    assert NEXT_DAY_MIN_GAMES == automation.NEXT_DAY_MIN_GAMES == 30


def test_small_match_day_lists_next_day_games_as_model_selections_only(tmp_path):
    calls = []
    artifact, document = _run(tmp_path, _scanner(calls), football_next_day=True)

    assert calls == [TODAY, TOMORROW]
    assert document["next_day_search_date"] == "2030-01-02"
    assert document["football_next_day"]["search_date"] == "2030-01-02"
    assert _fixture_ids(document["model_candidates"]) == {1, 2}
    assert 2 not in _fixture_ids(document["candidates"])
    assert 2 not in _fixture_ids(document["challenge_release_candidates"])
    summary = document["sources"]["football"]["next_day"]
    assert summary["status"] == "listed" and summary["today_games"] == 1 and summary["games"] == 1
    assert document["run_status"] == "completed"

    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    next_day = [signal for signal in forecasts if listed_next_day_signal(signal, now=NOW)]
    assert [signal.key for signal in next_day] == [
        row["key"] for row in document["model_candidates"] if row["fixture_id"] == 2]
    assert all(not listed_next_day_signal(signal, now=NOW)
               for signal in automated_wettfinder_signals(artifact, now=NOW))


def test_full_match_day_does_not_scan_the_next_day(tmp_path, monkeypatch):
    monkeypatch.setattr(automation, "NEXT_DAY_MIN_GAMES", 1)
    calls = []
    _artifact, document = _run(tmp_path, _scanner(calls), football_next_day=True)

    assert calls == [TODAY]
    assert "next_day_search_date" not in document and "football_next_day" not in document
    assert document["sources"]["football"]["next_day"]["status"] == "not_needed"


def test_isolated_runs_keep_the_single_day_unless_asked(tmp_path):
    calls = []
    _artifact, document = _run(tmp_path, _scanner(calls))

    assert calls == [TODAY]
    assert "next_day_search_date" not in document


def test_next_day_failure_leaves_today_unchanged(tmp_path):
    reference_calls = []
    _reference_artifact, reference = _run(tmp_path / "a", _scanner(reference_calls))
    calls = []
    _artifact, document = _run(tmp_path / "b", _scanner(calls, fail_next_day=True), football_next_day=True)

    assert calls == [TODAY, TOMORROW]
    assert document["run_status"] == "completed" and document["football"]["status"] == "completed"
    assert document["model_candidates"] == reference["model_candidates"]
    assert document["candidates"] == reference["candidates"]
    summary = document["sources"]["football"]["next_day"]
    assert summary == {"search_date": "2030-01-02", "status": "failed", "failure_type": "RuntimeError",
                       "today_games": 1, "candidate_count": 0, "games": 0, "price_checked_count": 0,
                       "price_status_counts": summary["price_status_counts"],
                       "quote_operational_error_count": 0}
    assert "secret" not in json.dumps(document)


@pytest.fixture
def listed(tmp_path):
    artifact, _document = _run(tmp_path, _scanner([]), football_next_day=True)
    return artifact, json.loads(artifact.read_text(encoding="utf-8"))


def _rewrite(artifact, document):
    artifact.write_text(json.dumps(document), encoding="utf-8")
    return _load_automated_wettfinder_document(artifact, now=NOW)


def test_loader_rejects_next_day_rows_without_a_valid_marker(listed):
    artifact, document = listed
    assert _rewrite(artifact, document) is not None

    assert _rewrite(artifact, {**document, "next_day_search_date": "2030-01-03"}) is None
    unmarked = dict(document)
    unmarked.pop("next_day_search_date")
    assert _rewrite(artifact, unmarked) is None
    assert _rewrite(artifact, {**document, "football_next_day": {
        **document["football_next_day"], "search_date": "2030-01-01"}}) is None


def test_loader_never_accepts_a_next_day_tip_or_15k_row(listed):
    artifact, document = listed
    next_row = next(row for row in document["model_candidates"] if row["fixture_id"] == 2)
    tip = {**next_row, "status": "RECOMMENDED"}
    assert _rewrite(artifact, {**document, "candidates": [*document["candidates"], tip]}) is None
    assert _rewrite(artifact, {**document, "challenge_release_candidates": [tip]}) is None


def test_next_day_rows_need_their_own_verified_context(listed):
    artifact, document = listed
    state = dict(document["football_next_day"])
    state["context_fixture_statuses"] = {"2": "unchecked"}
    state["context_verified_fixtures"] = 0
    state["context_unchecked_fixtures"] = 1
    _rewrite(artifact, {**document, "football_next_day": state})

    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    assert forecasts and not any(listed_next_day_signal(signal, now=NOW) for signal in forecasts)


def test_marker_helper_requires_the_following_day():
    state = {"search_date": "2030-01-02"}
    assert automated_next_day({"next_day_search_date": "2030-01-02", "football_next_day": state}, TODAY) == TOMORROW
    assert automated_next_day({"next_day_search_date": "2030-01-02", "football_next_day": state}, TOMORROW) is None
    assert automated_next_day({"next_day_search_date": "2030-01-02"}, TODAY) is None


def test_quotes_run_also_prices_listed_next_day_rows(listed, monkeypatch):
    _artifact, document = listed
    seen = []

    def loader(rows):
        seen.extend(row["fixture_id"] for row in rows)
        return {}, []

    monkeypatch.setattr(automation, "_persist_quote_diagnostics", lambda *args, **kwargs: None)
    automation._refresh_price_document(document, quote_sport="football", config=AppConfig(api_football_key="x"),
                                       now=NOW + timedelta(minutes=5), quote_loader=loader)
    assert {1, 2} <= set(seen)


@pytest.mark.price_policy("floor")  # unpriced rows below 65 % stay in the default inventory
def test_tip_archive_skips_listed_next_day_games(listed, monkeypatch):
    import tip_publication

    artifact, _document = listed
    archived = {}

    def record(surface, signals, **_kwargs):
        archived[surface] = [signal.key for signal in signals]
        return {"status": "recorded"}

    monkeypatch.setattr(tip_publication, "record_signal_catalog", record)
    assert tip_publication.record_automatic_publication(artifact, as_of=NOW)["status"] == "completed"
    assert archived["wettfinder_default_inventory"] == ["wettfinder-football-fixture-1-btts"]
