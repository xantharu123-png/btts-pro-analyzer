"""Unit evidence for the bounded synthetic full-growth input plan.

These tests enumerate cheap metadata for every planned row, but normalize only
representative rows and every consumer row.  They are not a stored corpus,
native-capacity, Source/D2, Original, snapshot, model, or release acceptance.
"""
from collections import Counter
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from itertools import islice

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_observations import _decode_receipt
from context_sources.tennis_status import validate_tennis_status_record
from model_artifacts import canonical_bytes
from context_growth_profile import (
    ADDITIONS_PER_DAY,
    DAYS,
    TOTAL_ADDITIONS,
    GrowthConsumerDescriptor,
    GrowthScheduleEntry,
    TourSeed,
    build_growth_profile,
)


START = datetime(2026, 9, 12, tzinfo=timezone.utc)
FIRST_ID = 8_000_000_000_000_000_000
BASELINE = "1" * 64


def _fixture(tour, *, tournament_id=None, surface="Hard", best_of=3, indoor=None):
    competition = {
        "id": "201" if tour == "ATP" else "202",
        "date": "2026-09-13T17:00:00Z",
        "surface": "Hard",
        "status": {
            "type": {
                "state": "pre",
                "name": "STATUS_SCHEDULED",
                "completed": False,
            }
        },
        "competitors": [
            {"id": "11" if tour == "ATP" else "21", "athlete": {"displayName": tour + " Alpha"}},
            {"id": "12" if tour == "ATP" else "22", "athlete": {"displayName": tour + " Beta"}},
        ],
    }
    return {
        "competition": competition,
        "tournament_id": tournament_id or ("901-2026" if tour == "ATP" else "902-2026"),
        "surface": surface,
        "best_of": best_of,
        "indoor": indoor,
    }


def _profile(kind):
    return build_growth_profile(
        kind,
        baseline_sha256=BASELINE,
        start_at=START,
        first_native_id=FIRST_ID,
        atp_fixture=_fixture("ATP", surface="Clay", best_of=5, indoor=True),
        wta_fixture=_fixture("WTA", surface="Grass", best_of=3, indoor=False) if kind == "mixed" else None,
    )


def _physically_decode(record, observed_at):
    observed = canonical_timestamp(observed_at)
    content_hash = digest(record)
    receipt_hash = digest({"content_digest": content_hash, "observed_at": observed})
    stored = (
        receipt_hash,
        content_hash,
        record["event_key"],
        observed,
        record["schedule_revision"],
        record["source"],
        record["subject_id"],
        record["kind"],
        canonical_bytes(record),
    )
    decoded = _decode_receipt(stored)
    validate_tennis_status_record(decoded)
    return decoded


@pytest.mark.parametrize("kind", ["atp-heavy", "mixed", "burst"])
def test_complete_schedule_has_exact_fixed_counts_and_sequential_namespace(kind):
    profile = _profile(kind)
    daily = Counter()
    daily_tours = Counter()
    consumers = Counter()
    keys = Counter()
    prior_ordinal = prior_native = None

    for entry in profile.iter_schedule():
        assert type(entry) is GrowthScheduleEntry
        assert entry.ordinal == entry.day_index * ADDITIONS_PER_DAY + entry.day_ordinal
        assert entry.native_id == FIRST_ID + entry.ordinal
        if prior_ordinal is not None:
            assert entry.ordinal == prior_ordinal + 1
            assert entry.native_id == prior_native + 1
        prior_ordinal, prior_native = entry.ordinal, entry.native_id
        daily[entry.day_index] += 1
        daily_tours[entry.day_index, entry.tour] += 1
        if entry.consumer_index is not None:
            consumers[entry.day_index, entry.tour] += 1
            keys[entry.day_index, entry.tour, entry.key_index] += 1

    assert profile.kind == kind
    assert profile.baseline_sha256 == BASELINE
    assert profile.start_at == START
    assert profile.first_native_id == FIRST_ID
    assert profile.days == DAYS == 7
    assert profile.additions_per_day == ADDITIONS_PER_DAY == 70_000
    assert profile.total_additions == TOTAL_ADDITIONS == 490_000
    assert daily == Counter({day: 70_000 for day in range(7)})
    assert prior_ordinal == 489_999 and prior_native == FIRST_ID + 489_999
    assert sum(consumers.values()) == 168
    if kind == "mixed":
        assert daily_tours == Counter({(day, tour): 35_000 for day in range(7) for tour in ("ATP", "WTA")})
        assert consumers == Counter({(day, tour): 12 for day in range(7) for tour in ("ATP", "WTA")})
        for day in range(7):
            for tour in ("ATP", "WTA"):
                assert sorted(count for (d, t, _), count in keys.items() if (d, t) == (day, tour)) == [1, 1, 2, 2, 2, 2, 2]
    else:
        assert daily_tours == Counter({(day, "ATP"): 70_000 for day in range(7)})
        assert consumers == Counter({(day, "ATP"): 24 for day in range(7)})
        for day in range(7):
            assert sorted(count for (d, t, _), count in keys.items() if (d, t) == (day, "ATP")) == [1, 1, 1, 1] + [2] * 10


@pytest.mark.parametrize("kind", ["atp-heavy", "mixed", "burst"])
def test_consumers_are_inside_daily_total_and_have_exact_prediction_clocks(kind):
    profile = _profile(kind)
    descriptors = profile.consumers()
    assert type(descriptors) is tuple and len(descriptors) == 168
    schedule_consumers = {entry.ordinal: entry for entry in profile.iter_schedule() if entry.consumer_index is not None}
    assert set(schedule_consumers) == {descriptor.ordinal for descriptor in descriptors}

    grouped = Counter()
    for descriptor in descriptors:
        assert type(descriptor) is GrowthConsumerDescriptor
        entry = schedule_consumers[descriptor.ordinal]
        assert entry.day_ordinal >= 70_000 - 24
        assert entry.tour == descriptor.tour
        assert entry.observed_at == descriptor.observed_at
        scheduled_start = datetime.fromisoformat(descriptor.native_fixture["date"].replace("Z", "+00:00"))
        assert descriptor.observed_at <= descriptor.cutoff < scheduled_start
        assert descriptor.created_at >= descriptor.cutoff
        assert descriptor.grouping_slug == ("mens-singles" if descriptor.tour == "ATP" else "womens-singles")
        expected = {
            "ATP": ("901-2026", "Clay", 5, True),
            "WTA": ("902-2026", "Grass", 3, False),
        }[descriptor.tour]
        assert (descriptor.tournament_id, descriptor.surface, descriptor.best_of, descriptor.indoor) == expected
        grouped[descriptor.day_index, descriptor.tour, descriptor.cutoff] += 1
    assert len(grouped) == 98
    assert sum(count == 2 for count in grouped.values()) == (70 if kind == "mixed" else 70)
    assert sum(count == 1 for count in grouped.values()) == 28


def test_non_burst_is_chronological_and_burst_has_real_ties_and_backward_transitions():
    for kind in ("atp-heavy", "mixed"):
        previous = None
        for entry in _profile(kind).iter_schedule():
            if previous is not None:
                assert previous < entry.observed_at
            previous = entry.observed_at

    profile = _profile("burst")
    clocks = {day: Counter() for day in range(7)}
    transitions = {day: [] for day in range(7)}
    previous = {day: None for day in range(7)}
    for entry in profile.iter_schedule():
        clocks[entry.day_index][entry.observed_at] += 1
        prior = previous[entry.day_index]
        if prior is not None and entry.observed_at < prior:
            transitions[entry.day_index].append(entry.day_ordinal - 1)
        previous[entry.day_index] = entry.observed_at
    for day in range(7):
        assert list(clocks[day].values()) == [7_000] * 10
        assert transitions[day] == [13_999, 27_999, 41_999, 55_999]
        assert len({descriptor.cutoff for descriptor in profile.consumers() if descriptor.day_index == day}) == 14
        assert all(descriptor.observed_at == START + timedelta(days=day, seconds=9)
                   for descriptor in profile.consumers() if descriptor.day_index == day)


@pytest.mark.parametrize("kind", ["atp-heavy", "mixed", "burst"])
def test_representative_and_every_consumer_receipt_use_real_status_validation(kind):
    profile = _profile(kind)
    consumers = {descriptor.ordinal: descriptor for descriptor in profile.consumers()}
    ordinals = sorted({0, 6_999, 7_000, 69_975, 69_976, 69_999, 70_000, 489_999, *consumers})
    for ordinal in ordinals:
        [(record, observed_at)] = list(profile.iter_receipts(start=ordinal, stop=ordinal + 1))
        decoded = _physically_decode(record, observed_at)
        assert decoded["payload"]["status"] == "scheduled"
        assert decoded["payload"]["issues"] == []
        assert decoded["payload"]["workload_receipts"] == []
        assert decoded["observed_at"] == canonical_timestamp(observed_at)
        if ordinal in consumers:
            descriptor = consumers[ordinal]
            assert record["event_key"].endswith(":" + str(FIRST_ID + ordinal))
            assert record["payload"]["participant_ids"] == [
                f"espn:tennis:{descriptor.tour}:player:{player['id']}"
                for player in descriptor.native_fixture["competitors"]
            ]


def test_repeatable_slices_and_nested_fixture_mutations_cannot_change_emissions():
    atp = _fixture("ATP")
    profile = build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
        first_native_id=FIRST_ID, atp_fixture=atp, wta_fixture=None)
    wanted = (69_975, 69_976, 69_999, 70_000)
    first = [next(profile.iter_receipts(start=index, stop=index + 1)) for index in wanted]
    atp["competition"]["competitors"][0]["id"] = "999"
    atp["tournament_id"] = "999-2099"
    atp["surface"] = "Grass"
    atp["best_of"] = 5
    atp["indoor"] = True
    first[0][0]["payload"]["participant_ids"][0] = "changed"
    descriptor_fixture = profile.consumers()[0].native_fixture
    descriptor_fixture["competitors"][0]["id"] = "888"
    second = [next(profile.iter_receipts(start=index, stop=index + 1)) for index in wanted]
    third = [next(profile.iter_receipts(start=index, stop=index + 1)) for index in wanted]
    assert second == third
    assert second[0][0]["payload"]["participant_ids"][0] != "changed"
    assert profile.consumers()[0].native_fixture["competitors"][0]["id"] == "11"
    assert (profile.consumers()[0].tournament_id, profile.consumers()[0].surface,
            profile.consumers()[0].best_of, profile.consumers()[0].indoor) == (
                "901-2026", "Hard", 3, None)
    assert [entry.ordinal for entry in islice(profile.iter_schedule(), 69_975, 70_001)] == list(range(69_975, 70_001))
    assert list(profile.iter_receipts(start=12, stop=12)) == []


def test_profile_and_descriptor_shapes_are_frozen_and_storage_is_bounded():
    profile = _profile("mixed")
    assert all(type(seed) is TourSeed for seed in profile.seeds)
    with pytest.raises(FrozenInstanceError):
        profile.kind = "burst"
    with pytest.raises(FrozenInstanceError):
        profile.seeds[0].tour = "WTA"
    with pytest.raises(FrozenInstanceError):
        profile.consumers()[0].tour = "WTA"
    assert not any(type(value) in (list, set) for value in vars(profile).values())
    assert max((len(value) for value in vars(profile).values() if type(value) is tuple), default=0) <= 168
    assert profile.targets.final_receipts_target == 590_553
    assert profile.targets.final_originals_target == 199
    assert profile.targets.final_snapshots_target == 199
    assert profile.targets.final_tour_cutoff_keys_target == 114


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"kind": "small"}, "kind"),
        ({"baseline_sha256": "A" * 64}, "SHA-256"),
        ({"start_at": datetime(2031, 2, 3, 8)}, "UTC"),
        ({"start_at": START.astimezone(timezone(timedelta(hours=1)))}, "UTC"),
        ({"first_native_id": True}, "integer"),
        ({"first_native_id": "7"}, "integer"),
        ({"first_native_id": 0}, "positive"),
        ({"first_native_id": 2**63 - TOTAL_ADDITIONS + 1}, "signed 64-bit"),
        ({"atp_fixture": None}, "ATP"),
    ],
)
def test_invalid_profile_inputs_fail_at_build_time(changes, match):
    values = {"kind": "atp-heavy", "baseline_sha256": BASELINE, "start_at": START,
              "first_native_id": FIRST_ID, "atp_fixture": _fixture("ATP"), "wta_fixture": None}
    values.update(changes)
    with pytest.raises((ContextContractError, TypeError, ValueError), match=match):
        build_growth_profile(**values)


def test_mixed_requires_both_tours_and_malformed_native_seed_fails_before_iteration():
    with pytest.raises((ContextContractError, ValueError), match="WTA"):
        build_growth_profile("mixed", baseline_sha256=BASELINE, start_at=START,
            first_native_id=FIRST_ID, atp_fixture=_fixture("ATP"), wta_fixture=None)
    malformed_status = _fixture("ATP")
    malformed_status["competition"]["status"] = {"type": {"state": "pre"}}
    with pytest.raises((ContextContractError, ValueError), match="scheduled|status|ATP"):
        build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
            first_native_id=FIRST_ID, atp_fixture=malformed_status, wta_fixture=None)
    malformed_players = _fixture("ATP")
    malformed_players["competition"]["competitors"][1]["id"] = malformed_players["competition"]["competitors"][0]["id"]
    with pytest.raises((ContextContractError, ValueError), match="participant|ATP"):
        build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
            first_native_id=FIRST_ID, atp_fixture=malformed_players, wta_fixture=None)


def test_explicit_none_prediction_inputs_are_preserved_without_defaults():
    profile = build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
        first_native_id=FIRST_ID,
        atp_fixture=_fixture("ATP", tournament_id="777-2030", surface=None, best_of=3, indoor=None),
        wta_fixture=None)
    assert {(item.tournament_id, item.surface, item.best_of, item.indoor)
            for item in profile.consumers()} == {("777-2030", None, 3, None)}


@pytest.mark.parametrize("missing", ["competition", "tournament_id", "surface", "best_of", "indoor"])
def test_closed_seed_mapping_rejects_every_missing_field_before_iteration(missing):
    seed = _fixture("ATP")
    del seed[missing]
    with pytest.raises((ContextContractError, TypeError, ValueError), match="seed|fields|mapping"):
        build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
            first_native_id=FIRST_ID, atp_fixture=seed, wta_fixture=None)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("surface", "Sand", "surface"),
        ("surface", 1, "surface"),
        ("best_of", True, "best_of"),
        ("best_of", 4, "best_of"),
        ("indoor", 0, "indoor"),
        ("tournament_id", "invalid", "scheduled|tournament"),
    ],
)
def test_closed_seed_mapping_rejects_invalid_explicit_inputs_before_iteration(field, value, match):
    seed = _fixture("ATP")
    seed[field] = value
    with pytest.raises((ContextContractError, TypeError, ValueError), match=match):
        build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
            first_native_id=FIRST_ID, atp_fixture=seed, wta_fixture=None)


def test_closed_seed_mapping_rejects_unknown_fields_before_iteration():
    seed = _fixture("ATP")
    seed["grouping_slug"] = "mens-singles"
    with pytest.raises((ContextContractError, TypeError, ValueError), match="seed|fields|mapping"):
        build_growth_profile("atp-heavy", baseline_sha256=BASELINE, start_at=START,
            first_native_id=FIRST_ID, atp_fixture=seed, wta_fixture=None)


@pytest.mark.parametrize("start,stop", [(-1, None), (0, 490_001), (2, 1), (False, 1), (0, True), (1.0, 2)])
def test_invalid_slice_indices_fail_before_returning_an_iterator(start, stop):
    profile = _profile("atp-heavy")
    with pytest.raises((TypeError, ValueError), match="slice|index|integer|range"):
        profile.iter_receipts(start=start, stop=stop)


def test_clock_overflow_is_rejected_when_profile_is_built():
    with pytest.raises((ContextContractError, ValueError), match="clock|range|overflow"):
        build_growth_profile("atp-heavy", baseline_sha256=BASELINE,
            start_at=datetime.max.replace(tzinfo=timezone.utc), first_native_id=FIRST_ID,
            atp_fixture=_fixture("ATP"), wta_fixture=None)
