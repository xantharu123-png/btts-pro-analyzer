"""Single-call derivation and fresh proof checks, with real owning validation."""
from collections import Counter
from copy import deepcopy

import pytest

import context_models.contracts as contracts
import context_sources.tennis_status as status
from model_artifacts import canonical_bytes
from test_context_runtime_capacity import encoded_history_fixture
from test_context_runtime_receipt_witness import prepared
from test_context_tennis_capture import competition, records


def selected(content):
    clock = "2026-09-09T11:00:00.000000Z"
    content_digest = contracts.digest(content)
    return {**deepcopy(content), "observed_at": clock, "content_digest": content_digest,
        "digest": contracts.digest({"content_digest": content_digest, "observed_at": clock}),
        "evidence_class": "prospective", "effective_at": clock, "publication_resolution": None}


NATIVE_CASES = [
    ({}, {}, "completed"),
    ({"status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}}}, {}, "scheduled"),
    ({"status": {"type": {"state": "in", "name": "STATUS_IN_PROGRESS", "completed": False}}}, {}, "started"),
    ({"status": None}, {}, "unknown"),
    ({"status": {"type": {"state": "post", "name": "STATUS_FINAL", "completed": "true"}}}, {}, "unknown"),
    ({"notes": [{"text": "retired"}]}, {}, "completed"),
    ({"notes": [{"text": "walkover"}]}, {}, "completed"),
    ({"notes": [{"text": "retired walkover"}]}, {}, "unknown"),
    ({"competitors": []}, {}, "completed"),
    ({"competitors": [{"id": "1"}, {"id": "1"}]}, {}, "completed"),
    ({"date": None}, {}, "completed"),
    ({}, {"tournament": None}, "completed"),
    ({}, {"slug": "mens-doubles"}, "completed"),
    ({}, {"slug": None}, "completed"),
    ({}, {"tour": "WTA", "slug": "womens-singles"}, "completed"),
] + [
    ({"status": {"type": {"state": "post", "name": name, "completed": True}}}, {}, outcome)
    for name, outcome in [("STATUS_CANCELED", "cancelled"), ("STATUS_CANCELLED", "cancelled"),
        ("STATUS_ABANDONED", "unknown"), ("STATUS_DEFAULTED", "unknown"), ("STATUS_OTHER", "unknown")]
]


@pytest.mark.parametrize("changes,kwargs,want", NATIVE_CASES)
def test_native_variants_keep_closed_envelope_and_workload_owner(changes, kwargs, want):
    contents = records(competition(**changes), **kwargs)
    row = selected(contents[0])
    original = canonical_bytes(row)
    assert status.validate_tennis_status_record(row)["status"] == want
    assert status._validate_selected_tennis_receipt_cold(row) is row
    assert canonical_bytes(row) == original
    for content in contents[1:]:
        work = selected(content)
        assert status._validate_selected_tennis_receipt_cold(work) is work
        assert work["kind"] == "workload"


class DictAlias(dict): pass
class ListAlias(list): pass
class TupleAlias(tuple): pass
class StrAlias(str): pass
class IntAlias(int): pass
class FloatAlias(float): pass


INVALID_FIELDS = [
    (("payload",), DictAlias),
    (("payload", "participant_ids"), tuple),
    (("payload", "participant_ids"), TupleAlias),
    (("payload", "participant_ids"), ListAlias),
    (("payload", "issues"), tuple),
    (("payload", "workload_receipts"), tuple),
    (("payload", "native_status"), DictAlias),
    (("payload", "tour"), StrAlias),
    (("payload", "native_status", "completed"), lambda _: IntAlias(1)),
    (("payload", "native_status", "completed"), lambda _: FloatAlias(1.0)),
    (("payload", "native_status", "completed"), lambda _: 1),
    (("payload", "native_status", "retired"), lambda _: 0.0),
    (("payload", "native_status", "retired"), lambda _: -0.0),
    (("payload", "tournament_id"), lambda _: True),
    (("payload", "tournament_id"), lambda _: float("nan")),
    (("payload", "tournament_id"), lambda _: float("inf")),
    (("payload", "tournament_id"), lambda _: float("-inf")),
    (("payload", "tournament_id"), lambda _: "0189"),
    (("payload", "tour"), lambda _: "WTA"),
    (("payload", "scheduled_start"), lambda _: "2026-09-08T18:00Z"),
    (("payload", "grouping_slug"), lambda _: "mens-doubles"),
    (("payload", "status"), lambda _: "started"),
    (("payload", "issues"), lambda _: ["invalid-status"]),
    (("payload", "workload_receipts"), lambda _: ["0"*64]),
    (("payload", "competition_revision"), lambda _: "0"*64),
    (("source",), lambda _: "other"), (("source_schema",), lambda _: "unknown"),
    (("sport",), lambda _: "football"), (("format",), lambda _: "doubles"),
    (("event_key",), lambda _: "espn:tennis:WTA:match:101"),
    (("subject_id",), lambda _: "espn:tennis:ATP:match:202"),
    (("competition",), lambda _: "espn:ATP:tournament:999"),
    (("kind",), lambda _: "workload"), (("complete",), lambda _: True),
    (("complete",), lambda _: 0), (("source_revision",), lambda _: "0"*64),
    (("schedule_revision",), lambda _: "0"*64),
    (("valid_from",), lambda _: "2026-09-09T10:00:00.000000Z"),
    (("valid_until",), lambda _: "2026-09-09T12:00:00.000000Z"),
    (("published_at",), lambda _: "2026-09-09T10:00:00.000000Z"),
    (("publication_proof",), lambda _: {}),
]


def invalid_rows():
    """Also consumed by the development-only immutable-899 differential run."""
    original = records()[0]
    for index, (path, change) in enumerate(INVALID_FIELDS):
        content = deepcopy(original)
        parent = content
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = change(parent[path[-1]])
        # Invalid finite values get newly computed B1 hashes: source validation
        # cannot rely on an earlier digest mismatch to reject them.
        try:
            row = selected(content)
        except ValueError:  # Non-finite JSON cannot receive a real content hash.
            row = selected(original)
            row["payload"] = content["payload"]
        yield str(index)+":"+".".join(path), row
    for container in ((), ("payload",), ("payload", "native_status")):
        for mutation in ("missing", "extra", "key-alias"):
            row = selected(original)
            parent = row
            for key in container:
                parent = parent[key]
            key = "complete" if not container else next(iter(parent))
            if mutation == "missing": del parent[key]
            elif mutation == "extra": parent["unexpected"] = None
            else: parent[StrAlias(key)] = parent.pop(key)
            yield repr(container)+mutation, row


@pytest.mark.parametrize("name,row", list(invalid_rows()))
def test_malformed_content_never_becomes_an_accepted_selected_receipt(name, row):
    with pytest.raises((contracts.ContextContractError, KeyError)):
        status._validate_selected_tennis_receipt_cold(deepcopy(row))
    # The public standalone validator has never owned transport-object keys.
    if name not in {"()extra", "()key-alias"}:
        with pytest.raises((contracts.ContextContractError, KeyError)):
            status.validate_tennis_status_record(deepcopy(row))


@pytest.mark.parametrize("field,value,accepted", [
    ("evidence_class", "archive", False), ("effective_at", "2026-09-09T10:00:00.000000Z", False),
    ("publication_resolution", {}, False), ("digest", "0"*64, False), ("content_digest", "0"*64, False),
    ("evidence_class", StrAlias("prospective"), True),
])
def test_transport_fields_keep_their_distinct_owner(field, value, accepted):
    row = selected(records()[0])
    row[field] = value
    assert status.validate_tennis_status_record(row)["status"] == "completed"
    if accepted:
        assert status._validate_selected_tennis_receipt_cold(row) is row
    else:
        with pytest.raises(contracts.ContextContractError):
            status._validate_selected_tennis_receipt_cold(row)


@pytest.mark.parametrize("value", ["2026-09-09T11:00Z", "2026-09-09T12:00:00.000000Z",
    "bad-clock", StrAlias("2026-09-09T11:00:00.000000Z"), True])
def test_changed_or_noncanonical_receipt_clock_cannot_reuse_envelope(value):
    row = selected(records()[0])
    row["observed_at"] = value
    with pytest.raises(contracts.ContextContractError):
        status._validate_selected_tennis_receipt_cold(row)


def test_standalone_still_normalizes_expected_payload(monkeypatch):
    row = selected(records()[0])
    normalize, calls = status.normalize_observation, []
    def counted(content, **kwargs):
        calls.append(canonical_bytes(content))
        return normalize(content, **kwargs)
    monkeypatch.setattr(status, "normalize_observation", counted)
    assert status.validate_tennis_status_record(row)["status"] == "completed"
    assert len(calls) == 1


def test_selected_status_derives_once_without_changing_content(encoded_history_fixture, monkeypatch):
    _, _, _, rows, _ = prepared(encoded_history_fixture)
    row = deepcopy(rows[0])
    expected = canonical_bytes(row)
    normalizations, encodings = [], []
    normalize = status.normalize_observation
    encode = canonical_bytes

    def counted_normalize(content, **kwargs):
        normalizations.append(encode(content))
        return normalize(content, **kwargs)

    def counted_encode(content):
        raw = encode(content)
        encodings.append(raw)
        return raw

    monkeypatch.setattr(status, "normalize_observation", counted_normalize)
    monkeypatch.setattr(status, "canonical_bytes", counted_encode)
    monkeypatch.setattr(contracts, "canonical_bytes", counted_encode)
    assert status._validate_selected_tennis_receipt_cold(row) is row
    assert canonical_bytes(row) == expected
    content = encode({key: row[key] for key in contracts.OBSERVATION_FIELDS})
    assert (normalizations.count(content), encodings.count(content)) == (1, 3)


def test_completed_proof_boundary_reads_each_schema_once(encoded_history_fixture):
    conn, receipts, _, _, cache = prepared(encoded_history_fixture)
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        cache._check_selected_proof(receipts)
    finally:
        conn.set_trace_callback(None)
    assert Counter(statements) == Counter({"PRAGMA main.schema_version": 1, "PRAGMA temp.schema_version": 1})
