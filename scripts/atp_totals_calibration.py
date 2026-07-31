"""Calibration check for the side markets (totals / set handicap).

The winner-market edge is backtested; the side markets are NOT (no
historical O/U prices).  Before showing model prices for them we must
prove the simulator's *distributions* are calibrated against reality:
walk forward through ATP box scores, predict BEFORE each match, then
compare p(over X) with the actual outcome bucket by bucket.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import defaultdict

from tennis.data_loader import load_atp_stats, add_normalized_names
from tennis.serve_model import ServeReturnModel, is_tour_level
from tennis.simulator import simulate_match
from tennis.backtest import _is_retired

MIN_SERVE_GAMES = 40.0  # same gate as predict.py

SET_RE = re.compile(r"(\d)(\d)")  # '16 75 63' -> ('1','6'),('7','5'),('6','3')


def parse_score(row):
    """Return (sets_a, sets_b, total_games, games_a, games_b) or None.

    ManTennisData carries numeric sets/games columns (winner perspective);
    the score string is only a fallback.
    """
    try:
        sa, sb = int(row.get("winner_sets_won")), int(row.get("loser_sets_won"))
        ga, gb = int(row.get("winner_games_won")), int(row.get("loser_games_won"))
        if sa + sb >= 2 and ga + gb > 0:
            return sa, sb, ga + gb, ga, gb
    except (TypeError, ValueError):
        pass
    score = row.get("match_score")
    if not isinstance(score, str):
        return None
    # ManTennisData format: '16 75 63' = 1-6 7-5 6-3 (winner first per set)
    sets = [(a, b) for a, b in SET_RE.findall(score) if a.isdigit() and b.isdigit()]
    if not sets:
        return None
    ga = sum(int(a) for a, _ in sets)
    gb = sum(int(b) for _, b in sets)
    sa = sum(1 for a, b in sets if int(a) > int(b))
    sb = sum(1 for a, b in sets if int(b) > int(a))
    return sa, sb, ga + gb, ga, gb


def main():
    stats = load_atp_stats(range(2022, 2027))
    stats = add_normalized_names(stats, "winner_name", "loser_name")
    stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    serve = ServeReturnModel()
    # predictions only from 2024 on: two full seasons to warm ratings up
    warmup_until = "2024-01-01"

    buckets = defaultdict(lambda: [0, 0.0, 0.0])   # market -> [n, p_sum, hit_sum]
    n_scored = 0
    for s in stats.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        w_key, l_key = s.get("winner_key"), s.get("loser_key")
        if not w_key or not l_key:
            continue
        scored = None
        if str(s["tourney_date"])[:10] >= warmup_until and is_tour_level(s):
            as_of = s.get("tourney_date")
            if (serve.service_games(w_key, as_of=as_of) >= MIN_SERVE_GAMES
                    and serve.service_games(l_key, as_of=as_of) >= MIN_SERVE_GAMES):
                scored = parse_score(s)
            if scored:
                # neutral "A" perspective (deterministic coin flip): without
                # this, "A covers" is measured on the actual WINNER and the
                # calibration test is nonsense by construction
                flip = hash(w_key) % 2 == 1
                key_a, key_b = (l_key, w_key) if flip else (w_key, l_key)
                hold_a, hold_b = serve.expected_hold_probabilities(
                    key_a, key_b, s.get("surface") if s.get("surface") in ("Hard", "Clay", "Grass") else None,
                    as_of=as_of,
                )
                m = simulate_match(hold_a, hold_b, best_of=3)
                sa_w, sb_w, total_games, ga_w, gb_w = scored
                sa, sb = (sb_w, sa_w) if flip else (sa_w, sb_w)
                ga, gb = (gb_w, ga_w) if flip else (ga_w, gb_w)
                actual = {
                    "over_20.5": total_games > 20.5,
                    "over_21.5": total_games > 21.5,
                    "over_22.5": total_games > 22.5,
                    "over_2.5_sets": (sa + sb) > 2.5,
                    "A_-1.5_sets": sa == 2 and sb == 0,
                    "A_-3.5_games": (ga - gb) > 3.5,
                }
                preds = {
                    "over_20.5": m.over_games(20.5),
                    "over_21.5": m.over_games(21.5),
                    "over_22.5": m.over_games(22.5),
                    "over_2.5_sets": m.over_sets(2.5),
                    "A_-1.5_sets": m.correct_scores.get((2, 0), 0.0),
                    "A_-3.5_games": m.handicap_a(-3.5),
                }
                for k, p in preds.items():
                    b = round(p * 10) / 10
                    key = (k, b)
                    buckets[key][0] += 1
                    buckets[key][1] += p
                    buckets[key][2] += 1.0 if actual[k] else 0.0
                n_scored += 1
        if is_tour_level(s):
            serve.update_from_match_row(s)

    print(f"gescorte Matches (beide >= {MIN_SERVE_GAMES:.0f} Serve-Games, 2024+): {n_scored}\n")
    for market in ("over_20.5", "over_21.5", "over_22.5", "over_2.5_sets", "A_-1.5_sets", "A_-3.5_games"):
        print(f"--- {market}")
        print(f"{'bucket':>7} {'n':>6} {'p_avg':>7} {'empirie':>8} {'diff':>7}")
        brier_n, brier_sum = 0, 0.0
        for (mk, b), (n, p_sum, hit) in sorted(buckets.items()):
            if mk != market or n < 15:
                continue
            p_avg = p_sum / n
            emp = hit / n
            brier_n += n
            brier_sum += n * (p_avg - emp) ** 2  # rough grouped brier
            print(f"{b:>7.1f} {n:>6} {p_avg:>7.3f} {emp:>8.3f} {emp - p_avg:>+7.3f}")
        if brier_n:
            print(f"   grouped-brier={ (brier_sum / brier_n) ** 0.5:.4f} (RMS-Abweichung, kleiner=besser)\n")


if __name__ == "__main__":
    main()
