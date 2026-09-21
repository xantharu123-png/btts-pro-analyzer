"""Append-only forecast lineage for an observed native opponent replacement.

No results, prices, old predictions or old model revisions are changed. Only
an exact, later, worker-verified native identity can supersede an active row.
"""
from __future__ import annotations

import json

from context_models.contracts import ContextIntegrityError
from context_models.tennis_live import validate_context_model
from tennis.prediction_revisions import _decode_stored_revision, _revision_digest, utc_epoch


def _read_revision(conn, prediction_id, revision_id=None):
    sql = ("SELECT revision_id,modeled_utc,payload_json FROM prediction_revisions "
           "WHERE prediction_id=?")
    args = [prediction_id]
    if revision_id is not None:
        sql += " AND revision_id=?"
        args.append(revision_id)
    rows = conn.execute(sql + " ORDER BY modeled_utc DESC,revision_id LIMIT 2", args).fetchall()
    if not rows or len(rows) == 2 and rows[0][1] == rows[1][1]:
        raise ContextIntegrityError("native successor needs an unambiguous previous revision")
    ref, modeled, serialized = rows[0]
    payload = _decode_stored_revision(serialized)
    cursor = conn.execute("SELECT * FROM predictions WHERE id=?", (prediction_id,))
    stored = cursor.fetchone()
    if stored is None:
        raise ContextIntegrityError("native successor has no original prediction")
    parent = dict(zip((column[0] for column in cursor.description), stored))
    if (_revision_digest(prediction_id, serialized) != ref
            or utc_epoch(payload["created_utc"]) != utc_epoch(modeled)
            or any(payload.get(field) != parent.get(field) for field in
                   ("player_a", "player_b", "tour", "model_version", "policy_version"))):
        raise ContextIntegrityError("native successor revision integrity mismatch")
    return ref, payload


def _event(revision):
    try:
        linked = validate_context_model(json.loads(revision["context_json"])["context_model"])
        event = linked["event"]
        if (revision["fixture_source"] != "ESPN"
                or event["event_key"] != f"espn:tennis:{revision['tour']}:match:{revision['provider_event_id']}"
                or utc_epoch(linked["cutoff"]) != utc_epoch(revision["created_utc"])
                or utc_epoch(event["scheduled_start"]) != utc_epoch(revision["scheduled_start_utc"])):
            raise ValueError("native identity mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        raise ContextIntegrityError("native successor requires two verified context identities") from exc
    return event


def validate_replacement(previous, successor):
    before, after = _event(previous), _event(successor)
    if not previous.get("append_observed_at"):
        raise ContextIntegrityError("native predecessor has no actual publication receipt")
    stable = ("event_key", "sport", "competition", "format", "tour")
    if (any(before[k] != after[k] for k in stable)
            or {before["home_id"], before["away_id"]} == {after["home_id"], after["away_id"]}
            or utc_epoch(successor["created_utc"]) <= utc_epoch(previous["created_utc"])
            or utc_epoch(successor["created_utc"]) <= utc_epoch(previous["append_observed_at"])):
        raise ContextIntegrityError("native successor is not a later observed opponent replacement")


def replacement_marker(conn, prediction_id, successor):
    ref, previous = _read_revision(conn, prediction_id)
    validate_replacement(previous, successor)
    settled, = conn.execute("SELECT settled FROM predictions WHERE id=?", (prediction_id,)).fetchone()
    if settled:
        raise ContextIntegrityError("a settled native prediction cannot be superseded")
    return {"schema": 1, "prediction_id": prediction_id, "revision_id": ref}


def has_replaced_native_players(conn, prediction_id, successor):
    if not conn.execute("SELECT 1 FROM prediction_revisions WHERE prediction_id=?", (prediction_id,)).fetchone():
        return False
    _, previous = _read_revision(conn, prediction_id)
    context = json.loads(previous.get("context_json") or "{}")
    if "context_model" not in context:
        return False
    before, after = _event(previous), _event(successor)
    return {before["home_id"], before["away_id"]} != {after["home_id"], after["away_id"]}


def superseded_prediction_ids(conn, *, as_of):
    """Resolve first-revision links, including settled successors, as of receipt.

    Keeping the link in the immutable first revision makes later refreshes and
    settlements unable to resurrect the old pair. Audit rows remain readable.
    """
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prediction_revisions'").fetchone():
        return set()
    cutoff, result = utc_epoch(as_of), set()
    rows = conn.execute("""
        SELECT r.prediction_id,r.revision_id,r.modeled_utc,r.payload_json
        FROM prediction_revisions r
        WHERE r.modeled_utc=(SELECT MIN(s.modeled_utc) FROM prediction_revisions s
                            WHERE s.prediction_id=r.prediction_id)
          AND r.modeled_utc<=?
    """, (cutoff,)).fetchall()
    for prediction_id, ref, modeled, serialized in rows:
        first = _decode_stored_revision(serialized)
        if _revision_digest(prediction_id, serialized) != ref or utc_epoch(first["created_utc"]) != modeled:
            raise ContextIntegrityError("native successor first revision integrity mismatch")
        marker = first.get("fixture_successor")
        if marker is None:
            continue
        if (type(marker) is not dict or set(marker) != {"schema", "prediction_id", "revision_id"}
                or type(marker["schema"]) is not int or marker["schema"] != 1
                or type(marker["prediction_id"]) is not int or not 0 < marker["prediction_id"] < prediction_id):
            raise ContextIntegrityError("invalid native successor lineage")
        if utc_epoch(first["append_observed_at"]) > cutoff:
            continue
        _, successor = _read_revision(conn, prediction_id, ref)
        _, previous = _read_revision(conn, marker["prediction_id"], marker["revision_id"])
        validate_replacement(previous, successor)
        parent_clock = conn.execute("SELECT created_utc FROM predictions WHERE id=?", (prediction_id,)).fetchone()[0]
        if utc_epoch(parent_clock) != utc_epoch(successor["created_utc"]):
            raise ContextIntegrityError("native successor must be its parent's first prediction")
        if marker["prediction_id"] in result:
            raise ContextIntegrityError("native prediction has competing successors")
        result.add(marker["prediction_id"])
    return result
