"""Live-Verifikation des vollen Stacks: CSV+Tail -> Stats/xG -> Kalibrierung -> Kandidaten.

Nutzung:
  python scripts/live_verification.py validate <league_id>   # Validierung rechnen + picklen
  python scripts/live_verification.py calibrate <league_id>  # Kalibrierung fitten + picklen
  python scripts/live_verification.py scan                   # naechste 7 Tage: Kandidaten
"""
import configparser
import pickle
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenge_engine import (  # noqa: E402
    adaptive_bin_threshold,
    build_fixture_candidates,
    candidate_is_credible,
    fit_market_calibration,
    validate_league_markets,
)
from football_data_history import fetch_history as fetch_stat_history  # noqa: E402
from football_data_history import merge_api_tail  # noqa: E402
from xg_backfill import annotate_history, _provider_fetch  # noqa: E402

LEAGUES = {78: "Bundesliga", 39: "Premier League", 140: "La Liga", 135: "Serie A", 61: "Ligue 1"}
SEASON = 2025
CACHE_DIR = ROOT / ".verification_cache"

cfg = configparser.ConfigParser()
cfg.read(ROOT / "config.ini", encoding="utf-8")
KEY = cfg.get("api", "api_football_key", fallback="").strip() or cfg.get(
    "api", "api_key", fallback=""
).strip()


def _cache_path(league_id: int, kind: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{kind}_{league_id}_{SEASON}.pkl"


def _load_history(league_id: int, with_tail: bool) -> list:
    history = fetch_stat_history(league_id, SEASON, []) or []
    if with_tail and history:
        fetch = _provider_fetch(KEY)
        today = date.today()
        tail = fetch(
            "fixtures",
            {
                "league": league_id,
                "season": SEASON,
                "status": "FT",
                "from": (today - timedelta(days=7)).isoformat(),
                "to": today.isoformat(),
                "timezone": "Europe/Zurich",
            },
            f"FT-Tail Liga {league_id}",
        )
        if tail:
            history = merge_api_tail(history, tail, tail_days=7)
    annotate_history(history, league_id, SEASON, _provider_fetch(KEY), max_new_calls=0)
    return history


def step_validate(league_id: int) -> None:
    history = _load_history(league_id, with_tail=False)
    metrics = validate_league_markets(history)
    with _cache_path(league_id, "validation").open("wb") as handle:
        pickle.dump(metrics, handle)
    print(f"{LEAGUES.get(league_id, league_id)}: Validierung ({len(history)} Spiele)")
    for market_key in ("RESULT_HOME", "DC_X2", "BTTS_YES", "TOTAL_OVER_2_5"):
        m = metrics.get(market_key)
        if m is None or not m.observations:
            continue
        thr = adaptive_bin_threshold(m.max_error_bin_mean_probability, m.max_error_bin_size)
        print(
            f"  {market_key:<16} n={m.observations:<4} Brier {m.raw_brier_score or 0:.3f} -> "
            f"{m.brier_score:.3f} | ECE {m.expected_calibration_error or 0:.3f} | "
            f"maxErr {m.max_calibration_error or 0:.3f} (Schwelle {thr:.3f}) | "
            f"Gate {'FREI' if m.passed else 'GESPERRT'}"
        )


def step_calibrate(league_id: int) -> None:
    history = _load_history(league_id, with_tail=False)
    curves = fit_market_calibration(history)
    with _cache_path(league_id, "calibration").open("wb") as handle:
        pickle.dump(curves, handle)
    print(f"{LEAGUES.get(league_id, league_id)}: {len(curves)} Kalibrierungskurven gefittet")
    for market_key in ("RESULT_HOME", "DC_X2", "BTTS_YES"):
        curve = curves.get(market_key)
        if curve is None:
            continue
        lo, hi = curve.points[0], curve.points[-1]
        print(
            f"  {market_key:<16} n={curve.samples:<4} Kurve: "
            f"({lo[0]:.2f}->{lo[1]:.2f}) ... ({hi[0]:.2f}->{hi[1]:.2f})"
        )


def step_scan() -> None:
    fetch = _provider_fetch(KEY)
    today = date.today()
    found_any = False
    for offset in range(0, 8):
        day = today + timedelta(days=offset)
        for league_id, name in LEAGUES.items():
            fixtures = fetch(
                "fixtures",
                {
                    "league": league_id,
                    "season": SEASON + 1,
                    "date": day.isoformat(),
                    "timezone": "Europe/Zurich",
                    "status": "NS",
                },
                f"Fixtures {name}",
            )
            if not fixtures:
                continue
            found_any = True
            print(f"\n=== {day.isoformat()} | {name}: {len(fixtures)} Spiele ===")
            validation_path = _cache_path(league_id, "validation")
            calibration_path = _cache_path(league_id, "calibration")
            if not validation_path.exists() or not calibration_path.exists():
                print("  (keine gecachten Artefakte — zuerst validate/calibrate laufen lassen)")
                continue
            with validation_path.open("rb") as handle:
                validation = pickle.load(handle)
            with calibration_path.open("rb") as handle:
                calibration = pickle.load(handle)
            history = _load_history(league_id, with_tail=True)
            for fixture in fixtures:
                teams = fixture.get("teams", {})
                label = (
                    f"{teams.get('home', {}).get('name', '?')} vs "
                    f"{teams.get('away', {}).get('name', '?')}"
                )
                candidates = build_fixture_candidates(fixture, history, validation, calibration)
                credible = [c for c in candidates if candidate_is_credible(c)]
                print(f"  {label}: {len(candidates)} Kandidaten, {len(credible)} glaubwuerdig")
                for c in sorted(credible, key=lambda item: -item.evidence_score)[:3]:
                    print(
                        f"    {c.market_key:<22} p={c.probability:.3f} "
                        f"konservativ={c.conservative_probability:.3f} "
                        f"evidence={c.evidence_score:.1f}"
                    )
    if not found_any:
        print(
            f"Keine anstehenden Spiele der Top-5-Ligen in den naechsten 7 Tagen "
            f"(ab {today.isoformat()}) — Sommerpause. Der Stack ist rechenseitig "
            f"verifiziert (siehe validate/calibrate); Live-Kandidaten gibt es "
            f"wieder zum Saisonstart bzw. ueber die Shadow-Automation mit "
            f"Sommerligen."
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    step = sys.argv[1]
    if step in {"validate", "calibrate"}:
        if len(sys.argv) < 3:
            raise SystemExit("league_id fehlt")
        globals()[f"step_{step}"](int(sys.argv[2]))
    elif step == "scan":
        step_scan()
    else:
        raise SystemExit(f"unbekannter Schritt: {step}")
