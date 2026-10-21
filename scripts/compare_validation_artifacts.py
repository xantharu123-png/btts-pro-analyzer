"""Compare the release-gate validation artifact of two goal-rate bases per league.

Runs the engine's own walk-forward artifact builder (validation metrics and
calibration maps, per-league Benjamini-Hochberg) once with the legacy basis and
once with a Dixon-Coles variant, on the saved football-data seasons. Reports
per market how many leagues pass ``_credible_validation`` and the statistical
release check, plus Brier, relative improvement over the base rate and ECE.

    python scripts/compare_validation_artifacts.py --variant dixon_coles_hl365_hybrid \
        --output docs/audits/2026-10-22-hybrid-validierung.md
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_engine import (  # noqa: E402
    GOAL_MARKET_SPECS, GOAL_MODEL_LEGACY, GOAL_MODEL_OPTIONS, _credible_statistical_release_validation,
    _credible_validation, build_market_model_artifact,
)
from football_data_history import FOOTBALL_DATA_DIVISIONS  # noqa: E402
from market_benchmark_history import load_league  # noqa: E402
from runtime_paths import RUNTIME_STATE_DIR  # noqa: E402

GOAL_KEYS = tuple(spec.key for spec in GOAL_MARKET_SPECS)


def summarise(validations):
    """Per market across leagues: passes, release passes, mean metrics."""
    rows = {}
    for league_id, metrics in validations.items():
        for key in GOAL_KEYS:
            metric = metrics.get(key)
            row = rows.setdefault(key, {"leagues": 0, "credible": 0, "released": 0, "brier": [], "improvement": [], "ece": [], "n": []})
            if metric is None or not metric.observations:
                continue
            row["leagues"] += 1
            row["credible"] += 1 if _credible_validation(metric) else 0
            row["released"] += 1 if (_credible_validation(metric) and _credible_statistical_release_validation(metric)) else 0
            if metric.brier_score is not None:
                row["brier"].append(float(metric.brier_score))
            if metric.relative_improvement is not None:
                row["improvement"].append(float(metric.relative_improvement))
            if metric.expected_calibration_error is not None:
                row["ece"].append(float(metric.expected_calibration_error))
            row["n"].append(int(metric.observations))
    return rows


def _mean(values):
    return sum(values) / len(values) if values else float("nan")


def render(variant, legacy_rows, variant_rows, leagues, elapsed):
    lines = [f"# Release-Gate-Validierung: `{variant}` gegen Legacy", "",
             "Gleicher Walk-forward-Artefakt-Builder wie der Produktionscache (`build_market_model_artifact`: "
             "Kalibrierung nur aus Vortagen, Brier gegen Laplace-Basisrate, Kalibrierdiagnostik, HAC und "
             "Benjamini-Hochberg je Liga). `credible` = `_credible_validation`, `released` = zusätzlich "
             "`_credible_statistical_release_validation`. Zahlen über alle Ligen; keine Quote im Modell. "
             "Dieser Vergleich misst Basisraten-Skill, nicht Marktskill (dafür `market_benchmark`).", "",
             f"Ligen: {', '.join(str(l) for l in leagues)}. Laufzeit {elapsed:.0f} s.", "",
             "| Markt | Ligen | credible Legacy | credible Variante | released Legacy | released Variante | Brier Legacy | Brier Variante | rel. Verb. Legacy | rel. Verb. Variante | ECE Legacy | ECE Variante |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    totals = [0] * 4
    for key in GOAL_KEYS:
        a, b = legacy_rows.get(key), variant_rows.get(key)
        if not a or not b:
            continue
        totals[0] += a["credible"]; totals[1] += b["credible"]; totals[2] += a["released"]; totals[3] += b["released"]
        lines.append(f"| {key} | {a['leagues']} | {a['credible']} | {b['credible']} | {a['released']} | {b['released']} | "
                     f"{_mean(a['brier']):.4f} | {_mean(b['brier']):.4f} | {_mean(a['improvement']) * 100:+.1f} % | "
                     f"{_mean(b['improvement']) * 100:+.1f} % | {_mean(a['ece']):.3f} | {_mean(b['ece']):.3f} |")
    lines += ["", f"Summe credible: Legacy {totals[0]}, Variante {totals[1]} · Summe released: Legacy {totals[2]}, Variante {totals[3]} "
              f"(Zellen = Märkte × Ligen).", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RUNTIME_STATE_DIR / "market_benchmark")
    parser.add_argument("--leagues", default=",".join(str(i) for i in FOOTBALL_DATA_DIVISIONS))
    parser.add_argument("--seasons", default="2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--variant", default="dixon_coles_hl365_hybrid", choices=sorted(GOAL_MODEL_OPTIONS))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    started = time.time()
    seasons = [int(x) for x in args.seasons.split(",") if x.strip()]
    legacy_validations, variant_validations, leagues = {}, {}, []
    for league_id in [int(x) for x in args.leagues.split(",") if x.strip()]:
        fixtures, _benchmark, loaded = load_league(args.data_dir, league_id, seasons)
        if not fixtures:
            print(f"league {league_id}: no saved seasons")
            continue
        league_started = time.time()
        legacy_validations[league_id], _ = build_market_model_artifact(fixtures, goal_model=GOAL_MODEL_LEGACY)
        variant_validations[league_id], _ = build_market_model_artifact(fixtures, goal_model=args.variant)
        leagues.append(league_id)
        passes = lambda v: sum(1 for m in v.values() if _credible_validation(m))  # noqa: E731
        print(f"league {league_id}: credible legacy {passes(legacy_validations[league_id])}, "
              f"variant {passes(variant_validations[league_id])}, {time.time() - league_started:.0f}s")
    markdown = render(args.variant, summarise(legacy_validations), summarise(variant_validations), leagues, time.time() - started)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"report written: {args.output}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
