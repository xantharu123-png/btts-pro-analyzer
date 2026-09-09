"""Worker-only capture of already budgeted API-Football responses.

No fetch, retry, model, price, guessed publication or receipt refresh belongs
here. Default providers and 15K renderers do not enable this observer. Only
explicit native context IDs are persisted; league discovery is joining material
for those IDs, not an unbounded duplicate historical feed.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from context_models.contracts import ContextContractError, canonical_timestamp, require_object
from context_observations import append_observation
from context_sources.football import _detail_event, normalize_football_context
from context_sources.football_provider import _native_id, _response
from context_sources.outcomes import normalize_football_base_input, normalize_football_outcome


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


class _Capture:
    def __init__(self):
        self.errors, self.receipts, self.wanted, self.refs = [], [], set(), set()

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
            if requested is None and not discovery:
                return
            if requested is not None:
                self.wanted.update(requested)
            if type(status) is not int or status != 200:
                raise ContextContractError("incomplete context HTTP response")
            rows, clock = _response({"payload": payload, "observed_at": canonical_timestamp(observed_at)})
            if endpoint == "fixtures":
                seen = set()
                for raw in rows:
                    ev = _detail_event(raw)
                    fid = _native_id(raw["fixture"]["id"])
                    if fid in seen or requested is not None and fid not in requested:
                        raise ContextContractError("context fixture response identity differs")
                    seen.add(fid)
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
                if requested is not None and seen != set(requested):
                    self.errors.append("Kontext-Capture: native-response-unavailable")
            elif any(_native_id(row["fixture"]["id"]) not in requested for row in rows):
                raise ContextContractError("context injury response identity differs")
            self.receipts.append({"endpoint": endpoint, "requested": requested,
                                  "rows": deepcopy(rows), "observed_at": clock})
        except (ContextContractError, KeyError, TypeError, ValueError, OverflowError):
            self.errors.append("Kontext-Capture: native-response-unavailable")

    def persist(self, path):
        # All normalization for one response completes before publishing any of
        # its records. B1 append is idempotent, not a fabricated all-source commit.
        # Interrupted multi-record append remains partial and is rejected as a
        # complete roster by existing collection validators on subsequent reads.
        details = [item for item in self.receipts if item["endpoint"] == "fixtures"]
        for receipt in self.receipts:
            observed = datetime.fromisoformat(receipt["observed_at"])
            additions = []
            try:
                if receipt["endpoint"] == "fixtures":
                    for raw in receipt["rows"]:
                        if raw["fixture"]["id"] not in self.wanted:
                            continue
                        ev = _detail_event(raw)
                        additions.extend(row for row in normalize_football_context(ev, injuries=[],
                            lineups=[raw] if "lineups" in raw and ev["status"] == "scheduled" else [],
                            appearances=[raw] if "players" in raw and ev["status"] == "completed" else [],
                            observed_at=observed) if row["kind"] != "availability")
                        if raw["fixture"]["status"]["short"] in {"NS", "TBD", "PST", "FT"}:
                            additions.append(normalize_football_base_input(raw, observed_at=observed))
                        outcome = normalize_football_outcome(ev, raw, observed_at=observed)
                        if outcome is not None:
                            additions.append(outcome)
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
            for record in additions:
                self.refs.add(append_observation(path, record, observed_at=observed))


@contextmanager
def capture_football_worker(provider, *, path=None):
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
    capture = _Capture()
    provider._context_capture = capture
    try:
        yield capture
    finally:
        provider._context_capture = None
        capture.persist(Path(path))
