"""Zeigt pro Markt, welche Gate-Bedingung bindet (Liga als argv[1])."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_engine import adaptive_bin_threshold, validate_league_markets
from football_data_history import fetch_history as fetch_stat_history
from xg_backfill import annotate_history, _provider_fetch
import configparser

cfg = configparser.ConfigParser()
cfg.read(Path(__file__).resolve().parents[1] / "config.ini", encoding="utf-8")
key = cfg.get("api", "api_football_key", fallback="").strip() or cfg.get("api", "api_key", fallback="").strip()

league_id = int(sys.argv[1])
history = fetch_stat_history(league_id, 2025, [])
annotate_history(history, league_id, 2025, _provider_fetch(key), max_new_calls=0)
metrics = validate_league_markets(history)

print(f"{'Markt':<24} {'n':>4} {'Verb.':>7} {'ECE':>6} {'Bins':>4} {'minBin':>6} {'maxErr':>7} {'Schwelle':>8} | bindet")
print("-" * 100)
for market_key in sorted(metrics, key=lambda k: -(metrics[k].relative_improvement or -9))[:14]:
    m = metrics[market_key]
    if not m.observations:
        continue
    thr = adaptive_bin_threshold(m.max_error_bin_mean_probability, m.max_error_bin_size)
    binds = []
    if m.observations < 200: binds.append("n<200")
    if (m.relative_improvement or 0) < 0.02: binds.append("Verb.<2%")
    if (m.expected_calibration_error or 1) > 0.08: binds.append("ECE>0.08")
    if m.calibration_bins < 3: binds.append(f"Bins={m.calibration_bins}<3")
    if m.min_bin_size < 20: binds.append(f"minBin={m.min_bin_size}<20")
    if m.max_calibration_error is not None and m.max_calibration_error > thr: binds.append("Bin-Fehler")
    print(f"{market_key:<24} {m.observations:>4} {(m.relative_improvement or 0):>7.3f} "
          f"{(m.expected_calibration_error or 0):>6.3f} {m.calibration_bins:>4} {m.min_bin_size:>6} "
          f"{(m.max_calibration_error or 0):>7.3f} {thr:>8.3f} | {', '.join(binds) or 'FREI ✓'}")
