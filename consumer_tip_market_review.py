"""Read-only Wettfinder market review; archived outcomes and price evidence are independent."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo

from consumer_tip_performance import WETTFINDER_SURFACES, build_consumer_tip_performance_report
from selection_performance import _utc


_COHORTS = ("first_main_card", "all_distinct_markets")


def _market_group(sport, key):
    if not key:
        return "unrecorded"
    if sport != "football":
        return key
    from challenge_engine import MARKET_BY_KEY

    market = MARKET_BY_KEY.get(key)
    if market is None:
        return key
    if market.kind in ("corner_total", "team_corners"):
        return "corners"
    if market.kind in ("total", "team_total"):
        return "goals_" + market.side.rsplit("_", 1)[-1]
    if market.kind in ("total_range", "team_range"):
        return "goals_range"
    return market.kind


def _summary(rows):
    counts = Counter(r["status"] for r in rows)
    decided = [r for r in rows if r["status"] in ("WIN", "LOSS")]
    n = len(decided)
    prices = [r["hypothetical_return_units"] for r in decided
              if r["quote_status"] == "fresh" and r["hypothetical_return_units"] is not None]
    wins = counts["WIN"]
    expected = math.fsum(r["probability"] for r in decided)
    return dict(games=len({(r["sport"], r["event_key"]) for r in rows}), selections=len(rows),
                wins=wins, losses=counts["LOSS"], decided=n, open=counts["UNRESOLVED"],
                void=counts["VOID"], unmatched=counts["UNMATCHED"], hit_rate=wins/n if n else None,
                mean_model_probability=expected/n if n else None, expected_wins=expected if n else None,
                quote_statuses=dict(Counter((r["quote_status"] or "unverified") if r["status"] != "UNMATCHED"
                                           else "unverified" for r in rows)),
                stale_quote_reasons=dict(Counter(r["stale_quote_reason"] for r in rows if r["stale_quote_reason"])),
                priced_decisions=len(prices), hypothetical_roi=math.fsum(prices)/len(prices) if prices else None,
                model_versions=sorted({r["model_version"] for r in rows if r["model_version"]}))


def _split(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        sport = row["sport"]
        groups[sport][_market_group(sport, row["market_key"])].append(row)
    return dict(summary=_summary(rows), by_sport_and_market={
        sport: {market: _summary(tips) for market, tips in sorted(markets.items())}
        for sport, markets in sorted(groups.items())})


def build_market_review(history_db, forecast_db, *, from_day, through_day, as_of=None,
                        surface=None, timezone_name="Europe/Zurich", unit_stake=1.0):
    first, last = date.fromisoformat(from_day), date.fromisoformat(through_day)
    span = (last-first).days + 1
    if span not in range(1, 32):
        raise ValueError("market review requires 1–31 completed days")
    surface = surface or WETTFINDER_SURFACES[0]
    if surface not in WETTFINDER_SURFACES or timezone_name != "Europe/Zurich":
        raise ValueError("market review requires a Wettfinder archive surface and Zurich calendar days")
    cutoff = _utc(as_of or datetime.now(timezone.utc))
    if last >= cutoff.astimezone(ZoneInfo(timezone_name)).date():
        raise ValueError("through-day must be a completed local calendar day")
    daily, overall = [], {key: [] for key in _COHORTS}
    for offset in range(span):
        day = (first+timedelta(days=offset)).isoformat()
        report = build_consumer_tip_performance_report(history_db, forecast_db, surface=surface,
            from_day=day, through_day=day, as_of=cutoff, unit_stake=unit_stake, timezone_name=timezone_name,
            include_market_metrics=True)
        data = dict(day=day, lead_evidence=report["matchday"]["first_card_evidence"],
                    databases_present=report["history_database_present"] and report["database_present"],
                    integrity_errors=report["integrity_error_count"])
        for key in _COHORTS:
            rows = report["matchday"][key]["rows"]
            data[key] = _split(rows)
            overall[key].extend(rows)
        daily.append(data)
    return dict(schema_version="wettfinder-market-review-v1", surface=surface, as_of=cutoff.isoformat(),
                timezone=timezone_name, daily=daily, overall={k: _split(v) for k, v in overall.items()},
                limitations=["Only archived first receipts, never inferred main cards or actual wagers.",
                             "ROI is a hypothetical flat stake on decided rows with original fresh prices only.",
                             "Unmatched rows with conflicting kickoff dates may appear under multiple days.",
                             "Market selections within a game are correlated; results do not establish an edge."])
