#!/usr/bin/env python3
"""Read-only context check; historical audit or explicit operational release check."""

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
    parser.add_argument("--sealed-file", action="store_true",
                        help="Explicit Linux root-sealed file input (never a live database)")
    parser.add_argument("--deployment-check", action="store_true",
                        help="Storage and active model startup only; no historical replay or model approval")
    parser.add_argument("--backup-root", type=Path, help="Optional explicit application root for configured-path discovery verification")
    arguments = parser.parse_args(argv)
    try:
        relative = None if arguments.backup_root is None else verify_context_backup_location(
            arguments.database, application_root=arguments.backup_root)
        verifier = verify_context_database
        if arguments.deployment_check:
            from context_runtime_deployment import verify_context_deployment
            verifier = verify_context_deployment
        report = verifier(arguments.database,
            input_mode="sealed_file" if arguments.sealed_file else "memory")
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
    success = report["verification_level"] in {"structural", "deployment"}
    print(json.dumps({"status": "verified" if success else "incomplete", **report}, sort_keys=True))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
