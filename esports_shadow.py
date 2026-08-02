"""E-sports shadow log: model predictions tracked against real results.

Every scan logs the Subgraph-ELO candidate for each UPCOMING match with
enough history (first observation per match counts). A later pass settles
open entries against the finished PandaScore result. The summary measures
what matters before real money: hit rate vs. average model probability
(calibration) and the Brier score.

Two disciplines keep the metric honest:

- PRE-MATCH ONLY.  A match first seen live is skipped: its logged
  probability would be conditioned on the current series score, a
  different product.  Mixing near-certain live records (2:0 in a Bo3)
  into the summary inflates hit rate and Brier with records nobody
  could have bet pre-match — the first 30-row batch carried 33 % of
  those (E1 audit finding).
- EXPLICIT SETTLEMENT ONLY. Provider gaps remain open and rotate through the
  retry queue. Only a provider-confirmed cancellation is voided.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config_loader import load_app_config
from esports_elo import subgraph_ratings
from multi_sport_recommendations import esports_match_winner_candidate
from scanners.esports_scanner import EsportsScanner

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "esports_shadow.db"
MAX_SETTLE_CALLS_PER_RUN = 15
STALE_AFTER_DAYS = 30
ESPORTS_MODEL_VERSION = "subgraph-elo-v2"
ESPORTS_RELEASE_MIN_SETTLED = 100
ESPORTS_RELEASE_MAX_CALIBRATION_GAP = 0.08
ESPORTS_RELEASE_MAX_BRIER = 0.25

_SCHEMA = """
CREATE TABLE IF NOT EXISTS esports_shadow_predictions (
    match_id INTEGER PRIMARY KEY,
    logged_at TEXT NOT NULL,
    game TEXT NOT NULL,
    team1 TEXT NOT NULL,
    team2 TEXT NOT NULL,
    selected_team_id INTEGER NOT NULL,
    selection TEXT NOT NULL,
    status TEXT NOT NULL,
    series_type INTEGER NOT NULL,
    score1 INTEGER NOT NULL,
    score2 INTEGER NOT NULL,
    elo1 REAL NOT NULL,
    elo2 REAL NOT NULL,
    model_probability REAL NOT NULL,
    risk_adjusted_probability REAL NOT NULL,
    minimum_odds REAL NOT NULL,
    settled INTEGER NOT NULL DEFAULT 0,
    winner_team_id INTEGER,
    hit INTEGER,
    settled_at TEXT,
    scheduled_at TEXT,
    model_version TEXT,
    last_checked_at TEXT,
    check_attempts INTEGER NOT NULL DEFAULT 0
)
"""


class EsportsShadowLog:
    def __init__(self, db_path: Any = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)
        with closing(self._connect()) as connection:
            connection.execute(_SCHEMA)
            existing = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(esports_shadow_predictions)"
                )
            }
            additions = {
                "scheduled_at": "TEXT",
                "model_version": "TEXT",
                "last_checked_at": "TEXT",
                "check_attempts": "INTEGER NOT NULL DEFAULT 0",
            }
            for column, column_type in additions.items():
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE esports_shadow_predictions "
                        f"ADD COLUMN {column} {column_type}"
                    )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def log_predictions(self, matches: List[Dict[str, Any]]) -> int:
        """Log model candidates for matches; first observation per match wins.

        Pre-match discipline: only matches the provider reports as
        ``upcoming`` (score verified 0:0, not started) are logged.  A
        match first seen live would record a score-conditioned
        probability — a different product that corrupts calibration.
        """
        now = datetime.now(timezone.utc).isoformat()
        logged = 0
        with closing(self._connect()) as connection:
            for match in matches or []:
                if not isinstance(match, dict):
                    continue
                if match.get("status") != "upcoming":
                    continue
                score1 = match.get("team1_score")
                score2 = match.get("team2_score")
                if (
                    isinstance(score1, bool)
                    or isinstance(score2, bool)
                    or not isinstance(score1, int)
                    or not isinstance(score2, int)
                    or score1 != 0
                    or score2 != 0
                ):
                    continue
                match_id = match.get("id")
                if (
                    not isinstance(match_id, int)
                    or isinstance(match_id, bool)
                    or match_id <= 0
                ):
                    continue
                candidate = esports_match_winner_candidate(match)
                if not candidate.model_ready:
                    continue
                team1_id = match.get("team1_id")
                team2_id = match.get("team2_id")
                if candidate.selection == match.get("team1"):
                    selected_team_id = team1_id
                elif candidate.selection == match.get("team2"):
                    selected_team_id = team2_id
                else:
                    continue
                if not isinstance(selected_team_id, int) or selected_team_id <= 0:
                    continue
                elo1, elo2, _subgraph_size = subgraph_ratings(
                    match.get("team1_history") or [],
                    match.get("team2_history") or [],
                    team1_id,
                    team2_id,
                )
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO esports_shadow_predictions (
                        match_id, logged_at, game, team1, team2,
                        selected_team_id, selection, status, series_type,
                        score1, score2, elo1, elo2, model_probability,
                        risk_adjusted_probability, minimum_odds,
                        scheduled_at, model_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        now,
                        str(match.get("game") or ""),
                        str(match.get("team1") or ""),
                        str(match.get("team2") or ""),
                        selected_team_id,
                        str(candidate.selection or ""),
                        str(match.get("status") or "live"),
                        int(match.get("series_type") or 0),
                        score1,
                        score2,
                        float(elo1),
                        float(elo2),
                        float(candidate.model_probability),
                        float(candidate.risk_adjusted_probability),
                        float(candidate.minimum_odds),
                        str(match.get("begin_at") or "").strip() or None,
                        ESPORTS_MODEL_VERSION,
                    ),
                )
                logged += cursor.rowcount
            connection.commit()
        return logged

    def settle_open(
        self,
        result_fetcher: Callable[[int], Optional[Dict[str, Any]]],
        *,
        max_calls: int = MAX_SETTLE_CALLS_PER_RUN,
        stale_after_days: int = STALE_AFTER_DAYS,
    ) -> int:
        """Settle open predictions against finished match results.

        Missing results stay open and rotate to the back of the queue. A row
        is voided only when the provider explicitly reports a canceled match;
        time or a transient API failure is not settlement evidence.
        """
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT match_id, selected_team_id, series_type, score1, score2,
                       logged_at, last_checked_at, check_attempts
                FROM esports_shadow_predictions
                WHERE settled = 0
                ORDER BY
                    CASE WHEN last_checked_at IS NULL THEN 0 ELSE 1 END,
                    last_checked_at ASC,
                    logged_at ASC,
                    match_id ASC
                LIMIT ?
                """,
                (max_calls,),
            ).fetchall()
        settled = 0
        now = datetime.now(timezone.utc)
        del stale_after_days
        with closing(self._connect()) as connection:
            for row in rows:
                try:
                    result = result_fetcher(int(row["match_id"]))
                except Exception:
                    result = None
                winner_id = result.get("winner_team_id") if isinstance(result, dict) else None
                explicitly_void = bool(
                    isinstance(result, dict) and result.get("void") is True
                )
                if (
                    not isinstance(winner_id, int)
                    or isinstance(winner_id, bool)
                    or winner_id <= 0
                ):
                    if explicitly_void:
                        connection.execute(
                            """
                            UPDATE esports_shadow_predictions
                            SET settled = 1, hit = NULL, settled_at = ?
                            WHERE match_id = ?
                            """,
                            (now.isoformat(), int(row["match_id"])),
                        )
                    else:
                        connection.execute(
                            """
                            UPDATE esports_shadow_predictions
                            SET last_checked_at = ?,
                                check_attempts = check_attempts + 1
                            WHERE match_id = ?
                            """,
                            (now.isoformat(), int(row["match_id"])),
                        )
                    continue
                hit = 1 if winner_id == int(row["selected_team_id"]) else 0
                connection.execute(
                    """
                    UPDATE esports_shadow_predictions
                    SET settled = 1, winner_team_id = ?, hit = ?, settled_at = ?
                    WHERE match_id = ?
                    """,
                    (winner_id, hit, now.isoformat(), int(row["match_id"])),
                )
                settled += 1
            connection.commit()
        return settled

    def summary(self) -> Dict[str, Any]:
        """Pre-match calibration numbers.

        The measured population is status = 'upcoming' rows only (E1);
        live records stay in the table for transparency but never enter
        the rates.  Voided rows (hit NULL) are excluded from scoring.
        """
        with closing(self._connect()) as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN settled = 1 AND hit IS NOT NULL
                           THEN 1 ELSE 0 END) AS scored_n,
                       SUM(CASE WHEN settled = 1 AND hit IS NOT NULL
                           THEN hit ELSE 0 END) AS hits,
                       SUM(CASE WHEN settled = 1 AND hit IS NULL
                           THEN 1 ELSE 0 END) AS voided_n,
                       AVG(CASE WHEN settled = 1 AND hit IS NOT NULL
                           THEN model_probability END) AS avg_prob,
                       AVG(CASE WHEN settled = 1 AND hit IS NOT NULL
                           THEN risk_adjusted_probability END) AS avg_risk_prob,
                       AVG(CASE WHEN settled = 1 AND hit IS NOT NULL
                           THEN (model_probability / 100.0 - hit)
                                * (model_probability / 100.0 - hit)
                           END) AS brier,
                       AVG(CASE WHEN settled = 1 AND hit IS NOT NULL
                           THEN (risk_adjusted_probability / 100.0 - hit)
                                * (risk_adjusted_probability / 100.0 - hit)
                           END) AS risk_brier
                FROM esports_shadow_predictions
                WHERE status = 'upcoming'
                """
            ).fetchone()
            live_n = connection.execute(
                """
                SELECT COUNT(*) AS n FROM esports_shadow_predictions
                WHERE status != 'upcoming'
                """
            ).fetchone()["n"]
        total = int(totals["n"] or 0)
        scored_n = int(totals["scored_n"] or 0)
        hits = int(totals["hits"] or 0)
        voided_n = int(totals["voided_n"] or 0)
        return {
            "predictions": total,
            "settled": scored_n,
            "hits": hits,
            "hit_rate": round(hits / scored_n * 100.0, 1) if scored_n else None,
            "avg_model_probability": (
                round(float(totals["avg_prob"]), 1)
                if totals["avg_prob"] is not None
                else None
            ),
            "avg_risk_adjusted_probability": (
                round(float(totals["avg_risk_prob"]), 1)
                if totals["avg_risk_prob"] is not None
                else None
            ),
            "brier_score": (
                round(float(totals["brier"]), 4)
                if totals["brier"] is not None
                else None
            ),
            "risk_adjusted_brier_score": (
                round(float(totals["risk_brier"]), 4)
                if totals["risk_brier"] is not None
                else None
            ),
            "open": total - scored_n - voided_n,
            "voided": voided_n,
            "live_records": int(live_n or 0),
        }

    def release_status(self) -> Dict[str, Any]:
        summary = self.summary()
        settled = int(summary["settled"])
        hit_rate = summary.get("hit_rate")
        average = summary.get("avg_risk_adjusted_probability")
        brier = summary.get("risk_adjusted_brier_score")
        gap = (
            abs(float(hit_rate) - float(average)) / 100.0
            if hit_rate is not None and average is not None
            else None
        )
        ready = bool(
            settled >= ESPORTS_RELEASE_MIN_SETTLED
            and gap is not None
            and gap <= ESPORTS_RELEASE_MAX_CALIBRATION_GAP
            and brier is not None
            and brier <= ESPORTS_RELEASE_MAX_BRIER
        )
        return {
            "ready": ready,
            "settled": settled,
            "required": ESPORTS_RELEASE_MIN_SETTLED,
            "calibration_gap": gap,
            "brier_score": brier,
        }


def _pandascore_result_fetcher(scanner: EsportsScanner) -> Callable[[int], Optional[Dict[str, Any]]]:
    def fetch(match_id: int) -> Optional[Dict[str, Any]]:
        return scanner.get_match_result(match_id)

    return fetch


def run_shadow_scan(
    db_path: Any = DEFAULT_DB_PATH,
    *,
    scanner: Optional[EsportsScanner] = None,
    max_settle_calls: int = MAX_SETTLE_CALLS_PER_RUN,
) -> Dict[str, Any]:
    """One shadow run: log current candidates, settle finished ones."""
    scanner = scanner or EsportsScanner()
    log = EsportsShadowLog(db_path)
    matches = scanner.get_matches("all") if scanner.api_key else []
    logged = log.log_predictions(matches)
    settled = log.settle_open(
        _pandascore_result_fetcher(scanner),
        max_calls=max_settle_calls,
    )
    summary = log.summary()
    summary.update(
        {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "scanned_matches": len(matches),
            "logged_new": logged,
            "settled_new": settled,
            "errors": dict(scanner.errors),
        }
    )
    return summary
