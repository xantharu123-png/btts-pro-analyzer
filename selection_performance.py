"""Read-only, date-bounded retrospective of frozen prospective forecasts.

This is a diagnostic of the internal candidate pool, not a reconstructed list
of customer tips. A supplied ID cohort is explicit, but does not itself prove
publication. No database initialization, settlement or provider calls occur.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from time import monotonic as _query_clock
from zoneinfo import ZoneInfo

from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS
from market_consensus import (
    ESPORTS_PRICE_SOURCE, ODDS_API_REFERENCE_SOURCE, REFERENCE_SOURCE,
    TEAM_PRICE_SOURCES, WETTFINDER_FETCH_MAX_AGE, WETTFINDER_QUOTE_MAX_AGE,
    exact_market_target,
)


_TABLES = {"forecast_runs", "forecast_rows", "forecast_quotes", "forecast_results"}
_MAX_ROWS = 100_000
_SPORT_PROVIDERS = {
    "football": {"api-football"}, "tennis": {"espn", "sofascore"},
    "esports": {"pandascore"}, "basketball": {"euroleague", "espn"},
    "ice_hockey": {"nhl"}, "cricket": {"cricbuzz", "cricketdata"},
}


def _utc(value: object) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _payload(row: dict, id_field: str) -> dict:
    value = json.loads(row["payload_json"])
    if not isinstance(value, dict) or _hash(value) != row[id_field]:
        raise ValueError("payload hash mismatch")
    return value


def _number(value: object, *, probability: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("invalid numeric value")
    if probability and not 0 <= value <= 1:
        raise ValueError("invalid probability")
    return float(value)


def _same_columns(row: dict, payload: dict, names: tuple[str, ...]) -> None:
    if any(row.get(name) != payload.get(name) for name in names):
        raise ValueError("payload differs from identity columns")


def _native_identity(forecast: dict) -> tuple[str, str, str]:
    sport = forecast["sport"]
    identity = forecast.get("quote_identity")
    if not isinstance(identity, dict) or sport not in _SPORT_PROVIDERS:
        raise ValueError("unsupported or absent native identity")
    provider = str(identity.get("fixture_source") or ("api-football" if sport == "football" else "")).casefold()
    provider_id = identity.get("provider_event_id")
    if sport == "football":
        fixture = identity.get("fixture_id")
        if type(fixture) is not int or fixture <= 0:
            raise ValueError("invalid football fixture identity")
        provider_id = provider_id or fixture
    if provider not in _SPORT_PROVIDERS[sport] or not provider_id or isinstance(provider_id, bool):
        raise ValueError("absent or mismatched native provider identity")
    # Several native adapters use stable_event_key() hashes rather than a
    # readable sport prefix. The native tuple provides the sport namespace.
    return sport, provider, str(provider_id)


def _role_binding(forecast: dict) -> tuple[str, str, str] | None:
    """Compare only complete explicit ordered participant bindings.

    Native IDs outrank mutable display names. Missing roles are unknown, never
    fabricated from a selection label or an event-key hash.
    """
    identity = forecast["quote_identity"]
    for first, second in (("home_id", "away_id"), ("competitor_a_id", "competitor_b_id")):
        a, b = identity.get(first), identity.get(second)
        if a is not None or b is not None:
            if isinstance(a, (int, str)) and not isinstance(a, bool) and isinstance(b, (int, str)) and not isinstance(b, bool) and str(a).strip() and str(b).strip() and str(a) != str(b):
                return "ids", str(a), str(b)
            return None
    for first, second in (("home_team", "away_team"), ("competitor_a", "competitor_b")):
        a, b = identity.get(first), identity.get(second)
        if isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip() and a.strip().casefold() != b.strip().casefold():
            return "names", a.strip().casefold(), b.strip().casefold()
    return None


def _forecast(row: dict, run_row: dict) -> dict:
    value = json.loads(row["payload_json"])
    if not isinstance(value, dict) or _hash({"run_id": row["run_id"], "forecast": value}) != row["forecast_id"]:
        raise ValueError("forecast hash mismatch")
    _same_columns(row, value, ("event_key", "sport", "market_key", "selection", "model_version", "policy_version", "starts_at", "decision_at"))
    run = json.loads(run_row["payload_json"])
    if not isinstance(run, dict) or _hash({k: v for k, v in run.items() if k != "recorded_at"}) != row["run_id"]:
        raise ValueError("run hash mismatch")
    _same_columns(run_row, run, ("decision_at",))
    if value.get("decision_at") != run.get("decision_at") or value.get("recorded_at") != run.get("recorded_at"):
        raise ValueError("forecast clock differs from run")
    digest = _hash({k: v for k, v in value.items() if k != "recorded_at"})
    if digest not in run.get("forecast_digests", []):
        raise ValueError("forecast absent from frozen run")
    _number(value.get("probability"), probability=True)
    start, decision, recorded = (_utc(value[k]) for k in ("starts_at", "decision_at", "recorded_at"))
    if decision > recorded or not decision < start or not recorded < start:
        raise ValueError("forecast was not frozen before planned start")
    identity = value.get("quote_identity")
    if not isinstance(identity, dict) or (identity.get("candidate_id") is not None and identity["candidate_id"] != value.get("candidate_id")) or identity.get("market_key") != value.get("market_key"):
        raise ValueError("quote identity differs from forecast")
    if identity.get("scheduled_start") is not None and _utc(identity["scheduled_start"]) != start:
        raise ValueError("native scheduled start differs from forecast")
    for field in ("modeled_at", "input_cutoff_at", "context_checked_at"):
        if value.get(field) is not None:
            _utc(value[field])
    value["native_event"] = _native_identity(value)
    value["forecast_id"] = row["forecast_id"]
    return value


def _result(row: dict, forecast: dict, cutoff: datetime) -> dict:
    value = _payload(row, "result_id")
    _same_columns(row, value, ("event_key", "market_key", "selection", "outcome", "observed_at"))
    if value["outcome"] not in {"WIN", "LOSS", "VOID"}:
        raise ValueError("unknown terminal outcome")
    proof = value.get("provenance")
    if not isinstance(proof, dict):
        raise ValueError("missing terminal provenance")
    _, provider, provider_id = forecast["native_event"]
    if str(proof.get("provider", "")).casefold() != provider or str(proof.get("provider_event_id", "")) != provider_id:
        raise ValueError("result belongs to another provider event")
    if not re.fullmatch(r"[0-9a-f]{64}", str(proof.get("payload_sha256", ""))) or not proof.get("source_record_id") or not proof.get("settlement_rule"):
        raise ValueError("missing result source hash or settlement rule")
    if any(token in str(proof["settlement_rule"]).casefold() for token in ("manual", "synthetic", "guess")):
        raise ValueError("inferred result is not prospective evidence")
    observed = _utc(value["observed_at"])
    start = _utc(forecast["starts_at"])
    if proof.get("actual_starts_at") is not None:
        if provider != "api-football":
            raise ValueError("actual kickoff override is not from football adapter")
        start = _utc(proof["actual_starts_at"])
    if observed > cutoff or (value["outcome"] != "VOID" and observed < start):
        raise ValueError("invalid terminal observation clock")
    value["effective_start"] = start
    return value


def _causal(forecast: dict, start: datetime) -> str | None:
    if _utc(forecast["decision_at"]) >= start or _utc(forecast["recorded_at"]) >= start:
        return "post_actual_start"
    modeled, inputs = forecast.get("modeled_at"), forecast.get("input_cutoff_at")
    if not modeled or not inputs:
        return "missing_input_clocks"
    if forecast.get("causal_provenance_complete") is not True:
        return "missing_causal_flag"
    if not _utc(inputs) <= _utc(modeled) <= _utc(forecast["decision_at"]):
        return "future_model_inputs"
    if forecast.get("context_checked_at") and _utc(forecast["context_checked_at"]) > _utc(forecast["decision_at"]):
        return "future_context"
    return None


def _quote(row: dict, forecast: dict, start: datetime) -> dict:
    value = _payload(row, "quote_id")
    _same_columns(row, value, ("forecast_id", "kind", "bookmaker_id", "observed_at", "fetched_at", "odds"))
    if type(row.get("executable")) is not int or row["executable"] not in {0, 1} or bool(row["executable"]) != value.get("executable"):
        raise ValueError("quote executable flag differs from payload")
    if value["forecast_id"] != forecast["forecast_id"] or value["kind"] != "entry" or not isinstance(value["bookmaker_id"], str) or not value["bookmaker_id"].strip():
        raise ValueError("quote is not a bound entry observation")
    if value.get("market_key") != forecast["market_key"] or _utc(value.get("starts_at")) != _utc(forecast["starts_at"]):
        raise ValueError("quote event or market differs from forecast")
    sport = forecast["sport"]
    identity = forecast["quote_identity"]
    if sport == "football":
        target = exact_market_target(forecast["market_key"])
        bound = target is not None and value.get("source") == REFERENCE_SOURCE and value.get("fixture_id") == identity.get("fixture_id") and value.get("selection") == target[1]
    else:
        expected_source = ODDS_API_REFERENCE_SOURCE if sport == "tennis" else ESPORTS_PRICE_SOURCE if sport == "esports" else TEAM_PRICE_SOURCES.get(sport)
        expected_id = identity.get("quote_provider_event_id")
        bound = bool(expected_source) and value.get("source") == expected_source and value.get("selection") == identity.get("selected_competitor") and bool(value.get("provider_event_id")) and (expected_id is None or str(value.get("provider_event_id")) == str(expected_id))
    if not bound:
        raise ValueError("quote source or exact selection mismatch")
    odds = _number(value["odds"])
    if odds <= 1:
        raise ValueError("invalid decimal quote")
    observed, fetched, decision = _utc(value["observed_at"]), _utc(value["fetched_at"]), _utc(forecast["decision_at"])
    if not observed <= fetched <= decision or observed >= start or fetched >= start:
        raise ValueError("quote was not available before decision and kickoff")
    value["quote_id"] = row["quote_id"]
    value["fresh"] = decision - fetched <= WETTFINDER_FETCH_MAX_AGE and decision - observed <= WETTFINDER_QUOTE_MAX_AGE
    return value


def _fetch_related(conn: sqlite3.Connection, table: str, column: str, values: list[str]) -> list[dict]:
    rows = []
    for begin in range(0, len(values), 800):
        chunk = values[begin:begin + 800]
        params = ",".join("?" for _ in chunk)
        rows.extend(dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE {column} IN ({params}) LIMIT ?", (*chunk, _MAX_ROWS + 1)))
        if len(rows) > _MAX_ROWS:
            raise ValueError(f"date window exceeds bounded {table} row limit")
    return rows


def _window_forecasts(conn: sqlite3.Connection, lower: datetime, upper: datetime, cutoff: datetime) -> list[dict]:
    """Two linear date scans, never a correlated result lookup per forecast."""
    planned = [dict(r) for r in conn.execute(
        "SELECT * FROM forecast_rows WHERE starts_at>=? AND starts_at<? LIMIT ?",
        (lower.isoformat(), upper.isoformat(), _MAX_ROWS + 1),
    )]
    if len(planned) > _MAX_ROWS:
        raise ValueError("date window exceeds bounded forecast row limit")
    # A moved event may have its frozen planned start outside this window. Read
    # terminal clocks once and then use the existing event-key index in bounded
    # batches. The terminal hashes/identity/clocks are still verified below.
    moved_rows = conn.execute(
        "SELECT event_key FROM forecast_results WHERE observed_at<=? "
        "AND CASE WHEN json_valid(payload_json) THEN json_extract(payload_json,'$.provenance.actual_starts_at') END>=? "
        "AND CASE WHEN json_valid(payload_json) THEN json_extract(payload_json,'$.provenance.actual_starts_at') END<? LIMIT ?",
        (cutoff.isoformat(), lower.isoformat(), upper.isoformat(), _MAX_ROWS + 1),
    ).fetchall()
    if len(moved_rows) > _MAX_ROWS:
        raise ValueError("date window exceeds bounded moved-event row limit")
    moved_keys = sorted({r[0] for r in moved_rows})
    selected = {row["forecast_id"]: row for row in planned}
    for row in _fetch_related(conn, "forecast_rows", "event_key", moved_keys):
        selected.setdefault(row["forecast_id"], row)
        if len(selected) > _MAX_ROWS:
            raise ValueError("date window exceeds bounded forecast row limit")
    return sorted(selected.values(), key=lambda r: (r["decision_at"], r["forecast_id"]))


def _summary(rows: list[dict], stake: float) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    scores = [row for row in rows if row["causal"] and row["outcome"] in {"WIN", "LOSS"}]
    returns = [row["hypothetical_return_units"] for row in rows if row["hypothetical_return_units"] is not None]
    risks = []
    logs = []
    bins = [{"lower": i / 10, "upper": (i + 1) / 10, "n": 0, "wins": 0, "sum_probability": 0.0} for i in range(10)]
    for row in scores:
        p, y = row["probability"], int(row["outcome"] == "WIN")
        risks.append((p - y) ** 2)
        clipped = max(1e-15, min(1 - 1e-15, p))
        logs.append(-(y * math.log(clipped) + (1 - y) * math.log(1 - clipped)))
        cell = bins[min(9, int(p * 10))]
        cell["n"] += 1
        cell["wins"] += y
        cell["sum_probability"] += p
    events = Counter(tuple(row["native_event"]) for row in rows)
    resolved = counts["WIN"] + counts["LOSS"]
    return {
        "selections": len(rows), "unique_events": len(events),
        "events_with_multiple_selections": sum(n > 1 for n in events.values()),
        "wins": counts["WIN"], "losses": counts["LOSS"], "voids": counts["VOID"], "unresolved": counts["UNRESOLVED"],
        "hit_rate": counts["WIN"] / resolved if resolved else None,
        "causal_hit_rate": sum(row["outcome"] == "WIN" for row in scores) / len(scores) if scores else None,
        "causal_selections": sum(row["causal"] for row in rows),
        "role_binding_coverage": dict(Counter(row.get("role_binding_status", "unknown") for row in rows)),
        "scored": len(scores), "brier_score": sum(risks) / len(risks) if risks else None,
        "log_loss": sum(logs) / len(logs) if logs else None,
        "quote_coverage": dict(Counter(row["quote_status"] for row in rows)),
        "hypothetical_resolved_quote_samples": len(returns),
        "hypothetical_void_quote_samples": sum(row["causal"] and row["quote_status"] == "fresh" and row["outcome"] == "VOID" for row in rows),
        "hypothetical_turnover_units": len(returns),
        "hypothetical_net_units": sum(returns),
        "hypothetical_net_amount": sum(returns) * stake,
        "hypothetical_roi": sum(returns) / len(returns) if returns else None,
        "probability_bins": [dict(lower=b["lower"], upper=b["upper"], n=b["n"], mean_probability=b["sum_probability"] / b["n"] if b["n"] else None, observed_rate=b["wins"] / b["n"] if b["n"] else None) for b in bins],
    }


def build_selection_performance_report(
    db_path: str | Path, *, from_day: str | date, through_day: str | date,
    timezone_name: str = "Europe/Zurich", unit_stake: float = 1.0,
    as_of: str | datetime | None = None, forecast_ids: list[str] | tuple[str, ...] | None = None,
    query_timeout_seconds: float = 30.0,
) -> dict:
    """Report completed local event days, deduplicating all model/policy revisions.

    ``forecast_ids`` is an explicit evidence cohort, not publication proof. An
    empty list means an empty cohort and never falls back to internal markets.
    """
    first = date.fromisoformat(from_day) if isinstance(from_day, str) else from_day
    last = date.fromisoformat(through_day) if isinstance(through_day, str) else through_day
    if type(first) is not date or type(last) is not date or last < first or (last - first).days > 365:
        raise ValueError("invalid or excessive completed-day window")
    zone = ZoneInfo(timezone_name)
    lower = datetime.combine(first, time.min, zone).astimezone(timezone.utc)
    upper = datetime.combine(last + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    cutoff = _utc(as_of or datetime.now(timezone.utc))
    if upper > cutoff:
        raise ValueError("through-day must be a completed local calendar day")
    stake = _number(unit_stake)
    if stake <= 0:
        raise ValueError("hypothetical unit stake must be positive")
    query_timeout = _number(query_timeout_seconds)
    if not 0 < query_timeout <= 120:
        raise ValueError("read-only query timeout must be positive and at most 120 seconds")
    ids = None if forecast_ids is None else set(forecast_ids)
    if ids is not None and (len(ids) > _MAX_ROWS or any(not isinstance(x, str) or not re.fullmatch(r"[0-9a-f]{64}", x) for x in ids)):
        raise ValueError("invalid explicit forecast ID cohort")
    path = Path(db_path)
    report = {
        "schema_version": "selection-performance-v1", "as_of": cutoff.isoformat(),
        "from_day": first.isoformat(), "through_day": last.isoformat(), "timezone": timezone_name,
        "window_start_utc": lower.isoformat(), "window_end_exclusive_utc": upper.isoformat(),
        "database_present": path.is_file(), "cohort": "internal_candidate_pool" if ids is None else "explicit_forecast_ids",
        "hypothetical_unit_stake": stake, "summary": _summary([], stake), "groups": [], "daily": [], "selections": [],
        "decision_revisions_read": 0, "duplicate_revisions_collapsed": 0, "clock_exclusions": {},
        "integrity_error_count": 0, "integrity_errors": [],
        "limitations": [
            "Internal forecasts are not proof of customer-visible tips or placed wagers.",
            "Different markets from one event are correlated, not independent samples.",
            "Returns use only exact fresh pre-decision quotes at or above 1.20, irrespective of the old value/executable gate.",
            "Missing, stale or unresolved prices are not assigned synthetic odds or losses.",
            "Hashes detect inconsistent stored records; public hashes do not authenticate against an attacker who can rewrite all evidence.",
            "No baseline or claim of improved betting quality is inferred from this retrospective.",
            "The raw outcome hit_rate includes clock-incomplete records; causal_hit_rate, Brier score and log loss use only strict causal observations.",
            "Native provider/event IDs bind outcomes; missing retained participant roles are shown as coverage gaps, not reconstructed or described as participant-verified.",
        ],
    }
    if not path.is_file() or ids == set():
        return report
    errors = []
    def error(kind: str, record_id: str, reason: str) -> None:
        report["integrity_error_count"] += 1
        if len(errors) < 200:
            errors.append(dict(kind=kind, record_id=record_id, reason=reason))
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        deadline = _query_clock() + query_timeout
        timed_out = False
        def progress() -> int:
            nonlocal timed_out
            timed_out = timed_out or _query_clock() >= deadline
            return int(timed_out)
        def check_deadline() -> None:
            # SQLite only invokes the VM callback after enough instructions.
            # Short statements (including an empty indexed window) may never
            # reach that interval; the whole read phase still has one budget.
            if progress():
                raise TimeoutError("bounded read-only selection query exceeded its time budget")
        conn.set_progress_handler(progress, 1000)
        try:
            check_deadline()
            if not _TABLES.issubset({r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}):
                raise ValueError("incomplete forecast evidence database")
            check_deadline()
            raw = _window_forecasts(conn, lower, upper, cutoff)
            check_deadline()
            if ids is not None:
                raw = [row for row in raw if row["forecast_id"] in ids]
            runs = {r["run_id"]: r for r in _fetch_related(conn, "forecast_runs", "run_id", sorted({r["run_id"] for r in raw}))}
            check_deadline()
            results = _fetch_related(conn, "forecast_results", "event_key", sorted({r["event_key"] for r in raw}))
            check_deadline()
            quotes = _fetch_related(conn, "forecast_quotes", "forecast_id", [r["forecast_id"] for r in raw])
            check_deadline()
        except sqlite3.OperationalError as exc:
            if timed_out:
                raise TimeoutError("bounded read-only selection query exceeded its time budget") from exc
            raise
        finally:
            conn.set_progress_handler(None, 0)
    report["decision_revisions_read"] = len(raw)
    result_index, quote_index, observations = defaultdict(list), defaultdict(list), defaultdict(list)
    invalid_quote_forecasts = set()
    for row in results:
        try:
            if _utc(row["observed_at"]) <= cutoff:
                result_index[(row["event_key"], row["market_key"], row["selection"])].append(row)
        except (ValueError, TypeError):
            error("result", row["result_id"], "invalid result observation clock")
    for row in quotes:
        try:
            value = _payload(row, "quote_id")
            _same_columns(row, value, ("forecast_id", "kind", "bookmaker_id", "observed_at", "fetched_at", "odds"))
            if row["kind"] not in {"entry", "closing"}:
                raise ValueError("unknown quote observation kind")
            if row["kind"] == "entry":
                quote_index[row["forecast_id"]].append(row)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            invalid_quote_forecasts.add(row["forecast_id"])
            error("quote", row["quote_id"], str(exc))
    for row in raw:
        try:
            if row["run_id"] not in runs:
                raise ValueError("missing frozen forecast run")
            forecast = _forecast(row, runs[row["run_id"]])
            if _utc(forecast["recorded_at"]) > cutoff:
                continue
            observations[(*forecast["native_event"], forecast["market_key"], forecast["selection"])].append(forecast)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            error("forecast", row["forecast_id"], str(exc))
    exclusions = Counter()
    selected = []
    for identity, revisions in sorted(observations.items()):
        revisions.sort(key=lambda r: (_utc(r["decision_at"]), r["forecast_id"]))
        bindings = {_role_binding(r) for r in revisions} - {None}
        identity_conflict = len({r["event_key"] for r in revisions}) > 1 or len(bindings) > 1
        if identity_conflict:
            error("forecast", revisions[0]["forecast_id"], "native event has conflicting frozen event keys or participant roles")
        terminal = []
        result_invalid = identity_conflict
        for row in result_index[(revisions[0]["event_key"], revisions[0]["market_key"], revisions[0]["selection"])]:
            try:
                terminal.append(_result(row, revisions[0], cutoff))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                result_invalid = True
                error("result", row["result_id"], str(exc))
        outcomes = {r["outcome"] for r in terminal}
        starts = {r["effective_start"] for r in terminal}
        if len(outcomes) > 1 or len(starts) > 1:
            result_invalid = True
            error("result", revisions[0]["event_key"], "conflicting terminal outcomes or actual kickoffs")
        start = next(iter(starts)) if len(starts) == 1 and not result_invalid else _utc(revisions[0]["starts_at"])
        if not lower <= start < upper:
            continue
        causal = []
        for forecast in revisions:
            reason = _causal(forecast, start)
            if reason is None and not identity_conflict:
                causal.append(forecast)
        chosen = causal[0] if causal else revisions[0]
        reason = "native_identity_conflict" if identity_conflict else _causal(chosen, start)
        if reason:
            exclusions[reason] += 1
        outcome = next(iter(outcomes)) if len(outcomes) == 1 and not result_invalid else "UNRESOLVED"
        if terminal and min(_utc(r["observed_at"]) for r in terminal) <= _utc(chosen["decision_at"]):
            outcome = "UNRESOLVED"
            error("result", chosen["forecast_id"], "terminal result was already observed at decision")
        entries = []
        quote_invalid = chosen["forecast_id"] in invalid_quote_forecasts
        for row in quote_index[chosen["forecast_id"]]:
            try:
                entries.append(_quote(row, chosen, start))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                quote_invalid = True
                error("quote", row["quote_id"], str(exc))
        # Selection is predefined by clock and stable bookmaker identity, never
        # by the realized outcome, best price, value gate or later revision.
        entries.sort(key=lambda q: (-_utc(q["observed_at"]).timestamp(), -_utc(q["fetched_at"]).timestamp(), q["bookmaker_id"], q["quote_id"]))
        quote = entries[0] if entries else None
        status = "invalid" if quote_invalid else "missing" if quote is None else "stale" if not quote["fresh"] else "below_floor" if quote["odds"] < MINIMUM_RECOMMENDED_DECIMAL_ODDS else "fresh"
        units = None
        if reason is None and status == "fresh" and outcome in {"WIN", "LOSS"}:
            units = quote["odds"] - 1 if outcome == "WIN" else -1.0
        selected.append({
            "forecast_id": chosen["forecast_id"], "event_key": chosen["event_key"], "native_event": list(identity[:3]),
            "sport": chosen["sport"], "market_key": chosen["market_key"], "selection": chosen["selection"],
            "model_version": chosen["model_version"], "policy_version": chosen["policy_version"],
            "day": start.astimezone(zone).date().isoformat(), "effective_start": start.isoformat(),
            "decision_at": chosen["decision_at"], "probability": chosen["probability"], "outcome": outcome,
            "causal": reason is None, "clock_exclusion": reason, "revision_count": len(revisions),
            "role_binding_status": "complete" if _role_binding(chosen) is not None else "missing",
            "quote_status": status, "entry_odds": quote["odds"] if quote else None,
            "entry_quote_id": quote["quote_id"] if quote else None,
            "hypothetical_return_units": units,
        })
    selected.sort(key=lambda r: (r["effective_start"], r["sport"], r["event_key"], r["market_key"], r["selection"]))
    report["selections"] = selected
    report["summary"] = _summary(selected, stake)
    report["duplicate_revisions_collapsed"] = sum(r["revision_count"] - 1 for r in selected)
    report["clock_exclusions"] = dict(exclusions)
    report["integrity_errors"] = errors
    groups, days = defaultdict(list), defaultdict(list)
    for row in selected:
        groups[(row["sport"], row["market_key"], row["model_version"], row["policy_version"])].append(row)
        days[row["day"]].append(row)
    report["groups"] = [dict(zip(("sport", "market_key", "model_version", "policy_version"), key), **_summary(rows, stake)) for key, rows in sorted(groups.items())]
    report["daily"] = [dict(day=key, **_summary(rows, stake)) for key, rows in sorted(days.items())]
    return report
