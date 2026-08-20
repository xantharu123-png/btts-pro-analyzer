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
MARKET_WORKFLOW_VERSION = 10
MARKET_SNAPSHOT_VERSION = 12
MARKET_AUDIT_VERSION = 1
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
    """Format internal scan diagnostics; never render this in consumer UI."""
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


def _consumer_no_tip_copy(
    snapshot: dict,
    *,
    day_label: str,
) -> tuple[str, str, bool]:
    """Return concise evidence and an honest empty-state conclusion."""

    found = int(snapshot.get("fixtures_found") or 0)
    modeled = int(snapshot.get("fixtures_modeled") or 0)
    base_fixtures = int(snapshot.get("base_fixture_count") or 0)
    context_verified = int(snapshot.get("context_verified_fixtures") or 0)
    context_incomplete = int(
        snapshot.get("context_data_incomplete_fixtures") or 0
    )
    context_unchecked = int(snapshot.get("context_unchecked_fixtures") or 0)
    context_deferred = int(snapshot.get("deferred_context_fixtures") or 0)
    operational_errors = int(snapshot.get("operational_error_count") or 0)
    unmodeled = max(found - modeled, 0)
    unmodeled_note = (
        f" {unmodeled} weitere gefundene "
        f"{'Spiel konnte' if unmodeled == 1 else 'Spiele konnten'} nicht "
        "modelliert werden."
        if unmodeled > 0
        else ""
    )

    evidence_parts = [
        f"{found} {'Spiel' if found == 1 else 'Spiele'} gefunden",
        f"{modeled} modelliert",
    ]
    if base_fixtures > 0:
        evidence_parts.append(
            f"{base_fixtures} {'Spiel' if base_fixtures == 1 else 'Spiele'} "
            "in der engeren Auswahl"
        )
        evidence_parts.append(f"{context_verified} vollständig geprüft")
    evidence = f"{day_label} · " + " · ".join(evidence_parts)

    if operational_errors > 0:
        message = (
            "Die Prüfung konnte nicht vollständig abgeschlossen werden. "
            "BetBoy gibt deshalb kein Qualitätsurteil ab."
        )
    elif found <= 0:
        message = "Im gewählten Zeitraum wurden keine anstehenden Spiele gefunden."
    elif modeled <= 0:
        message = (
            "Die Prüfung konnte nicht vollständig abgeschlossen werden. "
            "BetBoy gibt deshalb kein Qualitätsurteil ab."
        )
    elif context_incomplete > 0:
        message = (
            "Ein Teil der benötigten Daten war nicht vollständig verfügbar. "
            "Deshalb wurde kein Tipp freigegeben; das ist keine negative "
            "Aussage über den möglichen Spielausgang."
            + unmodeled_note
        )
    elif context_unchecked > 0 or context_deferred > 0:
        pending = context_unchecked + context_deferred
        pending_label = (
            "1 weiteres Spiel"
            if pending == 1
            else f"{pending} weitere Spiele"
        )
        message = (
            f"Unter den {context_verified} vollständig geprüften Spielen wurde "
            f"kein Tipp bestätigt. Für {pending_label} "
            f"{'steht' if pending == 1 else 'stehen'} die vollständige "
            "Prüfung noch aus. Die Quote war nicht der Ablehnungsgrund."
            + unmodeled_note
        )
    elif base_fixtures <= 0:
        message = (
            "Kein Spiel kam in die engere Auswahl. "
            "Eine Quote wurde deshalb noch nicht geprüft."
            + unmodeled_note
        )
    else:
        message = (
            f"Unter den {context_verified} vollständig geprüften Spielen wurde "
            "kein Tipp bestätigt. Die Quote war nicht der Ablehnungsgrund."
            + unmodeled_note
        )
    incomplete = bool(
        operational_errors > 0
        or (found > 0 and modeled <= 0)
        or unmodeled > 0
        or context_incomplete > 0
        or context_unchecked > 0
        or context_deferred > 0
    )
    return evidence, message, incomplete


def _market_audit_payload(result: object) -> Optional[dict]:
    """Persist a server-only, sanitized proof of the latest manual scan."""

    if not isinstance(result, dict):
        return None
    challenge = result.get("challenge")
    if not isinstance(challenge, dict):
        return None

    def count(name: str) -> int:
        value = challenge.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    def count_map(name: str) -> dict[str, int]:
        value = challenge.get(name)
        if not isinstance(value, dict):
            return {}
        return {
            str(key): item
            for key, item in value.items()
            if isinstance(item, int) and not isinstance(item, bool) and item >= 0
        }

    operational_errors = challenge.get("operational_errors")
    operational_error_count = (
        len(operational_errors) if isinstance(operational_errors, list) else 0
    )
    context_scope_complete = challenge.get("context_scope_complete") is True
    if operational_error_count > 0 or count("context_data_incomplete_fixtures") > 0:
        audit_status = "data_incomplete"
    elif (
        not context_scope_complete
        or count("fixtures_modeled") < count("fixtures_found")
    ):
        audit_status = "partial"
    else:
        audit_status = "completed"
    return {
        "version": MARKET_AUDIT_VERSION,
        "scanned_at": challenge.get("scanned_at"),
        "scope": result.get("scope"),
        "status": audit_status,
        "fixtures_found": count("fixtures_found"),
        "fixtures_modeled": count("fixtures_modeled"),
        "base_candidates": count("base_candidates"),
        "base_fixture_count": count("base_fixture_count"),
        "context_fixtures": count("context_fixtures"),
        "context_verified_fixtures": count("context_verified_fixtures"),
        "context_data_incomplete_fixtures": count(
            "context_data_incomplete_fixtures"
        ),
        "context_unchecked_fixtures": count("context_unchecked_fixtures"),
        "deferred_context_fixtures": count("deferred_context_fixtures"),
        "context_scope_complete": context_scope_complete,
        "model_approved_candidates": count("model_approved_candidates"),
        "price_checked_count": count("price_checked_count"),
        "price_checked_at": challenge.get("price_checked_at"),
        "approved_candidates": count("approved_candidates"),
        "price_status_counts": count_map("price_status_counts"),
        "model_blocked_counts": count_map("model_blocked_counts"),
        "context_blocked_counts": count_map("context_blocked_counts"),
        "coverage_notice_count": len(challenge.get("coverage_notices") or []),
        "operational_error_count": operational_error_count,
    }


def _consumer_partial_scope_notice(
    snapshot: dict,
    *,
    has_candidates: bool,
) -> Optional[str]:
    """Return one safe warning when only part of the requested scope ran."""

    scope_incomplete = bool(
        int(snapshot.get("operational_error_count") or 0) > 0
        or int(snapshot.get("fixtures_modeled") or 0)
        < int(snapshot.get("fixtures_found") or 0)
        or int(snapshot.get("context_data_incomplete_fixtures") or 0) > 0
        or int(snapshot.get("context_unchecked_fixtures") or 0) > 0
        or int(snapshot.get("deferred_context_fixtures") or 0) > 0
        or snapshot.get("context_scope_complete") is not True
    )
    if not has_candidates or not scope_incomplete:
        return None
    return (
        "Die Suche wurde nur teilweise abgeschlossen. Die angezeigten "
        "Auswahlen stammen aus erfolgreich geprüften Spielen; der gesamte "
        "gewählte Suchumfang ist nicht vollständig belegt."
    )


def _render_consumer_no_tip(snapshot: dict, *, day_label: str) -> None:
    evidence, message, incomplete = _consumer_no_tip_copy(
        snapshot,
        day_label=day_label,
    )
    st.caption(evidence)
    if incomplete:
        st.warning(message)
    else:
        st.info(message)


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
    injuries = (
        context.get("injuries")
        if isinstance(context.get("injuries"), dict)
        else {}
    )
    weather = (
        context.get("weather")
        if isinstance(context.get("weather"), dict)
        else {}
    )
    lineups = (
        context.get("lineups")
        if isinstance(context.get("lineups"), dict)
        else {}
    )
    context_labels = {
        "passed": "berücksichtigt",
        "observed": "berücksichtigt",
        "neutral": "ohne belastbares Veto",
        "pending": "noch nicht bestätigt",
        "unavailable": "derzeit nicht verfügbar",
        "provisional": "in Prüfphase",
    }
    evidence = tuple(candidate.reasons) + (
        f"Evidenzscore {candidate.evidence_score:.1f} %, Modellspanne {candidate.model_spread_pp:.1f} PP.",
        (
            f"Kontext: H2H {context_labels.get(h2h.get('status'), 'geprüft')}; "
            f"Ausfälle {context_labels.get(injuries.get('status'), 'geprüft')}; "
            f"Wetter {context_labels.get(weather.get('status'), 'geprüft')}; "
            f"Aufstellungen {context_labels.get(lineups.get('status'), 'geprüft')}."
        ),
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
        model_name="Kalibriertes Marktmodell + Kontextprüfung",
        evidence=evidence,
        blockers=blockers,
        expected_total=candidate.expected_home_goals + candidate.expected_away_goals,
        evidence_stage=EVIDENCE_SHADOW,
    )


def _merge_consumer_market_rows(
    priced_rows,
    model_rows,
    *,
    limit: int = 3,
):
    """Prefer priced fixtures and keep other model forecasts visible."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    displayed = []
    seen_events = set()
    for raw_candidate in [*(priced_rows or []), *(model_rows or [])]:
        fixture_id = getattr(raw_candidate, "fixture_id", None)
        identity = (
            f"fixture:{fixture_id}"
            if isinstance(fixture_id, int) and not isinstance(fixture_id, bool)
            else f"candidate:{getattr(raw_candidate, 'candidate_id', '')}"
        )
        if not identity or identity in seen_events:
            continue
        displayed.append(raw_candidate)
        seen_events.add(identity)
        if len(displayed) >= limit:
            break
    return displayed


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
    # The calculated forecast is a separate axis from bookmaker price and
    # from the later release decision.  In particular, a provisional UEFA
    # forecast must remain visible even when it is not an Echtgeld tip.
    model_shortlist = list(
        challenge_snapshot.get("forecast_shortlist")
        or challenge_snapshot.get("shortlist")
        or []
    )
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
        st.error("Die Fußball-Suche ist vorübergehend nicht verfügbar.")
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
        st.caption("Alle verfügbaren Fußballligen")
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

    # Kein künstliches Limit mehr: Alle Spiele der gewählten Ligen werden
    # modelliert. Technische Scan- und Gate-Details bleiben serverintern.
    max_fixtures = MAX_SCAN_FIXTURES
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
                persist_name="market_latest",
                persist_fn=_market_audit_payload,
            )
            if started:
                st.session_state["market_pending_scope"] = dict(scope)

    job = scan_jobs.get_job(job_key)
    if job["state"] == "running":
        scan_progress_fragment(job_key, "Fußball-Suche")
    elif job["state"] == "done":
        result = job.get("result") or {}
        challenge_snapshot = result.get("challenge") or {}
        st.session_state.pop("market_pending_scope", None)
        st.session_state["market_bet_finder_snapshot"] = {
            "version": MARKET_SNAPSHOT_VERSION,
            "scanned_at": challenge_snapshot.get("scanned_at"),
            "scope": result.get("scope") or scope,
            "shortlist": challenge_snapshot.get("shortlist", [])[:3],
            "model_shortlist": challenge_snapshot.get("model_shortlist", [])[:3],
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
            "base_fixture_count": challenge_snapshot.get("base_fixture_count", 0),
            "context_fixtures": challenge_snapshot.get("context_fixtures", 0),
            "context_verified_fixtures": challenge_snapshot.get(
                "context_verified_fixtures",
                0,
            ),
            "context_data_incomplete_fixtures": challenge_snapshot.get(
                "context_data_incomplete_fixtures",
                0,
            ),
            "context_unchecked_fixtures": challenge_snapshot.get(
                "context_unchecked_fixtures",
                0,
            ),
            "context_scope_complete": challenge_snapshot.get(
                "context_scope_complete",
                False,
            ),
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
            "operational_error_count": len(
                challenge_snapshot.get("operational_errors") or []
            ),
            "errors": challenge_snapshot.get("errors", []),
        }
        scan_jobs.clear_job(job_key)
    elif job["state"] == "error":
        st.session_state.pop("market_pending_scope", None)
        st.error("Die Suche konnte nicht abgeschlossen werden.")
        st.caption(
            "Es wurde kein unvollständiges Ergebnis übernommen. Bitte die Suche "
            "erneut starten."
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
        st.warning("Dieses Suchergebnis ist nicht mehr aktuell. Bitte erneut suchen.")
        return

    result_day = _market_result_day_label(snapshot)
    stand_parts = [
        f"Modellstand: {_format_snapshot_time(snapshot.get('scanned_at'))}",
    ]
    if int(snapshot.get("price_checked_count") or 0) > 0:
        stand_parts.append(
            f"Preisstand: {_format_snapshot_time(snapshot.get('price_checked_at'))}"
        )
    stand_parts.append(f"Zeitraum: {result_day}")
    st.caption(" · ".join(stand_parts))
    shortlist = snapshot.get("shortlist")
    shortlist = shortlist if isinstance(shortlist, list) else []
    model_shortlist = snapshot.get("model_shortlist")
    model_shortlist = model_shortlist if isinstance(model_shortlist, list) else []
    reference_quotes = deserialize_consensus_map(
        snapshot.get("reference_quotes")
    )
    partial_scope_notice = _consumer_partial_scope_notice(
        snapshot,
        has_candidates=bool(shortlist or model_shortlist),
    )
    if partial_scope_notice:
        st.warning(partial_scope_notice)
    # One price-passing market must not erase the other calculated forecasts.
    # Prefer priced fixtures, then fill the same maximum-three view with model
    # selections from different matches.
    displayed_rows = _merge_consumer_market_rows(shortlist, model_shortlist)

    if not displayed_rows:
        _render_consumer_no_tip(
            snapshot,
            day_label=result_day,
        )
    else:
        if shortlist:
            priced_count = min(len(shortlist), len(displayed_rows))
            st.info(
                f"{priced_count} Modell-Auswahl"
                f"{'en' if priced_count != 1 else ''} mit passender "
                f"Vergleichsquote für {result_day}. Weitere berechnete "
                "Auswahlen bleiben unabhängig vom Preis sichtbar."
            )
        else:
            found_label = (
                "Eine interessante Auswahl gefunden"
                if len(displayed_rows) == 1
                else f"{len(displayed_rows)} interessante Auswahlen gefunden"
            )
            st.info(f"{found_label} – aktuell noch kein spielbarer Tipp.")
        st.caption(
            "Die Quote bewertet den Wettpreis, nicht den möglichen "
            "Spielausgang. Fehlt eine belastbare Vergleichsquote oder ist "
            "sie zu niedrig, bleibt die Modell-Auswahl sichtbar."
        )
        candidates = [
            _strict_market_candidate(candidate) for candidate in displayed_rows
        ]
        for index, (candidate, raw_candidate) in enumerate(
            zip(candidates, displayed_rows),
            start=1,
        ):
            st.markdown(f"### Auswahl {index}")
            render_price_decision(
                candidate,
                key=f"market_{candidate.event_key}_{snapshot.get('scanned_at')}",
                bankroll_key="football_bet_finder_bankroll",
                save_source="Fußball Prematch",
                reference_quote=reference_quotes.get(
                    raw_candidate.candidate_id
                ),
                allow_manual_check=True,
            )
            if index < len(candidates):
                st.divider()


__all__ = [
    "FOOTBALL_MARKET_SCOPES",
    "_api_football_items",
    "_market_scope_signature",
    "_market_result_day_label",
    "create_alternative_markets_tab_extended",
]
