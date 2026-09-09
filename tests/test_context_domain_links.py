"""Optional immutable B3 references; legacy records retain their exact shape."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json

import pytest

from test_riskobet_domain import _snapshot
from test_riskobet_store import _run, _candidate


def reference(key="a", payload="b"):
    from context_links import ContextReference
    return ContextReference(key * 64, payload * 64)


def test_reference_is_closed_immutable_and_returns_detached_json():
    from context_links import ContextReference
    ref = reference()
    data = ref.to_dict()
    assert ContextReference.from_dict(data) == ref
    data["key"] = "f" * 64
    assert ref.to_dict()["key"] == "a" * 64
    with pytest.raises(FrozenInstanceError):
        ref.key = "c" * 64


@pytest.mark.parametrize("field,value", [("schema", True), ("kind", "unknown"),
    ("key", "a" * 63), ("payload_digest", "G" * 64), ("price", 2.)])
def test_reference_rejects_noncanonical_or_extra_claims(field, value):
    from context_links import ContextReference
    data = reference().to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        ContextReference.from_dict(data)


def test_legacy_snapshot_id_and_json_remain_byte_compatible():
    from riskobet_domain import _stable_id
    old = _snapshot()
    explicit = replace(old, context_ref=None)
    assert old.snapshot_id == _stable_id("snapshot", old.event_key, old.model_version, old.input_hash)
    assert old.to_dict() == explicit.to_dict()
    assert "context_ref" not in old.to_dict()


def test_snapshot_reference_changes_identity_without_changing_old_rows():
    old = _snapshot()
    original = old.to_dict()
    first = replace(old, context_ref=reference())
    changed_input = replace(old, context_ref=reference("c"))
    changed_payload = replace(old, context_ref=reference(payload="d"))
    assert len({old.snapshot_id, first.snapshot_id, changed_input.snapshot_id, changed_payload.snapshot_id}) == 4
    assert first.to_dict()["context_ref"] == reference().to_dict()
    assert old.to_dict() == original
    with pytest.raises(ValueError):
        replace(old, context_ref=reference().to_dict())


def test_new_and_old_riskobet_snapshots_coexist_and_roundtrip_ui(tmp_path):
    from riskobet_store import RiskBetStore, FrozenRevisionError
    from riskobet_domain import canonical_input_hash
    from riskobet_ui import _snapshot as read_snapshot
    old = _snapshot()
    # A different context is a different model input. The existing unique
    # event/model/input constraint must still reject a mislabeled old hash.
    new = replace(old, context_ref=reference(), input_hash=canonical_input_hash({
        "original_input_hash": old.input_hash, "context_ref": reference().to_dict()}))
    store = RiskBetStore(tmp_path / "risk.db", tmp_path / "latest.json")
    store.append_run(_run(old, _candidate(old), minute=1))
    mislabeled = replace(old, context_ref=reference())
    with pytest.raises(FrozenRevisionError):
        store.append_run(_run(mislabeled, _candidate(mislabeled), minute=2))
    store.append_run(_run(new, _candidate(new), minute=2))
    assert read_snapshot(old.to_dict()).to_dict() == old.to_dict()
    assert read_snapshot(new.to_dict()).to_dict() == new.to_dict()
    for payload in (old.to_dict(), new.to_dict()):
        assert store._verified_snapshot_row({
            "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "content_hash": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            **{name: payload[name] for name in ("snapshot_id", "event_key", "sport", "model_version", "input_hash", "modeled_at")},
        }) == payload


def test_ui_cannot_attach_reference_to_old_snapshot_identity():
    from riskobet_ui import _snapshot as read_snapshot, RiskBetViewError
    old = _snapshot().to_dict()
    old["context_ref"] = reference().to_dict()
    with pytest.raises(RiskBetViewError):
        read_snapshot(old)


def test_model_signal_optional_reference_survives_normal_projection_only_when_present():
    from ev_signal_sources import ModelSignal
    from wettfinder_automation import _signal_record
    old = ModelSignal(key="tennis-one", label="Alpha vs Beta", probability=.6,
                      probability_haircut=.1, evidence_stage="SHADOW", policy_version="test-v1",
                      detail="Modell", sport="Tennis")
    old_record = _signal_record(old)
    linked = _signal_record(replace(old, context_ref=reference()))
    assert "context_ref" not in old_record
    assert linked.pop("context_ref") == reference().to_dict()
    assert linked == old_record
    with pytest.raises(ValueError):
        replace(old, context_ref={"key": "a" * 64})


@pytest.mark.parametrize("field", [None, "payload_digest", "schema"])
def test_published_normal_model_and_price_overlay_keep_same_reference(tmp_path, field):
    from datetime import datetime, timezone
    from ev_signal_sources import automated_wettfinder_forecasts, automated_wettfinder_signals
    from test_ev_signal_sources import _playable_automatic_candidate, _model_overlay, _automatic_document
    strict = _playable_automatic_candidate()
    strict["context_ref"] = reference().to_dict()
    if field == "payload_digest":
        strict["context_ref"][field] = "wrong"
    elif field == "schema":
        strict["context_ref"][field] = True
    document = _automatic_document([_model_overlay(strict)], candidates=[strict])
    path = tmp_path / "normal.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    now = datetime(2030, 1, 1, 10, 1, tzinfo=timezone.utc)
    for reader in (automated_wettfinder_forecasts, automated_wettfinder_signals):
        signals = reader(path, now=now)
        if field is not None:
            assert signals == []
        else:
            assert len(signals) == 1
            assert signals[0].context_ref == reference()
