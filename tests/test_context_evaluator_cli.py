"""Explicit isolated offline CLI; no production defaults or free loss claims."""
import subprocess
import sys

from test_context_dataset import prepared


def _run(*args):
    return subprocess.run([sys.executable, "-B", "scripts/evaluate_context_models.py", *args],
                          capture_output=True, text=True, timeout=15)


def test_cli_requires_explicit_input_and_output_paths():
    assert _run().returncode != 0


def test_cli_exposes_only_the_one_source_resolved_interface():
    result = _run("--help")
    assert result.returncode == 0
    assert "--model-db" in result.stdout and "--experiment" in result.stdout


def test_cli_rejects_free_loss_files_and_force_flags(tmp_path):
    result = _run("--model-db", str(tmp_path/"absent.db"), "--experiment", "0"*64,
                  "--output-dir", str(tmp_path/"report"), "--force")
    assert result.returncode != 0
    assert not (tmp_path/"absent.db").exists() and not (tmp_path/"report").exists()


def test_cli_missing_input_does_not_create_database_or_output(tmp_path):
    result = _run("--model-db", str(tmp_path/"absent.db"), "--experiment", "0"*64, "--output-dir", str(tmp_path/"report"))
    assert result.returncode != 0
    assert not (tmp_path/"absent.db").exists() and not (tmp_path/"report").exists()


def test_cli_refuses_configured_production_root_even_with_explicit_flags(tmp_path):
    from runtime_paths import CONTEXT_MODEL_DB_PATH
    result = _run("--model-db", str(CONTEXT_MODEL_DB_PATH), "--experiment", "0"*64, "--output-dir", str(tmp_path/"report"))
    assert result.returncode != 0
    assert '"status": "failed"' in result.stdout


def test_cli_real_offline_dataset_exports_report_but_never_activates(prepared, tmp_path, monkeypatch, capsys):
    import json
    import sqlite3
    from scripts import evaluate_context_models as cli
    from context_dataset_helpers import EVALUATED, copy_packet
    from model_artifacts import _load_active
    packet = copy_packet(prepared, tmp_path)
    class FixtureClock:
        @staticmethod
        def now(tz):
            return EVALUATED
    monkeypatch.setattr(cli, "datetime", FixtureClock)
    output = tmp_path/"export"
    assert cli.main(["--model-db", str(packet["path"]), "--experiment", packet["experiment_ref"],
                     "--output-dir", str(output)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "evaluated_not_activated" and response["approval_count"] == 0
    result = json.loads((output/(response["report_hash"]+".json")).read_bytes())
    assert result["digest"] == response["report_hash"] and result["approvals"] == []
    with sqlite3.connect(packet["path"]) as connection:
        assert _load_active(connection)[1] == {}
