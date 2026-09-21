"""Exclude known retracted native pairings from current forecast views only.

Read already received facts; never fetch, predict, settle or rewrite history.
Legacy forecasts without native context retain their existing reader contract.
"""
import json

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader
from context_models.tennis_live import validate_context_model
from context_observations import _SELECT, _decode_receipt
from context_sources.tennis_status import STATUS_SCHEMA, _select_tennis_row


def current_native_forecasts(rows, *, as_of, path=None):
    decision = canonical_timestamp(as_of)
    rows = list(rows)
    linked = {}
    for index, row in enumerate(rows):
        context = json.loads(row.get("context_json") or "{}")
        if "context_model" in context:
            sidecar = validate_context_model(context["context_model"])
            event = sidecar["event"]
            if (row.get("fixture_source") != "ESPN" or row.get("tour") != event["tour"]
                    or event["event_key"] != f"espn:tennis:{event['tour']}:match:{row.get('provider_event_id')}"
                    or canonical_timestamp(row["scheduled_start_utc"]) != event["scheduled_start"]):
                raise ContextIntegrityError("current fixture differs from its native forecast identity")
            linked[index] = event
    if not linked:
        return rows
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    allowed, checked = set(), {}
    with _reader(path) as connection:
        for index, event in linked.items():
            if event["scheduled_start"] <= decision:
                continue
            key = (event["event_key"], event["tour"])
            if key not in checked:
                # Validate physical bytes before selecting source/tour/time.
                # One query per native event, not a whole-tour replay per card.
                history = []
                for raw in connection.execute(_SELECT+" WHERE r.event_key=?", (event["event_key"],)):
                    selected = _select_tennis_row(_decode_receipt(raw), decision, event["tour"])
                    if selected is not None:
                        history.append(selected)
                newest = max((r["observed_at"] for r in history), default=None)
                checked[key] = [r for r in history if r["observed_at"] == newest]
            latest = checked[key]
            if len(latest) != 1:
                continue
            observed = latest[0]
            payload = observed["payload"]
            if (observed["source_schema"] == STATUS_SCHEMA
                    and observed["competition"] == event["competition"]
                    and observed["format"] == event["format"]
                    and not payload["issues"] and payload["status"] == "scheduled"
                    and payload["participant_ids"] == [event["home_id"], event["away_id"]]
                    and payload["scheduled_start"] == event["scheduled_start"]
                    and observed["schedule_revision"] == event["schedule_revision"]
                    and decision < payload["scheduled_start"]):
                allowed.add(index)
    return [row for index, row in enumerate(rows) if index not in linked or index in allowed]
