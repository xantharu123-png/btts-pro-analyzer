"""Bounded native-result collection for the dedicated forecast evidence database.

No account, ticket, stake or bankroll state is read or written. Started events
are only a polling queue: real provider status, exact identity and an actual
result observation remain necessary. Missing data never become losses/voids.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Mapping

from challenge_15k import count_stats_from_response
from challenge_engine import COUNT_MARKET_KINDS, MARKET_BY_KEY, _fixture_market_outcome
from challenge_store import SETTLEMENT_RULE_VERSION as FOOTBALL_RULE_VERSION
import forecast_evidence as evidence
from riskobet_domain import stable_event_key
from riskobet_settlement import EsportsMarket, Selection, SettlementStatus, Sport, TennisMarket, settle_market
from riskobet_settlement_automation import (
    DEFAULT_ESPORTS_DB_PATH, DEFAULT_TENNIS_DB_PATH, SettlementRequest,
    _first_observation, _parse_time, _positive_int, esports_result_loader, tennis_result_loader,
    count_settlement_operational_errors,
)


MAX_EVENTS_PER_SPORT = 40
MAX_SOURCE_REVISIONS_PER_EVENT = 500
ROTATION_SECONDS = 30 * 60


def _native_identity(row: Mapping) -> tuple | None:
    quoted = row["quote_identity"]
    sport = row["sport"]
    provider = str(quoted.get("fixture_source") or ("api-football" if sport == "football" else "")).casefold()
    provider_id = quoted.get("provider_event_id")
    if sport == "football":
        provider_id = provider_id or quoted.get("fixture_id")
    if provider_id is None or isinstance(provider_id, bool):
        return None
    provider_id = str(provider_id).strip()
    allowed = {"football": {"api-football"}, "tennis": {"espn", "sofascore"}, "esports": {"pandascore"}}
    if provider not in allowed.get(sport, set()) or not provider_id:
        return None
    if sport == "football":
        a, b = _positive_int(quoted.get("home_id")), _positive_int(quoted.get("away_id"))
        if _positive_int(provider_id) is None or a is None or b is None or a == b:
            return None
        competitors = (a, b)
    else:
        a, b = quoted.get("competitor_a"), quoted.get("competitor_b")
        if not isinstance(a, str) or not isinstance(b, str) or not a.strip() or not b.strip() or a == b:
            return None
        competitors = (a, b)
        if sport == "esports":
            ids = (_positive_int(quoted.get("competitor_a_id")), _positive_int(quoted.get("competitor_b_id")))
            if _positive_int(provider_id) is None or None in ids or ids[0] == ids[1]:
                return None
            competitors += ids
    return (sport, provider, provider_id, evidence._utc(row["starts_at"]), *competitors)


def _supported_selection(row: Mapping) -> bool:
    if row["sport"] == "football":
        spec = MARKET_BY_KEY.get(row["market_key"])
        return spec is not None and row["selection"] == spec.selection
    quoted = row["quote_identity"]
    selected = quoted.get("selected_competitor")
    return (row["market_key"] == "H2H" and selected in {
        quoted.get("competitor_a"), quoted.get("competitor_b")}
        and selected is not None and row["selection"] == selected)


def _unambiguous_count_stats(payload, home_id: int, away_id: int) -> dict:
    """A duplicated named count is ambiguous, even if its last value parses."""
    if not isinstance(payload, list):
        return {}
    for team in payload:
        if not isinstance(team, Mapping) or not isinstance(team.get("statistics"), list):
            return {}
        names = [item.get("type") for item in team["statistics"]
                 if isinstance(item, Mapping) and item.get("type") in {"Corner Kicks", "Yellow Cards"}]
        if len(names) != len(set(names)):
            raise ValueError("duplicate provider count statistic")
    return count_stats_from_response(payload, home_id, away_id)


def _source_rows(path: Path, identity: tuple) -> list[dict]:
    """Read only matching native rows; bound revision floods without truncation bias."""
    if not path.is_file():
        return []
    sport, provider, provider_id, start, a, b, *ids = identity
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        if sport == "tennis":
            table = "predictions"
            required = {"id", "settled", "provider_event_id", "fixture_source", "player_a", "player_b", "scheduled_start_utc"}
            columns = {r[1] for r in connection.execute(f"PRAGMA table_info({table})")}
            if not required.issubset(columns):
                return []
            rows = connection.execute(
                "SELECT * FROM predictions WHERE settled=1 AND provider_event_id=? "
                "AND lower(fixture_source)=? AND player_a=? AND player_b=? ORDER BY id LIMIT ?",
                (provider_id, provider, a, b, MAX_SOURCE_REVISIONS_PER_EVENT + 1)).fetchall()
            clock = "scheduled_start_utc"
        else:
            table = "esports_shadow_predictions"
            required = {"match_id", "settled", "team1", "team2", "team1_id", "team2_id", "scheduled_at"}
            columns = {r[1] for r in connection.execute(f"PRAGMA table_info({table})")}
            if not required.issubset(columns):
                return []
            rows = connection.execute(
                "SELECT * FROM esports_shadow_predictions WHERE settled=1 AND match_id=? "
                "AND team1=? AND team2=? AND team1_id=? AND team2_id=? LIMIT ?",
                (int(provider_id), a, b, *ids, MAX_SOURCE_REVISIONS_PER_EVENT + 1)).fetchall()
            clock = "scheduled_at"
    if len(rows) > MAX_SOURCE_REVISIONS_PER_EVENT:
        return []
    return [dict(row) for row in rows if _parse_time(row[clock]) == start]


def _native_result(identity: tuple, rows: list[dict], path: Path, now: datetime):
    """Reuse native parsers, keeping their observed clocks and frozen identity checks."""
    sport, provider, provider_id, start, a, b, *ids = identity
    source_rows = _source_rows(path, identity)
    if not source_rows:
        return None
    # Repeated tennis forecasts may carry one result. Conflicting terminal facts
    # are not resolved by picking a convenient revision or winner.
    fact_fields = ("actual_winner", "ret_flag", "termination", "walkover", "home_sets", "away_sets",
                   "sets_a", "sets_b", "player_a_sets", "player_b_sets", "set_score", "result_score")
    if sport == "tennis" and len({evidence._hash({k: row.get(k) for k in fact_fields}) for row in source_rows}) != 1:
        raise ValueError("conflicting native terminal observations")
    valid = [row for row in source_rows if (observed := _first_observation(row, set(row))) is not None
             and start <= observed <= now]
    if not valid:
        return None
    selected = min(valid, key=lambda row: (_first_observation(row, set(row)), row.get("id", 0)))
    event_key = stable_event_key(sport, provider, provider_id)
    # The tennis native reader preserves the provider's source spelling when
    # building its event key. stable_event_key canonicalizes it itself.
    if sport == "tennis":
        event_key = stable_event_key(sport, str(selected["fixture_source"]), provider_id)
        factors = ({"factor_key": f"tennis_prediction_id:{selected['id']}"},)
        loader = tennis_result_loader(path)
    else:
        factors = tuple({"factor_key": key} for key in (
            f"esports_match_id:{provider_id}", f"esports_team1_id:{ids[0]}", f"esports_team2_id:{ids[1]}"))
        loader = esports_result_loader(path)
    request = SettlementRequest(sport, event_key, start, rows[0]["forecast_id"], f"{a} vs {b}",
                                factors, tuple(row["candidate_id"] for row in rows))
    batch = loader((request,), now)
    if len(batch.results) != 1:
        return None
    observation = batch.results[0]
    if (observation.sport != sport or observation.event_key != event_key
            or observation.observed_at != _first_observation(selected, set(selected))
            or not start <= observation.observed_at <= now):
        return None
    # A native DB is mutable. Do not bind a result parsed during a concurrent
    # source update to bytes observed before that update.
    if evidence._hash(source_rows) != evidence._hash(_source_rows(path, identity)):
        return None
    return observation, evidence._hash(selected)


def run_forecast_evidence_settlements(
    *, db_path: str | Path, now: datetime | None = None, football_provider=None,
    tennis_db_path: str | Path = DEFAULT_TENNIS_DB_PATH,
    esports_db_path: str | Path = DEFAULT_ESPORTS_DB_PATH,
    max_events_per_sport: int = MAX_EVENTS_PER_SPORT,
) -> dict:
    """Collect real outcomes, rotating finite event budgets once per half hour.

    ``now`` is an injectable observation clock for deterministic replay/tests;
    live callers should omit it so a provider response gets its actual read time.
    Football costs at most one bounded details batch and one statistics request
    per chosen event, independent of the number of forecast markets/revisions.
    Native shadow databases are opened read-only; only this evidence DB appends.
    """
    if isinstance(max_events_per_sport, bool) or not isinstance(max_events_per_sport, int) or not 1 <= max_events_per_sport <= MAX_EVENTS_PER_SPORT:
        raise ValueError("event budget must be an integer from 1 to 40")
    current = evidence._utc(now or datetime.now(timezone.utc))
    pending = evidence.unresolved_forecasts(db_path, as_of=current)
    summary = {"due_forecasts": len(pending), "checked_events": 0, "terminal_results": 0,
               "unresolved_forecasts": len(pending), "errors": []}
    errors = summary["errors"]
    grouped = defaultdict(list)
    for row in pending:
        if not row.get("causal_provenance_complete"):
            continue
        if not _supported_selection(row):
            code = "selection_identity_invalid" if row["sport"] == "football" and row["market_key"] in MARKET_BY_KEY else "unsupported_selection"
            errors.append(f"{row['sport']}:{code}")
            continue
        identity = _native_identity(row)
        if identity is None:
            errors.append(f"{row['sport']}:native_identity_unproven")
            continue
        grouped[(row["sport"], row["event_key"])].append((identity, row))
    events = defaultdict(dict)
    for (sport, event_key), group in sorted(grouped.items()):
        identities = {identity for identity, _ in group}
        if len(identities) != 1:
            errors.append(f"{sport}:event_identity_ambiguous")
            continue
        identity = next(iter(identities))
        events[sport].setdefault(identity, []).extend(row for _, row in group)
    selected = {}
    for sport, native_events in events.items():
        items = list(native_events.items())
        items.sort(key=lambda item: (item[0][3], item[1][0]["event_key"]))
        if len(items) > max_events_per_sport:
            offset = (int(current.timestamp()) // ROTATION_SECONDS * max_events_per_sport) % len(items)
            items = [items[(offset + i) % len(items)] for i in range(max_events_per_sport)]
            errors.append(f"{sport}:event_budget_reached")
        selected[sport] = items

    def append(row, outcome, observed, provider, provider_id, source_id, digest, rule):
        try:
            evidence.append_result(row["event_key"], row["market_key"], row["selection"], outcome,
                observed_at=observed, db_path=db_path, provenance={"provider": provider,
                    "provider_event_id": provider_id, "source_record_id": source_id,
                    "payload_sha256": digest, "settlement_rule": rule})
        except (ValueError, TypeError, sqlite3.Error):
            errors.append(f"{row['sport']}:result_append_rejected")
            return
        summary["terminal_results"] += 1
        summary["unresolved_forecasts"] -= 1

    football = selected.get("football", [])
    if football and football_provider is None:
        errors.append("football:result_source_unconfigured")
    elif football:
        ids = sorted({int(identity[2]) for identity, _ in football})
        try:
            details = football_provider.details_by_fixture(ids)
        except Exception:
            details = {}
            errors.append("football:result_source_failed")
        if details is not None and not isinstance(details, Mapping):
            errors.append("football:result_payload_invalid")
        details_observed = current if now is not None else evidence._now()
        stats_cache = {}
        summary["checked_events"] += len(ids)
        for identity, rows in football:
            _, provider, provider_id, start, home_id, away_id = identity
            item = details.get(int(provider_id)) if isinstance(details, Mapping) else None
            if not isinstance(item, dict):
                if item is not None:
                    errors.append("football:result_payload_invalid")
                continue
            fixture, teams = item.get("fixture"), item.get("teams")
            home = teams.get("home") if isinstance(teams, Mapping) else None
            away = teams.get("away") if isinstance(teams, Mapping) else None
            if (not isinstance(fixture, Mapping) or _positive_int(fixture.get("id")) != int(provider_id)
                    or _parse_time(fixture.get("date")) != start or not isinstance(teams, Mapping)
                    or not isinstance(home, Mapping) or not isinstance(away, Mapping)
                    or _positive_int(home.get("id")) != home_id
                    or _positive_int(away.get("id")) != away_id):
                errors.append("football:result_identity_mismatch")
                continue
            status = fixture.get("status")
            if not isinstance(status, Mapping) or not isinstance(status.get("short"), str) or not status["short"]:
                errors.append("football:result_payload_invalid")
                continue
            if status.get("short") != "FT":
                continue
            statistics = None
            observed = details_observed
            canonical = {**item, "challenge_stats": {}}
            if any(MARKET_BY_KEY[row["market_key"]].kind in COUNT_MARKET_KINDS for row in rows):
                if provider_id not in stats_cache:
                    try:
                        statistics = football_provider.statistics_by_fixture(int(provider_id))
                    except Exception:
                        errors.append("football:statistics_source_failed")
                    stats_cache[provider_id] = (statistics, current if now is not None else evidence._now())
                statistics, observed = stats_cache[provider_id]
                try:
                    canonical["challenge_stats"] = _unambiguous_count_stats(statistics, home_id, away_id)
                except ValueError:
                    errors.append("football:statistics_payload_invalid")
            try:
                digest = evidence._hash({"fixture": item, "statistics": statistics})
            except (ValueError, TypeError):
                errors.append("football:result_payload_invalid")
                continue
            for row in rows:
                spec = MARKET_BY_KEY[row["market_key"]]
                outcome = _fixture_market_outcome(spec, canonical)
                if outcome is None and spec.kind not in COUNT_MARKET_KINDS:
                    errors.append("football:regulation_score_invalid")
                if outcome is not None:
                    append(row, outcome, observed, provider, provider_id,
                           f"api-football:fixture:{provider_id}:FT", digest,
                           f"football-market-specs-v{FOOTBALL_RULE_VERSION}")

    for sport, path in (("tennis", Path(tennis_db_path)), ("esports", Path(esports_db_path))):
        for identity, rows in selected.get(sport, []):
            summary["checked_events"] += 1
            try:
                loaded = _native_result(identity, rows, path, current)
            except (sqlite3.Error, ValueError, TypeError):
                loaded = None
                errors.append(f"{sport}:native_result_unavailable")
                errors.append(f"{sport}:native_result_read_failed")
            if loaded is None:
                continue
            observation, digest = loaded
            _, provider, provider_id, _, competitor_a, *_ = identity
            for row in rows:
                selection = Selection.HOME if row["quote_identity"]["selected_competitor"] == competitor_a else Selection.AWAY
                try:
                    result = settle_market(sport=Sport(sport),
                        market=TennisMarket.MATCH_WINNER if sport == "tennis" else EsportsMarket.SERIES_WINNER,
                        selection=selection, result=observation.result)
                except (ValueError, TypeError):
                    errors.append(f"{sport}:canonical_result_invalid")
                    continue
                if result.status in {SettlementStatus.WIN, SettlementStatus.LOSS, SettlementStatus.VOID}:
                    append(row, result.status.value, observation.observed_at, provider, provider_id,
                           observation.source_result_id, digest, result.rule_version)
    summary["errors"] = list(dict.fromkeys(errors))
    summary["operational_error_count"] = count_settlement_operational_errors(summary["errors"])
    return summary
