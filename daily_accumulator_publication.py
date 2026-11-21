"""Attach the daily slip observer to an existing worker publication, never the UI."""
from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

LOG = logging.getLogger(__name__)
DB_NAME = "daily_accumulators.db"


def linked_legs(legs, signals, *, as_of, evidence_path, compact, bind):
    counts = Counter(signal.key for signal in signals)
    accepted = {leg["signal_key"] for leg in legs}
    rows = []
    for signal in signals:
        if signal.key in accepted and counts[signal.key] == 1:
            try:
                rows.append(compact(signal))
            except (KeyError, ValueError, TypeError):
                continue
    ids = {row["key"]: row["forecast_id"] for row in bind(rows, as_of=as_of, db_path=evidence_path)
           if row.get("forecast_id")}
    return [dict(leg, forecast_id=ids[leg["signal_key"]]) for leg in legs if leg["signal_key"] in ids]


def record_worker_combos(signals, *, as_of, directory, evidence_path=None):
    """Best effort diagnostic only. Never change existing tip publication or service status."""
    try:
        signals = tuple(signals)
        if not signals:
            return {"status": "empty"}
        from daily_accumulators import eligible_combo_legs, select_combo_set, select_confirmed_combo_set
        from daily_accumulator_receipts import capture_day, load_day
        from tip_publication import compact_signal_row, bind_forecast_ids
        day = as_of.astimezone(ZoneInfo("Europe/Zurich")).date()
        db = Path(directory) / DB_NAME
        arms = [(arm, selector) for arm, selector in [
            ("reference", select_confirmed_combo_set), ("model-observation", select_combo_set)]
            if len(load_day(db, day=day, arm=arm)) < 4]
        if not arms:
            return {"status": "full"}
        pool = linked_legs(eligible_combo_legs(signals, as_of=as_of, target_day=day), signals,
            as_of=as_of, evidence_path=evidence_path or Path(directory) / "forecast_evidence.db",
            compact=compact_signal_row, bind=bind_forecast_ids)
        if not pool:
            return {"status": "no_linked_legs"}
        sizes = {arm: [slip["size"] for slip in capture_day(
            db, day=day, as_of=as_of, pool=pool, select=selector, arm=arm)] for arm, selector in arms}
        LOG.info("Daily accumulator originals: day=%s linked_legs=%d sizes=%s", day, len(pool), sizes)
        return {"status": "processed", "linked_legs": len(pool), "sizes": sizes}
    except Exception:
        # An optional observation must never take down Doublebet, Tennis or today's original artifact.
        LOG.exception("Daily accumulator observation failed; existing forecasts unchanged")
        return {"status": "unavailable"}
