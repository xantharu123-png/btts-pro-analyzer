"""Shared, customer-facing rendering for one concrete model tip."""

from __future__ import annotations

import logging
from typing import Optional

import streamlit as st

from account_identity import storage_scope
from market_consensus import (
    MarketConsensus,
    reference_price_status,
)
from multi_sport_recommendations import (
    PriceDecision,
    RecommendationCandidate,
    evaluate_candidate_price,
    format_probability_percent,
)
from tip_store import TipStore


LOGGER = logging.getLogger(__name__)


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


def _render_reference_price(
    candidate: RecommendationCandidate,
    quote: Optional[MarketConsensus],
    *,
    bankroll: float,
) -> Optional[PriceDecision]:
    status = reference_price_status(quote, candidate.minimum_odds)
    decision = None
    if quote is not None and status.usable_odds is not None:
        decision = evaluate_candidate_price(
            candidate,
            status.usable_odds,
            bankroll=bankroll,
            quote_confirmed=True,
        )

    if status.code == "PLAYABLE" and quote is not None:
        if decision is not None and decision.status == "BET":
            st.success(
                f"SPIELBARER TIPP: {candidate.selection} | aktuelle "
                f"Vergleichsquote {quote.conservative_odds:.2f} | spielbar ab "
                f"{candidate.minimum_odds:.2f}"
            )
        else:
            st.info(
                f"PASSENDE QUOTE: {candidate.selection} | die aktuelle "
                f"Vergleichsquote {quote.conservative_odds:.2f} erreicht die "
                f"Mindestquote von {candidate.minimum_odds:.2f}. Das Modell "
                "sammelt noch Praxisergebnisse; daher kein Einsatzvorschlag."
            )
    elif status.code == "BORDERLINE" and quote is not None:
        st.info(
            f"PREIS NOCH OFFEN: {candidate.selection}. Nur einzelne Anbieter "
            f"erreichen {candidate.minimum_odds:.2f}; der Preis ist deshalb "
            "noch nicht zuverlässig bestätigt. Die Prognose bleibt unverändert."
        )
    elif status.code == "TOO_LOW" and quote is not None:
        st.info(
            f"QUOTE ZU NIEDRIG: {candidate.selection}. Die aktuell beobachtete "
            f"Bestquote {quote.best_odds:.2f} liegt unter der benötigten "
            f"Quote {candidate.minimum_odds:.2f}. Die Prognose bleibt "
            "unverändert; nur der angebotene Preis ist zu niedrig."
        )
    else:
        reason = {
            "THIN": "Es liegen noch zu wenige Vergleichsquoten vor.",
            "STALE": "Die Vergleichsquote ist nicht mehr aktuell.",
            "UNAVAILABLE": "Aktuell liegt keine exakt passende Vergleichsquote vor.",
            "INVALID_MINIMUM": "Die Mindestquote konnte nicht sicher berechnet werden.",
        }.get(status.code, "Der Wettpreis kann noch nicht sicher bewertet werden.")
        st.info(
            f"PREIS NOCH OFFEN: {candidate.selection}. {reason} Das ist keine "
            "Aussage darüber, ob der mögliche "
            "Spielausgang richtig oder falsch ist."
        )

    if decision is not None and decision.status == "BET":
        _render_stake_recommendation(decision)
    return decision


def _render_manual_check(
    candidate: RecommendationCandidate,
    *,
    key: str,
    bankroll_key: str,
    price_source: str,
    save_source: Optional[str],
) -> Optional[PriceDecision]:
    odds_widget_key = f"bet_odds_{key}"
    manual_bankroll_key = f"{bankroll_key}_{key}"
    with st.expander("Eigene Buchmacherquote prüfen", expanded=False):
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
            decision = evaluate_candidate_price(
                candidate,
                _decimal_input(raw_odds),
                bankroll=bankroll,
                quote_confirmed=confirmed,
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

        if decision.status == "PRICE_REQUIRED":
            st.info(
                f"Quote und exakte Auswahl bestätigen. Mindestquote "
                f"{candidate.minimum_odds:.2f}."
            )
        elif decision.status == "BET":
            st.success(
                f"PREIS BESTANDEN: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}"
            )
        elif decision.status in {"SHADOW", "RESEARCH"}:
            st.info(
                f"PREIS PASST: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}. Diese Auswahl wird noch "
                "geprüft; deshalb gibt es keinen Einsatzvorschlag."
            )
        else:
            st.info(
                f"MODELL-AUSWAHL BLEIBT: {candidate.selection}. Die angebotene "
                f"Quote reicht erst ab {candidate.minimum_odds:.2f} für eine "
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
    allow_manual_check: bool = False,
) -> Optional[PriceDecision]:
    """Render one model selection while keeping forecast and price separate."""
    del live_price  # Kept for call-site compatibility.
    selection = candidate.selection or "keine Auswahl"
    st.subheader(f"{candidate.market}: {selection}")
    st.caption(candidate.event_label)

    if candidate.forecast_available:
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
            "Mindestquote",
            (
                f"{candidate.minimum_odds:.2f}"
                if candidate.minimum_odds is not None
                else "k. A."
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

    quote = (
        reference_quote
        if isinstance(reference_quote, MarketConsensus)
        else MarketConsensus.from_dict(reference_quote)
    )
    bankroll = float(st.session_state.get(bankroll_key, 100.0) or 100.0)
    automatic_decision = _render_reference_price(
        candidate,
        quote,
        bankroll=bankroll,
    )

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
                source=f"{save_source} / {quote.source}",
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
        )

    return manual_decision or automatic_decision


__all__ = ["render_price_decision"]
