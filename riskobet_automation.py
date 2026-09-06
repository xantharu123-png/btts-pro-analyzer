"""Price-neutral RisikoBet aggregation and read-only publication.

This module deliberately knows nothing about Streamlit, provider clients or
bookmaker prices.  Scheduled jobs inject already adapted sport batches (or
loaders which return them), the aggregator isolates source failures, publishes
one immutable :class:`RiskRunSnapshot`, and the page only reads the resulting
``riskobet_latest.json`` document.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, TypeAlias

from date_context import ZURICH_TIMEZONE
from riskobet_domain import (
    ContextState,
    EvidenceStage,
    EventModelSnapshot,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
    RiskRunSnapshot,
    RunStatus,
    SUPPORTED_SPORTS,
)
from riskobet_store import DEFAULT_DB_PATH, DEFAULT_LATEST_PATH, RiskBetStore
from riskobet_quality import evidence_order


SPORT_ORDER = (
    "football",
    "tennis",
    "basketball",
    "ice_hockey",
    "cricket",
    "esports",
)
RESEARCH_REUSE_SPORTS = frozenset({"basketball", "ice_hockey", "cricket"})


@dataclass(frozen=True, slots=True)
class RiskSourceBatch:
    """One provider-free result from exactly one sport adapter.

    ``errors`` means that the adapter produced useful partial data.  A loader
    exception is represented by the aggregator instead, so one broken sport
    can never discard the successful output of another sport.
    """

    sport: str
    snapshots: tuple[EventModelSnapshot, ...] = ()
    candidates: tuple[RiskCandidate, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.sport not in SUPPORTED_SPORTS:
            raise ValueError("sport is not supported by RisikoBet")
        snapshots = tuple(self.snapshots)
        candidates = tuple(self.candidates)
        errors = tuple(str(error).strip() for error in self.errors)
        if any(not isinstance(item, EventModelSnapshot) for item in snapshots):
            raise TypeError("snapshots must contain EventModelSnapshot values")
        if any(not isinstance(item, RiskCandidate) for item in candidates):
            raise TypeError("candidates must contain RiskCandidate values")
        if any(item.sport != self.sport for item in snapshots):
            raise ValueError("a source batch may only contain its declared sport")
        if any(item.sport != self.sport for item in candidates):
            raise ValueError("a source batch may only contain its declared sport")
        snapshot_ids = {item.snapshot_id for item in snapshots}
        if any(item.snapshot_id not in snapshot_ids for item in candidates):
            raise ValueError("every source candidate must reference a source snapshot")
        if any(not error for error in errors):
            raise ValueError("source errors must not be empty")
        object.__setattr__(self, "snapshots", snapshots)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "errors", _unique(errors))


RiskSourceValue: TypeAlias = RiskSourceBatch | RiskRunSnapshot | object
RiskSourceLoader: TypeAlias = Callable[[], RiskSourceValue]


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return tuple(result)


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _parse_datetime(value: object, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value, field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO datetime")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    return _aware_utc(parsed, field_name)


def _error_text(sport: str, error: object) -> str:
    """Return a stable public error code without provider payload details."""

    if isinstance(error, BaseException):
        code = f"source_failed:{type(error).__name__}"
    elif str(error).strip() == "source is due but unavailable":
        code = "source_unavailable"
    else:
        # Batch errors can originate in provider responses.  Their raw text is
        # useful in private service logs, but the latest JSON is a consumer
        # artifact and must never become a secret/error-detail side channel.
        code = "source_partial"
    return f"{sport}: {code}"


def _factor_from_dict(payload: Mapping[str, object]) -> FactorEvidence:
    return FactorEvidence(
        factor_key=str(payload["factor_key"]),
        summary=str(payload["summary"]),
        source=str(payload["source"]),
        observed_at=_parse_datetime(payload["observed_at"], "observed_at"),
        imported_at=_parse_datetime(payload["imported_at"], "imported_at"),
        fresh_until=_parse_datetime(payload["fresh_until"], "fresh_until"),
        coverage=payload.get("coverage"),
        sample_size=payload.get("sample_size"),
        role=FactorRole(payload.get("role", FactorRole.MODEL.value)),
    )


def snapshot_from_dict(payload: Mapping[str, object]) -> EventModelSnapshot:
    """Rehydrate one immutable event revision from a consumer document."""

    factors = payload.get("factors", ())
    if not isinstance(factors, (list, tuple)):
        raise ValueError("snapshot factors must be a sequence")
    missing = payload.get("missing_core_data", ())
    if not isinstance(missing, (list, tuple)):
        raise ValueError("snapshot missing_core_data must be a sequence")
    snapshot = EventModelSnapshot(
        event_key=str(payload["event_key"]),
        sport=str(payload["sport"]),
        competition=str(payload["competition"]),
        event_label=str(payload["event_label"]),
        starts_at=_parse_datetime(payload["starts_at"], "starts_at"),
        modeled_at=_parse_datetime(payload["modeled_at"], "modeled_at"),
        input_cutoff_at=_parse_datetime(
            payload["input_cutoff_at"], "input_cutoff_at"
        ),
        model_version=str(payload["model_version"]),
        input_hash=str(payload["input_hash"]),
        factors=tuple(_factor_from_dict(item) for item in factors),
        missing_core_data=tuple(str(item) for item in missing),
    )
    stored_id = payload.get("snapshot_id")
    if stored_id is not None and stored_id != snapshot.snapshot_id:
        raise ValueError("snapshot_id does not match immutable snapshot content")
    return snapshot


def candidate_from_dict(payload: Mapping[str, object]) -> RiskCandidate:
    """Rehydrate a price-neutral candidate, ignoring consumer-only metadata."""

    pros = payload.get("pros", ())
    cons = payload.get("cons", ())
    missing = payload.get("missing_core_data", ())
    if not all(isinstance(items, (list, tuple)) for items in (pros, cons, missing)):
        raise ValueError("candidate evidence fields must be sequences")
    candidate = RiskCandidate(
        snapshot_id=str(payload["snapshot_id"]),
        event_key=str(payload["event_key"]),
        sport=str(payload["sport"]),
        competition=str(payload["competition"]),
        event_label=str(payload["event_label"]),
        starts_at=_parse_datetime(payload["starts_at"], "starts_at"),
        market_key=str(payload["market_key"]),
        market_label=str(payload["market_label"]),
        selection_key=str(payload["selection_key"]),
        selection_label=str(payload["selection_label"]),
        model_probability=payload.get("model_probability"),
        cautious_probability=payload.get("cautious_probability"),
        stage=EvidenceStage(payload["stage"]),
        context_state=ContextState(payload["context_state"]),
        policy_version=str(payload["policy_version"]),
        pros=tuple(str(item) for item in pros),
        cons=tuple(str(item) for item in cons),
        missing_core_data=tuple(str(item) for item in missing),
        settlement_contract=(
            None
            if payload.get("settlement_contract") is None
            else str(payload["settlement_contract"])
        ),
    )
    stored_id = payload.get("candidate_id")
    if stored_id is not None and stored_id != candidate.candidate_id:
        raise ValueError("candidate_id does not match immutable candidate content")
    return candidate


def run_from_dict(payload: Mapping[str, object]) -> RiskRunSnapshot:
    """Rehydrate a complete latest document and verify its deterministic ID."""

    snapshots_payload = payload.get("snapshots", ())
    candidates_payload = payload.get("candidates", ())
    errors_payload = payload.get("errors", ())
    if not isinstance(snapshots_payload, (list, tuple)):
        raise ValueError("run snapshots must be a sequence")
    if not isinstance(candidates_payload, (list, tuple)):
        raise ValueError("run candidates must be a sequence")
    if not isinstance(errors_payload, (list, tuple)):
        raise ValueError("run errors must be a sequence")
    run = RiskRunSnapshot(
        started_at=_parse_datetime(payload["started_at"], "started_at"),
        completed_at=_parse_datetime(payload["completed_at"], "completed_at"),
        status=RunStatus(payload["status"]),
        snapshots=tuple(snapshot_from_dict(item) for item in snapshots_payload),
        candidates=tuple(candidate_from_dict(item) for item in candidates_payload),
        errors=tuple(str(item) for item in errors_payload),
    )
    stored_id = payload.get("run_id")
    if stored_id is not None and stored_id != run.run_id:
        raise ValueError("run_id does not match immutable run content")
    return run


def load_latest_riskobet(
    *,
    store: Optional[RiskBetStore] = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    latest_path: str | Path = DEFAULT_LATEST_PATH,
    rehydrate: bool = False,
) -> Optional[dict[str, object] | RiskRunSnapshot]:
    """Read the published snapshot without making any provider call.

    Streamlit should use this function (normally with ``rehydrate=False``).
    Scheduled jobs can request a verified domain object for same-day reuse.
    """

    resolved = store or RiskBetStore(db_path, latest_path)
    payload = resolved.read_latest()
    if payload is None:
        # Backup restores may contain the integrity-checked database before
        # the derived latest JSON is recreated.  Recovery is deliberately
        # read-only and fails closed for legacy, foreign or partial stores.
        payload = RiskBetStore.recover_latest_from_database(resolved.db_path)
    if payload is None or not rehydrate:
        return payload
    return run_from_dict(payload)


def _batch_from_run(run: RiskRunSnapshot, sport: str) -> RiskSourceBatch:
    snapshots = tuple(item for item in run.snapshots if item.sport == sport)
    snapshot_ids = {item.snapshot_id for item in snapshots}
    candidates = tuple(
        item
        for item in run.candidates
        if item.sport == sport and item.snapshot_id in snapshot_ids
    )
    return RiskSourceBatch(sport=sport, snapshots=snapshots, candidates=candidates)


def _normalize_source(value: RiskSourceValue, sport: str) -> RiskSourceBatch:
    if isinstance(value, RiskSourceBatch):
        if value.sport != sport:
            raise ValueError(
                f"source returned {value.sport}, expected isolated sport {sport}"
            )
        return value
    if isinstance(value, RiskRunSnapshot):
        return _batch_from_run(value, sport)

    # ``riskobet_candidates.RiskAdapterResult`` intentionally stays outside
    # this module's import graph.  Its tiny structural contract also makes
    # adapter tests and future model versions independently injectable.
    if isinstance(value, (str, bytes, Mapping)):
        raise TypeError(
            "source must return a domain batch, run or RiskAdapterResult sequence"
        )
    if hasattr(value, "snapshot") and hasattr(value, "candidates"):
        adapter_results = (value,)
    else:
        try:
            adapter_results = tuple(value)  # type: ignore[arg-type]
        except TypeError as exc:
            raise TypeError(
                "source must return a domain batch, run or RiskAdapterResult sequence"
            ) from exc
    snapshots: list[EventModelSnapshot] = []
    candidates: list[RiskCandidate] = []
    for result in adapter_results:
        snapshot = getattr(result, "snapshot", None)
        result_candidates = getattr(result, "candidates", None)
        if not isinstance(snapshot, EventModelSnapshot) or result_candidates is None:
            raise TypeError("adapter results must expose snapshot and candidates")
        try:
            result_candidates = tuple(result_candidates)
        except TypeError as exc:
            raise TypeError("adapter candidates must be a sequence") from exc
        if any(not isinstance(item, RiskCandidate) for item in result_candidates):
            raise TypeError("adapter candidates must contain RiskCandidate values")
        snapshots.append(snapshot)
        candidates.extend(result_candidates)
    return RiskSourceBatch(
        sport=sport,
        snapshots=tuple(snapshots),
        candidates=tuple(candidates),
    )


def _same_zurich_day(left: datetime, right: datetime) -> bool:
    return left.astimezone(ZURICH_TIMEZONE).date() == right.astimezone(
        ZURICH_TIMEZONE
    ).date()


def _research_batch_from_prior(
    prior: Optional[RiskRunSnapshot],
    sport: str,
    now: datetime,
) -> Optional[RiskSourceBatch]:
    if (
        prior is None
        or sport not in RESEARCH_REUSE_SPORTS
        or not _same_zurich_day(prior.completed_at, now)
    ):
        return None
    # Reuse is not an unconditional copy of yesterday's/public latest.  Only
    # still-upcoming revisions whose evidence has not expired may survive a
    # skipped or failed refresh.  Factorless RESEARCH revisions are retained
    # for the current Zurich day because they explicitly carry ``p=None`` and
    # therefore cannot masquerade as a fresh measured probability.
    snapshots = tuple(
        snapshot
        for snapshot in prior.snapshots
        if snapshot.sport == sport
        and snapshot.starts_at > now
        and snapshot.modeled_at <= now
        and all(factor.fresh_until >= now for factor in snapshot.factors)
    )
    snapshot_ids = {snapshot.snapshot_id for snapshot in snapshots}
    candidates = tuple(
        candidate
        for candidate in prior.candidates
        if candidate.sport == sport
        and candidate.stage is EvidenceStage.RESEARCH
        and candidate.context_state is not ContextState.STALE
        and candidate.starts_at > now
        and candidate.snapshot_id in snapshot_ids
    )
    if not snapshots and not candidates:
        return None
    return RiskSourceBatch(sport=sport, snapshots=snapshots, candidates=candidates)


def _latest_revisions(
    batches: Iterable[RiskSourceBatch],
) -> tuple[tuple[EventModelSnapshot, ...], tuple[RiskCandidate, ...]]:
    snapshots_by_event: dict[tuple[str, str], EventModelSnapshot] = {}
    candidates: list[RiskCandidate] = []
    for batch in batches:
        for snapshot in batch.snapshots:
            key = (snapshot.sport, snapshot.event_key)
            previous = snapshots_by_event.get(key)
            if (
                previous is not None
                and snapshot.snapshot_id != previous.snapshot_id
                and (
                    snapshot.modeled_at,
                    snapshot.input_cutoff_at,
                )
                == (
                    previous.modeled_at,
                    previous.input_cutoff_at,
                )
            ):
                raise ValueError(
                    "ambiguous equal-time snapshot revisions for one event"
                )
            if previous is None or (
                snapshot.modeled_at,
                snapshot.input_cutoff_at,
            ) > (
                previous.modeled_at,
                previous.input_cutoff_at,
            ):
                snapshots_by_event[key] = snapshot
        candidates.extend(batch.candidates)

    snapshots = tuple(
        sorted(
            snapshots_by_event.values(),
            key=lambda item: (item.starts_at, SPORT_ORDER.index(item.sport), item.event_key),
        )
    )
    selected_snapshot_ids = {item.snapshot_id for item in snapshots}
    candidates = [
        candidate
        for candidate in candidates
        if candidate.snapshot_id in selected_snapshot_ids
    ]

    snapshot_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}

    def rank(candidate: RiskCandidate) -> tuple[object, ...]:
        return evidence_order(candidate, snapshot_by_id.get(candidate.snapshot_id))

    unique_candidates: dict[tuple[str, str], RiskCandidate] = {}
    for candidate in sorted(candidates, key=rank):
        unique_candidates.setdefault(
            (candidate.snapshot_id, candidate.candidate_id), candidate
        )

    selected: list[RiskCandidate] = []
    event_counts: dict[tuple[str, str], int] = {}
    for candidate in sorted(unique_candidates.values(), key=rank):
        event_key = (candidate.sport, candidate.event_key)
        if event_counts.get(event_key, 0) >= 2:
            continue
        selected.append(candidate)
        event_counts[event_key] = event_counts.get(event_key, 0) + 1
    return snapshots, tuple(selected)


def run_riskobet(
    *,
    football_source: Optional[RiskSourceValue | RiskSourceLoader] = None,
    tennis_source: Optional[RiskSourceValue | RiskSourceLoader] = None,
    basketball_source: Optional[RiskSourceValue | RiskSourceLoader] = None,
    ice_hockey_source: Optional[RiskSourceValue | RiskSourceLoader] = None,
    cricket_source: Optional[RiskSourceValue | RiskSourceLoader] = None,
    esports_source: Optional[RiskSourceValue | RiskSourceLoader] = None,
    source_loaders: Optional[Mapping[str, RiskSourceLoader]] = None,
    source_due: Optional[Mapping[str, bool]] = None,
    store: Optional[RiskBetStore] = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    latest_path: str | Path = DEFAULT_LATEST_PATH,
    now: Optional[datetime] = None,
    reuse_same_day_research: bool = True,
    preserve_latest_on_total_failure: bool = True,
) -> RiskRunSnapshot:
    """Aggregate six isolated sport sources and atomically publish the run.

    Inputs are already adapted domain batches or zero-argument loaders.  No
    default provider is imported or called here.  ``source_due`` can suppress
    a scheduled research refresh; same-Zurich-day Basketball, Ice Hockey and
    Cricket research revisions are then reused from the previous publication.
    """

    started_at = _aware_utc(now or datetime.now(timezone.utc), "now")
    if not isinstance(reuse_same_day_research, bool):
        raise ValueError("reuse_same_day_research must be a boolean")
    if not isinstance(preserve_latest_on_total_failure, bool):
        raise ValueError("preserve_latest_on_total_failure must be a boolean")
    resolved_store = store or RiskBetStore(db_path, latest_path)

    direct_sources: dict[str, Optional[RiskSourceValue | RiskSourceLoader]] = {
        "football": football_source,
        "tennis": tennis_source,
        "basketball": basketball_source,
        "ice_hockey": ice_hockey_source,
        "cricket": cricket_source,
        "esports": esports_source,
    }
    loaders = dict(source_loaders or {})
    unknown_loaders = set(loaders) - set(SPORT_ORDER)
    if unknown_loaders:
        raise ValueError(f"unsupported RisikoBet source: {sorted(unknown_loaders)[0]}")
    for sport, loader in loaders.items():
        if direct_sources[sport] is not None:
            raise ValueError(f"duplicate source configured for {sport}")
        if not callable(loader):
            raise TypeError(f"source loader for {sport} must be callable")
        direct_sources[sport] = loader

    due_map = dict(source_due or {})
    unknown_due = set(due_map) - set(SPORT_ORDER)
    if unknown_due:
        raise ValueError(f"unsupported RisikoBet due flag: {sorted(unknown_due)[0]}")
    if any(not isinstance(value, bool) for value in due_map.values()):
        raise ValueError("source_due values must be booleans")

    prior: Optional[RiskRunSnapshot] = None
    if reuse_same_day_research or preserve_latest_on_total_failure:
        try:
            loaded = load_latest_riskobet(store=resolved_store, rehydrate=True)
            prior = loaded if isinstance(loaded, RiskRunSnapshot) else None
        except (KeyError, TypeError, ValueError):
            # A new valid run can repair a malformed consumer document.  We do
            # not reuse unverified prior data and do not let it poison healthy
            # independent sport sources.
            prior = None

    batches: list[RiskSourceBatch] = []
    errors: list[str] = []
    successful_sources = 0
    reused_sources = 0
    attempted_sources = 0
    for sport in SPORT_ORDER:
        source = direct_sources[sport]
        due = due_map.get(sport, source is not None)
        if callable(source) and not due:
            source = None
        if source is None:
            if due:
                attempted_sources += 1
                errors.append(_error_text(sport, "source is due but unavailable"))
            reused = (
                _research_batch_from_prior(prior, sport, started_at)
                if reuse_same_day_research
                else None
            )
            if reused is not None:
                batches.append(reused)
                reused_sources += 1
            continue

        attempted_sources += 1
        try:
            value = source() if callable(source) else source
            batch = _normalize_source(value, sport)
        except Exception as exc:
            errors.append(_error_text(sport, exc))
            reused = (
                _research_batch_from_prior(prior, sport, started_at)
                if reuse_same_day_research
                else None
            )
            if reused is not None:
                batches.append(reused)
                reused_sources += 1
            continue
        batches.append(batch)
        successful_sources += 1
        errors.extend(_error_text(sport, error) for error in batch.errors)

    # A wake-up with no configured/due source is not a new observation.  Do
    # not manufacture a fresh run timestamp or replace the atomic latest file.
    if attempted_sources == 0:
        if prior is not None:
            return prior
        return RiskRunSnapshot(
            started_at=started_at,
            completed_at=started_at,
            status=RunStatus.FAILED,
            errors=("automation: no_source_configured",),
        )

    snapshots, candidates = _latest_revisions(batches)
    unique_errors = _unique(errors)
    if unique_errors:
        has_surviving_source = successful_sources > 0 or reused_sources > 0
        status = RunStatus.PARTIAL if has_surviving_source else RunStatus.FAILED
    else:
        status = RunStatus.COMPLETE
    run = RiskRunSnapshot(
        started_at=started_at,
        completed_at=started_at,
        status=status,
        snapshots=snapshots,
        candidates=candidates,
        errors=unique_errors,
    )
    resolved_store.append_run(run)
    if not (
        preserve_latest_on_total_failure
        and status is RunStatus.FAILED
        and prior is not None
    ):
        resolved_store.publish_latest(run.run_id)
    return run


__all__ = [
    "RESEARCH_REUSE_SPORTS",
    "SPORT_ORDER",
    "RiskSourceBatch",
    "candidate_from_dict",
    "load_latest_riskobet",
    "run_from_dict",
    "run_riskobet",
    "snapshot_from_dict",
]
