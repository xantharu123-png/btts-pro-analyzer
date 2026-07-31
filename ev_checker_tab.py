"""Wett-Check: eigenen fairen Preis gegen die Buchmacher-Quote prüfen.

Die Seite setzt die Lektion aus dem EV-Prinzip um: Du wettest nicht auf
ein Team, du kaufst eine Wahrscheinlichkeit zu einem Preis.  Drei Eingaben
(Quote, eigene Einschätzung in %, Einsatz) liefern Break-even, Edge,
Erwartungswert in CHF und ein klares JA / KNAPP / NEIN.
"""

from __future__ import annotations

import streamlit as st

from ev_calculator import (
    MIN_EDGE_FOR_BET,
    VERDICT_BET,
    VERDICT_CLOSE,
    breakeven_probability,
    edge_points,
    expected_profit,
    expected_value,
    verdict,
)


def _fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f} %".replace(".", ",")


def _fmt_pp(value: float) -> str:
    return f"{value * 100:+.1f} Punkte".replace(".", ",")


def _fmt_chf(value: float) -> str:
    return f"{value:+.2f} CHF".replace(".", ",")


def render_ev_checker() -> None:
    st.markdown(
        "Prüfe **vor jeder eigenen Wette**, ob der Preis stimmt: Die Quote ist "
        "kein Tipp, sie ist ein Preis. Du spielst nur, wenn deine Einschätzung "
        "deutlich über der Break-even-Marke der Quote liegt."
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
            "Deine Einschätzung (in %)",
            min_value=0.0,
            max_value=100.0,
            value=70.0,
            step=1.0,
            format="%.0f",
            help="Wie wahrscheinlich ist die Wette DEINER ehrlichen "
                 "Einschätzung nach? Nicht: wie sehr wünschst du sie dir.",
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

    probability = probability_pct / 100.0
    breakeven = breakeven_probability(odds)
    edge = edge_points(probability, odds)
    ev = expected_value(probability, odds)
    profit = expected_profit(probability, odds, stake)
    label, reason = verdict(probability, odds)

    col_be, col_edge, col_ev = st.columns(3)
    col_be.metric(
        "Break-even der Quote",
        _fmt_pct(breakeven),
        help="So oft musst du bei dieser Quote recht haben, um auf null zu kommen.",
    )
    col_edge.metric(
        "Dein Abstand zu Break-even",
        _fmt_pp(edge),
        help=f"Gespielt wird erst ab +{MIN_EDGE_FOR_BET * 100:.0f} Prozentpunkten "
             "Sicherheitsmarge — deine Schätzung kann danebenliegen.",
    )
    col_ev.metric(
        "Erwartungswert pro Wette",
        _fmt_pct(ev),
        delta=_fmt_chf(profit),
        help="So viel gewinnst oder verlierst du bei diesem Preis "
             "im langfristigen Schnitt pro Wette.",
    )

    if label == VERDICT_BET:
        st.success(f"**{label} — Preis ist falsch zu deinen Gunsten.** {reason}")
    elif label == VERDICT_CLOSE:
        st.warning(f"**{label} — Finger weg.** {reason}")
    else:
        st.error(f"**{label} — nicht wetten.** {reason}")

    hundred = expected_profit(probability, odds, stake * 100)
    st.caption(
        f"Langfristig-Bild: Bei 100 gleichen Wetten à {stake:.0f} CHF "
        f"(gesamt {stake * 100:.0f} CHF gesetzt) ist dein erwartetes Ergebnis "
        f"**{_fmt_chf(hundred)}**. Die einzelne Wette ist Zufall — "
        "100 Wetten sind Arithmetik."
    )

    with st.expander("Warum KNAPP schon NEIN bedeutet?"):
        st.markdown(
            f"Deine Prozent-Einschätzung ist eine Schätzung — sie kann um "
            f"ein paar Punkte danebenliegen. Liegt der Vorteil unter "
            f"{MIN_EDGE_FOR_BET * 100:.0f} Prozentpunkten, frisst dieser "
            f"Schätzfehler den ganzen Edge. **Beispiel Bayern:** Quote 1,50 "
            f"bei echten 71 % ist ein Kauf (+7 %). Dieselbe Bayern-Wette bei "
            f"Quote 1,40 gewinnst du zwei von drei Mal — und verlierst "
            f"trotzdem langfristig 6,7 % pro Wette. Oft gewinnen und gut "
            f"wetten sind verschiedene Dinge."
        )
