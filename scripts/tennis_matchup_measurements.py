"""Measurement only — no model changes.  Answers three questions with
walk-forward (strictly causal) evidence on tour-level matches 2015-2026:

M1  Lefty effect: does a left-hander beat his Elo expectation against
    right-handers?  (bias = mean(actual - expected) for the lefty)
M2  Environment: is hand-blind, environment-blind Elo mispriced on
    Hard Indoor vs Hard Outdoor?  (brier by environment)
M3  Style: net-approach rate as the only available style marker —
    is it stable per player, and does Elo misprice matchups vs
    high-net-approach opponents?

Run:  python scripts/tennis_matchup_measurements.py
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.data_loader import load_atp_stats, add_normalized_names  # noqa: E402
from tennis.elo import SurfaceElo  # noqa: E402
from tennis.serve_model import is_tour_level  # noqa: E402
from tennis.backtest import _is_retired  # noqa: E402

TOUR = {"gs", "1000", "atp500", "atp250", "og", "atpCup", "atpFinal"}


def brier(p, y):
    return (p - y) ** 2


def m4_calibrator_regimes():
    """F3: does the single Platt calibrator misfit one model regime?

    p_model is Elo-only when the serve gate fails (unknown players) and
    Elo+serve blended otherwise.  A stable regime bias would justify two
    calibrators.  Measured: the gap flips sign between windows -> noise,
    one calibrator stays.  (Production fit/score consistency verified by
    construction: build_state fits on the same mixture predict.py sees.)
    """
    from tennis.backtest import run_backtest

    for years in ((2021, 2022), (2023, 2024)):
        rep = run_backtest(odds_years=years, stats_years=range(2015, 2027),
                           tours=("atp",), serve_weight=0.3, recalibrate=True)
        f = rep.to_frame()
        f["regime"] = f["p_serve"].notna().map({True: "blended", False: "elo_only"})
        print(f"\n=== M4: Kalibrator-Regime-Mischung {years} ===")
        for regime, d in f.groupby("regime"):
            y = d["y_alpha"].astype(float)
            p = d["p_alpha"].clip(1e-6, 1 - 1e-6)
            print(f"  {regime:9s}: n={len(d):5d}  brier={brier(p, y).mean():.4f}"
                  f"  base_rate={y.mean():.4f}  mean_p={p.mean():.4f}"
                  f"  gap={p.mean() - y.mean():+.4f}")


def main():
    players = pd.read_csv(
        Path(__file__).resolve().parent.parent / "tennis" / "data" / "atp_players.csv",
        usecols=["code", "handedness"],
    )
    hand = dict(zip(players["code"], players["handedness"]))
    print(f"Handedness: {len(hand)} Spieler, "
          f"Linkshaender: {sum(1 for v in hand.values() if v == 'Left-Handed')}")

    stats = load_atp_stats(range(2015, 2027))
    stats = add_normalized_names(stats, "winner_name", "loser_name")
    stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)
    tour = stats[stats["series_category_id"].isin(TOUR)]
    print(f"tour-level matches: {len(tour)}")

    elo = SurfaceElo()
    # M1: (lefty_vs_righty) -> [n, sum(actual-lefty-win - p_lefty), sum p]
    m1 = defaultdict(lambda: [0, 0.0])
    m1_hand_cov = [0, 0]
    # M2: environment -> [n, brier_sum]
    m2 = defaultdict(lambda: [0, 0.0])
    # M3: net rates per player (career, for stability), and Elo error vs
    # opponent style bucket
    net_pts = defaultdict(lambda: [0.0, 0.0])   # player -> [net_total, pts_total]
    m3_rows = []  # (p_fav_won, p_fav, opp_net_rate_pre)

    for s in tour.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        w_key, l_key = s.get("winner_key"), s.get("loser_key")
        if not w_key or not l_key:
            continue
        surface = s.get("surface")
        env = s.get("indoor_outdoor")

        p_w = elo.win_probability(w_key, l_key, surface)

        # M1 ----------------------------------------------------------------
        hw, hl = hand.get(s.get("winner_code")), hand.get(s.get("loser_code"))
        m1_hand_cov[1] += 1
        if (isinstance(hw, str) and isinstance(hl, str)
                and hw != hl and "Handed" in hw and "Handed" in hl):
            m1_hand_cov[0] += 1
            # p of the LEFTY winning
            if hw == "Left-Handed":
                p_lefty, y_lefty = p_w, 1.0
            else:
                p_lefty, y_lefty = 1.0 - p_w, 0.0
            key = ("ALL",) if surface not in ("Hard", "Clay", "Grass") else (surface,)
            m1[key][0] += 1
            m1[key][1] += y_lefty - p_lefty
            m1[("ALL",)][0] += 0  # counted separately below
        # M2 ----------------------------------------------------------------
        if surface == "Hard":
            bucket = "Indoor" if env == "Indoor" else "notIndoor"
            m2[bucket][0] += 1
            m2[bucket][1] += brier(p_w, 1.0)  # 1 = winner actually won
        # M3 ----------------------------------------------------------------
        w_net = s.get("win_net_points_total")
        w_tot = s.get("win_total_points_total")
        l_net = s.get("los_net_points_total")
        l_tot = s.get("los_total_points_total")
        try:
            if w_net == w_net and w_tot == w_tot and float(w_tot) > 0:
                net_pts[w_key][0] += float(w_net)
                net_pts[w_key][1] += float(w_tot)
                opp_rate = (net_pts[l_key][0] / net_pts[l_key][1]
                            if net_pts[l_key][1] > 2000 else None)
                if opp_rate is not None:
                    m3_rows.append((p_w, opp_rate))
            if l_net == l_net and l_tot == l_tot and float(l_tot) > 0:
                net_pts[l_key][0] += float(l_net)
                net_pts[l_key][1] += float(l_tot)
        except (TypeError, ValueError):
            pass

        elo.update(w_key, l_key, surface)

    print("\n=== M1: Linkshaender vs Elo-Erwartung (nur L-vs-R-Matches) ===")
    cov = m1_hand_cov
    print(f"Hand-Abdeckung: {cov[0]}/{cov[1]} Matches ({cov[0]/max(cov[1],1):.1%})")
    for key in sorted(m1, key=lambda k: -m1[k][0]):
        n, bias = m1[key]
        if n < 500:
            continue
        se = math.sqrt(0.25 / n)
        print(f"  {key[0]:6s}: n={n:6d}  bias={bias/n:+.4f}  (SE {se:.4f})")

    print("\n=== M1b: individuelle Rechtshaender-Schwaeche vs Linkshaender ===")
    print("(korrigierte Fassung — erste Version zaehlte linkshaendige")
    print("Verlierer ins Rechtshaender-Bucket und Rechtshaender nur bei")
    print("Siegen: komplettes Selektions-Artefakt, z-sd 3.58. Wachter:")
    print("die Tabelle darf NUR Rechtshaender enthalten.)")
    elo2 = SurfaceElo()
    vs_l = defaultdict(lambda: [0, 0.0])   # righty -> [n vs lefty, sum(actual - expected)]
    for s in tour.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        w_key, l_key = s.get("winner_key"), s.get("loser_key")
        if not w_key or not l_key:
            continue
        p_w = elo2.win_probability(w_key, l_key, s.get("surface"))
        hw, hl = hand.get(s.get("winner_code")), hand.get(s.get("loser_code"))
        if (isinstance(hw, str) and isinstance(hl, str)
                and hw != hl and "Handed" in hw and "Handed" in hl):
            if hw == "Left-Handed":
                # loser is the righty: actual 0, expectation 1 - p_w
                vs_l[l_key][0] += 1
                vs_l[l_key][1] += 0.0 - (1.0 - p_w)
            else:
                # winner is the righty: actual 1, expectation p_w
                vs_l[w_key][0] += 1
                vs_l[w_key][1] += 1.0 - p_w
        elo2.update(w_key, l_key, s.get("surface"))

    # regression guard for the exact bug class above: the table must
    # contain ONLY right-handers (a lefty in it means leakage)
    code_by_name = {}
    for s in tour.to_dict("records"):
        code_by_name.setdefault(s.get("winner_key"), s.get("winner_code"))
        code_by_name.setdefault(s.get("loser_key"), s.get("loser_code"))
    leaked = [
        k for k in vs_l
        if hand.get(code_by_name.get(k)) == "Left-Handed"
    ]
    assert not leaked, f"Linkshaender im Rechtshaender-Bucket: {leaked}"

    rows = sorted(
        ((k, v[0], v[1] / v[0]) for k, v in vs_l.items() if v[0] >= 60),
        key=lambda r: r[2],
    )
    print(f"Rechtshaender mit 60+ Matches vs Linkshaender: {len(rows)}")
    for k, n, bias in rows[:4] + rows[-4:]:
        se = math.sqrt(0.25 / n)
        print(f"  {k:26s} n={n:3d}  bias={bias:+.3f}  (z={bias/se:+.1f})")
    if rows:
        zs = [b / math.sqrt(0.25 / n) for _, n, b in rows]
        sd = (sum((z - sum(zs) / len(zs)) ** 2 for z in zs) / len(zs)) ** 0.5
        print(f"  z-Streuung: sd={sd:.2f} (Nullhypothese reiner Noise: 1.00)")

    print("\n=== M2: Elo-Brier auf Hard nach Umgebung ===")
    for bucket, (n, b) in sorted(m2.items()):
        print(f"  {bucket:10s}: n={n:6d}  brier={b/n:.4f}")

    print("\n=== M3: Netz-Angriffsrate ===")
    rates = [v[0] / v[1] for v in net_pts.values() if v[1] > 5000]
    if rates:
        r = pd.Series(rates)
        print(f"  Spieler n={len(r)}, Netzrate p10={r.quantile(.1):.3f} "
              f"p50={r.quantile(.5):.3f} p90={r.quantile(.9):.3f}")
    if m3_rows:
        df = pd.DataFrame(m3_rows, columns=["p_w", "opp_net"])
        df["tercile"] = pd.qcut(df["opp_net"], 3, labels=["low", "mid", "high"])
        g = df.groupby("tercile", observed=True).apply(
            lambda d: pd.Series({
                "n": len(d),
                "brier_elo": ((d["p_w"] - 1.0) ** 2).mean(),
                "opp_net_mean": d["opp_net"].mean(),
            }), include_groups=False)
        print("  Elo-Brier des Siegers nach GEGNER-Netzrate-Terzil:")
        print(g.round(4).to_string())


if __name__ == "__main__":
    main()
    m4_calibrator_regimes()
