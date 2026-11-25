"""Print a read-only retrospective for completed local calendar days."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selection_performance import build_selection_performance_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--from-day")
    parser.add_argument("--through-day")
    parser.add_argument("--matchday", metavar="YYYY-MM-DD",
                        help="One completed Zurich day, using one archived Wettfinder surface; requires --history-db")
    parser.add_argument("--timezone", default="Europe/Zurich")
    parser.add_argument("--unit-stake", type=float, default=1.0, help="Hypothetical equal stake, not actual account transactions")
    parser.add_argument("--as-of", help="Timezone-aware reporting cutoff")
    parser.add_argument("--history-db", type=Path, help="Use prospectively archived UI selections, not the internal pool")
    parser.add_argument("--surface", help="Optional publication surface; requires --history-db")
    parser.add_argument("--market-review", action="store_true",
                        help="Compare archived Wettfinder markets and first cards for up to 31 completed Zurich days")
    args = parser.parse_args(argv)
    try:
        if args.matchday:
            from consumer_tip_performance import WETTFINDER_SURFACES
            if args.from_day or args.through_day or args.timezone != "Europe/Zurich" or not args.history_db:
                parser.error("--matchday requires --history-db and one Zurich day (no date range)")
            args.from_day = args.through_day = args.matchday
            args.surface = args.surface or WETTFINDER_SURFACES[0]
            if args.surface not in WETTFINDER_SURFACES:
                parser.error("--matchday requires one Wettfinder surface: " + ", ".join(WETTFINDER_SURFACES))
        elif not args.from_day or not args.through_day:
            parser.error("provide --from-day and --through-day, or --matchday with --history-db")
        if args.surface and not args.history_db:
            parser.error('--surface requires --history-db')
        options = dict(from_day=args.from_day, through_day=args.through_day,
            timezone_name=args.timezone, unit_stake=args.unit_stake, as_of=args.as_of)
        if args.market_review:
            from consumer_tip_market_review import build_market_review
            if not args.history_db or args.timezone != "Europe/Zurich":
                parser.error("--market-review requires --history-db and Zurich calendar days")
            report = build_market_review(args.history_db, args.db, surface=args.surface, **options)
        elif args.history_db:
            from consumer_tip_performance import build_consumer_tip_performance_report
            report = build_consumer_tip_performance_report(args.history_db, args.db, surface=args.surface, **options)
            if args.matchday:
                keys = ("from_day", "through_day", "timezone", "as_of", "surface_filter", "matchday",
                        "database_present", "history_database_present", "publication_count", "incomplete_publications",
                        "unique_archived_selections", "linkage_gap_reasons", "integrity_error_count", "integrity_errors")
                report = {"schema_version": "wettfinder-matchday-v1", **{key: report[key] for key in keys}}
        else:
            report = build_selection_performance_report(args.db, **options)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
