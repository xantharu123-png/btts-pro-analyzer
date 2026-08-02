from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from price_ledger import (
    PriceLedger,
    PriceLedgerError,
    PriceLedgerIntegrityError,
    PriceQuote,
)


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=3)


def _quote(**changes) -> PriceQuote:
    values = {
        "sport": "FOOTBALL",
        "event_id": "fixture-123",
        "event_name": "France vs Spain",
        "scheduled_start": START,
        "market_key": "TOTAL_OVER_4_5_CORNERS",
        "market_name": "Total corners",
        "selection_key": "OVER_4_5",
        "selection_name": "Over 4.5",
        "decimal_odds": 1.83,
        "phase": "ENTRY",
        "source": "MANUAL",
        "captured_at": NOW,
        "line": 4.5,
        "model_ref": "challenge-v4",
        "metadata": {"candidate_id": "abc"},
    }
    values.update(changes)
    return PriceQuote(**values)


def test_append_round_trip_and_hash_chain(tmp_path):
    ledger = PriceLedger(tmp_path / "prices.db")
    observation = ledger.append(_quote(), now=NOW)
    restored = ledger.get(observation.id)

    assert restored.bookmaker == "N1Bet"
    assert restored.decimal_odds == 1.83
    assert restored.line == 4.5
    assert restored.metadata == {"candidate_id": "abc"}
    assert ledger.verify_chain() == (True, None)


def test_rows_cannot_be_updated_or_deleted_through_sql(tmp_path):
    path = tmp_path / "prices.db"
    ledger = PriceLedger(path)
    observation = ledger.append(_quote(), now=NOW)
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE price_observations SET odds_micros=2000000 WHERE id=?",
                (observation.id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM price_observations WHERE id=?",
                (observation.id,),
            )


def test_correction_is_a_new_linked_observation(tmp_path):
    ledger = PriceLedger(tmp_path / "prices.db")
    original = ledger.append(_quote(), now=NOW)
    correction_time = NOW + timedelta(minutes=1)
    correction = ledger.append(
        _quote(
            decimal_odds=1.87,
            captured_at=correction_time,
            supersedes_id=original.id,
        ),
        now=correction_time,
    )
    assert correction.id != original.id
    assert correction.supersedes_id == original.id
    assert ledger.get(original.id).decimal_odds == 1.83
    assert ledger.verify_chain() == (True, None)


def test_correction_cannot_switch_event_identity(tmp_path):
    ledger = PriceLedger(tmp_path / "prices.db")
    original = ledger.append(_quote(), now=NOW)
    with pytest.raises(PriceLedgerError, match="same event and selection"):
        ledger.append(
            _quote(
                event_id="other-event",
                captured_at=NOW + timedelta(minutes=1),
                supersedes_id=original.id,
            ),
            now=NOW + timedelta(minutes=1),
        )


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"decimal_odds": 1.0}, "greater than 1.0"),
        ({"captured_at": NOW - timedelta(minutes=6)}, "retroactively"),
        ({"captured_at": START + timedelta(seconds=1)}, "future"),
        ({"source": "SCREENSHOT_WITHOUT_PERMISSION"}, "unsupported quote source"),
        ({"phase": "AFTER_RESULT"}, "unsupported quote phase"),
    ],
)
def test_invalid_or_retroactive_quotes_are_rejected(tmp_path, changes, error):
    ledger = PriceLedger(tmp_path / "prices.db")
    with pytest.raises(PriceLedgerError, match=error):
        ledger.append(_quote(**changes), now=NOW)


def test_pre_match_phase_is_rejected_after_scheduled_start(tmp_path):
    ledger = PriceLedger(tmp_path / "prices.db")
    captured = START + timedelta(seconds=1)
    with pytest.raises(PriceLedgerError, match="after start"):
        ledger.append(
            _quote(captured_at=captured),
            now=captured,
        )


def test_concurrent_appends_keep_one_valid_chain(tmp_path):
    ledger = PriceLedger(tmp_path / "prices.db")

    def append(index: int) -> int:
        return ledger.append(
            _quote(
                selection_key=f"selection-{index}",
                selection_name=f"Selection {index}",
                decimal_odds=1.5 + index / 100,
            ),
            now=NOW,
        ).id

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(append, range(18)))
    assert sorted(ids) == list(range(1, 19))
    assert ledger.verify_chain() == (True, None)


def test_external_tampering_is_detected_before_next_append(tmp_path):
    path = tmp_path / "prices.db"
    ledger = PriceLedger(path)
    ledger.append(_quote(), now=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER price_observations_no_update")
        connection.execute(
            "UPDATE price_observations SET odds_micros=9990000 WHERE id=1"
        )
    assert ledger.verify_chain() == (False, 1)
    with pytest.raises(PriceLedgerIntegrityError, match="observation 1"):
        ledger.append(
            _quote(
                captured_at=NOW + timedelta(minutes=1),
                decimal_odds=1.9,
            ),
            now=NOW + timedelta(minutes=1),
        )


def test_price_schema_contains_no_model_probability_column(tmp_path):
    path = tmp_path / "prices.db"
    PriceLedger(path)
    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(price_observations)"
            )
        }
    assert "model_probability" not in columns
    assert "odds_micros" in columns
