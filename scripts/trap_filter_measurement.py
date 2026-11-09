"""Read-only forward measurement of the pre-registered trap filter (docs/audits/2026-11-09-fallenfilter-vorab.md).

A published selection is a "trap" when its model probability is at least 5 points above 1/odds of the first stored
entry quote of its forecast (forecast_evidence.forecast_quotes, kind=entry). The pre-registered test uses the
selections whose first publication lies in [--since, --until) and asks:

A. Do the traps hit significantly less often than the model promised?
B. Do the traps hit significantly less often than the other selections with an entry quote?

Both must hold, with at least 150 settled traps. ``--count-only`` prints the settled counts per group without any
hit rate, so the sample size can be checked without looking at results. No network, no write. On the server:
    /opt/betboy/venv/bin/python -I scripts/trap_filter_measurement.py --count-only
    /opt/betboy/venv/bin/python -I scripts/trap_filter_measurement.py
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRAP_GAP = 0.05
MIN_TRAPS = 150
Z_CRITICAL = 1.645
DEFAULT_SINCE = "2026-11-10T00:00:00+00:00"
DEFAULT_UNTIL = "2026-11-28T00:00:00+00:00"


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _identity(payload):
    return payload.get("event_key"), payload.get("market_key"), payload.get("selection")


def first_entry_quotes(rows):
    """First entry quote per forecast from (forecast_id, kind, odds, bookmaker_id, observed_at) rows."""
    out = {}
    for forecast_id, kind, odds, bookmaker, observed in sorted(rows, key=lambda row: _utc(row[4])):
        if kind != "entry" or forecast_id in out:
            continue
        try:
            value = float(odds)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 1.0:
            out[forecast_id] = (value, str(bookmaker), observed)
    return out


def latest_results(rows):
    """Latest outcome per (event_key, market_key, selection) from (..., outcome, observed_at) rows."""
    out = {}
    for event_key, market_key, selection, outcome, observed in sorted(rows, key=lambda row: _utc(row[4])):
        out[(event_key, market_key, selection)] = str(outcome).upper()
    return out


def first_publications(publications):
    """First publication per selection from (first_observed_at, surface, payload) in any order."""
    out = {}
    for observed, surface, payload in sorted(publications, key=lambda row: _utc(row[0])):
        out.setdefault(_identity(payload), (_utc(observed), surface, payload))
    return out


def gap(probability, odds):
    return probability - 1.0 / odds


def tip_records(first, quotes, results, since, until):
    """Settled (WIN/LOSS) selections first published in [since, until); traps marked, no quote -> trap None."""
    records = []
    for key, (observed, surface, payload) in first.items():
        if not since <= observed < until or results.get(key) not in ("WIN", "LOSS"):
            continue
        probability = payload.get("probability")
        if type(probability) not in (int, float) or not 0.0 <= probability <= 1.0:
            continue
        quote = quotes.get(payload.get("forecast_id"))
        odds = quote[0] if quote else None
        records.append({
            "sport": str(payload.get("sport") or "?"), "surface": str(surface or "?"),
            "published": observed, "p": float(probability), "odds": odds,
            "trap": None if odds is None else gap(float(probability), odds) >= TRAP_GAP,
            "win": results[key] == "WIN",
        })
    return records


def verdict(records, min_traps=MIN_TRAPS):
    """Pre-registered decision: A (traps below the promise) and B (traps below the rest), both one-sided z >= 1.645."""
    traps = [r for r in records if r["trap"] is True]
    rest = [r for r in records if r["trap"] is False]
    summary = {"traps": len(traps), "rest": len(rest), "unquoted": sum(r["trap"] is None for r in records)}
    if len(traps) < min_traps or not rest:
        return {**summary, "status": "not_enough_data", "conditions": []}
    wins_t, wins_r = sum(r["win"] for r in traps), sum(r["win"] for r in rest)
    promised = sum(r["p"] for r in traps)
    variance = sum(r["p"] * (1.0 - r["p"]) for r in traps)
    z_a = (promised - wins_t) / math.sqrt(variance) if variance > 0 else 0.0
    hit_t, hit_r = wins_t / len(traps), wins_r / len(rest)
    pooled = (wins_t + wins_r) / (len(traps) + len(rest))
    se = math.sqrt(pooled * (1.0 - pooled) * (1.0 / len(traps) + 1.0 / len(rest)))
    z_b = (hit_r - hit_t) / se if se > 0 else 0.0
    conditions = [
        {"name": "A traps below promise", "hit": hit_t, "promised": promised / len(traps), "z": z_a,
         "met": z_a >= Z_CRITICAL},
        {"name": "B traps below rest", "hit": hit_t, "rest_hit": hit_r, "z": z_b, "met": z_b >= Z_CRITICAL},
    ]
    status = "passed" if all(c["met"] for c in conditions) else "failed"
    return {**summary, "status": status, "conditions": conditions}


def load(tips_db, evidence_db):
    tips = sqlite3.connect(f"file:{tips_db}?mode=ro", uri=True)
    evidence = sqlite3.connect(f"file:{evidence_db}?mode=ro", uri=True)
    try:
        publications = []
        for publication_id, surface, observed in tips.execute(
                "select publication_id, surface, first_observed_at from consumer_tip_publications"):
            for (payload,) in tips.execute("select payload_json from consumer_tips where publication_id=?",
                                           (publication_id,)):
                publications.append((observed, surface, json.loads(payload)))
        quotes = first_entry_quotes(evidence.execute(
            "select forecast_id, kind, odds, bookmaker_id, observed_at from forecast_quotes where kind='entry'"))
        results = latest_results(evidence.execute(
            "select event_key, market_key, selection, outcome, observed_at from forecast_results"))
    finally:
        tips.close()
        evidence.close()
    return first_publications(publications), quotes, results


def _rate(rows):
    return f"{100.0 * sum(r['win'] for r in rows) / len(rows):5.1f} %" if rows else "    -"


def report(records, since, until, count_only):
    days = max((min(until, datetime.now(timezone.utc)) - since).total_seconds() / 86400.0, 1e-9)
    traps = [r for r in records if r["trap"] is True]
    rest = [r for r in records if r["trap"] is False]
    unquoted = [r for r in records if r["trap"] is None]
    print(f"Fenster {since.isoformat()} bis {until.isoformat()} ({days:.1f} Tage bisher)")
    print(f"Abgerechnete Tipps {len(records)}: Fallen {len(traps)}, übrige mit Quote {len(rest)}, "
          f"ohne Quote {len(unquoted)}; nötig mindestens {MIN_TRAPS} Fallen")
    print("Fallen nach Sport:", dict(Counter(r["sport"] for r in traps).most_common()))
    print("Fallen nach Liste:", dict(Counter(r["surface"] for r in traps).most_common()))
    if count_only:
        return
    for label, rows in (("Fallen", traps), ("übrige mit Quote", rest), ("ohne Quote", unquoted),
                        ("alle", records), ("alle ohne Fallen", rest + unquoted)):
        quoted = [r for r in rows if r["odds"]]
        implied = f"{100.0 * sum(1.0 / r['odds'] for r in quoted) / len(quoted):5.1f} %" if quoted else "    -"
        promise = f"{100.0 * sum(r['p'] for r in rows) / len(rows):5.1f} %" if rows else "    -"
        print(f"  {label:<18} n={len(rows):5d}  Treffer {_rate(rows)}  Modell {promise}  Quote sagt {implied}")
    print(f"Wegfallende Tipps je Tag: {len(traps) / days:.1f}")
    result = verdict(records)
    for condition in result["conditions"]:
        print(f"  {condition['name']}: z={condition['z']:+.2f} -> {'erfüllt' if condition['met'] else 'nicht erfüllt'}")
    print("Ergebnis:", result["status"])


def main(argv=None):
    from runtime_paths import RUNTIME_STATE_DIR
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tips-db", default=str(RUNTIME_STATE_DIR / "consumer_tips.db"))
    parser.add_argument("--evidence-db", default=str(RUNTIME_STATE_DIR / "forecast_evidence.db"))
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args(argv)
    since, until = _utc(args.since), _utc(args.until)
    first, quotes, results = load(args.tips_db, args.evidence_db)
    report(tip_records(first, quotes, results, since, until), since, until, args.count_only)


if __name__ == "__main__":
    main()
