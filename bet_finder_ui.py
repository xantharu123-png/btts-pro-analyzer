"""Shared, customer-facing rendering for one concrete model tip."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional, TypeVar

import streamlit as st

from account_identity import storage_scope
from betting_math import EXTREME_SHORT_ODDS_CUTOFF
from market_consensus import (
    MarketConsensus,
    ODDS_API_REFERENCE_SOURCE,
    REFERENCE_SOURCE,
    ReferencePriceStatus,
    wettfinder_consensus,
    wettfinder_reference_price_status,
)
from multi_sport_recommendations import (
    PriceDecision,
    RecommendationCandidate,
    evaluate_candidate_price,
    format_probability_percent,
)
from tip_store import TipStore


LOGGER = logging.getLogger(__name__)
_ForecastRow = TypeVar("_ForecastRow")


@dataclass(frozen=True)
class ReferencePriceEvaluation:
    """The exact automatic price result, separated from Streamlit rendering."""

    decision: Optional[PriceDecision]
    status: ReferencePriceStatus
    quote: Optional[MarketConsensus]


def merge_consumer_forecast_catalog(
    *groups: Optional[Iterable[_ForecastRow]],
) -> list[_ForecastRow]:
    """Merge display catalogs without dropping distinct markets per fixture."""

    merged: list[_ForecastRow] = []
    seen: set[str] = set()
    for group in groups:
        for row in group or ():
            identity = _consumer_token(
                getattr(row, "candidate_id", None)
                or getattr(row, "key", None)
                or id(row)
            )
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(row)
    return merged


def _consumer_token(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def _consumer_market_utility_tier(row: object) -> int:
    """Rank main-card usefulness without changing market eligibility.

    Informative combined decisions should not be crowded out by repeated broad
    safety lines. Team under 1.5 remains an ordinary candidate: this tier only
    affects presentation and never deletes, blocks or reprices a forecast.
    """

    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    selection = _consumer_token(getattr(row, "selection", None))
    combined = "_".join(part for part in (market_key, market, selection) if part)
    if market_key.startswith("result_total_") or (
        "resultat" in market and ("gesamttore" in market or "tore" in market)
    ):
        return 0
    is_team_total = (
        market_key.startswith(
            ("home_under_", "home_over_", "away_under_", "away_over_")
        )
        or "team_1_gesamttore" in market
        or "team_2_gesamttore" in market
        or "teamtore" in market
        or "team_total" in combined
    )
    if market_key in {"home_under_1_5", "away_under_1_5"} or (
        is_team_total and selection == "unter_1_5"
    ):
        return 1
    if is_team_total:
        return 2
    if (
        market_key.startswith(("dc_", "mixed_"))
        or "doppelte_chance" in market
        or "gemischte_chance" in market
        or ("tore" in selection and "oder" in selection)
    ):
        return 3
    return 1


def _consumer_market_is_mixed(row: object) -> bool:
    """Identify configured mixed-or markets for normal-finder backfill."""

    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    return market_key.startswith("mixed_") or "gemischte_chance" in market


def _consumer_market_is_basis(row: object) -> bool:
    """Identify broad safety lines for secondary presentation only."""

    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    selection = _consumer_token(getattr(row, "selection", None))
    basic_prefixes = ("dc_", "mixed_", "home_range_", "away_range_")
    basic_keys = {
        "total_over_0_5",
        "total_under_4_5",
        "home_over_0_5",
        "away_over_0_5",
        "home_under_2_5",
        "away_under_2_5",
        "corners_over_5_5",
        "corners_under_11_5",
        "home_corners_over_2_5",
        "away_corners_over_2_5",
        "home_corners_under_5_5",
        "away_corners_under_5_5",
        "yellow_over_1_5",
        "yellow_under_4_5",
        "home_yellow_over_0_5",
        "away_yellow_over_0_5",
        "home_yellow_under_2_5",
        "away_yellow_under_2_5",
    }
    if market_key.startswith(basic_prefixes) or market_key in basic_keys:
        return True
    if "doppelte_chance" in market or "gemischte_chance" in market:
        return True
    if selection in {"1_3_tore", "2_4_tore"}:
        return True
    is_team_total = (
        "team_1_gesamttore" in market
        or "team_2_gesamttore" in market
        or "teamtore" in market
        or "team_total" in market
    )
    return is_team_total and selection in {"uber_0_5", "unter_2_5"}


def _consumer_is_confirmed_tip(row: object) -> bool:
    """Return whether the validated strict overlay made this row actionable."""

    return str(getattr(row, "evidence_stage", None) or "").upper() == "RELEASED"


def partition_consumer_basis_forecasts(
    rows: Iterable[_ForecastRow],
) -> tuple[list[_ForecastRow], list[_ForecastRow]]:
    """Separate broad model context from ordinary or confirmed selections."""

    ordinary: list[_ForecastRow] = []
    basis: list[_ForecastRow] = []
    for row in rows:
        if _consumer_market_is_basis(row) and not _consumer_is_confirmed_tip(row):
            basis.append(row)
        else:
            ordinary.append(row)
    return ordinary, basis


def _consumer_context_complete(row: object) -> bool:
    for attribute in ("context_complete", "release_context_complete"):
        value = getattr(row, attribute, None)
        if value is True:
            return True
    context = getattr(row, "context", None)
    return bool(
        isinstance(context, dict)
        and context.get("release_context_complete") is True
    )


def _consumer_fixture_identity(row: object) -> str:
    fixture_id = getattr(row, "fixture_id", None)
    if fixture_id is not None and not isinstance(fixture_id, bool):
        token = _consumer_token(fixture_id)
        if token:
            return f"fixture:{token}"
    event = _consumer_token(getattr(row, "event_label", None))
    if event:
        return f"event:{event}"
    teams = _consumer_token(
        "|".join(
            str(value or "")
            for value in (
                getattr(row, "home_team", None),
                getattr(row, "away_team", None),
            )
        )
    )
    if teams:
        return f"teams:{teams}"
    row_identity = (
        getattr(row, "candidate_id", None)
        or getattr(row, "key", None)
        or id(row)
    )
    return f"row:{_consumer_token(row_identity)}"


def _consumer_market_identity(row: object) -> str:
    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    keyed_families = (
        ("result_total_", "result_total"),
        ("result_", "result"),
        ("dc_", "double_chance"),
        ("btts_", "btts"),
        ("total_", "total"),
        ("home_corners_", "team_corners"),
        ("away_corners_", "team_corners"),
        ("corners_", "corner_total"),
        ("home_yellow_", "team_yellow"),
        ("away_yellow_", "team_yellow"),
        ("yellow_", "yellow_total"),
        ("home_", "team_total"),
        ("away_", "team_total"),
        ("mixed_", "mixed"),
    )
    for prefix, family in keyed_families:
        if market_key.startswith(prefix):
            return f"family:{family}"
    labeled_families = (
        ("resultat", "result_total"),
        ("beide_teams", "btts"),
        ("doppelte_chance", "double_chance"),
        ("team_1_gesamttore", "team_total"),
        ("team_2_gesamttore", "team_total"),
        ("teamtore", "team_total"),
        ("endergebnis", "result"),
        ("gesamttore", "total"),
    )
    for token, family in labeled_families:
        if token in market:
            return f"family:{family}"
    if market_key or market:
        return f"market:{market_key or market}"
    row_identity = (
        getattr(row, "candidate_id", None)
        or getattr(row, "key", None)
        or id(row)
    )
    return f"row:{_consumer_token(row_identity)}"


def consumer_fixture_label(row: object) -> str:
    """Return a compact public event label for grouped secondary markets."""

    for attribute in ("event_label", "event"):
        value = str(getattr(row, attribute, None) or "").strip()
        if value:
            return value[:160]
    home = str(getattr(row, "home_team", None) or "").strip()
    away = str(getattr(row, "away_team", None) or "").strip()
    if home and away:
        return f"{home} vs {away}"[:160]
    competitor_a = str(getattr(row, "competitor_a", None) or "").strip()
    competitor_b = str(getattr(row, "competitor_b", None) or "").strip()
    if competitor_a and competitor_b:
        return f"{competitor_a} vs {competitor_b}"[:160]
    return "diesem Spiel"


def group_consumer_markets_by_fixture(
    rows: Iterable[_ForecastRow],
) -> list[tuple[str, list[_ForecastRow]]]:
    """Group secondary forecasts by fixture while preserving model order."""

    grouped: dict[str, tuple[str, list[_ForecastRow]]] = {}
    for row in rows:
        identity = _consumer_fixture_identity(row)
        if identity not in grouped:
            grouped[identity] = (consumer_fixture_label(row), [])
        grouped[identity][1].append(row)
    return list(grouped.values())


def partition_consumer_featured_forecasts(
    rows: Iterable[_ForecastRow],
    *,
    max_featured: int = 3,
    allow_mixed_backfill: bool = False,
) -> tuple[list[_ForecastRow], list[_ForecastRow]]:
    """Choose useful, diverse main cards and keep every row visible.

    Market family and context completeness are presentation signals only. They
    never alter model probability, price evaluation or release eligibility.
    """

    if (
        isinstance(max_featured, bool)
        or not isinstance(max_featured, int)
        or max_featured < 1
    ):
        raise ValueError("max_featured must be a positive integer")
    original = list(rows)
    ranked = sorted(
        enumerate(original),
        key=lambda item: (
            _consumer_market_utility_tier(item[1]),
            0 if _consumer_context_complete(item[1]) else 1,
            item[0],
        ),
    )
    featured: list[_ForecastRow] = []
    featured_indices: set[int] = set()
    used_fixtures: set[str] = set()
    used_markets: set[str] = set()
    for index, row in ranked:
        mixed_backfill = allow_mixed_backfill and _consumer_market_is_mixed(row)
        if (
            _consumer_market_is_basis(row)
            and not _consumer_is_confirmed_tip(row)
            and not mixed_backfill
        ):
            continue
        fixture_identity = _consumer_fixture_identity(row)
        market_identity = _consumer_market_identity(row)
        can_feature = (
            len(featured) < max_featured
            and fixture_identity not in used_fixtures
            and market_identity not in used_markets
        )
        if can_feature:
            featured.append(row)
            featured_indices.add(index)
            used_fixtures.add(fixture_identity)
            used_markets.add(market_identity)
    secondary = [
        row for index, row in enumerate(original) if index not in featured_indices
    ]
    return featured, secondary


def partition_consumer_forecasts(
    rows: Iterable[_ForecastRow],
    *,
    quote_for: Callable[[_ForecastRow], Optional[MarketConsensus | dict]],
    now=None,
    price_status_for: Callable[..., ReferencePriceStatus] = (
        wettfinder_reference_price_status
    ),
) -> tuple[list[_ForecastRow], list[_ForecastRow]]:
    """Keep every forecast, but relegate confirmed extreme-short prices.

    Missing, thin, stale, or merely below-value quotes stay in the primary
    model order. Only a fresh TOO_LOW market whose best observed price is
    below the existing public usefulness floor moves to the secondary group.
    """

    primary: list[_ForecastRow] = []
    extreme_short: list[_ForecastRow] = []
    for row in rows:
        raw_quote = quote_for(row)
        quote = (
            raw_quote
            if isinstance(raw_quote, MarketConsensus)
            else MarketConsensus.from_dict(raw_quote)
        )
        minimum_odds = getattr(row, "minimum_odds", None)
        is_extreme_short = False
        if quote is not None and minimum_odds is not None:
            status = price_status_for(
                quote,
                minimum_odds,
                now=now,
            )
            is_extreme_short = (
                status.code == "TOO_LOW"
                and quote.best_odds < EXTREME_SHORT_ODDS_CUTOFF
            )
        (extreme_short if is_extreme_short else primary).append(row)
    return primary, extreme_short


def _decimal_input(value: str):
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def _save_tip(
    decision: PriceDecision,
    *,
    source: str,
) -> Optional[str]:
    try:
        store = TipStore(scope_id=storage_scope(st.session_state))
        if decision.status == "BET":
            store.save_decision(decision, source=source)
            return "Unter Meine Tipps gespeichert."
        if decision.quoted_odds is not None:
            candidate = decision.candidate
            store.archive_candidate(
                sport=candidate.sport,
                event_key=candidate.event_key,
                market=candidate.market,
                selection=candidate.selection or "keine Auswahl",
            )
    except (OSError, ValueError):
        LOGGER.exception("Consumer tip could not be persisted")
        return "Tipp konnte nicht gespeichert werden. Bitte später erneut versuchen."
    return None


def _render_stake_recommendation(decision: PriceDecision) -> None:
    if decision.status != "BET" or decision.stake_fraction <= 0:
        return
    st.caption(
        f"Einsatzvorschlag: {decision.stake_amount:.2f} € "
        f"({decision.stake_fraction * 100:.2f} % des Wettguthabens)"
    )


def _enforce_pending_release(decision: PriceDecision) -> PriceDecision:
    """A passed price cannot bypass the separate statistical release gate."""

    if not decision.candidate.release_pending or not decision.price_passed:
        return decision
    return PriceDecision(
        status="SHADOW",
        candidate=decision.candidate,
        quoted_odds=decision.quoted_odds,
        metrics=decision.metrics,
        stake_fraction=0.0,
        stake_amount=0.0,
        reasons=decision.reasons + (
            "Statistische Evidenzprüfung noch nicht abgeschlossen.",
        ),
    )


def evaluate_reference_price(
    candidate: RecommendationCandidate,
    quote: Optional[MarketConsensus | dict],
    *,
    bankroll: float,
    reference_binding_candidate: object = None,
    now: Optional[datetime] = None,
) -> ReferencePriceEvaluation:
    """Evaluate the exact automatic offer without producing UI side effects."""

    if now is None:
        evaluation_now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    else:
        evaluation_now = now.astimezone(timezone.utc)
    reference_quote = (
        quote
        if isinstance(quote, MarketConsensus)
        else MarketConsensus.from_dict(quote)
    )
    status = wettfinder_reference_price_status(
        reference_quote,
        candidate.minimum_odds,
        candidate=reference_binding_candidate,
        now=evaluation_now,
    )
    effective_quote = wettfinder_consensus(reference_quote, now=evaluation_now)
    decision = None
    if effective_quote is not None and status.usable_odds is not None:
        decision = _enforce_pending_release(
            evaluate_candidate_price(
                candidate,
                status.usable_odds,
                bankroll=bankroll,
                quote_confirmed=True,
            )
        )

    return ReferencePriceEvaluation(
        decision=decision,
        status=status,
        quote=effective_quote,
    )


def _render_reference_price(
    candidate: RecommendationCandidate,
    evaluation: ReferencePriceEvaluation,
) -> None:
    """Render the full-mode reference-price explanation."""

    decision = evaluation.decision
    status = evaluation.status
    quote = evaluation.quote

    if status.code == "PLAYABLE" and quote is not None:
        if candidate.release_pending:
            st.info(
                "Modell noch in statistischer Evidenzprüfung – Prognose "
                "sichtbar, kein Einsatz."
            )
        elif decision is not None and decision.status == "BET":
            st.success(
                f"SPIELBARER TIPP: {candidate.selection} | aktuelle "
                f"Quote {status.usable_odds:.2f} bei {status.bookmaker} | "
                "spielbar ab "
                f"{candidate.minimum_odds:.2f}"
            )
        else:
            st.info(
                f"PASSENDE QUOTE: {candidate.selection} | die aktuelle "
                f"Quote {status.usable_odds:.2f} bei {status.bookmaker} "
                "erreicht die "
                f"Value-Grenze von {candidate.minimum_odds:.2f}. Das Modell "
                "sammelt noch Praxisergebnisse; daher kein Einsatzvorschlag."
            )
    elif status.code == "BORDERLINE" and quote is not None:
        st.info(
            f"PREIS NOCH OFFEN: {candidate.selection}. Nur einzelne Anbieter "
            f"erreichen die Value-Grenze {candidate.minimum_odds:.2f}; der Preis ist deshalb "
            "noch nicht zuverlässig bestätigt. Die Prognose bleibt unverändert."
        )
    elif status.code == "TOO_LOW" and quote is not None:
        st.info(
            f"QUOTE ZU NIEDRIG: {candidate.selection}. Die aktuell beobachtete "
            f"Bestquote {quote.best_odds:.2f} liegt unter der benötigten "
            f"Value-Grenze {candidate.minimum_odds:.2f}. Die Prognose bleibt "
            "unverändert; nur der angebotene Preis ist zu niedrig. Die "
            "Value-Grenze ist keine erwartete Buchmacherquote."
        )
    else:
        reason = {
            "THIN": "Es liegen noch zu wenige Vergleichsquoten vor.",
            "STALE": "Die Vergleichsquote ist nicht mehr aktuell.",
            "UNAVAILABLE": "Keine exakt passende Marktquote verfügbar.",
            "INVALID_MINIMUM": "Die Value-Grenze konnte nicht sicher berechnet werden.",
        }.get(status.code, "Der Wettpreis kann noch nicht sicher bewertet werden.")
        st.info(
            f"PREIS NOCH OFFEN: {candidate.selection}. {reason} Das ist keine "
            "Aussage darüber, ob der mögliche "
            "Spielausgang richtig oder falsch ist."
        )

    if decision is not None and decision.status == "BET":
        _render_stake_recommendation(decision)


def _reference_execution_source(
    base_source: str,
    quote: MarketConsensus,
    status: ReferencePriceStatus,
) -> str:
    """Persist the concrete offer provenance without changing TipStore."""

    provider = {
        REFERENCE_SOURCE: "API-Football",
        ODDS_API_REFERENCE_SOURCE: "The Odds API",
    }.get(quote.source, quote.source[:12])
    return (
        f"{base_source[:18]} / {provider} / "
        f"{str(status.bookmaker or '')[:16]} "
        f"[{str(status.bookmaker_id or '')[:24]}] / "
        f"{str(status.observed_at or '')[:32]}"
    )


def _render_manual_check(
    candidate: RecommendationCandidate,
    *,
    key: str,
    bankroll_key: str,
    price_source: str,
    save_source: Optional[str],
    manual_surface: str = "expander",
) -> Optional[PriceDecision]:
    odds_widget_key = f"bet_odds_{key}"
    manual_bankroll_key = f"{bankroll_key}_{key}"
    if manual_surface == "popover":
        surface = st.popover("Eigene Quote prüfen")
    else:
        surface = st.expander("Eigene Buchmacherquote prüfen", expanded=False)
    with surface:
        st.caption(
            "Optional: Nur nötig, wenn die tatsächlich angebotene Quote mit "
            "der automatischen Marktübersicht verglichen werden soll."
        )
        with st.form(f"bet_price_{key}", border=False):
            price_column, bankroll_column = st.columns(2)
            with price_column:
                raw_odds = st.text_input(
                    f"{price_source} für {candidate.selection}",
                    placeholder="z. B. 1,95",
                    key=odds_widget_key,
                )
            with bankroll_column:
                bankroll = st.number_input(
                    "Aktuelles Wettguthaben",
                    min_value=1.0,
                    value=100.0,
                    step=10.0,
                    key=manual_bankroll_key,
                )
            confirmed = st.checkbox(
                f"Auswahl stimmt exakt: {candidate.selection} / {candidate.market}",
                value=False,
                key=f"bet_confirmed_{key}",
            )
            submitted = st.form_submit_button(
                "Eigene Quote prüfen",
                type="primary",
                use_container_width=True,
            )

        decision_state_key = f"bet_decision_{key}"
        if submitted:
            decision = _enforce_pending_release(
                evaluate_candidate_price(
                    candidate,
                    _decimal_input(raw_odds),
                    bankroll=bankroll,
                    quote_confirmed=confirmed,
                )
            )
            st.session_state[decision_state_key] = decision
            if (
                save_source
                and confirmed
                and decision.status != "PRICE_REQUIRED"
            ):
                message = _save_tip(
                    decision,
                    source=f"{save_source} / eigene Quote",
                )
                if message:
                    st.toast(message)
        else:
            decision = st.session_state.get(decision_state_key)
            if not isinstance(decision, PriceDecision):
                return None

        decision = _enforce_pending_release(decision)

        if decision.status == "PRICE_REQUIRED":
            st.info(
                f"Quote und exakte Auswahl bestätigen. Value-Grenze "
                f"{candidate.minimum_odds:.2f}."
            )
        elif decision.status == "BET":
            st.success(
                f"PREIS BESTANDEN: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}"
            )
        elif decision.status in {"SHADOW", "RESEARCH"}:
            if candidate.release_pending:
                st.info(
                    "Modell noch in statistischer Evidenzprüfung – Prognose "
                    "sichtbar, kein Einsatz."
                )
            else:
                st.info(
                    f"PREIS PASST: {candidate.selection} @ "
                    f"{decision.quoted_odds:.2f}. Diese Auswahl wird noch "
                    "geprüft; deshalb gibt es keinen Einsatzvorschlag."
                )
        else:
            st.info(
                f"MODELL-AUSWAHL BLEIBT: {candidate.selection}. Die angebotene "
                f"Quote erreicht die Value-Grenze {candidate.minimum_odds:.2f} "
                "noch nicht und reicht daher nicht für eine "
                "spielbare Preisbewertung."
            )
        if decision.status == "BET":
            _render_stake_recommendation(decision)
        return decision


def render_price_decision(
    candidate: RecommendationCandidate,
    *,
    key: str,
    bankroll_key: str = "shared_bet_finder_bankroll",
    price_source: str = "Dezimalquote",
    save_source: Optional[str] = None,
    live_price: bool = False,
    reference_quote: Optional[MarketConsensus | dict] = None,
    reference_binding_candidate: object = None,
    allow_manual_check: bool = False,
    presentation: str = "full",
    manual_surface: str = "expander",
) -> Optional[PriceDecision]:
    """Render one model selection while keeping forecast and price separate."""
    del live_price  # Kept for call-site compatibility.
    if presentation not in {"full", "compact"}:
        raise ValueError("presentation must be 'full' or 'compact'")
    if manual_surface not in {"expander", "popover"}:
        raise ValueError("manual_surface must be 'expander' or 'popover'")
    selection = candidate.selection or "keine Auswahl"
    if presentation == "full":
        st.subheader(f"{candidate.market}: {selection}")
        st.caption(candidate.event_label)

    if presentation == "full" and candidate.forecast_available:
        metrics = st.columns(3)
        metrics[0].metric(
            "Modellwahrscheinlichkeit",
            format_probability_percent(candidate.model_probability),
        )
        metrics[1].metric(
            "Vorsichtige Prognose",
            format_probability_percent(candidate.risk_adjusted_probability),
        )
        metrics[2].metric(
            "Value-Grenze",
            (
                f"{candidate.minimum_odds:.2f}"
                if candidate.minimum_odds is not None
                else "k. A."
            ),
            help=(
                "Preis, ab dem die vorsichtige Modellrechnung den Zielwert "
                "erreicht; keine erwartete oder übliche Buchmacherquote."
            ),
        )

    if candidate.blockers:
        if candidate.forecast_available:
            st.warning(
                "PROGNOSE VORHANDEN, ABER NICHT ALS TIPP FREIGEGEBEN."
            )
        else:
            st.error("KEINE BELASTBARE PROGNOSE.")
        return None

    bankroll = float(st.session_state.get(bankroll_key, 100.0) or 100.0)
    automatic_evaluation = evaluate_reference_price(
        candidate,
        reference_quote,
        bankroll=bankroll,
        reference_binding_candidate=reference_binding_candidate,
    )
    automatic_decision = automatic_evaluation.decision
    if presentation == "full":
        _render_reference_price(candidate, automatic_evaluation)
    elif automatic_decision is not None and automatic_decision.status == "BET":
        _render_stake_recommendation(automatic_decision)

    if (
        automatic_decision is not None
        and automatic_decision.status == "BET"
        and save_source
    ):
        if st.button(
            "Tipp merken",
            key=f"save_reference_{key}",
            use_container_width=True,
        ):
            message = _save_tip(
                automatic_decision,
                source=_reference_execution_source(
                    save_source,
                    automatic_evaluation.quote,
                    automatic_evaluation.status,
                ),
            )
            if message:
                st.toast(message)

    manual_decision = None
    if allow_manual_check:
        manual_decision = _render_manual_check(
            candidate,
            key=key,
            bankroll_key=bankroll_key,
            price_source=price_source,
            save_source=save_source,
            manual_surface=manual_surface,
        )

    return manual_decision or automatic_decision


__all__ = [
    "consumer_fixture_label",
    "group_consumer_markets_by_fixture",
    "merge_consumer_forecast_catalog",
    "partition_consumer_featured_forecasts",
    "partition_consumer_forecasts",
    "ReferencePriceEvaluation",
    "evaluate_reference_price",
    "render_price_decision",
]
