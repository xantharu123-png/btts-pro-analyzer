"""Exact API-Football 349 contract from the retained Roma/Genoa paid receipt.

Native facts: output/multigoal-quotes-20261017/paid-probe-04.json, fixture
1550148, Bet365 id 8, provider update 2026-10-17T09:18:17+00:00. No live calls.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import challenge_engine as engine
import market_consensus as mc
from tests.test_football_original_capture import values


UPDATED = datetime(2026, 10, 17, 9, 18, 17, tzinfo=timezone.utc)
FETCHED = datetime(2026, 10, 17, 13, 39, 51, 843829, tzinfo=timezone.utc)
START = "2026-10-17T18:45:00+00:00"


def native_payload():
    return {"get": "odds", "parameters": {"fixture": "1550148", "page": "1"},
        "errors": [], "results": 1, "paging": {"current": 1, "total": 1},
        "response": [{"fixture": {"id": 1550148, "timezone": "UTC", "date": START,
                                  "timestamp": 1792262700},
            "update": UPDATED.isoformat(), "bookmakers": [{"id": 8, "name": "Bet365",
                "bets": [{"id": 349, "name": "Number Of Goals In Match", "values": [
                    {"value": "Under 2 goals", "odd": "4.00"},
                    {"value": "2 or 3 goals", "odd": "2.00"},
                    {"value": "Over 3 goals", "odd": "3.20"}]}]}]}]}


@pytest.fixture(scope="module")
def modeled_candidate():
    fixture, history = values()
    fixture["fixture"].update(id=1550148, date=START, timestamp=1792262700)
    fixture["teams"]["home"]["name"] = "Roma"
    fixture["teams"]["away"]["name"] = "Genoa"
    candidates = engine.build_fixture_candidates(fixture, history, {},
        candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER)
    return next(row for row in candidates if row.market_key == "TOTAL_RANGE_2_3")


def test_only_the_approved_total_2_3_target_is_added():
    assert mc.exact_market_target("TOTAL_RANGE_2_3") == ("Total Goals Number By Ranges", "2-3")
    assert mc.exact_market_target("HOME_RANGE_2_3") is None
    assert mc.exact_market_target("AWAY_RANGE_2_3") is None


def test_native_349_parser_retains_only_the_observed_adjacent_pair_price():
    row = dict(candidate_id="native-349-contract", fixture_id=1550148,
               market_key="TOTAL_RANGE_2_3", selection="2-3 Tore", kickoff=START)

    quotes = mc.parse_fixture_consensus(native_payload(), [row], fetched_at=FETCHED,
                                        retain_observations=True)

    assert set(quotes) == {"native-349-contract"}
    assert quotes["native-349-contract"].value_name == "2-3"
    assert quotes["native-349-contract"].best_odds == 2.00
    assert mc.quote_matches_candidate(quotes["native-349-contract"], row)


def test_native_349_offer_binds_to_the_real_modeled_2_3_candidate_without_clock_rewrite(modeled_candidate):
    diagnostics = {}
    quotes = mc.parse_fixture_consensus(native_payload(), [modeled_candidate], fetched_at=FETCHED,
        retain_observations=True, diagnostics=diagnostics)

    quote = quotes[modeled_candidate.candidate_id]
    assert isinstance(modeled_candidate, engine.ChallengeCandidate)
    assert modeled_candidate.selection == "2-3 Tore"
    assert mc.quote_matches_candidate(quote, modeled_candidate)
    assert quote.bet_name == "Total Goals Number By Ranges"
    assert quote.value_name == "2-3"
    assert quote.bookmaker_count == 1
    assert quote.best_odds == 2.00
    assert quote.points[0].bookmaker == "Bet365"
    assert quote.points[0].bookmaker_id == "api-football:8"
    assert quote.points[0].observed_at == UPDATED.isoformat()
    assert quote.quoted_at == UPDATED.isoformat()
    assert quote.fetched_at == FETCHED.isoformat()
    assert diagnostics[modeled_candidate.candidate_id]["reason_code"] == "STALE_CLOCK"
    assert mc.wettfinder_consensus(quote, now=FETCHED) is None
    assert not mc.quote_below_publication_floor(quote, candidate=modeled_candidate, now=FETCHED)


@pytest.mark.parametrize("value", ["2 or 3 goals", " 2 OR 3 goals ", "2-3", "2 – 3"])
def test_adjacent_native_pair_and_existing_literal_range_share_one_exact_contract(modeled_candidate, value):
    payload = native_payload()
    payload["response"][0]["bookmakers"][0]["bets"][0]["values"] = [{"value": value, "odd": "2.00"}]

    quote = mc.parse_fixture_consensus(payload, [modeled_candidate], fetched_at=FETCHED,
        retain_observations=True)[modeled_candidate.candidate_id]

    assert quote.value_name == "2-3"
    assert quote.best_odds == 2.00
    assert mc.quote_matches_candidate(quote, modeled_candidate)


@pytest.mark.parametrize("value", ["1 or 3 goals", "2 or 4 goals", "3 or 2 goals",
    "2 or 3", "2 or 3 goals first half", "Under 2 goals", "Over 3 goals", "2", "3", "more 3"])
def test_disjoint_open_ended_or_period_qualified_values_never_supply_the_range(modeled_candidate, value):
    payload = native_payload()
    payload["response"][0]["bookmakers"][0]["bets"][0]["values"] = [{"value": value, "odd": "2.00"}]

    assert mc.parse_fixture_consensus(payload, [modeled_candidate], fetched_at=FETCHED,
                                      retain_observations=True) == {}


@pytest.mark.parametrize("bet_id,name", [
    (40, "Number Of Goals In Match"), (186, "Number Of Goals In Match"),
    (349, "Total Goals Number By Ranges"), (349, "Number Of Goals In Match - First Half"),
    (349, "Home Team Exact Goals Number"), (349, "Away Team Exact Goals Number"),
    (349, "Corners Over Under"), (349, "Correct Score"),
])
def test_wrong_market_id_name_period_or_role_cannot_relabel_349(modeled_candidate, bet_id, name):
    payload = native_payload()
    payload["response"][0]["bookmakers"][0]["bets"][0].update(id=bet_id, name=name)

    assert mc.parse_fixture_consensus(payload, [modeled_candidate], fetched_at=FETCHED,
                                      retain_observations=True) == {}


def test_native_total_pair_cannot_be_reused_for_other_ranges_or_team_roles(modeled_candidate):
    targets = [replace(modeled_candidate, candidate_id="other:" + key, market_key=key,
                       selection=selection) for key, selection in [
        ("TOTAL_RANGE_1_3", "1-3 Tore"), ("TOTAL_RANGE_2_4", "2-4 Tore"),
        ("HOME_RANGE_1_3", "1-3 Tore"), ("AWAY_RANGE_1_3", "1-3 Tore")]]

    assert mc.parse_fixture_consensus(native_payload(), targets, fetched_at=FETCHED,
                                      retain_observations=True) == {}


def test_native_349_rejects_a_foreign_fixture_or_wrong_start_without_rebinding(modeled_candidate):
    foreign = native_payload()
    foreign["response"][0]["fixture"]["id"] = 1550149
    assert mc.parse_fixture_consensus(foreign, [modeled_candidate], fetched_at=FETCHED,
                                      retain_observations=True) == {}
    quote = mc.parse_fixture_consensus(native_payload(), [modeled_candidate], fetched_at=FETCHED,
        retain_observations=True)[modeled_candidate.candidate_id]
    assert not mc.quote_matches_candidate(quote, replace(modeled_candidate,
        kickoff="2026-10-17T20:45:00+00:00"))


def test_captured_stale_native_offer_is_not_promoted_to_a_fresh_quote(modeled_candidate):
    assert mc.parse_fixture_consensus(native_payload(), [modeled_candidate], fetched_at=FETCHED) == {}
    expired = deepcopy(native_payload())
    expired["response"][0]["update"] = (FETCHED - timedelta(hours=25)).isoformat()
    assert mc.parse_fixture_consensus(expired, [modeled_candidate], fetched_at=FETCHED,
                                      retain_observations=True) == {}
