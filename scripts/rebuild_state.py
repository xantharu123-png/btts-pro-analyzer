"""Rebuild the persisted tennis model state (ATP + WTA Elo, calibrators).

Usage:
    rebuild_state.py --force              always rebuild
    rebuild_state.py --if-stale-days 7    check build age and ATP tournament-start coverage
    rebuild_state.py --force --refresh-data  revalidate active sources (default)
    rebuild_state.py --force --no-refresh-data  explicitly use cached sources

Exit code 0 always (unless the rebuild itself fails); prints whether a
rebuild happened so callers (daily automation) can log it.
"""
import argparse
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.model_state import build_state, save_state, load_state, state_exists


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--if-stale-days", type=float, default=None)
    ap.add_argument("--refresh-data", action=argparse.BooleanOptionalAction, default=True,
                    help="Revalidate active-year sources before rebuilding (default: enabled)")
    args = ap.parse_args()

    if not args.force and args.if_stale_days is not None and state_exists():
        state = load_state()
        age_days = (time.time() - state.built_at) / 86400.0
        try:
            coverage_days = (datetime.fromtimestamp(time.time(), timezone.utc).date() - date.fromisoformat(state.stats_through)).days
        except (TypeError, ValueError):
            coverage_days = float("inf")
        print(f"ATP-Turnierstart-Abdeckung: {state.stats_through} (kein letzter Spielzeitpunkt)")
        if 0 <= age_days < args.if_stale_days and 0 <= coverage_days < args.if_stale_days:
            print(f"State und Abdeckungsproxy innerhalb {args.if_stale_days} Tagen — kein Rebuild.")
            return 0
        print(f"Rebuild: State-Alter {age_days:.1f} Tage, ATP-Turnierstart-Proxy {coverage_days} Tage.")

    t0 = time.time()
    try:
        state = build_state(verbose=True, **({"refresh_training_data": True} if args.refresh_data else {}))
        path = save_state(state)
    except Exception as exc:
        label = "REFRESH_FAILED" if args.refresh_data else "REBUILD_FAILED"
        print(f"{label}: {type(exc).__name__}; bisheriger Modellstand bleibt erhalten.")
        return 1
    print(f"REBUILT in {time.time()-t0:.0f}s -> {path}")
    print(f"ATP-Turnierstart-Abdeckung: {state.stats_through}; aktive Quellen revalidiert={args.refresh_data}")
    print(f"ATP-Kal: a={state.cal_a:.4f} b={state.cal_b:.4f} (n={state.cal_samples})")
    print(f"WTA-Kal: a={state.cal_wta_a:.4f} b={state.cal_wta_b:.4f} (n={state.cal_wta_samples})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
