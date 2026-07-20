"""Shared Streamlit output for a concrete bet-or-no-bet decision."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from multi_sport_recommendations import (
    PriceDecision,
    RecommendationCandidate,
    evaluate_candidate_price,
)


def _decimal_input(value: str):
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def render_price_decision(
    candidate: RecommendationCandidate,
    *,
    key: str,
    bankroll_key: str = "shared_bet_finder_bankroll",
    price_source: str = "N1Bet",
) -> Optional[PriceDecision]:
    """Render one exact candidate and require a fresh manual bookmaker price."""
    st.subheader(candidate.selection or "Keine freigegebene Auswahl")
    st.caption(f"{candidate.event_label} | {candidate.market}")

    if candidate.blockers:
        st.error("NICHT WETTEN")
        for reason in candidate.blockers:
            st.write(f"- {reason}")
        if candidate.evidence:
            with st.expander("Prüfdetails"):
                st.write(f"Modell: {candidate.model_name}")
                for reason in candidate.evidence:
                    st.write(f"- {reason}")
        return None

    metrics = st.columns(3)
    metrics[0].metric("Modell", f"{candidate.model_probability:.1f} %")
    metrics[1].metric(
        "Konservativ",
        f"{candidate.risk_adjusted_probability:.1f} %",
    )
    metrics[2].metric("Mindestquote", f"{candidate.minimum_odds:.2f}")

    with st.form(f"bet_price_{key}", border=False):
        price_column, bankroll_column = st.columns(2)
        with price_column:
            raw_odds = st.text_input(
                f"{price_source}-Quote für {candidate.selection}",
                placeholder="z. B. 1,95",
                key=f"bet_odds_{key}",
            )
        with bankroll_column:
            bankroll = st.number_input(
                "Aktuelles Wettguthaben",
                min_value=1.0,
                value=100.0,
                step=10.0,
                key=bankroll_key,
            )
        confirmed = st.checkbox(
            f"Auswahl stimmt exakt: {candidate.selection} / {candidate.market}",
            value=False,
            key=f"bet_confirmed_{key}",
        )
        submitted = st.form_submit_button(
            "Quote prüfen",
            type="primary",
            use_container_width=True,
        )

    decision = evaluate_candidate_price(
        candidate,
        _decimal_input(raw_odds),
        bankroll=bankroll,
        quote_confirmed=submitted and confirmed,
    )
    if decision.status == "PRICE_REQUIRED":
        st.info(
            f"PREIS ERFORDERLICH: {decision.reasons[0]} "
            f"Mindestquote {candidate.minimum_odds:.2f}."
        )
    elif decision.actionable:
        st.success(
            f"WETTEN: {candidate.selection} @ {decision.quoted_odds:.2f} | "
            f"Einsatzreferenz {decision.stake_amount:.2f} "
            f"({decision.stake_fraction * 100:.2f} % des Guthabens)"
        )
    else:
        st.error("NICHT WETTEN")
        for reason in decision.reasons:
            st.write(f"- {reason}")

    if decision.metrics is not None:
        price_metrics = st.columns(3)
        price_metrics[0].metric(
            "Risiko-Edge", f"{decision.metrics.risk_adjusted_edge:.1f} pp"
        )
        price_metrics[1].metric(
            "Risiko-EV", f"{decision.metrics.risk_adjusted_expected_roi:.1f} %"
        )
        price_metrics[2].metric(
            "Einsatzreferenz", f"{decision.stake_fraction * 100:.2f} %"
        )

    with st.expander("Prüfdetails"):
        st.write(f"Modell: {candidate.model_name}")
        st.write(f"Modell-Fair-Quote: {candidate.fair_odds:.3f}")
        st.write(
            f"Robustheitsabschlag: {candidate.probability_haircut:.1f} Prozentpunkte"
        )
        for reason in candidate.evidence:
            st.write(f"- {reason}")
    return decision
