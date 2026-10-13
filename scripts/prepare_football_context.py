#!/usr/bin/env python3
"""Inspect or prepare an explicit offline native football context inventory.

No provider calls, production-state writes, copies or activation. A preparation
file declares config, binding requests, code revision and three test windows.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context_models.contracts import ContextContractError, require_object
from context_models.football_readiness import inspect_football_readiness, prepare_football_context
from model_artifacts import canonical_bytes
from runtime_paths import RUNTIME_STATE_DIR, _assert_no_symlink_components, atomic_write_bytes

MAX_PLAN_BYTES = 512 * 1024


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-db", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.evaluate and not args.prepare:
            raise ContextContractError("evaluation requires explicit offline preparation")
        paths = []
        for path in (args.model_db, args.plan, args.output):
            if not path.is_absolute():
                raise ContextContractError("all offline preparation paths must be absolute")
            path = _assert_no_symlink_components(path)
            production = RUNTIME_STATE_DIR.absolute()
            if path == production or production in path.parents:
                raise ContextContractError("offline CLI cannot access configured production state")
            paths.append(path)
        db, plan_path, output = paths
        if len(set(paths)) != 3 or output.exists():
            raise ContextContractError("offline input and new report paths must be distinct; output must not exist")
        if plan_path.stat().st_size > MAX_PLAN_BYTES:
            raise ContextContractError("explicit preparation plan exceeds its input bound")
        plan = json.loads(plan_path.read_bytes())
        require_object(plan, {"config", "requests", "test_blocks", "code_revision"}, label="football preparation plan")
        if type(plan["requests"]) is not list or type(plan["test_blocks"]) is not list:
            raise ContextContractError("preparation requires declared inventory and fixed windows")
        blocks = tuple(tuple(datetime.fromisoformat(value) for value in block) for block in plan["test_blocks"])
        now = datetime.now(timezone.utc)
        kwargs = dict(test_blocks=blocks)
        if args.prepare:
            result = prepare_football_context(db, tuple(plan["requests"]), plan["config"], **kwargs,
                code_revision=plan["code_revision"], created_at=now, evaluate=args.evaluate)
        else:
            result = {"status": "inspected_not_activated", "readiness": inspect_football_readiness(
                db, tuple(plan["requests"]), plan["config"], **kwargs, as_of=now), "activated": False}
        raw = canonical_bytes(result)+b"\n"
        atomic_write_bytes(output, raw, replace_existing=False)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps({key: result[key] for key in ("status", "activated")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
