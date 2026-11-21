"""First prospective daily slip per policy, arm and size. No price/network lookups."""
from __future__ import annotations

import json
import math
import re
import sqlite3
from contextlib import closing
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_POLICY = "daily-accumulators-v1"
DEFAULT_ARM = "reference"
_ZURICH = ZoneInfo("Europe/Zurich")
_SIZES = (3, 4, 5, 6)
_LEG_FIELDS = ("forecast_id", "event_key", "sport", "market_key", "selection", "evidence_selection",
               "participants", "participant_names", "aliases", "event_label", "probability", "starts_at",
               "signal_key", "reason", "fixture_id", "model_version")
_TABLE = """CREATE TABLE IF NOT EXISTS daily_accumulator_receipts(
    day TEXT NOT NULL, policy TEXT NOT NULL, arm TEXT NOT NULL,
    size INTEGER NOT NULL CHECK(size BETWEEN 3 AND 6), captured_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(day,policy,arm,size)
) WITHOUT ROWID"""


def _now():
    return datetime.now(timezone.utc)


def _clock(value):
    clock = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if clock.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return clock.astimezone(timezone.utc)


def _day(value):
    return date.fromisoformat(str(value)).isoformat()


def _load(conn, day, policy, arm):
    return [json.loads(row[0]) for row in conn.execute(
        "SELECT payload_json FROM daily_accumulator_receipts WHERE day=? AND policy=? AND arm=? ORDER BY size",
        (day, policy, arm))]


def load_day(path, *, day, policy=DEFAULT_POLICY, arm=DEFAULT_ARM):
    """Read only; an uninitialised store (or absent directory) contains no slips."""
    db = Path(path)
    if not db.is_file():
        return []
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='daily_accumulator_receipts'").fetchone():
            return []
        return _load(conn, _day(day), policy, arm)


def _bound_leg(leg):
    return {key: leg[key] for key in _LEG_FIELDS if key in leg}


def _source_index(pool):
    # The producer has verified forecast IDs using tip_publication.bind_forecast_ids.
    # A selector cannot substitute an ID, probability, identity, or source offer.
    sources = {}
    for leg in pool:
        if not isinstance(leg, dict):
            continue
        key = leg.get("forecast_id")
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key):
            continue
        if key in sources and sources[key] != leg:
            sources[key] = None
        else:
            sources[key] = leg
    return sources


def _number(value):
    return type(value) in (float, int) and math.isfinite(value)


def _receipt(slip, sources, *, day, policy, arm, decision, captured):
    size = slip["size"]
    legs = slip["legs"]
    if (type(size) is not int or size not in _SIZES or not isinstance(legs, (list, tuple))
            or len(legs) != size or len({leg["event_key"] for leg in legs}) != size):
        return None
    if decision > captured or captured.astimezone(_ZURICH).date().isoformat() != day:
        return None
    book = slip.get("bookmaker_id")
    status = slip.get("price_status")
    if (book is None and (status != "unconfirmed" or arm != "model-observation")
            or book is not None and (status != "confirmed" or not isinstance(book,str) or not book.strip())):
        return None
    kept = []
    for leg in legs:
        source = sources.get(leg["forecast_id"])
        if source is None or _bound_leg(leg) != _bound_leg(source):
            return None
        start, probability = _clock(source["starts_at"]), source["probability"]
        if (not captured < start or start.astimezone(_ZURICH).date().isoformat() != day
                or not _number(probability) or not 0 < probability < 1
                or any(not source.get(key) for key in ("sport","event_key","market_key","selection","model_version"))):
            return None
        item = _bound_leg(source)
        item["offers"] = {}
        if book is not None:
            point = source["offers"][book]
            if leg["offers"].get(book) != point:
                return None
            observed, fetched = _clock(point["observed_at"]), _clock(point["fetched_at"])
            odds = point["odds"]
            if (not _number(odds) or odds < 1.20 or not observed <= fetched <= decision
                    or captured - observed > timedelta(minutes=45)
                    or captured - fetched > timedelta(minutes=35)):
                return None
            item["offers"][book] = {"odds": odds, "observed_at": observed.isoformat(),
                                    "fetched_at": fetched.isoformat()}
        kept.append(item)
    baseline = math.prod(leg["probability"] for leg in kept)
    supplied = slip["reference_probability"]
    if not _number(supplied) or not math.isclose(baseline, supplied, rel_tol=1e-12):
        return None
    calibration = {}
    if arm == "candidate":
        fit_digest = slip.get("fit_digest")
        score = slip.get("candidate_probability")
        if not isinstance(fit_digest, str) or not re.fullmatch("[0-9a-f]{64}", fit_digest) or not (
                _number(score) and 0 < score < 1):
            return None
        calibration = {"fit_digest": fit_digest, "candidate_probability": score}
    return dict(day=day, policy=policy, arm=arm, size=size, captured_at=captured.isoformat(),
                decision_at=decision.isoformat(), bookmaker_id=book, price_status=status,
                reference_probability=baseline, legs=kept, **calibration)


def capture_day(path, *, day, as_of, pool, select, policy=DEFAULT_POLICY, arm=DEFAULT_ARM):
    """Atomically fill empty sizes. Input pool must carry previously bound forecast IDs.

    Selection sees all existing sizes under the write lock, so two publishers cannot
    consume the same overlap allowance. Only the slip's own bookmaker is retained.
    A bad candidate cannot invalidate an unrelated size; a crashed transaction adds none.
    """
    day, decision = _day(day), _clock(as_of)
    wall = _now()
    if (decision > wall or day != wall.astimezone(_ZURICH).date().isoformat()
            or day != decision.astimezone(_ZURICH).date().isoformat()):
        raise ValueError("prospective capture requires today's actual Zurich decision")
    if not all(isinstance(key,str) and key.strip() for key in (policy,arm)):
        raise ValueError("missing policy/arm")
    db = Path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db, timeout=10)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(_TABLE)
        existing = _load(conn, day, policy, arm)
        taken = {slip["size"] for slip in existing}
        if len(taken) == len(_SIZES) or any(_clock(row["decision_at"]) > decision for row in existing):
            return existing
        pool = list(pool)
        sources = _source_index(pool)
        # Do not let a throwing generator leave a partial publication; a slot
        # first becomes evidence when the whole selection is ready to commit.
        proposed = list(select(deepcopy(pool), frozen=existing))
        captured = _now()
        for slip in proposed:
            try:
                if slip["size"] in taken:
                    continue
                original = _receipt(slip, sources, day=day, policy=policy, arm=arm,
                                    decision=decision, captured=captured)
                if original is None:
                    continue
                encoded = json.dumps(original, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False)
            except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
                continue
            conn.execute("INSERT INTO daily_accumulator_receipts VALUES(?,?,?,?,?,?)",
                         (day, policy, arm, original["size"], captured.isoformat(), encoded))
            taken.add(original["size"])
        return _load(conn, day, policy, arm)
