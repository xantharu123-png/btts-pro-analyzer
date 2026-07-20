"""Price-independent football candidates for the shared betting gate."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping, Optional

from bet_finder_candidates import build_probability_candidate
from multi_sport_recommendations import RecommendationCandidate


PREMATCH_MAX_AGE_SECONDS = 6 * 3600
LIVE_MAX_AGE_SECONDS = 120


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _future_kickoff(value: Any, now: Optional[datetime] = None) -> Optional[bool]:
    if not value:
        return None
    try:
        kickoff = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if kickoff.tzinfo is None:
        return None
    reference = now or datetime.now().astimezone()
    if reference.tzinfo is None:
        return None
    return kickoff.astimezone() > reference.astimezone()


def prematch_btts_candidate(
    row: Mapping[str, Any],
    *,
    snapshot_age_seconds: Optional[float],
    validated_model_available: bool,
) -> RecommendationCandidate:
    analysis = row.get("_analysis")
    analysis = analysis if isinstance(analysis, dict) else {}
    details = analysis.get("details")
    details = details if isinstance(details, dict) else {}
    evidence_breakdown = details.get("evidence_breakdown")
    evidence_breakdown = evidence_breakdown if isinstance(evidence_breakdown, dict) else {}
    samples = evidence_breakdown.get("samples")
    samples = samples if isinstance(samples, dict) else {}

    home = str(row.get("Home") or "Heimteam")
    away = str(row.get("Away") or "Auswärtsteam")
    probability = _finite(row.get("BTTS_num", row.get("BTTS %")))
    quality = _finite(row.get("Quality_num", row.get("Data Quality")))
    ml_probability = _finite(analysis.get("ml_probability"))
    statistical_probability = _finite(analysis.get("statistical_probability"))
    spread = (
        abs(ml_probability - statistical_probability)
        if ml_probability is not None and statistical_probability is not None
        else None
    )
    venue_samples = (
        int(_finite(samples.get("home_venue_matches")) or 0),
        int(_finite(samples.get("away_venue_matches")) or 0),
    )
    form_samples = (
        int(_finite(samples.get("home_form_matches")) or 0),
        int(_finite(samples.get("away_form_matches")) or 0),
    )

    blockers: list[str] = []
    if snapshot_age_seconds is None or snapshot_age_seconds < -30:
        blockers.append("Der Prematch-Snapshot besitzt keine verlässliche Zeitbasis.")
    elif snapshot_age_seconds > PREMATCH_MAX_AGE_SECONDS:
        blockers.append("Der Prematch-Snapshot ist älter als sechs Stunden.")
    if _future_kickoff(row.get("_fixture_date")) is not True:
        blockers.append("Die zukünftige Anstoßzeit ist nicht eindeutig verifiziert.")
    if not validated_model_available or details.get("ml_active") is not True:
        blockers.append("Das chronologisch validierte BTTS-Modell ist für dieses Spiel nicht aktiv.")
    if probability is None or probability < 58.0:
        blockers.append("Die BTTS-Modellwahrscheinlichkeit liegt unter 58 %.")
    if quality is None or quality < 70.0:
        blockers.append("Der Evidenzscore liegt unter 70 %.")
    if min(venue_samples) < 5 or min(form_samples) < 5:
        blockers.append("Mindestens fünf Venue- und Formspiele je Team fehlen.")
    if spread is None or spread > 15.0:
        blockers.append("ML- und Statistikmodell stimmen nicht ausreichend überein.")

    quality_penalty = max(0.0, 80.0 - (quality or 0.0)) * 0.12
    spread_penalty = max(0.0, (spread or 20.0) - 5.0) * 0.25
    haircut = min(20.0, max(10.0, 10.0 + quality_penalty + spread_penalty))
    fixture_key = row.get("_fixture_id") or f"{row.get('_fixture_date')}:{home}:{away}"
    evidence = (
        f"Evidenzscore {quality:.1f} %." if quality is not None else "Evidenzscore fehlt.",
        f"Venue-Stichprobe {venue_samples[0]}/{venue_samples[1]}, Form {form_samples[0]}/{form_samples[1]}.",
        f"ML/Statistik-Abstand {spread:.1f} Prozentpunkte." if spread is not None else "Modellabstand nicht berechenbar.",
        f"Robustheitsabschlag {haircut:.1f} Prozentpunkte für Kalibrierungs-, Aufstellungs- und Marktrisiko.",
    )
    return build_probability_candidate(
        event_key=fixture_key,
        sport="Fußball",
        event_label=f"{home} vs {away}",
        market="Beide Teams treffen",
        selection="Ja",
        model_probability=probability,
        probability_haircut=haircut,
        model_name="Walk-forward BTTS + statistischer Konsistenzcheck",
        evidence=evidence,
        blockers=blockers,
        expected_total=_finite(row.get("xG Total")),
    )


def live_football_candidate(
    analysis: Mapping[str, Any],
    *,
    market: str,
    selection: str,
    probability: Any,
    snapshot_age_seconds: Optional[float],
) -> RecommendationCandidate:
    home = str(analysis.get("home_team") or "Heimteam")
    away = str(analysis.get("away_team") or "Auswärtsteam")
    minute = _finite(analysis.get("minute"))
    quality = str(analysis.get("live_data_quality") or "INSUFFICIENT").upper()
    probability_number = _finite(probability)
    blockers: list[str] = []
    if snapshot_age_seconds is None or snapshot_age_seconds < -15:
        blockers.append("Der Live-Snapshot besitzt keine verlässliche Zeitbasis.")
    elif snapshot_age_seconds > LIVE_MAX_AGE_SECONDS:
        blockers.append("Der Live-Snapshot ist älter als zwei Minuten.")
    if minute is None or not 1 <= minute <= 93:
        blockers.append("Die reguläre Spielminute ist nicht verifiziert.")
    if not str(analysis.get("score") or "").strip():
        blockers.append("Der aktuelle Spielstand fehlt.")
    if quality not in {"MEDIUM", "LOW"}:
        blockers.append("Die Live-Daten reichen für diesen Markt nicht aus.")
    if probability_number is None or probability_number < 55.0:
        blockers.append("Die Modellwahrscheinlichkeit liegt unter 55 %.")

    red_cards = analysis.get("red_cards")
    red_cards = red_cards if isinstance(red_cards, dict) else {}
    if red_cards.get("supported") is False:
        blockers.append("Der Platzverweisstand ist für das Restspielmodell nicht eindeutig.")
    haircut = 12.0 if quality == "MEDIUM" else 18.0
    event_key = analysis.get("fixture_id") or f"{home}:{away}:{analysis.get('minute')}"
    evidence = (
        f"Live-Stand {analysis.get('score', 'n/a')} in Minute {analysis.get('minute', 'n/a')}.",
        f"Datenbasis {quality}; Robustheitsabschlag {haircut:.1f} Prozentpunkte.",
        f"Platzverweisstatus {red_cards.get('status', 'nicht gemeldet')}.",
    )
    return build_probability_candidate(
        event_key=event_key,
        sport="Fußball Live",
        event_label=f"{home} vs {away}",
        market=market,
        selection=selection,
        model_probability=probability_number,
        probability_haircut=haircut,
        model_name="Restspiel-Poisson mit Live-xG/Prematch-Prior",
        evidence=evidence,
        blockers=blockers,
    )


def red_card_candidate(
    entry: Mapping[str, Any],
    *,
    snapshot_age_seconds: Optional[float],
) -> RecommendationCandidate:
    card = entry.get("card")
    card = card if isinstance(card, dict) else {}
    prediction = entry.get("prediction")
    prediction = prediction if isinstance(prediction, dict) else {}
    probabilities = (
        (str(entry.get("opponent") or "Gegner"), _finite(prediction.get("next_goal_by_opponent"))),
        (str(card.get("team") or "Team mit Platzverweis"), _finite(prediction.get("next_goal_by_red_team"))),
        ("Kein weiteres Tor", _finite(prediction.get("no_more_goals"))),
    )
    valid_probabilities = [(label, value) for label, value in probabilities if value is not None]
    selection, probability_decimal = max(valid_probabilities, key=lambda item: item[1]) if valid_probabilities else ("Keine Auswahl", None)
    probability = probability_decimal * 100.0 if probability_decimal is not None else None
    quality = str(prediction.get("data_quality") or "INSUFFICIENT").upper()
    blockers: list[str] = []
    if entry.get("error"):
        blockers.append(str(entry["error"]))
    if snapshot_age_seconds is None or snapshot_age_seconds < -15:
        blockers.append("Der Platzverweis-Snapshot besitzt keine verlässliche Zeitbasis.")
    elif snapshot_age_seconds > LIVE_MAX_AGE_SECONDS:
        blockers.append("Der Platzverweis-Snapshot ist älter als zwei Minuten.")
    if prediction.get("too_late_for_signal") is True:
        blockers.append("Für eine neue Wette bleibt zu wenig reguläre Spielzeit.")
    if entry.get("fixture_red_card_count") != 1:
        blockers.append("Mehrere Platzverweise werden vom 11-gegen-10-Modell nicht unterstützt.")
    if quality != "MEDIUM":
        blockers.append("Live-xG und Spielminute reichen nicht für die strenge Datenbasis.")
    if probability is None or probability < 55.0:
        blockers.append("Keine Nächstes-Tor-Auswahl erreicht 55 % Modellwahrscheinlichkeit.")

    home = str(entry.get("home") or "Heimteam")
    away = str(entry.get("away") or "Auswärtsteam")
    evidence = (
        f"Stand {entry.get('score', 'n/a')}, Platzverweis in Minute {card.get('minute', 'n/a')}.",
        f"Modell-Snapshot Minute {entry.get('prediction_minute', 'n/a')}, Datenbasis {quality}.",
        "Robustheitsabschlag 15,0 Prozentpunkte für seltene Ereignisse, Taktikwechsel und Modellunsicherheit.",
    )
    return build_probability_candidate(
        event_key=card.get("card_id") or f"{home}:{away}:{card.get('minute')}",
        sport="Fußball Live",
        event_label=f"{home} vs {away}",
        market="Nächstes Tor",
        selection=selection,
        model_probability=probability,
        probability_haircut=15.0,
        model_name="Platzverweis-Wirkungsmodell",
        evidence=evidence,
        blockers=blockers,
    )
