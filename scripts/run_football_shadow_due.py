"""Run the football Shadow pipeline only when work is due.

This is the systemd/cron entrypoint.  The managed KIMI automation used its
condition hook before calling ``shadow_clv_automation.run``; a plain timer
must preserve that API-budget guard explicitly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shadow_clv_automation as shadow  # noqa: E402


def main() -> int:
    if not shadow.should_fire(None):
        print(json.dumps({"status": "idle", "reason": "no_shadow_work_due"}))
        return 0

    result = shadow.run(
        {
            "input": {
                "league_ids": [],
                "max_fixtures": 60,
                "force_schedule": False,
            }
        }
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
