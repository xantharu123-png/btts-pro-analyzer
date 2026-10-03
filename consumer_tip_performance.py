"""Read-only performance of prospectively archived customer-facing selections.

No publication history is backfilled. Outcomes require an exact existing frozen
forecast binding; prices come from the real publication capture, not from the
internal model run's earlier quote. Missing linkage is a reported gap.
"""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import math
import json
from pathlib import Path
import sqlite3

from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS
from consumer_tip_history import read_tip_publications
from market_consensus import (
    ESPORTS_PRICE_SOURCE, ODDS_API_REFERENCE_SOURCE, REFERENCE_SOURCE,
    TEAM_PRICE_SOURCES, WETTFINDER_FETCH_MAX_AGE, WETTFINDER_QUOTE_MAX_AGE,
    exact_market_target,
)
from selection_performance import _summary, _utc, build_selection_performance_report
from tip_publication import bind_forecast_ids


def _rescheduled_event_starts(forecast_db, cutoff):
    path = Path(forecast_db)
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=0.5)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        rows = conn.execute("SELECT event_key,observed_at,payload_json FROM forecast_results "
            "WHERE CASE WHEN json_valid(payload_json) THEN json_extract(payload_json,'$.provenance.actual_starts_at') END IS NOT NULL LIMIT 100001").fetchall()
    if len(rows) > 100_000:
        raise ValueError("rescheduled result discovery exceeds bounded row limit")
    starts = defaultdict(set)
    for event_key, observed, raw in rows:
        try:
            actual = _utc(json.loads(raw)["provenance"]["actual_starts_at"])
            if _utc(observed) <= cutoff:
                starts[event_key].add(actual)
        except (ValueError, TypeError, KeyError):
            # Discovery never infers an outcome. Evidence integrity is checked
            # again by the exact-bound result report before any scoring.
            continue
    return starts


def _published_quote(tip, capture, effective_start):
    quote = tip.get("quote") or {}
    status = quote.get("status", "missing")
    if status != "observed":
        return status, None
    try:
        odds = quote.get("odds")
        if (type(odds) not in (int, float) or not math.isfinite(odds) or odds <= 1
                or not isinstance(quote.get("bookmaker_id"), str) or not quote["bookmaker_id"].strip()):
            return "invalid", None
        observed, fetched = _utc(quote["observed_at"]), _utc(quote["fetched_at"])
        if not observed <= fetched <= capture < effective_start:
            return "invalid", None
        if (capture-fetched > WETTFINDER_FETCH_MAX_AGE
                or capture-observed > WETTFINDER_QUOTE_MAX_AGE):
            return "stale", None
        if (_utc(quote["starts_at"]) != _utc(tip["starts_at"])
                or quote.get("market_key") != tip["market_key"]):
            return "invalid", None
        sport = tip["sport"]
        if sport == "football":
            target = exact_market_target(tip["market_key"])
            bound = (target is not None and quote.get("source") == REFERENCE_SOURCE
                     and type(tip.get("fixture_id")) is int
                     and quote.get("fixture_id") == tip["fixture_id"]
                     and quote.get("bet_name") == target[0] and quote.get("selection") == target[1])
        else:
            source = ODDS_API_REFERENCE_SOURCE if sport == "tennis" else ESPORTS_PRICE_SOURCE if sport == "esports" else TEAM_PRICE_SOURCES.get(sport)
            bound = (bool(source) and quote.get("source") == source
                     and bool(quote.get("provider_event_id"))
                     and quote.get("selection") == tip["selection"])
            expected_quote_event = tip.get("quote_provider_event_id")
            if expected_quote_event is not None:
                bound = bound and str(quote.get("provider_event_id")) == str(expected_quote_event)
        if not bound:
            return "invalid", None
        return ("below_floor", float(odds)) if odds < MINIMUM_RECOMMENDED_DECIMAL_ODDS else ("fresh", float(odds))
    except (ValueError, TypeError, KeyError, OverflowError):
        return "invalid", None


def build_consumer_tip_performance_report(
    history_db, forecast_db, *, from_day, through_day, as_of=None,
    surface=None, timezone_name="Europe/Zurich", unit_stake=1.0,
):
    """Count the first real capture per event/market/side, without pool fallback.

    An optional surface filter evaluates that inventory only. Results are joined
    at the original capture time, with exact probability, input clocks, model,
    and participant roles. Unlinked RiskBet snapshots remain unsupported gaps.
    """
    cutoff = _utc(as_of or datetime.now(timezone.utc))
    args = dict(from_day=from_day, through_day=through_day, as_of=cutoff,
                timezone_name=timezone_name, unit_stake=unit_stake)
    report = build_selection_performance_report(forecast_db, forecast_ids=[], **args)
    report.update(schema_version="consumer-tip-performance-v1", cohort="archived_publications",
                  history_database_present=Path(history_db).is_file(), surface_filter=surface,
                  publication_count=0, incomplete_publications=0, unique_archived_selections=0,
                  archive_revisions_collapsed=0, linkage_gap_count=0, linkage_gaps=[],
                  linkage_gap_reasons={}, publication_quote_source="actual_publication_capture")
    report["limitations"] = [
        "Only prospectively archived final UI inventories are considered; no historical customer-tip list is reconstructed.",
        "A publication receipt proves availability in the surface, not a customer's view or an actual wager.",
        "Repeated publication revisions use their first real capture, never the best later price or probability.",
        "Returns use the publication's exact fresh bookmaker point at or above 1.20, not the earlier model-run quote.",
        "Unlinked frozen RiskBet snapshots, missing prices, and unresolved results remain gaps; none are guessed.",
        "Different selections of one event are correlated, and this report does not prove improved betting quality.",
    ]
    lower, upper = _utc(report["window_start_utc"]), _utc(report["window_end_exclusive_utc"])
    observed_starts = _rescheduled_event_starts(forecast_db, cutoff)
    actual_starts = {event: next(iter(values)) for event, values in observed_starts.items() if len(values) == 1}
    # Keep discovery membership unchanged even for conflicting observations;
    # the evidence report still detects and rejects their conflicting results.
    related = {event for event, values in observed_starts.items()
               if any(lower <= start < upper for start in values)}
    publications = read_tip_publications(history_db, until=cutoff, surface=surface,
        event_window_start=lower, event_window_end=upper, related_event_keys=related)
    report["publication_count"] = len(publications)
    report["incomplete_publications"] = sum(not item["complete"] for item in publications)
    first, total = {}, 0
    for publication in publications:
        for tip in publication["tips"]:
            total += 1
            if total > 100_000:
                raise ValueError("publication window exceeds bounded selection limit")
            identity = (tip["event_key"], tip["sport"], tip["market_key"], tip["selection"])
            if identity not in first:
                first[identity] = (publication, tip)
    # A relevant inventory can also contain matches on unrelated days. Count
    # only requested event days, retaining the first real publication revision
    # and a unique recorded actual-kickoff override when one exists.
    report["unique_archived_selections"] = sum(
        lower <= actual_starts.get(tip["event_key"], _utc(tip["starts_at"])) < upper
        for _, tip in first.values())
    report["archive_revisions_collapsed"] = total-len(first)
    joined, gaps, reasons = {}, [], Counter()
    def gap(publication, tip, reason):
        # An unlinked future/past selection is not a gap in the requested day.
        if not lower <= _utc(tip["starts_at"]) < upper:
            return
        reasons[reason] += 1
        if len(gaps) < 200:
            gaps.append(dict(tip_id=tip["tip_id"], event_key=tip["event_key"],
                             surface=publication["surface"], first_observed_at=publication["first_observed_at"], reason=reason))
    for publication, tip in first.values():
        capture = _utc(publication["first_observed_at"])
        if not all(tip.get(name) for name in ("model_version", "policy_version", "modeled_at", "input_cutoff_at")):
            gap(publication, tip, "missing_exact_model_identity")
            continue
        # bind_forecast_ids discards supplied hints before performing an exact,
        # read-only join. Never trust an archive's arbitrary forecast_id alone.
        bound, = bind_forecast_ids([tip], as_of=capture, db_path=forecast_db)
        forecast_id = bound.get("forecast_id")
        if forecast_id is None:
            gap(publication, tip, "unlinked_frozen_snapshot" if tip.get("snapshot_id") else "missing_exact_forecast_binding")
            continue
        if tip.get("forecast_id") is not None and tip["forecast_id"] != forecast_id:
            gap(publication, tip, "archived_forecast_binding_mismatch")
            continue
        joined[forecast_id] = (publication, tip)
    evidence = build_selection_performance_report(forecast_db, forecast_ids=list(joined), **args)
    for field in ("database_present", "decision_revisions_read", "duplicate_revisions_collapsed",
                  "clock_exclusions", "integrity_error_count", "integrity_errors"):
        report[field] = evidence[field]
    selections = []
    included = {selected["forecast_id"] for selected in evidence["selections"]}
    for forecast_id, (publication, tip) in joined.items():
        if forecast_id not in included:
            gap(publication, tip, "forecast_outside_actual_window_or_invalid_evidence")
    for selected in evidence["selections"]:
        publication, tip = joined[selected["forecast_id"]]
        capture, effective = _utc(publication["first_observed_at"]), _utc(selected["effective_start"])
        # A fixture may have been moved earlier after the original publication.
        if capture >= effective:
            gap(publication, tip, "publication_after_actual_start")
            continue
        status, odds = _published_quote(tip, capture, effective)
        selected = dict(selected, publication_id=publication["publication_id"],
                        tip_id=tip["tip_id"], surface=publication["surface"],
                        first_observed_at=publication["first_observed_at"],
                        featured_role=tip.get("featured_role"), quote_status=status,
                        entry_odds=odds, entry_quote_id=None,
                        hypothetical_return_units=None)
        if selected["causal"] and status == "fresh" and selected["outcome"] in {"WIN", "LOSS"}:
            selected["hypothetical_return_units"] = odds-1 if selected["outcome"] == "WIN" else -1.0
        selections.append(selected)
    report["selections"] = selections
    report["summary"] = _summary(selections, report["hypothetical_unit_stake"])
    groups, days = defaultdict(list), defaultdict(list)
    for selected in selections:
        groups[(selected["sport"], selected["market_key"], selected["model_version"], selected["policy_version"])].append(selected)
        days[selected["day"]].append(selected)
    report["groups"] = [dict(zip(("sport", "market_key", "model_version", "policy_version"), key),
                             **_summary(rows, report["hypothetical_unit_stake"])) for key, rows in sorted(groups.items())]
    report["daily"] = [dict(day=day, **_summary(rows, report["hypothetical_unit_stake"])) for day, rows in sorted(days.items())]
    report["linkage_gap_count"] = sum(reasons.values())
    report["linkage_gap_reasons"] = dict(reasons)
    report["linkage_gaps"] = gaps
    return report
