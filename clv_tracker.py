"""Closing-line and settled-return recorder with quote provenance."""

import sqlite3
from contextlib import contextmanager
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import unicodedata

from betting_math import validate_decimal_odds, validate_probability_percent


class DuplicatePredictionError(ValueError):
    """A fixture already has a prediction for the same model/policy version."""


class SettlementConflictError(ValueError):
    """A prediction was already settled, including by a concurrent writer."""


class CLVEvidenceIntegrityError(RuntimeError):
    """Stored CLV evidence violates a release-critical database invariant."""


class CLVTracker:
    """Store pre-event predictions, verified prices, closers, and settlement."""

    OPENING_QUOTE_MAX_AGE = timedelta(minutes=10)
    CLOSING_WINDOW = timedelta(minutes=15)
    SHADOW_SETTLEABLE_MARKETS = frozenset({
        'RESULT_HOME',
        'RESULT_DRAW',
        'RESULT_AWAY',
        'DC_1X',
        'DC_X2',
        'DC_12',
        'BTTS_YES',
        'BTTS_NO',
        'TOTAL_OVER_0_5',
        'TOTAL_UNDER_0_5',
        'TOTAL_OVER_1_5',
        'TOTAL_UNDER_1_5',
        'TOTAL_OVER_2_5',
        'TOTAL_UNDER_2_5',
        'TOTAL_OVER_3_5',
        'TOTAL_UNDER_3_5',
        'TOTAL_OVER_4_5',
        'TOTAL_UNDER_4_5',
    })

    def __init__(self, db_path: str = "btts_clv.db"):
        self.db_path = db_path
        self._init_database()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_database(self):
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id INTEGER NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    odds REAL,
                    closing_odds REAL,
                    model_probability REAL,
                    confidence INTEGER,
                    result TEXT,
                    profit REAL,
                    home_score INTEGER,
                    away_score INTEGER,
                    created_at TEXT NOT NULL,
                    settled_at TEXT,
                    fixture_kickoff TEXT
                )
            ''')
            existing = {
                row[1] for row in conn.execute('PRAGMA table_info(predictions)')
            }
            additions = {
                'bookmaker': 'TEXT',
                'quote_source': 'TEXT',
                'quoted_at': 'TEXT',
                'closing_bookmaker': 'TEXT',
                'closing_source': 'TEXT',
                'closing_quoted_at': 'TEXT',
                'data_quality': 'TEXT',
                'fixture_kickoff': 'TEXT',
                'model_version': 'TEXT',
                'policy_version': 'TEXT',
            }
            for column, column_type in additions.items():
                if column not in existing:
                    conn.execute(
                        f'ALTER TABLE predictions ADD COLUMN {column} {column_type}'
                    )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_fixture ON predictions(fixture_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created ON predictions(created_at)')
            duplicate = conn.execute('''
                SELECT fixture_id, model_version, policy_version, COUNT(*)
                FROM predictions
                WHERE model_version IS NOT NULL AND policy_version IS NOT NULL
                GROUP BY fixture_id, model_version, policy_version
                HAVING COUNT(*) > 1
                LIMIT 1
            ''').fetchone()
            if duplicate is not None:
                raise CLVEvidenceIntegrityError(
                    "versioned duplicate predictions exist; evidence is locked "
                    "until the rows are reviewed without deleting history"
                )
            conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_prediction_fixture_model_policy
                ON predictions(fixture_id, model_version, policy_version)
                WHERE model_version IS NOT NULL AND policy_version IS NOT NULL
            ''')

    @staticmethod
    def _required_text(value, field: str) -> str:
        text = str(value or '').strip()
        if not text:
            raise ValueError(f"{field} is required")
        return text

    @staticmethod
    def _iso_timestamp(value=None) -> str:
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(value, datetime):
            timestamp = value
        elif isinstance(value, str):
            timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            raise ValueError("timestamp must be datetime or ISO-8601 text")
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return timestamp.astimezone(timezone.utc).isoformat()

    @classmethod
    def _valid_closing_timing(cls, opening, closing, kickoff) -> bool:
        if opening is None or closing is None or kickoff is None:
            return False
        try:
            opening_time = datetime.fromisoformat(cls._iso_timestamp(opening))
            closing_time = datetime.fromisoformat(cls._iso_timestamp(closing))
            kickoff_time = datetime.fromisoformat(cls._iso_timestamp(kickoff))
        except (TypeError, ValueError):
            return False
        return (
            opening_time <= closing_time < kickoff_time
            and kickoff_time - closing_time <= cls.CLOSING_WINDOW
        )

    @staticmethod
    def _result_for_score(
        market_type,
        prediction,
        home_score: int,
        away_score: int,
    ) -> str:
        """Reconstruct a goal-market result from the stored full-time score."""

        from challenge_engine import (  # Imported lazily to keep tracker startup lean.
            COUNT_MARKET_KINDS,
            MARKET_BY_KEY,
            market_outcome,
        )

        market_key = str(market_type or '').strip()
        spec = MARKET_BY_KEY.get(market_key)
        if spec is not None:
            if (
                market_key not in CLVTracker.SHADOW_SETTLEABLE_MARKETS
                or spec.kind in COUNT_MARKET_KINDS
            ):
                raise ValueError(
                    "market is not eligible for the quoted Shadow CLV cohort"
                )
            stored_selection = unicodedata.normalize(
                'NFKC',
                str(prediction or '').strip(),
            ).casefold()
            canonical_selection = unicodedata.normalize(
                'NFKC',
                str(spec.selection).strip(),
            ).casefold()
            if not stored_selection or stored_selection != canonical_selection:
                raise ValueError(
                    "prediction selection does not match the canonical market"
                )
            won = market_outcome(spec, home_score, away_score)
            return 'Won' if won else 'Lost'

        if market_key.casefold() in {'btts', 'beide teams treffen'}:
            selection = unicodedata.normalize(
                'NFKC',
                str(prediction or '').strip(),
            ).casefold()
            if selection in {'yes', 'ja'}:
                expects_both = True
            elif selection in {'no', 'nein'}:
                expects_both = False
            else:
                raise ValueError("legacy BTTS selection is invalid")
            both_scored = home_score > 0 and away_score > 0
            return 'Won' if both_scored == expects_both else 'Lost'

        raise ValueError("market cannot be reconstructed from the stored score")

    def record_prediction(
        self,
        fixture_id: int,
        home_team: str,
        away_team: str,
        market_type: str,
        prediction: str,
        odds: float,
        model_probability: float,
        confidence: Optional[int] = None,
        *,
        bookmaker: str,
        quote_source: str,
        fixture_kickoff,
        quoted_at=None,
        data_quality: Optional[str] = None,
        model_version: Optional[str] = None,
        policy_version: Optional[str] = None,
    ) -> int:
        if (
            not isinstance(fixture_id, int)
            or isinstance(fixture_id, bool)
            or fixture_id <= 0
        ):
            raise ValueError("fixture_id must be a positive integer")
        price = validate_decimal_odds(odds)
        probability = validate_probability_percent(model_probability)
        values = {
            'home_team': self._required_text(home_team, 'home_team'),
            'away_team': self._required_text(away_team, 'away_team'),
            'market_type': self._required_text(market_type, 'market_type'),
            'prediction': self._required_text(prediction, 'prediction'),
            'bookmaker': self._required_text(bookmaker, 'bookmaker'),
            'quote_source': self._required_text(quote_source, 'quote_source'),
        }
        if values['home_team'].casefold() == values['away_team'].casefold():
            raise ValueError("home_team and away_team must be different")
        normalized_model_version = str(model_version or '').strip() or None
        normalized_policy_version = str(policy_version or '').strip() or None
        if not normalized_model_version or not normalized_policy_version:
            raise ValueError(
                "model_version and policy_version are required for every new prediction"
            )
        if (
            confidence is not None
            and (
                isinstance(confidence, bool)
                or not isinstance(confidence, int)
                or not 0 <= confidence <= 100
            )
        ):
            raise ValueError("confidence must be an integer from 0 to 100")
        quote_time = self._iso_timestamp(quoted_at)
        kickoff_time = self._iso_timestamp(fixture_kickoff)
        now = datetime.now(timezone.utc)
        quote_datetime = datetime.fromisoformat(quote_time)
        kickoff_datetime = datetime.fromisoformat(kickoff_time)
        if quote_datetime > now + timedelta(seconds=60):
            raise ValueError("opening quote cannot be in the future")
        if now - quote_datetime > self.OPENING_QUOTE_MAX_AGE:
            raise ValueError("opening quote is stale")
        if kickoff_datetime <= now or quote_datetime >= kickoff_datetime:
            raise ValueError("prediction and opening quote must be pre-kickoff")
        created_at = now.isoformat()

        with self._connect() as conn:
            try:
                cursor = conn.execute('''
                    INSERT INTO predictions (
                        fixture_id, home_team, away_team, market_type, prediction,
                        odds, model_probability, confidence, created_at, bookmaker,
                        quote_source, quoted_at, data_quality, fixture_kickoff,
                        model_version, policy_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    fixture_id, values['home_team'], values['away_team'],
                    values['market_type'], values['prediction'], price, probability,
                    confidence, created_at, values['bookmaker'], values['quote_source'],
                    quote_time, str(data_quality or '').strip() or None, kickoff_time,
                    normalized_model_version, normalized_policy_version,
                ))
            except sqlite3.IntegrityError as exc:
                if (
                    getattr(exc, "sqlite_errorname", None)
                    == "SQLITE_CONSTRAINT_UNIQUE"
                ):
                    existing = conn.execute('''
                        SELECT 1 FROM predictions
                        WHERE fixture_id = ? AND model_version = ?
                          AND policy_version = ?
                        LIMIT 1
                    ''', (
                        fixture_id,
                        normalized_model_version,
                        normalized_policy_version,
                    )).fetchone()
                    if existing is not None:
                        raise DuplicatePredictionError(
                            "fixture already recorded for this model/policy version"
                        ) from exc
                raise
            return int(cursor.lastrowid)

    def update_closing_odds(
        self,
        prediction_id: int,
        closing_odds: float,
        *,
        bookmaker: str,
        quote_source: str,
        quoted_at=None,
    ) -> None:
        if (
            isinstance(prediction_id, bool)
            or not isinstance(prediction_id, int)
            or prediction_id <= 0
        ):
            raise ValueError("prediction_id must be a positive integer")
        price = validate_decimal_odds(closing_odds)
        bookmaker = self._required_text(bookmaker, 'bookmaker')
        quote_source = self._required_text(quote_source, 'quote_source')
        quote_time = self._iso_timestamp(quoted_at)
        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT result, quoted_at, fixture_kickoff, bookmaker, quote_source,
                       closing_odds
                FROM predictions WHERE id = ?
                ''',
                (prediction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"prediction {prediction_id} does not exist")
            if row[0] is not None:
                raise ValueError("closing price cannot be changed after settlement")
            if row[5] is not None:
                raise ValueError("closing price is immutable once captured")
            if row[1] is not None:
                opening_time = self._iso_timestamp(row[1])
                if datetime.fromisoformat(quote_time) < datetime.fromisoformat(opening_time):
                    raise ValueError("closing quote cannot predate the opening quote")
            if row[2] is None:
                raise ValueError("fixture kickoff provenance is required for CLV")
            if bookmaker.casefold() != str(row[3]).casefold():
                raise ValueError("closing quote must use the opening bookmaker")
            if quote_source.casefold() != str(row[4]).casefold():
                raise ValueError("closing quote must use the opening source")
            kickoff_time = self._iso_timestamp(row[2])
            closing_datetime = datetime.fromisoformat(quote_time)
            kickoff_datetime = datetime.fromisoformat(kickoff_time)
            if closing_datetime > datetime.now(timezone.utc) + timedelta(seconds=60):
                raise ValueError("closing quote cannot be in the future")
            if closing_datetime >= kickoff_datetime:
                raise ValueError("closing quote must be captured before kickoff")
            if kickoff_datetime - closing_datetime > self.CLOSING_WINDOW:
                raise ValueError("closing quote is outside the 15-minute closing window")
            cursor = conn.execute('''
                UPDATE predictions
                SET closing_odds = ?, closing_bookmaker = ?, closing_source = ?,
                    closing_quoted_at = ?
                WHERE id = ? AND closing_odds IS NULL AND result IS NULL
            ''', (price, bookmaker, quote_source, quote_time, prediction_id))
            if cursor.rowcount != 1:
                raise ValueError(
                    "closing price was already captured or the prediction was settled"
                )

    def settle_prediction(
        self,
        prediction_id: int,
        result: str,
        home_score: int,
        away_score: int,
    ) -> None:
        if (
            isinstance(prediction_id, bool)
            or not isinstance(prediction_id, int)
            or prediction_id <= 0
        ):
            raise ValueError("prediction_id must be a positive integer")
        normalized_result = str(result or '').strip().title()
        if normalized_result not in {'Won', 'Lost', 'Push'}:
            raise ValueError("result must be Won, Lost, or Push")
        if (
            isinstance(home_score, bool)
            or isinstance(away_score, bool)
            or not isinstance(home_score, int)
            or not isinstance(away_score, int)
            or home_score < 0
            or away_score < 0
            or home_score > 30
            or away_score > 30
        ):
            raise ValueError("final scores must be non-negative integers")

        with self._connect() as conn:
            row = conn.execute(
                '''
                SELECT odds, result, market_type, prediction, fixture_kickoff
                FROM predictions WHERE id = ?
                ''',
                (prediction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"prediction {prediction_id} does not exist")
            if row[1] is not None:
                raise SettlementConflictError("prediction is already settled")
            if row[4] is None:
                raise ValueError("fixture kickoff provenance is required for settlement")
            settlement_time = datetime.now(timezone.utc)
            kickoff_datetime = datetime.fromisoformat(self._iso_timestamp(row[4]))
            if settlement_time < kickoff_datetime:
                raise ValueError("prediction cannot be settled before fixture kickoff")
            expected_result = self._result_for_score(
                row[2],
                row[3],
                home_score,
                away_score,
            )
            if normalized_result != expected_result:
                raise ValueError(
                    "result does not match market outcome for the final score"
                )
            price = validate_decimal_odds(row[0])
            profit = price - 1.0 if normalized_result == 'Won' else (
                -1.0 if normalized_result == 'Lost' else 0.0
            )
            cursor = conn.execute('''
                UPDATE predictions
                SET result = ?, profit = ?, home_score = ?, away_score = ?,
                    settled_at = ?
                WHERE id = ? AND result IS NULL
            ''', (
                normalized_result, profit, home_score, away_score,
                settlement_time.isoformat(), prediction_id,
            ))
            if cursor.rowcount != 1:
                raise SettlementConflictError(
                    "prediction was settled by a concurrent writer"
                )

    def get_clv_statistics(
        self,
        days: int = 30,
        *,
        model_version: Optional[str] = None,
        policy_version: Optional[str] = None,
    ) -> Dict:
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 36500:
            raise ValueError("days must be an integer between 1 and 36500")

        def empty_statistics(
            *,
            evidence_valid: bool,
            cohort_versioned: bool,
            duplicate_fixture_groups: int = 0,
            invalid_evidence_rows: int = 0,
            integrity_issues: Optional[List[str]] = None,
        ) -> Dict:
            return {
                'total_bets': 0,
                'clv_bets': 0,
                'independent_clv_fixtures': 0,
                'evidence_valid': evidence_valid,
                'cohort_versioned': cohort_versioned,
                'duplicate_fixture_groups': duplicate_fixture_groups,
                'invalid_evidence_rows': invalid_evidence_rows,
                'integrity_issues': list(integrity_issues or []),
                'avg_clv': None,
                'win_rate': None,
                'profit': None,
                'roi': None,
            }

        version_filters = {
            "model_version": model_version,
            "policy_version": policy_version,
        }
        if (model_version is None) != (policy_version is None):
            raise ValueError(
                "model_version and policy_version must either both be set or both be absent"
            )
        for field, value in version_filters.items():
            if value is not None and not str(value).strip():
                raise ValueError(f"{field} must be non-empty when provided")
        date_cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cohort_versioned = model_version is not None and policy_version is not None
        integrity_clauses = []
        integrity_params: list[object] = []
        for field, value in version_filters.items():
            if value is not None:
                integrity_clauses.append(f"{field} = ?")
                integrity_params.append(str(value).strip())
        integrity_where = (
            "WHERE " + " AND ".join(integrity_clauses)
            if integrity_clauses
            else ""
        )
        settled_clauses = [
            *integrity_clauses,
            "(result IS NOT NULL OR profit IS NOT NULL OR settled_at IS NOT NULL "
            "OR home_score IS NOT NULL OR away_score IS NOT NULL)",
        ]
        settled_where = "WHERE " + " AND ".join(settled_clauses)
        with self._connect() as conn:
            duplicate_fixture_groups = conn.execute(f'''
                SELECT COUNT(*) FROM (
                    SELECT fixture_id, model_version, policy_version
                    FROM predictions
                    {integrity_where}
                    GROUP BY fixture_id, model_version, policy_version
                    HAVING COUNT(*) > 1
                )
            ''', tuple(integrity_params)).fetchone()[0]
            rows = conn.execute(f'''
                SELECT fixture_id, home_team, away_team, market_type, prediction,
                       odds, closing_odds, result, profit, created_at, settled_at,
                       home_score, away_score, bookmaker, quote_source, quoted_at,
                       closing_bookmaker, closing_source, closing_quoted_at,
                       fixture_kickoff
                FROM predictions
                {settled_where}
            ''', tuple(integrity_params)).fetchall()

        if duplicate_fixture_groups:
            return empty_statistics(
                evidence_valid=False,
                cohort_versioned=cohort_versioned,
                duplicate_fixture_groups=duplicate_fixture_groups,
                integrity_issues=['duplicate_fixture_version'],
            )

        if not rows:
            return empty_statistics(
                evidence_valid=True,
                cohort_versioned=cohort_versioned,
            )

        current_time = datetime.now(timezone.utc)
        valid_rows: list[tuple[str, float, float]] = []
        invalid_evidence_rows = 0
        integrity_issues: set[str] = set()

        def stored_time(value, field: str) -> datetime:
            if value is None or not str(value).strip():
                raise ValueError(f"{field} is missing")
            return datetime.fromisoformat(self._iso_timestamp(value))

        def stored_text(value, field: str) -> str:
            try:
                return self._required_text(value, field)
            except ValueError as exc:
                raise ValueError(f"{field} is missing") from exc

        clv_values = []
        for (
            fixture_id,
            home_team,
            away_team,
            market_type,
            prediction,
            opening,
            closing,
            result,
            profit,
            created_at,
            settled_at,
            home_score,
            away_score,
            opening_bookmaker,
            opening_source,
            opening_time,
            closing_bookmaker,
            closing_source,
            closing_time,
            kickoff,
        ) in rows:
            row_issues: set[str] = set()
            try:
                if (
                    not isinstance(fixture_id, int)
                    or isinstance(fixture_id, bool)
                    or fixture_id <= 0
                ):
                    raise ValueError("fixture_id")
                home = stored_text(home_team, 'home_team')
                away = stored_text(away_team, 'away_team')
                stored_text(market_type, 'market_type')
                stored_text(prediction, 'prediction')
                if home.casefold() == away.casefold():
                    raise ValueError("teams")
                opening_price = validate_decimal_odds(opening)
                closing_price = validate_decimal_odds(closing)
                numeric_profit = float(profit)
                if result not in {'Won', 'Lost', 'Push'}:
                    raise ValueError("result")
                if not math.isfinite(numeric_profit):
                    raise ValueError("profit")
                if (
                    isinstance(home_score, bool)
                    or isinstance(away_score, bool)
                    or not isinstance(home_score, int)
                    or not isinstance(away_score, int)
                    or not 0 <= home_score <= 30
                    or not 0 <= away_score <= 30
                ):
                    raise ValueError("scores")
                expected_result = self._result_for_score(
                    market_type,
                    prediction,
                    home_score,
                    away_score,
                )
                if result != expected_result:
                    raise ValueError("result")
                expected_profit = (
                    opening_price - 1.0
                    if result == 'Won'
                    else (-1.0 if result == 'Lost' else 0.0)
                )
                if not math.isclose(
                    numeric_profit,
                    expected_profit,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ):
                    raise ValueError("profit")
            except (TypeError, ValueError):
                row_issues.add('malformed_settlement')

            try:
                created_datetime = stored_time(created_at, 'created_at')
                settled_datetime = stored_time(settled_at, 'settled_at')
                opening_datetime = stored_time(opening_time, 'quoted_at')
                closing_datetime = stored_time(
                    closing_time,
                    'closing_quoted_at',
                )
                kickoff_datetime = stored_time(kickoff, 'fixture_kickoff')
                opening_book = stored_text(opening_bookmaker, 'bookmaker')
                opening_quote_source = stored_text(
                    opening_source,
                    'quote_source',
                )
                closing_book = stored_text(
                    closing_bookmaker,
                    'closing_bookmaker',
                )
                closing_quote_source = stored_text(
                    closing_source,
                    'closing_source',
                )
                if opening_book.casefold() != closing_book.casefold():
                    raise ValueError("bookmaker")
                if (
                    opening_quote_source.casefold()
                    != closing_quote_source.casefold()
                ):
                    raise ValueError("quote_source")
                if not (
                    opening_datetime <= closing_datetime < kickoff_datetime
                    and kickoff_datetime - closing_datetime <= self.CLOSING_WINDOW
                    and created_datetime < kickoff_datetime
                    and opening_datetime
                    <= created_datetime + timedelta(seconds=60)
                    and created_datetime - opening_datetime
                    <= self.OPENING_QUOTE_MAX_AGE
                    and closing_datetime
                    >= created_datetime - timedelta(seconds=60)
                    and settled_datetime >= kickoff_datetime
                    and settled_datetime <= current_time + timedelta(seconds=60)
                ):
                    raise ValueError("quote_timing")
            except (TypeError, ValueError):
                row_issues.add('invalid_quote_provenance')

            if row_issues:
                invalid_evidence_rows += 1
                integrity_issues.update(row_issues)
                continue

            if created_datetime <= date_cutoff:
                continue
            clv_value = (opening_price / closing_price - 1.0) * 100.0
            valid_rows.append((result, numeric_profit, clv_value))
            clv_values.append(clv_value)

        if invalid_evidence_rows:
            return empty_statistics(
                evidence_valid=False,
                cohort_versioned=cohort_versioned,
                invalid_evidence_rows=invalid_evidence_rows,
                integrity_issues=sorted(integrity_issues),
            )

        if not valid_rows:
            return empty_statistics(
                evidence_valid=True,
                cohort_versioned=cohort_versioned,
            )

        decisions = [result for result, _, _ in valid_rows if result != 'Push']
        wins = sum(result == 'Won' for result in decisions)
        total_profit = sum(profit for _, profit, _ in valid_rows)
        return {
            'total_bets': len(valid_rows),
            'clv_bets': len(clv_values),
            'independent_clv_fixtures': len(clv_values),
            'evidence_valid': True,
            'cohort_versioned': cohort_versioned,
            'duplicate_fixture_groups': 0,
            'invalid_evidence_rows': 0,
            'integrity_issues': [],
            'avg_clv': round(sum(clv_values) / len(clv_values), 2) if clv_values else None,
            'win_rate': round(wins / len(decisions) * 100.0, 1) if decisions else None,
            'profit': round(total_profit, 2),
            'roi': round(total_profit / len(valid_rows) * 100.0, 1),
        }

    def get_recent_predictions(
        self,
        limit: int = 10,
        *,
        model_version: Optional[str] = None,
        policy_version: Optional[str] = None,
    ) -> List[Dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        version_filters = {
            "model_version": model_version,
            "policy_version": policy_version,
        }
        clauses = []
        params: list[object] = []
        for field, value in version_filters.items():
            if value is not None:
                text = str(value).strip()
                if not text:
                    raise ValueError(f"{field} must be non-empty when provided")
                clauses.append(f"{field} = ?")
                params.append(text)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(f'''
                SELECT id, fixture_id, home_team, away_team, market_type,
                       prediction, odds, closing_odds, result, profit, created_at,
                       bookmaker, quote_source, quoted_at, closing_quoted_at,
                       fixture_kickoff
                FROM predictions
                {where}
                ORDER BY created_at DESC
                LIMIT ?
            ''', tuple(params)).fetchall()

        predictions = []
        for row in rows:
            closing = row[7]
            try:
                opening_price = validate_decimal_odds(row[6])
            except (TypeError, ValueError):
                opening_price = None
            try:
                closing_price = (
                    validate_decimal_odds(closing) if closing is not None else None
                )
            except (TypeError, ValueError):
                closing_price = None
            predictions.append({
                'id': row[0],
                'fixture_id': row[1],
                'home_team': row[2],
                'away_team': row[3],
                'market_type': row[4],
                'prediction': row[5],
                'odds': opening_price,
                'closing_odds': closing_price,
                'result': row[8],
                'profit': row[9],
                'created_at': row[10],
                'bookmaker': row[11],
                'quote_source': row[12],
                'quoted_at': row[13],
                'closing_quoted_at': row[14],
                'fixture_kickoff': row[15],
                'clv': round(
                    (opening_price / closing_price - 1.0) * 100.0,
                    2,
                )
                if (
                    opening_price is not None
                    and closing_price is not None
                    and self._valid_closing_timing(row[13], row[14], row[15])
                )
                else None,
            })
        return predictions
