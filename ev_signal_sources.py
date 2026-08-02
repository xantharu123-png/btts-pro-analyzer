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

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from betting_math import BETTING_POLICY_VERSION
from scan_jobs import JOBS_DIR, load_persisted
from tennis.predict import WINNER_PROBABILITY_HAIRCUT
from tennis.shadow import TENNIS_POLICY_VERSION

TENNIS_DB = Path(__file__).resolve().parent / "tennis" / "data" / "tennis_shadow.db"
ESPORTS_DB = Path(__file__).resolve().parent / "esports_shadow.db"
ZURICH_TZ = ZoneInfo("Europe/Zurich")

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

    def __post_init__(self) -> None:
        if not _valid_probability(self.probability):
            raise ValueError("Model signal probability must be between 0 and 1")
        if not _valid_haircut(self.probability_haircut, self.probability):
            raise ValueError("Model signal haircut is invalid")
        if self.evidence_stage not in {"RESEARCH", "SHADOW", "RELEASED"}:
            raise ValueError("Model signal evidence stage is invalid")
        if not str(self.policy_version).strip():
            raise ValueError("Model signal policy version is required")


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
           WHERE settled = 0 AND match_date >= ?
             AND verdict = 'WETTE'
             AND recommended_side IN ('A', 'B')
             AND policy_version = ?
           ORDER BY match_date, id""",
        (today, TENNIS_POLICY_VERSION),
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
            )
        )
    return signals


def esports_signals(
    db_path: Union[str, Path] = ESPORTS_DB,
    *,
    require_released: bool = True,
) -> List[ModelSignal]:
    """Pre-Match-E-Sport-Predictions (Status 'upcoming').

    model_probability liegt in Prozent vor (55.27 = 55,27 %); Bruchwerte
    (0.55) werden der Robustheit halber auch akzeptiert.
    """
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
                  model_probability, risk_adjusted_probability
           FROM esports_shadow_predictions
           WHERE status = 'upcoming' AND settled = 0
           ORDER BY logged_at DESC""",
    )
    signals: List[ModelSignal] = []
    for row in rows:
        probability = _normalized_probability(row["model_probability"])
        risk_probability = _normalized_probability(
            row["risk_adjusted_probability"]
        )
        if probability is None or risk_probability is None:
            continue
        haircut = probability - risk_probability
        if haircut < -1e-9 or not _valid_haircut(max(0.0, haircut), probability):
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
                policy_version=BETTING_POLICY_VERSION,
                detail=(
                    "E-Sport-Pre-Match-Modell · "
                    f"{'Freigegeben' if released else 'Shadow'}"
                ),
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
                )
            )
    return signals


def list_signals(
    tennis_db: Union[str, Path] = TENNIS_DB,
    esports_db: Union[str, Path] = ESPORTS_DB,
    jobs_dir: Union[str, Path] = JOBS_DIR,
    today: Optional[str] = None,
    scope: Optional[str] = None,
    require_esports_release: bool = True,
) -> List[ModelSignal]:
    """Alle verfügbaren Modell-Signale (Fußball, Tennis, E-Sport)."""
    return (
        football_signals(jobs_dir=jobs_dir, scope=scope)
        + tennis_signals(db_path=tennis_db, today=today)
        + esports_signals(
            db_path=esports_db,
            require_released=require_esports_release,
        )
    )
