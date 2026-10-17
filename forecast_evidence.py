"""Prospective forecast evidence, independent of user accounts and bankrolls.

All records append observations. Reports describe model accuracy and hypothetical
unit returns at proven quotes; they never turn an observed result into a placed
bet, synthesize no-vig prices, or claim that a small sample proves profit.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Mapping

from market_consensus import (
    MarketConsensus, WETTFINDER_FETCH_MAX_AGE, quote_matches_candidate,
    wettfinder_reference_price_status, bounded_tennis_price_observations,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast_runs (
    run_id TEXT PRIMARY KEY, decision_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forecast_rows (
    forecast_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, event_key TEXT NOT NULL,
    sport TEXT NOT NULL, market_key TEXT NOT NULL, selection TEXT NOT NULL,
    model_version TEXT NOT NULL, policy_version TEXT NOT NULL,
    starts_at TEXT NOT NULL, decision_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS forecast_event_market ON forecast_rows(event_key,market_key,selection);
CREATE TABLE IF NOT EXISTS forecast_quotes (
    quote_id TEXT PRIMARY KEY, forecast_id TEXT NOT NULL, kind TEXT NOT NULL,
    bookmaker_id TEXT NOT NULL, observed_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL, odds REAL NOT NULL, executable INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forecast_results (
    result_id TEXT PRIMARY KEY, event_key TEXT NOT NULL, market_key TEXT NOT NULL,
    selection TEXT NOT NULL, outcome TEXT NOT NULL, observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS forecast_result_identity_time
ON forecast_results(event_key,market_key,selection,observed_at);
"""
_TABLES = {"forecast_runs", "forecast_rows", "forecast_quotes", "forecast_results"}
_SPORTS = {"fußball": "football", "fussball": "football", "football": "football", "tennis": "tennis", "e-sport": "esports", "esports": "esports", "basketball": "basketball", "eishockey": "ice_hockey", "ice_hockey": "ice_hockey", "cricket": "cricket"}
_IDENTITY_FIELDS = ("candidate_id", "fixture_id", "market_key", "sport", "source", "selection", "scheduled_start", "competitor_a", "competitor_b", "selected_competitor", "quote_provider_event_id", "provider_event_id", "fixture_source", "home_team", "away_team", "home_id", "away_id", "competitor_a_id", "competitor_b_id", "minimum_odds")
_SECRET_KEY = re.compile(r"api.?key|token|secret|password|authorization|cookie|account|balance|bankroll|stake", re.I)
_MAX_CURRENT_CLOSING_QUOTES = 200
_MAX_CLOSING_VERSION_BINDINGS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: object) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evidence timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: object) -> str:
    return _utc(value).isoformat()


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError(f"{name} must be nonempty bounded text")
    return value.strip()


def _fraction(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("forecast probability must be a finite fraction")
    return float(value)


def _sanitize(value: object, depth: int = 0) -> object:
    """Retain context facts, not unrelated account/credential/provider blobs."""
    if depth > 10:
        return None
    if isinstance(value, Mapping):
        return {str(k): _sanitize(v, depth+1) for k, v in value.items() if not _SECRET_KEY.search(str(k))}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v, depth+1) for v in value[:1000]]
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and re.search(r"(?:api.?key|token|secret|password)\s*[=:]|bearer\s+", value, re.I):
            return "[credential detail omitted]"
        return value[:2000] if isinstance(value, str) else value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} - {"sqlite_sequence"}
    if tables - _TABLES:
        conn.close()
        raise ValueError("forecast evidence requires its own database")
    conn.executescript(_SCHEMA)
    for table in sorted(_TABLES):
        for operation in ("UPDATE", "DELETE"):
            conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'forecast evidence is immutable'); END")
    conn.commit()
    return conn


def _normalize_row(row: Mapping, decision: datetime, default_model: str, policy: str) -> dict:
    start = _utc(row.get("scheduled_start") or row.get("starts_at"))
    if start <= decision:
        raise ValueError("event must start after forecast decision")
    probability = _fraction(row.get("probability", row.get("model_probability")))
    cautious_raw = row.get("conservative_probability", row.get("cautious_probability"))
    cautious = _fraction(cautious_raw) if cautious_raw is not None else None
    if cautious is not None and cautious > probability:
        raise ValueError("cautious heuristic cannot exceed model probability")
    sport = _SPORTS.get(str(row.get("sport") or "").casefold())
    if sport is None:
        raise ValueError("unsupported forecast sport")
    modeled_raw = row.get("modeled_at") or row.get("model_generated_at")
    cutoff_raw = row.get("input_cutoff_at")
    modeled = _utc(modeled_raw) if modeled_raw else None
    cutoff = _utc(cutoff_raw) if cutoff_raw else None
    if modeled is not None and modeled > decision or cutoff is not None and cutoff > decision:
        raise ValueError("forecast contains future model input")
    if modeled is not None and cutoff is not None and cutoff > modeled:
        raise ValueError("input cutoff follows model calculation")
    if row.get("context_checked_at") and _utc(row["context_checked_at"]) > decision:
        raise ValueError("context was checked after forecast decision")
    quote_identity = {field: row.get(field) for field in _IDENTITY_FIELDS}
    if sport == "esports" and "competition" in row:
        # The same team name can occur in several games. Keep this binding
        # for new E-sport prices without changing legacy/non-esport identities.
        quote_identity["competition"] = row.get("competition")
    return {
        "event_key": _text(row.get("event_identity") or row.get("event_key"), "event identity"),
        "sport": sport,
        "market_key": _text(row.get("market_key"), "market key"),
        "selection": _text(row.get("selection_key") or row.get("selection"), "selection"),
        "candidate_id": _text(row.get("candidate_id") or row.get("key"), "candidate identity"),
        "model_version": _text(row.get("model_version") or default_model, "model version"),
        "policy_version": _text(row.get("policy_version") or policy, "policy version"),
        "starts_at": start.isoformat(), "decision_at": decision.isoformat(),
        "modeled_at": modeled.isoformat() if modeled else None,
        "input_cutoff_at": cutoff.isoformat() if cutoff else None,
        "causal_provenance_complete": modeled is not None and cutoff is not None,
        "probability": probability, "cautious_heuristic": cautious,
        "context": _sanitize(row.get("context") or row.get("context_evidence") or {}),
        "market_definition": _sanitize(row.get("market_definition") or {}),
        "context_checked_at": _iso(row["context_checked_at"]) if row.get("context_checked_at") else None,
        "evidence_stage": str(row.get("evidence_stage") or "unknown"),
        "quote_identity": quote_identity,
    }


def _complete_tennis_market(forecast, quote, point, observations):
    """Bind both real prices from an already received native H2H response.

    No synthetic opposing forecast is created and no provider is requested.
    A book/update/fetch mismatch leaves the optional full-market proof absent.
    """
    identity = forecast["quote_identity"]
    if forecast["sport"] != "tennis" or forecast["market_key"] != "H2H":
        return None
    a, b = identity.get("competitor_a"), identity.get("competitor_b")
    if not all(isinstance(name, str) and name for name in (a, b)) or a == b:
        return None
    offered = {}
    for row in observations:
        if any(row.get(field) != identity.get(field) for field in
                ("fixture_source", "provider_event_id", "competitor_a", "competitor_b")):
            continue
        selected = row.get("selected_competitor")
        other = MarketConsensus.from_dict(row.get("reference_quote"))
        if (selected not in (a, b) or other is None or not quote_matches_candidate(other, row)
                or other.source != quote.source or other.provider_event_id != quote.provider_event_id
                or other.fetched_at != quote.fetched_at or other.scheduled_start != quote.scheduled_start):
            continue
        for price in other.points:
            if price.bookmaker_id == point.bookmaker_id and price.observed_at == point.observed_at:
                if selected in offered and offered[selected] != price.odds:
                    return None
                offered[selected] = price.odds
    if (set(offered) != {a, b} or offered.get(identity.get("selected_competitor")) != point.odds):
        return None
    return {"market_key": "H2H", "fixture_source": identity.get("fixture_source"),
        "provider_event_id": identity.get("provider_event_id"), "quote_provider_event_id": quote.provider_event_id,
        "scheduled_start": forecast["starts_at"], "competitors": [a, b],
        "outcomes": [{"selection": name, "odds": offered[name]} for name in (a, b)]}


def _quote_records(forecast_id: str, forecast: dict, raw: object, kind: str,
                   market_observations=()) -> list[tuple]:
    quote = MarketConsensus.from_dict(raw.to_dict() if isinstance(raw, MarketConsensus) else raw)
    if quote is None or not quote_matches_candidate(quote, forecast["quote_identity"]):
        raise ValueError("quote does not exactly match forecast event and selection")
    decision, start = _utc(forecast["decision_at"]), _utc(forecast["starts_at"])
    fetched = _utc(quote.fetched_at)
    if fetched > _now():
        raise ValueError("quote fetch cannot be in the future")
    if _utc(quote.scheduled_start) != start:
        raise ValueError("quote kickoff differs from forecast")
    if kind == "entry":
        if fetched > decision:
            raise ValueError("entry quote was fetched after decision")
        capture = _utc(forecast["recorded_at"])
    elif kind == "closing":
        if not decision < fetched < start or start-fetched > timedelta(hours=1):
            raise ValueError("closing quote must be fetched after decision within final hour")
        capture = fetched
    else:
        raise ValueError("quote kind must be entry or closing")
    status = wettfinder_reference_price_status(quote, forecast["quote_identity"].get("minimum_odds"), candidate=forecast["quote_identity"], now=capture)
    records = []
    for point in quote.points:
        observed = _utc(point.observed_at)
        if observed > fetched or observed > capture or observed >= start:
            raise ValueError("quote observation has invalid causal timestamp")
        if kind == "closing" and (observed <= decision or start-observed > timedelta(hours=1)):
            continue
        if not point.bookmaker_id:
            continue
        payload = {
            "forecast_id": forecast_id, "kind": kind, "bookmaker_id": point.bookmaker_id,
            "bookmaker": point.bookmaker, "observed_at": observed.isoformat(),
            "fetched_at": fetched.isoformat(), "odds": point.odds,
            "executable": (
                status.code == "PLAYABLE"
                and status.bookmaker_id == point.bookmaker_id
                and status.usable_odds == point.odds
                and status.observed_at == point.observed_at
            ),
            "source": quote.source, "provider_event_id": quote.provider_event_id,
            "fixture_id": quote.fixture_id, "market_key": quote.market_key,
            "selection": quote.value_name, "starts_at": start.isoformat(),
        }
        complete_market = _complete_tennis_market(forecast, quote, point, market_observations)
        if complete_market is not None:
            payload["complete_market"] = complete_market
        records.append((_hash(payload), forecast_id, kind, point.bookmaker_id, payload["observed_at"], payload["fetched_at"], point.odds, int(payload["executable"]), _json(payload)))
    return records


def _capture_current_closing_quotes(conn, normalized: list, recorded_at: datetime,
                                    price_observations=()) -> int:
    """Bind fresh, already fetched prices to earlier causal forecasts.

    No historical import or provider call is performed. The first causal
    revision receives a market benchmark, even without an EV-qualified
    entry. The first executable revision also receives CLV observations for the
    unchanged historical return cohort. Neither is a new selection gate.
    Rebinding the internal candidate revision ID never changes provider identity,
    bookmaker, price, native participants, event time or observation clocks.
    """
    before = conn.total_changes
    market_observations = bounded_tennis_price_observations(price_observations, now=recorded_at)
    checked = 0
    identity_fields = ("fixture_id", "provider_event_id", "fixture_source", "home_id", "away_id",
                       "competitor_a", "competitor_b", "competitor_a_id", "competitor_b_id", "selected_competitor")
    for current, raw in normalized:
        if raw is None:
            continue
        quote = MarketConsensus.from_dict(raw.to_dict() if isinstance(raw, MarketConsensus) else raw)
        if quote is None or not quote_matches_candidate(quote, current["quote_identity"]):
            continue
        fetched, start = _utc(quote.fetched_at), _utc(current["starts_at"])
        if (not fetched <= recorded_at < start or start-fetched > timedelta(hours=1)
                or recorded_at-fetched > WETTFINDER_FETCH_MAX_AGE):
            continue
        checked += 1
        if checked > _MAX_CURRENT_CLOSING_QUOTES:
            break
        earlier = conn.execute(
            "WITH eligible AS (SELECT f.*, EXISTS (SELECT 1 FROM forecast_quotes q "
            "WHERE q.forecast_id=f.forecast_id AND q.kind='entry' AND q.executable=1) AS has_entry "
            "FROM forecast_rows f "
            "WHERE f.event_key=? AND f.sport=? AND f.market_key=? AND f.selection=? "
            "AND f.starts_at=? AND f.decision_at<? "
            "AND json_extract(f.payload_json,'$.causal_provenance_complete')=1), ranked AS ("
            "SELECT forecast_id,payload_json,has_entry, "
            "ROW_NUMBER() OVER (PARTITION BY model_version,policy_version "
            "ORDER BY decision_at,forecast_id) AS causal_order, "
            "ROW_NUMBER() OVER (PARTITION BY model_version,policy_version,has_entry "
            "ORDER BY decision_at,forecast_id) AS entry_order FROM eligible) "
            "SELECT forecast_id,payload_json FROM ranked "
            "WHERE causal_order=1 OR (has_entry=1 AND entry_order=1) "
            "ORDER BY forecast_id LIMIT ?",
            (current["event_key"], current["sport"], current["market_key"], current["selection"],
             current["starts_at"], fetched.isoformat(), _MAX_CLOSING_VERSION_BINDINGS),
        ).fetchall()
        for forecast_id, payload in earlier:
            forecast = json.loads(payload)
            if any(forecast["quote_identity"].get(key) != current["quote_identity"].get(key)
                   for key in identity_fields):
                continue
            bound = {**quote.to_dict(), "candidate_id": forecast["quote_identity"]["candidate_id"]}
            try:
                records = _quote_records(forecast_id, forecast, bound, "closing", market_observations)
            except (TypeError, ValueError):
                continue
            conn.executemany("INSERT OR IGNORE INTO forecast_quotes VALUES(?,?,?,?,?,?,?,?,?)", records)
    return conn.total_changes-before


def record_forecast_run(document: Mapping, db_path: str | Path, model_version: str) -> dict:
    """Append every valid pre-match row, reporting rejected provenance explicitly.

    Missing model clocks are recorded, not invented. Those rows are counted as
    coverage gaps and excluded from the strict causal accuracy/return subset.
    """
    decision = _utc(document.get("decision_at") or document.get("generated_at"))
    recorded_at = _now()
    if decision > recorded_at:
        raise ValueError("forecast decision cannot be in the future")
    model = _text(model_version, "model version")
    policy = _text(document.get("selection_policy_version") or document.get("betting_policy_version"), "policy version")
    rows = document.get("model_candidates")
    if not isinstance(rows, (list, tuple)):
        raise ValueError("model_candidates must be the complete candidate sequence")
    normalized, rejected = [], []
    for index, row in enumerate(rows):
        try:
            if not isinstance(row, Mapping):
                raise ValueError("forecast row must be a mapping")
            normalized_row = _normalize_row(row, decision, model, policy)
            if _utc(normalized_row["starts_at"]) <= recorded_at:
                raise ValueError("forecast was not recorded prospectively before start")
            normalized_row["recorded_at"] = recorded_at.isoformat()
            normalized.append((normalized_row, row.get("reference_quote")))
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "reason": str(exc)})
    run = {"decision_at": decision.isoformat(), "recorded_at": recorded_at.isoformat(), "model_version": model, "policy_version": policy, "forecast_digests": sorted(_hash({k:v for k,v in r.items() if k != "recorded_at"}) for r, _ in normalized), "rejected": rejected}
    run_id = _hash({k:v for k,v in run.items() if k != "recorded_at"})
    quote_rejected, ids = [], []
    closing_recorded = 0
    market_observations = bounded_tennis_price_observations(
        document.get("tennis_price_observations"), now=recorded_at)
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT payload_json FROM forecast_runs WHERE run_id=?", (run_id,)).fetchone()
        if existing:
            run = json.loads(existing[0])
            for row, _ in normalized:
                row["recorded_at"] = run["recorded_at"]
        conn.execute("INSERT OR IGNORE INTO forecast_runs VALUES(?,?,?)", (run_id, decision.isoformat(), _json(run)))
        for row, quote in normalized:
            forecast_id = _hash({"run_id": run_id, "forecast": row})
            ids.append(forecast_id)
            conn.execute("INSERT OR IGNORE INTO forecast_rows VALUES(?,?,?,?,?,?,?,?,?,?,?)", (forecast_id, run_id, row["event_key"], row["sport"], row["market_key"], row["selection"], row["model_version"], row["policy_version"], row["starts_at"], row["decision_at"], _json(row)))
            if quote is not None:
                try:
                    records = _quote_records(forecast_id, row, quote, "entry", market_observations)
                    conn.executemany("INSERT OR IGNORE INTO forecast_quotes VALUES(?,?,?,?,?,?,?,?,?)", records)
                except (TypeError, ValueError) as exc:
                    quote_rejected.append({"forecast_id": forecast_id, "reason": str(exc)})
        closing_recorded = _capture_current_closing_quotes(conn, normalized, recorded_at, market_observations)
    return {"run_id": run_id, "recorded": len(set(ids)), "forecast_ids": ids, "rejected": rejected,
            "quotes_rejected": quote_rejected, "closing_quotes_recorded": closing_recorded}


def append_quote_observation(forecast_id: str, quote: object, *, kind: str, db_path: str | Path) -> int:
    with closing(_connect(db_path)) as conn, conn:
        stored = conn.execute("SELECT payload_json FROM forecast_rows WHERE forecast_id=?", (forecast_id,)).fetchone()
        if stored is None:
            raise ValueError("unknown forecast identity")
        records = _quote_records(forecast_id, json.loads(stored[0]), quote, kind)
        before = conn.total_changes
        conn.executemany("INSERT OR IGNORE INTO forecast_quotes VALUES(?,?,?,?,?,?,?,?,?)", records)
        return conn.total_changes-before


def record_current_closing_quotes(document: Mapping, *, db_path: str | Path, model_version: str) -> dict:
    """Record already fetched closing prices, never a new model/run or entry.

    Price-only refreshes keep the original model decision and all probabilities.
    They previously updated the cards without reaching the closing-price owner.
    Missing evidence is not initialized by this optional observation step.
    """
    if not Path(db_path).is_file():
        return {"status": "no_existing_forecasts", "recorded": 0, "rejected": 0}
    decision = _utc(document.get("decision_at") or document.get("generated_at"))
    recorded_at = _now()
    if decision > recorded_at:
        raise ValueError("forecast decision cannot be in the future")
    model = _text(model_version, "model version")
    policy = _text(document.get("selection_policy_version") or document.get("betting_policy_version"), "policy version")
    rows = document.get("model_candidates")
    if not isinstance(rows, (list, tuple)):
        raise ValueError("model_candidates must be the complete candidate sequence")
    normalized, rejected = [], 0
    for row in rows:
        if not isinstance(row, Mapping) or row.get("reference_quote") is None:
            continue
        try:
            normalized.append((_normalize_row(row, decision, model, policy), row["reference_quote"]))
        except (TypeError, ValueError):
            rejected += 1
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        count = _capture_current_closing_quotes(conn, normalized, recorded_at,
            price_observations=document.get('tennis_price_observations'))
    return {"status": "completed", "recorded": count, "rejected": rejected}


def append_result(event_key: str, market_key: str, selection: str, outcome: str | bool, *, observed_at: datetime | str, provenance: Mapping, db_path: str | Path) -> str:
    """Append an adapter-verified event/market result, never a manual pick result.

    Callers must use existing canonical settlement rules and provide the exact
    provider-record hash. This API performs no provider request or settlement
    inference from elapsed time, odds, account transactions or displayed tips.
    """
    outcome = ("WIN" if outcome else "LOSS") if isinstance(outcome, bool) else outcome
    if outcome not in {"WIN", "LOSS", "VOID"}:
        raise ValueError("result must be WIN, LOSS or VOID")
    identity = tuple(_text(v, k) for v, k in ((event_key,"event key"),(market_key,"market key"),(selection,"selection")))
    observed = _utc(observed_at)
    if observed > _now():
        raise ValueError("result observation cannot be in the future")
    proof = {k: _text(provenance.get(k), k) for k in ("provider", "provider_event_id", "source_record_id", "payload_sha256", "settlement_rule")}
    if proof["provider"].casefold() not in {"api-football", "espn", "sofascore", "pandascore", "nhl", "euroleague", "cricbuzz", "cricketdata"} or not re.fullmatch(r"[0-9a-f]{64}", proof["payload_sha256"]):
        raise ValueError("result requires a recognized provider and canonical record hash")
    if any(token in proof["settlement_rule"].casefold() for token in ("manual", "synthetic", "guess")):
        raise ValueError("manual or inferred results are not evidence")
    actual_start = None
    if 'actual_starts_at' in provenance:
        if proof['provider'].casefold() != 'api-football':
            raise ValueError('rescheduled kickoff requires its owning football adapter')
        actual_start = _utc(provenance['actual_starts_at'])
        if actual_start > observed:
            raise ValueError('actual kickoff follows the result observation')
        proof['actual_starts_at'] = actual_start.isoformat()
    payload = {"event_key": identity[0], "market_key": identity[1], "selection": identity[2], "outcome": outcome, "observed_at": observed.isoformat(), "provenance": proof}
    result_id = _hash(payload)
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        forecasts = conn.execute("SELECT starts_at,payload_json FROM forecast_rows WHERE event_key=? AND market_key=? AND selection=?", identity).fetchall()
        if not forecasts:
            raise ValueError("result has no matching prospective forecast")
        if outcome != "VOID" and actual_start is None and any(observed < _utc(row[0]) for row in forecasts):
            raise ValueError("played result must be observed after event start")
        for _, raw in forecasts:
            quoted_identity = json.loads(raw)["quote_identity"]
            provider_id = quoted_identity.get("provider_event_id")
            if identity[0].startswith("football:"):
                provider_id = provider_id or quoted_identity.get("fixture_id")
            if provider_id is not None and str(provider_id) != proof["provider_event_id"]:
                raise ValueError("result provider event differs from forecast")
            provider_source = str(quoted_identity.get("fixture_source") or "").casefold()
            if not provider_source and identity[0].startswith("football:"):
                provider_source = "api-football"
            if provider_source and provider_source != proof["provider"].casefold():
                raise ValueError("result provider differs from forecast source")
        prior = conn.execute("SELECT outcome FROM forecast_results WHERE event_key=? AND market_key=? AND selection=?", identity).fetchall()
        if any(row[0] != outcome for row in prior):
            raise ValueError("contradictory result requires a separately reviewed correction")
        conn.execute("INSERT OR IGNORE INTO forecast_results VALUES(?,?,?,?,?,?,?)", (result_id, *identity, outcome, observed.isoformat(), _json(payload)))
    return result_id


def unresolved_forecasts(db_path: str | Path, *, as_of: datetime | str | None = None) -> list[dict]:
    """Read one started unresolved event/market/selection without DB mutation.

    Prefer its first causally timestamped decision, falling back to its first
    observation for coverage-only outcomes. This is an adapter queue, not a
    statement that an event is completed merely because its kickoff passed.
    The provider adapter must establish a real final result and exact identity.
    """
    path = Path(db_path)
    if not path.is_file():
        return []
    cutoff = _utc(as_of or _now()).isoformat()
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not _TABLES.issubset(tables):
            raise ValueError("incomplete forecast evidence database")
        rows = conn.execute(
            "SELECT f.* FROM forecast_rows f WHERE f.starts_at<=? AND f.decision_at<=? "
            "AND NOT EXISTS (SELECT 1 FROM forecast_results r WHERE r.event_key=f.event_key "
            "AND r.market_key=f.market_key AND r.selection=f.selection AND r.observed_at<=?) "
            "ORDER BY f.decision_at,f.forecast_id", (cutoff, cutoff, cutoff),
        ).fetchall()
    identities = {}
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload["forecast_id"] = row["forecast_id"]
        key = (row["event_key"], row["market_key"], row["selection"])
        previous = identities.get(key)
        if previous is None or (not previous["causal_provenance_complete"] and payload["causal_provenance_complete"]):
            identities[key] = payload
    return list(identities.values())


def build_quality_report(db_path: str | Path, *, as_of: datetime | str | None = None) -> dict:
    """Read grouped prequential accuracy, coverage and explicitly hypothetical returns."""
    path = Path(db_path)
    cutoff = _utc(as_of or datetime.now(timezone.utc))
    report = {"as_of": cutoff.isoformat(), "database_present": path.is_file(), "groups": [], "scoring_policy": "First causal decision per event/selection/model/policy; returns use first executable causal decision independently.", "limitations": ["Different selections from the same event remain correlated; unique event counts are shown.", "Observed quote returns are hypothetical equal-unit returns, not actual wagers or profit proof.", "CLV is the raw same-book odds ratio; no no-vig market probability is inferred.", "Missing input clocks are excluded from strict prequential scoring."]}
    report['sport_coverage'] = []
    report['limitations'].append('Verified actual kickoff overrides the planned start for causal scoring and prices; frozen forecasts stay unchanged.')
    if not path.is_file():
        return report

    class Mean:
        """Bounded compensated totals instead of retaining every scored sample."""

        def __init__(self):
            self.n = 0
            self.total = 0.0
            self.correction = 0.0

        def add(self, value):
            combined = self.total + value
            if abs(self.total) >= abs(value):
                self.correction += (self.total - combined) + value
            else:
                self.correction += (value - combined) + self.total
            self.total = combined
            self.n += 1

        def value(self):
            total = self.total
            if self.correction and math.isfinite(self.correction):
                total += self.correction
            return total / self.n if self.n else None

    groups, sport_rows = {}, {}
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not _TABLES.issubset(tables):
            raise ValueError("incomplete forecast evidence database")
        results = {}
        for row in conn.execute("SELECT event_key,market_key,selection,outcome,observed_at,payload_json FROM forecast_results WHERE observed_at<=? ORDER BY observed_at,result_id", (cutoff.isoformat(),)):
            key = (row["event_key"], row["market_key"], row["selection"])
            results.setdefault(key, dict(row))
        quotes = defaultdict(list)
        for row in conn.execute("SELECT quote_id,forecast_id,kind,bookmaker_id,observed_at,fetched_at,odds,executable FROM forecast_quotes WHERE fetched_at<=? ORDER BY observed_at,quote_id", (cutoff.isoformat(),)):
            quotes[row["forecast_id"]].append(dict(row))
        # Keep the cursor and all caches in this one read-only snapshot. Only
        # the current forecast payload is materialized; retained state scales
        # with distinct identities/groups and quote/result observations, not
        # with all forecast revisions or their context payloads.
        for record in conn.execute("SELECT forecast_id,event_key,sport,market_key,selection,model_version,policy_version,starts_at,decision_at,payload_json FROM forecast_rows WHERE decision_at<=? ORDER BY decision_at,forecast_id", (cutoff.isoformat(),)):
            key = (record["sport"],record["market_key"],record["model_version"],record["policy_version"])
            if key not in groups:
                summary = dict(zip(("sport","market","model_version","policy_version"),key))
                summary.update({"decision_revisions":0, "unique_events":0, "causal_forecasts":0, "unknown_input_clocks":0, "wins":0, "losses":0, "voids":0, "unresolved":0, "scored":0, "entry_quote_coverage":0, "executable_entry_coverage":0})
                groups[key] = dict(summary=summary, events=set(), scored=set(), outcomes=set(), executable=set(),
                                   losses=Mean(), log_losses=Mean(), returns=Mean(), clvs=Mean(),
                                   bins=[{"lower":i/10,"upper":(i+1)/10,"n":0,"sum_p":0.0,"wins":0} for i in range(10)])
            group = groups[key]
            summary = group["summary"]
            summary["decision_revisions"] += 1
            group["events"].add(record["event_key"])
            scored_identities, outcome_identities, executable_identities = group["scored"], group["outcomes"], group["executable"]
            losses, log_losses, returns, clvs, bins = group["losses"], group["log_losses"], group["returns"], group["clvs"], group["bins"]
            forecast = json.loads(record["payload_json"])
            identity = (record["event_key"],record["market_key"],record["selection"])
            result = results.get(identity)
            sport = sport_rows.setdefault(record["sport"], dict(revisions=0, events=set(), resolved=set()))
            sport["revisions"] += 1
            sport["events"].add(record["event_key"])
            if result:
                sport["resolved"].add(record["event_key"])
            proof = json.loads(result['payload_json']).get('provenance', {}) if result else {}
            effective_start = _utc(proof.get('actual_starts_at', record['starts_at']))
            causal = forecast["causal_provenance_complete"]
            # A moved-earlier fixture cannot turn a post-start decision or price
            # into historical prematch evidence. Later rescheduling likewise
            # never rewrites the original forecast, only the terminal proof.
            causal = causal and _utc(record['decision_at']) < effective_start and _utc(forecast['recorded_at']) < effective_start
            summary["causal_forecasts" if causal else "unknown_input_clocks"] += 1
            observed_quotes = quotes.get(record["forecast_id"], ())
            entries = [q for q in observed_quotes if q["kind"] == "entry"
                       and _utc(q['observed_at']) < effective_start and _utc(q['fetched_at']) < effective_start]
            executable = [q for q in entries if q["executable"]]
            summary["entry_quote_coverage"] += bool(entries)
            summary["executable_entry_coverage"] += bool(executable)
            outcome = result["outcome"] if result else None
            if identity not in outcome_identities:
                summary[{"WIN":"wins","LOSS":"losses","VOID":"voids"}.get(outcome,"unresolved")] += 1
                outcome_identities.add(identity)
            entry = max(executable,key=lambda q:(q["observed_at"],q["quote_id"])) if causal and executable and identity not in executable_identities else None
            if entry:
                executable_identities.add(identity)
                closings = [q for q in observed_quotes if q["kind"]=="closing" and q["bookmaker_id"]==entry["bookmaker_id"]
                            and _utc(q['observed_at']) <= effective_start and _utc(q['fetched_at']) <= effective_start]
                if closings:
                    close = max(closings,key=lambda q:(q["observed_at"],q["quote_id"]))
                    clvs.add(entry["odds"]/close["odds"]-1)
                if outcome in {"WIN","LOSS"} and _utc(result["observed_at"]) > _utc(record["decision_at"]):
                    returns.add(entry["odds"]*int(outcome=="WIN")-1)
            if identity in scored_identities:
                continue
            if causal:
                scored_identities.add(identity)
            if not causal or outcome not in {"WIN","LOSS"} or _utc(result["observed_at"]) <= _utc(record["decision_at"]):
                continue
            p, y = forecast["probability"], int(outcome=="WIN")
            losses.add((p-y)**2)
            clipped = max(1e-15,min(1-1e-15,p))
            log_losses.add(-(y*math.log(clipped)+(1-y)*math.log(1-clipped)))
            cell = bins[min(9,int(p*10))]
            cell["n"] += 1; cell["sum_p"] += p; cell["wins"] += y
    # Do not sum per-market counts into a misleading sample size. All markets,
    # repeated runs and policy revisions of the same fixture remain one event.
    for sport, rows in sorted(sport_rows.items()):
        report['sport_coverage'].append(dict(sport=sport, forecast_revisions=rows["revisions"],
            unique_events=len(rows["events"]), events_with_any_result=len(rows["resolved"]),
            events_without_results=len(rows["events"]-rows["resolved"])))
    for key, group in sorted(groups.items()):
        summary = group["summary"]
        losses, log_losses, returns, clvs, bins = group["losses"], group["log_losses"], group["returns"], group["clvs"], group["bins"]
        summary["unique_events"] = len(group["events"])
        summary.update({"scored":losses.n, "brier_score":losses.value(), "log_loss":log_losses.value(), "hypothetical_executable_samples":returns.n, "hypothetical_unit_roi":returns.value(), "same_book_raw_clv_samples":clvs.n, "same_book_raw_clv":clvs.value(), "calibration_bins":[{"lower":b["lower"],"upper":b["upper"],"n":b["n"],"mean_probability":b["sum_p"]/b["n"] if b["n"] else None,"observed_rate":b["wins"]/b["n"] if b["n"] else None} for b in bins]})
        summary["unique_event_selections"] = len(group["outcomes"])
        summary["first_causal_observations"] = len(group["scored"])
        summary["quote_coverage_unit"] = "decision revisions"
        report["groups"].append(summary)
    return report
