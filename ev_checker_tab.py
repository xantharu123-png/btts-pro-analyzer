"""Wett-Check: eigenen fairen Preis gegen die Buchmacher-Quote prüfen.

Die Seite setzt die Lektion aus dem EV-Prinzip um: Du wettest nicht auf
ein Team, du kaufst eine Wahrscheinlichkeit zu einem Preis.  Drei Eingaben
(Quote, eigene Einschätzung in %, Einsatz) liefern Break-even, Edge,
Erwartungswert in CHF und ein klares PREIS OK / KNAPP / NEIN.

Optional befüllt der automatische Wettfinder oder ein gespeichertes
Modell-Signal die Prozent-Einschätzung vor. Die Quote tippst du immer
selbst ein, denn der Preis entscheidet.
"""

from __future__ import annotations

from datetime import datetime
import math
from zoneinfo import ZoneInfo

import streamlit as st

from betting_math import minimum_acceptable_odds
from ev_calculator import (
    DEFAULT_PROBABILITY_UNCERTAINTY,
    MIN_EXPECTED_ROI_FOR_BET,
    VERDICT_BET,
    VERDICT_CLOSE,
    breakeven_probability,
    conservative_probability,
    edge_points,
    expected_profit,
    expected_value,
    verdict,
)
from ev_signal_sources import ModelSignal, list_signals

_MANUAL = "manual"
_ZURICH_TZ = ZoneInfo("Europe/Zurich")


def _fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f} %".replace(".", ",")


def _fmt_pp(value: float) -> str:
    return f"{value * 100:+.1f} Punkte".replace(".", ",")


def _fmt_chf(value: float) -> str:
    return f"{value:+.2f} CHF".replace(".", ",")


def _fmt_start(value: str | None) -> str:
    if not value:
        return "Startzeit offen"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Startzeit offen"
    if parsed.tzinfo is None:
        return "Startzeit offen"
    return parsed.astimezone(_ZURICH_TZ).strftime("%d.%m. %H:%M")


def _signal_inputs(signal: ModelSignal) -> tuple[float, float, float | None]:
    """Quantize conservatively to the exact 0.1-point UI controls."""
    probability_pct = math.floor(
        signal.probability * 1000.0 + 1e-12
    ) / 10.0
    haircut_pct = math.ceil(
        signal.probability_haircut * 1000.0 - 1e-12
    ) / 10.0
    minimum = minimum_acceptable_odds(
        probability_pct,
        probability_haircut=haircut_pct,
    )
    return probability_pct, haircut_pct, minimum


def render_ev_checker(scope: str | None = None) -> None:
    st.markdown(
        "Prüfe den Preis einer bereits begründeten Prognose: Die Quote ist "
        "kein Tipp, sie ist ein Preis. Du spielst nur, wenn deine Einschätzung "
        "deutlich über der Break-even-Marke der Quote liegt."
    )
    st.caption(
        "Diese Rechenhilfe erzeugt keine Prognose und keine Echtgeld-Freigabe. "
        "Sie bewertet nur die eingegebene Wahrscheinlichkeitsannahme."
    )

    signals = list_signals(scope=scope)
    by_key = {signal.key: signal for signal in signals}
    automatic = [
        signal
        for signal in signals
        if signal.source == "automated_wettfinder"
    ]
    if automatic:
        st.markdown("### Automatische Vorauswahl")
        for signal in automatic:
            probability_pct, haircut_pct, minimum_odds = _signal_inputs(signal)
            conservative = (probability_pct - haircut_pct) / 100.0
            minimum = (
                f"{minimum_odds:.2f}".replace(".", ",")
                if minimum_odds is not None
                else "offen"
            )
            st.markdown(f"**{signal.label}**")
            st.caption(
                f"{_fmt_start(signal.scheduled_start)} · "
                f"Konservativ {_fmt_pct(conservative)} · "
                f"N1Bet-Mindestquote {minimum} · "
                f"{signal.evidence_stage} · Preis noch eingeben"
            )

    def _apply_signal() -> None:
        signal = by_key.get(st.session_state.get("ev_signal_choice"))
        if signal is not None:
            probability_pct, haircut_pct, _minimum = _signal_inputs(signal)
            st.session_state["ev_prob"] = probability_pct
            st.session_state["ev_uncertainty"] = haircut_pct
        else:
            st.session_state["ev_uncertainty"] = (
                DEFAULT_PROBABILITY_UNCERTAINTY * 100.0
            )

    st.session_state.setdefault("ev_prob", 70.0)
    st.session_state.setdefault(
        "ev_uncertainty",
        DEFAULT_PROBABILITY_UNCERTAINTY * 100.0,
    )
    choice = st.selectbox(
        "Modell-Signal übernehmen (optional)",
        [_MANUAL] + list(by_key),
        format_func=lambda key: (
            "— manuell eingeben —" if key == _MANUAL else by_key[key].label
        ),
        key="ev_signal_choice",
        on_change=_apply_signal,
        help="Gespeicherte Fußball-, Tennis- und E-Sport-Signale übernehmen "
             "Punktprognose und den zugehörigen Modellabschlag gemeinsam.",
    )
    chosen = by_key.get(choice)
    if chosen is not None:
        chosen_probability, chosen_haircut, chosen_minimum = _signal_inputs(chosen)
        prob_text = f"{chosen_probability:.1f}".replace(".", ",")
        haircut_text = f"{chosen_haircut:.1f}".replace(".", ",")
        minimum_text = (
            f" · Mindestquote {chosen_minimum:.2f}".replace(".", ",")
            if chosen_minimum is not None
            else ""
        )
        st.caption(
            f"Übernommen: **{prob_text} % Punktprognose**, "
            f"**{haircut_text} Prozentpunkte Modellabschlag** · "
            f"Evidenz {chosen.evidence_stage}{minimum_text} — {chosen.detail}."
        )

    col_odds, col_prob, col_stake = st.columns(3)
    with col_odds:
        odds = st.number_input(
            "Buchmacher-Quote",
            min_value=1.01,
            max_value=1000.0,
            value=1.50,
            step=0.05,
            format="%.2f",
            help="Die Quote, die dir der Buchmacher anbietet.",
        )
    with col_prob:
        probability_pct = st.number_input(
            "Punktprognose (in %)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.1f",
            key="ev_prob",
            help="Wie wahrscheinlich ist die Wette DEINER ehrlichen "
                 "Einschätzung nach? Vom Modell vorbefüllbar — "
                 "du bleibst verantwortlich.",
        )
    with col_stake:
        stake = st.number_input(
            "Geplanter Einsatz (CHF)",
            min_value=0.0,
            max_value=100000.0,
            value=25.0,
            step=5.0,
            format="%.0f",
        )

    uncertainty_pct = st.slider(
        "Modell-Unsicherheitsabschlag",
        min_value=0.0,
        max_value=40.0,
        step=0.1,
        key="ev_uncertainty",
        help=(
            "Absolute Prozentpunkte, die vor der Einsatzentscheidung von der "
            "Punktprognose abgezogen werden. Bei einem übernommenen Signal "
            "kommt dieser Wert aus exakt derselben Modellpolicy wie der Tipp."
        ),
    )

    probability = probability_pct / 100.0
    uncertainty = uncertainty_pct / 100.0
    adjusted_probability = conservative_probability(probability, uncertainty)
    breakeven = breakeven_probability(odds)
    edge = edge_points(probability, odds)
    point_ev = expected_value(probability, odds)
    risk_ev = expected_value(adjusted_probability, odds)
    profit = expected_profit(adjusted_probability, odds, stake)
    label, reason = verdict(
        probability,
        odds,
        uncertainty=uncertainty,
    )

    col_be, col_edge, col_ev = st.columns(3)
    col_be.metric(
        "Break-even der Quote",
        _fmt_pct(breakeven),
        help="So oft musst du bei dieser Quote recht haben, um auf null zu kommen.",
    )
    col_edge.metric(
        "Dein Abstand zu Break-even",
        _fmt_pp(edge),
        help=(
            "Diagnosewert, kein starres Preis-Gate. Derselbe Abstand besitzt "
            "bei verschiedenen Quoten einen unterschiedlichen Geldwert."
        ),
    )
    col_ev.metric(
        "Risiko-EV pro Wette",
        _fmt_pct(risk_ev),
        delta=_fmt_chf(profit),
        help=(
            f"Nach {uncertainty_pct:.1f} Prozentpunkten Abschlag. "
            f"Freigabe ab {MIN_EXPECTED_ROI_FOR_BET * 100:.1f} % Risiko-EV."
        ),
    )
    st.caption(
        f"Punktschätzung: {probability_pct:.1f} % / EV {point_ev * 100:+.1f} % · "
        f"Konservativ: {adjusted_probability * 100:.1f} % / "
        f"Risiko-EV {risk_ev * 100:+.1f} %"
    )

    if label == VERDICT_BET:
        st.success(
            f"**{label} — unter dieser Wahrscheinlichkeitsannahme rechnerisch "
            f"ausreichend.** {reason} Das ist keine eigenständige Wettfreigabe."
        )
    elif label == VERDICT_CLOSE:
        st.warning(f"**{label} — Finger weg.** {reason}")
    else:
        st.error(f"**{label} — nicht wetten.** {reason}")

    hundred = expected_profit(adjusted_probability, odds, stake * 100)
    st.caption(
        f"Langfristig-Bild: Bei 100 gleichen Wetten à {stake:.0f} CHF "
        f"(gesamt {stake * 100:.0f} CHF gesetzt) ist dein erwartetes Ergebnis "
        f"**{_fmt_chf(hundred)}**. Die einzelne Wette ist Zufall — "
        "auch 100 Wetten folgen dieser Rechnung nur, wenn die verwendete "
        "Wahrscheinlichkeit wirklich kalibriert ist."
    )

    with st.expander("Warum eine wahrscheinliche Auswahl trotzdem keine Wette sein kann"):
        st.markdown(
            "Die Prognose beantwortet, was am wahrscheinlichsten passiert. "
            "Der Preis beantwortet, ob sich die Wette lohnt. **Beispiel:** "
            "Eine Auswahl kann mit 70 % sehr wahrscheinlich sein. Bei Quote "
            "1,30 liegt ihr Erwartungswert trotzdem bei −9 %. Die Prognose "
            "bleibt 70 %, aber die korrekte Wettentscheidung lautet NEIN. "
            "Der explizite Unsicherheitsabschlag verhindert zusätzlich, dass "
            "eine zu genaue Punktschätzung als Gewissheit behandelt wird."
        )
