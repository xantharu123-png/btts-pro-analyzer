"""One-off: REAL WTA backtest (Elo-only) after the URL fix.

The earlier 'WTA' backtest silently ran on ATP data (2024w.xlsx now
301-redirects to the ATP file). This rerun decides WTA release gates.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.backtest import run_backtest

rep = run_backtest(
    odds_years=range(2019, 2025),
    stats_years=range(2010, 2027),
    tours=("wta",),
    serve_weight=0.0,      # no WTA boxscore feed -> Elo-only
    recalibrate=True,
)
cal = rep.calibration()
print(f"n={cal['n']}  brier_cal={cal['brier_cal']}  brier_markt={cal['brier_market']}  "
      f"pick_acc={cal['pick_accuracy']:.1%}  gate_coverage={cal['gate_coverage']:.1%}")

print("\nROI nach Edge-Schwelle (gated):")
print(rep.summary((0.0, 0.05, 0.08, 0.10, 0.12, 0.15)).to_string(index=False))

frame = rep.to_frame()
bets = frame[(frame["chosen_edge"] >= 0.12) & frame["gated"]]
print("\nROI bei Edge >= 12% nach Belag:")
for s, grp in bets.groupby("surface"):
    pnl = grp.apply(lambda r: (r["chosen_odds"] - 1.0) if r["bet_won"] else -1.0, axis=1)
    print(f"  {s:6s}: n={len(grp):5d}  win={grp['bet_won'].mean():.1%}  ROI={pnl.mean():+.1%}")
if len(bets):
    pnl = bets.apply(lambda r: (r["chosen_odds"] - 1.0) if r["bet_won"] else -1.0, axis=1)
    print(f"  GESAMT: n={len(bets)}  ROI={pnl.mean():+.1%}")
