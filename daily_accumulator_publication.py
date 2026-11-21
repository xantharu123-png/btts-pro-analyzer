"""Publish original customer slips from the worker's existing model and price data."""
from __future__ import annotations

from collections import Counter
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

LOG = logging.getLogger(__name__)
DB_NAME = "daily_accumulators.db"


def read_artifact(path):
    try:
        if path.is_file() and path.stat().st_size <= 2_000_000:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, ValueError, TypeError):
        LOG.warning("Daily accumulator artifact unavailable: %s", path.name)
    return None


def candidate_selector(as_of, model, review):
    from daily_accumulator_quality import candidate_scorer
    from daily_accumulator_receipts import DEFAULT_POLICY
    from daily_accumulators import select_calibrated_combo_set
    stamp = as_of.isoformat()
    day = as_of.astimezone(ZoneInfo("Europe/Zurich")).date().isoformat()
    evaluate = candidate_scorer(model, as_of=as_of, review=review)
    def select(legs, *, frozen):
        def score(proposed):
            prospective = dict(proposed, day=day, policy=DEFAULT_POLICY, arm="candidate",
                               decision_at=stamp, captured_at=stamp, fit_digest=model["digest"])
            return evaluate(prospective)
        slips = select_calibrated_combo_set(legs, frozen=frozen, score=score)
        return [dict(slip, candidate_probability=slip["calibrated_probability"],
                     fit_digest=model["digest"]) for slip in slips]
    return select


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
    """Publish the day's selections without rerunning any model or price scan."""
    try:
        signals = tuple(signals)
        if not signals:
            return {"status": "empty"}
        from daily_accumulators import eligible_combo_legs, select_combo_set
        from daily_accumulator_receipts import PUBLIC_ARM, capture_day, load_daily_picks
        from tip_publication import compact_signal_row, bind_forecast_ids
        day = as_of.astimezone(ZoneInfo("Europe/Zurich")).date()
        db = Path(directory) / DB_NAME
        if len(load_daily_picks(db, day=day)) == 4:
            return {"status": "full"}
        pool = linked_legs(eligible_combo_legs(signals, as_of=as_of, target_day=day, public=True), signals,
            as_of=as_of, evidence_path=evidence_path or Path(directory) / "forecast_evidence.db",
            compact=compact_signal_row, bind=bind_forecast_ids)
        if not pool:
            return {"status": "no_linked_legs"}
        sizes = {PUBLIC_ARM: [slip["size"] for slip in capture_day(
            db, day=day, as_of=as_of, pool=pool, select=select_combo_set, arm=PUBLIC_ARM)]}
        LOG.info("Daily accumulator originals: day=%s linked_legs=%d sizes=%s", day, len(pool), sizes)
        return {"status": "processed", "linked_legs": len(pool), "sizes": sizes}
    except Exception:
        LOG.exception("Daily accumulator publication failed; existing forecasts unchanged")
        return {"status": "unavailable"}
