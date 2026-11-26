"""Compatibility of explicitly prior-backed analysis. The ticker no longer uses it."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

import pytest

from test_live_football_source import native, warm
from test_wettfinder_automation import _challenge_candidate
from wettfinder_automation import _football_candidate_record
from challenge_engine import CHALLENGE_PREDICTION_VERSION
from ev_signal_sources import AUTOMATED_WETTFINDER_VERSION


def analyze_with_published_prior(fixture, analyzer=None):
    from live_football_priors import stored_goal_priors
    from live_football_source import analyze_detail

    return analyze_detail(fixture, analyzer, prior_reader=stored_goal_priors)


def case(kickoff=None):
    fixture = native()
    if kickoff is None:
        kickoff = datetime.fromisoformat(fixture["fixture"]["date"])
    else:
        fixture["fixture"]["date"] = kickoff.isoformat()
        from season_utils import current_season_start_year_for_id
        fixture["league"]["season"] = current_season_start_year_for_id(39, when=kickoff)
    modeled = kickoff - timedelta(hours=3)
    day = kickoff.astimezone(ZoneInfo("Europe/Zurich")).date().isoformat()
    # Use the actual writer, including both independent identity representations.
    candidate = replace(_challenge_candidate(kickoff), candidate_id="81:BTTS_YES", fixture_id=81, home_team_id=1, away_team_id=2,
                        home_team="1", away_team="2", expected_home_goals=1.812, expected_away_goals=.942,
                        context={"forecast_passed": True, "passed": True})
    record = _football_candidate_record(candidate, context_checked_at=modeled)
    assert record and record["analysis_evidence"]
    state = {"search_date": day, "status": "degraded", "discovery_model_version": CHALLENGE_PREDICTION_VERSION,
             "candidates": [record], "basis_candidates": []}
    document = {"version": AUTOMATED_WETTFINDER_VERSION, "generated_at": (modeled + timedelta(minutes=1)).isoformat(),
                "target_search_date": day, "football": state}
    return fixture, document, record


def test_cold_session_uses_the_fixture_goal_pair_for_both_models(tmp_path, monkeypatch):
    import ev_signal_sources
    from red_card_impact_predictor import RED_CARD_MODEL_VERSION
    from scanners.ultra_live_scanner_v3 import UltraLiveScanner

    fixture, document, _ = case()
    path = tmp_path / "state.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    ordinary, red = analyze_with_published_prior(fixture)
    assert ordinary["live_data_quality"] == "MEDIUM"
    assert (ordinary["xg_data"]["home_prior"], ordinary["xg_data"]["away_prior"]) == (1.812, .942)
    assert ordinary["model_version"] != UltraLiveScanner.MODEL_VERSION
    assert red["model_version"] != RED_CARD_MODEL_VERSION
    assert ordinary["prematch_prior_source"] == red["prematch_prior_source"] == CHALLENGE_PREDICTION_VERSION


def test_ordinary_no_card_game_with_and_without_bilateral_live_xg(tmp_path, monkeypatch):
    import ev_signal_sources
    fixture, document, _ = case()
    fixture["events"].pop()  # only the confirmed goal remains
    fixture["statistics"][0]["statistics"][1]["value"] = 0
    path = tmp_path / "state.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    ordinary, specialist = analyze_with_published_prior(fixture)
    assert specialist is None and ordinary["live_data_quality"] == "MEDIUM"
    assert ordinary["remaining_goals"]["over_0_5_probability"] > 55
    fixture["statistics"][0]["statistics"].pop(0)  # a prior cannot replace missing live xG
    assert analyze_with_published_prior(fixture) == (None, None)


@pytest.mark.parametrize("damage", [
    "league", "team", "names", "kickoff", "native_timestamp", "missing_cutoff", "at_kickoff",
    "after_model", "after_publication", "published_live", "prediction_version", "validation_version",
    "discovery_version", "event_identity", "scope", "sport", "source", "count_market", "missing_market",
    "missing_home", "out_of_range", "boolean", "broken_binding", "conflicting_goals", "changed_revision",
    "missing_catalog", "wrong_search_day", "only_raw_payloads", "corrupt_file", "foreign_candidate_id",
    "wrong_native_season",
])
def test_no_guess_or_ram_substitution_for_bad_issued_basis(tmp_path, monkeypatch, damage):
    import ev_signal_sources
    fixture, doc, row = case()
    analysis = row["analysis_evidence"]
    state = doc["football"]
    start = datetime.fromisoformat(fixture["fixture"]["date"])
    if damage == "league":
        row["league_id"] = 78
    elif damage == "foreign_candidate_id":
        row["candidate_id"] = analysis["identity"]["candidate_id"] = "4:BTTS_YES"
    elif damage == "wrong_native_season":
        fixture["league"]["season"] -= 1
    elif damage == "team":
        row["home_id"] = analysis["identity"]["home_id"] = 4
    elif damage == "names":
        row["home_team"] = analysis["identity"]["home_team"] = "Another team"
    elif damage == "kickoff":
        shifted = (start + timedelta(minutes=1)).isoformat()
        row["scheduled_start"] = analysis["identity"]["scheduled_start"] = shifted
    elif damage == "native_timestamp":
        fixture["fixture"]["timestamp"] = int(start.timestamp()) - 60
    elif damage in ("missing_cutoff", "at_kickoff", "after_model", "after_publication"):
        key, stamp = {"missing_cutoff": ("input_cutoff_at", None), "at_kickoff": ("modeled_at", start.isoformat()),
                      "after_model": ("input_cutoff_at", (start-timedelta(minutes=1)).isoformat()),
                      "after_publication": ("modeled_at", (start-timedelta(minutes=1)).isoformat())}[damage]
        row[key] = analysis["identity"][key] = stamp
    elif damage == "published_live":
        doc["generated_at"] = start.isoformat()
    elif damage in ("prediction_version", "validation_version", "discovery_version"):
        if damage == "discovery_version":
            state["discovery_model_version"] = "foreign"
        else:
            row["prediction_version" if damage == "prediction_version" else "validation_prediction_version"] = "foreign"
    elif damage in ("event_identity", "sport", "source"):
        row[damage] = "foreign"
    elif damage == "scope":
        row["model_scope"] = analysis["identity"]["model_scope"] = "senior_national_pooled"
    elif damage in ("count_market", "missing_market"):
        row["market_key"] = analysis["identity"]["market_key"] = (
            "CORNERS_OVER_8_5" if damage == "count_market" else "")
        row["market_kind"] = "corner_total" if damage == "count_market" else "unknown"
        analysis["basis"].update(expected_market_home=4.5, expected_market_away=5.1)
    elif damage == "missing_home":
        del analysis["basis"]["expected_home_goals"]
        analysis["basis"]["expected_market_home"] = 1.812
    elif damage in ("out_of_range", "boolean"):
        analysis["basis"]["expected_home_goals"] = 9.1 if damage == "out_of_range" else True
    elif damage == "broken_binding":
        analysis["identity"]["away_id"] = 4
    elif damage in ("conflicting_goals", "changed_revision"):
        other = deepcopy(row)
        if damage == "conflicting_goals":
            other["analysis_evidence"]["basis"]["expected_home_goals"] += .25
        else:
            stamp = (start-timedelta(minutes=179)).isoformat()
            other["modeled_at"] = other["analysis_evidence"]["identity"]["modeled_at"] = stamp
        state["basis_candidates"].append(other)
    elif damage == "missing_catalog":
        del state["basis_candidates"]
    elif damage == "wrong_search_day":
        state["search_date"] = "1999-01-01"
    elif damage == "only_raw_payloads":
        state["candidates"] = []
        state["riskobet_source_candidates"] = [row]
        doc["model_candidates"] = [row]
    path = tmp_path / "state.json"
    path.write_text("not json" if damage == "corrupt_file" else json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    analyzer = warm(fixture, monkeypatch)
    ordinary, _ = analyze_with_published_prior(fixture, analyzer)
    assert ordinary["live_data_quality"] == "LOW"
    assert ordinary["xg_data"]["home_prior"] is ordinary["xg_data"]["away_prior"] is None


def test_an_atomic_replacement_expires_the_index_even_at_same_size_and_mtime(tmp_path, monkeypatch):
    import os
    import ev_signal_sources
    fixture, doc, row = case()
    path = tmp_path / "state.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    assert analyze_with_published_prior(fixture)[0]["xg_data"]["home_prior"] == 1.812
    row["analysis_evidence"]["basis"]["expected_home_goals"] = 1.532
    new = tmp_path / "new.json"
    new.write_text(json.dumps(doc), encoding="utf-8")
    stat = path.stat()
    os.utime(new, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    new.replace(path)
    assert analyze_with_published_prior(fixture)[0]["xg_data"]["home_prior"] == 1.532


def test_next_day_uses_its_own_publication_clock_and_not_current_prices(tmp_path, monkeypatch):
    import ev_signal_sources
    fixture, doc, row = case()
    state = doc.pop("football")
    doc["football_next_day"] = state
    doc["decision_at"] = doc["generated_at"]
    prior_day = datetime.fromisoformat(state["search_date"]) - timedelta(days=1)
    doc.update(football={}, target_search_date=prior_day.date().isoformat(), next_day_search_date=state["search_date"],
               generated_at=(datetime.fromisoformat(doc["decision_at"]) - timedelta(hours=4)).isoformat())
    row["minimum_odds"] = -1
    row["reference_quote"] = {"price": 444}
    path = tmp_path / "state.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    assert analyze_with_published_prior(fixture)[0]["xg_data"]["home_prior"] == 1.812


@pytest.mark.parametrize("start,admitted", [
    ("2026-11-22T22:45:00+00:00", True),   # 23:45 Zürich -> 00:30 (next day)
    ("2026-11-21T23:45:00+00:00", True),   # still the previous Zurich date
    ("2026-11-21T22:45:00+00:00", False),  # two Zurich dates ago
    ("2026-11-22T23:31:00+00:00", False),  # provider says live before kickoff
])
def test_current_live_fixture_respects_its_zurich_day_and_true_kickoff(tmp_path, monkeypatch, start, admitted):
    import ev_signal_sources
    import live_football_priors
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc).astimezone(tz)
    fixture, doc, _ = case(datetime.fromisoformat(start))
    path = tmp_path / "state.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    monkeypatch.setattr(live_football_priors, "datetime", Frozen)
    assert live_football_priors.stored_goal_priors(fixture) == ((1.812, .942) if admitted else None)


def test_corrupt_other_fixture_is_not_global_outage_and_price_only_edition_cannot_change_goal_pair(tmp_path, monkeypatch):
    import ev_signal_sources
    import live_football_priors
    fixture, doc, row = case()
    doc["football"]["basis_candidates"] = [dict(row, fixture_id=9, analysis_evidence={"identity": []})]
    path = tmp_path / "state.json"
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    for quote in (None, 99.99):
        row["reference_quote"] = quote
        path.write_text(json.dumps(doc), encoding="utf-8")
        assert live_football_priors.stored_goal_priors(fixture) == (1.812, .942)
