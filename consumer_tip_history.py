"""Compact prospective history of selections actually published to a UI surface.

This is not a bet ledger and never stores accounts, stakes, full context payloads,
or retrospective reconstructions. Callers must pass the final displayed rows,
not the internal model pool. Publication IDs ignore the observation clock, so a
browser rerun of the same selection does not duplicate its history.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from itertools import islice
import json
import math
from pathlib import Path
import re
import sqlite3

from market_consensus import (
    MarketConsensus, WETTFINDER_FETCH_MAX_AGE, WETTFINDER_QUOTE_MAX_AGE,
    quote_matches_candidate,
)
from selection_coherence import consumer_event_identity


SCHEMA_VERSION = 1
EVENT_LEAD_SURFACES = {"wettfinder_default_inventory": "wettfinder_default_event_leads",
                       "wettfinder_automatic": "wettfinder_automatic_event_leads"}
LEAD_MANIFEST_VERSION = 2  # JSON only; SQLite tables and immutable v1 receipts are unchanged.
MAX_VISIBLE_LEADS = 20
# One immutable first witness per sport/native event on each surface. The
# sparse expression index has no entries for legacy or base inventories.
_LEAD_INDEX = """CREATE UNIQUE INDEX IF NOT EXISTS consumer_tip_first_lead
ON consumer_tip_publications(surface, json_extract(payload_json,'$.first_lead_event'))
WHERE json_extract(payload_json,'$.first_lead_event') IS NOT NULL"""
MAX_PUBLICATION_ROWS = 1000
MAX_TIP_BYTES = 8192
_TABLES = {"consumer_tip_publications", "consumer_tips"}
_SECRET = re.compile(r"(?:api.?key|token|secret|password)\s*[=:]|bearer\s+", re.I)
_SPORTS = {
    "fußball": "football", "fussball": "football", "football": "football",
    "soccer": "football", "tennis": "tennis", "basketball": "basketball",
    "eishockey": "ice_hockey", "ice_hockey": "ice_hockey", "hockey": "ice_hockey",
    "ice hockey": "ice_hockey", "e-sport": "esports", "esports": "esports",
    "cricket": "cricket",
}
_NAMES = ("home_team", "away_team", "competitor_a", "competitor_b", "selected_competitor")
_IDS = ("fixture_id", "provider_event_id", "quote_provider_event_id", "fixture_source", "home_team_id",
        "away_team_id", "home_id", "away_id", "competitor_a_id", "competitor_b_id")
_CREATE = (
    "CREATE TABLE consumer_tip_publications (publication_id TEXT PRIMARY KEY, "
    "surface TEXT NOT NULL, source_run_id TEXT, policy_version TEXT, "
    "first_observed_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
    "CREATE TABLE consumer_tips (publication_id TEXT NOT NULL, position INTEGER NOT NULL, "
    "tip_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(publication_id,position), "
    "FOREIGN KEY(publication_id) REFERENCES consumer_tip_publications(publication_id))",
)
_COLUMNS = {
    "consumer_tip_publications": [
        ("publication_id", "TEXT", 0, 1), ("surface", "TEXT", 1, 0),
        ("source_run_id", "TEXT", 0, 0), ("policy_version", "TEXT", 0, 0),
        ("first_observed_at", "TEXT", 1, 0), ("payload_json", "TEXT", 1, 0),
    ],
    "consumer_tips": [
        ("publication_id", "TEXT", 1, 1), ("position", "INTEGER", 1, 2),
        ("tip_id", "TEXT", 1, 0), ("payload_json", "TEXT", 1, 0),
    ],
}


def _now():
    return datetime.now(timezone.utc)


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invalid_clock")
    return value.astimezone(timezone.utc)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _text(value, *, optional=False, limit=256):
    if optional and value is None:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 for char in value) or _SECRET.search(value)):
        raise ValueError("invalid_text")
    return value.strip()


def _mapping(row):
    if isinstance(row, Mapping):
        return row
    try:
        return vars(row)
    except TypeError as exc:
        raise ValueError("invalid_row") from exc


def _probability(value):
    if (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("invalid_probability")
    return float(value)


def _quote(row, identity, as_of, start):
    raw = row.get("reference_quote")
    if raw is None:
        return {"status": "missing"}
    if isinstance(raw, MarketConsensus):
        raw = raw.to_dict()
    quote = MarketConsensus.from_dict(raw)
    if quote is None:
        return {"status": "invalid"}
    if not quote_matches_candidate(quote, identity):
        return {"status": "identity_mismatch"}
    try:
        fetched = _utc(quote.fetched_at)
        # Matching helpers allow some schedule drift for UI presentation. The
        # retrospective history requires the exact stored kickoff instead.
        if _utc(quote.scheduled_start) != start:
            return {"status": "schedule_mismatch"}
        if fetched > as_of or fetched >= start:
            return {"status": "future"}
        valid, fresh = [], []
        for point in quote.points:
            if not point.bookmaker_id:
                continue
            observed = _utc(point.observed_at)
            if observed > fetched or observed >= start:
                continue
            valid.append(point)
            if (as_of-fetched <= WETTFINDER_FETCH_MAX_AGE
                    and as_of-observed <= WETTFINDER_QUOTE_MAX_AGE):
                fresh.append(point)
        if not valid:
            return {"status": "unverified_clock"}
        point = max(fresh or valid, key=lambda item: (item.odds, str(item.bookmaker_id)))
        # Exactly one real point is retained, not a synthetic consensus price.
        return {
            "status": "observed" if fresh else "stale", "odds": point.odds,
            "bookmaker_id": _text(str(point.bookmaker_id), limit=128),
            "observed_at": _utc(point.observed_at).isoformat(),
            "fetched_at": fetched.isoformat(), "source": _text(quote.source),
            "provider_event_id": _text(quote.provider_event_id, optional=True),
            "fixture_id": quote.fixture_id, "market_key": _text(quote.market_key),
            "bet_name": _text(quote.bet_name), "selection": _text(quote.value_name),
            "starts_at": start.isoformat(),
        }
    except (ValueError, TypeError, OverflowError):
        return {"status": "invalid"}


def normalize_publication_tip(row, *, as_of):
    """Project one final displayed selection onto the bounded public schema.

    Missing model/input clocks stay null; they are never replaced by the current
    time. A supplied forecast_id is an optional join hint, not proof of a match.
    """
    row, decision = _mapping(row), _utc(as_of)
    start = _utc(row.get("scheduled_start") or row.get("starts_at"))
    if start <= decision:
        raise ValueError("event_already_started")
    sport = _SPORTS.get(str(row.get("sport") or "").strip().casefold())
    if sport is None:
        raise ValueError("unsupported_sport")
    event = row.get("event_key") or row.get("event_identity") or row.get("event_id")
    if not event:
        event = consumer_event_identity(row)
        if event.startswith("unresolved:"):
            raise ValueError("unresolved_identity")
    candidate = row.get("candidate_id") or row.get("key") or row.get("signal_key")
    payload = {
        "event_key": _text(event, limit=512), "sport": sport,
        "candidate_id": _text(candidate), "market_key": _text(row.get("market_key")),
        "selection": _text(row.get("selection_key") or row.get("selected_competitor") or row.get("selection")),
        "starts_at": start.isoformat(),
        "probability": _probability(row.get("probability", row.get("model_probability"))),
        "model_version": _text(row.get("model_version"), optional=True),
        "policy_version": _text(row.get("policy_version"), optional=True),
        "modeled_at": None, "input_cutoff_at": None,
        "featured_role": _text(row.get("featured_role"), optional=True, limit=64),
    }
    for name in ("modeled_at", "input_cutoff_at"):
        if row.get(name) is not None:
            clock = _utc(row[name])
            if clock > decision:
                raise ValueError("future_model_input")
            payload[name] = clock.isoformat()
    if (payload["modeled_at"] is not None and payload["input_cutoff_at"] is not None
            and _utc(payload["input_cutoff_at"]) > _utc(payload["modeled_at"])):
        raise ValueError("input_after_model")
    for name in _NAMES:
        if row.get(name) is not None:
            payload[name] = _text(row[name])
    for name in _IDS:
        value = row.get(name)
        if value is None:
            continue
        if name == "fixture_id" and (type(value) is not int or value <= 0):
            raise ValueError("invalid_native_identity")
        if type(value) is int and value > 0:
            payload[name] = value
        elif isinstance(value, str):
            payload[name] = _text(value, limit=128)
        else:
            raise ValueError("invalid_native_identity")
    for left, right in (("home_team", "away_team"), ("competitor_a", "competitor_b")):
        if left in payload and right in payload and payload[left].casefold() == payload[right].casefold():
            raise ValueError("identical_participants")
    for alias, native in (("home_team_id", "home_id"), ("away_team_id", "away_id")):
        if (alias in payload and native in payload
                and str(payload[alias]) != str(payload[native])):
            raise ValueError("conflicting_participant_aliases")
    home = payload.get("home_team_id", payload.get("home_id"))
    away = payload.get("away_team_id", payload.get("away_id"))
    if home is not None and away is not None and str(home) == str(away):
        raise ValueError("identical_participant_ids")
    if ("competitor_a_id" in payload and "competitor_b_id" in payload
            and str(payload["competitor_a_id"]) == str(payload["competitor_b_id"])):
        raise ValueError("identical_participant_ids")
    if (payload.get("selected_competitor") is not None
            and all(name in payload for name in ("competitor_a", "competitor_b"))
            and payload["selected_competitor"] not in {payload["competitor_a"], payload["competitor_b"]}):
        raise ValueError("invalid_selected_competitor")
    football_identity = re.fullmatch(r"football:(\d+)", payload["event_key"])
    if (football_identity is not None and "fixture_id" in payload
            and int(football_identity[1]) != payload["fixture_id"]):
        raise ValueError("conflicting_event_identity")
    if row.get("forecast_id") is not None:
        if not isinstance(row["forecast_id"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["forecast_id"]):
            raise ValueError("invalid_forecast_id")
        payload["forecast_id"] = row["forecast_id"]
    if row.get("snapshot_id") is not None:
        payload["snapshot_id"] = _text(row["snapshot_id"], limit=128)
    if type(row.get("context_effect_applied")) is bool:
        payload["context_effect_applied"] = row["context_effect_applied"]
    identity = dict(row)
    identity.update(candidate_id=payload["candidate_id"], market_key=payload["market_key"],
                    scheduled_start=payload["starts_at"])
    payload["quote"] = _quote(row, identity, decision, start)
    if len(_json(payload).encode("utf-8")) > MAX_TIP_BYTES:
        raise ValueError("tip_too_large")
    return payload


def _trigger_sql(table, operation):
    return (f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
            "BEGIN SELECT RAISE(ABORT,'consumer tip history is immutable'); END")


def _validate_schema(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables != _TABLES or conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        raise ValueError("unexpected_history_schema")
    for table in sorted(_TABLES):
        actual_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
        expected_sql = next(sql for sql in _CREATE if sql.startswith(f"CREATE TABLE {table} ("))
        if actual_sql != expected_sql:
            raise ValueError("unexpected_history_schema")
        columns = [(row[1], row[2], row[3], row[5]) for row in conn.execute(f"PRAGMA table_info({table})")]
        if columns != _COLUMNS[table]:
            raise ValueError("unexpected_history_schema")
        for operation in ("UPDATE", "DELETE"):
            trigger = conn.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                                   (f"{table}_no_{operation.lower()}",)).fetchone()
            if trigger is None or trigger[0] != _trigger_sql(table, operation):
                raise ValueError("unexpected_history_schema")


def _initialize(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables:
        for sql in _CREATE:
            conn.execute(sql)
        for table in sorted(_TABLES):
            for operation in ("UPDATE", "DELETE"):
                conn.execute(_trigger_sql(table, operation))
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    _validate_schema(conn)


def _validate_publication(conn, record, inventory_cache=None):
    publication_id, surface, run, policy, observed, raw = record
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict) or raw != _json(manifest)
            or manifest.get("first_observed_at") != observed
            or manifest.get("surface") != surface or manifest.get("source_run_id") != run
            or manifest.get("policy_version") != policy):
        raise ValueError("invalid_publication_hash")
    stable = {key: value for key, value in manifest.items() if key != "first_observed_at"}
    if _hash(stable) != publication_id:
        raise ValueError("invalid_publication_hash")
    clock = _utc(observed)
    stored = conn.execute("SELECT position,tip_id,payload_json FROM consumer_tips "
                          "WHERE publication_id=? ORDER BY position", (publication_id,)).fetchall()
    companion = surface in EVENT_LEAD_SURFACES.values()
    if len(stored) != (0 if companion else manifest.get("recorded_count")) or len(stored) > MAX_PUBLICATION_ROWS:
        raise ValueError("invalid_publication_count")
    tips = []
    for expected, (position, tip_id, payload_json) in enumerate(stored):
        tip = json.loads(payload_json)
        if (type(position) is not int or position != expected or not isinstance(tip, dict)
                or payload_json != _json(tip) or _hash(tip) != tip_id
                or _utc(tip.get("starts_at")) <= clock
                or len(payload_json.encode("utf-8")) > MAX_TIP_BYTES):
            raise ValueError("invalid_tip_hash")
        tips.append({**tip, "tip_id": tip_id, "position": position})
    if manifest.get("tip_ids") != [item[1] for item in stored] or (companion and manifest.get("recorded_count") != 0):
        raise ValueError("invalid_publication_manifest")
    version = manifest.get("schema_version")
    if type(version) is not int or version not in {SCHEMA_VERSION, LEAD_MANIFEST_VERSION}:
        raise ValueError("invalid_publication_version")
    if companion:
        source = next(base for base, child in EVENT_LEAD_SURFACES.items() if child == surface)
        parent_id = manifest.get("inventory_id")
        if version != LEAD_MANIFEST_VERSION:
            raise ValueError("invalid_event_lead_manifest")
        if parent_id is None:
            items = manifest.get("inline_tips")
            if (surface != EVENT_LEAD_SURFACES["wettfinder_default_inventory"]
                    or not isinstance(items, list) or len(items) > MAX_VISIBLE_LEADS):
                raise ValueError("invalid_event_lead_inventory")
            tips = [dict(t, tip_id=_hash(t), position=i) for i,t in enumerate(items)
                    if isinstance(t, dict) and len(_json(t).encode("utf-8")) <= MAX_TIP_BYTES]
        else:
            if not isinstance(parent_id, str) or "inline_tips" in manifest:
                raise ValueError("invalid_event_lead_inventory")
            parent = (inventory_cache or {}).get(parent_id)
            if parent is None:
                record = conn.execute("SELECT * FROM consumer_tip_publications WHERE publication_id=? AND surface=?",
                                      (parent_id, source)).fetchone()
                if not record:
                    raise ValueError("invalid_event_lead_inventory")
                parent = _validate_publication(conn, record)
                if inventory_cache is not None:
                    inventory_cache[parent_id] = parent
            if (parent["schema_version"] != version or parent["source_run_id"] != run or parent["policy_version"] != policy
                    or parent["complete"] != manifest["complete"] or _utc(parent["first_observed_at"]) > clock):
                raise ValueError("invalid_event_lead_manifest")
            wanted = set(manifest["lead_tip_ids"])
            tips = [dict(t, position=i) for i,t in enumerate(t for t in parent["tips"] if t["tip_id"] in wanted)]
        events = {(t["sport"], t["event_key"]) for t in tips}
        if (len(tips) != 1 or len(events) != 1 or list(next(iter(events))) != manifest.get("first_lead_event")
                or any(_utc(t["starts_at"]) <= clock for t in tips)
                or [t["tip_id"] for t in tips] != manifest["lead_tip_ids"]
                or [[t["event_key"], t["starts_at"]] for t in tips] != manifest.get("lead_events")):
            raise ValueError("invalid_event_lead_manifest")
        # Reader projection; the physical v1-compatible manifest contains no tip rows.
        manifest = dict(manifest, tip_ids=manifest["lead_tip_ids"], recorded_count=len(tips))
    elif "inventory_id" in manifest or (version == LEAD_MANIFEST_VERSION and surface not in EVENT_LEAD_SURFACES):
        raise ValueError("invalid_event_lead_manifest")
    return {**manifest, "publication_id": publication_id, "tips": tips}


def _store_inventory(conn, stable, tips, observed):
    publication_id = _hash(stable)
    existing = conn.execute("SELECT * FROM consumer_tip_publications WHERE publication_id=?",
                            (publication_id,)).fetchone()
    if existing is not None:
        old = _validate_publication(conn, existing)
        return "unchanged", publication_id, old["first_observed_at"]
    manifest = {**stable, "first_observed_at": observed.isoformat()}
    conn.execute("INSERT INTO consumer_tip_publications VALUES(?,?,?,?,?,?)",
                 (publication_id, stable["surface"], stable["source_run_id"], stable["policy_version"],
                  manifest["first_observed_at"], _json(manifest)))
    conn.executemany("INSERT INTO consumer_tips VALUES(?,?,?,?)",
                     [(publication_id, idx, key, _json(tip)) for idx, (key, tip) in enumerate(tips)])
    return "recorded", publication_id, manifest["first_observed_at"]


def record_tip_publication(db_path, *, surface, rows, as_of,
                           source_run_id=None, policy_version=None, event_lead_candidates=None, leads_only=False):
    """Atomically append a bounded final UI inventory; fail closed on conflicts.

    Invalid rows are reported, never silently claimed as displayed evidence.
    Busy/unavailable/schema conflicts return a diagnostic instead of interrupting
    a sport scan or changing existing history. Empty valid inventories persist.
    """
    conn = None
    try:
        observed, decision = _utc(_now()), _utc(as_of)
        if decision > observed:
            raise ValueError("future_publication_clock")
        surface = _text(surface, limit=128)
        if (surface in EVENT_LEAD_SURFACES.values()
                or (event_lead_candidates is not None and surface not in EVENT_LEAD_SURFACES)
                or (leads_only and (surface != "wettfinder_default_inventory" or event_lead_candidates is None))):
            raise ValueError("invalid_event_lead_surface")
        source_run_id = _text(source_run_id, optional=True)
        policy_version = _text(policy_version, optional=True)
        # Do not silently truncate a generator or an oversized displayed list.
        rows = list(islice(iter(rows), MAX_PUBLICATION_ROWS+1))
        if len(rows) > MAX_PUBLICATION_ROWS:
            raise ValueError("too_many_publication_rows")
        tips, rejected, seen = [], Counter(), set()
        for row in rows:
            try:
                tip = normalize_publication_tip(row, as_of=decision)
                if _utc(tip["starts_at"]) <= observed:
                    raise ValueError("event_already_started")
                # A selector clock is not evidence of the current offer clock.
                # Reevaluate quote freshness at the actual capture time.
                raw_row = _mapping(row)
                identity = dict(raw_row)
                identity.update(candidate_id=tip["candidate_id"], market_key=tip["market_key"],
                                scheduled_start=tip["starts_at"])
                tip["quote"] = _quote(raw_row, identity, observed, _utc(tip["starts_at"]))
                tip_id = _hash(tip)
                if tip_id in seen:
                    raise ValueError("duplicate_display_row")
                seen.add(tip_id)
                tips.append((tip_id, tip))
            except (ValueError, TypeError, OverflowError) as exc:
                rejected[str(exc) if isinstance(exc, ValueError) else "invalid_row"] += 1
        stable = {
            "schema_version": SCHEMA_VERSION, "surface": surface,
            "source_run_id": source_run_id, "policy_version": policy_version,
            "supplied_count": len(rows), "recorded_count": len(tips),
            "complete": not rejected, "rejected": dict(sorted(rejected.items())),
            "tip_ids": [tip_id for tip_id, _ in tips],
        }
        leads = None
        if event_lead_candidates is not None:
            keys = list(islice(event_lead_candidates, MAX_VISIBLE_LEADS+1))
            if (len(keys) > MAX_VISIBLE_LEADS or any(not isinstance(key, str) for key in keys)
                    or len(set(keys)) != len(keys)):
                raise ValueError("invalid_event_lead_candidates")
            wanted = set(keys)
            leads = [(tid, t) for tid, t in tips if t["candidate_id"] in wanted]
            supplied = Counter()
            for raw in rows:
                try:
                    r = _mapping(raw)
                    cid = r.get("candidate_id") or r.get("key") or r.get("signal_key")
                    if isinstance(cid, str):
                        supplied[cid] += 1
                except ValueError:
                    pass  # Already counted among rejected rows.
            if (any(supplied[k] != 1 for k in wanted)
                    or len({(t["sport"], t["event_key"]) for _, t in leads}) != len(leads)
                    or (leads_only and (len(rows) != len(keys) or len(rows) > MAX_VISIBLE_LEADS))):
                raise ValueError("invalid_event_lead_candidates")
            stable["schema_version"] = LEAD_MANIFEST_VERSION
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=0.5)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        _initialize(conn)
        status, publication_id, first_clock = ("unchanged", None, observed.isoformat()) if leads_only else (
            _store_inventory(conn, stable, tips, observed))
        new_leads = 0
        if leads and not rejected:
            if _utc(first_clock) > observed:
                raise ValueError("inventory_after_event_lead_clock")
            conn.execute(_LEAD_INDEX)
            base_id = publication_id
            for tid, t in leads:
                ev = [t["sport"], t["event_key"]]
                child_surface = EVENT_LEAD_SURFACES[surface]
                old = conn.execute("SELECT publication_id,first_observed_at FROM consumer_tip_publications "
                    "WHERE surface=? AND json_extract(payload_json,'$.first_lead_event') IS NOT NULL "
                    "AND json_extract(payload_json,'$.first_lead_event')=?", (child_surface, _json(ev))).fetchone()
                if old:
                    if _utc(old[1]) > observed:
                        raise ValueError("event_lead_capture_clock_conflict")
                    continue
                child = dict(stable, surface=child_surface, inventory_id=base_id,
                             tip_ids=[], lead_tip_ids=[tid], supplied_count=1, recorded_count=0,
                             first_lead_event=ev, lead_events=[[t["event_key"], t["starts_at"]]])
                if leads_only:
                    child["inline_tips"] = [t]
                _store_inventory(conn, child, (), observed)
                new_leads += 1
                status = "recorded"
        conn.commit()
        if leads_only:
            return {"status": status, "recorded_tips": new_leads, "skipped_tips": len(rows)-len(tips),
                    "new_event_leads": new_leads, "errors": dict(rejected)}
        return {"status": status, "publication_id": publication_id,
                "recorded_tips": len(tips), "skipped_tips": len(rows)-len(tips),
                "first_observed_at": first_clock, "errors": dict(rejected),
                **({"new_event_leads": new_leads} if leads is not None else {})}
    except (ValueError, TypeError, OverflowError, sqlite3.Error, OSError) as exc:
        if conn is not None:
            conn.rollback()
        return {"status": "unavailable" if isinstance(exc, (sqlite3.Error, OSError)) else "rejected",
                "publication_id": None, "recorded_tips": 0, "skipped_tips": 0,
                "errors": {str(exc) if isinstance(exc, ValueError) else type(exc).__name__: 1}}
    finally:
        if conn is not None:
            conn.close()


def read_tip_publications(db_path, *, since=None, until=None, surface=None, limit=1000,
                          event_window_start=None, event_window_end=None, related_event_keys=()):
    """Read and hash-validate inventories without creating or changing a file.

    Capture-time filters use [since, until). ``tips[].forecast_id`` remains an
    optional join hint: reports must verify its exact model/event/selection
    binding in forecast evidence rather than accepting arbitrary IDs.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("invalid_reader_limit")
    path = Path(db_path)
    if not path.is_file():
        return []
    clauses, args = [], []
    if surface is None:
        # Companion receipts are first-card evidence, not more public inventories.
        clauses.append("surface NOT IN (?,?)")
        args.extend(EVENT_LEAD_SURFACES.values())
    for name, value, operator in (("first_observed_at", since, ">="),
                                  ("first_observed_at", until, "<"),
                                  ("surface", surface, "=")):
        if value is not None:
            clauses.append(f"{name}{operator}?")
            args.append(_text(value) if name == "surface" else _utc(value).isoformat())
    has_window = event_window_start is not None or event_window_end is not None
    if has_window:
        lower, upper = _utc(event_window_start), _utc(event_window_end)
        if upper <= lower:
            raise ValueError("invalid_event_window")
        related = sorted({_text(key, limit=512) for key in related_event_keys})
        if len(related) > 800:
            raise ValueError("too_many_related_event_keys")
    if has_window and surface in EVENT_LEAD_SURFACES.values():
        # Search only the bounded [event ID, original kickoff] references, not
        # forecast data. Include earlier observations if a later kickoff moved.
        args.extend((surface, lower.isoformat(), upper.isoformat()))
        moved = (" OR json_extract(e.value,'$[0]') IN ("+",".join("?" for _ in related)+")") if related else ""
        args.extend(related)
        before = " AND known.first_observed_at<?" if until is not None else ""
        if until is not None:
            args.append(_utc(until).isoformat())
        clauses.append("EXISTS (SELECT 1 FROM json_each(consumer_tip_publications.payload_json,'$.lead_events') seen "
            "WHERE json_extract(seen.value,'$[0]') IN (SELECT json_extract(e.value,'$[0]') "
            "FROM consumer_tip_publications known,json_each(known.payload_json,'$.lead_events') e "
            "WHERE known.surface=? AND ((json_extract(e.value,'$[1]')>=? AND json_extract(e.value,'$[1]')<?)"
            +moved+")"+before+"))")
    elif has_window:
        # Select ALL publication revisions for eligible events, not just the
        # first revision whose rescheduled kickoff entered the requested days.
        # Unrelated old publications do not consume the bounded reader limit.
        extra = " OR json_extract(eligible.payload_json,'$.event_key') IN ("+",".join("?" for _ in related)+")" if related else ""
        cutoff_clause = " AND eligible_publication.first_observed_at<?" if until is not None else ""
        clauses.append("(EXISTS (SELECT 1 FROM consumer_tips captured "
            "WHERE captured.publication_id=consumer_tip_publications.publication_id "
            "AND CASE WHEN json_valid(captured.payload_json) THEN json_extract(captured.payload_json,'$.event_key') END IN ("
            "SELECT DISTINCT json_extract(eligible.payload_json,'$.event_key') FROM consumer_tips eligible "
            "JOIN consumer_tip_publications eligible_publication ON eligible_publication.publication_id=eligible.publication_id "
            "WHERE json_valid(eligible.payload_json) AND ((json_extract(eligible.payload_json,'$.starts_at')>=? "
            "AND json_extract(eligible.payload_json,'$.starts_at')<?)"+extra+")"+cutoff_clause+")) "
            "OR (CASE WHEN json_valid(consumer_tip_publications.payload_json) THEN "
            "json_extract(consumer_tip_publications.payload_json,'$.recorded_count') END=0 "
            "AND first_observed_at>=? AND first_observed_at<?))")
        args.extend((lower.isoformat(), upper.isoformat(), *related))
        if until is not None:
            args.append(_utc(until).isoformat())
        args.extend((lower.isoformat(), upper.isoformat()))
    elif related_event_keys:
        raise ValueError("related_events_require_event_window")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=0.5)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        _validate_schema(conn)
        records = conn.execute("SELECT * FROM consumer_tip_publications"+where+
                               " ORDER BY first_observed_at,publication_id LIMIT ?", (*args, limit+1)).fetchall()
        if len(records) > limit:
            raise ValueError("publication_reader_limit_exceeded")
        cache = {}
        return [_validate_publication(conn, record, cache) for record in records]
