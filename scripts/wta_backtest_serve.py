"""WTA backtest WITH the serve/return model (Tennis Abstract box scores).

Design: Elo warms up on 2010-2024 odds-file results (odds-blind), the
serve model learns through 2024 on TA box scores, and ONLY 2025+ rows
are scored (score_from) — a true out-of-sample window.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.backtest import run_backtest

rep = run_backtest(
    odds_years=range(2010, 2027),
    stats_years=range(2010, 2027),
    tours=("wta",),
    serve_weight=0.3,
    score_from="2025-01-01",
    recalibrate=True,
)
cal = rep.calibration()
print(f"n={cal['n']}  brier_cal={cal['brier_cal']}  brier_markt={cal['brier_market']}  "
      f"pick_acc={cal['pick_accuracy']:.1%}  gate_coverage={cal['gate_coverage']:.1%}")

print("\nROI nach Edge-Schwelle (gated):")
print(rep.summary((0.0, 0.05, 0.08, 0.10, 0.12, 0.15)).to_string(index=False))

frame = rep.to_frame()
print("\np_serve-Abdeckung der gescorten Rows:", f"{frame['p_serve'].notna().mean():.1%}")
bets = frame[(frame["chosen_edge"] >= 0.12) & frame["gated"] & frame["p_serve"].notna()]
print("\nROI bei Edge >= 12% nach Belag (nur Rows MIT Serve-Modell):")
for s, grp in bets.groupby("surface"):
    pnl = grp.apply(lambda r: (r["chosen_odds"] - 1.0) if r["bet_won"] else -1.0, axis=1)
    print(f"  {s:6s}: n={len(grp):4d}  win={grp['bet_won'].mean():.1%}  ROI={pnl.mean():+.1%}")
if len(bets):
    pnl = bets.apply(lambda r: (r["chosen_odds"] - 1.0) if r["bet_won"] else -1.0, axis=1)
    print(f"  GESAMT: n={len(bets)}  ROI={pnl.mean():+.1%}")
for thr in (0.08, 0.10, 0.12, 0.15):
    b = frame[(frame.chosen_edge >= thr) & frame.gated & frame.p_serve.notna() & (frame.surface == "Hard")]
    if len(b):
        pnl = b.apply(lambda r: (r["chosen_odds"] - 1.0) if r["bet_won"] else -1.0, axis=1)
        print(f"  Hard @{thr:>4.0%}: n={len(b):4d}  ROI={pnl.mean():+.1%}")
