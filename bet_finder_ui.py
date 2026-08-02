"""Shared Streamlit output for a concrete bet-or-no-bet decision."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from betting_math import MINIMUM_RISK_ADJUSTED_ROI_PERCENT
from multi_sport_recommendations import (
    PriceDecision,
    RecommendationCandidate,
    evaluate_candidate_price,
    format_fair_odds,
    format_probability_percent,
)
from ui_components import edge_badge_html, ev_badge_html, plain_german


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
    selection = candidate.selection or "keine Auswahl"
    st.subheader(f"Prognose: {candidate.market}: {selection}")
    st.caption(
        f"{candidate.event_label} · Modellreife: {candidate.evidence_label}"
    )

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
        st.caption(
            "Diese Prognose entsteht ohne Quote. Die Quote ändert nicht die "
            "Prognose, sondern nur die Entscheidung, ob der Preis gut genug ist."
        )

    if candidate.blockers:
        if candidate.forecast_available:
            st.warning(
                "PROGNOSE VORHANDEN, ABER KEINE WETTFREIGABE - mindestens "
                "eine preisunabhängige Modell- oder Datenprüfung ist gesperrt."
            )
        else:
            st.error("KEINE BELASTBARE PROGNOSE - nicht wetten.")
        st.write("Gründe:")
        for reason in candidate.blockers:
            st.write(f"- {plain_german(reason)}")
        if candidate.evidence:
            with st.expander("Prüfdetails"):
                st.write(f"Modell: {candidate.model_name}")
                for reason in candidate.evidence:
                    st.write(f"- {reason}")
        return None

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
    elif decision.status == "SHADOW":
        st.info(
            f"SHADOW-TIPP: {candidate.selection} @ {decision.quoted_odds:.2f}. "
            "Modell und Preis bestehen die Prüfung, aber es gibt noch keine "
            "Echtgeldfreigabe und deshalb keinen Einsatz."
        )
    elif decision.status == "RESEARCH":
        st.warning(
            f"RESEARCH-SIGNAL: Der Preis für {candidate.selection} @ "
            f"{decision.quoted_odds:.2f} wäre rechnerisch ausreichend, aber "
            "dem Modell fehlt noch die unabhängige Modellfreigabe."
        )
    else:
        st.error(
            f"NICHT WETTEN ZU DIESER QUOTE - die Prognose bleibt "
            f"{candidate.selection} mit "
            f"{format_probability_percent(candidate.model_probability)}."
        )
        for reason in decision.reasons:
            st.write(f"- {plain_german(reason)}")

    if decision.metrics is not None:
        st.markdown(
            edge_badge_html(decision.metrics.risk_adjusted_edge, label="Risiko-Edge")
            + ev_badge_html(
                decision.metrics.risk_adjusted_expected_roi, label="Risiko-EV"
            )
            + '<span class="bb-edge-badge bb-edge-none">'
            f'<span class="bb-edge-label">Einsatz</span> '
            f"{decision.stake_fraction * 100:.2f} %</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Der Edge ist nur der Abstand zur Break-even-Wahrscheinlichkeit. "
            f"Das gemeinsame Preis-Gate ist ein risikobereinigter EV von mindestens "
            f"{MINIMUM_RISK_ADJUSTED_ROI_PERCENT:.1f} %."
        )

    with st.expander("Prüfdetails"):
        st.write(f"Modell: {candidate.model_name}")
        st.write(f"Modell-Fair-Quote: {format_fair_odds(candidate.fair_odds)}")
        st.write(
            f"Robustheitsabschlag: {candidate.probability_haircut:.1f} Prozentpunkte"
        )
        for reason in candidate.evidence:
            st.write(f"- {reason}")
    return decision
