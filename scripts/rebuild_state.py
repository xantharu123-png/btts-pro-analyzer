"""Rebuild and independently publish ATP/WTA tennis model artifacts.

Usage:
    rebuild_state.py --force              always rebuild
    rebuild_state.py --if-stale-days 7    check build age and ATP tournament-start coverage
    rebuild_state.py --force --refresh-data  revalidate active sources (default)
    rebuild_state.py --force --no-refresh-data  explicitly use cached sources

Exit 0 only if both tours are published or retained fresh. Partial/failed
refreshes return 1. The legacy combined pickle writer is explicit opt-in.
"""
import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.model_state import build_state, save_state, load_state, state_exists
from tennis.tour_state import build_tour_state, refresh_tours
from runtime_paths import CONTEXT_MODEL_DB_PATH


def _compact_serve_diagnostics(diagnostics: dict) -> dict:
    fields = (
        "admitted", "skipped", "admitted_match_count", "skipped_match_count",
        "admitted_tournament_count", "skipped_tournament_count",
        "unknown_match_identity", "unknown_tournament_identity",
        "unknown_year", "reasons",
        "admitted_years", "skipped_years",
    )
    return {
        phase: {name: summary[name] for name in fields if name in summary}
        for phase, summary in diagnostics.items()
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--if-stale-days", type=float, default=None)
    ap.add_argument("--legacy-combined", action="store_true",
                    help="Explicitly use the legacy combined pickle writer")
    ap.add_argument("--refresh-data", action=argparse.BooleanOptionalAction, default=True,
                    help="Revalidate active-year sources before rebuilding (default: enabled)")
    args = ap.parse_args()

    if not args.legacy_combined:
        cutoff = datetime.fromtimestamp(time.time(), timezone.utc)
        diagnostics_by_tour = {}
        def build(tour):
            diagnostics = {}
            diagnostics_by_tour[tour] = diagnostics
            return build_tour_state(
                tour, as_of=cutoff, refresh_training_data=args.refresh_data,
                diagnostics=diagnostics,
            )
        try:
            result = refresh_tours(
                path=CONTEXT_MODEL_DB_PATH, as_of=cutoff,
                builder=build,
                if_stale_days=None if args.force else args.if_stale_days,
            )
        except Exception as exc:
            print(f"REFRESH_FAILED: {type(exc).__name__}; bisherige Tour-Artefakte bleiben erhalten.")
            return 1
        for tour, record in result["tours"].items():
            print(f"{tour}: {record['status']}; artifact_hash={record['artifact_hash']}; "
                  f"built_at={record['built_at']}; training_cutoff={record['training_cutoff']}; "
                  f"{record['stats_through_kind']}={record['stats_through']}; "
                  f"error_type={record['error_type']}")
            if tour in diagnostics_by_tour:
                compact = _compact_serve_diagnostics(diagnostics_by_tour[tour])
                print(f"{tour} serve_admission=" + json.dumps(
                    compact, ensure_ascii=True, separators=(",", ":"), sort_keys=True,
                ))
        print(f"REFRESH_{result['status'].upper()}; Datenrefresh angefordert={args.refresh_data}")
        return 0 if result["status"] == "complete" else 1

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
