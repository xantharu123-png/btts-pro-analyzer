"""Pure deterministic data for the seven-day context-growth QA integration.

Declared immutable shapes
-------------------------
``TourSeed`` contains ``tour``, ``tournament_id``, ``grouping_slug``,
``surface``, ``best_of``, ``indoor`` and immutable ``_fixture_bytes``.
``native_fixture`` decodes a fresh copy and never exposes stored authority.

``GrowthScheduleEntry`` contains scalar ``ordinal``, ``day_index``,
``day_ordinal``, ``tour``, ``native_id``, ``observed_at``, ``receive_bucket``,
``consumer_index`` and ``key_index`` metadata.

``GrowthConsumerDescriptor`` contains ``ordinal``, ``day_index``,
``consumer_index``, ``key_index``, ``tour``, ``tournament_id``,
``grouping_slug``, ``observed_at``, ``cutoff``, ``created_at``, ``surface``,
``best_of``, ``indoor`` and immutable ``_fixture_bytes``. Its
``native_fixture`` property also returns a fresh copy.

``GrowthTargets`` labels four later integration targets; it does not report
stored counts. ``GrowthProfile`` stores at most two seeds and 168 descriptors.
Its 490,000 schedule entries and normalized receipt pairs are derived lazily.

This module is data only. It does not seal a baseline, prove namespace
collision freedom, bind model state or Source/D2 authority, create a corpus,
measure native capacity, or approve B/empirical/release acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Iterator

from context_models.contracts import ContextContractError, canonical_timestamp, require_digest, require_text
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import canonical_bytes


DAYS = 7
ADDITIONS_PER_DAY = 70_000
TOTAL_ADDITIONS = DAYS * ADDITIONS_PER_DAY
CONSUMERS_PER_DAY = 24
MAX_SIGNED_64 = 2**63 - 1
_BURST_BUCKET_ORDER = (0, 2, 1, 4, 3, 6, 5, 8, 7, 9)
_KINDS = frozenset({"atp-heavy", "mixed", "burst"})
_TOUR_DETAILS = {
    "ATP": ("mens-singles", "189-2026"),
    "WTA": ("womens-singles", "189-2026"),
}


def _fixture_copy(raw: bytes) -> dict:
    return json.loads(raw)


@dataclass(frozen=True)
class TourSeed:
    tour: str
    tournament_id: str
    grouping_slug: str
    surface: str
    best_of: int
    indoor: bool | None
    _fixture_bytes: bytes

    @property
    def native_fixture(self) -> dict:
        return _fixture_copy(self._fixture_bytes)


@dataclass(frozen=True)
class GrowthScheduleEntry:
    ordinal: int
    day_index: int
    day_ordinal: int
    tour: str
    native_id: int
    observed_at: datetime
    receive_bucket: int | None
    consumer_index: int | None
    key_index: int | None


@dataclass(frozen=True)
class GrowthConsumerDescriptor:
    ordinal: int
    day_index: int
    consumer_index: int
    key_index: int
    tour: str
    tournament_id: str
    grouping_slug: str
    observed_at: datetime
    cutoff: datetime
    created_at: datetime
    surface: str
    best_of: int
    indoor: bool | None
    _fixture_bytes: bytes

    @property
    def native_fixture(self) -> dict:
        return _fixture_copy(self._fixture_bytes)


@dataclass(frozen=True)
class GrowthTargets:
    final_receipts_target: int = 590_553
    final_originals_target: int = 199
    final_snapshots_target: int = 199
    final_tour_cutoff_keys_target: int = 114


@dataclass(frozen=True)
class GrowthProfile:
    kind: str
    baseline_sha256: str
    start_at: datetime
    first_native_id: int
    seeds: tuple[TourSeed, ...]
    _consumers: tuple[GrowthConsumerDescriptor, ...]
    targets: GrowthTargets = GrowthTargets()
    days: int = DAYS
    additions_per_day: int = ADDITIONS_PER_DAY
    total_additions: int = TOTAL_ADDITIONS

    def _tour_for(self, day_ordinal: int) -> str:
        if self.kind != "mixed":
            return "ATP"
        if day_ordinal < 34_988:
            return "ATP"
        if day_ordinal < ADDITIONS_PER_DAY - CONSUMERS_PER_DAY:
            return "WTA"
        return "ATP" if day_ordinal - (ADDITIONS_PER_DAY - CONSUMERS_PER_DAY) < 12 else "WTA"

    def _observed_at(self, day_index: int, day_ordinal: int) -> tuple[datetime, int | None]:
        day = self.start_at + timedelta(days=day_index)
        if self.kind == "burst":
            bucket = _BURST_BUCKET_ORDER[day_ordinal // 7_000]
            return day + timedelta(seconds=bucket), bucket
        return day + timedelta(microseconds=day_ordinal), None

    def iter_schedule(self) -> Iterator[GrowthScheduleEntry]:
        for ordinal in range(TOTAL_ADDITIONS):
            day_index, day_ordinal = divmod(ordinal, ADDITIONS_PER_DAY)
            consumer_index = day_ordinal - (ADDITIONS_PER_DAY - CONSUMERS_PER_DAY)
            if consumer_index < 0:
                consumer_index = None
                key_index = None
            else:
                _tour, key_index, _clock_index = _consumer_coordinates(self.kind, consumer_index)
            observed_at, bucket = self._observed_at(day_index, day_ordinal)
            yield GrowthScheduleEntry(
                ordinal=ordinal,
                day_index=day_index,
                day_ordinal=day_ordinal,
                tour=self._tour_for(day_ordinal),
                native_id=self.first_native_id + ordinal,
                observed_at=observed_at,
                receive_bucket=bucket,
                consumer_index=consumer_index,
                key_index=key_index,
            )

    def consumers(self) -> tuple[GrowthConsumerDescriptor, ...]:
        return self._consumers

    def iter_receipts(self, start: int = 0, stop: int | None = None) -> Iterator[tuple[dict, datetime]]:
        start = _slice_index(start, "start")
        stop = TOTAL_ADDITIONS if stop is None else _slice_index(stop, "stop")
        if start > stop or stop > TOTAL_ADDITIONS:
            raise ValueError("receipt slice is outside the fixed profile range")

        def generate():
            for ordinal in range(start, stop):
                yield self._receipt_at(ordinal)

        return generate()

    def _receipt_at(self, ordinal: int) -> tuple[dict, datetime]:
        day_index, day_ordinal = divmod(ordinal, ADDITIONS_PER_DAY)
        observed_at, _bucket = self._observed_at(day_index, day_ordinal)
        tour = self._tour_for(day_ordinal)
        consumer_index = day_ordinal - (ADDITIONS_PER_DAY - CONSUMERS_PER_DAY)
        if consumer_index >= 0:
            descriptor = self._consumers[day_index * CONSUMERS_PER_DAY + consumer_index]
            fixture = descriptor.native_fixture
            tournament_id = descriptor.tournament_id
            grouping_slug = descriptor.grouping_slug
        else:
            fixture = _ordinary_fixture(self.first_native_id + ordinal, ordinal, day_index, self.start_at)
            tournament_id = _TOUR_DETAILS[tour][1]
            grouping_slug = _TOUR_DETAILS[tour][0]
        rows = normalize_tennis_status(
            tour,
            tournament_id,
            fixture,
            grouping_slug=grouping_slug,
            observed_at=observed_at,
        )
        if len(rows) != 1 or rows[0]["payload"]["status"] != "scheduled" or rows[0]["payload"]["issues"]:
            raise ContextContractError("generated growth receipt is not one intact scheduled status")
        return rows[0], observed_at


def _slice_index(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"receipt slice {name} index must be an integer")
    if value < 0:
        raise ValueError(f"receipt slice {name} index is outside the fixed profile range")
    return value


def _checked_add(clock: datetime, **parts: int) -> datetime:
    try:
        return clock + timedelta(**parts)
    except (OverflowError, ValueError) as exc:
        raise ValueError("growth profile clock range overflow") from exc


def _seed(tour: str, fixture: object, start_at: datetime) -> TourSeed:
    if type(fixture) is not dict:
        raise ContextContractError(f"{tour} growth profile requires a native fixture object")
    try:
        frozen = canonical_bytes(fixture)
        detached = _fixture_copy(frozen)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContextContractError(f"{tour} native fixture is not canonical data") from exc
    grouping_slug, tournament_id = _TOUR_DETAILS[tour]
    rows = normalize_tennis_status(
        tour,
        tournament_id,
        detached,
        grouping_slug=grouping_slug,
        observed_at=start_at,
    )
    if len(rows) != 1 or rows[0]["payload"]["status"] != "scheduled" or rows[0]["payload"]["issues"]:
        raise ContextContractError(f"{tour} native fixture must be one intact scheduled singles status")
    competitors = detached.get("competitors")
    if type(competitors) is not list or len(competitors) != 2:
        raise ContextContractError(f"{tour} native fixture needs two participants")
    for participant in competitors:
        if type(participant) is not dict or type(participant.get("athlete")) is not dict:
            raise ContextContractError(f"{tour} native fixture participant metadata is malformed")
        require_text(participant["athlete"].get("displayName"), f"{tour} prediction participant name")
    surface = require_text(detached.get("surface"), f"{tour} prediction surface")
    return TourSeed(tour, tournament_id, grouping_slug, surface, 3, None, frozen)


def _consumer_coordinates(kind: str, consumer_index: int) -> tuple[str, int, int]:
    if kind != "mixed":
        key_index = consumer_index // 2 if consumer_index < 20 else 10 + consumer_index - 20
        return "ATP", key_index, key_index
    tour = "ATP" if consumer_index < 12 else "WTA"
    within = consumer_index if tour == "ATP" else consumer_index - 12
    key_index = within // 2 if within < 10 else 5 + within - 10
    return tour, key_index, key_index if tour == "ATP" else 7 + key_index


def _scheduled_fixture(seed: TourSeed, native_id: int, scheduled_start: datetime) -> bytes:
    fixture = seed.native_fixture
    fixture["id"] = str(native_id)
    fixture["date"] = canonical_timestamp(scheduled_start)
    return canonical_bytes(fixture)


def _ordinary_fixture(native_id: int, ordinal: int, day_index: int, start_at: datetime) -> dict:
    player = 1_000_000_001 + 2 * (ordinal % 1_000_000)
    return {
        "id": str(native_id),
        "date": canonical_timestamp(start_at + timedelta(days=day_index, hours=18)),
        "surface": "Hard",
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}},
        "competitors": [
            {"id": str(player), "athlete": {"displayName": f"Synthetic {ordinal % 1_000_000:06d} A"}},
            {"id": str(player + 1), "athlete": {"displayName": f"Synthetic {ordinal % 1_000_000:06d} B"}},
        ],
    }


def _build_consumers(kind: str, start_at: datetime, first_native_id: int,
        seeds: dict[str, TourSeed]) -> tuple[GrowthConsumerDescriptor, ...]:
    descriptors = []
    for day_index in range(DAYS):
        day = _checked_add(start_at, days=day_index)
        for consumer_index in range(CONSUMERS_PER_DAY):
            tour, key_index, clock_index = _consumer_coordinates(kind, consumer_index)
            ordinal = day_index * ADDITIONS_PER_DAY + ADDITIONS_PER_DAY - CONSUMERS_PER_DAY + consumer_index
            if kind == "burst":
                observed_at = _checked_add(day, seconds=9)
                cutoff = _checked_add(day, seconds=10 + clock_index)
            else:
                observed_at = _checked_add(day, microseconds=ADDITIONS_PER_DAY - CONSUMERS_PER_DAY + consumer_index)
                cutoff = _checked_add(day, hours=1, seconds=clock_index)
            scheduled_start = _checked_add(cutoff, hours=1)
            created_at = _checked_add(cutoff, microseconds=1)
            seed = seeds[tour]
            descriptors.append(GrowthConsumerDescriptor(
                ordinal=ordinal,
                day_index=day_index,
                consumer_index=consumer_index,
                key_index=key_index,
                tour=tour,
                tournament_id=seed.tournament_id,
                grouping_slug=seed.grouping_slug,
                observed_at=observed_at,
                cutoff=cutoff,
                created_at=created_at,
                surface=seed.surface,
                best_of=seed.best_of,
                indoor=seed.indoor,
                _fixture_bytes=_scheduled_fixture(seed, first_native_id + ordinal, scheduled_start),
            ))
    return tuple(descriptors)


def build_growth_profile(kind, *, baseline_sha256, start_at, first_native_id,
        atp_fixture=None, wta_fixture=None) -> GrowthProfile:
    """Build the exact fixed plan without materializing its 490,000 rows."""
    if type(kind) is not str or kind not in _KINDS:
        raise ValueError("growth profile kind must be atp-heavy, mixed or burst")
    require_digest(baseline_sha256, "growth baseline SHA-256")
    if not isinstance(start_at, datetime) or start_at.tzinfo is None or start_at.utcoffset() != timedelta(0):
        raise ContextContractError("growth profile start_at must be an aware UTC datetime")
    start_at = start_at.astimezone(timezone.utc)
    if type(first_native_id) is not int:
        raise TypeError("growth profile first native ID must be an integer")
    if first_native_id <= 0:
        raise ValueError("growth profile first native ID must be positive")
    if first_native_id + TOTAL_ADDITIONS - 1 > MAX_SIGNED_64:
        raise ValueError("growth profile native ID range exceeds signed 64-bit")
    _checked_add(start_at, days=DAYS - 1, hours=18)

    required = ("ATP", "WTA") if kind == "mixed" else ("ATP",)
    supplied = {"ATP": atp_fixture, "WTA": wta_fixture}
    seeds = {}
    for tour in required:
        if supplied[tour] is None:
            raise ContextContractError(f"{tour} fixture is required for {kind} growth profile")
        seeds[tour] = _seed(tour, supplied[tour], start_at)
    consumers = _build_consumers(kind, start_at, first_native_id, seeds)
    return GrowthProfile(
        kind=kind,
        baseline_sha256=baseline_sha256,
        start_at=start_at,
        first_native_id=first_native_id,
        seeds=tuple(seeds[tour] for tour in required),
        _consumers=consumers,
    )
