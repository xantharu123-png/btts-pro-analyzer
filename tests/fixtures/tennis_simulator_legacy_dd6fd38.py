"""Exact point -> game -> set -> match probability engine (no Monte Carlo).

Given each player's probability of holding serve, we compute exact
distributions for every market the app cares about:

- match winner (Bo3 and Bo5)
- set totals      (over/under 2.5 in Bo3; 3.5 / 4.5 in Bo5)
- game totals     (over/under any line, e.g. 22.5)
- game handicaps  (A -3.5 games etc.)
- correct set scores
- tiebreak played in the match (yes/no)

Method: closed-form game probability, dynamic programming over set
game-states (serve alternation + 6-6 tiebreak), then a match recursion
over per-set outcome distributions.  Sets are modelled i.i.d. and the
first-serve parity is averaged 50/50 — standard approximations with
negligible impact at market level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from math import comb
from typing import Dict, Tuple


# --------------------------------------------------------------------- points


def game_win_prob(p: float) -> float:
    """P(server wins the game) when winning each point with prob p."""
    q = 1.0 - p
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    deuce_win = (p * p) / (p * p + q * q)
    return p ** 4 * (1.0 + 4.0 * q + 10.0 * q * q) + 20.0 * (p ** 3) * (q ** 3) * deuce_win


def tiebreak_win_prob(p: float) -> float:
    """P(win a tiebreak) winning each point with prob p (win to 7, by 2)."""
    q = 1.0 - p
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    prob = 0.0
    for k in range(0, 6):
        # final score 7-k: A takes the last point; first 6+k points split 6-k
        prob += comb(6 + k, k) * (p ** 7) * (q ** k)
    # 6-6, then win by two clear points
    prob += comb(12, 6) * (p ** 6) * (q ** 6) * (p * p) / (p * p + q * q)
    return prob


def hold_to_point_prob(hold_prob: float) -> float:
    """Invert game_win_prob: which point probability yields this hold%?"""
    hold_prob = min(max(hold_prob, 1e-4), 1.0 - 1e-4)
    lo, hi = 1e-4, 1.0 - 1e-4
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if game_win_prob(mid) < hold_prob:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ----------------------------------------------------------------------- sets


def _set_over(ga: int, gb: int) -> bool:
    high, low = max(ga, gb), min(ga, gb)
    return (high == 6 and low <= 4) or (high == 7 and low == 5)


@lru_cache(maxsize=4096)
def _set_distribution_cached(p_hold_a: float, p_hold_b: float) -> Tuple:
    """Joint distribution over set outcomes from A's perspective.

    Returns tuple rows of (winner, games_a, games_b, tiebreak, prob).
    First-serve parity is averaged 50/50.
    """
    p_tb_a = (p_hold_a + (1.0 - p_hold_b)) / 2.0  # A's point prob in a tiebreak
    p_a_tb = tiebreak_win_prob(p_tb_a)
    out: Dict[Tuple[str, int, int, bool], float] = {}

    for a_serves_first in (True, False):
        weight = 0.5  # applied once at the root, NOT per game
        states: Dict[Tuple[int, int], float] = {(0, 0): weight}
        while states:
            nxt: Dict[Tuple[int, int], float] = {}
            for (ga, gb), prob in states.items():
                games_played = ga + gb
                a_serving = (games_played % 2 == 0) == a_serves_first
                p_a_game = p_hold_a if a_serving else (1.0 - p_hold_b)
                for a_wins, p_game in ((True, p_a_game), (False, 1.0 - p_a_game)):
                    na = ga + (1 if a_wins else 0)
                    nb = gb + (0 if a_wins else 1)
                    w = prob * p_game
                    if na == 6 and nb == 6:
                        _emit(out, 7, 6, True, w * p_a_tb)
                        _emit(out, 6, 7, True, w * (1.0 - p_a_tb))
                    elif _set_over(na, nb):
                        _emit(out, na, nb, False, w)
                    else:
                        nxt[(na, nb)] = nxt.get((na, nb), 0.0) + w
            states = nxt
    return tuple((w_, ga, gb, tb, p) for (w_, ga, gb, tb), p in sorted(out.items()))


def _emit(out, ga, gb, tb, prob):
    winner = "A" if ga > gb else "B"
    key = (winner, ga, gb, tb)
    out[key] = out.get(key, 0.0) + prob


# ---------------------------------------------------------------------- match


@dataclass
class MatchMarkets:
    """All market distributions for one match, from A's perspective."""

    p_a_win: float
    p_b_win: float
    best_of: int
    sets_played: Dict[int, float] = field(default_factory=dict)           # {3: p, 4: p, 5: p}
    correct_scores: Dict[Tuple[int, int], float] = field(default_factory=dict)  # {(3,1): p}
    games_total: Dict[int, float] = field(default_factory=dict)           # {total games: p}
    games_diff: Dict[int, float] = field(default_factory=dict)            # {a_games-b_games: p}
    p_tiebreak_in_match: float = 0.0
    expected_total_games: float = 0.0

    def over_sets(self, line: float) -> float:
        return sum(p for n, p in self.sets_played.items() if n > line)

    def over_games(self, line: float) -> float:
        return sum(p for n, p in self.games_total.items() if n > line)

    def handicap_a(self, line: float) -> float:
        """P(A covers ``line`` games): (A games - B games) + line > 0."""
        return sum(p for d, p in self.games_diff.items() if d + line > 0)


def simulate_match(p_hold_a: float, p_hold_b: float, best_of: int = 3) -> MatchMarkets:
    """Exact market distributions for a match between A and B."""
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    p_hold_a = min(max(p_hold_a, 1e-3), 1.0 - 1e-3)
    p_hold_b = min(max(p_hold_b, 1e-3), 1.0 - 1e-3)

    set_dist = _set_distribution_cached(round(p_hold_a, 4), round(p_hold_b, 4))
    sets_needed = 2 if best_of == 3 else 3

    p_a_win = 0.0
    p_no_tiebreak = 0.0
    sets_played: Dict[int, float] = {}
    correct: Dict[Tuple[int, int], float] = {}
    games_total: Dict[int, float] = {}
    games_diff: Dict[int, float] = {}

    # state: (sets_a, sets_b) -> (mass, games_joint, diff_joint, no_tb_mass)
    # every distribution is JOINT (already probability-weighted)
    State = Tuple[float, Dict[int, float], Dict[int, float], float]
    states: Dict[Tuple[int, int], State] = {(0, 0): (1.0, {0: 1.0}, {0: 1.0}, 1.0)}

    while states:
        nxt: Dict[Tuple[int, int], State] = {}
        for (sa, sb), (mass, gdist, ddist, no_tb) in states.items():
            if sa == sets_needed or sb == sets_needed:
                p_a_win += mass if sa == sets_needed else 0.0
                p_no_tiebreak += no_tb
                n_played = sa + sb
                sets_played[n_played] = sets_played.get(n_played, 0.0) + mass
                correct[(sa, sb)] = correct.get((sa, sb), 0.0) + mass
                for g, pg in gdist.items():
                    games_total[g] = games_total.get(g, 0.0) + pg
                for d, pd_ in ddist.items():
                    games_diff[d] = games_diff.get(d, 0.0) + pd_
                continue
            for winner, ga, gb, tb, p_set in set_dist:
                na = sa + (1 if winner == "A" else 0)
                nb = sb + (0 if winner == "A" else 1)
                key = (na, nb)
                cur = nxt.get(key) or (0.0, {}, {}, 0.0)
                n_mass = cur[0] + mass * p_set
                n_g = dict(cur[1])
                for g, pg in gdist.items():
                    ng = g + ga + gb
                    n_g[ng] = n_g.get(ng, 0.0) + p_set * pg
                n_d = dict(cur[2])
                for d, pd_ in ddist.items():
                    nd = d + (ga - gb)
                    n_d[nd] = n_d.get(nd, 0.0) + p_set * pd_
                n_no_tb = cur[3] + no_tb * p_set * (0.0 if tb else 1.0)
                nxt[key] = (n_mass, n_g, n_d, n_no_tb)
        states = nxt

    exp_games = sum(g * p for g, p in games_total.items())
    return MatchMarkets(
        p_a_win=p_a_win,
        p_b_win=1.0 - p_a_win,
        best_of=best_of,
        sets_played=sets_played,
        correct_scores=correct,
        games_total=games_total,
        games_diff=games_diff,
        p_tiebreak_in_match=1.0 - p_no_tiebreak,
        expected_total_games=exp_games,
    )
