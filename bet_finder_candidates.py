"""Generic price-independent candidate construction shared by all finders."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from multi_sport_recommendations import (
    EVIDENCE_RESEARCH,
    RecommendationCandidate,
    _candidate,
    _finite_number,
)


def build_probability_candidate(
    *,
    event_key: Any,
    sport: str,
    event_label: str,
    market: str,
    selection: str,
    model_probability: Any,
    probability_haircut: Any,
    model_name: str,
    evidence: Sequence[str],
    blockers: Sequence[str] = (),
    line: Optional[float] = None,
    expected_total: Optional[float] = None,
    evidence_stage: str = EVIDENCE_RESEARCH,
) -> RecommendationCandidate:
    """Build a generic candidate and fail closed on invalid model inputs."""
    normalized_blockers = [
        str(reason).strip() for reason in blockers if str(reason).strip()
    ]
    probability = _finite_number(model_probability)
    haircut = _finite_number(probability_haircut)
    key = str(event_key).strip()
    label = str(event_label).strip()
    market_label = str(market).strip()
    selection_label = str(selection).strip()
    if not key:
        normalized_blockers.append("Die Ereignis-ID fehlt.")
    if not label:
        normalized_blockers.append("Die Ereignisbezeichnung fehlt.")
    if not market_label or not selection_label:
        normalized_blockers.append("Markt und Auswahl sind nicht eindeutig.")
    if probability is None or not 0.0 < probability < 100.0:
        normalized_blockers.append("Die Modellwahrscheinlichkeit ist ungültig.")
    if haircut is None or not 0.0 <= haircut <= 40.0:
        normalized_blockers.append("Der Robustheitsabschlag ist ungültig.")

    if normalized_blockers:
        return RecommendationCandidate(
            event_key=key or "invalid-event",
            sport=str(sport).strip() or "Unbekannt",
            event_label=label or "Unbekanntes Ereignis",
            market=market_label or "Kein freigegebener Markt",
            selection=selection_label or None,
            line=line,
            model_probability=probability,
            risk_adjusted_probability=None,
            probability_haircut=haircut,
            fair_odds=None,
            minimum_odds=None,
            model_name=str(model_name).strip() or "Kein belastbares Modell",
            expected_total=expected_total,
            evidence=tuple(str(reason) for reason in evidence),
            blockers=tuple(dict.fromkeys(normalized_blockers)),
            evidence_stage=evidence_stage,
        )

    return _candidate(
        event_key=key,
        sport=str(sport).strip() or "Unbekannt",
        event_label=label,
        market=market_label,
        selection=selection_label,
        line=line,
        model_probability=probability,
        probability_haircut=haircut,
        model_name=str(model_name).strip() or "Unbenanntes Modell",
        expected_total=expected_total,
        evidence=evidence,
        evidence_stage=evidence_stage,
    )


__all__ = ["build_probability_candidate"]
