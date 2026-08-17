from __future__ import annotations

from datetime import date, timedelta
import json
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import runtime_paths
from scripts import run_daily_pipeline, weekly_report
from tennis import model_state


def test_automation_uses_ignored_runtime_directories() -> None:
    assert run_daily_pipeline.LOG_DIR == runtime_paths.PIPELINE_LOG_DIR
    assert (
        run_daily_pipeline.WATCH_JSON
        == runtime_paths.TENNIS_CALIBRATION_WATCH_PATH
    )
    assert weekly_report.WATCH_JSON == runtime_paths.TENNIS_CALIBRATION_WATCH_PATH
    assert weekly_report.REPORTS == runtime_paths.TENNIS_WEEKLY_REPORT_DIR
    assert model_state.DEFAULT_STATE_PATH == runtime_paths.TENNIS_MODEL_STATE_PATH
    assert run_daily_pipeline.atomic_write_text is runtime_paths.atomic_write_text
    assert weekly_report.atomic_write_text is runtime_paths.atomic_write_text

    assert "runtime_state" in run_daily_pipeline.LOG_DIR.parts
    assert "runtime_state" in run_daily_pipeline.WATCH_JSON.parts
    assert "runtime_reports" in weekly_report.REPORTS.parts
    assert "runtime_state" in model_state.DEFAULT_STATE_PATH.parts


def test_model_state_reads_packaged_seed_but_only_writes_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = tmp_path / "runtime_state" / "tennis" / "model_state.pkl"
    packaged = tmp_path / "tennis" / "data" / "model_state.pkl"
    packaged.parent.mkdir(parents=True)
    packaged_state = model_state.ModelState(
        elo=SimpleNamespace(),
        serve=None,
        cal_a=1.0,
        cal_b=0.0,
        cal_samples=1,
        built_at=1.0,
        stats_through="2026-01-01",
        serve_weight=0.3,
    )
    packaged_state.marker = "packaged"
    packaged.write_bytes(pickle.dumps(packaged_state))
    packaged_before = packaged.read_bytes()

    monkeypatch.setattr(model_state, "DEFAULT_STATE_PATH", runtime)
    monkeypatch.setattr(model_state, "PACKAGED_STATE_PATH", packaged)

    assert model_state.state_exists()
    assert model_state.load_state().marker == "packaged"

    runtime_state = model_state.ModelState(
        elo=SimpleNamespace(),
        serve=None,
        cal_a=1.0,
        cal_b=0.0,
        cal_samples=2,
        built_at=2.0,
        stats_through="2026-01-02",
        serve_weight=0.3,
    )
    runtime_state.marker = "runtime"
    saved = model_state.save_state(runtime_state)

    assert saved == runtime
    assert model_state.load_state().marker == "runtime"
    assert packaged.read_bytes() == packaged_before


def test_pipeline_persists_watch_and_log_below_runtime_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    log_dir = tmp_path / "runtime_state" / "logs"
    watch_json = (
        tmp_path
        / "runtime_state"
        / "tennis"
        / "calibration_watch_latest.json"
    )
    payload = {"status": "ok", "n_scored": 42}

    monkeypatch.setattr(run_daily_pipeline, "LOG_DIR", log_dir)
    monkeypatch.setattr(run_daily_pipeline, "WATCH_JSON", watch_json)
    monkeypatch.setattr(
        run_daily_pipeline,
        "run_step",
        lambda *_args, **_kwargs: (
            "CALIBRATION_WATCH_JSON=" + json.dumps(payload)
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline",
            "--skip-rebuild",
            "--skip-scan",
            "--force-monday",
            "--skip-report",
        ],
    )

    assert run_daily_pipeline.main() == 0
    assert list(log_dir.glob("pipeline_*.log"))
    saved = json.loads(watch_json.read_text(encoding="utf-8"))
    assert saved["status"] == "ok"
    assert saved["n_scored"] == 42
    assert saved["run_date"]


def test_weekly_report_can_read_legacy_watch_without_writing_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = tmp_path / "runtime" / "calibration_watch_latest.json"
    legacy = tmp_path / "legacy" / "calibration_watch_latest.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps({"status": "ok", "run_date": date.today().isoformat()}),
        encoding="utf-8",
    )
    legacy_before = legacy.read_bytes()

    monkeypatch.setattr(weekly_report, "WATCH_JSON", runtime)
    monkeypatch.setattr(weekly_report, "LEGACY_WATCH_JSON", legacy)

    watch, note = weekly_report.load_watch()

    assert watch == {"status": "ok", "run_date": date.today().isoformat()}
    assert note == ""
    assert not runtime.exists()
    assert legacy.read_bytes() == legacy_before


def test_weekly_report_rejects_future_watch_timestamp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = tmp_path / "runtime" / "calibration_watch_latest.json"
    runtime.parent.mkdir(parents=True)
    future = (date.today() + timedelta(days=1)).isoformat()
    runtime.write_text(
        json.dumps({"status": "ok", "run_date": future}),
        encoding="utf-8",
    )
    monkeypatch.setattr(weekly_report, "WATCH_JSON", runtime)
    monkeypatch.setattr(
        weekly_report,
        "LEGACY_WATCH_JSON",
        tmp_path / "missing-legacy.json",
    )

    watch, note = weekly_report.load_watch()

    assert watch is None
    assert "Zukunft" in note
    assert "ung&uuml;ltig" in note


def test_atomic_write_keeps_previous_file_if_replace_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "state.json"
    target.write_text("old", encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(runtime_paths.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        runtime_paths.atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob(".state.json.*.tmp"))


def test_model_state_rejects_symlink_pickle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = (tmp_path / "linked.pkl").absolute()
    artifact.write_bytes(pickle.dumps({"not": "trusted"}))
    original_lstat = runtime_paths.os.lstat

    def symlink_lstat(path, *args, **kwargs):
        if Path(path).absolute() == artifact:
            real_stat = original_lstat(path, *args, **kwargs)
            return SimpleNamespace(st_mode=runtime_paths.stat.S_IFLNK, **{
                name: getattr(real_stat, name)
                for name in ("st_uid", "st_dev", "st_ino")
            })
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(runtime_paths.os, "lstat", symlink_lstat)

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="symlink"):
        model_state.load_state(artifact)


def test_pickle_trust_boundary_rejects_wrong_owner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "state.pkl"
    artifact.write_bytes(pickle.dumps({"value": 1}))
    actual_owner = artifact.stat().st_uid
    monkeypatch.setattr(
        runtime_paths,
        "_trusted_owner_ids",
        lambda: {actual_owner + 1},
    )

    with pytest.raises(runtime_paths.RuntimeArtifactTrustError, match="owner"):
        runtime_paths.validate_trusted_pickle_path(artifact)


def test_manual_batch_uses_documented_venv_and_forbids_local_scheduler() -> None:
    batch = (runtime_paths.PROJECT_ROOT / "run_daily.bat").read_text(
        encoding="utf-8",
    ).casefold()

    assert ".venv\\scripts\\python.exe" in batch
    assert ".codex_test_venv" not in batch
    assert "ausschliesslich manueller diagnoselauf" in batch
    assert "nicht in der windows-aufgabenplanung aktivieren" in batch
    assert "vps ist der einzige" in batch
