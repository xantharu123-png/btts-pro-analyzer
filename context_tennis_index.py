"""Closed, optional derived tennis membership schema; never an implicit migration.

This owner imports neither the observation writer nor the runtime verifier.
SQL invalidators need no registered functions, including for legacy writers.
The state reader checks storage, not readiness or completeness: only an owning
builder/writer can publish a verified predecessor and matching generations.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, OBSERVATION_FIELDS,
    _validate_canonical_observation_content, digest, require_digest, require_object,
)
from context_sources.tennis import SOURCE_SCHEMA
from context_sources.tennis_status import STATUS_SCHEMA, _validate_tennis_source_tail
from model_artifacts import ArtifactIntegrityError, canonical_bytes


INDEX_SCHEMA_VERSION = 1
# Bind the actual fixed projector owner, not a caller-supplied version label.
PROJECTOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
Membership = tuple[str, str, str, str, str]


class TennisIndexUnavailable(ContextContractError):
    """No usable complete index; never an empty successful history."""


class IndexBudgetExceeded(ContextContractError):
    """An expected additional index budget was exceeded, not source/SQL damage."""


@dataclass(frozen=True)
class IndexState:
    schema_version: int
    projector_sha256: str
    db_identity: tuple[int, int]
    source_generation: int
    index_generation: int
    rewrite_generation: int
    verified_source_generation: int
    verified_index_generation: int
    verified_rewrite_generation: int
    logical_bytes: int
    covered_rowid: int | None
    status: str


_COUNTERS = (
    "source_generation", "index_generation", "rewrite_generation",
    "verified_source_generation", "verified_index_generation",
    "verified_rewrite_generation", "logical_bytes",
)
_STATE_FIELDS = ("schema_version", "projector_sha256", "db_identity", *_COUNTERS,
                 "covered_rowid", "status")
_COUNTER_SQL = ",\n    ".join(
    f"{name} INTEGER NOT NULL CHECK(typeof({name})='integer' AND {name}>=0)"
    for name in _COUNTERS)
INDEX_SCHEMA: dict[str, str] = {
    "tennis_player_events": """CREATE TABLE tennis_player_events (
    tour TEXT NOT NULL CHECK(typeof(tour)='text' AND tour IN ('ATP','WTA')),
    player_id TEXT NOT NULL CHECK(typeof(player_id)='text'),
    event_key TEXT NOT NULL CHECK(typeof(event_key)='text'),
    first_observed_at TEXT NOT NULL CHECK(typeof(first_observed_at)='text'),
    first_receipt_digest TEXT NOT NULL CHECK(typeof(first_receipt_digest)='text'),
    PRIMARY KEY(tour,player_id,event_key)
) WITHOUT ROWID""",
    "tennis_player_index_state": f"""CREATE TABLE tennis_player_index_state (
    id INTEGER PRIMARY KEY CHECK(typeof(id)='integer' AND id=1),
    schema_version INTEGER NOT NULL CHECK(typeof(schema_version)='integer' AND schema_version>0),
    projector_sha256 TEXT NOT NULL CHECK(typeof(projector_sha256)='text'),
    db_identity TEXT NOT NULL CHECK(typeof(db_identity)='text'),
    {_COUNTER_SQL},
    covered_rowid INTEGER CHECK(covered_rowid IS NULL OR typeof(covered_rowid)='integer'),
    status TEXT NOT NULL CHECK(typeof(status)='text' AND status IN ('building','ready','invalid'))
)""",
}
_OBJECTS = {name: ("table", name) for name in INDEX_SCHEMA}


def _invalidation_trigger(name, table, action, changes):
    return f"""CREATE TRIGGER {name} AFTER {action} ON {table}
BEGIN
    UPDATE tennis_player_index_state SET {changes},status='invalid' WHERE id=1;
END"""


# These are fixed schema constants, not caller-generated identifiers or SQL.
for _table, _suffix, _actions in (
    ("context_observations", "observations", ("INSERT", "UPDATE", "DELETE")),
    ("context_contents", "contents", ("UPDATE", "DELETE")),
    ("tennis_player_events", "memberships", ("INSERT", "UPDATE", "DELETE")),
):
    for _action in _actions:
        _name = f"tennis_player_index_{_suffix}_{_action.lower()}"
        if _table == "tennis_player_events":
            _changes = "index_generation=index_generation+1"
        elif _table == "context_observations" and _action == "INSERT":
            _changes = ("source_generation=source_generation+1,"
                "rewrite_generation=rewrite_generation+CASE WHEN covered_rowid IS NOT NULL "
                "AND NEW.rowid<=covered_rowid THEN 1 ELSE 0 END")
        else:
            _changes = "source_generation=source_generation+1,rewrite_generation=rewrite_generation+1"
        INDEX_SCHEMA[_name] = _invalidation_trigger(_name, _table, _action, _changes)
        _OBJECTS[_name] = ("trigger", _table)


# REPLACE need not fire DELETE triggers when recursive_triggers is disabled.
# Compare only the existing content primary key before replacement. New values
# and identical ignored duplicates do not dirty the source-generation contract.
_REPLACEMENT_TRIGGER = "tennis_player_index_contents_replace"
INDEX_SCHEMA[_REPLACEMENT_TRIGGER] = """CREATE TRIGGER tennis_player_index_contents_replace
BEFORE INSERT ON context_contents
WHEN EXISTS(SELECT 1 FROM context_contents
    WHERE content_digest=NEW.content_digest AND payload IS NOT NEW.payload)
BEGIN
    UPDATE tennis_player_index_state SET source_generation=source_generation+1,
        rewrite_generation=rewrite_generation+1,status='invalid' WHERE id=1;
END"""
_OBJECTS[_REPLACEMENT_TRIGGER] = ("trigger", "context_contents")


def _sql_identity(sql):
    if type(sql) is not str:
        raise ArtifactIntegrityError("tennis index schema SQL must be text")
    # Preserve string-literal contents; whitespace/case in a trigger's status
    # literal is semantic even though unquoted SQL whitespace/case is not.
    parts = re.split(r"('(?:''|[^'])*')", sql)
    return "".join(part if index % 2 else re.sub(r"\s+", "", part).casefold()
                   for index, part in enumerate(parts))


def check_index_schema(connection) -> bool:
    """Check this exact optional family, not legacy objects or SQLite health.

    The runtime's closed full catalog remains responsible for unrelated extra
    objects. This function also rejects unknown objects in the tennis namespace
    and unknown triggers attached to either derived table.
    """
    seen = set()
    for kind, name, table, sql in connection.execute(
            "SELECT type,name,tbl_name,sql FROM main.sqlite_master"):
        if name not in INDEX_SCHEMA:
            if name.startswith("tennis_") or table in ("tennis_player_events", "tennis_player_index_state"):
                raise ArtifactIntegrityError("unknown tennis index schema object")
            continue
        if ((kind, table) != _OBJECTS[name] or name in seen
                or _sql_identity(sql) != _sql_identity(INDEX_SCHEMA[name])):
            raise ArtifactIntegrityError("modified tennis index schema object")
        seen.add(name)
    if not seen:
        return False
    if seen != set(INDEX_SCHEMA):
        raise ArtifactIntegrityError("incomplete tennis index schema family")
    # A trigger on a dropped source table can survive as a broken family only
    # through catalog tampering. Never accept that as a deployable schema.
    sources = {row[0] for row in connection.execute(
        "SELECT name FROM main.sqlite_master WHERE type='table' AND name IN ('context_contents','context_observations')")}
    if sources != {"context_contents", "context_observations"}:
        raise ArtifactIntegrityError("tennis index source schema is missing")
    return True


def read_index_state(connection) -> IndexState:
    """Return strict stored scalars without int()/str() coercion or ready claims."""
    if not check_index_schema(connection):
        raise TennisIndexUnavailable("tennis player index schema is absent")
    rows = connection.execute("SELECT id," + ",".join(_STATE_FIELDS) +
        " FROM main.tennis_player_index_state LIMIT 2").fetchall()
    if len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] != 1:
        raise ArtifactIntegrityError("tennis index needs exactly one id=1 state row")
    values = dict(zip(_STATE_FIELDS, rows[0][1:]))
    if type(values["schema_version"]) is not int or values["schema_version"] <= 0:
        raise ArtifactIntegrityError("tennis index schema version is not a positive integer")
    for name in _COUNTERS:
        if type(values[name]) is not int or values[name] < 0:
            raise ArtifactIntegrityError("tennis index counter is not a nonnegative integer")
    cursor = values["covered_rowid"]
    if cursor is not None and type(cursor) is not int:
        raise ArtifactIntegrityError("tennis index cursor is not a signed integer or null")
    if type(values["status"]) is not str or values["status"] not in {"building", "ready", "invalid"}:
        raise ArtifactIntegrityError("tennis index status is unknown")
    try:
        require_digest(values["projector_sha256"], "tennis projector identity")
        raw = values["db_identity"]
        if type(raw) is not str or len(raw) > 128:
            raise ValueError("file identity must be bounded canonical text")
        identity = json.loads(raw)
        if (type(identity) is not list or len(identity) != 2
                or any(type(value) is not int or value < 0 for value in identity)
                or canonical_bytes(identity).decode("utf-8") != raw):
            raise ValueError("file identity must contain two canonical nonnegative integers")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ArtifactIntegrityError("invalid tennis index projector/file identity") from exc
    values["db_identity"] = tuple(identity)
    return IndexState(**values)


def project_memberships(receipt: dict) -> tuple[Membership, ...]:
    """Project every known native participant, including partial/unknown states.

    Physical receipt validation is repeated at this public boundary without
    importing its writer. No result labels or historical completeness are used.
    """
    require_object(receipt, set(OBSERVATION_FIELDS) | {"digest", "content_digest", "observed_at"},
                   label="physical tennis membership receipt")
    content = {key: receipt[key] for key in OBSERVATION_FIELDS}
    observed = receipt["observed_at"]
    require_digest(receipt["digest"], "membership receipt identity")
    require_digest(receipt["content_digest"], "membership content identity")
    _validate_canonical_observation_content(content, receipt=observed)
    content_bytes = canonical_bytes(content)
    if (hashlib.sha256(content_bytes).hexdigest() != receipt["content_digest"]
            or digest({"content_digest": receipt["content_digest"], "observed_at": observed}) != receipt["digest"]):
        raise ContextIntegrityError("membership physical receipt identity differs")
    if receipt["source"] != "espn" or receipt["kind"] not in {"event_status", "workload"}:
        return ()
    if receipt["sport"] != "tennis":
        if receipt["source_schema"] in {STATUS_SCHEMA, SOURCE_SCHEMA}:
            raise ContextContractError("claimed tennis schema has a different sport")
        return ()  # A valid, unambiguously other-sport receipt is processed.
    _validate_tennis_source_tail(receipt, content_bytes)
    payload = receipt["payload"]
    players = (payload["participant_ids"] if receipt["source_schema"] == STATUS_SCHEMA
               else (payload["player_id"], payload["opponent_id"]))
    return tuple((payload["tour"], player, receipt["event_key"], observed, receipt["digest"])
                 for player in sorted({player for player in players if player is not None}))
