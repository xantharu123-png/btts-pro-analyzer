"""Closing-line and settled-return recorder with quote provenance."""

import sqlite3
from contextlib import contextmanager
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from betting_math import validate_decimal_odds, validate_probability_percent


class CLVTracker:
    """Store pre-event predictions, verified prices, closers, and settlement."""

    OPENING_QUOTE_MAX_AGE = timedelta(minutes=10)
    CLOSING_WINDOW = timedelta(minutes=15)

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
                str(model_version or '').strip() or None,
                str(policy_version or '').strip() or None,
            ))
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
                SELECT result, quoted_at, fixture_kickoff, bookmaker, quote_source
                FROM predictions WHERE id = ?
                ''',
                (prediction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"prediction {prediction_id} does not exist")
            if row[0] is not None:
                raise ValueError("closing price cannot be changed after settlement")
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
            conn.execute('''
                UPDATE predictions
                SET closing_odds = ?, closing_bookmaker = ?, closing_source = ?,
                    closing_quoted_at = ?
                WHERE id = ?
            ''', (price, bookmaker, quote_source, quote_time, prediction_id))

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
                'SELECT odds, result FROM predictions WHERE id = ?',
                (prediction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"prediction {prediction_id} does not exist")
            if row[1] is not None:
                raise ValueError("prediction is already settled")
            price = validate_decimal_odds(row[0])
            profit = price - 1.0 if normalized_result == 'Won' else (
                -1.0 if normalized_result == 'Lost' else 0.0
            )
            conn.execute('''
                UPDATE predictions
                SET result = ?, profit = ?, home_score = ?, away_score = ?,
                    settled_at = ?
                WHERE id = ?
            ''', (
                normalized_result, profit, home_score, away_score,
                datetime.now(timezone.utc).isoformat(), prediction_id,
            ))

    def get_clv_statistics(
        self,
        days: int = 30,
        *,
        model_version: Optional[str] = None,
        policy_version: Optional[str] = None,
    ) -> Dict:
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 36500:
            raise ValueError("days must be an integer between 1 and 36500")
        version_filters = {
            "model_version": model_version,
            "policy_version": policy_version,
        }
        for field, value in version_filters.items():
            if value is not None and not str(value).strip():
                raise ValueError(f"{field} must be non-empty when provided")
        date_filter = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        clauses = ["created_at > ?", "result IS NOT NULL"]
        params: list[object] = [date_filter]
        for field, value in version_filters.items():
            if value is not None:
                clauses.append(f"{field} = ?")
                params.append(str(value).strip())
        with self._connect() as conn:
            rows = conn.execute(f'''
                SELECT odds, closing_odds, result, profit, quoted_at,
                       closing_quoted_at, fixture_kickoff
                FROM predictions
                WHERE {' AND '.join(clauses)}
            ''', tuple(params)).fetchall()

        if not rows:
            return {
                'total_bets': 0,
                'clv_bets': 0,
                'avg_clv': None,
                'win_rate': None,
                'profit': None,
                'roi': None,
            }

        valid_rows = []
        clv_values = []
        for opening, closing, result, profit, opening_time, closing_time, kickoff in rows:
            try:
                opening_price = validate_decimal_odds(opening)
                numeric_profit = float(profit)
            except (TypeError, ValueError):
                continue
            if result not in {'Won', 'Lost', 'Push'} or not math.isfinite(numeric_profit):
                continue
            valid_rows.append((result, numeric_profit))
            if (
                closing is not None
                and self._valid_closing_timing(
                    opening_time, closing_time, kickoff
                )
            ):
                try:
                    closing_price = validate_decimal_odds(closing)
                except (TypeError, ValueError):
                    continue
                clv_values.append(
                    (opening_price / closing_price - 1.0) * 100.0
                )

        if not valid_rows:
            return {
                'total_bets': 0,
                'clv_bets': 0,
                'avg_clv': None,
                'win_rate': None,
                'profit': None,
                'roi': None,
            }

        decisions = [result for result, _ in valid_rows if result != 'Push']
        wins = sum(result == 'Won' for result in decisions)
        total_profit = sum(profit for _, profit in valid_rows)
        return {
            'total_bets': len(valid_rows),
            'clv_bets': len(clv_values),
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
