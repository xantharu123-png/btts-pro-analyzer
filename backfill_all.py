"""Resumable Statistik-Backfill für den gesamten Ligenkatalog (xG + Ecken + Karten).

Pro Liga werden die relevanten Saisons bestimmt: die aktuelle Spielzeit und —
falls diese noch kaum abgeschlossene Spiele hat (Sommerpause) — zusätzlich die
gerade beendete Vorsaison als Validierungsbasis. Alles landet im SQLite-Cache
(``xg_cache.db``); Mehrfachläufe sind idempotent und setzen einfach fort.

Nutzung:
    python backfill_all.py --budget 3500          # heutiges Call-Budget
    python backfill_all.py --budget 3500 --csv-first
"""

from __future__ import annotations

import argparse
import configparser
from datetime import date
from pathlib import Path

from football_data_history import FOOTBALL_DATA_DIVISIONS
from league_catalog import LEAGUES
from season_utils import current_season_start_year_for_id
from xg_backfill import (
    XG_CACHE_PATH,
    _provider_fetch,
    cached_stats,
    fetch_missing_xg,
    season_fixture_index,
)

CONFIG_PATH = Path(__file__).resolve().with_name("config.ini")


def _api_key() -> str:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    key = config.get("api", "api_football_key", fallback="").strip() or config.get(
        "api", "api_key", fallback=""
    ).strip()
    if not key:
        raise SystemExit("Kein API-Football-Key in config.ini gefunden")
    return key


def _seasons_for_league(league_id: int, today: date, fetch) -> list[tuple[int, int]]:
    """(season, index_size) — aktuelle Saison, plus Vorsaison wenn sie kaum Spiele hat."""
    current = current_season_start_year_for_id(league_id, today)
    index = season_fixture_index(league_id, current, fetch) or []
    seasons = [(current, len(index))]
    if len(index) < 100:
        previous = current - 1
        previous_index = season_fixture_index(league_id, previous, fetch) or []
        if previous_index:
            seasons.append((previous, len(previous_index)))
    return seasons


COMPLETE_MARKER = Path(__file__).resolve().with_name(".backfill_complete")


def run_backfill(budget: int, only: list[int] | None = None, log=print) -> dict:
    """Führt einen Backfill-Lauf aus. Idempotent; Resume über den SQLite-Cache."""
    fetch = _provider_fetch(_api_key())
    today = date.today()
    budget = max(0, int(budget))

    league_ids = [league.league_id for league in LEAGUES]
    if only:
        wanted = set(only)
        league_ids = [league_id for league_id in league_ids if league_id in wanted]
    # CSV-Ligen zuerst: dort entsteht das volle Modell (Ecken/Karten aus CSV
    # plus xG aus der API), danach alle übrigen Katalog-Ligen.
    league_ids.sort(key=lambda league_id: league_id not in FOOTBALL_DATA_DIVISIONS)

    cache = cached_stats(XG_CACHE_PATH)
    totals = {"calls": 0, "fetched": 0, "unavailable": 0, "leagues_done": 0,
              "complete": False, "budget_left": budget}
    for league_id in league_ids:
        if budget <= 0:
            log(f"Budget erschöpft — Abbruch vor Liga {league_id}.")
            break
        try:
            seasons = _seasons_for_league(league_id, today, fetch)
        except Exception as exc:  # einzelne Liga darf den Lauf nicht stoppen
            log(f"Liga {league_id}: Saisonbestimmung fehlgeschlagen ({exc})")
            continue
        for season, index_size in seasons:
            if budget <= 0:
                break
            index = season_fixture_index(league_id, season, fetch) or []
            open_ids = [entry for entry in index if entry["id"] not in cache]
            if not open_ids:
                continue
            calls = min(budget, len(open_ids))
            stats = fetch_missing_xg(
                open_ids, fetch, XG_CACHE_PATH, max_calls=calls, pause_seconds=0.25
            )
            used = stats["fetched"] + stats["unavailable"]
            budget -= used
            totals["calls"] += used
            totals["fetched"] += stats["fetched"]
            totals["unavailable"] += stats["unavailable"]
            log(
                f"Liga {league_id} Saison {season}: +{stats['fetched']} Stats "
                f"({stats['unavailable']} ohne), {index_size - len(open_ids) + stats['fetched']}"
                f"/{index_size} im Cache | Restbudget {budget}"
            )
        else:
            totals["leagues_done"] += 1

    totals["budget_left"] = budget
    totals["complete"] = totals["leagues_done"] == len(league_ids) and budget > 0
    if totals["complete"]:
        COMPLETE_MARKER.write_text(date.today().isoformat(), encoding="utf-8")
    log(
        f"Fertig: {totals['calls']} Calls, {totals['fetched']} Fixtures mit Statistik, "
        f"{totals['unavailable']} ohne Statistik, {totals['leagues_done']} Ligen komplett."
    )
    if not totals["complete"]:
        log("Nicht alles geschafft — nächster Lauf setzt automatisch fort (Resume).")
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=3500,
                        help="Maximale statistics-Calls in diesem Lauf (Default 3500)")
    parser.add_argument("--only", type=int, nargs="*", default=None,
                        help="Nur diese League-IDs (Default: ganzer Katalog)")
    args = parser.parse_args()
    run_backfill(args.budget, only=args.only)


if __name__ == "__main__":
    main()
