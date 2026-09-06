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
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.data_loader import DEFAULT_CACHE_DIR, normalize_player_name  # noqa: E402
from tennis.model_state import load_state  # noqa: E402
from tennis.predict import predict_match  # noqa: E402
from tennis import shadow  # noqa: E402
from tennis.prediction_revisions import utc_epoch  # noqa: E402

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
    "national bank open": "Montreal",
    "rogers cup": "Montreal",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def provider_surface(value: object) -> tuple[str | None, bool | None]:
    """Translate an explicit scoreboard court description when available."""
    normalized = _norm(str(value or ""))
    if not normalized:
        return None, None
    if "indoor" in normalized:
        indoor = True
    elif "outdoor" in normalized:
        indoor = False
    else:
        indoor = None
    if "hard" in normalized or "acrylic" in normalized:
        return "Hard", indoor
    if "clay" in normalized or "sand" in normalized:
        return "Clay", indoor
    if "grass" in normalized:
        return "Grass", indoor
    if "carpet" in normalized:
        return "Carpet", indoor
    return None, indoor


def merge_surface(
    provider_value: str | None,
    catalog_value: str | None,
) -> str | None:
    """Prefer explicit data, but fail closed when two sources disagree."""
    if provider_value and catalog_value and provider_value != catalog_value:
        return None
    return provider_value or catalog_value


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
        event_id = ev.get("id")
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id <= 0:
            continue
        tournament = ev.get("tournament", {})
        category = (tournament.get("category") or {}).get("slug", "")
        if category not in ("atp", "wta"):
            continue
        start_utc, match_date = _start_metadata(ev.get("startTimestamp"), date)
        surface, indoor = provider_surface(
            ev.get("groundType") or tournament.get("groundType")
        )
        fixtures.append(
            {
                "tour": category.upper(),
                "tournament": tournament.get("name", ""),
                "player_a": ev.get("homeTeam", {}).get("name", ""),
                "player_b": ev.get("awayTeam", {}).get("name", ""),
                "match_date": match_date,
                "provider_event_id": str(event_id),
                "scheduled_start_utc": start_utc,
                "fixture_source": "SofaScore",
                "surface": surface,
                "indoor": indoor,
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
                    surface, indoor = provider_surface(
                        comp.get("groundType")
                        or comp.get("surface")
                        or ev.get("groundType")
                        or ev.get("surface")
                    )
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
                            "surface": surface,
                            "indoor": indoor,
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


def fetch_results_sofascore(date: str) -> list:
    """Return strictly evidenced SofaScore terminals for one schedule date."""
    url = f"https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{date}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        events = response.json().get("events", [])
    except (requests.RequestException, ValueError, AttributeError):
        return []
    result_observed_at = datetime.now(timezone.utc).isoformat()
    results = []
    for event in events:
        tournament = event.get("tournament") or {}
        category = (tournament.get("category") or {}).get("slug", "")
        if category not in ("atp", "wta"):
            continue
        event_id = event.get("id")
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id <= 0:
            continue
        provider_event_id = str(event_id)
        player_a = str((event.get("homeTeam") or {}).get("name") or "").strip()
        player_b = str((event.get("awayTeam") or {}).get("name") or "").strip()
        if not provider_event_id or not player_a or not player_b:
            continue
        start_utc, match_date = _start_metadata(event.get("startTimestamp"), date)
        if match_date != date:
            continue
        status = event.get("status") or {}
        status_type = str(status.get("type") or "").strip().casefold()
        status_blob = json.dumps(status, ensure_ascii=False).casefold()
        is_retirement = any(
            token in status_blob
            for token in ("retired", "retirement", "ret.", "ret'd")
        )
        is_walkover = any(
            token in status_blob for token in ("walkover", "walk-over", "w/o")
        )
        if (
            is_retirement and is_walkover
            or any(token in status_blob for token in ("defaulted", "abandoned"))
        ):
            continue
        common = {
            "provider_event_id": provider_event_id,
            "match_date": match_date,
            "scheduled_start_utc": start_utc,
            "player_a": player_a,
            "player_b": player_b,
            "result_observed_at": result_observed_at,
        }
        if is_retirement and status_type not in {"retired", "finished"}:
            continue
        if is_walkover and status_type not in {
            "walkover",
            "canceled",
            "cancelled",
            "finished",
        }:
            continue
        if is_retirement or is_walkover:
            results.append(
                {
                    **common,
                    "winner": None,
                    "winner_sets": None,
                    "loser_sets": None,
                    "termination": "retirement" if is_retirement else "walkover",
                }
            )
            continue
        if status_type != "finished":
            continue
        winner_code = event.get("winnerCode")
        if isinstance(winner_code, bool) or winner_code not in (1, 2):
            continue
        home_sets = (event.get("homeScore") or {}).get("current")
        away_sets = (event.get("awayScore") or {}).get("current")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (home_sets, away_sets)
        ):
            continue
        if (winner_code == 1 and home_sets <= away_sets) or (
            winner_code == 2 and away_sets <= home_sets
        ):
            continue
        winner_is_a = winner_code == 1
        results.append(
            {
                **common,
                "winner": player_a if winner_is_a else player_b,
                "winner_sets": home_sets if winner_is_a else away_sets,
                "loser_sets": away_sets if winner_is_a else home_sets,
                "termination": "normal",
            }
        )
    return results


def fetch_results_espn(date: str, tour: str) -> list:
    """Return only unambiguous normal, retirement, or walkover terminals."""
    tour_slug = str(tour).lower()
    want_slug = "mens-singles" if tour_slug == "atp" else "womens-singles"
    results = []
    events = _fetch_espn_events(tour_slug, date)
    result_observed_at = datetime.now(timezone.utc).isoformat()
    for event in events:
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
                retirement_tokens = (
                    "retired",
                    "retirement",
                    "ret.",
                    "ret'd",
                )
                walkover_tokens = (
                    "walkover",
                    "w/o",
                    "walk-over",
                )
                unsupported_tokens = (
                    "defaulted",
                    "abandoned",
                )
                is_retirement = any(
                    token in status_blob for token in retirement_tokens
                )
                is_walkover = any(token in status_blob for token in walkover_tokens)
                if (
                    status_type.get("state") != "post"
                    or status_type.get("completed") is not True
                    or (is_retirement and is_walkover)
                    or any(token in status_blob for token in unsupported_tokens)
                ):
                    continue
                competitors = comp.get("competitors", [])
                names = [
                    item.get("athlete", {}).get("displayName")
                    for item in competitors
                ]
                if len(competitors) != 2 or not all(names):
                    continue
                start_utc, match_date = _start_metadata(comp.get("date"), date)
                if match_date != date:
                    continue
                if is_retirement or is_walkover:
                    results.append(
                        {
                            "provider_event_id": str(comp.get("id") or ""),
                            "match_date": match_date,
                            "scheduled_start_utc": start_utc,
                            "player_a": names[0],
                            "player_b": names[1],
                            "winner": None,
                            "winner_sets": None,
                            "loser_sets": None,
                            "termination": (
                                "retirement" if is_retirement else "walkover"
                            ),
                            "result_observed_at": result_observed_at,
                        }
                    )
                    continue
                if status_type.get("name") != "STATUS_FINAL":
                    continue
                winners = [
                    item for item in competitors if item.get("winner") is True
                ]
                if len(winners) != 1:
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
                        "termination": "normal",
                        "result_observed_at": result_observed_at,
                    }
                )
    return results


def auto_settle_completed(today: str | None = None) -> int:
    """Settle old explicit terminals through their exact fixture provider."""
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
        fixture_source = str(row.get("fixture_source") or "").strip().casefold()
        if fixture_source == "sofascore":
            cache_key = ("sofascore", row["match_date"])
            if cache_key not in result_cache:
                result_cache[cache_key] = fetch_results_sofascore(row["match_date"])
        elif fixture_source == "espn":
            cache_key = (
                "espn",
                row["match_date"],
                str(row["tour"]).upper(),
            )
            if cache_key not in result_cache:
                result_cache[cache_key] = fetch_results_espn(
                    row["match_date"],
                    str(row["tour"]).upper(),
                )
        else:
            continue
        row_players = {
            normalize_player_name(row["player_a"]),
            normalize_player_name(row["player_b"]),
        }
        event_id = str(row.get("provider_event_id") or "").strip()
        if not event_id:
            continue
        match = next(
            (
                result
                for result in result_cache[cache_key]
                if result["provider_event_id"] == event_id
            ),
            None,
        )
        if match is None:
            continue
        match_players = {
            normalize_player_name(str(match.get("player_a") or "")),
            normalize_player_name(str(match.get("player_b") or "")),
        }
        if match_players != row_players:
            continue
        termination = str(match.get("termination") or "").strip().casefold()
        result_observed_at = match.get("result_observed_at")
        if not isinstance(result_observed_at, (datetime, str)):
            continue
        if termination in {"retirement", "walkover"}:
            try:
                shadow.settle(
                    row["id"],
                    None,
                    termination=termination,
                    result_observed_at=result_observed_at,
                )
            except (TypeError, ValueError):
                continue
            for bet in shadow.side_bets_for([row["id"]]):
                if not bet["settled"]:
                    shadow.settle_side_bet(bet["id"], "ret")
            settled += 1
            continue
        if termination != "normal":
            continue
        winner_key = normalize_player_name(match["winner"])
        if winner_key == normalize_player_name(row["player_a"]):
            winner = row["player_a"]
            player_a_sets = match["winner_sets"]
            player_b_sets = match["loser_sets"]
        elif winner_key == normalize_player_name(row["player_b"]):
            winner = row["player_b"]
            player_a_sets = match["loser_sets"]
            player_b_sets = match["winner_sets"]
        else:
            continue
        set_result = f"{player_a_sets}:{player_b_sets}"
        try:
            shadow.settle(
                row["id"],
                winner,
                termination="normal",
                result_observed_at=result_observed_at,
                player_a_sets=player_a_sets,
                player_b_sets=player_b_sets,
                match_duration_minutes=match.get("duration_minutes"),
            )
        except (TypeError, ValueError):
            continue
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


def _refresh_now() -> datetime:
    return datetime.fromtimestamp(time.time(), timezone.utc)


def refresh_pending_predictions(
    *,
    db_path: str | Path | None = None,
    as_of: datetime | None = None,
    minimum_interval: timedelta = timedelta(hours=2),
) -> dict:
    """Refresh due pending fixtures from the existing state without network I/O.

    This is the lightweight worker path, not the daily data pipeline. It never
    downloads, builds, fits, settles, or modifies prices. Fixture metadata is
    the latest stored observation; newly scheduled/changed fixtures still
    come from the fixture scan. ``stats_through`` always remains the actual
    cached model's training cutoff, not this refresh timestamp.

    All consumers read the same appended model revision. An unavailable state
    or invalid fixture leaves the previous immutable observation intact and is
    explicitly reported; a refresh is not represented as a fresh provider check.
    """
    if not isinstance(minimum_interval, timedelta) or minimum_interval.total_seconds() < 0:
        raise ValueError("minimum_interval must be a non-negative timedelta")
    checked_at = _refresh_now() if as_of is None else datetime.fromtimestamp(utc_epoch(as_of), timezone.utc)
    rows = shadow.latest_predictions(db_path, as_of=checked_at)
    result = {
        "status": "unchanged", "checked": len(rows), "due": 0,
        "refreshed": 0, "skipped": 0, "errors": [],
        "checked_at": checked_at.isoformat(), "completed_at": checked_at.isoformat(),
        "fixture_source": "stored_pending_fixtures", "provider_checked": False,
        "model_stats_through": None,
    }
    # Several historical model versions can reference the same event. Refresh
    # it once using its latest stored fixture metadata, never once per version.
    by_event = {}
    for row in rows:
        try:
            source = str(row.get("fixture_source") or "").strip()
            event_id = str(row.get("provider_event_id") or "").strip()
            players = (str(row.get("player_a") or "").strip(), str(row.get("player_b") or "").strip())
            if not source or not event_id or not all(players) or any("TBD" in p.upper() for p in players):
                raise ValueError("incomplete fixture identity")
            start = utc_epoch(row.get("scheduled_start_utc"))
            if start <= checked_at.timestamp():
                result["skipped"] += 1
                continue
            if row.get("tour") not in ("ATP", "WTA") or type(row.get("best_of")) is not int or row["best_of"] not in (3, 5):
                raise ValueError("unverified tour or match format")
            event_key = (source.casefold(), event_id)
            old = by_event.get(event_key)
            if old is None or utc_epoch(row["created_utc"]) > utc_epoch(old["created_utc"]):
                by_event[event_key] = row
        except (TypeError, ValueError, KeyError):
            result["skipped"] += 1
            result["errors"].append({"prediction_id": row.get("id"), "reason": "invalid_fixture_metadata"})
    due = [row for row in by_event.values() if checked_at.timestamp() - utc_epoch(row["created_utc"]) >= minimum_interval.total_seconds()]
    result["due"] = len(due)
    if not due:
        return result
    try:
        state = load_state()  # trusted existing artifact only; no build fallback
        workload = shadow.workload_history(db_path)
    except Exception as exc:
        result["status"] = "unavailable"
        result["errors"].append({"reason": "cached_state_or_history_unavailable", "error_type": type(exc).__name__})
        return result
    result["model_stats_through"] = state.stats_through
    for row in due:
        # Capture the decision after state/history reads, not at worker start.
        modeled_at = _refresh_now() if as_of is None else checked_at
        if utc_epoch(row["scheduled_start_utc"]) <= modeled_at.timestamp():
            result["skipped"] += 1
            continue
        try:
            context = json.loads(row.get("context_json") or "{}")
            model_inputs = context.get("model_inputs") or {}
            indoor = model_inputs.get("indoor")
            if indoor is not None and type(indoor) is not bool:
                indoor = None
            surface = row.get("surface")
            prediction = predict_match(
                state, row["player_a"], row["player_b"],
                surface if surface in ("Hard", "Clay", "Grass", "Carpet") else None,
                row["best_of"], tour=row["tour"], indoor=indoor,
                as_of=modeled_at, workload_history=workload,
            )
            # Do not append a pre-start prediction after the event has started
            # while a slow computation was running.
            finished_at = _refresh_now() if as_of is None else checked_at
            if utc_epoch(row["scheduled_start_utc"]) <= finished_at.timestamp():
                result["skipped"] += 1
                continue
            shadow.store_prediction(
                row["match_date"], row["tour"], row.get("tournament"), prediction,
                provider_event_id=str(row["provider_event_id"]),
                scheduled_start_utc=row["scheduled_start_utc"],
                fixture_source=row["fixture_source"], modeled_at=modeled_at,
                db_path=db_path,
            )
            result["refreshed"] += 1
        except Exception as exc:
            result["errors"].append({"prediction_id": row.get("id"), "reason": "prediction_refresh_failed", "error_type": type(exc).__name__})
    result["completed_at"] = (_refresh_now() if as_of is None else checked_at).isoformat()
    result["status"] = "partial" if result["errors"] else "complete"
    return result


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
    workload_history = shadow.workload_history()
    for fx in fixtures:
        if not fx["player_a"] or not fx["player_b"] or "TBD" in (
            fx["player_a"],
            fx["player_b"],
        ):
            continue  # qualifiers not yet decided — nothing to audit
        catalog_surface, best_of, official, catalog_indoor = resolve_surface(
            fx["tournament"], surfaces
        )
        surface = merge_surface(fx.get("surface"), catalog_surface)
        indoor = fx.get("indoor")
        if indoor is None:
            indoor = catalog_indoor
        pred = predict_match(
            state,
            fx["player_a"],
            fx["player_b"],
            surface,
            best_of,
            tour=fx.get("tour", "ATP"),
            indoor=indoor,
            workload_history=workload_history,
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
