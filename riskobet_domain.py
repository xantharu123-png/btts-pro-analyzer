"""Immutable, price-neutral domain contracts for RisikoBet.

The contracts in this module are intentionally independent from providers,
Streamlit and bookmaker prices.  A model snapshot describes one causal input
revision, while candidates describe possible sporting outcomes derived from
that revision.  Prices are consumer overlays and must never be added here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Optional


SUPPORTED_SPORTS = frozenset(
    {
        "football",
        "tennis",
        "basketball",
        "ice_hockey",
        "cricket",
        "esports",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class EvidenceStage(str, Enum):
    RESEARCH = "RESEARCH"
    SHADOW = "SHADOW"
    VALIDATED = "VALIDATED"


class FactorRole(str, Enum):
    MODEL = "MODEL"
    DISPLAY_ONLY = "DISPLAY_ONLY"


class ContextState(str, Enum):
    FRESH = "FRESH"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    OPEN = "OPEN"


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


def _text(value: object, field_name: str, maximum: int = 500) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(
            f"{field_name} must contain between 1 and {maximum} characters"
        )
    if any(ord(character) < 32 for character in normalized):
        raise ValueError(f"{field_name} contains control characters")
    return normalized


def _utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _enum(value: object, enum_type: type[Enum], field_name: str) -> Enum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        choices = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {choices}") from exc


def _probability(value: object, field_name: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a decimal probability")
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return probability


def _optional_fraction(value: object, field_name: str) -> Optional[float]:
    if value is None:
        return None
    return _probability(value, field_name)


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite number")
    return number


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _strings(
    values: Iterable[object],
    field_name: str,
    *,
    required: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    try:
        normalized = tuple(_text(item, field_name) for item in values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a sequence of strings") from exc
    if required and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()}"


def canonical_input_hash(payload: Any) -> str:
    """Return a stable SHA-256 for JSON-compatible provider/model input.

    Raw bytes are hashed as-is. Strings are encoded as UTF-8. Other values
    must be canonical-JSON serializable; non-finite numbers are rejected.
    """

    if isinstance(payload, bytes):
        encoded = payload
    elif isinstance(payload, str):
        encoded = payload.encode("utf-8")
    else:
        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("input payload must be canonical-JSON serializable") from exc
    return hashlib.sha256(encoded).hexdigest()


def stable_event_key(sport: str, provider: str, provider_event_id: str) -> str:
    """Build a locale-independent event identity from provider identity."""

    normalized_sport = _text(sport, "sport", 40)
    if normalized_sport not in SUPPORTED_SPORTS:
        raise ValueError("sport is not supported by RisikoBet")
    return _stable_id(
        "event",
        normalized_sport,
        _text(provider, "provider", 120),
        _text(provider_event_id, "provider_event_id", 240),
    )


@dataclass(frozen=True, slots=True)
class FactorEvidence:
    """One attributable and time-bounded model or display-only factor."""

    factor_key: str
    summary: str
    source: str
    observed_at: datetime
    imported_at: datetime
    fresh_until: datetime
    coverage: Optional[float] = None
    sample_size: Optional[int] = None
    role: FactorRole = FactorRole.MODEL

    def __post_init__(self) -> None:
        object.__setattr__(self, "factor_key", _text(self.factor_key, "factor_key", 160))
        object.__setattr__(self, "summary", _text(self.summary, "summary", 600))
        object.__setattr__(self, "source", _text(self.source, "source", 240))
        observed = _utc(self.observed_at, "observed_at")
        imported = _utc(self.imported_at, "imported_at")
        fresh_until = _utc(self.fresh_until, "fresh_until")
        if imported < observed:
            raise ValueError("imported_at must not precede observed_at")
        if fresh_until < observed:
            raise ValueError("fresh_until must not precede observed_at")
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "imported_at", imported)
        object.__setattr__(self, "fresh_until", fresh_until)
        object.__setattr__(
            self,
            "coverage",
            _optional_fraction(self.coverage, "coverage"),
        )
        if self.sample_size is not None:
            if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int):
                raise ValueError("sample_size must be an integer")
            if self.sample_size < 0:
                raise ValueError("sample_size must not be negative")
        object.__setattr__(self, "role", _enum(self.role, FactorRole, "role"))

    def to_dict(self) -> dict[str, object]:
        return {
            "factor_key": self.factor_key,
            "summary": self.summary,
            "source": self.source,
            "observed_at": _iso(self.observed_at),
            "imported_at": _iso(self.imported_at),
            "fresh_until": _iso(self.fresh_until),
            "coverage": self.coverage,
            "sample_size": self.sample_size,
            "role": self.role.value,
        }


@dataclass(frozen=True, slots=True)
class EventModelSnapshot:
    """One immutable, causal model input revision for a sporting event."""

    event_key: str
    sport: str
    competition: str
    event_label: str
    starts_at: datetime
    modeled_at: datetime
    input_cutoff_at: datetime
    model_version: str
    input_hash: str
    factors: tuple[FactorEvidence, ...] = ()
    missing_core_data: tuple[str, ...] = ()
    snapshot_id: str = field(init=False)

    def __post_init__(self) -> None:
        event_key = _text(self.event_key, "event_key", 240)
        sport = _text(self.sport, "sport", 40)
        if sport not in SUPPORTED_SPORTS:
            raise ValueError("sport is not supported by RisikoBet")
        model_version = _text(self.model_version, "model_version", 120)
        input_hash = _text(self.input_hash, "input_hash", 64).lower()
        if not _SHA256_RE.fullmatch(input_hash):
            raise ValueError("input_hash must be a lowercase SHA-256 digest")
        starts_at = _utc(self.starts_at, "starts_at")
        modeled_at = _utc(self.modeled_at, "modeled_at")
        input_cutoff_at = _utc(self.input_cutoff_at, "input_cutoff_at")
        if input_cutoff_at > modeled_at:
            raise ValueError("input_cutoff_at must not follow modeled_at")
        if modeled_at > starts_at:
            raise ValueError("modeled_at must not follow starts_at")
        try:
            factors = tuple(self.factors)
        except TypeError as exc:
            raise ValueError("factors must be a sequence") from exc
        if any(not isinstance(factor, FactorEvidence) for factor in factors):
            raise ValueError("factors must contain FactorEvidence values")
        if any(factor.observed_at > input_cutoff_at for factor in factors):
            raise ValueError("factor observed_at must not follow input_cutoff_at")
        if any(factor.imported_at > modeled_at for factor in factors):
            raise ValueError("factor imported_at must not follow modeled_at")
        factor_keys = [factor.factor_key for factor in factors]
        if len(set(factor_keys)) != len(factor_keys):
            raise ValueError("factor keys must be unique within a snapshot")
        missing = _strings(self.missing_core_data, "missing_core_data")
        object.__setattr__(self, "event_key", event_key)
        object.__setattr__(self, "sport", sport)
        object.__setattr__(self, "competition", _text(self.competition, "competition", 240))
        object.__setattr__(self, "event_label", _text(self.event_label, "event_label", 300))
        object.__setattr__(self, "starts_at", starts_at)
        object.__setattr__(self, "modeled_at", modeled_at)
        object.__setattr__(self, "input_cutoff_at", input_cutoff_at)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "input_hash", input_hash)
        object.__setattr__(self, "factors", factors)
        object.__setattr__(self, "missing_core_data", missing)
        object.__setattr__(
            self,
            "snapshot_id",
            _stable_id("snapshot", event_key, model_version, input_hash),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "event_key": self.event_key,
            "sport": self.sport,
            "competition": self.competition,
            "event_label": self.event_label,
            "starts_at": _iso(self.starts_at),
            "modeled_at": _iso(self.modeled_at),
            "input_cutoff_at": _iso(self.input_cutoff_at),
            "model_version": self.model_version,
            "input_hash": self.input_hash,
            "factors": [factor.to_dict() for factor in self.factors],
            "missing_core_data": list(self.missing_core_data),
        }


@dataclass(frozen=True, slots=True)
class ValidationEvidenceArtifact:
    """Version-bound proof required for a SHADOW -> VALIDATED promotion.

    The artifact contains only predeclared model-validation measurements.  It
    intentionally contains no bookmaker price, profit or CLV information.
    Invalid or incomplete evidence cannot be represented as an instance.
    """

    validation_version: str
    policy_version: str
    model_version: str
    settlement_contract: str
    walk_forward_sample_size: int
    predeclared_minimum_sample_size: int
    hac_brier_advantage_lower_bound: float
    bh_fdr_q: float
    tail_calibration_error: float
    maximum_tail_calibration_error: float
    active_drift: bool
    settlement_rate: float
    minimum_settlement_rate: float
    evaluation_blocks: int
    esports_patch_periods: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validation_version",
            _text(self.validation_version, "validation_version", 120),
        )
        object.__setattr__(
            self,
            "policy_version",
            _text(self.policy_version, "policy_version", 120),
        )
        object.__setattr__(
            self,
            "model_version",
            _text(self.model_version, "model_version", 120),
        )
        object.__setattr__(
            self,
            "settlement_contract",
            _text(self.settlement_contract, "settlement_contract", 240),
        )
        sample_size = _positive_integer(
            self.walk_forward_sample_size,
            "walk_forward_sample_size",
        )
        minimum_sample_size = _positive_integer(
            self.predeclared_minimum_sample_size,
            "predeclared_minimum_sample_size",
        )
        if sample_size < minimum_sample_size:
            raise ValueError(
                "walk_forward_sample_size must meet the predeclared minimum"
            )
        hac_lower = _finite_number(
            self.hac_brier_advantage_lower_bound,
            "hac_brier_advantage_lower_bound",
        )
        if hac_lower <= 0:
            raise ValueError("HAC Brier advantage lower bound must be above zero")
        q_value = _probability(self.bh_fdr_q, "bh_fdr_q")
        if q_value is None or q_value > 0.05:
            raise ValueError("bh_fdr_q must be at most 0.05")
        calibration_error = _probability(
            self.tail_calibration_error,
            "tail_calibration_error",
        )
        maximum_calibration_error = _probability(
            self.maximum_tail_calibration_error,
            "maximum_tail_calibration_error",
        )
        if (
            calibration_error is None
            or maximum_calibration_error is None
            or calibration_error > maximum_calibration_error
        ):
            raise ValueError(
                "tail calibration error exceeds the predeclared maximum"
            )
        if not isinstance(self.active_drift, bool):
            raise ValueError("active_drift must be a boolean")
        if self.active_drift:
            raise ValueError("VALIDATED evidence must not have active drift")
        settlement_rate = _probability(self.settlement_rate, "settlement_rate")
        minimum_settlement_rate = _probability(
            self.minimum_settlement_rate,
            "minimum_settlement_rate",
        )
        if (
            settlement_rate is None
            or minimum_settlement_rate is None
            or settlement_rate < minimum_settlement_rate
        ):
            raise ValueError("settlement_rate is below the predeclared minimum")
        evaluation_blocks = _positive_integer(
            self.evaluation_blocks,
            "evaluation_blocks",
        )
        if evaluation_blocks < 2:
            raise ValueError("VALIDATED evidence requires at least two blocks")
        if (
            isinstance(self.esports_patch_periods, bool)
            or not isinstance(self.esports_patch_periods, int)
            or self.esports_patch_periods < 0
        ):
            raise ValueError("esports_patch_periods must be a non-negative integer")
        object.__setattr__(self, "walk_forward_sample_size", sample_size)
        object.__setattr__(
            self,
            "predeclared_minimum_sample_size",
            minimum_sample_size,
        )
        object.__setattr__(
            self,
            "hac_brier_advantage_lower_bound",
            hac_lower,
        )
        object.__setattr__(self, "bh_fdr_q", q_value)
        object.__setattr__(self, "tail_calibration_error", calibration_error)
        object.__setattr__(
            self,
            "maximum_tail_calibration_error",
            maximum_calibration_error,
        )
        object.__setattr__(self, "settlement_rate", settlement_rate)
        object.__setattr__(
            self,
            "minimum_settlement_rate",
            minimum_settlement_rate,
        )
        object.__setattr__(self, "evaluation_blocks", evaluation_blocks)

    def to_dict(self) -> dict[str, object]:
        return {
            "validation_version": self.validation_version,
            "policy_version": self.policy_version,
            "model_version": self.model_version,
            "settlement_contract": self.settlement_contract,
            "walk_forward_sample_size": self.walk_forward_sample_size,
            "predeclared_minimum_sample_size": self.predeclared_minimum_sample_size,
            "hac_brier_advantage_lower_bound": self.hac_brier_advantage_lower_bound,
            "bh_fdr_q": self.bh_fdr_q,
            "tail_calibration_error": self.tail_calibration_error,
            "maximum_tail_calibration_error": self.maximum_tail_calibration_error,
            "active_drift": self.active_drift,
            "settlement_rate": self.settlement_rate,
            "minimum_settlement_rate": self.minimum_settlement_rate,
            "evaluation_blocks": self.evaluation_blocks,
            "esports_patch_periods": self.esports_patch_periods,
        }


@dataclass(frozen=True, slots=True)
class RiskCandidate:
    """A price-independent surprise scenario derived from one snapshot."""

    snapshot_id: str
    event_key: str
    sport: str
    competition: str
    event_label: str
    starts_at: datetime
    market_key: str
    market_label: str
    selection_key: str
    selection_label: str
    model_probability: Optional[float]
    cautious_probability: Optional[float]
    stage: EvidenceStage
    context_state: ContextState
    policy_version: str
    pros: tuple[str, ...] = ()
    cons: tuple[str, ...] = ()
    missing_core_data: tuple[str, ...] = ()
    settlement_contract: Optional[str] = None
    candidate_id: str = field(init=False)

    def __post_init__(self) -> None:
        snapshot_id = _text(self.snapshot_id, "snapshot_id", 100)
        if not snapshot_id.startswith("snapshot_") or not _SHA256_RE.fullmatch(
            snapshot_id.removeprefix("snapshot_")
        ):
            raise ValueError("snapshot_id is not a RisikoBet snapshot identity")
        event_key = _text(self.event_key, "event_key", 240)
        sport = _text(self.sport, "sport", 40)
        if sport not in SUPPORTED_SPORTS:
            raise ValueError("sport is not supported by RisikoBet")
        market_key = _text(self.market_key, "market_key", 160)
        selection_key = _text(self.selection_key, "selection_key", 160)
        policy_version = _text(self.policy_version, "policy_version", 120)
        model_probability = _probability(
            self.model_probability,
            "model_probability",
        )
        cautious_probability = _probability(
            self.cautious_probability,
            "cautious_probability",
        )
        stage = _enum(self.stage, EvidenceStage, "stage")
        context_state = _enum(self.context_state, ContextState, "context_state")
        if model_probability is None:
            if stage is not EvidenceStage.RESEARCH:
                raise ValueError("only RESEARCH candidates may omit model_probability")
            if cautious_probability is not None:
                raise ValueError(
                    "cautious_probability requires model_probability"
                )
        if (
            model_probability is not None
            and cautious_probability is not None
            and cautious_probability > model_probability
        ):
            raise ValueError(
                "cautious_probability must not exceed model_probability"
            )
        settlement_contract = self.settlement_contract
        if settlement_contract is not None:
            settlement_contract = _text(
                settlement_contract,
                "settlement_contract",
                240,
            )
        if stage in {EvidenceStage.SHADOW, EvidenceStage.VALIDATED} and not settlement_contract:
            raise ValueError("SHADOW and VALIDATED require a settlement_contract")
        missing = _strings(self.missing_core_data, "missing_core_data")
        if model_probability is None and not missing:
            raise ValueError(
                "a candidate without probability must name missing_core_data"
            )
        starts_at = _utc(self.starts_at, "starts_at")
        object.__setattr__(self, "snapshot_id", snapshot_id)
        object.__setattr__(self, "event_key", event_key)
        object.__setattr__(self, "sport", sport)
        object.__setattr__(self, "competition", _text(self.competition, "competition", 240))
        object.__setattr__(self, "event_label", _text(self.event_label, "event_label", 300))
        object.__setattr__(self, "starts_at", starts_at)
        object.__setattr__(self, "market_key", market_key)
        object.__setattr__(self, "market_label", _text(self.market_label, "market_label", 240))
        object.__setattr__(self, "selection_key", selection_key)
        object.__setattr__(self, "selection_label", _text(self.selection_label, "selection_label", 240))
        object.__setattr__(self, "model_probability", model_probability)
        object.__setattr__(self, "cautious_probability", cautious_probability)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "context_state", context_state)
        object.__setattr__(self, "policy_version", policy_version)
        object.__setattr__(self, "pros", _strings(self.pros, "pros", required=True))
        object.__setattr__(self, "cons", _strings(self.cons, "cons", required=True))
        object.__setattr__(self, "missing_core_data", missing)
        object.__setattr__(self, "settlement_contract", settlement_contract)
        object.__setattr__(
            self,
            "candidate_id",
            _stable_id(
                "candidate",
                event_key,
                sport,
                market_key,
                selection_key,
                policy_version,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "snapshot_id": self.snapshot_id,
            "event_key": self.event_key,
            "sport": self.sport,
            "competition": self.competition,
            "event_label": self.event_label,
            "starts_at": _iso(self.starts_at),
            "market_key": self.market_key,
            "market_label": self.market_label,
            "selection_key": self.selection_key,
            "selection_label": self.selection_label,
            "model_probability": self.model_probability,
            "cautious_probability": self.cautious_probability,
            "stage": self.stage.value,
            "context_state": self.context_state.value,
            "policy_version": self.policy_version,
            "pros": list(self.pros),
            "cons": list(self.cons),
            "missing_core_data": list(self.missing_core_data),
            "settlement_contract": self.settlement_contract,
        }


@dataclass(frozen=True, slots=True)
class RiskRunSnapshot:
    """One immutable aggregator result ready for persistence/publication."""

    started_at: datetime
    completed_at: datetime
    status: RunStatus
    snapshots: tuple[EventModelSnapshot, ...] = ()
    candidates: tuple[RiskCandidate, ...] = ()
    errors: tuple[str, ...] = ()
    run_id: str = field(init=False)

    def __post_init__(self) -> None:
        started_at = _utc(self.started_at, "started_at")
        completed_at = _utc(self.completed_at, "completed_at")
        if completed_at < started_at:
            raise ValueError("completed_at must not precede started_at")
        status = _enum(self.status, RunStatus, "status")
        try:
            snapshots = tuple(self.snapshots)
            candidates = tuple(self.candidates)
        except TypeError as exc:
            raise ValueError("snapshots and candidates must be sequences") from exc
        if any(not isinstance(item, EventModelSnapshot) for item in snapshots):
            raise ValueError("snapshots must contain EventModelSnapshot values")
        if any(not isinstance(item, RiskCandidate) for item in candidates):
            raise ValueError("candidates must contain RiskCandidate values")
        snapshot_ids = [item.snapshot_id for item in snapshots]
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise ValueError("run snapshots must not contain duplicates")
        candidate_keys = [
            (item.snapshot_id, item.candidate_id) for item in candidates
        ]
        if len(set(candidate_keys)) != len(candidate_keys):
            raise ValueError("run candidates must not contain duplicates")
        snapshot_by_id = {item.snapshot_id: item for item in snapshots}
        candidates_per_event: dict[str, int] = {}
        for candidate in candidates:
            snapshot = snapshot_by_id.get(candidate.snapshot_id)
            if snapshot is None:
                raise ValueError("every candidate must reference a run snapshot")
            if (
                candidate.event_key != snapshot.event_key
                or candidate.sport != snapshot.sport
                or candidate.competition != snapshot.competition
                or candidate.event_label != snapshot.event_label
                or candidate.starts_at != snapshot.starts_at
            ):
                raise ValueError("candidate event identity differs from its snapshot")
            candidates_per_event[candidate.event_key] = (
                candidates_per_event.get(candidate.event_key, 0) + 1
            )
        if any(count > 2 for count in candidates_per_event.values()):
            raise ValueError("a run may publish at most two candidates per event")
        errors = _strings(self.errors, "errors")
        if status is RunStatus.COMPLETE and errors:
            raise ValueError("a COMPLETE run must not contain errors")
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "completed_at", completed_at)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "snapshots", snapshots)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "errors", errors)
        identity_parts = [
            _iso(started_at),
            _iso(completed_at),
            status.value,
            *(sorted(snapshot_ids)),
            *(f"{snapshot_id}:{candidate_id}" for snapshot_id, candidate_id in sorted(candidate_keys)),
            *(f"error:{error}" for error in errors),
        ]
        object.__setattr__(self, "run_id", _stable_id("run", *identity_parts))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "started_at": _iso(self.started_at),
            "completed_at": _iso(self.completed_at),
            "status": self.status.value,
            "snapshots": [item.to_dict() for item in self.snapshots],
            "candidates": [item.to_dict() for item in self.candidates],
            "errors": list(self.errors),
        }


def canonical_json(payload: Mapping[str, object]) -> str:
    """Serialize a domain payload deterministically for storage and hashing."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = [
    "ContextState",
    "EvidenceStage",
    "EventModelSnapshot",
    "FactorEvidence",
    "FactorRole",
    "ValidationEvidenceArtifact",
    "RiskCandidate",
    "RiskRunSnapshot",
    "RunStatus",
    "SUPPORTED_SPORTS",
    "canonical_input_hash",
    "canonical_json",
    "stable_event_key",
]
