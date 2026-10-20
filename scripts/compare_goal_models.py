"""Walk-forward comparison: legacy additive goal rates versus a Dixon-Coles variant.

Both models run through the same validation-only engine path on the same saved
football-data seasons (no prices in either model). The variant is one of
``challenge_engine.GOAL_MODEL_OPTIONS`` (plan 2026-10-20: H1 half-life, H2 level
prior). A derived "hybrid" (H3) takes the variant's law for result markets
(result, double chance, result+total) and the legacy law for every other goal
market; it is an analysis column, not a production path. Where closing prices
exist, every series is also compared with the no-vig Pinnacle closing market.

    python scripts/compare_goal_models.py --variant dixon_coles_hl240 \
        --legacy-cache runtime_state/market_benchmark/legacy_raw.json \
        --output docs/audits/2026-10-20-dixon-coles-hl240.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_engine import GOAL_MARKET_SPECS, GOAL_MODEL_OPTIONS, MARKET_BY_KEY  # noqa: E402
from football_data_history import FOOTBALL_DATA_DIVISIONS  # noqa: E402
from football_dixon_coles import last_fit  # noqa: E402
from market_benchmark import (  # noqa: E402
    BENCHMARK_MARKET_KEYS, CellResult, _brier, _logloss, apply_fdr, reference_probabilities,
    walk_forward_model_probabilities,
)
from market_benchmark_history import load_league  # noqa: E402
from model_loss_statistics import paired_advantage_statistics  # noqa: E402
from runtime_paths import RUNTIME_STATE_DIR  # noqa: E402

GOAL_KEYS = tuple(spec.key for spec in GOAL_MARKET_SPECS)
RESULT_KINDS = {"result", "double_chance", "result_total"}


def hybrid_predictions(legacy_raw, variant_raw):
    """H3: variant law for result-type markets, legacy law for the rest."""
    hybrid = {}
    for fixture_id, markets in variant_raw.items():
        base = legacy_raw.get(fixture_id)
        if base is None:
            continue
        hybrid[fixture_id] = {
            key: (value if MARKET_BY_KEY[key].kind in RESULT_KINDS else base[key])
            for key, value in markets.items() if key in base
        }
    return hybrid


def paired_cells(league_id, name, candidate_raw, legacy_raw, outcomes):
    shared = [f for f in candidate_raw if f in legacy_raw]
    rows = []
    for key in GOAL_KEYS:
        pairs = [(legacy_raw[f][key], candidate_raw[f][key], outcomes[f][key]) for f in shared
                 if key in legacy_raw[f] and key in candidate_raw[f] and key in outcomes.get(f, {})]
        if len(pairs) < 2:
            continue
        legacy_p, cand_p, y = (list(column) for column in zip(*pairs))
        advantages = [(l - o) ** 2 - (c - o) ** 2 for l, c, o in zip(legacy_p, cand_p, y)]  # positive = candidate better
        mean, se, lower, p_value = paired_advantage_statistics(advantages)
        rows.append(CellResult(
            league_id=league_id, market_key=f"{name}:{key}", provider="legacy", closing_share=0.0,
            observations=len(y), brier_model=_brier(cand_p, y), brier_raw=_brier(cand_p, y),
            brier_market=_brier(legacy_p, y), logloss_model=_logloss(cand_p, y), logloss_market=_logloss(legacy_p, y),
            mean_model_minus_market_pp=100.0 * sum(c - l for l, c in zip(legacy_p, cand_p)) / len(y),
            advantage_mean=mean, advantage_se=se, advantage_lower=lower, p_value=p_value,
        ))
    return rows


def market_cells(league_id, name, raw, outcomes, benchmark, shared):
    rows = []
    for key in BENCHMARK_MARKET_KEYS:
        triples = []
        for f in shared:
            entry = benchmark.get(f)
            if entry is None or key not in raw.get(f, {}) or key not in outcomes.get(f, {}):
                continue
            provider, market_p, _closing = reference_probabilities(entry)
            if provider is None or key not in market_p:
                continue
            triples.append((raw[f][key], market_p[key], outcomes[f][key]))
        if len(triples) < 2:
            continue
        model_p, market_values, y = (list(column) for column in zip(*triples))
        advantages = [(m - o) ** 2 - (p - o) ** 2 for p, m, o in zip(model_p, market_values, y)]
        mean, se, lower, p_value = paired_advantage_statistics(advantages)
        rows.append(CellResult(
            league_id=league_id, market_key=f"{name}:{key}", provider="pinnacle", closing_share=1.0,
            observations=len(y), brier_model=_brier(model_p, y), brier_raw=_brier(model_p, y),
            brier_market=_brier(market_values, y), logloss_model=_logloss(model_p, y),
            logloss_market=_logloss(market_values, y),
            mean_model_minus_market_pp=100.0 * sum(p - m for p, m in zip(model_p, market_values)) / len(y),
            advantage_mean=mean, advantage_se=se, advantage_lower=lower, p_value=p_value,
        ))
    return rows


def _load_cache(path):
    if path is None or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(league): {"raw": {int(f): m for f, m in v["raw"].items()},
                          "outcomes": {int(f): m for f, m in v["outcomes"].items()}}
            for league, v in data.items()}


def _save_cache(path, cache):
    if path is None:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps({str(k): {"raw": {str(f): m for f, m in v["raw"].items()},
                                        "outcomes": {str(f): m for f, m in v["outcomes"].items()}}
                               for k, v in cache.items()}), encoding="utf-8")
    tmp.replace(target)


def render(variant, options, cells, market_rows, leagues, fits, elapsed):
    names = [variant, "hybrid"]
    lines = [f"# Dixon-Coles-Variante `{variant}` gegen Legacy-Torraten: Walk-forward-Vergleich", "",
             f"Optionen: Halbwertszeit {options['half_life_days']:.0f} Tage, Niveau-Prior "
             f"{'ja (ungewichtetes Fenstermittel)' if options['level_prior'] else 'nein (gewichtete MLE)'}. "
             "Beide Modelle laufen durch denselben Validierungspfad (`fixture_market_probabilities`, "
             "`_validation_only=True`) über dieselben gespeicherten football-data-Saisons; verglichen werden "
             "die rohen aktiven Wahrscheinlichkeiten. `hybrid` = Variante für Ergebnis-, Doppelte-Chance- und "
             "Ergebnis+Total-Märkte, Legacy für alle anderen (H3, nur Analyse). Vorteil = Brier(Legacy) − "
             "Brier(Kandidat) je Spiel, positiv = Kandidat besser; HAC-SE, einseitiger p, BH über alle Zellen. "
             "Keine Quote fließt in eines der Modelle.", "",
             "## Datenbasis und letzte Fits", "",
             "| Liga | Saisons | Spiele | gemeinsam | Teams | ρ | Heimvorteil (log) |", "|---|---|---:|---:|---:|---:|---:|"]
    for league_id, info in sorted(leagues.items()):
        fit = fits.get(league_id)
        lines.append(f"| {league_id} | {', '.join(str(s) for s in info['seasons'])} | {info['fixtures']} | {info['shared']} | "
                     + (f"{fit['teams']} | {fit['rho']:+.3f} | {fit['home_advantage']:+.3f} |" if fit else "– | – | – |"))
    for name in names:
        subset = [c for c in cells if c.market_key.startswith(name + ":")]
        lines += ["", f"## `{name}` gegen Legacy je Markt", "",
                  "| Liga | Markt | n | Brier Kandidat | Brier Legacy | LogLoss Kandidat | LogLoss Legacy | Ø Kandidat−Legacy (pp) | Vorteil | HAC-SE | Untergrenze | p | q (BH) |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for cell in sorted(subset, key=lambda c: (c.league_id, GOAL_KEYS.index(c.market_key.split(":", 1)[1]))):
            lines.append(f"| {cell.league_id} | {cell.market_key.split(':', 1)[1]} | {cell.observations} | {cell.brier_model:.4f} | "
                         f"{cell.brier_market:.4f} | {cell.logloss_model:.4f} | {cell.logloss_market:.4f} | "
                         f"{cell.mean_model_minus_market_pp:+.2f} | {cell.advantage_mean:+.5f} | {cell.advantage_se:.5f} | "
                         f"{cell.advantage_lower:+.5f} | {cell.p_value:.3f} | {cell.q_value:.3f} |")
        better = [c for c in subset if c.advantage_lower is not None and c.advantage_lower > 0 and (c.q_value or 1) <= 0.05]
        worse = [c for c in subset if c.advantage_mean is not None and c.advantage_mean < 0]
        lines += ["", f"`{name}`: Zellen {len(subset)} · signifikant besser als Legacy (Untergrenze > 0, q ≤ 0,05): "
                  f"{len(better)} · im Mittel schlechter: {len(worse)}."]
        summary = {}
        for cell in subset:
            key = cell.market_key.split(":", 1)[1]
            agg = summary.setdefault(key, [0, 0.0, 0.0, 0, 0])
            agg[0] += cell.observations; agg[1] += cell.brier_model * cell.observations
            agg[2] += cell.brier_market * cell.observations
            agg[3] += 1 if cell.advantage_mean is not None and cell.advantage_mean < 0 else 0
            agg[4] += 1 if cell in better else 0
        lines += ["", "| Markt (alle Ligen) | n | Brier Kandidat | Brier Legacy | Ligen Kandidat schlechter | Ligen signifikant besser |",
                  "|---|---:|---:|---:|---:|---:|"]
        for key in GOAL_KEYS:
            if key in summary:
                n, bm, bl, worse_n, better_n = summary[key]
                lines.append(f"| {key} | {n} | {bm / n:.4f} | {bl / n:.4f} | {worse_n} | {better_n} |")
    lines += ["", "## Alle Serien gegen den No-Vig-Closing-Markt", "",
              "| Liga | Serie:Markt | n | Brier Serie | Brier Markt | Ø Serie−Markt (pp) | Vorteil | Untergrenze | p | q (BH) |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cell in sorted(market_rows, key=lambda c: (c.league_id, c.market_key)):
        lines.append(f"| {cell.league_id} | {cell.market_key} | {cell.observations} | {cell.brier_model:.4f} | {cell.brier_market:.4f} | "
                     f"{cell.mean_model_minus_market_pp:+.2f} | {cell.advantage_mean:+.5f} | {cell.advantage_lower:+.5f} | "
                     f"{cell.p_value:.3f} | {cell.q_value:.3f} |")
    summary = {}
    for cell in market_rows:
        agg = summary.setdefault(cell.market_key, [0, 0.0, 0.0])
        agg[0] += cell.observations; agg[1] += cell.brier_model * cell.observations; agg[2] += cell.brier_market * cell.observations
    lines += ["", "| Serie:Markt (alle Ligen) | n | Brier Serie | Brier Markt | Lücke |", "|---|---:|---:|---:|---:|"]
    for key, (n, bm, bk) in sorted(summary.items(), key=lambda item: (item[0].split(":")[1], item[0])):
        lines.append(f"| {key} | {n} | {bm / n:.4f} | {bk / n:.4f} | {bm / n - bk / n:+.4f} |")
    lines += ["", f"Laufzeit {elapsed:.0f} s.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RUNTIME_STATE_DIR / "market_benchmark")
    parser.add_argument("--leagues", default=",".join(str(i) for i in FOOTBALL_DATA_DIVISIONS))
    parser.add_argument("--seasons", default="2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--variant", default="dixon_coles", choices=sorted(GOAL_MODEL_OPTIONS))
    parser.add_argument("--legacy-cache", type=Path, default=None, help="JSON cache of legacy raw predictions")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    options = GOAL_MODEL_OPTIONS[args.variant]
    started = time.time()
    cache = _load_cache(args.legacy_cache)
    leagues, cells, market_rows, fits = {}, [], [], {}
    seasons = [int(x) for x in args.seasons.split(",") if x.strip()]
    for league_id in [int(x) for x in args.leagues.split(",") if x.strip()]:
        fixtures, benchmark, loaded = load_league(args.data_dir, league_id, seasons)
        if not fixtures:
            print(f"league {league_id}: no saved seasons")
            continue
        league_started = time.time()
        if league_id in cache:
            legacy_raw, outcomes = cache[league_id]["raw"], cache[league_id]["outcomes"]
        else:
            _cal, legacy_raw, outcomes = walk_forward_model_probabilities(fixtures)
            cache[league_id] = {"raw": legacy_raw, "outcomes": outcomes}
            _save_cache(args.legacy_cache, cache)
        _cal, variant_raw, variant_outcomes = walk_forward_model_probabilities(fixtures, goal_model=args.variant)
        outcomes = {**outcomes, **variant_outcomes}
        hybrid_raw = hybrid_predictions(legacy_raw, variant_raw)
        shared = [f for f in variant_raw if f in legacy_raw]
        cells += paired_cells(league_id, args.variant, variant_raw, legacy_raw, outcomes)
        cells += paired_cells(league_id, "hybrid", hybrid_raw, legacy_raw, outcomes)
        for name, raw in (("legacy", legacy_raw), (args.variant, variant_raw), ("hybrid", hybrid_raw)):
            market_rows += market_cells(league_id, name, raw, outcomes, benchmark, shared)
        leagues[league_id] = {"seasons": loaded, "fixtures": len(fixtures), "shared": len(shared)}
        fit = last_fit(league_id, half_life_days=options["half_life_days"], level_prior=options["level_prior"])
        fits[league_id] = fit.summary() if fit else None
        print(f"league {league_id}: fixtures {len(fixtures)}, legacy {len(legacy_raw)}, variant {len(variant_raw)}, "
              f"shared {len(shared)}, {time.time() - league_started:.0f}s")
    cells = apply_fdr(cells)
    market_rows = apply_fdr(market_rows)
    markdown = render(args.variant, options, cells, market_rows, leagues, fits, time.time() - started)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"report written: {args.output}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
