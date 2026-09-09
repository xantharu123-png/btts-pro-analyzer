"""Bounded owning-source transport, distinct from feature and model execution.

The only network owner is ChallengeDataProvider's budgeted receipt helper.
There is no historical-publication claim, default healthy roster, cache-to-fresh
promotion, persistence, training or automatic activation in this module.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from context_models.contracts import ContextContractError, canonical_timestamp, validate_event
from context_sources.football import _detail_event, normalize_football_context


def _native_id(value):
    if type(value) is not int or value <= 0:
        raise ContextContractError("context fetch requires positive native fixture IDs")
    return value


def _event_id(event):
    prefix = "api-football:football:"
    key = event["event_key"]
    if event["sport"] != "football" or event["format"] != "90min" or not key.startswith(prefix):
        raise ContextContractError("source batch owns only native regulation football")
    raw = key[len(prefix):]
    if not raw.isascii() or not raw.isdecimal() or str(int(raw)) != raw:
        raise ContextContractError("context event requires a canonical native fixture ID")
    return _native_id(int(raw))


def _response(receipt):
    if receipt is None:
        raise ContextContractError("football context source unavailable")
    observed = canonical_timestamp(receipt["observed_at"])
    payload = receipt["payload"]
    if type(payload) is not dict or payload.get("errors") not in ([], {}):
        raise ContextContractError("football context source has errors")
    rows, paging, count = payload.get("response"), payload.get("paging"), payload.get("results")
    if type(rows) is not list or any(type(row) is not dict for row in rows):
        raise ContextContractError("football context source rows invalid")
    if type(count) is not int or count != len(rows) or type(paging) is not dict or set(paging) != {"current", "total"}:
        raise ContextContractError("football context source envelope incomplete")
    if any(type(paging[key]) is not int or paging[key] != 1 for key in ("current", "total")):
        raise ContextContractError("football context source is paginated or incomplete")
    return rows, observed


def collect_football_context(provider, events: tuple[dict, ...], *, historical_fixture_ids: tuple[int, ...]) -> dict:
    """One at-most-20-fixture unit; each endpoint succeeds independently.

    A successful empty injury response still means incomplete absence coverage.
    A failed endpoint creates no observation. Invalid native response identities
    invalidate that entire endpoint batch, not just the embarrassing rows.
    Raw native fixture envelopes remain INTERNAL joining material; B1 receives
    only normalized allowlisted records, each with its real receipt timestamp.
    """
    if type(events) is not tuple or type(historical_fixture_ids) is not tuple:
        raise ContextContractError("context batch requires explicit immutable ID/event tuples")
    wanted = {}
    for value in events:
        event = validate_event(value)
        identity = _event_id(event)
        if identity in wanted and wanted[identity] != event:
            raise ContextContractError("one batch cannot claim two revisions of an event")
        wanted[identity] = event
    historical = {_native_id(value) for value in historical_fixture_ids}
    ids = tuple(sorted(historical | set(wanted)))
    if len(ids) > 20:
        raise ContextContractError("one context batch is limited to 20 native fixtures")
    result = {"schema": 1, "observations": [], "native_details": [], "receipts": []}
    if not ids:
        return result

    def obtain(path, requested):
        receipt = provider._context_football_response(path, requested)
        metadata = {"source": "api-football", "endpoint": path, "requested_ids": list(requested),
                    "observed_at": None if receipt is None else receipt["observed_at"],
                    "status": "unavailable", "missing_ids": list(requested)}
        result["receipts"].append(metadata)
        rows, observed = _response(receipt)
        return rows, observed, metadata

    def attach(records, observed, *, kinds):
        return [{"record": record, "observed_at": observed} for record in records if record["kind"] in kinds]

    try:
        details, observed, metadata = obtain("fixtures", ids)
        additions, native, seen = [], [], set()
        for detail in details:
            identity = _native_id(detail["fixture"]["id"])
            if identity not in ids or identity in seen:
                raise ContextContractError("fixture batch native IDs are not unique/requested")
            seen.add(identity)
            actual = _detail_event(detail)
            event = wanted.get(identity, actual)
            if any(event[key] != actual[key] for key in ("event_key", "home_id", "away_id", "competition", "format", "scheduled_start", "status")):
                raise ContextContractError("fixture batch is not the requested event revision")
            records = normalize_football_context(
                event, injuries=[], lineups=[detail] if identity in wanted else [],
                appearances=[detail] if identity in historical else [], observed_at=datetime.fromisoformat(observed),
            )
            additions.extend(attach(records, observed, kinds={"appearance", "confirmed_lineup"}))
            native.append({"detail": deepcopy(detail), "observed_at": observed})
        result["observations"].extend(additions)
        result["native_details"].extend(native)
        metadata.update(status="completed" if seen == set(ids) else "partial", missing_ids=sorted(set(ids) - seen))
    except (ContextContractError, ValueError, TypeError, KeyError, OverflowError):
        provider.errors.append("Kontext fixtures: Empfang oder native Zuordnung nicht vollständig belegt")

    if wanted:
        requested = tuple(sorted(wanted))
        try:
            injuries, observed, metadata = obtain("injuries", requested)
            for row in injuries:
                if _native_id(row["fixture"]["id"]) not in wanted:
                    raise ContextContractError("injury batch contains an unrequested native event")
            additions = []
            for event in wanted.values():
                records = normalize_football_context(event, injuries=injuries, lineups=[], appearances=[],
                                                     observed_at=datetime.fromisoformat(observed))
                additions.extend(attach(records, observed, kinds={"availability"}))
            result["observations"].extend(additions)
            # Endpoint receipt completeness never certifies complete medical
            # coverage. Each team observation explicitly retains complete=False.
            metadata.update(status="completed", missing_ids=[])
        except (ContextContractError, ValueError, TypeError, KeyError, OverflowError):
            provider.errors.append("Kontext injuries: Empfang oder native Zuordnung nicht vollständig belegt")
    return result
