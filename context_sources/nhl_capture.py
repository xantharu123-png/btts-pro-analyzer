"""Daily-owner-only native NHL intake; source coverage is NOT model qualification.

No import/render effects, discovery scan, name joins, prediction mutation or raw
body copies. Existing completed history owns shared cross-process reservations.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

import requests

from context_models.contracts import canonical_timestamp
from context_models.dataset import _reader
from context_models.football_original_storage import StorageBudgetExceeded
from context_observations import _SELECT, _decode_receipt
from context_sources.nhl import (
    MAX_SOURCE_BYTES, append_nhl_boxscore_batch, normalize_nhl_boxscore,
    validate_nhl_boxscore_receipt,
)
from scanners.completed_history import CompletedHistoryStore, utc_time

MAX_NEW_BYTES = 1024 * 1024
PROVIDER = "NHL-context"


def _now():
    return datetime.now(timezone.utc)


def empty_capture_report(status="not_due"):
    return {"status": status, "eligible_games": 0, "requested": 0, "reused": 0,
            "stored_receipts": 0, "stored_new_payload_bytes": 0,
            "deferred_request_budget": 0, "deferred_storage_budget": 0,
            "errors": [], "decision_at": None, "observed_at": []}


def _positive_id(value):
    if type(value) is int:
        return value if 0 < value <= 10**9 else None
    if type(value) is str and re.fullmatch(r"[1-9][0-9]{0,8}", value):
        return int(value)
    return None


def _candidate(row, decision, *, completed):
    if type(row) is not dict:
        return None
    if (not any(row.get(k) == "NHL" for k in ("source", "provider"))
            or any(row.get(k) not in (None, "NHL") for k in ("source", "provider", "league", "competition"))
            or not any(row.get(k) == "NHL" for k in ("league", "competition"))
            or row.get("sport") not in (None, "ice_hockey") or row.get("source_contract") is not None):
        return None
    values = [row[k] for k in ("game_id", "provider_event_id", "event_id") if k in row]
    if not values or any(type(v) not in (int, str) or isinstance(v, bool)
                         or re.fullmatch(r"20[0-9]{2}0[23][0-9]{4}", str(v)) is None for v in values):
        return None
    game = int(values[0])
    season, kind = row.get("season"), row.get("game_type")
    if (any(int(v) != game for v in values) or game % 10000 == 0
            or type(season) not in (int, str) or str(season) not in {"20252026", "20262027"}
            or int(season) != game // 1000000 * 10000 + game // 1000000 + 1
            or type(kind) is not int or kind not in (2, 3) or kind != game // 10000 % 100):
        return None
    home, away = (_positive_id(row.get(k)) for k in ("home_team_id", "away_team_id"))
    start = utc_time(row.get("start_time") or row.get("starts_at"))
    if home is None or away is None or home == away or start is None:
        return None
    # Every supplied receipt must be causal; completed rows need actual result
    # receipt proof. The default owner supplies a receipt on current events.
    receipts = [utc_time(row[k]) for k in ("source_observed_at", "fetched_at", "result_observed_at")
                if row.get(k) is not None]
    if not receipts or any(t is None or t > decision for t in receipts):
        return None
    if completed:
        observed = utc_time(row.get("result_observed_at"))
        if (row.get("status") != "completed" or observed is None or not start < observed <= decision
                or not decision - timedelta(days=14) <= start < decision):
            return None
    elif row.get("status") not in ("upcoming", "scheduled") or start <= decision:
        return None
    score = {}
    for side in ("home", "away"):
        value = row.get(side + "_score")
        if value is not None:
            if type(value) is not int or not 0 <= value <= 100:
                return None
            score[side] = value
    phase = row.get("last_period_type")
    if phase not in (None, "", "REG", "OT", "SO"):
        return None
    if completed and (len(score) != 2 or score["home"] == score["away"]):
        return None
    return {"game": game, "teams": (home, away), "start": canonical_timestamp(start),
            "completed": completed, "score": score, "phase": phase or None}


def _unique_candidates(rows, decision, *, completed):
    selected, conflicts = {}, set()
    for row in rows or ():
        item = _candidate(row, decision, completed=completed)
        if item is None:
            continue
        key = item["game"]
        if key in selected and selected[key] != item:
            conflicts.add(key)
        selected[key] = item
    return {key: value for key, value in selected.items() if key not in conflicts}


def _candidates(events, completed_rows, decision):
    current = _unique_candidates(events, decision, completed=False)
    if not current:
        return []
    history = _unique_candidates(completed_rows, decision, completed=True)
    teams = {team for item in current.values() for team in item["teams"]}
    chosen = {}
    for team in teams:
        recent = sorted((item for item in history.values() if team in item["teams"]
                         and item["game"] not in current),
                        key=lambda item: (item["start"], item["game"]), reverse=True)[:2]
        chosen.update((item["game"], item) for item in recent)
    return list(current.values()) + list(chosen.values())


def _cached(path, candidates):
    if not Path(path).exists():
        return {}
    result = {}
    with _reader(Path(path)) as connection:
        tables = {r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('context_observations','context_contents')")}
        if len(tables) != 2:
            return {}
        # One indexed event slice at a time, only latest receipt/revision(s).
        # A same-clock conflict cannot be resolved by row insertion order.
        for item in candidates:
            key = f"nhl:ice_hockey:{item['game']}"
            stored = connection.execute(_SELECT +
                " WHERE r.event_key=? AND r.source='nhl' AND r.kind='native_boxscore'"
                " ORDER BY r.observed_at DESC, r.digest LIMIT 2", (key,)).fetchall()
            if not stored or len(stored) == 2 and stored[0][3] == stored[1][3]:
                continue
            row = _decode_receipt(stored[0])
            validate_nhl_boxscore_receipt(row)
            result[item["game"]] = row
    return result


def _matches(item, row):
    payload, event = row["payload"], row["payload"]["event"]
    if (event["home_id"] != f"nhl:ice_hockey:team:{item['teams'][0]}"
            or event["away_id"] != f"nhl:ice_hockey:team:{item['teams'][1]}"
            or event["scheduled_start"] != item["start"]
            or event["status"] != ("completed" if item["completed"] else "scheduled")):
        return False
    data = payload["data"]
    return (all(data["final_score"][side] == score for side, score in item["score"].items())
            and (item["phase"] is None or data["terminal_phase"] == item["phase"]))


class _FetchError(ValueError):
    pass


def _fetch(item, clock):
    url = f"https://api-web.nhle.com/v1/gamecenter/{item['game']}/boxscore"
    response = requests.get(url, timeout=10, allow_redirects=False, stream=True)
    try:
        if response.url != url or response.history:
            raise _FetchError("http_url")
        if response.status_code != 200:
            raise _FetchError("http_status")
        chunks, length = [], 0
        for chunk in response.iter_content(chunk_size=16384):
            length += len(chunk)
            if length > MAX_SOURCE_BYTES:
                raise _FetchError("body_limit")
            chunks.append(chunk)
        observed = utc_time(clock())
        if observed is None:
            raise _FetchError("invalid_clock")
        raw = json.loads(b"".join(chunks))
        row = normalize_nhl_boxscore(raw, requested_game_id=item["game"], observed_at=observed,
                                     expected_teams=item["teams"])
        # A real native revision can correct the older owner schedule/result.
        # Retain it as a separate actual source receipt, never rewrite the owner.
        return raw, item["game"], observed, _matches(item, row)
    finally:
        response.close()


def collect_nhl_context(*, path, events, completed_rows, history_store=None,
                        clock=None, max_new_payload_bytes=MAX_NEW_BYTES):
    """Collect bounded native facts; never return replacement history rows."""
    clock = clock or _now
    decision = utc_time(clock())
    if decision is None:
        raise ValueError("NHL capture requires an aware decision clock")
    if type(max_new_payload_bytes) is not int or not 0 <= max_new_payload_bytes <= MAX_NEW_BYTES:
        raise ValueError("NHL capture storage limit exceeds its bound")
    report = empty_capture_report("no_eligible_games")
    report["decision_at"] = decision.isoformat()
    candidates = _candidates(events, completed_rows, decision)
    report["eligible_games"] = len(candidates)
    if not candidates:
        return report
    try:
        cached = _cached(path, candidates)
    except Exception:
        cached = {}
        report["errors"].append("cache_unavailable")
    # Previously unseen source games precede routine refreshes.
    candidates.sort(key=lambda item: item["game"] in cached)
    store = history_store if history_store is not None else CompletedHistoryStore(
        Path(path).parent / "sports_completed_history.db", clock=lambda: utc_time(clock()))
    pending = []
    for item in candidates:
        previous = cached.get(item["game"])
        if previous is not None and _matches(item, previous):
            age = decision - utc_time(previous["observed_at"])
            if timedelta(0) <= age < timedelta(hours=24):
                report["reused"] += 1
                continue
        # B1 validation owns the 24h content cache; the existing reservation
        # owns only shared UTC-day budget and the unchanged 30min cooldown.
        key = str(item["game"])
        if not store.reserve(PROVIDER, key, ttl=timedelta(0), daily_limit=32):
            report["deferred_request_budget"] += 1
            continue
        report["requested"] += 1
        try:
            response = _fetch(item, clock)
            if response[2] < decision:
                raise _FetchError("invalid_clock")
            pending.append(response[:3])
            if not response[3] and "owner_revision_mismatch" not in report["errors"]:
                report["errors"].append("owner_revision_mismatch")
            stamp = response[2].isoformat()
            if stamp not in report["observed_at"]:
                report["observed_at"].append(stamp)
        except Exception as exc:
            code = str(exc) if isinstance(exc, _FetchError) else (
                "http_failed" if isinstance(exc, requests.RequestException) else "invalid_body")
            if code not in report["errors"]:
                report["errors"].append(code)
            store.record(PROVIDER, key, (), error=code)
    if pending:
        error = None
        try:
            refs, size = append_nhl_boxscore_batch(path, tuple(pending), max_new_payload_bytes=max_new_payload_bytes)
            report["stored_receipts"], report["stored_new_payload_bytes"] = len(refs), size
        except StorageBudgetExceeded:
            report["deferred_storage_budget"] = len(pending)
            error = "storage_budget"
        except Exception:
            error = "storage_failed"
        if error is not None:
            report["errors"].append(error)
        for _, game, _ in pending:
            store.record(PROVIDER, str(game), (), error=error)
    report["status"] = ("partial" if report["errors"] or report["deferred_request_budget"]
                        else "captured" if report["stored_receipts"] else "reused")
    return report


def daily_nhl_collector(*, path, report, clock=None):
    """Production closure: explicit context DB, lazy request store, admin only."""
    def collect(*, events, completed_rows):
        report.clear()
        try:
            report.update(collect_nhl_context(path=path, events=events,
                                             completed_rows=completed_rows, clock=clock))
        except Exception:
            report.update(empty_capture_report("failed"))
            report["errors"] = ["capture_failed"]
    return collect
