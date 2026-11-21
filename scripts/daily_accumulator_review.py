"""Fit a prospective whole-slip calibration or review its preregistered holdout.

The two input databases are always read-only. --output must be a NEW file;
no existing customer artifact is automatically overwritten or activated.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from daily_accumulator_quality import ARM, POLICY, ZONE, _midnight, fit, review, settled_receipts
from daily_accumulator_receipts import load_day


def _originals(path, first, last, *, arm=ARM):
    if not 0 <= (last-first).days <= 365:
        raise ValueError("provide a 1–366 day window")
    while first <= last:
        yield from load_day(path, day=first, policy=POLICY, arm=arm)
        first += timedelta(days=1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="stage", required=True)
    training = sub.add_parser("fit", help="freeze parameters using completed originals and register future test dates")
    training.add_argument("--training-from", type=date.fromisoformat, required=True)
    training.add_argument("--test-from", type=date.fromisoformat, required=True)
    training.add_argument("--test-through", type=date.fromisoformat, required=True)
    scoring = sub.add_parser("review", help="after the complete holdout plus 7 days, grade exactly those slips")
    scoring.add_argument("--model", type=Path, required=True)
    scoring.add_argument("--arm", choices=("candidate","reference"), default="candidate")
    for cmd in (training, scoring):
        cmd.add_argument("--receipts", type=Path, required=True)
        cmd.add_argument("--evidence", type=Path, required=True)
        cmd.add_argument("--output", type=Path, required=True, help="new path; never overwrites or uploads")
    args = parser.parse_args(argv)
    # Intentionally no backdating parameter. An artifact was available only
    # after this command ran, not at some retrospectively convenient instant.
    clock = datetime.now(timezone.utc)
    try:
        if args.output.exists() or not (args.receipts.is_file() and args.evidence.is_file()):
            raise ValueError("both existing input archives and a new output path are required")
        if args.stage == "fit":
            scopes = _originals(args.receipts, args.training_from, clock.astimezone(ZONE).date()-timedelta(days=1))
            obj = fit(settled_receipts(scopes, args.evidence, known_at=clock),
                      issued_at=clock, test_from=args.test_from, test_through=args.test_through)
            if not obj["groups"]:
                raise ValueError("insufficient settled originals for a prospective fit")
        else:
            model = json.loads(args.model.read_text(encoding="utf-8"))
            first, last = date.fromisoformat(model["test_from"]), date.fromisoformat(model["test_through"])
            # Same grades on every rerun: never use a newly observed later
            # result to improve a failed validation after opening its data.
            fixed_cutoff = _midnight(last+timedelta(days=8))
            if clock < fixed_cutoff:
                raise ValueError("validation is not mature")
            records = _originals(args.receipts, first, last, arm=args.arm)
            obj = review(model, settled_receipts(records, args.evidence, known_at=fixed_cutoff),
                         issued_at=clock, arm=args.arm)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(obj, handle, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps(dict(stage=obj["kind"], groups=len(obj["groups"]), passed=sum(
            g.get("passed", False) for g in obj["groups"].values()), output=str(args.output))))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f"Daily accumulator review: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
