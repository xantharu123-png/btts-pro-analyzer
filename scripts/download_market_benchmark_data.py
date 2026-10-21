"""Download football-data.co.uk season CSVs for the market benchmark (data only).

Files land in ``runtime_state/market_benchmark`` (ignored by Git). Nothing in
a downloaded file is executed; the benchmark reads prices and results only.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from football_data_history import FOOTBALL_DATA_DIVISIONS  # noqa: E402
from market_benchmark_history import download_benchmark_csv  # noqa: E402
from runtime_paths import RUNTIME_STATE_DIR  # noqa: E402

DEFAULT_SEASONS = (2019, 2020, 2021, 2022, 2023, 2024, 2025)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RUNTIME_STATE_DIR / "market_benchmark")
    parser.add_argument("--leagues", default=",".join(str(i) for i in FOOTBALL_DATA_DIVISIONS),
                        help="API-Football league ids, comma separated")
    parser.add_argument("--seasons", default=",".join(str(s) for s in DEFAULT_SEASONS),
                        help="season start years, comma separated")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--pause", type=float, default=0.5, help="seconds between requests")
    args = parser.parse_args()
    leagues = [int(x) for x in args.leagues.split(",") if x.strip()]
    seasons = [int(x) for x in args.seasons.split(",") if x.strip()]
    saved, failed = 0, []
    for league_id in leagues:
        for season in seasons:
            try:
                path = download_benchmark_csv(league_id, season, args.data_dir, overwrite=args.overwrite)
            except Exception as exc:  # Report, continue with the next file.
                failed.append((league_id, season, str(exc)[:120]))
                continue
            if path is not None:
                saved += 1
                print(f"{league_id} {season}: {path.name} ({path.stat().st_size // 1024} KB)")
            time.sleep(args.pause)
    print(f"saved/present: {saved}; failed: {len(failed)}")
    for item in failed:
        print("  failed:", item)
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
