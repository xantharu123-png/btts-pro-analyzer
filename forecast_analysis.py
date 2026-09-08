"""Deterministic, price-free facts for a short public forecast explanation.

No inference from prose, prices, other candidates or current provider data.
The optional evidence envelope is bound to native event/side identity and the
original model clocks. Legacy rows deliberately receive an honest fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Mapping
from zoneinfo import ZoneInfo

from challenge_engine import MARKET_BY_KEY


_SCHEMA = "football-card-analysis-v1"
_CONTEXT_MAX_AGE = timedelta(minutes=75)
_ZURICH = ZoneInfo("Europe/Zurich")
_GOAL_KINDS = {"result", "double_chance", "btts", "total", "team_total", "team_range", "result_total", "mixed_or"}
_COUNT_UNITS = {"corner_total": "Ecken", "team_corners": "Ecken", "yellow_total": "Gelbe Karten", "team_yellow": "Gelbe Karten"}


@dataclass(frozen=True)
class ForecastAnalysis:
    basis: str
    caution: str
    samples: str = ""


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _integer(value: object, *, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _clock(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _alias(row: Mapping, first: str, second: str) -> object:
    if first in row and second in row and row[first] != row[second]:
        return None
    return row.get(first, row.get(second))


def _identity(row: Mapping, *, clocks: bool = True) -> dict | None:
    result = {name: row.get(name) for name in (
        "candidate_id", "fixture_id", "home_team", "away_team", "market_key", "probability", "model_scope",
    )}
    result["home_id"] = _alias(row, "home_id", "home_team_id")
    result["away_id"] = _alias(row, "away_id", "away_team_id")
    scheduled = _clock(_alias(row, "scheduled_start", "kickoff"))
    if (
        not all(_integer(result[name], minimum=1) for name in ("fixture_id", "home_id", "away_id"))
        or result["home_id"] == result["away_id"]
        or not all(isinstance(result[name], str) and 0 < len(result[name].strip()) <= 200 for name in (
            "candidate_id", "home_team", "away_team", "market_key", "model_scope",
        ))
        or not _number(result["probability"])
        or not 0 < result["probability"] < 1
        or scheduled is None
    ):
        return None
    result["scheduled_start"] = scheduled.isoformat()
    if clocks:
        for field in ("modeled_at", "input_cutoff_at"):
            value = row.get(field)
            clock = _clock(value)
            if value is not None and clock is None:
                return None
            if clock is not None and clock > scheduled:
                return None
            result[field] = clock.isoformat() if clock else None
        if result["modeled_at"] and result["input_cutoff_at"] and result["input_cutoff_at"] > result["modeled_at"]:
            return None
    return result


def _basis_projection(raw: Mapping) -> dict:
    result = {}
    for home, away in (("expected_home_goals", "expected_away_goals"), ("expected_market_home", "expected_market_away")):
        if all(_number(raw.get(field)) for field in (home, away)):
            result.update({home: raw[home], away: raw[away]})
    if raw.get("expected_unit") in ("Ecken", "Gelbe Karten"):
        result["expected_unit"] = raw["expected_unit"]
    for field in ("venue_samples", "form_samples"):
        values = raw.get(field)
        if isinstance(values, (tuple, list)) and len(values) == 2 and all(_integer(n, minimum=1) for n in values):
            result[field] = list(values)
    return result


def _context_projection(raw: Mapping) -> dict:
    """Keep typed observation facts only, never provider prose or player names."""
    result = {}
    injuries = _mapping(raw.get("injuries"))
    if (
        injuries.get("status") in ("observed", "passed", "blocked")
        and injuries.get("availability") == "available"
        and injuries.get("coverage_available") is True
        and _clock(injuries.get("checked_at")) is not None
        and all(_integer(injuries.get(field)) for field in ("home_missing", "away_missing"))
    ):
        result["injuries"] = {name: injuries[name] for name in (
            "status", "availability", "coverage_available", "checked_at", "home_missing", "away_missing",
        )}
        if isinstance(injuries.get("impact_assessment_complete"), bool):
            result["injuries"]["impact_assessment_complete"] = injuries["impact_assessment_complete"]
    lineups = _mapping(raw.get("lineups"))
    if lineups.get("status") in ("passed", "pending", "confirmation_due", "unavailable", "blocked") and _clock(lineups.get("checked_at")):
        result["lineups"] = {name: lineups[name] for name in ("status", "checked_at")}
    applied = _mapping(raw.get("probability_integration")).get("applied")
    if isinstance(applied, bool):
        result["probability_integration"] = {"applied": applied}
    if "stale" in raw and raw.get("stale") is not False:
        result["stale"] = True
    return result


def project_football_analysis(row: Mapping, *, model_basis: Mapping) -> dict | None:
    """Attach known candidate facts during the ordinary in-process projection."""
    identity = _identity(row)
    if identity is None or _identity(row, clocks=False) != _identity(model_basis, clocks=False):
        return None
    return {
        "schema": _SCHEMA,
        "identity": identity,
        "basis": _basis_projection(model_basis),
        "context": _context_projection(_mapping(row.get("context"))),
    }


def read_football_analysis(row: Mapping) -> dict | None:
    """Validate only this row's envelope; never search/join other candidates."""
    evidence = _mapping(row.get("analysis_evidence"))
    if evidence.get("schema") != _SCHEMA:
        return None
    identity = _identity(row)
    raw_identity = _mapping(evidence.get("identity"))
    # Dict equality alone treats True as integer 1. Validate both sides before
    # comparison so malformed envelope values cannot impersonate native IDs.
    if identity is None or _identity(raw_identity) != identity or raw_identity != identity:
        return None
    context = _context_projection(_mapping(evidence.get("context")))
    if "context_stale" in row and row.get("context_stale") is not False:
        context["stale"] = True
    return {
        "schema": _SCHEMA, "identity": identity,
        "basis": _basis_projection(_mapping(evidence.get("basis"))), "context": context,
    }


def _decimal(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _percent(value: float) -> str:
    return f"{value * 100:.1f} %".replace(".", ",")


def _limit(number: int, unit: str, side: str, suffix: str) -> str:
    noun = "Tor" if unit == "Tore" and number == 1 else unit
    return f"{'mindestens' if side == 'over' else 'höchstens'} {number} {noun} {suffix}"


def _contract(spec, home: str, away: str) -> tuple[str, str]:
    fixed = {
        "RESULT_HOME": ("Heimsieg", "Remis oder Auswärtssieg"),
        "RESULT_AWAY": ("Auswärtssieg", "Heimsieg oder Remis"),
        "RESULT_DRAW": ("Remis", "Heim- oder Auswärtssieg"),
        "DC_1X": ("Heimsieg oder Remis", "Auswärtssieg"),
        "DC_X2": ("Remis oder Auswärtssieg", "Heimsieg"),
        "DC_12": ("Heim- oder Auswärtssieg", "Remis"),
        "BTTS_YES": ("beide Teams treffen", "mindestens ein Team ohne Tor"),
        "BTTS_NO": ("mindestens ein Team ohne Tor", "beide Teams treffen"),
    }
    if spec.key in fixed:
        return fixed[spec.key]
    if spec.kind in {"total", "team_total", *_COUNT_UNITS}:
        direction = spec.side.split("_")[-1]
        is_team = spec.kind in {"team_total", "team_corners", "team_yellow"}
        suffix = f"für {home if spec.side.startswith('home') else away}" if is_team else "insgesamt"
        unit = _COUNT_UNITS.get(spec.kind, "Tore")
        below = math.floor(spec.threshold)
        over = _limit(below + 1, unit, "over", suffix)
        under = _limit(below, unit, "under", suffix)
        return (over, under) if direction == "over" else (under, over)
    if spec.kind == "team_range":
        team = home if spec.side == "home" else away
        return f"{spec.low}–{spec.high} Tore für {team}", f"Tore für {team} außerhalb dieses Bereichs"
    # These are fixed canonical contracts, never raw provider text. Keep
    # conjunction/disjunction intact instead of inventing one-sided reasoning.
    return f"{spec.market}: {spec.selection}", "Auswahl tritt nicht ein"


def _rate_copy(spec, basis: Mapping, home: str, away: str) -> str | None:
    if spec.kind in _GOAL_KINDS:
        left, right = basis.get("expected_home_goals"), basis.get("expected_away_goals")
        unit = "Tore"
    elif basis.get("expected_unit") == _COUNT_UNITS.get(spec.kind):
        left, right = basis.get("expected_market_home"), basis.get("expected_market_away")
        unit = _COUNT_UNITS.get(spec.kind)
    else:
        return None
    if not _number(left) or not _number(right) or unit is None:
        return None
    if spec.kind == "result" and spec.side in {"home", "away"}:
        value, other, team, opponent = (left, right, home, away) if spec.side == "home" else (right, left, away, home)
        if value == other:
            return f"Die Torprognose ist gleich: {_decimal(value)} Tore für beide Teams"
        direction = "höher" if value > other else "niedriger"
        return f"Die Torprognose liegt für {team} {direction}: {_decimal(value)} Tore gegenüber {_decimal(other)} für {opponent}"
    if spec.kind in {"team_total", "team_range", "team_corners", "team_yellow"}:
        value, team = (left, home) if spec.side.startswith("home") else (right, away)
        return f"Das Modell erwartet {_decimal(value)} {unit} für {team}"
    pair = f"{_decimal(left)} für {home}, {_decimal(right)} für {away}"
    if spec.kind in {"total", "corner_total", "yellow_total", "result_total", "mixed_or"}:
        if not _number(left + right):
            return None
        return f"Das Modell erwartet {_decimal(left + right)} {unit} insgesamt ({pair})"
    return f"Das Modell erwartet {_decimal(left)} {unit} für {home} und {_decimal(right)} für {away}"


def _sample_copy(basis: Mapping) -> str:
    venue, form = basis.get("venue_samples"), basis.get("form_samples")
    parts = []
    if venue:
        parts.append(f"{venue[0]} Heimspiele / {venue[1]} Auswärtsspiele")
    if form:
        parts.append(
            f"je {form[0]} letzte Spiele beider Teams"
            if form[0] == form[1]
            else f"letzte Spiele: {form[0]} des Heimteams / {form[1]} des Auswärtsteams"
        )
    return f"Basis: {'; Form: '.join(parts)}" if parts else ""


def _context_caution(context: Mapping, now: datetime) -> str:
    def fresh(axis):
        clock = _clock(axis.get("checked_at"))
        return clock is not None and context.get("stale") is not True and timedelta(0) <= now - clock <= _CONTEXT_MAX_AGE

    injuries = _mapping(context.get("injuries"))
    lineups = _mapping(context.get("lineups"))
    if fresh(injuries):
        clock = _clock(injuries["checked_at"]).astimezone(_ZURICH)
        text = f"Kaderstand {clock.strftime('%d.%m. %H:%M')}: {injuries['home_missing']}/{injuries['away_missing']} Ausfälle gemeldet (Heim/Auswärts)"
        if fresh(lineups) and lineups.get("status") in {"pending", "confirmation_due"}:
            text += ", Aufstellungen noch offen"
            lineup_clock = _clock(lineups["checked_at"]).astimezone(_ZURICH)
            if lineup_clock != clock:
                text += f" (Stand {lineup_clock.strftime('%d.%m. %H:%M')})"
        elif not fresh(lineups):
            text += ", Aufstellungen nicht aktuell belegt"
        if _mapping(context.get("probability_integration")).get("applied") is False:
            text += "; ihre Wirkung ist in dieser Wahrscheinlichkeit nicht eingerechnet"
        elif injuries.get("impact_assessment_complete") is False:
            text += "; ihre Wirkung ist nicht vollständig belegt"
    else:
        text = "Unsicherheit: aktueller Kaderstand nicht belegt"
    return text + "."


def build_forecast_analysis(signal, *, now: datetime | None = None) -> ForecastAnalysis:
    """Compose at most four factual sentences; HTML escaping belongs to UI."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("analysis clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    football = str(signal.sport or "").strip().casefold().replace("ß", "ss") == "fussball"
    spec = MARKET_BY_KEY.get(signal.market_key) if football else None
    home, away = signal.home_team or "Heimteam", signal.away_team or "Auswärtsteam"
    contract, counter = _contract(spec, home, away) if spec else (
        f"{signal.market or 'Auswahl'}: {signal.selection or signal.label}", "Auswahl tritt nicht ein",
    )
    evidence = read_football_analysis(vars(signal)) if football else None
    basis = _mapping(evidence.get("basis")) if evidence else {}
    rates = _rate_copy(spec, basis, home, away) if spec else None
    if rates:
        explanation = f"{rates}; für „{contract}“ setzt das Modell {_percent(signal.probability)} an."
    else:
        explanation = f"Das gespeicherte Modell bewertet {contract} mit {_percent(signal.probability)}; konkrete Modellgrundlagen fehlen in diesem Datenstand."
    caution = f"Gegenrisiko – {counter}: {_percent(1 - signal.probability)}"
    if football and signal.model_scope in ("cross_competition_provisional_forecast", "cross_competition_unvalidated"):
        caution += "; die unterschiedliche Stärke ihrer Ligen ist noch nicht zuverlässig berücksichtigt"
    caution += "."
    if football:
        caution += " " + _context_caution(_mapping(evidence.get("context")) if evidence else {}, current)
    return ForecastAnalysis(explanation, caution, _sample_copy(basis) if rates else "")
