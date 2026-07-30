"""Rebuild the persisted tennis model state (ATP + WTA Elo, calibrators).

Usage:
    rebuild_state.py --force              always rebuild
    rebuild_state.py --if-stale-days 7    rebuild only when built_at is older

Exit code 0 always (unless the rebuild itself fails); prints whether a
rebuild happened so callers (daily automation) can log it.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.model_state import build_state, save_state, load_state, state_exists


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--if-stale-days", type=float, default=None)
    args = ap.parse_args()

    if not args.force and args.if_stale_days is not None and state_exists():
        state = load_state()
        age_days = (time.time() - state.built_at) / 86400.0
        if age_days < args.if_stale_days:
            print(f"State frisch ({age_days:.1f} Tage alt < {args.if_stale_days}) — kein Rebuild.")
            return 0
        print(f"State veraltet ({age_days:.1f} Tage >= {args.if_stale_days}) — Rebuild...")

    t0 = time.time()
    state = build_state(verbose=True)
    path = save_state(state)
    print(f"REBUILT in {time.time()-t0:.0f}s -> {path}")
    print(f"ATP-Kal: a={state.cal_a:.4f} b={state.cal_b:.4f} (n={state.cal_samples})")
    print(f"WTA-Kal: a={state.cal_wta_a:.4f} b={state.cal_wta_b:.4f} (n={state.cal_wta_samples})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
