"""Declared shadow/backtest match-winner rule, not bookmaker certification.

Only observed completed sets count. A partially played set is not a completed
set; missing terminal evidence is not a void, win, or healthy normal result.
"""
from __future__ import annotations
import math

RETIREMENT_RULE = "one_set"


def match_winner_status(termination: str, actual_winner: str | None,
                        completed_sets: int | None, *, rule: str = RETIREMENT_RULE) -> str:
    """Return standing, void, or non_evaluable without inventing a payout."""
    if termination not in {"normal", "retirement", "walkover"}:
        raise ValueError("unsupported tennis termination")
    if rule not in {"ball_served", "one_set", "match_completed"}:
        raise ValueError("unsupported retirement rule")
    if completed_sets is not None and (isinstance(completed_sets, bool)
            or not isinstance(completed_sets, int) or completed_sets < 0):
        raise ValueError("completed sets must be a non-negative integer")
    if termination == "walkover" or (termination == "retirement" and rule == "match_completed"):
        return "void"
    if termination == "retirement":
        if completed_sets is None:
            return "non_evaluable"
        if rule == "one_set" and completed_sets == 0:
            return "void"
        # For ball_served, a positive completed-set count proves play. A zero
        # count cannot tell a ball-served retirement from a no-play terminal.
        if rule == "ball_served" and completed_sets == 0:
            return "non_evaluable"
    return "standing" if actual_winner else "non_evaluable"


def unit_return(status: str, won: bool, odds: float | None) -> float | None:
    if status == "void":
        return 0.
    if (status != "standing" or isinstance(odds, bool)
            or not isinstance(odds, (int, float)) or not math.isfinite(odds) or odds <= 1.):
        return None
    return odds - 1. if won else -1.
