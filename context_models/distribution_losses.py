"""Declared outcome log losses after owning D1 case/effect resolution.

This CPU scorer binds the existing B1 event, distributions and native outcome
receipt. It does not prove a causal replay, source truth, fitted provenance,
frozen experiment membership or approval. The D2 owner must establish those
before consuming these losses. A scoring failure is NOT a favorable missing-
coverage exclusion: the ready hypothesis must retain the reported failure.
"""
from __future__ import annotations

import math
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, require_number,
    validate_base_distribution, validate_event,
)
from context_sources.outcomes import validate_outcome_record


_POLICIES = {
    "football:goals:90min": ("football-regulation-ft-v1", "independent-poisson-exact-score-log-v1"),
    "tennis:winner": ("tennis-completed-winner-v1", "native-winner-bernoulli-log-v1"),
    "tennis:serve": ("tennis-completed-serve-v1", "iidsets-holdproxy-tb7-match-set-score-log-v1"),
}


class DistributionScoringError(ContextContractError):
    """The declared law cannot score this observation without inventing a floor."""


def distribution_policy(family: str) -> tuple[str, str]:
    """Fixed code-versioned outcome/tail policy, never caller-selected epsilon."""
    if type(family) is not str or family not in _POLICIES:
        raise ContextContractError("no owning distribution scorer for this family")
    return _POLICIES[family]


def _log_positive(probability):
    require_number(probability, "outcome probability", minimum=0, maximum=1)
    if probability == 0:
        raise DistributionScoringError("observed outcome has zero or unrepresentable probability")
    return math.log(probability)


def _goal_logloss(params, result):
    # The original engine's finite rate domain remains authoritative. Its
    # market matrix folds a negligible tail into cell25; the declared LOG
    # outcome is instead the exact underlying unbounded independent-Poisson
    # goal pair. Never call score25 an exact observation of score26, and never
    # change those existing market probabilities in this scoring-only module.
    from challenge_engine import score_matrix
    score_matrix(params["home_lambda"], params["away_lambda"])
    terms = []
    for side in ("home", "away"):
        count, rate = result["goals_"+side], params[side+"_lambda"]
        if int(float(count)) != count:
            raise DistributionScoringError("goal outcome integer is not exactly representable")
        terms.append(rate-count*math.log(rate)+math.lgamma(count+1))
    return math.fsum(terms)


def _serve_logloss(params, result):
    from tennis.simulator import _set_distribution_cached, simulate_match
    # Validate the unchanged strict B7 law, without legacy clamp/rounding.
    simulate_match(params["hold_a"], params["hold_b"], params["best_of"], strict=True)
    set_distribution = _set_distribution_cached(params["hold_a"], params["hold_b"])
    probabilities = {
        side: math.fsum(row[4] for row in set_distribution if row[0] == side)
        for side in ("A", "B")
    }
    scores = result["set_scores"]
    a = sum(row["home"] > row["away"] for row in scores)
    b = len(scores)-a
    # Under the declared IID-set model the last set is won by the eventual
    # winner. All other set orders contribute comb(total-1, losing_sets).
    # Sum LOG terms before any product can underflow; the outcome is final
    # match-set score (e.g.2:1), not a fabricated full point/game-path density.
    terms = [math.log(math.comb(a+b-1, min(a, b)))]
    for wins, side in ((a, "A"), (b, "B")):
        if wins:
            terms.append(wins*_log_positive(probabilities[side]))
    return -math.fsum(terms)


def _score(family, params, result, event):
    try:
        if family == "football:goals:90min":
            loss = _goal_logloss(params, result)
        elif family == "tennis:serve":
            loss = _serve_logloss(params, result)
        else:
            p = params["p_a"]
            if result["winner_id"] == event["home_id"]:
                loss = -_log_positive(p)
            else:
                if p == 1:
                    raise DistributionScoringError("observed outcome has zero probability")
                loss = -math.log1p(-p)
        require_number(loss, "declared outcome logloss", minimum=0)
        return 0. if loss == 0 else loss
    except DistributionScoringError:
        raise
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise DistributionScoringError("declared distribution outcome is not numerically scoreable") from exc


def paired_distribution_losses(base: dict, comparison: dict, outcome: dict, *, event: dict, block: str) -> dict:
    """Score exactly one native result under two already resolved model laws.

    There are no caller-provided PMFs/losses/odds, no silent fallback to market
    products and no epsilon. Membership in the actual frozen block intervals
    and common ready-hypothesis cohort is a separate D2 owner check.
    """
    event = validate_event(event)
    base, comparison = validate_base_distribution(base), validate_base_distribution(comparison)
    if type(block) is not str or re.fullmatch(r"test:(0|[1-9][0-9]*)", block) is None:
        raise ContextContractError("distribution loss needs its canonical final-test block")
    if (event["status"] != "scheduled" or event["scheduled_start"] <= base["cutoff"]
            or base["event_key"] != event["event_key"] or base["family"].split(":")[0] != event["sport"]
            or any(comparison[key] != base[key] for key in ("event_key", "cutoff", "family"))):
        raise ContextIntegrityError("paired distribution event, decision or family differs")
    contract, policy = distribution_policy(base["family"])
    outcome = validate_outcome_record(outcome, event=event)
    if outcome["payload"]["outcome_contract"] != contract:
        raise ContextIntegrityError("native outcome does not match the declared distribution contract")
    if base["family"] == "tennis:serve":
        for model in (base, comparison):
            if event["format"] != f"singles_best_of_{model['params']['best_of']}":
                raise ContextIntegrityError("serve distribution differs from original match format")
    result = outcome["payload"]["result"]
    return {"event_key": event["event_key"], "decision_at": base["cutoff"], "block": block,
            "outcome_contract": contract, "tail_policy": policy,
            "base_logloss": _score(base["family"], base["params"], result, event),
            "context_logloss": _score(base["family"], comparison["params"], result, event)}
