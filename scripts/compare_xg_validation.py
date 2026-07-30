"""Vergleicht die Walk-forward-Validierung ohne vs. mit xG-Hybrid pro Liga."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_engine import validate_league_markets
from football_data_history import fetch_history as fetch_stat_history
from xg_backfill import annotate_history, _provider_fetch
import configparser

LEAGUES = {78: "Bundesliga", 39: "Premier League", 140: "La Liga"}
SEASON = 2025

cfg = configparser.ConfigParser()
cfg.read(Path(__file__).resolve().parents[1] / "config.ini", encoding="utf-8")
key = cfg.get("api", "api_football_key", fallback="").strip() or cfg.get("api", "api_key", fallback="").strip()
fetch = _provider_fetch(key)

league_id = int(sys.argv[1])
history_plain = fetch_stat_history(league_id, SEASON, [])
print(f"{LEAGUES.get(league_id, league_id)}: {len(history_plain)} Spiele aus football-data CSV")

history_xg = copy.deepcopy(history_plain)
result = annotate_history(history_xg, league_id, SEASON, fetch, max_new_calls=0)
print(f"xG annotiert: {result['annotated']}/{result['total']} ({result['coverage']:.0%})")

print("Validiere ohne xG ...")
metrics_plain = validate_league_markets(history_plain)
print("Validiere mit xG ...")
metrics_xg = validate_league_markets(history_xg)

print(f"\n{'Markt':<28} {'n':>4} | {'Brier ohne':>10} {'Brier mit':>10} {'Delta':>8} | "
      f"{'Verb. ohne':>10} {'Verb. mit':>10} | {'ECE ohne':>8} {'ECE mit':>8} | Gate")
print("-" * 125)
for market_key in sorted(metrics_plain, key=lambda k: -(metrics_plain[k].observations or 0)):
    plain = metrics_plain[market_key]
    xg = metrics_xg[market_key]
    if not plain.observations:
        continue
    delta = (xg.brier_score - plain.brier_score) if xg.brier_score is not None else None
    print(
        f"{market_key:<28} {plain.observations:>4} | "
        f"{plain.brier_score:>10.4f} {xg.brier_score:>10.4f} {delta:>+8.4f} | "
        f"{(plain.relative_improvement or 0):>10.4f} {(xg.relative_improvement or 0):>10.4f} | "
        f"{(plain.expected_calibration_error or 0):>8.4f} {(xg.expected_calibration_error or 0):>8.4f} | "
        f"{'JA' if xg.passed else 'nein'}"
    )
