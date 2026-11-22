"""Re-sync the local API-Football budget ledger with the provider's account status.

One governed account-status check, not a sport scan. Ordinary fixture
headers can lower the estimate but cannot restore a same-plan balance.
The automatic variant only runs for a contradictory protected reserve.

    /opt/betboy/venv/bin/python scripts/api_budget_resync.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_budget import (  # noqa: E402
    APIBudgetError, APIBudgetExceeded, APIBudgetPriority, FOOTBALL_ROLLOVER_STATUS_LABEL,
    active_football_account_usage, api_football_get, get_api_budget_governor,
)
from requests import RequestException  # noqa: E402
from config_loader import load_app_config  # noqa: E402

STATUS_URL = "https://v3.football.api-sports.io/status"


def check_rollover_if_needed() -> None:
    """Opportunistic account check in the scheduled worker, never from a viewer."""
    try:
        key = load_app_config(config_path=ROOT / "config.ini").api_football_key
        if not key:
            return
        governor = get_api_budget_governor()
        before = governor.snapshot(api_key=key)
        if (before.observed_remaining is None
                or not before.critical_floor < before.remaining_estimate
                <= before.background_reserve < before.observed_remaining):
            return
        response = api_football_get(
            STATUS_URL, headers={"x-apisports-key": key}, timeout=8,
            priority=APIBudgetPriority.CRITICAL, label=FOOTBALL_ROLLOVER_STATUS_LABEL,
        )
        after = governor.snapshot(api_key=key)
        result = "restored" if after.remaining_estimate > after.background_reserve else "reserve_protected"
        print(f"football_budget_status={result} http={response.status_code} "
              f"remaining={after.remaining_estimate}", file=sys.stderr)
    except APIBudgetExceeded:
        # The governor atomically rechecks eligibility and one attempt per UTC day.
        return
    except (APIBudgetError, RequestException, OSError, ValueError) as exc:
        # Never delay later jobs with a retry, or skip the actual Shadow work.
        print(f"football_budget_status=unavailable type={type(exc).__name__}", file=sys.stderr)


def main() -> int:
    config = load_app_config(config_path=ROOT / "config.ini")
    key = config.api_football_key
    if not key:
        print(json.dumps({"status": "error", "reason": "api_football_key_missing"}))
        return 1
    governor = get_api_budget_governor()
    before = governor.snapshot(api_key=key)
    try:
        response = api_football_get(
            STATUS_URL, headers={"x-apisports-key": key}, timeout=15,
            priority=APIBudgetPriority.CRITICAL, label="account status resync",
        )
        usage = active_football_account_usage(response)
    except Exception as exc:
        print(json.dumps({"status": "error", "reason": type(exc).__name__,
                          "before": before.__dict__}))
        return 1
    after = governor.snapshot(api_key=key)
    print(json.dumps({
        "status": "completed" if usage is not None else "unconfirmed",
        "http_status": response.status_code,
        "provider": {"requests": {"current": usage[0], "limit_day": usage[1]} if usage is not None else None},
        "before": before.__dict__, "after": after.__dict__,
    }, ensure_ascii=False, default=str))
    return 0 if usage is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
