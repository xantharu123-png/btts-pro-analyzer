"""Daily tennis scan: fixtures -> model -> shadow store.

Fetches tomorrow's (or a given date's) ATP/WTA fixtures, maps each
tournament to its surface, runs the full model stack (Surface-Elo +
serve simulator + calibrator) and stores every prediction in the
tennis shadow DB BEFORE the matches.

Fixture sources: SofaScore scheduled events (blocked on many hosts)
with ESPN scoreboard fallback (works).  Sponsor tournament names
('Mifel Tennis Open by Telcel Oppo') are resolved to official names
via TOURNAMENT_ALIASES — unknown surfaces fail the surface gate
honestly (NO BET), never guessed.

N1Bet prices are entered later in the app (manual price entry is part
of the design); the uncertainty-adjusted EV price gate is evaluated then.

Usage:
    python scripts/tennis_daily.py [YYYY-MM-DD]
"""

from __future__ import annotations

import json
import sys
import unicodedata
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.data_loader import DEFAULT_CACHE_DIR, normalize_player_name  # noqa: E402
from tennis.model_state import load_state  # noqa: E402
from tennis.predict import predict_match  # noqa: E402
from tennis import shadow  # noqa: E402

import pandas as pd  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
ZURICH_TZ = ZoneInfo("Europe/Zurich")

# sponsor/broadcast name (normalized substring) -> official tournament
# name in the ManTennisData table.  Extend weekly as new events appear;
# a missing alias means surface UNKNOWN -> gate red -> NO BET.
TOURNAMENT_ALIASES = {
    "mifel tennis open": "Los Cabos",
    "abierto de tenis mifel": "Los Cabos",
    "dc open": "Washington",
    "citi open": "Washington",
    "mubadala dc open": "Washington",
    "odlum brown": "Vancouver",
    "vanopen": "Vancouver",
    "memphis classic": "Memphis",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _start_metadata(value, fallback_date: str) -> tuple[str | None, str]:
    """Return (UTC ISO timestamp, Zurich match date) for a provider value."""
    if value in (None, ""):
        return None, fallback_date
    try:
        if isinstance(value, (int, float)):
            start = datetime.fromtimestamp(float(value), timezone.utc)
        else:
            start = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        start = start.astimezone(timezone.utc)
    except (TypeError, ValueError, OSError):
        return None, fallback_date
    start_utc = start.isoformat(timespec="seconds").replace("+00:00", "Z")
    return start_utc, start.astimezone(ZURICH_TZ).date().isoformat()


def _default_scan_date(now: datetime | None = None) -> str:
    current = now or datetime.now(ZURICH_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZURICH_TZ)
    local_day = current.astimezone(ZURICH_TZ).date()
    return (local_day + timedelta(days=1)).isoformat()


def tournament_surface_map(year: int) -> dict:
    """normalized official name/location/slug -> (surface, best_of, name, indoor)."""
    path = DEFAULT_CACHE_DIR / "atp_tournaments.csv"
    df = pd.read_csv(path)
    df = df[df["year"] == year]
    mapping = {}
    for row in df.itertuples(index=False):
        best_of = 5 if row.series_category_id == "gs" else 3
        indoor = getattr(row, "indoor_outdoor", None) == "Indoor"
        for token in {row.name, row.location, row.slug}:
            key = _norm(token)
            if key:
                mapping[key] = (row.surface, best_of, row.name, indoor)
    return mapping


def resolve_surface(tournament_name: str, surfaces: dict):
    """(surface, best_of, official_name, indoor) or (None, 3, None, None)."""
    t_norm = _norm(tournament_name)
    for alias, official in TOURNAMENT_ALIASES.items():
        if alias in t_norm:
            hit = surfaces.get(_norm(official))
            if hit:
                return hit
    for key, val in surfaces.items():
        if key and key in t_norm:
            return val
    return None, 3, None, None


# ------------------------------------------------------------------- fixtures


def fetch_fixtures_sofascore(date: str) -> list:
    url = f"https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{date}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    fixtures = []
    for ev in response.json().get("events", []):
        if ev.get("status", {}).get("type") != "notstarted":
            continue
        tournament = ev.get("tournament", {})
        category = (tournament.get("category") or {}).get("slug", "")
        if category not in ("atp", "wta"):
            continue
        start_utc, match_date = _start_metadata(ev.get("startTimestamp"), date)
        fixtures.append(
            {
                "tour": category.upper(),
                "tournament": tournament.get("name", ""),
                "player_a": ev.get("homeTeam", {}).get("name", ""),
                "player_b": ev.get("awayTeam", {}).get("name", ""),
                "match_date": match_date,
                "provider_event_id": str(ev.get("id") or ""),
                "scheduled_start_utc": start_utc,
                "fixture_source": "SofaScore",
            }
        )
    return fixtures


def fetch_fixtures_espn(date: str) -> list:
    """ESPN scoreboard fallback (tournaments with nested match lists)."""
    fixtures = []
    for tour in ("atp", "wta"):
        events = _fetch_espn_events(tour, date)
        want_slug = "mens-singles" if tour == "atp" else "womens-singles"
        for ev in events:
            for grouping in ev.get("groupings", []):
                if grouping.get("grouping", {}).get("slug") != want_slug:
                    continue
                for comp in grouping.get("competitions", []):
                    state = comp.get("status", {}).get("type", {}).get("state")
                    if state != "pre":
                        continue
                    names = [
                        c.get("athlete", {}).get("displayName")
                        for c in comp.get("competitors", [])
                    ]
                    if len(names) != 2 or not all(names):
                        continue
                    start_utc, match_date = _start_metadata(comp.get("date"), date)
                    fixtures.append(
                        {
                            "tour": tour.upper(),
                            "tournament": ev.get("name", ""),
                            "player_a": names[0],
                            "player_b": names[1],
                            "match_date": match_date,
                            "provider_event_id": str(comp.get("id") or ""),
                            "scheduled_start_utc": start_utc,
                            "fixture_source": "ESPN",
                        }
                    )
    return fixtures


def _fetch_espn_events(tour: str, date: str) -> list:
    yyyymmdd = date.replace("-", "")
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/tennis/"
        f"{tour}/scoreboard?dates={yyyymmdd}&limit=400"
    )
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.json().get("events", [])
    except (requests.RequestException, ValueError):
        return []


def fetch_results_espn(date: str, tour: str) -> list:
    """Return unambiguous normal finals for one tour/date."""
    tour_slug = str(tour).lower()
    want_slug = "mens-singles" if tour_slug == "atp" else "womens-singles"
    results = []
    for event in _fetch_espn_events(tour_slug, date):
        for grouping in event.get("groupings", []):
            if grouping.get("grouping", {}).get("slug") != want_slug:
                continue
            for comp in grouping.get("competitions", []):
                status_type = comp.get("status", {}).get("type", {})
                status_blob = json.dumps(
                    {
                        "status": comp.get("status", {}),
                        "notes": comp.get("notes", []),
                    },
                    ensure_ascii=False,
                ).casefold()
                abnormal_tokens = (
                    "retired",
                    "retirement",
                    "ret.",
                    "ret'd",
                    "walkover",
                    "w/o",
                    "defaulted",
                    "abandoned",
                )
                if (
                    status_type.get("state") != "post"
                    or status_type.get("completed") is not True
                    or status_type.get("name") != "STATUS_FINAL"
                    or any(token in status_blob for token in abnormal_tokens)
                ):
                    continue
                competitors = comp.get("competitors", [])
                winners = [
                    item for item in competitors if item.get("winner") is True
                ]
                names = [
                    item.get("athlete", {}).get("displayName")
                    for item in competitors
                ]
                if len(competitors) != 2 or len(winners) != 1 or not all(names):
                    continue
                winner_sets = sum(
                    1
                    for line in winners[0].get("linescores", [])
                    if line.get("winner") is True
                )
                loser = next(
                    item
                    for item in competitors
                    if item.get("winner") is not True
                )
                loser_sets = sum(
                    1
                    for line in loser.get("linescores", [])
                    if line.get("winner") is True
                )
                if winner_sets < 2:
                    continue
                start_utc, match_date = _start_metadata(comp.get("date"), date)
                if match_date != date:
                    continue
                results.append(
                    {
                        "provider_event_id": str(comp.get("id") or ""),
                        "match_date": match_date,
                        "scheduled_start_utc": start_utc,
                        "player_a": names[0],
                        "player_b": names[1],
                        "winner": winners[0].get("athlete", {}).get("displayName"),
                        "winner_sets": winner_sets,
                        "loser_sets": loser_sets,
                    }
                )
    return results


def auto_settle_completed(today: str | None = None) -> int:
    """Settle old normal finals; retirements and ambiguous rows stay manual."""
    local_today = today or datetime.now(ZURICH_TZ).date().isoformat()
    pending = [
        row
        for row in shadow.pending_predictions()
        if row["match_date"] < local_today
        and not any(
            "TBD" in str(player).upper()
            for player in (row["player_a"], row["player_b"])
        )
    ]
    if not pending:
        return 0

    result_cache = {}
    settled = 0
    for row in pending:
        cache_key = (row["match_date"], str(row["tour"]).upper())
        if cache_key not in result_cache:
            result_cache[cache_key] = fetch_results_espn(*cache_key)
        row_players = {
            normalize_player_name(row["player_a"]),
            normalize_player_name(row["player_b"]),
        }
        match = None
        event_id = str(row.get("provider_event_id") or "")
        if event_id:
            match = next(
                (
                    result
                    for result in result_cache[cache_key]
                    if result["provider_event_id"] == event_id
                ),
                None,
            )
        if match is None:
            match = next(
                (
                    result
                    for result in result_cache[cache_key]
                    if {
                        normalize_player_name(result["player_a"]),
                        normalize_player_name(result["player_b"]),
                    }
                    == row_players
                ),
                None,
            )
        if match is None:
            continue
        winner_key = normalize_player_name(match["winner"])
        if winner_key == normalize_player_name(row["player_a"]):
            winner = row["player_a"]
            set_result = f"{match['winner_sets']}:{match['loser_sets']}"
        elif winner_key == normalize_player_name(row["player_b"]):
            winner = row["player_b"]
            set_result = f"{match['loser_sets']}:{match['winner_sets']}"
        else:
            continue
        shadow.settle(row["id"], winner)
        for bet in shadow.side_bets_for([row["id"]]):
            if not bet["settled"]:
                shadow.settle_side_bet(bet["id"], set_result)
        settled += 1
    return settled


def fetch_fixtures(date: str) -> list:
    try:
        fixtures = fetch_fixtures_sofascore(date)
        if fixtures:
            return fixtures
    except requests.RequestException:
        pass
    return fetch_fixtures_espn(date)


# ----------------------------------------------------------------------- main


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else _default_scan_date()
    print(f"=== TENNIS DAILY SCAN {date} ===")
    settled = auto_settle_completed()
    print(f"Automatisch abgerechnet (normale ESPN-Finals): {settled}")

    try:
        state = load_state()
    except FileNotFoundError:
        # Z.B. erster Start auf Streamlit Cloud: State aus den Repo-Daten
        # einmalig neu bauen (mehrere Minuten), statt mit Traceback zu sterben.
        print("Modell-State fehlt — baue neu aus den mitgelieferten Daten ...")
        from tennis.model_state import build_state, save_state

        state = build_state()
        save_state(state)
        print("Modell-State gebaut und gespeichert.")
    print(f"Modell-Stand: Daten bis {state.stats_through}, Kalibrator n={state.cal_samples}")

    surfaces = tournament_surface_map(int(date[:4]))
    fixtures = fetch_fixtures(date)
    print(f"Fixtures (ATP/WTA Singles, noch nicht gestartet): {len(fixtures)}\n")

    stored = 0
    for fx in fixtures:
        if not fx["player_a"] or not fx["player_b"] or "TBD" in (
            fx["player_a"],
            fx["player_b"],
        ):
            continue  # qualifiers not yet decided — nothing to audit
        surface, best_of, official, indoor = resolve_surface(fx["tournament"], surfaces)
        pred = predict_match(
            state,
            fx["player_a"],
            fx["player_b"],
            surface,
            best_of,
            tour=fx.get("tour", "ATP"),
            indoor=indoor,
        )
        row_id = shadow.store_prediction(
            fx["match_date"],
            fx["tour"],
            fx["tournament"],
            pred,
            provider_event_id=fx.get("provider_event_id") or None,
            scheduled_start_utc=fx.get("scheduled_start_utc"),
            fixture_source=fx.get("fixture_source"),
        )
        if row_id > 0:
            stored += 1
        gates_ok = all(g.passed for g in pred.gates)
        flag = "GRUEN" if gates_ok else "rot "
        print(
            f"[{flag}] {fx['tour']:3} {fx['player_a']} vs {fx['player_b']} "
            f"({fx['tournament']}, {surface or 'Belag?'}, Bo{best_of}) "
            f"p={pred.p_a_cal:.1%} / {pred.p_b_cal:.1%}"
        )
        if not gates_ok:
            for g in pred.gates:
                if not g.passed:
                    print(f"        Sperre: {g.name} — {g.detail}")

    print(f"\nGespeichert: {stored} neue Predictions (Duplikate uebersprungen)")
    print("Shadow-Stand:", shadow.summary())


if __name__ == "__main__":
    main()
