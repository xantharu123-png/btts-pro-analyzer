"""Diagnose: Wo faellt ein Shadow-Fixture aus dem Logging? (argv: fixture_id league_id season)"""
import configparser
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenge_engine import (  # noqa: E402
    apply_candidate_context,
    build_fixture_candidates,
    candidate_is_credible,
    fit_market_calibration,
    validate_league_markets,
)
from football_data_history import fetch_history as fetch_stat_history  # noqa: E402
from xg_backfill import annotate_history, _provider_fetch  # noqa: E402

cfg = configparser.ConfigParser()
cfg.read(ROOT / "config.ini", encoding="utf-8")
key = cfg.get("api", "api_football_key", fallback="").strip() or cfg.get("api", "api_key", fallback="").strip()
fetch = _provider_fetch(key)

fixture_id, league_id, season = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])

detail_list = fetch("fixtures", {"id": fixture_id}, "Fixture-Detail")
detail = detail_list[0] if detail_list else None
assert detail, "kein Fixture-Detail"
teams = detail.get("teams", {})
print(f"Fixture: {teams.get('home', {}).get('name')} vs {teams.get('away', {}).get('name')} (Liga {league_id})")

history = fetch_stat_history(league_id, season, [detail])
source = "CSV"
if not history:
    history = fetch("fixtures", {"league": league_id, "season": season, "status": "FT"}, "Historie") or []
    source = "API-FT"
current_count = len(history)
if len(history) < 220 and season > 2020:
    previous = fetch_stat_history(league_id, season - 1, [detail])
    if not previous:
        previous = fetch("fixtures", {"league": league_id, "season": season - 1, "status": "FT"}, "Vorsaison") or []
    if previous:
        history = list(previous) + list(history)
        source += f"+Vorsaison({len(previous)})"
print(f"Historie: {len(history)} Spiele ({source}, aktuelle Saison: {current_count})")
annotate_history(history, league_id, season, fetch, max_new_calls=4)

validation = validate_league_markets(history)
print("\nValidierung (Top-Maerkte nach n):")
for market_key in sorted(validation, key=lambda k: -validation[k].observations)[:8]:
    m = validation[market_key]
    print(f"  {market_key:<22} n={m.observations:<4} Verb={m.relative_improvement or 0:.3f} "
          f"ECE={m.expected_calibration_error or 0:.3f} passed={m.passed}")

calibration = fit_market_calibration(history)
print(f"\nKalibrierungskurven: {len(calibration)}")

candidates = build_fixture_candidates(detail, history, validation, calibration)
print(f"\nKandidaten gesamt: {len(candidates)}")
for c in candidates:
    if c.market_key in {"BTTS_YES", "BTTS_NO", "RESULT_HOME", "DC_X2", "DC_1X"}:
        print(f"  {c.market_key:<22} base={c.base_eligible} p={c.probability:.3f} "
              f"kons={c.conservative_probability:.3f} evid={c.evidence_score:.1f} "
              f"valid={'JA' if c.validation and c.validation.passed else 'NEIN'}")

btts = [c for c in candidates if c.market_key in {"BTTS_YES", "BTTS_NO"} and c.base_eligible]
print(f"\nBTTS base_eligible: {len(btts)}")
credible = []
for c in btts:
    apply_candidate_context(c, h2h_fixtures=None, injuries=None, injury_coverage=False,
                            weather=None, lineups=None)
    if candidate_is_credible(c):
        credible.append(c)
print(f"BTTS credible nach Kontext: {len(credible)}")

all_credible = []
coverage_data = fetch("leagues", {"id": league_id, "season": season}, "Coverage")
coverage = {"injuries": False, "lineups": False}
if coverage_data:
    seasons_list = coverage_data[0].get("seasons") or []
    for s in seasons_list:
        if isinstance(s, dict) and s.get("year") == season:
            cov = s.get("coverage") or {}
            fixtures_cov = cov.get("fixtures") or {}
            coverage = {
                "injuries": bool(cov.get("injuries")),
                "lineups": bool(fixtures_cov.get("lineups")),
            }
print(f"Coverage: {coverage}")
home_id = teams.get("home", {}).get("id")
away_id = teams.get("away", {}).get("id")
h2h = fetch("fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "status": "FT", "last": 10}, "H2H") if home_id and away_id else None
injuries = fetch("injuries", {"fixture": fixture_id}, "Verletzungen") if coverage.get("injuries") else None
print(f"H2H-Spiele: {len(h2h or [])}, Verletzungen gemeldet: {len(injuries or [])}")
for c in candidates:
    if not c.base_eligible:
        continue
    apply_candidate_context(c, h2h_fixtures=h2h, injuries=injuries,
                            injury_coverage=bool(coverage.get("injuries")),
                            weather=None, lineups=None)
    if candidate_is_credible(c):
        all_credible.append(c)
    else:
        reasons = (c.context or {}).get("blocked_reasons", [])
        print(f"  BLOCKIERT {c.market_key:<20} kons={c.conservative_probability:.3f} -> {reasons}")
print(f"Alle Maerkte credible: {len(all_credible)}")
for c in sorted(all_credible, key=lambda x: -x.conservative_probability)[:5]:
    print(f"  {c.market_key:<22} kons={c.conservative_probability:.3f} evid={c.evidence_score:.1f}")

odds = fetch("odds", {"fixture": fixture_id}, "Quoten")
if odds:
    bets = odds[0].get("bookmakers", [{}])[0].get("bets", [])
    print(f"\nQuoten-Maerkte im Buchmacher-Block: {sorted({b.get('name') for b in bets})[:20]}")
else:
    print("\nKeine Quoten fuer dieses Fixture")
