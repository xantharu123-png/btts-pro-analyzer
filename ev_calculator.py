"""Erwartungswert-Rechner: eigenen fairen Preis gegen die Buchmacher-Quote prüfen.

Kernidee (App-Seite "Wett-Check"): Du wettest nicht auf ein Team, du kaufst
eine Wahrscheinlichkeit zu einem Preis.  Gespielt wird nur, wenn die eigene
Wahrscheinlichkeit deutlich ÜBER der Break-even-Marke der Quote liegt —
die Sicherheitsmarge MIN_EDGE_FOR_BET deckt den Schätzfehler der eigenen
Einschätzung.

Alle Funktionen sind rein (kein Streamlit, kein IO) und werfen ValueError
bei unsinnigen Eingaben.
"""

from __future__ import annotations

MIN_EDGE_FOR_BET = 0.03  # 3 Prozentpunkte Sicherheitsmarge über Break-even

VERDICT_BET = "JA"
VERDICT_CLOSE = "KNAPP"
VERDICT_NO_BET = "NEIN"


def _is_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and value == value  # NaN-Wache
    )


def _validate_probability(probability: float) -> None:
    if not _is_number(probability):
        raise ValueError("Wahrscheinlichkeit muss eine Zahl sein.")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Wahrscheinlichkeit muss zwischen 0 und 1 liegen.")


def _validate_odds(odds: float) -> None:
    if not _is_number(odds):
        raise ValueError("Quote muss eine Zahl sein.")
    if odds <= 1.0:
        raise ValueError("Quote muss größer als 1.0 sein.")


def breakeven_probability(odds: float) -> float:
    """Wahrscheinlichkeit, ab der die Quote langfristig +-0 ist (1 / Quote)."""
    _validate_odds(odds)
    return 1.0 / odds


def expected_value(probability: float, odds: float) -> float:
    """Erwarteter Gewinn pro 1 Einsatz-Einheit (+0.05 = +5 % pro Wette)."""
    _validate_probability(probability)
    _validate_odds(odds)
    return probability * odds - 1.0


def expected_profit(probability: float, odds: float, stake: float) -> float:
    """Erwarteter Gewinn in Währung bei gegebenem Einsatz."""
    if not _is_number(stake) or stake < 0:
        raise ValueError("Einsatz muss eine Zahl >= 0 sein.")
    return expected_value(probability, odds) * stake


def edge_points(probability: float, odds: float) -> float:
    """Abstand der eigenen Einschätzung über Break-even (in Wkt.-Punkten)."""
    _validate_probability(probability)
    _validate_odds(odds)
    return probability - breakeven_probability(odds)


def verdict(probability: float, odds: float) -> tuple[str, str]:
    """(Urteil, Begründung) — JA / KNAPP / NEIN.

    KNAPP heißt: rechnerisch leicht über Break-even, aber unter der
    Sicherheitsmarge — der Schätzfehler der eigenen Einschätzung frisst
    den Vorteil.  NEIN heißt: negativer Erwartungswert, langfristig
    garantierter Verlust, egal wie oft die Wette einmal aufgeht.
    """
    ev = expected_value(probability, odds)
    edge = edge_points(probability, odds)
    if edge >= MIN_EDGE_FOR_BET:
        return (
            VERDICT_BET,
            f"Deine Einschätzung liegt {edge * 100:.1f} Prozentpunkte über "
            f"Break-even und deckt die Sicherheitsmarge von "
            f"{MIN_EDGE_FOR_BET * 100:.0f} Punkten (Erwartungswert {ev * 100:+.1f} %).",
        )
    if ev > 0:
        return (
            VERDICT_CLOSE,
            f"Rechnerisch leicht positiv ({ev * 100:+.1f} %), aber unter der "
            f"Sicherheitsmarge von {MIN_EDGE_FOR_BET * 100:.0f} Prozentpunkten — "
            "der Schätzfehler deiner Einschätzung frisst den Vorteil.",
        )
    return (
        VERDICT_NO_BET,
        f"Erwartungswert {ev * 100:+.1f} % — bei diesem Preis verlierst du "
        "langfristig, egal wie oft die Wette im Einzelfall aufgeht.",
    )
