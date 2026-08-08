"""Strict football-market bet finder with one shared price decision."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import streamlit as st

import scan_jobs
from bet_finder_ui import render_price_decision
from bet_finder_candidates import build_probability_candidate
from multi_sport_recommendations import EVIDENCE_SHADOW
from ui_components import scan_progress_fragment
from challenge_15k import (
    MAX_SCAN_FIXTURES,
    ChallengeDataProvider,
    render_football_scan_diagnostics,
    scan_no_result_copy,
    scan_daily_challenge,
)
from challenge_engine import select_shortlist
from config_loader import load_app_config
from date_context import german_day_label, zurich_today
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from market_consensus import (
    deserialize_consensus_map,
    fetch_football_consensus,
    reference_price_status,
    serialize_consensus_map,
)


DEFAULT_LEAGUES = [78, 39, 140]
MARKET_WORKFLOW_VERSION = 9
MARKET_SNAPSHOT_VERSION = 9
MARKET_MAX_AGE_MINUTES = 20
FOOTBALL_MARKET_SCOPES = {
    "Beste Märkte": None,
    "Ergebnis": frozenset({"result", "double_chance"}),
    "Tore": frozenset(
        {"total", "team_total", "team_range", "result_total", "mixed_or"}
    ),
    "Beide treffen": frozenset({"btts"}),
    "Ecken": frozenset({"corner_total", "team_corners"}),
    "Karten": frozenset({"yellow_total", "team_yellow"}),
}
PRICE_STATUS_LABELS = {
    "TOO_LOW": "unter der Mindestquote",
    "UNAVAILABLE": "ohne exakt passende Marktquote",
    "BORDERLINE": "nur bei einzelnen Anbietern ausreichend",
    "THIN": "mit zu wenigen Vergleichsanbietern",
    "STALE": "mit veraltetem Marktstand",
    "INVALID_MINIMUM": "mit ungültiger Mindestquote",
    "PLAYABLE": "preislich spielbar",
}


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


def _market_scope_signature(
    leagues: list[int],
    search_date,
    search_end_date=None,
) -> dict:
    end_date = search_end_date or search_date
    return {
        "league_ids": sorted(int(league_id) for league_id in leagues),
        "date": search_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def _market_result_day_label(
    snapshot: dict,
    *,
    today=None,
) -> str:
    scope = snapshot.get("scope")
    raw_date = scope.get("date") if isinstance(scope, dict) else None
    raw_end_date = scope.get("end_date") if isinstance(scope, dict) else None
    try:
        start_date = datetime.fromisoformat(str(raw_date)).date()
        end_date = datetime.fromisoformat(str(raw_end_date or raw_date)).date()
    except (TypeError, ValueError):
        return german_day_label(raw_date, today=today or _zurich_today())
    if start_date == end_date:
        return german_day_label(start_date, today=today or _zurich_today())
    return f"{start_date:%d.%m.%Y} bis {end_date:%d.%m.%Y}"


def _format_snapshot_time(value: Optional[str]) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def _price_check_summary(snapshot: dict) -> Optional[str]:
    counts = snapshot.get("price_status_counts")
    counts = counts if isinstance(counts, dict) else {}
    parts = [
        f"{counts[code]} {label}"
        for code, label in PRICE_STATUS_LABELS.items()
        if isinstance(counts.get(code), int) and counts[code] > 0
    ]
    if not parts:
        return None
    checked = snapshot.get("price_checked_count")
    if isinstance(checked, bool) or not isinstance(checked, int) or checked < 1:
        checked = sum(counts.values())
    fixtures = snapshot.get("price_fixture_count")
    fixture_text = (
        f" aus {fixtures} {'Spiel' if fixtures == 1 else 'Spielen'}"
        if isinstance(fixtures, int) and not isinstance(fixtures, bool) and fixtures > 0
        else ""
    )
    return (
        f"Preisprüfung: {checked} Modellmärkte{fixture_text} geprüft · "
        + " · ".join(parts)
    )


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
    search_end_date,
    max_fixtures: int,
    scope: dict,
    market_kinds: Optional[frozenset[str]] = None,
    progress_cb=None,
) -> dict:
    """Hintergrund-Worker für den Markt-Scan (thread-sicher, kein st.*).

    Der Scope wird beim Job-Start eingefroren und mit dem Ergebnis
    zurückgegeben — ändert der Nutzer die Auswahl während des Scans,
    erkennt die Seite das wie bisher am Scope-Vergleich.
    """
    provider = ChallengeDataProvider(api_football_key, weather_key)

    def model_progress(value: float, text: str) -> None:
        if progress_cb:
            progress_cb(min(0.90, max(0.0, float(value)) * 0.90), text)

    scan_kwargs = {
        "progress_cb": model_progress if progress_cb else None,
    }
    if market_kinds is not None:
        scan_kwargs["market_kinds"] = set(market_kinds)
    challenge_snapshot = scan_daily_challenge(
        provider,
        league_ids,
        search_date,
        max_fixtures,
        search_end_date=search_end_date,
        **scan_kwargs,
    )
    if progress_cb:
        progress_cb(0.92, "Marktquoten der Modellkandidaten werden verglichen")
    model_shortlist = list(challenge_snapshot.get("shortlist") or [])
    price_candidates = list(
        challenge_snapshot.get("price_candidates")
        or model_shortlist
    )
    reference_quotes, quote_errors = fetch_football_consensus(
        api_football_key,
        price_candidates,
    )
    price_checked_at = datetime.now(timezone.utc)
    price_status_counts: dict[str, int] = {}
    playable_candidates = []
    for candidate in price_candidates:
        quote = reference_quotes.get(candidate.candidate_id)
        status = reference_price_status(
            quote,
            candidate.minimum_odds,
            now=price_checked_at,
        )
        price_status_counts[status.code] = (
            price_status_counts.get(status.code, 0) + 1
        )
        if status.code == "PLAYABLE":
            playable_candidates.append(candidate)

    challenge_snapshot["model_shortlist"] = model_shortlist
    challenge_snapshot["model_approved_candidates"] = len(model_shortlist)
    challenge_snapshot["shortlist"] = select_shortlist(
        playable_candidates,
        max_candidates=3,
    )
    challenge_snapshot["approved_candidates"] = len(
        challenge_snapshot["shortlist"]
    )
    challenge_snapshot["reference_quotes"] = serialize_consensus_map(
        reference_quotes
    )
    challenge_snapshot["quote_errors"] = quote_errors
    challenge_snapshot["price_checked_at"] = price_checked_at.isoformat()
    challenge_snapshot["price_checked_count"] = len(price_candidates)
    challenge_snapshot["price_fixture_count"] = len(
        {candidate.fixture_id for candidate in price_candidates}
    )
    challenge_snapshot["price_status_counts"] = price_status_counts
    challenge_snapshot["bookmaker_data_used"] = bool(reference_quotes)
    if progress_cb:
        progress_cb(1.0, "Tipps und Marktpreise sind bereit")
    return {"scope": scope, "challenge": challenge_snapshot}


def create_alternative_markets_tab_extended(
    *,
    market_scope: str = "Beste Märkte",
    search_date=None,
    search_end_date=None,
    embedded: bool = False,
) -> None:
    """Find up to three fully gated football-market candidates."""
    if market_scope not in FOOTBALL_MARKET_SCOPES:
        raise ValueError(f"Unbekannte Fußball-Wettart: {market_scope}")
    selected_market_kinds = FOOTBALL_MARKET_SCOPES[market_scope]
    session_scope = scan_jobs.session_scope(st.session_state)
    job_key = scan_jobs.scoped_key("markets", session_scope)
    config = load_app_config(st)
    if not config.api_football_key:
        st.error("API-Football-Key fehlt.")
        return

    if not embedded:
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

    if search_date is None:
        horizon_label = st.selectbox(
            "Zeitraum",
            ["Heute", "3 Tage voraus", "7 Tage voraus", "14 Tage voraus"],
            index=2,
            key="market_horizon",
        )
        horizon_days = {
            "Heute": 0,
            "3 Tage voraus": 3,
            "7 Tage voraus": 7,
            "14 Tage voraus": 14,
        }[horizon_label]
        search_date = _zurich_today()
        search_end_date = search_date + timedelta(days=horizon_days)
    elif search_end_date is None:
        search_end_date = search_date

    # Kein künstliches Limit mehr: ALLE Spiele der gewählten Ligen werden
    # modelliert (reine Lokalrechnung, keine Provider-Zusatzkosten).
    # Teure Live-Kontext-Checks (H2H, Wetter, Aufstellung) laufen nur für
    # die Top-Kandidaten; MAX_SCAN_FIXTURES ist nur das technische Sicherheitsventil.
    max_fixtures = MAX_SCAN_FIXTURES
    st.caption(
        "Alle Spiele im Zeitraum werden modelliert; H2H, Ausfälle und Wetter "
        "nur für die aussichtsreichsten Spiele im verfügbaren Kontextfenster."
    )
    scope = _market_scope_signature(
        selected_leagues,
        search_date,
        search_end_date,
    )
    scope["max_fixtures"] = max_fixtures
    scope["market_scope"] = market_scope
    scope["market_kinds"] = (
        sorted(selected_market_kinds)
        if selected_market_kinds is not None
        else None
    )
    find_bets = st.button(
        "Tipps finden",
        type="primary",
        use_container_width=True,
        key="run_market_bet_finder",
    )
    if find_bets and not selected_leagues:
        st.warning("Mindestens eine Liga auswählen.")
    elif find_bets and search_date < _zurich_today():
        st.error("NICHT WETTEN: Das gewählte Datum liegt in der Vergangenheit.")
    elif find_bets and (
        search_end_date < search_date
        or search_end_date > search_date + timedelta(days=14)
    ):
        st.error("Der Suchzeitraum darf höchstens 14 Tage voraus reichen.")
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
                    search_end_date,
                    max_fixtures,
                    dict(scope),
                    selected_market_kinds,
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
            active_start = active_scope.get("date", search_date.isoformat())
            active_end = active_scope.get("end_date", active_start)
            st.caption(
                f"Aktiver Auftrag: {len(active_leagues)} Ligen · "
                f"{active_start} bis {active_end}."
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
            "reference_quotes": challenge_snapshot.get("reference_quotes", {}),
            "quote_errors": challenge_snapshot.get("quote_errors", []),
            "price_checked_at": challenge_snapshot.get("price_checked_at"),
            "price_checked_count": challenge_snapshot.get(
                "price_checked_count", 0
            ),
            "price_fixture_count": challenge_snapshot.get(
                "price_fixture_count", 0
            ),
            "price_status_counts": challenge_snapshot.get(
                "price_status_counts", {}
            ),
            "bookmaker_data_used": challenge_snapshot.get(
                "bookmaker_data_used", False
            ),
            "model_approved_candidates": challenge_snapshot.get(
                "model_approved_candidates", 0
            ),
            "fixtures_found": challenge_snapshot.get("fixtures_found", 0),
            "fixtures_modeled": challenge_snapshot.get("fixtures_modeled", 0),
            "market_candidates": challenge_snapshot.get("market_candidates", 0),
            "base_candidates": challenge_snapshot.get("base_candidates", 0),
            "context_fixtures": challenge_snapshot.get("context_fixtures", 0),
            "approved_candidates": challenge_snapshot.get("approved_candidates", 0),
            "deferred_context_fixtures": challenge_snapshot.get(
                "deferred_context_fixtures",
                0,
            ),
            "continental_fixtures_found": challenge_snapshot.get(
                "continental_fixtures_found", 0
            ),
            "continental_fallback_modeled": challenge_snapshot.get(
                "continental_fallback_modeled", 0
            ),
            "continental_fallback_failed": challenge_snapshot.get(
                "continental_fallback_failed", 0
            ),
            "configured_market_definitions": challenge_snapshot.get(
                "configured_market_definitions", 0
            ),
            "modeled_market_definitions": challenge_snapshot.get(
                "modeled_market_definitions", 0
            ),
            "market_coverage": challenge_snapshot.get("market_coverage", []),
            "model_blocked_counts": challenge_snapshot.get(
                "model_blocked_counts", {}
            ),
            "context_blocked_counts": challenge_snapshot.get(
                "context_blocked_counts", {}
            ),
            "blocked_counts": challenge_snapshot.get("blocked_counts", {}),
            "transfer_only_candidates": challenge_snapshot.get(
                "transfer_only_candidates", 0
            ),
            "transfer_only_fixtures": challenge_snapshot.get(
                "transfer_only_fixtures", 0
            ),
            "transfer_only_examples": challenge_snapshot.get(
                "transfer_only_examples", []
            ),
            "coverage_notices": challenge_snapshot.get("coverage_notices", []),
            "operational_errors": challenge_snapshot.get(
                "operational_errors", []
            ),
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
        st.info(f"Noch keine Suche für {market_scope} in diesem Zeitraum.")
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
        f"Zeitraum: {result_day}"
    )
    shortlist = snapshot.get("shortlist")
    shortlist = shortlist if isinstance(shortlist, list) else []
    if not shortlist:
        price_summary = _price_check_summary(snapshot)
        if price_summary:
            st.error(
                f"{result_day}: keine preislich freigegebene Markt-Empfehlung."
            )
            st.caption(price_summary)
        else:
            headline, detail = scan_no_result_copy(
                snapshot,
                day_label=result_day,
                recommendation_label="Markt-Empfehlung",
            )
            st.error(headline)
            st.caption(detail)
        model_blockers = snapshot.get("model_blocked_counts") or {}
        if isinstance(model_blockers, dict) and model_blockers:
            reason, count = max(model_blockers.items(), key=lambda item: item[1])
            st.caption(
                f"Hauptsperre: {reason} ({count} Marktkandidaten; "
                "Mehrfachsperren möglich)."
            )
        transfer_only = int(snapshot.get("transfer_only_candidates") or 0)
        if transfer_only:
            st.caption(
                f"{transfer_only} Kandidaten bestanden alle übrigen Modellprüfungen, "
                "bleiben aber am UEFA-Transfergate gesperrt. Das sind keine Tipps."
            )
    else:
        candidates = [_strict_market_candidate(candidate) for candidate in shortlist]
        reference_quotes = deserialize_consensus_map(
            snapshot.get("reference_quotes")
        )
        st.success(
            f"{len(candidates)} konkrete Empfehlung(en) für {result_day}."
        )
        for index, (candidate, raw_candidate) in enumerate(
            zip(candidates, shortlist),
            start=1,
        ):
            st.markdown(f"### Tipp {index}")
            render_price_decision(
                candidate,
                key=f"market_{candidate.event_key}_{snapshot.get('scanned_at')}",
                bankroll_key="football_bet_finder_bankroll",
                save_source="Fußball Prematch",
                reference_quote=reference_quotes.get(
                    raw_candidate.candidate_id
                ),
            )
            if index < len(candidates):
                st.divider()
    quote_errors = snapshot.get("quote_errors") or []
    if quote_errors:
        with st.expander("Quotenabdeckung"):
            for error in quote_errors:
                st.write(f"- {error}")

    with st.expander("Suchprüfung", expanded=not shortlist):
        render_football_scan_diagnostics(snapshot, approved_count=len(shortlist))


__all__ = [
    "FOOTBALL_MARKET_SCOPES",
    "_api_football_items",
    "_market_scope_signature",
    "_market_result_day_label",
    "create_alternative_markets_tab_extended",
]
