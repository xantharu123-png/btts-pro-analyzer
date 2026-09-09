#!/usr/bin/env python3
"""Read-only context storage check; never a deployment or empirical approval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context_runtime import verify_context_database, verify_context_backup_location
from context_models.contracts import digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, help="Optional explicit application root for configured-path discovery verification")
    arguments = parser.parse_args(argv)
    try:
        relative = None if arguments.backup_root is None else verify_context_backup_location(
            arguments.database, application_root=arguments.backup_root)
        report = verify_context_database(arguments.database)
        if relative is not None:
            report["backup_location_verified"] = True
    except Exception as exc:
        # Errors may originate in a path, payload or source string. Print a
        # stable class only; never echo arbitrary stored data or credentials.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}, sort_keys=True))
        return 1
    # Arbitrary stored slot names are data too. The API retains the exact map
    # for trusted callers; CLI diagnostics expose only its identity and count.
    slots = report.pop("active_slots")
    report["active_slots_hash"] = digest(slots)
    report["active_slot_count"] = len(slots)
    print(json.dumps({"status": "verified" if report["verification_level"] == "structural" else "incomplete", **report}, sort_keys=True))
    return 0 if report["verification_level"] == "structural" else 2


if __name__ == "__main__":
    raise SystemExit(main())
