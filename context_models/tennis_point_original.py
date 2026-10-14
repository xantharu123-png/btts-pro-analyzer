"""Same-call POINT originals and native final-score reads, not fitted effects.

The winner-v1 artifact remains unchanged. This separate, bounded artifact
retains the actual joint-law parameters and all simulator distributions. Final
scores are read from the existing physical B1 status/workload pair; no extra
outcome rows, provider calls, name joins, durations or service trials are made.
"""
from copy import deepcopy
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp,
    require_digest, require_number, require_object,
)
from context_models.dataset import _artifact, _reader
from context_models.experiments import _artifact_created_at
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, validate_original_publication
from context_observations import _SELECT, _decode_receipt
from context_sources.tennis import SOURCE_SCHEMA
from context_sources.tennis_status import STATUS_SCHEMA, _select_tennis_row
from model_artifacts import _connect, _insert_artifact, _load_artifact, canonical_bytes, prepare_artifact
from tennis.simulator import POINT_MODEL_VERSION, simulate_match

POINT_ORIGINAL_KIND = "tennis-point-joint-original-v1"
POINT_CAPTURE_KIND = "tennis-point-joint-capture-v1"
POINT_SCORE_KIND = "tennis-point-native-score-read-v1"
MAX_ORIGINAL_BYTES = 32768
MAX_PUBLICATION_BYTES = MAX_ORIGINAL_BYTES+1024
MAX_SCORE_EVENT_KEYS = 500
MAX_ADMITTED_ORIGINALS = 2048
MAX_ADMITTED_BYTES = 128*1024*1024


class PointScoreAdmissionLimit(ContextContractError):
    """Explicit finite read exhaustion, not malformed or corrupted evidence."""
    def __init__(self, detail):
        self.detail = detail
        super().__init__("point original admission exceeds its finite batch budget")


def market_projection(markets):
    """Lossless JSON projection of the actual MatchMarkets, no re-estimation."""
    return {
        "winner_a": markets.p_a_win, "winner_b": markets.p_b_win,
        "best_of": markets.best_of,
        "sets_played": [[n, p] for n, p in sorted(markets.sets_played.items())],
        "correct_scores": [[a, b, p] for (a, b), p in sorted(markets.correct_scores.items())],
        "games_total": [[n, p] for n, p in sorted(markets.games_total.items())],
        "games_diff": [[n, p] for n, p in sorted(markets.games_diff.items())],
        "tiebreak_probability": markets.p_tiebreak_in_match,
        "expected_total_games": markets.expected_total_games,
    }


def point_capture(hold_a, hold_b, best_of, winner_anchor, markets):
    return {"schema": 1, "kind": POINT_CAPTURE_KIND, "model_version": POINT_MODEL_VERSION,
        "params": {"hold_a": hold_a, "hold_b": hold_b, "best_of": best_of,
                   "winner_anchor": winner_anchor}, "markets": market_projection(markets)}


def validate_point_capture(value):
    require_object(value, {"schema", "kind", "model_version", "params", "markets"}, label="point capture")
    if (type(value["schema"]) is not int or value["schema"] != 1
            or value["kind"] != POINT_CAPTURE_KIND or value["model_version"] != POINT_MODEL_VERSION):
        raise ContextContractError("unknown point original contract")
    params = require_object(value["params"], {"hold_a", "hold_b", "best_of", "winner_anchor"}, label="point parameters")
    for side in ("hold_a", "hold_b"):
        require_number(params[side], side, minimum=0, maximum=1)
        if not 0 < params[side] < 1:
            raise ContextContractError("point original requires interior holds")
    require_number(params["winner_anchor"], "actual calibrated anchor", minimum=0, maximum=1)
    if type(params["best_of"]) is not int or params["best_of"] not in (3, 5):
        raise ContextContractError("point original requires actual Bo3/Bo5 model input")
    projection = require_object(value["markets"], {"winner_a", "winner_b", "best_of", "sets_played",
        "correct_scores", "games_total", "games_diff", "tiebreak_probability", "expected_total_games"}, label="point markets")
    for field, width in (("sets_played", 2), ("correct_scores", 3), ("games_total", 2), ("games_diff", 2)):
        rows = projection[field]
        if type(rows) is not list or len(rows) > 128:
            raise ContextContractError("point market projection exceeds its finite support")
        for row in rows:
            if type(row) is not list or len(row) != width or any(type(n) is not int for n in row[:-1]):
                raise ContextContractError("point distribution requires canonical integer support")
            require_number(row[-1], "point market mass", minimum=0, maximum=1)
    for field in ("winner_a", "winner_b", "tiebreak_probability"):
        require_number(projection[field], field, minimum=0, maximum=1)
    require_number(projection["expected_total_games"], "expected total games", minimum=0, maximum=65)
    if type(projection["best_of"]) is not int or projection["best_of"] != params["best_of"]:
        raise ContextContractError("point market format differs from executed input")
    if len(canonical_bytes(value)) > MAX_ORIGINAL_BYTES:
        raise ContextContractError("point original exceeds its bounded storage contract")
    replay = simulate_match(params["hold_a"], params["hold_b"], best_of=params["best_of"], strict=True,
        model_version=POINT_MODEL_VERSION, winner_probability=params["winner_anchor"])
    if canonical_bytes(market_projection(replay)) != canonical_bytes(projection):
        raise ContextIntegrityError("point original markets differ from its actual joint law")
    return deepcopy(value)


def _require_capture_source_family(origin):
    from context_runtime_tennis import (
        _REVIEWED_POINT_CAPTURE_MANIFEST, _REVIEWED_CACHED_POINT_CAPTURE_MANIFEST,
    )
    if not any(all(origin["code_hashes"][name] in hashes for name, hashes in manifest.items())
               for manifest in (_REVIEWED_POINT_CAPTURE_MANIFEST, _REVIEWED_CACHED_POINT_CAPTURE_MANIFEST)):
        raise ContextIntegrityError("point original lacks its actual capture source family")


def publish_point_original(path, *, winner_original_hash, origin, capture, state, clock):
    """Owning live worker only: bind the same-call capture to verified A1/B1."""
    if not callable(clock):
        raise ContextContractError("point publication requires its owning actual clock")
    require_digest(winner_original_hash, "winner original")
    capture = validate_point_capture(capture)
    params, inputs = capture["params"], origin["inputs"]
    if (state.market_model_version != POINT_MODEL_VERSION or state.artifact_hash != origin["state_hash"]
            or params["best_of"] != inputs["best_of"]
            or params["winner_anchor"] != round(origin["values"]["p_a_cal"], 4)):
        raise ContextIntegrityError("point original differs from the actually used winner/state")
    holds = state.serve.expected_hold_probabilities(inputs["state_key_a"], inputs["state_key_b"],
        inputs["surface"], as_of=datetime.fromisoformat(origin["cutoff"]), indoor=inputs["indoor"])
    if canonical_bytes(list(holds)) != canonical_bytes([params["hold_a"], params["hold_b"]]):
        raise ContextIntegrityError("point holds differ from the actually used frozen state")
    with _reader(path) as connection:
        envelope = _load_artifact(connection, winner_original_hash)
        published = _artifact_created_at(connection, winner_original_hash)
    if (envelope["kind"] != ORIGINAL_ARTIFACT_KIND
            or canonical_bytes(envelope["payload"]["origin"]) != canonical_bytes(origin)):
        raise ContextIntegrityError("point original has no identical physical winner original")
    validate_original_publication(envelope["payload"], created_at=published)
    _require_capture_source_family(origin)
    payload = {"schema": 1, "event_key": origin["event"]["event_key"],
        "winner_original_hash": winner_original_hash, "capture": capture}
    prepared = prepare_artifact(kind=POINT_ORIGINAL_KIND, payload=payload)
    # Preparation/replay can be slow. The earlier winner clock cannot stand
    # in for this separate physical insert; sample only after it completes.
    with closing(_connect(Path(path))) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            if canonical_bytes(_load_artifact(connection, winner_original_hash)) != canonical_bytes(envelope):
                raise ContextIntegrityError("physical point owner changed during preparation")
            published = _artifact_created_at(connection, winner_original_hash)
            actual = clock()
            if not isinstance(actual, datetime) or actual.utcoffset() is None:
                raise ContextContractError("point publication needs an aware actual writer clock")
            created = canonical_timestamp(actual)
            if created < published:
                raise ContextIntegrityError("point writer clock precedes its physical owner")
            if created >= origin["event"]["scheduled_start"]:
                connection.rollback()
                return None  # Retain all existing Winner/Shadow publications.
            stored_at, _ = _insert_artifact(connection, prepared, created)
            stored_at = canonical_timestamp(stored_at)
            if not published <= stored_at <= created or stored_at >= origin["event"]["scheduled_start"]:
                raise ContextIntegrityError("physical point publication clock differs from its owner")
            connection.commit()
            return prepared.digest
        except BaseException:
            connection.rollback()
            raise


def _read_original(connection, ref, states):
    envelope = _load_artifact(connection, ref)
    if envelope["kind"] != POINT_ORIGINAL_KIND:
        raise ContextIntegrityError("not an owning point original")
    payload = require_object(envelope["payload"], {"schema", "event_key", "winner_original_hash", "capture"}, label="point original")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ContextContractError("unknown point publication version")
    require_digest(payload["winner_original_hash"], "physical winner original")
    winner = _load_artifact(connection, payload["winner_original_hash"])
    if winner["kind"] != ORIGINAL_ARTIFACT_KIND:
        raise ContextIntegrityError("point original references a non-winner artifact")
    published = _artifact_created_at(connection, payload["winner_original_hash"])
    validate_original_publication(winner["payload"], created_at=published)
    origin = winner["payload"]["origin"]
    _require_capture_source_family(origin)
    if payload["event_key"] != origin["event"]["event_key"]:
        raise ContextIntegrityError("point native event admission differs from its physical owner")
    created = _artifact_created_at(connection, ref)
    if not origin["cutoff"] <= published <= created < origin["event"]["scheduled_start"]:
        raise ContextIntegrityError("point/winner original physical chronology differs")
    # Full closed Winner source-family/state/value replay follows below; a
    # simulator/serve-only identity cannot establish the executed anchor.
    capture = validate_point_capture(payload["capture"])
    if (capture["params"]["best_of"] != origin["inputs"]["best_of"]
            or capture["params"]["winner_anchor"] != round(origin["values"]["p_a_cal"], 4)):
        raise ContextIntegrityError("point capture and winner anchor differ")
    from tennis.tour_state import _decode_wrapper
    key = origin["state_hash"], origin["event"]["tour"]
    if key not in states:
        state_artifact = _artifact(connection, key[0], "tennis-tour-state", latest=origin["cutoff"])
        states[key] = (_decode_wrapper(state_artifact["payload"], key[1]), _artifact_created_at(connection, key[0]))
    state, state_created = states[key]
    if (state.market_model_version != POINT_MODEL_VERSION or state_created > origin["cutoff"]
            or state.built_at > datetime.fromisoformat(origin["cutoff"]).timestamp()):
        raise ContextIntegrityError("point original has no causal immutable point-model state")
    inputs, params = origin["inputs"], capture["params"]
    holds = state.serve.expected_hold_probabilities(inputs["state_key_a"], inputs["state_key_b"],
        inputs["surface"], as_of=datetime.fromisoformat(origin["cutoff"]), indoor=inputs["indoor"])
    if canonical_bytes(list(holds)) != canonical_bytes([params["hold_a"], params["hold_b"]]):
        raise ContextIntegrityError("point original holds do not replay from its immutable state")
    from context_sources.tennis_outcome_capture import _native_binding
    _native_binding(connection, origin)
    from context_runtime_tennis import replay_live_winner_calculation
    prediction = replay_live_winner_calculation(origin, state)
    if (prediction.markets is None
            or canonical_bytes(market_projection(prediction.markets)) != canonical_bytes(capture["markets"])):
        raise ContextIntegrityError("point original differs from the actual full Winner/POINT calculation")
    return origin, capture, created


def verify_point_originals(connection, artifacts, winner_originals):
    """D4 owns every physical POINT publication, including safe orphans.

    The caller's full Winner inventory is already verified; no slot, snapshot,
    retirement or outcome can exempt an inactive POINT artifact from replay.
    This stays in the same held read-only transaction and never opens a path.
    """
    states = {}
    for ref, envelope in artifacts.items():
        if envelope["kind"] != POINT_ORIGINAL_KIND:
            continue
        _read_original(connection, ref, states)
        owner = envelope["payload"]["winner_original_hash"]
        if owner not in winner_originals:
            raise ContextIntegrityError("point original lacks its fully verified physical Winner owner")


def _native_score(connection, ref, *, as_of, states):
    origin, capture, created = _read_original(connection, ref, states)
    if created > as_of:
        return None
    event = origin["event"]
    from tennis.forecast_retirements import original_is_retired
    owner = _load_artifact(connection, ref)["payload"]["winner_original_hash"]
    if original_is_retired(owner, event["event_key"]):
        return None
    raw = connection.execute(_SELECT + " WHERE r.event_key=? AND r.kind='event_status' AND r.observed_at<=?"
        " ORDER BY r.observed_at DESC,r.digest LIMIT 2", (event["event_key"], as_of)).fetchall()
    rows = [_decode_receipt(row) for row in raw]
    if not rows or len(rows) == 2 and rows[0]["observed_at"] == rows[1]["observed_at"]:
        return None
    status = _select_tennis_row(rows[0], as_of, event["tour"])
    if status is None or status["source_schema"] != STATUS_SCHEMA:
        return None
    data = status["payload"]
    if (data["status"] != "completed" or data["issues"] or status["competition"] != event["competition"]
            or set(data["participant_ids"]) != {event["home_id"], event["away_id"]}
            or any(data["native_status"][key] for key in ("retired", "walkover", "unsupported"))
            or not created < min(event["scheduled_start"], data["scheduled_start"]) < status["observed_at"]):
        return None
    pair = []
    for receipt in data["workload_receipts"]:
        raw = connection.execute(_SELECT + " WHERE r.digest=?", (receipt,)).fetchone()
        if raw is None:
            raise ContextIntegrityError("point score lacks its actual native workload pair")
        row = _select_tennis_row(_decode_receipt(raw), as_of, event["tour"])
        if (row is None or row["source_schema"] != SOURCE_SCHEMA or row["event_key"] != event["event_key"]
                or row["competition"] != event["competition"] or row["observed_at"] != status["observed_at"]
                or row["schedule_revision"] != status["schedule_revision"]
                or row["payload"]["status"] != "completed" or row["payload"]["incomplete_match"]):
            raise ContextIntegrityError("point final and paired native workload disagree")
        pair.append(row)
    if len(pair) != 2 or {row["subject_id"] for row in pair} != {event["home_id"], event["away_id"]}:
        raise ContextIntegrityError("point score needs both exact native participants")
    home = next(row["payload"] for row in pair if row["subject_id"] == event["home_id"])
    away = next(row["payload"] for row in pair if row["subject_id"] == event["away_id"])
    if (home["opponent_id"] != event["away_id"] or away["opponent_id"] != event["home_id"]
            or home["set_scores"] != [{"a": s["b"], "b": s["a"], "completed": s["completed"]}
                for s in away["set_scores"]]):
        raise ContextIntegrityError("native final score orientations disagree")
    scores, wins = [], [0, 0]
    needed = (capture["params"]["best_of"]+1)//2
    for item in home["set_scores"]:
        a, b = item["a"], item["b"]
        if (max(wins) == needed or item["completed"] is not True or type(a) is not int or type(b) is not int
                or not (max(a, b) == 6 and min(a, b) <= 4 or max(a, b) == 7 and min(a, b) in (5, 6))):
            return None
        scores.append({"home": a, "away": b})
        wins[int(b > a)] += 1
    if max(wins) != needed or min(wins) >= needed:
        return None
    winner_id = event["home_id" if wins[0] > wins[1] else "away_id"]
    # Normal score totals cannot replace a missing/conflicting native winner
    # flag. Reuse its existing v1 receipt, without adding another outcome row.
    from context_sources.outcomes import TENNIS_WINNER_OUTCOME, validate_outcome_record
    admission = connection.execute("SELECT count(*),coalesce(sum(length(c.payload)),0),"
        "coalesce(sum(typeof(c.payload)!='blob'),0) FROM context_observations r "
        "LEFT JOIN context_contents c ON c.content_digest=r.content_digest "
        "WHERE r.event_key=? AND r.kind='match_outcome' AND r.observed_at=?",
        (event["event_key"], status["observed_at"])).fetchone()
    if admission[0] > 64 or admission[1] > 64*1024 or admission[2]:
        raise ContextIntegrityError("point native winner admission exceeds its bounded source contract")
    labels = []
    for raw in connection.execute(_SELECT + " WHERE r.event_key=? AND r.kind='match_outcome' AND r.observed_at=?",
            (event["event_key"], status["observed_at"])):
        row = _decode_receipt(raw)
        payload = row["payload"]
        if (payload.get("outcome_contract") != TENNIS_WINNER_OUTCOME
                or payload.get("home_id") != event["home_id"] or payload.get("away_id") != event["away_id"]
                or payload.get("scheduled_start") != event["scheduled_start"]):
            continue
        selected = {**row, "evidence_class": "prospective", "effective_at": row["observed_at"],
            "publication_resolution": None}
        validate_outcome_record(selected, event=event)
        if payload.get("reported_scheduled_start", payload["scheduled_start"]) != data["scheduled_start"]:
            continue
        labels.append(row)
    if len(labels) != 1 or labels[0]["payload"]["result"]["winner_id"] != winner_id:
        return None
    return {"schema": 1, "kind": POINT_SCORE_KIND, "original_hash": ref,
        "event": deepcopy(event), "status_receipt": status["digest"],
        "workload_receipts": sorted(row["digest"] for row in pair),
        "winner_receipt": labels[0]["digest"],
        "observed_at": status["observed_at"], "reported_scheduled_start": data["scheduled_start"],
        "native_best_of": None, "model_best_of": capture["params"]["best_of"],
        "result": {"winner_id": winner_id, "set_scores": scores}}


def read_point_score(path, original_hash, *, as_of):
    """Read the newest causal native revision, never an old convenient final."""
    require_digest(original_hash, "point original")
    cutoff = canonical_timestamp(as_of)
    with _reader(path) as connection:
        return _native_score(connection, original_hash, as_of=cutoff, states={})


def point_scores_as_of(path, *, as_of, event_keys):
    """Owning daily completion reads the small typed catalog, not all history."""
    cutoff = canonical_timestamp(as_of)
    def native_key(key):
        if type(key) is not str:
            return False
        parts = key.split(":")
        return (len(parts) == 5 and parts[:2] == ["espn", "tennis"] and parts[2] in ("ATP", "WTA")
            and parts[3] == "match" and parts[4].isascii() and parts[4].isdecimal()
            and str(int(parts[4])) == parts[4] and int(parts[4]) > 0)
    if (type(event_keys) is not set or len(event_keys) > MAX_SCORE_EVENT_KEYS
            or any(not native_key(key) for key in event_keys)):
        raise ContextContractError("point score collection requires explicit native event scopes")
    if not event_keys or not Path(path).exists():
        return ()
    with _reader(path) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifacts'").fetchone():
            return ()
        # Admit only compact headers for explicit received event scopes before
        # returning any BLOB to Python. Oversized bodies never reach JSON decode.
        if connection.execute("SELECT 1 FROM artifacts WHERE kind=? "
                "AND (typeof(payload)!='blob' OR length(payload)=0 OR length(payload)>?) LIMIT 1",
                (POINT_ORIGINAL_KIND, MAX_PUBLICATION_BYTES)).fetchone():
            raise ContextIntegrityError("invalid point original admission header")
        slots = ",".join("?" for _ in event_keys)
        try:
            headers = connection.execute("SELECT digest,length(payload),typeof(payload) FROM artifacts "
                "WHERE kind=? AND created_at<=? AND CASE WHEN typeof(payload)='blob' AND length(payload)<=? "
                "THEN json_extract(CAST(payload AS TEXT),'$.event_key') ELSE NULL END IN ("+slots+") "
                "ORDER BY digest LIMIT ?", (POINT_ORIGINAL_KIND, cutoff, MAX_PUBLICATION_BYTES,
                *sorted(event_keys), MAX_ADMITTED_ORIGINALS+1)).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ContextIntegrityError("invalid point original admission metadata") from exc
        if len(headers) > MAX_ADMITTED_ORIGINALS:
            # The bounded query intentionally reads only limit+1 headers, so
            # this is a lower bound, never a claimed complete original count.
            raise PointScoreAdmissionLimit({"reason": "original_count_limit_exceeded",
                "original_count_at_least": len(headers), "limit": MAX_ADMITTED_ORIGINALS})
        admitted_bytes = sum(row[1] for row in headers)
        if admitted_bytes > MAX_ADMITTED_BYTES:
            raise PointScoreAdmissionLimit({"reason": "original_bytes_limit_exceeded",
                "original_bytes": admitted_bytes, "limit": MAX_ADMITTED_BYTES})
        refs = []
        for ref, size, storage in headers:
            require_digest(ref, "point original admission digest")
            if type(size) is not int or storage != "blob" or not 0 < size <= MAX_PUBLICATION_BYTES:
                raise ContextIntegrityError("invalid point original admission header")
            refs.append(ref)
        states = {}
        return tuple(score for ref in refs if (score := _native_score(connection, ref, as_of=cutoff, states=states)) is not None)
