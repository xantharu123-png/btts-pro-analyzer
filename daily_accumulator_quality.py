"""Prospective whole-slip calibration; reads original evidence, never sports APIs.

v1: same original slip, two forecasts. Baseline = product of individual p.
Candidate = a single training-fitted log-odds offset per exact sport/model mix
and repeated-market structure. Price is not a feature. Test dates and offsets
are frozen BEFORE the first test day; the reference selector is unchanged.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Zurich")
UTC = timezone.utc
MODEL = "combo-scope-logit-offset-v1"
POLICY = "daily-accumulators-v1"
ARM = "reference"


def _clock(value):
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("expected a timezone-aware clock")
    return dt.astimezone(UTC)


def _day(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def _midnight(day):
    return datetime.combine(day, time.min, ZONE).astimezone(UTC)


def _digest(obj):
    raw = json.dumps({k: v for k, v in obj.items() if k != "digest"}, ensure_ascii=False,
                     sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode()).hexdigest()


def _sealed(obj):
    return dict(obj, digest=_digest(obj))


def _shape(slip):
    legs, size = slip["legs"], slip["size"]
    day = _day(slip["day"])
    decision, capture = _clock(slip["decision_at"]), _clock(slip["captured_at"])
    if (type(size) is not int or not 3 <= size <= 6 or len(legs) != size
            or slip["arm"] != ARM or slip["policy"] != POLICY or decision > capture
            or capture.astimezone(ZONE).date() != day):
        raise ValueError("not a frozen daily reference slip")
    for name in ("event_key", "forecast_id"):
        if len({leg[name] for leg in legs if leg[name]}) != size:
            raise ValueError("ambiguous leg identities")
    source, separator, book = str(slip.get("bookmaker_id") or "").partition(":")
    if not separator or not book or not source:
        raise ValueError("a priced original must identify the source")
    scope, markets, probs = [], [], []
    for leg in legs:
        # Verify the *frozen* offer, not its present freshness. Reopening the
        # page must not change a probability. Different source cohorts are
        # validated separately, but bookmaker identities/prices never enter p.
        point = leg["offers"][slip["bookmaker_id"]]
        seen, fetched, odds = _clock(point["observed_at"]), _clock(point["fetched_at"]), point["odds"]
        if (slip.get("price_status") != "confirmed" or type(odds) not in (float, int)
                or not math.isfinite(odds) or odds < 1.2 or not seen <= fetched <= decision
                or capture-seen > timedelta(minutes=45) or capture-fetched > timedelta(minutes=35)):
            raise ValueError("no admissible original common-book receipt")
        start, p = _clock(leg["starts_at"]), leg["probability"]
        if (start <= capture or start.astimezone(ZONE).date() != day or type(p) not in (int, float)
                or not 0 < p < 1 or any(not isinstance(leg.get(k), str) or not leg[k].strip()
                                          for k in ("sport", "model_version", "market_key", "selection"))):
            raise ValueError("unusable frozen leg")
        scope.append((leg["sport"], leg["model_version"]))
        markets.append((leg["sport"], leg["market_key"]))
        probs.append(p)
    # Separate repeated identical market exposure from unrelated markets; no
    # inference from bookmaker or decimal price. Scope preserves multiplicity.
    key = json.dumps([source, sorted(scope), sorted(Counter(markets).values())], separators=(",", ":"))
    return day, key, math.prod(probs)


def grade(slip, by_id):
    """Only completely verified original slips are binary training labels."""
    try:
        _shape(slip)
        capture, decision = _clock(slip["captured_at"]), _clock(slip["decision_at"])
        statuses = set()
        for leg in slip["legs"]:
            row = by_id[leg["forecast_id"]]
            if (any(row[k] != leg[k] for k in ("forecast_id", "event_key", "sport", "market_key",
                                                "model_version", "probability"))
                    or row["selection"] != leg.get("evidence_selection", leg["selection"])
                    or _clock(row["starts_at"]) != _clock(leg["starts_at"])
                    or row["causal"] is not True or row["invalid_result_evidence"] is not False
                    or _clock(row["decision_at"]) > decision or _clock(row["recorded_at"]) > capture
                    or _clock(row["effective_start"]) <= capture):
                return "UNMATCHED"
            if abs(_clock(row["effective_start"]) - _clock(leg["starts_at"])) > timedelta(hours=12):
                statuses.add("VOID")
            else:
                statuses.add(row["outcome"])
        if not statuses <= {"WIN", "LOSS", "VOID", "UNRESOLVED"}:
            return "UNMATCHED"
        if "VOID" in statuses:
            return "VOID"
        if "UNRESOLVED" in statuses:
            return "OPEN"
        return "LOSS" if "LOSS" in statuses else "WIN"
    except (KeyError, ValueError, TypeError, OverflowError):
        return "UNMATCHED"


def settled_receipts(slips, forecast_db, *, known_at):
    """Read-only join: exact archived IDs, canonical evidence/integrity rules.

    Resolve per slip: the generic report collapses revisions of a native
    market. Pooling all IDs across tickets would lose later real revisions.
    """
    from selection_performance import build_selection_performance_report
    cutoff, path = _clock(known_at), Path(forecast_db)
    if not path.is_file():
        for slip in slips:
            yield slip, "UNMATCHED"
        return
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for slip in slips:
            day, _, _ = _shape(slip)
            ids = [leg["forecast_id"] for leg in slip["legs"]]
            if _midnight(day+timedelta(days=1)) > cutoff:
                raise ValueError("settlement requires a completed local day")
            report = build_selection_performance_report(path, from_day=day, through_day=day,
                                                        forecast_ids=ids, as_of=cutoff)
            rows = {r["forecast_id"]: r for r in report["selections"]}
            marks = ", ".join("?" for _ in ids)
            for fid, raw in db.execute(f"SELECT forecast_id, payload_json FROM forecast_rows WHERE forecast_id IN ({marks})", ids):
                if fid in rows:
                    payload = json.loads(raw)
                    rows[fid].update(recorded_at=payload["recorded_at"], starts_at=payload["starts_at"])
            yield slip, grade(slip, rows)


def _prob(p, offset):
    mult = math.exp(offset)
    return p * mult / ((1-p) + p*mult)


def _offset(pys):
    # Offset-only logistic recalibration (Bernoulli score equation). Refuse
    # separation instead of assigning probability zero or one.
    wins = sum(y for p, y in pys)
    if len(pys) < 30 or wins in (0, len(pys)):
        return None
    lo, hi = -8.0, 8.0
    for _ in range(52):
        mid = (lo+hi)/2
        if sum(_prob(p, mid) for p, _ in pys) < wins:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def _group(records, start=None, stop=None):
    groups, seen = defaultdict(list), set()
    for slip, outcome in records:
        day, scope, p = _shape(slip)
        if ((start and day < start) or (stop and day > stop)
                or (day, slip["size"]) in seen or outcome not in {"WIN", "LOSS", "VOID", "OPEN", "UNMATCHED"}):
            raise ValueError("unexpected, duplicate or out-of-period original")
        seen.add((day, slip["size"]))
        groups[scope].append((day, p, outcome))
    return groups


def fit(records, *, issued_at, test_from, test_through):
    clock, first, last = _clock(issued_at), _day(test_from), _day(test_through)
    if not clock < _midnight(first) or not 139 <= (last-first).days <= 365:
        raise ValueError("freeze model before a predefined holdout of 140–366 days")
    groups = {}
    for scope, rows in _group(records, stop=clock.astimezone(ZONE).date()-timedelta(days=1)).items():
        pairs = [(p, int(s == "WIN")) for _, p, s in rows if s in {"WIN", "LOSS"}]
        offset = _offset(pairs)
        if offset is not None:
            groups[scope] = dict(offset=offset, training_days=len(pairs),
                                 low=min(p for p, _ in pairs), high=max(p for p, _ in pairs))
    return _sealed(dict(kind="fit", model=MODEL, policy=POLICY, arm=ARM, issued_at=clock.isoformat(),
                        test_from=str(first), test_through=str(last), groups=groups))


def _intervals(rows, offset, family):
    """Resample whole ISO weeks; paired candidate and reference on same slip."""
    import numpy as np
    blocks = defaultdict(lambda: [0., 0., 0.])
    for day, p, result in rows:
        y, q = int(result == "WIN"), _prob(p, offset)
        block = blocks[day - timedelta(days=day.weekday())]
        block[0] += (q-y)**2 - (p-y)**2
        block[1] += q-y
        block[2] += 1
    data = np.asarray([blocks[w] for w in sorted(blocks)])
    rng = np.random.default_rng(20261121)
    # Bonferroni over all predeclared scopes (at least the four tested sizes)
    # and both claims. Chunk to bound memory even with a long validation window.
    tail = .05 / (4*family)
    draws = []
    for _ in range(64):
        sums = data[rng.integers(len(data), size=(256, len(data)))].sum(axis=1)
        draws.append(sums[:, :2] / sums[:, 2, None])
    low, high = np.quantile(np.concatenate(draws), [tail, 1-tail], axis=0)
    return [[float(lo), float(hi)] for lo, hi in zip(low, high)]


def review(model, records, *, issued_at):
    clock = _clock(issued_at)
    first, last = _day(model["test_from"]), _day(model["test_through"])
    if (model.get("kind") != "fit" or model.get("model") != MODEL or model.get("arm") != ARM
            or model.get("policy") != POLICY or model.get("digest") != _digest(model)
            or _clock(model["issued_at"]) >= _midnight(first) or clock < _midnight(last+timedelta(days=8))):
        raise ValueError("unregistered model, premature review or incorrect policy")
    groups = _group(records, first, last)
    results = {}
    family = max(4, len(model["groups"]))
    for scope, group in model["groups"].items():
        rows = groups.get(scope, [])
        usable = [(d,p,s) for d,p,s in rows if s in {"WIN", "LOSS"}]
        counts = Counter(s for _, _, s in rows)
        weeks = len({d.isocalendar()[:2] for d, _, _ in usable})
        report = dict(group, passed=False, test_days=len(usable), weeks=weeks, wins=counts["WIN"],
                      losses=counts["LOSS"], void=counts["VOID"], open=counts["OPEN"], unmatched=counts["UNMATCHED"],
                      days_without_this_scope=(last-first).days+1-len(rows))
        if usable:
            ps = [(p,_prob(p,group["offset"]),int(s == "WIN")) for _,p,s in usable]
            report.update(expected_wins=sum(q for p,q,y in ps), brier=sum((q-y)**2 for p,q,y in ps)/len(ps),
                          reference_brier=sum((p-y)**2 for p,q,y in ps)/len(ps))
        if len(usable) >= 100 and weeks >= 20 and not counts["OPEN"] and not counts["UNMATCHED"]:
            diff, bias = _intervals(usable, group["offset"], family)
            report.update(brier_difference_ci=diff, calibration_ci=bias,
                          passed=diff[1] < 0 and -.10 <= bias[0] <= bias[1] <= .10)
        results[scope] = report
    return _sealed(dict(kind="review", model=MODEL, policy=POLICY, arm=ARM, fit_digest=model["digest"],
                        test_from=str(first), test_through=str(last), issued_at=clock.isoformat(),
                        expires_at=(_midnight(last+timedelta(days=98))).isoformat(),
                        groups=results, untrained_originals=sum(len(r) for g,r in groups.items() if g not in results)))


def chance_for_slip(slip, artifact, *, as_of):
    """Only a tested, matching, already available estimate for a future slip."""
    try:
        _, scope, p = _shape(slip)
        now, issued = _clock(as_of), _clock(artifact["issued_at"])
        if (artifact.get("model") != MODEL or artifact.get("kind") != "review"
                or artifact.get("digest") != _digest(artifact)
                or artifact["policy"] != slip["policy"] or artifact["arm"] != slip["arm"]
                or not issued <= _clock(slip["decision_at"]) <= _clock(slip["captured_at"]) <= now < _clock(artifact["expires_at"])
                or any(_clock(leg["starts_at"]) <= now for leg in slip["legs"])):
            return None
        g = artifact["groups"][scope]
        if (g["passed"] is not True or g["test_days"] < 100 or g["weeks"] < 20
                or not g["low"] <= p <= g["high"] or g["brier_difference_ci"][1] >= 0
                or not -.1 <= g["calibration_ci"][0] <= g["calibration_ci"][1] <= .1):
            return None
        return _prob(p, g["offset"])
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError, IndexError):
        return None
