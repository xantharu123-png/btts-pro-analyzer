"""Exit code of the shadow due-runner (owner 25.10.2026, Gesamtaudit D2/D5).

With ``OnFailure=betboy-alert@%n.service`` on ``betboy-football-shadow.service``
every exit 1 is an alert. A run that only waits for a quote must not be one.
"""
import importlib.util
import json
from pathlib import Path

import shadow_clv_automation as shadow

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_football_shadow_due", ROOT / "scripts" / "run_football_shadow_due.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_retry_and_missing_provider_data_are_data_statuses_not_operational_errors():
    data = [
        "Fixture 1551016: keine aktuelle Bet365-Quote mit Providerzeit; Retry",
        "Closing 1551016: Bet365-Quote/Zeitstempel RESULT_HOME fehlt",
        "Fixture 1551016: Details fehlen",
        "Hybrid-Vorbereitung Liga 39: Details fehlen",
    ]
    operational = [
        "Settlement 7: database is locked",
        "Logging 9: Duplicate ohne nachweisbaren Bestand",
        "Hybrid 1551016: KeyError('x')",
        "Fixtures Liga 39: Spielplanabruf fehlgeschlagen",
        "Wetter Oslo: ConnectionError",
    ]
    assert all(shadow.is_data_status(message) for message in data)
    assert not any(shadow.is_data_status(message) for message in operational)
    assert shadow.operational_errors(data + operational) == operational


def test_runner_exits_zero_for_a_partial_run_with_data_statuses_only(monkeypatch, capsys):
    monkeypatch.setattr(runner.shadow, "should_fire", lambda _: True)
    artifact = {"status": "partial", "errors": ["Fixture 1: keine aktuelle Bet365-Quote mit Providerzeit; Retry"],
                "operational_errors": []}
    monkeypatch.setattr(runner.shadow, "run", lambda ctx: {"artifact": artifact})
    assert runner.main() == 0
    assert json.loads(capsys.readouterr().out)["artifact"]["status"] == "partial"


def test_runner_exits_one_for_operational_errors_or_broken_artifacts(monkeypatch, capsys):
    monkeypatch.setattr(runner.shadow, "should_fire", lambda _: True)
    failing = {"status": "partial", "errors": ["Settlement 7: database is locked"],
               "operational_errors": ["Settlement 7: database is locked"]}
    monkeypatch.setattr(runner.shadow, "run", lambda ctx: {"artifact": failing})
    assert runner.main() == 1
    # An artifact of an older runner without the classification is classified here.
    legacy = {"status": "partial", "errors": ["Logging 9: ValueError"]}
    assert runner.exit_code(legacy) == 1
    assert runner.exit_code({"status": "partial", "errors": ["Fixture 2: Details fehlen"]}) == 0
    assert runner.exit_code({"status": "error"}) == 1
    monkeypatch.setattr(runner.shadow, "run", lambda ctx: {"not": "an artifact"})
    assert runner.main() == 1
    monkeypatch.setattr(runner.shadow, "should_fire", lambda _: False)
    assert runner.main() == 0
    capsys.readouterr()


def test_run_artifact_carries_the_classified_operational_errors():
    import inspect
    source = inspect.getsource(shadow.run)
    assert '"operational_errors": operational_errors(errors)[-15:]' in source
