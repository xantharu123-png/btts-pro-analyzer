"""Blueprint Automation runner: e-sports shadow scan.

Logs Subgraph-ELO candidates for live/upcoming matches and settles open
predictions against finished results. Follows the same managed-runner
convention as shadow_clv_automation.py: entrypoint ``run(ctx)`` returning
{"artifact": summary}, plus DAIMON_BLUEPRINT_AUTOMATION_OUTPUT_FILE dump.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
os.chdir(PROJECT_DIR)  # config.ini / esports_shadow.db relativ zur App

from esports_shadow import run_shadow_scan  # noqa: E402


def run(ctx=None):
    """Managed runner entrypoint: ein Shadow-Scan + Settlement-Durchlauf."""
    summary = run_shadow_scan()
    wrapper = {"artifact": summary}
    output_file = os.environ.get("DAIMON_BLUEPRINT_AUTOMATION_OUTPUT_FILE")
    if output_file:
        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(wrapper, handle)
    print(json.dumps(wrapper, ensure_ascii=False, indent=2))
    return wrapper


if __name__ == "__main__":
    run()
