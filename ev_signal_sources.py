"""Signalquellen für den Wett-Check: persistierte Modell-Wahrscheinlichkeiten.

Liest die bereits gespeicherten Modell-Ausgaben (Tennis-Shadow-DB,
E-Sport-Shadow-DB) und formt sie zu wählbaren Signalen für den
Erwartungswert-Check.  Kein Scan, keine API — nur lokale DB-Lektüre,
fail-safe bei fehlenden oder kaputten Dateien.

Ehrlichkeit: Die Signale kommen aus Shadow-Modellen. Sie liefern die
Wahrscheinlichkeit für eine zusätzliche Preisprüfung. Ein bestandener
Preis-Check ist noch keine Echtgeld-Freigabe; dafür braucht das jeweilige
Modell unabhängige ROI- und CLV-Evidenz.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from betting_math import BETTING_POLICY_VERSION, minimum_recommendation_odds
from market_consensus import (
    MarketConsensus,
    quote_matches_candidate,
    wettfinder_reference_price_status,
)
from scan_jobs import JOBS_DIR, load_persisted
from tennis.predict import WINNER_PROBABILITY_HAIRCUT
from tennis.shadow import TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION

TENNIS_DB = Path(__file__).resolve().parent / "tennis" / "data" / "tennis_shadow.db"
ESPORTS_DB = Path(__file__).resolve().parent / "esports_shadow.db"
AUTOMATED_WETTFINDER_PATH = (
    Path(__file__).resolve().parent
    / "runtime_state"
    / "wettfinder_latest.json"
)
ZURICH_TZ = ZoneInfo("Europe/Zurich")
AUTOMATED_WETTFINDER_VERSION = 16
AUTOMATED_SELECTION_POLICY_VERSION = "useful-selection-catalog-v14"
AUTOMATED_FOOTBALL_RELEASE_CONTRACT = "football-hac-fdr-context-price-v1"
MAX_AUTOMATED_FOOTBALL_CANDIDATES = 15
MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES = (
    MAX_AUTOMATED_FOOTBALL_CANDIDATES
)
MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT = 3
MAX_AUTOMATED_MODEL_CANDIDATES = 21
MAX_AUTOMATED_RECOMMENDATIONS = 3
AUTOMATED_WETTFINDER_MAX_AGE = timedelta(hours=2, minutes=30)
AUTOMATED_VALIDATION_MARKET_HYPOTHESES = 90
AUTOMATED_VALIDATION_FDR_ALPHA = 0.05

# Maximales Signal-Alter je Fußball-Quelle: Prematch-Spiele liegen in der
# Zukunft (24 h tragbar); Live- und Platzverweis-Märkte sind nach Spielende
# wertlos — nach wenigen Stunden ist das Spiel sicher vorbei.
FOOTBALL_SIGNAL_MAX_AGE_HOURS = {
    "prematch": 24.0,
    "red_cards": 6.0,
    "live": 2.0,
}


@dataclass(frozen=True)
class ModelSignal:
    key: str            # stabiler, eindeutiger Schlüssel
    label: str          # Anzeige in der Auswahl
    probability: float  # 0..1
    probability_haircut: float  # absolute Modellunsicherheit, 0..1
    evidence_stage: str
    policy_version: str
    detail: str         # Quelle/Kontext für die Transparenz-Zeile
    scheduled_start: Optional[str] = None
    minimum_odds: Optional[float] = None
    source: str = "persisted_model"
    sport: Optional[str] = None
    event_label: Optional[str] = None
    market: Optional[str] = None
    selection: Optional[str] = None
    market_key: Optional[str] = None
    candidate_id: Optional[str] = None
    fixture_id: Optional[int] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    quote_provider_event_id: Optional[str] = None
    reference_quote: Optional[dict] = None
    context_summary: Optional[str] = None
    context_complete: Optional[bool] = None
    competitor_a: Optional[str] = None
    competitor_b: Optional[str] = None
    selected_competitor: Optional[str] = None
    competition: Optional[str] = None
    statistical_release_passed: Optional[bool] = None

    def __post_init__(self) -> None:
        if not _valid_probability(self.probability):
            raise ValueError("Model signal probability must be between 0 and 1")
        if not _valid_haircut(self.probability_haircut, self.probability):
            raise ValueError("Model signal haircut is invalid")
        if self.evidence_stage not in {"RESEARCH", "SHADOW", "RELEASED"}:
            raise ValueError("Model signal evidence stage is invalid")
        if not str(self.policy_version).strip():
            raise ValueError("Model signal policy version is required")
        if self.scheduled_start is not None:
            scheduled = _parse_iso(self.scheduled_start)
            if scheduled is None or scheduled.tzinfo is None:
                raise ValueError("Model signal scheduled start is invalid")
        if self.minimum_odds is not None and (
            isinstance(self.minimum_odds, bool)
            or not isinstance(self.minimum_odds, (int, float))
            or self.minimum_odds != self.minimum_odds
            or not 1.0 < float(self.minimum_odds) < 1000.0
        ):
            raise ValueError("Model signal minimum odds are invalid")
        if not str(self.source).strip():
            raise ValueError("Model signal source is required")
        if self.fixture_id is not None and (
            isinstance(self.fixture_id, bool)
            or not isinstance(self.fixture_id, int)
            or self.fixture_id <= 0
        ):
            raise ValueError("Model signal fixture identity is invalid")
        if (
            self.reference_quote is not None
            and MarketConsensus.from_dict(self.reference_quote) is None
        ):
            raise ValueError("Model signal reference quote is invalid")
        if self.context_summary is not None and (
            not isinstance(self.context_summary, str)
            or not self.context_summary.strip()
            or len(self.context_summary) > 300
        ):
            raise ValueError("Model signal context summary is invalid")
        if self.context_complete is not None and not isinstance(
            self.context_complete,
            bool,
        ):
            raise ValueError("Model signal context completeness is invalid")
        if (
            self.statistical_release_passed is not None
            and not isinstance(self.statistical_release_passed, bool)
        ):
            raise ValueError("Model signal statistical release state is invalid")
        for value in (
            self.candidate_id,
            self.home_team,
            self.away_team,
            self.quote_provider_event_id,
            self.competitor_a,
            self.competitor_b,
            self.selected_competitor,
            self.competition,
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 200
            ):
                raise ValueError("Model signal competitor identity is invalid")


@dataclass(frozen=True)
class AutomatedWettfinderStatus:
    """Validated scan facts shown next to the automated recommendations."""

    generated_at: datetime
    target_search_date: Optional[str]
    football_search_date: Optional[str]
    last_discovery_at: Optional[datetime]
    football_status: str
    discovery_scope: int
    fixtures_found: int
    fixtures_modeled: int
    base_candidates: int
    base_fixture_count: int
    context_fixtures: int
    context_verified_fixtures: int
    context_data_incomplete_fixtures: int
    context_unchecked_fixtures: int
    deferred_context_fixtures: int
    context_scope_complete: bool
    context_accounting_available: bool
    operational_error_count: int
    approved_candidates: int
    candidate_count: int
    model_candidate_count: int
    bookmaker_data_used: bool
    price_checked_count: int
    reference_quote_count: int
    price_status_counts: tuple[tuple[str, int], ...]
    football_operational_error_count: int = 0


@dataclass(frozen=True)
class AutomatedWettfinderSnapshot:
    """One validated artifact view shared by status, forecasts and releases."""

    status: Optional[AutomatedWettfinderStatus]
    forecasts: tuple[ModelSignal, ...]
    signals: tuple[ModelSignal, ...]


def _valid_probability(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and value == value  # NaN-Wache
        and 0.0 < value < 1.0
    )


def _normalized_probability(value: object) -> Optional[float]:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value != value
    ):
        return None
    normalized = float(value) / 100.0 if value > 1.0 else float(value)
    return normalized if _valid_probability(normalized) else None


def _valid_haircut(value: object, probability: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and value == value
        and 0.0 <= float(value) < 1.0
        and float(value) <= probability
    )


def _minimum_odds(probability: float, haircut: float) -> Optional[float]:
    try:
        return minimum_recommendation_odds(
            probability * 100.0,
            probability_haircut=haircut * 100.0,
        )
    except (TypeError, ValueError):
        return None


def _current_automated_policies() -> set[str]:
    policies = {BETTING_POLICY_VERSION, TENNIS_POLICY_VERSION}
    try:
        from esports_shadow import ESPORTS_MODEL_VERSION

        policies.add(f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}")
    except (ImportError, OSError):
        pass
    return policies


_AUTOMATED_STRICT_SOURCES = frozenset(
    {"football_challenge", "tennis_shadow"}
)


def _supported_automated_strict_source(row: object) -> bool:
    return (
        isinstance(row, dict)
        and str(row.get("source") or "").strip()
        in _AUTOMATED_STRICT_SOURCES
    )


def _read_rows(db_path: Union[str, Path], query: str, params: tuple = ()) -> list:
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def tennis_signals(
    db_path: Union[str, Path] = TENNIS_DB,
    today: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[ModelSignal]:
    """Return open tennis Shadow signals from the current price policy."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    today = today or current.astimezone(ZURICH_TZ).date().isoformat()
    rows = _read_rows(
        db_path,
        """SELECT id, match_date, tour, tournament, player_a, player_b,
                  p_cal, verdict, recommended_side, scheduled_start_utc
           FROM predictions
           WHERE settled = 0 AND match_date = ?
             AND verdict = 'WETTE'
             AND recommended_side IN ('A', 'B')
             AND model_version = ? AND policy_version = ?
           ORDER BY match_date, id""",
        (today, TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION),
    )
    signals: List[ModelSignal] = []
    for row in rows:
        scheduled = _parse_iso(row["scheduled_start_utc"])
        if scheduled is None:
            continue
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if scheduled.astimezone(timezone.utc) <= current:
            continue
        if not _valid_probability(row["p_cal"]):
            continue
        p_a = float(row["p_cal"])
        detail = (
            f"Tennis-Shadow · {row['tour']} · {row['tournament']} · "
            f"{row['match_date']} · Policy {TENNIS_POLICY_VERSION}"
        )
        side = row["recommended_side"]
        player = row["player_a"] if side == "A" else row["player_b"]
        probability = p_a if side == "A" else 1.0 - p_a
        minimum_odds = _minimum_odds(
            probability,
            WINNER_PROBABILITY_HAIRCUT,
        )
        if minimum_odds is None:
            continue
        signals.append(
            ModelSignal(
                key=f"tennis-{row['id']}-{side}",
                label=(
                    f"🎾 {row['player_a']} vs {row['player_b']} · "
                    f"Sieg {player}"
                ),
                probability=probability,
                probability_haircut=WINNER_PROBABILITY_HAIRCUT,
                evidence_stage="SHADOW",
                policy_version=TENNIS_POLICY_VERSION,
                detail=detail,
                scheduled_start=scheduled.astimezone(timezone.utc).isoformat(),
                minimum_odds=minimum_odds,
                source="tennis_shadow",
                sport="Tennis",
                event_label=f"{row['player_a']} vs {row['player_b']}",
                market="Match Winner",
                selection=f"Sieg {player}",
                market_key="H2H",
                competitor_a=str(row["player_a"]),
                competitor_b=str(row["player_b"]),
                selected_competitor=str(player),
                competition=f"{row['tour']} {row['tournament']}",
            )
        )
    return signals


def tennis_model_signals(
    db_path: Union[str, Path] = TENNIS_DB,
    today: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[ModelSignal]:
    """Return one local match day's tennis candidates with all model gates green."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    today = today or current.astimezone(ZURICH_TZ).date().isoformat()
    rows = _read_rows(
        db_path,
        """SELECT id, match_date, tour, tournament, player_a, player_b,
                  p_cal, gates_json, scheduled_start_utc
           FROM predictions
           WHERE settled = 0 AND match_date = ?
             AND model_version = ? AND policy_version = ?
           ORDER BY match_date, scheduled_start_utc, id""",
        (today, TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION),
    )
    signals: List[ModelSignal] = []
    for row in rows:
        scheduled = _parse_iso(row["scheduled_start_utc"])
        if scheduled is None or scheduled.tzinfo is None:
            continue
        scheduled = scheduled.astimezone(timezone.utc)
        if scheduled <= current or not _valid_probability(row["p_cal"]):
            continue
        try:
            gates = json.loads(row["gates_json"])
        except (TypeError, ValueError):
            continue
        if not isinstance(gates, dict) or not gates:
            continue
        model_gates = {
            name: gate
            for name, gate in gates.items()
            if name != "Quote/Risiko-EV"
        }
        if (
            not model_gates
            or any(
                not isinstance(gate, dict) or gate.get("passed") is not True
                for gate in model_gates.values()
            )
        ):
            continue
        p_a = float(row["p_cal"])
        side = "A" if p_a > 0.5 else "B" if p_a < 0.5 else None
        if side is None:
            continue
        player = row["player_a"] if side == "A" else row["player_b"]
        probability = p_a if side == "A" else 1.0 - p_a
        minimum_odds = _minimum_odds(
            probability,
            WINNER_PROBABILITY_HAIRCUT,
        )
        if minimum_odds is None:
            continue
        signals.append(
            ModelSignal(
                key=f"tennis-model-{row['id']}-{side}",
                label=(
                    f"🎾 {row['player_a']} vs {row['player_b']} · "
                    f"Sieg {player}"
                ),
                probability=probability,
                probability_haircut=WINNER_PROBABILITY_HAIRCUT,
                evidence_stage="SHADOW",
                policy_version=TENNIS_POLICY_VERSION,
                detail=(
                    f"Tennis-Modell quotenfrei · {row['tour']} · "
                    f"{row['tournament']} · {row['match_date']}"
                ),
                scheduled_start=scheduled.isoformat(),
                minimum_odds=minimum_odds,
                source="tennis_model",
                sport="Tennis",
                event_label=f"{row['player_a']} vs {row['player_b']}",
                market="Match Winner",
                selection=f"Sieg {player}",
                market_key="H2H",
                competitor_a=str(row["player_a"]),
                competitor_b=str(row["player_b"]),
                selected_competitor=str(player),
                competition=f"{row['tour']} {row['tournament']}",
            )
        )
    return signals


def esports_signals(
    db_path: Union[str, Path] = ESPORTS_DB,
    *,
    require_released: bool = True,
    now: Optional[datetime] = None,
) -> List[ModelSignal]:
    """Pre-Match-E-Sport-Predictions (Status 'upcoming').

    model_probability liegt in Prozent vor (55.27 = 55,27 %); Bruchwerte
    (0.55) werden der Robustheit halber auch akzeptiert.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    try:
        from esports_shadow import ESPORTS_MODEL_VERSION
    except (ImportError, OSError):
        return []

    released = False
    if require_released:
        try:
            from esports_shadow import EsportsShadowLog

            if not EsportsShadowLog(db_path).release_status()["ready"]:
                return []
            released = True
        except (OSError, sqlite3.Error, ValueError):
            return []
    rows = _read_rows(
        db_path,
        """SELECT match_id, game, team1, team2, selection,
                  model_probability, risk_adjusted_probability,
                  scheduled_at, model_version
           FROM esports_shadow_predictions
           WHERE status = 'upcoming' AND settled = 0
           ORDER BY logged_at DESC""",
    )
    signals: List[ModelSignal] = []
    for row in rows:
        scheduled = _parse_iso(row["scheduled_at"])
        if scheduled is None or scheduled.tzinfo is None:
            continue
        scheduled = scheduled.astimezone(timezone.utc)
        if scheduled <= current or row["model_version"] != ESPORTS_MODEL_VERSION:
            continue
        probability = _normalized_probability(row["model_probability"])
        risk_probability = _normalized_probability(
            row["risk_adjusted_probability"]
        )
        if probability is None or risk_probability is None:
            continue
        haircut = probability - risk_probability
        if haircut < -1e-9 or not _valid_haircut(max(0.0, haircut), probability):
            continue
        minimum_odds = _minimum_odds(probability, max(0.0, haircut))
        if minimum_odds is None:
            continue
        signals.append(
            ModelSignal(
                key=f"esports-{row['match_id']}",
                label=(
                    f"🎮 {row['game']} · {row['team1']} vs {row['team2']} · "
                    f"Sieg {row['selection']}"
                ),
                probability=probability,
                probability_haircut=max(0.0, haircut),
                evidence_stage="RELEASED" if released else "SHADOW",
                policy_version=(
                    f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}"
                ),
                detail=(
                    "E-Sport-Pre-Match-Modell · "
                    f"{'Freigegeben' if released else 'Shadow'}"
                ),
                scheduled_start=scheduled.isoformat(),
                minimum_odds=minimum_odds,
                source="esports_shadow",
                sport="E-Sport",
                event_label=f"{row['game']} · {row['team1']} vs {row['team2']}",
                market="Match Winner",
                selection=f"Sieg {row['selection']}",
                market_key="H2H",
                competitor_a=str(row["team1"]),
                competitor_b=str(row["team2"]),
                selected_competitor=str(row["selection"]),
                competition=str(row["game"]),
            )
        )
    return signals


def _parse_iso(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def football_signals(
    jobs_dir: Union[str, Path] = JOBS_DIR,
    now: Optional[datetime] = None,
    max_age_hours: Optional[float] = None,
    scope: Optional[str] = None,
) -> List[ModelSignal]:
    """Letzte Fußball-Scans (BTTS Prematch, Platzverweis, Live) als Signale.

    Liest die von den Hintergrund-Scans persistierten Verdichtungen
    (scan_jobs/<name>.json) — nur frisch genug (Freshness je Quelle, per
    max_age_hours global überschreibbar) und nur mit gültigen
    Wahrscheinlichkeiten.
    """
    now = now or datetime.now().astimezone()
    signals: List[ModelSignal] = []
    for name, source in (
        ("prematch", "Fußball-Scan · BTTS"),
        ("red_cards", "Fußball-Scan · Platzverweis"),
        ("live", "Fußball-Scan · Live"),
    ):
        document = load_persisted(name, jobs_dir=jobs_dir, scope=scope)
        if not document:
            continue
        finished = _parse_iso(document.get("finished_at"))
        if finished is None:
            continue
        max_age = (
            max_age_hours
            if max_age_hours is not None
            else FOOTBALL_SIGNAL_MAX_AGE_HOURS[name]
        )
        age_hours = (now - finished).total_seconds() / 3600.0
        if age_hours < 0 or age_hours > max_age:
            continue
        for row in document.get("signals") or []:
            if not isinstance(row, dict):
                continue
            probability = row.get("p")
            if not _valid_probability(probability):
                continue
            haircut = row.get("haircut")
            if not _valid_haircut(haircut, float(probability)):
                continue
            evidence_stage = str(row.get("evidence_stage") or "").upper()
            if evidence_stage not in {"RESEARCH", "SHADOW", "RELEASED"}:
                continue
            if row.get("policy_version") != BETTING_POLICY_VERSION:
                continue
            home, away, market = row.get("home"), row.get("away"), row.get("market")
            if not home or not away or not market:
                continue
            signals.append(
                ModelSignal(
                    key=f"football-{name}-{len(signals)}",
                    label=f"⚽ {home} vs {away} · {market}",
                    probability=float(probability),
                    probability_haircut=float(haircut),
                    evidence_stage=evidence_stage,
                    policy_version=BETTING_POLICY_VERSION,
                    detail=(
                        f"{source} · {evidence_stage} · Stand "
                        f"{finished.strftime('%d.%m. %H:%M')}"
                    ),
                    minimum_odds=_minimum_odds(
                        float(probability),
                        float(haircut),
                    ),
                    source=f"football_{name}",
                )
            )
    return signals


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return number if number >= 0 else 0


_CONTEXT_FIXTURE_STATUSES = frozenset(
    {"verified", "data_incomplete", "unchecked", "deferred"}
)


def _validated_football_context_statuses(
    football: object,
) -> Optional[dict[str, str]]:
    """Validate the persisted per-fixture accounting before publication."""

    if not isinstance(football, dict) or (
        football.get("context_accounting_available") is not True
    ):
        return None
    raw = football.get("context_fixture_statuses")
    if not isinstance(raw, dict):
        return None
    statuses: dict[str, str] = {}
    for raw_fixture_id, raw_status in raw.items():
        fixture_id = str(raw_fixture_id)
        if (
            not fixture_id.isdigit()
            or int(fixture_id) <= 0
            or raw_status not in _CONTEXT_FIXTURE_STATUSES
        ):
            return None
        statuses[fixture_id] = str(raw_status)
    if len(statuses) != len(raw):
        return None
    expected_counts = {
        "base_fixture_count": len(statuses),
        "context_verified_fixtures": sum(
            status == "verified" for status in statuses.values()
        ),
        "context_data_incomplete_fixtures": sum(
            status == "data_incomplete" for status in statuses.values()
        ),
        "context_unchecked_fixtures": sum(
            status == "unchecked" for status in statuses.values()
        ),
        "deferred_context_fixtures": sum(
            status == "deferred" for status in statuses.values()
        ),
    }
    if any(
        _non_negative_int(football.get(field)) != expected
        for field, expected in expected_counts.items()
    ):
        return None
    if _non_negative_int(football.get("context_fixtures")) != (
        expected_counts["context_verified_fixtures"]
        + expected_counts["context_data_incomplete_fixtures"]
    ):
        return None
    expected_complete = all(
        status == "verified" for status in statuses.values()
    )
    if football.get("context_scope_complete") is not expected_complete:
        return None
    return statuses


_AUTOMATED_PRICE_STATUS_CODES = frozenset(
    {
        "PLAYABLE",
        "BORDERLINE",
        "TOO_LOW",
        "UNAVAILABLE",
        "THIN",
        "STALE",
        "INVALID_MINIMUM",
    }
)

_REFERENCE_EXECUTION_FIELDS = (
    "reference_quote_source",
    "reference_quote_executable_odds",
    "reference_quote_bookmaker",
    "reference_quote_bookmaker_id",
    "reference_quote_observed_at",
)


def _reference_execution_matches_row(
    row: dict,
    quote: MarketConsensus,
    status,
) -> bool:
    """Bind persisted execution provenance to the real usable offer."""

    if status.code != "PLAYABLE":
        return not any(field in row for field in _REFERENCE_EXECUTION_FIELDS)
    odds = row.get("reference_quote_executable_odds")
    if (
        status.usable_odds is None
        or isinstance(odds, bool)
        or not isinstance(odds, (int, float))
        or not math.isfinite(float(odds))
        or not math.isclose(
            float(odds),
            status.usable_odds,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        or row.get("reference_quote_source") != quote.source
        or row.get("reference_quote_bookmaker") != status.bookmaker
        or row.get("reference_quote_bookmaker_id") != status.bookmaker_id
    ):
        return False
    recorded_at = _parse_iso(row.get("reference_quote_observed_at"))
    expected_at = _parse_iso(status.observed_at)
    return (
        recorded_at is not None
        and expected_at is not None
        and recorded_at.astimezone(timezone.utc)
        == expected_at.astimezone(timezone.utc)
    )


def _price_status_counts(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, dict):
        return ()
    normalized = []
    for raw_code, raw_count in value.items():
        code = str(raw_code or "").strip().upper()
        count = _non_negative_int(raw_count)
        if code in _AUTOMATED_PRICE_STATUS_CODES and count > 0:
            normalized.append((code, count))
    return tuple(sorted(normalized))


def _load_automated_wettfinder_document(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
) -> Optional[tuple[dict, datetime, list]]:
    """Load one fresh, policy-compatible systemd artifact."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if (
        not isinstance(document, dict)
        or document.get("version") != AUTOMATED_WETTFINDER_VERSION
        or document.get("betting_policy_version") != BETTING_POLICY_VERSION
        or document.get("selection_policy_version")
        != AUTOMATED_SELECTION_POLICY_VERSION
        or not isinstance(document.get("bookmaker_data_used"), bool)
        or document.get("quote_required") is not True
        or document.get("run_status") not in {"completed", "degraded"}
        or isinstance(document.get("operational_error_count"), bool)
        or not isinstance(document.get("operational_error_count"), int)
        or document.get("operational_error_count") < 0
        or (
            document.get("run_status") == "completed"
            and document.get("operational_error_count") != 0
        )
        or (
            document.get("run_status") == "degraded"
            and document.get("operational_error_count") < 1
        )
    ):
        return None
    generated = _parse_iso(document.get("generated_at"))
    if generated is None or generated.tzinfo is None:
        return None
    generated = generated.astimezone(timezone.utc)
    age = current - generated
    if age.total_seconds() < 0 or age > max_age:
        return None
    candidates = document.get("candidates")
    if (
        not isinstance(candidates, list)
        or len(candidates) > MAX_AUTOMATED_RECOMMENDATIONS
    ):
        return None
    sources = document.get("sources")
    if not isinstance(sources, dict):
        return None
    challenge_release_candidates = document.get(
        "challenge_release_candidates"
    )
    if (
        not isinstance(challenge_release_candidates, list)
        or len(challenge_release_candidates)
        > MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES
    ):
        return None
    source_for_row = {
        "football_challenge": "football",
        "tennis_shadow": "tennis",
        "esports_shadow": "esports",
    }
    for row in candidates:
        if not isinstance(row, dict):
            return None
        source_name = source_for_row.get(str(row.get("source") or ""))
        source_status = sources.get(source_name) if source_name else None
        operational_errors = (
            source_status.get("operational_error_count")
            if isinstance(source_status, dict)
            else None
        )
        if (
            source_name is None
            or isinstance(operational_errors, bool)
            or not isinstance(operational_errors, int)
            or operational_errors != 0
        ):
            return None
    football_source = sources.get("football")
    football_operational_errors = (
        football_source.get("operational_error_count")
        if isinstance(football_source, dict)
        else None
    )
    if challenge_release_candidates and (
        isinstance(football_operational_errors, bool)
        or not isinstance(football_operational_errors, int)
        or football_operational_errors != 0
    ):
        return None
    model_candidates = document.get("model_candidates")
    if (
        not isinstance(model_candidates, list)
        or len(model_candidates) > MAX_AUTOMATED_MODEL_CANDIDATES
    ):
        return None
    sport_counts: dict[str, int] = {}
    for row in model_candidates:
        if not isinstance(row, dict):
            return None
        sport = str(row.get("sport") or "").strip()
        if not sport:
            return None
        normalized = sport.casefold().replace("ß", "ss")
        sport_counts[normalized] = sport_counts.get(normalized, 0) + 1
    if sport_counts.get("fussball", 0) > MAX_AUTOMATED_FOOTBALL_CANDIDATES:
        return None
    if any(
        count > MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT
        for sport, count in sport_counts.items()
        if sport != "fussball"
    ):
        return None
    model_keys = [
        str(row.get("key") or "").strip()
        for row in model_candidates
        if isinstance(row, dict)
    ]
    strict_keys = [
        str(row.get("key") or "").strip()
        for row in candidates
        if isinstance(row, dict)
    ]
    challenge_release_keys = [
        str(row.get("key") or "").strip()
        for row in challenge_release_candidates
        if isinstance(row, dict)
    ]
    if (
        len(model_keys) != len(model_candidates)
        or len(strict_keys) != len(candidates)
        or any(not key for key in [*model_keys, *strict_keys])
        or len(set(model_keys)) != len(model_keys)
        or len(set(strict_keys)) != len(strict_keys)
        or len(challenge_release_keys) != len(challenge_release_candidates)
        or any(not key for key in challenge_release_keys)
        or len(set(challenge_release_keys)) != len(challenge_release_keys)
        or any(key not in model_keys for key in strict_keys)
        or any(key not in model_keys for key in challenge_release_keys)
        or [key for key in model_keys if key in set(strict_keys)] != strict_keys
        or [
            key for key in model_keys if key in set(challenge_release_keys)
        ]
        != challenge_release_keys
    ):
        return None
    model_by_key = {
        str(row.get("key") or "").strip(): row
        for row in model_candidates
    }
    for strict_row in candidates:
        model_row = model_by_key[str(strict_row.get("key") or "").strip()]
        overlay_fields = {"status", "evidence_stage", "release_contract"}
        strict_decision = {
            key: value
            for key, value in strict_row.items()
            if key not in overlay_fields
        }
        model_decision = {
            key: value
            for key, value in model_row.items()
            if key not in overlay_fields
        }
        if strict_decision != model_decision:
            return None
        if strict_row.get("source") == "football_challenge":
            if (
                strict_row.get("evidence_stage") != "RELEASED"
                or strict_row.get("release_contract")
                != AUTOMATED_FOOTBALL_RELEASE_CONTRACT
                or model_row.get("evidence_stage") != "SHADOW"
                or "release_contract" in model_row
            ):
                return None
        elif (
            strict_row.get("evidence_stage") != model_row.get("evidence_stage")
            or strict_row.get("release_contract")
            != model_row.get("release_contract")
        ):
            return None
    for strict_row in challenge_release_candidates:
        if strict_row.get("source") != "football_challenge":
            return None
        model_row = model_by_key[
            str(strict_row.get("key") or "").strip()
        ]
        overlay_fields = {"status", "evidence_stage", "release_contract"}
        strict_decision = {
            key: value
            for key, value in strict_row.items()
            if key not in overlay_fields
        }
        model_decision = {
            key: value
            for key, value in model_row.items()
            if key not in overlay_fields
        }
        if (
            strict_decision != model_decision
            or strict_row.get("status") != "RECOMMENDED"
            or strict_row.get("evidence_stage") != "RELEASED"
            or strict_row.get("release_contract")
            != AUTOMATED_FOOTBALL_RELEASE_CONTRACT
            or model_row.get("evidence_stage") != "SHADOW"
            or "release_contract" in model_row
            or not _football_recommendation_release_eligible(strict_row)
        ):
            return None
    try:
        target = date.fromisoformat(str(document.get("target_search_date")))
    except (TypeError, ValueError):
        return None
    local = current.astimezone(ZURICH_TZ)
    expected_target = local.date()
    if target != expected_target:
        return None
    # Price evidence may reject every model candidate. A published candidate
    # still requires bookmaker data, but zero candidates does not imply that
    # no bookmaker price was observed.
    if (
        candidates or challenge_release_candidates
    ) and document["bookmaker_data_used"] is not True:
        return None
    for row in [*candidates, *challenge_release_candidates]:
        if (
            not isinstance(row, dict)
            or row.get("status") != "RECOMMENDED"
            or row.get("reference_price_status") != "PLAYABLE"
            or not _supported_automated_strict_source(row)
        ):
            return None
        quote = MarketConsensus.from_dict(row.get("reference_quote"))
        status = wettfinder_reference_price_status(
            quote,
            row.get("minimum_odds"),
            candidate=row,
            now=generated,
        )
        if (
            not quote_matches_candidate(quote, row)
            or status.code != "PLAYABLE"
            or not _reference_execution_matches_row(row, quote, status)
        ):
            return None
    for row in model_candidates:
        if (
            not isinstance(row, dict)
            or row.get("status") != "MODEL_SELECTION"
            or any(
                field in row
                for field in ("offered_odds", "bookmaker_odds", "n1bet_odds")
            )
        ):
            return None
        probability = row.get("probability")
        haircut = row.get("probability_haircut")
        if not _valid_probability(probability) or not _valid_haircut(
            haircut,
            float(probability),
        ):
            return None
        expected_minimum = _minimum_odds(float(probability), float(haircut))
        supplied_minimum = row.get("minimum_odds")
        if (
            expected_minimum is None
            or isinstance(supplied_minimum, bool)
            or not isinstance(supplied_minimum, (int, float))
            or abs(float(supplied_minimum) - expected_minimum) > 0.011
        ):
            return None
        scheduled = _parse_iso(row.get("scheduled_start"))
        if (
            scheduled is None
            or scheduled.astimezone(timezone.utc) <= current
            or scheduled.astimezone(ZURICH_TZ).date() != target
        ):
            return None
        quote_payload = row.get("reference_quote")
        if quote_payload is not None:
            quote = MarketConsensus.from_dict(quote_payload)
            if not quote_matches_candidate(quote, row):
                return None
            status = wettfinder_reference_price_status(
                quote,
                supplied_minimum,
                candidate=row,
                now=generated,
            )
            if (
                row.get("reference_price_status") != status.code
                or not _reference_execution_matches_row(row, quote, status)
            ):
                return None
        elif (
            row.get("reference_price_status") != "UNAVAILABLE"
            or any(field in row for field in _REFERENCE_EXECUTION_FIELDS)
        ):
            return None
    return document, generated, candidates


def automated_wettfinder_status(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
    _loaded: Optional[tuple[dict, datetime, list]] = None,
) -> Optional[AutomatedWettfinderStatus]:
    """Return validated scan facts even when no market passed every gate."""
    loaded = (
        _loaded
        if _loaded is not None
        else _load_automated_wettfinder_document(
            path,
            now=now,
            max_age=max_age,
        )
    )
    if loaded is None:
        return None
    document, generated, candidates = loaded
    football = document.get("football")
    if not isinstance(football, dict):
        football = {}
    sources = document.get("sources")
    football_source = sources.get("football") if isinstance(sources, dict) else {}
    if not isinstance(football_source, dict):
        football_source = {}
    last_discovery = _parse_iso(football.get("last_discovery_at"))
    if last_discovery is not None:
        if last_discovery.tzinfo is None:
            last_discovery = None
        else:
            last_discovery = last_discovery.astimezone(timezone.utc)
    base_candidates = _non_negative_int(football.get("base_candidates"))
    context_scope_value = football.get("context_scope_complete")
    context_statuses = _validated_football_context_statuses(football)
    context_accounting_available = context_statuses is not None
    context_scope_complete = (
        context_scope_value is True
        if isinstance(context_scope_value, bool)
        else base_candidates == 0
    )
    return AutomatedWettfinderStatus(
        generated_at=generated,
        target_search_date=(
            str(document.get("target_search_date"))
            if document.get("target_search_date")
            else None
        ),
        football_search_date=(
            str(football.get("search_date"))
            if football.get("search_date")
            else None
        ),
        last_discovery_at=last_discovery,
        football_status=str(football.get("status") or "unknown"),
        discovery_scope=_non_negative_int(
            football_source.get("discovery_scope")
        ),
        fixtures_found=_non_negative_int(football.get("fixtures_found")),
        fixtures_modeled=_non_negative_int(football.get("fixtures_modeled")),
        base_candidates=base_candidates,
        base_fixture_count=_non_negative_int(football.get("base_fixture_count")),
        context_fixtures=_non_negative_int(football.get("context_fixtures")),
        context_verified_fixtures=_non_negative_int(
            football.get("context_verified_fixtures")
        ),
        context_data_incomplete_fixtures=_non_negative_int(
            football.get("context_data_incomplete_fixtures")
        ),
        context_unchecked_fixtures=_non_negative_int(
            football.get("context_unchecked_fixtures")
        ),
        deferred_context_fixtures=_non_negative_int(
            football.get("deferred_context_fixtures")
        ),
        context_scope_complete=context_scope_complete,
        context_accounting_available=context_accounting_available,
        operational_error_count=_non_negative_int(
            document.get("operational_error_count")
        ),
        approved_candidates=_non_negative_int(
            football.get("approved_candidates")
        ),
        candidate_count=len(candidates),
        model_candidate_count=len(document.get("model_candidates") or []),
        bookmaker_data_used=document["bookmaker_data_used"],
        price_checked_count=_non_negative_int(
            football_source.get("price_checked_count")
        ),
        reference_quote_count=_non_negative_int(
            football_source.get("reference_quote_count")
        ),
        price_status_counts=_price_status_counts(
            football_source.get("price_status_counts")
        ),
        football_operational_error_count=_non_negative_int(
            football_source.get("operational_error_count")
        ),
    )


def _model_row_context_complete(row: dict) -> Optional[bool]:
    direct = row.get("context_complete")
    if isinstance(direct, bool):
        return direct
    context = row.get("context")
    if not isinstance(context, dict):
        return None
    value = context.get("release_context_complete")
    return value if isinstance(value, bool) else None


def _football_recommendation_release_eligible(row: dict) -> bool:
    context = row.get("context")
    evidence_values = tuple(
        row.get(field)
        for field in (
            "paired_loss_mean",
            "paired_loss_hac_standard_error",
            "paired_loss_lower_confidence_bound",
            "paired_loss_p_value",
            "fdr_q_value",
        )
    )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in evidence_values
    ):
        return False
    mean_advantage, standard_error, lower_bound, p_value, q_value = (
        float(value) for value in evidence_values
    )
    return (
        isinstance(context, dict)
        and context.get("release_context_complete") is True
        and context.get("release_eligible") is True
        and row.get("model_scope") == "same_competition"
        and row.get("context_stale") is False
        and row.get("statistical_release_passed") is True
        and (
            str(row.get("evidence_stage") or "").upper() != "RELEASED"
            or row.get("release_contract")
            == AUTOMATED_FOOTBALL_RELEASE_CONTRACT
        )
        and row.get("tested_hypotheses")
        == AUTOMATED_VALIDATION_MARKET_HYPOTHESES
        and -1.0 <= mean_advantage <= 1.0
        and 0.0 <= standard_error <= 1.0
        and 0.0 < lower_bound <= mean_advantage + 1e-9
        and 0.0 <= p_value <= q_value + 1e-9
        and q_value <= AUTOMATED_VALIDATION_FDR_ALPHA
    )


def automated_wettfinder_forecasts(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
    _loaded: Optional[tuple[dict, datetime, list]] = None,
) -> List[ModelSignal]:
    """Read the calculated model catalog independently of bookmaker price.

    These rows are deliberately separate from ``automated_wettfinder_signals``:
    a missing or too-low bookmaker quote must never erase a model forecast.
    Football rows require a verified, candidate-specific context record even
    when another league in the broad scan was incomplete. The evidence stage
    remains authoritative, so a Shadow/Research selection cannot become an
    Echtgeld tip through this API.
    """

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    loaded = (
        _loaded
        if _loaded is not None
        else _load_automated_wettfinder_document(
            path,
            now=current,
            max_age=max_age,
        )
    )
    if loaded is None:
        return []
    document, _generated, _priced_candidates = loaded
    rows = document.get("model_candidates")
    if not isinstance(rows, list):
        return []
    football = document.get("football")
    football = football if isinstance(football, dict) else {}
    football_statuses = _validated_football_context_statuses(football)
    football_context_available = football_statuses is not None
    policies = _current_automated_policies()
    forecasts: List[ModelSignal] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_sport = (
            str(row.get("sport") or "").strip().casefold().replace("ß", "ss")
        )
        is_football = (
            row.get("source") == "football_challenge"
            or normalized_sport == "fussball"
        )
        fixture_id = row.get("fixture_id")
        if is_football and (
            not football_context_available
            or isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or football_statuses.get(str(fixture_id)) != "verified"
        ):
            continue
        probability = row.get("probability")
        haircut = row.get("probability_haircut")
        minimum_odds = row.get("minimum_odds")
        if (
            not _valid_probability(probability)
            or not _valid_haircut(haircut, float(probability))
            or isinstance(minimum_odds, bool)
            or not isinstance(minimum_odds, (int, float))
        ):
            continue
        stage = str(row.get("evidence_stage") or "").upper()
        policy = str(row.get("policy_version") or "").strip()
        key = str(row.get("key") or "").strip()
        label = str(row.get("label") or "").strip()
        detail = str(row.get("detail") or "").strip()
        scheduled = _parse_iso(row.get("scheduled_start"))
        if (
            stage not in {"RESEARCH", "SHADOW", "RELEASED"}
            or policy not in policies
            or not all((key, label, detail))
            or scheduled is None
        ):
            continue
        quote = MarketConsensus.from_dict(row.get("reference_quote"))
        if not quote_matches_candidate(quote, row):
            quote = None
        try:
            forecasts.append(
                ModelSignal(
                    key=key,
                    label=label,
                    probability=float(probability),
                    probability_haircut=float(haircut),
                    evidence_stage=stage,
                    policy_version=policy,
                    detail=detail,
                    scheduled_start=scheduled.astimezone(timezone.utc).isoformat(),
                    minimum_odds=float(minimum_odds),
                    source="automated_wettfinder_forecast",
                    sport=str(row.get("sport") or "").strip() or None,
                    event_label=str(row.get("event") or "").strip() or label,
                    market=str(row.get("market") or "").strip() or "Auswahl",
                    selection=str(row.get("selection") or "").strip() or label,
                    market_key=str(row.get("market_key") or "").strip() or None,
                    candidate_id=(
                        str(row.get("candidate_id") or "").strip() or key
                    ),
                    fixture_id=(
                        fixture_id
                        if isinstance(fixture_id, int)
                        and not isinstance(fixture_id, bool)
                        and fixture_id > 0
                        else None
                    ),
                    home_team=(
                        str(row.get("home_team") or "").strip() or None
                    ),
                    away_team=(
                        str(row.get("away_team") or "").strip() or None
                    ),
                    quote_provider_event_id=(
                        str(row.get("quote_provider_event_id") or "").strip()
                        or None
                    ),
                    competitor_a=(
                        str(row.get("competitor_a") or "").strip() or None
                    ),
                    competitor_b=(
                        str(row.get("competitor_b") or "").strip() or None
                    ),
                    selected_competitor=(
                        str(row.get("selected_competitor") or "").strip()
                        or None
                    ),
                    competition=(
                        str(row.get("competition") or "").strip() or None
                    ),
                    reference_quote=quote.to_dict() if quote is not None else None,
                    context_summary=(
                        str(row.get("context_summary")).strip()
                        if isinstance(row.get("context_summary"), str)
                        and str(row.get("context_summary")).strip()
                        else None
                    ),
                    context_complete=_model_row_context_complete(row),
                    statistical_release_passed=(
                        row.get("statistical_release_passed")
                        if isinstance(
                            row.get("statistical_release_passed"),
                            bool,
                        )
                        else None
                    ),
                )
            )
        except ValueError:
            continue
    return forecasts


def automated_wettfinder_signals(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
    _loaded: Optional[tuple[dict, datetime, list]] = None,
) -> List[ModelSignal]:
    """Read the strict maximum-three artifact produced by systemd."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    loaded = (
        _loaded
        if _loaded is not None
        else _load_automated_wettfinder_document(
            path,
            now=current,
            max_age=max_age,
        )
    )
    if loaded is None:
        return []
    document, _generated, candidates = loaded
    target_date = date.fromisoformat(str(document["target_search_date"]))
    football_state = document.get("football")
    football_state = football_state if isinstance(football_state, dict) else {}
    football_context_statuses = _validated_football_context_statuses(
        football_state
    )
    football_publishable = (
        football_state.get("status") == "completed"
        and _non_negative_int(football_state.get("operational_error_count")) == 0
        and football_context_statuses is not None
    )

    signals: List[ModelSignal] = []
    current_policies = _current_automated_policies()
    for row in candidates:
        row_sport = str(row.get("sport") or "").strip().casefold().replace("ß", "ss")
        row_is_football = (
            row.get("source") == "football_challenge" or row_sport == "fussball"
        )
        row_is_esports = (
            row.get("source") == "esports_shadow"
            or row_sport.replace("-", "").replace(" ", "")
            in {"esport", "esports"}
        )
        row_fixture_id = row.get("fixture_id")
        football_fixture_verified = (
            isinstance(row_fixture_id, int)
            and not isinstance(row_fixture_id, bool)
            and football_context_statuses is not None
            and football_context_statuses.get(str(row_fixture_id)) == "verified"
        )
        if (
            not isinstance(row, dict)
            or row.get("status") != "RECOMMENDED"
            or not _supported_automated_strict_source(row)
            # The generator deliberately has no verified E-sport price
            # provider. Keep those model forecasts visible, but fail closed
            # if an inconsistent or manipulated artifact invents a strict row.
            or row_is_esports
            or (
                row_is_football
                and (
                    not football_publishable
                    or not football_fixture_verified
                    or not _football_recommendation_release_eligible(row)
                )
            )
            or any(
                field in row
                for field in ("offered_odds", "bookmaker_odds", "n1bet_odds")
            )
        ):
            continue
        probability = row.get("probability")
        haircut = row.get("probability_haircut")
        if not _valid_probability(probability):
            continue
        if not _valid_haircut(haircut, float(probability)):
            continue
        expected_minimum = _minimum_odds(float(probability), float(haircut))
        supplied_minimum = row.get("minimum_odds")
        if (
            expected_minimum is None
            or isinstance(supplied_minimum, bool)
            or not isinstance(supplied_minimum, (int, float))
            or abs(float(supplied_minimum) - expected_minimum) > 0.011
        ):
            continue
        scheduled_value = row.get("scheduled_start")
        scheduled = _parse_iso(scheduled_value)
        if (
            scheduled_value is None
            or scheduled is None
            or scheduled.tzinfo is None
            or scheduled.astimezone(timezone.utc) <= current
            or scheduled.astimezone(ZURICH_TZ).date() != target_date
        ):
            continue
        key = str(row.get("key") or "").strip()
        label = str(row.get("label") or "").strip()
        detail = str(row.get("detail") or "").strip()
        sport = str(row.get("sport") or "").strip() or None
        event_label = str(row.get("event") or "").strip() or label
        market = str(row.get("market") or "").strip() or "Auswahl"
        selection = str(row.get("selection") or "").strip() or label
        reference_quote = MarketConsensus.from_dict(row.get("reference_quote"))
        if not quote_matches_candidate(reference_quote, row):
            continue
        status = wettfinder_reference_price_status(
            reference_quote,
            float(supplied_minimum),
            candidate=row,
            now=current,
        )
        if (
            status.code != "PLAYABLE"
            or not _reference_execution_matches_row(
                row,
                reference_quote,
                status,
            )
        ):
            continue
        stage = str(row.get("evidence_stage") or "").upper()
        policy = str(row.get("policy_version") or "").strip()
        if (
            not all((key, label, detail, policy))
            or policy not in current_policies
        ):
            continue
        try:
            signals.append(
                ModelSignal(
                    key=key,
                    label=label,
                    probability=float(probability),
                    probability_haircut=float(haircut),
                    evidence_stage=stage,
                    policy_version=policy,
                    detail=detail,
                    scheduled_start=(
                        scheduled.astimezone(timezone.utc).isoformat()
                        if scheduled is not None
                        else None
                    ),
                    minimum_odds=float(supplied_minimum),
                    source="automated_wettfinder",
                    sport=sport,
                    event_label=event_label,
                    market=market,
                    selection=selection,
                    market_key=str(row.get("market_key") or "").strip() or None,
                    candidate_id=(
                        str(row.get("candidate_id") or "").strip() or key
                    ),
                    fixture_id=(
                        row_fixture_id
                        if isinstance(row_fixture_id, int)
                        and not isinstance(row_fixture_id, bool)
                        and row_fixture_id > 0
                        else None
                    ),
                    home_team=(
                        str(row.get("home_team") or "").strip() or None
                    ),
                    away_team=(
                        str(row.get("away_team") or "").strip() or None
                    ),
                    quote_provider_event_id=(
                        str(row.get("quote_provider_event_id") or "").strip()
                        or None
                    ),
                    competitor_a=(
                        str(row.get("competitor_a") or "").strip() or None
                    ),
                    competitor_b=(
                        str(row.get("competitor_b") or "").strip() or None
                    ),
                    selected_competitor=(
                        str(row.get("selected_competitor") or "").strip()
                        or None
                    ),
                    competition=(
                        str(row.get("competition") or "").strip() or None
                    ),
                    reference_quote=reference_quote.to_dict(),
                    context_summary=(
                        str(row.get("context_summary")).strip()
                        if isinstance(row.get("context_summary"), str)
                        and str(row.get("context_summary")).strip()
                        else None
                    ),
                    context_complete=_model_row_context_complete(row),
                    statistical_release_passed=(
                        True if row_is_football else None
                    ),
                )
            )
        except ValueError:
            continue
    return signals


def automated_wettfinder_snapshot(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
) -> AutomatedWettfinderSnapshot:
    """Load and derive every automatic surface collection from one document."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    loaded = _load_automated_wettfinder_document(
        path,
        now=current,
        max_age=max_age,
    )
    if loaded is None:
        return AutomatedWettfinderSnapshot(None, (), ())
    return AutomatedWettfinderSnapshot(
        status=automated_wettfinder_status(
            path,
            now=current,
            max_age=max_age,
            _loaded=loaded,
        ),
        forecasts=tuple(
            automated_wettfinder_forecasts(
                path,
                now=current,
                max_age=max_age,
                _loaded=loaded,
            )
        ),
        signals=tuple(
            automated_wettfinder_signals(
                path,
                now=current,
                max_age=max_age,
                _loaded=loaded,
            )
        ),
    )


def list_signals(
    tennis_db: Union[str, Path] = TENNIS_DB,
    esports_db: Union[str, Path] = ESPORTS_DB,
    jobs_dir: Union[str, Path] = JOBS_DIR,
    today: Optional[str] = None,
    scope: Optional[str] = None,
    require_esports_release: bool = True,
    automated_path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    now: Optional[datetime] = None,
) -> List[ModelSignal]:
    """Alle verfügbaren Modell-Signale (Fußball, Tennis, E-Sport)."""
    automatic = automated_wettfinder_signals(
        path=automated_path,
        now=now,
    )
    interactive_football = football_signals(
        jobs_dir=jobs_dir,
        scope=scope,
        now=now,
    )
    if automatic:
        candidates = automatic + interactive_football
    else:
        candidates = (
            interactive_football
            + tennis_signals(db_path=tennis_db, today=today, now=now)
            + esports_signals(
                db_path=esports_db,
                require_released=require_esports_release,
                now=now,
            )
        )
    unique: List[ModelSignal] = []
    seen: set[str] = set()
    for signal in candidates:
        if signal.key in seen:
            continue
        seen.add(signal.key)
        unique.append(signal)
    return unique
