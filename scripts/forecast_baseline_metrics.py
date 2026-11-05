"""Read-only baseline before model changes: calibration, Brier score and log loss per sport.

Usage: python -I scripts/forecast_baseline_metrics.py [forecast_evidence.db] [cut-off ISO time]
Source: settled forecasts in forecast_evidence.db (latest decision per event, market and
selection; VOID excluded). Reproducible: same script, same database, same cut-off.
"""
import json
import math
import sqlite3
import sys
from collections import defaultdict

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/betboy/app/runtime_state/forecast_evidence.db"
DB = f"file:{DB_PATH}?mode=ro"
THROUGH = sys.argv[2] if len(sys.argv) > 2 else "2026-11-05T00:00:00+00:00"
BINS = ((0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01))

con = sqlite3.connect(DB, uri=True, timeout=60)
results = {}
for event_key, market_key, selection, outcome in con.execute(
        "select event_key, market_key, selection, outcome from forecast_results"):
    results[(event_key, market_key, selection)] = str(outcome).upper()

latest = {}
for event_key, market_key, selection, sport, starts_at, decision_at, model_version, payload in con.execute(
        "select event_key, market_key, selection, sport, starts_at, decision_at, model_version, payload_json "
        "from forecast_rows where starts_at < ?", (THROUGH,)):
    key = (event_key, market_key, selection)
    if results.get(key) not in ("WIN", "LOSS"):
        continue
    if key not in latest or str(decision_at) > latest[key][0]:
        latest[key] = (str(decision_at), sport, model_version, payload)

groups = defaultdict(list)
versions = defaultdict(lambda: defaultdict(int))
for key, (_decision, sport, model_version, payload) in latest.items():
    p = json.loads(payload).get("probability")
    if not isinstance(p, (int, float)) or not 0 < p < 1:
        continue
    won = results[key] == "WIN"
    groups[sport].append((p, won))
    groups["ALLE"].append((p, won))
    versions[sport][model_version] += 1


def summary(rows):
    n = len(rows)
    promised = sum(p for p, _ in rows) / n
    hit = sum(w for _, w in rows) / n
    brier = sum((p - w) ** 2 for p, w in rows) / n
    eps = 1e-6
    log_loss = -sum(math.log(max(eps, p if w else 1 - p)) for p, w in rows) / n
    base = hit
    brier_base = sum((base - w) ** 2 for _, w in rows) / n
    return n, promised, hit, brier, log_loss, brier_base


print("cut-off (starts_at <)", THROUGH)
for sport in sorted(groups, key=lambda s: (s != "ALLE", str(s))):
    rows = groups[sport]
    n, promised, hit, brier, log_loss, brier_base = summary(rows)
    print("%s: n %d | versprochen %.1f %% | eingetroffen %.1f %% | Brier %.4f (Grundquote %.4f) | LogLoss %.4f" % (
        sport, n, 100 * promised, 100 * hit, brier, brier_base, log_loss))
    for low, high in BINS:
        part = [(p, w) for p, w in rows if low <= p < high]
        if part:
            print("    %2d-%2d %%: n %5d | versprochen %.1f %% | eingetroffen %.1f %%" % (
                100 * low, min(100, 100 * high), len(part), 100 * sum(p for p, _ in part) / len(part),
                100 * sum(w for _, w in part) / len(part)))
    if sport != "ALLE":
        top = sorted(versions[sport].items(), key=lambda kv: -kv[1])[:3]
        print("    Modellversionen:", top)
