"""Signalquellen für den Wett-Check: persistierte Modell-Wahrscheinlichkeiten.

Liest die bereits gespeicherten Modell-Ausgaben (Tennis-Shadow-DB,
E-Sport-Shadow-DB) und formt sie zu wählbaren Signalen für den
Erwartungswert-Check.  Kein Scan, keine API — nur lokale DB-Lektüre,
fail-safe bei fehlenden oder kaputten Dateien.

Ehrlichkeit: Die Signale kommen aus Shadow-Modellen.  Sie liefern die
Wahrscheinlichkeit; ob gewettet wird, entscheidet allein der Preis-Check
(Quote vs. Wahrscheinlichkeit).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Union

from scan_jobs import JOBS_DIR, load_persisted

TENNIS_DB = Path(__file__).resolve().parent / "tennis" / "data" / "tennis_shadow.db"
ESPORTS_DB = Path(__file__).resolve().parent / "esports_shadow.db"

# Fußball-Scans älter als 24h nicht mehr anbieten (Live-Bezug veraltet,
# Prematch-Spiele könnten bereits gelaufen sein).
FOOTBALL_SIGNAL_MAX_AGE_HOURS = 24


@dataclass(frozen=True)
class ModelSignal:
    key: str            # stabiler, eindeutiger Schlüssel
    label: str          # Anzeige in der Auswahl
    probability: float  # 0..1
    detail: str         # Quelle/Kontext für die Transparenz-Zeile


def _valid_probability(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and value == value  # NaN-Wache
        and 0.0 < value < 1.0
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
) -> List[ModelSignal]:
    """Offene Tennis-Predictions ab heute — beide Spielerseiten als Signale.

    p_cal ist die kalibrierte Sieg-Wahrscheinlichkeit von player_a.
    """
    today = today or date.today().isoformat()
    rows = _read_rows(
        db_path,
        """SELECT id, match_date, tour, tournament, player_a, player_b, p_cal
           FROM predictions
           WHERE settled = 0 AND match_date >= ?
           ORDER BY match_date, id""",
        (today,),
    )
    signals: List[ModelSignal] = []
    for row in rows:
        if not _valid_probability(row["p_cal"]):
            continue
        p_a = float(row["p_cal"])
        detail = (
            f"Tennis-Shadow · {row['tour']} · {row['tournament']} · "
            f"{row['match_date']}"
        )
        for side, player, prob in (
            ("A", row["player_a"], p_a),
            ("B", row["player_b"], 1.0 - p_a),
        ):
            signals.append(
                ModelSignal(
                    key=f"tennis-{row['id']}-{side}",
                    label=(
                        f"🎾 {row['player_a']} vs {row['player_b']} · "
                        f"Sieg {player}"
                    ),
                    probability=prob,
                    detail=detail,
                )
            )
    return signals


def esports_signals(db_path: Union[str, Path] = ESPORTS_DB) -> List[ModelSignal]:
    """Pre-Match-E-Sport-Predictions (Status 'upcoming').

    model_probability liegt in Prozent vor (55.27 = 55,27 %); Bruchwerte
    (0.55) werden der Robustheit halber auch akzeptiert.
    """
    rows = _read_rows(
        db_path,
        """SELECT match_id, game, team1, team2, selection, model_probability
           FROM esports_shadow_predictions
           WHERE status = 'upcoming'
           ORDER BY logged_at DESC""",
    )
    signals: List[ModelSignal] = []
    for row in rows:
        raw = row["model_probability"]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw != raw:
            continue
        prob = raw / 100.0 if raw > 1.0 else float(raw)
        if not _valid_probability(prob):
            continue
        signals.append(
            ModelSignal(
                key=f"esports-{row['match_id']}",
                label=(
                    f"🎮 {row['game']} · {row['team1']} vs {row['team2']} · "
                    f"Sieg {row['selection']}"
                ),
                probability=prob,
                detail="E-Sport-Shadow · Pre-Match-Modell",
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
    max_age_hours: float = FOOTBALL_SIGNAL_MAX_AGE_HOURS,
) -> List[ModelSignal]:
    """Letzte Fußball-Scans (BTTS Prematch + Platzverweis) als Signale.

    Liest die von den Hintergrund-Scans persistierten Verdichtungen
    (scan_jobs/<name>.json) — frisch genug (< max_age_hours) und nur mit
    gültigen Wahrscheinlichkeiten.
    """
    now = now or datetime.now().astimezone()
    signals: List[ModelSignal] = []
    for name, source in (
        ("prematch", "Fußball-Scan · BTTS"),
        ("red_cards", "Fußball-Scan · Platzverweis"),
    ):
        document = load_persisted(name, jobs_dir=jobs_dir)
        if not document:
            continue
        finished = _parse_iso(document.get("finished_at"))
        if finished is None:
            continue
        age_hours = (now - finished).total_seconds() / 3600.0
        if age_hours < 0 or age_hours > max_age_hours:
            continue
        for row in document.get("signals") or []:
            if not isinstance(row, dict):
                continue
            probability = row.get("p")
            if not _valid_probability(probability):
                continue
            home, away, market = row.get("home"), row.get("away"), row.get("market")
            if not home or not away or not market:
                continue
            signals.append(
                ModelSignal(
                    key=f"football-{name}-{len(signals)}",
                    label=f"⚽ {home} vs {away} · {market}",
                    probability=float(probability),
                    detail=f"{source} · Stand {finished.strftime('%d.%m. %H:%M')}",
                )
            )
    return signals


def list_signals(
    tennis_db: Union[str, Path] = TENNIS_DB,
    esports_db: Union[str, Path] = ESPORTS_DB,
    jobs_dir: Union[str, Path] = JOBS_DIR,
    today: Optional[str] = None,
) -> List[ModelSignal]:
    """Alle verfügbaren Modell-Signale (Fußball, Tennis, E-Sport)."""
    return (
        football_signals(jobs_dir=jobs_dir)
        + tennis_signals(db_path=tennis_db, today=today)
        + esports_signals(db_path=esports_db)
    )
