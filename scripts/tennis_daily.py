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
of the design); the edge gate is evaluated then.

Usage:
    python scripts/tennis_daily.py [YYYY-MM-DD]
"""

from __future__ import annotations

import sys
import unicodedata
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.data_loader import DEFAULT_CACHE_DIR  # noqa: E402
from tennis.model_state import load_state  # noqa: E402
from tennis.predict import predict_match  # noqa: E402
from tennis import shadow  # noqa: E402

import pandas as pd  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

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
        fixtures.append(
            {
                "tour": category.upper(),
                "tournament": tournament.get("name", ""),
                "player_a": ev.get("homeTeam", {}).get("name", ""),
                "player_b": ev.get("awayTeam", {}).get("name", ""),
                "match_date": date,
            }
        )
    return fixtures


def fetch_fixtures_espn(date: str) -> list:
    """ESPN scoreboard fallback (tournaments with nested match lists)."""
    yyyymmdd = date.replace("-", "")
    fixtures = []
    for tour in ("atp", "wta"):
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/tennis/"
            f"{tour}/scoreboard?dates={yyyymmdd}&limit=400"
        )
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            events = response.json().get("events", [])
        except (requests.RequestException, ValueError):
            continue
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
                    match_date = str(comp.get("date", ""))[:10] or date
                    fixtures.append(
                        {
                            "tour": tour.upper(),
                            "tournament": ev.get("name", ""),
                            "player_a": names[0],
                            "player_b": names[1],
                            "match_date": match_date,
                        }
                    )
    return fixtures


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
    date = sys.argv[1] if len(sys.argv) > 1 else (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    print(f"=== TENNIS DAILY SCAN {date} ===")

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
            fx["match_date"], fx["tour"], fx["tournament"], pred
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
