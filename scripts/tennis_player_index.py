"""Explicit local operator interface. Never loops across bounded invocations."""
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_tennis_index import IndexBudgetExceeded
from context_tennis_index_build import build_index, disable_index, index_status, initialize_index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "initialize", "build", "status", "disable"))
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--seconds", type=float, default=45)
    args = parser.parse_args(argv)
    if (args.path is None) == (args.db is None):
        parser.error("supply exactly one database path: --db PATH")
    path = args.db if args.db is not None else args.path
    try:
        if args.command == "build":
            result = build_index(path, seconds=args.seconds)
            print(json.dumps(asdict(result), sort_keys=True))
            return 0 if result.status == "ready" else 3
        if args.command == "status":
            state = index_status(path)
            print(json.dumps(asdict(state) if state else {"status": "absent"}, sort_keys=True))
            return 0 if state is not None and state.status == "ready" else 3
        (initialize_index if args.command in {"init", "initialize"} else disable_index)(path)
        print(json.dumps({"status": "initialized" if args.command in {"init", "initialize"} else "disabled"}))
        return 0
    except IndexBudgetExceeded as exc:
        print(json.dumps({"error": str(exc), "status": "incomplete"}), file=sys.stderr)
        return 3
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc), "status": "invalid"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
