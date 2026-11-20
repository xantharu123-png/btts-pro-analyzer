"""Read-only performance of prospectively archived customer-facing selections.

No publication history is backfilled. Outcomes require an exact existing frozen
forecast binding; prices come from the real publication capture, not from the
internal model run's earlier quote. Missing linkage is a reported gap.
"""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS
from consumer_tip_history import EVENT_LEAD_SURFACES, LEAD_MANIFEST_VERSION, read_tip_publications
from forecast_selection import select_event_leads
from market_consensus import (
    ESPORTS_PRICE_SOURCE, ODDS_API_REFERENCE_SOURCE, REFERENCE_SOURCE,
    TEAM_PRICE_SOURCES, WETTFINDER_FETCH_MAX_AGE, WETTFINDER_QUOTE_MAX_AGE,
    exact_market_target,
)
from selection_performance import _summary, _utc, _verified_actual_start, build_selection_performance_report
from tip_publication import bind_forecast_ids


WETTFINDER_SURFACES = ("wettfinder_default_inventory", "wettfinder_automatic")


def _matchday_view(rows):
    """Score only causal, exactly bound WIN/LOSS rows; preserve every gap."""
    def counts(items):
        states = Counter(row["status"] for row in items)
        decided = states["WIN"] + states["LOSS"]
        p = (math.fsum(r["probability"] for r in items if r["status"] in {"WIN", "LOSS"}) / decided
             if decided else None)
        hit = states["WIN"] / decided if decided else None
        return dict(games=len({(r["sport"], r["event_key"]) for r in items}), selections=len(items),
                    wins=states["WIN"], losses=states["LOSS"], open=states["UNRESOLVED"],
                    voids=states["VOID"], unmatched=states["UNMATCHED"], decided=decided,
                    mean_announced_probability=p, hit_rate=hit,
                    announced_minus_actual_pp=100*(p-hit) if decided else None,
                    fresh_quotes=sum(r["quote_status"] == "fresh" for r in items))
    sports = defaultdict(list)
    for row in rows:
        sports[row["sport"]].append(row)
    return dict(summary=counts(rows), by_sport={s: counts(group) for s, group in sorted(sports.items())}, rows=rows)


def _first_card(tips):
    """The inventory records global highlights, not an event-specific lead flag.

    Only replay the displayed card rule when the archived rows establish one
    comparable revision. Publication order (highlights first) is not evidence
    of the unseen producer's revision anchor.
    """
    from selection_coherence import _role_binding
    revisions = {(_role_binding(tip), *(tip.get(key) for key in
                  ("starts_at", "modeled_at", "input_cutoff_at", "model_version", "policy_version"))) for tip in tips}
    if len(revisions) != 1:
        return None
    cards = [SimpleNamespace(**tip, key=tip["candidate_id"], scheduled_start=tip["starts_at"]) for tip in tips]
    leads = select_event_leads(cards, require_comparable=True)
    if len(leads) == 1:
        return next(t for t in tips if t["tip_id"] == leads[0].tip_id)
    return None


def _matchday(publications, first, selections, gap_index, in_window, *, confirmed=None, lead_surface=False):
    scored = {(row["publication_id"], row["tip_id"]): row for row in selections}

    def row_for(pub, tip, reason=None, *, unknown_card=False):
        key = pub["publication_id"], tip["tip_id"]
        row = scored.get(key)
        reason = reason or gap_index.get(key) or (row["clock_exclusion"] if row else "not_exactly_bound")
        if not reason and row["invalid_result_evidence"]:
            reason = "invalid_result_evidence"
        return dict(sport=tip["sport"], event_key=tip["event_key"], surface=pub["surface"],
                    publication_id=key[0], first_observed_at=pub["first_observed_at"],
                    tip_id=None if unknown_card else key[1], forecast_id=None if unknown_card or not row else row["forecast_id"],
                    market_key=None if unknown_card else tip["market_key"], selection=None if unknown_card else tip["selection"],
                    probability=None if unknown_card else tip["probability"],
                    model_version=None if unknown_card else tip["model_version"],
                    policy_version=None if unknown_card else tip["policy_version"],
                    modeled_at=None if unknown_card else tip["modeled_at"],
                    input_cutoff_at=None if unknown_card else tip["input_cutoff_at"],
                    status="UNMATCHED" if reason else row["outcome"], reason=reason,
                    quote_status=None if unknown_card or not row else row["quote_status"])

    markets = [row_for(pub, tip) for pub, tip in first.values() if in_window(tip)]
    by_event = defaultdict(list)
    for row in markets:
        by_event[(row["sport"], row["event_key"])].append(row)
    # Select the first inventory before inspecting linkage, outcomes or prices.
    earliest = {}
    for pub in publications:
        game_tips = defaultdict(list)
        for tip in pub["tips"]:
            event = tip["sport"], tip["event_key"]
            if event in by_event:
                game_tips[event].append(tip)
        for event, tips in game_tips.items():
            if event not in earliest:
                earliest[event] = [(pub, tips)]
            elif earliest[event][0][0]["first_observed_at"] == pub["first_observed_at"]:
                earliest[event].append((pub, tips))
    main, reconstruction, retro, differences = [], [], [], []
    for event, rows in sorted(by_event.items()):
        inventories = earliest[event]
        pub, tips = inventories[0]
        if len(inventories) != 1:
            reason = "ambiguous_first_publication_clock"
        elif not pub["complete"]:
            reason = "incomplete_first_publication"
        else:
            reason = None
        def card_row(lead, missing):
            if reason is None and lead is not None and in_window(lead):
                return row_for(pub, lead)
            return row_for(pub, tips[0], reason or (missing if lead is None else "first_card_outside_day"),
                           unknown_card=True)
        # Legacy inventories were captured AFTER the price floor. The original
        # revision/role anchor could have been removed. Replaying visible rows
        # cannot certify an actual lead, even when only one candidate remains.
        marked = tips if lead_surface else [tip for tip in tips if tip.get("featured_role") == "primary"]
        if (confirmed is not None and all(p["schema_version"] == LEAD_MANIFEST_VERSION for p, _ in inventories)
                and (not reason or event in confirmed)):
            main.append(confirmed.get(event) or card_row(None, "no_recorded_visible_event_lead"))
        else:
            main.append(card_row(marked[0] if len(marked) == 1 else None,
                                 "ambiguous_event_lead_roles" if marked else "no_archived_event_lead_role"))
        reconstruction.append(card_row(_first_card(tips) if reason is None else None,
                                       "no_comparable_first_card_revision"))
        # Descriptive comparison on the first observation of each distinct
        # market; never describe this retrospective maximum as the first card.
        retro.append(max(rows, key=lambda row: row["probability"]))
        first_row, hindsight = main[-1], retro[-1]
        if (first_row["market_key"], first_row["selection"]) != (hindsight["market_key"], hindsight["selection"]):
            why = (first_row["reason"] if first_row["tip_id"] is None else
                   "equal_probability_tie" if first_row["probability"] == hindsight["probability"] else
                   "different_market_in_later_inventory")
            differences.append(dict(sport=event[0], event_key=event[1], reason=why,
                                    first_publication_id=first_row["publication_id"], first_tip_id=first_row["tip_id"],
                                    first_market=first_row["market_key"], first_status=first_row["status"],
                                    retrospective_publication_id=hindsight["publication_id"],
                                    retrospective_tip_id=hindsight["tip_id"], retrospective_market=hindsight["market_key"],
                                    retrospective_status=hindsight["status"]))
    if confirmed:
        # Regular quote publications may offer a new lead without writing a new
        # legacy inventory. Include those real captures in the main-card view only.
        main.extend(confirmed[event] for event in sorted(confirmed.keys()-by_event.keys()))
    return dict(first_main_card=_matchday_view(main), all_distinct_markets=_matchday_view(markets),
                first_inventory_reconstruction=_matchday_view(reconstruction),
                first_card_evidence=dict(identified=sum(row["tip_id"] is not None for row in main),
                                         missing=sum(row["tip_id"] is None for row in main),
                                         missing_reasons=dict(Counter(row["reason"] for row in main if row["tip_id"] is None))),
                retrospective_catalogue_max=_matchday_view(retro),
                first_vs_retrospective_differences=differences,
                tickets={product: dict(ticket_count=None, reason="no_original_ticket_input")
                         for product in ("doublebet", "riskobet", "15k")},
                limitations=["First main card requires an explicit event lead, not a global highlight. "
                             "Legacy first inventories without that role are never backfilled. New receipts use the "
                             "first observed eligible lead on the offered default page or the rendered automatic page.",
                             "First inventory reconstruction uses only retained post-floor rows. It is not a historical main-card receipt.",
                             "Descriptive only: small samples and correlated markets cannot establish model error or profit.",
                             "The archive covers inventory, not original tickets, completed wagers or all customer visits."])


def _rescheduled_event_starts(forecast_db, cutoff):
    path = Path(forecast_db)
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=0.5)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM forecast_results "
            "WHERE CASE WHEN json_valid(payload_json) THEN json_extract(payload_json,'$.provenance.actual_starts_at') END IS NOT NULL LIMIT 100001").fetchall()
    if len(rows) > 100_000:
        raise ValueError("rescheduled result discovery exceeds bounded row limit")
    starts = defaultdict(set)
    for row in rows:
        actual = _verified_actual_start(dict(row), cutoff)
        if actual is not None:
            starts[row["event_key"]].add(actual)
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
    def in_window(tip):
        clocks = observed_starts.get(tip["event_key"]) or (_utc(tip["starts_at"]),)
        return any(lower <= clock < upper for clock in clocks)

    report["unique_archived_selections"] = sum(in_window(tip) for _, tip in first.values())
    report["archive_revisions_collapsed"] = total-len(first)
    joined, gaps, reasons, gap_index = {}, [], Counter(), {}
    def gap(publication, tip, reason):
        # An unlinked future/past selection is not a gap in the requested day.
        if not in_window(tip):
            return
        reasons[reason] += 1
        gap_index[publication["publication_id"], tip["tip_id"]] = reason
        if len(gaps) < 200:
            gaps.append(dict(tip_id=tip["tip_id"], event_key=tip["event_key"],
                             surface=publication["surface"], first_observed_at=publication["first_observed_at"], reason=reason))
    for publication, tip in first.values():
        capture = _utc(publication["first_observed_at"])
        if len(observed_starts.get(tip["event_key"], ())) > 1:
            gap(publication, tip, "conflicting_actual_start")
            continue
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
        capture = _utc(publication["first_observed_at"])
        effective = actual_starts.get(tip["event_key"], _utc(selected["effective_start"]))
        if not lower <= effective < upper:
            continue
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
    if surface in EVENT_LEAD_SURFACES.values():
        report["first_visible_cards"] = _matchday(publications, first, selections, gap_index, in_window,
                                                 lead_surface=True)["first_main_card"]["rows"]
    elif surface in WETTFINDER_SURFACES:
        lead_report = build_consumer_tip_performance_report(history_db, forecast_db,
            surface=EVENT_LEAD_SURFACES[surface], **args)
        confirmed = {(r["sport"], r["event_key"]): r for r in lead_report["first_visible_cards"]}
        report["matchday"] = _matchday(publications, first, selections, gap_index, in_window, confirmed=confirmed)
    return report
