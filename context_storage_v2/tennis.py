"""Explicit, disk-backed execution of the unchanged Tennis v3 feature rules.

This is not a tuple adapter or a proof cache. Every selected source receipt is
validated before event/player projection. Event groups and output references
are repeatable disk streams; the complete tour and arbitrarily large revision
groups are never collected in Python. The legacy modules remain the oracle.

The result deliberately is NOT a legacy FeatureVector with truncated refs.
Its numeric header is small, while refs have their complete v2 block identity.
Legacy materialization requires an explicit bounded operation. Callers must
keep the owning HistoryView and this result open until consumption completes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import stat
from types import MappingProxyType

from context_models.contracts import (
    ContextContractError, canonical_timestamp, validate_base_distribution,
    validate_event, validate_feature_vector,
)
from context_models.tennis import (
    METRICS, WINDOWS, _instant, _joint_match_identity, _usable_history,
    recovery_bounds,
)
from context_models.tennis_v3 import (
    COVERAGE_VERSION, FEATURE_VERSION, tennis_reference_hash_v3,
)
from context_sources.tennis import SOURCE_SCHEMA
from context_sources.tennis_status import (
    STATUS_SCHEMA, _validate_selected_tennis_receipt_cold,
)
from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import (
    DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits,
)
from context_storage_v2.history import (
    _configure_read_connection, _private_build_directory, _read_policy_epoch,
)
from context_storage_v2.sqlite_profile import SQLiteWriterPlan, open_fresh_writer
from model_artifacts import canonical_bytes


FORMAT_VERSION = "context-tennis-features-stream-v2"
# This is an additional cap of this NEW optional helper. It is not the existing
# legacy input/cache budget and does not claim a pre-existing FeatureVector cap.
MAX_MATERIALIZATION_BYTES = 64 * 1024**2
_RESULT_TOKEN = object()


def _stamp(path: Path) -> tuple:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise StorageIntegrityError("Tennis result must be one private regular file")
    return (info.st_dev, info.st_ino, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _ensure_space(directory: Path, limits: StorageLimits) -> None:
    if shutil.disk_usage(directory).free < limits.min_free_bytes:
        raise StorageLimitError("Tennis processing would consume the reserved free space")


def _read_storage_epoch(connection):
    # DDL changes neither total_changes nor necessarily the file mtime while
    # the transaction remains open. Journal/TEMP changes also need a binding.
    pragmas = tuple(sqlite3.Connection.execute(connection, statement).fetchone()[0]
                   for statement in ("PRAGMA main.schema_version", "PRAGMA temp.schema_version",
                       "PRAGMA main.journal_mode", "PRAGMA temp.journal_mode",
                       "PRAGMA main.max_page_count", "PRAGMA main.cache_size",
                       "PRAGMA main.mmap_size", "PRAGMA temp_store", "PRAGMA threads"))
    return (pragmas, tuple(sqlite3.Connection.execute(connection, "PRAGMA database_list")),
            _read_policy_epoch(connection))


def _limits_identity(limits):
    if type(limits) is not StorageLimits:
        raise StorageLimitError("published Tennis output needs the exact C limits")
    StorageLimits.__post_init__(limits)
    return tuple((field.name, getattr(limits, field.name)) for field in fields(StorageLimits))


def _row(blob: bytes) -> dict:
    # These are this owner's canonical, already fully validated private rows,
    # not an alternative decoder for untrusted input database payloads.
    return json.loads(blob)


def _participants(row):
    payload = row["payload"]
    if row["source_schema"] == STATUS_SCHEMA:
        # Do not build a union of all historical (possibly defective) players.
        return payload["participant_ids"]
    return (payload["player_id"], payload["opponent_id"])


def _target_state(group, event):
    if group is None:
        return None, ()
    has_status = False
    for row in group.iter_rows():
        has_status |= row["source_schema"] == STATUS_SCHEMA
    if not has_status:
        return None, ()
    head, count = None, 0
    for row in group.iter_latest_rows():
        if row["source_schema"] == STATUS_SCHEMA:
            count += 1
            if count == 1:
                head = row
    if count > 1:
        return "conflicting", ()
    if head is None:
        return "missing", ()
    payload = head["payload"]
    if payload["status"] in {"started", "completed", "cancelled"}:
        return "not_applicable", ()
    if (payload["status"] != "scheduled" or payload["issues"]
            or head["competition"] != event["competition"]
            or payload["scheduled_start"] != event["scheduled_start"]
            or set(payload["participant_ids"]) != {event["home_id"], event["away_id"]}):
        return "missing", ()
    return None, (head["digest"],)


def _legacy_pair(group, *, cutoff, next_start):
    """Resolve a whole latest legacy group with constant-size summaries.

    Equal joint identities fix the full validated source envelope except the
    two bilateral projections. Thus one representative per player suffices for
    the original factor owner, but differing identities are never coalesced.
    Every latest row is inspected even after a conflict is known.
    """
    players, joint, representatives = None, None, {}
    conflict = False
    for row in group.iter_latest_rows():
        payload = row["payload"]
        pair = frozenset((payload["player_id"], payload["opponent_id"]))
        identity = _joint_match_identity(row)
        if players is None:
            players, joint = pair, identity
        if pair != players or identity != joint:
            conflict = True
            continue
        previous = representatives.get(row["subject_id"])
        if previous is not None and previous["content_digest"] != row["content_digest"]:
            # The unchanged factor owner rejects same-source simultaneous
            # differing content; do not turn it into a duplicate page.
            conflict = True
        if previous is None or row["digest"] < previous["digest"]:
            representatives[row["subject_id"]] = row
    if conflict:
        return (), True
    if players is None or set(representatives) != players:
        return (), False
    # This is a genuine, bounded tuple of actual validated source rows, NOT a
    # stand-in for the complete HistoryView or an arbitrarily pruned group.
    pair = tuple(representatives.values())
    usable, conflicts = _usable_history(pair, cutoff=cutoff, next_start=next_start)
    return tuple(usable), bool(conflicts)


def _paired_status(group, participants):
    head, head_count = None, 0
    for row in group.iter_latest_rows():
        if row["source_schema"] == STATUS_SCHEMA:
            head_count += 1
            if head_count == 1:
                head = row
    if head_count > 1:
        return (), (), "conflicting"
    if head is None or not head["payload"]["workload_receipts"]:
        return (), (), "missing"
    payload = head["payload"]
    required = set(payload["workload_receipts"])  # validated size exactly two
    actual, pair, extra = set(), [], False
    for row in group.iter_latest_rows():
        if row["source_schema"] != SOURCE_SCHEMA:
            continue
        if row["digest"] not in required:
            extra = True
        else:
            actual.add(row["digest"])
            pair.append(row)  # at most the two exact required receipt keys
    if extra:
        return (), (), "conflicting"
    if actual != required:
        return (), (), "missing"
    players = set(payload["participant_ids"])
    terminal = ("walkover" if payload["native_status"]["walkover"] else
                "retired" if payload["native_status"]["retired"] else "completed")
    coherent = (len(pair) == 2 and {row["subject_id"] for row in pair} == players
        and len({_joint_match_identity(row) for row in pair}) == 1
        and all(row["competition"] == head["competition"]
            and row["schedule_revision"] == head["schedule_revision"]
            and row["payload"]["status"] == terminal
            and row["payload"]["scheduled_start"] == payload["scheduled_start"]
            and row["payload"]["result_observed_at"] == head["observed_at"]
            and all(row["payload"][field] is None
                    for field in ("actual_start", "actual_end", "minutes"))
            for row in pair))
    if not coherent:
        return (), (), "conflicting"
    if not players & participants:
        return (), (), "removed"
    return tuple(pair), tuple(sorted(required | {head["digest"]})), None


def _stage_usable(connection, history, event, *, cutoff, next_start, check_build):
    participants = {event["home_id"], event["away_id"]}
    v2_conflicts, conflicts, unknown, modes = set(), set(), set(), set()
    sequence = 0
    for event_index, group in enumerate(history.iter_events(exclude_event=event["event_key"])):
        if event_index % 128 == 0:
            check_build()
        relevant, has_status = set(), False
        for row in group.iter_rows():
            has_status |= row["source_schema"] == STATUS_SCHEMA
            for player in _participants(row):
                if player in participants:
                    relevant.add(player)
        if not relevant:
            continue
        if not has_status:
            modes.add("legacy-only")
            usable, is_conflicting = _legacy_pair(group, cutoff=cutoff, next_start=next_start)
            if is_conflicting:
                v2_conflicts.update(relevant)
            association = None
        else:
            pair, association, status = _paired_status(group, participants)
            if status in {"conflicting", "missing"}:
                (conflicts if status == "conflicting" else unknown).update(relevant)
                modes.add("unavailable-status")
                continue
            if status == "removed":
                continue
            modes.add("status-paired")
            usable, pair_conflicts = _usable_history(pair, cutoff=cutoff, next_start=next_start)
            if pair_conflicts:
                v2_conflicts.update(relevant)
        for row in usable:
            if row["subject_id"] not in participants:
                continue
            sequence += 1
            side = "a" if row["subject_id"] == event["home_id"] else "b"
            connection.execute("INSERT INTO tennis_chosen VALUES(?,?,?,?)",
                (sequence, side, canonical_bytes(row),
                 canonical_bytes(association if association is not None else (row["digest"],))))
    mode = ("no-history" if not modes else "unavailable-status" if "unavailable-status" in modes
            else "mixed-status-legacy" if len(modes) > 1 else next(iter(modes)))
    return v2_conflicts, conflicts, unknown, mode


def _rows(connection, side):
    cursor = connection.execute(
        "SELECT row,association FROM tennis_chosen WHERE side=? ORDER BY sequence", (side,))
    try:
        for raw, association in cursor:
            yield _row(raw), json.loads(association)
    finally:
        cursor.close()


def _add_refs(connection, pool, refs):
    connection.executemany("INSERT OR IGNORE INTO tennis_ref_projection VALUES(?,?)",
                           ((pool, ref) for ref in refs))


def _window_rows(connection, side, start, stop):
    for row, _ in _rows(connection, side):
        ended = row["payload"]["actual_end"]
        if ended is not None and start <= ended < stop:
            yield row


def _compute_header(connection, event, base, *, cutoff, v2_conflicts,
                    conflicts, unknown, mode, target_state, target_refs, check_build):
    """Execute the old arithmetic in the same side/window/row order.

    In particular Python's original builtins.sum consumes a disk generator;
    SQL SUM and repeated += are not numerically equivalent on all runtimes.
    """
    values, states, plans, side_names = {}, {}, {}, set()
    decision, next_start = _instant(cutoff), _instant(event["scheduled_start"])

    def put(name, value, pools=(), state=None):
        values[name] = value
        states[name] = state or ("missing" if value is None else "available")
        plans[name] = tuple(pools) if states[name] == "available" else ()

    applicable = (event["status"] == "scheduled"
        and event["format"] in {"singles", "singles_best_of_3", "singles_best_of_5"}
        and event.get("tour") in {"ATP", "WTA"})
    coverage_count, known_end_count, bounded_unknown_sides = 0, 0, []
    for side, player in (("a", event["home_id"]), ("b", event["away_id"])):
        blocked = "not_applicable" if not applicable else "conflicting" if player in v2_conflicts else None
        count, known_count = 0, 0
        latest_receipt, latest_end, latest_unknown = None, None, None
        all_pool = side + ".all"
        if blocked is None:
            for row, associated in _rows(connection, side):
                payload = row["payload"]
                count += 1
                if count % 128 == 0:
                    check_build()
                receipt, ended = _instant(payload["result_observed_at"]), payload["actual_end"]
                latest_receipt = receipt if latest_receipt is None else max(latest_receipt, receipt)
                if ended is not None:
                    known_count += 1
                    ended = _instant(ended)
                    latest_end = ended if latest_end is None else max(latest_end, ended)
                else:
                    latest_unknown = receipt if latest_unknown is None else max(latest_unknown, receipt)
                _add_refs(connection, all_pool, associated)
        coverage_count += count
        known_end_count += known_count
        for days in WINDOWS:
            start, stop = canonical_timestamp(decision - timedelta(days=days)), canonical_timestamp(decision)
            uncertain = latest_unknown is not None and canonical_timestamp(latest_unknown) >= start
            window_count, incomplete = 0, 0
            measured = dict.fromkeys(METRICS, 0)
            window_pool = f"{side}.window.{days}"
            if blocked is None:
                for row, associated in _rows(connection, side):
                    payload, ended = row["payload"], row["payload"]["actual_end"]
                    if ended is None or not start <= ended < stop:
                        continue
                    window_count += 1
                    if window_count % 128 == 0:
                        check_build()
                    incomplete += payload["incomplete_match"]
                    _add_refs(connection, window_pool, associated)
                    for metric in METRICS:
                        if payload[metric] is not None:
                            measured[metric] += 1
                            _add_refs(connection, f"{side}.measured.{days}.{metric}", associated)
            for metric in METRICS:
                name = f"observed_{metric}_{days}d"
                side_names.add(name)
                total = (sum(row["payload"][metric]
                    for row in _window_rows(connection, side, start, stop)
                    if row["payload"][metric] is not None) if measured[metric] else None)
                put(f"{name}_{side}", total, (f"{side}.measured.{days}.{metric}",), blocked)
                complete = int(bool(window_count) and measured[metric] == window_count and not uncertain) if count else None
                put(f"observed_{metric}_complete_{days}d_{side}", complete, (all_pool,), blocked)
            put(f"observed_matches_{days}d_{side}", window_count if window_count else None, (window_pool,), blocked)
            put(f"incomplete_matches_{days}d_{side}", incomplete if window_count else None, (window_pool,), blocked)
            put(f"history_complete_{days}d_{side}", 0 if count else None, (all_pool,), blocked)
        if count:
            exact_end = latest_end if latest_end is not None and (
                latest_unknown is None or latest_unknown <= latest_end) else None
            if latest_unknown is not None:
                bounded_unknown_sides.append(exact_end is not None
                    and latest_unknown < decision - timedelta(days=max(WINDOWS)))
            bounds = recovery_bounds(next_start=next_start,
                result_observed_at=latest_receipt, ended_at=exact_end)
        else:
            bounds = {"minimum_hours": None, "exact_hours": None}
        for kind in ("minimum", "exact"):
            name = f"observed_recovery_{kind}_hours"
            side_names.add(name)
            put(f"{name}_{side}", bounds[f"{kind}_hours"], (all_pool,), blocked)
        put(f"recovery_is_exact_{side}", int(bounds["exact_hours"] is not None) if count else None, (all_pool,), blocked)
        for name in ("availability", "return_from_absence", "travel_hours"):
            side_names.add(name)
            put(f"{name}_{side}", None, state=blocked)

    def delta(name):
        a, b = name + "_a", name + "_b"
        if states[a] == states[b] == "available":
            put(name + "_delta", values[a] - values[b], tuple(sorted(set(plans[a]) | set(plans[b]))))
        else:
            state = ("not_applicable" if "not_applicable" in (states[a], states[b]) else
                     "conflicting" if "conflicting" in (states[a], states[b]) else "missing")
            put(name + "_delta", None, state=state)

    for name in sorted(side_names):
        delta(name)
    rest = ("exact-observed" if all(values[f"observed_recovery_exact_hours_{side}"] is not None for side in ("a", "b")) else
            "receipt-bound-observed" if all(values[f"observed_recovery_minimum_hours_{side}"] is not None for side in ("a", "b")) else "missing-rest")
    timing = ("no-history" if not coverage_count else "missing-end-times" if not known_end_count else
              "known-end-times" if known_end_count == coverage_count else "partial-end-times")
    if bounded_unknown_sides and all(bounded_unknown_sides):
        timing = "bounded-irrelevant-end-times"
    # Apply the v3 unknown/conflict overrides only AFTER deriving v2 timing.
    # Preemptively dropping such rows changes its declared coverage case.
    for side, player in (("a", event["home_id"]), ("b", event["away_id"])):
        if player in conflicts | unknown:
            for name in values:
                if name.endswith("_" + side) and states[name] != "not_applicable":
                    values[name], plans[name] = None, ()
                    states[name] = "conflicting" if player in conflicts else "missing"
    for name in sorted(side_names):
        delta(name)
    if target_state is not None:
        for name in values:
            values[name], states[name], plans[name] = None, target_state, ()
        mode = "unavailable-status"
    if target_state is not None or participants_affected(event, conflicts | unknown):
        rest = "missing-rest"
    header = validate_feature_vector({
        "version": FEATURE_VERSION, "event_key": event["event_key"],
        "cutoff": canonical_timestamp(decision), "values": values, "states": states,
        "refs": {name: [] for name in values},
        "coverage": {"version": COVERAGE_VERSION, "case": f"{mode}.observed-only.{rest}.{timing}"},
        "reference_hash": tennis_reference_hash_v3(base, event),
    })
    return header, {name: (plans[name], tuple(target_refs) if states[name] == "available" else ())
                    for name in values}


def participants_affected(event, players):
    return event["home_id"] in players or event["away_id"] in players


def _union_refs(connection, pools, literals):
    placeholders = ",".join("?" for _ in pools)
    sql = (f"SELECT ref FROM tennis_ref_projection WHERE pool IN ({placeholders})"
           if pools else "SELECT ref FROM tennis_ref_projection WHERE 0")
    for _ in literals:
        sql += " UNION SELECT ?"
    # DISTINCT also removes repeated references within different selected pools.
    sql = "SELECT DISTINCT ref FROM (" + sql + ") ORDER BY ref"
    cursor = connection.execute(sql, (*pools, *literals))
    try:
        for (ref,) in cursor:
            yield ref
    finally:
        cursor.close()


class StreamingTennisFeatures:
    """An explicit complete numeric header plus immutable blocked references."""
    __slots__ = ("_connection", "_path", "_stamp", "_history",
                 "_header", "_refs", "_limits", "_changes", "_closed", "_generation",
                 "_failed", "_connection_attributes", "_storage_epoch", "_limits_identity")
    format_version = FORMAT_VERSION

    def __init__(self, *, connection=None, path=None, history=None,
                 header=None, refs=None, limits=None, _token=None):
        if _token is not _RESULT_TOKEN:
            raise StorageIntegrityError("tennis_features_streaming owns complete result publication")
        for name, value in {
            "_connection": connection, "_path": path,
            "_history": history, "_header": canonical_bytes(header),
            "_refs": MappingProxyType(dict(refs)), "_limits": limits,
            "_closed": False, "_failed": False, "_stamp": _stamp(path),
            "_changes": connection.total_changes,
            "_generation": connection.transaction_generation,
            "_storage_epoch": _read_storage_epoch(connection),
            "_limits_identity": _limits_identity(limits),
        }.items():
            object.__setattr__(self, name, value)
        def reject_customization(*args, **kwargs):
            object.__setattr__(self, "_failed", True)
            raise StorageIntegrityError("published Tennis refs cannot install callbacks or extensions")
        for name in ("set_trace_callback", "set_progress_handler", "set_authorizer",
                     "create_function", "create_aggregate", "create_window_function",
                     "enable_load_extension", "load_extension"):
            setattr(connection, name, reject_customization)
        object.__setattr__(self, "_connection_attributes", MappingProxyType(dict(connection.__dict__)))

    def __setattr__(self, name, value):
        raise StorageIntegrityError("published Tennis result bindings cannot be changed")

    def assert_intact(self):
        try:
            if type(self) is not StreamingTennisFeatures or self._closed or self._failed:
                raise StorageIntegrityError("Tennis streaming result is closed or invalid")
            self._history.assert_intact()
            if (type(self._connection) is not TrackedConnection
                    or not self._connection.in_transaction
                    or self._connection.transaction_generation != self._generation
                    or self._connection.__dict__ != self._connection_attributes
                    or self._connection.row_factory is not None
                    or self._connection.text_factory is not str
                    or sqlite3.Connection.execute(self._connection, "PRAGMA query_only").fetchone() != (1,)
                    or self._connection.total_changes != self._changes
                    or _read_storage_epoch(self._connection) != self._storage_epoch
                    or _limits_identity(self._limits) != self._limits_identity
                    or _stamp(self._path) != self._stamp):
                raise StorageIntegrityError("Tennis result generation or transaction changed")
            if any(Path(str(self._path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
                raise StorageIntegrityError("published Tennis result has a SQLite companion")
        except BaseException as exc:
            object.__setattr__(self, "_failed", True)
            if isinstance(exc, (OSError, sqlite3.Error)):
                raise StorageIntegrityError("Tennis result lifetime or file is invalid") from exc
            raise

    @property
    def values(self):
        self.assert_intact()
        return MappingProxyType(json.loads(self._header)["values"])

    @property
    def states(self):
        self.assert_intact()
        return MappingProxyType(json.loads(self._header)["states"])

    @property
    def coverage(self):
        self.assert_intact()
        return MappingProxyType(json.loads(self._header)["coverage"])

    @property
    def ref_sets(self):
        self.assert_intact()
        return MappingProxyType(dict(self._refs))

    @property
    def history_binding(self):
        self.assert_intact()
        return self._history.binding

    @property
    def canonical_size(self):
        self.assert_intact()
        return len(self._header) + sum(
            descriptor.canonical_bytes - 2 for descriptor in self._refs.values())

    @property
    def path(self):
        """Diagnostic retained artifact path, not a seal or permission to mutate."""
        return self._path

    @property
    def output_bytes(self):
        self.assert_intact()
        return self._path.stat().st_size

    def iter_refs(self, name):
        from context_storage_v2.refs import iter_refset
        self.assert_intact()
        if name not in self._refs:
            raise ContextContractError("unknown Tennis feature reference name")
        try:
            for ref in iter_refset(self._connection, self._refs[name], limits=self._limits):
                self.assert_intact()
                yield ref
                self.assert_intact()
        except BaseException as exc:
            if not isinstance(exc, GeneratorExit):
                object.__setattr__(self, "_failed", True)
            raise
        self.assert_intact()

    def materialize(self, *, max_bytes=MAX_MATERIALIZATION_BYTES):
        """Build the exact old vector under this helper's new 64 MiB byte cap."""
        self.assert_intact()
        if type(max_bytes) is not int or not 0 < max_bytes <= MAX_MATERIALIZATION_BYTES:
            raise StorageLimitError("invalid or widened optional feature materialization limit")
        if self.canonical_size > max_bytes:
            raise StorageLimitError("complete Tennis feature refs exceed materialization budget")
        result = json.loads(self._header)
        result["refs"] = {name: list(self.iter_refs(name)) for name in self._refs}
        result = validate_feature_vector(result)
        self.assert_intact()
        if len(canonical_bytes(result)) != self.canonical_size:
            raise StorageIntegrityError("Tennis reference reconstruction byte size differs")
        return result

    def _canonical_chunks(self):
        """Canonical legacy bytes without constructing the complete old vector."""
        self.assert_intact()
        header = json.loads(self._header)
        yield b"{"
        for field_index, field in enumerate(sorted(header)):
            if field_index:
                yield b","
            yield canonical_bytes(field) + b":"
            if field != "refs":
                yield canonical_bytes(header[field])
                continue
            yield b"{"
            for name_index, name in enumerate(sorted(self._refs)):
                if name_index:
                    yield b","
                yield canonical_bytes(name) + b":["
                for ref_index, ref in enumerate(self.iter_refs(name)):
                    if ref_index:
                        yield b","
                    yield canonical_bytes(ref)
                yield b"]"
            yield b"}"
        yield b"}"
        self.assert_intact()

    def iter_canonical_chunks(self):
        """Reject invalidation even between two small numeric/header chunks."""
        for chunk in self._canonical_chunks():
            self.assert_intact()
            yield chunk
            self.assert_intact()

    def canonical_digest(self):
        hasher, count = hashlib.sha256(), 0
        for chunk in self.iter_canonical_chunks():
            hasher.update(chunk)
            count += len(chunk)
        if count != self.canonical_size:
            raise StorageIntegrityError("streamed Tennis feature byte size differs")
        return hasher.hexdigest()

    def close(self):
        if not self._closed:
            object.__setattr__(self, "_closed", True)
            self._connection.close()
            # Retain this generation and every failed attempt for its outer
            # inventory. Closing a Python handle does not release a disk slot.

    def __enter__(self):
        self.assert_intact()
        return self

    def __exit__(self, *exc):
        self.close()


def tennis_features_streaming(event: dict, history_view, base: dict, *,
                              cutoff: datetime, work_directory: Path,
                              main_cap_bytes: int, owned_directory=None,
                              limits: StorageLimits = DEFAULT_LIMITS):
    """New explicit owner; never enters the old tuple-only API with a fake type.

    The caller owns the complete C/B workspace cost and worker CPU/RAM limits.
    This component additionally caps its own SQLite file, single selected rows,
    and its free-space reserve. It does not claim whole-release admission.
    ``main_cap_bytes`` is logical main M with a separate journal-M reservation,
    not native enforcement or physical/global admission. The native owner uses
    an already reserved private empty ``owned_directory`` (direct child of
    work_directory), with fixed features.sqlite/features.sqlite-journal names.
    Omitted owned_directory is local convenience only and requires complete
    outer enumeration. Success exposes result.path; errors note the retained
    directory. Neither failure nor close deletes artifacts or releases budget.
    """
    from context_storage_v2.history import HistoryView
    from context_storage_v2.refs import create_schema, put_refset
    if type(history_view) is not HistoryView:
        raise StorageIntegrityError("Tennis streaming requires its complete owning HistoryView")
    if type(limits) is not StorageLimits:
        raise StorageLimitError("Tennis streaming requires explicit fixed storage limits")
    StorageLimits.__post_init__(limits)
    plan = SQLiteWriterPlan(main_cap_bytes=main_cap_bytes, cache_kib=4096)
    SQLiteWriterPlan._validate_limits(plan, limits)
    event, base = validate_event(event), validate_base_distribution(base)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("Tennis streaming requires an aware cutoff datetime")
    decision, next_start = _instant(cutoff), _instant(event["scheduled_start"])
    if event["sport"] != "tennis" or base["family"] not in {"tennis:winner", "tennis:serve"}:
        raise ContextContractError("tennis load requires a tennis event and base family")
    if base["event_key"] != event["event_key"] or base["cutoff"] != canonical_timestamp(decision):
        raise ContextContractError("tennis feature/base identity or decision clock mismatch")
    if decision >= next_start:
        raise ContextContractError("tennis decision must precede the next scheduled start")
    history_view.assert_intact()
    if history_view.cutoff != canonical_timestamp(decision) or history_view.tour != event.get("tour"):
        raise StorageIntegrityError("Tennis history belongs to a different tour or cutoff")
    if history_view.canonical_bytes > limits.tour_history_bytes:
        raise StorageLimitError("complete selected Tennis history exceeds the explicit tour budget")
    # Validate the full selected source stream BEFORE event/player filtering.
    for row in history_view.iter_rows():
        _validate_selected_tennis_receipt_cold(row)
        if len(canonical_bytes(row)) > limits.block_bytes:
            raise StorageLimitError("selected Tennis row requires a separately reviewed large-value adapter")
    history_view.assert_intact()
    directory = Path(work_directory)
    if directory.is_symlink() or not directory.is_dir():
        raise StorageIntegrityError("Tennis work directory must be an existing real directory")
    directory = directory.absolute()
    _ensure_space(directory, limits)
    private = _private_build_directory(directory, owned_directory, prefix="tennis-features-")
    path = private / "features.sqlite"
    writer = None
    connection = None
    try:
        writer = open_fresh_writer(path, plan=plan, limits=limits)
        build_connection = writer.connection  # Exact TrackedConnection; BEGIN already held.

        def check_build():
            observed = writer.check_profile()
            _ensure_space(private, limits)
            if observed.main_file_bytes + observed.journal_file_bytes > limits.workspace_bytes:
                raise StorageLimitError("private Tennis allocation exceeds its C envelope")

        # Keep the public-reader variable separate: writer owns every build
        # cursor/blob and closes them before its single commit handoff.
        check_build()
        build_connection.execute("CREATE TABLE tennis_chosen(sequence INTEGER PRIMARY KEY, side TEXT NOT NULL, row BLOB NOT NULL, association BLOB NOT NULL)")
        build_connection.execute("CREATE INDEX tennis_chosen_side ON tennis_chosen(side,sequence)")
        build_connection.execute("CREATE TABLE tennis_ref_projection(pool TEXT NOT NULL, ref TEXT NOT NULL, PRIMARY KEY(pool,ref)) WITHOUT ROWID")
        create_schema(build_connection)
        check_build()
        v2_conflicts, conflicts, unknown, mode = _stage_usable(
            build_connection, history_view, event, cutoff=decision, next_start=next_start,
            check_build=check_build)
        check_build()
        target_state, target_refs = _target_state(history_view.event(event["event_key"]), event)
        header, plans = _compute_header(build_connection, event, base, cutoff=decision,
            v2_conflicts=v2_conflicts, conflicts=conflicts, unknown=unknown, mode=mode,
            target_state=target_state, target_refs=target_refs, check_build=check_build)

        def checked_refs(pools, literals):
            for index, ref in enumerate(_union_refs(build_connection, pools, literals)):
                if index % 128 == 0:
                    check_build()
                yield ref
            check_build()

        descriptors, cache = {}, {}
        for name, ref_plan in plans.items():
            if ref_plan not in cache:
                check_build()
                cache[ref_plan] = put_refset(build_connection, checked_refs(*ref_plan), limits=limits)
            descriptors[name] = cache[ref_plan]
        history_view.assert_intact()
        check_build()  # No commit if the free reserve or exact writer profile drifted.
        writer.commit_build()
        # Never hand the private writer to a reader guarded merely by the
        # reversible query_only PRAGMA. The OS-opened main database is read-only.
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                     timeout=0, factory=TrackedConnection)
        _configure_read_connection(connection, plan)
        connection.execute("BEGIN")
        # A read establishes the held snapshot, not merely the deferred BEGIN.
        connection.execute("SELECT count(*) FROM tennis_chosen").fetchone()
        _ensure_space(directory, limits)
        result = StreamingTennisFeatures(connection=connection, path=path,
            history=history_view, header=header, refs=descriptors, limits=limits,
            _token=_RESULT_TOKEN)
        result.assert_intact()
        return result
    except BaseException as exc:
        if connection is not None:
            connection.close()
        if isinstance(exc, sqlite3.Error) and getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
            error = StorageLimitError("Tennis output exceeded its bounded SQLite allocation")
            error.add_note("Unpublished or failed C Tennis directory retained: " + str(private))
            raise error from exc
        exc.add_note("Unpublished or failed C Tennis directory retained: " + str(private))
        raise
    finally:
        if writer is not None:
            writer.close()
