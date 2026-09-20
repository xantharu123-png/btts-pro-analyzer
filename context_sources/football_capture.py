"""Worker-only capture of already budgeted API-Football responses.

No fetch, retry, model, price, guessed publication or receipt refresh belongs
here. Default providers and 15K renderers do not enable this observer. Only
explicit native context IDs are persisted; league discovery is joining material
for those IDs, not an unbounded duplicate historical feed.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, require_object
from context_observations import append_observation_batch
from context_sources.football import _detail_event, normalize_football_context
from context_sources.football_provider import _native_id, _response
from context_sources.outcomes import normalize_football_base_input, normalize_football_outcome, validate_football_base_input


def _ids(params, single):
    if set(params) == {single}:
        return (_native_id(params[single]),)
    if set(params) == {"ids"} and type(params["ids"]) is str:
        words = params["ids"].split("-")
        if any(not word.isascii() or not word.isdecimal() or str(int(word)) != word for word in words):
            raise ContextContractError("noncanonical context request IDs")
        values = tuple(_native_id(int(word)) for word in words)
        if not values or len(values) > 20 or len(set(values)) != len(values):
            raise ContextContractError("context request IDs must be unique and bounded")
        return values
    return None


def capture_report_fields(snapshot):
    """Closed, detached optional admin metadata; no legacy status authority."""
    if "context_capture" not in snapshot:
        return {}
    report = require_object(snapshot["context_capture"],
        {"schema", "scope", "status", "receipt_refs", "issues"}, label="football capture report")
    refs, issues = report["receipt_refs"], report["issues"]
    allowed = {"Kontext-Capture: " + reason for reason in
        ("native-response-unavailable", "native-event-binding-unavailable", "native-projection-unavailable")}
    if (type(report["schema"]) is not int or report["schema"] != 1
        or report["scope"] != "existing-football-context-requests"
        or type(refs) is not list or type(issues) is not list
        or any(type(ref) is not str or len(ref) != 64 or any(c not in "0123456789abcdef" for c in ref) for ref in refs)
        or any(type(issue) is not str or issue not in allowed for issue in issues)
        or refs != sorted(set(refs)) or issues != sorted(set(issues))
        or report["status"] != ("partial" if issues else "captured" if refs else "no_receipts")):
        raise ContextContractError("football capture report is inconsistent")
    return {"context_capture": deepcopy(report)}


def _previous_prematch_observations(path, event_keys):
    """Freeze receipts for this received result batch, not a whole-DB audit.

    The existing native base receipt authorizes retaining a later fetched
    result for that ID. It does NOT assert that any frozen event/schedule or
    historical model may consume the new result; owning outcome replay still
    checks those identities. No schema initialization or new source query.
    Validate detached bytes only after releasing the physical read image:
    historical football validation must not block tennis/model writers.
    """
    event_keys = tuple(sorted(set(event_keys)))
    if not event_keys or not os.path.lexists(path):
        return {}
    from context_models.dataset import _reader
    from context_observations import _SELECT, _decode_receipt
    watched = {}
    with _reader(path) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('context_observations','context_contents')")}
        if not tables:
            return watched  # A legitimate A1-only database stays untouched.
        if tables != {"context_observations", "context_contents"}:
            raise ContextIntegrityError("incomplete stored context observation tables")
        # Only these already received native IDs can produce results. Select
        # every kind/source for them, so altered source/kind indexes still fail
        # validation instead of hiding a damaged watch. Other sports/events
        # cannot authorize this batch and need no repeated inventory scan.
        frozen = []
        for start in range(0, len(event_keys), 128):
            keys = event_keys[start:start+128]
            placeholders = ','.join('?' for _ in keys)
            frozen.extend(connection.execute(_SELECT +
                f' WHERE r.event_key IN ({placeholders})', keys).fetchall())
    for stored in frozen:
        row = _decode_receipt(stored)
        if row["source"] != "api-football" or row["kind"] != "base_fixture":
            continue
        # The actual receipt clock is not an archival publication or live
        # cutoff; prematch and later-result bounds are checked separately.
        row = {**row, "evidence_class": "prospective", "effective_at": row["observed_at"],
               "publication_resolution": None}
        if row["source_schema"] != "native-football-base-detail-v1":
            continue
        try:
            validate_football_base_input(row)
        except ContextContractError as exc:
            raise ContextIntegrityError("invalid stored native football base receipt") from exc
        event = _detail_event(row["payload"]["detail"])
        if (event["status"] == "scheduled"
                and row["observed_at"] < event["scheduled_start"]):
            key = row["event_key"]
            watched[key] = min(watched.get(key, row["observed_at"]), row["observed_at"])
    return watched


class _Capture:
    def __init__(self, path=None, *, baseline_enabled=False):
        self.errors, self.receipts, self.wanted, self.refs = [], [], set(), set()
        self.path = path
        self.baseline_processed = set()
        self.baseline_refs = {}
        self.baseline_scope_records = {}
        self.source_inserted_bytes = 0
        self.baseline_enabled = baseline_enabled

    def flush_baseline_receipts(self, selected_input_scope, *, max_new_payload_bytes):
        """Retain received revisions in the explicit pool, never match scores."""
        from challenge_engine import football_base_history_record
        from context_models.contracts import digest
        from context_observations import append_bounded_observation_batch
        if type(selected_input_scope) is not tuple:
            raise ContextContractError("baseline input scope must be an explicit tuple")
        if type(max_new_payload_bytes) is not int or max_new_payload_bytes < 0:
            raise ValueError("source payload budget must be a finite nonnegative integer")
        records = {}
        for row in selected_input_scope:
            try:
                record = football_base_history_record(row)
                records[digest(record)] = record
            except ContextIntegrityError:
                raise
            except (ContextContractError, KeyError, TypeError, ValueError, OverflowError):
                self.errors.append("Kontext-Capture: native-projection-unavailable")
        self.baseline_scope_records = records
        wanted = {row["fixture_id"] for row in records.values()
                  if row["source_marker"] in {"unresolved", "api-football", "api-football-ft-tail"}}
        remaining = max_new_payload_bytes
        for index, receipt in enumerate(self.receipts):
            if receipt["endpoint"] != "fixtures":
                continue
            for row_index, raw in enumerate(receipt["rows"]):
                key = (index, row_index)
                if raw["fixture"]["id"] not in wanted or key in self.baseline_processed:
                    continue
                observed = datetime.fromisoformat(receipt["observed_at"])
                try:
                    event = _detail_event(raw)
                    additions = [row for row in normalize_football_context(event, injuries=[],
                        lineups=[raw] if "lineups" in raw and event["status"] == "scheduled" else [],
                        appearances=[raw] if "players" in raw and event["status"] == "completed" else [],
                        observed_at=observed) if row["kind"] != "availability"]
                    additions.append(normalize_football_base_input(raw, observed_at=observed))
                    base_index = len(additions) - 1
                    outcome = normalize_football_outcome(event, raw, observed_at=observed)
                    if outcome is not None:
                        additions.append(outcome)
                    if len(additions) > 512:
                        raise ContextContractError("native fixture projection exceeds bounded batch")
                except ContextIntegrityError:
                    raise
                except (ContextContractError, KeyError, TypeError, ValueError, OverflowError):
                    self.errors.append("Kontext-Capture: native-projection-unavailable")
                    continue
                refs, inserted = append_bounded_observation_batch(self.path,
                    tuple((record, observed) for record in additions), max_new_payload_bytes=remaining)
                remaining -= inserted
                self.source_inserted_bytes += inserted
                self.refs.update(refs)
                self.baseline_refs.setdefault(raw["fixture"]["id"], set()).add(refs[base_index])
                self.baseline_processed.add(key)
        return {ref: tuple(sorted(self.baseline_refs.get(row["fixture_id"], ())))
                if row["source_marker"] in {"unresolved", "api-football", "api-football-ft-tail"} else ()
                for ref, row in records.items()}

    def report(self):
        """Administrative capture status, never forecast/effect eligibility."""
        return {"schema": 1, "scope": "existing-football-context-requests",
                "status": "partial" if self.errors else "captured" if self.refs else "no_receipts",
                "receipt_refs": sorted(self.refs), "issues": sorted(set(self.errors))}

    def record(self, endpoint, params, payload, *, observed_at, status):
        if endpoint not in {"fixtures", "injuries"}:
            return
        try:
            requested = _ids(params, "id" if endpoint == "fixtures" else "fixture")
            discovery = endpoint == "fixtures" and params.get("status") == "NS" and (
                set(params) in ({"league", "season", "date", "timezone", "status"},
                                {"league", "season", "from", "to", "timezone", "status"}))
            results = endpoint == "fixtures" and params.get("status") == "FT" and (
                set(params) in ({"league", "season", "status"},
                                {"league", "season", "from", "to", "timezone", "status"}))
            domestic = self.baseline_enabled and endpoint == "fixtures" and set(params) == {"team", "last", "status", "timezone"}
            if domestic:
                _native_id(params["team"])
                if (type(params["last"]) is not int or not 1 <= params["last"] <= 100
                        or params["status"] != "FT" or type(params["timezone"]) is not str):
                    raise ContextContractError("invalid domestic request scope")
                ZoneInfo(params["timezone"])
            if requested is None and not discovery and not results and not domestic:
                return
            if requested is not None:
                self.wanted.update(requested)
            if type(status) is not int or status != 200:
                raise ContextContractError("incomplete context HTTP response")
            rows, clock = _response({"payload": payload, "observed_at": canonical_timestamp(observed_at)})
            if endpoint == "fixtures":
                seen = set()
                if domestic and len(rows) > params["last"]:
                    raise ContextContractError("domestic response exceeds requested count")
                for raw in rows:
                    ev = _detail_event(raw)
                    fid = _native_id(raw["fixture"]["id"])
                    if fid in seen or requested is not None and fid not in requested:
                        raise ContextContractError("context fixture response identity differs")
                    seen.add(fid)
                    if domestic and (params["team"] not in {raw["teams"][side]["id"] for side in ("home", "away")}
                            or raw["fixture"]["status"]["short"] != "FT"):
                        raise ContextContractError("domestic response is outside its request scope")
                    if discovery:
                        actual_date = datetime.fromisoformat(ev["scheduled_start"]).astimezone(ZoneInfo(params["timezone"])).date().isoformat()
                        first, last = params.get("date", params.get("from")), params.get("date", params.get("to"))
                        # NS/TBD/PST share the normalized scheduled state, but
                        # only the exact requested native status proves this
                        # discovery scope. Explicit ID queries are unchanged.
                        if (str(_native_id(params["league"])) != ev["competition"]
                            or type(params["season"]) is not int or raw["league"].get("season") != params["season"]
                            or raw["fixture"]["status"]["short"] != params["status"]
                            or ev["status"] != "scheduled" or not first <= actual_date <= last):
                            raise ContextContractError("context discovery is outside its native request scope")
                    if results:
                        if (str(_native_id(params["league"])) != ev["competition"]
                                or type(params["season"]) is not int or raw["league"].get("season") != params["season"]
                                or raw["fixture"]["status"]["short"] != "FT"):
                            raise ContextContractError("context result is outside its native request scope")
                        if "from" in params:
                            first, last = (date.fromisoformat(params[name]) for name in ("from", "to"))
                            actual_date = datetime.fromisoformat(ev["scheduled_start"]).astimezone(ZoneInfo(params["timezone"])).date()
                            if not first <= actual_date <= last:
                                raise ContextContractError("context result is outside its requested dates")
                if requested is not None and seen != set(requested):
                    self.errors.append("Kontext-Capture: native-response-unavailable")
            elif any(_native_id(row["fixture"]["id"]) not in requested for row in rows):
                raise ContextContractError("context injury response identity differs")
            self.receipts.append({"endpoint": endpoint, "requested": requested,
                                  "rows": deepcopy(rows), "observed_at": clock, "watched_results_only": results,
                                  "baseline_only": domestic})
        except (ContextContractError, KeyError, TypeError, ValueError, OverflowError):
            self.errors.append("Kontext-Capture: native-response-unavailable")

    def persist(self, path):
        # Each fixture is normalized completely before any of its records are
        # added. One bad player's row must not discard unrelated valid games
        # in an already scope-validated response. B1 append is idempotent.
        # Interrupted multi-record append remains partial and is rejected as a
        # complete roster by existing collection validators on subsequent reads.
        details = [item for item in self.receipts if item["endpoint"] == "fixtures"]
        result_keys = {_detail_event(raw)['event_key']
            for index, item in enumerate(self.receipts) if item['watched_results_only']
            for ri, raw in enumerate(item['rows']) if (index, ri) not in self.baseline_processed}
        watched = _previous_prematch_observations(path, result_keys)
        for receipt_index, receipt in enumerate(self.receipts):
            if receipt.get("baseline_only"):
                continue  # Opt-in additions only pass through their bounded flush.
            observed = datetime.fromisoformat(receipt["observed_at"])
            additions = []
            try:
                if receipt["endpoint"] == "fixtures":
                    for row_index, raw in enumerate(receipt["rows"]):
                        try:
                            if (receipt_index, row_index) in self.baseline_processed:
                                continue
                            ev = _detail_event(raw)
                            if receipt["watched_results_only"]:
                                known_at = watched.get(ev["event_key"])
                                if known_at is None or known_at > receipt["observed_at"]:
                                    continue
                            elif raw["fixture"]["id"] not in self.wanted:
                                continue
                            fixture_rows = [row for row in normalize_football_context(ev, injuries=[],
                                lineups=[raw] if "lineups" in raw and ev["status"] == "scheduled" else [],
                                appearances=[raw] if "players" in raw and ev["status"] == "completed" else [],
                                observed_at=observed) if row["kind"] != "availability"]
                            if raw["fixture"]["status"]["short"] in {"NS", "TBD", "PST", "FT"}:
                                fixture_rows.append(normalize_football_base_input(raw, observed_at=observed))
                            outcome = normalize_football_outcome(ev, raw, observed_at=observed)
                            if outcome is not None:
                                fixture_rows.append(outcome)
                        except (ContextContractError, KeyError, TypeError, ValueError, OverflowError):
                            self.errors.append("Kontext-Capture: native-projection-unavailable")
                            continue
                        additions.extend(fixture_rows)
                else:
                    for fid in receipt["requested"]:
                        # Require actual whole-event knowledge at the injury
                        # receipt, never manufacture it from a later detail.
                        known = [(item["observed_at"], _detail_event(raw)) for item in details
                            if item["observed_at"] <= receipt["observed_at"]
                            for raw in item["rows"] if raw["fixture"]["id"] == fid]
                        if not known:
                            raise ContextContractError("native-event-binding-unavailable")
                        latest = max(clock for clock, _ in known)
                        events = [ev for clock, ev in known if clock == latest]
                        if any(ev != events[0] for ev in events) or events[0]["status"] != "scheduled":
                            raise ContextContractError("native-event-binding-unavailable")
                        additions.extend(normalize_football_context(events[0], injuries=receipt["rows"],
                            lineups=[], appearances=[], observed_at=observed))
            except (ContextContractError, KeyError, TypeError, ValueError, OverflowError) as exc:
                reason = "native-event-binding-unavailable" if str(exc) == "native-event-binding-unavailable" else "native-projection-unavailable"
                self.errors.append("Kontext-Capture: " + reason)
                continue
            for start in range(0, len(additions), 512):
                self.refs.update(append_observation_batch(path,
                    tuple((record, observed) for record in additions[start:start+512])))


@contextmanager
def capture_football_worker(provider, *, path=None, baseline_enabled=False):
    """Enable the actual provider observer only for an explicit worker scope.

    Legacy injected providers without this interface remain unchanged. Actual
    storage integrity errors propagate; a worker cannot turn corruption into a
    healthy/missing-source claim. A prior worker exception still drains already
    received valid observations, and the observer is always removed.
    """
    if not hasattr(provider, "_context_capture"):
        yield
        return
    if provider._context_capture is not None:
        raise ContextContractError("football context capture is already owned by a worker")
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    if type(baseline_enabled) is not bool:
        raise ContextContractError("baseline capture opt-in must be boolean")
    capture = _Capture(Path(path), baseline_enabled=baseline_enabled)
    provider._context_capture = capture
    try:
        yield capture
    finally:
        provider._context_capture = None
        capture.persist(Path(path))
