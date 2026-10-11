"""Physical zero-copy validation stays equivalent to canonical normalization."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import context_observations as observations
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    normalize_observation, _validate_canonical_observation_content,
)
from model_artifacts import canonical_bytes
from test_context_observations import normalized_record


NOW = datetime(2026, 10, 11, 8, tzinfo=timezone.utc)
CLOCK = canonical_timestamp(NOW)


def content():
    return normalize_observation(normalized_record(
        valid_from=CLOCK,
        payload={"status": "out", "source": {"plain": [None, False, 0, -0.0, 1.25, "é"]}},
        publication_proof={"locator": "archive:123", "published": CLOCK},
    ), observed_at=NOW)


def physical(record, *, clock=CLOCK):
    ref = digest(record)
    return (digest({"content_digest": ref, "observed_at": clock}), ref,
        record["event_key"], clock, record["schedule_revision"], record["source"],
        record["subject_id"], record["kind"], canonical_bytes(record))


def oracle_accepts(record):
    try:
        normalized = normalize_observation(record, observed_at=NOW)
        return canonical_bytes(record) == canonical_bytes(normalized)
    except (ValueError, TypeError, OverflowError):
        return False


CHANGES = (
    ("published_at", None),
    ("published_at", CLOCK),
    ("published_at", canonical_timestamp(NOW + timedelta(seconds=1))),
    ("published_at", NOW.isoformat()),
    ("published_at", "2026-10-11T08:00:00"),
    ("published_at", 17),
    ("valid_from", NOW.isoformat()),
    ("valid_from", None),
    ("valid_from", "2026-10-11T10:00:00.000000+02:00"),
    ("valid_until", CLOCK),
    ("valid_until", canonical_timestamp(NOW + timedelta(seconds=1))),
    ("valid_until", NOW.isoformat()),
    ("valid_until", 0),
    ("complete", 1),
    ("complete", None),
    ("complete", True),
    ("payload", []),
    ("payload", {"liveOdds": 1.9}),
    ("payload", {"deep": [{"bookmaker2": "x"}]}),
    ("payload", {" blank ": 0}),
    ("payload", {"value": float("inf")}),
    ("payload", {"value": (1, 2)}),
    ("publication_proof", []),
    ("publication_proof", {"price": 1.5}),
    ("subject_id", "player"),
    ("subject_id", " player:1"),
    ("source", ""),
    ("source", "api football"),
    ("sport", "cricket"),
    ("event_key", "api-football:tennis:1"),
    ("format", "90min "),
)


@pytest.mark.parametrize("field,value", CHANGES)
def test_same_normalization_predicates_without_tree_copy(field, value):
    record = content()
    record[field] = value
    unchanged = deepcopy(record)
    if oracle_accepts(record):
        assert _validate_canonical_observation_content(record, receipt=CLOCK) is None
    else:
        with pytest.raises(ContextContractError):
            _validate_canonical_observation_content(record, receipt=CLOCK)
    assert record == unchanged


@pytest.mark.parametrize("field", ["extra", "payload", "event_key"])
def test_closed_schema_is_still_required(field):
    record = content()
    if field == "extra":
        record[field] = "foreign"
    else:
        del record[field]
    assert not oracle_accepts(record)
    with pytest.raises(ContextContractError):
        _validate_canonical_observation_content(record, receipt=CLOCK)


@pytest.mark.parametrize("index,replacement", [
    (0, "0" * 64), (1, "1" * 64), (2, "api-football:football:999"),
    (3, canonical_timestamp(NOW + timedelta(seconds=1))), (4, "other-schedule"),
    (5, "foreign-source"), (6, "player:999"), (7, "other-kind"),
])
def test_each_physical_receipt_hash_and_index_is_checked(index, replacement):
    raw = list(physical(content()))
    raw[index] = replacement
    with pytest.raises(ContextIntegrityError):
        observations._decode_receipt(tuple(raw))


def test_decoded_contents_are_not_shared_between_receipts_or_mutable_caches():
    raw = physical(content())
    expected = observations._decode_receipt(raw)
    changed = observations._decode_receipt(raw)
    changed["payload"]["source"]["plain"].clear()
    changed["publication_proof"]["locator"] = "mutated"
    assert observations._decode_receipt(raw) == expected


def test_noncanonical_payload_fields_still_rejected_even_with_recomputed_hashes():
    record = content()
    record["valid_from"] = NOW.isoformat()
    with pytest.raises(ContextIntegrityError):
        observations._decode_receipt(physical(record))


def test_noncanonical_receipt_is_not_accepted_as_a_content_validation_flag():
    with pytest.raises(ContextContractError):
        _validate_canonical_observation_content(content(), receipt=NOW.isoformat())
