#!/usr/bin/env python3
"""Evaluate an explicit offline A1/B1 dataset; never publish an active model.

The frozen experiment names the source-resolved dataset. Free --results or
--distribution-losses claims are deliberately not accepted by this interface.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context_models.contracts import ContextContractError, require_digest
from context_models.dataset import _reader
from context_models.evaluator import evaluate_experiment
from model_artifacts import canonical_bytes
from runtime_paths import RUNTIME_STATE_DIR, _assert_no_symlink_components, atomic_write_bytes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-db", required=True, type=Path)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.model_db.is_absolute() or not args.output_dir.is_absolute():
            raise ContextContractError("offline input and output paths must be explicit absolute locations")
        model_db = _assert_no_symlink_components(args.model_db)
        output_dir = _assert_no_symlink_components(args.output_dir)
        production = RUNTIME_STATE_DIR.absolute()
        if any(path == production or production in path.parents for path in (model_db, output_dir)):
            raise ContextContractError("offline research CLI cannot write configured production state")
        require_digest(args.experiment, "frozen experiment")
        # Bound a research invocation, not an empirical quality threshold. The
        # full 200-event policy still applies; large corpora need explicit batch
        # preparation, not an unbounded accidental production-wide evaluation.
        with _reader(model_db) as connection:
            count = connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-training-case-v1'").fetchone()[0]
            if count > 10000:
                raise ContextContractError("offline research database exceeds 10000-case invocation bound")
        if output_dir.exists() and not output_dir.is_dir():
            raise ContextContractError("explicit report directory is not a directory")
        result = evaluate_experiment(model_db, args.experiment, evaluated_at=datetime.now(timezone.utc))
        target = output_dir/(result["digest"]+".json")
        raw = canonical_bytes(result)+b"\n"
        if target.exists():
            if target.read_bytes() != raw:
                raise ContextContractError("immutable report output already contains different bytes")
        else:
            atomic_write_bytes(target, raw, replace_existing=False)
    except Exception as exc:
        # No arbitrary path/source text, full payload or credentials on stdout.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps({"status": "evaluated_not_activated", "report_hash": result["digest"],
                      "approval_count": len(result["approvals"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
