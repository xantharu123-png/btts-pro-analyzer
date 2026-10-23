"""Re-sync the local API-Football budget ledger with the provider's account status.

Use after a plan change (for example the free tier paid back up to Pro): the
ledger caches the limit it last saw and, within one plan, never raises its
estimate. One governed ``/status`` call at CRITICAL priority reads the
authoritative ``requests.current`` / ``limit_day`` from the provider and, since
23.10.2026, replaces a stale estimate whenever the limit grew. Prints the ledger
snapshot before and after; never prints the key.

    /opt/betboy/venv/bin/python scripts/api_budget_resync.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_budget import APIBudgetPriority, api_football_get, get_api_budget_governor  # noqa: E402
from config_loader import load_app_config  # noqa: E402

STATUS_URL = "https://v3.football.api-sports.io/status"


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
        payload = response.json()
    except Exception as exc:  # The ledger is left as it was; the reason is reported.
        print(json.dumps({"status": "error", "reason": type(exc).__name__,
                          "before": before.__dict__}))
        return 1
    account = payload.get("response") if isinstance(payload, dict) else None
    subscription = (account or {}).get("subscription") if isinstance(account, dict) else None
    usage = (account or {}).get("requests") if isinstance(account, dict) else None
    after = governor.snapshot(api_key=key)
    print(json.dumps({
        "status": "completed" if response.status_code == 200 else "degraded",
        "http_status": response.status_code,
        "provider": {"plan": (subscription or {}).get("plan"), "active": (subscription or {}).get("active"),
                     "end": (subscription or {}).get("end"), "requests": usage},
        "before": before.__dict__, "after": after.__dict__,
    }, ensure_ascii=False, default=str))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
