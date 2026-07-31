"""A/B: serve/return accumulators — career sums vs exponential decay.

Same walk-forward protocol, same serve_weight as production (0.3),
same evaluation window (ATP 2023+2024, ratings warmed from 2015).
Only difference: ``serve_half_life_days``.

Result (2023+2024 and 2021+2022, ~5k matches each): decay beats career
sums on brier/logloss in BOTH windows; ROI at the >=12% gate is a wash
within noise (+-5pp).  365d chosen as production default — best brier in
the recent window, best >=8% ROI there, largest effective sample.

Run:  python scripts/tennis_decay_ab.py
"""
from __future__ import annotations

import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.backtest import run_backtest  # noqa: E402

YEARS = (2023, 2024)
STATS = range(2015, 2027)


def run(label, half_life):
    t0 = time.time()
    rep = run_backtest(
        odds_years=YEARS,
        stats_years=STATS,
        tours=("atp",),
        serve_weight=0.3,
        serve_half_life_days=half_life,
    )
    cal = rep.calibration()
    print(f"\n=== {label}  ({time.time() - t0:.0f}s, n={cal['n']}) ===")
    print(
        f"brier raw/cal/market:  {cal['brier_raw']} / {cal['brier_cal']} / {cal['brier_market']}\n"
        f"logloss raw/cal/market: {cal['logloss_raw']} / {cal['logloss_cal']} / {cal['logloss_market']}\n"
        f"pick accuracy: {cal['pick_accuracy']}   gate coverage: {cal['gate_coverage']}"
    )
    print(rep.summary((0.05, 0.08, 0.10, 0.12)).to_string(index=False))
    return cal


if __name__ == "__main__":
    run("A: career sums (half_life=None)", None)
    run("B: decay half_life=180d", 180.0)
    run("C: decay half_life=365d (PRODUCTION)", 365.0)
