"""Verify candidate API-Football league ids against /leagues.

Usage: python scripts/verify_league_ids.py 104 114 120
Prints only public league metadata - never the API key.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api_budget import APIBudgetPriority, api_football_get
from config_loader import load_app_config


def main() -> int:
    ids = [int(a) for a in sys.argv[1:]] or [104, 114, 120, 164, 244, 245]
    cfg = load_app_config()
    key = cfg.api_football_key or cfg.api_key
    if not key:
        print("KEIN API-KEY gefunden (config.ini / env / secrets).")
        return 1
    headers = {"x-apisports-key": key}
    for lid in ids:
        r = api_football_get(
            "https://v3.football.api-sports.io/leagues",
            headers=headers, params={"id": lid}, timeout=15,
            priority=APIBudgetPriority.BACKGROUND,
            label=f"verify league {lid}",
        )
        data = r.json()
        resp = data.get("response") or []
        remaining = r.headers.get("x-ratelimit-requests-remaining", "?")
        if not resp:
            print(f"{lid}: NICHT GEFUNDEN  errors={data.get('errors')}")
            continue
        lg = resp[0]
        seasons = lg.get("seasons", [])
        cur = [s["year"] for s in seasons if s.get("current")]
        cov = (seasons[-1] if seasons else {}).get("coverage", {})
        fx = cov.get("fixtures", {})
        print(
            f"{lid}: {lg['league']['name']} ({lg['country']['name']}) | "
            f"current={cur} | events={fx.get('events')} stats={fx.get('statistics')} "
            f"lineups={fx.get('lineups')} | odds={cov.get('odds')} | "
            f"quota_rest={remaining}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
