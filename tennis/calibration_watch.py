"""Contract-bound calibration watchdog, not a model release certificate.

Re-runs the walk-forward calibration test (predict BEFORE each match,
compare simulator probabilities with actual outcomes). Production v2 needs
its actual calibrated winner anchor and joint original, which the box-score
source does not contain. The default therefore reports unavailable rather
than certifying v2 with legacy estimates. Explicit legacy analysis measures
only observed Bo3 formats; unknown/Bo5 rows never enter its market buckets.

Runs weekly inside the morning automation (Mondays, after the weekend
matches).  Drift verdicts:

- RMS deviation per market > RMS_DRIFT_LIMIT            -> drift
- max |bias| in well-filled mid buckets > BIAS_DRIFT_LIMIT -> drift

Game totals are measured too (they are banned from the UI); if their
bias ever resolves we can reconsider offering them.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from numbers import Real
from typing import Dict, Optional

from .backtest import _is_retired, stable_flip
from .data_loader import load_atp_stats, add_normalized_names
from .serve_model import ServeReturnModel, is_tour_level
from .simulator import LEGACY_MODEL_VERSION, POINT_MODEL_VERSION, simulate_match

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


def collect_calibration(*, model_version: str = POINT_MODEL_VERSION) -> Dict:
    """Collect only identifiable laws/formats; never invent a v2 winner anchor.

    ``best_of`` must be explicit source metadata, not inferred from score,
    tournament category/name, or the absence of a third set. The current ATP
    source has neither that field nor revision-bound v2 joint originals.
    ``hold-proxy-v1`` is an opt-in historical diagnostic, not production QA.
    """
    if model_version not in (LEGACY_MODEL_VERSION, POINT_MODEL_VERSION):
        raise ValueError("unsupported calibration watch model version")
    current_year = datetime.now(timezone.utc).year
    stats = load_atp_stats(range(max(2023, current_year - 3), current_year + 1))
    stats = add_normalized_names(stats, "winner_name", "loser_name")
    stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    serve = ServeReturnModel(split_indoor=True)
    buckets = defaultdict(lambda: [0, 0.0, 0.0])  # (market, bucket) -> [n, p_sum, hit_sum]
    n_scored = 0
    skipped = defaultdict(int)

    for s in stats.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        w_key, l_key = s.get("winner_key"), s.get("loser_key")
        if not w_key or not l_key:
            continue
        if str(s["tourney_date"])[:10] >= WARMUP_UNTIL and is_tour_level(s):
            best_of = s.get("best_of")
            reason = None
            if best_of is None or isinstance(best_of, Real) and math.isnan(best_of):
                reason = "format_not_observed"
            elif isinstance(best_of, bool) or not isinstance(best_of, Real) or best_of not in (3, 5):
                reason = "format_invalid"
            elif model_version == POINT_MODEL_VERSION:
                # A box-score row is not the original calibrated forecast.
                # Even a field named winner_probability cannot establish its
                # revision/state/source identity; use the owning original path.
                reason = "actual_joint_original_unavailable"
            elif best_of != 3:
                reason = "side_market_format_unsupported"
            if reason:
                skipped[reason] += 1
                serve.update_from_match_row(s)
                continue
            as_of = s.get("tourney_date")
            scored = None
            if (serve.service_games(w_key, as_of=as_of) >= MIN_SERVE_GAMES
                    and serve.service_games(l_key, as_of=as_of) >= MIN_SERVE_GAMES):
                scored = _parse_score(s)
            if scored and not (scored[0] == 2 and scored[1] in (0, 1)):
                skipped["score_format_conflict"] += 1
                scored = None
            if scored:
                flip = stable_flip(w_key)
                key_a, key_b = (l_key, w_key) if flip else (w_key, l_key)
                hold_a, hold_b = serve.expected_hold_probabilities(
                    key_a, key_b,
                    s.get("surface") if s.get("surface") in ("Hard", "Clay", "Grass") else None,
                    as_of=as_of,
                    indoor=s.get("indoor_outdoor") == "Indoor",
                )
                m = simulate_match(hold_a, hold_b, best_of=3,
                                   model_version=LEGACY_MODEL_VERSION)
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

    return {"buckets": buckets, "n_scored": n_scored,
            "model_version": model_version, "skipped": dict(skipped)}


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
    missing_markets = [
        market for market in WATCHED_MARKETS if market not in markets
    ]
    if offered_drift:
        status = "drift"
    elif missing_markets:
        status = "insufficient"
    else:
        status = "ok"
    return {
        "n_scored": n_scored,
        "markets": markets,
        "missing_markets": missing_markets,
        "status": status,
        "limits": {"rms": RMS_DRIFT_LIMIT, "mid_bias": BIAS_DRIFT_LIMIT},
    }


def run_watch(*, model_version: str = POINT_MODEL_VERSION) -> Dict:
    raw = collect_calibration(model_version=model_version)
    result = evaluate(raw["buckets"], raw["n_scored"])
    result.update(model_version=raw["model_version"], skipped=raw["skipped"],
                  production_model_certified=False)
    if model_version == POINT_MODEL_VERSION:
        result.update(status="unavailable",
                      unavailable_reason="actual_joint_original_unavailable")
    return result
