"""Strict football-market bet finder with one shared price decision."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import streamlit as st

import scan_jobs
from bet_finder_ui import render_price_decision
from bet_finder_candidates import build_probability_candidate
from multi_sport_recommendations import EVIDENCE_SHADOW
from ui_components import render_empty_state, scan_progress_fragment
from challenge_15k import ChallengeDataProvider, scan_daily_challenge
from config_loader import load_app_config
from date_context import german_day_label, zurich_today
from league_catalog import ALTERNATIVE_MARKET_LEAGUES


DEFAULT_LEAGUES = [78, 39, 140]
MARKET_WORKFLOW_VERSION = 5
MARKET_SNAPSHOT_VERSION = 4
MARKET_MAX_AGE_MINUTES = 20


def _segmented(label: str, options: list[str], key: str, default: str) -> str:
    if hasattr(st, "segmented_control"):
        value = st.segmented_control(
            label,
            options,
            default=default,
            key=key,
            selection_mode="single",
        )
        return value or default
    return st.radio(label, options, index=options.index(default), horizontal=True, key=key)


def _market_scope_signature(leagues: list[int], search_date) -> dict:
    return {
        "league_ids": sorted(int(league_id) for league_id in leagues),
        "date": search_date.isoformat(),
    }


def _market_result_day_label(
    snapshot: dict,
    *,
    today=None,
) -> str:
    scope = snapshot.get("scope")
    raw_date = scope.get("date") if isinstance(scope, dict) else None
    return german_day_label(raw_date, today=today or _zurich_today())


def _format_snapshot_time(value: Optional[str]) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def _zurich_today():
    return zurich_today()


def _snapshot_age_minutes(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if timestamp.tzinfo is None:
        return None
    return (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds() / 60.0


def _api_football_items(response, label: str) -> list[dict]:
    """Reject provider-level errors that API-Football returns with HTTP 200."""
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: invalid provider payload")
    errors = payload.get("errors")
    if errors:
        detail = (
            "; ".join(f"{key}: {value}" for key, value in errors.items())
            if isinstance(errors, dict)
            else str(errors)
        )
        raise ValueError(f"{label}: {detail}")
    items = payload.get("response")
    if not isinstance(items, list):
        raise ValueError(f"{label}: response list missing")
    return items


def _strict_market_candidate(candidate):
    market = candidate.market
    selection = candidate.selection
    if market.startswith("Team 1"):
        market = market.replace("Team 1", candidate.home_team, 1)
    elif market.startswith("Team 2"):
        market = market.replace("Team 2", candidate.away_team, 1)
    selection = {
        "Heimsieg": candidate.home_team,
        "Auswärtssieg": candidate.away_team,
    }.get(selection, selection)
    context = candidate.context if isinstance(candidate.context, dict) else {}
    h2h = context.get("h2h") if isinstance(context.get("h2h"), dict) else {}
    evidence = tuple(candidate.reasons) + (
        f"Evidenzscore {candidate.evidence_score:.1f} %, Modellspanne {candidate.model_spread_pp:.1f} PP.",
        f"H2H {h2h.get('matches', 0)} Spiele; Ausfälle, Wetter und Aufstellungen haben die Kontextgates bestanden.",
        "Markt hat das liga- und marktbezogene Walk-forward-Kalibrierungsgate bestanden.",
    )
    model_probability = candidate.probability * 100.0
    effective_haircut = model_probability - candidate.conservative_probability * 100.0
    blockers = list(candidate.blocked_reasons) + list(context.get("blocked_reasons", []))
    try:
        kickoff = datetime.fromisoformat(str(candidate.kickoff).replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        kickoff = None
    if kickoff is None or kickoff.tzinfo is None:
        blockers.append("Die Anstoßzeit ist nicht eindeutig verifiziert.")
    elif kickoff.astimezone(timezone.utc) <= datetime.now(timezone.utc):
        blockers.append("Das Spiel hat bereits begonnen.")
    return build_probability_candidate(
        event_key=candidate.candidate_id,
        sport="Fußball",
        event_label=f"{candidate.home_team} vs {candidate.away_team}",
        market=market,
        selection=selection,
        model_probability=model_probability,
        probability_haircut=effective_haircut,
        model_name="Walk-forward Marktmodell + Kontext-Vetos",
        evidence=evidence,
        blockers=blockers,
        expected_total=candidate.expected_home_goals + candidate.expected_away_goals,
        evidence_stage=EVIDENCE_SHADOW,
    )


def _run_market_scan_worker(
    api_football_key: str,
    weather_key: Optional[str],
    league_ids: list[int],
    search_date,
    max_fixtures: int,
    scope: dict,
    progress_cb=None,
) -> dict:
    """Hintergrund-Worker für den Markt-Scan (thread-sicher, kein st.*).

    Der Scope wird beim Job-Start eingefroren und mit dem Ergebnis
    zurückgegeben — ändert der Nutzer die Auswahl während des Scans,
    erkennt die Seite das wie bisher am Scope-Vergleich.
    """
    provider = ChallengeDataProvider(api_football_key, weather_key)
    challenge_snapshot = scan_daily_challenge(
        provider,
        league_ids,
        search_date,
        max_fixtures,
        progress_cb=progress_cb,
    )
    return {"scope": scope, "challenge": challenge_snapshot}


def create_alternative_markets_tab_extended() -> None:
    """Find up to three fully gated football-market candidates."""
    session_scope = scan_jobs.session_scope(st.session_state)
    job_key = scan_jobs.scoped_key("markets", session_scope)
    config = load_app_config(st)
    if not config.api_football_key:
        st.error("API-Football-Key fehlt.")
        return

    st.subheader("Wett-Suche")
    available_ids = list(ALTERNATIVE_MARKET_LEAGUES)
    favorites = [league_id for league_id in DEFAULT_LEAGUES if league_id in available_ids]
    all_scope_label = f"Alle ({len(available_ids)})"
    favorite_scope_label = f"Favoriten ({len(favorites)})"
    league_scope = _segmented(
        "Ligen",
        [all_scope_label, favorite_scope_label, "Auswahl"],
        "market_league_scope_v2",
        all_scope_label,
    )
    if league_scope == favorite_scope_label:
        selected_leagues = favorites
        st.caption(", ".join(ALTERNATIVE_MARKET_LEAGUES[item] for item in selected_leagues))
    elif league_scope == all_scope_label:
        selected_leagues = available_ids
        st.caption(
            f"{len(selected_leagues)} konfigurierte Ligen werden vollständig durchsucht."
        )
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_ids,
            default=favorites,
            format_func=lambda league_id: ALTERNATIVE_MARKET_LEAGUES.get(
                league_id, f"Liga {league_id}"
            ),
            key="market_selected_leagues",
        )

    date_mode = _segmented(
        "Datum",
        ["Heute", "Morgen", "Auswahl"],
        "market_date_mode",
        "Heute",
    )
    if date_mode == "Heute":
        search_date = _zurich_today()
    elif date_mode == "Morgen":
        search_date = _zurich_today() + timedelta(days=1)
    else:
        search_date = st.date_input(
            "Spieldatum", _zurich_today(), key="market_custom_date"
        )

    # Kein künstliches Limit mehr: ALLE Spiele der gewählten Ligen werden
    # modelliert (reine Lokalrechnung, keine Provider-Zusatzkosten).
    # Teure Live-Kontext-Checks (H2H, Wetter, Aufstellung) laufen nur für
    # die Top-Kandidaten — 400 ist das technische Sicherheitsventil.
    max_fixtures = 400
    st.caption(
        "Alle Spiele der gewählten Ligen werden modelliert; Live-Kontext "
        "(H2H, Wetter, Aufstellung) nur für die Top-Kandidaten."
    )
    scope = _market_scope_signature(selected_leagues, search_date)
    scope["max_fixtures"] = max_fixtures
    find_bets = st.button(
        "Wetten finden",
        type="primary",
        use_container_width=True,
        key="run_market_bet_finder",
    )
    if find_bets and not selected_leagues:
        st.warning("Mindestens eine Liga auswählen.")
    elif find_bets and search_date < _zurich_today():
        st.error("NICHT WETTEN: Das gewählte Datum liegt in der Vergangenheit.")
    elif find_bets:
        if scan_jobs.get_job(job_key)["state"] == "running":
            st.info("Der Markt-Scan läuft bereits im Hintergrund.")
        else:
            started = scan_jobs.start_job(
                job_key,
                _run_market_scan_worker,
                args=(
                    config.api_football_key,
                    config.weather_key,
                    list(selected_leagues),
                    search_date,
                    max_fixtures,
                    dict(scope),
                ),
            )
            if started:
                st.session_state["market_pending_scope"] = dict(scope)

    job = scan_jobs.get_job(job_key)
    if job["state"] == "running":
        active_scope = st.session_state.get("market_pending_scope")
        active_leagues = (
            active_scope.get("league_ids")
            if isinstance(active_scope, dict)
            else None
        )
        if isinstance(active_leagues, list):
            st.caption(
                f"Aktiver Auftrag: {len(active_leagues)} Ligen am "
                f"{active_scope.get('date', search_date.isoformat())}."
            )
        scan_progress_fragment(job_key, "Markt-Scan")
    elif job["state"] == "done":
        result = job.get("result") or {}
        challenge_snapshot = result.get("challenge") or {}
        st.session_state.pop("market_pending_scope", None)
        st.session_state["market_bet_finder_snapshot"] = {
            "version": MARKET_SNAPSHOT_VERSION,
            "scanned_at": challenge_snapshot.get("scanned_at"),
            "scope": result.get("scope") or scope,
            "shortlist": challenge_snapshot.get("shortlist", [])[:3],
            "fixtures_found": challenge_snapshot.get("fixtures_found", 0),
            "fixtures_modeled": challenge_snapshot.get("fixtures_modeled", 0),
            "blocked_counts": challenge_snapshot.get("blocked_counts", {}),
            "errors": challenge_snapshot.get("errors", []),
        }
        scan_jobs.clear_job(job_key)
    elif job["state"] == "error":
        failed_scope = st.session_state.pop("market_pending_scope", None)
        failed_leagues = (
            failed_scope.get("league_ids")
            if isinstance(failed_scope, dict)
            else None
        )
        scope_label = (
            f" für {len(failed_leagues)} Ligen"
            if isinstance(failed_leagues, list)
            else ""
        )
        st.error(
            f"Markt-Wettfinder{scope_label} technisch abgebrochen: "
            f"{job.get('error')}"
        )
        st.caption(
            "Es wurde keine Wettentscheidung aus diesem unvollständigen Lauf übernommen. "
            "Die Suche kann direkt neu gestartet werden."
        )
        scan_jobs.clear_job(job_key)

    snapshot = st.session_state.get("market_bet_finder_snapshot")
    if not isinstance(snapshot, dict):
        render_empty_state(
            "So funktioniert die Markt-Suche",
            [
                "Ligen, Datum und Prüfumfang wählen, dann „Wetten finden“ klicken.",
                "Das Modell prüft alle freigegebenen Märkte quotenfrei.",
                "Die exakte N1Bet-Quote entscheidet nur über den Preisstatus; "
                "die Shadow-Evidenz bleibt davon getrennt.",
            ],
            duration_hint="Dauer: abhängig von Spielplan und Datenbestand.",
        )
        return
    if snapshot.get("version") != MARKET_SNAPSHOT_VERSION:
        st.warning("Dieses Ergebnis stammt aus einer älteren App-Version. Wetten neu suchen.")
        return
    if snapshot.get("scope") != scope:
        st.warning("Liga, Datum oder Prüfumfang wurden geändert. Wetten neu suchen.")
        return

    snapshot_age = _snapshot_age_minutes(snapshot.get("scanned_at"))
    if (
        snapshot_age is None
        or snapshot_age < -1
        or snapshot_age > MARKET_MAX_AGE_MINUTES
    ):
        st.error(
            "NICHT WETTEN: Dieser Kontext-Datenstand ist älter als 20 Minuten oder zeitlich ungültig."
        )
        return

    result_day = _market_result_day_label(snapshot)
    st.caption(
        f"Datenstand: {_format_snapshot_time(snapshot.get('scanned_at'))} · "
        f"Spieltag: {result_day}"
    )
    shortlist = snapshot.get("shortlist")
    shortlist = shortlist if isinstance(shortlist, list) else []
    if not shortlist:
        st.error(
            f"{result_day} keine belastbare Markt-Empfehlung — kein Spiel "
            "besteht Modell, Kalibrierung, Direktvergleich, Ausfall- und "
            "Wetterprüfung gemeinsam."
        )
    else:
        candidates = [_strict_market_candidate(candidate) for candidate in shortlist]
        options = list(range(len(candidates)))
        selected = st.selectbox(
            "Spiel auswählen",
            options,
            format_func=lambda index: (
                f"{candidates[index].event_label} | "
                f"{candidates[index].market}: {candidates[index].selection}"
            ),
            key="market_bet_candidate",
        )
        candidate = candidates[selected]
        render_price_decision(
            candidate,
            key=f"market_{candidate.event_key}_{snapshot.get('scanned_at')}",
            bankroll_key="football_bet_finder_bankroll",
        )

    with st.expander("Suchprüfung"):
        summary = st.columns(3)
        summary[0].metric("Gefunden", snapshot.get("fixtures_found", 0))
        summary[1].metric("Modelliert", snapshot.get("fixtures_modeled", 0))
        summary[2].metric("Freigegeben", len(shortlist))
        blocked_counts = snapshot.get("blocked_counts")
        if isinstance(blocked_counts, dict) and blocked_counts:
            blocked_frame = pd.DataFrame(
                [
                    {"Sperrgrund": reason, "Kandidaten": count}
                    for reason, count in sorted(
                        blocked_counts.items(), key=lambda item: item[1], reverse=True
                    )
                ]
            )
            st.dataframe(blocked_frame, use_container_width=True, hide_index=True)
        if snapshot.get("errors"):
            st.warning(
                "Einige Provider-Prüfungen waren unvollständig und wurden nicht freigegeben."
            )


__all__ = [
    "_api_football_items",
    "_market_scope_signature",
    "_market_result_day_label",
    "create_alternative_markets_tab_extended",
]
