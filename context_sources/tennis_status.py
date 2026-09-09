"""Closed native ESPN competition receipts, including withdrawal revisions.

This source owns only already received scoreboard fields. It does not fetch,
infer player identities, diagnose availability, or infer real match clocks.
Workload-v1 remains unchanged; status-v1 binds its two actual receipt hashes.
"""
from contextlib import closing
from datetime import datetime
from pathlib import Path
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, OBSERVATION_FIELDS,
    canonical_timestamp, digest, normalize_observation, require_digest,
    require_list, require_object, require_text,
)
from context_sources.tennis import SOURCE_SCHEMA, _id, normalize_tennis_workload, validate_workload_record
from model_artifacts import canonical_bytes


STATUS_SCHEMA = "espn-tennis-event-status-v1"
_PAYLOAD = {"tour", "tournament_id", "participant_ids", "scheduled_start", "grouping_slug",
    "native_status", "status", "issues", "workload_receipts", "competition_revision"}
_NATIVE_STATUS = {"state", "name", "completed", "retired", "walkover", "cancelled", "unsupported", "malformed"}
_ISSUES = {"invalid-participants", "invalid-schedule", "invalid-tournament", "invalid-status",
    "unsupported-format", "unsupported-terminal", "terminal-workload-unavailable"}
_TOURNAMENT = re.compile(r"[1-9][0-9]*(?:-[1-9][0-9]*)?\Z")
_SLUGS = {"ATP": "mens-singles", "WTA": "womens-singles"}
_CANCEL_CODES = {"STATUS_CANCELED", "STATUS_CANCELLED"}


def _tour(tour):
    if type(tour) is not str or tour not in _SLUGS:
        raise ContextContractError("tennis status requires actual ATP/WTA request scope")
    return tour


def _native_status(comp):
    raw = comp.get("status")
    native = raw.get("type") if type(raw) is dict else None
    malformed = type(native) is not dict
    native = native if type(native) is dict else {}
    result = {}
    for name in ("state", "name"):
        value = native.get(name)
        try:
            result[name] = require_text(value, "native status " + name, code=True)
        except ContextContractError:
            result[name], malformed = None, True
    value = native.get("completed")
    result["completed"] = value if type(value) is bool else None
    malformed |= type(value) is not bool
    text = " ".join(value for key in ("name", "description", "detail", "shortDetail")
                    if type(value := native.get(key)) is str)
    notes = comp.get("notes", [])
    if type(notes) is list:
        text += " " + " ".join(note["text"] for note in notes if type(note) is dict and type(note.get("text")) is str)
    text = text.casefold()
    result.update(retired=any(token in text for token in ("retired", "retirement", "ret.", "ret'd")),
                  walkover=any(token in text for token in ("walkover", "w/o", "walk-over")),
                  cancelled=result["name"] in _CANCEL_CODES,
                  unsupported=any(token in text for token in ("abandoned", "defaulted")), malformed=malformed)
    return result


def _status(native):
    if native["malformed"]:
        return "unknown"
    if native["cancelled"]:
        return "cancelled"
    if native["unsupported"] or native["retired"] and native["walkover"]:
        return "unknown"
    if native["state"] == "pre" and native["completed"] is False:
        return "scheduled"
    if native["state"] == "in" and native["completed"] is False:
        return "started"
    if native["state"] == "post" and native["completed"] is True:
        if native["retired"] or native["walkover"] or native["name"] == "STATUS_FINAL":
            return "completed"
    return "unknown"


def _core_issues(payload):
    issues = []
    players = payload["participant_ids"]
    if len(players) != 2 or None in players or players[0] == players[1]:
        issues.append("invalid-participants")
    if payload["scheduled_start"] is None:
        issues.append("invalid-schedule")
    if payload["tournament_id"] is None:
        issues.append("invalid-tournament")
    if payload["grouping_slug"] != _SLUGS[payload["tour"]]:
        issues.append("unsupported-format")
    if payload["native_status"]["malformed"]:
        issues.append("invalid-status")
    if payload["status"] == "unknown" and not payload["native_status"]["malformed"]:
        issues.append("unsupported-terminal")
    return issues


def _record(payload, event_key, clock):
    # 'unresolved' is an explicit missing tournament, never a verified alias.
    tournament = payload["tournament_id"] or "unresolved"
    return normalize_observation({"event_key": event_key, "sport": "tennis",
        "competition": f"espn:{payload['tour']}:tournament:{tournament}",
        "format": "singles" if payload["grouping_slug"] == _SLUGS[payload["tour"]] else "unsupported",
        "subject_id": event_key, "kind": "event_status", "source": "espn", "source_schema": STATUS_SCHEMA,
        "source_revision": digest(payload),
        "schedule_revision": digest({"event_key": event_key, "scheduled_start": payload["scheduled_start"]}),
        "published_at": None, "publication_proof": None, "valid_from": canonical_timestamp(clock),
        "valid_until": None, "complete": False, "payload": payload}, observed_at=clock)


def normalize_tennis_status(tour: str, tournament_id, competition: dict, *, grouping_slug,
                            observed_at: datetime) -> tuple[dict, ...]:
    """Status FIRST, then an inseparable bilateral terminal projection if known.

    A native event with defective participant/schedule fields retains a closed
    unknown revision. It cannot borrow the missing fields from an older reply.
    The digest binds normalized sport fields only, not prices or display names.
    """
    _tour(tour)
    if not isinstance(observed_at, datetime) or type(competition) is not dict:
        raise ContextContractError("tennis status requires competition and actual receipt datetime")
    clock = canonical_timestamp(observed_at)
    event_key = f"espn:tennis:{tour}:match:{_id(competition.get('id'))}"
    tournament = tournament_id if type(tournament_id) is str and _TOURNAMENT.fullmatch(tournament_id) else None
    slug = grouping_slug if type(grouping_slug) is str and re.fullmatch(r"[a-z]+(?:-[a-z]+)*", grouping_slug) else None
    participants = []
    raw_players = competition.get("competitors")
    if type(raw_players) is list:
        for raw in raw_players:
            try:
                player = _id(raw.get("id") if type(raw) is dict else None)
                participants.append(f"espn:tennis:{tour}:player:{player}")
            except ContextContractError:
                participants.append(None)
    try:
        scheduled = canonical_timestamp(competition.get("date")) if type(competition.get("date")) is str else None
    except ContextContractError:
        scheduled = None
    native = _native_status(competition)
    payload = {"tour": tour, "tournament_id": tournament, "participant_ids": participants,
        "scheduled_start": scheduled, "grouping_slug": slug, "native_status": native,
        "status": _status(native), "issues": [], "workload_receipts": []}
    issues = _core_issues(payload)
    workload = ()
    if not issues and payload["status"] == "completed":
        try:
            workload = normalize_tennis_workload(({"source_schema": "espn-scoreboard-v1", "tour": tour,
                "tournament_id": tournament, "competition": competition},), observed_at=observed_at)
        except (ContextContractError, TypeError, ValueError, OverflowError, KeyError):
            workload = ()
        if len(workload) != 2:
            workload = ()
            issues.append("terminal-workload-unavailable")
    payload["issues"] = sorted(issues)
    payload["workload_receipts"] = sorted(digest({"content_digest": digest(row), "observed_at": clock}) for row in workload)
    payload["competition_revision"] = digest({"version": "espn-tennis-competition-reception-v1",
        "event_key": event_key, "observed_at": clock, "projection": payload})
    status = _record(payload, event_key, observed_at)
    validate_tennis_status_record({**status, "observed_at": clock})
    return (status, *workload)


def validate_tennis_status_record(row: dict) -> dict:
    payload = require_object(row["payload"], _PAYLOAD, label="native tennis status projection")
    tour = _tour(payload["tour"])
    prefix = f"espn:tennis:{tour}:match:"
    if type(row["event_key"]) is not str or not row["event_key"].startswith(prefix):
        raise ContextContractError("tennis status native event scope differs")
    _id(row["event_key"][len(prefix):])
    native = require_object(payload["native_status"], _NATIVE_STATUS, label="projected native status")
    for name in ("state", "name"):
        if native[name] is not None:
            require_text(native[name], "native " + name, code=True)
    if native["completed"] is not None and type(native["completed"]) is not bool:
        raise ContextContractError("native completed flag must be boolean or unknown")
    for name in _NATIVE_STATUS - {"state", "name", "completed"}:
        if type(native[name]) is not bool:
            raise ContextContractError("native status classification flags must be boolean")
    if native["malformed"] != any(native[name] is None for name in ("state", "name", "completed")):
        raise ContextContractError("native status missing fields were concealed")
    if native["cancelled"] != (native["name"] in _CANCEL_CODES):
        raise ContextContractError("cancellation requires its actual native status code")
    players = require_list(payload["participant_ids"], "native status participants")
    player_prefix = f"espn:tennis:{tour}:player:"
    for player in players:
        if player is not None:
            if type(player) is not str or not player.startswith(player_prefix):
                raise ContextContractError("native status participant tour differs")
            _id(player[len(player_prefix):])
    tournament = payload["tournament_id"]
    if tournament is not None and (type(tournament) is not str or not _TOURNAMENT.fullmatch(tournament)):
        raise ContextContractError("native status tournament is invalid")
    if payload["grouping_slug"] is not None and (type(payload["grouping_slug"]) is not str or
            not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", payload["grouping_slug"])):
        raise ContextContractError("native grouping projection is invalid")
    if payload["scheduled_start"] is not None and (type(payload["scheduled_start"]) is not str or
            canonical_timestamp(payload["scheduled_start"]) != payload["scheduled_start"]):
        raise ContextContractError("native status schedule is not canonical")
    refs = require_list(payload["workload_receipts"], "paired workload receipts")
    for ref in refs:
        require_digest(ref)
    if refs != sorted(set(refs)) or len(refs) not in (0, 2):
        raise ContextContractError("native status needs zero or two exact workload receipts")
    if payload["status"] != _status(native):
        raise ContextContractError("native status classification differs from projection")
    issues = require_list(payload["issues"], "native status issues")
    if any(type(issue) is not str or issue not in _ISSUES for issue in issues) or issues != sorted(set(issues)):
        raise ContextContractError("unknown native tennis status issue")
    expected_issues = _core_issues(payload)
    if not expected_issues and payload["status"] == "completed" and not refs:
        expected_issues.append("terminal-workload-unavailable")
    if issues != sorted(expected_issues) or refs and (issues or payload["status"] != "completed"):
        raise ContextContractError("native tennis status coverage is inconsistent")
    clock = canonical_timestamp(row["observed_at"])
    projection = {key: value for key, value in payload.items() if key != "competition_revision"}
    expected = digest({"version": "espn-tennis-competition-reception-v1", "event_key": row["event_key"],
                       "observed_at": clock, "projection": projection})
    if payload["competition_revision"] != expected:
        raise ContextIntegrityError("native competition reception identity differs")
    if canonical_bytes(_record(payload, row["event_key"], datetime.fromisoformat(clock))) != canonical_bytes({key: row[key] for key in OBSERVATION_FIELDS}):
        raise ContextIntegrityError("native tennis status envelope binding differs")
    return payload


def validate_selected_tennis_receipt(row: dict) -> dict:
    """Validate actual selected B1 transport before using any source field."""
    require_object(row, set(OBSERVATION_FIELDS) | {"digest", "content_digest", "observed_at",
        "evidence_class", "effective_at", "publication_resolution"}, label="selected tennis receipt")
    clock = canonical_timestamp(row["observed_at"])
    content = {key: row[key] for key in OBSERVATION_FIELDS}
    normalized = normalize_observation(content, observed_at=datetime.fromisoformat(clock))
    if (clock != row["observed_at"] or canonical_bytes(content) != canonical_bytes(normalized)
            or digest(content) != row["content_digest"]
            or digest({"content_digest": row["content_digest"], "observed_at": clock}) != row["digest"]):
        raise ContextIntegrityError("selected tennis receipt/content identity differs")
    if (row["evidence_class"] != "prospective" or row["effective_at"] != clock
            or row["publication_resolution"] is not None):
        raise ContextContractError("tennis status v3 consumes actual prospective receipts only")
    if row["source"] != "espn" or row["sport"] != "tennis":
        raise ContextContractError("tennis status source differs")
    if row["source_schema"] == STATUS_SCHEMA:
        validate_tennis_status_record(row)
    elif row["source_schema"] == SOURCE_SCHEMA:
        if row["kind"] != "workload" or row["format"] != "singles":
            raise ContextContractError("legacy workload kind/format mismatch")
        validate_workload_record(row)
    else:
        raise ContextContractError("unknown tennis source schema")
    return row


def tennis_observations_as_of(path: Path, *, cutoff: datetime, tour: str) -> tuple[dict, ...]:
    """Whole causal tour history BEFORE event/schedule/participant projection.

    Uses existing B1 identity validation, no latest-per-subject pruning or
    archive promotion. Missing DB stays absent. This is an owning worker read,
    not the sealed read-only D4 verifier or proof of complete player history.
    """
    from context_observations import _connect, _decode_receipt, _SELECT
    _tour(tour)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("tennis reader needs an actual cutoff datetime")
    decision = canonical_timestamp(cutoff)
    path = Path(path)
    if not path.exists():
        return ()
    with closing(_connect(path)) as connection:
        connection.execute("BEGIN")
        # Decode before scope pruning: an altered outer index cannot hide a
        # correction which remains in the actual B1 inventory.
        rows = [_decode_receipt(stored) for stored in connection.execute(_SELECT)]
        connection.commit()
    result = []
    for row in rows:
        if row["observed_at"] > decision or row["source_schema"] not in {STATUS_SCHEMA, SOURCE_SCHEMA}:
            continue
        selected = {**row, "evidence_class": "prospective", "effective_at": row["observed_at"], "publication_resolution": None}
        validate_selected_tennis_receipt(selected)
        if row["payload"]["tour"] == tour:
            result.append(selected)
    return tuple(sorted(result, key=lambda row: (row["observed_at"], row["digest"])))
