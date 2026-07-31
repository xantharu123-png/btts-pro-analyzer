"""Calibration watchdog for the offered side markets.

Re-runs the walk-forward calibration test (predict BEFORE each match,
compare simulator probabilities with actual outcomes) and answers one
question: are the set markets still calibrated, or has the simulator
started to drift?

Runs weekly inside the morning automation (Mondays, after the weekend
matches).  Drift verdicts:

- RMS deviation per market > RMS_DRIFT_LIMIT            -> drift
- max |bias| in well-filled mid buckets > BIAS_DRIFT_LIMIT -> drift

Game totals are measured too (they are banned from the UI); if their
bias ever resolves we can reconsider offering them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Optional

from .backtest import _is_retired
from .data_loader import load_atp_stats, add_normalized_names
from .serve_model import ServeReturnModel, is_tour_level
from .simulator import simulate_match

MIN_SERVE_GAMES = 40.0
WARMUP_UNTIL = "2024-01-01"

RMS_DRIFT_LIMIT = 0.07       # offered markets were at 0.037-0.047
BIAS_DRIFT_LIMIT = 0.05      # offered markets were at <=0.05 in mid buckets

SET_RE = re.compile(r"(\d)(\d)")  # '16 75 63' -> ('1','6'),('7','5'),('6','3')

WATCHED_MARKETS = ("over_2_5_sets", "under_2_5_sets", "set_a_2_0", "set_b_2_0")
REFERENCE_MARKETS = ("over_21_5_games",)  # banned from UI, still monitored


def _parse_score(row) -> Optional[tuple]:
    try:
        sa, sb = int(row.get("winner_sets_won")), int(row.get("loser_sets_won"))
        ga, gb = int(row.get("winner_games_won")), int(row.get("loser_games_won"))
        if sa + sb >= 2 and ga + gb > 0:
            return sa, sb, ga + gb, ga, gb
    except (TypeError, ValueError):
        pass
    return None


def collect_calibration() -> Dict:
    """Walk forward through ATP box scores; return bucket stats per market."""
    stats = load_atp_stats(range(2022, 2027))
    stats = add_normalized_names(stats, "winner_name", "loser_name")
    stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    serve = ServeReturnModel()
    buckets = defaultdict(lambda: [0, 0.0, 0.0])  # (market, bucket) -> [n, p_sum, hit_sum]
    n_scored = 0

    for s in stats.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        w_key, l_key = s.get("winner_key"), s.get("loser_key")
        if not w_key or not l_key:
            continue
        if str(s["tourney_date"])[:10] >= WARMUP_UNTIL and is_tour_level(s):
            as_of = s.get("tourney_date")
            scored = None
            if (serve.service_games(w_key, as_of=as_of) >= MIN_SERVE_GAMES
                    and serve.service_games(l_key, as_of=as_of) >= MIN_SERVE_GAMES):
                scored = _parse_score(s)
            if scored:
                flip = hash(w_key) % 2 == 1
                key_a, key_b = (l_key, w_key) if flip else (w_key, l_key)
                hold_a, hold_b = serve.expected_hold_probabilities(
                    key_a, key_b,
                    s.get("surface") if s.get("surface") in ("Hard", "Clay", "Grass") else None,
                    as_of=as_of,
                )
                m = simulate_match(hold_a, hold_b, best_of=3)
                sa_w, sb_w, total_games, _, _ = scored
                sa, sb = (sb_w, sa_w) if flip else (sa_w, sb_w)
                over_25 = m.over_sets(2.5)
                preds = {
                    "over_2_5_sets": over_25,
                    "under_2_5_sets": 1.0 - over_25,
                    "set_a_2_0": m.correct_scores.get((2, 0), 0.0),
                    "set_b_2_0": m.correct_scores.get((0, 2), 0.0),
                    "over_21_5_games": m.over_games(21.5),
                }
                actual = {
                    "over_2_5_sets": (sa + sb) > 2.5,
                    "under_2_5_sets": (sa + sb) <= 2.5,
                    "set_a_2_0": sa == 2 and sb == 0,
                    "set_b_2_0": sb == 2 and sa == 0,
                    "over_21_5_games": total_games > 21.5,
                }
                for k, p in preds.items():
                    b = round(p * 10) / 10
                    buckets[(k, b)][0] += 1
                    buckets[(k, b)][1] += p
                    buckets[(k, b)][2] += 1.0 if actual[k] else 0.0
                n_scored += 1
        if is_tour_level(s):
            serve.update_from_match_row(s)

    return {"buckets": buckets, "n_scored": n_scored}


def evaluate(buckets: Dict, n_scored: int) -> Dict:
    """Turn bucket stats into per-market RMS / max mid-bucket bias + verdict."""
    markets: Dict[str, Dict] = {}
    for market in WATCHED_MARKETS + REFERENCE_MARKETS:
        rms_n, rms_sum = 0, 0.0
        max_bias = 0.0
        n_total = 0
        for (mk, b), (n, p_sum, hit) in sorted(buckets.items()):
            if mk != market or n < 15:
                continue
            p_avg, emp = p_sum / n, hit / n
            rms_n += n
            rms_sum += n * (p_avg - emp) ** 2
            n_total += n
            if n >= 500 and 0.3 <= b <= 0.7:
                max_bias = max(max_bias, abs(emp - p_avg))
        if not rms_n:
            continue
        rms = (rms_sum / rms_n) ** 0.5
        markets[market] = {
            "n": n_total,
            "rms": round(rms, 4),
            "max_mid_bias": round(max_bias, 4),
            "drift": bool(rms > RMS_DRIFT_LIMIT or max_bias > BIAS_DRIFT_LIMIT),
        }
    offered_drift = any(
        markets.get(mk, {}).get("drift") for mk in WATCHED_MARKETS
    )
    return {
        "n_scored": n_scored,
        "markets": markets,
        "status": "drift" if offered_drift else "ok",
        "limits": {"rms": RMS_DRIFT_LIMIT, "mid_bias": BIAS_DRIFT_LIMIT},
    }


def run_watch() -> Dict:
    raw = collect_calibration()
    return evaluate(raw["buckets"], raw["n_scored"])
