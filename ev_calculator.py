"""Pure expected-value calculations for the manual wager check.

The forecast, its explicit uncertainty deduction, and the offered price are
separate inputs. A fixed probability-point edge cannot represent model error
at every odds level, so the decision uses expected return after uncertainty.
"""

from __future__ import annotations

DEFAULT_PROBABILITY_UNCERTAINTY = 0.05
MIN_EXPECTED_ROI_FOR_BET = 0.03

VERDICT_PRICE_PASS = "PREIS OK"
VERDICT_BET = VERDICT_PRICE_PASS  # Backward-compatible import name.
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


def conservative_probability(
    probability: float,
    uncertainty: float = DEFAULT_PROBABILITY_UNCERTAINTY,
) -> float:
    """Deduct an explicit absolute uncertainty from a point forecast."""
    _validate_probability(probability)
    _validate_probability(uncertainty)
    return max(0.0, probability - uncertainty)


def verdict(
    probability: float,
    odds: float,
    *,
    uncertainty: float = DEFAULT_PROBABILITY_UNCERTAINTY,
    minimum_expected_roi: float = MIN_EXPECTED_ROI_FOR_BET,
) -> tuple[str, str]:
    """(Urteil, Begründung) — PREIS OK / KNAPP / NEIN.

    ``KNAPP`` means the point estimate is positive but the conservative
    estimate misses the required ROI. ``NEIN`` means even the point estimate
    has no positive expected return. ``PREIS OK`` is only a mathematical
    price result under the supplied probability; it is not a model or
    real-money release.
    """
    _validate_probability(minimum_expected_roi)
    point_ev = expected_value(probability, odds)
    adjusted_probability = conservative_probability(probability, uncertainty)
    adjusted_ev = expected_value(adjusted_probability, odds)
    if adjusted_ev >= minimum_expected_roi:
        return (
            VERDICT_BET,
            f"Nach {uncertainty * 100:.1f} Prozentpunkten Unsicherheitsabschlag "
            f"beträgt die verwendete Wahrscheinlichkeit "
            f"{adjusted_probability * 100:.1f} % und der Risiko-EV "
            f"{adjusted_ev * 100:+.1f} %.",
        )
    if point_ev > 0:
        return (
            VERDICT_CLOSE,
            f"Der Punktwert ist positiv ({point_ev * 100:+.1f} %), aber nach "
            f"{uncertainty * 100:.1f} Prozentpunkten Unsicherheitsabschlag "
            f"bleiben nur {adjusted_ev * 100:+.1f} % Risiko-EV; erforderlich "
            f"sind {minimum_expected_roi * 100:.1f} %.",
        )
    return (
        VERDICT_NO_BET,
        f"Erwartungswert {point_ev * 100:+.1f} % — bei diesem Preis verlierst du "
        "langfristig, egal wie oft die Wette im Einzelfall aufgeht.",
    )
