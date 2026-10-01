"""Offline synthetic connection mechanics; not predictive-quality evidence."""
from copy import deepcopy
from datetime import timedelta
import shutil
import sqlite3

import pytest

import football_joint_worker as worker
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_training_helpers import NOW
from test_football_joint_training import source_case


@pytest.fixture(scope="module")
def original_case(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        import context_training_helpers as support
        full_detail = support.detail
        def reported_cohort(*args, **kwargs):
            raw = full_detail(*args, **kwargs)
            # A deliberately small explicitly reported synthetic cohort. This
            # is not promoted to a real complete eleven-player starting lineup.
            for block in raw["players"]:
                block["players"] = block["players"][:1]
            return raw
        patch.setattr(support, "detail", reported_cohort)
        return source_case(tmp_path_factory.mktemp("joint-worker-original"), patch)


@pytest.fixture
def isolated(original_case, tmp_path):
    source, case, config = deepcopy(original_case)
    target = tmp_path / "context.db"
    shutil.copyfile(source, target)
    return target, case, config


def fitted(isolated, *, names=None, published_at=None, second=False):
    from model_artifacts import put_artifact, publish_slots
    path, case, config = isolated
    names = names or ["schedule.gap_hours_home"]
    head = dict(link="log_joint_tilt", scale=[1.] * len(names), coef=[.01] * len(names), alpha=1., n_rows=3)
    effect = dict(schema=1, heads={"home": head, "away": head},
        training_end="2026-08-01T00:00:00.000000Z", training_refs_hash="b" * 64,
        **{key: config[key] for key in ("sport", "family", "feature_version", "feature_names",
            "preprocessing_artifacts", "joint_calibration", "population", "coverage", "model_variant")})
    effect["feature_names"] = names
    created = NOW + timedelta(seconds=2)
    effect_hash = put_artifact(path, kind="context-effect-v1", payload=effect, created_at=created)
    slots = {"context-effect:football:goals": effect_hash}
    if second:
        effect["training_refs_hash"] = "c" * 64
        slots["context-effect:football:other"] = put_artifact(path, kind="context-effect-v1", payload=effect, created_at=created)
    publish_slots(path, slots, expected_manifest=None, published_at=published_at or created)
    return effect_hash


def compare(isolated, *, later=2, **kwargs):
    path, case, _ = isolated
    return worker.publish_joint_comparison(path, case["case"]["payload"]["replay_ref"],
        decision_at=NOW + timedelta(minutes=later), **kwargs)


def snapshots(path):
    with sqlite3.connect(path) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='context_snapshots'").fetchone():
            return []
        return con.execute("SELECT key,payload,payload_digest FROM context_snapshots ORDER BY key").fetchall()


def test_absent_fitted_effect_preserves_database_and_never_fabricates_effect(isolated, monkeypatch):
    path, case, _ = isolated
    before = path.read_bytes()
    def forbidden(*_args, **_kwargs):
        pytest.fail("absent effect must not publish or fetch")
    monkeypatch.setattr(worker, "compute_once", forbidden)
    monkeypatch.setattr(worker, "_load_publication", forbidden)
    monkeypatch.setattr(worker, "joint_features", forbidden)
    monkeypatch.setattr("requests.get", forbidden)
    result = compare(isolated)
    assert result["status"] == "effect-unavailable"
    assert result["role"] == "not_applied" and result["reference"] is None
    assert "available_features" not in result  # No need to expand unused originals.
    assert path.read_bytes() == before and snapshots(path) == []


def test_fitted_unqualified_model_is_internal_and_baseline_stays_exact(isolated, monkeypatch):
    from context_models.dataset import _reader
    from context_snapshots import _decode_snapshot
    from context_snapshot_storage import freeze_reference_bytes
    path, case, _ = isolated
    fitted(isolated)
    monkeypatch.setattr("requests.get", lambda *_a, **_k: pytest.fail("source fetch forbidden"))
    first = compare(isolated)
    assert first["status"] == "comparison-stored" and first["role"] == "experimental", first
    assert first["decision_at"] == canonical_timestamp(NOW + timedelta(minutes=2))
    assert first["reference"] is not None and len(snapshots(path)) == 2
    key = first["reference"]["key"]
    with _reader(path) as con:
        saved = con.execute("SELECT payload,payload_digest FROM context_snapshots WHERE key=?", (key,)).fetchone()
        payload = _decode_snapshot(key, *saved, reference_data=freeze_reference_bytes(saved[0], con))
    result = payload["result"]
    assert result["used_markets"] == result["base_markets"] == case["case"]["payload"]["base"]["markets"]
    assert result["used_params"] == result["base_params"]
    assert result["comparison_markets"] != result["base_markets"]
    assert not result["certified_markets"] and result["approval_hash"] is None


def test_identical_sources_at_later_clock_reuse_first_actual_decision(isolated, monkeypatch):
    fitted(isolated)
    first = compare(isolated)
    stored = snapshots(isolated[0])
    def forbidden(**_kwargs):
        pytest.fail("unchanged revision must not rerun joint numerical comparison")
    monkeypatch.setattr(worker, "calculate_context_payload", forbidden)
    later = compare(isolated, later=12)
    assert later == first and snapshots(isolated[0]) == stored


def test_real_later_weather_revision_creates_new_context_not_backdated(isolated):
    from context_observations import append_observation
    from context_sources.openweather import forecast_payload, normalize_forecast
    from datetime import datetime
    path, case, _ = isolated
    fitted(isolated)
    first = compare(isolated)
    event = case["case"]["payload"]["event"]
    observed = NOW + timedelta(minutes=3)
    point = forecast_payload(event, city="Example", country="GB", latitude=50., longitude=0.,
        point={"dt": datetime.fromisoformat(event["scheduled_start"]).timestamp(),
               "main": {"temp": 18.}, "wind": {"speed": 4.}})
    append_observation(path, normalize_forecast(point, observed_at=observed), observed_at=observed)
    later = compare(isolated, later=4)
    assert later["reference"] != first["reference"]
    assert later["decision_at"] == canonical_timestamp(NOW + timedelta(minutes=4))
    assert first["decision_at"] == canonical_timestamp(NOW + timedelta(minutes=2))
    assert later["available_features"] > first["available_features"]
    assert len(snapshots(path)) == 4


def test_missing_consumed_weather_feature_leaves_no_database_growth(isolated):
    fitted(isolated, names=["weather.temperature_c"])
    before = isolated[0].read_bytes()
    result = compare(isolated)
    assert result["status"] == "effect-features-unavailable" and result["reference"] is None
    assert isolated[0].read_bytes() == before and snapshots(isolated[0]) == []


@pytest.mark.parametrize("field,reason", [("MAX_SOURCE_RECEIPTS", "joint_source_receipt_bound_exceeded"),
                                         ("MAX_SOURCE_BYTES", "joint_source_byte_bound_exceeded")])
def test_source_bound_declines_before_unbounded_body_materialization(isolated, monkeypatch, field, reason):
    fitted(isolated)
    monkeypatch.setattr(worker, field, 1)
    monkeypatch.setattr(worker, "_decode_receipt", lambda *_a, **_k: pytest.fail("too-large pool must not be decoded"))
    monkeypatch.setattr(worker, "compute_once", lambda *_a, **_k: pytest.fail("too-large pool must not publish"))
    before = isolated[0].read_bytes()
    result = compare(isolated)
    assert result["status"] == "source-unavailable" and result["reason"] == reason
    assert result["reference"] is None and isolated[0].read_bytes() == before


@pytest.mark.parametrize("variant", ["ambiguous", "future_manifest"])
def test_nonunique_or_late_fit_does_not_get_applied(isolated, variant):
    fitted(isolated, second=variant == "ambiguous",
           published_at=NOW + timedelta(minutes=3) if variant == "future_manifest" else None)
    before = isolated[0].read_bytes()
    result = compare(isolated)
    assert result["status"] == ("effect-ambiguous" if variant == "ambiguous" else "effect-after-decision")
    assert result["role"] == "not_applied" and isolated[0].read_bytes() == before


def test_source_revision_changed_before_current_decision_does_not_reuse_old_target(isolated):
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    from context_training_helpers import detail
    path, case, _ = isolated
    fitted(isolated)
    event = case["case"]["payload"]["event"]
    raw = detail(9000, NOW + timedelta(hours=4), terminal="NS")
    observed = NOW + timedelta(minutes=1)
    append_observation(path, normalize_football_base_input(raw, observed_at=observed), observed_at=observed)
    result = compare(isolated)
    assert result["status"] == "source-unavailable"
    assert result["reference"] is None and result["role"] == "not_applied"


@pytest.mark.parametrize("value", [True, 0, -1, worker.MAX_EVENT_BYTES + 1])
def test_event_payload_budget_is_finite(isolated, value):
    with pytest.raises(ContextContractError):
        compare(isolated, max_payload_bytes=value)


def test_small_budget_cannot_write_oversized_revision(isolated):
    fitted(isolated)
    before = isolated[0].read_bytes()
    result = compare(isolated, max_payload_bytes=100)
    assert result["status"] == "payload-budget-exhausted" and result["reference"] is None
    assert isolated[0].read_bytes() == before


def test_complete_payload_oversize_is_detected_before_pointer_write(isolated, monkeypatch):
    fitted(isolated)
    actual = worker.calculate_context_payload
    def large(**kwargs):
        payload = actual(**kwargs)
        payload["_deliberate_test_padding"] = "x" * worker.MAX_EVENT_BYTES
        return payload
    monkeypatch.setattr(worker, "calculate_context_payload", large)
    monkeypatch.setattr(worker, "compute_once", lambda *_a, **_k: pytest.fail("oversize must perform zero writes"))
    before = isolated[0].read_bytes()
    result = compare(isolated)
    assert result["status"] == "payload-budget-exhausted" and result["required_payload_bytes"] > worker.MAX_EVENT_BYTES
    assert isolated[0].read_bytes() == before


def test_invalid_pointer_is_not_treated_as_new_or_missing_data(isolated):
    fitted(isolated)
    compare(isolated)
    with sqlite3.connect(isolated[0]) as con:
        rows = con.execute("SELECT key,payload FROM context_snapshots").fetchall()
        pointer = next(key for key, value in rows if worker.POINTER_KIND.encode() in value)
        con.execute("UPDATE context_snapshots SET payload=? WHERE key=?", (b"{}", pointer))
    with pytest.raises(ContextIntegrityError):
        compare(isolated, later=12)


def test_batch_no_effect_report_does_not_write_or_reserve_storage(isolated):
    path, case, _ = isolated
    binding = case["case"]["payload"]["replay_ref"]
    report = {"schema": 1, "scope": "football-final-same-call-originals", "published_count": 1,
        "inserted_payload_bytes": 0, "source_inserted_payload_bytes": 0,
        "events": [{"target_record": "a" * 64, "binding_ref": binding, "status": "captured",
                    "inserted_payload_bytes": 0, "source_state": "captured",
                    "code_state": "execution-fingerprint-only", "empirical_state": "not-evaluated",
                    "unavailable_reason": None}]}
    before = path.read_bytes()
    result = worker.publish_joint_capture_report(path, report, decision_at=NOW + timedelta(minutes=2))
    assert len(result["events"]) == 1 and result["reserved_payload_bytes"] == 0
    assert result["unprocessed_events"] == 0 and path.read_bytes() == before
    assert worker.joint_comparison_report_fields({"football_joint_comparison": result}) == {"football_joint_comparison": result}


def capture_report(bindings):
    rows = [{"target_record": "a" * 64, "binding_ref": ref, "status": "captured",
             "inserted_payload_bytes": 0, "source_state": "captured",
             "code_state": "execution-fingerprint-only", "empirical_state": "not-evaluated",
             "unavailable_reason": None} for ref in bindings]
    return {"schema": 1, "scope": "football-final-same-call-originals", "published_count": len(rows),
            "inserted_payload_bytes": 0, "source_inserted_payload_bytes": 0, "events": rows}


def test_batch_reservation_is_finite_even_for_many_fitted_revisions(monkeypatch):
    visited = []
    def publish(_path, binding, **kwargs):
        visited.append((binding, kwargs["max_payload_bytes"]))
        return {"status": "comparison-stored"}
    monkeypatch.setattr(worker, "publish_joint_comparison", publish)
    refs = [f"{i:064x}" for i in range(1, 50)]
    result = worker.publish_joint_capture_report("unused.db", capture_report(refs), decision_at=NOW)
    assert len(visited) == 2 and result["reserved_payload_bytes"] == worker.MAX_RUN_BYTES
    assert result["unprocessed_events"] == 47
    assert all(allowance == worker.MAX_EVENT_BYTES for _, allowance in visited)


def test_started_original_is_skipped_and_future_sibling_completes(isolated, tmp_path):
    import context_training_helpers as support
    path, old_case, _ = isolated
    full_detail = support.detail
    def later_target(*args, **kwargs):
        raw = full_detail(*args, **kwargs)
        if raw["fixture"]["id"] == 9100:
            from datetime import datetime
            raw["fixture"]["date"] = canonical_timestamp(datetime.fromisoformat(raw["fixture"]["date"]) + timedelta(hours=1))
        for block in raw["players"]:
            block["players"] = block["players"][:1]
        return raw
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(support, "detail", later_target)
        other, later_case, _ = source_case(tmp_path / "later", patch, event_id=9100)
    with sqlite3.connect(path) as connection:
        connection.execute("ATTACH DATABASE ? AS incoming", (str(other),))
        for table in ("artifacts", "context_contents", "context_observations"):
            connection.execute(f"INSERT OR IGNORE INTO main.{table} SELECT * FROM incoming.{table}")
    fitted(isolated)
    refs = [case["case"]["payload"]["replay_ref"] for case in (old_case, later_case)]
    result = worker.publish_joint_capture_report(path, capture_report(refs), decision_at=NOW + timedelta(minutes=121))
    assert result["events"][0]["status"] == "source-unavailable"
    assert result["events"][0]["reason"] == "context_decision_not_prematch"
    assert result["events"][1]["status"] == "comparison-stored"
    assert result["events"][1]["role"] == "experimental"
    assert result["unprocessed_events"] == 0
    assert worker.joint_comparison_report_fields({"football_joint_comparison": result})["football_joint_comparison"] == result


def test_empty_batch_still_requires_aware_worker_decision(monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(worker, "publish_joint_comparison", lambda *_a, **_k: pytest.fail("must not run"))
    with pytest.raises(ContextContractError):
        worker.publish_joint_capture_report("unused.db", capture_report([]), decision_at=datetime(2026, 9, 9))


@pytest.mark.parametrize("field,value", [("schema", True), ("reserved_payload_bytes", True),
                                       ("unprocessed_events", -1), ("events", [None])])
def test_admin_report_rejects_unbounded_or_malformed_fields(field, value):
    report = {"schema": 1, "scope": "football-post-capture-internal-joint-comparison",
              "events": [], "unprocessed_events": 0, "reserved_payload_bytes": 0}
    report[field] = value
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        worker.joint_comparison_report_fields({"football_joint_comparison": report})


def test_admin_report_never_accepts_an_activation_claim():
    row = {"status": "effect-unavailable", "role": "applied", "binding_ref": "a" * 64, "reference": None}
    report = {"schema": 1, "scope": "football-post-capture-internal-joint-comparison",
              "events": [row], "unprocessed_events": 0, "reserved_payload_bytes": 0}
    with pytest.raises(ContextContractError):
        worker.joint_comparison_report_fields({"football_joint_comparison": report})


@pytest.mark.parametrize("kwargs", [{"max_events": True}, {"max_events": 33}, {"max_run_bytes": True},
                                   {"max_run_bytes": worker.MAX_RUN_BYTES + 1}])
def test_batch_bounds_rejected_before_any_io(kwargs, monkeypatch):
    monkeypatch.setattr(worker, "publish_joint_comparison", lambda *_a, **_k: pytest.fail("must not run"))
    with pytest.raises(ContextContractError):
        worker.publish_joint_capture_report("missing.db", {}, decision_at=NOW, **kwargs)
