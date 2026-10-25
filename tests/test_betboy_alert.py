"""Failure alert helper and its units (Gesamtaudit 25.10.2026, D5).

``scripts/betboy_alert.py`` is installed root-owned as
``/usr/local/libexec/betboy-alert.py`` and started by ``betboy-alert@.service``
through ``OnFailure=betboy-alert@%n.service`` on the core units. It must never
raise, never print a credential, and keep working without a Telegram token.
"""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("betboy_alert", ROOT / "scripts" / "betboy_alert.py")
alert = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alert)
NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def _run_factory(journal="first line\nAPI_FOOTBALL_KEY=abcdef\nlast line"):
    def run(command, **kwargs):
        if command[0] == "systemctl":
            value = {"Result": "exit-code", "ExecMainStatus": "1", "ExecMainExitTimestamp": "Sun 2030-01-01 12:00:00 CET",
                     "InvocationID": "abc"}[command[4]]
            return SimpleNamespace(stdout=value + "\n", returncode=0)
        return SimpleNamespace(stdout=journal, returncode=0)
    return run


def test_redaction_hides_values_that_look_like_credentials():
    text = "API_FOOTBALL_KEY=abcdef token: xyz appid=123 remaining words"
    redacted = alert.redact(text)
    assert "abcdef" not in redacted and "xyz" not in redacted and "123" not in redacted
    assert "remaining words" in redacted


def test_alert_without_telegram_logs_and_keeps_a_runtime_copy(tmp_path, capsys):
    log, copy = tmp_path / "log" / "alerts.jsonl", tmp_path / "ops_alerts.json"
    for _ in range(2):
        assert alert.main(["alert", "betboy-tennis.service"], env={}, run=_run_factory(), log_path=log,
                          runtime_copy_path=copy, now=NOW, owner=None) == 0
    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2 and lines[0]["unit"] == "betboy-tennis.service" and lines[0]["telegram"] == "skipped"
    assert lines[0]["result"] == "exit-code" and lines[0]["execmainstatus"] == "1"
    assert lines[0]["journal_tail"] == ["first line", "API_FOOTBALL_KEY=<redacted>", "last line"]
    copied = json.loads(copy.read_text(encoding="utf-8"))
    assert len(copied) == 2 and copied[-1]["at"] == NOW.isoformat(timespec="seconds")
    printed = capsys.readouterr().out
    assert "journal_tail" not in printed and "abcdef" not in printed and '"unit": "betboy-tennis.service"' in printed


def test_alert_with_telegram_posts_a_short_message_and_never_prints_the_token(tmp_path, capsys):
    sent = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        sent.append((request.full_url, request.data.decode("utf-8"), timeout))
        return Response()

    env = {"TELEGRAM_BOT_TOKEN": "123:SECRET", "TELEGRAM_CHAT_ID": "42"}
    assert alert.main(["alert", "betboy-quotes.service"], env=env, run=_run_factory(), urlopen=urlopen,
                      log_path=tmp_path / "alerts.jsonl", runtime_copy_path=tmp_path / "copy.json",
                      now=NOW, owner=None) == 0
    [(url, body, timeout)] = sent
    assert url.endswith("/bot123:SECRET/sendMessage") and timeout == 10
    assert "chat_id=42" in body and "betboy-quotes.service" in body and "abcdef" not in body
    output = tmp_path.joinpath("alerts.jsonl").read_text(encoding="utf-8") + capsys.readouterr().out
    assert "SECRET" not in output and '"telegram": "sent"' in output

    def failing(request, timeout):
        raise RuntimeError("https://api.telegram.org/bot123:SECRET/sendMessage")

    assert alert.main(["alert", "betboy-quotes.service"], env=env, run=_run_factory(), urlopen=failing,
                      log_path=tmp_path / "alerts.jsonl", runtime_copy_path=tmp_path / "copy.json",
                      now=NOW, owner=None) == 0
    output = tmp_path.joinpath("alerts.jsonl").read_text(encoding="utf-8") + capsys.readouterr().out
    assert "SECRET" not in output and '"telegram": "failed:RuntimeError"' in output


def test_alert_never_raises_on_broken_tools_or_names(tmp_path, capsys):
    def broken(command, **kwargs):
        raise OSError("no systemctl")

    assert alert.main(["alert", "../etc/passwd; rm"], env={}, run=broken, log_path=tmp_path / "x" / "alerts.jsonl",
                      runtime_copy_path=tmp_path / "copy.json", now=NOW, owner=None) == 0
    assert json.loads(capsys.readouterr().out)["unit"] == "invalid-unit-name"
    blocker = tmp_path / "blocker"
    blocker.write_text("a regular file where a directory is needed", encoding="utf-8")
    assert alert.main(["alert", "betboy-app.service"], env={}, run=broken, log_path=blocker / "alerts.jsonl",
                      runtime_copy_path=blocker / "copy.json", now=NOW, owner=None) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["result"] is None and summary.get("log_error") and summary.get("runtime_copy_error")


def test_message_is_bounded():
    record = {"unit": "betboy-wettfinder.service", "at": NOW.isoformat(), "result": "exit-code", "execmainstatus": "1",
              "execmainexittimestamp": None, "journal_tail": ["x" * 400] * 6}
    text = alert.telegram_text(record)
    assert len(text) <= alert.MESSAGE_LIMIT and text.startswith("BetBoy: betboy-wettfinder.service fehlgeschlagen")


@pytest.mark.parametrize("unit", ["betboy-wettfinder", "betboy-tennis", "betboy-esports", "betboy-quotes",
                                  "betboy-football-shadow", "betboy-app"])
def test_core_units_alert_on_failure_and_the_template_runs_the_installed_helper(unit):
    systemd = ROOT / "deploy" / "systemd"
    service = (systemd / f"{unit}.service").read_text(encoding="utf-8")
    assert service.count("OnFailure=betboy-alert@%n.service") == 1
    template = (systemd / "templates" / "betboy-alert@.service").read_text(encoding="utf-8")
    assert "ExecStart=/usr/bin/python3 -I /usr/local/libexec/betboy-alert.py %i" in template
    assert "EnvironmentFile=-/etc/betboy/betboy.env" in template and "Type=oneshot" in template
    # The template drops privileges like every other BetBoy unit; journal access comes from the group only.
    for line in ("User=betboy", "Group=betboy", "SupplementaryGroups=systemd-journal", "UMask=0027",
                 "NoNewPrivileges=true", "PrivateTmp=true", "ProtectHome=true"):
        assert template.count(line) == 1
    assert "ExecStart=/usr/bin" in template and "!" not in template.split("ExecStart=", 1)[1].split("\n", 1)[0]
    for script in ("bootstrap_server.sh", "update_server.sh"):
        source = (ROOT / "deploy" / script).read_text(encoding="utf-8")
        assert "TRUSTED_ALERT_HELPER=/usr/local/libexec/betboy-alert.py" in source
        assert '"$(trusted_file scripts/betboy_alert.py)"' in source
        assert "expected_alert_unit_sha256() {" in source and "validate_trusted_alert_unit" in source
        assert '"$(trusted_file deploy/systemd/templates/betboy-alert@.service)"' in source
