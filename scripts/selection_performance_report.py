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
    parser.add_argument("--from-day", required=True)
    parser.add_argument("--through-day", required=True)
    parser.add_argument("--timezone", default="Europe/Zurich")
    parser.add_argument("--unit-stake", type=float, default=1.0, help="Hypothetical equal stake, not actual account transactions")
    parser.add_argument("--as-of", help="Timezone-aware reporting cutoff")
    parser.add_argument("--history-db", type=Path, help="Use prospectively archived UI selections, not the internal pool")
    parser.add_argument("--surface", help="Optional publication surface; requires --history-db")
    args = parser.parse_args(argv)
    try:
        if args.surface and not args.history_db:
            parser.error('--surface requires --history-db')
        options = dict(from_day=args.from_day, through_day=args.through_day,
            timezone_name=args.timezone, unit_stake=args.unit_stake, as_of=args.as_of)
        if args.history_db:
            from consumer_tip_performance import build_consumer_tip_performance_report
            report = build_consumer_tip_performance_report(args.history_db, args.db, surface=args.surface, **options)
        else:
            report = build_selection_performance_report(args.db, **options)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
