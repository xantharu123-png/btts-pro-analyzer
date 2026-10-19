"""Walk-forward model-versus-closing-market benchmark on saved football-data CSVs.

Usage (from the app root, after ``scripts/download_market_benchmark_data.py``):

    python scripts/market_benchmark_report.py --leagues 39,78 --seasons 2021,2022,2023 \
        --output docs/audits/2026-10-19-marktbenchmark.md

Prices never enter the model; they are joined after prediction by fixture id.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from football_data_history import FOOTBALL_DATA_DIVISIONS  # noqa: E402
from market_benchmark import BenchmarkReport, GENERIC_HAIRCUT_PP, benchmark_league, finalise, render_markdown  # noqa: E402
from market_benchmark_history import load_league  # noqa: E402
from runtime_paths import RUNTIME_STATE_DIR  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RUNTIME_STATE_DIR / "market_benchmark")
    parser.add_argument("--leagues", default=",".join(str(i) for i in FOOTBALL_DATA_DIVISIONS))
    parser.add_argument("--seasons", default="2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--haircut-pp", type=float, default=GENERIC_HAIRCUT_PP)
    parser.add_argument("--output", type=Path, default=None, help="markdown report path")
    parser.add_argument("--json", type=Path, default=None, help="optional machine-readable cell dump")
    args = parser.parse_args()
    leagues = [int(x) for x in args.leagues.split(",") if x.strip()]
    seasons = [int(x) for x in args.seasons.split(",") if x.strip()]
    report = BenchmarkReport(haircut_pp=args.haircut_pp)
    started = time.time()
    for league_id in leagues:
        fixtures, benchmark, loaded = load_league(args.data_dir, league_id, seasons)
        if not fixtures:
            print(f"league {league_id}: no saved seasons in {args.data_dir}")
            continue
        league_started = time.time()
        benchmark_league(report, league_id=league_id, fixtures=fixtures, benchmark=benchmark, seasons=loaded)
        info = report.leagues[league_id]
        print(f"league {league_id}: seasons {loaded}, fixtures {info['fixtures']}, predicted {info['predicted']}, "
              f"joined {info['joined_with_benchmark']}, {time.time() - league_started:.0f}s")
    finalise(report)
    markdown = render_markdown(report)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown + f"\n\nLaufzeit {time.time() - started:.0f} s.\n", encoding="utf-8")
        print(f"report written: {args.output}")
    else:
        print(markdown)
    if args.json is not None:
        payload = {
            "leagues": report.leagues,
            "cells": [vars(cell) for cell in report.cells],
            "bets": len(report.bets),
            "haircut_pp": report.haircut_pp,
        }
        args.json.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
