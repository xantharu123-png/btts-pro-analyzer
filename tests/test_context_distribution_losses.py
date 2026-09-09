"""Synthetic score-law checks, not source-resolved empirical evaluations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import math

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, validate_event
from context_observations import append_observation, observations_as_of
from context_sources.outcomes import _record


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def api():
    return importlib.import_module("context_models.distribution_losses")


def fixture(tmp_path, family="football:goals:90min", *, goals=(2, 1), winner="home", best_of=3, lost_sets=0):
    football = family.startswith("football:")
    prefix = "api-football:football:" if football else "espn:tennis:ATP:"
    event = {"event_key": prefix+("901" if football else "match:901"),
             "sport": "football" if football else "tennis", "home_id": prefix+("team:" if football else "player:")+"1",
             "away_id": prefix+("team:" if football else "player:")+"2",
             "competition": "api-football:league:39" if football else "espn:ATP:tournament:1",
             "format": "90min" if football else f"singles_best_of_{best_of}",
             "scheduled_start": canonical_timestamp(NOW), "schedule_revision": "synthetic-v1", "status": "scheduled"}
    if not football:
        event.update(tour="ATP", surface="Hard", indoor=False)
    event = validate_event(event)
    if football:
        params = {"home_lambda": 1.7, "away_lambda": 1.1}
        markets = {"home_win": .5}
        contract, terminal = "football-regulation-ft-v1", "FT"
        result = dict(zip(("goals_home", "goals_away"), goals))
    else:
        params = {"p_a": .61} if family == "tennis:winner" else {"hold_a": .78, "hold_b": .72, "best_of": best_of}
        markets = {"winner_a": .61, "winner_b": .39}
        contract = "tennis-completed-winner-v1" if family == "tennis:winner" else "tennis-completed-serve-v1"
        terminal = "completed"
        result = {"winner_id": event[winner+"_id"]}
        if family == "tennis:serve":
            needed = best_of//2+1
            won = {"home": 6 if winner == "home" else 0, "away": 0 if winner == "home" else 6}
            lost = {"home": won["away"], "away": won["home"]}
            result.update(set_scores=[won]*(needed-1)+[lost]*lost_sets+[won],
                          held_games_home=3*(needed if winner == "home" else lost_sets), service_games_home=3*(needed+lost_sets),
                          held_games_away=3*(needed if winner == "away" else lost_sets), service_games_away=3*(needed+lost_sets))
    base = {"version": "synthetic-base-v1", "model_hash": "a"*64, "event_key": event["event_key"],
            "cutoff": canonical_timestamp(NOW-timedelta(hours=1)), "family": family, "params": params,
            "markets": markets, "history_refs": [],
            "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "synthetic-law-check"}}
    db = tmp_path/"observations.db"
    at = NOW+timedelta(hours=3)
    append_observation(db, _record(event, result, contract, terminal, at), observed_at=at)
    outcome = observations_as_of(db, event["event_key"], cutoff=at, schedule_revision=event["schedule_revision"])[0]
    return event, base, deepcopy(base), outcome


def score(values):
    event, base, comparison, outcome = values
    return api().paired_distribution_losses(base, comparison, outcome, event=event, block="test:0")


def test_joint_goal_logloss_uses_actual_pair_not_overlapping_market_marginals(tmp_path):
    values = fixture(tmp_path)
    event, base, comparison, outcome = values
    comparison["params"] = {"home_lambda": 2., "away_lambda": 1.3}
    comparison["markets"] = {"home_win": .95, "btts_yes": .95}
    original = deepcopy(values)
    result = score(values)
    expected = math.fsum(rate - k*math.log(rate)+math.lgamma(k+1) for k, rate in zip((2, 1), (2., 1.3)))
    assert result["context_logloss"] == pytest.approx(expected, abs=1e-14)
    assert result["event_key"] == event["event_key"] and result["decision_at"] == base["cutoff"]
    assert result["block"] == "test:0" and result["outcome_contract"] == "football-regulation-ft-v1"
    assert result["tail_policy"] == "independent-poisson-exact-score-log-v1"
    assert values == original


@pytest.mark.parametrize("goals", [(0, 0), (25, 0), (26, 1), (500, 501)])
def test_goal_score_tail_is_exact_not_folded_into_last_market_matrix_cell(tmp_path, goals):
    result = score(fixture(tmp_path, goals=goals))
    expected = math.fsum(rate-k*math.log(rate)+math.lgamma(k+1) for k, rate in zip(goals, (1.7, 1.1)))
    assert result["base_logloss"] == pytest.approx(expected, abs=1e-12)
    assert math.isfinite(result["base_logloss"])
    assert result["base_logloss"] == result["context_logloss"]


@pytest.mark.parametrize("winner,probability", [("home", .7), ("away", .7), ("home", 1e-300), ("away", 1e-300)])
def test_winner_bernoulli_uses_native_winner_and_stable_log_complement(tmp_path, winner, probability):
    values = fixture(tmp_path, "tennis:winner", winner=winner)
    for base in values[1:3]:
        base["params"]["p_a"] = probability
        base["markets"] = {"winner_a": probability, "winner_b": 1-probability}
    result = score(values)
    expected = -math.log(probability) if winner == "home" else -math.log1p(-probability)
    assert result["base_logloss"] == expected
    assert result["context_logloss"] == expected
    assert result["tail_policy"] == "native-winner-bernoulli-log-v1"


@pytest.mark.parametrize("best_of,lost_sets", [(3, 0), (3, 1), (5, 0), (5, 1), (5, 2)])
@pytest.mark.parametrize("winner", ["home", "away"])
def test_serve_scores_actual_match_set_result_from_existing_joint_law(tmp_path, best_of, lost_sets, winner):
    from tennis.simulator import simulate_match
    values = fixture(tmp_path, "tennis:serve", best_of=best_of, winner=winner, lost_sets=lost_sets)
    result = score(values)
    distribution = simulate_match(.78, .72, best_of, strict=True)
    needed = best_of//2+1
    key = (needed, lost_sets) if winner == "home" else (lost_sets, needed)
    assert result["base_logloss"] == pytest.approx(-math.log(distribution.correct_scores[key]), abs=1e-12)
    assert result["tail_policy"] == "iidsets-holdproxy-tb7-match-set-score-log-v1"


def test_serve_log_space_does_not_turn_underflowed_match_probability_into_a_floor(tmp_path):
    from tennis.simulator import simulate_match
    values = fixture(tmp_path, "tennis:serve", best_of=5)
    for base in values[1:3]:
        base["params"].update(hold_a=1e-30, hold_b=1-1e-16)
    assert simulate_match(1e-30, 1-1e-16, 5, strict=True).correct_scores[(3, 0)] == 0.
    result = score(values)
    assert math.isfinite(result["base_logloss"]) and result["base_logloss"] > 745
    assert result["base_logloss"] == result["context_logloss"]


@pytest.mark.parametrize("winner,probability", [("home", 0.), ("away", 1.)])
def test_impossible_winner_is_typed_failure_not_epsilon_or_missing_coverage(tmp_path, winner, probability):
    values = fixture(tmp_path, "tennis:winner", winner=winner)
    values[2]["params"]["p_a"] = probability
    values[2]["markets"] = {"winner_a": probability, "winner_b": 1-probability}
    with pytest.raises(ContextContractError):
        score(values)


@pytest.mark.parametrize("mutation", ["event", "cutoff", "family", "base-after-start", "started", "outcome-clock", "extra-price"])
def test_mismatched_or_mutated_comparison_inputs_do_not_produce_losses(tmp_path, mutation):
    values = fixture(tmp_path)
    event, base, comparison, outcome = values
    if mutation == "event":
        comparison["event_key"] = "api-football:football:902"
    elif mutation == "cutoff":
        comparison["cutoff"] = canonical_timestamp(NOW-timedelta(minutes=1))
    elif mutation == "family":
        comparison["family"] = "tennis:winner"
    elif mutation == "base-after-start":
        base["cutoff"] = comparison["cutoff"] = canonical_timestamp(NOW)
    elif mutation == "started":
        event["status"] = "live"
    elif mutation == "outcome-clock":
        outcome["observed_at"] = base["cutoff"]
    else:
        comparison["price"] = 1.5
    with pytest.raises((ContextContractError, ValueError)):
        score(values)


def test_serve_format_and_winner_only_outcome_cannot_be_cross_scored(tmp_path):
    values = fixture(tmp_path, "tennis:serve")
    values[2]["params"]["best_of"] = 5
    with pytest.raises(ContextContractError):
        score(values)


@pytest.mark.parametrize("block", ["train", "test:-1", "test:01", True, "price:1"])
def test_only_explicit_canonical_test_block_identifiers_are_accepted(tmp_path, block):
    event, base, comparison, outcome = fixture(tmp_path)
    with pytest.raises(ContextContractError):
        api().paired_distribution_losses(base, comparison, outcome, event=event, block=block)


@pytest.mark.parametrize("winner,probability", [("home", 1.), ("away", 0.)])
def test_exact_certain_correct_winner_has_zero_loss_without_floor(tmp_path, winner, probability):
    values = fixture(tmp_path, "tennis:winner", winner=winner)
    for base in values[1:3]:
        base["params"]["p_a"] = probability
        base["markets"] = {"winner_a": probability, "winner_b": 1-probability}
    result = score(values)
    assert result["base_logloss"] == result["context_logloss"] == 0.


@pytest.mark.parametrize("family", ["cricket", "ice_hockey:goals:60min", "basketball:margin:including_ot", "esports:winner", None, []])
def test_unimplemented_distribution_law_is_not_borrowed_from_another_sport(family):
    with pytest.raises(ContextContractError):
        api().distribution_policy(family)


@pytest.mark.parametrize("rate", [8.000001, 0., -1., True, float("inf"), float("nan")])
def test_goal_scorer_keeps_original_parameter_domain_not_a_new_rate_clip(tmp_path, rate):
    values = fixture(tmp_path)
    values[2]["params"]["home_lambda"] = rate
    with pytest.raises(ContextContractError):
        score(values)


def test_numeric_goal_count_cannot_be_rounded_before_scoring(tmp_path):
    values = fixture(tmp_path, goals=(2**53+1, 0))
    with pytest.raises(ContextContractError):
        score(values)


def test_distribution_helper_does_not_add_approval_or_case_truth_fields(tmp_path):
    assert set(score(fixture(tmp_path))) == {"event_key", "decision_at", "block", "outcome_contract",
                                           "tail_policy", "base_logloss", "context_logloss"}
