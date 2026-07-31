"""E-sports shadow log: model predictions tracked against real results.

Every scan logs the Subgraph-ELO candidate for each match with enough
history (first observation per match counts). A later pass settles open
entries against the finished PandaScore result. The summary measures
what matters before real money: hit rate vs. average model probability
(calibration) and the Brier score.
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
    settled_at TEXT
)
"""


class EsportsShadowLog:
    def __init__(self, db_path: Any = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)
        with closing(self._connect()) as connection:
            connection.execute(_SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def log_predictions(self, matches: List[Dict[str, Any]]) -> int:
        """Log model candidates for matches; first observation per match wins."""
        now = datetime.now(timezone.utc).isoformat()
        logged = 0
        with closing(self._connect()) as connection:
            for match in matches or []:
                if not isinstance(match, dict):
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
                selected_team_id = (
                    team1_id
                    if candidate.selection == match.get("team1")
                    else team2_id
                )
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
                        risk_adjusted_probability, minimum_odds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        int(match.get("team1_score") or 0),
                        int(match.get("team2_score") or 0),
                        float(elo1),
                        float(elo2),
                        float(candidate.model_probability),
                        float(candidate.risk_adjusted_probability),
                        float(candidate.minimum_odds),
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
    ) -> int:
        """Settle open predictions against finished match results."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT match_id, selected_team_id, series_type, score1, score2
                FROM esports_shadow_predictions
                WHERE settled = 0
                ORDER BY logged_at ASC
                LIMIT ?
                """,
                (max_calls,),
            ).fetchall()
        settled = 0
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            for row in rows:
                try:
                    result = result_fetcher(int(row["match_id"]))
                except Exception:
                    continue
                if not isinstance(result, dict):
                    continue
                winner_id = result.get("winner_team_id")
                if (
                    not isinstance(winner_id, int)
                    or isinstance(winner_id, bool)
                    or winner_id <= 0
                ):
                    continue
                hit = 1 if winner_id == int(row["selected_team_id"]) else 0
                connection.execute(
                    """
                    UPDATE esports_shadow_predictions
                    SET settled = 1, winner_team_id = ?, hit = ?, settled_at = ?
                    WHERE match_id = ?
                    """,
                    (winner_id, hit, now, int(row["match_id"])),
                )
                settled += 1
            connection.commit()
        return settled

    def summary(self) -> Dict[str, Any]:
        with closing(self._connect()) as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(settled) AS settled_n,
                       SUM(CASE WHEN settled = 1 THEN hit ELSE 0 END) AS hits,
                       AVG(CASE WHEN settled = 1 THEN model_probability END) AS avg_prob,
                       AVG(CASE WHEN settled = 1
                           THEN (model_probability / 100.0 - hit)
                                * (model_probability / 100.0 - hit)
                           END) AS brier
                FROM esports_shadow_predictions
                """
            ).fetchone()
        total = int(totals["n"] or 0)
        settled_n = int(totals["settled_n"] or 0)
        hits = int(totals["hits"] or 0)
        return {
            "predictions": total,
            "settled": settled_n,
            "hits": hits,
            "hit_rate": round(hits / settled_n * 100.0, 1) if settled_n else None,
            "avg_model_probability": (
                round(float(totals["avg_prob"]), 1)
                if totals["avg_prob"] is not None
                else None
            ),
            "brier_score": (
                round(float(totals["brier"]), 4)
                if totals["brier"] is not None
                else None
            ),
            "open": total - settled_n,
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
