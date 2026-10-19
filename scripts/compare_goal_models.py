"""Walk-forward comparison: legacy additive goal rates versus the opt-in Dixon-Coles fit.

Both models run through the same validation-only engine path on the same saved
football-data seasons (no prices in either model). Where closing prices exist,
both are also compared with the no-vig Pinnacle closing market. Usage:

    python scripts/compare_goal_models.py --leagues 39,78 --seasons 2021,2022,2023 \
        --output docs/audits/2026-10-19-dixon-coles-vergleich.md
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_engine import GOAL_MARKET_SPECS  # noqa: E402
from football_data_history import FOOTBALL_DATA_DIVISIONS  # noqa: E402
from football_dixon_coles import _LAST_FIT  # noqa: E402
from market_benchmark import (  # noqa: E402
    BENCHMARK_MARKET_KEYS, CellResult, _brier, _logloss, apply_fdr, reference_probabilities,
    walk_forward_model_probabilities,
)
from market_benchmark_history import load_league  # noqa: E402
from model_loss_statistics import paired_advantage_statistics  # noqa: E402
from runtime_paths import RUNTIME_STATE_DIR  # noqa: E402

GOAL_KEYS = tuple(spec.key for spec in GOAL_MARKET_SPECS)


def paired_cells(league_id, legacy_raw, dixon_raw, outcomes, benchmark):
    """Cells: DC versus legacy on every goal market; both versus market where priced."""
    shared = [f for f in dixon_raw if f in legacy_raw]
    rows = []
    for key in GOAL_KEYS:
        pairs = [(legacy_raw[f][key], dixon_raw[f][key], outcomes[f][key]) for f in shared
                 if key in legacy_raw[f] and key in dixon_raw[f] and key in outcomes.get(f, {})]
        if len(pairs) < 2:
            continue
        legacy_p, dixon_p, y = (list(column) for column in zip(*pairs))
        advantages = [(l - o) ** 2 - (d - o) ** 2 for l, d, o in zip(legacy_p, dixon_p, y)]  # positive = DC better
        mean, se, lower, p_value = paired_advantage_statistics(advantages)
        rows.append(CellResult(
            league_id=league_id, market_key=key, provider="legacy", closing_share=0.0, observations=len(y),
            brier_model=_brier(dixon_p, y), brier_raw=_brier(dixon_p, y), brier_market=_brier(legacy_p, y),
            logloss_model=_logloss(dixon_p, y), logloss_market=_logloss(legacy_p, y),
            mean_model_minus_market_pp=100.0 * sum(d - l for l, d in zip(legacy_p, dixon_p)) / len(y),
            advantage_mean=mean, advantage_se=se, advantage_lower=lower, p_value=p_value,
        ))
    market_rows = []
    for model_name, raw in (("legacy", legacy_raw), ("dixon_coles", dixon_raw)):
        for key in BENCHMARK_MARKET_KEYS:
            triples = []
            for f in shared:
                entry = benchmark.get(f)
                if entry is None or key not in raw[f] or key not in outcomes.get(f, {}):
                    continue
                provider, market_p, _closing = reference_probabilities(entry)
                if provider is None or key not in market_p:
                    continue
                triples.append((raw[f][key], market_p[key], outcomes[f][key]))
            if len(triples) < 2:
                continue
            model_p, market_p_values, y = (list(column) for column in zip(*triples))
            advantages = [(m - o) ** 2 - (p - o) ** 2 for p, m, o in zip(model_p, market_p_values, y)]
            mean, se, lower, p_value = paired_advantage_statistics(advantages)
            market_rows.append(CellResult(
                league_id=league_id, market_key=f"{model_name}:{key}", provider="pinnacle", closing_share=1.0,
                observations=len(y), brier_model=_brier(model_p, y), brier_raw=_brier(model_p, y),
                brier_market=_brier(market_p_values, y), logloss_model=_logloss(model_p, y),
                logloss_market=_logloss(market_p_values, y),
                mean_model_minus_market_pp=100.0 * sum(p - m for p, m in zip(model_p, market_p_values)) / len(y),
                advantage_mean=mean, advantage_se=se, advantage_lower=lower, p_value=p_value,
            ))
    return rows, market_rows


def render(cells, market_cells, leagues, fits, elapsed):
    lines = ["# Dixon-Coles gegen Legacy-Torraten: Walk-forward-Vergleich", "",
             "Beide Modelle laufen durch denselben Validierungspfad (`fixture_market_probabilities`, "
             "`_validation_only=True`) über dieselben gespeicherten football-data-Saisons. Verglichen werden die "
             "**rohen** (unkalibrierten) aktiven Wahrscheinlichkeiten je Zielmarkt. Vorteil = Brier(Legacy) − "
             "Brier(Dixon-Coles) je Spiel, positiv = Dixon-Coles besser; HAC-Standardfehler, einseitiger p-Wert, "
             "Benjamini-Hochberg über alle Zellen. Keine Quote fließt in eines der Modelle.", "",
             "## Datenbasis und letzte Fits", "", "| Liga | Saisons | Spiele | gemeinsam prognostiziert | Teams | ρ | Heimvorteil (log) | Halbwertszeit |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for league_id, info in sorted(leagues.items()):
        fit = fits.get(league_id)
        lines.append(f"| {league_id} | {', '.join(str(s) for s in info['seasons'])} | {info['fixtures']} | {info['shared']} | "
                     f"{fit['teams'] if fit else '–'} | {fit['rho']:+.3f} | {fit['home_advantage']:+.3f} | {fit['half_life_days']:.0f} d |"
                     if fit else f"| {league_id} | {', '.join(str(s) for s in info['seasons'])} | {info['fixtures']} | {info['shared']} | – | – | – | – |")
    lines += ["", "## Dixon-Coles gegen Legacy je Markt", "",
              "| Liga | Markt | n | Brier DC | Brier Legacy | LogLoss DC | LogLoss Legacy | Ø DC−Legacy (pp) | Vorteil | HAC-SE | Untergrenze | p | q (BH) |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cell in sorted(cells, key=lambda c: (c.league_id, GOAL_KEYS.index(c.market_key))):
        lines.append(f"| {cell.league_id} | {cell.market_key} | {cell.observations} | {cell.brier_model:.4f} | {cell.brier_market:.4f} | "
                     f"{cell.logloss_model:.4f} | {cell.logloss_market:.4f} | {cell.mean_model_minus_market_pp:+.2f} | "
                     f"{cell.advantage_mean:+.5f} | {cell.advantage_se:.5f} | {cell.advantage_lower:+.5f} | {cell.p_value:.3f} | {cell.q_value:.3f} |")
    better = [c for c in cells if c.advantage_lower is not None and c.advantage_lower > 0 and (c.q_value or 1) <= 0.05]
    worse = [c for c in cells if c.advantage_mean is not None and c.advantage_mean < 0]
    lines += ["", f"Zellen: {len(cells)} · Dixon-Coles signifikant besser (Untergrenze > 0, q ≤ 0,05): {len(better)} · "
              f"im Mittel schlechter: {len(worse)}.", "",
              "## Beide Modelle gegen den No-Vig-Closing-Markt", "",
              "| Liga | Modell:Markt | n | Brier Modell | Brier Markt | Ø Modell−Markt (pp) | Vorteil | Untergrenze | p | q (BH) |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cell in sorted(market_cells, key=lambda c: (c.league_id, c.market_key)):
        lines.append(f"| {cell.league_id} | {cell.market_key} | {cell.observations} | {cell.brier_model:.4f} | {cell.brier_market:.4f} | "
                     f"{cell.mean_model_minus_market_pp:+.2f} | {cell.advantage_mean:+.5f} | {cell.advantage_lower:+.5f} | {cell.p_value:.3f} | {cell.q_value:.3f} |")
    lines += ["", f"Laufzeit {elapsed:.0f} s.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RUNTIME_STATE_DIR / "market_benchmark")
    parser.add_argument("--leagues", default=",".join(str(i) for i in FOOTBALL_DATA_DIVISIONS))
    parser.add_argument("--seasons", default="2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    started = time.time()
    leagues, cells, market_cells, fits = {}, [], [], {}
    for league_id in [int(x) for x in args.leagues.split(",") if x.strip()]:
        fixtures, benchmark, loaded = load_league(args.data_dir, league_id, [int(x) for x in args.seasons.split(",") if x.strip()])
        if not fixtures:
            print(f"league {league_id}: no saved seasons")
            continue
        league_started = time.time()
        _legacy_cal, legacy_raw, outcomes = walk_forward_model_probabilities(fixtures)
        _dixon_cal, dixon_raw, dixon_outcomes = walk_forward_model_probabilities(fixtures, goal_model="dixon_coles")
        outcomes.update(dixon_outcomes)
        league_cells, league_market = paired_cells(league_id, legacy_raw, dixon_raw, outcomes, benchmark)
        cells.extend(league_cells)
        market_cells.extend(league_market)
        shared = sum(1 for f in dixon_raw if f in legacy_raw)
        leagues[league_id] = {"seasons": loaded, "fixtures": len(fixtures), "shared": shared}
        last = _LAST_FIT.get(league_id)
        fits[league_id] = last.summary() if last else None
        print(f"league {league_id}: fixtures {len(fixtures)}, legacy {len(legacy_raw)}, dixon {len(dixon_raw)}, "
              f"shared {shared}, {time.time() - league_started:.0f}s")
    cells = apply_fdr(cells)
    market_cells = apply_fdr(market_cells)
    markdown = render(cells, market_cells, leagues, fits, time.time() - started)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"report written: {args.output}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
