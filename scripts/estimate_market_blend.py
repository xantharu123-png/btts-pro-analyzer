"""Estimate the model/market blend weight and replay the price gate with blend and edge cap.

Input: the JSONL rows written by ``scripts/market_benchmark_report.py --rows``.

    python scripts/estimate_market_blend.py --rows runtime_state/market_benchmark/rows.jsonl \
        --output docs/audits/2026-10-20-marktmischung.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_benchmark import BENCHMARK_MARKET_KEYS, EDGE_CAP_PP  # noqa: E402
from market_blend import fit_blend_weight, replay_policy  # noqa: E402


def _pct(value):
    return "–" if value is None else f"{value * 100:+.1f} %"


def _ci(interval):
    return "–" if interval is None else f"[{interval[0] * 100:+.1f} %, {interval[1] * 100:+.1f} %]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--haircut-pp", type=float, default=5.0)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.rows.read_text(encoding="utf-8").splitlines() if line.strip()]
    direct = [r for r in rows if r["market_key"] in BENCHMARK_MARKET_KEYS and not r["market_key"].startswith("DC_")]
    fits = [fit_blend_weight(direct, label="alle Märkte")]
    weights = {}
    for key in BENCHMARK_MARKET_KEYS:
        subset = [r for r in direct if r["market_key"] == key]
        if len(subset) >= 200:
            fit = fit_blend_weight(subset, label=key)
            fits.append(fit)
            weights[key] = fit.weight
    replays = [
        replay_policy(direct, label="heutige Policy (w = 1, kein Cap)", haircut_pp=args.haircut_pp),
        replay_policy(direct, label=f"Policy + Edge-Cap {EDGE_CAP_PP:.0f} pp", haircut_pp=args.haircut_pp, edge_cap_pp=EDGE_CAP_PP),
        replay_policy(direct, label="Policy mit Mischung w* je Markt", haircut_pp=args.haircut_pp, weights=weights,
                      default_weight=fits[0].weight),
        replay_policy(direct, label=f"Mischung w* + Edge-Cap {EDGE_CAP_PP:.0f} pp", haircut_pp=args.haircut_pp,
                      weights=weights, default_weight=fits[0].weight, edge_cap_pp=EDGE_CAP_PP),
        replay_policy(direct, label="Mischung w* ohne Haircut", haircut_pp=0.0, weights=weights,
                      default_weight=fits[0].weight),
    ]
    lines = ["# Entscheidungswahrscheinlichkeit als Mischung von Modell und Markt", "",
             "Grundlage: Zeilen des Marktbenchmarks (walk-forward kalibrierte Modell-p, No-Vig-Pinnacle-Closing, "
             "Ergebnis, bester Closing-Preis). Mischung im Log-Odds-Raum, `logit(p) = w·logit(Modell) + (1−w)·logit(Markt)`. "
             "Das Gewicht w wird auf den chronologisch ersten 70 % der Zeilen per Log-Loss-Raster (Schritt 0,05) "
             "gewählt und auf den letzten 30 % bewertet. Die gespeicherte Modell-p bleibt unverändert; die "
             "Mischung ist eine getrennte Entscheidungsgrösse (Audit K3).", "",
             "## Gewicht und Out-of-sample-Güte", "",
             "| Markt | Zeilen Train/Test | w* (Modellanteil) | LogLoss Modell | LogLoss Markt | LogLoss Mischung | Brier Modell | Brier Markt | Brier Mischung |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for fit in fits:
        lines.append(f"| {fit.label} | {fit.train_rows}/{fit.test_rows} | {fit.weight:.2f} | {fit.test_logloss_model:.4f} | "
                     f"{fit.test_logloss_market:.4f} | {fit.test_logloss_blend:.4f} | {fit.test_brier_model:.4f} | "
                     f"{fit.test_brier_market:.4f} | {fit.test_brier_blend:.4f} |")
    lines += ["", f"Lesart: w* ist der Anteil, mit dem das Modell über den Markt hinaus Information beiträgt. "
              f"Ein w* nahe 0 bedeutet, dass die Entscheidung fast vollständig dem Markt folgen sollte.", "",
              f"## Replay der Preisgate-Policy (Haircut {args.haircut_pp:.0f} pp, 3 % Risiko-ROI, Boden 1,20, bester Closing-Preis)", "",
              "| Variante | Wetten | Trefferquote | ROI | ROI 90 %-Bootstrap | CLV | CLV 90 %-Bootstrap | Ø Modell−Markt (pp) |",
              "|---|---:|---:|---:|---|---:|---|---:|"]
    for replay in replays:
        lines.append(f"| {replay.label} | {replay.bets} | {_pct(replay.hit_rate)} | {_pct(replay.roi)} | {_ci(replay.roi_interval)} | "
                     f"{_pct(replay.clv)} | {_ci(replay.clv_interval)} | "
                     f"{replay.mean_edge_pp:+.1f} |" if replay.mean_edge_pp is not None else f"| {replay.label} | 0 | – | – | – | – | – | – |")
    lines += ["", "Hinweise: Wetten desselben Spiels auf mehreren Märkten sind korreliert (Intervalle zu schmal); "
              "der beste Closing-Preis ist für die Ausführung optimistisch; die Mischung mit Markt-p verlangt in der "
              "Produktion den vollständigen No-Vig-Markt (alle Seiten), den der heutige Quotenabruf nicht liefert.", ""]
    markdown = "\n".join(lines)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"report written: {args.output}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
