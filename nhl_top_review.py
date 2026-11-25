"""Read-only pre-registered NHL validation; never called by the app or by a timer."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
from statistics import median
from zoneinfo import ZoneInfo

from forecast_market_comparison import _native_selection_prices
from nhl_top_statistics import evaluate_nhl_top, nhl_top_coverage
from selection_performance import _causal, _forecast, _quote, _result, _role_binding, _utc


ZURICH = ZoneInfo("Europe/Zurich")
MODEL = "sports-prematch-research-v1"
POLICY = "team-sport-descriptive-v1"
SETTLEMENT_RULE = "riskobet-settlement-v1"
PILOT_FIRST, PILOT_LAST = date(2026, 11, 12), date(2026, 11, 24)
PILOT_CUTOFF = datetime(2026, 11, 25, 10, 31, tzinfo=ZURICH)
FORWARD_FIRST, FORWARD_LAST = date(2026, 11, 26), date(2027, 3, 31)
OPEN_AT = datetime(2027, 4, 3, tzinfo=ZURICH)


def _identity(row):
    identity = row["quote_identity"]
    roles = _role_binding(row)
    teams = identity.get("competitor_a"), identity.get("competitor_b")
    if (row["native_event"][:2] != ("ice_hockey", "nhl") or identity.get("source") != "team_sport_research"
            or not roles or roles[0] != "ids" or not all(isinstance(t, str) and t.strip() for t in teams)
            or teams[0].strip().casefold() == teams[1].strip().casefold()
            or row["selection"] not in teams or row["selection"] != identity.get("selected_competitor")):
        raise ValueError("incomplete NHL two-way identity")
    stem, _, side = row["candidate_id"].rpartition(":")
    if (not stem.startswith("team_sport_research:snapshot_")
            or side != ("home" if row["selection"] == teams[0] else "away")):
        raise ValueError("unbound NHL snapshot side")
    return roles, teams, stem


def _first_favorites(conn, bounds, cutoff, counts):
    events = defaultdict(lambda: defaultdict(list))
    keys = defaultdict(set)
    for f in conn.execute("""SELECT f.*, r.payload_json run_json, r.decision_at run_decision
           FROM forecast_rows f JOIN forecast_runs r USING(run_id)
           WHERE f.sport='ice_hockey' AND f.market_key='H2H' AND f.model_version=? AND f.policy_version=?
             AND f.starts_at>=? AND f.starts_at<? AND f.decision_at<=?""", (*bounds, cutoff.isoformat())):
        try:
            row = _forecast(dict(f), {"payload_json": f["run_json"], "decision_at": f["run_decision"]})
            roles, teams, snapshot = _identity(row)
            start, recorded = _utc(row["starts_at"]), _utc(row["recorded_at"])
            if recorded > cutoff or _causal(row, start):
                raise ValueError("not a causal cutoff observation")
        except (ValueError, KeyError, TypeError, OverflowError):
            counts["rejected_forecast_rows"] += 1
            continue
        event = row["native_event"][2]
        keys[event].add((row["event_key"], start, roles, teams))
        events[event][_utc(row["decision_at"]), f["run_id"], snapshot,
                      _utc(row["modeled_at"]), _utc(row["input_cutoff_at"])].append(row)
    for event, revisions in events.items():
        if len(keys[event]) != 1:
            counts["ambiguous_fixture"] += 1
            continue
        _, start, _, teams = next(iter(keys[event]))
        complete = [(k, rows) for k, rows in revisions.items() if len(rows) == 2
                    and {r["selection"] for r in rows} == set(teams)
                    and math.isclose(sum(r["probability"] for r in rows), 1., rel_tol=0, abs_tol=1e-8)]
        if not complete:
            counts["missing_model_pair"] += 1
            continue
        earliest = min(k[0] for k, _ in complete)
        first = [rows for k, rows in complete if k[0] == earliest]
        if len(first) != 1:
            counts["ambiguous_first_revision"] += 1
            continue
        counts["first_nhl_forecasts"] += 1
        favorite = max(first[0], key=lambda row: row["probability"])
        p = favorite["probability"]
        counts["favorite_70"] += round(100*p, 1) >= 70
        if p >= .60:
            counts["favorite_60"] += 1
            yield dict(event_id=event, start=start, p_model=p, favorite=favorite, teams=teams, rows=first[0])


def _quotes(conn, args, cutoff, games, counts):
    first_row = {row["forecast_id"]: (g, row) for g in games for row in g["rows"]}
    opens = defaultdict(lambda: defaultdict(set))
    closing_events = set()
    for q in conn.execute("""SELECT q.*,f.event_key evidence_event FROM forecast_quotes q JOIN forecast_rows f USING(forecast_id)
             WHERE f.sport='ice_hockey' AND f.market_key='H2H' AND f.model_version=? AND f.policy_version=?
               AND f.starts_at>=? AND f.starts_at<? AND q.fetched_at<=?
               AND json_extract(f.payload_json,'$.quote_identity.fixture_source')='NHL'""", (*args, cutoff.isoformat())):
        if q["kind"] == "closing":
            closing_events.add(q["evidence_event"])  # inventory only; never admissible for the first price
            continue
        matched = first_row.get(q["forecast_id"])
        if not matched or q["kind"] != "entry":
            continue
        g, row = matched
        try:
            quote = _quote(dict(q), row, g["start"])
            if not quote["fresh"]:
                continue
            observed, fetched = _utc(quote["observed_at"]), _utc(quote["fetched_at"])
            fair = _native_selection_prices(quote, {**row, "identity": row["quote_identity"]},
                g["teams"], row["selection"], observed, fetched)
            api_event = str(quote["provider_event_id"])
            if fair is None or not api_event.isdecimal() or int(api_event) < 1:
                continue
            side = g["favorite"]["selection"]
            selected_odds = next(x["odds"] for x in quote["native_market_partition"]["outcomes"] if x["selection"] == side)
            opens[g["event_id"]][fetched].add((quote["bookmaker_id"], observed, api_event, selected_odds, fair[side]))
        except (ValueError, KeyError, TypeError, OverflowError):
            counts["rejected_quote_rows"] += 1
    counts["raw_closing_games"] = len(closing_events)
    for g in games:
        batches = opens[g["event_id"]]
        if not batches:
            counts["missing_first_pair"] += 1
            continue
        quotes = batches[min(batches)]
        if len({q[0] for q in quotes}) != len(quotes) or len({q[2] for q in quotes}) != 1:
            counts["ambiguous_first_pair"] += 1
            continue
        if median(q[3] for q in quotes) < 1.20:
            counts["below_price_floor"] += 1
            continue
        counts["paired_entries"] += 1
        yield {**g, "p_market": median(q[4] for q in quotes)}


def _settled(conn, game, cutoff):
    scores = set()
    original_receipt = False
    for row in game["rows"]:
        for result in conn.execute("""SELECT * FROM forecast_results WHERE event_key=? AND market_key='H2H'
                 AND selection=? AND observed_at<=?""", (row["event_key"], row["selection"], cutoff.isoformat())):
            try:
                terminal = _result(dict(result), row, cutoff)
            except (ValueError, TypeError, KeyError, OverflowError):
                return None
            proof = terminal["provenance"]
            if (terminal["outcome"] == "VOID" or _utc(terminal["observed_at"]) <= game["start"]
                    or proof["settlement_rule"] != SETTLEMENT_RULE
                    or proof["source_record_id"] != f"nhl:event:{game['event_id']}:final"):
                return None
            is_favorite = row["forecast_id"] == game["favorite"]["forecast_id"]
            original_receipt |= is_favorite
            scores.add(int((terminal["outcome"] == "WIN") == is_favorite))
    return next(iter(scores)) if original_receipt and len(scores) == 1 else None


def build_nhl_review(path, *, first, last, cutoff, open_outcomes=False, now=None):
    path, cutoff = Path(path), _utc(cutoff)
    if last < first or last-first > timedelta(days=140) or last >= cutoff.astimezone(ZURICH).date():
        raise ValueError("NHL review requires a completed, bounded Zürich window")
    if open_outcomes and (first != FORWARD_FIRST or last != FORWARD_LAST or cutoff != OPEN_AT
                          or _utc(now or datetime.now(timezone.utc)) < OPEN_AT):
        raise ValueError("outcomes open only for the registered future test window, at the fixed cutoff")
    lower, upper = (datetime.combine(d, time.min, ZURICH).astimezone(timezone.utc).isoformat()
                    for d in (first, last+timedelta(days=1)))
    args = (MODEL, POLICY, lower, upper)
    counts = Counter(dict(first_nhl_forecasts=0, favorite_60=0, favorite_70=0, paired_entries=0, missing_first_pair=0))
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=3)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        games = list(_first_favorites(conn, args, cutoff, counts))
        paired = list(_quotes(conn, args, cutoff, games, counts))
        coverage = nhl_top_coverage(paired)
        evaluated = evaluate_nhl_top(paired, lambda g: _settled(conn, g, cutoff)) if open_outcomes else None
    return dict(from_day=first.isoformat(), through_day=last.isoformat(), cutoff=cutoff.isoformat(),
                model=MODEL, policy=POLICY, counts=dict(counts), coverage=coverage, evaluation=evaluated,
                market_probability_mean=(math.fsum(g["p_market"] for g in paired)/len(paired) if paired else None))


def main(argv=None, *, now=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--phase", choices=("pilot", "forward-coverage", "open"), default="pilot")
    args = parser.parse_args(argv)
    current = _utc(now or datetime.now(timezone.utc))
    if args.phase == "pilot":
        first, last, cutoff = PILOT_FIRST, PILOT_LAST, PILOT_CUTOFF
    elif args.phase == "forward-coverage":
        first, cutoff = FORWARD_FIRST, current
        last = min(FORWARD_LAST, cutoff.astimezone(ZURICH).date()-timedelta(days=1))
    else:
        first, last, cutoff = FORWARD_FIRST, FORWARD_LAST, OPEN_AT
    try:
        report = build_nhl_review(args.db, first=first, last=last, cutoff=cutoff, open_outcomes=args.phase == "open", now=current)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
