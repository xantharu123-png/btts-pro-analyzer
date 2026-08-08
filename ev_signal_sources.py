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
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from betting_math import BETTING_POLICY_VERSION, minimum_acceptable_odds
from market_consensus import MarketConsensus, reference_price_status
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
AUTOMATED_WETTFINDER_VERSION = 5
AUTOMATED_SELECTION_POLICY_VERSION = "price-gated-daily-recommendations-v5"
AUTOMATED_WETTFINDER_MAX_AGE = timedelta(hours=2, minutes=30)
AUTOMATED_TOMORROW_SCAN_HOUR = 23

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
    reference_quote: Optional[dict] = None

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
        if (
            self.reference_quote is not None
            and MarketConsensus.from_dict(self.reference_quote) is None
        ):
            raise ValueError("Model signal reference quote is invalid")


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
    approved_candidates: int
    candidate_count: int


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
        return minimum_acceptable_odds(
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
    if not isinstance(candidates, list) or len(candidates) > 3:
        return None
    try:
        target = date.fromisoformat(str(document.get("target_search_date")))
    except (TypeError, ValueError):
        return None
    local = current.astimezone(ZURICH_TZ)
    expected_target = local.date() + timedelta(
        days=local.hour >= AUTOMATED_TOMORROW_SCAN_HOUR
    )
    if target != expected_target:
        return None
    if document["bookmaker_data_used"] is not bool(candidates):
        return None
    for row in candidates:
        if (
            not isinstance(row, dict)
            or row.get("status") != "RECOMMENDED"
            or row.get("reference_price_status") != "PLAYABLE"
        ):
            return None
        quote = MarketConsensus.from_dict(row.get("reference_quote"))
        candidate_id = str(row.get("candidate_id") or "").strip()
        if (
            quote is None
            or not candidate_id
            or quote.candidate_id != candidate_id
            or reference_price_status(
                quote,
                row.get("minimum_odds"),
                now=current,
            ).code
            != "PLAYABLE"
        ):
            return None
    return document, generated, candidates


def automated_wettfinder_status(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
) -> Optional[AutomatedWettfinderStatus]:
    """Return validated scan facts even when no market passed every gate."""
    loaded = _load_automated_wettfinder_document(
        path,
        now=now,
        max_age=max_age,
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
        approved_candidates=_non_negative_int(
            football.get("approved_candidates")
        ),
        candidate_count=len(candidates),
    )


def automated_wettfinder_signals(
    path: Union[str, Path] = AUTOMATED_WETTFINDER_PATH,
    *,
    now: Optional[datetime] = None,
    max_age: timedelta = AUTOMATED_WETTFINDER_MAX_AGE,
) -> List[ModelSignal]:
    """Read the strict maximum-three artifact produced by systemd."""
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
        return []
    document, _generated, candidates = loaded
    target_date = date.fromisoformat(str(document["target_search_date"]))

    signals: List[ModelSignal] = []
    current_policies = _current_automated_policies()
    for row in candidates:
        if (
            not isinstance(row, dict)
            or row.get("status") != "RECOMMENDED"
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
        if reference_quote is None:
            continue
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not candidate_id or reference_quote.candidate_id != candidate_id:
            continue
        if reference_price_status(
            reference_quote,
            float(supplied_minimum),
            now=current,
        ).code != "PLAYABLE":
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
                    reference_quote=reference_quote.to_dict(),
                )
            )
        except ValueError:
            continue
    return signals


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
