"""Offline native pipeline mechanics; synthetic fixtures are not quality proof."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
import shutil
import sqlite3

import pytest

import context_models.football_readiness as readiness
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_training_helpers import NOW
from test_football_joint_training import native_case, joint_cohort

BLOCKS = tuple((NOW+timedelta(days=day), NOW+timedelta(days=day+2)) for day in (4, 6, 8))


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *_a, **_k: pytest.fail("readiness cannot call a provider"))


def requests(cases):
    return tuple({"binding_ref": case["case"]["payload"]["replay_ref"]} for case in cases)


def isolated(packet, tmp_path):
    db, *other = deepcopy(packet)
    target = tmp_path/"offline-context.db"
    shutil.copyfile(db, target)
    return target, *other


def test_actual_native_inventory_is_read_only_and_counts_events_not_heads(native_case):
    path, case, config = deepcopy(native_case)
    before = path.read_bytes()
    result = readiness.inspect_football_readiness(path, requests([case]), config, test_blocks=BLOCKS,
        as_of=NOW+timedelta(days=10))
    assert result["requested_events"] == result["inspected_events"] == result["source_complete_events"] == 1
    assert result["feature_complete_events"] == result["outcome_events"] == 1
    assert result["phase_counts"]["train"] == 1 and result["test_events"] == 0
    assert result["minimum_test_events"] == 200 and result["empirical_qualification"] == "not_evaluated"
    assert result["events"][0]["status"] == "ready"
    assert path.read_bytes() == before


def test_real_case_fit_dataset_evaluation_roundtrip_never_activates_small_cohort(joint_cohort, tmp_path):
    from context_models.dataset import _reader
    from context_models.evaluator import verify_evaluation
    path, cases, config, built = isolated(joint_cohort, tmp_path)
    with sqlite3.connect(path) as con:
        old = con.execute("SELECT digest,kind,payload,created_at FROM artifacts ORDER BY digest").fetchall()
    result = readiness.prepare_football_context(path, requests(cases), config, test_blocks=BLOCKS,
        code_revision="a"*40, created_at=built+timedelta(hours=1), evaluate=True)
    assert result["status"] == "evaluated_not_activated" and result["fit_status"] == "fitted"
    assert len(result["case_refs"]) == 6 and result["readiness"]["test_events"] == 3
    assert result["approval_count"] == 0 and result["activated"] is False
    assert result["identity_ref"] and result["dataset_ref"] and result["experiment_ref"]
    with _reader(path) as con:
        evaluated = verify_evaluation(con, result["evaluation_ref"])
        assert con.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-approval-v1'").fetchone() == (0,)
        assert len(evaluated["payload"]["distribution_losses"][next(iter(evaluated["payload"]["distribution_losses"]))]) == 3
        assert con.execute("SELECT COUNT(*) FROM active_manifest").fetchone()[0] == 0
        for row in old:
            assert con.execute("SELECT digest,kind,payload,created_at FROM artifacts WHERE digest=?", (row[0],)).fetchone() == row


def test_missing_weather_is_not_zero_or_fabricated_fit(native_case, tmp_path):
    path, case, config = isolated(native_case, tmp_path)
    config.update(feature_names=["weather.temperature_c"], groups={"weather": ["weather.temperature_c"]})
    inspected = readiness.inspect_football_readiness(path, requests([case]), config, test_blocks=BLOCKS,
        as_of=NOW+timedelta(days=10))
    assert inspected["source_complete_events"] == 1 and inspected["feature_complete_events"] == 0
    assert inspected["events"][0]["unavailable_features"] == ["weather.temperature_c"]
    result = readiness.prepare_football_context(path, requests([case]), config, test_blocks=BLOCKS,
        code_revision="a"*40, created_at=NOW+timedelta(days=10))
    assert result["fit_status"] == "unsupported" and result["approval_count"] == 0
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM artifacts WHERE kind='context-effect-v1'").fetchone() == (0,)


def test_missing_result_does_not_shrink_declared_final_cohort(joint_cohort, tmp_path):
    path, cases, config, built = isolated(joint_cohort, tmp_path)
    missing = cases[-1]["case"]["payload"]["outcome_ref"]
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM context_observations WHERE digest=?", (missing,))
    before = path.read_bytes()
    result = readiness.prepare_football_context(path, requests(cases), config, test_blocks=BLOCKS,
        code_revision="a"*40, created_at=built)
    assert result["status"] == "not_ready" and result["case_refs"] == [] and result["fit_ref"] is None
    assert result["readiness"]["test_events"] == 3
    assert result["readiness"]["events"][-1]["status"] == "outcome_unavailable"
    assert path.read_bytes() == before


def test_malformed_actual_source_is_rejected_before_preparation_writes(native_case, tmp_path):
    path, case, config = isolated(native_case, tmp_path)
    source = next(row["digest"] for row in case["observations"] if row["kind"] == "base_fixture")
    with sqlite3.connect(path) as con:
        con.execute("UPDATE context_contents SET payload=? WHERE content_digest=(SELECT content_digest FROM context_observations WHERE digest=?)", (b"{}", source))
    before = path.read_bytes()
    with pytest.raises(ContextIntegrityError):
        readiness.prepare_football_context(path, requests([case]), config, test_blocks=BLOCKS,
            code_revision="a"*40, created_at=NOW+timedelta(days=10))
    assert path.read_bytes() == before


def test_validly_hashed_foreign_result_cannot_bind_same_event_key(native_case, tmp_path):
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_outcome
    from context_training_helpers import detail
    path, case, config = isolated(native_case, tmp_path)
    event = deepcopy(case["case"]["payload"]["event"])
    event["home_id"] = "api-football:team:99"
    raw = detail(9000, NOW+timedelta(hours=2))
    raw["teams"]["home"]["id"] = 99
    clock = NOW+timedelta(hours=7)
    receipt = normalize_football_outcome(event, raw, observed_at=clock)
    append_observation(path, receipt, observed_at=clock)
    with pytest.raises(ContextContractError, match="differ"):
        readiness.inspect_football_readiness(path, requests([case]), config, test_blocks=BLOCKS,
            as_of=NOW+timedelta(days=10))


@pytest.mark.parametrize("value", [[], ({"binding_ref": "x"},), ({"binding_ref": "a"*64},)*2,
    ({"binding_ref": "a"*64, "context_ref": {"key": "old-cutoff-snapshot"}},),
    tuple({"binding_ref": f"{index:064x}"} for index in range(readiness.MAX_EVENTS+1))])
def test_inventory_is_explicit_unique_and_bounded_before_read(value, native_case, monkeypatch):
    _, _, config = deepcopy(native_case)
    monkeypatch.setattr(readiness, "_reader", lambda *_a: pytest.fail("invalid inventory must be rejected before IO"))
    with pytest.raises(ContextContractError):
        readiness.inspect_football_readiness("absent.db", value, config, test_blocks=BLOCKS, as_of=NOW)


def test_byte_admission_does_not_partially_fit_more_favorable_subset(native_case, tmp_path, monkeypatch):
    path, case, config = isolated(native_case, tmp_path)
    monkeypatch.setattr(readiness, "MAX_INPUT_BYTES", 1)
    before = path.read_bytes()
    result = readiness.prepare_football_context(path, requests([case]), config, test_blocks=BLOCKS,
        code_revision="a"*40, created_at=NOW+timedelta(days=10))
    assert result["status"] == "not_ready" and not result["case_refs"]
    assert result["readiness"]["events"][0]["reason"] == "preparation_total_byte_bound_exceeded"
    assert path.read_bytes() == before


def test_later_actual_decision_includes_weather_without_backdating_original(native_case, tmp_path):
    from context_models.dataset import _reader
    from context_models.football_training import _load_publication
    from context_observations import append_observation
    from context_sources.openweather import forecast_payload, normalize_forecast
    from football_context_decisions import DECISION_KIND
    from football_joint_worker import _bounded_receipts
    from model_artifacts import put_artifact
    path, case, config = isolated(native_case, tmp_path)
    binding = case["case"]["payload"]["replay_ref"]
    event = case["case"]["payload"]["event"]
    clock = NOW+timedelta(minutes=2)
    forecast = forecast_payload(event, city="Example", country="GB", latitude=50., longitude=0.,
        point={"dt": datetime.fromisoformat(event["scheduled_start"]).timestamp(), "main": {"temp": 18.}, "wind": {"speed": 4.}})
    append_observation(path, normalize_forecast(forecast, observed_at=clock), observed_at=clock)
    config.update(feature_names=["weather.temperature_c"], groups={"weather": ["weather.temperature_c"]})
    with _reader(path) as con:
        _, original, _ = _load_publication(con, binding, latest=canonical_timestamp(NOW+timedelta(days=10)))
        refs = sorted(row["digest"] for row in _bounded_receipts(con, original.to_dict(), cutoff=canonical_timestamp(clock)))
    proof = {"schema": 1, "binding_ref": binding, "event_key": event["event_key"], "decision_at": canonical_timestamp(clock),
             "observation_refs_hash": digest(refs), "observation_count": len(refs)}
    decision_ref = put_artifact(path, kind=DECISION_KIND, payload=proof, created_at=clock+timedelta(seconds=1))
    old = readiness.inspect_football_readiness(path, requests([case]), config, test_blocks=BLOCKS, as_of=NOW+timedelta(days=10))
    later = readiness.inspect_football_readiness(path, ({"binding_ref": binding, "decision_ref": decision_ref},),
        config, test_blocks=BLOCKS, as_of=NOW+timedelta(days=10))
    assert old["feature_complete_events"] == 0 and later["feature_complete_events"] == 1
    assert old["events"][0]["decision_at"] == canonical_timestamp(NOW)
    assert later["events"][0]["decision_at"] == canonical_timestamp(clock)
    proof["observation_refs_hash"] = "f"*64
    forged = put_artifact(path, kind=DECISION_KIND, payload=proof, created_at=clock+timedelta(seconds=1))
    with pytest.raises(ContextIntegrityError, match="frozen"):
        readiness.inspect_football_readiness(path, ({"binding_ref": binding, "decision_ref": forged},),
            config, test_blocks=BLOCKS, as_of=NOW+timedelta(days=10))


def test_preparation_rejects_production_database_before_any_io(native_case, monkeypatch):
    _, case, config = deepcopy(native_case)
    monkeypatch.setattr(readiness, "_reader", lambda *_a: pytest.fail("production must be rejected before IO"))
    with pytest.raises(ContextContractError, match="production"):
        readiness.prepare_football_context(readiness.RUNTIME_STATE_DIR.absolute()/"context_models.db", requests([case]),
            config, test_blocks=BLOCKS, code_revision="a"*40, created_at=NOW+timedelta(days=10))


def test_offline_cli_inspection_is_read_only_and_never_opens_provider(native_case, tmp_path, capsys, monkeypatch):
    from scripts import prepare_football_context as cli
    path, case, config = isolated(native_case, tmp_path)
    plan = {"config": config, "requests": list(requests([case])), "test_blocks": [[canonical_timestamp(v) for v in pair] for pair in BLOCKS],
            "code_revision": "a"*40}
    plan_path, output = tmp_path/"input.json", tmp_path/"readiness.json"
    plan_path.write_bytes(json.dumps(plan).encode())
    # Report-file atomic/hardlink ownership is covered by runtime_paths tests;
    # this managed Windows sandbox disallows creating a hard link. Only the
    # unrelated output primitive is replaced, never native case/DB resolvers.
    monkeypatch.setattr(cli, "atomic_write_bytes", lambda target, raw, **_kw: target.write_bytes(raw))
    before = path.read_bytes()
    assert cli.main(["--model-db", str(path), "--plan", str(plan_path), "--output", str(output)]) == 0
    assert json.loads(output.read_bytes())["activated"] is False
    assert json.loads(capsys.readouterr().out)["status"] == "inspected_not_activated"
    assert path.read_bytes() == before


@pytest.mark.parametrize("which", ["count", "bytes"])
def test_full_evaluator_admission_is_header_bounded_before_any_fit(native_case, tmp_path, monkeypatch, which):
    path, case, config = isolated(native_case, tmp_path)
    monkeypatch.setattr(readiness, "MAX_EVALUATION_RECEIPTS" if which == "count" else "MAX_EVALUATION_BYTES", 1)
    monkeypatch.setattr(readiness, "_inspect", lambda *_a, **_k: pytest.fail("large offline store must stop before case work"))
    before = path.read_bytes()
    with pytest.raises(ContextContractError, match="bounded"):
        readiness.prepare_football_context(path, requests([case]), config, test_blocks=BLOCKS,
            code_revision="a"*40, created_at=NOW+timedelta(days=10), evaluate=True)
    assert path.read_bytes() == before


def test_cli_refuses_existing_or_aliased_output_before_offline_writes(native_case, tmp_path, monkeypatch, capsys):
    from scripts import prepare_football_context as cli
    path, _, _ = isolated(native_case, tmp_path)
    plan = tmp_path/"unused.json"
    plan.write_bytes(b"{}")
    monkeypatch.setattr(cli, "prepare_football_context", lambda *_a, **_k: pytest.fail("aliased output must stop before mutation"))
    before = path.read_bytes()
    assert cli.main(["--model-db", str(path), "--plan", str(plan), "--output", str(path), "--prepare"]) == 1
    assert json.loads(capsys.readouterr().out)["error_type"] == "ContextContractError"
    assert path.read_bytes() == before
