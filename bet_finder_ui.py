"""Shared, customer-facing rendering for one concrete model tip."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import streamlit as st

from account_identity import storage_scope
from betting_math import MINIMUM_RISK_ADJUSTED_ROI_PERCENT
from market_consensus import (
    MarketConsensus,
    reference_price_status,
)
from multi_sport_recommendations import (
    PriceDecision,
    RecommendationCandidate,
    evaluate_candidate_price,
    format_fair_odds,
    format_probability_percent,
)
from tip_store import TipStore
from ui_components import edge_badge_html, ev_badge_html, plain_german


def _decimal_input(value: str):
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def _quote_time(quote: MarketConsensus) -> str:
    try:
        return datetime.fromisoformat(str(quote.quoted_at)).astimezone().strftime(
            "%d.%m.%Y %H:%M"
        )
    except (TypeError, ValueError):
        return "Zeit unbekannt"


def _save_tip(
    decision: PriceDecision,
    *,
    source: str,
) -> Optional[str]:
    try:
        store = TipStore(scope_id=storage_scope(st.session_state))
        if decision.status in {"BET", "SHADOW"}:
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
    except (OSError, ValueError) as exc:
        return f"Tipp konnte nicht gespeichert werden: {exc}"
    return None


def _render_decision_math(decision: PriceDecision) -> None:
    if decision.metrics is None:
        return
    st.markdown(
        edge_badge_html(decision.metrics.risk_adjusted_edge, label="Risiko-Edge")
        + ev_badge_html(
            decision.metrics.risk_adjusted_expected_roi,
            label="Risiko-EV",
        )
        + '<span class="bb-edge-badge bb-edge-none">'
        '<span class="bb-edge-label">Einsatz</span> '
        f"{decision.stake_fraction * 100:.2f} %</span>",
        unsafe_allow_html=True,
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
        st.success(
            f"TIPP: {candidate.selection} | konservative Referenzquote "
            f"{quote.conservative_odds:.2f} | spielbar ab "
            f"{candidate.minimum_odds:.2f}"
        )
    elif status.code == "BORDERLINE" and quote is not None:
        st.warning(
            f"KEINE WETTE: {candidate.selection} | Nur einzelne Anbieter "
            f"erreichen {candidate.minimum_odds:.2f}; der konservative "
            f"Marktpreis bestätigt die Auswahl nicht."
        )
    elif status.code == "TOO_LOW" and quote is not None:
        st.warning(
            f"KEINE WETTE: {candidate.selection} | Bestpreis "
            f"{quote.best_odds:.2f}, benötigt werden mindestens "
            f"{candidate.minimum_odds:.2f}."
        )
    else:
        reason = {
            "THIN": "zu wenige Anbieter für einen belastbaren Vergleich",
            "STALE": "Marktvergleich nicht mehr aktuell",
            "UNAVAILABLE": "exakte Marktquote im Feed nicht verfügbar",
            "INVALID_MINIMUM": "Mindestquote nicht belastbar",
        }.get(status.code, "keine automatische Preisfreigabe")
        st.info(
            f"KEINE WETTFREIGABE: Das Modell bevorzugt "
            f"{candidate.selection}, aber {reason}. Die rechnerische "
            f"Mindestquote {candidate.minimum_odds:.2f} ist eine "
            "Prüfschwelle, keine Empfehlung."
        )

    if quote is not None:
        st.caption(
            f"{quote.bookmaker_count} Anbieter | Marktbereich "
            f"{quote.lowest_odds:.2f}-{quote.best_odds:.2f} | Median "
            f"{quote.consensus_odds:.2f} | Stand {_quote_time(quote)}"
        )
    if decision is not None:
        _render_decision_math(decision)
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
            if save_source and confirmed:
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
        elif decision.actionable:
            st.success(
                f"PREIS BESTANDEN: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}"
            )
        elif decision.status in {"SHADOW", "RESEARCH"}:
            st.info(
                f"PREIS BESTANDEN: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}; Modellreife "
                f"{candidate.evidence_label}."
            )
        else:
            st.error(
                f"QUOTE ZU NIEDRIG: Die Prognose bleibt {candidate.selection}, "
                f"aber mindestens {candidate.minimum_odds:.2f} wird benötigt."
            )
            for reason in decision.reasons:
                st.write(f"- {plain_german(reason)}")
        _render_decision_math(decision)
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
    """Render a tip first; price evidence is automatic or optional detail."""
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
            "Konservativ",
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
        for reason in candidate.blockers:
            st.write(f"- {plain_german(reason)}")
        if candidate.evidence:
            with st.expander("Prüfdetails"):
                st.write(f"Modell: {candidate.model_name}")
                for reason in candidate.evidence:
                    st.write(f"- {reason}")
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

    if automatic_decision is not None and save_source:
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

    with st.expander("Analyse", expanded=False):
        st.write(f"Modell: {candidate.model_name}")
        st.write(f"Validierungsstand: {candidate.evidence_label}")
        st.write(f"Modell-Fair-Quote: {format_fair_odds(candidate.fair_odds)}")
        st.write(
            f"Robustheitsabschlag: {candidate.probability_haircut:.1f} Prozentpunkte"
        )
        for reason in candidate.evidence:
            st.write(f"- {reason}")
        st.caption(
            "Eine Quote verändert die Prognose nicht. Sie entscheidet nur, "
            f"ob der risikobereinigte EV mindestens "
            f"{MINIMUM_RISK_ADJUSTED_ROI_PERCENT:.1f} % erreicht."
        )
    return manual_decision or automatic_decision


__all__ = ["render_price_decision"]
