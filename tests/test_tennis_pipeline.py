from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from scripts import run_daily_pipeline


def test_requested_rebuild_failure_sets_nonzero_exit(monkeypatch) -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        monkeypatch.setattr(run_daily_pipeline, "LOG_DIR", Path(tmp) / "logs")
        monkeypatch.setattr(
            run_daily_pipeline,
            "run_step",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "pipeline",
                "--skip-scan",
                "--skip-watch",
                "--skip-report",
            ],
        )
        assert run_daily_pipeline.main() == 1


def test_all_skipped_pipeline_is_success(monkeypatch) -> None:
    with tempfile.TemporaryDirectory(dir=".") as tmp:
        monkeypatch.setattr(run_daily_pipeline, "LOG_DIR", Path(tmp) / "logs")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "pipeline",
                "--skip-rebuild",
                "--skip-scan",
                "--skip-watch",
                "--skip-report",
            ],
        )
        assert run_daily_pipeline.main() == 0
