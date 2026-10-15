"""Closed optional SQLite schema and actual, physically decoded memberships."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import sqlite3

import pytest

from context_models.contracts import ContextContractError, digest, normalize_observation
from context_observations import _decode_receipt
from context_runtime import _SCHEMA
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import ArtifactIntegrityError, canonical_bytes


CLOCK = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)
OBSERVED = "2026-10-15T10:00:00.000000Z"


def owner():
    # An explicit assertion makes the missing-owner RED a feature failure,
    # not a collection error masking the other test fixtures.
    assert importlib.util.find_spec("context_tennis_index") is not None, "tennis index owner is missing"
    return importlib.import_module("context_tennis_index")


def database(*, optional=False):
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    for sql in _SCHEMA.values():
        connection.execute(sql)
    if optional:
        for sql in owner().INDEX_SCHEMA.values():
            connection.execute(sql)
    return connection


def state(connection, **changes):
    values = dict(id=1, schema_version=1, projector_sha256=owner().PROJECTOR_SHA256,
        db_identity="[0,123]", source_generation=0, index_generation=0,
        rewrite_generation=0, verified_source_generation=0,
        verified_index_generation=0, verified_rewrite_generation=0,
        logical_bytes=4096, covered_rowid=None, status="building")
    values.update(changes)
    connection.execute("INSERT INTO tennis_player_index_state (" + ",".join(values) +
        ") VALUES (" + ",".join("?" for _ in values) + ")", tuple(values.values()))


def decoded(content):
    content = normalize_observation(content, observed_at=CLOCK)
    content_hash = digest(content)
    receipt_hash = digest({"content_digest": content_hash, "observed_at": OBSERVED})
    return _decode_receipt((receipt_hash, content_hash, content["event_key"], OBSERVED,
        content["schedule_revision"], content["source"], content["subject_id"],
        content["kind"], canonical_bytes(content)))


def status_receipt(players=("1", "9"), **changes):
    native = {"id": "101", "date": "2026-10-15T12:00:00Z",
        "competitors": [{"id": player} for player in players],
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}}}
    native.update(changes)
    row, = normalize_tennis_status("ATP", "189-2026", native,
        grouping_slug="mens-singles", observed_at=CLOCK)
    return decoded(row)


def test_legacy_and_complete_optional_schema_only():
    index = owner()
    from context_runtime import verify_context_schema_objects, _verify_schema
    with database() as connection:
        original = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
        assert index.check_index_schema(connection) is False
        assert verify_context_schema_objects(connection) == set(_SCHEMA)
        for sql in index.INDEX_SCHEMA.values():
            connection.execute(sql)
        assert index.check_index_schema(connection) is True
        assert verify_context_schema_objects(connection) == set(_SCHEMA) | set(index.INDEX_SCHEMA)
        assert _verify_schema(connection) == set(_SCHEMA) | set(index.INDEX_SCHEMA)
        assert connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'tennis_%'").fetchall() == original
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tennis_%' ORDER BY name").fetchall() == [
            ("tennis_player_events",), ("tennis_player_index_state",)]
        assert "WITHOUT ROWID" in index.INDEX_SCHEMA["tennis_player_events"]
        assert connection.execute("PRAGMA table_info(tennis_player_events)").fetchall() == [
            (0, "tour", "TEXT", 1, None, 1), (1, "player_id", "TEXT", 1, None, 2),
            (2, "event_key", "TEXT", 1, None, 3), (3, "first_observed_at", "TEXT", 1, None, 0),
            (4, "first_receipt_digest", "TEXT", 1, None, 0)]
        connection.execute("CREATE TABLE unexpected(value TEXT)")
        with pytest.raises(ArtifactIntegrityError):
            verify_context_schema_objects(connection)


@pytest.mark.parametrize("mutation", ["missing_trigger", "modified_trigger", "missing_table", "extra_trigger"])
def test_missing_or_modified_trigger_is_unavailable(mutation):
    index = owner()
    from context_runtime import verify_context_schema_objects
    with database(optional=True) as connection:
        trigger = connection.execute("SELECT name,tbl_name FROM sqlite_master WHERE type='trigger' ORDER BY name LIMIT 1").fetchone()
        if mutation in ("missing_trigger", "modified_trigger"):
            connection.execute('DROP TRIGGER "' + trigger[0] + '"')
            if mutation == "modified_trigger":
                connection.execute('CREATE TRIGGER "' + trigger[0] + '" AFTER INSERT ON "' + trigger[1] + '" BEGIN SELECT 1; END')
        elif mutation == "missing_table":
            connection.execute("DROP TABLE tennis_player_events")
        else:
            connection.execute("CREATE TRIGGER tennis_rogue AFTER INSERT ON context_contents BEGIN SELECT 1; END")
        with pytest.raises(ArtifactIntegrityError):
            index.check_index_schema(connection)
        with pytest.raises(ArtifactIntegrityError):
            verify_context_schema_objects(connection)


def test_full_catalog_rejects_unprefixed_trigger_outside_optional_family():
    index = owner()
    from context_runtime import verify_context_schema_objects
    with database(optional=True) as connection:
        connection.execute("CREATE TRIGGER rogue AFTER INSERT ON context_contents BEGIN SELECT 1; END")
        assert index.check_index_schema(connection) is True
        with pytest.raises(ArtifactIntegrityError):
            verify_context_schema_objects(connection)


def test_projection_keeps_unknown_and_removed_participants():
    index = owner()
    old = status_receipt()
    partial = status_receipt(("1", None), status=None)
    removed = status_receipt(("2", "3"))
    assert partial["payload"]["status"] == "unknown"
    assert index.project_memberships(partial) == (("ATP", "espn:tennis:ATP:player:1",
        "espn:tennis:ATP:match:101", OBSERVED, partial["digest"]),)
    memberships = set(index.project_memberships(old) + index.project_memberships(removed))
    assert {member[1] for member in memberships} == {"espn:tennis:ATP:player:1",
        "espn:tennis:ATP:player:9", "espn:tennis:ATP:player:2", "espn:tennis:ATP:player:3"}
    duplicate = status_receipt(("1", "1"))
    assert len(index.project_memberships(duplicate)) == 1


def test_workload_projects_both_known_players_without_cross_tour_aliases():
    index = owner()
    native = {"id": "101", "date": "2026-10-14T12:00:00Z",
        "competitors": [{"id": "1"}, {"id": "9"}],
        "status": {"type": {"state": "post", "name": "STATUS_FINAL", "completed": True}}}
    status, first, second = normalize_tennis_status("WTA", "189-2026", native,
        grouping_slug="womens-singles", observed_at=CLOCK)
    for content in (status, first, second):
        row = decoded(content)
        assert index.project_memberships(row) == (
            ("WTA", "espn:tennis:WTA:player:1", "espn:tennis:WTA:match:101", OBSERVED, row["digest"]),
            ("WTA", "espn:tennis:WTA:player:9", "espn:tennis:WTA:match:101", OBSERVED, row["digest"]))


def test_nba_is_not_tennis_but_cross_tour_corruption_fails():
    index = owner()
    content = {key: value for key, value in status_receipt().items()
        if key not in {"digest", "content_digest", "observed_at"}}
    nba = deepcopy(content)
    nba.update(sport="basketball", event_key="espn:basketball:401999999",
        subject_id="espn:basketball:team:1", competition="nba",
        source_schema="espn-basketball-context-v1", kind="workload", payload={"minutes": 12})
    assert index.project_memberships(decoded(nba)) == ()
    corrupt = deepcopy(content)
    corrupt["payload"]["participant_ids"][0] = "espn:tennis:WTA:player:1"
    with pytest.raises(ContextContractError):
        index.project_memberships(decoded(corrupt))
    corrupt = deepcopy(content)
    corrupt["source_schema"] = "unknown-tennis-projection"
    with pytest.raises(ContextContractError):
        index.project_memberships(decoded(corrupt))
    corrupt = status_receipt()
    corrupt["digest"] = "0" * 64
    with pytest.raises(ContextContractError):
        index.project_memberships(corrupt)


def test_state_is_immutable_strict_and_preserves_negative_cursor():
    index = owner()
    from dataclasses import FrozenInstanceError
    with database(optional=True) as connection:
        with pytest.raises(ArtifactIntegrityError):
            index.read_index_state(connection)
        state(connection, covered_rowid=-8)
        read = index.read_index_state(connection)
        assert read.db_identity == (0, 123)
        assert read.covered_rowid == -8
        assert read.status == "building"
        with pytest.raises(FrozenInstanceError):
            read.status = "ready"


@pytest.mark.parametrize("field,value", [("source_generation", 0.5), ("logical_bytes", 4096.5),
    ("covered_rowid", -1.5), ("source_generation", -1), ("schema_version", 1.5),
    ("id", 1.5), ("status", "maybe")])
def test_schema_rejects_noninteger_and_invalid_control_values(field, value):
    owner()
    with database(optional=True) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            state(connection, **{field: value})


@pytest.mark.parametrize("changes", [{"db_identity": "[0, 123]"}, {"db_identity": "[false,123]"},
    {"db_identity": "[0,1.5]"}, {"db_identity": "[-1,123]"}, {"projector_sha256": "not-a-digest"},
    {"source_generation": 1.5}, {"covered_rowid": -1.5}, {"status": "maybe"}, {"id": 2}])
def test_reader_rejects_noncanonical_or_bypassed_control_values(changes):
    index = owner()
    with database(optional=True) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        state(connection, **changes)
        with pytest.raises(ArtifactIntegrityError):
            index.read_index_state(connection)


def source_insert(connection, rowid):
    connection.execute("INSERT OR IGNORE INTO context_contents VALUES ('content', X'7b7d')")
    connection.execute("INSERT INTO context_observations(rowid,digest,content_digest,event_key,observed_at,schedule_revision,source,subject_id,kind) VALUES (? ,?,'content','espn:tennis:ATP:match:101',?,'schedule','espn','subject','event_status')",
        (rowid, str(rowid), OBSERVED))


def test_sql_triggers_track_generation_rewrites_and_membership_without_udfs():
    index = owner()
    with database(optional=True) as connection:
        state(connection, covered_rowid=-8, status="ready")
        source_insert(connection, -9)
        current = index.read_index_state(connection)
        assert (current.source_generation, current.rewrite_generation, current.status) == (1, 1, "invalid")
        source_insert(connection, 1)
        current = index.read_index_state(connection)
        assert (current.source_generation, current.rewrite_generation) == (2, 1)
        connection.execute("UPDATE context_observations SET subject_id='changed' WHERE rowid=1")
        assert index.read_index_state(connection).rewrite_generation == 2
        connection.execute("UPDATE context_contents SET payload=X'5b5d' WHERE content_digest='content'")
        assert index.read_index_state(connection).rewrite_generation == 3
        connection.execute("INSERT INTO tennis_player_events VALUES ('ATP','espn:tennis:ATP:player:1','espn:tennis:ATP:match:101',?,?)", (OBSERVED, "0" * 64))
        connection.execute("UPDATE tennis_player_events SET first_receipt_digest=?", ("1" * 64,))
        connection.execute("DELETE FROM tennis_player_events")
        assert index.read_index_state(connection).index_generation == 3
        connection.execute("DELETE FROM context_observations")
        connection.execute("DELETE FROM context_contents")
        current = index.read_index_state(connection)
        assert (current.source_generation, current.rewrite_generation) == (7, 6)


def test_structural_verifier_does_not_claim_sqlite_integrity():
    owner()
    from context_runtime import verify_context_schema_objects, _verify_schema
    with database(optional=True) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("INSERT INTO active_manifest VALUES (1,'missing')")
        assert verify_context_schema_objects(connection) == set(_SCHEMA) | set(owner().INDEX_SCHEMA)
        with pytest.raises(ArtifactIntegrityError, match="reference"):
            _verify_schema(connection)
