"""Risk scenarios must not become contradictory independent public tips."""
from dataclasses import replace
from itertools import permutations
import sqlite3

import pytest

from riskobet_candidates import adapt_esports_shadow, adapt_football_candidates
from riskobet_domain import EvidenceStage
from riskobet_surface import build_riskobet_card, compose_riskobet_catalog
from test_riskobet_candidates import MODELED_AT, create_esports_db, football_pool, insert_esports
from test_riskobet_surface import _candidate


def card(market, side, *, sport="football", event="event", snapshot="a", stage=EvidenceStage.SHADOW,
         probability=.3, price_excluded=False):
    candidate = _candidate(
        key=f"{sport}-{event}-{snapshot}-{market}-{side}", event_key=event, sport=sport,
        market_key=market, selection_key=side, selection_label=side,
        model_probability=probability, cautious_probability=max(0, probability-.08), stage=stage,
    )
    candidate = replace(candidate, snapshot_id="snapshot_" + snapshot*64,
        settlement_contract=f"riskobet-settlement-v1:{sport}:{market}:{side}")
    return replace(build_riskobet_card(candidate), quote_floor_excluded=price_excluded)


def keys(catalog):
    return {(c.market_key, c.selection_key) for c in catalog.cards}


def test_actual_football_adapter_no_longer_publishes_win_and_draw_as_two_tips():
    bundle = adapt_football_candidates(
        football_pool(home_win=.30, draw=.30, away_win=.40, dc=.60, two_goals=.20), modeled_at=MODELED_AT)[0]
    assert {c.market_key for c in bundle.candidates} == {"result_90_minutes", "draw_90_minutes"}
    cards = tuple(build_riskobet_card(c) for c in bundle.candidates)
    catalog = compose_riskobet_catalog(cards)
    assert len(catalog.cards) == 1
    assert catalog.cards[0] is cards[0]


@pytest.mark.parametrize("second", [
    ("result_90_minutes", "away"), ("draw_90_minutes", "draw"),
    ("double_chance_90_minutes", "away_or_draw")])
def test_whole_event_coherence_preserves_existing_underdog_anchor(second):
    underdog = card("result_90_minutes", "home", probability=.30)
    opposite = card(*second, probability=.60)
    catalog = compose_riskobet_catalog([underdog, opposite], max_featured=1)
    assert catalog.cards == (underdog,)
    assert underdog.model_probability == .30


def test_jointly_compatible_football_markets_stay_available():
    winner = card("result_90_minutes", "home")
    goals = card("underdog_team_over_1_5_90_minutes", "away")
    catalog = compose_riskobet_catalog([winner, goals])
    assert keys(catalog) == {(winner.market_key, "home"), (goals.market_key, "away")}


def test_three_double_chance_scenarios_cannot_reset_joint_intersection_or_page_scope():
    rows = [card("double_chance_90_minutes", side) for side in
            ("home_or_draw", "away_or_draw", "home_or_away")]
    catalog = compose_riskobet_catalog(rows, max_featured=1)
    assert len(catalog.cards) == 2
    assert keys(catalog) == {(row.market_key, row.selection_key) for row in rows[:2]}


def test_price_floor_does_not_flip_to_an_opposing_scenario():
    winner = card("result_90_minutes", "home", price_excluded=True)
    draw = card("draw_90_minutes", "draw")
    assert not compose_riskobet_catalog([winner, draw]).cards
    compatible = card("underdog_team_over_1_5_90_minutes", "away")
    assert compose_riskobet_catalog([winner, draw, compatible]).cards == (compatible,)


def test_evidence_priority_before_event_cap_can_keep_later_validated_record():
    research = [card("result_90_minutes", side, stage=EvidenceStage.RESEARCH) for side in ("home", "away")]
    validated = card("draw_90_minutes", "draw", stage=EvidenceStage.VALIDATED)
    catalog = compose_riskobet_catalog([*research, validated])
    assert catalog.cards == (validated,)


def test_two_compatible_weaker_rows_cannot_cap_out_a_validated_anchor():
    research = [card("underdog_team_over_1_5_90_minutes", side, stage=EvidenceStage.RESEARCH)
                for side in ("home", "away")]
    validated = card("result_90_minutes", "home", stage=EvidenceStage.VALIDATED)
    catalog = compose_riskobet_catalog([*research, validated])
    assert catalog.cards[0] is validated
    assert len(catalog.cards) == 2


@pytest.mark.parametrize("sport,market", [("tennis", "match_winner"), ("esports", "series_winner"),
    ("basketball", "match_winner_including_ot"), ("ice_hockey", "match_winner_including_ot"),
    ("cricket", "match_winner")])
def test_opposing_binary_winners_are_never_independent_tips(sport, market):
    first, second = [card(market, side, sport=sport) for side in ("home", "away")]
    for rows in permutations((first, second)):
        assert compose_riskobet_catalog(rows).cards == (rows[0],)


def test_tennis_winner_and_opponent_one_set_are_compatible():
    winner = card("match_winner", "home", sport="tennis")
    set_pick = card("plus_1_5_sets", "away", sport="tennis")
    assert len(compose_riskobet_catalog([winner, set_pick]).cards) == 2


def test_esports_series_format_missing_does_not_guess_map_compatibility():
    winner = card("series_winner", "home", sport="esports")
    map_pick = card("at_least_one_map", "away", sport="esports")
    assert compose_riskobet_catalog([winner, map_pick]).cards == (winner,)
    # Not a market ban: the original first risk scenario remains available.
    assert compose_riskobet_catalog([map_pick, winner]).cards == (map_pick,)


def test_native_best_of_one_map_is_not_assumed_compatible_with_opposite_winner(tmp_path):
    path = tmp_path / "bo1.db"
    create_esports_db(path)
    insert_esports(path, 1, 60.0, 120.0)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE esports_shadow_predictions SET series_type=1")
    bundle = adapt_esports_shadow(path, as_of=MODELED_AT)[0]
    cards = tuple(build_riskobet_card(c) for c in bundle.candidates)
    assert {c.market_key for c in cards} == {"series_winner", "at_least_one_map"}
    # The native adapter really does emit Bo1 maps. The public card has no
    # exact frozen format field and must not promise joint compatibility.
    assert compose_riskobet_catalog(cards).cards == (cards[0],)
    map_pick = next(c for c in cards if c.market_key == "at_least_one_map")
    opposite = replace(card("series_winner", "away", sport="esports"),
        snapshot_id=map_pick.snapshot_id, event_key=map_pick.event_key)
    assert compose_riskobet_catalog([map_pick, opposite]).cards == (map_pick,)


def test_never_merge_other_events_sports_or_frozen_snapshots():
    first = card("result_90_minutes", "home")
    same_event_new_snapshot = card("draw_90_minutes", "draw", snapshot="b")
    other = card("result_90_minutes", "away", event="another")
    tennis = card("match_winner", "away", sport="tennis")
    catalog = compose_riskobet_catalog([first, same_event_new_snapshot, other, tennis])
    assert {c.candidate_id for c in catalog.cards} == {first.candidate_id, other.candidate_id, tennis.candidate_id}


def test_unknown_contract_cannot_certify_extra_compatibility():
    first = replace(card("result_90_minutes", "home"), settlement_contract="legacy")
    second = card("underdog_team_over_1_5_90_minutes", "away")
    assert compose_riskobet_catalog([first, second]).cards == (first,)


def test_contract_side_mismatch_and_duplicate_identity_are_not_fuzzy_joined():
    first = card("result_90_minutes", "home")
    mismatched = replace(card("draw_90_minutes", "draw"),
        settlement_contract="riskobet-settlement-v1:football:draw_90_minutes:home")
    assert compose_riskobet_catalog([first, mismatched]).cards == (first,)
    with pytest.raises(ValueError, match="duplicate"):
        compose_riskobet_catalog([first, first])
