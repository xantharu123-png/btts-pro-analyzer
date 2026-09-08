"""Append-only, price-free context content and actual receipt revisions.

Uses the A1 SQLite location/trust rules. There are no providers, implicit clock
reads or production consumers here. Hashes detect broken identities; they do
not certify source truth or make retrospective data prospectively observed.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from model_artifacts import _connect as _artifact_connect, _decode_object, canonical_bytes
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, OBSERVATION_FIELDS,
    canonical_timestamp, digest, normalize_observation, require_digest,
    require_native_key, require_number, require_object, require_text,
)


@dataclass(frozen=True)
class _RegisteredArchiveResolver:
    source: str
    resolver_id: str
    resolver_version: str
    resolve_local: Callable[[dict], dict | None]


# Intentionally EMPTY. An owning, independently reviewed source adapter must
# register secured LOCAL evidence verification here before any real archive
# may enter a causal cohort. User/provider callbacks are never accepted.
_ARCHIVE_RESOLVERS: dict[str, _RegisteredArchiveResolver] = {}


def _connect(path: Path):
    connection = _artifact_connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS context_contents (
                content_digest TEXT PRIMARY KEY,
                payload BLOB NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS context_observations (
                digest TEXT PRIMARY KEY,
                content_digest TEXT NOT NULL REFERENCES context_contents(content_digest),
                event_key TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                schedule_revision TEXT NOT NULL,
                source TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                kind TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS context_event_receipts
            ON context_observations(event_key, schedule_revision, observed_at)
        """)
        connection.commit()
    except BaseException:
        connection.rollback()
        connection.close()
        raise
    return connection


_SELECT = """
    SELECT r.digest, r.content_digest, r.event_key, r.observed_at,
           r.schedule_revision, r.source, r.subject_id, r.kind, c.payload
    FROM context_observations AS r
    LEFT JOIN context_contents AS c ON c.content_digest = r.content_digest
"""


def _decode_receipt(stored: tuple) -> dict:
    receipt_hash, content_hash, event_key, observed_at, schedule, source, subject, kind, payload = stored
    try:
        require_digest(receipt_hash)
        require_digest(content_hash)
        if type(observed_at) is not str or canonical_timestamp(observed_at) != observed_at:
            raise ContextIntegrityError("stored receipt clock is not canonical UTC")
        content = _decode_object(payload, label="context content")
        normalized = normalize_observation(content, observed_at=datetime.fromisoformat(observed_at))
        if canonical_bytes(content) != canonical_bytes(normalized) or digest(content) != content_hash:
            raise ContextIntegrityError("context content identity mismatch")
        if digest({"content_digest": content_hash, "observed_at": observed_at}) != receipt_hash:
            raise ContextIntegrityError("context receipt identity mismatch")
        if (event_key, schedule, source, subject, kind) != tuple(
            content[name] for name in ("event_key", "schedule_revision", "source", "subject_id", "kind")
        ):
            raise ContextIntegrityError("context receipt index fields mismatch")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContextIntegrityError("invalid persisted context receipt") from exc
    return {**content, "digest": receipt_hash, "content_digest": content_hash, "observed_at": observed_at}


def append_observation(path: Path, record: dict, *, observed_at: datetime) -> str:
    """Append a genuine fetch receipt; duplicate receipt ingestion is idempotent."""
    content = normalize_observation(record, observed_at=observed_at)
    observed = canonical_timestamp(observed_at)
    content_hash = digest(content)
    receipt_hash = digest({"content_digest": content_hash, "observed_at": observed})
    payload = canonical_bytes(content)
    with closing(_connect(Path(path))) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT OR IGNORE INTO context_contents VALUES (?, ?)", (content_hash, payload))
            existing = connection.execute("SELECT payload FROM context_contents WHERE content_digest=?", (content_hash,)).fetchone()
            if existing != (payload,):
                raise ContextIntegrityError("context content identity collision")
            connection.execute("""
                INSERT OR IGNORE INTO context_observations (
                    digest, content_digest, event_key, observed_at, schedule_revision,
                    source, subject_id, kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (receipt_hash, content_hash, content["event_key"], observed,
                  content["schedule_revision"], content["source"], content["subject_id"], content["kind"]))
            stored = connection.execute(_SELECT + " WHERE r.digest=?", (receipt_hash,)).fetchone()
            if stored is None or _decode_receipt(stored) != {
                **content, "digest": receipt_hash, "content_digest": content_hash, "observed_at": observed,
            }:
                raise ContextIntegrityError("context receipt identity collision")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return receipt_hash


def _archive_resolution(row: dict, resolver_id: str | None, cutoff: str) -> dict | None:
    registered = _ARCHIVE_RESOLVERS.get(resolver_id) if resolver_id is not None else None
    if registered is None or registered.source != row["source"] or row["publication_proof"] is None:
        return None
    # A defensive copy prevents an adapter from rewriting the selected receipt.
    from copy import deepcopy
    try:
        resolved = registered.resolve_local(deepcopy(row))
        if resolved is None:
            return None
        fields = {"schema", "resolver_id", "resolver_version", "content_digest", "published_at",
                  "evidence_locator", "evidence_digest", "resolution_digest"}
        require_object(resolved, fields, label="archive proof resolution")
        if type(resolved["schema"]) is not int or resolved["schema"] != 1:
            raise ContextIntegrityError("unknown archive resolution schema")
        if (resolved["resolver_id"], resolved["resolver_version"]) != (registered.resolver_id, registered.resolver_version):
            raise ContextIntegrityError("archive resolver identity mismatch")
        if require_digest(resolved["content_digest"]) != row["content_digest"]:
            raise ContextIntegrityError("archive content identity mismatch")
        publication = canonical_timestamp(resolved["published_at"])
        if publication != resolved["published_at"] or publication != row["published_at"]:
            raise ContextIntegrityError("archive publication binding mismatch")
        require_text(resolved["evidence_locator"], "secured evidence locator")
        require_digest(resolved["evidence_digest"])
        require_digest(resolved["resolution_digest"])
        if digest({key: val for key, val in resolved.items() if key != "resolution_digest"}) != resolved["resolution_digest"]:
            raise ContextIntegrityError("archive resolution identity mismatch")
        if publication > cutoff:
            return None
        return dict(resolved)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContextIntegrityError("invalid claimed recognized archive proof") from exc


def observations_as_of(
    path: Path, event_key: str, *, cutoff: datetime, schedule_revision: str,
    mode: str = "prospective", proof_resolver: str | None = None,
) -> tuple[dict, ...]:
    """Select latest eligible revisions, preserving ties and retrospective class.

    Historical is an inspection/replay mode, NOT a causal approval. It returns
    late unverified imports separately, explicitly labelled retrospective.
    ``proof_resolver`` can only name a reviewed source-specific registry entry.
    """
    require_native_key(event_key)
    require_text(schedule_revision, "schedule_revision", code=True)
    decision = canonical_timestamp(cutoff)
    if type(mode) is not str or mode not in {"prospective", "historical"}:
        raise ContextContractError("unknown observation selection mode")
    if proof_resolver is not None and type(proof_resolver) is not str:
        raise ContextContractError("proof_resolver must name a registered resolver, not a callback")
    with closing(_connect(Path(path))) as connection:
        try:
            connection.execute("BEGIN")
            rows = [_decode_receipt(stored) for stored in connection.execute(
                _SELECT + " WHERE r.event_key=?", (event_key,),
            ).fetchall()]
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    latest: dict[tuple, list[dict]] = {}
    for row in rows:
        if row["schedule_revision"] != schedule_revision:
            continue
        resolution = None
        if row["observed_at"] <= decision:
            evidence, effective = "prospective", row["observed_at"]
        elif mode == "prospective":
            continue
        else:
            resolution = _archive_resolution(row, proof_resolver, decision)
            evidence = "archival_verified" if resolution is not None else "retrospective"
            effective = resolution["published_at"] if resolution is not None else row["observed_at"]
        selected = {**row, "evidence_class": evidence, "effective_at": effective, "publication_resolution": resolution}
        group = (row["source"], row["subject_id"], row["kind"], "retrospective" if evidence == "retrospective" else "causal")
        preceding = latest.get(group)
        if preceding is None or effective > preceding[0]["effective_at"]:
            latest[group] = [selected]
        elif effective == preceding[0]["effective_at"]:
            # Stable output ordering is not source/revision precedence.
            latest[group].append(selected)
    return tuple(sorted((row for group in latest.values() for row in group),
                        key=lambda row: (row["source"], row["subject_id"], row["kind"], row["evidence_class"], row["digest"])))


def freshness_policy(
    kind: str, *, schedule_revision: str, requires_complete: bool = True,
    event_status: str = "scheduled", source_precedence: list[str] | None = None,
    source_max_age_seconds: dict[str, int | float] | None = None,
) -> dict:
    """Versioned operational expiry, not a learned effect or completeness claim."""
    return _validate_policy({
        "version": "context-freshness-v1", "kind": kind, "schedule_revision": schedule_revision,
        "requires_complete": requires_complete, "event_status": event_status,
        "source_precedence": [] if source_precedence is None else source_precedence,
        "source_max_age_seconds": {} if source_max_age_seconds is None else source_max_age_seconds,
        "availability_max_age_seconds": 21600, "near_start_seconds": 7200,
        "near_start_max_age_seconds": 1800, "weather_max_age_seconds": 10800,
    })


def _validate_policy(policy: dict) -> dict:
    fields = {"version", "kind", "schedule_revision", "requires_complete", "event_status", "source_precedence",
              "source_max_age_seconds", "availability_max_age_seconds", "near_start_seconds",
              "near_start_max_age_seconds", "weather_max_age_seconds"}
    require_object(policy, fields, label="freshness policy")
    require_text(policy["version"], "policy version", code=True)
    require_text(policy["schedule_revision"], "schedule revision", code=True)
    if type(policy["kind"]) is not str or policy["kind"] not in {"availability", "expected_lineup", "confirmed_lineup", "weather", "workload", "workload_coverage"}:
        raise ContextContractError("unsupported freshness factor kind")
    if type(policy["requires_complete"]) is not bool:
        raise ContextContractError("requires_complete must be boolean")
    if type(policy["event_status"]) is not str or policy["event_status"] not in {"scheduled", "cancelled", "started", "completed"}:
        raise ContextContractError("unknown event status")
    for name in ("availability_max_age_seconds", "near_start_seconds", "near_start_max_age_seconds", "weather_max_age_seconds"):
        require_number(policy[name], name, minimum=0, maximum=31536000)
    defaults = {"availability_max_age_seconds": 21600, "near_start_seconds": 7200,
                "near_start_max_age_seconds": 1800, "weather_max_age_seconds": 10800}
    if policy["version"] == "context-freshness-v1" and any(policy[name] != seconds for name, seconds in defaults.items()):
        raise ContextContractError("changed operational expiry requires a new policy version")
    sources = policy["source_precedence"]
    if type(sources) is not list or any(type(source) is not str or not source for source in sources) or len(set(sources)) != len(sources):
        raise ContextContractError("source precedence must be a list of distinct source identities")
    limits = policy["source_max_age_seconds"]
    if type(limits) is not dict:
        raise ContextContractError("source freshness limits must be an object")
    for source, seconds in limits.items():
        require_text(source, "source freshness identity", code=True)
        require_number(seconds, "source maximum age", minimum=0, maximum=31536000)
    return {**policy, "source_precedence": list(sources), "source_max_age_seconds": dict(limits)}


def _check_selected_row(row: dict) -> None:
    required = set(OBSERVATION_FIELDS) | {"digest", "content_digest", "observed_at", "effective_at", "evidence_class", "publication_resolution"}
    require_object(row, required, label="selected observation")
    try:
        normalized = normalize_observation({key: row[key] for key in OBSERVATION_FIELDS}, observed_at=datetime.fromisoformat(row["observed_at"]))
        if canonical_bytes(normalized) != canonical_bytes({key: row[key] for key in OBSERVATION_FIELDS}):
            raise ContextIntegrityError("selected content is not canonical")
        if digest(normalized) != row["content_digest"] or digest({"content_digest": row["content_digest"], "observed_at": row["observed_at"]}) != row["digest"]:
            raise ContextIntegrityError("selected observation identity mismatch")
        if canonical_timestamp(row["observed_at"]) != row["observed_at"] or canonical_timestamp(row["effective_at"]) != row["effective_at"]:
            raise ContextIntegrityError("selected observation clocks must be canonical")
        if type(row["evidence_class"]) is not str or row["evidence_class"] not in {"prospective", "archival_verified", "retrospective"}:
            raise ContextIntegrityError("unknown selected evidence class")
        if row["evidence_class"] != "archival_verified" and (row["effective_at"] != row["observed_at"] or row["publication_resolution"] is not None):
            raise ContextIntegrityError("prospective/retrospective data must retain the actual receipt clock")
        if row["evidence_class"] == "archival_verified" and (type(row["publication_resolution"]) is not dict or row["effective_at"] != row["published_at"]):
            raise ContextIntegrityError("archival row is missing its separate publication binding")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContextIntegrityError("invalid selected context observation") from exc


def _has_reported_fact(value: object) -> bool:
    if type(value) is dict:
        return any(_has_reported_fact(item) for item in value.values())
    if type(value) is list:
        return any(_has_reported_fact(item) for item in value)
    return value is not None and value != ""


def factor_state(rows: tuple[dict, ...], *, cutoff: datetime, scheduled_start: datetime, policy: dict) -> dict:
    """Evaluate one factor's data state separately from its eventual model role.

    A player fact uses requires_complete=False. A team's entire absence list
    uses requires_complete=True. Neither state asserts a numerical effect.
    """
    if type(rows) is not tuple:
        raise ContextContractError("factor rows must be a tuple")
    policy = _validate_policy(policy)
    decision = canonical_timestamp(cutoff)
    kickoff = canonical_timestamp(scheduled_start)
    for row in rows:
        _check_selected_row(row)
    relevant = [row for row in rows if row["kind"] == policy["kind"]]
    refs = sorted({row["digest"] for row in relevant})

    def result(state, coverage, fresh_until=None):
        return {"state": state, "refs": refs, "coverage": coverage,
                "fresh_until": fresh_until, "policy_version": policy["version"]}

    if policy["event_status"] != "scheduled" or decision >= kickoff:
        return result("not_applicable", "not_applicable")
    if any(row["kind"] == "event_status" and row["schedule_revision"] == policy["schedule_revision"]
           and row["observed_at"] <= decision and row["payload"].get("status") in ("cancelled", "started", "completed")
           for row in rows):
        return result("not_applicable", "not_applicable")
    # Only prospectively received facts can refresh a live factor's clock.
    eligible = [row for row in relevant if row["schedule_revision"] == policy["schedule_revision"]
                and row["evidence_class"] == "prospective" and row["observed_at"] <= decision]
    if not eligible:
        return result("missing", "incomplete")
    if len({(row["event_key"], row["sport"], row["competition"], row["format"]) for row in eligible}) != 1:
        raise ContextContractError("factor rows mix different events or event scopes")
    if policy["requires_complete"] and not any(row["complete"] for row in eligible):
        return result("missing", "incomplete")
    if not any(row["complete"] or _has_reported_fact(row["payload"]) for row in eligible):
        return result("missing", "incomplete")
    if policy["kind"] == "workload":
        if all(row["payload"].get("status") == "walkover" for row in eligible):
            return result("not_applicable", "not_applicable")
        if any(row["payload"].get("status") not in ("completed", "retired", "walkover") for row in eligible):
            return result("missing", "incomplete")

    fresh, deadlines, fresh_deadlines = [], [], []
    for row in eligible:
        if policy["kind"] == "weather":
            valid = row["valid_from"] <= kickoff and row["valid_until"] is not None and kickoff < row["valid_until"]
        else:
            valid = row["valid_from"] <= decision and (row["valid_until"] is None or decision < row["valid_until"])
        if not valid:
            continue
        observed = datetime.fromisoformat(row["observed_at"])
        if policy["kind"] == "confirmed_lineup":
            deadline = kickoff
            if row["source"] in policy["source_max_age_seconds"]:
                deadline = min(deadline, canonical_timestamp(observed + timedelta(seconds=policy["source_max_age_seconds"][row["source"]])))
        elif policy["kind"] == "workload":
            deadline = None
        else:
            seconds = policy["weather_max_age_seconds"] if policy["kind"] == "weather" else policy["availability_max_age_seconds"]
            if policy["kind"] != "weather" and (datetime.fromisoformat(kickoff) - datetime.fromisoformat(decision)).total_seconds() <= policy["near_start_seconds"]:
                seconds = min(seconds, policy["near_start_max_age_seconds"])
            if row["source"] in policy["source_max_age_seconds"]:
                seconds = min(seconds, policy["source_max_age_seconds"][row["source"]])
            deadline = canonical_timestamp(observed + timedelta(seconds=seconds))
        if row["valid_until"] is not None and policy["kind"] != "weather":
            deadline = min(deadline, row["valid_until"]) if deadline is not None else row["valid_until"]
        if deadline is not None:
            deadlines.append(deadline)
        if deadline is None or decision < deadline:
            fresh.append(row)
            if deadline is not None:
                fresh_deadlines.append(deadline)
    if not fresh:
        return result("stale", "incomplete", min(deadlines) if deadlines else None)
    if policy["requires_complete"] and not any(row["complete"] for row in fresh):
        return result("missing", "incomplete")

    by_subject: dict[str, list[dict]] = {}
    for row in fresh:
        by_subject.setdefault(row["subject_id"], []).append(row)
    for alternatives in by_subject.values():
        sources = {row["source"] for row in alternatives}
        precedence = policy["source_precedence"]
        if len(sources) > 1 and sources <= set(precedence):
            chosen = min(sources, key=precedence.index)
            alternatives = [row for row in alternatives if row["source"] == chosen]
        source_revisions: dict[str, set[str]] = {}
        semantics = set()
        for row in alternatives:
            source_revisions.setdefault(row["source"], set()).add(row["content_digest"])
            semantics.add(canonical_bytes({"payload": row["payload"], "complete": row["complete"]}))
        if any(len(identities) > 1 for identities in source_revisions.values()) or len(semantics) > 1:
            return result("conflicting", "conflicting")
    complete = all(row["complete"] for row in fresh)
    return result("available", "complete" if complete else "incomplete", min(fresh_deadlines) if fresh_deadlines else None)
