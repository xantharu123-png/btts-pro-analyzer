"""Versioned game -> set -> match probability engine (no Monte Carlo).

Given each player's probability of holding serve, we compute exact
distributions for every market the app cares about:

- match winner (Bo3 and Bo5)
- set totals      (over/under 2.5 in Bo3; 3.5 / 4.5 in Bo5)
- game totals     (over/under any line, e.g. 22.5)
- game handicaps  (A -3.5 games etc.)
- correct set scores
- tiebreak played in the match (yes/no)

Method: game/set dynamic programming and match recursion. The frozen v1
retains its hold-proxy tiebreak. V2 inverts holds to serve-point chances and
uses the actual tiebreak serve order (Bo5 deciding tiebreak to ten). A calibrated
winner anchor reweights all terminal outcomes together, never isolated markets.
Sets are otherwise IID and first-server parity is averaged 50/50. These remain
model assumptions, not a claim of empirical predictive superiority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from math import comb, fsum, isclose, isfinite
from typing import Dict, Tuple

LEGACY_MODEL_VERSION = "hold-proxy-v1"
POINT_MODEL_VERSION = "serve-points-joint-v2"


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
    if type(hold_prob) not in (int, float) or not isfinite(hold_prob) or not 0 <= hold_prob <= 1:
        raise ValueError("hold probability must be finite and between zero and one")
    if hold_prob in (0, 1):
        return float(hold_prob)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if game_win_prob(mid) < hold_prob:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def serve_tiebreak_win_prob(p_serve_a: float, p_serve_b: float, *, a_serves_first: bool = True,
                           target: int = 7) -> float:
    """Win-by-two tiebreak with the actual 1-2-2 serve sequence.

    IID serve-point rates are inferred from the same hold-game model. At 6-6,
    every pair contains one serve per player; win/loss products are unchanged
    by pair order, so the infinite deuce tail is a closed geometric sum.
    """
    if type(target) is not int or target not in (7, 10) or type(a_serves_first) is not bool or any(type(p) not in (int, float) or not isfinite(p) or not 0 < p < 1
                                               for p in (p_serve_a, p_serve_b)):
        raise ValueError("tiebreak requires interior serve-point probabilities and an actual server flag")
    win_pair = p_serve_a * (1 - p_serve_b)
    lose_pair = (1 - p_serve_a) * p_serve_b
    tail = win_pair / (win_pair + lose_pair)
    @lru_cache(None)
    def visit(a, b):
        if max(a, b) >= target and abs(a-b) >= 2:
            return float(a > b)
        if a == b == target-1:
            return tail
        n = a+b
        serving_a = (n == 0 or ((n+1)//2) % 2 == 0) == a_serves_first
        p = p_serve_a if serving_a else 1-p_serve_b
        return p*visit(a+1, b) + (1-p)*visit(a, b+1)
    return visit(0, 0)


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
    return _set_distribution(p_hold_a, p_hold_b, (p_a_tb, p_a_tb))


@lru_cache(maxsize=4096)
def _point_set_distribution_cached(p_hold_a: float, p_hold_b: float, target: int = 7) -> Tuple:
    pa, pb = hold_to_point_prob(p_hold_a), hold_to_point_prob(p_hold_b)
    return _set_distribution(p_hold_a, p_hold_b, tuple(
        serve_tiebreak_win_prob(pa, pb, a_serves_first=first, target=target) for first in (True, False)))


def _set_distribution(p_hold_a, p_hold_b, tb_probabilities):
    out: Dict[Tuple[str, int, int, bool], float] = {}

    for a_serves_first, p_a_tb in zip((True, False), tb_probabilities):
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


def _winner_mass(set_dist, best_of, deciding_set_dist=None):
    needed = best_of//2+1
    a = fsum(p for winner, _, _, _, p in set_dist if winner == "A")
    b = fsum(p for winner, _, _, _, p in set_dist if winner == "B")
    if deciding_set_dist is not None:
        final_a = fsum(p for winner, _, _, _, p in deciding_set_dist if winner == "A")
        final_b = fsum(p for winner, _, _, _, p in deciding_set_dist if winner == "B")
        return (a**3+3*a**3*b+6*a*a*b*b*final_a,
                b**3+3*b**3*a+6*a*a*b*b*final_b)
    win = lambda x, y: fsum(comb(needed+k-1, k)*x**needed*y**k for k in range(needed))
    return win(a, b), win(b, a)


def point_match_win_probability(p_hold_a, p_hold_b, best_of=3):
    """Winner-only core for calibration; avoids a second full market DP."""
    if type(best_of) is not int or best_of not in (3, 5) or any(
            type(p) not in (int, float) or not isfinite(p) or not 0 < p < 1 for p in (p_hold_a, p_hold_b)):
        raise ValueError("point match inputs must be interior holds and Bo3/Bo5")
    return _winner_mass(_point_set_distribution_cached(p_hold_a, p_hold_b), best_of,
        _point_set_distribution_cached(p_hold_a, p_hold_b, 10) if best_of == 5 else None)[0]


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


def simulate_match(p_hold_a: float, p_hold_b: float, best_of: int = 3, *, strict: bool = False,
                   model_version: str = LEGACY_MODEL_VERSION,
                   winner_probability: float | None = None) -> MatchMarkets:
    """Versioned IID-set distributions with an optional coherent winner anchor.

    The legacy default retains its original clamp/rounding and results. New
    context models opt into strict finite interior inputs without quantization.
    Legacy artifacts keep their hold-proxy replay. V2 uses inferred serve
    points and the actual tiebreak serve order. Neither version models injury,
    non-IID form changes or a different final-set scoring rule.
    """
    if type(strict) is not bool:
        raise ValueError("strict must be an actual boolean")
    if model_version not in (LEGACY_MODEL_VERSION, POINT_MODEL_VERSION):
        raise ValueError("unknown tennis market model version")
    if winner_probability is not None and (model_version != POINT_MODEL_VERSION or
            type(winner_probability) not in (int, float) or not isfinite(winner_probability) or not 0 <= winner_probability <= 1):
        raise ValueError("a calibrated winner anchor requires the point joint model")
    if model_version == POINT_MODEL_VERSION:
        if type(best_of) is not int or best_of not in (3, 5) or any(
                type(p) not in (int, float) or not isfinite(p) or not 0 < p < 1 for p in (p_hold_a, p_hold_b)):
            raise ValueError("point model requires finite interior holds and Bo3/Bo5")
        set_dist = _point_set_distribution_cached(p_hold_a, p_hold_b)
    elif strict:
        if type(best_of) is not int or best_of not in (3, 5):
            raise ValueError("strict best_of must be the actual integer 3 or 5")
        if any(type(value) not in (int, float) or not 0 < value < 1 or not isfinite(value)
               for value in (p_hold_a, p_hold_b)):
            raise ValueError("strict holds must be finite interior JSON probabilities")
        set_dist = _set_distribution_cached(p_hold_a, p_hold_b)
    else:
        if best_of not in (3, 5):
            raise ValueError("best_of must be 3 or 5")
        p_hold_a = min(max(p_hold_a, 1e-3), 1.0 - 1e-3)
        p_hold_b = min(max(p_hold_b, 1e-3), 1.0 - 1e-3)
        set_dist = _set_distribution_cached(round(p_hold_a, 4), round(p_hold_b, 4))
    # Bo5 is the ATP Slam main-draw rule: at 2-2, the deciding set uses the
    # ten-point Slam tiebreak; other sets keep seven. Old artifacts retain
    # their old all-seven-set replay, explicitly under the legacy contract.
    deciding_set_dist = (_point_set_distribution_cached(p_hold_a, p_hold_b, 10)
        if model_version == POINT_MODEL_VERSION and best_of == 5 else None)
    winning_mass = _winner_mass(set_dist, best_of, deciding_set_dist) if winner_probability is not None else None
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
                # Conditional reweighting changes only P(match winner), retaining
                # the serve model's distribution GIVEN each winner. All score,
                # game, handicap and tiebreak marginals use the same weighting.
                scale = 1.0
                if winning_mass is not None:
                    target = winner_probability if sa == sets_needed else 1-winner_probability
                    denominator = winning_mass[0 if sa == sets_needed else 1]
                    if denominator <= 0:
                        raise ValueError("winner anchor has no conditional support")
                    scale = target/denominator
                    mass, no_tb = mass*scale, no_tb*scale
                    gdist = {g: p*scale for g, p in gdist.items()}
                    ddist = {d: p*scale for d, p in ddist.items()}
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
            this_set = deciding_set_dist if deciding_set_dist is not None and sa == sb == 2 else set_dist
            for winner, ga, gb, tb, p_set in this_set:
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
    result = MatchMarkets(
        p_a_win=winner_probability if winner_probability is not None else p_a_win,
        p_b_win=1.0 - (winner_probability if winner_probability is not None else p_a_win),
        best_of=best_of,
        sets_played=sets_played,
        correct_scores=correct,
        games_total=games_total,
        games_diff=games_diff,
        p_tiebreak_in_match=1.0 - p_no_tiebreak,
        expected_total_games=exp_games,
    )
    if strict or model_version == POINT_MODEL_VERSION:
        # Never repair a malformed probability mass by clipping/renormalizing.
        for distribution in (result.sets_played, result.correct_scores, result.games_total, result.games_diff):
            if (not distribution or any(not isfinite(p) or not 0 <= p <= 1 for p in distribution.values())
                    or not isclose(fsum(distribution.values()), 1., rel_tol=0., abs_tol=1e-10)):
                raise ValueError("strict simulator returned invalid probability mass")
        if any(not isfinite(p) or not 0 <= p <= 1 for p in (result.p_a_win, result.p_b_win, result.p_tiebreak_in_match)):
            raise ValueError("strict simulator returned an invalid probability")
        if not isfinite(result.expected_total_games) or result.expected_total_games <= 0:
            raise ValueError("strict simulator returned invalid expected games")
    return result
