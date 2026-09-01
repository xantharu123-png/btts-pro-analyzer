"""Bounded, price-neutral settlement runner for persisted RisikoBet candidates.

The runner only reads the explicitly published run, never guesses a result
from elapsed time, and never writes an ``UNRESOLVED`` polling row.  Provider
adapters return canonical results tied to the exact frozen event identity and
to the instant at which the result was actually observed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Callable, Iterable, Mapping, Optional, Sequence

from challenge_15k import ChallengeDataProvider
from config_loader import AppConfig, load_app_config
from esports_shadow import DEFAULT_DB_PATH as DEFAULT_ESPORTS_DB_PATH
from riskobet_domain import canonical_json, stable_event_key
from riskobet_settlement import (
    CanonicalResult,
    EsportsResult,
    EsportsTermination,
    EventStatus,
    FootballResult,
    ParsedSettlementContract,
    Selection,
    SettlementInputError,
    SettlementStatus,
    Sport,
    TennisResult,
    TennisTermination,
    parse_settlement_contract,
    settle_market,
)
from riskobet_store import (
    DEFAULT_DB_PATH,
    DEFAULT_LATEST_PATH,
    FrozenRevisionError,
    RiskBetStore,
)
from tennis.shadow import DB_PATH as DEFAULT_TENNIS_DB_PATH


MAX_EVENTS_PER_SPORT = 40
MAX_SHADOW_ROWS_PER_SOURCE = 500
SETTLEMENT_ROTATION_SECONDS = 30 * 60
TERMINAL_STORE_RESULTS = frozenset({"WON", "LOST", "VOID"})
SETTLEABLE_STAGES = frozenset({"SHADOW", "VALIDATED"})
SUPPORTED_DEFAULT_SPORTS = frozenset({"football", "tennis", "esports"})
_FIXTURE_FACTOR_RE = re.compile(r"^football_fixture_id:([1-9][0-9]*)$")
_TENNIS_PREDICTION_FACTOR_RE = re.compile(
    r"^tennis_prediction_id:([1-9][0-9]*)$"
)
_ESPORTS_MATCH_FACTOR_RE = re.compile(r"^esports_match_id:([1-9][0-9]*)$")
_ESPORTS_TEAM1_FACTOR_RE = re.compile(r"^esports_team1_id:([1-9][0-9]*)$")
_ESPORTS_TEAM2_FACTOR_RE = re.compile(r"^esports_team2_id:([1-9][0-9]*)$")
_SET_SCORE_RE = re.compile(r"^\s*([0-9]+)\s*[:\-]\s*([0-9]+)\s*$")


@dataclass(frozen=True, slots=True)
class SettlementRequest:
    """One deduplicated sport/event request passed to a result adapter."""

    sport: str
    event_key: str
    starts_at: datetime
    snapshot_id: str
    event_label: str
    factors: tuple[Mapping[str, object], ...]
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservedResult:
    """Canonical result bound to exact identity and observation time."""

    sport: str
    event_key: str
    observed_at: datetime
    result: CanonicalResult
    source_result_id: str


@dataclass(frozen=True, slots=True)
class ResultIssue:
    event_key: str
    code: str


@dataclass(frozen=True, slots=True)
class ResultLoadBatch:
    results: tuple[ObservedResult, ...] = ()
    issues: tuple[ResultIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class SettlementAutomationSummary:
    run_id: str | None
    due_candidates: int
    due_events: int
    checked_sports: tuple[str, ...]
    terminal_settlements: int
    unresolved_candidates: int
    published: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "due_candidates": self.due_candidates,
            "due_events": self.due_events,
            "checked_sports": list(self.checked_sports),
            "terminal_settlements": self.terminal_settlements,
            "unresolved_candidates": self.unresolved_candidates,
            "published": self.published,
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }


ResultLoader = Callable[
    [tuple[SettlementRequest, ...], datetime],
    ResultLoadBatch | Iterable[ObservedResult],
]


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value, "timestamp")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(float(value), timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        return parsed if parsed.timestamp() == float(value) else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _score(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_sport(value: object) -> str:
    text = str(value or "automation")
    return text if text in {sport.value for sport in Sport} else "automation"


def _safe_issue(sport: str, code: str) -> str:
    clean = re.sub(r"[^a-z0-9_]+", "_", str(code).casefold()).strip("_")
    return f"{_safe_sport(sport)}:{clean or 'result_unavailable'}"


def _canonical_result_payload(result: CanonicalResult) -> dict[str, object]:
    payload = asdict(result)
    for key, value in tuple(payload.items()):
        if isinstance(value, Enum):
            payload[key] = value.value
    return {"type": type(result).__name__, **payload}


def _snapshot_by_id(run: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for raw in run.get("snapshots", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        snapshot_id = raw.get("snapshot_id")
        if isinstance(snapshot_id, str) and snapshot_id:
            result[snapshot_id] = raw
    return result


@dataclass(frozen=True, slots=True)
class _DueCandidate:
    payload: Mapping[str, object]
    contract: ParsedSettlementContract
    starts_at: datetime
    snapshot: Mapping[str, object]


def _terminal_already_present(candidate: Mapping[str, object]) -> bool:
    settlements = candidate.get("settlements") or ()
    return any(
        isinstance(item, Mapping) and item.get("result") in TERMINAL_STORE_RESULTS
        for item in settlements
    )


def _due_candidates(
    run: Mapping[str, object],
    *,
    now: datetime,
) -> tuple[list[_DueCandidate], list[str]]:
    snapshots = _snapshot_by_id(run)
    due: list[_DueCandidate] = []
    errors: list[str] = []
    for candidate in run.get("candidates", ()) or ():
        if not isinstance(candidate, Mapping):
            errors.append("automation:candidate_payload_invalid")
            continue
        sport = _safe_sport(candidate.get("sport"))
        if candidate.get("stage") not in SETTLEABLE_STAGES:
            continue
        starts_at = _parse_time(candidate.get("starts_at"))
        if starts_at is None:
            errors.append(_safe_issue(sport, "candidate_start_invalid"))
            continue
        if starts_at > now or _terminal_already_present(candidate):
            continue
        snapshot_id = candidate.get("snapshot_id")
        snapshot = snapshots.get(str(snapshot_id or ""))
        if snapshot is None:
            errors.append(_safe_issue(sport, "snapshot_missing"))
            continue
        if (
            snapshot.get("event_key") != candidate.get("event_key")
            or snapshot.get("sport") != candidate.get("sport")
            or _parse_time(snapshot.get("starts_at")) != starts_at
        ):
            errors.append(_safe_issue(sport, "snapshot_identity_mismatch"))
            continue
        try:
            contract = parse_settlement_contract(
                candidate.get("settlement_contract"),  # type: ignore[arg-type]
                candidate=candidate,
            )
        except (SettlementInputError, TypeError, ValueError):
            errors.append(_safe_issue(sport, "settlement_contract_invalid"))
            continue
        due.append(
            _DueCandidate(
                payload=candidate,
                contract=contract,
                starts_at=starts_at,
                snapshot=snapshot,
            )
        )
    return due, errors


def _requests_by_sport(
    due: Sequence[_DueCandidate],
    *,
    max_events_per_sport: int,
    now: datetime,
) -> tuple[
    dict[str, tuple[SettlementRequest, ...]],
    dict[tuple[str, str], tuple[_DueCandidate, ...]],
    list[str],
]:
    grouped: dict[tuple[str, str], list[_DueCandidate]] = {}
    errors: list[str] = []
    for item in due:
        key = (item.contract.sport.value, str(item.payload["event_key"]))
        grouped.setdefault(key, []).append(item)
    candidates_by_event: dict[tuple[str, str], tuple[_DueCandidate, ...]] = {}
    eligible_by_sport: dict[str, list[tuple[str, list[_DueCandidate]]]] = {}
    for (sport, event_key), items in sorted(
        grouped.items(), key=lambda entry: (entry[0][0], entry[1][0].starts_at, entry[0][1])
    ):
        if len(items) > 2:
            errors.append(_safe_issue(sport, "event_candidate_limit_exceeded"))
            continue
        snapshot_ids = {str(item.payload["snapshot_id"]) for item in items}
        if len(snapshot_ids) != 1:
            errors.append(_safe_issue(sport, "event_snapshot_ambiguous"))
            continue
        eligible_by_sport.setdefault(sport, []).append((event_key, items))

    requests: dict[str, list[SettlementRequest]] = {}
    rotation_slot = int(now.timestamp()) // SETTLEMENT_ROTATION_SECONDS
    for sport, eligible in sorted(eligible_by_sport.items()):
        if len(eligible) > max_events_per_sport:
            errors.append(_safe_issue(sport, "event_limit_reached"))
            start = (rotation_slot * max_events_per_sport) % len(eligible)
            eligible = [
                eligible[(start + offset) % len(eligible)]
                for offset in range(max_events_per_sport)
            ]
        for event_key, items in eligible:
            snapshot_ids = {str(item.payload["snapshot_id"]) for item in items}
            snapshot = items[0].snapshot
            factors = snapshot.get("factors") or ()
            if not isinstance(factors, (list, tuple)) or any(
                not isinstance(factor, Mapping) for factor in factors
            ):
                errors.append(_safe_issue(sport, "snapshot_factors_invalid"))
                continue
            event_label = snapshot.get("event_label")
            if not isinstance(event_label, str) or not event_label.strip():
                errors.append(_safe_issue(sport, "snapshot_event_label_invalid"))
                continue
            request = SettlementRequest(
                sport=sport,
                event_key=event_key,
                starts_at=items[0].starts_at,
                snapshot_id=next(iter(snapshot_ids)),
                event_label=event_label.strip(),
                factors=tuple(dict(factor) for factor in factors),
                candidate_ids=tuple(
                    sorted(str(item.payload["candidate_id"]) for item in items)
                ),
            )
            requests.setdefault(sport, []).append(request)
            candidates_by_event[(sport, event_key)] = tuple(items)
    return (
        {sport: tuple(values) for sport, values in requests.items()},
        candidates_by_event,
        errors,
    )


def _normalize_batch(
    raw: ResultLoadBatch | Iterable[ObservedResult],
) -> ResultLoadBatch:
    if isinstance(raw, ResultLoadBatch):
        return raw
    return ResultLoadBatch(results=tuple(raw))


def _football_fixture_id(request: SettlementRequest) -> int | None:
    matches: list[int] = []
    for factor in request.factors:
        key = factor.get("factor_key")
        if not isinstance(key, str):
            continue
        match = _FIXTURE_FACTOR_RE.fullmatch(key)
        if match:
            matches.append(int(match.group(1)))
    return matches[0] if len(matches) == 1 else None


def _single_factor_id(
    request: SettlementRequest,
    pattern: re.Pattern[str],
) -> int | None:
    matches: list[int] = []
    for factor in request.factors:
        key = factor.get("factor_key")
        if not isinstance(key, str):
            continue
        matched = pattern.fullmatch(key)
        if matched:
            matches.append(int(matched.group(1)))
    return matches[0] if len(matches) == 1 else None


def football_result_loader(
    provider: ChallengeDataProvider,
) -> ResultLoader:
    """Create one bounded API-Football result loader."""

    def load(
        requests: tuple[SettlementRequest, ...],
        observed_at: datetime,
    ) -> ResultLoadBatch:
        fixture_by_event: dict[str, int] = {}
        issues: list[ResultIssue] = []
        for request in requests:
            fixture_id = _football_fixture_id(request)
            if fixture_id is None or fixture_id in fixture_by_event.values():
                issues.append(ResultIssue(request.event_key, "fixture_identity_unproven"))
                continue
            fixture_by_event[request.event_key] = fixture_id
        if not fixture_by_event:
            return ResultLoadBatch(issues=tuple(issues))
        details = provider.details_by_fixture(sorted(fixture_by_event.values()))
        if not isinstance(details, Mapping):
            return ResultLoadBatch(
                issues=tuple(
                    [*issues]
                    + [
                        ResultIssue(event_key, "provider_result_unavailable")
                        for event_key in fixture_by_event
                    ]
                )
            )
        results: list[ObservedResult] = []
        for event_key, fixture_id in fixture_by_event.items():
            item = details.get(fixture_id)
            if not isinstance(item, Mapping):
                issues.append(ResultIssue(event_key, "provider_result_unavailable"))
                continue
            fixture = item.get("fixture")
            if not isinstance(fixture, Mapping) or fixture.get("id") != fixture_id:
                issues.append(ResultIssue(event_key, "provider_identity_mismatch"))
                continue
            status_payload = fixture.get("status")
            status = (
                str(status_payload.get("short") or "").upper()
                if isinstance(status_payload, Mapping)
                else ""
            )
            canonical_status = {
                "FT": EventStatus.FINAL,
                "CANC": EventStatus.CANCELLED,
                "ABD": EventStatus.ABANDONED,
                "PST": EventStatus.POSTPONED,
                "SUSP": EventStatus.SUSPENDED,
                "INT": EventStatus.SUSPENDED,
                "NS": EventStatus.SCHEDULED,
                "TBD": EventStatus.SCHEDULED,
            }.get(status)
            if status in {"AET", "PEN", "AWD", "WO"}:
                issues.append(ResultIssue(event_key, "regulation_score_unproven"))
                continue
            if canonical_status is None:
                canonical_status = EventStatus.LIVE
            home_goals = away_goals = None
            if canonical_status is EventStatus.FINAL:
                goals = item.get("goals")
                if isinstance(goals, Mapping):
                    home_goals = _score(goals.get("home"))
                    away_goals = _score(goals.get("away"))
                if home_goals is None or away_goals is None:
                    issues.append(ResultIssue(event_key, "regulation_score_missing"))
            results.append(
                ObservedResult(
                    sport="football",
                    event_key=event_key,
                    observed_at=observed_at,
                    result=FootballResult(
                        status=canonical_status,
                        home_goals_90=home_goals,
                        away_goals_90=away_goals,
                    ),
                    source_result_id=f"api-football:fixture:{fixture_id}:{status or 'unknown'}",
                )
            )
        return ResultLoadBatch(tuple(results), tuple(issues))

    return load


def _readonly_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _first_observation(row: Mapping[str, object], columns: set[str]) -> datetime | None:
    for key in ("result_observed_at", "result_recorded_at", "settled_at"):
        if key in columns:
            parsed = _parse_time(row.get(key))
            if parsed is not None:
                return parsed
    return None


def _explicit_set_score(
    row: Mapping[str, object], columns: set[str]
) -> tuple[int, int] | None:
    for home_key, away_key in (
        ("home_sets", "away_sets"),
        ("sets_a", "sets_b"),
        ("player_a_sets", "player_b_sets"),
    ):
        if home_key in columns and away_key in columns:
            home, away = _score(row.get(home_key)), _score(row.get(away_key))
            if home is not None and away is not None:
                return home, away
    for key in ("set_score", "result_score"):
        if key in columns and isinstance(row.get(key), str):
            matched = _SET_SCORE_RE.fullmatch(str(row[key]))
            if matched:
                return int(matched.group(1)), int(matched.group(2))
    return None


def tennis_result_loader(
    db_path: str | Path = DEFAULT_TENNIS_DB_PATH,
) -> ResultLoader:
    path = Path(db_path)

    def load(
        requests: tuple[SettlementRequest, ...],
        _observed_at: datetime,
    ) -> ResultLoadBatch:
        request_by_event = {request.event_key: request for request in requests}
        prediction_by_event: dict[str, int] = {}
        issues: list[ResultIssue] = []
        for request in requests:
            prediction_id = _single_factor_id(
                request, _TENNIS_PREDICTION_FACTOR_RE
            )
            if prediction_id is None:
                issues.append(ResultIssue(request.event_key, "source_identity_unproven"))
                continue
            prediction_by_event[request.event_key] = prediction_id
        if not prediction_by_event:
            return ResultLoadBatch(issues=tuple(issues))
        if not path.is_file():
            return ResultLoadBatch(
                issues=tuple(ResultIssue(req.event_key, "result_database_missing") for req in requests)
            )
        try:
            with _readonly_connection(path) as connection:
                columns = _columns(connection, "predictions")
                required = {
                    "id", "settled", "player_a", "player_b",
                    "provider_event_id", "fixture_source", "actual_winner", "ret_flag",
                }
                if not required.issubset(columns):
                    return ResultLoadBatch(
                        issues=tuple(ResultIssue(req.event_key, "result_schema_incomplete") for req in requests)
                    )
                if not {"result_observed_at", "result_recorded_at", "settled_at"} & columns:
                    return ResultLoadBatch(
                        issues=tuple(ResultIssue(req.event_key, "result_observed_at_missing") for req in requests)
                    )
                if "termination" not in columns:
                    return ResultLoadBatch(
                        issues=tuple(
                            ResultIssue(req.event_key, "termination_unproven")
                            for req in requests
                        )
                    )
                prediction_ids = sorted(set(prediction_by_event.values()))
                placeholders = ",".join("?" for _ in prediction_ids)
                rows = connection.execute(
                    f"SELECT * FROM predictions WHERE settled=1 "
                    f"AND id IN ({placeholders}) ORDER BY id DESC",
                    prediction_ids,
                ).fetchall()
        except sqlite3.Error:
            return ResultLoadBatch(
                issues=tuple(ResultIssue(req.event_key, "result_database_unavailable") for req in requests)
            )
        results: list[ObservedResult] = []
        matched: set[str] = set()
        for sqlite_row in rows:
            row = dict(sqlite_row)
            provider_id = str(row.get("provider_event_id") or f"shadow-{row['id']}").strip()
            provider = str(row.get("fixture_source") or "tennis-shadow").strip()
            event_key = stable_event_key("tennis", provider, provider_id)
            request = request_by_event.get(event_key)
            expected_prediction_id = prediction_by_event.get(event_key)
            if (
                request is None
                or expected_prediction_id is None
                or row.get("id") != expected_prediction_id
                or event_key in matched
            ):
                continue
            observed = _first_observation(row, columns)
            if observed is None:
                continue
            player_a = str(row.get("player_a") or "").strip()
            player_b = str(row.get("player_b") or "").strip()
            if (
                not player_a
                or not player_b
                or f"{player_a} vs {player_b}" != request.event_label
            ):
                continue
            actual = str(row.get("actual_winner") or "").strip()
            retirement = row.get("ret_flag") in (1, True)
            termination_value = str(row.get("termination") or "").strip().casefold()
            walkover_flag = row.get("walkover") in (1, True)
            if termination_value == "retirement" and retirement:
                termination = TennisTermination.RETIREMENT
                winner = None
            elif termination_value == "walkover" and not retirement:
                termination = TennisTermination.WALKOVER
                winner = None
            elif (
                termination_value == "normal"
                and not retirement
                and not walkover_flag
                and actual == player_a
            ):
                termination = TennisTermination.NORMAL
                winner = Selection.HOME
            elif (
                termination_value == "normal"
                and not retirement
                and not walkover_flag
                and actual == player_b
            ):
                termination = TennisTermination.NORMAL
                winner = Selection.AWAY
            else:
                continue
            scores = _explicit_set_score(row, columns)
            results.append(
                ObservedResult(
                    sport="tennis",
                    event_key=event_key,
                    observed_at=observed,
                    result=TennisResult(
                        status=EventStatus.FINAL,
                        home_sets=scores[0] if scores else None,
                        away_sets=scores[1] if scores else None,
                        winner=winner,
                        termination=termination,
                    ),
                    source_result_id=f"tennis-shadow:prediction:{row['id']}",
                )
            )
            matched.add(event_key)
        issues.extend(
            ResultIssue(request.event_key, "matching_settled_result_missing")
            for request in requests
            if request.event_key in prediction_by_event
            and request.event_key not in matched
        )
        return ResultLoadBatch(tuple(results), tuple(issues))

    return load


def _explicit_map_score(
    row: Mapping[str, object], columns: set[str]
) -> tuple[int, int] | None:
    for home_key, away_key in (
        ("home_maps", "away_maps"),
        ("final_score1", "final_score2"),
    ):
        if home_key in columns and away_key in columns:
            home, away = _score(row.get(home_key)), _score(row.get(away_key))
            if home is not None and away is not None:
                return home, away
    return None


def esports_result_loader(
    db_path: str | Path = DEFAULT_ESPORTS_DB_PATH,
) -> ResultLoader:
    path = Path(db_path)

    def load(
        requests: tuple[SettlementRequest, ...],
        _observed_at: datetime,
    ) -> ResultLoadBatch:
        request_by_event = {request.event_key: request for request in requests}
        identity_by_event: dict[str, tuple[int, int, int]] = {}
        issues: list[ResultIssue] = []
        for request in requests:
            match_id = _single_factor_id(request, _ESPORTS_MATCH_FACTOR_RE)
            team1_id = _single_factor_id(request, _ESPORTS_TEAM1_FACTOR_RE)
            team2_id = _single_factor_id(request, _ESPORTS_TEAM2_FACTOR_RE)
            if (
                match_id is None
                or team1_id is None
                or team2_id is None
                or team1_id == team2_id
            ):
                issues.append(ResultIssue(request.event_key, "source_identity_unproven"))
                continue
            identity_by_event[request.event_key] = (match_id, team1_id, team2_id)
        if not identity_by_event:
            return ResultLoadBatch(issues=tuple(issues))
        if not path.is_file():
            return ResultLoadBatch(
                issues=tuple(ResultIssue(req.event_key, "result_database_missing") for req in requests)
            )
        try:
            with _readonly_connection(path) as connection:
                columns = _columns(connection, "esports_shadow_predictions")
                required = {
                    "match_id", "settled", "winner_team_id", "settled_at",
                    "selected_team_id", "selection", "team1", "team2",
                }
                if not required.issubset(columns):
                    return ResultLoadBatch(
                        issues=tuple(ResultIssue(req.event_key, "result_schema_incomplete") for req in requests)
                    )
                identity_columns = {
                    "team1_id", "team2_id", "termination",
                    "final_score1", "final_score2",
                }
                if not identity_columns.issubset(columns):
                    code = (
                        "termination_unproven"
                        if "termination" not in columns
                        else "source_identity_unproven"
                    )
                    return ResultLoadBatch(
                        issues=tuple(ResultIssue(req.event_key, code) for req in requests)
                    )
                match_ids = sorted(
                    {identity[0] for identity in identity_by_event.values()}
                )
                placeholders = ",".join("?" for _ in match_ids)
                rows = connection.execute(
                    "SELECT * FROM esports_shadow_predictions "
                    f"WHERE settled=1 AND match_id IN ({placeholders}) "
                    "ORDER BY settled_at DESC, match_id DESC",
                    match_ids,
                ).fetchall()
        except sqlite3.Error:
            return ResultLoadBatch(
                issues=tuple(ResultIssue(req.event_key, "result_database_unavailable") for req in requests)
            )
        results: list[ObservedResult] = []
        matched: set[str] = set()
        for sqlite_row in rows:
            row = dict(sqlite_row)
            match_id = _positive_int(row.get("match_id"))
            if match_id is None:
                continue
            event_key = stable_event_key("esports", "pandascore", str(match_id))
            request = request_by_event.get(event_key)
            frozen_identity = identity_by_event.get(event_key)
            if request is None or frozen_identity is None or event_key in matched:
                continue
            expected_match_id, expected_team1_id, expected_team2_id = frozen_identity
            expected_ids = (expected_team1_id, expected_team2_id)
            if match_id != expected_match_id:
                continue
            observed = _parse_time(row.get("settled_at"))
            if observed is None:
                continue
            winner_id = _positive_int(row.get("winner_team_id"))
            selected_id = _positive_int(row.get("selected_team_id"))
            favorite = str(row.get("selection") or "").strip()
            team1 = str(row.get("team1") or "").strip()
            team2 = str(row.get("team2") or "").strip()
            team1_id = _positive_int(row.get("team1_id"))
            team2_id = _positive_int(row.get("team2_id"))
            if (
                (team1_id, team2_id) != expected_ids
                or not team1
                or not team2
                or f"{team1} vs {team2}" != request.event_label
                or selected_id not in expected_ids
                or (
                    favorite == team1 and selected_id != team1_id
                )
                or (
                    favorite == team2 and selected_id != team2_id
                )
                or favorite not in {team1, team2}
            ):
                continue
            termination_text = str(row.get("termination") or "").strip().casefold()
            scores = _explicit_map_score(row, columns)
            if termination_text == "cancelled" and winner_id is None:
                status = EventStatus.CANCELLED
                winner = None
                termination = EsportsTermination.NORMAL
                scores = None
            elif termination_text in {"normal", "forfeit"}:
                if winner_id not in expected_ids:
                    continue
                winner = Selection.HOME if winner_id == team1_id else Selection.AWAY
                status = EventStatus.FINAL
                termination = (
                    EsportsTermination.FORFEIT
                    if termination_text == "forfeit"
                    else EsportsTermination.NORMAL
                )
                if termination_text == "normal" and scores is None:
                    continue
                if termination_text == "forfeit":
                    scores = None
            else:
                continue
            results.append(
                ObservedResult(
                    sport="esports",
                    event_key=event_key,
                    observed_at=observed,
                    result=EsportsResult(
                        status=status,
                        home_maps=scores[0] if scores else None,
                        away_maps=scores[1] if scores else None,
                        winner=winner,
                        termination=termination,
                    ),
                    source_result_id=f"esports-shadow:match:{match_id}",
                )
            )
            matched.add(event_key)
        issues.extend(
            ResultIssue(request.event_key, "matching_settled_result_missing")
            for request in requests
            if request.event_key in identity_by_event
            and request.event_key not in matched
        )
        return ResultLoadBatch(tuple(results), tuple(issues))

    return load


def _default_loader(
    sport: str,
    *,
    config: AppConfig | None,
    football_provider: ChallengeDataProvider | None,
    tennis_db_path: str | Path,
    esports_db_path: str | Path,
) -> ResultLoader | None:
    if sport == "football":
        provider = football_provider
        if provider is None:
            resolved = config or load_app_config()
            if not resolved.api_football_key:
                return None
            provider = ChallengeDataProvider(
                resolved.api_football_key,
                resolved.weather_key,
            )
        return football_result_loader(provider)
    if sport == "tennis":
        return tennis_result_loader(tennis_db_path)
    if sport == "esports":
        return esports_result_loader(esports_db_path)
    return None


def run_riskobet_settlements(
    *,
    store: RiskBetStore | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    latest_path: str | Path = DEFAULT_LATEST_PATH,
    now: datetime | None = None,
    result_loaders: Mapping[str, ResultLoader] | None = None,
    config: AppConfig | None = None,
    football_provider: ChallengeDataProvider | None = None,
    tennis_db_path: str | Path = DEFAULT_TENNIS_DB_PATH,
    esports_db_path: str | Path = DEFAULT_ESPORTS_DB_PATH,
    max_events_per_sport: int = MAX_EVENTS_PER_SPORT,
) -> SettlementAutomationSummary:
    """Settle due candidates from the explicitly published prior run."""

    observed_now = _utc(now or datetime.now(timezone.utc), "now")
    if (
        isinstance(max_events_per_sport, bool)
        or not isinstance(max_events_per_sport, int)
        or max_events_per_sport < 1
        or max_events_per_sport > MAX_EVENTS_PER_SPORT
    ):
        raise ValueError(f"max_events_per_sport must be between 1 and {MAX_EVENTS_PER_SPORT}")
    if result_loaders is not None:
        unknown = set(result_loaders) - {sport.value for sport in Sport}
        if unknown:
            raise ValueError(f"unsupported result loader: {sorted(unknown)[0]}")
        if any(not callable(loader) for loader in result_loaders.values()):
            raise TypeError("result loaders must be callable")
    resolved_store = store or RiskBetStore(db_path, latest_path)
    latest = resolved_store.read_latest()
    if latest is None:
        return SettlementAutomationSummary(None, 0, 0, (), 0, 0, False)
    run_id = latest.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("published RisikoBet run has no run_id")
    expected_payload_digest = hashlib.sha256(
        canonical_json(latest).encode("utf-8")
    ).hexdigest()
    stored_latest = resolved_store.load_run(run_id)
    if stored_latest is None:
        raise ValueError("published RisikoBet run is missing from the store")
    publication_needs_repair = canonical_json(stored_latest) != canonical_json(latest)
    targets = resolved_store.load_due_settlement_targets(as_of=observed_now)
    run = {
        "snapshots": [target["snapshot"] for target in targets],
        "candidates": [target["candidate"] for target in targets],
    }
    due, errors = _due_candidates(run, now=observed_now)
    requests, candidates_by_event, request_errors = _requests_by_sport(
        due,
        max_events_per_sport=max_events_per_sport,
        now=observed_now,
    )
    errors.extend(request_errors)
    inserted = 0
    queried_candidates = sum(
        len(candidates_by_event[(sport, request.event_key)])
        for sport, sport_requests in requests.items()
        for request in sport_requests
    )
    unresolved = len(due) - queried_candidates
    checked: list[str] = []
    overrides = dict(result_loaders or {})
    for sport in sorted(requests):
        sport_requests = requests[sport]
        if not sport_requests:
            continue
        loader = overrides.get(sport)
        if loader is None:
            loader = _default_loader(
                sport,
                config=config,
                football_provider=football_provider,
                tennis_db_path=tennis_db_path,
                esports_db_path=esports_db_path,
            )
        if loader is None:
            errors.append(_safe_issue(sport, "result_source_unconfigured"))
            unresolved += sum(
                len(candidates_by_event[(sport, request.event_key)])
                for request in sport_requests
            )
            continue
        checked.append(sport)
        try:
            batch = _normalize_batch(loader(sport_requests, observed_now))
        except Exception as exc:
            errors.append(_safe_issue(sport, f"result_source_failed_{type(exc).__name__}"))
            unresolved += sum(
                len(candidates_by_event[(sport, request.event_key)])
                for request in sport_requests
            )
            continue
        for issue in batch.issues:
            if isinstance(issue, ResultIssue) and issue.event_key in {
                request.event_key for request in sport_requests
            }:
                errors.append(_safe_issue(sport, issue.code))
        results_by_event: dict[str, ObservedResult] = {}
        ambiguous_events: set[str] = set()
        for observation in batch.results:
            if not isinstance(observation, ObservedResult):
                errors.append(_safe_issue(sport, "result_payload_invalid"))
                continue
            if observation.event_key in ambiguous_events:
                continue
            if observation.event_key in results_by_event:
                errors.append(_safe_issue(sport, "duplicate_event_result"))
                results_by_event.pop(observation.event_key, None)
                ambiguous_events.add(observation.event_key)
                continue
            results_by_event[observation.event_key] = observation
        requested_keys = {request.event_key for request in sport_requests}
        for event_key in sorted(requested_keys):
            event_candidates = candidates_by_event[(sport, event_key)]
            observation = results_by_event.get(event_key)
            if observation is None:
                unresolved += len(event_candidates)
                continue
            observed_at = _parse_time(observation.observed_at)
            if (
                observation.sport != sport
                or observed_at is None
                or observed_at > observed_now
                or observed_at < event_candidates[0].starts_at
                or not observation.source_result_id.strip()
            ):
                errors.append(_safe_issue(sport, "result_identity_or_time_invalid"))
                unresolved += len(event_candidates)
                continue
            for candidate in event_candidates:
                try:
                    decision = settle_market(
                        sport=candidate.contract.sport,
                        market=candidate.contract.market,
                        selection=candidate.contract.selection,
                        result=observation.result,
                    )
                except (SettlementInputError, TypeError, ValueError):
                    errors.append(_safe_issue(sport, "canonical_result_invalid"))
                    unresolved += 1
                    continue
                if decision.status is SettlementStatus.UNRESOLVED:
                    unresolved += 1
                    continue
                if decision.status not in {
                    SettlementStatus.WIN,
                    SettlementStatus.LOSS,
                    SettlementStatus.VOID,
                }:
                    errors.append(_safe_issue(sport, "settlement_status_invalid"))
                    unresolved += 1
                    continue
                detail = {
                    "event_key": event_key,
                    "source_result_id": observation.source_result_id,
                    "canonical_result": _canonical_result_payload(observation.result),
                }
                try:
                    was_inserted = resolved_store.append_terminal_settlement(
                        candidate_id=str(candidate.payload["candidate_id"]),
                        snapshot_id=str(candidate.payload["snapshot_id"]),
                        result=decision,
                        settled_at=observed_at,
                        settlement_version=str(candidate.payload["settlement_contract"]),
                        detail=detail,
                    )
                except FrozenRevisionError:
                    raise
                except Exception as exc:
                    errors.append(_safe_issue(sport, f"settlement_write_failed_{type(exc).__name__}"))
                    continue
                inserted += int(was_inserted)
    published = False
    if inserted or publication_needs_repair:
        published = resolved_store.republish_latest_if_current(
            run_id,
            expected_payload_digest=expected_payload_digest,
        )
        if not published:
            errors.append("automation:latest_changed_before_publication")
    return SettlementAutomationSummary(
        run_id=run_id,
        due_candidates=len(due),
        due_events=sum(len(items) for items in requests.values()),
        checked_sports=tuple(checked),
        terminal_settlements=inserted,
        unresolved_candidates=unresolved,
        published=published,
        errors=tuple(dict.fromkeys(errors)),
    )


__all__ = [
    "MAX_EVENTS_PER_SPORT",
    "MAX_SHADOW_ROWS_PER_SOURCE",
    "ObservedResult",
    "ResultIssue",
    "ResultLoadBatch",
    "ResultLoader",
    "SettlementAutomationSummary",
    "SettlementRequest",
    "esports_result_loader",
    "football_result_loader",
    "run_riskobet_settlements",
    "tennis_result_loader",
]
