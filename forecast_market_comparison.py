"""Read-only, event-balanced model comparison with complete native markets.

This is measurement, not a selection gate. A single offered price cannot be
turned into a margin-free probability. Entry and closing cohorts stay separate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sqlite3

from betting_math import BettingMathError, proportional_no_vig_market
from forecast_evidence import _TABLES, _utc
from model_loss_statistics import paired_advantage_statistics


def _contract(row, identity):
    """Only mutually exclusive, exhaustive, identically settled markets."""
    key = row["market_key"]
    if row["sport"] == "football":
        if key in {"RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY"}:
            return "RESULT", key.removeprefix("RESULT_"), ("HOME", "DRAW", "AWAY")
        if key in {"BTTS_YES", "BTTS_NO"}:
            return "BTTS", key.removeprefix("BTTS_"), ("YES", "NO")
        match = re.fullmatch(r"(TOTAL|HOME|AWAY|CORNERS|HOME_CORNERS|AWAY_CORNERS|YELLOW|HOME_YELLOW|AWAY_YELLOW)_(OVER|UNDER)_(\d+)_5", key)
        if match:
            prefix, side, line = match.groups()
            return f"{prefix}_{line}_5", side, ("OVER", "UNDER")
    if row["sport"] in {"tennis", "esports"} and key == "H2H":
        a, b, selected = (identity.get(name) for name in
                          ("competitor_a", "competitor_b", "selected_competitor"))
        if all(isinstance(name, str) and name.strip() for name in (a, b)) and a != b and selected in (a, b):
            return "H2H", selected, (a, b)
    return None


def _loss(probabilities, outcomes):
    brier = sum((p-y)**2 for p, y in zip(probabilities, outcomes))/len(outcomes)
    log_loss = -sum(y*math.log(max(1e-15, min(1-1e-15, p)))
        for p, y in zip(probabilities, outcomes))
    return brier, log_loss


def build_market_comparison(db_path: str | Path, *, as_of=None) -> dict:
    """Compare frozen causal forecasts to complete same-book/time prices.

    Only compact scalar fields are read; large context payloads are never loaded.
    Revisions, markets and bookmakers are averaged within each event before
    calculating paired statistics. No independent game count is manufactured.
    """
    path = Path(db_path)
    cutoff = _utc(as_of or datetime.now(timezone.utc))
    coverage = Counter(entry_quotes=0, closing_quotes=0, first_causal_selections=0,
        supported_selections=0, complete_model_markets=0, resolved_model_markets=0,
        matched_market_sets=0, matched_unique_events=0)
    report = {"as_of": cutoff.isoformat(), "database_present": path.is_file(),
        "groups": [], "coverage": coverage,
        "score_units": "Brier: mean squared outcome error per complete market; log loss: negative log probability of the realized outcome; both averaged within each event.",
        "policy": "First causal forecast per event/selection/model/policy; complete same-revision market; same native event, bookmaker, observation and fetch time; entry and closing separate; one averaged loss per event.",
        "limitations": ["Proportional margin removal is a market benchmark, not a true probability.",
            "Entry prices and closing prices are separate benchmarks, not interchangeable cohorts.",
            "Different bookmakers and markets from one event are not independent observations.",
            "Unsupported, incomplete, contradictory or unpriced outcome sets are excluded, never synthesized.",
            "Paired intervals and p-values are exploratory and unadjusted for model/policy cohort selection, not approval statistics.",
            "Accuracy differences are not evidence of profitable betting or a model activation decision."]}
    if not path.is_file():
        return report
    markets, forecast_lookup, seen = {}, {}, set()
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not _TABLES.issubset(tables):
            raise ValueError("incomplete forecast evidence database")
        results = {}
        for row in conn.execute("SELECT event_key,market_key,selection,outcome,observed_at,"
                "json_extract(payload_json,'$.provenance.actual_starts_at') actual_start, "
                "json_extract(payload_json,'$.provenance.provider') result_provider, "
                "json_extract(payload_json,'$.provenance.provider_event_id') result_event "
                "FROM forecast_results WHERE observed_at<=? AND json_valid(payload_json) "
                "ORDER BY observed_at,result_id", (cutoff.isoformat(),)):
            result_key = (row["event_key"], row["market_key"], row["selection"])
            if result_key not in results:
                results[result_key] = dict(row)
            else:
                prior = results[result_key]
                if prior is not None and any(prior[field] != row[field] for field in
                        ("outcome", "result_provider", "result_event", "actual_start")):
                    # The append owner rejects contradictory outcomes. A damaged
                    # store must not make the report choose a convenient result.
                    results[result_key] = None
        query = """SELECT forecast_id,run_id,event_key,sport,market_key,selection,
            model_version,policy_version,starts_at,decision_at,
            json_extract(payload_json,'$.probability') probability,
            json_type(payload_json,'$.probability') probability_type,
            json_extract(payload_json,'$.modeled_at') modeled,
            json_extract(payload_json,'$.input_cutoff_at') input_cutoff,
            json_extract(payload_json,'$.recorded_at') recorded,
            json_extract(payload_json,'$.quote_identity') identity
            FROM forecast_rows WHERE decision_at<=? AND json_valid(payload_json)
            ORDER BY decision_at,forecast_id"""
        for row in conn.execute(query, (cutoff.isoformat(),)):
            result = results.get((row["event_key"], row["market_key"], row["selection"]))
            try:
                start = _utc((result or {}).get("actual_start") or row["starts_at"])
                decision, modeled, input_cutoff, recorded = map(_utc,
                    (row["decision_at"], row["modeled"], row["input_cutoff"], row["recorded"]))
                p = row["probability"]
                if not (input_cutoff <= modeled <= decision < start and decision <= recorded < start
                        and recorded <= cutoff and row["probability_type"] in {"integer", "real"}
                        and isinstance(p, (int, float)) and not isinstance(p, bool)
                        and math.isfinite(p) and 0 <= p <= 1):
                    continue
                identity = json.loads(row["identity"])
                if not isinstance(identity, dict):
                    continue
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            unique = tuple(row[field] for field in ("sport", "event_key", "market_key", "selection", "model_version", "policy_version"))
            if unique in seen:
                continue
            seen.add(unique)
            coverage["first_causal_selections"] += 1
            contract = _contract(row, identity)
            if contract is None:
                continue
            coverage["supported_selections"] += 1
            family, side, expected = contract
            native = tuple(identity.get(field) for field in ("fixture_id", "fixture_source", "provider_event_id",
                "home_id", "away_id", "home_team", "away_team", "competitor_a_id", "competitor_b_id", "competitor_a", "competitor_b"))
            if any(value is not None and (isinstance(value, bool) or not isinstance(value, (str, int)))
                   for value in native):
                continue
            if result is not None:
                provider = identity.get("fixture_source") or ("api-football" if row["sport"] == "football" else None)
                event = identity.get("provider_event_id") or (identity.get("fixture_id") if row["sport"] == "football" else None)
                if (not isinstance(result["result_provider"], str) or not isinstance(provider, str)
                        or result["result_provider"].casefold() != provider.casefold()
                        or event is None or str(event) != result["result_event"]):
                    result = None
            key = tuple(row[field] for field in ("sport", "model_version", "policy_version", "event_key", "run_id", "decision_at", "starts_at"))+(family, native)
            market = markets.setdefault(key, {"expected": expected, "rows": {}, "snapshots": {}, "start": start,
                                             "native_pair_present": False})
            if side in market["rows"]:
                market["rows"][side] = None  # Ambiguous labels are not merged.
                continue
            record = dict(row)
            record.update(result=result, identity=identity, start=start, decision=decision)
            market["rows"][side] = record
            forecast_lookup[row["forecast_id"]] = (key, side)
        for row in conn.execute("SELECT forecast_id,kind,bookmaker_id,observed_at,fetched_at,odds,payload_json "
                "FROM forecast_quotes WHERE fetched_at<=? ORDER BY observed_at,quote_id", (cutoff.isoformat(),)):
            if row["kind"] in {"entry", "closing"}:
                coverage[row["kind"]+"_quotes"] += 1
            found = forecast_lookup.get(row["forecast_id"])
            if found is None or row["kind"] not in {"entry", "closing"}:
                continue
            key, side = found
            market = markets[key]
            forecast = market["rows"][side]
            if forecast is None:
                continue
            try:
                quote = json.loads(row["payload_json"])
                observed, fetched = _utc(row["observed_at"]), _utc(row["fetched_at"])
                if not (observed <= fetched < forecast["start"] and row["bookmaker_id"]):
                    continue
                if row["kind"] == "entry" and fetched > forecast["decision"]:
                    continue
                if row["kind"] == "closing" and not (forecast["decision"] < observed
                        and forecast["start"]-observed <= timedelta(hours=1)):
                    continue
                if (_utc(quote["starts_at"]) != _utc(forecast["starts_at"])
                        or quote.get("market_key") != forecast["market_key"]
                        or quote.get("fixture_id") != forecast["identity"].get("fixture_id")
                        or not isinstance(quote.get("source"), str) or not quote["source"]
                        or quote.get("provider_event_id") is not None and
                           (isinstance(quote["provider_event_id"], bool) or not isinstance(quote["provider_event_id"], (str, int)))):
                    continue
                for field in ("forecast_id", "kind", "bookmaker_id", "observed_at", "fetched_at", "odds"):
                    if quote.get(field) != row[field]:
                        raise ValueError("quote columns disagree with native observation")
                if forecast["sport"] != "football" and not quote.get("provider_event_id"):
                    continue
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
            snapshot = (row["kind"], row["bookmaker_id"], quote["source"], quote.get("fixture_id"),
                quote.get("provider_event_id"), row["observed_at"], row["fetched_at"])
            points = market["snapshots"].setdefault(snapshot, {})
            if side in points and points[side] != row["odds"]:
                points[side] = None
            else:
                points.setdefault(side, row["odds"])
            complete = quote.get("complete_market")
            if forecast["sport"] == "tennis" and isinstance(complete, dict):
                expected = market["expected"]
                identity = forecast["identity"]
                native = complete.get("outcomes")
                if (complete.get("market_key") != "H2H" or complete.get("competitors") != list(expected)
                        or complete.get("fixture_source") != identity.get("fixture_source")
                        or complete.get("provider_event_id") != identity.get("provider_event_id")
                        or complete.get("quote_provider_event_id") != quote.get("provider_event_id")
                        or complete.get("scheduled_start") != forecast["starts_at"]
                        or not isinstance(native, list) or len(native) != 2
                        or not all(isinstance(item, dict) and isinstance(item.get("selection"), str) for item in native)):
                    continue
                native_points = {item.get("selection"): item.get("odds") for item in native}
                if set(native_points) != set(expected) or native_points.get(side) != row["odds"]:
                    continue
                try:
                    proportional_no_vig_market(native_points.values())
                except BettingMathError:
                    continue
                for other_side, odds in native_points.items():
                    if other_side in points and points[other_side] != odds:
                        points[other_side] = None
                    else:
                        points.setdefault(other_side, odds)
                market["native_pair_present"] = True

    groups, all_events = {}, set()
    for key, market in markets.items():
        expected, rows = market["expected"], market["rows"]
        if market["native_pair_present"] and len(rows) == 1 and len(expected) == 2:
            # Binary complement is report arithmetic, never an inserted model
            # prediction or a fabricated opposing bookmaker price.
            selected = next(iter(rows))
            original = rows[selected]
            if original is not None and original["result"] and original["result"]["outcome"] in {"WIN", "LOSS"}:
                other = next(side for side in expected if side != selected)
                rows[other] = {**original, "probability": 1-original["probability"],
                    "result": {**original["result"], "outcome": "LOSS" if original["result"]["outcome"] == "WIN" else "WIN"}}
                coverage["binary_complement_report_selections"] += 1
        if set(rows) != set(expected) or any(rows[side] is None for side in expected):
            coverage["incomplete_model_markets"] += 1
            continue
        probabilities = [rows[side]["probability"] for side in expected]
        if not math.isclose(sum(probabilities), 1., abs_tol=5e-6, rel_tol=0):
            coverage["inconsistent_model_markets"] += 1
            continue  # Never normalize a contradictory model distribution.
        coverage["complete_model_markets"] += 1
        results = [rows[side]["result"] for side in expected]
        if any(result is None or result["outcome"] not in {"WIN", "LOSS"}
                or _utc(result["observed_at"]) <= rows[side]["decision"]
                or rows[side]["start"] != market["start"] for side, result in zip(expected, results)):
            coverage["unresolved_or_noncausal_markets"] += 1
            continue
        outcomes = [int(result["outcome"] == "WIN") for result in results]
        if sum(outcomes) != 1:
            coverage["contradictory_result_markets"] += 1
            continue
        coverage["resolved_model_markets"] += 1
        # Use the latest complete observation from each bookmaker, never a
        # best-price composite assembled from different companies or clocks.
        latest = {}
        for snapshot, points in market["snapshots"].items():
            if set(points) != set(expected) or any(points[side] is None for side in expected):
                continue
            try:
                prices = proportional_no_vig_market(points[side] for side in expected)
            except BettingMathError:
                continue
            book_key = snapshot[:5]
            if book_key not in latest or snapshot[5:] > latest[book_key][0][5:]:
                latest[book_key] = (snapshot, prices)
        by_kind = defaultdict(list)
        for snapshot, prices in latest.values():
            by_kind[snapshot[0]].append(_loss(prices.no_vig_probabilities, outcomes))
        if not by_kind:
            coverage["resolved_markets_without_complete_prices"] += 1
        for kind, losses in by_kind.items():
            group_key = key[:3]+(kind,)
            group = groups.setdefault(group_key, {"events": defaultdict(list), "snapshots": 0, "sets": 0})
            model_loss = _loss(probabilities, outcomes)
            market_loss = tuple(sum(item[i] for item in losses)/len(losses) for i in (0, 1))
            group["events"][key[3]].append((market["start"], *model_loss, *market_loss))
            group["snapshots"] += len(losses)
            group["sets"] += 1
            coverage["matched_market_sets"] += 1
            all_events.add((key[0], key[3]))
    coverage["matched_unique_events"] = len(all_events)
    for key, group in sorted(groups.items()):
        events = []
        for identity, rows in group["events"].items():
            events.append((min(row[0] for row in rows), identity,
                *(sum(row[i] for row in rows)/len(rows) for i in range(1, 5))))
        events.sort()
        advantages = [row[4]-row[2] for row in events]
        advantage, error, lower, p_value = paired_advantage_statistics(advantages)
        report["groups"].append(dict(zip(("sport", "model_version", "policy_version", "kind"), key)) | {
            "unique_events": len(events), "market_sets": group["sets"],
            "bookmaker_snapshots": group["snapshots"],
            "model_brier": sum(row[2] for row in events)/len(events),
            "model_log_loss": sum(row[3] for row in events)/len(events),
            "market_brier": sum(row[4] for row in events)/len(events),
            "market_log_loss": sum(row[5] for row in events)/len(events),
            "brier_advantage": advantage, "paired_hac_standard_error": error,
            "paired_one_sided_95pct_lower_bound": lower, "paired_one_sided_p_value": p_value})
    return report
