"""Precompute challenge model artifacts for an explicit football match day."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_15k import (  # noqa: E402
    MAX_SCAN_FIXTURES,
    ChallengeDataProvider,
    scan_daily_challenge,
)
from config_loader import load_app_config  # noqa: E402


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=_iso_date)
    parser.add_argument(
        "--leagues",
        nargs="+",
        required=True,
        type=int,
        help="API-Football league IDs",
    )
    parser.add_argument("--max-fixtures", type=int, default=MAX_SCAN_FIXTURES)
    args = parser.parse_args(argv)

    config = load_app_config()
    if not config.api_football_key:
        parser.error("API_FOOTBALL_KEY is not configured")
    provider = ChallengeDataProvider(
        config.api_football_key,
        config.weather_key,
    )
    started = monotonic()
    snapshot = scan_daily_challenge(
        provider,
        list(dict.fromkeys(args.leagues)),
        args.date,
        args.max_fixtures,
        progress_cb=lambda fraction, message: print(
            f"{fraction:6.1%} {message}",
            flush=True,
        ),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "search_date": snapshot["search_date"],
                "fixtures_found": snapshot["fixtures_found"],
                "fixtures_modeled": snapshot["fixtures_modeled"],
                "continental_fallback_modeled": snapshot.get(
                    "continental_fallback_modeled",
                    0,
                ),
                "base_candidates": snapshot["base_candidates"],
                "approved_candidates": snapshot["approved_candidates"],
                "blocked_counts": snapshot["blocked_counts"],
                "base_shortlist": [
                    {
                        "fixture_id": candidate.fixture_id,
                        "match": f"{candidate.home_team} vs {candidate.away_team}",
                        "market_key": candidate.market_key,
                        "conservative_probability": round(
                            candidate.conservative_probability,
                            6,
                        ),
                        "h2h_status": (candidate.context.get("h2h") or {}).get(
                            "status"
                        ),
                        "blocked_reasons": candidate.context.get(
                            "blocked_reasons",
                            [],
                        ),
                    }
                    for candidate in snapshot["base_shortlist"]
                ],
                "elapsed_seconds": round(monotonic() - started, 1),
                "provider_errors": snapshot["errors"],
            },
            ensure_ascii=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
