"""CPU-only synthetic B3 mechanics; these fixtures are not model approvals."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier
from time import monotonic
from types import SimpleNamespace

import pytest
import runtime_paths

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, digest, validate_context_approval,
    validate_context_result, validate_feature_vector,
)
from context_snapshots import compute_once, select_context_result, snapshot_key
from model_artifacts import canonical_bytes, load_artifact, put_artifact


NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
STAMP = "2026-09-08T12:00:00.000000Z"
REF = "b" * 64


def event():
    return {"event_key": "espn:tennis:42", "sport": "tennis", "competition": "atp:us-open",
            "format": "best_of_5", "home_id": "espn:player:1", "away_id": "espn:player:2",
            "scheduled_start": "2026-09-08T18:00:00.000000Z", "schedule_revision": "s1",
            "status": "scheduled", "tour": "ATP", "surface": "Hard", "indoor": False}


def population():
    return {"sport": "tennis", "competitions": ["atp:us-open"], "formats": ["best_of_5"],
            "tours": ["ATP"], "surfaces": ["Hard"], "indoor": [False]}


def base():
    return {"version": "tennis-winner-v1", "model_hash": "a" * 64, "event_key": event()["event_key"],
            "cutoff": STAMP, "family": "tennis:winner", "params": {"p_a": .6},
            "markets": {"winner_a": .6, "winner_b": .4}, "history_refs": [],
            "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "legacy-unavailable"}}


def features():
    return {"version": "tennis-load-v1", "event_key": event()["event_key"], "cutoff": STAMP,
            "values": {"load_difference": 1.0, "travel": None},
            "states": {"load_difference": "available", "travel": "missing"},
            "refs": {"load_difference": [REF], "travel": []},
            "coverage": {"version": "load-v1", "case": "known-load"}, "reference_hash": "c" * 64}


def effect():
    return {"schema": 1, "sport": "tennis", "family": "tennis:winner", "feature_version": "tennis-load-v1",
            "feature_names": ["load_difference"],
            "heads": {"winner": {"link": "logit", "scale": [1.0], "coef": [.2], "alpha": .1, "n_rows": 100}},
            "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"},
            "training_end": "2026-09-01T12:00:00.000000Z", "training_refs_hash": REF,
            "population": population(), "coverage": features()["coverage"], "model_variant": "load-difference-v1"}


def envelope(payload, kind):
    row = {"kind": kind, "payload": deepcopy(payload)}
    return {"digest": digest(row), **row}


def approval_payload(effect_hash):
    return {"schema": 1, "decision": "approved", "hypothesis_id": "1" * 64,
            "experiment_hash": "2" * 64, "report_hash": "3" * 64, "effect_hash": effect_hash,
            "dataset_hash": "4" * 64, "event_identity_hash": "5" * 64, "code_revision": "6" * 40,
            "policy_version": "context-policy-v1", "base_versions": [base()["version"]],
            "sport": "tennis", "family": "tennis:winner", "feature_version": "tennis-load-v1",
            "population": population(), "coverage": features()["coverage"], "model_variant": "load-difference-v1",
            "target_markets": ["winner_a", "winner_b"], "outcome_contract": "tennis:winner-v1",
            "test_events_hash": "7" * 64, "evaluated_at": "2026-09-07T12:00:00.000000Z"}


def arguments(*, approved=False):
    artifact = envelope(effect(), "context-effect-v1")
    comparison = {**base(), "version": "tennis-context-v1", "model_hash": "d" * 64,
                  "params": {"p_a": .65}, "markets": {"winner_a": .65, "winner_b": .35}}
    return {"base": base(), "comparison": comparison, "event": event(), "features": features(),
            "effect_artifact": {key: artifact[key] for key in ("kind", "payload")},
            "effect_hash": artifact["digest"],
            "approval": envelope(approval_payload(artifact["digest"]), "context-approval-v1") if approved else None,
            "factor_roles": {"load_difference": "applied", "travel": "not_applied"},
            "factor_states": features()["states"], "limitations": ["travel-unavailable"]}


def key_arguments():
    return {"event": event(), "base_hash": digest(base()), "context_refs": (REF,),
            "feature_version": features()["version"], "feature_hash": digest(validate_feature_vector(features())),
            "effect_hash": arguments()["effect_hash"], "decision_at": NOW, "approval_hash": None}


def test_shared_snapshot_computes_once_and_never_reuses_mutable_return_object(tmp_path):
    calls = []
    calculated = {"used_markets": {"home": .6}}
    def calculate():
        calls.append(1)
        return calculated
    path = tmp_path / "nested" / "models.db"
    first = compute_once(path, "a" * 64, calculate)
    first["used_markets"]["home"] = .1
    calculated["used_markets"]["home"] = .9
    second = compute_once(path, "a" * 64, calculate)
    assert second == {"used_markets": {"home": .6}}
    assert calls == [1]
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT typeof(key), typeof(payload), typeof(payload_digest) FROM context_snapshots").fetchone() == ("text", "blob", "text")


def test_concurrent_first_workers_compute_exactly_once(tmp_path):
    path = tmp_path / "models.db"
    start = Barrier(8)
    calls = []
    def worker(_):
        start.wait()
        return compute_once(path, "a" * 64, lambda: (calls.append(1) or {"used_markets": {"home": .6}}))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))
    assert len(calls) == 1
    assert all(value == results[0] for value in results)


@pytest.mark.parametrize("error", [ValueError("model failed"), KeyboardInterrupt()])
def test_callback_failure_rolls_back_and_allows_a_later_calculation(tmp_path, error):
    path = tmp_path / "models.db"
    def fail():
        raise error
    with pytest.raises(type(error)):
        compute_once(path, "a" * 64, fail)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0] == 0
    assert compute_once(path, "a" * 64, lambda: {"ok": True}) == {"ok": True}


@pytest.mark.parametrize("value", [None, [], {1: "bad"}, {"x": float("nan")}, {"x": float("inf")},
                                  {"nested": ({"tuple": True},)}, {"nested": {2: "bad"}}, {"x": object()}])
def test_bad_callback_json_never_publishes_a_partial_snapshot(tmp_path, value):
    path = tmp_path / "models.db"
    with pytest.raises(ContextContractError):
        compute_once(path, "a" * 64, lambda: value)
    assert compute_once(path, "a" * 64, lambda: {"ok": True}) == {"ok": True}


@pytest.mark.parametrize("key", ["A" * 64, "a" * 63, "not-a-key", None, 123])
def test_bad_key_rejected_before_any_database_or_callback(tmp_path, key):
    path = tmp_path / "models.db"
    with pytest.raises(ContextContractError):
        compute_once(path, key, lambda: pytest.fail("must not calculate"))
    assert not path.exists()


@pytest.mark.parametrize("payload", [b'{"x":2}', b'{"x":1,"x":1}', b'{ "x":1}', b'{"x":NaN}', b'[]',
                                   b'bad', '{"x":1}', b'{"x":1e309}'])
def test_corrupt_snapshot_is_not_recomputed_or_overwritten(tmp_path, payload):
    path = tmp_path / "models.db"
    compute_once(path, "a" * 64, lambda: {"x": 1})
    with sqlite3.connect(path) as con:
        con.execute("UPDATE context_snapshots SET payload=?", (payload,))
    with pytest.raises(ContextIntegrityError):
        compute_once(path, "a" * 64, lambda: pytest.fail("corruption must not trigger computation"))
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT payload FROM context_snapshots").fetchone()[0] == payload


def test_snapshot_digest_binds_key_not_just_payload_and_prior_history_stays_unchanged(tmp_path):
    path = tmp_path / "models.db"
    compute_once(path, "a" * 64, lambda: {"x": 1})
    with sqlite3.connect(path) as con:
        first = con.execute("SELECT * FROM context_snapshots").fetchall()
    compute_once(path, "b" * 64, lambda: {"x": 2})
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT * FROM context_snapshots WHERE key=?", ("a" * 64,)).fetchall() == first
        con.execute("UPDATE context_snapshots SET key=? WHERE key=?", ("c" * 64, "a" * 64))
    with pytest.raises(ContextIntegrityError):
        compute_once(path, "c" * 64, lambda: pytest.fail("not recomputed"))


def test_snapshot_uses_the_same_a1_database_and_does_not_modify_artifacts(tmp_path):
    path = tmp_path / "models.db"
    artifact_hash = put_artifact(path, kind="test", payload={"a": 1}, created_at=NOW)
    before = load_artifact(path, artifact_hash)
    compute_once(path, "a" * 64, lambda: {"x": 1})
    assert load_artifact(path, artifact_hash) == before


def test_key_is_clock_zone_order_and_tab_price_invariant():
    args = key_arguments()
    args["context_refs"] = ("c" * 64, REF)
    key = snapshot_key(**args)
    changed = deepcopy(args)
    changed["event"]["scheduled_start"] = "2026-09-08T20:00:00+02:00"
    changed["decision_at"] = NOW.astimezone(timezone(timedelta(hours=2)))
    changed["context_refs"] = (REF, "c" * 64)
    for _tab, _quote in (("Wettfinder", None), ("RisikoBet", 1.01), ("Wettfinder", 50.0)):
        assert snapshot_key(**changed) == key


@pytest.mark.parametrize("changes", [{"event_key": "espn:tennis:43"}, {"home_id": "espn:player:3"},
                                     {"competition": "atp:other"}, {"format": "best_of_3"}, {"tour": "WTA"},
                                     {"surface": "Clay"}, {"indoor": True}, {"schedule_revision": "s2"},
                                     {"scheduled_start": "2026-09-08T19:00:00.000000Z"}, {"status": "cancelled"}])
def test_key_binds_every_declared_event_identity_field(changes):
    args = key_arguments()
    assert snapshot_key(**{**args, "event": {**args["event"], **changes}}) != snapshot_key(**args)


@pytest.mark.parametrize("changes", [{"base_hash": "e" * 64}, {"context_refs": ("f" * 64,)},
                                     {"feature_version": "features-v2"}, {"feature_hash": "e" * 64},
                                     {"effect_hash": None}, {"approval_hash": "f" * 64},
                                     {"decision_at": NOW + timedelta(seconds=1)}])
def test_key_binds_model_feature_context_approval_and_shared_cutoff(changes):
    args = key_arguments()
    assert snapshot_key(**{**args, **changes}) != snapshot_key(**args)


@pytest.mark.parametrize("name,replacement", [("values", {"load_difference": 2., "travel": None}),
                                             ("states", {"load_difference": "stale", "travel": "missing"}),
                                             ("refs", {"load_difference": ["e" * 64], "travel": []}),
                                             ("coverage", {"version": "load-v2", "case": "partial"}),
                                             ("reference_hash", "e" * 64)])
def test_full_feature_hash_prevents_aliasing_another_feature_revision(name, replacement):
    args = key_arguments()
    revised = {**features(), name: replacement}
    revised_hash = digest(validate_feature_vector(revised))
    assert snapshot_key(**{**args, "feature_hash": revised_hash}) != snapshot_key(**args)


@pytest.mark.parametrize("field", ["odds", "quote", "tab", "bestPrice", "unknown"])
def test_key_rejects_unknown_event_fields_instead_of_accepting_model_price_input(field):
    args = key_arguments()
    args["event"][field] = 1.9
    with pytest.raises(ContextContractError):
        snapshot_key(**args)


@pytest.mark.parametrize("changes", [{"feature_hash": "bad"}, {"base_hash": None}, {"effect_hash": "bad"},
                                     {"approval_hash": "bad"}, {"decision_at": datetime(2026, 9, 8)},
                                     {"decision_at": STAMP}, {"context_refs": (REF, REF)},
                                     {"context_refs": [REF]}, {"context_refs": ("bad",)}, {"feature_version": ""}])
def test_key_rejects_incomplete_or_ambiguous_identity(changes):
    with pytest.raises(ContextContractError):
        snapshot_key(**{**key_arguments(), **changes})


def test_unapproved_comparison_is_experimental_and_keeps_exact_basis():
    args = arguments()
    original = deepcopy(args)
    result = select_context_result(**args)
    assert result["role"] == "experimental"
    assert result["used_markets"] == args["base"]["markets"]
    assert result["used_params"] == args["base"]["params"]
    assert result["comparison_markets"] == args["comparison"]["markets"]
    assert result["factor_roles"] == {"load_difference": "experimental", "travel": "not_applied"}
    assert result["factor_states"] == features()["states"]
    assert result["delta_pp"] == {"winner_a": 0., "winner_b": 0.}
    assert result["base_hash"] == digest(args["base"])
    assert args == original


def test_only_exact_verified_approval_uses_the_comparison_and_retains_certified_markets():
    args = arguments(approved=True)
    result = select_context_result(**args)
    assert result["role"] == "applied"
    assert result["used_params"] == args["comparison"]["params"]
    assert result["used_markets"] == args["comparison"]["markets"]
    assert result["delta_pp"] == pytest.approx({"winner_a": 5., "winner_b": -5.})
    assert result["factor_roles"] == {"load_difference": "applied", "travel": "not_applied"}
    assert result["approval_hash"] == args["approval"]["digest"]
    assert result["certified_markets"] == ["winner_a", "winner_b"]


def test_zero_effect_is_applied_but_never_compounded_on_rerun():
    args = arguments(approved=True)
    args["comparison"] = deepcopy(args["base"])
    args["effect_artifact"]["payload"]["heads"]["winner"]["coef"] = [0.]
    args["effect_hash"] = digest(args["effect_artifact"])
    args["approval"] = envelope(approval_payload(args["effect_hash"]), "context-approval-v1")
    result = select_context_result(**args)
    assert result["role"] == "applied"
    assert all(value == 0 for value in result["delta_pp"].values())
    assert select_context_result(**args) == result


def test_repeated_nonzero_result_does_not_become_a_valid_baseline():
    args = arguments(approved=True)
    result = select_context_result(**args)
    assert select_context_result(**args) == result
    with pytest.raises(ContextContractError):
        select_context_result(**{**args, "base": result})


@pytest.mark.parametrize("state", ["stale", "missing", "conflicting", "not_applicable"])
def test_ineligible_consumed_features_return_to_base_even_with_valid_approval(state):
    args = arguments(approved=True)
    args["features"]["states"]["load_difference"] = state
    args["factor_states"]["load_difference"] = state
    if state in {"missing", "not_applicable"}:
        args["features"]["values"]["load_difference"] = None
    result = select_context_result(**args)
    assert result["role"] == "not_applied"
    assert result["used_markets"] == base()["markets"]
    assert result["factor_roles"]["load_difference"] == "not_applied"
    assert "context-features-ineligible" in result["limitations"]
    assert result["approval_hash"] is None and result["certified_markets"] == []


def test_missing_context_or_model_error_keeps_basis_without_fabricating_a_comparison():
    args = arguments(approved=True)
    args["comparison"] = None
    args["limitations"].append("context-model-error")
    result = select_context_result(**args)
    assert result["role"] == "not_applied"
    assert result["comparison_markets"] is None
    assert result["used_markets"] == base()["markets"]
    assert "context-model-error" in result["limitations"]
    args.update(effect_hash=None, effect_artifact=None, approval=None)
    assert select_context_result(**args)["role"] == "not_applied"


@pytest.mark.parametrize("approval", [{}, {"approved": True}, True, {"decision": "approved"},
                                     {"digest": "f" * 64, "kind": "context-approval-v1", "payload": {}}])
def test_unknown_approval_cannot_enable_the_effect(approval):
    with pytest.raises(ContextIntegrityError):
        select_context_result(**{**arguments(), "approval": approval})


@pytest.mark.parametrize("target", ["effect_artifact", "approval"])
def test_verified_envelopes_reject_payload_tampering_before_eligibility(target):
    args = arguments(approved=True)
    args[target]["payload"]["model_variant"] = "tampered"
    args["comparison"] = None
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


@pytest.mark.parametrize("field,replacement", [("effect_hash", "e" * 64), ("feature_version", "other-v1"),
                                             ("model_variant", "other-model"),
                                             ("population", {**population(), "competitions": ["atp:other"]}),
                                             ("coverage", {"version": "load-v1", "case": "unseen"})])
def test_internally_valid_but_different_approval_scope_keeps_experimental_basis(field, replacement):
    args = arguments(approved=True)
    payload = {**args["approval"]["payload"], field: replacement}
    args["approval"] = envelope(payload, "context-approval-v1")
    result = select_context_result(**args)
    assert result["role"] == "experimental"
    assert result["used_markets"] == base()["markets"]
    assert "context-approval-scope-mismatch" in result["limitations"]


@pytest.mark.parametrize("field,replacement", [("competition", "atp:unseen"), ("format", "best_of_3"),
                                             ("tour", "WTA"), ("surface", "Clay"), ("indoor", True),
                                             ("surface", None)])
def test_unseen_event_population_does_not_inherit_a_numeric_effect(field, replacement):
    args = arguments(approved=True)
    args["event"][field] = replacement
    result = select_context_result(**args)
    assert result["role"] == "not_applied"
    assert result["used_markets"] == base()["markets"]
    assert "context-effect-scope-mismatch" in result["limitations"]


@pytest.mark.parametrize("status", ["cancelled", "started", "completed"])
def test_nonprematch_event_preserves_basis_but_does_not_apply_context(status):
    args = arguments(approved=True)
    args["event"]["status"] = status
    result = select_context_result(**args)
    assert result["role"] == "not_applied"
    assert "context-event-ineligible" in result["limitations"]


@pytest.mark.parametrize("component", ["event", "features", "comparison"])
def test_mixed_event_inputs_are_integrity_errors(component):
    args = arguments(approved=True)
    args[component]["event_key"] = "espn:tennis:43"
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


@pytest.mark.parametrize("component", ["features", "comparison"])
def test_a_different_cutoff_cannot_reuse_the_current_context_comparison(component):
    args = arguments(approved=True)
    args[component]["cutoff"] = "2026-09-08T12:01:00.000000Z"
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


def test_factor_states_cannot_disagree_with_features_or_claim_an_unconsumed_effect():
    args = arguments()
    args["factor_states"]["travel"] = "available"
    with pytest.raises(ContextContractError):
        select_context_result(**args)
    args = arguments()
    args["factor_roles"]["travel"] = "applied"
    with pytest.raises(ContextContractError):
        select_context_result(**args)


def test_basis_and_result_mutation_do_not_change_prior_snapshot(tmp_path):
    args = arguments(approved=True)
    originals = deepcopy(args)
    result = compute_once(tmp_path / "models.db", snapshot_key(**key_arguments()), lambda: select_context_result(**args))
    result["base_params"]["p_a"] = .01
    result["used_markets"]["winner_a"] = .01
    result["feature_refs"]["load_difference"].append("c" * 64)
    assert args == originals
    previous = compute_once(tmp_path / "models.db", snapshot_key(**key_arguments()), lambda: pytest.fail("must read previous"))
    assert previous["base_params"] == base()["params"]
    assert previous["used_markets"]["winner_a"] == .65
    assert previous["feature_refs"]["load_difference"] == [REF]


def test_independent_processes_share_the_same_first_calculation(tmp_path):
    # Streamlit AppTest can replace sys.modules['__main__'] with a generated
    # renderer. Spawn must not recycle that unrelated script. Each interpreter
    # gets its own explicit, CPU-only bootstrap and the actual repository.
    child_code = """
import json
import os
from pathlib import Path
import sys
from context_snapshots import compute_once

sentinel = int(sys.argv[2])
calls = []
def calculate():
    calls.append(sentinel)
    return {"worker": sentinel}

print(json.dumps({"ready": True, "pid": os.getpid(), "worker": sentinel}), flush=True)
if sys.stdin.readline() != "go\\n":
    raise RuntimeError("missing common start barrier")
result = compute_once(Path(sys.argv[1]), "a" * 64, calculate)
print(json.dumps({"result": result, "callbacks": len(calls)}), flush=True)
"""
    path = tmp_path / "models.db"
    repo = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHONPATH=str(repo))
    # Windows venv python.exe may be a launcher that creates another process.
    # This stdlib-only kernel uses the same real interpreter directly, so its
    # PID and timeout cleanup belong to the exact Popen child we own.
    interpreter = getattr(sys, "_base_executable", sys.executable) or sys.executable
    processes = []
    readers = ThreadPoolExecutor(max_workers=3)
    try:
        # All three processes are alive and waiting at the barrier before ANY
        # first write is allowed. No sleeps or scheduler timing assumptions.
        for number in range(3):
            processes.append(subprocess.Popen(
                [interpreter, "-B", "-u", "-c", child_code, str(path), str(number)],
                cwd=repo, env=environment, text=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ))
        ready_reads = [readers.submit(process.stdout.readline) for process in processes]
        deadline = monotonic() + 30
        for number, (process, ready) in enumerate(zip(processes, ready_reads)):
            payload = json.loads(ready.result(timeout=max(.01, deadline - monotonic())))
            assert payload == {"ready": True, "pid": process.pid, "worker": number}
        assert len({process.pid for process in processes}) == 3
        assert not path.exists(), "a child calculated before the common start barrier"
        for process in processes:
            process.stdin.write("go\n")
            process.stdin.flush()
        deadline = monotonic() + 30
        completed = [process.communicate(timeout=max(.01, deadline - monotonic())) for process in processes]
        reports = []
        for process, (stdout, stderr) in zip(processes, completed):
            assert process.returncode == 0, stderr
            assert stderr == ""
            reports.append(json.loads(stdout))
        assert all(set(report) == {"result", "callbacks"} for report in reports)
        assert all(type(report["callbacks"]) is int and report["callbacks"] in (0, 1) for report in reports)
        assert sum(report["callbacks"] for report in reports) == 1
        winner = next(number for number, report in enumerate(reports) if report["callbacks"] == 1)
        assert all(report["result"] == {"worker": winner} for report in reports)
    finally:
        # Only these three owned test children are eligible for cleanup.
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        readers.shutdown(wait=True, cancel_futures=True)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0] == 1
        stored = con.execute("SELECT payload FROM context_snapshots").fetchone()[0]
        assert json.loads(stored) == {"worker": winner}


def test_a1_path_guard_rejects_symlink_before_callback_or_creation(tmp_path, monkeypatch):
    path = (tmp_path / "models.db").absolute()
    original_lstat = runtime_paths.os.lstat
    def symlink_lstat(candidate, *args, **kwargs):
        if Path(candidate).absolute() == path:
            parent_stat = original_lstat(path.parent, *args, **kwargs)
            return SimpleNamespace(st_mode=runtime_paths.stat.S_IFLNK, st_uid=getattr(parent_stat, "st_uid", 0),
                                   st_dev=parent_stat.st_dev, st_ino=parent_stat.st_ino)
        return original_lstat(candidate, *args, **kwargs)
    monkeypatch.setattr(runtime_paths.os, "lstat", symlink_lstat)
    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="symlink"):
        compute_once(path, "a" * 64, lambda: pytest.fail("must not compute on an untrusted path"))
    assert not path.exists()


def test_shared_connection_uses_a1_foreign_keys_busy_timeout_and_trust_checks(tmp_path, monkeypatch):
    import context_snapshots
    original = context_snapshots._artifact_connect
    visited = []
    def checked(path):
        connection = original(path)
        visited.append((connection.execute("PRAGMA foreign_keys").fetchone()[0],
                        connection.execute("PRAGMA busy_timeout").fetchone()[0]))
        return connection
    monkeypatch.setattr(context_snapshots, "_artifact_connect", checked)
    compute_once(tmp_path / "models.db", "a" * 64, lambda: {"x": 1})
    assert visited == [(1, 5000)]


@pytest.mark.parametrize("value", ["e" * 64, b"e" * 64, "A" * 64, "123", 7])
def test_corrupt_payload_digest_type_or_value_never_refreshes_history(tmp_path, value):
    path = tmp_path / "models.db"
    compute_once(path, "a" * 64, lambda: {"x": 1})
    with sqlite3.connect(path) as con:
        con.execute("UPDATE context_snapshots SET payload_digest=?", (value,))
    with pytest.raises(ContextIntegrityError):
        compute_once(path, "a" * 64, lambda: pytest.fail("corrupt digest must not refresh"))


def test_persisted_payload_digest_has_one_documented_canonical_envelope(tmp_path):
    path = tmp_path / "models.db"
    result = compute_once(path, "a" * 64, lambda: {"z": "Grüße", "a": [1.0, None]})
    with sqlite3.connect(path) as con:
        payload, payload_hash = con.execute("SELECT payload, payload_digest FROM context_snapshots").fetchone()
    assert payload == canonical_bytes(result)
    assert payload_hash == hashlib.sha256(canonical_bytes({"key": "a" * 64, "payload": result})).hexdigest()


def test_frozen_worker_cutoff_and_snapshot_are_reused_by_both_consumers(tmp_path):
    args = arguments(approved=True)
    key_args = key_arguments()
    key_args["approval_hash"] = args["approval"]["digest"]
    key = snapshot_key(**key_args)
    calls = []
    def worker():
        calls.append(1)
        return {"decision_at": STAMP, "context": select_context_result(**args)}
    path = tmp_path / "models.db"
    snapshot = compute_once(path, key, worker)
    for tab, odds in (("Wettfinder", None), ("RisikoBet", 1.01), ("Wettfinder", 4.2)):
        # Consumer metadata stays outside the model key and persisted output.
        overlay = {"tab": tab, "price": odds}
        reread = compute_once(path, key, worker)
        assert reread == snapshot and reread["decision_at"] == STAMP
        assert overlay["tab"] not in str(reread)
    assert calls == [1]


def test_approved_effect_and_approval_real_a1_roundtrip(tmp_path):
    args = arguments(approved=True)
    path = tmp_path / "models.db"
    effect_hash = put_artifact(path, kind="context-effect-v1", payload=effect(), created_at=NOW)
    assert effect_hash == args["effect_hash"]
    approval_hash = put_artifact(path, kind="context-approval-v1", payload=approval_payload(effect_hash), created_at=NOW)
    args["effect_artifact"] = load_artifact(path, effect_hash)
    args["approval"] = {"digest": approval_hash, **load_artifact(path, approval_hash)}
    result = select_context_result(**args)
    assert result["approval_hash"] == approval_hash and result["role"] == "applied"


@pytest.mark.parametrize("name,value", [("schema", True), ("schema", 1.0), ("decision", "failed"),
    ("effect_hash", "wrong"), ("report_hash", None), ("hypothesis_id", "A" * 64),
    ("code_revision", "abc"), ("code_revision", "A" * 40), ("policy_version", ""),
    ("base_versions", []), ("base_versions", ["v2", "v1"]), ("base_versions", ["v1", "v1"]),
    ("base_versions", "v1"), ("base_versions", ["bestOdds"]), ("base_versions", [1]),
    ("target_markets", []), ("target_markets", ["winner_b", "winner_a"]),
    ("target_markets", ["winner_a", "winner_a"]), ("target_markets", ["minimumPrice"]),
    ("outcome_contract", {}), ("outcome_contract", "free form explanation"),
    ("evaluated_at", "2026-09-07T12:00:00"), ("evaluated_at", 1), ("coverage", "complete"),
    ("population", {**population(), "sport": "football"}), ("sport", "football")])
def test_closed_approval_contract_rejects_invalid_provenance_or_scope(name, value):
    payload = approval_payload(arguments()["effect_hash"])
    payload[name] = value
    with pytest.raises(ContextContractError):
        validate_context_approval(payload)
    args = arguments(approved=True)
    args["approval"] = envelope(payload, "context-approval-v1")
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


@pytest.mark.parametrize("kind", ["context-effect-v1", "context-evaluation-v1", "test", ""])
def test_approval_cannot_use_another_validly_hashed_artifact_kind(kind):
    args = arguments(approved=True)
    args["approval"] = envelope(args["approval"]["payload"], kind)
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


def test_context_transport_is_closed_and_utc_canonical():
    args = arguments(approved=True)
    args["approval"]["verified"] = True
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)
    args = arguments(approved=True)
    args["approval"]["payload"]["evaluated_at"] = "2026-09-07T14:00:00+02:00"
    args["approval"] = envelope(args["approval"]["payload"], "context-approval-v1")
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


def test_unknown_certified_market_is_not_silently_accepted_or_dropped():
    args = arguments(approved=True)
    args["approval"]["payload"]["target_markets"] = ["unseen"]
    args["approval"] = envelope(args["approval"]["payload"], "context-approval-v1")
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


def test_partial_target_market_certification_does_not_certify_the_other_markets():
    args = arguments(approved=True)
    args["approval"]["payload"]["target_markets"] = ["winner_a"]
    args["approval"] = envelope(args["approval"]["payload"], "context-approval-v1")
    result = select_context_result(**args)
    assert result["role"] == "applied"
    assert result["certified_markets"] == ["winner_a"]
    assert set(result["used_markets"]) == {"winner_a", "winner_b"}


def test_valid_approval_for_different_base_version_does_not_inherit_use():
    args = arguments(approved=True)
    args["approval"]["payload"]["base_versions"] = ["other-base-v1"]
    args["approval"] = envelope(args["approval"]["payload"], "context-approval-v1")
    result = select_context_result(**args)
    assert result["role"] == "experimental"
    assert "context-approval-scope-mismatch" in result["limitations"]


def test_future_approval_cannot_change_the_earlier_used_distribution():
    args = arguments(approved=True)
    args["approval"]["payload"]["evaluated_at"] = "2026-09-08T12:00:00.000001Z"
    args["approval"] = envelope(args["approval"]["payload"], "context-approval-v1")
    result = select_context_result(**args)
    assert result["role"] == "experimental"
    assert result["used_markets"] == base()["markets"]
    assert "context-approval-after-cutoff" in result["limitations"]


def test_approval_before_its_same_effect_training_end_is_contradictory():
    args = arguments(approved=True)
    args["approval"]["payload"]["evaluated_at"] = "2026-08-31T12:00:00.000000Z"
    args["approval"] = envelope(args["approval"]["payload"], "context-approval-v1")
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


@pytest.mark.parametrize("change", ["feature_version", "coverage", "future_training", "missing_consumed_feature"])
def test_valid_but_ineligible_features_or_effect_keep_the_basis(change):
    args = arguments()
    if change == "feature_version":
        args["features"]["version"] = "other-v1"
    elif change == "coverage":
        args["features"]["coverage"]["case"] = "unseen"
    elif change == "future_training":
        args["effect_artifact"]["payload"]["training_end"] = "2026-09-08T12:00:00.000001Z"
        args["effect_hash"] = digest(args["effect_artifact"])
    else:
        for field in ("values", "states", "refs"):
            args["features"][field].pop("load_difference")
        args["factor_roles"].pop("load_difference")
        args["factor_states"].pop("load_difference")
    result = select_context_result(**args)
    assert result["role"] == "not_applied"
    assert result["used_markets"] == base()["markets"]


def test_time_boundary_at_kickoff_is_not_prematch_context():
    args = arguments(approved=True)
    args["event"]["scheduled_start"] = STAMP
    assert select_context_result(**args)["role"] == "not_applied"


@pytest.mark.parametrize("change", [{"reference_weights": {"schema": 1, "kind": "unavailable", "reason": "another-history"}},
                                    {"cutoff": "2026-09-08T11:59:59.999999Z"}])
def test_comparison_cannot_silently_change_the_original_baseline_reference(change):
    args = arguments(approved=True)
    args["comparison"].update(change)
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


@pytest.mark.parametrize("field", ["approval_hash", "certified_markets"])
def test_single_certification_field_is_not_a_valid_result(field):
    args = arguments(approved=True)
    result = select_context_result(**args)
    result.pop(field)
    with pytest.raises(ContextContractError):
        validate_context_result(result, family="tennis:winner", effect_artifact=effect())


@pytest.mark.parametrize("changes", [{"approval_hash": None}, {"approval_hash": "bad"},
                                     {"certified_markets": []}, {"certified_markets": ["unseen"]},
                                     {"certified_markets": ["bestOdds"]}, {"certified_markets": "winner_a"},
                                     {"certified_markets": ["winner_b", "winner_a"]}])
def test_result_cannot_claim_invalid_or_absent_certification(changes):
    result = select_context_result(**arguments(approved=True))
    result.update(changes)
    with pytest.raises(ContextContractError):
        validate_context_result(result, family="tennis:winner", effect_artifact=effect())


def test_legacy_result_remains_readable_but_never_gains_certification_by_default():
    result = select_context_result(**arguments(approved=True))
    result.pop("approval_hash")
    result.pop("certified_markets")
    validated = validate_context_result(result, family="tennis:winner", effect_artifact=effect())
    assert validated == result
    assert "approval_hash" not in validated and "certified_markets" not in validated


@pytest.mark.parametrize("changes", [{"approval_hash": "a" * 64}, {"certified_markets": ["winner_a"]}])
def test_experimental_result_cannot_inherit_any_certification(changes):
    result = select_context_result(**arguments())
    result.update(changes)
    with pytest.raises(ContextContractError):
        validate_context_result(result, family="tennis:winner", effect_artifact=effect())


@pytest.mark.parametrize("component", ["base", "comparison", "features", "event"])
def test_selection_rejects_price_or_ui_metadata_in_any_model_input(component):
    args = arguments(approved=True)
    args[component]["current_odds"] = 1.1
    with pytest.raises(ContextContractError):
        select_context_result(**args)


@pytest.mark.parametrize("refs", [([],), ({"ref": REF},)])
def test_unhashable_context_refs_are_typed_contract_errors(refs):
    with pytest.raises(ContextContractError):
        snapshot_key(**{**key_arguments(), "context_refs": refs})


def test_callback_cyclic_json_is_a_typed_contract_error_without_published_row(tmp_path):
    path = tmp_path / "models.db"
    value = {}
    value["recursive"] = value
    with pytest.raises(ContextContractError):
        compute_once(path, "a" * 64, lambda: value)
    assert compute_once(path, "a" * 64, lambda: {"ok": 1}) == {"ok": 1}


def family_arguments(family):
    args = arguments(approved=True)
    if family == "tennis:winner":
        return args
    effect_payload = args["effect_artifact"]["payload"]
    approved = args["approval"]["payload"]
    head = deepcopy(effect_payload["heads"]["winner"])
    if family == "tennis:serve":
        effect_payload["heads"] = {"hold_a": deepcopy(head), "hold_b": deepcopy(head)}
        params = {"hold_a": .7, "hold_b": .6, "best_of": 5}
        adjusted = {**params, "hold_a": .75}
    else:
        head["link"] = "log_rate"
        effect_payload["heads"] = {"home": deepcopy(head), "away": deepcopy(head)}
        for value in (args["event"], effect_payload, approved):
            value["sport"] = "football"
        args["event"].update(event_key="api-football:football:42", competition="league:39", format="90min")
        for name in ("tour", "surface", "indoor"):
            args["event"].pop(name)
        args["features"]["event_key"] = args["event"]["event_key"]
        scope = {"sport": "football", "competitions": ["league:39"], "formats": ["90min"],
                 "tours": [None], "surfaces": [None], "indoor": [None]}
        effect_payload["population"], approved["population"] = deepcopy(scope), deepcopy(scope)
        params = {"home_lambda": 1.7, "away_lambda": 1.2}
        adjusted = {"home_lambda": 1.5, "away_lambda": 1.3}
        args["base"]["markets"] = {"RESULT_HOME": .5, "RESULT_AWAY": .2, "RESULT_DRAW": .3}
        args["comparison"]["markets"] = {"RESULT_HOME": .45, "RESULT_AWAY": .25, "RESULT_DRAW": .3}
    for value in (args["base"], args["comparison"], effect_payload, approved):
        value["family"] = family
    args["base"].update(event_key=args["event"]["event_key"], params=params)
    args["comparison"].update(event_key=args["event"]["event_key"], params=adjusted)
    args["effect_hash"] = digest(args["effect_artifact"])
    approved.update(effect_hash=args["effect_hash"], target_markets=sorted(args["base"]["markets"]))
    args["approval"] = envelope(approved, "context-approval-v1")
    return args


@pytest.mark.parametrize("family", ["football:goals:90min", "tennis:winner", "tennis:serve"])
def test_existing_supported_families_use_the_same_role_boundary(family):
    args = family_arguments(family)
    expected = deepcopy(args)
    result = select_context_result(**args)
    assert result["role"] == "applied"
    assert result["base_params"] == args["base"]["params"]
    assert result["used_params"] == args["comparison"]["params"]
    assert result["certified_markets"] == sorted(args["comparison"]["markets"])
    assert args == expected
    args["approval"] = None
    assert select_context_result(**args)["used_markets"] == args["base"]["markets"]


def test_context_cannot_change_the_tennis_match_format():
    args = family_arguments("tennis:serve")
    args["comparison"]["params"]["best_of"] = 3
    with pytest.raises(ContextIntegrityError):
        select_context_result(**args)


def test_valid_artifact_of_another_family_cannot_affect_the_basis():
    args = arguments(approved=True)
    other = family_arguments("football:goals:90min")
    args.update(effect_artifact=other["effect_artifact"], effect_hash=other["effect_hash"], approval=other["approval"])
    result = select_context_result(**args)
    assert result["role"] == "not_applied"
    assert result["used_markets"] == base()["markets"]
    assert "context-effect-scope-mismatch" in result["limitations"]


def test_snapshot_rejects_unscoped_approval_identity():
    args = key_arguments()
    args.update(effect_hash=None, approval_hash="a" * 64)
    with pytest.raises(ContextContractError):
        snapshot_key(**args)


def test_base_hash_binds_the_complete_normalized_baseline_not_just_its_global_model():
    from context_models.contracts import validate_base_distribution
    args = arguments()
    original = select_context_result(**args)
    assert original["base_hash"] != args["base"]["model_hash"]
    assert original["base_hash"] == digest(validate_base_distribution(args["base"]))
    args["base"]["params"] = {"p_a": .55}
    args["base"]["markets"] = {"winner_a": .55, "winner_b": .45}
    assert args["base"]["model_hash"] == base()["model_hash"]
    revised = select_context_result(**args)
    assert revised["base_hash"] != original["base_hash"]
    first_key = snapshot_key(**{**key_arguments(), "base_hash": original["base_hash"]})
    assert snapshot_key(**{**key_arguments(), "base_hash": revised["base_hash"]}) != first_key
    args["base"]["cutoff"] = "2026-09-08T14:00:00+02:00"
    assert select_context_result(**args)["base_hash"] == revised["base_hash"]
