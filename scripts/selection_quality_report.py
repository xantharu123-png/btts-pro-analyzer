"""Print a read-only selection-quality report from the dedicated evidence DB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forecast_evidence import build_quality_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Dedicated forecast evidence SQLite database")
    parser.add_argument("--as-of", help="Optional timezone-aware historical reporting cutoff")
    args = parser.parse_args(argv)
    report = build_quality_report(args.db, as_of=args.as_of)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
